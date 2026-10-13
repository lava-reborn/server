"""Item types of our own: things the game needs that the original's
objects.xml has no type for.

WHAT THE CLIENT NEEDS OF A TYPE

The client knows a type by two words of database/objects.xml, its root and
its internal name (SBase, SDBList: type_id, root_type_id, name), and it uses
them for one thing: the icon, classes/<root's folder>/<name>/ico.swf
(SSEmulator.getIcon, called by ItemContainer.attachIcon for every cell of a
bag, a stall or a slot). Everything else it shows or sends -- the name, the
words, the prices, the set, the slot, what buying sends (Trade.buy: the gold
code for anything with a g_cost) -- comes from the server's ss_si_*
(ItemFactory.requestSI). An oid carries the type in exactly four hex digits
(inventory.oid), so a type of ours is a number above the original's last,
50 035, and at most 65 535. A type the client's objects.xml lacks still
works; it only draws no picture.

data/own_items.json lists ours: type -> name and like. `like` is the
original type whose root ours has and whose picture it draws. The release
(client/build.py) writes database/objects.xml as the original's with a row
for each of ours, in the original's own format, and puts a byte copy of
like's icon at ours, classes/<folder>/<name>/ico.swf; the server lays the
same rows into items.catalogue(), so root_of, slot_of and every reader of
the catalogue see our type as the client does. A table that does not read,
or that names a type, a name or an icon the original already has, stops
both: the server at start, the release at build. The local stand serves
the same file and icons on its /res/ (bootstrap_http), what a release
carries.

An objects.xml read with rows in our range is a release's: the launcher
writes the release's file into the player's client, and the owner's own
client is one. Those rows are ours, as the release had them, so every
reader drops them first (originals) and lays the current ones on.

The first of them (the owner's «поставь ловеласа у Гали и за афро и за
голд», 2026-10-13): the gold copies of Чёрный Ловелас[12]'s pieces. The
original's Bs_U_LVL_12 is a quest series, _Q_mod00..mod10 and nothing else,
and one type has one currency (Trade.buy), so the set's gold version needed
five types of its own; the original draws a gold piece with its afro
piece's very picture (297 of its 305 A/G pairs of LVL clothing), so each
copies its quest piece's icon. data/sets.json makes them the set's G.
"""
import io
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "own_items.json")

# The original's last type is 50 035; an oid has four hex digits for one.
FIRST, LAST = 50036, 0xFFFF
# SSEmulator.getFolderName: the icon's folder by root (Item.as root ids).
FOLDERS = {0: "FireArm", 1: "WearItem", 2: "Heal_Item", 3: "Ammo", 4: "SimpleObject",
           5: "ColdArm", 6: "Trophy"}
# An internal name is a folder of the release: client/build.py's path rules
# (PART), and nothing that would read as another attribute in the XML row.
NAME = re.compile(r"[A-Za-z0-9_]+")
ROW = '<object type_id="%d" root_type_id= "%d" name="%s" />\n'


class Refused(ValueError):
    pass


def parse(doc):
    """type -> {"name", "like"} out of the file's document, checked for
    what needs no original: ids in our range, names a folder can carry,
    no name twice."""
    out, names = {}, {}
    for key, rec in (doc.get("items") or {}).items():
        if str(key).startswith("_"):
            continue
        where = "item %s" % key
        try:
            t = int(key)
        except ValueError:
            raise Refused("%s: the key is the type id, a number" % where)
        if not FIRST <= t <= LAST:
            raise Refused("%s: a type of ours is %d..%d (above the original's, within an "
                          "oid's four hex digits)" % (where, FIRST, LAST))
        if not isinstance(rec, dict):
            raise Refused("%s: not an object" % where)
        name, like = rec.get("name"), rec.get("like")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise Refused("%s: name %r is no internal name (letters, digits, _)" % (where, name))
        if name.lower() in names:
            raise Refused("%s: name %s is %d's too" % (where, name, names[name.lower()]))
        if isinstance(like, bool) or not isinstance(like, int):
            raise Refused("%s: like is the original type it copies, a number" % where)
        names[name.lower()] = t
        out[t] = dict(name=name, like=like)
    return out


def load(path=PATH):
    """The file's types (parse), {} when there is no file."""
    try:
        with io.open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise Refused("%s: %s" % (type(e).__name__, e))
    return parse(doc)


# A row of database/objects.xml as the client and items.catalogue read it,
# and a whole row with its line end, which objects_xml takes out of our range.
TABLE_ROW = re.compile(r'<object type_id="(\d+)" root_type_id=\s*"(\d+)" name="([^"]*)"')
ROW_LINE = re.compile(r'<object type_id="(\d+)"[^>]*/>[ \t]*(?:\r?\n)?')


def table(data):
    """type -> (root, name) out of a database/objects.xml, bytes or text."""
    if isinstance(data, bytes):
        data = data.decode("ascii", "replace")
    return {int(m.group(1)): (int(m.group(2)), m.group(3)) for m in TABLE_ROW.finditer(data)}


def originals(read):
    """A table as read, without its rows in our range. The original has
    none there, so such a row is ours -- a release's, as it is now or as an
    older release had it -- wherever the table was read: the objects.xml of
    a client the launcher has installed is the release's. What is left is
    the original's, which is what rows() checks ours against."""
    return {t: v for t, v in read.items() if not FIRST <= t <= LAST}


def rows(original, own=None):
    """type -> (root, name) of ours, checked against the original's
    catalogue (items.catalogue's shape: type -> (root, name)): like is one
    of its types with an icon folder, and our name is none of its. Rows of
    the table in our range are left out first (originals): ours, current or
    stale, never the original's."""
    own = load() if own is None else own
    original = originals(original)
    by_name = {n.lower(): t for t, (_r, n) in original.items()}
    out = {}
    for t, rec in sorted(own.items()):
        like = original.get(rec["like"])
        if like is None:
            raise Refused("item %d: like %d is no type of the original" % (t, rec["like"]))
        if like[0] not in FOLDERS:
            raise Refused("item %d: like %d has root %d, which has no icon folder"
                          % (t, rec["like"], like[0]))
        other = by_name.get(rec["name"].lower())
        if other is not None:
            raise Refused("item %d: the original's %d is named %s" % (t, other, rec["name"]))
        out[t] = (like[0], rec["name"])
    return out


def icon_path(root, name):
    """Where the client looks for a type's picture (SSEmulator.getIcon)."""
    return "classes/%s/%s/ico.swf" % (FOLDERS[root], name)


def icons(read, own=None):
    """Our icon path -> the original's icon path it is a copy of: like's
    (rows())."""
    own = load() if own is None else own
    original = originals(read)
    return {icon_path(root, name): icon_path(*original[own[t]["like"]])
            for t, (root, name) in rows(original, own).items()}


def objects_xml(original_bytes, mine):
    """The original's database/objects.xml with a row for each of ours
    (rows()) before its closing tag, in its own format: what the release
    ships. Any row the file has in our range goes first -- an objects.xml a
    release has written, read back, gives the same file, and a row of ours
    that is no longer (a rename, a type taken out) goes with it."""
    text = original_bytes.decode("ascii")
    text = ROW_LINE.sub(lambda m: "" if FIRST <= int(m.group(1)) <= LAST else m.group(0), text)
    end = text.rfind("</data>")
    if end < 0:
        raise Refused("database/objects.xml has no </data>")
    add = "".join(ROW % (t, root, name) for t, (root, name) in sorted(mine.items()))
    if add and not text[:end].endswith("\n"):
        add = "\n" + add
    return (text[:end] + add + text[end:]).encode("ascii")


def release_xml(data, own=None):
    """What the release ships as database/objects.xml, made from the one at
    hand, the original's or a release's: objects_xml with rows()."""
    return objects_xml(data, rows(table(data), own))
