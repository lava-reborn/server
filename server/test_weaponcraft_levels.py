"""Blueprint level boundaries without external client resource files.

Run: python -m unittest discover -s server -p test_weaponcraft_levels.py
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name):
    """Load an independent rule without importing resource-dependent modules."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class BlueprintLevels(unittest.TestCase):
    def test_service_ranges_for_every_city_and_family(self):
        service = load_function(ROOT / "data/build_weaponcraft.py", "service")
        recipe_bands = {"valley": (0, 4), "halfa": (0, 8), "abri": (8, 12),
                        "dongola": (9, 16), "abu_hamed": (17, 20)}
        player_bands = {"halfa": (0, 20), "abri": (6, 20),
                        "dongola": (9, 20), "abu_hamed": (17, 20)}
        for city, band in recipe_bands.items():
            for family in ("upgrade", "knife", "decode", "salvage", "assembly"):
                with self.subTest(city=city, family=family):
                    data = {"name": city, "band": band}
                    row = service(data, {"craft": {"family": family}})
                    expected = player_bands.get(city, band) if family in (
                        "upgrade", "knife", "decode") else band
                    self.assertEqual((row["level"], row["max_level"]), expected)
                    self.assertEqual(data["band"], band)

    def test_generated_rows_and_boundaries(self):
        service = load_function(ROOT / "data/build_weaponcraft.py", "service")
        over_cap = load_function(ROOT / "server/quests.py", "over_cap")
        bands = {"valley": (0, 4), "halfa": (0, 8), "abri": (8, 12),
                 "dongola": (9, 16), "abu_hamed": (17, 20)}
        rows = json.loads((ROOT / "data/questgen_weaponcraft.json").read_text(
            encoding="utf-8"))["quests"]
        covered = set()
        for row in rows:
            city = row["craft"]["key"].split(":")[1]
            family = row["craft"]["family"]
            lo, hi = bands[city]
            if city in ("halfa", "abri", "dongola", "abu_hamed") and family in ("upgrade", "knife", "decode"):
                lo, hi = (6 if city == "abri" else lo), 20
                covered.add((city, family))
            with self.subTest(quest=row["type"]):
                generated = service({"name": city, "band": bands[city]},
                                    {"craft": row["craft"]})
                self.assertEqual((row["level"], row["max_level"]), (lo, hi))
                self.assertEqual((generated["level"], generated["max_level"]), (lo, hi))
                quest = SimpleNamespace(max_level=row["max_level"])
                for level in (lo - 1, lo, 5, 6, 7, 8, 9, 12, 13, 16, 17, 20, 21):
                    available = row["level"] <= level and not over_cap(quest, level)
                    self.assertEqual(available, lo <= level <= hi)
        self.assertEqual(covered, {(city, family)
                         for city in ("halfa", "dongola", "abu_hamed")
                         for family in ("upgrade", "knife", "decode")} | {("abri", "knife")})


if __name__ == "__main__":
    unittest.main()
