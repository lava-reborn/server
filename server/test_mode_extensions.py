"""Optional mode hooks preserve ordinary combat, catalogues and storage."""
import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import accounts
import battle_medicine
import combat
import inventory
import items
import item_templates
import names
import sets
import storage
from test_healing_completion import HealingCompletion
from test_action_order import ActionOrder
from testkit import run_cases


class Templates(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(item_templates._FRAMES, {}, clear=True))
        self.enterContext(patch.dict(item_templates._SOURCES, {}, clear=True))
        self.enterContext(patch.object(item_templates, '_EFFECTS', frozenset()))
        self.source = 6055
        self.target = next(t for t in range(65535, 54000, -1) if t not in items.catalogue())
        command, params = items.static_info(self.source)
        self.frames = {self.target: (command, dict(params, type=self.target))}

    def register(self, frames=None, sources=None, **kw):
        item_templates.register(self.frames if frames is None else frames,
                                {self.target: self.source} if sources is None else sources,
                                catalogue=items.catalogue(), commands=items.SI_COMMAND, **kw)

    def test_extra_template_is_independent_and_does_not_replace_source(self):
        before = items.static_info(self.source)
        self.register()
        self.frames[self.target][1]['heal_cost'] = 999
        self.assertEqual(items.static_info(self.source), before)
        self.assertEqual(items.root_of(self.target), items.HEAL)
        self.assertEqual(items.battle_medicine(self.target), items.battle_medicine(self.source))
        self.assertEqual(items.no_combat(self.target), items.no_combat(self.source))
        info = items.static_info(self.target)
        info[1]['heal_cost'] = 888
        self.assertEqual(items.params_of(self.target)['heal_cost'], before[1]['heal_cost'])
        self.assertNotIn(self.target, items.catalogue())

    def test_bad_batch_and_collisions_publish_nothing(self):
        for frames, sources in (
                (self.frames, {}),
                ({self.source: self.frames[self.target]}, {self.source: self.source}),
                (self.frames, {self.target: self.target}),
                ({self.target: ('wrong_command', self.frames[self.target][1])}, {self.target: self.source}),
                ({self.target: (self.frames[self.target][0], dict(type=42))}, {self.target: self.source})):
            with self.subTest(frames=frames):
                with self.assertRaises(ValueError):
                    self.register(frames, sources)
                self.assertEqual(item_templates._SOURCES, {})
                self.assertEqual(item_templates._FRAMES, {})
        self.register()
        with self.assertRaises(ValueError):
            self.register()

    def test_private_template_is_rejected_before_any_inventory_write(self):
        self.register()
        inv = inventory.Inventory.__new__(inventory.Inventory)
        inv.store = NS(create_item=lambda *args, **kw: self.fail('unexpected write'))
        with self.assertRaisesRegex(ValueError, 'Private equipment'):
            inv.create(self.target)
        inventory.Inventory.validate_creation(inv, 6092)

    def test_effect_support_is_explicit_and_cannot_enable_real_stimulants(self):
        source = next(t for t, (root, _) in items.catalogue().items()
                      if root == items.HEAL and items.stimulant_unavailable(t))
        command, params = items.static_info(source)
        frames = {self.target: (command, dict(params, type=self.target))}
        self.register(frames, {self.target: source}, effects=[self.target])
        self.assertFalse(items.stimulant_unavailable(self.target))
        self.assertTrue(items.stimulant_unavailable(source))


class SetExtensions(unittest.TestCase):
    def setUp(self):
        for table in (sets._EXTRA_SETS, sets._EXTRA_SET_OF, sets._EXTRA_ITEMS):
            self.enterContext(patch.dict(table, {}, clear=True))

    def document(self):
        return {'sets': {'99000': dict(name='Extra set', variant='P', res=12,
            members={'helm': {'type': 65530, 'armor_class': 10}, 'shirt': {'type': 65531}},
            bonus={'2': {'hp': 3}})}}

    def test_extra_set_has_its_own_members_and_does_not_alter_base(self):
        original = copy.deepcopy(sets.SETS)
        sets.register(self.document())
        self.assertEqual(sets.set_of(65530), 99000)
        self.assertEqual(sets.slot_of(65530), 'helm')
        self.assertEqual(sets.variant_of(65530), 'P')
        self.assertEqual(sets.item(65530)['armor_class'], 10)
        self.assertEqual(sets.frame(99000)['bonus_2_hp'], 3)
        self.assertEqual(sets.bonuses([65530, 65531])['hp'], 3)
        self.assertEqual(sets.SETS, original)
        self.assertEqual(sets.frame(98999), sets.fallback(98999))

    def test_collision_and_invalid_batch_leave_registry_unchanged(self):
        doc = self.document()
        doc['sets'][str(next(iter(sets.SETS)))] = doc['sets'].pop('99000')
        with self.assertRaises(ValueError):
            sets.register(doc)
        self.assertEqual(sets._EXTRA_SETS, {})
        doc = self.document()
        doc['sets']['99000']['members']['helm']['type'] = next(iter(sets.SET_OF))
        with self.assertRaises(ValueError):
            sets.register(doc)
        self.assertEqual(sets._EXTRA_SET_OF, {})
        with self.assertRaises(ValueError):
            sets.parse(self.document())


class Strings(unittest.TestCase):
    def test_registration_is_before_preload_and_rejects_conflicting_batch(self):
        with patch.dict(names.ALL, {1: 'Existing'}, clear=True), \
                patch.object(names, '_DOCUMENT', None), patch.object(names, '_BLOB', None), \
                patch.object(names, '_SHA', None):
            with self.assertRaises(ValueError):
                names.register_strings({2: 'New', 1: 'Conflict'})
            self.assertEqual(names.ALL, {1: 'Existing'})
            names.register_strings({2: 'New'})
            self.assertTrue(names.known(2))
            self.assertIn(b"<s id='2'>New</s>", names.document_bytes())
            with self.assertRaises(RuntimeError):
                names.register_strings({3: 'Too late'})


class CombatDefaults(unittest.TestCase):
    def test_damage_and_critical_defaults_match_ordinary_functions(self):
        fighter = combat.Fighter.__new__(combat.Fighter)
        room = combat.RoomCombat.__new__(combat.RoomCombat)
        weapon = NS(crit=25, piercing=7)
        target = NS(armor=lambda: 61, crit_evade_ranged=lambda: 3)
        self.assertIs(fighter.prepare_weapon(weapon, {}, {}), weapon)
        self.assertEqual(fighter.prepare_melee((10, 20), None), (10, 20))
        for damage in (0, 1, 55, 200):
            for stamina in (0, 10, 1000):
                for critical in (False, True):
                    self.assertEqual(room.bullet_damage(fighter, target, weapon, damage, 5, critical, stamina),
                                     combat.split_damage(damage, 61, 7, critical, stamina, 5))
                    self.assertEqual(room.melee_damage(fighter, target, damage, critical, stamina),
                                     combat.melee_split(damage, critical, stamina))
        with patch.object(combat, 'roll', return_value=True) as roll:
            self.assertFalse(room.ranged_critical(fighter, target, weapon, False))
            roll.assert_not_called()
            self.assertTrue(room.ranged_critical(fighter, target, weapon, True))
            roll.assert_called_once_with(22)

    def test_isolated_store_uses_its_connection_not_global_backend(self):
        db = storage.SqliteDB(':memory:')
        self.addCleanup(db.close)
        db.create_schema(accounts.SCHEMA)
        accounts.migrate(db)
        with patch.object(accounts, 'connect', side_effect=AssertionError('unexpected connection')), \
                patch.object(storage, 'DB_URL', 'postgresql://unused'):
            store = accounts.Store(db=db)
            self.assertIs(store.db, db)
            self.assertFalse(store.lock_quest_character(-1))

    def test_imports_work_when_training_package_is_forbidden(self):
        code = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('training.') and fullname not in ('training.api', 'training.config'):
            raise AssertionError('feature import: ' + fullname)
sys.meta_path.insert(0, Block())
import accounts, combat, inventory, items, sets, names, server
assert not any(n.startswith('training.') and n not in ('training.api', 'training.config') for n in sys.modules)
import item_templates
assert not item_templates._FRAMES
'''
        env = dict(os.environ, LAVA_DB=':memory:', LAVA_DB_URL='', PYTHONDONTWRITEBYTECODE='1')
        env['PYTHONPATH'] = str(Path(__file__).resolve().parent)
        for flag in ('0', '1'):
            result = subprocess.run([sys.executable, '-B', '-c', code],
                                    env=dict(env, LAVA_TRAINING_GROUND=flag),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


class HealingHooks(unittest.IsolatedAsyncioTestCase):
    async def test_weapon_hook_changes_only_the_prepared_attack(self):
        f, ch, room, used, events, row = ActionOrder().attack_fixture()
        captured = []

        def prepare(weapon, ammo, item):
            captured.append((weapon, ammo, item))
            return weapon._replace(dmin=777, dmax=777)

        f.prepare_weapon = prepare
        before = items.params_of(row['type_id'])
        try:
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
            self.assertEqual(len(captured), 1)
            f.aim._callback(*f.aim._args)
            args = next(args for name, args in events if name == 'resolved_fire')
            self.assertEqual((args[3].dmin, args[3].dmax), (777, 777))
            self.assertEqual(items.params_of(row['type_id']), before)
        finally:
            combat.Fighter.cancel_timers(f)

    async def test_overridden_healing_hooks_are_used_at_completion(self):
        f, ch, room, consumed = HealingCompletion().fixture(6055)
        room.ws = True
        f.healing_spec = lambda vitals: combat.SPEC_FIRST_AID
        f.healing_multiplier = lambda character: 2
        f.medicine_cooldown_seconds = lambda: 2
        with patch.object(combat, 'now', return_value=100), \
                patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: lo):
            args = HealingCompletion().start(f)
            f.heal_now(*args)
        self.assertEqual(consumed, [1])
        self.assertEqual(battle_medicine.remaining_ms(f.store, 1, 100), 2000)
        self.assertGreater(ch.hp, 30)

    async def test_invalid_cooldown_cannot_mutate_deadline_or_schedule_callback(self):
        store = NS()
        for duration in (0, -1, float('nan'), float('inf'), 5):
            with self.assertRaises(ValueError):
                battle_medicine.start(store, 1, 100, duration)
            self.assertFalse(hasattr(store, '_battle_medicine_deadlines'))


if __name__ == '__main__':
    run_cases(Templates, SetExtensions, Strings, CombatDefaults, HealingHooks)
