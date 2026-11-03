"""Abu-Hamed independent loot chances, quest diamond and real weapon frames."""
import ast
import logging
import os
from pathlib import Path
import random
from types import SimpleNamespace as NS
import unittest

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import inventory
import items
import mobs
import world
from testkit import run_cases

CHANCES = {2258: 1, 3159: .25, 6953: .05, 6946: .1}


class AbuHamedMinerLoot(unittest.TestCase):
    def test_other_miners_have_the_approved_region_sand_chances(self):
        for kind, chance in ((836,.25),(837,.25),(838,.75),(839,.75),(840,1),(841,1)):
            table = dict((t,p) for t,p,v in mobs.loot_table(kind))
            self.assertEqual(table[2258], chance)
            self.assertIn(2258, mobs.independent_loot(kind))

    def test_chances_and_exact_boundaries(self):
        for kind in (930, 931):
            table = mobs.loot_table(kind)
            self.assertEqual(next(p for t,p,v in table if t == 2258), 1)
            self.assertIn(6959, [t for t,p,v in table])
            for target,chance,_ in table:
                if chance >= 1:
                    continue
                for value, expected in ((chance-.000001,True),(chance,False)):
                    rolls = iter(value if t == target else 1. for t,p,v in table if p<1)
                    drops = mobs.roll_table(kind, NS(random=lambda:next(rolls)))
                    self.assertEqual(any(t==target for t,n in drops),expected)

    def test_only_sand_is_outside_the_random_loot_cap(self):
        for kind in (838,839,840,841,930,931):
            self.assertEqual(mobs.independent_loot(kind),frozenset({2258}))
            drops=mobs.roll_table(kind,NS(random=lambda:0))
            self.assertIn((2258,1),drops)
            self.assertEqual(len([t for t,n in drops if t!=2258]),mobs.MAX_DROPS)

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

    def test_quest_diamond_is_preserved_and_saleable_diamond_has_an_independent_source(self):
        for kind in (930, 931):
            self.assertIn((5545, .1), mobs.quest_table(kind))
            for wanted in ((), (5545,)):
                # Include carried junk and ammunition: no alternative drop
                # path may reintroduce the removed saleable diamond.
                rng = random.Random(1)
                rng.random = lambda: 0
                drops = mobs.loot_for(mobs.stats(kind), rng, wanted)
                self.assertEqual(any(t == 5545 for t, _ in drops), bool(wanted))
                # Force the quest's own boundary, independently of junk RNG.
                quest_drops = mobs.quest_roll(kind, wanted, NS(random=lambda: 0))
                self.assertEqual(any(t == 5545 for t, _ in quest_drops), bool(wanted))
                self.assertNotIn(6959, [t for t, _ in quest_drops])
            table=mobs.loot_table(kind)
            rolls=iter(0 if t==6959 else 1 for t,p,v in table if p<1)
            self.assertIn((6959,1),mobs.roll_table(kind,NS(random=lambda:next(rolls))))
            for value, expected in ((.099999, True), (.1, False)):
                drops = mobs.quest_roll(kind, (5545,), NS(random=lambda: value))
                self.assertEqual(any(t == 5545 for t, _ in drops), expected)
        self.assertEqual(items.params_of(6959)['cost'], 3000)
        self.assertFalse(items.out_of_game(6959))


if __name__ == '__main__':
    run_cases(AbuHamedMinerLoot)
