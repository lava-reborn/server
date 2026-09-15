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
again.close()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("accounts OK")
