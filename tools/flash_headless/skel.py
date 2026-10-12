"""The empty film FFDec compiles host.as into (Dockerfile, stage "film"):
SWF 9, AS2, a 950x650 stage at 25 frames a second, one frame holding an
empty DoAction for FFDec's importScript to fill.

    python3 skel.py OUT.swf
"""
import struct
import sys


def rect(*vals):
    n = max(max(abs(v).bit_length() for v in vals) + 1, 1)
    bits = "{:05b}".format(n) + "".join(format(v & ((1 << n) - 1), "0%db" % n) for v in vals)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def tag(code, body):
    if len(body) >= 63:
        return struct.pack("<HI", code << 6 | 63, len(body)) + body
    return struct.pack("<H", code << 6 | len(body)) + body


body = rect(0, 950 * 20, 0, 650 * 20) + struct.pack("<HH", 25 << 8, 1)
body += tag(69, struct.pack("<I", 0)) + tag(9, b"\x33\x33\x33") + tag(12, b"\x00") + tag(1, b"") + tag(0, b"")
with open(sys.argv[1], "wb") as fh:
    fh.write(b"FWS" + bytes([9]) + struct.pack("<I", 8 + len(body)) + body)
