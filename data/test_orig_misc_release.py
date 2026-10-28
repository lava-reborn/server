"""Reviewed release text changes retain original references and strict legacy checks."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import build_orig_misc as builder

HERE = Path(__file__).resolve().parent


class ReleaseTexts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = json.loads((HERE / "orig_misc.json").read_text(encoding="utf-8"))["quests"]
        cls.rows = {r["type"]: r for r in json.loads((HERE / "quests.json").read_text(encoding="utf-8"))["quests"]}

    def build(self, quest_type, row=None):
        original = self.originals[str(quest_type)]
        ids = original["ids"]
        texts = {ident: original[key] for key, ident in zip(builder.QUEST_KEYS, ids) if ident is not None}
        with patch.object(builder, "VERIFIED", {quest_type: tuple(ids)}):
            return builder.build_quests(texts, [row if row is not None else self.rows[quest_type]])[0][str(quest_type)]

    def test_provision_rewrite_keeps_original_references(self):
        record = self.build(148)
        self.assertEqual(record["ids"], [62719, 62720, 62721, 62722])
        self.assertEqual(record["start"], self.originals["148"]["start"])
        self.assertIn("один мешок фасоли", self.rows[148]["start"])
        self.assertIn("квестовую Фуль", self.rows[148]["start"])

    def test_three_prison_guards_accept_new_schedule_only(self):
        for quest_type in (158, 636, 884):
            with self.subTest(quest=quest_type):
                self.assertEqual(self.build(quest_type)["ids"], [62257, 62258, None, 62259])
                row = copy.deepcopy(self.rows[quest_type])
                row["start"] = row["start"].replace("13:00", "14:00")
                with self.assertRaises(SystemExit):
                    self.build(quest_type, row)

    def test_provision_exception_does_not_allow_renaming_the_quest(self):
        row = copy.deepcopy(self.rows[148])
        row["name"] = "Другая награда"
        with self.assertRaises(SystemExit):
            self.build(148, row)

    def test_legacy_own_start_still_cannot_add_unrelated_text(self):
        self.build(765)
        row = copy.deepcopy(self.rows[765])
        row["start"] += " Несогласованная новая награда."
        with self.assertRaises(SystemExit):
            self.build(765, row)


if __name__ == "__main__":
    unittest.main()
