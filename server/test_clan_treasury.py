"""The clan's treasury (clan_treasury.py) and the report of money that
counts it (tools/money_report.py), driven in process where the order of
frames across the sessions is exact.

A clan of three -- the head, an officer with the right to take afro out
(0x400) and a member without it -- a member of another clan, and a
character in none: the balance to whom it is for, a deposit by the member
without the right, a withdrawal by the officer and the refusal of the same
without the right, the purse pushed before the answer, the balance sent to
the other holders of 0x400 and to nobody else, a withdrawal past the
balance, every number a modified client could write (fractions, zero,
huge, infinite, strings, lists, the key twice) and the whole numbers a
float may stand for, the gold refused, two withdrawals of the whole
treasury racing -- in the game, and across two connections where one waits
on the other's lock -- the three writes of a move in one transaction, a
kicked member's stale page, a dead member's balance, both journals adding
up, and the report: transfers kept out of the taps and drains, the
treasuries' own section, their stock.

    LAVA_RES=.../lava/res python3 server/test_clan_treasury.py

Runs on Postgres too, when LAVA_DB_URL names a throwaway database: every
name is made unique per run, nothing is dropped, and the journals are read
for this run's characters and clans only.
"""
import asyncio
import contextlib
import io
import logging
import os
import random
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "clan_treasury.db")
os.environ["LAVA_DB"] = DB
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import accounts  # noqa: E402
import storage  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
PG = storage.using_postgres()


def nick(base):
    return "%s%s" % (base, RUN)


LOGINS = ("alice", "bob", "carol", "dave", "eve")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l + RUN, "secret")
_store.close()

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)
import clan_treasury  # noqa: E402
import clans  # noqa: E402
import money_report  # noqa: E402

STORE = server.STORE
CLANS = server.CLANS
fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

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


CLAN_FRAMES = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code",
               "userInfo_Player")


def shape(frames):
    """(name, what tells it) of each clan frame: an answer's or a list's
    res, the purse of a userInfo_Player."""
    out = []
    for n, p in frames:
        if n not in CLAN_FRAMES:
            continue
        if n == "userInfo_Player":
            out.append((n, p.get("afro")))
        elif n == "gg_list" and p.get("res") == 3:
            out.append((n, 3, p.get("data")))
        else:
            out.append((n, p.get("res", p.get("reg"))))
    return out


def login(login_name, char_name):
    sess = server.Session(Writer(), login_name)
    run(sess, "login;hash=@%s@;" % accounts.credential(login_name + RUN, "secret"))
    run(sess, "newPers;res=1;sex=0;name=@%s@;" % escape(char_name))
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    return sess


def give(sess, afro, gold=0):
    ch = sess.character()
    ch.afro, ch.gold = afro, gold
    ch.save(STORE)


def one_ack(sess, text, label):
    """One clan command: exactly one cmdAck, never a code the client pops an
    alert for. Returns (res, frames)."""
    take(sess)
    run(sess, text)
    got = take(sess)
    a = [p["res"] for n, p in got if n == "cmdAck"]
    if len(a) != 1 or a[0] in clans.NEVER:
        fails.append("%s: acks %r for %r" % (label, a, text))
    return (a[0] if a else None), got


def purse(sess):
    """(in memory, in the row) of the afro: they must agree."""
    return sess.character().afro, STORE.money(sess.char_id)[0]


def counts(clan_id, *sessions):
    """How many rows the two journals hold for these characters and this
    clan: a refusal must not add one."""
    ids = [s.char_id for s in sessions]
    money = sum(len(STORE.ledger(c)) for c in ids)
    return money, len(STORE.clan_ledger_rows(clan_id, 100000))


async def main():
    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    carol = login("carol", nick("Carol"))
    dave = login("dave", nick("Dave"))
    eve = login("eve", nick("Eve"))
    everyone = (alice, bob, carol, dave, eve)

    # --- two clans: ours, with an officer holding 0x400, and Eve's --------------------
    give(alice, 2000000, 1000)
    run(alice, "head;reg=@x@;soc=@Казна %s@;" % RUN)
    ours = CLANS.member(alice.char_id)["clan_id"]
    for who, perm in ((bob, clans.R_AFRO | clans.R_CHAT), (carol, clans.R_CHAT)):
        run(alice, "admit;char=@%s@;perm=%d;post=@@;" % (escape(who.nick), perm))
        run(who, "apply;number=0;action=2;")
    give(eve, 1000, 1000)
    run(eve, "head;reg=@x@;soc=@Соседи %s@;" % RUN)
    theirs = CLANS.member(eve.char_id)["clan_id"]
    for s in everyone:
        run(s, "gg_info;det=1;")
    check("the clan: the head 65535, the officer 0x402, the member 0x2",
          [CLANS.member(s.char_id)["perm"] for s in (alice, bob, carol)],
          [65535, clans.R_AFRO | clans.R_CHAT, clans.R_CHAT])
    give(bob, 1000)
    give(carol, 1000)
    for s in everyone:
        take(s)

    # --- the balance: to the holders of 0x400, silently refused to the rest ----------
    for s, who in ((alice, "the head (65535)"), (bob, "the officer (0x400)")):
        res, got = one_ack(s, "gg_info;det=3;", "balance")
        check("det=3 from %s: res=3 with 0, then 0" % who, shape(got),
              [("gg_list", 3, [0]), ("cmdAck", 0)])
    for s, who in ((carol, "a member without 0x400"), (dave, "a character in no clan")):
        res, got = one_ack(s, "gg_info;det=3;", "balance refused")
        check("det=3 from %s: 20 alone -- no balance, no gg_code popup" % who, shape(got),
              [("cmdAck", 20)])
    for s in (alice, carol, dave):
        res, got = one_ack(s, "gg_info;det=4;", "gold balance")
        check("det=4 (the gold treasury is off) from %s: 20 alone" % s.nick, shape(got),
              [("cmdAck", 20)])

    # --- a deposit by a member without any right -----------------------------------------
    m0, c0 = counts(ours, carol)
    res, got = one_ack(carol, "apply;number=500;action=3;", "deposit")
    check("Carol, without 0x400, puts 500 in: the purse pushed BEFORE the 0",
          shape(got), [("userInfo_Player", 500), ("cmdAck", 0)])
    check("  ..500 less in memory and in the row, 500 in the treasury",
          (purse(carol), STORE.clan_treasury(ours)), ((500, 500), 500))
    check("  ..one row in each journal", counts(ours, carol), (m0 + 1, c0 + 1))
    check("  ..money_ledger: source clan, ref the clan, -500",
          [(r["source"], r["ref"], r["afro"], r["gold"]) for r in STORE.ledger(carol.char_id)][-1],
          ("clan", ours, -500, 0))
    check("  ..clan_ledger: deposit, by her, +500",
          [(r["source"], r["char_id"], r["ref"], r["afro"])
           for r in STORE.clan_ledger_rows(ours, 1)], [("deposit", carol.char_id, 0, 500)])
    check("  ..the other holders of 0x400 online get the balance, unasked; nobody else",
          [shape(take(s)) for s in (alice, bob, carol, dave, eve)],
          [[("gg_list", 3, [500])], [("gg_list", 3, [500])], [], [], []])

    # --- a withdrawal: without the right, and with it ---------------------------------
    res, got = one_ack(carol, "apply;number=-100;action=3;", "withdraw, no right")
    check("Carol takes 100 out without 0x400: gg_code 20, then 20",
          shape(got), [("gg_code", 20), ("cmdAck", 20)])
    check("  ..nothing moved", (purse(carol), STORE.clan_treasury(ours), counts(ours, carol)),
          ((500, 500), 500, (m0 + 1, c0 + 1)))
    bob0 = purse(bob)[0]
    res, got = one_ack(bob, "apply;number=-200;action=3;", "withdraw")
    check("Bob, with 0x400, takes 200 out: the purse, then 0",
          shape(got), [("userInfo_Player", bob0 + 200), ("cmdAck", 0)])
    check("  ..in memory, in the row, and 300 left",
          (purse(bob), STORE.clan_treasury(ours)), ((bob0 + 200, bob0 + 200), 300))
    check("  ..booked clan +200 and withdraw -200",
          ([(r["source"], r["ref"], r["afro"]) for r in STORE.ledger(bob.char_id)][-1],
           [(r["source"], r["char_id"], r["afro"]) for r in STORE.clan_ledger_rows(ours, 1)]),
          (("clan", ours, 200), [("withdraw", bob.char_id, -200)]))
    check("  ..the head hears the new balance; Bob, whose page asks by itself, does not",
          [shape(take(s)) for s in (alice, bob, carol)], [[("gg_list", 3, [300])], [], []])
    res, got = one_ack(bob, "gg_info;det=3;", "balance after")
    check("  ..and when it asks: 300", shape(got), [("gg_list", 3, [300]), ("cmdAck", 0)])

    # --- past the balance, past the purse ---------------------------------------------------
    before = (purse(bob), STORE.clan_treasury(ours), counts(ours, bob))
    res, got = one_ack(bob, "apply;number=-301;action=3;", "past the balance")
    check("Bob takes 301 out of 300: 21, no purse pushed", shape(got), [("cmdAck", 21)])
    check("  ..and he is told the balance, as the page shows nothing",
          [p["entry"] for p in named(got, "userMsg")],
          ["На клановом счёте 300 афро — снять 301 нельзя"])
    check("  ..nothing moved", (purse(bob), STORE.clan_treasury(ours), counts(ours, bob)),
          before)
    res, got = one_ack(carol, "apply;number=501;action=3;", "past the purse")
    check("Carol puts in 501 of her 500: 21, nothing moved",
          (shape(got), purse(carol), STORE.clan_treasury(ours)),
          ([("cmdAck", 21)], (500, 500), 300))
    for s in everyone:
        take(s)

    # --- whatever a modified client writes as the number -------------------------------
    before = (purse(alice), STORE.clan_treasury(ours), counts(ours, alice))
    bad = ("0", "0.0", "-0.0", "2.5", "-2.5", "0.5", "1e-7", "1000000", "-1000000",
           "99999999999999999999", "-99999999999999999999", "1e999", "-1e999",
           "@100@", "x100", "|100|", "|@100@|")
    for number in bad:
        res, got = one_ack(alice, "apply;number=%s;action=3;" % number, "bad number")
        check("number=%s: 21 alone" % number, shape(got), [("cmdAck", 21)])
    for text in ("apply;action=3;", "apply;number=100;number=100;action=3;"):
        res, got = one_ack(alice, text, "bad frame")
        check("%s: 21 alone" % text, shape(got), [("cmdAck", 21)])
    check("  ..and after all of them nothing moved, in memory, the row, the treasury or"
          " a journal", (purse(alice), STORE.clan_treasury(ours), counts(ours, alice)), before)
    check("  ..and the other holders heard nothing", [shape(take(s)) for s in (bob, carol)],
          [[], []])
    alice0 = purse(alice)[0]
    for number in ("1e2", "99.99999999999999", "100.0"):
        res, got = one_ack(alice, "apply;number=%s;action=3;" % number, "whole float")
        check("number=%s is the whole 100 it stands for: the purse, then 0" % number,
              shape(got), [("userInfo_Player", alice0 - 100), ("cmdAck", 0)])
        alice0 -= 100
    check("  ..300 more, booked as whole numbers", (STORE.clan_treasury(ours), [
        (r["source"], r["afro"]) for r in STORE.clan_ledger_rows(ours, 3)]),
          (600, [("deposit", 100)] * 3))
    check("  ..the numbers in the rows are integers",
          {type(r["afro"]) for r in STORE.clan_ledger_rows(ours, 3)}, {int})
    res, got = one_ack(alice, "apply;number=-300.0000000001;action=3;", "whole float out")
    check("-300.0000000001 is 300 out: 0", (res, STORE.clan_treasury(ours), purse(alice)[0]),
          (0, 300, alice0 + 300))
    res, got = one_ack(alice, "apply;number=999999;action=3;", "the most in")
    check("999 999 in at once, the field's six digits: 0",
          (res, STORE.clan_treasury(ours)), (0, 300 + 999999))
    res, got = one_ack(alice, "apply;number=-999999;action=3;", "the most out")
    check("999 999 out at once: 0", (res, STORE.clan_treasury(ours)), (0, 300))
    for s in everyone:
        take(s)

    # --- the gold treasury: off ------------------------------------------------------------------
    gold0 = (alice.character().gold, STORE.money(alice.char_id)[1])
    before = (purse(alice), STORE.clan_treasury(ours), counts(ours, alice))
    for s, text in ((alice, "apply;number=100;action=4;"),
                    (alice, "apply;number=-28.999999999999996;action=4;"),
                    (alice, "apply;number=@x@;action=4;"),
                    (dave, "apply;number=100;action=4;")):
        res, got = one_ack(s, text, "gold")
        check("%s from %s: 21 alone" % (text, s.nick), shape(got), [("cmdAck", 21)])
    check("  ..no gold and no afro moved",
          ((alice.character().gold, STORE.money(alice.char_id)[1]), purse(alice),
           STORE.clan_treasury(ours), counts(ours, alice)), (gold0,) + before)

    # --- a character in no clan, and another clan's member -----------------------------------
    for text in ("apply;number=100;action=3;", "apply;number=-100;action=3;"):
        res, got = one_ack(dave, text, "not a member")
        check("%s from a character in no clan: 20 alone" % text, shape(got), [("cmdAck", 20)])
    eve0 = purse(eve)
    res, got = one_ack(eve, "apply;number=-100;action=3;", "the other clan")
    check("Eve, head of the other clan, takes 100 out: of her own clan's empty treasury,"
          " 21 -- ours is never touched", (res, purse(eve), STORE.clan_treasury(ours),
                                          STORE.clan_treasury(theirs)), (21, eve0, 300, 0))
    for s in everyone:
        take(s)

    # --- two withdrawals of the whole treasury, in the game ------------------------------------
    alice0, bob0 = purse(alice)[0], purse(bob)[0]
    res_a, got_a = one_ack(alice, "apply;number=-300;action=3;", "race, first")
    res_b, got_b = one_ack(bob, "apply;number=-300;action=3;", "race, second")
    check("the head and the officer both take the whole 300: the first 0, the second 21",
          (res_a, res_b, shape(got_b)[:1]), (0, 21, [("cmdAck", 21)]))
    check("  ..paid once", (purse(alice)[0] - alice0, purse(bob)[0] - bob0,
                            STORE.clan_treasury(ours)), (300, 0, 0))

    # --- ... and across two connections: the admin's tools take it meanwhile -------------------
    res, _ = one_ack(alice, "apply;number=400;action=3;", "refill")
    for s in everyone:
        take(s)
    bob0 = purse(bob)
    moved = counts(ours, bob)
    STORE.db.commit()
    held, done = threading.Event(), threading.Event()

    def other_process():
        # Another connection -- another process, as tools/ are -- takes the
        # whole treasury in a transaction it keeps open a while; booked, as
        # the admin's adjustment is.
        db = storage.connect() if PG else storage.connect(DB)
        try:
            db.execute("UPDATE clans SET afro = afro - ? WHERE id = ? AND afro >= ?",
                       (400, ours, 400))
            accounts.clan_book(db, ours, "admin", -400)
            held.set()
            time.sleep(0.8)
            db.commit()
        finally:
            db.close()
            done.set()

    worker = threading.Thread(target=other_process)
    worker.start()
    held.wait(10)
    t0 = time.time()
    res, got = one_ack(bob, "apply;number=-400;action=3;", "cross race")
    waited = time.time() - t0
    worker.join(10)
    check("Bob takes the 400 while another connection holds the row: his write waits for"
          " its commit, then finds nothing -- 21", (res, waited > 0.5, shape(got)),
          (21, True, [("cmdAck", 21)]))
    check("  ..he has nothing more, nothing is booked, the treasury is empty",
          (purse(bob), counts(ours, bob)[0] - moved[0], STORE.clan_treasury(ours)),
          (bob0, 0, 0))

    # --- the three writes of a move in one transaction ------------------------------------
    run(alice, "apply;number=1000;action=3;")
    for s in everyone:
        take(s)
    before = (purse(alice), STORE.clan_treasury(ours), counts(ours, alice))
    real_book = accounts.clan_book

    def broken(*_a, **_k):
        raise RuntimeError("the treasury's journal failed")

    accounts.clan_book = broken
    try:
        res, got = one_ack(alice, "apply;number=10;action=3;", "failing journal")
    finally:
        accounts.clan_book = real_book
    check("the treasury's journal fails mid-move: 20 from the wrapper, no purse pushed",
          shape(got), [("cmdAck", 20)])
    check("  ..and neither the purse (memory, row) nor the treasury nor money_ledger moved",
          (purse(alice), STORE.clan_treasury(ours), counts(ours, alice)), before)
    check("  ..no answer was ever sent twice", CLANS.double_acks, [])

    # --- a dead member ------------------------------------------------------------------------
    bob.combat.dead = True
    res, got = one_ack(bob, "gg_info;det=3;", "dead balance")
    check("a dead officer's page asks the balance: it gets it (gg_info passes the dead"
          " filter)", shape(got), [("gg_list", 3, [1000]), ("cmdAck", 0)])
    res, got = one_ack(bob, "apply;number=-10;action=3;", "dead withdraw")
    check("  ..but takes nothing out: the dead filter's 20", (shape(got), purse(bob)),
          ([("cmdAck", 20)], bob0))
    bob.combat.dead = False

    # --- a kicked member's page, still open ----------------------------------------------------
    run(alice, "apply;number=%d;action=1;" % carol.char_id)
    check("Carol is kicked", CLANS.member(carol.char_id), None)
    for s in everyone:
        take(s)
    carol0 = purse(carol)
    for text, want in (("apply;number=50;action=3;", [("cmdAck", 20)]),
                       ("apply;number=-50;action=3;", [("cmdAck", 20)]),
                       ("gg_info;det=3;", [("cmdAck", 20)]),
                       ("apply;number=50;action=4;", [("cmdAck", 21)])):
        res, got = one_ack(carol, text, "stale page")
        check("her stale page sends %s: %s" % (text, want), shape(got), want)
    check("  ..her purse and the treasury as they were", (purse(carol), STORE.clan_treasury(ours)),
          (carol0, 1000))
    run(alice, "apply;number=5;action=3;")
    check("  ..and the next move's balance goes to Bob, not to her (nor to the mover)",
          [shape(take(s)) for s in (bob, carol, alice)],
          [[("gg_list", 3, [1005])], [], [("userInfo_Player", purse(alice)[0]), ("cmdAck", 0)]])

    # --- both journals add up ------------------------------------------------------------------
    rows = STORE.clan_ledger_rows(ours, 100000)
    check("the treasury's journal adds up to the treasury",
          sum(r["afro"] for r in rows), STORE.clan_treasury(ours))
    mine = {s.char_id for s in everyone}
    money = [r for c in mine for r in STORE.ledger(c) if r["source"] == "clan"
             and r["ref"] == ours]
    check("  ..and every 'clan' row of a purse is a deposit or withdrawal the other way",
          sum(r["afro"] for r in money),
          -sum(r["afro"] for r in rows if r["source"] in ("deposit", "withdraw")))
    check("  ..one row each side per move",
          len(money), len([r for r in rows if r["source"] in ("deposit", "withdraw")]))

    # --- the report --------------------------------------------------------------------------
    # A stance paid for, an admin's gift, Eve's clan disbanded with its
    # treasury into her live purse, and Dave's clan lost with him when the
    # admin's tool deletes him, its last member.
    check("a stance paid for out of the treasury (clan_diplomacy's way)",
          STORE.clan_spend(ours, clans.STANCE_UP, "diplomacy", theirs, alice.char_id), True)
    clan_treasury.tell_balance(CLANS, ours)
    check("  ..and tell_balance sends it to the holders of 0x400 online",
          [shape(take(s)) for s in (alice, bob, carol)],
          [[("gg_list", 3, [5])], [("gg_list", 3, [5])], []])
    STORE.clan_treasury_adjust(ours, 50, "admin")
    STORE.clan_treasury_adjust(theirs, 70, "admin")
    eve0 = purse(eve)[0]
    check("Eve's clan disbanded: its 70 into her live purse", CLANS.disband(theirs), 70)
    check("  ..in memory and the row", purse(eve), (eve0 + 70, eve0 + 70))
    give(dave, 0, 1000)
    run(dave, "head;reg=@x@;soc=@Одиночки %s@;" % RUN)
    lone = CLANS.member(dave.char_id)["clan_id"]
    STORE.clan_treasury_adjust(lone, 30, "admin")
    STORE.db.commit()
    tool = accounts.Store(DB)
    with tool.db:
        gone = accounts.clan_hand_over(tool.db, dave.char_id)
    tool.close()
    check("Dave's clan goes with him, its 30 with it", gone, (lone, None, 30))

    our_clans = {ours, theirs, lone}
    money_rows = [r for r in STORE.ledger() if r["char_id"] in mine]
    clan_rows = [r for r in money_report.treasury_rows(STORE) if r["clan_id"] in our_clans]
    paid = {c: a for c, a in money_report.payouts(STORE).items() if c in our_clans}
    s = money_report.summarize(money_rows)
    moves = [r for r in money_rows if r["source"] in ("clan", "clan_disband")]
    check("the report keeps clan and clan_disband out of the sources, the bands and the days",
          ("clan" in s["source"], "clan_disband" in s["source"],
           any(src in ("clan", "clan_disband") for _b, src in s["band"]),
           any(src in ("clan", "clan_disband") for _d, src in s["day"])),
          (False, False, False, False))
    check("  ..and out of the total: every row is a tap or drain, a transfer, or opening",
          s["total"].rows + sum(x.rows for x in s["transfer"].values()) + s["opening"].rows,
          len(money_rows))
    check("  ..the transfers on their own: every move, and the 70 paid out",
          (sum(x.rows for x in s["transfer"].values()), s["transfer"]["clan_disband"].afro_in),
          (len(moves), 70))
    check("  ..clan_create, the founding fee, stays a drain of gold",
          s["source"]["clan_create"].gold_out, -3000)
    t = money_report.summarize_treasury(clan_rows, paid)
    k = t["kind"]
    net = lambda x: x.afro_in + x.afro_out  # noqa: E731
    check("the treasuries' transfers are the purses' the other way round",
          net(k["transfer"]), -sum(net(x) for x in s["transfer"].values()))
    check("  ..the taps: the admin's +50, +70, +30",
          (k["tap"].afro_in, k["tap"].afro_out), (150, 0))
    check("  ..the drains: the other connection's -400 (an admin's), the stance's -1000,"
          " the 30 lost with Dave", (k["drain"].afro_in, k["drain"].afro_out),
          (0, -400 - 1000 - 30))
    check("  ..by source", sorted(t["source"]),
          ["admin", "deposit", "diplomacy", "disband", "withdraw"])
    stock = money_report.treasury_stock(STORE)
    check("the stock: what the treasuries hold is what their journal adds up to",
          [off for off in stock["off"] if off[0] in our_clans], [])
    text = money_report.report(money_rows, clan_rows, paid, stock)
    check("  ..and the report prints the transfers, the treasuries and the whole economy",
          [w in text for w in ("moves between purses and clan treasuries",
                               "Transfers with clan treasuries:",
                               "Clan treasuries (clan_ledger)", "treasuries now:",
                               "Clan treasuries by source:", "diplomacy",
                               "The whole economy")], [True] * 7)
    check("  ..the transfers are not in its «By source» table",
          [line for line in text.split("Transfers with clan treasuries:")[0].splitlines()
           if line.strip().startswith(("clan ", "clan_disband"))], [])
    STORE.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = money_report.main(["--days", "0"] + ([] if PG else ["--db", DB]))
    check("tools/money_report.py itself runs on this database and prints the treasuries",
          (rc, "Clan treasuries by source:" in out.getvalue(),
           "treasuries now:" in out.getvalue()), (0, True, True))
    STORE.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        money_report.main(["--days", "1", "--char", str(bob.char_id)]
                          + ([] if PG else ["--db", DB]))
    check("  ..and for one character: his moves, his treasury rows",
          ("Transfers with clan treasuries:" in out.getvalue(),
           "withdraw" in out.getvalue(), "deposit " in out.getvalue()), (True, True, False))

    # --- over a restart ------------------------------------------------------------------------
    STORE.db.commit()
    fresh = accounts.Store(DB)
    check("a fresh connection reads the treasury as the game left it",
          fresh.clan_treasury(ours), STORE.clan_treasury(ours))
    fresh.close()
    check("no command was ever answered twice", CLANS.double_acks, [])
    for sess in list(server.SESSIONS) + list(everyone):
        sess.close()


logging.getLogger("lava").disabled = True
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("clan treasury OK")
