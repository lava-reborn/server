"""One-command manual review stand. Uses only a separate local SQLite DB.

    python tools/local_review.py

No launcher/update service, installed resource writes or production DB.
The Flash window is visible and plays real audio for manual acceptance.
"""
import argparse
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'logs' / 'manual-review-2026-10-27'
MOVIE_PATH = '/res/main-review-2026-10-27.swf'
LOGIN, PASSWORD = 'Review27', 'review-local-27'


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def configure(res, game_port, http_port):
    os.environ.pop('LAVA_DB_URL', None)
    os.environ.update(
        LAVA_DB=str(WORK / 'review.sqlite'), LAVA_RES=str(res),
        LAVA_HOST='127.0.0.1', LAVA_PORT=str(game_port), LAVA_POLICY_PORT='0',
        LAVA_GAME_HOST='127.0.0.1', LAVA_GAME_PORT=str(game_port),
        LAVA_HTTP_HOST='127.0.0.1', LAVA_HTTP_PORT=str(http_port),
        LAVA_HTTP_RES='1', LAVA_CHEATS='1', LAVA_REGISTER_EMAIL='0',
        LAVA_ADMINS='', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')


def serve_web():
    sys.path.insert(0, str(ROOT / 'server'))
    import bootstrap_http as web

    class Handler(web.Handler):
        def _resource(self, path):
            if path != MOVIE_PATH:
                return super()._resource(path)
            payload = (WORK / 'review.swf').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-shockwave-flash')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    web.names.document()
    with web.Server(('127.0.0.1', int(os.environ['LAVA_HTTP_PORT'])), Handler) as http:
        print('Local review HTTP ready', flush=True)
        http.serve_forever()


def seed_account():
    sys.path.insert(0, str(ROOT / 'server'))
    import accounts
    store = accounts.Store()
    try:
        account = store.account_by_login(LOGIN)
        if account is None:
            account_id, error = store.register(LOGIN, PASSWORD)
            if error:
                raise RuntimeError(error)
        else:
            account_id = account['id']
        if not store.characters(account_id):
            store.create_character(account_id, 'Review', 0, '1', home=(102, 5965, 1728))
    finally:
        store.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--res', type=Path, default=Path('D:/lava-reborn/res'))
    ap.add_argument('--player', type=Path,
                    default=Path.home() / 'Downloads' / 'flashplayer_32_sa.exe')
    ap.add_argument('--web-child', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--prepare-only', action='store_true',
                    help='build the review movie and local account without opening Flash')
    args = ap.parse_args()
    if args.web_child:
        serve_web()
        return
    if not (args.res / 'main.swf').is_file() or not args.player.is_file():
        ap.error('Resources or Flash player missing; use --res and --player to set paths.')
    WORK.mkdir(parents=True, exist_ok=True)
    game_port, http_port = available_port(), available_port()
    while game_port == http_port:
        http_port = available_port()
    configure(args.res.resolve(), game_port, http_port)
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'widescreen.py'),
                    str(args.res / 'main.swf'), str(WORK / 'review.swf')],
                   cwd=ROOT, check=True)
    seed_account()
    if args.prepare_only:
        print('Prepared local review files in ' + str(WORK))
        return
    logs, children = [], []
    player = None
    try:
        for name, command in (
            ('game', [sys.executable, '-B', str(ROOT / 'server' / 'server.py')]),
            ('http', [sys.executable, '-B', str(Path(__file__).resolve()), '--web-child'])):
            log = open(WORK / (name + '.log'), 'w', encoding='utf-8')
            logs.append(log)
            children.append(subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log))
        url = 'http://127.0.0.1:%d%s?vversion=1' % (http_port, MOVIE_PATH)
        expected = hashlib.sha256((WORK / 'review.swf').read_bytes()).digest()
        deadline = time.monotonic() + 60
        while True:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('A local server stopped. See game.log / http.log in ' + str(WORK))
            try:
                with socket.create_connection(('127.0.0.1', game_port), timeout=.3):
                    pass
                with urllib.request.urlopen(url, timeout=1) as response:
                    if hashlib.sha256(response.read()).digest() != expected:
                        raise RuntimeError('Review SWF checksum mismatch')
                break
            except (OSError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    raise RuntimeError('Local start timed out; see logs in ' + str(WORK))
                time.sleep(.2)
        print('\nLOCAL REVIEW ONLY. Login: %s  Password: %s' % (LOGIN, PASSWORD), flush=True)
        print('Database: ' + str(WORK / 'review.sqlite'), flush=True)
        print('Close Flash, or press Ctrl+C here, to stop this stand.', flush=True)
        print('Test chat commands: /goto 103, /skill 1 16, /money 1000000 10000', flush=True)
        player = subprocess.Popen([str(args.player), url])
        player.wait()
        time.sleep(.5)  # let the local game process observe disconnect and save
    finally:
        if player is not None and player.poll() is None:
            player.terminate()
            player.wait(timeout=5)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nLocal review stopped.')
