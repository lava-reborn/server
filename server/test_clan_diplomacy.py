"""Clan diplomacy (clan_diplomacy.py), driven in process where the order of
frames across several sessions is exact.

Two clans of two members each and a free onlooker, all standing in one
place, and a third clan that comes and goes: the prices; who may change a
stance and every refusal with its code (rights, a clan that is no more, a
step past war or peace, a treasury short) with nothing charged; a step
up and a step down each charging its price out of the treasury and booking
it 'diplomacy' in the clan's journal, and no purse; the frames in their
order -- the actor's cmdAck 0 BEFORE his res=8, res=8 to every member of
ours, res=9 to every member of theirs, a fresh tag of each of their
members on our screens after it and none on theirs; the full standings
first to a client that does not hold the clan (I2); relations one-sided;
an officer with the right of diplomacy; «Спросить»; the step as one
transaction that writes nothing when anything it named has moved; a clan
founded and one disbanded, its relations gone both ways; the stance kept
across a new connection to the database and a new login. One cmdAck per
command throughout, never a code the client pops an alert for.

    LAVA_RES=.../lava/res python3 server/test_clan_diplomacy.py

Runs on Postgres too, when LAVA_DB_URL names a throwaway database: every
name is made unique per run, the clans of other runs are left out of what
is compared, and nothing is dropped.
"""
import asyncio
import logging
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "clan_diplomacy.db")
os.environ["LAVA_DB"] = DB
# Everyone wakes in the same place, so that they see each other.
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
# No reload hint in the way: every client here asks for its roster.
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"

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
import clans  # noqa: E402

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


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def named(frames, name):
    return [p for n, p in frames if n == name]


CLAN_FRAMES = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code",
               "userInfo_Player")


def only(frames, *keep):
    return [(n, p) for n, p in frames if n in (keep or CLAN_FRAMES)]


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


def give_gold(sess, gold):
    ch = sess.character()
    ch.gold = gold
    ch.save(STORE)


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
    give_gold(sess, clans.CREATE_GOLD)
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


def shape(frames):
    """(name, what tells it apart) of each clan frame: an answer's or a
    list's res, the id a fellow is about."""
    out = []
    for n, p in only(frames):
        out.append((n, p.get("id") if n == "fellow" else p.get("res")))
    return out


def standing(frames, mine):
    """{clan: stat} of the res=0 lists in frames, this run's clans only."""
    out = []
    for p in named(frames, "gg_list"):
        if p["res"] == 0:
            out.append({c: s for c, s in zip(p["data"], p["stats"]) if c in mine})
    return out


def journal(clan_id):
    return [(r["source"], r["afro"], r["ref"], r["char_id"])
            for r in reversed(STORE.clan_ledger_rows(clan_id, 100))]


async def main():
    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    carol = login("carol", nick("Carol"))
    dave = login("dave", nick("Dave"))
    eve = login("eve", nick("Eve"))
    for s in (alice, bob, carol, dave, eve):
        take(s)

    # --- the prices -------------------------------------------------------------
    res, got = one_ack(eve, "gg_info;det=6;", "prices")
    check("det=6: [0] founding, [1] a step down, [2] a step up -- then 0",
          only(got), [("gg_list", {"res": 6, "data": [1000, 100, 1000]}), ("cmdAck", {"res": 0})])
    check("  ..the same prices the steps charge",
          (clans.STANCE_DOWN, clans.STANCE_UP), (100, 1000))

    # --- two clans of two ----------------------------------------------------------
    wolves_name, foxes_name = "Волки %s" % RUN, "Лисы %s" % RUN
    wolves = found(alice, wolves_name)
    foxes = found(carol, foxes_name)
    join(alice, bob, 0x2)
    join(carol, dave, 0x2)
    mine = {wolves, foxes}
    for s in (alice, bob, carol, dave, eve):
        take(s)
    res, got = one_ack(bob, "gg_info;det=5;", "standings")
    check("det=5 from a member: every other clan at neutral, never his own, then 0",
          (standing(got, mine), acks(got)), ([{foxes: 0}], [0]))
    res, got = one_ack(eve, "gg_info;det=5;", "free standings")
    check("  ..from a free character: 0 and nothing", only(got), [("cmdAck", {"res": 0})])
    seen = {s.char_id for s in CLANS.visible_to(alice)}
    check("the four and the onlooker stand where they see each other",
          {bob.char_id, carol.char_id, dave.char_id, eve.char_id} <= seen, True)
    wolf_ledger0 = len(STORE.ledger(alice.char_id))

    # --- who may, and the refusals ------------------------------------------------
    res, got = one_ack(eve, "apply;number=%d;action=5;" % foxes, "free")
    check("a free character: gg_code 20, then 20", only(got),
          [("gg_code", {"res": 20}), ("cmdAck", {"res": 20})])
    res, got = one_ack(bob, "apply;number=%d;action=5;" % foxes, "no right")
    check("a member without 0x2000: gg_code 20, then 20", only(got),
          [("gg_code", {"res": 20}), ("cmdAck", {"res": 20})])
    for act in (5, 6):
        res, got = one_ack(alice, "apply;number=%d;action=%d;" % (foxes, act), "empty")
        check("the head with an empty treasury, action %d: 21 alone" % act,
              only(got), [("cmdAck", {"res": 21})])
    for bad in ("", "number=0;", "number=-1;", "number=1.5;", "number=%d;" % wolves,
                "number=16777215;", "number=%d;" % (2 ** 40), "number=@%d@;" % foxes):
        res, got = one_ack(alice, "apply;%saction=5;" % bad, "bad number")
        check("a step toward %r: 12 alone" % (bad or "no number"), only(got),
              [("cmdAck", {"res": 12})])
    top = max(c["id"] for c in STORE.clan_all())
    res, _ = one_ack(alice, "apply;number=%d;action=6;" % (top + 1000), "nobody")
    check("  ..toward a clan that is not: 12", res, 12)
    alice.combat.dead = True
    res, _ = one_ack(alice, "apply;number=%d;action=5;" % foxes, "dead")
    alice.combat.dead = False
    check("from a dead body: 20, never 3", res, 20)
    check("nothing was charged, nothing booked, nothing set",
          (STORE.clan_treasury(wolves), journal(wolves), STORE.clan_relations_of(wolves)),
          (0, [], {}))
    check("  ..and no other client heard a thing",
          [only(take(s)) for s in (bob, carol, dave, eve)], [[], [], [], []])

    # --- a step up ------------------------------------------------------------------
    STORE.clan_treasury_adjust(wolves, 1150, "admin")
    res, got = one_ack(alice, "apply;number=%d;action=5;" % foxes, "up")
    check("up: the actor's 0 FIRST, then his res=8, then the tags of theirs he sees,"
          " then the balance the step left (she holds 0x400: tell_balance)",
          shape(got), [("cmdAck", 0), ("gg_list", 8), ("fellow", carol.pid),
                       ("fellow", dave.pid), ("gg_list", 3)])
    check("  ..res=8 in full, and res=3 with what is left", named(got, "gg_list"),
          [{"res": 8, "data": [foxes], "names": [foxes_name], "stats": [1]},
           {"res": 3, "data": [150]}])
    check("  ..the tags as they were: their clan, now drawn by our peace",
          named(got, "fellow"), [{"id": carol.pid, "reg": foxes, "soc": foxes_name},
                                 {"id": dave.pid, "reg": foxes, "soc": foxes_name}])
    got = take(bob)
    check("  ..our other member, with no right of diplomacy: res=8, then the tags --"
          " and no balance, as he has no 0x400",
          shape(got), [("gg_list", 8), ("fellow", carol.pid), ("fellow", dave.pid)])
    want9 = [{"res": 9, "data": [wolves], "names": [wolves_name], "stats": [1]}]
    check("  ..each of theirs: res=9 and no tag -- their colours of us did not move",
          [only(take(s)) for s in (carol, dave)], [[("gg_list", want9[0])]] * 2)
    check("  ..the onlooker: nothing", only(take(eve)), [])
    check("  ..1 000 out of the treasury, booked 'diplomacy', ref them, by her",
          (STORE.clan_treasury(wolves), journal(wolves)[1:]),
          (150, [("diplomacy", -1000, foxes, alice.char_id)]))
    check("  ..one-sided: ours is peace, theirs still neutral",
          (STORE.clan_relation(wolves, foxes), STORE.clan_relation(foxes, wolves)), (1, 0))
    check("  ..and no purse moved", len(STORE.ledger(alice.char_id)), wolf_ledger0)

    res, got = one_ack(alice, "apply;number=%d;action=5;" % foxes, "past peace")
    check("up again at peace: 20 alone, nothing charged",
          (only(got), STORE.clan_treasury(wolves)), ([("cmdAck", {"res": 20})], 150))

    # --- steps down --------------------------------------------------------------------
    res, got = one_ack(alice, "apply;number=%d;action=6;" % foxes, "down")
    check("down from peace: 0, res=8 neutral, 100 out",
          (shape(got)[:2], named(got, "gg_list")[0]["stats"], STORE.clan_treasury(wolves)),
          ([("cmdAck", 0), ("gg_list", 8)], [0], 50))
    res, got = one_ack(alice, "apply;number=%d;action=6;" % foxes, "short")
    check("down with 50 in the treasury: 21, still neutral, the 50 kept",
          (only(got), STORE.clan_relation(wolves, foxes), STORE.clan_treasury(wolves)),
          ([("cmdAck", {"res": 21})], 0, 50))
    for s in (bob, carol, dave):
        take(s)
    STORE.clan_treasury_adjust(wolves, 1000, "admin")
    res, got = one_ack(alice, "apply;number=%d;action=6;" % foxes, "war")
    check("down to war: 0 first, res=8 with -1, then their tags, then the balance",
          (shape(got), named(got, "gg_list")[0]["stats"], named(got, "gg_list")[-1]),
          ([("cmdAck", 0), ("gg_list", 8), ("fellow", carol.pid), ("fellow", dave.pid),
            ("gg_list", 3)], [-1], {"res": 3, "data": [950]}))
    check("  ..every viewer of the war target on our side gets his fresh tag",
          [p["id"] for p in named(take(bob), "fellow")], [carol.pid, dave.pid])
    check("  ..theirs hear «изменил отношения к вашему клану на войну»",
          [[p["stats"] for p in named(take(s), "gg_list")] for s in (carol, dave)],
          [[[-1]], [[-1]]])
    res, got = one_ack(alice, "apply;number=%d;action=6;" % foxes, "past war")
    check("down again at war: 20, nothing charged",
          (res, STORE.clan_treasury(wolves)), (20, 950))
    check("the journal: 1 000 up, 100 down, 100 down, each 'diplomacy' ref them",
          [r for r in journal(wolves) if r[0] == "diplomacy"],
          [("diplomacy", -1000, foxes, alice.char_id), ("diplomacy", -100, foxes, alice.char_id),
           ("diplomacy", -100, foxes, alice.char_id)])

    # --- «Спросить» --------------------------------------------------------------------
    res, got = one_ack(dave, "apply;number=%d;action=7;" % wolves, "ask")
    check("ask from their member without rights: res=5 with our war on them, then 0",
          only(got), [("gg_list", {"res": 5, "data": [wolves], "stats": [-1]}),
                      ("cmdAck", {"res": 0})])
    res, got = one_ack(alice, "apply;number=%d;action=7;" % foxes, "ask back")
    check("  ..and ours of them: still neutral, one-sided", named(got, "gg_list")[0]["stats"], [0])
    res, got = one_ack(alice, "apply;number=%d;action=7;" % wolves, "ask self")
    check("  ..of our own clan: 12", res, 12)

    # --- their side, on its own, and I2 ------------------------------------------------
    STORE.clan_treasury_adjust(foxes, 2000, "admin")
    bob.clan_view.known.discard(foxes)
    dave.clan_view.known.discard(wolves)
    res, got = one_ack(carol, "apply;number=%d;action=5;" % wolves, "their up")
    check("they make peace with us: her 0, res=8, our tags on her screen, her balance",
          shape(got), [("cmdAck", 0), ("gg_list", 8), ("fellow", alice.pid),
                       ("fellow", bob.pid), ("gg_list", 3)])
    got = take(dave)
    check("  ..her member whose client lacks us: the full standings FIRST, then res=8 (I2)",
          (shape(got)[:2], standing(got, mine)), ([("gg_list", 0), ("gg_list", 8)], [{wolves: 1}]))
    got = take(bob)
    check("  ..our member whose client lacks them: the full standings, then res=9 --"
          " still OUR war in them", (shape(got), standing(got, mine), named(got, "gg_list")[1]),
          ([("gg_list", 0), ("gg_list", 9)], [{foxes: -1}],
           {"res": 9, "data": [foxes], "names": [foxes_name], "stats": [1]}))
    got = take(alice)
    check("  ..our head, whose client holds them: res=9 alone, no tags",
          shape(got), [("gg_list", 9)])
    check("  ..two stances, one each way", (STORE.clan_relation(wolves, foxes),
                                            STORE.clan_relation(foxes, wolves)), (-1, 1))
    alice.clan_view.known_for = None
    res, got = one_ack(carol, "apply;number=%d;action=6;" % wolves, "their down")
    check("  ..a client holding another clan's standings is given ours first",
          shape(take(alice)), [("gg_list", 0), ("gg_list", 9)])
    check("  ..their treasury paid 1 000 and 100", STORE.clan_treasury(foxes), 900)

    # --- an officer with the right ----------------------------------------------------
    res, _ = one_ack(alice, "admit;char=%d;perm=%d;post=@Посол@;" % (bob.char_id, 0x2 | 0x2000),
                     "grant diplomacy")
    check("the head grants bob the right of diplomacy", (res, CLANS.member(bob.char_id)["perm"]),
          (0, 0x2 | 0x2000))
    for s in (alice, bob, carol, dave):
        take(s)
    STORE.clan_treasury_adjust(wolves, 100, "admin")
    res, got = one_ack(bob, "apply;number=%d;action=5;" % foxes, "officer up")
    check("  ..and makes war into neutrality: his 0 first, res=8, their tags",
          shape(got), [("cmdAck", 0), ("gg_list", 8), ("fellow", carol.pid),
                       ("fellow", dave.pid)])
    check("  ..the head hears res=8 like any member, and, holding 0x400, the balance"
          " the officer's step left (he has no 0x400: none to him)",
          [(p["res"], p.get("stats", p.get("data"))) for p in named(take(alice), "gg_list")],
          [(8, [0]), (3, [STORE.clan_treasury(wolves)])])
    check("  ..booked by him", journal(wolves)[-1], ("diplomacy", -1000, foxes, bob.char_id))

    # --- the step is one transaction --------------------------------------------------
    before = (STORE.clan_treasury(wolves), journal(wolves), STORE.clan_relations_of(wolves))
    for label, args in (("a stance that moved in between",
                         (wolves, foxes, 1, 0, 100, alice.char_id, clans.R_DIPLOMACY)),
                        ("an actor no longer in the clan",
                         (wolves, foxes, 0, -1, 100, carol.char_id, 0)),
                        ("an actor without every bit asked",
                         (wolves, foxes, 0, -1, 100, bob.char_id,
                          clans.R_DIPLOMACY | clans.R_GOLD)),
                        ("a free character", (wolves, foxes, 0, -1, 100, eve.char_id, 0)),
                        ("a treasury short", (wolves, foxes, 0, 1, 10 ** 9, alice.char_id, 0)),
                        ("a clan gone", (wolves, top + 1000, 0, 1, 100, alice.char_id, 0))):
        check("Store.clan_stance_step with %s: None" % label,
              STORE.clan_stance_step(*args[:6], need=args[6]), None)
    check("  ..and not a thing written by any of them",
          (STORE.clan_treasury(wolves), journal(wolves), STORE.clan_relations_of(wolves)), before)

    # --- a clan founded, and one disbanded ---------------------------------------------
    gus = login("gus", nick("Gus"))
    take(gus)
    for s in (alice, bob, carol, dave):
        take(s)
    jackals_name = "Шакалы %s" % RUN
    give_gold(gus, clans.CREATE_GOLD)
    res, got = one_ack(gus, "head;reg=@x@;soc=@%s@;" % jackals_name, "third clan")
    jackals = CLANS.member(gus.char_id)["clan_id"]
    mine.add(jackals)
    check("a new clan's founder: the other two at neutral in his standings",
          standing(got, mine), [{wolves: 0, foxes: 0}])
    check("  ..and every member online of the others: a new res=0 with it",
          [standing(take(s), mine) for s in (alice, bob, carol, dave)],
          [[{foxes: 0, jackals: 0}]] * 2 + [[{wolves: 0, jackals: 0}]] * 2)
    run(gus, "gg_info;det=1;")
    take(gus)
    STORE.clan_treasury_adjust(jackals, 300, "admin")
    STORE.clan_treasury_adjust(wolves, 100, "admin")
    for who, text in ((alice, "apply;number=%d;action=6;" % jackals),
                      (carol, "apply;number=%d;action=6;" % jackals),
                      (gus, "apply;number=%d;action=6;" % wolves),
                      (gus, "apply;number=%d;action=6;" % foxes)):
        res, _ = one_ack(who, text, "toward jackals")
        check("a step down between the jackals and %s: 0" % who.nick, res, 0)
    rows = lambda: sorted(  # noqa: E731
        (r["clan_id"], r["other"], r["stat"]) for r in STORE.db.execute(
            "SELECT clan_id, other, stat FROM clan_relations WHERE clan_id = ? OR other = ?",
            (jackals, jackals)))
    check("  ..four rows name the jackals, both ways", len(rows()), 4)
    for s in (alice, bob, carol, dave):
        take(s)
    res, got = one_ack(gus, "apply;number=0;action=1;", "lone head leaves")
    check("the jackals' lone head leaves: disbanded, what was left paid to him",
          (res, STORE.clan(jackals), named(got, "userInfo_Player") != []), (0, None, True))
    check("  ..their relations gone both ways", rows(), [])
    check("  ..ours and theirs toward each other untouched",
          (STORE.clan_relation(wolves, foxes), STORE.clan_relation(foxes, wolves)), (0, 0))
    check("  ..and every member online of the others: a new res=0 without it",
          [standing(take(s), mine) for s in (alice, bob, carol, dave)],
          [[{foxes: 0}]] * 2 + [[{wolves: 0}]] * 2)
    res, _ = one_ack(alice, "apply;number=%d;action=5;" % jackals, "toward the gone")
    check("  ..a step toward the gone clan from a page still showing it: 12", res, 12)

    # --- kept: a new connection, a new login ---------------------------------------------
    STORE.clan_treasury_adjust(wolves, 100, "admin")
    res, _ = one_ack(alice, "apply;number=%d;action=6;" % foxes, "war again")
    STORE.db.commit()
    fresh = accounts.Store(DB)
    check("a fresh connection reads both stances as the game left them",
          (fresh.clan_relation(wolves, foxes), fresh.clan_relation(foxes, wolves)), (-1, 0))
    fresh.close()
    bob.close()
    bob = login("bob", nick("Bob"), new=False)
    got = take(bob)
    check("our member logging in again: his standings carry our war on them",
          standing(got, mine), [{foxes: -1}])
    check("  ..and are the ones his client is known to hold (I2)",
          (bob.clan_view.known_for, foxes in bob.clan_view.known), (wolves, True))

    check("no command was ever answered twice", CLANS.double_acks, [])
    for s in list(server.SESSIONS) + [alice, bob, carol, dave, eve, gus]:
        s.close()


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
print("clan diplomacy OK")
