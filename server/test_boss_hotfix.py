"""Historical boss pool floors and regional gold rewards survive the release.

The combat release keeps historical HP/SP floors and uses plain A weapons
with KS rounds outside defended sites. Gold rewards and XP stay unchanged.
"""
import os
import random
import sys
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(__file__))
import bosses
import battle_balance
import combat
import holdings
import items
import mobs
import quests
import rooms
import world
from testkit import check, fails


CARRIERS = {2103, 269, 270, 283, 284, 299, 300, 313, 314,
            327, 328, 360, 361, 374, 375, 407, 408,
            777, 778, 8620, 1037, 1038}
PROFILE = battle_balance.data()
REFERENCE_RECORDS = battle_balance.world_boss_damage_references()
REFERENCES = {type_id: row['reference'] for type_id, row in REFERENCE_RECORDS.items()}


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
    weapon = items.params_of(st.weapon_type_id) if getattr(st, 'plain_weapon', False) else None
    scale = min(1, adjustment.get('damage_scale', 1) / 1.5)
    if weapon and items.root_of(st.weapon_type_id) == items.FIRE_ARM:
        mode = max((i for i, shots in enumerate(weapon['fire_mods']) if shots and weapon['max_range'][i]),
                   key=lambda i: weapon['max_range'][i])
        ammo = items.params_of(st.loot_ammo_type)
        damage = round(weapon['h_damage_min'][mode] * scale * ammo['dam_mod'])
    elif weapon and items.root_of(st.weapon_type_id) == items.COLD_ARM:
        damage = round(weapon['h_damage_min'] * scale)
    else:
        damage = round((accepted['dmg_min'] if accepted else original.dmg_min)
                       * adjustment.get('damage_scale', 1) / 1.5)
    if int(t) in REFERENCES:
        damage = min(damage, mobs.stats(REFERENCES[int(t)]).dmg_min)
    damage_bad = (not 0 <= st.dmg_min <= max(1, damage) if int(t) in REFERENCES
                  else st.dmg_min != max(1, damage))
    if (st.sp_max != max(original.sp_max, round((accepted['sp_max'] if accepted else original.sp_max) / 1.5))
            or damage_bad
            or st.xp_mult != role['xp_mult']):
        other_errors.append(int(t))
check('reviewed bosses follow the final reduction with the historical HP floor',
      health_errors, [])
check('boss SP/damage follow the final reduction and XP multipliers retain existing rules', other_errors, [])

# Apply the final cap after real item modes exist. Looking only at the pinned
# simulator's attack would miss a later A-weapon or ammunition substitution.
check('world boss damage references include every camp recovery boss',
      set(bosses.CAMP_RECOVERY_TYPES) <= REFERENCES.keys(), True)
manager = rooms.Rooms(world.mob_types())
reference_errors, cap_errors, increase_errors, pool_errors = [], [], [], []
for type_id, record in REFERENCE_RECORDS.items():
    reference_type = REFERENCES[type_id]
    for loc_id in record['locations']:
        ordinary = {npc.type_id: mobs.stats(npc.type_id) for npc in manager.get(loc_id).npcs.values()
                    if npc.root == world.MOB}
        ordinary = {t: st for t, st in ordinary.items() if st.role == 'mob' and st.can_attack
                    and t not in {1749, 1750, 1751, 2170}}
        if ordinary:
            if (reference_type not in ordinary
                    or ordinary[reference_type].level != min(st.level for st in ordinary.values())):
                reference_errors.append((loc_id, type_id, reference_type))
        elif mobs.stats(reference_type).level != mobs.stats(type_id).level:
            reference_errors.append((loc_id, type_id, 'fallback must match level'))
    reference = mobs.stats(reference_type)
    modes = getattr(reference, 'balanced_modes', ())
    mode = max(modes, key=lambda row: row['reach']) if modes else {}
    limits = dict(dmin=reference.dmg_min, dmax=reference.dmg_max,
                  sdmin=mode.get('sdmin', 0), sdmax=mode.get('sdmax', 0))
    after = mobs.stats(type_id)
    with patch.object(battle_balance, 'world_boss_damage_references', return_value={}):
        before = mobs.MobStats(type_id)
    if after.dmg_min > limits['dmin'] or after.dmg_max > limits['dmax']:
        cap_errors.append((type_id, 'display'))
    for previous, current in zip(getattr(before, 'balanced_modes', ()),
                                 getattr(after, 'balanced_modes', ())):
        if any(current.get(key, 0) > limit for key, limit in limits.items()):
            cap_errors.append((type_id, 'mode'))
        if (any(current.get(key, 0) > previous.get(key, 0) for key in limits)
                or {k: v for k, v in current.items() if k not in limits}
                != {k: v for k, v in previous.items() if k not in limits}):
            increase_errors.append(type_id)
        for low, high, per_ap, burst, per_second in (
                ('dmin', 'dmax', 'damage_per_ap', 'burst_damage', 'damage_per_second'),
                ('sdmin', 'sdmax', 'stamina_per_ap', 'burst_stamina', 'stamina_per_second')):
            if ((current[low] + current[high]) / 2 * current['shots'] / max(1, current['ap'])
                    > record['ceiling'][per_ap] + 1e-9
                    or current[high] * current['shots'] > record['ceiling'][burst] + 1e-9
                    or (current[low] + current[high]) / 2 * current['shots'] / max(.05, current['time'])
                    > record['ceiling'][per_second] + 1e-9):
                cap_errors.append((type_id, per_ap))
    if after.dmg_min > before.dmg_min or after.dmg_max > before.dmg_max:
        increase_errors.append(type_id)
    attack_keys = {'dmg_min', 'dmg_max', 'balanced_modes'}
    if ({k: v for k, v in vars(after).items() if k not in attack_keys}
            != {k: v for k, v in vars(before).items() if k not in attack_keys}):
        pool_errors.append(type_id)
    unchanged = deepcopy(vars(after))
    battle_balance.cap_world_boss_damage(after)
    if vars(after) != unchanged:
        increase_errors.append(type_id)
check('each world boss uses a real lowest-level room mob or a same-level fallback',
      reference_errors, [])
check('all actual world boss HP/SP attack bounds stay within that ordinary reference', cap_errors, [])
check('the final cap never increases damage, changes mode pacing or accumulates on reuse', increase_errors, [])
check('the final cap leaves boss health, stamina, level, crit and equipment unchanged', pool_errors, [])
unrelated = (bosses.WAREHOUSE_MASTERS | (bosses.ALL_DAY & frozenset(int(t) for t in mobs.TYPES
                                                                  if mobs.TYPES[t].get('role') == 'boss'))) - REFERENCES.keys()
unrelated_errors = []
for type_id in unrelated:
    current = mobs.MobStats(type_id)
    with patch.object(battle_balance, 'world_boss_damage_references', return_value={}):
        previous = mobs.MobStats(type_id)
    if vars(current) != vars(previous):
        unrelated_errors.append(type_id)
check('warehouse and unavailable private quest bosses keep their attacks', unrelated_errors, [])
site = mobs.MobStats(777, balanced=False)
with patch.object(battle_balance, 'cap_world_boss_damage', side_effect=AssertionError('site cap leak')):
    battle_balance.configure_mob(site, site=True)
check('a prepared site copy bypasses the ordinary camp boss cap', site.type_id, 777)
synthetic = deepcopy(mobs.stats(269))
synthetic.balanced_modes = (dict(shots=100, ap=1, reach=10, dmin=500, dmax=1000,
                                  sdmin=500, sdmax=1000, time=.1),)
battle_balance.cap_world_boss_damage(synthetic)
mode = synthetic.balanced_modes[0]
ceiling = REFERENCE_RECORDS[269]['ceiling']
check('a cheaper burst mode cannot bypass the frozen weaker boss damage ceiling',
      ((mode['dmin'] + mode['dmax']) / 2 * mode['shots'] / mode['ap'] <= ceiling['damage_per_ap'] + 1e-9
       and mode['dmax'] * mode['shots'] <= ceiling['burst_damage'] + 1e-9
       and (mode['dmin'] + mode['dmax']) / 2 * mode['shots'] / mode['time'] <= ceiling['damage_per_second'] + 1e-9
       and (mode['shots'], mode['ap'], mode['time']) == (100, 1, .1)), True)
valid = json.loads(battle_balance.PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
invalid = []
for value in (None, [], 'bad'):
    doc = deepcopy(valid)
    doc['world_boss_damage_references']['269']['ceiling'] = value
    invalid.append(doc)
for value in (None, True, -1, float('nan'), float('inf')):
    doc = deepcopy(valid)
    doc['world_boss_damage_references']['269']['ceiling']['damage_per_ap'] = value
    invalid.append(doc)
validation_errors = []
for index, doc in enumerate(invalid):
    path = Mock()
    path.with_name.return_value.read_text.return_value = json.dumps(doc)
    battle_balance.world_boss_damage_references.cache_clear()
    with patch.object(battle_balance, 'PATH', path):
        try:
            battle_balance.world_boss_damage_references()
        except ValueError:
            pass
        else:
            validation_errors.append(index)
battle_balance.world_boss_damage_references.cache_clear()
check('malformed frozen boss ceilings are rejected as invalid data', validation_errors, [])

# Use the same public transition graph as a player: static settlements and
# available quest/door/side ways, excluding retired places and private rooms.
data_dir = Path(__file__).resolve().parents[1] / 'data'
cut = {int(key) for key in json.loads((data_dir / 'retired.json').read_text(encoding='utf-8'))['places']
       if key.isdigit()}
passages = json.loads((data_dir / 'passages.json').read_text(encoding='utf-8'))
reachable = set(world.settlements().values()) - cut
while True:
    extra = set()
    for section in ('doors', 'sides', 'quest', 'walk_in'):
        for source, records in passages[section].items():
            if not source.isdigit() or int(source) not in reachable:
                continue
            for record in records.values() if isinstance(records, dict) else records:
                if record.get('confidence', 'high') not in ('high', 'manual'):
                    continue
                if section == 'quest':
                    quest = quests.get(record['quest'])
                    if quest is None or quests.acquisition_blocked(quest):
                        continue
                if record.get('target_loc_id') is not None:
                    extra.add(int(record['target_loc_id']))
    extra -= reachable | cut
    if not extra:
        break
    reachable |= extra
actual = {}
for loc_id in sorted(reachable):
    for npc in manager.get(loc_id).npcs.values():
        if npc.root != world.MOB or npc.type_id in bosses.WAREHOUSE_MASTERS:
            continue
        stats = mobs.stats(npc.type_id)
        if stats.role == 'boss' and stats.can_attack:
            actual.setdefault(npc.type_id, set()).add(loc_id)
check('every reachable world or quest boss is covered and no unavailable boss is added',
      {t: set(row['locations']) for t, row in REFERENCE_RECORDS.items()}, actual)

ordinary_errors = []
for t in (12, 14, 836, 930, 931):
    st = mobs.stats(t)
    if st.hp_max < mobs.MobStats(t, balanced=False).hp_max:
        ordinary_errors.append(t)
check('ordinary mobs and miners never fall below their original HP', ordinary_errors, [])

# Warehouse capture is a separate rule: each clan's harm is capped at the
# actual boss pool for logging; only the finishing clan may capture.
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
                                     (3, 2, pool // 2), (4, 2, pool - pool // 2 - 1),
                                     (5, 1, 1), (6, 2, 1))]
snapshot = dict(pool=pool, fighters=fighters, killer=4, killer_clan=2)
check('warehouse capture logs the actual HP and stamina pool for the finishing clan',
      holdings.winner(snapshot, squad=3, min_level=8), (2, '2', pool, 4))
fighters[3]['harm'] -= 1
check('the finishing clan wins even when another clan has more capped harm',
      holdings.winner(snapshot, squad=3, min_level=8), (2, '2', pool - 1, 4))

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

def bag(hours, type_id=777, killer_level=None, multiplier=1):
    rows = []
    def create(owner, t, root, **fields):
        row = dict(fields, type_id=t, root=root, char_id=owner)
        rows.append(row)
        return row
    loc = next(loc for loc, t in bosses.CAMP_RECOVERY_BOSSES if t == type_id)
    rc = NS(room=NS(loc=NS(id=loc)), store=NS(create_item=create))
    mob = NS(type_id=type_id, stats=mobs.stats(type_id), quest_wants={},
             blueprint_killer_level=killer_level, loot_multiplier=multiplier)
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
for type_id in sorted(CARRIERS):
    for delta, multiplier in ((5, 1), (10, 3), (5, 0)):
        on = bag([20 * 60], type_id, mobs.stats(type_id).level + delta, multiplier)
        off = bag([], type_id, mobs.stats(type_id).level + delta, multiplier)
        check('only the original ingots survive the level cutoff for boss %d, gap %d, loot x%d'
              % (type_id, delta, multiplier),
              ([(r['type_id'], r['count']) for r in on], off), (gold[type_id], []))
q = quests.get(10)
check('the valley exchange retains its two-ingot requirement and two-G reward',
      (q.wants(), q.rew_gold), ([(7620, 2)], 200))

if fails:
    print('\n'.join(fails))
    sys.exit(1)
