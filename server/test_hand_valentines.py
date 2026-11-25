"""Hand gifts: actual inventory moves, temporary stats and unchanged saved progress."""
import unittest

import inventory
import items
import names
import progression
from test_release_battle import BattleFixes
from testkit import run_cases


class HandValentines(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = BattleFixes()
        await self.case.asyncSetUp()
        self.addAsyncCleanup(self.case.asyncTearDown)
        self.s = self.case.players[0]

    async def test_each_valentine_bonuses_either_hand_and_never_the_bag_or_belt(self):
        original = self.s.char.attrib[:]
        for type_id, (attribute, amount) in items.HAND_VALENTINES.items():
            row = self.s.inv.create(type_id)
            self.assertEqual(row['root'], items.COLD_ARM)
            self.assertFalse(inventory.fits(row, inventory.BELT))
            self.s.inv.refresh_gear(push=False)
            self.assertEqual(self.s.char.bonus_attribs, [0] * 5)
            for slot in inventory.HAND_SLOTS:
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': inventory.BAG, 'to': slot}))
                self.assertEqual(self.case.store.item(row['uniq'])['slot'], slot)
                self.assertEqual(self.s.char.attr(attribute), original[attribute] + amount)
                self.assertEqual(self.s.char.attrib, original)
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': slot, 'to': inventory.BAG}))
                self.assertEqual(self.s.char.bonus_attribs, [0] * 5)
            description = names.ALL[items.params_of(type_id)['desc']]
            self.assertIn('в любой руке', description)
            self.assertIn('+' + str(amount), description)
            reloaded = progression.Character.load(self.case.store, self.s.char_id)
            reloaded.set_gear(inventory.gear_bonus(self.s.inv.rows(), reloaded))
            self.assertEqual(reloaded.attrib, original)
            self.assertEqual(reloaded.bonus_attribs, [0] * 5)


if __name__ == '__main__':
    run_cases(HandValentines)
