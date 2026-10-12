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
both: the server at start, the release at build.

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


def rows(original, own=None):
    """type -> (root, name) of ours, checked against the original's
    catalogue (items.catalogue's shape: type -> (root, name)): like is one
    of its types with an icon folder, and neither our id nor our name is
    already one of its. A row the original already holds as it is -- a
    release's objects.xml, ours included, read as the original -- is ours
    all the same."""
    own = load() if own is None else own
    by_name = {n.lower(): t for t, (_r, n) in original.items()}
    out = {}
    for t, rec in sorted(own.items()):
        like = original.get(rec["like"])
        if like is None:
            raise Refused("item %d: like %d is no type of the original" % (t, rec["like"]))
        if like[0] not in FOLDERS:
            raise Refused("item %d: like %d has root %d, which has no icon folder"
                          % (t, rec["like"], like[0]))
        mine = (like[0], rec["name"])
        if t in original and original[t] != mine:
            raise Refused("item %d: the original has this type, %s" % (t, original[t][1]))
        other = by_name.get(rec["name"].lower())
        if other is not None and other != t:
            raise Refused("item %d: the original's %d is named %s" % (t, other, rec["name"]))
        out[t] = mine
    return out


def icon_path(root, name):
    """Where the client looks for a type's picture (SSEmulator.getIcon)."""
    return "classes/%s/%s/ico.swf" % (FOLDERS[root], name)


def objects_xml(original_bytes, mine):
    """The original's database/objects.xml with a row for each of ours
    (rows()) before its closing tag, in its own format: what the release
    ships. Rows the file already has stay as they are, once."""
    text = original_bytes.decode("ascii")
    end = text.rfind("</data>")
    if end < 0:
        raise Refused("database/objects.xml has no </data>")
    add = "".join(ROW % (t, root, name) for t, (root, name) in sorted(mine.items())
                  if (ROW % (t, root, name)) not in text)
    if add and not text[:end].endswith("\n"):
        add = "\n" + add
    return (text[:end] + add + text[end:]).encode("ascii")
