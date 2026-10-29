"""Prison schedule, related windows and player-facing hours stay aligned."""
import os
import unittest
from datetime import datetime
from pathlib import Path

import bosses
import events
import map_labels
import quests


class PrisonSchedule(unittest.TestCase):
    def test_daily_windows_and_boss_starts(self):
        schedule = events.table()
        for town in ('wh', 'dn', 'ah'):
            for minute in range(1440):
                t = datetime(2026, 10, 27, minute // 60, minute % 60,
                             tzinfo=bosses.ZONE).timestamp()
                for suffix, lo, hi in (('', 0, 30), ('_gates', -15, 30),
                                       ('_medics', 25, 30)):
                    expected = any(h * 60 + lo <= minute < h * 60 + hi
                                   for h in (13, 17, 21))
                    self.assertEqual(schedule.window('prison_' + town + suffix)
                                     .is_open(t), expected, (town, minute, suffix))
        for h in (13, 17, 21):
            self.assertNotIn(h * 60, bosses.parse_hours(bosses.DEFAULT_HOURS))

    def test_served_quest_texts(self):
        texts = [q.texts[1] for q in quests.QUESTS.values()]
        self.assertGreaterEqual(sum('отправиться в тюрьму' in t and '13:00' in t
                                    for t in texts), 6)
        self.assertFalse(any('12:00, 16:00' in t for t in texts))

    def test_map_labels(self):
        resource = os.environ.get('LAVA_RES')
        if not resource:
            self.skipTest('LAVA_RES is required for the client map file')
        raw = (Path(resource) / 'database' / 'locations.xml').read_bytes()
        result, _changed = map_labels.apply(raw)
        import html
        labels = []
        for row in map_labels.ROW.finditer(result):
            attrs = {k.decode(): html.unescape(v.decode('utf-8'))
                     for k, v in map_labels.ATTR.findall(row.group(0))}
            if 'Усиление режима' in attrs.get('text', ''):
                labels.append(attrs['text'])
        self.assertEqual(len(labels), 3)
        for text in labels:
            for time in ('13:00', '17:00', '21:00'):
                self.assertIn(time, text)
            for time in ('12:00', '16:00', '23:00'):
                self.assertNotIn(time, text)


if __name__ == '__main__':
    unittest.main()
