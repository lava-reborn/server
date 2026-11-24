"""Formula boundaries only; actual medicine demand requires battle measurements."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import battle_balance
from testkit import run_cases


class PlusTwoPressure(unittest.TestCase):
    def test_resistance_is_local_to_plus_two_and_preserves_prepared_sites(self):
        player = NS(is_player=True, character=lambda: NS(level=16))
        target = NS(is_player=False, stats=NS(level=18, role='mob'), armor=lambda: 0)
        args = (player, target, 10000, 1, False, 0)
        self.assertEqual(battle_balance.split(*args, ordinary=True), (3693, 0))
        target._holding_prepared = True
        self.assertEqual(battle_balance.split(*args, ordinary=True), (3951, 0))
        target._holding_prepared = False
        for gap in (0, 1):
            target.stats.level = 16 + gap
            self.assertEqual(battle_balance.split(*args, ordinary=True), (10000, 0))

    def test_crit_rises_at_plus_two_without_making_every_hit_critical(self):
        player = NS(is_player=True, character=lambda: NS(level=16))
        mob = NS(is_player=False, stats=NS(level=18, role='mob', plain_weapon=True))
        for raw, expected in ((-100, 12), (16, 16), (100, 20)):
            self.assertEqual(battle_balance.critical_chance(mob, player, raw, ordinary=True), expected)
            self.assertEqual(battle_balance.critical_chance(mob, player, raw, False, ordinary=True), expected / 2)
        mob.stats.level = 17
        self.assertEqual(battle_balance.critical_chance(mob, player, 100, ordinary=True), 6)
        mob._holding_prepared = True
        self.assertEqual(battle_balance.critical_chance(mob, player, 20, ordinary=True), 20)

    def test_real_weapon_damage_is_not_multiplied_by_the_plus_two_change(self):
        player = NS(is_player=True, character=lambda: NS(level=16), armor=lambda: 0)
        mob = NS(is_player=False, stats=NS(level=18, role='mob', plain_weapon=True))
        for critical in (False, True):
            args = (mob, player, 100, 1, critical, 1000, 20)
            self.assertEqual(battle_balance.split(*args, ordinary=True), battle_balance.split(*args))

    def test_higher_steps_and_boss_equivalence_are_preserved(self):
        player = NS(is_player=True, character=lambda: NS(level=16))
        target = NS(is_player=False, stats=NS(level=18, role='mob'), armor=lambda: 0)
        args = (player, target, 10000, 1, False, 0)
        mob_plus_two = battle_balance.split(*args, ordinary=True)
        target.stats.role = 'boss'
        target.stats.level = 20
        self.assertEqual(battle_balance.split(*args, ordinary=True), mob_plus_two)
        target.stats.role = 'mob'
        # Final reviewed curve: floor(10000 * .748284 * .30) and
        # floor(10000 * .748284 * .5 * .25); +5 remains near-impermeable.
        for gap, expected in ((3, 2244), (4, 935), (5, 2)):
            target.stats.level = 16 + gap
            self.assertEqual(battle_balance.split(*args, ordinary=True), (expected, 0))

    def test_malformed_pressure_config_is_rejected_with_a_value_error(self):
        valid = json.loads(battle_balance.PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
        malformed = [None, [], {}, {'ordinary_mob_pressure': None},
                     {'ordinary_mob_pressure': []}, {'ordinary_mob_pressure': 'bad'}]
        arrays = ('stamina_levels', 'crit_bounds', 'crit_bonus_by_gap', 'player_damage_ratios',
                  'camp_hard_gap_damage_ratios', 'player_crit_ratios')
        for key in arrays:
            for value in (None, {}, 'bad'):
                row = deepcopy(valid)
                row['ordinary_mob_pressure'][key] = value
                malformed.append(row)
        for value in (None, 1, {}, 'bad'):
            row = deepcopy(valid)
            row['ordinary_mob_pressure']['crit_bounds'][2] = value
            malformed.append(row)
        for value in (None, True, 'bad', 0, .5, float('nan'), float('inf')):
            row = deepcopy(valid)
            row['ordinary_mob_pressure']['plus_two_damage_ratio'] = value
            malformed.append(row)
        row = deepcopy(valid)
        del row['ordinary_mob_pressure']['plus_two_damage_ratio']
        malformed.append(row)
        self.addCleanup(battle_balance.ordinary_mob_pressure.cache_clear)
        for index, row in enumerate(malformed):
            path = Mock()
            path.with_name.return_value.read_text.return_value = json.dumps(row)
            battle_balance.ordinary_mob_pressure.cache_clear()
            with self.subTest(case=index), patch.object(battle_balance, 'PATH', path), \
                    patch.object(battle_balance, 'data', return_value={'source_commit': valid['source_commit']}):
                with self.assertRaisesRegex(ValueError, 'Invalid ordinary mob pressure'):
                    battle_balance.ordinary_mob_pressure()


if __name__ == '__main__':
    run_cases(PlusTwoPressure)
