"""Terrain editor drafts preserve kinds, blocked water and existing metadata."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import map_editor as editor
from testkit import run_cases


class TerrainEditor(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='map-editor-')
        self.path=Path(self.directory.name)/'terrain.json'
        self.original={'_':'existing explanation','blocked':['6000,1700'],
                       'passable':['6001,1700'],'other':{'preserve':True}}
        self.path.write_text(json.dumps(self.original),encoding='utf-8')
        self.target=patch.object(editor,'VERIFIED',str(self.path));self.target.start()
        self.seed=patch.object(editor,'EDITOR_SEED',str(Path(self.directory.name)/'seed.json'));self.seed.start()

    def tearDown(self):
        self.target.stop();self.seed.stop();self.directory.cleanup()

    def payload(self):
        doc,revision=editor.read_document()
        return dict(editor.normalise(doc),revision=revision)

    def test_standard_entry_opens_the_new_boundary_editor(self):
        import map_editor_preview
        with patch.object(editor,'render') as render,patch.object(map_editor_preview,'main') as launch, \
             patch.object(sys,'argv',['map_editor.py']):
            editor.main()
            render.assert_called_once();launch.assert_called_once()
            self.assertEqual(sys.argv[sys.argv.index('--source')+1],str(self.path))
            self.assertIn('--map-image',sys.argv);self.assertIn('--port',sys.argv)

    def test_new_install_starts_with_the_shipped_draft_without_modifying_it(self):
        import map_editor_preview
        seed=Path(editor.EDITOR_SEED);seed.write_bytes(self.path.read_bytes());before=seed.read_bytes()
        with patch.object(editor,'render'),patch.object(map_editor_preview,'main'),patch.object(sys,'argv',['map_editor.py']):
            editor.main()
            self.assertEqual(sys.argv[sys.argv.index('--source')+1],str(seed))
        self.assertEqual(seed.read_bytes(),before)

    def test_water_and_rocks_round_trip_as_distinct_blocked_terrain(self):
        data=self.payload();data.update(water=['6002,1700'],rocks=['6003,1700'],opacity=35)
        code,result=editor.save_document(data)
        self.assertEqual(code,200)
        saved,revision=editor.read_document()
        self.assertEqual(saved['blocked'],['6000,1700','6002,1700','6003,1700'])
        self.assertEqual(saved['water'],['6002,1700'])
        self.assertEqual(saved['rocks'],['6003,1700'])
        self.assertEqual(saved['passable'],['6001,1700'])
        self.assertEqual(saved['opacity'],35)
        self.assertEqual(saved['other'],{'preserve':True})
        self.assertEqual(result['revision'],revision)
        self.assertEqual(saved['_'],self.original['_'])

    def test_erasing_manual_water_removes_both_type_and_manual_block(self):
        data=self.payload();data.update(water=['6002,1700'])
        editor.save_document(data)
        data=self.payload();data['blocked'].remove('6002,1700');data['water']=[]
        self.assertEqual(editor.save_document(data)[0],200)
        saved,_=editor.read_document()
        self.assertNotIn('6002,1700',saved['blocked']);self.assertEqual(saved['water'],[])

    def test_stale_tab_cannot_overwrite_newer_draft(self):
        first=self.payload();stale=dict(first)
        first['water']=['6002,1700'];editor.save_document(first)
        before=self.path.read_bytes()
        self.assertEqual(editor.save_document(stale)[0],409)
        self.assertEqual(self.path.read_bytes(),before)

    def test_legacy_browser_cannot_silently_drop_new_terrain_kinds(self):
        data=self.payload();data.pop('water')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):editor.save_document(data)
        self.assertEqual(self.path.read_bytes(),before)

    def test_water_cannot_be_simultaneously_passable(self):
        data=self.payload();data['water']=['6001,1700']
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):editor.save_document(data)
        self.assertEqual(self.path.read_bytes(),before)

    def test_bad_coordinates_and_opacity_do_not_write_partial_drafts(self):
        for changes in ({'water':['0,0']},{'rocks':['not a cell']},{'opacity':101},{'opacity':-1},{'opacity':True}):
            data=self.payload();data.update(changes);before=self.path.read_bytes()
            with self.assertRaises(ValueError):editor.save_document(data)
            self.assertEqual(self.path.read_bytes(),before)

    def test_fully_transparent_and_opaque_views_preserve_terrain(self):
        for opacity in (0,100):
            data=self.payload();data['opacity']=opacity
            self.assertEqual(editor.save_document(data)[0],200)
            self.assertEqual(self.payload()['opacity'],opacity)
            self.assertEqual(self.payload()['blocked'],['6000,1700'])

    def test_atomic_replace_failure_keeps_previous_draft(self):
        data=self.payload();data['water']=['6002,1700'];before=self.path.read_bytes()
        with patch.object(editor.os,'replace',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):editor.save_document(data)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(Path(str(self.path)+'.tmp').exists())

    def test_connectivity_uses_edited_draft_instead_of_old_game_override(self):
        start=(6268,1819);target=(6269,1819)
        with patch.object(editor.world,'in_map',side_effect=lambda x,y:(x,y) in (start,target)), \
             patch.object(editor.world,'settlements',return_value={start:1,target:2}), \
             patch.object(editor.world,'water',return_value=False), \
             patch.object(editor.world,'terrain_repairs',return_value=set()), \
             patch.object(editor.world,'passable',return_value=False):
            self.assertTrue(editor.reachability([],[])['ok'])
            self.assertFalse(editor.reachability(['6269,1819'],[])['ok'])
            self.assertTrue(editor.reachability([],['6269,1819'])['ok'])


if __name__=='__main__':
    run_cases(TerrainEditor)
