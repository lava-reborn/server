import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/protocol.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace(
'''def encode(*_cmd, **params):
    """Build a frame body (no NUL terminator)."""
    out = name + ";"''',
'''def encode(*_cmd, **params):
    """Build a frame body (no NUL terminator).

    The command name is positional so that a protocol parameter literally
    called "name" (e.g. ah_search) cannot collide with it.
    """
    name = _cmd[0]
    out = name + ";"''')

s = s.replace(
'''def frame(*_cmd, **params):
    """Build a complete NUL-terminated wire frame."""
    return encode(name, **params).encode(ENCODING, "replace") + TERM''',
'''def frame(*_cmd, **params):
    """Build a complete NUL-terminated wire frame."""
    return encode(_cmd[0], **params).encode(ENCODING, "replace") + TERM''')

io.open(p, "w", encoding="utf-8").write(s)
print("patched protocol.py")
