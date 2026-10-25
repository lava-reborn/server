"""Missing A/G upgrades; runs without external client XML.

The A/G parity rule is the owner's request recorded in the branch report;
base/modification types come from firearm_families and items_wiki. The
builder's real numbering and service functions validate stable generation.

python server/test_weaponcraft_completion.py
"""
import ast
import collections
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from testkit import run_cases  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))

def function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]
spec = importlib.util.spec_from_file_location('completion', DATA / 'weaponcraft_completion.py')
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)

class WeaponcraftCompletion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = load('questgen_weaponcraft.json')
        cls.rows = [r for r in cls.doc['quests'] if r['craft']['family'] == 'upgrade']
        cls.added = [r for r in cls.rows if 'completion-' in r['craft']['key']]
        cls.wiki = load('items_wiki.json')['items']
        cls.families = load('firearm_families.json')['lines']
        craft_tree = ast.parse((ROOT / 'server/craft.py').read_text(encoding='utf-8'))
        cls.durability_corrections = next(
            ast.literal_eval(node.value) for node in craft_tree.body
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'DURABILITY_CORRECTIONS'
                for target in node.targets))
        tree = ast.parse((DATA / 'build_weaponcraft.py').read_text(encoding='utf-8'))
        cls.rules = {'collections': collections}
        for node in tree.body:
            if isinstance(node, ast.Assign) and any((isinstance(t, ast.Name) and t.id in {'CITIES', 'EFFECT_TITLE', 'FAMILIES'} for t in node.targets)):
                exec(compile(ast.Module(body=[node], type_ignores=[]), 'builder', 'exec'), cls.rules)
        for name in ('service', 'number'):
            function(DATA / 'build_weaponcraft.py', name, cls.rules)

    def test_all_active_named_mass_weapons_have_services(self):
        retired = load('retired.json')['items']
        covered = {r['craft']['gun'] for r in self.rows}
        for family in self.families.values():
            if family['index'] < 1:
                continue
            for line in ('A', 'G'):
                gun = family['members'].get(line)
                if str(gun) in self.wiki and str(gun) not in retired:
                    self.assertIn(gun, covered)

    def test_existing_and_completion_pairs_are_unique(self):
        pairs = [(r['craft']['gun'], r['craft']['effect']) for r in self.added]
        self.assertEqual(len(pairs), len(set(pairs)))
        old_pairs = {(r['craft']['gun'], r['craft']['effect']) for r in self.rows if r not in self.added}
        self.assertFalse(set(pairs) & old_pairs)
        self.assertEqual(len(self.added), 78)
        self.assertEqual(len({r['craft']['gun'] for r in self.added}), 27)
        self.assertEqual(len(self.doc['types']), len(set(self.doc['types'].values())))

    def test_regeneration_preserves_rows_and_types(self):
        baseline = [r for r in self.rows if not completion.owns_recipe(r)]
        expected = {(r['craft']['gun'], r['craft']['effect']): r for r in self.added}
        bp = {(r['craft']['effect'], r['craft'].get('blueprint_level', r['craft']['level']), r['craft']['line']): r['craft']['blueprint'] for r in self.rows}
        mods = {r['craft']['mod']: r['craft']['gun'] for r in self.added}

        def params(t):
            if t == 25015:
                return {'max_break_abs': 5500}
            return self.wiki.get(str(t)) or self.wiki[str(mods[t])]
        regenerated = []
        for city in self.rules['CITIES']:

            def camps(_city, level, chiefs_only):
                options = {tuple(o['mobs']) for r in self.added if r['craft']['key'].split(':')[1] == _city['name'] and r['craft'].get('blueprint_level', r['craft']['level']) == level for o in r['objs'] if 'mobs' in o}
                self.assertLessEqual(len(options), 1)
                return list(next(iter(options), ()))
            regenerated += completion.additions(city, baseline, blueprint=lambda e, l, v: bp[e, l, v], eligible=lambda t: t is not None, params=params, service=self.rules['service'], camp_mobs=camps, titles=self.rules['EFFECT_TITLE'])
        self.assertEqual(len(regenerated), len(expected))
        for row in regenerated:
            want = dict(expected[row['craft']['gun'], row['craft']['effect']])
            want.pop('type')
            self.assertEqual(row, want)
        fams = collections.OrderedDict(((f, []) for f in self.rules['FAMILIES']))
        for row in self.doc['quests']:
            clean = dict(row)
            clean.pop('type')
            fams[row['craft']['family']].append(clean)
        rows, types = self.rules['number'](fams, self.doc['types'])
        self.assertEqual(rows, self.doc['quests'])
        self.assertEqual(types, self.doc['types'])

    def test_blueprints_are_on_sale_at_relevant_stalls(self):
        stocks = load('npcs.json')['stock']
        classes = {t: {'pistols': 'pistol', 'assault_rifle': 'assault', 'shotgun': 'shotgun', 'sub_machine_guns': 'smg', 'machine_gun': 'mg'}.get(f['cls']) for f in self.families.values() for t in f['members'].values()}
        cities = {c['name']: c for c in self.rules['CITIES']}
        for row in self.added:
            c = row['craft']
            city = cities[c['key'].split(':')[1]]
            stalls = city['stalls'][classes[c['gun']]]
            self.assertTrue(stalls)
            for stall in stalls:
                self.assertIn(c['blueprint'], stocks[str(stall)])
            self.assertEqual((row['level'], row['max_level']), {'halfa': (0, 20), 'dongola': (9, 20), 'abu_hamed': (17, 20)}[city['name']])

    def test_desert_eagle_and_f2000_gold_match_afro_options(self):
        for a, g in ((25656, 25657), (25319, 25320)):
            effects = lambda gun: {r['craft']['effect'] for r in self.rows if r['craft']['gun'] == gun}
            self.assertEqual(effects(a), effects(g))

    def test_supported_afro_gold_counterparts_have_matching_services(self):
        retired = load('retired.json')['items']
        effects = collections.defaultdict(set)
        for row in self.rows:
            effects[row['craft']['gun']].add(row['craft']['effect'])
        for family in self.families.values():
            a, g = (family['members'].get('A'), family['members'].get('G'))
            if not all((str(t) in self.wiki and str(t) not in retired for t in (a, g))):
                continue
            for line, gun, other in (('A', a, g), ('G', g, a)):
                for effect in effects[other]:
                    if family['members'].get(line + ':' + effect) is not None:
                        self.assertIn(effect, effects[gun])

    def test_aug_durability_overlay(self):
        fake_items = SimpleNamespace(catalogue=lambda: {25015: (0, 'aug_mod')}, FIRE_ARM=0, TRASH=1)
        scope = {'DURABILITY_CORRECTIONS': self.durability_corrections, '_table': lambda: {},
                 'lay_stat_corrections': lambda *_args: None}
        lay_frame = function(ROOT / 'server/craft.py', 'lay_frame', scope)
        values = {'max_break_abs': 550}
        with patch.dict(sys.modules, {'items': fake_items}):
            lay_frame(25015, values, {'max_break_abs': 550})
        self.assertEqual(values['max_break_abs'], 2 * self.wiki['25006']['max_break_abs'])

    def test_bren_afro_and_gold_durability_doubles_after_wiki_overlay(self):
        fake_items = SimpleNamespace(
            catalogue=lambda: {25048: (0, 'bren_mod'), 25049: (0, 'bren_mod_gold')},
            FIRE_ARM=0, TRASH=1)
        scope = {'DURABILITY_CORRECTIONS': self.durability_corrections, '_table': lambda: {},
                 'lay_stat_corrections': lambda *_args: None}
        lay_frame = function(ROOT / 'server/craft.py', 'lay_frame', scope)
        with patch.dict(sys.modules, {'items': fake_items}):
            for base, mod in ((25039, 25048), (25040, 25049)):
                values = {'max_break_abs': self.wiki[str(mod)]['max_break_abs']}
                lay_frame(mod, values, self.wiki[str(mod)])
                self.assertEqual(values['max_break_abs'], self.wiki[str(base)]['max_break_abs'] * 2)

    def test_durability_blueprints_never_grant_tenfold_durability(self):
        # Wiki values remain evidence; AUG's explicit correction is checked
        # through lay_frame above. Table-less modifications use EFFECTS x2.
        ratios = []
        for row in self.rows:
            c = row['craft']
            if c['effect'] != 'attrition_x2':
                continue
            base = self.wiki[str(c['gun'])]['max_break_abs']
            upgraded = self.durability_corrections.get(
                c['mod'], self.wiki.get(str(c['mod']), {}).get('max_break_abs', base * 2))
            ratios.append(upgraded / base)
            self.assertLessEqual(upgraded / base, 2.5, (c['gun'], c['mod']))
        self.assertGreater(len(ratios), 70)

    def test_each_completion_works_through_real_upgrade_handler(self):
        inventory = SimpleNamespace(RES_NOT_FOUND=12, RES_REFUSED=11, RES_OK=0)
        items = SimpleNamespace(FIRE_ARM=0)
        setcraft = SimpleNamespace(pass_wear=Mock())
        scope = {'log': Mock(), 'wear_of': lambda row: (3, 10, 10)}
        upgrade = function(ROOT / 'server/craft.py', 'upgrade', scope)
        with patch.dict(sys.modules, {'inventory': inventory, 'items': items, 'setcraft': setcraft}):
            for recipe in self.added:
                c = recipe['craft']
                q = SimpleNamespace(level=recipe['level'], over_cap=lambda level: level > 20)
                scope['recipes_of'] = lambda master: [(q, c['gun'], c['mod'], c['blueprint'])] if master == recipe['give'][0] else []
                inv = Mock()
                inv.bag_pieces.return_value = {c['blueprint']: 1}
                inv.give_pieces.return_value = [{'uniq': 102}]
                sess = SimpleNamespace(inv=inv, skill_level=lambda: recipe['level'])
                row = dict(type_id=c['gun'], uniq=100, root=0, brk=3, max_break_cur=10)
                upgrade(sess, recipe['give'][0], row, c['mod'])
                inv.ack.assert_called_once_with(0)
                inv.take_pieces.assert_called_once_with(c['blueprint'], 1)
                inv.give_pieces.assert_called_once_with(c['mod'], 1)
                inv.reset_mock()
                inv.bag_pieces.return_value = {}
                upgrade(sess, recipe['give'][0], row, c['mod'])
                inv.ack.assert_called_once_with(11)
                inv.store.delete_item.assert_not_called()
                inv.reset_mock()
                upgraded = dict(row, type_id=c['mod'])
                upgrade(sess, recipe['give'][0], upgraded, c['mod'])
                inv.ack.assert_called_once_with(12)
                inv.take_pieces.assert_not_called()
if __name__ == '__main__':
    run_cases(WeaponcraftCompletion)
