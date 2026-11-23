"""Room-local world boss defence ceilings; no calibrated battles or RNG."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import battle_balance as balance
import combat
import mobs
import rooms
import world
from testkit import run_cases


def player(level):
    return NS(is_player=True, character=lambda: NS(level=level), armor=lambda: 15)


def context(location):
    room = rooms.Rooms(world.mob_types()).get(location)
    return combat.RoomCombat(room, None)


def boss(rc, type_id):
    return next(mob for mob in rc.mobs.values() if mob.type_id == type_id)


class BossLocalResistance(unittest.TestCase):
    def test_janjaweed_room_ceiling_does_not_mutate_stats_or_pools(self):
        for location, type_id, actual in ((84, 299, 9), (86, 300, 8)):
            before = deepcopy(vars(mobs.stats(type_id)))
            rc = context(location)
            mob = boss(rc, type_id)
            self.assertEqual(mob._world_boss_defence_ceiling, (6, 34.5, 12.21875))
            self.assertEqual(balance.target_defence_level(mob, True), 6)
            self.assertEqual(mob.stats.level, actual)
            self.assertEqual((mob.hp, mob.sp), (mob.stats.hp_max, mob.stats.sp_max))
            self.assertEqual(vars(mob.stats), before)

    def test_janjaweed_player_five_penetrates_hp_and_recovers_native_antikrit(self):
        for location, type_id in ((84, 299), (86, 300)):
            mob = boss(context(location), type_id)
            shooter = player(5)
            after = balance.split(shooter, mob, 81, 1, False, mob.sp, ordinary=True)
            chance = balance.critical_chance(shooter, mob, 30 - mob.crit_evade_ranged(), ordinary=True)
            ceiling = mob._world_boss_defence_ceiling
            mob._world_boss_defence_ceiling = None
            before = balance.split(shooter, mob, 81, 1, False, mob.sp, ordinary=True)
            old_chance = balance.critical_chance(shooter, mob, 30 - mob.crit_evade_ranged(), ordinary=True)
            mob._world_boss_defence_ceiling = ceiling
            self.assertGreater(after[0], 0)
            self.assertGreater(after[0], before[0])
            self.assertGreater(chance, old_chance)
            self.assertEqual(mob.crit_evade_ranged(), mob.crit_evade_melee())
            self.assertEqual(balance.critical_chance(shooter, mob, 30 - mob.crit_evade_melee(), ordinary=True), chance)

    def test_all_recorded_rooms_use_highest_native_ordinary_level(self):
        manager = rooms.Rooms(world.mob_types())
        checked, empty = 0, 0
        for type_id, record in balance.world_boss_damage_references().items():
            for location in record['locations']:
                room = manager.get(location)
                rc = combat.RoomCombat(room, None)
                mob = mobs.Mob(-1, type_id, 0)
                rc.mobs[-1] = mob
                before = deepcopy(vars(mob.stats))
                balance.prepare_world_boss_defence(rc, mob)
                ordinary = [other.stats for other in rc.mobs.values()
                            if other.stats.role in ('mob', 'animal', 'turret')
                            and other.stats.can_attack and not getattr(other, '_holding_prepared', False)]
                if ordinary:
                    highest = max(st.level for st in ordinary)
                    peers = [st for st in ordinary if st.level == highest]
                    self.assertEqual(mob._world_boss_defence_ceiling,
                                     (highest, max(st.armor for st in peers), max(st.crit_evade for st in peers)))
                    self.assertLessEqual(balance.target_defence_level(mob, True), min(mob.stats.level - 2, highest))
                    checked += 1
                else:
                    self.assertIsNone(mob._world_boss_defence_ceiling)
                    self.assertEqual(balance.target_defence_level(mob, True), mob.stats.level - 2)
                    empty += 1
                self.assertEqual(vars(mob.stats), before)
        self.assertGreaterEqual(checked, 37)
        self.assertGreater(empty, 0)

    def test_nubia_three_and_four_have_finite_penetration_without_pool_reduction(self):
        for location, type_id in ((34, 2103), (80, 270), (82, 269), (81, 283), (83, 284)):
            mob = boss(context(location), type_id)
            hp, sp = mob.hp, mob.sp
            for level in (3, 4):
                # A finite native split, with full SP rather than a depleted dummy.
                health, stamina = balance.split(player(level), mob, 60, 1, False, sp, ordinary=True)
                self.assertGreater(health + stamina, 0)
                self.assertGreater(balance.split(player(level), mob, 60, 1, False, 0, ordinary=True)[0], 0)
            self.assertEqual((mob.hp, mob.sp), (hp, sp))

    def test_rifle_ceiling_never_increases_any_previously_weaker_boss_resistance(self):
        for location, type_id in ((84, 299), (86, 300), (34, 2103), (80, 270), (82, 269)):
            mob = boss(context(location), type_id)
            ceiling = mob._world_boss_defence_ceiling
            for level in range(1, 18):
                for piercing in (.5, 1, 2):
                    after = balance.split(player(level), mob, 100, piercing, False, mob.sp, rifle=True, ordinary=True)
                    mob._world_boss_defence_ceiling = None
                    before = balance.split(player(level), mob, 100, piercing, False, mob.sp, rifle=True, ordinary=True)
                    mob._world_boss_defence_ceiling = ceiling
                    self.assertGreaterEqual(after[0], before[0])
                    self.assertGreaterEqual(sum(after), sum(before))

    def test_private_and_prepared_defenders_do_not_use_local_caps(self):
        for attribute in ('_holding_prepared', 'training_ground'):
            mob = boss(context(84), 299)
            setattr(mob, attribute, True)
            self.assertIsNone(balance.world_boss_defence(mob, True))
            mob._world_boss_defence_ceiling = None
            before = balance.split(player(5), mob, 81, 1, False, mob.sp, ordinary=True)
            mob._world_boss_defence_ceiling = (1, 0, 0)
            self.assertEqual(balance.split(player(5), mob, 81, 1, False, mob.sp, ordinary=True), before)
        mob = boss(context(84), 299)
        self.assertIsNone(balance.world_boss_defence(mob, False))
        self.assertEqual(balance.target_defence_level(mob, False), mob.stats.level)

    def test_boss_outgoing_attacks_and_ordinary_targets_are_unchanged(self):
        rc = context(84)
        mob = boss(rc, 299)
        target = next(m for m in rc.mobs.values() if m.stats.role == 'mob')
        for shooter, recipient in ((mob, player(5)), (player(5), target)):
            previous = balance.split(shooter, recipient, 40, 1, False, 300, ordinary=True)
            chance = balance.critical_chance(shooter, recipient, 20, ordinary=True)
            saved = mob._world_boss_defence_ceiling
            mob._world_boss_defence_ceiling = None
            self.assertEqual(balance.split(shooter, recipient, 40, 1, False, 300, ordinary=True), previous)
            self.assertEqual(balance.critical_chance(shooter, recipient, 20, ordinary=True), chance)
            mob._world_boss_defence_ceiling = saved

    def test_newly_arriving_quest_boss_receives_the_room_ceiling(self):
        rc = context(34)
        mob = mobs.Mob(-1, 2103, 0)
        rc.mobs[-1] = mob
        mob.alive = False
        rc.room.players = []
        with patch.object(combat.movement, 'get', return_value=NS(free_cell=lambda cell, **kw: cell)):
            rc.respawn(mob)
        self.assertTrue(mob.alive)
        self.assertEqual(mob._world_boss_defence_ceiling, (4, 27.5, 12))

    def test_killed_ordinary_peers_still_define_the_location(self):
        rc = context(84)
        for mob in rc.mobs.values():
            if mob.stats.role == 'mob':
                mob.alive = False
        target = boss(rc, 299)
        balance.prepare_world_boss_defence(rc, target)
        self.assertEqual(target._world_boss_defence_ceiling, (6, 34.5, 12.21875))


if __name__ == '__main__':
    run_cases(BossLocalResistance)
