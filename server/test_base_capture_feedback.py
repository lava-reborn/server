"""Native test-allies shots, weekly capture, pending flag and payment feedback."""
from datetime import datetime
import unittest
from unittest.mock import patch

import bosses
import combat
import holdings
import inventory
import items
import progression
import quests
import rooms
import server
import world
from protocol import decode
from test_training_ground import TrainingGround
from testkit import run_cases


SLOT = datetime(2026, 11, 21, 20, tzinfo=bosses.ZONE).timestamp()


class BaseCaptureFeedback(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = TrainingGround.asyncSetUp

    async def asyncTearDown(self):
        for ally in tuple(getattr(self.s, 'local_test_allies', ())):
            ally.exit()
        self.s.combat.cancel_timers()
        rc = getattr(self.s.room, 'combat', None)
        if rc is not None and rc.timer is not None:
            rc.timer.cancel()
            rc.timer = None
        await TrainingGround.asyncTearDown(self)

    def frames(self):
        return [decode(data[:-1]) for data in self.s.writer.frames]

    def scene(self, key, count=2):
        previous = getattr(self.s.room, 'combat', None)
        if previous is not None and previous.timer is not None:
            previous.timer.cancel()
            previous.timer = None
        self.base = holdings.site(key)
        self.now = SLOT + 10
        self.enterContext(patch.object(bosses, 'clock', lambda: self.now))
        self.enterContext(patch.object(server, 'CHEATS', True))
        for skill in self.s.char.skill:
            skill[0] = self.base.min_level
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.clan = self.store.clan_create(self.s.char_id, 'Capture test', 'capture-test', '', None)
        self.store.clan_treasury_adjust(self.clan, 4_500_000, 'admin')
        self.s.loc = world.location(self.base.loc)
        room = self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
        self.rc = room.combat = combat.RoomCombat(room, self.store)
        room.players[self.s] = True
        self.s.gx, self.s.gy = world.cell_of(self.base.loc)
        self.s.on_map = False
        self.rc.keep_hours()
        self.master = next(m for m in self.rc.bosses if m.type_id == self.base.boss)
        self.assertTrue(self.master.alive and not self.master.away)
        occupied = {n.cell for n in room.npcs.values()}
        self.cells = [c for c in progression.hex_neighbours(self.master.cell, self.s.loc.width, self.s.loc.height)
                      if c not in occupied and c not in self.s.loc.obstacles]
        self.assertGreaterEqual(len(self.cells), count + 1)
        self.s.pos = self.cells[0]
        for row in self.s.inv.rows():
            if row['slot'] == inventory.PRIMARY:
                self.store.delete_item(row['uniq'])
        gun = self.s.inv.create(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        si = items.params_of(gun['type_id'])
        # The native starter uses its old named ammo family, before the
        # later _KS/_ST catalogue. Use its actual compatible default round.
        self.store.update_item(gun['uniq'], ammo_type=si['comp_array'][0],
                               ammo_count=min(20, si['clip_size']))
        self.s.cmd_userMsg(dict(group=0, entry='/test-allies %d' % count))
        self.allies = tuple(self.s.local_test_allies)
        self.assertEqual(len(self.allies), count)
        self.assertTrue(any(cmd == 'userMsg' and 'союзники' in str(p['entry']) for cmd,p in self.frames()))
        for i, ally in enumerate(self.allies, 1):
            ally.enemy.pos = self.cells[i]
        self.s.writer.frames.clear()

    def shoot(self, fighter):
        gun = fighter.sess.inv.in_slot(inventory.PRIMARY)
        fighter.ap = fighter.ap_max
        fighter.use_fire(dict(obj=inventory.oid_of(gun), target='1%08x' % self.master.eid))
        self.assertIsNotNone(fighter.aim)
        args = fighter.aim._args[-1]
        fighter.aim.cancel()
        fighter.aim = None
        # Capture, rather than scatter, is under test. The real native action,
        # damage, consumption, ledger, kill and settlement paths remain active.
        with patch.object(combat, 'bullet_offset', return_value=0):
            fighter.fire_now(*args)

    def finish(self):
        self.master.hp, self.master.sp = 1, 0
        self.s.writer.frames.clear()
        self.shoot(self.s.combat)
        self.assertFalse(self.master.alive)

    def flag_packet(self):
        eid = next(eid for eid,npc in self.s.room.npcs.items() if npc.type_id == self.base.flag)
        self.s.send_npc_info(eid)
        frame = next(p for cmd,p in reversed(self.frames()) if cmd == 'userInfo_Trader' and p['id'] == eid)
        return eid, frame

    def answers(self):
        return [str(p['entry']) for cmd,p in self.frames() if cmd == 'userMsg' and p.get('from') == 0]

    async def test_two_real_allies_and_owner_capture_with_living_guards_and_show_pending_flag(self):
        for key in ('base_dn', 'base_ah'):
            with self.subTest(base=key):
                self.scene(key, 2)
                for ally in self.allies:
                    self.shoot(ally.enemy.combat)
                guards = [m for m in self.rc.bosses if m.type_id in self.base.guards + self.base.troops]
                self.assertTrue(all(m.alive and not m.away for m in guards))
                self.finish()
                held = holdings.holder(self.store, self.base)
                self.assertEqual(held['clan_id'], self.clan)
                self.assertEqual(held['paid_until'], 0)
                self.assertIsNone(holdings.paid_holder(self.store, self.base))
                self.assertIsNone(holdings.paid_base_for(self.store, self.base.loc, self.s.char_id))
                eid, frame = self.flag_packet()
                self.assertEqual(frame['clan'], self.clan)
                self.assertEqual((frame['can_trade'], frame['can_repair']), (0, 0))
                self.assertTrue(any(cmd == 'fellow' and p['id'] == eid and p['reg'] == self.clan
                                    for cmd,p in self.frames()))
                self.assertFalse(holdings.defender_friendly(self.rc, guards[0], self.s.combat))
                self.assertTrue(self.s.quest_available(quests.get(self.base.rent_quest)))
                self.assertTrue(any('База захвачена' in text and '21:15' in text and '1 500 000' in text
                                    for text in self.answers()))
                self.assertEqual(sum(1 for r in self.store.db.execute('SELECT * FROM clan_holding_log')
                                     if r['site'] == self.base.key and r['how'] == 'capture'), 1)
                for ally in self.allies:
                    ally.exit()
                self.store.holding_clear(self.base.key, 'admin')
                self.store.clan_disband(self.clan)

    async def test_four_real_allies_count_as_distinct_contributors_and_native_rent_activates_benefits(self):
        self.scene('base_ah', 4)
        for ally in self.allies:
            self.shoot(ally.enemy.combat)
        self.finish()
        self.assertEqual(holdings.holder(self.store, self.base)['clan_id'], self.clan)
        self.assertEqual(len([k for k in self.master.capture_harm if k < 0]), 4)
        flag, _ = self.flag_packet()
        npc = self.s.room.npc(flag)
        self.s.pos = npc.cell
        self.s.cmd_q_st(dict(mob=flag, q_idx=quests.given_by(npc.type_id).index(self.base.rent_quest)))
        row = next(r for r in self.store.quests(self.s.char_id) if r['type'] == self.base.rent_quest)
        self.s.cmd_q_co(dict(mob=flag, q_id=row['q_id']))
        self.assertIsNone(self.store.quest(row['q_id']))
        self.assertIsNotNone(holdings.paid_holder(self.store, self.base))
        self.assertIs(holdings.paid_base_for(self.store, self.base.loc, self.s.char_id), self.base)
        guard = next(m for m in self.rc.bosses if m.type_id in self.base.guards)
        self.assertTrue(holdings.defender_friendly(self.rc, guard, self.s.combat))

    async def test_two_damagers_with_third_alive_but_not_hitting_fail_with_exact_count(self):
        self.scene('base_dn', 2)
        self.shoot(self.allies[0].enemy.combat)
        self.finish()
        self.assertIsNone(holdings.holder(self.store, self.base))
        self.assertTrue(any('2 из 3' in text and '12+' in text for text in self.answers()))

    async def test_dead_contributor_does_not_relax_three_living_rule(self):
        self.scene('base_ah', 2)
        for ally in self.allies:
            self.shoot(ally.enemy.combat)
        self.allies[1].enemy.combat.dead = True
        self.finish()
        self.assertIsNone(holdings.holder(self.store, self.base))
        self.assertTrue(any('2 из 3' in text and '16+' in text for text in self.answers()))

    async def test_other_base_reservation_keeps_one_base_rule_and_explains_refusal(self):
        self.scene('base_dn', 2)
        other = holdings.site('base_ah')
        self.assertEqual(self.store.holding_capture(other.key, self.clan, SLOT, self.s.char_id,
                                                   self.now, base_sites=holdings.base_keys())[1], 'ok')
        for ally in self.allies:
            self.shoot(ally.enemy.combat)
        self.finish()
        self.assertIsNone(holdings.holder(self.store, self.base))
        self.assertTrue(any('одной клановой базой' in text for text in self.answers()))

    async def test_out_of_weekly_window_gives_reason_without_ownership(self):
        self.scene('base_dn', 2)
        for ally in self.allies:
            self.shoot(ally.enemy.combat)
        self.now = SLOT + 3601
        self.finish()
        self.assertIsNone(holdings.holder(self.store, self.base))
        self.assertTrue(any('с 20:00 до 21:00' in text for text in self.answers()))

    async def test_unpaid_flag_reservation_disappears_at_payment_deadline(self):
        self.scene('base_dn', 2)
        for ally in self.allies:
            self.shoot(ally.enemy.combat)
        self.finish()
        self.assertEqual(self.flag_packet()[1]['clan'], self.clan)
        self.now = SLOT + 75 * 60
        self.assertNotIn('clan', self.flag_packet()[1])
        self.assertIsNone(holdings.paid_holder(self.store, self.base))
        self.assertFalse(self.s.quest_available(quests.get(self.base.rent_quest)))


if __name__ == '__main__':
    run_cases(BaseCaptureFeedback)
