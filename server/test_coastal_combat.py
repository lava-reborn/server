"""Ordinary XP, gold-tier natural attacks and XP-only strengthened patrols."""
import asyncio
import copy
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import accounts
import battle_balance as balance
import coasts
import combat
import location_entry
import mobs
import progression as p
import rooms
import world
from test_combat_damage_xp import DamageXp
from test_mob_penetration import afro_character, afro_modes
from testkit import run_cases


class CoastalCombat(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = accounts.Store(':memory:')
        self.active = []

    async def asyncTearDown(self):
        for rc in self.active:
            for mob in rc.mobs.values():
                if mob.aim is not None:
                    mob.aim.cancel()
            for bag in rc.loot.values():
                if bag.expiry is not None:
                    bag.expiry.cancel()
        self.store.close()

    def room(self, loc_id):
        room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), world.mob_types())
        rc = combat.RoomCombat(room, self.store)
        room.combat = rc
        self.active.append(rc)
        return rc

    async def test_all_spawned_profiles_keep_native_melee_and_common_balance_limits(self):
        for loc_id, type_id in coasts.profiles():
            rc = self.room(loc_id)
            level = coasts.profiles()[loc_id, type_id]
            reference = balance.ordinary_mob_reference()[0][level]
            original = copy.copy(mobs.stats(type_id).__dict__)
            for mob in rc.mobs.values():
                with self.subTest(location=loc_id, mob=mob.eid):
                    self.assertEqual(mob.level, level)
                    self.assertEqual(mob.stats.role, 'animal')
                    self.assertEqual(mob.stats.xp_mult, 1.0)
                    self.assertEqual(mob.stats.range, 1)
                    self.assertEqual(mob.stats.aggro, 5)
                    self.assertTrue(mob.stats.moves)
                    self.assertFalse(mob.stats.ranged)
                    self.assertIsNone(mob.stats.weapon_type_id)
                    self.assertEqual(mob.hp_max,max(round(mobs.LEVELS[str(level)]['hp']*mobs.ROLES['mob']['hp_mult']),round(reference['hp_max']/balance.MOB_BALANCE_DIVISOR)))
                    for field in ('armor','hit','dodge','crit','crit_evade'):
                        self.assertEqual(getattr(mob.stats,field), reference[field])
                    attack=coasts.fangs(level)
                    self.assertEqual((mob.stats.dmg_min,mob.stats.dmg_max,mob.stats.attack_ap),
                        (attack['h_damage_min'],attack['h_damage_max'],attack['strike_cost']))
                    self.assertEqual(mob.stats.attack_name,'Клыки')
                    self.assertEqual(mob.stats.attack_time,attack['strike_time']/1000)
                    self.assertEqual(mob.ap, mob.ap_max)
            self.assertEqual(mobs.stats(type_id).__dict__, original)

    async def test_every_edge_arrival_starts_outside_native_crocodile_aggro(self):
        for loc_id, _type_id in coasts.profiles():
            rc = self.room(loc_id)
            loc = rc.room.loc
            occupied = {m.cell for m in rc.mobs.values()}
            self.assertEqual(len(occupied),len(rc.mobs))
            entries = {cell for cell,_exit in location_entry._geometry(loc).approaches}
            for mob in rc.mobs.values():
                self.assertNotIn(mob.home,loc.obstacles)
                self.assertEqual(mob.home,mob.cell)
                self.assertEqual(rc.room.npcs[mob.eid].cell,mob.cell)
                self.assertGreater(min(mobs.hex_distance(mob.cell,e,loc.width) for e in entries),
                                   mob.stats.aggro,(loc_id,mob.home))
                self.assertIsNotNone(mobs.find_path(loc,mob.home,lambda c:c in entries,limit=8192))

    async def test_no_loot_even_with_scanner_quest_events_and_production(self):
        before = self.store.db.execute('SELECT COUNT(*) FROM items').fetchone()[0]
        for loc_id, type_id in coasts.profiles():
            rc = self.room(loc_id)
            mob = next(iter(rc.mobs.values()))
            mob.quest_wants = frozenset((4326,))
            mob.loot_multiplier = mob.gold_loot_multiplier = mob.scanner_multiplier = 20
            self.assertEqual(mobs.loot_for(mob.stats,random.Random(1),mob.quest_wants,
                loc_id=loc_id, multiplier=20, gold_multiplier=20, scanner_multiplier=20), [])
            with patch.object(combat.events,'loot',return_value=[(7620,4)]), \
                    patch.object(combat.production,'yield_of',return_value=[(1752,1)]):
                self.assertEqual(rc.drop_loot(mob), [])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM items').fetchone()[0], before)
        # The shared level-12 type still drops meat and requested eggs at its quest site.
        self.assertFalse(coasts.without_loot(189,130))
        rolled = mobs.loot_for(mobs.stats(130), random.Random(1), (4326,), loc_id=189)
        self.assertIn((1752,1),rolled)
        self.assertIn((4326,1),rolled)
        self.assertFalse(coasts.without_loot(168,1035))

    async def test_level_19_magrib_patrol_pays_normal_xp_and_never_generates_items(self):
        st=mobs.stats(98)
        self.assertEqual(st.level,19)
        self.assertEqual(st.xp_mult,1.0)
        self.assertTrue(coasts.without_loot(6,98))
        for seed in range(20):
            self.assertEqual(mobs.loot_for(st,random.Random(seed),(4326,),loc_id=6,
                multiplier=20,gold_multiplier=20,scanner_multiplier=20),[])
        rc=self.room(17)
        mob=NS(type_id=98,stats=st,quest_wants=frozenset((4326,)))
        with patch.object(combat.events,'loot',return_value=[(7620,4)]), \
                patch.object(combat.production,'yield_of',return_value=[(1752,1)]):
            self.assertEqual(rc.drop_loot(mob),[])
        self.assertEqual(st.xp_mult,1.0)

    async def test_patrol_has_double_hp_and_real_gold_damage_blueprint_weapon(self):
        import inventory,items,names
        original=copy.deepcopy(mobs.stats(98).__dict__)
        room=rooms.Room(world.location(6),rooms.IdAllocator(),world.mob_types())
        room.npcs={100:rooms.NPC(1300,98,world.MOB)}
        rc=combat.RoomCombat(room,self.store);room.combat=rc;self.active.append(rc)
        mob=rc.mobs[100]
        self.assertEqual(mob.hp_max,2*original['hp_max'])
        self.assertEqual(mob.sp_max,original['sp_max'])
        self.assertEqual(mob.stats.weapon_type_id,25078)
        self.assertEqual(items.catalogue()[25078][1],'machine_gun_1_lvl_19_mod_damage_gold')
        self.assertEqual(mob.stats.xp_mult,1)
        self.assertEqual(names.text(98),'Патрульный Магриба')
        self.assertEqual(inventory.parse_oid(str(mob.weapon_oid()))[1],25078)
        old=items.params_of(original['weapon_type_id']);gold=items.params_of(25078)
        for index,mode in enumerate(mob.stats.balanced_modes):
            self.assertEqual(mode['dmin'],round(original['balanced_modes'][index]['dmin']*gold['h_damage_min'][index]/old['h_damage_min'][index]))
            self.assertEqual(mode['dmax'],round(original['balanced_modes'][index]['dmax']*gold['h_damage_max'][index]/old['h_damage_max'][index]))
        frames=[];viewer=NS(rc=rc,sess=NS(room=room,send=lambda cmd,**p:frames.append((cmd,p))))
        self.assertTrue(combat.Fighter.ss_get_di(viewer,{'obj':str(mob.weapon_oid())}))
        self.assertEqual(frames[-1][1]['ammo_type'],mob.stats.loot_ammo_type)
        self.assertEqual(mobs.stats(98).__dict__,original)
        coasts.prepare_room(rc)
        self.assertEqual(mob.hp_max,2*original['hp_max'])
        fixture=DamageXp();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fighter,ch,spec=fixture.fighter(16);rc.room.players=[fighter.sess]
        fixture.hit(fighter,mob,mob.hp,mob.sp,spec=spec);rc.settle_xp(mob)
        expected=p.combat_mob_xp(19,16,xp_mult=1)
        self.assertAlmostEqual(fixture.skill_xp(ch,start=16),expected)
        rc.settle_xp(mob)
        self.assertAlmostEqual(fixture.skill_xp(ch,start=16),expected)
        rc.room.players={}

    async def test_patrol_gold_weapon_does_not_enable_legacy_extra_pressure(self):
        # The gold item's higher bounds are already applied by patrol_stats.
        # Resolve a fixed impact through the real ordinary combat policy:
        # an additional legacy multiplier or SP shock was never approved.
        patrol=coasts.patrol_stats()
        shooter=NS(is_player=False,stats=patrol)
        character=p.Character()
        character.set_skill(p.SHOOTING,17)
        target=NS(is_player=True,character=lambda:character,armor=lambda:0)
        for critical,expected in ((False,(40,0)),(True,(40,40))):
            with self.subTest(critical=critical):
                self.assertEqual(balance.split(shooter,target,40,.9,critical,1000,
                                               ordinary=True),expected)

    async def test_fangs_use_native_gold_knife_values_without_creating_an_item(self):
        self.assertEqual(tuple(coasts.fangs(4)[k] for k in ('h_damage_min','h_damage_max')),(37,49))
        self.assertEqual(tuple(coasts.fangs(11)[k] for k in ('h_damage_min','h_damage_max')),(68,111))
        self.assertEqual(tuple(coasts.fangs(12)[k] for k in ('h_damage_min','h_damage_max')),(74,124))
        self.assertEqual(tuple(coasts.fangs(17)[k] for k in ('h_damage_min','h_damage_max')),(115,223))

    async def test_real_death_and_natural_respawn_keep_empty_ground_and_local_profile(self):
        for loc_id in (17,21,20,38):
            rc = self.room(loc_id)
            mob = next(iter(rc.mobs.values()))
            before = (mob.level,mob.hp_max,mob.sp_max,mob.stats.armor)
            loop = asyncio.get_running_loop()
            respawn = loop.create_future()
            real_respawn = rc.respawn
            def record_respawn(target):
                real_respawn(target)
                if not respawn.done():
                    respawn.set_result(None)
            with patch.object(combat,'CORPSE_DELAY',.001), \
                    patch.object(combat,'RESPAWN_DELAY',.001), \
                    patch.object(rc,'respawn',side_effect=record_respawn):
                rc.kill(mob,None)
                self.assertFalse(mob.alive)
                await asyncio.wait_for(respawn, 1)
            self.assertTrue(mob.alive)
            self.assertFalse(mob.away)
            self.assertEqual((mob.level,mob.hp_max,mob.sp_max,mob.stats.armor),before)
            self.assertEqual((mob.hp,mob.sp,mob.ap),(mob.hp_max,mob.sp_max,mob.ap_max))
            self.assertIn(mob.eid,rc.room.npcs)
            self.assertEqual(rc.loot,{})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM items').fetchone()[0],0)

    async def test_death_pays_exact_common_xp_once_using_the_local_level(self):
        fixture = DamageXp()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for loc_id, player_level in ((17,3),(21,10),(20,11),(38,15)):
            rc = self.room(loc_id)
            mob = next(iter(rc.mobs.values()))
            fighter,ch,spec = fixture.fighter(player_level)
            # The fixture session is not hashable; a list is enough for the
            # real settlement, which iterates the active subscribers.
            rc.room.players = [fighter.sess]
            fixture.hit(fighter,mob,mob.hp,mob.sp,spec=spec)
            self.assertEqual(fixture.skill_xp(ch,start=player_level),0)
            rc.settle_xp(mob)
            expected = p.combat_mob_xp(mob.level,player_level,xp_mult=1)
            self.assertAlmostEqual(fixture.skill_xp(ch,start=player_level),expected)
            rc.settle_xp(mob)
            self.assertAlmostEqual(fixture.skill_xp(ch,start=player_level),expected)
            rc.room.players = {}

    async def test_maximum_melee_critical_does_not_one_shot_a_two_level_junior(self):
        for loc_id in (17,21,20,38):
            mob = next(iter(self.room(loc_id).mobs.values()))
            character = afro_character(mob.level-2,'smg')
            player = NS(is_player=True,character=lambda: character,armor=lambda: 0)
            damage, _stamina = balance.split(mob,player,mob.stats.dmg_max,1,True,
                                             character.sp_max,melee=True,ordinary=True)
            self.assertGreater(damage,0)
            self.assertLess(damage,character.hp_max,(loc_id,damage,character.hp_max))

    async def test_plain_same_level_weapons_can_damage_each_regional_profile(self):
        for loc_id in (17,21,20,38):
            mob = next(iter(self.room(loc_id).mobs.values()))
            for kind in ('pistol','shotgun','smg','assault_rifle','rifle','machine_gun'):
                character = afro_character(mob.level,kind)
                shooter = NS(is_player=True,character=lambda: character)
                for gun,ammo,mode,weapon,_rounds in afro_modes(character,kind):
                    full = combat.RoomCombat.bullet_damage(None,shooter,mob,weapon,
                        weapon.dmax,weapon.sdmax,False,mob.sp)
                    empty = combat.RoomCombat.bullet_damage(None,shooter,mob,weapon,
                        weapon.dmax,weapon.sdmax,False,0)
                    self.assertGreater(sum(full),0,(loc_id,gun,ammo,mode))
                    self.assertGreater(empty[0],0,(loc_id,gun,ammo,mode))


if __name__ == '__main__':
    run_cases(CoastalCombat)
