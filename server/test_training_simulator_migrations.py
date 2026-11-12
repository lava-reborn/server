"""Stable engine/copy identities and lossless persisted profile upgrades."""
import copy
import json
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import items
from training import items as copies, profiles, rules, session
from training.engines import simulator_v1 as engine
import test_training_ground as fixtures


class SimulatorMigrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        session.preload()

    def test_snapshot_commit_does_not_change_engine_or_personal_identity(self):
        base = profiles.catalogue()[1]
        record = profiles.personal_record('user-0123456789abcdef', 'My test',
                                         replace(base.rules, health=2, spread=.5))
        stored = profiles.dump_personal([record])
        changed = dict(engine.data(), source_commit='a' * 40)
        try:
            with patch.object(engine, 'data', return_value=changed):
                profiles.catalogue.cache_clear()
                rules.simulator_notes.cache_clear()
                self.assertEqual(profiles.catalogue()[1].key, 'simulator-v1')
                loaded = profiles.load_personal(stored)
                self.assertEqual(profiles.dump_personal(loaded), stored)
                self.assertEqual(loaded[0].rules.health, 2)
                self.assertEqual(loaded[0].rules.spread, .5)
        finally:
            profiles.catalogue.cache_clear()
            rules.simulator_notes.cache_clear()

    def test_legacy_commit_keys_migrate_only_when_loading_owned_records(self):
        values = replace(profiles.catalogue()[1].rules, armour=2).values()
        for commit in ('6b7b28d', '1234567', 'f' * 40):
            raw = dict(key='user-0123456789abcdef', title='Saved',
                       base='simulator-' + commit, values=values)
            record, = profiles.load_personal([raw])
            self.assertIsNone(record.saved)
            self.assertEqual(record.rules.armour, 2)
            self.assertEqual(profiles.dump_personal([record])[0], dict(raw, base=engine.KEY))
            with self.assertRaises(ValueError):
                profiles.resolve(values, raw['base'])  # Stale live command is rejected.

    def test_unknown_or_inconsistent_engine_is_archived_without_reinterpretation(self):
        for base, values in (('simulator-v99', profiles.catalogue()[1].rules.values()),
                             ('simulator-1234567', profiles.catalogue()[0].rules.values())):
            raw = dict(key='user-0123456789abcdef', title='Saved', base=base, values=values)
            loaded = profiles.load_personal([raw])
            self.assertEqual(profiles.dump_personal(loaded), [raw])
            self.assertIsNotNone(loaded[0].saved)
            payload = profiles.payload(profiles.catalogue()[0].rules, loaded)
            self.assertNotIn(raw['key'], payload['profile_keys'])

    def test_copy_ids_are_independent_of_order_and_removed_equipment(self):
        sources = tuple(copies.PROFILE_SOURCES.values())[:3]
        self.assertEqual(len(sources), 3)
        original = copies.registered_ids(sources, items.catalogue(), 'simulator')
        self.assertEqual(original, copies.registered_ids(reversed(sources), items.catalogue(), 'simulator'))
        self.assertEqual(copies.registered_ids(sources[1:], items.catalogue(), 'simulator'),
                         {key: original[key] for key in sources[1:]})
        self.assertTrue(set(original.values()).isdisjoint(copies.COPIES.values()))

    def test_cross_namespace_collision_is_rejected_before_publication(self):
        raw = json.loads(copies.PATH.with_name('training_item_ids.json').read_text(encoding='utf-8'))
        raw['simulator'][next(iter(raw['simulator']))] = next(iter(raw['baseline'].values()))
        before = dict(copies.FRAMES)
        with patch.object(copies.json, 'loads', return_value=raw), self.assertRaises(ValueError):
            copies.registered_ids([], items.catalogue(), 'simulator')
        self.assertEqual(copies.FRAMES, before)

    def test_equation_drift_is_rejected_before_use(self):
        raw = copy.deepcopy(engine.data())
        raw['equations']['INT_DAMAGE'] *= 2
        try:
            with patch.object(engine, 'PATH', SimpleNamespace(read_text=lambda **kwargs: json.dumps(raw))):
                engine.data.cache_clear()
                with self.assertRaisesRegex(ValueError, 'equations changed'):
                    engine.data()
        finally:
            engine.data.cache_clear()

    def test_profile_fields_cannot_override_prices_or_transfer_policy(self):
        forbidden = {'cost', 'g_cost', 'sell_mod', 'premium', 'exchang', 'type', 'comp_array'}
        self.assertTrue(all(forbidden.isdisjoint(fields) for fields in engine.data()['equipment'].values()))


class SavedSimulatorSession(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged

    async def test_legacy_saved_session_and_personal_rules_survive_resume(self):
        ground = self.enter()
        ground.exit(notify=False, suspend=True)
        saved = self.store.training_profile(self.s.char_id)
        old = replace(profiles.catalogue()[1].rules, revision='simulator-1234567', health=2)
        saved['rules'] = old.as_dict()
        raw = dict(key='user-0123456789abcdef', title='Saved', base=old.revision, values=old.values())
        saved['personal_rules'] = [raw]
        self.store.save_training_profile(self.s.char_id, saved)
        self.assertTrue(session.resume(self.s))
        restored = self.s.training_ground
        self.assertEqual(restored.rules.revision, engine.KEY)
        self.assertEqual(restored.rules.health, 2)
        self.assertEqual(profiles.dump_personal(restored.personal_profiles)[0], dict(raw, base=engine.KEY))
        restored.save_settings()
        current = self.store.training_profile(self.s.char_id)
        self.assertEqual(current['rules']['revision'], engine.KEY)
        self.assertEqual(current['personal_rules'][0]['base'], engine.KEY)
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(SimulatorMigrations, SavedSimulatorSession)
