from training import profiles as installed_profiles
"""Bounded complete kits, exact identities, private replacement and rollback."""
import copy
import time
import unittest
from unittest.mock import patch

import inventory
import items
import progression
from protocol import decode
from training import catalog as range_catalog
from training import character as range_character
from training import supply as range_supply
import sets
from training import session as tg
from training import items as copies
from training import presets as kits
from training import rules as training_rules
import test_training_ground as fixtures


class TrainingPresets(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    approach_shop = fixtures.TrainingGround.approach_shop
    party_members = fixtures.TrainingGround.party_members

    def request(self, g, op, **p):
        g.last_request = g.last_catalogue_request = 0
        g.request(dict(op=op, token=g.token, **p))

    def prepare(self, g, level=12, line='G', wclass=1):
        self.request(g, 'kit_prepare', level=level, line=line, wclass=wclass)
        return g.kit_confirmation[0]

    async def test_every_available_recipe_meets_requirements_and_has_compatible_ammo(self):
        self.enter()
        found = 0
        for simulator in (p.rules.simulator_formulas for p in installed_profiles.catalogue()):
            rules = training_rules.Rules(simulator_formulas=simulator)
            for level in range(1, 21):
                for line in ('A', 'G'):
                    for wclass in range(7):
                        entry = kits.recipe(level, line, wclass, simulator)
                        if not entry:
                            continue
                        found += 1
                        profile = range_character.validate_profile(entry['profile'], rules)
                        self.assertEqual(max(profile['skills']), level)
                        self.assertTrue(all(n <= progression.SPEC_MAX for n in profile['specs']))
                        worn = [t for t in profile['gear'] if items.root_of(t) in inventory.GEAR_ROOTS]
                        self.assertGreaterEqual(len(worn), 6)
                        self.assertTrue(all(range_catalog.item_line(t) == line for t in worn))
                        guns = [t for t in worn if items.root_of(t) == items.FIRE_ARM]
                        for gun in guns:
                            compatible = items.params_of(copies.copy_type(gun, simulator))['comp_array']
                            self.assertTrue(any(copies.copy_type(t, simulator) in compatible
                                                for t in profile['gear'] if items.root_of(t) == items.AMMO))
                        self.assertTrue(any(items.root_of(t) == items.HEAL for t in profile['gear']))
                        medicines=[]
                        for source,count in profile['gear'].items():
                            params=items.params_of(copies.copy_type(source,simulator))
                            if items.root_of(source)==items.AMMO:
                                self.assertEqual(count,800)
                            if items.root_of(source)==items.HEAL:
                                medicines.append(params)
                                self.assertEqual(count,1 if line=='G' else 10)
                                self.assertEqual(params['use_count'],20 if line=='G' else 1)
                        self.assertTrue(any(p.get('max_h_rest',0)>p.get('max_st_rest',0) for p in medicines) if line=='A' else medicines)
                        self.assertTrue(any(p.get('max_st_rest',0)>p.get('max_h_rest',0) for p in medicines))
        self.assertGreater(found, 150 * len(installed_profiles.catalogue()))
        self.unchanged()


    async def test_enemy_sets_use_profile_compatible_ammo_and_a_pouch(self):
        g=self.enter()
        for simulator in (p.rules.simulator_formulas for p in installed_profiles.catalogue()):
            g.rules=training_rules.Rules(simulator_formulas=simulator)
            checked=0
            for record in range_supply.set_catalogue().values():
                if record['variant'] not in ('A','G') or not 1<=record['level']<=20:
                    continue
                if not all(copies.available(t,simulator) for t in record['members'].values()):
                    continue
                key=next(k for k,v in sets.SETS.items() if v['members']==record['members'])
                profile=g.fighter_preset(key)
                slots=range_character.profile_slots(profile)
                self.assertIn(inventory.BELT,slots.values())
                guns=[t for t in profile['gear'] if items.root_of(t)==items.FIRE_ARM]
                self.assertEqual(len(guns),1)
                compatible=items.params_of(copies.copy_type(guns[0],simulator))['comp_array']
                self.assertTrue(any(copies.copy_type(t,simulator) in compatible for t in profile['gear'] if items.root_of(t)==items.AMMO))
                range_character.validate_profile(profile,g.rules)
                checked+=1
            self.assertGreater(checked,10)
        self.unchanged()

    async def test_preview_and_confirmation_are_read_only_then_exact_kit_is_saved(self):
        g = self.enter()
        self.approach_shop(g, 'player')
        old = copy.deepcopy(g.profile)
        self.request(g, 'kit_preview', level=12, line='G', wclass=1, request_id=23)
        packet = decode(self.s.writer.frames[-1][:-1])[1]
        self.assertEqual(packet['request_id'], 23)
        self.assertIn('12 ур.', packet['title'])
        nonce = self.prepare(g)
        self.assertEqual(g.profile, old)
        self.request(g, 'kit_apply', confirmation=nonce)
        expected = kits.recipe(12, 'G', 1, False)['profile']
        self.assertEqual(g.profile, expected)
        actual = {}
        for row in g.clone.inv.rows():
            self.assertTrue(copies.is_copy(row['type_id']))
            source = copies.profile_source(row['type_id'])
            actual[source] = actual.get(source, 0) + (row['count'] if row['root'] in items.HEAPABLE_ROOTS else 1)
        self.assertEqual(actual, expected['gear'])
        self.assertEqual(range_character.validate_profile(self.store.training_profile(self.s.char_id)['player'], g.rules), expected)
        self.assertEqual(g.clone.char.hp, g.clone.char.hp_max)
        self.assertEqual(g.clone.combat.ap, g.clone.char.ap_ceiling)
        with self.assertRaises(ValueError):
            self.request(g, 'kit_apply', confirmation=nonce)
        self.unchanged()

    async def test_failed_private_create_preserves_previous_avatar_and_emits_nothing(self):
        g = self.enter()
        self.approach_shop(g, 'player')
        self.request(g, 'kit_apply', confirmation=self.prepare(g))
        g.clone.training_effects.add(3115)
        nonce = self.prepare(g, level=16)
        old_char, old_profile = g.clone.char, copy.deepcopy(g.profile)
        old_rows = [dict(r) for r in g.clone.inv.rows()]
        saved = self.store.training_profile(self.s.char_id)
        frames = len(self.s.writer.frames)
        with patch.object(g.clone.inv, 'create', side_effect=RuntimeError('failed write')):
            with self.assertRaises(ValueError):
                self.request(g, 'kit_apply', confirmation=nonce)
        self.assertIs(g.clone.char, old_char)
        self.assertEqual(g.profile, old_profile)
        self.assertEqual([dict(r) for r in g.clone.inv.rows()], old_rows)
        self.assertEqual(self.store.training_profile(self.s.char_id), saved)
        self.assertEqual(len(self.s.writer.frames), frames)
        self.assertTrue(g.clone.training_effects.active)
        self.unchanged()

    async def test_confirmation_revalidates_location_fight_rules_expiry_and_inventory(self):
        g = self.enter()
        with self.assertRaises(ValueError):
            self.prepare(g)
        self.approach_shop(g, 'player')
        nonce = self.prepare(g)
        pos = g.clone.pos
        g.clone.pos = 0
        with self.assertRaises(ValueError):
            self.request(g, 'kit_apply', confirmation=nonce)
        g.clone.pos = pos
        with patch.object(g.clone.combat, 'strike', object()):
            with self.assertRaises(ValueError):
                self.request(g, 'kit_apply', confirmation=nonce)
        for kind in ('expired', 'rules', 'inventory'):
            nonce = self.prepare(g)
            if kind == 'expired':
                g.kit_confirmation = (nonce, time.monotonic() - 1, *g.kit_confirmation[2:])
            elif kind == 'rules':
                g.rules = training_rules.Rules(health=2)
            else:
                g.outfit_revision += 1
            with self.assertRaises(ValueError):
                self.request(g, 'kit_apply', confirmation=nonce)
        self.unchanged()

    async def test_other_players_cannot_apply_confirmation_and_are_not_modified(self):
        members, _, _ = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for g in (first, second):
            g.clone.cmd_lenter({})
            self.approach_shop(g, 'player')
        nonce = self.prepare(first)
        profile = copy.deepcopy(second.profile)
        rows = [dict(r) for r in second.clone.inv.rows()]
        with self.assertRaises(ValueError):
            self.request(second, 'kit_apply', confirmation=nonce)
        self.request(first, 'kit_apply', confirmation=nonce)
        self.assertEqual(second.profile, profile)
        self.assertEqual([dict(r) for r in second.clone.inv.rows()], rows)
        self.unchanged()

    async def test_invalid_parameters_never_create_or_change_items(self):
        g = self.enter()
        self.approach_shop(g, 'player')
        for params in (dict(level=40), dict(line='P'), dict(wclass=10), dict(level=0)):
            with self.assertRaises(ValueError):
                self.request(g, 'kit_prepare', **dict(dict(level=12, line='A', wclass=1), **params))
        self.assertFalse(g.clone.inv.rows())
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingPresets)
