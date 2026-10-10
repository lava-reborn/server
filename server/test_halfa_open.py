"""Вади-Хальфа open (the owner's «займись фулл восстановлением Вади-Хальфы»,
2026-09-28; open again since 2026-10-03, «открой хальфу»): «В Хальфу!» (43)
switched on, and a newcomer's first steps in the town walked end to end on
the real tables -- the shipped data/quests.json (with its questgen
companions), data/passages.json and data/placements.json, no knob of the
suite's own but the cheats that stand in for the walking.

  valley   the story up to Наби's farewell (42) behind him, as
           test_valley_story walks it; Демир's «В Хальфу!» from the
           caravan's village (186) to Причал (41)
  welcome  «Добро пожаловать в Хальфу» (45): Демир at Причал -> Саид in the
           quarter (36)
  act 1    «Рэкетиры» (102): the New Colonists' camp (80) stands its
           fighters of the town's first band, levels 0-2; five Лазутчики
           shot, a hundred afro at Саид's
  the Tir  «Тир Берта Гаммера» (1682) from Берт on the old market (35) into
           his bunker; the seven lessons with the kit each lends (the
           training gun and the Tir's rounds; «Получить боеприпасы» asked
           whenever they run dry), the targets teaching nothing (objects pay
           no experience); the certificate, and back on the market
  Тиль     «Охотник» (1829) on the black market (102): the certificate for
           a part of the self-teacher and the coin
  healer   Деда Джоф (100) at the station (37): healing for 150 afro, and
           «Прописка» there
  the way  «Назад, в долину» (44) at Причал: offered at the second level,
  back     ridden, and gone at the third
  gold     the one rate the client is told at login and c_ga converts at:
           50 000 afro an ounce (the owner's, progression.GOLD_TO_AFRO_RATE)

Along the whole path nobody stands by his mobs.xml name (but the remainder
data/orig_names_manual.json lists under "none" with its reason; the one of
it the path met, the black market's 639, is out of the game since the
owner's «надо убрать с хальфы wh_modif_armor_g» of 2026-10-10, and the
black market's frames are held to show him no more), no thing the path
hands out shows its internal name -- the lent kit, the certificate, the
self-teacher's parts and the coin -- and every string id of its quests is in
the launcher's table (a missing one sends the client back to the login).

In process first: row 43 on in the shipped table (Демир of the caravan gives
and takes it) and the suite on that very table, its way in
data/passages.json, and the rows the path takes in the order their
givers list them.

    LAVA_RES=.../lava/res python3 server/test_halfa_open.py
"""
import collections
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK", "LAVA_START", "LAVA_START_AFRO", "LAVA_SCHEDULE",
              "LAVA_GX", "LAVA_GY", "LAVA_LOC"):
    os.environ.pop(_knob, None)

# «В Хальфу!» (43) is on in the shipped table again since 2026-10-03 (the
# owner: «открой хальфу»; off from 2026-09-26, on 2026-09-28 once the town
# was restored, off again the same evening, «закрой хальфу обратно»):
# Демир of the caravan (5193) gives and takes it, which is checked first.
# The path below plays on that table itself, with the questgen companions a
# table LAVA_QUESTS names would not have (the knob is popped above).
_REAL = os.path.join(os.path.dirname(HERE), "data", "quests.json")
with open(_REAL, encoding=ENC) as _fh:
    HALFA_ON = [(r["give"], r["take"]) for r in json.load(_fh)["quests"] if r["type"] == 43]

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# The places.
START, VILLAGE, PIER, QUARTER, CAMP_NC, CHIEF_NC = 181, 186, 41, 36, 80, 82
OLD_MARKET, BLACK_MARKET, STATION = 35, 102, 37
RANGE = [732, 1048, 1233, 1260, 1276, 1280, 1282]            # TIR_00..06
# The quests.
VALLEY_STORY = list(range(28, 43))                          # «Нет больше покоя» .. 42
TO_HALFA, BACK, WELCOME, RACKET = 43, 44, 45, 102
COURSE, LESSONS, AMMO_Q, HUNTER = 1682, list(range(351, 358)), 365, 1829
PATH = [TO_HALFA, BACK, WELCOME, RACKET, COURSE] + LESSONS + [AMMO_Q, HUNTER]
# The people.
DEMIR_V, DEMIR_H, SAID, BERT, TIL, HEALER = 5193, 30, 44, 2088, 5, 100
WAKKAS, KHAMIS = 1204, 1205                                 # the black market's clothing
ARMOR_G = 639          # wh_modif_armor_g, out of the game since 2026-10-10 (data/retired.json)
BERT_TI = [2089, 2090, 2091, 2092, 2093, 2094, 2095]
SCOUT = 258                                                 # [0] Лазутчик, Новые колонисты
# The things.
ROUNDS, GUNS, CERT, COIN = 3727, [3728, 3729, 3730, 3731, 3732, 3733], 3742, 46652
PARTS = list(range(5065, 5071))                              # «Охотник»: a part of six
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
RATE = 50000                                                # afro an ounce, the owner's
SHOOTING = progression.SHOOTING
MT = world.mob_types()
# Named by nobody, each with its reason in the file (test_halfa_names holds it
# small): on this path nobody shows by his mobs.xml name since the black
# market's 639 left the game (data/retired.json, 2026-10-10).
with open(os.path.join(os.path.dirname(HERE), "data", "orig_names_manual.json"),
          encoding=ENC) as _fh:
    REMAINDER = {int(k) for k in json.load(_fh)["none"]}


# --- in process ------------------------------------------------------------------------
try:
    check("«В Хальфу!» is on in the shipped table: Демир of the caravan gives and takes it",
          HALFA_ON, [([DEMIR_V], [DEMIR_V])])
    check("  ..and the suite walks that very table, its companions with it (no LAVA_QUESTS)",
          (os.path.abspath(quests.quests_path()) == os.path.abspath(_REAL),
           bool(quests.companion_paths(quests.quests_path()))), (True, True))
    to_halfa = quests.get(TO_HALFA)
    check("«В Хальфу!» as the server reads it: Демир of the caravan gives and takes it,"
          " a repeatable ride open at any level",
          (to_halfa.give, to_halfa.take, to_halfa.repeatable, to_halfa.level,
           to_halfa.max_level or 0), ([DEMIR_V], [DEMIR_V], 1, 0, 0))
    check("  ..its way in data/passages.json: from the caravan's village to Причал",
          int((travel.quest_way(world.location(VILLAGE), TO_HALFA) or {})
              .get("target_loc_id", 0)), PIER)
    check("the givers list the path's rows where q_idx will find them",
          ([t in quests.given_by(DEMIR_V) for t in (TO_HALFA,)],
           [t in quests.given_by(DEMIR_H) for t in (BACK, WELCOME)],
           RACKET in quests.given_by(SAID), COURSE in quests.given_by(BERT),
           HUNTER in quests.given_by(TIL)),
          ([True], [True, True], True, True, True))
    check("  ..«Назад, в долину» is capped at the second level; «Рэкетиры» follows the"
          " welcome, the certificate follows the last lesson",
          (quests.get(BACK).max_level, quests.get(RACKET).need_quest,
           quests.get(HUNTER).need_quest, quests.get(WELCOME).need_quest), (2, WELCOME, 357, 42))
    check("the lessons pay no experience of their own: whatever the course teaches, the"
          " targets would",
          [t for t in [COURSE] + LESSONS if quests.get(t).rew_xp or quests.get(t).rew_spec_xp], [])
    check("every string id of the path's quests is in the launcher's table",
          [t for t in PATH if not all(names.known(i) for i in quests.get(t).string_ids())], [])
    check("the targets are objects, and objects pay no experience (combat.OBJECTS_PAY_XP)",
          (sorted({world.creature_role(t) for t in range(1397, 1403)}), combat.OBJECTS_PAY_XP),
          (["object"], False))
    check("one rate, the owner's", progression.GOLD_TO_AFRO_RATE, RATE)
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server -------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_open.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("newcomer", "secret")
_store.close()
CRED = accounts.credential("newcomer", "secret")
# The one switch of the suite's own: a newcomer wakes in the valley's north
# village (one of server.START_PLACES), as run_suite asks of a suite that
# needs one. The cheats stand in for the walking and the admin gun for the
# camp's fight; the Tir is shot with what the course lends.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START=str(START), LAVA_AP_REGEN="50", LAVA_RESPAWN="2",
           LAVA_SEED="11", LAVA_LEAVE_COMBAT="2", LAVA_POLICY_PORT="0")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


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


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(eid):
    return "x1%08x" % eid


# Every creature the client was shown on the way: type -> the place first seen.
SEEN = {}


def inhabitants(frames, where=None):
    """type id -> [entity id] of the userInfo_* frames of an arrival (and a
    note of each type for the check of names at the end)."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    for t in out:
        SEEN.setdefault(t, where)
    return out


def infos(frames):
    """type id -> (frame name, params) of the first userInfo_* of each type."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], (n, p))
    return out


def positions(frames):
    where = {}
    for n, p in frames:
        if n == "lch" and "newUser" in p:
            where[p["newUser"]] = p["pos"]
        elif n == "userMove" and p.get("id") in where and p.get("path"):
            where[p["id"]] = p["path"][-1]
    return where


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, loc_id):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, here, npc_type, qtype):
    npc = here.get(npc_type, [0])[0]
    offered = quests.given_by(npc_type)
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, offered.index(qtype) if qtype in offered else 99))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id, obj_idx=0, wait=0.9):
    npc = here.get(npc_type, [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def moved(c, got, where=None, wait=8):
    """The lcall a way's hand-in is followed by, and the arrival's frames:
    (lcall params, arrival)."""
    call = first(got, "lcall") or first(c.until(lambda f: f[0] == "lcall", wait), "lcall")
    arrival = arrive(c) if call else []
    inhabitants(arrival, where or call.get("id"))
    return call, arrival


def store():
    return accounts.Store(DB)


def cid_of(name):
    st = store()
    row = st.character_by_name(name)
    st.close()
    return row["id"]


def held(cid):
    """type id -> pieces the character has, wherever (bag, hands, body, bank)."""
    st = store()
    out = collections.Counter()
    for r in st.items_of(cid):
        out[r["type_id"]] += r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
    st.close()
    return out


def money(cid):
    st = store()
    got = tuple(st.money(cid))
    st.close()
    return got


def learned(cid):
    """The character's skills and specialisations as saved: (level, xp) each."""
    st = store()
    ch = progression.Character.load(st, cid)
    st.close()
    return ([tuple(s[:2]) for s in ch.skill], [tuple(s[:2]) for s in ch.spec])


def login(first_time=False):
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    got = c.frames()
    if first_time:
        c.send("newPers;res=1;sex=0;name=@Newcomer@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    arrival = arrive(c)
    inhabitants(arrival, call.get("id"))
    return c, got, call, arrival


def logout(c):
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)


def oid(cid, type_id):
    """The oid of a thing of a type in the bag or the hands (of a stack, the
    largest), or None."""
    st = store()
    rows = [r for r in st.items_of(cid) if r["type_id"] == type_id
            and r["slot"] in (inventory.BAG,) + inventory.HAND_SLOTS]
    st.close()
    rows.sort(key=lambda r: -r["count"])
    return inventory.oid_of(rows[0]) if rows else None


def wield(c, thing):
    """Into the hand (primary), whatever was there back into the bag."""
    c.send("ss_get;target=0;slot=11;")
    held_ = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held_) > 6 and held_[6] not in ("0", thing):
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held_[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % thing)
    return acks(c.frames())


def load(c, gun, rounds):
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "cmdAck" and f[1]["res"]), 3)
    return got + c.frames(0.3)


ASKED_ROUNDS = []


def more_rounds(c, arrival, loc_id):
    """«Получить боеприпасы» from Берт's copy in the range: a hundred more of
    the Tir's rounds, free."""
    here, npc = inhabitants(arrival), BERT_TI[RANGE.index(loc_id)]
    got, q = take(c, here, npc, AMMO_Q)
    got = got + (hand_in(c, here, npc, q) if q else [])
    ASKED_ROUNDS.append((loc_id, acks(got)))
    return got


def shoot_targets(c, arrival, loc_id, want, gun, cid, mode=0):
    """Shoot from the booth, over its counter, the targets a lesson asks for
    (type -> pieces) with the lent gun, loading it from the Tir's rounds
    whenever it runs dry and asking Берт for more when none are left, as a
    player out of them would (test_halfa_training does the same): (the
    fight's frames, the types felled)."""
    loc = world.location(loc_id)
    W = loc.width
    reach = items.params_of(inventory.parse_oid(gun)[1])["max_range"][mode]
    ents = {e: t for t, es in inhabitants(arrival).items() for e in es}
    where = positions(arrival)
    pos = first(arrival, "lenter").get("pos")
    booth, todo = {pos}, collections.deque([pos])
    while todo:
        cur = todo.popleft()
        for nb in progression.hex_neighbours(cur, W, loc.height):
            if nb not in booth and nb not in loc.obstacles and nb not in where.values():
                booth.add(nb)
                todo.append(nb)
    out, felled = [], []
    for t, n in sorted(want.items()):
        for eid in [e for e, tt in sorted(ents.items()) if tt == t][:n]:
            cell = where[eid]
            spots = sorted((mobs.hex_distance(b, cell, W), mobs.hex_distance(b, pos, W), b)
                           for b in booth if combat.shot_wall(loc, b, cell) is None
                           and mobs.hex_distance(b, cell, W) <= reach)
            if not spots:
                continue
            goal = spots[0][2]
            if goal != pos:
                path = mobs.find_path(loc, pos, lambda x: x == goal, set(where.values()),
                                      limit=20000)
                c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
                out += c.frames(0.3 + 0.25 * len(path or [goal]))
                pos = goal
            for _ in range(80):
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
                got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "lch" and f[1].get(
                    "dead") == eid) or (f[0] == "cmdAck" and f[1]["res"]), 3)
                got += c.frames(0.05)
                out += got
                if inventory.RES_NO_AMMO in acks(got):
                    rounds = oid(cid, ROUNDS)
                    if rounds is None:
                        out += more_rounds(c, arrival, loc_id)
                        rounds = oid(cid, ROUNDS)
                    loaded = load(c, gun, rounds) if rounds else []
                    out += loaded
                    if acks(loaded) != [0]:
                        return out, felled
                    continue
                if any(nm == "lch" and p.get("dead") == eid for nm, p in got):
                    felled.append(t)
                    break
    return out + c.frames(0.5), felled


def hunt(c, got, loc_id, target, pos, gun):
    """Shoot one creature of a type with the admin gun from a cell with a
    clear line to it and out of every other hostile's reach, as
    test_halfa_story does: (frames, killed?)."""
    loc = world.location(loc_id)
    cells = range(loc.width * loc.height)
    types = {e: t for t, es in inhabitants(got, loc_id).items() for e in es}
    hostile = {e for e, t in types.items() if MT.get(t, (None,))[0] == world.MOB}
    reach = max([mobs.stats(types[e]).aggro for e in hostile] or [0]) + 0.5
    where = positions(got)
    out = []
    for eid in [e for e, t in types.items() if t == target]:
        home = where.get(eid)
        if home is None:
            continue
        others = [where[e] for e in hostile if e != eid and e in where]
        wary = {cell for cell in cells
                if any(mobs.hex_distance(cell, o, loc.width) <= reach for o in others + [home])}
        spots = sorted((mobs.hex_distance(cell, home, loc.width), cell) for cell in cells
                       if cell not in loc.obstacles and cell not in wary
                       and travel.side_at(loc, cell) is None and cell not in where.values()
                       and mobs.hex_distance(cell, home, loc.width) <= 40
                       and mobs.line_of_fire(loc, cell, home) is None)
        if not spots:
            continue
        goal = spots[0][1]
        path = mobs.find_path(loc, pos, lambda cell: cell == goal, wary, limit=20000)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
        out += c.frames(0.15 * len(path or [0]) + 0.8)
        for _ in range(30):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
            got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                           or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
            out += got_
            if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                return out, True
            time.sleep(0.3)
    return out, False


try:
    # --- login: the one rate ------------------------------------------------------------
    c, got, call, arrival = login(first_time=True)
    check("the client is told the owner's rate at login: 50 000 afro an ounce",
          [p.get("gold_to_afro_rate") for p in named(got, "constants")], [RATE])
    check("a newcomer wakes in the valley's north village", call.get("id"), START)
    CID = cid_of("Newcomer")
    check("  ..offered Демир's ride to Вади-Хальфа and the one back, not Саид's errand (the"
          " story is not behind him) nor anything of the town's",
          [status(c, t) for t in (TO_HALFA, BACK, WELCOME, RACKET, HUNTER)], [1, 1, 0, 0, 0])
    logout(c)
    # The valley's story up to Наби's farewell, as test_valley_story walks it.
    st = store()
    for t in VALLEY_STORY:
        st.finish_quest(0, CID, t)
    st.close()

    # --- the valley: Демир's ride ---------------------------------------------------------
    c, _got, _call, _arr = login()
    here = inhabitants(goto(c, VILLAGE), VILLAGE)
    got, q = take(c, here, DEMIR_V, TO_HALFA)
    check("«В Хальфу!» taken from Демир in the caravan's village: the ack, the journal,"
          " complete", (order(got)[:2], first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    got = hand_in(c, here, DEMIR_V, q)
    call, arrival = moved(c, got)
    here = inhabitants(arrival, PIER)
    check("  ..handed back: the ack, and the ride to Причал, where Демир of the town stands",
          (acks(got)[:1], call.get("id"), len(here.get(DEMIR_H, []))), ([0], PIER, 1))
    check("at Причал: Саид's errand now, and the ride back", [status(c, t) for t in (WELCOME, BACK)],
          [1, 1])

    # --- the welcome, Саид --------------------------------------------------------------------
    got, q = take(c, here, DEMIR_H, WELCOME)
    check("«Добро пожаловать в Хальфу» taken from Демир, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    here = inhabitants(goto(c, QUARTER), QUARTER)
    check("Саид offers nothing of his own before the welcome", status(c, RACKET), 0)
    got = hand_in(c, here, SAID, q)
    check("  ..handed in to Саид in the quarter: the experience, the ack",
          ([n for n in upto_ack(got) if n != "usrUp"], acks(got)), (["rp_info", "cmdAck"], [0]))
    check("  ..and «Рэкетиры» is offered now", status(c, RACKET), 1)
    got, q_racket = take(c, here, SAID, RACKET)
    check("«Рэкетиры» taken: nought of five",
          [(p["kill_num"], p["complete"]) for p in named(got, "q_di_kill_mobs")], [([0], 0)])

    # --- the camp of the New Colonists ----------------------------------------------------
    GUN, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 99)
    wield(c, GUN)
    load(c, GUN, rounds)
    arrival = goto(c, CAMP_NC)
    camp = inhabitants(arrival, CAMP_NC)
    fighters = sorted(t for t in camp if MT.get(t, (None,))[0] == world.MOB
                      and getattr(mobs.stats(t), "role", None) != "object")
    check("the New Colonists' camp (80) stands its fighters, all of the town's first band,"
          " levels 0-2, the Лазутчики among them",
          (len(fighters) >= 9, sorted({mobs.stats(t).level for t in fighters}) <= [0, 1, 2]
           and all(0 <= mobs.stats(t).level <= 2 for t in fighters),
           all(MT[t][1].startswith(("nc_", "mrare_")) for t in fighters), SCOUT in fighters),
          (True, True, True, True))
    mark, shot = len(c.seen), 0
    for i in range(14):
        loc_id = (CAMP_NC, CHIEF_NC)[i % 2]
        arrival = goto(c, loc_id)
        _fight, killed = hunt(c, arrival, loc_id, SCOUT, first(arrival, "lenter").get("pos"), GUN)
        shot += bool(killed)
        if shot == 5:
            break
        time.sleep(1.0)
    c.frames(0.5)
    check("five Лазутчики shot in the camp and at its chief's, the journal complete on the"
          " fifth", (shot, [p["complete"] for p in named(c.seen[mark:], "q_di_kill_mobs")][-1:]),
          (5, [1]))
    here = inhabitants(goto(c, QUARTER), QUARTER)
    afro0 = money(CID)[0]
    got = hand_in(c, here, SAID, q_racket)
    check("  ..handed in to Саид: the ack, a hundred afro", (acks(got), money(CID)[0] - afro0),
          ([0], 100))
    logout(c)
    SKILLS_BEFORE = learned(CID)

    # --- the Tir ------------------------------------------------------------------------------
    c, _got, _call, _arr = login()
    here = inhabitants(goto(c, OLD_MARKET), OLD_MARKET)
    got, q = take(c, here, BERT, COURSE)
    check("«Тир Берта Гаммера» taken from Берт on the old market, complete",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, BERT, q)
    call, arrival = moved(c, got)
    check("  ..handed back: into his bunker (TIR_00), told as a sublocation",
          (acks(got), call.get("id"), call.get("g_id", 0) >> 26), ([0], RANGE[0], 1))
    rp_shots = 0
    for k, t in enumerate(LESSONS):
        loc_id = RANGE[k]
        here = inhabitants(arrival, loc_id)
        got, q = take(c, here, BERT_TI[k], t)
        if k:
            have = held(CID)
            gun, rounds = oid(CID, GUNS[k - 1]), oid(CID, ROUNDS)
            check("lesson %d («%s»): the training gun and a hundred of the Tir's rounds lent"
                  % (k + 1, quests.get(t).name),
                  (acks(got), have[GUNS[k - 1]], have[ROUNDS] >= 100), ([0], 1, True))
            wield(c, gun)
            load(c, gun, rounds)
            mode = 1 if items.params_of(GUNS[k - 1])["fire_mods"][1] else 0
            if mode:
                c.send("ss_use;target=x%x;obj=x%s;type=64;" % (mode, gun))
                c.frames(0.5)
            want = dict(zip(quests.get(t).mobs_kill, quests.get(t).num_kill))
            fight, felled = shoot_targets(c, arrival, loc_id, want, gun, CID, mode)
            rp_shots += len(named(fight, "rp_info"))
            check("  ..its targets shot from the booth with the lent kit alone, counted to"
                  " complete", (sorted(felled), (named(fight, "q_di_kill_mobs") or [{}])[-1]
                                .get("complete")),
                  (sorted(tt for tt, n in want.items() for _ in range(n)), 1))
        else:
            check("lesson 1: the theory, complete at once",
                  (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
        got = hand_in(c, here, BERT_TI[k], q, wait=1.2)
        call, arrival = moved(c, got)
        nxt = RANGE[k + 1] if k + 1 < len(RANGE) else OLD_MARKET
        check("  ..handed in: on to %s" % ("TIR_0%d" % (k + 1) if nxt != OLD_MARKET
                                           else "the old market"),
              (acks(got)[:1], call.get("id")), ([0], nxt))
        if k:
            check("  ..the training gun taken back", held(CID)[GUNS[k - 1]], 0)
    check("the targets taught nothing: no experience frame in any lesson's fight",
          rp_shots, 0)
    have = held(CID)
    check("the course over: the certificate in the bag, no training gun",
          (have[CERT], [g for g in GUNS if have[g]]), (1, []))
    check("  ..«Получить боеприпасы» answered every time the lent rounds ran dry",
          [a for _l, a in ASKED_ROUNDS if a[:1] != [0]], [])

    # --- Тиль: the certificate ----------------------------------------------------------------
    here = inhabitants(goto(c, BLACK_MARKET), BLACK_MARKET)
    check("the black market as the client is shown it: Тиль, Ваккас and Хамис, and no"
          " wh_modif_armor_g (639), out of the game by the owner's word of 2026-10-10",
          (TIL in here, WAKKAS in here, KHAMIS in here, ARMOR_G in here), (True, True, True, False))
    check("Мастер Тиль offers «Охотник» now", status(c, HUNTER), 1)
    got, q = take(c, here, TIL, HUNTER)
    check("«Охотник» taken at Тиль: the certificate in the bag, complete",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, TIL, q, obj_idx=0)
    have = held(CID)
    check("  ..handed in: the certificate out, one part of the self-teacher and the coin in",
          (acks(got), have[CERT], sum(have[p] for p in PARTS), have[COIN]), ([0], 0, 1, 1))
    logout(c)
    check("the whole course and «Охотник» after it: the skills and specialisations as they"
          " were before the Tir (objects pay no experience, the lessons none of their own)",
          learned(CID), SKILLS_BEFORE)

    # --- the healer at the station ----------------------------------------------------------
    c, _got, _call, _arr = login()
    arrival = goto(c, STATION)
    inhabitants(arrival, STATION)
    kind, healer = infos(arrival).get(HEALER, ("", {}))
    check("Деда Джоф at the station: a healer at 150 afro who offers «Прописка»",
          (kind, healer.get("a_price"), healer.get("can_set_home")), ("userInfo_Medic", 150, 1))
    afro0 = money(CID)[0]
    c.send("on_conv;mob=%d;op=1;" % healer.get("id", 0))
    got = c.frames()
    check("  ..healing: the ack, 150 afro taken", (acks(got), afro0 - money(CID)[0]), ([0], 150))
    c.send("on_conv;mob=%d;op=0;" % healer.get("id", 0))
    check("  ..home registered there", acks(c.frames()), [0])
    st = store()
    check("  ..and the home is the station",
          st.db.execute("SELECT home_loc FROM characters WHERE id = ?", (CID,)).fetchone()[0],
          STATION)
    st.close()

    # --- gold into afro -------------------------------------------------------------------------
    c.send("userMsg;entry=@/money 0 100@;group=0;")
    c.frames()
    before = money(CID)
    c.send("c_ga;gold=100;")
    got = c.frames()
    check("c_ga: one ounce into 50 000 afro, the ack first",
          (order(got)[:2], acks(got), money(CID)[0] - before[0], before[1] - money(CID)[1]),
          (["cmdAck", "userInfo_Player"], [0], RATE, 100))
    logout(c)

    # --- «Назад, в долину»: the second level and the third ------------------------------------
    st = store()
    st.save_stats(CID, [("skill", SHOOTING, 2, 0, progression.skill_xp_max(2))])
    st.save_character_state(CID, level=2)
    st.close()
    c, _got, _call, _arr = login()
    here = inhabitants(goto(c, PIER), PIER)
    check("at the second level «Назад, в долину» is offered at Причал", status(c, BACK), 1)
    got, q = take(c, here, DEMIR_H, BACK)
    got = hand_in(c, here, DEMIR_H, q)
    call, arrival = moved(c, got)
    check("  ..and rides him back to the caravan's village", (acks(got)[:1], call.get("id")),
          ([0], VILLAGE))
    here = inhabitants(arrival, VILLAGE)
    got, q = take(c, here, DEMIR_V, TO_HALFA)
    got = hand_in(c, here, DEMIR_V, q)
    call, arrival = moved(c, got)
    check("  ..and «В Хальфу!» takes him to Причал again", (acks(got)[:1], call.get("id")),
          ([0], PIER))
    logout(c)
    st = store()
    st.save_stats(CID, [("skill", SHOOTING, 3, 0, progression.skill_xp_max(3))])
    st.save_character_state(CID, level=3)
    st.close()
    c, _got, call, arrival = login()
    check("at the third level, at Причал: «Назад, в долину» is offered no more",
          (call.get("id"), status(c, BACK)), (PIER, 0))
    logout(c)

    # --- names along the whole path -------------------------------------------------------------
    shown = {t: (MT.get(t, ("", "?"))[1], where) for t, where in SEEN.items()
             if names.ALL.get(t) in (None, MT.get(t, ("", None))[1])}
    check("nobody along the whole path stands by his mobs.xml name (%d types seen) but the"
          " remainder data/orig_names_manual.json lists under \"none\", each with its reason"
          % len(SEEN), sorted(t for t in shown if t not in REMAINDER), [])
    things = [ROUNDS, CERT, COIN] + GUNS + PARTS
    check("  ..nor does any thing the path hands out show its internal name",
          [t for t in things if names.text(items.STRING_ID_OFFSET + t) == items.catalogue()[t][1]],
          [])
except SystemExit:
    raise
except Exception:
    import traceback
    fails.append("the socket part broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

with open(LOG, encoding=ENC, errors="replace") as _fh:
    _log = _fh.read().splitlines()
bad = [line for line in _log if "Traceback" in line or "!!" in line]
check("the server logged no traceback", bad, [])
if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    print("\n--- server log tail ---\n" + "\n".join(_log[-60:]))
    sys.exit(1)
print("\nall passed")
