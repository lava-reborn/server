"""G restoration charges, rollback/replay protection and actual client bytecode."""
import contextlib
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_mortimer_sales as fixtures
import inventory
import items
import gold_trade
import restore_policy
import storage
from testkit import run_cases

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import widescreen
from avm_test import Function
from restore_price_client import patches


class RestorePrice(unittest.TestCase):
    give = fixtures.MortimerSales.give

    def setUp(self):
        fixtures.MortimerSales.setUp(self)
        self.s.room.loc = self.s.loc
        self.inv.trade = inventory.TradeSession(1, 123, 36)
        self.store.set_money(self.cid, 12345, 10000)
        self.s.char.gold = 10000

    def worn(self, type_id=26075):
        row = self.give(type_id)
        factory = items.params_of(type_id)['max_break_abs']
        self.store.update_item(row['uniq'], brk=0, max_break_cur=factory // 2)
        return self.store.item(row['uniq'])

    def restore(self, row):
        self.frames.clear()
        self.inv.repair(dict(obj=inventory.oid_of(row)), inventory.UPD_RESTORE)
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def test_proportional_prices_and_rounding(self):
        params = dict(g_cost=1000, max_break_abs=200)
        for ceiling, expected in ((200, 0), (150, 250), (100, 500), (50, 750), (0, 1000)):
            self.assertEqual(restore_policy.price(params, ceiling), expected)
        self.assertEqual(restore_policy.price(dict(g_cost=1037, max_break_abs=1500), 750), 519)
        self.assertEqual(restore_policy.price(dict(g_cost=1, max_break_abs=1500), 1499), 1)
        for ceiling in (-1, 201):
            self.assertIsNone(restore_policy.price(params, ceiling))

    def test_gun_and_armour_restore_once_without_changing_ammo_or_modification(self):
        vest = next(t for t, (_, name) in items.catalogue().items()
                    if name == 'armor_Set_M_LVL_8_G_mod00')
        for type_id in (26075, 25804, 26062, vest):
            with self.subTest(type_id=type_id):
                row = self.worn(type_id)
                ammo = 3 if row['root'] == items.FIRE_ARM else 0
                self.store.update_item(row['uniq'], ammo_count=ammo)
                row = self.store.item(row['uniq'])
                params = items.params_of(type_id)
                expected = math.floor(params['g_cost'] * .5 + .5)
                before = self.store.money(self.cid)
                self.assertEqual(self.restore(row), [0])
                after = self.store.item(row['uniq'])
                self.assertEqual((after['brk'], after['max_break_cur']),
                                 (params['max_break_abs'],) * 2)
                self.assertEqual((after['type_id'], after['ammo_count']), (type_id, ammo))
                self.assertEqual(self.store.money(self.cid), (before[0], before[1] - expected))
                self.assertEqual(self.restore(row), [0])
                self.assertEqual(self.store.money(self.cid), (before[0], before[1] - expected))

    def test_full_ceiling_does_not_give_free_repair(self):
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=1)
        row = self.store.item(row['uniq'])
        self.assertEqual(self.restore(row), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(row['uniq'])['brk'], 1)
        self.assertEqual(self.store.money(self.cid), (12345, 10000))

    def test_afro_item_cannot_restore_even_with_alternate_gold_price(self):
        row = self.worn(26061)
        params = dict(items.params_of(26061), g_cost=1037)
        with patch.object(items, 'params_of', return_value=params):
            self.assertEqual(self.restore(row), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(row['uniq'])['brk'], 0)
        self.assertEqual(self.store.money(self.cid), (12345, 10000))
        self.assertEqual(gold_trade.client_fields(26061)['g_restore_base'], 0)

    def test_insufficient_persisted_balance_does_not_change_item(self):
        row = self.worn()
        self.store.set_money(self.cid, 12345, 518)
        self.s.char.gold = 999999
        self.assertEqual(self.restore(row), [inventory.RES_NO_MONEY])
        self.assertEqual(self.store.item(row['uniq'])['brk'], 0)
        self.assertEqual(self.store.money(self.cid), (12345, 518))
        self.assertEqual(self.s.char.gold, 518)

    def test_success_uses_persisted_balance_and_records_one_charge(self):
        import server
        self.frames.clear()
        server.Session.cmd_ss_get_si(self.s, dict(type=26075))
        self.assertEqual(self.frames[-1][1]['g_restore_base'], 1037)
        row = self.worn()
        self.s.char.gold = 0
        self.assertEqual(self.restore(row), [0])
        self.assertEqual(self.s.char.gold, 9481)
        self.assertEqual(self.store.money(self.cid), (12345, 9481))
        paid = self.store.db.execute(
            "SELECT gold FROM money_ledger WHERE char_id=? AND source='repair'", (self.cid,)).fetchall()
        self.assertEqual([r['gold'] for r in paid], [-519])

    def test_item_write_failure_rolls_back_money_and_ledger(self):
        row = self.worn()
        with patch.object(self.store, 'update_item', side_effect=RuntimeError('injected')):
            self.assertEqual(self.restore(row), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), (12345, 10000))
        self.assertEqual(self.s.char.gold, 10000)
        self.assertEqual(self.store.item(row['uniq'])['max_break_cur'], row['max_break_cur'])
        paid = self.store.db.execute(
            "SELECT gold FROM money_ledger WHERE char_id=? AND source='repair'", (self.cid,)).fetchall()
        self.assertEqual(paid, [])

    def test_bank_item_cannot_be_restored_by_forged_request(self):
        row = self.worn()
        self.store.update_item(row['uniq'], slot=inventory.BANK)
        self.assertEqual(self.restore(row), [inventory.RES_NOT_FOUND])
        self.assertEqual(self.store.money(self.cid), (12345, 10000))

    def test_uncertain_commit_reloads_balance_before_exit(self):
        row = self.worn()
        original = storage.atomic

        @contextlib.contextmanager
        def lost_reply(db):
            with original(db):
                yield db
            raise storage.CommitError('committed but reply lost')

        with patch.object(storage, 'atomic', lost_reply):
            self.assertEqual(self.restore(row), [])
        self.assertTrue(self.s.closed)
        self.assertEqual(self.store.money(self.cid), (12345, 9481))
        self.assertEqual(self.s.char.gold, 9481)
        self.assertEqual(self.store.item(row['uniq'])['brk'], 1500)


class RestoreClient(unittest.TestCase):
    def setUp(self):
        self.env = dict(_global={}, String=str,
                        Math=dict(max=max, round=lambda x: math.floor(x + .5)),
                        lol=dict(core=dict(GConstatns=dict(gold_restore_price_mod=1))))
        spec = patches(widescreen.Asm, widescreen.UNDEF)
        for name, params, body in spec['globals']:
            self.env['_global'][name] = Function(params, body.assemble(), self.env)
        self.methods = {method: Function(params, body.assemble(), self.env)
                        for _, method, _, params, body in spec['wraps']}

    def panel(self, base, factory, ceiling):
        props = dict(g_restore_base=base, max_break_abs=factory, max_break_cur=ceiling)
        return dict(repair_slot=dict(item_mc=dict(item=dict(getProp=lambda key: props.get(key)))),
                    restoreGold_btn=dict(enabled=False), restoreGoldCost_txt=dict(text='old'),
                    __restoreCountOrig=lambda: None, __restoreDoubleClickOrig=lambda: None,
                    __restoreDropOrig=lambda: None)

    def test_emitted_client_price_matches_server_for_each_slot_path(self):
        from gold_commerce_client import patches as commerce_patches
        params, body = next((p, b) for _, name, _, p, b in
                            commerce_patches(widescreen.Asm, widescreen.UNDEF)['wraps']
                            if name == 'initialize')
        target = dict(__gcInitializeOrig=lambda obj: None)
        Function(params, body.assemble(), self.env).invoke(target, [dict(g_restore_base=1037)])
        self.assertEqual(target['g_restore_base'], 1037)
        for method, function in self.methods.items():
            for base, factory in ((1037, 1500), (300, 1250), (1, 3000)):
                for ceiling in (0, 1, factory // 4, factory // 2, factory - 1, factory):
                    with self.subTest(method=method, base=base, ceiling=ceiling):
                        panel = self.panel(base, factory, ceiling)
                        function.invoke(panel, [])
                        expected = restore_policy.price(dict(g_cost=base, max_break_abs=factory), ceiling)
                        self.assertEqual(panel['restoreGold_btn']['enabled'], ceiling < factory)
                        if ceiling < factory:
                            self.assertEqual(float(panel['restoreGoldCost_txt']['text']), expected / 100)

    def test_afro_empty_and_invalid_slot_do_not_enable_restore(self):
        for base, factory, ceiling in ((0, 1500, 750), (1037, 0, 0), (1037, 1500, -1), (1037, 1500, 1501)):
            panel = self.panel(base, factory, ceiling)
            self.methods['repairCostCount'].invoke(panel, [])
            self.assertFalse(panel['restoreGold_btn']['enabled'])
        panel['repair_slot']['item_mc']['item'] = None
        self.methods['repairCostCount'].invoke(panel, [])
        self.assertFalse(panel['restoreGold_btn']['enabled'])


if __name__ == '__main__':
    run_cases(RestorePrice, RestoreClient)
