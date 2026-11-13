"""A broken spectator must not interrupt a room's movement or combat fact."""
import unittest
from types import SimpleNamespace as NS

import rooms
from testkit import run_cases


class RoomDelivery(unittest.TestCase):
    def test_programming_errors_are_not_disguised_as_a_disconnected_player(self):
        closed = []
        def invalid(*_args,**_kwargs):
            raise TypeError('invalid event construction')
        sess = NS(writer=NS(close=lambda:closed.append(True)),send=invalid)
        with self.assertRaises(TypeError):
            rooms.send_to(sess,'online',dict(count=2))
        self.assertEqual(closed,[])

    def test_socket_error_during_failed_recipient_close_does_not_abort_delivery(self):
        frames = []
        def fail(*_args, **_kwargs):
            raise ConnectionResetError('socket already reset')
        stale = NS(writer=NS(close=fail),send=fail)
        healthy = NS(writer=NS(close=lambda:None),send=lambda c,**p:frames.append((c,p)))
        room = NS(players=[stale,healthy])
        rooms.Room.broadcast(room,lambda _viewer:('online',dict(count=2)))
        self.assertEqual(frames,[('online',dict(count=2))])
        self.assertFalse(rooms.send_to(stale,'online',dict(count=3)))

    def test_failed_socket_is_not_retried_but_a_resumed_socket_receives_frames(self):
        sent=[]
        first=NS(close=lambda:sent.append('closed'))
        sess=NS(writer=first)
        def fail(*a,**kw):
            sent.append('write-failed')
            raise BrokenPipeError('gone')
        sess.send=fail
        for _ in range(30):
            self.assertFalse(rooms.send_to(sess,'faShot',dict(status=1)))
        self.assertEqual(sent,['write-failed','closed'])
        sess.writer=NS(close=lambda:None)
        sess.send=lambda c,**p:sent.append(c)
        self.assertTrue(rooms.send_to(sess,'online',dict(count=1)))
        self.assertEqual(sent[-1],'online')
        self.assertIsNone(sess._failed_fanout_writer)

    def test_stale_map_viewer_does_not_stop_heartbeat_for_everyone(self):
        frames,closed,armed=[],[],[]
        class Seat:
            closed=False
            on_map=True
            leg=None
            def __init__(self,pid,broken=False):
                self.pid,self.broken=pid,broken
                self.writer=NS(close=lambda:closed.append(pid))
            def current_pos(self):
                return 0,0
            def send(self,command,**params):
                if self.broken:
                    raise BrokenPipeError('stale map viewer')
                frames.append((self.pid,command,params))
        stale,healthy=Seat(1000001,True),Seat(1000002)
        room=rooms.GlobalMapRoom(50)
        room.seen={stale:set(),healthy:set()}
        room._arm=lambda:armed.append(True)
        room._tick()
        self.assertTrue(armed)
        self.assertTrue(any(pid==healthy.pid and c=='userMove' for pid,c,p in frames))
        self.assertEqual(set(closed),{stale.pid})

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
