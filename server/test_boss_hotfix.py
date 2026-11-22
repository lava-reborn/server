"""Historical boss pool floors and regional gold rewards survive the release.

The combat release reduces reviewed HP/SP/damage by 1.5, with original HP/SP
as a floor. Gold carriers, exchange prices and XP multipliers stay unchanged.
"""
import os
import random
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import bosses
import battle_balance
import combat
import holdings
import items
import mobs
import quests
from testkit import check, fails


CARRIERS = {2103, 269, 270, 283, 284, 299, 300, 313, 314,
            327, 328, 360, 361, 374, 375, 407, 408,
            777, 778, 8620, 1037, 1038}
PROFILE = battle_balance.data()


def reviewed(type_id):
    index = PROFILE['mobs'].get(str(type_id))
    return PROFILE['mob_records'][index] if index is not None else None

health_errors, other_errors = [], []
for t, info in mobs.TYPES.items():
    if info.get('role') != 'boss':
        continue
    st = mobs.stats(int(t))
    role = mobs.ROLES['boss']
    original = mobs.MobStats(int(t), balanced=False)
    accepted = reviewed(t)
    adjustment = battle_balance.boss_adjustments().get(int(t), {})
    expected = max(original.hp_max, round((accepted['hp_max'] if accepted else original.hp_max)
                                         * adjustment.get('hp_scale', 1) / 1.5))
    if st.hp_max != expected:
        health_errors.append(int(t))
    if (st.sp_max != max(original.sp_max, round((accepted['sp_max'] if accepted else original.sp_max) / 1.5))
            or st.dmg_min != round((accepted['dmg_min'] if accepted else original.dmg_min)
                                   * adjustment.get('damage_scale', 1) / 1.5)
            or st.xp_mult != role['xp_mult']):
        other_errors.append(int(t))
check('reviewed bosses follow the final reduction with the historical HP floor',
      health_errors, [])
check('boss SP/damage follow the final reduction and XP multipliers retain existing rules', other_errors, [])

ordinary_errors = []
for t in (12, 14, 836, 930, 931):
    st = mobs.stats(t)
    if st.hp_max < mobs.MobStats(t, balanced=False).hp_max:
        ordinary_errors.append(t)
check('ordinary mobs and miners never fall below their original HP', ordinary_errors, [])

# Warehouse capture is a separate rule: each clan's harm is capped at the
# actual boss pool. Increased HP must not turn its tie fixture into a loss.
for kind in sorted(bosses.WAREHOUSE_MASTERS):
    st = mobs.stats(kind)
    base = mobs.LEVELS[str(max(0, min(mobs.MAX_LEVEL, st.level)))]["hp"]
    check('warehouse boss %d retains base HP' % kind,
          st.hp_max, round(base * mobs.ROLES[st.role]["hp_mult"]))
master = mobs.stats(7448)
pool = master.hp_max + master.sp_max
fighters = [dict(char=char, clan=clan, clan_name=str(clan), here=True,
                 alive=True, level=8, harm=harm)
            for char, clan, harm in ((1, 1, 5 * pool), (2, 1, 5 * pool),
                                     (3, 2, pool // 2), (4, 2, pool - pool // 2))]
snapshot = dict(pool=pool, fighters=fighters, killer=4, killer_clan=2)
check('warehouse capture tie uses the actual HP and stamina pool',
      holdings.winner(snapshot, squad=2, min_level=8), (2, '2', pool, 4))
fighters[-1]['harm'] -= 1
check('a killing blow cannot beat a clan with more capped harm',
      holdings.winner(snapshot, squad=2, min_level=8)[:3], (1, '1', pool))

carriers = {int(t) for t in mobs.TYPES
            if any(i in items.GOLD_INGOTS for i, _c, _v in mobs.loot_table(int(t)))}
check('gold carriers remain exactly the existing twenty two boss types', carriers, CARRIERS)
gold = {t: [(i, n) for i, n in mobs.roll_table(t, random.Random(t))
            if i in items.GOLD_INGOTS] for t in CARRIERS}
check('each existing carrier drops its regional one-ounce ingot count',
      gold, {t: [(7620, n)] for n, types in ((1, {2103, 269, 270, 283, 284, 299, 300, 313, 314}),
                                    (2, {327, 328, 360, 361}),
                                    (3, {374, 375, 407, 408}),
                                    (4, {777, 778, 8620, 1037, 1038})) for t in types})

def bag(hours):
    rows = []
    def create(owner, t, root, **fields):
        row = dict(fields, type_id=t, root=root, char_id=owner)
        rows.append(row)
        return row
    rc = NS(room=NS(loc=NS(id=132)), store=NS(create_item=create))
    mob = NS(type_id=777, stats=mobs.stats(777), quest_wants={})
    with patch.object(bosses, 'HOURS', hours), patch.object(combat, 'RNG', random.Random(1)):
        combat.RoomCombat.drop_loot(rc, mob)
    return rows

on, off = bag([14 * 60, 18 * 60, 22 * 60]), bag([])
check('real corpse creation preserves the scheduled-boss gold restriction',
      ([(r['type_id'], r['count']) for r in on if r['type_id'] in items.GOLD_INGOTS],
       [r['type_id'] for r in off if r['type_id'] in items.GOLD_INGOTS]),
      ([(7620, 4)], []))
check('disabling boss hours leaves non-gold corpse loot unchanged',
      [(r['type_id'], r['count']) for r in on if r['type_id'] not in items.GOLD_INGOTS],
      [(r['type_id'], r['count']) for r in off])
q = quests.get(10)
check('the valley exchange retains its two-ingot requirement and two-G reward',
      (q.wants(), q.rew_gold), ([(7620, 2)], 200))

if fails:
    print('\n'.join(fails))
    sys.exit(1)
