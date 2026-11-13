"""Execute emitted Shift/Esc bytecode; rendering and OS focus are separate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import Arr, Function
from inventory_controls_client import patches
from bank_client import patches as bank_patches
from gold_commerce_client import patches as gold_patches
from testkit import run_cases


class InventoryControls(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.windows = {name: dict(instance=None) for name in (
            'exchange', 'query', 'queryTradeItem', 'queryDeleteItem',
            'queryWithCheckBox', 'alert', 'trade')}
        self.keys = dict(hotKeyFilter_arr=Arr(['equipment']),
                         checkFilter=lambda name: self.keys['hotKeyFilter_arr'][-1] == name)
        self.events = dict(ESC='ESC', CANCEL='CANCEL', SHIFT_SELECT='shift', CTRL='ctrl', SHIFT='shift-key')
        self.env = dict(_global={}, String=str, Key=dict(isDown=lambda code: code == 16),
                        lol=dict(core=dict(SceneShifter=dict(_ref=dict(UIPanels=self.windows),
                                                            hotKeyManager=self.keys)),
                                 services=dict(HotKeyEvent=self.events),
                                 gpui=dict(ItemContainer=self.events,
                                           AnnotationManager=dict(clear=lambda: None))))
        spec = patches(w.Asm, w.UNDEF)
        self.functions = {}
        for name, args, body in spec['globals']:
            fn = Function(args, body.assemble(), self.env)
            self.functions[name] = self.env['_global'][name] = fn
        for path, method, keep, args, body in spec['wraps']:
            self.functions[(path[-1], method)] = Function(args, body.assemble(), self.env)

    def call(self, cls, method, target, *args):
        return self.functions[(cls, method)].invoke(target, args)

    def card(self):
        return dict(item=dict(id='one', inited=True), clickFlag=True,
                    clickTimer=dict(Clear=lambda: self.calls.append('clear-timer')))

    def owner(self, cls='EquipInterface'):
        bag = dict(clearSelectList=lambda: self.calls.append('clear-selection'))
        panel = dict(bag_mc=bag, visavisBag_mc={}, __icDead=False, ddOperation_arr=Arr())
        bag['__icOwner'] = panel
        helper = '__icEquipDoubleOrig' if cls == 'EquipInterface' else '__ic' + cls + 'doubleClickOrig'
        panel[helper] = lambda event: self.calls.append(event)
        panel['doubleClick'] = lambda event: self.call(cls, 'doubleClick', panel, event)
        return panel, bag

    def test_shift_routes_own_bag_to_native_equip_or_sale_without_drag(self):
        for cls in ('EquipInterface', 'TradeInterface'):
            with self.subTest(cls=cls):
                self.calls.clear()
                panel, bag = self.owner(cls)
                card = self.card()
                card['__icBag'] = bag
                self.call('BagInterface', 'shiftSelect', bag, dict(target=card))
                self.assertIs(self.calls[-1]['target'], bag)
                self.assertIs(self.calls[-1]['item_mc'], card)
                self.assertFalse(card['clickFlag'])

    def test_native_release_is_not_also_double_click_and_does_not_start_drag(self):
        panel, bag = self.owner()
        card = self.card()
        card.update(__icBag=bag, price_mc={},
                    __icReleaseOrig=lambda: self.fail('native double-click must not also run'),
                    __icPressOrig=lambda: self.fail('Shift must not start drag'),
                    dispatch=lambda event: self.calls.append(event['type']))
        self.call('ItemContainer', 'onPressBg', card)
        self.assertIsNone(card['onMouseMove'])
        for _ in range(2):
            self.call('ItemContainer', 'onReleaseBg', card)
        self.assertEqual(self.calls, ['clear-timer', 'shift', 'shift'])
        self.assertFalse(card['clickFlag'])

    def test_plain_click_and_npc_stock_keep_native_behavior(self):
        card = self.card()
        card.update(__icBag={}, __icPressOrig=lambda: self.calls.append('press'),
                    __icReleaseOrig=lambda: self.calls.append('release'))
        self.call('ItemContainer', 'onPressBg', card)
        self.call('ItemContainer', 'onReleaseBg', card)
        self.assertEqual(self.calls, ['press', 'release'])

    def test_shift_unequips_each_owned_slot_once_until_ack(self):
        for slot_id in ('primary', 'secondary', 'head', 'armor', 'camouflage', 'legs', 'boots', 'belt'):
            with self.subTest(slot=slot_id):
                self.calls.clear()
                panel, bag = self.owner()
                card = self.card()
                slot = dict(id=slot_id, item_mc=card, __icEquipOwner=panel)
                card.update(__icSlot=slot, price_mc={},
                            __icPressOrig=lambda: self.fail('Shift must not start dragging'),
                            __icReleaseOrig=lambda: self.fail('Shift must not also double click'),
                            dispatch=lambda event: self.fail('slot must not enter bag selection'))
                def set_from(*args):
                    self.calls.append(('from', args))
                    card['blockFlag'] = True
                operation = dict(setFrom=set_from, setTo=lambda *args: self.calls.append(('to', args)))
                self.env['lol']['gpui']['DDOperation'] = lambda: operation
                def submit():
                    self.calls.append('server-validated-transfer')
                    panel['ddOperation_arr'].append(panel['currDDOperation'])
                    panel['currDDOperation'] = None
                panel['sendTransferToServer'] = submit
                self.call('ItemContainer', 'onPressBg', card)
                self.call('ItemContainer', 'onReleaseBg', card)
                self.call('ItemContainer', 'onReleaseBg', card)
                self.assertEqual([c for c in self.calls if c == 'server-validated-transfer'],
                                 ['server-validated-transfer'])
                self.assertIn(('from', (card['item'], slot, card)), self.calls)
                self.assertIn(('to', (None, bag)), self.calls)
                self.assertFalse(card['clickFlag'])
                self.assertIsNone(card['onMouseMove'])
                self.assertEqual(len(panel['ddOperation_arr']), 1)
                # Once acknowledged, another equipped item can be removed.
                panel['ddOperation_arr'].clear()
                card['blockFlag'] = False
                self.call('ItemContainer', 'onReleaseBg', card)
                self.assertEqual(self.calls.count('server-validated-transfer'), 2)

    def test_equipment_slot_binding_follows_init_new_cards_remove_and_kill(self):
        panel, bag = self.owner()
        card = self.card()
        slot = dict(item_mc=card)
        panel.update(outfitInterface=dict(head_mc=slot),
                     __icEquipInitOrig=lambda: self.calls.append('init'),
                     __icEquipKillOrig=lambda: self.calls.append('kill'))
        self.call('EquipInterface', 'init', panel)
        self.assertIs(slot['__icEquipOwner'], panel)
        self.assertIs(card['__icSlot'], slot)
        slot['__icSlotRemoveOrig'] = lambda: self.calls.append('remove')
        self.call('SlotPan', 'removeItem', slot)
        self.assertIsNone(card['__icSlot'])
        replacement = self.card()
        slot['__icSlotAddOrig'] = lambda item: slot.update(item_mc=replacement)
        self.call('SlotPan', 'addItem', slot, replacement['item'])
        self.assertIs(replacement['__icSlot'], slot)
        self.call('EquipInterface', 'kill', panel)
        self.assertIsNone(slot['__icEquipOwner'])
        self.assertIsNone(replacement['__icSlot'])
        self.assertIsNone(bag['__icOwner'])
        self.assertEqual(self.calls, ['init', 'remove', 'kill'])

    def test_shift_slot_rejects_stale_cards_and_closed_busy_or_modal_owner(self):
        for reason in ('stale', 'closed', 'pending', 'modal', 'unloaded'):
            with self.subTest(reason=reason):
                panel, bag = self.owner()
                card = self.card()
                slot = dict(item_mc=card, __icEquipOwner=panel)
                card.update(__icSlot=slot, price_mc={},
                            __icReleaseOrig=lambda: None)
                if reason == 'stale':
                    slot['item_mc'] = self.card()
                if reason == 'closed':
                    panel['__icDead'] = True
                if reason == 'pending':
                    panel['ddOperation_arr'] = Arr([{}])
                if reason == 'modal':
                    self.windows['exchange']['instance'] = dict(content={})
                if reason == 'unloaded':
                    card['item']['inited'] = False
                self.call('ItemContainer', 'onReleaseBg', card)
                self.assertNotIn('currDDOperation', panel)
                self.windows['exchange']['instance'] = None

    def test_unowned_slots_and_plain_equipment_clicks_remain_native(self):
        panel, bag = self.owner()
        card = self.card()
        card.update(__icSlot=dict(item_mc=card),
                    __icPressOrig=lambda: self.calls.append('press'),
                    __icReleaseOrig=lambda: self.calls.append('release'))
        self.call('ItemContainer', 'onPressBg', card)
        self.call('ItemContainer', 'onReleaseBg', card)
        self.env['Key']['isDown'] = lambda code: False
        card['__icSlot']['__icEquipOwner'] = panel
        self.call('ItemContainer', 'onPressBg', card)
        self.call('ItemContainer', 'onReleaseBg', card)
        self.assertEqual(self.calls, ['press', 'release', 'press', 'release'])
        other_slot = dict(item_mc=self.card(), __icSlotAddOrig=lambda item: None)
        self.call('SlotPan', 'addItem', other_slot, card['item'])
        self.assertNotIn('__icSlot', other_slot['item_mc'])

    def test_shift_on_npc_stock_never_becomes_a_double_click_purchase(self):
        card = self.card()
        card.update(__icBag=dict(__icPassiveShift=True), price_mc={},
                    __icReleaseOrig=lambda: self.fail('accidental purchase'),
                    dispatch=lambda event: self.calls.append(event['type']))
        self.call('ItemContainer', 'onReleaseBg', card)
        self.assertEqual(self.calls, ['clear-timer', 'shift'])

    def test_busy_shift_double_click_and_drag_cannot_replace_pending_operation(self):
        for cls in ('EquipInterface', 'TradeInterface', 'BankInterface'):
            for busy in ('ddFlag', 'currDDOperation', 'ddOperation_arr', 'equipment', 'bank', 'trade'):
                with self.subTest(cls=cls, busy=busy):
                    panel, bag = self.owner(cls)
                    card = self.card()
                    card['__icBag'] = bag
                    panel[busy] = (Arr([{}]) if busy == 'ddOperation_arr' else
                                   dict(transferStack=Arr([{}])) if busy in ('equipment', 'bank', 'trade') else True)
                    self.call(cls, 'doubleClick', panel, dict(target=bag, item_mc=card))
                    self.call(cls, 'startDragNDrop', panel, dict(target=bag, item_mc=card))
                    self.assertEqual(self.calls, [])

    def test_stale_blocked_unloaded_and_empty_cards_do_not_start_operations(self):
        panel, bag = self.owner()
        card = self.card()
        for change in (dict(blockFlag=True), dict(item=None), dict(item=dict(inited=False)), {}):
            with self.subTest(change=change):
                candidate = dict(card, **change)  # no binding: retired/moved card
                self.call('BagInterface', 'shiftSelect', bag, dict(target=candidate))
        self.assertEqual(self.calls, [])

    def test_modal_blocks_new_actions_until_cancelled(self):
        panel, bag = self.owner()
        for name in self.windows:
            if name == 'trade':
                continue
            self.windows[name]['instance'] = dict(content={})
            self.call('EquipInterface', 'doubleClick', panel, dict(target=bag, item_mc=self.card()))
            self.windows[name]['instance'] = None
        self.assertEqual(self.calls, [])
        self.call('EquipInterface', 'doubleClick', panel, dict(target=bag, item_mc=self.card()))
        self.assertEqual(len(self.calls), 1)

    def test_bank_shift_still_reaches_existing_quantity_pipeline(self):
        funcs = bank_patches(w.Asm, w.UNDEF)['globals']
        shift = next(Function(args, body.assemble(), self.env) for name, args, body in funcs if name == '__bkShift')
        card = self.card()
        bag = dict(__bkOwner=dict(doubleClick=lambda event: self.calls.append(event)))
        bag['__icShiftOrig'] = lambda event: shift.invoke(bag, [event])
        self.call('BagInterface', 'shiftSelect', bag, dict(target=card))
        self.assertEqual(len(self.calls), 1)
        self.assertIs(self.calls[0]['item_mc'], card)

    def test_range_with_stale_or_filtered_anchor_uses_single_selection(self):
        card = self.card()
        bag = dict(currSelectItem=dict(item=dict(id='removed')),
                   getNumFromSortList=lambda oid: None if oid == 'removed' else 0,
                   select=lambda event: self.calls.append(event),
                   __icRangeOrig=lambda card: self.fail('stale range'))
        self.call('BagInterface', 'itemPressShift', bag, card)
        bag['currSelectItem'] = None
        self.call('BagInterface', 'itemPressShift', bag, card)
        self.assertEqual(self.calls, [dict(target=card)] * 2)

    def test_normal_range_selection_in_other_windows_remains_native(self):
        bag = dict(currSelectItem=dict(item=dict(id='one')), selectGroupAvailable=True,
                   __icShiftOrig=lambda event: self.calls.append('shift'),
                   __icRangeOrig=lambda card: self.calls.append('range'),
                   getNumFromSortList=lambda oid: 0)
        card = self.card()
        self.call('BagInterface', 'shiftSelect', bag, dict(target=card))
        self.call('BagInterface', 'itemPressShift', bag, card)
        self.assertEqual(self.calls, ['shift', 'range'])

    def test_bag_kill_detaches_owners_and_stale_shift_is_inert(self):
        bag = dict(__icOwner={}, __bkOwner={}, __icBagKillOrig=lambda: self.calls.append('kill'))
        self.call('BagInterface', 'kill', bag)
        self.call('BagInterface', 'shiftSelect', bag, dict(target=self.card()))
        self.assertEqual(self.calls, ['kill'])
        self.assertIsNone(bag['__icOwner'])
        self.assertIsNone(bag['__bkOwner'])

    def test_trade_escape_has_its_own_filter_and_does_not_broadcast_cancel(self):
        self.escape('inventoryTrade')
        self.assertEqual(self.calls, ['__icTradeEscape'])
        filters = dict(__icFilterOrig=lambda name: self.calls.append(name) or 'native')
        self.assertEqual(self.call('HotKeyFilter', 'getFilter', filters, 'inventoryTrade'),
                         ['CANCEL', 'ctrl', 'shift-key'])
        self.assertEqual(self.call('HotKeyFilter', 'getFilter', filters, 'persInfo'), 'native')

    def escape(self, top, preferred=None, focus=True):
        self.keys.update(keyStack=Arr([27]), enabled=focus,
                         hotKeyFilter_arr=Arr([top]),
                         hotKeyFilters=dict(getFilter=lambda name: Arr(['CANCEL', 'ESC'])),
                         __icDispatchOrig=lambda event: self.fail('must dispatch exactly one scoped Escape'),
                         dispatchEvent=preferred or (lambda event: self.calls.append(event['type'])))
        def native(suffix):
            # Both orders occur in native enumeration; other event kinds are
            # left to the original dispatcher. Closing changes the live filter.
            for event in ('CANCEL', 'ESC', 'CANCEL'):
                self.call('HotKeyManager', 'checkAndDispatch', self.keys, event)
        self.keys['__icCheckKeysOrig'] = native
        self.call('HotKeyManager', 'checkHotKey', self.keys, '')
        self.assertIsNone(self.keys['__icEscape'])

    def test_one_escape_event_even_if_closing_changes_filter_or_text_has_focus(self):
        for top, want in (('equipment', 'ESC'), ('dialogue', 'CANCEL'), ('quest', 'CANCEL'), ('chat', 'ESC')):
            self.calls.clear()
            def closing(event):
                self.calls.append(event['type'])
                self.keys['hotKeyFilter_arr'] = Arr(['equipment'])
            self.escape(top, closing, focus=False)
            self.assertEqual(self.calls, [want])

    def test_dialogue_escape_does_not_close_bank_skills_quests_or_settings(self):
        def cancel(event):
            # The dialog's native CANCEL callback ran first and removed its
            # filter; underlying CANCEL subscribers still see this broadcast.
            self.keys['hotKeyFilter_arr'] = Arr(['cancel'])
            for cls, method in (('BankInterface', 'close'), ('CharInterface', 'cancel'),
                                ('QuestInterface', 'close'), ('SettingsInterface', 'close')):
                helper = '__ic' + cls + 'CloseOrig'
                self.call(cls, method, {helper: lambda: self.fail('closed underlying window')})
        self.escape('dialogue', cancel)

    def test_equipment_escape_cancels_drag_and_unblocks_entire_group_before_close(self):
        panel = dict(ddFlag=True, dragItemMc=dict(kill=lambda: None, removeMovieClip=lambda: None),
                     currDDOperation=dict(failedOperation=lambda: self.calls.append('unblock-group')),
                     __icEquipEscOrig=lambda: self.calls.append('close'))
        self.call('EquipInterface', 'pressEscKey', panel)
        self.assertEqual(self.calls, ['unblock-group'])
        self.assertIsNone(panel['currDDOperation'])
        self.assertIsNone(panel['onMouseMove'])
        self.call('EquipInterface', 'pressEscKey', panel)
        self.assertEqual(self.calls, ['unblock-group', 'close'])

    def test_chat_escape_does_not_close_inventory(self):
        self.keys['hotKeyFilter_arr'] = Arr(['chat'])
        self.call('EquipInterface', 'pressEscKey', dict(__icEquipEscOrig=lambda: self.fail('inventory closed')))

    def test_trade_init_kill_owns_and_releases_its_subscription(self):
        panel, bag = self.owner('TradeInterface')
        panel.update(__icTradeInitOrig=lambda: None, __icTradeKillOrig=lambda: None)
        for name in ('addFilter', 'addEventListener', 'removeFilter', 'removeEventListener'):
            self.keys[name] = lambda *args, name=name: self.calls.append((name, args))
        self.call('TradeInterface', 'init', panel)
        self.call('TradeInterface', 'kill', panel)
        self.call('TradeInterface', 'kill', panel)
        self.assertEqual([entry[0] for entry in self.calls],
                         ['addFilter', 'addEventListener', 'removeEventListener', 'removeFilter'])
        self.assertIsNone(bag['__icOwner'])
        self.assertEqual(self.calls[0][1], ('inventoryTrade',))
        self.assertEqual(self.calls[-1][1], ('inventoryTrade',))

    def test_cancelled_equipment_warning_does_not_block_next_action(self):
        operation = dict(item='weapon')
        panel = dict(currDDOperation=operation, __icWarningAnswerOrig=lambda event: self.calls.append('native-cancel'))
        self.call('EquipInterface', 'warningAnswer', panel, dict(success=False))
        self.assertIsNone(panel['currDDOperation'])
        self.assertEqual(self.calls, ['native-cancel'])

    def test_hand_items_choose_primary_and_keep_native_requirement_checks(self):
        # Item.as: FIRE_ARM=0, COLD_ARM=5, AMMO=3. Wear and medicine
        # must retain their distinct native equip/use routes.
        for root in (0, 5, 3):
            with self.subTest(root=root):
                self.calls.clear()
                panel, bag = self.owner()
                slot = dict(id='primary', item_mc=dict(item='previous', blockItem=lambda: self.calls.append('block')))
                operation = dict(setFrom=lambda *args: self.calls.append(('from', args)),
                                 setTo=lambda *args: self.calls.append(('to', args)))
                self.env['lol']['gpui']['DDOperation'] = lambda: operation
                panel['outfitInterface'] = dict(prim_mc=slot)
                panel['sendTransferToServer'] = lambda: self.calls.append('native-requirements-and-confirmation')
                card = self.card()
                card['item']['rootID'] = root
                self.call('EquipInterface', 'doubleClick', panel, dict(target=bag, item_mc=card))
                self.assertIs(panel['currDDOperation'], operation)
                self.assertEqual(self.calls[1], ('to', ('previous', slot, slot['item_mc'])))
                self.assertEqual(self.calls[-1], 'native-requirements-and-confirmation')

    def test_armour_and_medicine_keep_native_slot_and_use_routes(self):
        for root in (1, 2):
            with self.subTest(root=root):
                self.calls.clear()
                panel, bag = self.owner()
                panel['outfitInterface'] = dict(prim_mc=dict(id='primary',item_mc={}))
                card = self.card()
                card['item']['rootID'] = root
                self.call('EquipInterface','doubleClick',panel,dict(target=bag,item_mc=card))
                self.assertEqual(len(self.calls),1)
                self.assertIs(self.calls[0]['item_mc'],card)
                self.assertNotIn('currDDOperation',panel)

    def test_equipment_rejection_releases_pointer_but_waiting_warning_keeps_it(self):
        operation = dict(item='weapon')
        panel = dict(currDDOperation=operation, __icEquipSendOrig=lambda: self.calls.append('native-send'))
        self.windows['queryWithCheckBox']['instance'] = dict(content={})
        self.call('EquipInterface', 'sendTransferToServer', panel)
        self.assertIs(panel['currDDOperation'], operation)
        self.windows['queryWithCheckBox']['instance'] = None
        self.call('EquipInterface', 'sendTransferToServer', panel)
        self.assertIsNone(panel['currDDOperation'])

    def test_deferred_trade_and_bank_init_cannot_reinstall_closed_window(self):
        for cls in ('TradeInterface', 'BankInterface'):
            with self.subTest(cls=cls):
                panel = dict(__icDead=True)
                self.call(cls, 'init', panel)
                self.assertTrue(panel['__icDead'])

    def test_bank_kill_releases_both_shift_bindings_and_pending_ui_init(self):
        panel = dict(bag_mc=dict(__bkOwner=True), visavisBag_mc=dict(__bkOwner=True),
                     methodTable=Arr(['init']), __methodTable=Arr(['init']),
                     __icBankKillOrig=lambda: self.calls.append('native'))
        self.call('BankInterface', 'kill', panel)
        self.assertIsNone(panel['bag_mc']['__bkOwner'])
        self.assertIsNone(panel['visavisBag_mc']['__bkOwner'])
        self.assertEqual(panel['methodTable'], [])
        self.assertEqual(panel['__methodTable'], [])

    def test_trade_escape_does_not_discard_pending_ack(self):
        self.keys['hotKeyFilter_arr'] = Arr(['inventoryTrade'])
        panel = dict(trade=dict(__gcBusy=True), close=lambda: self.fail('closed before ACK'))
        self.call('TradeInterface', '__icTradeEsc', panel)

    def test_shift_sale_keeps_real_gold_quote_guard_in_chain(self):
        panel, bag = self.owner('TradeInterface')
        spec = gold_patches(w.Asm, w.UNDEF)
        ask = next(Function(args, body.assemble(), self.env)
                   for path, method, keep, args, body in spec['wraps'] if method == 'askTradeItem')
        self.env['_global']['__moActive'] = lambda: False
        card = self.card()
        card['__icBag'] = bag
        card['item']['getProp'] = lambda name: 100 if name == 'g_sale_unit' else None
        def native(event):
            panel['currDDOperation'] = dict(fromSlot=bag, toSlot=panel['visavisBag_mc'], fromItem=card['item'])
            ask.invoke(panel, [])
        panel.update(visavisBag_mc={}, __icTradeInterfacedoubleClickOrig=native,
                     tryToSendTransferToServer=lambda: self.calls.append('quoted-transfer-pipeline'),
                     __gcAskSaleOrig=lambda: self.fail('quote bypassed'))
        self.call('BagInterface', 'shiftSelect', bag, dict(target=card))
        self.assertEqual(self.calls, ['clear-selection', 'quoted-transfer-pipeline'])
        self.call('BagInterface', 'shiftSelect', bag, dict(target=card))
        self.assertEqual(self.calls, ['clear-selection', 'quoted-transfer-pipeline'])


if __name__ == '__main__':
    run_cases(InventoryControls)
