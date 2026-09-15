import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_protocol.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("from protocol import decode, encode, frame, FrameReader, Str, Hex, BigUInt",
              "from protocol import (decode, encode, frame, FrameReader, Str, Hex,\n"
              "                      BigUInt, escape, unescape)")
s = s.replace("print()\nif fails:",
'''# --- escaping, verbatim from lol/server/XMLString.as ---
check("esc lt", escape("<"), "%3C")
check("esc gt", escape(">"), "%3E")
check("esc apos", escape("'"), "%27")
check("esc quote", escape('"'), "%5C")      # the client's own oddity, not %22
check("esc amp", escape("&"), "%26")
check("esc at", escape("@"), "%40")
check("esc percent", escape("%"), "%25")
check("esc plain", escape("Vasya"), "Vasya")
check("unesc quote", unescape("%5C"), '"')
check("unesc roundtrip", unescape(escape('a<b>&"@%\'c')), 'a<b>&"@%\'c')
check("escaped percent not re-decoded", unescape(escape("%3C")), "%3C")

# an "@" inside a name must not end the @string@ value early
nick = "va@sya"
f_at = encode("userMsg", to=Str(nick))
check("at escaped on wire", f_at, "userMsg;to=@va%40sya@;")
check("at survives roundtrip", decode(f_at), ("userMsg", {"to": nick}))

print()
if fails:''')
io.open(p, "w", encoding="utf-8").write(s)
print("tests added")
