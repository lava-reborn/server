"""Felled palms and owned ground through real commands, without timer sleeps."""
import contextlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from test_eden_harvest import EdenHarvestTests
from test_quest_state import session
import accounts
import combat
import eden
import eden_ground
import eden_harvest as harvest
import inventory
import pace
import progression
import rooms
import storage
import world
from testkit import run_cases


class EdenHarvestGroundTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.case = EdenHarvestTests()
        self.case.setUp()
        self.addCleanup(self.case.dispose)
        self.store, self.s, self.f, self.rc, self.palm = (
            self.case.store, self.case.s, self.case.f, self.case.rc, self.case.palm)

    def harvest(self):
        for _ in range(3):
            self.case.click()
            self.case.finish()
        bag = self.rc.loot[self.palm.cell]
        rows = [self.store.item(uniq) for uniq in bag.uniqs]
        return bag, rows

    def ack(self, frames=None):
        return [p['res'] for c, p in (self.case.frames if frames is None else frames) if c == 'cmdAck']

    async def test_death_has_one_ground_item_and_the_camp_creature_respawn_clock(self):
        bag, rows = self.harvest()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['char_id'], rows[0]['count']), (combat.LOOT_OWNER, 1))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_BANANA, 0), 0)
        self.assertFalse(self.palm.alive)
        self.assertNotIn(self.palm.eid, self.s.room.npcs)
        delay = pace.paced(combat.CORPSE_DELAY) + combat.RESPAWN_DELAY
        self.assertEqual(self.palm._eden_due - self.case.clock, delay)
        self.assertGreater(delay, 180)
        original = self.palm._eden_respawn_token
        self.palm._eden_respawn_timer.cancel()
        with patch.object(self.rc, 'respawn', wraps=self.rc.respawn) as respawn:
            self.case.clock += delay - .001
            harvest._respawn(self.rc, self.palm, original)
            respawn.assert_not_called()
            self.palm._eden_respawn_timer.cancel()
            self.case.clock += .001
            harvest._respawn(self.rc, self.palm, original)
            respawn.assert_called_once_with(self.palm)
        self.assertTrue(self.palm.alive)
        self.assertEqual(self.palm.hp, 5000)
        self.assertIn(self.palm.eid, self.s.room.npcs)
        self.assertEqual(len(bag.uniqs), 1)
        self.assertEqual(self.store.db.execute('SELECT * FROM eden_palm_state').fetchall(), [])

    async def test_uses_shared_creature_override_and_scales_only_the_corpse_phase(self):
        with patch.object(combat, 'RESPAWN_DELAY', 420), \
                patch.object(combat, 'OBJECT_RESPAWN_DELAY', 1), \
                patch.object(pace, 'SCALE', .5):
            self.harvest()
            self.assertEqual(self.palm.stats.role, 'object')
            self.assertEqual(self.palm._eden_due - self.case.clock,
                             420 + combat.CORPSE_DELAY * .5)

    async def test_only_finisher_sees_and_picks_its_resource_and_cannot_drop_it_again(self):
        other = self.case.other_worker(2)
        bag, rows = self.harvest()
        row, = rows
        other.f.open_loot(dict(target=bag.cell))
        self.assertEqual(other.f.session_items(), [])
        other.frames.clear()
        other.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        self.assertEqual(self.ack(other.frames), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(row['uniq'])['char_id'], 0)
        self.case.pickup()
        self.assertEqual(self.store.item(row['uniq'])['char_id'], self.s.char_id)
        self.assertIsNone(self.store.db.execute('SELECT * FROM eden_ground WHERE uniq=?',
                                                (row['uniq'],)).fetchone())
        self.f.open_loot(dict(target=self.s.pos))
        self.case.frames.clear()
        self.f.ss_upd(dict(s_status=2, obj=inventory.oid_of(row)))
        self.assertEqual(self.ack(), [inventory.RES_REFUSED])
        self.assertFalse(self.rc.loot)

    async def test_pickup_failure_rolls_back_row_binding_ground_then_retry_pays_once(self):
        bag, rows = self.harvest()
        row, = rows
        self.f.open_loot(dict(target=bag.cell))
        original = self.store.pick_up
        def fail(*args):
            original(*args)
            raise RuntimeError('injected pickup rollback')
        self.case.frames.clear()
        with patch.object(self.store, 'pick_up', side_effect=fail):
            self.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        self.assertEqual(self.ack(), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(row['uniq'])['char_id'], 0)
        self.assertTrue(eden_ground.claimable(self.f, self.store.item(row['uniq']), bag.cell))
        self.case.pickup()
        self.case.frames.clear()
        self.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        self.assertNotIn(0, self.ack())
        self.assertEqual(self.s.inv.bag_pieces()[row['type_id']], 1)

    async def test_uncertain_final_commit_restores_one_ground_marker_and_never_replays(self):
        self.case.prime_final_hit()
        self.case.click()
        pending = self.case.pending
        atomic = storage.atomic
        @contextlib.contextmanager
        def lost_reply(db):
            with atomic(db):
                yield db
            raise storage.CommitError('commit succeeded; reply lost')
        with patch.object(storage, 'atomic', lost_reply), patch.object(self.s, 'close') as close:
            self.case.finish()
        close.assert_called_once_with(force=True)
        self.case.finish(pending)
        self.assertFalse(self.palm.alive)
        self.assertEqual(len(self.store.on_ground(0)), 1)
        self.assertEqual(len(self.rc.loot[self.palm.cell].uniqs), 1)
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_BANANA, 0), 0)

    async def test_uncertain_pickup_commit_keeps_one_authoritative_owner(self):
        bag, rows = self.harvest()
        row, = rows
        self.f.open_loot(dict(target=bag.cell))
        atomic = storage.atomic
        @contextlib.contextmanager
        def lost_reply(db):
            with atomic(db):
                yield db
            raise storage.CommitError('pickup committed; reply lost')
        self.case.frames.clear()
        with patch.object(storage, 'atomic', lost_reply), patch.object(self.s, 'close') as close:
            self.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        close.assert_called_once_with(force=True)
        self.assertEqual(self.ack(), [])
        self.assertEqual(self.store.item(row['uniq'])['char_id'], self.s.char_id)
        self.assertEqual(self.store.on_ground(0), [])
        eden_ground.refresh_bag(self.rc, bag)
        self.assertFalse(self.rc.loot)
        self.case.frames.clear()
        self.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        self.assertNotIn(0, self.ack())
        self.assertEqual(self.s.inv.bag_pieces()[row['type_id']], 1)

    async def test_release_withdrawal_rolls_back_then_removes_only_its_owned_ground(self):
        other = self.case.other_worker(2)
        bag, rows = self.harvest()
        row, = rows
        personal = self.case.give(6946)
        self.store.update_item(personal['uniq'], char_id=0)
        self.rc.add_to_bag(bag.cell, [personal])
        with self.assertRaises(RuntimeError):
            with storage.atomic(self.store.db):
                self.assertEqual(eden_ground.withdraw_owned_ground(self.store, self.s.char_id), [row['uniq']])
                raise RuntimeError('release rollback')
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertTrue(eden_ground.claimable(self.f, self.store.item(row['uniq']), bag.cell))
        with storage.atomic(self.store.db):
            eden.release(self.store, self.s.char_id)
            eden_ground.withdraw_owned_ground(self.store, self.s.char_id)
        eden_ground.refresh_rooms(NS(rooms={self.s.loc.id: self.s.room}))
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertIsNotNone(self.store.item(personal['uniq']))
        self.assertEqual(bag.uniqs, [personal['uniq']])
        other.f.open_loot(dict(target=bag.cell))
        other.frames.clear()
        other.f.ss_upd(dict(s_status=1, obj=inventory.oid_of(row)))
        self.assertNotIn(0, self.ack(other.frames))
        self.assertEqual(self.store.item(personal['uniq'])['char_id'], 0)

    async def test_previous_visit_or_normal_world_cannot_claim_a_stale_resource(self):
        bag, rows = self.harvest()
        row, = rows
        eden.release(self.store, self.s.char_id)
        self.s.eden_sentence = eden.assign(self.store, self.s.char_id, 'test', 'second visit')
        self.assertEqual(self.s.eden_sentence['visit'], 2)
        self.assertFalse(eden_ground.claimable(self.f, row, bag.cell))
        self.s.loc = world.location(41)
        self.assertFalse(eden_ground.claimable(self.f, row, bag.cell))
        self.assertEqual(self.store.item(row['uniq'])['char_id'], 0)

    async def test_real_release_cleanup_withdraws_ground_and_cached_take_all_cannot_restore_it(self):
        bag, rows = self.harvest()
        row, = rows
        personal = self.case.give(6946)
        self.store.update_item(personal['uniq'], char_id=0)
        self.rc.add_to_bag(bag.cell, [personal])
        self.f.open_loot(dict(target=bag.cell))
        self.assertEqual({r['uniq'] for r in self.f.session_items()}, {row['uniq'], personal['uniq']})
        with storage.atomic(self.store.db):
            eden.complete_release(self.s, self.store, (41, 5970, 1730))
        eden_ground.refresh_rooms(NS(rooms={self.s.loc.id: self.s.room}))
        self.assertIsNone(self.store.item(row['uniq']))
        self.case.frames.clear()
        self.f.ss_upd(dict(s_status=3))
        self.assertEqual(self.ack(), [0])
        # The native take-all moves the old displayed list. Its correction
        # immediately removes the reclaimed resource from that client list.
        self.assertTrue(any(c == 'ss_obj_status' and p['status'] == 0
                            for c, p in self.case.frames))
        self.assertEqual(self.store.item(personal['uniq'])['char_id'], self.s.char_id)
        self.assertFalse(any(r['type_id'] in eden.LOCAL_ITEMS for r in self.s.inv.rows()))

    async def test_expiry_and_postgres_schema_do_not_leave_binding_or_change_ordinary_ground(self):
        bag, rows = self.harvest()
        row, = rows
        self.case.clock = bag.until[row['uniq']]
        self.rc.expire_bag(bag.cell)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.db.execute('SELECT * FROM eden_ground').fetchall(), [])
        ddl = storage.pg_schema(accounts.SCHEMA)
        binding = next(sql for sql in ddl if sql.startswith('CREATE TABLE IF NOT EXISTS eden_ground '))
        state = next(sql for sql in ddl if sql.startswith('CREATE TABLE IF NOT EXISTS eden_palm_state '))
        self.assertIn('owner_char BIGINT NOT NULL', binding)
        self.assertIn('PRIMARY KEY (loc, home_cell, mob_type)', state)

    async def test_expired_owner_window_refuses_take_all_until_ordinary_expiry_callback(self):
        bag, rows = self.harvest()
        row, = rows
        self.f.open_loot(dict(target=bag.cell))
        self.assertEqual([r['uniq'] for r in self.f.session_items()], [row['uniq']])
        self.case.clock = bag.until[row['uniq']]
        # The timer has not run yet. No success ack may move the old UI list.
        self.case.frames.clear()
        self.f.ss_upd(dict(s_status=3))
        self.assertEqual(self.ack(), [inventory.RES_REFUSED])
        self.assertEqual(self.store.item(row['uniq'])['char_id'], 0)
        self.rc.expire_bag(bag.cell)
        self.assertIsNone(self.store.item(row['uniq']))

    async def test_file_reopen_restores_ground_binding_and_remaining_respawn_clock(self):
        bag, rows = self.harvest()
        row, = rows
        with tempfile.TemporaryDirectory(prefix='eden-ground-restart-') as folder:
            path = str(Path(folder) / 'test.sqlite')
            target = sqlite3.connect(path)
            self.store.db.raw.backup(target)
            target.close()
            reopened = accounts.Store(path)
            manager = rooms.Rooms(world.mob_types())
            try:
                self.case.clock += 12
                self.assertEqual(combat.restore_ground(manager, reopened), (0, 1))
                rc = manager.get(self.s.loc.id).combat
                palm = next(m for m in rc.mobs.values() if m.home == self.palm.home
                            and m.type_id == self.palm.type_id)
                self.assertFalse(palm.alive)
                self.assertAlmostEqual(palm._eden_due - self.case.clock,
                                       pace.paced(combat.CORPSE_DELAY) + combat.RESPAWN_DELAY - 12)
                restored = rc.loot[bag.cell]
                self.assertEqual(restored.uniqs, [row['uniq']])
                s = session(reopened, char_id=self.s.char_id)
                s.char = progression.Character.load(reopened, self.s.char_id)
                s.loc, s.room, s.pos, s.on_map = self.s.loc, rc.room, self.s.pos, False
                s.live_cell = lambda: s.pos
                s.combat = f = combat.Fighter(s)
                self.assertTrue(eden_ground.claimable(f, reopened.item(row['uniq']), bag.cell))
            finally:
                for room in manager.rooms.values():
                    if room.combat:
                        for palm in room.combat.mobs.values():
                            timer = getattr(palm, '_eden_respawn_timer', None)
                            if timer:
                                timer.cancel()
                        for bag in room.combat.loot.values():
                            if bag.expiry:
                                bag.expiry.cancel()
                reopened.close()


if __name__ == '__main__':
    run_cases(EdenHarvestGroundTests)
