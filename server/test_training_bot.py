"""Configured player-like enemies use bounded routes, modes and real medicine."""
import unittest
from unittest.mock import patch
import battle_medicine
import combat
import inventory
import items
import mobs
from training import bot as bot
from training import character as range_character
from training import session as training
from training import items as copies
import test_training_ground as fixtures


class TrainingBot(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged

    def fighter(self, healing=False, count=5, spawn=None):
        ground = self.enter()
        source = 25055  # M60 A, three modes with different effective distances.
        ammo = items.params_of(source)['comp_array'][0]
        profile = dict(skills=[0, 20, 20, 0, 0], specs=[5] * 12 + [-1] * 3,
                       gear={source: 1, ammo: 200})
        ground.opponent = range_character.validate_profile(profile)
        ground.enemy_healing = healing
        ground.heal_count = count
        if spawn is not None:
            ground.spawn_point = spawn
        ground.start('fighter')
        enemy = ground.enemy
        gun = enemy.inv.in_slot(inventory.PRIMARY)
        ground.store.update_item(gun['uniq'], ammo_count=50, ammo_type=copies.copy_type(ammo))
        enemy.combat.ap = enemy.combat.ap_max
        return ground, enemy, ground.store.item(gun['uniq'])

    async def test_real_modes_change_with_distance_and_never_fire_beyond_range(self):
        ground, _enemy, gun = self.fighter()
        near = bot.modes(ground, gun, 2)
        far = bot.modes(ground, gun, 33)
        self.assertIsNotNone(near)
        self.assertEqual(far, 0)
        self.assertNotEqual(near, far)
        self.assertIsNone(bot.modes(ground, gun, 100))
        self.unchanged()

    async def test_no_path_search_or_action_while_already_walking(self):
        ground, enemy, _gun = self.fighter()
        marker = object()
        enemy.walk = marker
        try:
            with patch.object(mobs, 'find_path', side_effect=AssertionError('redundant path')):
                ground.enemy_turn()
        finally:
            enemy.walk = None

    async def test_far_enemy_gets_a_bounded_multicell_route_not_single_step(self):
        ground, enemy, _gun = self.fighter(spawn=2)
        with patch.object(enemy, 'move_in_location') as move:
            ground.enemy_turn()
        path = move.call_args.args[0]['path']
        self.assertGreater(len(path), 2)
        self.assertLessEqual(len(path), bot.PATH_LEGS + 1)
        self.assertEqual(path[0], enemy.pos)
        self.unchanged()

    async def test_disabled_healing_never_uses_or_grants_medicine(self):
        ground, enemy, _gun = self.fighter()
        enemy.char.hp = 1
        with patch.object(enemy.combat, 'use_heal', side_effect=AssertionError('disabled')):
            self.assertFalse(bot.heal(ground))
        self.assertFalse([row for row in enemy.inv.rows() if row['root'] == items.HEAL])
        self.unchanged()

    async def test_enabled_healing_uses_normal_transaction_cooldown_and_limit(self):
        ground, enemy, _gun = self.fighter(healing=True, count=1)
        row = next(row for row in enemy.inv.rows() if row['root'] == items.HEAL)
        enemy.char.hp = 1
        enemy.char.sp = 1
        before = dict(row)
        self.assertTrue(bot.heal(ground))
        enemy.combat.healing.cancel()
        enemy.combat.healing = None
        enemy.combat.heal_now(row['uniq'], enemy.combat, ap_cost=0)
        self.assertEqual(ground.enemy_heals_left, 0)
        self.assertTrue(battle_medicine.remaining_ms(ground.store, enemy.char_id, combat.now()))
        after = ground.store.item(row['uniq'])
        self.assertTrue(after is None or after['use_count'] < before['use_count'])
        self.assertFalse(bot.heal(ground))
        self.unchanged()

    async def test_reloading_and_committed_animation_are_not_restarted(self):
        ground, enemy, _gun = self.fighter()
        with patch.object(enemy.inv, 'use_load', side_effect=AssertionError('duplicate reload')):
            enemy.combat.reloading = object()
            ground.enemy_turn()
            enemy.combat.reloading = None
        enemy.combat.recovery_until = combat.now() + 1
        with patch.object(mobs, 'find_path', side_effect=AssertionError('animation interrupted')):
            ground.enemy_turn()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingBot)
