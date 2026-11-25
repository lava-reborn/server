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
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 11, 21, 20, tzinfo=bosses.ZONE).timestamp() + 60
        self.enterContext(patch.object(bosses, 'clock', lambda: self.now))

    def lease(self, loc_id):
        base = holdings.base_for(loc_id)
        slot = self.now - 60
        self.store.holding_set(base.key, self.clan, 'admin', slot=slot, when=slot)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                              (slot + 7 * 86400 - 300, base.key))
        self.store.db.commit()

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

    def test_paid_owner_can_complete_both_native_entries(self):
        self.member()
        for loc_id, kind, interior in ((118, 18201, 609), (1442, 18203, 1443)):
            with self.subTest(location=loc_id):
                eid = self.scene(loc_id, kind)
                self.lease(loc_id)
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
                self.lease(loc_id)
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

    def test_all_lifts_recheck_paid_ownership_at_offer_take_and_stale_hand_in(self):
        self.member()
        aid, _ = self.store.register('foreign-base', 'local-only')
        head, _ = self.store.create_character(aid, 'ForeignBase', 0, '1')
        other = self.store.clan_create(head, 'Foreign clan', 'foreign-base', '', None)
        slot, week = self.now - 60, 7 * 86400
        states = (
            ('neutral', None, slot, 0),
            ('unpaid-owner', self.clan, slot, 0),
            ('paid-foreign', other, slot, slot + week - 300),
            ('expired-owner', self.clan, slot, self.now),
            ('future-owner', self.clan, slot + week, slot + 2 * week - 300),
            ('invalid-extension', self.clan, slot, slot + week + 1),
        )
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            base = holdings.base_for(loc_id)
            for state, clan, captured, until in states:
                self.store.holding_clear(base.key, 'admin')
                if clan is not None:
                    self.store.holding_set(base.key, clan, 'admin', slot=captured, when=slot)
                    self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?', (until, base.key))
                    self.store.db.commit()
                for eid, npc in self.entry_npcs(loc_id, kind):
                    with self.subTest(location=loc_id, state=state, npc=eid):
                        self.s.pos = npc.cell
                        self.s.enter_location.reset_mock()
                        self.s.frames.clear()
                        frame = self.npc_quest_frame(eid)
                        self.assertEqual((frame['give_quests'], frame['take_quests']), ([], []))
                        self.s.cmd_q_status(dict(q_type=kind))
                        self.assertEqual(self.s.frames[-1][1]['status'], 0)
                        self.take(kind, eid)
                        self.assertFalse(self.store.has_quest(self.cid, kind))
                        qid = self.store.take_quest(self.cid, kind, {}, True)
                        before = dict(self.store.quest(qid))
                        self.s.cmd_q_co(dict(q_id=qid, mob=eid))
                        self.assertEqual(dict(self.store.quest(qid)), before)
                        self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.s.frames)
                        self.s.enter_location.assert_not_called()
                        self.store.drop_quest(qid)

    def test_fight_delayed_entry_loses_access_after_expiry_or_owner_change(self):
        async def check(loc_id, kind, change):
            self.lease(loc_id)
            self.scene(loc_id, kind)
            quest = quests.get(kind)
            self.s.hold_line = Mock(return_value=('fight', 'Подождите окончания боя.'))
            self.s.follow_way(quest, self.s.room)
            self.assertIsNotNone(self.s.way)
            self.s.way.cancel()
            if change == 'expire':
                self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                                      (self.now, holdings.base_for(loc_id).key))
                self.store.db.commit()
            else:
                self.store.holding_clear(holdings.base_for(loc_id).key, 'admin')
            with patch.object(self.s, 'refund_way') as refund, \
                    patch.object(server.travel, 'plan_quest_way') as plan:
                self.s.take_way(quest, self.s.room, frozenset(('fight',)))
                refund.assert_called_once_with(quest)
                plan.assert_not_called()
            self.assertIsNone(self.s.way)
        self.member()
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            for change in ('expire', 'owner'):
                with self.subTest(location=loc_id, change=change):
                    asyncio.run(check(loc_id, kind, change))

    def test_fight_delayed_entry_rechecks_live_clan_membership(self):
        async def check(loc_id, kind):
            self.member()
            self.lease(loc_id)
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

    def entry_npcs(self, loc_id, kind):
        self.scene(loc_id)
        found = [(eid, npc) for eid, npc in self.s.room.npcs.items()
                 if kind in quests.given_by(npc.type_id)]
        self.assertEqual(len(found), 3)
        return found

    def npc_quest_frame(self, eid):
        # Only combat presentation is unrelated to this packet regression;
        # membership, actual room NPCs, quest indices and handlers are native.
        with patch.object(self.s, 'combat', NS(mob_info=lambda _: {}, after_npc_info=lambda _: None)):
            self.s.send_npc_info(eid)
        return next(p for cmd, p in reversed(self.s.frames)
                    if cmd.startswith('userInfo') and p['id'] == eid)

    def test_all_six_lifts_hide_entries_and_reject_native_status_and_take_for_clanless(self):
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            for eid, npc in self.entry_npcs(loc_id, kind):
                with self.subTest(location=loc_id, npc=eid):
                    self.s.pos = npc.cell
                    self.s.frames.clear()
                    frame = self.npc_quest_frame(eid)
                    self.assertEqual(frame['give_quests'], [])
                    self.assertEqual(frame['take_quests'], [])
                    self.s.cmd_q_status(dict(q_type=kind))
                    self.assertEqual(self.s.frames[-1][0], 'q_status')
                    self.assertEqual(self.s.frames[-1][1]['status'], 0)
                    self.take(kind, eid)
                    self.assertEqual(self.s.frames[-1], ('cmdAck', dict(res=server.RES_NOT_AVAILABLE)))
                    self.assertFalse(self.store.has_quest(self.cid, kind))
                    self.assertEqual(self.s.loc.id, loc_id)
                    # A private packet must not edit the shared/native index.
                    self.assertEqual(quests.given_by(npc.type_id), [kind])

    def test_all_six_lifts_keep_real_member_indices_and_complete_native_passages(self):
        self.member()
        for loc_id, kind, interior in ((118, 18201, 609), (1442, 18203, 1443)):
            self.lease(loc_id)
            for index in range(3):
                entries = self.entry_npcs(loc_id, kind)
                eid, npc = entries[index]
                self.s.pos = npc.cell
                with self.subTest(location=loc_id, npc=eid):
                    frame = self.npc_quest_frame(eid)
                    self.assertEqual(frame['give_quests'], quests.given_by(npc.type_id))
                    self.assertEqual(frame['take_quests'], quests.taken_by(npc.type_id))
                    self.s.cmd_q_status(dict(q_type=kind))
                    self.assertEqual(self.s.frames[-1][1]['status'], 1)
                    self.take(kind, eid)
                    row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                    self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                    self.assertIsNone(self.store.quest(row['q_id']))
                    self.assertEqual(self.s.loc.id, interior)

    def test_cached_member_status_and_old_active_quest_cannot_open_any_lift_after_leaving(self):
        for loc_id, kind in ((118, 18201), (1442, 18203)):
            self.member()
            self.lease(loc_id)
            entries = self.entry_npcs(loc_id, kind)
            quest = quests.get(kind)
            q_id = self.store.take_quest(self.cid, kind, quest.fresh_progress(), True)
            self.s.cmd_q_status(dict(q_type=kind))
            self.assertEqual(self.s.frames[-1][1]['status'], 1)
            snapshot = self.s._quest_status_snapshot
            before = dict(self.store.quest(q_id))
            self.assertTrue(self.store.clan_member_remove(self.cid, self.clan))
            # A stale cached identity is not evidence of actual membership.
            self.s.active = dict(self.s.active, clan_id=str(self.clan), clan_name='Passage clan')
            for eid, npc in entries:
                with self.subTest(location=loc_id, npc=eid):
                    self.s.pos = npc.cell
                    self.s.frames.clear()
                    frame = self.npc_quest_frame(eid)
                    self.assertEqual((frame['give_quests'], frame['take_quests']), ([], []))
                    self.s.cmd_q_status(dict(q_type=kind))
                    self.assertEqual(self.s.frames[-1][1]['status'], 0)
                    self.assertIs(self.s._quest_status_snapshot, snapshot)
                    self.s.cmd_q_co(dict(q_id=q_id, mob=eid))
                    self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.s.frames)
                    self.assertEqual(dict(self.store.quest(q_id)), before)
                    self.assertEqual(self.s.loc.id, loc_id)
            self.store.drop_quest(q_id)

    def test_no_clan_wire_sentinels_or_orphan_membership_are_not_actual_clans(self):
        for clan_id in (-1, 0, 16777215, 999999):
            with self.subTest(clan=clan_id):
                if clan_id != 999999:
                    self.store.db.execute('INSERT INTO clans (id,name,name_key,head,created_at) VALUES (?,?,?,?,?)',
                                          (clan_id, 'Imported sentinel', 'sentinel-' + str(clan_id), self.cid, 1))
                self.store.db.execute('INSERT INTO clan_members (char_id,clan_id,joined_at) VALUES (?,?,?)',
                                      (self.cid, clan_id, 1))
                self.store.db.commit()
                for loc_id, kind in ((118, 18201), (1442, 18203)):
                    eid = self.scene(loc_id, kind)
                    self.s.active = dict(self.s.active, clan_id=str(clan_id))
                    self.s.cmd_q_status(dict(q_type=kind))
                    self.assertEqual(self.s.frames[-1][1]['status'], 0)
                    self.assertEqual(self.npc_quest_frame(eid)['give_quests'], [])
                    self.take(kind, eid)
                    self.assertFalse(self.store.has_quest(self.cid, kind))
                self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                if clan_id != 999999:
                    self.store.db.execute('DELETE FROM clans WHERE id=?', (clan_id,))
                self.store.db.commit()

    def test_clanless_exit_lists_and_status_remain_available_at_all_six_return_lifts(self):
        for interior, kind in ((609, 18202), (1443, 18204)):
            for eid, npc in self.entry_npcs(interior, kind):
                with self.subTest(location=interior, npc=eid):
                    self.s.pos = npc.cell
                    frame = self.npc_quest_frame(eid)
                    self.assertEqual(frame['give_quests'], quests.given_by(npc.type_id))
                    self.assertEqual(frame['take_quests'], quests.taken_by(npc.type_id))
                    self.assertIn(kind, frame['give_quests'])
                    self.assertIn(kind, frame['take_quests'])
                    for offered in frame['give_quests']:
                        self.s.cmd_q_status(dict(q_type=offered))
                    statuses = {p['type']: p['status'] for cmd, p in self.s.frames if cmd == 'q_status'}
                    self.assertEqual({t for t, status in statuses.items() if status}, {kind})
                    self.s.cmd_q_status(dict(q_type=kind))
                    self.assertEqual(self.s.frames[-1][1]['status'], 1)

    def test_only_local_exit_is_offered_and_each_of_six_lifts_completes_it(self):
        for joined in (False, True):
            if joined:
                self.member()
            for interior, kind, surface in ((609, 18202, 118), (1443, 18204, 1442)):
                other = next(t for t in quests.CLAN_BASE_EXITS if t != kind)
                for eid, npc in self.entry_npcs(interior, kind):
                    with self.subTest(member=joined, interior=interior, lift=eid):
                        self.scene(interior)
                        self.s.pos = npc.cell
                        self.assertTrue(self.s.quest_available(quests.get(kind)))
                        self.assertFalse(self.s.quest_available(quests.get(other)))
                        self.take(other, eid)
                        self.assertFalse(self.store.has_quest(self.cid, other))
                        self.take(kind, eid)
                        row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                        self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                        self.assertEqual(self.s.loc.id, surface)

    def test_every_return_lift_remains_usable_when_membership_or_owner_changes(self):
        account, _ = self.store.register('new-base-head', 'local-only')
        head, _ = self.store.create_character(account, 'NewBaseHead', 0, '1')
        other = self.store.clan_create(head, 'New base owner', 'new-base-owner', '', None)
        for interior, kind, surface in ((609, 18202, 118), (1443, 18204, 1442)):
            base = holdings.base_for(interior)
            for change in ('leave', 'foreign', 'new-owner', 'neutral', 'expired'):
                for index in range(3):
                    with self.subTest(interior=interior, change=change, lift=index):
                        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                        self.store.db.commit()
                        self.member()
                        self.store.holding_clear(base.key, 'admin')
                        self.store.holding_set(base.key, self.clan, 'admin', slot=1000, when=1000)
                        self.store.db.execute('UPDATE clan_holdings SET paid_until=2000 WHERE site=?', (base.key,))
                        self.store.db.commit()
                        entries = self.entry_npcs(interior, kind)
                        eid, npc = entries[index]
                        self.s.pos = npc.cell
                        self.take(kind, eid)
                        row = next(r for r in self.store.quests(self.cid) if r['type'] == kind)
                        if change in ('leave', 'foreign'):
                            self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                            self.store.db.commit()
                            if change == 'foreign':
                                self.store.clan_member_add(self.cid, other, 0, '')
                        elif change == 'new-owner':
                            self.store.holding_set(base.key, other, 'admin', slot=1000, when=1000)
                        elif change == 'neutral':
                            self.store.holding_clear(base.key, 'admin')
                        else:
                            self.store.db.execute('UPDATE clan_holdings SET paid_until=1 WHERE site=?', (base.key,))
                            self.store.db.commit()
                        self.s.frames.clear()
                        self.assertTrue(self.s.quest_available(quests.get(kind)))
                        self.s.cmd_q_status(dict(q_type=kind))
                        self.assertEqual(self.s.frames[-1][1]['status'], 1)
                        self.s.cmd_q_co(dict(q_id=row['q_id'], mob=eid))
                        self.assertEqual(self.s.loc.id, surface)
                        self.assertIsNone(self.store.quest(row['q_id']))
                        self.assertIn(('cmdAck', dict(res=0)), self.s.frames)


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
        moment = datetime(2026, 11, 23, 17, 30, tzinfo=bosses.ZONE).timestamp()
        for site in holdings.sites().values():
            if site.kind != 'warehouse':
                continue
            with self.subTest(site=site.key), patch.object(server, 'CHEATS', True), \
                    patch.object(bosses.time, 'time', return_value=moment), patch.object(bosses, '_OFFSET', 0):
                rc = self.room_combat(site.loc)
                rc.keep_hours()
                self.assertTrue(all(m.away for m in rc.bosses))
                self.assertTrue(any('появился рядом' in text for text in self.command()))
                guards = [m for m in rc.bosses if m.type_id in site.guards]
                self.assertEqual(len(guards), 2)
                self.assertTrue(all(m.alive and not m.away for m in guards))
                self.assertTrue(next(m for m in rc.bosses if m.type_id == site.boss).alive)

    def test_alias_advances_to_weekly_timer_and_restores_master_with_living_guards(self):
        moment = datetime(2026, 11, 23, 17, 30, tzinfo=bosses.ZONE).timestamp()
        for key in ('base_dn', 'base_ah'):
            base = holdings.site(key)
            rc = self.room_combat(base.loc)
            with self.subTest(base=key), patch.object(server, 'CHEATS', True), \
                    patch.object(bosses.time, 'time', return_value=moment), patch.object(bosses, '_OFFSET', 0):
                rc.keep_hours()
                master = next(m for m in rc.bosses if m.type_id == base.boss)
                self.assertTrue(master.away)
                self.assertTrue(all(m.away for m in rc.bosses if m.type_id in base.guards))
                treasury = self.store.clan_treasury(self.clan)
                self.assertTrue(any('восстановлена' in text for text in self.command()))
                slot = holdings.battle_slot(base)
                guards = [m for m in rc.bosses if m.type_id in base.guards + base.troops]
                master = next(m for m in rc.bosses if m.type_id == base.boss)
                self.assertEqual(len(guards), 13)
                self.assertTrue(all(m.alive and not m.away for m in guards))
                self.assertTrue(master.alive and not master.away)
                self.assertEqual(master.slot, slot)
                opened = datetime.fromtimestamp(slot, bosses.ZONE)
                self.assertEqual((opened.weekday(), opened.hour, opened.minute), (5, 20, 0))
                rc.keep_hours()
                self.assertTrue(master.alive and not master.away)
                self.assertIsNone(self.store.holding(base.key))
                self.assertEqual(self.store.clan_treasury(self.clan), treasury)
                self.assertTrue(any('исходной' in text for text in self.command('/test-time-reset')))
                self.assertEqual(bosses.clock(), moment)
                rc.keep_hours()
                self.assertTrue(master.away)
                self.assertTrue(all(m.away for m in guards if m.type_id in base.guards))
                self.assertTrue(all(m.alive and not m.away for m in guards if m.type_id in base.troops))

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
