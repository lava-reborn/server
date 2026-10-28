"""Opt-in real Flash: NPC quest offers after three minutes on the map.

LAVA_QUEST_QUEUE_CONTROL=1 runs the same stand with only the queue fix off.
This is not a reproduction of every production/network timing condition.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_location_transition as host
import widescreen as w
from testkit import check, fails

IDLE = int(os.environ.get('LAVA_QUEST_MAP_IDLE_SECONDS', '180'))
RETURN_AT = 30 + IDLE
LAST = RETURN_AT + 32


def probe(url):
    a = w.Asm()
    a.var('_root').push('tick').var('_root').member('tick').push(1).op('add2').op('setmember')
    a.push('m', 0).var('lol').member('core', 'Master').push('getInstance').op('callmethod').op('definelocal')
    a.push('qi', 0).var('lol').member('core', 'quests', 'QuestInspector').push('getInstance').op('callmethod').op('definelocal')
    a.push('ui').var('lol').member('core', 'SceneShifter', '_ref', 'currentScene').op('definelocal')
    a.push('r'); w.new(a, ['_global'], 'LoadVars', 0).op('definelocal')
    a.var('_root').member('tick').push(12).op('equals2').op('not').iftrue('not_goto')
    a.push('message'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
    a.var('message').push('group', 0).op('setmember')
    a.var('message').push('mess', '/goto 49').op('setmember')
    a.var('message').push(1).var('m').member('chat').push('sendMessage').op('callmethod').op('pop')
    a.label('not_goto')
    for tick, method in ((30, 'toGlobal'), (RETURN_AT, 'toLocation')):
        a.var('_root').member('tick').push(tick).op('equals2').op('not').iftrue('skip_world%d' % tick)
        a.push(0).var('ui').push(method).op('callmethod').op('pop')
        a.label('skip_world%d' % tick)
    for name, root, path in (
        ('tick', '_root', ('tick',)), ('state', 'm', ('currentState',)),
        ('loc', 'm', ('currentLocation', 'locInfo', 'locID')),
        ('inflight', 'lol', ('core', 'quests', 'QuestInspector', 'callCount')),
        ('queued', 'lol', ('core', 'quests', 'QuestInspector', 'callStack', 'length')),
        ('locked', 'qi', ('lockUpdate',)),
        ('ack', 'lol', ('server', 'XMLCCallStack', 'callList', 'cmdAck', 'commandList', 'length'))):
        a.var('r').push(name).var(root).member(*path).op('setmember')
    a.var('m').member('currentState').push('loc').op('equals2').op('not').iftrue('send')
    a.push('npcs', 0).var('qi').push('getNPCList').op('callmethod').op('definelocal')
    a.var('r').push('npcs').var('npcs').member('length').op('setmember')
    a.push('offers', 0).op('definelocal')
    a.push('i', 0).op('definelocal')
    a.label('npc_loop')
    a.var('i').var('npcs').member('length').op('less2').op('not').iftrue('npc_done')
    a.push('npc').var('npcs').var('i').op('getmember').op('definelocal')
    a.push('offers').var('offers').var('npc').push(1).var('qi').push('getGQs').op('callmethod').member('length').op('add2').op('definelocal')
    a.push('i').var('i').push(1).op('add2').op('definelocal')
    a.push(True).iftrue('npc_loop')
    a.label('npc_done')
    a.var('r').push('offers').var('offers').op('setmember')
    a.var('r').push('active', 0).var('qi').push('getCurrentQuestLength').op('callmethod').op('setmember')
    a.label('send')
    a.push('POST').var('r').push(url); w.call_method(a, 'r', 'sendAndLoad', 3)
    a.var('_root').member('activated').iftrue('out')
    a.var('m').member('gamer', 'playerInfo', 'name').op('not').iftrue('out')
    a.var('m').member('persGen', 'xmlInfoLoaded').op('not').iftrue('out')
    a.var('_root').push('activated', True).op('setmember')
    a.push(0).var('m').member('persGen').push('activatePlayer').op('callmethod').op('pop')
    a.label('out')
    return a


def prepare(store, cid):
    import progression
    import quests
    ch = progression.Character.load(store, cid)
    ch.set_skill(1, 16)
    ch.add_money(1000000, 10000)
    ch.save(store)
    for t in (31, 32, 33):
        q = quests.get(t)
        store.take_quest(cid, t, q.fresh_progress(), False)


def main():
    if not host.PLAYER or os.name != 'nt':
        print('SKIP: set LAVA_FLASH_PLAYER and LAVA_RES on Windows')
        return
    if not 1 <= IDLE <= 900:
        raise ValueError('LAVA_QUEST_MAP_IDLE_SECONDS must be 1..900')
    if os.environ.get('LAVA_CLIENT_MAIN'):
        host.SRC = Path(os.environ['LAVA_CLIENT_MAIN'])
    control = os.environ.get('LAVA_QUEST_QUEUE_CONTROL') == '1'
    if control:
        def original(name):
            a = w.Asm(); a.push(0).var('this').push(name).op('callmethod').op('pop')
            return a
        w.fn_quest_send_call = lambda: original('__questSendOrig')
        w.fn_quest_filter_resume = lambda: original('__questFilterOrig')
    host.probe, host.resize = probe, lambda *args: None
    host.RESIZE_AT, host.LAST, host.RUN_TIMEOUT = 99999, LAST, LAST + 60
    rows = host.run(True, prepare_store=prepare)
    mode = 'control' if control else 'patched'
    path = Path('logs/quest-map-return-%s.json' % mode)
    path.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    by_tick = {int(r['tick']): r for r in rows}
    before, idle, after = by_tick.get(29, {}), by_tick.get(RETURN_AT - 1, {}), by_tick.get(LAST - 1, {})
    print(json.dumps({'mode': mode, 'idle_seconds': IDLE, 'before': before, 'map_end': idle, 'after': after}, indent=2))
    if control:
        return  # diagnostic control can pass: a timing race is not guaranteed
    check('stand reaches the station before map travel', (before.get('state'), before.get('loc')), ('loc', '49'))
    check('stand remains on the global map during the idle period', idle.get('state'), 'gm')
    check('return from global map reaches a local scene', after.get('state'), 'loc')
    check('NPC quest offers are present after return', int(after.get('offers', '0')) > 0, True)
    check('quest reads and acknowledgement queue settle after return',
          (after.get('inflight'), after.get('queued'), after.get('locked'), after.get('ack')), ('0', '0', 'false', '0'))
    check('active quest log survives map travel', after.get('active'), '3')
    if fails:
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
