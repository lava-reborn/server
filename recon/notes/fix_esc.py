import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/protocol.py"
s = io.open(p, encoding="utf-8").read()
old_start = s.index("# --- escaping (lol.server.XMLString) ---")
old_end = s.index("# --- encoding ---")
new = '''# --- escaping (lol.server.XMLString) -------------------------------------
# Verbatim from the client's escape table. Note the oddity: a double quote
# maps to %5C, the percent-encoding of a BACKSLASH, not %22. Reproducing the
# quirk is mandatory, since the client decodes %5C back into a double quote.
# "@" must be escaped or it would terminate an @string@ value early.
ESCAPES = [
    ("%", "%25"),   # first on encode, last on decode
    ("<", "%3C"),
    (">", "%3E"),
    ("'", "%27"),
    ('"', "%5C"),
    ("&", "%26"),
    ("@", "%40"),
]
_ESC_MAP = dict(ESCAPES)
_UNESC_MAP = {v: k for k, v in ESCAPES}


def escape(s):
    """Per-character escape, matching XMLString.escape()."""
    return "".join(_ESC_MAP.get(ch, ch) for ch in s)


def unescape(s):
    """Single left-to-right pass, so an escaped percent cannot be re-decoded."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "%" and i + 3 <= n and s[i:i + 3] in _UNESC_MAP:
            out.append(_UNESC_MAP[s[i:i + 3]])
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


'''
io.open(p, "w", encoding="utf-8").write(s[:old_start] + new + s[old_end:])
print("escaping fixed")
