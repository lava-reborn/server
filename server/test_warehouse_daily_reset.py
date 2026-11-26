"""Daily warehouse expiry and gold claims on SQLite and PostgreSQL.

Real persisted ownership/claim rows, without changing the boss/reward hours.
This suite honours LAVA_DB_URL and is included in the PostgreSQL CI job.
"""
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import accounts
import bosses
import holdings
import items
import storage
from testkit import run_cases


START = datetime(2026, 11, 26, 20, tzinfo=bosses.ZONE).timestamp()


class WarehouseDailyReset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='warehouse-reset-')
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'state.sqlite')
        self.store = accounts.Store(self.path)
        self.addCleanup(lambda: self.store.close())
        self.now = START - 1
        self.enterContext(patch.object(bosses, 'clock', lambda: self.now))
        self.sites = [s for s in holdings.sites().values() if s.kind == 'warehouse']
        # Each PostgreSQL method shares the suite database, unlike SQLite.
        with self.store.db:
            for site in self.sites:
                self.store.db.execute('DELETE FROM clan_holdings WHERE site=?', (site.key,))
                self.store.db.execute('DELETE FROM clan_holding_claims WHERE site=?', (site.key,))
        tag = uuid.uuid4().hex[:12]
        aid, _ = self.store.register('wh-' + tag, 'test-only')
        self.cid, _ = self.store.create_character(aid, 'Wh' + tag, 0, '1')
        self.clan = self.store.clan_create(self.cid, 'Warehouse ' + tag, 'wh-' + tag, '', None)
        with self.store.db:
            self.store.db.execute('UPDATE clan_members SET joined_at=? WHERE char_id=?',
                                  (START - 3 * 86400, self.cid))
        self.site = self.sites[0]

    def own(self, site=None, at=None):
        site = site or self.site
        at = START - 86400 + 5 if at is None else at
        return self.store.holding_set(site.key, self.clan, 'admin', when=at, slot=at - 5)

    def day(self, when):
        return int(when // 86400 * 86400)

    def claim(self, when):
        return self.store.holding_gold_claim(self.site.key, self.day(when), self.cid,
            holdings.table().tenure, when=when, owner_since=holdings.warehouse_reset_at)

    def scene(self, at, slot=None):
        fighters = [dict(char=self.cid, clan=self.clan, clan_name='Holder', harm=1,
                         here=True, alive=True, level=self.site.min_level),
                    dict(char=-42, clan=self.clan, clan_name='Holder', harm=1,
                         here=True, alive=True, level=self.site.min_level)]
        snap = dict(site=self.site.key, at=at, slot=at if slot is None else slot,
                    pool=100, fighters=fighters, killer=self.cid,
                    killer_clan=self.clan, killer_actor=self.cid)
        return NS(store=self.store, room=NS(players=[], npcs={})), NS(capture=snap)

    def test_all_seven_reset_at_twenty_after_their_reward_windows_not_midnight(self):
        self.assertEqual(len(self.sites), 7)
        for site in self.sites:
            self.own(site)
        base = holdings.site('base_ah')
        self.own(base)
        self.assertEqual(holdings.reset_warehouses(self.store), ())
        self.assertTrue(all(holdings.holder(self.store, s) for s in self.sites))
        self.now = START
        self.assertTrue(all(holdings.holder(self.store, s) is None for s in self.sites))
        self.assertEqual(set(holdings.reset_warehouses(self.store)), {s.key for s in self.sites})
        self.assertTrue(all(self.store.holding(s.key) is None for s in self.sites))
        self.assertIsNotNone(self.store.holding(base.key))
        logs = {s.key: len(self.store.holding_log(s.key)) for s in self.sites}
        self.assertEqual(holdings.reset_warehouses(self.store), ())
        self.assertEqual(logs, {s.key: len(self.store.holding_log(s.key)) for s in self.sites})
        self.own(at=START)
        for hours in (1, 4, 12, 23):
            self.now = START + hours * 3600
            self.assertEqual(holdings.reset_warehouses(self.store), ())
            self.assertIsNotNone(holdings.holder(self.store, self.site))
        self.now = START + 86400
        self.assertEqual(holdings.reset_warehouses(self.store), (self.site.key,))

    def test_restart_and_empty_rooms_cannot_extend_ownership_or_allow_a_stale_claim(self):
        self.own()
        self.now = START + 5 * 86400
        self.store.close()
        self.store = accounts.Store(self.path)
        self.assertIsNone(holdings.holder(self.store, self.site))
        # No background or room timer has run yet; the locked claim still refuses.
        self.assertFalse(self.claim(self.now))
        rooms = NS(rooms={})
        self.assertEqual(holdings.reset_warehouses(self.store, rooms), (self.site.key,))
        self.assertIsNone(self.store.holding(self.site.key))

    def test_stale_reset_cannot_erase_a_new_capture_and_room_tick_notifies_once(self):
        self.own(at=START)
        self.assertIsNone(self.store.holding_clear(self.site.key, 'expire', before_since=START))
        self.now = START
        rc = NS(store=self.store, room=NS(loc=NS(id=self.site.loc)))
        with patch.object(holdings, 'refresh') as refresh:
            holdings.reset_warehouse(rc)
            refresh.assert_not_called()
            self.now += 86400
            holdings.reset_warehouse(rc)
            holdings.reset_warehouse(rc)
            refresh.assert_called_once_with(rc.room, self.site)
        self.assertIsNone(self.store.holding(self.site.key))

    def test_old_clan_can_recapture_after_reset_without_reopening_same_day_gold(self):
        self.own()
        self.assertTrue(self.claim(self.now))
        self.store.boss_killed('warehouse-reset-checkpoint', START - 86400)
        self.now = START
        holdings.reset_warehouses(self.store)
        self.assertTrue(self.store.holding_gold_claimed(self.site.key, self.day(self.now)))
        self.assertEqual(self.store.boss_kills(['warehouse-reset-checkpoint']),
                         {'warehouse-reset-checkpoint': START - 86400})
        rc, mob = self.scene(START + 10)
        self.now += 10
        with patch.object(holdings, 'refresh'):
            self.assertEqual(holdings.settle(rc, mob), 'capture')
        self.assertIsNone(mob.capture)
        held = self.store.holding(self.site.key)
        self.assertEqual((held['clan_id'], held['since']), (self.clan, self.now))
        self.assertFalse(self.claim(self.now))
        # Same-cycle own reset/defence preserves the owner's cycle and reward quota.
        rc, mob = self.scene(START + 20)
        self.now += 10
        self.assertEqual(holdings.settle(rc, mob), 'defend')
        self.assertEqual(self.store.holding(self.site.key)['since'], held['since'])
        self.assertFalse(self.claim(self.now))
        # The next day's legitimate reward is available before the next reset.
        self.now = START + 23 * 3600
        self.assertTrue(self.claim(self.now))
        self.assertFalse(self.claim(self.now))

    def test_delayed_old_corpse_cannot_capture_after_reset_or_overwrite_a_new_owner(self):
        for new_owner in (False, True):
            self.own()
            rc, mob = self.scene(START - 5)
            self.now = START + 5
            holdings.reset_warehouses(self.store)
            if new_owner:
                self.own(at=START + 1)
            before = self.store.holding(self.site.key)
            self.assertEqual(holdings.settle(rc, mob), 'none')
            self.assertEqual(self.store.holding(self.site.key), before)
            self.assertIsNone(mob.capture)
            self.store.holding_clear(self.site.key, 'admin')

    def test_claim_rechecks_live_boundary_under_lock_and_keeps_rights_and_tenure(self):
        self.own()
        cutoffs = []
        def crossed_boundary():
            self.assertGreater(self.store.db._atomic_depth, 0)
            cutoffs.append(START)
            return START
        self.assertFalse(self.store.holding_gold_claim(self.site.key, self.day(self.now),
            self.cid, holdings.table().tenure, when=self.now, owner_since=crossed_boundary))
        self.assertEqual(cutoffs, [START])
        with self.store.db:
            self.store.db.execute('UPDATE clan_members SET perm=0 WHERE char_id=?', (self.cid,))
        self.assertFalse(self.claim(self.now))
        with self.store.db:
            self.store.db.execute('UPDATE clan_members SET perm=?, joined_at=? WHERE char_id=?',
                                  (0x400, self.now - 86399, self.cid))
        self.assertFalse(self.claim(self.now))
        with self.store.db:
            self.store.db.execute('UPDATE clan_members SET joined_at=? WHERE char_id=?',
                                  (self.now - 86400, self.cid))
        self.assertTrue(self.claim(self.now))

    def test_reward_reservation_items_and_history_roll_back_together_then_retry(self):
        self.own()
        before = self.store.items_of(self.cid)
        quest = self.store.take_quest(self.cid, self.site.gold_quest, {}, True)
        with self.assertRaisesRegex(RuntimeError, 'grant failed'):
            with storage.atomic(self.store.db):
                self.assertTrue(self.claim(self.now))
                self.store.create_item(self.cid, 7620, items.root_of(7620), count=3)
                self.store.finish_quest(quest, self.cid, self.site.gold_quest, require_active=True)
                raise RuntimeError('grant failed')
        self.assertFalse(self.store.holding_gold_claimed(self.site.key, self.day(self.now)))
        self.assertEqual(self.store.items_of(self.cid), before)
        self.assertIsNotNone(self.store.quest(quest))
        with storage.atomic(self.store.db):
            self.assertTrue(self.claim(self.now))
            self.store.create_item(self.cid, 7620, items.root_of(7620), count=3)
            self.store.finish_quest(quest, self.cid, self.site.gold_quest, require_active=True)
        self.assertFalse(self.claim(self.now))
        self.assertIsNone(self.store.quest(quest))
        self.now = START
        holdings.reset_warehouses(self.store)
        self.assertTrue(self.store.holding_gold_claimed(self.site.key, self.day(self.now)))


if __name__ == '__main__':
    run_cases(WarehouseDailyReset)
