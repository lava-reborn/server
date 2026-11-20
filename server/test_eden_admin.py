"""Real queued admin transitions on isolated Eden characters."""
import contextlib
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from test_eden_quests import EdenQuestTests
import eden
import inventory
import items
import quests
import rooms
import server
import storage
import world
from test_release_battle import BattleFixes
from testkit import run_cases


class EdenAdminTests(unittest.TestCase):
    def setUp(self):
        fixture = EdenQuestTests("test_three_real_exchanges_feed_the_full_quota_and_exit")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.store, self.s, self.cid = fixture, fixture.store, fixture.s, fixture.cid
        eden.release(self.store, self.cid)
        self.s.eden_sentence = None
        self.s.loc, self.s.pos = world.location(41), 100
        self.s.gx, self.s.gy, self.s.on_map = 5970, 1730, False
        self.store.save_position(self.cid, 41, 100, 5970, 1730, False)
        self.s.close = lambda **_kwargs: setattr(self.s, "closed", True)

    def action(self, kind="eden"):
        return dict(kind=kind, char_id=self.cid, account_id=self.s.active["account_id"],
                    admin="local-test", args_json=json.dumps({"reason": "Admin regression"}))

    def apply(self, kind="eden", online=True):
        with patch.object(server, "session_for", return_value=self.s if online else None):
            return server.apply_admin_action(self.action(kind))

    def test_online_assignment_preserves_worn_belt_and_grants_only_a_cleaver(self):
        own_belt = self.fixture.give(3577, slot=inventory.BELT)
        own_gun = self.fixture.give(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        result = self.apply()
        self.assertIn("№2", result)
        self.assertEqual(eden.assigned(self.store, self.cid)["visit"], 2)
        self.assertTrue(eden.inside(self.s.loc))
        self.assertEqual(self.store.character(self.cid)["loc"], eden.CENTER)
        worn = {row["slot"]: row for row in self.store.items_of(self.cid)
                if row["slot"] != inventory.BAG}
        self.assertEqual(worn[inventory.BELT], own_belt)
        self.assertEqual(worn[inventory.PRIMARY]["type_id"], eden.CLEAVER)
        self.assertEqual(self.store.item(own_belt['uniq']), own_belt)
        self.assertEqual(self.store.item(own_gun['uniq']), dict(own_gun, slot=inventory.BAG))
        self.assertFalse(any(row['type_id'] == eden.BASKET
                             for row in self.store.items_of(self.cid)))
        rows_before = self.store.items_of(self.cid)
        with self.assertRaisesRegex(ValueError, "already assigned"):
            self.apply()
        self.assertEqual(self.store.items_of(self.cid), rows_before)
        self.assertEqual(eden.assigned(self.store, self.cid)["visit"], 2)

    def test_offline_assignment_and_release_keep_the_persistent_visit_counter(self):
        own_belt = self.fixture.give(3577, slot=inventory.BELT)
        own_gun = self.fixture.give(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        self.assertIn("№2", self.apply(online=False))
        assigned = eden.assigned(self.store, self.cid)
        self.assertEqual((assigned["visit"], self.store.character(self.cid)["loc"]),
                         (2, eden.CENTER))
        types = {row["type_id"] for row in self.store.items_of(self.cid)}
        self.assertIn(eden.CLEAVER, types)
        self.assertNotIn(eden.BASKET, types)
        self.assertEqual(self.store.item(own_belt['uniq']), own_belt)
        self.assertEqual(self.store.item(own_gun['uniq']), dict(own_gun, slot=inventory.BAG))
        self.apply("eden_release", online=False)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertFalse(any(row["type_id"] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.cid)))
        self.assertEqual(self.store.item(own_belt['uniq']), own_belt)
        self.assertIn("№3", self.apply(online=False))
        self.assertEqual(eden.assigned(self.store, self.cid)["visit"], 3)

    def test_assignment_write_failure_rolls_back_location_tools_and_next_visit(self):
        own_belt = self.fixture.give(3577, slot=inventory.BELT)
        before = dict(self.store.character(self.cid))
        before_items = self.store.items_of(self.cid)
        with patch.object(self.store, "save_position", side_effect=RuntimeError("write failed")):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                self.apply()
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertEqual(dict(self.store.character(self.cid)), before)
        self.assertEqual(self.store.items_of(self.cid), before_items)
        self.assertEqual(self.store.item(own_belt["uniq"])["slot"], inventory.BELT)
        self.assertEqual(self.fixture.departures, [])
        self.assertFalse(any(cmd == 'eden_inv' for cmd, _params in self.fixture.frames))
        self.assertIn("№2", self.apply())

    def test_uncertain_assignment_commit_closes_the_online_session(self):
        atomic = storage.atomic

        @contextlib.contextmanager
        def lost_commit_reply(db):
            with atomic(db) as transaction:
                yield transaction
            if db._atomic_depth == 0:
                raise storage.CommitError("commit was made but its reply was lost")

        with patch.object(storage, "atomic", lost_commit_reply):
            with contextlib.suppress(storage.CommitError):
                self.apply()
        self.assertTrue(self.s.closed)
        self.assertIsNotNone(eden.assigned(self.store, self.cid))
        self.assertEqual(self.store.character(self.cid)["loc"], eden.CENTER)

    def test_uncertain_release_commit_closes_without_restoring_an_old_sentence(self):
        self.apply()
        atomic = storage.atomic

        @contextlib.contextmanager
        def lost_commit_reply(db):
            with atomic(db) as transaction:
                yield transaction
            if db._atomic_depth == 0:
                raise storage.CommitError("release committed; reply lost")

        with patch.object(storage, "atomic", lost_commit_reply):
            with contextlib.suppress(storage.CommitError):
                self.apply("eden_release")
        self.assertTrue(self.s.closed)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertFalse(eden.inside(self.store.character(self.cid)["loc"]))

    def test_postcommit_ground_refresh_failure_closes_the_old_body(self):
        import eden_ground
        self.apply()
        with patch.object(eden_ground, "refresh_rooms", side_effect=RuntimeError("refresh failed")):
            with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                self.apply("eden_release")
        self.assertTrue(self.s.closed)
        self.assertIsNone(self.s.eden_sentence)
        self.assertTrue(self.s._failed_location_entry)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertFalse(eden.inside(self.store.character(self.cid)["loc"]))
        self.assertFalse(any(row['type_id'] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.cid)))

    def test_postcommit_arrival_failure_closes_without_undoing_release(self):
        self.apply()
        with patch.object(self.s, "enter_location", side_effect=RuntimeError("arrival failed")):
            with self.assertRaisesRegex(RuntimeError, "arrival failed"):
                self.apply("eden_release")
        self.assertTrue(self.s.closed)
        self.assertIsNone(self.s.eden_sentence)
        self.assertTrue(self.s._failed_location_entry)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertFalse(eden.inside(self.store.character(self.cid)["loc"]))


class EdenAdminRealCloseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = BattleFixes()
        await self.case.asyncSetUp()
        self.store, self.s = self.case.store, self.case.players[0]
        self.manager, self.directory = rooms.Rooms(world.mob_types()), rooms.Directory()
        self.enterContext(patch.object(server, 'ROOMS', self.manager))
        self.enterContext(patch.object(server, 'ONLINE', self.directory))
        self.enterContext(patch.object(server, 'GMAP', NS(leave=Mock())))
        self.enterContext(patch.object(server, 'PARTIES', NS(
            disconnected=Mock(), online=Mock(), party_of=lambda _s: None)))
        self.enterContext(patch.object(server, 'CLANS', NS(
            offline=Mock(), online=Mock(), entered=Mock())))
        self.enterContext(patch.object(server, 'broadcast_online_count'))
        self.store.save_character_state(self.s.char_id, home_loc=41, home_gx=5970, home_gy=1730)
        self.directory.add(self.s)

    async def asyncTearDown(self):
        for room in self.manager.rooms.values():
            if room.combat and room.combat.timer:
                room.combat.timer.cancel()
        await self.case.asyncTearDown()

    def apply(self, kind, *, online=True):
        row = dict(kind=kind, char_id=self.s.char_id,
                   account_id=self.s.active['account_id'], admin='test',
                   args_json=json.dumps({'reason': 'Real close regression'}))
        with patch.object(server, 'session_for', return_value=self.s if online else None):
            return server.apply_admin_action(row)

    def read_equipment(self, sess):
        sess.writer.frames.clear()
        sess.cmd_ss_get(dict(slot=11, target=0))
        ack, = [p for command, p in sess.writer.frames if command == 'ss_ack']
        return ack['o_list']

    def assert_refresh_before_location(self):
        frames = self.s.writer.frames
        refresh = [i for i, (command, p) in enumerate(frames)
                   if command == 'eden_inv' and p.get('refresh') == 1]
        lcall = [i for i, (command, _p) in enumerate(frames) if command == 'lcall']
        self.assertEqual(len(refresh), 1)
        self.assertEqual(len(lcall), 1)
        self.assertLess(refresh[0], lcall[0])
        self.assertFalse(any(command in ('cmdAck', 'ss_ack') for command, _p in frames))

    async def test_live_reassignment_refreshes_new_primary_and_preserves_ordinary_items(self):
        own_gun = self.s.inv.create(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        own_ammo = self.s.inv.create(inventory.STARTER_AMMO, count=17)
        before_money = self.store.money(self.s.char_id)
        previous = None
        for visit in (1, 2):
            self.s.writer.frames.clear()
            self.apply('eden')
            self.assert_refresh_before_location()
            self.assertEqual(self.s.eden_sentence['visit'], visit)
            tool, = [r for r in self.store.items_of(self.s.char_id) if r['type_id'] == eden.CLEAVER]
            self.assertEqual(tool['slot'], inventory.PRIMARY)
            self.assertNotEqual(tool['uniq'], previous)
            self.s.cmd_lenter(dict(accept=1))
            displayed = self.read_equipment(self.s)
            self.assertEqual(displayed[len(inventory.WEAR_SLOTS)], inventory.oid_of(tool))
            self.assertIn(inventory.oid_of(own_gun), displayed[8:])
            self.assertIn(inventory.oid_of(own_ammo), displayed[8:])
            self.s.writer.frames.clear()
            self.apply('eden_release')
            self.assert_refresh_before_location()
            self.s.cmd_lenter(dict(accept=1))
            displayed = self.read_equipment(self.s)
            self.assertNotIn(inventory.oid_of(tool), displayed)
            self.assertIn(inventory.oid_of(own_gun), displayed[8:])
            self.assertEqual(self.store.item(own_gun['uniq']), dict(own_gun, slot=inventory.BAG))
            self.assertEqual(self.store.item(own_ammo['uniq']), own_ammo)
            self.assertEqual(self.store.money(self.s.char_id), before_money)
            previous = tool['uniq']

    async def test_committed_assignment_invalidates_old_merchant_buy_sell_and_repair(self):
        # A real Session previously kept this ordinary stock across lcall.
        # A forged purchase then bought Bartholomew's goods inside Eden.
        self.s.inv.trade = inventory.TradeSession(1, 81, 36)
        stock_index = items.stock_for(81, 36).index(6043)
        ordinary = self.s.inv.create(inventory.STARTER_PISTOL)
        self.store.update_item(ordinary['uniq'], brk=1)
        self.s.char.gold = 10000
        self.s.char.save(self.store)
        self.apply('eden')
        self.s.cmd_lenter(dict(accept=1))
        self.assertEqual(self.s.loc.id, eden.CENTER)
        self.assertIsNone(self.s.inv.trade)
        before = self.store.money(self.s.char_id), self.store.items_of(self.s.char_id)
        operations = (
            dict(s_status=inventory.UPD_BUY, obj=format(stock_index, 'x'), param=1),
            dict(s_status=inventory.UPD_BUY_GOLD, obj=format(stock_index, 'x'), param=1),
            dict(s_status=inventory.UPD_SELL, obj=inventory.oid_of(ordinary), param=1),
            *(dict(s_status=code, obj=inventory.oid_of(ordinary)) for code in
              (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE)),
        )
        for packet in operations:
            with self.subTest(code=packet['s_status']):
                self.s.writer.frames.clear()
                self.s.cmd_ss_upd(packet)
                self.assertIsNone(self.s.inv.trade)
                self.assertEqual((self.store.money(self.s.char_id),
                                  self.store.items_of(self.s.char_id)), before)
                # No shop owns this command now. Keep the existing bare
                # fallback acknowledgement, without item or money updates.
                self.assertEqual(self.s.writer.frames, [('cmdAck', {'res': 0})])

    async def test_assignment_rollback_preserves_the_previous_merchant_session(self):
        trade = self.s.inv.trade = inventory.TradeSession(1, 81, 36)
        before = (dict(self.store.character(self.s.char_id)),
                  self.store.items_of(self.s.char_id))
        self.s.writer.frames.clear()
        with patch.object(self.store, 'save_position', side_effect=RuntimeError('assignment rollback')):
            with self.assertRaisesRegex(RuntimeError, 'assignment rollback'):
                self.apply('eden')
        self.assertIs(self.s.inv.trade, trade)
        self.assertIsNone(eden.assigned(self.store, self.s.char_id))
        self.assertEqual((dict(self.store.character(self.s.char_id)),
                          self.store.items_of(self.s.char_id)), before)
        self.assertFalse(self.s.closed)
        self.assertEqual(self.s.writer.frames, [])

    async def test_offline_reassignment_is_loaded_by_a_fresh_native_equipment_request(self):
        own_gun = self.s.inv.create(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        own_ammo = self.s.inv.create(inventory.STARTER_AMMO, count=17)
        before_money = self.store.money(self.s.char_id)
        self.directory.remove(self.s)
        self.s.room.players.pop(self.s, None)
        self.s.room = None
        previous = None
        for visit in (1, 2):
            self.s.writer.frames.clear()
            self.apply('eden', online=False)
            fresh = server.Session(type(self.s.writer)(), 'fresh-Eden-regression')
            fresh.char_id = self.s.char_id
            fresh.active = dict(self.store.character(fresh.char_id))
            fresh.load_character(fresh.char_id)
            fresh.restore(self.store.character(fresh.char_id))
            self.addCleanup(fresh.combat.cancel_timers)
            displayed = self.read_equipment(fresh)
            tool, = [r for r in self.store.items_of(self.s.char_id) if r['type_id'] == eden.CLEAVER]
            self.assertEqual(displayed[len(inventory.WEAR_SLOTS)], inventory.oid_of(tool))
            self.assertEqual(fresh.eden_sentence['visit'], visit)
            self.assertNotEqual(tool['uniq'], previous)
            self.assertIn(inventory.oid_of(own_gun), displayed[8:])
            self.assertIn(inventory.oid_of(own_ammo), displayed[8:])
            self.assertEqual(self.s.writer.frames, [])
            self.apply('eden_release', online=False)
            self.assertIsNone(self.store.item(tool['uniq']))
            self.assertEqual(self.store.item(own_gun['uniq']), dict(own_gun, slot=inventory.BAG))
            self.assertEqual(self.store.item(own_ammo['uniq']), own_ammo)
            self.assertEqual(self.store.money(self.s.char_id), before_money)
            previous = tool['uniq']

    @contextlib.contextmanager
    def lost_commit_reply(self):
        atomic = storage.atomic

        @contextlib.contextmanager
        def lost(db):
            with atomic(db) as transaction:
                yield transaction
            if db._atomic_depth == 0:
                raise storage.CommitError('commit completed; reply lost')

        with patch.object(storage, 'atomic', lost):
            yield

    def confine(self):
        self.s.eden_sentence = eden.assign(self.store, self.s.char_id, 'test', 'Real close setup')
        eden.grant_tools(self.store, self.s.char_id)
        self.case.room.players.pop(self.s, None)
        self.s.room = self.manager.get(eden.CENTER)
        self.s.room.players[self.s] = True
        self.s.loc, self.s.pos = self.s.room.loc, self.s.room.loc.entry_cell()
        self.s.gx, self.s.gy = eden.target_cell(eden.CENTER)
        self.store.save_position(self.s.char_id, eden.CENTER, self.s.pos,
                                 self.s.gx, self.s.gy, False)

    async def test_uncertain_release_real_close_keeps_committed_home_and_purse(self):
        self.confine()
        ordinary = self.store.take_quest(self.s.char_id, 9, {}, False)
        self.store.take_quest(self.s.char_id, 18114, {}, False)
        self.store.take_quest(self.s.char_id, 18110, {}, False)
        before_money = self.store.money(self.s.char_id)
        with self.lost_commit_reply(), self.assertRaises(storage.CommitError):
            self.apply('eden_release')
        self.assertTrue(self.s.closed)
        self.assertIsNone(self.s.eden_sentence)
        row = self.store.character(self.s.char_id)
        self.assertEqual((row['loc'], row['gx'], row['gy'], row['on_map']), (41, 5970, 1730, 0))
        self.assertEqual(self.store.money(self.s.char_id), before_money)
        self.assertEqual([q['q_id'] for q in self.store.quests(self.s.char_id)], [ordinary])
        self.assertFalse(any(command == 'eden_inv' and p.get('clear_eden')
                             for command, p in self.s.writer.frames))
        self.assertFalse(any(row['type_id'] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.s.char_id)))

    async def test_uncertain_assignment_real_close_keeps_committed_eden_destination(self):
        before_money = self.store.money(self.s.char_id)
        with self.lost_commit_reply(), self.assertRaises(storage.CommitError):
            self.apply('eden')
        self.assertTrue(self.s.closed)
        self.assertEqual(self.s.eden_sentence, eden.assigned(self.store, self.s.char_id))
        self.assertEqual(self.store.character(self.s.char_id)['loc'], eden.CENTER)
        self.assertEqual(self.store.money(self.s.char_id), before_money)
        self.assertTrue(any(row['type_id'] == eden.CLEAVER
                            for row in self.store.items_of(self.s.char_id)))

    async def test_postcommit_refresh_failure_real_close_keeps_home(self):
        import eden_ground
        self.confine()
        with patch.object(eden_ground, 'refresh_rooms', side_effect=RuntimeError('refresh failed')):
            with self.assertRaisesRegex(RuntimeError, 'refresh failed'):
                self.apply('eden_release')
        self.assertTrue(self.s.closed)
        self.assertIsNone(eden.assigned(self.store, self.s.char_id))
        self.assertEqual(self.store.character(self.s.char_id)['loc'], 41)

    async def test_release_write_failure_real_close_keeps_rollback_items_and_sentence(self):
        self.confine()
        self.store.take_quest(self.s.char_id, 18114, {}, False)
        self.store.take_quest(self.s.char_id, 9, {}, False)
        before_quests = self.store.quests(self.s.char_id)
        before_items = self.store.items_of(self.s.char_id)
        before_money = self.store.money(self.s.char_id)
        with patch.object(self.store, 'save_position', side_effect=RuntimeError('release write failed')):
            with self.assertRaisesRegex(RuntimeError, 'release write failed'):
                self.apply('eden_release')
        self.assertTrue(self.s.closed)
        self.assertTrue(self.s._failed_location_entry)
        self.assertEqual(self.s.eden_sentence, eden.assigned(self.store, self.s.char_id))
        self.assertIsNotNone(self.s.eden_sentence)
        self.assertEqual(self.store.character(self.s.char_id)['loc'], eden.CENTER)
        self.assertEqual(self.store.items_of(self.s.char_id), before_items)
        self.assertEqual(self.store.money(self.s.char_id), before_money)
        self.assertEqual(self.store.quests(self.s.char_id), before_quests)
        self.assertFalse(any(command == 'eden_inv' and p.get('clear_eden')
                             for command, p in self.s.writer.frames))

    async def test_uncertain_paid_release_real_close_keeps_fee_home_and_cleanup(self):
        self.confine()
        self.s.char.gold = 10_000
        self.s.char.save(self.store)
        before_afro = self.store.money(self.s.char_id)[0]
        giver = quests.get(eden.GOLD_EXIT).give[0]
        npc = next((eid, row) for eid, row in self.s.room.npcs.items()
                   if row.type_id == giver)
        self.s.pos = npc[1].cell
        self.s.cmd_q_st(dict(mob=npc[0], q_idx=quests.given_by(giver).index(eden.GOLD_EXIT)))
        qid = next(row['q_id'] for row in self.store.quests(self.s.char_id)
                   if row['type'] == eden.GOLD_EXIT)
        with self.lost_commit_reply():
            self.s.cmd_q_co(dict(q_id=qid, mob=npc[0], obj_idx=0))
        self.assertTrue(self.s.closed)
        self.assertIsNone(self.s.eden_sentence)
        self.assertIsNone(eden.assigned(self.store, self.s.char_id))
        self.assertEqual(self.store.character(self.s.char_id)['loc'], 41)
        self.assertEqual(self.store.money(self.s.char_id), (before_afro, 5_000))
        self.assertIsNone(self.store.quest(qid))
        self.assertFalse(any(command == 'eden_inv' and p.get('clear_eden')
                             for command, p in self.s.writer.frames))
        self.assertFalse(any(row['type_id'] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.s.char_id)))


if __name__ == "__main__":
    try:
        run_cases(EdenAdminTests, EdenAdminRealCloseTests)
    finally:
        server.STORE.close()
