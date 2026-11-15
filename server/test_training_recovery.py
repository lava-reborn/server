"""Checkpoint fault injection, stable namespaces and disabled-mode boundaries."""
from contextlib import contextmanager
import asyncio
import copy
import json
import unittest
from unittest.mock import patch

import inventory
import items
import progression
import rooms
import server
import storage
import world
from training import settings
from training import api, checkpoints, commands, content, formulas, items as copies
from training import profiles, rules, runtime, session as training
import test_training_ground as fixtures
from testkit import run_cases


class Recovery(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    party_members = fixtures.TrainingGround.party_members

    def reconnect(self):
        old = self.s
        self.s = server.Session(fixtures.Writer(), 'reconnected')
        self.s.training_protocol = 1
        self.s.char_id = old.char_id
        self.s.active = dict(self.store.character(old.char_id))
        self.s.char = progression.Character.load(self.store, old.char_id)
        self.s.loc, self.s.pos = old.loc, old.pos
        self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
        self.npc, bert = next((eid, npc) for eid, npc in self.s.room.npcs.items()
                              if npc.type_id == settings.BERT)
        self.s.pos = bert.cell
        return self.s

    async def test_entry_persists_real_progress_before_the_clone_can_change(self):
        self.s.char.set_skill(progression.SHOOTING, 13)
        self.s.char.hp = 30
        g = self.enter()
        restored = progression.Character.load(self.store, self.s.char_id)
        self.assertEqual(restored.skill, self.s.char.skill)
        self.assertEqual(restored.hp, self.s.char.hp)
        g.clone.char.set_skill(progression.SHOOTING, 20)
        g.save_settings()
        again = progression.Character.load(self.store, self.s.char_id)
        self.assertEqual(again.skill, restored.skill)
        self.assertEqual(again.hp, restored.hp)

    async def test_failed_entry_keeps_pending_real_specialization_slots_dirty(self):
        self.s.char._spec_slots_dirty = True
        with patch.object(self.store, 'save_training_profile', side_effect=ValueError('checkpoint failed')):
            with self.assertRaises(ValueError):
                self.enter()
        self.assertTrue(self.s.char._spec_slots_dirty)
        self.assertIsNone(self.s.training_ground)
        self.unchanged()

    async def test_invalid_token_rate_and_distance_reject_before_snapshot(self):
        g = self.enter()
        with patch.object(checkpoints, 'snapshot_database', side_effect=AssertionError('unnecessary copy')):
            with self.assertRaises(ValueError):
                g.request(dict(op='spawn', token='forged', spawn_point=1))
            g.last_request = __import__('time').monotonic()
            with self.assertRaises(ValueError):
                g.request(dict(op='spawn', token=g.token, spawn_point=1))
            g.last_request = 0
            g.clone.pos = 0
            with self.assertRaises(ValueError):
                g.request(dict(op='spawn', token=g.token, spawn_point=1))
        self.unchanged()

    async def test_failed_apply_and_serial_exhaustion_do_not_publish_partial_character(self):
        g = self.enter()
        gun = g.clone.inv.create(copies.copy_type(26075))
        before = [dict(row) for row in g.clone.inv.rows()]
        original = g.clone.char
        profile = dict(skills=[12, 12, 12, 0, 0], specs=[3] * 12 + [-1] * 3,
                       gear={26075: 1, 6108: 20})
        create = g.clone.inv.create
        calls = 0

        def fail_second(*args, **kw):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError('injected second create')
            return create(*args, **kw)

        with patch.object(g.clone.inv, 'create', side_effect=fail_second):
            with self.assertRaises(ValueError):
                g.apply(g.clone, profile)
        self.assertIs(g.clone.char, original)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        g.store.db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='items'", (g.serial_base + (1 << 20),))
        g.store.db.commit()
        with self.assertRaises(ValueError):
            g.apply(g.clone, profile)
        self.assertIs(g.clone.char, original)
        self.assertIsNotNone(g.store.item(gun['uniq']))
        self.unchanged()

    async def test_private_commit_reply_failure_recovers_from_memory_snapshot(self):
        g = self.enter()
        original = g.clone.char
        before = list(g.store.db.raw.iterdump())
        atomic = storage.atomic

        @contextmanager
        def commit_then_fail(db):
            with atomic(db):
                yield db
            if db is g.store.db:
                raise storage.CommitError('injected lost private commit reply')

        with patch.object(storage, 'atomic', commit_then_fail):
            with self.assertRaises(storage.CommitError):
                g.configure_player(dict(skills=[12, 12, 0, 0, 0], specs=[-1] * 15, gear={}))
        self.assertFalse(g.closed)
        self.assertIs(g.clone.char, original)
        self.assertEqual(list(g.store.db.raw.iterdump()), before)
        self.unchanged()

    async def test_uncertain_main_commit_is_read_back_without_compensation(self):
        g = self.enter()
        before_items = [dict(row) for row in self.s.inv.rows()]
        write = self.store.save_training_profile
        calls = []

        def committed_but_reply_lost(*args):
            calls.append(args)
            write(*args)
            raise storage.CommitError('injected lost durable reply')

        with patch.object(self.store, 'save_training_profile', side_effect=committed_but_reply_lost):
            with self.assertRaises(ValueError):
                g.configure_player(dict(skills=[0, 16, 0, 0, 0], specs=[-1] * 15, gear={}))
        self.assertEqual(len(calls), 1)
        self.assertTrue(g.closed)
        self.assertIsNone(self.s.training_ground)
        self.assertEqual([dict(row) for row in self.s.inv.rows()], before_items)
        self.assertEqual(self.store.training_profile(self.s.char_id)['player']['skills'][1], 16)
        self.assertTrue(training.resume(self.reconnect()))
        self.assertEqual(self.s.training_ground.clone.char.level, 16)

    async def test_failed_private_recovery_closes_only_private_state_without_main_write(self):
        g = self.enter()
        saved = self.store.training_profile(self.s.char_id)
        with (patch.object(g.clone.inv, 'switch_profile', side_effect=ValueError('injected')),
                patch.object(checkpoints, 'restore_database', side_effect=RuntimeError('injected recovery failure')),
                patch.object(self.store, 'save_training_profile', side_effect=AssertionError('compensation write'))):
            with self.assertRaises(ValueError):
                g.configure_player(g.profile, g.rules)
        self.assertTrue(g.closed)
        self.assertIsNone(self.s.training_ground)
        self.assertEqual(saved, self.store.training_profile(self.s.char_id))

    async def test_resume_guard_stops_repeating_bad_checkpoint_without_erasing_presets(self):
        g = self.enter()
        g.exit(notify=False, suspend=True)
        saved = self.store.training_profile(self.s.char_id)
        saved['resume_failures'] = 'corrupt old counter'
        self.store.save_training_profile(self.s.char_id, saved)
        with patch.object(training, 'Ground', side_effect=ValueError('invalid saved setup')) as construct:
            for _ in range(3):
                self.assertFalse(training.resume(self.s))
            self.assertFalse(training.resume(self.s))
            self.assertEqual(construct.call_count, 3)
        recovered = self.store.training_profile(self.s.char_id)
        self.assertFalse(recovered['inside'])
        self.assertEqual(recovered['player'], saved['player'])
        self.assertEqual(recovered['opponent'], saved['opponent'])
        self.unchanged()

    async def test_command_and_idle_failures_release_all_timers_and_membership(self):
        for failure in ('command', 'idle'):
            g = self.enter()
            with patch.object(self.store, 'save_training_profile', side_effect=OSError('unavailable')):
                if failure == 'command':
                    with patch.object(g, 'request', side_effect=RuntimeError('handler failed')):
                        self.assertTrue(commands.handle(self.s, 'tg', dict(op='spawn')))
                else:
                    # monotonic() is relative to boot, not the Unix epoch.
                    # A fresh CI host may have been up for less than the TTL.
                    g.last_activity = training.time.monotonic() - training.IDLE_SECONDS - 1
                    g.timer.cancel()  # The scheduled callback is being fired manually.
                    g.idle()
            self.assertTrue(g.closed)
            self.assertIsNone(g.timer)
            self.assertNotIn(g, runtime.ACTIVE)
            self.assertIsNone(self.s.training_ground)
            self.reconnect()

    async def test_idle_deadline_handles_a_recently_booted_host(self):
        g = self.enter()
        g.timer.cancel()
        g.last_activity = 100
        # Keep the virtual clock scoped to these synchronous callbacks.
        with patch.object(training.time, 'monotonic', return_value=110):
            g.idle()
        self.assertFalse(g.closed)
        self.assertIsNotNone(g.timer)
        g.timer.cancel()
        with patch.object(training.time, 'monotonic', return_value=100 + training.IDLE_SECONDS):
            g.idle()
        self.assertTrue(g.closed)
        self.assertIsNone(g.timer)
        self.assertNotIn(g, runtime.ACTIVE)
        self.assertFalse(self.store.training_profile(self.s.char_id)['inside'])
        self.unchanged()

    async def test_local_npc_ids_are_reused_without_touching_global_allocator(self):
        with patch.object(server.ROOMS.ids, 'npc', side_effect=AssertionError('global allocation')):
            g = self.enter()
            ids = []
            for _ in range(4):
                g.start('mob')
                ids.append(g.mob_eid)
                self.assertNotIn(g.mob_eid, g.posts)
                g.target_defeated(g.room.combat.mobs[g.mob_eid])
            self.assertEqual(len(set(ids)), 1)
        self.unchanged()

    async def test_relocation_keeps_mob_and_post_ids_disjoint_for_all_participants(self):
        members, _, _ = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        grounds = [member.training_ground for member in members]
        for g in grounds:
            g.clone.cmd_lenter({})
        grounds[0].change_location(59)
        for g in grounds:
            g.clone.cmd_lenter({})
            g.start('mob')
            self.assertNotIn(g.mob_eid, g.posts)
        self.assertNotEqual(grounds[0].mob_eid, grounds[1].mob_eid)
        self.unchanged()

    async def test_private_checkpoint_does_not_capture_another_players_private_items(self):
        members, _, _ = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        foreign = second.clone.inv.create(copies.copy_type(6108), 10)
        first.clone.handle_training('ss_use', dict(obj=inventory.oid_of(foreign), type=2))
        self.assertIsNotNone(second.store.item(foreign['uniq']))
        self.assertFalse(first.clone.inv.rows())
        self.unchanged()

    async def test_entry_requires_protocol_negotiation_before_quest_is_available(self):
        self.s.training_protocol = None
        self.assertFalse(api.entry_available(self.s))
        with self.assertRaises(ValueError):
            api.check_entry(self.s, dict(npc=self.npc))
        self.assertTrue(api.handle(self.s, 'tg', dict(op='hello', version=999)))
        self.assertFalse(api.entry_available(self.s))
        self.assertTrue(api.handle(self.s, 'tg', dict(op='hello', version=1)))
        self.assertTrue(api.entry_available(self.s))
        api.check_entry(self.s, dict(npc=self.npc))
        self.unchanged()

    async def test_unsupported_saved_rules_and_equipment_are_archived_without_erasing_them(self):
        g = self.enter()
        g.exit(notify=False, suspend=True)
        saved = self.store.training_profile(self.s.char_id)
        saved['rules'] = rules.Rules(simulator_formulas=True).as_dict()
        saved['player']['gear'] = {'61000': 1}
        expected = copy.deepcopy(saved['player'])
        self.store.save_training_profile(self.s.char_id, saved)
        with patch.object(formulas, 'available', return_value=False):
            self.assertTrue(training.resume(self.s))
            current = self.store.training_profile(self.s.char_id)
            self.assertEqual(current['unavailable_presets']['player'], expected)
            self.assertEqual(rules.Rules.parse(current['unavailable_rules']), rules.Rules.parse(saved['rules']))
        self.assertFalse(self.s.training_ground.rules.simulator_formulas)
        self.unchanged()

    async def test_incompatible_party_member_prevents_partial_entry(self):
        members, _, _ = self.party_members(2)
        members[1].training_protocol = None
        with self.assertRaises(ValueError):
            training.enter(self.s, dict(npc=self.npc))
        self.assertTrue(all(member.training_ground is None for member in members))
        self.assertFalse(runtime.ACTIVE)
        self.unchanged()

    async def test_party_invites_work_inside_shared_range_and_refuse_cross_mode_waits(self):
        members, parties, group = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        parties.dissolve(group)
        first.clone.handle_training('p_op', dict(op=0, id=second.clone.pid))
        self.assertIn(members[1].char_id, parties.invites)
        second.clone.handle_training('p_op', dict(op=2))
        self.assertIsNotNone(parties.party_of(members[0]))
        self.assertIs(parties.party_of(members[0]), parties.party_of(members[1]))
        parties.dissolve(parties.party_of(members[0]))
        first.exit(notify=False)
        parties.invite(members[0], members[1].pid)
        self.assertNotIn(members[1].char_id, parties.invites)
        parties.invite(members[1], members[0].pid)
        self.assertNotIn(members[0].char_id, parties.invites)
        self.unchanged()

    async def test_readonly_mail_and_clan_events_are_delivered_without_main_item_frames(self):
        self.enter()
        for command in ('lsml', 'gg_struct', 'fellow', 'userMsg'):
            fields = {'id': 42}
            self.assertIs(api.outgoing(self.s, command, fields), fields)
        for command in ('userInfo_Player', 'ss_di_firearm', 'ss_obj_move', 'rp_info'):
            self.assertIsNone(api.outgoing(self.s, command, {'id': 42}))
        self.unchanged()

    async def test_private_slot_lookup_keeps_row_contract_and_skips_bag_materialisation(self):
        g = self.enter()
        row = g.clone.inv.create(copies.copy_type(26075), slot=inventory.PRIMARY)
        with patch.object(g.clone.inv, 'rows', side_effect=AssertionError('whole bag read')):
            selected = g.clone.inv.in_slot(inventory.PRIMARY)
            self.assertEqual(selected['uniq'], row['uniq'])
            self.assertIsInstance(selected, dict)
            self.assertIsNone(g.clone.inv.in_slot(inventory.SECONDARY))
        self.unchanged()

    async def test_free_supply_does_not_write_main_database_on_each_item(self):
        g = self.enter()
        fixtures.TrainingGround.approach_shop(self, g, 'supplies')
        saved = self.store.training_profile(self.s.char_id)
        with patch.object(self.store, 'save_training_profile', side_effect=AssertionError('unnecessary main write')):
            for sequence in range(1, 4):
                g.last_request = 0
                g.request(dict(op='supply_get', token=g.token, source=6108, count=1, sequence=sequence))
        self.assertEqual(sum(row['count'] for row in g.clone.inv.rows()), 3)
        self.assertEqual(saved, self.store.training_profile(self.s.char_id))
        self.unchanged()

    async def test_failed_recipient_does_not_close_healthy_shared_session(self):
        members, _, _ = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for g in (first, second):
            g.clone.cmd_lenter({})
        with patch.object(second.clone, 'send', side_effect=BrokenPipeError('lost peer')):
            first.room.broadcast(('userMsg', {'id': first.clone.pid}))
            self.assertFalse(second.closed)
            await asyncio.sleep(0)
        self.assertTrue(second.closed)
        self.assertFalse(first.closed)
        self.assertIs(members[0].training_ground, first)
        self.assertIsNotNone(first.clone.inv.create(copies.copy_type(6108), 1))


class ProfileAndContent(unittest.TestCase):
    def test_type_ids_do_not_depend_on_catalogue_order_or_subset(self):
        sources = [26075, 6108, 6055]
        first = copies.registered_ids(sources, items.catalogue())
        self.assertEqual(first, copies.registered_ids(reversed(sources), items.catalogue()))
        self.assertEqual(first[6108], copies.registered_ids([6108], items.catalogue())[6108])
        registry = json.loads((copies.PATH.parent / 'training_item_ids.json').read_text(encoding='utf-8'))
        other = next(t for t in items.catalogue() if str(t) not in registry['baseline'])
        with self.assertRaises(ValueError):
            copies.registered_ids([*sources, other], items.catalogue())

    def test_unavailable_personal_profile_survives_roundtrip_but_is_not_selectable(self):
        raw = dict(key='user-0123456789abcdef', title='Saved test', base='simulator-v99',
                   values=rules.Rules(simulator_formulas=True).values())
        loaded = profiles.load_personal([raw])
        self.assertEqual(profiles.dump_personal(loaded), [raw])
        payload = profiles.payload(profiles.catalogue()[0].rules, loaded)
        self.assertEqual(len(payload['profile_keys']), len(profiles.catalogue()))
        with self.assertRaises(ValueError):
            profiles.resolve(raw['values'], raw['key'], loaded)

    def test_reviewed_content_exists_without_simulator_snapshot(self):
        try:
            with patch.object(formulas, '_ENGINE', None):
                profiles._catalogue.cache_clear()
                self.assertFalse(formulas.available())
                content.validate()
                self.assertEqual([profile.key for profile in profiles.catalogue()], ['baseline-v1'])
        finally:
            profiles._catalogue.cache_clear()


if __name__ == '__main__':
    run_cases(Recovery, ProfileAndContent)
