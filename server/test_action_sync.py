"""Movement AP, confirmed healing bars, observer cancellation and melee spam.

See PROTOCOL.md action synchronization, Location.movePlayer and
DisplayLocScene's aiming events. Session's position setter is real; frames
are captured without a socket. test_combat covers the matching wire flow.
"""
import asyncio
import logging
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import rooms  # noqa: E402
import movement  # noqa: E402
from protocol import decode, frame  # noqa: E402
import server  # noqa: E402
import test_action_order as fixtures  # noqa: E402
from testkit import run_cases  # noqa: E402

class ActionSync(unittest.IsolatedAsyncioTestCase):

    def fixture(self, weapon=25566):
        f, ch, room, used, events, row = fixtures.ActionOrder().attack_fixture(weapon)
        source = f.sess
        s = server.Session.__new__(server.Session)
        s.char_id = 1
        s.char = ch
        s.combat = f
        s.room = room
        s.loc = source.loc
        s.inv = source.inv
        s.send = source.send
        s.answer = source.answer
        s.cancel_passage = lambda: None
        s.on_map = False
        s.pos = 0
        f.sess = s
        f.ap_max = 100
        room.ws = True

        async def cleanup():
            combat.Fighter.cancel_timers(f)
        self.addAsyncCleanup(cleanup)
        return (f, s, room, events, row)

    def clock(self, seconds):
        return patch.object(asyncio.get_running_loop(), 'time', return_value=seconds)

    def start_walk(self, f, s, cells):
        s.pos = cells[-1]
        s.walk = (cells, 100.0)
        combat.Fighter.moved(f, cells)

    def movement_session(self):
        f, s, room, events, row = self.fixture()
        s.loc.obstacles = set()
        room.npcs = {}
        room.players = {s: None}
        room.loc = s.loc
        room.combat = f.rc
        f.rc.mobs = {}
        room.motion = movement.Motion(room)
        room.motion.schedule = lambda: None  # This fixture advances a fake clock explicitly.
        s.barter = NS(moved=lambda: None)
        s.passage = None
        s.arm_passage = lambda length: None
        f.moved = lambda cells: combat.Fighter.moved(f, cells)
        return f, s, room, events, row

    async def test_duplicate_route_only_acks_without_restarting_walk_or_passage(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        original = s.walk
        calls = []
        s.cancel_passage = lambda: calls.append('cancel passage')
        s.arm_passage = lambda length: calls.append('arm passage')
        s.barter.moved = lambda: calls.append('barter')
        room.broadcast = lambda *args, **kwargs: calls.append('broadcast')
        events.clear()
        for now in (100.05, 100.25, 100.65):
            with self.clock(now):
                s.move_in_location(dict(path=list(range(11))))
            self.assertIs(s.walk, original)
        self.assertEqual(events, [('cmdAck', dict(res=0))] * 3)
        self.assertEqual(calls, [])
        self.assertEqual(s.pos, 10)
        self.assertEqual(f.ap, 97)

    async def test_different_remaining_route_to_same_destination_is_not_a_duplicate(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        events.clear()
        changed = [1, 2, 22, 23, 24, 4, 5, 6, 7, 8, 9, 10]
        with self.clock(100.25):
            s.move_in_location(dict(path=changed))
        self.assertEqual(s.walk[0], changed)
        self.assertAlmostEqual(s.walk[1], 100.2)
        self.assertTrue(any(cmd == 'userMove' for cmd, _ in events))

    async def test_delayed_reroute_echoes_only_unwalked_tail_and_keeps_step_phase(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            s.move_in_location(dict(path=list(range(9))))
            self.assertEqual(s.walk[0], list(range(2, 9)))
            self.assertAlmostEqual(s.walk[1], 100.4)
            self.assertEqual(f.ap, 98)
            move = next(p for cmd, p in events if cmd == 'userMove' and p['id'] == 0)
            self.assertEqual(move['path'], list(range(2, 9)))
            self.assertAlmostEqual(move['step_ms'], 50, delta=1)
            self.assertEqual(move['ap'], 98)
        with self.clock(100.65):
            self.assertEqual(s.live_cell(), 3)
            self.assertEqual(f.ap, 97)

    async def test_stop_on_passage_arms_exit_without_single_cell_walk_animation(self):
        f, s, room, events, row = self.movement_session()
        armed = []
        s.arm_passage = armed.append
        s.move_in_location(dict(path=[s.pos]))
        self.assertEqual(armed, [1])
        self.assertFalse(any(cmd == 'userMove' for cmd, _ in events))
        self.assertTrue(any(cmd == 'actionCancel' for cmd, _ in events))

    async def test_click_arriving_after_route_finished_does_not_replay_its_prefix(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, [0, 1, 2])
        with self.clock(100.45):
            self.assertEqual(s.live_cell(), 2)
            self.assertIsNone(s.walk)
            s.move_in_location(dict(path=[0, 1, 2, 3, 4]))
            self.assertEqual(s.walk[0], [2, 3, 4])
            self.assertEqual(f.ap, 98)
        s.pos = 8  # a teleport must not reuse the old location's route
        self.assertIsNone(s._completed_walk)

    async def test_turn_back_starts_here_not_at_clicks_stale_cell(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.65):
            s.move_in_location(dict(path=[1, 2, 22]))
            self.assertEqual(s.walk[0][:2], [3, 4])
            self.assertEqual(s.walk[0][-1], 22)
            self.assertNotIn(1, s.walk[0])
            self.assertNotIn(2, s.walk[0])
            self.assertAlmostEqual(s.walk[1], 100.6)
            self.assertEqual(f.ap, 97)
            self.assertNotIn(('userMove', dict(id=0, path=[1, 2, 22])), events)

    async def test_turn_back_revisits_initial_hex_without_replaying_paid_steps(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            s.move_in_location(dict(path=[2, 3, 2, 1]))
            self.assertEqual(s.walk[0], [2, 3, 2, 1])
            self.assertEqual(f.ap, 98)
        with self.clock(100.85):
            self.assertEqual(s.live_cell(), 2)
            self.assertEqual(f.ap, 96)
            s.move_in_location(dict(path=[2, 1, 0]))
            self.assertEqual(s.walk[0], [2, 1, 0])
            self.assertAlmostEqual(s.walk[1], 100.8)
        with self.clock(101.25):
            self.assertEqual(s.live_cell(), 0)
            self.assertEqual(f.ap, 94)
            combat.Fighter.settle_walk(f)
            self.assertEqual(f.ap, 94)

    async def test_owner_and_observer_receive_one_identical_path_and_phase(self):
        f, s, room, events, row = self.movement_session()
        own, other = [], []
        s.send = lambda cmd, **p: own.append((cmd, p))
        room.broadcast = lambda frame, **kw: other.append(frame)
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            s.move_in_location(dict(path=[2, 3, 22]))
        owner = [p for cmd, p in own if cmd == 'userMove']
        observer = [p for cmd, p in other if cmd == 'userMove']
        self.assertEqual(len(owner), 1)
        self.assertEqual(len(observer), 1)
        self.assertEqual(owner[0]['path'], observer[0]['path'])
        self.assertEqual(owner[0]['step_ms'], observer[0]['step_ms'])
        self.assertEqual((owner[0]['id'], observer[0]['id']), (0, s.pid))
        self.assertEqual(owner[0]['ap'], 98)
        self.assertNotIn('ap', observer[0])

    async def test_two_tcp_clients_receive_the_same_authoritative_reroutes(self):
        f, actor, room, events, row = self.movement_session()
        _, observer, _, _, _ = self.movement_session()
        observer.char_id = 2
        observer.room = room
        room.players = {actor: None, observer: None}
        room.broadcast = lambda value, **kw: rooms.Room.broadcast(room, value, **kw)
        with self.clock(100):
            self.start_walk(f, actor, list(range(11)))
        seats = [actor, observer]
        moments = iter((100.45, 100.65))
        ready = asyncio.Event()
        handlers = set()
        failures = []

        async def handle(reader, writer):
            task = asyncio.current_task()
            handlers.add(task)
            seat = seats.pop(0)
            seat.writer, seat.closed = writer, False
            seat.send = lambda cmd, **p: server.Session.send(seat, cmd, **p)
            if not seats:
                ready.set()
            try:
                while True:
                    raw = await reader.readuntil(b'\0')
                    cmd, params = decode(raw[:-1].decode('utf-8'))
                    self.assertEqual(cmd, 'moveTo')
                    with self.clock(next(moments)):
                        seat.cmd_moveTo(params)
                    await writer.drain()
            except asyncio.IncompleteReadError:
                pass
            except Exception as exc:
                failures.append(exc)
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)

        listener = await asyncio.start_server(handle, '127.0.0.1', 0)
        port = listener.sockets[0].getsockname()[1]
        connections = []
        async def receive_move(reader):
            while True:
                raw = await asyncio.wait_for(reader.readuntil(b'\0'), 2)
                cmd, params = decode(raw[:-1].decode('utf-8'))
                if cmd == 'userMove':
                    return params
        try:
            connections.append(await asyncio.open_connection('127.0.0.1', port))
            connections.append(await asyncio.open_connection('127.0.0.1', port))
            await asyncio.wait_for(ready.wait(), 2)
            for requested, ap in (([2, 3, 22], 98), ([2, 3, 2, 1], 97)):
                reader, writer = connections[0]
                writer.write(frame('moveTo', path=requested))
                await writer.drain()
                own, other = await asyncio.gather(receive_move(reader), receive_move(connections[1][0]))
                self.assertEqual(own['path'], other['path'])
                self.assertEqual(own['step_ms'], other['step_ms'])
                self.assertEqual(own['path'], actor.walk[0])
                self.assertEqual((own['id'], other['id']), (0, actor.pid))
                self.assertEqual(own['ap'], ap)
                self.assertNotIn('ap', other)
                self.assertTrue(0 <= own['step_ms'] < combat.mobs.HEX_MS)
        finally:
            for _, writer in connections:
                writer.close()
                await writer.wait_closed()
            listener.close()
            await listener.wait_closed()
            if handlers:
                await asyncio.wait_for(asyncio.gather(*list(handlers)), 2)
        self.assertEqual(failures, [])

    async def test_matching_edge_reuses_tail_without_server_path_search(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45), patch.object(combat.mobs, 'find_path') as search:
            s.move_in_location(dict(path=[2, 3, 22]))
        search.assert_not_called()
        self.assertEqual(s.walk[0], [2, 3, 22])

    async def test_stale_repair_uses_live_mob_positions_instead_of_empty_spawns(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        room.npcs = {1: NS(cell=22, root=server.world.MOB),
                     2: NS(cell=40, root=server.world.TRADER)}
        room.combat = NS(mobs={1: NS(cell=41, alive=True), 3: NS(cell=42, alive=False)})
        find = combat.mobs.find_path
        with self.clock(100.65), patch.object(combat.mobs, 'find_path', wraps=find) as search:
            s.move_in_location(dict(path=[1, 2, 22]))
        blocked = search.call_args.args[3]
        self.assertEqual(blocked, {40, 41})
        self.assertEqual(s.walk[0][-1], 22)

    def test_idle_live_cell_does_not_read_event_loop_clock(self):
        s = server.Session.__new__(server.Session)
        s._pos, s.walk = 7, None
        with patch.object(asyncio, 'get_running_loop', side_effect=AssertionError('idle clock')):
            self.assertEqual(s.live_cell(), 7)

    async def test_reroute_through_wall_is_refused_without_teleport(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        s.loc.obstacles = {22}
        with self.clock(100.45):
            s.move_in_location(dict(path=[2, 3, 22]))
        self.assertEqual(s.pos, 2)
        self.assertEqual(f.ap, 98)
        self.assertFalse(any(cmd == 'userMove' for cmd, _ in events))
        self.assertIn(('breakMv', dict(id=0, pos=2)), events)

    async def test_unreachable_stale_click_is_refused_without_replaying_old_route(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        # The requested route is valid, but disconnected from the live edge.
        s.loc.obstacles = set(range(400)) - {0, 1, 2, 3, 4, 22}
        with self.clock(100.65), patch.object(combat.mobs, 'find_path', return_value=None) as search:
            s.move_in_location(dict(path=[1, 2, 22]))
        search.assert_called_once()
        self.assertEqual(s.pos, 3)
        self.assertEqual(f.ap, 97)
        self.assertFalse(any(cmd == 'userMove' for cmd, _ in events))

    async def test_delayed_click_after_action_replans_from_stop_without_teleport(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            combat.Fighter.begin_action(f)
            self.assertEqual(s.pos, 2)
            self.assertIsNone(s.walk)
            self.assertEqual(s._completed_walk[0], [0, 1, 2])
        with self.clock(100.55):
            s.move_in_location(dict(path=[0, 1, 21, 41]))
            self.assertEqual(s.walk[0][0], 2)
            self.assertEqual(s.walk[0][-1], 41)
            self.assertNotIn(0, s.walk[0])
            self.assertAlmostEqual(s.walk[1], 100.55)
            self.assertEqual(f.ap, 98)

    async def test_unreached_old_tail_after_action_cannot_jump_to_destination(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            combat.Fighter.begin_action(f)
        with self.clock(100.55):
            s.move_in_location(dict(path=[8, 9]))
        self.assertEqual((s.pos, f.ap), (2, 98))
        self.assertIsNone(s.walk)
        self.assertIn(('breakMv', dict(id=0, pos=2)), events)
        self.assertFalse(any(cmd == 'userMove' for cmd, _ in events))

    async def test_reroute_ending_here_is_stop_without_one_cell_usermove_or_fifo_skip(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            s.move_in_location(dict(path=[0, 1, 2]))
        self.assertEqual((s.pos, f.ap), (2, 98))
        self.assertIsNone(s.walk)
        self.assertIn(('actionCancel', dict(pos=2)), events)
        own = [(cmd, p) for cmd, p in events if cmd == 'cmdAck']
        self.assertEqual(own, [('cmdAck', dict(res=0))])
        self.assertFalse(any(cmd in ('userMove', 'breakMv') for cmd, p in events))

    async def test_impossible_reroute_refuses_at_live_cell_not_old_destination(self):
        f, s, room, events, row = self.movement_session()
        with self.clock(100):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.45):
            s.move_in_location(dict(path=[8, 9]))
        self.assertEqual((s.pos, f.ap), (2, 98))
        self.assertIn(('breakMv', dict(id=0, pos=2)), events)
        self.assertFalse(any(cmd == 'cmdAck' for cmd, p in events))

    async def test_fire_acceptance_always_carries_stop_position_even_after_server_arrival(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100):
            self.start_walk(f, s, [0, 1, 2])
        with self.clock(100.45):
            self.assertEqual(s.live_cell(), 2)
            self.assertIsNone(s.walk)
            # The older action fixture is an NS, not Fighter.cell's property.
            f.cell = 2
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        aiming = [p for cmd, p in events if cmd == 'faAim']
        self.assertEqual(len(aiming), 1)
        self.assertEqual(aiming[0]['pos'], 2)
        self.assertIsNotNone(f.aim)
        self.assertEqual((row['ammo_count'], row['brk']), (10, 100))

    async def test_stopping_at_second_step_charges_two_not_whole_route(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
            self.assertEqual(f.ap, 100)
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual((s.pos, f.ap), (2, 98))
        self.assertIsNone(s.walk)
        self.assertIsNone(f.walk_ap)
        self.assertIn(('c_ap', dict(ap=98)), events)

    async def test_attack_ap_check_does_not_charge_unwalked_tail(self):
        f, s, room, events, row = self.fixture()
        cost = items.params_of(row['type_id'])['fire_costs'][row['cur_mode']]
        f.ap = cost + 2
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        self.assertIsNotNone(f.aim)
        self.assertEqual((s.pos, f.ap), (2, cost))

    async def test_finished_walk_is_charged_exactly_once(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 10.1 * combat.mobs.HEX_MS / 1000):
            self.assertEqual(s.live_cell(), 10)
            combat.Fighter.settle_walk(f)
            combat.Fighter.begin_action(f)
        self.assertEqual(f.ap, 90)

    async def test_reroute_does_not_charge_old_tail(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        second = 100.0 + 2.1 * combat.mobs.HEX_MS / 1000
        with self.clock(second):
            s.pos = 6
            s.walk = ([2, 3, 4, 5, 6], second)
            combat.Fighter.moved(f, [2, 3, 4, 5, 6])
        with self.clock(second + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual((s.pos, f.ap), (4, 96))

    async def test_peace_steps_not_charged_when_war_starts(self):
        f, s, room, events, row = self.fixture()
        room.ws = False
        rc = NS(room=room, fighters=lambda: [f], mobs={})
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.RoomCombat.set_ws(rc, True)
        with self.clock(100.0 + 4.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual(f.ap, 98)

    async def test_replacing_aim_notifies_owner_and_observers(self):
        f, s, room, events, row = self.fixture()
        own = []
        observers = []
        s.send = lambda cmd, **p: own.append((cmd, p))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        saved = (f.aim._callback, f.aim._args)
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        saved[0](*saved[1])
        self.assertIn(('actionCancel', dict(release=0, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)
        self.assertIsNone(f.aim)
        self.assertFalse(any((e[0] == 'resolved_fire' for e in events)))
        self.assertEqual(own[-1][0], 'actionStart')

    def movable_inventory(self, f, s, row):
        store = NS(update_item=lambda uniq, **fields: row.update(fields))
        inv = inventory.Inventory(s, store)
        inv.find = lambda obj: row
        inv.in_slot = lambda slot: None
        s.character = f.character
        f.primary_changed = lambda: combat.Fighter.primary_changed(f)
        return inv

    async def test_switch_away_and_back_cancels_aim_and_saved_callback(self):
        f, s, room, events, row = self.fixture()
        inv = self.movable_inventory(f, s, row)
        own = []
        observers = []
        s.send = lambda cmd, **p: own.append((cmd, p))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        saved = (timer._callback, timer._args)
        before = (f.ap, row['ammo_count'], row['brk'])
        for src, dst in ((inventory.PRIMARY, inventory.SECONDARY), (inventory.SECONDARY, inventory.PRIMARY)):
            inv.ss_move(dict(obj='weapon', **{'from': src, 'to': dst}))
        saved[0](*saved[1])
        self.assertTrue(timer.cancelled())
        self.assertIsNone(f.aim)
        self.assertEqual((f.ap, row['ammo_count'], row['brk']), before)
        self.assertFalse(any((e[0] == 'resolved_fire' for e in events)))
        self.assertIn(('actionCancel', dict(release=1, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)

    async def test_refused_weapon_move_preserves_aim(self):
        f, s, room, events, row = self.fixture()
        inv = self.movable_inventory(f, s, row)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        revision = f.action_revision
        inv.ss_move(dict(obj='weapon', **{'from': inventory.BAG, 'to': inventory.PRIMARY}))
        self.assertIs(f.aim, timer)
        self.assertFalse(timer.cancelled())
        self.assertEqual(f.action_revision, revision)

    async def test_unrelated_inventory_move_preserves_aim(self):
        f, s, room, events, row = self.fixture()
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        revision = f.action_revision
        spare = dict(row, uniq=3, slot=inventory.BAG)
        inv = self.movable_inventory(f, s, spare)
        inv.ss_move(dict(obj='spare', **{'from': inventory.BAG, 'to': inventory.SECONDARY}))
        self.assertIs(f.aim, timer)
        self.assertFalse(timer.cancelled())
        self.assertEqual(f.action_revision, revision)

    async def test_primary_change_without_aim_preserves_melee_or_heal(self):
        for kind in ('strike', 'healing'):
            f, s, room, events, row = self.fixture()
            revision = combat.Fighter.begin_action(f)
            combat.Fighter.schedule_action(f, revision, kind, 100, lambda: None)
            pending = getattr(f, kind)
            combat.Fighter.primary_changed(f)
            self.assertIs(getattr(f, kind), pending)
            self.assertFalse(pending.cancelled())
            self.assertEqual(f.action_revision, revision)

    async def test_repeated_heal_confirms_bar_after_cancelling_old_timer(self):
        f, s, room, events, row = self.fixture()
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        old = f.healing
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertTrue(old.cancelled())
        commands = [cmd for cmd, p in events if isinstance(cmd, str)]
        self.assertEqual(commands[-3:], ['actionCancel', 'c_ap', 'actionStart'])

    async def test_ap_loss_before_shot_cancels_aim_for_owner_and_observers(self):
        f, s, room, events, row = self.fixture()
        own, observers = ([], [])
        s.send = lambda command, **params: own.append((command, params))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        f.ap = 0
        before = (row['ammo_count'], row['brk'])
        combat.Fighter.fire_now(f, row['uniq'], None, None, NS(num_shots=1), 11, 1)
        self.assertIn(('actionCancel', dict(release=1, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)
        self.assertIn(('c_ap', dict(ap=0)), events)
        self.assertEqual((row['ammo_count'], row['brk']), before)

    async def test_thousand_melee_presses_keep_one_timer_and_one_impact(self):
        f, s, room, events, row = self.fixture(6241)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.strike
        saved = (timer._callback, timer._args)
        deadline = timer.when()
        for _ in range(1000):
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000002'))
            self.assertIs(f.strike, timer)
            self.assertEqual(f.strike.when(), deadline)
        saved[0](*saved[1])
        saved[0](*saved[1])
        timer.cancel()
        hits = [e for e in events if e[0] == 'resolved_strike']
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1][1], 1)
if __name__ == '__main__':
    try:
        run_cases(ActionSync)
    finally:
        server.STORE.close()
