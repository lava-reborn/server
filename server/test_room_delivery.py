"""A broken spectator must not interrupt a room's movement or combat fact."""
import unittest
from types import SimpleNamespace as NS

import rooms
from testkit import run_cases


class RoomDelivery(unittest.TestCase):
    def test_one_broken_transport_does_not_truncate_viewer_frames(self):
        delivered, closed = [], []
        class Seat:
            def __init__(self, pid, broken=False):
                self.pid, self.broken = pid, broken
                self.writer = NS(close=lambda: closed.append(pid))
            def send(self, command, **params):
                if self.broken:
                    raise BrokenPipeError('stale room spectator')
                delivered.append((self.pid, command, params))
        owner, stale, observer = Seat(1000001), Seat(1000002, True), Seat(1000003)
        room = NS(players={owner: True, stale: True, observer: True})
        for command, params in (
            ('userMove', dict(id=owner.pid, path=[1, 2], step_ms=75)),
            ('faShot', dict(id=owner.pid, status=1)),
            ('faHit', dict(target=observer.pid, dmg=10)),
            ('faShot', dict(id=owner.pid, status=0)),
        ):
            rooms.Room.broadcast(room, (command, params))
        self.assertEqual([c for pid, c, p in delivered if pid == owner.pid],
                         ['userMove', 'faShot', 'faHit', 'faShot'])
        self.assertEqual([c for pid, c, p in delivered if pid == observer.pid],
                         ['userMove', 'faShot', 'faHit', 'faShot'])
        self.assertEqual(delivered[0][2]['id'], 0)
        self.assertEqual(delivered[1][2]['id'], owner.pid)
        self.assertEqual(delivered[4][2]['target'], observer.pid)
        self.assertEqual(delivered[5][2]['target'], 0)
        self.assertEqual(set(closed), {stale.pid})


if __name__ == '__main__':
    run_cases(RoomDelivery)
