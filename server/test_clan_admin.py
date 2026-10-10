"""The admin's clan tools (clan_admin.py), driven in process through real
admin_actions rows -- queued as the panel and tools/admin_account.py queue
them, carried out as the game's queue carries them out -- where what each
member's client is sent can be told exactly.

Two clans, a member of each online and one offline: every op with its
result text and every refusal; the treasury's 'admin' rows in clan_ledger
(ref: the order) and the balance pushed to those who may see it; a rename's
rules and the other clan's standings renewed; the lead handed to a member
offline and back to one online, 65535 moving and both told; a kick of a
member online (put out on the spot) and of one offline (who finds himself
free at his login); a disband paying a character who plays -- into his live
purse, pushed, booked in both journals -- and one who does not, the name
free again. Then the tool: its read-only listing, and an order it queues
while no game is running, carried out when the queue is next read.

    LAVA_RES=.../lava/res python3 server/test_clan_admin.py

Runs on Postgres too, when LAVA_DB_URL names a throwaway database: every
name is unique per run, and nothing is dropped. The panel and the tool
against a running server over sockets: test_clan_admin_wire.py. The
warehouses' hold and release (holdings.py): test_holdings.py.
"""
import asyncio
import contextlib
import io
import json
import logging
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(tempfile.mkdtemp(), "clan_admin.db")
os.environ["LAVA_DB"] = DB
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import accounts  # noqa: E402
import storage  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
PG = storage.using_postgres()
LOGINS = ("alice", "bob", "carol", "dave", "zed", "yan")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l + RUN, "secret")
_store.close()

import admin_account  # noqa: E402
import clan_admin  # noqa: E402
import clans  # noqa: E402
import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)

STORE = server.STORE
CLANS = server.CLANS
from testkit import check, fails  # noqa: E402


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


CLAN_FRAMES = ("cmdAck", "fellow", "gg_list", "gg_struct", "gg_code", "userInfo_Player")


def shape(frames):
    """(name, what tells it apart) of each clan frame, in order."""
    out = []
    for n, p in frames:
        if n not in CLAN_FRAMES:
            continue
        out.append((n, p.get("act") if n == "gg_struct" else p.get("reg") if n == "fellow"
                    else p.get("res") if n in ("cmdAck", "gg_list", "gg_code") else None))
    return out


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


def found(sess, name):
    ch = sess.character()
    ch.gold += clans.CREATE_GOLD
    ch.save(STORE)
    run(sess, "head;reg=@x@;soc=@%s@;" % name)
    run(sess, "gg_info;det=1;")
    take(sess)
    return CLANS.member(sess.char_id)["clan_id"]


def join(head, sess, perm):
    run(head, "admit;char=@%s@;perm=%d;post=@@;" % (escape(sess.nick), perm))
    run(sess, "apply;number=0;action=2;")
    run(sess, "gg_info;det=1;")
    take(head)
    take(sess)


def order(op, **args):
    """Queue one clan order as the panel does (Store.admin_push) and read
    the queue as the game does (server.drain_admin_actions): (its id, what
    it answered)."""
    aid = STORE.admin_push("tester", "clan", op=op, **args)
    for row in STORE.admin_pending():
        STORE.admin_done(row["id"], server.apply_admin_action(row))
    row = STORE.db.execute("SELECT result FROM admin_actions WHERE id = ?", (aid,)).fetchone()
    return aid, row["result"]


def result(op, **args):
    return order(op, **args)[1]


def ledger(clan_id):
    return [(r["source"], r["afro"], r["ref"]) for r in STORE.db.execute(
        "SELECT * FROM clan_ledger WHERE clan_id = ? ORDER BY id", (clan_id,))]


def tool(*argv):
    """tools/admin_account.py, run as its command line would: (exit code,
    what it printed). The game's Store commits first, or on Postgres the
    tool's reads would wait behind its open transaction."""
    STORE.db.commit()
    out = io.StringIO()
    args = list(argv) + ([] if PG else ["--db", DB])
    with contextlib.redirect_stdout(out):
        try:
            code = admin_account.main(args)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


async def main():
    alice = login("alice", nick("Alice"))
    bob = login("bob", nick("Bob"))
    carol = login("carol", nick("Carol"))
    dave = login("dave", nick("Dave"))
    zed = login("zed", nick("Zed"))
    yan = login("yan", nick("Yan"))
    wolves_name = "Волки %s" % RUN
    wolves = found(alice, wolves_name)
    join(alice, bob, clans.R_AFRO | clans.R_KICK | clans.R_CHAT)
    join(alice, carol, clans.R_CHAT)
    jackals = found(dave, "Шакалы %s" % RUN)
    carol_id, yan_id = carol.char_id, yan.char_id
    carol.close()
    yan.close()
    for s in (alice, bob, dave, zed):
        take(s)

    # --- the order itself ---------------------------------------------------------------
    check("an op nobody knows: said so, with the ones there are",
          result("fly", clan=wolves),
          "неизвестная операция с кланом: fly (есть: rename, disband, head, treasury, kick,"
          " hold, release)")
    check("a clan that is not: said so", result("treasury", clan=999999, afro=5),
          "клана 999999 нет")
    check("a row with no args_json to read",
          clan_admin.apply({"kind": "clan", "args_json": "{"}, CLANS),
          "не разобрать аргументы действия")

    # --- the treasury -------------------------------------------------------------------
    aid, said = order("treasury", clan=wolves_name.upper(), afro=500)
    check("500 afro into the treasury, the clan named in capitals: done",
          said, "казна «%s»: +500 афро, теперь 500" % wolves_name)
    check("  ..one 'admin' row in clan_ledger, ref the order that made it",
          ledger(wolves), [("admin", 500, aid)])
    check("  ..the new balance to the members online who may see it (0x400): the head,"
          " Bob", ([p["data"] for p in named(take(alice), "gg_list") if p["res"] == 3],
                   [p["data"] for p in named(take(bob), "gg_list") if p["res"] == 3]),
          ([[500]], [[500]]))
    check("  ..and to nobody else", named(take(dave), "gg_list"), [])
    check("200 out: done", result("treasury", clan=wolves, afro=-200),
          "казна «%s»: -200 афро, теперь 300" % wolves_name)
    for s in (alice, bob):
        take(s)
    check("more out than there is: refused, nothing written",
          (result("treasury", clan=wolves, afro=-1000), STORE.clan_treasury(wolves),
           len(ledger(wolves))),
          ("в казне «%s» 300 афро: снять 1000 нельзя" % wolves_name, 300, 2))
    check("  ..and nobody told anything", named(take(alice), "gg_list"), [])
    for bad in (0, "сто", 2.5, None):
        check("an amount of %r: refused" % (bad,), result("treasury", clan=wolves, afro=bad),
              "сумма — целое число афро, не ноль (минус — снять)")
    check("past what the column holds: refused",
          result("treasury", clan=wolves, afro=clan_admin.AFRO_LIMIT),
          "столько в казну не поместится: не больше %d афро" % clan_admin.AFRO_LIMIT)

    # --- rename -------------------------------------------------------------------------
    for bad, want in (("ab", None), ("Кот;Пёс", None),
                      ("ШАКАЛЫ  %s" % RUN, "название «ШАКАЛЫ %s» уже у клана «Шакалы %s» (id %d)"
                       % (RUN, RUN, jackals)),
                      ("Аукцион", "название «Аукцион» занято: так подписывается сама игра"),
                      (wolves_name, "у клана «%s» уже это название" % wolves_name)):
        got = result("rename", clan=wolves, name=bad)
        check("rename to %r: refused" % bad,
              got.startswith("название не годится") if want is None else got,
              True if want is None else want)
    check("  ..and the name stays", STORE.clan(wolves)["name"], wolves_name)
    for s in (alice, bob, dave):
        take(s)
    new_name = "Серые волки %s" % RUN
    said = result("rename", clan=wolves, name="  Серые   волки %s " % RUN)
    check("rename, the name cleaned as a founding cleans it: done, and F5 said",
          (said.startswith("«%s» → «%s»" % (wolves_name, new_name)), "F5" in said), (True, True))
    check("  ..the row: the name, and its skeleton for uniqueness",
          (STORE.clan(wolves)["name"], STORE.clan_by_key(clans.name_key(new_name))["id"],
           STORE.clan_by_key(clans.name_key(wolves_name))), (new_name, wolves, None))
    check("  ..the other clan's member online has his standings again, the new name in them",
          [(p["res"], dict(zip(p["data"], p["names"])).get(wolves)) for p in
           named(take(dave), "gg_list")], [(0, new_name)])
    check("  ..the clan's own clients are sent nothing: they keep the name by id till F5",
          (shape(take(alice)), shape(take(bob))), ([], []))
    check("  ..and the old name is free for anybody", STORE.clan_by_key(
        clans.name_key(wolves_name)), None)

    # --- the lead -------------------------------------------------------------------------
    check("hand the lead to a character outside the clan: refused",
          result("head", clan=wolves, char=zed.char_id),
          "%s не состоит в клане «%s»" % (nick("Zed"), new_name))
    check("  ..to the head himself: said so",
          result("head", clan=wolves, char=nick("Alice")),
          "%s и так глава «%s»" % (nick("Alice"), new_name))
    check("  ..to a character that is not: said so", result("head", clan=wolves, char="Никто"),
          "персонажа «Никто» нет")
    said = result("head", clan=wolves, char=nick("Carol"))
    check("the lead to Carol, offline: done",
          said, "глава «%s» теперь %s; %s остаётся в клане со всеми правами, кроме главы"
          % (new_name, nick("Carol"), nick("Alice")))
    check("  ..65535 moved, the old head keeps everything but the head's bit",
          (STORE.clan(wolves)["head"], CLANS.member(carol_id)["perm"],
           CLANS.member(alice.char_id)["perm"]), (carol_id, 65535, 0x2F67))
    check("  ..Alice, online: her row and Carol's to her roster, then her own rights",
          [(n, p.get("id"), p.get("perm")) for n, p in take(alice)
           if n in ("gg_struct", "fellow")],
          [("gg_struct", alice.char_id, 0x2F67), ("fellow", 0, 0x2F67),
           ("gg_struct", carol_id, 65535)])
    check("  ..Bob, holding the roster: both rows", [(p["id"], p["act"], p["perm"])
                                                     for p in named(take(bob), "gg_struct")],
          [(alice.char_id, 3, 0x2F67), (carol_id, 3, 65535)])
    said = result("head", clan=wolves, char=alice.char_id)
    check("and back to Alice, online: 65535 hers again, her own fellow says so",
          (said.startswith("глава «%s» теперь %s" % (new_name, nick("Alice"))),
           CLANS.member(alice.char_id)["perm"], CLANS.member(carol_id)["perm"],
           [p["perm"] for p in named(take(alice), "fellow")]),
          (True, 65535, 0x2F67, [65535]))
    take(bob)

    # --- kick -------------------------------------------------------------------------------
    check("kick the head: refused", result("kick", clan=wolves, char=alice.char_id),
          "главу не исключить: сначала передайте главенство (head) или распустите клан"
          " (disband)")
    check("kick a member of another clan: refused",
          result("kick", clan=wolves, char=dave.char_id),
          "%s не состоит в клане «%s»" % (nick("Dave"), new_name))
    said = result("kick", clan=wolves, char=bob.char_id)
    check("kick Bob, online: done, and he was told", said,
          "%s исключён из «%s» (в игре: ему пришло «Вас исключили из клана»)"
          % (nick("Bob"), new_name))
    check("  ..his client: fellow reg=0, then his standings emptied",
          shape(take(bob)), [("fellow", 0), ("gg_list", 0)])
    check("  ..the head, holding the roster: act=2", [(p["id"], p["act"]) for p in
                                                      named(take(alice), "gg_struct")],
          [(bob.char_id, 2)])
    check("  ..and he is in no clan", CLANS.member(bob.char_id), None)
    said = result("kick", clan=wolves, char=carol_id)
    check("kick Carol, offline: done", said, "%s исключён из «%s» (не в игре: увидит при входе)"
          % (nick("Carol"), new_name))
    carol = login("carol", nick("Carol"), new=False)
    check("  ..she logs in free: no clan's fellow, nothing of the clan",
          ([p for p in named(take(carol), "fellow") if p["id"] == 0], CLANS.member(carol_id)),
          ([], None))
    check("  ..and the head heard act=2 about her", [(p["id"], p["act"]) for p in
                                                     named(take(alice), "gg_struct")],
          [(carol_id, 2)])

    # --- disband ------------------------------------------------------------------------------
    check("disband with the treasury to somebody who is not: refused, the clan stays",
          (result("disband", clan=wolves, payout="Никто"), STORE.clan(wolves) is not None),
          ("персонажа «Никто» нет: клан не распущен", True))
    zed_afro = zed.character().afro
    led_zed = len(STORE.ledger(zed.char_id))
    for s in (alice, dave, zed):
        take(s)
    said = result("disband", clan=wolves, payout=nick("Zed"))
    check("disband, the treasury to Zed who plays and is in no clan: done",
          said, "клан «%s» распущен (членов: 1), название свободно; казна 300 афро — %s,"
          " в игре: в кошелёк сразу" % (new_name, nick("Zed")))
    check("  ..into his live purse, pushed, and in his row",
          (zed.character().afro, [p["afro"] for p in named(take(zed), "userInfo_Player")],
           STORE.money(zed.char_id)[0]), (zed_afro + 300, [zed_afro + 300], zed_afro + 300))
    check("  ..booked clan_disband, ref the clan, and 'disband' in the clan's journal",
          ([(r["source"], r["ref"], r["afro"]) for r in STORE.ledger(zed.char_id)[led_zed:]],
           ledger(wolves)[-1][:2]), ([("clan_disband", wolves, 300)], ("disband", -300)))
    zed.character().save(STORE)
    check("  ..and his save at logout keeps it", STORE.money(zed.char_id)[0], zed_afro + 300)
    check("  ..the head online put out: fellow reg=0, standings emptied",
          shape(take(alice)), [("fellow", 0), ("gg_list", 0)])
    check("  ..the other clan's member online: his standings without it",
          [(p["res"], wolves in p["data"]) for p in named(take(dave), "gg_list")], [(0, False)])
    check("  ..the clan, its members and the name are gone",
          (STORE.clan(wolves), CLANS.member(alice.char_id),
           STORE.clan_by_key(clans.name_key(new_name))), (None, None, None))
    check("  ..and a second disband finds nothing", result("disband", clan=wolves),
          "клана %d нет" % wolves)

    # The other clan: its head offline, the treasury to him by default.
    STORE.clan_treasury_adjust(jackals, 70, "admin")
    dave_id = dave.char_id
    dave.close()
    afro0 = STORE.money(dave_id)[0]
    said = result("disband", clan="Шакалы %s" % RUN)
    check("disband a clan whose head is offline, by name, the treasury to him by default",
          (said, STORE.money(dave_id)[0]),
          ("клан «Шакалы %s» распущен (членов: 1), название свободно; казна 70 афро — %s,"
           " не в игре: в его строку" % (RUN, nick("Dave")), afro0 + 70))

    # --- the tool -------------------------------------------------------------------------------
    owls = found(alice, "Совы %s" % RUN)
    join(alice, carol, clans.R_CHAT)
    code, out = tool("clans")
    check("tool: clans lists them: the id, the name, the head, the members",
          (code, any(line.split()[:1] == [str(owls)] and "Совы %s" % RUN in line
                     and nick("Alice") in line for line in out.splitlines())), (0, True))
    code, out = tool("clan", "совы  %s" % RUN)
    check("tool: clan shows its members, named in any case and spacing",
          (code, "clan Совы %s (id %d)" % (RUN, owls) in out, nick("Carol") in out,
           "head" in out), (0, True, True, True))
    code, out = tool("clan-treasury", str(owls), "--afro", "250", "--wait", "1")
    check("tool: an order while no game runs is queued and said to wait (exit 2)",
          (code, "not running" in out), (2, True))
    check("  ..nothing done yet", STORE.clan_treasury(owls), 0)
    pending = [dict(r) for r in STORE.admin_pending()]
    check("  ..the row the panel would have written: kind clan, the clan by id",
          [(r["kind"], r["admin"], json.loads(r["args_json"])) for r in pending],
          [("clan", "console", {"op": "treasury", "clan": owls, "afro": 250})])
    for row in STORE.admin_pending():
        STORE.admin_done(row["id"], server.apply_admin_action(row))
    check("  ..and carried out when the game reads its queue", STORE.clan_treasury(owls), 250)
    code, out = tool("clan-kick", str(owls), "--char", "Никто")
    check("tool: a character it cannot find is refused before anything is queued",
          (code, list(STORE.admin_pending())), ("no character named or numbered 'Никто'", []))
    code, out = tool("clan-disband", str(owls))
    check("tool: disband without --yes says what it would do and queues nothing",
          (code, "250 afro" in out, list(STORE.admin_pending())), (1, True, []))

    check("no clan command was answered twice", CLANS.double_acks, [])
    for s in list(server.SESSIONS) + [alice, bob, carol, zed]:
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
print("clan admin OK")
