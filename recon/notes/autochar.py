import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''        # No storage yet: every login starts with an empty roster, so the
        # client goes straight to character creation.
        self.characters = []''',
'''        # With a character already on the account and can_create=0, the client
        # selects slot 0 by itself and walks straight into the world, which
        # makes every test run reproducible without clicking through creation.
        # LAVA_NEWCHAR=1 starts with an empty roster and shows that screen.
        self.characters = [] if NEW_CHAR else [
            {"name": "polestvr", "sex": 0, "res": 1}]''')

s = s.replace('POLICY_PORT = 843',
              'POLICY_PORT = 843\nNEW_CHAR = os.environ.get("LAVA_NEWCHAR") == "1"')

s = s.replace('        self.send("accountInfo", nPers=len(self.characters), can_create=1)',
'''        # can_create must be falsy for the auto-select path: PersGenerator
        # opens the creation screen whenever it is truthy, regardless of how
        # many characters the account already has.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=1 if not self.characters else 0)''')

io.open(p, "w", encoding="utf-8").write(s)
import ast
ast.parse(io.open(p, encoding="utf-8").read())
print("patched, syntax ok")
