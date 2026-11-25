"""Build native SHK palette variants, preserving SWF geometry and alpha.

Offline asset tool only (Pillow through swfx). Runtime/builds copy the committed
SWFs and need no image library. No Flash execution or new ActionScript.
"""
import argparse
import colorsys
import hashlib
import json
from pathlib import Path
import struct
import zlib

import swfx
import swfgen

# The original has no dedicated 16-gauge art; use its shotgun stun shells.
# 6.8's shipped artwork is a throwing blade, and 5.45's loose icon has an
# OT-labelled box. Use similar rifle cartridge shapes without a wrong label.
SOURCES = {
    60011: (6153, 'Ammo_45_EK_G'),
    60012: (6154, 'Ammo_762x25_EK_G'),
    60013: (6155, 'Ammo_762x51_EK_G'),
    60014: (6156, 'Ammo_12mm_EK_G'),
    60015: (6157, 'Ammo_556x45_EK_G'),
    60016: (6158, 'Ammo_762x39_EK_G'),
    60017: (6159, 'Ammo_762x54R_EK_G'),
    60018: (6160, 'Ammo_SP_5_6_EK_G'),
    60019: (6161, 'Ammo_SS190_EK_G'),
    60020: (6162, 'Ammo_86x70_EK_G'),
    60021: (6163, 'Ammo_SP_10_12_EK_G'),
    60022: (7116, 'Ammo_556x45_EK_G'),
    60023: (35025, 'Ammo_Metallbolt_EK_G'),
    60024: (35237, 'Ammo_40mmRPG_EK_G'),
    60025: (41239, 'Ammo_762x39_EK_G'),
    60026: (6156, 'Ammo_stun_G'),
}


def orange_variant(blob, red_shells=False):
    """Replace bitmap definitions only; retain all original tags and anchors."""
    swf = swfx.Swf(blob)
    body = zlib.decompress(blob[8:]) if blob[:3] == b'CWS' else blob[8:]
    _rect, end = swfx.read_rect(body, 0)
    end += 4  # rate and frame count
    tags, changed = [], 0
    for code, payload in swfx.iter_tags(body, end, len(body)):
        if code not in (6, 21, 35, 20, 36):
            tags.append(swfgen.tag(code, payload))
            continue
        cid = struct.unpack_from('<H', payload)[0]
        picture = swf.chars[cid][1].convert('RGBA')
        pixels = bytearray(picture.tobytes())
        for i in range(0, len(pixels), 4):
            r, g, b, a = pixels[i:i + 4]
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            selected = ((h < .055 or h > .94) if red_shells else .49 < h < .76)
            if a and selected and s > .18:
                # Same light/shadow and alpha; only the native tip/shell hue changes.
                rgb = colorsys.hsv_to_rgb(.065, max(.55, s), v)
                pixels[i:i + 3] = bytes(round(c * 255) for c in rgb)
                changed += 1
        tags.append(swfgen.lossless2(cid, picture.width, picture.height, bytes(pixels)))
    result = body[:end] + b''.join(tags)
    return b'CWS' + blob[3:4] + struct.pack('<I', len(result) + 8) + zlib.compress(result, 9), changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--res', type=Path, required=True)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    args = parser.parse_args()
    document = json.loads((args.data / 'own_items.json').read_text(encoding='utf-8'))
    dest = args.data / 'item_icons'
    dest.mkdir(exist_ok=True)
    sources = {}
    for type_id, (like, source) in SOURCES.items():
        rec = document['items'][str(type_id)]
        blob = (args.res / 'classes/Ammo' / source / 'ico.swf').read_bytes()
        icon, changed = orange_variant(blob, red_shells=type_id == 60026)
        (dest / (rec['name'] + '.swf')).write_bytes(icon)
        rec.update(like=like, own_icon=True)
        sources[str(type_id)] = dict(source=source, source_sha256=hashlib.sha256(blob).hexdigest(),
                                    sha256=hashlib.sha256(icon).hexdigest(), changed_pixels=changed)
    document['_meta']['shock_icons'] = ('2026-11-24: ШК сохраняют форму боеприпаса и оранжевую маркировку; '
        'собственные SWF в data/item_icons, воспроизводимы tools/shock_icons.py. '
        '9 мм — штатная Ammo_9mmNato_shock. Для 5.45 и 6.8 выбрана близкая винтовочная геометрия '
        'без неверной маркировки, для 16-го — дробовые гильзы. Свойства боеприпасов не меняются.')
    # Keep the hand-maintained compact document rather than reformatting unrelated rows.
    text = (args.data / 'own_items.json').read_text(encoding='utf-8')
    import re
    for tid in SOURCES:
        row = json.dumps(document['items'][str(tid)], ensure_ascii=False)
        text, n = re.subn(r'("%d": )\{[^\n]+\}' % tid, lambda m: m.group(1) + row, text)
        assert n == 1
    text = re.sub(r'("shock_icons": )"[^\n]+",',
                  lambda m: m.group(1) + json.dumps(document['_meta']['shock_icons'], ensure_ascii=False) + ',', text)
    (args.data / 'own_items.json').write_text(text, encoding='utf-8')
    (dest / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Built %d native SHK icons.' % len(sources))


if __name__ == '__main__':
    main()
