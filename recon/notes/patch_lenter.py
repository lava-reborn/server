import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
old = '''    def cmd_lenter(self, p):
        self.send("cmdAck", res=0)
        # aspd is the action-point gain per 600ms tick, amax the ceiling.
        self.send("lenter", pos=self.pos, aspd=1, amax=20)
        self.populate()'''
new = '''    ENTER_DELAY = float(os.environ.get("LAVA_ENTER_DELAY", "0.4"))

    def cmd_lenter(self, p):
        """Answer the client's "I have loaded, let me in".

        No cmdAck on success: Master.lenter cancels the handler it registered
        for one as soon as the lenter frame lands, so the acknowledgement is
        the failure path only.

        The frame itself is held back briefly. The client asks from inside
        locLoaded, while its own resources are still settling, and the scene
        only switches once both halves agree they are ready; replying inside
        the same instant leaves the login screen sitting on top of a world
        that has otherwise finished loading.
        """
        loop = asyncio.get_running_loop()
        loop.call_later(self.ENTER_DELAY, self.enter_ready)

    def enter_ready(self):
        # aspd is the action-point gain per 600ms tick, amax the ceiling.
        self.send("lenter", pos=self.pos, aspd=1, amax=20)
        self.populate()'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
