"""Trade permissions never make G gear/supplies droppable; ingots stay loot."""
import unittest

import combat
import craft
import inventory
import items
import setcraft
import shop_bands
from testkit import run_cases


class AlwaysDrop:
    def random(self):
        return 0.0

    def randint(self, low, high):
        return low


class GoldDeath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop_gold = {t for t, (_, level, _, tier) in shop_bands.wares().items()
                         if tier == 1 and level <= items.PLAYER_GEAR_MAX_LEVEL}
        cls.weapons = set(cls.shop_gold)
        for row in craft.rows().values():
            if row.get('family') == 'upgrade' and row['gun'] in cls.shop_gold:
                cls.weapons.add(row['mod'])
        cls.armour = set()
        for rung in setcraft.LADDER:
            if rung['variant'] == 'G' and rung['level'] <= items.PLAYER_GEAR_MAX_LEVEL:
                for base in rung['members'].values():
                    cls.armour.update(setcraft.CHAINS.get(base, (base,)))
        cls.supplies = set(items.GOLD_POUCHES.values())
        for t, (root, name) in items.catalogue().items():
            if root == items.AMMO and not items.out_of_game(t):
                p = items.params_of(t) or {}
                if p.get('g_cost', 0) > 0 and not p.get('cost', 0):
                    cls.supplies.add(t)
            elif name.startswith(('bpg_', 'bpb_')) and '_gold_' in name:
                cls.supplies.add(t)
        cls.gold = cls.weapons | cls.armour | cls.supplies

    def test_g_shop_gear_and_weapon_modifications_never_drop(self):
        self.assertGreater(len(self.weapons), 100)
        for t in self.weapons:
            with self.subTest(type=t):
                self.assertTrue(combat.gold_item(t))
                self.assertFalse(combat.drops_on_death(t))

    def test_every_g_set_piece_and_reworked_copy_never_drop(self):
        self.assertGreater(len(self.armour), 400)
        for t in self.armour:
            with self.subTest(type=t):
                self.assertTrue(combat.gold_item(t))
                self.assertFalse(combat.drops_on_death(t))

    def test_g_ammo_pouches_and_blueprints_never_drop(self):
        self.assertGreater(len(self.supplies), 50)
        for t in self.supplies:
            with self.subTest(type=t):
                self.assertTrue(combat.gold_item(t))
                self.assertFalse(combat.drops_on_death(t))

    def test_actual_death_loss_plan_keeps_damaged_g_gear_and_large_stacks(self):
        rows = []
        for t in self.gold:
            for slot in (inventory.BAG, inventory.ARMOR if items.root_of(t) == items.WEAR
                         else inventory.PRIMARY):
                rows.append(dict(uniq=len(rows)+1, type_id=t, root=items.root_of(t),
                                 slot=slot, count=99, brk=0, max_break_cur=1))
        self.assertEqual(combat.death_losses(rows, rng=AlwaysDrop()), [])

    def test_ingots_keep_the_existing_death_drop_exception(self):
        rows = []
        for t in items.GOLD_INGOTS:
            self.assertFalse(combat.gold_item(t))
            self.assertTrue(combat.drops_on_death(t))
            rows.append(dict(uniq=t, type_id=t, root=items.root_of(t),
                             slot=inventory.BAG, count=3))
        self.assertEqual([(row['type_id'], n) for row, n in
                          combat.death_losses(rows, rng=AlwaysDrop())],
                         [(t, 1) for t in items.GOLD_INGOTS])

    def test_g_trade_and_ingots_do_not_disable_normal_afro_losses(self):
        row = dict(uniq=1, type_id=26061, root=items.FIRE_ARM, slot=inventory.BAG, count=1)
        self.assertFalse(combat.gold_item(26061))
        self.assertEqual(combat.death_losses([row], rng=AlwaysDrop()), [(row, 1)])


if __name__ == '__main__':
    run_cases(GoldDeath)
