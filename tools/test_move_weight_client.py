"""Execute emitted movement/weight AVM1 patches; no Flash, sockets or polling."""
import sys
import unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'server')]
import widescreen as w
from avm_test import execute
from testkit import run_cases


class MoveWeightClient(unittest.TestCase):
    def panels(self, opened):
        self.calls = []
        panels = {name: dict(instance=dict(content=dict(weightPan=dict(
            count=lambda name=name: self.calls.append(name))))) for name in opened}
        return dict(lol=dict(core=dict(SceneShifter=dict(_ref=dict(UIPanels=panels)))))

    def test_quantity_refreshes_after_original_update_and_closed_panels_are_ignored(self):
        env = self.panels(('equip', 'trade'))
        env.update(this=dict(__weightDynamicOrig=lambda obj: self.calls.append('original')), obj=dict(param=dict(size=5000)))
        execute(w.fn_weight_item_info(True).assemble(), env)
        self.assertEqual(self.calls, ['original', 'equip', 'trade'])
        env = self.panels(())
        env.update(this=dict(__weightDynamicOrig=lambda obj: self.calls.append('original')), obj=dict(param=dict(size=0)))
        execute(w.fn_weight_item_info(True).assemble(), env)
        self.assertEqual(self.calls, ['original'])

    def test_ammo_purchase_race_and_late_unit_weight_recount_without_reopening(self):
        item = dict(size=1, weight=0)
        shown = []
        pan = dict(count=lambda: shown.append(item['size'] * item['weight']))
        panels = dict(trade=dict(instance=dict(content=dict(weightPan=pan))))
        env = dict(lol=dict(core=dict(SceneShifter=dict(_ref=dict(UIPanels=panels)))))
        obj = dict(param=dict(size=5000))
        env.update(obj=obj, this=dict(__weightDynamicOrig=lambda obj: item.update(size=obj['param']['size'])))
        execute(w.fn_weight_item_info(True).assemble(), env)
        env.update(obj=dict(param=dict(weight=8)), rootID=3,
                   this=dict(__weightStaticOrig=lambda obj, root: item.update(weight=obj['param']['weight'])))
        execute(w.fn_weight_item_info().assemble(), env)
        self.assertEqual(shown, [0, 40000])
        env.update(obj=dict(param=dict(size=2500)), this=dict(__weightDynamicOrig=lambda obj: item.update(size=obj['param']['size'])))
        execute(w.fn_weight_item_info(True).assemble(), env)
        self.assertEqual(shown[-1], 20000)

    def test_unrelated_dynamic_frames_do_not_recount_weight(self):
        env = self.panels(('trade',))
        env.update(this=dict(__weightDynamicOrig=lambda obj: self.calls.append('original')), obj=dict(param=dict(ammo_count=5, **{'break': 100})))
        execute(w.fn_weight_item_info(True).assemble(), env)
        self.assertEqual(self.calls, ['original'])

    def test_step_clock_does_not_accumulate_interval_lateness(self):
        walker = {}
        clock = [100]
        walker['__walkStartOrig'] = lambda: walker.update(startTime=clock[0], finishTime=200.00000000003)
        for i in range(20):
            clock[0] = 100 + i * 200 + (40 if i else 0)
            execute(w.fn_walk_start().assemble(), dict(this=walker))
            self.assertEqual(walker['startTime'], 100 + i * 200)
            self.assertEqual(walker['finishTime'], 200)
        self.assertEqual(walker['__walkNextAt'], 4100)

    def test_reroute_keeps_current_edge_phase_only_while_moving(self):
        observed = []
        walker = dict(__walkActive=True, startTime=100, numPos=2, path=[dict(num=3), dict(num=4)],
                      __walkCreateOrig=lambda path: observed.append(walker['__walkNextAt']))
        execute(w.fn_walk_create().assemble(), dict(this=walker, _path=[dict(num=2), dict(num=3), dict(num=8)]))
        self.assertEqual(observed, [100])
        walker['__walkFinishOrig'] = lambda: None
        execute(w.fn_walk_finish().assemble(), dict(this=walker))
        execute(w.fn_walk_create().assemble(), dict(this=walker, _path=[dict(num=2), dict(num=3)]))
        self.assertEqual(observed, [100, None])
        execute(w.fn_walk_create().assemble(), dict(this=walker, _path=[dict(num=2), dict(num=8)]))
        self.assertIsNone(observed[-1])

    def test_aim_stops_lagging_walker_before_original_bar_and_never_uses_breakmv(self):
        events = []
        walker = dict(numPos=2, path=[dict(num=3), dict(num=4)])
        def stop(pos):
            events.append(('stop', pos))
            walker.update(prevNumPos=walker['numPos'], numPos=pos)
        walker['breakMove'] = stop
        cells = {2: dict(busy=True), 4: dict(busy=False)}
        loc = dict(getWalker=lambda id: walker, getCellFromNumber=lambda pos: cells[pos],
                   __aimPositionOrig=lambda obj: events.append(('aim', walker['numPos'])))
        execute(w.fn_aim_position().assemble(), dict(this=loc, obj=dict(param=dict(id=1, pos=4))))
        self.assertEqual(events, [('stop', 4), ('aim', 4)])
        self.assertEqual(walker['finishPos'], 4)
        self.assertFalse(cells[2]['busy'])
        self.assertTrue(cells[4]['busy'])
        events.clear()
        execute(w.fn_aim_position().assemble(), dict(this=loc, obj=dict(param=dict(id=1))))
        self.assertEqual(events, [('aim', 4)])

    def test_owner_ap_restored_after_stop_without_spending_or_touching_fifo(self):
        manager = dict(ap=30)
        walker = dict(id=0, numPos=2, path=[dict(num=3), dict(num=4)])
        def stop(pos):
            if walker['id'] == 0:
                manager['ap'] -= 3  # original syncPos / finishPart prediction
            walker.update(prevNumPos=2, numPos=pos)
        walker['breakMove'] = stop
        cells = {2: {}, 4: {}}
        loc = dict(master=dict(gamer=dict(apManager=manager)), getWalker=lambda id: walker,
                   getCellFromNumber=lambda pos: cells[pos], __aimPositionOrig=lambda obj: None)
        execute(w.fn_aim_position().assemble(), dict(this=loc, obj=dict(param=dict(id=0, pos=4, ap=28))))
        self.assertEqual(manager['ap'], 28)
        walker.update(numPos=2, id=7)
        execute(w.fn_aim_position().assemble(), dict(this=loc, obj=dict(param=dict(id=7, pos=4, ap=90))))
        self.assertEqual(manager['ap'], 28)  # observer's own AP is untouched

    def test_new_hooks_are_injected_idempotently(self):
        emitted = w.injected()
        for name in ('__weightDynamicOrig', '__weightStaticOrig', '__walkCreateOrig',
                     '__walkStartOrig', '__walkFinishOrig', '__aimPositionOrig'):
            self.assertIn(name.encode(), emitted)


if __name__ == '__main__':
    run_cases(MoveWeightClient)
