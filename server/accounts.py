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
"""

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
]


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

    def save_position(self, char_id, loc, pos, gx, gy, on_map):
        self.db.execute(
            "UPDATE characters SET loc = ?, pos = ?, gx = ?, gy = ?, on_map = ?"
            " WHERE id = ?", (loc, pos, gx, gy, 1 if on_map else 0, char_id))
        self.db.commit()

    def close(self):
        self.db.close()
