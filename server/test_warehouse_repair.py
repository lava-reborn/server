"""Warehouse repair rate, current ownership, rollback and uncertain commit."""
import contextlib
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_mortimer_sales as fixtures
import holdings
import inventory
import items
import storage
from testkit import run_cases


class WarehouseRepair(unittest.TestCase):
    give = fixtures.MortimerSales.give

    def setUp(self):
        fixtures.MortimerSales.setUp(self)
        self.s.room.loc=self.s.loc
        self.inv.trade=inventory.TradeSession(1,123,36)
        self.store.set_money(self.cid,1000000,100000)
        self.s.char.afro,self.s.char.gold=1000000,100000

    def worn(self):
        row=self.give(25636)
        self.store.update_item(row['uniq'],brk=0)
        return self.store.item(row['uniq'])

    def repair(self,row,code=inventory.UPD_REPAIR):
        self.frames.clear()
        self.inv.repair(dict(obj=inventory.oid_of(row)),code)
        return [p['res'] for c,p in self.frames if c=='cmdAck']

    def warehouse(self):
        self.s.room.loc=NS(id=111)
        self.inv.trade=inventory.TradeSession(1,1011,111)
        clan=self.store.clan_create(self.cid,'RepairClan','repairclan','',None)
        self.store.holding_set('wh_sever',clan,'admin')

    def test_only_actual_site_flag_has_30_percent_discount(self):
        self.assertAlmostEqual(inventory.repair_rmod(111,1011),inventory.RMOD*.7)
        self.assertEqual(inventory.repair_rmod(1380,1011),inventory.RMOD)
        self.assertEqual(inventory.repair_rmod(111,123),inventory.RMOD)
        self.assertEqual(inventory.repair_rmod(None,1011),inventory.RMOD)

    def test_warehouse_charge_matches_advertised_rate_in_both_currencies(self):
        self.warehouse()
        for code,index in ((inventory.UPD_REPAIR,0),(inventory.UPD_REPAIR_GOLD,1)):
            row=self.worn()
            si=items.params_of(row['type_id'])
            price=inventory.repair_prices(si,row['brk'],row['max_break_cur'],inventory.RMOD*.7)[index]
            before=self.store.money(self.cid)
            self.assertEqual(self.repair(row,code),[0])
            after=self.store.money(self.cid)
            self.assertEqual(before[index]-after[index],price)
            self.assertEqual(self.repair(self.store.item(row['uniq']),code),[0])
            self.assertEqual(self.store.money(self.cid),after)

    def test_lost_ownership_after_open_refuses_without_any_changes(self):
        self.warehouse()
        row=self.worn()
        self.store.holding_clear('wh_sever','admin')
        before=self.store.money(self.cid)
        self.assertEqual(self.repair(row),[inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid),before)
        self.assertEqual(self.store.item(row['uniq']),row)

    def test_failed_item_write_rolls_back_purse_and_ledger_without_success_frames(self):
        row=self.worn()
        before=self.store.money(self.cid)
        with patch.object(self.store,'update_item',side_effect=RuntimeError('injected repair write')):
            self.assertEqual(self.repair(row),[inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid),before)
        self.assertEqual((self.s.char.afro,self.s.char.gold),before)
        self.assertEqual(self.store.item(row['uniq']),row)
        self.assertFalse(any(c.startswith('ss_') for c,p in self.frames))
        self.assertEqual(self.store.db.execute("SELECT * FROM money_ledger WHERE source='repair'").fetchall(),[])

    def test_uncertain_commit_reloads_committed_purse_and_closes_without_success_ack(self):
        row=self.worn()
        original=storage.atomic
        @contextlib.contextmanager
        def uncertain(db):
            with original(db):
                yield db
            raise storage.CommitError('confirmation lost after actual commit')
        with patch.object(storage,'atomic',uncertain):
            self.assertEqual(self.repair(row),[])
        self.assertTrue(self.s.closed)
        self.assertEqual((self.s.char.afro,self.s.char.gold),self.store.money(self.cid))
        self.assertGreater(self.store.item(row['uniq'])['brk'],0)


if __name__ == '__main__':
    run_cases(WarehouseRepair)
