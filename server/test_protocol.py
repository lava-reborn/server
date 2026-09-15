"""Codec tests derived from lol.server.SCDataParser semantics."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import (decode, encode, frame, FrameReader, Str, Hex,
                      BigUInt, Repeated, every, escape, unescape)

fails = []

def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)

# --- decoding, per SCDataParser.getData dispatch ---
check("digit", decode("cmdAck;res=0;"), ("cmdAck", {"res": 0}))
check("negative", decode("x;v=-42;"), ("x", {"v": -42}))
check("string", decode("a;name=@Vasya@;"), ("a", {"name": "Vasya"}))
check("string with ;", decode("a;t=@a;b@;"), ("a", {"t": "a;b"}))
check("two strings", decode("a;x=@p@;y=@q@;"), ("a", {"x": "p", "y": "q"}))
check("hex", decode("a;c=HFF00AA;"), ("a", {"c": 0xFF00AA}))
check("biguint", decode("a;id=x4294967296;"), ("a", {"id": "4294967296"}))
check("empty list", decode("a;l=|;"), ("a", {"l": []}))
check("digit list", decode("a;l=|1|2|3|;"), ("a", {"l": [1, 2, 3]}))
check("string list", decode("a;l=|@a@|@b@|;"), ("a", {"l": ["a", "b"]}))
check("biguint list", decode("a;l=|x10|x20|;"), ("a", {"l": ["10", "20"]}))
check("mixed", decode("lenter;id=7;name=@Zone@;pos=|3|4|;"),
      ("lenter", {"id": 7, "name": "Zone", "pos": [3, 4]}))
check("no params", decode("logout;"), ("logout", {}))

# --- encoding ---
check("enc hello", encode("hello", minor=2, major=0), "hello;minor=2;major=0;")
check("enc login", encode("login", hash=Str("abc123")), "login;hash=@abc123@;")
check("enc ack", encode("cmdAck", res=0), "cmdAck;res=0;")
check("enc hex", encode("a", c=Hex(0xFF00AA)), "a;c=HFF00AA;")
check("enc list", encode("a", l=[1, 2, 3]), "a;l=|1|2|3|;")
check("enc strlist", encode("a", l=["a", "b"]), "a;l=|@a@|@b@|;")
check("enc empty", encode("a", l=[]), "a;l=|;")

# --- round trip ---
for name, params in [
    ("lenter", {"id": 7, "name": "Zone", "pos": [3, 4]}),
    ("userMsg", {"to": "Vasya", "group": 1, "entry": "hi & bye"}),
    ("cmdAck", {"res": 0}),
]:
    enc = encode(name, **{k: (Str(v) if isinstance(v, str) else v) for k, v in params.items()})
    check("roundtrip %s" % name, decode(enc), (name, params))

# --- framing ---
fr = FrameReader()
check("framing split", fr.feed(b"hello;min"), [])
check("framing complete", fr.feed(b"or=2;\x00logout;\x00"), [b"hello;minor=2;", b"logout;"])

# --- cyrillic / cp1251 ---
f = frame("userMsg", entry=Str("Привет"))
check("utf-8 frame", f.endswith(b"\x00"), True)
check("utf-8 roundtrip", decode(f[:-1])[1]["entry"], "Привет")

# --- regression: a protocol param literally named "name" (ah_search) ---
check("param called name",
      encode("ah_search", name=Str("gun"), page=1),
      "ah_search;name=@gun@;page=1;")
check("param name roundtrip",
      decode(encode("ah_search", name=Str("gun"), page=1)),
      ("ah_search", {"name": "gun", "page": 1}))

# --- escaping, verbatim from lol/server/XMLString.as ---
check("esc lt", escape("<"), "%3C")
check("esc gt", escape(">"), "%3E")
check("esc apos", escape(chr(39)), "%27")
check("esc quote", escape(chr(34)), "%5C")  # client oddity, not %22
check("esc amp", escape("&"), "%26")
check("esc at", escape("@"), "%40")
check("esc percent", escape("%"), "%25")
check("esc plain", escape("Vasya"), "Vasya")
check("unesc quote", unescape("%5C"), chr(34))
MIXED = 'a<b>&"@%\'c'
check("unesc roundtrip", unescape(escape(MIXED)), MIXED)
check("escaped percent not re-decoded", unescape(escape("%3C")), "%3C")

# an @ inside a nickname must not terminate the @string@ value early
NICK = "va@sya"
F_AT = encode("userMsg", to=Str(NICK))
check("at escaped on wire", F_AT, "userMsg;to=@va%40sya@;")
check("at survives roundtrip", decode(F_AT), ("userMsg", {"to": NICK}))

# --- repeated keys, per CSMessage.addProp(name, value, duplicateName) ---
# The client writes the original name for every duplicate: a mail with
# attachments is "sndml;item=..;item=..;", a bulk delete "rmvml;id=..;id=..;".
# Every value has to survive, and a key sent once must decode as before.
_, mail = decode("sndml;item=x1a111c00;item=x2b111c00;item=x3c111c00;"
                 "body=@hi@;type=0;subj=@s@;to=@Vasya@;")
check("repeats keep every value", mail["item"],
      ["1a111c00", "2b111c00", "3c111c00"])
check("repeats are marked", isinstance(mail["item"], Repeated), True)
check("keys around the repeat are untouched",
      (mail["body"], mail["type"], mail["subj"], mail["to"]),
      ("hi", 0, "s", "Vasya"))
check("two repeats", decode("rmvml;id=x1;id=x2;"), ("rmvml", {"id": ["1", "2"]}))
single = decode("rmvml;id=x1;")[1]
check("a single key is still a scalar", single, {"id": "1"})
check("and not marked", isinstance(single["id"], Repeated), False)
check("a |list| value is not mistaken for a repeat",
      isinstance(decode("moveTo;path=|1|2|;")[1]["path"], Repeated), False)
check("every: absent", every(single, "item"), [])
check("every: single", every(single, "id"), ["1"])
check("every: repeated", every(mail, "item"), ["1a111c00", "2b111c00", "3c111c00"])
check("every: a list value stays one value",
      every(decode("moveTo;path=|1|2|;")[1], "path"), [[1, 2]])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f_ in fails:
        print(" -", f_)
    sys.exit(1)
print("all codec tests passed")
