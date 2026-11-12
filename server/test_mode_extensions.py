"""Optional mode hooks preserve ordinary combat, catalogues and storage."""
import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import accounts
import battle_medicine
import combat
import inventory
import items
import item_templates
import names
import mode_extensions
import sets
import shop_bands
import storage
from testkit import run_cases, healing_fixture, start_healing, attack_fixture


class Templates(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(item_templates._FRAMES, {}, clear=True))
        self.enterContext(patch.dict(item_templates._SOURCES, {}, clear=True))
        self.enterContext(patch.object(item_templates, '_EFFECTS', frozenset()))
        self.enterContext(patch.object(item_templates, '_SEALED', False))
        self.enterContext(patch.object(names, '_SEALED', False))
        self.enterContext(patch.object(names, '_DOCUMENT', None))
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
        self.assertTrue(items.acquisition_blocked(self.target))
        self.assertFalse(items.acquisition_blocked(self.source))
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
        self.enterContext(patch.object(sets, '_SEALED', False))
        self.enterContext(patch.object(names, '_SEALED', False))
        self.enterContext(patch.object(names, '_DOCUMENT', None))
        self.enterContext(patch.dict(names.ALL))
        for table in (sets._EXTRA_SETS, sets._EXTRA_SET_OF, sets._EXTRA_ITEMS):
            self.enterContext(patch.dict(table, {}, clear=True))

    def document(self):
        return {'sets': {'99000': dict(name='Extra set', variant='P', res=12,
            members={'helm': {'type': 65530, 'armor_class': 10}, 'shirt': {'type': 65531}},
            bonus={'2': {'hp': 3}})}}

    def test_extra_set_has_its_own_members_and_does_not_alter_base(self):
        original = copy.deepcopy(sets.SETS)
        sets.register(self.document(), variants=sets.VARIANTS + ("P",))
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
            sets.register(doc, variants=sets.VARIANTS + ("P",))
        self.assertEqual(sets._EXTRA_SETS, {})
        doc = self.document()
        doc['sets']['99000']['members']['helm']['type'] = next(iter(sets.SET_OF))
        with self.assertRaises(ValueError):
            sets.register(doc, variants=sets.VARIANTS + ("P",))
        self.assertEqual(sets._EXTRA_SET_OF, {})
        with self.assertRaises(ValueError):
            sets.parse(self.document())


class Strings(unittest.TestCase):
    def test_registration_is_before_preload_and_rejects_conflicting_batch(self):
        with patch.dict(names.ALL, {1: 'Existing'}, clear=True), \
                patch.object(names, '_DOCUMENT', None), patch.object(names, '_SEALED', False), patch.object(names, '_BLOB', None), \
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
        result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


class HealingHooks(unittest.IsolatedAsyncioTestCase):
    async def test_weapon_hook_changes_only_the_prepared_attack(self):
        f, ch, room, used, events, row = attack_fixture()
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
        f, ch, room, consumed = healing_fixture(6055)
        room.ws = True
        f.healing_spec = lambda vitals: combat.SPEC_FIRST_AID
        f.healing_multiplier = lambda character: 2
        f.medicine_cooldown_seconds = lambda: 2
        with patch.object(combat, 'now', return_value=100), \
                patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: lo):
            args = start_healing(f)
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


class HookFailures(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_weapon_hook_preserves_existing_action_and_never_acknowledges_success(self):
        for invalid in ('exception', 'shots', 'nan', 'bounds', 'fraction'):
            f,ch,room,used,events,row = attack_fixture()
            combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
            previous = f.healing
            events.clear()
            def prepare(weapon, ammo, row):
                if invalid == 'exception':
                    raise ValueError('bad mode')
                return weapon._replace(**{'shots':dict(num_shots=weapon.num_shots+1),
                    'nan':dict(cone=float('nan')), 'bounds':dict(dmin=100,dmax=1),
                    'fraction':dict(dmin=1.5)}[invalid])
            f.prepare_weapon=prepare
            try:
                with self.assertRaises(ValueError):
                    combat.Fighter.use_fire(f,dict(obj='weapon',target='000000001'))
                self.assertIs(f.healing,previous)
                self.assertFalse(room.ws)
                self.assertEqual((f.ap,row['ammo_count'],used),(100,10,[]))
                self.assertFalse(events)
            finally:
                combat.Fighter.cancel_timers(f)

    async def test_melee_hook_prepares_blade_and_fist_before_action_acceptance(self):
        for bare in (False,True):
            f,ch,room,used,events,row=attack_fixture(6241)
            seen=[]
            f.prepare_melee=lambda bounds,item: seen.append(item) or (77,88)
            combat.Fighter.use_fire(f,dict(obj='0' if bare else 'weapon',target='000000001'))
            try:
                self.assertEqual(seen,[None if bare else row])
                if f.strike is not None:
                    f.strike._callback(*f.strike._args)
                args=next(args for name,args in events if name=='resolved_strike')
                self.assertEqual(args[2],(77,88))
            finally:
                combat.Fighter.cancel_timers(f)

    async def test_invalid_healing_hook_cannot_consume_or_change_health_ap_deadline(self):
        for invalid in (0,-1,float('nan'),float('inf'),5,True,None):
            f,ch,room,used=healing_fixture(6055)
            room.ws=True
            f.medicine_cooldown_seconds=lambda:invalid
            before=(ch.hp,ch.sp,f.ap)
            with self.assertRaises(ValueError):
                combat.Fighter.heal_now(f,1,f,None,8)
            self.assertEqual((ch.hp,ch.sp,f.ap),before)
            self.assertEqual(used,[])
            self.assertFalse(hasattr(f.store,'_battle_medicine_deadlines'))
        for kind in ('spec','multiplier'):
            f,ch,room,used=healing_fixture(6055)
            before=(ch.hp,ch.sp,f.ap)
            if kind=='spec':f.healing_spec=lambda v:100
            else:f.healing_multiplier=lambda ch:float('nan')
            with self.assertRaises(ValueError):combat.Fighter.heal_now(f,1,f,None,0)
            self.assertEqual((ch.hp,ch.sp,f.ap),before)
            self.assertEqual(used,[])

    async def test_room_resolution_dispatches_all_policies_for_players_and_mobs(self):
        seen = []
        class Policy(combat.RoomCombat):
            def ranged_critical(self, actor, *args):
                seen.append(('ranged', actor.is_player))
                return True
            def melee_critical(self, actor, *args):
                seen.append(('melee', actor.is_player))
                return True
            def bullet_damage(self, actor, *args):
                seen.append(('bullet', actor.is_player))
                return 11, 22
            def melee_damage(self, actor, *args):
                seen.append(('strike', actor.is_player))
                return 33, 44
        rc = Policy.__new__(Policy)
        rc.room = NS(loc=NS(width=20, height=20), ws=False, broadcast=lambda *a: None)
        rc.bodies = lambda *a: {}
        rc.hit_landed = rc.push_vitals = rc.after_hostile = lambda *a: None
        target = MagicMock(cell=1, is_player=False, hp=1000, eid=2)
        target.sp_now.return_value = 1000
        target.present.return_value = True
        target.dodge_melee.return_value = target.crit_evade_melee.return_value = 0
        target.apply_damage.return_value = False
        weapon = combat.Weapon(1, 10, 10, 0, 10, 20, 0, 0, 25, 0, 0)
        for player in (True, False):
            actor = NS(is_player=player, cell=0)
            with patch.object(combat, 'shot_wall', return_value=None), \
                    patch.object(combat, 'bodies_between', return_value=[]), \
                    patch.object(combat, 'flight', return_value=([], None)), \
                    patch.object(combat, 'bullet_offset', return_value=0):
                pairs, struck = rc.resolve(actor, target, target.cell, weapon, 1)
            self.assertEqual(struck[target][:3], [11, 22, 1])
            self.assertTrue(pairs[0][1][0][3])
        with patch.object(combat, 'roll', return_value=True):
            mob = NS(is_player=False, alive=True, cell=0, eid=3, ap=100,
                     stats=NS(hit=100, crit=100, dmg_min=1, dmg_max=1, attack_ap=5))
            rc.mob_strike(mob, target)
            f, ch, room, used, events, row = attack_fixture()
            f.rc, f.sess.loc = rc, rc.room.loc
            f.hold_stats = f.release_stats = f.award_xp = lambda *a: None
            combat.Fighter.strike_now(f, target, None, (1, 1), combat.SPEC_FIST, 0)
        self.assertEqual(target.apply_damage.call_args_list[-2:],
                         [unittest.mock.call(33, 44), unittest.mock.call(33, 44)])
        self.assertEqual(seen, [('ranged', True), ('bullet', True),
                               ('ranged', False), ('bullet', False),
                               ('melee', False), ('strike', False),
                               ('melee', True), ('strike', True)])


class Registry(unittest.TestCase):
    def setUp(self):
        for module, names_ in ((item_templates,('_FRAMES','_SOURCES')),
                               (sets,('_EXTRA_SETS','_EXTRA_SET_OF','_EXTRA_ITEMS'))):
            for name in names_:self.enterContext(patch.dict(getattr(module,name),{},clear=True))
            self.enterContext(patch.object(module,'_SEALED',False))
        self.enterContext(patch.object(item_templates,'_EFFECTS',frozenset()))
        self.enterContext(patch.object(names,'_SEALED',False))
        self.enterContext(patch.object(names,'_DOCUMENT',None))
        self.enterContext(patch.object(names,'_BLOB',None))
        self.enterContext(patch.object(names,'_SHA',None))
        self.enterContext(patch.dict(names.ALL))
        inventory.armour_durability_ratio.cache_clear()
        inventory.weapon_durability_ratio.cache_clear()

    def test_atomic_batch_registers_set_member_strings_and_seals_every_registry(self):
        source=next(t for t in sets.SET_OF if items.root_of(t)==items.WEAR)
        command,params=items.static_info(source)
        target=65530
        doc={'sets':{'99000':dict(name='Mode set',variant='V',members={
            'helm':dict(type=target,name='Mode helmet',desc='Mode description')})}}
        mode_extensions.register(frames={target:(command,dict(params,type=target))},sources={target:source},
            set_document=doc,strings={9990001:'Mode text'},catalogue=items.catalogue(),
            commands=items.SI_COMMAND,variants=sets.VARIANTS+('V',))
        for key,text in ((sets.NAME_ID_OFFSET+99000,'Mode set'),
                         (items.STRING_ID_OFFSET+target,'Mode helmet'),
                         (items.DESC_ID_OFFSET+target,'Mode description')):
            self.assertEqual(names.ALL[key],text)
        self.assertTrue(item_templates.contains(target))
        self.assertTrue(items.acquisition_blocked(target))
        self.assertEqual(sets.set_of(target),99000)
        with self.assertRaises(RuntimeError):names.register_strings({9990002:'late'})
        with self.assertRaises(RuntimeError):sets.register({'sets':{}})
        with self.assertRaises(RuntimeError):item_templates.register({}, {},catalogue={},commands={})

    def test_invalid_batches_missing_commands_and_cross_collisions_publish_nothing(self):
        before=dict(names.ALL)
        source=6055;command,params=items.static_info(source)
        common=dict(frames={65530:(command,dict(params,type=65530))},sources={65530:source},
                    catalogue=items.catalogue(),commands=items.SI_COMMAND)
        for bad in ({**common,'commands':{}}, {**common,'set_document':{'sets':{'99000':dict(
                        name='Wrong',members={'helm':{'type':65530}})}}},
                    {**common,'strings':{next(iter(names.ALL)):'conflict'}}):
            with self.assertRaises(ValueError):mode_extensions.register(**bad)
            self.assertEqual(item_templates._FRAMES,{})
            self.assertEqual(sets._EXTRA_SETS,{})
            self.assertEqual(names.ALL,before)
            self.assertFalse(item_templates._SEALED)
        sets.register({'sets':{'99000':dict(name='Extra',members={'helm':{'type':65530}})}})
        with self.assertRaises(ValueError):item_templates.register(common['frames'],common['sources'],
            catalogue=common['catalogue'],commands=common['commands'])

    def test_non_template_variant_has_durability_reference_and_cached_use_freezes_registry(self):
        doc={'sets':{'99000':dict(name='Extra',variant='V',level=10,members={
            'helm':dict(type=65530,armor_class=10,max_break_abs=100)})}}
        sets.register(doc,variants=sets.VARIANTS+('V',))
        self.assertEqual(inventory.armour_durability_ratio(65530,10),1)
        with patch.object(shop_bands, 'wares', return_value={65530: ('sets', 10, 'extra', 0)}):
            self.assertEqual(shop_bands._order(65530), (10, '99000', 0, 'extra'))
        with self.assertRaises(RuntimeError):sets.register({'sets':{}})
        with self.assertRaises(RuntimeError):item_templates.register({}, {},catalogue={},commands={})

    def test_isolated_sqlite_uses_its_dialect_for_cyrillic_search_under_pg_default(self):
        db=storage.SqliteDB(':memory:');self.addCleanup(db.close)
        db.create_schema(accounts.SCHEMA);accounts.migrate(db)
        default=accounts.DB_PATH
        with patch.object(storage,'DB_URL','postgresql://unused'):
            store=accounts.Store(db=db)
            aid,error=store.register('review-search','password');self.assertFalse(error)
            store.create_character(aid,'Ветеран',0,'1')
            self.assertTrue(store.find_characters('ВЕТ'))
            self.assertFalse(storage.using_postgres(db))
            self.assertEqual(storage.lower('c.name',db),'pylower(c.name)')
            with self.assertRaises(ValueError):accounts.Store('unexpected',db=db)
        with patch.object(accounts,'connect',return_value=db) as connect:
            accounts.Store('isolated.sqlite');connect.assert_called_once_with('isolated.sqlite')
        self.assertEqual(accounts.DB_PATH,default)


if __name__ == '__main__':
    run_cases(Templates, SetExtensions, Strings, CombatDefaults, HealingHooks, HookFailures, Registry)
