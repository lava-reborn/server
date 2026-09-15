import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("import world\nfrom protocol import",
              "import accounts\nimport world\nfrom protocol import")
s = s.replace('NEW_CHAR = os.environ.get("LAVA_NEWCHAR") == "1"',
              'STORE = accounts.Store()')

s = s.replace('''        # With a character already on the account and can_create=0, the client
        # selects slot 0 by itself and walks straight into the world, which
        # makes every test run reproducible without clicking through creation.
        # LAVA_NEWCHAR=1 starts with an empty roster and shows that screen.
        self.characters = [] if NEW_CHAR else [default_character()]''',
'''        self.account = None
        self.characters = []
        self.char_id = None''')

old_login = '''    def cmd_login(self, p):
        self.hash = p.get("hash")
        self.logged_in = True
        self.send("cmdAck", res=0)
        self.send_account()'''
new_login = '''    def cmd_login(self, p):
        """The digest the client sends is the whole credential.

        Its login screen hashes password + login and sends only that, so there
        is nothing else to check it against: the digest identifies the account
        by itself. res=1 is what the client words as a wrong login, 2 as a ban.
        """
        self.hash = p.get("hash") or ""
        row = STORE.by_credential(self.hash)
        if not row:
            log.info("  ..    unknown credential, refusing")
            self.send("cmdAck", res=1)
            return
        if row["banned"]:
            self.send("cmdAck", res=2)
            return
        self.account = row
        self.characters = [dict(r) for r in STORE.characters(row["id"])]
        self.logged_in = True
        log.info("  ..    %s logged in, %d character(s)",
                 row["login"], len(self.characters))
        self.send("cmdAck", res=0)
        self.send_account()'''
assert old_login in s
s = s.replace(old_login, new_login)

s = s.replace('''        for i, pers in enumerate(self.characters):
            self.send("persInfo", num=i, name=Str(pers["name"]),
                      sex=pers["sex"], death=0,
                      res=Str(str(pers["res"])))
        # can_create must be falsy for the auto-select path: PersGenerator
        # opens the creation screen whenever it is truthy, regardless of how
        # many characters the account already has.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=1 if not self.characters else 0)''',
'''        for pers in self.characters:
            self.send("persInfo", num=pers["slot"], name=Str(pers["name"]),
                      sex=pers["sex"], death=0, res=Str(str(pers["res"])))
        # can_create must be falsy once the account has someone, or the client
        # opens the creation screen instead of selecting: PersGenerator acts on
        # the flag alone and never looks at how many characters arrived.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=0 if self.characters else 1)''')

old_new = '''    def cmd_newPers(self, p):
        self.characters = [{"name": p.get("name", "Noname"),
                            "sex": p.get("sex", 0),
                            "res": p.get("res", AVATARS[0][0])}]
        self.active = self.characters[0]
        # The client plays its intro after this, then sends actPlayer itself.
        self.send("cmdAck", res=0)'''
new_new = '''    def cmd_newPers(self, p):
        if not self.account:
            self.send("cmdAck", res=1)
            return
        name = (p.get("name") or "").strip()
        if not name:
            self.send("cmdAck", res=5)          # invalid characters in name
            return
        if STORE.name_taken(name):
            self.send("cmdAck", res=6)          # name already in use
            return
        char_id, slot = STORE.create_character(
            self.account["id"], name, int(p.get("sex", 0)),
            p.get("res", AVATARS[0][0]))
        self.characters = [dict(r) for r in STORE.characters(self.account["id"])]
        self.char_id = char_id
        self.active = next(c for c in self.characters if c["slot"] == slot)
        log.info("  ..    created %r in slot %d", name, slot)
        # The client plays its intro after this, then sends actPlayer itself.
        self.send("cmdAck", res=0)'''
assert old_new in s
s = s.replace(old_new, new_new)

old_sel = '''        idx = int(p.get("num", 0))
        if idx < len(self.characters):
            self.active = self.characters[idx]
        self.enter_location()'''
new_sel = '''        slot = int(p.get("num", 0))
        for c in self.characters:
            if c["slot"] == slot:
                self.active = c
                self.char_id = c["id"]
                self.restore(c)
                break
        self.enter_location()

    def restore(self, c):
        """Put the character back where it was left."""
        if c["loc"] is not None and c["loc"] == LOCATION.id and c["pos"]:
            self.pos = c["pos"]
        if c["gx"] and c["gy"]:
            self.gx, self.gy = c["gx"], c["gy"]
        self.on_map = bool(c["on_map"])'''
assert old_sel in s
s = s.replace(old_sel, new_sel)

s = s.replace('''    def close(self):
        self.cancel_travel()
        self.writer.close()''',
'''    def close(self):
        self.cancel_travel()
        if self.char_id:
            STORE.save_position(self.char_id, LOCATION.id, self.pos,
                                self.gx, self.gy, self.on_map)
        self.writer.close()''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
