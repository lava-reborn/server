"""Declared armour levels, client warnings and gear-independent combat XP."""
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import inventory
import items
import progression
import sets
import shop_bands
from testkit import run_cases

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'data'))
import set_release_rules
import widescreen
from avm_test import execute


class ReleaseSets(unittest.TestCase):
    def test_armour_stocks_fit_client_and_keep_complete_pairs(self):
        # The temporary release ceiling leaves the level-16 and level-17
        # complete A/G pairs; higher sets remain in the catalogue only.
        pieces = set(sets.ITEMS)
        marat = items.stock_for(1219, 126)
        self.assertEqual(len(marat), 10)
        self.assertFalse(pieces.intersection(marat))
        expected = {t for t, ware in shop_bands.wares().items()
                    if ware[0] == 'sets' and 16 <= ware[1] <= 17}
        for trader, loc in ((1223, 126), (5161, 467)):
            stock = items.stock_for(trader, loc)
            self.assertEqual(set(stock), expected)
            self.assertEqual(len(stock), 20)
            self.assertLessEqual(len(stock), 64)
            for start in range(0, len(stock), 10):
                a, g = stock[start:start + 5], stock[start + 5:start + 10]
                self.assertTrue(all(sets.variant_of(t) == 'A' for t in a))
                self.assertTrue(all(sets.variant_of(t) == 'G' for t in g))
                self.assertEqual(sets.SETS[sets.set_of(a[0])]['family'],
                                 sets.SETS[sets.set_of(g[0])]['family'])

    def test_stock_order_uses_family_even_when_gold_display_name_changes(self):
        before = shop_bands.goods(('sets',), 16, 20)
        gold = sets.SETS[60005]
        with patch.dict(gold, name='AAA renamed gold set'):
            self.assertEqual(shop_bands.goods(('sets',), 16, 20), before)

    def test_declared_levels_remain_without_equipment_level_gate(self):
        for sid, level in ((11002, 17), (11004, 17), (11125, 18), (60005, 18),
                           (10961, 16), (10965, 16)):
            for t in sets.SETS[sid]['members'].values():
                self.assertEqual(inventory.item_level(t), level)
                row = dict(root=items.WEAR, type_id=t)
                for best in (progression.MELEE, progression.SHOOTING, progression.MEDICINE):
                    ch = progression.Character()
                    ch.skill[best][0] = level
                    ch.recalc()
                    self.assertTrue(inventory.wearable(row, ch.level, ch))
                    p = items.static_info(t)[1]
                    needed = inventory.unpacked(p.get('need_attribs_m'),
                                                p.get('need_attribs'), progression.ATTRIBS)
                    for i, value in enumerate(needed):
                        self.assertLessEqual(value, ch.attr(i), (sid, t, i))
                    ch.skill[best][0] = level - 1
                    ch.bonus_skills[best] = 5
                    self.assertTrue(inventory.wearable(row, ch.level, ch))

    def test_red_echo_has_no_shooting_bonus(self):
        for sid in (10961, 10965):
            for bonus in sets.SETS[sid]['bonus'].values():
                self.assertEqual(bonus['skills'][progression.SHOOTING], 0)

    def test_generation_corrections_are_idempotent(self):
        doc = json.loads((ROOT / 'data/sets.json').read_text(encoding='utf-8'))
        before = json.dumps(doc, sort_keys=True)
        set_release_rules.apply(doc['sets'])
        self.assertEqual(json.dumps(doc, sort_keys=True), before)

    def test_client_armour_has_no_level_warning(self):
        target = dict(currDDOperation=dict(fromItem=dict(rootID=items.WEAR)),
                      __armorSkillsOrig=lambda a, titles: 'weapon requirements')
        for level, allowed in ((0, True), (16, True), (17, True), (18, True)):
            env = dict(this=target, arr=[None, 17], titleArr=[],
                       lol=dict(core=dict(Master=dict(getInstance=lambda:
                           dict(gamer=dict(attributes=dict(skillArray=[
                               dict(value=level, level=level + 2),
                               dict(value=16, level=18)])))))))
            result = execute(widescreen.fn_armor_skills().assemble(), env)
            self.assertEqual(result == '', allowed)
        target['currDDOperation']['fromItem']['rootID'] = items.HEAL
        self.assertEqual(execute(widescreen.fn_armor_skills().assemble(), env),
                         'weapon requirements')

    def test_weapon_warning_uses_base_combat_skill_and_preserves_noncombat_warnings(self):
        skills=[dict(value=0,level=100),dict(value=16,level=100),dict(value=0,level=5)]
        target=dict(currDDOperation=dict(fromItem=dict(rootID=items.FIRE_ARM)),
                    __armorSkillsOrig=lambda a,t: 'unchanged')
        attributes=dict(skillArray=skills)
        master=dict(getInstance=lambda: dict(gamer=dict(attributes=attributes)))
        env=dict(this=target,arr=[None,17,3],titleArr=['Melee','Shooting','Medicine'],
                 lol=dict(core=dict(Master=master)))
        code=widescreen.fn_armor_skills().assemble()
        self.assertEqual(execute(code,env),'<b>Shooting не ниже 17</b>\r')
        skills[1]['value']=17
        self.assertEqual(execute(code,env),'')
        target['currDDOperation']['fromItem']['rootID']=items.COLD_ARM
        env['arr']=[6]
        self.assertEqual(execute(code,env),'<b>Melee не ниже 6</b>\r')
        target['currDDOperation']['fromItem']['rootID']=items.WEAR
        self.assertEqual(execute(code,env),'')

    def test_combat_xp_ignores_gear_skill_bonus(self):
        for skill in (progression.MELEE, progression.SHOOTING):
            values = []
            for bonus in (0, 2, 5):
                ch = progression.Character()
                ch.skill[skill][0] = 16
                ch.bonus_skills[skill] = bonus
                ch.gain_xp = Mock(return_value=dict(attribs=set(), skills=set(), specs=set()))
                f = NS(character=lambda: ch)
                target = NS(level=17, stats=NS(role='mob', xp_mult=1))
                combat.Fighter.credit_xp(f, skill, None, 1.0, target)
                values.append(ch.gain_xp.call_args.args[1])
            self.assertEqual(values, [progression.mob_xp(17, 16)] * 3)


if __name__ == '__main__':
    run_cases(ReleaseSets)
