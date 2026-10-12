"""Accounts and saved characters.

The client authenticates itself: its login screen takes a name and a password,
computes md5 over the two concatenated, and sends only that digest to the game
socket. So the digest is the credential and the account key at once, and the
server never sees the password. Registration therefore has to happen outside
the client, which is what the original site did.

MD5rus.hashMD5 walks the string and maps Unicode Cyrillic into the 0xC0..0xFF
range before hashing, which is cp1251; everything else goes through unchanged.
That makes it a plain md5 of the cp1251 bytes of password + login.
"""
import contextlib
import hashlib
import json
import logging
import os
import secrets
import time

import progression
import storage

log = logging.getLogger("lava")

DB_PATH = os.environ.get(
    "LAVA_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "lava.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id      INTEGER PRIMARY KEY,
    login   TEXT    NOT NULL UNIQUE,
    hash    TEXT    NOT NULL UNIQUE,
    created INTEGER NOT NULL,
    banned  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS characters (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    slot       INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    sex        INTEGER NOT NULL,
    res        TEXT    NOT NULL,
    loc        INTEGER,
    pos        INTEGER,
    gx         REAL,
    gy         REAL,
    on_map     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (account_id, slot)
);
CREATE TABLE IF NOT EXISTS char_stats (
    char_id INTEGER NOT NULL REFERENCES characters(id),
    kind    TEXT    NOT NULL,      -- 'attrib' | 'skill' | 'spec'
    idx     INTEGER NOT NULL,      -- 0..4 / 0..4 / 0..14
    value   INTEGER NOT NULL,      -- attribute base / skill level / spec level, -1 unlearned
    xp      INTEGER NOT NULL DEFAULT 0,
    xp_max  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (char_id, kind, idx)
);
CREATE TABLE IF NOT EXISTS items (
    -- The serial part of the item's wire id. AUTOINCREMENT on purpose: the
    -- client keeps every oid it has ever seen in ItemFactory.itemStore for
    -- the whole session, so a serial reused for a new item of the same type
    -- would hand the player the old object with its stale stack size.
    uniq          INTEGER PRIMARY KEY AUTOINCREMENT,
    char_id       INTEGER NOT NULL REFERENCES characters(id),
    type_id       INTEGER NOT NULL,
    root          INTEGER NOT NULL,
    slot          INTEGER NOT NULL DEFAULT 2048,   -- container code, inventory.py
    count         INTEGER NOT NULL DEFAULT 1,      -- stack size ("size" on the wire)
    brk           INTEGER NOT NULL DEFAULT 0,      -- durability ("break" on the wire)
    max_break_cur INTEGER NOT NULL DEFAULT 0,
    ammo_count    INTEGER NOT NULL DEFAULT 0,
    ammo_type     INTEGER NOT NULL DEFAULT 0,
    cur_mode      INTEGER NOT NULL DEFAULT 0,
    use_count     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_by_char ON items (char_id);
CREATE TABLE IF NOT EXISTS char_quests (
    -- AUTOINCREMENT on purpose: a plain rowid is reused once the highest row
    -- is deleted, and a hand-in deletes its row, so the very next quest
    -- would come back under the id the client just dropped from its journal.
    q_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    char_id       INTEGER NOT NULL REFERENCES characters(id),
    type          INTEGER NOT NULL,
    progress_json TEXT    NOT NULL DEFAULT '{}',
    complete      INTEGER NOT NULL DEFAULT 0,
    taken_at      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS char_quests_done (
    id       INTEGER PRIMARY KEY,
    char_id  INTEGER NOT NULL REFERENCES characters(id),
    type     INTEGER NOT NULL,
    done_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mail (
    -- One row per letter, seen from two sides: the addressee's inbox and
    -- the sender's outbox are the same row under two deletion flags, so a
    -- sender clearing the outbox cannot take a parcel out of the inbox.
    -- AUTOINCREMENT on purpose: MailInspector keys its inbox/outbox arrays
    -- by id for the whole session, and a deleted id coming back on a new
    -- letter would land on the old LetterObject.
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    to_char      INTEGER NOT NULL REFERENCES characters(id),
    -- 0 is no character: letters the server files itself (the auction's,
    -- mail.SYSTEM_SENDER). Like items.char_id = 0 for a loot bag on the
    -- ground, that relies on the declaration staying a declaration: SQLite
    -- is told not to enforce it (storage.SqliteDB) and the Postgres
    -- translation does not carry it (storage.pg_schema).
    from_char    INTEGER NOT NULL REFERENCES characters(id),
    type         INTEGER NOT NULL DEFAULT 0,      -- mail.py LETTER..ORDER_EXPRESS
    subject      TEXT    NOT NULL DEFAULT '',
    body         TEXT    NOT NULL DEFAULT '',
    sent_at      INTEGER NOT NULL,
    read         INTEGER NOT NULL DEFAULT 0,
    returned     INTEGER NOT NULL DEFAULT 0,      -- came back with its parcel
    afro         INTEGER NOT NULL DEFAULT 0,      -- attached, or the asking price
    gold         INTEGER NOT NULL DEFAULT 0,
    items_json   TEXT    NOT NULL DEFAULT '[]',   -- attached instances, mail.snapshot
    to_deleted   INTEGER NOT NULL DEFAULT 0,
    from_deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS mail_by_to ON mail (to_char);
CREATE INDEX IF NOT EXISTS mail_by_from ON mail (from_char);
CREATE TABLE IF NOT EXISTS online (
    -- Who is in the game right now, written by the game server once a second
    -- and read by the admin panel, which has no other way to know: the
    -- sessions live in the other process. Rows are replaced wholesale on
    -- every pass, so a server that stops leaves the table as it was -- hence
    -- seen_at, which is what makes a stale snapshot obvious instead of a lie.
    char_id INTEGER PRIMARY KEY,
    nick    TEXT    NOT NULL,
    login   TEXT    NOT NULL DEFAULT '',
    loc     INTEGER,
    title   TEXT    NOT NULL DEFAULT '',
    gx      INTEGER,
    gy      INTEGER,
    since   INTEGER NOT NULL,
    seen_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS heartbeat (
    -- One row, rewritten by the game server on every pass. Without it an
    -- empty online table says two different things -- nobody is playing, or
    -- nobody is writing -- and the panel has no way to tell them apart.
    id INTEGER PRIMARY KEY CHECK (id = 1),
    at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS stop_plan (
    -- A stop announced to the players ahead of time (server/stopwarn.py).
    -- One row, written by the game server whenever what it says changes, and
    -- read by the panel and by stopwarn.py status, which the deploy waits on;
    -- the heartbeat says whether it is current. A table of its own and not
    -- columns on heartbeat: the game and the panel run migrate() at the same
    -- moment, and two ALTERs of one table race into "duplicate column".
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    stop_at INTEGER,                      -- epoch second of the stop; NULL: none
    made_at INTEGER NOT NULL DEFAULT 0,   -- when it was announced
    admin   TEXT    NOT NULL DEFAULT '',  -- by whom: a panel login, CI, deploy.sh
    players INTEGER NOT NULL DEFAULT 0    -- logged-in sessions, as last counted
);
CREATE TABLE IF NOT EXISTS admin_actions (
    -- The admin panel runs in the HTTP process and the game runs in another,
    -- with only this database between them. A panel that wrote to characters
    -- directly would lose every change made to somebody who is online: their
    -- Character.save() on the way out writes the numbers it has been holding
    -- since login, over the top. So the panel writes intent here and the game
    -- server, which owns those objects, carries it out and marks the row done.
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    made_at    INTEGER NOT NULL,
    admin      TEXT    NOT NULL,      -- the name the kick window shows
    kind       TEXT    NOT NULL,      -- money | item | transport | goto | kick | ban
    char_id    INTEGER,               -- target character, when there is one
    account_id INTEGER,               -- target account, for kick and ban
    args_json  TEXT    NOT NULL DEFAULT '{}',
    done_at    INTEGER,               -- NULL while it is still waiting
    result     TEXT                   -- what happened, for the panel to show
);
CREATE INDEX IF NOT EXISTS admin_actions_pending
    ON admin_actions (done_at) WHERE done_at IS NULL;
CREATE TABLE IF NOT EXISTS map_marks (
    -- A character's bookmarks on the global map, addressed by position:
    -- updMark;id= and rmMark;id= carry the index into the client's own
    -- array (GlobalMap.editMark/removeMark), which is the order the marks
    -- frame listed them in, so idx is the key and stays dense.
    char_id INTEGER NOT NULL REFERENCES characters(id),
    idx     INTEGER NOT NULL,
    x       INTEGER NOT NULL,      -- absolute map cell; the wire carries
    y       INTEGER NOT NULL,      -- offsets from wherever the player stands
    title   TEXT    NOT NULL DEFAULT '',
    info    TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (char_id, idx)
);
CREATE TABLE IF NOT EXISTS auction_lots (
    -- One row per lot on sale (auction.py). The item is NOT in items while
    -- it is here: it travels as a snapshot (mail.snapshot), exactly like a
    -- parcel, so nobody can wear, sell or load it meanwhile. item_uniq is
    -- its serial, which the lot's wire id is built from and ah_op names it
    -- by; AUTOINCREMENT on items never hands it out again.
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_uniq    INTEGER NOT NULL UNIQUE,
    type_id      INTEGER NOT NULL,
    root         INTEGER NOT NULL,
    item_json    TEXT    NOT NULL,
    seller       INTEGER NOT NULL REFERENCES characters(id),
    seller_name  TEXT    NOT NULL,
    currency     INTEGER NOT NULL DEFAULT 0,   -- 0 afro, 1 gold (hundredths)
    start_bid    INTEGER NOT NULL,
    buyout       INTEGER NOT NULL DEFAULT 0,   -- 0: no buyout
    bid          INTEGER NOT NULL DEFAULT 0,   -- the highest bid, held here
    bidder       INTEGER NOT NULL DEFAULT 0,   -- 0: nobody yet
    bidder_name  TEXT    NOT NULL DEFAULT '',
    fee          INTEGER NOT NULL DEFAULT 0,   -- commission paid at listing
    hours        INTEGER NOT NULL,             -- 24 | 72 | 168
    created_at   INTEGER NOT NULL,
    ends_at      REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS auction_by_end ON auction_lots (ends_at);
CREATE INDEX IF NOT EXISTS auction_by_seller ON auction_lots (seller);
CREATE TABLE IF NOT EXISTS migrations (
    -- Data fixes that must run once per database and never again (run_once):
    -- the name of each that has run here, and when.
    name     TEXT    PRIMARY KEY,
    done_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS trophies (
    -- Who killed whom, and when: what a trophy says about itself
    -- (trophies.py; ss_di_trophy's k_name, v_name, time and the rest). One
    -- row per trophy, keyed by the serial of its items row -- the serial its
    -- wire id is built from -- for as long as it is a thing in a bag, on
    -- the ground, in a letter or on sale. A registered trophy has no items
    -- row any more and is this row alone, still under that serial:
    -- AUTOINCREMENT on items never hands it out again. No AUTOINCREMENT
    -- here, as the value is always the item's.
    uniq          INTEGER PRIMARY KEY,
    type_id       INTEGER NOT NULL,
    killer_id     INTEGER NOT NULL,      -- characters.id
    killer_name   TEXT    NOT NULL,
    killer_lvl    INTEGER NOT NULL,      -- levels as they were at the kill
    victim_id     INTEGER NOT NULL,
    victim_name   TEXT    NOT NULL,
    victim_lvl    INTEGER NOT NULL,
    victim_clan   TEXT    NOT NULL DEFAULT '',
    killed_at     INTEGER NOT NULL,      -- epoch second of the (last) kill
    kills         INTEGER NOT NULL DEFAULT 1,
    owner         INTEGER NOT NULL DEFAULT 0,   -- whose collection; 0 while a thing,
                                                -- and 0 again once deleted from it
    registered_at INTEGER,                      -- NULL while it is a thing
    paid_at       INTEGER                       -- last registration that paid rep
    -- and the columns it gained since: TROPHY_COLUMNS
);
CREATE INDEX IF NOT EXISTS trophies_by_owner ON trophies (owner);
CREATE INDEX IF NOT EXISTS trophies_by_pair ON trophies (killer_id, victim_id);
CREATE TABLE IF NOT EXISTS money_ledger (
    -- The journal of money (book): one row per change of a purse --
    -- whose, at what level (the best skill, as the characters row caches
    -- it), when, why (source: LEDGER_SOURCES, or cmd:<command> for a
    -- command no source was named for) and about what (ref: the quest
    -- type, the thing bought or sold, the lot, the other side of a
    -- barter), and by how much: afro, gold in hundredths of an ounce, and
    -- silver for when there is some. Written in the transaction that
    -- writes the purse, so the two are never apart. Read by
    -- tools/money_report.py. No REFERENCES: rows outlive a deleted
    -- character, as the money they moved does.
    id      INTEGER PRIMARY KEY,
    at      INTEGER NOT NULL,
    char_id INTEGER NOT NULL,
    level   INTEGER NOT NULL DEFAULT 0,
    source  TEXT    NOT NULL,
    ref     INTEGER NOT NULL DEFAULT 0,
    afro    INTEGER NOT NULL DEFAULT 0,
    gold    INTEGER NOT NULL DEFAULT 0,
    silver  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS money_ledger_by_at ON money_ledger (at);
CREATE INDEX IF NOT EXISTS money_ledger_by_char ON money_ledger (char_id);
CREATE TABLE IF NOT EXISTS char_lent (
    -- When a quest last lent a character things used up by their use --
    -- rounds, medicine (quests.lends_consumables) -- so that it lends them
    -- once a day: use them, drop the quest, take it again was a free
    -- supply as often as one liked (server.py Session.quest_available).
    char_id INTEGER NOT NULL,
    type    INTEGER NOT NULL,
    lent_at INTEGER NOT NULL,
    PRIMARY KEY (char_id, type)
);
CREATE TABLE IF NOT EXISTS clans (
    -- One row per clan (server/clans.py). The id is the clan's "reg" on the
    -- wire, and AUTOINCREMENT on purpose: ClanInspector.clanArray caches a
    -- ClanInfo by reg for the life of the page, so an id handed out again
    -- would show the new clan under the old one's name. It stays inside
    -- 1..16777214: 0 means "no clan" and 16777215 "no clan, invitations
    -- forbidden" in fellow (Store.clan_create refuses anything else).
    -- name is as shown, name_key its skeleton (mail._skeleton: case,
    -- lookalike letters and spaces folded), which is what is unique. UNIQUE
    -- is written inline, never as CREATE UNIQUE INDEX: storage.pg_schema
    -- re-adds IF NOT EXISTS to a plain index only, and the second start on
    -- Postgres would fail on it. afro is the treasury, never below zero --
    -- kept so by conditional UPDATEs, as a CHECK does not reach Postgres.
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    name_key   TEXT    NOT NULL UNIQUE,
    descr      TEXT    NOT NULL DEFAULT '',     -- stored; no frame shows it
    head       INTEGER NOT NULL,                -- characters.id, perm 65535
    created_at INTEGER NOT NULL,
    afro       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clan_members (
    -- Who is in which clan: one row a character, so one clan a character
    -- (a second is the client's res 28 by itself). char_id is always given
    -- explicitly; Postgres makes it an identity BY DEFAULT, which is
    -- harmless. perm is the rights code of the wire (clans.py R_*), post
    -- the free text the roster shows under «Описание».
    char_id    INTEGER PRIMARY KEY,
    clan_id    INTEGER NOT NULL,
    perm       INTEGER NOT NULL DEFAULT 0,
    post       TEXT    NOT NULL DEFAULT '',
    joined_at  INTEGER NOT NULL,
    invited_by INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS clan_members_by_clan ON clan_members (clan_id);
CREATE TABLE IF NOT EXISTS clan_relations (
    -- One clan's stance toward another, one-sided as the original had it:
    -- -1 war, 0 neutral, 1 peace. A missing row is 0.
    clan_id    INTEGER NOT NULL,
    other      INTEGER NOT NULL,
    stat       INTEGER NOT NULL DEFAULT 0,
    changed_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (clan_id, other)
);
CREATE TABLE IF NOT EXISTS clan_ledger (
    -- The journal of a treasury, as money_ledger is of a purse: one row per
    -- change of clans.afro, signed, with why (CLAN_LEDGER_SOURCES) and who.
    -- Written in the transaction that writes the treasury. A move between a
    -- purse and a treasury is a row here and a row there (source "clan" in
    -- money_ledger), so the report can net it out as a transfer.
    id      INTEGER PRIMARY KEY,
    at      INTEGER NOT NULL,
    clan_id INTEGER NOT NULL,
    char_id INTEGER NOT NULL DEFAULT 0,
    source  TEXT    NOT NULL,
    ref     INTEGER NOT NULL DEFAULT 0,
    afro    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS clan_ledger_by_clan ON clan_ledger (clan_id);
CREATE TABLE IF NOT EXISTS ground (
    -- Where a thing lying on the ground lies, and until when: one row per
    -- items row of nobody's (combat.LOOT_OWNER) that a bag holds (combat.
    -- RoomCombat.loot) -- a creature's loot, what fell off a dead player,
    -- a thing thrown down, a trophy. Each lies combat.LOOT_LIFETIME from
    -- the moment it was put down, whoever is in the place or nobody (the
    -- owner's rule, 2026-09-28), and a restart must not cut that short: a
    -- dead player's gear lying there is his one way back to it. So the
    -- game server writes a row as it puts a thing down, takes it away as
    -- the thing is picked up or runs out, and at its start puts back into
    -- its room whatever is still due (combat.restore_ground). The place is
    -- the room's key (travel.room_key): the location, and the map cell
    -- only for a scene split by cell -- NULL for a place that is one room;
    -- a pack's room (encounters.py) is written as its location's own. No
    -- AUTOINCREMENT: the key is always the item's serial.
    uniq       INTEGER PRIMARY KEY,
    loc        INTEGER NOT NULL,
    gx         INTEGER,
    gy         INTEGER,
    cell       INTEGER NOT NULL,      -- the hex the bag lies on
    expires_at REAL    NOT NULL       -- the epoch second it goes
);
CREATE TABLE IF NOT EXISTS boss_kills (
    -- A boss that keeps the hours (server/bosses.py), killed in its window,
    -- is gone until the next one (combat.RoomCombat.keep_hours). Kept in
    -- the game server's memory alone, that was lost to a restart inside the
    -- window -- a deploy, a crash -- and every boss killed in it stood
    -- there again, its loot and its gold ingots with it. So the game server
    -- writes a kill down (RoomCombat.boss_killed) and reads it back as it
    -- makes the room (RoomCombat.recall_kills): killed in the window open
    -- now, the boss starts away. One row a boss, its last kill: spot is the
    -- room's place, the boss's spawn cell and its type (RoomCombat.
    -- boss_spot), slot the epoch second its window opened (bosses.slot). A
    -- row of a window long shut is harmless and is written over by the
    -- next kill.
    spot TEXT PRIMARY KEY,
    slot REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS clan_holdings (
    -- Who holds a capturable site now (server/holdings.py): one row a held
    -- site, none for a site nobody holds. site is a key of data/
    -- holdings.json. Written by the kill of the site's boss and by the
    -- admin's order (Store.holding_set, holding_clear); a disband takes the
    -- clan's rows with it (clan_drop). Read for every flag, box and repair:
    -- the game caches none of it, as it caches no clan.
    site     TEXT    PRIMARY KEY,
    clan_id  INTEGER NOT NULL,     -- clans.id
    since    REAL    NOT NULL,     -- the epoch second of the capture or the order
    by_char  INTEGER,              -- the winning clan's member credited; NULL for the admin
    slot     REAL                  -- the boss window it was taken in (bosses.slot)
);
CREATE TABLE IF NOT EXISTS clan_holding_log (
    -- Every outcome at a site (holdings.HOW): a capture, a defence, a kill
    -- that took nothing ('none'), the admin's order, a disband -- what the
    -- owner reads in place of lines in the chat, and the site's history.
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    at       REAL    NOT NULL,
    site     TEXT    NOT NULL,
    clan_id  INTEGER,              -- the holder after it, NULL when nobody
    prev     INTEGER,              -- the holder before it, NULL when nobody
    how      TEXT    NOT NULL,
    by_char  INTEGER,
    slot     REAL
);
CREATE INDEX IF NOT EXISTS clan_holding_log_by_site ON clan_holding_log (site, at);
CREATE TABLE IF NOT EXISTS email_tokens (
    -- The links the mail sends (server/email_flow.py): one row per letter
    -- that carries one. kind 'confirm' proves an address belongs to the
    -- account (the address is this row's, not yet the account's), kind
    -- 'reset' lets a new password be set. Only the token's sha256 is kept:
    -- a copy of this table opens no account. A row is spent once (used),
    -- and is good until expires; created is what the mail's own pace is
    -- counted by.
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    kind       TEXT    NOT NULL,
    digest     TEXT    NOT NULL UNIQUE,
    email      TEXT    NOT NULL,
    created    INTEGER NOT NULL,
    expires    INTEGER NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS email_tokens_by_account ON email_tokens (account_id);
CREATE TABLE IF NOT EXISTS site_orders (
    -- A stance step ordered on the site (lava-site api/db.py queue_stance),
    -- carried out by the game (server/site_orders.py). The site may insert
    -- here and read; it can do nothing else to the game's tables. A table
    -- of its own, never admin_actions: that queue carries every privileged
    -- order, and a row here can ask for nothing but one step a character
    -- could make in the game himself, every column a number but the login.
    -- The game marks a row done in the transaction that makes the step
    -- (Store.clan_stance_step), so a step is made once or not at all.
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    made_at   REAL    NOT NULL,   -- the site's clock; site and game share a host
    login     TEXT    NOT NULL,   -- the signed-in account
    char_id   INTEGER NOT NULL,
    clan_id   INTEGER NOT NULL,   -- the clan the site saw; the game derives its own
    other     INTEGER NOT NULL,
    stat_from INTEGER NOT NULL,   -- "from" is a reserved word
    dir       INTEGER NOT NULL,
    done_at   REAL,               -- NULL while it waits
    code      TEXT,               -- OK, R1..R7 (site_orders.TEXTS)
    result    TEXT                -- the words the site shows the player
);
CREATE INDEX IF NOT EXISTS site_orders_pending ON site_orders (done_at, id);
"""

# The sources a row of the money ledger names (money_ledger.source). A
# command that moves money without naming one is booked under
# "cmd:<command>" (server.py Session.handle), a timer's under "other".
LEDGER_SOURCES = {
    "opening": "the purse a character had when the ledger began (open_ledger)",
    "start": "a newborn's purse (progression.START_AFRO)",
    "quest": "a quest's reward, less its fee, at the hand-in (ref: the type)",
    "quest_fee": "a kill quest's fee, paid at the take (ref: the type)",
    "quest_refund": "a fee given back: a kill quest dropped, a way that moved nobody",
    "shop_buy": "a thing bought at a stall (ref: its type)",
    "shop_sell": "a thing sold to a stall (ref: its type)",
    "repair": "a repair or a restore at a stall (ref: the type)",
    "bank": "a step of bank storage",
    "c_ga": "gold into afro at the one rate",
    "healer": "a healer's full heal (ref: the healer's type)",
    "transport": "a rental (ref: the vehicle's type)",
    "spec": "a specialisation bought from a teacher (ref: its index)",
    "mail": "postage, money sent or taken out of a letter, a paid parcel",
    "auction": "a lot's fee, a bid, a buyout; its payouts come by letter (ref: the lot)",
    "barter": "the money of a barter (ref: the other side)",
    "trophy": "a trophy's registration, a place on the show (ref: the trophy)",
    "set_upgrade": "a set's piece upgraded or exchanged in an upgrader's window (ref: the new piece)",
    "death": "a paid resurrection",
    "admin": "the admin panel or a cheat",
    "clan_create": "a clan founded: its fee, a sink (ref: the clan)",
    "clan": "afro between a purse and its clan's treasury (ref: the clan)",
    "clan_disband": "a disbanded clan's treasury paid into a purse (ref: the clan)",
    "other": "a change no command named (a timer's)",
}
LEDGER_OTHER = "other"

# The sources a row of a clan's treasury journal names (clan_ledger.source),
# each row the signed change of clans.afro.
CLAN_LEDGER_SOURCES = {
    "deposit": "afro put in from a member's purse",
    "withdraw": "afro taken out into a member's purse",
    "diplomacy": "a change of stance paid for, a sink (ref: the other clan)",
    "disband": "what was left, paid out to a character or gone with him",
    "admin": "the admin panel's adjustment, either way",
}

# A clan's rights code (clan_members.perm): the eleven bits the client knows
# (Rights.as) and the rank ClanInterface.rankDetection derives from them. They
# live here rather than in clans.py for the one reader that must not import
# the game: tools/admin_account.py hands a clan over when it deletes its head,
# and picks the successor the way the game does (clan_successor).
CLAN_HEAD = 0x8000             # "all other rights": the head, and only him
CLAN_HEAD_PERM = 65535         # the head's stored code, as the original's
CLAN_VALID = 0xAF67            # every bit with a meaning (clans.R_*)


def clan_rank(perm):
    """ClanInterface.rankDetection: 4 the head, 2 an officer (kick, rights,
    treasury, diplomacy), 1 a recruiter (accept, storage out), else 0."""
    perm = int(perm or 0)
    if perm & CLAN_HEAD:
        return 4
    if perm & (0x100 | 0x200 | 0x400 | 0x800 | 0x2000):
        return 2
    if perm & (0x40 | 0x20):
        return 1
    return 0


def clan_successor(db, clan_id, leaving):
    """Who heads the clan when its head goes: of the other members, the
    highest rank, then the most rights, then the longest in the clan (the
    owner's decision 3). The client has no way to hand the lead on, so this
    is the server's; the game (Store.clan_leave) and the admin tool
    (clan_hand_over) both ask here and cannot disagree. leaving is the one
    who goes, or every one who goes at once (an account's characters).
    None: nobody left."""
    gone = {int(leaving)} if isinstance(leaving, int) else {int(c) for c in leaving}
    rows = [r for r in db.execute("SELECT char_id, perm, joined_at FROM clan_members"
                                  " WHERE clan_id = ?", (int(clan_id),)).fetchall()
            if int(r["char_id"]) not in gone]
    if not rows:
        return None
    best = max(rows, key=lambda r: (clan_rank(r["perm"]),
                                    bin(int(r["perm"]) & CLAN_VALID).count("1"),
                                    -int(r["joined_at"]), -int(r["char_id"])))
    return int(best["char_id"])


def clan_book(db, clan_id, source, afro, char_id=0, ref=0, when=None):
    """One row of a treasury's journal (clan_ledger), with no commit: the
    caller's transaction carries it with the treasury it describes."""
    if int(afro):
        db.execute("INSERT INTO clan_ledger (at, clan_id, char_id, source, ref, afro)"
                   " VALUES (?, ?, ?, ?, ?, ?)",
                   (int(when or time.time()), int(clan_id), int(char_id or 0),
                    str(source), int(ref or 0), int(afro)))


def clan_drop(db, clan_id, char_id=0, when=None):
    """Delete a clan with no commit: its row, its members, its relations
    both ways, the sites it held (server/holdings.py: a 'disband' row in
    clan_holding_log each). Returns (name, treasury) as the row held them,
    or None when there was no such clan. The row goes first, by a DELETE
    that names it, so of two processes disbanding at once one gets the
    treasury and the other None. What the treasury held is booked as a
    'disband' row; where it goes is the caller's (Store.clan_disband pays it
    into a purse, clan_hand_over lets it go with a deleted character)."""
    rows = db.execute("DELETE FROM clans WHERE id = ? RETURNING name, afro",
                      (int(clan_id),)).fetchall()
    if not rows:
        return None
    afro = int(rows[0]["afro"] or 0)
    db.execute("DELETE FROM clan_members WHERE clan_id = ?", (int(clan_id),))
    db.execute("DELETE FROM clan_relations WHERE clan_id = ? OR other = ?",
               (int(clan_id), int(clan_id)))
    clan_book(db, clan_id, "disband", -afro, char_id, 0, when)
    # A database no server of today has opened yet has no holdings to drop
    # (tools/admin_account.py never builds the schema; has_table there).
    if db.columns("clan_holdings"):
        at = float(when or time.time())
        for r in db.execute("DELETE FROM clan_holdings WHERE clan_id = ? RETURNING site",
                            (int(clan_id),)).fetchall():
            db.execute("INSERT INTO clan_holding_log (at, site, clan_id, prev, how)"
                       " VALUES (?, ?, NULL, ?, 'disband')", (at, r["site"], int(clan_id)))
    return rows[0]["name"], afro


def clan_hand_over(db, char_id, when=None, exclude=()):
    """A character leaves its clan for good -- deleted by tools/
    admin_account.py -- with no commit: the tool commits it with the rest of
    the deletion. A head's clan passes to clan_successor, never to one of
    `exclude` (the account's other characters, going with him); a head with
    nobody left disbands it, and the treasury goes with him as his purse
    does (a 'disband' row in clan_ledger, a sink). His own membership row is
    left for the tool's CHILDREN to delete. Returns (clan_id, new head or
    None when disbanded, treasury lost), or None when he was in no clan or
    was not its head."""
    row = db.execute("SELECT m.clan_id, k.head FROM clan_members m"
                     " JOIN clans k ON k.id = m.clan_id WHERE m.char_id = ?",
                     (int(char_id),)).fetchone()
    if row is None or int(row["head"]) != int(char_id):
        return None
    clan_id = int(row["clan_id"])
    new = clan_successor(db, clan_id, {int(char_id)} | {int(c) for c in exclude})
    if new is None:
        gone = clan_drop(db, clan_id, char_id, when)
        return clan_id, None, (gone[1] if gone else 0)
    db.execute("UPDATE clans SET head = ? WHERE id = ?", (new, clan_id))
    db.execute("UPDATE clan_members SET perm = ? WHERE char_id = ? AND clan_id = ?",
               (CLAN_HEAD_PERM, new, clan_id))
    return clan_id, new, 0

# What a trophy row says, besides its serial and the three bookkeeping
# columns (owner, registered_at, paid_at): written at the kill.
TROPHY_FIELDS = ("type_id", "killer_id", "killer_name", "killer_lvl",
                 "victim_id", "victim_name", "victim_lvl", "victim_clan",
                 "killed_at", "kills")

MAIL_FIELDS = ("to_char", "type", "subject", "body", "sent_at", "read",
               "returned", "afro", "gold", "items_json", "to_deleted",
               "from_deleted")

# Columns the characters table gained after the first databases were made.
# SCHEMA runs as CREATE TABLE IF NOT EXISTS, which leaves an existing table
# as it was, so these are added one by one where missing. Every NOT NULL
# column carries a default, which is what ALTER TABLE ADD COLUMN demands.
# hp/sp NULL means full; level is the best skill, cached for listings.
CHARACTER_COLUMNS = [
    ("hp", "INTEGER"),
    ("sp", "INTEGER"),
    ("afro", "INTEGER NOT NULL DEFAULT 0"),
    ("gold", "INTEGER NOT NULL DEFAULT 0"),
    ("premium", "INTEGER NOT NULL DEFAULT 0"),
    ("premium_until", "INTEGER"),
    ("rep", "INTEGER NOT NULL DEFAULT 0"),
    ("bg_rep", "INTEGER NOT NULL DEFAULT 0"),
    ("bg_pen", "INTEGER NOT NULL DEFAULT 0"),
    ("max_specs", "INTEGER NOT NULL DEFAULT 1"),
    ("level", "INTEGER NOT NULL DEFAULT 0"),
    # where the character respawns, set by on_conv;op=0
    ("home_loc", "INTEGER"),
    # whether the starter kit has been handed out; characters made before
    # the inventory existed get it on their next login
    ("kit", "INTEGER NOT NULL DEFAULT 0"),
    # and the map cell the home location stands on: an interior does not
    # know its own cell, so leaving home for the map needs it remembered here
    ("home_gx", "INTEGER"),
    ("home_gy", "INTEGER"),
    # whether the character is lying dead. A death the socket does not
    # outlive is no death at all, so the flag is written here by
    # combat.Fighter.die and read back at selPers; it is also what
    # persInfo;death carries to the character screen, and the flag the
    # client raises the regeneration window from once it is in a location
    # (PersGenerator.persInfo, Master.lenter/gmap).
    #
    # Deliberately not a column progression.Character writes: its save()
    # runs on the way out over hp/sp/money and would have to be taught the
    # flag as well for it not to be undone.
    ("death", "INTEGER NOT NULL DEFAULT 0"),
    # The rented vehicle and the epoch second the rental runs out. Both NULL
    # means on foot, which is what the client is told by leaving tr and
    # tr_hours out of userInfo_Player altogether (world.md 4). Character.save
    # does not write these, so a rental is not clobbered on the way out.
    ("transport_type", "INTEGER"),
    ("transport_until", "INTEGER"),
    # How many 50 kg expansions of the bank storage were bought
    # (inventory.bank_increase). The storage itself needs no table: its
    # contents are items rows with slot = inventory.BANK. Character.save
    # does not write this either, so a purchase outlives the logout.
    ("bank_steps", "INTEGER NOT NULL DEFAULT 0"),
    # How many places to show a trophy on were bought (trophies.buy_place),
    # over the ones every character has (trophies.START_PLACES): counted
    # as bought, so moving that number moves everybody's show. Character.save
    # does not write it; the purchase writes it with the purse
    # (Store.buy_trophy_place).
    ("trophy_places", "INTEGER NOT NULL DEFAULT 0"),
    # The Settings box «Запретить другим игрокам приглашать меня в клан»
    # (clans.py): 1 is fellow;reg=16777215 on the wire, 0 accepts. Only a
    # character in no clan has it on; founding or joining one clears it.
    ("clan_no_invites", "INTEGER NOT NULL DEFAULT 0"),
    # When the character last came into the game or left it (clans.py,
    # the roster's «Последнее посещение»); 0 for never, which the roster
    # sends as an empty date rather than 01.01.1970. Neither is written by
    # Character.save.
    ("seen_at", "INTEGER NOT NULL DEFAULT 0"),
]

# The same for the accounts table: the address the mail goes to
# (server/email_flow.py), lower case, and whether a letter's link has proved
# it the player's. email NULL is an account made before there was mail, or
# made without an address; email_ok 0 with an address is one given at
# registration and not yet confirmed. A changed address waits in its
# token's row until it is confirmed, and only then lands here, so the
# confirmed one keeps working until the new one does.
ACCOUNT_COLUMNS = [
    ("email", "TEXT"),
    ("email_ok", "INTEGER NOT NULL DEFAULT 0"),
]

# The same for the trophies table (accounts.SCHEMA): shown is the place
# (0, 1, ...) an entry of the collection stands on in its owner's show --
# what another player inspecting him sees (ss_get;slot=32, trophies.py) --
# and NULL for an entry the collection only keeps.
TROPHY_COLUMNS = [
    ("shown", "INTEGER"),
]

# char_id is updatable too: an item picked out of a loot bag keeps its
# serial, and with it the oid the client already holds it under (combat.py).
ITEM_FIELDS = ("char_id", "slot", "count", "brk", "max_break_cur", "ammo_count",
               "ammo_type", "cur_mode", "use_count")


class _Stale(Exception):
    """An offered item is not as it was offered: Store.barter_swap rolls
    back on it."""

    def __init__(self, uniq):
        super().__init__(uniq)
        self.uniq = uniq


class _Answered(Exception):
    """A site order is no longer waiting (site_orders.py): Store.
    clan_stance_step rolls its step back on it."""


def credential(login, password):
    """The digest the client will send: md5 of cp1251(password + login)."""
    return hashlib.md5((password + login).encode("cp1251", "replace")).hexdigest()


def migrate(db):
    """Bring a database made by an older server up to the current schema.

    Characters that predate char_stats get the newborn's numbers, money
    included: they had none stored, and the server they were made under
    showed everyone the same fixed figures anyway.
    """
    for table, wanted in (("characters", CHARACTER_COLUMNS),
                          ("trophies", TROPHY_COLUMNS),
                          ("accounts", ACCOUNT_COLUMNS)):
        have = db.columns(table)
        for col, decl in wanted:
            if col not in have:
                db.add_column(table, col, decl)
    orphans = db.execute(
        "SELECT id FROM characters WHERE id NOT IN"
        " (SELECT DISTINCT char_id FROM char_stats)").fetchall()
    for row in orphans:
        seed_stats(db, row["id"])
    db.commit()
    run_once(db, "heal-relink-2026-09-23", relink_heals)
    run_once(db, "retire-black-market-placeholders-2026-09-28", retire_placeholders)
    run_once(db, "money-ledger-opening-2026-09-28", open_ledger)
    run_once(db, RETIRED_PLACES_FIX, relocate_retired_places)
    run_once(db, HALFA_CUT_FIX, relocate_halfa_cut)
    run_once(db, HALFA_FSC_FIX, relocate_halfa_fsc)
    run_once(db, ABRI_CUT_FIX, relocate_abri_cut)
    # Only with the client's tables to tell a premium thing by: a process
    # without them (a tool run outside the container) leaves the fix for
    # the next start that has them, rather than writing it down as done
    # with nothing found.
    if not ran(db, PREMIUM_THINGS_FIX):
        premium = premium_test()
        if premium is None:
            log.warning("  ..    %s waits: the client's objects.xml is not here to tell"
                        " a premium thing by", PREMIUM_THINGS_FIX)
        else:
            run_once(db, PREMIUM_THINGS_FIX,
                     lambda d: retire_premium_things(d, premium))


def ran(db, name):
    """Whether the fix of this name has run on this database (run_once)."""
    return db.execute("SELECT 1 FROM migrations WHERE name = ?", (name,)).fetchone() is not None


def run_once(db, name, fix):
    """fix(db) and the record that it ran, in one transaction, unless the
    record is there already. The record goes in first: a second process
    opening the same database at the same moment (the server and the
    registration page both do) waits on it and then finds it taken.

    Looked up before it is tried: the registration page opens a Store for
    every request, and on Postgres each INSERT that runs into the key is an
    ERROR in the server's log -- one per page view, forever."""
    if ran(db, name):
        return False
    try:
        with db:
            db.execute("INSERT INTO migrations (name, done_at) VALUES (?, ?)",
                       (name, int(time.time())))
            fix(db)
    except storage.IntegrityError:
        return False
    return True


# The medicines whose numbers moved (data/heal_manual.json, 2026-09-23). Until
# then the six Med_Battle_HR_*_P types carried the Эгоист..Спасатель line --
# twenty uses, 0 AP, 135..1380 health -- and three stalls sold them for gold
# under it; the original has that line at 6904..6909, where its numbers are
# now, and 6067..6072 became another line (5 uses at 7..15 AP, or one weak
# one). What was bought is what is kept: every instance, in a bag, a bank, a
# letter or a lot, moves to the type that now holds what was paid for, its
# use_count as it is. Once per database, not at every start: premium things
# are out of the game, and an admin could still hand out a 6067 then (no
# longer since the cut of (P), 2026-10-02: retire_premium_things, below,
# runs after this one and takes what is left).
HEAL_RELINK = {t: t + 837 for t in range(6067, 6073)}


def _relinked(snaps):
    """The snapshot(s) of a letter or a lot with the moved types moved;
    None when nothing in them is one."""
    one = isinstance(snaps, dict)
    moved = False
    for snap in [snaps] if one else snaps:
        if isinstance(snap, dict) and snap.get("type_id") in HEAL_RELINK:
            snap["type_id"] = HEAL_RELINK[snap["type_id"]]
            moved = True
    return snaps if moved else None


def relink_heals(db):
    for old, new in HEAL_RELINK.items():
        db.execute("UPDATE items SET type_id = ? WHERE type_id = ?", (new, old))
        db.execute("UPDATE auction_lots SET type_id = ? WHERE type_id = ?", (new, old))
    for table, column in (("mail", "items_json"), ("auction_lots", "item_json")):
        for row in db.execute("SELECT id, %s FROM %s" % (column, table)).fetchall():
            try:
                snaps = _relinked(json.loads(row[column] or "[]"))
            except ValueError:
                continue
            if snaps is not None:
                db.execute("UPDATE %s SET %s = ? WHERE id = ?" % (table, column),
                           (json.dumps(snaps), row["id"]))


# The black market's placeholder quests (data/quests.json 1-3, 5 and 6: texts
# of this server's, no row of the original, 3 paying half an ounce for a
# word passed on), out of the table since 2026-09-28 (the plan's correction
# а). One carried in a journal would stay there under no name, taking a
# place, so it leaves the journals once per database; what was handed in
# stays in the history, which asks the table of nothing.
RETIRED_QUESTS = (1, 2, 3, 5, 6)


def retire_placeholders(db):
    db.execute("DELETE FROM char_quests WHERE type IN (%s)"
               % ", ".join("?" * len(RETIRED_QUESTS)), RETIRED_QUESTS)


def open_ledger(db):
    """The purses as they stand when the ledger begins, one "opening" row a
    character: from then on a character's rows add up to his purse, the old
    characters' too. Less what the ledger already holds of him -- a
    character re-seeded by migrate on the same start books its newborn's
    purse first. A new database has nobody to open."""
    db.execute("INSERT INTO money_ledger (at, char_id, level, source, ref, afro, gold)"
               " SELECT ?, c.id, c.level, 'opening', 0,"
               " c.afro - COALESCE(l.afro, 0), c.gold - COALESCE(l.gold, 0)"
               " FROM characters c LEFT JOIN (SELECT char_id, SUM(afro) AS afro,"
               " SUM(gold) AS gold FROM money_ledger GROUP BY char_id) l"
               " ON l.char_id = c.id"
               " WHERE c.afro - COALESCE(l.afro, 0) <> 0"
               " OR c.gold - COALESCE(l.gold, 0) <> 0", (int(time.time()),))


# The owner's cut of (P) (2026-09-30, «удали всё, что связано с (P), в том
# числе и локации»). The premium masters' camps 124 (Вади-Хальфа), 125
# (Донгола) and 130 (Абу-Хамед) are off the map (data/retired.json places),
# and the craftsmen's quarter 447 lost its only ways in and out with 124
# (quests.json 414/415 OFF). Their files stay, so a character saved inside
# one would still come in -- to a place with nobody in it and, from 447, no
# way out but the map button onto a walled cell -- and a home registered in
# one would send a death back there. So whoever is in one, or calls one
# home, goes to Причал (41, on 5965,1728), the town's pier, once per
# database. A read-only census of production (2026-09-30) found nobody
# there; this is for the database that has somebody.
RETIRED_PLACES_FIX = "retire-premium-places-2026-10-02"
RETIRED_PLACES = (124, 125, 130, 447)
RETIRED_PLACES_TO = (41, 5965, 1728)


def relocate_retired_places(db):
    loc, gx, gy = RETIRED_PLACES_TO
    marks = ", ".join("?" * len(RETIRED_PLACES))
    inside = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE loc IN (%s) ORDER BY id" % marks,
        RETIRED_PLACES).fetchall()]
    homes = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE home_loc IN (%s) ORDER BY id" % marks,
        RETIRED_PLACES).fetchall()]
    # The cell inside the old file means nothing in Причал's (pos NULL: the
    # login picks the entry beside its people, Session.restore), and a
    # character left on the map beside the old place starts in Причал too.
    db.execute("UPDATE characters SET loc = ?, pos = NULL, gx = ?, gy = ?, on_map = 0"
               " WHERE loc IN (%s)" % marks, (loc, gx, gy) + RETIRED_PLACES)
    db.execute("UPDATE characters SET home_loc = ?, home_gx = ?, home_gy = ?"
               " WHERE home_loc IN (%s)" % marks, (loc, gx, gy) + RETIRED_PLACES)
    # A warning, not info: the game server opens its Store at import, before
    # main() sets the log's level, and a one-off change to the players'
    # rows is worth the line wherever it runs.
    log.warning("  ..    %s: %d character(s) moved out of %s to %d %s, %d home(s) moved",
                RETIRED_PLACES_FIX, len(inside), "/".join(map(str, RETIRED_PLACES)), loc,
                inside, len(homes))


# The owner's cut of Вади-Хальфа (2026-10-09, «убери из хальфы следующие
# локации: торговцы одеждой, улучшение сетов 6-8, ремесленники по одежде 6, 7
# и 8, а также кланбазу KKND»): the clothing market 468 and the craftsmen's
# quarters 452, 456, 457 are off the map, and the KKND clan base's files
# (297, 383, 384, 938, 961, 1189) are out of the game with them (data/
# retired.json places). A character saved in one, or calling one home, goes
# to Причал as the cut of (P) sent them -- the pier «В Хальфу!» (43) lands
# newcomers on, the town's open door since 2026-10-03. And the quests that
# went with them leave the journals, as the black market's placeholders did
# (retire_placeholders): the talks about the set upgrade's window, 238 and
# 239, and the clothing craftsmen's rows (setcraft.TYPE_RANGE, Вади-Хальфа's
# block 11000-11499) -- nobody gives or takes them any more, and a journal
# would keep them under a name nobody can hand in to. The history
# (char_quests_done) and the money ledger keep what was done. Nothing in a
# bag goes: the reworked pieces and the cheques stay their owners'.
HALFA_CUT_FIX = "retire-halfa-cut-2026-10-09"
HALFA_CUT_PLACES = (468, 452, 456, 457, 297, 383, 384, 938, 961, 1189)
HALFA_CUT_QUESTS = (238, 239)
HALFA_CUT_ROWS = (11000, 11500)          # setcraft SLICES['Вади-Хальфа'] types


def relocate_halfa_cut(db):
    """Whoever is in a place of the cut, or calls one home, to Причал (as
    relocate_retired_places), and the cut's quests out of the journals;
    returns the counts it logs."""
    loc, gx, gy = RETIRED_PLACES_TO
    marks = ", ".join("?" * len(HALFA_CUT_PLACES))
    inside = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE loc IN (%s) ORDER BY id" % marks,
        HALFA_CUT_PLACES).fetchall()]
    homes = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE home_loc IN (%s) ORDER BY id" % marks,
        HALFA_CUT_PLACES).fetchall()]
    db.execute("UPDATE characters SET loc = ?, pos = NULL, gx = ?, gy = ?, on_map = 0"
               " WHERE loc IN (%s)" % marks, (loc, gx, gy) + HALFA_CUT_PLACES)
    db.execute("UPDATE characters SET home_loc = ?, home_gx = ?, home_gy = ?"
               " WHERE home_loc IN (%s)" % marks, (loc, gx, gy) + HALFA_CUT_PLACES)
    where = "type IN (%s) OR (type >= ? AND type < ?)" % ", ".join("?" * len(HALFA_CUT_QUESTS))
    args = HALFA_CUT_QUESTS + HALFA_CUT_ROWS
    journal = db.execute("SELECT COUNT(*) AS c FROM char_quests WHERE " + where,
                         args).fetchone()["c"]
    db.execute("DELETE FROM char_quests WHERE " + where, args)
    # A warning for the reason relocate_retired_places' is one.
    log.warning("  ..    %s: %d character(s) moved out of %s to %d %s, %d home(s) moved, %d"
                " quest(s) out of the journals", HALFA_CUT_FIX, len(inside),
                "/".join(map(str, HALFA_CUT_PLACES)), loc, inside, len(homes), journal)
    return dict(moved=len(inside), homes=len(homes), journal=journal)


# The owner's cut of Вади-Хальфа's ФСЦ (2026-10-10, «убери фсц тоже», after
# the cut above): the FSC airfield 528 (5970,1727) and the FSC base «НИЛ-1»
# 522 (5942,1723, across the river) are off the map (data/retired.json
# places). A character saved in one, or calling one home, goes to Причал as
# the cuts before sent them. No journal step: no quest gives, takes, asks
# for or points into either place -- the airfield's two upgraders give none,
# nobody stands in the base (server/test_halfa_cut.py holds that) -- so no
# journal row can have become impossible with them. Nothing else is touched.
HALFA_FSC_FIX = "retire-halfa-fsc-2026-10-10"
HALFA_FSC_PLACES = (528, 522)


def relocate_halfa_fsc(db):
    """Whoever is in the FSC airfield or base, or calls one home, to Причал
    (as relocate_retired_places); returns the counts it logs."""
    loc, gx, gy = RETIRED_PLACES_TO
    marks = ", ".join("?" * len(HALFA_FSC_PLACES))
    inside = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE loc IN (%s) ORDER BY id" % marks,
        HALFA_FSC_PLACES).fetchall()]
    homes = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE home_loc IN (%s) ORDER BY id" % marks,
        HALFA_FSC_PLACES).fetchall()]
    db.execute("UPDATE characters SET loc = ?, pos = NULL, gx = ?, gy = ?, on_map = 0"
               " WHERE loc IN (%s)" % marks, (loc, gx, gy) + HALFA_FSC_PLACES)
    db.execute("UPDATE characters SET home_loc = ?, home_gx = ?, home_gy = ?"
               " WHERE home_loc IN (%s)" % marks, (loc, gx, gy) + HALFA_FSC_PLACES)
    # A warning for the reason relocate_retired_places' is one.
    log.warning("  ..    %s: %d character(s) moved out of %s to %d %s, %d home(s) moved",
                HALFA_FSC_FIX, len(inside), "/".join(map(str, HALFA_FSC_PLACES)), loc,
                inside, len(homes))
    return dict(moved=len(inside), homes=len(homes))


# The owner's cut of Абри (2026-10-12, «Убери локации: все ремесленники по
# одежде; Авиабаза ЦСЦ; улучшение сетов 10-12; ...; убери кланбазу
# Либерти»): the clothing craftsmen's quarters 453, 454, 458, 459, the ЦСЦ's
# air base 427 and the quarter 450 behind «Улучшение сетов 10-12», and every
# file of the clan base Liberty (328 and 327 on their cells, the rest never
# on one) are off the map (data/retired.json places); so, by the decisions
# taken for him the same day («Все, что не сможешь восстановить, вырезай»),
# are the ФСЦ airfield 529 and every file of the clan base Blackwater (its
# block post 317 on its cell, the rest never on one). A character saved in
# one, or calling one home, goes to Абри's own door, the Портовый рынок 187
# (5860,1835), where the ride from Вади-Хальфа lands, rather than across the
# desert to Причал. No journal step: no quest gives, takes, asks for or
# points into these places -- the clothing craftsmen of Абри never had
# rows (server/setcraft.py has no slice for the town), the air base's people,
# the airfield's and the clan bases' give none (server/test_abri_cut.py holds
# that).
ABRI_CUT_FIX = "retire-abri-cut-2026-10-12"
ABRI_CUT_PLACES = (453, 454, 458, 459, 427, 450,
                   328, 327, 326, 329, 936, 937, 939, 940, 1190, 148, 610,
                   529, 317, 311, 312, 927, 931, 935, 1188)
ABRI_CUT_TO = (187, 5860, 1835)


def relocate_abri_cut(db):
    """Whoever is in a place of Абри's cut, or calls one home, to Абри's port
    market (as relocate_retired_places sends them to Причал); returns the
    counts it logs."""
    loc, gx, gy = ABRI_CUT_TO
    marks = ", ".join("?" * len(ABRI_CUT_PLACES))
    inside = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE loc IN (%s) ORDER BY id" % marks,
        ABRI_CUT_PLACES).fetchall()]
    homes = [r["id"] for r in db.execute(
        "SELECT id FROM characters WHERE home_loc IN (%s) ORDER BY id" % marks,
        ABRI_CUT_PLACES).fetchall()]
    db.execute("UPDATE characters SET loc = ?, pos = NULL, gx = ?, gy = ?, on_map = 0"
               " WHERE loc IN (%s)" % marks, (loc, gx, gy) + ABRI_CUT_PLACES)
    db.execute("UPDATE characters SET home_loc = ?, home_gx = ?, home_gy = ?"
               " WHERE home_loc IN (%s)" % marks, (loc, gx, gy) + ABRI_CUT_PLACES)
    # A warning for the reason relocate_retired_places' is one.
    log.warning("  ..    %s: %d character(s) moved out of %s to %d %s, %d home(s) moved",
                ABRI_CUT_FIX, len(inside), "/".join(map(str, ABRI_CUT_PLACES)), loc,
                inside, len(homes))
    return dict(moved=len(inside), homes=len(homes))


# The same cut for the things: a premium thing (items.premium, 6 860 types)
# is out of the game -- no stall, loot, quest or admin hands one out, no
# letter, lot or barter passes one on -- and any that got into the game
# before goes, once per database: from the bags, the banks, the bodies and
# the ground (items rows, and the ground's rows of nobody's), from the
# auction (the lot with it, its standing bid back to the bidder by letter,
# as a lot taken off pays it), and out of the letters (the snapshot alone;
# the letter stays, and a trade letter left with nothing in it asks
# nothing for it either). The names of the types stay in the string table
# -- an unknown id sends a client to the login screen -- so nothing that is
# missed here can break a client. The counts go to the log. A read-only
# census of production (2026-09-30) found 0 in items, lots and letters.
PREMIUM_THINGS_FIX = "retire-premium-things-2026-10-02"
# mail.TRADE and TRADE_EXPRESS, and mail.SYSTEM_SENDER, mail.LETTER: mail
# imports this module, so the numbers are repeated here (test_premium_cut).
_TRADE_LETTERS = (4, 5)
_SYSTEM_SENDER, _LETTER = 0, 0


def premium_test():
    """items.premium, when the client's tables are there to tell a premium
    thing by; None when they are not. Late: items imports half the server
    and reads res/database/objects.xml, which a tool run outside the
    container may not have."""
    try:
        import items
        if not items.catalogue():
            return None
    except (ImportError, OSError) as exc:
        log.warning("  ..    no item tables for %s: %s", PREMIUM_THINGS_FIX, exc)
        return None
    return items.premium


def retire_premium_things(db, premium=None):
    """Every premium thing out of the database (the comment above); returns
    the counts it logs."""
    premium = premium or premium_test()
    if premium is None:
        raise RuntimeError("%s: no item tables to tell a premium thing by" % PREMIUM_THINGS_FIX)
    counts = dict(items=0, types=0, ground=0, lots=0, bids=0, letters=0, parcels=0)

    types = sorted(t for t in (int(r["type_id"]) for r in db.execute(
        "SELECT DISTINCT type_id FROM items").fetchall()) if premium(t))
    if types:
        marks = ", ".join("?" * len(types))
        uniqs = [r["uniq"] for r in db.execute(
            "SELECT uniq FROM items WHERE type_id IN (%s)" % marks, types).fetchall()]
        for i in range(0, len(uniqs), 500):
            part = uniqs[i:i + 500]
            counts["ground"] += len(db.execute(
                "SELECT uniq FROM ground WHERE uniq IN (%s)" % ", ".join("?" * len(part)),
                part).fetchall())
            db.execute("DELETE FROM ground WHERE uniq IN (%s)" % ", ".join("?" * len(part)),
                       part)
        db.execute("DELETE FROM items WHERE type_id IN (%s)" % marks, types)
        counts["items"], counts["types"] = len(uniqs), len(types)

    now = int(time.time())
    for lot in db.execute("SELECT id, type_id, bidder, bid, currency FROM auction_lots"
                          " ORDER BY id").fetchall():
        if not premium(int(lot["type_id"])):
            continue
        if lot["bidder"] and lot["bid"]:
            gold = int(lot["currency"]) == 1          # auction.GOLD, as money_text
            what = ("%.2f G" % (lot["bid"] / 100.0)) if gold else ("%d афро" % lot["bid"])
            db.execute(
                "INSERT INTO mail (to_char, from_char, type, subject, body, sent_at,"
                " afro, gold, items_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lot["bidder"], _SYSTEM_SENDER, _LETTER, "Аукцион: ставка возвращена",
                 "Лот снят: вещи (P) выведены из игры. Возвращаем вашу ставку %s." % what,
                 now, 0 if gold else lot["bid"], lot["bid"] if gold else 0, "[]"))
            counts["bids"] += 1
        db.execute("DELETE FROM auction_lots WHERE id = ?", (lot["id"],))
        counts["lots"] += 1

    for row in db.execute("SELECT id, type, items_json FROM mail"
                          " WHERE items_json <> '[]' ORDER BY id").fetchall():
        try:
            snaps = json.loads(row["items_json"] or "[]")
        except ValueError:
            continue
        if not isinstance(snaps, list):
            continue
        kept = [s for s in snaps
                if not (isinstance(s, dict) and premium(int(s.get("type_id") or 0)))]
        if len(kept) == len(snaps):
            continue
        if not kept and int(row["type"]) in _TRADE_LETTERS:
            db.execute("UPDATE mail SET items_json = ?, afro = 0, gold = 0 WHERE id = ?",
                       ("[]", row["id"]))
        else:
            db.execute("UPDATE mail SET items_json = ? WHERE id = ?",
                       (json.dumps(kept), row["id"]))
        counts["letters"] += 1
        counts["parcels"] += len(snaps) - len(kept)

    # A warning for the reason relocate_retired_places' is one.
    log.warning("  ..    %s: %d premium thing(s) of %d type(s) gone from bags, banks and the"
                " ground (%d of them lying there), %d lot(s) (%d bid(s) sent back), %d"
                " out of %d letter(s)", PREMIUM_THINGS_FIX, counts["items"], counts["types"],
                counts["ground"], counts["lots"], counts["bids"], counts["parcels"],
                counts["letters"])
    return counts


def book(db, char_id, afro=None, gold=None, source=None, ref=0, level=None, when=None):
    """The ledger row for the purse of char_id becoming (afro, gold) -- None
    for a currency that does not change -- written with no commit, so that
    the caller's commit of the purse carries it (money_ledger). The
    difference is taken from the row as it stands, before the purse is
    written over it; nothing is written when there is none. level None
    takes the row's own. Returns (afro, gold) of the difference."""
    row = db.execute("SELECT afro, gold, level FROM characters WHERE id = ?",
                     (int(char_id),)).fetchone()
    if row is None:
        return 0, 0
    d_afro = 0 if afro is None else int(afro) - int(row["afro"] or 0)
    d_gold = 0 if gold is None else int(gold) - int(row["gold"] or 0)
    if d_afro or d_gold:
        db.execute("INSERT INTO money_ledger (at, char_id, level, source, ref, afro, gold)"
                   " VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (int(when or time.time()), int(char_id),
                    int(row["level"] or 0) if level is None else int(level),
                    source or LEDGER_OTHER, int(ref or 0), d_afro, d_gold))
    return d_afro, d_gold


def seed_stats(db, char_id):
    """A newborn's stats and purse, for a new character and for one found
    without stats (migrate): the purse it gets is booked (book), so its
    rows still add up to it."""
    book(db, char_id, progression.START_AFRO, 0, "start", level=0)
    db.replace("char_stats",
               ("char_id", "kind", "idx", "value", "xp", "xp_max"),
               [(char_id,) + r for r in progression.starting_rows()],
               conflict=("char_id", "kind", "idx"))
    db.execute("UPDATE characters SET afro = ?, gold = 0, max_specs = 1,"
               " level = 0, hp = NULL, sp = NULL WHERE id = ?",
               (progression.START_AFRO, char_id))


def connect():
    db = storage.connect(DB_PATH)
    # Журнал и таймаут выставляет сам storage: два процесса держат эту
    # базу -- сервер игры и страница регистрации, -- и писатель не должен
    # запирать читателя на всю транзакцию. Схема одна на обе базы: для
    # Postgres она переводится, а не переписывается второй раз. И
    # перестраивает её один процесс за раз (storage.PostgresDB.schema_lock).
    with db.schema_lock():
        db.create_schema(SCHEMA)
        migrate(db)
    return db


class Store:
    def __init__(self, path=None):
        global DB_PATH
        if path:
            DB_PATH = path
        self.db = connect()
        # (source, ref) a purse written now is booked under (money_ledger),
        # set around a command by its handler (booked_as); None books it
        # under LEDGER_OTHER. The game server is one thread: a command runs
        # to its end before the next one starts.
        self.money_source = None

    @contextlib.contextmanager
    def booked_as(self, source, ref=0):
        """Book every purse written inside this block under source and ref
        (money_ledger), the one around it back after."""
        was = self.money_source
        self.money_source = (str(source), int(ref or 0))
        try:
            yield self
        finally:
            self.money_source = was

    def _book(self, char_id, afro=None, gold=None, source=None, ref=0, level=None):
        """book() under source and ref, or else under money_source."""
        if source is None:
            source, ref = self.money_source or (LEDGER_OTHER, 0)
        return book(self.db, char_id, afro, gold, source, ref, level)

    # --- accounts --------------------------------------------------------
    def register(self, login, password):
        """Create an account. Returns (account_id, error); error is a message."""
        login = (login or "").strip()
        if len(login) < 3:
            return None, "Логин короче трёх символов"
        if len(login) > 20:
            return None, "Логин длиннее двадцати символов"
        if not password:
            return None, "Введите пароль"
        if len(password) < 4:
            return None, "Пароль короче четырёх символов"
        cred = credential(login, password)
        try:
            new_id = self.db.insert(
                "INSERT INTO accounts (login, hash, created) VALUES (?, ?, ?)",
                (login, cred, int(time.time())), returning="id")
            self.db.commit()
            return new_id, None
        except storage.IntegrityError:
            row = self.db.execute("SELECT id FROM accounts WHERE login = ?",
                                  (login,)).fetchone()
            if row:
                return None, "Такой логин уже занят"
            # Same digest under a different name: the client could not tell the
            # two accounts apart, since the digest is all it ever sends.
            return None, "Выберите другой пароль"

    def by_credential(self, cred):
        return self.db.execute("SELECT * FROM accounts WHERE hash = ?",
                               (cred,)).fetchone()

    def account_count(self):
        return self.db.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"]

    def all_accounts(self):
        return self.db.execute(
            "SELECT * FROM accounts ORDER BY id").fetchall()

    def set_banned(self, account_id, flag=True):
        self.db.execute("UPDATE accounts SET banned = ? WHERE id = ?",
                        (1 if flag else 0, account_id))
        self.db.commit()

    def account_by_login(self, login):
        return self.db.execute("SELECT * FROM accounts WHERE login = ?",
                               (login,)).fetchone()

    # --- e-mail: confirming an address, a new password by a link ------------
    # (server/email_flow.py). The token itself goes out in a letter and is
    # never stored; email_tokens keeps its sha256.

    def account_by_id(self, account_id):
        return self.db.execute("SELECT * FROM accounts WHERE id = ?",
                               (account_id,)).fetchone()

    def account_by_login_loose(self, login):
        """The account a person means by the login they typed: the exact one
        first, else the one that differs only in letter case. Logins are
        unique as typed; two that differ only in case leave the loose match
        to nobody."""
        login = (login or "").strip()
        row = self.account_by_login(login)
        if row or not login:
            return row
        folded = login.casefold()
        found = [r for r in self.all_accounts() if r["login"].casefold() == folded]
        return found[0] if len(found) == 1 else None

    def accounts_by_email(self, email):
        """The accounts whose confirmed address this is (a player may keep
        several accounts on one address)."""
        return self.db.execute(
            "SELECT * FROM accounts WHERE email = ? AND email_ok = 1 ORDER BY id",
            ((email or "").strip().lower(),)).fetchall()

    def set_email_unconfirmed(self, account_id, email):
        """Write an address the account has no confirmed one in place of:
        shown in the cabinet as waiting. A confirmed address is left as it is
        -- the new one waits in its token until its own link is opened."""
        self.db.execute(
            "UPDATE accounts SET email = ?, email_ok = 0 WHERE id = ? AND email_ok = 0",
            ((email or "").strip().lower(), account_id))
        self.db.commit()

    def issue_email_token(self, account_id, kind, email, ttl, now=None):
        """A new link's token for this account: the token, to go out in the
        letter, while only its digest is kept."""
        now = int(now if now is not None else time.time())
        token = secrets.token_urlsafe(32)
        self.db.insert(
            "INSERT INTO email_tokens (account_id, kind, digest, email, created, expires)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, kind, hashlib.sha256(token.encode("ascii")).hexdigest(),
             (email or "").strip().lower(), now, now + int(ttl)), returning="id")
        self.db.commit()
        return token

    def email_tokens_since(self, account_id, since, kind):
        """How many letters of this kind with a link this account was sent
        from since on."""
        return self.db.execute(
            "SELECT COUNT(*) c FROM email_tokens"
            " WHERE account_id = ? AND kind = ? AND created >= ?",
            (account_id, kind, int(since))).fetchone()["c"]

    def take_email_token(self, token, kind, now=None):
        """Spend a link: the token's row if it was this kind, unspent and in
        time -- spent by this very call, so a second opening of the same
        link finds nothing -- else (None, why) with why one of 'unknown',
        'used', 'expired'."""
        now = int(now if now is not None else time.time())
        if not token or len(token) > 200:
            return None, "unknown"
        digest = hashlib.sha256(token.encode("ascii", "replace")).hexdigest()
        row = self.db.execute(
            "SELECT * FROM email_tokens WHERE digest = ? AND kind = ?",
            (digest, kind)).fetchone()
        if not row:
            return None, "unknown"
        if row["used"]:
            return None, "used"
        if row["expires"] < now:
            return None, "expired"
        # Spent by an UPDATE that only one of two racing openings can win.
        cur = self.db.execute(
            "UPDATE email_tokens SET used = 1 WHERE id = ? AND used = 0", (row["id"],))
        self.db.commit()
        if cur.rowcount != 1:
            return None, "used"
        return row, None

    def confirm_email(self, account_id, email):
        """The address a confirm link carried becomes the account's own."""
        self.db.execute("UPDATE accounts SET email = ?, email_ok = 1 WHERE id = ?",
                        ((email or "").strip().lower(), account_id))
        # Older confirm links of this account would put back an address it
        # has moved away from.
        self.db.execute(
            "UPDATE email_tokens SET used = 1 WHERE account_id = ? AND kind = 'confirm'",
            (account_id,))
        self.db.commit()

    def set_password(self, account_id, password):
        """A new password for the account, by a reset link: its digest
        replaced (credential), every other reset link of the account spent.
        Returns None, or a message for the person."""
        if not password:
            return "Введите пароль"
        if len(password) < 4:
            return "Пароль короче четырёх символов"
        row = self.account_by_id(account_id)
        if not row:
            return "Аккаунта больше нет"
        try:
            self.db.execute("UPDATE accounts SET hash = ? WHERE id = ?",
                            (credential(row["login"], password), account_id))
            self.db.commit()
        except storage.IntegrityError:
            # The digest is the account's key (register): the same password
            # and login run together as another account's.
            return "Выберите другой пароль"
        self.db.execute(
            "UPDATE email_tokens SET used = 1 WHERE account_id = ? AND kind = 'reset'",
            (account_id,))
        self.db.commit()
        return None

    def find_characters(self, query, limit=40):
        """Characters whose name contains this, with the owning login.

        The panel used to list everybody, which is fine for three accounts
        and useless for three hundred. Matching is case-insensitive the way
        sqlite does it for ASCII only, so LOWER is applied to both sides for
        the Cyrillic the nicknames are actually in.
        """
        like = "%" + (query or "").strip().lower() + "%"
        # pylower, not sqlite's LOWER: that one folds ASCII and nothing else,
        # so a search for "Вет" would never find "Ветеран" -- which is most
        # nicknames on this server.
        self.db.create_function("pylower", 1,
                                lambda s: (s or "").lower(), deterministic=True)
        return self.db.execute(
            "SELECT c.*, a.login, a.banned FROM characters c"
            " JOIN accounts a ON a.id = c.account_id"
            " WHERE %s LIKE ? OR %s LIKE ?"
            % (storage.lower("c.name"), storage.lower("a.login")) +
            " ORDER BY c.name LIMIT ?", (like, like, limit)).fetchall()

    # --- who is in the game ----------------------------------------------
    def set_online(self, rows):
        """Replace the snapshot. rows: dicts with the online columns."""
        now = int(time.time())
        with self.db:
            self.db.execute("DELETE FROM online")
            self.db.executemany(
                "INSERT INTO online (char_id, nick, login, loc, title, gx, gy,"
                " since, seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(r["char_id"], r["nick"], r.get("login", ""), r.get("loc"),
                  r.get("title", ""), r.get("gx"), r.get("gy"),
                  r.get("since", now), now) for r in rows])
            self.db.execute(
                "INSERT INTO heartbeat (id, at) VALUES (1, ?)"
                " ON CONFLICT(id) DO UPDATE SET at = excluded.at", (now,))

    def online(self):
        """Who the game server last said was playing, and when it last said.

        Returns (rows, at). `at` is None when the game server has never
        written, and an old one means it is not writing now -- which the
        panel says out loud rather than showing an empty list as if it were
        the truth.
        """
        rows = self.db.execute(
            "SELECT * FROM online ORDER BY nick").fetchall()
        beat = self.db.execute("SELECT at FROM heartbeat WHERE id = 1"
                               ).fetchone()
        return rows, (beat["at"] if beat else None)

    # --- a stop announced ahead (stopwarn.py) ----------------------------
    def set_stop_plan(self, stop_at, made_at, admin, players):
        """The game's word on the stop it has announced: stop_at None when
        there is none."""
        with self.db:
            self.db.execute(
                "INSERT INTO stop_plan (id, stop_at, made_at, admin, players)"
                " VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET"
                " stop_at = excluded.stop_at, made_at = excluded.made_at,"
                " admin = excluded.admin, players = excluded.players",
                (None if stop_at is None else int(stop_at), int(made_at or 0),
                 str(admin or ""), int(players)))

    def stop_plan(self):
        """stop_plan's row as a dict, or None before the game first wrote it."""
        row = self.db.execute("SELECT * FROM stop_plan WHERE id = 1").fetchone()
        return dict(row) if row else None

    # --- admin actions ---------------------------------------------------
    def admin_push(self, admin, kind, char_id=None, account_id=None, **args):
        """Queue one action for the game server to carry out."""
        new_id = self.db.insert(
            "INSERT INTO admin_actions (made_at, admin, kind, char_id,"
            " account_id, args_json) VALUES (?, ?, ?, ?, ?, ?)",
            (int(time.time()), admin, kind, char_id, account_id,
             json.dumps(args, ensure_ascii=False)), returning="id")
        self.db.commit()
        return new_id

    def admin_pending(self):
        return self.db.execute(
            "SELECT * FROM admin_actions WHERE done_at IS NULL ORDER BY id"
        ).fetchall()

    def admin_done(self, action_id, result):
        self.db.execute(
            "UPDATE admin_actions SET done_at = ?, result = ? WHERE id = ?",
            (int(time.time()), result, action_id))
        self.db.commit()

    def admin_recent(self, limit=40):
        return self.db.execute(
            "SELECT * FROM admin_actions ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()

    # --- stance steps ordered on the site (server/site_orders.py) ------------
    # Not the admin queue: the site writes these rows with a database role
    # that may insert here and nothing else, and the game carries them out
    # with a handler that knows nothing but a stance step.
    def site_pending(self, limit=20):
        """The site's orders still waiting, oldest first."""
        return self.db.execute(
            "SELECT * FROM site_orders WHERE done_at IS NULL ORDER BY id LIMIT ?",
            (int(limit),)).fetchall()

    def site_done(self, order_id, code, result, when=None):
        """An order answered without a step (a refusal): its code and words.
        False when it was answered already -- a step is marked done by
        clan_stance_step itself, and nothing here writes over it."""
        with self.db:
            hit = self.db.execute(
                "UPDATE site_orders SET done_at = ?, code = ?, result = ?"
                " WHERE id = ? AND done_at IS NULL",
                (float(when if when is not None else time.time()), str(code), str(result),
                 int(order_id))).rowcount
        return hit == 1

    def site_order(self, order_id):
        """One order as it stands now, or None."""
        row = self.db.execute("SELECT * FROM site_orders WHERE id = ?",
                              (int(order_id),)).fetchone()
        return dict(row) if row else None

    # --- characters ------------------------------------------------------
    def characters(self, account_id):
        return self.db.execute(
            "SELECT * FROM characters WHERE account_id = ? ORDER BY slot",
            (account_id,)).fetchall()

    def create_character(self, account_id, name, sex, res, home=None):
        """A new row and its stats: (id, slot). home is (loc, gx, gy), where
        it wakes (server.START_PLACES): written as its place and as its
        home both, in the one INSERT, so the first login and a resurrection
        before any «Прописка» find the same start. None leaves both empty,
        as every row made before the start was drawn is."""
        used = [r["slot"] for r in self.characters(account_id)]
        slot = next(i for i in range(100) if i not in used)
        loc, gx, gy = home if home is not None else (None, None, None)
        char_id = self.db.insert(
            "INSERT INTO characters (account_id, slot, name, sex, res, loc, gx, gy,"
            " home_loc, home_gx, home_gy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, slot, name, sex, str(res), loc, gx, gy, loc, gx, gy),
            returning="id")
        # SQLite gives the id of a deleted last character to the next one
        # (INTEGER PRIMARY KEY without AUTOINCREMENT; a Postgres identity
        # never comes back): what outlives a character under its id is not
        # the newcomer's -- the loans of its quests go, its ledger rows stay
        # history under the id negated.
        self.db.execute("DELETE FROM char_lent WHERE char_id = ?", (char_id,))
        self.db.execute("UPDATE money_ledger SET char_id = ? WHERE char_id = ?",
                        (-char_id, char_id))
        # Nor the clan: a membership row left under the id would make the
        # newborn a member, with the dead one's rights (clans.py).
        self.db.execute("DELETE FROM clan_members WHERE char_id = ?", (char_id,))
        # The client never sends a stat: everything a newborn has is decided
        # here (wiki: "задаётся в GSDL, экземпляр Player_Trait"). The purse
        # it is born with is the ledger's first row of it (seed_stats).
        seed_stats(self.db, char_id)
        self.db.commit()
        return char_id, slot

    def character(self, char_id):
        return self.db.execute("SELECT * FROM characters WHERE id = ?",
                               (char_id,)).fetchone()

    # --- progression -----------------------------------------------------
    def load_stats(self, char_id):
        return self.db.execute(
            "SELECT kind, idx, value, xp, xp_max FROM char_stats"
            " WHERE char_id = ? ORDER BY kind, idx", (char_id,)).fetchall()

    def save_stats(self, char_id, rows):
        """rows: (kind, idx, value, xp, xp_max), the whole set at once."""
        self.db.replace("char_stats",
                        ("char_id", "kind", "idx", "value", "xp", "xp_max"),
                        [(char_id,) + tuple(r) for r in rows],
                        conflict=("char_id", "kind", "idx"))
        self.db.commit()

    def save_character_state(self, char_id, **cols):
        """Money, vitals, premium, reputation, counters: any of the columns
        in CHARACTER_COLUMNS, by name."""
        allowed = {c for c, _d in CHARACTER_COLUMNS}
        cols = {k: v for k, v in cols.items() if k in allowed}
        if not cols:
            return
        if "afro" in cols or "gold" in cols:
            # The purse moves: its ledger row goes with it (book).
            self._book(char_id, cols.get("afro"), cols.get("gold"),
                       level=cols.get("level"))
        keys = list(cols)
        self.db.execute(
            "UPDATE characters SET %s WHERE id = ?"
            % ", ".join("%s = ?" % k for k in keys),
            [cols[k] for k in keys] + [char_id])
        self.db.commit()

    def name_taken(self, name):
        return self.db.execute("SELECT 1 FROM characters WHERE name = ?",
                               (name,)).fetchone() is not None

    def character_by_name(self, name):
        """The character called name, exactly or ignoring case, or None.

        Mail addresses by the name typed into the window (sndml;to=@..@),
        the same way private chat does; the id never travels.
        """
        row = self.db.execute("SELECT * FROM characters WHERE name = ?",
                              (name,)).fetchone()
        if row is not None:
            return row
        want = name.casefold()
        for row in self.db.execute("SELECT * FROM characters"):
            if row["name"].casefold() == want:
                return row
        return None

    def save_position(self, char_id, loc, pos, gx, gy, on_map):
        self.db.execute(
            "UPDATE characters SET loc = ?, pos = ?, gx = ?, gy = ?, on_map = ?"
            " WHERE id = ?", (loc, pos, gx, gy, 1 if on_map else 0, char_id))
        self.db.commit()

    # --- money -----------------------------------------------------------
    def money(self, char_id):
        """(afro, gold) of a character; gold in hundredths of an ounce."""
        row = self.db.execute("SELECT afro, gold FROM characters WHERE id = ?",
                              (char_id,)).fetchone()
        return (row["afro"], row["gold"]) if row else (0, 0)

    def set_money(self, char_id, afro, gold):
        self._book(char_id, afro, gold)
        self.db.execute("UPDATE characters SET afro = ?, gold = ? WHERE id = ?",
                        (int(afro), int(gold), char_id))
        self.db.commit()

    # --- the money ledger (money_ledger, book) -------------------------------
    def ledger(self, char_id=None, since=0):
        """The ledger's rows, oldest first: of one character, or of all."""
        if char_id is None:
            return [dict(r) for r in self.db.execute(
                "SELECT * FROM money_ledger WHERE at >= ? ORDER BY id", (int(since),))]
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM money_ledger WHERE char_id = ? AND at >= ? ORDER BY id",
            (int(char_id), int(since)))]

    # --- what a quest lent that is used up by its use (char_lent) --------------
    def lent_at(self, char_id, quest_type):
        """When this quest last lent the character its rounds or medicine,
        or None."""
        row = self.db.execute("SELECT lent_at FROM char_lent WHERE char_id = ? AND type = ?",
                              (int(char_id), int(quest_type))).fetchone()
        return int(row["lent_at"]) if row else None

    def note_lent(self, char_id, quest_type, when=None):
        self.db.replace("char_lent", ("char_id", "type", "lent_at"),
                        [(int(char_id), int(quest_type), int(when or time.time()))],
                        conflict=("char_id", "type"))
        self.db.commit()

    def forget_lent(self, char_id, quest_type):
        """The loan struck: all of it came back unused (server.py
        Session.cmd_q_ca), so the quest may lend again today."""
        self.db.execute("DELETE FROM char_lent WHERE char_id = ? AND type = ?",
                        (int(char_id), int(quest_type)))
        self.db.commit()

    # --- items -----------------------------------------------------------
    # One row per item instance; a stack of ammunition is one row with a
    # count. The wire id is derived from (uniq, type_id, root) by
    # inventory.oid, never stored, so the layout can change in one place.
    def items_of(self, char_id):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM items WHERE char_id = ? ORDER BY uniq",
            (char_id,)).fetchall()]

    def item(self, uniq):
        row = self.db.execute("SELECT * FROM items WHERE uniq = ?",
                              (uniq,)).fetchone()
        return dict(row) if row else None

    def create_item(self, char_id, type_id, root, **fields):
        """Insert an instance; returns its row. Unset fields take the defaults."""
        unknown = set(fields) - set(ITEM_FIELDS)
        if unknown:
            raise ValueError("no such item field: %s" % ", ".join(sorted(unknown)))
        cols = ["char_id", "type_id", "root"] + list(fields)
        vals = [char_id, type_id, root] + [int(v) for v in fields.values()]
        uniq = self.db.insert(
            "INSERT INTO items (%s) VALUES (%s)"
            % (", ".join(cols), ", ".join("?" * len(cols))), vals,
            returning="uniq")
        self.db.commit()
        return self.item(uniq)

    def update_item(self, uniq, **fields):
        unknown = set(fields) - set(ITEM_FIELDS)
        if unknown:
            raise ValueError("no such item field: %s" % ", ".join(sorted(unknown)))
        if not fields:
            return
        self.db.execute(
            "UPDATE items SET %s WHERE uniq = ?"
            % ", ".join("%s = ?" % k for k in fields),
            [int(v) for v in fields.values()] + [uniq])
        self.db.commit()

    def delete_item(self, uniq):
        self.db.execute("DELETE FROM items WHERE uniq = ?", (uniq,))
        self.db.commit()

    def clear_ground(self, loot_owner, now=None):
        """Delete every item row lying on the ground that has nowhere to lie
        any more; returns how many.

        A bag on the ground is the game server's memory (combat.RoomCombat.
        loot) over rows owned by nobody (combat.LOOT_OWNER), each with a
        ground row saying where it lies and until when (lay_down): a thing
        that runs out goes (sweep_ground), a pick-up gives it an owner
        (pick_up). The game server asks this as it starts, before any room
        exists -- no other process makes a bag -- and puts back what is left
        (combat.restore_ground). What goes: a thing whose time ran out while
        nothing was running, and one with no ground row at all -- put down
        by a server from before the table, or caught between the two writes
        of a death (drop_items, then the bag); it is in no room and could
        never be opened. And a ground row whose thing is gone or somebody's."""
        now = time.time() if now is None else float(now)
        due = "SELECT uniq FROM ground WHERE expires_at > ?"
        owner = int(loot_owner)
        with self.db:
            # A trophy lying out goes with its words (the trophies table); one
            # registered, in somebody's collection, has no items row to match.
            self.db.execute("DELETE FROM trophies WHERE registered_at IS NULL AND uniq IN"
                            " (SELECT uniq FROM items WHERE char_id = ? AND uniq NOT IN"
                            " (%s))" % due, (owner, now))
            n = self.db.execute("DELETE FROM items WHERE char_id = ? AND uniq NOT IN (%s)"
                                % due, (owner, now)).rowcount
            self.db.execute("DELETE FROM ground WHERE expires_at <= ? OR uniq NOT IN"
                            " (SELECT uniq FROM items WHERE char_id = ?)", (now, owner))
        return max(0, n or 0)

    # --- the ground (the ground table, combat.RoomCombat.loot) -------------------
    GROUND_COLUMNS = ("uniq", "loc", "gx", "gy", "cell", "expires_at")

    def lay_down(self, things, place, cell):
        """Write down where things put on the ground lie and until when:
        things is {uniq: the epoch second it goes}, place the room's (loc,
        gx, gy) -- gx and gy None for a place that is one room -- and cell
        the hex of the bag. A thing written down already is written over."""
        loc, gx, gy = place
        self.db.replace("ground", self.GROUND_COLUMNS,
                        [(int(u), int(loc), None if gx is None else int(gx),
                          None if gy is None else int(gy), int(cell), float(t))
                         for u, t in things.items()], conflict=("uniq",))
        self.db.commit()

    def on_ground(self, loot_owner):
        """The ground rows of every thing lying out, by serial: what the game
        server puts back into the rooms as it starts (combat.restore_ground),
        after clear_ground has taken away what has nowhere to lie."""
        return [dict(r) for r in self.db.execute(
            "SELECT g.uniq, g.loc, g.gx, g.gy, g.cell, g.expires_at FROM ground g"
            " JOIN items i ON i.uniq = g.uniq WHERE i.char_id = ? ORDER BY g.uniq",
            (int(loot_owner),)).fetchall()]

    def pick_up(self, uniqs, char_id, slot):
        """Things off the ground into char_id's slot, in one transaction: each
        items row changes owner under its own serial -- the oid the client
        already holds the thing under -- and its ground row goes with it."""
        with self.db:
            for u in uniqs:
                self.db.execute("UPDATE items SET char_id = ?, slot = ? WHERE uniq = ?",
                                (int(char_id), int(slot), int(u)))
                self.db.execute("DELETE FROM ground WHERE uniq = ?", (int(u),))

    def sweep_ground(self, uniqs, loot_owner):
        """Things on the ground whose time has run out (combat.RoomCombat.
        expire_bag), gone for good in one transaction: the items row, a
        trophy's words with it (forget_trophy's rule) and the ground row. A
        row that is somebody's is left alone, words and all."""
        owner = int(loot_owner)
        with self.db:
            for u in uniqs:
                self.db.execute("DELETE FROM trophies WHERE uniq = ? AND registered_at IS NULL"
                                " AND uniq IN (SELECT uniq FROM items WHERE char_id = ?)",
                                (int(u), owner))
                self.db.execute("DELETE FROM items WHERE uniq = ? AND char_id = ?",
                                (int(u), owner))
                self.db.execute("DELETE FROM ground WHERE uniq = ?", (int(u),))

    # --- bosses killed in their window (the boss_kills table) --------------------------
    def boss_killed(self, spot, slot):
        """Write down that the boss at spot (combat.RoomCombat.boss_spot)
        was killed in the window that opened at slot (bosses.slot). One row
        a boss: a boss written down already is written over."""
        self.db.replace("boss_kills", ("spot", "slot"), [(str(spot), float(slot))],
                        conflict=("spot",))
        self.db.commit()

    def boss_kills(self, spots):
        """{spot: the window of its last kill} for those of these spots
        written down (boss_killed); the game server asks it as it makes a
        room with bosses in it (combat.RoomCombat.recall_kills)."""
        spots = sorted({str(s) for s in spots})
        if not spots:
            return {}
        rows = self.db.execute(
            "SELECT spot, slot FROM boss_kills WHERE spot IN (%s)"
            % ", ".join("?" * len(spots)), spots).fetchall()
        return {r["spot"]: float(r["slot"]) for r in rows}

    # --- sites clans hold (server/holdings.py; clan_holdings, clan_holding_log) ---------
    _HOLDING = ("SELECT h.site, h.clan_id, k.name, h.since, h.by_char, h.slot"
                " FROM clan_holdings h JOIN clans k ON k.id = h.clan_id")

    def holding(self, site):
        """Who holds the site: {site, clan_id, name, since, by_char, slot},
        or None. A row whose clan is gone is nobody's (the JOIN leaves it
        out), as a membership's is (clan_member)."""
        row = self.db.execute(self._HOLDING + " WHERE h.site = ?", (str(site),)).fetchone()
        return dict(row) if row else None

    def holdings(self):
        """Every site held, by its key."""
        return [dict(r) for r in self.db.execute(self._HOLDING + " ORDER BY h.site")]

    def holding_set(self, site, clan_id, how, by_char=None, slot=None, when=None):
        """The clan holds the site from now (a capture, the admin's order), in
        one transaction with its row in the log. Returns (the clan that held
        it before or None, "ok" | "same" | "gone"): "same" when it already
        holds it -- nothing written, its since unchanged, so an order run
        twice is one -- and "gone" when the clan is no more by the time of
        the write (the INSERT names it: a disband a moment earlier, from
        another process too). INSERT ... SELECT, since db.replace cannot
        carry the condition; SQLite reads ON CONFLICT after a SELECT only
        when the SELECT has its WHERE, which this one has."""
        when = float(when or time.time())
        with self.db:
            row = self.db.execute(
                "SELECT h.clan_id FROM clan_holdings h JOIN clans k ON k.id = h.clan_id"
                " WHERE h.site = ?", (str(site),)).fetchone()
            prev = int(row["clan_id"]) if row else None
            if prev == int(clan_id):
                return prev, "same"
            hit = self.db.execute(
                "INSERT INTO clan_holdings (site, clan_id, since, by_char, slot)"
                " SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM clans WHERE id = ?)"
                " ON CONFLICT (site) DO UPDATE SET clan_id = EXCLUDED.clan_id,"
                " since = EXCLUDED.since, by_char = EXCLUDED.by_char, slot = EXCLUDED.slot",
                (str(site), int(clan_id), when, by_char, slot, int(clan_id))).rowcount
            if hit != 1:
                return prev, "gone"
            self._holding_log(site, how, int(clan_id), prev, by_char, slot, when)
        return prev, "ok"

    def holding_clear(self, site, how, clan_id=None, when=None):
        """Nobody holds the site from now -- only if clan_id holds it, when
        given, so a stale or repeated order clears nothing -- in one
        transaction with its row in the log. Returns the clan that held it,
        or None when nothing was cleared."""
        when = float(when or time.time())
        cond, args = ("", (str(site),)) if clan_id is None else \
            (" AND clan_id = ?", (str(site), int(clan_id)))
        with self.db:
            rows = self.db.execute("DELETE FROM clan_holdings WHERE site = ?" + cond
                                   + " RETURNING clan_id", args).fetchall()
            if not rows:
                return None
            prev = int(rows[0]["clan_id"])
            self._holding_log(site, how, None, prev, None, None, when)
        return prev

    def holding_logged(self, site, how, clan_id, by_char=None, slot=None, when=None):
        """A row in the log alone: a defence, a kill that took nothing. The
        holder stands as it was, before and after."""
        with self.db:
            self._holding_log(site, how, clan_id, clan_id, by_char, slot,
                              float(when or time.time()))

    def _holding_log(self, site, how, clan_id, prev, by_char, slot, when):
        self.db.execute("INSERT INTO clan_holding_log (at, site, clan_id, prev, how, by_char,"
                        " slot) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (float(when), str(site), clan_id, prev, str(how), by_char, slot))

    def holding_log(self, site=None, limit=50):
        """The log, newest first; of one site when given."""
        where, args = ("", ()) if site is None else (" WHERE site = ?", (str(site),))
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM clan_holding_log" + where + " ORDER BY id DESC LIMIT ?",
            args + (int(limit),))]

    def holdings_lost(self, clan_id):
        """The sites a disband took from the clan (clan_drop's 'disband'
        rows): the ids of clans are never handed out again, so these are
        that one disband's."""
        return [r["site"] for r in self.db.execute(
            "SELECT DISTINCT site FROM clan_holding_log WHERE prev = ? AND how = 'disband'"
            " ORDER BY site", (int(clan_id),))]

    def add_money(self, char_id, afro=0, gold=0):
        """Credit (or, negative, debit) the purse; returns the new (afro, gold)."""
        have = self.money(char_id)
        self._book(char_id, have[0] + int(afro), have[1] + int(gold))
        self.db.execute(
            "UPDATE characters SET afro = afro + ?, gold = gold + ? WHERE id = ?",
            (int(afro), int(gold), char_id))
        self.db.commit()
        return self.money(char_id)

    def bank_expand(self, char_id, afro, gold):
        """One more step of bank storage and the purse that paid for it,
        in one transaction. Two commits, the purse's and then the count's,
        left after a stop between them the ounce taken and no capacity
        given. Returns the new count of steps."""
        with self.db:
            self.db.execute("UPDATE characters SET bank_steps ="
                            " COALESCE(bank_steps, 0) + 1 WHERE id = ?", (char_id,))
            self._purse((char_id, afro, gold), "bank")
        return self.character(char_id)["bank_steps"]

    def set_home(self, char_id, loc, gx=None, gy=None):
        self.db.execute(
            "UPDATE characters SET home_loc = ?, home_gx = ?, home_gy = ?"
            " WHERE id = ?", (loc, gx, gy, char_id))
        self.db.commit()

    # --- map marks -------------------------------------------------------
    # The list is what the client indexes by, so it is kept dense: a removal
    # renumbers everything behind it, exactly as Array.splice does on the
    # other side (GlobalMap.__removeMark).
    def marks(self, char_id):
        return [dict(r) for r in self.db.execute(
            "SELECT idx, x, y, title, info FROM map_marks WHERE char_id = ?"
            " ORDER BY idx", (char_id,)).fetchall()]

    def insert_mark(self, char_id, x, y, title, info):
        """Append a mark; returns its index."""
        idx = self.db.execute(
            "SELECT COUNT(*) c FROM map_marks WHERE char_id = ?",
            (char_id,)).fetchone()["c"]
        self.db.execute(
            "INSERT INTO map_marks (char_id, idx, x, y, title, info)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (char_id, idx, int(x), int(y), title, info))
        self.db.commit()
        return idx

    def update_mark(self, char_id, idx, title, info):
        cur = self.db.execute(
            "UPDATE map_marks SET title = ?, info = ? WHERE char_id = ? AND idx = ?",
            (title, info, char_id, idx))
        self.db.commit()
        return cur.rowcount > 0

    def remove_mark(self, char_id, idx):
        """Drop the mark at idx and close the gap. Returns False for an
        index that names nothing."""
        rows = self.marks(char_id)
        if not (0 <= idx < len(rows)):
            return False
        del rows[idx]
        # Rewritten whole rather than shifted in place: idx is part of the
        # primary key, and SQLite checks it row by row during an UPDATE, so
        # a bulk "idx = idx - 1" can collide with the row it has not moved yet.
        self.db.execute("DELETE FROM map_marks WHERE char_id = ?", (char_id,))
        self.db.executemany(
            "INSERT INTO map_marks (char_id, idx, x, y, title, info)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [(char_id, n, r["x"], r["y"], r["title"], r["info"])
             for n, r in enumerate(rows)])
        self.db.commit()
        return True

    # --- quests ----------------------------------------------------------
    # An instance is one row of char_quests for as long as the character
    # carries it; q_id is the row id, so it is unique across characters, which
    # is what the client assumes (QuestInspector keys currentQuests by it).
    def quests(self, char_id):
        return self.db.execute(
            "SELECT * FROM char_quests WHERE char_id = ? ORDER BY q_id",
            (char_id,)).fetchall()

    def quest(self, q_id):
        return self.db.execute("SELECT * FROM char_quests WHERE q_id = ?",
                               (q_id,)).fetchone()

    def has_quest(self, char_id, quest_type):
        return self.db.execute(
            "SELECT 1 FROM char_quests WHERE char_id = ? AND type = ?",
            (char_id, quest_type)).fetchone() is not None

    def take_quest(self, char_id, quest_type, progress, complete):
        q_id = self.db.insert(
            "INSERT INTO char_quests (char_id, type, progress_json, complete,"
            " taken_at) VALUES (?, ?, ?, ?, ?)",
            (char_id, quest_type, json.dumps(progress), 1 if complete else 0,
             int(time.time())), returning="q_id")
        self.db.commit()
        return q_id

    def update_quest(self, q_id, progress, complete):
        self.db.execute(
            "UPDATE char_quests SET progress_json = ?, complete = ? WHERE q_id = ?",
            (json.dumps(progress), 1 if complete else 0, q_id))
        self.db.commit()

    def drop_quest(self, q_id):
        self.db.execute("DELETE FROM char_quests WHERE q_id = ?", (q_id,))
        self.db.commit()

    def finish_quest(self, q_id, char_id, quest_type, when=None):
        """Hand the instance in: it leaves the log and joins the history that
        non-repeatable checks and the daily count are answered from."""
        self.db.execute("DELETE FROM char_quests WHERE q_id = ?", (q_id,))
        self.db.execute(
            "INSERT INTO char_quests_done (char_id, type, done_at) VALUES (?, ?, ?)",
            (char_id, quest_type, int(when or time.time())))
        self.db.commit()

    def quest_done(self, char_id, quest_type):
        return self.db.execute(
            "SELECT 1 FROM char_quests_done WHERE char_id = ? AND type = ?",
            (char_id, quest_type)).fetchone() is not None

    def first_done(self, char_id, types):
        """Of these types, the one handed in first -- the earliest done_at,
        and the row written first between two of one second -- or None when
        none of them is in the history: which branch of a choice a
        character took up first (server.py Session.excluded)."""
        types = sorted({int(t) for t in types})
        if not types:
            return None
        row = self.db.execute(
            "SELECT type FROM char_quests_done WHERE char_id = ? AND type IN (%s)"
            " ORDER BY done_at, id LIMIT 1" % ", ".join("?" * len(types)),
            (char_id, *types)).fetchone()
        return row["type"] if row is not None else None

    def quests_done_since(self, char_id, since, types=None):
        """Hand-ins since a moment; of these types only, when given -- the
        daily limit counts the repeatable ones (quests.repeatable_types)."""
        if types is None:
            return self.db.execute(
                "SELECT COUNT(*) c FROM char_quests_done WHERE char_id = ?"
                " AND done_at >= ?", (char_id, int(since))).fetchone()["c"]
        types = sorted({int(t) for t in types})
        if not types:
            return 0
        return self.db.execute(
            "SELECT COUNT(*) c FROM char_quests_done WHERE char_id = ?"
            " AND done_at >= ? AND type IN (%s)" % ", ".join("?" * len(types)),
            (char_id, int(since), *types)).fetchone()["c"]

    def account_quests_done_since(self, account_id, since, types):
        """Hand-ins of these types since a moment by any character of the
        account: a warehouse's box pays one character of an account a day
        (server/holdings.py box_refusal), where per_day counts one."""
        types = sorted({int(t) for t in types})
        if not types:
            return 0
        return self.db.execute(
            "SELECT COUNT(*) c FROM char_quests_done d JOIN characters c ON c.id = d.char_id"
            " WHERE c.account_id = ? AND d.done_at >= ? AND d.type IN (%s)"
            % ", ".join("?" * len(types)),
            (int(account_id), int(since), *types)).fetchone()["c"]

    # --- mail ------------------------------------------------------------
    # Rows are returned as dicts, like items: mail.py reads and rewrites
    # their fields and a sqlite3.Row cannot be assigned to.
    def mail_inbox(self, char_id):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM mail WHERE to_char = ? AND to_deleted = 0"
            " ORDER BY id", (char_id,)).fetchall()]

    def mail_outbox(self, char_id):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM mail WHERE from_char = ? AND from_deleted = 0"
            " ORDER BY id", (char_id,)).fetchall()]

    def mail_letter(self, mail_id):
        row = self.db.execute("SELECT * FROM mail WHERE id = ?",
                              (mail_id,)).fetchone()
        return dict(row) if row else None

    def _mail_insert(self, to_char, from_char, kind, subject, body, afro,
                     gold, items_json, when=None):
        """INSERT one letter without committing; returns its id."""
        return self.db.insert(
            "INSERT INTO mail (to_char, from_char, type, subject, body,"
            " sent_at, afro, gold, items_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (to_char, from_char, int(kind), subject, body,
             int(when or time.time()), int(afro), int(gold), items_json),
            returning="id")

    def mail_send(self, to_char, from_char, kind, subject, body, afro, gold,
                  items_json, when=None):
        """File a letter; returns its row."""
        mail_id = self._mail_insert(to_char, from_char, kind, subject, body,
                                    afro, gold, items_json, when)
        self.db.commit()
        return self.mail_letter(mail_id)

    def mail_send_each(self, to_chars, from_char, kind, subject, body, purse,
                       when=None):
        """The same letter, with nothing in it, to each of to_chars, and the
        postage that paid for them, in ONE transaction: a clan's mail
        (mail.Mail.clan_letter). mail_send commits a letter at a time, and a
        stop between two commits would have charged for letters never filed
        or filed half a clan. The sender's outbox keeps the first alone:
        every other row is filed already deleted on his side. purse is his
        whole new (char_id, afro, gold), booked 'mail' with ref the first
        letter. Returns the rows in the order of to_chars."""
        when = int(when or time.time())
        with self.db:
            ids = [self._mail_insert(to, from_char, kind, subject, body, 0, 0,
                                     "[]", when) for to in to_chars]
            if len(ids) > 1:
                self.db.execute("UPDATE mail SET from_deleted = 1 WHERE id IN (%s)"
                                % ", ".join("?" * (len(ids) - 1)), ids[1:])
            self._purse(purse, "mail", ids[0] if ids else 0)
        return [self.mail_letter(i) for i in ids]

    # --- auction -----------------------------------------------------------
    # Each change is one transaction: the lot, the letters it produces and
    # the acting player's purse are written together or not at all, so a
    # stop between two commits can neither duplicate an item nor lose a bid.
    # A lost race is told by the write itself, which goes first: a SELECT
    # locks nothing -- in SQLite the transaction starts at the first write,
    # and a Postgres row is locked by an UPDATE or DELETE, not by a read --
    # so another process (tools/admin_account.py) could settle the lot
    # between a read and the write, and the letters would pay a second
    # time. The DELETE or UPDATE names the lot -- and, given `was`, the bid
    # the caller read on it and wrote its letters from; only when it
    # touched exactly one row are the letters filed and the purse charged.
    AUCTION_COLS = ("item_uniq", "type_id", "root", "item_json", "seller",
                    "seller_name", "currency", "start_bid", "buyout", "fee",
                    "hours", "created_at", "ends_at")

    def auction_lot(self, lot_id):
        row = self.db.execute("SELECT * FROM auction_lots WHERE id = ?",
                              (lot_id,)).fetchone()
        return dict(row) if row else None

    def auction_lot_by_item(self, uniq):
        row = self.db.execute("SELECT * FROM auction_lots WHERE item_uniq = ?",
                              (uniq,)).fetchone()
        return dict(row) if row else None

    def auction_active(self, now):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM auction_lots WHERE ends_at > ? ORDER BY id",
            (now,)).fetchall()]

    def auction_due(self, now):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM auction_lots WHERE ends_at <= ? ORDER BY id",
            (now,)).fetchall()]

    def auction_count(self, seller, now):
        return self.db.execute(
            "SELECT COUNT(*) c FROM auction_lots WHERE seller = ? AND ends_at > ?",
            (seller, now)).fetchone()["c"]

    def _purse(self, purse, source, ref=0):
        """A whole new purse, inside the caller's transaction, booked under
        source and ref (money_ledger)."""
        if purse is not None:
            char_id, afro, gold = purse
            self._book(char_id, afro, gold, source, ref)
            self.db.execute("UPDATE characters SET afro = ?, gold = ? WHERE id = ?",
                            (int(afro), int(gold), char_id))

    def _letters(self, letters):
        return [self._mail_insert(l["to_char"], l["from_char"], l["kind"],
                                  l["subject"], l["body"], l["afro"], l["gold"],
                                  l["items_json"]) for l in letters]

    @staticmethod
    def _standing(was):
        """The WHERE for a lot still holding the bid the caller read:
        `was` is (bidder, bid), or None for "whatever it holds"."""
        if was is None:
            return "", ()
        bidder, bid = was
        return " AND bidder = ? AND bid = ?", (int(bidder or 0), int(bid or 0))

    def auction_list(self, uniq, seller, lot, purse=None):
        """The item leaves the seller's bag and becomes a lot."""
        with self.db:
            gone = self.db.execute(
                "DELETE FROM items WHERE uniq = ? AND char_id = ?",
                (uniq, seller)).rowcount
            if gone != 1:
                # Raised inside the transaction, so it is rolled back:
                # nothing was deleted anyway, and no lot is made of an item
                # that is not there.
                raise ValueError("item %d is not character %d's" % (uniq, seller))
            vals = dict(lot, item_uniq=uniq)
            lot_id = self.db.insert(
                "INSERT INTO auction_lots (%s) VALUES (%s)"
                % (", ".join(self.AUCTION_COLS), ", ".join("?" * len(self.AUCTION_COLS))),
                [vals[c] for c in self.AUCTION_COLS], returning="id")
            self._purse(purse, "auction", lot_id)
        return self.auction_lot(lot_id)

    def auction_rebid(self, lot_id, bid, bidder, bidder_name, letters=(),
                      purse=None, was=None):
        """A new highest bid; the letters refund the one it beats.

        None when the lot is gone, or -- with `was`, the (bidder, bid) the
        letters were written from -- when that is no longer the standing
        bid: struck out by the admin tool, say, whose account's money went
        with it and must not come back by letter.
        """
        extra, args = self._standing(was)
        with self.db:
            hit = self.db.execute(
                "UPDATE auction_lots SET bid = ?, bidder = ?, bidder_name = ?"
                " WHERE id = ?" + extra,
                (int(bid), bidder, bidder_name, lot_id) + args).rowcount
            if hit != 1:
                return None
            ids = self._letters(letters)
            self._purse(purse, "auction", lot_id)
        return [self.mail_letter(i) for i in ids]

    def auction_close(self, lot_id, letters=(), purse=None, was=None):
        """The lot is over: gone from the table, its letters filed. None
        when somebody closed it first, so nothing is settled twice, or --
        with `was`, as for auction_rebid -- when the bid the letters settle
        is no longer the one on it."""
        extra, args = self._standing(was)
        with self.db:
            hit = self.db.execute("DELETE FROM auction_lots WHERE id = ?" + extra,
                                  (lot_id,) + args).rowcount
            if hit != 1:
                return None
            ids = self._letters(letters)
            self._purse(purse, "auction", lot_id)
        return [self.mail_letter(i) for i in ids]

    # --- barter ------------------------------------------------------------
    # Both halves of a barter (barter.py) in one transaction: every item
    # changes hands and both purses are written, or nothing is. An item moves
    # by an UPDATE that names it exactly as it was offered -- its owner, the
    # bag, its type, stack, wear, rounds and charges -- so a thing that
    # changed or left in the meantime is told by the write itself, which
    # then touches no row, and not by a read before it that locks nothing
    # (see the auction's note above).
    BARTER_GUARD = ("slot", "type_id", "root", "count", "brk", "max_break_cur",
                    "ammo_count", "ammo_type", "cur_mode", "use_count")

    def barter_swap(self, moves, purses):
        """moves: (row as offered, new owner) per item; purses: (char_id,
        afro, gold), each side's whole new purse. None when all of it is
        written; otherwise the serial of the first item no longer as offered,
        and nothing at all was written."""
        sql = ("UPDATE items SET char_id = ? WHERE uniq = ? AND char_id = ?"
               + "".join(" AND %s = ?" % c for c in self.BARTER_GUARD))
        try:
            with self.db:
                for row, to_char in moves:
                    hit = self.db.execute(
                        sql, [int(to_char), int(row["uniq"]), int(row["char_id"])]
                        + [int(row[c]) for c in self.BARTER_GUARD]).rowcount
                    if hit != 1:
                        # Raised inside the transaction, so every move
                        # before this one is rolled back with it.
                        raise _Stale(row["uniq"])
                sides = [int(p[0]) for p in purses]
                for purse in purses:
                    # ref: the other side of the barter
                    other = [c for c in sides if c != int(purse[0])]
                    self._purse(purse, "barter", other[0] if other else 0)
        except _Stale as stale:
            return stale.uniq
        return None

    # --- what a dead player loses --------------------------------------------
    # Every move of one death in one transaction (combat.Fighter.
    # drop_on_death): a thing that falls whole changes owner and place under
    # its own serial; a stack that loses part of itself keeps the rest under
    # its serial and the part becomes a row of its own, so the client, which
    # already holds the stack under that serial, only learns its new size.
    # Each write names the row as it was read -- its owner, place, type and
    # stack -- so a row that changed in the meantime is told by the write
    # touching nothing, and then nothing at all is written (the barter's
    # way, above): a death never loses half of what it was to lose, nor
    # anything twice.
    DEATH_GUARD = ("slot", "type_id", "root", "count")
    # What the split-off part copies from its stack besides type, root and
    # the new size: every other column an item has (ITEM_FIELDS).
    SPLIT_COPY = tuple(c for c in ITEM_FIELDS if c not in ("char_id", "slot", "count"))

    def drop_items(self, char_id, losses, owner, slot):
        """losses: (row as read, pieces) per thing of char_id's; pieces None
        moves the whole row to owner/slot, a number splits that many off
        into a new row there. Returns the rows now lying there, in the
        order given, or None when a row was no longer as read -- and then
        nothing at all was written."""
        guard = " AND char_id = ?" + "".join(" AND %s = ?" % c for c in self.DEATH_GUARD)
        whole = "UPDATE items SET char_id = ?, slot = ? WHERE uniq = ?" + guard
        part = "UPDATE items SET count = count - ? WHERE uniq = ?" + guard
        cols = ("char_id", "type_id", "root", "slot", "count") + self.SPLIT_COPY
        insert = "INSERT INTO items (%s) VALUES (%s)" % (", ".join(cols),
                                                         ", ".join("?" * len(cols)))
        placed = []
        try:
            with self.db:
                for row, pieces in losses:
                    key = [int(row["uniq"]), int(char_id)] + [int(row[c]) for c in self.DEATH_GUARD]
                    if pieces is None:
                        hit = self.db.execute(whole, [int(owner), int(slot)] + key).rowcount
                        placed.append(int(row["uniq"]))
                    elif 0 < pieces < row["count"]:
                        hit = self.db.execute(part, [int(pieces)] + key).rowcount
                        if hit == 1:
                            placed.append(self.db.insert(
                                insert, [int(owner), int(row["type_id"]), int(row["root"]),
                                         int(slot), int(pieces)]
                                + [int(row[c]) for c in self.SPLIT_COPY], returning="uniq"))
                    else:
                        hit = 0         # nothing to split: not as read either
                    if hit != 1:
                        # Raised inside the transaction, so every move
                        # before this one is rolled back with it.
                        raise _Stale(row["uniq"])
        except _Stale:
            return None
        return [self.item(u) for u in placed]

    # --- trophies (trophies.py) ------------------------------------------------
    # A trophy is an ordinary items row (root 6) while it is a thing, and its
    # words -- who killed whom, and when -- are a trophies row under the same
    # serial. Registering it (trophies.Collection.register) takes the items
    # row away and keeps the words, in the registrant's collection.
    def trophy(self, uniq):
        row = self.db.execute("SELECT * FROM trophies WHERE uniq = ?",
                              (int(uniq),)).fetchone()
        return dict(row) if row else None

    def create_trophy(self, char_id, slot, type_id, root, rec):
        """A new trophy: its items row and its words in one transaction, so
        there is never the one without the other. rec holds TROPHY_FIELDS
        but for type_id (and kills, 1 unless said). Returns the items row."""
        rec = dict(rec, type_id=int(type_id), kills=int(rec.get("kills", 1)))
        cols = ("uniq",) + TROPHY_FIELDS
        with self.db:
            uniq = self.db.insert(
                "INSERT INTO items (char_id, type_id, root, slot, count)"
                " VALUES (?, ?, ?, ?, 1)",
                (int(char_id), int(type_id), int(root), int(slot)), returning="uniq")
            self.db.execute("INSERT INTO trophies (%s) VALUES (%s)"
                            % (", ".join(cols), ", ".join("?" * len(cols))),
                            [int(uniq)] + [rec[c] for c in TROPHY_FIELDS])
        return self.item(uniq)

    def trophies_of(self, owner):
        """The collection: every registered trophy of a character, oldest
        first."""
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM trophies WHERE owner = ? AND registered_at IS NOT NULL"
            " ORDER BY uniq", (int(owner),)).fetchall()]

    def trophy_like(self, owner, type_id, victim_id):
        """The registered trophy of this kind off this victim in a
        collection, which a new one of the same joins; or None."""
        row = self.db.execute(
            "SELECT * FROM trophies WHERE owner = ? AND registered_at IS NOT NULL"
            " AND type_id = ? AND victim_id = ? ORDER BY uniq LIMIT 1",
            (int(owner), int(type_id), int(victim_id))).fetchone()
        return dict(row) if row else None

    def trophy_paid_since(self, killer_id, victim_id, since):
        """Whether a registration after `since` (epoch seconds) already paid
        this killer the fighter's skill for this victim -- an entry deleted
        from the collection since included (delete_trophy keeps its row)."""
        return self.db.execute(
            "SELECT 1 AS hit FROM trophies WHERE killer_id = ? AND victim_id = ?"
            " AND paid_at IS NOT NULL AND paid_at > ? LIMIT 1",
            (int(killer_id), int(victim_id), int(since))).fetchone() is not None

    def register_trophy(self, row, rec, char_id, now, paid, purse, rep, into=None):
        """One registration, all of it or none: the trophy's items row
        leaves the bag (named as it was read: owner, place, type), its words
        go into char_id's collection -- as an entry of their own, or into
        `into` as one more kill of the same victim -- and the purse and the
        fighter's skill are written. paid marks the registration that paid
        the skill (trophy_paid_since). True when written; False when any of
        it was no longer as read, and then nothing at all was."""
        paid_at = int(now) if paid else None
        try:
            with self.db:
                gone = self.db.execute(
                    "DELETE FROM items WHERE uniq = ? AND char_id = ? AND slot = ?"
                    " AND type_id = ? AND root = ?",
                    (int(row["uniq"]), int(char_id), int(row["slot"]),
                     int(row["type_id"]), int(row["root"]))).rowcount
                if gone != 1:
                    raise _Stale(row["uniq"])
                if into is None:
                    hit = self.db.execute(
                        "UPDATE trophies SET owner = ?, registered_at = ?, paid_at = ?"
                        " WHERE uniq = ? AND registered_at IS NULL",
                        (int(char_id), int(now), paid_at, int(row["uniq"]))).rowcount
                else:
                    # The newer kill speaks for the entry: its levels, its
                    # names, its time ("Последнее убийство").
                    src = rec if rec["killed_at"] >= into["killed_at"] else into
                    hit = self.db.execute(
                        "UPDATE trophies SET kills = ?, killed_at = ?, killer_name = ?,"
                        " killer_lvl = ?, victim_name = ?, victim_lvl = ?,"
                        " victim_clan = ?, paid_at = ? WHERE uniq = ? AND owner = ?"
                        " AND kills = ? AND registered_at IS NOT NULL",
                        (int(into["kills"]) + int(rec["kills"]), int(src["killed_at"]),
                         src["killer_name"], int(src["killer_lvl"]), src["victim_name"],
                         int(src["victim_lvl"]), src["victim_clan"],
                         paid_at if paid else into["paid_at"], int(into["uniq"]),
                         int(char_id), int(into["kills"]))).rowcount
                    if hit == 1:
                        hit = self.db.execute(
                            "DELETE FROM trophies WHERE uniq = ? AND registered_at IS NULL",
                            (int(row["uniq"]),)).rowcount
                if hit != 1:
                    # Inside the transaction: the item comes back with it.
                    raise _Stale(row["uniq"])
                _char, afro, gold = purse
                self._book(char_id, afro, gold, "trophy", row["uniq"])
                self.db.execute("UPDATE characters SET afro = ?, gold = ?, rep = ?"
                                " WHERE id = ?", (int(afro), int(gold), int(rep), int(char_id)))
        except _Stale:
            return False
        return True

    def delete_trophy(self, uniq, owner):
        """Out of a collection for good ("Удалить трофей"); True if it was
        there. The row stays behind, nobody's (owner 0) but registered: its
        paid_at is what trophy_paid_since reads, and a delete must not give
        the pair its hour back -- register, delete, register would pay the
        fighter's skill every time. The collection (trophies_of,
        trophy_like) and trophies.registered_row read an owner's rows only;
        clear_ground, sweep_ground, forget_trophy and rekey_trophy
        unregistered ones."""
        if not int(owner):
            return False
        # Off the show too: what is out of the collection is nobody's to show.
        n = self.db.execute("UPDATE trophies SET owner = 0, shown = NULL"
                            " WHERE uniq = ? AND owner = ? AND registered_at IS NOT NULL",
                            (int(uniq), int(owner))).rowcount
        self.db.commit()
        return n == 1

    def shown_trophies(self, owner):
        """A character's show (trophies.show_of): {place: entry} of the
        registered trophies of his collection that stand on a place."""
        if not int(owner or 0):
            return {}
        return {int(r["shown"]): dict(r) for r in self.db.execute(
            "SELECT * FROM trophies WHERE owner = ? AND registered_at IS NOT NULL"
            " AND shown IS NOT NULL", (int(owner),)).fetchall()}

    def show_trophy(self, owner, place, uniq=None):
        """Put an entry of owner's collection on show at `place`, or with
        uniq None empty the place. Whatever stood there goes back to being
        only kept, and the entry leaves the place it had: one column, so an
        entry is never shown twice. One transaction; True when done, False
        when uniq is no registered entry of owner's -- and then nothing
        changed, the place not emptied either."""
        if not int(owner or 0):
            return False
        try:
            with self.db:
                self.db.execute("UPDATE trophies SET shown = NULL WHERE owner = ? AND shown = ?",
                                (int(owner), int(place)))
                if uniq is not None:
                    hit = self.db.execute(
                        "UPDATE trophies SET shown = ? WHERE uniq = ? AND owner = ?"
                        " AND registered_at IS NOT NULL",
                        (int(place), int(uniq), int(owner))).rowcount
                    if hit != 1:
                        raise _Stale(uniq)
        except _Stale:
            return False
        return True

    def buy_trophy_place(self, char_id, had, afro, gold):
        """One more place to show a trophy on and the purse that paid for
        it, in one transaction (bank_expand's rule). had is the count of
        bought places as the buyer read it: if it moved since, this is no
        purchase and nothing is written. Returns the new count, or None."""
        with self.db:
            n = self.db.execute("UPDATE characters SET trophy_places = ?"
                                " WHERE id = ? AND trophy_places = ?",
                                (int(had) + 1, int(char_id), int(had))).rowcount
            if n != 1:
                return None
            self._purse((char_id, afro, gold), "trophy")
        return int(had) + 1

    def rekey_trophy(self, old, new):
        """A trophy's words follow it to the serial a letter's parcel is
        unpacked under (mail.Mail.uldml makes every attachment a new row)."""
        self.db.execute("UPDATE trophies SET uniq = ? WHERE uniq = ?"
                        " AND registered_at IS NULL", (int(new), int(old)))
        self.db.commit()

    def forget_trophy(self, uniq):
        """The words of a trophy that is no more. A bag on the ground that
        runs out takes them with its rows (sweep_ground, the same rule)."""
        self.db.execute("DELETE FROM trophies WHERE uniq = ? AND registered_at IS NULL",
                        (int(uniq),))
        self.db.commit()

    def mail_update(self, mail_id, **cols):
        unknown = set(cols) - set(MAIL_FIELDS)
        if unknown:
            raise ValueError("no such mail field: %s" % ", ".join(sorted(unknown)))
        if not cols:
            return
        keys = list(cols)
        self.db.execute(
            "UPDATE mail SET %s WHERE id = ?"
            % ", ".join("%s = ?" % k for k in keys),
            [cols[k] for k in keys] + [mail_id])
        self.db.commit()

    def mail_delete(self, mail_id):
        self.db.execute("DELETE FROM mail WHERE id = ?", (mail_id,))
        self.db.commit()

    # --- clans (server/clans.py) ----------------------------------------------
    # The database is the only authority on who is in which clan with what
    # rights: nothing about a clan is cached in the game process, because
    # tools/admin_account.py changes clans from another process while the
    # game runs (clan_hand_over) and a cached head or member would then
    # decide in the game's name. Every change is one transaction, and every
    # write names what it was decided on -- the clan, the member in that
    # clan, the treasury holding enough -- so a row that moved in between is
    # told by the write touching nothing, and then nothing at all is
    # written (the auction's rule above). An IntegrityError is never caught
    # inside `with self.db`: Postgres has aborted the transaction by then
    # (storage.PostgresDB.execute), so it is let out and read by the caller.
    # Nothing here calls a helper that commits on its own (set_money,
    # save_character_state, mail_send): a purse goes through _purse.
    CLAN_MAX_ID = 16777214        # 0 and 16777215 mean "no clan" on the wire

    def clan(self, clan_id):
        row = self.db.execute("SELECT * FROM clans WHERE id = ?",
                              (int(clan_id),)).fetchone()
        return dict(row) if row else None

    def clan_by_key(self, key):
        row = self.db.execute("SELECT * FROM clans WHERE name_key = ?",
                              (key,)).fetchone()
        return dict(row) if row else None

    def clan_all(self):
        """Every clan, oldest first."""
        return [dict(r) for r in self.db.execute("SELECT * FROM clans ORDER BY id")]

    def clan_members_all(self):
        """{char_id: (clan_id, perm)} of every member of every clan: one read
        for a push that goes to the members of all clans (clans.py)."""
        return {int(r["char_id"]): (int(r["clan_id"]), int(r["perm"]))
                for r in self.db.execute("SELECT char_id, clan_id, perm FROM clan_members")}

    def clan_member(self, char_id):
        """A character's membership with its clan's name and head, or None.
        A row whose clan is gone is no membership (the JOIN leaves it out)."""
        row = self.db.execute(
            "SELECT m.char_id, m.clan_id, m.perm, m.post, m.joined_at, m.invited_by,"
            " k.name AS clan_name, k.head AS head FROM clan_members m"
            " JOIN clans k ON k.id = m.clan_id WHERE m.char_id = ?",
            (int(char_id),)).fetchone()
        return dict(row) if row else None

    def clan_member_perms(self, clan_id):
        """[(char_id, perm)] of a clan's members."""
        return [(int(r["char_id"]), int(r["perm"])) for r in self.db.execute(
            "SELECT char_id, perm FROM clan_members WHERE clan_id = ?"
            " ORDER BY joined_at, char_id", (int(clan_id),))]

    def clan_roster(self, clan_id):
        """The member list as gg_list;res=1 carries it: each member's id,
        name, post, rights and when he was last seen, in order of joining."""
        return [dict(r) for r in self.db.execute(
            "SELECT m.char_id, m.perm, m.post, m.joined_at, c.name, c.seen_at"
            " FROM clan_members m JOIN characters c ON c.id = m.char_id"
            " WHERE m.clan_id = ? ORDER BY m.joined_at, m.char_id", (int(clan_id),))]

    def clan_create(self, char_id, name, key, descr, purse, when=None):
        """Found a clan: its row, its head (perm 65535) and the fee out of
        his purse -- purse is the whole new (char_id, afro, gold), booked
        'clan_create' -- in one transaction. The founder's invitation ban
        goes too (clans.py: leaving never has to put it back). Returns the
        new id, or None when the name's key is taken (a race: the caller
        looked first) or the founder turned out to be a member already."""
        when = int(when or time.time())
        try:
            with self.db:
                # A membership whose clan is gone is nobody's: it must not
                # stand in the way (the PRIMARY KEY) of a new one.
                self.db.execute("DELETE FROM clan_members WHERE char_id = ? AND clan_id"
                                " NOT IN (SELECT id FROM clans)", (int(char_id),))
                clan_id = self.db.insert(
                    "INSERT INTO clans (name, name_key, descr, head, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (name, key, descr or "", int(char_id), when), returning="id")
                if not 0 < int(clan_id) <= self.CLAN_MAX_ID:
                    # Raised inside the transaction: nothing is founded.
                    raise ValueError("clan id %s is past what the wire can say" % clan_id)
                self.db.execute(
                    "INSERT INTO clan_members (char_id, clan_id, perm, post, joined_at,"
                    " invited_by) VALUES (?, ?, ?, '', ?, 0)",
                    (int(char_id), int(clan_id), CLAN_HEAD_PERM, when))
                self.db.execute("UPDATE characters SET clan_no_invites = 0 WHERE id = ?",
                                (int(char_id),))
                self._purse(purse, "clan_create", clan_id)
        except storage.IntegrityError:
            return None
        return int(clan_id)

    def clan_member_add(self, char_id, clan_id, perm, post, invited_by=0, when=None):
        """A character joins: True when written; False when the clan is gone
        (disbanded while the invitation waited). Already in a clan is an
        IntegrityError for the caller, as the one row a character may have."""
        with self.db:
            self.db.execute("DELETE FROM clan_members WHERE char_id = ? AND clan_id"
                            " NOT IN (SELECT id FROM clans)", (int(char_id),))
            hit = self.db.execute(
                "INSERT INTO clan_members (char_id, clan_id, perm, post, joined_at,"
                " invited_by) SELECT ?, ?, ?, ?, ?, ? WHERE EXISTS"
                " (SELECT 1 FROM clans WHERE id = ?)",
                (int(char_id), int(clan_id), int(perm), post or "",
                 int(when or time.time()), int(invited_by or 0), int(clan_id))).rowcount
            if hit != 1:
                return False
            self.db.execute("UPDATE characters SET clan_no_invites = 0 WHERE id = ?",
                            (int(char_id),))
        return True

    def clan_member_update(self, char_id, clan_id, perm=None, post=None):
        """New rights and/or post of a member of that clan; False when he is
        no longer in it."""
        sets, args = [], []
        if perm is not None:
            sets.append("perm = ?")
            args.append(int(perm))
        if post is not None:
            sets.append("post = ?")
            args.append(post)
        if not sets:
            return self.clan_member(char_id) is not None
        with self.db:
            hit = self.db.execute("UPDATE clan_members SET %s WHERE char_id = ? AND clan_id = ?"
                                  % ", ".join(sets), args + [int(char_id), int(clan_id)]).rowcount
        return hit == 1

    def clan_member_remove(self, char_id, clan_id):
        """Out of that clan (a kick); False when he was not in it any more.
        Not for the head: he leaves by clan_leave, which hands the clan on."""
        with self.db:
            hit = self.db.execute("DELETE FROM clan_members WHERE char_id = ? AND clan_id = ?"
                                  " AND char_id <> (SELECT head FROM clans WHERE id = ?)",
                                  (int(char_id), int(clan_id), int(clan_id))).rowcount
        return hit == 1

    def clan_leave(self, char_id, clan_id, purse=None, when=None):
        """A member leaves by his own choice, in one transaction: a head
        hands the clan to clan_successor first, and a head alone disbands it,
        its treasury paid into his purse -- purse is the (char_id, afro,
        gold) the caller holds for him (the live Character's, so that its
        save at logout does not write the payout away), None to take the
        row's. Returns {"new_head": id or None, "disbanded": bool, "paid":
        afro}, or None when he was not in that clan any more."""
        when = int(when or time.time())
        with self.db:
            row = self.db.execute("SELECT k.head FROM clan_members m JOIN clans k"
                                  " ON k.id = m.clan_id WHERE m.char_id = ? AND m.clan_id = ?",
                                  (int(char_id), int(clan_id))).fetchone()
            if row is None:
                return None
            out = {"new_head": None, "disbanded": False, "paid": 0}
            if int(row["head"]) == int(char_id):
                new = clan_successor(self.db, clan_id, char_id)
                if new is None:
                    out["disbanded"] = True
                    out["paid"] = self._clan_pay_out(clan_id, char_id, purse, when) or 0
                    return out
                self.db.execute("UPDATE clans SET head = ? WHERE id = ?", (new, int(clan_id)))
                self.db.execute("UPDATE clan_members SET perm = ? WHERE char_id = ?"
                                " AND clan_id = ?", (CLAN_HEAD_PERM, new, int(clan_id)))
                out["new_head"] = new
            self.db.execute("DELETE FROM clan_members WHERE char_id = ? AND clan_id = ?",
                            (int(char_id), int(clan_id)))
        return out

    def _clan_pay_out(self, clan_id, payout_char, purse, when):
        """Inside the caller's transaction: the clan goes (clan_drop) and its
        treasury into payout_char's purse, booked 'clan_disband' -- onto
        purse's (afro, gold) when given, else onto the row's. Returns what
        was paid; None when the clan was gone already."""
        gone = clan_drop(self.db, clan_id, payout_char or 0, when)
        if gone is None:
            return None
        afro = gone[1]
        if afro and payout_char:
            if purse is None:
                have = self.db.execute("SELECT afro, gold FROM characters WHERE id = ?",
                                       (int(payout_char),)).fetchone()
                purse = (payout_char, have["afro"], have["gold"]) if have else None
            if purse is not None:
                self._purse((int(payout_char), int(purse[1]) + afro, int(purse[2])),
                            "clan_disband", clan_id)
        return afro

    def clan_disband(self, clan_id, payout_char=None, purse=None, when=None):
        """Disband a clan outright (the admin's, clan_admin.py): members,
        relations both ways and the row go, the treasury into payout_char's
        purse as clan_leave pays it. Returns the afro paid, or None when the
        clan was gone already."""
        with self.db:
            return self._clan_pay_out(clan_id, payout_char, purse,
                                      int(when or time.time()))

    def clan_set_head(self, clan_id, new, old_perm=0x2F67):
        """Hand the clan to another of its members (admin): he gets 65535,
        the old head old_perm (everything but the head's bit, by default).
        False when new is not a member of that clan."""
        with self.db:
            old = self.db.execute("SELECT head FROM clans WHERE id = ?",
                                  (int(clan_id),)).fetchone()
            if old is None:
                return False
            hit = self.db.execute("UPDATE clan_members SET perm = ? WHERE char_id = ?"
                                  " AND clan_id = ?", (CLAN_HEAD_PERM, int(new), int(clan_id))).rowcount
            if hit != 1:
                return False
            if int(old["head"]) != int(new):
                self.db.execute("UPDATE clan_members SET perm = ? WHERE char_id = ?"
                                " AND clan_id = ?", (int(old_perm) & ~CLAN_HEAD & 0xFFFF,
                                                     int(old["head"]), int(clan_id)))
            self.db.execute("UPDATE clans SET head = ? WHERE id = ?", (int(new), int(clan_id)))
        return True

    def clan_rename(self, clan_id, name, key):
        """A new name (admin). False when the clan is gone; an IntegrityError
        when the key is taken."""
        with self.db:
            hit = self.db.execute("UPDATE clans SET name = ?, name_key = ? WHERE id = ?",
                                  (name, key, int(clan_id))).rowcount
        return hit == 1

    def clan_treasury(self, clan_id):
        row = self.db.execute("SELECT afro FROM clans WHERE id = ?",
                              (int(clan_id),)).fetchone()
        return int(row["afro"]) if row else None

    def clan_treasury_move(self, clan_id, char_id, delta, purse, when=None):
        """Afro between a member's purse and his clan's treasury, in one
        transaction: delta > 0 puts it in, < 0 takes it out. purse is the
        member's whole new (char_id, afro, gold), booked 'clan' (ref: the
        clan). The treasury is written first, by an UPDATE that names the
        member still in the clan and, for a withdrawal, the treasury still
        holding enough; when it touches no row nothing is written. Returns
        the new balance, or None."""
        delta = int(delta)
        if not delta:
            return None
        cond = "" if delta > 0 else " AND afro >= ?"
        args = [delta, int(clan_id), int(char_id), int(clan_id)] + ([-delta] if delta < 0 else [])
        with self.db:
            hit = self.db.execute(
                "UPDATE clans SET afro = afro + ? WHERE id = ? AND EXISTS (SELECT 1 FROM"
                " clan_members WHERE char_id = ? AND clan_id = ?)" + cond, args).rowcount
            if hit != 1:
                return None
            self._purse(purse, "clan", clan_id)
            clan_book(self.db, clan_id, "deposit" if delta > 0 else "withdraw", delta,
                      char_id, 0, when)
            return self.clan_treasury(clan_id)

    def clan_treasury_adjust(self, clan_id, delta, source, ref=0, char_id=0, when=None):
        """The treasury alone, up or down (a stance paid for, the admin's
        adjustment): a debit only while it holds enough. Returns the new
        balance, or None when the clan is gone or short."""
        delta = int(delta)
        cond = " AND afro >= ?" if delta < 0 else ""
        with self.db:
            hit = self.db.execute("UPDATE clans SET afro = afro + ? WHERE id = ?" + cond,
                                  [delta, int(clan_id)] + ([-delta] if delta < 0 else [])).rowcount
            if hit != 1:
                return None
            clan_book(self.db, clan_id, source, delta, char_id, ref, when)
            return self.clan_treasury(clan_id)

    def clan_spend(self, clan_id, afro, source, ref=0, char_id=0, when=None):
        """Pay afro out of the treasury (clan_treasury_adjust); True if it
        held enough."""
        return self.clan_treasury_adjust(clan_id, -abs(int(afro)), source, ref,
                                         char_id, when) is not None

    def clan_relation(self, clan_id, other):
        """clan_id's stance toward other: -1, 0 or 1."""
        row = self.db.execute("SELECT stat FROM clan_relations WHERE clan_id = ? AND other = ?",
                              (int(clan_id), int(other))).fetchone()
        return int(row["stat"]) if row else 0

    def clan_relations_of(self, clan_id):
        """{other: stat} of every stance clan_id has set."""
        return {int(r["other"]): int(r["stat"]) for r in self.db.execute(
            "SELECT other, stat FROM clan_relations WHERE clan_id = ?", (int(clan_id),))}

    def clan_relation_set(self, clan_id, other, stat, when=None):
        self.db.replace("clan_relations", ("clan_id", "other", "stat", "changed_at"),
                        [(int(clan_id), int(other), int(stat), int(when or time.time()))],
                        conflict=("clan_id", "other"))
        self.db.commit()

    def clan_stance_step(self, clan_id, other, old, new, afro, char_id, need=0, when=None,
                         order=None):
        """clan_id's stance toward other moved from old to new and paid for
        out of its treasury (clan_diplomacy.py), in one transaction: a price
        taken with no stance to show for it, or a stance got for nothing,
        is what two commits would leave behind a crash between them. The
        treasury is written first, by an UPDATE that names all the step was
        decided on -- the treasury holding afro, the other clan still there,
        the stance still old (no row is 0), char_id still in the clan and
        holding every bit of need -- then the stance and the journal's
        'diplomacy' row, a sink (ref: the other clan). Returns the new
        balance, or None when that UPDATE touched nothing, and then nothing
        at all is written.

        order is (id, words) when the step was ordered on the site
        (site_orders.py): the order is marked done, code OK and the words
        for the site to show, in the same transaction, and only if it was
        still waiting -- else the step is rolled back and None returned. So
        a step and its order's "done" are written together or not at all,
        and an order is carried out once, whatever stops the game when."""
        when = int(when or time.time())
        afro = abs(int(afro))
        try:
            with self.db:
                hit = self.db.execute(
                    "UPDATE clans SET afro = afro - ? WHERE id = ? AND afro >= ?"
                    " AND EXISTS (SELECT 1 FROM clans WHERE id = ?)"
                    " AND COALESCE((SELECT stat FROM clan_relations WHERE clan_id = ?"
                    " AND other = ?), 0) = ?"
                    " AND EXISTS (SELECT 1 FROM clan_members WHERE char_id = ?"
                    " AND clan_id = ? AND (perm & ?) = ?)",
                    (afro, int(clan_id), afro, int(other), int(clan_id), int(other), int(old),
                     int(char_id), int(clan_id), int(need), int(need))).rowcount
                if hit != 1:
                    return None
                self.db.replace("clan_relations", ("clan_id", "other", "stat", "changed_at"),
                                [(int(clan_id), int(other), int(new), when)],
                                conflict=("clan_id", "other"))
                clan_book(self.db, clan_id, "diplomacy", -afro, char_id, other, when)
                if order is not None:
                    order_id, words = order
                    done = self.db.execute(
                        "UPDATE site_orders SET done_at = ?, code = 'OK', result = ?"
                        " WHERE id = ? AND done_at IS NULL",
                        (float(when), str(words), int(order_id))).rowcount
                    if done != 1:
                        # Raised inside the transaction: the price, the
                        # stance and the journal's row go back with it.
                        raise _Answered(order_id)
                return self.clan_treasury(clan_id)
        except _Answered:
            return None

    def clan_ledger_rows(self, clan_id, limit=50):
        """A treasury's journal, newest first."""
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM clan_ledger WHERE clan_id = ? ORDER BY id DESC LIMIT ?",
            (int(clan_id), int(limit)))]

    def clan_hand_over(self, char_id, when=None):
        """clan_hand_over as its own transaction, the membership row going
        with it: what the admin tool does to a deleted character, for a
        caller holding a Store."""
        with self.db:
            out = clan_hand_over(self.db, char_id, when)
            self.db.execute("DELETE FROM clan_members WHERE char_id = ?", (int(char_id),))
        return out

    def close(self):
        self.db.close()
