"""Local native tests + CI check scripts + security review. Never pushes/deploys.

Reports go to logs/local-checks/<unique run>. No scanner/dependency is installed
on the host automatically. All mode is the pre-push check; other modes are partial.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid

import suite

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = (
    'test_action_hotkeys', 'test_hotkey_windows', 'test_quick_medicine',
    'test_client_audio', 'test_client_audio_flash', 'test_item_frames',
    'test_item_frames_flash', 'test_quest_queue', 'test_quest_queue_flash',
    'test_quest_map_return', 'test_widescreen', 'test_weapon_tooltips',
    'test_quest_transactions', 'test_quest_state', 'test_prison_schedule',
    'test_boss_blueprints', 'test_equipment_level_wear', 'test_weapon_requirements',
    'test_equipment_release_cap', 'test_set_upgrade_transactions',
    'test_carry_weight', 'test_residence', 'test_residence_protocol',
    'test_residence_client', 'test_reload_sync', 'test_ks12_balance',
    'test_repair_policy', 'test_transport', 'test_transport_data',
    'test_set_look', 'test_tester_startup', 'test_tester_map_cache',
    'test_tester_avatar', 'test_tester_launcher',
)
SKIP = re.compile(r'(?im)^\s*(?:SKIP(?:PED)?\b|.*:\s*пропущено\b)|\bskipped=\d*[1-9]\d*')
WARN = re.compile(r'(?i)\b(?:ResourceWarning|DeprecationWarning|RuntimeWarning|UserWarning)\b|::warning')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def fingerprint():
    """Hash file contents, including untracked source; no source/secret contents in report."""
    h = hashlib.sha256()
    for directory in ('server', 'data', 'tools', 'client', 'launcher', 'deploy', '.github'):
        for p in sorted((ROOT / directory).rglob('*')):
            if not p.is_file() or any(x in p.parts for x in ('node_modules', '__pycache__')):
                continue
            if p.suffix not in ('.py', '.ps1', '.sh', '.json', '.yml', '.yaml', '.cs', '.txt',
                                '.xml', '.filter'):
                continue
            h.update(p.relative_to(ROOT).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def clean_env(res, player, client_main):
    # Never inherit a production DB URL, test clock, altered schedules or remote host.
    env = {k: v for k, v in os.environ.items() if not k.startswith('LAVA_')}
    env.update(LAVA_RES=str(res), LAVA_ORIG_TEXTS=str(res / 'xml' / 'texts.xml'),
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               PYTHONWARNINGS='always::ResourceWarning')
    if player.is_file():
        env['LAVA_FLASH_PLAYER'] = str(player)
    if client_main.is_file():
        env['LAVA_CLIENT_MAIN'] = str(client_main)
    return env


def asset_inputs(res):
    """Identify installed/painted map inputs without weakening the map tests."""
    base = ROOT / 'client' / 'base.txt'
    problems = []
    for line in base.read_text(encoding='utf-8').splitlines():
        fields = line.split('\t')
        if len(fields) != 3:
            continue
        expected, _size, path = fields
        if path != 'database/locations.xml' and not path.startswith('globalmap/full/'):
            continue
        source = res.joinpath(*path.split('/')).resolve()
        if not source.is_relative_to(res.resolve()):
            problems.append(dict(path=path, reason='invalid path outside resource directory'))
            continue
        if not source.is_file():
            problems.append(dict(path=path, reason='missing original asset'))
        else:
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual != expected:
                problems.append(dict(path=path, reason='differs from client/base.txt',
                                     expected=expected, actual=actual))
    return problems


def execute(name, command, out, env, timeout, processes, container=None):
    """Sample the whole live process tree; measurements are not gameplay benchmarks."""
    stdout, stderr = out / (name + '.out'), out / (name + '.err')
    start = time.monotonic()
    metrics = {'sampled_tree_peak_rss_bytes': None, 'sampled_tree_cpu_seconds': None}
    cpu, peak = {}, 0
    container_samples = []
    last_container_sample = 0.0
    psutil = None
    if importlib.util.find_spec('psutil'):
        import psutil
    print('START ' + name, flush=True)
    code, timed_out = None, False
    with stdout.open('w', encoding='utf-8') as fo, stderr.open('w', encoding='utf-8') as fe:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=fo, stderr=fe,
                                   **suite.OWN_GROUP)
        processes.append(process)
        heartbeat = start
        try:
            while True:
                if psutil:
                    try:
                        parent = psutil.Process(process.pid)
                        rss = 0
                        for child in [parent] + parent.children(recursive=True):
                            try:
                                key = (child.pid, child.create_time())
                                times = child.cpu_times()
                                cpu[key] = max(cpu.get(key, 0), times.user + times.system)
                                rss += child.memory_info().rss
                            except psutil.Error:
                                pass
                        peak = max(peak, rss)
                    except psutil.Error:
                        pass
                code = process.poll()
                if code is not None:
                    break
                now = time.monotonic()
                if container and now - last_container_sample >= 10:
                    try:
                        stats = subprocess.run(['docker', 'stats', '--no-stream', '--format',
                                                '{{json .}}', container], capture_output=True,
                                               text=True, timeout=5)
                        if stats.returncode == 0:
                            container_samples.append(dict(seconds=round(now-start, 1),
                                                          **json.loads(stats.stdout)))
                    except (OSError, ValueError, subprocess.SubprocessError):
                        pass
                    last_container_sample = now
                if now - start > timeout:
                    timed_out = True
                    suite.kill_group(process)
                    code = process.wait()
                    break
                if now - heartbeat >= 30:
                    print('RUNNING %s: %.0fs; logs: %s' % (name, now-start, stdout), flush=True)
                    heartbeat = now
                time.sleep(.25)
        finally:
            if process.poll() is None:
                suite.kill_group(process)
                process.wait()
            processes.remove(process)
    if psutil:
        metrics.update(sampled_tree_peak_rss_bytes=peak, sampled_tree_cpu_seconds=sum(cpu.values()))
    if container:
        write_json(out / (name + '-container-stats.json'), container_samples)
    print('END %s: exit=%s, %.1fs' % (name, code, time.monotonic()-start), flush=True)
    return dict(name=name, code=code, timed_out=timed_out,
                seconds=round(time.monotonic()-start, 3), metrics=metrics,
                stdout=stdout.name, stderr=stderr.name)


def ci_run(args, out, env, processes, phases, gaps):
    if not shutil.which('docker'):
        gaps.append('Docker is missing: Linux CI and isolated PostgreSQL did not run')
        return
    token = uuid.uuid4().hex[:12]
    network, postgres, worker = ('lava-check-' + token + x for x in ('-net', '-pg', '-ci'))
    password = secrets.token_hex(24)
    owned_network = False
    try:
        def docker_check(arguments):
            return subprocess.run(['docker'] + arguments, env=env, capture_output=True,
                                  timeout=180, check=True)
        docker_check(['network', 'create', network]); owned_network = True
        pg_env = dict(env, POSTGRES_PASSWORD=password)
        subprocess.run(['docker', 'run', '-d', '--name', postgres, '--network', network,
                        '--network-alias', 'postgres', '-e', 'POSTGRES_PASSWORD',
                        '-e', 'POSTGRES_USER=lava', '-e', 'POSTGRES_DB=postgres',
                        'postgres:16-alpine'], env=pg_env, capture_output=True,
                       timeout=600, check=True)
        for _ in range(90):
            result = subprocess.run(['docker', 'exec', postgres, 'pg_isready', '-U', 'lava'],
                                    capture_output=True, timeout=10)
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('isolated Postgres did not become ready')
        docker_env = dict(env, LAVA_PG='postgresql://lava:%s@postgres:5432' % password,
                          LOCAL_CHECK_JOBS=str(args.jobs))
        command = ['docker', 'run', '--rm', '--init', '--name', worker, '--network', network,
                   '--cpus', '2', '--memory', '4g',
                   '--mount', 'type=bind,src=%s,dst=/source,readonly' % ROOT,
                   '--mount', 'type=bind,src=%s,dst=/res,readonly' % args.res,
                   '--mount', 'type=bind,src=%s,dst=/reports' % out,
                   '-e', 'LAVA_PG', '-e', 'LOCAL_CHECK_JOBS', 'python:3.12-slim',
                   'bash', '-c', "sed 's/\r$//' /source/tools/local_ci_checks.sh > /tmp/check.sh; exec bash /tmp/check.sh"]
        phase = execute('linux-ci', command, out, docker_env, args.timeout, processes, worker)
        phase['metrics_note'] = 'Docker client only; container CPU/RSS not measured by host process sampling'
        phase['metrics'] = {k: None for k in phase['metrics']}
        phases.append(phase)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        # Never print a command/environment containing database credentials.
        gaps.append('Local Docker CI setup failed (%s); inspect Docker Desktop and prerequisites' % type(exc).__name__)
    finally:
        # Only this invocation's generated names. No host files/DBs are removed.
        subprocess.run(['docker', 'rm', '-f', worker], capture_output=True, timeout=60)
        # Also covers an interrupted `docker run` whose response was lost.
        subprocess.run(['docker', 'rm', '-f', postgres], capture_output=True, timeout=60)
        if owned_network:
            subprocess.run(['docker', 'network', 'rm', network], capture_output=True, timeout=60)


def security(out, env, timeout, processes, phases, gaps):
    findings = []
    for module in ('bandit', 'pip_audit'):
        if not importlib.util.find_spec(module):
            gaps.append('%s is not installed: security check unavailable' % module)
            continue
        result_file = out / (module + '.json')
        if module == 'bandit':
            command = [sys.executable, '-m', module, '-r', 'server', 'data', 'tools', 'client',
                       '--ignore-nosec', '-f', 'json', '-o', str(result_file)]
        else:
            # Uses advisory service over the internet; no --fix, no installs.
            command = [sys.executable, '-m', module, '--local', '--format', 'json',
                       '--output', str(result_file)]
        phase = execute(module, command, out, env, min(timeout, 900), processes)
        phases.append(phase)
        if not result_file.exists() or phase['timed_out']:
            gaps.append(module + ': no complete machine-readable security result')
            continue
        data = json.loads(result_file.read_text(encoding='utf-8'))
        if module == 'bandit':
            if data.get('errors'):
                gaps.append('Bandit could not analyse some files; see bandit.json')
            for item in data.get('results', []):
                findings.append(dict(scanner=module, id=item['test_id'],
                    severity=item['issue_severity'], confidence=item['issue_confidence'],
                    file=item['filename'], line=item['line_number'], text=item['issue_text']))
        else:
            for dep in data.get('dependencies', []):
                if dep.get('skip_reason'):
                    gaps.append('pip-audit: package %s not audited' % dep.get('name'))
                for vuln in dep.get('vulns', []):
                    findings.append(dict(scanner=module, id=vuln['id'],
                        package=dep['name'], version=dep.get('version'),
                        fixes=vuln.get('fix_versions', []), text=vuln.get('description', '')))
    return findings


def report(out, phases, gaps, findings, before, after, mode, interrupted):
    warnings, skips = [], []
    for p in sorted(out.rglob('*')):
        if p.suffix not in ('.out', '.err', '.log') or 'isolated' in p.parts:
            continue
        for number, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            entry = dict(file=str(p.relative_to(out)), line=number, text=line)
            if WARN.search(line): warnings.append(entry)
            if SKIP.search(line): skips.append(entry)
    # A Linux-only Flash skip is covered only by a successful, non-skipping
    # execution of the same suite on native Windows in this exact run.
    native_passed = set()
    summary = out / 'native' / 'summary.txt'
    if summary.is_file():
        for line in summary.read_text(encoding='utf-8').splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[0] == '0': native_passed.add(fields[2])
    native_skips = {Path(x['file']).stem for x in skips if x['file'].startswith('native')}
    native_passed -= native_skips
    unresolved = []
    for entry in skips:
        stem = Path(entry['file']).stem
        if entry['file'].startswith('ci') and stem in native_passed and re.search(
                r'(?i)flash|windows|LAVA_FLASH_PLAYER', entry['text']):
            entry['covered_by'] = 'native/' + stem
        else:
            unresolved.append(entry)
    if unresolved: gaps.append('Uncovered skipped checks detected; inspect skips.json')
    if before != after: gaps.append('Source files changed during the run; this report is stale')
    if mode != 'all': gaps.append('Partial mode: not a full pre-push check')
    if interrupted: gaps.append('Run interrupted')
    failed = [p['name'] for p in phases if p['code'] != 0 or p['timed_out']]
    # Preserve original failures even if the CI policy accepts a known failure
    # or a retry later passes. Such a run needs explicit human review.
    for p in out.rglob('summary*.txt'):
        if 'isolated' in p.parts: continue
        for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
            match = re.fullmatch(r'(-?\d+)\s+[\d.]+s\s+(\S+)', line.strip())
            if match and int(match[1]) != 0:
                failed.append('%s: %s (exit=%s)' % (p.relative_to(out), match[2], match[1]))
    ready = bool(phases) and not (failed or gaps or findings or warnings)
    payload = dict(mode=mode, ready_for_review=ready, source_before=before, source_after=after,
                   phases=phases, failed=failed, gaps=gaps, security_findings=findings,
                   warnings=warnings, skipped=skips)
    write_json(out / 'report.json', payload)
    write_json(out / 'warnings.json', warnings)
    write_json(out / 'skips.json', skips)
    timings = []
    for summary_file in out.rglob('summary.txt'):
        if 'isolated' in summary_file.parts: continue
        for line in summary_file.read_text(encoding='utf-8', errors='replace').splitlines():
            match = re.fullmatch(r'(-?\d+)\s+([\d.]+)s\s+(\S+)', line.strip())
            if match:
                timings.append(dict(suite=match[3], seconds=float(match[2]), code=int(match[1]),
                                    source=str(summary_file.relative_to(out))))
    timings.sort(key=lambda x: x['seconds'], reverse=True)
    write_json(out / 'timings.json', timings)
    lines = ['# Local checks', '', 'Status: ' + ('READY FOR REVIEW' if ready else 'NEEDS REVIEW'),
             '', 'No commit, push, deployment, production access or automatic fixes.', '',
             '## Phases', '', '| Phase | Exit | Seconds | Sampled peak MiB |', '|---|---:|---:|---:|']
    for p in phases:
        rss = p['metrics']['sampled_tree_peak_rss_bytes']
        lines.append('| %s | %s | %.1f | %s |' % (p['name'], p['code'], p['seconds'],
                     'unavailable' if rss is None else '%.1f' % (rss / 1048576)))
    lines += ['', '## Gaps / failures', ''] + ['- ' + x for x in failed + gaps]
    lines += ['', '## Security findings (all returned findings, require triage)', '']
    lines += ['- ' + json.dumps(x, ensure_ascii=False) for x in findings]
    lines += ['', '## Slowest suite records (not production performance)', '']
    lines += ['- %(suite)s: %(seconds).1fs, exit=%(code)s (%(source)s)' % x for x in timings[:20]]
    lines += ['', 'Security findings: ' + str(dict(Counter(x['scanner'] for x in findings))),
              'Warning records: %d; skip records: %d.' % (len(warnings), len(skips))]
    lines += ['', '## Measurements / limitations', '',
              '- Native: per-suite seconds and checks in native/report.html and native/summary.txt.',
              '- CI: per-stage seconds in ci/stages.tsv, per-suite output in ci/shards and ci/postgres; sampled container CPU/memory in linux-ci-container-stats.json.',
              '- CPU/RSS sampling can miss short-lived processes; Docker server/container memory is not host client RSS.',
              '- No gameplay FPS, SQL timings, load or farm simulation. Slow tests are candidates for investigation, not proof of slow production.',
              '- All warnings: warnings.json; skipped checks: skips.json; raw security output: bandit.json / pip_audit.json.',
              '- pip-audit covers this Python environment, not every deployed dependency. Bandit covers Python, not Flash/C#/infrastructure.',
              '- Security scanners cannot prove the absence of vulnerabilities. Manual auth/transport and transaction review remains necessary.',
              '- Remote Actions artifact/cache transport and deployment are not emulated; GitHub CI remains required.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n' + '\n'.join(lines), flush=True)
    print('\nReport: ' + str(out / 'report.md'), flush=True)
    return 0 if ready else (1 if failed or findings else 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('all', 'native', 'ci', 'regression'), default='all')
    parser.add_argument('--res', type=Path, required=True)
    parser.add_argument('--player', type=Path, required=True)
    parser.add_argument('--client-main', type=Path, default=ROOT.parent / 'main (1).swf')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--timeout', type=int, default=21600)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8 or args.timeout < 60:
        parser.error('jobs must be 1..8 and timeout at least 60 seconds')
    args.res = args.res.resolve()
    out = (args.out or ROOT / 'logs' / 'local-checks' /
           (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])).resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = clean_env(args.res, args.player.resolve(), args.client_main.resolve())
    temp = out / 'isolated'; temp.mkdir()
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), LAVA_DB=str(temp / 'local.sqlite'))
    phases, gaps, processes, findings = [], [], [], []
    write_json(out / 'inventory.json', dict(
        native_suites=[str(Path(p).relative_to(ROOT)) for p in suite.suites()],
        postgres_inventory_source='deploy/ci/pg_suites.sh (same script as GitHub CI)',
        python=sys.version, platform=sys.platform, jobs=args.jobs, mode=args.mode,
        timeout_seconds=args.timeout))
    before = fingerprint()
    interrupted = False
    try:
        if not (args.res / 'database' / 'objects.xml').is_file():
            gaps.append('Missing res/database/objects.xml; tests cannot run')
        else:
            if args.mode != 'regression':
                inputs = asset_inputs(args.res)
                write_json(out / 'asset-inputs.json', inputs)
                if inputs:
                    gaps.append('Map inputs are not pristine: see asset-inputs.json; use original test resources')
                    print('INPUT WARNING: %d map assets differ from the original or are missing; '
                          'map checks may fail. Installed game files will not be changed.' % len(inputs), flush=True)
            if args.mode in ('all', 'native', 'regression'):
                if os.name != 'nt' or not args.player.is_file() or not args.client_main.is_file():
                    gaps.append('Real Flash coverage needs Windows, player and original main (1).swf')
                native = out / 'native'
                command = [sys.executable, '-B', str(ROOT / 'tools' / 'suite.py'),
                           '--out', str(native), '--jobs', str(args.jobs), '--res', str(args.res)]
                if args.mode == 'regression': command += ['--only', ','.join(REGRESSION)]
                phases.append(execute('native', command, out, env, args.timeout, processes))
            if args.mode in ('all', 'ci'):
                ci_run(args, out, env, processes, phases, gaps)
        if not importlib.util.find_spec('psutil'):
            gaps.append('psutil is missing: CPU/RSS measurements unavailable')
        findings = security(out, env, args.timeout, processes, phases, gaps)
    except KeyboardInterrupt:
        interrupted = True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        gaps.append('Runner error: ' + type(exc).__name__ + '; inspect phase logs')
    finally:
        for process in processes[:]:
            suite.kill_group(process)
            process.wait()
    return report(out, phases, gaps, findings, before, fingerprint(), args.mode, interrupted)


if __name__ == '__main__':
    sys.exit(main())
