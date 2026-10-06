"""The global map's population, as a watcher's client draws it.

The owner's report: players watching the map sometimes see another player
twice, and their own round trip into a location and back clears it. The
cause is in what the client does with each frame (recon/as-src):

  * GlobalMap.newUser always adds (addPlayer): a new MapObject, and an
    "addPlayer" event on which DisplayGlobalMap attaches a figure and
    GlobalMapInterface lists the name -- whether or not that id already
    has one.
  * GlobalMap.userMove adds only an id it has no player under, and moves
    the one it has otherwise: it is the one idempotent frame.
  * GlobalMap.userLost takes the player out of GlobalMap.playerList and
    kills the MapObject's timer -- and dispatches "removePlayer", which
    neither DisplayGlobalMap nor GlobalMapInterface listens for. The figure
    stays drawn, frozen, and the name stays listed.
  * The one goodbye the client carries out in full is its own timer
    (MapObject.checkLive): with no userMove for more than six ticks of a
    second, "lost" takes the figure (DisplayGlobalMap.lost), the name
    (GlobalMapInterface.lost) and then the player (GlobalMap.removePlayer).

So a server that said goodbye with userLost left a frozen figure behind
every player who went into a location, logged out or walked out of sight,
and drew a second one beside it when that player came back; a fresh
GlobalMap on the watcher's next gmap was the only thing that cleared it.

MapView below keeps one client's map by those rules, fed with the frames a
watcher really receives over a socket, and counts the figures drawn under
each id. A player may be drawn once at most, and not at all once the
client's own timer has had the time to take him off.

Run from server/ with LAVA_RES pointing at the client's res folder.
"""
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ENC = "utf-8"

import accounts   # noqa: E402
import rooms      # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def parse(frame):
    """name, {key: text} of one frame as it travels."""
    parts = frame.rstrip(";").split(";")
    params = {}
    for part in parts[1:]:
        key, _eq, value = part.partition("=")
        params[key] = value
    return parts[0], params


# --- one client's map, by the client's own rules ---------------------------------------------
class MapView:
    """GlobalMap, DisplayGlobalMap and GlobalMapInterface of one client, as
    far as who is drawn goes. Times are seconds, whatever clock the frames
    came in by."""

    # MapObject.startCheckLive: a one-second interval from the figure's
    # birth; startMove zeroes the count, and the tick that takes it past six
    # dispatches "lost".
    TICK = 1.0
    LOST_TICKS = 7

    class Walker:
        def __init__(self, pid, t):
            self.id, self.born, self.reset, self.alive = pid, t, t, True

    def __init__(self):
        # the most figures ever drawn at once under one id, and the frames
        # that did it, for the report
        self.peak = {}
        self.clear()

    def clear(self):
        """Master.gmap builds a new GlobalMap and the scene a new display;
        Master.lenter kills the map. Either way nothing is left drawn."""
        self.walkers = {}      # GlobalMap.playerList
        self.timers = []       # every MapObject whose liveInterval still runs
        self.figures = []      # DisplayGlobalMap's clips, drawn: (id, clip)
        self.latest = {}       # DisplayGlobalMap.playerList: id -> its clip
        self.listed = []       # GlobalMapInterface's user list, by id

    def deadline(self, w):
        ticks_before = math.floor(w.reset - w.born + 1e-9)
        return w.born + (ticks_before + self.LOST_TICKS) * self.TICK

    def advance(self, t):
        """Let every timer that is due by t go off, in order."""
        while True:
            due = [w for w in self.timers if w.alive and self.deadline(w) <= t]
            if not due:
                return
            self.lost(min(due, key=self.deadline))

    def lost(self, w):
        # MapObject.checkLive stops itself; GlobalMap.lost dispatches "lost"
        # with the walker's id, then removes whatever player is under it.
        w.alive = False
        clip = self.latest.pop(w.id, None)
        if clip is not None:
            self.figures.remove((w.id, clip))
        if w.id in self.listed:
            self.listed.remove(w.id)
        current = self.walkers.pop(w.id, None)
        if current is not None:
            current.alive = False

    def add(self, pid, t):
        """GlobalMap.addPlayer: a new walker under the id (an old one is
        replaced in the list, not killed), a figure, a name in the list."""
        w = self.Walker(pid, t)
        self.walkers[pid] = w
        self.timers.append(w)
        clip = object()
        self.figures.append((pid, clip))
        self.latest[pid] = clip
        self.listed.append(pid)
        return w

    def feed(self, t, frame):
        self.advance(t)
        name, p = parse(frame)
        if name in ("gmap", "lenter"):
            self.clear()
        elif name == "newUser" and "dx" in p:
            self.add(int(p["id"]), t)
        elif name == "userMove" and "vx" in p:
            pid = int(p["id"])
            if pid:
                w = self.walkers.get(pid) or self.add(pid, t)
                w.reset = t
        elif name == "userLost":
            w = self.walkers.pop(int(p["id"]), None)
            if w is not None:
                w.alive = False
        for pid in set(i for i, _c in self.figures):
            self.peak[pid] = max(self.peak.get(pid, 0), self.drawn(pid))

    def drawn(self, pid):
        return sum(1 for i, _c in self.figures if i == pid)

    def names(self, pid):
        return self.listed.count(pid)


# --- in process: the room itself, with stand-ins ------------------------------------------------
class Stand:
    """What GlobalMapRoom reads off a session."""

    def __init__(self, pid, x, y, clock):
        self.pid, self.gx, self.gy, self.clock = pid, x, y, clock
        self.nick = "player%d" % pid
        self.leg, self.on_map, self.closed = None, True, False
        self.got = []

    def current_pos(self):
        return self.gx, self.gy

    def send(self, cmd, **params):
        text = cmd + ";" + "".join("%s=%s;" % kv for kv in params.items())
        self.got.append((self.clock[0], text))


def replay(stand):
    """The stand-in's map as its client would have it now."""
    view = MapView()
    view.feed(0.0, "gmap;x=0;y=0;v_rad=8;")
    for t, frame in stand.got:
        view.feed(t, frame)
    view.advance(stand.clock[0])
    return view


class Handle:
    """The heartbeat's timer, driven by hand here instead of by a loop."""

    def cancel(self):
        pass


def in_process():
    print("\nв процессе: радиус, уход без leave()")
    clock = [0.0]
    room = rooms.GlobalMapRoom(8)
    room._arm = lambda: setattr(room, "_timer", Handle())

    def beat(seconds):
        """The heartbeat, one HEARTBEAT at a time, as the loop would run it."""
        end = clock[0] + seconds
        while clock[0] + room.HEARTBEAT <= end + 1e-9:
            clock[0] += room.HEARTBEAT
            room._tick()
        clock[0] = end

    w = Stand(rooms.player_id(1), 100, 100, clock)
    x = Stand(rooms.player_id(2), 101, 100, clock)
    room.enter(w)
    room.enter(x)
    beat(4)
    # Out of sight and straight back, before the watcher's client has had
    # the time to let the figure go.
    x.gx = 130
    beat(2)
    x.gx = 101
    beat(4)
    view = replay(w)
    check("из радиуса и обратно за 2 с: у смотрящего одна фигура, не две",
          view.peak.get(x.pid), 1)
    check("  ..и она на карте", view.drawn(x.pid), 1)
    check("  ..а в списке справа одно имя", view.names(x.pid), 1)
    check("  ..userLost не шлётся вовсе (клиент рисунок по нему не убирает)",
          [f for _t, f in w.got if f.startswith("userLost")], [])

    # Out of sight for long: the watcher's own timer takes the figure off,
    # and coming back draws it once.
    x.gx = 130
    beat(10)
    view = replay(w)
    check("из радиуса надолго: фигуру снимает таймер клиента, призрака нет",
          (view.drawn(x.pid), view.names(x.pid)), (0, 0))
    x.gx = 101
    beat(4)
    view = replay(w)
    check("  ..вернулся: снова одна фигура", (view.drawn(x.pid), view.peak.get(x.pid)), (1, 1))
    news = [f for _t, f in w.got if f.startswith("newUser;id=%d;" % x.pid)]
    check("  ..newUser о нём -- один раз за всё время на карте, дальше только userMove",
          len(news), 1)

    # A way off the map that forgot to say so: the room notices on its own
    # beat, and the silence that follows takes the figure off.
    x.on_map = False
    beat(10)
    view = replay(w)
    check("ушёл с карты мимо leave(): комната сама перестаёт его показывать",
          (x in room.seen, view.drawn(x.pid)), (False, 0))
    x.on_map = True
    room.enter(x)
    beat(4)
    x.closed = True
    closed_at = clock[0]
    beat(10)
    view = replay(w)
    check("закрытый сокет, оставшийся в комнате, тоже снимается",
          (x in room.seen, view.drawn(x.pid)), (False, 0))
    check("  ..и на сам закрытый сокет больше ничего не пишется",
          [f for t, f in x.got if t > closed_at + room.HEARTBEAT], [])
    room.leave(w)
    check("последний ушёл -- таймер карты остановлен", room._timer, None)


try:
    in_process()
except Exception:
    import traceback
    fails.append("in-process part broke:\n" + traceback.format_exc())


# --- in process: map chat follows current visibility ----------------------------
try:
    chat_room = rooms.GlobalMapRoom(8)
    clock = [0.0]
    talker = Stand(rooms.player_id(10), 100, 100, clock)
    near = Stand(rooms.player_id(11), 101, 100, clock)
    edge = Stand(rooms.player_id(12), 108, 100, clock)
    far = Stand(rooms.player_id(13), 108.01, 100, clock)
    diagonal = Stand(rooms.player_id(14), 106, 106, clock)
    inside = Stand(rooms.player_id(15), 100, 100, clock)
    closed = Stand(rooms.player_id(16), 100, 100, clock)
    inside.on_map = False
    closed.closed = True
    peers = (talker, near, edge, far, diagonal, inside, closed)
    # Deliberately stale membership: a heartbeat has not cleaned it yet.
    chat_room.seen = {p: set(peers) for p in peers}
    raw = "^0^map message"
    chat_room.chat(talker, raw)
    check("map chat reaches neighbours and the radius boundary, not distant,"
          " local-scene or closed players; no echo to the sender",
          [len(p.got) for p in peers], [0, 1, 1, 0, 0, 0, 0])
    check("  ..the location channel carries the exact chunk, nick and player id",
          near.got, [(0.0, "userMsg;group=0;nick=%s;entry=%s;from=%d;"
                      % (talker.nick, raw, talker.pid))])
    # Current movement can differ from gx/gy and the cached visibility set.
    near.current_pos = lambda: (108.01, 100)
    chat_room.chat(talker, "out of range")
    check("a listener already beyond the radius hears no more before the next beat",
          len(near.got), 1)
    near.current_pos = lambda: (107.99, 100)
    chat_room.seen[talker].clear()
    chat_room.chat(talker, "back in range")
    check("a listener back in range hears the next line without waiting for a beat",
          len(near.got), 2)
    before = [len(p.got) for p in peers]
    talker.on_map = False
    chat_room.chat(talker, "left the map")
    talker.on_map, talker.closed = True, True
    chat_room.chat(talker, "closed")
    talker.closed = False
    chat_room.seen.pop(talker)
    chat_room.chat(talker, "not on the map")
    check("departed, closed and unregistered senders cannot speak through the map",
          [len(p.got) for p in peers], before)
except Exception:
    import traceback
    fails.append("map chat in process broke:\n" + traceback.format_exc())


# --- on sockets ----------------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "gmap.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for login in ("watcher", "walker", "third"):
    _store.register(login, "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_GX="5970", LAVA_GY="1730", LAVA_POLICY_PORT="0",
           LAVA_ENCOUNTER_CHANCE="0", LAVA_CHEATS="1")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


class Client:
    """A socket read on its own thread, every frame kept with the moment it
    came in, so the map's timers can be replayed against real time."""

    def __init__(self):
        self.s = connect()
        # the connect timeout would end the reader at the first quiet half second
        self.s.settimeout(None)
        self.log = []
        self.lock = threading.Lock()
        self.cursor = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            try:
                chunk = self.s.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            parts = buf.split(b"\x00")
            buf = parts.pop()
            now = time.time()
            with self.lock:
                self.log.extend((now, p.decode(ENC)) for p in parts if p)

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def until(self, pred, timeout=5.0):
        """Frames from the cursor up to the first that pred accepts."""
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                new = self.log[self.cursor:]
            for k, (_t, f) in enumerate(new):
                if pred(f):
                    self.cursor += k + 1
                    return [x for _t, x in new[:k + 1]]
            time.sleep(0.02)
        with self.lock:
            rest = self.log[self.cursor:]
        raise AssertionError("waited in vain; got %r" % [f for _t, f in rest][-8:])

    def drain(self):
        with self.lock:
            self.cursor = len(self.log)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def to_location(c):
    c.until(lambda f: f.startswith("lcall"))
    c.send("lenter;accept=1;")
    c.until(lambda f: f.startswith("lenter"))


def arrive(login, nick, new):
    """Log in and stand in the starting location."""
    c = Client()
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential(login, "secret"))
    c.until(lambda f: f.startswith("accountInfo"))
    if new:
        c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
        c.until(lambda f: f.startswith("cmdAck"))
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    to_location(c)
    return c


def to_map(c):
    c.drain()
    c.send("chWorld;")
    c.until(lambda f: f.startswith("gmap"))


def into_cell(c):
    c.drain()
    c.send("chWorld;")
    to_location(c)


def pid_of(name):
    st = accounts.Store(DB)
    try:
        row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    finally:
        st.close()
    return rooms.player_id(row["id"])


def view_of(c, until=None):
    """The watcher's map as its client has it at `until` (now by default):
    every frame since its last gmap, replayed with the times they came in."""
    until = time.time() if until is None else until
    with c.lock:
        log = list(c.log)
    start = max(k for k, (_t, f) in enumerate(log) if f.startswith("gmap"))
    view = MapView()
    for t, f in log[start:]:
        if t <= until:
            view.feed(t, f)
    view.advance(until)
    return view


def frames_about(c, pid, since):
    with c.lock:
        return [f for t, f in c.log if t >= since and ";id=%d;" % pid in f
                and f.split(";")[0] in ("newUser", "userLost")]


ghost_wait = 8.0   # past the client's 6-7 s timer, with room for the socket

try:
    print("\nна сокетах: смотрящий на карте, ходок уходит и возвращается")
    w = arrive("watcher", "Watcher", True)
    x = arrive("walker", "Walker", True)
    x_pid = pid_of("Walker")
    to_map(w)
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("ходок у смотрящего на карте: одна фигура", view.drawn(x_pid), 1)

    # 1. The owner's case: into the location under the cell and straight out.
    t0 = time.time()
    into_cell(x)
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("1. зашёл в локацию и сразу вышел: фигура одна, не две",
          view.peak.get(x_pid), 1)
    check("  ..и она на карте", view.drawn(x_pid), 1)
    check("  ..имя в списке справа одно", view.names(x_pid), 1)
    check("  ..ни userLost, ни второго newUser",
          frames_about(w, x_pid, t0), [])

    # 2. Into the location and staying there: the watcher's timer takes the
    # figure off, instead of leaving it frozen where he went in.
    t0 = time.time()
    into_cell(x)
    time.sleep(ghost_wait)
    view = view_of(w)
    check("2. зашёл в локацию и остался: на карте смотрящего его больше нет",
          (view.drawn(x_pid), view.names(x_pid)), (0, 0))
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("  ..вышел снова: одна фигура", (view.drawn(x_pid), view.peak.get(x_pid)), (1, 1))

    # 3. Logout on the map, and back in at once on a new socket.
    t0 = time.time()
    x.send("logout;")
    x.close()
    x = arrive("walker", "Walker", False)
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("3. вышел из игры с карты и тут же вернулся на карту: фигура одна",
          (view.drawn(x_pid), view.peak.get(x_pid)), (1, 1))

    # 4. A second login kicking the first off the map.
    x2 = arrive("walker", "Walker", False)
    x.close()
    x = x2
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("4. второй вход выбил первый прямо с карты: фигура одна",
          (view.drawn(x_pid), view.peak.get(x_pid)), (1, 1))

    # 5. /home from the map, and back out.
    x.drain()
    x.send("userMsg;entry=@/home@;group=0;")
    to_location(x)
    to_map(x)
    time.sleep(2.5)
    view = view_of(w)
    check("5. /home с карты и обратно: фигура одна",
          (view.drawn(x_pid), view.peak.get(x_pid)), (1, 1))

    # 6. A dropped socket on the map: the figure goes by the watcher's timer.
    x.close()
    time.sleep(ghost_wait)
    view = view_of(w)
    check("6. сокет оборвался на карте: фигура уходит, призрака нет",
          (view.drawn(x_pid), view.names(x_pid)), (0, 0))

    # 7. A third player coming onto the map while the watcher looks: once.
    y = arrive("third", "Third", True)
    y_pid = pid_of("Third")
    to_map(y)
    into_cell(y)
    to_map(y)
    time.sleep(2.5)
    view = view_of(w)
    check("7. новый игрок пришёл, зашёл-вышел: одна фигура",
          (view.drawn(y_pid), view.peak.get(y_pid)), (1, 1))

    # 8. Into the cell in the middle of a walk: the ways in drop the leg
    # first (Session.cancel_travel), so without a word the figure would walk
    # on at the watcher's until his timer ran out. It stops where the leg
    # had brought him, and then goes like any other.
    y.drain()
    y.send("moveTo;dx=-300;dy=0;")
    y.until(lambda f: f.startswith("moveAck"))
    time.sleep(1.2)
    t0 = time.time()
    into_cell(y)
    time.sleep(2.5)
    with w.lock:
        about = [f for t, f in w.log if t >= t0 and ";id=%d;" % y_pid in f]
    last = parse(about[-1])[1] if about else {}
    # a beat of the walk itself may just precede the chWorld; only it
    check("8. зашёл в клетку на ходу: смотрящему -- остановка (userMove с нулевой"
          " скоростью), и больше о нём ничего",
          (sum(";vx=0;vy=0;" in f for f in about), last.get("vx"), last.get("vy")),
          (1, "0", "0"))
    check("  ..там, куда он успел дойти: запад от 5970 на треть клетки с лишним",
          5969.3 < float(last.get("dx", 0)) < 5969.7 and last.get("dy") == "1730", True)
    time.sleep(ghost_wait - 2.5)
    view = view_of(w)
    check("  ..и фигура уходит по таймеру клиента", view.drawn(y_pid), 0)
    to_map(y)
    time.sleep(2.5)
    view = view_of(w)
    check("  ..вышел снова: одна фигура", (view.drawn(y_pid), view.peak.get(y_pid)), (1, 1))

    # The watcher's own round trip: a new map, the players on it once each.
    into_cell(w)
    to_map(w)
    time.sleep(2.5)
    view = view_of(w)
    check("своя дорога в локацию и обратно: карта заново, игрок на ней один раз",
          (view.drawn(y_pid), view.drawn(x_pid)), (1, 0))
    for c in (w, y):
        c.send("logout;")
        c.close()
except AssertionError:
    import traceback
    fails.append("socket scene stopped:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("global map presence OK")
