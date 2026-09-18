"""Dying properly: the corpse stays a corpse, and wakes up where it lives.

test_combat kills a player once, on its way past. This is the rest of it,
and every step is what the client does with what it is sent:

  * lch;dead=<me> opens the regeneration window (Resurrector.lch) and the
    same frame about someone else lays that figure out (Location.lch);
  * characters.death outlives the socket, and persInfo;death=1 is how the
    next login is told -- PersGenerator.persInfo takes it as
    Boolean(param.death) and Master.lenter opens the window from it;
  * the three buttons of RegenerationInterface differ: free is the one the
    window's fifteen-second timer presses by itself, so the wait is what it
    costs and the body comes back at a quarter; five gold and five hundred
    afro are the same sum at the gold_to_afro_rate the server sends, and
    both are instant and whole;
  * the body always travels home (characters.home_loc, on_conv;op=0), or to
    the starting cell when nowhere is registered -- never to where it fell;
  * one backpack item the wiki marks with drop_on_death is left lying in an
    ordinary loot bag on the cell of the death;
  * a corpse acts on nothing: its shots, walks and chWorld are refused,
    while the pipelined requests are still answered so no request window on
    the client's side is left shut.

The fight is the dump behind the black market (location 100) again: the dog
nearest the entrance stands just outside its aggro radius, so one step
towards it is enough to be attacked, and a character left with 1 HP dies to
the first bite. The deaths after the first one are set up by writing the
flag into the database rather than by being mauled four more times -- which
is the relogin path anyway, and the only way to be sure it is the flag and
not the memory that the server is going by.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts
import combat
import inventory
import items
import mobs
import progression
import rooms
import travel
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "death.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("victim", "secret")
_store.register("witness", "secret")
_store.close()
VICTIM = accounts.credential("victim", "secret")
WITNESS = accounts.credential("witness", "secret")

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- in process: the table behind the losses, and the fallback home -----------
# "Шанс выпадения при смерти" reached data/items_wiki.json as a flag, not a
# percentage, and it is a wiki extra: items._overlay keeps it off the wire,
# so combat reads it from the raw table.
DROPPING = [t for t in sorted(items.catalogue())
            if combat.drops_on_death(t) and items.params_of(t) is not None]
check("the wiki marks some types as falling off a corpse", len(DROPPING) >= 50, True)
check("and the starter kit is not among them",
      [combat.drops_on_death(t) for t, _n in inventory.STARTER_KIT], [False, False])
DROP_TYPE = DROPPING[0]
check("with no home registered, home is the starting cell, not the last one",
      travel.home({"home_loc": None, "home_gx": None, "home_gy": None},
                  (102, 5970, 1730)), (102, 5970, 1730))
check("free, gold and afro are the window's own numbering",
      (combat.RES_FREE, combat.RES_GOLD, combat.RES_AFRO), (0, 1, 2))
check("and five gold is five hundred afro at the rate the server sends",
      combat.RESURRECT_GOLD * 100, combat.RESURRECT_AFRO)

# --- the server ---------------------------------------------------------------
# The free resurrection's wait is cut from the window's fifteen seconds to
# four, so that the refusal before it and the acceptance after it both fit in
# a test; the exit timer is shortened for the /home check; the dog is given a
# long respawn so nothing walks in on the corpse.
WAIT = 4.0
LEAVE = 3.0
# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB, LAVA_GX="5970", LAVA_GY="1730",
           LAVA_AP_REGEN="25", LAVA_LEAVE_COMBAT=str(int(LEAVE)),
           LAVA_RESPAWN="120", LAVA_RESURRECT_WAIT=str(WAIT), LAVA_SEED="11")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
# The log outgrows a pipe nobody drains: at 64 KB the write blocks and the
# server stops answering in the middle of the test.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


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

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out

    def names(self, wait=0.5):
        return [n for n, _ in self.frames(wait)]


def named(frames, name):
    return [p for n, p in frames if n == name]


def only(frames, *names):
    return [(n, p) for n, p in frames if n in names]


def ours(frames, *names):
    """Frames of these names that are about the receiver's own figure. id 0
    is always oneself (Gamer.as:31), so this leaves out the room's own
    traffic -- a dog walking off to the next thing it can see, and swinging
    at it -- which would otherwise land in the middle of a check."""
    return [(n, p) for n, p in frames if n in names and p.get("id", 0) == 0]


def hexcell(cell):
    return "x0%08x" % cell


def login(c, cred, first=False, name="pers"):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    got = c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@%s@;" % name)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    got += c.until(lambda f: f[0] == "lcall")
    return got


def enter(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, named(got, "lenter")[0]["pos"]


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)


def store():
    return accounts.Store(DB)


def row_of(char_id):
    st = store()
    row = dict(st.character(char_id))
    st.close()
    return row


def flag_dead(char_id):
    """Lay a logged-out character out in the database, as a mauling would
    have. Fighter.restore is what has to pick it up at the next selPers."""
    st = store()
    st.save_character_state(char_id, death=1, hp=0, sp=0)
    st.close()


DUMP = 100
DOG_HOME = 4551          # the dog nearest the entrance (test_combat)
DUMP_LOC = world.location(DUMP)

try:
    # --- a home on the market, a bottle in the bag, and a walk to the dump ----
    v = Client(connect())
    got = login(v, VICTIM, first=True, name="victim")
    MARKET = named(got, "lcall")[0]["id"]
    arrival, pos = enter(v)
    npc = {p["name"]: p["id"] for n, p in arrival if n.startswith("userInfo")}
    v.send("on_conv;mob=%d;op=0;" % npc[2424])
    check("home registered on the market", v.frames(), [("cmdAck", {"res": 0})])
    VICTIM_ID = store().db.execute(
        "SELECT id FROM characters WHERE name = 'victim'").fetchone()[0]
    check("and written down with its cell",
          (row_of(VICTIM_ID)["home_loc"], row_of(VICTIM_ID)["death"]), (MARKET, 0))

    chat(v, "/give %d" % DROP_TYPE)
    got = v.frames()
    check("a bottle that the wiki says falls off a corpse is in the bag",
          [n for n, _ in got][:2], ["cmdAck", "ss_obj_status"])
    chat(v, "/goto %d" % DUMP)
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("the dump opens, at peace until somebody starts something",
          [(p["id"], p["ws"]) for p in named(got, "lcall")], [(DUMP, 0)])
    enter(v)
    v.send("logout;")
    v.frames(0.3)
    v.s.close()

    # One hit point left, as after a fight that went badly: the first bite
    # will finish it.
    st = store()
    st.save_character_state(VICTIM_ID, hp=1, sp=0)
    bag_before = {r["uniq"] for r in st.items_of(VICTIM_ID)
                  if r["slot"] == inventory.BAG and combat.drops_on_death(r["type_id"])}
    st.close()
    check("exactly one thing in the bag can fall", len(bag_before), 1)

    # --- a witness in the room, who first tries to walk out of a fight -------
    w = Client(connect())
    login(w, WITNESS, first=True, name="witness")
    enter(w)
    chat(w, "/goto %d" % DUMP)
    w.until(lambda f: f[0] == "lcall", 2)
    _arrival, wpos = enter(w)
    # /home is not a way round the exit timer chWorld is held to. The dog is
    # asleep at the far end -- a swing at an empty hex is what starts the
    # clock -- and the refusal has to be a line of chat, because this userMsg
    # has already been acknowledged and a second cmdAck would shift the queue.
    w.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(wpos + 1))
    w.frames(0.5)
    chat(w, "/home")
    got = w.frames(0.5)
    check("a swing just thrown: /home says no, in chat, and nobody travels",
          ([n for n, _ in only(got, "cmdAck", "lcall", "userMsg")],
           [p for n, p in got if n == "lch" and "lostUser" in p]),
          (["cmdAck", "userMsg"], []))
    time.sleep(LEAVE)
    chat(w, "/home")
    got = w.until(lambda f: f[0] == "lcall", 2)
    check("once the exit timer is out, it goes -- to the start, unregistered",
          [(n, p.get("res", p.get("id"))) for n, p in got
           if n in ("cmdAck", "lcall")], [("cmdAck", 0), ("lcall", MARKET)])
    enter(w)
    # The same journey from the global map, which is the other side
    # Session.go_home has to work from: off the map, onto the home cell, and
    # into the location standing on it.
    w.send("chWorld;")
    got = w.until(lambda f: f[0] == "gmap", 2)
    check("out to the map first", named(got, "gmap") != [], True)
    chat(w, "/home")
    got = w.until(lambda f: f[0] == "lcall", 2)
    check("/home off the global map lands in the location all the same",
          [p["id"] for p in named(got, "lcall")], [MARKET])
    enter(w)
    chat(w, "/goto %d" % DUMP)
    w.until(lambda f: f[0] == "lcall", 2)
    enter(w)

    v = Client(connect())
    got = login(v, VICTIM)
    check("a live character is announced as live",
          [p["death"] for p in named(got, "persInfo")], [0])
    check("and called back into the dump", named(got, "lcall")[0]["id"], DUMP)
    arrival, pos = enter(v)
    seen = w.frames(1.0)
    newcomers = [p for p in named(seen, "lch") if "newUser" in p]
    check("the witness sees the victim walk in", len(newcomers), 1)
    VICTIM_PID = newcomers[0]["newUser"]
    check("under the id the players table gives them",
          VICTIM_PID, rooms.player_id(VICTIM_ID))

    # The entrance is 6.2 hexes from the dog and its aggro radius is 5, so a
    # couple of steps towards it are enough to be noticed; then it comes, and
    # one bite is one hit point too many.
    dog_aggro = mobs.stats(82).aggro
    path = [pos]
    while mobs.hex_distance(path[-1], DOG_HOME, DUMP_LOC.width) > dog_aggro - 0.5:
        path.append(min(
            (n for n in progression.hex_neighbours(path[-1], DUMP_LOC.width,
                                                   DUMP_LOC.height)
             if n not in DUMP_LOC.obstacles and n not in path),
            key=lambda n: mobs.hex_distance(n, DOG_HOME, DUMP_LOC.width)))
    step = path[-1]
    v.send("moveTo;path=|%s|;" % "|".join(str(c) for c in path))
    got = v.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 40)
    # The losses are settled behind the death frame, so the tail comes too.
    got += v.frames(0.6)
    check("bitten to death: lch;dead=0, once",
          [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    check("with a bite to show for it",
          [p["target"] for n, p in got if n == "caHit"][:1], [0])

    seen = w.frames(1.5)
    check("the witness is told the same about the victim's own id",
          [p for n, p in seen if n == "lch" and "dead" in p], [{"dead": VICTIM_PID}])
    dropped = named(seen, "ss_loot")
    check("and sees a bag appear where the body fell",
          [(p["s_status"], p["hex"]) for p in dropped], [(1, [step])])

    check("the death is written down, hit points and all",
          (row_of(VICTIM_ID)["death"], row_of(VICTIM_ID)["hp"]), (1, 0))
    st = store()
    left = {r["uniq"] for r in st.items_of(VICTIM_ID)}
    on_ground = {r["uniq"] for r in st.db.execute(
        "SELECT uniq FROM items WHERE char_id = 0").fetchall()}
    st.close()
    check("the bottle is on the ground and no longer the victim's",
          (bag_before & left, bag_before <= on_ground), (set(), True))
    check("the client is told it left the bag",
          [(str(p["obj"]), p["status"]) for p in named(got, "ss_obj_status")
           if p["status"] == 0] != [], True)

    # --- free is not free: it costs the window's fifteen seconds -------------
    v.send("resurrect;res_type=0;")
    check("free too soon is refused, and no lcall follows",
          only(v.frames(0.5), "cmdAck", "lcall"),
          [("cmdAck", {"res": inventory.RES_NOT_READY})])
    check("the character is still dead in the table", row_of(VICTIM_ID)["death"], 1)

    # --- a corpse acts on nothing, and is answered all the same --------------
    v.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(step + 1))
    check("dead: a punch is refused with one ack and no swing of its own",
          ours(v.frames(0.4), "cmdAck", "caHit", "caMiss", "faAim"),
          [("cmdAck", {"res": inventory.RES_REFUSED})])
    v.send("moveTo;path=|%d|%d|;" % (step, step + 1))
    check("dead: a walk is dropped, ack and all",
          ours(v.frames(0.4), "cmdAck", "userMove", "breakMv"), [])
    v.send("chWorld;")
    check("dead: the way out to the map is refused",
          only(v.frames(0.4), "cmdAck", "gmap"),
          [("cmdAck", {"res": inventory.RES_REFUSED})])
    chat(v, "/home")
    check("dead: even the chat is refused, and its ack comes anyway",
          only(v.frames(0.4), "cmdAck", "lcall", "userMsg"),
          [("cmdAck", {"res": inventory.RES_REFUSED})])
    v.send("ss_get;target=0;slot=8;")
    check("but a request with a window of its own is still answered",
          [n for n, _ in v.frames(0.4)], ["ss_ack"])
    v.send("getInfo;lvl=0;id=0;type=0;")
    got = v.frames(0.4)
    check("and so is the character's own card, showing no hit points",
          ([n for n, _ in only(got, "userInfo_Player", "usrUp")],
           named(got, "usrUp")[0]["hcur"]),
          (["userInfo_Player", "usrUp"], 0))
    # Nothing keeps hitting a corpse: the dog was made to let go the moment
    # the body fell, and what it does next -- walk home, or find the witness
    # standing by the entrance -- is no longer aimed here. caMiss carries the
    # cell of whoever is being swung at, so the death cell is the tell.
    quiet = got + v.frames(2.0)
    check("the dog lets the corpse go",
          ([p for n, p in quiet if n == "caHit" and p.get("target", 0) == 0],
           [p for n, p in quiet if n == "caMiss" and p.get("hex") == step]),
          ([], []))

    # --- the death outlives the socket ---------------------------------------
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    check("a corpse that logs out does not stay standing in the room",
          [p for n, p in w.frames(0.8) if n == "lch" and "lostUser" in p],
          [{"lostUser": VICTIM_PID}])
    v = Client(connect())
    got = login(v, VICTIM)
    check("a dead character is announced dead at the character screen",
          [p["death"] for p in named(got, "persInfo")], [1])
    arrival, pos = enter(v)
    check("and is let into the location all the same, which is where the "
          "client opens its window", named(arrival, "lenter") != [], True)
    seen = w.frames(1.0)
    check("the room sees a corpse walk in, and lays it out again",
          [p for n, p in seen if n == "lch" and "dead" in p],
          [{"dead": VICTIM_PID}])
    v.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(pos + 1))
    check("still dead, still refused",
          only(v.frames(0.4), "cmdAck"),
          [("cmdAck", {"res": inventory.RES_REFUSED})])

    # --- free, once the window's timer has run out ---------------------------
    time.sleep(WAIT)
    v.send("resurrect;res_type=0;")
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("after the wait it is taken, and the body is called home",
          [(n, p.get("res", p.get("id"))) for n, p in got
           if n in ("cmdAck", "lcall")],
          [("cmdAck", 0), ("lcall", MARKET)])
    check("and stands up in the table", row_of(VICTIM_ID)["death"], 0)
    seen = w.frames(1.0)
    check("the room it left is told the figure is gone",
          [p for n, p in seen if n == "lch" and "lostUser" in p],
          [{"lostUser": VICTIM_PID}])
    arrival, pos = enter(v)
    check("home is a room like any other: its inhabitants come with it",
          len([p for p in named(arrival, "lch") if "newUser" in p]) > 10, True)
    v.send("getInfo;lvl=0;id=0;type=0;")
    vit = named(v.until(lambda f: f[0] == "usrUp"), "usrUp")[0]
    FULL_HP, FULL_SP = vit["hmax"], vit["smax"]
    check("a free resurrection is the penalised one: a quarter, no stamina",
          (vit["hcur"], vit["scur"]),
          (max(1, int(FULL_HP * combat.FREE_HP_SHARE)), 0))

    # And the neighbours can see the resurrected body standing there.
    chat(w, "/goto %d" % MARKET)
    w.until(lambda f: f[0] == "lcall", 2)
    arrival_w, _pos_w = enter(w)
    check("a newcomer at home finds the resurrected player standing in it",
          [p for p in named(arrival_w, "lch") if p.get("newUser") == VICTIM_PID],
          [dict(newUser=VICTIM_PID, pos=pos, rtype=-1)])
    seen = v.frames(1.0)
    check("and is seen by them in turn",
          [p["newUser"] for n, p in seen if n == "lch" and "newUser" in p] != [], True)

    # --- five gold: the price the window prints ------------------------------
    chat(v, "/money 0 %d" % combat.RESURRECT_GOLD)
    v.frames(0.5)
    check("the purse holds exactly what the gold button checks for",
          row_of(VICTIM_ID)["gold"], combat.RESURRECT_GOLD)
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    flag_dead(VICTIM_ID)
    v = Client(connect())
    login(v, VICTIM)
    enter(v)
    v.send("resurrect;res_type=1;")
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("gold: acknowledged, the purse pushed, and home at once",
          [n for n, _ in got if n in ("cmdAck", "userInfo_Player", "lcall")],
          ["cmdAck", "userInfo_Player", "lcall"])
    check("the five gold are gone", row_of(VICTIM_ID)["gold"], 0)
    enter(v)
    v.send("getInfo;lvl=0;id=0;type=0;")
    vit = named(v.until(lambda f: f[0] == "usrUp"), "usrUp")[0]
    check("and a paid body is whole, hit points and stamina",
          (vit["hcur"], vit["scur"]), (FULL_HP, FULL_SP))

    # --- five hundred afro: the same sum, the other purse --------------------
    afro_before = row_of(VICTIM_ID)["afro"]
    check("there is enough afro for the other button",
          afro_before >= combat.RESURRECT_AFRO, True)
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    flag_dead(VICTIM_ID)
    v = Client(connect())
    login(v, VICTIM)
    enter(v)
    v.send("resurrect;res_type=2;")
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("afro: acknowledged and home at once, with no wait either",
          [(n, p.get("res", p.get("id"))) for n, p in got
           if n in ("cmdAck", "lcall")], [("cmdAck", 0), ("lcall", MARKET)])
    check("and exactly five hundred afro the poorer",
          afro_before - row_of(VICTIM_ID)["afro"], combat.RESURRECT_AFRO)
    enter(v)
    v.send("getInfo;lvl=0;id=0;type=0;")
    vit = named(v.until(lambda f: f[0] == "usrUp"), "usrUp")[0]
    check("whole again", (vit["hcur"], vit["scur"]), (FULL_HP, FULL_SP))

    # --- an empty purse buys nothing, and the window stays up ----------------
    chat(v, "/money -1000000 -1000000")
    v.frames(0.5)
    check("penniless", (row_of(VICTIM_ID)["afro"], row_of(VICTIM_ID)["gold"]), (0, 0))
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    flag_dead(VICTIM_ID)
    v = Client(connect())
    login(v, VICTIM)
    enter(v)
    v.send("resurrect;res_type=1;")
    check("no gold, no resurrection, and no journey",
          only(v.frames(0.5), "cmdAck", "lcall"),
          [("cmdAck", {"res": inventory.RES_NO_MONEY})])
    v.send("resurrect;res_type=2;")
    check("no afro either",
          only(v.frames(0.5), "cmdAck", "lcall"),
          [("cmdAck", {"res": inventory.RES_NO_MONEY})])
    check("and the body is still lying there", row_of(VICTIM_ID)["death"], 1)
    time.sleep(WAIT)
    v.send("resurrect;res_type=0;")
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("the free one always works in the end",
          [(n, p.get("res", p.get("id"))) for n, p in got
           if n in ("cmdAck", "lcall")], [("cmdAck", 0), ("lcall", MARKET)])
    enter(v)

    # --- nowhere registered: the start, never where the body lies ------------
    st = store()
    st.set_home(VICTIM_ID, None, None, None)
    st.close()
    chat(v, "/goto %d" % DUMP)
    v.until(lambda f: f[0] == "lcall", 2)
    enter(v)
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    flag_dead(VICTIM_ID)
    v = Client(connect())
    got = login(v, VICTIM)
    check("the body is where it fell, in the dump",
          named(got, "lcall")[0]["id"], DUMP)
    enter(v)
    time.sleep(WAIT)
    v.send("resurrect;res_type=0;")
    got = v.until(lambda f: f[0] == "lcall", 2)
    check("with no home, it wakes up at the start and not in the dump",
          [p["id"] for p in named(got, "lcall")], [MARKET])
    enter(v)
    v.send("logout;")
    v.frames(0.3)
    v.s.close()
    w.send("logout;")
    w.frames(0.3)
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("death OK")
