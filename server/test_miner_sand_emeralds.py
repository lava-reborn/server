"""Magrib and Peacekeeper miners drop sand and emeralds without quests."""
import os
import random
import sqlite3
from collections import Counter
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
def no_database(*args, **kwargs):
    raise RuntimeError('Loot table checks must not open a database')
sqlite3.connect = no_database

import mobs
import items
from testkit import check, fails

# --- exact sources and real loot rolls without active quests ---
for mob in (838, 839, 840, 841):
    sand_chance = 0.75 if mob in (838, 839) else 1.0
    emerald_chance = 0.15 if mob in (838, 839) else 0.25
    table = mobs.loot_table(mob)
    check('%d: configured sand/emerald chances and tiers' % mob,
          [(t, c, v) for t, c, v in table if t in (2258, 3159)],
          [(3159, emerald_chance, True), (2258, sand_chance, False)])
    # Force just the two new rows through the full loot_for path.
    values = [0 if t in (2258, 3159) else 1 for t, c, v in table if c < 1]
    rolls = iter(values)
    with patch.object(mobs, 'carried', return_value=[]):
        rng = type('Rolls', (), {'random': lambda self: next(rolls)})()
        check('%d: both items actually appear without a quest' % mob,
              mobs.loot_for(mobs.stats(mob), rng), [(3159, 1), (2258, 1)])
    if mob in (840, 841):
        # Guaranteed Peacekeeper sand ignores the random-loot cap.
        for value in (0.0, 0.999999):
            with patch.object(mobs, 'carried', return_value=[]):
                rng = type('Fixed', (), {'random': lambda self: value})()
                drops = mobs.loot_for(mobs.stats(mob), rng)
            check('%d: exactly one guaranteed sand' % mob,
                  [row for row in drops if row[0] == 2258], [(2258, 1)])
            if value == 0.0:
                check('%d: sand is outside the random-loot cap' % mob,
                      len(drops), mobs.MAX_DROPS + 1)
    else:
        # Fail every unrelated row: assert the exact 75% boundary.
        for value, expected in ((0.749999, [(2258, 1)]), (0.75, [])):
            rolls = iter([value if t == 2258 else 1.0
                          for t, c, v in table if c < 1])
            with patch.object(mobs, 'carried', return_value=[]):
                rng = type('Rolls', (), {'random': lambda self: next(rolls)})()
                check('%d: exact 75 percent sand boundary' % mob,
                      mobs.loot_for(mobs.stats(mob), rng), expected)
    rng = random.Random(20261022)
    counts = Counter()
    for _ in range(20000):
        for t, n in mobs.roll_table(mob, rng):
            counts[t] += n
    if mob in (840, 841):
        check('%d: every kill yields sand' % mob, counts[2258], 20000)
    else:
        check('%d: sand respects 75 percent roll and random-loot cap' % mob,
              0.72 < counts[2258] / 20000 < 0.76, True)
    check('%d: emerald frequency matches its faction chance' % mob,
          abs(counts[3159] / 20000 - emerald_chance) < 0.01, True)

# --- faction case type, same five-percent chance, no quest required ---
for mob in (836, 837, 838, 839, 840, 841):
    case = 6946 if mob in (838, 839) else 6953
    other_case = 6953 if case == 6946 else 6946
    table = mobs.loot_table(mob)
    check('%d: faction cigarette case uses Nubian five-percent chance' % mob,
          [(c, v) for t, c, v in table if t == case], [(0.05, True)])
    check('%d: opposite faction case absent from table' % mob,
          any(t == other_case for t, c, v in table), False)
    for value, expected in ((0.049999, [(case, 1)]), (0.05, [])):
        rolls = iter([value if t == case else 1.0 for t, c, v in table if c < 1])
        with patch.object(mobs, 'carried', return_value=[]):
            rng = type('Rolls', (), {'random': lambda self: next(rolls)})()
            loot = mobs.loot_for(mobs.stats(mob), rng)
        check('%d: faction cigarette case exact boundary without quests' % mob,
              [row for row in loot if row[0] == case], expected)

# --- no accidental changes to other miners or item availability ---
for mob in (665, 930, 931):
    check('%d: no new sand or emerald row' % mob,
          [t for t, c, v in mobs.loot_table(mob) if t in (2258, 3159)], [])
for mob in (836, 837):
    check('%d: Nubian mine keeps original chances' % mob,
          [(t, c) for t, c, v in mobs.loot_table(mob) if t in (2258, 3159)],
          [(3159, 0.1), (2258, 0.5)])
check('both new loot items survive the corpse out-of-game filter',
      [items.out_of_game(t) for t in (2258, 3159)], [False, False])
if fails:
    for failure in fails:
        print(failure)
    raise SystemExit(1)
print('miner sand and emeralds OK')
