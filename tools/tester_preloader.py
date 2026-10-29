"""Small tester-only startup SWF using the original game's loading artwork."""
from pathlib import Path
import struct
import zlib

from swfx import Bits, iter_tags, read_matrix, read_rect
from swfgen import rect, tag
from widescreen import Asm, call_method


def shape_bitmaps(code, data):
    """Read all style arrays, including StateNewStyles inside ShapeRecords."""
    _, pos = read_rect(data, 2)
    if code == 83:
        _, pos = read_rect(data, pos)
        pos += 1
    ids = set()

    def count(pos):
        n = data[pos]
        pos += 1
        if n == 255 and code != 2:
            n = struct.unpack_from('<H', data, pos)[0]
            pos += 2
        return n, pos

    def fill(pos):
        kind = data[pos]
        pos += 1
        color = 3 if code in (2, 22) else 4
        if kind == 0:
            return pos + color
        if kind in (16, 18, 19):
            _, pos = read_matrix(data, pos)
            n = data[pos] & 15
            return pos + 1 + n * (1 + color) + (2 if kind == 19 else 0)
        if kind in (64, 65, 66, 67):
            bitmap = struct.unpack_from('<H', data, pos)[0]
            if bitmap != 65535:
                ids.add(bitmap)
            _, pos = read_matrix(data, pos + 2)
            return pos
        raise ValueError('Unsupported fill in startup artwork')

    def styles(pos):
        n, pos = count(pos)
        for _ in range(n):
            pos = fill(pos)
        n, pos = count(pos)
        for _ in range(n):
            pos += 2  # Stroke width.
            if code != 83:
                pos += 3 if code in (2, 22) else 4
            else:
                bits = Bits(data, pos)
                bits.u(2)  # Start cap.
                join = bits.u(2)
                has_fill = bits.u(1)
                bits.u(1)  # No horizontal scaling.
                bits.u(1)  # No vertical scaling.
                bits.u(1)  # Pixel hinting.
                bits.u(5)  # Reserved.
                bits.u(1)  # No close.
                bits.u(2)  # End cap, independent of join style.
                pos = bits.pos + (2 if join == 2 else 0)
                pos = fill(pos) if has_fill else pos + 4
        return pos

    bits = Bits(data, styles(pos))
    nf, nl = bits.u(4), bits.u(4)
    while True:
        if bits.u(1):
            straight = bits.u(1)
            n = bits.u(4) + 2
            if not straight:
                bits.u(4 * n)
            elif bits.u(1):
                bits.u(2 * n)
            else:
                bits.u(1)
                bits.u(n)
        else:
            flags = bits.u(5)
            if flags == 0:
                break
            if flags & 1:
                bits.u(2 * bits.u(5))
            if flags & 2:
                bits.u(nf)
            if flags & 4:
                bits.u(nf)
            if flags & 8:
                bits.u(nl)
            if flags & 16:
                bits = Bits(data, styles(bits.pos))
                nf, nl = bits.u(4), bits.u(4)
    return ids


def artwork(source):
    raw = Path(source).read_bytes()
    body = zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]
    _, pos = read_rect(body, 0)
    tags = list(iter_tags(body, pos + 4, len(body)))
    kinds = (2, 6, 20, 21, 22, 32, 35, 36, 39, 46, 83)
    definitions = {struct.unpack_from('<H', part)[0]: (code, part)
                   for code, part in tags if code in kinds}
    exported = {}
    for code, part in tags:
        if code != 56:
            continue
        at = 2
        for _ in range(struct.unpack_from('<H', part)[0]):
            cid = struct.unpack_from('<H', part, at)[0]
            at += 2
            end = part.index(b'\0', at)
            exported[part[at:end].decode('utf-8')] = cid
            at = end + 1
    panel = definitions[exported['preloaderPan']][1]
    children = [(part, struct.unpack_from('<H', part, 3)[0])
                for code, part in iter_tags(panel, 4, len(panel))
                if code == 26 and part[0] & 2]
    bar = next(cid for part, cid in children if b'progressBar\0' in part)
    background = next(cid for part, cid in children if part.endswith(b'bg\0'))
    selected = set()

    def include(cid):
        if cid in selected:
            return
        selected.add(cid)
        code, part = definitions[cid]
        if code == 39:
            for child_code, child in iter_tags(part, 4, len(part)):
                if child_code == 26 and child[0] & 2:
                    include(struct.unpack_from('<H', child, 3)[0])
                elif child_code == 4:
                    include(struct.unpack_from('<H', child)[0])
                elif child_code == 70:
                    raise ValueError('Unexpected PlaceObject3 in startup artwork')
        elif code in (2, 22, 32, 83):
            for bitmap in shape_bitmaps(code, part):
                include(bitmap)

    include(bar)
    include(background)
    library = b''.join(tag(code, part) for code, part in tags if code == 8 or
                       (code in kinds and struct.unpack_from('<H', part)[0] in selected))
    library += tag(56, struct.pack('<HH', 2, bar) + b'BootBar\0'
                   + struct.pack('<H', background) + b'BootFrame\0')
    if struct.unpack_from('<H', definitions[bar][1], 2)[0] != 100:
        raise ValueError('Expected the original 100-frame loading bar')
    return library, selected


def response_actions():
    a = Asm()
    a.var('_root').push('pending', False).op('setmember')
    a.var('ok').op('not').iftrue('out')
    a.var('this').member('progress').push(1, 'Number').op('callfunc')
    a.push(1).var('_root').member('bar').push('gotoAndStop').op('callmethod').op('pop')
    a.var('_root').member('label').push('text').var('this').member('stage').op('setmember')
    a.var('this').member('ready').push('-1').op('equals2').op('not').iftrue('check_ready')
    a.var('_root').push('onEnterFrame', None).op('setmember')
    a.push(True).iftrue('out')
    a.label('check_ready')
    a.var('this').member('ready').push('1').op('equals2').op('not').iftrue('out')
    a.var('_root').push('onEnterFrame', None).op('setmember')
    a.push('/res/main.swf?vversion=1', 1).var('_root').push('loadMovie').op('callmethod').op('pop')
    a.label('out')
    return a


def poll_actions():
    a = Asm()
    a.var('this').member('pending').iftrue('out')
    a.op('gettime').var('this').member('nextPoll').op('less2').iftrue('out')
    a.var('this').push('nextPoll').op('gettime').push(500).op('add2').op('setmember')
    a.var('this').push('pending', True).op('setmember')
    a.push('request', 0).var('_global').push('LoadVars').op('newmethod').op('definelocal')
    a.var('request').push('onLoad').function(['ok'], response_actions()).op('setmember')
    a.push('/startup-status?t=').op('gettime').op('add2')
    call_method(a, 'request', 'load', 1)
    a.label('out')
    return a


def script():
    a = Asm()
    for symbol, name, depth, x, y in (
            ('BootFrame', 'frame', 1, 482, 348), ('BootBar', 'bar', 2, 526, 404)):
        a.push(depth, name, symbol)
        call_method(a, '_root', 'attachMovie', 3)
        for prop, value in [('_x', x), ('_y', y)]:
            a.var('_root').member(name).push(prop, value).op('setmember')
        a.push(1, 1).var('_root').member(name).push('gotoAndStop').op('callmethod').op('pop')
    a.push(28, 275, 366, 501, 3, 'label')
    call_method(a, '_root', 'createTextField', 6)
    for prop, value in [('text', 'Подготовка игры…'), ('textColor', 0xC7C19B), ('selectable', False)]:
        a.var('_root').member('label').push(prop, value).op('setmember')
    a.var('_root').push('nextPoll', 0).op('setmember')
    a.var('_root').push('onEnterFrame').function([], poll_actions()).op('setmember')
    a.parts.append(b'\x07')  # Stop; onEnterFrame keeps the game's 25 frames/s.
    return a.assemble() + b'\0'


def build(source, target):
    library, ids = artwork(source)
    payload = rect(0, 1280 * 20, 0, 800 * 20) + struct.pack('<HH', 25 * 256, 1)
    payload += (tag(69, b'\0\0\0\0') + tag(9, b'\0\0\0') + library
                + tag(12, script()) + tag(1, b'') + tag(0, b''))
    movie = b'CWS' + bytes([8]) + struct.pack('<I', len(payload) + 8) + zlib.compress(payload, 9)
    Path(target).write_bytes(movie)
    return len(movie), len(ids)
