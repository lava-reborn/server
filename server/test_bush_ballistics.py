"""Verified foliage passes shots with reduced damage; hard cover stops them."""
from types import SimpleNamespace as NS
import copy
import unittest
from unittest.mock import patch

import combat
import mobs
from testkit import run_cases


class Body:
    is_player = False

    def __init__(self, cell):
        self.cell = cell
        self.stats = NS(level=10, role='object')

    def sp_now(self):
        return 1000

    def armor(self):
        return 0


class BushBallistics(unittest.TestCase):
    def scene(self, bushes=(), hard=(), targets=(50,), critical=False):
        loc = NS(width=20, height=5, obstacles=set(bushes) | set(hard),
                 bushes=frozenset(bushes), shoot_over=frozenset())
        shooter = NS(cell=40, is_player=True, character=lambda: NS(level=10))
        bodies = [Body(cell) for cell in targets]
        rc = object.__new__(combat.RoomCombat)
        rc.room = NS(loc=loc)
        rc.bodies = lambda *_: {body.cell: body for body in bodies}
        rc.ranged_critical = lambda *_: critical
        weapon = combat.Weapon(1, 100, 100, 0, 15, 15, 1, 0, 0, None, None,
                               sdmin=40, sdmax=40)
        return loc, rc, shooter, bodies, weapon

    def shoot(self, bushes=(), hard=(), *, critical=False, shots=1):
        loc, rc, shooter, bodies, weapon = self.scene(bushes, hard, critical=critical)
        with patch.object(combat, 'bullet_offset', return_value=0):
            pairs, struck = rc.resolve(shooter, bodies[0], bodies[0].cell,
                                       weapon._replace(num_shots=shots), shots)
        return loc, pairs, struck.get(bodies[0])

    def test_bush_hit_loses_one_quarter_of_both_damage_components(self):
        _, clear, damage = self.shoot()
        self.assertEqual(damage[:3], [100, 40, 1])
        loc, covered, damage = self.shoot((44, 45, 46))
        self.assertEqual(damage[:3], [75, 30, 1])
        self.assertIsNone(clear[0][0])
        self.assertIsNone(covered[0][0])
        self.assertEqual(loc.obstacles, {44, 45, 46})

    def test_multiple_bush_cells_do_not_compound_damage_loss(self):
        for cells in ((43,), (43, 44, 47, 48)):
            with self.subTest(cells=cells):
                _, pairs, damage = self.shoot(cells, shots=4)
                self.assertEqual(damage[:3], [300, 120, 4])
                self.assertEqual(len(pairs), 4)

    def test_bush_beyond_target_does_not_reduce_its_damage(self):
        _, _, damage = self.shoot((52, 53))
        self.assertEqual(damage[:3], [100, 40, 1])

    def test_critical_hits_keep_foliage_reduction(self):
        _, _, damage = self.shoot((45,), critical=True)
        self.assertEqual(damage[:3], [75, 75, 1])

    def test_tree_stone_or_wall_still_stops_shot_after_or_before_bush(self):
        for hard in (42, 47):
            loc, pairs, damage = self.shoot((45,), (hard,))
            self.assertIsNone(damage)
            self.assertEqual(pairs, [(('faWall', {'hex': hard}), [])])
            self.assertEqual(combat.shot_wall(loc, 40, 50), hard)
            passed, end = combat.flight(loc, 40, 50, 0, 15)
            self.assertEqual((passed, end), ([], ('faWall', {'hex': hard})))

    def test_rifle_penetration_only_reduces_body_beyond_the_bush(self):
        loc, rc, shooter, bodies, weapon = self.scene((47,), targets=(45, 50))
        with patch.object(combat, 'bullet_offset', return_value=0):
            _, struck = rc.resolve(shooter, bodies[0], bodies[0].cell,
                                   weapon._replace(through=True), 1)
        self.assertEqual(struck[bodies[0]][:3], [100, 40, 1])
        self.assertEqual(struck[bodies[1]][:3], [37, 15, 1])

    def test_stray_ray_records_only_bushes_it_actually_crosses(self):
        loc, _, shooter, bodies, _ = self.scene((45,), targets=(50,))
        crossed = []
        combat.flight(loc, shooter.cell, bodies[0].cell, 0, 15, bush_hits=crossed)
        self.assertTrue(crossed)
        crossed = []
        combat.flight(loc, shooter.cell, bodies[0].cell, 5, 15, bush_hits=crossed)
        self.assertFalse(crossed)

    def test_range_counter_exception_remains_shootable_without_foliage_loss(self):
        loc, rc, shooter, bodies, weapon = self.scene(hard=(45,))
        loc.shoot_over = frozenset({45})
        self.assertIsNone(combat.shot_wall(loc, shooter.cell, bodies[0].cell))
        with patch.object(combat, 'bullet_offset', return_value=0):
            _, struck = rc.resolve(shooter, bodies[0], bodies[0].cell, weapon, 1)
        self.assertEqual(struck[bodies[0]][:3], [100, 40, 1])

    def test_burst_prepares_obstacle_view_once_for_all_pellets(self):
        loc, rc, shooter, bodies, weapon = self.scene((45,))
        with patch.object(combat, '_Sights', wraps=combat._Sights) as view, \
                patch.object(combat, 'bullet_offset', return_value=0):
            _, struck = rc.resolve(shooter, bodies[0], bodies[0].cell,
                                   weapon._replace(num_shots=20), 20)
        self.assertEqual(view.call_count, 1)
        self.assertEqual(struck[bodies[0]][2], 20)

    def test_cleared_private_arena_does_not_keep_original_foliage(self):
        from training import geometry
        original = NS(width=64, height=128, obstacles={45}, bushes=frozenset({45}),
                      shoot_over=frozenset(), entries=[], spawns=[])
        geometry.arena_location.cache_clear()
        self.addCleanup(geometry.arena_location.cache_clear)
        with patch.object(geometry.world, 'location', return_value=original):
            loc = geometry.arena_location()
        self.assertFalse(loc.bushes)
        self.assertFalse(loc.obstacles)
        self.assertEqual(original.bushes, frozenset({45}))

    def mob_scene(self, bushes=(), hard=()):
        loc, rc, _, bodies, weapon = self.scene(bushes, hard)
        mob = mobs.Mob(1, 258, 40)
        mob.stats = copy.copy(mob.stats)
        mob.stats.ranged, mob.stats.range = True, weapon.max_range
        mob.stats.moves, mob.stats.attack_ap = True, 1
        mob.stats.weapon_class = 'pistol'
        mob.ap = 100
        target = NS(cell=50, present=lambda _rc: True)
        mob.target = target
        calls, goals = [], []
        rc.mob_attack = lambda *_: calls.append('attack')
        rc.mob_walk = lambda _mob, goal, _now: (calls.append('walk'), goals.append(goal))
        return loc, rc, mob, bodies, weapon, calls, goals

    def test_ranged_mob_attacks_through_verified_bush_instead_of_walking_around(self):
        for bushes in ((), (45,), (43, 45, 47)):
            loc, rc, mob, _, _, calls, goals = self.mob_scene(bushes)
            mob.think(rc, 100)
            self.assertEqual(calls, ['attack'], bushes)
            self.assertFalse(goals)
            self.assertEqual(loc.obstacles, set(bushes))

    def test_ranged_mob_walking_goal_ignores_bush_but_keeps_hard_cover(self):
        for hard in (42, 47):
            loc, rc, mob, _, _, calls, goals = self.mob_scene((45,), (hard,))
            mob.think(rc, 100)
            self.assertEqual(calls, ['walk'])
            self.assertFalse(goals[0](mob.cell))
            # A candidate beyond the solid obstacle can fire back through
            # the remaining bush. It is a walk goal, never a free teleport.
            self.assertTrue(goals[0](hard + 1))
            self.assertEqual(loc.obstacles, {45, hard})

    def test_ranged_mob_bullets_lose_the_same_quarter_as_player_bullets(self):
        for bushes, hard, expected in (((), (), [100, 40, 1]),
                                       ((45,), (), [75, 30, 1]),
                                       ((43, 45, 47), (), [75, 30, 1]),
                                       ((45,), (47,), None)):
            with self.subTest(bushes=bushes, hard=hard):
                _, rc, mob, bodies, weapon, _, _ = self.mob_scene(bushes, hard)
                with patch.object(combat, 'bullet_offset', return_value=0):
                    _, struck = rc.resolve(mob, bodies[0], bodies[0].cell, weapon, 1)
                damage = struck.get(bodies[0])
                self.assertEqual(damage[:3] if damage else None, expected)

    def test_ranged_mob_ai_with_no_bushes_keeps_ordinary_wall_and_ap_rules(self):
        for hard, ap, expected in (((), 100, ['attack']), ((45,), 100, ['walk']),
                                   ((), 0, [])):
            loc, rc, mob, _, _, calls, _ = self.mob_scene(hard=hard)
            mob.ap = ap
            mob.think(rc, 100)
            self.assertEqual(calls, expected)
            self.assertFalse(loc.bushes)


if __name__ == '__main__':
    run_cases(BushBallistics)
