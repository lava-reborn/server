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
"""


def credential(login, password):
    """The digest the client will send: md5 of cp1251(password + login)."""
    return hashlib.md5((password + login).encode("cp1251", "replace")).hexdigest()


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
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

    def close(self):
        self.db.close()
