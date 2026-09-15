"""Read a location's own XML: geometry, entry cells and mob spawns.

The shipped client kept more than artwork in res/locations. Alongside the
drawing instructions each file carries the walkability grid, the cells players
arrive on, and the spawn points with the type ids they refer to, for 1356 of
the 1396 locations. Only the serverdata node was emptied before release.

Coordinates are packed as hex byte pairs inside a single text node, read at a
fixed stride: 4 characters per cell for the plain lists, 5 where a per-cell
extra byte follows, and 8 for mob spawns, whose last four characters are the
type id. A hex cell's number is gy * width + gx.
"""
import os
import re

# The servers run under WSL while the client lives on the Windows drive, so
# fall back to the mounted path whenever the configured one is unreachable.
RES = os.environ.get("LAVA_RES") or ""
if not os.path.isdir(RES):
    for _candidate in (r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res",
                       "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        if os.path.isdir(_candidate):
            RES = _candidate
            break

# Entity.as: the class the client builds for an entity, taken from its
# root_type_id in mobs.xml and sent back as rtype in lch.
MOB, TRADER, TEACHER, UPGRADER, COMMONER, HEALER, LESSOR, AUCTIONER = range(8)

# The frame name is the dispatch key, so each class needs its own command.
USERINFO = {
    MOB: "userInfo",
    TRADER: "userInfo_Trader",
    TEACHER: "userInfo_SpecTrainer",
    UPGRADER: "userInfo_Upgrader",
    COMMONER: "userInfo_Commoner",
    HEALER: "userInfo_Medic",
    LESSOR: "userInfo_Lessor",
    AUCTIONER: "userInfo_Auctioneer",
}


def _read(path):
    """Location files are UTF-8 despite declaring windows-1251."""
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", "replace")


def _chunks(txt, tag, step):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), txt, re.S)
    if not m or not m.group(1).strip():
        return []
    s = "".join(m.group(1).split())
    return [s[i:i + step] for i in range(0, len(s) - step + 1, step)]


class Location:
    def __init__(self, loc_id):
        self.id = loc_id
        txt = _read(os.path.join(RES, "locations", "static", "%d.xml" % loc_id))
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        self.title = attrs.get("title", "")
        self.width = int(attrs["width"])
        self.height = int(attrs["height"])
        self.war = int(attrs.get("war", 0))
        self.pvp = int(attrs.get("pvp", 0))

        self.obstacles = {self._cell(c) for c in _chunks(txt, "obstacles", 5)}
        self.entries = [self._cell(c) for c in _chunks(txt, "inzones", 4)]
        self.spawns = [(self._cell(c), int(c[4:8], 16))
                       for c in _chunks(txt, "mobs", 8)]

    def _cell(self, chunk):
        gx, gy = int(chunk[0:2], 16), int(chunk[2:4], 16)
        return gy * self.width + gx

    def entry_cell(self):
        """A free entry cell, preferring one near whoever lives here.

        inzones usually rings the whole map, and its first cell tends to sit in
        a far corner with nothing around it. Spawning beside the inhabitants
        makes the location look inhabited the moment it opens.
        """
        free = [c for c in self.entries if c not in self.obstacles]
        if not free:
            return self.entries[0] if self.entries else 0
        if not self.spawns:
            return free[0]
        cx = sum(c % self.width for c, _t in self.spawns) / len(self.spawns)
        cy = sum(c // self.width for c, _t in self.spawns) / len(self.spawns)
        return min(free, key=lambda c: (c % self.width - cx) ** 2
                                       + (c // self.width - cy) ** 2)


def mob_types():
    """type_id -> (root_type_id, internal name, art folder).

    The art folder is the "resource" attribute, and it is what the client wants
    in the res field: it builds paths as mobs/<resource>/..., with names like
    1f_npc9 or q4-1 rather than anything numeric. Sending the type id there
    leaves the creature invisible.
    """
    txt = _read(os.path.join(RES, "database", "mobs.xml"))
    out = {}
    for m in re.finditer(r'<mob type_id="(\d+)"\s+root_type_id=\s*"(\d+)"'
                         r'\s+name="([^"]*)"(?:\s+resource="([^"]*)")?', txt):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3), m.group(4) or "")
    return out


def avatars():
    """The eight entries of avatars/list.xml as (id, sex) pairs.

    The two fields are not interchangeable and both have to come from the same
    entry. id picks the portrait, avatars/<id>_1.png. sex picks the body,
    because PersInfo.set sex assigns persType as a side effect and the walker
    resolves art as personages/<persType>. Mixing an id from one row with a sex
    from another puts a different person in the corner than the one standing in
    the location.
    """
    txt = _read(os.path.join(RES, "avatars", "list.xml"))
    return [(m.group(1), int(m.group(2)))
            for m in re.finditer(r"<a\s+id='([^']*)'\s+sex='(\d+)'", txt)]
