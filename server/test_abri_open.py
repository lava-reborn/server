"""Абри open (the owner's «Делаем Абри», 2026-10-12: «Открой у водителя на
вокзале квест поездку в Абри ... Там голду дают 6 (работорговцы) и 8
(живодеры), принимает также Мортимер в портовом рынке. Убери локации ...
Восстанови все квесты и все имена мобов ... Добавь каждому продавцу нужные
предметы ... Город должен быть полноценным игровым»; and «Также надо будет
восстановить локации: хижина Хаксли; автосвалки (2 штуки, непонятно зачем);
хиппи в пустыне; тотем - это пустоши»): a character of the town's band
walked from Вади-Хальфа's station to Абри and back on the real tables -- the
shipped data/quests.json with its companions, data/passages.json,
data/placements.json, data/schedule.json -- no knob of the suite's own but
the cheats that stand in for the walking and the earning.

  the ride    «Поездка в Абри» (273) at Хассир on the station (37): refused
              with no afro; the ticket home (6545) bought at his stall
              before leaving; for 100 afro an lcall to the Портовый рынок
              (187), Луиджи beside the arrival
  the market  everybody there by a name the client has; Мортимер with his
              ingots and his cashing, Луиджи with the two ways back
  the cut     stepped off the market onto the map and one cell south: the
              clothing craftsmen's quarter is wasteland; the other cells of
              the cut (the craftsmen, the ЦСЦ's air base, the set upgrade,
              the green mark, the second «Автосвалка», the clan base
              Liberty at Абри and at Абу-Хамед, the ФСЦ airfield, the clan
              base Blackwater's block post and its square) the same
  the hut     two cells east on the map: «Хижина Говарда Хаксли» opens his
              fields (261); «Планшет Хаксли» (564) and «Найти Мариса
              Дамбиса» (565) to Марис Дамбис in the desert (284); the corn
              harvested (478)
  the four    the places the owner named stand on their cells: the car dump
              (289), the Тотем (262), the hippies (191) of the town's band
  the dump    МакКэндлесс's tools bought, a junk pile searched (522): the
              tools back and the lead found
  the smelter the abandoned factory's door (290 b) into the smelter (766),
              the lead smelted (532), and its door back up (766 a)
  the mine    the lead mine's gate down (558) into the control room (662),
              its door to the first tier (1030) and back, the gate up (561)
  the gold    at six in the evening: Папаша Абу in the slave traders' camp
              (88) and Элфрид in the flayers' (92) shot, their bags 6 and 8
              ounces in ingots; at Мортимер's in the market every ingot
              cashed, 0.05 less each, the ledger a row a cashing; the ingot
              not sold for afro
  spending    a lottery ticket at the market (518), a coupon at Хаксли's
              bought with the ingots' gold and changed for rounds (492)
  the mafia   a P90 bought at the market's stall and handed to Вальдес, who
              waits in his car in the quarter (450); «В чем дело» from him to
              the mansion's door (451)
  home        «Проездной в Вади Хальфу» (280) at Луиджи with the ticket
              bought at the station: back at 37

Along the whole path nobody shows his mobs.xml name (the remainder
data/orig_names_manual.json lists under "none" included: none of it stands
in Абри), no thing the path hands out shows its internal name, every string
id of its quests is in the launcher's table, and the server logs no
traceback.

In process first: the four rides on in the shipped table with their ways at
both ends; and no trap -- from every place of Абри a player can get into,
and everything its doors, sides and quest ways open (the mines' gates and
tiers, the smelter, the mafia's rooms, the Amazon's), some way of doors,
sides and quest ways leads back to a place on a map cell.

    LAVA_RES=.../lava/res python3 server/test_abri_open.py
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
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK", "LAVA_START", "LAVA_START_AFRO", "LAVA_SCHEDULE",
              "LAVA_GX", "LAVA_GY", "LAVA_LOC", "LAVA_ENCOUNTER_CHANCE"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import names  # noqa: E402  (first: the level its mobs' names carry is rewritten at import)
import accounts  # noqa: E402
import bosses  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

# The places.
STATION, PORT, FIELDS, MARIS, DUMP, FACTORY, SMELTER = 37, 187, 261, 284, 289, 290, 766
TOTEM, HIPPIES, LEAD_MOUTH, LEAD_CONTROL, LEAD_TIER = 262, 191, 205, 662, 1030
CAMP_ST, CAMP_ZD = 88, 92
# The places of Абри a player walks into from the map: the town, the camps
# and their chiefs', the quest places and the works (DESIGN 7.2); the island
# (434, 502, 513, 523) has no boat. The clothing market 378 is cut (the
# owner's «и ещё убери локацию торговцы одеждой в Абри», 2026-10-12).
ABRI = [76, 88, 89, 90, 92, 187, 188, 189, 191, 203, 204, 205, 206, 207, 219, 220, 251, 252,
        255, 256, 261, 262, 283, 284, 285, 289, 290, 368]
# ..and the interiors their doors, sides and quest ways open (the smelter's
# assembly shop 1055 is cut, and no door leads on to it).
INTERIORS = [192, 193, 660, 661, 662, 671, 672, 766, 1028, 1029, 1030, 1221, 1222, 1223]
# The cuts of 2026-10-12: cell -> what stood there (the clothing market 378
# by the owner's «и ещё убери локацию торговцы одеждой в Абри»).
CUT = {(5860, 1836): "Ремесленники по одежде 10 (453)",
       (5861, 1836): "Ремесленники по одежде 10 (454)",
       (5860, 1837): "Ремесленники по одежде 11 (458)",
       (5863, 1837): "Ремесленники по одежде 12 (459)",
       (5866, 1836): "Авиабаза ЦСЦ (427)", (5866, 1837): "Улучшение сетов 10-12",
       (5862, 1837): "the green mark", (5863, 1836): "the second «Автосвалка»",
       (5906, 1888): "Кланбаза Liberty (328)", (5906, 1889): "Плешь смерти (327)",
       (6248, 1979): "Кланбаза Liberty by Абу-Хамед",
       (5865, 1835): "Аэроплощадка ФСЦ (529)", (5924, 1838): "Блок-пост Blackwater (317)",
       (5923, 1838): "Blackwater's square", (5865, 1836): "Торговцы одеждой (378)"}
CUT_FILES = [453, 454, 458, 459, 427, 450, 328, 327, 529, 317, 1055, 378]
# The places the owner's follow-up named: cell -> file.
FOUR = {(5862, 1836): FIELDS, (5863, 1835): DUMP, (5864, 1838): TOTEM, (5860, 1838): HIPPIES}
# The quests.
RIDE, RIDE_BACK, TICKET_RIDE, TICKET_BACK = 273, 274, 279, 280
PAD, FIND_MARIS, HARVEST, SEARCH_LEAD, SMELT_LEAD = 564, 565, 478, 522, 532
GATE_DOWN, GATE_UP, COUPON_EK, LOTTERY = 558, 561, 492, 518
REVENGE, WHATS_UP = 450, 451                    # the mafia's first two: the P90, the door
CASH = {7620: 301, 4796: 302, 4797: 303}
PATH = [RIDE, RIDE_BACK, TICKET_RIDE, TICKET_BACK, PAD, FIND_MARIS, HARVEST, SEARCH_LEAD,
        SMELT_LEAD, GATE_DOWN, GATE_UP, COUPON_EK, LOTTERY, REVENGE, WHATS_UP]
PATH += sorted(CASH.values())
# The people.
HASSIR, LUIGI, MORTIMER, LOTTERY_MAN = 105, 1179, 1188, 1172
HUXLEY, CORN, MARIS_D, MCCANDLESS, PILE_LEAD, SMELT = 5766, 1682, 2193, 2390, 2367, 2393
GATE_IN, GATE_OUT, TOTEM_POLE = 1321, 1333, 1686
HIPPIE_KINDS = (1175, 1176, 5631)
ABU, ELFRID = 327, 360
QUARTER, VALDES, MANSION_DOOR, SMG_STALL = 188, 1415, 1394, 1163     # Вальдес: his car
# The things.
TICKET_HOME, PAD_OBJ, COB, LEAD, LEAD_INGOT = 6545, 5733, 3916, 7043, 7089
TOOLS = (7025, 7026, 7027)                      # «Признаки свинца»: lamp, hammer, tin
COUPON, EK_ROUNDS, LOT_TICKET, P90 = 6294, 6152, 2646, 25485
I1, I5, I10 = 7620, 4796, 4797
INGOTS = (I1, I5, I10)
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
OUNCE = progression.GOLD_OUNCE
MT = world.mob_types()
with open(os.path.join(ROOT, "data", "orig_names_manual.json"), encoding=ENC) as _fh:
    REMAINDER = {int(k) for k in json.load(_fh)["none"]}


def reached_from(start):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way."""
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
        targets += [r.get("target_loc_id") for r in (sides.get(str(lid)) or {}).values()
                    if isinstance(r, dict)]
        for t in targets:
            if t and int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    return seen


def on_map(lid):
    """A place on a map cell, or one whose own file leads out over a side
    onto the map (an interior keeps the cell it was entered from)."""
    if world.cell_of(lid) is not None:
        return True
    if travel.no_map(lid):
        return False
    with open(travel.passages_path(), encoding=ENC) as fh:
        inner = (json.load(fh).get("sides") or {}).get(str(lid)) or {}
    return any(s in travel.SIDES and s not in inner
               for s in set(travel.exit_sides(world.location(lid)).values()))


# --- in process ------------------------------------------------------------------------
try:
    rides = {t: (quests.get(t).give, quests.get(t).take, quests.get(t).repeatable)
             for t in (RIDE, TICKET_RIDE, RIDE_BACK, TICKET_BACK)}
    check("the four rides are on in the shipped table: Хассир gives and takes the two to Абри,"
          " Луиджи the two back, each repeatable",
          rides, {RIDE: ([HASSIR], [HASSIR], 1), TICKET_RIDE: ([HASSIR], [HASSIR], 1),
                  RIDE_BACK: ([LUIGI], [LUIGI], 1), TICKET_BACK: ([LUIGI], [LUIGI], 1)})
    check("  ..their ways in data/passages.json: from the station to the port market and back",
          {t: int((travel.quest_way(world.location(frm), t) or {}).get("target_loc_id", 0))
           for t, frm in ((RIDE, STATION), (TICKET_RIDE, STATION), (RIDE_BACK, PORT),
                          (TICKET_BACK, PORT))},
          {RIDE: PORT, TICKET_RIDE: PORT, RIDE_BACK: STATION, TICKET_BACK: STATION})
    check("every string id of the path's quests is in the launcher's table",
          [t for t in PATH if not all(names.known(i) for i in quests.get(t).string_ids())], [])
    check("the places of Абри the path starts from all stand on map cells",
          [lid for lid in ABRI if world.cell_of(lid) is None], [])
    closure = reached_from(set(ABRI))
    check("their doors, sides and quest ways open the mines' control rooms and tiers, the"
          " smelter and its workshop, the mafia's rooms and the Amazon's",
          [lid for lid in INTERIORS if lid not in closure], [])
    traps = sorted(lid for lid in closure - set(ABRI)
                   if not any(on_map(p) for p in reached_from({lid})))
    check("no trap: from every place of them (%d) a way of doors, sides and quest ways leads"
          " back to a place on the map" % len(closure), traps, [])
    check("  ..and none of them is a place of the cut",
          sorted(set(CUT_FILES) & closure), [])
    check("the four places the owner named stand on their cells",
          {c: world.location_at(*c) for c in FOUR}, FOUR)
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server -------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT_NO = free_port()
DB = os.path.join(tempfile.mkdtemp(), "abri_open.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("traveller", "secret")
_store.close()
CRED = accounts.credential("traveller", "secret")
STATION_CELL = world.cell_of(STATION)
# A newcomer wakes on the station's cell of Вади-Хальфа (LAVA_GX/LAVA_GY), with
# no afro of his own; the clock is at six in the evening, in the bosses' hour;
# the map's packs stay home (the cut's cells are the town's ground anyway).
# The cheats stand in for the walking between places and the earning; the
# admin gun for the camps' fights.
env = dict(os.environ, LAVA_PORT=str(PORT_NO), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(STATION_CELL[0]), LAVA_GY=str(STATION_CELL[1]),
           LAVA_START_AFRO="0", LAVA_AP_REGEN="50", LAVA_RESPAWN="600", LAVA_SEED="12",
           LAVA_LEAVE_COMBAT="2", LAVA_POLICY_PORT="0", LAVA_ENCOUNTER_CHANCE="0",
           LAVA_BOSS_CLOCK="2026-10-12T18:00:05")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


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


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(eid):
    return "x1%08x" % eid


# Every creature the client was shown on the way: type -> the place first seen.
SEEN = {}


def inhabitants(frames, where=None):
    """type id -> [entity id] of the userInfo* frames of an arrival (and a
    note of each type for the check of names at the end)."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    for t in out:
        SEEN.setdefault(t, where)
    return out


def infos(frames):
    """type id -> (frame name, params) of the first userInfo* of each type."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], (n, p))
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, *where):
    """/goto a place by id, or the place on a map cell by x y: (lcall id,
    the arrival's frames)."""
    c.send("userMsg;entry=@/goto %s@;group=0;" % " ".join(str(w) for w in where))
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    arrival = arrive(c)
    inhabitants(arrival, call.get("id"))
    return call.get("id"), arrival


def cheat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)
    return c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)


def give(c, type_id, n=1):
    got = cheat(c, "/give %d %d" % (type_id, n))
    new = named(got, "ss_obj_status")
    return str(new[0]["obj"]) if new else None


def to_map(c):
    c.send("chWorld;")
    return c.until(lambda f: f[0] == "gmap", 3)


def walk_map(c, dx, dy):
    """One leg on the map, dx and dy in cells: the frames up to the stop."""
    c.send("moveTo;dx=%d;dy=%d;" % (round(dx * 100), round(dy * 100)))
    return c.until(lambda f: f[0] == "userMove" and f[1].get("id") == 0
                   and f[1].get("vx") == 0, 30)


def enter_cell(c):
    """chWorld from the map: into whatever stands on the cell under the
    player -- (lcall id, the arrival's frames)."""
    c.send("chWorld;")
    call = first(c.until(lambda f: f[0] == "lcall", 5), "lcall")
    arrival = arrive(c) if call else []
    inhabitants(arrival, call.get("id"))
    return call.get("id"), arrival


def take(c, here, npc_type, qtype):
    npc = here.get(npc_type, [0])[0]
    offered = quests.given_by(npc_type)
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, offered.index(qtype) if qtype in offered else 99))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id, obj_idx=0, wait=1.0):
    npc = here.get(npc_type, [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def moved(c, got, wait=8):
    """The lcall a way's hand-in (or a door) is followed by, and the
    arrival's frames: (lcall id, arrival)."""
    call = first(got, "lcall") or first(c.until(lambda f: f[0] == "lcall", wait), "lcall")
    arrival = arrive(c) if call else []
    inhabitants(arrival, call.get("id"))
    return call.get("id"), arrival


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def store():
    return accounts.Store(DB)


def held(cid):
    """type id -> pieces the character has, wherever."""
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


def ledger(cid):
    st = store()
    got = st.ledger(cid)
    st.close()
    return got


def learned(cid):
    st = store()
    ch = progression.Character.load(st, cid)
    st.close()
    return [tuple(s[:2]) for s in ch.spec]


def open_stall(c, here, trader):
    """The trader's window (getInfo) and the stall opened on it: (its list,
    the ack)."""
    npc = here.get(trader, [0])[0]
    c.send("getInfo;lvl=0;id=%d;type=0;" % npc)
    window = first(c.until(lambda f: f[0] == "userInfo_Trader"), "userInfo_Trader")
    stall = window.get("type_list")
    stall = list(stall) if isinstance(stall, list) else ([] if stall in (None, "") else [stall])
    c.send("ss_create;s_type=1;target=%d;" % npc)
    return stall, acks(c.frames())


def buy(c, cid, stall, t, gold=False, n=1):
    """One purchase off the open stall: (acks, pieces of t that came, afro and
    gold spent)."""
    before, had = money(cid), held(cid)[t]
    code = inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY
    c.send("ss_upd;s_status=%d;obj=x%x;param=%d;" % (code, stall.index(t), n))
    got = c.frames(0.8)
    after = money(cid)
    return acks(got), held(cid)[t] - had, before[0] - after[0], before[1] - after[1]


def close_stall(c):
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)


def wield(c, thing):
    c.send("ss_get;target=0;slot=11;")
    held_ = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held_) > 6 and held_[6] not in ("0", thing):
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held_[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % thing)
    return acks(c.frames())


def shoot(c, gun, target, tries=40):
    """Fire the admin gun at an entity until it falls: the frames of its
    death, or None."""
    for _ in range(tries):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(target)))
        got = c.until(lambda f: f[0] == "ss_di_firearm"
                      or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.3)
        if [p for p in named(got, "lch") if p.get("dead") == target]:
            return got
        time.sleep(0.5)
    return None


def walk_to(c, loc, pos, goal, avoid=()):
    """A real path inside a location to a goal cell (or the nearest cell of a
    set), sent as the client sends it: the cell the walk ends on."""
    goals = goal if isinstance(goal, (set, frozenset, list, tuple)) else {goal}
    path = mobs.find_path(loc, pos, lambda cell: cell in goals, set(avoid), limit=20000)
    if not path:
        # No way round whoever stands between: the goal cell alone, which the
        # server takes (it checks a path against the grid only), as
        # test_halfa_open's hunt does -- a stand-in for the walk round a camp.
        path = [min(goals, key=lambda cell: mobs.hex_distance(cell, pos, loc.width))]
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    c.frames(0.3 + 0.25 * len(path))
    return path[-1]


def through_door(c, loc_id, side, pos):
    """Walk onto door a or b of a location and press «в другую локацию»
    (chWorld;to=1): (ack, lcall id, arrival)."""
    loc = world.location(loc_id)
    cells = {cell for cell, s in travel.exit_sides(loc).items()
             if s == side and cell not in loc.obstacles}
    walk_to(c, loc, pos, cells)
    c.send("chWorld;to=1;")
    got = c.until(lambda f: f[0] == "lcall", 4)
    lid, arrival = moved(c, got)
    return acks(got)[:1], lid, arrival


def boss_bag(c, gun, where, boss):
    """Into a camp in the boss's hour: shoot him from a cell out of every
    other fighter's reach, shoot whoever would see the player at his bag,
    walk to the bag and take it whole -- (fell?, the ingots taken {type:
    pieces})."""
    lid, arrival = goto(c, where)
    place = world.location(where)
    W = place.width
    pos = first(arrival, "lenter").get("pos")
    ents = {p["id"]: p["name"] for p in named(arrival, "userInfo")}
    placed = {p["newUser"]: p["pos"] for p in named(arrival, "lch")
              if "newUser" in p and p["newUser"] in ents}
    bosses_ = [i for i, t in ents.items() if t == boss]
    if not bosses_:
        return False, {}
    me = bosses_[0]
    home = placed[me]
    fighters = {i: cell for i, cell in placed.items() if i != me and mobs.stats(ents[i]).aggro}
    wary = max([mobs.stats(ents[i]).aggro for i in fighters] or [0]) + 0.5
    reach = mobs.stats(boss).aggro
    spots = sorted((mobs.hex_distance(cell, home, W), cell)
                   for cell in range(W * place.height)
                   if cell not in place.obstacles and cell not in placed.values()
                   and reach + 0.5 < mobs.hex_distance(cell, home, W) <= 14
                   and mobs.line_of_fire(place, cell, home) is None
                   and all(mobs.hex_distance(cell, o, W) > wary for o in fighters.values()))
    if not spots:
        return False, {}
    wary_cells = {cell for cell in range(W * place.height)
                  if any(mobs.hex_distance(cell, o, W) <= wary for o in fighters.values())}
    pos = walk_to(c, place, pos, spots[0][1], wary_cells)
    dead = shoot(c, gun, me)
    if dead is None:
        return False, {}
    got = list(dead)
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    bag_at = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    if not bag_at:
        return True, {}
    now = dict(fighters)
    for n, p in c.seen:
        if n == "userMove" and p.get("id") in now:
            now[p["id"]] = p["path"][-1]
    near = [i for i, cell in now.items() if mobs.hex_distance(cell, bag_at[0], W) <= wary + 1]
    downed = [i for i in near if shoot(c, gun, i, 10) is not None]
    now = {i: cell for i, cell in now.items() if i not in downed}
    for n, p in c.seen:
        if n == "userMove" and p.get("id") in now:
            now[p["id"]] = p["path"][-1]
    wary_cells = {cell for cell in range(W * place.height)
                  if any(mobs.hex_distance(cell, o, W) <= wary for o in now.values())}
    path = mobs.find_path(place, pos, lambda cell: cell == bag_at[0] or progression.within_reach(
        cell, bag_at[0], W, place.height), wary_cells) or [bag_at[0]]
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    c.frames(0.25 * len(path) + 1.0)
    c.send("ss_create;s_type=0;target=%d;" % bag_at[0])
    if acks(c.frames()) != [0]:
        return True, {}
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    oids = [inventory.parse_oid(o) for o in lst[lst.index("0") + 1:]] if "0" in lst else []
    st = store()
    stacks = collections.Counter()
    for u, t, _r in oids:
        if t in INGOTS:
            stacks[t] += st.item(u)["count"]
    st.close()
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return True, dict(stacks)


def ounces(bag):
    return sum(items.GOLD_INGOTS[t] * n for t, n in bag.items()) // OUNCE


try:
    # --- the station of Вади-Хальфа: the ride ------------------------------------------
    c = Client(testkit.connect(PORT_NO, srv, LOG))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Traveller@;")
    c.frames()
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.3)
    st = store()
    CID = st.character_by_name("Traveller")["id"]
    # The town's band 8-12: a character of the tenth level (the mines' gates
    # want 8-12, the lottery's ticket [10] 9-10) who has learned Переработка,
    # which the smelter pays into (a specialisation not learned takes none).
    RECYCLING = quests.SPEC_KEYS["recycling"]
    st.save_stats(CID, [("skill", progression.SHOOTING, 10, 0, progression.skill_xp_max(10)),
                        ("spec", RECYCLING, 0, 0, progression.SPEC_XP_START)])
    st.save_character_state(CID, level=10)
    st.close()
    SPEC0 = learned(CID)
    c = Client(testkit.connect(PORT_NO, srv, LOG))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("selPers;num=0;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    arrival = arrive(c)
    here = inhabitants(arrival, call.get("id"))
    check("a character of the tenth level wakes at Вади-Хальфа's station, Хассир there, with"
          " no afro", (call.get("id"), HASSIR in here, money(CID)[0]), (STATION, True, 0))
    check("  ..offered «Поездка в Абри» and «Проездной в Абри»",
          [status(c, t) for t in (RIDE, TICKET_RIDE)], [1, 1])
    took, q_ride = take(c, here, HASSIR, RIDE)
    refused = hand_in(c, here, HASSIR, q_ride)
    check("«Поездка в Абри» taken; with no afro the hand-in is refused and nobody moves",
          (acks(took), acks(refused)[:1] != [0], bool(named(refused, "lcall"))),
          ([0], True, False))
    cheat(c, "/money 250 0")
    stall, opened = open_stall(c, here, HASSIR)
    check("Хассир's stall: the ticket to Абри and the ticket home, the way back bought before"
          " leaving -- «Билет в Вади Хальфу» for 150 afro",
          (stall, opened, buy(c, CID, stall, TICKET_HOME)),
          ([6544, TICKET_HOME], [0], ([0], 1, 150, 0)))
    close_stall(c)
    went = hand_in(c, here, HASSIR, q_ride)
    lid, arrival = moved(c, went)
    here = inhabitants(arrival, lid)
    check("  ..with 100 afro: handed in, the fare gone, and an lcall to the Портовый рынок of"
          " Абри", (acks(went)[:1], money(CID)[0], lid), ([0], 0, PORT))

    # --- the port market ----------------------------------------------------------------
    shown = infos(arrival)
    check("the port market as the client is shown it: Луиджи with the two ways back, Мортимер"
          " with the three ingots and his cashing, the lottery men, Ведич, Одноухий",
          (shown.get(LUIGI, ("", {}))[1].get("give_quests"),
           shown.get(MORTIMER, ("", {}))[1].get("type_list"),
           shown.get(MORTIMER, ("", {}))[1].get("give_quests"),
           [t in here for t in (LOTTERY_MAN, 1171, 1174, 1164)]),
          ([RIDE_BACK, TICKET_BACK], list(INGOTS), list(range(301, 308)), [True] * 4))
    check("  ..arrived beside Луиджи's way back",
          first(arrival, "lenter").get("pos") == travel.door_arrival(world.location(PORT), STATION),
          True)
    check("  ..everybody there by a name the client has, none by his mobs.xml name",
          sorted(t for t in here if not names.known(t) or names.ALL.get(t) == MT[t][1]), [])

    # --- the cut: walked off the market ------------------------------------------------
    got = to_map(c)
    check("out of the market onto the map: on its cell, 5860,1835",
          [(p.get("x"), p.get("y")) for p in named(got, "gmap")], [world.cell_of(PORT)])
    walked = walk_map(c, 0.5, 1.5)
    lid, arrival = enter_cell(c)
    gone = {t for f in CUT_FILES for _c, t in world.location(f).spawns if t}
    check("a cell south, where «Ремесленники по одежде 10 уровень» stood: the wasteland of the"
          " cell, nobody of the cut's places in it",
          (bool(named(walked, "userMove")), lid, sorted(set(inhabitants(arrival)) & gone)),
          (True, world.pack(5860, 1836), []))
    to_map(c)
    walk_map(c, 2.5, 0.5)
    lid, arrival = enter_cell(c)
    here = inhabitants(arrival, lid)
    check("two cells east, «Хижина Говарда Хаксли»: his fields (261), Хаксли and the corn",
          (lid, HUXLEY in here, len(here.get(CORN, []))), (FIELDS, True, 13))
    other_cut = {}
    for cell in CUT:
        if cell == (5860, 1836):
            continue
        lid, arrival = goto(c, *cell)
        other_cut[cell] = (lid == world.pack(*cell), sorted(set(inhabitants(arrival)) & gone))
    check("every other cell of the cut opens its wasteland, nobody of the cut's places there:"
          " %s" % ", ".join(CUT[cell] for cell in sorted(other_cut)),
          other_cut, {cell: (True, []) for cell in other_cut})

    # --- Хаксли's fields ----------------------------------------------------------------
    lid, arrival = goto(c, 5862, 1836)
    here = inhabitants(arrival, lid)
    got, q = take(c, here, HUXLEY, PAD)
    done = hand_in(c, here, HUXLEY, q)
    check("«Планшет Хаксли» (564): a talk with Хаксли, and his pad in the bag",
          (acks(got), acks(done)[:1], held(CID)[PAD_OBJ]), ([0], [0], 1))
    got, q_maris = take(c, here, HUXLEY, FIND_MARIS)
    check("  ..«Найти Мариса Дамбиса» (565) taken", acks(got), [0])
    got, q = take(c, here, CORN, HARVEST)
    done = hand_in(c, here, CORN, q)
    check("«Собрать урожай» (478) at a corn plant: two cobs",
          (acks(got), acks(done)[:1], held(CID)[COB]), ([0], [0], 2))
    lid, arrival = goto(c, 5900, 1832)
    here = inhabitants(arrival, lid)
    done = hand_in(c, here, MARIS_D, q_maris)
    check("  ..and handed in to Марис Дамбис in the desert (5900,1832, place 284)",
          (lid, MARIS_D in here, acks(done)[:1]), (MARIS, True, [0]))

    # --- the four places of the owner's word ----------------------------------------------
    lid, arrival = goto(c, 5864, 1838)
    here = inhabitants(arrival, lid)
    check("«Тотем» (5864,1838): the totem pole of Q_Abri_Totem, its skull, the sick and hungry"
          " hyenas", (lid, TOTEM_POLE in here, 2101 in here, len(here.get(1675, [])),
                      len(here.get(1676, []))), (TOTEM, True, True, 4, 4))
    lid, arrival = goto(c, 5860, 1838)
    here = inhabitants(arrival, lid)
    check("«Хиппи в пустыне» (5860,1838): twelve hippies of the town's band, 9-11",
          (lid, sum(len(here.get(t, [])) for t in HIPPIE_KINDS),
           sorted({mobs.stats(t).level for t in here if t in HIPPIE_KINDS})),
          (HIPPIES, 12, [9, 10, 11]))
    lid, arrival = goto(c, 5863, 1835)
    here = inhabitants(arrival, lid)
    check("«Автосвалка» (5863,1835): the car dump, МакКэндлесс and the eight junk piles",
          (lid, MCCANDLESS in here, sorted(t for t in range(2367, 2375) if t in here)),
          (DUMP, True, list(range(2367, 2375))))

    # --- the dump: tools bought, a pile searched -------------------------------------------
    GUN = give(c, ADMIN_GUN)
    rounds = give(c, GUN_ROUNDS, 99)
    wield(c, GUN)
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, GUN))
    c.until(lambda f: f[0] == "ss_di_firearm")
    cheat(c, "/money 3000 0")
    stall, opened = open_stall(c, here, MCCANDLESS)
    bought = [buy(c, CID, stall, t) for t in TOOLS]
    close_stall(c)
    check("МакКэндлесс's stall: «Все по 100 афро» -- the lamp, the geologist's hammer and the"
          " tin for 100 afro each", (opened, bought), ([0], [([0], 1, 100, 0)] * 3))
    got, q = take(c, here, PILE_LEAD, SEARCH_LEAD)
    done = hand_in(c, here, PILE_LEAD, q)
    have = held(CID)
    check("«Признаки свинца» (522) at a junk pile: the tools back, the battery's lead found",
          (acks(got), acks(done)[:1], [have[t] for t in TOOLS], have[LEAD]),
          ([0], [0], [1, 1, 1], 1))

    # --- the smelter: down from the abandoned factory and back up ---------------------------
    lid, arrival = goto(c, 5864, 1835)
    check("«Заброшенный завод» (5864,1835)", lid, FACTORY)
    ack, lid, arrival = through_door(c, FACTORY, "b", first(arrival, "lenter").get("pos"))
    here = inhabitants(arrival, lid)
    check("  ..its door b leads down into the smelter (766), the machines there",
          (ack, lid, SMELT in here), ([0], SMELTER, True))
    afro0 = money(CID)[0]
    got, q = take(c, here, SMELT, SMELT_LEAD)
    done = hand_in(c, here, SMELT, q)
    have = held(CID)
    check("«Выплавка свинца.» (532): the lead in, an ingot of it out, 100 afro (the +40 of"
          " Переработка is read off the saved character at the end)",
          (acks(got), acks(done)[:1], have[LEAD], have[LEAD_INGOT], afro0 - money(CID)[0]),
          ([0], [0], 0, 1, 100))
    ack, lid, arrival = through_door(c, SMELTER, "a", first(arrival, "lenter").get("pos"))
    check("  ..and its door a leads back up into the factory: no dead end",
          (ack, lid), ([0], FACTORY))

    # --- the lead mine: the gates and a tier ------------------------------------------------
    lid, arrival = goto(c, 5889, 1825)
    here = inhabitants(arrival, lid)
    got, q = take(c, here, GATE_IN, GATE_DOWN)
    went = hand_in(c, here, GATE_IN, q)
    lid, arrival = moved(c, went)
    here = inhabitants(arrival, lid)
    check("the lead mine's mouth (5889,1825): «Спуститься в шахту» (558) for the band 8-12,"
          " into the control room (662)", (acks(got), acks(went)[:1], lid, GATE_OUT in here),
          ([0], [0], LEAD_CONTROL, True))
    ack, lid, tier = through_door(c, LEAD_CONTROL, "b", first(arrival, "lenter").get("pos"))
    check("  ..its door b to the first tier (1030), the lead ore standing there",
          (ack, lid, 1309 in inhabitants(tier, lid)), ([0], LEAD_TIER, True))
    ack, lid, arrival = through_door(c, LEAD_TIER, "a", first(tier, "lenter").get("pos"))
    here = inhabitants(arrival, lid)
    check("  ..the tier's door a (its EXIT sign) back to the control room", (ack, lid),
          ([0], LEAD_CONTROL))
    got, q = take(c, here, GATE_OUT, GATE_UP)
    went = hand_in(c, here, GATE_OUT, q)
    lid, arrival = moved(c, went)
    check("  ..«Выйти из шахты» (561) up to the mouth", (acks(got), acks(went)[:1], lid),
          ([0], [0], LEAD_MOUTH))

    # --- the gold: the camps at six ------------------------------------------------------
    fell, bag_abu = boss_bag(c, GUN, CAMP_ST, ABU)
    check("at six Папаша Абу in the slave traders' camp (88) falls; his bag: an ingot of five and"
          " one of one, 6 ounces", (fell, bag_abu, ounces(bag_abu)), (True, {I5: 1, I1: 1}, 6))
    fell, bag_elfrid = boss_bag(c, GUN, CAMP_ZD, ELFRID)
    check("  ..Элфрид in the flayers' camp (92) falls; his bag: an ingot of five and three of one,"
          " 8 ounces", (fell, bag_elfrid, ounces(bag_elfrid)), (True, {I5: 1, I1: 3}, 8))
    have = held(CID)
    check("  ..14 ounces in ingots in the bag", {t: have[t] for t in INGOTS},
          {I1: 4, I5: 2, I10: 0})

    # --- Мортимер in the port market ------------------------------------------------------
    lid, arrival = goto(c, PORT)
    here = inhabitants(arrival, lid)
    stall, opened = open_stall(c, here, MORTIMER)
    check("Мортимер's stall in the port market: the ingots for gold at face value, never for"
          " afro", (stall, opened, buy(c, CID, stall, I1)), (list(INGOTS), [0],
                                                             ([inventory.RES_REFUSED], 0, 0, 0)))
    close_stall(c)
    purse0, cashed = money(CID), []
    for t in [I5, I5, I1, I1, I1, I1]:
        before = money(CID)
        got, q = take(c, here, MORTIMER, CASH[t])
        done = hand_in(c, here, MORTIMER, q)
        cashed.append((CASH[t], acks(got) + acks(done)[:1], money(CID)[1] - before[1]))
    check("every ingot cashed at his: «Обналичить 5 унций» twice, «Обналичить 1 унцию» four times,"
          " 0.05 less each", cashed, [(302, [0, 0], 495)] * 2 + [(301, [0, 0], 95)] * 4)
    check("  ..14 ounces of loot made 13.70 on the account, no afro, the ingots gone",
          (money(CID)[1] - purse0[1], money(CID)[0] - purse0[0],
           [held(CID)[t] for t in INGOTS]), (1370, 0, [0, 0, 0]))
    rows = [(r["source"], r["ref"], r["gold"]) for r in ledger(CID) if r["source"] == "quest"
            and r["ref"] in CASH.values()]
    check("  ..the ledger: a row for each cashing under its quest",
          sorted(rows), sorted([("quest", 302, 495)] * 2 + [("quest", 301, 95)] * 4))

    # --- spending: a lottery ticket and a coupon --------------------------------------------
    stall, opened = open_stall(c, here, LOTTERY_MAN)
    check("the lottery man's stall: «Лотерейный билет [10]» for 1000 afro",
          (opened, buy(c, CID, stall, LOT_TICKET)), ([0], ([0], 1, 1000, 0)))
    close_stall(c)
    before = held(CID)
    got, q = take(c, here, LOTTERY_MAN, LOTTERY)
    done = hand_in(c, here, LOTTERY_MAN, q)
    after = held(CID)
    prizes = {o for o, _n, _w in quests.get(LOTTERY).rew_random}
    check("  ..«Лотерея Абри (9-10)» (518): the ticket gone, one of the draw's prizes in the bag",
          (acks(got), acks(done)[:1], after[LOT_TICKET],
           len([t for t in prizes if after[t] > before[t]])), ([0], [0], 0, 1))
    lid, arrival = goto(c, FIELDS)
    here = inhabitants(arrival, lid)
    stall, opened = open_stall(c, here, HUXLEY)
    check("Хаксли's stall: «Купон на 20 патронов» for 0.1 ounce of the ingots' gold; for afro"
          " refused", (opened, buy(c, CID, stall, COUPON, gold=True), buy(c, CID, stall, COUPON)),
          ([0], ([0], 1, 0, 10), ([inventory.RES_REFUSED], 0, 0, 0)))
    close_stall(c)
    got, q = take(c, here, HUXLEY, COUPON_EK)
    done = hand_in(c, here, HUXLEY, q, obj_idx=0)
    check("  ..«20 патронов (ЭК) за купон» (492): the coupon in, twenty gold rounds out",
          (acks(got), acks(done)[:1], held(CID)[COUPON], held(CID)[EK_ROUNDS]), ([0], [0], 0, 20))

    # --- the mafia: the P90 and the mansion's door ---------------------------------------
    lid, arrival = goto(c, PORT)
    here = inhabitants(arrival, lid)
    cheat(c, "/money 32500 0")
    stall, opened = open_stall(c, here, SMG_STALL)
    p90 = buy(c, CID, stall, P90)
    close_stall(c)
    check("the port market's «Пистолет-пулеметы и патроны»: a P90 for 32 500 afro",
          (opened, p90), ([0], ([0], 1, 32500, 0)))
    lid, arrival = goto(c, QUARTER)
    here = inhabitants(arrival, lid)
    afro0 = money(CID)[0]
    got, q = take(c, here, VALDES, REVENGE)
    done = hand_in(c, here, VALDES, q)
    check("«Оружие возмездия» (450) at Вальдес's car in the quarter (188): the P90 in,"
          " 15 000 afro out", (lid, acks(got), acks(done)[:1], held(CID)[P90],
                               money(CID)[0] - afro0), (QUARTER, [0], [0], 0, 15000))
    got, q = take(c, here, VALDES, WHATS_UP)
    done = hand_in(c, here, MANSION_DOOR, q)
    check("  ..«В чем дело» (451) from him, handed in at the mansion's door",
          (acks(got), acks(done)[:1]), ([0], [0]))

    # --- home: the ticket bought at the station ---------------------------------------------
    lid, arrival = goto(c, PORT)
    here = inhabitants(arrival, lid)
    afro0 = money(CID)[0]
    got, q = take(c, here, LUIGI, TICKET_BACK)
    went = hand_in(c, here, LUIGI, q)
    lid, arrival = moved(c, went)
    check("«Проездной в Вади Хальфу» (280) at Луиджи: the ticket from Хассир's stall taken, no"
          " afro, and back at the station of Вади-Хальфа",
          (acks(got), acks(went)[:1], held(CID)[TICKET_HOME], money(CID)[0] - afro0, lid,
           HASSIR in inhabitants(arrival, lid)), ([0], [0], 0, 0, STATION, True))
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)
    check("the smelter's one run, saved with the character: +40 Переработка",
          (SPEC0[RECYCLING], learned(CID)[RECYCLING]), ((0, 0), (0, 40)))

    # --- names along the whole path -----------------------------------------------------
    shown = {t: (MT.get(t, ("", "?"))[1], where) for t, where in SEEN.items()
             if names.ALL.get(t) in (None, MT.get(t, ("", None))[1])}
    check("nobody along the whole path stands by his mobs.xml name (%d types seen), the remainder"
          " data/orig_names_manual.json lists under \"none\" included (%d types, none of them"
          " Абри's since its ФСЦ airfield went)" % (len(SEEN), len(REMAINDER)), sorted(shown), [])
    things = [TICKET_HOME, PAD_OBJ, COB, LEAD, LEAD_INGOT, COUPON, EK_ROUNDS, LOT_TICKET, P90]
    things += list(TOOLS) + list(INGOTS)
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
print("\nabri open OK")
