"""Exercise the legacy Flash frame scanner, then the emitted range UI bytecode."""
import math
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from protocol import encode, unescape, Str
from training import profiles as training_profiles
from test_training_ui_client import environment, ASArray, ASString, Clip


def flash_parse(source):
    # SCDataParser.parse advances by delimiters, not by the end of string lists.
    # A Python protocol.decode roundtrip cannot reproduce this client defect.
    params = {}
    equal = semi = 0
    for _ in range(len(source)):
        equal = source.find('=', equal + 1)
        if equal < 0:
            return params
        semi = source.find(';', semi + 1)
        key = source[semi + 1:equal]
        start = equal + 1
        first = source[start]
        if first == '@':
            value = ASString(unescape(source[start + 1:source.index('@;', start + 1)]))
            params[key] = value
            if value:
                semi += len(key) + 2 + len(value)
                equal += 2 + len(value)
        elif first == '|':
            if source[start + 1] == '@':
                end = source.index('@|;', start)
                params[key] = ASArray(ASString(v) for v in source[start + 2:end].split('@|@'))
            elif source[start + 1] == ';':
                params[key] = ASArray()
            else:
                end = source.index('|;', start)
                params[key] = ASArray(int(v) for v in source[start + 1:end].split('|'))
        elif first.isdigit() or first in '+-':
            value = source[start:source.index(';', start)]
            try:
                params[key] = int(value)
            except ValueError:
                params[key] = math.nan
    raise AssertionError('Scanner did not terminate')


class ProfileWire(unittest.TestCase):
    def test_both_search_windows_preserve_input_through_real_server_decoding(self):
        from protocol import escape, decode
        text = ASString('АК %26 @ "; next=value & <G> Привет')
        for supply in (False,True):
            funcs,g,root=environment(tab='gear',context='weapons',supply=supply)
            sent=[]
            def message():
                row={}
                row['addProp']=lambda key,value:row.update({key:value})
                return row
            env=funcs['__tgRequestList'].closure
            env['lol']['server']=dict(XMLString=dict(escape=escape),mess=dict(CSMessage=message))
            g.update(__tgPanel=dict(__supply=supply,query=dict(text=text),status={},previewTitle={},variantTitle={},price={}),
                     __tgToken='test-token',__tgCatalogueRequest=0,__tgClass=-1,__tgLine='G',__tgPage=0,
                     __tgUpgrade='all',__tgFilterLevel=0,__tgMobGroup='camps',__tgSupplyPage=0,
                     __tgSupplyLevel=0,__tgSupplyLine=0,__tgSupplyClass=-1,__tgSupplyCategory='all',
                     __tgSupplyDetail='all',__tgSupplyBag=False,__tgTransmit=sent.append)
            for helper in ('__tgUIEnable','__tgUISupplySelection','__tgSupplyClear'):
                g[helper]=lambda *args:None
            funcs['__tgSupplyRequest' if supply else '__tgRequestList'].invoke(None,[])
            props={k:v for k,v in sent[-1].items() if k not in ('_name','addProp')}
            frame='tg'+''.join(';'+k+'='+str(v) for k,v in props.items())+';'
            command,parsed=decode(frame)
            self.assertEqual(command,'tg')
            self.assertEqual(parsed['query'],text)
            self.assertNotIn('next',parsed)

    def test_real_frame_keeps_default_and_all_profiles_after_description_lists(self):
        for index, profile in enumerate(training_profiles.catalogue()):
            payload = training_profiles.payload(profile.rules)
            frame = encode('tg', op=Str('open'), context=Str('computer'),
                           title=Str('Компьютер полигона'), category=Str('mob'),
                           mob=1, wclass=-1, supply=0, **payload)
            packet = flash_parse(frame)
            self.assertEqual(packet['profile_selected'], index)
            funcs, g, root = environment(context='computer', tab='mob')
            funcs['__tgProfileTexts'].closure['lol']['server'] = dict(XMLString=dict(unescape=lambda s:ASString(unescape(s))))
            funcs['__tgNotifyWrapper'].invoke(None, [dict(messID='tg', params=packet)])
            g['__tgTab'] = 'rules'
            g['__tgRuleDraftValues'] = ASString(profile.rules.values())
            funcs['__tgBuild'].invoke(None, [])
            self.assertEqual(g['__tgProfileSelected'], index)
            self.assertEqual(g['__tgPanel']['profileSelect']['caption']['text'], 'Профиль: ' + profile.title + ' ▼')
            for choice, expected in enumerate(training_profiles.catalogue()):
                funcs['__tgClick'].invoke(dict(__op='rulespreset', __value=choice), [])
                self.assertEqual(g['__tgPanel']['ruleDescription']['text'], '\n\n'.join(expected.notes))
            self.assertEqual(list(g['__tgProfileNotes']), [s for p in training_profiles.catalogue() for s in p.notes])

    def test_delimiters_and_literal_percent_sequences_roundtrip_without_damaging_following_fields(self):
        texts = ['Урон +10%; броня = 2 | A@G', '100% "%3B" & <бонус> O\'Neil', 'Строка\nЕщё строка']
        packet = flash_parse(encode('tg', texts=training_profiles._texts(texts), selected=0, count=3))
        self.assertEqual((packet['selected'], packet['count']), (0, 3))
        funcs, g, root = environment()
        funcs['__tgProfileTexts'].closure['lol']['server'] = dict(XMLString=dict(unescape=lambda s:ASString(unescape(s))))
        self.assertEqual(list(funcs['__tgProfileTexts'].invoke(None, [packet['texts'], 1])), texts)

    def test_legacy_packet_reproduces_missing_default_profile(self):
        payload = training_profiles.payload(training_profiles.catalogue()[0].rules)
        # This defect is about the legacy scanner, not which engines are installed.
        payload['profile_notes'] = ['Было: броня = 2; стало: броня = 3.']
        old = flash_parse(encode('tg', op=Str('open'), **payload))
        self.assertNotIn('profile_selected', old)

    def test_missing_or_invalid_profile_never_applies_a_different_profile(self):
        for bad in (None, -1, 10, 'undefined'):
            funcs, g, root = environment(context='computer', tab='rules')
            funcs['__tgProfilesLoad'].invoke(None, [dict(profile_selected=bad)])
            funcs['__tgBuild'].invoke(None, [])
            p = g['__tgPanel']
            self.assertEqual(p['profileSelect']['caption']['text'], 'Профили не загружены')
            self.assertFalse(p['profileSelect']['enabled'])
            self.assertNotIn('applyRules', p)
            sent = []
            g['__tgSend'] = lambda *args:sent.append(args)
            funcs['__tgClick'].invoke(dict(__op='rulesapply', __value=''), [])
            self.assertEqual(sent, [])

    def test_private_text_and_buttons_use_unscaled_integer_positions_and_plain_arial(self):
        funcs, g, root = environment()
        p = Clip(); p['__tgStyled'] = True
        f = funcs['__tgText'].invoke(None, [p, 'sample', 'Текст', 3.3, 4.5, 155.5, 23.2, False])
        self.assertEqual((f['_x'], f['_y'], f['_width'], f['_height']), (3, 5, 156, 23))
        self.assertEqual(f['format']['font'], 'Arial')
        self.assertFalse(f['format']['bold']); self.assertFalse(f['format']['italic'])
        self.assertFalse(f['embedFonts']); self.assertEqual(f['filters'], [])
        b = funcs['__tgButton'].invoke(None, [p, 'b', 'Выбрать', 5.5, 6.2, 180, 'tab', 'rules'])
        self.assertEqual((b['_x'], b['_y']), (6, 6))


    def test_supply_filter_and_category_choices_always_keep_readable_captions(self):
        for context in ('weapons','armoury','supplies','medical','boosts','specialist','archive'):
            funcs,g,root=environment(tab='gear',context=context,supply=True)
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            for family in ('line','level','detail'):
                p['__supplyLevels']=ASArray([1,10,17,20])
                funcs['__tgSupplyMenu'].invoke(None,[family])
                options=[c for c in p['supplyOptions'].children if c.get('__op')]
                for b in options:
                    label=b['caption']['text']
                    self.assertTrue(label,(context,family))
                    funcs['__tgSupplyClick'].invoke(b,[])
                    for field in ('line','level','detail'):
                        caption=p[field]['caption']['text']
                        self.assertIsInstance(caption,str)
                        self.assertFalse(any(bad in caption for bad in ('undefined','None','NaN')),(context,field,caption))
            for b in [c for c in p.children if c.get('__op')=='category']:
                funcs['__tgSupplyClick'].invoke(b,[])
                self.assertEqual(p['detail']['caption']['text'],'Фильтр: все')

    def test_enemy_filters_and_preset_categories_have_labels_after_every_selection(self):
        funcs,g,root=environment(tab='enemygear',context='computer')
        funcs['__tgBuild'].invoke(None,[])
        for family in ('category','class','line','upgrade','level'):
            p=g['__tgPanel'];p['__catalogueLevels']=ASArray([1,10,17,20])
            funcs['__tgFilterMenu'].invoke(None,[family])
            options=[c for c in p['filtermenu'].children if c.get('__op')]
            for b in options:
                funcs['__tgClick'].invoke(b,[])
                for field in ('category','class','linefilter','upgradefilter','levelfilter'):
                    caption=g['__tgPanel'][field]['caption']['text']
                    self.assertIsInstance(caption,str)
                    self.assertFalse(any(bad in caption for bad in ('undefined','None','NaN')),(family,caption))
        funcs,g,root=environment(tab='kits',context='player')
        funcs['__tgBuild'].invoke(None,[])
        for family in ('class','line','level'):
            g['__tgKitLevels']=ASArray([1,10,17,20])
            funcs['__tgKitMenu'].invoke(None,[family])
            options=[c for c in g['__tgPanel']['kitMenu'].children if c.get('__op')]
            for b in options:
                funcs['__tgClick'].invoke(b,[])
                for field in ('kitClass','kitLine','kitLevel'):
                    caption=g['__tgPanel'][field]['caption']['text']
                    self.assertIsInstance(caption,str)
                    self.assertFalse(any(bad in caption for bad in ('undefined','None','NaN')),(family,caption))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(ProfileWire)
