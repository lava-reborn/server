"""Build a private local tester kit from working-tree files. Never runs tests."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def copy_tree(src, dst, allowed=None):
    for source in src.rglob('*'):
        rel = source.relative_to(src)
        if not source.is_file() or any(p in ('__pycache__', '.git') for p in rel.parts):
            continue
        if allowed is not None and not allowed(source):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)



def ensure_tester_avatar(res):
    """Keep the synthetic characters' portrait 1 resolvable after userInfo."""
    import xml.etree.ElementTree as ET
    res = Path(res)
    path = res / 'avatars/list.xml'
    text = path.read_text(encoding='utf-8-sig')
    tree = ET.fromstring(text)
    if any(row.get('id') == '1' for row in tree.findall('./avatars/a')):
        return False
    if not (res / 'avatars/1_1.png').is_file():
        raise RuntimeError('Tester portrait 1_1.png is missing')
    if text.count('</avatars>') != 1:
        raise ValueError('Unexpected avatar list')
    row = "<a id='1' sex='0' buy='free'>Тестовый персонаж.</a>\n"
    path.write_text(text.replace('</avatars>', row + '</avatars>'), encoding='utf-8')
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--res', type=Path, required=True)
    ap.add_argument('--player', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists() or out.with_suffix('.zip').exists():
        ap.error('Output already exists; choose a new directory (no overwrite).')
    if not (args.res / 'main.swf').is_file() or not args.player.is_file():
        ap.error('Missing original resources or Flash projector.')
    out.mkdir(parents=True)
    print('Copying game resources...', flush=True)
    # Only game asset formats; cache databases, binaries and user data stay out.
    assets = {'.swf', '.xml', '.jpg', '.jpeg', '.png', '.mp3', '.wav', '.gif', '.txt'}
    copy_tree(args.res, out / 'res', lambda p: p.suffix.lower() in assets)
    copy_tree(ROOT / 'client' / 'files', out / 'res')
    print('Copying current server and data...', flush=True)
    copy_tree(ROOT / 'server', out / 'server',
              lambda p: p.suffix == '.py' and not p.name.startswith('test_'))
    copy_tree(ROOT / 'data', out / 'data', lambda p: (
        p.suffix.lower() in {'.json', '.xml', '.py', '.png', '.swf', '.html', '.txt', '.md'}
        and not p.name.startswith('test_')))
    copy_tree(ROOT / 'client' / 'objects', out / 'client' / 'objects')
    (out / 'tools').mkdir()
    for name in ('custom_objects.py', 'swfgen.py', 'tester_map_cache.py'):
        shutil.copy2(ROOT / 'tools' / name, out / 'tools' / name)
    # D: contains a previous local map build: retain its recovered original labels.
    original_map = ROOT / 'logs' / 'boss-schedule-map-fixture' / 'database' / 'locations.xml'
    if original_map.is_file():
        shutil.copy2(original_map, out / 'res' / 'database' / 'locations.xml')
    ensure_tester_avatar(out / 'res')
    print('Building client with current patches...', flush=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'widescreen.py'),
                    str(args.res / 'main.swf'), str(out / 'res' / 'main.swf')],
                   cwd=ROOT, check=True)
    from tester_preloader import build as build_preloader
    build_preloader(out / 'res' / 'main.swf', out / 'res' / 'tester-start.swf')
    print('Copying self-contained Python and Flash...', flush=True)
    runtime = out / 'python'
    runtime.mkdir()
    base = Path(sys.base_prefix)
    for source in base.iterdir():
        if source.is_file() and (source.suffix.lower() in ('.exe', '.dll') or source.name == 'LICENSE.txt'):
            shutil.copy2(source, runtime / source.name)
    copy_tree(base / 'DLLs', runtime / 'DLLs')
    copy_tree(base / 'Lib', runtime / 'Lib', lambda p: not any(
        part in {'site-packages', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', '__pycache__'}
        for part in p.relative_to(base / 'Lib').parts))
    (out / 'player').mkdir()
    shutil.copy2(args.player, out / 'player' / 'flashplayer_32_sa.exe')
    shutil.copy2(ROOT / 'tools' / 'tester_runtime.py', out / 'start.py')
    from build_tester_launcher import build as build_launcher
    build_launcher(out)
    print('Creating 20 synthetic accounts in a NEW isolated SQLite database...', flush=True)
    (out / 'state').mkdir()
    for key in list(os.environ):
        if key.startswith('LAVA_'):
            del os.environ[key]
    os.environ.update(LAVA_DB=str(out / 'state' / 'tester.sqlite'), LAVA_RES=str(out / 'res'))
    sys.path.insert(0, str(out / 'server'))
    import accounts
    import progression
    store = accounts.Store()
    credentials = []
    try:
        for level in range(1, 21):
            login = 'Tester%02d' % level
            password = secrets.token_hex(8)
            account_id, error = store.register(login, password)
            if error:
                raise RuntimeError(error)
            char_id, _ = store.create_character(account_id, login, 0, '1', home=(102, 5965, 1728))
            ch = progression.Character.load(store, char_id)
            ch.set_skill(progression.SHOOTING, level)
            ch.afro, ch.gold = 5_000_000, 100_000  # gold is stored in hundredths
            ch.save(store)
            credentials.append((login, password, level, 1000, 5000000))
        rows = store.db.execute('SELECT level, afro, gold FROM characters ORDER BY level').fetchall()
        if [(r['level'], r['afro'], r['gold']) for r in rows] != [
                (level, 5000000, 100000) for level in range(1, 21)]:
            raise RuntimeError('Seed account totals do not match requested values.')
    finally:
        store.close()
    with (out / 'accounts.csv').open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.writer(target, delimiter=';')
        writer.writerow(('Login', 'Password', 'Level', 'Gold', 'Afro'))
        writer.writerows(credentials)
    (out / 'READ_ME.txt').write_text(
        'ЛОКАЛЬНЫЙ ТЕСТОВЫЙ КОМПЛЕКТ — Windows x64\n\n'
        '1. Полностью распакуйте ZIP в отдельную папку, например C:\\LavaTest.\n'
        '2. Закройте другие локальные серверы игры (порты 19775 и 18080).\n'
        '3. Откройте TestLauncher.exe или Start.vbs. Нажмите «Играть». Подготовка отображается во Flash.\n'
        '4. В открывшемся Flash введите логин и пароль из accounts.csv.\n'
        '5. Для быстрого повторного входа закройте Flash и снова нажмите «Играть». Для завершения закройте лаунчер.\n\n'
        'Python и Flash уже включены. Docker, Git и установка Python не нужны.\n'
        '20 аккаунтов Tester01–Tester20, уровни 1–20 через навык стрельбы.\n'
        'Каждому выдано 1000 G и 5 000 000 афро. Старт: рынок Вади-Хальфы.\n'
        'Другие навыки, специализации и задания исходные; снаряжение не выдано.\n'
        'Специализации можно изучить у учителей. Локальные команды:\n'
        '/goto 103 — перейти на локацию; /skill 1 16 — стрельба 16.\n'
        'Они работают только на этом тестовом сервере с включённым LAVA_CHEATS.\n'
        'Деньги, покупки и прогресс сохраняются в state/tester.sqlite.\n'
        'Для возврата начальных данных закройте комплект и распакуйте ZIP заново в новую папку.\n'
        'Сервер слушает только 127.0.0.1. Связи с продакшеном и его базой нет.\n'
        'Пароли тестовые; не используйте их для реальных аккаунтов.\n'
        'При ошибке пришлите state/game.log и state/http.log.\n\n'
        'ЧТО ПРОВЕРИТЬ:\n'
        '1. P и повторное P, Esc; статы во время бега; свернуть/развернуть игру.\n'
        '   После каждого действия должны работать движение и хоткеи.\n'
        '2. Громкость выстрелов и музыки, смена трека, переходы локация/глобальная карта.\n'
        '3. Золотые рамки предметов, подсветка и кнопка информации у торговцев и в рюкзаке.\n'
        '4. Несколько минут на глобальной карте, затем вокзал: квесты NPC должны открыться без перезахода.\n'
        '5. Оазис: улучшение каждой части G-сета, половина цены НОВОЙ части; максимум 17 уровень.\n'
        '6. Продажа и получение оружия/брони 18–20 уровней должны быть недоступны.\n'
        '7. ПММ контрабандиста уровней 4 и 5: магазин 7 патронов, перезарядка тратит нужное число.\n'
        '8. КС-12: стоимость ОД за выстрел и показанная цена обычного ремонта соответствуют текущему ребалансу.\n'
        '9. Обычная медицина вне боя выбирается первой; сравните кнопку и хоткей.\n\n'
        'Это сборка текущих незакоммиченных правок. Автотесты и игровая проверка при сборке не запускались.\n'
        'Снятие требований к уровню и новая прогрессия износа, прописка/ВНЖ ещё НЕ реализованы.\n',
        encoding='utf-8-sig')
    print('Writing checksums and ZIP...', flush=True)
    manifest = {}
    for source in sorted(out.rglob('*')):
        if source.is_file():
            with source.open('rb') as stream:
                manifest[source.relative_to(out).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (out / 'SHA256.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    archive = out.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
        for source in sorted(out.rglob('*')):
            if source.is_file():
                zipped.write(source, str(Path(out.name) / source.relative_to(out)))
    print('READY: ' + str(archive), flush=True)


if __name__ == '__main__':
    main()
