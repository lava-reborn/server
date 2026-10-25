"""Abu-Hamed independent loot chances, quest diamond and real weapon frames."""
import ast
import logging
import os
from pathlib import Path
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import inventory
import items
import mobs
import world
from testkit import run_cases

CHANCES = {2258: 1, 3159: .25, 6959: .03, 6953: .1, 6946: .1}


class AbuHamedMinerLoot(unittest.TestCase):
    def test_chances_and_exact_boundaries(self):
        for kind in (930, 931):
            table = mobs.loot_table(kind)
            self.assertEqual({t: c for t, c, _ in table if t in CHANCES}, CHANCES)
            self.assertNotIn(6928, [t for t, _, _ in table])
            for target, chance in CHANCES.items():
                if chance == 1:
                    continue
                for value, expected in ((chance - .000001, True), (chance, False)):
                    rolls = iter(value if t == target else 1.0 for t, c, _ in table if c < 1)
                    rng = NS(random=lambda: next(rolls))
                    drops = mobs.roll_table(kind, rng)
                    self.assertEqual(any(t == target for t, _ in drops), expected)
                    self.assertEqual([n for t, n in drops if t == 2258], [1])

    def test_new_drops_cannot_be_lost_to_or_consume_the_cap(self):
        for kind in (930, 931):
            drops = mobs.roll_table(kind, NS(random=lambda: 0))
            self.assertEqual({t for t, _ in drops} & CHANCES.keys(), CHANCES.keys())
            ordinary = [t for t, _ in drops if t not in CHANCES]
            self.assertEqual(len(ordinary), min(mobs.MAX_DROPS,
                len([t for t, c, _ in mobs.loot_table(kind) if t not in CHANCES])))
        for kind in (838, 839, 840, 841):
            self.assertEqual(mobs.independent_loot(kind), frozenset())
            drops = mobs.roll_table(kind, NS(random=lambda: 0))
            sure = {t for t, chance, _ in mobs.loot_table(kind) if chance >= 1}
            self.assertLessEqual(len([t for t, _ in drops if t not in sure]), mobs.MAX_DROPS)

    def test_normal_ammunition_and_generator(self):
        path = Path(__file__).resolve().parents[1] / 'data/build_mob_types.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        designed = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'DESIGNED_KINDS' for t in n.targets))
        for kind, level in ((930, 18), (931, 19)):
            st = mobs.stats(kind)
            self.assertEqual((st.level, st.weapon_type_id, st.weapon_class, st.ranged),
                             (level, 25319, 'assault_rifle', True))
            for k, v in designed[st.name].items():
                self.assertEqual(mobs.TYPES[str(kind)][k], v)
            self.assertIn(6109, items.params_of(25319)['comp_array'])
            for seed in range(10):
                drops = mobs.carried(st, random.Random(seed))
                self.assertEqual(drops[0][0], 6109)
                self.assertTrue(3 <= drops[0][1] <= 10)
        ammo = items.params_of(6109)
        self.assertEqual([ammo[k] for k in ('acc_mod', 'dam_mod', 'st_mod', 'range_mod', 'piercing')], [1]*5)

    def test_actual_weapon_response_uses_standard_rounds(self):
        frames = []
        npc = NS(type_id=930, root=world.MOB)
        sess = NS(room=NS(npcs={123: npc}), send=lambda *cmd, **p: frames.append((cmd[0], p)))
        obj = inventory.oid(mobs.VIRTUAL_BASE + 123, 25319, items.FIRE_ARM)
        self.assertTrue(combat.Fighter.ss_get_di(NS(sess=sess), dict(obj=obj)))
        self.assertEqual(frames[0][1]['ammo_type'], 6109)

    def test_quest_diamond_and_golden_diamond_are_distinct(self):
        for kind in (930, 931):
            for wanted in ((), (5545,)):
                with patch.object(mobs, 'carried', return_value=[]):
                    drops = mobs.loot_for(mobs.stats(kind), NS(random=lambda: 0), wanted)
                self.assertEqual(any(t == 5545 for t, _ in drops), bool(wanted))
                self.assertIn((6959, 1), drops)
        self.assertEqual(items.params_of(6959)['cost'], 3000)
        self.assertFalse(items.out_of_game(6959))


if __name__ == '__main__':
    run_cases(AbuHamedMinerLoot)
