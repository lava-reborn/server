"""Verify the real private-tab artwork without launching Flash."""
import os
from pathlib import Path
import struct
import unittest
import chat_tabs
import widescreen as w


def exports(tags):
    out = {}
    for code, payload, _ in tags:
        if code != 56:
            continue
        at = 2
        for _ in range(struct.unpack_from('<H', payload)[0]):
            cid = struct.unpack_from('<H', payload, at)[0]
            at += 2
            end = payload.index(b'\0', at)
            out[payload[at:end].decode()] = cid
            at = end + 1
    return out


def fixture():
    """Small native tab/font envelope for CI, which omits main.swf."""
    from swfgen import rect
    names = {'channel_clan_btn': 1, 'channel_btn': 2,
             'channel_main_btn': 3, 'channel_private_btn': 4}
    codes = list(range(32, 127)) + list(range(0x400, 0x460))
    count = len(codes)
    offsets = [2 * (count + 1) + 2 * i for i in range(count + 1)]
    font = (struct.pack('<H', 5) + bytes((4, 0, 6)) + b'Arial\0'
            + struct.pack('<H', count) + struct.pack('<%dH' % (count + 1), *offsets)
            + b'\0\0' * count + struct.pack('<%dH' % count, *codes))
    tags = [(75, font, True), (2, struct.pack('<H', 6) + rect(0, 20, 0, 20)
                             + b'\0\0\0', True)]
    for cid in names.values():
        caption = bytes((6,)) + struct.pack('<HH', 4, 6) + b'\0'
        close = bytes((0x26,)) + struct.pack('<HH', 5, 6) + b'\0close_btn\0'
        children = [(26, caption, True)]
        if cid == 2:
            children.append((26, close, True))
        children += [(1, b'', False), (0, b'', False)]
        tags.append((39, struct.pack('<HH', cid, 1) + w.join_tags(b'', children), True))
    tags += [(56, struct.pack('<H', len(names)) + b''.join(
        struct.pack('<H', cid) + name.encode() + b'\0' for name, cid in names.items()), True),
        (1, b'', False), (0, b'', False)]
    return tags


class PrivateCaptionArtwork(unittest.TestCase):
    def test_private_caption_replaces_baked_clan_text_without_changing_clan(self):
        source = Path(os.environ.get('LAVA_RES', 'res')) / 'main.swf'
        if source.is_file():
            _, body = w.read_swf(source)
            original = w.split_tags(body)
        else:
            original = fixture()
        patched = chat_tabs.artwork(original)
        self.assertEqual(chat_tabs.artwork(patched), patched)
        links = exports(patched)
        def definition(tags, cid):
            return next((code, payload) for code, payload, _ in tags
                        if code in (37, 39) and struct.unpack_from('<H', payload)[0] == cid)
        clan_id = links['channel_clan_btn']
        self.assertEqual(definition(original, clan_id), definition(patched, clan_id))
        _, sprite = definition(patched, links['__pm_channel_btn'])
        children = w.split_tags(b'\x08\0\0\0\0\0' + sprite[4:])
        captions = [p for c, p, _ in children if c == 26
                    and struct.unpack_from('<H', p, 1)[0] == 4]
        self.assertEqual(len(captions), 1)
        self.assertEqual(struct.unpack_from('<H', captions[0], 3)[0], links['__pm_nickname_text'])
        self.assertTrue(captions[0].endswith(b'pmNickname\0'))
        self.assertEqual(sum(c == 26 and b'close_btn\0' in p for c, p, _ in children), 1)
        _, text = definition(patched, links['__pm_nickname_text'])
        nbits = text[2] >> 3
        at = 2 + (5 + 4 * nbits + 7) // 8
        from swfgen import rect
        self.assertEqual(text[2:at], rect(360, 1560, 20, 360))
        self.assertEqual(text[at:at + 2], bytes((0x8D, 0x31)))
        font_id, height = struct.unpack_from('<HH', text, at + 2)
        self.assertEqual(height, 220)  # 11 px, without scaling the overlay.
        self.assertEqual(text[at + 10], 2)  # SWF: 1=right, 2=center.
        font = next(p for c, p, _ in patched if c == 75
                    and struct.unpack_from('<H', p)[0] == font_id)
        self.assertEqual(font[5:5 + font[4]].rstrip(b'\0'), b'Arial')
        offset = 5 + font[4]
        count = struct.unpack_from('<H', font, offset)[0]
        table = offset + 2
        size = 4 if font[2] & 8 else 2
        code_offset = struct.unpack_from('<I' if size == 4 else '<H',
                                         font, table + count * size)[0] + table
        codes = struct.unpack_from('<%dH' % count, font, code_offset)
        self.assertTrue(all(ord(ch) in codes for ch in 'Tester0123456789Лейкан'))
        self.assertTrue(text.endswith(b'\0\0'))  # No fixed caption or variable.
        for name in ('channel_btn', 'channel_main_btn', 'channel_private_btn'):
            self.assertEqual(definition(original, links[name]), definition(patched, links[name]))


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from testkit import run_cases
    run_cases(PrivateCaptionArtwork)
