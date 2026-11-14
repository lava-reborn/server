"""Addressed academy-knife loss checks, without a statistical death run."""
import unittest
from types import SimpleNamespace as NS

import combat
import inventory
import items
from testkit import run_cases


class AcademyKnifeDeath(unittest.TestCase):
    def row(self, t, slot, serial=1):
        return dict(inventory.new_fields(t, 50), type_id=t, uniq=serial, slot=slot, count=50)

    def test_academy_knives_never_enter_loss_plan_in_any_container(self):
        self.assertFalse(combat.drops_on_death(4203))
        self.assertFalse(items.params_of(4203).get('quest'))
        for slot in (inventory.BAG, inventory.PRIMARY, inventory.SECONDARY, inventory.BANK):
            row=self.row(4203,slot)
            for _ in range(2):
                self.assertEqual(combat.death_losses([row],set(),NS(random=lambda:0)),[])
                self.assertEqual(row['count'],50)

    def test_other_loot_still_falls_and_bank_remains_safe(self):
        sand=self.row(2258,inventory.BAG,2)
        bank=self.row(2258,inventory.BANK,3)
        plan=combat.death_losses([self.row(4203,inventory.BAG),sand,bank],set(),NS(random=lambda:0))
        self.assertEqual([(row['uniq'],n) for row,n in plan],[(2,17)])


if __name__ == '__main__':
    run_cases(AcademyKnifeDeath)
