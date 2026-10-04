"""Down the Nubian mine and back through its quests: Рудо's "Отправка в
шахту" at the mouth, Камал's "Выведи меня отсюда" on the first tier, its
bandits, the hold a bandit puts on the way out, and the tiers below.

153 "Скалы: Шахта" (6273,1829) draws the mouth of a mine with rails running
out of it and Рудо standing there, and has no zone to go in by. The way down
was his quest, and the way up Камал's (the wiki; texts.xml 59928-59943):
data/quests.json has both, as the original wrote them, and
data/passages.json says where each leads. Each is a quest in two steps, as
the owner reported it has to be (2026-09-25): taken, it is journalled like
any quest -- the ack and a q_di_del_obj, complete at once, and nothing
moves; handed in to the NPC who gave it, the finish is shown and then the
player is moved -- the q_co is acknowledged and an lcall follows, nothing
else: nothing is paid, the daily count stays where it was (a spent day
stops neither way), the journal is empty again and the NPC offers it again.
The hand-in is written into the history like any quest's (need_quest and
per_day count it, server.py cmd_q_co), and the day's count leaves it out.
A hand-in that names nobody who takes it, or is made from the map or at
the other end of the mine, is refused and moves nobody, and the quest
stays in the journal; a second q_co of one instance finds nothing. A quest
in the journal outlives the socket: the same character on a second socket
finds it there and hands it in once, the first socket moving nobody. A
bandit after the player does not refuse the hand-in -- the client words
every refused q_co as the daily limit -- and neither does the bandit's
taking him for its target, which it keeps for as long as he stays. What
holds the move is the exit timer a hit starts: the reason in chat, once, a
step in the room changes nothing, another hit keeps it running, and the
player goes up by himself the moment it has run out, the bandit still at
his heels (the other holds, and what ends a wait, are test_walk_in's).
The end of the rails and the cells under the EXIT sign, which used to be
walk-ins, are only ground now. The first tier's door down, and the second
tier's two, carry the client's own "up"/"down" signs, which is what the
table follows over data/exits.json's guess. A player on the map has no
inhabitant to take a quest from. And a click on the ground right behind
the hand-in button -- a moveTo that reaches the server after the lcall has
gone and before lenter -- is refused with its ack and moves nobody: its
cells are the mouth's, and the player is already on the tier.

Written against the code that moved the player at the take, it fails from
the table on -- nobody takes the ways back -- and on the socket at the
first take, which moves the player at once and journals nothing.
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
# The real table, for this process and the server alike, whatever the shell
# has set (travel.passages_path).
os.environ.pop("LAVA_PASSAGES", None)

sys.path.insert(0, HERE)
import accounts
import mobs
import names
import progression
import quests
import travel
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "mine.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("miner", "secret")
_store.close()
CRED = accounts.credential("miner", "secret")

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


MOUTH, TIER1, TIER2, TIER3 = 153, 612, 1011, 1217
MOUTH_CELL = (6273, 1829)
RUDO, KAMAL = 1133, 1134
DOWN, UP = 7, 8                     # their quests
GOLD = 9                            # Камал's «Золотоискатель» (test_mine_gold)
EMERALDS = 59                       # Камал's «Изумруды» (test_valley_market)
# Шульц's «Старые штольни», which sends the player to Рудо: the way down is
# offered after it, or after «Золотоискатель» (need_any), and Рудо takes it
# (test_valley_market).
OLD_ADITS = 57
OTHER = 10                          # Джеррах's «Обмен слитка», repeatable, for the day's
                                    # history (the market's «Голодные собаки», 5, left the
                                    # table on 2026-09-28)
BANDITS = (836, 837)
NO_SUCH = 1                         # server.RES_NO_SUCH: no such instance
WRONG_NPC = 2                       # server.RES_WRONG_NPC: nobody here takes it
NOT_READY = 3                       # server.RES_NOT_READY: a walk between rooms
DAILY_MAX = 10                      # server.DAILY_MAX: hand-ins a day
TIMER_LINE = re.compile(r"^Идёт бой: отправитесь через (\d+) с$")
HOLD = 8                            # LAVA_LEAVE_COMBAT for this run, seconds
RETRY = 1.0                         # server.PASSAGE_RETRY


def cells(loc, pairs):
    return {y * loc.width + x for x, y in pairs}


with open(os.path.join(os.path.dirname(HERE), "data", "passages.json"),
          encoding="utf-8") as fh:
    TABLE = json.load(fh)
mouth, tier1 = world.location(MOUTH), world.location(TIER1)
WAYS = {(int(key), rec["quest"]): rec for key, rows in TABLE.get("quest", {}).items()
        for rec in rows}
# Where the ways are drawn: the end of the rails, and the cells under the
# EXIT sign at (50,19). Walk-ins until now; ground to walk on from here.
RAILS_END = cells(mouth, [(47, 24), (48, 24), (46, 25), (47, 25), (48, 25), (47, 26),
                          (48, 26)])
UNDER_SIGN = cells(tier1, [(49, 19), (48, 20), (49, 20), (50, 20)])
# The alcove at the rails' end: where a player comes out of the mine.
ALCOVE = {c for c in mouth.entries
          if 42 <= c % mouth.width <= 49 and 22 <= c // mouth.width <= 31}
# The first tier's north-east pocket, under its EXIT sign at (50,19).
POCKET = {c for c in tier1.entries if c % tier1.width >= 48 and c // tier1.width <= 26}

# --- the tables against the client's own files, in process --------------------
# Every row, not only the mine's: a row added later is held to the same.
check("the mine's mouth stands on its map cell",
      world.location_at(*MOUTH_CELL), MOUTH)
for key, doors in sorted(TABLE["doors"].items()):
    loc = world.location(int(key))
    for side, rec in sorted(doors.items()):
        check("%s %s: a door the file really has" % (key, side),
              side in travel.exit_sides(loc).values(), True)
        check("%s %s: leading to a file that exists" % (key, side),
              world.path_for(rec["target_loc_id"]) is not None, True)
        check("%s %s: rated to be followed, with its reason" % (key, side),
              (rec["confidence"] in travel.DOOR_CONFIDENCE, bool(rec.get("why"))),
              (True, True))
check("the mine has no walk-in any more: its quests are the way",
      (TABLE.get("walk_in", {}).get(str(MOUTH)), TABLE.get("walk_in", {}).get(str(TIER1)),
       travel.walk_ins(mouth), travel.walk_ins(tier1)), (None, None, [], []))
# The mine's two; the table's other rows (Демир's rides out of the valley
# and back, test_valley_story) are held to the same checks below.
check("the table names both ways of the mine",
      sorted(k for k in WAYS if k[0] in (MOUTH, TIER1, TIER2, TIER3)),
      [(MOUTH, DOWN), (TIER1, UP)])
for (key, qtype), rec in sorted(WAYS.items()):
    loc = world.location(key)
    q = quests.get(qtype)
    zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                   "zones", 4)}
    way = cells(loc, rec["cells"])
    check("%s: quest %d is in the quest table" % (key, qtype), q is not None, True)
    if q is None:
        continue
    # A way switched off in the table -- nobody gives or takes it, as the
    # boat to Заречье (412), or «В Хальфу!» while the owner kept the town
    # closed -- keeps its row here for the day it is switched back on, and
    # is nobody's to stand beside.
    if not q.give and not q.take:
        continue
    here = {s for _, s in loc.spawns}
    check("%s: given by somebody who stands here" % key,
          bool(q.give) and all(t in here for t in q.give), True)
    # And by nobody anywhere else: the way is asked of the room it is handed
    # in in, so a taker standing elsewhere would take it for nothing.
    elsewhere = sorted(
        (lid, t) for lid in (TIER1, TIER2, TIER3, MOUTH) if lid != key
        for t in {s for _, s in world.location(lid).spawns} if t in q.give)
    check("%s: and taken back by him alone, who stands nowhere else in the mine" % key,
          (q.take, elsewhere), (q.give, []))
    # Handed back, it moves the player and pays nothing; it carries nothing,
    # and taking it again must always be possible.
    # The way down comes after Шульц's «Старые штольни», the original's
    # order, or, for a veteran of the mine, after «Золотоискатель»; the way
    # out has no chain, whoever is below. Since a way is handed in in full
    # before the move (server.py cmd_q_co), a way may also be a lesson that
    # counts its kills and pays, or a gate with a level: Берт's course and
    # its lessons, the quarry's, the ore mines' and the boat's ways
    # (halfa-training-ways, 1682 and 351-449), which test_halfa_training
    # holds. Every other way is held to the bare ride here.
    if not (qtype == 1682 or 351 <= qtype <= 449):
        check("%s: quest %d is a way and nothing else" % (key, qtype),
              (q.kind, q.obj, q.rew_obj, q.rew_afro, q.rew_gold, q.repeatable,
               q.rew_loc, q.level, q.need_all, q.need_any),
              (quests.DEL_OBJ, 0, [], 0, 0, 1, 1, 0, [],
               [OLD_ADITS, GOLD] if qtype == DOWN else []))
        check("%s: taken, it is complete at once" % key,
              q.is_complete(q.fresh_progress()), True)
    check("%s: leading to a file that exists, with its reason" % key,
          (world.path_for(rec["target_loc_id"]) is not None,
           rec.get("why", "").startswith(("DESIGNED", "RECOVERED"))), (True, True))
    check("%s: drawn on ground a walker can stand on" % key,
          (len(way), sorted(c for c in way if c in loc.obstacles)), (len(rec["cells"]), []))
    check("%s: where the client opens no window and nobody arrives" % key,
          (sorted(way & zones), sorted(way & set(loc.entries))), ([], []))
check("the two ways lead to each other, drawn at the rails' end and under the sign",
      [(WAYS[k]["target_loc_id"], cells(loc, WAYS[k]["cells"])) if k in WAYS else None
       for k, loc in (((MOUTH, DOWN), mouth), ((TIER1, UP), tier1))],
      [(TIER1, RAILS_END), (MOUTH, UNDER_SIGN)])
check("the quests go by the original's names",
      [getattr(quests.get(t), "name", None) for t in (DOWN, UP)],
      ["Отправка в шахту", "Выведи меня отсюда"])
check("and their texts reach the string table, all four of each",
      [names.known(sid) and bool(names.text(sid))
       for t in (DOWN, UP) if quests.get(t) for sid in quests.get(t).string_ids()],
      [True] * 8)
check("the finish each shows at the hand-in is the original's",
      [quests.get(t).texts[quests.FINISH] for t in (DOWN, UP)],
      ["Подмога! Как вовремя!", "Ну, в дорогу!"])
check("the rails' end is a walk from the alcove Рудо guards",
      mobs.find_path(mouth, min(ALCOVE), lambda c: c in RAILS_END) is not None, True)
check("the EXIT sign is a walk from where the tier is arrived at",
      mobs.find_path(tier1, min(POCKET), lambda c: c in UNDER_SIGN) is not None, True)
check("the mine's bandits go by the original's names",
      [names.text(t) for t in BANDITS], ["[1] Слабый Мародёр", "[2] Мародёр"])

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX=str(MOUTH_CELL[0]), LAVA_GY=str(MOUTH_CELL[1]),
           LAVA_AP_REGEN="25", LAVA_RESPAWN="600", LAVA_SEED="7",
           LAVA_LEAVE_COMBAT=str(HOLD))
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
        except OSError:
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


def named(frames, name):
    return [p for n, p in frames if n == name]


def lines(frames):
    """What the server said in the location's chat, in order."""
    return [p["entry"] for p in named(frames, "userMsg")
            if p.get("nick") == "Сервер" and p.get("group") == 0]


def calls(frames):
    return [p["id"] for p in named(frames, "lcall")]


def entity(target_id):
    return "x1%08x" % target_id


def enter(c):
    """lenter;accept=1: (all frames, the cell the player stands on)."""
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return got, named(got, "lenter")[0]["pos"]


def walk(c, loc, start, goal, avoid=()):
    """A real path to the nearest goal cell, sent as the client sends it."""
    path = mobs.find_path(loc, start, goal, set(avoid))
    if path is None:
        raise RuntimeError("no path from %d in %d" % (start, loc.id))
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    return path


def stand_on(c, cell):
    c.send("moveTo;path=|%d|;" % cell)
    return c.frames(0.3)


def through_door(c, cell, label):
    """Stand on a door and press "в другую локацию" (chWorld;to=1): the
    acknowledgement, then the lcall; returns the location it calls."""
    stand_on(c, cell)
    c.send("chWorld;to=1;")
    got = c.frames()
    # Only the answer: a bandit that took him for its target walks and
    # snaps around him meanwhile (it keeps him while he stays).
    check(label, [(n, p.get("res")) for n, p in got if n in ("cmdAck", "lcall")][:2],
          [("cmdAck", 0), ("lcall", None)])
    return named(got, "lcall")[0]["id"] if named(got, "lcall") else None


def door_cell(loc, side):
    return min(c for c, s in travel.exit_sides(loc).items()
               if s == side and c not in loc.obstacles)


def npc(frames, type_id):
    """The userInfo_Commoner of this inhabitant among the frames, or {}."""
    return next((p for p in named(frames, "userInfo_Commoner") if p["name"] == type_id), {})


def take(c, npc_id, idx=0):
    """"Взять задание" on the NPC's idx-th quest -- his way, for Рудо and
    for Камал alike, is q_idx 0: q_st;mob;q_idx, as QuestInspector.getQuest
    sends it. Returns the frames up to the q_di or two seconds, and what
    follows in the next moment -- long enough for an lcall that should not
    come."""
    c.send("q_st;mob=%d;q_idx=%d;" % (npc_id, idx))
    return c.until(lambda f: f[0].startswith("q_di"), 2) + c.frames(0.8)


def journalled(frames):
    """The q_di_del_obj among the frames: (q_type, complete, obj) each."""
    return [(p["q_type"], p["complete"], p["obj"]) for p in named(frames, "q_di_del_obj")]


def q_id_of(frames):
    di = named(frames, "q_di_del_obj")
    return di[0]["q_id"] if di else 0


def hand_in(c, npc_id, q_id, wait=2):
    """The hand-in button of the NPC's window: q_co;obj_idx;mob;q_id, as
    QuestInspector.takeQuest sends it. The frames up to the lcall or wait
    seconds, and a moment more."""
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (npc_id, q_id))
    return c.until(lambda f: f[0] == "lcall", wait) + c.frames(0.4)


def answer(frames):
    """What the server said to the player himself, without the room's
    comings and goings (a bandit's steps and blows): acknowledgements,
    location calls, quest frames and the purse."""
    return [(n, p.get("res"), p.get("id")) for n, p in frames
            if n in ("cmdAck", "lcall", "userInfo_Player") or n.startswith("q_")]


def journal(c):
    c.send("q_list;")
    got = named(c.frames(), "q_list")
    return [(p["q_id"], p["q_types"]) for p in got]


def own_steps(frames):
    """The frames a walk of the player's own brought back: the ack, his
    userMove (id 0), and anything that would move him."""
    return [n for n, p in frames if n in ("cmdAck", "lcall")
            or (n == "userMove" and p.get("id") == 0)]


def log_in(first=False):
    """A fresh socket up to the lcall: a new character the first time, the
    existing one (slot 0) after."""
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@miner@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    return c, calls(c.until(lambda f: f[0] == "lcall"))


CHAR = None
try:
    c, first = log_in(first=True)
    check("the character starts at the mine's mouth", first, [MOUTH])
    # Ближний бой 50 before anything is seen, for the bandit below: his
    # fist lands every time, and the bandit's knife never gets through.
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    probe = accounts.Store(DB)
    row = probe.db.execute("SELECT id FROM characters WHERE name = ?", ("miner",)).fetchone()
    CHAR = row["id"]
    PURSE = probe.money(CHAR)
    ch = progression.Character.load(probe, CHAR)
    ch.skill[progression.MELEE] = [50, 0, progression.skill_xp_max(50)]
    ch.recalc()
    ch.save(probe)
    # A veteran of the mine: Камал's «Золотоискатель» handed in a day ago
    # (no hand-in of today's), Шульц's errand never taken -- as one who went
    # down before the ways wrote any history. The way down is offered after
    # either (need_any); a
    # newcomer, who has neither, walks Шульц's errand (test_valley_market).
    probe.finish_quest(0, CHAR, GOLD, when=int(time.time()) - 86400)
    probe.close()
    c, first = log_in()
    check("and is back there after the logout", first, [MOUTH])
    arrival, pos = enter(c)
    rudo = npc(arrival, RUDO)
    check("Рудо stands there, with his quest to give and to take back, and Шульц's"
          " errand to him to take",
          (rudo.get("give_quests"), rudo.get("take_quests")), ([DOWN], [DOWN, OLD_ADITS]))
    check("and the player arrives beside him, in the alcove at the rails' end",
          pos in ALCOVE, True)
    check("the daily count is full", [p["daily_available"] for p in named(arrival, "q_sys")],
          [DAILY_MAX])

    # --- what the client asks before it shows the quest ------------------------------
    # q_status for every type an NPC lists, q_si for the description, q_list
    # once: each is answered by a frame, and the quest is on offer.
    c.send("q_status;q_type=%d;" % DOWN)
    got = c.frames()
    check("the quest is on offer, under its name",
          named(got, "q_status"),
          [{"type": DOWN, "status": 1, "q_type": 0,
            "name": quests.STRING_BASE + quests.STRINGS_PER_QUEST * DOWN + quests.NAME}])
    c.send("q_si;q_type=%d;" % DOWN)
    si = named(c.frames(), "q_si_del_obj")
    check("its description: moves the player after the hand-in, pays nothing, repeats",
          [(p["type"], p["rew_loc"], p["repeatable"], p["rew_afro"], p["rew_gold"],
            p["rew_obj"], p["obj"]) for p in si], [(DOWN, 1, 1, 0, 0, [], 0)])
    check("with all four texts, the finish too",
          [(p["name"], p["start_desc"], p["notfinish_desc"], p["finish_desc"]) for p in si],
          [quests.get(DOWN).string_ids()])
    check("the journal is empty", journal(c), [([], [])])

    # --- the end of the rails is ground now ------------------------------------------
    path = walk(c, mouth, pos, lambda cell: cell in RAILS_END)
    got = c.frames(0.2 * len(path) + 1.5)
    check("a walk to the end of the rails is a walk and nothing more",
          [n for n, _ in got], ["cmdAck", "userMove"])
    pos = path[-1]

    # --- down: Рудо's quest taken, then handed back to him ---------------------------
    got = take(c, rudo["id"])
    check("taking Рудо's quest: the one ack q_st is owed, then the quest, and nobody moves",
          (answer(got), journalled(got)),
          ([("cmdAck", 0, None), ("q_di_del_obj", None, None)], [(DOWN, 1, 1)]))
    Q = q_id_of(got)
    check("it is in the journal", journal(c), [([Q], [DOWN])])
    c.send("q_di;q_id=%d;" % Q)
    check("complete, asked again: there is nothing to do but hand it in",
          journalled(c.frames()), [(DOWN, 1, 1)])
    c.send("q_status;q_type=%d;" % DOWN)
    check("and still available, so the taker's list keeps it (QuestInspector.getTQs)",
          [p["status"] for p in named(c.frames(), "q_status")], [1])
    got = hand_in(c, rudo["id"], Q)
    check("handed back to Рудо: the one ack q_co is owed, then the mine opens",
          answer(got), [("cmdAck", 0, None), ("lcall", None, TIER1)])
    lcall = named(got, "lcall")
    if lcall:
        check("the mine keeps the map cell of its mouth, and is at peace",
              (lcall[0]["g_id"], lcall[0]["ws"]), (world.pack(*MOUTH_CELL), 0))
    check("and not a word in chat", lines(got), [])
    arrival, pos = enter(c)
    check("the player comes down under the EXIT sign", pos in POCKET, True)
    check("the hand-in cost none of the day's", [p["daily_available"]
                                                 for p in named(arrival, "q_sys")], [DAILY_MAX])
    check("and the journal is empty again", journal(c), [([], [])])
    check("a second q_co of the same instance finds nothing, and moves nobody",
          answer(hand_in(c, rudo["id"], Q, 0.6)), [("cmdAck", NO_SUCH, None)])
    kamal = npc(arrival, KAMAL)
    # The way out first, so "Взять задание" on q_idx 0 is still the way;
    # his gold-sand quest second, handed in to him as well.
    check("Камал stands by the way out, with it and his work quests to give and take",
          (kamal.get("give_quests"), kamal.get("take_quests")),
          ([UP, GOLD, EMERALDS], [UP, GOLD, EMERALDS]))
    mob_infos = named(arrival, "userInfo")
    check("the mine is full of bandits",
          (len(mob_infos) >= 20, {p["name"] for p in mob_infos} <= set(BANDITS)), (True, True))
    check("of their own levels",
          sorted({(p["name"], p["lvl"]) for p in mob_infos}), [(836, 1), (837, 2)])
    bandits = {p["newUser"]: p["pos"] for p in named(arrival, "lch") if "newUser" in p
               and p["newUser"] in {m["id"] for m in mob_infos}}

    # --- the EXIT sign is only a sign ---------------------------------------------------
    path = walk(c, tier1, pos, lambda cell: cell in UNDER_SIGN, avoid=bandits.values())
    got = c.frames(0.2 * len(path) + 1.5)
    check("a walk under the EXIT sign takes nobody up",
          own_steps(got), ["cmdAck", "userMove"])
    pos = path[-1]

    # --- Камал's quest taken; handed to nobody who takes it -----------------------------
    got = take(c, kamal["id"])
    check("taking Камал's quest: the ack and the quest, nobody moves",
          (answer(got), journalled(got)),
          ([("cmdAck", 0, None), ("q_di_del_obj", None, None)], [(UP, 1, 1)]))
    Q = q_id_of(got)
    # Hand-made frames: the client offers the hand-in only at an inhabitant
    # whose take_quests has it, and only one who stands in this room.
    some_bandit = min(bandits) if bandits else 0
    for label, who in (("a bandit", some_bandit), ("Рудо, who is up at the mouth", rudo["id"]),
                       ("nobody at all", 999999)):
        got = hand_in(c, who, Q, 0.6)
        check("handed to %s: refused, nobody moves" % label,
              answer(got), [("cmdAck", WRONG_NPC, None)])
    check("and the quest is in the journal still", journal(c), [([Q], [UP])])

    # --- one of them, woken and hit; the way up held by the exit timer ------------------
    # The player walks up to a bandit until it takes him as its target, and
    # punches it. The bandit keeps him as its target for as long as he is on
    # the tier (the owner's rule), but that is not what holds him: the exit
    # timer is, which the punch has started -- the countdown the client
    # shows from every hit given or taken. Камал's quest handed back now is
    # accepted and the move held, as chWorld is, or his quest would be the
    # way out of every fight in the mine; a step in the room changes
    # nothing; another punch keeps it held past where the first alone would
    # have let him go; and once the timer has run out he goes up by himself,
    # the bandit still at his heels. His Ближний бой (50, given him at the
    # start) lands his fist every time and keeps the bandit's knife off him,
    # so the only hits are his own.
    aggro = mobs.stats(837).aggro
    target = min(bandits, key=lambda b: mobs.hex_distance(bandits[b], pos, tier1.width))
    # Inside its aggro and nobody else's, so one bandit wakes and no other.
    near = [cell for cell in range(tier1.width * tier1.height)
            if cell not in tier1.obstacles and cell not in bandits.values()
            and mobs.hex_distance(cell, bandits[target], tier1.width) <= aggro - 1
            and all(mobs.hex_distance(cell, b, tier1.width) > aggro + 0.5
                    for i, b in bandits.items() if i != target)]
    check("somewhere only the nearest bandit will notice", bool(near), True)
    pos = min(near, key=lambda cell: mobs.hex_distance(cell, pos, tier1.width))
    c.send("moveTo;path=|%d|;" % pos)
    got = c.until(lambda f: f[0] == "lch" and f[1].get("enemy") == target, 4)
    check("the bandit takes the player for its target",
          [p["enemy"] for p in named(got, "lch") if "enemy" in p][:1], [target])
    seen = list(got)

    def bandit_cell():
        for n, p in reversed(seen):
            if n == "userMove" and p.get("id") == target:
                return p["path"][-1]
        return bandits[target]

    def beside():
        """Frames until the bandit stands next to the player, or 6 s."""
        deadline = time.time() + 6
        while not mobs.adjacent(pos, bandit_cell(), tier1) and time.time() < deadline:
            seen.extend(c.frames(0.2))
        return mobs.adjacent(pos, bandit_cell(), tier1)

    def punch():
        """The fist at the bandit until it lands: when it did, or None."""
        for _ in range(10):
            c.send("ss_use;type=16;obj=x0;target=%s;" % entity(target))
            got = c.until(lambda f: f[0] in ("caHit", "caMiss") and f[1].get("id", 0) == 0, 2)
            seen.extend(got)
            if [p for p in named(got, "caHit") if p.get("id", 0) == 0]:
                return time.time()
            time.sleep(0.3)
        return None

    check("it comes up to him", beside(), True)
    struck = punch()
    check("his fist lands on it", struck is not None, True)
    got = hand_in(c, kamal["id"], Q, 1.0)
    seen += got
    since = list(got)
    check("handed back to Камал with the timer running: accepted, and nobody moves",
          answer(got), [("cmdAck", 0, None)])
    said = lines(got)
    left = [int(m.group(1)) for m in map(TIMER_LINE.match, said[:1]) if m]
    check("the reason, in the location's chat, with the seconds the timer has left",
          (len(said), [0 < n <= HOLD for n in left]), (1, [True]))
    c.send("q_list;")
    got = c.frames()
    seen += got
    since += got
    check("the quest is out of the journal: it is handed in",
          [(p["q_id"], p["q_types"]) for p in named(got, "q_list")], [([], [])])
    # A step in the room does not end the wait: the player may have to
    # walk to get out of reach of what keeps hitting him.
    step = next((n for n in progression.hex_neighbours(pos, tier1.width, tier1.height)
                 if n in near and n != bandit_cell()), None)
    if step is not None:
        c.send("moveTo;path=|%d|%d|;" % (pos, step))
        got = c.frames(1.2)
        seen += got
        since += got
        check("a step while it waits moves him one cell and no further",
              (own_steps(got)[:2], calls(got)), (["cmdAck", "userMove"], []))
        pos = step
    check("the bandit follows him", beside(), True)
    again = punch()
    check("and his fist lands again", again is not None, True)
    since += c.frames(max(0.0, struck + HOLD + 0.5 - time.time()))
    check("past where the first punch alone would have let him go, the second holds him",
          calls(since), [])
    mark = len(since)
    if not calls(since):
        since += c.until(lambda f: f[0] == "lcall", again + HOLD + RETRY + 2 - time.time())
    took = time.time() - again
    check("the timer run out, the player goes up by himself: one lcall, to the mouth",
          calls(since), [MOUTH])
    check("not before", took >= HOLD - 0.5, True)
    check("the bandit at his heels all the while: snapping at him to the last, never "
          "landing, and the tier at war",
          ([n for n, p in since[mark:] if n == "caMiss" and p.get("id") == target] != [],
           [p for n, p in seen + since if n == "caHit" and p.get("id") == target],
           [p["ws"] for p in named(seen + since, "lch") if "ws" in p]),
          (True, [], [1]))
    check("to the mouth's own map cell",
          [p["g_id"] for p in named(since, "lcall")], [world.pack(*MOUTH_CELL)])
    check("told why once, not once a second", len(lines(since)), 1)
    arrival, pos = enter(c)
    check("out at the mouth, in the alcove", pos in ALCOVE, True)
    check("beside the end of the rails, not on it", pos in RAILS_END, False)
    check("no hand-in counted: the daily count is still full",
          [p["daily_available"] for p in named(arrival, "q_sys")], [DAILY_MAX])
    check("and nothing in the journal", journal(c), [([], [])])

    # --- again: the way down is always on offer ------------------------------------------
    rudo = npc(arrival, RUDO) or rudo
    c.send("q_status;q_type=%d;" % DOWN)
    check("Рудо's quest is on offer again", [p["status"] for p in named(c.frames(), "q_status")],
          [1])
    got = take(c, rudo["id"])
    check("taken again, it is journalled again", journalled(got), [(DOWN, 1, 1)])
    Q = q_id_of(got)
    # Handed in this time with a click on the ground right behind it: the
    # client sends moveTo until the lcall reaches it (FilterManager.
    # createCWFilter), so the walk arrives once the server has the player in
    # the first tier. Its cells are the mouth's, and numbered on the tier's
    # grid they are anywhere, rock included; the step is refused with the
    # ack its moveCmdAck waits for, and nothing moves.
    step = mobs.find_path(mouth, pos, lambda cell: cell not in POCKET
                          and mobs.hex_distance(cell, pos, mouth.width) >= 3)
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (rudo["id"], Q))
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in step))
    got = c.until(lambda f: f[0] == "lcall", 2) + c.frames(0.6)
    check("handed in, it takes the player down again; the step behind it is refused,"
          " and acknowledged",
          answer(got),
          [("cmdAck", 0, None), ("lcall", None, TIER1), ("cmdAck", NOT_READY, None)])
    check("with no walk of his own echoed, nor snapped back",
          [n for n, p in got if n in ("userMove", "breakMv") and p.get("id") == 0], [])
    arrival, pos = enter(c)
    check("under the EXIT sign again, not where the step's numbers fall on the tier",
          (pos in POCKET, pos == step[-1]), (True, False))
    kamal = npc(arrival, KAMAL) or kamal

    # --- up again, and the hand-in button pressed twice -----------------------------
    got = take(c, kamal["id"])
    Q = q_id_of(got)
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (kamal["id"], Q))
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (kamal["id"], Q))
    got = c.until(lambda f: f[0] == "lcall", 2) + c.frames(1.2)
    check("two hand-ins of one quest: one ack of each, and one lcall",
          answer(got), [("cmdAck", 0, None), ("lcall", None, MOUTH), ("cmdAck", NO_SUCH, None)])
    arrival, pos = enter(c)
    check("up at the mouth once, the day untouched",
          (pos in ALCOVE, [p["daily_available"] for p in named(arrival, "q_sys")]),
          (True, [DAILY_MAX]))

    # --- the quest in the journal outlives the socket -----------------------------------
    # Taken at the mouth and not handed in; the same character on a second
    # socket, the first still open: the server puts the older one away
    # (selPers), and the quest is in the journal of the new one.
    rudo = npc(arrival, RUDO) or rudo
    got = take(c, rudo["id"])
    Q = q_id_of(got)
    old = c
    c, first = log_in()
    check("back on a second socket, at the mouth", first, [MOUTH])
    arrival, pos = enter(c)
    rudo = npc(arrival, RUDO) or rudo
    check("with Рудо's quest in the journal", journal(c), [([Q], [DOWN])])
    c.send("q_di;q_id=%d;" % Q)
    check("complete, as it was taken", journalled(c.frames()), [(DOWN, 1, 1)])
    c.send("q_status;q_type=%d;" % DOWN)
    check("and available, so Рудо takes it back",
          [p["status"] for p in named(c.frames(), "q_status")], [1])
    try:
        old.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (rudo["id"], Q))
    except OSError:
        pass
    check("the older socket, put away, hands in nothing and is called nowhere",
          calls(old.frames(1.0)), [])
    got = hand_in(c, rudo["id"], Q)
    check("handed in on the new one: one ack, one lcall down",
          answer(got), [("cmdAck", 0, None), ("lcall", None, TIER1)])
    arrival, pos = enter(c)
    check("under the EXIT sign", pos in POCKET, True)
    kamal = npc(arrival, KAMAL) or kamal

    # --- carried out of the mine by the map, it is handed in nowhere -------------------
    # The map is a way out of the mine too: someone with the journal full,
    # whom the client will not let take Камал's quest (QuestInterface.getQuest),
    # is not shut in. Taken and carried off, the quest is harmless.
    got = take(c, kamal["id"])
    Q = q_id_of(got)
    c.send("chWorld;")
    got = c.until(lambda f: f[0] == "gmap")
    check("out on the map, from the first tier", [n for n, _ in got if n in ("cmdAck", "gmap")][:2],
          ["cmdAck", "gmap"])
    check("standing on the mouth's cell", [(p["x"], p["y"]) for p in named(got, "gmap")],
          [MOUTH_CELL])
    c.frames(0.3)
    got = hand_in(c, kamal["id"], Q, 0.6)
    check("Камал's quest handed in from the map: refused, nobody moves",
          answer(got), [("cmdAck", WRONG_NPC, None)])
    c.send("chWorld;")
    got = c.until(lambda f: f[0] == "lcall")
    check("back in from the map: the mouth", calls(got), [MOUTH])
    arrival, pos = enter(c)
    rudo = npc(arrival, RUDO) or rudo
    got = hand_in(c, rudo["id"], Q, 0.6)
    check("Камал's quest handed to Рудо: refused, nobody moves",
          answer(got), [("cmdAck", WRONG_NPC, None)])
    check("it stays in the journal, harmless", journal(c), [([Q], [UP])])
    c.send("q_ca;q_id=%d;" % Q)
    check("and can be dropped from it like any quest",
          ([p["res"] for p in named(c.frames(), "cmdAck")], journal(c)), ([0], [([], [])]))

    # --- a spent day stops neither way ---------------------------------------------------
    # Ten hand-ins of another quest today, written straight into the history.
    probe = accounts.Store(DB)
    for _ in range(DAILY_MAX):
        probe.finish_quest(0, CHAR, OTHER)
    probe.close()
    got = take(c, rudo["id"])
    Q = q_id_of(got)
    got = hand_in(c, rudo["id"], Q)
    check("the day spent, Рудо's quest still takes the player down",
          answer(got), [("cmdAck", 0, None), ("lcall", None, TIER1)])
    arrival, pos = enter(c)
    check("and the count says the day is spent, no less",
          [p["daily_available"] for p in named(arrival, "q_sys")], [0])

    # --- the tiers below, by their own signs ------------------------------------------
    tier2, tier3 = world.location(TIER2), world.location(TIER3)
    check("the first tier's door marked 'down' leads to the second",
          through_door(c, door_cell(tier1, "b"), "612 b acknowledged, then called"), TIER2)
    _, pos = enter(c)
    check("arriving by its ladder up, in the south-west", pos // tier2.width > 100, True)
    check("the second tier's door marked 'down' leads to the third",
          through_door(c, door_cell(tier2, "b"), "1011 b acknowledged, then called"), TIER3)
    _, pos = enter(c)
    check("arriving by its sign 'up', in the north-east", pos // tier3.width < 30, True)
    check("the third tier's door leads back up to the second",
          through_door(c, door_cell(tier3, "a"), "1217 a acknowledged, then called"), TIER2)
    _, pos = enter(c)
    check("arriving by the second tier's way down", pos // tier2.width < 30, True)
    check("and the ladder climbs back to the first",
          through_door(c, door_cell(tier2, "a"), "1011 a acknowledged, then called"), TIER1)
    arrival, pos = enter(c)
    check("arriving by the first tier's way down", pos // tier1.width > 100, True)

    # --- nor from the map --------------------------------------------------------------
    # A modified client's: on the map there is no location, so no Камал
    # to take a quest from, whatever id it names.
    kamal = npc(arrival, KAMAL) or kamal
    c.send("chWorld;")
    got = c.until(lambda f: f[0] == "gmap")
    check("out on the map", [n for n, _ in got if n in ("cmdAck", "gmap")][:2],
          ["cmdAck", "gmap"])
    c.frames(0.3)
    got = take(c, kamal["id"])
    check("Камал's quest asked from the map: refused, and nobody moves",
          ([n for n, p in got if n == "cmdAck" and p.get("res")], calls(got),
           journalled(got)), (["cmdAck"], [], []))
    c.send("logout;")
    c.frames(0.5)
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
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

# --- what the database kept of it all --------------------------------------------------
try:
    probe = accounts.Store(DB)
    if CHAR is not None:
        done = [r["type"] for r in probe.db.execute(
            "SELECT type FROM char_quests_done WHERE char_id = ?", (CHAR,)).fetchall()]
        ways = {DOWN, UP}
        check("no quest row; the history holds the day written into it, the veteran's"
              " gold and the ways handed in, both of them; and the purse as it was",
              (len(probe.quests(CHAR)), sorted(t for t in done if t not in ways),
               sorted({t for t in done if t in ways}), probe.money(CHAR)),
              (0, sorted([OTHER] * DAILY_MAX + [GOLD]), sorted(ways), PURSE))
    probe.close()
except Exception:
    import traceback
    fails.append("the database could not be read:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("mine OK")
