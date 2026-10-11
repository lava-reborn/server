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
         "__mapScrollOrig")                            # global map scroll box
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
                else:
                    raise AssertionError("unexpected push type: %s" % kind)
        elif op == 0x1C:
            stack.append(env[stack.pop()])
        elif op == 0x4E:
            key, obj = stack.pop(), stack.pop()
            stack.append(obj.get(key))
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


# --- the global map's scroll box (patch 13) --------------------------------
# The wrapper on DisplayLandscape.drawArea runs against a model of the
# original (DisplayLandscape.as:29-59) and of ViewFrame's box and bounds
# (ViewFrame.as:89-103, 185-192, 259-329). The player stands at the Meroe
# mine, cell 5943,2110 in tile 185,65, where the owner's missing.log was
# written (columns 181..190, rows 62..69: n = 4, m = 3).
TILE = 256
MINE = (5943, 2110)
WINDOWS = (("1280x1024", (1280, 1024)), ("1920x1080", (1920, 1080)),
           ("owner's setting, smallest", (1586, 1224)),
           ("owner's setting, largest", (2097, 1735)),
           ("3840x2160", (3840, 2160)))


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


def draw_area(window, cell=MINE, scale=8, stroke=0):
    """The patched drawArea in a window: every box set, in order, the block
    asked for and the mask. The frame is the window less 50 x 200
    (GlobalMapInterface.resizeStage); drawMask's stroke may make the mask
    one pixel larger."""
    fw, fh = window[0] - 50, window[1] - 200
    boxes, asked = [], []
    mask = (fw + stroke, fh + stroke)
    frame = dict(mask_mc=dict(_width=mask[0], _height=mask[1]),
                 setScrollArea=lambda *box: boxes.append(box))
    ui = dict(getFrameSize=lambda: dict(width=fw, height=fh), globalMapFrame=frame)
    this = dict(cellSize=TILE, mapScale=scale)
    this["__mapScrollOrig"] = lambda x, y, centerPers: asked.append(
        original_draw_area(this, ui, x, y))
    env = dict(this=this, x=cell[0], y=cell[1], centerPers=None,
               Math=dict(floor=math.floor),
               lol=dict(core=dict(SceneShifter=dict(gmapScreen=ui))))
    execute(w.fn_map_scroll().assemble(), env, returns=False)
    return boxes, asked[0], mask


def views(box, mask, asked):
    """Where ViewFrame lets the view stand with this box, as its top-left in
    map pixels: centred on the player anywhere in the tile (_centerPoint),
    then scrolled as far as it goes towards each corner (scrollX/scrollY:
    edge scrolling; a drag gets the same rectangle). The content holds at
    least the tiles asked for."""
    x, y, bw, bh = box
    mw, mh = mask
    left, right, top, bottom = mw - (x + bw), -x, mh - (y + bh), -y
    content = ((asked[1] - asked[0] + 1) * TILE, (asked[3] - asked[2] + 1) * TILE)

    def bound(cx, cy):
        if left < right and content[0] > mw:            # boundOX
            cx = left if cx < left else math.ceil(right) if cx > right else cx
        if content[1] > mh:                             # boundOY
            cy = math.floor(top) if cy < top else math.ceil(bottom) if cy > bottom else cy
        return -cx, -cy
    tx, ty = asked[0] + (asked[1] - asked[0] - 1) // 2, asked[2] + (asked[3] - asked[2] - 1) // 2
    players = [(px, py) for px in (tx * TILE, tx * TILE + 8 * 23, tx * TILE + 248)
               for py in (ty * TILE, ty * TILE + 8 * 30, ty * TILE + 248)]
    centred = [bound(mw / 2 - px, mh / 2 - py) for px, py in players]
    scrolled = [bound(sx, sy) for sx in (-99999, 99999) for sy in (-99999, 99999)]
    return players, centred, scrolled


def beyond(view, mask, asked):
    """Pixels of the view past the tiles asked for: west, east, north, south."""
    return (max(0, asked[0] * TILE - view[0]),
            max(0, view[0] + mask[0] - (asked[1] + 1) * TILE),
            max(0, asked[2] * TILE - view[1]),
            max(0, view[1] + mask[1] - (asked[3] + 1) * TILE))


try:
    want = {"1280x1024": ((46848, 16128, 1280, 1280), (182, 189, 63, 68)),
            "1920x1080": ((46336, 16128, 2560, 1280), (181, 190, 63, 68)),
            "owner's setting, smallest": ((46336, 16128, 2560, 1280), (181, 190, 62, 69)),
            "owner's setting, largest": ((46336, 15872, 2560, 2048), (181, 190, 62, 69)),
            "3840x2160": ((45312, 15616, 4608, 2560), (177, 194, 61, 70))}
    for name, window in WINDOWS:
        for stroke in (0, 1):
            boxes, asked, mask = draw_area(window, stroke=stroke)
            check("map box, %s, mask +%d: the original's box, then (x, y, w, h) at the "
                  "Meroe mine, and the tiles asked for" % (name, stroke),
                  (len(boxes), boxes[0], boxes[-1], asked),
                  (2, (46848, 16128, 1280, 1280)) + want[name])
            players, centred, scrolled = views(boxes[-1], mask, asked)
            _, before, _ = views(boxes[0], mask, asked)
            block = [boxes[-1][2 + k] != 5 * TILE for k in (0, 1)]
            check("map box, %s, mask +%d: centred anywhere in the tile, the view is on "
                  "the player along a block, where the original puts it along five "
                  "tiles" % (name, stroke), centred,
                  [tuple(p[k] - mask[k] / 2 if block[k] else b[k] for k in (0, 1))
                   for p, b in zip(players, before)])
            check("map box, %s, mask +%d: centred or scrolled to any corner, the view "
                  "shows only tiles asked for" % (name, stroke),
                  [beyond(v, mask, asked) for v in centred + scrolled
                   if beyond(v, mask, asked) != (0, 0, 0, 0)], [])

    check("map box, 1280x1024: both calls set exactly the original's numbers",
          draw_area((1280, 1024))[0], [(46848, 16128, 1280, 1280)] * 2)
    check("map box, 1920x1080: wider than five tiles, so the ten columns asked for; "
          "the rows keep the original's five",
          draw_area((1920, 1080))[0][-1][2:], (10 * TILE, 5 * TILE))
    check("map box, 3840x2160: both axes take the block, 18 x 10 tiles",
          draw_area((3840, 2160))[0][-1][2:], (18 * TILE, 10 * TILE))

    # Regression control: the original's box alone, measured the same way.
    _, asked, mask = draw_area((1920, 1080))
    _, _, scrolled = views((46848, 16128, 1280, 1280), mask, asked)
    check("original box, 1920x1080: edge scrolling runs off the tiles asked for",
          all(beyond(v, mask, asked)[:2] != (0, 0) for v in scrolled), True)
    _, asked, mask = draw_area((3840, 2160))
    _, centred, _ = views((46848, 16128, 1280, 1280), mask, asked)
    check("original box, 3840x2160: the view sits 168 px above the rows asked for",
          sorted({beyond(v, mask, asked)[2] for v in centred}), [168])

    # The switch is boundOX's own test: the mask against five tiles.
    check("map box at the edge: a 1280 px frame (window 1330) takes the block, "
          "1279 takes it only when the stroke makes the mask 1280",
          [draw_area((1330, 1024))[0][-1][::2],
           draw_area((1329, 1024))[0][-1][::2],
           draw_area((1329, 1024), stroke=1)[0][-1][::2]],
          [(182 * TILE, 8 * TILE), (183 * TILE, 5 * TILE), (182 * TILE, 8 * TILE)])
    # The small scale is 1 px a cell, tiles of 256 px too: tile 23,8.
    check("map box, small scale, 3840x2160: the block asked for",
          draw_area((3840, 2160), scale=1)[:2],
          ([(21 * TILE, 6 * TILE, 5 * TILE, 5 * TILE), (15 * TILE, 4 * TILE, 18 * TILE, 10 * TILE)],
           (15, 32, 4, 13)))
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
                                 b"__mapScrollOrig", b"setScrollArea", b"mask_mc")
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
                          "gmapScreen", "globalMapFrame", "cellSize", "mapScale"}
                     <= set(w.constant_pool(payload[2:]))]
        check("real client: DisplayLandscape, with every name the scroll box "
              "wrapper reads, is built in frame 1 before the injected code",
              [k < ours for k in landscape], [True])
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
