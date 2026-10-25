"""The auction house, the way Auction.as and the two auction windows drive it.

Three players meet at the Nubian market's auctioneer (type 5184). Every
ah_create and ah_op gets exactly one cmdAck; every ah_search gets no cmdAck
and exactly one ah_sresult, followed by one ah_lot per lot and that lot's
one ss_di_*. Money and items between players travel only by mail, from
"Аукцион" (mail.SYSTEM_SENDER). A fourth character lies dead in the same
market and still gets an (empty) answer to every search; a fifth account
finds the house's name taken.

An auction hour is shrunk to half a second, so a 24-hour lot runs out in
twelve, and a seller may keep only three lots up at once.

Before the server starts, the Store alone: a second connection, standing
in for tools/admin_account.py, closes a lot, strikes out a bid or takes an
item away right before the Store's own write, and the Store then files no
letter and charges no purse. And, offline, the lock every Store opens
under in Postgres: a connection that dies inside it is reported as itself.
"""
import contextlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
sys.path.insert(0, HERE)
import accounts
import auction
import inventory
import items
import mail
import storage
from protocol import decode

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- in process: the arithmetic the windows print --------------------------------
check("afro commission as checkComission prints it: 100 afro, 3 days -> 8",
      auction.afro_fee(100, 1, 72), 8)
check("800 afro for 3 days -> 57, not 56", auction.afro_fee(800, 1, 72),
      int(math.ceil(800 * 0.07 * 1)))
check("a stack counts every piece", auction.afro_fee(20, 200, 24), 200)
check("gold commission has its floor", auction.gold_fee(100, 24), 50)
check("and its share above the floor", auction.gold_fee(10000, 168), 400)
check("first bid may meet the start",
      auction.least_bid(dict(bidder=0, bid=0, start_bid=100)), 100)
check("later ones beat the last by 10%",
      auction.least_bid(dict(bidder=7, bid=100, start_bid=100)), 110)
BERETTA = 25586            # pistols_1_lvl_2, Беретта 92, 800 afro, exchang=1
ROUNDS = items.AMMO_9MM[0]  # Ammo_9mmNato_KS, 20 afro a pack, 200 to a stack
COST = items.params_of(BERETTA)["cost"]
CLIP = items.params_of(BERETTA)["clip_size"]
check("a pistol: firearm, subcat 0, level 2",
      auction.meta(BERETTA)[:3], (items.FIRE_ARM, 0, 2))
check("9mm rounds: calibre 5 of AuctionInterface.changedCategory",
      auction.meta(ROUNDS)[:2], (items.AMMO, 5))
check("the Beretta takes these rounds", ROUNDS in items.params_of(BERETTA)["comp_array"], True)

# --- the house's name ---------------------------------------------------------
check("the house's own name is reserved", mail.is_system_name("Аукцион"), True)
check("in any case", mail.is_system_name(" аукЦИОН "), True)
check("and with a Latin A and o passing for Cyrillic",
      mail.is_system_name("\x41укци\x6fн"), True)
check("an ordinary name is not", mail.is_system_name("Аукционист"), False)
check("nor is it with the lookalikes a name happens to hold",
      [mail.is_system_name(n) for n in ("Alice", "Bob", "Ωмега", "Аукцион 2")], [False] * 4)
check("a Greek capital alpha or omicron passes for Cyrillic too",
      [mail.is_system_name(n) for n in ("Αукцион", "Аукциοн", "ΑΥΚЦИΟН")],
      [True] * 3)
check("and so does a zero for the о",
      mail.is_system_name("Аукци0н"), True)
check("an invisible character inside changes nothing: zero-width space, word joiner, "
      "soft hyphen, no-break space",
      [mail.is_system_name(n) for n in ("Аукцион​", "Ау⁠кцион", "Аук­цион",
                                        "Аукцион ")], [True] * 4)
check("nor does an accent laid over a letter, or a fullwidth form",
      [mail.is_system_name(n) for n in ("А́укцион", "Аукциӧн", "Ａукцион")],
      [True] * 3)

TMP = tempfile.mkdtemp()

# --- the letters from character 0 and the declared foreign key ------------------
# mail.from_char is declared REFERENCES characters(id), and the house writes
# 0 there. That holds only while the declaration stays a declaration: this
# pins both halves, so a change to either fails here and not in a sale.
st = accounts.Store(os.path.join(TMP, "fk.db"))
if storage.using_postgres():
    check("Postgres holds no FOREIGN KEY at all",
          st.db.execute("SELECT COUNT(*) c FROM information_schema.table_constraints"
                        " WHERE constraint_type = 'FOREIGN KEY'").fetchone()["c"], 0)
else:
    check("SQLite is told not to enforce REFERENCES",
          st.db.execute("PRAGMA foreign_keys").fetchone()[0], 0)
acc, _ = st.register("keys", "secret")
cid, _ = st.create_character(acc, "Fk", 0, "1")
fields = inventory.new_fields(BERETTA)
root = fields.pop("root")
row = st.create_item(cid, BERETTA, root, **fields)
now = time.time()
lot = st.auction_list(row["uniq"], cid, dict(
    type_id=BERETTA, root=root, item_json=json.dumps(mail.snapshot(row)),
    seller=cid, seller_name="Fk", currency=auction.AFRO, start_bid=100,
    buyout=0, fee=0, hours=24, created_at=int(now), ends_at=now + 60))
check("listing takes the row out of items", st.item(row["uniq"]), None)
sent = st.auction_close(lot["id"], auction.give_back(lot, "s", "b"))
check("a lot is settled with a letter from character 0",
      [(r["from_char"], r["to_char"]) for r in sent or []], [(0, cid)])
check("and closed once only", st.auction_close(lot["id"], []), None)
if not storage.using_postgres():
    st.db.execute("PRAGMA foreign_keys=ON")
    try:
        st.mail_send(cid, mail.SYSTEM_SENDER, mail.LETTER, "s", "b", 1, 0, "[]")
        refused = False
    except storage.IntegrityError:
        refused = True
    check("(with enforcement on the same letter is refused: why it stays off)",
          refused, True)
st.close()
check("the Postgres translation carries no REFERENCES either",
      [s.split("(")[0] for s in storage.pg_schema(accounts.SCHEMA)
       if "REFERENCES" in s.upper()], [])


# --- a lost race is told by the write ----------------------------------------------
# The game server is not the only writer: tools/admin_account.py, a process
# of its own, closes a deleted account's lots and strikes out its bids. A
# read inside the transaction locks nothing -- SQLite starts the transaction
# at the first write, Postgres locks a row by writing it -- so `first` lets
# that other connection act right before this Store's first write, which is
# where a read-then-write loses the race.
WRITES = ("INSERT", "UPDATE", "DELETE")


@contextlib.contextmanager
def first(store, act):
    real = store.db.execute
    pending = [act]

    def execute(sql, args=()):
        if pending and sql.split(None, 1)[0].upper() in WRITES:
            pending.pop()()
        return real(sql, args)
    store.db.execute = execute
    try:
        yield
    finally:
        del store.db.execute


RACE = os.path.join(TMP, "race.db")
st = accounts.Store(RACE)
tool = storage.connect(RACE)


def by_tool(sql, *args):
    return lambda: (tool.execute(sql, args), tool.commit())


def person(login):
    acc, _ = st.register(login, "secret")
    return st.create_character(acc, login.title(), 0, "1")[0]


seller, gone, rival = person("seller"), person("gone"), person("rival")
st.save_character_state(rival, afro=1000)


def lot_with(bidder=0, bid=0):
    f = inventory.new_fields(BERETTA)
    r = f.pop("root")
    row = st.create_item(seller, BERETTA, r, **f)
    lot = st.auction_list(row["uniq"], seller, dict(
        type_id=BERETTA, root=r, item_json=json.dumps(mail.snapshot(row)),
        seller=seller, seller_name="Seller", currency=auction.AFRO, start_bid=100,
        buyout=0, fee=0, hours=24, created_at=int(time.time()), ends_at=time.time() + 60))
    if bidder:
        st.auction_rebid(lot["id"], bid, bidder, "Gone")
    return st.auction_lot(lot["id"])


def letters_to(char_id):
    return st.db.execute("SELECT COUNT(*) c FROM mail WHERE to_char = ?",
                         (char_id,)).fetchone()["c"]


def races():
    lot = lot_with(gone, 100)
    with first(st, by_tool("DELETE FROM auction_lots WHERE id = ?", lot["id"])):
        sent = st.auction_close(lot["id"], auction.settle(lot, gone, 100, "Gone"))
    check("a sale closed by the other process first settles nothing here",
          (sent, letters_to(gone), letters_to(seller)), (None, 0, 0))

    lot = lot_with(gone, 100)
    with first(st, by_tool("DELETE FROM auction_lots WHERE id = ?", lot["id"])):
        sent = st.auction_rebid(lot["id"], 150, rival, "Rival",
                                auction.refund(lot, "Вашу ставку перебили на"),
                                purse=(rival, 850, 0))
    check("a bid on a lot closed first: None, the old bid not refunded twice, the bidder not charged",
          (sent, letters_to(gone), st.money(rival)), (None, 0, (1000, 0)))

    f = inventory.new_fields(BERETTA)
    r = f.pop("root")
    row = st.create_item(seller, BERETTA, r, **f)
    try:
        with first(st, by_tool("DELETE FROM items WHERE uniq = ?", row["uniq"])):
            st.auction_list(row["uniq"], seller, dict(
                type_id=BERETTA, root=r, item_json=json.dumps(mail.snapshot(row)),
                seller=seller, seller_name="Seller", currency=auction.AFRO, start_bid=100,
                buyout=0, fee=0, hours=24, created_at=int(time.time()),
                ends_at=time.time() + 60))
        refused = False
    except ValueError:
        refused = True
    check("an item taken away before the listing's write is not listed",
          (refused, st.auction_lot_by_item(row["uniq"])), (True, None))

    lot = lot_with(gone, 100)
    strike = by_tool("UPDATE auction_lots SET bid = 0, bidder = 0, bidder_name = ''"
                     " WHERE id = ? AND bidder = ?", lot["id"], gone)
    with first(st, strike):
        sent = st.auction_rebid(lot["id"], 150, rival, "Rival",
                                auction.refund(lot, "Вашу ставку перебили на"),
                                purse=(rival, 850, 0), was=(lot["bidder"], lot["bid"]))
    check("a bid whose refund was written from a bid struck out since: None",
          (sent, letters_to(gone), st.money(rival)), (None, 0, (1000, 0)))
    now_lot = st.auction_lot(lot["id"])
    check("  ..and the lot stays as the strike left it",
          (now_lot["bid"], now_lot["bidder"]), (0, 0))
    sent = st.auction_rebid(lot["id"], 150, rival, "Rival", [], purse=(rival, 850, 0),
                            was=(now_lot["bidder"], now_lot["bid"]))
    check("  ..while a bid read as the lot now stands goes in, and is paid for",
          (sent, st.auction_lot(lot["id"])["bidder"], st.money(rival)), ([], rival, (850, 0)))

    lot = lot_with(gone, 100)
    strike = by_tool("UPDATE auction_lots SET bid = 0, bidder = 0, bidder_name = ''"
                     " WHERE id = ? AND bidder = ?", lot["id"], gone)
    with first(st, strike):
        sent = st.auction_close(lot["id"], auction.settle(lot, gone, 100, "Gone"),
                                was=(lot["bidder"], lot["bid"]))
    check("a sale to a bidder struck out since: None, the lot left for the next sweep",
          (sent, letters_to(gone), letters_to(seller), st.auction_lot(lot["id"]) is not None),
          (None, 0, 0, True))


# The race checks work on a scratch database of their own. Under LAVA_DB_URL
# every store is the one shared Postgres database, so the lots they leave
# would turn up in the socket search checks below: there they are skipped,
# and test_storage_pg covers the same writes on Postgres.
try:
    if storage.using_postgres():
        print("  --  race checks skipped: they need a database of their own")
    else:
        races()
except Exception:
    import traceback
    fails.append("the race checks crashed:\n" + traceback.format_exc())
tool.close()
st.close()


# --- the schema lock on a connection that died --------------------------------------
# Every Store opens through PostgresDB.schema_lock, which releases its advisory
# lock on the way out. When what failed inside was the connection itself, the
# release fails too, and the error to be seen is still the first one. Offline,
# with a stand-in for psycopg's connection, like the pg_schema check above.
class PgError(Exception):
    pass


class Lost(Exception):
    pass


class Conn:
    def __init__(self):
        self.alive, self.sent = True, []
        self.info = SimpleNamespace(transaction_status="IDLE")

    def execute(self, sql, args=()):
        if not self.alive:
            raise PgError("the connection is closed")
        self.sent.append(sql.split("(")[0])

    def rollback(self):
        self.execute("ROLLBACK")

    def commit(self):
        self.execute("COMMIT")


def pg_over(conn):
    db = object.__new__(storage.PostgresDB)
    db._conn = conn
    db._psycopg = SimpleNamespace(Error=PgError, pq=SimpleNamespace(
        TransactionStatus=SimpleNamespace(INERROR="INERROR")))
    return db


def outcome(body, conn):
    try:
        with pg_over(conn).schema_lock():
            body(conn)
    except Exception as exc:         # noqa: BLE001
        return type(exc).__name__
    return None


def dies(conn):
    conn.alive = False
    raise Lost("the server went away half way through the migration")


check("the schema lock: the connection dying inside comes out as that, not as the failed release",
      outcome(dies, Conn()), "Lost")
live = Conn()
check("  ..a clean pass takes the lock, releases it and commits",
      (outcome(lambda c: None, live), live.sent),
      (None, ["SELECT pg_advisory_lock", "SELECT pg_advisory_unlock", "COMMIT"]))
check("  ..and a release that fails with nothing failed before it is not swallowed",
      outcome(lambda c: setattr(c, "alive", False), Conn()), "PgError")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
DB = os.path.join(TMP, "test.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for login in ("alice", "bob", "carol", "dave", "eve"):
    _store.register(login, "secret")
# Dave lies dead in the market from the start: logged out after a mauling,
# the way test_death lays a character out.
DAVE, _ = _store.create_character(_store.account_by_login("dave")["id"],
                                  "Dave", 0, "1")
_store.save_character_state(DAVE, death=1, hp=0, sp=0)
_store.close()
CRED = {n: accounts.credential(n, "secret")
        for n in ("alice", "bob", "carol", "dave", "eve")}

HOUR = 0.5
MAX_LOTS = 3
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="6268", LAVA_GY="1825", LAVA_POLICY_PORT="0",
           LAVA_AUCTION_HOUR=str(HOUR), LAVA_AUCTION_SWEEP="0.2",
           LAVA_AUCTION_MAX_LOTS=str(MAX_LOTS))
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True).start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


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
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]


def names_of(frames):
    return [n for n, _ in frames]


def named(frames, name):
    return [p for n, p in frames if n == name]


def enter(c, who, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED[who])
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    got = c.frames(2)
    auc = [p["newUser"] for n, p in got if n == "lch" and p.get("rtype") == 7]
    c.send("chkml;mode=0;")          # LocationInterface.checkNewLetter
    c.frames()
    return auc[0] if auc else None


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)
    return c.frames()


def purse(c):
    c.send("getInfo;lvl=0;id=0;type=0;")
    p = named(c.frames(), "userInfo_Player")[0]
    return p["afro"], p["gold"]


def search(c, **kw):
    q = dict(s_mode=1, sort=0, max_g=0, min_g=0, max_a=0, min_a=0, max_lvl=0,
             min_lvl=0, subcat=-1, cat=-1, name="", page=0, target=AUC)
    q.update(kw)
    text = "ah_search;" + "".join(
        "%s=%s;" % (k, "@%s@" % v if k == "name" else v) for k, v in q.items())
    c.send(text)
    return c.frames()


def lots(frames):
    return named(frames, "ah_lot")


def give(c, type_id, count=1):
    got = chat(c, "/give %d %d" % (type_id, count))
    return str(named(got, "ss_obj_status")[0]["obj"])


def create(c, oid, hours=72, a_bid=0, a_buyout=0, g_bid=None, g_buyout=None):
    # CSMessage leaves out an undefined property: an afro lot has no g_*.
    parts = ["ah_create;"]
    if g_buyout is not None:
        parts.append("g_buyout=%d;" % g_buyout)
    if g_bid is not None:
        parts.append("g_bid=%d;" % g_bid)
    if a_buyout is not None and g_bid is None:
        parts.append("a_buyout=%d;" % a_buyout)
    if a_bid is not None and g_bid is None:
        parts.append("a_bid=%d;" % a_bid)
    parts.append("time=%d;obj=x%s;target=%d;" % (hours, oid, AUC))
    c.send("".join(parts))
    return c.frames()


def op(c, kind, oid, amount=None):
    amt = "" if amount is None else "amount=%d;" % amount
    c.send("ah_op;%sobj=x%s;type=%d;target=%d;" % (amt, oid, kind, AUC))
    return c.frames()


def newest(c):
    """The id of the newest letter in the inbox, as the list spells it."""
    c.send("chkml;mode=0;")
    return str(named(c.frames(), "lsml")[0]["id"][-1])


def inbox_ids(c):
    c.send("chkml;mode=0;")
    return [str(i) for i in named(c.frames(), "lsml")[0]["id"]]


def unpack_newest(c):
    """Open the newest letter and take its parcel; returns (letter params,
    ctml params, frames)."""
    lid = newest(c)
    c.send("getml;id=x%s;" % lid)
    rc = named(c.frames(), "rcml")[0]
    c.send("uldml;id=x%s;" % lid)
    got = c.frames()
    return rc, named(got, "ctml")[0], got


def bag(c):
    c.send("ss_get;target=0;slot=8;")
    return [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]


try:
    a, b, cc = Client(connect()), Client(connect()), Client(connect())
    AUC = enter(a, "alice", "Alice")
    enter(b, "bob", "Bob")
    enter(cc, "carol", "Carol")
    check("the market has an auctioneer (rtype 7)", AUC is not None, True)
    chat(a, "/money 20000 0")
    for x in (a, b, cc):
        x.frames(0.3)

    # --- an empty house ---------------------------------------------------------
    got = search(a)
    check("search: ah_sresult alone, no cmdAck", names_of(got), ["ah_sresult"])
    check("page 0, nothing, no next page", got[0][1],
          {"page": 0, "count": 0, "next": 0})
    got = search(a, target=999999)
    check("a target that is no auctioneer still gets its ah_sresult",
          names_of(got), ["ah_sresult"])

    # --- listing ----------------------------------------------------------------
    gold_belt = give(a, 4363)       # belt_critical_g_Jons: gold by its name, exchang=1
    got = create(a, gold_belt, hours=168, a_bid=100, a_buyout=500, g_bid=None)
    check("gold gear with exchang=1 cannot be listed and stays in the bag",
          ([p["res"] for n, p in got if n == "cmdAck"], gold_belt in bag(a)),
          ([auction.RES_REFUSED], True))
    a.send("sndml;item=x%s;body=@@;type=0;subj=@x@;to=@Bob@;" % gold_belt)
    got = a.frames()
    check("the same gold gear cannot bypass binding in a letter",
          ([p["res"] for n, p in got if n == "cmdAck"],
           named(got, "ctml"), gold_belt in bag(a), inbox_ids(b)),
          ([mail.RES_REFUSED], [], True, []))
    gun = give(a, BERETTA)
    afro0, _ = purse(a)
    got = create(a, gun, hours=168, a_bid=100, a_buyout=500, g_bid=None)
    check("create: exactly one cmdAck, res 0",
          [p for n, p in got if n == "cmdAck"], [{"res": 0}])
    check("then the item leaves the bag by ss_obj_status 0",
          named(got, "ss_obj_status"), [{"obj": gun, "status": 0}])
    fee = auction.afro_fee(COST, 1, 168)
    check("and the purse comes back less the commission",
          named(got, "userInfo_Player")[0]["afro"], afro0 - fee)
    check("gone from the bag", gun in bag(a), False)
    starter = give(a, inventory.STARTER_PISTOL)
    got = create(a, starter, a_bid=10)
    check("an untradeable item: refused with 3, reason in chat",
          (names_of(got), got[0][1]), (["cmdAck", "userMsg"], {"res": 3}))
    got = create(a, "dead0063d600", a_bid=10)
    check("an item that is not hers: refused", got[0], ("cmdAck", {"res": 3}))

    got = search(a, cat=auction.MY_LOTS)
    check("my lots: header, the lot, its one DI", names_of(got),
          ["ah_sresult", "ah_lot", "ss_di_firearm"])
    lot = lots(got)[0]
    check("the lot as Auction.addLot reads it",
          (lot["obj"], lot["a_bid"], lot["a_buyout"], lot["owner"], lot["bidder"]),
          (gun, 100, 500, "Alice", ""))
    # Whole hours, rounded up; a shrunk hour has passed a few while we looked.
    check("hours left, as AuctionItem prints them",
          150 <= lot["time_left"] <= 168, True)
    check("no gold pair on an afro lot", "g_bid" in lot, False)

    # --- a player the server holds dead -------------------------------------
    d = Client(connect())
    d.send("hello;minor=2;major=0;")
    d.send("login;hash=@%s@;" % CRED["dave"])
    d.frames()
    d.send("selPers;num=0;")
    d.frames(1.0)
    d.send("lenter;accept=1;")
    d.frames(2)
    got = search(d)
    check("dead: a search is still answered, with an empty page and no cmdAck",
          got, [("ah_sresult", {"page": 0, "count": 0, "next": 0})])
    dgun = give(a, BERETTA)
    d.send("ah_create;a_bid=10;time=24;obj=x%s;target=%d;" % (dgun, AUC))
    check("dead: a listing is refused with one ack",
          d.frames(), [("cmdAck", {"res": 3})])
    got = search(d, cat=auction.MY_LOTS)
    check("and the next search is answered all the same",
          names_of(got), ["ah_sresult"])
    for x in (a, b, cc):
        x.frames(0.3)

    # --- the search ---------------------------------------------------------------
    check("Bob sees it", [l["obj"] for l in lots(search(b))], [gun])
    check("by name, any case", len(lots(search(b, name="берет"))), 1)
    check("a name that fits nothing", named(search(b, name="zzz"), "ah_sresult")[0]["count"], 0)
    check("firearms, pistols", len(lots(search(b, cat=0, subcat=0))), 1)
    check("not a shotgun", len(lots(search(b, cat=0, subcat=1))), 0)
    check("not clothes", len(lots(search(b, cat=1))), 0)
    check("level 3 and up excludes a level-2 gun", len(lots(search(b, min_lvl=3))), 0)
    check("under 50 afro excludes it", len(lots(search(b, max_a=50))), 0)
    check("gold bounds exclude an afro lot", len(lots(search(b, min_g=1))), 0)

    # --- bidding ---------------------------------------------------------------------
    b_afro, _ = purse(b)
    got = op(b, auction.BID, gun, 99)
    check("under the start: 9", got, [("cmdAck", {"res": 9})])
    got = op(b, auction.BID, gun, 100)
    check("the start itself: accepted, purse follows",
          names_of(got)[:2], ["cmdAck", "userInfo_Player"])
    check("res 0", got[0][1], {"res": 0})
    check("the bid is held", named(got, "userInfo_Player")[0]["afro"], b_afro - 100)
    got = op(a, auction.BID, gun, 200)
    check("the seller cannot bid", (got[0], names_of(got)[1:]),
          (("cmdAck", {"res": 3}), ["userMsg"]))
    got = op(cc, auction.BID, gun, 105)
    check("less than last + 10%: 9", got, [("cmdAck", {"res": 9})])
    got = op(cc, auction.BID, gun, 110)
    check("Carol outbids", got[0], ("cmdAck", {"res": 0}))
    got = b.frames()
    check("Bob hears of a letter at once", names_of(got), ["lsml"])
    check("from the auction house", named(got, "lsml")[0]["name"], [mail.SYSTEM_NAME])
    lot = lots(search(a, cat=auction.MY_LOTS))[0]
    check("the seller sees the new bid and who made it",
          (lot["a_bid"], lot["bidder"]), (110, "Carol"))
    rc, ct, got = unpack_newest(b)
    check("the refund letter carries Bob's 100", rc["afro"], 100)
    check("and pays it on uldml", named(got, "userInfo_Player")[0]["afro"], b_afro)

    # --- buyout ------------------------------------------------------------------------
    c_afro, _ = purse(cc)
    got = op(b, auction.BUYOUT, gun)
    check("buyout: one cmdAck 0, the purse", names_of(got)[:2], ["cmdAck", "userInfo_Player"])
    check("res 0", got[0][1], {"res": 0})
    check("500 paid", named(got, "userInfo_Player")[0]["afro"], b_afro - 500)
    check("and Bob's letter with the gun is pushed to him",
          "lsml" in names_of(got) or "lsml" in names_of(b.frames()), True)
    check("Carol is refunded by letter", "lsml" in names_of(cc.frames()), True)
    check("Alice is paid by letter", "lsml" in names_of(a.frames()), True)
    got = op(cc, auction.BID, gun, 1000)
    check("the lot is gone: 40", got, [("cmdAck", {"res": 40})])
    check("and gone from the search", named(search(b), "ah_sresult")[0]["count"], 0)

    # --- a letter from the house cannot be thrown away with its parcel ----------
    lid = newest(b)
    b.send("rmvml;id=x%s;" % lid)
    got = b.frames()
    check("deleting the purchase unopened: refused with 2 "
          "(\"Недопустимое действие\"), reason in chat",
          (got[0], names_of(got)[1:]), (("cmdAck", {"res": 2}), ["userMsg"]))
    check("and it is still in the box", lid in inbox_ids(b), True)
    b.send("sndml;to=@%s@;subj=@re@;type=0;body=@hi@;afro=0;gold=0;" % mail.SYSTEM_NAME)
    check("a reply to the house finds nobody: 34", b.frames(),
          [("cmdAck", {"res": 34})])

    rc, ct, got = unpack_newest(b)
    check("the letter from the auction holds the gun",
          (rc["from"], items.catalogue()[inventory.parse_oid(str(rc["items"][0]))[1]][0]),
          (mail.SYSTEM_NAME, items.FIRE_ARM))
    check("taken into the bag as a new instance", ct["code"][0], 1)
    b.send("rmvml;id=x%s;" % lid)
    check("emptied, it goes like any other", b.frames(), [("cmdAck", {"res": 0})])
    check("gone from the box", lid in inbox_ids(b), False)
    raw = storage.connect(DB)
    left = raw.execute("SELECT COUNT(*) c FROM mail WHERE id = ?",
                       (int(lid),)).fetchone()["c"]
    raw.close()
    check("and from the table: the house keeps no outbox copy", left, 0)
    rc, ct, got = unpack_newest(a)
    check("Alice's payment: 500 afro", rc["afro"], 500)
    rc, ct, got = unpack_newest(cc)
    check("Carol's 110 back", (rc["afro"], named(got, "userInfo_Player")[0]["afro"]),
          (110, c_afro + 110))

    # --- take off, sell to the bidder --------------------------------------------------
    stack = give(a, ROUNDS, 200)
    afro1, _ = purse(a)
    got = create(a, stack, hours=168, a_bid=50)
    check("a stack listed", got[0], ("cmdAck", {"res": 0}))
    check("its commission counts all 200 rounds, as the window shows it",
          named(got, "userInfo_Player")[0]["afro"],
          afro1 - auction.afro_fee(items.params_of(ROUNDS)["cost"], 200, 168))
    got = op(b, auction.TAKEOFF, stack)
    check("only the seller takes a lot off: 40 for anyone else",
          got, [("cmdAck", {"res": 40})])
    got = op(a, auction.TAKEOFF, stack)
    check("taken off", got[0], ("cmdAck", {"res": 0}))
    rc, ct, got = unpack_newest(a)
    check("the stack comes back by letter, all 200",
          rc["body"].startswith("=?HS:200?="), True)
    gun2 = give(a, BERETTA)
    create(a, gun2, hours=168, a_bid=100)
    got = op(a, auction.SELL, gun2)
    check("selling with no bid: refused", got[0], ("cmdAck", {"res": 3}))
    op(cc, auction.BID, gun2, 150)
    got = op(a, auction.SELL, gun2)
    check("sold to the bidder at her bid", got[0], ("cmdAck", {"res": 0}))
    rc, _, _ = unpack_newest(cc)
    check("the gun goes to Carol", len(rc["items"]), 1)
    rc, _, _ = unpack_newest(a)
    check("150 to Alice", rc["afro"], 150)

    # --- a lot with a bid taken off: the bid goes back ----------------------------
    gun6 = give(a, BERETTA)
    create(a, gun6, hours=168, a_bid=100)
    b_afro, _ = purse(b)
    op(b, auction.BID, gun6, 100)
    got = op(a, auction.TAKEOFF, gun6)
    check("a lot carrying a bid may still be taken off", got[0], ("cmdAck", {"res": 0}))
    rc, _, got = unpack_newest(b)
    check("and the bidder gets the bid back by letter",
          (rc["afro"], named(got, "userInfo_Player")[0]["afro"]), (100, b_afro))
    rc, _, _ = unpack_newest(a)
    check("the gun back to Alice", (rc["from"], len(rc["items"])), (mail.SYSTEM_NAME, 1))

    # --- the clock -------------------------------------------------------------------------
    gun3 = give(a, BERETTA)
    gun4 = give(a, BERETTA)
    create(a, gun3, hours=24, a_bid=100)
    create(a, gun4, hours=24, a_bid=100)
    op(b, auction.BID, gun4, 120)
    check("two lots: one ah_lot and exactly one DI each",
          names_of(search(a, cat=auction.MY_LOTS)),
          ["ah_sresult", "ah_lot", "ss_di_firearm", "ah_lot", "ss_di_firearm"])
    a.send("chkml;mode=0;")
    before = len(named(a.frames(), "lsml")[0]["subj"])
    time.sleep(24 * HOUR + 1.0)
    check("both ran out", named(search(a, cat=auction.MY_LOTS), "ah_sresult")[0]["count"], 0)
    rc, _, _ = unpack_newest(b)
    check("the bid one went to Bob", (rc["from"], len(rc["items"])), (mail.SYSTEM_NAME, 1))
    a.send("chkml;mode=0;")
    new = named(a.frames(), "lsml")[0]["subj"][before:]
    check("Alice got the unsold one back and 120 for the other",
          sorted(s.split("«")[0] for s in new),
          ["Аукцион: ", "Аукцион: продан "])

    # --- part of a stack ---------------------------------------------------------------
    # "Сколько штук положить?" 50 of 200: exchangeDropAck sends ss_heap_c
    # with the pieces that STAY (heapNum = obj.left), and separateAck then
    # lists the original id, which is left holding the 50.
    stack = give(a, ROUNDS, 200)
    a.send("ss_heap_c;num=150;obj=x%s;" % stack)
    got = a.frames()
    check("the split: one cmdAck 0", [p for n, p in got if n == "cmdAck"], [{"res": 0}])
    rest = str(named(got, "ss_obj_status")[0]["obj"])
    check("150 in a new stack, 50 left under the old id",
          sorted((str(p["obj"]), p["size"]) for p in named(got, "ss_di_heap")),
          sorted([(rest, 150), (stack, 50)]))
    afro2, _ = purse(a)
    got = create(a, stack, hours=168, a_bid=30)
    check("the original listed", got[0], ("cmdAck", {"res": 0}))
    check("and only it leaves the bag", named(got, "ss_obj_status"),
          [{"obj": stack, "status": 0}])
    check("the commission is for the 50 alone",
          named(got, "userInfo_Player")[0]["afro"],
          afro2 - auction.afro_fee(items.params_of(ROUNDS)["cost"], 50, 168))
    check("the 150 stay in the bag", (rest in bag(a), stack in bag(a)), (True, False))
    got = search(b, cat=items.AMMO, subcat=5)
    check("the lot shows its 50 rounds by its DI",
          [(str(p["obj"]), p["size"]) for p in named(got, "ss_di_heap")], [(stack, 50)])
    op(a, auction.TAKEOFF, stack)
    rc, _, _ = unpack_newest(a)
    check("taken off, 50 come back", rc["body"].startswith("=?HS:50?="), True)

    # --- a loaded gun goes with its rounds ---------------------------------------
    gun7 = give(a, BERETTA)
    clip = give(a, ROUNDS, CLIP)
    a.send("ss_use;type=%d;obj=x%s;target=x%s;" % (inventory.USE_LOAD, gun7, clip))
    loaded = a.frames(items.params_of(BERETTA)["reload_time"] / 1000.0 + 1)
    check("loaded", loaded[0], ("cmdAck", {"res": 0}))
    check("reload completed before listing",
          [p['ammo_count'] for p in named(loaded, 'ss_di_firearm')], [CLIP])
    got = create(a, gun7, hours=168, a_bid=100, a_buyout=300)
    check("listed after reload", got[0], ("cmdAck", {"res": 0}))
    check("and the reload no longer reports a gun that is gone",
          [p for n, p in a.frames(2.0) if n == "ss_di_firearm"], [])
    di = named(search(b, name="берет"), "ss_di_firearm")
    check("the lot shows the magazine full",
          [(str(p["obj"]), p["ammo_count"], p["ammo_type"]) for p in di],
          [(gun7, CLIP, ROUNDS)])
    op(b, auction.BUYOUT, gun7)
    rc, ct, got = unpack_newest(b)
    mine = str(ct["item"][0])
    b.send("ss_get_di;obj=x%s;" % mine)
    di = named(b.frames(), "ss_di_firearm")[0]
    check("and Bob's new pistol arrives loaded",
          (di["ammo_count"], di["ammo_type"]), (CLIP, ROUNDS))
    unpack_newest(a)

    # A pending reload has not moved ammunition. Listing the gun cancels it
    # and must not put the seller's rounds into a buyer's future weapon.
    pending = give(a, BERETTA)
    reserve = give(a, ROUNDS, CLIP)
    a.send("ss_use;type=%d;obj=x%s;target=x%s;" % (inventory.USE_LOAD, pending, reserve))
    a.frames(0.1)
    got = create(a, pending, hours=168, a_bid=100, a_buyout=300)
    check("listing mid-reload acknowledges once", named(got, 'cmdAck'), [{'res': 0}])
    check("listing cancels the pending bar", named(got, 'actionCancel'), [{'release': 1}])
    check("cancelled reload never reports a loaded gun",
          named(a.frames(items.params_of(BERETTA)['reload_time'] / 1000.0 + 1), 'ss_di_firearm'), [])
    a.send("ss_get_di;obj=x%s;" % reserve)
    check("cancelled reload leaves ammunition with the seller",
          named(a.frames(), 'ss_di_heap')[0]['size'], CLIP)
    di = named(search(b, name="берет"), "ss_di_firearm")
    check("the mid-reload lot stays empty",
          [(str(p['obj']), p['ammo_count'], p['ammo_type']) for p in di], [(pending, 0, 0)])
    op(a, auction.TAKEOFF, pending)
    unpack_newest(a)

    # --- a gold lot, from a client that can make one ------------------------------
    gun8 = give(a, BERETTA)
    got = create(a, gun8, hours=168, g_bid=100, g_buyout=300)
    check("a gold lot is accepted, with no commission up front",
          names_of(got), ["cmdAck", "ss_obj_status"])
    lot = [l for l in lots(search(b)) if l["obj"] == gun8][0]
    check("it shows the gold pair only",
          (lot.get("g_bid"), lot.get("g_buyout"), "a_bid" in lot), (100, 300, False))
    chat(b, "/money 0 1000")
    _, b_gold = purse(b)
    check("under the gold start: 9", op(b, auction.BID, gun8, 50), [("cmdAck", {"res": 9})])
    got = op(b, auction.BUYOUT, gun8)
    check("bought out in gold", (got[0], named(got, "userInfo_Player")[0]["gold"]),
          (("cmdAck", {"res": 0}), b_gold - 300))
    rc, _, _ = unpack_newest(a)
    check("the seller gets the price less the gold commission, by letter",
          rc["gold"], 300 - auction.gold_fee(300, 168))
    unpack_newest(b)

    # --- at most MAX_LOTS at once ------------------------------------------------
    up = [give(a, BERETTA) for _ in range(MAX_LOTS + 1)]
    got = [create(a, g, hours=168, a_bid=100)[0] for g in up[:MAX_LOTS]]
    check("%d lots go up" % MAX_LOTS, got, [("cmdAck", {"res": 0})] * MAX_LOTS)
    got = create(a, up[-1], hours=168, a_bid=100)
    check("one more is refused, reason in chat",
          (got[0], names_of(got)[1:]), (("cmdAck", {"res": 3}), ["userMsg"]))
    check("and stays in the bag", up[-1] in bag(a), True)
    for g in up[:MAX_LOTS]:
        op(a, auction.TAKEOFF, g)

    # --- no money for the commission -----------------------------------------------------
    chat(a, "/money -1000000 0")
    gun5 = give(a, BERETTA)
    got = create(a, gun5, a_bid=100)
    check("no money for the commission: 9", got, [("cmdAck", {"res": 9})])

    # --- the house's name at the character screen ----------------------------------
    e = Client(connect())
    e.send("hello;minor=2;major=0;")
    e.send("login;hash=@%s@;" % CRED["eve"])
    e.frames()
    for name in ("Аукцион", "аукцион", "\x41укцион"):     # the last: Latin A
        e.send("newPers;res=1;sex=0;name=@%s@;" % name)
        check("newPers %r: the name is taken (6)" % name, e.frames(),
              [("cmdAck", {"res": 6})])
    e.send("newPers;res=1;sex=0;name=@Eve@;")
    check("an ordinary one is not", e.frames()[0], ("cmdAck", {"res": 0}))
finally:
    srv.terminate()
    try:
        srv.wait(5)
    except subprocess.TimeoutExpired:
        srv.kill()

bad = [l for l in _log if "!!" in l or "Traceback" in l]
check("no handler failed on the way", bad, [])
if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("\nall auction checks passed")
