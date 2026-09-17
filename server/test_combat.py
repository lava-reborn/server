"""Shoot a starving dog, get bitten, loot the corpse, die, come back home.

Every exchange is the client's own: ItemActivator.as sends the ss_use, and
Location.as, Loot.as, Resurrector.as and PersEquip.as read the answers in the
order checked here (recon/analysis/combat.md 1-3, invariants in 10). The
fight happens in location 100, the dump behind the black market, where quest
5 sends the player for three dogs; the dog nearest the entrance stands 6.2
hexes away, one more than its aggro radius, so the first shot is the
player's.

Randomness is real (hits, misses, damage), so the fight is a loop that
checks the shape of every burst rather than a fixed transcript, and the AP
regeneration and the combat timeouts are shortened through the environment
to keep the whole thing under a minute.
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
import quests
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "combat.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("gunner", "secret")
_store.close()
CRED = accounts.credential("gunner", "secret")

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- the formulas and the geometry, in process --------------------------------
# Wiki "Броня": 100 damage against armour 60 -> 40 HP, 60 SP; 120 -> 0/100;
# 0 -> 100/0. Stamina that is not there spills into HP; a crit skips it all.
check("armour turns damage into stamina loss", combat.split_damage(100, 60, 0, False, 1000), (40, 60))
check("armour above the damage absorbs everything", combat.split_damage(100, 120, 0, False, 1000), (0, 100))
check("no armour, all HP", combat.split_damage(100, 0, 0, False, 1000), (100, 0))
check("missing stamina spills into HP", combat.split_damage(100, 60, 0, False, 20), (80, 20))
check("a crit ignores armour", combat.split_damage(100, 60, 0, True, 1000), (100, 0))
check("piercing eats into the armour", combat.split_damage(100, 60, 10, False, 1000), (50, 50))
check("a blow lands on stamina first", combat.melee_split(10, False, 4), (6, 4))
check("target BigUINT: one type digit then eight of id", combat.parse_target("10000002a"), (1, 42))
check("a hex target has type 0", combat.parse_target("000000f3c"), (0, 3900))
W = 64
even = 4 * W + 5
check("facing east is 8", mobs.direction(even, even + 1, W), 8)
check("facing west is 4", mobs.direction(even, even - 1, W), 4)
check("down-right is 1", mobs.direction(even, even + W, W), 1)
check("straight down keeps the facing", mobs.direction(even, even + 2 * W, W), 0)
check("neighbours are exactly one hex apart",
      sorted(round(mobs.hex_distance(even, n, W), 6)
             for n in progression.hex_neighbours(even, W, 128)), [1.0] * 6)
loc100 = world.location(100)
rock = next(o for o in sorted(loc100.obstacles)
            if 2 <= o % W <= W - 3
            and all(o + d not in loc100.obstacles for d in (-2, -1, 1, 2)))
check("a rock on the straight line is what faWall reports",
      mobs.line_of_fire(loc100, rock - 2, rock + 2), rock)
check("nothing between neighbours", mobs.line_of_fire(loc100, even, even + 1), None)
dog_stats = mobs.stats(82)
check("a level-1 dog has the curve's HP times the animal share",
      (dog_stats.level, dog_stats.hp_max, dog_stats.ranged, dog_stats.can_attack),
      (1, 84, False, True))
check("a box is an object: shot at, never shooting", mobs.stats(409).can_attack, False)
check("an armed bandit carries the stall's pistol", mobs.stats(17).weapon_type_id, 4380)

# The kill counter, on a scratch character in a scratch database.
_scratch = accounts.Store(os.path.join(tempfile.mkdtemp(), "scratch.db"))
_acc, _ = _scratch.register("scratch", "secret")
_cid, _ = _scratch.create_character(_acc, "scratch", 0, "1")
_q5 = quests.get(5)
_scratch.take_quest(_cid, 5, _q5.fresh_progress(), 0)
check("a kill of the wrong type moves nothing", quests.kill_progress(_scratch, _cid, 999), [])
check("a dog counts", quests.kill_progress(_scratch, _cid, 82),
      [("q_di_kill_mobs", dict(q_id=1, q_type=5, complete=0, kill_num=[1]))])
quests.kill_progress(_scratch, _cid, 82)
check("the third completes the quest", quests.kill_progress(_scratch, _cid, 82),
      [("q_di_kill_mobs", dict(q_id=1, q_type=5, complete=1, kill_num=[3]))])
check("a fourth is not counted", quests.kill_progress(_scratch, _cid, 82), [])
_scratch.close()

# --- the server -----------------------------------------------------------------
# AP regeneration is raised so the bar never throttles the fight, the exit
# timer and the respawn are shortened, and the dice are seeded. The wait a
# free resurrection costs goes to zero: that it is charged at all is
# test_death's business, and here it would only add fifteen seconds.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_AP_REGEN="25", LAVA_LEAVE_COMBAT="3", LAVA_RESPAWN="4",
           LAVA_RESURRECT_WAIT="0", LAVA_SEED="7")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.5):
        """Everything within an exact window, decoded to (name, params)."""
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        """Everything up to and including the first frame pred accepts, or
        everything that came before the window closed."""
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out

    def names(self, wait=0.5):
        return [n for n, _ in self.frames(wait)]


def named(frames, name):
    return [p for n, p in frames if n == name]


def only(frames, *names):
    """The frames of these names, in order: what a check is about, with the
    room's own traffic (a respawn, a war-state edge) left out."""
    return [(n, p) for n, p in frames if n in names]


def oids(p):
    return [str(x) for x in p["o_list"]]


def entity(target_id):
    """ss_use target for an entity: type digit 1 and the id in eight hex."""
    return "x1%08x" % target_id


def hexcell(cell):
    return "x0%08x" % cell


PISTOL = 4380
ROUNDS = items.AMMO_9MM[0]
PISTOL_SI = items.params_of(PISTOL)
CLIP = PISTOL_SI["clip_size"]
COST = PISTOL_SI["fire_costs"][0]


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@gunner@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    got = c.until(lambda f: f[0] == "lcall")
    return named(got, "lcall")[0]


def enter(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, named(got, "lenter")[0]["pos"]


class FireTracker:
    """combat.md 10: hits only inside a faShot pair, pairs never nested, as
    many pairs per shooter as its faAim announced, usrUp never inside."""

    def __init__(self):
        self.expected = {}
        self.seen = {}
        self.open = None
        self.errors = []

    def feed(self, frames):
        for name, p in frames:
            sid = p.get("id", 0)
            if name == "faAim":
                if sid in self.expected and self.seen[sid] != self.expected[sid]:
                    self.errors.append("shooter %s: %d pairs for num_shots %d"
                                       % (sid, self.seen[sid], self.expected[sid]))
                self.expected[sid] = p.get("num_shots", 1)
                self.seen[sid] = 0
            elif name == "faShot":
                if p["status"] == 1:
                    if self.open is not None:
                        self.errors.append("pair opened inside a pair")
                    self.open = sid
                else:
                    if self.open != sid:
                        self.errors.append("pair closed by %s while %s open" % (sid, self.open))
                    self.open = None
                    self.seen[sid] = self.seen.get(sid, 0) + 1
            elif name in ("faHit", "faMiss", "faWall"):
                if self.open is None:
                    self.errors.append("%s outside a pair" % name)
            elif name == "usrUp" and self.open is not None:
                self.errors.append("usrUp inside a pair")

    def finish(self):
        for sid, n in self.expected.items():
            if self.seen.get(sid) != n:
                self.errors.append("shooter %s ended with %s pairs for %d"
                                   % (sid, self.seen.get(sid), n))
        return self.errors


def last_cell(frames, mob_id, default):
    """Where a mob's walks left it: the end of its last userMove path."""
    for n, p in reversed(frames):
        if n == "userMove" and p.get("id") == mob_id:
            return p["path"][-1]
    return default


def walk(c, loc, start, goal, avoid=()):
    """A real path (adjacent, off the obstacles) to the nearest goal cell,
    sent as the client would; returns the cell reached."""
    path = mobs.find_path(loc, start, goal, set(avoid))
    if path is None:
        raise RuntimeError("no path from %d" % start)
    if len(path) == 1:
        return start, []
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    got = c.until(lambda f: f[0] == "userMove" and f[1].get("id") == 0)
    check("walk accepted", [n for n, _ in got if n in ("cmdAck", "breakMv")][:1], ["cmdAck"])
    return path[-1], got


try:
    c = Client(connect())
    lcall = login(c, first=True)
    check("a peaceful location is called with ws=0", lcall["ws"], 0)
    arrival, pos = enter(c)
    npc = {p["name"]: p["id"] for n, p in arrival if n.startswith("userInfo")}
    TECHNOGEEK, AARON = npc[652], npc[2424]
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.frames()
    check("own bars on entry", [n for n, _ in got], ["userInfo_Player", "usrUp"])
    check("full at birth", (got[1][1]["hcur"], got[1][1]["hmax"]), (120, 120))

    # --- the kit: rounds from the stall, the pistol worn and loaded ------------
    stall = [p for p in named(arrival, "userInfo_Trader") if p["type_list"][:1] == [PISTOL]][0]
    ammo_idx = stall["type_list"].index(ROUNDS)
    c.send("ss_create;s_type=1;target=%d;" % stall["id"])
    c.frames()
    c.send("ss_upd;param=200;obj=x%x;s_status=1;" % ammo_idx)
    got = c.frames()
    check("200 rounds bought", [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_heap", "userInfo_Player"])
    rounds = str(got[1][1]["obj"])
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.2)
    c.send("ss_get;target=0;slot=11;")
    lst = oids(c.frames()[0][1])
    pistol = [o for o in lst[8:] if inventory.parse_oid(o)[1] == PISTOL][0]
    c.send("ss_move;obj=x%s;to=512;from=2048;" % pistol)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
    got = c.frames()
    check("loading acknowledged", got[0], ("cmdAck", {"res": 0}))
    got = c.until(lambda f: f[0] == "ss_di_firearm")
    check("a full magazine", named(got, "ss_di_firearm")[0]["ammo_count"], CLIP)
    ammo = CLIP

    # --- the errand, and a home to come back to ----------------------------------
    c.send("q_st;mob=%d;q_idx=1;" % TECHNOGEEK)
    got = c.frames()
    check("the dog quest is taken", got,
          [("cmdAck", {"res": 0}),
           ("q_di_kill_mobs", dict(q_id=1, q_type=5, complete=0, kill_num=[0]))])
    c.send("on_conv;mob=%d;op=0;" % AARON)
    check("home registered on the market", c.frames(), [("cmdAck", {"res": 0})])

    # --- no fighting on the market: one refusal, nothing else --------------------
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, hexcell(pos + 1)))
    got = c.frames()
    check("a shot in a peaceful location is refused with one ack",
          ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))
    c.send("ss_use;type=16;obj=x0;target=%s;" % hexcell(pos + 1))
    got = c.frames()
    check("so is a punch", ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))

    # --- effects: the window of five must be answered ------------------------------
    c.send("e_get_si;type=3;")
    got = c.frames()
    check("e_si comes back for the type asked", (got[0][0], got[0][1]["type"]), ("e_si", 3))
    check("with a preloaded string id for its name",
          got[0][1]["name"] == quests.EMPTY_STRING_ID, True)
    check("and the immob/stun flags", (got[0][1]["immob"], got[0][1]["stun"]), (0, 0))
    c.send("e_get_di;type=3;mobi_id=0;")
    got = c.frames()
    check("e_di answered", (got[0][0], got[0][1]["type"], got[0][1]["mobi_id"]), ("e_di", 3, 0))

    # --- the dump: mobs with levels, bars and weapons -----------------------------
    c.send("userMsg;entry=@/goto 100@;group=0;")
    got = c.until(lambda f: f[0] == "lcall")
    lcall = named(got, "lcall")[0]
    check("the dump is called with ws=0 although war=1", (lcall["id"], lcall["ws"]), (100, 0))
    arrival, pos = enter(c)
    loc = world.location(100)
    check("the player stands on the entry cell", pos, loc.entry_cell())
    seq = [(n, p) for n, p in arrival]
    mob_infos = [(i, p) for i, (n, p) in enumerate(seq) if n == "userInfo"]
    check("the dump has mobs", len(mob_infos) > 5, True)
    check("every mob's userInfo is followed at once by its usrUp",
          all(seq[i + 1][0] == "usrUp" and seq[i + 1][1]["id"] == p["id"]
              and seq[i + 1][1]["hcur"] == seq[i + 1][1]["hmax"] > 0
              for i, p in mob_infos), True)
    check("the dog is level 1, the bum level 3",
          sorted({(p["name"], p["lvl"]) for _, p in mob_infos if p["name"] in (82, 411)}),
          [(82, 1), (411, 3)])
    check("an empty effect list is pushed for the player",
          named(arrival, "e_list"), [dict(mobi_id=0, effects=[])])
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    DOG_HOME = 4551
    dog = spawns[DOG_HOME]
    bum = [p["id"] for _, p in mob_infos if p["name"] == 411][0]
    dog_hp = [p for p in named(arrival, "usrUp") if p["id"] == dog][0]["hmax"]
    check("the dog's bar is the curve's", dog_hp, dog_stats.hp_max)

    c.send("ss_get;target=%d;slot=3;" % dog)
    check("a dog has bare paws: eight empty slots", oids(c.frames()[0][1]), ["0"] * 8)
    c.send("ss_get;target=%d;slot=3;" % bum)
    hands = oids(c.frames()[0][1])
    knife = inventory.parse_oid(hands[6])
    check("the bum holds a knife in the primary hand",
          (len(hands), hands[:6], hands[7], knife[1:]), (8, ["0"] * 6, "0", (195, items.COLD_ARM)))
    check("a virtual serial, far above the items table", knife[0] >= mobs.VIRTUAL_BASE, True)
    c.send("ss_get_di;obj=x%s;" % hands[6])
    got = c.frames()
    check("the knife's dynamic info is answered",
          (got[0][0], str(got[0][1]["obj"]), got[0][1]["break"] > 0), ("ss_di_coldarm", hands[6], True))
    c.send("ss_get_si;type=195;")
    check("and its static info", c.frames()[0][0], "ss_si_coldarm")

    # --- the first shot: ack, war state, aim, then the burst -----------------------
    check("the dog is out of its aggro radius but in pistol range",
          dog_stats.aggro < mobs.hex_distance(pos, DOG_HOME, loc.width) <= PISTOL_SI["max_range"][0],
          True)
    tracker = FireTracker()
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.frames(0.3)
    check("ack, then the room goes to war, then the aim",
          got, [("cmdAck", {"res": 0}), ("lch", {"ws": 1}),
                ("faAim", dict(id=0, ang=mobs.direction(pos, DOG_HOME, loc.width), num_shots=1))])
    tracker.feed(got)
    # The magazine report closes the burst; the experience and the dog's
    # reaction follow it in the same breath, so the window is held open a
    # moment longer to catch them.
    got = c.until(lambda f: f[0] == "ss_di_firearm") + c.frames(0.4)
    tracker.feed(got)
    names_ = [n for n, _ in got]
    first = names_.index("faShot")
    burst = names_[first:first + 3]
    check("one pair around the bullet's fate",
          (burst[0], burst[1] in ("faHit", "faMiss", "faWall"), burst[2]), ("faShot", True, "faShot"))
    check("the pair is the player's, open then closed",
          [p for n, p in got if n == "faShot"], [{"id": 0, "status": 1}, {"id": 0, "status": 0}])
    hit = named(got, "faHit")
    tail = names_[first + 3:]
    if hit:
        check("a hit names the dog and its damage",
              (hit[0]["target"], hit[0]["dmg"] + hit[0]["sdmg"] > 0), (dog, True))
        check("after the pair: the dog's bars, then c_ap, then the magazine",
              tail[:3], ["usrUp", "c_ap", "ss_di_firearm"])
        check("the dog's bar dropped",
              [p["hcur"] < dog_hp for n, p in got if n == "usrUp" and p["id"] == dog], [True])
        check("experience pushed for shooting",
              [bool(p["xp_skills_mask"] & 2) for p in named(got, "rp_info")][:1], [True])
    else:
        check("after the pair: c_ap, then the magazine", tail[:2], ["c_ap", "ss_di_firearm"])
    check("the burst cost one shot's action points", named(got, "c_ap")[0]["ap"], 50 - COST)
    ammo -= 1
    check("the magazine lost a round", named(got, "ss_di_firearm")[0]["ammo_count"], ammo)
    check("the dog turns on the shooter, and the room stays at war",
          [p for n, p in got if n == "lch"], [{"enemy": dog}])
    dog_cell = last_cell(got, dog, DOG_HOME)

    # --- leaving is refused right after a shot ------------------------------------------
    c.send("chWorld;")
    got = c.frames(0.4)
    tracker.feed(got)
    dog_cell = last_cell(got, dog, dog_cell)
    check("chWorld inside leave_combat_timeout: res=39 and no gmap",
          [(n, p) for n, p in got if n in ("cmdAck", "gmap", "lcall")], [("cmdAck", {"res": 39})])

    # --- moving cancels the aim, at no cost --------------------------------------------
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.until(lambda f: f[0] == "faAim" and f[1].get("id") == 0, 1)
    # This aim is about to be cancelled by a walk and owes no pairs.
    tracker.feed([f for f in got if not (f[0] == "faAim" and f[1].get("id") == 0)])
    dog_cell = last_cell(got, dog, dog_cell)
    check("second aim taken", [p for n, p in got if n == "faAim" and p["id"] == 0] != [], True)
    step = [n for n in progression.hex_neighbours(pos, loc.width, loc.height)
            if n not in loc.obstacles and n != dog_cell]
    step = max(step, key=lambda n: mobs.hex_distance(n, DOG_HOME, loc.width))
    c.send("moveTo;path=|%d|%d|;" % (pos, step))
    old_pos, pos = pos, step
    got = c.frames(1.5)
    tracker.feed(got)
    dog_cell = last_cell(got, dog, dog_cell)
    check("the walk is acknowledged and echoed",
          [(n, p) for n, p in got if n in ("cmdAck", "userMove") and p.get("id", 0) == 0][:2],
          [("cmdAck", {"res": 0}), ("userMove", {"id": 0, "path": [old_pos, pos]})])
    check("no bullet leaves after the walk",
          [p for n, p in got if n == "faShot" and p.get("id", 0) == 0], [])
    check("and nothing is charged or reported",
          [n for n, _ in got if n in ("c_ap", "ss_di_firearm")], [])
    c.send("ss_get_di;obj=x%s;" % pistol)
    got = c.until(lambda f: f[0] == "ss_di_firearm")
    tracker.feed([f for f in got if f[0] != "ss_di_firearm"])
    dog_cell = last_cell(got, dog, dog_cell)
    check("the magazine is untouched", named(got, "ss_di_firearm")[0]["ammo_count"], ammo)

    # --- the fight to the death ----------------------------------------------------------
    bites = hits_on_me = punched = 0
    ap_max = 50
    dead_frames = None
    for attempt in range(60):
        if ammo == 0:
            c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
            got = c.until(lambda f: f[0] == "ss_di_firearm" and str(f[1]["obj"]) == pistol, 3)
            tracker.feed(got)
            ammo = named(got, "ss_di_firearm")[-1]["ammo_count"]
            check("reloaded mid-fight", ammo, CLIP)
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
        got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "cmdAck" and f[1]["res"] != 0), 3)
        got += c.frames(0.2)
        tracker.feed(got)
        for i, (n, p) in enumerate(got):
            if n == "userMove" and p.get("id") == dog:
                dog_cell = p["path"][-1]
            elif n == "rp_info" and p.get("ap_max"):
                ap_max = p["ap_max"]          # a level-up widens the pool
            elif n == "caHit" and p.get("id") == dog:
                bites += 1
                check("a bite lands on the player as target 0", p["target"], 0)
                check("and the player's own bars follow it at once",
                      (got[i + 1][0], got[i + 1][1].get("id")), ("usrUp", 0))
                hits_on_me += 1
            elif n == "caMiss" and p.get("id") == dog:
                bites += 1
        if [p for n, p in got if n == "lch" and p.get("dead") == dog]:
            dead_frames = got
            break
        acks = named(got, "cmdAck")
        if acks and acks[0]["res"] != 0:
            check("only 'not enough AP' may refuse a shot mid-fight", acks[0]["res"], 11)
            time.sleep(0.7)
            continue
        if named(got, "ss_di_firearm"):
            ammo = named(got, "ss_di_firearm")[-1]["ammo_count"]
        if not punched and mobs.adjacent(pos, dog_cell, loc):
            # The dog is at the player's side: a bare-handed strike, which
            # lands at once (strike_time 0) and costs 5 AP.
            c.send("ss_use;type=16;obj=x0;target=%s;" % entity(dog))
            got = c.until(lambda f: f[0] == "c_ap", 2) + c.frames(0.2)
            tracker.feed(got)
            dog_cell = last_cell(got, dog, dog_cell)
            names_ = [n for n, _ in got]
            swing = [(n, p) for n, p in got if n in ("caHit", "caMiss") and p.get("id", 0) == 0]
            check("a punch: ack, then one caHit or caMiss of the player's",
                  (names_[0], len(swing)), ("cmdAck", 1))
            if swing[0][0] == "caHit":
                check("the punch names the dog", swing[0][1]["target"], dog)
                check("the dog's bars follow the punch",
                      [p["id"] for n, p in got if n == "usrUp" and p["id"] == dog] != [], True)
            else:
                check("a miss names the dog's hex", swing[0][1]["hex"], dog_cell)
            # The pool refills to the maximum between actions at the test's
            # regeneration, so the punch leaves at most max - 5.
            check("the fist costs 5 AP", named(got, "c_ap")[-1]["ap"] <= ap_max - combat.FIST_AP, True)
            punched = 1
            if [p for n, p in got if n == "lch" and p.get("dead") == dog]:
                dead_frames = got
                break
    check("the dog died within sixty shots", dead_frames is not None, True)
    check("the dog came and bit", bites > 0, True)
    check("the player's own bars followed a bite", hits_on_me > 0, True)
    check("every burst kept its shape", tracker.finish(), [])
    names_ = [n for n, _ in dead_frames]
    i_dead = [i for i, (n, p) in enumerate(dead_frames) if n == "lch" and p.get("dead") == dog][0]
    check("the kill is reported to the journal right after lch;dead",
          dead_frames[i_dead + 1], ("q_di_kill_mobs", dict(q_id=1, q_type=5, complete=0, kill_num=[1])))
    dog_cell = last_cell(dead_frames, dog, dog_cell)
    got = c.until(lambda f: f[0] == "ss_loot", 4)
    check("the corpse fades and a bag appears where it fell",
          only(got, "lch", "ss_loot"),
          [("lch", {"lostUser": dog}), ("ss_loot", {"s_status": 1, "hex": [dog_cell]})])
    # From here the room's own life goes on around the checks: the war
    # state ends leave_combat_timeout after the kill and the dog respawns,
    # whenever those fall; they are gathered and judged at the end.
    after = list(got)

    # --- the bag -------------------------------------------------------------------------------
    if not progression.within_reach(pos, dog_cell, loc.width, loc.height):
        pos, got = walk(c, loc, pos, lambda cell: mobs.adjacent(cell, dog_cell, loc), avoid={dog_cell})
        after += got
    c.send("ss_create;s_type=0;target=%d;" % dog_cell)
    got = c.frames()
    after += got
    check("the bag opens", only(got, "cmdAck"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=24;")
    got = c.frames()
    after += got
    lst = oids(named(got, "ss_ack")[0])
    divider = lst.index("0")
    bag, loot = lst[:divider], lst[divider + 1:]
    check("the bag lists the player's things, a 0, then the loot",
          (pistol not in bag, rounds in bag, len(loot) >= 1), (True, True, True))
    kinds = sorted({inventory.parse_oid(o)[1] for o in loot})
    check("a dog leaves meat, and maybe a fang or a skin",
          all(k in (216, 217, 218) for k in kinds) and 216 in kinds, True)
    c.send("ss_get_di;obj=x%s;" % loot[0])
    got = c.frames()
    after += got
    check("loot has dynamic info like anything else",
          [(n, p["size"]) for n, p in got if n == "ss_di_heap"], [("ss_di_heap", 1)])
    c.send("ss_upd;s_status=1;obj=x%s;param=1;" % loot[0])
    got = c.frames()
    after += got
    check("one piece taken", only(got, "cmdAck", "ss_loot", "ss_obj_status"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=8;")
    got = c.frames()
    after += got
    check("it is in the bag under the same id", loot[0] in oids(named(got, "ss_ack")[0]), True)
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % loot[0])
    got = c.frames()
    after += got
    check("and put back", only(got, "cmdAck", "ss_loot", "ss_obj_status"), [("cmdAck", {"res": 0})])
    c.send("ss_get;slot=24;")
    got = c.frames()
    after += got
    lst = oids(named(got, "ss_ack")[0])
    check("back on the ground", loot[0] in lst[lst.index("0") + 1:], True)
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = c.frames()
    after += got
    check("take all: ack, then the empty bag vanishes",
          only(got, "cmdAck", "ss_loot", "ss_obj_status"),
          [("cmdAck", {"res": 0}), ("ss_loot", {"s_status": 0, "hex": [dog_cell]})])
    c.send("ss_get;slot=8;")
    got = c.frames()
    after += got
    check("everything is in the bag", all(o in oids(named(got, "ss_ack")[0]) for o in loot), True)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    got = c.frames(0.3)
    after += got
    check("closing the bag is answered with nothing", only(got, "cmdAck", "ss_ack", "ss_loot"), [])
    # Out of the way of the dog that is about to come back, so peace can hold.
    pos, got = walk(c, loc, pos,
                    lambda cell: mobs.hex_distance(cell, DOG_HOME, loc.width) >= dog_stats.aggro + 1.5
                    and mobs.hex_distance(cell, DOG_HOME, loc.width) <= PISTOL_SI["max_range"][0] - 2)
    after += got

    # --- peace returns, the dog too ---------------------------------------------------------------
    after += c.frames(8)
    got = after
    tracker2 = FireTracker()
    tracker2.feed(got)
    check("nothing shoots while nobody fights", tracker2.finish(), [])
    check("the room leaves the war state after leave_combat_timeout",
          [p for n, p in got if n == "lch" and "ws" in p], [{"ws": 0}])
    back = [i for i, (n, p) in enumerate(got) if n == "lch" and p.get("newUser") == dog]
    check("the dog respawns under its old id on its spawn cell",
          [got[i][1] for i in back], [dict(newUser=dog, pos=DOG_HOME, rtype=0)])
    i = back[0]
    check("with its details and full bars right behind",
          (got[i + 1][0], got[i + 1][1]["id"], got[i + 1][1]["lvl"],
           got[i + 2][0], got[i + 2][1]["id"], got[i + 2][1]["hcur"]),
          ("userInfo", dog, 1, "usrUp", dog, dog_hp))
    c.send("chWorld;")
    got = c.frames()
    check("leaving is allowed once the timer ran out",
          [n for n, _ in got], ["cmdAck", "gmap", "marks"])
    # Back into the dump before logging out: a character that logs out on
    # the map is restored with on_map set, and the next sessions fight here.
    c.send("userMsg;entry=@/goto 100@;group=0;")
    c.until(lambda f: f[0] == "lcall")
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    check("the fight left the player alive", named(got, "usrUp")[0]["hcur"] > 0, True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    # --- a heal, on a wounded character with a bandage slipped into the bag -----------------
    store = accounts.Store(DB)
    char_id = store.db.execute("SELECT id FROM characters").fetchone()[0]
    heal_type = next(t for t, (root, name) in sorted(items.catalogue().items())
                     if root == items.HEAL and items.params_of(t) is not None)
    heal_row = store.create_item(char_id, heal_type, items.HEAL, slot=inventory.BAG, use_count=1)
    store.save_character_state(char_id, hp=60, sp=0)
    store.close()
    heal_oid = inventory.oid_of(heal_row)
    HEAL_SI = items.params_of(heal_type)

    c = Client(connect())
    lcall = login(c)
    check("the character is back in the dump", lcall["id"], 100)
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    check("wounded as written", (named(got, "usrUp")[0]["hcur"], named(got, "usrUp")[0]["scur"]), (60, 0))
    c.send("ss_use;type=2;obj=x%s;" % heal_oid)
    got = c.frames(0.3)
    check("a bandage: one ack at once", got, [("cmdAck", {"res": 0})])
    got = c.until(lambda f: f[0] == "ss_obj_status", HEAL_SI["heal_time"] / 1000.0 + 1.5)
    got += c.frames(0.3)         # the experience follows the item's removal
    heal = named(got, "heal")
    check("then, after heal_time, an absolute heal frame for oneself",
          (len(heal), heal and heal[0]["id"], heal and heal[0]["target"]), (1, 0, 0))
    check("healed by the item's range, stamina too",
          (HEAL_SI["min_h_rest"] <= heal[0]["hp"] - 60 <= HEAL_SI["max_h_rest"],
           heal[0]["sp"] >= 0), (True, True))
    check("a single-use bandage is removed",
          [(str(p["obj"]), p["status"]) for p in named(got, "ss_obj_status")], [(heal_oid, 0)])
    check("medicine gained experience",
          [bool(p["xp_skills_mask"] & 4) for p in named(got, "rp_info")], [True])
    c.send("logout;")
    c.frames(0.3)
    c.s.close()

    # --- death and resurrection ------------------------------------------------------------------
    store = accounts.Store(DB)
    store.save_character_state(char_id, hp=2, sp=0)
    store.close()
    c = Client(connect())
    login(c)
    arrival, pos = enter(c)
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    check("the dog is back on its cell for the newcomer", spawns.get(DOG_HOME), dog)
    c.send("ss_get;target=0;slot=2;")
    check("the pistol is still in hand", oids(c.frames()[0][1])[0], pistol)
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 30)
    check("the dog kills the wounded player: lch;dead=0",
          [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    bitten = [p for n, p in got if n == "caHit" and p.get("id") == dog]
    check("with a bite", len(bitten) >= 1, True)
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pistol, entity(dog)))
    got = c.frames(0.5)
    check("dead: a shot is refused with an ack and nothing follows",
          [(n, p) for n, p in got if n in ("cmdAck", "faAim")], [("cmdAck", {"res": 3})])
    c.send("moveTo;path=|%d|%d|;" % (pos, pos + 1))
    check("dead: a walk is dropped", [n for n, _ in c.frames(0.4) if n in ("cmdAck", "userMove", "breakMv")], [])
    c.send("resurrect;res_type=0;")
    got = c.until(lambda f: f[0] == "lcall", 2)
    check("resurrection is acknowledged and the character is called home",
          [(n, p.get("res", p.get("id"))) for n, p in got if n in ("cmdAck", "lcall")],
          [("cmdAck", 0), ("lcall", 102)])
    arrival, pos = enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until(lambda f: f[0] == "usrUp")
    v = named(got, "usrUp")[0]
    # A free resurrection is the penalised one: a quarter of the HP and no
    # stamina (combat.Fighter.resurrect). The prices and the rest of what
    # dying costs are test_death's.
    check("alive at home, on a free resurrection's quarter of the HP",
          (v["hcur"], v["hcur"] < v["hmax"], v["scur"]),
          (max(1, int(v["hmax"] * combat.FREE_HP_SHARE)), True, 0))
    c.send("logout;")
    c.frames(0.3)
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
print("combat OK")
