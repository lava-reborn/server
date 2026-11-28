"""Only verified complete bush footprints become shoot-through cover.

Movement still reads the original obstacle set. Unknown scenery and walls
keep priority; changing an id or a collision template cannot open a wall.
"""
import os
import unittest
from unittest.mock import patch

import world
from testkit import run_cases


class BushCover(unittest.TestCase):
    even = {(9, 9), (10, 9), (9, 10), (10, 10), (11, 10), (9, 11), (10, 11)}
    odd = {(10, 10), (11, 10), (9, 11), (10, 11), (11, 11), (10, 12), (11, 12)}

    def xml(self, anchor=(10, 10), cells=None, extra="", bush_id="LN_plant32.png",
            kind="ext", library="Desert", front="7f8080808180"):
        if cells is None:
            points = self.odd if anchor[1] % 2 else self.even
            cells = {p: "3" if p == anchor else "2" for p in points}
        obstacles = "".join("%02x%02x%s" % (x, y, code) for (x, y), code in sorted(cells.items()))
        return ('<location title="fixture" width="20" height="20" library="%s" war="1">'
                '<sprite id="%s" type="%s" front="%s">%02x%02x</sprite>%s'
                '<obstacles>%s</obstacles><inzones>0101</inzones><mobs></mobs></location>'
                % (library, bush_id, kind, front, *anchor, extra, obstacles))

    def load(self, text):
        with patch.object(world, "path_for", return_value="locations/static/2000.xml"), \
                patch.object(world, "_read", return_value=text):
            return world.Location(2000)

    def packed(self, cells):
        return frozenset(y * 20 + x for x, y in cells)

    def test_complete_bush_keeps_all_seven_movement_obstacles(self):
        loc = self.load(self.xml())
        self.assertIsInstance(loc.bushes, frozenset)
        self.assertEqual(loc.bushes, self.packed(self.even))
        self.assertEqual(loc.obstacles, self.packed(self.even))
        self.assertEqual(loc.shoot_over, frozenset())
        self.assertNotIn(loc.entry_cell(), loc.obstacles)

    def test_odd_row_footprint_uses_hex_offset_coordinates(self):
        loc = self.load(self.xml(anchor=(10, 11)))
        self.assertEqual(loc.bushes, self.packed(self.odd))
        self.assertEqual(loc.obstacles, self.packed(self.odd))

    def test_depth_front_does_not_define_the_bush_footprint(self):
        loc = self.load(self.xml(front="8080"))
        self.assertEqual(loc.bushes, self.packed(self.even))

    def test_incomplete_or_changed_collision_template_remains_hard(self):
        for changed in (None, "1", "f", "4"):
            cells = {p: "3" if p == (10, 10) else "2" for p in self.even}
            if changed is None:
                cells.pop((9, 9))
            else:
                cells[(9, 9)] = changed
            with self.subTest(code=changed):
                loc = self.load(self.xml(cells=cells))
                self.assertEqual(loc.bushes, frozenset())
                self.assertEqual(loc.obstacles, self.packed(cells))

    def test_tree_stone_unknown_and_library_alias_cannot_be_softened(self):
        for name in ("LN_tree01.png", "DN_stones23.png", "future_object.png"):
            extra = '<sprite id="%s" type="ext" front="8080">0a0a</sprite>' % name
            with self.subTest(name=name):
                loc = self.load(self.xml(extra=extra))
                self.assertEqual(loc.bushes, frozenset())
                self.assertEqual(loc.obstacles, self.packed(self.even))
        self.assertEqual(self.load(self.xml(kind="lib")).bushes, frozenset())
        self.assertEqual(self.load(self.xml(bush_id="LN_plant29.png")).bushes, frozenset())

    def test_unknown_scenery_box_protects_overlap_away_from_its_anchor(self):
        # The tree is anchored at (13,10); its depth contour reaches (11,10).
        # Its conservative reserved box touches the bush at (11,10).
        extra = '<sprite id="LN_tree01.png" type="ext" front="7e808080">0d0a</sprite>'
        self.assertEqual(self.load(self.xml(extra=extra)).bushes, frozenset())

    def test_unrelated_hard_scenery_does_not_disable_an_isolated_bush(self):
        extra = '<sprite id="DN_stones23.png" type="ext" front="8080">0202</sprite>'
        loc = self.load(self.xml(extra=extra))
        self.assertEqual(loc.bushes, self.packed(self.even))

    def test_verified_low_vegetation_does_not_hide_bush_or_soften_its_own_cells(self):
        for kind, name, library in (("ext", "LN_plant05.png", "Desert"),
                                    ("ext", "LN_plant06.png", "Desert"),
                                    ("lib", "plant05.png", "Desert"),
                                    ("lib", "bush1.png", "OW_Jungle_2")):
            extra = '<sprite id="%s" type="%s" front="80808180">0a0a</sprite>' % (name, kind)
            with self.subTest(kind=kind, name=name, library=library):
                loc = self.load(self.xml(extra=extra, library=library))
                self.assertEqual(loc.bushes, self.packed(self.even))
                self.assertEqual(loc.obstacles, self.packed(self.even))
                # The same artwork alone still lacks a verified footprint.
                self.assertEqual(self.load(self.xml(kind=kind, bush_id=name,
                                                    library=library)).bushes, frozenset())

    def test_unverified_library_alias_of_low_vegetation_still_protects_hard_cover(self):
        for library in ("MKS_Desert", "Graveyards_Ghost", "future_library"):
            extra = '<sprite id="plant05.png" type="lib" front="80808180">0a0a</sprite>'
            self.assertEqual(self.load(self.xml(extra=extra, library=library)).bushes, frozenset())

    def test_low_vegetation_never_overrides_stone_or_wall_priority(self):
        grass = '<sprite id="LN_plant05.png" type="ext" front="8080">0a0a</sprite>'
        stone = '<sprite id="DN_stones23.png" type="ext" front="8080">0a0a</sprite>'
        self.assertEqual(self.load(self.xml(extra=grass + stone)).bushes, frozenset())
        text = self.xml(extra=grass).replace('</obstacles>', '0a0af</obstacles>')
        self.assertEqual(self.load(text).bushes, frozenset())

    def test_duplicate_wall_code_cannot_be_hidden_by_a_bush_code(self):
        text = self.xml().replace('</obstacles>', '0a0af</obstacles>')
        self.assertEqual(self.load(text).bushes, frozenset())

    def test_malformed_or_out_of_bounds_footprint_keeps_obstacles_hard(self):
        malformed = self.xml().replace('>0a0a</sprite>', '>0a0</sprite>')
        self.assertEqual(self.load(malformed).bushes, frozenset())
        cells = {(0, 0): "3", (1, 0): "2", (0, 1): "2"}
        self.assertEqual(self.load(self.xml(anchor=(0, 0), cells=cells)).bushes, frozenset())

    def test_sides_foliage_collision_variants_keep_both_hex_parities_and_heights(self):
        # Independent fixtures recovered from isolated native placements:
        # a tuft, both reed orientations and two tall-grass size variants.
        fixtures = ((3, (((0, 0),),)),
                    (4, (((0, 0), (0, 1)), ((0, 0), (1, 0)))),
                    (5, (((-1, -1), (0, -1), (0, 0)),
                         ((-1, -1), (0, -2), (0, -1), (0, 0)))))
        for number, shapes in fixtures:
            for shape in shapes:
                for ay in (10, 11):
                    for code in ("2", "3", "4"):
                        with self.subTest(plant=number, shape=shape, row=ay, code=code):
                            cells = {(10 + dx + (1 if ay % 2 and dy % 2 else 0), ay + dy): code
                                     for dx, dy in shape}
                            loc = self.load(self.xml(anchor=(10, ay), cells=cells,
                                bush_id="plant%02d.png" % number, kind="lib", library="Sides"))
                            self.assertEqual(loc.bushes, self.packed(cells))
                            self.assertEqual(loc.obstacles, self.packed(cells))

    def test_sides_foliage_never_opens_hard_scenery_or_another_library(self):
        fixtures = {"plant03.png": ((0, 0),),
                    "plant05.png": ((-1, -1), (0, -1), (0, 0)),
                    "plant13.png": ((-1, -1), (-1, 0), (0, -1), (0, 0), (0, 1), (1, 0))}
        for plant, shape in fixtures.items():
            cells = {(10 + dx, 10 + dy): "2" for dx, dy in shape}
            base = self.xml(cells=cells, bush_id=plant, kind="lib", library="Sides")
            for name in ("rock22.png", "palm01.png", "future_scenery.png"):
                extra = '<sprite id="%s" type="lib" front="8080">0a0a</sprite>' % name
                self.assertFalse(self.load(base.replace('<obstacles>', extra + '<obstacles>')).bushes)
            self.assertFalse(self.load(base.replace('library="Sides"', 'library="Desert"')).bushes)
            self.assertFalse(self.load(base.replace('type="lib"', 'type="ext"')).bushes)
            self.assertFalse(self.load(base.replace('</obstacles>', '0a0af</obstacles>')).bushes)

    def test_incomplete_or_unsupported_sides_footprints_stay_hard(self):
        for cells in ({(10, 10): "1"}, {(10, 10): "f"}, {(10, 10): "2"}):
            loc = self.load(self.xml(cells=cells, bush_id="plant05.png", kind="lib", library="Sides"))
            self.assertFalse(loc.bushes)
            self.assertEqual(loc.obstacles, self.packed(cells))

    def test_every_original_coast_has_verified_soft_foliage_without_opening_walls(self):
        for loc_id in (17,18,19,20,21,22,23,24,38,39,54,55,56,57):
            with self.subTest(location=loc_id):
                loc = world.location(loc_id)
                txt = world._read(world.path_for(loc_id))
                original = {loc._cell(c) for c in world._chunks(txt, "obstacles", 5)}
                walls = {loc._cell(c) for c in world._chunks(txt, "obstacles", 5)
                         if c[4].lower() not in ("2", "3", "4")}
                self.assertTrue(loc.bushes)
                self.assertLessEqual(loc.bushes, original)
                self.assertTrue(loc.bushes.isdisjoint(walls))
                self.assertEqual(loc.obstacles, original)

    def test_real_original_bushes_are_obstacles_with_the_verified_material_codes(self):
        path = os.path.join(world.RES, 'locations', 'static', '1304.xml')
        if not os.path.isfile(path):
            self.skipTest('Original location 1304.xml not installed')
        with patch.object(world, 'path_for', return_value=path):
            loc = world.Location(1304)
        text = world._read(path)
        original = {loc._cell(c) for c in world._chunks(text, 'obstacles', 5)}
        wall_cells = {loc._cell(c) for c in world._chunks(text, 'obstacles', 5) if c[4].lower() == 'f'}
        self.assertTrue(loc.bushes)
        self.assertEqual(loc.obstacles, original)
        self.assertLessEqual(loc.bushes, original)
        self.assertTrue(loc.bushes.isdisjoint(wall_cells))
        self.assertIn(64 * loc.width + 32, loc.bushes)


if __name__ == '__main__':
    run_cases(BushCover)
