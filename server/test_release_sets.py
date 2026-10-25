"""Declared armour levels, client warnings and gear-independent combat XP."""
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import inventory
import items
import progression
import sets
from testkit import run_cases

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'data'))
import set_release_rules
import widescreen
from avm_test import execute


class ReleaseSets(unittest.TestCase):
    def test_declared_levels_use_highest_base_skill(self):
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
                    self.assertFalse(inventory.wearable(row, ch.level, ch))

    def test_red_echo_has_no_shooting_bonus(self):
        for sid in (10961, 10965):
            for bonus in sets.SETS[sid]['bonus'].values():
                self.assertEqual(bonus['skills'][progression.SHOOTING], 0)

    def test_generation_corrections_are_idempotent(self):
        doc = json.loads((ROOT / 'data/sets.json').read_text(encoding='utf-8'))
        before = json.dumps(doc, sort_keys=True)
        set_release_rules.apply(doc['sets'])
        self.assertEqual(json.dumps(doc, sort_keys=True), before)

    def test_client_armour_warning_uses_best_skill(self):
        target = dict(currDDOperation=dict(fromItem=dict(rootID=items.WEAR)),
                      __armorSkillsOrig=lambda a, titles: 'weapon requirements')
        for level, allowed in ((16, False), (17, True), (18, True)):
            env = dict(this=target, arr=[None, 17], titleArr=[],
                       lol=dict(core=dict(Master=dict(getInstance=lambda:
                           dict(gamer=dict(attributes=dict(skillArray=[
                               dict(value=level, level=level + 2),
                               dict(value=16, level=18)])))))))
            result = execute(widescreen.fn_armor_skills().assemble(), env)
            self.assertEqual(result == '', allowed)
        target['currDDOperation']['fromItem']['rootID'] = items.FIRE_ARM
        self.assertEqual(execute(widescreen.fn_armor_skills().assemble(), env),
                         'weapon requirements')

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
