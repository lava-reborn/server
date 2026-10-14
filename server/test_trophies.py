"""Trophies and «Навык бойца»: the owner's rules of 2026-09-25.

  * «обязательно падает трофей, если убивший ниже лвл-ом или одинакового»
    -- a player killed by a player at their level or below leaves a trophy,
    always, in the bag the death leaves; a stronger killer gets none, and a
    mob's kill none either;
  * «навык бойца качается, если убить кого-то, получить с него трофей и
    сдать» -- the kill pays no fighter's skill any more; registering the
    trophy at a registrar (the butchers of Вади-Хальфа, «Мясники», location
    164) does, and costs the trophy's price in afro;
  * the same killer and victim pay the skill once an hour of registrations;
    only the killer registers a trophy; the collection keeps it, merged by
    kind and victim, across a relog;
  * «унеси сохранение трофея от адама к демиру и сделай возможность
    демонстрировать их» -- the valley's registrar is Демир in «Караван»
    (186), Адам on the Nubian market an ordinary stall again; and a
    registered trophy can be put on show (ss_upd 1), places bought
    (ss_upd 3), and anybody inspecting sees the show (ss_get;slot=32) and
    what each trophy says.

In process: eligibility, weighted parts at every level, ss_di_trophy words,
and every Store method on a real SQLite database (the Postgres run is
test_storage_pg's); and a quarry killed half way through a walk, whose
trophy goes into the one bag the death leaves where the walk ends. Over
sockets, with nothing falling off the body but a stack's third
(LAVA_WEAR_DROP=0, LAVA_BAG_DROP=0): two newcomers, a hunter
and a quarry, three kills in the open desert (the last of the quarry as a
member of a clan, which the trophy's «Клан жертвы» keeps), the hunter's
show looked at by
the quarry, a trophy posted from one to the other, and one death to the
dump's dog.

    LAVA_RES=.../lava/res python3 server/test_trophies.py
"""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock, patch

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_WEAR_DROP", "LAVA_BAG_DROP"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import barter  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import world  # noqa: E402
from inventory import BAG  # noqa: E402
from protocol import Str, decode  # noqa: E402

try:
    import trophies  # noqa: E402
except ImportError:
    trophies = None

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


EAR, FINGER, SCALP, SKULL, HAND = 1495, 1494, 1493, 1492, 1496
T0 = 1_790_000_000          # a fixed moment: 2026-09-21 14:13:20 UTC

# --- in process: the rule ------------------------------------------------------
if trophies is None:
    fails.append("no trophies module")
else:
    check("a trophy falls for a killer at the victim's level or below, never above",
          [trophies.falls(k, v) for k, v in ((0, 0), (3, 5), (7, 7), (5, 4), (1, 0))],
          [True, True, True, False, False])
    check("the original's names", [trophies.name_of(t) for t in (EAR, FINGER, SCALP, SKULL, HAND)],
          ["Ухо", "Палец", "Скальп", "Череп", "Кисть"])
    check("the fee is the trophy's price, as the registration window draws it",
          [trophies.fee_of(t) for t in (EAR, FINGER, SCALP, SKULL, HAND)],
          [25, 30, 100, 200, 1500])
    check("a trophy changes hands (the game's template: обмен Да, продажа Нет)",
          [(items.params_of(t)["exchang"], barter.tradable(t)) for t in (EAR, HAND)],
          [(1, True), (1, True)])
    check("the time as Annotation.parseDate reads it, UTC",
          trophies.when(T0), "2026-09-21 14:13:20")
    rec = dict(uniq=5, type_id=EAR, killer_id=1, killer_name="hunter", killer_lvl=2,
               victim_id=2, victim_name="quarry", victim_lvl=3, victim_clan="",
               killed_at=T0, kills=2)
    f = trophies.fields_of(rec)
    check("ss_di_trophy's keys: count and levels, the players' ids, then the"
          " strings, the names last",
          (list(f), f), (["count", "k_id", "k_lvl", "v_id", "v_lvl", "time", "v_clan",
                          "k_name", "v_name"],
                         dict(count=2, k_id=rooms.player_id(1), k_lvl=2,
                              v_id=rooms.player_id(2), v_lvl=3, time="2026-09-21 14:13:20",
                              v_clan="", k_name="hunter", v_name="quarry")))
    check("  ..every string as a string on the wire, whatever it looks like",
          [type(f[k]) for k in ("time", "v_clan", "k_name", "v_name")], [Str] * 4)
    check("the victim's clan at the kill is a word of its own (v_clan, «Клан жертвы»),"
          " none by default",
          (trophies.record(1, "hunter", 2, 2, "quarry", 3, T0, victim_clan="Волки")["victim_clan"],
           trophies.fields_of(dict(rec, victim_clan="Волки"))["v_clan"],
           trophies.record(1, "hunter", 2, 2, "quarry", 3, T0)["victim_clan"]),
          ("Волки", "Волки", ""))
    check("the registrars are the six butchers of Вади-Хальфа, the original's"
          " own, Демир in «Караван», Хассир on the station, Луиджи in Абри's port"
          " market (since 2026-10-12), Нур-ад-Дин on Донгола's station (since"
          " 2026-10-13) and Веласкес on Абу-Хамед's (since 2026-10-14), built as Traders",
          (sorted(trophies.REGISTRARS), world.entity_root(939, world.COMMONER),
           world.entity_root(5193, world.COMMONER), world.entity_root(5212, world.TRADER),
           world.entity_root(5228, world.COMMONER), world.entity_root(740, world.COMMONER)),
          ([105, 156, 740, 939, 940, 941, 942, 943, 1132, 1179, 2033, 2034, 2035, 2036, 5193],
           world.TRADER, world.TRADER, world.TRADER, world.COMMONER, world.TRADER))
    check("  ..and Адам, who stood in for Демир, is none: an ordinary Trader",
          (trophies.is_registrar(5216), world.entity_root(5216, world.TRADER)),
          (False, world.TRADER))
    if hasattr(trophies, "places"):
        S_, M_ = trophies.START_PLACES, trophies.MAX_PLACES
        check("a show: START_PLACES places, one more for each bought, never past"
              " MAX_PLACES", [trophies.places(n) for n in (0, 1, M_)],
              [S_, min(S_ + 1, M_), M_])
    else:
        fails.append("no show: trophies.places")
    check("the kill pays no skill any more: combat's own counter is gone",
          hasattr(combat, "pvp_rep_due"), False)

# --- in process: the store --------------------------------------------------------
st = accounts.Store(os.path.join(tempfile.mkdtemp(), "trophies.db"))
ka, _ = st.register("killer", "secret")
va, _ = st.register("victim", "secret")
K, _ = st.create_character(ka, "Killer", 0, "1")
V, _ = st.create_character(va, "Victim", 0, "1")


def words(**kw):
    return dict(dict(killer_id=K, killer_name="Killer", killer_lvl=0, victim_id=V,
                     victim_name="Victim", victim_lvl=0, victim_clan="", killed_at=T0), **kw)


if trophies is not None and hasattr(st, "create_trophy"):
    t1 = st.create_trophy(0, BAG, EAR, items.TROPHY, words())
    check("a trophy is an items row on the ground and its words, one serial",
          ((t1["char_id"], t1["type_id"], t1["root"], t1["slot"], t1["count"]),
           {k: st.trophy(t1["uniq"])[k] for k in ("type_id", "kills", "owner",
                                                  "registered_at", "paid_at")}),
          ((0, EAR, items.TROPHY, BAG, 1),
           dict(type_id=EAR, kills=1, owner=0, registered_at=None, paid_at=None)))
    check("inventory.di_params adds the words to a trophy's ss_di_trophy",
          {k: v for k, v in inventory.di_params(t1, st).items() if k != "obj"},
          trophies.fields_of(dict(st.trophy(t1["uniq"]), kills=1)))
    check("  ..and without a store it stays what it was", inventory.di_params(t1),
          {"obj": inventory.oid_of(t1), "count": 1})
    st.update_item(t1["uniq"], char_id=K)
    t1 = st.item(t1["uniq"])
    r1 = st.trophy(t1["uniq"])
    # A row that changed under the write: nothing is written at all.
    st.update_item(t1["uniq"], slot=inventory.BANK)
    check("a registration of a row no longer as read is refused",
          st.register_trophy(t1, r1, K, T0 + 60, True, (K, 975, 0), 10), False)
    check("  ..and nothing moved: the thing, its words, the purse, the skill",
          (st.item(t1["uniq"])["char_id"], st.trophy(t1["uniq"])["registered_at"],
           st.money(K), st.character(K)["rep"]), (K, None, (1000, 0), 0))
    st.update_item(t1["uniq"], slot=BAG)
    t1 = st.item(t1["uniq"])
    check("a registration: True", st.register_trophy(t1, r1, K, T0 + 60, True,
                                                     (K, 975, 0), 10), True)
    check("  ..the thing is gone, its words are in the collection, paid; the purse"
          " and the skill written",
          (st.item(t1["uniq"]), [(r["uniq"], r["owner"], r["registered_at"], r["paid_at"])
                                 for r in st.trophies_of(K)], st.money(K),
           st.character(K)["rep"]),
          (None, [(t1["uniq"], K, T0 + 60, T0 + 60)], (975, 0), 10))
    check("a registered trophy is described from its words, having no items row",
          trophies.registered_row(st, t1["uniq"], EAR, items.TROPHY),
          dict(uniq=t1["uniq"], type_id=EAR, root=items.TROPHY, count=1, slot=0))
    check("  ..and only under its own type", trophies.registered_row(st, t1["uniq"], FINGER,
                                                                     items.TROPHY), None)
    check("the pair has paid within the hour, and not before it",
          (st.trophy_paid_since(K, V, T0 + 60 - 3600), st.trophy_paid_since(K, V, T0 + 60),
           st.trophy_paid_since(V, K, 0)), (True, False, False))
    check("a registered one is not registered twice",
          st.register_trophy(t1, r1, K, T0 + 70, True, (K, 950, 0), 20), False)
    t2 = st.create_trophy(K, BAG, EAR, items.TROPHY, words(killed_at=T0 + 600,
                                                           killer_lvl=1, victim_lvl=2))
    into = st.trophy_like(K, EAR, V)
    check("a second ear off the same victim finds the first", into["uniq"], t1["uniq"])
    check("  ..and joins it, unpaid", st.register_trophy(t2, st.trophy(t2["uniq"]), K,
                                                          T0 + 700, False, (K, 950, 0), 10,
                                                          into), True)
    merged = st.trophies_of(K)
    check("  ..one entry: two kills, the newer one's levels and time, the old paid mark",
          [(r["uniq"], r["kills"], r["killed_at"], r["killer_lvl"], r["victim_lvl"],
            r["paid_at"]) for r in merged],
          [(t1["uniq"], 2, T0 + 600, 1, 2, T0 + 60)])
    check("  ..the second's words and thing are gone", (st.trophy(t2["uniq"]),
                                                         st.item(t2["uniq"])), (None, None))
    check("a stranger cannot delete it; its owner can",
          (st.delete_trophy(t1["uniq"], V), st.delete_trophy(t1["uniq"], K),
           st.trophies_of(K)), (False, True, []))
    check("  ..and the pair's pay mark outlives the entry: deleting it does not reset"
          " the hour; nothing is left to join, describe or delete again",
          (st.trophy_paid_since(K, V, T0 + 60 - 3600), st.trophy_like(K, EAR, V),
           trophies.registered_row(st, t1["uniq"], EAR, items.TROPHY),
           st.delete_trophy(t1["uniq"], K), st.delete_trophy(t1["uniq"], 0)),
          (True, None, None, False, False))
    t3 = st.create_trophy(K, BAG, SKULL, items.TROPHY, words())
    st.rekey_trophy(t3["uniq"], 9999)
    check("the words follow a trophy unpacked from a letter under a new serial",
          (st.trophy(t3["uniq"]), st.trophy(9999)["type_id"]), (None, SKULL))
    t4 = st.create_trophy(0, BAG, SCALP, items.TROPHY, words())
    t5 = st.create_trophy(0, BAG, SCALP, items.TROPHY, words())
    st.forget_trophy(t4["uniq"])
    check("a bag that runs out takes its trophies' words with it",
          st.trophy(t4["uniq"]), None)
    check("the start's clear of the ground takes the words of what lay there",
          (st.clear_ground(0), st.trophy(t5["uniq"]), st.trophy(9999) is not None),
          (2, None, True))
    st.forget_trophy(t1["uniq"])
    check("  ..and neither it nor a bag running out takes a deleted entry's pay mark",
          st.trophy_paid_since(K, V, T0 + 60 - 3600), True)

# --- in process: the show ------------------------------------------------------
if trophies is not None and hasattr(st, "show_trophy") and hasattr(trophies, "show_of"):
    S_ = trophies.START_PLACES

    def registered(type_id, **kw):
        t = st.create_trophy(K, BAG, type_id, items.TROPHY, words(**kw))
        st.register_trophy(t, st.trophy(t["uniq"]), K, T0 + 900, False,
                           (K, st.money(K)[0], 0), 10)
        return t["uniq"], inventory.oid(t["uniq"], type_id, items.TROPHY)

    def shown():
        return [str(o) for o in trophies.show_of(st, K)]

    ua, oa = registered(SCALP, victim_id=V + 100)
    ub, ob = registered(SKULL, victim_id=V + 101)
    loose = st.create_trophy(K, BAG, EAR, items.TROPHY, words(victim_id=V + 102))
    check("nobody has shown anything: START_PLACES empty places, a stranger's none",
          (shown(), trophies.show_of(st, 0), trophies.show_of(st, 987654)),
          (["0"] * S_, [], []))
    check("an entry on the first place", (st.show_trophy(K, 0, ua), shown()),
          (True, [oa] + ["0"] * (S_ - 1)))
    check("  ..on the last one: it moves, an entry is never shown twice",
          (st.show_trophy(K, S_ - 1, ua), shown()), (True, ["0"] * (S_ - 1) + [oa]))
    check("  ..another on the same place: the first goes back to being kept",
          (st.show_trophy(K, S_ - 1, ub), shown(), st.trophy(ua)["shown"]),
          (True, ["0"] * (S_ - 1) + [ob], None))
    check("neither a stranger's entry, nor a thing in the bag, nor nothing is shown,"
          " and a refusal empties no place",
          (st.show_trophy(V, 0, ua), st.show_trophy(K, S_ - 1, loose["uniq"]),
           st.show_trophy(K, S_ - 1, 99999), st.show_trophy(0, 0, ua), shown()),
          (False, False, False, False, ["0"] * (S_ - 1) + [ob]))
    check("an empty place is emptied", (st.show_trophy(K, S_ - 1), shown()),
          (True, ["0"] * S_))
    st.show_trophy(K, 1, ub)
    check("a deleted entry leaves the show with the collection",
          (st.delete_trophy(ub, K), shown(), st.trophy(ub)["shown"], st.shown_trophies(K)),
          (True, ["0"] * S_, None, {}))
    st.set_money(K, 900, 7)
    check("a place bought: the count and the purse at once",
          (st.buy_trophy_place(K, 0, 900 - trophies.PLACE_PRICE, 7),
           st.character(K)["trophy_places"], st.money(K), len(shown())),
          (1, 1, (900 - trophies.PLACE_PRICE, 7), trophies.places(1)))
    check("  ..one counted from a stale count is no purchase: nothing written",
          (st.buy_trophy_place(K, 0, 0, 0), st.character(K)["trophy_places"], st.money(K)),
          (None, 1, (900 - trophies.PLACE_PRICE, 7)))
else:
    fails.append("no show in the store (Store.show_trophy, trophies.show_of)")

# --- in process: the victim's clan --------------------------------------------
if trophies is not None and hasattr(trophies, "clan_of"):
    pack = st.clan_create(V, "Волки", "волки", "", (V,) + tuple(st.money(V)))
    check("trophies.clan_of: the clan a character is in, read from the database; ''"
          " for one in none and for nobody",
          (trophies.clan_of(st, V), trophies.clan_of(st, K), trophies.clan_of(st, 0)),
          ("Волки", "", ""))
    st.clan_disband(pack)
    check("  ..and '' again once the clan is no more", trophies.clan_of(st, V), "")
else:
    fails.append("no trophies.clan_of")


# --- in process: a quarry killed on its way ---------------------------------------
# The client does not stop a figure that dies walking (DisplayLocScene.dead
# only plays the fall): the corpse finishes the walk and lies where the path
# ends, and so does what fell off it (Fighter.drop_on_death, on pos). The
# trophy goes into that bag -- not into a second one on the hex the figure
# was crossing when the blow landed (Fighter.cell, the live cell), with the
# killer told it lies «на месте гибели».
class _Room(object):
    combat = None
    ws = False

    def __init__(self, loc):
        self.loc = loc
        self.npcs = {}
        self.players = {}
        self.sent = []

    def broadcast(self, frame, exclude=None):
        self.sent.append(frame)


class _Inv(object):
    """What a death asks of a session's Inventory, on the real store."""
    locked = frozenset()

    def __init__(self, sess):
        self.sess, self.store = sess, st

    def rows(self):
        return st.items_of(self.sess.char_id)

    def forget_reload(self, uniq):
        pass

    def push_status(self, row, status):
        pass

    def push_di(self, row):
        pass

    def refresh_gear(self):
        pass


class _Seat(object):
    """A player in that room: pos is where its walk ends, live the hex its
    figure has reached (what server.Session.live_cell answers)."""

    def __init__(self, room, char_id, nick, pos, live):
        self.room, self.char_id, self.nick = room, char_id, nick
        self.pos, self.live = pos, live
        self.pid = rooms.player_id(char_id)
        self.inv = _Inv(self)
        self.char = progression.Character()
        self.said = []
        self.combat = combat.Fighter(self)
        room.players[self] = None

    def live_cell(self):
        return self.live

    def character(self):
        return self.char

    def send(self, *cmd, **params):
        pass

    def say(self, text):
        self.said.append(text)


async def _killed_walking():
    loc = world.location(world.location_at(5992, 1760))     # the desert below
    path = [next(c for c in range(loc.width * loc.height) if c not in loc.obstacles
                 and len(progression.hex_neighbours(c, loc.width, loc.height)) == 6)]
    while len(path) < 5:
        path.append(next(n for n in progression.hex_neighbours(path[-1], loc.width, loc.height)
                         if n not in loc.obstacles and n not in path))
    room = _Room(loc)
    hunter = _Seat(room, K, "Killer", path[0], path[0])
    quarry = _Seat(room, V, "Victim", path[-1], path[1])
    stack = st.create_item(V, AMMO, items.root_of(AMMO), slot=BAG, count=9)
    check("the quarry's figure on the second hex of its walk, the walk ending three on",
          (quarry.combat.cell, quarry.pos), (path[1], path[-1]))
    rc = combat.room_combat(room, st)
    with patch.object(trophies, "random") as draw:
        draw.randrange.return_value = 0
        rc.kill(quarry.combat, hunter.combat)
    lying = {cell: list(bag.uniqs) for cell, bag in rc.loot.items()}
    trophy = [u for u in lying.get(path[-1], ()) if (st.item(u) or {}).get("root") == items.TROPHY]
    check("killed walking: one bag, where the walk ends -- the corpse's",
          ([p["hex"] for n, p in room.sent if n == "ss_loot"], list(lying)),
          ([[path[-1]]], [path[-1]]))
    check("  ..a third of the stack in it, and the trophy with it",
          (sorted((st.item(u) or {}).get("type_id") for u in lying.get(path[-1], ())),
           len(trophy), (st.item(stack["uniq"]) or {}).get("count")),
          (sorted([AMMO, EAR]), 1, 6))
    for bag in rc.loot.values():
        if bag.expiry is not None:
            bag.expiry.cancel()


AMMO = 6188
try:
    asyncio.run(_killed_walking())
except Exception:
    import traceback
    fails.append("the walker's death broke:\n" + traceback.format_exc())


# --- in process: every rarity through the real drop and store --------------------
# Exhaust every integer draw, including all boundaries, without sampling noise.
# Level 5 reproduces the report of fingers only; newcomers and veterans must
# have the same distribution. Only the source of randomness is replaced.
for level in (0, 5, 20):
    killer = SimpleNamespace(level=level, store=st,
                             sess=SimpleNamespace(char_id=K, nick="Killer", say=Mock()))
    victim = SimpleNamespace(level=level, rc=Mock(),
                             sess=SimpleNamespace(char_id=V, nick="Victim", pos=42))
    parts, records_ok, bags_ok = [], [], []
    with patch.object(trophies, "random") as draw:
        draw.randrange.side_effect = range(100)
        for _ in range(100):
            row = trophies.drop(killer, victim, combat.LOOT_OWNER, BAG)
            parts.append(row["type_id"])
            rec = st.trophy(row["uniq"])
            records_ok.append((rec["type_id"], rec["killer_lvl"], rec["victim_lvl"],
                               rec["kills"]) == (row["type_id"], level, level, 1))
            bags_ok.append(victim.rc.add_to_bag.call_args.args == (42, [row]))
        check("level %d: all five parts, ear 40%%, finger 30%%, scalp 18%%,"
              " hand 10%%, skull 2%%" % level, Counter(parts),
              {EAR: 40, FINGER: 30, SCALP: 18, HAND: 10, SKULL: 2})
        check("  ..one uniform draw per kill, with 100 possible outcomes",
              [c.args for c in draw.randrange.call_args_list], [(100,)] * 100)
    check("  ..each part is recorded with the actual levels and put in the death bag",
          (all(records_ok), all(bags_ok), victim.rc.add_to_bag.call_count),
          (True, True, 100))
    killer.level = level + 1
    with patch.object(trophies, "random") as draw:
        victim.rc.reset_mock()
        check("  ..a stronger killer gets no trophy and makes no rarity draw",
              (trophies.drop(killer, victim, combat.LOOT_OWNER, BAG),
               draw.randrange.called, victim.rc.add_to_bag.called), (None, False, False))
st.close()

# --- the server -----------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "trophies_srv.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for login_ in ("hunter", "quarry"):
    _store.register(login_, "secret")
_store.close()
CRED = {n: accounts.credential(n, "secret") for n in ("hunter", "quarry")}

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="120", LAVA_LEAVE_COMBAT="2", LAVA_SEED="7",
           LAVA_WEAR_DROP="0", LAVA_BAG_DROP="0")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
# The quarry dies once as a member of a clan written straight into the
# database: its client here never asks for a roster, and the line telling
# it to reload the page (clans.DEAF_LINE) is not what this suite reads.
env["LAVA_CLAN_DEAF_CHECK"] = "0"
# Two ears exercise collection merging; a skull then exercises a different
# rarity's pickup, description and fee. Patch only trophy randomness so combat
# keeps its seeded rolls and the production selection/drop path still runs.
_boot = """import runpy
from unittest.mock import patch
import trophies
with patch.object(trophies, 'random') as draw:
    draw.randrange.side_effect = [0, 39, 99]
    runpy.run_path('server.py', run_name='__main__')
"""
srv = subprocess.Popen([sys.executable, "-c", _boot], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def said(frames):
    return [p["entry"] for p in named(frames, "userMsg")]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)


def newcomer(c, cred, name):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % name)
    c.frames()
    c.send("actPlayer;")
    got = c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return got + c.frames(wait=2)


def come_back(c, cred):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    got = c.frames()
    c.send("selPers;num=0;")
    got += c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return got + c.frames(wait=2)


def goto(c, where):
    """/goto a location or a map cell: (the cell the lenter gave, every frame)."""
    chat(c, "/goto %d %d" % where if isinstance(where, tuple) else "/goto %d" % where)
    got = c.until(lambda f: f[0] == "lcall", 3)
    c.send("lenter;accept=1;")
    got += c.frames(wait=2)
    return named(got, "lenter")[0]["pos"], got


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.2)


def store():
    return accounts.Store(DB)


def char_id(name):
    s = store()
    row = s.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    s.close()
    return row["id"]


def db_rows(sql, args=()):
    s = store()
    out = [dict(r) for r in s.db.execute(sql, args).fetchall()]
    s.close()
    return out


def with_store(fn):
    s = store()
    try:
        return fn(s)
    finally:
        s.close()


def trophy_count():
    return db_rows("SELECT COUNT(*) AS n FROM trophies")[0]["n"]


def di_of(c, oid):
    c.send("ss_get_di;obj=x%s;" % oid)
    got = c.until(lambda f: f[0].startswith("ss_di_"))
    return [(n, p) for n, p in got if n.startswith("ss_di_")][0]


DESERT = (5992, 1760)   # open desert, pvp, nobody else in it (test_pvp)
BUTCHERS = 164          # «Мясники», Вади-Хальфа
MARKET = 185            # Нубийский рынок: Борис, an ordinary stall
BORIS = 5212
ADAM = 5216             # also on the market: the valley's registrar until 2026-09-25
CARAVAN = 186           # «Караван», inside the Nubian valley
DEMIR = 5193            # there: the valley's registrar now (world.py)
RATCATCHER = 5194       # beside him, a Commoner: the caravan's «Прописка»
DUMP = 100
DOG_HOME = 4551


def kill(h, q, QP):
    """Both to the desert, the hunter first; he steps beside the quarry and
    swings until it falls. Returns (hunter's frames, quarry's, the cell)."""
    goto(h, DESERT)
    h.frames(0.5)
    where, _got = goto(q, DESERT)
    h.frames(1.0)
    q.frames(0.5)
    desert = world.location(world.location_at(*DESERT))
    spot = next(n for n in progression.hex_neighbours(where, desert.width, desert.height)
                if n not in desert.obstacles)
    h.send("moveTo;path=|%d|%d|;" % (where, spot))
    h.frames(0.5 + mobs.HEX_MS / 1000.0)
    seen_h, seen_q = [], []
    for _ in range(30):
        h.send("ss_use;type=16;obj=x0;target=x1%08x;" % QP)
        seen_h += h.until(lambda f: f[0] in ("caHit", "caMiss") or
                          (f[0] == "cmdAck" and f[1].get("res") != 0), 3.0)
        seen_q += q.frames(0.3)
        if any(n == "lch" and p.get("dead") == 0 for n, p in seen_q):
            break
    seen_h += h.frames(1.0)
    seen_q += q.frames(0.5)
    return seen_h, seen_q, where


def weak_again(q, cred, name):
    """The quarry back on its feet, logged out, one hit point, logged in."""
    q.send("resurrect;res_type=0;")
    q.until(lambda f: f[0] == "lcall", 3)
    leave(q)
    with_store(lambda s: s.save_character_state(char_id(name), hp=1, sp=0))
    q = Client(connect())
    come_back(q, cred)
    return q


def take_from_bag(h, cell, oid):
    h.send("ss_create;s_type=0;target=%d;" % cell)
    opened = acks(h.frames())
    h.send("ss_get;slot=24;")
    listed = [str(o) for o in named(h.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
    inside = listed[listed.index("0") + 1:]
    h.send("ss_upd;s_status=1;obj=x%s;param=1;" % oid)
    took = acks(h.frames())
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    return opened, inside, took


def butcher(arrival):
    """(entity id, userInfo_Trader) of the first butcher in an arrival."""
    for p in named(arrival, "userInfo_Trader"):
        if p["name"] in world.TROPHY_REGISTRARS:
            return p["id"], p
    return None, {}


def register(c, eid, oid):
    c.send("ss_create;s_type=1;target=%d;" % eid)
    opened = acks(c.frames())
    c.send("ss_upd;s_status=6;obj=x%s;" % oid)
    got = c.until(lambda f: f[0] == "cmdAck", 3) + c.frames(0.6)
    c.send("ss_upd;s_status=0;obj=x0;")
    got += c.frames(0.3)
    return opened, got


def mine(frames):
    return [p for p in named(frames, "userInfo_Player") if p.get("id") == 0]


try:
    h = Client(connect())
    newcomer(h, CRED["hunter"], "hunter")
    q = Client(connect())
    newcomer(q, CRED["quarry"], "quarry")
    leave(q)
    H, Q = char_id("hunter"), char_id("quarry")
    HP_, QP = rooms.player_id(H), rooms.player_id(Q)
    with_store(lambda s: s.save_character_state(Q, hp=1, sp=0))
    q = Client(connect())
    come_back(q, CRED["quarry"])
    START = db_rows("SELECT afro, rep FROM characters WHERE id = ?", (H,))[0]
    check("two newcomers, level 0 both; the hunter's purse and skill as born",
          (START["afro"], START["rep"]), (progression.START_AFRO, 0))

    # === kill 1: an equal -> a trophy, and no skill yet =========================
    before = time.time()
    seen_h, seen_q, cell = kill(h, q, QP)
    check("the quarry falls to the hunter's fists",
          [p for n, p in seen_q if n == "lch" and "dead" in p], [{"dead": 0}])
    rows = db_rows("SELECT * FROM trophies")
    check("one trophy, an ear: the hunter killed an equal",
          [(r["type_id"], r["killer_id"], r["killer_name"], r["killer_lvl"],
            r["victim_id"], r["victim_name"], r["victim_lvl"], r["victim_clan"], r["kills"],
            r["owner"], r["registered_at"]) for r in rows],
          [(EAR, H, "hunter", 0, Q, "quarry", 0, "", 1, 0, None)])
    T1 = rows[0]["uniq"] if rows else 0
    check("  ..written at the kill", bool(rows) and before - 1 <= rows[0]["killed_at"]
          <= time.time() + 1, True)
    lying = with_store(lambda s: s.item(T1)) or {}
    check("  ..lying in the bag on the quarry's cell, nobody's",
          (lying.get("char_id"), lying.get("slot"), lying.get("root")),
          (combat.LOOT_OWNER, BAG, items.TROPHY))
    check("the hunter sees one bag where the quarry fell",
          [(p["s_status"], p["hex"]) for p in named(seen_h, "ss_loot")], [(1, [cell])])
    check("and is told of the trophy and where to register it",
          [("трофей «Ухо»" in t and "Вади-Хальф" in t) for t in said(seen_h)
           if "трофей" in t], [True])
    check("the kill itself pays no fighter's skill: no userInfo_Player, rep 0",
          (mine(seen_h), db_rows("SELECT rep FROM characters WHERE id = ?", (H,))[0]["rep"]),
          ([], 0))
    OID1 = inventory.oid(T1, EAR, items.TROPHY)
    opened, inside, took = take_from_bag(h, cell, OID1)
    check("the hunter opens the bag, finds the trophy in it, takes it",
          (opened, OID1 in inside, took), ([0], True, [0]))
    check("  ..it is his now, in his backpack",
          (with_store(lambda s: s.item(T1)) or {}).get("char_id"), H)
    name, di = di_of(h, OID1)
    killed_at = rows[0]["killed_at"] if rows else 0
    WORDS = dict(count=1, k_id=HP_, k_lvl=0, v_id=QP, v_lvl=0,
                 time=trophies.when(killed_at) if trophies else None,
                 v_clan="", k_name="hunter", v_name="quarry")
    check("its ss_di_trophy says who killed whom, at what levels, and when",
          (name, {k: di.get(k) for k in WORDS}), ("ss_di_trophy", WORDS))

    # --- an ordinary stall neither buys nor registers it --------------------------
    _pos, arrival = goto(h, MARKET)
    stall = next((p for p in named(arrival, "userInfo_Trader") if p["name"] == BORIS), {})
    check("Борис is an ordinary stall: no trophies", (stall.get("can_trade"),
                                                      stall.get("can_trophy")), (1, 0))
    h.send("ss_create;s_type=1;target=%d;" % stall.get("id", 0))
    h.frames()
    h.send("ss_upd;s_status=2;obj=x%s;param=1;" % OID1)
    sold = acks(h.frames())
    h.send("ss_upd;s_status=6;obj=x%s;" % OID1)
    reg = acks(h.frames())
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    check("a trophy is not for sale (\"Вы не можете продать трофеи\"), nor is it"
          " registered at a stall", (sold, reg), ([inventory.RES_REFUSED], [inventory.RES_REFUSED]))
    check("  ..and stays in the bag", (with_store(lambda s: s.item(T1)) or {}).get("char_id"), H)
    # Адам stood in as the valley's registrar until the owner moved it to
    # Демир: an ordinary stall again, the emptied one he was before.
    adam = next((p for p in named(arrival, "userInfo_Trader") if p["name"] == ADAM), {})
    check("Адам on the Nubian market takes no trophies any more: his stall as it was"
          " before him (can_trade, can_repair, nothing on it)",
          (adam.get("can_trophy"), adam.get("can_trade"), adam.get("can_repair"),
           adam.get("type_list")), (0, 1, 1, items.stock_for(ADAM)))
    opened, got = register(h, adam.get("id", 0), OID1)
    check("  ..and a registration there is refused, the trophy still in the bag",
          (opened, acks(got), named(got, "ss_obj_status"),
           (with_store(lambda s: s.item(T1)) or {}).get("slot")),
          ([0], [inventory.RES_REFUSED], [], BAG))

    # --- the relog keeps the words ------------------------------------------------
    leave(h)
    h = Client(connect())
    come_back(h, CRED["hunter"])
    check("after a relog the trophy says the same", di_of(h, OID1), ("ss_di_trophy", dict(
        di, obj=di.get("obj"))))

    # === the registration at the butchers =========================================
    _pos, arrival = goto(h, BUTCHERS)
    eid, info = butcher(arrival)
    check("the butchers of Вади-Хальфа are Traders that only register trophies",
          (bool(eid), info.get("can_trophy"), info.get("can_trade"), info.get("can_repair"),
           info.get("type_list")), (True, 1, 0, 0, []))
    newusers = {p["newUser"]: p.get("rtype") for n, p in arrival if n == "lch" and "newUser" in p}
    check("  ..built as Traders on the client (lch rtype=1)", newusers.get(eid), world.TRADER)
    # The first one is registered with Демир in «Караван», the valley's own
    # registrar -- a newcomer cannot get out to the butchers.
    _pos, arrival = goto(h, CARAVAN)
    demir = next((p for p in named(arrival, "userInfo_Trader") if p["name"] == DEMIR), {})
    eid = demir.get("id", 0)
    newusers = {p["newUser"]: p.get("rtype") for n, p in arrival if n == "lch" and "newUser" in p}
    check("Демир in «Караван» registers: a Trader on the client (lch rtype=1, no longer"
          " the Commoner of mobs.xml) that only takes trophies",
          (newusers.get(eid), demir.get("can_trophy"), demir.get("can_trade"),
           demir.get("can_repair"), demir.get("type_list")), (world.TRADER, 1, 0, 0, []))
    check("  ..and still himself: his name and figure, an ally, and the quests the quest"
          " table gives him (the quests tab is any class's)",
          (demir.get("name"), demir.get("res"), demir.get("ally"), demir.get("give_quests"),
           demir.get("take_quests")),
          (DEMIR, DEMIR, 1, quests.given_by(DEMIR), quests.taken_by(DEMIR)))
    # Home registration belongs to the caravan's healer, not its commoners
    # or the trophy registrar, whose Trader window has no support tab.
    rat = next((p for p in named(arrival, "userInfo_Commoner") if p["name"] == RATCATCHER), {})
    h.send("on_conv;mob=%d;op=0;" % rat.get("id", 0))
    check("  ..the ratcatcher neither offers nor accepts home registration",
          (rat.get("can_set_home"), acks(h.frames())), (0, [2]))
    healer = next((p for p in named(arrival, "userInfo_Medic") if p["name"] == 5202), {})
    h.send("on_conv;mob=%d;op=0;" % healer.get("id", 0))
    check("  ..the healer offers registration and registers the caravan as home",
          (healer.get("can_set_home"), acks(h.frames()),
           db_rows("SELECT home_loc FROM characters WHERE id = ?", (H,))[0]["home_loc"]),
          (1, [0], CARAVAN))
    h.send("on_conv;mob=%d;op=0;" % eid)
    check("  ..the trophy registrar refuses home registration too",
          acks(h.frames()), [2])
    opened, got = register(h, eid, OID1)
    check("the stall opens; the registration is answered 0",
          (opened, acks(got)), ([0], [0]))
    check("  ..the trophy leaves the bag", [(str(p["obj"]), p["status"])
                                            for p in named(got, "ss_obj_status")],
          [(OID1, 0)])
    check("  ..the fee is paid and «Навык бойца» rises by an equal's price",
          [(p["afro"], p["rep"]) for p in mine(got)],
          [(START["afro"] - 25, [1])])
    check("  ..and the chat says so", [t.startswith("Трофей зарегистрирован: Ухо — quarry")
                                       for t in said(got)], [True])
    now_h = db_rows("SELECT afro, rep FROM characters WHERE id = ?", (H,))[0]
    rec = (db_rows("SELECT * FROM trophies WHERE uniq = ?", (T1,)) or [{}])[0]
    check("the database: purse, skill, no item, the words in his collection, paid",
          ((now_h["afro"], now_h["rep"]), with_store(lambda s: s.item(T1)),
           rec.get("owner"), rec.get("registered_at") is not None,
           rec.get("paid_at") == rec.get("registered_at")),
          ((START["afro"] - 25, 1), None, H, True, True))

    # --- the collection window (s_type=6) -----------------------------------------
    def collection(c):
        c.send("ss_create;s_type=6;target=0;")
        opened = acks(c.frames())
        c.send("ss_get;target=0;slot=16;")
        listed = [str(o) for o in named(c.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
        return opened, listed

    opened, listed = collection(h)
    check("the collection opens and lists the registered trophy, no divider",
          (opened, listed), ([0], [OID1]))
    name, di2 = di_of(h, OID1)
    check("  ..described from its words though no items row is left",
          (name, {k: di2.get(k) for k in WORDS}), ("ss_di_trophy", WORDS))
    # --- the show: ss_get;slot=32, ss_upd 1 (put on / take off), 3 (a place) --------
    S = getattr(trophies, "START_PLACES", 0)
    M = getattr(trophies, "MAX_PLACES", 0)
    PRICE = getattr(trophies, "PLACE_PRICE", 0)
    NOBODY = "0"

    def show(c, target=0):
        """(the frames that answered, the o_list) of one ss_get;slot=32."""
        c.send("ss_get;target=%d;slot=32;" % target)
        got = c.frames()
        return ([n for n, p in got if n in ("ss_ack", "cmdAck")],
                [str(o) for p in named(got, "ss_ack") for o in p["o_list"]])

    def put(c, oid, place):
        c.send("ss_upd;s_status=1;obj=x%s;param=%d;" % (oid, place))
        return acks(c.frames())

    def buy(c):
        c.send("ss_upd;s_status=3;")
        return c.frames()

    def purse_and_places():
        row = db_rows("SELECT * FROM characters WHERE id = ?", (H,))[0]
        return row["afro"], row.get("trophy_places")

    check("his show, as the window asks for it: START_PLACES empty places, one ss_ack",
          show(h), (["ss_ack"], [NOBODY] * S))
    check("the hunter puts the ear on the first place: 0, and it stands there",
          (put(h, OID1, 0), show(h)[1]), ([0], [OID1] + [NOBODY] * (S - 1)))
    check("  ..onto the last one: it moves, never shown twice",
          (put(h, OID1, S - 1), show(h)[1]), ([0], [NOBODY] * (S - 1) + [OID1]))
    check("  ..x0 takes it off (the window's drag back into the collection)",
          (put(h, NOBODY, S - 1), show(h)[1]), ([0], [NOBODY] * S))
    check("a place the show does not have is refused (31, no words), nothing moves",
          (put(h, OID1, S), show(h)[1]), ([inventory.RES_UNWORDED], [NOBODY] * S))
    check("  ..and so is a trophy that is no entry of his collection (12)",
          (put(h, inventory.oid(987654, EAR, items.TROPHY), 0), show(h)[1]),
          ([inventory.RES_NOT_FOUND], [NOBODY] * S))
    check("the ear back on the first place", put(h, OID1, 0), [0])
    h.send("ss_upd;s_status=0;obj=x0;")
    check("closing the collection is not answered", h.frames(0.4), [])

    # A place costs PRICE afro: exactly that much in the purse, then none.
    leave(h)
    with_store(lambda s: s.save_character_state(H, afro=PRICE))
    h = Client(connect())
    come_back(h, CRED["hunter"])
    check("after a relog the collection is the same", collection(h), ([0], [OID1]))
    check("  ..and so is the show", show(h), (["ss_ack"], [OID1] + [NOBODY] * (S - 1)))
    got = buy(h)
    check("a place bought with exactly its price: 0, the purse down to nothing",
          (acks(got), [p["afro"] for p in mine(got)], purse_and_places()),
          ([0], [0], (0, 1)))
    check("  ..the show one place longer", show(h)[1], [OID1] + [NOBODY] * S)
    got = buy(h)
    check("another with nothing left: 21, the client's «У вас недостаточно денег»;"
          " nothing charged, nothing given",
          (acks(got), mine(got), purse_and_places(), len(show(h)[1])),
          ([inventory.RES_NO_MONEY], [], (0, 1), S + 1))
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    # And the last place there is: money enough for two, room for one.
    leave(h)
    with_store(lambda s: s.save_character_state(H, afro=2 * PRICE,
                                                trophy_places=M - S - 1))
    h = Client(connect())
    come_back(h, CRED["hunter"])
    collection(h)
    got = buy(h)
    check("the last place of MAX_PLACES bought", (acks(got), purse_and_places()),
          ([0], (PRICE, M - S)))
    got = buy(h)
    check("  ..and no more past it, money or not: 31, nothing charged",
          (acks(got), mine(got), purse_and_places(), show(h)[1]),
          ([inventory.RES_UNWORDED], [], (PRICE, M - S), [OID1] + [NOBODY] * (M - 1)))
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    leave(h)
    with_store(lambda s: s.save_character_state(H, afro=START["afro"] - 25))
    h = Client(connect())
    come_back(h, CRED["hunter"])
    check("after a relog: the places bought and the ear on the first",
          show(h), (["ss_ack"], [OID1] + [NOBODY] * (M - 1)))

    # === what another player sees: the inspect window's trophy tab ================
    q = weak_again(q, CRED["quarry"], "quarry")
    check("the quarry inspects the hunter (ss_get;target=<his id>;slot=32): exactly"
          " his show, one ss_ack", show(q, HP_), (["ss_ack"], [OID1] + [NOBODY] * (M - 1)))
    q.send("ss_get_di;target=%d;obj=x%s;" % (HP_, OID1))
    got = q.until(lambda f: f[0].startswith("ss_di_"))
    seen = [(n, p) for n, p in got if n.startswith("ss_di_")]
    check("  ..and the ear on it says what it says to him: who killed whom, when",
          [(n, {k: p.get(k) for k in WORDS}) for n, p in seen], [("ss_di_trophy", WORDS)])
    check("  ..his own show (target 0) is his, empty; a creature has none",
          (show(q)[1], show(q, rooms.FIRST_NPC_ID)), ([NOBODY] * S, (["ss_ack"], [])))

    # === kill 2: the same pair within the hour ====================================
    seen_h, seen_q, cell = kill(h, q, QP)
    rows = db_rows("SELECT * FROM trophies WHERE registered_at IS NULL")
    check("the same victim again: a second ear", [(r["type_id"], r["killer_id"], r["victim_id"])
                                                  for r in rows], [(EAR, H, Q)])
    T2 = rows[0]["uniq"] if rows else 0
    OID2 = inventory.oid(T2, EAR, items.TROPHY)
    _o, _inside, took = take_from_bag(h, cell, OID2)
    check("  ..picked up", took, [0])
    _pos, arrival = goto(h, BUTCHERS)
    eid, _info = butcher(arrival)
    _opened, got = register(h, eid, OID2)
    check("registered within the hour: answered 0, the fee paid, the skill as it was",
          (acks(got), [(p["afro"], p["rep"]) for p in mine(got)]),
          ([0], [(START["afro"] - 50, [1])]))
    check("  ..and the chat says why it did not rise",
          [("не чаще раза в час" in t) for t in said(got)], [True])
    # The client built OID1 when it took it out of the bag and never asks
    # for it again (ItemFactory.create returns the stored item): the entry
    # that grew is told unasked, after the frame that takes the new one off.
    check("  ..the entry it joined is described again unasked, right after the new one"
          " leaves the bag: «Количество» 2, the newer kill's time",
          ([n for n, p in got if n in ("cmdAck", "ss_obj_status", "ss_di_trophy")],
           [(str(p["obj"]), p.get("count"), p.get("time")) for p in named(got, "ss_di_trophy")]),
          (["cmdAck", "ss_obj_status", "ss_di_trophy"],
           [(OID1, 2, trophies.when(rows[0]["killed_at"]) if rows else None)]))
    merged = db_rows("SELECT * FROM trophies WHERE owner = ? AND registered_at IS NOT NULL",
                     (H,))
    check("the collection keeps one ear off the quarry, two kills, the newer time",
          [(r["uniq"], r["kills"], r["killed_at"]) for r in merged],
          [(T1, 2, rows[0]["killed_at"] if rows else None)])
    check("  ..the second one's thing and words are gone",
          (with_store(lambda s: s.item(T2)), with_store(lambda s: s.trophy(T2))), (None, None))
    _opened, listed = collection(h)
    name, di3 = di_of(h, OID1)
    check("  ..the window lists one, «Количество» 2", (listed, di3.get("count")), ([OID1], 2))
    check("  ..and the entry that grew is still on show, on its place",
          show(h)[1], [OID1] + [NOBODY] * (M - 1))

    # --- «Удалить трофей» does not reset the hour ---------------------------------
    h.send("ss_upd;s_status=4;obj=x%s;" % OID1)
    deleted = acks(h.frames())
    h.send("ss_get;target=0;slot=16;")
    listed = [str(o) for o in named(h.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
    check("the hunter deletes the entry: answered 0, the collection is empty",
          (deleted, listed), ([0], []))
    check("  ..and it has left his show with it (the window asks slot=32 again itself)",
          (show(h)[1], [r.get("shown") for r in db_rows(
              "SELECT * FROM trophies WHERE uniq = ?", (T1,))]),
          ([NOBODY] * M, [None]))
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    q = weak_again(q, CRED["quarry"], "quarry")
    check("  ..for the quarry too: the places, all empty", show(q, HP_),
          (["ss_ack"], [NOBODY] * M))
    # This time the quarry is in a clan -- written straight into the
    # database, which the game reads on every look at a clan.
    PACK = "Шакалы"
    pack = with_store(lambda s: s.clan_create(Q, PACK, "шакалы-трофей", "",
                                              (Q,) + tuple(s.money(Q))))
    seen_h, seen_q, cell = kill(h, q, QP)
    rows = db_rows("SELECT * FROM trophies WHERE registered_at IS NULL")
    T3 = rows[0]["uniq"] if rows else 0
    check("a level-zero victim can leave the rarest part, a skull",
          [r["type_id"] for r in rows], [SKULL])
    OID3 = inventory.oid(T3, SKULL, items.TROPHY)
    _o, _inside, took = take_from_bag(h, cell, OID3)
    check("a quarry killed as a member of a clan: the trophy's words keep the clan"
          " (v_clan, «Клан жертвы»)",
          ([r["victim_clan"] for r in rows], di_of(h, OID3)[1].get("v_clan")), ([PACK], PACK))
    with_store(lambda s: s.clan_disband(pack))
    _pos, arrival = goto(h, BUTCHERS)
    eid, _info = butcher(arrival)
    _opened, got = register(h, eid, OID3)
    check("the same pair once more, still inside the hour: the deleted entry kept the"
          " pay mark, so the fee is paid and the skill stays",
          (took, acks(got), [(p["afro"], p["rep"]) for p in mine(got)],
           db_rows("SELECT afro, rep FROM characters WHERE id = ?", (H,))[0]["rep"]),
          ([0], [0], [(START["afro"] - 50 - 200, [1])], 1))
    check("  ..and the chat says why", [("не чаще раза в час" in t) for t in said(got)],
          [True])
    check("  ..a new entry of its own: nothing is joined to a deleted one",
          collection(h), ([0], [OID3]))
    check("  ..and it still names the clan the quarry died in, the clan disbanded since",
          di_of(h, OID3)[1].get("v_clan"), PACK)
    check("  ..kept, and not shown until he puts it on a place",
          show(h)[1], [NOBODY] * M)
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)

    # === somebody else's trophy, by post, and one too dear =========================
    # The hunter has one more ear off the quarry, which he posts to it: a
    # letter's parcel is unpacked under a new serial, and the words follow.
    q.send("resurrect;res_type=0;")
    q.until(lambda f: f[0] == "lcall", 3)
    leave(q)
    leave(h)
    words_h = trophies.record(H, "hunter", 0, Q, "quarry", 0, T0)
    words_q = trophies.record(Q, "quarry", 3, H, "hunter", 20)
    posted = with_store(lambda s: s.create_trophy(H, BAG, EAR, items.TROPHY, words_h))
    dear = with_store(lambda s: s.create_trophy(Q, BAG, HAND, items.TROPHY, words_q))
    # And one more of his own, for the stall carried away from the butchers.
    away = with_store(lambda s: s.create_trophy(H, BAG, EAR, items.TROPHY, words_h))
    h = Client(connect())
    come_back(h, CRED["hunter"])
    q = Client(connect())
    come_back(q, CRED["quarry"])
    h.send("sndml;item=x%s;body=@на память@;type=0;subj=@Ухо@;to=@quarry@;"
           % inventory.oid_of(posted))
    got = h.frames()
    sent = named(got, "ctml")
    check("the hunter posts an ear to the quarry: a trophy changes hands",
          (acks(got), [p["code"][:1] for p in sent]), ([0], [[-1]]))
    letter = str(sent[0]["id"]) if sent else "0"
    q.frames(0.5)
    q.send("uldml;id=x%s;" % letter)
    got = q.frames()
    unpacked = [str(p["item"][0]) for p in named(got, "ctml")]
    check("  ..and the quarry takes it out of the letter, under a new serial",
          (acks(got), len(unpacked), unpacked and unpacked[0] != inventory.oid_of(posted)),
          ([0], 1, True))
    got_oid = unpacked[0] if unpacked else "0"
    stranger = with_store(lambda s: s.item(inventory.parse_oid(got_oid)[0])) or {"uniq": 0}
    name, di4 = di_of(q, got_oid)
    check("  ..its words came with it: the hunter's kill of the quarry",
          (name, {k: di4.get(k) for k in ("k_name", "v_name", "time", "count")}),
          ("ss_di_trophy", dict(k_name="hunter", v_name="quarry", time=trophies.when(T0),
                                count=1)))
    _pos, arrival = goto(q, BUTCHERS)
    eid, _info = butcher(arrival)
    q_before = db_rows("SELECT afro, rep FROM characters WHERE id = ?", (Q,))[0]
    _opened, got = register(q, eid, got_oid)
    check("the hunter's trophy in the quarry's bag is refused: only one's own counts",
          (acks(got), [("только свой" in t) for t in said(got)]),
          ([inventory.RES_UNWORDED], [True]))
    _opened, got = register(q, eid, inventory.oid_of(dear))
    check("its own hand costs 1500 afro, more than it has: refused, and the chat says so"
          " (the window has no word for 21 and only unblocks the trophy)",
          (acks(got), [("1500 афро" in t and "Кисть" in t) for t in said(got)]),
          ([inventory.RES_NO_MONEY], [True]))
    check("  ..and nothing changed: both still its, unregistered; purse and skill",
          ([(with_store(lambda s, u=u: s.item(u)) or {}).get("char_id")
            for u in (stranger["uniq"], dear["uniq"])],
           [(with_store(lambda s, u=u: s.trophy(u)) or {}).get("registered_at")
            for u in (stranger["uniq"], dear["uniq"])],
           db_rows("SELECT afro, rep FROM characters WHERE id = ?", (Q,))[0]),
          ([Q, Q], [None, None], q_before))

    # --- the butchers' stall does not travel ----------------------------------------
    # The trade session outlives the location (leave_room ends the bank, not
    # the stall): opened at the butchers and never closed, it must not
    # register anything once the player stands somewhere else.
    _pos, arrival = goto(h, BUTCHERS)
    eid, _info = butcher(arrival)
    h.send("ss_create;s_type=1;target=%d;" % eid)
    opened = acks(h.frames())
    goto(h, MARKET)
    h_before = db_rows("SELECT afro, rep FROM characters WHERE id = ?", (H,))[0]
    h.send("ss_upd;s_status=6;obj=x%s;" % inventory.oid_of(away))
    got = h.until(lambda f: f[0] == "cmdAck", 3) + h.frames(0.6)
    check("the butchers' stall carried to Нубийский рынок registers nothing: refused,"
          " the chat says where",
          (opened, acks(got), [("Мясник" in t) for t in said(got)],
           named(got, "ss_obj_status")), ([0], [inventory.RES_UNWORDED], [True], []))
    check("  ..the trophy still his, in the bag, unregistered; purse and skill as they were",
          ((with_store(lambda s: s.item(away["uniq"])) or {}).get("slot"),
           (with_store(lambda s: s.trophy(away["uniq"])) or {}).get("registered_at", 0),
           db_rows("SELECT afro, rep FROM characters WHERE id = ?", (H,))[0]),
          (BAG, None, h_before))
    h.send("ss_upd;s_status=0;obj=x0;")
    h.frames(0.3)
    _pos, arrival = goto(h, BUTCHERS)
    eid, _info = butcher(arrival)
    _opened, got = register(h, eid, inventory.oid_of(away))
    check("  ..and back at the butchers it is registered", acks(got), [0])

    # === kill 3: a stronger killer takes nothing ==================================
    leave(h)
    leave(q)

    def level_one(s):
        s.save_stats(H, [("skill", 0, 1, 0, progression.skill_xp_max(1))])
        s.save_character_state(H, level=1)
        s.save_character_state(Q, hp=1, sp=0)
    with_store(level_one)
    h = Client(connect())
    come_back(h, CRED["hunter"])
    q = Client(connect())
    come_back(q, CRED["quarry"])
    n_before = trophy_count()
    seen_h, seen_q, cell = kill(h, q, QP)
    check("the hunter, a level above, kills the quarry", [p for n, p in seen_q
                                                          if n == "lch" and "dead" in p],
          [{"dead": 0}])
    check("  ..and no trophy falls: none written, none on the ground, nothing said",
          (trophy_count(), [r["uniq"] for r in db_rows(
              "SELECT uniq FROM items WHERE char_id = 0 AND root = ?", (items.TROPHY,))],
           [t for t in said(seen_h) if "трофей" in t]), (n_before, [], []))

    # === a mob's kill: none either ================================================
    q.send("resurrect;res_type=0;")
    q.until(lambda f: f[0] == "lcall", 3)
    leave(q)
    with_store(lambda s: s.save_character_state(Q, hp=1, sp=0))
    q = Client(connect())
    come_back(q, CRED["quarry"])
    pos, _got = goto(q, DUMP)
    dump = world.location(DUMP)
    aggro = mobs.stats(82).aggro
    path = [pos]
    while mobs.hex_distance(path[-1], DOG_HOME, dump.width) > aggro - 0.5:
        path.append(min(
            (n for n in progression.hex_neighbours(path[-1], dump.width, dump.height)
             if n not in dump.obstacles and n not in path),
            key=lambda n: mobs.hex_distance(n, DOG_HOME, dump.width)))
    q.send("moveTo;path=|%s|;" % "|".join(str(c) for c in path))
    got = q.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 40)
    check("the quarry is bitten to death by the dump's dog",
          [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    time.sleep(0.5)
    check("  ..and a mob takes no trophy", trophy_count(), n_before)
    leave(q)
    leave(h)
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("trophies OK")
