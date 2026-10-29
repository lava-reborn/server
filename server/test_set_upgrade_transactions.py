"""Set exchange through the real window: atomic payment, replacement and replay.

An explicit recipe fixture isolates transaction safety from city/price policy.
No sockets, running game or production database are used.
"""
import logging
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"

import accounts
import inventory
import progression
import server
import setcraft
import upgrader
from test_quest_state import session
from testkit import run_cases


class SetUpgradeTransactions(unittest.TestCase):
    NPC, BEFORE, AFTER, COST = 93, 11249, 10739, 100
    LOCATION, GOLD = 104, 10000

    def setUp(self):
        self.store = accounts.Store(":memory:")
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, "STORE", previous)
        self.addCleanup(self.store.close)
        account, _ = self.store.register("set-upgrade", "local-password")
        self.cid, _ = self.store.create_character(account, "set-upgrade", 0, "1")
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.char.afro, self.s.char.gold = 10000, self.GOLD
        self.s.char.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.transport = None
        self.s.closed = False
        self.s.loc = NS(id=self.LOCATION, spawns=[])
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames = []
        self.s.send = lambda command, **params: self.frames.append((command, params))
        self.room = NS(loc=self.s.loc, npcs={1: NS(type_id=self.NPC)})
        self.s.room = self.room
        self.s.npc_session = upgrader.SESSION_UPGRADE
        self.window = upgrader.Window(self.s)
        self.window.open_, self.window.npc_type, self.window.room = True, self.NPC, self.room
        if self.NPC == 93:
            recipe = patch.dict(setcraft._WINDOWS, {self.NPC: [(self.BEFORE, self.AFTER, self.COST)]})
            recipe.start()
            self.addCleanup(recipe.stop)
        fields = inventory.new_fields(self.BEFORE)
        root = fields.pop("root")
        fields["slot"] = inventory.BAG
        self.old = self.store.create_item(self.cid, self.BEFORE, root, **fields)
        self.params = dict(s_status=1, obj=inventory.oid_of(self.old), param=self.AFTER)

    def acks(self):
        return [p["res"] for n, p in self.frames if n == "cmdAck"]

    def assert_unchanged(self):
        self.assertEqual(self.store.items_of(self.cid), [self.old])
        self.assertEqual(self.store.money(self.cid), (10000, self.GOLD))
        self.assertEqual(self.s.inv.money(), (10000, self.GOLD))

    def test_payment_and_replacement_commit_once_and_replay_is_refused(self):
        self.window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_OK])
        self.assertIsNone(self.store.item(self.old["uniq"]))
        self.assertEqual(self.s.inv.bag_pieces(), {self.AFTER: 1})
        self.assertEqual(self.store.money(self.cid), (10000, self.GOLD - self.COST))
        self.frames.clear()
        self.window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assertEqual(self.s.inv.bag_pieces(), {self.AFTER: 1})
        self.assertEqual(self.store.money(self.cid), (10000, self.GOLD - self.COST))

    def test_failed_creation_restores_item_and_both_purses_without_success_frames(self):
        with patch.object(self.s.inv, "create", side_effect=RuntimeError("creation failed")):
            with self.assertLogs("lava", level=logging.ERROR):
                self.window.ss_upd(self.params)
        self.assert_unchanged()
        self.assertEqual(self.acks(), [1])
        self.assertFalse(any(n.startswith("ss_") for n, _ in self.frames))

    def test_failed_deletion_restores_payment(self):
        with patch.object(self.store, "delete_item", side_effect=RuntimeError("delete failed")):
            with self.assertLogs("lava", level=logging.ERROR):
                self.window.ss_upd(self.params)
        self.assert_unchanged()
        self.assertEqual(self.acks(), [1])

    def test_rechecks_item_inside_transaction(self):
        calls = 0
        find = self.s.inv.find

        def vanish(oid):
            nonlocal calls
            calls += 1
            return find(oid) if calls == 1 else None

        with patch.object(self.s.inv, "find", side_effect=vanish):
            self.window.ss_upd(self.params)
        self.assert_unchanged()
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])

    def test_wrong_output_and_absent_master_do_not_charge(self):
        self.window.ss_upd(dict(self.params, param=self.BEFORE))
        self.assertEqual(self.acks(), [inventory.RES_REFUSED])
        self.assert_unchanged()
        self.window.left()
        self.frames.clear()
        self.window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_REFUSED])
        self.assert_unchanged()

    def test_insufficient_gold_does_not_consume_item(self):
        self.s.char.gold = self.COST - 1
        self.s.char.save(self.store)
        self.window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NO_MONEY])
        self.assertEqual(self.store.items_of(self.cid), [self.old])
        self.assertEqual(self.store.money(self.cid), (10000, self.COST - 1))

    def test_banked_locked_and_equipped_items_cannot_be_exchanged(self):
        self.s.inv.locked.add(self.old["uniq"])
        self.window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assert_unchanged()
        self.s.inv.locked.clear()
        for slot in (inventory.BANK, inventory.HEAD):
            self.store.update_item(self.old["uniq"], slot=slot)
            self.frames.clear()
            self.window.ss_upd(self.params)
            self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
            self.assertEqual(self.store.money(self.cid), (10000, self.GOLD))
            self.assertIsNotNone(self.store.item(self.old["uniq"]))


class OasisSetUpgradeTransactions(SetUpgradeTransactions):
    """Real enabled oasis recipe, no injected catalogue or prices."""
    NPC, BEFORE, AFTER, COST = 7548, 10769, 11309, 2188
    LOCATION = 76


class DongolaOasisSetUpgradeTransactions(OasisSetUpgradeTransactions):
    """Dongola's existing Joseph uses the same transactional service."""
    LOCATION = 195


class HalfaOasisSetUpgradeTransactions(OasisSetUpgradeTransactions):
    LOCATION = 62


class AbuOasisSetUpgradeTransactions(OasisSetUpgradeTransactions):
    LOCATION = 196


if __name__ == "__main__":
    try:
        run_cases(SetUpgradeTransactions, OasisSetUpgradeTransactions,
                  DongolaOasisSetUpgradeTransactions,
                  HalfaOasisSetUpgradeTransactions, AbuOasisSetUpgradeTransactions)
    finally:
        server.STORE.close()
