#!/usr/bin/env python3
"""Build the films the launcher points the projector at instead of main.swf.

    python3 tools/make_wrapper.py            both films
    python3 tools/make_wrapper.py --debug    both, with trace(), into dist/.build

launcher/assets/wrapper.swf is the film that makes the game bigger (16:9,
opt-in with LAVA_SCALE). launcher/assets/wrapper_plain.swf is the same film
without any of the scaling -- main.swf's own 950x650 stage, the game at the
origin, nothing done to Stage or _quality -- opt-in with LAVA_PLAIN. Both
exist for a second reason as well, which has nothing to do with size: they
are the only code of ours that runs inside the client, and the client has a
bug that only code inside it can mend. See CLAN INSPECTOR below.

Neither is the default, and the reason is the one that kept the 16:9 film
opt-in: a game loaded into either of them stops taking clicks on the ground,
so the character cannot walk. The plain film settled that the stage is not
to blame (it never touches the stage and loses the clicks all the same: six
clicks posted to the projector walked four times on main.swf, never in
either film). Until that is cured, players get main.swf on level 0 and with
it the deaf clan window; the mend is here, pinned and proven, for the day a
film becomes the default.

WHY THERE IS A WRAPPER AT ALL

main.swf is drawn at 950x650 and sets Stage.scaleMode = "noScale" in its own
frame script, which tells the player never to stretch it. A maximised window
therefore does not enlarge the game, it only paints black around it, and
SceneShifter.setMCSize cannot help: its maxW/maxH are used for centring
offsets and nowhere else.

Scale belongs to the stage, and the stage belongs to whoever is on level 0.
So this film takes level 0, sets scaleMode = "exactFit", and loads the game
into a clip inside itself. The game is not modified -- it is loaded, and it
goes on reading _root, which is this timeline and carries the flashvars the
projector was started with.

The game sets noScale as it initialises, so a second clip, "keeper", spins
two empty frames forever and puts exactFit back on each one. Crude; it is the
only lever there is from outside a film.

TWO RULES THIS FILE FOLLOWS, BOTH PAID FOR

1. No GetURL2. The first version of this wrapper loaded the game with it, the
   target flag was wrong, and Flash's fallback for a target it cannot resolve
   is to hand the URL to the browser -- 478 copies of main.swf in the
   downloads folder, 800 MB, in thirty seconds. loadMovie is called here as a
   method of the clip instead: if anything is wrong with it, nothing happens.

2. Nothing is assembled from memory. Every opcode below was first read back
   out of main.swf with tools/swf_actions.py, which is also what checks this
   file's own output before it is ever run.

main.swf is AVM1 (FileAttributes has the AS3 bit clear, 831 DoInitAction
tags), which is why one virtual machine holds both films and _root reaches
across.

CLAN INSPECTOR

lol.core.clans.ClanInspector is a singleton, and it goes deaf. When the game
socket closes -- a server restart, a dropped line, a logout -- its onClose
calls kill(), which takes every one of its listeners off the connection
(fellow, invite, gg_list, gg_struct, gg_code, the userInfo_* family, onClose)
and off Master (changeState). Master.onClose then rebuilds the session:
finish -> start -> initClanInspector -> ClanInspector.getInstance(). But
kill() never let go of sInstance, so getInstance hands back the same dead
object, init() is not run again, and SceneShifter.initClanInspectorListeners
subscribes the scene to it. From then until the client is restarted the clan
side hears nothing: a member's roster is never asked for (firstRequest waits
on the fellow frame it no longer receives), and the founding page asks the
price with gg_info det=6, the server answers gg_list res=6, and the window
stays blank -- which is how the owner found it, on the evening of the first
deploy after clans went live.

The mend is one method, replaced at run time: ClanInspector.prototype.kill
becomes the original kill, then the two lines MailInspector.kill already
uses to let go of its own singleton (sInstance = null; delete sInstance), then
Master.getInstance().initClanInspector() -- which is what Master.start would
have done, and which builds a fresh inspector with all its listeners and
subscribes the scene to it. See clan_inspector_patch() for why it is kill and
not onClose, and why the fresh one is built right there rather than left to
Master. main.swf itself is not touched.

Seen on the real client, both films (debug projector, a throwaway server
restarted under it, the second login made in the same SWF the way the login
button makes it): without the mend nothing is left listening on gg_list after
the second login, the founding page's price field stays empty and a member
never asks for his roster; with it there is one listener, the field reads 10
and the member sends gg_info det=1 by himself, as at the first login.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "launcher", "assets", "wrapper.swf")
OUT_DEBUG = os.path.join(ROOT, "dist", ".build", "wrapper_debug.swf")
OUT_PLAIN = os.path.join(ROOT, "launcher", "assets", "wrapper_plain.swf")
OUT_PLAIN_DEBUG = os.path.join(ROOT, "dist", ".build", "wrapper_plain_debug.swf")

# THE STAGE IS THE LEVER, and for a while it was the mistake. Under showAll
# the game reads Stage.width/height from the film on level 0 -- this one --
# not from the window. Copying main.swf.s own 950x650 here therefore told the
# game to lay itself out small no matter how big the window was.
#
# 1280x720 is 16:9, and it is the largest 16:9 the client has anything to say
# about. SceneShifter.setMCSize clamps the layout to maxW = 1280 and then puts
# the scene at (Stage.width - maxW) / 2, so a wider stage buys no more field,
# only bare stage down either side. Height is what 16:9 costs: the client would
# lay out to maxH = 1024 if it were asked, and 720 is the price of the shape.
#
# Against main.swf.s own 950x650 that is 330 more pixels across and 70 more
# down, and in a window of exactly this size not one of them is scaled -- the
# gain is field of view, not magnification.
#
# The frame rate must still match main.swf: level 0 sets the pace for
# everything loaded beneath it.
WIDTH, HEIGHT = 1280, 720
FRAME_RATE = 25.0
MOVIE = "main.swf"          # beside the wrapper, so relative paths hold
GAME = "game"               # the clip the film is loaded into
KEEPER = "keeper"           # the clip that keeps putting exactFit back

GAME_ID, KEEPER_ID = 1, 2

# main.swf.s own size, and where the offset below comes from. The game
# believes the player centres it and corrects for that itself --
# SceneShifter.setMCSize (recon/as-src/lol/core/SceneShifter.as:91-92) does
#     linkGame._x = Math.round((minW - Stage.width) / 2)
#     linkGame._y = Math.round((minH - Stage.height) / 2)
# with minW/minH = 950/650. That is the move which reaches the window.s top
# left corner when a 950x650 film sits in the middle of a wider stage. Put the
# clip in the corner instead and the same correction drags the whole interface
# up and to the left, cutting off the top bar and leaving black at the right --
# which is exactly what it did. So the clip goes where the game already thinks
# it is, in the centre, and the two cancel.
ART_W, ART_H = 950, 650

# showAll, not exactFit. exactFit fills the window by ignoring the shape of
# the picture: 950x650 pulled onto 1904x984 stretches half again as much
# across as down, and every face and wheel in the game comes out squat.
# showAll scales as far as it can while keeping the proportions, and leaves
# a band at the sides -- which the launcher then removes by sizing the window
# to the picture rather than to the screen.
SCALE_MODE = "showAll"


# --- AVM1 ------------------------------------------------------------------

class Reg(int):
    """A register, for push(): Reg(1) is 'reg:1' in swf_actions, which inside
    a method whose DefineFunction2 preloads this (flags 0x29,0x00 -- every
    method of ClanInspector) is `this`."""


def push(*values):
    """ActionPush. Strings go as type 0, booleans as type 5, None as type 2
    (null), a Reg as type 4, other numbers as type 1 (float), which is what
    the real compiler emits for an argument count (see swf_actions on
    main.swf: 'Push 0.0, const8:1' before every CallMethod). main.swf's
    MailInspector.kill pushes null exactly this way ('sInstance', null), and
    every method pushes reg:1 for this."""
    body = b""
    for v in values:
        if isinstance(v, str):
            body += b"\x00" + v.encode("utf-8") + b"\x00"
        elif isinstance(v, bool):
            body += b"\x05" + bytes([1 if v else 0])
        elif v is None:
            body += b"\x02"
        elif isinstance(v, Reg):
            body += b"\x04" + bytes([int(v)])
        else:
            body += b"\x01" + struct.pack("<f", float(v))
    return b"\x96" + struct.pack("<H", len(body)) + body


GET_VARIABLE = b"\x1c"
GET_MEMBER = b"\x4e"
SET_MEMBER = b"\x4f"
CALL_METHOD = b"\x52"
POP = b"\x17"
STOP = b"\x07"
TRACE = b"\x26"
END = b"\x00"
# Read out of main.swf for the ClanInspector patch, each where the decompiled
# source says what it is: Not/If from getInstance's `if(!sInstance)` (Not,
# Not, If) and getInbox's `if(this.firstGetInbox)` (Not, If); Delete from
# MailInspector.kill's `delete lol.core.mail.MailInspector.sInstance` (Push
# the object and the name, Delete, Pop); DefineFunction2 from every method.
NOT = b"\x12"
DELETE = b"\x3a"


def if_true(skip):
    """ActionIf: jump over the next `skip` bytes when the value popped is
    true. The offset counts from the end of this action."""
    return b"\x9d" + struct.pack("<H", 2) + struct.pack("<h", skip)


def when(cond, body):
    """if (cond) { body } -- as main.swf compiles it: the condition, Not, and
    an If that jumps over the body when the Not came out true. when(x + NOT,
    ...) is therefore if (!x), and comes out Not, Not, If, like getInstance."""
    return cond + NOT + if_true(len(body)) + body


def chain(*names):
    """names[0].names[1]...: GetVariable for the first, GetMember for the
    rest, the shape of every `lol.core.x.Y` in main.swf."""
    out = push(names[0]) + GET_VARIABLE
    for n in names[1:]:
        out += push(n) + GET_MEMBER
    return out


def method2(body, registers=2, flags=(0x29, 0x00)):
    """DefineFunction2 for an anonymous method of no parameters, with its
    body. Flags 0x29,0x00 and two registers are what main.swf gives every
    ClanInspector method: preload this into reg:1, suppress arguments and
    super. The header is name '' (one NUL), no parameters, the register
    count, the two flag bytes and the body's length; the body follows the
    action in the stream, and the function object is left on the stack."""
    header = b"\x00" + struct.pack("<H", 0) + bytes([registers]) + bytes(flags) \
        + struct.pack("<H", len(body))
    return b"\x8e" + struct.pack("<H", len(header)) + header + body


def trace_member(obj, member):
    """trace(obj.member) -- only built with --debug, and only to answer the
    one question a person cannot answer by looking at a loading screen:
    whether exactFit is still in force after the game has had its say."""
    return push(obj) + GET_VARIABLE + push(member) + GET_MEMBER + TRACE


def set_scale_mode(mode=SCALE_MODE):
    """Stage.scaleMode = mode. SetMember pops value, name, object."""
    return push("Stage") + GET_VARIABLE + push("scaleMode", mode) + SET_MEMBER


def set_quality(level="BEST"):
    """_root._quality = level.

    The reason the enlarged picture looked like porridge. A location's
    background is a JPEG, and the projector runs at HIGH by default, where
    vectors are anti-aliased but bitmaps are NOT smoothed -- so a photograph
    blown up twice over is resampled by nearest neighbour. BEST is the one
    level that smooths bitmaps as well.

    Neither "BEST" nor "HIGH" appears anywhere in main.swf, so the game never
    sets this itself and nothing fights us for it; it is re-asserted on every
    keeper frame anyway, for the same reason scaleMode is.
    """
    return push("_root") + GET_VARIABLE + push("_quality", level) + SET_MEMBER


def root_member(name):
    """_root.<name> on the stack."""
    return push("_root") + GET_VARIABLE + push(name) + GET_MEMBER


def lock_root():
    """_root.game._lockroot = true.

    This is the lever the whole thing turned on. A film loaded into a clip
    normally keeps reading the LOADER's _root -- so the game was looking for
    logged on the wrapper's timeline while its own classes resolved _root
    somewhere else entirely, found nothing, and Session.loadSBase quietly took
    the branch that never asks loaduser. With _lockroot the loaded film is its
    own _root, which is the timeline hand_down() writes the flashvars onto, so
    both halves finally point at the same place.

    Set before the film is loaded, because it decides what _root means while
    the film initialises, and again on every keeper frame in case the load
    resets it.
    """
    return (root_member(GAME) + push("_lockroot", True) + SET_MEMBER)


def hand_down(name):
    """_root.game.<name> = _root.<name>.

    The flashvars arrive on the wrapper's own timeline, because that is the
    film the projector was pointed at. The game then reads _root.logged --
    and for a film loaded into a clip, which timeline _root means is exactly
    the thing that differs between player builds. So the value is put on the
    clip as well: whichever of the two the game ends up reading, it finds it.

    Done on every frame of the keeper rather than once, because the clip's
    variables are wiped when the film lands in it, and the game only looks at
    logged several seconds later, once SBase has finished loading.
    """
    return (root_member(GAME) + push(name) + root_member(name) + SET_MEMBER)


def call_method(obj, method, *args):
    """obj.method(args...) -- arguments in reverse, then how many, then the
    object, then the name. The return value is dropped."""
    out = b""
    for a in reversed(args):
        out += push(a)
    out += push(len(args))
    out += push(obj) + GET_VARIABLE
    out += push(method) + CALL_METHOD + POP
    return out


CLAN_INSPECTOR = ("lol", "core", "clans", "ClanInspector")
# Where the original kill is kept. A name the client never uses, on the
# prototype, so every inspector -- the one alive when the patch lands and
# every one built after -- finds it.
SAVED_KILL = "rebornKill"


def clan_inspector_patch(debug=False):
    """Mend ClanInspector once main.swf has defined it; see CLAN INSPECTOR.

        if (!ClanInspector.prototype.rebornKill) {        // not yet mended
            if (ClanInspector.prototype.kill) {           // the class exists
                ClanInspector.prototype.rebornKill = ClanInspector.prototype.kill;
                ClanInspector.prototype.kill = function () {
                    this.rebornKill();
                    ClanInspector.sInstance = null;
                    delete ClanInspector.sInstance;
                    lol.core.Master.getInstance().initClanInspector();
                };
            }
        }

    Runs on every keeper frame and does its work on the first one after the
    class appears; after that it is two property reads.

    WHY kill AND NOT onClose. LEventDispatcher.addEventListener stores the
    listener as [object, object[event]] -- the function itself, looked up at
    the moment of subscribing. The inspector subscribes in init(), 100 ms
    after Master is built, and nothing guarantees the keeper has run by then.
    A replacement onClose would therefore never be called for an inspector
    that subscribed first; worse, kill()'s removeEventListener("onClose",
    this) looks this.onClose up AGAIN, finds the replacement, matches nothing
    in the queue, and leaves the original subscribed for ever. kill is found
    at the moment of the call (this.kill() in onClose), and nothing anywhere
    keeps a copy of it, so a new kill reaches every inspector, whenever it
    was born. It is only ever called from onClose.

    WHY THE FRESH ONE IS BUILT HERE. The connection calls its onClose
    listeners in the order LEventDispatcher.dispatchQueue's for-in walks the
    array, and that order is the player's. Flash walks it from the last
    index down, which puts the inspector (subscribed after Master) first --
    seen in the debug projector: the --debug trace in kill prints Master's
    currentLocation as an object, and Master.finish deletes it -- and
    Master.finish -> start -> initClanInspector would then find the
    singleton gone and build the fresh one by itself. Built here, the order
    stops mattering: if Master went first, it subscribed the scene to the
    dead inspector and this subscribes it to the live one; if Master comes
    after, its getInstance finds this one and subscribing the scene again is
    a no-op (addEventListener takes a duplicate out before it pushes). The
    fresh inspector's own onClose, added in the middle of the dispatch, is
    past the keys for-in collected before its first call -- and should a
    forward walk reach it anyway, because taking the dead one out shifted
    the array, it is dropped and rebuilt once more and the end is the same:
    one live inspector, listening, with the scene subscribed to it.
    """
    proto = chain(*CLAN_INSPECTOR + ("prototype",))
    kill = (push(0, Reg(1), SAVED_KILL) + CALL_METHOD + POP
            + chain(*CLAN_INSPECTOR) + push("sInstance", None) + SET_MEMBER
            + chain(*CLAN_INSPECTOR) + push("sInstance") + DELETE + POP
            + push(0, 0) + chain("lol", "core", "Master") + push("getInstance")
            + CALL_METHOD + push("initClanInspector") + CALL_METHOD + POP)
    if debug:
        # Master.finish deletes currentLocation, so the second line says
        # which of the two onClose listeners the player called first: an
        # object means the inspector, undefined means Master.
        kill = (push("reborn: ClanInspector.kill -> fresh inspector") + TRACE
                + chain("lol", "core", "Master", "sInstance", "currentLocation")
                + TRACE + kill)
    install = (proto + push(SAVED_KILL) + proto + push("kill") + GET_MEMBER + SET_MEMBER
               + proto + push("kill") + method2(kill) + SET_MEMBER)
    if debug:
        install += push("reborn: ClanInspector mended") + TRACE
    return when(proto + push(SAVED_KILL) + GET_MEMBER + NOT,
                when(proto + push("kill") + GET_MEMBER, install))


# --- SWF -------------------------------------------------------------------

def tag(code, body):
    if len(body) < 0x3F:
        return struct.pack("<H", (code << 6) | len(body)) + body
    return struct.pack("<HI", (code << 6) | 0x3F, len(body)) + body


def sprite(sprite_id, frames):
    """DefineSprite: each frame is a blob of actions, possibly empty."""
    body = struct.pack("<HH", sprite_id, len(frames))
    for actions in frames:
        if actions:
            body += tag(12, actions + END)
        body += tag(1, b"")
    return tag(39, body + tag(0, b""))


def matrix(tx_px=0, ty_px=0):
    """A MATRIX carrying nothing but a translation, in twips."""
    if not tx_px and not ty_px:
        return b"\x00"                      # no scale, no rotate, no translate
    tx, ty = int(round(tx_px * 20)), int(round(ty_px * 20))
    n = max(tx.bit_length(), ty.bit_length()) + 1     # +1 for the sign bit
    bits = "00" + format(n, "05b")          # HasScale = 0, HasRotate = 0
    for v in (tx, ty):
        bits += format(v & ((1 << n) - 1), "0%db" % n)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def place(sprite_id, depth, name, tx=0, ty=0):
    # has character (0x02) + has matrix (0x04) + has name (0x20).
    return tag(26, bytes([0x02 | 0x04 | 0x20]) + struct.pack("<H", depth)
               + struct.pack("<H", sprite_id) + matrix(tx, ty)
               + name.encode("utf-8") + b"\x00")


def rect(xmax_twips, ymax_twips):
    nbits = 16
    bits = format(nbits, "05b")
    for v in (0, xmax_twips, 0, ymax_twips):
        bits += format(v & 0xFFFF, "016b")
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def build(debug=False, scale=True, mend=True):
    """The film. scale=True is wrapper.swf, the 16:9 one; scale=False is
    wrapper_plain.swf: main.swf's own stage (950x650), the game at the
    origin, and nothing said to Stage or _quality -- meant to differ from
    main.swf on level 0 only by the ClanInspector mend, and which differs
    by the lost clicks as well (see the top of this file).
    mend=False leaves the mend out -- the film as it was before it, kept so
    the two can be compared on a live client."""
    # The load target: one empty frame, and nothing of ours inside it,
    # because loading a film into a clip throws away whatever was there.
    game = sprite(GAME_ID, [b""])
    # The keeper: two frames so that it actually loops and re-runs its
    # script; a one-frame clip sits on its only frame and the script would
    # run once.
    watch = (trace_member("Stage", "scaleMode") + trace_member("Stage", "width")
             if debug else b"")
    vars_down = lock_root() + b"".join(hand_down(v) for v in
                         ("logged", "var_host", "var_port", "vversion", "session"))
    # Last on each frame, after everything the film already did, so that the
    # 16:9 film's frames are what they were with the mend appended.
    patch = clan_inspector_patch(debug) if mend else b""
    scale_first = set_scale_mode() + set_quality() if scale else b""
    keeper = sprite(KEEPER_ID, [scale_first + vars_down + patch,
                                scale_first + vars_down + patch + watch])

    root_actions = (scale_first
                    + lock_root()
                    + call_method(GAME, "loadMovie", MOVIE)
                    + STOP + END)

    if scale:
        width, height = WIDTH, HEIGHT
        at = ((WIDTH - ART_W) / 2.0, (HEIGHT - ART_H) / 2.0)
    else:
        # main.swf's own stage, so the projector lays the window out exactly
        # as it does for main.swf, and the game at the origin, so every
        # coordinate in it is the same number it would be on level 0 --
        # _root._xmouse, which the game hands to hitTest as if it were a
        # stage coordinate (SceneObject.as:70, BagInterface.as:238), included.
        width, height = ART_W, ART_H
        at = (0, 0)

    body = (tag(9, b"\x00\x00\x00")            # black behind everything
            + game + keeper
            + place(GAME_ID, 1, GAME, *at)
            + place(KEEPER_ID, 2, KEEPER)
            + tag(12, root_actions)
            + tag(1, b"")
            + tag(0, b""))

    header = (rect(width * 20, height * 20)
              + struct.pack("<H", int(round(FRAME_RATE * 256)))
              + struct.pack("<H", 1))          # one frame: the load runs once
    return b"FWS" + bytes([8]) + struct.pack("<I", 8 + len(header) + len(body)) \
        + header + body


def main():
    debug = "--debug" in sys.argv
    global WIDTH, HEIGHT
    for k, a in enumerate(sys.argv):
        if a == "--stage":
            WIDTH, HEIGHT = (int(x) for x in sys.argv[k + 1].lower().split("x"))
    for scale, out, dbg_out in ((True, OUT, OUT_DEBUG), (False, OUT_PLAIN, OUT_PLAIN_DEBUG)):
        data = build(debug, scale)
        out = dbg_out if debug else out
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as fh:
            fh.write(data)
        w, h = (WIDTH, HEIGHT) if scale else (ART_W, ART_H)
        print("%s: %d байт, сцена %dx%d, %.0f кадр/с"
              % (os.path.relpath(out, ROOT), len(data), w, h, FRAME_RATE))
    print("проверить: python3 tools/swf_actions.py launcher/assets/wrapper_plain.swf")
    print("           python3 tools/test_wrapper.py")


if __name__ == "__main__":
    sys.exit(main())
