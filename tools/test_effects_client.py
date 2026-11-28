"""Late buff metadata/time must reach the current scene after travelling."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Arr, Function
from effects_client import patches
from testkit import run_cases
import widescreen as w


class EffectScene(unittest.TestCase):
    def setUp(self):
        self.cache = {}
        self.env = dict(lol=dict(core=dict(effects=dict(EffectsFactory=dict(fxStore=self.cache)))))
        _, _, _, params, body = patches(w.Asm, w.UNDEF)['wraps'][0]
        self.wrapper = Function(params, body.assemble(), self.env)

    def manager(self, own=True, mob=0):
        manager = dict(isGamer=own, mobID=mob, live={}, calls=0)
        def native(frame):
            manager['calls'] += 1
            if frame['param']['mobi_id'] != mob:
                return
            for kind in frame['param']['effects']:
                proto = self.cache.setdefault(kind, dict(_em=manager))
                manager['live'][kind] = dict(proto)
        def update(proto):
            manager['live'][proto['type']] = dict(proto)
        manager.update(__effectSceneListOrig=native, onEffectUpdate=update)
        return manager

    def list(self, manager, kinds, mob=0):
        self.wrapper.invoke(manager, [dict(param=dict(mobi_id=mob, effects=Arr(kinds)))])

    def test_late_static_and_dynamic_data_update_the_current_effect(self):
        old, current = self.manager(), self.manager()
        self.cache[93897] = dict(_em=old, type=93897)
        self.list(current, [93897])
        proto = self.cache[93897]
        self.assertIs(proto['_em'], current)
        proto.update(work_time=7200000, time=1200, register_time=5000, max_od=20)
        proto['_em']['onEffectUpdate'](proto)
        self.assertEqual(current['live'][93897]['work_time'] - current['live'][93897]['time'], 7198800)
        self.assertEqual(current['live'][93897]['max_od'], 20)
        self.assertFalse(old['live'])

    def test_repeated_transitions_rebind_all_cached_buffs_once(self):
        old = self.manager()
        for kind in (93897, 93470, 94919, 93114):
            self.cache[kind] = dict(type=kind, _em=old, work_time=1800000)
        for _ in range(3):
            current = self.manager()
            self.list(current, list(self.cache))
            self.assertEqual(current['calls'], 1)
            self.assertTrue(all(proto['_em'] is current for proto in self.cache.values()))

    def test_fresh_and_empty_lists_keep_native_construction(self):
        current = self.manager()
        self.list(current, [93897])
        self.assertIs(self.cache[93897]['_em'], current)
        self.list(current, [])
        self.assertEqual(current['calls'], 2)

    def test_foreign_frames_and_other_players_do_not_steal_the_cache(self):
        current = self.manager()
        self.cache[93897] = dict(type=93897, _em=current)
        for manager, mob in ((self.manager(mob=0), 7), (self.manager(own=False, mob=7), 7)):
            self.list(manager, [93897], mob)
            self.assertIs(self.cache[93897]['_em'], current)
            self.assertEqual(manager['calls'], 1)

    def test_wrapper_is_in_the_shipped_injection(self):
        self.assertIn(b'__effectSceneListOrig', w.injected())


if __name__ == '__main__':
    run_cases(EffectScene)
