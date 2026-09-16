"""Sanity of the wiki-derived item data (run from WSL: python3 data/test_wiki_data.py).

Checks that every type_id the wiki data names exists in the client's
objects.xml, that the fields the client divides by are never zero, that
every firearm has at least one fire mode, and pins the coverage reached so
a regression in the linker or the parser shows up as a failing number.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import HERE, FIRE_ARM, WEAR, HEAL, AMMO, COLD_ARM, load_objects, load_json

# Reached on the 2026-09-16 mirror; lower only with a reason.
MIN_LINKED_PAGES = 900
MIN_LINKED_TYPES = 1100
MIN_SI_ITEMS = 1100
MIN_GROUP = {"Огнестрел": 30, "Холодное": 80, "Броня/одежда": 90, "Боеприпасы": 25,
             "Лечилки/бафы": 80, "Чертежи": 180, "Лут": 400}
MIN_FIREARM_RESOLVED = 10
MIN_BLUEPRINTS = 198


class Data(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = load_objects()
        cls.links = load_json(os.path.join(HERE, "wiki_links.json"))
        cls.si = load_json(os.path.join(HERE, "items_wiki.json"))["items"]
        cls.fam = load_json(os.path.join(HERE, "firearm_families.json"))
        cls.mods = load_json(os.path.join(HERE, "mods_wiki.json"))

    def test_type_ids_exist(self):
        unknown = [k for k in self.si if int(k) not in self.objects]
        self.assertEqual(unknown, [])
        for title, rec in self.links["pages"].items():
            for l in rec["links"]:
                self.assertTrue(0 < l["confidence"] <= 1, title)
                for t in l["type_ids"]:
                    self.assertIn(t, self.objects, "%s -> %s" % (title, t))
        for name, fam in self.fam["lines"].items():
            for t in fam["members"].values():
                self.assertIn(t, self.objects, name)

    def test_divisors_and_modes(self):
        for k, si in self.si.items():
            root = self.objects[int(k)][0]
            if root == FIRE_ARM:
                self.assertTrue(any(si["fire_mods"]), k)
                for i in range(3):
                    if si["fire_mods"][i]:
                        self.assertGreater(si["max_range"][i], 0, k)
                        self.assertGreater(si["target_size"][i], 0, k)
                    for key in ("h_damage_min", "h_damage_max", "st_damage_min",
                                "st_damage_max", "fire_costs", "fire_times",
                                "opt_range", "end_opt_range", "piercing"):
                        self.assertEqual(len(si[key]), 3, k)
                self.assertGreater(si.get("clip_size", 1), 0, k)
            elif root == COLD_ARM:
                self.assertGreater(si["max_range"], 0, k)
            elif root == AMMO and "acc_mod" in si:
                # acc_mod 0 is legal: the wiki's "Точность +100%" (ПАБ-9 СБ).
                for key in ("range_mod", "acc_mod", "dam_mod", "st_mod", "piercing"):
                    self.assertGreaterEqual(si[key], 0, k)
                self.assertGreater(si["range_mod"], 0, k)
            elif root == WEAR:
                self.assertIn("armor_class", si, k)
            self.assertGreaterEqual(si.get("weight", 1), 0, k)
            self.assertNotEqual(si.get("sell_num", 1), 0, k)
            self.assertNotEqual(si.get("max_count", 1), 0, k)

    def test_variant_matches_name(self):
        """A _pm/_gold copy must have been read off the (P)/(G) column."""
        for k, si in self.si.items():
            name = self.objects[int(k)][1]
            col = si["_wiki"]["column"]
            if name.endswith(("_pm", "_P")) and "(P)" in col.replace("Р", "P"):
                self.assertEqual(si.get("premium"), 1, name)
            if name.endswith(("_gold", "_G", "_Gold")) and "(A)" in col.replace("А", "A"):
                self.fail("%s read off %s" % (name, col))

    def test_coverage(self):
        cov = self.links["_meta"]["coverage"]
        linked = sum(1 for r in self.links["pages"].values() if r["confidence"] >= 0.5)
        self.assertGreaterEqual(linked, MIN_LINKED_PAGES)
        self.assertGreaterEqual(len(self.links["by_type"]), MIN_LINKED_TYPES)
        self.assertGreaterEqual(len(self.si), MIN_SI_ITEMS)
        for group, n in MIN_GROUP.items():
            self.assertGreaterEqual(cov[group]["linked"], n, group)

    def test_firearm_families(self):
        meta = self.fam["_meta"]
        self.assertGreaterEqual(meta["resolved"], MIN_FIREARM_RESOLVED)
        self.assertEqual(meta["mod_suffix"]["IX"], "clipsize")
        for key, a in self.fam["articles"].items():
            self.assertLessEqual(len(a["candidates"]), 4, key)
            if a["resolved"]:
                self.assertIn(a["resolved"], a["candidates"], key)
                self.assertIn(a["resolved"], self.fam["lines"], key)
                self.assertGreaterEqual(a["confidence"], 0.6, key)
            else:
                self.assertLess(a["confidence"], 0.6, key)

    def test_mods(self):
        bp = self.mods["blueprints"]
        self.assertGreaterEqual(len(bp), MIN_BLUEPRINTS)
        self.assertEqual(bp["Урон (10у)"]["effects"].get("damage_pct"), 10)
        self.assertEqual(bp["Вес (10у)"]["effects"].get("weight_pct"), -25)
        self.assertEqual(bp["Зашифрованный чертеж (10у)"]["type_ids"],
                         [t for t, (r, n) in self.objects.items() if n == "codified_bp_10"])
        self.assertEqual(self.mods["mod_table"]["IX"]["suffix"], "clipsize")
        self.assertEqual(self.mods["mod_table"]["XII"]["suffix"], "damage")
        for title, rec in self.mods["mod_pages"].items():
            for t in rec["type_ids"]:
                self.assertIn(t, self.objects, title)


if __name__ == "__main__":
    unittest.main()
