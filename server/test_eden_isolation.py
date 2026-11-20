"""Addressed work-property escape regressions through actual item handlers."""
import json
import unittest
from types import SimpleNamespace as NS

from test_eden_harvest import EdenHarvestTests
from test_eden_quests import EdenQuestTests
from test_mail_gold_loot import MailGoldLootTests
import auction
import barter
import combat
import eden
import inventory
import items
import mail
import rooms
import server
import storage
import world
from testkit import run_cases


class EdenGroundIsolation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = EdenHarvestTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.dispose)
        self.store, self.s, self.f = self.fixture.store, self.fixture.s, self.fixture.f
        self.rc = self.f.rc
        self.addCleanup(self.stop_bags)

    def stop_bags(self):
        for bag in self.rc.loot.values():
            if bag.expiry:
                bag.expiry.cancel()

    def ground(self, type_id):
        fields = inventory.new_fields(type_id)
        root = fields.pop("root")
        row = self.store.create_item(combat.LOOT_OWNER, type_id, root, **fields)
        self.rc.add_to_bag(self.s.pos, [row])
        return row

    def results(self, frames=None):
        return [p["res"] for cmd, p in (self.fixture.frames if frames is None else frames)
                if cmd == "cmdAck"]

    async def test_no_local_type_can_be_dropped_or_create_a_shared_ground_bag(self):
        self.f.open_loot({"target": self.s.pos})
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.fixture.give(type_id)
            self.fixture.frames.clear()
            before = self.store.items_of(self.s.char_id), self.store.on_ground(combat.LOOT_OWNER)
            self.f.ss_upd({"s_status": 2, "obj": inventory.oid_of(row)})
            self.assertEqual(self.results(), [inventory.RES_REFUSED])
            self.assertEqual((self.store.items_of(self.s.char_id),
                              self.store.on_ground(combat.LOOT_OWNER)), before)
            self.assertFalse(self.rc.loot)

    async def test_legacy_local_ground_rows_cannot_be_picked_individually_or_together(self):
        rows = [self.ground(t) for t in sorted(eden.LOCAL_ITEMS)]
        other = self.fixture.other_worker(2)
        other.s.pos = self.s.pos
        other.f.open_loot({"target": self.s.pos})
        before = self.store.items_of(other.s.char_id), self.store.on_ground(combat.LOOT_OWNER)
        for row in rows:
            other.frames.clear()
            other.f.ss_upd({"s_status": 1, "obj": inventory.oid_of(row)})
            self.assertEqual(self.results(other.frames), [inventory.RES_REFUSED])
        for _ in range(2):  # Replaying a cached take-all cannot move the rows.
            other.frames.clear()
            other.f.ss_upd({"s_status": 3})
            self.assertEqual(self.results(other.frames), [inventory.RES_REFUSED])
        self.assertEqual((self.store.items_of(other.s.char_id),
                          self.store.on_ground(combat.LOOT_OWNER)), before)

    async def test_personal_ground_drop_pickup_and_deletion_keep_working(self):
        personal = self.fixture.give(6946)
        self.f.open_loot({"target": self.s.pos})
        self.fixture.frames.clear()
        self.f.ss_upd({"s_status": 2, "obj": inventory.oid_of(personal)})
        self.assertEqual(self.results(), [inventory.RES_OK])
        self.assertEqual(self.store.item(personal["uniq"])["char_id"], combat.LOOT_OWNER)
        other = self.fixture.other_worker(2)
        other.f.open_loot({"target": self.s.pos})
        other.frames.clear()
        other.f.ss_upd({"s_status": 1, "obj": inventory.oid_of(personal)})
        self.assertEqual(self.results(other.frames), [inventory.RES_OK])
        self.assertEqual(self.store.item(personal["uniq"])["char_id"], other.s.char_id)
        other.frames.clear()
        other.s.inv.use_delete({"obj": inventory.oid_of(personal)})
        self.assertEqual(self.results(other.frames), [inventory.RES_OK])
        self.assertIsNone(self.store.item(personal["uniq"]))

    async def test_release_does_not_make_legacy_ground_claimable_and_personal_loot_still_works(self):
        local = self.ground(eden.GOOD_TICKET)
        personal = self.ground(6946)
        other = self.fixture.other_worker(2)
        other.s.pos = self.s.pos
        other.f.open_loot({"target": self.s.pos})
        cached = other.f.session_items()
        self.assertEqual({r["uniq"] for r in cached}, {local["uniq"], personal["uniq"]})
        with storage.atomic(self.store.db):
            eden.complete_release(self.s, self.store, (41, 5970, 1730))
        self.assertIsNone(eden.assigned(self.store, self.s.char_id))
        # The cached bag is shared, but no local row can become somebody's.
        for params in ({"s_status": 1, "obj": inventory.oid_of(local)}, {"s_status": 3}):
            other.frames.clear()
            other.f.ss_upd(params)
            self.assertEqual(self.results(other.frames), [inventory.RES_REFUSED])
        other.frames.clear()
        other.f.ss_upd({"s_status": 1, "obj": inventory.oid_of(personal)})
        self.assertEqual(self.results(other.frames), [inventory.RES_OK])
        self.assertEqual(self.store.item(personal["uniq"])["char_id"], other.s.char_id)
        self.assertEqual(self.store.item(local["uniq"])["char_id"], combat.LOOT_OWNER)

    async def test_legacy_local_ground_remains_unclaimable_after_room_restoration(self):
        local = self.ground(eden.CLEAVER)
        restored = rooms.Rooms(world.mob_types())
        self.assertEqual(combat.restore_ground(restored, self.store), (0, 1))
        self.s.room = restored.get(self.s.loc.id)
        self.s.room.players[self.s] = None
        rc = self.f.rc
        self.addCleanup(lambda: [bag.expiry.cancel() for bag in rc.loot.values() if bag.expiry])
        self.f.open_loot({"target": self.s.pos})
        self.fixture.frames.clear()
        self.f.ss_upd({"s_status": 1, "obj": inventory.oid_of(local)})
        self.assertEqual(self.results(), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(local["uniq"])["char_id"], combat.LOOT_OWNER)

    async def test_local_items_never_fall_on_death_while_personal_items_keep_their_rule(self):
        local = [self.fixture.give(t) for t in sorted(eden.LOCAL_ITEMS)]
        personal = self.fixture.give(6946)
        losses = combat.death_losses(local + [personal], rng=NS(randint=lambda _lo, _hi: 1))
        self.assertEqual([(r["uniq"], n) for r, n in losses], [(personal["uniq"], 1)])
        self.assertTrue(all(not combat.drops_on_death(r["type_id"]) for r in local))

    async def test_all_local_items_are_refused_by_real_sale_barter_and_auction_handlers(self):
        self.s.say = lambda _text: None
        trader = barter.Barter(self.s, self.store, rooms.Directory())
        house = auction.Auction(self.s, self.store, rooms.Directory())
        house.at_auctioneer = lambda _p: True  # Contact I/O boundary only.
        self.s.inv.trade = inventory.TradeSession(1, 1164, self.s.loc.id)
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.fixture.give(type_id)
            before = self.store.items_of(self.s.char_id), self.store.money(self.s.char_id)
            self.fixture.frames.clear()
            self.s.inv.sell({"obj": inventory.oid_of(row), "param": 1})
            self.assertEqual(self.results(), [inventory.RES_REFUSED])
            self.fixture.frames.clear()
            trader.put(NS(open=True), NS(items={}), NS(), {"obj": inventory.oid_of(row)})
            self.assertNotEqual(self.results(), [inventory.RES_OK])
            result, _ = house._create({"obj": inventory.oid_of(row), "time": 24, "a_bid": 1000})
            self.assertNotEqual(result, inventory.RES_OK)
            self.assertEqual((self.store.items_of(self.s.char_id), self.store.money(self.s.char_id)), before)


class EdenQuestIsolation(unittest.TestCase):
    def setUp(self):
        self.fixture = EdenQuestTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.s, self.store = self.fixture.s, self.fixture.store

    def test_cancelling_and_retaking_basket_quest_never_mints_a_free_basket(self):
        self.fixture.give(eden.PALM_LEAF, 20)
        personal = self.fixture.give(6946, 3)
        for _ in range(3):
            self.assertEqual(self.fixture.take(18116), [0])
            qid = self.fixture.taken_id(18116)
            self.s.cmd_q_ca({"q_id": qid})
            self.assertEqual(self.s.inv.bag_pieces().get(eden.PALM_LEAF), 20)
            self.assertNotIn(eden.BASKET, self.s.inv.bag_pieces())
        self.assertEqual(self.fixture.take(18116), [0])
        qid = self.fixture.taken_id(18116)
        self.assertEqual(self.fixture.hand_in(qid), [0])
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.s.inv.bag_pieces().get(eden.BASKET), 1)
        self.assertNotIn(eden.PALM_LEAF, self.s.inv.bag_pieces())
        self.assertEqual(self.store.item(personal["uniq"]), personal)

    def test_release_and_rollback_cover_bag_body_bank_without_touching_personal_rows(self):
        local = []
        for index, type_id in enumerate(sorted(eden.LOCAL_ITEMS)):
            local.append(self.fixture.give(type_id, slot=(inventory.BAG, inventory.PRIMARY,
                                                        inventory.BANK)[index % 3]))
        personal = [self.fixture.give(6946, 3), self.fixture.give(3577, slot=inventory.BELT),
                    self.fixture.give(3159, 2, inventory.BANK)]
        before = self.s.inv.rows(), eden.assigned(self.store, self.s.char_id)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with storage.atomic(self.store.db):
                eden.complete_release(self.s, self.store, (41, 5970, 1730))
                raise RuntimeError("rollback")
        self.assertEqual((self.s.inv.rows(), eden.assigned(self.store, self.s.char_id)), before)
        with storage.atomic(self.store.db):
            eden.complete_release(self.s, self.store, (41, 5970, 1730))
        self.assertTrue(all(self.store.item(r["uniq"]) is None for r in local))
        self.assertEqual([self.store.item(r["uniq"]) for r in personal], personal)

    def test_stale_local_barter_locks_cannot_survive_cleanup_or_break_rollback(self):
        local = [self.fixture.give(t, slot=(inventory.BAG, inventory.PRIMARY,
                                           inventory.BANK)[index % 3])
                 for index, t in enumerate(sorted(eden.LOCAL_ITEMS))]
        personal = self.fixture.give(6946, 3)
        self.s.inv.locked.update(r["uniq"] for r in local + [personal])
        locked = self.s.inv.locked
        expected_locks = set(locked)
        before = self.s.inv.rows(), eden.assigned(self.store, self.s.char_id)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with storage.atomic(self.store.db):
                eden.complete_release(self.s, self.store, (41, 5970, 1730))
                raise RuntimeError("rollback")
        self.assertEqual((self.s.inv.rows(), eden.assigned(self.store, self.s.char_id)), before)
        self.assertIs(self.s.inv.locked, locked)
        self.assertEqual(self.s.inv.locked, expected_locks)
        with storage.atomic(self.store.db):
            eden.complete_release(self.s, self.store, (41, 5970, 1730))
        self.assertTrue(all(self.store.item(r["uniq"]) is None for r in local))
        self.assertEqual(self.store.item(personal["uniq"]), personal)
        self.assertIs(self.s.inv.locked, locked)
        self.assertEqual(self.s.inv.locked, expected_locks)


class EdenLegacyMailIsolation(unittest.TestCase):
    def setUp(self):
        self.fixture = MailGoldLootTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_legacy_local_parcels_are_quarantined_outside_eden_without_spending_or_duplication(self):
        t = self.fixture
        for type_id in sorted(eden.LOCAL_ITEMS):
            for kind in (mail.LETTER, mail.TRADE, mail.TRADE_EXPRESS):
                with self.subTest(type_id=type_id, kind=kind):
                    local = t.give(type_id)
                    ordinary = t.give(6946)
                    snaps = [mail.snapshot(ordinary), mail.snapshot(local)]
                    for row in (local, ordinary):
                        t.store.delete_item(row["uniq"])
                    letter = t.store.mail_send(t.cid, t.recipient, kind, "legacy local", "test",
                                               100, 0, json.dumps(snaps))
                    before = t.state()
                    for _ in range(2):
                        t.frames.clear()
                        t.box.uldml({"id": str(letter["id"])})
                        self.assertEqual(t.frames, [("cmdAck", {"res": mail.RES_PARCEL_REFUSED})])
                        self.assertEqual(t.state(), before)
                        self.assertIn("письмо сохранено", t.answers[-1])


if __name__ == "__main__":
    try:
        run_cases(EdenGroundIsolation, EdenQuestIsolation, EdenLegacyMailIsolation)
    finally:
        server.STORE.close()
