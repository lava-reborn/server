"""The Nubian valley's world, made ready for its quests (the owner's «давай
готовь квесты все», 2026-09-26): the places, the inhabitants, the loot and
the names those quests need, held to before the quests are written.

  * places on the map the client's own tooltips name: «Поля и Пастбища»
    (6268,1818) is 182, the cows' place, moved there from the north-west
    corner and walked into from the Нубийское поселение below it and back;
    «Гонец» (6272,1833) is 28, the courier's; «Банда коммисара Рекса»
    (6273,1832) is 30, the commissar's (data/settlements_verified.json);
  * the barn's door (166, b) leads down into the old adits 643 and their
    door (a) back up (data/passages.json);
  * an inhabitant put down by hand (data/placements.json): the tools box of
    «Забрать инструменты» in 184, drawn and named like any inhabitant, with
    no «Прописка»; a table that would put somebody where he cannot stand
    does not start the server, which is tried on a second one; a hostile
    creature put down by hand fights like one of the file's own;
  * a quest's thing on a creature (mobs.QUEST_TIER): the courier's letter is
    in his bag for a player whose quest asks for it, and for nobody else --
    not before the quest is taken, not once the letter is in the bag;
  * names: the boss by his full one, «[5] Лидер Ян Дуглас» (texts.xml 50270),
    the arena's trader, the courier, the commissar and the three raiders who
    stand with him in 30, the black rats, the box, the cows -- and nobody the
    valley or the rooms its doors lead into stand by his mobs.xml name but
    the one the original has no row for (5208); the things the valley's
    creatures and quests leave in a bag, by the original's names and with
    its descriptions in the frame ss_get_si answers with, not only in the
    table.

The courier's quest here is a fixture of this suite (LAVA_QUESTS): the real
«Пути информации» is written later, on this.

    LAVA_RES=.../lava/res python3 server/test_valley_world.py
"""
import asyncio
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

LETTER = 233            # Бумага с посланием: cost 0, the courier's
COURIER = 17            # m05_BanditCourier_lvl2, alone in 28
RAIDER = 16             # m05_BanditRaider_lvl3, three of them beside the commissar in 30
NO_ROW = set()          # 5208 Npc_Trader000035, the one the original has no row for, is named by
                        # the owner's data/npcs.json since 2026-09-26 («Ящик с припасами»)
# What the valley's creatures and quests leave in a bag: the dogs', rats' and
# antelopes' parts, the gun parts and medicaments, the letter, the leader's
# notes, the grindstone, the rat king, the matches.
THINGS = {216: "Мясо животного", 217: "Собачий клык", 218: "Собачья шкура",
          219: "Кость животного", 224: "Мясо антилопы", 225: "Шкура антилопы",
          226: "Рог антилопы", 228: "Ствол оружия", 229: "УСМ", 230: "Железный затвор",
          231: "Рукоятка", 232: "Медикаменты", 233: "Бумага с посланием", 234: "Записи",
          3216: "Крысиный хвост", 3217: "Точильный камень", 3218: "Крысиный король",
          6915: "Коробка спичек"}
SEIFUL = 35             # Сейфул, in 29
LETTER_Q = 90201        # the suite's own quest: bring the letter to Сейфул
FIXTURES = [
    dict(type=LETTER_Q, kind="bring_l_obj", name="Письмо курьера",
         start="Перехвати курьера и принеси его письмо.", notfinish="Где письмо?",
         finish="Посмотрим, что он вёз.", give=[SEIFUL], take=[SEIFUL],
         objs=[dict(obj=LETTER, num=1, mobs=[COURIER])], rew_afro=10, repeatable=0),
]
with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"),
          encoding="utf-8") as fh:
    TABLE = json.load(fh)
TABLE["quests"] = TABLE["quests"] + FIXTURES
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as fh:
    json.dump(TABLE, fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE
for _knob in ("LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP", "LAVA_BAG_DROP"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


PASTURE, GONEC, REX = (6268, 1818), (6272, 1833), (6273, 1832)
VILLAGE = (6268, 1819)                      # 181, the start
OLD_CORNER = (5833, 1607)                   # where the placer had 182
BARN, ADITS = 166, 643
BOX, BOX_LOC, BOX_XY = 1135, 184, (56, 88)
MT = world.mob_types()


def exit_cell(loc, side):
    """An exit cell of the side one can stand on, nearest the middle of the
    edge (or of the door's cells, for a or b). Some files' outzones run a
    row past their own grid (182's to y 128 of 0..127)."""
    cells = sorted(c for c, s in travel.exit_sides(loc).items() if s == side
                   and 0 <= c < loc.width * loc.height and c not in loc.obstacles)
    if side in travel.SIDES:
        mx, my = travel._edge_middle(loc, side)
    else:
        mx = sum(c % loc.width for c in cells) / float(len(cells))
        my = sum(c // loc.width for c in cells) / float(len(cells))
    return min(cells, key=lambda c: ((c % loc.width - mx) ** 2
                                     + (c // loc.width - my) ** 2, c))


# --- in process: the map --------------------------------------------------------
try:
    check("the map's «Поля и Пастбища», «Гонец» and «Банда коммисара Рекса" " open 182, 28, 30",
          [world.location_at(*c) for c in (PASTURE, GONEC, REX)], [182, 28, 30])
    check("and each stands on its own cell",
          [world.cell_of(i) for i in (182, 28, 30)], [PASTURE, GONEC, REX])
    check("the north-west corner that had 182 is the rim's rock again",
          (world.location_at(*OLD_CORNER) != 182, world.location_at(*OLD_CORNER) in
           travel.ROCK_WALL), (True, True))
    check("all three inside the owner's wall, none of it opened",
          [world.in_noob_valley(*c) and world.passable(*c) for c in (PASTURE, GONEC, REX)],
          [True] * 3)
    village, pasture = world.location(181), world.location(182)
    ex = travel.plan_exit(village, exit_cell(village, travel.N), *VILLAGE)
    check("north out of the village is the pasture", (ex.loc_id, ex.gx, ex.gy),
          (182,) + PASTURE)
    check("whose one way out is south", sorted(set(travel.exit_sides(pasture).values())),
          [travel.S])
    ex = travel.plan_exit(pasture, exit_cell(pasture, travel.S), *PASTURE)
    check("and it leads back into the village", (ex.loc_id, ex.gx, ex.gy), (181,) + VILLAGE)
    barn, adits = world.location(BARN), world.location(ADITS)
    barn_cell = world.cell_of(BARN)
    ex = travel.plan_exit(barn, exit_cell(barn, "b"), *barn_cell)
    check("the barn's door goes down into the old adits, on the barn's cell",
          (ex.loc_id, (ex.gx, ex.gy)), (ADITS, barn_cell))
    check("  ..arriving beside the door back, not on it",
          (travel.side_at(adits, ex.pos), ex.pos in adits.obstacles), (None, False))
    ex = travel.plan_exit(adits, exit_cell(adits, "a"), *barn_cell)
    check("and the adits' door comes back up into the barn", ex.loc_id, BARN)
except Exception:
    import traceback
    fails.append("the map in process broke:\n" + traceback.format_exc())

# --- in process: the inhabitants put down by hand ----------------------------------
placed_in = getattr(world, "placed_in", lambda _loc: [])
problems = getattr(rooms, "placement_problems", None)
try:
    check("the table puts the tools box in 184, on 56,88, with no «Прописка»",
          [(r.get("type"), list(r.get("cell", ())), r.get("home")) for r in placed_in(BOX_LOC)],
          [(BOX, list(BOX_XY), False)])
    check("and every row of it can stand", problems(MT) if problems else None, [])
    bad = {BOX_LOC: [dict(type=39, cell=[40, 90], why="a box of loot"),
                     dict(type=BOX, cell=[63, 81], why="on the way out"),
                     dict(type=999999, cell=[40, 91], why="nobody"),
                     dict(type=BOX, cell=[99, 5], why="off the map"),
                     dict(type=BOX, cell=[40, 92])],
           185: [dict(type=82, cell=[30, 60], why="a dog in the market")]}
    got = problems(MT, bad) if problems else []
    check("a table is refused for a loot box, an exit, an unknown creature, a cell"
          " off the grid, a row with no why and a fighter where nobody fights",
          [any(frag in p for p in got) for frag in (
              "39 on 40,90: a loot box", "on an exit", "999999 on 40,91", "off the 64x128",
              "40,92: no why", "loc 185: 82 on 30,60: a hostile")], [True] * 6)
    room = rooms.Room(world.location(BOX_LOC), rooms.IdAllocator(), MT)
    boxes = [n for n in room.npcs.values() if n.type_id == BOX]
    check("the room of 184 holds the box, a commoner, on its cell",
          [(n.cell, n.root) for n in boxes],
          [(BOX_XY[1] * 64 + BOX_XY[0], world.COMMONER)])
    check("the box registers nobody's home; a cow does",
          (getattr(world, "offers_home", lambda _t: True)(BOX),
           getattr(world, "offers_home", lambda _t: True)(5195)), (False, True))
    # A creature put down by hand fights like the file's own: in a table of
    # this process only, a dog beside the box.
    saved = getattr(world, "_PLACEMENTS", None)
    try:
        world._PLACEMENTS = {BOX_LOC: [dict(type=82, cell=[40, 90], why="a test dog")]}
        room = rooms.Room(world.location(BOX_LOC), rooms.IdAllocator(), MT)
        rc = combat.RoomCombat(room, None)
        dogs = sorted(m.home for m in rc.mobs.values() if m.type_id == 82)
        check("a dog put down by hand is one more mob of the room, at home on its cell",
              (len(dogs), 90 * 64 + 40 in dogs), (5, True))
    finally:
        world._PLACEMENTS = saved
except Exception:
    import traceback
    fails.append("the placements in process broke:\n" + traceback.format_exc())

# --- in process: a quest's thing on a creature ----------------------------------------
quest_table = getattr(mobs, "quest_table", lambda _t: [])
try:
    check("the courier carries his letter for a quest, certainly",
          quest_table(COURIER), [(LETTER, 1.0)])
    check("and never in his ordinary table", [r for r in mobs.loot_table(COURIER)
                                              if r[0] == LETTER], [])
    rng = random.Random(3)
    plain = [mobs.loot_for(mobs.stats(COURIER), rng) for _ in range(200)]
    check("for nobody's quest it is never in his bag",
          any(t == LETTER for drop in plain for t, _n in drop), False)
    try:
        asked = [mobs.loot_for(mobs.stats(COURIER), rng, {LETTER}) for _ in range(50)]
    except TypeError:
        asked = []
    check("for a quest that asks for it, in every bag, once",
          [sum(1 for t, _n in drop if t == LETTER) for drop in asked], [1] * 50)
    wanted_rows = {t: [r[0] for r in quest_table(t)] for t in (14, 15, 250, 251, 2103, 1019, 12)}
    # 3179 (Доктор Гофус's old chip) and the antelopes' meat and fillet came
    # with the valley's third batch of quests (server/test_valley_market.py).
    check("the other quest things the valley's quests ask of its creatures",
          wanted_rows, {14: [228, 229, 230, 231, 232], 15: [228, 229, 230, 231, 232],
                        250: [232, 3179, 3217, 6915], 251: [232, 3179, 3217, 6915],
                        2103: [234], 1019: [3218], 12: [260, 3059]})
    check("  ..among them things no ordinary row may drop: unpriced, or a quest's own",
          [mobs.droppable(t) for t in (LETTER, 228, 3217, 3218, 234)], [False] * 5)
except Exception:
    import traceback
    fails.append("the quest loot in process broke:\n" + traceback.format_exc())

# --- in process: names -----------------------------------------------------------------
try:
    blob = names.document_bytes()
    want = {2103: "[5] Лидер Ян Дуглас<br>Новые колонисты",
            1187: "Барыга Сет<br>Торговля для экспедиций",
            COURIER: "[2] Курьер",
            1405: "[3] Комиссар Рекс<br>Новые колонисты",
            RAIDER: "[3] Мародёр",
            1019: "[3] Черная Крыса<br>Дикое животное",
            BOX: "Ящик с инструментами",
            115: "Корова", 116: "Корова", 120: "Корова"}
    check("the boss by his full name, and the valley's nameless by theirs",
          {t: names.ALL.get(t) for t in want}, want)
    things = THINGS
    check("the things they leave in a bag by the original's names, not objects.xml's",
          {t: names.ALL.get(items.STRING_ID_OFFSET + t) for t in things}, things)
    check("  ..with the original's descriptions",
          [bool(names.ALL.get(items.DESC_ID_OFFSET + t)) for t in things], [True] * len(things))
    # The table alone is not the tooltip: the client shows a description
    # only if the item's ss_si_* frame points at it (desc), and
    # items.static_info is that frame.
    check("  ..and the frame ss_get_si sends for each points at its description",
          {t: (items.static_info(t) or ("", {}))[1].get("desc") for t in things},
          {t: items.DESC_ID_OFFSET + t for t in things})
    ids = list(want) + [items.STRING_ID_OFFSET + t for t in things] + \
        [items.DESC_ID_OFFSET + t for t in things]
    check("every one of those ids in the table the launcher is handed",
          [("<s id='%d'>" % i).encode() in blob for i in ids], [True] * len(ids))

    def row(i, text):
        return ("<s id='%d'>%s</s>" % (i, text.replace("&", "&amp;").replace(
            "<", "&lt;").replace(">", "&gt;"))).encode("utf-8")
    check("  ..and under those names", [t for t in want if row(t, want[t]) not in blob], [])
except Exception:
    import traceback
    fails.append("the names in process broke:\n" + traceback.format_exc())

# --- in process: nobody by his mobs.xml name ----------------------------------------------
# Every place on a cell inside the owner's wall, and every room its doors and
# quest ways lead into (the barn's adits, the mine's three tiers): whoever the
# room stands there -- the file's own, the hand-placed -- is named, not called
# m05_BanditRaider_lvl3 over his head. Stage 2 made 30 reachable and its three
# raiders were the first to show a player their internal name.
try:
    valley = sorted({i for c, i in world.settlements().items() if world.in_noob_valley(*c)})
    todo, rooms_seen = list(valley), set()
    while todo:
        lid = todo.pop()
        if lid in rooms_seen:
            continue
        rooms_seen.add(lid)
        loc = world.location(lid)
        ways = [travel.door(lid, side) for side in ("a", "b")] + \
            [rec for _cells, rec in travel.quest_ways(loc)]
        for rec in ways:
            to = (rec or {}).get("target_loc_id")
            cell = world.cell_of(int(to)) if to else None
            if to and (cell is None or world.in_noob_valley(*cell)):
                todo.append(int(to))
    internal = {}
    for lid in sorted(rooms_seen):
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            if names.ALL.get(n.type_id, MT[n.type_id][1]) == MT[n.type_id][1]:
                internal.setdefault(n.type_id, set()).add(lid)
    check("the valley's rooms, the adits and the mine's tiers among them",
          (set(valley) | {ADITS, 612, 1011, 1217}) <= rooms_seen and 30 in rooms_seen, True)
    check("nobody in them stands by his mobs.xml name but the one the original has no row for",
          sorted(internal), sorted(NO_ROW))
except Exception:
    import traceback
    fails.append("the internal names in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "valley_world.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("scout", "secret")
_store.close()
CRED = accounts.credential("scout", "secret")
ADMIN_GUN, ROUNDS = 1534, 6092

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(VILLAGE[0]), LAVA_GY=str(VILLAGE[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="3", LAVA_SEED="11", LAVA_QUESTS=QUESTS_FILE)
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)

# A second server, on a placements table with a dog in the peaceful market:
# it must not start at all (server.main asks rooms.check_placements before
# its first socket).
BAD_FILE = os.path.join(tempfile.mkdtemp(), "placements.json")
with open(BAD_FILE, "w", encoding="utf-8") as fh:
    json.dump({"locations": {"185": [dict(type=82, cell=[30, 60], why="a dog in the market")]}},
              fh, ensure_ascii=False)
bad_srv = subprocess.Popen(
    [sys.executable, "server.py"], cwd=HERE,
    env=dict(env, LAVA_PORT=str(free_port()), LAVA_POLICY_PORT="0",
             LAVA_PLACEMENTS=BAD_FILE, LAVA_DB=os.path.join(tempfile.mkdtemp(), "bad.db")),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_bad_log = []
_bad_drain = threading.Thread(target=lambda: _bad_log.extend(bad_srv.stdout), daemon=True)
_bad_drain.start()


def bad_server_outcome(timeout=60):
    end = time.time() + timeout
    while time.time() < end and bad_srv.poll() is None \
            and "game server on" not in "".join(_bad_log):
        time.sleep(0.1)
    code = bad_srv.poll()
    if code is not None:
        _bad_drain.join(timeout=5)
    return code, "".join(_bad_log)


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


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(target_id):
    return "x1%08x" % target_id


def arrive(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, first(got, "lenter").get("pos")


def goto(c, *where):
    """/goto a location id, or a map cell's two numbers: the lcall, then the
    arrival (its frames, the cell stood on)."""
    c.send("userMsg;entry=@/goto %s@;group=0;" % " ".join(str(w) for w in where))
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    got, pos = arrive(c)
    return call, got, pos


def through(c, cell):
    """Stand on an exit cell and take it: chWorld;to=1 (the exit window's
    «other location»). The lcall it answers with, or {}, and the arrival's
    frames."""
    c.send("moveTo;path=|%d|;" % cell)
    c.frames(0.4)
    c.send("chWorld;to=1;")
    call = first(c.until(lambda f: f[0] == "lcall", 2), "lcall")
    got = arrive(c)[0] if call else []
    return call, got


def inhabitants(frames):
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return str(new[0]["obj"]) if new else None


def bag_of(char_id, type_id):
    probe = accounts.Store(DB)
    try:
        return sum(r["count"] for r in probe.items_of(char_id)
                   if r["type_id"] == type_id and r["slot"] == inventory.BAG)
    finally:
        probe.close()


def hunt(c, gun):
    """In 28: shoot the courier from out of his reach until he falls, then
    open his bag. What it holds (type ids), or None if he did not fall."""
    call, got, pos = goto(c, *GONEC)
    here = world.location(28)
    found = inhabitants(got).get(COURIER, [])
    if not found:
        got += c.until(lambda f: f[0] == "userInfo" and f[1].get("name") == COURIER, 8)
        found = inhabitants(got).get(COURIER, [])
    if not found:
        return None
    eid = found[0]
    home = next((p["pos"] for p in named(got, "lch") if p.get("newUser") == eid), None)
    if home is None:
        return None
    reach = mobs.stats(COURIER).aggro
    spots = sorted((mobs.hex_distance(cell, home, here.width), cell)
                   for cell in range(here.width * here.height)
                   if cell not in here.obstacles and cell != home
                   and reach + 0.5 < mobs.hex_distance(cell, home, here.width) <= 12
                   and mobs.line_of_fire(here, cell, home) is None
                   and travel.side_at(here, cell) is None)
    if not spots:
        return None
    pos = spots[0][1]
    c.send("moveTo;path=|%d|;" % pos)
    c.frames(0.5)
    dead = None
    for _ in range(40):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
        got = c.until(lambda f: f[0] == "ss_di_firearm"
                      or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.3)
        if [p for p in named(got, "lch") if p.get("dead") == eid]:
            dead = got
            break
        time.sleep(0.4)
    if dead is None:
        return None
    if not named(dead, "ss_loot"):
        dead += c.until(lambda f: f[0] == "ss_loot", 6)
    where = [p["hex"][0] for p in named(dead, "ss_loot") if p.get("s_status") == 1]
    if not where:
        return None
    c.send("moveTo;path=|%d|;" % where[0])
    c.frames(0.4)
    c.send("ss_create;s_type=0;target=%d;" % where[0])
    if acks(c.frames()) != [0]:
        return None
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    return [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]] if "0" in lst else []


def take_all(c):
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return got


CHAR = None
try:
    code, out = bad_server_outcome()
    check("a server whose placements put a dog in the peaceful market does not start",
          (code not in (None, 0), "game server on" in out), (True, False))
    check("and says which row and why",
          ("loc 185: 82 on 30,60" in out, "a hostile creature in a location at peace" in out),
          (True, True))

    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@scout@;")
    c.frames()
    probe = accounts.Store(DB)
    CHAR = probe.db.execute("SELECT id FROM characters WHERE name = 'scout'").fetchone()["id"]
    probe.close()
    c.send("actPlayer;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    check("a newcomer starts in the Нубийское поселение", call.get("id"), 181)
    got, pos = arrive(c)
    village = world.location(181)

    # --- what the client is told of the valley's things -------------------------------
    # ItemFactory asks ss_get_si for a type the first time a bag or a stall
    # shows it, and the tooltip's text is the desc id of the answer.
    told = {}
    for t in THINGS:
        c.send("ss_get_si;type=%d;" % t)
        frame = [p for p in named(c.until(lambda f: f[0] == "ss_si_simple_obj"
                                          and f[1].get("type") == t, 2), "ss_si_simple_obj")
                 if p.get("type") == t]
        told[t] = (names.text(frame[0].get("name", 0)), frame[0].get("desc")) if frame else None
    check("ss_get_si tells the client each thing's original name and its description id",
          told, {t: (THINGS[t], items.DESC_ID_OFFSET + t) for t in THINGS})

    # --- walked: north to the pasture, and back ---------------------------------------
    call, got = through(c, exit_cell(village, travel.N))
    check("north out of the village is the pasture, 182 on 6268,1818",
          (call.get("id"), call.get("g_id")), (182, world.pack(*PASTURE)))
    here = inhabitants(got)
    check("where the cows are: three to talk to and three grazing",
          (len(here.get(5195, [])), sorted(t for t in here if t in (115, 116, 120))),
          (3, [115, 116, 120]))
    call, got = through(c, exit_cell(world.location(182), travel.S))
    check("and south out of it is the village again", (call.get("id"), call.get("g_id")),
          (181, world.pack(*VILLAGE)))

    # --- on the map's own cells ----------------------------------------------------------
    call, got, pos = goto(c, *GONEC)
    check("the map's «Гонец» opens 28, with the courier in it",
          (call.get("id"), COURIER in inhabitants(got)), (28, True))
    call, got, pos = goto(c, *REX)
    check("«Банда коммисара Рекса» opens 30, with the commissar in it",
          (call.get("id"), 1405 in inhabitants(got)), (30, True))
    here = inhabitants(got)
    check("  ..and his three raiders, each drawn under the name id the table has"
          " «[3] Мародёр» for",
          (len(here.get(RAIDER, [])), names.text(RAIDER)), (3, "[3] Мародёр"))
    check("  ..nobody of 30 shown by his mobs.xml name",
          sorted(t for t in here if names.text(t) == MT[t][1]), [])
    call, got, pos = goto(c, *OLD_CORNER)
    check("the north-west corner opens no cows any more", call.get("id") != 182, True)

    # --- down into the old adits, and back up ---------------------------------------------
    call, got, pos = goto(c, BARN)
    check("in the barn", call.get("id"), BARN)
    call, got = through(c, exit_cell(world.location(BARN), "b"))
    check("its door leads down into the old adits, the black rats' place",
          (call.get("id"), 1019 in inhabitants(got)), (ADITS, True))
    call, got = through(c, exit_cell(world.location(ADITS), "a"))
    check("and their door back up into the barn", call.get("id"), BARN)

    # --- the tools box -------------------------------------------------------------------
    call, got, pos = goto(c, BOX_LOC)
    box = [p for p in named(got, "userInfo_Commoner") if p.get("name") == BOX]
    check("in 184 the tools box stands, a commoner", len(box), 1)
    if box:
        placed = [p for p in named(got, "lch") if p.get("newUser") == box[0]["id"]]
        check("placed on its cell and built as a commoner",
              [(p.get("pos"), p.get("rtype")) for p in placed],
              [(BOX_XY[1] * 64 + BOX_XY[0], world.COMMONER)])
        check("drawn and named as nz_Box, with no «Прописка»",
              [box[0].get(k) for k in ("res", "can_set_home", "can_banking")], [BOX, 0, 0])

    # --- the courier's letter -------------------------------------------------------------
    gun = give(c, ADMIN_GUN)
    rounds = give(c, ROUNDS, 50)
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in c.frames()[0][1]["o_list"]]
    if held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")

    loot = hunt(c, gun)
    check("with no quest the courier falls, and his bag holds no letter",
          (loot is not None, LETTER in (loot or [])), (True, False))
    # Emptied, so that the next corpse opens a bag of its own where it falls
    # (a second corpse on the same cell only fills the first bag up).
    take_all(c)

    call, got, pos = goto(c, 29)
    seiful = inhabitants(got).get(SEIFUL, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (seiful, quests.given_by(SEIFUL).index(LETTER_Q)))
    got = c.frames(0.8)
    check("Сейфул's quest taken, at nought of one",
          (acks(got), [p["obj_num"] for p in named(got, "q_di_bring_l_obj")]), ([0], [[0]]))
    q_id = first(got, "q_di_bring_l_obj").get("q_id", 0)
    time.sleep(3.5)                     # the courier comes back (LAVA_RESPAWN 3)
    loot = hunt(c, gun)
    check("with the quest the courier's bag holds his letter, once",
          (loot or []).count(LETTER), 1)
    got = take_all(c)
    check("taken: the journal counts it, complete",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([1], 1)])
    check("the letter is in the bag", bag_of(CHAR, LETTER), 1)
    time.sleep(3.5)
    loot = hunt(c, gun)
    check("with the letter in the bag, the next courier's bag holds none",
          (loot is not None, LETTER in (loot or [])), (True, False))
    take_all(c)
    call, got, pos = goto(c, 29)
    seiful = inhabitants(got).get(SEIFUL, [0])[0]
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (seiful, q_id))
    got = c.frames(0.8)
    check("handed in to Сейфул: the letter leaves the bag, then the ack",
          (acks(got), bag_of(CHAR, LETTER)), ([0], 0))
    c.send("logout;")
    c.frames(0.5)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    if bad_srv.poll() is None:
        bad_srv.terminate()
        bad_srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-50:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("valley world OK")
