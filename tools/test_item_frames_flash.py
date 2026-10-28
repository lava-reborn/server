"""Replay late static item data through real Flash item-container methods.

The isolated host disables music/effects. No user settings are persisted.
"""
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
    a.var('_root').member('tick').push(5).op('equals2').op('not').iftrue('send')
    noop = w.Asm()
    get_prop = w.Asm(); get_prop.var('this').var('name').op('getmember').op('return')
    paint = w.Asm(); paint.var('_root').push('__frameProbeStyle').var('symbol').op('setmember')
    paint.var('depth').var('name').var('symbol').push(3).var('this').push('__nativeAttach').op('callmethod').op('return')
    for cls in ('ItemContainer', 'ExtItemContainer', 'ListItemContainer', 'ExtListItemContainer'):
        a.push('item'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
        for field, value in (('rootID', 0), ('g_cost', 0), ('cost', 0),
                             ('premium', 0), ('quest', 0), ('name', 'Probe')):
            a.var('item').push(field, value).op('setmember')
        a.var('item').push('getProp').function(('name',), get_prop).op('setmember')
        a.push('panel'); a.push(0).var('_root').push('getNextHighestDepth').op('callmethod')
        a.push('__frameProbe' + cls, 2).var('_root').push('createEmptyMovieClip').op('callmethod').op('definelocal')
        a.push('bg', 0, 'bg_mc', 2).var('panel').push('createEmptyMovieClip').op('callmethod').op('definelocal')
        a.var('bg').push('__nativeAttach').var('bg').member('attachMovie').op('setmember')
        a.var('bg').push('attachMovie').function(('symbol', 'name', 'depth'), paint).op('setmember')
        a.var('panel').push('item').var('item').op('setmember')
        a.var('panel').push('__item').var('item').op('setmember')
        getter = w.Asm(); getter.var('this').member('__item').op('return')
        a.var('panel').push('__get__item').function((), getter).op('setmember')
        a.var('panel').push('__set__toggled_frame').var('lol').member('gpui', 'ItemContainer', 'prototype', '__set__toggled_frame').op('setmember')
        a.var('panel').push('bg_mc').var('bg').op('setmember')
        a.var('panel').push('attachBackEnabled', True).op('setmember')
        a.push('text'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
        a.var('text').push('setTextFormat').function(('format',), noop).op('setmember')
        for field in ('name_txt', 'modeType_txt'):
            a.var('panel').push(field).var('text').op('setmember')
        for method in ('doLater', 'attachAmmoMode'):
            a.var('panel').push(method).function(('arg',), noop).op('setmember')
        a.var('panel').push('attachBack').var('lol').member('gpui', cls, 'prototype', 'attachBack').op('setmember')
        for method in ('itemUpdate', '__itemFrameUpdateOrig'):
            a.var('panel').push(method).var('lol').member('gpui', 'ItemContainer', 'prototype', method).op('setmember')
        a.push(0, 1).var('panel').push('attachBack').op('callmethod').op('pop')
        if cls.startswith('Ext'):
            for method in ('attachBtn', '__itemInfoAttachOrig'):
                a.var('panel').push(method).var('lol').member('gpui', 'ExtItemContainer', 'prototype', method).op('setmember')
            a.var('panel').push('btnLinkID', 'list_info_btn' if 'List' in cls else 'info_btn').op('setmember')
            click = w.Asm(); click.var('this').push('clicks').var('this').member('clicks').push(1).op('add2').op('setmember')
            a.var('panel').push('clicks', 0).op('setmember')
            a.var('panel').push('onPressBtn').function((), click).op('setmember')
            a.push(0).var('panel').push('attachBtn').op('callmethod').op('pop')
        # Actual background MovieClip is hovered before static info arrives.
        a.push(True, 1).var('panel').push('__set__toggled_frame').op('callmethod').op('pop')
        a.var('item').push('g_cost', 2500).op('setmember')
        a.push(None, 1).var('panel').push('__itemFrameUpdateOrig').op('callmethod').op('pop')
        a.var('r').push(cls + '_before').var('_root').member('__frameProbeStyle').op('setmember')
        a.push(None, 1).var('panel').push('itemUpdate').op('callmethod').op('pop')
        a.var('r').push(cls + '_after').var('_root').member('__frameProbeStyle').op('setmember')
        a.var('r').push(cls + '_hover').var('panel').member('bg_mc', 'bg', '_currentframe').op('setmember')
        if cls.startswith('Ext'):
            a.var('r').push(cls + '_button').var('panel').member('info_btn', '_name').op('setmember')
            a.var('r').push(cls + '_button_hover').var('panel').member('info_btn', '_currentframe').op('setmember')
            a.push(0).var('panel').member('info_btn').push('onRelease').op('callmethod').op('pop')
            a.var('r').push(cls + '_clicks').var('panel').member('clicks').op('setmember')
            # Repeating the constructor's deferred call must not duplicate suffixes.
            a.push(0).var('panel').push('attachBtn').op('callmethod').op('pop')
            a.var('r').push(cls + '_repeat_button').var('panel').member('info_btn', '_name').op('setmember')
            a.var('item').push('premium', 1).op('setmember')
            a.var('panel').push('toggled', True).op('setmember')
            a.push(None, 1).var('panel').push('itemUpdate').op('callmethod').op('pop')
            a.var('r').push(cls + '_premium_button').var('panel').member('info_btn', '_name').op('setmember')
            a.var('r').push(cls + '_selected').var('panel').member('bg_mc', 'bg', '_currentframe').op('setmember')
            a.var('r').push(cls + '_old_gold_removed').var('panel').member('list_info_btn_gold' if 'List' in cls else 'info_btn_gold', '_name').push(w.UNDEF).op('equals2').op('setmember')
            a.var('item').push('premium', 0).op('setmember')
            a.push(None, 1).var('panel').push('itemUpdate').op('callmethod').op('pop')
        a.var('r').push(cls + '_style').var('panel').member('__itemFrameStyle').op('setmember')
        a.push(0, 1).var('panel').push('attachBack').op('callmethod').op('pop')
        a.var('r').push(cls + '_direct').var('_root').member('__frameProbeStyle').op('setmember')
        a.var('r').push(cls + '_price').var('item').member('g_cost').op('setmember')
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
    host.RESIZE_AT, host.LAST = 999, 8
    rows = host.run(True)
    result = next((r for r in rows if r.get('tick') == '5'), {})
    for cls in ('ItemContainer', 'ExtItemContainer', 'ListItemContainer', 'ExtListItemContainer'):
        base = 'list_fireArmBG' if 'List' in cls else 'fireArmBG'
        check(cls + ': original late update leaves an ordinary background',
              result.get(cls + '_before'), base)
        check(cls + ': patched late update paints gold background',
              result.get(cls + '_after'), base + '_gold')
        check(cls + ': the price is unchanged', result.get(cls + '_price'), '2500')
        check(cls + ': hovered background stays highlighted', result.get(cls + '_hover'), '2')
        if cls.startswith('Ext'):
            button = 'list_info_btn' if 'List' in cls else 'info_btn'
            check(cls + ': info button becomes gold and stays highlighted',
                  (result.get(cls + '_button'), result.get(cls + '_button_hover')), (button + '_gold', '2'))
            check(cls + ': info click still reaches its original delegated handler', result.get(cls + '_clicks'), '1')
            check(cls + ': repeated attach keeps a single style suffix', result.get(cls + '_repeat_button'), button + '_gold')
            check(cls + ': premium keeps selection and removes the former gold button',
                  (result.get(cls + '_premium_button'), result.get(cls + '_selected'), result.get(cls + '_old_gold_removed')),
                  (button + '_premium', '2', 'true'))
    if fails:
        print(result)
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
