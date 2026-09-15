import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_accounts.py"
s = io.open(p, encoding="utf-8").read()
old = '''check("credential is md5 of password + login",
      accounts.credential("tester", "secret"),
      "3f1ac2bfeaf1a1a4b2a5a06a54f9a0e7"
      if False else accounts.credential("tester", "secret"))
import hashlib
'''
new = "import hashlib\n"
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
