"""Hand gifts: actual inventory moves, temporary stats and unchanged saved progress."""
import json
import time
import unittest

import accounts
import auction
import mail
from unittest.mock import patch

import combat
import inventory
import items
import names
import progression
from test_release_battle import BattleFixes
from testkit import run_cases


class HandValentines(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = BattleFixes()
        await self.case.asyncSetUp()
        self.addAsyncCleanup(self.case.asyncTearDown)
        self.s = self.case.players[0]

    async def test_each_valentine_bonuses_either_hand_and_never_the_bag_or_belt(self):
        original = self.s.char.attrib[:]
        for type_id, (attribute, amount) in items.HAND_VALENTINES.items():
            row = self.s.inv.create(type_id)
            self.assertEqual(row['root'], items.COLD_ARM)
            command, si = items.static_info(type_id)
            self.assertEqual(command, 'ss_si_coldarm')
            self.assertEqual((si['cost'], si['g_cost'], si['action_map']),
                             (0, 2500, items.ACT_FIRE))
            self.assertNotIn('slot_type', si)
            self.assertEqual((si['h_damage_min'], si['h_damage_max'], si['strike_cost']), (1, 1, 1))
            self.assertTrue(inventory.oid_of(row).endswith('05'))
            self.assertFalse(inventory.fits(row, inventory.BELT))
            self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': inventory.BAG, 'to': inventory.BELT}))
            self.assertEqual(self.case.store.item(row['uniq'])['slot'], inventory.BAG)
            self.s.inv.refresh_gear(push=False)
            self.assertEqual(self.s.char.bonus_attribs, [0] * 5)
            for slot in inventory.HAND_SLOTS:
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': inventory.BAG, 'to': slot}))
                self.assertEqual(self.case.store.item(row['uniq'])['slot'], slot)
                self.assertEqual(self.s.char.attr(attribute), original[attribute] + amount)
                self.assertEqual(self.s.char.attrib, original)
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': slot, 'to': inventory.BAG}))
                self.assertEqual(self.s.char.bonus_attribs, [0] * 5)
            description = names.ALL[items.params_of(type_id)['desc']]
            self.assertIn('в любой руке', description)
            self.assertIn('Режущее оружие', description)
            self.assertIn('Не надевается на пояс', description)
            self.assertIn('+' + str(amount), description)
            reloaded = progression.Character.load(self.case.store, self.s.char_id)
            reloaded.set_gear(inventory.gear_bonus(self.s.inv.rows(), reloaded))
            self.assertEqual(reloaded.attrib, original)
            self.assertEqual(reloaded.bonus_attribs, [0] * 5)

    async def test_buy_each_25_gold_gift_then_equip_and_relogin(self):
        self.s.char.gold = 20000
        self.s.char.save(self.case.store)
        self.s.inv.trade = inventory.TradeSession(1, 1959, 41)
        for type_id, (attribute, amount) in items.HAND_VALENTINES.items():
            before = {r['uniq'] for r in self.s.inv.rows()}
            money = self.s.char.gold
            with patch.object(items, 'stock_for', return_value=[type_id]), \
                    patch.object(self.s.inv, 'current_trade_rates', return_value=dict(pmod=1, smod=.7, rmod=1)):
                self.s.inv.buy(dict(obj='0', param=1), inventory.UPD_BUY_GOLD)
            bought = [r for r in self.s.inv.rows() if r['uniq'] not in before]
            self.assertEqual(len(bought), 1)
            row = bought[0]
            self.assertEqual((self.s.char.gold, self.case.store.money(self.s.char_id)[1]),
                             (money - 2500, money - 2500))
            self.assertEqual((row['type_id'], row['root'], row['count']), (type_id, items.COLD_ARM, 1))
            self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': inventory.BAG, 'to': inventory.SECONDARY}))
            self.s.load_character(self.s.char_id)
            self.assertEqual(self.case.store.item(row['uniq'])['slot'], inventory.SECONDARY)
            self.assertEqual(self.s.char.attr(attribute), self.s.char.attrib[attribute] + amount)
            self.s.handle('ss_move', dict(obj=inventory.oid_of(row), **{'from': inventory.SECONDARY, 'to': inventory.BAG}))

    async def test_each_valentine_uses_the_blade_skill_and_native_strike_action(self):
        for type_id in items.HAND_VALENTINES:
            row = self.s.inv.create(type_id, slot=inventory.PRIMARY)
            self.s.inv.refresh_gear(push=False)
            with patch.object(combat.Fighter, 'schedule_action') as schedule:
                self.s.combat.strike_with(row, self.case.players[1].combat, None)
            args = schedule.call_args.args
            self.assertEqual(args[2], 'strike')
            self.assertEqual(args[8], combat.SPEC_BLADE)
            self.assertEqual(args[9], 1)
            self.assertEqual(args[10], row['uniq'])
            self.case.store.update_item(row['uniq'], slot=inventory.BAG)

    async def test_old_parcels_can_be_read_claimed_and_equipped_without_relogin(self):
        store = self.case.store
        parcels = []
        for index, type_id in enumerate(items.HAND_VALENTINES):
            row = self.s.inv.create(type_id)
            snap = dict(mail.snapshot(row), root=items.WEAR)
            store.delete_item(row['uniq'])
            kind = mail.TRADE if index % 2 else mail.LETTER
            letter = store.mail_send(self.s.char_id, self.s.char_id, kind,
                                      'old gift', 'old gift', 25 if kind == mail.TRADE else 0,
                                      0, json.dumps([snap]))
            parcels.append((letter, snap))
        self.assertTrue(accounts.run_once(store.db, inventory.HAND_VALENTINES_FIX,
                                          inventory.repair_legacy_hand_valentines))
        for letter, snap in parcels:
            with self.subTest(type_id=snap['type_id']):
                frames = []
                before = store.money(self.s.char_id)
                with patch.object(self.s, 'send', side_effect=lambda cmd, **data: frames.append((cmd, data))):
                    self.s.mail.getml(dict(id=str(letter['id'])))
                    info = next(data for cmd, data in frames if cmd == 'rcml')
                    self.assertEqual(inventory.parse_oid(info['items'][0])[2], items.COLD_ARM)
                    self.s.mail.uldml(dict(id=str(letter['id'])))
                received = [r for r in self.s.inv.rows() if r['type_id'] == snap['type_id']]
                self.assertEqual(len(received), 1)
                row = received[0]
                self.assertEqual((row['root'], row['count'], row['brk'], row['max_break_cur']),
                                 (items.COLD_ARM, snap['count'], snap['brk'], snap['max_break_cur']))
                self.assertEqual(store.money(self.s.char_id), (before[0] - letter['afro'], before[1]))
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row),
                              **{'from': inventory.BAG, 'to': inventory.SECONDARY}))
                self.assertEqual(store.item(row['uniq'])['slot'], inventory.SECONDARY)
                attribute, amount = items.HAND_VALENTINES[row['type_id']]
                self.assertEqual(self.s.char.attr(attribute), self.s.char.attrib[attribute] + amount)
                money = store.money(self.s.char_id)
                self.s.mail.uldml(dict(id=str(letter['id'])))
                self.assertEqual(store.money(self.s.char_id), money)
                self.assertEqual(len([r for r in self.s.inv.rows() if r['type_id'] == row['type_id']]), 1)
                self.s.handle('ss_move', dict(obj=inventory.oid_of(row),
                              **{'from': inventory.SECONDARY, 'to': inventory.BAG}))

    async def test_old_auction_lot_keeps_matching_wire_ids_and_returns_a_usable_gift(self):
        store = self.case.store
        row = self.s.inv.create(1070)
        store.db.execute('UPDATE items SET root=? WHERE uniq=?', (items.WEAR, row['uniq']))
        store.db.commit()
        snap = mail.snapshot(store.item(row['uniq']))
        now = time.time()
        lot = store.auction_list(row['uniq'], self.s.char_id, dict(
            type_id=1070, root=items.WEAR, item_json=json.dumps(snap),
            seller=self.s.char_id, seller_name=self.s.nick, currency=auction.GOLD,
            start_bid=100, buyout=200, fee=0, hours=24, created_at=int(now), ends_at=now + 86400))
        accounts.run_once(store.db, inventory.HAND_VALENTINES_FIX,
                          inventory.repair_legacy_hand_valentines)
        current = store.auction_lot(lot['id'])
        house = auction.Auction(self.s, store, self.s.mail.directory)
        frames = []
        with patch.object(self.s, 'send', side_effect=lambda cmd, **data: frames.append((cmd, data))):
            house.send_lot(current, now)
        wire_id = next(data['obj'] for cmd, data in frames if cmd == 'ah_lot')
        self.assertEqual(inventory.parse_oid(wire_id), (row['uniq'], 1070, items.COLD_ARM))
        self.assertEqual(house.find_lot(wire_id)['id'], lot['id'])
        self.assertEqual(frames[-1][0], 'ss_di_coldarm')
        returned = store.auction_close(lot['id'], auction.give_back(current, 'return', 'return'))
        self.s.mail.uldml(dict(id=str(returned[0]['id'])))
        received = next(r for r in self.s.inv.rows() if r['type_id'] == 1070)
        self.s.handle('ss_move', dict(obj=inventory.oid_of(received),
                      **{'from': inventory.BAG, 'to': inventory.SECONDARY}))
        self.assertEqual(store.item(received['uniq'])['slot'], inventory.SECONDARY)
        self.assertEqual(store.item(received['uniq'])['root'], items.COLD_ARM)
        self.assertIsNone(store.auction_close(lot['id'], auction.give_back(current, 'again', 'again')))

    async def test_legacy_belt_and_bank_rows_are_repaired_without_replacing_items(self):
        rows = []
        for type_id, slot in zip(items.HAND_VALENTINES, (inventory.BELT, inventory.BAG, inventory.BANK, inventory.SECONDARY)):
            row = self.s.inv.create(type_id)
            self.case.store.db.execute('UPDATE items SET root=?,slot=? WHERE uniq=?',
                                       (items.WEAR, slot, row['uniq']))
            rows.append(self.case.store.item(row['uniq']))
        self.case.store.db.commit()
        unrelated = self.s.inv.create(3722, slot=inventory.BELT)
        foreign = self.case.players[1].inv.create(1069)
        self.case.store.db.execute('UPDATE items SET root=? WHERE uniq=?', (items.WEAR, foreign['uniq']))
        self.case.store.db.commit()
        original = (self.s.char.attrib[:], self.s.char.skill[:], self.s.char.gold)
        self.s.load_character(self.s.char_id)
        for row in rows:
            expected = dict(row, root=items.COLD_ARM,
                            slot=inventory.BAG if row['slot'] == inventory.BELT else row['slot'])
            self.assertEqual(self.case.store.item(row['uniq']), expected)
        self.assertEqual(self.case.store.item(unrelated['uniq']), unrelated)
        self.assertEqual(self.case.store.item(foreign['uniq'])['root'], items.WEAR)
        self.assertEqual((self.s.char.attrib, self.s.char.skill, self.s.char.gold), original)
        self.assertEqual(self.s.inv.normalize_hand_valentines(), [])

    async def test_failed_legacy_repair_rolls_back_every_item(self):
        rows = [self.s.inv.create(t) for t in (1069, 1070)]
        for row in rows:
            self.case.store.db.execute('UPDATE items SET root=?,slot=? WHERE uniq=?',
                                       (items.WEAR, inventory.BELT, row['uniq']))
        self.case.store.db.commit()
        before = self.s.inv.rows()
        execute = self.case.store.db.execute
        updates = 0
        def fail_second(sql, args=()):
            nonlocal updates
            if sql.startswith('UPDATE items SET root='):
                updates += 1
                if updates == 2:
                    raise RuntimeError('interrupted repair')
            return execute(sql, args)
        with patch.object(self.case.store.db, 'execute', side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'interrupted repair'):
                self.s.inv.normalize_hand_valentines()
        self.assertEqual(self.s.inv.rows(), before)

    async def test_stale_catalogue_root_does_not_turn_hand_gifts_into_belts(self):
        import own_items
        # Rebuild from original rows only: the released catalogue already
        # includes own_items, which must not be reintroduced as native types.
        table = own_items.originals(dict(items.catalogue()))
        for type_id in items.HAND_VALENTINES:
            table[type_id] = (items.WEAR, table[type_id][1])
        with patch.object(items, '_CATALOGUE', None), \
                patch.object(own_items, 'originals', return_value=table):
            for type_id in items.HAND_VALENTINES:
                self.assertEqual(items.root_of(type_id), items.COLD_ARM)
                self.assertEqual(items.static_info(type_id)[0], 'ss_si_coldarm')


if __name__ == '__main__':
    run_cases(HandValentines)
