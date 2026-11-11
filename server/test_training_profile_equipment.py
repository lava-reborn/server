"""Profile switches preserve private instances and never mutate live templates."""
import unittest
from unittest.mock import patch

from protocol import decode

import inventory
import items
import sets
from training import catalog as range_catalog
from training import character as range_character
from training import session as training
from training import items as copies
from training.rules import Rules
import test_training_ground as fixtures


class ProfileEquipment(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    party_members = fixtures.TrainingGround.party_members

    def equip(self, ground):
        profile = range_character.preset(12)
        profile['specs'] = [3] * 8 + [-1] * 7
        profile['gear'] = {t: 1 for t in sets.SETS[60000]['members'].values()}
        profile['gear'][26075] = 1
        ground.profile = range_character.validate_profile(profile, ground.rules)
        ground.apply(ground.clone, ground.profile)
        ground.remember_outfit()

    def switch(self, ground, enabled):
        ground.last_request = 0
        ground.request(dict(op='rules', token=ground.token,
                            values=Rules(simulator_formulas=enabled, ammo_modifiers=True).values()))

    async def test_switch_round_trip_preserves_instances_and_source_tables(self):
        ground = self.enter()
        self.equip(ground)
        rows = [dict(r) for r in ground.clone.inv.rows()]
        original = {copies.source_type(r['type_id']): items.params_of(copies.source_type(r['type_id'])) for r in rows}
        gun = ground.clone.inv.in_slot(inventory.PRIMARY)
        ammo = items.params_of(gun['type_id'])['comp_array'][0]
        ground.store.update_item(gun['uniq'], brk=7, ammo_type=ammo, ammo_count=2)
        before = [dict(r) for r in ground.clone.inv.rows()]
        self.switch(ground, True)
        current = [dict(r) for r in ground.clone.inv.rows()]
        self.assertTrue(any(a['type_id'] != b['type_id'] for a, b in zip(before, current)))
        for a, b in zip(before, current):
            self.assertEqual({k: v for k, v in a.items() if k != 'type_id'},
                             {k: v for k, v in b.items() if k != 'type_id'})
        char = ground.clone.character()
        self.assertEqual((char.hp_max, char.sp_max, char.ap_ceiling), (493, 801, 136))
        self.assertEqual([char.attr(i) for i in range(5)], [16, 16, 16, 12, 5])
        for row in current:
            source = copies.profile_source(row['type_id'])
            self.assertEqual(items.params_of(source), original[source])
            if row['root'] == items.WEAR:
                self.assertEqual(items.params_of(row['type_id'])['set_type'], sets.set_of(row['type_id']))
        self.switch(ground, False)
        self.assertEqual([dict(r) for r in ground.clone.inv.rows()], before)
        self.unchanged()

    async def test_shared_room_receives_new_equipment_and_vitals_without_changing_peer(self):
        members, _, _ = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for ground in (first, second):
            ground.clone.cmd_lenter({})
        self.equip(first)
        peer_rows = [dict(row) for row in second.clone.inv.rows()]
        members[1].writer.frames.clear()
        self.switch(first, True)
        frames = [decode(frame[:-1]) for frame in members[1].writer.frames]
        gun = first.clone.inv.in_slot(inventory.PRIMARY)
        live_index = next(i for i, (cmd, p) in enumerate(frames)
                          if cmd == 'tg' and p['op'] == 'inventory')
        hand_index = next(i for i, (cmd, p) in enumerate(frames)
                          if cmd == 'ss_obj_move' and p['id'] == first.clone.pid
                          and p['to'] == inventory.PRIMARY)
        self.assertLess(live_index, hand_index)
        self.assertEqual(str(frames[hand_index][1]['obj']), inventory.oid_of(gun))
        self.assertIn(inventory.oid_of(gun), frames[live_index][1]['live_oids'])
        self.assertTrue(any(cmd == 'usrUp' and p['id'] == first.clone.pid
                            and p['hmax'] == first.clone.char.hp_max for cmd, p in frames))
        self.assertEqual([dict(row) for row in second.clone.inv.rows()], peer_rows)
        self.assertFalse(second.rules.simulator_formulas)
        self.unchanged()

    async def test_failed_conversion_rolls_back_all_rows_without_notifications(self):
        ground = self.enter()
        self.equip(ground)
        before = [dict(r) for r in ground.clone.inv.rows()]
        frames = len(self.s.writer.frames)
        real_update = ground.store.db.execute
        count = 0
        def fail_second(*args, **kwargs):
            nonlocal count
            if args[0].startswith('UPDATE items SET type_id='):
                count += 1
                if count == 2:
                    raise RuntimeError('injected failure')
            return real_update(*args, **kwargs)
        with patch.object(ground.store.db, 'execute', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                ground.clone.inv.switch_profile(True)
        self.assertEqual([dict(r) for r in ground.clone.inv.rows()], before)
        self.assertEqual(len(self.s.writer.frames), frames)
        self.unchanged()

    async def test_disabled_item_blocks_switch_and_wrong_profile_issuance(self):
        ground = self.enter()
        source = next(t for t in range_catalog.item_catalogue() if not copies.available(t, True))
        ground.clone.inv.issue(copies.copy_type(source), 1)
        before = [dict(r) for r in ground.clone.inv.rows()]
        with self.assertRaises(ValueError):
            ground.clone.inv.switch_profile(True)
        self.assertEqual([dict(r) for r in ground.clone.inv.rows()], before)
        source = next(t for t in copies.COPIES if copies.copy_type(t, True) != copies.copy_type(t))
        with self.assertRaises(ValueError):
            ground.clone.inv.issue(copies.copy_type(source, True), 1)
        self.unchanged()

    async def test_gold_rifle_cost_fix_has_own_static_id(self):
        self.enter()
        source = next(t for t in range_catalog.item_catalogue()
                      if t in items.catalogue() and items.catalogue()[t][1].startswith('rifle_1_lvl_19')
                      and items.params_of(t).get('fire_costs', [0])[0] == 324)
        before = copies.copy_type(source)
        after = copies.copy_type(source, True)
        self.assertNotEqual(before, after)
        self.assertEqual(items.params_of(before)['fire_costs'][0], 324)
        self.assertEqual(items.params_of(after)['fire_costs'][0], 34)
        self.assertEqual(items.params_of(source)['fire_costs'][0], 324)

    async def test_saved_withdrawn_equipment_restores_old_profile_without_reset(self):
        ground = self.enter()
        source = next(t for t in range_catalog.item_catalogue()
                      if not copies.available(t, True) and items.root_of(t) == items.WEAR)
        saved = self.store.training_profile(self.s.char_id)
        ground.exit(notify=False)
        saved['player']['gear'] = {str(source): 1}
        saved['rules'] = Rules(simulator_formulas=True).as_dict()
        self.store.save_training_profile(self.s.char_id, saved)
        restored = training.Ground(self.s)
        try:
            self.assertFalse(restored.rules.simulator_formulas)
            self.assertEqual(restored.profile['gear'], {source: 1})
            self.assertIn('Пресеты сохранены', restored.restore_notice)
            self.unchanged()
        finally:
            restored.exit(notify=False)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(ProfileEquipment)
