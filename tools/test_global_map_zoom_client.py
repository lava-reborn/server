"""Execute extra map zoom bytecode against native full/overview transitions."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Function
from global_map_zoom_client import patches
from testkit import run_cases
import widescreen as w


class MapClip(dict):
    """The native DisplayGlobalMap.mapScale getter reads its landscape."""
    def get(self, key, default=None):
        if key == 'mapScale':
            return self['landscape']['mapScale']
        return super().get(key, default)


class GlobalMapZoom(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.settings, self.saves = {}, []
        shared = {}
        settings = dict(GLOBAL_SCALE='globalScale',getSetting=self.get_setting,setSetting=self.save_setting)
        env = dict(_global=shared,lol=dict(gpui=dict(UserSettings=settings)))
        feature = patches(w.Asm,w.UNDEF)
        for name, args, body in feature['globals']:
            shared[name] = Function(args,body.assemble(),env)
        self.functions = {(path[-1], method): Function(args, body.assemble(), env)
            for path, method, _keep, args, body in feature['wraps']}
        self.new_scene()

    def get_setting(self, key):
        return self.settings.get(key,'up')

    def save_setting(self, key, value):
        self.settings[key] = value
        self.saves.append((key,value))

    def new_scene(self):
        self.land = dict(mapScaleType='full',mapScale=8,cellSize=256,locationSize=8)
        self.land['__gzLandscapeScaleOrig'] = self.native_scale
        self.land['setScale'] = lambda kind: self.call('DisplayLandscape','setScale',self.land,kind)
        self.border = dict(_visible=False,_xscale=100,_yscale=100,
                           name_txt=dict(_x=17.85,_y=0.4,_xscale=100,_yscale=100))
        self.display = MapClip(landscape=self.land,curScaleType='full',locBorder=self.border,
            __gzRedrawOrig=self.redraw,setScale=self.set_scale,
            __gzScaleUpOrig=lambda:self.set_scale('full'),__gzScaleDownOrig=lambda:self.set_scale('small'))
        self.display['redrawMap'] = lambda:self.call('DisplayGlobalMap','redrawMap',self.display)
        self.display['scaleUp'] = self.up
        self.display['scaleDown'] = self.down
        self.ui = dict(displayMap=self.display,locBorder_mc=self.border,__gzLocBorderOrig=self.draw_border,
                       __gzUiInitOrig=self.native_init)

    def native_init(self):
        # Original GlobalMapInterface.init: native DisplayLandscape starts
        # in overview; only the historical up/down preferences are recognised.
        self.land.update(mapScaleType='small',mapScale=1,cellSize=32)
        saved=self.get_setting('globalScale')
        if saved=='up':
            self.up()
        elif saved=='down':
            self.down()
        return 'initialised'

    def draw_border(self, name, x, y):
        self.border.update(_x=x,_y=y,_visible=True)
        self.border['name_txt']['htmlText']=name
        return 'border-drawn'

    def hover(self, x=5997, y=1679, name='<i>Location</i>'):
        scale=self.land['mapScale']
        return self.call('GlobalMapInterface','drawLocBorder',self.ui,name,x*scale,y*scale)

    def ui_up(self):
        return self.call('GlobalMapInterface','scaleUp',self.ui)

    def ui_down(self):
        return self.call('GlobalMapInterface','scaleDown',self.ui)

    def enter_map(self):
        self.new_scene()
        return self.call('GlobalMapInterface','init',self.ui)

    def call(self, cls, method, target, *args):
        return self.functions[cls,method].invoke(target,args)

    def native_scale(self, kind):
        # DisplayLandscape.setScale from the original AS2: the tile folder,
        # scale and tile width change; locationSize remains a separate field.
        self.events.append(('native',kind))
        self.land['mapScaleType'] = kind
        if kind == 'full':
            self.land.update(mapScale=8,cellSize=256)
        elif kind == 'small':
            self.land.update(mapScale=1,cellSize=256)
        return 'native-result'

    def set_scale(self, kind):
        self.land['setScale'](kind)
        return self.display['redrawMap']()

    def redraw(self):
        # Native centerCharAfterBuild checks folder equality, not mapScale.
        if self.display.get('curScaleType') != self.land['mapScaleType']:
            self.events.append(('center',self.land['mapScale']))
            self.display['curScaleType'] = self.land['mapScaleType']
        self.events.append(('draw',self.land['mapScale']))
        return 'redrawn'

    def up(self):
        return self.call('DisplayGlobalMap','scaleUp',self.display)

    def down(self):
        return self.call('DisplayGlobalMap','scaleDown',self.display)

    def test_plus_enlarges_full_map_grid_and_tiles_by_fifty_percent(self):
        self.assertEqual(self.up(),'redrawn')
        self.assertEqual({k:self.land[k] for k in ('mapScale','cellSize','locationSize','mapScaleType')},
            dict(mapScale=12,cellSize=384,locationSize=12,mapScaleType='full'))
        self.assertEqual(self.events,[('native','full'),('center',12),('draw',12)])

    def test_plus_keeps_overview_to_full_transition_before_extra_zoom(self):
        self.set_scale('small');self.events.clear()
        self.up()
        self.assertEqual((self.land['mapScale'],self.land['cellSize'],self.land['locationSize']),(8,256,8))
        self.up()
        self.assertEqual(self.land['mapScale'],12)

    def test_minus_returns_to_full_then_overview_and_restores_grid(self):
        self.up();self.events.clear()
        self.down()
        self.assertEqual((self.land['mapScale'],self.land['cellSize'],self.land['locationSize']),(8,256,8))
        self.assertEqual(self.events,[('native','full'),('center',8),('draw',8)])
        self.down()
        self.assertEqual((self.land['mapScaleType'],self.land['mapScale'],self.land['locationSize']),('small',1,8))

    def test_repeated_plus_at_ceiling_does_not_reload_tiles_or_compound_scale(self):
        self.up();self.events.clear()
        for _ in range(200):
            self.up()
        self.assertEqual(self.land['mapScale'],12)
        self.assertEqual(self.events,[])

    def test_direct_native_scale_reset_preserves_result_and_removes_enlarged_grid(self):
        for kind in ('full','small'):
            self.up()
            result=self.call('DisplayLandscape','setScale',self.land,kind)
            self.assertEqual(result,'native-result')
            self.assertEqual(self.land['locationSize'],8)
            self.assertEqual(self.land['cellSize'],256)

    def test_zoom_cycles_keep_tile_indices_and_point_selection_in_world_coordinates(self):
        points=((5997.25,1679.75),(5858.5,1834.5),(6305.125,2110.375))
        for _ in range(30):
            for action in (self.up,self.down):
                action()
                scale,tile=self.land['mapScale'],self.land['cellSize']
                self.assertEqual(self.land['mapScaleType'],'full')
                self.assertEqual(tile/scale,32)
                for x,y in points:
                    # Same native pixel/cell conversions used by tile lookup,
                    # playerMove and mouse coordinates, with the emitted state.
                    self.assertEqual((math.floor(scale*x/tile),math.floor(scale*y/tile)),
                                     (math.floor(x/32),math.floor(y/32)))
                    self.assertAlmostEqual((x*scale)/scale,x)
                    self.assertAlmostEqual((y*scale)/scale,y)

    def test_missing_landscape_uses_native_handlers_without_inventing_state(self):
        events=[]
        display=dict(__gzScaleUpOrig=lambda:events.append('up'),
                     __gzScaleDownOrig=lambda:events.append('down'))
        self.call('DisplayGlobalMap','scaleUp',display)
        self.call('DisplayGlobalMap','scaleDown',display)
        self.assertEqual(events,['up','down'])
        self.assertNotIn('curScaleType',display)


    def test_hover_square_follows_zoom_without_enlarging_text(self):
        for action, factor in ((lambda:None,1),(self.up,1.5),(self.down,1),(self.down,1)):
            action()
            self.assertEqual(self.hover(),'border-drawn')
            title=self.border['name_txt']
            self.assertEqual(self.border['_xscale'],100*factor)
            self.assertEqual(self.border['_yscale'],100*factor)
            self.assertAlmostEqual(title['_xscale']*factor,100)
            self.assertAlmostEqual(title['_yscale']*factor,100)
            # Same native gap between the cell's right edge and its title.
            self.assertAlmostEqual(title['_x']*factor-8*factor,17.85-8)
            self.assertAlmostEqual(title['_y']*factor,0.4)
            scale=self.land['mapScale']
            self.assertEqual((self.border['_x'],self.border['_y']),(5997*scale,1679*scale))
            self.assertEqual(title['htmlText'],'<i>Location</i>')

    def test_many_zoom_cycles_do_not_compound_border_or_text_sizes(self):
        for _ in range(50):
            self.up();self.hover()
            self.down();self.hover()
        self.assertEqual(self.border['_xscale'],100)
        self.assertEqual(self.border['name_txt']['_xscale'],100)
        self.assertAlmostEqual(self.border['name_txt']['_x'],17.85)
        self.assertAlmostEqual(self.border['name_txt']['_y'],0.4)

    def test_zoom_hides_stale_hover_until_mouse_reselects_new_cell(self):
        self.display['redrawMap']()
        self.hover()
        self.display['redrawMap']()
        self.assertTrue(self.border['_visible'])
        self.up()
        self.assertFalse(self.border['_visible'])
        self.hover(x=6000,y=1680)
        self.assertTrue(self.border['_visible'])
        self.assertEqual((self.border['_x'],self.border['_y']),(72000,20160))
        self.down()
        self.assertFalse(self.border['_visible'])

    def test_zoom_redraw_before_border_creation_remains_safe(self):
        self.display.pop('locBorder')
        self.up()
        self.assertEqual(self.land['mapScale'],12)
        self.assertEqual(self.events[-1],('draw',12))

    def test_ui_buttons_save_all_three_steps_and_full_return_is_not_saved_as_overview(self):
        self.set_scale('small')
        for action, scale, saved in ((self.ui_up,8,'up'),(self.ui_up,12,'zoom'),
                                     (self.ui_down,8,'up'),(self.ui_down,1,'down')):
            action()
            self.assertEqual(self.land['mapScale'],scale)
            self.assertEqual(self.settings['globalScale'],saved)
        self.assertEqual(self.saves,[('globalScale',v) for v in ('up','zoom','up','down')])

    def test_selected_zoom_survives_repeated_location_round_trips(self):
        self.ui_up()
        self.assertEqual(self.settings['globalScale'],'zoom')
        saves=list(self.saves)
        for _ in range(10):
            self.events.clear()
            self.assertEqual(self.enter_map(),'initialised')
            self.assertEqual((self.land['mapScale'],self.land['cellSize'],self.land['locationSize']),(12,384,12))
            self.assertEqual(self.events,[('native','full'),('native','full'),('center',12),('draw',12)])
            self.assertEqual(self.saves,saves)

    def test_reopening_ordinary_full_map_does_not_silently_zoom_in(self):
        self.ui_up();self.ui_down()
        self.assertEqual(self.settings['globalScale'],'up')
        self.enter_map()
        self.assertEqual(self.land['mapScale'],8)
        self.assertEqual(self.land['locationSize'],8)

    def test_overview_and_legacy_preferences_restore_without_rewriting_storage(self):
        for value,scale in (('up',8),('down',1)):
            self.settings['globalScale']=value
            self.events.clear()
            self.enter_map()
            self.assertEqual(self.land['mapScale'],scale)
        self.assertEqual(self.saves,[])

    def test_preference_uses_native_storage_across_fresh_scene_and_helper_objects(self):
        self.ui_up()
        stored=dict(self.settings)
        self.setUp()
        self.settings.update(stored)
        self.enter_map()
        self.assertEqual(self.land['mapScale'],12)
        self.assertEqual(self.saves,[])

    def test_mark_click_targets_same_world_cell_centre_in_every_scale(self):
        calls=[]
        mark={}
        self.display['markManager']=dict(getMarkNum=lambda obj:0,markList=[mark])
        self.display['playerMoveToCoords']=lambda x,y:calls.append((x/self.land['mapScale'],y/self.land['mapScale']))
        for kind,scale in (('small',1),('full',8),('zoom',12)):
            if kind=='zoom':self.up()
            else:self.set_scale(kind)
            for x,y in ((5997,1679),(0,0)):
                mark.update(_x=x*scale,_y=y*scale)
                self.call('GlobalMapInterface','_moveToLabel',self.ui,dict(target=dict(markObj={})))
                self.assertEqual(calls[-1],(x+0.5,y+0.5))

    def test_missing_mark_does_not_send_an_invalid_move(self):
        self.display['markManager']=dict(getMarkNum=lambda obj:None,markList={})
        self.display['playerMoveToCoords']=lambda *_:self.fail('unexpected move')
        self.call('GlobalMapInterface','_moveToLabel',self.ui,dict(target=dict(markObj={})))


if __name__ == '__main__':
    run_cases(GlobalMapZoom)
