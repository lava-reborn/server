"""The bank: one storage per character, opened at any of the city banks.

Every exchange below is the client's own, and so is the order it waits for
the answers in: lol/core/player/Gamer.as (proposeContact), Bank.as,
StuffManager.as, NPCService.as, gpui/BankInterface.as and PersEquip.as. The
client moves nothing by itself in this window -- a put only adds the item to
the banker's bag, a take only removes it from there -- so the ss_obj_status
after every success is what really moves it, and it is checked as closely
as the acknowledgement.

The storage starts at LAVA_BANK_BASE grams (100 here, so the first put
overflows) and grows by 50 kg for each ounce of gold, as the window's own
text promises.
"""
import logging
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))

# The black market's placeholder quests (Техногик 652, Аарон 2424, Шихаб
# 653, Точильный камень 2279) as they stood in data/quests.json until
# 2026-09-28, when they left it (the plan's correction а: texts of this
# server's, no row of the original, 3 paying half an ounce for a word). The
# suite plays the engine on them still, as fixtures put in front of the real
# table -- for this process and the server alike (quests.quests_path,
# LAVA_QUESTS) -- so their givers list them first.
BLACK_MARKET = [
    dict(type=1,
         kind="del_obj",
         name="Посылка для Аарона",
         start=("Слушай, %имя%, выручи. Аарон ждёт от меня расписку, а я от верстака "
                "отойти не могу. <hint>Передай ему на словах</hint>, что всё готово, — "
                "он тут же, на рынке, у сейфа."),
         notfinish="Ты от Техногика? Он обещал расписку... Так что передать-то велел?",
         finish=("Значит, всё готово? Хорошо. Передай Техногику, что я доволен. А это "
                 "тебе за ноги — %sex?сам:сама% понимаешь, лишними не будут."),
         give=[652],
         take=[2424],
         obj=0,
         rew_afro=50,
         rew_gold=0,
         repeatable=0,
         level=0,
         q_type=0),
    dict(type=2,
         kind="del_obj",
         name="Весточка Шихабу",
         start=("Раз уж ты бегаешь по рынку — скажи Шихабу, что его верблюды "
                "застрахованы. Он у загона, там, где сдают транспорт."),
         notfinish="От Аарона? Ну и что там с моими верблюдами?",
         finish="Застрахованы, говоришь? Хвала небесам. Держи за труды.",
         give=[2424],
         take=[653],
         obj=0,
         rew_afro=20,
         rew_gold=0,
         repeatable=1,
         level=0,
         q_type=0),
]

with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"), encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
_TABLE["quests"] = BLACK_MARKET + _TABLE["quests"]
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as _fh:
    json.dump(_TABLE, _fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts
import inventory
import items
import names
import progression
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "bank.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("alice", "secret")
_store.register("bob", "secret")
_store.close()
ALICE = accounts.credential("alice", "secret")
BOB = accounts.credential("bob", "secret")

BASE = 100                     # grams: less than the starting rounds weigh
HEAVY = 4160                   # a 40 kg crate: two of them overload anybody
PISTOL = inventory.STARTER_PISTOL
ROUNDS = inventory.STARTER_AMMO

from testkit import check, fails  # noqa: E402


# --- in process: the table, and the strings it puts on the wire -------------
check("the four city banks", sorted(inventory.BANK_TYPES), [729, 1170, 2424, 5228])
MOB_TYPES = world.mob_types()
check("all of them commoners, the only class that can bank (Gamer.proposeContact)",
      {MOB_TYPES[t][0] for t in inventory.BANK_TYPES}, {world.COMMONER})
# name= is the type id itself (server.send_npc_info): a type missing from the
# preload would send the client for a string batch and back to the login.
check("every bank's name is in the preload",
      [t for t in sorted(inventory.BANK_TYPES) if not names.known(t)], [])
check("a stored row has a slot of its own, on the session bit",
      (inventory.BANK, inventory.BANK >> 8), (4096, inventory.MASK_SESSION))
check("50 kg for an ounce, as the window says",
      (inventory.BANK_STEP, inventory.BANK_STEP_GOLD), (50000, 100))
check("nothing can be moved into storage by ss_move",
      inventory.fits({"root": items.AMMO, "type_id": ROUNDS}, inventory.BANK), False)
check("the crate is as heavy as the scene needs",
      items.params_of(HEAVY)["weight"], 40000)


# --- in process: exactly one cmdAck, whatever breaks -------------------------
# Session.handle logs an exception and answers nothing, so the bank has to
# answer for itself. A fake session and store make the failures happen on
# purpose; the traceback goes to a null handler instead of the test's output.
logging.getLogger("lava").addHandler(logging.NullHandler())


class FakeRoom:
    def __init__(self, npcs, broken=False):
        self.npcs, self.broken = npcs, broken

    def npc(self, eid):
        if self.broken:
            raise RuntimeError("room went away")
        return self.npcs.get(eid)


class FakeStore:
    def __init__(self, rows, broken=()):
        self.rows, self.broken = rows, set(broken)

    def item(self, uniq):
        return self.rows.get(uniq)

    def items_of(self, char_id):
        return [r for r in self.rows.values() if r["char_id"] == char_id]

    def character(self, char_id):
        if "character" in self.broken:
            raise RuntimeError("database gone")
        return {"bank_steps": 0}

    def update_item(self, uniq, **fields):
        if "update" in self.broken:
            raise RuntimeError("disk full")
        self.rows[uniq].update(fields)


class FakeSession:
    char_id = 7
    pos = 3740

    def __init__(self, room):
        self.room = room
        self.loc = SimpleNamespace(width=64, height=128)
        self.sent = []

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def say(self, text, group=0):
        self.sent.append(("userMsg", {"entry": text}))


def fake(room, broken=()):
    rows = {5: dict(uniq=5, char_id=7, type_id=ROUNDS, root=items.AMMO,
                    slot=inventory.BAG, count=1)}
    sess = FakeSession(room)
    return inventory.Inventory(sess, FakeStore(rows, broken)), sess, rows


def acks(sess):
    return [p["res"] for n, p in sess.sent if n == "cmdAck"]


BANKER = {40: (2786, 5228, world.COMMONER)}
inv, sess, _rows = fake(FakeRoom(BANKER, broken=True))
inv.open_bank({"target": "40", "s_type": "3"})
check("open: a failure before the answer is answered with one refusal",
      (sess.sent, inv.bank), ([("cmdAck", {"res": inventory.RES_REFUSED})], None))
inv, sess, _rows = fake(FakeRoom(BANKER), broken=("character",))
inv.open_bank({"target": "40", "s_type": "3"})
check("open: a failure after the answer adds no second one", acks(sess), [0])
inv, sess, rows = fake(FakeRoom(BANKER), broken=("update",))
inv.bank = 40
handled = inv.bank_upd({"s_status": "1", "obj": inventory.oid(5, ROUNDS, items.AMMO)})
check("put: a failure half way is still one answer, a refusal",
      (handled, sess.sent), (True, [("cmdAck", {"res": inventory.RES_REFUSED})]))
check("and the row stays in the bag", rows[5]["slot"], inventory.BAG)
inv, sess, _rows = fake(FakeRoom(BANKER, broken=True))
inv.bank = 40
check("close is answered with nothing even when the room is broken",
      (inv.bank_upd({"s_status": "0", "obj": "0"}), sess.sent, inv.bank),
      (True, [], None))
inv, sess, _rows = fake(FakeRoom(BANKER, broken=True))
inv.bank = 40
inv.bank_upd({"s_status": "6"})
check("expand: the broken room is one refusal", acks(sess), [inventory.RES_REFUSED])
inv, sess, _rows = fake(FakeRoom(BANKER))
check("with no bank open, ss_upd is somebody else's",
      (inv.bank_upd({"s_status": "1", "obj": "0"}), sess.sent), (False, []))


# --- in process: an expansion is paid for and given at once, or not at all ----
# The purse and the count of expansions are two columns of one row. Written
# by two commits, a stop between them kept the ounce and gave no capacity.
# So every write the expansion sends is tried as the place the process dies:
# the write raises, the connection is closed without a commit, and a fresh
# one reads what stayed. The copy of the purse in memory is held to the same
# rule, since Character.save writes it back at the next save.
XDB = os.path.join(tempfile.mkdtemp(), "expand.db")
_x = accounts.Store(XDB)
XCHAR, _ = _x.create_character(_x.register("expander", "secret")[0], "Expander", 0, "1")
_x.close()


class Died(Exception):
    pass


def expand(die_at=None):
    """One expansion with 2.5 ounces in the purse, the process dying at its
    die_at-th write. Returns (answers, (gold, steps) as a fresh connection
    reads them, gold in memory, writes sent)."""
    st = accounts.Store(XDB)
    st.save_character_state(XCHAR, gold=250, bank_steps=0)
    ch = progression.Character.load(st, XCHAR)
    sess = FakeSession(FakeRoom(BANKER))
    sess.char_id = XCHAR
    sess.character = lambda: ch
    sess.send_player_info = lambda: sess.sent.append(("userInfo_Player", {}))
    inv = inventory.Inventory(sess, st)
    inv.bank = 40
    real, writes = st.db.execute, [0]

    def execute(sql, args=()):
        if sql.split(None, 1)[0].upper() in ("INSERT", "UPDATE", "DELETE"):
            writes[0] += 1
            if writes[0] == die_at:
                raise Died("the process stops here")
        return real(sql, args)
    st.db.execute = execute
    inv.bank_upd({"s_status": "6"})
    st.close()
    st = accounts.Store(XDB)
    row = st.character(XCHAR)
    st.close()
    return acks(sess), (row["gold"], row["bank_steps"]), ch.gold, writes[0]


answers, stored, held, n = expand()
check("an expansion: one answer, an ounce less and a step more, the memory agreeing",
      (answers, stored, held), ([inventory.RES_OK], (150, 1), 150))
for k in range(1, n + 1):
    answers, stored, held, _n = expand(k)
    check("the process dying at write %d of %d: a refusal, and nothing paid for nothing" % (k, n),
          (answers, stored, held), ([inventory.RES_REFUSED], (250, 0), 250))


# --- the server --------------------------------------------------------------
# The Nubian market (location 185), where the safe 5228 stands. /goto, /give
# and /money set the scene; they are off on a served server.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_GX="6268", LAVA_GY="1825", LAVA_POLICY_PORT="0",
           LAVA_CHEATS="1", LAVA_BANK_BASE=str(BASE))
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
# Drain the log as it comes: a full pipe stops the server mid-reply.
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

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [decode(f.decode(ENC)) for f in out if f]


def named(frames, name):
    return [p for n, p in frames if n == name]


def oids(frames):
    return [str(x) for x in named(frames, "ss_ack")[0]["o_list"]]


def storage(frames):
    """What follows the first "0" of a mask-24 list: the bank's side."""
    lst = oids(frames)
    return lst[lst.index("0") + 1:]


def shape(frames):
    """(name, res or status or s_status, obj) per frame: what the bank
    window reads out of each."""
    out = []
    for n, p in frames:
        code = p.get("res", p.get("status", p.get("s_status")))
        out.append((n, code, str(p["obj"]) if "obj" in p else None))
    return out


def login(c, cred, first, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.frames()


def enter(c):
    """lenter;accept=1 -> (where we stand, {type id: (entity, cell, userInfo)})."""
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    cells = {p["newUser"]: p["pos"] for n, p in got if n == "lch" and "newUser" in p}
    people = {}
    for n, p in got:
        if n.startswith("userInfo") and p.get("id") in cells:
            people[p["name"]] = (p["id"], cells[p["id"]], dict(p, _cmd=n))
    return named(got, "lenter")[0]["pos"], people


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)
    return c.frames()


def walk(c, *cells):
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in cells))
    c.frames()


def beside(loc_id, cell):
    loc = world.location(loc_id)
    return progression.hex_neighbours(cell, loc.width, loc.height)[0]


def open_frames(max_g, cur_g):
    return [("cmdAck", 0, None), ("ss_upd", inventory.BANK_MAX, "%x" % max_g),
            ("ss_upd", inventory.BANK_CUR, "%x" % cur_g)]


def gold_of(frames):
    return [p["gold"] for p in named(frames, "userInfo_Player")]


try:
    # Bob first, so a letter has somebody to go to; he waits on the market.
    b = Client(connect())
    login(b, BOB, True, "Bob")
    bob_pos, _people = enter(b)

    a = Client(connect())
    login(a, ALICE, True, "Alice")
    pos, people = enter(a)

    # --- who is a bank ---------------------------------------------------------
    safe_id, safe_cell, safe = people[5228]
    check("the Nubian safe is a commoner that banks and offers no Прописка",
          (safe["_cmd"], safe["can_banking"], safe["can_set_home"]),
          ("userInfo_Commoner", 1, 0))
    muad = people[5186][2]
    check("an ordinary commoner (5186 Муад) neither registers homes nor banks",
          (muad["can_banking"], muad["can_set_home"]), (0, 0))

    a.send("ss_get;target=0;slot=11;")
    lst = oids(a.frames())
    pistol, rounds = lst[6], lst[8]
    check("the starting pistol in the hand, the rounds in the bag",
          [inventory.parse_oid(o)[1] for o in (pistol, rounds)], [PISTOL, ROUNDS])
    a.send("ss_get_di;obj=x%s;" % rounds)
    rounds_g = inventory.weight_of(dict(type_id=ROUNDS, root=items.AMMO,
                                        count=named(a.frames(), "ss_di_heap")[0]["size"]))
    check("and they weigh more than the empty storage holds", rounds_g > BASE, True)

    # --- what is not a bank ----------------------------------------------------
    a.send("ss_create;target=%d;s_type=3;" % people[5186][0])
    check("a commoner that is not a bank: 12, and nothing opens",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_create;target=99999;s_type=3;")
    check("an id nobody here has: 12", shape(a.frames()),
          [("cmdAck", inventory.RES_NOT_FOUND, None)])

    # --- opening -----------------------------------------------------------------
    # The client asks from wherever its walker stands the moment the click
    # lands, and a walker animates a path hex by hex -- while the server has
    # already put the player at the path's end. A click on the bank on the
    # way past is therefore beside it on the client and far off here, and
    # must still open (inventory.open_bank).
    loc185 = world.location(185)
    check("the entrance is not next to the safe",
          progression.within_reach(pos, safe_cell, loc185.width, loc185.height), False)
    near = beside(185, safe_cell)
    walk(a, pos, near, pos)
    a.send("ss_create;target=%d;s_type=3;" % safe_id)
    check("clicked on the way past: opens all the same -- cmdAck, then the"
          " capacity and the load, in hex grams", shape(a.frames()),
          open_frames(BASE, 0))
    a.send("ss_upd;obj=x0;s_status=0;")
    check("closing is answered with nothing (Bank.close registers no handler)",
          a.frames(), [])
    walk(a, pos, near)
    a.send("ss_create;target=%d;s_type=3;" % safe_id)
    check("standing beside it: the same three frames", shape(a.frames()),
          open_frames(BASE, 0))
    a.send("ss_get;slot=24;")
    check("mask 24: the bag, the divider, an empty storage",
          oids(a.frames()), [rounds, "0"])

    # --- a full storage, and buying more of it -------------------------------
    a.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    got = a.frames()
    check("a put that does not fit: 28, a code with no text, and a line of chat",
          [(n, p.get("res")) for n, p in got],
          [("cmdAck", inventory.RES_BANK_FULL), ("userMsg", None)])
    check("the line says how full it is",
          "Хранилище заполнено" in str(named(got, "userMsg")[0]["entry"]), True)

    a.send("ss_upd;s_status=6;")
    got = a.frames()
    check("expanding with no gold: 21 and a line of chat",
          [(n, p.get("res")) for n, p in got],
          [("cmdAck", inventory.RES_NO_MONEY), ("userMsg", None)])
    gold = gold_of(chat(a, "/money 0 150"))
    check("an ounce and a half in the purse", gold, [150])
    a.send("ss_upd;s_status=6;")
    got = a.frames()
    BIG = BASE + inventory.BANK_STEP
    check("expanding: the ack, the new capacity, then the purse",
          [(n, p.get("res", p.get("s_status")), str(p.get("obj", "")))
           for n, p in got if n != "userInfo_Player"]
          + [n for n, _ in got if n == "userInfo_Player"],
          [("cmdAck", 0, ""), ("ss_upd", inventory.BANK_MAX, "%x" % BIG),
           "userInfo_Player"])
    check("exactly one ounce taken", gold_of(got), [50])

    # --- put -----------------------------------------------------------------------
    a.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    check("put: the ack, the rounds leave the bag, the new load",
          shape(a.frames()),
          [("cmdAck", 0, None), ("ss_obj_status", 0, rounds),
           ("ss_upd", inventory.BANK_CUR, "%x" % rounds_g)])
    a.send("ss_get;slot=24;")
    check("mask 24 now: an empty bag, the divider, the rounds",
          oids(a.frames()), ["0", rounds])
    a.send("ss_get;target=0;slot=11;")
    check("the inventory's own list no longer shows them",
          oids(a.frames()), ["0"] * 6 + [pistol, "0"])
    a.send("ss_get_di;obj=x%s;" % rounds)
    check("a stored thing is still described when the window asks",
          [str(p["obj"]) for p in named(a.frames(), "ss_di_heap")], [rounds])

    # --- a stored thing is out of reach of every other verb -------------------
    a.send("ss_upd;obj=x%s;s_status=1;" % pistol)
    check("the gun in the hand cannot be put: the window shows the bag only",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    check("nor can the rounds be put twice",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_upd;obj=x%s;s_status=2;" % pistol)
    check("and the gun cannot be taken out of a storage it is not in",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_move;obj=x%s;from=4096;to=2048;" % rounds)
    check("ss_move cannot reach into storage",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_use;obj=x%s;type=0;" % rounds)
    check("nor can it be thrown away",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_heap_c;num=5;obj=x%s;" % rounds)
    check("nor split",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
    check("nor loaded from",
          shape(a.frames()), [("cmdAck", inventory.RES_NO_AMMO, None)])
    a.send("sndml;item=x%s;body=@@;type=0;subj=@x@;to=@Bob@;" % rounds)
    check("nor posted",
          shape(a.frames()), [("cmdAck", inventory.RES_REFUSED, None)])

    # --- close, and the queue is still straight -------------------------------
    a.send("ss_upd;obj=x0;s_status=0;")
    check("close: nothing at all", a.frames(), [])
    a.send("ss_create;target=%d;s_type=3;" % safe_id)
    check("so the next command gets exactly its own answer, and the storage"
          " remembers its capacity and load", shape(a.frames()),
          open_frames(BIG, rounds_g))

    # --- take ------------------------------------------------------------------------
    a.send("ss_upd;obj=x%s;s_status=2;" % rounds)
    check("take: the ack, the same id back into the bag, the new load",
          shape(a.frames()),
          [("cmdAck", 0, None), ("ss_obj_status", 1, rounds),
           ("ss_upd", inventory.BANK_CUR, "0")])
    a.send("ss_get;slot=24;")
    check("mask 24: the rounds in the bag again, the storage empty",
          oids(a.frames()), [rounds, "0"])

    # --- carried weight is the bag, not the bank --------------------------------
    got = chat(a, "/give %d" % HEAVY) + chat(a, "/give %d" % HEAVY)
    crates = [str(p["obj"]) for p in named(got, "ss_obj_status")]
    check("two crates of 40 kg in the bag", len(crates), 2)
    stall_id, _cell, stall = people[5212]
    check("the stall sells the starting pistol first", stall["type_list"][0], PISTOL)
    # The stall opens without the bank window being closed first: a new
    # session is what makes the old one stale, and its ss_upd codes are its own.
    a.send("ss_create;s_type=1;target=%d;" % stall_id)
    a.frames()
    a.send("ss_upd;param=1;obj=x0;s_status=1;")
    check("eighty kilos on the back: the stall refuses with 27",
          shape(a.frames()), [("cmdAck", inventory.RES_OVERLOAD, None)])
    a.send("ss_upd;obj=x0;s_status=0;")
    a.frames()
    a.send("ss_create;target=%d;s_type=3;" % safe_id)
    a.frames()
    a.send("ss_upd;obj=x%s;s_status=1;" % crates[0])
    check("one crate into storage",
          shape(a.frames()),
          [("cmdAck", 0, None), ("ss_obj_status", 0, crates[0]),
           ("ss_upd", inventory.BANK_CUR, "%x" % 40000)])
    a.send("ss_upd;obj=x%s;s_status=1;" % crates[1])
    check("the second does not fit in 50.1 kg: 28 and chat",
          [(n, p.get("res")) for n, p in a.frames()],
          [("cmdAck", inventory.RES_BANK_FULL), ("userMsg", None)])
    a.send("ss_create;s_type=1;target=%d;" % stall_id)
    a.frames()
    a.send("ss_upd;param=1;obj=x0;s_status=1;")
    got = a.frames()
    check("with one crate stored the same pistol is bought: storage is not"
          " carried, and a stall after the bank buys rather than banks",
          [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_firearm", "userInfo_Player"])
    check("bought", named(got, "cmdAck")[0]["res"], 0)
    a.send("ss_upd;param=1;obj=x%s;s_status=2;" % crates[0])
    check("and the stored crate cannot be sold to it",
          shape(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    a.send("ss_upd;obj=x0;s_status=0;")
    check("the stall closes in silence too", a.frames(), [])
    a.send("ss_create;target=%d;s_type=3;" % safe_id)
    a.frames()
    a.send("ss_upd;obj=x%s;s_status=2;" % crates[0])
    check("taking the crate back is not refused for weight: the window has"
          " already asked the player (BankInterface)",
          shape(a.frames()),
          [("cmdAck", 0, None), ("ss_obj_status", 1, crates[0]),
           ("ss_upd", inventory.BANK_CUR, "0")])
    a.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    check("and the rounds go back in for the road",
          [n for n, _ in a.frames()], ["cmdAck", "ss_obj_status", "ss_upd"])
    a.send("ss_upd;obj=x0;s_status=0;")
    a.frames()

    # --- 2424 on the black market: a bank that also has quests ---------------
    # With a quest to give, the client puts the quests tab first
    # (NPCService.openService), but the bank is still created by the
    # ss_create before it: refusing it would lose the quests with the bank.
    chat(a, "/goto 102")
    pos, people = enter(a)
    aaron_id, aaron_cell, aaron = people[2424]
    techno_id = people[652][0]
    check("2424 banks, offers no Прописка, gives quest 2 and takes quest 1",
          (aaron["_cmd"], aaron["can_banking"], aaron["can_set_home"],
           aaron["give_quests"], aaron["take_quests"]),
          ("userInfo_Commoner", 1, 0, [2], [1]))
    check("the technogeek beside it offers quests, not home registration",
          people[652][2]["can_set_home"], 0)
    a.send("q_st;mob=%d;q_idx=0;" % techno_id)
    got = a.frames()
    check("the delivery for Aaron taken from the technogeek",
          [n for n, _ in got], ["cmdAck", "q_di_del_obj"])
    # The id the log files it under: 1 in a fresh file, whatever comes next
    # in a database that already has quests in it (LAVA_DB_URL).
    delivery = named(got, "q_di_del_obj")[0]["q_id"] if named(got, "q_di_del_obj") else 1
    a.send("q_status;q_type=2;")
    check("and Aaron has a quest to give, so his quests tab comes first",
          named(a.frames(), "q_status")[0]["status"], 1)
    walk(a, pos, beside(102, aaron_cell))
    a.send("ss_create;target=%d;s_type=3;" % aaron_id)
    check("2424 opens beside it: the same storage, capacity and load as"
          " the Nubian safe left them", shape(a.frames()), open_frames(BIG, rounds_g))
    a.send("ss_get;slot=24;")
    check("one storage for every bank: the rounds put in at 5228 are here",
          storage(a.frames()), [rounds])
    a.send("q_co;obj_idx=0;mob=%d;q_id=%s;" % (aaron_id, delivery))
    got = a.frames()
    check("the delivery is handed in with the bank open",
          ([n for n, _ in got], named(got, "cmdAck")[0]["res"]),
          (["userInfo_Player", "cmdAck"], 0))
    a.send("q_st;mob=%d;q_idx=0;" % aaron_id)
    got = a.frames()
    check("and Aaron's own errand taken",
          ([n for n, _ in got], named(got, "cmdAck")[0]["res"]),
          (["cmdAck", "q_di_del_obj"], 0))
    a.send("ss_upd;obj=x%s;s_status=2;" % rounds)
    check("then the bank tab still works: the rounds come out here",
          shape(a.frames()),
          [("cmdAck", 0, None), ("ss_obj_status", 1, rounds),
           ("ss_upd", inventory.BANK_CUR, "0")])
    a.send("ss_upd;obj=x0;s_status=0;")
    check("closed in silence", a.frames(), [])

    # --- the other two city banks ----------------------------------------------
    chat(a, "/goto 188")
    pos, people = enter(a)
    abri_id, abri_cell, abri = people[1170]
    check("Abri's banker (1170) banks and offers no Прописка",
          (abri["can_banking"], abri["can_set_home"]), (1, 0))
    walk(a, pos, beside(188, abri_cell))
    a.send("ss_create;target=%d;s_type=3;" % abri_id)
    check("and opens the same storage", shape(a.frames()), open_frames(BIG, 0))
    a.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    check("the rounds stored in Abri",
          [n for n, _ in a.frames()], ["cmdAck", "ss_obj_status", "ss_upd"])
    a.send("ss_upd;obj=x0;s_status=0;")
    a.frames()
    chat(a, "/goto 35")
    pos, people = enter(a)
    david = people[729][2]
    check("the Wadi Halfa banker (729) banks and offers no Прописка",
          (david["can_banking"], david["can_set_home"]), (1, 0))

    # --- relogin: the storage and what was paid for it outlive the socket -----
    a.send("logout;")
    a.frames(0.3)
    a.s.close()
    a = Client(connect())
    login(a, ALICE, False, "Alice")
    pos, people = enter(a)
    david_id, david_cell, _ = people[729]
    walk(a, pos, beside(35, david_cell))
    a.send("ss_create;target=%d;s_type=3;" % david_id)
    check("after relogin: the bought capacity and the load are remembered",
          shape(a.frames()), open_frames(BIG, rounds_g))
    a.send("ss_get;slot=24;")
    check("and the rounds are still in storage", storage(a.frames()), [rounds])
    st = accounts.Store(DB)
    alice_id = st.db.execute("SELECT id FROM characters WHERE name = 'Alice'").fetchone()["id"]
    check("one expansion written down", st.character(alice_id)["bank_steps"], 1)
    st.close()

    # --- somebody else's storage -------------------------------------------------
    b.frames(0.2)
    walk(b, bob_pos, near)
    b.send("ss_create;target=%d;s_type=3;" % safe_id)
    check("Bob's own storage: the base capacity, empty",
          shape(b.frames()), open_frames(BASE, 0))
    b.send("ss_get;slot=24;")
    check("with nothing of Alice's in it", storage(b.frames()), [])
    b.send("ss_upd;obj=x%s;s_status=2;" % rounds)
    check("Bob cannot take Alice's rounds out",
          shape(b.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    b.send("ss_upd;obj=x%s;s_status=1;" % rounds)
    check("nor put them into his own",
          shape(b.frames()), [("cmdAck", inventory.RES_NOT_FOUND, None)])
    st = accounts.Store(DB)
    row = st.item(inventory.parse_oid(rounds)[0])
    check("the rounds are Alice's and stored, as they were",
          (row["char_id"], row["slot"]), (alice_id, inventory.BANK))
    st.close()
    a.send("logout;")
    b.send("logout;")
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-6000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("bank OK")
