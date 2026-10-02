"""Deleting an account closes its business on the auction.

characters.id is INTEGER PRIMARY KEY without AUTOINCREMENT, so the character
made right after the last one is deleted gets the same id back. A lot that
still named the deleted seller then belonged to the newcomer, who could take
it off (the item by mail) or sell it to its bidder for money. So the tool
closes the seller's lots -- a bid on one going back to its bidder by mail,
as auction.refund writes it -- and strikes out the seller's own bids on
other players' lots, and says so before --yes. What it then does is taken
from its own writes: the game goes on settling lots in between, and a
lot it sold already is not refunded a second time, nor a bid somebody
made since struck out.

    LAVA_RES=.../lava/res python3 tools/test_admin_account.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server")
sys.path.insert(0, HERE)
sys.path.insert(0, SERVER)

import accounts  # noqa: E402
import admin_account  # noqa: E402
import auction  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
import storage  # noqa: E402

from testkit import check, fails  # noqa: E402


check("the tool's letter constants are mail.py's",
      (admin_account.SYSTEM_SENDER, admin_account.LETTER), (mail.SYSTEM_SENDER, mail.LETTER))
check("  ..and its money is written as auction.py writes it",
      [admin_account.money_text(a, c) for a, c in ((150, 0), (250, 1))],
      [auction.money_text(a, c) for a, c in ((150, 0), (250, 1))])

DB = os.path.join(tempfile.mkdtemp(), "admin.db")
st = accounts.Store(DB)
a1, _ = st.register("alice", "secret1")
a2, _ = st.register("bobby", "secret2")
alice, _ = st.create_character(a1, "Алиса", 0, 1)
bob, _ = st.create_character(a2, "Боб", 0, 1)
now = time.time()


def lot_of(char_id, name, currency=0):
    row = dict(st.create_item(char_id, inventory.STARTER_AMMO, items.AMMO, count=20))
    return st.auction_list(row["uniq"], char_id, dict(
        type_id=row["type_id"], root=row["root"], item_json=json.dumps(mail.snapshot(row)),
        seller=char_id, seller_name=name, currency=currency, start_bid=100, buyout=0,
        fee=8, hours=24, created_at=int(now), ends_at=now + 86400))["id"]


def words(killer, killer_name, victim, victim_name):
    return dict(killer_id=killer, killer_name=killer_name, killer_lvl=0,
                victim_id=victim, victim_name=victim_name, victim_lvl=0,
                victim_clan="", killed_at=int(now))


def registered(char_id, type_id, rec):
    """A trophy of char_id's registered into its collection, purse and
    skill left as they are."""
    row = st.create_trophy(char_id, inventory.BAG, type_id, items.TROPHY, rec)
    afro, gold = st.money(char_id)
    st.register_trophy(row, st.trophy(row["uniq"]), char_id, int(now), True,
                       (char_id, afro, gold), st.character(char_id)["rep"])
    return row["uniq"]


# Bob's trophies: an entry in his collection, one he deleted from it (the
# row stays for the hour's pay mark, trophies.py), one still a thing in his
# bag. Alice's collection keeps her kill of Bob: that is hers.
registered(bob, 1495, words(bob, "Боб", alice, "Алиса"))
st.delete_trophy(registered(bob, 1494, words(bob, "Боб", alice, "Алиса")), bob)
st.create_trophy(bob, inventory.BAG, 1493, items.TROPHY, words(bob, "Боб", alice, "Алиса"))
hers = registered(alice, 1495, words(alice, "Алиса", bob, "Боб"))

afro_lot = lot_of(bob, "Боб")
st.auction_rebid(afro_lot, 150, alice, "Алиса")
bare_lot = lot_of(bob, "Боб")
gold_lot = lot_of(bob, "Боб", currency=1)
st.auction_rebid(gold_lot, 250, alice, "Алиса")
alices = lot_of(alice, "Алиса")
st.auction_rebid(alices, 200, bob, "Боб")
st.close()


def tool(*args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "admin_account.py"), "delete",
                        "bobby", "--db", DB] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout


code, out = tool()
check("without --yes nothing is deleted", code, 1)
check("  ..but the lots and the bids are counted",
      ("3 lots on sale go with the account; 2 bids on them go back" in out,
       "1 bids on other players' lots are struck out" in out), (True, True))
code, out = tool("--yes")
check("with --yes the account goes", (code, "auction: 3 lots closed, 2 bids refunded by mail, "
                                       "1 bids struck out" in out), (0, True))

st = accounts.Store(DB)
left = st.auction_active(time.time())
check("the deleted seller's lots are gone, the other seller's lot stays",
      [l["id"] for l in left], [alices])
check("  ..without the deleted bidder's bid on it",
      [(l["bid"], l["bidder"], l["bidder_name"]) for l in left], [(0, 0, "")])
letters = [dict(r) for r in st.db.execute(
    "SELECT * FROM mail WHERE to_char = ? ORDER BY id", (alice,)).fetchall()]
check("the outbid money comes back to its bidder by mail, from the house, in its currency",
      [(l["from_char"], l["type"], l["afro"], l["gold"], l["subject"]) for l in letters],
      [(mail.SYSTEM_SENDER, mail.LETTER, 150, 0, "Аукцион: ставка возвращена"),
       (mail.SYSTEM_SENDER, mail.LETTER, 0, 250, "Аукцион: ставка возвращена")])
a3, _ = st.register("carol", "secret3")
carol, _ = st.create_character(a3, "Кэрол", 0, 1)
if not storage.using_postgres():
    # SQLite's rowid comes back; an identity column in Postgres never does,
    # and the check below is then the whole of it.
    check("the next character takes the deleted one's id", carol, bob)
check("  ..and inherits no lot of it", (st.auction_count(carol, time.time()),
                                       [l for l in st.auction_active(time.time())
                                        if l["seller"] == carol or l["bidder"] == carol]), (0, []))
check("  ..nor a trophy: Bob's collection, the entry he deleted and the words of the one"
      " in his bag went with him; Alice's kill of him stays in hers",
      ([r["uniq"] for r in st.db.execute("SELECT uniq FROM trophies ORDER BY uniq")],
       st.trophies_of(carol), st.trophy_paid_since(carol, alice, 0)),
      ([hers], [], False))

# --- the game settles while the tool is between its count and its write ------
# The server does not stop for the tool. Dora is deleted; her lot has run
# out with Эд's bid on it, and she holds the bid on Кэрол's lot. Right after
# the tool has read the auction for its report, the server's sweep sells
# Dora's lot to Эд (the item to him by letter) and Эд outbids her on
# Кэрол's (her 120 back to her by letter). A refund written from the read
# would pay Эд his 100 on top of the item, and striking out "Dora's" bid by
# lot id would wipe the 150 Эд has in escrow now.
a4, _ = st.register("dora", "secret4")
a5, _ = st.register("eddie", "secret5")
dora, _ = st.create_character(a4, "Дора", 0, 1)
ed, _ = st.create_character(a5, "Эд", 0, 1)
ran_out = lot_of(dora, "Дора")
st.db.execute("UPDATE auction_lots SET ends_at = ? WHERE id = ?", (now - 1, ran_out))
st.db.commit()
st.auction_rebid(ran_out, 100, ed, "Эд")
carols = lot_of(carol, "Кэрол")
st.auction_rebid(carols, 120, dora, "Дора")

counted = admin_account.auction_rows


def meanwhile(db, char_ids):
    rows = counted(db, char_ids)
    for lot in st.auction_due(time.time()):
        st.auction_close(lot["id"], auction.settle(lot, lot["bidder"], lot["bid"],
                                                   lot["bidder_name"]))
    lot = st.auction_lot(carols)
    st.auction_rebid(carols, 150, ed, "Эд", auction.refund(lot, "Вашу ставку перебили на"))
    return rows


admin_account.auction_rows = meanwhile
report = io.StringIO()
try:
    with contextlib.redirect_stdout(report):
        code = admin_account.main(["delete", "dora", "--db", DB, "--yes"])
finally:
    admin_account.auction_rows = counted
out = report.getvalue()
check("the tool counted a lot and a bid, and went through",
      (code, "1 lots on sale go with the account; 1 bids on them go back" in out,
       "1 bids on other players' lots are struck out" in out), (0, True, True))
check("  ..and says it did neither, the game having got there first",
      ("auction: 0 lots closed, 0 bids refunded by mail, 0 bids struck out" in out,
       "not what was counted above" in out), (True, True))
got = [(l["subject"].split("«")[0], l["afro"], l["gold"], len(json.loads(l["items_json"])))
       for l in st.db.execute("SELECT * FROM mail WHERE to_char = ? ORDER BY id",
                              (ed,)).fetchall()]
check("Эд has the item he won and no refund of the bid that paid for it",
      got, [("Аукцион: покупка ", 0, 0, 1)])
lot = st.auction_lot(carols)
check("his 150 on Кэрол's lot stands: the bid the tool meant to strike out was Dora's",
      (lot["bid"], lot["bidder"], lot["bidder_name"]), (150, ed, "Эд"))
check("  ..and nothing of Dora's is left on the auction",
      [l["id"] for l in st.auction_active(0) if dora in (l["seller"], l["bidder"])], [])

# --- a clan's head deleted ---------------------------------------------------
# The clan passes to the member the game would pick (accounts.clan_successor:
# rank, then rights, then time in the clan) -- never to the account's other
# character, who goes too -- or, with nobody left, is disbanded, and its
# treasury goes with the account as the purse does. The game caches nothing
# of a clan (server/clans.py), so what the tool writes is what it plays by.
a6, _ = st.register("frank", "secret6")
a7, _ = st.register("gina", "secret7")
a8, _ = st.register("hank", "secret8")
frank, _ = st.create_character(a6, "Франк", 0, 1)
gina, _ = st.create_character(a7, "Гина", 0, 1)
hank, _ = st.create_character(a8, "Хэнк", 0, 1)
hank2, _ = st.create_character(a8, "Хэнк-второй", 0, 1)
eagles = st.clan_create(frank, "Орлы", "орлы", "", None, when=1000)
st.clan_member_add(carol, eagles, 0x2, "", frank, when=1001)
st.clan_member_add(ed, eagles, 0x100 | 0x2, "", frank, when=1002)
owls = st.clan_create(gina, "Совы", "совы", "", None)
st.clan_treasury_adjust(owls, 250, "admin")
hawks = st.clan_create(hank, "Ястребы", "ястребы", "", None, when=1000)
st.clan_member_add(hank2, hawks, 0x2000 | 0x2, "", hank, when=1001)
stays, _ = st.create_character(a5, "Эд-второй", 0, 1)
st.clan_member_add(stays, hawks, 0x2, "", hank, when=1002)
st.close()


def delete(login, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = admin_account.main(["delete", login, "--db", DB] + list(args))
    return code, out.getvalue()


code, out = delete("frank")
check("the count says the clan passes on, and to whom",
      (code, "Франк heads «Орлы» (id %d): it passes to Эд" % eagles in out), (1, True))
code, out = delete("frank", "--yes")
st = accounts.Store(DB)
check("deleted: the officer heads «Орлы» now, with 65535, and the head's row is gone",
      (code, st.clan(eagles)["head"], st.clan_member(ed)["perm"], st.clan_member(frank),
       "clan %d: handed over to character %d" % (eagles, ed) in out),
      (0, ed, 65535, None, True))
st.close()
code, out = delete("gina")
check("a lone head: the count says the clan is disbanded with its 250 afro",
      "Гина heads «Совы» (id %d) with nobody else in it: it is disbanded, and the 250 afro"
      % owls in out, True)
code, out = delete("gina", "--yes")
st = accounts.Store(DB)
check("  ..and it is: no clan, the treasury booked gone",
      (st.clan(owls), [(r["source"], r["afro"]) for r in st.clan_ledger_rows(owls)]),
      (None, [("disband", -250), ("admin", 250)]))
st.close()
code, out = delete("hank", "--yes")
st = accounts.Store(DB)
check("the head's other character, a higher rank, goes with the account: the clan passes"
      " to the one who stays", (st.clan(hawks)["head"], st.clan_member_perms(hawks)),
      (stays, [(stays, 65535)]))
st.close()

# A database no server of today has opened has no clan tables: the tool,
# which never builds the schema, deletes all the same.
OLD = os.path.join(tempfile.mkdtemp(), "old.db")
st = accounts.Store(OLD)
old_acc, _ = st.register("oldie", "secret9")
st.create_character(old_acc, "Старый", 0, 1)
for table in ("clans", "clan_members", "clan_relations", "clan_ledger"):
    st.db.execute("DROP TABLE %s" % table)
st.db.commit()
st.close()
with contextlib.redirect_stdout(io.StringIO()):
    code = admin_account.main(["delete", "oldie", "--db", OLD, "--yes"])
check("a database without clan tables: the account is deleted all the same", code, 0)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("admin_account OK")
