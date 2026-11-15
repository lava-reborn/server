"""Boundary contracts: no reverse coordinator imports or real-session filtering."""
import ast
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from training import api

SERVER = Path(__file__).resolve().parent
PACKAGE = SERVER / 'training'


def training_imports(path):
    result = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('training.'):
                    result.add(alias.name.split('.')[1])
                if alias.name.startswith('training_'):
                    result.add('legacy:' + alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'training':
                result.update(alias.name for alias in node.names)
            elif node.module and node.module.startswith('training.'):
                result.add(node.module.split('.')[1])
            elif node.module and node.module.startswith('training_'):
                result.add('legacy:' + node.module)
    return result


class TrainingArchitecture(unittest.TestCase):
    def test_package_does_not_discover_host_globals_by_dynamic_import_or_sys_modules(self):
        for path in PACKAGE.rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, '__import__', str(path))
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertNotEqual((node.value.id, node.attr), ('sys', 'modules'), str(path))

    def test_lower_layers_do_not_import_coordinator_or_dispatcher(self):
        for path in PACKAGE.rglob('*.py'):
            if path.stem in ('api', 'session'):
                continue
            with self.subTest(module=path.stem):
                imports = training_imports(path)
                self.assertFalse(imports & {'session', 'api', 'commands'}, imports)
                self.assertFalse(any(name.startswith('legacy:') for name in imports))

    def test_main_session_uses_only_public_facade(self):
        self.assertEqual(training_imports(SERVER / 'server.py'), {'api'})

    def test_package_import_does_not_initialize_game_or_private_stores(self):
        env = dict(os.environ, PYTHONPATH=str(SERVER))
        subprocess.run([sys.executable, '-B', '-c',
                        "import sys, training; assert 'accounts' not in sys.modules; "
                        "assert not any(n.startswith('training.') for n in sys.modules)"],
                       check=True, timeout=10, env=env, capture_output=True)

    def test_cold_optional_preload_registers_strings_only_when_enabled(self):
        code = '''
import os, sys, names
from training import api
before = dict(names.ALL)
api.preload()
assert 'training.session' not in sys.modules
assert 'training.engines.simulator_v1' not in sys.modules
assert names.ALL == before
os.environ['LAVA_TRAINING_GROUND'] = '1'
api.preload()
assert 'training.engines.simulator_v1' in sys.modules
from training import opponents
import item_templates, sets
assert all(names.ALL.get(key) == text for key, text in opponents.NAMES.items())
assert all(names.ALL.get(key) == text for key, text in before.items())
assert item_templates._SEALED and sets._SEALED and names._SEALED
try:
    names.register_strings({99999999: 'late'})
except RuntimeError:
    pass
else:
    raise AssertionError('late registration accepted')
assert "<s id='8200011'>" in names.document()
'''
        env = dict(os.environ, PYTHONPATH=str(SERVER), LAVA_TRAINING_GROUND='0',
                   LAVA_DB=':memory:', LAVA_DB_URL='')
        result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ordinary_session_events_are_unchanged_and_commands_fall_through(self):
        owner = NS(training_ground=None)
        for command in ('ss_obj_move', 'q_di_kill', 'hp', 'gg_list', 'cmdAck', 'p_m'):
            params = {'id': 123, 'list': [1, 2]}
            self.assertIs(api.outgoing(owner, command, params), params)
            self.assertFalse(api.handle(owner, command, params))
        api.suspend(owner)

    def test_only_allowed_background_events_reach_private_avatar(self):
        owner = NS(training_ground=NS(room=NS(owner_ids={10: 20}), deferred_events=set(), deferred_refresh=set()))
        for command in ('ss_obj_move', 'userInfo', 'q_di_kill', 'cmdAck', 'gg_list'):
            self.assertIsNone(api.outgoing(owner, command, {}))
        params = {'text': 'hello'}
        self.assertIs(api.outgoing(owner, 'userMsg', params), params)
        for flag in ('training_chat', 'training_party_control', 'training_clan_read'):
            setattr(owner, flag, True)
            self.assertIs(api.outgoing(owner, 'cmdAck', params), params)
            setattr(owner, flag, False)
        owner.training_clan_read = True
        self.assertIs(api.outgoing(owner, 'gg_list', params), params)
        owner.training_clan_read = False
        self.assertIsNone(api.outgoing(owner, 'gg_list', params))

    def test_party_mapping_does_not_mutate_source_frame(self):
        owner = NS(training_ground=NS(room=NS(owner_ids={10: 20}), deferred_events=set(), deferred_refresh=set()))
        params = {'list': [10, 30]}
        self.assertEqual(api.outgoing(owner, 'p_m', params), {'list': [20, 30]})
        self.assertEqual(params, {'list': [10, 30]})

    def test_disconnect_preserves_private_membership(self):
        ground = NS(exit=Mock())
        api.suspend(NS(training_ground=ground))
        ground.exit.assert_called_once_with(notify=False, suspend=True)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingArchitecture)
