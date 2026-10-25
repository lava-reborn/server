"""A walk-in passage held shut by a fight, and a login on one; and the
quest that is the mine's way out now, held by the same holds.

A walk-in is a cell with no zone where the server itself moves a player
whose walk ends there. No place in the world has one any more: the Nubian
mine's mouth and its EXIT sign were the two, and the quests of Рудо and
Камал took over (test_mine). The mechanism stays for the next place that
needs it, and this suite keeps it honest on a table of its own: the real
data/passages.json with the mine's two walk-ins put back, handed to the
server and to this process through LAVA_PASSAGES. A fight holds a walk-in
shut, as it holds chWorld. What is held to here:

  * held is not refused: a player who stays on the cell goes through by
    himself the moment the fight lets him -- one lcall, no cmdAck -- because
    the client sends no walk to the cell its figure already stands on
    (Location.movePlayer), so "stepping on it again" is not something he
    can do without stepping off first;
  * the line in chat says a fight holds him -- a duel here (the mine's
    tiers are pvp="1") -- with the seconds its exit timer has left: the
    countdown a hit given or taken starts, the one chWorld is held to;
  * the wait ends with a step off the cell, and with death: a corpse on
    the way out is not carried through it;
  * a heal of the player's own still in the air holds the way too, without
    a word, until it lands: the lcall would cut it short;
  * reconnecting to a body on a walk-in leaves it on the same cell and
    takes no passage. The cancelled passage is not rearmed until the player
    steps off and back onto it. A login after the body expires still uses
    the saved-position rule that places the player beside the passage.

Камал's quest, "Выведи меня отсюда", is a quest in two steps: taken, it is
journalled, and handed back to him it brings the player up. The same things
hold it, and hold it the same way -- not the take, which moves nobody, and
not the hand-in, which the client would word as the daily limit if it were
refused, but the move behind it:

  * struck by a player, he takes the quest and hands it in: the ack, the
    timer's seconds in chat, and he goes up by himself once they run out --
    one lcall, no cmdAck; a second hand-in while he waits is a new wait,
    not a second move;
  * leaving the room ends the wait (a /goto here), and so do death -- the
    dead one's hand-in is refused, and his resurrection is the one thing
    that moves him -- and a dropped socket: the login takes him nowhere,
    and the quest, handed in, is not in the journal to hand in again;
  * a bandage of his own in the air holds it without a word until it lands.

The creature's hold on it is test_mine's. The table here also names Рудо's
quest as a way from another place than the mouth he stands at -- a table
behind an inhabitant who was moved -- and his quest is then refused where
he gives it, with a word, and not taken into the journal: handed in there,
it would lead nowhere.

Two players: the brawler strikes until a blow lands -- a miss starts no
timer, on the client or here -- and the stayer is struck and walks for the
EXIT sign. The exit timer is cut to a few seconds (LAVA_LEAVE_COMBAT) to
keep the run short.

Written against the code that moved the player at the take, it fails at
the first of Камал's quests -- refused in the duel with res=39, nothing
journalled, so nothing to hand in -- and at every hold of it after (7
checks), and the run breaks at the corpse: the refusals have used up the
duel's seconds, and the walk-in carries him up before the gun finds him.
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
ENC = "utf-8"

# The table this suite runs on, set before anything asks travel for a way.
# The two walk-ins are the mine's as they were: the end of the rails at the
# mouth, and the cells under the first tier's EXIT sign.
FIXTURE_WALK_INS = {
    "153": [{"cells": [[47, 24], [48, 24], [46, 25], [47, 25], [48, 25], [47, 26],
                       [48, 26]],
             "target_loc_id": 612,
             "why": "DESIGNED, for server/test_walk_in.py only: the end of the rails."}],
    "612": [{"cells": [[49, 19], [48, 20], [49, 20], [50, 20]],
             "target_loc_id": 153,
             "why": "DESIGNED, for server/test_walk_in.py only: under the EXIT sign."}],
}
with open(os.path.join(os.path.dirname(HERE), "data", "passages.json"),
          encoding="utf-8") as fh:
    TABLE = json.load(fh)
TABLE["walk_in"] = FIXTURE_WALK_INS
# And Рудо's quest named as a way out of the second tier, 1011, where he
# does not stand: a table that has not caught up with an inhabitant who was
# moved. Nothing else reads that row -- 1011 is never visited here, and
# nobody arrives by it: both sides of the mine are arrived at by the
# walk-ins above.
FIXTURE_ELSEWHERE = "1011"
TABLE["quest"] = {(FIXTURE_ELSEWHERE if key == "153" else key): rows
                  for key, rows in TABLE["quest"].items()}
PASSAGES = os.path.join(tempfile.mkdtemp(), "passages.json")
with open(PASSAGES, "w", encoding="utf-8") as fh:
    json.dump(TABLE, fh, ensure_ascii=False)
os.environ["LAVA_PASSAGES"] = PASSAGES

sys.path.insert(0, HERE)
import accounts   # noqa: E402
import items      # noqa: E402
import mobs       # noqa: E402
import progression  # noqa: E402
import rooms      # noqa: E402
import travel     # noqa: E402
import world      # noqa: E402
from protocol import decode  # noqa: E402


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "walk_in.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("brawler", "secret")
_store.register("stayer", "secret")
_store.close()
CRED_A = accounts.credential("brawler", "secret")
CRED_B = accounts.credential("stayer", "secret")

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


MOUTH, TIER1 = 153, 612
MOUTH_CELL = (6273, 1829)
RUDO, KAMAL = 1133, 1134
OLD_ADITS = 57      # Шульц's «Старые штольни»: Рудо's way down is offered after it
DOWN, UP = 7, 8     # Рудо's quest, "Отправка в шахту"; Камал's, "Выведи меня отсюда"
ADMIN_GUN, ROUNDS = 1534, 6092
HOLD = 4            # LAVA_LEAVE_COMBAT for this run, seconds
RETRY = 1.0         # server.PASSAGE_RETRY
NOT_AVAILABLE = 4   # server.RES_NOT_AVAILABLE: a quest way leading nowhere from here
NOWHERE_LINE = "Это задание никуда не ведёт"
DUEL_LINE = re.compile(r"^Идёт бой: пройдёте через (\d+) с$")
QUEST_DUEL_LINE = re.compile(r"^Идёт бой: отправитесь через (\d+) с$")
# The first heal of the catalogue, as test_combat takes it; it has to take
# longer than the one-step walk under the sign for the heal to be in the air.
BANDAGE = next(t for t, (root, _) in sorted(items.catalogue().items())
               if root == items.HEAL and items.params_of(t) is not None)
BANDAGE_S = items.params_of(BANDAGE)["heal_time"] / 1000.0
assert BANDAGE_S > travel.walk_seconds(2) + 0.3, BANDAGE_S

mouth, tier1 = world.location(MOUTH), world.location(TIER1)
INTO = {c for cells, _ in travel.walk_ins(mouth) for c in cells}
OUT = {c for cells, _ in travel.walk_ins(tier1) for c in cells}
check("the suite runs on its own table, with the mine's walk-ins put back",
      (getattr(travel, "passages_path", lambda: None)(), len(INTO), len(OUT)),
      (PASSAGES, 7, 4))
check("and with Рудо's quest a way from the second tier, not from where he stands",
      (travel.quest_way(mouth, DOWN),
       travel.quest_way(world.location(int(FIXTURE_ELSEWHERE)), DOWN) is not None),
      (None, True))
# Where a player comes out of the mine, and where he comes down into it.
ALCOVE = {c for c in mouth.entries
          if 42 <= c % mouth.width <= 49 and 22 <= c // mouth.width <= 31}
POCKET = {c for c in tier1.entries if c % tier1.width >= 48 and c // tier1.width <= 26}

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(MOUTH_CELL[0]), LAVA_GY=str(MOUTH_CELL[1]),
           LAVA_LEAVE_COMBAT=str(HOLD), LAVA_AP_REGEN="25", LAVA_RESPAWN="600",
           LAVA_SEED="7")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


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

    def drop(self):
        """The socket goes without a logout, as a lost connection does."""
        self.s.close()


def named(frames, name):
    return [p for n, p in frames if n == name]


def lines(frames):
    """What the server said in chat, in order."""
    return [p["entry"] for p in named(frames, "userMsg") if p.get("nick") == "Сервер"]


def calls(frames):
    return [p["id"] for p in named(frames, "lcall")]


def entity(eid):
    return "x1%08x" % eid


def enter(c):
    """lenter;accept=1: (all frames, the cell the player stands on)."""
    c.send("lenter;accept=1;")
    got = c.frames(wait=1.5)
    return got, named(got, "lenter")[0]["pos"]


def log_in(cred, nick=None):
    """A fresh socket up to the first lcall: a new character when nick is
    given, the existing one (slot 0) otherwise."""
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    if nick:
        c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    got = c.until(lambda f: f[0] == "lcall")
    return c, calls(got)


def send_walk(c, loc, start, goal):
    """A real path to the nearest goal cell, sent as the client sends it."""
    path = mobs.find_path(loc, start, goal)
    if path is None:
        raise RuntimeError("no path from %d in %d" % (start, loc.id))
    if len(path) < 2:
        # Location.movePlayer sends nothing for the cell the figure is on.
        raise RuntimeError("already standing on %d in %d: the client has no walk"
                           " to send" % (start, loc.id))
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    return path


def step_off(c, loc, pos, way):
    """One step off the way through, onto ground that is not part of it.

    What the code before this change asked of a player it had left standing
    on a walk-in; only a run against that code comes this way, and it keeps
    the later sections of such a run reporting instead of breaking on the
    first."""
    off = next(n for n in progression.hex_neighbours(pos, loc.width, loc.height)
               if n not in loc.obstacles and n not in way)
    c.send("moveTo;path=|%d|%d|;" % (pos, off))
    c.frames(0.5)
    return off


# Камал's entity id in the first tier: the room keeps its inhabitants' ids
# (rooms.Rooms), so the first sight of him serves the whole run.
KAMAL_ID = {}


def into_mine(c, pos):
    """From the alcove to the mouth and down: the cell arrived on."""
    path = send_walk(c, mouth, pos, lambda cell: cell in INTO)
    got = c.until(lambda f: f[0] == "lcall", 0.2 * len(path) + 3)
    if calls(got) != [TIER1]:
        raise RuntimeError("the mine did not open: %r" % calls(got))
    arrival, pos = enter(c)
    for p in named(arrival, "userInfo_Commoner"):
        if p["name"] == KAMAL:
            KAMAL_ID["id"] = p["id"]
    return pos


def take_kamal(c):
    """"Взять задание" at Камал on his way out, the first quest he gives,
    q_idx 0: (the frames up to its q_di and a moment more, its q_id or 0)."""
    c.send("q_st;mob=%d;q_idx=0;" % KAMAL_ID["id"])
    got = c.until(lambda f: f[0].startswith("q_di") or f[0] == "lcall", 2) + c.frames(0.3)
    di = [p for p in named(got, "q_di_del_obj") if p.get("q_type") == UP]
    return got, (di[0]["q_id"] if di else 0)


def hand_in_kamal(c, q_id):
    """The hand-in button at Камал: q_co, as QuestInspector.takeQuest sends it."""
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (KAMAL_ID["id"], q_id))


def journal(c):
    c.send("q_list;")
    return [(p["q_id"], p["q_types"]) for p in named(c.frames(), "q_list")]


def strike(a, b, pid):
    """The brawler's fist at the stayer until a blow lands: a hit starts the
    exit timer of both of them, the one who struck as much as the one who
    was struck, and a miss starts nothing (the client's countdown runs from
    faHit and caHit alone). The stayer's side of it is read off his socket
    here, so that what follows is only his walk. Returns when the hit
    landed."""
    a.frames(0.2)
    for _ in range(25):
        a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid))
        got = a.until(lambda f: f[0] in ("caHit", "caMiss"), 3)
        if named(got, "caHit"):
            break
    check("the fist is swung, and lands",
          (named(got, "cmdAck")[:1], bool(named(got, "caHit"))), ([{"res": 0}], True))
    at = time.time()
    b.frames(0.3)
    return at


def run_for_exit(b, pos):
    """The stayer walks for the EXIT sign: (the path, the frames up to the
    server's answer or a second past the figure's arrival)."""
    path = send_walk(b, tier1, pos, lambda cell: cell in OUT)
    echo = b.until(lambda f: f[0] == "userMove", 1)
    check("the walk for the sign is echoed like any other",
          [(n, p.get("path")) for n, p in echo if n in ("cmdAck", "userMove")],
          [("cmdAck", None), ("userMove", path)])
    got = b.until(lambda f: f[0] in ("userMsg", "lcall"), travel.walk_seconds(len(path)) + 1)
    return path, got


try:
    a, first = log_in(CRED_A, "brawler")
    check("the brawler starts at the mine's mouth", first, [MOUTH])
    # A marksman's hand, for the death below: the admin gun kills what it
    # hits, but only a hit holds the one it is fired at -- a miss starts no
    # exit timer -- so it has to find him before the seconds of the blow that
    # held him run out. Стрельба 50 puts the chance past a hundred.
    a.send("logout;")
    a.frames(0.3)
    a.s.close()
    _st = accounts.Store(DB)
    _ch = progression.Character.load(_st, _st.character_by_name("brawler")["id"])
    _ch.skill[progression.SHOOTING] = [50, 0, progression.skill_xp_max(50)]
    _ch.recalc()
    _ch.save(_st)
    _st.close()
    a, first = log_in(CRED_A)
    check("and is back there, a marksman now", first, [MOUTH])
    _, pos_a = enter(a)
    b, first = log_in(CRED_B, "stayer")
    arrival, pos_b = enter(b)
    a.frames(0.5)
    pid_b = rooms.player_id(2)
    # Шульц's errand to Рудо done a day ago, so that it is the way, not the
    # chain before it (need_any), that refuses the take below.
    _st = accounts.Store(DB)
    _st.finish_quest(0, _st.character_by_name("stayer")["id"], OLD_ADITS,
                     when=int(time.time()) - 86400)
    _st.close()

    # --- Рудо's quest, a way the table names for another place ------------------
    # Handed back to Рудо here, it would lead nowhere, so it would sit in the
    # journal for good: where the table has no row for it, the take is
    # refused, with a word, nothing is journalled and nothing moves.
    rudo = next((p["id"] for p in named(arrival, "userInfo_Commoner")
                 if p["name"] == RUDO), None)
    check("Рудо stands at the mouth", rudo is not None, True)
    b.send("q_st;mob=%d;q_idx=0;" % rudo)
    got = b.until(lambda f: f[0] == "userMsg", 1) + b.frames(0.3)
    check("his quest, a way from somewhere else: refused, with a word, nobody moves",
          ([p.get("res") for p in named(got, "cmdAck")], lines(got), calls(got),
           [n for n, _ in got if n.startswith("q_di")]),
          ([NOT_AVAILABLE], [NOWHERE_LINE], [], []))
    b.send("q_list;")
    check("and it is not taken into the journal",
          named(b.frames(), "q_list"), [{"q_id": [], "q_types": []}])

    # The brawler's admin gun, for the death below: it kills what it hits.
    gun = rounds = None
    for label, cmd in (("gun", "/give %d" % ADMIN_GUN), ("rounds", "/give %d 50" % ROUNDS)):
        a.send("userMsg;entry=@%s@;group=0;" % cmd)
        got = a.until(lambda f: f[0] == "userMsg")
        obj = str(named(got, "ss_obj_status")[0]["obj"])
        gun, rounds = (obj, rounds) if label == "gun" else (gun, obj)
    a.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in next(p["o_list"] for _, p in a.frames() if "o_list" in p)]
    if held[6] != "0":
        a.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        a.frames()
    a.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    a.frames()
    a.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    got = a.until(lambda f: f[0] == "ss_di_firearm")
    check("the brawler's gun is loaded", named(got, "ss_di_firearm")[-1]["ammo_count"] > 0, True)
    # And the stayer's purse, for a resurrection that does not wait.
    b.send("userMsg;entry=@/money 2000@;group=0;")
    b.until(lambda f: f[0] == "userMsg")

    # --- a socket dropped on the way into the mine ----------------------------
    path = send_walk(b, mouth, pos_b, lambda cell: cell in INTO)
    b.drop()
    time.sleep(0.3)
    b, first = log_in(CRED_B)
    check("the stayer, back, is called into the place he never left", first, [MOUTH])
    got, pos_b = enter(b)
    check("not onto the mouth of the mine his last walk ended on",
          (path[-1] in INTO, pos_b in INTO), (True, False))
    check("but beside it, in the alcove at the rails' end", pos_b in ALCOVE, True)
    got += b.frames(travel.walk_seconds(len(path)) + RETRY + 0.5)
    check("and the login takes him nowhere by itself", calls(got), [])
    if pos_b in INTO:
        pos_b = step_off(b, mouth, pos_b, INTO)
    pos_b = into_mine(b, pos_b)
    check("one walk from there takes him down", pos_b in POCKET, True)

    pos_a = into_mine(a, pos_a)
    b.frames(0.5)
    check("the two come down side by side", pos_a, pos_b)
    spot = next(n for n in progression.hex_neighbours(pos_b, tier1.width, tier1.height)
                if n not in tier1.obstacles and n not in OUT)
    a.send("moveTo;path=|%d|%d|;" % (pos_a, spot))
    a.frames(0.5)
    b.frames(0.2)
    pos_a = spot

    # --- held by a duel, let out by itself -------------------------------------
    struck = strike(a, b, pid_b)
    path, got = run_for_exit(b, pos_b)
    pos_b = path[-1]
    check("struck by a player, the stayer is not let out", calls(got), [])
    said = lines(got)
    left = [int(m.group(1)) for m in map(DUEL_LINE.match, said[:1]) if m]
    check("and is told it is a duel, with the seconds it has left",
          (len(said), [0 < s <= HOLD for s in left]), (1, [True]))
    rest = b.until(lambda f: f[0] == "lcall", HOLD + RETRY + 2)
    took = time.time() - struck
    check("staying under the sign, he goes up once the duel lets him",
          calls(rest), [MOUTH])
    check("not before", took >= HOLD - 0.5, True)
    check("by an lcall alone: the client asked for nothing it could be an answer to",
          [n for n, _ in rest if n == "cmdAck"], [])
    check("and was told why once, not once a second", lines(rest), [])
    if not calls(rest):
        pos_b = step_off(b, tier1, pos_b, OUT)
        path = send_walk(b, tier1, pos_b, lambda cell: cell in OUT)
        b.until(lambda f: f[0] == "lcall", travel.walk_seconds(len(path)) + 2)
    got, pos_b = enter(b)
    check("up at the mouth, in the alcove", pos_b in ALCOVE, True)
    got += b.frames(RETRY + 0.5)
    check("and there it ends: nothing calls him anywhere again", calls(got), [])

    # --- a step off the cell ends the wait --------------------------------------
    pos_b = into_mine(b, pos_b)
    strike(a, b, pid_b)
    path, got = run_for_exit(b, pos_b)
    pos_b = path[-1]
    check("held again", (calls(got), len(lines(got))), ([], 1))
    # One step back the way he came: off the sign, and still in sight of it.
    back = path[-2]
    b.send("moveTo;path=|%d|%d|;" % (pos_b, back))
    pos_b = back
    got = b.frames(HOLD + RETRY + 1)
    check("a step away from the sign, and the duel's end lets nobody out",
          (calls(got), lines(got)), ([], []))
    path = send_walk(b, tier1, pos_b, lambda cell: cell in OUT)
    got = b.until(lambda f: f[0] == "lcall", travel.walk_seconds(len(path)) + 2)
    check("a walk back under it, the duel over, goes up at once",
          (calls(got), lines(got)), ([MOUTH], []))
    _, pos_b = enter(b)

    # --- Камал's quest in a duel: taken, handed in, held, let out -----------------
    # The way out the mine has now. A fight refuses no take -- taking the
    # quest moves nobody -- and no hand-in, which the client would word as
    # the daily limit: it holds the move, and lets it go by itself once the
    # duel's seconds run out, as the walk-in does.
    pos_b = into_mine(b, pos_b)
    check("Камал stands in the first tier", "id" in KAMAL_ID, True)
    struck = strike(a, b, pid_b)
    got, q = take_kamal(b)
    check("struck by a player, he takes Камал's quest: the ack and the quest, nobody moves",
          ([p.get("res") for p in named(got, "cmdAck")],
           [(p["q_type"], p["complete"]) for p in named(got, "q_di_del_obj")],
           calls(got), lines(got)),
          ([0], [(UP, 1)], [], []))
    hand_in_kamal(b, q)
    got = b.until(lambda f: f[0] == "userMsg", 2)
    said = lines(got)
    left = [int(m.group(1)) for m in map(QUEST_DUEL_LINE.match, said[:1]) if m]
    check("and hands it back: accepted, and held, with the duel's seconds in chat",
          ([p.get("res") for p in named(got, "cmdAck")], len(said),
           [0 < s <= HOLD for s in left], calls(got)),
          ([0], 1, [True], []))
    # Taken and handed in again while he waits: a new wait in place of the
    # old one, not a second move behind the first.
    got, q = take_kamal(b)
    hand_in_kamal(b, q)
    got += b.until(lambda f: f[0] == "userMsg", 2)
    check("taken and handed in again while he waits: accepted, and held the same",
          ([p.get("res") for p in named(got, "cmdAck")], len(lines(got)), calls(got)),
          ([0, 0], 1, []))
    rest = b.until(lambda f: f[0] == "lcall", HOLD + RETRY + 2)
    took = time.time() - struck
    rest += b.frames(RETRY + 1)
    check("the duel over, he goes up by himself, once", calls(rest), [MOUTH])
    check("not before", took >= HOLD - 0.5, True)
    check("by an lcall alone: the ack was the hand-in's",
          [n for n, _ in rest if n == "cmdAck"], [])
    check("and was told why once a hand-in, not once a second", lines(rest), [])
    got, pos_b = enter(b)
    check("up at the mouth, in the alcove, by Камал's hand", pos_b in ALCOVE, True)
    check("with nothing left in the journal", journal(b), [([], [])])

    # --- leaving the room ends the wait ------------------------------------------
    pos_b = into_mine(b, pos_b)
    strike(a, b, pid_b)
    got, q = take_kamal(b)
    hand_in_kamal(b, q)
    got = b.until(lambda f: f[0] == "userMsg", 2)
    check("held again", ([p.get("res") for p in named(got, "cmdAck")], len(lines(got)),
                         calls(got)), ([0], 1, []))
    b.send("userMsg;entry=@/goto %d@;group=0;" % MOUTH)
    got = b.until(lambda f: f[0] == "lcall", 2)
    check("a /goto takes him out of the room while he waits", calls(got), [MOUTH])
    got, pos_b = enter(b)
    got += b.frames(HOLD + RETRY + 0.5)
    check("and the duel's end sends him nowhere after it", (calls(got), lines(got)), ([], []))

    # --- nor is a corpse carried through ----------------------------------------
    pos_b = into_mine(b, pos_b)
    strike(a, b, pid_b)
    got, q = take_kamal(b)
    hand_in_kamal(b, q)
    got = b.until(lambda f: f[0] == "userMsg", 2)
    check("Камал's quest handed in, and held", ([p.get("res") for p in named(got, "cmdAck")],
                                              len(lines(got))), ([0], 1))
    path, got = run_for_exit(b, pos_b)
    pos_b = path[-1]
    check("held under the sign as well", (calls(got), len(lines(got))), ([], 1))
    for attempt in range(20):
        a.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(pid_b)))
        got = a.until(lambda f: f[0] == "lch" and f[1].get("dead") == pid_b, 1.5)
        if [p for p in named(got, "lch") if p.get("dead") == pid_b]:
            break
    else:
        raise RuntimeError("the admin gun never brought the stayer down")
    seen = b.frames(HOLD + RETRY + 1)
    check("killed under the sign, he lies there: the duel's end moves nobody",
          ([p for p in named(seen, "lch") if p.get("dead") == 0][:1], calls(seen)),
          ([{"dead": 0}], []))
    # The client sends nothing but resurrect while dead; a q_st or a q_co
    # that comes anyway is a modified client's, and the dead filter answers
    # it.
    got, _q = take_kamal(b)
    hand_in_kamal(b, q)
    got += b.frames(0.8)
    check("nor does Камал's quest carry a corpse out: take and hand-in refused, nobody moves",
          ([bool(p.get("res")) for p in named(got, "cmdAck")], calls(got)), ([True, True], []))
    b.send("resurrect;res_type=2;")
    got = b.until(lambda f: f[0] == "lcall", 2) + b.frames(RETRY + 0.5)
    check("his resurrection is the one thing that moves him, once",
          (named(got, "cmdAck")[:1], calls(got)), ([{"res": 0}], [MOUTH]))
    _, pos_b = enter(b)

    # --- a socket dropped under the sign ----------------------------------------
    pos_b = into_mine(b, pos_b)
    strike(a, b, pid_b)
    got, q = take_kamal(b)
    hand_in_kamal(b, q)
    b.until(lambda f: f[0] == "userMsg", 2)
    path, got = run_for_exit(b, pos_b)
    pos_b = path[-1]
    check("held under the sign when the socket goes, Камал's quest handed in and held too",
          (calls(got), len(lines(got))), ([], 1))
    left_on = pos_b
    b.drop()
    time.sleep(HOLD + RETRY)
    b, first = log_in(CRED_B)
    check("back, he is in the mine still", first, [TIER1])
    got, pos_b = enter(b)
    check("reconnected to the same body under the sign, without moving it",
          (pos_b, pos_b in OUT), (left_on, True))
    got += b.frames(RETRY + 1)
    check("and not carried out by the login", calls(got), [])
    check("nor is the quest he handed in there to hand in twice", journal(b), [([], [])])
    if pos_b in OUT:
        pos_b = step_off(b, tier1, pos_b, OUT)
    path = send_walk(b, tier1, pos_b, lambda cell: cell in OUT)
    got = b.until(lambda f: f[0] == "lcall", travel.walk_seconds(len(path)) + 2)
    check("one walk under the sign takes him up", calls(got), [MOUTH])
    _, pos_b = enter(b)

    # --- nor is a heal of his own cut short ---------------------------------------
    # A quest transition waits for the pending heal. An accepted walk now
    # cancels it, so walking under the sign transitions without a late heal.
    def bandage_on(c):
        c.send("userMsg;entry=@/give %d@;group=0;" % BANDAGE)
        got = c.until(lambda f: f[0] == "userMsg")
        oid = str(named(got, "ss_obj_status")[0]["obj"])
        c.frames(0.3)
        c.send("ss_use;type=2;obj=x%s;" % oid)
        return named(c.until(lambda f: f[0] == "cmdAck", 1), "cmdAck")

    pos_b = into_mine(b, pos_b)
    got, q = take_kamal(b)
    check("a bandage on himself, acknowledged at once", bandage_on(b), [{"res": 0}])
    hand_in_kamal(b, q)
    got = b.until(lambda f: f[0] == "lcall", BANDAGE_S + RETRY + 2) + b.frames(0.3)
    check("Камал's quest handed in with the bandage still on: accepted; it lands,"
          " then he goes up, without a word",
          ([p.get("res") for p in named(got, "cmdAck")][:1],
           [n for n, _ in got if n in ("heal", "lcall")], calls(got), lines(got)),
          ([0], ["heal", "lcall"], [MOUTH], []))
    _, pos_b = enter(b)
    pos_b = into_mine(b, pos_b)
    check("a bandage on himself again", bandage_on(b), [{"res": 0}])
    path, got = run_for_exit(b, pos_b)
    if not calls(got):
        got += b.until(lambda f: f[0] == "lcall", BANDAGE_S + RETRY + 2)
    check("walking under the sign cancels the bandage and goes up without a late heal",
          ([n for n, _ in got if n in ("heal", "lcall")], calls(got), lines(got)),
          (["lcall"], [MOUTH], []))

    a.send("logout;")
    b.send("logout;")
    a.frames(0.3)
    b.frames(0.3)
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
        fails.append("server log, commands and notes:\n" + "\n".join(story[-50:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("walk-in OK")
