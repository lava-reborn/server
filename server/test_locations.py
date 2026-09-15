"""Every location the client can draw, and which one a map cell leads into.

The id-to-file rule is a port of lol/services/SSEmulator.getLocDescription,
and both sides read the walkability grid out of whatever file they picked, so
a disagreement is not cosmetic: the player would walk through walls the client
is drawing, or into ones it is not.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import world

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def name(loc_id):
    return world.location(loc_id).file


# --- the client's own rule --------------------------------------------------
check("a file number is its own file", name(102), "static/102.xml")

# A cell with nothing on it packs into an id that picks one of four wasteland
# tiles from its own coordinates. This is what makes the whole map enterable
# without a table: no data has to exist for a cell to lead somewhere.
geo = world.pack(5970, 1730)
check("a map cell packs the way the client unpacks it", geo, 48907970)
check("and unpacks back", world.unpack(geo), (5970, 1730))
check("an empty cell is open desert", name(world.pack(6100, 1900)),
      "desert/0001.xml")
# ((gx + gy) & 3) + 1, so neighbouring cells differ
check("neighbouring cells draw different tiles",
      [name(world.pack(6100, 1900 + d))[-8:] for d in range(4)],
      ["0001.xml", "0002.xml", "0003.xml", "0004.xml"])
check("the death locations resolve too",
      name((4 << 28) | (2 << 26)), "deadloc/2.xml")

# A file number and a packed cell are both just integers, and telling them
# apart is what keeps /goto 456 from being read as cell 0x456.
check("a file number is not wilderness", world.is_wilderness(456), False)
check("a packed cell is", world.is_wilderness(geo), True)

# --- every file the client ships --------------------------------------------
d = os.path.join(world.RES, "locations", "static")
ids = sorted(int(f[:-4]) for f in os.listdir(d) if f.endswith(".xml"))
check("all 1381 static locations present", len(ids), 1381)

broken = []
without_entry = []
for i in ids:
    try:
        loc = world.location(i)
    except Exception as exc:
        broken.append((i, exc))
        continue
    # entry_cell is what the player is placed on; a location with no free one
    # would drop them at cell 0, which is a corner and usually a wall.
    if not loc.entries:
        without_entry.append(i)
check("every one of them parses", broken, [])
check("every one offers somewhere to stand", without_entry, [])

# --- the map ---------------------------------------------------------------
cells = world.settlements()
check("settlements recovered", len(cells) >= 60, True)

# One file, one place. A title reused up and down the map used to pin the
# same location to cells hundreds apart, and at most one of those could be
# where it stood. Neighbouring cells are allowed: a settlement may be wider
# than one cell.
claims = {}
for cell, loc_id in cells.items():
    claims.setdefault(loc_id, []).append(cell)
scattered = {i: cs for i, cs in claims.items()
             if max(abs(a[0] - b[0]) + abs(a[1] - b[1])
                    for a in cs for b in cs) > 3}
check("no location claimed from two ends of the map", scattered, {})

# Scratch files were never anywhere. KB_TESTCLAN_Block_Post is titled
# "Кладбище", generic enough that it had claimed six scattered cells.
check("no scratch file ended up on the map",
      [i for i in claims if "test" in world.location(i).fn.lower()], [])
check("the black market is where it was played",
      world.location_at(5970, 1730), 102)
check("and Dongola's is its own", world.location_at(5879, 2012), 103)
check("naming them apart needed the region, not the name alone",
      world.location(102).title != world.location(103).title, True)
# An unnamed cell must still answer, or the map has holes in it.
check("an unnamed cell still leads somewhere",
      world.location_at(6100, 1900), world.pack(6100, 1900))
# Fractional positions arrive mid-travel; the cell is the one the map drew.
check("a fractional position rounds to the cell under it",
      world.location_at(5970.4, 1729.6), 102)

# Every recovered settlement has to resolve, or a cell on the map opens
# nothing at all.
unresolved = [c for c, i in cells.items() if world.path_for(i) is None]
check("every recovered settlement resolves", unresolved, [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("locations OK")
