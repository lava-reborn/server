#!/usr/bin/env python3
"""Create, delete and re-password game accounts from outside the game.

The client never sends a password: it sends md5(cp1251(password + login)) and
that digest is both the credential and the account key (accounts.hash, UNIQUE).
Two consequences shape this tool:

* An account cannot be renamed. The login is baked into the digest, so a new
  name means a new digest, which means the password has to be known in the
  clear. Delete and create is the honest way to change an admin's name.
* A password cannot be recovered, only replaced -- `passwd` recomputes the
  digest from a new one.

Deleting an account is not one row. A character hangs items, stats, quests,
marks and letters off itself, and letters are shared: a row in mail belongs to
the sender's outbox and the addressee's inbox at once, so deleting a character
takes its sent letters out of other players' inboxes too. Its lots on the
auction close, a bid on one going back to its bidder by mail, and its own
bids on other lots are struck out. A clan it heads passes to the member the
game itself would pick (accounts.clan_successor), or is disbanded when
nobody else is in it, its treasury going with the account. The count is
printed before anything is touched, and what was actually done after: the
game may settle a lot in between, and then the tool leaves it alone.

    python3 tools/admin_account.py list
    python3 tools/admin_account.py create Archivist --random
    python3 tools/admin_account.py delete OldName --yes
    python3 tools/admin_account.py passwd Archivist

Clans are looked at here and changed through the game (see "clans" below):

    python3 tools/admin_account.py clans
    python3 tools/admin_account.py clan Волки
    python3 tools/admin_account.py clan-rename Волки --name "Серые волки"
    python3 tools/admin_account.py clan-head Волки --char Боб
    python3 tools/admin_account.py clan-kick 7 --char Ева
    python3 tools/admin_account.py clan-treasury Волки --afro -500
    python3 tools/admin_account.py clan-disband Волки --payout Боб --yes

And the warehouses clans hold (server/holdings.py), the same way:

    python3 tools/admin_account.py holdings
    python3 tools/admin_account.py clan-hold Волки --site wh_sever
    python3 tools/admin_account.py clan-release Волки --site wh_sever

Where the data lives is the environment's business, exactly as it is for the
server: LAVA_DB_URL picks Postgres, its absence picks the SQLite file (--db,
or data/lava.db next to this checkout).

The password is read from a terminal prompt by default. --password-stdin takes
the first line of standard input instead, for scripts; --random invents one and
prints it on the last line of the report, for the caller to capture into a file
rather than a shell history.
"""
import argparse
import getpass
import json
import os
import secrets
import string
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))

import accounts  # noqa: E402  (needs the path above)
import storage  # noqa: E402

# Everything that hangs off a character, in the order the foreign keys allow.
# mail is first and counted twice on purpose: a character is on both sides of
# a letter, and both sides have to go before characters can.
CHILDREN = (
    ("mail", "to_char = ? OR from_char = ?", 2),
    ("map_marks", "char_id = ?", 1),
    ("char_quests", "char_id = ?", 1),
    ("char_quests_done", "char_id = ?", 1),
    # Trophies (server/trophies.py): the collection, the entries deleted
    # from it (kept, nobody's, for the hour's pay mark of the killer), and
    # the words of a trophy that is a thing in this character's hands --
    # before items, whose rows that last part is found by. A trophy of its
    # kill in another player's hands, or another's kill of it in another's
    # collection, is that player's and stays.
    ("trophies", "owner = ? OR (killer_id = ? AND registered_at IS NOT NULL)"
                 " OR (registered_at IS NULL AND uniq IN"
                 " (SELECT uniq FROM items WHERE char_id = ?))", 3),
    ("items", "char_id = ?", 1),
    ("char_stats", "char_id = ?", 1),
    ("online", "char_id = ?", 1),
    # The membership, once hand_over_clans has passed a clan this character
    # heads to somebody else (or disbanded it). The id comes back for the
    # next character in SQLite, and a row left under it would make him a
    # member with the dead one's rights.
    ("clan_members", "char_id = ?", 1),
)

# The auction is not in CHILDREN: a lot is not only its seller's. Its
# characters.id is INTEGER PRIMARY KEY without AUTOINCREMENT, so the next
# character made after the last one is deleted takes the same id -- and with
# it every lot still naming that id, which it could take off (the item by
# mail) or sell to the bidder for money. A lot of theirs is closed with the
# account, the bid on it going back to its bidder by mail; a bid of theirs on
# another player's lot is struck out, the money going with the account as
# its purse does. auction.py writes these letters; this tool does not import
# it, or it would need the client's resources (names reads them at import),
# so its two constants are repeated here and tools/test_admin_account.py
# holds them to mail.py's.
SYSTEM_SENDER = 0        # mail.SYSTEM_SENDER: letters from the house
LETTER = 0               # mail.LETTER


def money_text(amount, currency):
    """auction.money_text: currency 1 is gold in hundredths."""
    if currency == 1:
        return "%.2f G" % (amount / 100.0)
    return "%d афро" % amount


def auction_rows(db, char_ids):
    """(lots these characters sell, other players' lots they hold the bid
    on), each a list of rows."""
    selling, bidding = [], []
    for cid in char_ids:
        selling += db.execute("SELECT * FROM auction_lots WHERE seller = ?"
                              " ORDER BY id", (cid,)).fetchall()
        bidding += [r for r in db.execute(
            "SELECT * FROM auction_lots WHERE bidder = ? ORDER BY id",
            (cid,)).fetchall() if r["seller"] not in char_ids]
    return selling, bidding


def close_auction(db, char_ids):
    """No commit: cmd_delete commits it with the rest. Returns (lots
    closed, refund letters filed, bids struck out).

    Nothing here acts on what auction_rows read for the report. The game
    server goes on settling lots meanwhile -- one runs out, is bought out,
    gets a new bid -- and a refund written from that earlier read paid a
    bidder who had the item already, or returned a bid that had been
    beaten and refunded since. So each lot is taken as the DELETE removes
    it (RETURNING), and its refund is written from that row or not at all;
    a bid is struck out by an UPDATE that names its bidder, so a bid made
    since by somebody else stays. Both hold the row until the commit, and
    the server's own write on it, which goes first in its transaction too,
    then waits and finds the lot gone -- or, when the server says which bid
    its letters were written from (`was`), finds that bid struck out -- and
    files nothing (accounts.Store.auction_close, auction_rebid).
    """
    closed = refunds = struck = 0
    for cid in char_ids:
        for lot in db.execute("DELETE FROM auction_lots WHERE seller = ?"
                              " RETURNING *", (cid,)).fetchall():
            closed += 1
            if not lot["bidder"] or lot["bidder"] in char_ids:
                continue
            db.insert(
                "INSERT INTO mail (to_char, from_char, type, subject, body,"
                " sent_at, afro, gold, items_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lot["bidder"], SYSTEM_SENDER, LETTER,
                 "Аукцион: ставка возвращена",
                 "Лот снят с торгов: аккаунт продавца удалён. Возвращаем "
                 "вашу ставку %s." % money_text(lot["bid"], lot["currency"]),
                 int(time.time()),
                 lot["bid"] if lot["currency"] != 1 else 0,
                 lot["bid"] if lot["currency"] == 1 else 0, "[]"),
                returning="id")
            refunds += 1
    for cid in char_ids:
        # The account's own lots are gone by now, so what is left with its
        # bid on it is somebody else's.
        struck += db.execute("UPDATE auction_lots SET bid = 0, bidder = 0,"
                             " bidder_name = '' WHERE bidder = ?",
                             (cid,)).rowcount
    return closed, refunds, struck


# A character seen by the game this recently is playing right now; deleting
# them underneath a live session would leave the session writing to rows that
# are no longer there. online.seen_at is rewritten once a second.
ONLINE_WINDOW = 120


def open_db(path):
    """The same database the server opens, without touching its schema."""
    return storage.connect(path or accounts.DB_PATH)


def account_row(db, login):
    return db.execute("SELECT * FROM accounts WHERE login = ?",
                      (login,)).fetchone()


def characters_of(db, account_id):
    return db.execute(
        "SELECT id, name, level FROM characters WHERE account_id = ?"
        " ORDER BY slot", (account_id,)).fetchall()


def playing_now(db, char_ids):
    """Which of these characters the game has seen in the last two minutes."""
    live = []
    for char_id in char_ids:
        row = db.execute("SELECT seen_at FROM online WHERE char_id = ?",
                         (char_id,)).fetchone()
        if row and int(time.time()) - int(row["seen_at"]) < ONLINE_WINDOW:
            live.append(char_id)
    return live


def has_table(db, table):
    """Whether the database has this table: one no server of today has
    opened yet (the tool never builds the schema itself) may lack the
    newer ones, the clans' say."""
    return bool(db.columns(table))


def count(db, table, where, args):
    if not has_table(db, table):
        return 0
    row = db.execute("SELECT count(*) AS n FROM %s WHERE %s" % (table, where),
                     args).fetchone()
    return int(row["n"])


def clan_rows(db, char_ids):
    """The clans these characters head, and what deleting them does to each:
    [(char_id, clan_id, clan name, successor id or None, treasury)]. A
    member who is not the head just leaves (CHILDREN). The successor is
    picked as the game picks it (accounts.clan_successor), never among the
    account's own characters, who go too."""
    if not has_table(db, "clan_members"):
        return []
    out = []
    for cid in char_ids:
        row = db.execute("SELECT k.id, k.name, k.head, k.afro FROM clan_members m"
                         " JOIN clans k ON k.id = m.clan_id WHERE m.char_id = ?",
                         (cid,)).fetchone()
        if row is None or int(row["head"]) != int(cid):
            continue
        out.append((cid, int(row["id"]), row["name"],
                    accounts.clan_successor(db, row["id"], char_ids), int(row["afro"] or 0)))
    return out


def hand_over_clans(db, char_ids):
    """No commit: cmd_delete commits it with the rest. Each clan one of
    these characters heads passes on, or is disbanded with nobody left --
    its treasury then gone with the account, as the purse is (a 'disband'
    row in clan_ledger). Taken from the writes, not from what clan_rows
    read for the report: the game may have changed the clan in between.
    Returns [(clan_id, new head or None, treasury lost)].

    The game reads clans from the database on every command and caches
    nothing, so it follows at once; clients online see the new head or the
    clan gone only at their next login, which an admin tool can afford."""
    if not has_table(db, "clan_members"):
        return []
    done = []
    for cid in char_ids:
        out = accounts.clan_hand_over(db, cid, exclude=char_ids)
        if out is not None:
            done.append(out)
    return done


def read_password(args, what):
    if args.random:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(20)), True
    if args.password_stdin:
        line = sys.stdin.readline()
        if not line.strip():
            sys.exit("empty password on stdin")
        return line.rstrip("\n"), False
    if not sys.stdin.isatty():
        sys.exit("no terminal to ask for a password on; "
                 "use --password-stdin or --random")
    first = getpass.getpass("%s: " % what)
    if len(first) < 4:
        sys.exit("password shorter than four characters")
    if first != getpass.getpass("again: "):
        sys.exit("the two passwords differ")
    return first, False


# --- commands -------------------------------------------------------------

def cmd_list(db, args):
    admins = {s.strip() for s in os.environ.get("LAVA_ADMINS", "").split(",")
              if s.strip()}
    rows = db.execute(
        "SELECT a.id, a.login, a.banned, a.created FROM accounts a"
        " ORDER BY a.id").fetchall()
    print("%-5s %-22s %-7s %s" % ("id", "login", "banned", "characters"))
    for row in rows:
        chars = characters_of(db, row["id"])
        mark = " *admin" if row["login"] in admins else ""
        print("%-5s %-22s %-7s %s%s"
              % (row["id"], row["login"], int(row["banned"] or 0),
                 ", ".join("%s (%s)" % (c["name"], c["level"]) for c in chars)
                 or "-", mark))
    if admins:
        print("\nLAVA_ADMINS: %s" % ", ".join(sorted(admins)))
    else:
        print("\nLAVA_ADMINS is empty in this environment: the panel lets "
              "nobody in.")
    return 0


def cmd_create(db, args):
    if account_row(db, args.login):
        sys.exit("login %r already exists" % args.login)
    if len(args.login) < 3 or len(args.login) > 20:
        sys.exit("the game accepts logins of 3 to 20 characters")
    password, invented = read_password(args, "password for %s" % args.login)
    cred = accounts.credential(args.login, password)
    if db.execute("SELECT id FROM accounts WHERE hash = ?",
                  (cred,)).fetchone():
        # The digest is UNIQUE and it is the credential: two accounts sharing
        # one could not be told apart at login.
        sys.exit("that login and password already hash to an existing account")
    new_id = db.insert(
        "INSERT INTO accounts (login, hash, created) VALUES (?, ?, ?)",
        (args.login, cred, int(time.time())), returning="id")
    db.commit()
    print("created account %s (id %s)" % (args.login, new_id))
    print("no character yet: the client makes one on first login")
    if invented:
        print("password: %s" % password)
    return 0


def cmd_delete(db, args):
    row = account_row(db, args.login)
    if not row:
        sys.exit("no account named %r" % args.login)
    chars = characters_of(db, row["id"])
    char_ids = [c["id"] for c in chars]

    print("account %s (id %s, created %s)"
          % (row["login"], row["id"],
             time.strftime("%Y-%m-%d", time.localtime(int(row["created"])))))
    for char in chars:
        print("  character %s (id %s, level %s)"
              % (char["name"], char["id"], char["level"]))
    total = 0
    for table, where, repeats in CHILDREN:
        n = sum(count(db, table, where, (cid,) * repeats) for cid in char_ids)
        total += n
        if n:
            print("  %-18s %s rows" % (table, n))
    selling, bidding = auction_rows(db, char_ids)
    if selling:
        backed = sum(1 for r in selling if r["bidder"] and r["bidder"] not in char_ids)
        print("  %-18s %s lots on sale go with the account; %s bids on them "
              "go back to their bidders by mail" % ("auction_lots", len(selling), backed))
    if bidding:
        print("  %-18s %s bids on other players' lots are struck out; the "
              "lots stay" % ("auction_lots", len(bidding)))
    actions = count(db, "admin_actions", "admin = ?", (args.login,))
    if actions:
        print("  %-18s %s rows kept: the panel's log is history, and the "
              "name in it stays" % ("admin_actions", actions))
    names = {c["id"]: c["name"] for c in chars}
    for cid, clan_id, clan_name, heir, afro in clan_rows(db, char_ids):
        if heir is not None:
            heir_row = db.execute("SELECT name FROM characters WHERE id = ?",
                                  (heir,)).fetchone()
            print("  %-18s %s heads «%s» (id %s): it passes to %s"
                  % ("clans", names.get(cid, cid), clan_name, clan_id,
                     heir_row["name"] if heir_row else heir))
        else:
            print("  %-18s %s heads «%s» (id %s) with nobody else in it: it is"
                  " disbanded, and the %s afro of its treasury go with the account"
                  % ("clans", names.get(cid, cid), clan_name, clan_id, afro))

    live = playing_now(db, char_ids)
    if live and not args.force:
        sys.exit("character %s is in the game right now; stop the server or "
                 "pass --force" % live[0])

    if not args.yes:
        print("\nnothing deleted: pass --yes to go through with it")
        return 1

    closed, refunds, struck = close_auction(db, char_ids)
    handed = hand_over_clans(db, char_ids)
    for table, where, repeats in CHILDREN:
        if not has_table(db, table):
            continue
        for cid in char_ids:
            db.execute("DELETE FROM %s WHERE %s" % (table, where),
                       (cid,) * repeats)
    if char_ids:
        db.execute("DELETE FROM characters WHERE account_id = ?", (row["id"],))
    # The links the account was sent (email_tokens): useless without it,
    # and an address of the player's besides.
    if has_table(db, "email_tokens"):
        db.execute("DELETE FROM email_tokens WHERE account_id = ?", (row["id"],))
    db.execute("DELETE FROM accounts WHERE id = ?", (row["id"],))
    db.commit()
    print("\ndeleted: 1 account, %s characters, %s dependent rows"
          % (len(chars), total))
    if selling or bidding or closed or struck:
        print("auction: %s lots closed, %s bids refunded by mail, %s bids struck out"
              % (closed, refunds, struck))
        if (closed, struck) != (len(selling), len(bidding)):
            print("  (not what was counted above: the game settled or re-bid "
                  "some of them in between, and these are what was done)")
    for clan_id, heir, afro in handed:
        if heir is not None:
            print("clan %s: handed over to character %s" % (clan_id, heir))
        else:
            print("clan %s: disbanded, %s afro of its treasury gone" % (clan_id, afro))
    return 0


def cmd_passwd(db, args):
    row = account_row(db, args.login)
    if not row:
        sys.exit("no account named %r" % args.login)
    password, invented = read_password(args, "new password for %s" % args.login)
    cred = accounts.credential(args.login, password)
    clash = db.execute("SELECT login FROM accounts WHERE hash = ? AND id <> ?",
                       (cred, row["id"])).fetchone()
    if clash:
        sys.exit("that password collides with account %r" % clash["login"])
    db.execute("UPDATE accounts SET hash = ? WHERE id = ?", (cred, row["id"]))
    # Whoever is playing on it goes: the game's admin queue, as the panel
    # and a reset by mail do it (server/email_flow.py kick_out). Sessions of
    # the site, the forum and the panel carry a mark of the password and
    # end by themselves.
    db.execute(
        "INSERT INTO admin_actions (made_at, admin, kind, char_id, account_id, args_json)"
        " VALUES (?, ?, 'kick', NULL, ?, ?)",
        (int(time.time()), "Lava Reborn", row["id"],
         json.dumps({"reason": "Пароль аккаунта сменён. Войдите с новым паролем."},
                    ensure_ascii=False)))
    db.commit()
    print("password changed for %s; anyone playing on it is put out" % args.login)
    if invented:
        print("password: %s" % password)
    return 0


# --- clans ------------------------------------------------------------------
#
# This tool only LOOKS at a clan by itself. A change -- rename, disband, a new
# head, the treasury, a kick, a warehouse held or released -- is queued as an
# admin_actions row of kind 'clan', the same the panel writes, and the game
# server carries it out
# (server/clan_admin.py). Two reasons, the panel's own. A member who is
# online has a client that was told his clan, his rights and his roster, and
# a Character whose purse Character.save writes back at logout: only the
# game process can tell the one and pay into the other. And the checks -- the
# name's rules and uniqueness by skeleton, who is a member, what the
# treasury holds -- live in the game's modules, which this tool may not
# import (names reads the client's files at import); in one place they
# cannot disagree. The game reads clans from the database on every command
# and caches nothing, so a member offline finds the change at his login.
#
# The tool then waits for the game's answer and prints it. With no game
# running (the heartbeat the game writes every second is stale), the order
# stays queued and is carried out at the game's next start; the tool says
# so and exits 2, as it does when the answer does not come in --wait.

CLAN_OPS = {"clan-rename": "rename", "clan-disband": "disband", "clan-head": "head",
            "clan-treasury": "treasury", "clan-kick": "kick", "clan-hold": "hold",
            "clan-release": "release"}
# The warehouses a clan can hold, read from the file the game reads
# (server/holdings.py), not through the game's module: the tool imports none
# of the game's content.
HOLDINGS = os.path.join(ROOT, "data", "holdings.json")
# A heartbeat older than this is a game that is not running: the panel's
# own threshold.
BEAT_FRESH = 15
# accounts.clan_rank's ranks as the panel names them.
RANKS = {4: "head", 2: "officer", 1: "recruiter", 0: "member"}


def find_clan(db, ref):
    """A clan row by its name -- spaces and case aside -- or by its id.
    The game's own lookup folds lookalike letters too (mail._skeleton);
    the tool resolves to an id before it queues, so what it names is what
    the game acts on."""
    if not has_table(db, "clans") or ref is None:
        return None
    text = str(ref).strip()
    want = " ".join(text.split()).casefold()
    for row in db.execute("SELECT * FROM clans ORDER BY id").fetchall():
        if " ".join(str(row["name"]).split()).casefold() == want:
            return row
    if text.isdigit():
        return db.execute("SELECT * FROM clans WHERE id = ?", (int(text),)).fetchone()
    return None


def find_char(db, ref):
    """A character by its exact name, or by its id."""
    text = str(ref).strip()
    row = db.execute("SELECT id, name FROM characters WHERE name = ?", (text,)).fetchone()
    if row is None and text.isdigit():
        row = db.execute("SELECT id, name FROM characters WHERE id = ?",
                         (int(text),)).fetchone()
    return row


def char_name(db, char_id):
    row = db.execute("SELECT name FROM characters WHERE id = ?", (char_id,)).fetchone()
    return row["name"] if row else "#%s" % char_id


def day(when):
    return time.strftime("%Y-%m-%d", time.localtime(int(when))) if when else "-"


def game_beat(db):
    """When the game last wrote its heartbeat, or None."""
    if not has_table(db, "heartbeat"):
        return None
    row = db.execute("SELECT at FROM heartbeat WHERE id = 1").fetchone()
    return int(row["at"]) if row else None


def queue_clan(db, admin, payload):
    """One admin_actions row of kind 'clan'; its id."""
    new_id = db.insert(
        "INSERT INTO admin_actions (made_at, admin, kind, char_id, account_id,"
        " args_json) VALUES (?, ?, 'clan', NULL, NULL, ?)",
        (int(time.time()), admin, json.dumps(payload, ensure_ascii=False)),
        returning="id")
    db.commit()
    return new_id


def wait_done(db, action_id, wait):
    """Print the game's answer to a queued order: 0 when it came, 2 when
    it did not (no game, or not in time) -- the order is queued either way."""
    beat = game_beat(db)
    if beat is None or time.time() - beat > BEAT_FRESH:
        print("the game server is not running (%s): the order waits in the queue"
              " and is carried out when it starts; its result will be in the"
              " panel's log" % ("no heartbeat ever" if beat is None
                                else "last heartbeat %ds ago" % (time.time() - beat)))
        return 2
    end = time.time() + wait
    while True:
        # A new snapshot each time, and no read left holding the table.
        db.commit()
        row = db.execute("SELECT done_at, result FROM admin_actions WHERE id = ?",
                         (action_id,)).fetchone()
        if row is not None and row["done_at"] is not None:
            print("done: %s" % row["result"])
            return 0
        if time.time() >= end:
            break
        time.sleep(0.2)
    print("no answer from the game in %gs: the order stays queued (admin action %s)"
          % (wait, action_id))
    return 2


def cmd_clans(db, args):
    if not has_table(db, "clans"):
        print("no clans table: no server of today has opened this database yet")
        return 0
    counts = {}
    for row in db.execute("SELECT clan_id, count(*) AS n FROM clan_members"
                          " GROUP BY clan_id").fetchall():
        counts[int(row["clan_id"])] = int(row["n"])
    rows = db.execute("SELECT * FROM clans ORDER BY id").fetchall()
    print("%-6s %-30s %-20s %-8s %-10s %s" % ("id", "clan", "head", "members",
                                               "treasury", "founded"))
    for row in rows:
        print("%-6s %-30s %-20s %-8s %-10s %s"
              % (row["id"], row["name"], char_name(db, row["head"]),
                 counts.get(int(row["id"]), 0), row["afro"], day(row["created_at"])))
    if not rows:
        print("(none)")
    return 0


def cmd_clan(db, args):
    clan = find_clan(db, args.login)
    if clan is None:
        sys.exit("no clan named or numbered %r" % args.login)
    print("clan %s (id %s), founded %s, treasury %s afro"
          % (clan["name"], clan["id"], day(clan["created_at"]), clan["afro"]))
    print("\n%-20s %-20s %-10s %-7s %-10s %s" % ("member", "post", "rank", "perm",
                                                  "joined", "last seen"))
    for row in db.execute(
            "SELECT m.char_id, m.perm, m.post, m.joined_at, c.name, c.seen_at"
            " FROM clan_members m JOIN characters c ON c.id = m.char_id"
            " WHERE m.clan_id = ? ORDER BY m.joined_at, m.char_id", (clan["id"],)).fetchall():
        print("%-20s %-20s %-10s 0x%04X  %-10s %s"
              % (row["name"], row["post"] or "-", RANKS[accounts.clan_rank(row["perm"])],
                 int(row["perm"]), day(row["joined_at"]),
                 time.strftime("%Y-%m-%d %H:%M", time.localtime(int(row["seen_at"])))
                 if row["seen_at"] else "never"))
    ledger = db.execute("SELECT * FROM clan_ledger WHERE clan_id = ? ORDER BY id DESC"
                        " LIMIT 20", (clan["id"],)).fetchall()
    print("\ntreasury journal, newest first:")
    for row in ledger:
        print("  %s  %-9s %+8d  %s%s"
              % (time.strftime("%Y-%m-%d %H:%M", time.localtime(int(row["at"]))),
                 row["source"], int(row["afro"]),
                 char_name(db, row["char_id"]) if row["char_id"] else "-",
                 "  ref %s" % row["ref"] if row["ref"] else ""))
    if not ledger:
        print("  (empty)")
    return 0


def holding_sites():
    """key -> title of every site data/holdings.json lists, in key order."""
    try:
        with open(HOLDINGS, encoding="utf-8") as fh:
            sites = json.load(fh).get("sites") or {}
    except OSError:
        return {}
    return {k: v.get("title", k) for k, v in sorted(sites.items()) if not k.startswith("_")}


def cmd_holdings(db, args):
    """Every site, who holds it and since when, and its last changes."""
    sites = holding_sites()
    held = {}
    if has_table(db, "clan_holdings"):
        for row in db.execute("SELECT h.site, h.clan_id, k.name, h.since FROM clan_holdings h"
                              " JOIN clans k ON k.id = h.clan_id").fetchall():
            held[row["site"]] = row
    print("%-10s %-30s %-30s %s" % ("site", "warehouse", "held by", "since"))
    for key, title in sites.items():
        row = held.get(key)
        print("%-10s %-30s %-30s %s"
              % (key, title, "%s (id %s)" % (row["name"], row["clan_id"]) if row else "nobody",
                 time.strftime("%Y-%m-%d %H:%M", time.localtime(float(row["since"])))
                 if row else "-"))
    if not sites:
        print("(no data/holdings.json)")
    if has_table(db, "clan_holding_log"):
        rows = db.execute("SELECT * FROM clan_holding_log ORDER BY id DESC LIMIT 20").fetchall()
        print("\nthe last changes, newest first:")
        for row in rows:
            print("  %s  %-10s %-8s %s -> %s%s"
                  % (time.strftime("%Y-%m-%d %H:%M", time.localtime(float(row["at"]))),
                     row["site"], row["how"], row["prev"] or "-", row["clan_id"] or "-",
                     "  char %s" % row["by_char"] if row["by_char"] else ""))
        if not rows:
            print("  (none)")
    return 0


def cmd_clan_op(db, args):
    op = CLAN_OPS[args.command]
    clan = find_clan(db, args.login)
    if clan is None:
        sys.exit("no clan named or numbered %r" % args.login)
    payload = {"op": op, "clan": int(clan["id"])}
    if op in ("hold", "release"):
        sites = holding_sites()
        if args.site not in sites:
            sys.exit("%s needs --site, one of: %s" % (args.command, ", ".join(sites) or "none"))
        payload["site"] = args.site
    if op == "rename":
        if not args.name:
            sys.exit("clan-rename needs --name")
        payload["name"] = args.name
    elif op in ("head", "kick"):
        if not args.char:
            sys.exit("%s needs --char (a character's name or id)" % args.command)
        who = find_char(db, args.char)
        if who is None:
            sys.exit("no character named or numbered %r" % args.char)
        payload["char"] = int(who["id"])
    elif op == "treasury":
        if not args.afro:
            sys.exit("clan-treasury needs --afro, a non-zero whole number (minus takes out)")
        payload["afro"] = int(args.afro)
    elif op == "disband":
        payee = find_char(db, args.payout) if args.payout else None
        if args.payout and payee is None:
            sys.exit("no character named or numbered %r" % args.payout)
        payload["payout"] = int(payee["id"]) if payee is not None else None
        members = db.execute("SELECT count(*) AS n FROM clan_members WHERE clan_id = ?",
                             (clan["id"],)).fetchone()["n"]
        print("clan %s (id %s): %s members put out, the name freed, %s afro of the"
              " treasury to %s" % (clan["name"], clan["id"], members, clan["afro"],
                                   payee["name"] if payee is not None
                                   else "the head, %s" % char_name(db, clan["head"])))
        if not args.yes:
            print("\nnothing queued: pass --yes to go through with it")
            return 1
    action = queue_clan(db, args.admin, payload)
    print("queued as admin action %s: %s" % (action, json.dumps(payload, ensure_ascii=False)))
    return wait_done(db, action, args.wait)


COMMANDS = {"list": cmd_list, "create": cmd_create, "delete": cmd_delete,
            "passwd": cmd_passwd, "clans": cmd_clans, "clan": cmd_clan,
            "holdings": cmd_holdings}
COMMANDS.update({name: cmd_clan_op for name in CLAN_OPS})
# The commands that name nothing.
BARE = ("list", "clans", "holdings")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("login", nargs="?", metavar="login|clan",
                        help="the account to act on; for clan commands the clan,"
                             " by name or id")
    parser.add_argument("--db", help="SQLite file, when LAVA_DB_URL is unset")
    parser.add_argument("--yes", action="store_true",
                        help="delete, clan-disband: go through with it")
    parser.add_argument("--force", action="store_true",
                        help="delete: even if the character is playing")
    parser.add_argument("--password-stdin", action="store_true",
                        help="read the password from the first line of stdin")
    parser.add_argument("--random", action="store_true",
                        help="invent the password and print it")
    parser.add_argument("--name", help="clan-rename: the new name")
    parser.add_argument("--char", help="clan-head, clan-kick: the member, by name or id")
    parser.add_argument("--payout", help="clan-disband: who gets the treasury (the head"
                                         " if left out), by name or id")
    parser.add_argument("--afro", type=int, help="clan-treasury: afro in, or out if negative")
    parser.add_argument("--site", help="clan-hold, clan-release: the warehouse, a key of"
                                       " data/holdings.json (wh_sever, wh_vostok, wh_ug)")
    parser.add_argument("--admin", default="console",
                        help="clan-*: the name the queue's log shows (default console)")
    parser.add_argument("--wait", type=float, default=15.0,
                        help="clan-*: seconds to wait for the game's answer")
    args = parser.parse_args(argv)
    if args.command not in BARE and not args.login:
        parser.error("%s needs a %s" % (args.command, "clan" if args.command.startswith("clan")
                                        else "login"))

    db = open_db(args.db)
    try:
        return COMMANDS[args.command](db, args)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
