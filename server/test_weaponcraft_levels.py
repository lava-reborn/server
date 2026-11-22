"""Recipe-level access and generated metadata."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import inventory

ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class BlueprintLevels(unittest.TestCase):
    def test_same_recipe_has_same_access_in_every_city(self):
        service = load_function(ROOT / 'data/build_weaponcraft.py', 'service')
        for city, band in (('halfa', (0, 8)), ('abri', (8, 12)),
                           ('dongola', (9, 16)), ('abu_hamed', (17, 20))):
            for family in ('upgrade', 'knife', 'decode'):
                for required, minimum in ((1, 0), (3, 0), (4, 1), (15, 12), (16, 13), (20, 17)):
                    with self.subTest(city=city, family=family, required=required):
                        with patch.object(inventory, 'item_level', return_value=required):
                            row = service(dict(name=city, band=band),
                                          dict(craft=dict(family=family, level=required, mod=1)))
                        self.assertEqual((row['level'], row['max_level']), (minimum, 20))
            for family in ('salvage', 'assembly'):
                row = service(dict(name=city, band=band), dict(craft=dict(family=family)))
                self.assertEqual((row['level'], row['max_level']), band)

    def test_published_recipes_match_builder_and_allow_exactly_plus_three(self):
        service = load_function(ROOT / 'data/build_weaponcraft.py', 'service')
        over_cap = load_function(ROOT / 'server/quests.py', 'over_cap')
        bands = dict(valley=(0, 4), halfa=(0, 8), abri=(8, 12), dongola=(9, 16), abu_hamed=(17, 20))
        rows = json.loads((ROOT / 'data/questgen_weaponcraft.json').read_text(encoding='utf-8'))['quests']
        for row in rows:
            recipe = row['craft']
            city = recipe['key'].split(':')[1]
            generated = service(dict(name=city, band=bands[city]), dict(craft=recipe))
            with self.subTest(quest=row['type']):
                self.assertEqual((row['level'], row['max_level']), (generated['level'], generated['max_level']))
                if recipe['family'] not in ('upgrade', 'knife', 'decode'):
                    continue
                required = recipe['level'] if recipe['family'] == 'decode' else inventory.item_level(recipe['mod'])
                for level in range(22):
                    allowed = row['level'] <= level and not over_cap(SimpleNamespace(max_level=row['max_level']), level)
                    self.assertEqual(allowed, level <= 20 and required <= level + 3)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(BlueprintLevels)
