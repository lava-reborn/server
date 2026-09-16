"""Two players write to each other and form a party.

Mail is recon/analysis/world.md section 7 as lol/core/mail/MailInspector.as
drives it: every command acknowledged first, ctml only after res=0, the
parcel described at the front of the body, letters returned rather than
lost. The party is section 8 as lol/core/party/PartyManager.as reads it:
every id in the receiver's coordinates, op 5 answered by p_m alone, a
dropped socket reported as "disconnected" and the same character back as
"returned".
"""
import os
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts
import inventory
import items
import mail
import party
from protocol import decode


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()

DB = os.path.join(tempfile.mkdtemp(), "test.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("alice", "secret")
_store.register("bob", "secret")
_store.register("carol", "secret")
_store.close()
CRED_A = accounts.credential("alice", "secret")
CRED_B = accounts.credential("bob", "secret")
CRED_C = accounts.credential("carol", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if srv.poll() is not None:
            raise SystemExit("server exited before listening:\n"
                             + srv.communicate()[0][-1500:])
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
        """Whatever arrives within the window, as (name, params)."""
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
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def names(self, wait=0.5):
        return [n for n, _ in self.frames(wait)]


def named(frames, name):
    return [p for n, p in frames if n == name]


def oids(params):
    return [str(x) for x in params["o_list"]]


def enter(c, cred, nick, first=True):
    """Log in, create or pick the character, stand in the starting
    location. Returns the entry frames and the other players seen."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
        check("%s is created" % nick, c.names(), ["cmdAck"])
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    pre = c.frames()
    check("%s is called into a location" % nick, [n for n, _ in pre][-1], "lcall")
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    check("%s is positioned" % nick, got[0][0], "lenter")
    others = [p["newUser"] for n, p in got if n == "lch" and p.get("rtype") == -1]
    return pre, got, others


def bag(c):
    c.send("ss_get;target=0;slot=8;")
    return oids(c.frames()[0][1])


def purse(c):
    c.send("getInfo;lvl=0;id=0;type=0;")
    return named(c.frames(), "userInfo_Player")[0]["afro"]


PISTOL = 4380
ROUNDS = items.AMMO_9MM[0]
PISTOL_SI = items.params_of(PISTOL)
ROUNDS_SI = items.params_of(ROUNDS)
LETTER_FEE = mail.tariff(mail.LETTER, PISTOL_SI["weight"])[0]
PLAIN_FEE = mail.tariff(mail.LETTER, 0)[0]

try:
    a = Client(connect())
    b = Client(connect())
    _, _, _ = enter(a, CRED_A, "Alice")
    _, _, seen = enter(b, CRED_B, "Bob")
    pid_a = seen[0]
    got = a.frames()
    pid_b = [p["newUser"] for n, p in got if n == "lch"][0]

    # --- tariffs and empty boxes ---------------------------------------------
    a.send("chkml;mode=255;")
    got = a.frames()
    check("tariffs: ack then svml", [n for n, _ in got], ["cmdAck", "svml"])
    check("eight prices, eight times, as MailParam reads them",
          (got[1][1]["data"], got[1][1]["time"]), (mail.PRICES, mail.TIMES))
    b.send("chkml;mode=0;")
    got = b.frames()
    check("empty inbox: ack then an lsml of five empty lists", got,
          [("cmdAck", {"res": 0}),
           ("lsml", {"id": [], "date": [], "name": [], "flag": [], "subj": []})])
    a.send("chkml;mode=0;")
    a.frames()

    # --- a parcel: money and the pistol -------------------------------------
    pistol_a, rounds_a = bag(a)
    afro_a = purse(a)
    afro_b = purse(b)
    check("both start with the newborn's purse", (afro_a, afro_b), (1000, 1000))
    a.send("sndml;afro=100;item=x%s;body=@держи@;type=0;subj=@Пистолет@;to=@Bob@;"
           % pistol_a)
    got = a.frames()
    check("sent: ack, the control packet, then the purse",
          [n for n, _ in got], ["cmdAck", "ctml", "userInfo_Player"])
    check("accepted", got[0][1]["res"], 0)
    letter = str(got[1][1]["id"])
    check("the control packet names the letter", letter != "0", True)
    check("and takes the pistol out of the bag (code -1)",
          (got[1][1]["item"], got[1][1]["code"]), ([pistol_a], [-1]))
    afro_a -= 100 + LETTER_FEE
    check("charged the attached money plus base plus per-kilogram",
          got[2][1]["afro"], afro_a)
    check("the pistol has left the sender's bag", bag(a), [rounds_a])

    # The addressee has listed his inbox, so the new letter is pushed as one
    # more lsml, and the client shows the envelope from it.
    got = b.frames()
    check("addressee online: the letter is pushed", [n for n, _ in got], ["lsml"])
    push = got[0][1]
    check("under its id, from Alice, unread with a parcel",
          (push["id"], push["name"], push["flag"], push["subj"]),
          ([letter], ["Alice"], [mail.FLAG_UNREAD | mail.FLAG_ATTACHED], ["Пистолет"]))
    check("dated in UTC as YYYY-MM-DD HH:MM:SS",
          len(push["date"][0]) == 19 and push["date"][0][10] == " ", True)

    b.send("chkml;mode=0;")
    got = b.frames()
    check("the inbox lists it", named(got, "lsml")[0]["id"], [letter])

    b.send("getml;id=x%s;" % letter)
    got = b.frames()
    check("open: ack then rcml", [n for n, _ in got], ["cmdAck", "rcml"])
    rc = got[1][1]
    check("the letter, read now, with its parcel",
          (str(rc["id"]), rc["flag"], rc["from"], rc["to"], rc["afro"], rc["gold"]),
          (letter, mail.FLAG_ATTACHED, "Alice", "Bob", 100, 0))
    check("the parcel is the pistol under the sender's id", rc["items"], [pistol_a])
    mb = PISTOL_SI["max_break_abs"]
    block = "=?BS:%d/%d?=" % (mb, mb)
    check("durability block, then what LetterObject cuts off, then the text",
          rc["body"], block + " " * len(block) + "держи")
    b.send("chkml;mode=0;")
    check("listed as read now", named(b.frames(), "lsml")[0]["flag"],
          [mail.FLAG_ATTACHED])
    a.send("chkml;mode=1;")
    got = named(a.frames(), "lsml")[0]
    check("the sender's outbox shows it, addressed to Bob, parcel still inside",
          (got["id"], got["name"], got["flag"]),
          ([letter], ["Bob"], [mail.FLAG_OUTBOX | mail.FLAG_ATTACHED]))

    b.send("getml;id=x999;")
    check("no such letter: 35", b.frames(), [("cmdAck", {"res": 35})])

    b.send("uldml;id=x%s;" % letter)
    got = b.frames()
    check("take the parcel: ack, control packet, purse",
          [n for n, _ in got], ["cmdAck", "ctml", "userInfo_Player"])
    ct = got[1][1]
    check("five item slots, afro, gold; one item and the afro received",
          (len(ct["item"]), ct["code"]), (7, [1, 0, 0, 0, 0, 1, 0]))
    new_pistol = ct["item"][0]
    parsed = inventory.parse_oid(new_pistol)
    check("a new instance of the pistol", (parsed[1], parsed[2]), (PISTOL, items.FIRE_ARM))
    check("not the sender's serial", new_pistol != pistol_a, True)
    check("the afro spelled in hex for Number('0x'+..)", ct["item"][5], "%x" % 100)
    afro_b += 100
    check("the purse is the record with the money in", got[2][1]["afro"], afro_b)
    bag_b = bag(b)
    check("the pistol is in the addressee's bag", new_pistol in bag_b and len(bag_b) == 3, True)
    b.send("ss_get_di;obj=x%s;" % new_pistol)
    got = b.frames()
    check("with the durability it was sent with",
          (got[0][0], got[0][1]["break"], got[0][1]["max_break_cur"]),
          ("ss_di_firearm", mb, mb))
    b.send("uldml;id=x%s;" % letter)
    check("nothing left to take: 36", b.frames(), [("cmdAck", {"res": 36})])
    a.send("chkml;mode=1;")
    check("the outbox shows the parcel gone", named(a.frames(), "lsml")[0]["flag"],
          [mail.FLAG_OUTBOX])

    b.send("rmvml;id=x%s;" % letter)
    check("delete acknowledged", b.frames(), [("cmdAck", {"res": 0})])
    b.send("chkml;mode=0;")
    check("gone from the inbox", named(b.frames(), "lsml")[0]["id"], [])
    a.send("chkml;mode=1;")
    check("but still in the sender's outbox", named(a.frames(), "lsml")[0]["id"], [letter])
    a.send("rmvml;id=x%s;" % letter)
    a.frames()
    a.send("chkml;mode=1;")
    check("until the sender deletes it too", named(a.frames(), "lsml")[0]["id"], [])

    # --- refusals, each with the code the window words -------------------------
    a.send("sndml;body=@@;type=0;subj=@x@;to=@Nobody@;")
    check("unknown addressee: 34", a.frames(), [("cmdAck", {"res": 34})])
    a.send("sndml;body=@@;type=0;subj=@x@;to=@Alice@;")
    check("to oneself: 34", a.frames(), [("cmdAck", {"res": 34})])
    a.send("sndml;body=@@;type=2;subj=@x@;to=@Bob@;")
    check("clan letter without a clan: 37", a.frames(), [("cmdAck", {"res": 37})])
    a.send("sndml;body=@@;type=6;subj=@x@;to=@Bob@;")
    check("an order: refused, no ctml", a.frames(), [("cmdAck", {"res": 3})])
    a.send("sndml;afro=100000;body=@@;type=0;subj=@x@;to=@Bob@;")
    got = a.frames()
    check("more money than owned: refused, told in chat, no ctml",
          [n for n, _ in got], ["cmdAck", "userMsg"])
    check("with a non-zero code", got[0][1]["res"] != 0, True)
    a.send("sndml;item=xdead111c00;body=@@;type=0;subj=@x@;to=@Bob@;")
    check("an item not in the bag: refused, no ctml", a.frames(), [("cmdAck", {"res": 3})])
    a.send("uldml;id=x999;")
    check("unpacking an unknown letter: 35", a.frames(), [("cmdAck", {"res": 35})])
    check("nothing of that reached the addressee", b.frames(0.3), [])
    check("and nothing was charged", purse(a), afro_a)

    # --- a parcel thrown away comes back ------------------------------------------
    a.send("sndml;item=x%s;body=@патроны@;type=0;subj=@Патроны@;to=@Bob@;" % rounds_a)
    got = a.frames()
    check("rounds sent", got[1][1]["code"], [-1])
    letter2 = str(got[1][1]["id"])
    afro_a -= PLAIN_FEE
    check("a light parcel costs the base fee alone", got[2][1]["afro"], afro_a)
    check("the sender's bag is empty", bag(a), [])
    got = b.frames()
    check("pushed to the addressee", named(got, "lsml")[0]["id"], [letter2])
    b.send("rmvml;id=x%s;" % letter2)
    check("addressee deletes it unopened", b.frames(), [("cmdAck", {"res": 0})])
    got = a.frames()
    check("the parcel returns to the sender as a new inbox letter",
          [n for n, _ in got], ["lsml"])
    check("flagged returned, unread, with the parcel, from herself",
          (got[0][1]["id"], got[0][1]["flag"], got[0][1]["name"]),
          ([letter2], [mail.FLAG_RETURNED | mail.FLAG_ATTACHED | mail.FLAG_UNREAD], ["Alice"]))
    a.send("getml;id=x%s;" % letter2)
    rc = named(a.frames(), "rcml")[0]
    check("a stack is described by its size", rc["body"].startswith("=?HS:%d?=" % items.AMMO_PACK), True)
    a.send("uldml;id=x%s;" % letter2)
    got = a.frames()
    check("taken back: one item, no money", got[1][1]["code"], [1, 0, 0, 0, 0, 0, 0])
    check("no purse frame when no money moved", [n for n, _ in got], ["cmdAck", "ctml"])
    rounds_back = got[1][1]["item"][0]
    check("the rounds are in the bag again", bag(a), [rounds_back])
    a.send("ss_get_di;obj=x%s;" % rounds_back)
    check("the whole pack", a.frames()[0][1]["size"], items.AMMO_PACK)
    a.send("rmvml;id=x%s;" % letter2)
    a.frames()

    # --- an addressee who is offline ----------------------------------------------
    b.send("logout;")
    b.s.close()
    a.frames()
    a.send("sndml;afro=50;body=@на карман@;type=0;subj=@Деньги@;to=@Bob@;")
    got = a.frames()
    check("letter to someone offline is filed all the same",
          [n for n, _ in got], ["cmdAck", "ctml", "userInfo_Player"])
    check("no items: empty control lists", (got[1][1]["item"], got[1][1]["code"]), ([], []))
    letter3 = str(got[1][1]["id"])
    afro_a -= 50 + PLAIN_FEE
    check("charged", got[2][1]["afro"], afro_a)

    b = Client(connect())
    enter(b, CRED_B, "Bob", first=False)
    a.frames()
    b.send("chkml;mode=0;")
    got = named(b.frames(), "lsml")[0]
    check("found on the next login", (got["id"], got["flag"], got["name"]),
          ([letter3], [mail.FLAG_UNREAD | mail.FLAG_ATTACHED], ["Alice"]))
    b.send("uldml;id=x%s;" % letter3)
    got = b.frames()
    afro_b += 50
    check("money taken: the afro code and the purse",
          (got[1][1]["code"][5], got[2][1]["afro"]), (1, afro_b))
    check("the purse survived the relogin too", purse(b), afro_b)
    b.send("rmvml;id=x%s;" % letter3)
    b.frames()

    # --- party: invite, accept, roster -----------------------------------------------
    a.send("p_op;id=7;op=0;")
    check("inviting an inhabitant: 31", a.frames(), [("cmdAck", {"res": 31})])
    a.send("p_op;id=%d;op=0;" % pid_b)
    check("invite acknowledged", a.frames(), [("cmdAck", {"res": 0})])
    check("the guest is asked, by the inviter's id", b.frames(),
          [("p_op", {"op": party.RECV_INVITE, "mob_id": pid_a})])
    a.send("p_op;id=%d;op=0;" % pid_b)
    check("asked twice: 31", a.frames(), [("cmdAck", {"res": 31})])
    b.frames(0.2)
    b.send("p_op;id=0;op=2;")
    got = b.frames()
    check("accepted: ack, then the roster with the leader first",
          got, [("cmdAck", {"res": 0}), ("p_m", {"list": [pid_a, 0]})])
    got = a.frames()
    check("the inviter hears the join and gets the roster, itself as 0",
          got, [("p_op", {"op": party.RECV_JOIN, "mob_id": pid_b}),
                ("p_m", {"list": [0, pid_b]})])
    # After res=0 the client asks for the list itself, with no handler.
    b.send("p_op;id=0;op=5;")
    check("the list request is answered by p_m alone", b.frames(),
          [("p_m", {"list": [pid_a, 0]})])

    # --- channel 1 reaches the party and nobody else ------------------------------
    c = Client(connect())
    enter(c, CRED_C, "Carol")
    pid_c = [p["newUser"] for n, p in a.frames() if n == "lch"][0]
    b.frames()
    a.send("userMsg;entry=@свои@;group=1;")
    check("party talk acknowledged", a.frames(), [("cmdAck", {"res": 0})])
    check("heard by the other member", b.frames(),
          [("userMsg", {"group": 1, "nick": "Alice", "entry": "свои", "from": pid_a})])
    check("not by the bystander", c.frames(0.3), [])
    c.send("userMsg;entry=@эй@;group=1;")
    check("the bystander's party talk is acknowledged", c.frames(), [("cmdAck", {"res": 0})])
    check("and goes nowhere", (a.frames(0.3), b.frames(0.3)), ([], []))
    c.send("p_op;id=0;op=5;")
    check("no party, no roster, and no ack", c.frames(0.3), [])
    b.send("p_op;id=%d;op=0;" % pid_c)
    check("a member who is not the leader cannot invite: 31", b.frames(),
          [("cmdAck", {"res": 31})])
    a.send("p_op;id=%d;op=0;" % pid_c)
    a.frames()
    check("the bystander is asked", c.names(), ["p_op"])
    c.send("p_op;id=0;op=3;")
    check("declined: acknowledged", c.frames(), [("cmdAck", {"res": 0})])
    check("the inviter is told who refused", a.frames(),
          [("p_op", {"op": party.RECV_REFUSE, "mob_id": pid_c})])

    # --- leadership and kicking ------------------------------------------------------
    b.send("p_op;id=%d;op=4;" % pid_a)
    check("only the leader hands over the lead", b.frames(), [("cmdAck", {"res": 3})])
    a.send("p_op;id=%d;op=4;" % pid_b)
    check("lead handed over: ack, the change, the roster reordered",
          a.frames(), [("cmdAck", {"res": 0}),
                       ("p_op", {"op": party.RECV_LEADER, "mob_id": pid_b}),
                       ("p_m", {"list": [pid_b, 0]})])
    check("the new leader hears it as itself", b.frames(),
          [("p_op", {"op": party.RECV_LEADER, "mob_id": 0}),
           ("p_m", {"list": [0, pid_a]})])
    a.send("p_op;id=%d;op=1;" % pid_b)
    check("a member cannot kick", a.frames(), [("cmdAck", {"res": 3})])
    b.send("p_op;id=%d;op=1;" % pid_a)
    check("the leader kicks the last other member: ack, kicked, disbanded",
          b.frames(), [("cmdAck", {"res": 0}),
                       ("p_op", {"op": party.RECV_KICKED, "mob_id": pid_a}),
                       ("p_op", {"op": party.RECV_DISBAND, "mob_id": 0})])
    check("the kicked one is told with mob_id 0, its own id", a.frames(),
          [("p_op", {"op": party.RECV_KICKED, "mob_id": 0})])
    a.send("p_op;id=0;op=1;")
    check("leaving with no party: refused", a.frames(), [("cmdAck", {"res": 3})])

    # --- leaving by choice -----------------------------------------------------------
    a.send("p_op;id=%d;op=0;" % pid_b)
    a.frames()
    b.frames()
    b.send("p_op;id=0;op=2;")
    b.frames()
    a.frames()
    b.send("p_op;id=0;op=1;")
    check("leaving: the leaver only gets the ack", b.frames(), [("cmdAck", {"res": 0})])
    check("the one left hears the leave and then the disbandment", a.frames(),
          [("p_op", {"op": party.RECV_LEAVE, "mob_id": pid_b}),
           ("p_op", {"op": party.RECV_DISBAND, "mob_id": 0})])

    # --- a dropped link, and the way back ---------------------------------------------
    a.send("p_op;id=%d;op=0;" % pid_b)
    a.frames()
    b.frames()
    b.send("p_op;id=0;op=2;")
    b.frames()
    a.frames()
    b.s.close()
    got = a.frames()
    check("the member's socket drops: the room loses him, the party keeps him",
          got, [("lch", {"lostUser": pid_b}),
                ("p_op", {"op": party.RECV_OFFLINE, "mob_id": pid_b})])
    b = Client(connect())
    pre, _, _ = enter(b, CRED_B, "Bob", first=False)
    check("back on a new socket: the roster comes before the location call",
          [n for n, _ in pre], ["p_m", "lcall"])
    check("with the leader first and himself as 0", pre[0][1]["list"], [pid_a, 0])
    got = a.frames()
    check("the leader hears him return, then sees him arrive",
          [(n, p.get("op"), p.get("mob_id", p.get("newUser"))) for n, p in got],
          [("p_op", party.RECV_ONLINE, pid_b), ("lch", None, pid_b)])
    b.send("userMsg;entry=@вернулся@;group=1;")
    b.frames()
    check("and the channel still works", a.frames(),
          [("userMsg", {"group": 1, "nick": "Bob", "entry": "вернулся", "from": pid_b})])
    a.send("logout;")
    a.s.close()
    got = b.frames()
    check("the leader logging out is a disconnect to the party too",
          [f for f in got if f[0] == "p_op"],
          [("p_op", {"op": party.RECV_OFFLINE, "mob_id": pid_a})])
    b.send("logout;")
    c.send("logout;")
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    out = srv.communicate(timeout=5)[0]
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-8000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("social OK")
