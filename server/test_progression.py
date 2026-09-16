"""The character's numbers: stored, derived, shown, bought and kept.

First the model on its own against the wiki tables and the client's readers
(PersAttributes.updateParam, Training.getCost, ReputationObject), then the
whole path over a socket: rp_info out of the database after newPers, the
teacher's window as Training.as drives it, and everything still there after
logging back in.
"""
import os
import threading
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import accounts
import progression
import world
from progression import Character
from protocol import decode

ENC = "utf-8"


def free_port():
    """A port nobody holds right now. The other suites pin theirs, and two
    of them run at once whenever two people work on the repository; a
    fixed number here would make this one fail for the wrong reason."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- the model ---------------------------------------------------------------
ch = Character()
check("a newborn has 25 stat rows", len(progression.starting_rows()), 25)
# "Таблица опыта", row "Уровень 1": 120 life and stamina at constitution 5.
check("HP = 4*strength + 20*constitution", ch.hp_max, 120)
check("SP = 4*agility + 20*constitution", ch.sp_max, 120)
check("action points = 50 + 5*best skill", ch.ap_max, 50)
check("weight = (30 + 2*strength) kg, in grams", ch.max_weight(), 40000)
check("base armour is the card's (3*agility + perception)/4", ch.armor, 5.0)
check("level is the best skill", ch.level, 0)
check("the first specialisation is free", ch.spec_cost(), (0, 0))

# The frame: a mask and a dense list per group, values only for the set bits.
p = ch.rp_info()
check("all five attributes", (p["a_attribs_mask"], p["a_attribs"]), (31, [5] * 5))
check("skills start at 0 with 100 to go",
      (p["a_skills"], p["xp_skills"], p["xp_max_skills"]),
      ([0] * 5, [0] * 5, [100] * 5))
check("specialisations start switched off",
      (p["a_specs_mask"], p["a_specs"]), (32767, [-1] * 15))
check("their thresholds wait at 1250", p["xp_max_specs"], [1250] * 15)
# SpecObject starts value_bonus at 0 and announces every change as a level
# gained, so an unlearned one is sent as 0, not -1.
check("unlearned f_specs are 0, not -1", p["f_specs"], [0] * 15)
check("one free slot", p["max_specs"], 1)
check("HP and SP are not in rp_info (usrUp carries them)",
      "hp" in p or "hp_max" in p or "sp" in p, False)

# A partial push carries only what changed; updateParam walks the mask.
p = ch.rp_info(attribs=set(), skills=set(), specs={2, 10})
check("partial mask names the two specs", p["a_specs_mask"], (1 << 2) | (1 << 10))
check("and the list is just as long", len(p["a_specs"]), 2)
check("other groups are empty, not absent", (p["a_attribs_mask"], p["a_attribs"]), (0, []))

# usrUp: full when nothing is stored, clamped to the maximum otherwise.
check("fresh vitals are full", ch.vitals(), dict(hcur=120, hmax=120, scur=120, smax=120))
ch.hp = 500
check("stored HP is clamped to the maximum", ch.vitals()["hcur"], 120)
ch.hp = None

# --- the teacher's rules (Training.getCost, PersAttributes min_skill_level) --
ch = Character()
check("shotguns need shooting 4", ch.learn_spec(3), progression.ERR_SKILL)
check("machine guns need shooting 16", ch.learn_spec(6), progression.ERR_SKILL)
check("a hidden production spec cannot be bought", ch.learn_spec(12), progression.ERR_STATE)
check("pistols are free at skill 0", ch.learn_spec(2), 0)
check("and now count as learned", (ch.spec[2], ch.specs_learned()), ([0, 0, 1250], 1))
check("buying it twice is refused", ch.learn_spec(2), progression.ERR_STATE)
check("the second costs 1000 afro", ch.spec_cost(), (1000, 0))
ch.afro = 999
check("999 afro is not enough", ch.learn_spec(0), progression.ERR_MONEY)
ch.afro = 1000
check("1000 afro is", ch.learn_spec(0), 0)
check("and is spent", ch.afro, 0)
check("the third costs 10 gold", ch.spec_cost(), (0, 10))
check("with no gold it is refused", ch.learn_spec(1), progression.ERR_MONEY)
ch.gold = 10
check("10 gold buys it", (ch.learn_spec(1), ch.gold), (0, 0))
check("then 30, 55, 75 gold", [progression.SPEC_COST[3], progression.SPEC_COST[4],
                              progression.SPEC_COST_MAX], [(0, 30), (0, 55), (0, 75)])
ch.max_specs = 5
check("free slots cover the count", ch.spec_cost(), (0, 0))

# Forgetting: the attribute drops by the level, nothing is refunded.
ch = Character()
ch.learn_spec(0)                       # рукопашный бой -> сила
ch.spec[0][0] = 3
ch.attrib[progression.STRENGTH] += 3
check("forgetting drops the attribute by the level",
      (ch.forget_spec(0), ch.attrib[progression.STRENGTH], ch.spec[0]),
      (0, 5, [-1, 0, 1250]))
check("forgetting what is not learned is refused", ch.forget_spec(0), progression.ERR_STATE)

# --- experience: thresholds from the wiki, constitution from the table -------
ch = Character()
changed = ch.gain_xp(progression.SHOOTING, 150)
check("150 xp lifts shooting to 1 with 50 carried", ch.skill[1], [1, 50, 200])
check("the changed skill is reported", changed["skills"], {1})
changed = ch.gain_xp(progression.SHOOTING, 150 + 400)   # 150 to reach 2, 400 to reach 3
check("shooting 3 after 550 more", ch.skill[1], [3, 0, 800])
# "Таблица опыта": at the fourth row (skill 3) constitution 7, life 160.
check("constitution follows the best skill", ch.attrib[progression.CONSTITUTION], 7)
check("and life with it", (ch.hp_max, ch.sp_max), (160, 160))
check("action points too", ch.ap_max, 65)
check("constitution is reported as changed", progression.CONSTITUTION in changed["attribs"], True)
ch.learn_spec(2)
changed = ch.gain_xp(progression.SHOOTING, 2500, spec_idx=2)
check("half of the award goes to the specialisation", ch.spec[2], [1, 0, 10000])
check("which raises its attribute by one", ch.attrib[progression.PERCEPTION], 6)
# The other half took shooting from 3 to 4, so constitution moved as well.
check("both reported, constitution included", (changed["specs"], changed["attribs"]),
      ({2}, {progression.PERCEPTION, progression.CONSTITUTION}))
check("shooting 4 gives constitution 8", (ch.skill[1][0], ch.attrib[progression.CONSTITUTION]), (4, 8))
check("skill thresholds double: 100 * 2^lvl", [progression.skill_xp_max(i) for i in (0, 1, 10, 20)],
      [100, 200, 102400, 104857600])
check("spec thresholds: 1250 * 8^lvl", [progression.spec_xp_max(i) for i in range(6)],
      [1250, 10000, 80000, 640000, 5120000, 40960000])

# --- premium: totals carry the share the client splits back out -------------
ch = Character()
ch.premium = 1
check("pr is the premium level", ch.player_info()["pr"], 1)
check("weight total includes the share", ch.max_weight(), 50000)
ch.gain_xp(progression.MELEE, 100)
check("experience total includes the share", ch.skill[0], [1, 25, 200])
ch.premium_until = int(time.time()) - 1
check("an expired premium counts as none", (ch.premium_level(), ch.max_weight()), (0, 40000))
# WeightPan's own arithmetic on the figure it is sent: bonus = v*b/(1+b).
b = progression.PREMIUM_WEIGHT_BONUS[1]
check("the client recovers +10 kg from 50000", round(50000 * b * 0.001 / (b + 1)), 10)

# --- reputation: one faction, capped below the last range's end ------------
ch = Character()
ch.add_rep(30000)
check("reputation is capped at 25599", ch.rep, 25599)
check("which is still the last rank", ch.rank(), 8)
ch.set_rep(-5)
check("and never negative", ch.rep, 0)
ch.set_rep(3200)
check("3200 is a desert ranger", (ch.rank(), progression.RANKS[ch.rank()][2]), (6, "Пустынный рейнджер"))

# --- the card's formulas ----------------------------------------------------
ch = Character()
check("melee evade = agi + per + melee + blades(-1)", progression.melee_evade(ch), 9)
check("pistol crit before bonuses",
      progression.crit_chance(ch, progression.PISTOL), ((5 * 8 + 5 * 4) / 4 + 0 - 1, (5 + 5) / 2 + 0 - 1))
check("no crit line for melee weapons", progression.crit_chance(ch, 99), None)
check("level gap clamps to +-4", (progression.level_gap(10, 2), progression.level_gap(0, 9)), (4, -4))

# --- hex adjacency, as LocationGrid.getSiblings counts it -------------------
W, H = 64, 40
check("an even row leans left", sorted(progression.hex_neighbours(2 * W + 5, W, H)),
      sorted([2 * W + 4, 2 * W + 6, W + 5, 3 * W + 5, 3 * W + 4, W + 4]))
check("an odd row leans right", sorted(progression.hex_neighbours(3 * W + 5, W, H)),
      sorted([3 * W + 4, 3 * W + 6, 2 * W + 5, 4 * W + 5, 4 * W + 6, 2 * W + 6]))
check("the same cell is within reach", progression.within_reach(7, 7, W, H), True)
check("two cells away is not", progression.within_reach(7, 9, W, H), False)

# --- persistence ------------------------------------------------------------
DB = os.path.join(tempfile.mkdtemp(), "progression.db")
store = accounts.Store(DB)
acc_id, _err = store.register("tester", "secret")
char_id, _slot = store.create_character(acc_id, "Ветеран", 0, "45676")
check("creation seeds the stat rows", len(store.load_stats(char_id)), 25)
ch = Character.load(store, char_id)
check("a loaded newborn has the starting purse", (ch.afro, ch.gold), (1000, 0))
ch.learn_spec(2)
ch.learn_spec(0)
ch.add_rep(50)
ch.hp = 77
ch.gain_xp(progression.SHOOTING, 150)
ch.save(store)
again = Character.load(accounts.Store(DB), char_id)
check("specialisations survive a reload", (again.spec[2], again.spec[0]), ([0, 0, 1250], [0, 0, 1250]))
check("so does the purse", (again.afro, again.gold), (0, 0))
check("and reputation, HP and skill xp", (again.rep, again.hp, again.skill[1]), (50, 77, [1, 50, 200]))
check("the cached level column follows", store.character(char_id)["level"], 1)
store.save_character_state(char_id, rep=99999)
check("an oversized stored reputation loads capped", Character.load(store, char_id).rep, 25599)
store.close()

# An older database: the characters table as it was, no char_stats at all.
OLD = os.path.join(tempfile.mkdtemp(), "old.db")
raw = sqlite3.connect(OLD)
raw.executescript("""
CREATE TABLE accounts (id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL UNIQUE, created INTEGER NOT NULL, banned INTEGER NOT NULL DEFAULT 0);
CREATE TABLE characters (id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
    slot INTEGER NOT NULL, name TEXT NOT NULL, sex INTEGER NOT NULL, res TEXT NOT NULL,
    loc INTEGER, pos INTEGER, gx REAL, gy REAL, on_map INTEGER NOT NULL DEFAULT 0,
    UNIQUE (account_id, slot));
INSERT INTO accounts VALUES (1, 'old', 'abc', 0, 0);
INSERT INTO characters (id, account_id, slot, name, sex, res, loc, pos) VALUES (1, 1, 0, 'Старый', 0, '45676', 102, 3809);
""")
raw.commit()
raw.close()
old = accounts.Store(OLD)
cols = {r["name"] for r in old.db.execute("PRAGMA table_info(characters)")}
check("migration adds the new columns",
      all(c in cols for c, _d in accounts.CHARACTER_COLUMNS), True)
check("an old character gets the newborn's rows", len(old.load_stats(1)), 25)
migrated = Character.load(old, 1)
check("and the newborn's numbers", (migrated.hp_max, migrated.afro, migrated.spec[0][0]), (120, 1000, -1))
check("its position is untouched", (old.character(1)["loc"], old.character(1)["pos"]), (102, 3809))
old.close()
check("opening it again changes nothing", len(accounts.Store(OLD).load_stats(1)), 25)


# --- over the socket --------------------------------------------------------
SDB = os.path.join(tempfile.mkdtemp(), "server.db")
accounts.DB_PATH = SDB
_store = accounts.Store(SDB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=SDB)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)



# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
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
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
        """Whatever arrives within the window, decoded."""
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [decode(f.decode(ENC)) for f in out if f]

    def until(self, name, timeout=15, settle=0.5):
        """Frames up to and including the first one called name, plus
        whatever follows it within settle seconds.

        A location opens only after its file is read, and on a slow disk
        that takes longer than any fixed window; waiting for the frame
        itself keeps the test about the protocol rather than the disk.
        """
        got = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            got += self.frames(0.3)
            if any(n == name for n, _p in got):
                return got + self.frames(settle)
        raise SystemExit("no %s frame within %ds; got %r"
                         % (name, timeout, [n for n, _p in got]))

    def names(self, wait=0.5):
        return [n for n, _p in self.frames(wait)]

    def close(self):
        self.s.close()


def one(frames, name):
    return next(p for n, p in frames if n == name)


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.until("accountInfo")
    c.send("newPers;res=45676;sex=0;name=@Ветеран@;")
    c.until("cmdAck")
    c.send("actPlayer;")
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.until("lenter")
    check("lenter carries the action-point ceiling", one(got, "lenter")["amax"], 50)

    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.until("usrUp")
    check("getInfo answers with the player and the vitals",
          [n for n, _p in got], ["userInfo_Player", "usrUp"])
    info = one(got, "userInfo_Player")
    check("level, premium, reputation, purse from the database",
          (info["lvl"], info["pr"], info["rep"], info["bg_rep"], info["afro"], info["gold"]),
          (0, 0, [0], 0, 1000, 0))
    check("vitals are the newborn's 120/120",
          one(got, "usrUp"), dict(id=0, hcur=120, hmax=120, scur=120, smax=120))

    c.send("rp_get_info;")
    got = c.until("rp_info")
    rp = one(got, "rp_info")
    check("rp_info: five attributes of 5", (rp["a_attribs_mask"], rp["a_attribs"]), (31, [5] * 5))
    check("rp_info: five skills at 0/100", (rp["a_skills_mask"], rp["a_skills"], rp["xp_max_skills"]),
          (31, [0] * 5, [100] * 5))
    check("rp_info: fifteen specs off", (rp["a_specs_mask"], rp["a_specs"]), (32767, [-1] * 15))
    check("rp_info: scalars", (rp["max_specs"], rp["ap_max"], rp["max_weight"], rp["armor"], rp["lvl"]),
          (1, 50, 40000, 5, 0))
    check("rp_info: no hp", "hp" in rp, False)

    # --- the teacher -----------------------------------------------------
    # The starting market has none; Абри's residential quarter spawns one
    # (type 4, Simple_SpecTrainer).
    c.send("userMsg;entry=@/goto 188@;group=0;")
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.until("lenter", settle=1.0)
    teacher = next(p for n, p in got if n == "lch" and p.get("rtype") == world.TEACHER)
    other = next(p for n, p in got if n == "lch" and p.get("rtype") != world.TEACHER)
    my_pos = one(got, "lenter")["pos"]
    loc = world.location(188)
    check("a teacher is placed", "newUser" in teacher, True)

    c.send("ss_create;s_type=4;target=%d;" % other["newUser"])
    got = c.until("cmdAck")
    check("training with a non-teacher is refused", one(got, "cmdAck")["res"], progression.ERR_NOT_FOUND)
    if not progression.within_reach(my_pos, teacher["pos"], loc.width, loc.height):
        c.send("ss_create;s_type=4;target=%d;" % teacher["newUser"])
        got = c.until("cmdAck")
        check("training from across the room is refused", one(got, "cmdAck")["res"], progression.ERR_TOO_FAR)

    # Walk up to the teacher. The server echoes any path today; a real one
    # would come from the client's own pathfinder.
    beside = progression.hex_neighbours(teacher["pos"], loc.width, loc.height)[0]
    c.send("moveTo;path=|%d|%d|;" % (my_pos, beside))
    c.until("userMove")
    c.send("ss_create;s_type=4;target=%d;" % teacher["newUser"])
    got = c.until("cmdAck")
    check("training opens beside the teacher", [n for n, _p in got], ["cmdAck"])
    check("with res=0", one(got, "cmdAck")["res"], 0)

    # Shotguns need shooting 4; the client cannot know (spec.xml says 0).
    c.send("ss_upd;obj=x3;s_status=2;")
    got = c.until("userMsg")
    check("the skill gate is the server's", [n for n, _p in got], ["cmdAck", "userMsg"])
    check("refused with the client's own 'not enough skill' code", one(got, "cmdAck")["res"], progression.ERR_SKILL)

    # Pistols: free, the first slot.
    c.send("ss_upd;obj=x2;s_status=2;")
    got = c.until("userInfo_Player")
    check("a purchase is acked, then pushed, then the purse",
          [n for n, _p in got], ["cmdAck", "rp_info", "userInfo_Player"])
    rp = one(got, "rp_info")
    check("the push names that spec alone", (rp["a_specs_mask"], rp["a_specs"], rp["f_specs"]),
          (1 << 2, [0], [0]))
    check("with its xp and threshold", (rp["xp_specs"], rp["xp_max_specs"]), ([0], [1250]))
    check("and its attribute", (rp["a_attribs_mask"], rp["a_attribs"]), (1 << progression.PERCEPTION, [5]))
    check("skills are left alone", (rp["a_skills_mask"], rp["a_skills"]), (0, []))
    check("the first one cost nothing", one(got, "userInfo_Player")["afro"], 1000)

    # Hand-to-hand: the second, 1000 afro.
    c.send("ss_upd;obj=x0;s_status=2;")
    got = c.until("userInfo_Player")
    check("the second is paid for", one(got, "userInfo_Player")["afro"], 0)
    check("and reported learned", one(got, "rp_info")["a_specs"], [0])

    # Blades: the third, 10 gold, and there is none.
    c.send("ss_upd;obj=x1;s_status=2;")
    got = c.until("userMsg")
    check("no gold, no third", [n for n, _p in got], ["cmdAck", "userMsg"])
    check("refused for money", one(got, "cmdAck")["res"], progression.ERR_MONEY)
    check("and the player is told why", "голда" in one(got, "userMsg")["entry"], True)

    # Reset hand-to-hand.
    c.send("ss_upd;obj=x0;s_status=1;")
    got = c.until("userInfo_Player")
    check("a reset is acked and pushed", [n for n, _p in got], ["cmdAck", "rp_info", "userInfo_Player"])
    check("the spec is off again", one(got, "rp_info")["a_specs"], [-1])
    check("nothing is refunded", one(got, "userInfo_Player")["afro"], 0)

    # Closing the window registers no handler: an answer here would be
    # consumed by whatever the client asks next.
    c.send("ss_upd;obj=x0;s_status=0;")
    check("closing is not acknowledged", c.frames(1.0), [])
    c.send("q_list;")
    check("and the queue is still in step", [n for n, _p in c.until("q_list")], ["q_list"])
    c.send("ss_upd;obj=x1;s_status=2;")
    check("outside a session ss_upd is the generic ack", [n for n, _p in c.until("cmdAck")], ["cmdAck"])

    # --- log back in -----------------------------------------------------
    c.send("logout;")
    c.close()
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    got = c.until("accountInfo")
    check("the character is listed again", "persInfo" in [n for n, _p in got], True)
    c.send("selPers;num=0;")
    got = c.until("lcall")
    check("selected without an ack", [n for n, _p in got], ["lcall"])
    c.send("lenter;accept=1;")
    c.until("lenter")
    c.send("rp_get_info;")
    rp = one(c.until("rp_info"), "rp_info")
    check("pistols are still learned", rp["a_specs"][2], 0)
    check("hand-to-hand is still reset", rp["a_specs"][0], -1)
    c.send("getInfo;lvl=0;id=0;type=0;")
    check("the purse is still spent", one(c.until("usrUp"), "userInfo_Player")["afro"], 0)
    c.send("logout;")
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("progression OK")
