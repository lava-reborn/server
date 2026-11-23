"""Eight-direction aiming geometry; no rooms, actions or model battles."""
import unittest

import mobs
from testkit import run_cases


class AimFacing(unittest.TestCase):
    def test_all_eight_directions_on_both_hex_row_parities(self):
        width = 64
        for row in (4, 5):
            origin = row * width + 5
            # Pick the adjacent left/right diagonal on either row parity.
            right = row % 2
            offsets = {8: 1, 4: -1, 2: 2 * width, 6: -2 * width,
                       1: width + right, 3: width + right - 1,
                       7: -width + right, 5: -width + right - 1}
            for direction, offset in offsets.items():
                with self.subTest(row=row, direction=direction):
                    self.assertEqual(mobs.direction(origin, origin + offset, width), direction)

    def test_only_same_position_keeps_the_previous_facing(self):
        for width in (1, 32, 64, 128):
            for row in (4, 5):
                origin = row * width
                with self.subTest(width=width, row=row):
                    self.assertEqual(mobs.direction(origin, origin, width), 0)
                    self.assertEqual(mobs.direction(origin, origin + 2 * width, width), 2)
                    self.assertEqual(mobs.direction(origin, origin - 2 * width, width), 6)


if __name__ == '__main__':
    run_cases(AimFacing)
