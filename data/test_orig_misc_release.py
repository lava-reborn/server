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

    def test_provision_restores_original_description_and_quantities(self):
        record = self.build(148)
        self.assertEqual(record["ids"], [62719, 62720, 62721, 62722])
        self.assertEqual(record["start"], self.originals["148"]["start"])
        self.assertEqual(self.rows[148]["start"], record["start"])
        self.assertNotIn("start", self.rows[148].get("own_texts", []))
        self.assertEqual([(o["obj"], o["num"]) for o in self.rows[148]["objs"]],
                         [(333, 5), (334, 1)])

    def test_three_prison_guards_accept_new_schedule_only(self):
        for quest_type in (158, 636, 884):
            with self.subTest(quest=quest_type):
                self.assertEqual(self.build(quest_type)["ids"], [62257, 62258, None, 62259])
                row = copy.deepcopy(self.rows[quest_type])
                row["start"] = row["start"].replace("13:00", "14:00")
                with self.assertRaises(SystemExit):
                    self.build(quest_type, row)

    def build_prison_rides(self, changed=None):
        ride_types = (159, 632, 880)
        texts = {}
        for quest_type in ride_types:
            record = self.originals[str(quest_type)]
            texts.update({ident: record[key] for key, ident in
                          zip(builder.QUEST_KEYS, record["ids"]) if ident is not None})
        verified = {t: builder.VERIFIED[t] for t in ride_types}
        rows = [changed if changed is not None and changed["type"] == t
                else self.rows[t] for t in ride_types]
        with patch.object(builder, "VERIFIED", verified):
            return builder.build_quests(texts, rows)[0]

    def test_prison_rides_keep_each_destination_with_new_hours(self):
        records = self.build_prison_rides()
        for quest_type, start_id in ((159, 62263), (632, 62264), (880, 62265)):
            with self.subTest(quest=quest_type):
                self.assertEqual(records[str(quest_type)]["ids"],
                                 [62262, start_id, None, 59830])
                self.assertEqual(records[str(quest_type)], self.originals[str(quest_type)])

    def test_prison_rides_reject_wrong_hours_or_destination(self):
        for quest_type in (159, 632, 880):
            for replacement in ("12:00", "14:00"):
                with self.subTest(quest=quest_type, hours=replacement):
                    row = copy.deepcopy(self.rows[quest_type])
                    row["start"] = row["start"].replace("13:00", replacement)
                    with self.assertRaises(SystemExit):
                        self.build_prison_rides(row)
        row = copy.deepcopy(self.rows[159])
        row["start"] = self.rows[880]["start"]
        with self.assertRaises(SystemExit):
            self.build_prison_rides(row)

    def test_verified_quest_archive_rebuilds_without_text_changes(self):
        archive = json.loads((HERE / "orig_misc.json").read_text(encoding="utf-8"))
        texts = {}
        for record in self.originals.values():
            for key, ident in zip(builder.QUEST_KEYS, record["ids"]):
                if ident is not None:
                    self.assertEqual(texts.get(ident, record[key]), record[key])
                    texts[ident] = record[key]
        for record in archive["transport"].values():
            for key in ("name", "desc"):
                ident = record[key + "_id"]
                if ident is not None:
                    texts[ident] = record[key]
        rows = list(self.rows.values())
        for path in sorted(HERE.glob("questgen_*.json")):
            rows += json.loads(path.read_text(encoding="utf-8"))["quests"]
        self.assertEqual(builder.build_quests(texts, rows)[0], self.originals)

    def test_provision_does_not_allow_renaming_the_quest(self):
        row = copy.deepcopy(self.rows[148])
        row["name"] = "Другая награда"
        with self.assertRaises(SystemExit):
            self.build(148, row)

    def test_provision_own_description_cannot_add_unrelated_text(self):
        row = copy.deepcopy(self.rows[148])
        row["own_texts"] = ["start"]
        row["start"] += " Дополнительная награда 10 голд."
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
