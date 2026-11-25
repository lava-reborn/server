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
