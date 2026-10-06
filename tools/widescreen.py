#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A main.swf that lays itself out across a wide window and keeps its frame whole.

    python3 tools/widescreen.py <main.swf> <out.swf> [--max 3840x2160]
    python3 tools/widescreen.py <main.swf> --check

Client patches applied without altering the original artwork:

1. The layout ceiling. SceneShifter.setMCSize clamps the size it hands every
   interface to maxW x maxH = 1280 x 1024 (SceneShifter.as:43-44). Past that
   the scene stops growing and sits in the middle of a black field. The two
   integer pushes behind those fields are rewritten -- found through the
   class's own constant pool, not by offset, so the patch refuses a file it
   does not recognise instead of writing into the wrong place.

2. The frame. Past 1280 the interface does lay itself out to the window
   (LocationInterface.resizeStage, GlobalMapInterface.resizeStage), but the
   art was drawn for 1280 at most: the top bar is two 640-pixel strips of pipe
   masked to half the width each, and the bottom bar is a 1010-pixel corner
   piece whose plate and pipe run out 820 and 520 pixels from the right edge.
   On a 2560 window that leaves black holes between the pieces.

   The holes are tiled with the pieces' own art. On the first resize a slice
   of plain pipe or plate is copied out of the piece into a BitmapData, and
   an empty clip underneath the piece's own content is filled with it,
   repeated, from where the art ends to where it has to reach. The clips live
   inside the pieces, so the pieces' masks, mirroring and depths apply to the
   fill exactly as they do to the art. At 1280 and below nothing is drawn and
   the client looks as it always did.

   The code goes in as one DoAction at the end of the first frame, after the
   classes' DoInitAction tags: it wraps resizeStage on both prototypes. That
   has to happen before any interface is built, because
   LEventDispatcher.addEventListener stores handler[event] at the moment of
   registration, not a name to look up later.

3. The doubled «+N опыта». SpecSkillMessages, the service that prints a
   skill's experience, is built with every Gamer and subscribes to the
   skills five seconds later, on a Timeout nobody cancels
   (SpecSkillMessages.as:13-30). A Gamer killed inside those five seconds --
   a location left for the map within them -- kills a service that has not
   subscribed yet, so its kill() removes nothing; the Timeout then fires and
   subscribes the orphan to the skills of whoever is master.gamer by then,
   for good. Every such quick visit adds one more listener, and one more
   copy of every «Медицина: +74 опыта» from then on (a player counted three).

   The same wrapping as the frame's, on SpecSkillMessages.prototype.init:
   the original runs only while master.gamer.ssMessages is this very
   service, which a Gamer's kill() has already deleted for an orphan.

   Initial progress is silent too. PersAttributes.rp_info first loads the
   saved values, then enables its four progress-event forwarders. A saved
   specialization at level one otherwise looks like a gain from zero when
   login takes longer than the service's five-second subscription delay.
   Character redraws still run; subsequent gains and combat queues keep
   their original handlers. Each new character object gets its own baseline.

4. The doubled services. NPC.userInfo pushes «Прописка» onto supportList
   whenever can_set_home is set, and Healer.userInfo pushes «Лечение» after
   it, but the list is made once, in the constructor (NPC.as:19-24, 44-50,
   Healer.as:13-20). The server answers every getInfo with a fresh
   userInfo, so Ибн Сина seen on entering the market and clicked once
   offered two of each.

   The same wrapping again, on NPC.prototype.userInfo: the list starts
   empty, then the original fills it from this frame alone. Healer's
   super.userInfo lands in the wrapper, so its «Лечение» still comes after
   «Прописка», once.

5. A silent «Прописка». Attendance.cmdAck is empty (Attendance.as:46-48):
   the server registers the home and acks it, and the player sees nothing.
   A refusal already shows, through ErrorReport's own cmdAck listener. The
   wrapper on Attendance.prototype.cmdAck puts up the top line the client
   uses for its own notices (ItemActivator.as:82-84), for two seconds, when
   a SET_HOME comes back with res=0.

6. Online players. A compact plate with a people icon, the live count and
   an arrow, just left of the exit button, on both world interfaces. The
   plate is the popup's own dark frame (below), two rows of it with a rivet
   at either end; the icon is the one of data/client/online-panel.png, cut
   out at build time with its plate made transparent; count and arrow are
   muted beige, the arrow down while the list is closed and up while open.
   XMLConnection.Send opts in with hello;online=2; sendNotification caches
   online;count=N;names=|..| before a scene exists and refreshes the count
   when players enter or leave. Resize builds the counter once and anchors
   its right edge; it widens with the count. Below 1200 pixels it uses the
   upper lip of the bar, clear of the gold balance. No timers or per-scene
   connection listeners survive a scene change.

   A click on the counter drops the list of everybody online under it:
   hello;online=2 asks the server for the names with each count. The popup
   is built from the original's own pieces -- the settings window's frame
   (shape 581) and texture (596), exported under new names and sliced into
   nine parts, the hotkey list's scrollPan2, mail_btn for the envelopes,
   closeWindow_btn_ -- in the colours of the settings rows. An envelope or
   a nick hands the name to ChatPan.selectPrivateUserNick, the client's
   own way into a private, which keeps the draft; one already addressed
   to that nick only gets the focus. Every popup has a name of its own and
   is taken down explicitly: the listeners its buttons and scroll pane
   register (EMouse, Key, Mouse) go with it, and one left behind by a
   scene change removes itself on the next click.

7. Gold-only repairs. Item.getProp supplies the gold price converted to afro
   when RepairInterface is open and the requested afro cost is zero. This
   fixes the slot, drag preview, bag labels and both repair-all totals.
   Outside repair, the zero afro price still prevents buying or selling
   gold-only equipment for afro. No item data is modified. Gold payment
   uses Math.round to the nearest hundredth, with the original 0.01 minimum.

8. Location viewports larger than the map. The original ViewFrame bounds
   leave small scenes free to drift outside the viewport. Location frames
   center a short axis and clamp a long one to the declared map bounds.
   An opaque backing keeps the launcher's loading screen out of the gaps.
   SourceLibrary parks its artwork at y=1800; hide the library explicitly
   so large windows cannot expose the stored copies below the interface.

   A location entered straight from another one (a quest way, a caravan,
   /goto) loses its map mask. SceneShifter.locationScene removes the old
   panel and attaches the new one as the same "lp" on the same depth in one
   call; the new ViewFrame's setMask runs, yet by the next frame the player
   no longer clips cont_mc, and the whole map covers the lower-depth chat.
   The script still sees the mask in place. Through the global map the new
   panel comes 100 ms later and keeps its mask. Measured in Flash 32: a
   setMask repeated right after locationScene is lost as well, the same
   call one frame later holds. The wrapper repeats it for two frames.

Every opcode emitted here is read back out of the written file and compared
with what was meant (see verify()) -- the lesson of make_wrapper.py, where an
opcode assembled from memory once sprayed the downloads folder with copies of
main.swf.
"""
import argparse
from pathlib import Path
import struct
import sys
import zlib

MARK = "__wideFrame"            # the injected DoAction is recognised by this

# --- SWF container ----------------------------------------------------------

def read_swf(path):
    data = open(path, "rb").read()
    sig = data[:3]
    if sig not in (b"CWS", b"FWS"):
        raise SystemExit("%s: not an uncompressed or zlib SWF" % path)
    body = zlib.decompress(data[8:]) if sig == b"CWS" else data[8:]
    return data[3], body


def write_swf(path, version, body):
    out = b"CWS" + bytes([version]) + struct.pack("<I", len(body) + 8)
    open(path, "wb").write(out + zlib.compress(body, 9))


def header_len(body):
    nbits = body[0] >> 3
    return (5 + 4 * nbits + 7) // 8 + 4


def split_tags(body):
    """[(code, payload, long_header)] for the top-level tags, End included.

    The header form is kept per tag: some players insist on the long form for
    bitmap tags even when the length would fit in six bits, and a file that
    went in working should come out with every untouched tag byte-identical.
    """
    i, out = header_len(body), []
    while i < len(body):
        (th,) = struct.unpack_from("<H", body, i)
        i += 2
        code, ln = th >> 6, th & 0x3F
        long_header = ln == 0x3F
        if long_header:
            (ln,) = struct.unpack_from("<I", body, i)
            i += 4
        out.append((code, body[i:i + ln], long_header))
        i += ln
        if code == 0:
            break
    return out


def join_tags(head, tags):
    out = bytearray(head)
    for code, payload, long_header in tags:
        if long_header or len(payload) >= 0x3F:
            out += struct.pack("<HI", (code << 6) | 0x3F, len(payload))
        else:
            out += struct.pack("<H", (code << 6) | len(payload))
        out += payload
    return bytes(out)


# --- the layout ceiling -----------------------------------------------------

def constant_pool(actions):
    """The first ConstantPool in an action stream, as a list of strings."""
    i = 0
    while i < len(actions):
        op = actions[i]
        if op < 0x80:
            i += 1
            continue
        (ln,) = struct.unpack_from("<H", actions, i + 1)
        if op == 0x88:
            (n,) = struct.unpack_from("<H", actions, i + 3)
            pool, j = [], i + 5
            for _ in range(n):
                e = actions.index(b"\x00", j)
                pool.append(actions[j:e].decode("utf-8"))
                j = e + 1
            return pool
        i += 3 + ln
    return []


def patch_ceiling(tags, max_w, max_h):
    """Rewrite `var maxW = ...; var maxH = ...` in SceneShifter's class init.

    The compiler emits each field initialiser as one Push of (register 2 --
    the prototype --, constant name, integer value) followed by SetMember.
    Exactly that shape is looked for, and exactly one of each must be found.
    """
    for k, (code, payload, long_header) in enumerate(tags):
        if code != 59:
            continue
        actions = payload[2:]
        pool = constant_pool(actions)
        if "maxW" not in pool or "maxH" not in pool or "setMCSize" not in pool:
            continue
        buf = bytearray(payload)
        done = {}
        for name, value in (("maxW", max_w), ("maxH", max_h)):
            idx = pool.index(name)
            if idx > 0xFF:
                raise SystemExit("constant %s past constant8 range" % name)
            probe = bytes([0x96, 0x09, 0x00, 0x04, 0x02, 0x08, idx, 0x07])
            at = [i for i in range(len(buf)) if buf[i:i + 8] == probe]
            if len(at) != 1:
                raise SystemExit("%s: expected one initialiser, found %d" % (name, len(at)))
            old = struct.unpack_from("<i", buf, at[0] + 8)[0]
            struct.pack_into("<i", buf, at[0] + 8, value)
            done[name] = (old, value)
        tags[k] = (code, bytes(buf), long_header)
        return done
    raise SystemExit("SceneShifter's class init was not found -- not the LAVA client?")


# --- a small AVM1 assembler -------------------------------------------------

class Reg(int):
    """A register reference inside Push."""


UNDEF = object()

OPS = {
    "end": 0x00, "subtract": 0x0B, "multiply": 0x0C, "divide": 0x0D,
    "not": 0x12, "pop": 0x17,
    "getvar": 0x1C, "definelocal": 0x3C, "callfunc": 0x3D, "return": 0x3E,
    "add2": 0x47, "less2": 0x48, "equals2": 0x49, "getmember": 0x4E,
    "setmember": 0x4F, "callmethod": 0x52, "newmethod": 0x53,
    "initarray": 0x42,
}


def push_payload(values):
    out = bytearray()
    for v in values:
        if v is UNDEF:
            out += b"\x03"
        elif v is None:
            out += b"\x02"
        elif isinstance(v, bool):
            out += b"\x05" + bytes([1 if v else 0])
        elif isinstance(v, Reg):
            out += b"\x04" + bytes([int(v)])
        elif isinstance(v, int):
            out += b"\x07" + struct.pack("<i", v)
        elif isinstance(v, str):
            out += b"\x00" + v.encode("utf-8") + b"\x00"
        else:
            raise TypeError(v)
    return bytes(out)


class Asm:
    """Straight-line AVM1 with forward labels and nested functions."""

    def __init__(self):
        self.parts = []            # bytes, or ("branch", op, label)
        self.labels = {}

    def op(self, name):
        self.parts.append(bytes([OPS[name]]))
        return self

    def push(self, *values):
        p = push_payload(values)
        self.parts.append(b"\x96" + struct.pack("<H", len(p)) + p)
        return self

    def var(self, name):
        return self.push(name).op("getvar")

    def member(self, *names):
        for n in names:
            self.push(n).op("getmember")
        return self

    def label(self, name):
        self.labels[name] = len(self.parts)
        self.parts.append(b"")
        return self

    def iftrue(self, label):
        self.parts.append(("branch", 0x9D, label))
        return self

    def function(self, params, body):
        """DefineFunction (0x9B), anonymous: leaves the function on the stack."""
        code = body.assemble()
        p = b"\x00" + struct.pack("<H", len(params))
        for name in params:
            p += name.encode("utf-8") + b"\x00"
        p += struct.pack("<H", len(code))
        self.parts.append(b"\x9B" + struct.pack("<H", len(p)) + p + code)
        return self

    def assemble(self):
        size = [5 if isinstance(x, tuple) else len(x) for x in self.parts]
        offset, at = [], 0
        for s in size:
            offset.append(at)
            at += s
        out = bytearray()
        for k, x in enumerate(self.parts):
            if isinstance(x, tuple):
                _, opcode, label = x
                target = offset[self.labels[label]]
                rel = target - (offset[k] + 5)
                out += bytes([opcode]) + struct.pack("<Hh", 2, rel)
            else:
                out += x
        return bytes(out)


def new(asm, path, cls, argc):
    """new path.cls(<argc arguments already on the stack>)."""
    asm.push(argc)
    first, rest = path[0], path[1:]
    asm.var(first)
    for name in rest:
        asm.member(name)
    return asm.push(cls).op("newmethod")


def call_method(asm, obj_var, method, argc):
    return asm.push(argc).var(obj_var).push(method).op("callmethod").op("pop")


# --- the frame: which slices, and where they go -----------------------------

# Every slice is (x, y, w, h, kind) in the piece's own coordinates. kind 0
# repeats the slice as it is; 1 lays it mirrored and straight in turn along
# x, 2 the same along y. Mirrored pairs join without a seam by construction,
# which is what a painted texture with no period of its own needs. The plate
# has one -- its planks repeat every 300 px, measured on the art -- and is
# repeated as is, in phase with the art, so the joins fall on real plank
# joints the way they do in the original.
PLAIN, MIRROR_X, MIRROR_Y = 0, 1, 2

DESIGN_W = 1280                 # the width the art was drawn for
STRIP_END = 640                 # top strips: the pipe stops here
# The last 120 px of the pipe, laid mirrored first: the fill begins with the
# art's own last column, so even the join where the art ends does not show.
STRIP_SLICE = (STRIP_END - 120, 0, 120, 63, MIRROR_X)
CORNER_PLATE_END = 820          # bottom corner: the plate stops here
CORNER_PIPE_END = 520           # ... and the pipe under it here
PLATE_PERIOD = 300
CORNER_PLATE = (CORNER_PLATE_END % PLATE_PERIOD, 141, PLATE_PERIOD, 31, PLAIN)
CORNER_PIPE = (281, 172, 120, 18, MIRROR_X)
# At 1280 the corner piece covers [270, 1280] and its plate starts at
# 1280 - 820 = 460, under the weapon panel. The fill starts there too, so the
# left half of the bar is built exactly as it is at 1280.
BOTTOM_START = DESIGN_W - CORNER_PLATE_END
# Side posts: 955 px of art from y = 63, and the bottom corners' own posts
# start at h - 339. Where the two ends meet depends on the window's height,
# and both ends fade out over their last rows, so a fill that only bridged
# the measured gap left a dark slit at other heights. It runs instead from
# well inside the art (underneath it: the fill sits below the piece's own
# content) down to where frame_mask stops everything, h - 200 -- under the
# corner, which is drawn on top. Wherever the art is opaque it hides the
# fill; wherever either end fades, the post goes on.
SIDE_FROM = 900
SIDE_SLICE = (0, 340, 58, 120, MIRROR_Y)
SIDE_REACH = 63 + 200           # the fill ends at h minus this, post coords
# Chat tab bar: `right` is a 1385 px dark strip ending in a cap, under a mask
# fixed at x 35..1151 that the client never resizes (ChatPan.as:1097 sets the
# width of a `mask` that does not exist). Past the art's width the cap slides
# in and out of that mask, and the strip stops short of the tabs. The strip
# is redrawn underneath at its real length, and the original is hidden.
CHAT_LEFT = 35
CHAT_CAP = 40                   # the cap and a little strip before it
CHAT_SLICE = (-398, 0, 120, 43, MIRROR_X)
CHAT_CAP_SLICE = (-CHAT_CAP, 0, CHAT_CAP, 43, PLAIN)


def draws(sl):
    """Bitmap size, and matrix (a, d, tx, ty) plus clip box for each draw."""
    x, y, w, h, kind = sl
    if kind == PLAIN:
        return (w, h), [(1, 1, -x, -y, 0, 0, w, h)]
    if kind == MIRROR_X:
        return (2 * w, h), [(-1, 1, x + w, -y, 0, 0, w, h),
                            (1, 1, w - x, -y, w, 0, w, h)]
    return (w, 2 * h), [(1, -1, -x, y + h, 0, 0, w, h),
                        (1, 1, -x, h - y, 0, h, w, h)]


def fn_draw():
    """_global.__wideDraw(bd, host, a, d, tx, ty, cx, cy, cw, ch)."""
    a = Asm()
    a.push("m").var("ty").var("tx").var("d").push(0, 0).var("a")
    new(a, ["flash", "geom"], "Matrix", 6).op("definelocal")
    a.push("r").var("ch").var("cw").var("cy").var("cx")
    new(a, ["flash", "geom"], "Rectangle", 4).op("definelocal")
    a.push("c")
    new(a, ["flash", "geom"], "ColorTransform", 0).op("definelocal")
    # bd.draw(host, m, c, "normal", r)
    a.var("r").push("normal").var("c").var("m").var("host")
    call_method(a, "bd", "draw", 5)
    return a


def fn_fill():
    """_global.__wideFill(mc, bd, x0, y0, x1, y1): bd repeated over the box."""
    a = Asm()
    a.var("x0").var("x1").op("less2").op("not").iftrue("done")
    a.var("y0").var("y1").op("less2").op("not").iftrue("done")
    a.push("m").var("y0").var("x0").push(1, 0, 0, 1)
    new(a, ["flash", "geom"], "Matrix", 6).op("definelocal")
    a.push(False, True).var("m").var("bd")
    call_method(a, "mc", "beginBitmapFill", 4)
    a.var("y0").var("x0")
    call_method(a, "mc", "moveTo", 2)
    for xs, ys in (("x1", "y0"), ("x1", "y1"), ("x0", "y1"), ("x0", "y0")):
        a.var(ys).var(xs)
        call_method(a, "mc", "lineTo", 2)
    call_method(a, "mc", "endFill", 0)
    a.label("done")
    return a


def slice_into(a, key, sl):
    """host[key] = the slice as a BitmapData, made once per piece."""
    (bw, bh), plan = draws(sl)
    a.var("host").push(key).op("getmember").push(UNDEF).op("equals2").op("not")
    a.iftrue("have_" + key)
    a.push("bd", 0, True, bh, bw)
    new(a, ["flash", "display"], "BitmapData", 4).op("definelocal")
    for (ma, md, tx, ty, cx, cy, cw, ch) in plan:
        a.push(ch, cw, cy, cx, ty, tx, md, ma).var("host").var("bd")
        a.push(10, "__wideDraw").op("callfunc").op("pop")
    a.var("host").push(key).var("bd").op("setmember")
    a.label("have_" + key)


def fresh_clip(a, where="host"):
    """var mc = where.createEmptyMovieClip("__wide", -16384): under the art."""
    a.push("mc", -16384, "__wide", 2).var(where)
    a.push("createEmptyMovieClip").op("callmethod").op("definelocal")


def fill_call(a, key, x0, y0, x1, y1, src="host"):
    """__wideFill(mc, src[key], x0, y0, x1, y1). A bound is a number, or a
    function emitting code that leaves the number on the stack."""
    for v in (y1, x1, y0, x0):
        if callable(v):
            v(a)
        else:
            a.push(v)
    a.var(src).push(key).op("getmember").var("mc")
    a.push(6, "__wideFill").op("callfunc").op("pop")


def expr(*code):
    """w - 460 and the like, written ('w', '-', 460)."""
    def emit(a):
        a.var(code[0])
        for k in range(1, len(code), 2):
            a.push(code[k + 1])
            a.op({"+": "add2", "-": "subtract", "/": "divide"}[code[k]])
    return emit


def guard_host(a):
    a.var("host").push(UNDEF).op("equals2").iftrue("out")


def only_wide(a):
    a.push(DESIGN_W).var("w").op("less2").op("not").iftrue("out")


def fn_strip():
    """_global.__wideStrip(host, w, h): a top strip, pipe from 640 to w/2."""
    a = Asm()
    guard_host(a)
    slice_into(a, "__wS", STRIP_SLICE)
    fresh_clip(a)
    only_wide(a)
    # to w/2 and a few pixels past: the mask stops it at w/2 either way, and
    # rounding must not leave a hairline between the two halves
    fill_call(a, "__wS", STRIP_END, 0, expr("w", "/", 2, "+", 4), STRIP_SLICE[3])
    a.label("out")
    return a


def fn_corner():
    """_global.__wideCorner(host, w, h): bottom plate and pipe, leftwards."""
    a = Asm()
    guard_host(a)
    # both slices before the fill clip exists, or the second copy would
    # pick up the first fill
    slice_into(a, "__wP", CORNER_PLATE)
    slice_into(a, "__wQ", CORNER_PIPE)
    fresh_clip(a)
    only_wide(a)
    end = expr("w", "-", BOTTOM_START)
    fill_call(a, "__wP", CORNER_PLATE_END, CORNER_PLATE[1], end,
              CORNER_PLATE[1] + CORNER_PLATE[3])
    fill_call(a, "__wQ", CORNER_PIPE_END, CORNER_PIPE[1], end,
              CORNER_PIPE[1] + CORNER_PIPE[3])
    a.label("out")
    return a


def fn_side():
    """_global.__wideSide(host, w, h): a side post, downwards to the corner."""
    a = Asm()
    guard_host(a)
    slice_into(a, "__wV", SIDE_SLICE)
    fresh_clip(a)
    fill_call(a, "__wV", 0, SIDE_FROM, SIDE_SLICE[2], expr("h", "-", SIDE_REACH))
    a.label("out")
    return a


def fn_chat():
    """_global.__wideChat(chat, w): the tab bar strip at its real length."""
    a = Asm()
    a.push("cp").var("chat").member("channelPan").op("definelocal")
    a.var("cp").push(UNDEF).op("equals2").iftrue("out")
    a.push("host").var("cp").member("right").op("definelocal")
    guard_host(a)
    slice_into(a, "__wC", CHAT_SLICE)
    slice_into(a, "__wE", CHAT_CAP_SLICE)
    fresh_clip(a, "cp")
    a.push(DESIGN_W).var("w").op("less2").op("not").iftrue("narrow")
    a.var("host").push("_visible", False).op("setmember")
    a.push("rx").var("host").member("_x").op("definelocal")
    fill_call(a, "__wC", CHAT_LEFT, 0, expr("rx", "-", CHAT_CAP), 43)
    fill_call(a, "__wE", expr("rx", "-", CHAT_CAP), 0, expr("rx"), 43)
    a.push(True).iftrue("out")
    a.label("narrow")
    a.var("host").push("_visible", True).op("setmember")
    a.label("out")
    return a


def fn_frame():
    """_global.__wideFrame(ui, w, h): every piece of one interface."""
    a = Asm()
    a.var("h").var("w").var("ui").push(3, "__wideLocationBack").op("callfunc").op("pop")
    for piece, fn in (("frame_top_left", "__wideStrip"),
                      ("frame_top_right", "__wideStrip"),
                      ("frame_right_corner", "__wideCorner"),
                      ("frame_left", "__wideSide"),
                      ("frame_right", "__wideSide")):
        a.var("h").var("w").var("ui").member(piece).push(3, fn).op("callfunc").op("pop")
    a.var("w").var("ui").push(2, "__onlinePanel").op("callfunc").op("pop")
    return a


def fn_location_back():
    """Opaque scene backing ending above the chat, which has a lower depth."""
    a = Asm()
    a.var("ui").member("locationFrame").push(UNDEF).op("equals2").iftrue("out")
    a.push("h").var("h").push(144).op("subtract").op("definelocal")
    a.push("mc", -16384, "__wideLocationBack", 2).var("ui")
    a.push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.push(100, 0x10151B)
    call_method(a, "mc", "beginFill", 2)
    a.push(0, 0)
    call_method(a, "mc", "moveTo", 2)
    for x, y in (("w", None), ("w", "h"), (None, "h"), (None, None)):
        a.var(y) if y else a.push(0)
        a.var(x) if x else a.push(0)
        call_method(a, "mc", "lineTo", 2)
    call_method(a, "mc", "endFill", 0)
    a.label("out")
    return a


def fn_location_bound(axis):
    """Clamp by map bounds, centering maps smaller than the view on each axis.

    Only LocationInterface.locationFrame opts in. Other ViewFrame users
    retain the original behavior, including windows and the global map.
    """
    low, high = ("left", "right") if axis == "X" else ("top", "bottom")
    prop = "_x" if axis == "X" else "_y"
    a = Asm()
    a.var("this").member("_parent", "locationFrame").var("this").op("equals2")
    a.op("not").iftrue("original")
    a.var("this").member("setArea").op("not").iftrue("original")
    a.push("lo").var("this").member(low).op("definelocal")
    a.push("hi").var("this").member(high).op("definelocal")
    a.push("pos").var("this").member("cont_mc", prop).op("definelocal")
    a.var("lo").var("hi").op("less2").iftrue("clamp")
    a.push("pos").var("lo").var("hi").op("add2").push(2).op("divide").op("definelocal")
    a.push(True).iftrue("apply")
    a.label("clamp")
    # A previous zero scroll span makes ViewFrame.x/yPosition return NaN.
    a.var("pos").push(1, "isNaN").op("callfunc").op("not").iftrue("finite")
    a.push("pos").var("hi").op("definelocal")
    a.label("finite")
    a.push("pos").var("pos").var("hi").push(2).var("Math").push("min").op("callmethod")
    a.var("lo").push(2).var("Math").push("max").op("callmethod").op("definelocal")
    a.label("apply")
    # A slide targeting a point outside the camera range never reaches its
    # endpoint. Stop it when clamping, or it pulls every manual scroll back
    # to the boundary on the next frame (ViewFrame.slideContX/slideContY).
    a.var("this").member("cont_mc", prop).var("pos").op("equals2").iftrue("position")
    a.push("slideCont" + axis)
    call_method(a, "this", "deleteEnterFrame", 1)
    a.label("position")
    a.var("this").member("cont_mc").push(prop).var("pos").op("setmember")
    a.push(UNDEF).op("return")
    a.label("original")
    call_method(a, "this", "__wideBound" + axis + "Orig", 0)
    return a


def fn_source_library():
    """The hidden source clips remain usable by BitmapData.draw/loadBitmap."""
    a = Asm()
    call_method(a, "this", "__wideCreateOrig", 0)
    a.var("this").member("_lib").push("_visible", False).op("setmember")
    return a


def fn_location_scene():
    """SceneShifter.locationScene(): the original, then the mask again."""
    tick = Asm()
    tick.push("f").var("this").member("_parent", "locationFrame").op("definelocal")
    tick.var("f").member("mask_mc").push(1).var("f").member("cont_mc")
    tick.push("setMask").op("callmethod").op("pop")
    tick.var("this").push("left").var("this").member("left").push(1)
    tick.op("subtract").op("setmember")
    tick.push(0).var("this").member("left").op("less2").iftrue("out")
    call_method(tick, "this", "removeMovieClip", 0)
    tick.label("out")
    a = Asm()
    call_method(a, "this", "__wideSceneOrig", 0)
    a.push("ui").var("this").member("locationScreen").op("definelocal")
    a.var("ui").push(UNDEF).op("equals2").iftrue("out")
    a.push("mc", 0).var("ui").push("getNextHighestDepth").op("callmethod")
    a.push("__wideRemask", 2).var("ui").push("createEmptyMovieClip").op("callmethod")
    a.op("definelocal")
    a.var("mc").push("left", 2).op("setmember")
    a.var("mc").push("onEnterFrame").function((), tick).op("setmember")
    a.label("out")
    return a


def fn_wrapper(call):
    """resizeStage(obj): the original first, then the fill."""
    a = Asm()
    a.var("obj").push(1).var("this").push("__wideOrig").op("callmethod").op("pop")
    a.var("obj").push(UNDEF).op("equals2").iftrue("out")
    if call == MARK:
        a.var("obj").member("h").var("obj").member("w").var("this")
        a.push(3, MARK).op("callfunc").op("pop")
    else:
        a.var("obj").member("w").var("this")
        a.push(2, call).op("callfunc").op("pop")
    a.label("out")
    return a


def fn_messages():
    """SpecSkillMessages.init(): the original, unless this service is an
    orphan -- not the one master.gamer holds, because the Gamer it was made
    with is dead and deleted it (Gamer.as:361-368). Written as
    `if (Master.getInstance().gamer.ssMessages == this) this.__wideOrig()`."""
    a = Asm()
    a.var("this")
    a.push(0).var("lol").member("core", "Master").push("getInstance").op("callmethod")
    a.member("gamer", "ssMessages")
    a.op("equals2").op("not").iftrue("out")
    a.push(0).var("this").push("__wideOrig").op("callmethod").op("pop")
    a.label("out")
    return a


def fn_progress_snapshot():
    """Load the initial rp_info silently before enabling progress events.

    SpecObject starts value_bonus at zero, so a saved level of one emits
    INCREASE_SPEC_LEVEL even on the first snapshot. The five-second delay
    in SpecSkillMessages.init is not a loading barrier.
    """
    a = Asm()
    a.var("obj").push(1).var("this").push("__progressInfoOrig").op("callmethod").op("pop")
    a.var("this").push("__progressLoaded", True).op("setmember")
    return a


def fn_progress_event(original):
    """Forward progress only after this PersAttributes has a baseline.

    Keep rp_info's assignments and UPDATE_PARAMS intact. Filtering at
    showMessage would leave false login events in the combat queues.
    """
    a = Asm()
    a.var("this").member("__progressLoaded").op("not").iftrue("out")
    a.var("obj").push(1).var("this").push(original).op("callmethod").op("pop")
    a.label("out")
    return a


def fn_services():
    """NPC.userInfo(obj): `this.supportList = []; this.__wideOrig(obj)`,
    so a repeated userInfo rebuilds the services instead of adding to them."""
    a = Asm()
    a.var("this").push("supportList").push(0).op("initarray").op("setmember")
    a.var("obj").push(1).var("this").push("__wideOrig").op("callmethod").op("pop")
    return a


def fn_repair_cost():
    """Item.getProp: value gold-only items in afro in SS_REPAIR only.

    All RepairInterface slot, drag, double-click and bulk calculations,
    plus ItemContainer's bag prices, read cost through this method.
    StaffInterface.kill clears ssType; shops keep the original zero cost
    and therefore cannot buy or sell gold-only items for afro.
    """
    a = Asm()
    a.push("value").var("prop").push(1).var("this")
    a.push("__repairGetPropOrig").op("callmethod").op("definelocal")
    a.var("prop").push("cost").op("equals2").op("not").iftrue("original")
    a.var("value").iftrue("original")
    a.var("lol").member("gpui", "StaffInterface", "ssType")
    a.push("repair").op("equals2").op("not").iftrue("original")
    a.push("gold").push("g_cost", 1).var("this")
    a.push("__repairGetPropOrig").op("callmethod").op("definelocal")
    a.var("gold").op("not").iftrue("original")
    a.var("gold").var("lol").member("core", "GConstatns", "gold_repair_mod")
    a.op("multiply").push(100).op("divide").op("return")
    a.label("original").var("value").op("return")
    return a


def fn_repair_gold():
    """RepairInterface.calcGoldCostFromAfroCost: nearest cent, at least one."""
    a = Asm()
    a.push("gold").var("afro_cost")
    a.var("lol").member("core", "GConstatns", "gold_repair_mod")
    a.op("divide").push(100).op("multiply")
    a.push(1).var("Math").push("round").op("callmethod").op("definelocal")
    a.var("gold").push(1).op("less2").op("not").iftrue("out")
    a.push("gold", 1).op("definelocal")
    a.label("out").var("gold").push(100).op("divide").op("return")
    return a


HOME_SET = "Теперь вы будете возрождаться в этой локации"

ONLINE_WIDTH = 76
ONLINE_BITMAP = "__lavaOnlineIcon"
ONLINE_OLD_BITMAPS = ("__lavaOnlinePlate",)    # what earlier patches exported
ONLINE_ASSET = Path(__file__).resolve().parent.parent / "data/client/online-panel.png"
ONLINE_ICON = (12, 5, 18, 18)   # the people icon inside the plate: x, y, w, h
ONLINE_RIGHT = 180             # 40 pixels before the exit at w - 140
ONLINE_INLINE_MIN = 1200        # gold controls end around w / 2 + 313; a 90-pixel
                                # plate ending at w - 180 clears them from 1176
ONLINE_TEXT_RGB = 0xCFC6AE      # muted beige, the icon's own tone
# The plate is the popup's frame cut inside its shadow (the plate runs
# x 8..488, y 5..462 of the art), in five rows: the top edge, some plain
# plate, the band with the corner rivets, plain plate again, the bottom
# edge, so each rivet sits halfway up its end. (key suffix, art y, height):
ONLINE_ROWS = (("t", 5, 4), ("f", 400, 3), ("r", 9, 8), ("f", 400, 3), ("b", 458, 4))
ONLINE_H = sum(h for _, _, h in ONLINE_ROWS)      # 22, the narrow bar's lip
ONLINE_LABEL_X, ONLINE_ARROW_W, ONLINE_CAP = 33, 10, 22
ONLINE_COLUMNS = (("l", 8), ("m", 40), ("r", 466))    # (suffix, art x)


def fn_online_art():
    """_global.__onlineArt(host): the settings window's frame and texture as
    BitmapData slices, made once a session from art attached for a moment."""
    a = Asm()
    a.var("_global").member("__onlineSlices").push(UNDEF).op("equals2").op("not").iftrue("done")
    a.push("S")
    new(a, ("_global",), "Object", 0).op("definelocal")
    for name, _ in LIST_ART:
        a.push(0).var("host").push("getNextHighestDepth").op("callmethod")
        a.push(name, name, 3).var("host").push("attachMovie").op("callmethod").op("pop")
    for key, art, x, y, w, h in LIST_SLICES:
        a.push("bd", 0, True, h, w)
        new(a, ("flash", "display"), "BitmapData", 4).op("definelocal")
        a.push(h, w, 0, 0, -y, -x, 1, 1).var("host").member(art).var("bd")
        a.push(10, "__wideDraw").op("callfunc").op("pop")
        a.var("S").push(key).var("bd").op("setmember")
    for name, _ in LIST_ART:
        a.push(0).var("host").member(name).push("removeMovieClip").op("callmethod").op("pop")
    a.var("_global").push("__onlineSlices").var("S").op("setmember")
    a.label("done")
    a.var("_global").member("__onlineSlices").op("return")
    return a


def fn_online_refresh():
    """The count, the arrow and a plate as wide as they need, right-anchored."""
    E, R = ONLINE_CAP, expr("W", "-", ONLINE_CAP)
    a = Asm()
    a.push("panel").var("ui").member("__onlinePanel").op("definelocal")
    a.var("panel").push(UNDEF).op("equals2").iftrue("out")
    a.push("value", "...").op("definelocal")
    a.var("_global").member("__onlineCount").push(UNDEF).op("equals2").iftrue("draw")
    a.push("value").var("_global").member("__onlineCount").op("definelocal")
    a.label("draw")
    a.var("panel").push("hintTitle_str", "Игроков в сети: ").var("value").op("add2").op("setmember")
    a.push("label").var("panel").member("label").op("definelocal")
    a.var("label").push("text").var("value").op("setmember")
    # AutoSize geometry is delayed by a frame in AVM1: size by digit count.
    a.push("lw").var("value").push(1, "String").op("callfunc").member("length")
    a.push(8).op("multiply").push(4).op("add2").op("definelocal")
    a.var("label").push("_width").var("lw").op("setmember")
    a.push("ax").var("lw").push(ONLINE_LABEL_X + 3).op("add2").op("definelocal")
    # The right rivet starts 11 in from the edge; the arrow stops 5 before.
    a.push("W").var("ax").push(ONLINE_ARROW_W + 16).op("add2").op("definelocal")
    a.var("panel").member("__w").var("W").op("equals2").iftrue("drawn")
    a.var("panel").push("__w").var("W").op("setmember")
    a.push("S").var("ui").push(1, "__onlineArt").op("callfunc").op("definelocal")
    a.push("mc", 0, "bg", 2).var("panel").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    y0 = 0
    for row, _, h in ONLINE_ROWS:
        for col, box in (("m", (E, y0, R, y0 + h)), ("l", (0, y0, E, y0 + h)),
                         ("r", (R, y0, expr("W"), y0 + h))):
            fill_call(a, "c" + row + col, *box, src="S")
        y0 += h
    a.label("drawn")
    # The arrow says what a click does: down opens, up closes.
    a.push("mc", 3, "arrow", 2).var("panel").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.var("mc").push("_x").var("ax").op("setmember")
    a.var("mc").push("_y", ONLINE_H // 2 - 2).op("setmember")
    # Whole pixel rows, 10 to 2 wide: an antialiased triangle and its mirror
    # image do not rasterize alike, rows do. Up is the same rows reversed.
    a.push(100, ONLINE_TEXT_RGB)
    call_method(a, "mc", "beginFill", 2)
    a.var("ui").member("__onlineOpen", "_name").push(UNDEF).op("equals2").iftrue("down")
    for label, order in (("up", (4, 3, 2, 1, 0)), ("down", (0, 1, 2, 3, 4))):
        if label == "down":
            a.label("down")
        for y, i in enumerate(order):
            x0, x1 = i, ONLINE_ARROW_W - i
            for k, (x, yy) in enumerate(((x0, y), (x1, y), (x1, y + 1), (x0, y + 1), (x0, y))):
                a.push(yy, x)
                call_method(a, "mc", "moveTo" if k == 0 else "lineTo", 2)
        if label == "up":
            a.push(True).iftrue("drawn_arrow")
    a.label("drawn_arrow")
    call_method(a, "mc", "endFill", 0)
    a.var("panel").push("_x").var("panel").member("__right").var("W").op("subtract")
    a.push(1).var("Math").push("round").op("callmethod").op("setmember")
    a.label("out")
    return a


def fn_online_panel():
    """The popup's frame as a plate, the original icon, live text and tooltip."""
    a = Asm()
    a.var("ui").member("__onlinePanel").push(UNDEF).op("equals2").op("not").iftrue("place")
    a.push("panel")
    a.push(0).var("ui").push("getNextHighestDepth").op("callmethod")
    a.push("__onlinePanel", 2).var("ui").push("createEmptyMovieClip").op("callmethod")
    a.op("definelocal")
    a.var("_global").member("__onlineBitmap").push(UNDEF).op("equals2").op("not").iftrue("bitmap")
    a.var("_global").push("__onlineBitmap", ONLINE_BITMAP, 1)
    a.var("flash").member("display", "BitmapData").push("loadBitmap").op("callmethod").op("setmember")
    a.label("bitmap")
    a.push("icon", 1, "icon", 2).var("panel").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.push(0).var("_global").member("__onlineBitmap")
    call_method(a, "icon", "attachBitmap", 2)
    # The icon's own pixels start a pixel into its square: just past the
    # left rivet, centred on the plate.
    a.var("icon").push("_x", 14).op("setmember")
    a.var("icon").push("_y", 3).op("setmember")
    a.push(18, 12, 2, ONLINE_LABEL_X, 2, "label")
    call_method(a, "panel", "createTextField", 6)
    a.push("label").var("panel").member("label").op("definelocal")
    for key, value in (("selectable", False), ("embedFonts", False),
                       ("autoSize", False), ("wordWrap", False)):
        a.var("label").push(key, value).op("setmember")
    a.push("fmt")
    new(a, ("_global",), "TextFormat", 0).op("definelocal")
    for key, value in (("font", "Tahoma"), ("size", 13), ("bold", True),
                       ("color", ONLINE_TEXT_RGB), ("align", "center")):
        a.var("fmt").push(key, value).op("setmember")
    a.var("fmt")
    call_method(a, "label", "setNewTextFormat", 1)
    a.var("panel").push("tabEnabled", False).op("setmember")
    over = Asm()
    over.var("this").push("__hover", True).op("setmember")
    over.push(ONLINE_H).var("this").member("_ymouse").op("subtract")
    over.var("this").member("_ymouse").var("this").member("hintTitle_str").push(3)
    over.var("lol").member("gpui", "HintManager").push("showHint").op("callmethod").op("pop")
    out = Asm()
    out.var("this").member("__hover").op("not").iftrue("done")
    out.var("this").push("__hover", False).op("setmember")
    out.push(0).var("lol").member("gpui", "HintManager").push("closeHint").op("callmethod").op("pop")
    out.label("done")
    toggle = Asm()
    toggle.push(0).var("lol").member("gpui", "HintManager").push("closeHint").op("callmethod").op("pop")
    toggle.var("this").member("_parent").push(1, "__onlineToggle").op("callfunc").op("pop")
    for event, handler in (("onRollOver", over), ("onRollOut", out), ("onUnload", out),
                           ("onRelease", toggle)):
        a.var("panel").push(event).function((), handler).op("setmember")
    a.label("place")
    a.push("panel").var("ui").member("__onlinePanel").op("definelocal")
    # Narrow windows have only the 22-pixel lip above the gold controls;
    # wide ones centre the plate where the bar is tallest.
    a.var("panel").push("_y", 0).op("setmember")
    a.var("w").push(ONLINE_INLINE_MIN).op("less2").iftrue("anchor")
    a.var("panel").push("_y", 21).op("setmember")
    a.label("anchor")
    a.var("panel").push("__right").var("w").push(ONLINE_RIGHT).op("subtract").op("setmember")
    a.var("ui").push(1, "__onlineRefresh").op("callfunc").op("pop")
    return a


def fn_online_send():
    """Opt in on hello; keep Send's boolean result and its normal filtering."""
    a = Asm()
    a.var("mess").member("name").push("hello").op("equals2").op("not").iftrue("send")
    a.var("_global").push("__onlineCount", UNDEF).op("setmember")
    a.var("_global").push("__onlineNames", UNDEF).op("setmember")
    a.push(2, "online")
    call_method(a, "mess", "addProp", 2)
    a.label("send")
    a.var("mess").push(1).var("this").push("__onlineSendOrig").op("callmethod").op("return")
    return a


def fn_online_notification():
    """Cache the push independently of either location/map scene's lifetime."""
    a = Asm()
    a.var("cmd").member("messID").push("online").op("equals2").op("not").iftrue("dispatch")
    a.var("_global").push("__onlineCount").var("cmd").member("params", "count").op("setmember")
    a.var("_global").push("__onlineNames").var("cmd").member("params", "names").op("setmember")
    a.push("scene").var("lol").member("core", "SceneShifter", "_ref", "currentScene").op("definelocal")
    a.var("scene").push(1, "__onlineRefresh").op("callfunc").op("pop")
    a.var("scene").push(1, "__onlineUpdate").op("callfunc").op("pop")
    a.label("dispatch")
    a.var("cmd").push(1).var("this").push("__onlineNotifyOrig").op("callmethod").op("pop")
    return a


# --- the list of players under the counter ----------------------------------

LIST_FRAME = "__lavaOnlineFrame"    # the settings window's frame, shape 581
LIST_INNER = "__lavaOnlineInner"    # the settings window's texture, shape 596
LIST_ART = ((LIST_FRAME, 581), (LIST_INNER, 596))
LIST_EDGE = 22                      # frame border: plate, rivet and shadow
LIST_PAD = 4
LIST_ROW_W, LIST_ROW_H, LIST_PITCH = 176, 23, 27    # SettingsInterface rows
LIST_BAR = 19                       # scrollPan2's vBar draws x -1..15, 3 from the rows
LIST_ROWS = (3, 8)                  # visible rows: fewest, most
LIST_W = 2 * LIST_EDGE + LIST_PAD + LIST_ROW_W + LIST_BAR + 3
LIST_ROW_RGB, LIST_TEXT_RGB, LIST_KANT_RGB = 0x6D6B65, 0x3A3936, 0x524F49
# (key, art, x, y, w, h): slices of the 496x471 frame art. Its plate runs
# x 8..488, y 5..464 with a rivet in each corner; the edges come from the
# solid band under the window's hole (y 378..464).
LIST_SLICES = (("tl", LIST_FRAME, 0, 0, 22, 22), ("tr", LIST_FRAME, 474, 0, 22, 22),
               ("bl", LIST_FRAME, 0, 449, 22, 22), ("br", LIST_FRAME, 474, 449, 22, 22),
               ("t", LIST_FRAME, 40, 0, 16, 22), ("b", LIST_FRAME, 40, 449, 16, 22),
               ("l", LIST_FRAME, 0, 400, 22, 16), ("r", LIST_FRAME, 474, 400, 22, 16),
               ("in", LIST_INNER, 300, 90, 200, 200),
               # the counter's plate, row by row and column by column
               ) + tuple(("c" + row + col, LIST_FRAME, x, y, 16 if col == "m" else 22, h)
                         for row, y, h in ONLINE_ROWS
                         for col, x in ONLINE_COLUMNS)


def emit(a, v):
    """A number, or a function emitting code that leaves one on the stack."""
    if callable(v):
        v(a)
    else:
        a.push(v)


def rect(a, clip, w, h, rgb, alpha=100):
    """clip: a filled w x h rectangle at its origin."""
    a.push(alpha, rgb)
    call_method(a, clip, "beginFill", 2)
    for k, (x, y) in enumerate(((0, 0), (w, 0), (w, h), (0, h), (0, 0))):
        emit(a, y)
        emit(a, x)
        call_method(a, clip, "moveTo" if k == 0 else "lineTo", 2)
    call_method(a, clip, "endFill", 0)


def fn_online_toggle():
    """_global.__onlineToggle(ui): the counter opens and closes the list."""
    a = Asm()
    a.var("ui").member("__onlineOpen", "_name").push(UNDEF).op("equals2").iftrue("open")
    a.var("ui").push(1, "__onlineClose").op("callfunc").op("pop")
    a.push(UNDEF).op("return")
    a.label("open")
    a.push(UNDEF).var("ui").push(2, "__onlineShow").op("callfunc").op("pop")
    return a


def fn_online_update():
    """_global.__onlineUpdate(ui): new names into an open list, same scroll."""
    a = Asm()
    a.var("ui").member("__onlineOpen", "_name").push(UNDEF).op("equals2").iftrue("out")
    a.push("y").var("ui").member("__onlineOpen", "pan", "yPosition").op("definelocal")
    a.var("ui").push(1, "__onlineClose").op("callfunc").op("pop")
    a.var("y").var("ui").push(2, "__onlineShow").op("callfunc").op("pop")
    a.label("out")
    return a


def fn_online_close():
    """_global.__onlineClose(ui): the popup and everything it registered."""
    a = Asm()
    a.push("p").var("ui").member("__onlineOpen").op("definelocal")
    a.var("ui").push("__onlineOpen", UNDEF).op("setmember")
    a.var("p").member("_name").push(UNDEF).op("equals2").iftrue("out")
    a.var("p").member("__watch").push("wheel").var("p").member("pan", "mouseListener").op("setmember")
    a.var("p").member("__watch", "inside").op("not").iftrue("cursor")
    a.push(False).var("ui").push(2, "__onlineCursor").op("callfunc").op("pop")
    a.label("cursor")
    # While the references are live: a removed clip's reference equals
    # every other dead one, and would take other listeners with it.
    a.var("p").member("__watch").push(1, "__onlineForget").op("callfunc").op("pop")
    call_method(a, "p", "removeMovieClip", 0)
    a.var("ui").push(1, "__onlineRefresh").op("callfunc").op("pop")
    a.label("out")
    return a


def fn_online_forget():
    """_global.__onlineForget(watch): unregister what one popup registered.

    References alone are enough, so this also cleans up after a popup whose
    scene is gone: the dispatchers compare listeners by identity."""
    a = Asm()
    a.var("watch").push(1).var("Mouse").push("removeListener").op("callmethod").op("pop")
    a.var("watch").member("wheel").push(UNDEF).op("equals2").iftrue("nowheel")
    a.var("watch").member("wheel").push(1).var("Mouse").push("removeListener").op("callmethod").op("pop")
    a.label("nowheel")
    # The pane and its inner frame both listen to Key, ViewFrame's way:
    # added twice, and each call takes one copy.
    for k, path in enumerate((("pan",), ("pan_frame",))):
        a.label("keys%d" % k)
        a.var("watch").member(*path).push(1).var("Key").push("removeListener").op("callmethod")
        a.iftrue("keys%d" % k)
    a.push("dc").var("lol").member("gpui", "controls", "GPUIButton", "prototype", "doubleClick")
    a.op("definelocal")
    a.push("i", 0).op("definelocal")
    a.label("loop")
    a.var("i").var("watch").member("buttons", "length").op("less2").op("not").iftrue("out")
    a.var("dc").var("watch").member("buttons").var("i").op("getmember").push("onDoubleClick", 3)
    a.var("lol").member("utils", "EMouse").push("removeEventListener").op("callmethod").op("pop")
    a.push("i").var("i").push(1).op("add2").op("definelocal")
    a.push(True).iftrue("loop")
    a.label("out")
    a.var("watch").push("buttons", 0).op("initarray").op("setmember")
    return a


def fn_online_watch():
    """watch.onMouseDown: a click outside the popup and the counter closes it."""
    a = Asm()
    a.push("p").var("this").member("p").op("definelocal")
    a.var("p").member("_name").push(UNDEF).op("equals2").op("not").iftrue("alive")
    a.var("this").push(1, "__onlineForget").op("callfunc").op("pop")
    a.push(UNDEF).op("return")
    a.label("alive")
    a.var("this").push("wheel").var("p").member("pan", "mouseListener").op("setmember")
    for target in (("p",), ("p", "_parent", "__onlinePanel")):
        a.push(True).var("_root").member("_ymouse").var("_root").member("_xmouse").push(3)
        a.var(target[0]).member(*target[1:]).push("hitTest").op("callmethod")
        a.iftrue("inside")
    a.var("p").member("_parent").push(1, "__onlineClose").op("callfunc").op("pop")
    a.label("inside")
    return a


def fn_online_watch_move():
    """watch.onMouseMove: the location's own cursor is off over the popup.

    CursorManager finds sprites under the mouse from a Mouse listener, past
    any clip on top; the client's modal windows switch it off through
    sceneEnabled. The popup does the same while the mouse is over it, and
    gives it back on leaving unless a modal window holds the scene."""
    a = Asm()
    a.push("p").var("this").member("p").op("definelocal")
    a.var("p").member("_name").push(UNDEF).op("equals2").iftrue("out")
    a.push("inside").push(True).var("_root").member("_ymouse").var("_root").member("_xmouse")
    a.push(3).var("p").push("hitTest").op("callmethod").op("definelocal")
    a.var("inside").var("this").member("inside").op("equals2").iftrue("out")
    a.var("this").push("inside").var("inside").op("setmember")
    a.var("inside").var("p").member("_parent").push(2, "__onlineCursor").op("callfunc").op("pop")
    a.label("out")
    return a


def fn_online_cursor():
    """_global.__onlineCursor(ui, hidden): the location's cursor off or back."""
    a = Asm()
    a.push("cm").var("ui").member("displayLoc", "cursorManager").op("definelocal")
    a.var("cm").push(UNDEF).op("equals2").iftrue("out")
    a.var("hidden").op("not").iftrue("back")
    a.push(False, 1).var("cm").push("activate").op("callmethod").op("pop")
    a.push(UNDEF).op("return")
    a.label("back")
    a.var("lol").member("core", "SceneShifter", "_ref", "flagSceneEnabled").iftrue("out")
    a.push(True, 1).var("cm").push("activate").op("callmethod").op("pop")
    a.label("out")
    return a


def fn_online_pick():
    """Envelope or nick: close the list and prepare a private in the chat."""
    a = Asm()
    a.push("nick").var("this").member("__nick").op("definelocal")
    a.var("this").member("__ui").push(1, "__onlineClose").op("callfunc").op("pop")
    a.push("chat").var("lol").member("core", "SceneShifter", "chat").op("definelocal")
    # Already "private <nick>:": the client's own call would turn it into
    # "to <nick>:" (ChatPan.selectUserNickBase), so only focus the line.
    a.push("private ").var("nick").op("add2").push(":").op("add2")
    a.push(1).var("chat").member("chatInput", "text").push("indexOf").op("callmethod")
    a.push(0).op("equals2").op("not").iftrue("select")
    call_method(a, "chat", "gotoLastSymbol", 0)
    a.push(UNDEF).op("return")
    a.label("select")
    a.var("nick")
    call_method(a, "chat", "selectPrivateUserNick", 1)
    return a


def fn_online_hover(on):
    a = Asm()
    a.var("this").member("_parent", "hi").push("_visible", on).op("setmember")
    return a


def fn_online_show():
    """_global.__onlineShow(ui, y): build the popup under the counter."""
    E = LIST_EDGE
    W_E, H_E = expr("W", "-", E), expr("H", "-", E)
    a = Asm()
    a.push("panel").var("ui").member("__onlinePanel").op("definelocal")
    a.var("panel").push(UNDEF).op("equals2").iftrue("out")
    a.push("names").var("_global").member("__onlineNames").op("definelocal")
    a.var("names").push(UNDEF).op("equals2").iftrue("out")
    a.push("me").var("lol").member("core", "Master", "sInstance", "gamer", "playerInfo", "name")
    a.op("definelocal")
    # Own name first, then the server's order.
    a.push("list", 0).op("initarray").op("definelocal")
    for k, own in ((1, True), (2, False)):
        a.push("i", 0).op("definelocal")
        a.label("sort%d" % k)
        a.var("i").var("names").member("length").op("less2").op("not").iftrue("sorted%d" % k)
        a.var("names").var("i").op("getmember").var("me").op("equals2")
        if own:
            a.op("not")
        a.iftrue("next%d" % k)
        a.var("names").var("i").op("getmember").push(1).var("list").push("push").op("callmethod").op("pop")
        a.label("next%d" % k)
        a.push("i").var("i").push(1).op("add2").op("definelocal")
        a.push(True).iftrue("sort%d" % k)
        a.label("sorted%d" % k)
    a.push("n").var("list").member("length").op("definelocal")
    # As many rows as fit between the counter and the chat.
    # The frame's own shadow is 5 above its plate and 8 right of it.
    a.push("top").var("panel").member("_y").push(ONLINE_H + 3 - 5).op("add2").op("definelocal")
    a.push("rows", LIST_ROWS[1]).op("definelocal")
    a.push("room").var("lol").member("core", "SceneShifter", "chat", "_y").var("top").op("subtract")
    a.push(2 * E + 2 * LIST_PAD + 4).op("subtract").push(LIST_PITCH).op("divide")
    a.push(1).var("Math").push("floor").op("callmethod").op("definelocal")
    a.var("room").var("rows").op("less2").op("not").iftrue("fits")
    a.push("rows").var("room").op("definelocal")
    a.var("rows").push(LIST_ROWS[0]).op("less2").op("not").iftrue("fits")
    a.push("rows", LIST_ROWS[0]).op("definelocal")
    a.label("fits")
    # Rows run to the right edge when there is nothing to scroll.
    a.push("rw", LIST_ROW_W).op("definelocal")
    a.push("pw", LIST_ROW_W + 3).op("definelocal")
    a.var("n").var("rows").op("less2").op("not").iftrue("many")
    a.push("rows").var("n").op("definelocal")
    a.label("many")
    a.var("rows").var("n").op("less2").iftrue("scrolls")
    a.push("rw", LIST_ROW_W + LIST_BAR).op("definelocal")
    a.push("pw").var("rw").op("definelocal")
    a.label("scrolls")
    a.push("lh").var("rows").push(LIST_PITCH).op("multiply")
    a.push(LIST_PITCH - LIST_ROW_H).op("subtract").op("definelocal")
    a.push("W", LIST_W).op("definelocal")
    a.push("H").var("lh").push(2 * E + 2 * LIST_PAD).op("add2").op("definelocal")
    # A name of its own: a stale reference never finds the next popup.
    a.var("_global").member("__onlineSeq").push(UNDEF).op("equals2").op("not").iftrue("counted")
    a.var("_global").push("__onlineSeq", 0).op("setmember")
    a.label("counted")
    a.var("_global").push("__onlineSeq").var("_global").member("__onlineSeq").push(1).op("add2")
    a.op("setmember")
    a.push("p")
    a.push(0).var("ui").push("getNextHighestDepth").op("callmethod")
    a.push("__onlinePopup").var("_global").member("__onlineSeq").op("add2")
    a.push(2).var("ui").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.var("ui").push("__onlineOpen").var("p").op("setmember")
    a.push("x").var("panel").member("_x").var("panel").member("__w").op("add2")
    a.var("W").op("subtract").push(8).op("add2").op("definelocal")
    a.var("x").push(8).op("less2").op("not").iftrue("left")
    a.push("x", 8).op("definelocal")
    a.label("left")
    a.var("p").push("_x").var("x").push(1).var("Math").push("round").op("callmethod").op("setmember")
    a.var("p").push("_y").var("top").push(1).var("Math").push("round").op("callmethod").op("setmember")
    a.push("S").var("p").push(1, "__onlineArt").op("callfunc").op("definelocal")
    a.push("mc", 0, "frame", 2).var("p").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    for key, box in (("in", (E, E, W_E, H_E)), ("t", (E, 0, W_E, E)),
                     ("b", (E, H_E, W_E, expr("H"))), ("l", (0, E, E, H_E)),
                     ("r", (W_E, E, expr("W"), H_E)), ("tl", (0, 0, E, E)),
                     ("tr", (W_E, 0, expr("W"), E)), ("bl", (0, H_E, E, expr("H"))),
                     ("br", (W_E, H_E, expr("W"), expr("H")))):
        fill_call(a, key, *box, src="S")
    a.push(100, LIST_KANT_RGB, 2)
    call_method(a, "mc", "lineStyle", 3)
    for k, (x, y) in enumerate(((E, E), (W_E, E), (W_E, H_E), (E, H_E), (E, E))):
        emit(a, y)
        emit(a, x)
        call_method(a, "mc", "moveTo" if k == 0 else "lineTo", 2)
    call_method(a, "mc", "lineStyle", 0)
    # The frame takes the clicks that miss a row or button, so the map
    # under it gets none (its ground answers onPress, GlobalMapInterface's
    # map too); the location's sprites listen to Mouse instead, see
    # __onlineWatchMove.
    a.var("mc").push("onPress").var("_global").member("__onlineNothing").op("setmember")
    a.var("mc").push("useHandCursor", False).op("setmember")
    # What the popup registers, kept apart from it for __onlineForget.
    a.push("watch")
    new(a, ("_global",), "Object", 0).op("definelocal")
    a.var("watch").push("p").var("p").op("setmember")
    a.var("watch").push("buttons", 0).op("initarray").op("setmember")
    a.var("watch").push("onMouseDown").var("_global").member("__onlineWatch").op("setmember")
    a.var("watch").push("onMouseMove").var("_global").member("__onlineWatchMove").op("setmember")
    a.var("p").push("__watch").var("watch").op("setmember")
    # The hotkey list's scroll pane.
    a.push("pan", 2, "pan", "scrollPan2", 3).var("p").push("attachMovie").op("callmethod").op("definelocal")
    a.var("pan").push("_x", E + LIST_PAD).op("setmember")
    a.var("pan").push("_y", E + LIST_PAD).op("setmember")
    a.var("watch").push("pan").var("pan").op("setmember")
    a.var("watch").push("pan_frame").var("pan").member("frame").op("setmember")
    for bar in ("vBar", "hBar"):
        for b in ("upButton", "downButton", "sliderButton"):
            a.var("pan").member(bar, b).push(1).var("watch").member("buttons")
            a.push("push").op("callmethod").op("pop")
    call_method(a, "pan", "fillContent", 0)
    a.push("c").var("pan").member("_content").op("definelocal")
    a.push("fmt")
    new(a, ("_global",), "TextFormat", 0).op("definelocal")
    for key, value in (("font", "Tahoma"), ("size", 11), ("color", LIST_TEXT_RGB)):
        a.var("fmt").push(key, value).op("setmember")
    a.push("i", 0).op("definelocal")
    a.label("row")
    a.var("i").var("n").op("less2").op("not").iftrue("rows_done")
    a.push("nick").var("list").var("i").op("getmember").op("definelocal")
    a.push("r").var("i").push("r").var("i").op("add2").push(2).var("c")
    a.push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.var("r").push("_y").var("i").push(LIST_PITCH).op("multiply").op("setmember")
    a.push("mc", 0, "bg", 2).var("r").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    rect(a, "mc", expr("rw"), LIST_ROW_H, LIST_ROW_RGB)
    a.push("hi", 1, "hi", 2).var("r").push("createEmptyMovieClip").op("callmethod").op("definelocal")
    rect(a, "hi", expr("rw"), LIST_ROW_H, 0xFFFFFF, 12)
    a.var("hi").push("_visible", False).op("setmember")
    a.push(LIST_ROW_H - 4).var("rw").push(34).op("subtract").push(3, 6, 2, "t", 6)
    a.var("r").push("createTextField").op("callmethod").op("pop")
    a.push("t").var("r").member("t").op("definelocal")
    a.var("t").push("selectable", False).op("setmember")
    a.var("fmt")
    call_method(a, "t", "setNewTextFormat", 1)
    a.var("t").push("text").var("nick").op("setmember")
    a.push("m", 3, "m", "mail_btn", 3).var("r").push("attachMovie").op("callmethod").op("definelocal")
    a.var("m").push("_x").var("rw").push(25).op("subtract").op("setmember")
    a.var("m").push(1).var("watch").member("buttons").push("push").op("callmethod").op("pop")
    a.var("nick").var("me").op("equals2").op("not").iftrue("other")
    a.var("t").push("text").var("nick").push(" (вы)").op("add2").op("setmember")
    a.var("m").push("enabled", False).op("setmember")
    # GPUIButton's own dimming is faint on this dark button; fade it too.
    a.var("m").push("_alpha", 45).op("setmember")
    a.push(True).iftrue("next")
    a.label("other")
    for target in ("m", "mc"):
        a.var(target).push("__nick").var("nick").op("setmember")
        a.var(target).push("__ui").var("ui").op("setmember")
    a.var("_global").member("__onlinePick").var("m").push("release", 3)
    a.var("m").push("addEventListener").op("callmethod").op("pop")
    for event, handler in (("onRelease", "__onlinePick"), ("onRollOver", "__onlineOver"),
                           ("onRollOut", "__onlineOut"), ("onDragOut", "__onlineOut")):
        a.var("mc").push(event).var("_global").member(handler).op("setmember")
    a.label("next")
    a.push("i").var("i").push(1).op("add2").op("definelocal")
    a.push(True).iftrue("row")
    a.label("rows_done")
    a.var("lh").var("pw").push(2)
    a.var("pan").push("setSize").op("callmethod").op("pop")
    a.var("y").push(UNDEF).op("equals2").iftrue("scrolled")
    a.var("y").push(0, 2)
    a.var("pan").push("setPosition").op("callmethod").op("pop")
    a.label("scrolled")
    # The settings window's close cross, over the top right rivet.
    a.push("x", 4, "x", "closeWindow_btn_", 3).var("p").push("attachMovie").op("callmethod")
    a.op("definelocal")
    a.var("x").push("_x").var("W").push(E + 2).op("subtract").op("setmember")
    a.var("x").push("_y", 6).op("setmember")
    a.var("x").push("__ui").var("ui").op("setmember")
    a.var("x").push(1).var("watch").member("buttons").push("push").op("callmethod").op("pop")
    a.var("_global").member("__onlineCross").var("x").push("release", 3)
    a.var("x").push("addEventListener").op("callmethod").op("pop")
    a.var("watch").push(1).var("Mouse").push("addListener").op("callmethod").op("pop")
    a.var("ui").push(1, "__onlineRefresh").op("callfunc").op("pop")
    a.label("out")
    return a


def fn_online_cross():
    a = Asm()
    a.var("this").member("__ui").push(1, "__onlineClose").op("callfunc").op("pop")
    return a


def online_list_art(tags, used):
    """Shapes 581 and 596 in sprites of their own, exported for attachMovie.

    Each sprite places its shape so that the shape's bounds start at 0,0."""
    bounds = {}
    for code, payload, _ in tags:
        if code in (2, 22, 32, 83):
            ident = struct.unpack_from("<H", payload)[0]
            nbits = payload[2] >> 3
            bits = "".join("{:08b}".format(b) for b in payload[2:2 + (5 + 4 * nbits + 7) // 8])
            vals = [int(bits[5 + i * nbits:5 + (i + 1) * nbits], 2) for i in range(4)]
            vals = [v - (1 << nbits) if v >> (nbits - 1) else v for v in vals]
            bounds[ident] = (vals[0], vals[2])        # xmin, ymin in twips
    missing = [shape for _, shape in LIST_ART if shape not in bounds]
    if missing:
        raise SystemExit("the settings window's shapes %s were not found -- not the LAVA client?"
                         % missing)
    out = []
    for name, shape in LIST_ART:
        ident = next(i for i in range(1, 65536) if i not in used)
        used.add(ident)
        tx, ty = (-v for v in bounds[shape])
        n = max(abs(tx), abs(ty)).bit_length() + 1
        bits = "00" + "{:05b}".format(n) + "".join(
            "{:0{}b}".format(v & ((1 << n) - 1), n) for v in (tx, ty))
        bits += "0" * (-len(bits) % 8)
        matrix = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        place = bytes([0x06]) + struct.pack("<HH", 1, shape) + matrix
        body = (struct.pack("<H", (26 << 6) | 0x3F) + struct.pack("<I", len(place)) + place
                + struct.pack("<H", 1 << 6) + struct.pack("<H", 0))
        out.append((39, struct.pack("<HH", ident, 1) + body, True))
        out.append((56, struct.pack("<HH", 1, ident) + name.encode() + b"\0", False))
    return out


def fn_home_ack():
    """Attendance.cmdAck(obj): the original, then for a home registered
    (`this.id == Attendance.SET_HOME && obj.param.res == 0`) the same top
    line ItemActivator raises, closed by the same Timeout."""
    a = Asm()
    a.var("obj").push(1).var("this").push("__wideOrig").op("callmethod").op("pop")
    a.var("this").member("id").var("lol").member("core", "player", "Attendance", "SET_HOME")
    a.op("equals2").op("not").iftrue("out")
    a.var("obj").member("param", "res").push(0).op("equals2").op("not").iftrue("out")
    a.push("topSimple", 1).var("lol").member("core", "SceneShifter")
    a.push("openNewAlert").op("callmethod")
    a.push("label", HOME_SET).op("setmember")
    a.push("topQuery", 2000).var("lol").member("core", "SceneShifter", "closeAlert")
    a.var("lol").member("core", "SceneShifter")
    new(a, ("lol", "utils"), "Timeout", 4).op("pop")
    a.label("out")
    return a


def injected():
    a = Asm()
    for name, fn, params in (
            ("__wideDraw", fn_draw, ("bd", "host", "a", "d", "tx", "ty",
                                     "cx", "cy", "cw", "ch")),
            ("__wideFill", fn_fill, ("mc", "bd", "x0", "y0", "x1", "y1")),
            ("__wideStrip", fn_strip, ("host", "w", "h")),
            ("__wideCorner", fn_corner, ("host", "w", "h")),
            ("__wideSide", fn_side, ("host", "w", "h")),
            ("__wideChat", fn_chat, ("chat", "w")),
            ("__onlineRefresh", fn_online_refresh, ("ui",)),
            ("__onlinePanel", fn_online_panel, ("ui", "w")),
            ("__wideLocationBack", fn_location_back, ("ui", "w", "h")),
            ("__onlineArt", fn_online_art, ("host",)),
            ("__onlineToggle", fn_online_toggle, ("ui",)),
            ("__onlineUpdate", fn_online_update, ("ui",)),
            ("__onlineClose", fn_online_close, ("ui",)),
            ("__onlineForget", fn_online_forget, ("watch",)),
            ("__onlineWatch", fn_online_watch, ()),
            ("__onlineWatchMove", fn_online_watch_move, ()),
            ("__onlineCursor", fn_online_cursor, ("ui", "hidden")),
            ("__onlineNothing", Asm, ()),
            ("__onlinePick", fn_online_pick, ()),
            ("__onlineCross", fn_online_cross, ()),
            ("__onlineOver", lambda: fn_online_hover(True), ()),
            ("__onlineOut", lambda: fn_online_hover(False), ()),
            ("__onlineShow", fn_online_show, ("ui", "y")),
            (MARK, fn_frame, ("ui", "w", "h"))):
        a.var("_global").push(name).function(params, fn()).op("setmember")
    wraps = (
        (("gpui", "view", "ExtViewFrame"), "boundOX", "__wideBoundXOrig",
         (), fn_location_bound("X")),
        (("gpui", "view", "ExtViewFrame"), "boundOY", "__wideBoundYOrig",
         (), fn_location_bound("Y")),
        (("gpui", "RepairInterface"), "calcGoldCostFromAfroCost", "__repairGoldOrig",
         ("afro_cost",), fn_repair_gold()),
        (("core", "objects", "Item"), "getProp", "__repairGetPropOrig",
         ("prop",), fn_repair_cost()),
        (("gpui", "LocationInterface"), "resizeStage", "__wideOrig",
         ("obj",), fn_wrapper(MARK)),
        (("gpui", "GlobalMapInterface"), "resizeStage", "__wideOrig",
         ("obj",), fn_wrapper(MARK)),
        (("services", "ChatPan"), "resizeStage", "__wideOrig",
         ("obj",), fn_wrapper("__wideChat")),
        (("services", "SpecSkillMessages"), "init", "__wideOrig",
         (), fn_messages()),
        (("core", "player", "PersAttributes"), "rp_info", "__progressInfoOrig",
         ("obj",), fn_progress_snapshot()),
        (("core", "player", "NPC"), "userInfo", "__wideOrig",
         ("obj",), fn_services()),
        (("core", "player", "Attendance"), "cmdAck", "__wideOrig",
         ("obj",), fn_home_ack()),
        (("server", "XMLConnection"), "Send", "__onlineSendOrig",
         ("mess",), fn_online_send()),
        (("server", "XMLConnection"), "sendNotification", "__onlineNotifyOrig",
         ("cmd",), fn_online_notification()),
    )
    for method in ("increase_skill_func", "increase_level_func",
                   "increase_spec_func", "increase_spec_level_func"):
        keep = "__progress_" + method
        wraps += ((("core", "player", "PersAttributes"), method, keep,
                   ("obj",), fn_progress_event(keep)),)
    for path, method, keep, params, body in wraps:
        cls = path[-1]
        skip = "skip_%s_%s" % (cls, method)
        pvar = "__wideP" + cls
        # var P = lol.<path>.prototype; wrap P[method] once, keeping the
        # original under P[keep]
        a.push(pvar).var("lol").member(*path).member("prototype").op("definelocal")
        a.var(pvar).push(UNDEF).op("equals2").iftrue(skip)
        a.var(pvar).push(keep).op("getmember").push(UNDEF).op("equals2")
        a.op("not").iftrue(skip)
        a.var(pvar).push(keep).var(pvar).push(method).op("getmember").op("setmember")
        a.var(pvar).push(method).function(params, body).op("setmember")
        a.label(skip)
    # SourceLibrary.create is static, unlike the prototype methods above.
    a.push("__wideLibrary").var("lol").member("display", "SourceLibrary").op("definelocal")
    a.var("__wideLibrary").push(UNDEF).op("equals2").iftrue("library_done")
    a.var("__wideLibrary").member("__wideCreateOrig").push(UNDEF).op("equals2")
    a.op("not").iftrue("library_done")
    a.var("__wideLibrary").push("__wideCreateOrig").var("__wideLibrary").member("create").op("setmember")
    a.var("__wideLibrary").push("create").function((), fn_source_library()).op("setmember")
    a.label("library_done")
    # So is SceneShifter.locationScene.
    a.push("__wideShifter").var("lol").member("core", "SceneShifter").op("definelocal")
    a.var("__wideShifter").push(UNDEF).op("equals2").iftrue("scene_done")
    a.var("__wideShifter").member("__wideSceneOrig").push(UNDEF).op("equals2")
    a.op("not").iftrue("scene_done")
    a.var("__wideShifter").push("__wideSceneOrig").var("__wideShifter").member("locationScene").op("setmember")
    a.var("__wideShifter").push("locationScene").function((), fn_location_scene()).op("setmember")
    a.label("scene_done")
    a.op("end")
    return a.assemble()


def without_online_art(tags):
    """Remove only our own exports and what they define, when repatching."""
    out = list(tags)
    for name in [ONLINE_BITMAP, *ONLINE_OLD_BITMAPS] + [n for n, _ in LIST_ART]:
        name = name.encode() + b"\0"
        exports = [t for t in out if t[0] == 56 and t[1][:2] == b"\1\0"
                   and t[1][4:] == name]
        if len(exports) > 1:
            raise ValueError("duplicate export %r" % name)
        if not exports:
            continue
        ident = exports[0][1][2:4]
        out = [t for t in out if t != exports[0]
               and not (t[0] in (21, 39) and t[1][:2] == ident)]
    return out


def png_pixels(png):
    """8-bit RGBA PNG -> (width, height, rows of RGBA bytes); no PIL here."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    at, data, head = 8, b"", None
    while at < len(png):
        size, kind = struct.unpack_from(">I4s", png, at)
        body = png[at + 8:at + 8 + size]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            data += body
        at += 12 + size
    width, height, depth, colour, _, _, interlace = head
    if (depth, colour, interlace) != (8, 6, 0):
        raise ValueError("online panel must be 8-bit RGBA, not interlaced")
    raw, stride, rows, prev = zlib.decompress(data), width * 4, [], bytearray(width * 4)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up, corner = prev[i], (prev[i - 4] if i >= 4 else 0)
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
        rows.append(line)
        prev = line
    return width, height, rows


def online_icon():
    """The people icon out of the counter's PNG, its plate made transparent.

    The pixels are the PNG's own; only the alpha is new, from how far each
    one stands out of the dark plate, so the icon keeps its soft edges and
    does not carry a square of the old plate onto the new one."""
    width, height, rows = png_pixels(ONLINE_ASSET.read_bytes())
    if (width, height) != (ONLINE_WIDTH, 28):
        raise ValueError("online panel must be a 76x28 PNG")
    x0, y0, w, h = ONLINE_ICON
    raw = b""
    for y in range(y0, y0 + h):
        line = bytearray(b"\0")
        for x in range(x0, x0 + w):
            r, g, b, alpha = rows[y][x * 4:x * 4 + 4]
            light = (r + g + b) // 3
            alpha = alpha * max(0, min(95, light - 55)) // 95
            line += bytes((r, g, b, alpha))
        raw += line

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def online_art(tags):
    """PNG in DefineBitsJPEG2 (Flash 8+), exported for BitmapData.loadBitmap."""
    definitions = {2, 6, 7, 10, 11, 14, 20, 21, 22, 32, 33, 34, 35, 36,
                   37, 39, 46, 48, 60, 75, 83, 84, 87, 90, 91}
    used = set()

    def collect(items):
        for code, payload, _ in items:
            if code in definitions:
                used.add(struct.unpack_from("<H", payload)[0])
            if code == 39:
                # A sprite's tag stream follows its ID and frame count.
                collect(split_tags(b"\x08\0\0\0\0\0" + payload[4:]))

    collect(tags)
    ident = next(i for i in range(1, 65536) if i not in used)
    used.add(ident)
    bitmap = (21, struct.pack("<H", ident) + online_icon(), True)
    export = (56, struct.pack("<HH", 1, ident) + ONLINE_BITMAP.encode() + b"\0", False)
    return [bitmap, export] + online_list_art(tags, used)


def inject(tags):
    """Put the DoAction before the first ShowFrame, replacing an earlier one."""
    tags = [t for t in tags if not (t[0] == 12 and MARK.encode() in t[1])]
    tags = without_online_art(tags)
    at = next(k for k, t in enumerate(tags) if t[0] == 1)
    tags[at:at] = online_art(tags) + [(12, injected(), True)]
    return tags


# --- reading it back --------------------------------------------------------

def disassemble(code):
    """Opcode names in order, descending into function bodies."""
    names = {v: k for k, v in OPS.items()}
    names.update({0x96: "push", 0x9B: "function", 0x9D: "iftrue"})
    out, i = [], 0
    while i < len(code):
        op = code[i]
        if op < 0x80:
            out.append(names.get(op, "0x%02X" % op))
            i += 1
            continue
        (ln,) = struct.unpack_from("<H", code, i + 1)
        out.append(names.get(op, "0x%02X" % op))
        i += 3 + ln                  # a function body simply follows inline
    return out


def verify(path, max_w, max_h):
    _, body = read_swf(path)
    tags = split_tags(body)
    mine = [t[1] for t in tags if t[0] == 12 and MARK.encode() in t[1]]
    if len(mine) != 1:
        raise SystemExit("verify: expected one injected DoAction, found %d" % len(mine))
    if mine[0] != injected():
        raise SystemExit("verify: the DoAction in the file is not the one assembled")
    if inject(tags) != tags:
        raise SystemExit("verify: online artwork is missing, changed or duplicated")
    ops = disassemble(mine[0])
    unknown = [o for o in ops if o.startswith("0x")]
    if unknown:
        raise SystemExit("verify: opcodes nobody here meant: %s" % unknown)
    first_show = next(k for k, t in enumerate(tags) if t[0] == 1)
    pos = next(k for k, t in enumerate(tags) if t[0] == 12 and MARK.encode() in t[1])
    if pos != first_show - 1:
        raise SystemExit("verify: the DoAction is not the last tag of frame 1")
    ceiling = patch_ceiling(list(tags), max_w, max_h)
    for name, (old, new_value) in ceiling.items():
        if old != new_value:
            raise SystemExit("verify: %s is %d, wanted %d" % (name, old, new_value))
    return len(ops), len(mine[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--max", default="3840x2160",
                    help="layout ceiling, WxH (the client ships 1280x1024)")
    ap.add_argument("--check", action="store_true",
                    help="only report what the file already carries")
    args = ap.parse_args(argv)
    max_w, max_h = (int(v) for v in args.max.lower().split("x"))

    version, body = read_swf(args.src)
    tags = split_tags(body)
    if args.check:
        before = patch_ceiling(list(tags), 0, 0)
        has = any(t[0] == 12 and MARK.encode() in t[1] for t in tags)
        print("ceiling %dx%d, frame tiling %s" % (
            before["maxW"][0], before["maxH"][0], "present" if has else "absent"))
        return 0
    if not args.dst:
        ap.error("an output path is needed")

    ceiling = patch_ceiling(tags, max_w, max_h)
    tags = inject(tags)
    write_swf(args.dst, version, join_tags(body[:header_len(body)], tags))
    count, size = verify(args.dst, max_w, max_h)
    for name, (old, new_value) in sorted(ceiling.items()):
        print("%s: %d -> %d" % (name, old, new_value))
    print("frame tiling: %d actions, %d bytes, read back and matched" % (count, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
