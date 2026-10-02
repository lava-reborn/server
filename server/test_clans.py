"""Clans, the core (clans.py), driven in process where the order of frames
across several sessions is exact.

Five players and a sixth who never comes online: founding (the fee, its
ledger row, the frames in their order), the tag under a name, invitations
(every refusal code, one open invitation a character, running out), the
answer, the invitation ban, the chat of channel 2 and who hears it, rights
by rank, kicking and leaving in the client's order, the head's succession,
a lone head leaving with the treasury paid into his live purse, an admin's
disband paying an offline and an online character, a dead member's roster,
the database changed behind the game's back by the admin tool, a client
that stopped listening, and one cmdAck per command whatever happens --
never a code the client pops an alert for.

    LAVA_RES=.../lava/res python3 server/test_clans.py

Runs on Postgres too, when LAVA_DB_URL names a throwaway database: every
name is made unique per run, and nothing is dropped.
"""
import asyncio
import logging
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "clans.db")
os.environ["LAVA_DB"] = DB
# Everyone wakes in the same place, so that they see each other.
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0.4"

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import protocol  # noqa: E402
import storage  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
PG = storage.using_postgres()


def nick(base):
    return "%s%s" % (base, RUN)


LOGINS = ("alice", "bob", "carol", "dave", "eve", "zed", "oneil", "odd")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l + RUN, "secret")
_store.close()

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)
import clans  # noqa: E402
import combat  # noqa: E402

STORE = server.STORE
CLANS = server.CLANS
from testkit import check, fails  # noqa: E402


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it:
    each frame decoded, and its raw text beside it."""

    def __init__(self):
        self.frames = []
        self.raw = []
        self.closed = False

    def write(self, data):
        text = data[:-1].decode("utf-8")
        self.raw.append(text)
        self.frames.append(decode(text))

    def close(self):
        self.closed = True

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def take(sess):
    """The frames since the last take, and forget them."""
    out = sess.writer.frames[:]
    sess.writer.frames.clear()
    sess.writer.raw.clear()
    return out


def raw(sess):
    out = sess.writer.raw[:]
    sess.writer.frames.clear()
    sess.writer.raw.clear()
    return out


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def named(frames, name):
    return [p for n, p in frames if n == name]


def key(n, p):
    """What tells one frame of a clan exchange from another: the code of an
    answer or a list, the clan of a fellow."""
    if n in ("cmdAck", "gg_list", "gg_code"):
        return p.get("res")
    if n == "fellow":
        return p.get("reg")
    return None


def names(frames, keep=None):
    return [n for n, _ in frames if keep is None or n in keep]


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
    """Send one clan command: exactly one cmdAck comes, and not a code the
    client pops an alert for (clans.NEVER). Returns (res, frames)."""
    take(sess)
    run(sess, text)
    got = take(sess)
    a = acks(got)
    if len(a) != 1 or a[0] in clans.NEVER:
        fails.append("%s: acks %r for %r" % (label, a, text))
    return (a[0] if a else None), got


async def main():
    # --- the prices, with or without a character --------------------------------
    early = server.Session(Writer(), "early")
    run(early, "login;hash=@%s@;" % accounts.credential("eve" + RUN, "secret"))
    take(early)
    res, got = one_ack(early, "gg_info;det=6;", "det=6 before a character")
    check("det=6 before any character: the prices, then 0",
          only(got), [("gg_list", {"res": 6, "data": [1000, 100, 1000]}), ("cmdAck", {"res": 0})])
    for det in (1, 3, 5, 9):
        res, got = one_ack(early, "gg_info;det=%d;" % det, "no character")
        check("det=%d with no character: 20, nothing else" % det, only(got), [("cmdAck", {"res": 20})])
    early.close()

    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    eve = login("eve", nick("Eve"))
    oneil_name = "O'Neil&50%" + RUN
    odd_name = "Semi;co=lon|x@y" + RUN
    for s in (alice, bob, eve):
        take(s)
    check("a free character open to invitations is told nothing at login",
          [n for s in (alice, bob, eve) for n, _ in s.writer.frames if n == "fellow"], [])

    # --- founding ---------------------------------------------------------------
    for bad in ("ab", "A;B" + RUN[:1], "<Клан>", "%%%x", "   ", "..!!", "x" * 41, "Кот@Пёс"):
        res, _ = one_ack(alice, "head;reg=@о нас@;soc=@%s@;" % escape(bad), "bad name")
        check("a clan named %r: 5" % bad, res, 5)
    for taken in ("Аукцион", "СЕРВЕР", "Аукциoн"):
        res, _ = one_ack(alice, "head;reg=@x@;soc=@%s@;" % taken, "reserved")
        check("%r is the house's: 6" % taken, res, 6)
    res, got = one_ack(alice, "head;reg=@x@;soc=@Волки%s@;" % RUN, "no gold")
    check("a newborn without 10 G: 21, and no clan", (res, CLANS.member(alice.char_id)), (21, None))
    check("  ..no level is asked for: a level-0 character is refused for the gold alone",
          alice.character().level, 0)
    give_gold(alice, 1500)
    ledger0 = len(STORE.ledger(alice.char_id))
    res, got = one_ack(alice, "head;reg=@о нас; и всё@;soc=@  Волки   %s @;" % RUN, "found")
    wolves = CLANS.member(alice.char_id)["clan_id"] if CLANS.member(alice.char_id) else None
    wolves_name = "Волки %s" % RUN
    check("founded: the purse, fellow id=0 with the clan and 65535, the standings, then 0",
          [(n, key(n, p)) for n, p in only(got)],
          [("userInfo_Player", None), ("fellow", wolves), ("gg_list", 0), ("cmdAck", 0)])
    check("  ..the fellow in full", named(got, "fellow"),
          [{"id": 0, "reg": wolves, "soc": wolves_name, "post": "", "char": alice.char_id,
            "perm": 65535, "stand": 0}])
    check("  ..the purse the client is shown is 10 G lighter",
          (named(got, "userInfo_Player")[0]["gold"], alice.character().gold,
           STORE.money(alice.char_id)[1]), (500, 500, 500))
    led = STORE.ledger(alice.char_id)[ledger0:]
    check("  ..and the fee is booked clan_create, ref the clan, once",
          [(r["source"], r["ref"], r["afro"], r["gold"]) for r in led],
          [("clan_create", wolves, 0, -1000)])
    check("  ..the name stored trimmed, the description too",
          (STORE.clan(wolves)["name"], STORE.clan(wolves)["descr"], STORE.clan(wolves)["head"]),
          (wolves_name, "о нас; и всё", alice.char_id))
    give_gold(bob, 5000)
    res, _ = one_ack(bob, "head;reg=@x@;soc=@ВОЛКИ  %s@;" % RUN, "taken")
    check("the same name in other letters and spacing: 6", res, 6)
    res, _ = one_ack(bob, "head;reg=@x@;soc=@BОЛKИ %s@;" % RUN, "lookalike")
    check("  ..and with Latin lookalikes in it: 6", res, 6)
    res, _ = one_ack(alice, "head;reg=@x@;soc=@Другие %s@;" % RUN, "twice")
    check("a member founds nothing more: 20", res, 20)
    check("  ..and pays nothing", alice.character().gold, 500)

    # --- the roster, and the deaf check ----------------------------------------------
    res, got = one_ack(alice, "gg_info;det=1;", "roster")
    roster = named(got, "gg_list")[0]
    check("det=1: the roster as res=1, then 0",
          (roster["res"], roster["data"], roster["names"], roster["posts"], roster["perms"],
           roster["stats"]), (1, [alice.char_id], [nick("Alice")], [""], [65535], [1]))
    check("  ..the date is the login's, in UTC", len(roster["dates"][0]), 19)
    await asyncio.sleep(0.6)
    check("a client that asked for its roster is not told to reload",
          [p for n, p in take(alice) if n == "userMsg"], [])

    # --- the tag under a name ------------------------------------------------------------
    take(bob)
    run(bob, "getInfo;id=%d;" % alice.pid)
    got = take(bob)
    check("getInfo about a member: userInfo_Player, usrUp, then his clan",
          [(n, p.get("id")) for n, p in got],
          [("userInfo_Player", alice.pid), ("usrUp", alice.pid), ("fellow", alice.pid)])
    check("  ..reg and the name", named(got, "fellow")[0], {"id": alice.pid, "reg": wolves,
                                                            "soc": wolves_name})
    run(alice, "getInfo;id=%d;" % eve.pid)
    check("getInfo about a free character: no fellow at all",
          names(take(alice)), ["userInfo_Player", "usrUp"])

    # A second clan appears in the first one's standings.
    dave = login("dave", nick("Dave"))
    take(dave)
    give_gold(dave, 1000)
    take(alice)
    res, got = one_ack(dave, "head;reg=@x@;soc=@Шакалы %s@;" % RUN, "second clan")
    jackals = CLANS.member(dave.char_id)["clan_id"]
    check("a second clan founded with exactly 10 G", (res, dave.character().gold), (0, 0))
    check("  ..its standings list the first one, at neutral",
          [(p["data"], p["names"], p["stats"]) for p in named(got, "gg_list")],
          [([wolves], [wolves_name], [0])])
    got = take(alice)
    check("  ..and the first clan's member online hears of it: res=0 with it",
          [(p["res"], jackals in p["data"]) for p in named(got, "gg_list")], [(0, True)])
    check("  ..and sees the founder's tag, standing in the same room",
          [p for p in named(got, "fellow") if p["id"] == dave.pid],
          [{"id": dave.pid, "reg": jackals, "soc": "Шакалы %s" % RUN}])
    run(dave, "gg_info;det=1;")
    take(dave)

    # --- invitations --------------------------------------------------------------------
    carol = login("carol", nick("Carol"))
    oneil = login("oneil", oneil_name)
    odd = login("odd", odd_name)
    zed = login("zed", nick("Zed"))
    zed.close()
    for s in (alice, bob, carol, dave, eve, oneil, odd):
        take(s)
    res, got = one_ack(bob, "admit;char=@%s@;perm=2;post=@x@;" % nick("Carol"), "free inviter")
    check("a free character invites nobody: gg_code 20, then 20",
          only(got), [("gg_code", {"res": 20}), ("cmdAck", {"res": 20})])
    for who, want, why in (("", 30, "an empty nick"), ("Никто" + RUN, 30, "a nick nobody has"),
                           (nick("Dave"), 28, "a member of another clan"),
                           (nick("Zed"), 22, "a character not in the game"),
                           (nick("Alice"), 28, "the inviter himself")):
        res, got = one_ack(alice, "admit;char=@%s@;perm=2;post=@x@;" % escape(who), why)
        check("invite %s: %d" % (why, want), res, want)
    carol.combat.dead = True
    res, _ = one_ack(alice, "admit;char=@%s@;perm=2;post=@@;" % nick("Carol"), "dead")
    check("invite a dead character, who could never answer: 22", res, 22)
    carol.combat.dead = False
    take(eve)
    res, got = one_ack(eve, "apply;number=0;action=0;", "ban on")
    check("the invitation ban on: 0, then fellow reg=16777215",
          only(got), [("cmdAck", {"res": 0}), ("fellow", {"id": 0, "reg": 16777215})])
    check("  ..kept in the row", STORE.character(eve.char_id)["clan_no_invites"], 1)
    res, got = one_ack(alice, "admit;char=@%s@;perm=2;post=@@;" % nick("Eve"), "banned")
    check("invite a character who forbids it: 29, and the inviter is told why in chat",
          (res, [p["entry"] for p in named(got, "userMsg")]),
          (29, ["%s не принимает приглашений в кланы" % nick("Eve")]))
    check("  ..and the target hears nothing", only(take(eve)), [])
    run(eve, "apply;number=0;action=0;")
    check("the ban off again: 0, then fellow reg=0",
          only(take(eve)), [("cmdAck", {"res": 0}), ("fellow", {"id": 0, "reg": 0})])

    # Alice, the head (rank 4), asks for chat, inviting, kicking and the
    # head's own bit: the last is never granted.
    res, got = one_ack(alice, "admit;char=@%s@;perm=%d;post=@Разведчик; <1>@;"
                       % (nick("Bob"), 0x8000 | 0x100 | 0x40 | 0x2 | 0x1), "invite Bob")
    check("invite Bob: 0 to the inviter", res, 0)
    inv = named(take(bob), "invite")
    check("  ..Bob sees who, into which clan, and the post cleaned of ; and < >",
          inv, [{"rec": nick("Alice"), "soc": wolves_name, "pos": "Разведчик 1"}])
    res, _ = one_ack(dave, "admit;char=@%s@;perm=2;post=@@;" % nick("Bob"), "second invite")
    check("another clan invites Bob while he has one open: 29", res, 29)
    res, _ = one_ack(alice, "admit;char=@%s@;perm=%d;post=@Разведчик@;"
                     % (nick("Bob"), 0x8000 | 0x100 | 0x40 | 0x2 | 0x1), "again")
    check("the same clan asking again: 0, and the popup comes again",
          (res, len(named(take(bob), "invite"))), (0, 1))
    res, _ = one_ack(bob, "head;reg=@x@;soc=@Бобры %s@;" % RUN, "found over an invitation")
    check("founding over an invitation still on its way: 20", res, 20)

    # --- the answer ---------------------------------------------------------------------
    take(alice)
    res, got = one_ack(bob, "apply;number=0;action=2;", "accept")
    bob_perm = 0x100 | 0x40 | 0x2 | 0x1
    check("Bob accepts: fellow with the clan, the standings, then 0",
          [(n, key(n, p)) for n, p in only(got)],
          [("fellow", wolves), ("gg_list", 0), ("cmdAck", 0)])
    check("  ..his rights: what the head may grant of what was asked, never 0x8000",
          named(got, "fellow")[0], {"id": 0, "reg": wolves, "soc": wolves_name,
                                    "post": "Разведчик", "char": bob.char_id,
                                    "perm": bob_perm, "stand": 0})
    check("  ..the newcomer is never sent act=1 about himself", named(got, "gg_struct"), [])
    got = take(alice)
    act1 = named(got, "gg_struct")
    check("the roster holder hears act=1 with his name, post, date and rights",
          [(p["id"], p["act"], p["name"], p["post"], p["perm"], len(p["date"])) for p in act1],
          [(bob.char_id, 1, nick("Bob"), "Разведчик", bob_perm, 19)])
    check("  ..and sees his tag", [p for p in named(got, "fellow") if p["id"] == bob.pid],
          [{"id": bob.pid, "reg": wolves, "soc": wolves_name}])
    check("the invitation is gone with the answer", CLANS.invites.get(bob.char_id), None)
    run(bob, "gg_info;det=1;")
    take(bob)
    res, _ = one_ack(bob, "apply;number=0;action=2;", "accept twice")
    check("a second yes: 12, the invitation is no more", res, 12)
    res, _ = one_ack(dave, "admit;char=@%s@;perm=2;post=@@;" % nick("Bob"), "member now")
    check("Bob is in a clan now: 28 to others", res, 28)

    # Declining, and an invitation that ran out.
    res, _ = one_ack(alice, "admit;char=@%s@;perm=0;post=@@;" % nick("Eve"), "invite Eve")
    res, got = one_ack(eve, "apply;number=0;action=1;", "decline")
    check("Eve declines: 0, and she is in no clan", (res, CLANS.member(eve.char_id)), (0, None))
    res, _ = one_ack(eve, "apply;number=0;action=2;", "accept after declining")
    check("  ..a yes after the no: 12", res, 12)
    one_ack(alice, "admit;char=@%s@;perm=0;post=@@;" % nick("Eve"), "invite Eve again")
    CLANS.invites[eve.char_id] = CLANS.invites[eve.char_id]._replace(
        at=time.time() - clans.INVITE_TTL - 1)
    res, _ = one_ack(eve, "apply;number=0;action=2;", "late")
    check("a yes after five minutes: 12, and no clan", (res, CLANS.member(eve.char_id)), (12, None))
    one_ack(dave, "admit;char=@%s@;perm=0;post=@@;" % nick("Eve"), "old invitation")
    CLANS.invites[eve.char_id] = CLANS.invites[eve.char_id]._replace(
        at=time.time() - clans.INVITE_RACE - 1)
    give_gold(eve, 1000)
    res, _ = one_ack(eve, "head;reg=@x@;soc=@Ежи %s@;" % RUN, "found over an old invitation")
    check("an invitation older than a few seconds, the player founding all the same: it was"
          " never shown, it goes, and the clan is founded", (res, eve.char_id in CLANS.invites),
          (0, False))
    hedgehogs = CLANS.member(eve.char_id)["clan_id"]
    run(eve, "gg_info;det=1;")

    # Carol and O'Neil join; Carol by a recruiter who can grant nothing.
    for s in (alice, bob, dave, eve):
        take(s)
    res, _ = one_ack(alice, "admit;char=@%s@;perm=%d;post=@@;" % (escape(oneil_name), 0x2),
                     "invite O'Neil")
    run(oneil, "apply;number=0;action=2;")
    run(oneil, "gg_info;det=1;")
    take(oneil)
    res, _ = one_ack(bob, "admit;char=@%s@;perm=%d;post=@Новобранец@;" % (nick("Carol"), 0x400),
                     "a rank-2 inviter")
    check("an officer invites (0x40): 0", res, 0)
    run(carol, "apply;number=0;action=2;")
    check("  ..what he may not grant is dropped: 0x400 asked, nothing given but the base",
          CLANS.member(carol.char_id)["perm"], 0)
    run(carol, "gg_info;det=1;")
    take(carol)

    # --- the lists go raw ------------------------------------------------------------------
    take(alice)
    run(alice, "gg_info;det=1;")
    lines = [t for t in raw(alice) if t.startswith("gg_list;")]
    check("the roster's names arrive as they are, not %-escaped: O'Neil&50% whole",
          ("@%s@" % oneil_name) in lines[0] and "%27" not in lines[0] and "%26" not in lines[0],
          True)
    res, _ = one_ack(alice, "admit;char=@%s@;perm=2;post=@@;" % escape(odd_name), "odd name")
    run(odd, "apply;number=0;action=2;")
    take(odd)
    run(alice, "gg_info;det=1;")
    line = [t for t in raw(alice) if t.startswith("gg_list;")][0]
    odd_shown = "Semi,co═lon¦x©y" + RUN
    check("a name holding ; = | @ is shown with lookalikes in the list, and the frame parses",
          ("@%s@" % odd_shown in line, decode(line)[1]["names"][-1]), (True, odd_shown))
    check("  ..which the act=1 about him used too, so the two agree",
          clans.list_safe(odd_name), odd_shown)
    try:
        protocol.frame("gg_list", names=protocol.RawList(["a;b"]))
        refused = False
    except ValueError:
        refused = True
    check("a raw list with an unsafe item is refused, never sent", refused, True)

    # --- the clan's channel -------------------------------------------------------------------
    for s in (alice, bob, carol, dave, oneil, odd):
        take(s)
    run(bob, "userMsg;entry=@свои, приём@;group=2;")
    check("Bob in channel 2: his own ack only", acks(take(bob)), [0])
    heard = {s.nick: named(take(s), "userMsg") for s in (alice, carol, dave, oneil, odd)}
    line = {"group": 2, "player": bob.char_id, "nick": nick("Bob"), "entry": "свои, приём"}
    check("  ..heard by the members holding 0x2, with player= his char id",
          (heard[nick("Alice")], heard[oneil_name], heard[odd_name]), ([line], [line], [line]))
    check("  ..not by the member without the right, nor by another clan",
          (heard[nick("Carol")], heard[nick("Dave")]), ([], []))
    run(carol, "userMsg;entry=@меня слышно?@;group=2;")
    check("the member without the right speaks into nothing",
          [named(take(s), "userMsg") for s in (alice, bob, oneil)], [[], [], []])

    # --- rights ------------------------------------------------------------------------------
    for s in (alice, bob, carol, oneil, odd):
        take(s)
    res, got = one_ack(alice, "admit;char=%d;perm=%d;post=@Офицер@;"
                       % (bob.char_id, 0x100 | 0x200 | 0x40 | 0x2 | 0x1), "head sets Bob")
    check("the head makes Bob an officer: act=3 to the roster holders, then 0",
          (named(got, "gg_struct"), acks(got)),
          ([{"id": bob.char_id, "act": 3, "post": "Офицер", "perm": 0x343}], [0]))
    got = take(bob)
    check("  ..Bob hears act=3 and then his own fellow with the new rights -- before the"
          " head's ack, which went to the head alone",
          [(n, p.get("act"), p.get("perm")) for n, p in only(got)],
          [("gg_struct", 3, 0x343), ("fellow", None, 0x343)])
    check("  ..a member without the roster hears nothing of it",
          named(take(odd), "gg_struct"), [])
    take(carol)
    res, got = one_ack(bob, "admit;char=%d;perm=%d;post=@Кладовщик@;" % (carol.char_id, 0x4 | 0x2),
                       "officer grants")
    check("an officer (rank 2) grants chat and storage to a rank-0: 0", res, 0)
    check("  ..and Carol has them", CLANS.member(carol.char_id)["perm"], 0x6)
    for perm, why in ((0x6 | 0x400, "the treasury, past an officer's grant"),
                      (0x6 | 0x8000, "the head's bit")):
        res, got = one_ack(bob, "admit;char=%d;perm=%d;post=@@;" % (carol.char_id, perm), why)
        check("officer grants %s: gg_code 20, then 20" % why, only(got),
              [("gg_code", {"res": 20}), ("cmdAck", {"res": 20})])
    res, _ = one_ack(bob, "admit;char=%d;perm=2;post=@@;" % alice.char_id, "edit the head")
    check("an officer edits the head: 20", res, 20)
    res, _ = one_ack(bob, "admit;char=%d;perm=%d;post=@Сам@;" % (bob.char_id, 0x343), "self")
    check("an officer edits himself: 20 -- only the head does", res, 20)
    res, _ = one_ack(carol, "admit;char=%d;perm=2;post=@@;" % oneil.char_id, "rank 0 edits")
    check("a member without 0x200 or 0x40 edits nobody: 20", res, 20)
    res, _ = one_ack(alice, "admit;char=%d;perm=2;post=@@;" % dave.char_id, "another clan")
    check("the head edits a member of another clan: 12", res, 12)
    # A recruiter (0x40 alone, rank 1) resends a rank-0's own bits from the
    # disabled boxes, with a new post: nothing changed he may not grant.
    STORE.clan_member_update(oneil.char_id, wolves, perm=0x40 | 0x2)
    res, _ = one_ack(oneil, "admit;char=%d;perm=%d;post=@Связной@;"
                     % (odd.char_id, CLANS.member(odd.char_id)["perm"]), "rank 1 resends")
    check("a recruiter resending a rank-0's own rights with a new post: 0",
          (res, CLANS.member(odd.char_id)["post"]), (0, "Связной"))
    res, _ = one_ack(oneil, "admit;char=%d;perm=0;post=@@;" % odd.char_id, "rank 1 changes")
    check("  ..but taking a right away: 20", res, 20)
    res, got = one_ack(alice, "admit;char=%d;perm=65535;post=@Глава@;" % alice.char_id, "self")
    check("the head's own post: 0, rights still 65535 whatever the page sent",
          (res, CLANS.member(alice.char_id)["post"], CLANS.member(alice.char_id)["perm"]),
          (0, "Глава", 65535))
    check("  ..his own fellow tells him the post", [p["post"] for p in named(got, "fellow")],
          ["Глава"])
    res, _ = one_ack(alice, "admit;perm=2;post=@@;", "no char")
    check("admit with no char at all: 12, never a guess", res, 12)

    # --- kicking ----------------------------------------------------------------------------
    for s in (alice, bob, carol, oneil, odd, dave):
        take(s)
    res, got = one_ack(bob, "apply;number=%d;action=1;" % alice.char_id, "kick the head")
    check("kick the head: gg_code 20, then 20", only(got),
          [("gg_code", {"res": 20}), ("cmdAck", {"res": 20})])
    res, _ = one_ack(bob, "apply;number=%d;action=1;" % bob.char_id, "kick oneself")
    check("kick oneself: 20", res, 20)
    res, _ = one_ack(carol, "apply;number=%d;action=1;" % odd.char_id, "no 0x100")
    check("kick without 0x100: 20", res, 20)
    res, _ = one_ack(bob, "apply;number=%d;action=1;" % dave.char_id, "not ours")
    check("kick a member of another clan: 12", res, 12)
    res, _ = one_ack(bob, "apply;action=1;", "no number")
    check("a kick with no number is no leave: 12, and Bob stays",
          (res, CLANS.member(bob.char_id)["clan_id"]), (12, wolves))
    res, _ = one_ack(bob, "apply;number=1.5;action=1;", "float number")
    check("  ..nor with a fraction: 12", res, 12)
    take(alice)
    take(carol)
    res, got = one_ack(bob, "apply;number=%d;action=1;" % carol.char_id, "kick Carol")
    check("Bob kicks Carol: act=2 to him BEFORE his 0, then -- standing beside her -- her tag"
          " gone", [(n, p.get("act", p.get("res", p.get("reg")))) for n, p in only(got)],
          [("gg_struct", 2), ("cmdAck", 0), ("fellow", 0)])
    check("  ..the others holding the roster hear act=2",
          [(p["id"], p["act"]) for p in named(take(alice), "gg_struct")], [(carol.char_id, 2)])
    check("  ..a member whose client never asked for the roster hears no act=2 (I1: its"
          " splice(null) would take out the first row)", named(take(odd), "gg_struct"), [])
    got = take(carol)
    check("  ..Carol is put out: fellow id=0 reg=0, then her standings emptied, and no act=2",
          only(got), [("fellow", {"id": 0, "reg": 0}),
                      ("gg_list", {"res": 0, "data": [], "names": [], "stats": []})])
    check("  ..the others in the room see her tag go",
          [p for p in named(take(dave), "fellow") if p["id"] == carol.pid],
          [{"id": carol.pid, "reg": 0, "soc": ""}])
    check("  ..and she is in no clan", CLANS.member(carol.char_id), None)
    res, got = one_ack(carol, "gg_info;det=1;", "stale det=1")
    check("her client, sticky, asks for the roster: 0 and nothing, never 9", only(got),
          [("cmdAck", {"res": 0})])

    # --- leaving ------------------------------------------------------------------------------
    take(alice)
    res, got = one_ack(odd, "apply;number=0;action=1;", "leave")
    check("leaving: 0 FIRST, then fellow reg=0, then the emptied standings",
          [(n, key(n, p)) for n, p in only(got)],
          [("cmdAck", 0), ("fellow", 0), ("gg_list", 0)])
    check("  ..the roster holders hear act=2",
          [(p["id"], p["act"]) for p in named(take(alice), "gg_struct")], [(odd.char_id, 2)])

    # --- the head goes: succession ----------------------------------------------------------
    # Wolves: Alice (head), Bob (0x343, rank 2), O'Neil (0x42, rank 1).
    for s in (alice, bob, oneil):
        take(s)
    res, got = one_ack(alice, "apply;number=0;action=1;", "head leaves")
    check("the head leaves: 0, then put out", [(n, key(n, p))
                                              for n, p in only(got)],
          [("cmdAck", 0), ("fellow", 0), ("gg_list", 0)])
    check("  ..the clan goes to the highest rank, Bob, with 65535",
          (STORE.clan(wolves)["head"], CLANS.member(bob.char_id)["perm"]), (bob.char_id, 65535))
    got = take(bob)
    check("  ..Bob hears act=2 for Alice, act=3 for himself and his new rights",
          [(n, p.get("id"), p.get("act"), p.get("perm")) for n, p in only(got)
           if n in ("gg_struct", "fellow") and p.get("id") in (0, alice.char_id, bob.char_id)],
          [("gg_struct", alice.char_id, 2, None), ("gg_struct", bob.char_id, 3, 65535),
           ("fellow", 0, None, 65535)])
    check("  ..O'Neil the same rows", [(p["id"], p["act"]) for p in named(take(oneil), "gg_struct")],
          [(alice.char_id, 2), (bob.char_id, 3)])

    # --- a lone head leaves: disbanded, the treasury into his live purse --------------------
    STORE.clan_treasury_adjust(jackals, 777, "admin")
    dave_afro = dave.character().afro
    for s in (bob, eve, dave):
        take(s)
    res, got = one_ack(dave, "apply;number=0;action=1;", "last leaves")
    check("the last member leaves: the purse pushed BEFORE the 0, then put out",
          [(n, key(n, p)) for n, p in only(got)],
          [("userInfo_Player", None), ("cmdAck", 0), ("fellow", 0), ("gg_list", 0)])
    check("  ..777 afro more, in the frame, in memory and in the row",
          (named(got, "userInfo_Player")[0]["afro"], dave.character().afro,
           STORE.money(dave.char_id)[0]), (dave_afro + 777,) * 3)
    check("  ..booked clan_disband, ref the clan, in both journals",
          ([(r["source"], r["ref"], r["afro"]) for r in STORE.ledger(dave.char_id)][-1:],
           [(r["source"], r["afro"]) for r in STORE.db.execute(
               "SELECT * FROM clan_ledger WHERE clan_id = ? ORDER BY id", (jackals,))]),
          ([("clan_disband", jackals, 777)], [("admin", 777), ("disband", -777)]))
    check("  ..and the clan is gone", (STORE.clan(jackals), CLANS.member(dave.char_id)),
          (None, None))
    check("  ..the other clans' members online get their standings without it",
          [(p["res"], jackals in p["data"]) for s in (bob, eve) for p in named(take(s), "gg_list")],
          [(0, False), (0, False)])
    dave.character().save(STORE)
    check("  ..and his save at logout keeps it", STORE.money(dave.char_id)[0], dave_afro + 777)
    give_gold(dave, 1000)
    res, _ = one_ack(dave, "head;reg=@x@;soc=@Шакалы %s@;" % RUN, "the name is free")
    check("the name is free again, under a new id", (res, CLANS.member(dave.char_id)["clan_id"]
                                                     > jackals), (0, True))
    jackals2 = CLANS.member(dave.char_id)["clan_id"]
    run(dave, "gg_info;det=1;")

    # --- the admin's disband: an offline head, then an online one ---------------------------
    STORE.clan_treasury_adjust(hedgehogs, 300, "admin")
    eve_afro = eve.character().afro
    take(eve)
    paid = CLANS.disband(hedgehogs)
    check("disband a clan whose head plays: 300 into his live purse, pushed",
          (paid, eve.character().afro, STORE.money(eve.char_id)[0],
           [n for n, _ in only(take(eve))]),
          (300, eve_afro + 300, eve_afro + 300, ["userInfo_Player", "fellow", "gg_list"]))
    STORE.clan_treasury_adjust(jackals2, 50, "admin")
    dave_id = dave.char_id
    dave.close()
    afro_before = STORE.money(dave_id)[0]
    check("disband a clan whose head is offline: 50 into the row",
          (CLANS.disband(jackals2), STORE.money(dave_id)[0]), (50, afro_before + 50))
    check("  ..booked", [(r["source"], r["afro"]) for r in STORE.ledger(dave_id)][-1:],
          [("clan_disband", 50)])
    check("a clan that is no more is not disbanded twice", CLANS.disband(jackals2), None)

    # --- a dead member logs in: his roster, never «Сервер не отвечает» ------------------------
    oneil_id = oneil.char_id
    oneil.close()
    STORE.save_character_state(oneil_id, death=1)
    back = login("oneil", oneil_name, new=False)
    check("the dead member is dead to the server", back.combat.dead, True)
    got = take(back)
    check("  ..his login fellow says his clan", [p["reg"] for p in named(got, "fellow")
                                                 if p["id"] == 0], [wolves])
    res, got = one_ack(back, "gg_info;det=1;", "dead det=1")
    check("  ..and his client's own det=1 gets the roster and 0, not 3",
          [(n, key(n, p)) for n, p in only(got)], [("gg_list", 1), ("cmdAck", 0)])
    res, got = one_ack(back, "gg_info;det=5;", "dead det=5")
    check("  ..det=5 the standings and 0", [(n, key(n, p)) for n, p in only(got)],
          [("gg_list", 0), ("cmdAck", 0)])
    for text in ("apply;number=0;action=1;", "head;reg=@x@;soc=@Мертвецы@;",
                 "admit;char=@x@;perm=0;post=@@;"):
        res, _ = one_ack(back, text, "dead action")
        check("a clan action from a dead body: 20, not 3 (%s)" % text.split(";")[0], res, 20)
    check("  ..and the dead filter's table says so for all three",
          {c: combat.DEAD_REFUSAL[c] for c in ("head", "admit", "apply")},
          {c: clans.NOT_ALLOWED for c in ("head", "admit", "apply")})
    check("  ..and he is still a member", CLANS.member(back.char_id)["clan_id"], wolves)
    back.combat.dead = False
    STORE.save_character_state(oneil_id, death=0)

    # --- a client that stopped listening ------------------------------------------------------
    take(back)
    await asyncio.sleep(0.6)
    check("a member's client that asked is left alone", named(take(back), "userMsg"), [])
    # The line is one the server says by itself (Session.say): out of the
    # chat while the server's own lines are off, as they are on the served
    # game, and in it when they are on.
    deaf = login("bob", nick("Bob"), new=False)
    take(deaf)
    await asyncio.sleep(0.6)
    check("one that never asks for its roster, with the server's lines off: nothing in the chat",
          named(take(deaf), "userMsg"), [])
    server.SERVER_CHAT = True
    try:
        deaf = login("bob", nick("Bob"), new=False)
        take(deaf)
        await asyncio.sleep(0.6)
        check("  ..with them on: told once to start the game again",
              [p["entry"] for p in named(take(deaf), "userMsg")], [clans.DEAF_LINE])
        run(deaf, "lenter;accept=1;")
        await asyncio.sleep(0.6)
        check("  ..once", named(take(deaf), "userMsg"), [])
    finally:
        server.SERVER_CHAT = False
    bob = deaf

    # --- the database changed behind the game's back -------------------------------------------
    # The admin tool, another process, deletes the head: the clan passes on
    # in the database, and the game, which caches nothing, follows at once.
    run(back, "gg_info;det=1;")
    take(back)
    # A read in Postgres holds its table until the commit, and the other
    # Store's migrate would wait on it for ever: the game commits every
    # second (publish_online), this test has to say so itself.
    STORE.db.commit()
    other = accounts.Store(DB)
    STORE.clan_member_update(oneil_id, wolves, perm=0x100 | 0x40 | 0x2)
    with other.db:
        out = accounts.clan_hand_over(other.db, bob.char_id)
        other.db.execute("DELETE FROM clan_members WHERE char_id = ?", (bob.char_id,))
    other.close()
    check("the tool hands the clan over to the one left", out, (wolves, oneil_id, 0))
    check("  ..and the game takes the new head for the head at once",
          (CLANS.member(oneil_id)["perm"], CLANS.member(bob.char_id)), (65535, None))
    res, _ = one_ack(bob, "admit;char=%d;perm=2;post=@@;" % oneil_id, "stale head")
    check("  ..the old head, still in the game, can do nothing: 20", res, 20)
    run(bob, "userMsg;entry=@я глава@;group=2;")
    check("  ..nor speak in the channel", named(take(back), "userMsg"), [])

    # --- the later packages, as the core hands to them --------------------------------------
    take(back)
    # (The treasury is built: test_clan_treasury.py. Here only that the head
    # is answered by it, in the frames' order.)
    res, got = one_ack(back, "gg_info;det=3;", "treasury")
    check("the treasury's balance to the head: res=3, then 0",
          [(n, key(n, p)) for n, p in only(got)], [("gg_list", 3), ("cmdAck", 0)])
    res, got = one_ack(back, "apply;number=-1;action=3;", "treasury")
    check("  ..taking out more than it holds: 21, and no purse pushed",
          [(n, key(n, p)) for n, p in only(got)], [("cmdAck", 21)])
    give_gold(dave, 0)
    dave = login("dave", nick("Dave"), new=False)
    give_gold(dave, 1000)
    run(dave, "head;reg=@x@;soc=@Лисы %s@;" % RUN)
    foxes = CLANS.member(dave.char_id)["clan_id"]
    STORE.clan_relation_set(foxes, wolves, -1)
    back.clan_view.known.discard(foxes)
    take(back)
    res, got = one_ack(back, "apply;number=%d;action=7;" % foxes, "ask")
    check("ask their stance: the standings first where the client lacks them (I2), then"
          " res=5 with it, then 0", [(n, p.get("res"), p.get("stats")) for n, p in only(got)],
          [("gg_list", 0, [0]), ("gg_list", 5, [-1]), ("cmdAck", 0, None)])
    res, _ = one_ack(back, "apply;number=%d;action=7;" % 999999, "ask nobody")
    check("  ..about a clan that is no more: 12", res, 12)
    res, _ = one_ack(back, "apply;number=%d;action=5;" % foxes, "diplomacy")
    check("a change of stance with nothing in the treasury: 21 (test_clan_diplomacy.py has"
          " the rest)", (res, STORE.clan_relation(wolves, foxes)), (21, 0))
    # (What each op does is test_clan_admin.py's.)
    check("the admin's clan action is taken before any character is asked for",
          server.apply_admin_action({"kind": "clan", "char_id": None, "account_id": None,
                                     "args_json": '{"op": "disband", "clan": %d}' % foxes,
                                     "admin": "x"}).startswith("клан «Лисы %s» распущен" % RUN),
          True)

    # --- persistence, and an id handed out again -------------------------------------------------
    STORE.db.commit()
    fresh = accounts.Store(DB)
    check("a fresh connection reads the clan as the game left it: its head, its members",
          (fresh.clan(wolves)["head"], fresh.clan_member_perms(wolves)),
          (oneil_id, [(oneil_id, 65535)]))
    fresh.close()
    if not PG:
        # SQLite gives the last deleted id to the next character: nothing
        # of the clan may come with it.
        acc = STORE.db.execute("SELECT account_id FROM characters WHERE id = ?",
                               (oneil_id,)).fetchone()["account_id"]
        top = STORE.db.execute("SELECT MAX(id) m FROM characters").fetchone()["m"]
        STORE.db.execute("INSERT INTO clan_members (char_id, clan_id, perm, post, joined_at)"
                         " VALUES (?, ?, 65535, '', 0)", (top + 1, wolves))
        STORE.db.commit()
        new_id, _slot = STORE.create_character(acc, "Новичок" + RUN, 0, "1")
        check("a new character under an id a member row still names: no clan",
              (new_id, CLANS.member(new_id), STORE.db.execute(
                  "SELECT COUNT(*) c FROM clan_members WHERE char_id = ?", (new_id,)
              ).fetchone()["c"]), (top + 1, None, 0))

    # --- one cmdAck per command, whatever comes -----------------------------------------------
    forms = ["gg_info;det=%d;" % d for d in range(0, 9)] + ["gg_info;id=0;", "gg_info;det=@x@;"]
    forms += ["apply;number=%s;action=%d;" % (n, a) for a in range(-1, 9)
              for n in ("0", "1", "-5", "2.5", "999999")]
    forms += ["apply;action=%d;" % a for a in range(0, 8)] + ["apply;number=0;"]
    forms += ["admit;char=@%s@;perm=2;post=@@;" % nick("Carol"), "admit;char=0;perm=2;post=@@;",
              "admit;char=2.5;perm=2;post=@@;", "admit;char=|1|2|;perm=0;",
              "head;reg=@x@;soc=@@;", "head;soc=@Кто-то там@;", "head;"]
    counts = []
    for text in forms:
        for s in (back, carol):
            res, _ = one_ack(s, text, "form")
            counts.append(res is not None)
    check("every form of the four commands from a member and from a free character: exactly"
          " one cmdAck each, none the client alerts on", (all(counts), len(counts)),
          (True, 2 * len(forms)))
    original = STORE.clan_member

    def broken(char_id):
        raise RuntimeError("a bug in the middle of a handler")

    STORE.clan_member = broken
    try:
        for text in ("gg_info;det=1;", "apply;number=0;action=1;", "head;reg=@x@;soc=@Кот %s@;"
                     % RUN, "admit;char=@x@;perm=0;post=@@;"):
            res, _ = one_ack(back, text, "raising")
            check("a handler that raises is still answered once, with 20 (%s)"
                  % text.split(";")[0], res, 20)
    finally:
        STORE.clan_member = original
    check("no command was ever answered twice", CLANS.double_acks, [])
    check("a clan frame that cannot be read is refused 20, anything else 3",
          [server.bad_frame_res(b) for b in (b"head;soc=@x", b"apply;number=", b"ah_op;x")],
          [20, 20, 3])

    for s in list(server.SESSIONS) + [alice, bob, carol, dave, eve, back, odd]:
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
print("clans OK")
