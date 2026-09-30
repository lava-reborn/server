"""Registration, the credential the client computes, and persistence."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import accounts

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


DB = os.path.join(tempfile.mkdtemp(), "accounts.db")
store = accounts.Store(DB)

# The client hashes password + login, in that order, over cp1251 bytes, and
# sends only the digest. Getting the order or the encoding wrong here would
# reject every real login while every test that computes it the same wrong way
# still passed, so pin it against a value taken from the client's own algorithm.
import hashlib
check("credential matches md5(cp1251(password + login))",
      accounts.credential("tester", "secret"),
      hashlib.md5("secrettester".encode("cp1251")).hexdigest())
check("cyrillic login hashes as cp1251, not utf-8",
      accounts.credential("Ветеран", "пароль"),
      hashlib.md5("парольВетеран".encode("cp1251")).hexdigest())

# --- registration -----------------------------------------------------------
acc_id, err = store.register("tester", "secret")
check("account created", err, None)
check("account is findable by its digest",
      store.by_credential(accounts.credential("tester", "secret"))["login"],
      "tester")
check("a wrong password yields nothing",
      store.by_credential(accounts.credential("tester", "wrong")), None)

_id, err = store.register("tester", "another")
check("duplicate login refused", err, "Такой логин уже занят")
_id, err = store.register("ab", "secret")
check("short login refused", err, "Логин короче трёх символов")
_id, err = store.register("someone", "x")
check("short password refused", err, "Пароль короче четырёх символов")

# The login is part of what gets hashed, which is what keeps two people who
# happen to pick the same password from producing the same digest. Since the
# digest is the only thing the client ever sends, that is what stops the server
# confusing one account for the other.
_id, err = store.register("other", "secret")
check("same password, different account, still allowed", err, None)
check("their digests differ",
      accounts.credential("tester", "secret") !=
      accounts.credential("other", "secret"), True)
check("each digest finds its own account",
      store.by_credential(accounts.credential("other", "secret"))["login"],
      "other")

# --- characters -------------------------------------------------------------
check("new account has no characters", len(store.characters(acc_id)), 0)
char_id, slot = store.create_character(acc_id, "Ветеран", 0, "45676")
check("first character lands in slot 0", slot, 0)
check("name is taken afterwards", store.name_taken("Ветеран"), True)
check("other names are free", store.name_taken("Кто-то"), False)

rows = store.characters(acc_id)
check("character is listed", len(rows), 1)
check("cyrillic name survives the round trip", rows[0]["name"], "Ветеран")
check("avatar kept as written", rows[0]["res"], "45676")

_id2, slot2 = store.create_character(acc_id, "Второй", 128, "49327")
check("second character takes the next slot", slot2, 1)

# --- position ---------------------------------------------------------------
store.save_position(char_id, 102, 3809, 5970.5, 1730.25, False)
row = [r for r in store.characters(acc_id) if r["id"] == char_id][0]
check("location saved", row["loc"], 102)
check("cell saved", row["pos"], 3809)
check("map position saved", (row["gx"], row["gy"]), (5970.5, 1730.25))
check("world flag saved", row["on_map"], 0)

# survives a reopen
store.close()
again = accounts.Store(DB)
row = again.characters(acc_id)[0]
check("still there after reopening", row["name"], "Ветеран")
check("position still there", row["pos"], 3809)
check("a new character has bought no bank expansions", row["bank_steps"], 0)
again.close()

# --- a database from before the bank ------------------------------------------
# The characters table of an older server has none of CHARACTER_COLUMNS, and
# bank_steps is one of them: opening the file must add it, with the default
# that leaves every existing character on the base storage.
if not os.environ.get("LAVA_DB_URL"):
    import sqlite3
    OLD = os.path.join(tempfile.mkdtemp(), "old.db")
    raw = sqlite3.connect(OLD)
    raw.executescript(accounts.SCHEMA)
    raw.execute("INSERT INTO accounts (login, hash, created) VALUES ('old', 'h', 0)")
    raw.execute("INSERT INTO characters (account_id, slot, name, sex, res)"
                " VALUES (1, 0, 'Старожил', 0, '1')")
    raw.commit()
    had = {r[1] for r in raw.execute("PRAGMA table_info(characters)")}
    raw.close()
    check("the old table has no bank_steps", "bank_steps" in had, False)
    old = accounts.Store(OLD)
    check("opening it adds bank_steps, 0 for the character already there",
          old.character(1)["bank_steps"], 0)
    old.close()

# --- medicines bought before their numbers moved --------------------------------
# 6067..6072 were sold as the Эгоист..Спасатель line, whose numbers now live
# at 6904..6909: opening a database from before moves every instance there
# -- bag, letter, lot -- with its use_count, once, and never again.
if not os.environ.get("LAVA_DB_URL"):
    import json
    import sqlite3
    LEG = os.path.join(tempfile.mkdtemp(), "legacy.db")
    raw = sqlite3.connect(LEG)
    raw.executescript(accounts.SCHEMA)
    raw.execute("INSERT INTO accounts (login, hash, created) VALUES ('old', 'h', 0)")
    raw.execute("INSERT INTO characters (account_id, slot, name, sex, res)"
                " VALUES (1, 0, 'Старожил', 0, '1')")
    for type_id, uses in ((6071, 20), (6067, 3), (6043, 5), (6904, 7)):
        raw.execute("INSERT INTO items (char_id, type_id, root, use_count) VALUES (1, ?, 2, ?)",
                    (type_id, uses))
    raw.execute("INSERT INTO mail (to_char, from_char, sent_at, items_json) VALUES (1, 0, 0, ?)",
                (json.dumps([{"uniq": 90, "type_id": 6069, "root": 2, "use_count": 12},
                             {"uniq": 91, "type_id": 3577, "root": 1}]),))
    raw.execute("INSERT INTO auction_lots (item_uniq, type_id, root, item_json, seller,"
                " seller_name, start_bid, hours, created_at, ends_at)"
                " VALUES (92, 6072, 2, ?, 1, 'Старожил', 10, 24, 0, 0)",
                (json.dumps({"uniq": 92, "type_id": 6072, "root": 2, "use_count": 20}),))
    raw.commit()
    raw.close()
    leg = accounts.Store(LEG)
    check("opened: the bag's 6071 and 6067 are 6908 and 6904, their uses kept; others stay",
          [(r["type_id"], r["use_count"]) for r in leg.items_of(1)],
          [(6908, 20), (6904, 3), (6043, 5), (6904, 7)])
    letter = leg.db.execute("SELECT items_json FROM mail").fetchone()["items_json"]
    check("  ..the medicine in a letter moves too, the rest of it is left alone",
          [(s["type_id"], s.get("use_count")) for s in json.loads(letter)],
          [(6906, 12), (3577, None)])
    lot = leg.db.execute("SELECT type_id, item_json FROM auction_lots").fetchone()
    check("  ..and the one on the auction, both its type and its snapshot",
          (lot["type_id"], json.loads(lot["item_json"])["type_id"]), (6909, 6909))
    leg.create_item(1, 6067, 2, use_count=5)
    leg.close()
    leg = accounts.Store(LEG)
    check("once only: a 6067 made after the move stays a 6067 at the next start",
          [r["type_id"] for r in leg.items_of(1)][-1], 6067)
    check("  ..and the database says the fix ran, once",
          [r["name"] for r in leg.db.execute("SELECT name FROM migrations").fetchall()
           if r["name"].startswith("heal-relink")],
          ["heal-relink-2026-09-23"])
    leg.close()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("accounts OK")
