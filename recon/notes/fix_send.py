import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()

old = '''    def send(self, name, **params):
        data = frame(name, **params)
        log.info("  S->C  %s", data[:-1].decode("cp1251", "replace"))
        self.writer.write(data)

    def handle(self, name, params):
        log.info("  C->S  %s %s", name, params)
        fn = getattr(self, "cmd_" + name, None)
        if fn:
            fn(params)
        else:
            log.warning("  ??    unimplemented command %r", name)'''

new = '''    def send(self, *_cmd, **params):
        """Send one frame. The command name is positional, because several
        commands carry a parameter literally called "name"."""
        data = frame(_cmd[0], **params)
        log.info("  S->C  %s", data[:-1].decode("cp1251", "replace"))
        self.writer.write(data)

    def handle(self, cmd, params):
        log.info("  C->S  %s %s", cmd, params)
        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
            return
        try:
            fn(params)
        except Exception:
            # A bug in one handler must not drop the player's connection.
            log.exception("  !!    handler for %r failed", cmd)'''

assert old in s, "anchor not found"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
import ast
ast.parse(io.open(p, encoding="utf-8").read())
print("patched, syntax ok")
