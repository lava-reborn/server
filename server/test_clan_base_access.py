"""Clan bunker access and local native boss/escort spawning boundaries."""
import asyncio
import logging
import os
import unittest
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import accounts
import bosses
import combat
import holdings
import mobs
import progression
import quests
import rooms
import server
import world
from test_quest_state import session
from testkit import run_cases


class BaseScene(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, 'STORE', self.store))
        account, _ = self.store.register('passage-head', 'local-only')
        head, _ = self.store.create_character(account, 'PassageHead', 0, '1')
        self.clan = self.store.clan_create(head, 'Passage clan', 'passage-clan', '', None)
        account, _ = self.store.register('passage-member', 'local-only')
        self.cid, _ = self.store.create_character(account, 'PassageMember', 0, '1')
        self.s = session(self.store, level=17, char_id=self.cid)
        self.s.active = self.store.character(self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.closed = self.s.on_map = False
        self.s.combat = NS(dead=False)
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.s.way = self.s.way_quest = None
        self.s.enter_location = Mock()
        self.s.cancel_travel = Mock()
        self.s.hold_line = Mock(return_value=None)
        self.s.frames = []
        self.s.send = lambda cmd, **p: self.s.frames.append((cmd, p))
        self.s.answer = lambda text, *args: self.s.send('answer', text=text)
        self.s.live_cell = lambda: self.s.pos

    def member(self):
        self.store.clan_member_add(self.cid, self.clan, 0, '')

    def scene(self, loc_id, quest_type=None):
        s = self.s
        s.loc = world.location(loc_id)
        s.room = rooms.Room(s.loc, rooms.IdAllocator(), world.mob_types())
        s.pos = s.loc.entry_cell()
        if quest_type is not None:
            giver = quests.get(quest_type).give[0]
            eid, npc = next((eid, npc) for eid, npc in s.room.npcs.items()
                            if npc.type_id == giver)
            s.pos = npc.cell
        else:
            eid = None
        s.gx, s.gy = 6083, 1957
        s.frames.clear()
        return eid

    def take(self, quest_type, eid):
        giver = self.s.npc_type(eid)
        self.s.cmd_q_st(dict(mob=eid, q_idx=quests.given_by(giver).index(quest_type)))


class ClanBaseAccess(BaseScene):
    def test_clanless_can_enter_both_courtyards_from_the_global_map(self):
        for loc_id in (118, 1442):
            with self.subTest(location=loc_id):
                self.scene(loc_id)
                room = self.s.room
                room.combat = combat.RoomCombat(room, self.store)
                gx, gy = world.cell_of(loc_id)
                self.s.current_pos = lambda: (gx + .5, gy + .5)
                self.s.on_map = True
                self.s.enter_location.reset_mock()
                with patch.object(server, 'ROOMS', NS(get=lambda key: room)), \
                        patch.object(server, 'GMAP', NS(leave=Mock())):
                    self.assertTrue(self.s.enter_cell(acknowledge=True))
                self.assertIsNone(self.store.clan_member(self.cid))
                self.assertFalse(self.s.on_map)
                self.assertEqual(self.s.loc.id, loc_id)
                self.s.enter_location.assert_called_once()
                self.assertIn(('cmdAck', dict(res=0)), self.s.frames)

    def test_clanless_cannot_offer_or_take_either_bunker_entry(self):
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            with self.subTest(location=loc_id):
                eid = self.scene(loc_id, kind)
                self.assertIsNone(self.store.clan_member(self.cid))
                self.assertFalse(self.s.quest_available(quests.get(kind)))
                self.take(kind, eid)
                self.assertFalse(self.store.has_quest(self.cid, kind))
                self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.s.frames)
                self.assertEqual(self.s.loc.id, loc_id)
                self.assertIn(eid, self.s.room.npcs)  # the courtyard stays usable

    def test_member_of_any_clan_can_complete_both_native_entries(self):
        self.member()
        for loc_id, kind, interior in ((118, 18201, 609), (1442, 18203, 1443)):
            with self.subTest(location=loc_id):
                eid = self.scene(loc_id, kind)
                self.assertIsNone(holdings.holder(self.store, holdings.base_for(loc_id)))
                self.assertTrue(self.s.quest_available(quests.get(kind)))
                self.take(kind, eid)
                row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                self.assertIsNone(self.store.quest(row['q_id']))
                self.assertTrue(self.store.quest_done(self.cid, kind))
                self.assertEqual(self.s.loc.id, interior)
                self.assertIn(('cmdAck', dict(res=0)), self.s.frames)

    def test_leaving_clan_blocks_stale_hand_in_without_consuming_quest(self):
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            with self.subTest(location=loc_id):
                self.member()
                eid = self.scene(loc_id, kind)
                self.take(kind, eid)
                row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                before = dict(row)
                self.assertTrue(self.store.clan_member_remove(self.cid, self.clan))
                self.assertFalse(self.s.quest_available(quests.get(kind)))
                self.s.frames.clear()
                self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                self.assertEqual(dict(self.store.quest(row['q_id'])), before)
                self.assertFalse(self.store.quest_done(self.cid, kind))
                self.assertEqual(self.s.loc.id, loc_id)
                self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.s.frames)
                self.s.enter_location.assert_not_called()

    def test_fight_delayed_entry_rechecks_live_clan_membership(self):
        async def check(loc_id, kind):
            self.member()
            self.scene(loc_id, kind)
            quest = quests.get(kind)
            self.s.hold_line = Mock(return_value=('fight', 'Подождите окончания боя.'))
            self.s.follow_way(quest, self.s.room)
            self.assertIsNotNone(self.s.way)
            self.s.way.cancel()
            self.assertTrue(self.store.clan_member_remove(self.cid, self.clan))
            with patch.object(self.s, 'refund_way') as refund, \
                    patch.object(server.travel, 'plan_quest_way') as plan:
                self.s.take_way(quest, self.s.room, frozenset(('fight',)))
                refund.assert_called_once_with(quest)
                plan.assert_not_called()
            self.assertIsNone(self.s.way)
            self.s.enter_location.assert_not_called()
            self.assertEqual(self.s.loc.id, loc_id)
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            with self.subTest(location=loc_id):
                asyncio.run(check(loc_id, kind))

    def test_clanless_can_leave_either_bunker(self):
        for interior, kind, surface in ((609, 18202, 118), (1443, 18204, 1442)):
            with self.subTest(location=interior):
                eid = self.scene(interior, kind)
                self.assertTrue(self.s.quest_available(quests.get(kind)))
                self.take(kind, eid)
                row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                self.assertEqual(self.s.loc.id, surface)
                self.assertTrue(self.store.quest_done(self.cid, kind))

    def test_capture_minimum_is_inclusive_and_has_no_upper_level_limit(self):
        for key, levels in (('base_dn', (11, 12, 13, 17)), ('base_ah', (15, 16, 17))):
            base = holdings.site(key)
            for level in levels:
                with self.subTest(base=key, level=level):
                    fighters = [dict(char=i + 1, clan=self.clan, clan_name='Passage clan',
                                     here=True, alive=True, level=level, harm=10)
                                for i in range(3)]
                    snap = dict(fighters=fighters, pool=100, killer=1, killer_clan=self.clan)
                    won = holdings.winner(snap, holdings.BASE_SQUAD, base.min_level)
                    self.assertEqual(won is not None, level >= base.min_level)
                    fighters[0]['level'] = base.min_level - 1
                    self.assertIsNone(holdings.winner(snap, holdings.BASE_SQUAD, base.min_level))


class LocalBossSpawning(BaseScene):
    def room_combat(self, loc_id):
        self.scene(loc_id)
        rc = combat.RoomCombat(self.s.room, self.store)
        self.s.room.combat = rc
        return rc

    def command(self, entry='/boss-spawn'):
        self.s.frames.clear()
        self.s.cmd_userMsg(dict(group=0, entry=entry))
        return [p['text'] for cmd, p in self.s.frames if cmd == 'answer']

    def test_local_alias_restores_and_moves_boss_with_native_escort(self):
        rc = self.room_combat(31)
        self.assertEqual(len(rc.escorts), 3)
        moment = datetime(2026, 11, 23, 17, 30, tzinfo=bosses.ZONE).timestamp()
        with patch.object(server, 'CHEATS', True), patch.object(bosses.time, 'time', return_value=moment), \
                patch.object(bosses, '_OFFSET', 0):
            rc.keep_hours()
            self.assertTrue(all(m.away for m in rc.bosses))
            for escort in rc.escorts:
                rc.boss_leaves(escort)
            homes = {m.eid: m.home for m in rc.bosses + rc.escorts}
            self.assertTrue(any('штатной охраной' in text for text in self.command()))
            cells = []
            for mob in rc.bosses + rc.escorts:
                self.assertTrue(mob.alive and not mob.away)
                self.assertEqual((mob.hp, mob.sp), (mob.hp_max, mob.sp_max))
                self.assertEqual(mob.home, homes[mob.eid])
                self.assertIn(mob.eid, self.s.room.npcs)
                self.assertNotIn(mob.cell, self.s.loc.obstacles)
                self.assertLessEqual(mobs.hex_distance(mob.cell, self.s.pos, self.s.loc.width), 2)
                cells.append(mob.cell)
            self.assertEqual(len(cells), len(set(cells)))

    def test_alias_restores_warehouse_boss_and_its_two_guards(self):
        site = holdings.site('wh_sever')
        rc = self.room_combat(site.loc)
        moment = datetime(2026, 11, 23, 17, 30, tzinfo=bosses.ZONE).timestamp()
        with patch.object(server, 'CHEATS', True), patch.object(bosses.time, 'time', return_value=moment), \
                patch.object(bosses, '_OFFSET', 0):
            rc.keep_hours()
            self.assertTrue(any('появился рядом' in text for text in self.command()))
            guards = [m for m in rc.bosses if m.type_id in site.guards]
            self.assertEqual(len(guards), 2)
            self.assertTrue(all(m.alive and not m.away for m in guards))
            self.assertTrue(next(m for m in rc.bosses if m.type_id == site.boss).alive)

    def test_alias_restores_both_base_waves_without_bypassing_master_gate(self):
        moment = datetime(2026, 11, 23, 17, 30, tzinfo=bosses.ZONE).timestamp()
        for key in ('base_dn', 'base_ah'):
            base = holdings.site(key)
            rc = self.room_combat(base.loc)
            with self.subTest(base=key), patch.object(server, 'CHEATS', True), \
                    patch.object(bosses.time, 'time', return_value=moment), patch.object(bosses, '_OFFSET', 0):
                rc.keep_hours()
                self.assertTrue(any('восстановлена' in text for text in self.command()))
                slot = holdings.battle_slot(base)
                guards = [m for m in rc.bosses if m.type_id in base.guards + base.troops]
                master = next(m for m in rc.bosses if m.type_id == base.boss)
                self.assertEqual(len(guards), 13)
                self.assertTrue(all(m.alive and not m.away for m in guards))
                self.assertTrue(master.away)
                for guard in guards:
                    guard.alive = False
                    guard.away = True
                    guard.slot = slot
                    self.s.room.npcs.pop(guard.eid, None)
                rc.keep_hours()
                self.assertTrue(master.alive and not master.away)

    def test_refuses_invalid_arguments_production_and_active_escort(self):
        rc = self.room_combat(31)
        with patch.object(server, 'CHEATS', False):
            before = bosses._OFFSET
            self.assertIn('локального', self.s.admin_boss_now())
            self.assertEqual(bosses._OFFSET, before)
        with patch.object(server, 'CHEATS', True):
            self.assertEqual(self.command('/boss-spawn 3'), ['Используйте /boss-spawn без аргументов.'])
            escort = rc.escorts[0]
            escort.aim = NS(cancel=lambda: None)
            before = bosses._OFFSET
            self.assertTrue(any('конца боя' in text for text in self.command()))
            self.assertEqual(bosses._OFFSET, before)


if __name__ == '__main__':
    run_cases(ClanBaseAccess, LocalBossSpawning)
