"""Native impact, wire and follow-up boundaries of the narrow MG pull guard."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import items
import mobs
import progression
from testkit import run_cases


class Player:
    is_player = True

    def __init__(self, level, cell=1):
        self.ch = progression.Character()
        self.ch.set_skill(progression.SHOOTING, level)
        self.ch.hp, self.ch.sp = self.ch.hp_max, self.ch.sp_max
        self.level = level
        self.cell = cell
        self.eid = cell + 100
        self.store = NS()
        self.sess = NS(inv=NS(wear_worn=Mock()))

    def character(self):
        return self.ch

    def vitals(self):
        return self.ch.vitals()

    def sp_now(self):
        return self.vitals()['scur']

    def armor(self):
        return 0

    def present(self, rc):
        return True

    def apply_damage(self, hp, sp):
        return combat.Fighter.apply_damage(self, hp, sp)


class MachinegunBurstSurvival(unittest.TestCase):
    def scene(self, shooter, target, kind=items.MACHINEGUN, shots=10, critical=False):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        frames = []
        rc.room = NS(loc=NS(id=0, width=20, height=20, obstacles=set()),
                     broadcast=frames.append)
        rc.bodies = lambda *args: {}
        rc.ranged_critical = Mock(return_value=critical)
        rc.hit_landed = rc.push_vitals = Mock()
        weapon = combat.Weapon(shots, 100, 100, 1, 20, 20, 0, 0, 100,
                               progression.SHOOTING, combat.SPEC_OF_WEAPON[kind])
        return rc, weapon, frames

    def burst(self, rc, shooter, target, weapon):
        with patch.object(combat, 'shot_wall', return_value=None), \
                patch.object(combat, 'bodies_between', return_value=[]), \
                patch.object(combat, 'bullet_offset', return_value=0), \
                patch.object(combat.eden_harvest, 'before_native_damage'):
            return rc.burst(shooter, target, target.cell, weapon, weapon.num_shots)

    def test_healthy_player_keeps_thirty_percent_of_impact_hp_then_can_be_finished(self):
        for gap in (-1, 0, 1, 2):
            for critical in (False, True):
                for hurt in (0, 1):
                    with self.subTest(gap=gap, critical=critical, hurt=hurt):
                        shooter, target = Player(16, 0), Player(16-gap)
                        target.ch.hp -= hurt
                        rc, weapon, frames = self.scene(shooter, target, critical=critical)
                        hp = target.ch.hp
                        damage = hp * 7 // 10
                        h, s, hits, killed = self.burst(rc, shooter, target, weapon)
                        self.assertEqual((h, hits, killed, target.ch.hp), (damage, 10, False, hp-damage))
                        self.assertEqual(sum(p['dmg'] for cmd, p in frames if cmd == 'faHit'), h)
                        self.assertEqual(sum(p['sdmg'] for cmd, p in frames if cmd == 'faHit'), s)
                        self.assertTrue(self.burst(rc, shooter, target, weapon)[3])
                        self.assertEqual(target.ch.hp, 0)

    def test_exact_health_threshold_and_stamina_do_not_change_the_rule(self):
        shooter, target = Player(16, 0), Player(16)
        _, weapon, _ = self.scene(shooter, target)
        for hp, expected in ((89, None), (90, None), (91, 63), (100, 70)):
            for stamina in (0, 1, 100):
                target.vitals = lambda: dict(hcur=hp, hmax=100, scur=stamina, smax=100)
                self.assertEqual(combat.machinegun_burst_limit(shooter, target, weapon), expected)

    def test_wounded_lower_level_and_other_classes_stay_lethal(self):
        for shooter_level, target_level, kind, wounded in (
                (16, 16, items.MACHINEGUN, True), (16, 13, items.MACHINEGUN, False),
                (16, 12, items.MACHINEGUN, False), (16, 16, items.ASSAULT, False),
                (16, 16, items.RIFLE, False), (16, 16, items.SHOTGUN, False)):
            with self.subTest(levels=(shooter_level, target_level), kind=kind, wounded=wounded):
                shooter, target = Player(shooter_level, 0), Player(target_level)
                if wounded:
                    target.ch.hp = target.ch.hp_max * 9 // 10
                rc, weapon, _ = self.scene(shooter, target, kind=kind)
                self.assertTrue(self.burst(rc, shooter, target, weapon)[3])

    def test_final_ammo_bonus_cannot_bypass_the_burst_health_limit(self):
        shooter, target = Player(16, 0), Player(16)
        rc, weapon, _ = self.scene(shooter, target, critical=True)
        weapon = weapon._replace(hp_multiplier=1.3, sp_multiplier=1.3)
        hp = target.ch.hp
        h, _, _, killed = self.burst(rc, shooter, target, weapon)
        self.assertEqual((h, killed, target.ch.hp), (hp*7//10, False, hp-hp*7//10))

    def test_single_shot_and_player_to_mob_have_no_health_guard(self):
        shooter,target=Player(16,0),Player(16)
        rc,weapon,_=self.scene(shooter,target,shots=1)
        self.assertIsNone(combat.machinegun_burst_limit(shooter,target,weapon))
        mob=mobs.Mob(2,20,1)
        self.assertIsNone(combat.machinegun_burst_limit(shooter,mob,weapon._replace(num_shots=10)))

    def test_native_machinegun_mob_obeys_the_same_impact_boundary(self):
        for critical in (False,True):
            with self.subTest(critical=critical):
                shooter=mobs.Mob(9,931,0)
                self.assertEqual(items.params_of(shooter.stats.weapon_type_id)['weapon_type'],items.MACHINEGUN)
                target=Player(shooter.level)
                rc,weapon,frames=self.scene(shooter,target,critical=critical)
                weapon=weapon._replace(skill=None,spec=None)
                h,s,hits,killed=self.burst(rc,shooter,target,weapon)
                self.assertEqual((h,killed,target.ch.hp),(target.ch.hp_max*7//10,False,target.ch.hp_max-target.ch.hp_max*7//10))
                self.assertEqual(sum(p['dmg'] for cmd,p in frames if cmd=='faHit'),h)
                self.assertGreater(hits,1)


if __name__=='__main__':
    run_cases(MachinegunBurstSurvival)
