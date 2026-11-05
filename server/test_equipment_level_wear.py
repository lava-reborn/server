"""Level-free equipment, retained specialisations and base-skill equipment wear.

Real SQLite inventories and actual fire/strike completion handlers, no sockets
or production data. Burst trajectory is stubbed; ammunition/AP/wear are real.
"""
import os
import logging
import unittest
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)
import accounts
import combat
import inventory
import items
import progression
import quests
import sets
import setcraft
import craft
from testkit import run_cases


class Fighter(combat.Fighter):
    rc = None


async def resolved(callback, *args):
    return callback(*args)


class LevelWear(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        aid, error = self.store.register('levelwear', 'test-only')
        self.assertIsNone(error)
        cid, _ = self.store.create_character(aid, 'LevelWear', 0, '1')
        self.ch = progression.Character.load(self.store, cid)
        for spec in self.ch.spec:
            spec[0] = 5
        self.frames = []
        self.sess = NS(char_id=cid, pid=1, room=None, loc=NS(war=True),
                       pos=0, character=lambda: self.ch,
                       send=lambda cmd, **p: self.frames.append((cmd, p)), answer=lambda _: None)
        self.inv = self.sess.inv = inventory.Inventory(self.sess, self.store)
        self.f = self.sess.combat = Fighter(self.sess)
        self.f.ap = 100
        self.live = []
        self.f.rc = NS(room=NS(ws=True, broadcast=self.frames.append),
                       within_fire=lambda *a: False,
                       burst=lambda *a, **timing: self.live.append(a[4]) or (0, 0, 0, False))

    def make(self, type_id, slot=inventory.PRIMARY, **extra):
        fields = inventory.new_fields(type_id)
        root = fields.pop('root')
        fields.update(slot=slot, **extra)
        return self.store.create_item(self.sess.char_id, type_id, root, **fields)

    def test_each_difference_and_base_skill_not_bonus_or_character_level(self):
        for type_id, skill, tier in ((7072, progression.SHOOTING, 4),
                                     (6241, progression.MELEE, 6)):
            row = dict(type_id=type_id, root=items.root_of(type_id))
            self.assertEqual(inventory.item_level(type_id), tier)
            for base in range(21):
                self.ch.skill[skill][0] = base
                self.ch.skill[progression.MEDICINE][0] = 20
                self.ch.bonus_skills[skill] = 100
                difference = tier - base
                expected = (inventory.weapon_durability_ratio(type_id, base)
                            * (1.5 + .15 * (difference - 1)) if difference > 0 else 1)
                self.assertAlmostEqual(inventory.wear_multiplier(row, self.ch), expected)
        with patch.object(inventory, 'item_level', return_value=20):
            self.ch.skill[progression.SHOOTING][0] = 0
            ratio = inventory.weapon_durability_ratio(7072, 0)
            self.assertAlmostEqual(inventory.wear_multiplier(dict(root=items.FIRE_ARM,type_id=7072),self.ch), ratio * 4.35)

    def test_penalty_steps_are_additive_and_do_not_affect_on_level_gear(self):
        for difference, expected in ((-2, 1), (0, 1), (1, 1.5), (2, 1.65),
                                     (3, 1.8), (4, 1.95), (5, 2.1)):
            self.assertAlmostEqual(inventory.level_wear_penalty(difference), expected)

    def test_every_set_piece_equalises_life_at_each_lower_base_level(self):
        for current in sets.SETS.values():
            if not 4 <= current['level'] <= 17:
                continue
            for base in range(4, current['level']):
                candidates = [s for s in sets.SETS.values()
                              if s['variant'] == current['variant'] and s['level'] <= base]
                reference = max(candidates, key=lambda s: s['level'])
                penalty = 1.5 + .15 * (current['level'] - base - 1)
                self.ch.skill[progression.SHOOTING][0] = base
                for slot, type_id in current['members'].items():
                    durability = sets.item(type_id)['max_break_abs']
                    expected_life = sets.item(reference['members'][slot])['max_break_abs'] / penalty
                    multiplier = inventory.wear_multiplier(dict(root=items.WEAR, type_id=type_id), self.ch)
                    with self.subTest(set=current['name'], base=base, slot=slot):
                        self.assertAlmostEqual(durability / multiplier, expected_life)

    def test_missing_rung_variant_and_unchanged_on_level_wear(self):
        for variant in ('A', 'G'):
            # Storm-M boots have 1250 points; difference 17-15 => x1.65.
            current = next(s for s in sets.SETS.values() if s['level'] == 17 and s['variant'] == variant)
            t = current['members']['boots']
            self.ch.skill[progression.SHOOTING][0] = 15
            self.assertAlmostEqual(inventory.wear_multiplier(dict(root=items.WEAR, type_id=t), self.ch),
                                   1250 / (950 if variant == 'A' else 750) * 1.65)
            self.ch.skill[progression.SHOOTING][0] = 17
            self.assertEqual(inventory.wear_multiplier(dict(root=items.WEAR, type_id=t), self.ch), 1)

    def test_reworked_armour_keeps_durability_advantage(self):
        mod, (base, _) = next(iter(setcraft.MOD_OF.items()))
        self.assertEqual(inventory.armour_durability_ratio(mod, 4),
                         inventory.armour_durability_ratio(base, 4))

    def test_weapon_reference_ignores_event_and_modified_durabilities(self):
        references = inventory.weapon_wear_references()
        # Ordinary G knife 2: 300; a damage/AP modification has 600 and
        # holiday weapons can have 30000. Neither belongs in the baseline.
        self.assertEqual(references[(items.COLD_ARM, 0, True)][2], 300)
        self.assertNotIn(0, references[(items.COLD_ARM, 0, True)])
        mod, base = next((t, m[0]) for t in items.catalogue()
                         if (m := craft.mod_of(t)) is not None)
        self.assertEqual(inventory.weapon_durability_ratio(mod, 4),
                         inventory.weapon_durability_ratio(base, 4))

    def test_fractional_armour_wear_is_not_truncated_or_banked_in_session(self):
        current = next(s for s in sets.SETS.values() if s['level'] == 13 and s['variant'] == 'A')
        row = self.make(current['members']['helm'], inventory.HEAD, brk=1000)
        self.ch.skill[progression.SHOOTING][0] = 12
        # 1875 / 1750 * 1.5 = 45/28: exactly 45 points over an evenly
        # spaced set of 28 draws. Restarting Inventory needs no remainder.
        with patch.object(inventory.RNG, 'random', side_effect=[(i + .5) / 28 for i in range(28)]):
            for i in range(28):
                if i == 14:
                    self.inv = self.sess.inv = inventory.Inventory(self.sess, self.store)
                row = self.inv.wear(row)
        self.assertEqual(self.store.item(row['uniq'])['brk'], 955)

    def test_normalisation_cache_does_not_read_database_or_rebuild_each_hit(self):
        inventory.weapon_durability_ratio(7072, 2)
        with patch.object(inventory, 'weapon_wear_references', side_effect=AssertionError('rebuilt')):
            self.assertGreater(inventory.weapon_durability_ratio(7072, 2), 0)

    def test_level_zero_can_equip_but_specialisation_level_is_mandatory(self):
        self.ch.spec[1][0] = -1
        row = self.make(6241, inventory.BAG)
        params = dict(obj=inventory.oid_of(row), **{'from': inventory.BAG, 'to': inventory.PRIMARY})
        for trained, wanted in ((-1, inventory.RES_LEVEL), (0, inventory.RES_LEVEL), (1, inventory.RES_OK)):
            self.ch.spec[1][0] = trained
            self.frames.clear()
            self.inv.ss_move(params)
            self.assertEqual([p['res'] for cmd,p in self.frames if cmd=='cmdAck'],[wanted])
        self.assertEqual(self.ch.level, 0)
        self.assertEqual(self.store.item(row['uniq'])['slot'], inventory.PRIMARY)
        self.assertEqual(inventory.item_level(6241), 6)
        self.assertEqual(self.inv.over_level_to_bag(), [])
        self.ch.spec[1][0] = -1
        self.assertEqual(self.inv.over_level_to_bag(), [row['uniq']])

    def test_smuggled_pkm_needs_learned_spec_zero_but_not_shooting_sixteen(self):
        self.ch.skill[progression.SHOOTING][0] = 0
        row = self.make(7051, inventory.BAG)
        params = dict(obj=inventory.oid_of(row),
                      **{'from': inventory.BAG, 'to': inventory.PRIMARY})
        for trained, wanted in ((-1, inventory.RES_LEVEL),
                                (0, inventory.RES_OK)):
            self.ch.spec[6][0] = trained
            self.frames.clear()
            self.inv.ss_move(params)
            self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'],
                             [wanted])
        self.assertEqual(self.ch.level, 0)
        self.assertEqual(inventory.item_level(7051), 16)
        self.ch.spec[6][0] = -1
        error = inventory.weapon_requirement_error(row, self.ch)
        self.assertIn('специализация не изучена', error)
        self.assertNotIn('у вас -1', error)

    def test_ordinary_pkm_keeps_its_learned_zero_requirement(self):
        self.ch.skill[progression.SHOOTING][0] = 0
        row = self.make(24989, inventory.BAG)
        self.ch.spec[6][0] = -1
        self.assertFalse(inventory.wearable(row, 0, self.ch))
        self.ch.spec[6][0] = 0
        self.assertTrue(inventory.wearable(row, 0, self.ch))

    def test_armour_has_no_level_gate_and_scales_wear(self):
        type_id = next(iter(sets.SETS[11002]['members'].values()))
        row = self.make(type_id, inventory.BAG)
        self.assertEqual(inventory.item_level(type_id), 17)
        self.assertTrue(inventory.wearable(row, self.ch.level, self.ch))
        self.assertAlmostEqual(inventory.wear_multiplier(row, self.ch), 19.5)
        before = row['brk']
        with patch.object(inventory.RNG, 'random', return_value=.9):
            self.assertEqual(self.inv.wear(row, 1)['brk'], before-19)

    def test_armour_uses_best_base_combat_skill_not_bonuses_or_noncombat_level(self):
        type_id = next(iter(sets.SETS[11002]['members'].values()))
        row = dict(type_id=type_id, root=items.WEAR)
        self.ch.skill[progression.MEDICINE][0] = 20
        self.ch.bonus_skills[progression.SHOOTING] = 100
        self.ch.bonus_skills[progression.MELEE] = 100
        for shooting in range(21):
            for melee in range(21):
                self.ch.skill[progression.SHOOTING][0] = shooting
                self.ch.skill[progression.MELEE][0] = melee
                base = max(shooting, melee)
                expected = (inventory.armour_durability_ratio(type_id, base)
                            * (1.5 + .15 * (16 - base)) if base < 17 else 1)
                self.assertAlmostEqual(inventory.wear_multiplier(row, self.ch), expected)

    def test_damage_wears_one_armour_piece_once_and_zero_damage_does_not_wear(self):
        types = list(sets.SETS[11002]['members'].values())[:2]
        rows = [self.make(t, inventory.HEAD + items.params_of(t)['slot_type'], brk=100) for t in types]
        self.ch.skill[progression.SHOOTING][0] = 14
        self.ch.skill[progression.MELEE][0] = 15
        with patch.object(inventory.RNG, 'choice', side_effect=lambda worn: worn[0]), \
                patch.object(inventory.RNG, 'random', return_value=.9):
            self.f.apply_damage(1, 0)
        saved = [self.store.item(r['uniq'])['brk'] for r in rows]
        self.assertEqual(sorted(saved), [98, 100])  # nearest lower reference is Legionnaire 14
        self.f.apply_damage(0, 0)
        self.assertEqual([self.store.item(r['uniq'])['brk'] for r in rows], saved)

    def test_armour_wear_clamps_at_zero_refreshes_bonuses_and_preserves_quest_loans(self):
        type_id = next(iter(sets.SETS[11002]['members'].values()))
        row = self.make(type_id, inventory.HEAD + items.params_of(type_id)['slot_type'], brk=5)
        with patch.object(quests, 'lent', return_value=True):
            self.assertEqual(self.inv.wear(row, 1)['brk'], 5)
        with patch.object(self.inv, 'refresh_gear') as refresh:
            self.assertEqual(self.inv.wear(row, 1)['brk'], 0)
        refresh.assert_called_once_with()
        self.assertEqual(self.inv.wear_uniq(row['uniq'], 1)['brk'], 0)

    def test_noncombat_skill_and_all_specialisation_requirements_still_gate_gear(self):
        row = dict(type_id=7072, root=items.FIRE_ARM)
        params = dict(need_skills_m=1<<progression.MEDICINE,need_skills=[3],
                      need_specs_m=1<<3,need_specs=[2])
        self.ch.spec[3][0] = 2
        with patch.object(items,'params_of',return_value=params):
            self.assertFalse(inventory.wearable(row,20,self.ch))
            self.ch.skill[progression.MEDICINE][0] = 3
            self.assertTrue(inventory.wearable(row,0,self.ch))
            self.ch.spec[3][0] = 1
            self.assertFalse(inventory.wearable(row,20,self.ch))

    def test_melee_completion_uses_multiplier_once_and_clamps_at_zero(self):
        row = self.make(6241, brk=5)
        self.ch.skill[progression.MELEE][0] = 1
        self.assertAlmostEqual(inventory.wear_multiplier(row, self.ch), 2.8)
        with patch.object(inventory.RNG, 'random', return_value=0):
            asyncio.run(resolved(self.f.strike_now, None, 0, (1, 1), 1, 8, row['uniq']))
            self.assertEqual((self.store.item(row['uniq'])['brk'], self.f.ap), (2, 92))
            asyncio.run(resolved(self.f.strike_now, None, 0, (1, 1), 1, 8, row['uniq']))
            self.assertEqual((self.store.item(row['uniq'])['brk'], self.f.ap), (0, 84))
            asyncio.run(resolved(self.f.strike_now, None, 0, (1, 1), 1, 8, row['uniq']))
            self.assertEqual((self.store.item(row['uniq'])['brk'], self.f.ap), (0, 84))

    def fire(self,row,rounds=1):
        weapon = combat.Weapon(num_shots=12,dmin=1,dmax=1,opt_lo=0,opt_hi=0,max_range=1,
                               piercing=1,cone=0,crit=0,skill=progression.SHOOTING,spec=3)
        asyncio.run(resolved(self.f.fire_now, row['uniq'],None,0,weapon,31,rounds))

    def test_shotgun_pellets_do_not_multiply_round_wear(self):
        row = self.make(7072, brk=100, ammo_count=6)
        self.ch.skill[progression.SHOOTING][0] = 1
        with patch.object(combat,'WEAR_PER_ROUND',.5), patch.object(combat.WEAR_RNG,'random',return_value=.99):
            self.fire(row)
        saved = self.store.item(row['uniq'])
        self.assertEqual((saved['brk'],saved['ammo_count'],self.f.ap),(99,5,69))
        self.assertEqual(self.live,[12])
        self.assertTrue(any(cmd=='ss_di_firearm' and p['break']==99 for cmd,p in self.frames))

    def test_fractional_fire_wear_scales_before_rounding(self):
        row=self.make(7072,brk=100,ammo_count=6)
        self.ch.skill[progression.SHOOTING][0]=2  # tier 4 vs base 2; equalisation precedes stochastic rounding
        for draw, expected in ((.99,100),(.1,99)):
            self.store.update_item(row['uniq'],brk=100,ammo_count=6)
            self.f.ap=100
            with patch.object(combat,'WEAR_PER_ROUND',.5), patch.object(combat.WEAR_RNG,'random',return_value=draw):
                self.fire(row)
            self.assertEqual(self.store.item(row['uniq'])['brk'],expected)

    def test_short_burst_wears_only_rounds_really_spent_and_loans_do_not_wear(self):
        row = self.make(7072,brk=100,ammo_count=1)
        self.ch.skill[progression.SHOOTING][0] = 1
        with patch.object(combat,'WEAR_PER_ROUND',.5), patch.object(combat.WEAR_RNG,'random',return_value=.99):
            self.fire(row,rounds=3)
        self.assertEqual((self.store.item(row['uniq'])['brk'],self.live),(99,[4]))
        self.store.update_item(row['uniq'],ammo_count=1)
        with patch.object(quests,'lent',return_value=True):
            self.fire(row)
            self.inv.wear_uniq(row['uniq'],10)
        self.assertEqual(self.store.item(row['uniq'])['brk'],99)

    def test_reset_during_aim_never_spends_ammo_wear_or_ap(self):
        type_id=next(t for t,(root,_) in items.catalogue().items()
                     if root==items.FIRE_ARM and inventory.item_level(t)<=17
                     and items.params_of(t).get('need_specs_m'))
        row=self.make(type_id,brk=100,ammo_count=6)
        mask=items.params_of(type_id)['need_specs_m']
        spec=next(i for i in range(progression.SPECS) if mask>>i&1)
        self.ch.spec[spec][0] = -1
        self.fire(row)
        saved=self.store.item(row['uniq'])
        self.assertEqual((saved['brk'],saved['ammo_count'],self.f.ap),(100,6,100))
        self.assertEqual(self.live,[])

    def test_noncombat_training_thresholds_and_hidden_specs_are_not_removed(self):
        gates=list(progression.SPEC_MIN_SKILL)
        gates[8]=3
        self.ch.spec[8][0]=-1
        self.ch.skill[progression.MEDICINE][0]=0
        with patch.object(progression,'SPEC_MIN_SKILL',gates):
            self.assertEqual(self.ch.learn_spec(8),progression.ERR_SKILL)
        self.assertEqual(self.ch.learn_spec(12),progression.ERR_STATE)


if __name__ == '__main__':
    run_cases(LevelWear)
