"""Authoritative gram limits: actual purchases/loot, gear refresh and quest guard."""
import os
import logging
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
import accounts
import combat
import inventory
import items
import progression
logging.disable(logging.CRITICAL)
import server
from testkit import run_cases


class Fighter(combat.Fighter):
    rc = None


class CarryWeight(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        self.addCleanup(self.store.close)
        account, _ = self.store.register("weight", "test-only")
        cid, _ = self.store.create_character(account, "Weight", 0, "1")
        self.ch = progression.Character.load(self.store, cid)
        self.ch.afro = 100000
        self.frames = []
        self.s = NS(char_id=cid, pid=1, room=None, pos=0, character=lambda: self.ch,
                    send=lambda cmd, **p: self.frames.append((cmd, p)),
                    send_player_info=lambda: None, push_vitals=lambda: None,
                    push_stats=lambda **kw: self.frames.append(("rp_info", self.ch.rp_info())),
                    answer=lambda _: None)
        self.inv = self.s.inv = inventory.Inventory(self.s, self.store)
        self.inv.push_look = lambda *_: None
        self.f = self.s.combat = Fighter(self.s)
        self.inv.trade = NS(trader_type=1200, loc_id=102)

    def make(self, type_id, count=1, slot=inventory.BAG, owner=None):
        fields = inventory.new_fields(type_id, count)
        root = fields.pop("root")
        fields["slot"] = slot
        return self.store.create_item(self.s.char_id if owner is None else owner,
                                      type_id, root, **fields)

    def fill_to(self, grams):
        rest = grams - self.inv.total_weight()
        # Real 75 g medicine plus 4 g ammunition represents any large gram count.
        meds = next(n for n in range(4) if (rest-75*n) % 4 == 0)
        for _ in range(meds):
            self.make(6043)
        rounds = (rest-75*meds)//4
        while rounds:
            n = min(5000, rounds)
            self.make(6106, n)
            rounds -= n
        self.assertEqual(self.inv.total_weight(), grams)

    def buy(self):
        self.frames.clear()
        with patch.object(items, "stock_for", return_value=[6106]):
            self.inv.buy(dict(obj="0", param="1"), inventory.UPD_BUY)
        return [p["res"] for cmd,p in self.frames if cmd == "cmdAck"]

    def test_purchase_matches_advertised_40_54_and_premium_grams(self):
        for strength, premium, expired in ((5,0,False),(12,0,False),
                                           (12,1,False),(12,2,False),(12,1,True)):
            with self.subTest(strength=strength,premium=premium,expired=expired):
                for row in self.inv.rows():
                    self.store.delete_item(row["uniq"])
                self.ch.attrib[progression.STRENGTH] = strength
                self.ch.premium = premium
                self.ch.premium_until = time.time() + (-60 if expired else 3600)
                limit = self.ch.rp_info()["max_weight"]
                self.assertEqual(self.inv.carry_limit(),limit)
                self.fill_to(limit-3)  # one 4 g round exceeds by exactly 1 g
                snapshot = self.inv.rows(), self.inv.money()
                self.assertEqual(self.buy(),[inventory.RES_OVERLOAD])
                self.assertEqual((self.inv.rows(),self.inv.money()),snapshot)
                # Move one gram from the boundary using actual 75/4 g items.
                for row in self.inv.rows():
                    self.store.delete_item(row["uniq"])
                self.fill_to(limit-4)
                self.assertEqual(self.buy(),[inventory.RES_OK])
                self.assertEqual(self.inv.total_weight(),limit)
                self.assertEqual(self.buy(),[inventory.RES_OVERLOAD])

    def test_pouch_and_strength_stack_refresh_and_removal_preserves_items(self):
        self.ch.attrib[progression.STRENGTH] = 12
        pouch = self.make(3602,slot=inventory.BELT)  # real +1 strength pouch, 700 g
        self.inv.refresh_gear()
        self.assertEqual(self.inv.carry_limit(),56000)
        self.assertEqual(self.frames[-1][1]["max_weight"],56000)
        self.fill_to(56000-4)
        self.assertEqual(self.buy(),[0])
        self.store.update_item(pouch["uniq"],slot=inventory.BAG)
        before = self.inv.rows()
        self.inv.refresh_gear()
        self.assertEqual(self.inv.carry_limit(),54000)
        self.assertEqual(self.frames[-1][1]["max_weight"],54000)
        self.assertEqual(self.inv.rows(),before)
        self.assertEqual(self.inv.total_weight(),56000)
        self.assertEqual(self.buy(),[inventory.RES_OVERLOAD])
        # Re-equipping restores the same limit; an unworn bank pouch adds neither weight nor strength.
        self.store.update_item(pouch["uniq"],slot=inventory.BANK)
        self.inv.refresh_gear()
        self.assertEqual((self.inv.carry_limit(),self.inv.total_weight()),(54000,55300))
        self.store.update_item(pouch["uniq"],slot=inventory.BELT)
        self.inv.refresh_gear()
        self.assertEqual((self.inv.carry_limit(),self.inv.total_weight()),(56000,56000))

    def loot(self, rows, code):
        bag = combat.LootBag(0,[r["uniq"] for r in rows])
        self.f.loot = 0
        self.f.rc = NS(loot={0:bag}, close_bag=lambda _: None)
        self.frames.clear()
        self.assertTrue(self.f.ss_upd(dict(s_status=str(code),obj=inventory.oid_of(rows[0]))))
        return [p["res"] for cmd,p in self.frames if cmd == "cmdAck"], bag

    def test_single_and_all_loot_above_old_50kg_limit_and_exact_boundary(self):
        self.ch.attrib[progression.STRENGTH] = 12
        for code in (1,3):
            with self.subTest(code=code):
                for row in self.inv.rows():
                    self.store.delete_item(row["uniq"])
                self.fill_to(54000-3)
                row = self.make(6106,owner=combat.LOOT_OWNER)
                result,bag = self.loot([row],code)
                self.assertEqual(result,[inventory.RES_OVERLOAD])
                self.assertEqual(bag.uniqs,[row["uniq"]])
                self.assertEqual(self.store.item(row["uniq"])["char_id"],combat.LOOT_OWNER)
                for carried in self.inv.rows():
                    self.store.delete_item(carried["uniq"])
                self.fill_to(54000-4)
                result,bag = self.loot([row],code)
                self.assertEqual(result,[0])
                self.assertEqual(bag.uniqs,[])
                self.assertEqual(self.inv.total_weight(),54000)

    def test_take_all_is_atomic_for_combined_weight(self):
        self.fill_to(40000-4)
        rows = [self.make(6106,owner=combat.LOOT_OWNER) for _ in range(2)]
        result,bag = self.loot(rows,3)
        self.assertEqual(result,[inventory.RES_OVERLOAD])
        self.assertEqual(len(bag.uniqs),2)
        self.assertEqual(self.inv.total_weight(),39996)
        self.assertTrue(all(self.store.item(r["uniq"])["char_id"] == combat.LOOT_OWNER for r in rows))

    def test_quest_guard_uses_same_limit_and_subtracts_hand_in(self):
        self.ch.attrib[progression.STRENGTH] = 12
        self.fill_to(54000)
        self.assertTrue(server.Session.over_weight(self.s,[(6106,1)]))
        self.assertFalse(server.Session.over_weight(self.s,[(6106,1)],[(6106,1)]))
        self.assertFalse(server.Session.over_weight(self.s,[]))
        self.assertTrue(server.QUEST_ITEMS_PAST_WEIGHT)  # deliberate quest exception retained


if __name__ == "__main__":
    try:
        run_cases(CarryWeight)
    finally:
        server.STORE.close()
