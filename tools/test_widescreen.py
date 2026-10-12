"""Client patch: valid AVM1 branches, one injection, original artwork intact.

The online HUD shares the frame patch's handwritten AVM1. Verify every
function's branches within that function, then patch a small SWF fixture
twice: no accumulated wrappers, altered art or unrelated class changes.
CI intentionally carries no main.swf (deploy/ci/make_test_extras.sh).
When the real client is available, run the same checks on it as well.
"""
import math
import os
import re
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import widescreen as w  # noqa: E402
import world  # noqa: E402
from testkit import check, fails  # noqa: E402


def validate(code):
    """Parse function envelopes separately; no jump may leave its body."""
    at, starts, targets, errors = 0, set(), [], []
    while at < len(code):
        starts.add(at)
        op = code[at]
        at += 1
        if op < 0x80:
            if op not in w.OPS.values():
                errors.append("unexpected action %02x" % op)
            continue
        size, = struct.unpack_from("<H", code, at)
        at += 2
        end = at + size
        if end > len(code):
            errors.append("truncated action")
            break
        if op == 0x9D:
            delta, = struct.unpack_from("<h", code, at)
            targets.append(end + delta)
        elif op == 0x83:
            # GetURL: url and target, two NUL-terminated strings, no more.
            if code[at:end].count(b"\0") != 2 or code[end - 1] != 0:
                errors.append("malformed GetURL")
        elif op == 0x9B:
            body_size, = struct.unpack_from("<H", code, end - 2)
            errors.extend(validate(code[end:end + body_size]))
            end += body_size
        elif op != 0x96:
            errors.append("unexpected long action %02x" % op)
        at = end
    starts.add(len(code))
    errors.extend("branch outside its function: %s" % target
                  for target in targets if target not in starts)
    if at != len(code):
        errors.append("function length mismatch")
    return errors


# --- bytecode, in process --------------------------------------------------
check("every HUD and frame branch lands inside its own function",
      validate(w.injected()), [])

# A merge of main into location-viewport (ec8cd46) once dropped the two
# ExtViewFrame wraps from the table and left fn_location_bound defined and
# never called: the code was valid and every check here passed, while the
# camera clamp was simply not in the client. The real-Flash suites that
# would see it skip without LAVA_FLASH_PLAYER. So: every patch body the
# module defines is used, and every wrap leaves its saved original's name
# in the injected code, which only a wired wrap puts there.
WIRED = ("__wideBoundXOrig", "__wideBoundYOrig",       # location camera
         "__repairGoldOrig", "__repairGetPropOrig",    # gold-only repairs
         "__siteForumOrig", "__siteTooltipOrig",       # the old site's links
         "__progressInfoOrig", "__progress_increase_spec_level_func",
         "__onlineSendOrig", "__onlineNotifyOrig",     # online players
         "__wideCreateOrig", "__wideSceneOrig",        # library, location mask
         "__byeKickOrig", "__byeOrig",                 # no old login screen
         "__corpseDeadOrig", "__corpseFocusOrig",      # a corpse and its bag
         "__corpseLocationOrig", "__corpseRemoveOrig", # corpse cell ownership
         "__subInitOrig", "__subGlobalOrig",           # sublocation exit
         "__mapScrollOrig", "__mapResizeOrig")         # global map scroll box
_source = open(w.__file__, encoding="utf-8").read()
check("every fn_* patch body in widescreen.py is used",
      [name for name in re.findall(r"^def (fn_\w+)\(", _source, re.M)
       if len(re.findall(r"\b%s\b" % name, _source)) < 2], [])
check("every wrap is wired into the injected code",
      [name for name in WIRED if name.encode() not in w.injected()], [])


def execute(code, env, returns=True):
    """Execute an emitted AVM1 wrapper with the original as a stub.

    This catches stack order, branches and returns that container checks
    alone cannot exercise. Opcodes follow the AVM1 stack convention. A body
    that ends without Return (returns=False) gives None.
    """
    stack, at = [], 0
    while at < len(code):
        op = code[at]
        at += 1
        payload = b""
        if op >= 0x80:
            size, = struct.unpack_from("<H", code, at)
            at += 2
            payload = code[at:at + size]
            at += size
        if op == 0x96:
            p = 0
            while p < len(payload):
                kind = payload[p]
                p += 1
                if kind == 0:
                    end = payload.index(b"\0", p)
                    stack.append(payload[p:end].decode())
                    p = end + 1
                elif kind == 7:
                    stack.append(struct.unpack_from("<i", payload, p)[0])
                    p += 4
                elif kind in (2, 3):                    # null, undefined
                    stack.append(None)
                else:
                    raise AssertionError("unexpected push type: %s" % kind)
        elif op == 0x1C:
            stack.append(env[stack.pop()])
        elif op == 0x4E:
            # a member of undefined is undefined, as in the player
            key, obj = stack.pop(), stack.pop()
            stack.append(None if obj is None else obj.get(key))
        elif op == 0x4F:
            value, key, obj = stack.pop(), stack.pop(), stack.pop()
            obj[key] = value
        elif op == 0x52:
            method, obj, count = stack.pop(), stack.pop(), stack.pop()
            stack.append(obj[method](*[stack.pop() for _ in range(count)]))
        elif op == 0x3C:
            value, key = stack.pop(), stack.pop()
            env[key] = value
        elif op == 0x12:
            stack.append(not stack.pop())
        elif op == 0x17:
            stack.pop()
        elif op in (0x49, 0x48, 0x0C, 0x0D, 0x0B, 0x47):
            right, left = stack.pop(), stack.pop()
            stack.append({0x49: lambda: left == right, 0x48: lambda: left < right,
                          0x0C: lambda: left * right, 0x0D: lambda: left / right,
                          0x0B: lambda: left - right, 0x47: lambda: left + right}[op]())
        elif op == 0x9D:
            if stack.pop():
                at += struct.unpack("<h", payload)[0]
        elif op == 0x3E:
            return stack.pop()
        else:
            raise AssertionError("unexpected opcode: %02x" % op)
    if returns:
        raise AssertionError("missing return")
    return None


def run_repair_getprop(props, prop, mode, rate=50000):
    env = dict(prop=prop, this={"__repairGetPropOrig": lambda key: props.get(key)},
               lol=dict(gpui=dict(StaffInterface=dict(ssType=mode)),
                        core=dict(GConstatns=dict(gold_repair_mod=rate))))
    return execute(w.fn_repair_cost().assemble(), env)


check("gold repair bytecode rounds to nearest cent, halves up, with a one-cent minimum",
      [execute(w.fn_repair_gold().assemble(),
               dict(afro_cost=a, Math=dict(round=lambda x: math.floor(x + 0.5)),
                    lol=dict(core=dict(GConstatns=dict(gold_repair_mod=50000)))))
       for a in (0, 1, 749, 750, 751, 975, 1249, 1250, 1251)],
      [0.01, 0.01, 0.01, 0.02, 0.02, 0.02, 0.02, 0.03, 0.03])


check("gold Walther has a 6500 afro repair valuation only while repair is open",
      [run_repair_getprop(dict(cost=0, g_cost=13), "cost", mode)
       for mode in ("repair", "trade", "barter", None)], [6500, 0, 0, 0])
check("repair valuation follows the server's currency rate",
      run_repair_getprop(dict(cost=0, g_cost=300), "cost", "repair", 40000), 120000)
check("ordinary and dual-priced items keep their afro price in repairs",
      [run_repair_getprop(dict(cost=2800, g_cost=g), "cost", "repair")
       for g in (0, 13)], [2800, 2800])
check("gold price, repair modifier and genuinely unpriced items are unchanged",
      [run_repair_getprop(dict(cost=0, g_cost=13, repair_mod=1), p, "repair")
       for p in ("g_cost", "repair_mod", "absent")]
      + [run_repair_getprop(dict(cost=0, g_cost=0), "cost", "repair")],
      [13, 1, None, 0])


# --- the global map's picture: MAP_TILES against a release's tiles ----------
# Patch 13 holds the view on MAP_TILES. A release's tiles are client/base.txt
# (the original's, less client/remove.txt), client/extra.txt and client/files
# (ours), all in git, so this runs in CI too (client/build.py, the layers).
CLIENT = os.path.join(os.path.dirname(HERE), "client")


def release_tiles(folder, row):
    """{(column, row)} of the release's globalmap/<folder>/<n>.jpg, n being
    row * <row> + column (SSEmulator.getGMTURL)."""
    prefix = "globalmap/%s/" % folder
    with open(os.path.join(CLIENT, "remove.txt"), encoding="utf-8") as fh:
        removed = {line.strip() for line in fh if line.strip() and not line.startswith("#")}
    names = set()
    for listing, gone in (("base.txt", removed), ("extra.txt", set())):
        with open(os.path.join(CLIENT, listing), encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 3 and parts[2].startswith(prefix) and parts[2] not in gone:
                    names.add(parts[2][len(prefix):])
    ours = os.path.join(CLIENT, "files", *prefix.split("/"))
    if os.path.isdir(ours):
        names.update(os.listdir(ours))
    stems = [name[:-4] for name in names if name.endswith(".jpg")]
    return {(int(n) % row, int(n) // row) for n in stems if n.isdigit()}


try:
    for scale, folder, row, stray in (("full", "full", 256, [(163, 57)]),
                                      ("small", "client", 32, [])):
        have = release_tiles(folder, row)
        x0, y0, x1, y1 = w.MAP_TILES[scale]
        box = {(x, y) for x in range(x0, x1) for y in range(y0, y1)}
        check("MAP_TILES %s: every tile of columns %d..%d by rows %d..%d is in the "
              "release" % (scale, x0, x1 - 1, y0, y1 - 1), sorted(box - have), [])
        rims = {"west": [(x0 - 1, y) for y in range(y0, y1)],
                "east": [(x1, y) for y in range(y0, y1)],
                "north": [(x, y0 - 1) for x in range(x0, x1)],
                "south": [(x, y1) for x in range(x0, x1)]}
        check("MAP_TILES %s: no whole column or row more on any side" % scale,
              [side for side, rim in rims.items() if set(rim) <= have], [])
        check("MAP_TILES %s: outside it, only the tiles known to stand alone" % scale,
              sorted(have - box), stray)
    # The five tiles of a narrow window stay on the picture wherever the
    # server lets the player stand: two tiles in from every edge.
    x0, y0, x1, y1 = w.MAP_TILES["full"]
    check("the world (world.MAP_X, MAP_Y) lies two tiles in from every edge of "
          "the full-scale picture",
          [x0 + 2 <= world.MAP_X[0] * 8 // 256, world.MAP_X[1] * 8 // 256 + 3 <= x1,
           y0 + 2 <= world.MAP_Y[0] * 8 // 256, world.MAP_Y[1] * 8 // 256 + 3 <= y1],
          [True] * 4)
except Exception:
    import traceback
    fails.append("map tiles check crashed:\n" + traceback.format_exc())


# --- the global map's scroll box (patch 13) --------------------------------
# The wrapper on DisplayLandscape.drawArea runs against a model of the
# original (DisplayLandscape.as:29-59) and of ViewFrame's box, bounds and
# drag (ViewFrame.as:63, 89-103, 185-192, 259-329), at Abri (cell 5850,1860
# in tile 182,58, where the owner dragged the map into the grey), at the
# Meroe mine (5943,2110 in tile 185,65, where his missing.log was written)
# and at every corner and edge of the rectangle the server keeps the player
# in (world.MAP_X, MAP_Y).
TILE = 256
CELL = 8                        # px a cell at the full scale (mapScale)
ABRI = (5850, 1860)
MINE = (5943, 2110)
WINDOWS = (("1280x1024", (1280, 1024)), ("1920x1080", (1920, 1080)),
           ("2560x1440", (2560, 1440)),
           ("owner's setting, smallest", (1586, 1224)),     # n = 4, m = 3
           ("owner's setting, largest", (2097, 1735)),
           ("3840x2160", (3840, 2160)))
_X0, _X1 = world.MAP_X
_Y0, _Y1 = world.MAP_Y
_XM, _YM = (_X0 + _X1) // 2, (_Y0 + _Y1) // 2
CORNERS = (("north-west corner", (_X0, _Y0)), ("north edge", (_XM, _Y0)),
           ("north-east corner", (_X1, _Y0)), ("west edge", (_X0, _YM)),
           ("middle", (_XM, _YM)), ("east edge", (_X1, _YM)),
           ("south-west corner", (_X0, _Y1)), ("south edge", (_XM, _Y1)),
           ("south-east corner", (_X1, _Y1)))
PLACES = (("Abri", ABRI), ("the Meroe mine", MINE)) + CORNERS
# A picture narrower than the 3840x2160 frame both ways, 10 x 7 tiles round
# Abri: the game's tiles never are, so only this reaches the centring.
NARROW = {"full": (180, 54, 190, 61), "small": w.MAP_TILES["small"]}


def original_draw_area(this, ui, x, y):
    """drawArea as main.swf has it: sets the five-tile box and returns the
    block of tiles it asks for, (first, last column, first, last row)."""
    s = this["cellSize"]
    cx = math.floor(this["mapScale"] * x / s)
    cy = math.floor(this["mapScale"] * y / s)
    size = ui["getFrameSize"]()
    n = math.floor(0.5 * size["width"] / s) + 1
    m = math.floor(0.5 * size["height"] / s) + 1
    ui["globalMapFrame"]["setScrollArea"]((cx - 2) * s, (cy - 2) * s, 5 * s, 5 * s)
    return cx - n, cx + n + 1, cy - m, cy + m + 1


def draw_area(window, cell=ABRI, scale=8, stroke=0, body=None):
    """The patched drawArea in a window: every box set, in order, the block
    asked for and the mask. The frame is the window less 50 x 200
    (GlobalMapInterface.resizeStage); drawMask's stroke may make the mask
    one pixel larger. body is the wrapper, fn_map_scroll() by default."""
    fw, fh = window[0] - 50, window[1] - 200
    boxes, asked = [], []
    mask = (fw + stroke, fh + stroke)
    frame = dict(mask_mc=dict(_width=mask[0], _height=mask[1]),
                 setScrollArea=lambda *box: boxes.append(box))
    ui = dict(getFrameSize=lambda: dict(width=fw, height=fh), globalMapFrame=frame)
    this = dict(cellSize=TILE, mapScale=scale, mapScaleType="full" if scale == 8 else "small")
    this["__mapScrollOrig"] = lambda x, y, centerPers: asked.append(
        original_draw_area(this, ui, x, y))
    env = dict(this=this, x=cell[0], y=cell[1], centerPers=None,
               Math=dict(floor=math.floor, min=min, max=max),
               lol=dict(core=dict(SceneShifter=dict(gmapScreen=ui))))
    execute((body or w.fn_map_scroll()).assemble(), env, returns=False)
    return boxes, asked[0], mask


def original_only(window, cell):
    """The same without the patch: the original's box, its block, the mask."""
    fw, fh = window[0] - 50, window[1] - 200
    boxes = []
    ui = dict(getFrameSize=lambda: dict(width=fw, height=fh),
              globalMapFrame=dict(setScrollArea=lambda *box: boxes.append(box)))
    asked = original_draw_area(dict(cellSize=TILE, mapScale=8), ui, *cell)
    return boxes[0], asked, (fw, fh)


def frame_range(box, mask):
    """Where ViewFrame lets cont_mc stand, (left, right, top, bottom)
    (ViewFrame.as:89-103, 298-329); startDrag gets these as they are."""
    x, y, bw, bh = box
    return mask[0] - (x + bw), -x, mask[1] - (y + bh), -y


def views(box, mask, asked, player):
    """Where ViewFrame lets the view stand with this box, as its top-left in
    map pixels: centred on the player's cell (_centerPoint, which centerChar
    asks for), scrolled as far as it goes towards each corner (scrollX and
    scrollY: edge scrolling), and the corners of the rectangle startDrag
    keeps cont_mc in (a drag). The content holds the tiles asked for."""
    left, right, top, bottom = frame_range(box, mask)
    mw, mh = mask
    content = ((asked[1] - asked[0] + 1) * TILE, (asked[3] - asked[2] + 1) * TILE)

    def bound(cx, cy):
        if left < right and content[0] > mw:            # boundOX
            cx = left if cx < left else math.ceil(right) if cx > right else cx
        if content[1] > mh:                             # boundOY
            cy = math.floor(top) if cy < top else math.ceil(bottom) if cy > bottom else cy
        return -cx, -cy
    centred = bound(mw / 2 - player[0], mh / 2 - player[1])
    scrolled = [bound(sx, sy) for sx in (-99999, 99999) for sy in (-99999, 99999)]
    dragged = [(-cx, -cy) for cx in (left, right) for cy in (top, bottom)]
    return centred, scrolled, dragged


def faults(tiles=None, body=None, windows=WINDOWS, places=PLACES):
    """What is wrong with the view the wrapper leaves at each window, stroke
    and place, as (window, stroke, place, axis, what); empty when nothing is.

    On an axis whose mask is five tiles wide or more the block asked for
    keeps the original's size and the player's tile; it is the original's
    block where that lies on the picture and else lies on it, when the
    picture is wide enough. A narrower mask keeps the original's block and
    five tiles. Where the picture is wider than the mask, the view --
    centred, scrolled to any corner, dragged anywhere -- shows nothing past
    the picture or the tiles asked for, and centres on the player as far
    as those let it. Where it is no wider, the view stands centred on it
    within two pixels (the box's play, and half a pixel of an odd mask).
    Everywhere the drag rectangle is the right way round and the player's
    cell is in the centred view."""
    picture = (tiles or w.MAP_TILES)["full"]
    out = []
    for wname, window in windows:
        frame = (window[0] - 50, window[1] - 200)
        for stroke in (0, 1):
            for pname, cell in places:
                boxes, asked, mask = draw_area(window, cell, stroke=stroke, body=body)
                player = (cell[0] * CELL, cell[1] * CELL)
                centred, scrolled, dragged = views(boxes[-1], mask, asked, player)
                left, right, top, bottom = frame_range(boxes[-1], mask)
                for k, (axis, before, after) in enumerate((("X", "west", "east"),
                                                           ("Y", "north", "south"))):
                    def fault(what):
                        out.append((wname, stroke, pname, axis, what))
                    size, p = mask[k], player[k]
                    c = p // TILE
                    lo, hi = picture[k], picture[2 + k]
                    first, last = asked[2 * k], asked[2 * k + 1]
                    n = math.floor(0.5 * frame[k] / TILE) + 1
                    if last + 1 - first != 2 * n + 2:
                        fault("asks for %d tiles, not %d" % (last + 1 - first, 2 * n + 2))
                    if not first <= c <= last:
                        fault("does not ask for the player's tile %d" % c)
                    if size < 5 * TILE or (lo <= c - n and c + n + 2 <= hi):
                        if first != c - n:
                            fault("asks from tile %d, the original from %d" % (first, c - n))
                    elif 2 * n + 2 <= hi - lo and not lo <= first <= last < hi:
                        fault("asks for tiles %d..%d, off the picture" % (first, last))
                    a0, a1 = (c - 2, c + 3) if size < 5 * TILE else (first, last + 1)
                    r0, r1 = max(lo, a0) * TILE, min(hi, a1) * TILE
                    seen = [v[k] for v in [centred] + scrolled + dragged]
                    if (hi - lo) * TILE > size:
                        if r1 - r0 < size:
                            fault("the tiles there and asked for, %d px, are narrower "
                                  "than the mask, %d" % (r1 - r0, size))
                        past = (max([r0 - v for v in seen] + [0]),
                                max([v + size - r1 for v in seen] + [0]))
                        if past != (0, 0):
                            fault("the view runs %s px %s, %s px %s past the tiles there "
                                  "and asked for" % (past[0], before, past[1], after))
                        want = min(max(p - size / 2, r0), r1 - size)
                        if centred[k] != want:
                            fault("centred at %s, not %s" % (centred[k], want))
                    else:
                        off = max(abs(v - (r0 + r1 - size) / 2) for v in seen)
                        if off > 2:
                            fault("the view stands %s px off the middle of a picture "
                                  "no wider than the mask" % off)
                    if not (left < right if k == 0 else top < bottom):
                        fault("the drag rectangle is empty or inside out")
                    if not centred[k] <= p <= p + CELL <= centred[k] + size:
                        fault("the player's cell is out of the centred view")
    return out


try:
    check("map box: at Abri, the Meroe mine and every corner and edge of the world, "
          "in every window and with either mask, the view stays on tiles that are "
          "there and were asked for and centres on the player as far as they let it",
          faults(), [])
    check("map box, a picture narrower than the frame (10 x 7 tiles at Abri): the "
          "view stands centred on it, and the bounds still act",
          faults(NARROW, w.fn_map_scroll(NARROW), places=(("Abri", ABRI),)), [])

    # The numbers at Abri: the box (x, y, w, h) and the tiles asked for. The
    # original's five tiles from column 180 and row 56 in the 1280x1024
    # window; columns from 180, the picture's west edge, wherever the block
    # is taken; rows as asked, where nothing reaches the north or the south.
    want = {"1280x1024": ((46080, 14336, 1280, 1280), (179, 186, 56, 61)),
            "1920x1080": ((46080, 14336, 2560, 1280), (180, 189, 56, 61)),
            "2560x1440": ((46080, 14336, 3072, 1280), (180, 191, 55, 62)),
            "owner's setting, smallest": ((46080, 14336, 2560, 1280), (180, 189, 55, 62)),
            "owner's setting, largest": ((46080, 14080, 2560, 2048), (180, 189, 55, 62)),
            "3840x2160": ((46080, 13824, 4608, 2560), (180, 197, 54, 63))}
    for name, window in WINDOWS:
        boxes, asked, _ = draw_area(window, ABRI)
        check("map box, %s, at Abri: two boxes set, then (x, y, w, h), and the tiles "
              "asked for" % name, (len(boxes), boxes[-1], asked), (2,) + want[name])
    # ... and the corners at 3840x2160, where the block is moved most.
    want = {"north-west corner": ((46080, 12288, 4608, 2560), (180, 197, 48, 57)),
            "north-east corner": ((47360, 12288, 4608, 2560), (185, 202, 48, 57)),
            "south-west corner": ((46080, 15104, 4608, 2560), (180, 197, 59, 68)),
            "south-east corner": ((47360, 15104, 4608, 2560), (185, 202, 59, 68))}
    for name, cell in CORNERS:
        if name in want:
            boxes, asked, _ = draw_area((3840, 2160), cell)
            check("map box, 3840x2160, at the %s: the box and the tiles asked for, "
                  "all on the picture" % name, (boxes[-1], asked), want[name])

    # Below 1330 x 1480 nothing changes: the original's five tiles, twice.
    five = lambda cell: tuple((cell[k] * CELL // TILE - 2) * TILE for k in (0, 1)) + (5 * TILE,) * 2
    check("map box, 1280x1024 and 1329x1479: at every place both calls set the "
          "original's numbers",
          [(name, window) for name, cell in PLACES for window in ((1280, 1024), (1329, 1479))
           if draw_area(window, cell)[0] != [five(cell)] * 2], [])
    # The switch is boundOX's own test: the mask against five tiles.
    check("map box at the edge: a 1280 px frame (window 1330) takes the block, "
          "1279 takes it only when the stroke makes the mask 1280",
          [draw_area((1330, 1024), MINE)[0][-1][::2],
           draw_area((1329, 1024), MINE)[0][-1][::2],
           draw_area((1329, 1024), MINE, stroke=1)[0][-1][::2]],
          [(182 * TILE, 8 * TILE), (183 * TILE, 5 * TILE), (182 * TILE, 8 * TILE)])
    # The picture narrower than the frame: centred, 2 px of play so that
    # left < right, at ((180 + 190) * 256 - 3790) / 2 - 1 and so on.
    check("map box, a 10 x 7 picture at Abri, 3840x2160: the box is the mask and "
          "2 px, centred on the picture",
          draw_area((3840, 2160), ABRI, body=w.fn_map_scroll(NARROW))[0][-1],
          (45464, 13739, 3792, 1962))
    # The same picture exactly the frame's size: 2610x1992 makes a 2560 x
    # 1792 frame, 10 x 7 tiles. A box the mask's width leaves left == right,
    # where boundOX idles (ViewFrame.as:264) and edge scrolling runs off for
    # good, and the drag rectangle is a line: centred like a narrower one
    # (centring only a narrower one, the view ran 146079 px off here).
    exact = (("2610x1992", (2610, 1992)),)
    check("map box, a picture exactly the frame's size: centred, and the bounds "
          "still act", faults(NARROW, w.fn_map_scroll(NARROW), windows=exact,
                              places=(("Abri", ABRI),)), [])
    check("map box, a picture exactly the frame's size: the box is the mask and 2 px",
          [draw_area((2610, 1992), ABRI, stroke=s, body=w.fn_map_scroll(NARROW))[0][-1]
           for s in (0, 1)],
          [(46079, 13823, 2562, 1794), (46078, 13822, 2563, 1795)])
    # A player off the picture (one that lies east and south of Abri): no
    # edges, so in the owner's window the original asks for the block it
    # always did and the box is that block, columns 178..187, and the
    # original's five rows, as before the picture was known.
    off = {"full": (190, 60, 200, 66), "small": w.MAP_TILES["small"]}
    check("map box, the player off the picture: nothing moved or cut",
          draw_area((1586, 1224), ABRI, body=w.fn_map_scroll(off))[:2],
          ([(46080, 14336, 1280, 1280), (45568, 14336, 2560, 1280)], (178, 187, 55, 62)))
    # The small scale is 1 px a cell, tiles of 256 px too: tile 23,8, and
    # 32 columns, so a column 32 would be the next row's first tile.
    check("map box, small scale, 3840x2160: the block moved off column 32",
          draw_area((3840, 2160), MINE, scale=1)[:2],
          ([(20 * TILE, 6 * TILE, 5 * TILE, 5 * TILE), (14 * TILE, 4 * TILE, 18 * TILE, 10 * TILE)],
           (14, 31, 4, 13)))

    # A resize. GlobalMapInterface.init sizes the frame (resizeStage) and
    # then sets the scale, which draws the map; later the window is resized
    # on the map, or the chat is (chatRes, through resizeStage too). The
    # model runs fn_map_resize with the original resizeStage as setSize
    # (the window less 50 x 200), and the landscape's drawArea as
    # fn_map_scroll against the original's model. Per window: every call
    # the frame got after the original, the tiles asked for last, the mask.
    def map_session(windows, cell=ABRI, hook=None):
        calls, asked, size = [], [], {}
        frame = dict(mask_mc={}, setScrollArea=lambda *box: calls.append(box),
                     boundOX=lambda: calls.append("boundOX"),
                     boundOY=lambda: calls.append("boundOY"))
        ui = dict(getFrameSize=lambda: dict(size), globalMapFrame=frame)
        land = dict(cellSize=TILE, mapScale=8, mapScaleType="full")
        land["__mapScrollOrig"] = lambda x, y, centerPers: asked.append(
            original_draw_area(land, ui, x, y))
        land["drawArea"] = lambda x, y: execute(
            w.fn_map_scroll().assemble(),
            dict(this=land, x=x, y=y, centerPers=None,
                 Math=dict(floor=math.floor, min=min, max=max),
                 lol=dict(core=dict(SceneShifter=dict(gmapScreen=ui)))), returns=False)

        def set_size(obj):
            size.update(width=obj["w"] - 50, height=obj["h"] - 200)
            frame["mask_mc"].update(_width=size["width"], _height=size["height"])
        this = dict(displayMap=dict(landscape=land), globalMapFrame=frame,
                    __mapResizeOrig=set_size)
        out = []
        for k, window in enumerate(windows):
            del calls[:]
            execute((hook or w.fn_map_resize()).assemble(),
                    dict(this=this, obj=dict(w=window[0], h=window[1])), returns=False)
            after = list(calls)
            if k == 0:
                land["drawArea"](*cell)          # the scale, after init
            out.append((after, asked[-1] if asked else None,
                        (size["width"], size["height"])))
        return out

    opened, widened, narrowed = map_session(((1280, 1024), (2560, 1440), (1280, 1024)))
    check("map resize: init's resizeStage, before the first drawArea, adds nothing",
          opened[0], [])
    big, small = draw_area((2560, 1440)), draw_area((1280, 1024))
    check("map resize: widened on the map, 1280x1024 to 2560x1440 at Abri, the "
          "map is drawn again for the new frame -- its box and tiles -- and the "
          "view bounded in it",
          widened[:2], ([big[0][0], big[0][1], "boundOX", "boundOY"], big[1]))
    check("map resize: back to 1280x1024, the original's five tiles again",
          narrowed[:2], ([small[0][0], small[0][1], "boundOX", "boundOY"], small[1]))
    # The original's resizeStage alone, no hook: the box stays the five
    # tiles of the 1280x1024 frame, narrower than the new 2510 px mask, so
    # the drag rectangle is inside out and boundOX idles.
    alone = w.Asm()
    alone.var("obj").push(1).var("this").push("__mapResizeOrig").op("callmethod").op("pop")
    _, stale = map_session(((1280, 1024), (2560, 1440)), hook=alone)
    left, right = frame_range(small[0][-1], stale[2])[:2]
    check("broken: without the resize hook the widened frame keeps the old box, "
          "the drag rectangle inside out",
          (stale[0], left < right), ([], False))
    # The map gone (GlobalMapInterface.kill deletes displayMap, and its
    # resizeStage listener stays registered): the original, and nothing more.
    gone = []
    execute(w.fn_map_resize().assemble(),
            dict(this=dict(__mapResizeOrig=gone.append), obj=dict(w=2560, h=1440)),
            returns=False)
    check("map resize: once the map is killed, only the original runs",
          gone, [dict(w=2560, h=1440)])

    # Regression controls: the original's box alone, measured the same way.
    box, asked, mask = original_only((1920, 1080), MINE)
    _, scrolled, _ = views(box, mask, asked, (MINE[0] * CELL, MINE[1] * CELL))
    check("original box, 1920x1080: edge scrolling runs off the tiles asked for",
          all(v[0] < asked[0] * TILE or v[0] + mask[0] > (asked[1] + 1) * TILE
              for v in scrolled), True)
    box, asked, mask = original_only((3840, 2160), MINE)
    centred, _, _ = views(box, mask, asked, (MINE[0] * CELL, MINE[1] * CELL))
    check("original box, 3840x2160: the view sits 168 px above the rows asked for",
          asked[2] * TILE - centred[1], 168)

    # Three broken wrappers, each caught. The box the block asked for, the
    # picture unknown (the patch as 0a11de7 had it): at Abri the owner's
    # window drags 512 px into the grey, columns 178 and 179.
    OPEN = {scale: (-w.MAP_OPEN, -w.MAP_OPEN, w.MAP_OPEN, w.MAP_OPEN) for scale in w.MAP_TILES}
    caught = faults(body=w.fn_map_scroll(OPEN))
    check("broken: the box the block asked for (0a11de7) is caught at Abri in the "
          "owner's window, 512 px into the grey",
          ("owner's setting, smallest", 0, "Abri", "X",
           "the view runs 512 px west, 0 px east past the tiles there and asked for")
          in caught, True)
    # The block cut down to the picture but not moved onto it: at Abri a
    # 2560 frame keeps 9 columns, 2304 px, narrower than its 2510, and the
    # view centred on them shows 104 px of grey to the west and 104 px of
    # column 189, never asked for, to the east.
    caught = faults(body=w.fn_map_scroll(shift=False))
    check("broken: the block cut to the picture, not moved onto it, is caught at "
          "Abri in 2560x1440",
          [what for wname, stroke, place, axis, what in caught
           if (wname, stroke, place, axis) == ("2560x1440", 0, "Abri", "X")],
          ["asks for tiles 177..188, off the picture",
           "the tiles there and asked for, 2304 px, are narrower than the mask, 2510",
           "the view runs 104 px west, 104 px east past the tiles there and asked for",
           "centred at 45976, not 45874"])
    # No centring: a picture narrower than the frame leaves the box inside
    # out, boundOX idle (edge scrolling runs off for good) and boundOY
    # throwing the view between two edges 168 px apart.
    caught = faults(NARROW, w.fn_map_scroll(NARROW, centre=False), places=(("Abri", ABRI),))
    check("broken: no centring is caught on the narrow picture at 3840x2160",
          sorted({(wname, axis, what) for wname, stroke, place, axis, what in caught
                  if stroke == 0}),
          [("3840x2160", "X", "the drag rectangle is empty or inside out"),
           ("3840x2160", "X", "the view stands 145464.0 px off the middle of a "
                              "picture no wider than the mask"),
           ("3840x2160", "Y", "the drag rectangle is empty or inside out"),
           ("3840x2160", "Y", "the view stands 84.0 px off the middle of a "
                              "picture no wider than the mask")])
except Exception:
    import traceback
    fails.append("map scroll box check crashed:\n" + traceback.format_exc())


def check_container(label, version, body):
    """The same file round trip for the fixture and the optional real client."""
    original = w.split_tags(body)
    patched = w.inject(list(original))
    w.patch_ceiling(patched, 3840, 2160)
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "main.swf")
        w.write_swf(path, version, w.join_tags(body[:w.header_len(body)], patched))
        check(label + ": the saved client verifies its code and dimensions",
              w.verify(path, 3840, 2160)[1] > 0, True)
        _, out = w.read_swf(path)
        actual = w.split_tags(out)
        check(label + ": applying the patch twice does not stack HUDs or wrappers",
              w.inject(actual), actual)
        mine = [t[1] for t in actual if t[0] == 12 and w.MARK.encode() in t[1]]
        check(label + ": the saved DoAction wraps DisplayLandscape.drawArea",
              [name for name in (b"globmap", b"DisplayLandscape", b"drawArea",
                                 b"__mapScrollOrig", b"setScrollArea", b"mask_mc",
                                 b"mapScaleType")
               if name not in mine[0]], [])
        # Both ceilings are normalized to the same value; everything else
        # except our marked DoAction and new bitmap must remain identical.
        w.patch_ceiling(original, 3840, 2160)
        keep = lambda tags: [t for t in w.without_online_art(tags)
                             if not (t[0] == 12 and w.MARK.encode() in t[1])]
        check(label + ": the patch preserves all artwork and unrelated scripts",
              keep(actual) == keep(original), True)


def fixture():
    """Minimal SWF tags, including a nested bitmap whose ID must stay reserved.

    The class-init action has the compiler's ConstantPool and Push register,
    constant8, integer / SetMember shape documented by patch_ceiling. It is
    only a container fixture, not an executable substitute for the client.
    """
    # RECT with one-bit coordinates, 25 fps, one frame.
    head = b"\x08\x00\x00\x19\x01\x00"
    pool = b"\x03\x00maxW\x00maxH\x00setMCSize\x00"
    actions = b"\x88" + struct.pack("<H", len(pool)) + pool
    for index, value in enumerate((1280, 1024)):
        actions += b"\x96\x09\x00\x04\x02\x08" + bytes([index])
        actions += b"\x07" + struct.pack("<i", value) + b"\x4f"
    actions += b"\x00"
    bitmap = (21, b"\x02\x00" + w.ONLINE_ASSET.read_bytes(), True)
    sprite = b"\x01\x00\x01\x00" + w.join_tags(
        b"", [bitmap, (1, b"", False), (0, b"", False)])
    # The settings window's frame and texture, which the online list
    # borrows by ID: empty shapes with a one-bit RECT are enough here.
    shapes = [(2, struct.pack("<H", ident) + b"\x08\x00\x00\x00\x00\x00", True)
              for ident in (581, 596)]
    tags = [(9, b"\x12\x34\x56", True)] + shapes + [
            (39, sprite, True),
            (56, b"\x01\x00\x02\x00fixtureIcon\x00", False),
            (59, b"\x01\x00" + actions, True),
            (12, b"\x07\x00", False),
            (1, b"", False), (0, b"", False)]
    return head, tags


# --- SWF fixture: always, including CI without the client ------------------
try:
    head, tags = fixture()
    patched = w.inject(list(tags))
    check("the HUD bitmap avoids both sprite and nested bitmap IDs",
          [struct.unpack_from("<H", payload)[0]
           for code, payload, _ in patched if code == 21], [3])
    check_container("fixture", 8, w.join_tags(head, tags))
except Exception:
    import traceback
    fails.append("SWF fixture check crashed:\n" + traceback.format_exc())


# --- real SWF container: the full client, when installed -------------------
res = os.environ.get("LAVA_RES", os.path.join(os.path.dirname(HERE), "..", "client", "res"))
src = os.path.join(res, "main.swf")
try:
    if os.path.exists(src):
        version, body = w.read_swf(src)
        check_container("real client", version, body)
        # Patch 13 wraps a prototype that frame 1 has to have built by the
        # time the injected DoAction runs, and reads these names from it.
        real = w.inject(w.split_tags(body))
        ours = next(k for k, t in enumerate(real) if t[0] == 12 and w.MARK.encode() in t[1])
        landscape = [k for k, (code, payload, _) in enumerate(real) if code == 59
                     and {"DisplayLandscape", "drawArea", "setScrollArea", "getFrameSize",
                          "gmapScreen", "globalMapFrame", "cellSize", "mapScale",
                          "mapScaleType", "full"}
                     <= set(w.constant_pool(payload[2:]))]
        check("real client: DisplayLandscape, with every name the scroll box "
              "wrapper reads, is built in frame 1 before the injected code",
              [k < ours for k in landscape], [True])
        # ... and the resize hook's names, each in its class's own code.
        pools = [set(w.constant_pool(payload[2:])) for code, payload, _ in real[:ours]
                 if code == 59]
        check("real client: the names the map's resize hook reads are in frame 1",
              [names for names in ({"GlobalMapInterface", "resizeStage", "displayMap",
                                    "globalMapFrame"},
                                   {"DisplayGlobalMap", "landscape"},
                                   {"ViewFrame", "boundOX", "boundOY"})
               if not any(names <= pool for pool in pools)], [])
    else:
        print("  --  main.swf not found at %s; real-client checks skipped;"
              " fixture checks ran above" % res)
except Exception:
    import traceback
    fails.append("SWF check crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("widescreen OK")
