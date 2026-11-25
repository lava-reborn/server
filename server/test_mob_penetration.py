"""Pure live-formula penetration boundaries; no RNG or simulated fights."""
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')

import battle_balance as balance
import combat
import inventory
import items
import mob_loadouts
import mobs
import progression
import sets
from testkit import run_cases


OLD_RATIOS = (.12, .14, .005)


def afro_character(level, weapon_class, spec=4):
    character = progression.Character()
    character.set_skill(progression.SHOOTING, level)
    kinds = {'pistol': items.PISTOL, 'shotgun': items.SHOTGUN, 'smg': items.SMG,
             'assault_rifle': items.ASSAULT, 'rifle': items.RIFLE, 'machine_gun': items.MACHINEGUN}
    character.set_spec(combat.SPEC_OF_WEAPON[kinds[weapon_class]], spec)
    outfit = max((record for record in sets.records()
                  if record['variant'] == 'A' and record['level'] <= level),
                 key=lambda record: record['level'])
    rows = [dict(type_id=outfit['members'][slot_name], root=items.WEAR, slot=slot, brk=1)
            for slot_name, slot in zip(sets.SLOTS, inventory.SET_SLOTS)]
    character.set_gear(inventory.gear_bonus(rows, character), inventory.card_repeat(rows))
    return character


def afro_modes(character, weapon_class, suffix='_ST'):
    choices = [row for row in balance.mob_weapons().get(weapon_class, ()) if row[0] <= character.level]
    if not choices:
        return
    type_id = max(choices, key=lambda row: (row[0], row[1], -row[2]))[2]
    params = items.params_of(type_id)
    ammo_type = next((t for t in params['comp_array'] if items.catalogue()[t][1].endswith(suffix)), None)
    if ammo_type is None:
        return
    ammo = items.params_of(ammo_type)
    spec = combat.SPEC_OF_WEAPON[params['weapon_type']]
    spread = combat.spread_factor(character.skill_level(progression.SHOOTING),
                                  combat.spec_or_zero(character, spec))
    crit = progression.crit_chance(character, params['weapon_type'])[0]
    for mode, count in enumerate(params['fire_mods']):
        if not count:
            continue
        shots, rounds = combat.pull(params, mode, 10000)
        weapon = combat.Weapon(shots, params['h_damage_min'][mode], params['h_damage_max'][mode],
            params['opt_range'][mode], params['end_opt_range'][mode], params['max_range'][mode],
            ammo.get('piercing', 1),
            combat.cone_of(spread, params['target_size'][mode], ammo.get('acc_mod', 1) or 1,
                           params['max_range'][mode]),
            crit, progression.SHOOTING, spec,
            sdmin=params.get('st_damage_min', [0, 0, 0])[mode],
            sdmax=params.get('st_damage_max', [0, 0, 0])[mode])
        prepared = balance.weapon(weapon, character, dict(type_id=type_id, cur_mode=mode), ammo)
        yield type_id, ammo_type, mode, prepared, rounds


class MobPenetration(unittest.TestCase):
    def test_every_camp_type_has_a_positive_plus_three_damage_path(self):
        members = {t for group, _sniper in mob_loadouts.policy()[0].values() for t in group}
        checked_types, profiles = set(), 0
        for type_id in members:
            target = mobs.Mob(1, type_id, 0)
            player_level = target.level - 3
            if not 1 <= player_level <= 17:
                continue
            for kind in ('pistol', 'shotgun', 'smg', 'assault_rifle', 'rifle', 'machine_gun'):
                character = afro_character(player_level, kind)
                shooter = NS(is_player=True, character=lambda: character)
                for suffix in ('_KS', '_ST', '_OT'):
                    for gun, ammo, mode, weapon, _rounds in afro_modes(character, kind, suffix):
                        full = combat.RoomCombat.bullet_damage(None, shooter, target, weapon,
                            weapon.dmax, weapon.sdmax, False, target.sp)
                        empty = combat.RoomCombat.bullet_damage(None, shooter, target, weapon,
                            weapon.dmax, weapon.sdmax, False, 0)
                        self.assertGreater(sum(full), 0, (type_id, gun, ammo, mode))
                        self.assertGreater(empty[0], 0, (type_id, gun, ammo, mode))
                        self.assertEqual(empty[1], 0)
                        self.assertGreaterEqual(empty[0], full[0])
                        profiles += 1
                        checked_types.add(type_id)
        self.assertEqual(len(members), 174)
        self.assertEqual(len(checked_types), 147)
        self.assertGreater(profiles, 2000)

    def test_m249_selected_rounds_and_sturm_a_seventeen_reach_hp_after_stamina(self):
        character = afro_character(17, 'machine_gun')
        shooter = NS(is_player=True, character=lambda: character)
        target = mobs.Mob(1, 1732, 0)
        gun, ammo, _mode, weapon, rounds = list(afro_modes(character, 'machine_gun', '_OT'))[2]
        self.assertEqual((gun, ammo, weapon.num_shots, rounds), (25022, 6121, 9, 9))
        self.assertEqual((target.hp, target.sp), (621, 621))
        self.assertEqual(character.ap_ceiling, 200)
        low = weapon.dmin + (weapon.dmax - weapon.dmin) // 2
        self.assertEqual((low, weapon.dmax), (54, 80))
        for raw, expected in ((low, 13), (weapon.dmax, 19)):
            args = (shooter, target, raw, weapon.piercing, False)
            self.assertEqual(balance.split(*args, target.sp, ordinary=True), (0, expected))
            self.assertEqual(balance.split(*args, 0, ordinary=True), (expected, 0))
            self.assertEqual(balance.split(*args, 2, ordinary=True), (expected - 2, 2))

    def test_all_plain_level_seventeen_weapons_have_positive_near_and_far_impact(self):
        tested = 0
        for kind, rows in balance.mob_weapons().items():
            if kind == 'knife':
                continue
            for tier, _cost, gun in rows:
                if tier != 17:
                    continue
                character = afro_character(17, kind)
                shooter = NS(is_player=True, character=lambda: character)
                target = mobs.Mob(1, 1732, 0)
                params = items.params_of(gun)
                ammo = items.params_of(next(t for t in params['comp_array']
                                           if items.catalogue()[t][1].endswith('_ST')))
                for mode, shots in enumerate(params['fire_mods']):
                    if not shots:
                        continue
                    for damage in (params['h_damage_min'][mode], params['h_damage_max'][mode]):
                        self.assertGreater(sum(balance.split(shooter, target,
                            round(damage * ammo.get('dam_mod', 1)), ammo.get('piercing', 1),
                            False, target.sp, ordinary=True)), 0)
                        tested += 1
        self.assertGreater(tested, 10)

    def test_gap_ladder_is_monotonic_at_every_player_level(self):
        for player_level in range(1, 18):
            shooter = NS(is_player=True, character=lambda: NS(level=player_level))
            outputs = []
            for gap in range(6):
                target = NS(is_player=False, stats=NS(level=player_level + gap, role='mob'), armor=lambda: 0)
                outputs.append(balance.split(shooter, target, 10000, 1, False, 0, ordinary=True)[0])
            self.assertEqual(outputs, sorted(outputs, reverse=True), (player_level, outputs))
            self.assertGreater(outputs[3], outputs[4])
            self.assertGreater(outputs[4], outputs[5])

    def test_plus_five_near_impenetrability_is_unchanged(self):
        current = dict(balance.ordinary_mob_pressure())
        old = dict(current, camp_hard_gap_damage_ratios=OLD_RATIOS)
        for level in range(1, 18):
            shooter = NS(is_player=True, character=lambda: NS(level=level))
            target = NS(is_player=False, stats=NS(level=level + 5, role='mob'), armor=lambda: 0)
            for damage in (1, 20, 100, 500, 10000):
                actual = balance.split(shooter, target, damage, 1, False, 0, ordinary=True)
                with patch.object(balance, 'ordinary_mob_pressure', return_value=old):
                    previous = balance.split(shooter, target, damage, 1, False, 0, ordinary=True)
                self.assertEqual(actual, previous)
                if damage <= 100:
                    self.assertEqual(actual, (0, 0))
            # Arbitrary 500/10000-damage diagnostics may still round above
            # zero at early levels. Check the actual A catalogue separately.
            for kind in ('pistol', 'shotgun', 'smg', 'assault_rifle', 'rifle', 'machine_gun'):
                character = afro_character(level, kind)
                actor = NS(is_player=True, character=lambda: character)
                for _gun, _ammo, _mode, weapon, _rounds in afro_modes(character, kind, '_ST'):
                    self.assertEqual(balance.split(actor, target, weapon.dmax, weapon.piercing,
                        False, 0, weapon.sdmax, rifle=kind == 'rifle', ordinary=True), (0, 0))

    def test_site_and_private_formula_outputs_are_unchanged(self):
        old = dict(balance.ordinary_mob_pressure(), camp_hard_gap_damage_ratios=OLD_RATIOS)
        shooter = NS(is_player=True, character=lambda: NS(level=17))
        for role in ('mob', 'boss'):
            for prepared in (False, True):
                target = NS(is_player=False, stats=NS(level=20, role=role), armor=lambda: 900,
                            _holding_prepared=prepared)
                for ordinary in (False, True):
                    if ordinary and role == 'mob' and not prepared:
                        continue
                    args = (shooter, target, 100, 1, False, 50)
                    actual = balance.split(*args, ordinary=ordinary)
                    with patch.object(balance, 'ordinary_mob_pressure', return_value=old):
                        self.assertEqual(balance.split(*args, ordinary=ordinary), actual)

    def test_rifle_and_melee_keep_their_native_armour_and_overflow_rules(self):
        shooter = NS(is_player=True, character=lambda: NS(level=17))
        target = mobs.Mob(1, 1732, 0)
        for rifle, melee in ((False, False), (True, False), (False, True)):
            full = balance.split(shooter, target, 100, 1, False, target.sp,
                                 rifle=rifle, melee=melee, ordinary=True)
            empty = balance.split(shooter, target, 100, 1, False, 0,
                                  rifle=rifle, melee=melee, ordinary=True)
            self.assertGreater(sum(full), 0)
            self.assertEqual(sum(full), sum(empty))
            self.assertEqual(empty[1], 0)
            if rifle:
                self.assertGreater(full[0], 0)
            else:
                self.assertEqual(full[0], 0)
        self.assertEqual(balance.split(shooter, target, 100, 1, True, target.sp,
                                       melee=True, ordinary=True)[1], 0)


if __name__ == '__main__':
    raise SystemExit(run_cases(MobPenetration))
