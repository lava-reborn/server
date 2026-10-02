"""Every location the client can draw, and which one a map cell leads into.

The id-to-file rule is a port of lol/services/SSEmulator.getLocDescription,
and both sides read the walkability grid out of whatever file they picked, so
a disagreement is not cosmetic: the player would walk through walls the client
is drawing, or into ones it is not.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import names
import world

from testkit import check, fails  # noqa: E402


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

# Nothing the server places may carry a name the client has not been handed.
# An unknown string id makes StringCollector fetch a batch, and a batch after
# login puts the login screen back on top of the game -- which is exactly how
# one wasteland creature undid the fix for it. Walking every location catches
# that statically, instead of waiting to stumble into the one location that
# happens to spawn it.
mobs = world.mob_types()
unnamed, undrawable = set(), set()
for i in ids:
    for _cell, type_id in world.location(i).spawns:
        if type_id in mobs and not names.known(type_id):
            unnamed.add(type_id)
        elif type_id and type_id not in mobs:
            undrawable.add(type_id)
check("every creature the server may place is already named", unnamed, set())
# The other 665 are the reason the filter exists: no record in mobs.xml means
# the client resolves the art to mobs/undefined.xml and the name to nothing.
check("and the rest are known to be unplaceable", len(undrawable) > 0, True)

# --- the map ---------------------------------------------------------------
cells = world.settlements()
check("settlements recovered", len(cells) >= 200, True)

# Only cells confirmed by standing on them in the client are pinned here;
# everything else the placer chose is checked by data/test_settlements.py
# for consistency, not for truth, and waits for a player to confirm it.
check("the new market is where it was played", world.location_at(5967, 1728), 104)

# Who stands in a room. The location file lists everyone who ever stood
# there: New Year lottery stalls, Victory Day traders, clan-event vendors,
# quest creatures and loot boxes. A market has none of that on an ordinary
# day, and open desert has no clan's trader in it.
import rooms
mobs = world.mob_types()
market = rooms.Room(world.location(102), rooms.IdAllocator(), mobs)
stalls = {mobs[n.type_id][1] for n in market.npcs.values()}
check("the market keeps its traders", "wh_Pistols" in stalls, True)
# The gold lottery (wh_lotery_g) is the town's own and stands again
# (world.SEASON_KEPT, 2026-09-28); the New Year presents stall does not.
check("but not the New Year presents", any("presents" in n for n in stalls), False)
check("nor the developers' stand-ins", any("Admin" in n for n in stalls), False)
waste = rooms.Room(world.location(world.pack(6100, 1901)), rooms.IdAllocator(), mobs)
check("open desert holds no event trader", len(waste.npcs), 0)
check("a hostile creature does not stand in a peaceful place",
      world.belongs_here(1, "mAntilope", world.MOB, war=0), False)
check("but does in the wasteland",
      world.belongs_here(1, "mAntilope", world.MOB, war=1), True)

# Stand-ins (a designed table, data/spawn_substitutes.json): a battle
# location whose fighters the client cannot draw gets known creatures of the
# same faction instead, and only there. The camp is found from the table
# itself, so the check does not pin any one file.
import json
with open(os.path.join(os.path.dirname(HERE), "data", "spawn_substitutes.json"),
          encoding="utf-8") as fh:
    subs = json.load(fh)["substitutes"]
camp = next(i for rec in subs.values() for i in rec["files"] if world.location(i).war)
camp_room = rooms.Room(world.location(camp), rooms.IdAllocator(), mobs)
stood_in = [n for n in camp_room.npcs.values()
            if n.type_id in {int(r["type_id"]) for r in subs.values()}]
check("a battle camp gets stand-ins for the creatures the client lacks",
      len(stood_in) > 0, True)
check("and every stand-in is a hostile", {n.root for n in stood_in}, {world.MOB})
calm = next((i for rec in subs.values() for i in rec["files"]
             if not world.location(i).war), None)
if calm is not None:
    calm_room = rooms.Room(world.location(calm), rooms.IdAllocator(), mobs)
    check("a peaceful place gets none",
          [n for n in calm_room.npcs.values()
           if n.type_id in {int(r["type_id"]) for r in subs.values()}], [])

# One file, one place. A title reused up and down the map used to pin the
# same location to cells hundreds apart, and at most one of those could be
# where it stood. A chain of neighbouring cells is allowed: a settlement may
# be wider than one cell, or a strip like the five cells of a mountain pass.
claims = {}
for cell, loc_id in cells.items():
    claims.setdefault(loc_id, []).append(cell)


def chained(cs):
    seen, frontier = {cs[0]}, [cs[0]]
    while frontier:
        a = frontier.pop()
        for b in cs:
            if b not in seen and abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 3:
                seen.add(b)
                frontier.append(b)
    return len(seen) == len(cs)


scattered = {i: cs for i, cs in claims.items() if not chained(cs)}
check("no location claimed from two ends of the map", scattered, {})

# Scratch files were never anywhere. KB_TESTCLAN_Block_Post is titled
# "Кладбище", generic enough that it had claimed six scattered cells. What
# data/settlements_verified.json puts down is the truth whatever the file is
# called: the valley's courier place 28 is Q_IV_test_gonec, on the map's own
# «Гонец» (6272,1833).
with open(os.path.join(os.path.dirname(HERE), "data", "settlements_verified.json"),
          encoding="utf-8") as _fh:
    _verified = {v for v in json.load(_fh)["cells"].values() if v is not None}
check("no scratch file ended up on the map, but for one a verified cell holds",
      [i for i in claims if "test" in world.location(i).fn.lower() and i not in _verified], [])
check("the black market is where it was played",
      world.location_at(5970, 1730), 102)
check("and Dongola's is its own", world.location_at(5879, 2012), 103)
check("naming them apart needed the region, not the name alone",
      world.location(102).title != world.location(103).title, True)
# The placer prefers the peaceful copy of a place: a night or war twin of a
# town file is never what the map leads into. Whatever it chose for the
# towns, none of it is a war file titled like a peaceful one.
calm_titles = {world.location(i).title for i in set(cells.values())
               if not world.location(i).war}
war_twins = [i for i in set(cells.values())
             if world.location(i).war and world.location(i).title in calm_titles]
check("no war twin of a peaceful place is on the map", war_twins, [])

# cell_of is location_at read backwards, and it is what puts a player sent
# straight to a settlement onto its cell: without it, leaving for the map
# dropped them wherever they last stood.
for _cell, _loc in list(world.settlements().items())[:40]:
    if world.cell_of(_loc) == _cell:
        check("a settlement answers with its own cell (%d)" % _loc,
              world.location_at(*_cell), _loc)
        break
check("an interior has no cell of its own", world.cell_of(1072), None)

# An unnamed cell must still answer, or the map has holes in it.
check("an unnamed cell still leads somewhere",
      world.location_at(6100, 1900), world.pack(6100, 1900))
# Fractional positions arrive mid-travel; the cell is the one the map drew.
# The client floors a position to its cell (DisplayGlobalMap.as:207), and
# draws the settlement from that square's corner, so 5970.9 is still cell
# 5970 while 5969.9 is the neighbour's, however close it looks.
check("a fractional position floors to the cell under it",
      world.location_at(5970.9, 1730.9), 102)
check("and just short of the square is the cell before",
      world.location_at(5969.9, 1730.5) == 102, False)

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
