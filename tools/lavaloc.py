"""A location file of the client (res/locations/**/*.xml): read it, write it,
and the hex grid it is drawn on. Standard library only.

Two layers:

  RawDoc   lossless. parse_raw keeps the BOM, the declaration, every
           attribute as its raw string in file order, every child as it is
           written (text, self-closing, the space before '/>'), and what
           follows </location>. write_raw(parse_raw(b)) == b for all 1396
           files of the original (tools/test_lavaloc.py).

  model    a plain dict, JSON as it is (decode / encode):

    attrs          {name: value} of <location>, in file order, unescaped
    width, height  ints (encode writes them back into attrs)
    background     {type, id, fx} of <background>, or None (desert, deadloc)
    sprites        [{id, type, dx, dy, front, anchors: [(gx, gy)]}]
                   type None when the file does not say (the client: lib);
                   front the depth template as written (front_cells)
    bgdecorations  [{id, type, dx, dy}]
    lists          {obstacles|zones|warinzones|inzones|outzones|mobs:
                    [(gx, gy, extra)]}, extra: the obstacle code, the exit
                   side (SIDES), the mob type as 4 hex digits, else ""
    tails          {list: an incomplete last record, kept as it is}
    serverdata     its text ("\\r\\n" in static files), or None

encode(model, base) rebuilds a RawDoc: a child or an attribute whose meaning
did not change is taken from `base` byte for byte, anything else is written
in the static style (write_static). So an edit changes only what it edits,
and encode(decode(d), d) == d.

The format (recon/as-src/lol/core/location: LDParser, LocationGrid,
LocDeclaration, LDepthManager, SceneObject):

  <location title preloader bgExt bg bgsound height width dir library pvp
            war fn version>                 the static order (ROOT_ORDER)
    <background type id fx />               overrides bg/bgExt
    <sprite id dx dy front type>GXGY...</sprite>   one image, at each anchor
    <bgdecoration id dx dy type />          a decal at absolute pixels
    <obstacles> GXGYc   <zones> GXGY   <warinzones> GXGY   <inzones> GXGY
    <outzones> GXGYs   <mobs> GXGYtttt   <serverdata>\\r\\n</serverdata>
  </location>

A cell is two lowercase hex digits of gx and two of gy. Rows are "odd-r":
odd rows sit half a cell to the right, and a cell's centre pixel is
cell_px(gx, gy) = (40*gx + 20*(gy & 1), 15*gy) on a canvas of W*40 x H*15.
The client reads obstacles (dropping the code), zones, sprites,
bgdecorations and the background; inzones, warinzones, outzones and mobs
are the server's (server/world.py, server/travel.py). Obstacle code 'f' is
a wall; '1' is also a counter that is shot over in world.SHOOT_OVER.
"""
import copy
import math
import re

BOM = b"\xef\xbb\xbf"
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
LISTS = ("obstacles", "zones", "warinzones", "inzones", "outzones", "mobs")
STRIDE = {"obstacles": 5, "zones": 4, "warinzones": 4, "inzones": 4,
          "outzones": 5, "mobs": 8}
ROOT_ORDER = ("title", "preloader", "bgExt", "bg", "bgsound", "height", "width",
              "dir", "library", "pvp", "war", "fn", "version")
BACKGROUND_ORDER = ("type", "id", "fx")
SPRITE_ORDER = ("id", "dx", "dy", "front", "type")
DECAL_ORDER = ("id", "dx", "dy", "type")
# outzones extra -> the side data/exits_sides.json and travel.SIDE_CODE use:
# a map edge (1 west, 2 north, 3 east, 4 south) or a door a/b.
SIDES = {"1": "W", "2": "N", "3": "E", "4": "S", "a": "a", "b": "b"}
SIZES = ((64, 128), (32, 64))     # the only two the original has
CELL_W, ROW_H = 40, 15            # LocationGrid.cellW, LocDeclaration: 40*sqrt(3)/4*sqrt(3)/2
# A hex around its centre, clockwise from the top (the cells tile with it).
HEX = ((0, -10), (20, -5), (20, 5), (0, 10), (-20, 5), (-20, -5))

TAG_RE = re.compile(r'<(\w+)((?:\s+[\w:]+="[^"]*")*)(\s*)(/?)>', re.S)
ATTR_RE = re.compile(r'([\w:]+)="([^"]*)"')
DECL_RE = re.compile(r'<\?xml[^>]*\?>')


# --- raw layer -----------------------------------------------------------------

class RawDoc:
    """A location file exactly as written. children: dicts of tag, attrs
    [(name, raw value)], text (None when self-closing), selfclose, sp (the
    whitespace before '>' or '/>')."""

    def __init__(self):
        self.bom = False
        self.decl = ""
        self.root_attrs = []
        self.children = []
        self.tail = ""


def parse_raw(data):
    """bytes -> RawDoc. ValueError on anything the files never contain
    (comments, nesting, CDATA, single quotes)."""
    d = RawDoc()
    if data.startswith(BOM):
        d.bom, data = True, data[len(BOM):]
    s = data.decode("utf-8")
    m = DECL_RE.match(s)
    if m:
        d.decl, s = m.group(0), s[m.end():]
    m = TAG_RE.match(s)
    if not m or m.group(1) != "location" or m.group(4):
        raise ValueError("not a location file: %r" % s[:80])
    d.root_attrs = ATTR_RE.findall(m.group(2))
    pos = m.end()
    end = s.rfind("</location>")
    if end < pos:
        raise ValueError("no </location>")
    d.tail = s[end + len("</location>"):]
    while pos < end:
        m = TAG_RE.match(s, pos)
        if not m:
            raise ValueError("unexpected %r" % s[pos:pos + 60])
        tag, attrs, sp, sc = m.group(1), ATTR_RE.findall(m.group(2)), m.group(3), m.group(4) == "/"
        if sc:
            d.children.append(dict(tag=tag, attrs=attrs, text=None, selfclose=True, sp=sp))
            pos = m.end()
        else:
            close = s.find("</%s>" % tag, m.end())
            if close < 0 or "<" in s[m.end():close]:
                raise ValueError("<%s> is not closed or holds markup" % tag)
            d.children.append(dict(tag=tag, attrs=attrs, text=s[m.end():close],
                                   selfclose=False, sp=sp))
            pos = close + len(tag) + 3
    return d


def _attrs(attrs):
    return "".join(' %s="%s"' % (k, v) for k, v in attrs)


def write_raw(d):
    out = [d.decl, "<location", _attrs(d.root_attrs), ">"]
    for c in d.children:
        if c["selfclose"]:
            out.append("<%s%s%s/>" % (c["tag"], _attrs(c["attrs"]), c["sp"]))
        else:
            out.append("<%s%s%s>%s</%s>" % (c["tag"], _attrs(c["attrs"]), c["sp"],
                                            c["text"], c["tag"]))
    out.append("</location>")
    out.append(d.tail)
    return (BOM if d.bom else b"") + "".join(out).encode("utf-8")


def read_raw(path):
    with open(path, "rb") as fh:
        return parse_raw(fh.read())


# --- values ------------------------------------------------------------------------

_ENT = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
_ENT_RE = re.compile(r"&(#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);")


def unescape(v):
    def one(m):
        e = m.group(1)
        if e.startswith("#x"):
            return chr(int(e[2:], 16))
        if e.startswith("#"):
            return chr(int(e[1:]))
        return _ENT[e]
    return _ENT_RE.sub(one, v) if "&" in v else v


def escape(v):
    return (str(v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def num(v):
    """An attribute as the client's Number() reads it, NaN and absent as 0
    (LDParser): int when whole, else float."""
    if v is None:
        return 0
    try:
        f = float(str(v).strip())
    except ValueError:
        return 0
    if math.isnan(f) or math.isinf(f):
        return 0
    return int(f) if f.is_integer() else f


def fmt_num(v):
    """dx/dy as the static files write them: the shortest decimal with at
    most two places (-115, 12.5, 7.25)."""
    v = round(float(v), 2)
    if v.is_integer():
        return str(int(v))
    return ("%.2f" % v).rstrip("0").rstrip(".")


# --- cells -----------------------------------------------------------------------------

def dec_cells(s, stride):
    """A cell list -> [(gx, gy, extra)] (LDParser.getHexCoord with no offset).
    An incomplete last record is dropped here; decode keeps it in tails."""
    s = "".join((s or "").split())
    return [(int(s[i:i + 2], 16), int(s[i + 2:i + 4], 16), s[i + 4:i + stride])
            for i in range(0, len(s) - stride + 1, stride)]


def enc_cells(cells):
    return "".join("%02x%02x%s" % (int(c[0]), int(c[1]), c[2] if len(c) > 2 else "")
                   for c in cells)


def front_cells(front, ax, ay):
    """A sprite's front template -> absolute cells for the anchor (ax, ay):
    LDParser.getHexCoord(front, ax-128, ay-128). The template is written for
    an anchor on an even row; on an odd anchor row, odd relative rows move
    one cell right."""
    out = []
    front = front or ""
    for i in range(0, len(front) - 3, 4):
        bx, by = int(front[i:i + 2], 16), int(front[i + 2:i + 4], 16)
        par = 1 if (ay % 2 == 1 and by % 2 == 1) else 0
        out.append((bx + ax - 128 + par, by + ay - 128))
    return out


def front_hex(cells, ax, ay):
    """Inverse of front_cells for one anchor."""
    out = []
    for fx, fy in cells:
        dy = fy - ay
        par = 1 if (ay % 2 == 1 and dy % 2 != 0) else 0
        out.append("%02x%02x" % (fx - ax + 128 - par, dy + 128))
    return "".join(out)


def front_offsets(front):
    """The template as offsets from the anchor, for an anchor on an even row
    (the convention client/objects/manifest.json writes front and footprint
    in): [(dx, dy)]."""
    front = front or ""
    return [(int(front[i:i + 2], 16) - 128, int(front[i + 2:i + 4], 16) - 128)
            for i in range(0, len(front) - 3, 4)]


def offsets_front(offsets):
    """Inverse of front_offsets."""
    return "".join("%02x%02x" % (0x80 + dx, 0x80 + dy) for dx, dy in offsets)


def offsets_cells(offsets, ax, ay):
    """Offsets from an anchor (even-row convention) -> absolute cells, by the
    client's rule: the same as front_cells(offsets_front(offsets), ax, ay)."""
    return [(ax + dx + (1 if (ay % 2 and dy % 2) else 0), ay + dy) for dx, dy in offsets]


# kept for the scratchpad prototype's callers
front_abs = front_cells
front_rel_encode = front_hex


# --- geometry ---------------------------------------------------------------------------

def cell_px(gx, gy):
    """A cell's centre pixel: LocationGrid.createCells rx = gx + 0.5*(gy%2),
    ry = gy*sqrt(3)/2, through LocDeclaration.abstractToReal (40*rx, 15*gy).
    A character's feet and a sprite's anchor stand here."""
    return CELL_W * gx + (CELL_W // 2) * (gy % 2), ROW_H * gy


def px_cell(x, y):
    """The cell under a pixel: LocDeclaration.realToGrid, verbatim."""
    cell_h = 15.0
    row = math.floor(y / cell_h)
    d = y - row * cell_h - 0.5 * cell_h
    if abs(d) > cell_h / 6:
        a = 1 if d >= 0 else 0
    else:
        x4 = x - 40 * 0.5 * (row % 2)
        t = 40 * 0.5 - abs(x4 - math.floor((x4 + 20) / 40) * 40)
        y9 = y - row * cell_h - cell_h / 3
        a = 0 if y9 <= abs(t / 4) else 1
    gy = row + a
    gx = math.floor(x / 40 - 0.5 * (gy % 2) + 0.5)
    return gx, gy


def cell_num(gx, gy, width):
    """The number the server and the client's CellsNum give a cell."""
    return gy * width + gx


def num_cell(n, width):
    return n % width, n // width


def neighbours(gx, gy):
    """The six cells around one (LocationGrid.getSiblings): the odd-r rule."""
    s = 1 if gy % 2 else -1
    return [(gx - 1, gy), (gx + 1, gy), (gx, gy - 1), (gx, gy + 1),
            (gx + s, gy - 1), (gx + s, gy + 1)]


def hex_points(gx, gy, scale=1.0):
    """The outline of a cell, in (scaled) canvas pixels."""
    cx, cy = cell_px(gx, gy)
    return [((cx + dx) * scale, (cy + dy) * scale) for dx, dy in HEX]


# --- the model --------------------------------------------------------------------------

def _int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _sprite(at, text):
    return {"id": at.get("id", ""), "type": at.get("type"),
            "dx": num(at.get("dx")), "dy": num(at.get("dy")),
            "front": at.get("front"),
            "anchors": [(x, y) for x, y, _ in dec_cells(text, 4)]}


def _decal(at):
    return {"id": at.get("id", ""), "type": at.get("type"),
            "dx": num(at.get("dx")), "dy": num(at.get("dy"))}


def _list(text, tag):
    t = "".join((text or "").split())
    r = len(t) % STRIDE[tag]
    return dec_cells(t, STRIDE[tag]), (t[len(t) - r:] if r else "")


def decode(d):
    """RawDoc -> model (see the module's docstring)."""
    attrs = {k: unescape(v) for k, v in d.root_attrs}
    m = {"attrs": attrs, "width": _int(attrs.get("width")),
         "height": _int(attrs.get("height")), "background": None,
         "sprites": [], "bgdecorations": [],
         "lists": {t: [] for t in LISTS}, "tails": {t: "" for t in LISTS},
         "serverdata": None}
    for c in d.children:
        at = {k: unescape(v) for k, v in c["attrs"]}
        tag = c["tag"]
        if tag == "background":
            m["background"] = at
        elif tag == "sprite":
            m["sprites"].append(_sprite(at, c["text"]))
        elif tag == "bgdecoration":
            m["bgdecorations"].append(_decal(at))
        elif tag in STRIDE:
            m["lists"][tag], m["tails"][tag] = _list(c["text"], tag)
        elif tag == "serverdata":
            m["serverdata"] = c["text"] or ""
    return m


def load(src):
    """A model from a path or from bytes."""
    if isinstance(src, (bytes, bytearray)):
        return decode(parse_raw(bytes(src)))
    return decode(read_raw(src))


def encode_into(d, m):
    """Re-encode only the model's cell lists and sprite anchors into the raw
    doc d (in place; returns d). The lossless round trip of the cell codec."""
    si = 0
    for c in d.children:
        if c["tag"] == "sprite":
            sp = m["sprites"][si]
            si += 1
            c["text"] = "".join("%02x%02x" % (int(a[0]), int(a[1])) for a in sp["anchors"])
        elif c["tag"] in STRIDE:
            c["text"] = enc_cells(m["lists"][c["tag"]]) + (m.get("tails") or {}).get(c["tag"], "")
    return d


def _cells_key(cells):
    return tuple((int(c[0]), int(c[1]), c[2] if len(c) > 2 else "") for c in cells)


def _key(tag, sem):
    """What a child means: two children with one key write the same thing
    for the client and the server."""
    if tag == "background":
        return (tag, tuple(sorted((k, str(v)) for k, v in sem.items())))
    if tag == "sprite":
        return (tag, sem["id"], sem.get("type"), num(sem.get("dx")), num(sem.get("dy")),
                sem.get("front"), tuple((int(a[0]), int(a[1])) for a in sem["anchors"]))
    if tag == "bgdecoration":
        return (tag, sem["id"], sem.get("type"), num(sem.get("dx")), num(sem.get("dy")))
    if tag in STRIDE:
        cells, tail = sem
        return (tag, _cells_key(cells), tail or "")
    return (tag, sem)


def _raw_key(c):
    at = {k: unescape(v) for k, v in c["attrs"]}
    tag = c["tag"]
    if tag == "background":
        return _key(tag, at)
    if tag == "sprite":
        return _key(tag, _sprite(at, c["text"]))
    if tag == "bgdecoration":
        return _key(tag, _decal(at))
    if tag in STRIDE:
        return _key(tag, _list(c["text"], tag))
    if tag == "serverdata":
        return _key(tag, c["text"] or "")
    return ("?", tag, tuple(c["attrs"]), c["text"])


def _ordered(names, canonical, base_order=None):
    """names in the canonical order; with base_order, the base's own order,
    and a name it lacks after the last base name canonically before it."""
    rank = {n: i for i, n in enumerate(canonical)}
    big = len(canonical)
    if base_order is None:
        return sorted(names, key=lambda n: (rank.get(n, big), names.index(n)))
    out = [n for n in base_order if n in names]
    for n in sorted((n for n in names if n not in out), key=lambda n: (rank.get(n, big), names.index(n))):
        at = 0
        for i, o in enumerate(out):
            if rank.get(o, big) <= rank.get(n, big):
                at = i + 1
        out.insert(at, n)
    return out


def _child_attrs(values, canonical):
    """[(name, raw)] for a child's attributes (None values are left out)."""
    names = [k for k, v in values.items() if v is not None]
    names = _ordered(names, canonical)
    return [(k, escape(fmt_num(values[k]) if k in ("dx", "dy") else values[k])) for k in names]


def encode(m, base=None, derive_zones=True):
    """model -> RawDoc. With base (the RawDoc the model was decoded from),
    every attribute and child whose meaning is unchanged is the base's own
    bytes; without it, a new file in the static style. derive_zones writes
    zones as the outzones cells in their order, which all 1396 originals
    are; the client opens its exit window on zones, the server reads
    outzones."""
    d = RawDoc()
    if base is not None:
        d.bom, d.decl, d.tail = base.bom, base.decl, base.tail
    else:
        d.decl = DECL
    attrs = dict(m.get("attrs") or {})
    if m.get("width") is not None:
        attrs["width"] = str(int(m["width"]))
    if m.get("height") is not None:
        attrs["height"] = str(int(m["height"]))
    bg = m.get("background")
    if bg is not None:
        if bg.get("id") is not None:
            attrs["bg"] = bg["id"]
        if bg.get("type") is not None and ("bgExt" in attrs or base is None):
            attrs["bgExt"] = bg["type"]
    if base is None:
        defaults = {"title": "", "preloader": "", "bgExt": "lib", "bg": "", "bgsound": "",
                    "dir": "Static", "library": "", "pvp": "1", "war": "0", "fn": "",
                    "version": "1"}
        for k, v in defaults.items():
            attrs.setdefault(k, v)
    base_attrs = dict(base.root_attrs) if base is not None else {}
    names = _ordered(list(attrs), ROOT_ORDER,
                     [k for k, _ in base.root_attrs] if base is not None else None)
    d.root_attrs = [(k, base_attrs[k] if k in base_attrs and unescape(base_attrs[k]) == str(attrs[k])
                     else escape(attrs[k])) for k in names]

    made = []   # (key, canonical child)
    if bg is not None:
        made.append((_key("background", bg),
                     dict(tag="background", attrs=_child_attrs(bg, BACKGROUND_ORDER),
                          text=None, selfclose=True, sp=" ")))
    for sp in m.get("sprites") or []:
        vals = {"id": sp["id"], "dx": num(sp.get("dx")), "dy": num(sp.get("dy")),
                "front": sp.get("front") if sp.get("front") is not None else "",
                "type": sp.get("type") or "lib"}
        text = "".join("%02x%02x" % (int(a[0]), int(a[1])) for a in sp["anchors"])
        made.append((_key("sprite", sp), dict(tag="sprite", attrs=_child_attrs(vals, SPRITE_ORDER),
                                              text=text, selfclose=False, sp="")))
    for dc in m.get("bgdecorations") or []:
        vals = {"id": dc["id"], "dx": num(dc.get("dx")), "dy": num(dc.get("dy")),
                "type": dc.get("type") or "lib"}
        made.append((_key("bgdecoration", dc),
                     dict(tag="bgdecoration", attrs=_child_attrs(vals, DECAL_ORDER),
                          text=None, selfclose=True, sp=" ")))
    lists = dict(m.get("lists") or {})
    tails = m.get("tails") or {}
    if derive_zones:
        lists["zones"] = [(c[0], c[1], "") for c in lists.get("outzones") or []]
    base_tags = {c["tag"] for c in base.children} if base is not None else set(LISTS)
    for tag in LISTS:
        cells = lists.get(tag) or []
        tail = tails.get(tag, "")
        if tag not in base_tags and not cells and not tail:
            continue
        made.append((_key(tag, (cells, tail)),
                     dict(tag=tag, attrs=[], text=enc_cells(cells) + tail,
                          selfclose=False, sp="")))
    sd = m.get("serverdata")
    if not sd and base is None:
        sd = "\r\n"
    if sd is not None:
        made.append((_key("serverdata", sd),
                     dict(tag="serverdata", attrs=[], text=sd, selfclose=False, sp="")))

    pool = {}
    if base is not None:
        for c in base.children:
            pool.setdefault(_raw_key(c), []).append(c)
    for key, child in made:
        same = pool.get(key)
        if same:
            c = same.pop(0)
            child = dict(c, attrs=list(c["attrs"]))
        d.children.append(child)
    return d


def write_static(m):
    """A model as a new file in the static style: the declaration, no BOM,
    one line, canonical order of elements and attributes, pvp and fn
    present, lowercase hex, zones = outzones, <serverdata>\\r\\n</serverdata>."""
    return write_raw(encode(m))


def normalized(m):
    """A copy of a model made ready to be a new static file, meaning for the
    client what it meant: a <background> (from bg/bgExt where the file had
    none, as the desert and deadloc templates), bgExt and bg agreeing with
    it, pvp written (absent is open, LDParser), fn present, every type
    spelled lib or ext ("undefined" and absent are lib to the client),
    <serverdata>\\r\\n</serverdata>. Cell lists, the extra row y == H and
    incomplete records are kept as they are."""
    n = copy.deepcopy(m)
    a = n["attrs"] = dict(n.get("attrs") or {})
    bg = n.get("background")
    if bg is None:
        bg = {"type": "ext" if a.get("bgExt") == "ext" else "lib", "id": a.get("bg", ""), "fx": ""}
    else:
        bg = dict(bg)
        bg["type"] = "ext" if bg.get("type") == "ext" else "lib"
        bg.setdefault("id", a.get("bg", ""))
        bg.setdefault("fx", "")
    n["background"] = bg
    a["bgExt"], a["bg"] = bg["type"], bg["id"]
    a["pvp"] = "0" if a.get("pvp") == "0" else "1"
    a.setdefault("fn", "")
    for s in n.get("sprites") or []:
        s["type"] = "ext" if s.get("type") == "ext" else "lib"
        if s.get("front") is None:
            s["front"] = ""
    for dc in n.get("bgdecorations") or []:
        dc["type"] = "ext" if dc.get("type") == "ext" else "lib"
    n["serverdata"] = "\r\n"
    return n


# --- what the server and the client read out of it ------------------------------------------

def exits_row(m):
    """{str(cell number): side} -- the location's row of data/exits_sides.json."""
    w = m["width"]
    return {str(cell_num(x, y, w)): SIDES.get(e, e) for x, y, e in m["lists"]["outzones"]}


def mob_slots(m):
    """[(gx, gy, type id)] of <mobs> as world.Location reads them (type 0 is
    an empty slot)."""
    return [(x, y, int(e, 16)) for x, y, e in m["lists"]["mobs"]]


def cells(m, tag):
    """The (gx, gy) of a list, as a set."""
    return {(c[0], c[1]) for c in m["lists"][tag]}


# --- depth: LDepthManager ------------------------------------------------------------------------

class SceneObject:
    """One sprite instance as LDepthManager sees it: its front sorted by x
    (SceneObject.front), a one-cell front replaced by the anchor and an
    empty one kept empty (SceneObject.point), minD 1 (LocBuilder)."""
    __slots__ = ("sprite", "anchor", "point", "front", "left", "right", "minD", "turned")

    def __init__(self, sprite, anchor, point, front):
        self.sprite, self.anchor, self.point = sprite, anchor, point
        front = sorted(front, key=lambda c: c[0])
        if len(front) == 1:
            front = [point]
        self.front = front
        self.left = front[0] if front else None
        self.right = front[-1] if front else None
        self.minD = 1
        self.turned = False


def scene_objects(m, order="reverse"):
    """The sprite instances in the client's displayList order. LDParser
    walks the children with for..in, which in AVM1 runs an array from its
    last element to its first: order="reverse" (the default) takes the
    <sprite> elements last to first, each one's anchors in order; "file"
    keeps the file's order. Not run in Flash (no windows): a hypothesis."""
    objs = []
    idx = list(range(len(m["sprites"])))
    if order == "reverse":
        idx.reverse()
    for si in idx:
        sp = m["sprites"][si]
        for ai, (ax, ay) in enumerate(sp["anchors"]):
            objs.append(SceneObject(si, ai, (ax, ay), front_cells(sp.get("front"), ax, ay)))
    return objs


def _first_y(front, x):
    for c in front:
        if c[0] == x:
            return c[1]
    return None


def collision(obj, other):
    """LDepthManager.getCollision: 1 when obj is drawn over other, -1 under,
    0 when their fronts share no column."""
    L, R, L2, R2 = obj.left, obj.right, other.left, other.right
    if L is None or L2 is None:
        return 0
    if L2[0] > R[0] or R2[0] < L[0]:
        return 0
    if L2[0] <= L[0] <= R2[0]:
        y = _first_y(other.front, L[0])
        return 1 if y is not None and L[1] > y else -1
    if L[0] <= L2[0] <= R[0]:
        y = _first_y(obj.front, L2[0])
        return 1 if y is not None and y > L2[1] else -1
    return 0


def depth_sort(objs):
    """LDepthManager.zSort over SceneObjects: every object with minD 1 adds
    up the minD of all it is drawn over (findCollisions, recursively), then
    the list is sorted by minD, the lowest drawn first. Flash's sortOn is not
    stable; ties keep the displayList order here. Returns the objects in
    drawing order (the last on top)."""
    n = len(objs)
    for start in objs:
        if start.minD != 1 or start.turned:
            continue
        start.turned = True
        stack = [[start, 0, None]]
        while stack:
            fr = stack[-1]
            o = fr[0]
            if fr[2] is not None:
                o.minD += fr[2].minD
                fr[2] = None
            if fr[1] >= n:
                stack.pop()
                continue
            other = objs[fr[1]]
            fr[1] += 1
            if other is o or collision(o, other) <= 0:
                continue
            if other.minD == 1 and not other.turned:
                other.turned = True
                fr[2] = other
                stack.append([other, 0, None])
            else:
                o.minD += other.minD
    return [o for _, o in sorted(enumerate(objs), key=lambda t: (t[1].minD, t[0]))]


def depth_order(m, order="reverse"):
    """[(sprite index, anchor index)] of every sprite instance in the order
    the client draws them, the last on top."""
    return [(o.sprite, o.anchor) for o in depth_sort(scene_objects(m, order))]


def walker_index(drawn, gx, gy):
    """Where LDepthManager.listZSort puts a walker (a character or a mob)
    standing on (gx, gy) among objects in drawing order: it joins at the
    end of the list and searches from the bottom for the first object it
    stands in front of (getSimpleCollision); the walker goes right above it,
    or under everything."""
    for i in range(len(drawn) - 1, -1, -1):
        o = drawn[i]
        if o.left is None:
            continue
        if o.left[0] > gx or o.right[0] < gx:
            continue
        y = _first_y(o.front, gx)
        if y is not None and gy > y:
            return i + 1
    return 0
