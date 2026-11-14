"""An accepted active-hand change reaches observers before the next attack."""
import unittest
from unittest.mock import patch

import test_release_battle as fixtures
import combat
import inventory
from testkit import run_cases


class RemoteWeaponSync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = fixtures.BattleFixes()
        await self.fixture.asyncSetUp()
        self.players, self.store = self.fixture.players, self.fixture.store

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def test_swaps_and_empty_primary_reach_both_observers(self):
        actor, first, second = self.players
        gun = actor.inv.create(25566, slot=inventory.PRIMARY)
        other = actor.inv.create(25636, slot=inventory.SECONDARY)
        for row in (other, gun, other):
            with self.fixture.at(100):
                for s in self.players:
                    s.writer.frames.clear()
                actor.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from':inventory.SECONDARY,'to':inventory.PRIMARY}))
            for viewer in (first,second):
                moves = [p for n,p in viewer.writer.frames if n=='ss_obj_move']
                self.assertEqual(len(moves),1)
                self.assertEqual(moves[0],dict(id=actor.pid,obj=inventory.oid_of(row),to=inventory.PRIMARY,**{'from':inventory.PRIMARY}))
            self.assertEqual([n for n,_ in actor.writer.frames].count('cmdAck'),1)
        for s in self.players:
            s.writer.frames.clear()
        with self.fixture.at(100):
            actor.handle('ss_move',dict(obj=inventory.oid_of(other),**{'from':inventory.PRIMARY,'to':inventory.BAG}))
        for viewer in (first,second):
            move=next(p for n,p in viewer.writer.frames if n=='ss_obj_move')
            self.assertEqual(move['obj'],'0')
            self.assertEqual(move['to'],inventory.PRIMARY)

    async def test_secondary_and_refused_moves_do_not_change_observers(self):
        actor, first, second = self.players
        row=actor.inv.create(25636)
        for s in self.players:
            s.writer.frames.clear()
        with self.fixture.at(100):
            actor.handle('ss_move',dict(obj=inventory.oid_of(row),**{'from':inventory.BAG,'to':inventory.SECONDARY}))
            actor.handle('ss_move',dict(obj=inventory.oid_of(row),**{'from':inventory.BAG,'to':inventory.PRIMARY}))
        for viewer in (first,second):
            self.assertFalse(any(n=='ss_obj_move' for n,_ in viewer.writer.frames))

    async def test_failed_recipient_does_not_break_hand_change(self):
        actor, broken, healthy=self.players
        row=actor.inv.create(25636)
        with self.fixture.at(100),patch.object(broken.writer,'write',side_effect=BrokenPipeError('closed observer')):
            actor.handle('ss_move',dict(obj=inventory.oid_of(row),**{'from':inventory.BAG,'to':inventory.PRIMARY}))
        self.assertTrue(any(n=='ss_obj_move' and p.get('obj')==inventory.oid_of(row) for n,p in healthy.writer.frames))
        self.assertEqual(self.store.item(row['uniq'])['slot'],inventory.PRIMARY)

    async def test_delayed_weapon_change_is_published_before_next_aim(self):
        actor, first, second = self.players
        row = actor.inv.create(25636)
        self.store.update_item(row['uniq'], ammo_count=16, ammo_type=6092)
        # A delayed packet arrives at server time 100.25. The next request
        # is evaluated after that change, with one ordered stream per viewer.
        with self.fixture.at(100.25):
            actor.handle('ss_move', dict(obj=inventory.oid_of(row),
                **{'from': inventory.BAG, 'to': inventory.PRIMARY}))
        with self.fixture.at(100.5):
            actor.handle('ss_use', dict(type=inventory.USE_FIRE,
                obj=inventory.oid_of(row), target='1%08x' % first.pid))
        for viewer in (first, second):
            frames = viewer.writer.frames
            changed = next(i for i,(n,p) in enumerate(frames)
                           if n == 'ss_obj_move' and p.get('obj') == inventory.oid_of(row))
            aiming = next(i for i,(n,p) in enumerate(frames) if n == 'faAim')
            self.assertLess(changed, aiming)

    async def test_recent_server_hit_blocks_delayed_and_exit_cell_requests(self):
        actor, other, _ = self.players
        with self.fixture.at(100):
            actor.combat.hit_exchanged()
        for arrival in (100.25, 110, 114.99):
            for params in ({}, {'to': 1}):
                actor.writer.frames.clear()
                with self.fixture.at(arrival):
                    actor.handle('chWorld', params)
                self.assertFalse(actor.on_map)
                self.assertIs(actor.room, self.fixture.room)
                ack = [p['res'] for n,p in actor.writer.frames if n == 'cmdAck']
                self.assertEqual(ack, [39])
        # Every new confirmed hit refreshes the server's timeout, including
        # while the client still displays older information.
        with self.fixture.at(114):
            actor.combat.hit_exchanged()
        with self.fixture.at(115.5):
            self.assertTrue(actor.combat.in_combat())
            self.assertAlmostEqual(actor.combat.exit_timer_left(), 13.5)

    async def test_stale_remote_position_does_not_teleport_or_avoid_registered_hit(self):
        attacker, target, _ = self.players
        gun = attacker.inv.create(25566, slot=inventory.PRIMARY)
        self.store.update_item(gun['uniq'], ammo_count=7, ammo_type=6094)
        actual = target.live_cell()
        hp = target.char.vitals()['hcur']
        # The packet claims a route from a remote cell. No client position
        # is trusted for either the walk or the following shot calculation.
        with self.fixture.at(100):
            target.handle('moveTo', dict(path=[399,398]))
            self.assertEqual(target.live_cell(), actual)
            attacker.handle('ss_use', dict(type=inventory.USE_FIRE,
                obj=inventory.oid_of(gun), target='1%08x' % target.pid))
            timer = attacker.combat.aim
            self.assertIsNotNone(timer)
            callback, args, when = timer._callback, timer._args, timer.when()
            timer.cancel()
        # Fix the random scatter, not damage or validation, to exercise a
        # definite hit and its actual HP/resource/exit-timer bookkeeping.
        with self.fixture.at(when), patch.object(combat, 'bullet_offset', return_value=0), \
                patch.object(combat.log, 'exception', side_effect=AssertionError('shot resolver failed')):
            callback(*args)
            self.assertLess(target.char.vitals()['hcur'], hp)
            self.assertTrue(target.combat.in_combat())
            self.assertEqual(target.live_cell(), actual)
            self.assertEqual(self.store.item(gun['uniq'])['ammo_count'], 6)


if __name__ == "__main__":
    run_cases(RemoteWeaponSync)
