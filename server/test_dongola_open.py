"""Донгола open (the owner's «и потом сделай донголу тоже», 2026-10-13 --
Донгола the way Абри was made the day before, whose order said «Открой у
водителя на вокзале квест поездку в Абри ... Там голду дают ... принимает
также Мортимер ... Убери локации ... Восстанови все квесты и все имена мобов
... Добавь каждому продавцу нужные предметы ... Город должен быть
полноценным игровым»; then «делай как считаешь нужным»): a character of the
town's band 12-16 rides in from Вади-Хальфа and from Абри and back on the real
tables -- the shipped data/quests.json with its companions, data/passages.json,
data/placements.json, data/camp_fill.json, data/schedule.json,
data/loot_manual.json -- no knob of the suite's own but the cheats that stand
in for the walking and the earning.

  the ride     «Поездка в Донголу» (630) at Хассир on Вади-Хальфа's station
               (37): refused with no afro; «Амин» (638) heard out at Расул in
               the quarter (36) for 500 afro and its second part (639) taken;
               with the fare an lcall to Донгола's station (49), beside
               Нур-ад-Дин's way back, where Тахир takes «Амин (часть 2)»
  the station  everybody there by a name the client has; Нур-ад-Дин with his
               four rows and the ticket to Абри
  the cut      stepped off the station onto the map and walked to the ФСЦ
               airfield's cell (5879,2011): wasteland; the clothing craftsmen
               (455, 460, 518), the clothing market (469) and Delta Force's
               block post (382) the same
  restored     Мастер Люшера Вельс's house (147) and the dump (1042) on
               their cells, their people there
  the markets  the old market (50), the new (197), the quarter (79) and the
               black market (103): everybody by a name the client has
  catacombs    «Возможная опасность» (695) from the Техномастер to агент
               Фарис, «Вход в катакомбы» (696) on to Тариф, the envelope bought
               at his stall for 30 000, «Перед входом» (697): the envelope
               shown and handed back, down into the sewers (607), whose map
               button is grey; «Старый бродяга» (702) there and «На свежий
               воздух» (705) up to the quarter
  the quarry   «Работа в Каменоломне» (708) at Джамшут in the new market down
               to the north pit (632); the map out of reach there; its side
               south into the centre (631) and the centre's north back;
               «Покинуть каменоломню.» (709) up to the new market
  the mine     «Спуститься в шахту» (715) at the copper mine's mouth (208)
               into the control room (663), its door b to the first tier
               (1031) and the tier's a back, «Выйти из шахты» (718) up
  a lottery    «Лотерея Донголы (12-16)» (721): the ticket for 2 400 afro at
               the old market's lottery man, one of the draw's prizes
  the gold     at six in the evening the four bosses: Полковник Халил (93)
               and Джибрил Ибрагим (91) of the ДСР, 10 ounces each in one
               ingot; Шеф Дженсен (98) and Макс Коул (99) of the Peacekeepers,
               12 each, an ingot of ten and two of one
  Мортимер     in the new market (197): the ingots for gold at face value,
               never for afro; every ingot cashed, 0.05 less each, the ledger
               a row a cashing
  the stalls   the black market's band 12-16, afro and gold: Дари's sets
               (Чёрный Ловелас's helmet for afro, its (G) for the ingots'
               gold), «Автоматы и патроны» (a G36 for afro, an АК-47 (G) for
               gold), Одноногий's knives (a Боевой нож (G)); the golden
               lottery (722) for its (G) ticket
  home         the ticket to Абри at Нур-ад-Дин's (110 afro), «Проездной в
               Абри» (282) to the Портовый рынок (187); the ticket to Донгола
               at Луиджи's (100), «Проездной в Донголу» (281) back to the
               station; «Поездка в Вади Хальфу» (631) for 150 to 37
  the prison   a second server at noon: «Поехали!» (632) at Нур-ад-Дин to the
               yard (159), «Тюрьма: западные ворота» (634) down into the
               western block (618), the map out of reach there, its side east
               into the centre (622), «Выход» (163) at Томас up to the yard
               and «Назад в Донголу» (633) at the supply man to the station;
               the uprising's prisoners in the northern cells (620)

Along the whole path nobody shows his mobs.xml name (the remainder
data/orig_names_manual.json lists under "none" included: none of it stands
in Донгола), no thing the path hands out shows its internal name, every
string id of its quests is in the launcher's table, and neither server logs
a traceback.

In process first: the five rides on in the shipped table with their ways at
both ends; Донгола's places on their map cells and the restored ones on
theirs; no trap -- from every place of Донгола a player can get into, Zone 49
and everything their doors, sides and quest ways open (the prison, the
quarry, the mines and their tiers, the sewers, the slavers' camp), some way
of doors, sides and quest ways leads back to a place on a map cell -- and
the strict check beside it (on_map takes a side the table does not list for
a way out): every side of each interior of Донгола is listed in
data/passages.json, the map is out of reach there, and its free ways, sides
and doors alone lead to a place on a map cell; «Выход» (163) under 622 up to
the yard; none of it is a place of the cut.

    LAVA_RES=.../lava/res python3 server/test_dongola_open.py
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
import names  # noqa: E402
import accounts  # noqa: E402
import events  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import npcs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import sets  # noqa: E402
import shop_bands  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

# The places.
STATION_WH, HALFA_QUARTER, PORT = 37, 36, 187
DN_STATION, MARKET, NEW_MARKET, QUARTER, BLACK = 49, 50, 197, 79, 103
SEWERS, QUARRY_PIT, QUARRY_CENTRE = 607, 632, 631
COPPER_MOUTH, COPPER_CONTROL, COPPER_TIER = 208, 663, 1031
YARD, WEST_BLOCK, CENTRE_BLOCK, NORTH_CELLS = 159, 618, 622, 620
CAMP_DSR, CHIEF_DSR, CAMP_PK, CHIEF_PK = 93, 91, 98, 99
# The places of Донгола a player walks into from the map (DESIGN 7.2): the
# town, the camps and their chiefs', the quest places, the mines' mouths, the
# prison's yard and the works.
DONGOLA = [49, 50, 67, 68, 69, 72, 73, 74, 77, 79, 91, 93, 96, 97, 98, 99, 103, 105, 112, 113,
           114, 115, 144, 145, 146, 147, 155, 157, 159, 161, 162, 195, 197, 208, 209, 210, 211,
           212, 253, 445, 625, 697, 1042]
# Zone 49, which no cell opens: Каспар's way from Вади-Хальфа's quarter (733)
# and Генри Джонс's from Абри's slums (744) lead into it.
ZONE49 = [702, 703, 704, 705]
# The interiors of Донгола (DESIGN 4.3): no side of them leads onto the map.
PRISON = [618, 619, 620, 621, 622]
QUARRY = [631, 632, 633, 634, 635]
DN_MINE = [614, 616, 1013, 1015, 1020, 1021, 1022, 1023, 1214]
SEWER_ROOMS = [607, 608, 1009]
INTERIORS = PRISON + QUARRY + DN_MINE + SEWER_ROOMS + ZONE49
# ..and what else the doors and ways of the town open: the copper, saltpetre
# and lead mines' control rooms and tiers, the slavers' camp of «Старые
# приятели» (762).
WORKS = [663, 664, 665, 1031, 1032, 1033, 1224, 1225, 1226, 150]
# The places that opened as plain wasteland, on their cells since 2026-10-13.
RESTORED = {(5878, 2012): 147, (5899, 2003): 253, (5900, 2017): 144, (5894, 2019): 145,
            (5876, 2031): 146, (5896, 2026): 157, (5900, 2026): 161, (5943, 1960): 209,
            (5921, 1982): 211, (5879, 2013): 1042, (5875, 2009): 697, (5877, 2004): 77,
            (5889, 2003): 115, (5882, 2036): 91, (5920, 2010): 99}
# The cut of 2026-10-13: cell -> what stood there; and every file of it.
CUT = {(5879, 2011): "Аэроплощадка ФСЦ (530)", (5876, 2013): "Ремесленники по одежде 14 (455)",
       (5878, 2014): "Ремесленники по одежде 15 (460)",
       (5878, 2015): "Ремесленники по одежде 16 (518)",
       (5878, 2013): "Вещевой рынок «Торговцы одеждой» (469)",
       (5955, 2032): "Блок-пост Delta Force (382)"}
CUT_FILES = ([455, 460, 518, 469, 530, 382, 448, 380, 381, 385, 386, 387, 388, 958, 959, 960,
              1196, 534, 535, 536, 537, 593, 594, 991, 992, 993, 1207, 337, 338, 339, 342, 346,
              350, 354, 358, 362, 366, 955, 956, 957, 1195, 1171, 389])
# The quests.
RIDE_WH, RIDE_BACK_WH, RIDE_ABRI, TICKET_DN, TICKET_ABRI = 630, 631, 275, 281, 282
PRISON_RIDE, PRISON_BACK, GATE_WEST, PRISON_EXIT = 632, 633, 634, 163
AMIN, AMIN_2 = 638, 639
DANGER, CATACOMBS, BEFORE, OLD_TRAMP, FRESH_AIR = 695, 696, 697, 702, 705
QUARRY_IN, QUARRY_OUT, GATE_DOWN, GATE_UP = 708, 709, 715, 718
LOTTERY, GOLD_LOTTERY = 721, 722
CASH = {7620: 301, 4796: 302, 4797: 303}
PATH = [RIDE_WH, RIDE_BACK_WH, TICKET_DN, TICKET_ABRI, PRISON_RIDE, PRISON_BACK, GATE_WEST,
        PRISON_EXIT, AMIN, AMIN_2, DANGER, CATACOMBS, BEFORE, OLD_TRAMP, FRESH_AIR, QUARRY_IN,
        QUARRY_OUT, GATE_DOWN, GATE_UP, LOTTERY, GOLD_LOTTERY] + sorted(CASH.values())
# The people.
HASSIR, LUIGI, NUR, MORTIMER, RASUL, TAHIR = 105, 1179, 156, 1188, 107, 108
TECHNOMASTER, FARIS, TARIF, TARIF_DOWN, TRAMP = 646, 6504, 678, 674, 676
JAMSHUT, OLEG, GATE_IN, GATE_OUT, SORTER = 982, 983, 1330, 1342, 1369
LOTTERY_MAN, GOLD_LOTTERY_MAN, DARI, RIFLES_STALL, ONE_LEG = 663, 712, 1213, 1209, 1153
WELS, WELS_BOX, SORENSEN = 827, 828, 1767
WEST_GUARD, SOUTH_GUARD, SUPPLY, TOMAS = 1792, 1795, 2181, 876
PRISONERS = (932, 933, 934, 935, 936)
KHALIL, JIBRIL, JENSEN, COLE = 374, 375, 407, 408
# The things.
TICKET_TO_DN, TICKET_TO_ABRI, ENVELOPE = 6546, 6547, 1309
LOT_TICKET, GOLD_LOT_TICKET = 2648, 2651
HELMET, HELMET_G, G36, AK47_G, KNIFE_G = 11721, 60000, 25287, 25186, 6261
COPPER_ORE = 1318
I1, I5, I10 = 7620, 4796, 4797
INGOTS = (I1, I5, I10)
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
OUNCE = progression.GOLD_OUNCE
MT = world.mob_types()
with open(os.path.join(ROOT, "data", "orig_names_manual.json"), encoding=ENC) as _fh:
    REMAINDER = {int(k) for k in json.load(_fh)["none"]}


def reached_from(start, free_only=False):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way;
    with free_only, only the free ways -- level 0, no chain, nothing asked,
    no fee, no window (DESIGN 5.2)."""
    with open(travel.passages_path(), encoding=ENC) as fh:
        sides = json.load(fh).get("sides") or {}
    gates = events.table().gates
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = []
        for _c, r in travel.quest_ways(world.location(lid)):
            q = quests.get(int(r["quest"]))
            if free_only and (q is None or not q.give or q.level or q.need_all or q.need_any
                              or q.wants() or q.has_fee or int(r["quest"]) in gates):
                continue
            targets.append(r.get("target_loc_id"))
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
    RIDES = {RIDE_WH: (HASSIR, STATION_WH, DN_STATION), RIDE_BACK_WH: (NUR, DN_STATION, STATION_WH),
             RIDE_ABRI: (LUIGI, PORT, DN_STATION), TICKET_DN: (LUIGI, PORT, DN_STATION),
             TICKET_ABRI: (NUR, DN_STATION, PORT)}
    check("the five rides are on in the shipped table: Хассир to Донгола, Нур-ад-Дин back to"
          " Вади-Хальфа and to Абри by the ticket, Луиджи to Донгола for the fare and by the"
          " ticket; each given and taken by its driver, repeatable",
          {t: (quests.get(t).give, quests.get(t).take, quests.get(t).repeatable) for t in RIDES},
          {t: ([d], [d], 1) for t, (d, _f, _to) in RIDES.items()})
    check("  ..their ways in data/passages.json, from the driver's place to the other end",
          {t: int((travel.quest_way(world.location(frm), t) or {}).get("target_loc_id", 0))
           for t, (_d, frm, _to) in RIDES.items()},
          {t: to for t, (_d, _f, to) in RIDES.items()})
    check("  ..and the way back written at the other end too: Нур-ад-Дин's 631 and 282 at the"
          " station a ride brings one to, Хассир's 630 and Луиджи's 275/281 at theirs",
          sorted(t for t, (_d, frm, to) in RIDES.items()
                 if not [b for b, (_d2, f2, to2) in RIDES.items() if f2 == to and to2 == frm]),
          [])
    check("every string id of the path's quests is in the launcher's table",
          [t for t in PATH if not all(names.known(i) for i in quests.get(t).string_ids())], [])
    check("the places of Донгола the path starts from all stand on map cells",
          [lid for lid in DONGOLA if world.cell_of(lid) is None], [])
    check("the places that opened as wasteland stand on their cells",
          {c: world.location_at(*c) for c in RESTORED}, RESTORED)
    closure = reached_from(set(DONGOLA) | set(ZONE49))
    check("their doors, sides and quest ways open the prison, the quarry, the town's mine, the"
          " sewers and the copper, saltpetre and lead mines with their tiers, the slavers' camp;"
          " Zone 49 is open from Вади-Хальфа's quarter and Абри's slums",
          ([lid for lid in INTERIORS + WORKS if lid not in closure],
           [lid for lid in ZONE49 if lid not in reached_from({HALFA_QUARTER, 255})]), ([], []))
    traps = sorted(lid for lid in closure - set(DONGOLA)
                   if not any(on_map(p) for p in reached_from({lid})))
    check("no trap: from every place of them (%d) a way of doors, sides and quest ways leads"
          " back to a place on the map" % len(closure), traps, [])
    with open(travel.passages_path(), encoding=ENC) as _fh:
        SIDES = json.load(_fh).get("sides") or {}
    unlisted = {lid: sorted(s for s in set(travel.exit_sides(world.location(lid)).values())
                            if s in travel.SIDES and s not in (SIDES.get(str(lid)) or {}))
                for lid in INTERIORS}
    check("  ..and the strict check beside it: every side of each interior of Донгола is listed"
          " in data/passages.json (none is left to lead onto the map), the map is out of reach"
          " there (no_map)",
          ({lid: s for lid, s in unlisted.items() if s},
           [lid for lid in INTERIORS if not travel.no_map(lid)]), ({}, []))
    check("  ..and from each its free ways (level 0, no chain, nothing asked, no fee, no window),"
          " sides and doors alone lead to a place on a map cell",
          sorted(lid for lid in INTERIORS
                 if not any(world.cell_of(p) is not None
                            for p in reached_from({lid}, free_only=True))), [])
    check("«Выход» (163) at Томас leads from the prison's centre (622) up to the yard (159)",
          int((travel.quest_way(world.location(CENTRE_BLOCK), PRISON_EXIT) or {})
              .get("target_loc_id", 0)), YARD)
    check("  ..and none of the places is a place of the cut", sorted(set(CUT_FILES) & closure), [])
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the servers ------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


class Server:
    """A server of the suite's own on a database of its own: a newcomer wakes
    on the map cell given, with no afro of his own; the clock at the local
    time given (the bosses' and the windows'); the map's packs stay home.
    The cheats stand in for the walking between places and the earning; the
    admin gun for the camps' fights."""

    def __init__(self, tag, clock, cell):
        self.tag = tag
        self.port = free_port()
        self.db = os.path.join(tempfile.mkdtemp(), "dongola_open_%s.db" % tag)
        accounts.DB_PATH = self.db
        st = accounts.Store(self.db)
        st.register(tag, "secret")
        st.close()
        self.cred = accounts.credential(tag, "secret")
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1", LAVA_DB=self.db,
                   LAVA_CHEATS="1", LAVA_GX=str(cell[0]), LAVA_GY=str(cell[1]),
                   LAVA_START_AFRO="0", LAVA_AP_REGEN="50", LAVA_RESPAWN="600", LAVA_SEED="12",
                   LAVA_LEAVE_COMBAT="2", LAVA_POLICY_PORT="0", LAVA_ENCOUNTER_CHANCE="0",
                   LAVA_BOSS_CLOCK=clock)
        self.log = os.path.join(os.path.dirname(self.db), "server.log")
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                                     stdout=open(self.log, "w"), stderr=subprocess.STDOUT,
                                     text=True)

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        with open(self.log, encoding=ENC, errors="replace") as fh:
            lines = fh.read().splitlines()
        check("the %s server logged no traceback" % self.tag,
              [line for line in lines if "Traceback" in line or "!!" in line], [])
        return lines


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


def internal(here):
    """The types of an arrival shown by no name the client has, or by their
    mobs.xml one."""
    return sorted(t for t in here if not names.known(t) or names.ALL.get(t) == MT[t][1])


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


def map_refused(c):
    """The map button pressed in an interior: (refused?, a map frame came?)."""
    c.send("chWorld;")
    got = c.frames(1.0)
    return acks(got)[:1] not in ([], [0]), bool(named(got, "gmap"))


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


def ride(c, here, npc_type, qtype):
    """A way row taken and handed back at once: (acks of both, lcall id,
    the arrival's frames)."""
    got, q = take(c, here, npc_type, qtype)
    went = hand_in(c, here, npc_type, q)
    lid, arrival = moved(c, went)
    return acks(got) + acks(went)[:1], lid, arrival


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def store():
    return accounts.Store(SRV.db)


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


def priced(t):
    """(afro price?, gold price?) of a thing, as a stall sells it."""
    si = (items.static_info(t) or (None, {}))[1]
    return bool(si.get("cost")), bool(si.get("g_cost"))


def wield(c, thing):
    c.send("ss_get;target=0;slot=11;")
    held_ = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held_) > 6 and held_[6] not in ("0", thing):
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held_[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % thing)
    return acks(c.frames())


def reload(c, gun):
    """A fresh clip of 99 into the admin gun."""
    rounds = give(c, GUN_ROUNDS, 99)
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")


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
        # test_abri_open's does -- a stand-in for the walk round a camp.
        path = [min(goals, key=lambda cell: mobs.hex_distance(cell, pos, loc.width))]
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    c.frames(0.3 + 0.25 * len(path))
    return path[-1]


def through(c, loc_id, side, pos):
    """Walk onto an exit of a location -- door a or b, or a side W/N/E/S --
    and press «в другую локацию» (chWorld;to=1): (ack, lcall id, arrival).
    A fight's exit timer (LAVA_LEAVE_COMBAT) refusing the first press, the
    second comes after it."""
    loc = world.location(loc_id)
    cells = {cell for cell, s in travel.exit_sides(loc).items()
             if s == side and cell not in loc.obstacles}
    walk_to(c, loc, pos, cells)
    got = []
    for _ in range(3):
        c.send("chWorld;to=1;")
        got = c.until(lambda f: f[0] == "lcall" or (f[0] == "cmdAck" and f[1].get("res")), 4)
        if named(got, "lcall") or acks(got)[:1] == [0]:
            break
        time.sleep(2.5)
    lid, arrival = moved(c, got)
    return acks(got)[-1:], lid, arrival


def boss_bag(c, gun, where, boss):
    """Into a camp in the boss's hour: shoot him from a cell out of every
    other fighter's reach, shoot whoever would see the player at his bag,
    walk to the bag and take it whole -- (fell?, the ingots taken {type:
    pieces})."""
    lid, clinic = goto(c, DN_STATION)
    healer_type = next(t for _cell, t in world.location(DN_STATION).spawns
                       if t and MT[t][0] == world.HEALER)
    healer = inhabitants(clinic, lid)[healer_type][0]
    cheat(c, "/money %d 0" % npcs.healer_price(healer_type, 10))
    c.send("on_conv;mob=%d;op=1;" % healer)
    healed = c.frames()
    vitals = [p for p in named(healed, "usrUp") if p.get("id") == 0]
    check("boss route: healer restores HP and stamina before each fight",
          (acks(healed), [(p["hcur"] == p["hmax"], p["scur"] == p["smax"]) for p in vitals]),
          ([0], [(True, True)]))
    reload(c, gun)
    lid, arrival = goto(c, where)
    mark = len(c.seen) - len(arrival)     # the frames before are other rooms', their ids too
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

    def safe_spots():
        return sorted((mobs.hex_distance(cell, home, W), cell)
                      for cell in range(W * place.height)
                      if cell not in place.obstacles and cell not in placed.values()
                      and reach + 0.5 < mobs.hex_distance(cell, home, W) <= 14
                      and mobs.line_of_fire(place, cell, home) is None
                      and all(mobs.hex_distance(cell, o, W) > wary for o in fighters.values()))
    def watched():
        return {cell for cell in range(W * place.height)
                if any(mobs.hex_distance(cell, o, W) <= wary for o in fighters.values())}
    spots = safe_spots()
    while not spots:
        # A camp too crowded for a cell out of every fighter's reach (the
        # Peacekeepers' 98, ten of the fill round Дженсен and his boxes): his
        # guards first, nearest to him first, each from the nearest cell out
        # of every guard's reach with a line of fire to him.
        seen_cells = watched()
        aim = None
        for _d, i in sorted((mobs.hex_distance(cell, home, W), i) for i, cell in fighters.items()):
            cells = [cell for cell in range(W * place.height)
                     if mobs.hex_distance(cell, fighters[i], W) <= 14
                     and cell not in place.obstacles and cell not in placed.values()
                     and cell not in seen_cells
                     and mobs.line_of_fire(place, cell, fighters[i]) is None]
            if cells:
                aim = (i, min(cells, key=lambda cell: mobs.hex_distance(cell, pos, W)))
                break
        if aim is None:
            return False, {}
        pos = walk_to(c, place, pos, aim[1], seen_cells)
        if shoot(c, gun, aim[0], 10) is None:
            return False, {}
        fighters.pop(aim[0])
        for n, p in c.seen[mark:]:
            if n == "userMove" and p.get("id") in fighters:
                fighters[p["id"]] = p["path"][-1]
        spots = safe_spots()
    pos = walk_to(c, place, pos, spots[0][1], watched())
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
    for n, p in c.seen[mark:]:
        if n == "userMove" and p.get("id") in now:
            now[p["id"]] = p["path"][-1]
    near = [i for i, cell in now.items() if mobs.hex_distance(cell, bag_at[0], W) <= wary + 1]
    downed = [i for i in near if shoot(c, gun, i, 10) is not None]
    now = {i: cell for i, cell in now.items() if i not in downed}
    for n, p in c.seen[mark:]:
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


def newcomer(nick, level):
    """A character of the server's account made, raised to a level of the
    town's band (the skill of his gun with it), and logged in: (client, id,
    lcall id, the arrival's frames)."""
    c = Client(testkit.connect(SRV.port, SRV.proc, SRV.log))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % SRV.cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.3)
    st = store()
    cid = st.character_by_name(nick)["id"]
    st.save_stats(cid, [("skill", progression.SHOOTING, level, 0, progression.skill_xp_max(level))])
    st.save_character_state(cid, level=level)
    st.close()
    c = Client(testkit.connect(SRV.port, SRV.proc, SRV.log))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % SRV.cred)
    c.frames()
    c.send("selPers;num=0;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    arrival = arrive(c)
    inhabitants(arrival, call.get("id"))
    return c, cid, call.get("id"), arrival


# --- the first server: six in the evening, the bosses' hour ------------------------------
SRV = Server("traveller", "2026-10-13T18:00:05", world.cell_of(STATION_WH))
try:
    # --- Вади-Хальфа: the ride, and «Амин» on the way --------------------------------------
    # The town's band 12-16: a character of the thirteenth level (the
    # lotteries 12-16, the mines' gates 12-15, the quarry
    # 12-16).
    c, CID, lid, arrival = newcomer("Traveller", 13)
    here = inhabitants(arrival, lid)
    check("a character of the thirteenth level wakes at Вади-Хальфа's station, Хассир there, with"
          " no afro", (lid, HASSIR in here, money(CID)[0]), (STATION_WH, True, 0))
    check("  ..offered «Поездка в Донголу»", status(c, RIDE_WH), 1)
    took, q_ride = take(c, here, HASSIR, RIDE_WH)
    refused = hand_in(c, here, HASSIR, q_ride)
    check("«Поездка в Донголу» taken; with no afro the hand-in is refused and nobody moves",
          (acks(took), acks(refused)[:1] != [0], bool(named(refused, "lcall"))),
          ([0], True, False))
    lid, arrival = goto(c, HALFA_QUARTER)
    here = inhabitants(arrival, lid)
    got, q = take(c, here, RASUL, AMIN)
    done = hand_in(c, here, RASUL, q)
    check("«Амин» (638) at Расул in Вади-Хальфа's quarter: heard out, 500 afro",
          (lid, acks(got), acks(done)[:1], money(CID)[0]), (HALFA_QUARTER, [0], [0], 500))
    got, q_amin2 = take(c, here, RASUL, AMIN_2)
    check("  ..«Амин (часть 2)» (639) taken: Амин went to Донгола", acks(got), [0])
    lid, arrival = goto(c, STATION_WH)
    here = inhabitants(arrival, lid)
    went = hand_in(c, here, HASSIR, q_ride)
    lid, arrival = moved(c, went)
    here = inhabitants(arrival, lid)
    check("  ..with the afro: handed in, the fare of 200 gone, and an lcall to Донгола's station",
          (acks(went)[:1], money(CID)[0], lid), ([0], 300, DN_STATION))

    # --- the station of Донгола --------------------------------------------------------
    shown = infos(arrival)
    # Since 2026-10-14 (the owner's «сделай потом абу хамед в таком же формате») the
    # station's driver drives to Абу-Хамед too, for 0,25 G or the ticket 1567, and sells
    # that ticket and the one back, 1639 (server/test_abuhamed_quests, the TRADE
    # package's stall).
    check("Донгола's station as the client is shown it: Нур-ад-Дин with the rides to"
          " Абу-Хамед, Абри and Вади-Хальфа, the prison's ride and the prison guard's"
          " invitation, and the tickets to Абри and to Абу-Хамед and back",
          (shown.get(NUR, ("", {}))[1].get("give_quests"),
           shown.get(NUR, ("", {}))[1].get("type_list")),
          ([276, TICKET_ABRI, 283, RIDE_BACK_WH, PRISON_RIDE, 636],
           [TICKET_TO_ABRI, 1567, 1639]))
    check("  ..arrived beside Нур-ад-Дин's way back",
          first(arrival, "lenter").get("pos")
          == travel.door_arrival(world.location(DN_STATION), STATION_WH), True)
    check("  ..everybody there by a name the client has, none by his mobs.xml name",
          internal(here), [])
    done = hand_in(c, here, TAHIR, q_amin2)
    check("«Амин (часть 2)» handed in to Тахир at the station", acks(done)[:1], [0])

    # --- the cut: walked off the station ---------------------------------------------------
    got = to_map(c)
    check("out of the station onto the map: on its cell, 5877,2010",
          [(p.get("x"), p.get("y")) for p in named(got, "gmap")], [world.cell_of(DN_STATION)])
    walked = walk_map(c, 2.5, 1.5)
    lid, arrival = enter_cell(c)
    gone = {t for f in CUT_FILES for _c, t in world.location(f).spawns if t}
    check("two cells east and one south, where «Аэроплощадка ФСЦ» stood: the wasteland of the"
          " cell, nobody of the cut's places in it",
          (bool(named(walked, "userMove")), lid, sorted(set(inhabitants(arrival)) & gone)),
          (True, world.pack(5879, 2011), []))
    other_cut = {}
    for cell in CUT:
        if cell == (5879, 2011):
            continue
        lid, arrival = goto(c, *cell)
        other_cut[cell] = (lid == world.pack(*cell), sorted(set(inhabitants(arrival)) & gone))
    check("every other cell of the cut opens its wasteland, nobody of the cut's places there:"
          " %s" % ", ".join(CUT[cell] for cell in sorted(other_cut)),
          other_cut, {cell: (True, []) for cell in other_cut})

    # --- two of the places restored ------------------------------------------------------
    lid, arrival = goto(c, 5878, 2012)
    here = inhabitants(arrival, lid)
    check("«Дом Мастера Люшера Вельса» (5878,2012): his house (147), Вельс and his three boxes",
          (lid, WELS in here, len(here.get(WELS_BOX, []))), (147, True, 3))
    lid, arrival = goto(c, 5879, 2013)
    here = inhabitants(arrival, lid)
    check("«Свалка Донголы» (5879,2013): the dump (1042), Полковник Дарт Соренсен and his tramps",
          (lid, SORENSEN in here, len(here.get(1772, []))), (1042, True, 4))

    # --- the markets and the quarter: names ------------------------------------------------
    unnamed = {}
    for where in (MARKET, NEW_MARKET, QUARTER, BLACK):
        lid, arrival = goto(c, where)
        unnamed[where] = (lid, internal(inhabitants(arrival, lid)))
    check("the old market, the new, the quarter and the black market: everybody by a name the"
          " client has, none by his mobs.xml name",
          unnamed, {w: (w, []) for w in (MARKET, NEW_MARKET, QUARTER, BLACK)})

    # --- the catacombs: the envelope, down into the sewers and up ---------------------------
    lid, arrival = goto(c, MARKET)
    here = inhabitants(arrival, lid)
    got, q = take(c, here, TECHNOMASTER, DANGER)
    lid, arrival = goto(c, QUARTER)
    here = inhabitants(arrival, lid)
    done = hand_in(c, here, FARIS, q)
    check("«Возможная опасность» (695) from the Техномастер in the old market to агент Фарис in"
          " the quarter", (acks(got), acks(done)[:1]), ([0], [0]))
    got, q = take(c, here, FARIS, CATACOMBS)
    done = hand_in(c, here, TARIF, q)
    check("  ..«Вход в катакомбы» (696) from Фарис to Тариф", (acks(got), acks(done)[:1]),
          ([0], [0]))
    cheat(c, "/money 30000 0")
    stall, opened = open_stall(c, here, TARIF)
    check("Тариф's stall: the envelope for 30 000 afro (60014: «Конверт ты можешь купить у меня,"
          " он стоит 30 000 афро»)", (stall, opened, buy(c, CID, stall, ENVELOPE)),
          ([ENVELOPE], [0], ([0], 1, 30000, 0)))
    close_stall(c)
    got, q = take(c, here, TARIF, BEFORE)
    went = hand_in(c, here, TARIF, q)
    lid, arrival = moved(c, went)
    here = inhabitants(arrival, lid)
    check("  ..«Перед входом» (697): the envelope shown and handed back, and down into the sewers"
          " (607), Тариф there", (acks(got), acks(went)[:1], lid, held(CID)[ENVELOPE],
                                  TARIF_DOWN in here), ([0], [0], SEWERS, 1, True))
    check("  ..where the map is out of reach", map_refused(c), (True, False))
    got, q = take(c, here, TRAMP, OLD_TRAMP)
    done = hand_in(c, here, TRAMP, q)
    check("«Старый бродяга» (702) at the old tramp in the sewers", (acks(got), acks(done)[:1]),
          ([0], [0]))
    ack, lid, arrival = ride(c, here, TARIF_DOWN, FRESH_AIR)
    check("  ..«На свежий воздух» (705) at Тариф: up to the quarter", (ack, lid),
          ([0, 0], QUARTER))

    # --- the quarry: down from the new market and up ----------------------------------------
    lid, arrival = goto(c, NEW_MARKET)
    here = inhabitants(arrival, lid)
    ack, lid, arrival = ride(c, here, JAMSHUT, QUARRY_IN)
    here = inhabitants(arrival, lid)
    check("«Работа в Каменоломне» (708) at Джамшут in the new market: into the quarry's north pit"
          " (632), Олег there", (ack, lid, OLEG in here), ([0, 0], QUARRY_PIT, True))
    check("  ..where the map is out of reach", map_refused(c), (True, False))
    ack, lid, mid = through(c, QUARRY_PIT, "S", first(arrival, "lenter").get("pos"))
    check("  ..its side south into the quarry's centre (631), the stones there",
          (ack, lid, len(inhabitants(mid, lid).get(980, []))), ([0], QUARRY_CENTRE, 20))
    ack, lid, back = through(c, QUARRY_CENTRE, "N", first(mid, "lenter").get("pos"))
    here = inhabitants(back, lid)
    check("  ..and the centre's north back to the pit", (ack, lid), ([0], QUARRY_PIT))
    ack, lid, arrival = ride(c, here, OLEG, QUARRY_OUT)
    check("  ..«Покинуть каменоломню.» (709) at Олег: up to the new market", (ack, lid),
          ([0, 0], NEW_MARKET))

    # --- the copper mine: the gates and a tier ----------------------------------------------
    lid, arrival = goto(c, COPPER_MOUTH)
    here = inhabitants(arrival, lid)
    ack, lid, arrival = ride(c, here, GATE_IN, GATE_DOWN)
    here = inhabitants(arrival, lid)
    check("the copper mine's mouth (208): «Спуститься в шахту» (715) for the band 12-15, into the"
          " control room (663), the sorter and the way up there",
          (ack, lid, SORTER in here, GATE_OUT in here), ([0, 0], COPPER_CONTROL, True, True))
    ack, lid, tier = through(c, COPPER_CONTROL, "b", first(arrival, "lenter").get("pos"))
    check("  ..its door b to the first tier (1031), the copper ore standing there",
          (ack, lid, COPPER_ORE in inhabitants(tier, lid)), ([0], COPPER_TIER, True))
    ack, lid, arrival = through(c, COPPER_TIER, "a", first(tier, "lenter").get("pos"))
    here = inhabitants(arrival, lid)
    check("  ..the tier's door a back to the control room", (ack, lid), ([0], COPPER_CONTROL))
    ack, lid, arrival = ride(c, here, GATE_OUT, GATE_UP)
    check("  ..«Выйти из шахты» (718) up to the mouth", (ack, lid), ([0, 0], COPPER_MOUTH))

    # --- a lottery ---------------------------------------------------------------------
    lid, arrival = goto(c, MARKET)
    here = inhabitants(arrival, lid)
    cheat(c, "/money 2400 0")
    stall, opened = open_stall(c, here, LOTTERY_MAN)
    check("the old market's lottery man: «Лотерейный билет (14)» for 2 400 afro",
          (stall, opened, buy(c, CID, stall, LOT_TICKET)),
          ([LOT_TICKET], [0], ([0], 1, 2400, 0)))
    close_stall(c)
    before = held(CID)
    got, q = take(c, here, LOTTERY_MAN, LOTTERY)
    done = hand_in(c, here, LOTTERY_MAN, q)
    after = held(CID)
    prizes = {o for o, _n, _w in quests.get(LOTTERY).rew_random}
    check("  ..«Лотерея Донголы (12-16)» (721): the ticket gone, one of the draw's prizes in the"
          " bag", (acks(got), acks(done)[:1], after[LOT_TICKET],
                   len([t for t in prizes if after[t] > before[t]])), ([0], [0], 0, 1))

    # --- the gold: the four bosses at six -------------------------------------------------
    GUN = give(c, ADMIN_GUN)
    wield(c, GUN)
    # This scene checks boss loot, not a naked character's endurance.
    # Equip legal level-12 armour; keep real mob damage and aggro.
    for slot, piece in zip(inventory.SET_SLOTS, sets.SLOTS):
        armour = give(c, sets.SETS[11120]["members"][piece])
        c.send("ss_move;obj=x%s;to=%d;from=2048;" % (armour, slot))
        check("boss route: legal armour %s equipped" % piece, acks(c.frames()), [0])
    bags = {}
    for boss, where in ((KHALIL, CAMP_DSR), (JIBRIL, CHIEF_DSR), (JENSEN, CAMP_PK),
                        (COLE, CHIEF_PK)):
        fell, bag = boss_bag(c, GUN, where, boss)
        bags[boss] = (fell, bag, ounces(bag))
    check("at six all four bosses fall and each leaves 3 one-ounce ingots",
          bags, {boss: (True, {I1: 3}, 3) for boss in (KHALIL, JIBRIL, JENSEN, COLE)})
    have = held(CID)
    check("  ..12 ounces in ingots in the bag", {t: have[t] for t in INGOTS},
          {I1: 12, I5: 0, I10: 0})

    # --- Мортимер in the new market --------------------------------------------------------
    lid, arrival = goto(c, NEW_MARKET)
    here = inhabitants(arrival, lid)
    stall, opened = open_stall(c, here, MORTIMER)
    check("Мортимер's stall in the new market: the ingots for gold at face value, never for afro",
          (stall, opened, buy(c, CID, stall, I1)),
          (list(INGOTS), [0], ([inventory.RES_REFUSED], 0, 0, 0)))
    close_stall(c)
    purse0, cashed = money(CID), []
    for t in [I1] * 12:
        before = money(CID)
        got, q = take(c, here, MORTIMER, CASH[t])
        done = hand_in(c, here, MORTIMER, q)
        cashed.append((CASH[t], acks(got) + acks(done)[:1], money(CID)[1] - before[1]))
    check("every ingot cashed at his: «Обналичить 1 унцию» 12 times, 0.05 less each", cashed, [(301, [0, 0], 95)] * 12)
    check("  ..12 ounces of loot made 11.40 on the account, no afro, the ingots gone",
          (money(CID)[1] - purse0[1], money(CID)[0] - purse0[0],
           [held(CID)[t] for t in INGOTS]), (1140, 0, [0, 0, 0]))
    rows = [(r["source"], r["ref"], r["gold"]) for r in ledger(CID) if r["source"] == "quest"
            and r["ref"] in CASH.values()]
    check("  ..the ledger: a row for each cashing under its quest",
          sorted(rows), [("quest", 301, 95)] * 12)

    # --- the black market's stalls: the band 12-16, afro and gold ---------------------------
    lid, arrival = goto(c, BLACK)
    here = inhabitants(arrival, lid)
    lo, hi = shop_bands.band(BLACK)
    seen_stalls = {}
    for trader in (DARI, RIFLES_STALL, ONE_LEG):
        stall, _opened = open_stall(c, here, trader)
        close_stall(c)
        seen_stalls[trader] = stall
    check("the black market's band is the town's, 12-16; Дари's sets, the assault rifles' stall"
          " and Одноногий's knives sell nothing of their kind out of it, each for afro and for"
          " gold",
          ((lo, hi), {t: ([x for x in s if shop_bands.band_ware(x) and not shop_bands.fits(x, lo, hi)],
                          any(priced(x) == (True, False) for x in s),
                          any(priced(x) == (False, True) for x in s))
                      for t, s in seen_stalls.items()}),
          ((12, 16), {t: ([], True, True) for t in seen_stalls}))
    # Purchases exercise prices independently of the temporary loot budget.
    shopping_gold = 10000
    cheat(c, "/money %d %d" % (42000 + 67400, shopping_gold))
    stall, opened = open_stall(c, here, DARI)
    bought = [buy(c, CID, stall, HELMET), buy(c, CID, stall, HELMET_G, gold=True)]
    close_stall(c)
    check("Дари: Чёрный Ловелас's helmet for 42 000 afro, its (G) for 10.50 of the ingots' gold",
          (HELMET in stall, HELMET_G in stall, opened, bought),
          (True, True, [0], [([0], 1, 42000, 0), ([0], 1, 0, 1050)]))
    stall, opened = open_stall(c, here, RIFLES_STALL)
    bought = [buy(c, CID, stall, G36), buy(c, CID, stall, AK47_G, gold=True)]
    close_stall(c)
    check("«Автоматы и патроны»: a G36 for 67 400 afro, an АК-47 (G) for 14.28 gold",
          (opened, bought), ([0], [([0], 1, 67400, 0), ([0], 1, 0, 1428)]))
    stall, opened = open_stall(c, here, ONE_LEG)
    check("Одноногий: a Боевой нож (G) for 5.12 gold; for afro refused",
          (opened, buy(c, CID, stall, KNIFE_G, gold=True), buy(c, CID, stall, KNIFE_G)),
          ([0], ([0], 1, 0, 512), ([inventory.RES_REFUSED], 0, 0, 0)))
    close_stall(c)
    stall, opened = open_stall(c, here, GOLD_LOTTERY_MAN)
    check("the golden lottery: «Лотерейный билет (G)(14)» for 3 gold, for gold alone",
          (stall, opened, buy(c, CID, stall, GOLD_LOT_TICKET, gold=True),
           buy(c, CID, stall, GOLD_LOT_TICKET)),
          ([GOLD_LOT_TICKET], [0], ([0], 1, 0, 300), ([inventory.RES_REFUSED], 0, 0, 0)))
    close_stall(c)
    before = held(CID)
    got, q = take(c, here, GOLD_LOTTERY_MAN, GOLD_LOTTERY)
    done = hand_in(c, here, GOLD_LOTTERY_MAN, q)
    after = held(CID)
    prizes = {o for o, _n, _w in quests.get(GOLD_LOTTERY).rew_random}
    check("  ..«Золотая Лотерея Донголы (12-16)» (722): the ticket gone, one of the prizes in the"
          " bag", (acks(got), acks(done)[:1], after[GOLD_LOT_TICKET],
                   len([t for t in prizes if after[t] > before[t]])), ([0], [0], 0, 1))
    check("  ..shop funding plus boss proceeds cover all purchases",
          money(CID)[1] - purse0[1], shopping_gold + 1140 - 1050 - 1428 - 512 - 300)

    # --- home: to Абри, back, and to Вади-Хальфа ----------------------------------------
    lid, arrival = goto(c, DN_STATION)
    here = inhabitants(arrival, lid)
    cheat(c, "/money 110 0")
    stall, opened = open_stall(c, here, NUR)
    check("Нур-ад-Дин's stall: «Билет в Абри из Донголы» for 110 afro (beside the tickets to"
          " Абу-Хамед and back since 2026-10-14)",
          (stall, opened, buy(c, CID, stall, TICKET_TO_ABRI)),
          ([TICKET_TO_ABRI, 1567, 1639], [0], ([0], 1, 110, 0)))
    close_stall(c)
    afro0 = money(CID)[0]
    ack, lid, arrival = ride(c, here, NUR, TICKET_ABRI)
    here = inhabitants(arrival, lid)
    check("«Проездной в Абри» (282) at Нур-ад-Дин: the ticket taken, no afro, and on to Абри's"
          " Портовый рынок, Луиджи there",
          (ack, held(CID)[TICKET_TO_ABRI], money(CID)[0] - afro0, lid, LUIGI in here),
          ([0, 0], 0, 0, PORT, True))
    cheat(c, "/money 100 0")
    stall, opened = open_stall(c, here, LUIGI)
    check("Луиджи's stall: the tickets to Вади-Хальфа and to Донгола, and the one back from"
          " Донгола; «Билет в Донголу из Абри» for 100 afro",
          (stall, opened, buy(c, CID, stall, TICKET_TO_DN)),
          ([6545, TICKET_TO_DN, TICKET_TO_ABRI], [0], ([0], 1, 100, 0)))
    close_stall(c)
    afro0 = money(CID)[0]
    ack, lid, arrival = ride(c, here, LUIGI, TICKET_DN)
    here = inhabitants(arrival, lid)
    check("«Проездной в Донголу» (281) at Луиджи: the ticket taken, no afro, and back at Донгола's"
          " station", (ack, held(CID)[TICKET_TO_DN], money(CID)[0] - afro0, lid, NUR in here),
          ([0, 0], 0, 0, DN_STATION, True))
    cheat(c, "/money 150 0")
    afro0 = money(CID)[0]
    ack, lid, arrival = ride(c, here, NUR, RIDE_BACK_WH)
    check("«Поездка в Вади Хальфу» (631) at Нур-ад-Дин: 150 afro, and back at Вади-Хальфа's"
          " station", (ack, afro0 - money(CID)[0], lid, HASSIR in inhabitants(arrival, lid)),
          ([0, 0], 150, STATION_WH, True))
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)
    things = [TICKET_TO_DN, TICKET_TO_ABRI, ENVELOPE, LOT_TICKET, GOLD_LOT_TICKET, HELMET,
              HELMET_G, G36, AK47_G, KNIFE_G] + list(INGOTS)
    things += sorted({o for t in (LOTTERY, GOLD_LOTTERY) for o, _n, _w in quests.get(t).rew_random})
    check("no thing the path hands out shows its internal name",
          [t for t in things
           if names.text(items.STRING_ID_OFFSET + t) == items.catalogue().get(t, (None, None))[1]],
          [])
except SystemExit:
    raise
except Exception:
    import traceback
    fails.append("the evening's socket part broke:\n" + traceback.format_exc())
finally:
    LOG_EVENING = SRV.stop()

# --- the second server: noon, the prison's uprising ---------------------------------------
SRV = Server("warden", "2026-10-13T12:00:05", world.cell_of(DN_STATION))
try:
    c, CID, lid, arrival = newcomer("Warden", 13)
    here = inhabitants(arrival, lid)
    check("at noon a character of the thirteenth level wakes at Донгола's station, Нур-ад-Дин"
          " there", (lid, NUR in here), (DN_STATION, True))
    ack, lid, arrival = ride(c, here, NUR, PRISON_RIDE)
    here = inhabitants(arrival, lid)
    check("«Поехали!» (632) at Нур-ад-Дин in the uprising's hour: to the prison's yard (159), its"
          " two guards, the supply man and the healer there",
          (ack, lid, sorted(t for t in (WEST_GUARD, SOUTH_GUARD, SUPPLY, 2109) if t in here)),
          ([0, 0], YARD, sorted([WEST_GUARD, SOUTH_GUARD, SUPPLY, 2109])))
    check("  ..everybody there by a name the client has", internal(here), [])
    yard = here
    ack, lid, arrival = ride(c, here, WEST_GUARD, GATE_WEST)
    check("«Тюрьма: западные ворота» (634) at the western guard: down into the western block (618)",
          (ack, lid), ([0, 0], WEST_BLOCK))
    check("  ..where the map is out of reach", map_refused(c), (True, False))
    ack, lid, centre = through(c, WEST_BLOCK, "E", first(arrival, "lenter").get("pos"))
    here = inhabitants(centre, lid)
    check("  ..its side east into the centre (622), Томас there", (ack, lid, TOMAS in here),
          ([0], CENTRE_BLOCK, True))
    ack, lid, arrival = ride(c, here, TOMAS, PRISON_EXIT)
    here = inhabitants(arrival, lid)
    check("«Выход» (163) at Томас: up to the yard", (ack, lid, SUPPLY in here), ([0, 0], YARD, True))
    ack, lid, arrival = ride(c, here, SUPPLY, PRISON_BACK)
    check("«Назад в Донголу» (633) at the supply man: back at the station",
          (ack, lid, NUR in inhabitants(arrival, lid)), ([0, 0], DN_STATION, True))
    lid, arrival = goto(c, NORTH_CELLS)
    here = inhabitants(arrival, lid)
    check("the uprising's prisoners in the northern cells (620): ten, by the original's name",
          (lid, sum(len(here.get(t, [])) for t in PRISONERS), internal(here)),
          (NORTH_CELLS, 10, []))
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
except SystemExit:
    raise
except Exception:
    import traceback
    fails.append("the noon's socket part broke:\n" + traceback.format_exc())
finally:
    LOG_NOON = SRV.stop()

# --- names along the whole path -----------------------------------------------------------
shown = {t: (MT.get(t, ("", "?"))[1], where) for t, where in SEEN.items()
         if names.ALL.get(t) in (None, MT.get(t, ("", None))[1])}
check("nobody along the whole path stands by his mobs.xml name (%d types seen), the remainder"
      " data/orig_names_manual.json lists under \"none\" included (%d types, none of them"
      " standing in Донгола)" % (len(SEEN), len(REMAINDER)), sorted(shown), [])
if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    print("\n--- evening server log tail ---\n" + "\n".join(LOG_EVENING[-40:]))
    print("\n--- noon server log tail ---\n" + "\n".join(LOG_NOON[-40:]))
    sys.exit(1)
print("\ndongola open OK")
