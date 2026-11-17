"""The confined client build receives the game's resolved training opt-in only.

Exercise the gate's actual client_build function with local stand-ins for
Docker and publishing. No containers, network, server .env or game DB.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'deploy/remote/lava-gate.sh'


class TrainingDeploy(unittest.TestCase):
    def build(self, config, *, compose_failure=False):
        with tempfile.TemporaryDirectory(prefix='training-deploy-') as tmp:
            root = Path(tmp)
            for name in ('stage/tree/client/build.py', 'app/.env',
                         'client/publish.py', 'key', 'compose.json'):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{}', encoding='utf-8')
            (root / 'stage/tree/docker-compose.yml').write_text('services: {}\n')
            (root / 'store').mkdir()
            (root / 'compose.json').write_text(json.dumps(config), encoding='utf-8')
            function = re.search(r'^client_build\(\) \{.*?^\}',
                                 GATE.read_text(encoding='utf-8'), re.M | re.S).group()
            script = r'''
set -uo pipefail
STAGE=$TEST_ROOT/stage
APP_DIR=$TEST_ROOT/app
CLIENT_ROOT=$TEST_ROOT
CLIENT_PY=$TEST_ROOT/client/publish.py
CLIENT_KEY=$TEST_ROOT/key
CLIENT_TIMEOUT=10
CLIENT_IMAGE=test-image
RES_DIR=$TEST_ROOT/res
DLOG=$TEST_ROOT/deploy.log
ID=test
id() { echo 1000; }
timeout() { shift 3; "$@"; }
policy_python() { "$TEST_PYTHON" "$@"; }
python3() { return 0; }
docker() {
  if [ "$1" = compose ]; then
    cat "$TEST_ROOT/compose.json"
    [ "$TEST_COMPOSE_FAILURE" = 0 ]
  elif [ "$1" = run ]; then
    printf '%s\n' "$@" > "$TEST_ROOT/build.args"
    printf '%s\t1\tdatabase/texts.xml\n' hash > "$STAGE/client/files.tsv"
  else
    return 1
  fi
}
'''
            script += function + '\nclient_build\nstatus=$?\necho "$WHY"\nexit "$status"\n'
            env = dict(os.environ, TEST_ROOT=str(root), TEST_PYTHON=sys.executable,
                       TEST_COMPOSE_FAILURE=str(int(compose_failure)),
                       LAVA_TRAINING_GROUND='0')
            result = subprocess.run(['bash', '-c', script], env=env, capture_output=True,
                                    text=True, timeout=10)
            args = root / 'build.args'
            return result.returncode, result.stdout + result.stderr, (
                args.read_text().splitlines() if args.is_file() else [])

    def test_resolved_game_flag_overrides_the_unrelated_build_host_environment(self):
        for value, expected in (('1', '1'), ('0', '0'), (None, '0'), ('yes', '0')):
            with self.subTest(value=value):
                config = {'services': {'game': {'environment': {
                    'LAVA_TRAINING_GROUND': value, 'LAVA_DB_URL': 'private-test-value'}}}}
                code, output, args = self.build(config)
                self.assertEqual(code, 0, output)
                self.assertIn('LAVA_TRAINING_GROUND=' + expected, args)
                self.assertNotIn('private-test-value', '\n'.join(args))
                self.assertIn('--read-only', args)
                self.assertEqual(args[args.index('--network') + 1], 'none')

    def test_missing_flag_defaults_to_disabled(self):
        code, output, args = self.build({'services': {'game': {}}})
        self.assertEqual(code, 0, output)
        self.assertIn('LAVA_TRAINING_GROUND=0', args)

    def test_unresolved_configuration_stops_before_any_build(self):
        for config, failed in (({}, False), ({'services': {}}, False),
                               ({'services': {'game': {'environment': {
                                   'LAVA_TRAINING_GROUND': '1'}}}}, True)):
            with self.subTest(config=config, compose_failure=failed):
                code, output, args = self.build(config, compose_failure=failed)
                self.assertEqual(code, 1, output)
                self.assertIn('could not', output)
                self.assertEqual(args, [])


if __name__ == '__main__':
    unittest.main()
