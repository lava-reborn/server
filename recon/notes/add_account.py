import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

old = '''    def cmd_login(self, p):
        self.hash = p.get("hash")
        # res=0 -> success; client then calls persGen.loadDescription()
        self.logged_in = True
        self.send("cmdAck", res=0)
'''
new = '''    def cmd_login(self, p):
        self.hash = p.get("hash")
        # res=0 -> success; client then calls persGen.loadDescription(),
        # which is an HTTP fetch of avatars/list.xml, not a socket command.
        self.logged_in = True
        self.send("cmdAck", res=0)
        self.send_account()

    def send_account(self):
        """Push the account state the client waits for but never asks for.

        PersGenerator.checkFullInfo only opens the character screen once the
        avatar list has loaded AND accountInfo has arrived. Note that
        accountInfo is ignored entirely unless can_create is truthy
        (PersGenerator.accountInfo), so a zero there leaves the client idle
        with no error of any kind.
        """
        self.send("constants",
                  gold_to_afro_rate=100,
                  quest_log_capacity=20,
                  leave_combat_timeout=30,
                  premium_weight_bonus_1=2, premium_weight_bonus_2=4,
                  premium_break_bonus_1=1, premium_break_bonus_2=2,
                  premium_xp_bonus_1=1, premium_xp_bonus_2=2,
                  gold_repair_price_mod=1, gold_repair_mod=10000,
                  daily_max=10, daily_reset_time=0)
        for i, pers in enumerate(self.characters):
            self.send("persInfo", num=i, name=Str(pers["name"]),
                      sex=pers["sex"], death=0, res=pers["res"])
        self.send("accountInfo",
                  nPers=len(self.characters),
                  can_create=1)
'''
assert old in s
s = s.replace(old, new)

# characters live on the session for now; persistence comes later
s = s.replace('''        self.hash = None
        self.logged_in = False''',
              '''        self.hash = None
        self.logged_in = False
        # No storage yet: every login starts with an empty roster, so the
        # client goes straight to character creation.
        self.characters = []''')
io.open(p, "w", encoding="utf-8").write(s)
print("server.py patched")
