"""Real Flash quest reads through original CW/LOCAL filters, no socket sends."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_location_transition as host
import widescreen as w
from testkit import check, fails


def probe(url):
    a = w.Asm()
    a.var('_root').push('tick').var('_root').member('tick').push(1).op('add2').op('setmember')
    a.push('r'); w.new(a, ['_global'], 'LoadVars', 0).op('definelocal')
    a.var('r').push('tick').var('_root').member('tick').op('setmember')
    a.var('_root').member('tick').push(4).op('equals2').op('not').iftrue('send')
    a.push('cls').var('lol').member('core', 'quests', 'QuestInspector').op('definelocal')
    a.push('master', 0).var('lol').member('core', 'Master').push('getInstance').op('callmethod').op('definelocal')
    a.push('filters', 0).var('lol').member('server', 'filters', 'FilterManager').push('getInstance').op('callmethod').op('definelocal')
    a.push('oldState').var('master').member('_currentState').op('definelocal')
    a.push('oldFilter').var('filters').member('currentFilter').op('definelocal')
    for key in ('callStack', 'callCount', 'sInstance'):
        a.push('old' + key).var('cls').member(key).op('definelocal')
    for mode in ('before', 'after'):
        a.var('cls').push('callStack', 0).op('initarray').op('setmember')
        a.var('cls').push('callCount', 0).op('setmember')
        a.var('filters').push('currentFilter').var('filters').member('cwFilter').op('setmember')
        a.push('ins'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
        a.push('conn'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
        a.var('conn').push('filters').var('filters').op('setmember')
        a.var('conn').push('sent', 0).op('setmember')
        send = w.Asm()
        send.push('allowed').var('message').push(1).var('this').member('filters').push('isValid').op('callmethod').op('definelocal')
        send.var('allowed').op('not').iftrue('out')
        send.var('this').push('sent').var('this').member('sent').push(1).op('add2').op('setmember')
        send.label('out'); send.var('allowed').op('return')
        a.var('conn').push('Send').function(('message',), send).op('setmember')
        a.var('ins').push('XMC').var('conn').op('setmember')
        for key in ('checkedQuests', 'checkedNPC'):
            a.var('ins').push(key, 0).op('initarray').op('setmember')
        a.var('ins').push('statusCount', 0).op('setmember')
        for name in ('addCall', 'sendCall', 'checkQStatus', 'updateCall', 'questStatus'):
            source = '__questSendOrig' if mode == 'before' and name == 'sendCall' else name
            a.var('ins').push(name).var('cls').member('prototype', source).op('setmember')
        # Only stand-ins for quest display; queue/filter/response methods are real.
        a.push('quest'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
        for name in ('addEventListener', 'setName'):
            a.var('quest').push(name).function(('arg',), w.Asm()).op('setmember')
        a.var('ins').push('quest').var('quest').op('setmember')
        make = w.Asm(); make.var('this').member('quest').op('return')
        a.var('ins').push('createQuest').function(('type',), make).op('setmember')
        for name in ('questUpdate', 'checkStatusChanged'):
            a.var('ins').push(name).function((), w.Asm()).op('setmember')
        a.var('cls').push('sInstance').var('ins').op('setmember')
        for quest, npc in ((273, 123), (274, 124)):
            a.push(npc, quest, 2).var('ins').push('checkQStatus').op('callmethod').op('pop')

        def record(phase):
            for label, path in (('inflight', ('callCount',)), ('queued', ('callStack', 'length'))):
                a.var('r').push(mode + '_' + phase + '_' + label).var('cls').member(*path).op('setmember')
            a.var('r').push(mode + '_' + phase + '_sent').var('conn').member('sent').op('setmember')

        record('blocked')
        a.var('master').push('_currentState').var('lol').member('core', 'Master', 'LOCAL_STATE').op('setmember')
        a.push(0).var('filters').push('__questFilterOrig' if mode == 'before' else 'changeState').op('callmethod').op('pop')
        record('ready')
        if mode == 'after':
            a.push(0).var('filters').push('changeState').op('callmethod').op('pop')
            record('repeat')
            for quest in (273, 274):
                a.push('response'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
                a.var('response').push('param')
                a.push('type', quest, 'status', 1, 'name', 0, 'q_type', 0, 4).op('initobject').op('setmember')
                a.var('response').push(1).var('ins').push('questStatus').op('callmethod').op('pop')
            record('complete')
            a.var('r').push('after_locked').var('ins').member('lockUpdate').op('setmember')
    for key in ('callStack', 'callCount', 'sInstance'):
        a.var('cls').push(key).var('old' + key).op('setmember')
    a.var('master').push('_currentState').var('oldState').op('setmember')
    a.var('filters').push('currentFilter').var('oldFilter').op('setmember')
    a.label('send')
    a.push('POST').var('r').push(url); w.call_method(a, 'r', 'sendAndLoad', 3)
    return a


def main():
    if not host.PLAYER or os.name != 'nt':
        print('SKIP: set LAVA_FLASH_PLAYER and LAVA_RES on Windows')
        return
    if os.environ.get('LAVA_CLIENT_MAIN'):
        host.SRC = Path(os.environ['LAVA_CLIENT_MAIN'])
    host.probe, host.resize = probe, lambda *args: None
    host.RESIZE_AT, host.LAST = 999, 7
    rows = host.run(True)
    result = next((r for r in rows if r.get('tick') == '4'), {})
    def values(mode, phase):
        return tuple(result.get(mode + '_' + phase + '_' + key) for key in ('inflight', 'queued', 'sent'))
    check('original queue wedges after CW-filtered read', values('before', 'blocked'), ('1', '1', '0'))
    check('original queue stays wedged after returning to LOCAL', values('before', 'ready'), ('1', '1', '0'))
    check('patched queue retains both filtered requests', values('after', 'blocked'), ('0', '2', '0'))
    check('LOCAL filter resumes exactly one request', values('after', 'ready'), ('1', '1', '1'))
    check('another filter update does not duplicate the inflight read', values('after', 'repeat'), ('1', '1', '1'))
    check('real q_status handlers drain the queue and unlock updates',
          (values('after', 'complete'), result.get('after_locked')), (('0', '0', '2'), 'false'))
    if fails:
        print(result)
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
