"""Native static frames describe the existing equip gate, without changing it."""
import unittest
from unittest.mock import patch

import inventory
import item_templates
import items
import progression
import sets
import setcraft
from protocol import encode, decode
from testkit import run_cases


class EquipmentLevelTooltips(unittest.TestCase):
    def test_level_metadata_survives_the_actual_static_frame_wire_codec(self):
        for type_id in (3941, 7072, 3726, 3735, 3203, 3207, 6055):
            with self.subTest(type_id=type_id):
                command, fields = items.static_info(type_id)
                actual_command, packet = decode(encode(command, **fields))
                self.assertEqual(actual_command, command)
                for key in ('equip_level', 'equip_allowance', 'buff_level'):
                    self.assertEqual(packet.get(key), fields.get(key))
                self.assertEqual(packet.get('need_skills_m'), fields.get('need_skills_m'))
                self.assertEqual(packet.get('need_skills'), fields.get('need_skills'))

    def test_all_native_equipment_frames_match_the_actual_gate(self):
        checked = 0
        for type_id, (root, _) in items.catalogue().items():
            if root not in (items.FIRE_ARM, items.COLD_ARM, items.WEAR):
                continue
            if item_templates.contains(type_id):
                continue
            frame = items.static_info(type_id)[1]
            level = inventory.item_level(type_id)
            is_set = root == items.WEAR and sets.set_of(setcraft.base_of(type_id))
            allowance = (3 if (root in (items.FIRE_ARM, items.COLD_ARM) or is_set)
                         and type_id not in items.STRICT_LEVEL_GEAR else 0)
            self.assertEqual(inventory.gear_level_allowance(type_id), allowance, type_id)
            expected = (dict(equip_level=level,
                             equip_allowance=allowance)
                        if level > 0 else {})
            actual = {key: frame[key] for key in ('equip_level', 'equip_allowance')
                      if key in frame}
            self.assertEqual(actual, expected, type_id)
            checked += bool(expected)
        self.assertGreater(checked, 1000)

    def test_strict_laboratory_pouches_never_advertise_minus_three(self):
        self.assertEqual(len(items.STRICT_LEVEL_GEAR), 7)
        for type_id in items.STRICT_LEVEL_GEAR:
            with self.subTest(type_id=type_id):
                frame = items.static_info(type_id)[1]
                self.assertEqual((frame['equip_level'], frame['equip_allowance']), (16, 0))
                self.assertEqual(items.equipment_level_text(type_id),
                                 'Можно надеть только с 16-го уровня.')

    def test_free_gear_has_the_same_allowance_as_sold_gear(self):
        frame = items.static_info(3941)[1]  # Native unpriced Bone_Knife.
        self.assertFalse(frame.get('cost') or frame.get('g_cost'))
        self.assertEqual((frame['equip_level'], frame['equip_allowance']), (6, 3))
        self.assertIn('с 3-го уровня', items.equipment_level_text(3941))

    def test_literal_non_gear_skills_and_templates_have_no_equip_allowance(self):
        for type_id, (root, _) in items.catalogue().items():
            if root in (items.FIRE_ARM, items.COLD_ARM, items.WEAR):
                continue
            frame = items.static_info(type_id)[1]
            self.assertNotIn('equip_level', frame, type_id)
            self.assertNotIn('equip_allowance', frame, type_id)
        for type_id in items.catalogue():
            if item_templates.contains(type_id):
                frame = items.static_info(type_id)[1]
                self.assertNotIn('equip_level', frame, type_id)
                self.assertNotIn('equip_allowance', frame, type_id)

    def test_presentation_does_not_change_native_wear_eligibility(self):
        character = progression.Character()
        for spec in character.spec:
            spec[0] = 5
        for type_id in (3941, 3735):
            required = inventory.item_level(type_id)
            allowance = inventory.gear_level_allowance(type_id)
            for skill in character.skill:
                skill[0] = required - allowance
            item = dict(type_id=type_id, root=items.root_of(type_id))
            self.assertIsNone(inventory.weapon_requirement_error(item, character))
            for skill in character.skill:
                skill[0] = required - allowance - 1
            self.assertIsNotNone(inventory.weapon_requirement_error(item, character))

    def test_only_set_pieces_and_weapons_have_minus_three_at_the_equip_boundary(self):
        native_set = next(row for row in sets.SETS.values() if row['level'] == 14 and row['variant'] == 'A')
        native_piece = native_set['members']['helm']
        mod_piece = next(t for t, (base, mod) in setcraft.MOD_OF.items()
                         if base == native_piece and mod == 1)
        for type_id, allowance in ((native_piece, 3), (mod_piece, 3),
                                   (3941, 3), (3726, 0), (3735, 0), (4973, 0)):
            with self.subTest(type_id=type_id):
                level = inventory.item_level(type_id)
                row = dict(root=items.root_of(type_id), type_id=type_id)
                self.assertEqual(items.equipment_level_allowance(type_id), allowance)
                self.assertTrue(inventory.wearable(row, level - allowance))
                self.assertFalse(inventory.wearable(row, level - allowance - 1))
                prose = items.equipment_level_text(type_id)
                self.assertEqual('только' in prose, not allowance)

    def test_private_template_frames_keep_their_own_requirement_rules(self):
        type_id = 65000
        frame = ('ss_si_coldarm', dict(type=type_id, need_skills_m=1, need_skills=[20]))
        with patch.dict(item_templates._SOURCES, {type_id: 3941}), \
             patch.dict(item_templates._FRAMES, {type_id: frame}):
            self.assertEqual(items.static_info(type_id), frame)
            self.assertEqual(items.equipment_level_fields(type_id, frame[1]), {})
            self.assertEqual(items.equipment_level_text(type_id), '')


if __name__ == '__main__':
    run_cases(EquipmentLevelTooltips)
