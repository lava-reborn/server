"""Stance steps ordered on the site (site_orders.py), carried out in process
where the order of frames across several sessions is exact.

The site writes a row into site_orders and the game's admin loop carries it
out (site_orders.drain). Two clans of two members each, a free onlooker,
and an officer of ours with the right of diplomacy who is not playing.
Every refusal of the module's note with its code and its words, each
writing nothing but its row's answer: no right (R1), a clan that is no more
or our own (R2), a step past war or peace (R3), a stance or a clan that
moved (R4), a treasury short (R5), a row too old by a fixed clock (R6), and
a row that speaks for someone else, a banned account, a character that is
not, a column that is not a whole number, a row from the future (R7). A step
up and a step down: the price out of the treasury, one 'diplomacy' row in
its journal, the stance, and the order marked OK with the words the site
shows -- and the frames of the in-game button, res=8 to every member of
ours online with the tags after it, res=9 to theirs, the balance to the
0x400 holders, with no cmdAck to anyone and no chat line; the actor need
not be playing. A pass takes the oldest first, 20 at most. An order run
again keeps its answer and charges nothing. A stop before the step's commit
writes nothing and leaves the order waiting; a stop after it leaves the
order done, never run again. And the real admin loop, where no site row
reaches server.apply_admin_action.

    LAVA_RES=.../lava/res python3 server/test_site_orders.py

Runs on Postgres too, when LAVA_DB_URL names a throwaway database: every
name is made unique per run, and only this run's orders and clans are
compared. The columns SQLite keeps as they come (a text, a fraction) are
written on SQLite alone, Postgres refusing to store them; a row handed to
site_orders.apply with a dir of True is tried on both.
"""
import asyncio
import logging
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "site_orders.db")
os.environ["LAVA_DB"] = DB
# Everyone wakes in the same place, so that they see each other.
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
# No reload hint in the way: every client here asks for its roster.
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"
# The admin loop's pass, short: the last section runs the loop itself.
os.environ["LAVA_ADMIN_POLL"] = "0.05"

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import storage  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
PG = storage.using_postgres()


def nick(base):
    return "%s%s" % (base, RUN)


LOGINS = ("alice", "bob", "carol", "dave", "eve", "gus")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l + RUN, "secret")
_store.close()

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)
import clan_diplomacy  # noqa: E402
import clans  # noqa: E402
import site_orders  # noqa: E402

STORE = server.STORE
CLANS = server.CLANS
from testkit import check, fails  # noqa: E402


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


class Lines(logging.Handler):
    """What the game's log was told, and at which level."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelno, record.getMessage()))


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def take(sess):
    out = sess.writer.frames[:]
    sess.writer.frames.clear()
    return out


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def named(frames, name):
    return [p for n, p in frames if n == name]


CLAN_FRAMES = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code",
               "userInfo_Player", "userMsg")


def only(frames):
    return [(n, p) for n, p in frames if n in CLAN_FRAMES]


def shape(frames):
    """(name, what tells it apart) of each clan frame: an answer's or a
    list's res, the id a fellow is about."""
    return [(n, p.get("id") if n == "fellow" else p.get("res")) for n, p in only(frames)]


def login(login_name, char_name):
    sess = server.Session(Writer(), login_name)
    run(sess, "login;hash=@%s@;" % accounts.credential(login_name + RUN, "secret"))
    run(sess, "newPers;res=1;sex=0;name=@%s@;" % escape(char_name))
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    return sess


def one_ack(sess, text, label):
    """One clan command: exactly one cmdAck, never one the client pops an
    alert for (clans.NEVER). Returns (res, frames)."""
    take(sess)
    run(sess, text)
    got = take(sess)
    a = acks(got)
    if len(a) != 1 or a[0] in clans.NEVER:
        fails.append("%s: acks %r for %r" % (label, a, text))
    return (a[0] if a else None), got


def found(sess, name):
    """sess founds a clan and asks what its client asks on the fellow."""
    ch = sess.character()
    ch.gold = clans.CREATE_GOLD
    ch.save(STORE)
    res, _ = one_ack(sess, "head;reg=@x@;soc=@%s@;" % name, "found " + name)
    if res != 0:
        fails.append("founding %r: %r" % (name, res))
    run(sess, "gg_info;det=1;")
    run(sess, "gg_info;det=5;")
    take(sess)
    return CLANS.member(sess.char_id)["clan_id"]


def join(head, sess, perm):
    one_ack(head, "admit;char=@%s@;perm=%d;post=@@;" % (escape(sess.nick), perm), "invite")
    res, _ = one_ack(sess, "apply;number=0;action=2;", "accept")
    if res != 0:
        fails.append("%s joining: %r" % (sess.nick, res))
    run(sess, "gg_info;det=1;")
    run(sess, "gg_info;det=5;")
    take(sess)


# This run's orders: on Postgres the table may hold other runs' too.
MINE = set()


def order(char_id, who, clan_id, other, stat_from, step, made_at=None):
    """A row as the site writes it (lava-site api/db.py queue_stance): every
    value a bound parameter, the login the signed-in one."""
    oid = STORE.db.insert(
        "INSERT INTO site_orders (made_at, login, char_id, clan_id, other, stat_from, dir)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time() if made_at is None else made_at, who, char_id, clan_id, other,
         stat_from, step))
    STORE.db.commit()
    MINE.add(oid)
    return oid


def drained(now=None):
    """One pass of the drain: [(id, code)] of this run's orders."""
    return [(i, c) for i, c in site_orders.drain(STORE, CLANS, now) if i in MINE]


def answer(oid):
    row = STORE.site_order(oid)
    return (row["code"], row["result"]) if row["done_at"] is not None else None


def journal(clan_id):
    return [(r["source"], r["afro"], r["ref"], r["char_id"])
            for r in reversed(STORE.clan_ledger_rows(clan_id, 100))]


def books(clan_id):
    """Everything a step writes: the treasury, its journal, the stances."""
    return (STORE.clan_treasury(clan_id), journal(clan_id), STORE.clan_relations_of(clan_id))


async def main():
    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    carol = login("carol", nick("Carol"))
    dave = login("dave", nick("Dave"))
    eve = login("eve", nick("Eve"))
    gus = login("gus", nick("Gus"))
    sessions = (alice, bob, carol, dave, eve)
    for s in sessions + (gus,):
        take(s)
    acct = {s: s.account["login"] for s in sessions + (gus,)}

    # --- two clans, and an officer of ours who is not playing --------------------------
    wolves_name, foxes_name = "Волки %s" % RUN, "Лисы %s" % RUN
    wolves = found(alice, wolves_name)
    foxes = found(carol, foxes_name)
    join(alice, bob, 0x2)
    join(carol, dave, 0x2)
    join(alice, gus, 0x2 | clans.R_DIPLOMACY)
    gus_id = gus.char_id
    gus.close()
    for s in sessions:
        take(s)
    check("the officer holds the right of diplomacy, and he is not playing",
          (CLANS.member(gus_id)["perm"] & clans.R_DIPLOMACY, gus_id in
           {s.char_id for s in server.SESSIONS if not s.closed}), (clans.R_DIPLOMACY, False))
    top = max(c["id"] for c in STORE.clan_all())
    clean = books(wolves)

    # --- the refusals, each writing nothing but its answer -----------------------------
    now = time.time()
    shaped = []
    if not PG:
        # SQLite keeps what it is given in a column of any type.
        shaped = [order(alice.char_id, acct[alice], wolves, foxes, 0, "up"),
                  order(alice.char_id, acct[alice], wolves, foxes, 0.5, 1),
                  order(alice.char_id, acct[alice], wolves, foxes, 0, 1, made_at="вчера")]
    cases = [
        ("a member without 0x2000", order(bob.char_id, acct[bob], wolves, foxes, 0, 1),
         ("R1", "У персонажа %s нет права дипломатии в клане." % bob.nick)),
        ("a free character", order(eve.char_id, acct[eve], wolves, foxes, 0, 1),
         ("R1", "У персонажа %s нет права дипломатии в клане." % eve.nick)),
        ("a clan that is not", order(alice.char_id, acct[alice], wolves, top + 1000, 0, 1),
         ("R2", "Клана «%d» больше нет." % (top + 1000))),
        ("our own clan", order(alice.char_id, acct[alice], wolves, wolves, 0, 1),
         ("R2", "Клана «%s» больше нет." % wolves_name)),
        ("a step past peace", order(alice.char_id, acct[alice], wolves, foxes, 1, 1),
         ("R3", "Отношение к клану «%s» уже мир." % foxes_name)),
        ("a step past war", order(alice.char_id, acct[alice], wolves, foxes, -1, -1),
         ("R3", "Отношение к клану «%s» уже война." % foxes_name)),
        ("a stance that is not the one the site saw",
         order(alice.char_id, acct[alice], wolves, foxes, -1, 1),
         ("R4", "Отношение к клану «%s» уже изменилось. Обновите страницу." % foxes_name)),
        ("a clan that is not hers", order(alice.char_id, acct[alice], foxes, wolves, 0, 1),
         ("R4", "Отношение к клану «%s» уже изменилось. Обновите страницу." % wolves_name)),
        ("a step up, the treasury empty", order(alice.char_id, acct[alice], wolves, foxes, 0, 1),
         ("R5", "В казне клана «%s» меньше 1.000 афро." % wolves_name)),
        ("a step down, the treasury empty",
         order(alice.char_id, acct[alice], wolves, foxes, 0, -1, made_at=now - 59),
         ("R5", "В казне клана «%s» меньше 100 афро." % wolves_name)),
        ("a row made 61 s ago", order(alice.char_id, acct[alice], wolves, foxes, 0, -1,
                                      made_at=now - 61),
         ("R6", "Игровой сервер не успел выполнить приказ, отношения не изменились."
                " Попробуйте ещё раз.")),
        ("a row from an hour ahead", order(alice.char_id, acct[alice], wolves, foxes, 0, -1,
                                           made_at=now + 3600), ("R7", "Приказ отклонён.")),
        ("her character, another's login", order(alice.char_id, acct[eve], wolves, foxes, 0, 1),
         ("R7", "Приказ отклонён.")),
        ("a character that is not", order(10 ** 12, acct[alice], wolves, foxes, 0, 1),
         ("R7", "Приказ отклонён.")),
        ("a step of two", order(alice.char_id, acct[alice], wolves, foxes, -1, 2),
         ("R7", "Приказ отклонён.")),
        ("no step at all", order(alice.char_id, acct[alice], wolves, foxes, 0, 0),
         ("R7", "Приказ отклонён.")),
        ("a stance that is none of the three", order(alice.char_id, acct[alice], wolves, foxes,
                                                     2, -1), ("R7", "Приказ отклонён.")),
    ] + [("a column SQLite kept as it came (%d)" % (i + 1), oid, ("R7", "Приказ отклонён."))
         for i, oid in enumerate(shaped)]
    STORE.db.execute("UPDATE accounts SET banned = 1 WHERE login = ?", (acct[gus],))
    STORE.db.commit()
    cases.append(("a banned account", order(gus_id, acct[gus], wolves, foxes, 0, 1),
                  ("R7", "Приказ отклонён.")))
    forged = order(alice.char_id, acct[alice], wolves, foxes, 0, 1)
    row = dict(STORE.site_order(forged))
    row["dir"] = True
    check("a row handed over with dir True, not a whole number: R7",
          site_orders.apply(STORE, CLANS, row, now), ("R7", "Приказ отклонён."))
    MINE.discard(forged)
    passes = []
    while not passes or passes[-1]:
        passes.append(drained(now))
    got = dict(sum(passes, []))
    check("a pass carries out %d orders at most, the rest wait for the next"
          % site_orders.BATCH, [len(p) for p in passes[:-1]],
          [min(site_orders.BATCH, len(cases) - i)
           for i in range(0, len(cases), site_orders.BATCH)])
    for label, oid, want in cases:
        check("%s: %s" % (label, want[0]), (got.get(oid), answer(oid)), (want[0], want))
    STORE.db.execute("UPDATE accounts SET banned = 0 WHERE login = ?", (acct[gus],))
    STORE.db.commit()
    check("  ..the passes answered every one of them, the forged row before them",
          (sorted(got), answer(forged)), (sorted(oid for _l, oid, _w in cases),
                                           ("R7", "Приказ отклонён.")))
    check("  ..and nothing was charged, booked or set", books(wolves), clean)
    check("  ..and no client heard a thing: no answer, no list, no chat line",
          [only(take(s)) for s in sessions], [[]] * len(sessions))

    # --- a step up, ordered on the site ----------------------------------------------
    STORE.clan_treasury_adjust(wolves, 1150, "admin")
    up = order(alice.char_id, acct[alice], wolves, foxes, 0, 1)
    check("the drain: OK", drained(), [(up, "OK")])
    check("  ..the order answered with the words the site shows",
          answer(up), ("OK", "Готово: отношение клана «%s» к клану «%s» теперь — мир."
                             " Из казны списано 1.000 афро." % (wolves_name, foxes_name)))
    got = take(alice)
    check("  ..the actor, playing: res=8 like any member, the tags of theirs she sees,"
          " the balance (she holds 0x400) -- and no cmdAck, there being no command",
          shape(got), [("gg_list", 8), ("fellow", carol.pid), ("fellow", dave.pid),
                       ("gg_list", 3)])
    check("  ..res=8 in full, res=3 with what is left", named(got, "gg_list"),
          [{"res": 8, "data": [foxes], "names": [foxes_name], "stats": [1]},
           {"res": 3, "data": [150]}])
    check("  ..our other member: res=8 and the tags, no balance without 0x400",
          shape(take(bob)), [("gg_list", 8), ("fellow", carol.pid), ("fellow", dave.pid)])
    want9 = {"res": 9, "data": [wolves], "names": [wolves_name], "stats": [1]}
    check("  ..each of theirs: res=9 alone", [only(take(s)) for s in (carol, dave)],
          [[("gg_list", want9)]] * 2)
    check("  ..the onlooker: nothing", only(take(eve)), [])
    check("  ..1 000 out, one 'diplomacy' row by her, ref them; ours peace, theirs neutral",
          (STORE.clan_treasury(wolves), journal(wolves)[1:], STORE.clan_relation(wolves, foxes),
           STORE.clan_relation(foxes, wolves)),
          (150, [("diplomacy", -1000, foxes, alice.char_id)], 1, 0))
    check("  ..one clan_relations row for it",
          STORE.db.execute("SELECT COUNT(*) AS c FROM clan_relations WHERE clan_id = ?",
                           (wolves,)).fetchone()["c"], 1)
    check("  ..the drain again: nothing waits", drained(), [])

    # --- a step down by the officer who is not playing --------------------------------
    down = order(gus_id, acct[gus], wolves, foxes, 1, -1)
    check("the officer's step down: OK, 100 out", (drained(), answer(down)),
          ([(down, "OK")], ("OK", "Готово: отношение клана «%s» к клану «%s» теперь —"
                                  " нейтралитет. Из казны списано 100 афро."
                            % (wolves_name, foxes_name))))
    check("  ..the head hears res=8 with neutrality and the balance",
          [(p["res"], p.get("stats", p.get("data"))) for p in named(take(alice), "gg_list")],
          [(8, [0]), (3, [50])])
    check("  ..bob res=8; theirs res=9", (shape(take(bob))[:1],
                                          [named(take(s), "gg_list") for s in (carol, dave)]),
          ([("gg_list", 8)], [[dict(want9, stats=[0])]] * 2))
    check("  ..booked by him", journal(wolves)[-1], ("diplomacy", -100, foxes, gus_id))

    # --- one pass, oldest first ---------------------------------------------------------
    STORE.clan_treasury_adjust(wolves, 1100, "admin")
    first = order(alice.char_id, acct[alice], wolves, foxes, 0, -1)
    second = order(alice.char_id, acct[alice], wolves, foxes, 0, -1)
    third = order(alice.char_id, acct[alice], wolves, foxes, -1, 1)
    snapshot = {r["id"]: dict(r) for r in STORE.site_pending()}
    check("three orders in one pass: the first makes war, the second finds it made,"
          " the third makes neutrality again", drained(),
          [(first, "OK"), (second, "R4"), (third, "OK")])
    check("  ..100 and 1 000 out",
          (STORE.clan_treasury(wolves), STORE.clan_relation(wolves, foxes)), (50, 0))
    for s in sessions:
        take(s)

    # --- an order run again keeps its answer ----------------------------------------------
    STORE.clan_treasury_adjust(wolves, 1000, "admin")
    before = books(wolves)
    kept = {oid: answer(oid) for oid in (first, second)}
    check("the first order, read before it was answered, run again: its own answer back,"
          " and kept", (site_orders.apply(STORE, CLANS, snapshot[first]), answer(first)),
          (kept[first], kept[first]))
    check("  ..the step it would make rolled back with the order: nothing charged or set",
          books(wolves), before)
    check("  ..the second, a refusal, run again: its R4 back and kept, nothing written",
          (site_orders.apply(STORE, CLANS, snapshot[second]), answer(second), books(wolves)),
          (kept[second], kept[second], before))
    check("  ..an order answered with a refusal is not answered again",
          STORE.site_done(second, "R7", "x"), False)
    check("  ..and nobody heard of either", [only(take(s)) for s in sessions],
          [[]] * len(sessions))
    check("Store.clan_stance_step for an order answered already: None, nothing written",
          (STORE.clan_stance_step(wolves, foxes, 0, 1, 1000, alice.char_id,
                                  need=clans.R_DIPLOMACY, order=(first, "x")),
           books(wolves), answer(first)[0]), (None, before, "OK"))

    # --- a stop before the step's commit --------------------------------------------------
    real_book = accounts.clan_book

    def broken_book(*_a, **_k):
        raise RuntimeError("the database went away mid-step")

    peace = order(alice.char_id, acct[alice], wolves, foxes, 0, 1)
    accounts.clan_book = broken_book
    try:
        got = drained()
    finally:
        accounts.clan_book = real_book
    check("the step failing before its commit: not answered", (got, answer(peace)), ([], None))
    check("  ..nothing written: no price, no stance, no journal row",
          books(wolves), before)
    check("  ..nobody heard a thing", [only(take(s)) for s in sessions], [[]] * len(sessions))
    check("  ..the order still waits, and the next pass carries it out",
          (drained(), STORE.clan_treasury(wolves), STORE.clan_relation(wolves, foxes)),
          ([(peace, "OK")], 50, 1))
    for s in sessions:
        take(s)

    # --- a stop after the step's commit ---------------------------------------------------
    STORE.clan_treasury_adjust(wolves, 100, "admin")
    real_announce = clan_diplomacy.announce

    def broken_announce(*_a, **_k):
        raise RuntimeError("the process stopped after the commit")

    calm = order(alice.char_id, acct[alice], wolves, foxes, 1, -1)
    clan_diplomacy.announce = broken_announce
    try:
        got = drained()
    finally:
        clan_diplomacy.announce = real_announce
    check("the pushes failing after the commit: the order done, OK", (got, answer(calm)[0]),
          ([], "OK"))
    check("  ..the step made once", (STORE.clan_treasury(wolves),
                                     STORE.clan_relation(wolves, foxes),
                                     journal(wolves)[-1]),
          (50, 0, ("diplomacy", -100, foxes, alice.char_id)))
    check("  ..the next pass does not run it again", (drained(), STORE.clan_treasury(wolves)),
          ([], 50))
    check("  ..the clients learn the stance at their next login: nothing now",
          [only(take(s)) for s in sessions], [[]] * len(sessions))

    # --- the admin loop: no site row reaches apply_admin_action -----------------------------
    seen = []
    real_apply = server.apply_admin_action

    def recorder(admin_row):
        seen.append((admin_row["id"], admin_row["kind"]))
        return "записано тестом"

    STORE.clan_treasury_adjust(wolves, 100, "admin")
    action = STORE.admin_push("tester" + RUN, "money", char_id=alice.char_id,
                              account_id=alice.account["id"], afro=1)
    war = order(alice.char_id, acct[alice], wolves, foxes, 0, -1)
    server.apply_admin_action = recorder
    try:
        loop = asyncio.ensure_future(server.drain_admin_actions())
        for _ in range(100):
            await asyncio.sleep(0.05)
            if answer(war) is not None and action in [i for i, _k in seen]:
                break
        loop.cancel()
        try:
            await loop
        except asyncio.CancelledError:
            pass
    finally:
        server.apply_admin_action = real_apply
    check("the admin loop: the admin's row to apply_admin_action, the site's to its own"
          " handler", ([s for s in seen if s[0] == action], answer(war)[0]),
          ([(action, "money")], "OK"))
    check("  ..nothing but the admin's own row reached apply_admin_action",
          [k for _i, k in seen], ["money"] * len(seen))
    check("  ..the war made, 100 out", (STORE.clan_relation(wolves, foxes),
                                        STORE.clan_treasury(wolves)), (-1, 50))
    check("  ..its frames, as the in-game button's", shape(take(alice)),
          [("gg_list", 8), ("fellow", carol.pid), ("fellow", dave.pid), ("gg_list", 3)])

    # --- the log ---------------------------------------------------------------------------
    said = [m for _lv, m in LINES.lines]
    for oid in sorted(MINE):
        if not any(("site order %d " % oid) in m or ("site order %d:" % oid) in m
                   for m in said):
            fails.append("order %d: no line in the log" % oid)
    check("every outcome has its line in the log; the only errors are the two stops"
          " this test made", [m for lv, m in LINES.lines if lv >= logging.ERROR],
          ["site order %d failed" % peace, "site order %d failed" % calm])
    check("no command was ever answered twice", CLANS.double_acks, [])
    for s in list(server.SESSIONS) + list(sessions):
        s.close()


LINES = Lines()
_lava = logging.getLogger("lava")
_lava.setLevel(logging.INFO)
_lava.propagate = False
_lava.addHandler(LINES)
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
print("site orders OK")
