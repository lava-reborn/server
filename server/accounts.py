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
import hashlib
import json
import os
import sqlite3
import time

import progression

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
"""

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
]

ITEM_FIELDS = ("slot", "count", "brk", "max_break_cur", "ammo_count",
               "ammo_type", "cur_mode", "use_count")


def credential(login, password):
    """The digest the client will send: md5 of cp1251(password + login)."""
    return hashlib.md5((password + login).encode("cp1251", "replace")).hexdigest()


def migrate(db):
    """Bring a database made by an older server up to the current schema.

    Characters that predate char_stats get the newborn's numbers, money
    included: they had none stored, and the server they were made under
    showed everyone the same fixed figures anyway.
    """
    have = {r["name"] for r in db.execute("PRAGMA table_info(characters)")}
    for col, decl in CHARACTER_COLUMNS:
        if col not in have:
            db.execute("ALTER TABLE characters ADD COLUMN %s %s" % (col, decl))
    orphans = db.execute(
        "SELECT id FROM characters WHERE id NOT IN"
        " (SELECT DISTINCT char_id FROM char_stats)").fetchall()
    for row in orphans:
        seed_stats(db, row["id"])
    db.commit()


def seed_stats(db, char_id):
    db.executemany(
        "INSERT OR REPLACE INTO char_stats (char_id, kind, idx, value, xp, xp_max)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [(char_id,) + r for r in progression.starting_rows()])
    db.execute("UPDATE characters SET afro = ?, gold = 0, max_specs = 1,"
               " level = 0, hp = NULL, sp = NULL WHERE id = ?",
               (progression.START_AFRO, char_id))


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    migrate(db)
    return db


class Store:
    def __init__(self, path=None):
        global DB_PATH
        if path:
            DB_PATH = path
        self.db = connect()

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
            cur = self.db.execute(
                "INSERT INTO accounts (login, hash, created) VALUES (?, ?, ?)",
                (login, cred, int(time.time())))
            self.db.commit()
            return cur.lastrowid, None
        except sqlite3.IntegrityError:
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

    # --- characters ------------------------------------------------------
    def characters(self, account_id):
        return self.db.execute(
            "SELECT * FROM characters WHERE account_id = ? ORDER BY slot",
            (account_id,)).fetchall()

    def create_character(self, account_id, name, sex, res):
        used = [r["slot"] for r in self.characters(account_id)]
        slot = next(i for i in range(100) if i not in used)
        cur = self.db.execute(
            "INSERT INTO characters (account_id, slot, name, sex, res)"
            " VALUES (?, ?, ?, ?, ?)", (account_id, slot, name, sex, str(res)))
        # The client never sends a stat: everything a newborn has is decided
        # here (wiki: "задаётся в GSDL, экземпляр Player_Trait").
        seed_stats(self.db, cur.lastrowid)
        self.db.commit()
        return cur.lastrowid, slot

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
        self.db.executemany(
            "INSERT OR REPLACE INTO char_stats (char_id, kind, idx, value, xp, xp_max)"
            " VALUES (?, ?, ?, ?, ?, ?)", [(char_id,) + tuple(r) for r in rows])
        self.db.commit()

    def save_character_state(self, char_id, **cols):
        """Money, vitals, premium, reputation, counters: any of the columns
        in CHARACTER_COLUMNS, by name."""
        allowed = {c for c, _d in CHARACTER_COLUMNS}
        cols = {k: v for k, v in cols.items() if k in allowed}
        if not cols:
            return
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
        self.db.execute("UPDATE characters SET afro = ?, gold = ? WHERE id = ?",
                        (int(afro), int(gold), char_id))
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
        cur = self.db.execute(
            "INSERT INTO items (%s) VALUES (%s)"
            % (", ".join(cols), ", ".join("?" * len(cols))), vals)
        self.db.commit()
        return self.item(cur.lastrowid)

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

    def add_money(self, char_id, afro=0, gold=0):
        """Credit (or, negative, debit) the purse; returns the new (afro, gold)."""
        self.db.execute(
            "UPDATE characters SET afro = afro + ?, gold = gold + ? WHERE id = ?",
            (int(afro), int(gold), char_id))
        self.db.commit()
        return self.money(char_id)

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
        cur = self.db.execute(
            "INSERT INTO char_quests (char_id, type, progress_json, complete,"
            " taken_at) VALUES (?, ?, ?, ?, ?)",
            (char_id, quest_type, json.dumps(progress), 1 if complete else 0,
             int(time.time())))
        self.db.commit()
        return cur.lastrowid

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

    def quests_done_since(self, char_id, since):
        return self.db.execute(
            "SELECT COUNT(*) c FROM char_quests_done WHERE char_id = ?"
            " AND done_at >= ?", (char_id, int(since))).fetchone()["c"]

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

    def mail_send(self, to_char, from_char, kind, subject, body, afro, gold,
                  items_json, when=None):
        """File a letter; returns its row."""
        cur = self.db.execute(
            "INSERT INTO mail (to_char, from_char, type, subject, body,"
            " sent_at, afro, gold, items_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (to_char, from_char, int(kind), subject, body,
             int(when or time.time()), int(afro), int(gold), items_json))
        self.db.commit()
        return self.mail_letter(cur.lastrowid)

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

    def close(self):
        self.db.close()
