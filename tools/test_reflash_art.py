"""Inspect the shipped ReFlash symbol instead of relying on mocked UI labels."""
import struct
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import widescreen as w
from reflash_art import artwork, LINKAGE
import zlib
from testkit import run_cases


class ReFlashArtwork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        source = Path(os.environ.get('LAVA_RES', 'D:/lava-reborn/res')) / 'main.swf'
        if not source.is_file():
            raise unittest.SkipTest('original main.swf assets not available')
        _, body = w.read_swf(source)
        cls.tags = w.split_tags(body)

    def linked(self, tags):
        found = {}
        for code,p,_ in tags:
            if code != 56:
                continue
            at=2
            for _ in range(int.from_bytes(p[:2],'little')):
                cid=int.from_bytes(p[at:at+2],'little')
                end=p.index(0,at+2)
                found[p[at+2:end].decode()]=cid
                at=end+1
        return found

    def test_two_baked_states_without_any_text_or_filters_or_native_class(self):
        tags=artwork(self.tags)
        links=self.linked(tags)
        cid=links[LINKAGE]
        sprite=next(p for code,p,_ in tags if code==39 and int.from_bytes(p[:2],'little')==cid)
        children=w.split_tags(b'\x08\0\0\0\0\0'+sprite[4:])
        self.assertEqual([code for code,_,_ in children],[12,26,1,26,1,0])
        self.assertNotIn('__rf_caption_art',links)
        self.assertFalse(any(code==59 and int.from_bytes(p[:2],'little')==cid for code,p,_ in tags))
        frames=[]
        for name in ('__rf_up_bitmap','__rf_down_bitmap'):
            bid=links[name]
            bitmap=next(p for code,p,_ in tags if code==36 and int.from_bytes(p[:2],'little')==bid)
            self.assertEqual(struct.unpack_from('<BHH',bitmap,2),(5,83,45))
            pixels=zlib.decompress(bitmap[7:])
            self.assertEqual(len(pixels),83*45*4)
            frames.append(pixels)
        self.assertNotEqual(frames[0],frames[1])

    def test_new_definitions_reserve_nested_bitmap_ids(self):
        nested=[(36,struct.pack('<H',2)+b'fixture',True),(1,b'',False),(0,b'',False)]
        fixture=[(39,struct.pack('<HH',1,1)+w.join_tags(b'',nested),True),
                 (1,b'',False),(0,b'',False)]
        result=artwork(fixture)
        self.assertEqual(self.linked(result)[LINKAGE],3)
        self.assertIn(fixture[0],result)

    def test_full_client_injection_is_idempotent_with_baked_states(self):
        once=w.inject(self.tags)
        self.assertEqual(w.inject(once),once)
        reread=w.split_tags(b'\x08\0\0\0\0\0'+w.join_tags(b'',once))
        self.assertEqual(w.inject(reread),reread)

    def test_rebuild_is_idempotent_and_keeps_original_exit_untouched(self):
        once=artwork(self.tags)
        self.assertEqual(artwork(once),once)
        original=self.linked(self.tags)['exit_btn']
        self.assertEqual([t for t in once if t[0]==39 and int.from_bytes(t[1][:2],'little')==original],
                         [t for t in self.tags if t[0]==39 and int.from_bytes(t[1][:2],'little')==original])


if __name__=='__main__':
    run_cases(ReFlashArtwork)
