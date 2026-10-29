"""Opt-in real Flash Sound.getVolume regression, with silent probe clips.

Runs original and patched effect playback against the same 25/10/0/100
settings. It measures the real Flash channel, not perceived speaker volume.
Uses the same isolated-server host as test_hotkey_windows.py.
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
    a.push('m', 0).var('lol').member('core', 'Master').push('getInstance').op('callmethod').op('definelocal')
    a.push('r'); w.new(a, ['_global'], 'LoadVars', 0).op('definelocal')
    a.var('r').push('tick').var('_root').member('tick').op('setmember')
    a.var('_root').member('tick').push(12).op('equals2').op('not').iftrue('send')
    a.push('settings').var('lol').member('gpui', 'UserSettings', 'settingsArray').op('definelocal')
    a.push('oldVolume', 'gameSoundVolume', 1).var('lol').member('gpui', 'UserSettings').push('getSetting').op('callmethod').op('definelocal')
    a.push('effect', 'volumeProbe'); w.new(a, ['lol', 'sound'], 'SoundTLContainer', 1).op('definelocal')
    a.var('effect').push('cont')
    a.push(0).var('_root').push('getNextHighestDepth').op('callmethod')
    a.push('__volumeProbe', 2).var('_root').push('createEmptyMovieClip').op('callmethod').op('setmember')
    for volume in (25, 10, 0, 100):
        # Avoid persisting test preferences in SharedObject.
        a.var('settings').push('gameSoundVolume', volume).op('setmember')
        if volume in (25, 10):
            a.push(0).var('effect').push('playSound').op('callmethod').op('pop')
        else:
            a.push(0, '__applyGameVolume').op('callfunc').op('pop')
        a.var('r').push('volume%d' % volume).push(0).var('effect').member('_sound').push('getVolume').op('callmethod').op('setmember')
    a.var('settings').push('gameSoundVolume').var('oldVolume').op('setmember')
    # Replay the original music handlers on a silent, empty clip. No music
    # file is loaded, so even the unpatched control cannot be audible.
    a.push('oldMusic', 'musicVolume', 1).var('lol').member('gpui', 'UserSettings').push('getSetting').op('callmethod').op('definelocal')
    a.var('settings').push('musicVolume', 50).op('setmember')
    a.push('track', 'Signals'); w.new(a, ['lol', 'sound'], 'SoundTrackContainer', 1).op('definelocal')
    a.var('track').push('cont')
    a.push(0).var('_root').push('getNextHighestDepth').op('callmethod')
    a.push('__silentTrackProbe', 2).var('_root').push('createEmptyMovieClip').op('callmethod').op('setmember')
    a.var('_root').push('__silentTrack').var('track').op('setmember')
    a.push('manager'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
    a.var('manager').push('__wantedTrack', 'Underground').op('setmember')
    a.var('manager').push('currentTrackName', 'Underground').op('setmember')
    a.var('manager').push('stopCurrentTrack').function((), w.Asm()).op('setmember')
    a.push('proto').var('lol').member('sound', 'SoundManager', 'prototype').op('definelocal')
    for name in ('trackLoaded', '__trackLoadedOrig', 'musicVolume', '__musicVolumeOrig'):
        a.var('manager').push(name).var('proto').member(name).op('setmember')
    a.push('target').var('track').push(1).op('initobject').push(1)
    a.var('manager').push('trackLoaded').op('callmethod').op('pop')
    a.var('r').push('late_track').var('manager').member('currentTrackName').op('setmember')
    a.push(0).var('track').push('playSound').op('callmethod').op('pop')
    a.push('fx', 1000, 50, 0, None); w.new(a, ['lol', 'fx'], 'FadeSound', 4).op('definelocal')
    a.var('fx').push(1).var('track').push('setFX').op('callmethod').op('pop')
    a.push('lib'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
    get_sound = w.Asm(); get_sound.var('_root').member('__silentTrack').op('return')
    a.var('lib').push('getSound').function(('name',), get_sound).op('setmember')
    a.var('manager').push('trackLib').var('lib').op('setmember')
    a.var('manager').push('__wantedTrack', 'Signals').op('setmember')
    a.var('manager').push('currentTrackName', 'Signals').op('setmember')
    a.var('manager').push('muteFlag', True).op('setmember')
    a.push(10, 1).var('manager').push('musicVolume').op('callmethod').op('pop')
    a.var('settings').push('musicVolume').var('oldMusic').op('setmember')
    a.label('send')
    a.var('_root').member('tick').push(14).op('equals2').op('not').iftrue('not_fade')
    a.var('r').push('after_fade').push(0).var('_root').member('__silentTrack', '_sound').push('getVolume').op('callmethod').op('setmember')
    a.label('not_fade')
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
    if os.environ.get('LAVA_CLIENT_MAIN'):
        host.SRC = Path(os.environ['LAVA_CLIENT_MAIN'])
    host.probe, host.resize = probe, lambda *args: None
    host.RESIZE_AT, host.LAST = 999, 16
    originals = {name: getattr(w, name) for name in ('fn_event_sound_play', 'fn_track_loaded', 'fn_music_volume')}
    def passthrough(original, parameter=None):
        a = w.Asm()
        if parameter:
            a.var(parameter)
        a.push(1 if parameter else 0).var('this').push(original).op('callmethod').op('pop')
        return a
    try:
        w.fn_event_sound_play = lambda: passthrough('__eventPlayOrig')
        w.fn_track_loaded = lambda: passthrough('__trackLoadedOrig', 'obj')
        w.fn_music_volume = lambda: passthrough('__musicVolumeOrig', 'vol')
        before_rows = host.run(True)
    finally:
        for name, original in originals.items():
            setattr(w, name, original)
    after_rows = host.run(True)
    before = next((r for r in before_rows if r.get('tick') == '12'), {})
    after = next((r for r in after_rows if r.get('tick') == '12'), {})
    check('original playback ignores numeric effects volume',
          [before.get('volume%d' % n) for n in (25, 10)], ['100', '100'])
    check('real Flash effects channel follows slider, mute and restore',
          [after.get('volume%d' % n) for n in (25, 10, 0, 100)], ['25', '10', '0', '100'])
    check('original music handler accepts an obsolete Signals completion', before.get('late_track'), 'Signals')
    check('patched music handler rejects an obsolete Signals completion', after.get('late_track'), 'Underground')
    check('original fade overrides a newer volume adjustment',
          next((r.get('after_fade') for r in before_rows if r.get('tick') == '14'), None), '50')
    check('patched fade cannot restore the previous loudness',
          next((r.get('after_fade') for r in after_rows if r.get('tick') == '14'), None), '10')
    if fails:
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
