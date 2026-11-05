"""Socket fixtures follow placement and release frames without rewriting commands."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import testkit


@testkit.scene_client
class Client:
    def __init__(self):
        self.pending = []
        self.sent = []
    def frames(self, wait=0):
        out, self.pending = self.pending, []
        return out
    def send(self, text):
        self.sent.append(text)


class SocketFixtures(unittest.TestCase):
    def test_map_velocity_cannot_override_location_position(self):
        c = Client()
        c.pending = [('lcall', dict(id=100)), ('lenter', dict(pos=0)),
                     ('userMove', dict(id=1, dx=123, dy=456)),
                     ('lch', dict(newUser=7, pos=2)),
                     ('actionCancel', dict(id=7, pos=1))]
        c.frames()
        self.assertEqual((c.scene_id, c.scene_pos, c.scene_cells), (100, 0, {7: 1}))
        self.assertEqual(c.sent, [])

    def test_setup_approaches_occupied_hex_and_leaves_response_on_socket(self):
        c = Client()
        c.scene_id, c.scene_pos, c.scene_cells = 100, 0, {7: 2}
        loc = NS(id=100, width=20, height=20, obstacles=set())
        with patch('world.location', return_value=loc), patch('testkit.time.sleep') as wait:
            result = testkit.walk_to(c, 2)
        self.assertEqual(result, 1)
        self.assertEqual(c.sent, ['moveTo;path=|0|1|;'])
        wait.assert_called_once_with(0.25)

    def test_owner_release_wait_preserves_received_frames(self):
        c = Client()
        with patch('testkit.time.monotonic', return_value=10):
            c.pending = [('faShot', dict(id=0, status=0, recovery_ms=120))]
            c.frames()
        c.pending = [('usrUp', dict(id=1, hcur=10))]
        with patch('testkit.time.monotonic', side_effect=[10, 11]):
            self.assertEqual(testkit.wait_recovery(c), [('usrUp', dict(id=1, hcur=10))])
        self.assertEqual(c.sent, [])


if __name__ == '__main__':
    testkit.run_cases(SocketFixtures)
