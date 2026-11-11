"""Execute private panel bytecode: native-window isolation and compact layout bounds.

The fake display tree checks geometry and handlers, not Flash rasterization.
"""
import math
import unittest
import training_ground_client as client, widescreen
from avm_test import Function, Arr

class ASArray(Arr):
    def join(self, sep): return ASString(sep.join(str(x) for x in self))
    def concat(self, other): return ASArray([*self, *other])
class ASString(str):
    def split(self, sep): return ASArray(super().split(sep))

class Clip(dict):
    def __init__(self, name='root', parent=None):
        super().__init__(_name=name, _parent=parent, _x=0, _y=0, _visible=True)
        self.children=[]
        self.update(createEmptyMovieClip=self.clip, createTextField=self.field,
            getNextHighestDepth=lambda:len(self.children), stopDrag=lambda:None,
            swapDepths=lambda d:self.update(depth=d),
            getBounds=lambda target:dict(xMin=self.get("_x",0),yMin=self.get("_y",0),xMax=self.get("_x",0)+self.get("__width",self.get("_width",0)),yMax=self.get("_y",0)+self.get("__height",self.get("_height",0))),
            removeMovieClip=lambda:None, beginFill=lambda *a:None,
            beginBitmapFill=lambda *a:None, beginGradientFill=lambda *a:None, moveTo=lambda *a:None,
            lineTo=lambda *a:None, curveTo=lambda *a:None,
            lineStyle=lambda *a:None, endFill=lambda:None)
    def clip(self, name, depth):
        c=Clip(name,self); self[name]=c; self.children.append(c); return c
    def field(self,name,depth,x,y,w,h):
        f=self.clip(name,depth)
        f.update(_x=x,_y=y,_width=w,_height=h,text='',kind='text',format={})
        f.update(setTextFormat=lambda fmt:f.update(format=dict(fmt)),
                 setNewTextFormat=lambda fmt:f.update(format=dict(fmt)),
                 getTextFormat=lambda:dict(f['format']))

def environment(width=1004,height=710,tab='player',context='player',supply=False):
    g=dict(__tgSupply=supply,__tgTab=tab,__tgContext=context,__tgPostTitle='Учебный центр · испытательный полигон',
      __tgStatus='Уровень 12 · HP 481 · Выносливость 789 · ОД 136',__tgMode='mob',
      __tgPlayer=dict(skills=ASString('0,12,0,0,0'),specs=ASString('0,0,0,3,0,0,0,0,0,0,0,0,0,0,0')),
      __tgEnemy=dict(skills=ASString('0,12,0,0,0'),specs=ASString('0,0,0,3,0,0,0,0,0,0,0,0,0,0,0')),
      __tgSpecMax=5,__tgParticipants=1,__tgSpawnLabels=['Ближняя · выше и правее компьютера'],
      __tgSpawnPoint=0,__tgDistance=12,__tgEnemyHealing=True,__tgHealBelow=50,__tgHealCount=5,
      __tgMobHealth=100,__tgMobDamage=100,__tgMobName='Боец лагеря · 12 ур.',
      __tgEnemyPreset='Чёрный ловелас (A) · 12 ур. / Remington 11-87 (G)',
      __tgReport='Бой завершён. Урон: 1250. Попаданий: 12.',__tgMobGroup='camps',
      __tgCategory='mob' if tab=='mob' else 'weapon',__tgLine='all',__tgFilterQuery='',
      __tgRuleDraftValues=ASString('1,1,1,1,1,1,1,1,1,0,1,0,1,1'),__tgRules='Симулятор: после правок',__tgArmour=80)
    g.update(__tgProfileTitles=ASArray(["Исходный", "Исправленный", "Симулятор"]),
        __tgProfileKeys=ASArray(["baseline-v1", "candidate-v2", "simulator-test"]),
        __tgProfileValues=ASArray([g["__tgRuleDraftValues"]]*3),__tgProfileSelected=2)
    root=Clip()
    env=dict(_global=g,Stage=dict(width=width,height=height,addListener=lambda p:None,removeListener=lambda p:None),
      Mouse=dict(addListener=lambda p:None,removeListener=lambda p:None),
      Math=dict(min=min,max=max,floor=math.floor,ceil=math.ceil,round=lambda x:math.floor(x+0.5)),Boolean=bool,Number=float,
      String=lambda x:ASString(str(int(x)) if isinstance(x,float) and x.is_integer() else str(x)),
      TextFormat=lambda:{},flash=dict(geom=dict(Matrix=lambda:dict(createGradientBox=lambda *a:None))),
      lol=dict(core=dict(SceneShifter=dict(linkWindow=root,hotKeyManager=dict(addFilter=lambda x:None)))))
    funcs={}
    for name,args,body in client.patches(widescreen.Asm,widescreen.UNDEF)['globals']:
        funcs[name]=g[name]=Function(args,body.assemble(),env)
    for name in ('__tgResetClose','__tgLayout','__tgRequestList','__tgSupplyRequest','__tgKitRequest'):
        g[name]=lambda *a:None
    g['__onlineArt']=lambda *a:{k:None for k in ('in','t','b','l','r','tl','tr','bl','br')}
    g['__tgSelected']=lambda *a:'Remington 11-87 (G)'
    return funcs,g,root

class TrainingPrivateUI(unittest.TestCase):
    def test_profile_menu_selection_is_draft_and_description_has_no_overlaps(self):
        for width,height in ((800,600),(1004,710),(1280,720)):
            funcs,g,root=environment(width,height,tab='rules',context='computer')
            g.update(__tgProfileTitles=ASArray(['Исходный','Исправленная модель','Симулятор']),
                __tgProfileKeys=ASArray(['baseline-v1','candidate-v2','simulator-6b7b28d']),
                __tgProfileValues=ASArray([ASString('1,1,1,1,1,1,1,1,1,0,0,1,0'),ASString('1,1,1,1,1,1,1,1,1,0,1,0,1'),g['__tgRuleDraftValues']]),
                __tgProfileNotes=ASArray(['Исходные правила','Исправленные правила','Симулятор: новая броня','Новые режимы оружия']),
                __tgProfileOffsets=ASArray([0,1,2]),__tgProfileCounts=ASArray([1,1,2]),
                __tgProfileSelected=2,__tgRuleDetails=True,__tgRulePage=0)
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            self.assertEqual(p['ruleDescription']['text'],'Симулятор: новая броня\n\nНовые режимы оружия')
            self.assertLessEqual(p['ruleDescription']['_y']+p['ruleDescription']['_height'],p['rulesInfo']['_y'])
            self.assertLess(p['applyRules']['_y']+p['applyRules']['__height'],p['status']['_y'])
            funcs['__tgClick'].invoke(dict(__op='profiles',__value=''),[])
            self.assertEqual(p['__menuKey'],'profiles')
            menu=p['profiles']
            for b in menu.children:
                if b.get('__op') == 'rulespreset':
                    self.assertGreaterEqual(b['_x'],menu['__menuX'])
                    self.assertGreaterEqual(b['_y'],menu['__menuY'])
                    self.assertLessEqual(b['_y']+b['__height'],menu['__menuY']+menu['__menuHeight'])
            funcs['__tgClick'].invoke(dict(__op='profiles',__value=''),[])
            self.assertIsNone(p['__menuKey'])
            funcs['__tgClick'].invoke(dict(__op='rulespreset',__value=0),[])
            self.assertEqual(g['__tgProfileSelected'],0)
            self.assertEqual(g['__tgRuleDraftValues'],g['__tgProfileValues'][0])
            self.assertEqual(g['__tgPanel']['ruleDescription']['text'],'Исходные правила')

    def test_kit_preview_ignores_stale_data_and_uses_only_available_levels(self):
        funcs,g,root=environment(tab='kits',context='player')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];g['__tgKitSeq']=10
        packet=dict(request_id=9,level=12,line='G',wclass=1,levels=[4,8,12],available=1,title='12 G',summary='Skills',contents='Armour + gun')
        funcs['__tgKitPreview'].invoke(None,[packet])
        self.assertEqual(p['kitHeading']['text'],'Загрузка состава…')
        packet['request_id']=10
        funcs['__tgKitPreview'].invoke(None,[packet])
        self.assertEqual(p['kitContents']['text'],packet['contents'])
        self.assertEqual(p['kitLine']['caption']['text'],'Версия: G ▼')
        self.assertEqual(p['kitClass']['caption']['text'],'Дробовики ▼')
        self.assertFalse(p['apply']['_visible'])
        self.assertFalse(p['recover']['_visible'])
        funcs['__tgKitMenu'].invoke(None,['level'])
        self.assertEqual(len([c for c in p['kitMenu'].children if '__value' in c]),3)
        self.assertEqual([c['__value']['value'] for c in p['kitMenu'].children if '__value' in c],[4,8,12])
        self.assertNotIn('titleFrame',p)

    def test_repeated_click_closes_and_other_filter_replaces_the_menu(self):
        funcs,g,root=environment(tab='kits',context='player')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];g['__tgKitLevels']=list(range(1,21))
        funcs['__tgKitMenu'].invoke(None,['level'])
        self.assertEqual(p['__menuKey'],'kit:level')
        funcs['__tgKitMenu'].invoke(None,['level'])
        self.assertIsNone(p['kitMenu']);self.assertIsNone(p['__menuKey'])
        funcs['__tgKitMenu'].invoke(None,['line'])
        funcs['__tgKitMenu'].invoke(None,['class'])
        self.assertEqual(p['__menuKey'],'kit:class')
        choices=[c for c in p['kitMenu'].children if '__op' in c]
        self.assertEqual(len(choices),7)
        self.assertEqual([c['__value']['value'] for c in choices],list(range(7)))

    def test_all_popup_families_have_one_opaque_background_and_fit(self):
        for size in ((800,600),(1004,710),(1280,720)):
            for family,key in (('kit','level'),('filter','level'),('supply','level'),
                               ('supply','line'),('supply','detail')):
                with self.subTest(size=size,family=family,key=key):
                    funcs,g,root=environment(*size,tab='kits' if family=='kit' else 'mob',
                        context='player' if family=='kit' else 'supplies',supply=family=='supply')
                    funcs['__tgBuild'].invoke(None,[])
                    p=g['__tgPanel'];p['__catalogueLevels']=p['__supplyLevels']=list(range(1,21))
                    g['__tgKitLevels']=list(range(1,21))
                    paints=[]
                    original=g['__tgUIRect']
                    def paint(*args):
                        paints.append(args)
                        return original.invoke(None,list(args))
                    g['__tgUIRect']=paint
                    function,name={'kit':('__tgKitMenu','kitMenu'),'filter':('__tgFilterMenu','filtermenu'),
                                   'supply':('__tgSupplyMenu','supplyOptions')}[family]
                    funcs[function].invoke(None,[key])
                    box=p[name]
                    self.assertEqual(next(args[-1] for args in paints if args[1]=='menuBackground'),100)
                    self.assertGreaterEqual(box['__menuX'],16)
                    self.assertGreaterEqual(box['__menuY'],88)
                    self.assertLessEqual(box['__menuX']+box['__menuWidth'],p['__w']-16)
                    self.assertLessEqual(box['__menuY']+box['__menuHeight'],p['__h']-80)
                    choices=[c for c in box.children if '__op' in c]
                    for c in choices:
                        self.assertGreaterEqual(c['_x'],box['__menuX'])
                        self.assertLessEqual(c['_x']+c['__width'],box['__menuX']+box['__menuWidth'])
                        self.assertLessEqual(c['_y']+c['__height'],box['__menuY']+box['__menuHeight'])
                    funcs[function].invoke(None,[key])
                    self.assertIsNone(p[name])

    def test_escape_closes_top_layer_once_and_preserves_native_keyboard(self):
        funcs,g,root=environment(tab='kits',context='player')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];g['__tgKitLevels']=[1,4,12]
        funcs['__tgKitMenu'].invoke(None,['level'])
        env=funcs['__tgEscape'].closure
        query={}
        env['lol']['core']['SceneShifter']['_ref']=dict(UIPanels=dict(query=query))
        events=[]
        g['__tgClose']=lambda:g.update(__tgPanel=None)
        code=[27]
        for function in ('__tgKeysDown','__tgKeysUp'):
            funcs[function].closure['Key']=dict(getCode=lambda:code[0])
        keys=dict(__tgKeysDownOrig=lambda:events.append('down'),__tgKeysUpOrig=lambda:events.append('up'))
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertIsNone(p['kitMenu']);self.assertIs(g['__tgPanel'],p)
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertIs(g['__tgPanel'],p)  # OS auto-repeat must not close the parent.
        funcs['__tgKeysUp'].invoke(keys,[])
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertIsNone(g['__tgPanel']);self.assertFalse(events)
        funcs['__tgKeysUp'].invoke(keys,[])
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertEqual(events,['down'])  # No private window: ordinary Escape.
        g['__tgPanel']=p;query['instance']={'native':True}
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertEqual(events,['down','down'])
        self.assertIs(g['__tgPanel'],p)
        query['instance']=None;g['__tgResetPending']=True
        g['__tgResetClose']=lambda:g.update(__tgResetPending=False)
        funcs['__tgKeysDown'].invoke(keys,[])
        self.assertFalse(g['__tgResetPending']);self.assertIs(g['__tgPanel'],p)

    def test_filter_caption_survives_removal_of_clicked_movieclip(self):
        funcs,g,root=environment(tab='gear',context='weapons',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];requested=[]
        g['__tgSupplyRequest']=lambda:requested.append(g['__tgSupplyDetail'])
        for value,label in [('base','Без улучшения'),('modified','С улучшением'),('all','Все улучшения')]:
            button=dict(__op='detailset',__value=value,__label=label)
            # Flash unloads properties on the clicked clip when its popup dies.
            g['__tgMenusClose']=lambda *a:button.clear()
            funcs['__tgSupplyClick'].invoke(button,[])
            self.assertEqual(p['detail']['caption']['text'],label)
            self.assertEqual(g['__tgSupplyDetail'],value)
        self.assertEqual(requested,['base','modified','all'])

    def test_outside_click_closes_popup_but_anchor_click_can_toggle(self):
        funcs,g,root=environment(tab='kits',context='player')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];g['__tgKitLevels']=[1,5,12]
        funcs['__tgKitMenu'].invoke(None,['level'])
        p['_xmouse']=40;p['_ymouse']=110
        funcs['__tgMenuMouseDown'].invoke(p,[])
        self.assertIsNotNone(p['kitMenu'])
        funcs['__tgKitMenu'].invoke(None,['level'])
        self.assertIsNone(p['kitMenu'])
        funcs['__tgKitMenu'].invoke(None,['level'])
        box=p['kitMenu'];p['_xmouse']=box['__menuX']+10;p['_ymouse']=box['__menuY']+10
        funcs['__tgMenuMouseDown'].invoke(p,[])
        self.assertIsNotNone(p['kitMenu'])
        p['_xmouse']=p['__w']-10;p['_ymouse']=p['__h']-10
        funcs['__tgMenuMouseDown'].invoke(p,[])
        self.assertIsNone(p['kitMenu'])



    def test_personal_description_reuses_base_notes_and_preview_releases_listeners(self):
        funcs,g,root=environment(tab='rules',context='computer')
        g.update(__tgRuleDetails=True,__tgProfileTitles=['Base','Mine'],__tgProfileKeys=['baseline-v1','user-0000000000000000'],
                 __tgProfileValues=[ASString('1,1,1,1,1,1,1,1,1,0,0,1,0')]*2,
                 __tgProfilePersonal=[0,1],__tgProfileBases=['baseline-v1','baseline-v1'],
                 __tgProfileOffsets=[0,1],__tgProfileCounts=[1,1],__tgProfileNotes=['Base description','My tuning'],__tgProfileSelected=1)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        self.assertEqual(p['ruleDescription']['text'],'My tuning\n\nBase description')
        calls=[]
        proto=dict(removeEventListener=lambda *a:calls.append(('proto',a)))
        item=dict(removeEventListener=lambda *a:calls.append(('item',a)),stringUpdate='listener')
        holder=dict(__panel=p,__proto=proto,__item=item,
                    card=dict(icon_mc=dict(src=dict(removeEventListener=lambda *a:calls.append(('icon',a))),mcl_list={}),
                              kill=lambda:calls.append(('kill',))),removeMovieClip=lambda:calls.append(('remove',)))
        p['__gearViews']=[holder]
        funcs['__tgGearClear'].closure['lol']['utils']=dict(StringCollector=dict(getInstance=lambda:dict(removeEventListener=lambda *a:calls.append(('strings',a)))))
        funcs['__tgGearClear'].invoke(None,[p])
        self.assertIsNone(p['__gearViews']);self.assertIsNone(holder['__panel'])
        self.assertEqual([c[0] for c in calls],['proto','item','proto','strings','icon','kill','remove'])
        funcs['__tgGearReady'].invoke(holder,[dict(target=proto)]) # Late callback must do nothing.
        self.assertEqual(len(calls),7)

    def test_description_scrolls_without_rebuild_or_server_request(self):
        funcs,g,root=environment(tab='rules',context='computer')
        g.update(__tgRuleDetails=True,__tgProfileOffsets=[0,0,0],__tgProfileCounts=[1,1,1],__tgProfileNotes=['Long description'])
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];f=p['ruleDescription'];f['maxscroll']=30
        g['__tgBuild']=lambda:self.fail('Scrolling rebuilt the panel')
        g['__tgTransmit']=lambda *a:self.fail('Scrolling used the network')
        p['_xmouse']=f['_x']+10;p['_ymouse']=f['_y']+10
        funcs['__tgRuleWheel'].invoke(p,[-1])
        self.assertEqual(f['scroll'],4)
        funcs['__tgRuleScroll'].invoke(None,[100])
        self.assertEqual(f['scroll'],30)
        p['__menuKey']='profiles'
        funcs['__tgRuleWheel'].invoke(p,[1])
        self.assertEqual(f['scroll'],30)
        p['__menuKey']=None
        funcs['__tgRuleScroll'].invoke(None,[-100])
        self.assertEqual(f['scroll'],1)
        self.assertNotIn('ruleNext',p)

    def test_personal_form_and_close_button_fit_compact_window(self):
        for mode in ('create','edit','delete'):
            funcs,g,root=environment(800,600,'rules','computer')
            g.update(__tgPersonalMode=mode,__tgPersonalName='Мои правила',__tgProfilePersonal=[0,0,1])
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            self.assertEqual(p['cross']['_y'],p['__w']-p['cross']['_x']-p['cross']['__width'])
            self.assertLessEqual(p['profileName']['_y']+p['profileName']['_height'],p['personalInfo']['_y'])
            self.assertLessEqual(p['personalInfo']['_y']+p['personalInfo']['_height'],p['personalConfirm']['_y'])
            self.assertLess(p['personalConfirm']['_y']+25,p['status']['_y'])

    def test_enemy_preview_slots_fit_and_switch_back(self):
        funcs,g,root=environment(800,600,'enemygear','computer')
        g['__tgEnemy']['gear']=ASString('')
        g.update(__tgEnemyLook=True,__tgSlots={},__tgPreviewTypes={})
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        self.assertEqual(len(p['__gearViews']),8)
        self.assertIn('Подсумок',[v['slotTitle']['text'] for v in p['__gearViews']])
        for v in p['__gearViews']:
            self.assertLess(v['_x']+v['__width'],p['__w'])
            self.assertLess(v['_y']+24+v['__cardHeight'],p['status']['_y'])
        funcs['__tgClick'].invoke(dict(__op='enemylook',__value=''),[])
        self.assertFalse(g['__tgEnemyLook'])
        self.assertIn('category',g['__tgPanel'])

    def test_archive_has_categories_and_visible_warning(self):
        for width,height in ((800,600),(1004,710)):
            funcs,g,root=environment(width,height,tab='gear',context='archive',supply=True)
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            self.assertEqual([p['cat'+str(i)]['__value'] for i in range(3)],
                             ['souvenir','unsupported','legacy'])
            self.assertFalse(p['detail']['_visible'])
            self.assertIn('Архив',p['profileNote']['text'])

    def test_condition_controls_only_expose_effective_parameters(self):
        for fighter,healing in ((False,False),(True,False),(True,True)):
            funcs,g,root=environment(tab='result',context='computer')
            g['__tgMode']='fighter' if fighter else 'mob'
            g['__tgEnemyHealing']=healing
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            self.assertEqual(p['healing']['_visible'],fighter)
            self.assertEqual(p['healBelow']['_visible'],fighter and healing)
            self.assertEqual(p['healCount']['_visible'],fighter and healing)
            self.assertEqual(p['mobDamage']['_visible'],not fighter)
            self.assertEqual(p['mobHealth']['_visible'],not fighter)

    def test_empty_supply_and_last_page_disable_unusable_controls(self):
        funcs,g,root=environment(tab='gear',context='boosts',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        # Initial builder sends no request in this fixture; exercise the real one.
        funcs['__tgSupplyClear'].invoke(None,[p])
        self.assertFalse(p['give']['enabled'])
        self.assertFalse(p['amount']['_visible'])
        self.assertFalse(p['detail']['_visible'])
        g['__tgCatalogueRequest']=1
        funcs['__tgSupplyList'].invoke(None,[dict(context='boosts',request_id=1,page=0,
            total=0,ids=[],available_levels=[],selected_level=0)])
        self.assertFalse(p['prev']['enabled']);self.assertFalse(p['next']['enabled'])
        funcs['__tgSupplyList'].invoke(None,[dict(context='boosts',request_id=1,page=1,
            total=11,ids=[],available_levels=[],selected_level=0)])
        self.assertTrue(p['prev']['enabled']);self.assertFalse(p['next']['enabled'])

    def test_standard_windows_and_hud_do_not_inherit_private_style(self):
        funcs,g,root=environment()
        for name in ('dialog','quest','trade','teaching','hud'):
            native=Clip(name)
            self.assertFalse(funcs['__tgUIOwned'].invoke(None,[native]))
            funcs['__tgUISelect'].invoke(None,[native,True])
            self.assertNotIn('__selected',native)
            field=funcs['__tgText'].invoke(None,[native,'test','Test',0,0,100,25,False])
            self.assertEqual(field['format']['size'],12)

    def test_owned_controls_keep_handler_and_selection_inside_panel(self):
        funcs,g,root=environment()
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        self.assertTrue(funcs['__tgUIOwned'].invoke(None,[p['apply']]))
        self.assertIs(p['apply']['onRelease'],g['__tgClick'])
        self.assertEqual(p['apply']['__op'],'apply')
        self.assertEqual(p['skill0']['format']['size'],16)
        self.assertTrue(p['tab0']['selectedMark']['_visible'])


    def test_skills_and_specializations_are_separate_without_changing_actions(self):
        for tab in ('player','enemy'):
            funcs,g,root=environment(800,600,tab,'player' if tab=='player' else 'computer')
            funcs['__tgBuild'].invoke(None,[])
            p=g['__tgPanel']
            self.assertEqual(p['skillsHeading']['text'],'Основные навыки')
            self.assertEqual(p['specsHeading']['text'],'Специализации')
            for i in range(5):
                self.assertLess(p[f'skill{i}plus']['_x']+22,p['skillsDivider']['_x'])
                self.assertEqual(p[f'skill{i}plus']['__value']['field'],f'skill{i}')
            for i in range(12):
                self.assertGreater(p[f'spec{i}label']['_x'],p['skillsDivider']['_x'])
                self.assertEqual(p[f'spec{i}plus']['__value']['field'],f'spec{i}')
            if tab=='enemy':
                self.assertGreater(p['copy']['_y'],p['spec11plus']['_y']+25)

    def test_mob_level_menu_uses_only_received_category_levels(self):
        funcs,g,root=environment(tab='mob',context='computer')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];p['__catalogueLevels']=[3,7,12,18]
        funcs['__tgFilterMenu'].invoke(None,['level'])
        self.assertEqual([c['__value']['value'] for c in p['filtermenu'].children if '__value' in c],[0,3,7,12,18])
        # New category has no metadata yet: do not reuse the previous choices.
        funcs['__tgMenusClose'].invoke(None,[p]);p['__catalogueLevels']=[]
        funcs['__tgFilterMenu'].invoke(None,['level'])
        self.assertEqual([c['__value']['value'] for c in p['filtermenu'].children if '__value' in c],[0])

    def test_level_metadata_ignores_old_reply_and_syncs_corrected_selection(self):
        funcs,g,root=environment(tab='mob',context='computer')
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];g['__tgCatalogueRequest']=2
        rows=dict(context='computer',request_id=2,available_levels=[4,8,12],
                  selected_level=0,page=0,total=0,ids=[])
        g['__tgFilterLevel']=40;g['__tgPage']=5
        funcs['__tgList'].invoke(None,[rows])
        self.assertEqual(p['__catalogueLevels'],[4,8,12])
        self.assertEqual(g['__tgFilterLevel'],0)
        self.assertEqual(g['__tgPage'],0)
        self.assertIn('Любой уровень',p['levelfilter']['caption']['text'])
        funcs['__tgList'].invoke(None,[dict(rows,request_id=1,available_levels=[40],selected_level=40)])
        self.assertEqual(p['__catalogueLevels'],[4,8,12])
        self.assertEqual(g['__tgFilterLevel'],0)

    def test_item_levels_are_not_restricted_by_mob_category(self):
        funcs,g,root=environment(tab='enemygear',context='computer')
        funcs['__tgBuild'].invoke(None,[])
        g['__tgPanel']['__catalogueLevels']=[4,12,17]
        funcs['__tgFilterMenu'].invoke(None,['level'])
        self.assertEqual([c['__value']['value'] for c in g['__tgPanel']['filtermenu'].children if '__value' in c],[0,4,12,17])

    def test_supply_level_menu_uses_received_item_levels(self):
        funcs,g,root=environment(tab='gear',context='weapons',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel'];p['__supplyLevels']=[1,4,12]
        funcs['__tgSupplyMenu'].invoke(None,['level'])
        options=[c for c in p['supplyOptions'].children if '__op' in c]
        self.assertEqual([c['__value'] for c in options],[0,1,4,12])


    def test_medical_categories_hide_level_and_preserve_selected_caption(self):
        funcs,g,root=environment(tab='gear',context='medical',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        self.assertFalse(p['level']['_visible'])
        self.assertEqual(g['__tgSupplyCategory'],'medicine')
        requests=[]
        g['__tgSupplyRequest']=lambda:requests.append((g['__tgSupplyCategory'],g['__tgSupplyDetail'],g['__tgSupplyLevel']))
        funcs['__tgSupplyMenu'].invoke(None,['category'])
        options=[b for b in p['supplyOptions'].children if '__op' in b]
        self.assertEqual([b['__label'] for b in options],['Медицина','Ивентовое лечение'])
        self.assertEqual([b['__value'] for b in options],['medicine','event_medicine'])
        button=options[1]
        g['__tgSupplyDetail']='battle';g['__tgSupplyLevel']=20
        # Flash unloads the clicked clip with its containing menu.
        close=g['__tgMenusClose']
        g['__tgMenusClose']=lambda panel:(close.invoke(None,[panel]),button.clear())
        funcs['__tgSupplyClick'].invoke(button,[])
        self.assertEqual(requests[-1],('event_medicine','all',0))
        self.assertEqual(p['all']['caption']['text'],'Ивентовое лечение ▼')
        self.assertEqual(p['all']['hintTitle_str'],'Категория: Ивентовое лечение')
        for shelf in (1,0):
            funcs['__tgSupplyClick'].invoke(dict(__op='shelf',__value=shelf),[])
            self.assertFalse(p['level']['_visible'])
            self.assertEqual(p['all']['_visible'],not shelf)

    def test_medical_menu_mouse_down_then_release_toggles_without_request(self):
        for kind,anchor in [('detail','detail'),('category','all'),('line','line')]:
            with self.subTest(kind=kind):
                funcs,g,root=environment(800,600,'gear','medical',True)
                funcs['__tgBuild'].invoke(None,[])
                p=g['__tgPanel'];requests=[]
                g['__tgSupplyRequest']=lambda:requests.append(1)
                button=p[anchor]
                for expected in (True,False,True,False):
                    p['_xmouse']=button['_x']+button['__width']/2
                    p['_ymouse']=button['_y']+button['__height']/2
                    funcs['__tgMenuMouseDown'].invoke(p,[])
                    button['onRelease'].invoke(button,[])
                    self.assertEqual(p.get('__menuKey'),('supply:'+kind) if expected else None)
                self.assertEqual(requests,[])

    def test_medical_escape_closes_list_then_panel(self):
        funcs,g,root=environment(tab='gear',context='medical',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        funcs['__tgEscape'].closure['lol']['core']['SceneShifter']['_ref']=dict(UIPanels=dict(query={}))
        g['__tgClose']=lambda:g.update(__tgPanel=None)
        for kind in ('category','detail','line'):
            funcs['__tgSupplyMenu'].invoke(None,[kind])
            self.assertTrue(funcs['__tgEscape'].invoke(None,[]))
            self.assertIsNone(p['__menuKey'])
            self.assertIs(g['__tgPanel'],p)
        self.assertTrue(funcs['__tgEscape'].invoke(None,[]))
        self.assertIsNone(g['__tgPanel'])

    def test_buff_filters_stay_hidden_after_switching_shelves(self):
        funcs,g,root=environment(tab='gear',context='boosts',supply=True)
        funcs['__tgBuild'].invoke(None,[])
        p=g['__tgPanel']
        for value in (1,0,1,0):
            funcs['__tgSupplyClick'].invoke(dict(__op='shelf',__value=value),[])
            for key in ('level','all','detail'):
                self.assertFalse(p[key]['_visible'],key)
            self.assertEqual(p['query']['_visible'],not value)
            self.assertEqual(p['line']['_visible'],not value)

    def test_visible_controls_do_not_overlap_each_other_or_column_dividers(self):
        configurations=[('player','player',False),('kits','player',False),('enemy','computer',False),
            ('result','computer',False),('rules','computer',False),('reset','computer',False),
            ('mob','computer',False),('enemygear','computer',False)]
        configurations += [('gear',ctx,True) for ctx in
            ('weapons','armoury','supplies','medical','boosts','specialist','archive')]
        for size in ((800,600),(1004,710),(1280,720),(1920,1080)):
            for tab,ctx,supply in configurations:
                with self.subTest(size=size,tab=tab,context=ctx):
                    funcs,g,root=environment(*size,tab,ctx,supply)
                    dividers=[]
                    def rect(parent,name,x,y,w,h,color,alpha):
                        if name in ('filterDivider','previewDivider','categoryDivider'):
                            dividers.append((name,x,y,w,h))
                        return funcs['__tgUIRect'].invoke(None,[parent,name,x,y,w,h,color,alpha])
                    g['__tgUIRect']=rect
                    funcs['__tgBuild'].invoke(None,[])
                    p=g['__tgPanel']
                    boxes=[]
                    for c in p.children:
                        if c.get('_visible',True) and (c.get('kind')=='text' or '__op' in c):
                            boxes.append((c['_name'],c['_x'],c['_y'],
                                c.get('__width',c.get('_width',0)),c.get('__height',c.get('_height',0))))
                    for i,(name,x,y,w,h) in enumerate(boxes):
                        for other,xx,yy,ww,hh in boxes[i+1:]+dividers:
                            overlaps=min(x+w,xx+ww)>max(x,xx) and min(y+h,yy+hh)>max(y,yy)
                            self.assertFalse(overlaps,(name,other))

    def test_background_stops_inside_metal_border(self):
        funcs,g,root=environment()
        tiles=[]
        g['__tgTile']=lambda p,name,bitmap,x,y,w,h:tiles.append((name,x,y,w,h))
        funcs['__tgUIFrame'].invoke(None,[root,980,640])
        self.assertIn(('inside',8,8,964,624),tiles)

    def test_new_panels_fit_supported_window_sizes(self):
        for width,height in [(800,600),(1004,710),(1280,720),(1920,1080)]:
            for tab,ctx,supply in [('player','player',False),('kits','player',False),('enemy','computer',False),
                ('result','computer',False),('rules','computer',False),('reset','computer',False),
                ('mob','computer',False),('enemygear','computer',False),
                ('gear','weapons',True),('gear','armoury',True),('gear','medical',True)]:
                with self.subTest(size=(width,height),tab=tab,context=ctx):
                    funcs,g,root=environment(width,height,tab,ctx,supply)
                    funcs['__tgBuild'].invoke(None,[])
                    p=g['__tgPanel'];H=p['__h'];W=p['__w']
                    for c in p.children:
                        if c.get('kind')=='text' and c['_visible']:
                            self.assertGreaterEqual(c['_x'],0,c['_name'])
                            self.assertGreaterEqual(c['_y'],0,c['_name'])
                            self.assertLessEqual(c['_x']+c['_width'],W+1,c['_name'])
                            self.assertLessEqual(c['_y']+c['_height'],H+1,c['_name'])
                    if tab in ('player','enemy'):
                        self.assertLessEqual(p['spec3plus']['_y']+25,p['levelHint']['_y']-4)
                    if tab=='result':
                        self.assertLessEqual(p['distanceInfo']['_y']+p['distanceInfo']['_height'],p['healing']['_y'])
                    if tab=='rules':
                        self.assertGreaterEqual(p['personalHint']['_height'],18)

if __name__=='__main__': unittest.main()
