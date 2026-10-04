"""Barter between players: the proposal, the table, the exchange, and every
way it can end without one.

Every frame below is the client's own, in the order it sends them:
lol/core/player/Barter.as (UPD_* codes, what is acked and what goes out
bare), gpui/BarterInterface.as (the window: transfers, money, the ready
button) and Gamer.as (proposeContact for a player, ss_create for an
invitation). What each side must receive is what those classes read:

  * the invitee an ss_create naming the proposer, the proposer an ss_upd 1
    when the invitee agrees -- each opens its window on it and asks for its
    bag;
  * one cmdAck for 1, 3, 4, 7 and 8 and none at all for 0, 2, 5 and 6, or
    the client's cmdAck queue slides by one;
  * the other side's every move on the table relayed as the same ss_upd;
  * ss_upd 0 after EVERY end, the exchange included: the client's Barter
    dies nowhere else, and one left alive ignores the next invitation and
    reads a bank's weights as barter;
  * the bag as it really is behind every end (ss_obj_status), because the
    window closed by the server puts nothing back by itself.

The exchange is checked in the database as well as on the wire: who owns
each thing and what each purse holds, including when something changed
underneath it (another process writing the row, a purse that shrank), in
which case nothing at all may move.

Three players stand at the entrance of the Nubian settlement; the death
happens in the dump (location 100, pvp="1"), where a fist can reach.
"""
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts
import barter
import inventory
import items
import mobs
import progression
import rooms
import world
from protocol import decode


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "barter.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for login in ("alice", "bob", "carol"):
    _store.register(login, "secret")
_store.close()
ALICE, BOB, CAROL = (accounts.credential(n, "secret") for n in ("alice", "bob", "carol"))

BERETTA = 25586                 # pistols_1_lvl_2, exchang=1
ROUNDS = inventory.STARTER_AMMO  # a stack of 20, exchang=1
PREMIUM = 6067                  # Аптечка «Мини» (P): exchang=1, but premium
PAPER = 233                     # Бумага с посланием: exchang=0
DUMP = 100

SETTLE = 0.5                    # LAVA_BARTER_SETTLE for this run
WAIT = 6.0                      # LAVA_BARTER_WAIT
LEFTOVERS = 0.3                 # LAVA_BARTER_LEFTOVERS

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- in process: the rules the server applies before anything moves -----------
check("a Beretta may change hands", barter.tradable(BERETTA), True)
check("the starter rounds may too", barter.tradable(ROUNDS), True)
check("a premium thing may not, exchang or no (items.premium)",
      (items.params_of(PREMIUM)["exchang"], barter.tradable(PREMIUM)), (1, False))
check("nor anything with exchang=0",
      (items.params_of(PAPER)["exchang"], barter.tradable(PAPER)), (0, False))
check("nor the starter pistol, which the wiki marks untradable",
      barter.tradable(inventory.STARTER_PISTOL), False)
check("money arrives as num.toString(16): 300 afro", barter._sum("12c"), 300)
check("a fraction keeps what is before the point, as Number('0x'+..) does",
      barter._sum("1c.fffffffffffff"), 28)
check("nothing negative, nothing that is not a number",
      [barter._sum(v) for v in ("-5", "NaN", "", None)], [None] * 4)
check("the four bare codes are close, deny, ready and not ready",
      sorted(barter.BARE), [0, 2, 5, 6])


# --- in process: the exchange is one transaction --------------------------------
XDB = os.path.join(tempfile.mkdtemp(), "swap.db")
xs = accounts.Store(XDB)
xa, _ = xs.create_character(xs.register("xalpha", "secret")[0], "Xa", 0, "1")
xb, _ = xs.create_character(xs.register("xbeta", "secret")[0], "Xb", 0, "1")
gun = xs.create_item(xa, BERETTA, items.root_of(BERETTA), brk=90, max_break_cur=100)
ammo = xs.create_item(xb, ROUNDS, items.root_of(ROUNDS), count=20)
check("both halves at once: None, and every row the other's",
      xs.barter_swap([(gun, xb), (ammo, xa)], [(xa, 10, 0), (xb, 5, 7)]), None)
check("the gun is Xb's, the rounds Xa's",
      (xs.item(gun["uniq"])["char_id"], xs.item(ammo["uniq"])["char_id"]), (xb, xa))
check("and both purses are as written", (xs.money(xa), xs.money(xb)), ((10, 0), (5, 7)))
gun, ammo = xs.item(gun["uniq"]), xs.item(ammo["uniq"])
xs.update_item(ammo["uniq"], count=19)      # somebody fired one meanwhile
check("a stack that changed since it was offered: its serial back",
      xs.barter_swap([(gun, xa), (ammo, xb)], [(xa, 0, 0), (xb, 0, 0)]), ammo["uniq"])
check("and nothing moved at all -- not even the gun before it",
      (xs.item(gun["uniq"])["char_id"], xs.item(ammo["uniq"])["char_id"]), (xb, xa))
check("nor was any purse written", (xs.money(xa), xs.money(xb)), ((10, 0), (5, 7)))
xs.delete_item(gun["uniq"])
check("a thing that is gone is not traded either",
      xs.barter_swap([(gun, xa)], []), gun["uniq"])
xs.close()


# --- in process: an end that fails half way still closes both windows -----------
class _Gone:
    """A store whose connection dropped under it."""

    def item(self, uniq):
        raise RuntimeError("connection lost")


class _Mine:
    def __init__(self, char_id):
        self.char_id = char_id

    def item(self, uniq):
        return {"uniq": uniq, "char_id": self.char_id, "slot": inventory.BAG}


class _Side:
    """The parts of server.Session that barter.finish touches."""

    def __init__(self, nick, char_id, store):
        self.nick, self.char_id, self.closed = nick, char_id, False
        self.got = []
        self.inv = type("Inv", (), {})()
        self.inv.locked = set()
        self.inv.push_status = lambda row, status: self.got.append(("ss_obj_status", status))
        self.barter = barter.Barter(self, store, None)

    def send(self, cmd, **params):
        self.got.append((cmd, params.get("s_status")))

    def say(self, text, group=0):
        self.got.append(("say",))


xa_side, xb_side = _Side("Xa", 1, _Gone()), _Side("Xb", 2, _Mine(2))
deal = barter.Deal(xa_side, xb_side)
deal.open = True
xa_side.barter.deal = xb_side.barter.deal = deal
deal.proposer.items = {7: {"uniq": 7}}
deal.invitee.items = {8: {"uniq": 8}}
barter.log.disabled = True          # the traceback it logs is the point here
try:
    barter.finish(deal, {xa_side: "x", xb_side: "y"})
    escaped = None
except Exception as e:                                  # noqa: BLE001
    escaped = type(e).__name__
barter.log.disabled = False
check("a side whose bag cannot be read back does not stop the end: nothing"
      " escapes, and it has its close all the same",
      (escaped, xa_side.got[:1]), (None, [("ss_upd", barter.UPD_CLOSE)]))
check("and the other side gets its close, its bag and its line -- or its"
      " Barter would outlive the deal and block every invitation",
      xb_side.got, [("ss_upd", barter.UPD_CLOSE), ("ss_obj_status", 1), ("say",)])


# --- the server -------------------------------------------------------------------
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_GX="6268", LAVA_GY="1819", LAVA_POLICY_PORT="0",
           LAVA_CHEATS="1", LAVA_BARTER_SETTLE=str(SETTLE),
           LAVA_BARTER_WAIT=str(WAIT), LAVA_BARTER_LEFTOVERS=str(LEFTOVERS),
           # Enough action points for a few fists in a row (test_death).
           LAVA_AP_REGEN="25")
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


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


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

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.4):
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


def named(frames, name):
    return [p for n, p in frames if n == name]


def view(frames):
    """What a barter window and the bag read out of each frame, and only
    the frames they read: the acknowledgement, the barter frames, the bag,
    the purse, and whether the server said something in the chat."""
    out = []
    for n, p in frames:
        if n == "cmdAck":
            out.append(("cmdAck", p["res"]))
        elif n == "ss_upd":
            out.append(("ss_upd", p["s_status"], str(p.get("obj"))))
        elif n == "ss_create":
            out.append(("ss_create", p.get("target"), p.get("s_type")))
        elif n == "ss_obj_status":
            out.append(("ss_obj_status", p["status"], str(p["obj"])))
        elif n == "userInfo_Player" and p.get("id") == 0:
            out.append(("purse", p.get("afro"), p.get("gold")))
        elif n == "userMsg" and p.get("from") == 0:
            out.append(("say",))
    return out


def said(frames):
    return [str(p["entry"]) for n, p in frames if n == "userMsg" and p.get("from") == 0]


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
    return c.until(lambda f: f[0] == "lcall")


def enter(c):
    c.send("lenter;accept=1;")
    got = c.frames(wait=1.5)
    return got, named(got, "lenter")[0]["pos"]


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)
    return c.frames()


def given(frames):
    """The oid of the thing /give just put in the bag."""
    return [str(p["obj"]) for p in named(frames, "ss_obj_status") if p["status"] == 1][0]


def bag(c):
    c.send("ss_get;target=0;slot=8;")
    return [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]


def purse(frames):
    return [(p["afro"], p["gold"]) for p in named(frames, "userInfo_Player")
            if p.get("id") == 0]


def drain(*clients, wait=0.4):
    for c in clients:
        c.frames(wait)


def upd(c, code, obj="0"):
    c.send("ss_upd;obj=x%s;s_status=%d;" % (obj, code))


def propose(c, pid):
    c.send("ss_create;target=%d;s_type=2;" % pid)


def owner(oid):
    st = accounts.Store(DB)
    row = st.item(inventory.parse_oid(oid)[0])
    st.close()
    return row["char_id"] if row else None


def money_of(char_id):
    st = accounts.Store(DB)
    m = st.money(char_id)
    st.close()
    return m


def open_barter(proposer, invitee, pid_inv, pid_prop):
    """A proposes, B agrees, both windows ask for their bags; returns what
    each side saw on the way, as the view."""
    time.sleep(LEFTOVERS + 0.1)
    propose(proposer, pid_inv)
    got_p = proposer.frames()
    got_i = invitee.frames()
    upd(invitee, barter.UPD_AGREE)
    got_i += invitee.frames()
    got_p += proposer.frames()
    proposer.send("ss_get;slot=8;")
    invitee.send("ss_get;slot=8;")
    got_p += proposer.frames()
    got_i += invitee.frames()
    return view(got_p), view(got_i)


REFUSED = [("cmdAck", barter.RES_CANT), ("ss_upd", 0, "0"), ("say",)]

try:
    a = Client(connect())
    got = login(a, ALICE, True, "Alice")
    loc = world.location(named(got, "lcall")[0]["id"])
    _got, pos = enter(a)
    b = Client(connect())
    login(b, BOB, True, "Bob")
    arrival, pos_b = enter(b)
    c = Client(connect())
    login(c, CAROL, True, "Carol")
    _got, pos_c = enter(c)
    drain(a, b, c)
    check("all three at the settlement's entrance, side by side",
          (pos_b, pos_c), (pos, pos))
    # Characters get ids in the order they were made, and a player's entity
    # id follows from it (rooms.player_id).
    A_ID, B_ID, C_ID = 1, 2, 3
    pid_a, pid_b, pid_c = (rooms.player_id(i) for i in (A_ID, B_ID, C_ID))
    traders = [p["id"] for n, p in arrival if n == "userInfo_Trader"]
    check("the settlement has a trader to be busy with", traders != [], True)

    # The things on the table.
    beretta = given(chat(a, "/give %d" % BERETTA))
    # Not by /give, which refuses a premium thing since the owner's cut of
    # (P) (server.PREMIUM_REFUSED): written into Alice's bag behind the
    # session's back, as a thing from before the cut would lie there -- the
    # barter looks it up in the database (Inventory.find), as every verb does.
    _st = accounts.Store(DB)
    premium = inventory.oid_of(_st.create_item(A_ID, PREMIUM, items.root_of(PREMIUM)))
    _st.close()
    paper = given(chat(a, "/give %d" % PAPER))
    a.send("ss_get;target=0;slot=11;")
    kit_a = [str(x) for x in named(a.frames(), "ss_ack")[0]["o_list"]]
    pistol_a, rounds_a = kit_a[6], kit_a[8]
    b.send("ss_get;target=0;slot=11;")
    kit_b = [str(x) for x in named(b.frames(), "ss_ack")[0]["o_list"]]
    rounds_b = kit_b[8]
    beretta_b = given(chat(b, "/give %d" % BERETTA))
    purse_a = purse(chat(a, "/money 1000 0"))[0]
    purse_b = purse(chat(b, "/money 0 500"))[0]
    check("Alice has afro and Bob has gold to put on the table",
          (purse_a[0] >= 1000, purse_b[1] >= 500), (True, True))

    # --- proposals that cannot be made --------------------------------------------
    # Every refusal is the cmdAck the proposer waits for, then ss_upd 0: its
    # Barter would otherwise outlive the refusal and let it propose nothing
    # ever again (Gamer.proposeContact: if(!this.barter)).
    propose(a, 999999)
    check("to nobody: refused, then the proposer's Barter closed, and why",
          view(a.frames()), REFUSED)
    propose(a, pid_a)
    check("to oneself: the same", view(a.frames()), REFUSED)
    far = next(x for x in range(pos + 3, pos + 40)
               if mobs.hex_distance(pos, x, loc.width) >= 3)
    c.send("moveTo;path=|%d|%d|;" % (pos, far))
    drain(a, b, c)
    propose(a, pid_c)
    got = a.frames()
    check("to somebody three hexes off: refused", view(got), REFUSED)
    check("and the chat says why", ["далеко" in t for t in said(got)], [True])
    check("Carol hears nothing of it", view(c.frames()), [])
    c.send("moveTo;path=|%d|%d|;" % (far, pos))
    drain(a, b, c)
    c.send("ss_create;target=%d;s_type=1;" % traders[0])
    check("Carol opens a stall", view(c.frames()), [("cmdAck", 0)])
    propose(a, pid_c)
    got = a.frames()
    check("to somebody in a stall: refused -- its Trade would read every relay",
          (view(got), ["занят" in t for t in said(got)]), (REFUSED, [True]))
    check("and the stall is left alone", view(c.frames()), [])
    upd(c, 0)
    check("Carol shuts the stall, unanswered as ever", view(c.frames()), [])

    # --- an invitation, and a no ------------------------------------------------------
    propose(a, pid_b)
    check("Alice proposes to Bob: one cmdAck, 0", view(a.frames()), [("cmdAck", 0)])
    check("Bob is invited under Alice's id (Gamer.ss_create -> Barter.ss_create)",
          view(b.frames()), [("ss_create", pid_a, barter.SESSION_BARTER)])
    propose(c, pid_b)
    check("three of them: Carol cannot invite Bob while he is invited",
          view(c.frames()), REFUSED)
    propose(c, pid_a)
    check("nor Alice while she waits for him", view(c.frames()), REFUSED)
    check("and neither of them hears of it", (view(a.frames()), view(b.frames())),
          ([], []))
    upd(b, barter.UPD_DENY)
    got_b, got_a = b.frames(), a.frames()
    check("Bob says no: bare, so no cmdAck -- only the close his Barter needs",
          view(got_b), [("ss_upd", 0, "0")])
    check("Alice's waiting alert closes on ss_upd 0 (\"Игрок занят\"), and why",
          view(got_a), [("ss_upd", 0, "0"), ("say",)])
    check("in so many words", ["отказывается" in t for t in said(got_a)], [True])

    # --- the proposer changes her mind ---------------------------------------------------
    time.sleep(LEFTOVERS + 0.1)
    propose(a, pid_b)
    drain(a)
    check("invited again", view(b.frames()), [("ss_create", pid_a, 2)])
    upd(a, barter.UPD_DENY)          # awaitingAnswer: "Отказаться от бартера"
    check("Alice calls it off: bare, and her Barter is closed",
          view(a.frames()), [("ss_upd", 0, "0")])
    check("Bob's invitation goes the same way, with a word",
          view(b.frames()), [("ss_upd", 0, "0"), ("say",)])

    # --- an invitation nobody answers --------------------------------------------------
    time.sleep(LEFTOVERS + 0.1)
    propose(a, pid_b)
    drain(a, b)
    got_a = a.until(lambda f: f[0] == "ss_upd", WAIT + 2)
    got_a += a.frames()
    check("unanswered for LAVA_BARTER_WAIT: Alice's alert closes, and why",
          (view(got_a), ["не ответил" in t for t in said(got_a)]),
          ([("ss_upd", 0, "0"), ("say",)], [True]))
    check("and so does Bob's invitation", view(b.frames()), [("ss_upd", 0, "0")])

    # --- two invitations crossing ------------------------------------------------------
    # Bob's client built a Barter of its own (he clicked Carol) before
    # Alice's invitation reached it, so Gamer.ss_create passed hers by.
    time.sleep(LEFTOVERS + 0.1)
    propose(a, pid_b)
    drain(a, b)
    propose(b, pid_c)
    check("Bob proposes to Carol while invited by Alice: his proposal goes",
          view(b.frames()), [("cmdAck", 0)])
    check("Carol is invited by Bob", view(c.frames()), [("ss_create", pid_b, 2)])
    got_a = a.frames()
    check("and Alice, whose invitation he never saw, is told he is busy",
          (view(got_a), ["занят" in t for t in said(got_a)]),
          ([("ss_upd", 0, "0"), ("say",)], [True]))
    upd(c, barter.UPD_DENY)
    check("Carol says no", (view(c.frames()), view(b.frames())),
          ([("ss_upd", 0, "0")], [("ss_upd", 0, "0"), ("say",)]))

    # --- the table ---------------------------------------------------------------------
    got_a, got_b = open_barter(a, b, pid_b, pid_a)
    check("Bob agrees: his cmdAck opens his window (agreeBarterAck)",
          [v for v in got_b if v[0] != "ss_create"], [("cmdAck", 0)])
    check("Alice's opens on the relayed agree", got_a, [("cmdAck", 0), ("ss_upd", 1, "0")])

    # The barter window is modal, so a stall clicked now comes from a client
    # without one: its invitation was never shown, or applyBarter shut it.
    a.send("ss_create;target=%d;s_type=1;" % traders[0])
    got = a.frames()
    check("no stall while the barter is on -- its Trade would read the"
          " relays -- and the barter it cannot be looking at ends, and why",
          (view(got), ["отменён" in t for t in said(got)]),
          ([("cmdAck", barter.RES_CANT), ("ss_upd", 0, "0"), ("say",)], [True]))
    got = b.frames()
    check("Bob's window closes on it, and he is told she is busy",
          (view(got), ["занят" in t for t in said(got)]),
          ([("ss_upd", 0, "0"), ("say",)], [True]))
    got_a, got_b = open_barter(a, b, pid_b, pid_a)
    check("they start again", (got_a[-1:], got_b[-1:]),
          ([("ss_upd", 1, "0")], [("cmdAck", 0)]))
    propose(c, pid_a)
    check("nor may Carol cut in", view(c.frames()), REFUSED)

    upd(a, barter.UPD_TO_BUFFER, beretta)
    check("Alice puts the Beretta on the table: acked", view(a.frames()), [("cmdAck", 0)])
    check("Bob sees it arrive, by its id (addToVAVList)",
          view(b.frames()), [("ss_upd", 3, beretta)])
    b.send("ss_get_di;obj=x%s;" % beretta)
    b.send("ss_get_di;obj=x%s;" % beretta)
    got = b.frames()
    check("and the two ss_get_di his window sends for it get one answer each",
          [str(p["obj"]) for p in named(got, "ss_di_firearm")], [beretta, beretta])
    upd(a, barter.UPD_TO_BUFFER, beretta)
    check("the same thing twice: not found", view(a.frames()),
          [("cmdAck", barter.RES_NOT_FOUND)])
    upd(a, barter.UPD_TO_BUFFER, pistol_a)
    check("a thing in the hand: not found -- the window offers the bag only",
          view(a.frames()), [("cmdAck", barter.RES_NOT_FOUND)])
    upd(a, barter.UPD_TO_BUFFER, rounds_b)
    check("somebody else's thing: not found", view(a.frames()),
          [("cmdAck", barter.RES_NOT_FOUND)])
    upd(a, barter.UPD_TO_BUFFER, premium)
    got = a.frames()
    check("a premium thing: refused, and why", view(got), [("cmdAck", 31), ("say",)])
    upd(a, barter.UPD_TO_BUFFER, paper)
    check("an exchang=0 thing: refused", view(a.frames()), [("cmdAck", 31), ("say",)])
    check("Bob sees none of those", view(b.frames()), [])

    # What is on the table is out of reach of every other verb.
    a.send("ss_move;obj=x%s;from=2048;to=512;" % beretta)
    check("the Beretta on the table cannot be taken in hand",
          view(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND)])
    a.send("ss_use;obj=x%s;type=0;" % beretta)
    check("nor thrown away", view(a.frames()), [("cmdAck", inventory.RES_NOT_FOUND)])
    a.send("sndml;to=@Carol@;subj=@x@;type=0;body=@x@;item=x%s;afro=0;gold=0;" % beretta)
    check("nor posted to Carol", view(a.frames())[:1], [("cmdAck", 3)])
    check("and it is still Alice's", owner(beretta), A_ID)

    upd(a, barter.UPD_ADD_AFRO, "%x" % 300)
    check("300 afro on the table: acked", view(a.frames()), [("cmdAck", 0)])
    check("Bob reads the sum as Number('0x'+obj)", view(b.frames()), [("ss_upd", 7, "12c")])
    upd(a, barter.UPD_BREAK)         # changeAfro follows with readyToBarter(false)
    check("the bare 6 behind it: nothing back", view(a.frames()), [])
    check("relayed to Bob", view(b.frames()), [("ss_upd", 6, "0")])
    upd(a, barter.UPD_ADD_AFRO, "%x" % 99999999)
    check("more afro than the purse holds: 21, and why",
          view(a.frames()), [("cmdAck", barter.RES_NO_MONEY), ("say",)])
    check("Bob still sees 300", view(b.frames()), [])

    upd(b, barter.UPD_TO_BUFFER, rounds_b)
    check("Bob puts his rounds up", view(b.frames()), [("cmdAck", 0)])
    check("Alice sees them", view(a.frames()), [("ss_upd", 3, rounds_b)])
    b.send("ss_heap_c;obj=x%s;num=5;" % rounds_b)
    check("an offered stack cannot be split under the other's eyes",
          view(b.frames()), [("cmdAck", inventory.RES_NOT_FOUND)])
    upd(b, barter.UPD_TO_BAG, rounds_b)
    check("and back into the bag", view(b.frames()), [("cmdAck", 0)])
    check("Alice sees them go", view(a.frames()), [("ss_upd", 4, rounds_b)])
    upd(b, barter.UPD_TO_BAG, rounds_b)
    check("what is not on the table cannot come off it", view(b.frames()),
          [("cmdAck", barter.RES_NOT_FOUND)])
    upd(b, barter.UPD_TO_BUFFER, rounds_b)
    check("the rounds again", view(b.until(lambda f: f[0] == "cmdAck", 1.0)),
          [("cmdAck", 0)])
    upd(b, barter.UPD_ADD_GOLD, "%x" % 150)
    check("and 1.5 ounces", view(b.until(lambda f: f[0] == "cmdAck", 1.0)),
          [("cmdAck", 0)])
    # A ready clicked before Bob's last change could have reached Alice's
    # window: sent the moment the change is in, well inside the settle time.
    upd(a, barter.UPD_APPLY)
    check("Alice sees both, and her ready at that moment is turned back with"
          " a 6, her button off again", view(a.frames()),
          [("ss_upd", 3, rounds_b), ("ss_upd", 8, "96"), ("ss_upd", 6, "0")])
    check("and Bob is not told she is ready", view(b.frames()), [])
    time.sleep(SETTLE + 0.1)
    upd(a, barter.UPD_APPLY)
    check("ready after the table settled: bare, nothing back",
          view(a.frames()), [])
    check("Bob's light for her goes on", view(b.frames()), [("ss_upd", 5, "0")])

    upd(b, barter.UPD_APPLY)
    got_b, got_a = b.frames(), a.frames()
    new_a = (purse_a[0] - 300, purse_a[1] + 150)
    new_b = (purse_b[0] + 300, purse_b[1] - 150)
    check("Bob ready too: his Barter closed, his bag as it is, his purse",
          view(got_b), [("ss_upd", 0, "0"), ("ss_obj_status", 0, rounds_b),
                        ("ss_obj_status", 1, beretta), ("purse",) + new_b, ("say",)])
    check("Alice's window applies on the relayed 5, then the same",
          view(got_a), [("ss_upd", 5, "0"), ("ss_upd", 0, "0"),
                        ("ss_obj_status", 0, beretta), ("ss_obj_status", 1, rounds_b),
                        ("purse",) + new_a, ("say",)])
    check("the Beretta is Bob's and the rounds Alice's, in the database",
          (owner(beretta), owner(rounds_b)), (B_ID, A_ID))
    check("and the purses there are the ones the frames showed",
          (money_of(A_ID), money_of(B_ID)), (new_a, new_b))
    check("Alice's bag has the rounds and no Beretta",
          (rounds_b in bag(a), beretta in bag(a)), (True, False))
    check("Bob's the Beretta and no rounds of his own",
          (beretta in bag(b), rounds_b in bag(b)), (True, False))

    # Frames Bob's client sent before the close reached it.
    upd(b, barter.UPD_APPLY)
    check("a ready left over from the closed barter: nothing", view(b.frames()), [])
    upd(b, barter.UPD_TO_BUFFER, beretta)
    upd(b, barter.UPD_TO_BAG, beretta)
    check("two transfers whose handlers Barter.kill took off: nothing",
          view(b.frames()), [])
    upd(b, barter.UPD_TO_BUFFER, beretta)
    check("a third kept its handler: answered", view(b.frames()), [("cmdAck", 31)])
    upd(b, barter.UPD_ADD_GOLD, "0")
    check("and so is a money offer (kill skips no addMoneyAck)",
          view(b.frames()), [("cmdAck", 31)])
    # Handled, not taken in hand: the Beretta asks Стрельба 2 of whoever
    # holds it and Bob is a newborn (inventory.py, "the level"), while a
    # fire mode is switched on the gun wherever it lies, through the same
    # find() the table's lock hides it from.
    b.send("ss_use;target=x%x;obj=x%s;type=64;"
           % (items.first_mode(items.params_of(BERETTA)["fire_mods"]), beretta))
    check("off the table the Beretta is Bob's to handle",
          view(b.frames())[:1], [("cmdAck", 0)])
    a.send("ss_heap_c;obj=x%s;num=5;" % rounds_b)
    check("and the rounds Alice's to split", view(a.frames())[:1], [("cmdAck", 0)])

    # --- one side closes the window ------------------------------------------------------
    got_b, got_a = open_barter(b, a, pid_a, pid_b)
    check("Bob proposes, Alice agrees", (got_a[-1:], got_b[-1:]),
          ([("cmdAck", 0)], [("ss_upd", 1, "0")]))
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    upd(b, barter.UPD_TO_BUFFER, beretta_b)
    drain(a, b)
    upd(a, barter.UPD_CLOSE)
    check("Alice closes: bare, and her own window put her things back",
          view(a.frames()), [])
    got = b.frames()
    check("Bob's window closes on ss_upd 0 and gets his Beretta back in the bag",
          view(got), [("ss_upd", 0, "0"), ("ss_obj_status", 1, beretta_b), ("say",)])
    check("nothing changed hands", (owner(rounds_a), owner(beretta_b)), (A_ID, B_ID))
    a.send("ss_heap_c;obj=x%s;num=2;" % rounds_a)
    check("and nothing stays locked", view(a.frames())[:1], [("cmdAck", 0)])

    # --- the close overtakes a window's own bag request ---------------------------------
    time.sleep(LEFTOVERS + 0.1)
    propose(b, pid_a)
    drain(b)
    a.frames()
    upd(a, barter.UPD_AGREE)
    drain(a)
    check("Bob's window is opening", view(b.frames()), [("ss_upd", 1, "0")])
    upd(a, barter.UPD_CLOSE)          # Alice shuts hers before Bob's asks
    b.frames()
    b.send("ss_get;slot=8;")          # sent by createSession before the 0 landed
    check("that ss_get goes unanswered: Barter.kill took its ss_ack handler",
          view(b.frames()) + [n for n, _ in b.frames(0.2)], [])
    b.send("ss_get;slot=8;")
    check("the next one is answered as ever",
          [n for n, _ in b.frames()], ["ss_ack"])

    # --- walking away -------------------------------------------------------------------
    open_barter(b, a, pid_a, pid_b)
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    drain(a, b)
    b.send("moveTo;path=|%d|%d|;" % (pos, far))
    got_b, got_a = b.frames(), a.frames()
    check("Bob walks off: his step, then his window closed, and why",
          [v for v in view(got_b)], [("cmdAck", 0), ("ss_upd", 0, "0"), ("say",)])
    check("Alice's closes too, her rounds back in her bag",
          view(got_a), [("ss_upd", 0, "0"), ("ss_obj_status", 1, rounds_a), ("say",)])
    b.send("moveTo;path=|%d|%d|;" % (far, pos))
    drain(a, b, c)

    # --- out to the map while invited -----------------------------------------------------
    time.sleep(LEFTOVERS + 0.1)
    propose(a, pid_b)
    drain(a, b)
    a.send("chWorld;")
    got_a = a.until(lambda f: f[0] == "gmap")
    check("Alice leaves for the map: acked, her Barter closed on the way out",
          view(got_a)[:2], [("cmdAck", 0), ("ss_upd", 0, "0")])
    got_b = b.frames()
    check("Bob's invitation closes, with a word",
          [v for v in view(got_b)], [("ss_upd", 0, "0"), ("say",)])
    a.send("chWorld;")
    a.until(lambda f: f[0] == "lcall")
    enter(a)
    drain(a, b, c)

    # --- logging out mid-barter -------------------------------------------------------------
    open_barter(b, a, pid_a, pid_b)
    upd(b, barter.UPD_TO_BUFFER, beretta_b)
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    drain(a, b)
    a.send("logout;")
    time.sleep(0.3)
    a.s.close()
    got = b.until(lambda f: f[0] == "ss_upd")
    got += b.frames()
    check("Alice logs out: Bob's window closes, his Beretta back in his bag",
          [v for v in view(got)], [("ss_upd", 0, "0"), ("ss_obj_status", 1, beretta_b),
                                    ("say",)])
    check("and nothing changed hands", (owner(rounds_a), owner(beretta_b)), (A_ID, B_ID))
    a = Client(connect())
    login(a, ALICE, False, "Alice")
    enter(a)
    drain(a, b, c)

    # --- the same character logging in on another socket -------------------------------------
    open_barter(a, b, pid_b, pid_a)
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    drain(a, b)
    a2 = Client(connect())
    login(a2, ALICE, False, "Alice")
    got = b.frames()
    check("Alice again from elsewhere: the old socket goes, and Bob's window with it",
          [v for v in view(got)], [("ss_upd", 0, "0"), ("say",)])
    a.frames(0.2)
    a = a2
    enter(a)
    drain(a, b, c)
    check("her rounds are hers", owner(rounds_a), A_ID)

    # --- a purse that shrank before both said yes ---------------------------------------------
    have = money_of(A_ID)[0]
    open_barter(a, b, pid_b, pid_a)
    upd(a, barter.UPD_ADD_AFRO, "%x" % have)
    upd(b, barter.UPD_TO_BUFFER, beretta_b)
    drain(a, b)
    chat(a, "/money -%d 0" % have)       # a letter paid, a fine, the panel
    time.sleep(SETTLE + 0.1)
    upd(b, barter.UPD_APPLY)
    drain(b)
    a.frames()
    upd(a, barter.UPD_APPLY)
    got_a, got_b = a.frames(), b.frames()
    # Alice's yes came last, so her window has already moved the Beretta
    # into her bag (applyBarter): the server takes it out again.
    check("both said yes, but Alice cannot pay: her window closes, the Beretta"
          " her window took leaves her bag, and she is told why",
          (view(got_a), ["денег" in t for t in said(got_a)]),
          ([("ss_upd", 0, "0"), ("ss_obj_status", 0, beretta_b), ("say",)], [True]))
    check("Bob's too, the Beretta back in his bag", view(got_b),
          [("ss_upd", 0, "0"), ("ss_obj_status", 1, beretta_b), ("say",)])
    check("nothing moved", (owner(beretta_b), money_of(B_ID)[0]), (B_ID, new_b[0]))

    # --- a thing changed underneath by another process -----------------------------------------
    open_barter(a, b, pid_b, pid_a)
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    upd(b, barter.UPD_ADD_GOLD, "%x" % 10)
    drain(a, b)
    raw = sqlite3.connect(DB)
    raw.execute("UPDATE items SET count = count - 1 WHERE uniq = ?",
                (inventory.parse_oid(rounds_a)[0],))
    raw.commit()
    raw.close()
    time.sleep(SETTLE + 0.1)
    upd(a, barter.UPD_APPLY)
    drain(a)
    b.frames()
    upd(b, barter.UPD_APPLY)
    got_b, got_a = b.frames(), a.frames()
    check("the rounds are not as offered: Bob's window closes, and the rounds"
          " his applyBarter took leave his bag again",
          view(got_b), [("ss_upd", 0, "0"), ("ss_obj_status", 0, rounds_a), ("say",)])
    check("Alice's closes with the rounds back in hers",
          view(got_a), [("ss_upd", 0, "0"), ("ss_obj_status", 1, rounds_a), ("say",)])
    check("and nothing moved, gold included",
          (owner(rounds_a), money_of(B_ID)[1]), (A_ID, new_b[1]))

    # --- a ready on a light the server has already put out -----------------------------------
    # Barter.readyToBarter lights the clicker's own lamp before its 5 goes
    # out, and checkReady runs applyBarter the moment both lamps are on in
    # that window: the other side's things go into the bag and the window
    # closes. So a 5 from a window that had the other side's lamp on comes
    # from a client with no window left, whatever the server makes of it.
    gun_1 = given(chat(b, "/give %d" % BERETTA))
    gun_2 = given(chat(b, "/give %d" % BERETTA))
    gun_a = given(chat(a, "/give %d" % BERETTA))

    # Bob is ready, then puts a second Beretta up; Alice clicks before the
    # 3 reaches her window, on his lamp still lit there.
    open_barter(a, b, pid_b, pid_a)
    upd(b, barter.UPD_TO_BUFFER, gun_1)
    b.until(lambda f: f[0] == "cmdAck", 1.0)
    a.frames()
    time.sleep(SETTLE + 0.1)
    upd(b, barter.UPD_APPLY)
    check("Bob is ready: his lamp lights in Alice's window",
          view(a.frames()), [("ss_upd", 5, "0")])
    upd(b, barter.UPD_TO_BUFFER, gun_2)
    b_acked = b.until(lambda f: f[0] == "cmdAck", 1.0)
    upd(a, barter.UPD_APPLY)
    got_a, got_b = a.frames(), b_acked + b.frames()
    check("Alice's ready on his stale lamp ends the barter: her Barter closed"
          " (its window is gone), both Berettas her applyBarter may have taken"
          " out of her bag again, and why -- not a 6 to a window that is gone",
          (view(got_a), ["условия" in t for t in said(got_a)]),
          ([("ss_upd", 3, gun_2), ("ss_upd", 0, "0"), ("ss_obj_status", 0, gun_1),
            ("ss_obj_status", 0, gun_2), ("say",)], [True]))
    check("Bob's window closes too, both Berettas back in his bag",
          view(got_b), [("cmdAck", 0), ("ss_upd", 0, "0"), ("ss_obj_status", 1, gun_1),
                        ("ss_obj_status", 1, gun_2), ("say",)])
    check("nothing changed hands", (owner(gun_1), owner(gun_2)), (B_ID, B_ID))
    a.send("ss_create;target=%d;s_type=1;" % traders[0])
    check("and Alice's next stall opens at once, no barter in the way",
          view(a.frames()), [("cmdAck", 0)])
    upd(a, 0)
    a.frames()

    # An honest fast trade: Bob puts the second one up and is ready again at
    # once, and Alice, who saw both, clicks inside the settle time. Her
    # window closed on the new table; the server cannot tell that from a
    # click on the old one, so this ends too, and they go again.
    open_barter(a, b, pid_b, pid_a)
    upd(b, barter.UPD_TO_BUFFER, gun_1)
    b.until(lambda f: f[0] == "cmdAck", 1.0)
    a.frames()
    time.sleep(SETTLE + 0.1)
    upd(b, barter.UPD_TO_BUFFER, gun_2)
    b.until(lambda f: f[0] == "cmdAck", 1.0)
    upd(b, barter.UPD_APPLY)
    got = a.until(lambda f: f[0] == "ss_upd" and f[1]["s_status"] == 5, 1.0)
    check("Alice sees the second Beretta, then Bob's lamp",
          view(got), [("ss_upd", 3, gun_2), ("ss_upd", 5, "0")])
    upd(a, barter.UPD_APPLY)
    got_a, got_b = a.frames(), b.frames()
    check("her ready right after it ends the barter as well, the Berettas out"
          " of her bag", view(got_a),
          [("ss_upd", 0, "0"), ("ss_obj_status", 0, gun_1),
           ("ss_obj_status", 0, gun_2), ("say",)])
    check("and back in Bob's", view(got_b),
          [("ss_upd", 0, "0"), ("ss_obj_status", 1, gun_1),
           ("ss_obj_status", 1, gun_2), ("say",)])

    # Bob's 5 crosses a change of Alice's: her window put his lamp out as it
    # sent the change, and his 5 lit it again after. The server puts it out
    # once more, and a ready of hers in the meantime ends the barter.
    open_barter(a, b, pid_b, pid_a)
    upd(b, barter.UPD_TO_BUFFER, gun_1)
    b.until(lambda f: f[0] == "cmdAck", 1.0)
    a.frames()
    time.sleep(SETTLE + 0.1)
    upd(b, barter.UPD_APPLY)
    a.until(lambda f: f[0] == "ss_upd", 1.0)
    upd(a, barter.UPD_TO_BUFFER, gun_a)
    got = a.until(lambda f: f[0] == "ss_upd", 1.0)
    check("Alice's change right after Bob's 5 went to her: acked, then a 6 for"
          " the lamp his 5 may have lit again behind it", view(got),
          [("cmdAck", 0), ("ss_upd", 6, "0")])
    check("Bob sees her Beretta", view(b.frames()), [("ss_upd", 3, gun_a)])
    upd(a, barter.UPD_APPLY)
    got_a, got_b = a.frames(), b.frames()
    check("a ready of hers before that 6 can have landed ends it: her own"
          " Beretta back, Bob's out of her bag", view(got_a),
          [("ss_upd", 0, "0"), ("ss_obj_status", 1, gun_a),
           ("ss_obj_status", 0, gun_1), ("say",)])
    check("and Bob's window closes, his Beretta back", view(got_b),
          [("ss_upd", 0, "0"), ("ss_obj_status", 1, gun_1),
           ("ss_obj_status", 0, gun_a), ("say",)])

    # The same with nothing crossing: his 5 reached her window long before
    # her change left it, so there is nothing to put out, and her ready
    # right after her own change stands.
    open_barter(a, b, pid_b, pid_a)
    upd(b, barter.UPD_TO_BUFFER, gun_1)
    b.until(lambda f: f[0] == "cmdAck", 1.0)
    a.frames()
    time.sleep(SETTLE + 0.1)
    upd(b, barter.UPD_APPLY)
    a.until(lambda f: f[0] == "ss_upd", 1.0)
    time.sleep(SETTLE + 0.1)
    upd(a, barter.UPD_TO_BUFFER, gun_a)
    check("Alice's change long after his 5: only its ack",
          view(a.frames()), [("cmdAck", 0)])
    b.frames()
    upd(a, barter.UPD_APPLY)
    check("her ready stands: nothing back", view(a.frames()), [])
    check("and Bob's lamp for her goes on", view(b.frames()), [("ss_upd", 5, "0")])
    upd(b, barter.UPD_CLOSE)
    check("Bob closes: Alice's window closes, her Beretta back",
          view(a.frames()), [("ss_upd", 0, "0"), ("ss_obj_status", 1, gun_a), ("say",)])
    check("nothing changed hands", (owner(gun_1), owner(gun_a)), (B_ID, A_ID))

    # --- an invitation the invitee's client never showed ------------------------------------
    # Gamer.ss_create passes an invitation by while a Barter of the client's
    # own is alive (its "Предложить бартер?" query, answered no), and every
    # barter window is modal: a stall clicked by the invitee proves it has
    # none on screen, and could otherwise do nothing for a minute.
    time.sleep(LEFTOVERS + 0.1)
    propose(a, pid_b)
    drain(a)
    check("Alice invites Bob", view(b.frames()), [("ss_create", pid_a, 2)])
    b.send("ss_create;target=%d;s_type=1;" % traders[0])
    got = b.frames()
    check("Bob clicks a stall: refused this once, the invitation ended",
          (view(got), ["отменён" in t for t in said(got)]),
          ([("cmdAck", barter.RES_CANT), ("ss_upd", 0, "0"), ("say",)], [True]))
    got = a.frames()
    check("Alice's waiting alert closes, and she is told he is busy",
          (view(got), ["занят" in t for t in said(got)]),
          ([("ss_upd", 0, "0"), ("say",)], [True]))
    b.send("ss_create;target=%d;s_type=1;" % traders[0])
    check("his next click opens the stall", view(b.frames()), [("cmdAck", 0)])
    upd(b, 0)
    b.frames()

    # --- a transfer slower than LEFTOVERS, overtaken by a new invitation ------------------
    open_barter(a, b, pid_b, pid_a)
    upd(a, barter.UPD_CLOSE)          # Bob's window is closed by the server
    check("Alice closes; Bob's window is closed for him",
          view(b.frames()), [("ss_upd", 0, "0"), ("say",)])
    time.sleep(LEFTOVERS + 0.1)
    propose(c, pid_b)
    check("Carol invites Bob once LEFTOVERS is over", view(c.frames()), [("cmdAck", 0)])
    check("Bob is invited", view(b.frames()), [("ss_create", pid_c, 2)])
    upd(b, barter.UPD_TO_BUFFER, gun_1)     # sent before Alice's close reached him
    check("a transfer from the window that close shut: nothing -- Barter.kill"
          " took its handler, invitation or no", view(b.frames()), [])
    upd(b, barter.UPD_DENY)
    check("Bob says no to Carol", (view(b.frames()), view(c.frames())),
          ([("ss_upd", 0, "0")], [("ss_upd", 0, "0"), ("say",)]))

    # --- dying mid-barter ------------------------------------------------------------------------
    # A fist from Bob in the dump, where pvp="1"; Alice goes in with one hit
    # point, as after a fight that went badly.
    a.send("logout;")
    time.sleep(0.3)
    a.s.close()
    st = accounts.Store(DB)
    st.save_character_state(A_ID, hp=1, sp=0)
    st.close()
    a = Client(connect())
    login(a, ALICE, False, "Alice")
    enter(a)
    chat(b, "/goto %d" % DUMP)
    b.until(lambda f: f[0] == "lcall")
    _got, dump_pos = enter(b)
    chat(a, "/goto %d" % DUMP)
    a.until(lambda f: f[0] == "lcall")
    enter(a)
    drain(a, b)
    open_barter(b, a, pid_a, pid_b)
    upd(a, barter.UPD_TO_BUFFER, rounds_a)
    drain(a, b)
    dump = world.location(DUMP)
    # A fist reaches the next hex and not its own; the one furthest from the
    # dog, so that nothing else joins in.
    spot = max((n for n in progression.hex_neighbours(dump_pos, dump.width, dump.height)
                if n not in dump.obstacles),
               key=lambda n: mobs.hex_distance(n, 4551, dump.width))
    b.send("moveTo;path=|%d|%d|;" % (dump_pos, spot))
    check("Bob steps beside Alice: still side by side, the barter stands",
          [v for v in view(b.frames(0.5 + mobs.HEX_MS / 1000.0)) if v[0] == "ss_upd"], [])
    got_a, got_b = [], []
    for _ in range(15):
        b.send("ss_use;type=16;obj=x0;target=x1%08x;" % pid_a)
        got_b += b.until(lambda f: f[0] in ("caHit", "caMiss"), 3.0)
        got_a += a.frames(0.3)
        if any(n == "lch" and p.get("dead") == 0 for n, p in got_a):
            break
    got_a += a.frames(0.5)
    got_b += b.frames(0.5)
    check("Alice is struck dead", any(n == "lch" and p.get("dead") == 0
                                      for n, p in got_a), True)
    check("her window closes, her rounds back in her bag",
          [v for v in view(got_a) if v[0] in ("ss_upd", "ss_obj_status")][:2],
          [("ss_upd", 0, "0"), ("ss_obj_status", 1, rounds_a)])
    check("Bob's closes, and he is told why",
          ([v for v in view(got_b) if v[0] == "ss_upd"],
           [t for t in said(got_b) if "погиб" in t] != []),
          ([("ss_upd", 0, "0")], True))
    check("nothing changed hands", owner(rounds_a), A_ID)

    log_text = "".join(_log)
    check("no handler failed on the way", "Traceback" in log_text, False)
except Exception:
    import traceback
    traceback.print_exc()
    fails.append("the scenario broke off")
finally:
    srv.terminate()
    try:
        srv.wait(5)
    except subprocess.TimeoutExpired:
        srv.kill()
    _drain.join(2)

if fails:
    print("\nFAILED:")
    for f in fails:
        print(" - " + f)
    tail = "".join(_log[-80:])
    if "Traceback" in "".join(_log):
        print("\n--- server log (tail) ---\n" + tail)
    sys.exit(1)
print("\nbarter: all checks passed")
