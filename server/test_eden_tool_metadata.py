"""Eden tool durability reaches real saved and wire instances, without changing knives."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import accounts
import eden
import inventory
import items
import names
import progression
from testkit import run_cases


class EdenToolMetadataTests(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store.temporary()
        self.addCleanup(self.store.close)
        account, err = self.store.register('eden_tool_metadata', 'isolated-password')
        self.assertFalse(err)
        self.cid, _ = self.store.create_character(account, 'EdenToolTester', 0, '1')

    def test_assignment_persists_full_ten_thousand_and_publishes_it_on_wire(self):
        fields = inventory.new_fields(6240)
        root = fields.pop('root')
        fields['slot'] = inventory.PRIMARY
        old_weapon = self.store.create_item(self.cid, 6240, root, **fields)
        eden.grant_tools(self.store, self.cid)
        tool, = [row for row in self.store.items_of(self.cid) if row['type_id'] == eden.CLEAVER]
        self.assertEqual((tool['brk'], tool['max_break_cur']), (10000, 10000))
        self.assertEqual(tool['slot'], inventory.PRIMARY)
        dynamic = inventory.di_params(tool)
        self.assertEqual((dynamic['break'], dynamic['max_break_cur']), (10000, 10000))
        static = items.static_info(eden.CLEAVER)[1]
        self.assertEqual(static['max_break_abs'], 10000)
        self.assertEqual((static['need_skills_m'], static['need_specs_m'], static['need_attribs_m']),
                         (0, 0, 0))
        original = self.store.item(old_weapon['uniq'])
        self.assertEqual((original['brk'], original['max_break_cur'], original['slot']),
                         (400, 400, inventory.BAG))
        self.assertEqual(items.params_of(6240)['max_break_abs'], 400)

    def test_static_update_does_not_implicitly_refill_an_existing_item(self):
        # A saved 999/999 instance does not consult new_fields on reconnect.
        # This checks the need for the installer's narrow existing-tool fix.
        fields = inventory.new_fields(eden.CLEAVER)
        root = fields.pop('root')
        fields.update(brk=999, max_break_cur=999)
        old = self.store.create_item(self.cid, eden.CLEAVER, root, **fields)
        self.assertEqual(items.params_of(eden.CLEAVER)['max_break_abs'], 10000)
        saved = self.store.item(old['uniq'])
        self.assertEqual((saved['brk'], saved['max_break_cur']), (999, 999))
        self.assertEqual(inventory.new_fields(eden.CLEAVER)['max_break_cur'], 10000)

    def test_dedicated_tool_has_the_approved_name_and_short_description(self):
        self.assertEqual(names.ALL[items.STRING_ID_OFFSET + eden.CLEAVER], 'ТЕСАК')
        description = names.ALL[items.DESC_ID_OFFSET + eden.CLEAVER]
        self.assertEqual(description, 'Инструмент, чтобы искупить свою вину.')
        self.assertNotIn('прочност', description.lower())
        self.assertEqual(items.params_of(eden.CLEAVER)['max_break_abs'], 10000)
        self.assertEqual(items.params_of(6240)['max_break_abs'], 400)

    def test_all_three_tickets_weigh_one_gram_on_wire_and_in_real_stacks(self):
        for type_id in (eden.GREEN_TICKET, eden.GOOD_TICKET, eden.BAD_TICKET):
            self.assertEqual(items.static_info(type_id)[1]['weight'], 1)
            fields = inventory.new_fields(type_id, 7)
            root = fields.pop('root')
            row = self.store.create_item(self.cid, type_id, root, **fields)
            self.assertEqual(inventory.weight_of(row), 7)
        for type_id in (eden.EXIT_PASS, eden.PALM_LEAF):
            self.assertEqual(items.static_info(type_id)[1]['weight'], 1)

    def test_basket_adds_fifty_strength_and_one_hundred_kilograms_only_on_the_belt(self):
        ch = progression.Character.load(self.store, self.cid)
        before = ch.max_weight()
        fields = inventory.new_fields(eden.BASKET)
        root = fields.pop('root')
        basket = self.store.create_item(self.cid, eden.BASKET, root, **fields)
        for slot, extra in ((inventory.BAG, 0), (inventory.BELT, 100000),
                            (inventory.BANK, 0), (inventory.BELT, 100000)):
            with self.subTest(slot=slot):
                basket['slot'] = slot
                ch.set_gear(inventory.gear_bonus([basket], ch))
                self.assertEqual(ch.max_weight(), before + extra)
                self.assertEqual(ch.attr(progression.STRENGTH), ch.attrib[progression.STRENGTH] + (50 if slot == inventory.BELT else 0))
                self.assertEqual(ch.rp_info()['max_weight'], before + extra)
        self.assertIn('+100 кг', names.ALL[items.DESC_ID_OFFSET + eden.BASKET])

    def test_basket_has_one_thousand_factory_and_new_instance_durability(self):
        self.assertEqual(items.static_info(eden.BASKET)[1]['max_break_abs'], 1000)
        fields = inventory.new_fields(eden.BASKET)
        root = fields.pop('root')
        basket = self.store.create_item(self.cid, eden.BASKET, root, **fields)
        self.assertEqual((basket['brk'], basket['max_break_cur']), (1000, 1000))
        dynamic = inventory.di_params(basket)
        self.assertEqual((dynamic['break'], dynamic['max_break_cur']), (1000, 1000))


if __name__ == '__main__':
    run_cases(EdenToolMetadataTests)
