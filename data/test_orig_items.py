"""Original item texts (run from WSL: LAVA_RES=.../lava/res python3 data/test_orig_items.py).

Pins what data/build_orig_items.py must keep true of data/orig_items.json:
the hand-checked firearm lines and the zero level, the Tokarev trap the std
filter exists for, the shape and tier marks of firearm names, the trophies,
texts copied verbatim, and a rebuild that reproduces the committed file byte
for byte (the launcher compares a digest of the string table, so a
wandering order would make every player download it on every start).
The texts.xml-dependent checks skip when the source is not on this machine.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_orig_items as B
from wiki_common import FIRE_ARM, HERE, RES, load_json, load_objects

DATA = os.path.join(HERE, "orig_items.json")
SOURCE_MD5 = "7a10e992003480a76546b6c824b3dbc2"
SOURCE_SIZE = 20433511
SIX = {"Пистолет", "Пистолет-пулемёт", "Дробовик", "Пулемет", "Автомат", "Винтовка"}
CLAN_WORDS = {"Le Mon", "Liberty", "Delta Force", "Blackwater"}

# Reached on 2026-09-23 from the md5 above; lower only with a reason.
# ColdArm went from 75 to 105 on 2026-09-24 with the knife line (rule 7b),
# SimpleObject from 537 to 539 on 2026-09-25 with the mine's loot (rule 7c),
# and to 542 the same day with the three gold ingots (rule 7d).
MIN_TYPES = {"FireArm": 5494, "WearItem": 5530, "SimpleObject": 542, "Ammo": 160,
             "ColdArm": 105, "Heal_Item": 94, "Trophy": 7}
MIN_FIREARM_HIGH = 3515
# FireArm types named from the wiki, outside every "Имя[..]$Класс" rule
# (MEG_23, VSS_rifle_Mk2, Police_gun ...): their rows carry no "$". Six more
# since 2026-09-28: Берт Гаммер's training guns noob_* (rule 7f), whose
# rows "Тренировочный пистолет" ... carry none either.
MAX_FIREARM_WITHOUT_CLASS = 12

ZERO_LEVEL = {"pistols_0_lvl_0": "Desert Eagle Mark XIX", "pistols_1_lvl_0": "Самострел",
              "pistols_2_lvl_0": "Самопальный револьвер", "pistols_3_lvl_0": "Mauser Mod.712"}
# From the task statement, spelled as texts.xml spells them: C96 has a Latin C.
NAMED_LINES = {"pistols_1_lvl_2": "Беретта 92", "pistols_2_lvl_2": "Браунинг",
               "pistols_1_lvl_4": "Glock 17", "pistols_2_lvl_4": "Walther P99",
               "pistols_0_lvl_2": "Маузер C96"}
TROPHIES = {"tr_Skull": (800, "Череп"), "tr_Scalp": (802, "Скальп"), "tr_Finger": (804, "Палец"),
            "tr_Ear": (806, "Ухо"), "tr_Hand": (808, "Кисть"), "tr_Heart": (810, "Сердце"),
            "tr_Horn": (812, "Рога")}


def base_name(text):
    """'Беретта 92[A][2]$Пистолет' -> 'Беретта 92'."""
    return text.split("$")[0].split("[")[0].strip()


def latin_c(s):
    return s.replace("С", "C")


def source_path():
    return os.environ.get("LAVA_ORIG_TEXTS") or B.DEFAULT_TEXTS


class OrigItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(os.path.join(RES, "database", "objects.xml")):
            raise RuntimeError("set LAVA_RES to the client's res directory")
        cls.data = load_json(DATA)
        cls.items = cls.data["items"]
        cls.objects = load_objects()
        cls.lines = load_json(os.path.join(HERE, "firearm_families.json"))["lines"]
        cls.manual = load_json(os.path.join(HERE, "firearm_lines_manual.json"))["lines"]
        cls.by_name = {n: t for t, (_, n) in cls.objects.items()}
        cls.line_types, cls.clan_types = {}, {}
        for line, rec in cls.lines.items():
            for key, t in rec["members"].items():
                cls.line_types[t] = (line, key)
            for key, t in rec["extra"].items():
                (cls.line_types if key == "A+mob" else cls.clan_types)[t] = (line, key)

    def name_of(self, type_id):
        rec = self.items.get(str(type_id))
        return rec and rec["name"]

    def line_name(self, line):
        return self.name_of(self.lines[line]["members"]["A"])

    # --- shape -----------------------------------------------------------------

    def test_meta_and_records(self):
        meta = self.data["_meta"]
        self.assertEqual(meta["source_md5"], SOURCE_MD5)
        self.assertEqual(meta["source_size"], SOURCE_SIZE)
        counts = {}
        for key, rec in self.items.items():
            self.assertEqual(set(rec), {"name", "desc", "name_id", "desc_id", "confidence", "root"}, key)
            self.assertIn(rec["confidence"], ("high", "medium"), key)
            root = self.objects[int(key)][0]
            self.assertEqual(rec["root"], B.ROOT_NAME[root], key)
            self.assertIsNotNone(rec["name"], key)
            for f in ("name", "desc"):
                self.assertEqual(rec[f] is None, rec[f + "_id"] is None, key)
            counts.setdefault(rec["root"], {}).setdefault(rec["confidence"], 0)
            counts[rec["root"]][rec["confidence"]] += 1
        self.assertEqual(meta["counts"], counts)

    def test_coverage(self):
        c = self.data["_meta"]["counts"]
        for root, n in MIN_TYPES.items():
            self.assertGreaterEqual(sum(c.get(root, {}).values()), n, root)
        self.assertGreaterEqual(c["FireArm"]["high"], MIN_FIREARM_HIGH)

    # --- firearm lines ---------------------------------------------------------

    def test_manual_lines(self):
        """Every hand-decided article of firearm_lines_manual.json names its line."""
        # 12, the 17 of the gun stalls of Вади-Хальфа (2026-09-28), and the 48
        # guns of 9-20 of the stalls by city level (2026-10-10)
        self.assertEqual(len(self.manual), 77)
        for article, rec in self.manual.items():
            name = self.line_name(rec["family"])
            self.assertIsNotNone(name, rec["family"])
            self.assertEqual(latin_c(base_name(name)), latin_c(article), rec["family"])
        for line, want in NAMED_LINES.items():
            self.assertEqual(base_name(self.line_name(line)), want, line)

    def test_zero_level(self):
        for line, want in ZERO_LEVEL.items():
            self.assertEqual(base_name(self.line_name(line)), want, line)

    def test_tokarev_is_not_pistols_2_lvl_6(self):
        """Without the std filter the [A][P][G] rows of "Тульский Токарева" (no [M],
        one description) count as a block and pistols_2_lvl_6 takes them."""
        self.assertEqual(self.objects[43777][1], "pistols_2_lvl_6")
        for t in self.lines["pistols_2_lvl_6"]["members"].values():
            self.assertNotIn("Тульский Токарев", self.name_of(t) or "", t)

    def test_line_is_one_gun(self):
        """All types of a line -- tiers, mods, the mob copy -- carry one gun name."""
        for line, rec in self.lines.items():
            names = {base_name(self.name_of(t)) for t in rec["members"].values()
                     if self.name_of(t)}
            self.assertLessEqual(len(names), 1, (line, names))

    def test_level_with_decimals(self):
        """MG 1_14 and 2_14 write their level as [14.00]."""
        for line in ("machine_gun_1_lvl_14", "machine_gun_2_lvl_14"):
            self.assertIn("[14.00]$Пулемет", self.line_name(line), line)

    def test_firearm_class_word(self):
        without = []
        for key, rec in self.items.items():
            if rec["root"] != "FireArm":
                continue
            t, obj = int(key), self.objects[int(key)][1]
            word = rec["name"].rsplit("$", 1)[1] if "$" in rec["name"] else None
            if t in self.line_types or obj.startswith(("USSR_", "NY2016_")):
                self.assertIn(word, SIX, (t, rec["name"]))
            elif t in self.clan_types:
                self.assertIn(word, SIX | CLAN_WORDS, (t, rec["name"]))
            else:
                without.append(t)
        self.assertLessEqual(len(without), MAX_FIREARM_WITHOUT_CLASS, without)

    def test_tier_marks(self):
        """_gold -> [G], _pm -> [P], _mob -> [M]; a +LeMon copy is the clan's [S] row."""
        for key, rec in self.items.items():
            if rec["root"] != "FireArm":
                continue
            obj = self.objects[int(key)][1]
            tags = re.findall(r"\[([^\]]*)\]", rec["name"].split("$")[0])
            if obj.endswith("_LeMon"):
                self.assertIn("S", tags, (obj, rec["name"]))
            elif re.search(r"_gold(_|$)", obj):
                self.assertIn("G", tags, (obj, rec["name"]))
            elif re.search(r"_pm(_|$)", obj):
                self.assertIn("P", tags, (obj, rec["name"]))
            elif re.search(r"_mob(_|$)", obj) and int(key) in self.line_types:
                self.assertIn("M", tags, (obj, rec["name"]))
            elif int(key) in self.line_types:
                self.assertTrue({"A", "Q", "RW"} & set(tags), (obj, rec["name"]))

    # --- other roots -------------------------------------------------------------

    def test_trophies(self):
        for obj, (row, name) in TROPHIES.items():
            rec = self.items[str(self.by_name[obj])]
            self.assertEqual((rec["name_id"], rec["desc_id"]), (row, row + 1), obj)
            self.assertEqual(rec["name"], name, obj)
            self.assertEqual(rec["confidence"], "high", obj)

    def test_heal_blocks(self):
        """Every Med_* type has its own block row, and the action points the
        wiki gives for it are the ones its original description states."""
        wiki = load_json(os.path.join(HERE, "items_wiki.json"))["items"]
        want = {"Med_Pacific_Heal_0_3_A": "Корень Маниока$Еда",
                "Med_Pacific_Heal_4_7_Ax10": "Фуль (10)$Еда",
                "Med_Pacific_Rest_0_3_A": "Пластиковая бутылка (10)$Вода",
                "Med_Pacific_HR_0_3_G": "Аптечка «Эгоист» (20) (G)$Лекарство",
                "Med_Battle_Rest_4_7_A": "«Караванщик»$Боевой Энергетик",
                "Med_Battle_HR_0_3_P": "Аптечка «Мини» (5) (P)$Боевая Медицина",
                "Med_Battle_HR_4_7_P": "Аптечка «Базовая» (5) (P)$Боевая Медицина",
                "Med_Battle_HR_0_3_G_Pack": "20 доз Б.Т.Р. (G)$Боевой инъектор",
                "shaurma": "Шаурма"}
        for name, text in want.items():
            rec = self.items[str(self.by_name[name])]
            self.assertEqual((rec["name"], rec["confidence"]), (text, "high"), name)
        med = [(t, n) for t, (r, n) in self.objects.items() if n.startswith("Med_")
               and re.search(r"_(0_3|4_7|8_11|12_15|16_19|20)_", n)]
        self.assertEqual(len(med), 55)
        for t, n in med:
            rec = self.items[str(t)]
            ap = re.search(r"Расход ОД: </b>(\d+)$", rec["desc"])
            self.assertTrue(ap, n)
            if str(t) in wiki and "heal_cost" in wiki[str(t)]:
                self.assertEqual(int(ap.group(1)), wiki[str(t)]["heal_cost"], n)
        pack = self.items[str(self.by_name["Med_Battle_HR_0_3_G_Pack"])]
        single = self.items[str(self.by_name["Med_Battle_HR_0_3_G"])]
        self.assertEqual(pack["desc_id"], single["desc_id"])

    def test_knife_line(self):
        """The shop knives by level: the plain copy unmarked, the gold one
        "(G)", each gold mod "(G)$<what was done to it>" -- never, as the
        wiki-name rule had it, a gold knife under its plain twin's row or both
        Тесак types under the sharpened copy's."""
        want = {"knife_lvl1_A": "Шило", "knife_lvl2_A": "Заточка",
                "knife_lvl2_G": "Самодельный Нож (G)",
                "knife_lvl2_G_damage": "Самодельный Нож (G)$Острый",
                "knife_lvl4_A": "Кухонный нож", "knife_lvl4_G": "Кухонный нож (G)",
                "knife_lvl6_A": "Тесак", "knife_lvl6_G": "Тесак (G)",
                "knife_lvl6_G_actionpoint": "Тесак (G)$Эргономичный",
                "knife_lvl8_A": "Охотничий нож", "knife_lvl8_G": "Охотничий нож (G)",
                "knife_lvl8_G_damage_actionpoints": "Охотничий нож (G)$Острый и Эргономичный",
                "knife_lvl20_A": "Мачете", "knife_lvl20_G": "Мачете (G)"}
        for name, text in want.items():
            rec = self.items[str(self.by_name[name])]
            self.assertEqual((rec["name"], rec["confidence"]), (text, "high"), name)
        n = 0
        for tid, (root, name) in self.objects.items():
            m = re.fullmatch(r"knife_lvl(\d+)_(A|G(?:_damage|_actionpoint|_damage_actionpoints)?)",
                             name)
            if not m or m.group(1) == "0":
                continue
            n += 1
            rec = self.items[str(tid)]
            tier = m.group(2)
            if tier == "A":
                self.assertNotIn("(G)", rec["name"], name)
            elif tier == "G":
                self.assertTrue(rec["name"].endswith(" (G)"), name)
                plain = self.items.get(str(self.by_name.get("knife_lvl%s_A" % m.group(1))))
                if plain and m.group(1) != "2":
                    self.assertEqual(rec["name"], plain["name"] + " (G)", name)
                    self.assertEqual(rec["desc_id"], plain["desc_id"], name)
            else:
                self.assertIn(" (G)$", rec["name"], name)
            self.assertTrue(rec["desc"] and len(rec["desc"]) > 30, name)
        # level 1 (A), level 2 (A, G, three mods), levels 4..20 (A, G, three mods)
        self.assertEqual(n, 1 + 5 + 9 * 5)

    def test_mine_loot(self):
        """What the Nubian mine's marauders drop, by its own rows: the bag of
        gold sand, and of the three emeralds the small ones -- each of the
        three by the row its internal name speaks of, never another's."""
        want = {"Gold_sand": (7352, 7353, "Золотой песок", "мешочек"),
                "small_emerald": (7243, 7244, "Небольшие изумруды", "ценятся торговцами")}
        for name, (nid, did, text, words) in want.items():
            rec = self.items.get(str(self.by_name[name]))
            self.assertIsNotNone(rec, name)
            self.assertEqual((rec["name_id"], rec["desc_id"], rec["name"], rec["confidence"]),
                             (nid, did, text, "high"), name)
            self.assertIn(words, rec["desc"], name)
        self.assertEqual((self.by_name["Gold_sand"], self.by_name["small_emerald"]), (2258, 3159))
        for name in ("cracked_emerald", "fine_emerald"):
            rec = self.items.get(str(self.by_name[name]))
            self.assertTrue(rec is None or rec["name_id"] not in (7243, 7352), name)

    def test_gold_ingots(self):
        """The ingots of 1, 5 and 10 ounces -- the 5-ounce one the Nubian
        valley's boss drops -- by the run 7636-7641, each by the row of its
        own denomination; the older Gold_Ingot_5/_10, whose icons draw a
        lollipop, by none of them."""
        want = {"New_Gold_Ingot_1": (7620, 7636, "1 унция золота",
                                     "Слиток номиналом в одну золотую унцию."),
                "New_Gold_Ingot_5": (4796, 7638, "5 унций золота",
                                     "Слиток номиналом в пять золотых унций."),
                "New_Gold_Ingot_10": (4797, 7640, "10 унций золота",
                                      "Слиток номиналом в десять золотых унций.")}
        for name, (tid, nid, text, desc) in want.items():
            self.assertEqual(self.by_name[name], tid, name)
            rec = self.items.get(str(tid))
            self.assertIsNotNone(rec, name)
            self.assertEqual((rec["name_id"], rec["desc_id"], rec["name"], rec["desc"],
                              rec["confidence"]), (nid, nid + 1, text, desc, "high"), name)
        for name in ("Gold_Ingot_5", "Gold_Ingot_10"):
            rec = self.items.get(str(self.by_name[name]))
            self.assertTrue(rec is None or not 7636 <= rec["name_id"] <= 7641, name)

    def test_ammo_quality_code(self):
        for key, rec in self.items.items():
            m = B.AMMO_TYPE.match(self.objects[int(key)][1])
            if rec["root"] == "Ammo" and m:
                tier, code = B.QUALITY[m.group(2)]
                self.assertIn("[%s]" % tier, rec["name"], key)
                self.assertTrue(rec["name"].endswith("$" + code), key)

    def test_wear_series(self):
        for key, rec in self.items.items():
            m = B.WEAR_TYPE.match(self.objects[int(key)][1])
            if rec["root"] == "WearItem" and m:
                series = m.group(2) + ("_U" if m.group(3) == "U" else "")
                if series in B.SET_SERIES:
                    self.assertIn(int(m.group(4)), B.SET_LEVELS, key)
                    self.assertFalse(m.group(6), key)
                else:
                    self.assertIn(series, B.WEAR_SERIES, key)

    def test_wear_sets(self):
        """Беженец, Колонист, Легионер / Красное ЭXO of levels 0-8: every piece,
        every tier and mod, named by its series' own word for its slot, with
        its tier and mod -- Колонист[2] by level 0's row -- and described."""
        n = 0
        for tid, (root, name) in self.objects.items():
            m = B.WEAR_TYPE.match(name)
            if not m or m.group(2) not in B.SET_SERIES or m.group(3) != "M" or m.group(6):
                continue
            slot, ser, _, level, tier, _, mod = m.groups()
            level = int(level)
            if level not in B.SET_LEVELS:
                continue
            n += 1
            rec = self.items.get(str(tid))
            self.assertIsNotNone(rec, name)
            word = B.set_words(ser, level)[B.WEAR_SLOTS.index(slot)]
            want_level = B.SET_BORROWED_LEVEL.get((ser, level), level)
            self.assertEqual(rec["name"].replace(word + " [", word + "["),
                             "%s[%d][%s][мод%s]" % (word, want_level, tier, mod), name)
            self.assertTrue(rec["desc"] and len(rec["desc"]) > 20, name)
            self.assertNotIn("<hint", rec["desc"], name)
        # 3 series x 8 levels (there is no level 1) x A/P/G x 11 mods x 5 slots
        self.assertEqual(n, 3 * 8 * 3 * 11 * 5)
        shirt = self.items[str(self.by_name["shirt_Set_M_LVL_5_G_mod07"])]
        self.assertTrue(shirt["desc"].startswith("Рубашка неизвестного происхождения"), shirt)
        red = self.items[str(self.by_name["armor_Exzo_M_LVL_7_P_mod00"])]
        self.assertEqual(red["name"], "Корпус Красное ЭXO[7][P][мод00]")

    # --- against the source ---------------------------------------------------------

    def source_or_skip(self):
        path = source_path()
        if not os.path.isfile(path):
            self.skipTest("no texts.xml at %s (set LAVA_ORIG_TEXTS)" % path)
        return path

    def test_texts_verbatim(self):
        """name/desc are the html-unescaped rows, untouched otherwise."""
        T, md5, _ = B.load_texts(self.source_or_skip())
        self.assertEqual(md5, SOURCE_MD5)
        for key, rec in self.items.items():
            for f in ("name", "desc"):
                if rec[f + "_id"] is not None:
                    self.assertEqual(rec[f], T[rec[f + "_id"]], (key, f))
        self.assertTrue(any("<Br><B>" in (r["desc"] or "") for r in self.items.values()))

    def test_wear_sets_not_quest_titles(self):
        """An upgrade quest is titled with the item's name; no set piece may
        take such a row, which the <hint> after it gives away."""
        T, _, _ = B.load_texts(self.source_or_skip())
        for key, rec in self.items.items():
            m = B.WEAR_TYPE.match(self.objects[int(key)][1])
            if m and m.group(2) in B.SET_SERIES:
                self.assertFalse(T[rec["name_id"] + 1].startswith("<hint"), key)

    def test_rebuild_is_byte_identical(self):
        """Two builds under different hash seeds and the committed file agree."""
        path = self.source_or_skip()
        digests = []
        with tempfile.TemporaryDirectory() as tmp:
            for seed in ("0", "1"):
                out = os.path.join(tmp, "orig_items_%s.json" % seed)
                env = dict(os.environ, PYTHONHASHSEED=seed, LAVA_ORIG_TEXTS=path, LAVA_RES=RES)
                subprocess.run([sys.executable, os.path.join(HERE, "build_orig_items.py"), out],
                               env=env, check=True, stdout=subprocess.DEVNULL)
                with open(out, "rb") as f:
                    digests.append(hashlib.sha256(f.read()).hexdigest())
        self.assertEqual(digests[0], digests[1])
        if self.data["_meta"]["source"] == path:
            with open(DATA, "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digests[0],
                                 "data/orig_items.json is stale: re-run build_orig_items.py")


if __name__ == "__main__":
    unittest.main()
