"""Actual oasis/prison counters, retail grades and purchases past index 64."""
import re
import unittest
from types import SimpleNamespace as NS

import inventory
import items
import npcs
import rooms
import shop_bands
import world
from test_gold_commerce import GoldCommerce
from testkit import run_cases


class AmmunitionShops(unittest.TestCase):
    def test_every_city_and_archived_ammunition_seller_keeps_all_released_grades(self):
        # Derive the expected grades independently of the production index.
        grades = {}
        for tid, (root, name) in items.catalogue().items():
            match = re.fullmatch(r'Ammo_(.+)_(?:KS|ST|OT|OT_PS|BB_G|EK_G|SHK_G)', name)
            if root != items.AMMO or not (match or tid == 6189):
                continue
            if tid not in items.wiki() and tid not in items.loot_manual():
                continue
            si = items.params_of(tid)
            if (si.get('quest') or not (si.get('cost') or si.get('g_cost'))
                    or items.out_of_game(tid) or items.acquisition_blocked(tid)):
                continue
            calibre = '9mmNato' if tid == 6189 else match[1]
            grades.setdefault('SP_5_6' if calibre == 'SP_5' else calibre, set()).add(tid)
        counters = {(None, t) for t in set(items.stock_table()) | set(npcs.STOCK)}
        for loc in shop_bands.CITY_OF:
            room = rooms.Room(world.location(loc), rooms.IdAllocator(), world.mob_types())
            counters.update((loc, n.type_id) for n in room.npcs.values() if n.root == world.TRADER)
        checked = 0
        for loc, trader in counters:
            stock = items.stock_for(trader, loc)
            ammunition = {t for t in stock if items.root_of(t) == items.AMMO}
            if not ammunition:
                continue
            checked += 1
            with self.subTest(location=loc, trader=trader):
                self.assertEqual(len(stock), len(set(stock)))
                self.assertLess(len(stock), 256)
                for t in ammunition:
                    calibre = shop_bands.ammunition_order(t)[0]
                    expected = set(grades.get(calibre, ()))
                    if trader in (2180, 2181, 880):
                        expected = {t for t in expected if not items.catalogue()[t][1].endswith('_KS')}
                    if trader in (714, 5240):
                        expected = {t for t in expected if items.params_of(t).get('g_cost')
                                    or items.catalogue()[t][1].endswith('_OT')}
                    self.assertTrue(expected <= ammunition, expected - ammunition)
        self.assertGreater(checked, 40)
        for placeholder in (7113, 35022, 35234, 41236, 42260):
            self.assertFalse(any(placeholder in group for group in grades.values()))

    def test_oases_have_disjoint_nonempty_weapon_and_ammunition_counters(self):
        for loc, gun_seller, ammo_seller in ((76, 1225, 1228), (195, 1229, 1230), (196, None, 1232)):
            room = rooms.Room(world.location(loc), rooms.IdAllocator(), world.mob_types())
            present = {n.type_id for n in room.npcs.values()}
            self.assertIn(ammo_seller, present)
            ammo = items.stock_for(ammo_seller, loc)
            self.assertTrue(ammo)
            self.assertTrue(all(items.root_of(t) == items.AMMO for t in ammo))
            if gun_seller is None:
                continue
            self.assertIn(gun_seller, present)
            guns = items.stock_for(gun_seller, loc)
            self.assertTrue(guns)
            self.assertTrue(all(items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM) for t in guns))
            self.assertFalse(set(guns) & set(ammo))
            for gun in guns:
                if items.root_of(gun) == items.FIRE_ARM:
                    self.assertTrue(set(items.params_of(gun)['comp_array']) & set(ammo), gun)

    def test_prison_suppliers_keep_medicine_and_every_gold_grade_without_makeshift(self):
        for loc, trader in ((176, 2180), (159, 2181), (177, 880)):
            stock = items.stock_for(trader, loc)
            self.assertTrue(any(items.root_of(t) == items.HEAL for t in stock))
            for tid in (6140, 6152, 6164, 6189):
                self.assertIn(tid, stock)
            self.assertFalse(any(items.root_of(t) == items.AMMO
                                 and items.catalogue()[t][1].endswith('_KS') for t in stock))


class AmmunitionPurchases(unittest.TestCase):
    setUp = GoldCommerce.setUp

    def test_native_indices_and_prices_at_all_oasis_and_prison_ammunition_counters(self):
        self.inv.carry_limit = lambda: 1_000_000
        for loc, trader in ((76, 1228), (195, 1230), (196, 1232), (176, 2180), (159, 2181), (177, 880)):
            self.s.loc = self.s.room.loc = NS(id=loc)
            self.s.room.npc = lambda n, t=trader: (0, t, world.TRADER) if n == 1 else None
            self.inv.trade = inventory.TradeSession(1, trader, loc)
            stock = items.stock_for(trader, loc)
            for index, tid in enumerate(stock):
                if items.root_of(tid) != items.AMMO:
                    continue
                with self.subTest(location=loc, item=tid, index=index):
                    self.store.set_money(self.cid, 1_000_000_000, 100000)
                    before = self.store.money(self.cid)
                    si = items.params_of(tid)
                    gold = bool(si['g_cost'])
                    self.frames.clear()
                    self.inv.buy(dict(obj=format(index, 'x'), param=7),
                                 inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
                    self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
                    after = self.store.money(self.cid)
                    self.assertEqual(before[int(gold)] - after[int(gold)],
                                     inventory.buy_price(si, items.AMMO, 7, gold))
                    self.assertEqual(before[int(not gold)], after[int(not gold)])
                    self.assertEqual([(r['type_id'], r['count']) for r in self.inv.rows()], [(tid, 7)])
                    for row in self.inv.rows():
                        self.store.delete_item(row['uniq'])


if __name__ == '__main__':
    run_cases(AmmunitionShops, AmmunitionPurchases)
