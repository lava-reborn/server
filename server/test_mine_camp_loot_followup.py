"""Literal mine emerald chances and the narrow surrounding-camp AF uplift."""
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import camp_loot
import encounters
import holdings
import items
import loot_rules
import mobs
import mortimer
import names
import world
from testkit import run_cases


ROOT = Path(__file__).resolve().parents[1]
EMERALD = 3159
MINERS = {838: .7, 839: .7, 840: 1., 841: 1., 930: 1., 931: 1.}


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value

    def randint(self, low, high):
        return low

    def choice(self, rows):
        return rows[0]


class MineCampLootFollowup(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / 'data/loot_rebalance.json').read_text(encoding='utf-8'))
        self.manual = json.loads((ROOT / 'data/loot_manual.json').read_text(encoding='utf-8'))
        self.followup = self.doc['followup_2026_11_23']

    def test_all_six_native_miners_have_one_exact_independent_emerald_row(self):
        for kind, chance in MINERS.items():
            with self.subTest(miner=kind):
                native = [r for r in mobs.loot_table(kind) if r[0] == EMERALD]
                self.assertEqual(native, [(EMERALD, chance, True)])
                self.assertIn(EMERALD, mobs.independent_loot(kind))
                self.assertEqual(mobs.count_of(kind, EMERALD), 1)
                for source in (self.doc, self.manual):
                    rows = [r for r in source['by_type'][str(kind)] if r.get('type') == EMERALD]
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['chance'], chance)
                    self.assertIs(rows[0]['independent'], True)
                self.assertIs(next(r for r in self.manual['by_type'][str(kind)]
                                   if r.get('type') == EMERALD)['exact_chance'], True)

    def test_halfa_threshold_and_existing_level_scanner_multipliers(self):
        for kind in (838, 839):
            for multiplier, threshold in ((.25, .175), (1, .7), (3, 1)):
                with self.subTest(miner=kind, multiplier=multiplier):
                    before = math.nextafter(threshold, 0)
                    self.assertIn((EMERALD, 1), mobs.roll_table(kind, FixedRandom(before), multiplier))
                    self.assertNotIn((EMERALD, 1), mobs.roll_table(kind, FixedRandom(threshold), multiplier))

    def test_dongola_and_abu_are_guaranteed_without_extra_roll_or_cap_slot(self):
        for kind in (840, 841, 930, 931):
            for multiplier in (.25, 1, 3.75):
                self.assertIn((EMERALD, 1), mobs.roll_table(kind, FixedRandom(1), multiplier))
        for kind in MINERS:
            drops = mobs.roll_table(kind, FixedRandom(0))
            self.assertEqual(drops.count((EMERALD, 1)), 1)
            table = {t: chance for t, chance, _ in mobs.loot_table(kind)}
            ordinary = [t for t, _count in drops if t not in mobs.independent_loot(kind)
                        and table.get(t, 0) < mobs.SURE]
            self.assertLessEqual(len(ordinary), mobs.MAX_DROPS)

    def test_an_independent_emerald_survives_two_earlier_successes(self):
        for kind in MINERS:
            rows = [(6941, .5, True), (6944, .5, True), (EMERALD, MINERS[kind], True)]
            with patch.object(mobs, 'loot_table', return_value=rows):
                self.assertEqual(mobs.roll_table(kind, FixedRandom(0)),
                                 [(6941, 1), (6944, 1), (EMERALD, 1)])

    def test_duplicate_wiki_manual_override_sources_do_not_duplicate_or_raise_chance(self):
        for kind in MINERS:
            mobs._TABLES.pop(kind, None)
            self.addCleanup(mobs._TABLES.pop, kind, None)
            source = {str(kind): [dict(item='Небольшие изумруды', chance=.99, tier='Ценный')]}
            with patch.object(mobs, '_loot_wiki', return_value=source):
                self.assertEqual([r for r in mobs.loot_table(kind) if r[0] == EMERALD],
                                 [(EMERALD, MINERS[kind], True)])
                self.assertEqual(mobs.roll_table(kind, FixedRandom(0)).count((EMERALD, 1)), 1)

    def test_minus_five_cutoff_and_existing_active_diamond_quest_conditions(self):
        for kind in MINERS:
            stats = mobs.stats(kind)
            drops = mobs.loot_for(stats, FixedRandom(0), killer_level=stats.level + 5)
            self.assertNotIn(EMERALD, [t for t, _count in drops])
        for kind in (930, 931):
            stats = mobs.stats(kind)
            self.assertIn((5545, .1), mobs.quest_table(kind))
            self.assertNotIn(5545, [t for t, _chance, _valuable in mobs.loot_table(kind)])
            self.assertEqual(mobs.quest_roll(kind, (5545,), FixedRandom(0)), [(5545, 1)])
            self.assertEqual(mobs.quest_roll(kind, (), FixedRandom(0)), [])
            # This exchangeable fare is not a personal-only quest item;
            # retain its existing cutoff rule rather than silently widening it.
            self.assertFalse(mobs.personal_quest_item(5545))
            self.assertEqual(mobs.loot_for(stats, FixedRandom(0), wanted=(5545,),
                                          killer_level=stats.level + 5), [])

    def test_sand_and_nubian_emerald_sources_keep_their_previous_rules(self):
        for kind in MINERS:
            chance = .75 if kind in (838, 839) else 1.
            self.assertIn((mortimer.SAND, chance, False), mobs.loot_table(kind))
        self.assertNotIn('836', self.followup['emerald_chances'])
        self.assertNotIn('837', self.followup['emerald_chances'])
        self.assertEqual(mobs.quest_table(930), mobs.quest_table(931))

    def test_uplift_scope_is_existing_surrounding_combat_types_not_special_roles(self):
        selected = set(self.followup['camp_type_ids'])
        rings = {row['type'] for rows in world.placements().values() for row in rows
                 if row.get('patrol') in camp_loot.CENTRES}
        encounters_types = {t for band, _reach in encounters.bands() for t in band.types}
        sites = {t for site in holdings.sites().values()
                 for t in (site.boss,) + site.guards + site.troops}
        self.assertEqual(len(selected), 93)
        self.assertLessEqual(selected, rings | encounters_types)
        self.assertFalse(selected & (set(MINERS) | {836, 837} | sites))
        for kind in selected:
            self.assertEqual(mobs.stats(kind).role, 'mob')
            self.assertTrue(mobs.stats(kind).can_attack)
            self.assertFalse(any(word in names.text(kind).lower() for word in ('казнач', 'бухгалтер')))

    def test_only_existing_afro_economic_chances_grow_and_metadata_is_explicit(self):
        self.assertEqual(len(self.followup['changed_rows']), 279)
        self.assertEqual(self.followup['chance_factor'], 1.1)
        current = loot_rules.records()
        for row in self.followup['changed_rows']:
            kind, item = row['mob'], row['item']
            self.assertIn(kind, self.followup['camp_type_ids'])
            self.assertTrue(loot_rules.economic(item))
            self.assertNotIn(item, mortimer.VALUABLES)
            self.assertNotIn(item, set(items.GOLD_INGOTS) | loot_rules.QUEST_MATERIALS)
            self.assertNotEqual(item, mortimer.SAND)
            self.assertAlmostEqual(row['after'], min(1, row['before'] * 1.1), places=9)
            actual = next(r for r in current[kind] if r['type'] == item)
            self.assertEqual(actual['chance'], row['after'])
            self.assertIs(actual['independent'], False)
        self.assertEqual(set(self.followup['income_delta_175']),
                         {str(t) for t in set(self.followup['camp_type_ids']) | set(MINERS)})


if __name__ == '__main__':
    run_cases(MineCampLootFollowup)
