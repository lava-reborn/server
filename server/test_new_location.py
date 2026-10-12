"""A new place made from a copy, walked into on the real server and out again.

tools/new_location.py makes a location of ours: the copy of an interior
under the first free id from 1381 (data/locations/static/<id>.xml, its row
in index.json and in exits_sides.json), a walk-in into it from an original
location -- whose own file is not touched -- and its door back
(data/passages.json). Here it writes into a copy of data/, and the server is
started on that copy (LAVA_LOC_OVERLAY, LAVA_PASSAGES), as a deploy would
start it on the repository's:

  * the tool's refusals: an id of the original's, a walk-in on a wall or on
    an exit, a door the copy has not;
  * the rows it writes, every other byte of the tables kept;
  * travel resolves the ways both ways (plan_walk_in, plan_exit);
  * a player walks from Вади-Хальфа's black market (102) onto the walk-in
    and is called into the new place, arriving beside its door; walks to the
    door and goes through it, back beside the walk-in;
  * left saved on a cell the place has a wall on now (a location of ours
    may change under a player who logged out in it), a login stands him on
    the entry instead (Session.restore).

    python3 server/test_new_location.py
"""
import collections
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"

W = tempfile.mkdtemp(prefix="test-new-location-")
DATA = os.path.join(W, "data")
os.makedirs(DATA)
for name in ("passages.json", "exits_sides.json"):
    shutil.copy(os.path.join(ROOT, "data", name), os.path.join(DATA, name))
shutil.copytree(os.path.join(ROOT, "data", "locations"), os.path.join(DATA, "locations"))
# This process reads what the server will: set before anything asks.
os.environ["LAVA_LOC_OVERLAY"] = os.path.join(DATA, "locations")
os.environ["LAVA_PASSAGES"] = os.path.join(DATA, "passages.json")

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "data"))
import accounts  # noqa: E402
import build_exits_sides as B  # noqa: E402
import lavaloc  # noqa: E402
import mobs  # noqa: E402
import new_location  # noqa: E402
import progression  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402
import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "a location of ours, walked into"

SRC, FROM = 673, 102          # «Минибункер», 32x64 with door a; the black market
FROM_CELL = (5970, 1730)
TITLE = "Тайник"


def tool(*args, data=DATA):
    """(exit code, its JSON or its refusal)."""
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "new_location.py")] + list(args)
                       + ["--data", data, "--author", "test", "--why", "for server/test_new_location.py"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    return p.returncode, (json.loads(p.stdout) if p.returncode == 0 else p.stderr.strip())


def reach(loc, start):
    """{cell: steps} of the free cells a walk from start reaches."""
    seen = {start: 0}
    todo = collections.deque([start])
    while todo:
        c = todo.popleft()
        for n in progression.hex_neighbours(c, loc.width, loc.height):
            if n not in seen and n not in loc.obstacles:
                seen[n] = seen[c] + 1
                todo.append(n)
    return seen


srv = None
try:
    # --- where the walk-in goes: two free cells of the market, a few steps in ----------------
    market = world.location(FROM)
    exits = travel.exit_sides(market)
    steps = reach(market, market.entry_cell())
    pick = [c for c, n in sorted(steps.items(), key=lambda kv: (kv[1], kv[0]))
            if n >= 4 and c not in exits and c not in market.entries]
    a = pick[0]
    b = next(n for n in progression.hex_neighbours(a, market.width, market.height)
             if n in steps and n not in exits and n not in market.entries and n != a)
    WALK = {a, b}
    spec = "%d:%s" % (FROM, ";".join("%d,%d" % (c % market.width, c // market.width) for c in sorted(WALK)))
    wall = next(iter(sorted(market.obstacles)))
    wall_spec = "%d:%d,%d" % (FROM, wall % market.width, wall // market.width)
    exit_cell = next(iter(sorted(exits)))
    exit_spec = "%d:%d,%d" % (FROM, exit_cell % market.width, exit_cell // market.width)

    # --- the tool's refusals, on a scratch copy -----------------------------------------------
    print("what the tool refuses")
    scratch = os.path.join(W, "scratch")
    shutil.copytree(DATA, scratch)
    before = {n: open(os.path.join(scratch, n), "rb").read() for n in ("passages.json", "exits_sides.json")}
    for why, args, said in (
            ("an id of the original's (262 «Тотем» among them)",
             ("--from", str(SRC), "--title", TITLE, "--id", "262"), "a new place's id"),
            ("a walk-in on a wall", ("--from", str(SRC), "--title", TITLE, "--walk-in", wall_spec), "is a wall"),
            ("a walk-in on an exit", ("--from", str(SRC), "--title", TITLE, "--walk-in", exit_spec),
             "is an exit already"),
            ("a door the copy has not", ("--from", str(SRC), "--title", TITLE, "--walk-in", spec, "--door", "b"),
             "has no door b"),
            ("a door that leads nowhere said", ("--from", str(SRC), "--title", TITLE, "--door", "a"),
             "leads where")):
        code, out = tool(*args, data=scratch)
        check("%s: refused, and why" % why, (code, said in str(out)), (2, True))
    check("  ..and a refusal leaves nothing behind",
          (os.listdir(os.path.join(scratch, "locations", "static")) if os.path.isdir(
              os.path.join(scratch, "locations", "static")) else [],
           {n: open(os.path.join(scratch, n), "rb").read() == before[n] for n in before}),
          (sorted(os.listdir(os.path.join(DATA, "locations", "static")))
           if os.path.isdir(os.path.join(DATA, "locations", "static")) else [],
           {n: True for n in before}))

    # --- the new place -------------------------------------------------------------------------
    print("the new place")
    NEW = new_location.next_id(world.static_ids())
    p_before = open(os.path.join(DATA, "passages.json"), encoding="utf-8").read()
    code, out = tool("--from", str(SRC), "--title", TITLE, "--walk-in", spec, "--door", "a")
    check("the tool makes it under the first free id from 1381", (code, out.get("id") if code == 0 else out),
          (0, NEW))
    world._CACHE.clear()
    place = world.location(NEW)
    check("it is the copy, read from data/locations: its title, the copy's grid, nobody standing in it",
          (place.file, place.title, place.width, place.height, place.spawns,
           world.static_path(NEW) == os.path.join(DATA, "locations", "static", "%d.xml" % NEW)),
          ("static/%d.xml" % NEW, TITLE, 32, 64, [], True))
    check("  ..no map cell to the server, and no desert", world.is_wilderness(NEW), False)
    index = world.overlay_index()
    check("its row in the index", {k: index.get(NEW, {}).get(k) for k in ("title", "from", "author")},
          {"title": TITLE, "from": SRC, "author": "test"})
    with io.open(os.path.join(DATA, "exits_sides.json"), encoding="utf-8") as fh:
        es = json.load(fh)
    check("its rows in exits_sides.json, read off its own outzones",
          (es["locations"].get(str(NEW)), es["summary"].get(str(NEW))), B.row(NEW, world.static_path(NEW))[:2])
    # The location file's own reader and writer (tools/lavaloc.py) agree:
    # the copy is the original but for title, fn and <mobs>, and the table's
    # row is what the editor computes from the file.
    with open(world.static_path(NEW), "rb") as fh:
        new_raw = fh.read()
    with open(world.static_path(SRC), "rb") as fh:
        src_raw = fh.read()
    new_m, src_m = lavaloc.load(new_raw), lavaloc.load(src_raw)
    want_m = lavaloc.load(src_raw)
    want_m["attrs"].update(title=TITLE, fn="ED_%d" % NEW)
    want_m["lists"]["mobs"], want_m["tails"]["mobs"] = [], ""
    check("lavaloc: the copy is the original but for title, fn and <mobs>, and reads back byte for byte",
          (new_m == want_m, lavaloc.write_raw(lavaloc.parse_raw(new_raw)) == new_raw,
           len(src_m["lists"]["mobs"]) > 0),
          (True, True, True))
    check("  ..and its exits_sides row is lavaloc's exits_row of the file",
          es["locations"].get(str(NEW)), lavaloc.exits_row(new_m))
    p_after = open(os.path.join(DATA, "passages.json"), encoding="utf-8").read()
    doc_b, doc_a = json.loads(p_before), json.loads(p_after)
    walk_rows = doc_a["walk_in"].pop(str(FROM))
    door_row = doc_a["doors"].pop(str(NEW))
    if not doc_b["walk_in"].get(str(FROM)):
        doc_b["walk_in"].pop(str(FROM), None)
    else:
        walk_rows = walk_rows[len(doc_b["walk_in"].pop(str(FROM))):]
    check("passages.json: a walk-in in %d into it, and its door a back; every other row as it was" % FROM,
          ([(r["cells"], r["target_loc_id"]) for r in walk_rows],
           {s: (r["target_loc_id"], r["confidence"], r["source"]) for s, r in door_row.items()}, doc_a == doc_b),
          ([([[c % market.width, c // market.width] for c in sorted(WALK)], NEW)],
           {"a": (FROM, "high", "editor")}, True))
    gone = [ln for ln in p_before.split("\n") if ln not in set(p_after.split("\n"))]
    check("  ..and every line of the file is still there but the ones the rows were added to",
          [ln for ln in gone if (ln + ",") not in p_after and '"walk_in"' not in ln], [])

    # --- travel, in this process, on the same tables --------------------------------------------
    door_cells = sorted(c for c, s in travel.exit_sides(place).items() if s == "a")
    into = travel.plan_walk_in(market, a, *FROM_CELL)
    check("travel: the walk-in leads into it, beside its door, the market's cell kept",
          (into.loc_id, into.pos in place.entries, into.pos in door_cells, (into.gx, into.gy)),
          (NEW, True, False, FROM_CELL))
    back = travel.plan_exit(place, door_cells[0], *FROM_CELL)
    check("  ..and its door a back to the market, beside the walk-in, never on it",
          (back.loc_id, back.pos in WALK, back.pos == travel.door_arrival(market, NEW)), (FROM, False, True))

    # --- the real server ------------------------------------------------------------------------
    print("the real server")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        PORT = probe.getsockname()[1]
    DB = os.path.join(W, "new_location.db")
    accounts.DB_PATH = DB
    store = accounts.Store(DB)
    store.register("walker", "secret")
    store.close()
    CRED = accounts.credential("walker", "secret")
    env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB, LAVA_CHEATS="1",
               LAVA_GX=str(FROM_CELL[0]), LAVA_GY=str(FROM_CELL[1]), LAVA_SEED="7")
    LOG = os.path.join(W, "server.log")
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                           stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)

    class Client:
        def __init__(self, sock):
            self.s, self.buf = sock, b""

        def send(self, text):
            self.s.sendall(text.encode(ENC) + b"\x00")

        def until(self, pred, wait=3.0):
            out = []
            deadline = time.time() + wait
            while time.time() < deadline:
                self.s.settimeout(max(0.01, deadline - time.time()))
                try:
                    chunk = self.s.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                self.buf += chunk
                parts = self.buf.split(b"\x00")
                self.buf = parts.pop()
                new = [decode(f.decode(ENC)) for f in parts if f]
                out += new
                if any(pred(f) for f in new):
                    break
            return out

    def calls(frames):
        return [p["id"] for n, p in frames if n == "lcall"]

    def enter(c):
        c.send("lenter;accept=1;")
        got = c.until(lambda f: f[0] == "lenter", 3)
        return [p for n, p in got if n == "lenter"][0]["pos"]

    def log_in(new):
        c = Client(testkit.connect(PORT, srv, LOG))
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % CRED)
        c.until(lambda f: f[0] == "accountInfo")
        if new:
            c.send("newPers;res=1;sex=0;name=@walker@;")
            c.until(lambda f: f[0] == "cmdAck")
            c.send("actPlayer;")
        else:
            c.send("selPers;num=0;")
        return c, calls(c.until(lambda f: f[0] == "lcall", 5))

    def walk(c, loc, start, goal):
        path = mobs.find_path(loc, start, goal)
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
        return path

    c, _first = log_in(True)
    enter(c)
    c.send("userMsg;entry=@/goto %d@;group=0;" % FROM)
    check("/goto %d: into the market" % FROM, calls(c.until(lambda f: f[0] == "lcall")), [FROM])
    pos = enter(c)
    path = walk(c, market, pos, lambda cell: cell in WALK)
    got = c.until(lambda f: f[0] == "lcall", travel.walk_seconds(len(path)) + 4)
    check("a walk that ends on the walk-in calls the player into the new place", calls(got), [NEW])
    pos = enter(c)
    check("  ..where he arrives beside its door, on a free entry",
          (pos in place.entries, pos in place.obstacles, pos == travel.door_arrival(place, FROM)),
          (True, False, True))
    path = walk(c, place, pos, lambda cell: cell in door_cells)
    time.sleep(travel.walk_seconds(len(path)) + 0.5)
    c.until(lambda f: False, 0.3)
    c.send("chWorld;to=1;")
    got = c.until(lambda f: f[0] == "lcall", 3)
    check("its door a, «в другую локацию», takes him back to the market",
          ([n for n, _p in got if n in ("cmdAck", "lcall")], calls(got)), (["cmdAck", "lcall"], [FROM]))
    pos = enter(c)
    check("  ..beside the walk-in, never on it", (pos in WALK, pos == travel.door_arrival(market, NEW)),
          (False, True))

    # --- left on a cell that is a wall now --------------------------------------------------------
    path = walk(c, market, pos, lambda cell: cell in WALK)
    got = c.until(lambda f: f[0] == "lcall", travel.walk_seconds(len(path)) + 4)
    pos = enter(c)
    c.s.close()
    db = sqlite3.connect(DB)
    deadline = time.time() + 10
    row = None
    while time.time() < deadline:
        row = db.execute("SELECT id, loc, pos FROM characters WHERE name = ?", ("walker",)).fetchone()
        if row and row[1] == NEW and row[2] == pos:
            break
        time.sleep(0.2)
    check("the server saved him in the new place, where he stood", (row[1], row[2]) if row else None, (NEW, pos))
    db.close()
    wall_here = sorted(place.obstacles)[len(place.obstacles) // 2]
    store = accounts.Store(DB)
    store.save_position(row[0], NEW, wall_here, FROM_CELL[0], FROM_CELL[1], False)
    store.close()
    c, first = log_in(False)
    pos = enter(c)
    check("a login saved on a cell that is a wall stands on the entry instead (Session.restore)",
          (first, pos in place.obstacles, pos == place.entry_cell()), ([NEW], False, True))
    c.s.close()
except Exception:
    import traceback
    fails.append("crashed:\n" + traceback.format_exc())
finally:
    if srv is not None:
        srv.terminate()
        try:
            srv.wait(10)
        except subprocess.TimeoutExpired:
            srv.kill()
    shutil.rmtree(W, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("new location OK")
