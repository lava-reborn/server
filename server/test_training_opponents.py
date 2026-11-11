"""Small catalogue, lifecycle and isolation checks for player-facing targets."""
import unittest
import names
import mobs
import bosses
import sets
import training_ground as tg
import training_opponents as catalogue
from protocol import decode
import test_training_ground as fixtures


class Catalogue(unittest.TestCase):
    def test_reviewed_catalogue_has_names_groups_and_all_camp_bosses(self):
        choices = tg.mob_catalogue()
        self.assertLess(len(choices), 300)
        self.assertTrue(bosses.CAMP_RECOVERY_TYPES <= choices.keys())
        self.assertEqual(set(row['group'] for row in catalogue.RECORDS.values()), set(catalogue.GROUPS)-{'all'})
        for t, label in choices.items():
            self.assertNotIn('_', label)
            self.assertRegex(label, '[А-Яа-яЁё]')
            self.assertIn(catalogue.NAME_BASE+t, names.ALL)
        self.assertNotEqual(names.text(1949), names.text(catalogue.NAME_BASE+1949))
        self.assertNotIn(1081, choices)  # Old UFO/debug content is not a selectable target.


class Opponents(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged

    async def test_spawn_near_computer_and_each_group_can_finish_without_rewards(self):
        g = self.enter()
        self.assertEqual(g.spawn_point, 0)
        self.assertLess(g.distance, 20)
        for group in set(catalogue.GROUPS)-{'all'}:
            g.mob_type = next(t for t in tg.mob_catalogue() if catalogue.RECORDS[t]['group'] == group)
            original = vars(mobs.stats(g.mob_type)).copy()
            g.start('mob')
            mob = g.room.combat.mobs[g.mob_eid]
            self.assertGreater(mob.cell % g.clone.loc.width, tg.COMPUTER_CELL % g.clone.loc.width)
            g.target_defeated(mob)
            self.assertEqual(g.phase, 'ready')
            self.assertIsNone(g.mob_eid)
            self.assertEqual(vars(mobs.stats(g.mob_type)), original)
        self.unchanged()


    async def test_category_level_choices_match_profile_before_search_and_paging(self):
        from dataclasses import replace
        g = self.enter()
        data = tg.training_formulas.data()
        for simulator in (False, True):
            g.rules = replace(g.rules, simulator_formulas=simulator)
            for group in catalogue.GROUPS:
                def level(t):
                    if simulator and str(t) in data['mobs']:
                        return data['mob_records'][data['mobs'][str(t)]]['level']
                    return mobs.stats(t).level
                expected = sorted({level(t) for t in tg.mob_catalogue()
                                   if (group == 'all' or catalogue.RECORDS[t]['group'] == group)
                                   and level(t) > 0})
                for request in (dict(),dict(query='несуществующая цель',page=5),dict(level=40,page=5)):
                    g.catalogue(dict(category='mob',group=group,**request))
                    _,packet = decode(self.s.writer.frames[-1][:-1])
                    self.assertEqual(packet['available_levels'],expected,(simulator,group))
                    if request.get('level') == 40:
                        self.assertEqual(packet['selected_level'],0)
                        self.assertEqual(packet['page'],0)
                for selected in expected:
                    g.catalogue(dict(category='mob',group=group,level=selected))
                    _,packet = decode(self.s.writer.frames[-1][:-1])
                    self.assertGreater(packet['total'],0,(simulator,group,selected))
                    self.assertTrue(all(value==selected for value in packet['levels']))
        self.unchanged()

    async def test_calibrated_boss_level_matches_simulator_and_label(self):
        from dataclasses import replace
        g = self.enter()
        g.rules = replace(g.rules, simulator_formulas=True)
        g.mob_type = 8620
        g.start('mob')
        self.assertEqual(g.room.combat.mobs[g.mob_eid].stats.level, 21)
        self.assertEqual(mobs.stats(8620).level, 33)
        self.assertIn('21 ур.', g.mob_label(8620))
        g.catalogue(dict(category='mob', group='bosses', level=21))
        _, packet = decode(self.s.writer.frames[-1][:-1])
        self.assertIn(8620, packet['ids'])
        g.target_defeated(g.room.combat.mobs[g.mob_eid])
        self.unchanged()

    async def test_selected_fighter_summary_reflects_set_and_custom_changes(self):
        g = self.enter()
        set_id = next(t for t,r in sets.SETS.items() if r['level'] == 12 and r['variant'] == 'A'
                      and all(m in tg.item_catalogue() for m in r['members'].values()))
        g.opponent = g.fighter_preset(set_id)
        self.assertIn(sets.SETS[set_id]['name'],g.opponent_summary())
        g.opponent['gear'] = {}
        self.assertIn('Своя сборка',g.opponent_summary())
        self.assertIn('Без оружия',g.opponent_summary())

    async def test_hidden_old_target_does_not_discard_saved_character(self):
        g = self.enter()
        g.profile = tg.validate_profile(tg.preset(12))
        g.mob_type = 1081
        g.save_settings()
        restored = tg.Ground(self.s)
        try:
            self.assertEqual(max(restored.profile['skills']),12)
            self.assertIn(restored.mob_type,tg.mob_catalogue())
            self.assertIn('цель удалена',restored.restore_notice)
        finally:
            restored.exit(notify=False)

    async def test_spawned_target_name_uses_only_private_string_id(self):
        g = self.enter()
        g.mob_type = 1949
        g.start('mob')
        g.clone.send_npc_info(g.mob_eid)
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        packet = next(params for command,params in reversed(frames) if command == 'userInfo')
        self.assertEqual(packet['name'], catalogue.NAME_BASE+1949)
        self.assertEqual(packet['res'], 1949)
        self.assertEqual(names.text(1949), 'kv_Camel_lvl8')
        self.unchanged()
