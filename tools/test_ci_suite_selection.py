"""Client suites must survive PR selection and be required by shard merging."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

import suite
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

    def test_warehouse_capture_contracts_are_included_in_the_full_release_suites(self):
        required = {'server/test_warehouse_capture_rules.py', 'server/test_holdings.py',
                    'server/test_clan_bases.py', 'server/test_clan_base_access.py',
                    'server/test_release_integrity.py', 'server/test_boss_hotfix.py',
                    'server/test_capture_review_fixes.py', 'server/test_base_capture_feedback.py'}
        selected = {Path(path).relative_to(ROOT).as_posix() for path in suite.suites()}
        self.assertFalse(required - selected, 'Warehouse/base capture regressions must reach CI')

    def test_progression_weapon_and_buff_bank_regressions_are_included_in_ci(self):
        required = {'server/test_action_recovery.py', 'server/test_action_sync.py',
                    'server/test_mob_penetration.py', 'server/test_combat_xp_ramp.py',
                    'server/test_weekend_experience.py', 'server/test_hand_valentines.py',
                    'server/test_combat_xp_cap.py', 'server/test_aggro_hold.py',
                    'server/test_ground.py', 'server/test_war_state.py', 'server/test_loot.py',
                    'server/test_items.py', 'server/test_camp_box_loot.py',
                    'server/test_eden_native_weapons.py',
                    'server/test_buff_purchases.py', 'server/test_archived_buffs.py',
                    'server/test_bank_stacks.py',
                    'server/test_machinegun_burst_survival.py', 'server/test_machinegun_balance.py',
                    'server/test_mob_loot_followup.py', 'server/test_release_combat.py',
                    'server/test_scanner_loot.py', 'server/test_stat_pipeline.py',
                    'tools/test_action_recovery_client.py', 'tools/test_bank_client.py',
                    'tools/test_stat_breakdown_client.py',
                    'tools/test_medicine_cooldown_client.py', 'tools/test_tester_launcher.py'}
        selected = {Path(path).relative_to(ROOT).as_posix() for path in suite.suites()}
        self.assertFalse(required - selected)


    def test_buff_bank_transactions_are_also_scheduled_on_postgres(self):
        postgres = (ROOT / 'deploy/ci/pg_suites.sh').read_text(encoding='utf-8')
        groups = {name for group in re.findall(r'(?ms)^SUITES\+?=\((.*?)\)', postgres)
                  for name in group.split()}
        self.assertIn('bank_stacks', groups)

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

    def test_every_repository_test_is_discovered_or_in_the_postgres_job(self):
        expected = {path.relative_to(ROOT).as_posix()
                    for folder in ('server', 'data', 'tools', 'client')
                    for path in (ROOT / folder).rglob('test_*.py')}
        paths = suite.suites()
        actual = {suite.rel(path) for path in paths}
        separate = {'server/' + name + '.py' for name in suite.LEFT_OUT}
        postgres = (ROOT / 'deploy/ci/pg_suites.sh').read_text(encoding='utf-8')
        pg_suites = {'server/test_' + name + '.py'
                     for group in re.findall(r'(?ms)^SUITES\+?=\((.*?)\)', postgres)
                     for name in group.split()}
        self.assertEqual(actual, expected - separate)
        self.assertEqual(len(paths), len({suite.name_of(path) for path in paths}),
                         'Duplicate suite names overwrite results')
        self.assertLessEqual(separate, pg_suites)
        self.assertLessEqual(pg_suites, expected)

    def test_release_branches_select_every_suite_instead_of_the_impact_subset(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        block = re.search(r'(?ms)^          if \[ "\$PR_BASE_REF".*?^          fi',
                          workflow)
        self.assertIsNotNone(block)
        self.write('bin/python3', '#!/bin/sh\nprintf \'%s\\n\' "$@"\n')
        for base, head, full in (('main', 'release/combat', True),
                                 ('feature/base', 'feature/followup', True),
                                 ('main', 'feature/small-change', False)):
            with self.subTest(base=base, head=head):
                env = dict(os.environ, PATH=str(self.tree / 'bin') + os.pathsep + os.environ['PATH'],
                           PR_BASE_REF=base, PR_HEAD_REF=head,
                           RUNNER_TEMP=shell_path(self.tree))
                result = subprocess.run([self.bash, '-c', textwrap.dedent(block.group())],
                                        cwd=self.tree, env=env, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                args = (self.tree / 'pick.txt').read_text().splitlines()
                self.assertEqual(args, ['tools/suite.py', '--list'] if full else
                                 ['tools/suite.py', '--affected', '--list', '--base', 'origin/main'])

    def test_real_shards_cover_all_roots_once_with_and_without_durations(self):
        self.write('server/test_halfa_training.py', '')
        self.write('server/test_storage_pg.py', '')
        self.write('bin/python3', '#!/bin/sh\nexit 0\n')
        expected = {Path(path).stem for path in self.suites} | {'test_halfa_training'}
        for timed in (False, True):
            with self.subTest(previous_durations=timed):
                label = 'timed' if timed else 'static'
                counts = []
                for shard in range(1, 4):
                    out = self.tree / label / str(shard)
                    if timed:
                        self.write(label + '/' + str(shard) + '/summary.txt',
                                   ''.join('0 %ds %s\n' % (100 if n == 'test_alpha' else 1, n)
                                           for n in sorted(expected)))
                    result = self.shell('tools/run_suite.sh', '--shard', str(shard) + '/3',
                                        '.', shell_path(out), '2')
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    counts += [Path(path).stem for path in
                               (out / 'list.txt').read_text().splitlines()]
                self.assertEqual(set(counts), expected)
                self.assertEqual(len(counts), len(expected))
                result = self.shell('deploy/ci/merge_shards.sh',
                                    shell_path(self.tree / label),
                                    shell_path(self.tree / (label + '-merged.txt')))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
