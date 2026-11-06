"""Small checks of player-facing schedules, without starting a game server."""
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import bosses
import map_labels
import mobs
import quests
from testkit import run_cases


ROOT = Path(__file__).resolve().parents[1]
CLOCK = re.compile(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)')
EVEN_HOURS = tuple(range(0, 24 * 60, 120))


def times(text):
    return tuple(int(h) * 60 + int(m) for h, m in CLOCK.findall(text))


class ReleaseConsistency(unittest.TestCase):
    def test_boss_map_labels_match_default_scheduler(self):
        self.assertEqual(tuple(bosses.hours_from(bosses.DEFAULT_HOURS)), EVEN_HOURS)
        doc = json.loads((ROOT / 'data/map_labels.json').read_text(encoding='utf-8'))
        rows = [e for e in doc['labels'] if e.get('why', '').startswith(
            "The owner's boss clock, 2026-10-11")]
        self.assertEqual(len(rows), 47)
        for row in rows:
            with self.subTest(cell=(row['x'], row['y'])):
                lines = re.split(r'<br\s*/?>', row['text'], flags=re.IGNORECASE)
                clock_lines = [line for line in lines if any(word in line for word in (
                    'Сражение за золото в', 'Староста присутствует в',
                    'Начальник склада приходит в', 'часто кто-то приезжает с золотом'))]
                self.assertEqual(len(clock_lines), 1)
                self.assertEqual(times(clock_lines[0]), EVEN_HOURS)

    def test_boss_dialogues_use_current_scheduler_including_custom_minutes(self):
        source = json.loads((ROOT / 'data/quests.json').read_text(encoding='utf-8'))
        # Use the authored start rather than the already-expanded global quest.
        row = next(q for q in source['quests'] if q['type'] == 10)
        original = quests.QUESTS[10]
        import copy
        for hours, expected in (([90, 1080], (90, 1080)), ([], ())):
            q = copy.copy(original)
            texts = list(original.texts)
            texts[quests.START] = row['start']
            q.texts = tuple(texts)
            with patch.object(bosses, 'HOURS', hours):
                quests._hours(q)
            self.assertEqual(times(q.texts[quests.START]), expected)
            self.assertNotIn('{boss_hours}', q.texts[quests.START])

    def test_prison_dialogues_and_map_match_all_three_windows(self):
        doc = json.loads((ROOT / 'data/schedule.json').read_text(encoding='utf-8'))
        expected = (780, 1020, 1260)
        for prison in ('prison_wh', 'prison_dn', 'prison_ah'):
            window = doc['windows'][prison]
            self.assertEqual(times(', '.join(window['daily'])), expected)
            self.assertEqual(window['minutes'], 30)
        for kind in (158, 159, 632, 636, 880, 884):
            text = quests.QUESTS[kind].texts[quests.START]
            actual = times(text)
            self.assertTrue(actual, kind)
            # Some starts repeat the invitation's hours in their hint.
            self.assertEqual(actual, expected * (len(actual) // len(expected)), kind)
        prison_rows = [text for _, _, _, text in map_labels.load()
                       if text and 'Усиление режима' in text]
        self.assertEqual(len(prison_rows), 3)
        for text in prison_rows:
            self.assertEqual(times(text), expected)

    def test_warehouse_keeps_its_daily_window(self):
        self.assertEqual(tuple(bosses.warehouse_hours_from(bosses.DEFAULT_WAREHOUSE_HOURS)), (1200,))
        self.assertEqual(bosses.DEFAULT_STAY, 60)
        # Only Abu's level requirement changed; its daily hours stay exact.
        rows = [(x, y, text) for x, y, _, text in map_labels.load()
                if text and 'Хозяин присутствует' in text]
        self.assertEqual([(x, y) for x, y, _ in rows], [(6183, 1976)])
        self.assertIn('17 уровня', rows[0][2])
        self.assertEqual(times(rows[0][2]), (1200, 1260, 1140, 1155))

    def test_leader_hint_matches_one_ingot_without_changing_two_ingot_exchange(self):
        text = quests.QUESTS[10].texts[quests.START]
        self.assertIn('У лидера при себе один слиток.', text)
        self.assertNotIn('Два слитка у него при себе всегда', text)
        self.assertIn('два слитка', text)
        # The actual drop table, not a second description of its settings.
        ingots = [r for r in mobs.loot_table(2103) if r[0] in (7620, 4796, 4797)]
        self.assertEqual(ingots, [(7620, 1.0, True)])
        self.assertEqual(mobs.count_of(2103, 7620), 1)


if __name__ == '__main__':
    run_cases(ReleaseConsistency)
