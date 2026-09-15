import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

# 1. every in-location move expects an acknowledgement
old = '''        path = p.get("path")
        if not path:
            return
        self.pos = int(path[-1])
        self.send("userMove", id=0, path=[int(c) for c in path])'''
new = '''        path = p.get("path")
        if not path:
            return
        # Location.movePlayer registers a cmdAck handler for every single step
        # it asks for. Leaving those unanswered does not stall movement, since
        # that handler is empty, but the queue is strictly ordered: each later
        # reply is then handed to a stale mover instead of the command that
        # earned it, and things like opening a shop quietly stop working.
        self.send("cmdAck", res=0)
        self.pos = int(path[-1])
        self.send("userMove", id=0, path=[int(c) for c in path])'''
assert old in s
s = s.replace(old, new)

# 2. mail check, which the client sends the moment it enters a location
s = s.replace('''    def cmd_q_status(self, p):''',
'''    def cmd_chkml(self, p):
        """Mail. The client asks the moment it lands in a location.

        mode 0 is the inbox, 1 the outbox, 255 the tariffs. All three expect an
        acknowledgement first, then the listing itself.
        """
        mode = int(p.get("mode", 0))
        self.send("cmdAck", res=0)
        if mode == 255:
            # Eight prices and eight delivery times, in the order the client
            # reads them: ordinary, express, clan, express clan, then the same
            # four again as the charge per kilogram of attachments.
            self.send("svml", data=[10, 100, 20, 200, 5, 50, 15, 150],
                      time=[3600, 600, 3600, 600, 3600, 600, 3600, 600])
        else:
            self.send("lsml", id=[], date=[], name=[], flag=[], subj=[])

    def cmd_q_status(self, p):''')

# 3. a net for the rest: refuse rather than stay silent
s = s.replace('''        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
            return''',
'''        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
            # Commands that register a handler must be answered even when the
            # feature does not exist yet. A refusal keeps the queue in step; a
            # silence shifts every later reply onto the wrong handler.
            if cmd in EXPECTS_ACK:
                self.send("cmdAck", res=3)
            return''')

s = s.replace('STORE = accounts.Store()',
'''STORE = accounts.Store()

# Commands whose sender registers a cmdAck handler, gathered from the client:
# mail, clans, party, auction, battlegrounds, item sessions, quests, map marks
# and chat all do. Anything here has to be answered, implemented or not.
EXPECTS_ACK = {
    "chkml", "getml", "sndml", "rmvml", "uldml",
    "p_op", "admit", "apply", "head", "gg_info", "c_ga",
    "ah_create", "ah_op", "ah_search", "bg_op",
    "ss_move", "ss_use", "ss_heap_c", "ss_create", "ss_upd",
    "on_conv", "q_st", "q_co", "q_ca",
    "insMark", "updMark", "rmMark",
    "userMsg", "resurrect", "actPlayer", "newPers", "lenter", "chWorld",
}''')
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
