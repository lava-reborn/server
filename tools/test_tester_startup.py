"""Isolated startup UI, readiness and map-progress checks. No game/account DB."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'server')]
import tempfile
import os
import struct
import zlib
import threading
import urllib.request
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import tester_preloader as preloader
import tester_runtime as runtime
from avm_test import execute

class Startup(unittest.TestCase):

    def env(self):
        self.frames, self.movies = ([], [])
        self.root = dict(pending=True, bar=dict(gotoAndStop=self.frames.append), label={}, loadMovie=self.movies.append)
        return dict(_root=self.root, Number=int)

    def test_failure_and_not_ready_never_load_game(self):
        env = self.env()
        execute(preloader.response_actions().assemble(), dict(env, ok=False, this={}))
        self.assertFalse(self.root['pending'])
        self.assertEqual(self.movies, [])
        execute(preloader.response_actions().assemble(), dict(env, ok=True, this=dict(progress='35', stage='Map', ready='0')))
        self.assertEqual(self.frames, [35])
        self.assertEqual(self.movies, [])
        self.assertEqual(self.root['label']['text'], 'Map')

    def test_startup_error_keeps_message_and_stops_polling(self):
        env = self.env()
        self.root['onEnterFrame'] = 'poll'
        execute(preloader.response_actions().assemble(), dict(env, ok=True, this=dict(progress='1', stage='Failed', ready='-1')))
        self.assertEqual(self.movies, [])
        self.assertIsNone(self.root['onEnterFrame'])
        self.assertEqual(self.root['label']['text'], 'Failed')

    def test_ready_loads_game_and_stops_polling(self):
        env = self.env()
        self.root['onEnterFrame'] = 'poll'
        execute(preloader.response_actions().assemble(), dict(env, ok=True, this=dict(progress='100', stage='Ready', ready='1')))
        self.assertEqual(self.frames, [100])
        self.assertEqual(self.movies, ['/res/main.swf?vversion=1'])
        self.assertIsNone(self.root['onEnterFrame'])

    def test_poll_is_single_flight_and_at_most_twice_a_second(self):
        self.env()
        loads = []
        requests = []

        def factory():
            req = dict(load=loads.append)
            requests.append(req)
            return req
        env = dict(_root=self.root, this=self.root, _global=dict(LoadVars=factory), getTimer=lambda: 1000)
        self.root.update(pending=False, nextPoll=0)
        execute(preloader.poll_actions().assemble(), env)
        self.assertEqual(loads, ['/startup-status?t=1000'])
        execute(preloader.poll_actions().assemble(), env)
        self.assertEqual(len(loads), 1)
        self.root['pending'] = False
        execute(preloader.poll_actions().assemble(), env)
        self.assertEqual(len(loads), 1)
        self.assertEqual(self.root['nextPoll'], 1500)

    def test_root_script_creates_native_bar_and_starts_polling(self):
        self.env()

        def attach(symbol, name, depth):
            self.assertIn(symbol, ('BootFrame', 'BootBar'))
            self.root[name] = dict(gotoAndStop=self.frames.append)

        def text(name, depth, x, y, w, h):
            self.root[name] = {}
        self.root.update(attachMovie=attach, createTextField=text)
        code = preloader.script()
        self.assertEqual(code[-2:], b'\x07\x00')
        execute(code[:-2], dict(_root=self.root))
        self.assertEqual(self.frames, [1, 1])
        self.assertIsNotNone(self.root['onEnterFrame'])
        self.assertEqual(self.root['nextPoll'], 0)

    def test_real_artwork_build_is_small_and_keeps_game_frame_rate(self):
        source = Path(os.environ.get('LAVA_RES', '')) / 'main.swf'
        if not source.is_file():
            self.skipTest('Original main.swf not provided')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'startup.swf'
            size, assets = preloader.build(source, target)
            self.assertLess(size, 16384)
            self.assertGreater(assets, 0)
            body = zlib.decompress(target.read_bytes()[8:])
            _, pos = preloader.read_rect(body, 0)
            self.assertEqual(struct.unpack_from('<H', body, pos)[0], 25 * 256)

    def test_startup_http_does_not_release_game_before_ready(self):
        state = runtime.StartupState()
        with ThreadingHTTPServer(('127.0.0.1', 0), runtime.startup_handler(state)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = 'http://127.0.0.1:%d' % server.server_port
                with urllib.request.urlopen(url + '/startup-status') as reply:
                    self.assertIn(b'ready=0', reply.read())
                    self.assertEqual(reply.headers['Cache-Control'], 'no-store')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url + '/res/main.swf')
                self.assertEqual(error.exception.code, 503)
                error.exception.close()
                state.update(100, 'Ready', 1)
                with urllib.request.urlopen(url + '/startup-status') as reply:
                    self.assertIn(b'ready=1', reply.read())
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_stop_during_startup_cancels_without_waiting_for_http(self):
        import io
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'state').mkdir()
            (root / 'state/tester.sqlite').touch()
            child = unittest.mock.Mock()
            child.poll.return_value = None
            child.wait.return_value = 0
            thread = lambda target, **kw: SimpleNamespace(start=target)
            with patch.object(runtime, 'ROOT', root), patch.object(runtime, 'configure'), patch.object(runtime.sys, 'argv', ['start.py', '--backend']), patch.object(runtime.sys, 'stdin', io.StringIO('stop\n')), patch.object(runtime.socket, 'socket'), patch.object(runtime.subprocess, 'Popen', return_value=child) as popen, patch.object(runtime.threading, 'Thread', side_effect=thread), patch.object(runtime.urllib.request, 'urlopen') as request:
                runtime.main()
            request.assert_not_called()
            self.assertEqual(popen.call_count, 2)
            self.assertEqual(child.terminate.call_count, 2)
            self.assertTrue(all((call.kwargs['stdin'] == runtime.subprocess.DEVNULL for call in popen.call_args_list)))

    def test_prepared_map_uses_public_constructor_without_repainting(self):
        import map_cells
        plan = unittest.mock.Mock()
        plan.tiles.return_value = [123]
        served = map_cells.Served('unused', plan, prepared_tiles={'globalmap/full/123.jpg': b'ready'})
        with patch.object(map_cells, 'apply', side_effect=AssertionError('unexpected painter')):
            self.assertEqual(served.get('globalmap/full/123.jpg'), b'ready')

    def test_shape4_miter_join_does_not_confuse_end_cap_with_join(self):
        from swfgen import rect
        for flags, miter in ((8192, b'\x00\x01'), (2, b'')):
            shape = struct.pack('<H', 1) + rect(0, 20, 0, 20) * 2 + b'\x00' + b'\x00\x01' + struct.pack('<H', 20) + struct.pack('>H', flags) + miter + b'\xff\x00\x00\xff' + b'\x01\x00'
            self.assertEqual(preloader.shape_bitmaps(83, shape), set())

    def test_startup_state_retains_owner_across_progress_updates(self):
        from urllib.parse import parse_qs
        state = runtime.StartupState('a' * 32)
        state.update(100, 'Ready', 1)
        values = parse_qs(state.encoded().decode())
        self.assertEqual(values['instance'], ['a' * 32])
        self.assertEqual(values['ready'], ['1'])
        with patch.object(runtime.sys, 'argv', ['start.py', '--instance']):
            with self.assertRaises(ValueError):
                runtime.instance_id()

    def test_map_progress_does_not_change_result(self):
        import map_cells
        canvas = unittest.mock.Mock()
        canvas.encode.return_value = ({}, {})
        with patch.object(map_cells, 'Canvas', return_value=canvas), patch.object(map_cells, 'clear_zones', return_value=([], ['zones'])), patch.object(map_cells, 'erase', return_value=([], [], [], ['erase'])), patch.object(map_cells, 'paint', return_value=['paint']):
            progress = []
            actual = map_cells.apply(None, object(), progress=lambda n, p: progress.append((n, p)))
            self.assertEqual(actual, ({}, ['zones', 'erase', 'paint']))
            self.assertEqual([n for n, p in progress], [5, 45, 65, 80, 100])
            self.assertEqual(map_cells.apply(None, object()), actual)
if __name__ == '__main__':
    unittest.main()
