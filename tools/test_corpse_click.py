"""Client patch: a dead creature no longer takes the click meant for its bag.

lch;dead=<id> lays the figure down, but in the original its SpriteFocus
lives on until lch;lostUser, CORPSE_DELAY later: the body stays the target
under the pointer and the selected one, so a click on it, or on the bag
under it, goes out as a blow at the dead and comes back as error 12.

In process: the real bytecode of both wrappers (DisplayLocScene.dead and
CursorManager.removeFocus) runs against a model of the client's focus
classes, written line for line from recon/as-src/lol (SpriteFocusManager,
TargetList, CursorManager), down to TargetList.removeTarget's
splice(null, 1), which in Flash cuts the first entry (splice(undefined, 1),
SpriteFocusManager's, cuts nothing; measured in Flash 32): what a second
removeFocus for the same sprite does to somebody else's target.

Real Flash (LAVA_FLASH_PLAYER and LAVA_RES, Windows): the patched client
logs in to a server of its own, and a probe walks two figures of the
location through the client's own Location.lch: the pointer over both,
the other selected, then it, then dead=<it>, then lostUser=<it>. Run three
times: the original's focus code, the dead wrapper without the removeFocus
guard, and the patch as built.
"""
import ast
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import zlib

HERE = Path(__file__).resolve().parent
SERVER = HERE.parent / "server"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SERVER))
import widescreen as w  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- a small AVM1 executor ---------------------------------------------------

class Undefined:
    def __repr__(self):
        return "undefined"


U = Undefined()


def loose_equal(a, b):
    """equals2 as far as these wrappers need it: undefined == null."""
    if a is U or a is None or b is U or b is None:
        return (a is U or a is None) and (b is U or b is None)
    return a == b


def get(target, key):
    if isinstance(target, dict):
        return target.get(key, U)
    if target in (U, None):
        return U
    return getattr(target, key, U)


def execute(code, env):
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
                elif kind == 2:
                    stack.append(None)
                elif kind == 3:
                    stack.append(U)
                elif kind == 5:
                    stack.append(bool(payload[p]))
                    p += 1
                elif kind == 7:
                    stack.append(struct.unpack_from("<i", payload, p)[0])
                    p += 4
                else:
                    raise AssertionError("unexpected push type: %s" % kind)
        elif op == 0x1C:
            stack.append(env.get(stack.pop(), U))
        elif op == 0x3C:
            value, name = stack.pop(), stack.pop()
            env[name] = value
        elif op == 0x4E:
            key, target = stack.pop(), stack.pop()
            stack.append(get(target, key))
        elif op == 0x4F:
            value, key, target = stack.pop(), stack.pop(), stack.pop()
            setattr(target, key, value)
        elif op == 0x52:
            method, target, count = stack.pop(), stack.pop(), stack.pop()
            args = [stack.pop() for _ in range(count)]
            fn = get(target, method)
            # Calling a method of undefined does nothing in AVM1.
            stack.append(U if fn is U else fn(*args))
        elif op == 0x42:
            count = stack.pop()
            stack.append([stack.pop() for _ in range(count)])
        elif op == 0x49:
            b, a = stack.pop(), stack.pop()
            stack.append(loose_equal(a, b))
        elif op == 0x12:
            stack.append(not stack.pop())
        elif op == 0x17:
            stack.pop()
        elif op == 0x9D:
            if stack.pop():
                at += struct.unpack("<h", payload)[0]
        else:
            raise AssertionError("unexpected opcode: %02x" % op)
    if stack:
        raise AssertionError("wrapper leaked stack values: %r" % stack)


LOL = dict(core=dict(player=dict(Gamer=dict(ID=0))))


def splice_one(items, i):
    """Array.splice(i, 1) as Flash 32 does it: a null start counts as 0,
    an undefined one removes nothing."""
    if i is U:
        return
    i = 0 if i is None else i
    del items[i:i + 1]


# --- the original focus code, from recon/as-src/lol --------------------------

class Sprite:
    def __init__(self, ident, kind, depth):
        self.id, self.kind, self.depth = ident, kind, depth
        self.filters = []
        self.behavior = "stand"


class SpriteFocus:
    def __init__(self, target):
        self.target, self.activated, self.glow = target, True, False

    def activate(self, a):
        self.activated = a

    def flare(self, f):
        self.glow = f

    def kill(self):
        self.activate(False)
        self.flare(False)


class SpriteFocusManager:
    def __init__(self):
        self.sf_arr, self.overArr, self.flared = [], [], None
        self.listener = None

    def getFocus(self, targ):
        for f in self.sf_arr:
            if f.target is targ:
                return f
        return U

    def getIndex(self, targ):
        for i, f in enumerate(self.sf_arr):
            if f.target is targ:
                return i
        return U

    def removeFocus(self, targ):          # SpriteFocusManager.as removeFocus
        f = self.getFocus(targ)
        if f is not U:
            f.activate(False)
        if loose_equal(f, self.flared):
            self.flared = None
            self.listener.spriteOver(dict(flared=U))
        for i, o in enumerate(self.overArr):
            if o is f:
                del self.overArr[i]
                break
        splice_one(self.sf_arr, self.getIndex(targ))
        if f is not U:
            f.kill()

    def over(self, targ):
        """The pointer comes onto a sprite: SpriteFocus.__onMouseMove."""
        self.overArr.append(self.getFocus(targ))
        self.checkOvered()

    def checkOvered(self):                # SpriteFocusManager.as checkOvered
        if self.overArr:
            top = -1
            for o in self.overArr:
                o.flare(False)
                if o.target.depth > top:
                    self.flared, top = o, o.target.depth
            self.flared.flare(True)
        else:
            self.flared = None
        self.listener.spriteOver(dict(flared=self.flared))
        return self.flared


class TargetList:
    def __init__(self, cm):
        self.target_list, self.currentTarget, self.cm = [], U, cm

    def index(self, ident):
        for i, t in enumerate(self.target_list):
            if t == ident:
                return i
        return None

    def addTarget(self, ident):
        if self.index(ident) is None:
            self.target_list.append(ident)

    def removeTarget(self, ident):        # TargetList.as removeTarget
        splice_one(self.target_list, self.index(ident))

    def nextTarget(self):                 # TargetList.as nextTarget
        i = self.index(self.currentTarget)
        i = (0 if i is None else i) + 1
        if i >= len(self.target_list):
            i = 0
        self.currentTarget = self.target_list[i] if i < len(self.target_list) else U
        if self.currentTarget is not U:
            self.cm.changeTargetHandler(self.currentTarget)


class CursorManager:
    def __init__(self, scene):
        self.scene, self.selected = scene, None
        self.sfManager = SpriteFocusManager()
        self.sfManager.listener = self
        self.targetList = TargetList(self)
        self.modes = []

    def spriteOver(self, obj):
        pass

    def original_removeFocus(self, targ):  # CursorManager.as removeFocus
        self.targetList.removeTarget(get(targ, "id"))
        if loose_equal(self.selected, self.sfManager.getFocus(targ)):
            self.selected = None
            self.targetList.nextTarget()
        self.sfManager.removeFocus(targ)

    def select(self, focus):
        if self.selected:
            self.selected.target.filters = []
        self.selected = focus
        focus.target.filters = ["glow"]
        self.targetList.addTarget(focus.target.id)

    def changeTargetHandler(self, ident):
        self.select(self.sfManager.getFocus(self.scene.getWalker(ident)))

    def mouse_up(self):
        """What a click does: CursorManager.__onMouseUp, with a fist
        (itemActionMap.fist) and the targetActionMap."""
        flared = self.sfManager.flared
        kind = flared.target.kind if flared else "hex"
        if flared and self.selected and flared is self.selected:
            return dict(mob="strike", bag="take", hex="move")[kind]
        return dict(mob="select", bag="take", hex="move")[kind]


class Scene:
    def __init__(self, patched, guard=True):
        self.cursorManager = CursorManager(self)
        cm = self.cursorManager
        self.playerList, self.gamer_mc = {}, Sprite(0, "gamer", 5)
        self.playerList[0] = self.gamer_mc
        # setattr: a name with two underscores would be mangled here
        setattr(cm, "__corpseFocusOrig", cm.original_removeFocus)
        if guard:
            cm.removeFocus = lambda targ: execute(
                w.fn_corpse_focus().assemble(), dict(this=cm, targ=targ, lol=LOL))
        else:
            cm.removeFocus = cm.original_removeFocus
        setattr(self, "__corpseDeadOrig", self.original_dead)
        if patched:
            self.dead = lambda obj: execute(
                w.fn_corpse_dead().assemble(), dict(this=self, obj=obj, lol=LOL))
        else:
            self.dead = self.original_dead
        self.add(self.gamer_mc)

    def add(self, sprite):
        if sprite.kind != "bag":
            self.playerList[sprite.id] = sprite
        self.cursorManager.sfManager.sf_arr.append(SpriteFocus(sprite))
        return sprite

    def getWalker(self, ident):
        return self.playerList.get(ident, U)

    def original_dead(self, obj):          # DisplayLocScene.as dead
        ident = obj["dead"]
        walker = self.getWalker(ident) if ident else self.gamer_mc
        if walker is U:
            return
        walker.behavior = "die"
        f = self.cursorManager.sfManager.getFocus(walker)
        if f is not U:
            f.flare(False)

    def removePlayer(self, ident):         # DisplayLocScene.as removePlayer
        walker = self.getWalker(ident)
        self.cursorManager.removeFocus(walker)
        del self.playerList[ident]


def fight(patched, guard=True):
    """A rat (215) at the front, another (216) behind it, the bag of an
    earlier kill under the rat. The rat is selected and killed, the pointer
    on it and on the bag."""
    s = Scene(patched, guard)
    other = s.add(Sprite(216, "mob", 1))
    bag = s.add(Sprite(None, "bag", 2))
    rat = s.add(Sprite(215, "mob", 3))
    cm = s.cursorManager
    cm.targetList.addTarget(216)
    cm.select(cm.sfManager.getFocus(rat))
    cm.sfManager.over(bag)
    cm.sfManager.over(rat)
    return s, cm, rat, bag, other


def foci(cm):
    return [f.target.id if f.target.kind != "bag" else "bag" for f in cm.sfManager.sf_arr]


# --- in process: the wrappers' own bytecode ---------------------------------
s, cm, rat, bag, other = fight(patched=False)
check("the scene: before the kill a click on the rat strikes it", cm.mouse_up(), "strike")
s.dead(dict(dead=215))
check("original: a click on the dead rat over the bag still strikes the dead",
      cm.mouse_up(), "strike")

s, cm, rat, bag, other = fight(patched=True)
s.dead(dict(dead=215))
check("patched: the dead rat lies down as before", rat.behavior, "die")
check("patched: a click there now goes to the bag under the body", cm.mouse_up(), "take")
check("patched: the corpse has no focus and is no longer a target",
      (foci(cm), cm.targetList.target_list), ([0, 216, "bag"], [216]))
check("patched: the next creature is selected and the corpse loses its glow",
      (cm.selected.target is other, rat.filters, other.filters), (True, [], ["glow"]))
s.removePlayer(215)
check("patched: lostUser afterwards leaves the other foci and targets alone",
      (foci(cm), cm.targetList.target_list), ([0, 216, "bag"], [216]))

s, cm, rat, bag, other = fight(patched=True, guard=False)
s.dead(dict(dead=215))
s.removePlayer(215)
check("without the removeFocus guard lostUser cuts the next creature off the target list",
      (foci(cm), cm.targetList.target_list), ([0, 216, "bag"], []))

s, cm, rat, bag, other = fight(patched=True)
s.dead(dict(dead=0))
check("the gamer's own death keeps every focus", foci(cm), [0, 216, "bag", 215])
s.dead(dict(dead=999))
check("a death for a figure not on screen changes nothing",
      (foci(cm), cm.mouse_up()), ([0, 216, "bag", 215], "strike"))
s.dead(dict(dead=215))
s.dead(dict(dead=215))
check("a second dead for the same corpse cuts nobody else's focus",
      (foci(cm), cm.targetList.target_list), ([0, 216, "bag"], [216]))

check("both wraps are in the injected code",
      [n for n in ("__corpseDeadOrig", "__corpseFocusOrig") if n.encode() not in w.injected()], [])


# --- real Flash: the same walk through the original client's classes --------
PLAYER = os.environ.get("LAVA_FLASH_PLAYER", "")
RES = Path(os.environ.get("LAVA_RES", ""))
SRC = RES / "main.swf.orig" if (RES / "main.swf.orig").is_file() else RES / "main.swf"
LAST = 40


def probe(url):
    """Once a second. Finds the location's DisplayLocScene among the
    listeners of Location's "dead", picks two figures with a focus that are
    not the gamer, and from the tick it has them walks steps 1-3:
    1: pointer onto `other`, then onto `victim`; both selected in turn;
    2: Location.lch dead=<victim>;  3: Location.lch lostUser=<victim>.
    Each report carries the focus count and who is flared and selected."""
    a = w.Asm()
    a.var("_root").push("tick").var("_root").member("tick").push(1).op("add2").op("setmember")
    a.push("r")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    a.push("m", 0).var("lol").member("core", "Master").push("getInstance").op("callmethod").op("definelocal")
    a.var("r").push("tick").var("_root").member("tick").op("setmember")
    a.var("r").push("state").var("m").member("currentState").op("setmember")
    # The scene: the first listener of "dead" with a cursorManager.
    a.push("q").var("m").member("currentLocation", "__q_dead").op("definelocal")
    a.push("scene").var("q").push(0).op("getmember").push(0).op("getmember").op("definelocal")
    a.var("scene").member("cursorManager").push(w.UNDEF).op("equals2").op("not").iftrue("found")
    a.push("scene").var("q").push(1).op("getmember").push(0).op("getmember").op("definelocal")
    a.label("found")
    a.push("cm").var("scene").member("cursorManager").op("definelocal")
    a.var("cm").push(w.UNDEF).op("equals2").iftrue("send")
    a.push("sf").var("cm").member("sfManager").op("definelocal")
    # Pick the two once, from sf_arr: walkers that are not the gamer.
    a.var("_root").member("victim").iftrue("picked")
    a.push("i", 0).op("definelocal")
    a.label("loop")
    a.var("i").var("sf").member("sf_arr", "length").op("less2").op("not").iftrue("picked")
    a.push("t").var("sf").member("sf_arr").var("i").op("getmember").member("target").op("definelocal")
    a.var("t").var("scene").member("gamer_mc").op("equals2").iftrue("next")
    a.var("t").member("id").push(1).var("scene").push("getWalker").op("callmethod")
    a.var("t").op("equals2").op("not").iftrue("next")
    a.var("_root").member("other").iftrue("second")
    a.var("_root").push("other").var("t").op("setmember")
    a.push(True).iftrue("next")
    a.label("second")
    a.var("_root").push("victim").var("t").op("setmember")
    a.var("_root").push("start").var("_root").member("tick").push(2).op("add2").op("setmember")
    a.push(True).iftrue("picked")
    a.label("next")
    a.push("i").var("i").push(1).op("add2").op("definelocal")
    a.push(True).iftrue("loop")
    a.label("picked")
    a.push("v").var("_root").member("victim").op("definelocal")
    a.push("o").var("_root").member("other").op("definelocal")
    a.var("v").op("not").iftrue("send")
    a.push("step").var("_root").member("tick").var("_root").member("start").op("subtract").op("definelocal")
    a.var("r").push("step").var("step").op("setmember")
    a.var("r").push("victim").var("v").member("id").op("setmember")
    # step 1: the pointer onto both, the victim selected
    a.var("step").push(1).op("equals2").op("not").iftrue("s2")
    for who in ("o", "v"):
        a.push("e")
        w.new(a, ["_global"], "Object", 0).op("definelocal")
        a.var("e").push("type", "spriteOver").op("setmember")
        a.var("e").push("over", True).op("setmember")
        a.var("e").push(1).var(who).push(1).var("sf").push("getFocus").op("callmethod")
        a.push("dispatchEvent").op("callmethod").op("pop")
    for who in ("o", "v"):
        a.var(who).push(1).var("sf").push("getFocus").op("callmethod")
        a.push(1).var("cm").push("select").op("callmethod").op("pop")
    a.label("s2")
    for step, key in ((2, "dead"), (3, "lostUser")):
        a.var("step").push(step).op("equals2").op("not").iftrue("s%d" % (step + 1))
        a.push("frame")
        w.new(a, ["_global"], "Object", 0).op("definelocal")
        a.var("frame").push("param")
        w.new(a, ["_global"], "Object", 0).op("setmember")
        a.var("frame").member("param").push(key).var("v").member("id").op("setmember")
        a.var("frame").push(1).var("m").member("currentLocation").push("lch").op("callmethod").op("pop")
        a.label("s%d" % (step + 1))
    a.var("r").push("foci").var("sf").member("sf_arr", "length").op("setmember")
    a.var("r").push("victim_focus").var("v").push(1).var("sf").push("getFocus").op("callmethod")
    a.push(w.UNDEF).op("equals2").op("not").op("setmember")
    a.var("r").push("other_focus").var("o").push(1).var("sf").push("getFocus").op("callmethod")
    a.push(w.UNDEF).op("equals2").op("not").op("setmember")
    a.var("r").push("flared_victim").var("sf").member("flared", "target").var("v").op("equals2").op("setmember")
    a.var("r").push("flared_other").var("sf").member("flared", "target").var("o").op("equals2").op("setmember")
    a.var("r").push("targets").var("cm").member("targetList", "target_list", "length").op("setmember")
    a.var("r").push("selected_other").var("cm").member("selected", "target").var("o").op("equals2").op("setmember")
    a.var("r").push("selected_victim").var("cm").member("selected", "target").var("v").op("equals2").op("setmember")
    a.var("r").push("victim_dead").var("v").member("behavior").push("die").op("equals2").op("setmember")
    a.label("send")
    a.push("POST").var("r").push(url)
    w.call_method(a, "r", "sendAndLoad", 3)
    a.var("_root").member("activated").iftrue("out")
    a.var("m").member("gamer", "playerInfo", "name").op("not").iftrue("out")
    a.var("m").member("persGen", "xmlInfoLoaded").op("not").iftrue("out")
    a.var("_root").push("activated", True).op("setmember")
    a.push(0).var("m").member("persGen").push("activatePlayer").op("callmethod").op("pop")
    a.label("out")
    return a


def run(variant):
    """variant: "original", "no-guard" or "patched"."""
    import accounts
    work = Path(tempfile.mkdtemp(prefix="lava_corpse_"))
    store = accounts.Store(str(work / "lava.db"))
    aid, _ = store.register("probe", "probe-password")
    store.create_character(aid, "Probe", 0, 1, home=(102, 5965, 1728))
    store.close()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    tree = ast.parse((SERVER / "bootstrap_http.py").read_text(encoding="utf-8"))
    settings = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", None) == "CSETTINGS" for t in n.targets))
    reports = []

    class Handler(BaseHTTPRequestHandler):
        def serve(self):
            path = unquote(urlsplit(self.path).path)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            status = 200
            if path == "/report":
                reports.append({k: v[0] for k, v in parse_qs(body.decode()).items()})
                data = b"ok=1"
            elif path.endswith("/loaduser/"):
                data = ("data=127.0.0.1:%d %s" % (port, accounts.credential("probe", "probe-password"))).encode()
            elif path.endswith("crossdomain.xml"):
                data = b'<cross-domain-policy><allow-access-from domain="*" to-ports="*"/></cross-domain-policy>'
            elif path == "/res/main.swf":
                data = movie
            elif path.endswith("csettings_v1.xml"):
                data = settings.format(host="127.0.0.1", port=port, http_port=http.server_port).encode()
            elif path.endswith("/hints/hints.xml"):
                data = b"\xef\xbb\xbf<?xml version='1.0'?><data/>"
            elif path.startswith("/res/") and (RES / path[5:]).is_file():
                data = (RES / path[5:]).read_bytes()
            else:
                status, data = 404, b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        do_GET = do_POST = serve

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d" % http.server_port
    version, body = w.read_swf(SRC)
    tags = [t for t in w.split_tags(body) if t[0] not in (12, 26)] if SRC.name == "main.swf" else w.split_tags(body)
    w.patch_ceiling(tags, 3840, 2160)
    keep = w.fn_corpse_dead, w.fn_corpse_focus

    def passthrough(orig, arg):
        def body():
            a = w.Asm()
            a.var(arg).push(1).var("this").push(orig).op("callmethod").op("pop")
            return a
        return body
    if variant == "original":
        w.fn_corpse_dead = passthrough("__corpseDeadOrig", "obj")
    if variant in ("original", "no-guard"):
        w.fn_corpse_focus = passthrough("__corpseFocusOrig", "targ")
    try:
        tags = w.inject(tags)
    finally:
        w.fn_corpse_dead, w.fn_corpse_focus = keep
    code = w.Asm()
    code.var("_root").push("tick", 0).op("setmember")
    code.var("_global").push("__corpseProbe").function((), probe(url + "/report")).op("setmember")
    code.push(1000, "__corpseProbe").var("_global").push(3, "setInterval").op("callfunc").op("pop").op("end")
    at = next(i for i, t in enumerate(tags) if t[0] == 1)
    tags.insert(at, (12, code.assemble(), True))
    payload = w.join_tags(body[:w.header_len(body)], tags)
    movie = b"CWS" + bytes([version]) + struct.pack("<I", len(payload) + 8) + zlib.compress(payload)
    log = open(work / "server.log", "w", encoding="utf-8")
    env = dict(os.environ, LAVA_DB=str(work / "lava.db"), LAVA_PORT=str(port),
               LAVA_POLICY_PORT="0", LAVA_CHEATS="1", PYTHONIOENCODING="utf-8")
    server = subprocess.Popen([sys.executable, "server.py"], cwd=SERVER,
                              env=env, stdout=log, stderr=log)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    player = subprocess.Popen([PLAYER, url + "/res/main.swf?logged=1&vversion=1"], startupinfo=startup)
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(.2)
            if any(int(r.get("step", -99)) >= 4 for r in reports):
                break
            if reports and int(reports[-1].get("tick", 0)) >= LAST:
                break
        return {int(r["step"]): r for r in reports if "step" in r}
    finally:
        player.terminate()
        player.wait(timeout=5)
        server.terminate()
        server.wait(timeout=5)
        http.shutdown()
        http.server_close()
        log.close()


def walk(variant):
    steps = run(variant)
    missing = [n for n in (1, 2, 3) if n not in steps]
    if missing:
        raise AssertionError("%s: the probe never reported steps %s (%d reports)"
                             % (variant, missing, len(steps)))
    return steps[1], steps[2], steps[3]


try:
    if PLAYER and SRC.is_file() and os.name == "nt":
        hover, dead, lost = walk("original")
        check("Flash, original: over the figure and selected before its death",
              (hover["selected_victim"], hover["victim_focus"]), ("true", "true"))
        check("Flash, original: the corpse keeps its focus and the selection",
              (dead["victim_dead"], dead["victim_focus"], dead["selected_victim"]),
              ("true", "true", "true"))
        n = int(hover["foci"])
        hover, dead, lost = walk("no-guard")
        check("Flash, no guard: lostUser after dead cuts the next creature off the target list",
              (int(dead["targets"]), int(lost["targets"]), int(lost["foci"])), (1, 0, n - 1))
        hover, dead, lost = walk("patched")
        check("Flash, patched: the figure still dies",
              dead["victim_dead"], "true")
        check("Flash, patched: the corpse lets go of focus and selection at once",
              (dead["victim_focus"], dead["selected_victim"], dead["flared_victim"]),
              ("false", "false", "false"))
        check("Flash, patched: the pointer's other figure is under it now",
              dead["flared_other"], "true")
        check("Flash, patched: lostUser takes nothing more away",
              (int(hover["foci"]), int(dead["foci"]), int(lost["foci"]), lost["other_focus"],
               int(dead["targets"]), int(lost["targets"]), lost["selected_other"]),
              (n, n - 1, n - 1, "true", 1, 1, "true"))
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES on Windows for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash corpse probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("corpse click OK")
