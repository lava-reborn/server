"""Armed NPC presentation keeps real combat identity and native guard art."""
import copy
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

os.environ.setdefault('LAVA_DB', ':memory:')

import holdings
import items
import mobs
import server
import world


class MobWeaponVisuals(unittest.TestCase):
    def test_unsupported_armed_bodies_use_complete_existing_human_art(self):
        resources = {'bich': (14, 14, 14), '120': (14, 14, 14),
                     'band_leader': (1668, None, None), '82': (1668, None, None),
                     'm7': (None, 131, 131)}
        for key, info in mobs.TYPES.items():
            if info['role'] not in ('mob', 'boss') or info['resource'] not in resources:
                continue
            type_id = int(key)
            for index, (root, weapon_type) in enumerate(((items.COLD_ARM, None),
                                                        (items.FIRE_ARM, items.PISTOL),
                                                        (items.FIRE_ARM, items.ASSAULT))):
                with self.subTest(type_id=type_id, root=root, weapon_type=weapon_type):
                    with patch.object(items, 'root_of', return_value=root), \
                            patch.object(items, 'params_of', return_value={'weapon_type': weapon_type}):
                        expected = resources[info['resource']][index] or type_id
                        self.assertEqual(mobs.visual_type(type_id, 1), expected)

    def test_actual_equipment_and_stats_are_unchanged(self):
        for type_id in (411, 670, 1429, 1708, 1718, 1772, 2176, 4828, 4829):
            with self.subTest(type_id=type_id):
                stats = mobs.stats(type_id)
                before = copy.deepcopy(vars(stats))
                weapon = stats.weapon_oid(123)
                mobs.visual_type(type_id, stats.weapon_type_id)
                self.assertEqual(vars(stats), before)
                self.assertEqual(stats.weapon_oid(123), weapon)

    def test_natural_attacks_objects_turrets_and_other_models_are_untouched(self):
        for key, info in mobs.TYPES.items():
            if info['role'] not in ('mob', 'boss') or info['resource'] not in (
                    'bich', '120', 'band_leader', '82', 'm7'):
                with self.subTest(type_id=key):
                    self.assertEqual(mobs.visual_type(int(key), 1), int(key))
        for type_id in (411, 1429, 2176):
            self.assertEqual(mobs.visual_type(type_id, None), type_id)
            with patch.object(items, 'root_of', return_value=items.HEAL):
                self.assertEqual(mobs.visual_type(type_id, 1), type_id)

    def npc_info(self, type_id, weapon_type_id, *, display_guard=None, root=world.MOB):
        actor = NS(stats=NS(weapon_type_id=weapon_type_id))
        combat = NS(rc=NS(mobs={123: actor}), mob_info=lambda _id: {'lvl': 12},
                    after_npc_info=Mock())
        sess = NS(room=NS(npc=lambda _id: (123, type_id, root), loc=NS(id=98)),
                  combat=combat, char_id=1, home_here=lambda _type: False, send=Mock())
        with patch.object(holdings, 'guard_site', return_value=display_guard), \
                patch.object(holdings, 'paid_holder', return_value=None), \
                patch.object(holdings, 'flag_for', return_value=(None, False)):
            server.Session.send_npc_info(sess, 123)
        self.assertEqual(sess.send.call_count, 1)
        combat.after_npc_info.assert_called_once_with(123)
        return sess.send.call_args.args[0], sess.send.call_args.kwargs

    def test_wire_only_changes_visual_resource_not_identity_name_or_level(self):
        command, fields = self.npc_info(411, mobs.stats(411).weapon_type_id)
        self.assertEqual(command, 'userInfo')
        self.assertEqual((fields['id'], fields['name'], fields['lvl'], fields['res']),
                         (123, 411, 12, 14))

    def test_wire_keeps_local_base_guard_model_and_caption(self):
        guard = holdings.base_for(118)
        command, fields = self.npc_info(918, mobs.stats(4828).weapon_type_id, display_guard=guard)
        self.assertEqual(command, 'userInfo')
        self.assertEqual((fields['id'], fields['name'], fields['lvl'], fields['res']),
                         (123, holdings.BASE_GUARD_NAME, 12, guard.guards[0]))

    def test_services_never_receive_combat_presentation_fallback(self):
        command, fields = self.npc_info(411, mobs.stats(411).weapon_type_id, root=world.COMMONER)
        self.assertEqual(command, 'userInfo_Commoner')
        self.assertEqual(fields['res'], 411)

    def test_donors_have_every_native_armed_animation_file(self):
        resources = Path(world.RES) / 'mobs'
        if not resources.is_dir():
            self.skipTest('Original client resources are not configured')
        for type_id in (14, 131, 1668):
            resource = mobs.TYPES[str(type_id)]['resource']
            xml = ET.parse(resources / (resource + '.xml')).getroot()
            self.assertEqual(xml.get('composite'), 'true')
            for stance in ('knife', 'pistol', 'rifle'):
                section = xml.find(stance)
                self.assertIsNotNone(section)
                for action in section.findall('action'):
                    animation = action.get('action')
                    if animation:
                        with self.subTest(type_id=type_id, stance=stance, animation=animation):
                            self.assertTrue((resources / resource / (resource + '_' + animation + '.swf')).is_file())

    def test_guard_overlay_changes_only_missing_rifle_stand(self):
        root = Path(__file__).resolve().parents[1]
        original_path = Path(world.RES) / 'mobs/m118_coevoet.xml'
        if not original_path.is_file():
            self.skipTest('Original client resources are not configured')
        original = ET.parse(original_path).getroot()
        updated = ET.parse(root / 'client/files/mobs/m118_coevoet.xml').getroot()
        old_stand = original.find("rifle/action[@id='stand']")
        stand = updated.find("rifle/action[@id='stand']")
        mili = original.find("rifle/action[@id='stand_mili']")
        self.assertEqual(stand.get('action'), mili.get('action'))
        self.assertEqual(stand.text, mili.text)
        self.assertEqual(stand.get('action'), 'rifle_mili')
        stand.attrib.clear()
        stand.attrib.update(old_stand.attrib)
        stand.text = old_stand.text
        for tree in (updated, original):
            for element in tree.iter():
                element.text = element.text.strip() if element.text else None
                element.tail = None
        self.assertEqual(ET.tostring(updated), ET.tostring(original))
        self.assertTrue((original_path.parent / 'm118_coevoet/m118_coevoet_rifle_mili.swf').is_file())


if __name__ == '__main__':
    unittest.main()
