"""Real death/item transactions: a mob's level never protects possessions.

No battle simulation or server process: fixed successful loss rolls exercise
RoomCombat.kill -> Fighter.die -> drop_on_death against an isolated SQLite DB.
The separate PvP four-level exclusion must not leak into ordinary PvE deaths.
"""
from contextlib import contextmanager
import logging
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ.setdefault('LAVA_DB', ':memory:')
logging.disable(logging.CRITICAL)

import accounts
import combat
import inventory
import items
import progression
import sets
from testkit import run_cases


class AllLosses:
    def randint(self, low, high):
        return low


class DeathLootLevelGate(unittest.TestCase):
    @contextmanager
    def victim(self, level=16):
        store = accounts.Store(':memory:')
        try:
            account_id, _ = store.register('death-level-gate', 'local-test')
            char_id, _ = store.create_character(account_id, 'DeathGate', 0, '1')
            character = progression.Character.load(store, char_id)
            character.set_skill(progression.SHOOTING, level)
            character.save(store)
            rows = {}

            def make(name, type_id, slot, count=1):
                fields = inventory.new_fields(type_id, count)
                fields['slot'] = slot
                rows[name] = store.create_item(char_id, type_id, fields.pop('root'), **fields)

            afro = sets.SETS[11167]['members']
            gold = sets.SETS[11169]['members']
            make('helm', afro['helm'], inventory.HEAD)
            make('boots', afro['boots'], inventory.BOOTS)
            make('pouch', 3577, inventory.BELT)
            make('ammo', inventory.STARTER_AMMO, inventory.BAG, 20)
            make('ingot', next(iter(items.GOLD_INGOTS)), inventory.BAG)
            make('gold', gold['armor'], inventory.ARMOR)
            make('quest', 260, inventory.BAG)
            make('hand', inventory.STARTER_PISTOL, inventory.PRIMARY)
            make('bank', inventory.STARTER_AMMO, inventory.BANK, 20)
            inv = NS(rows=lambda: store.items_of(char_id), locked=set(),
                     forget_reload=Mock(), push_status=Mock(), push_di=Mock(), refresh_gear=Mock())
            room = NS(broadcast=Mock())
            rc = NS(mobs={}, add_to_bag=Mock(), calm=Mock())
            seat = NS(char_id=char_id, nick='DeathGate', walk=None, room=room,
                      inv=inv, pos=123, say=Mock())
            fighter = NS(is_player=True, level=level, sess=seat, rc=rc, store=store,
                         eid='p1', cell=123, character=lambda: character,
                         end_duels=Mock(), cancel_timers=Mock())
            fighter.drop_on_death = lambda: combat.Fighter.drop_on_death(fighter)
            fighter.die = lambda killer: combat.Fighter.die(fighter, killer)
            yield fighter, rows
        finally:
            store.close()

    def kill(self, victim, killer):
        with patch.object(combat, 'RNG', AllLosses()), \
                patch.object(combat.eden_harvest, 'native_kill', return_value=False):
            combat.RoomCombat.kill(victim.rc, victim, killer)

    def assert_ordinary_losses(self, victim, rows):
        ground = list(victim.store.items_of(combat.LOOT_OWNER))
        self.assertEqual({r['type_id']: r['count'] for r in ground}, {
            rows['helm']['type_id']: 1, rows['pouch']['type_id']: 1,
            rows['ammo']['type_id']: 7, rows['ingot']['type_id']: 1})
        self.assertEqual(victim.store.item(rows['ammo']['uniq'])['count'], 13)
        for kept in ('boots', 'gold', 'quest', 'hand', 'bank'):
            self.assertEqual(victim.store.item(rows[kept]['uniq'])['char_id'], victim.sess.char_id)
        victim.rc.add_to_bag.assert_called_once()
        self.assertEqual(victim.rc.add_to_bag.call_args.args[0], victim.sess.pos)
        self.assertEqual({r['uniq'] for r in victim.rc.add_to_bag.call_args.args[1]},
                         {r['uniq'] for r in ground})
        victim.sess.inv.refresh_gear.assert_called_once()
        self.assertEqual(victim.store.character(victim.sess.char_id)['death'], 1)

    def test_mob_deaths_keep_normal_losses_at_every_level_gap(self):
        for mob_level in (1, 12, 15, 16, 17, 19, 20, 21, 40):
            with self.subTest(mob_level=mob_level), self.victim() as (victim, rows):
                self.kill(victim, NS(is_player=False, level=mob_level, eid='m1'))
                self.assert_ordinary_losses(victim, rows)

    def test_mob_death_does_not_even_need_a_killer_level(self):
        with self.victim() as (victim, rows):
            self.kill(victim, NS(is_player=False, eid='m1'))
            self.assert_ordinary_losses(victim, rows)

    def test_environmental_deaths_keep_the_same_losses(self):
        with self.victim() as (victim, rows):
            self.kill(victim, None)
            self.assert_ordinary_losses(victim, rows)

    def test_pvp_excludes_only_victims_four_or_more_levels_below_the_killer(self):
        for killer_level in (1, 12, 13, 16, 19, 20, 21):
            with self.subTest(killer_level=killer_level), self.victim() as (victim, rows):
                before = {r['uniq']: dict(r) for r in victim.store.items_of(victim.sess.char_id)}
                killer = NS(is_player=True, level=killer_level, eid='p2', pvp_kill=Mock())
                self.kill(victim, killer)
                if killer_level < victim.level + 4:
                    self.assert_ordinary_losses(victim, rows)
                else:
                    self.assertEqual(list(victim.store.items_of(combat.LOOT_OWNER)), [])
                    self.assertEqual({r['uniq']: dict(r) for r in victim.store.items_of(victim.sess.char_id)},
                                     before)
                    victim.rc.add_to_bag.assert_not_called()
                killer.pvp_kill.assert_called_once_with(victim)


if __name__ == '__main__':
    run_cases(DeathLootLevelGate)
