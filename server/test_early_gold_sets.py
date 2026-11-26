"""The two early G upgrades: canonical generation, live bonuses and wire data."""
import copy
import json
import sys
import unittest
from pathlib import Path

import inventory
import items
import progression
import sets
from protocol import decode, encode
from testkit import run_cases

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
import build_sets
import set_release_rules


FIELDS = ('hp', 'st', 'armor', 'od', 'cp', 'ce')
PAIRS = ((11218, 11221), (11191, 11193))
TARGETS = {11221: (0, 84, 16, 0, 1, 1), 11193: (14, 119, 53, 6, 6, 6)}


def rows(key):
    return [dict(type_id=t, root=items.WEAR, slot=inventory.HEAD + i + (i >= 3), brk=1)
            for i, t in enumerate(sets.SETS[key]['members'].values())]


def totals(key):
    equipped = rows(key)
    bonus = inventory.gear_bonus(equipped)
    armour = sum(items.params_of(row['type_id'])['armor_class'] for row in equipped)
    return tuple(armour if field == 'armor' else bonus[field] for field in FIELDS)


class EarlyGoldSets(unittest.TestCase):
    def test_exact_live_totals_and_unchanged_afro_targets(self):
        for key, want in {**TARGETS, 11218: (0, 70, 13, 0, 1, 1),
                          11191: (12, 99, 44, 5, 5, 5)}.items():
            with self.subTest(set=key):
                self.assertEqual(totals(key), want)

    def test_gold_advantage_is_local_and_keeps_the_next_rung_pools_higher(self):
        for afro, gold in PAIRS:
            a, g = totals(afro), totals(gold)
            self.assertTrue(all(x <= y for x, y in zip(a, g)))
            self.assertGreater(g[1], a[1])
            self.assertGreater(g[2], a[2])
        for low, high in ((11221, 11169), (11193, 11258)):
            self.assertTrue(all(totals(low)[i] < totals(high)[i] for i in (1, 2)))
            self.assertLessEqual(totals(low)[0], totals(high)[0])

    def test_protocol_piece_and_set_frames_keep_exact_updated_values(self):
        for _afro, gold in PAIRS:
            for row in rows(gold):
                cmd, params = items.static_info(row['type_id'])
                _, decoded = decode(encode(cmd, **params))
                for field in ('armor_class', 'bonus_hp', 'bonus_st', 'bonus_od',
                              'bonus_cp', 'bonus_ce', 'cost', 'g_cost', 'max_break_abs'):
                    self.assertEqual(decoded.get(field, 0), params.get(field, 0))
            _, decoded = decode(encode('ss_si_set', **sets.frame(gold)))
            self.assertEqual(decoded, sets.frame(gold))

    def test_live_character_applies_bonuses_once_and_reverts_without_gear(self):
        for _afro, gold in PAIRS:
            ch = progression.Character()
            before = ch.hp_max, ch.sp_max, ch.ap_ceiling
            bonus = inventory.gear_bonus(rows(gold))
            ch.set_gear(bonus)
            strength, agility, constitution = bonus['attribs'][:3]
            self.assertEqual(ch.hp_max - before[0], bonus['hp'] + 4 * strength + 20 * constitution)
            self.assertEqual(ch.sp_max - before[1], bonus['st'] + 4 * agility + 20 * constitution)
            self.assertEqual(ch.ap_ceiling - before[2], bonus['od'] + 5 * max([0] + bonus['skills']))
            ch.set_gear(sets.zero())
            self.assertEqual((ch.hp_max, ch.sp_max, ch.ap_ceiling), before)

    def test_partial_set_bonuses_use_every_threshold_once(self):
        members = list(sets.SETS[11193]['members'].values())
        for count, expected in ((1, (0, 0, 0, 0, 0)), (2, (2, 2, 0, 0, 0)),
                                (3, (2, 8, 2, 0, 0)), (4, (2, 18, 6, 0, 3)),
                                (5, (2, 32, 6, 3, 3))):
            bonus = sets.bonuses(members[:count])
            self.assertEqual(tuple(bonus[field] for field in sets.SCALARS), expected)

    def test_release_regeneration_is_idempotent_and_preserves_other_records(self):
        document = json.loads(Path(sets.PATH).read_text(encoding='utf-8'))
        before = copy.deepcopy(document)
        for afro, gold in PAIRS:
            # Restore the shared A/G stats which the single wiki column supplied.
            source, target = document['sets'][str(afro)], document['sets'][str(gold)]
            for slot, piece in target['members'].items():
                for field in ('armor_class', 'bonus_hp', 'bonus_st', 'bonus_od', 'bonus_cp', 'bonus_ce'):
                    if field in source['members'][slot]:
                        piece[field] = source['members'][slot][field]
                    else:
                        piece.pop(field, None)
            target['bonus'] = copy.deepcopy(source['bonus'])
            target['_designed'] = [line for line in target['_designed']
                                    if not line.startswith('Release 2026-11-23: early G')]
        untouched = {key: copy.deepcopy(row) for key, row in document['sets'].items()
                     if int(key) not in TARGETS}
        set_release_rules.apply(document['sets'])
        self.assertEqual(document, before)
        self.assertEqual(untouched, {key: row for key, row in document['sets'].items()
                                     if int(key) not in TARGETS})
        set_release_rules.apply(document['sets'])
        self.assertEqual(document, before)
        self.assertEqual(json.loads(build_sets.dump(document['_meta'], document['sets'])), before)


if __name__ == '__main__':
    run_cases(EarlyGoldSets)
