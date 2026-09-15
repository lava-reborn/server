import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_accounts.py"
s = io.open(p, encoding="utf-8").read()
old = '''# Two accounts sharing a digest would be indistinguishable to the server,
# since the digest is the only thing the client ever sends.
_id, err = store.register("other", "secret")
check("colliding digest refused", err is not None, True)'''
new = '''# The login is part of what gets hashed, which is what keeps two people who
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
      "other")'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
