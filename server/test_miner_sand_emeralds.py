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
    emerald_chance = 0
    table = mobs.loot_table(mob)
    check('%d: configured sand/emerald chances and tiers' % mob,
          [(t, c, v) for t, c, v in table if t in (2258, 3159)],
          [(2258, sand_chance, False)])
    # Force just the two new rows through the full loot_for path.
    values = [0 if t in (2258, 3159) else 1 for t, c, v in table if c < 1]
    rolls = iter(values)
    with patch.object(mobs, 'carried', return_value=[]):
        rng = type('Rolls', (), {'random': lambda self: next(rolls)})()
        check('%d: both items actually appear without a quest' % mob,
              mobs.loot_for(mobs.stats(mob), rng), [(2258, 1)])
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

# Region income and full exact boundaries are covered by test_loot_rebalance.
# Existing shared item names do not imply that factions have exclusive cases.
for kind in (836,837,838,839,840,841):
    table=mobs.loot_table(kind)
    for target,chance,_ in table:
        if chance >= 1:
            continue
        for value,expected in ((chance-.000001,True),(chance,False)):
            rolls=iter(value if t==target else 1 for t,p,v in table if p<1)
            drops=mobs.roll_table(kind,type('Rolls',(),{'random':lambda self:next(rolls)})())
            check('%d: item %d exact probability boundary'%(kind,target),
                  any(t==target for t,n in drops),expected)

# --- no accidental changes to other miners or item availability ---
for mob in (665,):
    check('%d: no new sand or emerald row' % mob,
          [t for t, c, v in mobs.loot_table(mob) if t in (2258, 3159)], [])
for mob in (836, 837):
    check('%d: Nubian mine keeps original chances' % mob,
          [(t, c) for t, c, v in mobs.loot_table(mob) if t in (2258, 3159)],
          [(3159, .133461 if mob == 836 else .134471), (2258, .25)])
check('both new loot items survive the corpse out-of-game filter',
      [items.out_of_game(t) for t in (2258, 3159)], [False, False])
if fails:
    for failure in fails:
        print(failure)
    raise SystemExit(1)
print('miner sand and emeralds OK')
