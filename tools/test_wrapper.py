"""The two films the launcher points the projector at, read back.

    python3 tools/test_wrapper.py

make_wrapper.py assembles AVM1 by hand, and its rule is that nothing is
assembled from memory: every opcode is first read out of main.swf, then out
of our own film before it is ever run. This is that second reading, made
permanent. It pins, action by action, the ClanInspector mend both films
carry (make_wrapper.py, CLAN INSPECTOR), checks that every jump and every
function body ends on an action boundary, that the 16:9 film is still the
film it was with the mend appended and nothing else changed, that the plain
film says nothing to the stage, that neither film holds a GetURL of any kind,
and -- when the client's main.swf is on this machine (LAVA_RES) -- that every
opcode and every function flag we emit is one main.swf itself uses.
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import make_wrapper as mw  # noqa: E402
import swf_actions as sa  # noqa: E402

RES = os.environ.get("LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res")

sys.path.insert(0, os.path.join(ROOT, "server"))
from testkit import check, fails  # noqa: E402


def blocks(data):
    return [(where, sa.disassemble(actions)) for where, actions in sa.action_blocks(data)]


def plain_listing(listing):
    return [(name, detail) for _, name, detail in listing]


def header(data):
    body = sa.body_of(data)
    nbits = body[0] >> 3
    bits = "".join(format(b, "08b") for b in body[:(5 + 4 * nbits + 7) // 8])
    rect = [int(bits[5 + i * nbits:5 + (i + 1) * nbits], 2) for i in range(4)]
    at = (5 + 4 * nbits + 7) // 8
    rate, frames = struct.unpack_from("<HH", body, at)
    return data[:3], data[3], rect[1] // 20, rect[3] // 20, rate / 256.0, frames


def matrix(blob, at):
    """A MATRIX at byte `at`: (its length in bytes, x and y translation in
    pixels). Scale and rotate are skipped over; ours never carry them."""
    bits = "".join(format(b, "08b") for b in blob[at:at + 40])
    i = 0
    for _ in ("scale", "rotate"):
        if bits[i] == "1":
            n = int(bits[i + 1:i + 6], 2)
            i += 6 + 2 * n
        else:
            i += 1
    n = int(bits[i:i + 5], 2)
    i += 5

    def signed(s):
        return int(s, 2) - (1 << len(s)) if s and s[0] == "1" else int(s or "0", 2)
    tx, ty = signed(bits[i:i + n]), signed(bits[i + n:i + 2 * n])
    return (i + 2 * n + 7) // 8, (tx / 20.0, ty / 20.0)


def places(data):
    """(depth, name, (x, y)) of each PlaceObject2 on the timeline -- flags,
    depth, character, matrix, name, which is all make_wrapper.place writes."""
    out = []
    for code, blob in sa.tags(sa.body_of(data)):
        if code == 26:
            (depth,) = struct.unpack_from("<H", blob, 1)
            ln, xy = matrix(blob, 5)
            out.append((depth, sa.cstr(blob, 5 + ln)[0], xy))
    return out


def boundaries_hold(actions):
    """Every If/Jump lands on an action, and every DefineFunction2 body ends
    on one; returns the offending offsets."""
    listing = sa.disassemble(actions)
    starts = {at for at, _, _ in listing} | {len(actions)}
    bad = []
    for at, name, detail in listing:
        if name in ("If", "Jump"):
            if at + 5 + int(detail) not in starts:
                bad.append((at, name, detail))
        if name == "DefineFunction2":
            (ln,) = struct.unpack_from("<H", actions, at + 1)
            size = int(detail.rsplit("body=", 1)[1])
            if at + 3 + ln + size not in starts:
                bad.append((at, name, detail))
    return bad


# The mend, as swf_actions prints it. Pinned whole: a change to any action of
# it has to be made here too, on purpose.
PROTO = [("Push", "'lol'"), ("GetVariable", ""), ("Push", "'core'"), ("GetMember", ""),
         ("Push", "'clans'"), ("GetMember", ""), ("Push", "'ClanInspector'"),
         ("GetMember", ""), ("Push", "'prototype'"), ("GetMember", "")]
CLASS = PROTO[:8]
KILL_BODY = ([("Push", "0.0, reg:1, 'rebornKill'"), ("CallMethod", ""), ("Pop", "")]
             + CLASS + [("Push", "'sInstance', null"), ("SetMember", "")]
             + CLASS + [("Push", "'sInstance'"), ("Delete", ""), ("Pop", "")]
             + [("Push", "0.0, 0.0"), ("Push", "'lol'"), ("GetVariable", ""),
                ("Push", "'core'"), ("GetMember", ""), ("Push", "'Master'"),
                ("GetMember", ""), ("Push", "'getInstance'"), ("CallMethod", ""),
                ("Push", "'initClanInspector'"), ("CallMethod", ""), ("Pop", "")])
MEND = (PROTO + [("Push", "'rebornKill'"), ("GetMember", ""), ("Not", ""), ("Not", ""),
                 ("If", "558")]
        + PROTO + [("Push", "'kill'"), ("GetMember", ""), ("Not", ""), ("If", "478")]
        + PROTO + [("Push", "'rebornKill'")] + PROTO + [("Push", "'kill'"),
                                                         ("GetMember", ""), ("SetMember", "")]
        + PROTO + [("Push", "'kill'"),
                   ("DefineFunction2", "name='' params=() regs=2 flags=0x29,0x00 body=239")]
        + KILL_BODY + [("SetMember", "")])

# What the 16:9 film was before the mend, byte for byte: the film every
# LAVA_SCALE run had shipped until then.
PRE_MEND_SHA = "8cb90cbb16152a543469a679c90917efda14a04a0dce86a97cbd761506ce17ba"

films = {"wrapper.swf": mw.build(), "wrapper_plain.swf": mw.build(scale=False)}

print("the films on disk are the films this script builds")
for name, data in films.items():
    path = os.path.join(ROOT, "launcher", "assets", name)
    with open(path, "rb") as fh:
        check("launcher/assets/%s is up to date" % name, fh.read() == data, True)

print("the 16:9 film is what it was, with the mend appended")
check("without the mend it is the pre-mend film byte for byte",
      hashlib.sha256(mw.build(mend=False)).hexdigest(), PRE_MEND_SHA)
old = dict(blocks(mw.build(mend=False)))
new = dict(blocks(films["wrapper.swf"]))
check("same action streams", sorted(new), sorted(old))
for where in sorted(new):
    was, now = plain_listing(old[where]), plain_listing(new[where])
    if where.startswith("DefineSprite 2"):
        check("%s: the old frame, then the mend, then End" % where,
              now, was[:-1] + MEND + [("End", "")])
    else:
        check("%s: unchanged" % where, now, was)
check("16:9 header: FWS 8, 1280x720, 25 fps, one frame",
      header(films["wrapper.swf"]), (b"FWS", 8, 1280, 720, 25.0, 1))

print("the plain film")
plain = dict(blocks(films["wrapper_plain.swf"]))
check("header: FWS 8, main.swf's own 950x650, 25 fps, one frame",
      header(films["wrapper_plain.swf"]), (b"FWS", 8, 950, 650, 25.0, 1))
check("the game at the origin, the keeper beside it",
      places(films["wrapper_plain.swf"]),
      [(1, "game", (0.0, 0.0)), (2, "keeper", (0.0, 0.0))])
check("the 16:9 film's game still sits in the middle, where the game thinks it is",
      places(films["wrapper.swf"]),
      [(1, "game", (165.0, 35.0)), (2, "keeper", (0.0, 0.0))])
said = " ".join(d for listing in plain.values() for _, _, d in listing)
check("nothing said to Stage, scaleMode or _quality",
      [w for w in ("'Stage'", "'scaleMode'", "'_quality'") if w in said], [])
for frame in (1, 2):
    where = "DefineSprite 2, кадр %d: DoAction" % frame
    listing = plain_listing(plain[where])
    check("keeper frame %d: _lockroot, the five flashvars, the mend, End" % frame,
          (listing[:6], listing[-len(MEND) - 1:]),
          ([("Push", "'_root'"), ("GetVariable", ""), ("Push", "'game'"),
            ("GetMember", ""), ("Push", "'_lockroot', true"), ("SetMember", "")],
           MEND + [("End", "")]))
    check("keeper frame %d: every flashvar handed down" % frame,
          [d for n, d in listing if n == "Push" and d in
           ("'logged'", "'var_host'", "'var_port'", "'vversion'", "'session'")],
          ["'logged'", "'logged'", "'var_host'", "'var_host'", "'var_port'",
           "'var_port'", "'vversion'", "'vversion'", "'session'", "'session'"])
check("root frame: _lockroot, game.loadMovie('main.swf'), Stop -- and no mend",
      plain_listing(plain["DoAction, кадр 1"]),
      [("Push", "'_root'"), ("GetVariable", ""), ("Push", "'game'"), ("GetMember", ""),
       ("Push", "'_lockroot', true"), ("SetMember", ""), ("Push", "'main.swf'"),
       ("Push", "1.0"), ("Push", "'game'"), ("GetVariable", ""), ("Push", "'loadMovie'"),
       ("CallMethod", ""), ("Pop", ""), ("Stop", ""), ("End", "")])

print("both films, and their debug builds")
debug = {"wrapper_debug": mw.build(debug=True), "wrapper_plain_debug": mw.build(True, False)}
for name, data in list(films.items()) + list(debug.items()):
    for where, actions in sa.action_blocks(data):
        check("%s, %s: jumps and function bodies land on actions" % (name, where),
              boundaries_hold(actions), [])
    names = {n for _, listing in blocks(data) for _, n, _ in listing}
    check("%s: no GetURL, no GetURL2" % name, names & {"GetURL", "GetURL2"}, set())
    check("%s: every opcode is one swf_actions knows by name" % name,
          sorted(n for n in names if n.startswith("0x")), [])
for name, data in debug.items():
    said = [d for _, listing in blocks(data) for _, n, d in listing if n == "Push"]
    check("%s: says when the mend lands and when it works" % name,
          ("'reborn: ClanInspector mended'" in said,
           "'reborn: ClanInspector.kill -> fresh inspector'" in said), (True, True))

main_swf = os.path.join(RES, "main.swf")
if os.path.exists(main_swf):
    print("nothing assembled from memory: checked against %s" % main_swf)
    with open(main_swf, "rb") as fh:
        game = fh.read()
    theirs, flags = set(), set()
    for _, actions in sa.action_blocks(game):
        for _, n, d in sa.disassemble(actions):
            theirs.add(n)
            if n == "DefineFunction2":
                flags.add(d.split("flags=")[1].split()[0])
    for name, data in list(films.items()) + list(debug.items()):
        ours = {n for _, listing in blocks(data) for _, n, _ in listing}
        check("%s: every opcode also occurs in main.swf" % name, sorted(ours - theirs), [])
    check("flags 0x29,0x00 -- preload this into reg:1 -- are main.swf's own",
          "0x29,0x00" in flags, True)
else:
    print("  --  main.swf not found at %s; the opcode check against it is skipped" % RES)

if fails:
    print("\n%d FAILED:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("\nall ok")
