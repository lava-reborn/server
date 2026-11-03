"""Type-only economic loot and existing elite fighters; no sockets or live DB."""
import os
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
import collections
import json
import math
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

import bosses
import camp_elites
import inventory
import items
import loot_rules
import mobs
import mortimer
import quests
import rooms
import world

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data'))
import build_camp_patrols as builder


def price(t):
    p = items.params_of(t) or {}
    if (not p.get('cost') or p.get('quest') or t in mortimer.VALUABLES
            or t == mortimer.SAND or t in items.GOLD_INGOTS
            or items.root_of(t) == items.TROPHY):
        return 0
    return max(1, math.floor(p['cost'] / p.get('sell_num', 1)
                            * inventory.SMOD * p.get('sell_mod', 1)))


def expected(k):
    """Independent cap-state calculation, including guaranteed carried loot."""
    st = mobs.stats(k)
    seq = mobs.series(mobs.TRASH_SERIES)
    hi = min(st.level, len(seq) - 1)
    lo = max(0, hi - mobs.JUNK_SPREAD)
    out = collections.defaultdict(float)
    for i in range(lo, hi + 1):
        out[seq[i]] += 1 / (hi - lo + 1)
    si = items.params_of(st.weapon_type_id) if st.weapon_type_id else None
    if si and st.ranged and si.get('comp_array'):
        out[st.loot_ammo_type or si['comp_array'][0]] += sum(st.loot_ammo_count) / 2
    state = [1., 0., 0.]
    independent = mobs.independent_loot(k)
    for t, p, _ in mobs.loot_table(k):
        if p >= 1 or t in independent:
            q = min(p, 1)
        else:
            q = p * sum(state[:2])
            state = [state[0] * (1-p), state[1] * (1-p) + state[0] * p,
                     state[2] + state[1] * p]
        out[t] += q * mobs.count_of(k, t)
    for group in mobs.one_of_groups(k):
        total = sum(w for t, w in group)
        for t, w in group:
            out[t] += w / total
    return dict(out)


def revenue(k):
    loot = expected(k)
    return (175 * sum(price(t) * n for t, n in loot.items()),
            175 * sum(mortimer.unit_gold(t) / 100 * n for t, n in loot.items())
            + loot.get(mortimer.SAND, 0))


class LootRebalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / 'data/loot_rebalance.json').read_text(encoding='utf-8'))
        cls.elites = set(cls.doc['elite_types'])
        cls.manager = rooms.Rooms(world.mob_types())

    def test_overrides_use_real_items_and_only_existing_fighters(self):
        known = world.mob_types()
        for k, rows in loot_rules.records().items():
            self.assertIn(k, known)
            self.assertEqual(mobs.stats(k).role, 'mob')
            seen = set()
            for row in rows:
                self.assertNotIn(row['type'], seen)
                seen.add(row['type'])
                self.assertTrue(mobs.droppable(row['type']))
                self.assertTrue(0 < row['chance'] <= 1)
                self.assertEqual(row['independent'], row['type'] == mortimer.SAND)

    def test_real_patrol_composition_meets_the_income_targets(self):
        for profile in self.doc['targets']:
            counts = {int(k): n for k, n in profile['counts'].items()}
            if profile['context'] == 'Окрестности':
                camp = int(profile['id'].split('-')[1])
                actual = collections.Counter(r['type'] for rows in world.placements().values()
                                              for r in rows if r.get('patrol') == camp)
                self.assertEqual(actual, counts)
                total = sum(counts.values())
                a = sum(revenue(k)[0] * n for k, n in counts.items()) / total
                g = sum(revenue(k)[1] * n for k, n in counts.items()) / total
                self.assertAlmostEqual(a, profile['afro'], delta=1)
                self.assertAlmostEqual(g, profile['gold'], delta=.0001)
            else:
                top = max(mobs.stats(k).level for k in counts)
                for k in counts:
                    factor = 1 - .03 * (top - mobs.stats(k).level)
                    a, g = revenue(k)
                    self.assertAlmostEqual(a, profile['afro'] * factor, delta=1)
                    self.assertAlmostEqual(g, profile['gold'] * factor, delta=.0001)

    def test_sa_base_income_is_105000_afro_and_1_2_gold(self):
        profile = next(p for p in self.doc['targets'] if p['id'] == 'camp-263')
        counts = {int(k): n for k, n in profile['counts'].items()}
        total = sum(counts.values())
        a = sum(revenue(k)[0] * n for k, n in counts.items()) / total
        g = sum(revenue(k)[1] * n for k, n in counts.items()) / total
        self.assertAlmostEqual(a, 105000, delta=1)
        self.assertAlmostEqual(g, 1.2, delta=.0001)

    def test_elite_roster_is_absent_from_every_patrol_and_not_officers(self):
        forbidden = ('командир', 'командер', 'полков', 'капитан', 'лейтенант', 'майор', 'казнач', 'бухгалтер')
        for rows in world.placements().values():
            for row in rows:
                if 'patrol' in row:
                    self.assertNotIn(row['type'], self.elites)
        import names
        for k in self.elites:
            self.assertFalse(any(w in names.text(k).lower() for w in forbidden))
            self.assertFalse(quests.given_by(k) or quests.taken_by(k))
            self.assertFalse(bosses.keeps_hours(k))
            self.assertFalse(any(loot_rules.economic(t) for t, _, _ in mobs.loot_table(k)))

    def test_centres_and_secondary_boss_places_have_diverse_existing_elites(self):
        config = json.loads((ROOT / 'data/camp_elites.json').read_text(encoding='utf-8'))
        protected = {336, 1563, 1564, 1565, 1749, 1750, 1751, 2170}
        for lid, record in config['locations'].items():
            room = self.manager.get(int(lid))
            ordinary = [n.type_id for n in room.npcs.values()
                        if n.root == world.MOB and mobs.stats(n.type_id).role == 'mob'
                        and n.type_id not in protected]
            self.assertTrue(ordinary)
            self.assertLessEqual(set(ordinary), set(record['types']))
            self.assertGreaterEqual(len(set(ordinary)), min(3, len(ordinary)))
            for k in protected:
                self.assertEqual(camp_elites.replacement(int(lid), k, 0), k)
            for k in (586, 587, 588, 589, 590, 591, 592, 593, 764, 1024, 1736):
                self.assertEqual(camp_elites.replacement(int(lid), k, 0), k)

    def test_quest_anchor_targets_remain_available(self):
        def at(x, y):
            return {r['type'] for r in world.placed_in(world.pack(x, y)) if 'patrol' in r}
        self.assertLessEqual({261, 262, 266, 267}, at(5970, 1725))
        self.assertIn(291, at(5974, 1738))
        self.assertLessEqual({303, 307, 311}, at(5992, 1722))
        self.assertIn((5545, .1), mobs.quest_table(930))
        self.assertIn((5545, .1), mobs.quest_table(931))
        for kind in (930, 931):
            self.assertEqual(mobs.quest_roll(kind, (), random.Random(1)), [])

    def test_drop_table_is_type_only_even_in_different_locations(self):
        for kind in (20, 264, 838, 930):
            a = mobs.loot_for(mobs.stats(kind), random.Random(19), (), loc_id=34)
            b = mobs.loot_for(mobs.stats(kind), random.Random(19), (), loc_id=132)
            self.assertEqual(a, b)

    def test_sand_is_outside_cap_and_normal_random_rows_still_share_two_slots(self):
        for k in (836, 837, 838, 839, 840, 841, 930, 931):
            self.assertIn(mortimer.SAND, mobs.independent_loot(k))
            rng = random.Random(7)
            rng.random = lambda: 0
            drops = mobs.roll_table(k, rng)
            self.assertIn((mortimer.SAND, 1), drops)
            self.assertLessEqual(len([t for t, n in drops if t != mortimer.SAND]), 2)

    def test_five_gold_valuables_expand_by_level_without_changing_quantity(self):
        for k, rows in loot_rules.records().items():
            if k in self.elites:
                continue
            lvl = mobs.stats(k).level
            expected_count = 1 if lvl < 4 else 2 if lvl < 8 else 3 if lvl < 12 else 4 if lvl < 16 else 5
            self.assertEqual(sum(row['type'] in mortimer.VALUABLES for row in rows), expected_count)
            self.assertTrue(all(mobs.count_of(k, row['type']) == 1 for row in rows))

    def test_unlisted_creatures_keep_their_previous_tables(self):
        untouched = [int(k) for k in mobs.TYPES if int(k) not in loot_rules.records()]
        current = {k: mobs.loot_table(k) for k in untouched}
        with patch.object(loot_rules, 'records', return_value={}), \
                patch.dict(mobs._TABLES, {}, clear=True):
            self.assertEqual(current, {k: mobs.loot_table(k) for k in untouched})

    def test_resource_mine_guard_and_treasurer_tables_have_no_override(self):
        for k in (665, 1714, 1715, 1716, 1717, 586, 587, 588, 589, 590, 591, 592, 593, 764, 1024, 1736):
            self.assertNotIn(k, loot_rules.records())
        for k in bosses.CAMP_BOSS_TYPES:
            self.assertNotIn(k, loot_rules.records())


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(LootRebalance)
