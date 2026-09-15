"""Codec tests derived from lol.server.SCDataParser semantics."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol import decode, encode, frame, FrameReader, Str, Hex, BigUInt

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
check("cp1251 frame", f.endswith(b"\x00"), True)
check("cp1251 roundtrip", decode(f[:-1])[1]["entry"], "Привет")

# --- regression: a protocol param literally named "name" (ah_search) ---
check("param called name",
      encode("ah_search", name=Str("gun"), page=1),
      "ah_search;name=@gun@;page=1;")
check("param name roundtrip",
      decode(encode("ah_search", name=Str("gun"), page=1)),
      ("ah_search", {"name": "gun", "page": 1}))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f_ in fails:
        print(" -", f_)
    sys.exit(1)
print("all codec tests passed")
