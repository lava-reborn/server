"""One bounded decision per server combat tick, using ordinary player actions."""
import battle_medicine
import combat
import inventory
import items
import mobs
import movement
import progression

PATH_LEGS = 8


def modes(ground, gun, distance):
    """At most three small estimates; the actual shot still uses Fighter."""
    enemy = ground.enemy
    si = items.params_of(gun['type_id'])
    ammo = items.params_of(gun['ammo_type']) or {}
    ch = enemy.character()
    spec = combat.SPEC_OF_WEAPON.get(si.get('weapon_type', items.PISTOL))
    factor = combat.spread_factor(ch.skill_level(progression.SHOOTING), combat.spec_or_zero(ch, spec))
    choices = []
    for mode, burst in enumerate(si['fire_mods']):
        if not burst or si['fire_costs'][mode] > enemy.combat.ap:
            continue
        shots, _rounds = combat.pull(si, mode, gun['ammo_count'])
        if not shots:
            continue
        weapon = combat.Weapon(shots, si['h_damage_min'][mode], si['h_damage_max'][mode],
            si['opt_range'][mode], si['end_opt_range'][mode], si['max_range'][mode],
            ammo.get('piercing', 1), combat.cone_of(factor, si['target_size'][mode],
                ammo.get('acc_mod', 1) or 1, si['max_range'][mode]), 0,
            progression.SHOOTING, spec)
        weapon = enemy.combat.prepare_weapon(weapon, ammo, gun, mode)
        if distance > weapon.max_range:
            continue
        hit = combat.hit_probability(weapon.cone, distance)
        # Expected HP per time spent aiming/firing; no RNG or simulated shots.
        duration = max(.1, (si['fire_times'][mode] + combat.action_animation.duration_ms(enemy, si, shots)) / 1000)
        score = shots * (weapon.dmin + weapon.dmax) / 2 * hit / duration
        choices.append((score, -si['fire_costs'][mode], -mode, mode))
    return max(choices)[3] if choices else None


def heal(ground):
    enemy = ground.enemy
    if (not ground.enemy_healing or ground.enemy_heals_left <= 0
            or battle_medicine.remaining_ms(ground.store, enemy.char_id, combat.now())):
        return False
    vitals = enemy.character().vitals()
    threshold = ground.heal_below / 100
    hp_low = vitals['hcur'] < vitals['hmax'] * threshold
    sp_low = vitals['scur'] < vitals['smax'] * threshold
    if not (hp_low or sp_low):
        return False
    for row in enemy.inv.rows():
        if row['root'] != items.HEAL or not items.battle_medicine(row['type_id']):
            continue
        si = items.params_of(row['type_id'])
        useful = (hp_low and si.get('max_h_rest', 0) > 0) or (sp_low and si.get('max_st_rest', 0) > 0)
        if useful and enemy.combat.ap >= si['heal_cost']:
            enemy.combat.use_heal(dict(obj=inventory.oid_of(row)), inventory.USE_IDLE)
            if enemy.combat.healing is not None:
                return True
    return False


def turn(ground):
    enemy = ground.enemy
    fighter = enemy.combat
    if (fighter.acting() or fighter.dead or fighter.reloading is not None
            or fighter.recovering() or enemy.walk is not None):
        return
    if heal(ground):
        return
    gun = enemy.inv.in_slot(inventory.PRIMARY)
    if gun and gun['root'] == items.FIRE_ARM and not gun['ammo_count']:
        si = items.params_of(gun['type_id'])
        if fighter.ap < si['reload_cost']:
            return
        stack = next((row for row in enemy.inv.rows() if row['root'] == items.AMMO
                      and row['type_id'] in si['comp_array']), None)
        if stack:
            enemy.inv.use_load(dict(obj=inventory.oid_of(gun), target=inventory.oid_of(stack)))
        return
    target = ground.clone.combat
    loc = enemy.loc
    distance = mobs.hex_distance(enemy.pos, target.cell, loc.width)
    firearm = gun and gun['root'] == items.FIRE_ARM
    mode = modes(ground, gun, distance) if firearm else None
    if firearm:
        si = items.params_of(gun['type_id'])
        if mode is not None and mode != gun['cur_mode']:
            enemy.inv.use_mode(dict(obj=inventory.oid_of(gun), target=format(mode, 'x')))
            gun = enemy.inv.in_slot(inventory.PRIMARY)
        ammo = items.params_of(gun['ammo_type']) or {}
        reach = max(r for r, burst in zip(si['max_range'], si['fire_mods']) if burst)
        if ground.rules.ammo_modifiers:
            reach *= ammo.get('range_mod', 1)
    else:
        reach = 1
    in_reach = distance <= reach if firearm else mobs.adjacent(enemy.pos, target.cell, loc)
    if not in_reach or combat.shot_wall(loc, enemy.pos, target.cell) is not None:
        target_cell = target.cell
        def goal(cell):
            reachable = (0 < mobs.hex_distance(cell, target_cell, loc.width) <= reach if firearm
                         else mobs.adjacent(cell, target_cell, loc))
            return reachable and combat.shot_wall(loc, cell, target_cell) is None
        blocked = movement.get(ground.room).occupied(exclude=enemy)
        path = mobs.find_path(loc, enemy.pos, goal, blocked, toward=target_cell)
        if path and len(path) > 1:
            # One short continuous route, not a one-cell start/stop per AI tick.
            enemy.move_in_location(dict(path=path[:PATH_LEGS + 1]))
        return
    if not firearm or mode is not None:
        fighter.use_fire(dict(obj=inventory.oid_of(gun) if gun else '0', target='1%08x' % target.eid))
