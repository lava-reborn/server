"""Patrols round the camps: the open desert next to a camp stands the camp's fighters.

The owner's word of 2026-10-11: «во всех соседних локациях тоже добавь мобов
они там должны быть». The rows of data/placements.json marked "patrol",
written by data/build_camp_patrols.py, on the real table and the real world:

  * the rings: every open-desert cell touching one of Вади-Хальфа's camps or
    its chief's place (12 round each of 80/82, 81/83, 84/86, 85/87) stands,
    in rooms.Room, eight of the camp's own fighters -- role mob, kinds of
    the camp's data/camp_fill.json, levels inside the camp's band -- on the
    slot cells of the original's wasteland tile MW_023; every cell touching
    the valley's «Лагерь бандитов» (8, inside the valley's wall) four of its
    bandits 20, 21 and 251; and since the owner's «В Абри добавь мобов в
    лагеря и в окрестности» (2026-10-12) the 12 round each of Абри's camps
    and their chiefs' places, 88/89 (the slave traders, 8-10) and 92/90 (the
    flayers, 10-12), eight of their fighters each, and since the owner's «и
    потом сделай донголу тоже» (2026-10-13) the 12 round each of Донгола's,
    93/91 (the ДСР, 12-14) and 98/99 (the Peacekeepers, 14-16); every ring
    cell is open desert, at war, passable, no settlement and no place taken
    out of the game;
  * the cells the lavabook names for the camps' quests stand the kinds
    those quests want there: «Учет» and «Раббин аль-Гуд» on 5970,1725,
    «Заказ» on 5977,1727, «Как слышно?» and «Бандитская активность» on
    5974,1738, «Порядок (часть 2)» on 5992,1722, whose officers stand on no
    other cell; nobody of «Театр жизни» (336), no treasurer, no boss;
  * the table: every row can stand (rooms.placement_problems), the patrol
    rows are exactly the builder's, the hand rows of 184, 31 and 102 are
    as they were, and Абри's (Мортимер in 187, Санденс Кид in 88, Бутч
    Кэссиди in 92, the dump's eight junk piles in 289) and Донгола's
    (the machine-gun trader in its black market, 1208 in 103, and Вильям
    Блейд in the ДСР's camp, 1565 in 93) are all there are besides;
  * no ambush on a ring cell, as before (encounters.band_at, near_town);
  * a patrol fighter killed comes back on the respawn timer, on its cell.

On a socket: the server starts on the table (rooms.check_placements, before
its first socket), and a player sent onto a ring cell is shown its eight on
their cells.

    LAVA_RES=.../lava/res python3 server/test_camp_patrols.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_PLACEMENTS", "LAVA_QUESTS", "LAVA_PASSAGES", "LAVA_START",
              "LAVA_ENCOUNTER_CHANCE", "LAVA_RESPAWN"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "data"))
import accounts      # noqa: E402
import bosses        # noqa: E402
import combat        # noqa: E402
import encounters    # noqa: E402
import mobs          # noqa: E402
import quests        # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

import build_camp_patrols    # noqa: E402
import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MT = world.mob_types()
with open(os.path.join(ROOT, "data", "camp_fill.json"), encoding="utf-8") as _fh:
    FILL = {int(k): v for k, v in json.load(_fh)["fill"].items()}

# camp -> its chief's place, the creatures per cell
CAMPS = {80: (82, 8), 81: (83, 8), 84: (86, 8), 85: (87, 8), 34: (None, 4),
         88: (89, 8), 92: (90, 8), 93: (91, 8), 98: (99, 8)}
VALLEY_CAMP, VALLEY_KINDS = 34, {20, 21, 251}
SLOTS8 = [(20, 34), (35, 44), (20, 54), (29, 70), (50, 74), (15, 84), (39, 95), (25, 104)]
SLOTS4 = [(20, 34), (29, 70), (50, 74), (25, 104)]
LOOSER, TREASURERS, OFFICERS = 336, (586, 590, 591, 592, 593), {303, 307, 311}
# The lavabook's cells, and the quests whose kinds stand there.
UCHET, ZAKAZ, KAK_SLYSHNO, PORYADOK = (5970, 1725), (5977, 1727), (5974, 1738), (5992, 1722)
# The hand rows: Ибрахим's tools box, Мвамба's three thugs, Мортимер; and
# Абри's (2026-10-12): Мортимер in the port market, Санденс Кид and Бутч
# Кэссиди in their camps, the car dump's eight junk piles; and Донгола's
# machine-gun trader «Пулеметы и патроны» (1208) on its black market, the
# medicine by the cities' tiers of the same day; and Вильям Блейд in the
# ДСР's camp (the owner's Донгола, 2026-10-13).
HAND = {184: [(1135, [56, 88], False)],
        31: [(566, [34, 61], True), (566, [30, 70], True), (566, [39, 70], True)],
        102: [(1188, [40, 59], False)],
        187: [(1188, [40, 72], False)],
        103: [(1208, [36, 79], False)],
        88: [(1563, [40, 36], False)],
        92: [(1564, [39, 40], False)],
        93: [(1565, [38, 53], False)],
        289: [(2367, [28, 69], False), (2368, [14, 95], False), (2369, [20, 13], False),
              (2370, [20, 85], False), (2371, [36, 114], False), (2372, [23, 9], False),
              (2373, [24, 80], False), (2374, [41, 38], False)]}


def ring(camp):
    chief = CAMPS[camp][0]
    places = [world.cell_of(camp)] + ([world.cell_of(chief)] if chief else [])
    cells = {(x + dx, y + dy) for x, y in places for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return sorted(cells - set(places), key=lambda c: (c[1], c[0]))


def band(camp):
    """The levels the camp's own fighters stand in: its camp_fill band, or,
    for the valley camp the table does not fill, its file's bandits'."""
    if camp in FILL:
        return tuple(FILL[camp]["band"])
    levels = [mobs.stats(t).level for _c, t in world.location(camp).spawns
              if t and mobs.stats(t).role == "mob"]
    return min(levels), max(levels)


def camp_kinds(camp):
    chief = CAMPS[camp][0]
    if camp not in FILL:
        return {t for _c, t in world.location(camp).spawns if t and mobs.stats(t).role == "mob"}
    # The fill of both, and the fighters the files stand themselves (the four
    # slave traders of Абри's chief's place 89).
    return ({t for lid in (camp, chief) for t in FILL[lid]["types"]}
            | {t for lid in (camp, chief) for _c, t in world.location(lid).spawns
               if t and mobs.stats(t).role == "mob"})


table = world.placements()
patrol = {lid: [r for r in recs if "patrol" in r] for lid, recs in table.items()}
patrol = {lid: recs for lid, recs in patrol.items() if recs}
RINGS = {camp: ring(camp) for camp in CAMPS}
STOOD = {}                      # (x, y) -> [type id] as rooms.Room stands them

# --- the rings ------------------------------------------------------------------------------
print("the rings")
try:
    check("104 cells hold a patrol: 12 round each of the four camps of Вади-Хальфа, of Абри's two and"
          " of Донгола's two, 8 round the valley's «Лагерь бандитов»",
          (len(patrol), {camp: len(cells) for camp, cells in RINGS.items()}),
          (104, {80: 12, 81: 12, 84: 12, 85: 12, 34: 8, 88: 12, 92: 12, 93: 12, 98: 12}))
    check("  ..and they are exactly the open-desert cells touching a camp or its chief's place",
          sorted(patrol), sorted(world.pack(x, y) for cells in RINGS.values() for x, y in cells))
    check("  ..each row naming its own camp",
          {camp: sorted({r["patrol"] for x, y in cells for r in patrol[world.pack(x, y)]})
           for camp, cells in RINGS.items()},
          {camp: [camp] for camp in CAMPS})
    bad = []
    for camp, cells in RINGS.items():
        inside = camp == VALLEY_CAMP
        for x, y in cells:
            loc = world.location(world.location_at(x, y))
            if not (world.location_at(x, y) == world.pack(x, y) and loc.file.startswith("desert/")
                    and loc.war and world.passable(x, y)
                    and (x, y) not in world.settlements() and (x, y) not in world.retired_cells()
                    and world.in_noob_valley(x, y) == inside):
                bad.append((camp, x, y, loc.file))
    check("every ring cell is open desert at war, passable, no settlement, no place taken out"
          " of the game, and on its camp's side of the valley's wall", bad, [])

    for camp, cells in RINGS.items():
        n = CAMPS[camp][1]
        lo, hi = band(camp)
        kinds = camp_kinds(camp)
        counts, wrong, levels, slots = set(), [], set(), set()
        for x, y in cells:
            room = rooms.Room(world.location(world.pack(x, y)), rooms.IdAllocator(), MT)
            npcs = list(room.npcs.values())
            STOOD[(x, y)] = sorted(npc.type_id for npc in npcs)
            counts.add(len(npcs))
            for npc in npcs:
                st = mobs.stats(npc.type_id)
                levels.add(st.level)
                if npc.root != world.MOB or st.role != "mob" or npc.type_id not in kinds:
                    wrong.append((x, y, npc.type_id, st.role))
            slots.add(tuple(sorted((npc.cell % 64, npc.cell // 64) for npc in npcs)))
        name = world.location(camp).title
        check("%s (%d): each of its %d cells stands %d, all fighters of the camp's own kinds"
              % (name, camp, len(cells), n), (counts, wrong), ({n}, []))
        check("  ..of levels %d-%d, the camp's band, none above it" % (lo, hi),
              all(lo <= lv <= hi for lv in levels), True)
        check("  ..on the slot cells of MW_023", slots,
              {tuple(sorted(SLOTS8 if n == 8 else SLOTS4))})
    check("the valley's ring: its bandits 20, 21 and 251, four to a cell",
          sorted({t for c in RINGS[VALLEY_CAMP] for t in STOOD[c]}), sorted(VALLEY_KINDS))
    check("the whole range of each camp's patrol kinds stands somewhere on its ring",
          {camp: sorted({t for c in RINGS[camp] for t in STOOD[c]}) for camp in CAMPS},
          {camp: sorted(set(build_camp_patrols.kinds(camp))
                        | {t for c, (ks, _w) in build_camp_patrols.ANCHORS.items()
                           if c in RINGS[camp] for t in ks}) for camp in CAMPS})
    check("800 fighters in all (416 of Вади-Хальфа and the valley, 192 of Абри, 192 of Донгола)",
          sum(len(v) for v in STOOD.values()), 800)
except Exception:
    fails.append("the rings broke:\n" + traceback.format_exc())


# --- the lavabook's cells ---------------------------------------------------------------------
print("the lavabook's cells")
try:
    def wants(qtype):
        q = quests.get(qtype)
        return {m for _o, _n, ms in q.objs for m in ms} | set(q.mobs_kill)

    check("«Учет» (103): 5970,1725 stands the four whose «Учетные записи» it wants",
          ({261, 262, 266, 267} <= set(STOOD[UCHET]), {261, 262, 266, 267} <= wants(103)),
          (True, True))
    check("  ..and the rest there are colonists «Раббин аль-Гуд» (115) takes its money bags off",
          sorted(set(STOOD[UCHET]) - wants(103) - wants(115)), [])
    check("«Заказ» (119): 5977,1727 stands only the sect's kinds it takes the parts off",
          set(STOOD[ZAKAZ]) <= wants(119), True)
    check("«Как слышно?» (116) and «Бандитская активность» (117): 5974,1738 stands the"
          " Janjaweed, the Диверсант of the fifth level among them",
          (set(STOOD[KAK_SLYSHNO]) <= wants(116), 291 in STOOD[KAK_SLYSHNO], wants(117)),
          (True, True, {291}))
    check("«Порядок (часть 2)» (130): 5992,1722 stands its three officers",
          (OFFICERS <= set(STOOD[PORYADOK]), wants(130)), (True, OFFICERS))
    check("  ..who stand on no other ring cell",
          sorted(c for c, ts in STOOD.items() if c != PORYADOK and OFFICERS & set(ts)), [])
    every = [t for ts in STOOD.values() for t in ts]
    check("no ring cell stands «Неудачник» 336, a treasurer (586, Абри's 590 and 591, Донгола's 592"
          " and 593), Санденс Кид, Бутч Кэссиди or Вильям Блейд, or anybody who keeps the bosses' hours",
          sorted({t for t in every if t in (LOOSER,) + TREASURERS + (1563, 1564, 1565)
                  or bosses.keeps_hours(t) or mobs.stats(t).role != "mob"}), [])
except Exception:
    fails.append("the lavabook's cells broke:\n" + traceback.format_exc())


# --- the table --------------------------------------------------------------------------------
print("the table")
try:
    check("every row of data/placements.json can stand (rooms.placement_problems)",
          rooms.placement_problems(MT), [])
    check("  ..and the server would start on it (rooms.check_placements)",
          rooms.check_placements(MT), None)
    check("the patrol rows are exactly what data/build_camp_patrols.py builds", patrol,
          build_camp_patrols.rows())
    check("every patrol cell's first row says why, the rest point to it",
          [lid for lid, recs in patrol.items()
           if not recs[0]["why"].startswith(
               "DESIGNED, the owner's (2026-10-12, «Делаем Абри»)" if recs[0]["patrol"] in (88, 92)
               else "DESIGNED, the owner's (2026-10-13): «и потом сделай донголу тоже»"
               if recs[0]["patrol"] in (93, 98) else "DESIGNED, the owner's (2026-10-11)")
           or any(r["why"] != "As the first row of %d (%d,%d)." % ((lid,) + world.unpack(lid))
                  for r in recs[1:])], [])
    # The owner's places of ours (data/locations, the location editor) stand
    # whom he puts there: their rows are the editor's and its checks', not
    # hand rows of the original's places.
    OURS = set(world.overlay_ids())
    check("the hand rows of 184, 31 and 102 are as they were, and Абри's of 187, 88, 92 and 289"
          " and Донгола's of 103 and 93 are the only others (the places of ours aside)",
          {lid: [(r["type"], r["cell"], bool(r.get("escort"))) for r in recs if "patrol" not in r]
           for lid, recs in table.items() if any("patrol" not in r for r in recs)
           and not (lid in OURS and lid >= world.FIRST_NEW_ID)}, HAND)
except Exception:
    fails.append("the table broke:\n" + traceback.format_exc())


# --- the ambushes -----------------------------------------------------------------------------
print("the ambushes")
try:
    cells = [c for cs in RINGS.values() for c in cs]
    check("no ambush on a ring cell: each touches its camp (encounters.near_town), so none is"
          " any band's wasteland (encounters.band_at)",
          ([c for c in cells if not encounters.near_town(*c)],
           [c for c in cells if encounters.band_at(*c) is not None]), ([], []))
except Exception:
    fails.append("the ambushes broke:\n" + traceback.format_exc())


# --- the respawn ------------------------------------------------------------------------------
class _Seat(object):
    """A session standing in the room: whatever reaches it is kept."""
    pid = rooms.player_id(1)

    def __init__(self):
        self.sent = []
        self.combat = type("F", (), {"aim": None, "strike": None, "duels": {},
                                     "dead": False})()

    def send(self, cmd, **params):
        self.sent.append((cmd, params))

    def send_npc_info(self, npc_id):
        self.sent.append(("npc_info", dict(id=npc_id)))

    def take(self):
        out, self.sent = self.sent, []
        return out


async def _respawn():
    x, y = RINGS[80][0]
    loc = world.location(world.pack(x, y))
    store = accounts.Store(os.path.join(tempfile.mkdtemp(), "patrols.db"))
    saved = combat.CORPSE_DELAY, combat.RESPAWN_DELAY
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.05
    try:
        room = rooms.Room(loc, rooms.IdAllocator(), MT)
        rc = combat.RoomCombat(room, store)
        check("a patrol cell's eight are the room's fighters, none a boss",
              (len(rc.mobs), rc.bosses), (8, []))
        seat = _Seat()
        room.players[seat] = True
        mob = sorted(rc.mobs.values(), key=lambda m: m.eid)[0]
        rc.kill(mob, None)
        await asyncio.sleep(0.4)          # the corpse fades, the respawn delay passes
        got = seat.take()
        check("one killed falls, fades and comes back on the respawn timer, on its own cell",
              ([n for n, p in got if n == "lch" and "dead" in p] != [],
               [p.get("lostUser") for n, p in got if n == "lch" and "lostUser" in p],
               [(p.get("newUser"), p.get("pos")) for n, p in got if n == "lch" and "newUser" in p],
               mob.alive, mob.eid in room.npcs),
              (True, [mob.eid], [(mob.eid, mob.home)], True, True))
        for bag in rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()
    finally:
        combat.CORPSE_DELAY, combat.RESPAWN_DELAY = saved
        store.close()


print("the respawn")
try:
    asyncio.run(_respawn())
except Exception:
    fails.append("the respawn broke:\n" + traceback.format_exc())


# --- the server ---------------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


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

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=5.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


print("the server")
PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "camp_patrols.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("patrolman", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_SEED="11", LAVA_POLICY_PORT="0")
env.pop("LAVA_DB_URL", None)
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)
try:
    c = Client(testkit.connect(PORT, srv, LOG))
    check("the server starts on the table with the patrols in it", srv.poll(), None)
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential("patrolman", "secret"))
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Patrolman@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.frames(1.5)
    x, y = UCHET
    c.send("userMsg;entry=@/goto %d %d@;group=0;" % (x, y))
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    got = c.frames(2.5)
    placed = {}
    for n, p in got:
        if n == "lch" and "newUser" in p and int(p.get("rtype", -1)) == world.MOB:
            placed[int(p["newUser"])] = int(p["pos"])
    kinds = {int(p["id"]): int(p["name"]) for n, p in got if n == "userInfo" and "name" in p}
    want = sorted((r["type"], r["cell"][1] * 64 + r["cell"][0])
                  for r in patrol[world.pack(x, y)])
    check("sent onto 5970,1725 a player is shown its eight on their cells, by kind",
          sorted((kinds.get(eid), pos) for eid, pos in placed.items()), want)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
except Exception:
    fails.append("the socket run broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()
    with open(LOG, encoding="utf-8", errors="replace") as _fh:
        _out = _fh.read()
    if "Traceback" in _out:
        fails.append("server logged a traceback:\n" + _out[-2500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    print("server log: %s" % LOG)
    sys.exit(1)
print("camp patrols OK")
