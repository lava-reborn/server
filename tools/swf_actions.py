#!/usr/bin/env python3
"""Disassemble AVM1 action streams out of a SWF.

    python3 tools/swf_actions.py <file.swf> [--find CallMethod] [--limit 40]

Written after a wrapper of mine sprayed 478 copies of main.swf into the
downloads folder: I had assembled a GetURL2 from memory, its target flag was
wrong, and Flash's fallback for a target it cannot resolve is to hand the URL
to the browser. So the rule now is that nothing gets assembled from memory --
every opcode this project emits is first read back out of a film the real
Flash compiler produced, and then out of our own before it is ever run.

Actions inside a DefineSprite are listed too, with the sprite and the frame
they run on. The first version of this file only looked at the film's own
timeline, and the wrapper's keeper -- the clip whose frames do all the work
after the first -- lives inside a sprite, so the self-check this file promises
did not cover exactly the code that mattered.

A ConstantPool is decoded and the pushes that refer to it are shown with the
string they mean (main.swf pushes almost every name that way), and a
DefineFunction/DefineFunction2 header is spelled out -- name, parameters,
registers, flags, body length -- because the body follows it inline in the
same stream and the header is what says where the body ends.
"""
import struct
import sys
import zlib

# Only what this project emits or reads. Anything else prints as its number,
# which is the honest thing to show for an opcode nobody here verified.
# Delete, NewMethod, StoreRegister and ConstantPool were added when the
# ClanInspector patch was written: each was read out of main.swf at a spot the
# decompiled source names (MailInspector.kill's `delete ...sInstance`, the
# `new ...MailInspector()` in its getInstance, the register stores of every
# method prologue, the pool at the head of every class). Trace is what the
# wrapper's --debug build emits, and main.swf has it too (XMLConnection's
# "Use getInstance method." is one).
NAMES = {
    0x00: "End", 0x04: "NextFrame", 0x06: "Play", 0x07: "Stop",
    0x12: "Not", 0x17: "Pop", 0x1C: "GetVariable", 0x1D: "SetVariable",
    0x26: "Trace", 0x3A: "Delete",
    0x3D: "CallFunction", 0x3E: "Return", 0x40: "NewObject",
    0x4E: "GetMember", 0x4F: "SetMember", 0x52: "CallMethod",
    0x53: "NewMethod",
    0x81: "GotoFrame", 0x83: "GetURL", 0x87: "StoreRegister",
    0x88: "ConstantPool", 0x8B: "SetTarget", 0x8E: "DefineFunction2",
    0x96: "Push", 0x99: "Jump", 0x9A: "GetURL2", 0x9B: "DefineFunction",
    0x9D: "If", 0x9F: "GotoFrame2",
}

PUSH_TYPES = {0: "str", 1: "float", 2: "null", 3: "undef", 4: "reg",
              5: "bool", 6: "double", 7: "int", 8: "const8", 9: "const16"}


def body_of(data):
    return zlib.decompress(data[8:]) if data[:3] == b"CWS" else data[8:]


def tag_stream(body, i):
    """(code, blob) for each tag from offset i up to and including End."""
    while i < len(body) - 1:
        (th,) = struct.unpack_from("<H", body, i)
        i += 2
        code, ln = th >> 6, th & 0x3F
        if ln == 0x3F:
            (ln,) = struct.unpack_from("<I", body, i)
            i += 4
        yield code, body[i:i + ln]
        if code == 0:
            return
        i += ln


def tags(body):
    """The film's own tags: skip the header's RECT, frame rate and count."""
    nbits = body[0] >> 3
    return tag_stream(body, (5 + 4 * nbits + 7) // 8 + 4)


def cstr(blob, i):
    """A NUL-terminated UTF-8 string at i, and the offset just past it."""
    end = blob.index(b"\x00", i)
    return blob[i:end].decode("utf-8", "replace"), end + 1


def push_args(blob, pool=None):
    out, i = [], 0
    while i < len(blob):
        t = blob[i]
        i += 1
        if t == 0:
            s, i = cstr(blob, i)
            out.append("'%s'" % s)
        elif t == 7:
            out.append(str(struct.unpack_from("<i", blob, i)[0]))
            i += 4
        elif t == 1:
            out.append(str(struct.unpack_from("<f", blob, i)[0]))
            i += 4
        elif t == 6:
            out.append(str(struct.unpack_from("<d", blob, i)[0]))
            i += 8
        elif t in (4, 8):
            out.append("%s:%d" % (PUSH_TYPES[t], blob[i]))
            if t == 8 and pool is not None and blob[i] < len(pool):
                out[-1] += "='%s'" % pool[blob[i]]
            i += 1
        elif t == 9:
            n = struct.unpack_from("<H", blob, i)[0]
            out.append("const16:%d" % n)
            if pool is not None and n < len(pool):
                out[-1] += "='%s'" % pool[n]
            i += 2
        elif t == 5:
            out.append("true" if blob[i] else "false")
            i += 1
        else:
            out.append(PUSH_TYPES.get(t, "?%d" % t))
    return out


def function_header(code, blob):
    """The header of DefineFunction (0x9B) or DefineFunction2 (0x8E), spelled
    out. The body is not in blob: it follows the action in the stream, and
    'body=' is how many bytes of it there are."""
    name, i = cstr(blob, 0)
    (nparams,) = struct.unpack_from("<H", blob, i)
    i += 2
    if code == 0x9B:
        params = []
        for _ in range(nparams):
            p, i = cstr(blob, i)
            params.append(p)
        (size,) = struct.unpack_from("<H", blob, i)
        return "name='%s' params=(%s) body=%d" % (name, ", ".join(params), size)
    regs = blob[i]
    flags = blob[i + 1:i + 3]
    i += 3
    params = []
    for _ in range(nparams):
        reg = blob[i]
        p, i = cstr(blob, i + 1)
        params.append("%s@reg:%d" % (p, reg))
    (size,) = struct.unpack_from("<H", blob, i)
    return ("name='%s' params=(%s) regs=%d flags=0x%02X,0x%02X body=%d"
            % (name, ", ".join(params), regs, flags[0], flags[1], size))


def disassemble(actions):
    out, i, pool = [], 0, None
    while i < len(actions):
        code = actions[i]
        at = i
        i += 1
        if code < 0x80:
            out.append((at, NAMES.get(code, "0x%02X" % code), ""))
            if code == 0:
                break
            continue
        (ln,) = struct.unpack_from("<H", actions, i)
        i += 2
        blob = actions[i:i + ln]
        i += ln
        name = NAMES.get(code, "0x%02X" % code)
        if code == 0x96:
            detail = ", ".join(push_args(blob, pool))
        elif code == 0x88:
            (count,) = struct.unpack_from("<H", blob, 0)
            pool, j = [], 2
            for _ in range(count):
                s, j = cstr(blob, j)
                pool.append(s)
            detail = "%d: %s" % (count, ", ".join("'%s'" % s for s in pool[:6])
                                 + (", ..." if count > 6 else ""))
        elif code in (0x8E, 0x9B):
            detail = function_header(code, blob)
        elif code == 0x87:
            detail = "reg:%d" % blob[0]
        elif code == 0x9A:
            f = blob[0]
            detail = ("flags=0x%02X (SendVars=%d, LoadTarget=%d, LoadVars=%d)"
                      % (f, f >> 6, (f >> 1) & 1, f & 1))
        elif code in (0x81, 0x99, 0x9D):
            detail = str(struct.unpack_from("<h", blob, 0)[0])
        else:
            detail = blob.hex()[:40]
        out.append((at, name, detail))
    return out


def action_blocks(data):
    """Every action stream in a film, as (where, actions): the timeline's
    DoAction and DoInitAction tags, and the DoAction tags of every sprite
    with the frame they sit on (frames counted from 1, as Flash does)."""
    body = body_of(data)
    frame = 1
    for code, blob in tags(body):
        if code == 12:
            yield "DoAction, кадр %d" % frame, blob
        elif code == 59:
            yield ("DoInitAction sprite %d" % struct.unpack_from("<H", blob, 0)[0],
                   blob[2:])
        elif code == 39:
            sid = struct.unpack_from("<H", blob, 0)[0]
            sframe = 1
            for scode, sblob in tag_stream(blob, 4):
                if scode == 12:
                    yield "DefineSprite %d, кадр %d: DoAction" % (sid, sframe), sblob
                elif scode == 1:
                    sframe += 1
        elif code == 1:
            frame += 1


def main(argv):
    path = argv[1]
    find = None
    limit = 40
    for k, a in enumerate(argv):
        if a == "--find":
            find = argv[k + 1]
        if a == "--limit":
            limit = int(argv[k + 1])

    with open(path, "rb") as fh:
        data = fh.read()

    shown = 0
    for where, actions in action_blocks(data):
        listing = disassemble(actions)
        if find and not any(find in n for _, n, _ in listing):
            continue
        print("=== %s, %d байт ===" % (where, len(actions)))
        for at, name, detail in listing:
            print("  %5d  %-16s %s" % (at, name, detail))
        shown += 1
        if shown >= limit:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
