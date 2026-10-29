"""Launcher for an isolated, portable Windows tester bundle. No production DB."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parent


def configure():
    # Inherited developer/production configuration must never select this DB.
    for key in list(os.environ):
        if key.startswith('LAVA_'):
            del os.environ[key]
    os.environ.update(
        LAVA_DB=str(ROOT / 'state' / 'tester.sqlite'),
        LAVA_RES=str(ROOT / 'res'), LAVA_HOST='127.0.0.1',
        LAVA_PORT='19775', LAVA_POLICY_PORT='0', LAVA_GAME_HOST='127.0.0.1',
        LAVA_GAME_PORT='19775', LAVA_HTTP_HOST='127.0.0.1',
        LAVA_HTTP_PORT='18080', LAVA_HTTP_RES='1', LAVA_CHEATS='1',
        LAVA_REGISTER_EMAIL='0', LAVA_ADMINS='',
        LAVA_BOSS_HOURS=','.join(str(i) for i in range(0, 24, 2)),
        LAVA_BOSS_TZ='Europe/Moscow', LAVA_BOSS_STAY='60',
        LAVA_WAREHOUSE_HOURS='20', LAVA_START='181', LAVA_START_AFRO='1000',
        PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')


def instance_id():
    """Bind launcher readiness to this backend, not another kit on the same port."""
    if '--instance' not in sys.argv:
        return ''  # Direct/legacy startup does not have a controlling launcher.
    index = sys.argv.index('--instance') + 1
    value = sys.argv[index] if index < len(sys.argv) else ''
    if len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid local launcher instance identifier')
    return value


class StartupState:
    def __init__(self, instance=''):
        self.instance = instance
        self.lock = threading.Lock()
        self.values = dict(progress=1, stage='Запуск локального сервера…', ready=0)

    def update(self, progress, stage, ready=0):
        with self.lock:
            self.values = dict(progress=progress, stage=stage, ready=ready)

    def encoded(self):
        with self.lock:
            return urlencode(dict(self.values, instance=self.instance)).encode('ascii')


def startup_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/startup-status':
                body, kind = state.encoded(), 'application/x-www-form-urlencoded; charset=UTF-8'
            elif path == '/res/tester-start.swf':
                body, kind = (ROOT / 'res' / 'tester-start.swf').read_bytes(), 'application/x-shockwave-flash'
            else:
                self.send_error(503, 'Preparing game')
                return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass
    return Handler


def serve_http():
    state = StartupState(instance_id())
    handler = startup_handler(state)
    with ThreadingHTTPServer(('127.0.0.1', 18080), handler) as http:
        def prepare():
            try:
                import bootstrap_http as web
                state.update(15, 'Подготовка игровых данных…')
                web.names.document()
                state.update(35, 'Подготовка глобальной карты…')
                from tester_map_cache import prepare as prepare_map
                def map_progress(percent, phase):
                    titles = dict(zones='Подготовка карты…', labels='Обновление подписей карты…',
                                  paint='Подготовка клеток карты…', encode='Сохранение карты…',
                                  done='Карта готова…', cached='Карта загружена из кэша…')
                    state.update(35 + percent // 2, titles[phase])
                prepare_map(web, ROOT, map_progress)
                state.update(90, 'Проверка готовности сервера…')
                deadline = time.monotonic() + 600
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1', 19775), timeout=.5):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Game server startup timeout')
                        time.sleep(.3)
                class ReadyHandler(web.Handler):
                    def do_GET(self):
                        if urlsplit(self.path).path in ('/startup-status', '/res/tester-start.swf'):
                            return handler.do_GET(self)
                        return super().do_GET()
                # Install normal routes before allowing Flash to load main.swf.
                http.RequestHandlerClass = ReadyHandler
                state.update(100, 'Загрузка клиента…', 1)
            except Exception:
                import traceback
                traceback.print_exc()
                state.update(1, 'Ошибка запуска. Подробности в state/http.log.', -1)
        threading.Thread(target=prepare, name='startup', daemon=True).start()
        http.serve_forever()


def main():
    configure()
    instance = instance_id()
    sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'tools')]
    if '--http' in sys.argv:
        serve_http()
        return
    if not (ROOT / 'state' / 'tester.sqlite').is_file():
        raise RuntimeError('Missing state/tester.sqlite. Extract the complete bundle.')
    for port in (19775, 18080):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    children, logs = [], []
    worker_python = Path(sys.executable).with_name('python.exe')
    worker_python = str(worker_python) if worker_python.is_file() else sys.executable
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    player = None
    backend = '--backend' in sys.argv
    stopped = threading.Event()
    if backend:
        def control():
            if sys.stdin is not None:
                sys.stdin.readline()  # stop command or pipe closed with launcher
            stopped.set()
        threading.Thread(target=control, daemon=True).start()
    try:
        for name, argv in (
            ('game', [worker_python, '-B', str(ROOT / 'server' / 'server.py')]),
            ('http', [worker_python, '-B', str(Path(__file__).resolve()), '--http'])):
            if name == 'http' and instance:
                argv += ['--instance', instance]
            log = open(ROOT / 'state' / (name + '.log'), 'w', encoding='utf-8')
            logs.append(log)
            children.append(subprocess.Popen(
                argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, creationflags=hidden))
        url = 'http://127.0.0.1:18080/res/tester-start.swf'
        print('Starting local servers and preparing resources.', flush=True)
        deadline = time.monotonic() + 600
        while True:
            if stopped.is_set():
                return
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Server stopped. See state/game.log and state/http.log.')
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.read(3) not in (b'CWS', b'FWS'):
                        raise RuntimeError('Unexpected client response.')
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Startup timeout. See state/*.log.')
                stopped.wait(.3)
        if backend:
            while not stopped.wait(.3):
                if any(child.poll() is not None for child in children):
                    raise RuntimeError('Local server stopped; see state/*.log.')
            time.sleep(2)  # let a recently closed game save its disconnect
            return
        print('Opening Flash startup screen. Accounts: accounts.csv. Close Flash to stop the local servers.', flush=True)
        player = subprocess.Popen([str(ROOT / 'player' / 'flashplayer_32_sa.exe'), url])
        while player.poll() is None:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Server stopped. See state/game.log and state/http.log.')
            if time.monotonic() >= deadline:
                with urllib.request.urlopen('http://127.0.0.1:18080/startup-status', timeout=2) as response:
                    if b'ready=1' not in response.read():
                        raise RuntimeError('Startup timeout. See state/http.log.')
                deadline = float('inf')
            time.sleep(.3)
        time.sleep(2)  # allow the game to save the disconnect
    finally:
        if player is not None and player.poll() is None:
            player.terminate()
            player.wait(timeout=10)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == '__main__':
    if sys.stdout is None:
        stream = open(ROOT / 'state' / 'startup.log', 'a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr = stream
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.')
    except Exception as error:
        import traceback
        traceback.print_exc()
        if '--backend' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Lava Reborn — запуск', 0x10)
        raise SystemExit(1)
