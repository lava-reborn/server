"""Capture-finisher eligibility and bounded AI rights queries on real memberships."""
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


class CaptureReviewFixes(unittest.TestCase):
    setUp = ClanBases.setUp

    def members(self):
        ids = [self.cid]
        for index in range(3):
            account, _ = self.store.register('capture-review-%d' % index, 'test-only')
            char, _ = self.store.create_character(account, 'ReviewMember%d' % index, 0, '1')
            self.store.clan_member_add(char, self.clan, 0, '')
            ids.append(char)
        return ids

    def seats(self, ids, level):
        seats = []
        for char in ids:
            sess = NS(char_id=char, send=Mock(), answer=Mock())
            sess.combat = NS(is_player=True, store=self.store, sess=sess,
                             dead=False, level=level, cell=100, regen_at=float('inf'),
                             present=lambda _rc: True, preparing=lambda: False)
            seats.append(sess)
        return seats

    def scene(self, site, seats, harm):
        room = NS(loc=world.location(site.loc), players=seats, npcs={})
        rc = NS(store=self.store, room=room, boss_spot=lambda _mob: 'review-' + site.key)
        mob = NS(type_id=site.boss, slot=SLOT, hp_max=100, sp_max=0, capture_harm=harm)
        return rc, mob

    def test_ineligible_finisher_cannot_use_another_complete_squad_at_any_site(self):
        ids = self.members()
        for site in holdings.sites().values():
            squad = holdings.BASE_SQUAD if site.kind == 'base' else holdings.table().squad
            for case in ('low', 'dead', 'away', 'no_damage', 'untracked'):
                with self.subTest(site=site.key, case=case):
                    seats = self.seats(ids[:squad + 1], site.min_level)
                    rc, mob = self.scene(site, seats, dict.fromkeys(ids[:squad + 1], 1))
                    killer = seats[0].combat
                    if case == 'low':
                        killer.level -= 1
                    elif case == 'dead':
                        killer.dead = True
                    elif case == 'away':
                        rc.room.players = seats[1:]
                    elif case == 'no_damage':
                        mob.capture_harm[self.cid] = 0
                    else:
                        mob.capture_harm.pop(self.cid)
                    snap = holdings.snapshot(rc, mob, killer)
                    # The helpers alone meet the numeric threshold: only the finisher fails.
                    self.assertEqual(sum(f['char'] != self.cid and f['here'] and f['alive']
                                         and f['level'] >= site.min_level and f['harm'] > 0
                                         for f in snap['fighters']), squad)
                    self.assertIsNone(holdings.winner(snap, squad, site.min_level))
                    mob.capture = snap
                    self.assertEqual(holdings.settle(rc, mob), 'none')
                    self.assertIsNone(self.store.holding(site.key))
                    self.assertFalse(any(row['how'] == 'capture'
                                         for row in self.store.holding_log(site.key)))
                    if site.kind == 'base':
                        message = seats[-1].answer.call_args.args[0]
                        self.assertIn('добивший хозяина должен', message)
                        self.assertNotIn('из 3', message)

    def test_actual_ally_finisher_is_checked_while_ownership_credits_its_owner(self):
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                owner = self.seats([self.cid], site.min_level)[0]
                owner.inv = NS(store=self.store)
                allies = []
                for char in (-101, -102, -103):
                    ally = NS(ground=NS(ally=True, owner=owner, capture_char=char))
                    ally.combat = NS(is_player=True, dead=False, level=site.min_level, sess=ally)
                    allies.append(ally)
                rc, mob = self.scene(site, [owner] + allies,
                                     dict.fromkeys([self.cid, -101, -102, -103], 1))
                owner.room = rc.room
                squad = holdings.BASE_SQUAD if site.kind == 'base' else holdings.table().squad
                killer = allies[-1].combat
                killer.level -= 1
                snap = holdings.snapshot(rc, mob, killer)
                self.assertEqual((snap['killer'], snap['killer_actor']), (self.cid, -103))
                self.assertIsNone(holdings.winner(snap, squad, site.min_level))
                # A qualified bot may finish even if its credited owner is underlevel.
                killer.level += 1
                owner.combat.level -= 1
                snap = holdings.snapshot(rc, mob, killer)
                won = holdings.winner(snap, squad, site.min_level)
                self.assertEqual((won[0], won[3]), (self.clan, self.cid))

    def ai_room(self, site, seats):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        rc.store = self.store
        rc.room = NS(loc=world.location(site.loc), ws=False)
        rc.fighters = lambda: [seat.combat for seat in seats]
        rc.keep_hours = Mock()
        rc.regen_mob = Mock()
        rc.calm = Mock()
        rc.set_ws = Mock()
        rc.ap_last = 100
        rc.mobs = {eid: mobs.Mob(eid, kind, 100)
                   for eid, kind in enumerate((site.boss, *site.guards, *site.troops), 1)}
        return rc

    def test_distant_candidates_do_not_read_owner_or_membership(self):
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                seats = self.seats([self.cid], site.min_level)
                rc = self.ai_room(site, seats)
                seats[0].combat.cell += rc.room.loc.width * 20
                mob = next(iter(rc.mobs.values()))
                with patch.object(self.store, 'holding', wraps=self.store.holding) as held, \
                        patch.object(self.store, 'clan_member', wraps=self.store.clan_member) as member:
                    self.assertIsNone(rc.nearest_fighter(mob.cell, 1, mob))
                self.assertEqual((held.call_count, member.call_count), (0, 0))

    def test_ai_pass_reuses_rights_and_next_pass_observes_membership_and_owner_changes(self):
        char = self.members()[1]
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                self.store.holding_set(site.key, self.clan, 'admin', slot=SLOT)
                seats = self.seats([char], site.min_level)
                rc = self.ai_room(site, seats)
                with patch.object(combat, 'now', return_value=100), \
                        patch.object(self.store, 'holding', wraps=self.store.holding) as held, \
                        patch.object(self.store, 'clan_member', wraps=self.store.clan_member) as member:
                    rc._step()
                    self.assertTrue(all(mob.target is None for mob in rc.mobs.values()))
                    self.assertEqual((held.call_count, member.call_count), (1, 1))
                    self.assertIsNone(rc._defender_cache)
                    self.assertTrue(self.store.clan_member_remove(char, self.clan))
                    rc._step()
                    self.assertTrue(all(mob.target is seats[0].combat for mob in rc.mobs.values()))
                    self.assertEqual((held.call_count, member.call_count), (2, 2))
                    self.store.clan_member_add(char, self.clan, 0, '')
                    for mob in rc.mobs.values():
                        mob.target = None
                    rc._step()
                    self.assertTrue(all(mob.target is None for mob in rc.mobs.values()))
                    self.assertEqual((held.call_count, member.call_count), (3, 3))
                    self.store.holding_clear(site.key, 'admin')
                    rc._step()
                    self.assertTrue(all(mob.target is seats[0].combat for mob in rc.mobs.values()))
                    self.assertEqual((held.call_count, member.call_count), (4, 3))

    def test_ai_pass_reads_one_holder_for_multiple_nearby_clanmates(self):
        ids = self.members()[:2]
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                self.store.holding_set(site.key, self.clan, 'admin', slot=SLOT)
                rc = self.ai_room(site, self.seats(ids, site.min_level))
                with patch.object(combat, 'now', return_value=100), \
                        patch.object(self.store, 'holding', wraps=self.store.holding) as held, \
                        patch.object(self.store, 'clan_member', wraps=self.store.clan_member) as member:
                    rc._step()
                    self.assertTrue(all(mob.target is None for mob in rc.mobs.values()))
                    self.assertEqual((held.call_count, member.call_count), (1, 2))
                self.store.holding_clear(site.key, 'admin')

    def test_ai_pass_discards_rights_even_when_a_mob_brain_raises(self):
        site = holdings.site('wh_sever')
        self.store.holding_set(site.key, self.clan, 'admin')
        rc = self.ai_room(site, self.seats([self.cid], site.min_level))
        mob = next(iter(rc.mobs.values()))
        def fail(room, _now):
            self.assertIsNone(room.nearest_fighter(mob.cell, 20, mob))
            raise RuntimeError('brain interrupted')
        with patch.object(combat, 'now', return_value=100), \
                patch.object(mob, 'think', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'brain interrupted'):
                rc._step()
        self.assertIsNone(rc._defender_cache)
        self.store.holding_clear(site.key, 'admin')
        self.assertIs(rc.nearest_fighter(mob.cell, 20, mob), rc.fighters()[0])


if __name__ == '__main__':
    run_cases(CaptureReviewFixes)
