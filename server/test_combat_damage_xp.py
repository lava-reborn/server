"""Death-only combat XP: actual damage ownership, snapshots and live persistence."""
import copy
import gc
import logging
import os
from types import SimpleNamespace as NS
import unittest
import weakref
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import eden
import effects
import mobs
import progression as p
from test_combat_xp_cap import CombatXpCap
from testkit import run_cases


class DamageXp(unittest.TestCase):
    def setUp(self):
        calendar = patch.object(p, 'combat_calendar_multiplier', return_value=1)
        calendar.start()
        self.addCleanup(calendar.stop)
        self.fixture = CombatXpCap()
        self.serial = 0

    def fighter(self, level=12, premium=0, skill=p.SHOOTING):
        fighter, ch, spec = self.fixture.fighter(level, premium, skill)
        self.serial += 1
        fighter.sess.char_id = self.serial
        fighter.sess.combat = fighter
        fighter.sess.closed = False
        return fighter, ch, spec

    def mob(self):
        mob = mobs.Mob.__new__(mobs.Mob)
        mob.eid, mob.type_id = 900, 82
        mob.stats = NS(level=14, hp_max=100, sp_max=100, ap_max=100,
                       role='mob', xp_mult=1)
        mob.home = mob.cell = 0
        mob.hp, mob.sp, mob.ap = 100, 100, 100
        mob.alive, mob.target, mob.homing, mob.regen_at = True, None, False, 0
        mob.xp_ledger, mob.capture_harm, mob.loot_level = {}, {}, 0
        return mob

    def room(self, *fighters):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        rc.room = NS(loc=NS(id=100), players=[f.sess for f in fighters])
        rc.push_vitals = lambda _mob: None
        return rc

    def hit(self, fighter, mob, hp, sp=0, spec=2, skill=p.SHOOTING):
        hp_before, sp_before = mob.hp, mob.sp
        mob.apply_damage(hp, sp)
        fighter.award_xp(skill, spec,
                         hp_before - mob.hp + sp_before - mob.sp, mob)

    def skill_xp(self, ch, skill=p.SHOOTING, start=12):
        level, xp, _ceiling = ch.skill[skill]
        return sum(p.skill_xp_max(i) for i in range(start, level)) + xp + ch.xp_carry.get(skill, 0)

    def spec_xp(self, ch, spec):
        return self.fixture.spec_total(ch, spec) + ch.xp_carry.get(('spec', spec), 0)

    def test_no_experience_before_death_and_exact_100_90_10_99_1_shares(self):
        for first_damage in (100, 90, 99):
            with self.subTest(first_damage=first_damage):
                first, a, spec_a = self.fighter()
                second, b, spec_b = self.fighter()
                mob = self.mob()
                self.hit(first, mob, first_damage)
                self.hit(second, mob, 100 - first_damage)
                self.assertEqual(self.skill_xp(a), 0)
                self.assertEqual(self.skill_xp(b), 0)
                self.room(first, second).settle_xp(mob)
                reward = p.combat_mob_xp(14, 12)
                self.assertAlmostEqual(self.skill_xp(a), reward * first_damage / 100)
                self.assertAlmostEqual(self.skill_xp(b), reward * (100 - first_damage) / 100)
                self.assertAlmostEqual(self.spec_xp(a, spec_a), reward * first_damage / 100)
                self.assertAlmostEqual(self.spec_xp(b, spec_b), reward * (100 - first_damage) / 100)

    def test_weapon_99_1_divides_specialisations_and_fractional_residues(self):
        f, ch, first = self.fighter()
        second = 5
        ch.set_spec(second, 0)
        mob = self.mob()
        self.hit(f, mob, 99, spec=first)
        self.hit(f, mob, 1, spec=second)
        self.room(f).settle_xp(mob)
        reward = p.combat_mob_xp(14, 12)
        self.assertAlmostEqual(self.spec_xp(ch, first), reward * .99)
        self.assertAlmostEqual(self.spec_xp(ch, second), reward * .01)
        self.assertAlmostEqual(self.skill_xp(ch), reward)

    def test_each_skill_uses_its_damage_time_base_level(self):
        f, ch, first = self.fighter()
        ch.set_skill(p.MELEE, 0)
        ch.set_spec(0, 0)
        mob = self.mob()
        self.hit(f, mob, 90, spec=first)
        self.hit(f, mob, 10, spec=0, skill=p.MELEE)
        self.room(f).settle_xp(mob)
        self.assertAlmostEqual(self.skill_xp(ch), p.combat_mob_xp(14, 12) * .9)
        self.assertAlmostEqual(self.skill_xp(ch, p.MELEE, 0), p.combat_mob_xp(14, 0) * .1)
        self.assertAlmostEqual(self.spec_xp(ch, 0), p.combat_mob_xp(14, 0) * .1)

    def test_home_recovery_and_regeneration_never_create_extra_kill_prices(self):
        for same_player in (False, True):
            with self.subTest(same_player=same_player):
                first, a, spec_a = self.fighter()
                second, b, spec_b = (first, a, spec_a) if same_player else self.fighter()
                mob = self.mob()
                rc = self.room(first, second)
                self.hit(first, mob, 50, 50)
                rc.mob_recover(mob)
                self.assertEqual((mob.hp, mob.sp), (100, 100))
                self.hit(second, mob, 100)
                self.assertEqual(self.skill_xp(a), 0)
                rc.settle_xp(mob)
                reward = p.combat_mob_xp(14, 12)
                self.assertAlmostEqual(self.skill_xp(a), reward if same_player else reward / 2)
                if not same_player:
                    self.assertAlmostEqual(self.skill_xp(b), reward / 2)
        f, ch, _ = self.fighter()
        mob = self.mob()
        rc = self.room(f)
        self.hit(f, mob, 50)
        rc.regen_mob(mob, 60)
        self.assertEqual(mob.hp, 65)
        self.hit(f, mob, 65)
        rc.settle_xp(mob)
        self.assertAlmostEqual(self.skill_xp(ch), p.combat_mob_xp(14, 12))

    def test_damage_time_intux_residence_and_reduction_apply_once(self):
        for source, boost in ((3112, .1), (3113, .3), (3114, .5), (3561, .7)):
            for premium, residence in ((0, 0), (1, .15), (2, .3)):
                for reduction, factor in ((None, 1), (3205, .5), (3206, .2), (3207, .01)):
                    with self.subTest(source=source, premium=premium, reduction=reduction):
                        f, ch, spec = self.fighter(premium=premium)
                        active = {source: NS(source=source, deadline=10)}
                        if reduction:
                            active[reduction] = NS(source=reduction, deadline=10)
                        clock = [0]
                        f.sess.effects = NS(active=active, clock=lambda: clock[0])
                        mob = self.mob()
                        self.hit(f, mob, 100)
                        clock[0] = 100  # All effects have expired before settlement.
                        ch.premium_until = 1
                        self.room(f).settle_xp(mob)
                        reward = p.combat_mob_xp(14, 12) * (1 + boost + residence) * factor
                        self.assertAlmostEqual(self.skill_xp(ch), reward)
                        self.assertAlmostEqual(self.spec_xp(ch, spec), reward)

    def test_last_hit_buff_and_late_spec_do_not_reprice_old_damage(self):
        f, ch, spec = self.fighter()
        mob = self.mob()
        self.hit(f, mob, 99)
        ch.premium = 2
        f.sess.effects = NS(active={3561: NS(source=3561, deadline=10)}, clock=lambda: 0)
        self.hit(f, mob, 1)
        self.room(f).settle_xp(mob)
        self.assertAlmostEqual(self.skill_xp(ch), p.combat_mob_xp(14, 12) * 1.01)
        self.assertAlmostEqual(self.spec_xp(ch, spec), p.combat_mob_xp(14, 12) * 1.01)
        f, ch, spec = self.fighter()
        ch.forget_spec(spec)
        mob = self.mob()
        self.hit(f, mob, 100)
        ch.set_spec(spec, 0)
        self.room(f).settle_xp(mob)
        self.assertAlmostEqual(self.skill_xp(ch), p.combat_mob_xp(14, 12))
        self.assertEqual(self.spec_xp(ch, spec), 0)

    def test_skill_cap_and_pre_settlement_levels_do_not_reprice_other_buckets(self):
        f, ch, spec = self.fighter(16)
        ch.skill[p.SHOOTING][1] = ch.skill[p.SHOOTING][2] - 1
        second = 5
        ch.set_spec(second, 0)
        mob = self.mob()
        mob.stats.level = 18
        self.hit(f, mob, 90, spec=spec)
        self.hit(f, mob, 10, spec=second)
        self.room(f).settle_xp(mob)
        reward = p.combat_mob_xp(18, 16)
        self.assertEqual(ch.skill[p.SHOOTING], [17, 0, p.skill_xp_max(17)])
        self.assertAlmostEqual(self.spec_xp(ch, spec), reward * .9)
        self.assertAlmostEqual(self.spec_xp(ch, second), reward * .1)

    def test_reset_discards_unfinished_life_and_repeat_settlement_pays_nothing(self):
        f, ch, _ = self.fighter()
        mob = self.mob()
        self.hit(f, mob, 99)
        mob.reset()
        self.assertEqual(mob.xp_ledger, {})
        self.assertEqual(self.skill_xp(ch), 0)
        self.hit(f, mob, 10000, 10000)
        rc = self.room(f)
        rc.settle_xp(mob)
        before = copy.deepcopy((ch.skill, ch.spec, ch.xp_carry))
        rc.settle_xp(mob)
        self.assertEqual((ch.skill, ch.spec, ch.xp_carry), before)
        mob.alive = False
        f.award_xp(p.SHOOTING, 2, 200, mob)
        self.assertEqual(mob.xp_ledger, {})
        self.assertAlmostEqual(self.skill_xp(ch), p.combat_mob_xp(14, 12))

    def test_absent_damage_is_not_given_to_the_finisher_and_capture_is_unchanged(self):
        first, a, _ = self.fighter()
        second, b, _ = self.fighter()
        mob = self.mob()
        self.hit(first, mob, 90)
        self.hit(second, mob, 10)
        harm, loot_level = copy.copy(mob.capture_harm), mob.loot_level
        first.sess.closed = True
        self.room(second).settle_xp(mob)
        self.assertEqual(self.skill_xp(a), 0)
        self.assertAlmostEqual(self.skill_xp(b), p.combat_mob_xp(14, 12) * .1)
        self.assertEqual((mob.capture_harm, mob.loot_level), (harm, loot_level))

    def test_repeated_reconnects_keep_one_plain_damage_record_without_old_sessions(self):
        mob = self.mob()
        retired = []
        for _ in range(200):
            fighter, _ch, _spec = self.fighter()
            fighter.sess.char_id = 123
            mob.hp = 100
            self.hit(fighter, mob, 1)
            self.assertEqual(set(mob.xp_ledger), {123})
            retired.append(weakref.ref(fighter))
        del fighter
        gc.collect()
        self.assertTrue(all(ref() is None for ref in retired))
        self.assertEqual(mob.xp_ledger[123][0], 200)
        returned, ch, spec = self.fighter()
        returned.sess.char_id = 123
        mob.hp = 100
        self.hit(returned, mob, 100)
        rc = self.room(returned)
        rc.settle_xp(mob)
        reward = p.combat_mob_xp(14, 12)
        self.assertAlmostEqual(self.skill_xp(ch), reward)
        self.assertAlmostEqual(self.spec_xp(ch, spec), reward)
        before = self.skill_xp(ch)
        rc.settle_xp(mob)
        self.assertEqual(self.skill_xp(ch), before)

    def test_identity_record_keeps_live_level_guard_and_quest_loot_after_reconnect(self):
        first, _ch, _spec = self.fighter(14)
        mob = self.mob()
        mob.stats.level = 18
        self.hit(first, mob, 1)
        returned, current, _spec = self.fighter(14)
        returned.sess.char_id = first.sess.char_id
        returned.sess.inv = NS(bag_pieces=lambda: {})
        rc = self.room(returned)
        rc.store = object()
        self.assertEqual(rc.loot_multiplier(mob, None), 1.30)
        current.set_skill(p.SHOOTING, 15)
        self.assertEqual(rc.loot_multiplier(mob, None), 1.20)
        current.set_skill(p.SHOOTING, 10)
        self.assertEqual(rc.loot_multiplier(mob, None), 1.30)
        with patch.object(combat.mobs, 'quest_table', return_value=((1234, .5),)), \
                patch.object(combat.quests, 'wanted_things', return_value={1234}) as wanted:
            self.assertEqual(rc.quest_wants(mob, None), {1234})
            self.assertEqual(wanted.call_args.args[1], returned.sess.char_id)

    def test_objects_palms_and_private_training_never_produce_combat_xp(self):
        f, ch, _ = self.fighter()
        mob = self.mob()
        mob.stats.role = 'object'
        self.hit(f, mob, 100)
        self.room(f).settle_xp(mob)
        self.assertEqual(self.skill_xp(ch), 0)
        mob = self.mob()
        mob.type_id = next(iter(eden.PALMS))
        f.sess.loc.id = eden.CENTER
        self.hit(f, mob, 100)
        self.assertEqual(mob.xp_ledger, {})
        from training.arena import TrainingFighter
        TrainingFighter.award_xp(f, p.SHOOTING, 2, 100, self.mob())
        TrainingFighter.credit_xp(f, p.SHOOTING, 2, 1, self.mob(), reward=100)
        self.assertEqual(self.skill_xp(ch), 0)


class DamageXpPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_real_logout_login_merges_help_on_live_character_and_persists_once(self):
        from test_connection_entry import EntryFailures, Writer
        import accounts
        import server
        case = EntryFailures()
        await case.asyncSetUp()
        try:
            with patch.object(server, 'COMBAT_LINGER', 0):
                old, _other, _slot, mob = case.xp_characters('DamageXpRelog')
                self.assertEqual(old.char.skill[p.SHOOTING][1], 0)
                old_character, old_fighter = old.char, old.combat
                char_id = old.char_id
                slot = case.store.character(char_id)['slot']
                old.handle('logout', {})
                current = server.Session(Writer(), ('127.0.0.1', 99))
                case.sessions.append(current)
                current.handle('hello', {})
                current.handle('login', dict(hash=accounts.credential('DamageXpRelog', 'test-secret')))
                current.handle('selPers', dict(num=slot))
                current.handle('lenter', dict(accept=1))
                self.assertFalse(current.closed)
                self.assertIsNot(current.combat, old_fighter)
                current.combat.award_xp(p.SHOOTING, 2, 100, mob)
                current.char.set_spec(5, 0)
                current.combat.award_xp(p.SHOOTING, 5, 100, mob)
                rc = NS(room=current.room)
                with patch.object(current.char, 'save', wraps=current.char.save) as save:
                    combat.RoomCombat.settle_xp(rc, mob)
                save.assert_called_once_with(case.store)
                reward = p.combat_mob_xp(13, 12) * p.combat_calendar_multiplier()
                self.assertEqual(current.char.skill[p.SHOOTING][1], int(reward))
                self.assertEqual(old_character.skill[p.SHOOTING][1], 0)
                stored = p.Character.load(case.store, char_id)
                self.assertEqual(stored.skill, current.char.skill)
                self.assertEqual(stored.spec, current.char.spec)
                before = copy.deepcopy((stored.skill, stored.spec))
                combat.RoomCombat.settle_xp(rc, mob)
                self.assertEqual((p.Character.load(case.store, char_id).skill,
                                  p.Character.load(case.store, char_id).spec), before)
        finally:
            await case.asyncTearDown()
            case.doCleanups()


if __name__ == '__main__':
    run_cases(DamageXp, DamageXpPersistence)
