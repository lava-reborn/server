"""Абри's quests (the owner's «Делаем Абри», 2026-10-12): the rows 450-599 of
data/quests.json, the ways of data/passages.json they take and the rows of
Вади-Хальфа that waited for the town (250-286), held on the real tables.

In process:

  * every row of 450-599 sits in its block of the plan (DESIGN.md 5.0) --
    the mafia 450-469, «Заполучить амазонку» 470-476, the corn 477-484, Багира
    485-490, Хаксли's coupons 491-502, Эльза 503-506 (cut, empty), Камал
    507-512, Ан-Насир 513-517, the lotteries 518-521, the car dump 522-531,
    the smelter 532-539, the assembly shop 540-552 (cut, empty), the golden
    artefact 553-557 (cut, empty), the mines' gates 558-563, «Вода для Мариса
    Дамбиса» 564-579 -- and is on: no row of the block is switched off;
  * the givers and takers of every row of 450-599 and of every live row of
    250-286 stand in a place the map opens (a cell of data/settlements.json,
    or what a door, a side or a quest way leads to from one), and each has a
    name of the original's or a DESIGNED one (not its mobs.xml name);
  * every string id of theirs is in the preload; the texts are the
    original's where data/build_orig_misc.py pins them (VERIFIED), laid over
    the table's; the rows not pinned are exactly the DESIGNED ones, and no
    DESIGNED line says «не ..., а ...»;
  * every thing a row names is an objects.xml object with a name and a
    description of its own (the name is never the internal one: a text id
    taken for a type id would show «qSomething» or nothing), none premium;
    every thing asked for can be had -- something drops it while the quest
    wants it, a stall in the open places sells it, or another row hands it out;
  * no row of 450-599 pays gold (rew_gold); Ведич's part 2 pays back the
    injector in kind, two for one; the coupons and lotteries pay gold things
    no stall buys, each draw worth less than its ticket;
  * the smelter: every machine's output sells at a stall for less than its
    fee alone; the car dump: the tools come back with the find;
  * the ways: each way row has its record in data/passages.json at the
    giver's place, its cells on the grid, walkable, off the exits and off
    anybody's spawn; from every place a way of these rows leads to, doors,
    sides and ways lead back to a place with a cell on the map (no trap);
  * the mines' gates: three ways down at level 8-12, three up at any level;
  * Зубери's map in four parts (256): every part only from bosses that keep
    the boss hours, the map of Донгола out of the choice;
  * the rides: Хассир gives «Поездка в Абри» and «Проездной в Абри», Луиджи
    the two back; the four ways lead between 37 and 187.

On a socket (a server of the suite's own, LAVA_CHEATS):

  * at the station (37) a character of the 8th level takes «Поездка в Абри»
    from Хассир with no afro: the hand-in is refused, nothing moves; with
    100 afro it goes through, the fee is gone and an lcall brings him to the
    Портовый рынок (187), beside Луиджи's car;
  * there «Поездка в Вади Хальфу» costs 400 and brings him back to 37;
  * «Проездной в Абри» takes the ticket 6544 and nothing else.

    LAVA_RES=.../lava/res python3 server/test_abri_quests.py
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_START",
              "LAVA_START_AFRO", "LAVA_BOSS_HOURS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import bosses  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MT = world.mob_types()
ABRI = range(450, 600)
# The plan's blocks (DESIGN.md 5.0); the cut ones stay empty.
BLOCKS = {"mafia": range(450, 470), "amazon": range(470, 477), "corn": range(477, 485),
          "bagira": range(485, 491), "coupons": range(491, 503), "elsa": range(503, 507),
          "kamal": range(507, 513), "an-nasir": range(513, 518), "lottery": range(518, 522),
          "dump": range(522, 532), "smelter": range(532, 540), "assembly": range(540, 553),
          "artefact": range(553, 558), "gates": range(558, 564), "maris": range(564, 580),
          "reserve": range(580, 600)}
CUT = ("elsa", "assembly", "artefact", "reserve")
# What each block holds now.
EXPECT = {"mafia": list(range(450, 468)), "amazon": list(range(470, 476)),
          "corn": [477, 478, 479, 480, 481, 482], "bagira": list(range(485, 490)),
          "coupons": list(range(491, 503)), "kamal": [507], "an-nasir": [513, 514, 515, 516],
          "lottery": [518, 519, 520, 521], "dump": list(range(522, 530)),
          "smelter": list(range(532, 539)), "gates": list(range(558, 564)),
          "maris": list(range(564, 580))}
# Not pinned to the original: their texts are DESIGNED, or the start is ours
# (the lotteries' prize lists without the (P) guns, as Вади-Хальфа's 308/309).
DESIGNED = {518, 519, 520, 521, 558, 559, 560, 561, 562, 563, 579}
# Вади-Хальфа's rows that waited for Абри and are on now.
HALFA_ON = [250, 252, 253, 255, 256, 265, 266, 267, 273, 274, 279, 280]
RIDES = {273: (105, 37, 187), 279: (105, 37, 187), 274: (1179, 187, 37), 280: (1179, 187, 37)}
HASSIR, LUIGI, STATION, PORT_MARKET = 105, 1179, 37, 187
TICKET_TO_ABRI = 6544
SMELTER = range(532, 539)
DUMP = range(522, 530)
GATES_DOWN = {558: (205, 662), 559: (204, 661), 560: (203, 660)}
GATES_UP = {561: (662, 205), 562: (661, 204), 563: (660, 203)}
# Zuberi's four parts and the bosses each falls from (the plan's decision 37).
PARTS = {3888: [313, 314], 3889: [327], 3890: [360, 361], 3891: [328]}
# «не X, а Y»: the construction the owner wants in no Russian line.
NOT_BUT = re.compile(r"(?:^|[\s(«])не\s[^.!?<]*?,\s*а\s", re.I)


def reached_from(start):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way
    (test_halfa_city's rule)."""
    with open(travel.passages_path(), encoding=ENC) as fh:
        sides = json.load(fh).get("sides") or {}
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = [r.get("target_loc_id") for _c, r in travel.quest_ways(world.location(lid))]
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
                targets.append(rec.get("target_loc_id"))
        own = sides.get(str(lid)) if isinstance(sides, dict) else None
        targets += [r.get("target_loc_id") for r in (own or {}).values() if isinstance(r, dict)]
        for t in targets:
            if t and int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    return seen


def on_map(lid):
    """Whether a place is on the map: a cell of its own, or a side of its file
    that leads out onto the map (an interior entered by a way keeps the cell it
    was entered from)."""
    if world.cell_of(lid) is not None:
        return True
    with open(travel.passages_path(), encoding=ENC) as fh:
        inner = (json.load(fh).get("sides") or {}).get(str(lid)) or {}
    return any(s in travel.SIDES and s not in inner
               for s in set(travel.exit_sides(world.location(lid)).values()))


def item_name(t):
    return names.ALL.get(items.STRING_ID_OFFSET + t)


# --- in process: the table -------------------------------------------------------------
try:
    real = quests.QUESTS
    raw = {r["type"]: r for r in quests.table_rows()}
    mine = sorted(t for t in real if t in ABRI)
    check("the rows of 450-599 sit in their blocks of the plan, the cut blocks empty",
          {b: [t for t in mine if t in r] for b, r in BLOCKS.items()},
          dict({b: [] for b in CUT}, **EXPECT))
    check("  ..and every one of them is on (a giver and a taker)",
          [t for t in mine if not (real[t].give and real[t].take)], [])

    # Where the people stand: every place of the map, and what it opens.
    open_places = reached_from(set(world.settlements().values()))
    stands = {}
    for lid in sorted(open_places):
        loc = world.location(lid)
        for _cell, t in loc.spawns:
            stands.setdefault(t, set()).add(lid)
        for t in world.camp_fill(lid):
            stands.setdefault(t, set()).add(lid)
        for rec in world.placed_in(lid):
            stands.setdefault(int(rec["type"]), set()).add(lid)
    live = mine + HALFA_ON
    people = sorted({w for t in live for w in real[t].give + real[t].take})
    check("every giver and taker of the rows stands in a place the map opens",
          [w for w in people if not stands.get(w)], [])
    check("  ..and shows a name of the original's or a DESIGNED one, never its mobs.xml name",
          [w for w in people if not names.known(w) or names.ALL.get(w) == MT[w][1]], [])

    # The strings and the texts.
    check("every string id of the rows is in the preload",
          [(t, sid) for t in mine for sid in real[t].string_ids() if not names.known(sid)], [])
    with open(os.path.join(ROOT, "data", "orig_misc.json"), encoding=ENC) as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts pinned to the original (data/build_orig_misc.py VERIFIED): every row but"
          " the DESIGNED ones (the lotteries' starts, the mines' gates, «Флешка для Хаксли»)",
          sorted(set(mine) - set(pinned)), sorted(DESIGNED))
    orig = orig_texts.quests()
    check("  ..laid over the table's (but what a row keeps as its own, own_texts)",
          [(t, key) for t in mine for k, key in enumerate(quests.TEXT_KEYS)
           if orig.get(t, {}).get(key) and key not in real[t].own_texts
           and real[t].texts[k] != quests.served(real[t], k, orig[t][key])], [])
    designed_lines = [(t, key, raw[t][key]) for t in mine for key in quests.TEXT_KEYS
                      if raw[t].get(key) and (t in DESIGNED or not orig.get(t, {}).get(key)
                                              or key in real[t].own_texts)]
    check("no DESIGNED line says «не ..., а ...»",
          [(t, key) for t, key, line in designed_lines if NOT_BUT.search(line)], [])

    # The things.
    things = sorted({o for t in live for _f, o in real[t].things()})
    cat = items.catalogue()
    check("every thing the rows name is an objects.xml object (quests.check_items)",
          ([o for o in things if o not in cat], quests.check_items()), ([], None))
    check("  ..with a name and a description the client knows, the name never the internal one,"
          " none premium",
          [o for o in things if not names.known(items.STRING_ID_OFFSET + o)
           or not names.known(items.DESC_ID_OFFSET + o)
           or item_name(o) in (None, "", cat[o][1]) or items.premium(o)], [])
    # Whoever stands in the open places and keeps a stall.
    traders = {w for w in stands if MT.get(w) and MT[w][0] == world.TRADER}
    on_sale = {o for w in traders for o in items.stock_for(w)}
    handed = {o for q in real.values() if q.give for o in
              q.rew_obj + [t for t, _n in q.rew_also] + [t for t, _n, _w in q.rew_random]
              + [t for t, _n in q.start_obj]}
    dropped = {o for q in real.values() if q.give for _m, o, _c in q.drops
               if stands.get(_m)}
    asked = sorted({o for t in live for o, _n in real[t].wants()})
    check("every thing a row asks for can be had: dropped while the quest wants it by somebody"
          " standing in the open places, sold at a stall there, or handed out by a row",
          [o for o in asked if o not in on_sale | handed | dropped], [])
    check("  ..Хаксли's coupons, the dump's tools, the splint's gypsum, wire and bandages, the"
          " lottery tickets, the P90 and the injector are sold",
          sorted(o for o in (6294, 6295, 6296, 7025, 7026, 7027, 7028, 7029, 7036, 7037, 7038,
                             7039, 7040, 7041, 7042, 5740, 5741, 5742, 2646, 2647, 2649, 2650,
                             25485, 6075, 6050) if o not in on_sale), [])

    # Gold.
    check("no row of 450-599 pays gold (rew_gold), and none hands out an ingot",
          ([t for t in mine if real[t].rew_gold],
           [t for t in mine for _f, o in real[t].things() if o in items.GOLD_INGOTS]), ([], []))
    check("Ведич's part 2 pays the injector back in kind, two for the one bought",
          (real[471].wants(), list(zip(real[471].rew_obj, real[471].num_rew_obj))),
          ([(6075, 1)], [(6075, 2)]))

    def gold_worth(obj, num):
        return inventory.buy_price(items.params_of(obj), items.root_of(obj), num, True)

    def afro_worth(obj, num):
        return inventory.buy_price(items.params_of(obj), items.root_of(obj), num)

    def ticket(t):
        o = real[t].objs[0][0]
        si = items.params_of(o)
        return gold_worth(o, 1) if si.get("g_cost") else afro_worth(o, 1)

    lottery = {t: (ticket(t), max((gold_worth if items.params_of(o).get("g_cost") else afro_worth)
                                  (o, n) for o, n, _w in real[t].rew_random))
               for t in (518, 519, 520, 521)}
    check("the lotteries: every prize worth less than the ticket (the house wins), the gold"
          " ones' prizes gold things",
          ({t: prize < price for t, (price, prize) in lottery.items()},
           [o for t in (520, 521) for o, _n, _w in real[t].rew_random
            if not items.params_of(o).get("g_cost")]),
          ({518: True, 519: True, 520: True, 521: True}, []))
    check("  ..at the tickets' prices: 1000 and 1700 afro, 2 and 2,5 G",
          {t: price for t, (price, _p) in lottery.items()},
          {518: 1000, 519: 1700, 520: 200, 521: 250})
    check("the coupons: a coupon of 20, 300 or 5000 for as many rounds of one of the twelve"
          " calibres -- the prison's (Q) ОТ, or the gold ЭК, ББ, СБ -- a service each",
          {t: (real[t].wants(), len(real[t].rew_obj), sorted(set(real[t].num_rew_obj)),
               real[t].rew_obj[0], real[t].service) for t in range(491, 503)},
          {491 + 4 * i + j: ([(coupon, 1)], 12, [count], first, True)
           for i, (coupon, count) in enumerate(((6294, 20), (6295, 300), (6296, 5000)))
           for j, first in enumerate((6140, 6152, 6164, 6176))})

    # The smelter and the car dump.
    def sells_for(obj, num):
        si = items.params_of(obj) or {}
        if si.get("cost", 0) <= 0 or si.get("quest"):
            return 0
        return int(si["cost"] / float(si.get("sell_num", 1)) * num * inventory.SMOD
                   * si.get("sell_mod", 1))

    check("the smelter: what every machine makes sells at a stall for less than its fee alone",
          [t for t in SMELTER
           if max(sells_for(o, n) for o, n in zip(real[t].rew_obj, real[t].num_rew_obj))
           >= real[t].cost_afro], [])
    check("  ..every machine takes 100 afro and pays +40 Переработка (recycling)",
          {t: (real[t].cost_afro, real[t].rew_spec_xp) for t in SMELTER},
          {t: (100, [(quests.SPEC_KEYS["recycling"], 40)]) for t in SMELTER})
    check("the car dump: the tools a search shows come back with its find",
          [t for t in DUMP if sorted(o for o, _n in real[t].wants())
           != sorted(o for o, _n in real[t].rew_also) or len(real[t].rew_obj) != 1], [])

    # The ways.
    ways = {}
    for t in live:
        if real[t].rew_loc:
            for lid in sorted({p for w in real[t].give for p in stands.get(w, ())}):
                rec = travel.quest_way(world.location(lid), t)
                if rec:
                    ways[t] = (lid, int(rec["target_loc_id"]))
    check("every way row has its record at the giver's place in data/passages.json",
          sorted(t for t in live if real[t].rew_loc and t not in ways), [])
    bad_cells = []
    for t, (lid, _to) in sorted(ways.items()):
        loc = world.location(lid)
        cells, _rec = next((c, r) for c, r in travel.quest_ways(loc) if int(r["quest"]) == t)
        taken = {c for c, _t in loc.spawns}
        zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                       "zones", 4)}
        for c in cells:
            if c in loc.obstacles or c in travel.exit_sides(loc) or c in taken \
                    or c in zones or c in loc.entries:
                bad_cells.append((t, lid, c % loc.width, c // loc.width))
    check("  ..its cells on the grid, walkable, off the exits, where no window opens, nobody"
          " arrives and nobody stands (test_halfa_training's rule)", bad_cells, [])
    check("  ..given and taken by one inhabitant, as every way (server/test_mine)",
          [t for t in ways if real[t].give != real[t].take], [])
    traps = sorted({to for _t, (_lid, to) in ways.items()
                    if not any(on_map(p) for p in reached_from({to}))})
    check("  ..and from every place a way leads to, doors, sides and ways lead back to the map"
          " (no trap)", traps, [])
    check("the rides: Хассир gives the two to Абри, Луиджи the two back, each a way between"
          " the station 37 and the port market 187",
          {t: (real[t].give, ways.get(t)) for t in RIDES},
          {t: ([d], (frm, to)) for t, (d, frm, to) in RIDES.items()})
    check("  ..the fares the texts name, 100 and 400 afro, and the tickets 6544 and 6545",
          [(real[t].cost_afro, [o for o, _n in real[t].wants()]) for t in (273, 274, 279, 280)],
          [(100, []), (400, []), (0, [6544]), (0, [6545])])
    check("the mines' gates: down at levels 8-12 from the surface to the control room, up at"
          " any level back",
          ({t: (real[t].level, real[t].max_level, ways.get(t)) for t in GATES_DOWN},
           {t: (real[t].level, real[t].max_level, ways.get(t)) for t in GATES_UP}),
          ({t: (8, 12, v) for t, v in GATES_DOWN.items()},
           {t: (0, None, v) for t, v in GATES_UP.items()}))

    # Зубери's map in four parts.
    check("Зубери's map in four parts (256): each part only from bosses that keep the boss"
          " hours; the choice four maps, the one of Донгола out",
          ({o: sorted(ms) for o, _n, ms in real[256].objs},
           all(bosses.keeps_hours(m) for ms in PARTS.values() for m in ms),
           sorted({o for _m, o, _c in real[256].drops}), real[256].rew_obj),
          (PARTS, True, sorted(PARTS), [3892, 3893, 3894, 3906]))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "abri_quests.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("rider", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_START_AFRO="0", LAVA_SEED="11",
           LAVA_POLICY_PORT="0")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


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

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def inhabitants(frames):
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(1.5)


def goto(c, where):
    c.send("userMsg;entry=@/goto %d@;group=0;" % where)
    c.until(lambda f: f[0] == "lcall")
    return inhabitants(arrive(c))


def store():
    return accounts.Store(DB)


def char_id(name):
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def purse(name):
    st = store()
    got = tuple(st.money(char_id(name)))
    st.close()
    return got


def owned(name):
    st = store()
    out = {}
    for r in st.items_of(char_id(name)):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def login(first=False):
    c = Client(testkit.connect(PORT, srv, LOG))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential("rider", "secret"))
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@Rider@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    return c


def take(c, here, npc_type, qtype):
    c.send("q_st;mob=%d;q_idx=%d;" % (here[npc_type][0], quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[npc_type][0], q_id))
    return c.frames(1.0)


def ride(c, got):
    """The lcall a way's hand-in brings, and where the player stands after it."""
    call = named(got, "lcall") or named(c.until(lambda f: f[0] == "lcall", 6), "lcall")
    if not call:
        return None, None, {}
    arrival = arrive(c)
    pos = named(arrival, "lenter")
    return call[0].get("id"), (pos[0].get("pos") if pos else None), inhabitants(arrival)


try:
    c = login(first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.3)
    st = store()
    cid = char_id("Rider")
    st.save_stats(cid, [("skill", progression.SHOOTING, 8, 0, progression.skill_xp_max(8))])
    st.save_character_state(cid, level=8)
    st.close()
    c = login()

    # --- to Абри for the fare
    here = goto(c, STATION)
    check("Хассир stands at the station", HASSIR in here, True)
    took, q_id = take(c, here, HASSIR, 273)
    refused = hand_in(c, here, HASSIR, q_id)
    check("«Поездка в Абри» with no afro: taken, and the hand-in refused -- nobody moves",
          (acks(took), acks(refused)[:1] != [0], bool(named(refused, "lcall"))),
          ([0], True, False))
    c.send("userMsg;entry=@/money 100 0@;group=0;")
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)
    went = hand_in(c, here, HASSIR, q_id)
    lid, pos, there = ride(c, went)
    port = world.location(PORT_MARKET)
    luigi_cells = {y * port.width + x for x, y in
                   travel.quest_way(port, 274)["cells"]}
    check("  ..with 100 afro: handed in, the fare gone, and an lcall to the Портовый рынок of"
          " Абри, where Луиджи stands",
          (acks(went)[:1], purse("Rider")[0], lid, LUIGI in there), ([0], 0, PORT_MARKET, True))
    check("  ..arrived beside the way back (travel.door_arrival on 274's cells)",
          pos == travel.door_arrival(port, STATION) if pos is not None else None, True)

    # --- back for the fare
    c.send("userMsg;entry=@/money 400 0@;group=0;")
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)
    took, q_id = take(c, there, LUIGI, 274)
    back = hand_in(c, there, LUIGI, q_id)
    lid, _pos, here = ride(c, back)
    check("«Поездка в Вади Хальфу» at Луиджи's: 400 afro, and back at the station",
          (acks(took), acks(back)[:1], purse("Rider")[0], lid, HASSIR in here),
          ([0], [0], 0, STATION, True))

    # --- to Абри by the ticket
    c.send("userMsg;entry=@/give %d 1@;group=0;" % TICKET_TO_ABRI)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)
    took, q_id = take(c, here, HASSIR, 279)
    went = hand_in(c, here, HASSIR, q_id)
    lid, _pos, there = ride(c, went)
    check("«Проездной в Абри»: the ticket 6544 taken, no afro, and on to the Портовый рынок",
          (acks(took), acks(went)[:1], owned("Rider").get(TICKET_TO_ABRI, 0),
           purse("Rider")[0], lid), ([0], [0], 0, 0, PORT_MARKET))
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    with open(LOG, encoding=ENC) as fh:
        text = fh.read()
    check("the server's log has no Traceback", "Traceback" in text, False)
except Exception:
    import traceback
    fails.append("the socket run broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print("  - " + f)
    print("server log: %s" % LOG)
    sys.exit(1)
print("\nall ok")
