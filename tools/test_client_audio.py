"""Execute emitted client audio fixes; no speakers, network or game DB."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server'))
import widescreen as w
from avm_test import Arr, execute
from testkit import run_cases


class ClientAudio(unittest.TestCase):
    def test_late_music_load_cannot_replace_newer_scene(self):
        for order in (('Signals', 'Underground'), ('Underground', 'Signals')):
            requests, played = [], []
            manager = NS()
            setattr(manager, '__trackRequestOrig', requests.append)
            setattr(manager, '__trackLoadedOrig', lambda obj: played.append(obj.target.name))
            for name in ('Signals', 'Underground'):
                execute(w.fn_track_request().assemble(), dict(this=manager, name=name))
            for name in order:
                execute(w.fn_track_loaded().assemble(), dict(this=manager, obj=NS(target=NS(name=name))))
            self.assertEqual(requests, ['Signals', 'Underground'])
            self.assertEqual(played, ['Underground'])

    def test_cached_music_completion_sees_request_already_recorded(self):
        played = []
        manager = NS()
        setattr(manager, '__trackLoadedOrig', lambda obj: played.append(obj.target.name))
        setattr(manager, '__trackRequestOrig', lambda name: execute(
            w.fn_track_loaded().assemble(), dict(this=manager, obj=NS(target=NS(name=name)))))
        execute(w.fn_track_request().assemble(), dict(this=manager, name='Underground'))
        self.assertEqual(played, ['Underground'])

    def test_music_slider_cancels_old_fade_and_mute_stops_channel(self):
        for volume in (0, 1, 10, 25, 100):
            events = []
            track = NS(sfx=NS(kill=lambda: events.append('kill fade')),
                       setVolume=lambda n: events.append(('volume', n)),
                       stop=lambda: events.append('stop'))
            manager = NS(currentTrackName='Underground', muteFlag=True,
                         trackLib=NS(getSound=lambda name: track))
            setattr(manager, '__wantedTrack', 'Underground')
            setattr(manager, '__musicVolumeOrig', lambda n: events.append(('original', n)))
            execute(w.fn_music_volume().assemble(), dict(this=manager, vol=volume))
            self.assertEqual(events, [('original', volume), 'kill fade', ('volume', volume)]
                             + (['stop'] if volume == 0 else []))

    def test_unmute_in_new_scene_does_not_restart_previous_music(self):
        events = []
        track = NS(sfx=NS(kill=lambda: None), setVolume=lambda n: None)
        manager = NS(currentTrackName='Signals', muteFlag=False,
                     trackLib=NS(getSound=lambda name: track), playSoundTrack=events.append)
        setattr(manager, '__wantedTrack', 'Underground')
        setattr(manager, '__musicVolumeOrig', lambda n: events.append('wrong original restart'))
        execute(w.fn_music_volume().assemble(), dict(this=manager, vol=25))
        self.assertEqual(events, ['Underground'])
        self.assertTrue(manager.muteFlag)

    def env(self, volume):
        settings = {'gameSoundVolume': volume}
        return settings, dict(lol=NS(gpui=NS(UserSettings=NS(getSetting=settings.get))),
                             _global=NS())

    def test_effect_uses_numeric_volume_and_registers_once(self):
        for volume in (0, 1, 10, 25, 50, 100):
            settings, env = self.env(volume)
            volumes, plays = [], []
            sound = NS(setVolume=volumes.append)
            container = NS(_sound=sound)
            setattr(container, '__eventPlayOrig', lambda: plays.append('original'))
            for _ in range(3):
                execute(w.fn_event_sound_play().assemble(), dict(env, this=container))
            self.assertEqual(volumes, [volume] * 3)
            self.assertEqual(plays, ['original'] * 3)
            self.assertEqual(getattr(env['_global'], '__gameVolumeSounds'), [container])

    def test_first_muted_effect_does_not_create_a_sound_or_registry(self):
        _, env = self.env(0)
        container = NS(_sound=None)
        setattr(container, '__eventPlayOrig', lambda: None)
        execute(w.fn_event_sound_play().assemble(), dict(env, this=container))
        self.assertFalse(hasattr(env['_global'], '__gameVolumeSounds'))

    def test_slider_mutes_and_restores_all_cached_channels(self):
        settings, env = self.env(25)
        channels = [[], [], []]
        setattr(env['_global'], '__gameVolumeSounds', Arr(NS(_sound=NS(setVolume=c.append)) for c in channels))
        for volume in (25, 0, 10, 100):
            settings['gameSoundVolume'] = volume
            execute(w.fn_apply_game_volume().assemble(), env)
        self.assertEqual(channels, [[25, 0, 10, 100]] * 3)

    def test_game_slider_updates_existing_channels_after_saving(self):
        for kind in ('game', 'interface'):
            events = []
            ui = NS()
            setattr(ui, '__gameSliderOrig', lambda obj: events.append(('save', obj.target.data)))
            execute(w.fn_game_volume_slider().assemble(), dict(
                this=ui, obj=NS(target=NS(data=kind)),
                __applyGameVolume=lambda: events.append(('apply', kind))))
            self.assertEqual(events, [('save', kind)] + ([('apply', kind)] if kind == 'game' else []))

    def test_game_mute_button_applies_current_setting(self):
        events = []
        ui = NS()
        setattr(ui, '__soundVolumeOrig', lambda scroll, value: events.append(('save', scroll.data, value)))
        execute(w.fn_sound_volume_setting().assemble(), dict(
            this=ui, scroll=NS(data='game'), value=0,
            __applyGameVolume=lambda: events.append(('apply',))))
        self.assertEqual(events, [('save', 'game', 0), ('apply',)])


if __name__ == '__main__':
    run_cases(ClientAudio)
