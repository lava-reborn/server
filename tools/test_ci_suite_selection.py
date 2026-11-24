"""Client suites must survive PR selection and be required by shard merging."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from testkit import run_cases


def shell_path(path):
    value = str(path.resolve()).replace('\\', '/')
    if sys.platform == 'win32':
        return '/' + value[0].lower() + value[2:]
    return value


class ClientSuiteSelection(unittest.TestCase):
    def test_required_pr_checks_run_after_documentation_only_pushes(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        triggers = re.search(r'(?ms)^on:\n(.*?)(?=^[a-zA-Z_][\w-]*:|\Z)', workflow)
        self.assertIsNotNone(triggers)
        pr = re.search(r'(?ms)^  pull_request:[ \t]*\n(.*?)(?=^  [a-zA-Z_][\w-]*:|\Z)',
                       triggers.group(1))
        self.assertIsNotNone(pr, 'Required checks need a pull_request trigger')
        self.assertNotRegex(pr.group(1), r'(?m)^    paths(?:-ignore)?:',
                            'A skipped workflow leaves required PR checks pending')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lava_ci_selection_')
        self.addCleanup(self.temporary.cleanup)
        self.tree = Path(self.temporary.name)
        self.bash = ('C:/Program Files/Git/bin/bash.exe' if sys.platform == 'win32'
                     else shutil.which('bash'))
        if not self.bash or not Path(self.bash).is_file():
            self.skipTest('Bash is required to execute the real CI selection/merge scripts')
        self.suites = ['server/test_alpha.py', 'data/test_gamma.py',
                       'tools/test_beta.py', 'client/test_client_contract.py']
        for relative in self.suites:
            self.write(relative, '')
        for relative in ('tools/run_suite.sh', 'deploy/ci/merge_shards.sh'):
            self.write(relative, (ROOT / relative).read_text(encoding='utf-8'))
        self.write('res/database/objects.xml', '<objects/>')
        self.write('bin/python3', "#!/bin/sh\nprintf '%s\\n' 'client/test_client_contract.py'\n")
        (self.tree / 'bin/python3').chmod(0o755)

    def write(self, relative, value):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8', newline='\n')

    def shell(self, script, *args, env_extra=None):
        env = dict(os.environ, LAVA_RES=shell_path(self.tree / 'res'), LAVA_CI_PART='1')
        env.update(env_extra or {})
        return subprocess.run([self.bash, '-c',
            'export PATH="$1:$PATH"; shift; exec bash "$@"', '--',
            shell_path(self.tree / 'bin'), shell_path(self.tree / script), *args],
            cwd=self.tree, env=env, capture_output=True, text=True, timeout=30)

    def test_child_database_and_temp_follow_configured_temp_root_with_spaces(self):
        self.write('bin/python3', '#!/bin/sh\ncase "$1" in *suite.py) printf \'%s\\n\' \'server/test_alpha.py\'; exit 0;; test_alpha.py) ;; *) exit 0;; esac\nprintf \'%s\\n\' "$LAVA_DB" "$TMPDIR" > "$LAVA_TEMP_TRACE"\ntest -d "$TMPDIR"\n')
        (self.tree / 'temp with spaces').mkdir()
        temporary = shell_path(self.tree / 'temp with spaces')
        result = self.shell('tools/run_suite.sh', '--only', 'test_alpha',
                            '.', shell_path(self.tree / 'out'), '1',
                            env_extra=dict(TMPDIR=temporary,
                                           LAVA_TEMP_TRACE=shell_path(self.tree / 'trace.txt')))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        database, child_tmp = (self.tree / 'trace.txt').read_text().splitlines()
        self.assertTrue(database.startswith(temporary + '/lava_suite_tmp.'), database)
        self.assertTrue(database.endswith('/test_alpha/lava.db'), database)
        self.assertEqual(child_tmp, database.rsplit('/', 1)[0] + '/tmp')

    def test_selected_client_suite_is_not_dropped_by_shell_runner(self):
        result = self.shell('tools/run_suite.sh', '--only', 'test_client_contract',
                            '--list', '.', shell_path(self.tree / 'out'), '1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('client/test_client_contract.py', result.stdout.splitlines())
        self.assertNotIn('nothing to run', result.stdout)

    def test_merge_requires_client_suite_once_in_full_and_selected_runs(self):
        names = [Path(path).stem for path in self.suites]
        self.write('shards/1/summary.txt', ''.join('0 0s %s\n' % n for n in names))
        args = (shell_path(self.tree / 'shards'), shell_path(self.tree / 'merged.txt'))
        result = self.shell('deploy/ci/merge_shards.sh', *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.write('shards/1/summary.txt', ''.join('0 0s %s\n' % n for n in names[:-1]))
        for selected in ((), (','.join(names),)):
            result = self.shell('deploy/ci/merge_shards.sh', *args, *selected)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('test_client_contract ran in no shard', result.stdout)
        self.write('shards/1/summary.txt', ''.join('0 0s %s\n' % n for n in names + [names[-1]]))
        result = self.shell('deploy/ci/merge_shards.sh', *args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('test_client_contract ran in more than one shard', result.stdout)

    def test_workflow_pick_filters_preserve_every_discovered_suite_root(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        patterns = re.findall(r"grep -(?:v)?E '([^']+)' .*pick[.]txt", workflow)
        self.assertEqual(len(patterns), 2)
        for pattern in patterns:
            for suite in self.suites:
                self.assertRegex(suite, pattern)


if __name__ == '__main__':
    run_cases(ClientSuiteSelection)
