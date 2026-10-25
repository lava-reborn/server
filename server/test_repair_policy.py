"""Decreasing A/G repair premiums and actual client AVM1 calculations."""
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import inventory
import items
import repair_policy
from testkit import run_cases

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import widescreen
from avm_test import execute


class RepairPolicy(unittest.TestCase):
    def test_real_pairs_all_wear_and_ceiling_cases(self):
        checked = 0
        for gold, afro in repair_policy.counterparts().items():
            g = items.static_info(gold)[1]
            if 'repair_cost' not in g:
                continue
            a = items.static_info(afro)[1]
            self.assertEqual(g.get('repair_mod', 1), a.get('repair_mod', 1))
            factor = repair_policy.multiplier(inventory.item_level(gold))
            self.assertEqual(g['repair_cost'], a['cost'] * factor)
            expected = dict(a, repair_cost=a['cost'] * factor)
            for ceiling in (1000, 900):
                for wear in (0, 1, 450, 899):
                    if wear >= ceiling:
                        continue
                    gp = inventory.repair_window(g, wear, ceiling)
                    ap = inventory.repair_window(expected, wear, ceiling)
                    self.assertEqual(gp[0][:2], ap[0][:2], (gold, afro, wear))
                    self.assertEqual(gp[1], ap[1], (gold, afro, wear))
            checked += 1
        self.assertGreater(checked, 1000)

    def test_shop_restore_and_afro_unchanged(self):
        for afro in set(repair_policy.counterparts().values()):
            self.assertNotIn('repair_cost', items.static_info(afro)[1])
        rem = items.static_info(26062)[1]
        self.assertEqual((rem['cost'], rem['g_cost']), (0, 1037))
        self.assertEqual(inventory.repair_window(rem, 750, 1500)[0][2], 1037)

    def test_level_boundary(self):
        pair = next((g, a) for g, a in repair_policy.counterparts().items()
                    if g == 26062)
        p = dict(items.static_info(pair[0])[1], need_skills=[0])
        self.assertIsNone(repair_policy.valuation(pair[0], p))
        for level, factor in ((1, 5), (9, 5), (10, 4.75), (11, 4.5), (12, 4.25),
                              (13, 3.75), (14, 3.5), (15, 2.75), (16, 2),
                              (17, 1.8), (18, 1.6), (19, 1.4), (20, 1.2), (21, 1.2)):
            p['need_skills'] = [level]
            self.assertEqual(repair_policy.valuation(pair[0], p), 32500 * factor)

    def test_pouches_use_their_separate_rate(self):
        for gold in items.GOLD_POUCHES.values():
            p = items.static_info(gold)[1]
            self.assertEqual(p['repair_cost'], p['g_cost'] * 100)

    def test_shop_and_alternate_modification_names_are_covered(self):
        import shop_bands

        for t in shop_bands.wares():
            p = items.params_of(t) or {}
            if (items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM, items.WEAR)
                    and p.get('g_cost') and p.get('max_break_abs')
                    and inventory.item_level(t) > 0):
                self.assertIn('repair_cost', p, t)
        for g, a in ((37893, repair_policy.counterparts()[37893]), (6257, 6255)):
            self.assertEqual(items.params_of(g)['repair_cost'],
                             items.params_of(a)['cost'] *
                             repair_policy.multiplier(inventory.item_level(g)))

    def test_client_initialize_and_prices(self):
        obj = dict(cost=0, g_cost=1037, repair_cost=138125)
        target = {'__repairInitializeOrig': lambda p: target.update(p)}
        execute(widescreen.fn_repair_initialize().assemble(), dict(this=target, obj=obj))
        self.assertEqual(target['repair_cost'], 138125)
        target['__repairGetPropOrig'] = lambda key: target.get(key)
        for mode, expected in (('repair', 138125), ('trade', 0), (None, 0)):
            env = dict(this=target, prop='cost',
                       lol=dict(gpui=dict(StaffInterface=dict(ssType=mode)),
                                core=dict(GConstatns=dict(gold_repair_mod=50000))))
            self.assertEqual(execute(widescreen.fn_repair_cost().assemble(), env), expected)
        del obj['repair_cost']
        execute(widescreen.fn_repair_initialize().assemble(), dict(this=target, obj=obj))
        self.assertIsNone(target['repair_cost'])

    def test_actual_charge_matches_repair_window(self):
        import accounts
        import progression

        store = accounts.Store(':memory:')
        self.addCleanup(store.close)
        account, _ = store.register('repair-unit', 'unit-password')
        cid, _ = store.create_character(account, 'РемонтТест', 0, 1)
        store.set_money(cid, 1000000, 10000)
        char = progression.Character.load(store, cid)
        frames = []
        sess = NS(char_id=cid, character=lambda: char,
                  send=lambda *cmd, **p: frames.append((cmd[0], p)),
                  send_player_info=lambda: None)
        inv = inventory.Inventory(sess, store)
        inv.trade = inventory.TradeSession(1, 1200)
        for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD):
            row = inv.create(26062)
            store.update_item(row['uniq'], brk=750, max_break_cur=1500)
            row = store.item(row['uniq'])
            before = (char.afro, char.gold)
            frames.clear()
            inv.repair(dict(obj=inventory.oid_of(row)), code)
            self.assertEqual([p['res'] for n, p in frames if n == 'cmdAck'], [0])
            self.assertEqual((before[0] - char.afro, before[1] - char.gold),
                             (20718, 0) if code == inventory.UPD_REPAIR else (0, 41))
            updated = store.item(row['uniq'])
            self.assertEqual((updated['brk'], updated['max_break_cur']), (1350, 1350))


if __name__ == '__main__':
    run_cases(RepairPolicy)
