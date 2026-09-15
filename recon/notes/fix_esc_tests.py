import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_protocol.py"
lines = io.open(p, encoding="utf-8").read().split("\n")
# drop the broken escaping block, then re-add it built without nested quoting
start = next(i for i, l in enumerate(lines) if l.startswith("# --- escaping, verbatim"))
end = next(i for i, l in enumerate(lines) if l.startswith("print()"))
Q = chr(34)      # "
A = chr(39)      # '
mixed = "a<b>&" + Q + "@%" + A + "c"
block = [
    "# --- escaping, verbatim from lol/server/XMLString.as ---",
    "check(" + Q + "esc lt" + Q + ", escape(" + Q + "<" + Q + "), " + Q + "%3C" + Q + ")",
    "check(" + Q + "esc gt" + Q + ", escape(" + Q + ">" + Q + "), " + Q + "%3E" + Q + ")",
    "check(" + Q + "esc apos" + Q + ", escape(chr(39)), " + Q + "%27" + Q + ")",
    "check(" + Q + "esc quote" + Q + ", escape(chr(34)), " + Q + "%5C" + Q + ")  # client oddity, not %22",
    "check(" + Q + "esc amp" + Q + ", escape(" + Q + "&" + Q + "), " + Q + "%26" + Q + ")",
    "check(" + Q + "esc at" + Q + ", escape(" + Q + "@" + Q + "), " + Q + "%40" + Q + ")",
    "check(" + Q + "esc percent" + Q + ", escape(" + Q + "%" + Q + "), " + Q + "%25" + Q + ")",
    "check(" + Q + "esc plain" + Q + ", escape(" + Q + "Vasya" + Q + "), " + Q + "Vasya" + Q + ")",
    "check(" + Q + "unesc quote" + Q + ", unescape(" + Q + "%5C" + Q + "), chr(34))",
    "MIXED = " + repr(mixed),
    "check(" + Q + "unesc roundtrip" + Q + ", unescape(escape(MIXED)), MIXED)",
    "check(" + Q + "escaped percent not re-decoded" + Q + ", unescape(escape(" + Q + "%3C" + Q + ")), " + Q + "%3C" + Q + ")",
    "",
    "# an @ inside a nickname must not terminate the @string@ value early",
    "NICK = " + Q + "va@sya" + Q,
    "F_AT = encode(" + Q + "userMsg" + Q + ", to=Str(NICK))",
    "check(" + Q + "at escaped on wire" + Q + ", F_AT, " + Q + "userMsg;to=@va%40sya@;" + Q + ")",
    "check(" + Q + "at survives roundtrip" + Q + ", decode(F_AT), (" + Q + "userMsg" + Q + ", {" + Q + "to" + Q + ": NICK}))",
    "",
]
io.open(p, "w", encoding="utf-8").write("\n".join(lines[:start] + block + lines[end:]))
print("tests rebuilt")
