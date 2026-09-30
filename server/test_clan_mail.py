"""The clan's mail: sndml types 2 («Внутриклановая рассылка», afro) and 3
(the express one, gold) -- mail.Mail.clan_letter.

In process, where the order of frames across sessions is exact: a clan of
three, one of them offline, and a letter to it -- the sender's cmdAck 0,
ctml and purse in that order; one letter per member but the sender, the
offline one's too, one copy in the sender's outbox; the tariff charged
once, flat, booked 'mail'; the online member told at once, the offline one
at his login. Then every refusal, each a 37 (the one code the window keeps
for these letters, silent) and never a charge: money or a parcel attached
(the reason said), a character in no clan and one kicked earlier on the
page (the bare 37 test_social.py also holds), a clan of one, too little
money.

Over sockets, three clients against a server of their own: the same
letter as the client sends it, its arrival, a letter waiting for a member
who logs in, and a kicked member's letter refused.

    LAVA_RES=.../lava/res python3 server/test_clan_mail.py

The in-process part runs on Postgres too, when LAVA_DB_URL names a
throwaway database (names unique per run, nothing dropped); the socket part
then is left out.
"""
import asyncio
import logging
import os
import random
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "clan_mail.db")
os.environ["LAVA_DB"] = DB
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import storage  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
PG = storage.using_postgres()
LOGINS = ("alice", "bob", "carol", "dave", "eve")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l + RUN, "secret")
_store.close()

import clans  # noqa: E402
import mail  # noqa: E402
import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)

STORE = server.STORE
CLANS = server.CLANS
fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def nick(base):
    return "%s%s" % (base, RUN)


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def take(sess):
    out = sess.writer.frames[:]
    sess.writer.frames.clear()
    return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def login(login_name, char_name, new=True):
    sess = server.Session(Writer(), login_name)
    run(sess, "login;hash=@%s@;" % accounts.credential(login_name + RUN, "secret"))
    if new:
        run(sess, "newPers;res=1;sex=0;name=@%s@;" % escape(char_name))
        run(sess, "actPlayer;")
    else:
        run(sess, "selPers;num=0;")
    run(sess, "lenter;accept=1;")
    return sess


def give(sess, afro=None, gold=None):
    ch = sess.character()
    if afro is not None:
        ch.afro = afro
    if gold is not None:
        ch.gold = gold
    ch.save(STORE)


def found(sess, name):
    give(sess, gold=sess.character().gold + clans.CREATE_GOLD)
    run(sess, "head;reg=@x@;soc=@%s@;" % name)
    run(sess, "gg_info;det=1;")
    take(sess)
    return CLANS.member(sess.char_id)["clan_id"]


def join(head, sess):
    run(head, "admit;char=@%s@;perm=2;post=@@;" % escape(sess.nick))
    run(sess, "apply;number=0;action=2;")
    run(sess, "gg_info;det=1;")
    take(head)
    take(sess)


def letter(sess, text):
    """One sndml: (its single cmdAck, every frame it brought)."""
    take(sess)
    run(sess, text)
    got = take(sess)
    a = acks(got)
    if len(a) != 1 or a[0] not in (0, mail.RES_NOT_IN_CLAN):
        fails.append("%r: acks %r" % (text, a))
    return (a[0] if a else None), got


def rows_from(char_id):
    return [dict(r) for r in STORE.db.execute(
        "SELECT * FROM mail WHERE from_char = ? ORDER BY id", (char_id,)).fetchall()]


def said(frames):
    return [p["entry"] for n, p in frames if n == "userMsg"]


async def main():
    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    carol = login("carol", nick("Carol"))
    dave = login("dave", nick("Dave"))
    wolves = found(alice, "Волки %s" % RUN)
    join(alice, bob)
    join(alice, carol)
    carol_id = carol.char_id
    carol.close()
    for s in (alice, bob, dave):
        run(s, "chkml;mode=0;")
        take(s)

    # --- a letter to the clan -------------------------------------------------------
    give(alice, afro=1000)
    led0 = len(STORE.ledger(alice.char_id))
    res, got = letter(alice, "sndml;body=@Сбор в 20:00@;type=2;subj=@Сбор@;to=@Кто-то@;")
    check("a clan letter: cmdAck 0, then ctml, then the purse -- in that order",
          [n for n, _ in got], ["cmdAck", "ctml", "userInfo_Player"])
    sent = rows_from(alice.char_id)
    check("  ..one letter each for the two other members, the offline one too, never the"
          " sender; `to` not read",
          sorted((r["to_char"], r["type"], r["subject"], r["body"]) for r in sent),
          sorted([(bob.char_id, 2, "Сбор", "Сбор в 20:00"),
                  (carol_id, 2, "Сбор", "Сбор в 20:00")]))
    check("  ..in the order the clan's members joined, nothing in them",
          [(r["to_char"], r["afro"], r["gold"], r["items_json"]) for r in sent],
          [(bob.char_id, 0, 0, "[]"), (carol_id, 0, 0, "[]")])
    ctml = named(got, "ctml")[0]
    check("  ..ctml names the first letter and takes nothing out of the bag",
          (str(ctml["id"]), ctml["item"], ctml["code"]), (str(sent[0]["id"]), [], []))
    check("  ..the sender's outbox holds one copy: the first",
          [r["id"] for r in STORE.mail_outbox(alice.char_id)], [sent[0]["id"]])
    check("  ..the tariff once, flat: 10 afro for two letters, in the frame, in memory, in"
          " the row", (named(got, "userInfo_Player")[0]["afro"], alice.character().afro,
                       STORE.money(alice.char_id)[0]), (990, 990, 990))
    check("  ..booked 'mail' once, ref the first letter",
          [(r["source"], r["ref"], r["afro"], r["gold"])
           for r in STORE.ledger(alice.char_id)[led0:]],
          [("mail", sent[0]["id"], -10, 0)])
    pushed = named(take(bob), "lsml")
    check("the member online is told at once: one lsml with the letter, from the sender,"
          " a clan letter, unread",
          [(p["id"], p["name"], p["flag"], p["subj"]) for p in pushed],
          [([str(sent[0]["id"])], [nick("Alice")],
            [mail.CLAN | mail.FLAG_UNREAD], ["Сбор"])])
    check("  ..the one outside the clan hears nothing", named(take(dave), "lsml"), [])
    run(bob, "getml;id=x%s;" % sent[0]["id"])
    got = take(bob)
    check("  ..and reads it: from the sender, to him",
          [(p["from"], p["to"], p["body"]) for p in named(got, "rcml")],
          [(nick("Alice"), nick("Bob"), "Сбор в 20:00")])
    carol = login("carol", nick("Carol"), new=False)
    run(carol, "chkml;mode=0;")
    got = named(take(carol), "lsml")
    check("the member who was offline finds it in his inbox at his login",
          [(p["name"], p["subj"]) for p in got], [([nick("Alice")], ["Сбор"])])

    # The express one, in gold.
    give(alice, gold=100)
    res, got = letter(alice, "sndml;body=@срочно@;type=3;subj=@Тревога@;to=@@;")
    check("an express clan letter: 0, and 0.20 G once for two letters",
          (res, alice.character().gold, STORE.money(alice.char_id)[1],
           [(r["source"], r["gold"]) for r in STORE.ledger(alice.char_id)][-1:]),
          (0, 80, 80, [("mail", -20)]))
    check("  ..two more letters, type 3", [r["type"] for r in rows_from(alice.char_id)][2:],
          [3, 3])

    # Deleting: the rows not in the outbox go as soon as their addressee
    # throws them away.
    third = rows_from(alice.char_id)[1]
    run(carol, "rmvml;id=x%s;" % third["id"])
    take(carol)
    check("the member deletes his copy -- not the sender's outbox one: the row is gone",
          STORE.mail_letter(third["id"]), None)

    # --- refusals: 37, never a charge -------------------------------------------------
    before = (STORE.money(alice.char_id), len(rows_from(alice.char_id)))
    for extra, why in (("afro=5;", "afro"), ("gold=100;", "gold"),
                       ("item=x%s;" % "1234abc", "a parcel")):
        res, got = letter(alice, "sndml;%sbody=@x@;type=2;subj=@x@;to=@@;" % extra)
        check("a clan letter with %s in it: 37, no ctml, the reason said" % why,
              (res, [n for n, _ in got if n != "userMsg"], len(said(got))),
              (37, ["cmdAck"], 1))
    check("  ..nothing charged, nothing filed",
          (STORE.money(alice.char_id), len(rows_from(alice.char_id))), before)
    give(alice, afro=5)
    res, got = letter(alice, "sndml;body=@x@;type=2;subj=@x@;to=@@;")
    check("too little for the tariff: 37, and the price said",
          (res, said(got)), (37, ["Не хватает денег на рассылку: она стоит 10 афро"]))
    give(alice, afro=1000, gold=0)
    res, got = letter(alice, "sndml;body=@x@;type=3;subj=@x@;to=@@;")
    check("  ..the express one without gold: the same, in gold",
          (res, said(got)), (37, ["Не хватает денег на рассылку: она стоит 0,20 G"]))
    res, got = letter(dave, "sndml;body=@@;type=2;subj=@x@;to=@%s@;" % nick("Bob"))
    check("a character in no clan: the bare 37, nothing else", got, [("cmdAck", {"res": 37})])
    run(alice, "apply;number=%d;action=1;" % carol.char_id)
    take(alice)
    take(carol)
    res, got = letter(carol, "sndml;body=@@;type=2;subj=@x@;to=@@;")
    check("a member kicked earlier (his client's radios still live): the bare 37",
          got, [("cmdAck", {"res": 37})])
    eve = login("eve", nick("Eve"))
    found(eve, "Одиночки %s" % RUN)
    run(eve, "chkml;mode=0;")
    give(eve, afro=1000)
    res, got = letter(eve, "sndml;body=@@;type=2;subj=@x@;to=@@;")
    check("a clan of one: 37, and why", (res, said(got)),
          (37, ["В клане «Одиночки %s», кроме вас, никого нет: рассылать некому" % RUN]))
    check("  ..and nothing charged", STORE.money(eve.char_id)[0], 1000)
    check("the letters of one clan never reach another's members",
          [r for r in STORE.mail_inbox(eve.char_id)], [])
    check("no clan command was answered twice", CLANS.double_acks, [])
    for s in list(server.SESSIONS) + [alice, bob, carol, dave, eve]:
        s.close()


logging.getLogger("lava").disabled = True
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("in-process part crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()


# --- over sockets -------------------------------------------------------------------
WDB = os.path.join(tempfile.mkdtemp(), "clan_mail_wire.db")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode("utf-8") + b"\x00")

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
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode("utf-8")) for f in parts if f]

    def close(self):
        self.s.close()


def wire():
    wire_run = "%04d" % random.randrange(10000)
    names = {l: l.capitalize() + wire_run for l in ("alice", "bob", "carol")}
    st = accounts.Store(WDB)
    for l in names:
        st.register(l + wire_run, "secret")
    st.close()
    cred = {l: accounts.credential(l + wire_run, "secret") for l in names}
    port = free_port()
    env = dict(os.environ, LAVA_PORT=str(port), LAVA_HOST="127.0.0.1", LAVA_DB=WDB,
               LAVA_GX="6268", LAVA_GY="1819", LAVA_CHEATS="1", LAVA_POLICY_PORT="0",
               LAVA_CLAN_DEAF_CHECK="0")
    env.pop("LAVA_DB_URL", None)
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []
    threading.Thread(target=lambda: log.extend(proc.stdout), daemon=True).start()

    def connect():
        end = time.time() + 15
        while time.time() < end:
            if proc.poll() is not None:
                raise SystemExit("server exited:\n" + "".join(log)[-2000:])
            try:
                return Client(socket.create_connection(("127.0.0.1", port), 0.5))
            except OSError:
                time.sleep(0.1)
        raise SystemExit("server did not start")

    def enter(c, login_name, new=True):
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % cred[login_name])
        c.frames()
        if new:
            c.send("newPers;res=1;sex=0;name=@%s@;" % escape(names[login_name]))
            c.frames()
            c.send("actPlayer;")
        else:
            c.send("selPers;num=0;")
        c.frames()
        c.send("lenter;accept=1;")
        c.frames(1.0)

    try:
        a, b, c = connect(), connect(), connect()
        for cl, l in ((a, "alice"), (b, "bob"), (c, "carol")):
            enter(cl, l)
        a.send("userMsg;entry=@/money 1000 1000@;group=0;")
        a.frames()
        a.send("head;reg=@x@;soc=@Совы %s@;" % wire_run)
        a.frames()
        for cl, l in ((b, "bob"), (c, "carol")):
            a.send("admit;char=@%s@;perm=2;post=@@;" % names[l])
            a.frames()
            cl.frames()
            cl.send("apply;number=0;action=2;")
            cl.frames()
        c.send("logout;")
        c.close()
        b.send("chkml;mode=0;")
        b.frames()
        a.frames()
        a.send("sndml;body=@на сбор@;type=2;subj=@Сбор@;to=@@;")
        got = [(n, p) for n, p in a.frames() if n in ("cmdAck", "ctml", "userInfo_Player")]
        check("wire: the sender gets cmdAck 0, ctml, then the purse",
              [(n, p.get("res") if n == "cmdAck" else None) for n, p in got],
              [("cmdAck", 0), ("ctml", None), ("userInfo_Player", None)])
        arrived = [p for n, p in b.frames() if n == "lsml"]
        check("wire: the member online sees the envelope at once",
              [(p["name"], p["subj"], p["flag"]) for p in arrived],
              [([names["alice"]], ["Сбор"], [mail.CLAN | mail.FLAG_UNREAD])])
        c = connect()
        enter(c, "carol", new=False)
        c.send("chkml;mode=0;")
        listed = [p for n, p in c.frames() if n == "lsml"]
        check("wire: the member who was away finds it at his login",
              [(p["name"], p["subj"]) for p in listed], [([names["alice"]], ["Сбор"])])
        b.send("sndml;afro=50;body=@@;type=2;subj=@x@;to=@@;")
        got = b.frames()
        check("wire: money in a clan letter: 37 and the reason in chat, no ctml",
              ([(n, p.get("res")) for n, p in got if n in ("cmdAck", "ctml")],
               len([p for n, p in got if n == "userMsg"])), ([("cmdAck", 37)], 1))
        a.send("gg_info;det=1;")
        a.frames()
        st = accounts.Store(WDB)
        carol_id = st.character_by_name(names["carol"])["id"]
        st.close()
        a.send("apply;number=%d;action=1;" % carol_id)
        a.frames()
        c.frames()
        c.send("sndml;body=@@;type=2;subj=@x@;to=@@;")
        check("wire: a kicked member's clan letter: 37, alone",
              c.frames(), [("cmdAck", {"res": 37})])
        for cl in (a, b, c):
            cl.close()
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if PG:
    print("  --  the socket part runs on SQLite only; skipped under LAVA_DB_URL")
else:
    try:
        wire()
    except (Exception, SystemExit):
        import traceback
        fails.append("socket part crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("clan mail OK")
