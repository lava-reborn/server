"""Camp ammunition boxes: calibre, player-tier medicine and atomic corpse loot."""
import asyncio
import logging
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import accounts
import camp_box_loot
import combat
import inventory
import items
import mobs
import progression
import shop_bands
import world
from testkit import run_cases


class Dice:
    def __init__(self, index=0, amounts=(1, 2)):
        self.index = index
        self.amounts = iter(amounts)
        self.choices = []

    def random(self):
        return .999999

    def choice(self, values):
        self.choices.append(tuple(values))
        return values[self.index % len(values)]

    def randint(self, low, high):
        value = next(self.amounts)
        assert low <= value <= high
        return value


def supplies(loc=80, *, weapon=None, level=1, rng=None, ordinary=()):
    return camp_box_loot.replace(list(ordinary), mobs.stats(camp_box_loot.BOXES[loc]),
                                 rng or Dice(), loc_id=loc, player_kill=True,
                                 weapon_type_id=weapon, killer_level=level)


class CampBoxSupplies(unittest.TestCase):
    def test_explicit_box_pairs_are_only_native_camp_centre_objects(self):
        expected = {(loc, t) for loc, types in world.STANDING_OBJECTS.items() for t in types
                    if mobs.TYPES[str(t)]['name'].endswith('_box_ammo')}
        self.assertEqual(set(camp_box_loot.BOXES.items()), expected)
        self.assertEqual(len(expected), 11)
        for loc, kind in expected:
            self.assertEqual(mobs.stats(kind).role, 'object')
            self.assertIn(kind, {t for _cell, t in world.location(loc).spawns})

    def test_all_released_gun_calibres_receive_exactly_fifty_compatible_afro_ot(self):
        checked = set()
        for gun in shop_bands.wares():
            if items.root_of(gun) != items.FIRE_ARM:
                continue
            compatible = set(items.params_of(gun).get('comp_array', ())) & set(camp_box_loot.ammunition())
            if not compatible:
                continue
            with self.subTest(gun=gun):
                drops = supplies(weapon=gun)
                rounds = [(t, n) for t, n in drops if items.root_of(t) == items.AMMO]
                self.assertEqual(len(rounds), 1)
                self.assertIn(rounds[0][0], compatible)
                self.assertEqual(rounds[0][1], 50)
                si = items.params_of(rounds[0][0])
                self.assertEqual(si['g_cost'], 0)
                self.assertTrue(items.catalogue()[rounds[0][0]][1].endswith('_OT'))
                checked.add(rounds[0][0])
        self.assertEqual(checked, set(camp_box_loot.ammunition()))
        self.assertEqual(len(checked), 12)

    def test_melee_missing_gun_and_missing_compatible_ammo_pick_one_random_calibre(self):
        pool = camp_box_loot.ammunition()
        for weapon in (None, 6229, 999999999, 25562):
            got = []
            for index, ammo in enumerate(pool):
                rng = Dice(index)
                drops = supplies(weapon=weapon, rng=rng)
                self.assertEqual(rng.choices, [pool])
                self.assertEqual(drops[0], (ammo, 50))
                got.append(drops[0][0])
            self.assertCountEqual(got, pool)

    def test_medicine_uses_killer_level_not_box_level_at_every_tier_boundary(self):
        for loc in camp_box_loot.BOXES:
            for level in (None, 0, 1, 3, 4, 7, 8, 11, 12, 15, 16, 17, 19, 20, 30):
                with self.subTest(location=loc, level=level):
                    tier = min(5, max(0, (level or 0) // 4))
                    drops = supplies(loc, level=level)
                    self.assertEqual(drops[1:], [(6055 + tier, 1), (6061 + tier, 2)])
                    self.assertTrue(all(items.params_of(t)['use_count'] == 1 for t, _n in drops[1:]))
                    self.assertTrue(all(items.params_of(t)['g_cost'] == 0 for t, _n in drops[1:]))

    def test_both_medicine_counts_have_independent_one_and_two_boundaries(self):
        for amounts in ((1, 1), (1, 2), (2, 1), (2, 2)):
            self.assertEqual([n for _t, n in supplies(rng=Dice(amounts=amounts))[1:]], list(amounts))

    def test_native_ammo_and_afro_battle_medicine_are_replaced_without_extra_calibres(self):
        native = [(6104, 20), (6122, 9), (6055, 1), (6061, 1), (6059, 2), (6065, 2), (4796, 1)]
        drops = supplies(ordinary=native)
        self.assertEqual(drops, [(4796, 1), (6116, 50), (6055, 1), (6061, 2)])

    def test_wrong_type_location_encounter_or_nonplayer_cannot_create_new_supplies(self):
        native = [(6104, 20), (4796, 1)]
        for role, kind, loc, ambush, player in (
                ('object', 409, 82, None, True), ('object', 41, 80, None, True),
                ('object', 409, 80, 80, True), ('mob', 409, 80, None, True),
                ('object', 409, 80, None, False), ('object', 409, 1442, None, True),
                ('object', 409, 43, None, True)):
            rng = Mock()
            got = camp_box_loot.replace(native, NS(role=role, type_id=kind), rng,
                                         loc_id=loc, ambush_camp=ambush, player_kill=player)
            self.assertIs(got, native)
            self.assertEqual(rng.mock_calls, [])

    def test_empty_catalogue_fails_closed_without_losing_native_loot(self):
        native = [(6104, 20)]
        with patch.object(camp_box_loot, 'ammunition', return_value=()):
            self.assertEqual(supplies(ordinary=native), native)

    def test_level_cutoff_and_scanner_do_not_scale_supplies_or_personal_quests(self):
        for level, multiplier in ((1, .25), (5, 0), (17, 3.75)):
            with patch.object(mobs, 'quest_roll', return_value=[(2258, 1)]):
                drops = mobs.loot_for(mobs.stats(409), Dice(), {2258}, loc_id=80,
                                      killer_level=level, multiplier=multiplier,
                                      box_player_kill=True)
            tier = level // 4
            self.assertEqual(drops, [(6116, 50), (6055 + tier, 1), (6061 + tier, 2), (2258, 1)])


class CampBoxCorpse(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        self.mob = mobs.Mob(1, 409, 0)
        self.mob.alive = False
        self.mob.blueprint_killer_level = 16
        self.mob.box_player_kill = True
        self.mob.box_weapon_type = 25566
        self.rc = NS(room=NS(loc=NS(id=80)), store=self.store, place=(80, None, None),
                     add_to_bag=Mock())
        self.rc.drop_loot = lambda mob: combat.RoomCombat.drop_loot(self.rc, mob)

    def ground(self):
        return [self.store.item(row['uniq']) for row in self.store.on_ground(combat.LOOT_OWNER)]

    def test_actual_item_counts_weights_and_one_materialization_per_life(self):
        with patch.object(combat, 'RNG', Dice()):
            combat.RoomCombat.materialize_loot(self.rc, self.mob)
        rows = self.ground()
        self.assertEqual(len(rows), 3)
        self.assertEqual([(r['type_id'], r['count']) for r in rows], [(6118, 50), (6059, 1), (6065, 2)])
        for row in rows:
            self.assertEqual(inventory.weight_of(row), items.params_of(row['type_id'])['weight'] * row['count'])
            self.assertEqual(inventory.di_params(row)['size'], row['count'])
            if row['root'] == items.HEAL:
                self.assertEqual(inventory.di_params(row)['use_count'], 1)
        with patch.object(self.rc, 'drop_loot', side_effect=AssertionError('replayed creation')):
            combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertEqual(self.ground(), rows)
        self.rc.add_to_bag.assert_called_once()
        # Pickup moves existing serials. Replayed corpse processing cannot
        # reconstruct the bundle after it has left the ground.
        self.store.pick_up([r['uniq'] for r in rows], 7, inventory.BAG)
        combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertEqual(self.ground(), [])
        self.assertEqual([self.store.item(r['uniq'])['char_id'] for r in rows], [7, 7, 7])

    def test_failed_creation_rolls_back_all_items_and_can_retry_once(self):
        original = self.store.create_item
        writes = []

        def fail(*args, **kwargs):
            row = original(*args, **kwargs)
            writes.append(row)
            if len(writes) == 2:
                raise RuntimeError('failed second item')
            return row

        with patch.object(self.store, 'create_item', side_effect=fail), patch.object(combat, 'RNG', Dice()):
            with self.assertRaisesRegex(RuntimeError, 'second item'):
                combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertFalse(getattr(self.mob, '_loot_materialized', False))
        self.assertEqual(self.ground(), [])
        self.assertTrue(all(self.store.item(row['uniq']) is None for row in writes))
        self.rc.add_to_bag.assert_not_called()
        with patch.object(combat, 'RNG', Dice()):
            combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertEqual(len(self.ground()), 3)

    def test_failed_ground_commit_cannot_leave_items_without_a_bag(self):
        original = self.store.lay_down

        def fail(*args):
            original(*args)
            raise RuntimeError('failed ground write')

        with patch.object(self.store, 'lay_down', side_effect=fail), patch.object(combat, 'RNG', Dice()):
            with self.assertRaisesRegex(RuntimeError, 'ground write'):
                combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertFalse(getattr(self.mob, '_loot_materialized', False))
        self.assertEqual(self.ground(), [])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM items WHERE char_id = 0').fetchone()[0], 0)
        self.rc.add_to_bag.assert_not_called()

    def test_nonplayer_death_keeps_native_box_loot_without_the_new_bundle(self):
        self.mob.box_player_kill = False
        with patch.object(combat, 'RNG', Dice()):
            combat.RoomCombat.materialize_loot(self.rc, self.mob)
        self.assertEqual([(r['type_id'], r['count']) for r in self.ground()], [(6104, 20)])

    def test_respawn_clears_the_previous_killer_snapshot(self):
        self.mob.reset()
        self.assertFalse(self.mob.box_player_kill)
        self.assertIsNone(self.mob.box_weapon_type)

    def test_actual_kill_saves_type_and_pre_xp_level_and_nonplayer_clears_them(self):
        async def exercise():
            for killer in (NS(is_player=True, level=16, eid=7, sess=NS(), count_kill=Mock(), release_stats=Mock()),
                           NS(is_player=False, eid=8), None):
                self.mob.reset()
                room = NS(loc=NS(id=80, title='camp'), players=[], npcs={1: self.mob}, broadcast=Mock())
                rc = NS(room=room, quest_wants=lambda *_: frozenset(), settle_xp=Mock(),
                        corpse_gone=Mock(), calm=Mock())
                with patch.object(combat.RoomCombat, 'materialize_loot') as materialize, \
                        patch.object(combat.production, 'mined_by'), \
                        patch.object(combat.holdings, 'snapshot', return_value=None):
                    combat.RoomCombat.kill(rc, self.mob, killer,
                                           blueprint_killer_level=15, killing_weapon_type=25566)
                player = killer is not None and killer.is_player
                self.assertEqual(self.mob.box_player_kill, player)
                self.assertEqual(self.mob.box_weapon_type, 25566 if player else None)
                self.assertEqual(self.mob.blueprint_killer_level, 15 if player else None)
                materialize.assert_called_once_with(rc, self.mob)
        asyncio.run(exercise())


class CampBoxFinishingShot(unittest.TestCase):
    def test_real_fire_path_passes_lethal_gun_for_direct_and_collateral_box(self):
        for loaded in (6094, 6106, 6118, 6142):
            # The loaded round's quality does not change the awarded A-OT.
            row = dict(char_id=7, type_id=25566, root=items.FIRE_ARM,
                       slot=inventory.PRIMARY, ammo_type=loaded, ammo_count=1, brk=100)
            character = progression.Character()
            character.set_skill(progression.SHOOTING, 16)
            target = NS(is_player=False, cell=1, hp=10)
            other = NS(is_player=False, cell=2, hp=10)
            room = NS(ws=False)
            rc = NS(room=room, within_fire=lambda *_: True, after_hostile=Mock(), kill=Mock())
            fighter = NS(dead=False, is_player=True, level=16, rc=rc, cell=0,
                         character=lambda: character, present=lambda _rc: True,
                         store=NS(item=lambda _uniq: dict(row), update_item=Mock()),
                         c_ap=Mock(), award_xp=Mock(), hold_stats=Mock(), release_stats=Mock(),
                         sess=NS(char_id=7, room=room, inv=NS(push_di=Mock())))

            def burst(_shooter, _target, _hex, _weapon, _live, others, **_kw):
                others.append((other, 10, 0, True, 10))
                return 10, 0, 1, True

            rc.burst = burst
            weapon = NS(num_shots=1, max_range=10, skill=progression.SHOOTING, spec=None)
            with patch.object(combat.Fighter, 'commit_animation', return_value=0):
                combat.Fighter.fire_now(fighter, 1, target, None, weapon, 5)
            self.assertEqual(rc.kill.call_count, 2)
            self.assertEqual([call.args[0] for call in rc.kill.call_args_list], [target, other])
            for call in rc.kill.call_args_list:
                self.assertEqual(call.kwargs, dict(blueprint_killer_level=16, killing_weapon_type=25566))


if __name__ == '__main__':
    run_cases(CampBoxSupplies, CampBoxCorpse, CampBoxFinishingShot)
