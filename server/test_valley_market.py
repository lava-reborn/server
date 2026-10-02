"""The Nubian valley's market, farm and mine, the third batch of its quests
(the owner's «давай готовь квесты все», 2026-09-26), walked on a socket on
the real data/quests.json: twenty-two quests, types 46-67.

  Муад      «Лучшее снаряжение» (to Сет at the arena, +5 Стрельба); «Попутный
            ветер» (to Фая in the caravan, +5); «Точильный камень» (the
            grindstone off the colonists, 50 afro); «Клык за Клык» (ten dog
            fangs, 150); «Раненый сын» (medicaments, 200)
  Сорванец  «Спички детям» (five boxes of matches, 300 afro, once a day)
  Гофус     «Сгоревшая микросхема» (an old chip: Салюс МК I or Анестетик МК
            I, the player's choice, once a day)
  Крысолов  «Крысиный переполох» (to Фермер Хрущ at his barn); «Крысиные
            хвосты» (twenty tails, 300 afro, once a day)
  Хрущ      «Крысиный король» (the rat king, 200 afro, once a day);
            «Королевский Элексир» (a rat king to Эддай in Вади-Хальфа, 500)
  Шульц     «Старые штольни» (to Рудо, whose way down comes after it);
            «Экипировка к пистолету» (Большой Мвамба in his camp at the boss
            hour, a party's quest: +200 Стрельба)
  Камал     «Изумруды» (five emeralds of the mine: +100 Стрельба)
  Хасани    Сабир's «Любимая антилопа» (to the dead antelope, and its meat
            carried back), «Еда» (three pieces of meat, once a day), «Охота
            на антилоп» (ten fillets); the map flags «Где антилопы?», «Где
            мастер Норман?», «Где Сейфул?», «Где доктор Корбен?»

Each group is held to its take (one ack, then the journal; the meat into the
bag first), its progress (the kill, the bag, the journal told), its hand-in
(what the quest asked for out of the bag, the reward in: the thing chosen,
the experience, the money, the day's count for a daily one, all before the
ack) and the chain it opens. A quest of once a day is not offered again the
same day, and is again once its hand-in is a day old.

In process: the rows, their texts laid over from the original
(data/orig_misc.json, data/build_orig_misc.py VERIFIED, the newest edition),
every string id in the launcher's table, every giver and taker standing
where the quest sends the player as an inhabitant the client opens quests
for -- Эддай (6763) by the quarter's own file, under the original's row --
every creature a quest asks to kill or rob standing where it lives and
carrying what is asked for it, Мвамба's camp on the map, the old chip by
the original's name.

    LAVA_RES=.../lava/res python3 server/test_valley_market.py
"""
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


# The quests, by type.
(GEAR, WIND, STONE, FANGS, SON, MATCHES_Q, CHIP_Q, RAT_RIOT, TAILS, KING_Q, ELIXIR,
 ADITS, PISTOL_KIT, EMERALDS_Q, ANTELOPE1, ANTELOPE2, FOOD, HUNT_Q, WHERE_ANT, WHERE_NORMAN,
 WHERE_SEIFUL, WHERE_CORBEN) = range(46, 68)
MARKET_Q = list(range(46, 68))
DAILY = [MATCHES_Q, CHIP_Q, TAILS, KING_Q, FOOD]
ONE_OFF = [t for t in MARKET_Q if t not in DAILY]
MINE_DOWN = 7                       # Рудо's way down, after «Старые штольни»
# Who gives and takes them.
MUAD, SET, FAYA, SORVANETS, GOFUS = 5186, 1187, 5198, 5189, 5215
RATCATCHER, KHRUSCH, EDDAI, SCHULZ, RUDO, KAMAL = 5194, 5234, 6763, 5221, 1133, 1134
HASANI, CARCASS, NORMAN, SEIFUL, CORBEN = 5217, 38, 5196, 35, 5233
# The creatures.
DOG, GREY_RAT, BLACK_RAT, ANTELOPE, SHOOTER, STORMER = 82, 1023, 1019, 12, 250, 251
MARAUDER1, MARAUDER2, MVAMBA = 836, 837, 1406
# The things.
GRINDSTONE, FANG, MEDS, MATCHES, CHIP, TAIL, KING = 3217, 217, 232, 6915, 3179, 3216, 3218
EMERALD, MEAT, FILLET, SALUS, ANESTHETIC = 3159, 260, 3059, 4918, 4938
# The places.
MARKET, VILLAGE, BARN, ADITS_LOC, ARENA, MOUTH, TIER1 = 185, 186, 166, 643, 167, 153, 612
NORTH, ANTELOPES, BURIALS, TRUCK, SQUAD, SCOUT_LOC = 181, 25, 184, 26, 29, 33
CAMP_M, QUARTER = 31, 36
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
MEDICINE, SHOOTING = progression.MEDICINE, progression.SHOOTING
TASK_LABEL = re.compile(r"№\s*0000")      # the 2012 edition's «№0000720» labels

GIVE_TAKE = {GEAR: (MUAD, SET), WIND: (MUAD, FAYA), STONE: (MUAD, MUAD),
             FANGS: (MUAD, MUAD), SON: (MUAD, MUAD), MATCHES_Q: (SORVANETS, SORVANETS),
             CHIP_Q: (GOFUS, GOFUS), RAT_RIOT: (RATCATCHER, KHRUSCH),
             TAILS: (RATCATCHER, RATCATCHER), KING_Q: (KHRUSCH, KHRUSCH),
             ELIXIR: (KHRUSCH, EDDAI), ADITS: (SCHULZ, RUDO), PISTOL_KIT: (SCHULZ, SCHULZ),
             EMERALDS_Q: (KAMAL, KAMAL), ANTELOPE1: (HASANI, CARCASS),
             ANTELOPE2: (CARCASS, HASANI), FOOD: (HASANI, HASANI), HUNT_Q: (HASANI, HASANI),
             WHERE_ANT: (HASANI, CARCASS), WHERE_NORMAN: (HASANI, NORMAN),
             WHERE_SEIFUL: (HASANI, SEIFUL), WHERE_CORBEN: (HASANI, CORBEN)}
CHAIN = {GEAR: [], WIND: [GEAR], STONE: [GEAR], FANGS: [GEAR], SON: [GEAR], MATCHES_Q: [],
         CHIP_Q: [], RAT_RIOT: [], TAILS: [], KING_Q: [RAT_RIOT], ELIXIR: [KING_Q], ADITS: [],
         PISTOL_KIT: [], EMERALDS_Q: [], ANTELOPE1: [], ANTELOPE2: [ANTELOPE1],
         FOOD: [ANTELOPE2], HUNT_Q: [ANTELOPE2], WHERE_ANT: [ANTELOPE2], WHERE_NORMAN: [30],
         WHERE_SEIFUL: [33], WHERE_CORBEN: [35]}
# Where each giver and taker stands (Фая in the caravan and on the market).
WHERE = {MUAD: {MARKET}, SET: {ARENA}, FAYA: {MARKET, VILLAGE}, SORVANETS: {MARKET},
         GOFUS: {MARKET}, RATCATCHER: {VILLAGE}, KHRUSCH: {BARN}, EDDAI: {QUARTER},
         SCHULZ: {VILLAGE}, RUDO: {MOUTH}, KAMAL: {TIER1}, HASANI: {NORTH},
         CARCASS: {ANTELOPES}, NORMAN: {TRUCK}, SEIFUL: {SQUAD}, CORBEN: {SCOUT_LOC}}
MED20 = {"medicine": 20}
# What each quest pays: [(thing, pieces)] to choose from, afro, experience.
PAYS = {GEAR: ([], 0, {"shooting": 5}), WIND: ([], 0, {"shooting": 5}),
        STONE: ([], 50, {}), FANGS: ([], 150, {}), SON: ([], 200, {}),
        MATCHES_Q: ([], 300, {}), CHIP_Q: ([(SALUS, 1), (ANESTHETIC, 1)], 0, {}),
        RAT_RIOT: ([], 0, MED20), TAILS: ([], 300, {}), KING_Q: ([], 200, {}),
        ELIXIR: ([], 500, {}), ADITS: ([], 0, MED20), PISTOL_KIT: ([], 0, {"shooting": 200}),
        EMERALDS_Q: ([], 0, {"shooting": 100}), ANTELOPE1: ([], 0, MED20),
        ANTELOPE2: ([], 0, MED20), FOOD: ([], 100, {}), HUNT_Q: ([], 150, {"shooting": 30}),
        WHERE_ANT: ([], 0, {}), WHERE_NORMAN: ([], 0, {}), WHERE_SEIFUL: ([], 0, {}),
        WHERE_CORBEN: ([], 0, {})}
# What the quests that ask for things ask for, and who carries it: "quest"
# a «Квестовый» row of data/loot_manual.json (only while the quest wants it),
# "animal" what the animal always has on it or at even odds
# (mobs.ANIMAL_LOOT), "loot" an ordinary row of its table.
BRINGS = {STONE: (GRINDSTONE, 1, [SHOOTER, STORMER], "quest"),
          FANGS: (FANG, 10, [DOG], "animal"),
          SON: (MEDS, 1, [SHOOTER, STORMER], "quest"),
          MATCHES_Q: (MATCHES, 5, [SHOOTER, STORMER], "quest"),
          CHIP_Q: (CHIP, 1, [SHOOTER, STORMER], "quest"),
          TAILS: (TAIL, 20, [GREY_RAT, BLACK_RAT], "animal"),
          KING_Q: (KING, 1, [BLACK_RAT], "quest"),
          ELIXIR: (KING, 1, [BLACK_RAT], "quest"),
          EMERALDS_Q: (EMERALD, 5, [MARAUDER1, MARAUDER2], "loot"),
          FOOD: (MEAT, 3, [ANTELOPE], "quest"),
          HUNT_Q: (FILLET, 10, [ANTELOPE], "quest")}
# Where the carriers stand, of the places the quests send the player to
# (the grey rats in the barn and on the burial ground both).
HOMES = {SHOOTER: {SCOUT_LOC}, STORMER: {SCOUT_LOC}, DOG: {BURIALS},
         GREY_RAT: {BARN, BURIALS}, BLACK_RAT: {ADITS_LOC}, MARAUDER1: {TIER1},
         MARAUDER2: {TIER1}, ANTELOPE: {ANTELOPES}, MVAMBA: {CAMP_M}}


def pack(gx, gy):
    return (gx << 13) | gy


# --- in process: the table ------------------------------------------------------------
MT = world.mob_types()
try:
    rows = [quests.get(t) for t in MARKET_Q]
    check("the twenty-two quests of the valley's market, farm and mine are in the table",
          [q is not None for q in rows], [True] * 22)
    check("  ..repeatable only where the original says «не чаще 1 раза в сутки», and then"
          " once a day (per_day); none of them a way",
          ([t for t in MARKET_Q if quests.get(t).repeatable],
           [t for t in MARKET_Q if quests.get(t).per_day == 1],
           [t for t in MARKET_Q if travel.is_quest_way(t) or quests.get(t).rew_loc]),
          (DAILY, DAILY, []))
    check("  ..given and taken by the NPCs the texts and the wiki name, or their stand-ins",
          {q.type: (q.give, q.take) for q in rows},
          {t: ([g], [k]) for t, (g, k) in GIVE_TAKE.items()})
    check("  ..in the chain the original draws, and as each row's why designs",
          {q.type: q.need_all + q.need_any for q in rows}, CHAIN)
    check("  ..Рудо's way down after Шульц's «Старые штольни», or for a veteran of the"
          " mine after Камал's «Золотоискатель» (test_mine)",
          (quests.get(MINE_DOWN).need_all, quests.get(MINE_DOWN).need_any), ([], [ADITS, 9]))
    check("  ..paying what the original pays, or what each row's why designs",
          {q.type: (list(zip(q.rew_obj, q.num_rew_obj)), q.rew_afro,
                    {key: xp for key, idx in quests.SKILL_KEYS.items()
                     for skill, xp in q.rew_xp if skill == idx})
           for q in rows}, PAYS)
    check("  ..no gold, nothing beside the reward, no level, no cap; one party quest",
          ([t for t in MARKET_Q if quests.get(t).rew_gold or quests.get(t).rew_also
            or quests.get(t).level or quests.get(t).max_level is not None],
           {t: quests.get(t).party_size for t in MARKET_Q if quests.get(t).party_size}),
          ([], {PISTOL_KIT: 3}))
    check("  ..appended: Камал's way out and gold sand keep their q_idx 0 and 1",
          (quests.given_by(KAMAL), quests.given_by(RUDO), quests.taken_by(RUDO)),
          ([8, 9, EMERALDS_Q], [MINE_DOWN], [MINE_DOWN, ADITS]))
    check("the things to bring, how many, and who carries them",
          {t: (q.objs[0][0], q.objs[0][1], q.objs[0][2]) for t, q in
           ((t, quests.get(t)) for t in MARKET_Q) if q.kind == quests.BRING_L_OBJ},
          {t: (o, n, ms) for t, (o, n, ms, _how) in BRINGS.items()})
    check("the kill: Большой Мвамба, once", (quests.get(PISTOL_KIT).mobs_kill,
                                            quests.get(PISTOL_KIT).num_kill), ([MVAMBA], [1]))
    check("the meat is handed over by the dead antelope at the take, delivered, and kept"
          " at a death", (quests.get(ANTELOPE2).start_obj, quests.get(ANTELOPE2).obj,
                          combat.drops_on_death(MEAT)), ([(MEAT, 1)], MEAT, False))
    check("  ..and never thrown on the ground: «Еда» asks for the same meat",
          ([o for o, _n in quests.get(FOOD).wants()], quests.not_on_ground(MEAT)),
          ([MEAT], True))
    orig = orig_texts.quests()
    with open(os.path.join(os.path.dirname(HERE), "data", "orig_misc.json"),
              encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts are the original's (data/orig_misc.json)",
          [t for t in MARKET_Q if t not in pinned], [])
    check("  ..laid over the table's",
          [t for t in MARKET_Q for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and quests.get(t).texts[k] != quests.served(quests.get(t), k, orig[t][key])], [])
    check("  ..the newest edition: no line carries the 2012 number label",
          [t for t in MARKET_Q if any(TASK_LABEL.search(x) for x in quests.get(t).texts)], [])
    check("  ..«Еда»'s start and notfinish told apart by their task lines",
          pinned.get(FOOD), [59874, 59875, 59877, 59878])
    check("  ..and the two with no name line of their own named by the thing's",
          [(pinned.get(t, [None])[0], quests.get(t).name) for t in (STONE, KING_Q)],
          [(6342, "Точильный камень"), (6344, "Крысиный король")])
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has, and what they hand over is worth"
          " nothing away from them", quests.check_items(), None)
    try:
        quests.Quest(dict(type=90001, kind="del_obj", name="x", per_day=1))
        once_a_day_one_off = "accepted"
    except ValueError:
        once_a_day_one_off = "refused"
    check("a one-off quest with per_day is refused: only a repeatable one has a next day",
          once_a_day_one_off, "refused")
    check("  ..and per_day is spent by as many hand-ins since the day's reset",
          [quests.get(TAILS).done_for_today(n) for n in (0, 1, 2)]
          + [quests.get(RAT_RIOT).done_for_today(5)], [False, True, True, False])

    # Where everybody stands: every class but a mob's has the quest tab
    # (NPCService.openService), Эддай by the quarter's own file.
    stand = {}
    for lid in sorted({lid for v in list(WHERE.values()) + list(HOMES.values()) for lid in v}):
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            stand.setdefault(n.type_id, set()).add((lid, n.root))
    check("each giver and taker stands where the quests send the player, not a mob",
          {npc: {lid for lid, root in stand.get(npc, ()) if root != world.MOB}
           for npc in WHERE}, WHERE)
    check("  ..Эддай by the quarter's own file, under the original's row 10351; no stand-in by hand",
          ([t for _c, t in world.location(QUARTER).spawns if t == EDDAI],
           [r.get("type") for r in world.placed_in(QUARTER) if r.get("type") in (EDDAI, 421)],
           names.ALL.get(EDDAI)), ([EDDAI], [], "Эддай<br>Местный житель"))
    check("each creature stands, a mob, where it lives",
          {m: {lid for lid, root in stand.get(m, ()) if root == world.MOB}
           for m in HOMES}, HOMES)
    carried = {}
    for t, (obj, _n, ms, how) in BRINGS.items():
        for m in ms:
            if how == "quest":
                ok = obj in dict(mobs.quest_table(m))
            elif how == "animal":
                ok = obj in mobs.animal_parts(mobs.stats(m))
            else:
                ok = obj in [r[0] for r in mobs.loot_table(m)]
            carried.setdefault(t, []).append(ok)
    check("  ..and carries the thing asked for it: a quest's row, an animal's part, loot",
          carried, {t: [True] * len(ms) for t, (_o, _n, ms, _h) in BRINGS.items()})
    rng = random.Random(0)
    got = [mobs.quest_roll(SHOOTER, {CHIP}, rng) for _ in range(400)]
    check("  ..the old chip off a colonist only for a quest that wants it, about one in four",
          (mobs.quest_roll(SHOOTER, set(), random.Random(0)),
           80 <= sum(1 for g in got if (CHIP, 1) in g) <= 120), ([], True))
    check("  ..the antelope's meat certain for a quest that wants it, the fillet one in two",
          ([mobs.quest_roll(ANTELOPE, {MEAT}, random.Random(s)) for s in range(3)],
           dict(mobs.quest_table(ANTELOPE))), ([[(MEAT, 1)]] * 3, {MEAT: 1.0, FILLET: 0.5}))
    def mark(lid):
        cell = world.cell_of(lid) if lid else None
        return pack(*cell) if cell else None
    # The taker's place for the hand-in's flag (Фая's in the caravan, where
    # the wiki ends «Попутный ветер»; none for Камал down the mine), and the
    # place the quest sends the player to, if it sends him anywhere.
    TAKER_AT = {SET: ARENA, FAYA: VILLAGE, MUAD: MARKET, SORVANETS: MARKET, GOFUS: MARKET,
                KHRUSCH: BARN, RATCATCHER: VILLAGE, EDDAI: QUARTER, RUDO: MOUTH,
                SCHULZ: VILLAGE, KAMAL: None, CARCASS: ANTELOPES, HASANI: NORTH,
                NORMAN: TRUCK, SEIFUL: SQUAD, CORBEN: SCOUT_LOC}
    SENT_TO = {STONE: SCOUT_LOC, FANGS: BURIALS, SON: SCOUT_LOC, MATCHES_Q: SCOUT_LOC,
               CHIP_Q: SCOUT_LOC, TAILS: BARN, KING_Q: BARN, ELIXIR: BARN, PISTOL_KIT: CAMP_M,
               ANTELOPE1: ANTELOPES, FOOD: ANTELOPES, HUNT_Q: ANTELOPES, WHERE_ANT: ANTELOPES,
               WHERE_NORMAN: TRUCK, WHERE_SEIFUL: SQUAD, WHERE_CORBEN: SCOUT_LOC}
    check("each hand-in's flag is the taker's place (none down the mine)",
          {t: quests.get(t).finish_loc for t in MARKET_Q},
          {t: mark(TAKER_AT[GIVE_TAKE[t][1]]) or -1 for t in MARKET_Q})
    check("  ..and the place the quest sends the player to has its flag",
          {t: quests.get(t).loc for t in MARKET_Q},
          {t: mark(SENT_TO.get(t)) or 0 for t in MARKET_Q})
    check("Большой Мвамба: his camp on the map, a boss of the fifth level, by the"
          " original's name",
          (world.cell_of(CAMP_M), world.settlements().get((6274, 1833)),
           world.creature_role(MVAMBA), mobs.stats(MVAMBA).level, names.ALL.get(MVAMBA)),
          ((6274, 1833), CAMP_M, "boss", 5, "[5] Большой Мвамба<br>Новые колонисты"))
    # His guards (data/placements.json, the owner's of 2026-10-02): three
    # thugs in his own art, two hexes round him, on the ordinary respawn.
    _camp = rooms.Room(world.location(CAMP_M), rooms.IdAllocator(), MT)
    _home = next(n.cell for n in _camp.npcs.values() if n.type_id == MVAMBA)
    _guards = [n for n in _camp.npcs.values() if n.type_id != MVAMBA]
    _art = MT
    check("  ..and three guards round him: «[4] Головорез», his art, two hexes off,"
          " not at the boss hours",
          sorted((names.ALL.get(n.type_id), _art[n.type_id][2], mobs.stats(n.type_id).level,
                  round(mobs.hex_distance(n.cell, _home, world.location(CAMP_M).width)),
                  world.creature_role(n.type_id)) for n in _guards),
          [("[4] Головорез", _art[MVAMBA][2], 4, 2, "mob")] * 3)
    check("the old chip by the original's name and description, and in its frame",
          (names.ALL.get(items.STRING_ID_OFFSET + CHIP), names.ALL.get(items.DESC_ID_OFFSET + CHIP),
           items.static_info(CHIP)[1].get("desc")),
          ("Старая микросхема", "Пыльная микросхема, извлеченная из неизвестного устройства.",
           items.DESC_ID_OFFSET + CHIP))
    check("the rewards are things of the game: the two preparations of Гофус",
          [(items.root_of(t), names.ALL.get(items.STRING_ID_OFFSET + t)) for t in (SALUS, ANESTHETIC)],
          [(items.HEAL, "Салюс МК I"), (items.HEAL, "Анестетик МК I")])
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "valley_market.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("hunter", "secret")
_store.close()
CRED = accounts.credential("hunter", "secret")

# Five seconds past six on the Moscow clock: Большой Мвамба is in his camp
# for the hour, and he is the test's first errand.
CLOCK = datetime(2026, 9, 24, 18, 0, 5)
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="6268", LAVA_GY="1819", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="30", LAVA_SEED="5", LAVA_BOSS_CLOCK=CLOCK.isoformat())
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.seen = []

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
        out = [decode(f.decode(ENC)) for f in parts if f]
        self.seen += out
        return out

    def frames(self, wait=0.5):
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


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def order(frames):
    return [n for n, _p in frames]


def upto_ack(frames):
    seq = order(frames)
    return seq[:seq.index("cmdAck") + 1] if "cmdAck" in seq else seq


def no_level(seq):
    """A frame order with a level-up's usrUp left out: whether a skill
    crosses a level at a hand-in depends on what the kills paid for it."""
    return [n for n in seq if n != "usrUp"]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(target_id):
    return "x1%08x" % target_id


def inhabitants(frames):
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, loc_id):
    """/goto a location: the arrival's frames."""
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def ints(v):
    """A list field as the decoder leaves it -- a list, one value, or none."""
    if v in (None, "", []):
        return []
    return [int(x) for x in (v if isinstance(v, list) else [v])]


def quest_lists(c, here, npc_type):
    """(give_quests, take_quests) of the first inhabitant of a type here, as
    its getInfo answer lists them: the client indexes q_st by the first."""
    c.send("getInfo;lvl=0;id=%d;type=0;" % here.get(npc_type, [0])[0])
    got = [p for n, p in c.until(lambda f: f[0].startswith("userInfo_"), 2)
           if n.startswith("userInfo_") and p.get("name") == npc_type]
    return (ints(got[0].get("give_quests")), ints(got[0].get("take_quests"))) if got else None


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, here, qtype):
    """q_st of a type from the first NPC of its giver's type here."""
    npc_type = GIVE_TAKE[qtype][0]
    npc = here.get(npc_type, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, qtype, q_id, obj_idx=0, wait=0.9):
    npc = here.get(GIVE_TAKE[qtype][1], [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = 'Hunter'").fetchone()
    st.close()
    return row["id"]


def owned(cid, slot=inventory.BAG):
    """type id -> pieces of it in the bag."""
    st = store()
    out = {}
    for r in st.items_of(cid):
        if r["slot"] == slot:
            n = r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
            out[r["type_id"]] = out.get(r["type_id"], 0) + n
    st.close()
    return out


def unpacked(mask, values):
    """index -> value of a packed group (progression.packed)."""
    out, it = {}, iter(values)
    for i in range(32):
        if mask & (1 << i):
            out[i] = next(it)
    return out


def skill_seen(c, skill):
    """All the experience a skill has had, as the client was last told of it
    (every rp_info seen, the kills' and the quests' alike)."""
    level = xp = 0
    for n, p in c.seen:
        if n != "rp_info":
            continue
        level = unpacked(p["a_skills_mask"], p["a_skills"]).get(skill, level)
        xp = unpacked(p["xp_skills_mask"], p["xp_skills"]).get(skill, xp)
    return sum(progression.skill_xp_max(lvl) for lvl in range(level)) + xp


def done(cid):
    st = store()
    got = sorted(r["type"] for r in st.db.execute(
        "SELECT type FROM char_quests_done WHERE char_id = ?", (cid,)).fetchall())
    st.close()
    return got


def new_things(frames):
    """The type ids of what came into the bag (ss_obj_status 1), in order."""
    out = []
    for p in named(frames, "ss_obj_status"):
        oid = inventory.parse_oid(str(p["obj"]).lstrip("x"))
        if p.get("status") == 1 and oid:
            out.append(oid[1])
    return out


def gone_things(frames):
    """How many things left the bag (ss_obj_status 0)."""
    return len([p for p in named(frames, "ss_obj_status") if p.get("status") == 0])


def purse(frames):
    got = named(frames, "userInfo_Player")
    return got[-1].get("afro") if got else None


def counts(frames, kind):
    key = "kill_num" if kind == quests.KILL_MOBS else "obj_num"
    return [(p[key], p["complete"]) for p in named(frames, "q_di_" + kind)]


def positions(frames):
    """entity id -> cell of every inhabitant the frames bring in (lch
    newUser), moved on by the userMove frames among them."""
    where = {}
    for n, p in frames:
        if n == "lch" and "newUser" in p:
            where[p["newUser"]] = p["pos"]
        elif n == "userMove" and p.get("id") in where and p.get("path"):
            where[p["id"]] = p["path"][-1]
    return where


def hunt(c, got, loc_id, targets, pos):
    """Shoot one creature of each type in targets, in order, each from a cell
    with a clear line to it and out of every hostile's reach (the admin gun
    fells anything with one shot). (the fight's frames, the types killed,
    where the player stands, type -> the cell it fell on, the cells within
    reach of the hostiles still standing)."""
    loc = world.location(loc_id)
    cells = range(loc.width * loc.height)
    types = {}
    for t, es in inhabitants(got).items():
        for e in es:
            types[e] = t
    hostile = {e for e, t in types.items() if MT.get(t, (None,))[0] == world.MOB}
    reach = max([mobs.stats(types[e]).aggro for e in hostile] or [0]) + 0.5
    out, killed, fell, dead = [], [], {}, set()
    for want in targets:
        where = positions(got + out)
        for eid in [e for e, t in types.items() if t == want and e not in dead]:
            home = where.get(eid)
            if home is None:
                continue
            others = [where[e] for e in hostile if e not in dead and e != eid and e in where]
            wary = {cell for cell in cells
                    if any(mobs.hex_distance(cell, o, loc.width) <= reach
                           for o in others + [home])}
            spots = sorted((mobs.hex_distance(cell, home, loc.width), cell) for cell in cells
                           if cell not in loc.obstacles and cell not in wary
                           and travel.side_at(loc, cell) is None
                           and cell not in where.values()
                           and mobs.hex_distance(cell, home, loc.width) <= 40
                           and mobs.line_of_fire(loc, cell, home) is None)
            if not spots:
                continue
            goal = spots[0][1]
            path = mobs.find_path(loc, pos, lambda cell: cell == goal, wary, limit=20000)
            c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
            out += c.frames(0.15 * len(path or [0]) + 0.8)
            pos = goal
            for _ in range(30):
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (GUN, entity(eid)))
                got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                               or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
                out += got_
                if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                    killed.append(want)
                    dead.add(eid)
                    fell[want] = positions(got + out).get(eid, home)
                    break
                time.sleep(0.3)
            if want in killed:
                break
    where = positions(got + out)
    standing = [where[e] for e in hostile if e not in dead and e in where]
    wary = {cell for cell in cells
            if any(mobs.hex_distance(cell, o, loc.width) <= reach for o in standing)}
    return out, killed, pos, fell, wary


def loot(c, fight, loc_id, pos, near, wary=frozenset()):
    """Walk to the corpse's bag that lies nearest `near`, keeping out of
    the wary cells, open it, take all of it and close it: (the types it
    held, the frames of the taking)."""
    loc = world.location(loc_id)
    got = list(fight)
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    bags = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    if not bags:
        return None, []
    bag = min(bags, key=lambda cell: mobs.hex_distance(cell, near, loc.width))
    path = mobs.find_path(loc, pos, lambda cell: cell == bag or progression.within_reach(
        cell, bag, loc.width, loc.height), set(wary), limit=20000)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
    c.frames(0.2 * len(path or [pos]) + 1.0)
    c.send("ss_create;s_type=0;target=%d;" % bag)
    if acks(c.frames()) != [0]:
        return None, []
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
    held = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    took = c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return held, took


def relogin():
    c_ = Client(connect())
    c_.send("hello;minor=2;major=0;")
    c_.send("login;hash=@%s@;" % CRED)
    c_.frames()
    c_.send("selPers;num=0;")
    call = first(c_.until(lambda f: f[0] == "lcall"), "lcall")
    return c_, call, arrive(c_)


def logout(c_):
    c_.send("logout;")
    c_.frames(0.5)
    c_.s.close()
    time.sleep(0.3)


def history_back(cid, types, seconds=86400):
    """Move the hand-ins of these types a day back, as if made yesterday."""
    st = store()
    st.db.execute("UPDATE char_quests_done SET done_at = done_at - ? WHERE char_id = ?"
                  " AND type IN (%s)" % ", ".join("?" * len(types)),
                  (seconds, cid, *types))
    st.db.commit()
    st.close()


def hand_in_story(cid, types):
    """The story quests these map flags wait for, handed in a day ago."""
    st = store()
    for t in types:
        st.finish_quest(0, cid, t, when=int(time.time()) - 86400)
    st.close()


def tail_after(seq, name):
    """The frame names from the last `name` on."""
    return seq[len(seq) - seq[::-1].index(name) - 1:] if name in seq else []


GUN = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Hunter@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    CID = char_id()
    AFRO = 1000
    OFFERED = [GEAR, MATCHES_Q, CHIP_Q, RAT_RIOT, TAILS, ADITS, PISTOL_KIT, EMERALDS_Q,
               ANTELOPE1]
    check("a newcomer: the first of each line is offered, nothing that waits for another",
          [status(c, t) for t in MARKET_Q], [1 if t in OFFERED else 0 for t in MARKET_Q])
    check("  ..and Рудо's way down waits for Шульц's errand", status(c, MINE_DOWN), 0)

    # --- the admin gun, loaded ---------------------------------------------------------
    GUN, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 99)
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held) > 6 and held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % GUN)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, GUN))
    c.until(lambda f: f[0] == "ss_di_firearm")

    # --- Шульц: the mine, and Большой Мвамба at the boss hour ----------------------------
    here = inhabitants(goto(c, VILLAGE))
    check("the caravan: Шульц, Крысолов and Фая",
          [len(here.get(n, [])) for n in (SCHULZ, RATCATCHER, FAYA)], [1, 1, 1])
    # Шульц's «Обучение» (101, Вади-Хальфа's story) stands before his own two
    # in the table, so it is his q_idx 0 (test_halfa_story).
    check("  ..their frames list what they give and take, in the order q_idx counts",
          [quest_lists(c, here, n) for n in (SCHULZ, RATCATCHER)],
          [([101, ADITS, PISTOL_KIT], [PISTOL_KIT]), ([RAT_RIOT, TAILS], [TAILS])])
    got, q_adits = take(c, here, ADITS)
    check("«Старые штольни» taken from Шульц, complete at once",
          (order(got), first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    got, q_kit = take(c, here, PISTOL_KIT)
    check("«Экипировка к пистолету» taken: nought of one", counts(got, quests.KILL_MOBS),
          [([0], 0)])
    c.send("q_si;q_type=%d;" % PISTOL_KIT)
    si = first(c.frames(), "q_si_kill_mobs")
    check("  ..a party's quest, for three: the client prints it under the quest",
          (si.get("party_size"), ints(si.get("mobs_kill"))), (3, [MVAMBA]))
    here = inhabitants(goto(c, MOUTH))
    check("at the mine's mouth, Рудо takes Шульц's errand and his own way down",
          quest_lists(c, here, RUDO), ([MINE_DOWN], [MINE_DOWN, ADITS]))
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, ADITS, q_adits)
    check("  ..handed in to Рудо: the experience, the ack",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, MEDICINE) - med0),
          (["rp_info", "cmdAck"], [0], 20))
    check("  ..and his way down is offered now", status(c, MINE_DOWN), 1)
    got = goto(c, CAMP_M)
    check("at six Большой Мвамба is in his camp, by his name",
          len(inhabitants(got).get(MVAMBA, [])), 1)
    fight, killed, pos, _f, _w = hunt(c, got, CAMP_M, [MVAMBA], first(got, "lenter").get("pos"))
    fight += c.frames(0.5)
    check("Большой Мвамба shot", killed, [MVAMBA])
    check("  ..the journal counts him, complete", counts(fight, quests.KILL_MOBS), [([1], 1)])
    here = inhabitants(goto(c, VILLAGE))
    sh0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, PISTOL_KIT, q_kit)
    check("  ..handed in to Шульц: his teaching, the ack",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, SHOOTING) - sh0),
          (["rp_info", "cmdAck"], [0], 200))

    # --- Муад ----------------------------------------------------------------------------
    here = inhabitants(goto(c, MARKET))
    check("the market: Муад, Сорванец, Доктор Гофус, Фая",
          [len(here.get(n, [])) for n in (MUAD, SORVANETS, GOFUS, FAYA)], [1, 1, 1, 1])
    check("  ..Муад lists all five of his, and takes back the three that ask for things",
          quest_lists(c, here, MUAD), ([GEAR, WIND, STONE, FANGS, SON], [STONE, FANGS, SON]))
    check("  ..nothing of his but the first before the first meeting",
          [status(c, t) for t in (GEAR, WIND, STONE, FANGS, SON)], [1, 0, 0, 0, 0])
    got, q = take(c, here, GEAR)
    check("«Лучшее снаряжение» taken from Муад, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    here = inhabitants(goto(c, ARENA))
    check("the arena: Барыга Сет takes it", quest_lists(c, here, SET), ([], [GEAR]))
    sh0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, GEAR, q)
    check("  ..handed in to Сет: +5 Стрельба, the ack",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, SHOOTING) - sh0),
          (["rp_info", "cmdAck"], [0], 5))
    check("  ..and the rest of Муад's are offered now",
          [status(c, t) for t in (GEAR, WIND, STONE, FANGS, SON)], [0, 1, 1, 1, 1])
    here = inhabitants(goto(c, MARKET))
    got, q_wind = take(c, here, WIND)
    got, q_fangs = take(c, here, FANGS)
    check("«Клык за Клык» taken: nought of ten", counts(got, quests.BRING_L_OBJ),
          [([0], 0)])
    _, got = give(c, FANG, 10)
    got += c.frames(0.4)
    check("  ..ten fangs in the bag: complete", counts(got, quests.BRING_L_OBJ), [([10], 1)])
    got = hand_in(c, here, FANGS, q_fangs)
    AFRO += 150
    check("  ..handed in to Муад: the fangs out, a hundred and fifty afro, the ack",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(FANG)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], AFRO, None))
    for qtype, thing, pay in ((STONE, GRINDSTONE, 50), (SON, MEDS, 200)):
        got, q = take(c, here, qtype)
        _, more = give(c, thing)
        got += more + c.frames(0.4)
        check("«%s» taken; the %s in the bag: complete"
              % (quests.get(qtype).name, names.ALL.get(items.STRING_ID_OFFSET + thing)),
              counts(got, quests.BRING_L_OBJ), [([0], 0), ([1], 1)])
        got = hand_in(c, here, qtype, q)
        AFRO += pay
        check("  ..handed in to Муад: it goes out, %d afro in, the ack" % pay,
              (upto_ack(got), acks(got), purse(got), owned(CID).get(thing)),
              (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], AFRO, None))
    here = inhabitants(goto(c, VILLAGE))
    sh0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, WIND, q_wind)
    check("«Попутный ветер» handed in to Фая in the caravan: +5 Стрельба",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, SHOOTING) - sh0),
          (["rp_info", "cmdAck"], [0], 5))
    check("  ..none of Муад's is offered again",
          [status(c, t) for t in (GEAR, WIND, STONE, FANGS, SON)], [0] * 5)

    # --- the day's quests of the market: Сорванец and Доктор Гофус ----------------------
    here = inhabitants(goto(c, MARKET))
    got, q = take(c, here, MATCHES_Q)
    _, more = give(c, MATCHES, 5)
    got += more + c.frames(0.4)
    check("«Спички детям» taken from Сорванец; five boxes in the bag: complete",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([5], 1)])
    got = hand_in(c, here, MATCHES_Q, q)
    AFRO += 300
    check("  ..handed in: the matches out, three hundred afro, the day's count, the ack",
          (upto_ack(got), acks(got), purse(got), [p["daily_available"] for p in
                                                   named(got, "q_sys")]),
          (["ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"], [0], AFRO, [9]))
    check("  ..not offered again today", status(c, MATCHES_Q), 0)
    got, _q = take(c, here, MATCHES_Q)
    check("  ..nor given", (order(got), acks(got)), (["cmdAck"], [4]))
    got, q = take(c, here, CHIP_Q)
    _, more = give(c, CHIP)
    got += more + c.frames(0.4)
    check("«Сгоревшая микросхема» taken from Доктор Гофус; the old chip in the bag: complete",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([1], 1)])
    got = hand_in(c, here, CHIP_Q, q, obj_idx=0)
    check("  ..handed in choosing the first icon (it counts from the end): the chip out,"
          " the Анестетик МК I in, the day's count, the ack",
          (upto_ack(got), acks(got), new_things(got), owned(CID).get(CHIP),
           [p["daily_available"] for p in named(got, "q_sys")]),
          (["ss_obj_status", "ss_obj_status", "ss_di_heal", "q_sys", "cmdAck"], [0],
           [ANESTHETIC], None, [8]))
    check("  ..not offered again today", status(c, CHIP_Q), 0)
    history_back(CID, [MATCHES_Q, CHIP_Q])
    check("a day later, both are offered again", [status(c, t) for t in (MATCHES_Q, CHIP_Q)],
          [1, 1])
    got, q = take(c, here, CHIP_Q)
    give(c, CHIP)
    c.frames(0.4)
    got = hand_in(c, here, CHIP_Q, q, obj_idx=1)
    check("  ..the chip again, choosing the other icon: the Салюс МК I",
          (acks(got), new_things(got)), ([0], [SALUS]))

    # --- the rat-catcher, the farmer and his brother -------------------------------------
    here = inhabitants(goto(c, VILLAGE))
    got, q_riot = take(c, here, RAT_RIOT)
    got, q_tails = take(c, here, TAILS)
    _, more = give(c, TAIL, 20)
    got += more + c.frames(0.4)
    check("«Крысиный переполох» and «Крысиные хвосты» taken; twenty tails in the bag",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([20], 1)])
    got = hand_in(c, here, TAILS, q_tails)
    AFRO += 300
    check("  ..the tails handed in to Крысолов: out, three hundred afro, the day's count",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(TAIL)),
          (["ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"], [0], AFRO, None))
    here = inhabitants(goto(c, BARN))
    check("the barn: Фермер Хрущ among his grey rats",
          (quest_lists(c, here, KHRUSCH), len(here.get(GREY_RAT, [])) > 0),
          (([KING_Q, ELIXIR], [RAT_RIOT, KING_Q]), True))
    check("  ..the rat king waits for the rat-catcher's word", status(c, KING_Q), 0)
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, RAT_RIOT, q_riot)
    check("«Крысиный переполох» handed in to Хрущ: the experience",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, MEDICINE) - med0),
          (["rp_info", "cmdAck"], [0], 20))
    got, q = take(c, here, KING_Q)
    check("«Крысиный король» taken: no king yet", counts(got, quests.BRING_L_OBJ), [([0], 0)])
    _, more = give(c, KING)
    more += c.frames(0.4)
    check("  ..a king in the bag: complete", counts(more, quests.BRING_L_OBJ), [([1], 1)])
    got = hand_in(c, here, KING_Q, q)
    AFRO += 200
    check("  ..handed in to Хрущ: the king out, two hundred afro, the day's count",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(KING)),
          (["ss_obj_status", "userInfo_Player", "q_sys", "cmdAck"], [0], AFRO, None))
    check("  ..not again today; his brother's errand is offered now",
          [status(c, t) for t in (KING_Q, ELIXIR)], [0, 1])
    got, q = take(c, here, ELIXIR)
    _, more = give(c, KING)
    got += more + c.frames(0.4)
    check("«Королевский Элексир» taken; a king in the bag: complete",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([1], 1)])
    here = inhabitants(goto(c, QUARTER))
    check("the quarter of Вади-Хальфа: Эддай stands there, and takes it",
          (len(here.get(EDDAI, [])), quest_lists(c, here, EDDAI)), (1, ([], [ELIXIR])))
    got = hand_in(c, here, ELIXIR, q)
    AFRO += 500
    check("  ..handed in to Эддай: the king out, five hundred afro, the ack",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(KING)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], AFRO, None))

    # --- Камал's emeralds ----------------------------------------------------------------
    here = inhabitants(goto(c, TIER1))
    check("the mine's first tier: Камал gives the way out, the gold sand and the emeralds",
          quest_lists(c, here, KAMAL), ([8, 9, EMERALDS_Q], [8, 9, EMERALDS_Q]))
    got, q = take(c, here, EMERALDS_Q)
    _, more = give(c, EMERALD, 5)
    got += more + c.frames(0.4)
    check("«Изумруды» taken; five emeralds in the bag: complete",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([5], 1)])
    sh0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, EMERALDS_Q, q)
    check("  ..handed in to Камал: the emeralds out, he teaches shooting, the ack",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, SHOOTING) - sh0,
           owned(CID).get(EMERALD)), (["ss_obj_status", "rp_info", "cmdAck"], [0], 100, None))

    # --- Сабир's antelopes, with Хасани ---------------------------------------------------
    here = inhabitants(goto(c, NORTH))
    check("the north village: Хасани lists Сабир's quests and the four map flags",
          quest_lists(c, here, HASANI),
          ([ANTELOPE1, FOOD, HUNT_Q, WHERE_ANT, WHERE_NORMAN, WHERE_SEIFUL, WHERE_CORBEN],
           [ANTELOPE2, FOOD, HUNT_Q]))
    check("  ..the first of them only, before the antelope",
          [status(c, t) for t in (ANTELOPE1, FOOD, HUNT_Q, WHERE_ANT, WHERE_NORMAN,
                                  WHERE_SEIFUL, WHERE_CORBEN)], [1, 0, 0, 0, 0, 0, 0])
    got, q = take(c, here, ANTELOPE1)
    got = goto(c, ANTELOPES)
    here, cell = inhabitants(got), first(got, "lenter").get("pos")
    check("the antelopes: the dead one takes the first part and gives the second",
          (len(here.get(ANTELOPE, [])) > 0, quest_lists(c, here, CARCASS)),
          (True, ([ANTELOPE2], [ANTELOPE1, WHERE_ANT])))
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, ANTELOPE1, q)
    check("«Любимая антилопа» handed in at the carcass: the experience",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, MEDICINE) - med0),
          (["rp_info", "cmdAck"], [0], 20))
    got, q = take(c, here, ANTELOPE2)
    check("part 2 taken from the carcass: the meat into the bag, the ack, found and complete",
          (order(got), first(got, "q_di_del_obj").get("obj"),
           first(got, "q_di_del_obj").get("complete"), owned(CID).get(MEAT)),
          (["ss_obj_status", "ss_di_heap", "cmdAck", "q_di_del_obj"], 1, 1, 1))
    # «Еда» asks for that meat: thrown down, dropped from the journal (which
    # takes back only what the character has) and picked up again, each take
    # of part 2 would be one more piece for the village without a hunt.
    meat = [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status")
            if (inventory.parse_oid(str(p["obj"]).lstrip("x")) or (0, 0))[1] == MEAT]
    c.send("ss_create;s_type=0;target=%d;" % cell)
    opened = acks(c.frames())
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % meat[0])
    thrown = c.frames()
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    check("  ..and not thrown on the ground: the session opens, the drop is refused, no"
          " bag goes down, the meat still in the bag",
          (opened, order(thrown), acks(thrown), owned(CID).get(MEAT)),
          ([0], ["cmdAck"], [3], 1))
    here = inhabitants(goto(c, NORTH))
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, ANTELOPE2, q)
    check("  ..carried to Хасани: the meat out, the experience, the ack",
          (no_level(upto_ack(got)), acks(got), owned(CID).get(MEAT),
           skill_seen(c, MEDICINE) - med0), (["ss_obj_status", "rp_info", "cmdAck"], [0], None,
                                             20))
    check("  ..the village's meat, the hunt and the antelopes' flag are offered now",
          [status(c, t) for t in (FOOD, HUNT_Q, WHERE_ANT)], [1, 1, 1])
    got, q_food = take(c, here, FOOD)
    got, q_hunt = take(c, here, HUNT_Q)
    got, q_where = take(c, here, WHERE_ANT)
    check("«Еда», «Охота на антилоп» and «Где антилопы?» taken",
          [bool(q_food), bool(q_hunt), bool(q_where)], [True] * 3)
    got = goto(c, ANTELOPES)
    here = inhabitants(got)
    got2 = hand_in(c, here, WHERE_ANT, q_where)
    check("«Где антилопы?» handed in at the dead antelope: nothing paid, the ack",
          (upto_ack(got2), acks(got2)), (["cmdAck"], [0]))
    fight, killed, pos, fell, wary = hunt(c, got, ANTELOPES, [ANTELOPE],
                                         first(got, "lenter").get("pos"))
    check("an antelope shot", killed, [ANTELOPE])
    held, took = loot(c, fight, ANTELOPES, pos, fell.get(ANTELOPE, pos), wary)
    check("  ..its bag holds the meat for the village, once, beside its own",
          ((held or []).count(MEAT), (held or []).count(224) >= 1), (1, True))
    check("  ..taken: «Еда» counts it",
          [p["obj_num"] for p in named(took, "q_di_bring_l_obj") if p["q_id"] == q_food],
          [[1]])
    _, more = give(c, MEAT, 2)
    more += c.frames(0.4)
    _, more2 = give(c, FILLET, 10)
    more += more2 + c.frames(0.4)
    last = {}
    for p in named(more, "q_di_bring_l_obj"):
        last[p["q_id"]] = (p["obj_num"], p["complete"])
    check("  ..two more pieces and ten fillets: both complete",
          [last.get(q_food), last.get(q_hunt)], [([3], 1), ([10], 1)])
    here = inhabitants(goto(c, NORTH))
    got = hand_in(c, here, FOOD, q_food)
    AFRO += 100
    check("«Еда» handed in to Хасани: the meat out, a hundred afro, the day's count",
          (tail_after(upto_ack(got), "userInfo_Player"), acks(got), purse(got),
           owned(CID).get(MEAT), gone_things(got) >= 1),
          (["userInfo_Player", "q_sys", "cmdAck"], [0], AFRO, None, True))
    sh0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, HUNT_Q, q_hunt)
    AFRO += 150
    check("«Охота на антилоп» handed in: ten fillets out, +30 Стрельба, 150 afro",
          (tail_after(no_level(upto_ack(got)), "rp_info"), acks(got), purse(got),
           skill_seen(c, SHOOTING) - sh0, owned(CID).get(FILLET, 0) < 10),
          (["rp_info", "userInfo_Player", "cmdAck"], [0], AFRO, 30, True))
    check("  ..«Еда» not again today, the hunt not again",
          [status(c, t) for t in (FOOD, HUNT_Q)], [0, 0])

    # --- the map flags to the story's people ----------------------------------------------
    check("the flags to Норман, Сейфул and Корбен wait for Наби's line",
          [status(c, t) for t in (WHERE_NORMAN, WHERE_SEIFUL, WHERE_CORBEN)], [0, 0, 0])
    hand_in_story(CID, [30, 33, 35])
    check("  ..and are offered once it has sent the player their way",
          [status(c, t) for t in (WHERE_NORMAN, WHERE_SEIFUL, WHERE_CORBEN)], [1, 1, 1])
    got, q = take(c, here, WHERE_NORMAN)
    check("«Где мастер Норман?» taken from Хасани, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    c.send("q_si;q_type=%d;" % WHERE_NORMAN)
    si = first(c.frames(), "q_si_del_obj")
    check("  ..its flag is the truck's cell", (si.get("loc"), si.get("finish_loc")),
          (pack(*world.cell_of(TRUCK)),) * 2)
    here = inhabitants(goto(c, TRUCK))
    got = hand_in(c, here, WHERE_NORMAN, q)
    check("  ..handed in to Мастер Норман: nothing paid, the ack", (upto_ack(got), acks(got)),
          (["cmdAck"], [0]))

    # --- all of it ------------------------------------------------------------------------
    handed = [t for t in done(CID) if t in MARKET_Q]
    check("every quest of the batch walked is in the history as often as it was handed in",
          handed, sorted([GEAR, WIND, STONE, FANGS, SON, MATCHES_Q, CHIP_Q, CHIP_Q, RAT_RIOT,
                          TAILS, KING_Q, ELIXIR, ADITS, PISTOL_KIT, EMERALDS_Q, ANTELOPE1,
                          ANTELOPE2, FOOD, HUNT_Q, WHERE_ANT, WHERE_NORMAN]))
    check("  ..no one-off of them offered again",
          [t for t in ONE_OFF if t in handed and status(c, t)], [])
    check("  ..of the day's, only the matches, handed in «yesterday»",
          [t for t in DAILY if status(c, t)], [MATCHES_Q])
    got = goto(c, MARKET)
    check("the day's repeatable hand-ins: the second chip, the tails, the king, the meat --"
          " six left", [p["daily_available"] for p in named(got, "q_sys")][-1:], [6])
    logout(c)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-60:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("valley market OK")
