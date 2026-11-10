"""Small build-time contracts for native training-window hooks."""
import re
from pathlib import Path
import unittest

import training_ground_client as client
import widescreen


class TrainingClient(unittest.TestCase):
    def test_simulator_preset_is_explicit_draft_and_keeps_profile_flag_on_numeric_edit(self):
        class Parts(dict):
            def __init__(self, parts):
                super().__init__(enumerate(parts))
                self['join'] = lambda sep: Text(sep.join(self[index] for index in range(len(self) - 1)))
        class Text(str):
            def split(self, sep):
                return Parts(Text(part) for part in super().split(sep))
        built = []
        sent = []
        values = '1,1,1,1,1,1,1,1,1,0,1,0,1,1'
        env = dict(_global=dict(__tgPanel=dict(status=dict(text='')), __tgRuleDraftValues='old'), String=str)
        funcs = self.helpers(env)
        env['_global']['__tgBuild'] = lambda: built.append(True)
        env['_global']['__tgTransmit'] = lambda m: sent.append(m)
        funcs['__tgClick'].invoke(dict(__op='rulespreset', __value=values), [])
        self.assertEqual(env['_global']['__tgRuleDraftValues'], values)
        self.assertEqual(built, [True])
        self.assertEqual(sent, [])
        panel = env['_global']['__tgPanel']
        env['_global']['__tgRuleDraftValues'] = Text(values)
        for index, value in enumerate(values.split(',')[:10]):
            panel['rule' + str(index)] = dict(text=Text(value))
        panel['rule7']['text'] = Text('1,5')
        funcs['__tgRuleDraft'].invoke(None, [])
        updated = str(env['_global']['__tgRuleDraftValues']).split(',')
        self.assertEqual(updated[7], '1.5')
        self.assertEqual(updated[10:], ['1', '0', '1', '1'])
        self.assertIn('"Симулятор: после правок"', client.SOURCE)
        self.assertIn('"rulespreset", "' + values + '"', client.SOURCE)

    def test_free_quantity_apply_dispatches_even_when_displayed_price_is_zero(self):
        calls=[]
        env=dict(_global=dict(__tgActive=True), Number=float)
        funcs=self.helpers(env)
        box=dict(__tgFreeQuantity=True,rightNum='4',leftNum=46,maxValue=50,
                 money_mc=dict(info_txt=dict(text='0')),dispatchEvent=calls.append,
                 cancel=lambda:calls.append('cancel'),__tgQuantityApplyOrig=lambda:calls.append('native'))
        funcs['__tgQuantityApply'].invoke(box,[])
        self.assertEqual(calls,[dict(type='exchange',left=46,right=4)])
        box['rightNum']=0
        funcs['__tgQuantityApply'].invoke(box,[])
        self.assertEqual(calls[-1],'cancel')
        box['__tgFreeQuantity']=False
        funcs['__tgQuantityApply'].invoke(box,[])
        self.assertEqual(calls[-1],'native')

    def test_cancel_closes_free_quantity_and_restores_drag_once_without_request(self):
        calls=[]
        env=dict(_global={},lol=dict(core=dict(SceneShifter=dict(closeWindow=lambda name:calls.append(('closed',name))))))
        funcs=self.helpers(env)
        box=dict(removeEventListener=lambda *args:None)
        trade=dict(__tgPurchaseItem=dict(typeID=54000),__tgPurchaseBox=box,
                   applyTransfer=lambda success:calls.append(('transfer',success)))
        funcs['__tgTradeCancel'].invoke(trade,[dict(target=box)])
        funcs['__tgTradeCancel'].invoke(trade,[dict(target=box)])
        self.assertEqual(calls,[('closed','exchange'),('transfer',False)])
        self.assertIsNone(trade['__tgPurchaseBox'])

    def test_late_quantity_callback_does_not_close_new_dialog_or_buy_new_item(self):
        calls=[]
        env=dict(_global=dict(__tgActive=True),lol=dict(core=dict(SceneShifter=dict(closeWindow=calls.append))))
        funcs=self.helpers(env)
        old=dict(removeEventListener=lambda *args:None)
        current=dict(removeEventListener=lambda *args:None,new=True)
        item=dict(typeID=54001)
        trade=dict(__tgPurchaseItem=item,__tgPurchaseBox=current)
        funcs['__tgTradeQuantity'].invoke(trade,[dict(target=old,right=8)])
        self.assertEqual(calls,[])
        self.assertIs(trade['__tgPurchaseItem'],item)
        self.assertIs(trade['__tgPurchaseBox'],current)

    def test_ammo_quantity_cancel_restores_current_operation_without_money_alert(self):
        calls=[]
        env=dict(_global=dict(__tgActive=True),lol=dict(core=dict(SceneShifter=dict(closeWindow=lambda name:calls.append(name)))))
        funcs=self.helpers(env)
        panel=dict(currDDOperation=dict(failedOperation=lambda:calls.append('restore')),dropEnabled=False)
        box=dict(__tgFreeQuantity=True,__tgQuantityOwner=panel,removeEventListener=lambda *args:None)
        funcs['__tgQuantityCancel'].invoke(panel,[dict(target=box)])
        funcs['__tgQuantityCancel'].invoke(panel,[dict(target=box)])
        self.assertEqual(calls,['exchange','restore'])
        self.assertTrue(panel['dropEnabled'])
        self.assertIsNone(panel['currDDOperation'])

    def test_copy_weapon_drag_buys_one_without_opening_quantity_window(self):
        calls=[]
        env=dict(_global=dict(__tgActive=True),
                 lol=dict(core=dict(objects=dict(Item=dict(FIRE_ARM=2,COLD_ARM=3,WEAR=1,AMMO=4)))))
        funcs=self.helpers(env)
        env['_global']['__tgIsCopy']=lambda item: True
        env['_global']['__tgBuyFree']=lambda *args: calls.append(args)
        for root in (1,2,3):
            item=dict(typeID=54000,rootID=root)
            trade={}
            funcs['__tgTradeBuy'].invoke(trade,[item,20])
            self.assertEqual(calls[-1],(trade,item,1))
        self.assertEqual(len(calls),3)

    def test_copy_rarity_art_uses_native_gold_and_premium_links_at_zero_price(self):
        calls=[]
        env=dict(_global=dict(__tgActive=True,__tgLines={54000:'G',54001:'P'}),
                 lol=dict(core=dict(objects=dict(Item=dict(HEAL_ITEM=5,AMMO=4,QUEST=6,WEAR=1)))))
        funcs=self.helpers(env)
        view=dict(item=dict(typeID=54000),bg_mc=dict(attachMovie=lambda *args: calls.append(args)),groupItem=False)
        funcs['__tgBack'].invoke(view,[2])
        self.assertEqual(calls[-1][0],'fireArmBG_gold')
        view['item']['typeID']=54001
        funcs['__tgBack'].invoke(view,[1])
        self.assertEqual(calls[-1][0],'wearBG_premium')

    def test_no_manual_save_or_unavailable_specialization_controls(self):
        self.assertNotRegex(client.SOURCE,r'__tgButton\([^\n]+"(?:save|load|saveRules|loadRules|slot)"')
        self.assertIn('while i < 17:',client.SOURCE)
        self.assertIn('lol.core.SceneShifter.closeWindow("support")',client.SOURCE)

    def test_all_prototype_hooks_match_existing_game_methods(self):
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        root = Path(__file__).resolve().parents[1] / 'recon/as-src/lol'
        for path, method, _, params, body in package['wraps']:
            with self.subTest(path=path, method=method):
                source = (root.joinpath(*path).with_suffix('.as')).read_text(encoding='utf-8')
                match = re.search(r'function\s+' + re.escape(method) + r'\(([^)]*)\)', source)
                self.assertIsNotNone(match)
                native = [part for part in match[1].split(',') if part.strip()]
                self.assertEqual(len(params), len(native))
                self.assertTrue(body.assemble())

    def test_spawn_selection_sends_only_index_and_rebuilds_from_server_state(self):
        messages = []
        class Message:
            def __init__(self, op):
                self.data = dict(op=op)
            def addProp(self, name, value):
                self.data[name] = value
        env = dict(_global=dict(__tgPanel={},
                               __tgSend=Message,
                               __tgTransmit=lambda m: messages.append(m.data)),
                   Number=int)
        funcs = self.helpers(env)
        env['_global']['__tgSend'] = Message
        env['_global']['__tgTransmit'] = lambda m: messages.append(m.data)
        funcs['__tgClick'].invoke(dict(__op='spawn', __value=1), [])
        self.assertEqual(messages, [dict(op='spawn', spawn_point=1)])
        self.assertNotIn('p.distance.text', client.SOURCE)
        self.assertIn('m.addProp("spawn_point", _global.__tgSpawnPoint)', client.SOURCE)

    def test_confirmed_spawn_updates_caption_distance_and_closes_dropdown(self):
        events = []
        env = dict(_global=dict(__tgSpawnLabels=['Ближняя', 'Средняя', 'Дальняя'],
                               __tgSpawnPoint=1, __tgDistance=14), String=str)
        funcs = self.helpers(env)
        panel = dict(spawn=dict(caption=dict(text='old')), distanceInfo=dict(text='old'),
                     spawns=dict(removeMovieClip=lambda: events.append('closed')))
        funcs['__tgSpawnState'].invoke(None, [panel])
        self.assertEqual(panel['spawn']['caption']['text'], 'Средняя ▼')
        self.assertEqual(panel['distanceInfo']['text'], 'Расстояние: около 14 гексов')
        self.assertEqual(events, ['closed'])
        funcs['__tgSpawnState'].invoke(None, [{}])

    def test_local_presets_are_scoped_by_endpoint_character_and_slot(self):
        keys = []
        env = dict(_global=dict(__tgLocalSlot=1, __hcEndpoint='local', __tgOwner='Tester12',
                               __hcEncode=lambda value: value), String=str,
                   SharedObject=dict(getLocal=lambda key: keys.append(key)))
        funcs = self.helpers(env)
        funcs['__tgPresetStore'].invoke(None, [])
        env['_global']['__tgLocalSlot'] = 2
        funcs['__tgPresetStore'].invoke(None, [])
        env['_global']['__tgOwner'] = 'Tester13'
        funcs['__tgPresetStore'].invoke(None, [])
        env['_global']['__hcEndpoint'] = 'other-server'
        funcs['__tgPresetStore'].invoke(None, [])
        self.assertEqual(len(set(keys)), 4)
        self.assertTrue(all(key.startswith('lavaTrainingPresets_v1_') for key in keys))

    def test_local_load_is_draft_only_and_corrupt_rules_leave_current_preset(self):
        sent, built = [], []
        player = dict(skills='0,12,0,0,0', specs=','.join(['-1'] * 15), gear='')
        values = '1,1,1,1,1,2,1,1,1,25,1,0'
        data = dict(player=player, enemy=dict(player), rules=values)
        env = dict(_global=dict(__tgPlayer=dict(player), __tgEnemy=dict(player),
                               __tgPanel=dict(status=dict(text='')), __tgRuleDraftValues='old'),
                   SharedObject={}, String=str)
        funcs = self.helpers(env)
        env['_global']['__tgPresetStore'] = lambda: dict(data=data)
        env['_global']['__tgBuild'] = lambda: built.append(True)
        env['_global']['__tgTransmit'] = lambda m: sent.append(m)
        funcs['__tgLoad'].invoke(None, [])
        self.assertEqual(env['_global']['__tgRuleDraftValues'], values)
        self.assertEqual(built, [True])
        self.assertEqual(sent, [])
        data['rules'] = 'x' * 257
        funcs['__tgLoad'].invoke(None, [])
        self.assertEqual(env['_global']['__tgRuleDraftValues'], values)
        self.assertEqual(built, [True])

    def test_manual_save_flushes_player_enemy_and_rule_draft_together(self):
        writes = []
        values = '1,1,1,1,1,1.5,1,1,1,0,1,0'
        player = dict(skills='0,12,0,0,0', specs=','.join(['-1'] * 15), gear='')
        data = {}
        env = dict(_global=dict(__tgPlayer=dict(player), __tgEnemy=dict(player),
                               __tgRuleDraftValues=values, __tgPanel=dict(status=dict(text=''))))
        funcs = self.helpers(env)
        env['_global']['__tgPresetStore'] = lambda: dict(data=data, flush=lambda: writes.append(True))
        funcs['__tgSave'].invoke(None, [])
        self.assertEqual(data['rules'], values)
        self.assertEqual(data['player'], player)
        self.assertEqual(data['enemy'], player)
        self.assertEqual(writes, [True])

    def test_start_requires_applying_loaded_rules_first(self):
        env = dict(_global=dict(__tgPanel=dict(status=dict(text='')), __tgTab='rules',
                               __tgRuleDraftValues='pending', __tgRuleValues='current'))
        funcs = self.helpers(env)
        env['_global']['__tgDraft'] = lambda tab: None
        funcs['__tgClick'].invoke(dict(__op='start', __value=''), [])
        self.assertIn('Сначала примените правила', env['_global']['__tgPanel']['status']['text'])

    def test_profile_and_button_objects_use_literal_field_names(self):
        import ast
        tree = ast.parse(client.SOURCE)
        count = 0
        for obj in ast.walk(tree):
            if isinstance(obj, ast.Dict):
                for key in obj.keys:
                    self.assertIsInstance(key, ast.Constant)
                    self.assertIsInstance(key.value, str)
                    count += 1
        self.assertGreater(count, 15)

    def helpers(self, env):
        from avm_test import Function
        functions = {}
        for name, args, body in client.patches(widescreen.Asm, widescreen.UNDEF)['globals']:
            fn = Function(args, body.assemble(), env)
            env['_global'][name] = functions[name] = fn
        return functions

    def test_catalogue_ignores_late_reply_from_another_post_or_page(self):
        env = dict(_global=dict(__tgPanel=dict(page={}), __tgContext='shotguns',
                               __tgCatalogueRequest=8))
        funcs = self.helpers(env)
        funcs['__tgList'].invoke(None, [dict(context='pistols', request_id=8)])
        funcs['__tgList'].invoke(None, [dict(context='shotguns', request_id=7)])
        self.assertEqual(env['_global']['__tgPanel'], dict(page={}))

    def test_thumbnail_is_fitted_once_and_listener_detached(self):
        calls = []
        env = dict(_global={}, Math=dict(min=min))
        funcs = self.helpers(env)
        icon = dict(display_mc=dict(_width=200, _height=100),
                    removeEventListener=lambda *args: calls.append(args))
        funcs['__tgThumbReady'].invoke(None, [dict(target=icon)])
        self.assertEqual((icon['_xscale'], icon['_yscale']), (24, 24))
        self.assertEqual(len(calls), 1)

    def test_page_cleanup_detaches_pending_icon_callbacks(self):
        calls = []
        icon = dict(src=dict(removeEventListener=lambda *args: calls.append('source')),
                    mcl_list=dict(onLoadInit='pending'),
                    removeEventListener=lambda *args: calls.append('completed'))
        cards = dict(row0=dict(icon=icon), removeMovieClip=lambda: calls.append('removed'))
        env = dict(_global={}, String=str)
        funcs = self.helpers(env)
        funcs['__tgReleaseRows'].invoke(None, [dict(cards=cards)])
        self.assertEqual(calls, ['completed', 'source', 'removed'])
        self.assertIsNone(icon['mcl_list']['onLoadInit'])

    def test_normal_trade_keeps_native_buy_and_sell_checks(self):
        calls = []
        item = dict(id='ordinary', typeID=26075)
        env = dict(Boolean=bool, _global=dict(__tgActive=False, __tgCopies={54000: 26075}))
        funcs = self.helpers(env)
        owner = dict(__tgTradeBuyOrig=lambda *args: calls.append(('buy', args)),
                     __tgCheckSellOrig=lambda arg: 'native refusal')
        funcs['__tgTradeBuy'].invoke(owner, [item, 3])
        self.assertEqual(calls, [('buy', (item, 3))])
        self.assertEqual(funcs['__tgCheckSell'].invoke(owner, [item]), 'native refusal')
        env['_global']['__tgActive'] = True
        self.assertIsNone(funcs['__tgCheckSell'].invoke(owner, [dict(id='copy', typeID=54000)]))

    def test_training_price_override_is_zero_without_changing_normal_prices(self):
        shown = []
        env = dict(String=str,_global=dict(__tgActive=True, __tgCopies={54000: 26075}))
        funcs = self.helpers(env)
        view = dict(mainCost=42, attachIconEnabled=True, __tgShowCostOrig=lambda *args: None,
                    price_mc=dict(gotoAndStop=lambda frame: shown.append(frame),
                                  fontContainer=dict(showValue=shown.append)))
        funcs['__tgShowCost'].invoke(view, [dict(typeID=26075), 'right'])
        self.assertEqual((view['mainCost'], shown), (42, []))
        funcs['__tgShowCost'].invoke(view, [dict(typeID=54000), 'right'])
        self.assertEqual(view['mainCost'], 0)
        self.assertEqual(shown, [1, '0'])

    def test_reference_gold_price_is_visible_without_changing_payable_cost(self):
        shown=[]
        env=dict(String=str,Number=float,Math=dict(floor=__import__("math").floor),_global=dict(__tgActive=True,__tgCopies={54000:26075},
                 __tgPrices={54000:dict(cost=50000,gold=1250)}))
        funcs=self.helpers(env)
        view=dict(mainCost=99,attachIconEnabled=True,showHeapCount=False,__tgShowCostOrig=lambda *args:None,
                  price_mc=dict(gotoAndStop=lambda frame:shown.append(frame),fontContainer=dict(showValue=shown.append)))
        funcs['__tgShowCost'].invoke(view,[dict(typeID=54000),'right'])
        self.assertEqual(shown,[2,'12.5'])
        self.assertEqual(view['mainCost'],0)
        self.assertEqual(env['_global']['__tgPrices'][54000],dict(cost=50000,gold=1250))

    def test_battery_pack_price_is_displayed_as_ten_thousand_per_piece(self):
        env=dict(String=str,Number=float,Math=dict(floor=__import__('math').floor),
                 _global=dict(__tgPrices={54000:dict(cost=200000,gold=0,pack=20)}))
        funcs=self.helpers(env)
        price=funcs['__tgReferencePrice'].invoke(None,[dict(typeID=54000)])
        self.assertEqual(price,dict(value=10000,gold=False))

    def test_reference_afro_stack_price_and_tooltip_both_state_free_trade(self):
        from avm_test import Arr
        shown=[]
        env=dict(String=str,Number=float,Math=dict(floor=__import__("math").floor),_global=dict(__tgActive=True,__tgCopies={54000:123},
                 __tgPrices={54000:dict(cost=2,gold=0)}))
        funcs=self.helpers(env)
        item=dict(typeID=54000,getProp=lambda key:50 if key=='size' else None)
        view=dict(mainCost=9,attachIconEnabled=False,showHeapCount=True,__tgShowCostOrig=lambda *args:None,
                  price_mc=dict(gotoAndStop=lambda frame:None,fontContainer=dict(showValue=shown.append)))
        funcs['__tgShowCost'].invoke(view,[item,'right'])
        self.assertEqual(float(shown[-1][1:]),100)
        self.assertEqual(shown[-1][0],'a')
        self.assertEqual(view['mainCost'],0)
        rows=Arr()
        funcs['__tgAnnotationPrice'].invoke(dict(item=item),[rows])
        self.assertEqual(len(rows),2)
        self.assertIn('за 1 шт.',rows[0][0])
        self.assertEqual(rows[1][1],'получение и сдача бесплатно')

    def test_closing_trade_detaches_quantity_callbacks_and_late_cancel_is_ignored(self):
        calls = []
        env = dict(_global={},lol=dict(core=dict(SceneShifter=dict(closeWindow=lambda name:calls.append('window closed')))))
        funcs = self.helpers(env)
        box = dict(removeEventListener=lambda *args: calls.append(args[0]))
        trade = dict(__tgPurchaseItem='copy', __tgPurchaseBox=box,
                     __tgTradeKillOrig=lambda: calls.append('native kill'),
                     applyTransfer=lambda success: calls.append(success))
        funcs['__tgTradeKill'].invoke(trade, [])
        self.assertEqual(calls, ['exchange', 'close', 'window closed', 'native kill'])
        self.assertIsNone(trade['__tgPurchaseItem'])
        funcs['__tgTradeCancel'].invoke(trade, [dict(target=box)])
        self.assertNotIn(False, calls)

    def test_free_quantity_confirmation_sends_one_request_and_detaches_callbacks(self):
        calls = []
        env = dict(_global=dict(__tgActive=True),
                   lol=dict(core=dict(SceneShifter=dict(closeWindow=lambda name: calls.append(name)))))
        funcs = self.helpers(env)
        env['_global']['__tgBuyFree'] = lambda *args: calls.append(args)
        box = dict(removeEventListener=lambda *args: None)
        item = dict(typeID=54000, tradeID=0)
        trade = dict(__tgPurchaseItem=item, __tgPurchaseBox=box,
                     applyTransfer=lambda success: calls.append(success))
        funcs['__tgTradeQuantity'].invoke(trade, [dict(target=box, right=4)])
        self.assertEqual(calls, ['exchange', (trade, item, 4)])
        funcs['__tgTradeQuantity'].invoke(trade, [dict(target=box, right=4)])
        self.assertEqual(len([call for call in calls if isinstance(call, tuple)]), 1)

    def test_free_quantity_cancel_restores_drag_without_money_error(self):
        from avm_test import Arr
        calls = []
        env = dict(_global={})
        funcs = self.helpers(env)
        panel = dict(trade=dict(__tgCancelledFree=True),
                     ddOperation_arr=Arr([dict(failedOperation=lambda: calls.append('restore'))]),
                     __tgTradeErrorOrig=lambda: calls.append('money error'))
        funcs['__tgTradeError'].invoke(panel, [])
        self.assertEqual(calls, ['restore'])
        panel['trade']['__tgCancelledFree'] = False
        funcs['__tgTradeError'].invoke(panel, [])
        self.assertEqual(calls, ['restore', 'money error'])

    def test_center_and_clamp_use_original_movie_origin(self):
        env = dict(_global={}, Stage=dict(width=1920, height=1080),
                   Math=dict(round=round, max=max, min=min),
                   lol=dict(core=dict(SceneShifter=dict(_ref=dict(minW=950, minH=650)))))
        funcs = self.helpers(env)
        panel = dict(__w=1040, __h=640, _x=0, _y=0)
        funcs['__tgLayout'].invoke(None, [panel, True])
        self.assertEqual((panel['_x'], panel['_y']), (-45, 5))
        panel.update(_x=9999, _y=-9999)
        funcs['__tgLayout'].invoke(None, [panel, False])
        self.assertEqual((panel['_x'], panel['_y']), (387, -207))

    def test_training_and_restore_snapshots_do_not_emit_xp_but_real_gains_do(self):
        env = dict(_global=dict(__tgActive=True))
        funcs = self.helpers(env)
        messages, values = [], []
        attrs = dict(__progressLoaded=True)
        def native(obj):
            values.append(obj['xp'])
            if attrs['__progressLoaded']:
                messages.append(obj['xp'])
            attrs['__progressLoaded'] = True
        attrs['__tgStatsOrig'] = native
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=0)])
        env['_global'].update(__tgActive=False, __tgSnapshotPending=True)
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=10398)])
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=10418)])
        self.assertEqual(values, [0, 10398, 10418])
        self.assertEqual(messages, [10418])
        self.assertFalse(env['_global']['__tgSnapshotPending'])

    def test_equipment_is_refreshed_once_per_clone_revision_after_loading(self):
        from avm_test import Arr
        class IDs(Arr):
            def join(self, sep):
                return sep.join(self)
        calls = []
        gamer = dict(equipment=dict(getStuff=lambda *args: calls.append(args)),
                     apManager=dict(setAP=lambda *args: None))
        env = dict(_global={}, lol=dict(core=dict(Master=dict(getInstance=lambda: dict(gamer=gamer)))))
        funcs = self.helpers(env)
        v = dict(loaded=0, live_oids=IDs(['copy-1']), regen=2.5, ap=136)
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [])
        v['loaded'] = 1
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [(11, 0)])
        v['live_oids'] = IDs(['copy-2'])
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [(11, 0), (11, 0)])

    def test_exit_zones_removed_only_from_private_training_descriptions(self):
        info = dict(zones=[dict(x=1, y=2)], pvpEnabled=False)
        env = dict(_global={})
        funcs = self.helpers(env)
        parser = dict(__tgParseOrig=lambda doc: dict(info))
        ordinary = funcs['__tgParse'].invoke(parser, [None])
        self.assertEqual(ordinary, info)
        env['_global']['__tgActive'] = True
        private = funcs['__tgParse'].invoke(parser, [None])
        self.assertEqual(private['zones'], [])
        self.assertTrue(private['pvpEnabled'])
        self.assertEqual(info['zones'], [dict(x=1, y=2)])

    def test_return_refreshes_real_equipment_after_native_location_entry(self):
        calls = []
        env = dict(_global=dict(__tgReturnEquipment=True, __rfRepairKeys=lambda: True))
        funcs = self.helpers(env)
        owner = dict(__tgEnterOrig=lambda obj: calls.append('entered'),
                     gamer=dict(equipment=dict(getStuff=lambda *args: calls.append(args))))
        funcs['__tgEnterWrapper'].invoke(owner, [None])
        funcs['__tgEnterWrapper'].invoke(owner, [None])
        self.assertEqual(calls, ['entered', (11, 0), 'entered'])
        self.assertFalse(env['_global']['__tgReturnEquipment'])

    def test_managed_full_bag_snapshot_replaces_old_rows_with_native_removal_events(self):
        import math
        from avm_test import Arr
        removed, detached = [], []
        old = [dict(id='real-old'), dict(id='training-old')]
        for item in old:
            item['removeEventListener'] = lambda *args: detached.append(args)
        bag = dict(itemList=Arr(old))
        fresh = dict(id='real-current')
        eq = dict(isGamer=True, __tgManaged=True, __tgReplaceBag=True, bag=bag, slots_arr=Arr(), action_arr=Arr())
        def remove(slot, item):
            self.assertIs(slot, bag)
            self.assertEqual(bag['itemList'], [])
            removed.append(item['id'])
        def native(obj):
            bag['itemList'].append(fresh)
        eq.update(removeItem=remove, __tgEquipOrig=native)
        env = dict(_global=dict(__tgActive=False), Number=float, Math=dict(floor=math.floor))
        funcs = self.helpers(env)
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=11)])
        self.assertEqual(removed, ['real-old', 'training-old'])
        self.assertEqual(len(detached), 2)
        self.assertEqual(bag['itemList'], [fresh])
        self.assertEqual([i['id'] for i in old], ['real-old', 'training-old'])

    def test_late_snapshot_cannot_replace_bag_after_training_boundary(self):
        received = []
        env = dict(_global=dict(__tgEpoch=3), Boolean=bool)
        funcs = self.helpers(env)
        eq = dict(ss_ack=received.append)
        funcs['__tgSnapshotAck'].invoke(eq, [dict(data=dict(mask=11, epoch=2), param=dict(o_list=['copy']))])
        self.assertEqual(received, [])
        funcs['__tgSnapshotAck'].invoke(eq, [dict(data=dict(mask=11, epoch=3), param=dict(o_list=['real']))])
        self.assertEqual(received, [dict(data=11, param=dict(o_list=['real']))])

    def test_late_item_initialization_cannot_reinsert_retired_training_copy(self):
        calls, detached = [], []
        item = dict(id='copy-old', typeID=54000, removeEventListener=lambda *args: detached.append(args))
        eq = dict(isGamer=True, __tgManaged=True, __tgBagUpdateOrig=calls.append)
        env = dict(_global=dict(__tgActive=False, __tgCopies={54000:26075}, __tgLive={}), Boolean=bool)
        funcs = self.helpers(env)
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [])
        self.assertEqual(len(detached), 1)
        env['_global']['__tgActive'] = True
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [])
        env['_global']['__tgLive']['copy-old'] = True
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [dict(target=item)])

    def test_ordinary_snapshot_after_training_does_not_rebuild_bag(self):
        from avm_test import Arr
        bag = dict(itemList=Arr([dict(id='real-item')]))
        called = []
        eq = dict(isGamer=True, __tgManaged=True, bag=bag, __tgEquipOrig=lambda obj: called.append(obj))
        funcs = self.helpers(dict(_global={}))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=11)])
        self.assertEqual(bag['itemList'], [dict(id='real-item')])
        self.assertEqual(len(called), 1)

    def test_partial_equipment_snapshot_keeps_bag(self):
        import math
        from avm_test import Arr
        bag = dict(itemList=Arr([dict(id='kept')]))
        eq = dict(isGamer=True, __tgManaged=True, __tgReplaceBag=True, bag=bag, slots_arr=Arr(), action_arr=Arr(), __tgEquipOrig=lambda obj: None)
        funcs = self.helpers(dict(_global={}, Number=float, Math=dict(floor=math.floor)))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=3)])
        self.assertEqual(bag['itemList'], [dict(id='kept')])

    def test_replacement_clears_empty_wear_and_hand_slots_before_native_snapshot(self):
        import math
        from avm_test import Arr
        removed = []
        primary = dict(item=dict(id='old-primary'))
        secondary = dict(item=dict(id='old-secondary'))
        helmet = dict(item=dict(id='old-helmet'))
        eq = dict(isGamer=True, __tgReplaceBag=True,
                  slots_arr=Arr([helmet]), action_arr=Arr([primary, secondary]))
        def remove(slot, item):
            removed.append(item['id'])
            slot['item'] = None
        def native(obj):
            self.assertIsNone(primary['item'])
            self.assertIsNone(secondary['item'])
            self.assertIsNone(helmet['item'])
        eq.update(removeItem=remove, __tgEquipOrig=native)
        funcs = self.helpers(dict(_global={}, Number=float, Math=dict(floor=math.floor)))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=3)])
        self.assertEqual(removed, ['old-helmet', 'old-primary', 'old-secondary'])

    def test_closing_terminal_releases_only_its_filter_and_repairs_keys(self):
        events = []
        panel = dict(stopDrag=lambda: events.append('stop'), removeMovieClip=lambda: events.append('remove'))
        env = dict(_global=dict(__tgPanel=panel, __rfRepairKeys=lambda: events.append('keys')),
                   Stage=dict(removeListener=lambda p: events.append('stage')),
                   lol=dict(core=dict(SceneShifter=dict(hotKeyManager=dict(removeFilter=lambda key: events.append(key)))),
                            gpui=dict(HintManager=dict(closeHint=lambda: events.append('hint')))))
        funcs = self.helpers(env)
        funcs['__tgClose'].invoke(None, [])
        self.assertEqual(events, ['stop', 'stage', 'remove', 'tg', 'keys', 'hint'])
        self.assertIsNone(env['_global']['__tgPanel'])

    def test_whole_client_injection_builds_with_new_helpers(self):
        payload = widescreen.injected()
        self.assertIn(b'__tgInstall', payload)
        self.assertIn(b'__tgForgetItems', payload)
        self.assertTrue('Компьютер полигона'.encode('utf-8') in payload, 'Sandbox title missing from injection')
        # A native DoAction is used; no browser or command-line UI dependency.
        self.assertNotIn(b'ExternalInterface', client.SOURCE.encode('utf-8'))


    def test_compiled_copy_guard_never_labels_normal_items_or_prototypes(self):
        from avm_test import execute
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        _, _, body = next(row for row in package['globals'] if row[0] == '__tgIsCopy')
        for item, expected in ((None, False), ({'id': 0, 'typeID': 54000}, False),
                               ({'id': 'abcd65db00', 'uID': float('nan'), 'typeID': 26075}, False),
                               ({'id': '10000000000d2f000', 'typeID': 54000}, True)):
            env = dict(item=item, Boolean=bool, _global={'__tgCopies': {54000: 26075}})
            self.assertEqual(execute(body.assemble(), env), expected)


    def test_trade_card_is_named_before_native_quantity_and_display_initialization(self):
        item=dict(id='model7',typeID=54000)
        proto=dict(name='machine_gun_2_lvl_18_mod_precision_pm$service')
        env=dict(_global=dict(__tgCopies={54000:40175},__tgLabels={54000:'M60 (P) · Точность'}),
                 Boolean=bool,lol=dict(core=dict(objects=dict(ItemFactory=dict(getProtoItem=lambda t:proto)))))
        funcs=self.helpers(env)
        seen=[]
        owner=dict(item=item,__tgTradeParamsOrig=lambda:seen.append(item.get('_name')))
        funcs['__tgTradeParams'].invoke(owner,[])
        self.assertEqual(seen,['M60 (P) · Точность$service'])

    def test_icon_alias_uses_exact_model_for_copy_but_does_not_change_real_icon(self):
        called=[]
        env=dict(_global=dict(__tgActive=False,__tgCopies={54000:40175},
                             __tgIcons={54000:25057,40175:25057}))
        funcs=self.helpers(env)
        owner=dict(__tgIconOrig=lambda t:called.append(t) or t)
        self.assertEqual(funcs['__tgIcon'].invoke(owner,[54000]),25057)
        self.assertEqual(funcs['__tgIcon'].invoke(owner,[40175]),40175)
        env['_global']['__tgActive']=True
        self.assertEqual(funcs['__tgIcon'].invoke(owner,[40175]),25057)
        self.assertEqual(called,[25057,40175,25057])

    def test_exit_pending_closes_native_quest_UI_and_stops_its_polling_before_ack(self):
        from avm_test import Arr
        events=[]
        inspector=dict(updateTimerID=77,updateNPCList=Arr([1]),lockUpdate=False,currentQuests={'old':'still needed by takeAck'})
        panel=dict(takeAck='pending success redraw')
        inspector['removeEventListener']=lambda *args:events.append(('detach',)+args)
        env=dict(_global={},clearInterval=lambda t:events.append(('timer',t)),
                 lol=dict(core=dict(SceneShifter=dict(closeWindow=lambda *args:events.append(args),
                     _ref=dict(UIPanels=dict(quests=dict(instance=dict(content=panel))))),
                     quests=dict(QuestInspector=dict(getInstance=lambda:inspector)))))
        funcs=self.helpers(env)
        env['_global']['__tgClose']=lambda:events.append(('panel',))
        funcs['__tgExitPending'].invoke(None,[])
        self.assertEqual(events[0],('detach','update',panel,'pending success redraw'))
        self.assertEqual(events[1:4],[('quests',),('questInfo',),('annotation','all')])
        self.assertTrue(inspector['lockUpdate'])
        self.assertEqual(inspector['updateNPCList'],[])
        self.assertEqual(inspector['currentQuests'],{'old':'still needed by takeAck'})

    def test_cleanup_is_bounded_when_a_callback_adds_or_reenters_item_cleanup(self):
        from avm_test import Arr
        deleted=[]
        new=dict(id='new',typeID=54001)
        env=dict(_global=dict(__tgObjects=Arr(),__tgLive={}),
                 lol=dict(core=dict(Master=dict(getInstance=lambda:dict(gamer=dict(equipment={}))),
                    objects=dict(ItemFactory=dict(callCount=0,callStack=Arr(),
                        getProtoItem=lambda t:dict(removeEventListener=lambda *args:None)))),
                    utils=dict(StringCollector=dict(getInstance=lambda:dict(removeEventListener=lambda *args:None)))))
        funcs=self.helpers(env)
        env['_global']['__tgDeleteItem']=deleted.append
        def callback(*args):
            env['_global']['__tgObjects'].append(new)
            funcs['__tgForgetItems'].invoke(None,[True])
        old=dict(id='old',typeID=54000,removeEventListener=callback)
        env['_global']['__tgObjects'].append(old)
        funcs['__tgForgetItems'].invoke(None,[True])
        self.assertEqual(deleted,['old'])
        self.assertEqual(env['_global']['__tgObjects'],[new])
        self.assertFalse(env['_global']['__tgForgetting'])


if __name__ == '__main__':
    unittest.main()
