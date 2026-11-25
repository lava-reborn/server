"""Each committed single-use stack dose consumes one finite bot heal allowance."""
import unittest
from unittest.mock import patch

import combat
import inventory
import items
from training import arena, bot
from training import items as copies
from test_training_bot import TrainingBot
from testkit import run_cases


class BotMedicineStacks(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = TrainingBot.asyncSetUp
    asyncTearDown = TrainingBot.asyncTearDown
    enter = TrainingBot.enter
    unchanged = TrainingBot.unchanged
    fighter = TrainingBot.fighter

    async def test_both_fighters_count_stack_doses_and_stop_before_spending_the_rest(self):
        ground, enemy, _gun = self.fighter(healing=True, count=2)
        ground.room.ws = True
        for index, fighter_type in enumerate((arena.TrainingFighter, bot.LocalFighter)):
            with self.subTest(fighter=fighter_type.__name__):
                for row in enemy.inv.rows():
                    if row['root'] == items.HEAL:
                        ground.store.delete_item(row['uniq'])
                row = enemy.inv.create(copies.copy_type(6055), 10)
                enemy.combat = fighter_type(enemy)
                enemy.combat.ap = enemy.combat.ap_max
                ground.enemy_heals_left = 2
                for attempt in range(2):
                    enemy.char.hp = enemy.char.sp = 1
                    moment = 100 + index * 100 + attempt * 7
                    with patch.object(combat, 'now', return_value=moment):
                        enemy.combat.heal_now(row['uniq'], enemy.combat)
                    current = ground.store.item(row['uniq'])
                    self.assertEqual((current['count'], current['use_count']), (9 - attempt, 1))
                    self.assertEqual(ground.enemy_heals_left, 1 - attempt)
                    self.assertGreater(enemy.char.hp, 1)
                enemy.char.hp = enemy.char.sp = 1
                with patch.object(combat, 'now', return_value=moment + 7):
                    self.assertFalse(bot.heal(ground))
                self.assertEqual(ground.store.item(row['uniq'])['count'], 8)
        self.unchanged()

    async def test_failed_or_rejected_completion_does_not_spend_bot_allowance(self):
        ground, enemy, _gun = self.fighter(healing=True, count=2)
        ground.room.ws = True
        for fighter_type in (arena.TrainingFighter, bot.LocalFighter):
            with self.subTest(fighter=fighter_type.__name__):
                row = enemy.inv.create(copies.copy_type(6055), 3)
                enemy.combat = fighter_type(enemy)
                enemy.combat.ap = enemy.combat.ap_max
                ground.enemy_heals_left = 2
                enemy.char.hp = 1
                enemy.inv.locked.add(row['uniq'])
                enemy.combat.heal_now(row['uniq'], enemy.combat)
                enemy.inv.locked.remove(row['uniq'])
                self.assertEqual(ground.enemy_heals_left, 2)
                with patch.object(ground.store, 'update_item', side_effect=RuntimeError('injected')), \
                        patch.object(combat.log, 'exception') as failure:
                    enemy.combat.heal_now(row['uniq'], enemy.combat)
                failure.assert_called_once()
                self.assertEqual(ground.enemy_heals_left, 2)
                self.assertEqual(ground.store.item(row['uniq'])['count'], 3)
                self.assertEqual(enemy.char.hp, 1)
        self.unchanged()


if __name__ == '__main__':
    run_cases(BotMedicineStacks)
