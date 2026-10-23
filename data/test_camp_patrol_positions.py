"""Patrol spawn points must have a path to an entrance.

Read-only, no server or database. Run with LAVA_RES pointing to client resources.
"""
import json
import os
import sys
from collections import deque
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import build_camp_patrols as builder
import progression
import world
from testkit import check, fails

# A free island is not reachable just because its own cell is walkable.
loc = SimpleNamespace(width=7, height=7, entries=[0], file="isolated fixture",
                      obstacles=set(progression.hex_neighbours(24, 7, 7)))
check("an isolated free cell is excluded", 24 in builder.accessible_cells(loc), False)
check("the entrance stays reachable", 0 in builder.accessible_cells(loc), True)

with open(builder.PATH, encoding="utf-8") as fh:
    table = json.load(fh)["locations"]
actual = {int(k): [r for r in rows if "patrol" in r]
          for k, rows in table.items() if any("patrol" in r for r in rows)}
built = builder.rows()
check("stored patrols match the generator", actual, built)
check("repeated generation is deterministic", builder.rows(), built)
problems = []
for lid, rows in actual.items():
    loc = world.location(lid)
    # Independent flood fill from the entrances, not the builder's helper.
    reached = {c for c in loc.entries if c not in loc.obstacles}
    queue = deque(reached)
    while queue:
        for c in progression.hex_neighbours(queue.popleft(), loc.width, loc.height):
            if c not in loc.obstacles and c not in reached:
                reached.add(c)
                queue.append(c)
    cells = [r["cell"][1] * loc.width + r["cell"][0] for r in rows]
    if len(cells) != len(set(cells)):
        problems.append((lid, "duplicate"))
    for cell in cells:
        if cell not in reached:
            problems.append((lid, cell))
check("all patrols have a path to an entrance", problems, [])
# Accessible positions must not be moved just for being beside rocks.
unchanged_problems = []
for lid, rows in actual.items():
    loc = world.location(lid)
    originals = builder.SLOTS4 if rows[0]["patrol"] == 34 else builder.SLOTS8
    reached = builder.accessible_cells(loc)
    for row, (x, y) in zip(rows, originals):
        if y * loc.width + x in reached and row["cell"] != [x, y]:
            unchanged_problems.append((lid, row["type"]))
check("all originally reachable patrol positions stay unchanged", unchanged_problems, [])
target = actual[world.pack(5869, 1854)]
check("the reported mob leaves its isolated original position",
      [r["cell"] for r in target if r["type"] == 350] != [[39, 95]], True)
if fails:
    print("\n".join(fails))
    sys.exit(1)
