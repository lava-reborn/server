"""Opt-in real Flash: window hotkeys, running, chat and world transitions.

Uses an isolated local server and invokes the real client's keyPress/keyRelease
and UI handlers. This does not emulate physical Windows keyboard focus.
LAVA_FLASH_PLAYER, LAVA_RES and optionally LAVA_CLIENT_MAIN select inputs.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_location_transition as host
import widescreen as w
from testkit import check, fails

# One second between phases; loading and animation have their own settling
# intervals. A real listener observes whether the HotKeyManager dispatches.
KEYS = {14: 80, 16: 80, 18: 80, 20: 27,
        22: 73, 24: 73, 26: 73,
        30: 78, 32: 27, 34: 80,
        38: 73, 44: 80, 46: 80,
        54: 80, 56: 27, 58: 13, 60: 27,
        64: 73, 74: 80, 76: 27}
CLOSE_BUTTONS = (28, 36)
RAPID_KEYS = {80: 80, 84: 73}
WORLD_BUTTONS = (40, 48, 66, 70)
CHECKPOINTS = {17: ('loc', 'running stats/P'),
               21: ('loc', 'running stats/Esc'),
               25: ('loc', 'inventory/I'),
               29: ('loc', 'inventory/button'),
               33: ('loc', 'settings/Esc'),
               37: ('loc', 'stats/button'),
               47: ('gm', 'map stats/P'),
               57: ('loc', 'return and stats/Esc'),
               61: ('loc', 'chat/Esc'),
               77: ('loc', 'repeated world transitions'),
               82: ('loc', 'rapid P open/close before init'),
               86: ('loc', 'rapid I open/close before init')}


def probe(url, destination):
    a = w.Asm()
    a.var('_root').push('tick').var('_root').member('tick').push(1).op('add2').op('setmember')
    a.push('m', 0).var('lol').member('core', 'Master').push('getInstance').op('callmethod').op('definelocal')
    a.push('hk').var('lol').member('core', 'SceneShifter', 'hotKeyManager').op('definelocal')
    a.push('ui').var('lol').member('core', 'SceneShifter', '_ref', 'currentScene').op('definelocal')
    a.push('r'); w.new(a, ['_global'], 'LoadVars', 0).op('definelocal')
    a.var('_root').member('tick').push(12).op('equals2').op('not').iftrue('not_start')
    a.push(destination, 1).var('m').member('currentLocation').push('getCellFromNumber').op('callmethod')
    a.push(1).var('m').member('currentLocation').push('movePlayer').op('callmethod').op('pop')
    observer = w.Asm()
    observer.var('_root').push('hotkeySeen', True).op('setmember')
    a.var('_root').push('observe').function(('obj',), observer).op('setmember')
    # CENTER_ON_CHAR has a real handler in both local and global scenes.
    a.var('_root').member('observe').var('_root').var('lol').member('services', 'HotKeyEvent', 'CENTER_ON_CHAR')
    a.push(3).var('hk').push('addEventListener').op('callmethod').op('pop')
    a.label('not_start')
    for tick, key in sorted(KEYS.items()):
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_key%d' % tick)
        a.push(key, 1).var('hk').push('keyPress').op('callmethod').op('pop')
        a.push(key, 1).var('hk').push('keyRelease').op('callmethod').op('pop')
        a.label('skip_key%d' % tick)
    for tick, key in RAPID_KEYS.items():
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_rapid%d' % tick)
        for _ in range(2):
            a.push(key, 1).var('hk').push('keyPress').op('callmethod').op('pop')
            a.push(key, 1).var('hk').push('keyRelease').op('callmethod').op('pop')
        a.label('skip_rapid%d' % tick)
    for tick in CLOSE_BUTTONS:
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_close%d' % tick)
        a.push(0).var('lol').member('core', 'SceneShifter', '_sl').push('closeWinBtn_func').op('callmethod').op('pop')
        a.label('skip_close%d' % tick)
    for tick in WORLD_BUTTONS:
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_world%d' % tick)
        a.push(0).var('ui').push('toGlobal' if tick in (40, 66) else 'toLocation').op('callmethod').op('pop')
        a.label('skip_world%d' % tick)
    for tick in CHECKPOINTS:
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_check%d' % tick)
        a.var('_root').push('hotkeySeen', False).op('setmember')
        a.push(67, 1).var('hk').push('keyPress').op('callmethod').op('pop')
        a.push(67, 1).var('hk').push('keyRelease').op('callmethod').op('pop')
        a.label('skip_check%d' % tick)
    for field, root, path in (
        ('tick', '_root', ('tick',)), ('seen', '_root', ('hotkeySeen',)),
        ('enabled', 'hk', ('enabled',)), ('filters', 'hk', ('hotKeyFilter_arr',)),
        ('key_count', 'hk', ('keyStack', 'length')), ('state', 'm', ('currentState',)),
        ('pos', 'm', ('gamer', 'walker', 'numPos')),
        ('finish', 'm', ('gamer', 'walker', 'finishPos')),
        ('pending_ack', 'lol', ('server', 'XMLCCallStack', 'callList', 'cmdAck', 'commandList', 'length'))):
        a.var('r').push(field).var(root).member(*path).op('setmember')
    a.var('r').push('focus').push(0).var('Selection').push('getFocus').op('callmethod').op('setmember')
    a.push('POST').var('r').push(url); w.call_method(a, 'r', 'sendAndLoad', 3)
    a.var('_root').member('activated').iftrue('out')
    a.var('m').member('gamer', 'playerInfo', 'name').op('not').iftrue('out')
    a.var('m').member('persGen', 'xmlInfoLoaded').op('not').iftrue('out')
    a.var('_root').push('activated', True).op('setmember')
    a.push(0).var('m').member('persGen').push('activatePlayer').op('callmethod').op('pop')
    a.label('out')
    return a


def main():
    if not host.PLAYER or os.name != 'nt':
        print('SKIP: set LAVA_FLASH_PLAYER and LAVA_RES on Windows')
        return
    source = os.environ.get('LAVA_CLIENT_MAIN')
    if source:
        host.SRC = Path(source)
    import world, mobs
    loc = world.location(102)
    start = loc.entry_cell()
    candidates = sorted(set(range(loc.width * loc.height)) - loc.obstacles,
                        key=lambda c: mobs.hex_distance(start, c, loc.width), reverse=True)
    destination = next(c for c in candidates if mobs.find_path(loc, start, lambda x: x == c, set()))
    host.probe = lambda url: probe(url, destination)
    host.resize = lambda *args: None
    host.RESIZE_AT, host.LAST = 999, 88
    reports = host.run(True)
    output = os.environ.get('LAVA_HOTKEY_REPORT')
    if output:
        Path(output).write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    by_tick = {int(r['tick']): r for r in reports}
    moving = by_tick.get(15, {})
    check('stats are opened while the character is still moving',
          moving.get('pos') not in (None, 'undefined', moving.get('finish')), True)
    check('stats really install their modal filter', moving.get('filters'), 'location,persInfo')
    for tick, (state, label) in CHECKPOINTS.items():
        row = by_tick.get(tick, {})
        expected_filter = 'global' if state == 'gm' else 'location'
        check(label + ': keyboard and window state restored',
              (row.get('state'), row.get('enabled'), row.get('seen'), row.get('filters'), row.get('key_count')),
              (state, 'true', 'true', expected_filter, '0'))
        check(label + ': command acknowledgement queue drains', row.get('pending_ack'), '0')
    check('chat focuses and intentionally suppresses game hotkeys',
          (by_tick.get(59, {}).get('enabled'), by_tick.get(59, {}).get('filters')),
          ('false', 'location,chat'))
    if fails:
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
