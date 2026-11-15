"""Small catalogue, lifecycle and isolation checks for player-facing targets."""
import asyncio
import copy
import unittest
from unittest.mock import patch
import names
import mobs
import bosses
import sets
from training import catalog as range_catalog
from training import character as range_character
from training import formulas as range_formulas
from training import settings as range_settings
from training import session as tg
from training import opponents as catalogue
from training import profiles as installed_profiles
from protocol import decode
import test_training_ground as fixtures


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Production preloads optional strings before accepting connections.
        # Do not depend on another suite having constructed a Ground first.
        tg.preload()

    def test_reviewed_catalogue_has_names_groups_and_all_camp_bosses(self):
        choices = range_catalog.mob_catalogue()
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

    async def test_extended_scales_apply_once_and_do_not_modify_normal_mobs(self):
        g = self.enter()
        original = copy.deepcopy(vars(mobs.stats(g.mob_type)))
        for profile in installed_profiles.catalogue():
            g.rules = profile.rules
            base = None
            for health, damage in ((100, 100), (1, 10000), (888, 888), (10000, 1)):
                g.last_request = 0
                g.request(dict(op='start', token=g.token, mode='mob', stationary=1,
                               mob_health=health, mob_damage=damage))
                mob = g.room.combat.mobs[g.mob_eid]
                actual = (mob.hp_max, mob.sp_max, mob.stats.dmg_min, mob.stats.dmg_max)
                if base is None:
                    base = actual
                expected_min = max(0, round(base[2] * damage / 100))
                expected = (max(1, round(base[0] * health / 100)),
                            max(0, round(base[1] * health / 100)), expected_min,
                            max(expected_min, round(base[3] * damage / 100)))
                self.assertEqual(actual, expected, (profile.key, health, damage))
                g.room.broadcast(('lch', dict(id=mob.eid, **mob.vitals())))
                _, packet = decode(self.s.writer.frames[-1][:-1])
                self.assertEqual((packet['hmax'], packet['smax']), actual[:2])
                self.assertEqual(vars(mobs.stats(g.mob_type)), original)
                g.finish('test', force=True)
                await asyncio.sleep(0)  # Finish schedules the reset for the next loop turn.
                self.assertEqual(g.phase, 'ready')
                self.assertFalse(g.room.combat.mobs)
        self.unchanged()

    async def test_invalid_scales_are_rejected_without_starting_or_saving(self):
        g = self.enter()
        before = self.store.training_profile(self.s.char_id)
        for field in ('mob_health', 'mob_damage'):
            for invalid in (0, -1, 10001, '1.5', 'NaN', 'Infinity', True, '', None):
                g.last_request = 0
                request = dict(op='start', token=g.token, mode='mob', stationary=1,
                               mob_health=888, mob_damage=888)
                request[field] = invalid
                with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                    g.request(request)
                self.assertEqual((g.mob_health, g.mob_damage), (100, 100))
                self.assertEqual(g.phase, 'ready')
                self.assertFalse(g.room.combat.mobs)
                self.assertEqual(self.store.training_profile(self.s.char_id), before)
        self.unchanged()

    async def test_spawn_near_computer_and_each_group_can_finish_without_rewards(self):
        g = self.enter()
        self.assertEqual(g.spawn_point, 0)
        self.assertLess(g.distance, 20)
        for group in set(catalogue.GROUPS)-{'all'}:
            g.mob_type = next(t for t in range_catalog.mob_catalogue() if catalogue.RECORDS[t]['group'] == group)
            original = vars(mobs.stats(g.mob_type)).copy()
            g.start('mob')
            mob = g.room.combat.mobs[g.mob_eid]
            self.assertGreater(mob.cell % g.clone.loc.width, range_settings.COMPUTER_CELL % g.clone.loc.width)
            g.target_defeated(mob)
            self.assertEqual(g.phase, 'ready')
            self.assertIsNone(g.mob_eid)
            self.assertEqual(vars(mobs.stats(g.mob_type)), original)
        self.unchanged()


    async def test_category_level_choices_match_profile_before_search_and_paging(self):
        from dataclasses import replace
        g = self.enter()
        data = range_formulas.data() if range_formulas.available() else None
        for simulator in (p.rules.simulator_formulas for p in installed_profiles.catalogue()):
            g.rules = replace(g.rules, simulator_formulas=simulator)
            for group in catalogue.GROUPS:
                def level(t):
                    if simulator and str(t) in data['mobs']:
                        return data['mob_records'][data['mobs'][str(t)]]['level']
                    return mobs.stats(t).level
                expected = sorted({level(t) for t in range_catalog.mob_catalogue()
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

    async def test_unavailable_engine_cannot_replace_boss_stats(self):
        g = self.enter()
        g.mob_type = 8620
        original = mobs.stats(8620).level
        with patch.object(range_formulas, '_ENGINE', None):
            self.assertFalse(range_formulas.available())
            with self.assertRaises(ValueError):
                range_formulas.data()
        self.assertEqual(mobs.stats(8620).level, original)
        self.unchanged()

    async def test_selected_fighter_summary_reflects_set_and_custom_changes(self):
        g = self.enter()
        set_id = next(t for t,r in sets.SETS.items() if r['level'] == 12 and r['variant'] == 'A'
                      and all(m in range_catalog.item_catalogue() for m in r['members'].values()))
        g.opponent = g.fighter_preset(set_id)
        self.assertIn(sets.SETS[set_id]['name'],g.opponent_summary())
        g.opponent['gear'] = {}
        self.assertIn('Своя сборка',g.opponent_summary())
        self.assertIn('Без оружия',g.opponent_summary())

    async def test_hidden_old_target_does_not_discard_saved_character(self):
        g = self.enter()
        g.profile = range_character.validate_profile(range_character.preset(12))
        g.mob_type = 1081
        g.save_settings()
        restored = tg.Ground(self.s)
        try:
            self.assertEqual(max(restored.profile['skills']),12)
            self.assertIn(restored.mob_type,range_catalog.mob_catalogue())
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


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(Catalogue, Opponents)
