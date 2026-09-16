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
"""

# Columns added after the table was first shipped. CREATE IF NOT EXISTS does
# nothing to an existing table, so these are applied one by one on start, and
# each ALTER carries a default so the rows already there get one.
#   afro, gold  the purse; gold in hundredths of an ounce, the unit the
#               client divides by 100 to show (QuestInterface.as:342)
#   home_loc    where the character respawns, set by on_conv;op=0
CHARACTER_COLUMNS = [
    ("afro", "INTEGER NOT NULL DEFAULT 1000"),
    ("gold", "INTEGER NOT NULL DEFAULT 0"),
    ("home_loc", "INTEGER"),
]


def credential(login, password):
    """The digest the client will send: md5 of cp1251(password + login)."""
    return hashlib.md5((password + login).encode("cp1251", "replace")).hexdigest()


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    have = {r["name"] for r in db.execute("PRAGMA table_info(characters)")}
    for column, decl in CHARACTER_COLUMNS:
        if column not in have:
            db.execute("ALTER TABLE characters ADD COLUMN %s %s" % (column, decl))
    db.commit()
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
        self.db.commit()
        return cur.lastrowid, slot

    def name_taken(self, name):
        return self.db.execute("SELECT 1 FROM characters WHERE name = ?",
                               (name,)).fetchone() is not None

    def save_position(self, char_id, loc, pos, gx, gy, on_map):
        self.db.execute(
            "UPDATE characters SET loc = ?, pos = ?, gx = ?, gy = ?, on_map = ?"
            " WHERE id = ?", (loc, pos, gx, gy, 1 if on_map else 0, char_id))
        self.db.commit()

    # --- purse and home --------------------------------------------------
    def money(self, char_id):
        """(afro, gold) as stored."""
        row = self.db.execute("SELECT afro, gold FROM characters WHERE id = ?",
                              (char_id,)).fetchone()
        return (row["afro"], row["gold"]) if row else (0, 0)

    def add_money(self, char_id, afro=0, gold=0):
        """Credit (or, negative, debit) the purse; returns the new (afro, gold)."""
        self.db.execute(
            "UPDATE characters SET afro = afro + ?, gold = gold + ? WHERE id = ?",
            (int(afro), int(gold), char_id))
        self.db.commit()
        return self.money(char_id)

    def set_home(self, char_id, loc):
        self.db.execute("UPDATE characters SET home_loc = ? WHERE id = ?",
                        (loc, char_id))
        self.db.commit()

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

    def close(self):
        self.db.close()
