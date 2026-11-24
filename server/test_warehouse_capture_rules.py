"""Warehouse last-hit capture and passive ownership use live memberships."""
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

import combat
import holdings
import mobs
import world
from test_clan_bases import ClanBases, SLOT
from testkit import run_cases


class WarehouseCaptureRules(unittest.TestCase):
    setUp = ClanBases.setUp
    supporters = ClanBases.supporters

    def sites(self):
        return [s for s in holdings.sites().values() if s.kind == 'warehouse']

    def fighters(self, ids, level):
        seats = []
        for char_id in ids:
            sess = NS(char_id=char_id, send=Mock())
            sess.combat = NS(is_player=True, store=self.store, sess=sess,
                             dead=False, level=level, cell=100,
                             present=lambda _rc: True, preparing=lambda: False)
            seats.append(sess)
        return seats

    def capture_scene(self, site, seats, harm):
        room = NS(loc=world.location(site.loc), players=seats, npcs={})
        rc = NS(store=self.store, room=room)
        mob = NS(type_id=site.boss, slot=SLOT, hp_max=1000, sp_max=1000,
                 capture_harm=harm)
        return rc, mob

    def test_all_seven_warehouses_use_three_contributors_and_the_finishing_clan(self):
        self.assertEqual(len(self.sites()), 7)
        self.assertEqual(holdings.table().squad, 3)
        own = [self.cid] + [p['char'] for p in self.supporters()]
        account, _ = self.store.register('warehouse-rival', 'test-only')
        rival, _ = self.store.create_character(account, 'WarehouseRival', 0, '1')
        rival_clan = self.store.clan_create(rival, 'Rival clan', 'warehouse-rival', '', None)
        rivals = [rival] + [p['char'] for p in self.supporters(rival_clan)]
        for site in self.sites():
            with self.subTest(site=site.key):
                seats = self.fighters(own + rivals, site.min_level)
                rc, mob = self.capture_scene(site, seats,
                    {**dict.fromkeys(own, 1), **dict.fromkeys(rivals, 500)})
                mob.capture = holdings.snapshot(rc, mob, seats[0].combat)
                with patch.object(holdings, 'refresh'):
                    self.assertEqual(holdings.settle(rc, mob), 'capture')
                self.assertEqual(self.store.holding(site.key)['clan_id'], self.clan)
                self.assertEqual(self.store.holding(site.key)['by_char'], self.cid)
                self.assertIsNone(holdings.settle(rc, mob))
                # The same participants defend by finishing, without resetting ownership age.
                since = self.store.holding(site.key)['since']
                mob.capture = holdings.snapshot(rc, mob, seats[0].combat)
                self.assertEqual(holdings.settle(rc, mob), 'defend')
                self.assertEqual(self.store.holding(site.key)['since'], since)

    def test_no_fallback_when_finishing_clan_lacks_a_qualified_squad(self):
        own = [self.cid] + [p['char'] for p in self.supporters()]
        for site in self.sites():
            for case in ('two', 'dead', 'away', 'low', 'no_damage', 'clanless', 'no_killer', 'duplicate', 'left_clan'):
                with self.subTest(site=site.key, case=case):
                    seats = self.fighters(own, site.min_level)
                    rc, mob = self.capture_scene(site, seats, dict.fromkeys(own, 1))
                    if case == 'two':
                        mob.capture_harm.pop(own[-1])
                    elif case == 'dead':
                        seats[-1].combat.dead = True
                    elif case == 'away':
                        rc.room.players = seats[:-1]
                    elif case == 'low':
                        seats[-1].combat.level -= 1
                    elif case == 'no_damage':
                        mob.capture_harm[own[-1]] = 0
                    if case == 'left_clan':
                        self.assertTrue(self.store.clan_member_remove(own[-1], self.clan))
                    killer = None if case == 'no_killer' else seats[0].combat
                    snap = holdings.snapshot(rc, mob, killer)
                    if case == 'clanless':
                        snap['killer_clan'] = None
                    elif case == 'duplicate':
                        snap['fighters'] = snap['fighters'][:2] + [snap['fighters'][1]]
                    # A different clan's complete high-damage squad cannot inherit the kill.
                    snap['fighters'] += [dict(char=10000 + i, clan=999, clan_name='Damage leaders',
                                              here=True, alive=True, level=20, harm=500)
                                         for i in range(3)]
                    self.assertIsNone(holdings.winner(snap, holdings.table().squad, site.min_level))
                    mob.capture = snap
                    self.assertEqual(holdings.settle(rc, mob), 'none')
                    self.assertIsNone(self.store.holding(site.key))
                    if case == 'left_clan':
                        self.store.clan_member_add(own[-1], self.clan, 0, '')

    def test_warehouse_defenders_are_passive_but_retaliate_against_the_owner(self):
        member = self.supporters()[0]['char']
        owner, outsider = [s.combat for s in self.fighters((member, 999999), 20)]
        for site in self.sites():
            self.store.holding_set(site.key, self.clan, 'admin')
            for kind in (site.boss, *site.guards):
                with self.subTest(site=site.key, type_id=kind):
                    rc = combat.RoomCombat.__new__(combat.RoomCombat)
                    rc.store = self.store
                    rc.room = NS(loc=world.location(site.loc))
                    rc.set_ws = Mock()
                    mob = mobs.Mob(123, kind, owner.cell)
                    rc.fighters = lambda: [owner]
                    self.assertTrue(holdings.warehouse_defender_passive(rc, mob, owner))
                    self.assertFalse(holdings.defender_friendly(rc, mob, owner))
                    self.assertIsNone(rc.nearest_fighter(mob.cell, 20, mob))
                    rc.aggro(mob, owner, t=100)
                    self.assertIsNone(mob.target)
                    rc.set_ws.assert_not_called()
                    rc.fighters = lambda: [owner, outsider]
                    self.assertIs(rc.nearest_fighter(mob.cell, 20, mob), outsider)
                    rc.aggro(mob, outsider, t=100)
                    self.assertIs(mob.target, outsider)
                    mob.target = None
                    with patch.object(combat, 'now', return_value=100):
                        rc.after_hostile(owner, mob)
                    self.assertIs(mob.target, owner)
                    self.store.holding_clear(site.key, 'admin')
                    self.assertFalse(holdings.warehouse_defender_passive(rc, mob, owner))
                    self.store.holding_set(site.key, self.clan, 'admin')
        self.assertTrue(self.store.clan_member_remove(member, self.clan))
        self.assertFalse(holdings.warehouse_defender_passive(rc, mob, owner))

    def test_warehouse_passivity_does_not_cover_unrelated_mobs_or_private_clones(self):
        site = self.sites()[0]
        self.store.holding_set(site.key, self.clan, 'admin')
        owner = self.fighters((self.cid,), 20)[0].combat
        rc = NS(store=self.store, room=NS(loc=world.location(site.loc)))
        self.assertFalse(holdings.warehouse_defender_passive(rc, mobs.Mob(1, 82, 100), owner))
        owner.store = object()
        self.assertFalse(holdings.warehouse_defender_passive(rc, mobs.Mob(2, site.boss, 100), owner))


if __name__ == '__main__':
    run_cases(WarehouseCaptureRules)
