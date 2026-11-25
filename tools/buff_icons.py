"""Align the native Anesthetic + artwork; retain bitmap bytes and icon bounds."""
import argparse
import hashlib
from pathlib import Path
import struct
import zlib

import swfx
import swfgen

SOURCE_SHA256 = 'abfc2f6577fa2be9f4fab6d03662862aa00833ca5683bb00ffe3d85d09aded59'


def matrix(values):
    a, b, c, d, tx, ty = values
    writer = swfgen.BitWriter()
    for pair, default in (((a, d), (1, 1)), ((b, c), (0, 0))):
        present = pair != default
        writer.u(1, int(present))
        if present:
            integers = [round(value * 65536) for value in pair]
            n = swfgen.sbits(*integers)
            writer.u(5, n)
            for value in integers:
                writer.s(n, value)
    n = swfgen.sbits(tx, ty)
    writer.u(5, n)
    writer.s(n, tx)
    writer.s(n, ty)
    return writer.bytes()


def aligned_icon(blob):
    body = zlib.decompress(blob[8:]) if blob[:3] == b'CWS' else blob[8:]
    _, start = swfx.read_rect(body, 0)
    start += 4
    tags, changed = [], 0
    for code, payload in swfx.iter_tags(body, start, len(body)):
        if code in (2, 22, 32):
            _, p = swfx.read_rect(payload, 2)
            # This native icon is one clipped bitmap fill. Refuse a new
            # source layout rather than editing unrelated shapes or pixels.
            if payload[p] == 1 and payload[p + 1] in (0x41, 0x43):
                offset = p + 4  # fill count, type and bitmap ID
                transform, end = swfx.read_matrix(payload, offset)
                a, b, c, d, x, y = transform
                payload = payload[:offset] + matrix((a, b, c, d, x + 31 * 20, y)) + payload[end:]
                changed += 1
        tags.append(swfgen.tag(code, payload))
    if changed != 1:
        raise ValueError('Expected one native bitmap placement')
    result = body[:start] + b''.join(tags)
    return b'CWS' + blob[3:4] + struct.pack('<I', len(result) + 8) + zlib.compress(result, 9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]
                        / 'client/files/classes/Heal_Item/Anesthetic_Plus/ico.swf')
    args = parser.parse_args()
    blob = args.source.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SOURCE_SHA256:
        raise ValueError('Expected the original Anesthetic + icon')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(aligned_icon(blob))
    print(args.output)


if __name__ == '__main__':
    main()
