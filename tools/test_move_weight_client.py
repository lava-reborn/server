"""Execute emitted movement/weight AVM1 patches; no Flash, sockets or polling."""
import sys
import unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'server')]
import widescreen as w
from avm_test import Arr, execute
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
        walker['moveDirectionInc'] = lambda: None
        for i in range(20):
            clock[0] = 100 + i * 200 + (40 if i else 0)
            execute(w.fn_walk_start().assemble(), dict(this=walker))
            self.assertEqual(walker['startTime'], 100 + i * 200)
            self.assertEqual(walker['finishTime'], 200)
        self.assertEqual(walker['__walkNextAt'], 4100)

    def test_reroute_splices_current_edge_including_last_step_without_restart(self):
        for old_path in ([dict(num=3)], [dict(num=3), dict(num=4)]):
            calls = []
            walker = dict(__walkActive=True, startTime=100, numPos=2, path=old_path,
                          x=27, y=19, moveTime=75, interval=41,
                          __walkCreateOrig=lambda path: calls.append(path))
            execute(w.fn_walk_create().assemble(), dict(this=walker,
                _path=Arr([dict(num=2), dict(num=3), dict(num=8)])))
            self.assertEqual(calls, [])
            self.assertEqual([c['num'] for c in walker['path']], [3, 8])
            self.assertEqual(walker['completedPath'], [dict(num=2)])
            self.assertEqual((walker['x'], walker['y'], walker['moveTime'], walker['interval']),
                             (27, 19, 75, 41))
            self.assertEqual((walker['startTime'], walker['__walkNextAt']), (100, 300))

    def test_new_or_corrected_edge_uses_server_phase_and_clears_it(self):
        observed = []
        walker = dict(__walkActive=False, __walkElapsed=75,
                      __walkCreateOrig=lambda path: observed.append(walker['__walkNextAt']))
        env = dict(this=walker, _path=Arr([dict(num=2), dict(num=3)]), getTimer=lambda: 500)
        execute(w.fn_walk_create().assemble(), env)
        self.assertEqual(observed, [425])
        self.assertIsNone(walker['__walkElapsed'])
        execute(w.fn_walk_create().assemble(), env)
        self.assertEqual(observed, [425, None])
        for phase in (-1, 200):
            walker['__walkElapsed'] = phase
            execute(w.fn_walk_create().assemble(), env)
            self.assertIsNone(observed[-1])

    def test_late_render_tick_never_moves_beyond_the_next_hex(self):
        points = []
        walker = dict(startTime=100, finishTime=200, moveTime=0, x=0, y=0, vx=1, vy=2)
        def position(x, y):
            points.append((x, y))
            walker.update(x=x, y=y)
        walker['setPosition'] = position
        for now in (150, 400, 600):
            execute(w.fn_walk_increment().assemble(), dict(this=walker, getTimer=lambda: now))
        self.assertEqual(points, [(50, 100), (200, 400), (200, 400)])
        self.assertEqual(walker['moveTime'], 200)

    def test_refused_walk_releases_target_after_native_callback_and_allows_same_click(self):
        events = []
        walker = dict(numPos=1, finishPos=9)
        def refused(obj):
            events.append('native refusal')
            walker['numPos'] = obj['param']['pos']
        scene = dict(__walkRefuseOrig=refused, getWalker=lambda ident: walker,
                     gamer=dict(walker=walker),
                     __walkRequestOrig=lambda cell, splice: events.append(('new request', cell['num'])))
        execute(w.fn_walk_refused().assemble(), dict(this=scene, obj=dict(param=dict(id=0, pos=2))))
        self.assertEqual(events, ['native refusal'])
        self.assertEqual(walker['finishPos'], 2)
        execute(w.fn_walk_request().assemble(), dict(this=scene, cell=dict(num=9), spliceNum=None))
        self.assertEqual(events, ['native refusal', ('new request', 9)])

    def test_repeated_destination_skips_path_search_and_send_but_stop_allows_retry(self):
        calls = []
        walker = dict(finishPos=8, numPos=2)
        def native(cell, splice):
            calls.append((cell['num'], splice))
            walker['finishPos'] = cell['num']
            return 'sent'
        scene = dict(gamer=dict(walker=walker), __walkRequestOrig=native)
        env = dict(this=scene, cell=dict(num=8), spliceNum=2)
        for _ in range(10):
            execute(w.fn_walk_request().assemble(), env)
        self.assertEqual(calls, [])
        env['cell'] = dict(num=9)
        self.assertEqual(execute(w.fn_walk_request().assemble(), env), 'sent')
        self.assertEqual(calls, [(9, 2)])
        # The authoritative action stop releases the same native destination latch.
        walker['finishPos'] = walker['numPos']
        self.assertEqual(execute(w.fn_walk_request().assemble(), env), 'sent')
        self.assertEqual(calls, [(9, 2), (9, 2)])

    def test_click_plans_from_current_edge_end_with_one_path_search(self):
        cells = {n: dict(num=n) for n in (2, 3, 4, 8)}
        calls = []
        walker = dict(__walkActive=True, numPos=2, path=Arr([cells[3]]))
        def find(start, end):
            calls.append((start['num'], end['num']))
            return Arr([cells[4], cells[8]])
        location = dict(gamer=dict(walker=walker), __walkPathOrig=find)
        result = execute(w.fn_walk_path().assemble(), dict(this=location, cell0=cells[2], cell1=cells[8]))
        self.assertEqual(calls, [(3, 8)])
        self.assertEqual([c['num'] for c in result], [3, 4, 8])
        result = execute(w.fn_walk_path().assemble(), dict(this=location, cell0=cells[2], cell1=cells[3]))
        self.assertEqual(result, [cells[3]])
        self.assertEqual(calls, [(3, 8)])
        walker['__walkActive'] = False
        execute(w.fn_walk_path().assemble(), dict(this=location, cell0=cells[2], cell1=cells[8]))
        self.assertEqual(calls[-1], (2, 8))

    def test_authoritative_frame_aligns_observer_but_changes_only_owner_ap(self):
        for ident in (0, 17):
            events = []
            walker = dict(numPos=1)
            walker['breakMove'] = lambda pos: (events.append(('stop', pos)), walker.update(numPos=pos))
            ap = dict(ap=77)
            location = dict(getWalker=lambda id: walker,
                            master=dict(gamer=dict(apManager=ap)),
                            __walkFrameOrig=lambda obj: events.append(('route', walker['__walkElapsed'])))
            execute(w.fn_walk_frame().assemble(), dict(this=location,
                obj=dict(param=dict(id=ident, path=[2, 3, 8], step_ms=50, ap=98))))
            self.assertEqual(events, [('stop', 2), ('route', 50)])
            self.assertEqual(ap['ap'], 98 if ident == 0 else 77)

    def test_running_faces_edge_before_position_without_intermediate_rotation(self):
        events = []
        rotate = object()
        figure = dict(__direction=1, rotate=rotate,
                      deleteEnterFrame=lambda fn: events.append(('cancel_rotate', fn)))
        scene = dict(getWalker=lambda id: figure,
                     __runPositionOrig=lambda obj: events.append(('position', figure['__direction'])))
        execute(w.fn_run_position().assemble(), dict(this=scene, obj=dict(walker=dict(id=17, direction=5))))
        self.assertEqual(events, [('cancel_rotate', rotate), ('position', 5)])
        figure['behavior'] = 'run'
        events.clear()
        execute(w.fn_run_position().assemble(), dict(this=scene, obj=dict(walker=dict(id=17, direction=5))))
        self.assertEqual(events, [('position', 5)])

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
                     '__walkStartOrig', '__walkFinishOrig', '__aimPositionOrig',
                     '__walkPathOrig', '__walkFrameOrig', '__runPositionOrig', '__walkIncrementOrig'):
            self.assertIn(name.encode(), emitted)


if __name__ == '__main__':
    run_cases(MoveWeightClient)
