"""Checks of data/orig_npcs.json, the original names of NPCs and mobs.

    MSYS_NO_PATHCONV=1 wsl.exe -e bash -lc "cd /mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server && LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/test_orig_npcs.py"

The file alone is enough for the format, the "Тест" guard, the generated
block and the hand-checked anchors. With LAVA_RES the kinds are checked
against mobs.xml; with the original texts.xml (LAVA_ORIG_TEXTS, default
/mnt/c/Users/gmkrt/Downloads/texts.xml) every name is compared with the
original string, and the builder is run again (about two minutes) to show
that it gives the same bytes: the launcher of every player compares a digest
of the string table, so the file must not change from run to run.
"""
import html
import json
import os
import re
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

PATH = os.path.join(HERE, "orig_npcs.json")
SOURCE = os.environ.get("LAVA_ORIG_TEXTS") or "/mnt/c/Users/gmkrt/Downloads/texts.xml"
SOURCE_MD5 = "7a10e992003480a76546b6c824b3dbc2"
SOURCE_SIZE = 20433511
GENERATED = range(9182, 9446)

# Checked by hand before this file existed: type_id -> (string_id, part of the text).
ANCHORS = {
    5212: (10437, "Борис<Br>Пистолеты и патроны"),
    5221: (10446, "Шульц<Br>Пистолеты и патроны"),
    5216: (10441, "Адам<Br>старший помощник"),
    5215: (10440, "Доктор Гофус<Br>Специальное снаряжение"),
    5140: (10389, "Ибн Сина<Br>Лекарь"),
    5198: (10386, "Фая<Br>Аренда транспорта"),
    5211: (10436, "Морис<Br>Еда и Медикаменты"),
    5122: (9637, "Кондрат<Br>Пилот"),
    5146: (9640, "Жрец Тефнут"),
    5189: (9645, "Сорванец"),
    5192: (9648, "Точильный камень"),
    5195: (9651, "Корова"),
    1682: (46953, "Кукуруза"),
}
# Types the recon named with a "Тестовый ..." string although they spawn.
SPAWNED_TEST_TYPES = ("5320", "8289")   # KKND_Npc_Commoner000000, VOV_Npc_Lessor000000

# Reached on the 2026-09-23 build; lower only with a reason. Raised on
# 2026-09-28 with Вади-Хальфа's names (orig_names_manual.json), which took 57
# of the matcher's medium guesses into "npcs" by hand: "suggest" fell by as
# many, from 726 to 667 (the last two, 7021 and 7548, by their family's own
# offset instead of the matcher's).
MIN_NPCS = 679
MIN_NPC_KIND = 371
MIN_MOB_KIND = 308
# The prison's staff by hand (the events package): Томас 876 was the
# matcher's medium guess, one less. And the ДСР stand-ins of «Механик ДСР»
# by hand at the integration of 2026-09-28: 51 was the matcher's medium
# «[4] Связной<Br>Джанджавиды», one less again. Абри's people by hand
# (2026-10-12, the owner's «Делаем Абри»): 26 of the matcher's medium guesses
# went into "npcs" -- the market's traders (Одноухий, Алима, Гали), Дед
# Кузин, Говард Хаксли, the Кучка песка, Санденс Кид, the slave traders' and
# flayers' ranks the matcher had from another block, the crocodile and the
# Амазонка -- and "suggest" fell from 665 to 639.
MIN_SUGGEST = 639


def canonical(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")


def starts_with_test(text):
    low = text.lower()
    return low.startswith("тест") or bool(re.match(r"\[\d+\]\s*тест", low))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_doc():
    return json.loads(read_bytes(PATH).decode("utf-8"))


def load_original():
    raw = read_bytes(SOURCE)
    texts = {int(m.group(1)): html.unescape(m.group(2))
             for m in re.finditer(r'<item id="(\d+)">(.*?)</item>', raw.decode("utf-8"), re.S)}
    return raw, texts


def res_dir():
    res = os.environ.get("LAVA_RES") or ""
    return res if os.path.isfile(os.path.join(res, "database", "mobs.xml")) else None


class Format(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = read_bytes(PATH)
        cls.doc = json.loads(cls.raw.decode("utf-8"))
        cls.npcs = cls.doc["npcs"]
        cls.suggest = cls.doc["suggest"]

    def test_canonical_bytes(self):
        """sort_keys, indent=1, ensure_ascii=False: the same content is always the same bytes."""
        self.assertEqual(self.raw, canonical(self.doc))

    def test_shape(self):
        self.assertEqual(set(self.doc), {"_meta", "npcs", "suggest"})
        meta = self.doc["_meta"]
        self.assertEqual(set(meta), {"source", "source_md5", "source_size", "rule", "counts"})
        self.assertEqual(meta["source_md5"], SOURCE_MD5)
        self.assertEqual(meta["source_size"], SOURCE_SIZE)
        for k, v in self.npcs.items():
            self.assertEqual(k, str(int(k)))
            self.assertEqual(set(v), {"name", "string_id", "kind", "confidence"}, k)
            self.assertEqual(v["confidence"], "high", k)
            self.assertIn(v["kind"], ("npc", "mob"), k)
            self.assertIsInstance(v["string_id"], int, k)
            self.assertTrue(v["name"], k)
        for k, v in self.suggest.items():
            self.assertEqual(k, str(int(k)))
            self.assertEqual(set(v), {"name", "string_id", "confidence"}, k)
            self.assertEqual(v["confidence"], "medium", k)
            self.assertIsInstance(v["string_id"], int, k)
            self.assertTrue(v["name"], k)
        self.assertEqual(set(self.npcs) & set(self.suggest), set())

    def test_counts(self):
        c = self.doc["_meta"]["counts"]
        kinds = [v["kind"] for v in self.npcs.values()]
        self.assertEqual(c["npcs"], len(self.npcs))
        self.assertEqual(c["npcs_npc"], kinds.count("npc"))
        self.assertEqual(c["npcs_mob"], kinds.count("mob"))
        self.assertEqual(c["suggest"], len(self.suggest))
        self.assertGreaterEqual(len(self.npcs), MIN_NPCS)
        self.assertGreaterEqual(kinds.count("npc"), MIN_NPC_KIND)
        self.assertGreaterEqual(kinds.count("mob"), MIN_MOB_KIND)
        self.assertGreaterEqual(len(self.suggest), MIN_SUGGEST)

    def test_no_test_strings(self):
        """No "Тестовый аукцион" over a head in the world, not even as a hint."""
        for part in (self.npcs, self.suggest):
            bad = {k: v["name"] for k, v in part.items() if starts_with_test(v["name"])}
            self.assertEqual(bad, {})
        for t in SPAWNED_TEST_TYPES:
            self.assertNotIn(t, self.npcs)
            self.assertNotIn(t, self.suggest)

    def test_generated_block_unused(self):
        for part in (self.npcs, self.suggest):
            used = {k: v["string_id"] for k, v in part.items() if v["string_id"] in GENERATED}
            self.assertEqual(used, {})

    def test_anchors(self):
        for t, (sid, fragment) in ANCHORS.items():
            got = self.npcs.get(str(t))
            self.assertIsNotNone(got, t)
            self.assertEqual(got["string_id"], sid, t)
            self.assertIn(fragment, got["name"], t)
        self.assertEqual(self.npcs["5212"]["name"], "Борис<Br>Пистолеты и патроны")
        self.assertEqual(self.npcs["5146"]["name"], "Ирже Котунц<Br>Жрец Тефнут")

    def test_warehouse_flag_caption(self):
        """The warehouses' flag 1011 by hand (orig_names_manual.json): the
        original's caption 46362 «Складом владеют:», over the holding clan's
        name (server/holdings.py), no longer the item row's 'Флаг' (7495)."""
        self.assertEqual(self.npcs["1011"], {"name": "Складом владеют:", "string_id": 46362,
                                             "kind": "npc", "confidence": "high"})

    def test_text_left_as_is(self):
        """Formatting is the server's job: '<Br>' and '[N] ' prefixes stay."""
        names = [v["name"] for v in self.npcs.values()]
        self.assertTrue(any("<Br>" in n for n in names))
        # Rows chosen by hand (orig_names_manual.json) are the file's text as
        # it is, and some of them never had a level. The level goes on the
        # wire either way (orig_texts.person_name, the owner's 2026-10-12).
        hand = set(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "orig_names_manual.json"),
                                  encoding="utf-8"))["types"])
        mobs = [v["name"] for k, v in self.npcs.items() if v["kind"] == "mob" and k not in hand]
        self.assertTrue(mobs and all(re.match(r"\[\d+\] ?", n) for n in mobs))
        self.assertFalse(any("&lt;" in n or "&gt;" in n or "&quot;" in n for n in names))


@unittest.skipUnless(res_dir(), "LAVA_RES does not point at the client's res folder")
class AgainstClient(unittest.TestCase):
    def test_kinds_match_mobs_xml(self):
        import world
        types = world.mob_types()
        doc = read_doc()
        for k, v in doc["npcs"].items():
            self.assertIn(int(k), types, k)
            self.assertEqual(v["kind"] == "mob", types[int(k)][0] == world.MOB, k)
        for k in doc["suggest"]:
            self.assertIn(int(k), types, k)


@unittest.skipUnless(os.path.isfile(SOURCE), "original texts.xml not found (LAVA_ORIG_TEXTS)")
class AgainstOriginal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.texts = load_original()
        cls.doc = read_doc()

    def test_source_is_the_one_in_meta(self):
        import hashlib
        self.assertEqual(hashlib.md5(self.raw).hexdigest(), self.doc["_meta"]["source_md5"])
        self.assertEqual(len(self.raw), self.doc["_meta"]["source_size"])

    def test_names_are_original_texts(self):
        for part in ("npcs", "suggest"):
            for k, v in self.doc[part].items():
                self.assertEqual(v["name"], self.texts[v["string_id"]], "%s %s" % (part, k))

    def test_generated_block_is_generated(self):
        """9182-9445 is an alphabetical list whose level cycles 1..20: not names of anyone."""
        for i in GENERATED:
            self.assertTrue(self.texts[i].startswith("[%d]" % ((i - 9182) % 20 + 1)), i)

    @unittest.skipUnless(res_dir(), "LAVA_RES does not point at the client's res folder")
    def test_rebuild_gives_same_bytes(self):
        import build_orig_npcs
        doc, _ = build_orig_npcs.build(SOURCE)
        self.assertEqual(canonical(doc), read_bytes(PATH))


if __name__ == "__main__":
    unittest.main(verbosity=2)
