"""Immutable equipment choices and per-spawn combat data for sandbox mobs."""
from functools import lru_cache

import combat
import craft
import inventory
import items
import mobs
import progression
import sets
import training_balance
import training_items

CLASSES = {'pistol': items.PISTOL, 'shotgun': items.SHOTGUN,
           'smg': items.SMG, 'assault_rifle': items.ASSAULT,
           'rifle': items.RIFLE, 'machine_gun': items.MACHINEGUN}


@lru_cache(maxsize=128)
def equipment(level, weapon_class):
    import training_ground as training
    catalogue = training.item_catalogue()
    kind = CLASSES.get(weapon_class)
    candidates = [source for source, (category, item_level, _label) in catalogue.items()
                  if category == 'weapon' and 0 < item_level <= level
                  and training.item_line(source) == 'A' and source not in training.contraband()
                  and not craft.mod_of(source) and items.root_of(source) == items.FIRE_ARM
                  and items.params_of(source).get('weapon_type') == kind]
    gun = min(candidates, key=lambda source: (-catalogue[source][1], source)) if candidates else None
    armour = [record for record in sets.SETS.values()
              if record['variant'] == 'A' and record['level'] <= level
              and all(source in catalogue for source in record['members'].values())]
    worn = max(armour, key=lambda record: record['level'])['members'].values() if armour else ()
    return gun, tuple(worn)


def configure(mob, ground):
    """Called once at spawn. Animals retain their natural attack and curves."""
    if not ground.rules.combat_v2 or mob.stats.role not in ('mob', 'boss'):
        return
    import training_ground as training
    st = mob.stats
    gun, worn = equipment(st.level, st.weapon_class)
    profile = training.preset(st.level)
    profile['specs'][:8] = [min(progression.SPEC_MAX, st.level // 4)] * 8
    ch = training.character(profile, ground.rules)
    fields = []
    for source in worn:
        copy_type = training_items.copy_type(source)
        row = inventory.new_fields(copy_type, 1)
        row.update(type_id=copy_type, slot=inventory.HEAD + items.params_of(copy_type)['slot_type'])
        fields.append(row)
    ch.set_gear(inventory.gear_bonus(fields, ch))
    role = mobs.ROLES.get(st.role, mobs.ROLES['mob'])
    health = role['hp_mult']
    st.hp_max = max(1, round(ch.hp_max * health))
    st.sp_max = max(1, round(ch.sp_max * health))
    st.ap_max = ch.ap_ceiling
    st.armor = (progression.armor_class(ch, sum(items.params_of(r['type_id']).get('armor_class', 0)
                                               for r in fields)) + ground.rules.effect_armour) * ground.rules.armour
    st.dodge = progression.melee_evade(ch)
    if gun is None:
        return
    st.weapon_type_id = training_items.copy_type(gun)
    params = items.params_of(st.weapon_type_id)
    ammo_type = next(iter(params.get('comp_array', ())), None)
    ammo = items.params_of(ammo_type) or {}
    mode = next(i for i, enabled in enumerate(params['fire_mods']) if enabled)
    kind = params['weapon_type']
    spec = combat.SPEC_OF_WEAPON[kind]
    cp, ce = progression.crit_chance(ch, kind)
    weapon = combat.Weapon(
        num_shots=combat.pull(params, mode, params['clip_size'])[0], dmin=params['h_damage_min'][mode],
        dmax=params['h_damage_max'][mode], sdmin=params.get('st_damage_min', [0]*3)[mode],
        sdmax=params.get('st_damage_max', [0]*3)[mode],
        opt_lo=params['opt_range'][mode], opt_hi=params['end_opt_range'][mode],
        max_range=params['max_range'][mode], piercing=ammo.get('piercing', 1),
        cone=combat.cone_of(combat.spread_factor(st.level, ch.spec_level(spec)),
                            params['target_size'][mode], ammo.get('acc_mod', 1), params['max_range'][mode]),
        crit=cp, skill=None, spec=None, through=kind in combat.THROUGH_TYPES)
    weapon = ground.rules.weapon(weapon, ammo)
    multiplier = training_balance.intellect_multiplier(ch) * role['dmg_mult']
    weapon = weapon._replace(**{field: training_balance.rounded(getattr(weapon, field) * multiplier)
                                for field in ('dmin', 'dmax', 'sdmin', 'sdmax')})
    mob.training_weapon = weapon
    st.loot_ammo_type = ammo_type
    st.attack_ap, st.attack_time = params['fire_costs'][mode], params['fire_times'][mode] / 1000
    st.shots, st.range = weapon.num_shots, weapon.max_range
    st.crit, st.crit_evade = cp, ce
    st.dmg_min, st.dmg_max = weapon.dmin, weapon.dmax
    st.spec = ch.spec_level(spec)
    st.scatter = params['target_size'][mode] / params['max_range'][mode]
