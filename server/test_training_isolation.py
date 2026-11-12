"""Real command-boundary checks against the complete main-store snapshot."""
import asyncio
import copy
import unittest
from unittest.mock import patch

import barter
import combat
import inventory
from protocol import decode
from training import character, items as copies, runtime, session as training
import test_training_ground as fixtures


class Isolation(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    party_members = fixtures.TrainingGround.party_members

    def main_state(self):
        # A linked training checkpoint is the only expected persistent change.
        return dict(database=sorted(line for line in self.store.db.raw.iterdump()
                                    if not line.startswith('INSERT INTO "char_training_profiles"')),
                    stats=copy.deepcopy(self.s.char.rows()), hp=self.s.char.hp, sp=self.s.char.sp,
                    money=self.s.inv.money(), ap=self.s.combat.ap,
                    location=(self.s.loc.id, self.s.pos, self.s.gx, self.s.gy, self.s.on_map))

    async def test_declared_effect_capability_consumes_buffs_changes_stats_and_expires(self):
        g = self.enter()
        g.clone.cmd_lenter({})
        before = self.main_state()
        # SimulatorIsolation inherits this contract with its own selected rules.
        # Never switch profiles behind the fixture's isolation assertions.
        g.configure_player(character.preset(20))
        fighter = g.clone.combat
        manager = g.clone.training_effects
        base = g.clone.character().bonus_cp
        row = g.clone.inv.create(copies.copy_type(3115, g.rules.simulator_formulas))
        uses = row['use_count']
        fighter.ap = fighter.ap_max
        with patch.object(combat.Fighter, 'schedule_action') as schedule:
            fighter.use_heal(dict(obj=inventory.oid_of(row)), inventory.USE_IDLE)
            self.assertTrue(schedule.called)
            args = schedule.call_args.args
        args[4](*args[5:])
        current = g.store.item(row['uniq'])
        self.assertEqual(current['use_count'] if current else 0, uses - 1)
        self.assertEqual(g.clone.character().bonus_cp, base + 10)
        self.assertEqual(len(manager.active), 1)
        active = next(iter(manager.active.values()))
        active.deadline = asyncio.get_running_loop().time() - 1
        manager.refresh()
        self.assertFalse(manager.active)
        self.assertEqual(g.clone.character().bonus_cp, base)
        self.assertEqual(self.main_state(), before)

    async def test_main_mutation_commands_never_reach_owner_handlers_inside_range(self):
        g = self.enter()
        item = g.clone.inv.create(copies.copy_type(26075, simulator=g.rules.simulator_formulas))
        oid = inventory.oid_of(item)
        before = self.main_state()
        private_rows = [dict(row) for row in g.clone.inv.rows()]
        commands = [
            ('ss_create', dict(s_type=inventory.SESSION_BANK, target=self.npc)),
            ('ss_create', dict(s_type=barter.SESSION_BARTER, target=self.s.pid)),
            ('ss_upd', dict(obj=oid, to=inventory.BANK)),
            ('sndml', dict(to='Receiver', type=0, item=oid, afro=100)),
            ('uldml', dict(id='1')),
            ('rmvml', dict(id='1')),
            ('ah_create', dict(obj=oid, time=24)),
            ('ah_op', dict(type=0, obj='1', amount=1)),
            ('head', dict(type=0)),
            ('gg_info', dict(det=3)),
            ('q_st', dict(mob=self.npc, q_idx=0)),
            ('q_co', dict(q_id=1)),
        ]
        for command, params in commands:
            with self.subTest(command=command, params=params), patch.object(
                    self.s, 'cmd_' + command, side_effect=AssertionError('main handler called')) as main:
                self.s.handle(command, params)
                main.assert_not_called()
                self.assertEqual(self.main_state(), before)
                self.assertEqual([dict(row) for row in g.clone.inv.rows()], private_rows)

    async def test_buffs_victory_death_and_reset_leave_entire_main_state_unchanged(self):
        self.s.char.set_spec(8, 3)
        self.s.char.set_spec(9, 4)
        self.s.char.spec[8][1], self.s.char.spec[9][1] = 123, 456
        self.s.char.hp, self.s.char.sp = 35, 60
        self.s.char.save(self.store)
        before = self.main_state()
        g = self.enter()
        g.configure_player(character.preset(20))
        g.clone.training_effects.add(3115)
        g.clone.inv.create(copies.copy_type(26075, simulator=g.rules.simulator_formulas))
        g.remember_outfit()
        self.assertEqual(self.main_state(), before)
        g.start('mob')
        target = g.room.combat.mobs[g.mob_eid]
        g.room.combat.kill(target, g.clone.combat)
        g.clone.combat.award_xp(0, 100000)
        g.clone.combat.count_kill(target.type_id)
        self.assertEqual(self.main_state(), before)
        g.start('mob')
        g.room.combat.kill(g.clone.combat, None)
        await asyncio.sleep(0)  # Complete the scheduled private respawn.
        self.assertEqual(g.phase, 'ready')
        g.last_request = 0
        g.request(dict(op='reset_prepare', token=g.token))
        nonce = g.reset_confirmation[0]
        g.last_request = 0
        g.request(dict(op='reset_player', token=g.token, confirmation=nonce))
        self.assertFalse(g.clone.inv.rows())
        self.assertFalse(g.clone.training_effects.active)
        g.exit(notify=False)
        self.assertEqual(self.main_state(), before)
        self.assertNotIn(g, runtime.ACTIVE)

    async def test_shared_room_rejects_other_visitors_tokens_and_item_identities(self):
        members, _, _ = self.party_members(2)
        before = self.main_state()
        training.enter(self.s, dict(npc=self.npc))
        first, second = (member.training_ground for member in members)
        for ground in (first, second):
            ground.clone.cmd_lenter({})
        foreign = second.clone.inv.create(copies.copy_type(26075, simulator=second.rules.simulator_formulas))
        forged = dict(foreign, uniq=self.real_item['uniq'])
        checkpoints = [copy.deepcopy(self.store.training_profile(member.char_id)) for member in members]
        for row in (foreign, forged, self.real_item):
            with self.subTest(row=row['uniq']):
                self.assertIsNone(first.clone.inv.find(inventory.oid_of(row)))
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row), to=inventory.PRIMARY,
                                             **{'from': inventory.BAG}))
                self.assertFalse(first.clone.inv.rows())
        with self.assertRaises(ValueError):
            first.request(dict(op='reset_prepare', token=second.token))
        self.assertEqual([self.store.training_profile(member.char_id) for member in members], checkpoints)
        self.assertIsNotNone(second.store.item(foreign['uniq']))
        self.assertEqual(self.main_state(), before)

    async def test_stale_training_items_cannot_be_posted_or_auctioned_after_exit(self):
        aid, _ = self.store.register('range-recipient', 'test-only')
        self.store.create_character(aid, 'Receiver', 0, '1')
        before = self.main_state()
        g = self.enter()
        row = g.clone.inv.create(copies.copy_type(26075, simulator=g.rules.simulator_formulas))
        stale = inventory.oid_of(row)
        forged = inventory.oid_of(dict(row, uniq=self.real_item['uniq']))
        g.exit(notify=False)
        for oid in (stale, forged):
            with self.subTest(oid=oid), patch.object(self.s.auction, 'at_auctioneer', return_value=True):
                for command, params in (
                    ('sndml', dict(to='Receiver', type=0, item=oid, body='test')),
                    ('ah_create', dict(obj=oid, time=24)),
                ):
                    self.s.writer.frames.clear()
                    self.s.handle(command, params)
                    replies = [decode(frame[:-1]) for frame in self.s.writer.frames]
                    self.assertTrue(any(name == 'cmdAck' and fields['res'] != inventory.RES_OK
                                        for name, fields in replies), replies)
                    self.assertEqual(self.main_state(), before)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(Isolation)
