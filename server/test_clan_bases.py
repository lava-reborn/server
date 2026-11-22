"""Weekly clan bases reuse holdings and native quest transactions.

Real stores cover capture/payment persistence, reservations, stale rights,
idempotence, rollback and SQLite connections racing for two different bases.
Native quest handlers cover the live flag and post-commit notification order.
"""
import asyncio
import logging
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)

import accounts
import bosses
import combat
import events
import holdings
import inventory
import mobs
import progression
import quests
import server
import storage
import rooms
import world
from test_quest_state import session
from testkit import run_cases


SLOT = datetime(2026, 11, 21, 20, tzinfo=bosses.ZONE).timestamp()


class ClanBases(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        self.now = SLOT + 10
        self.enterContext(patch.object(bosses, "clock", lambda: self.now))
        account, _ = self.store.register("base-owner", "local-password")
        self.cid, _ = self.store.create_character(account, "BaseOwner", 0, "1")
        self.clan = self.store.clan_create(self.cid, "Base clan", "base-clan", "", None)
        self.store.clan_treasury_adjust(self.clan, 4_500_000, "admin")
        self.base = holdings.site("base_ah")

    def capture(self, s=None, at=None, clan=None):
        s = s or self.base
        return self.store.holding_capture(s.key, clan or self.clan, SLOT, self.cid,
                                          self.now if at is None else at,
                                          base_sites=holdings.base_keys())

    def pay(self, s=None):
        return holdings.pay_rent(self.store, s or self.base, self.cid, self.now)

    def native(self):
        s = session(self.store, char_id=self.cid)
        s.char = progression.Character.load(self.store, self.cid)
        for skill in s.char.skill:
            skill[0] = 20
        s.char.recalc()
        s.char.save(self.store)
        s.active = self.store.character(self.cid)
        s.closed = False
        s.loc = world.location(self.base.loc)
        flag_cell = next(c for c, ty in s.loc.spawns if ty == self.base.flag)
        s.pos = flag_cell
        s.live_cell = lambda: s.pos
        s.npc_type = lambda _: self.base.flag
        s.room = NS(npc=lambda _eid: (flag_cell, self.base.flag))
        s.fee_shown, s.skill_shown = {}, {}
        frames = []
        s.send = lambda command, **p: frames.append((command, p))
        s.answer = lambda text: s.send("answer", text=text)
        return s, frames

    def ready_quest(self):
        return self.store.take_quest(self.cid, self.base.rent_quest, {}, True)

    def leave_owner(self):
        account = self.store.character(self.cid)["account_id"]
        other, _ = self.store.create_character(account, "Successor", 0, "1")
        self.store.clan_member_add(other, self.clan, 0x400, "")
        self.store.clan_leave(self.cid, self.clan)

    def test_capture_health_is_local_and_survives_reset_without_growing(self):
        for base in (self.base, holdings.site("base_dn")):
            with self.subTest(base=base.key):
                original = mobs.stats(base.boss)
                before = vars(original).copy()
                room = rooms.Room(world.location(base.loc), rooms.IdAllocator(), world.mob_types())
                rc = combat.RoomCombat(room, self.store)
                target = next(m for m in rc.mobs.values() if m.type_id == base.boss)
                self.assertIsNot(target.stats, original)
                self.assertEqual((target.hp, target.sp),
                                 (round(original.hp_max * 30), round(original.sp_max * 30)))
                self.assertEqual(target.vitals(), dict(hcur=target.hp, hmax=target.hp,
                                                      scur=target.sp, smax=target.sp))
                for field, value in before.items():
                    if field not in ("hp_max", "sp_max"):
                        self.assertEqual(getattr(target.stats, field), value)
                target.hp = target.sp = 1
                holdings.prepare_room(rc)
                self.assertEqual((target.hp, target.sp), (1, 1))
                target.reset()
                self.assertEqual((target.hp, target.sp), (original.hp_max * 30, original.sp_max * 30))
                self.assertEqual(vars(original), before)
                other = next(s for s in holdings.sites().values()
                             if s.kind != "base" and s.boss == base.boss)
                normal = mobs.Mob(1, base.boss, 0)
                holdings.prepare_room(NS(room=NS(loc=NS(id=other.loc)), mobs={1: normal}))
                self.assertIs(normal.stats, original)
                self.assertEqual(normal.vitals(), dict(hcur=original.hp_max, hmax=original.hp_max,
                                                      scur=original.sp_max, smax=original.sp_max))

    def test_definitions_and_location_specific_weekly_hours(self):
        self.assertEqual(holdings.problems(), [])
        self.assertEqual((self.base.min_level, holdings.site("base_dn").min_level), (16, 12))
        for base in (self.base, holdings.site("base_dn")):
            for loc_id in base.rooms:
                self.assertIs(holdings.site_at(loc_id), base)
            for offset in (-1, 0, 3599, 3600, 86400, 7 * 86400):
                expected = SLOT if 0 <= offset < 3600 else (
                    SLOT + 7 * 86400 if offset == 7 * 86400 else None)
                self.assertEqual(bosses.slot_of(base.boss, SLOT + offset, base.loc), expected)
        # The very same original mob art keeps its daily warehouse schedule.
        sunday = SLOT + 86400
        self.assertIsNone(bosses.slot_of(7454, sunday, 118))
        self.assertEqual(bosses.slot_of(7454, sunday, 128), sunday)

    def test_scoped_health_configuration_rejects_nonfinite_or_excessive_values(self):
        rec = dict(loc=118, boss=7454, flag=4427, min_level=16, title="base")
        self.assertEqual(holdings.Site("default", rec).health_scale, 1)
        for field in ('health_scale', 'guard_health_scale'):
            for value in (0, -1, 101, float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    holdings.Site("invalid", dict(rec, **{field: value}))
            for value in (1, 30, 100):
                self.assertEqual(getattr(holdings.Site("valid", dict(rec, **{field: value})), field), value)

    def test_payment_persists_once_and_expires_at_next_battle(self):
        self.assertEqual(self.capture(), (None, "ok"))
        self.assertIsNone(holdings.paid_base_for(self.store, 609, self.cid, self.now))
        self.assertEqual(self.pay(), 3_000_000)
        self.assertIs(holdings.paid_base_for(self.store, 609, self.cid, self.now), self.base)
        self.assertIsNone(self.pay())
        self.assertEqual(self.store.clan_treasury(self.clan), 3_000_000)
        rent = [r for r in self.store.clan_ledger_rows(self.clan) if r["source"] == "base_rent"]
        self.assertEqual([r["afro"] for r in rent], [-1_500_000])
        self.assertEqual(self.store.holding(self.base.key)["paid_until"], SLOT + 7 * 86400)
        self.assertIsNone(holdings.paid_base_for(self.store, 118, self.cid, SLOT + 7 * 86400))
        # Bases repair at explicit supply NPCs, never at a warehouse flag.
        self.assertEqual(holdings.flag_for(self.store, 118, self.base.flag, self.cid)[1], False)
        self.now = SLOT + 7 * 86400
        self.assertEqual(holdings.flag_for(self.store, 118, self.base.flag, self.cid), (None, False))

    def test_deadline_has_no_grace_and_old_capture_cannot_renew(self):
        self.capture()
        self.now = SLOT + 75 * 60
        self.assertIsNone(self.pay())
        self.now = SLOT + 7 * 86400 + 10
        self.assertIsNone(self.pay())
        self.assertEqual(self.store.clan_treasury(self.clan), 4_500_000)
        self.store.holding_capture(self.base.key, self.clan, SLOT + 7 * 86400,
                                  self.cid, self.now, base_sites=holdings.base_keys())
        self.assertEqual(self.pay(), 3_000_000)

    def test_recapture_resets_lease_but_duplicate_does_not(self):
        self.capture()
        self.pay()
        self.assertEqual(self.capture()[1], "same")
        self.assertEqual(self.store.holding(self.base.key)["paid_until"], SLOT + 7 * 86400)
        self.now += 7 * 86400
        self.store.holding_capture(self.base.key, self.clan, SLOT + 7 * 86400,
                                  self.cid, self.now, base_sites=holdings.base_keys())
        self.assertEqual(self.store.holding(self.base.key)["paid_until"], 0)
        self.assertIsNone(holdings.paid_base_for(self.store, 609, self.cid, self.now))

    def test_one_base_pending_and_paid_but_warehouses_do_not_count(self):
        other = holdings.site("base_dn")
        self.store.holding_set("wh_sever", self.clan, "admin")
        self.assertEqual(self.capture()[1], "ok")
        self.assertEqual(self.capture(other)[1], "occupied")
        self.pay()
        self.assertEqual(self.capture(other)[1], "occupied")
        self.assertEqual(self.store.holding("wh_sever")["clan_id"], self.clan)
        self.assertIsNone(self.store.holding(other.key))

    def test_unpaid_reservation_releases_after_deadline(self):
        self.capture()
        self.assertTrue(self.store.base_reserved(self.clan, holdings.base_keys(), SLOT + 4499))
        self.assertFalse(self.store.base_reserved(self.clan, holdings.base_keys(), SLOT + 4500))
        self.assertFalse(self.store.base_reserved(self.clan, holdings.base_keys(), SLOT + 7 * 86400))

    def test_new_week_clears_old_owner_but_never_current_reservation(self):
        for base in (self.base, holdings.site('base_dn')):
            with self.subTest(base=base.key):
                previous = SLOT - 7 * 86400
                self.now = previous + 300
                self.store.holding_capture(base.key, self.clan, previous, self.cid, self.now)
                self.assertIsNotNone(holdings.pay_rent(self.store, base, self.cid, self.now))
                room = rooms.Room(world.location(base.loc), rooms.IdAllocator(), world.mob_types())
                rc = combat.RoomCombat(room, self.store)
                self.now = SLOT - 1
                rc.keep_hours()
                self.assertIsNotNone(holdings.paid_holder(self.store, base))
                self.now = SLOT
                rc.keep_hours()
                self.assertIsNone(self.store.holding(base.key))
                self.assertEqual(self.store.holding_log(base.key)[0]['how'], 'expire')
                rc.keep_hours()
                self.assertEqual(sum(r['how'] == 'expire' for r in self.store.holding_log(base.key)), 1)
                self.store.holding_capture(base.key, self.clan, SLOT, self.cid, self.now)
                self.assertIsNone(self.store.holding_clear(base.key, 'expire', before_slot=SLOT))
                rc.keep_hours()
                self.assertEqual(self.store.holding(base.key)['slot'], SLOT)
                self.store.holding_clear(base.key, 'admin')

    def test_three_guards_unlock_boss_persist_on_restart_and_return_next_week(self):
        async def check(base):
            self.now = SLOT
            room = rooms.Room(world.location(base.loc), rooms.IdAllocator(), world.mob_types())
            rc = combat.RoomCombat(room, self.store)
            rc.keep_hours()
            guards = [m for m in rc.mobs.values() if m.type_id in base.guards]
            target = next(m for m in rc.mobs.values() if m.type_id == base.boss)
            self.assertEqual(len(guards), 3)
            self.assertTrue(all(m.alive and not m.away and m.slot == SLOT for m in guards))
            self.assertTrue(target.away)
            self.assertNotIn(target.eid, room.npcs)
            target.capture_harm = {self.cid: 100}
            self.assertIsNone(holdings.snapshot(rc, target, None))
            for index, guard in enumerate(guards):
                rc.kill(guard, None)
                rc.keep_hours()
                self.assertEqual(target.eid in room.npcs, index == 2)
                self.assertEqual(self.store.boss_kills([rc.boss_spot(guard)]),
                                 {rc.boss_spot(guard): SLOT})
            restored_room = rooms.Room(world.location(base.loc), rooms.IdAllocator(), world.mob_types())
            restored = combat.RoomCombat(restored_room, self.store)
            restored.keep_hours()
            self.assertTrue(holdings.guards_cleared(restored, base, SLOT))
            self.assertTrue(any(m.type_id == base.boss and m.alive and not m.away
                                for m in restored.mobs.values()))
            self.now = SLOT + 7 * 86400
            restored.keep_hours()
            self.assertFalse(holdings.guards_cleared(restored, base, self.now))
            self.assertEqual(sum(m.alive and not m.away for m in restored.mobs.values()
                                 if m.type_id in base.guards), 3)
            self.assertTrue(next(m for m in restored.mobs.values() if m.type_id == base.boss).away)

        for base in (self.base, holdings.site('base_dn')):
            with self.subTest(base=base.key):
                asyncio.run(check(base))

    def test_member_rights_funds_and_disband_rechecked(self):
        self.capture()
        self.store.clan_member_update(self.cid, self.clan, perm=1)
        self.assertIsNone(self.pay())
        self.store.clan_member_update(self.cid, self.clan, perm=0x400)
        self.assertEqual(self.pay(), 3_000_000)
        self.leave_owner()
        self.assertIsNone(holdings.paid_base_for(self.store, 609, self.cid, self.now))
        self.store.clan_disband(self.clan)
        self.assertIsNone(self.store.holding(self.base.key))

    def test_insufficient_treasury_touches_nothing(self):
        self.capture()
        self.store.clan_treasury_adjust(self.clan, -4_000_001, "admin")
        before = self.store.holding(self.base.key)
        ledger = self.store.clan_ledger_rows(self.clan)
        self.assertIsNone(self.pay())
        self.assertEqual(self.store.holding(self.base.key), before)
        self.assertEqual(self.store.clan_ledger_rows(self.clan), ledger)

    def test_failed_journal_rolls_back_treasury_and_lease(self):
        self.capture()
        before = self.store.holding(self.base.key)
        original = self.store._holding_log
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("failure after lease and treasury journal")
        with patch.object(self.store, "_holding_log", fail), self.assertRaises(RuntimeError):
            self.pay()
        self.assertEqual(self.store.clan_treasury(self.clan), 4_500_000)
        self.assertEqual(self.store.holding(self.base.key), before)
        self.assertFalse(any(r["source"] == "base_rent" for r in self.store.clan_ledger_rows(self.clan)))

    def test_native_quest_success_and_replay_debit_once_after_commit(self):
        self.capture()
        s, frames = self.native()
        self.assertTrue(s.quest_available(quests.get(self.base.rent_quest)))
        qid = self.ready_quest()
        notices = []
        def refreshed(_online, base):
            notices.append(self.store.holding(base.key)["paid_until"])
            self.assertFalse(getattr(self.store.db, "_atomic_depth", 0))
            self.assertTrue(any(n == "cmdAck" and p["res"] == 0 for n, p in frames))
        with patch.object(holdings, "changed", refreshed), \
                patch.object(server.clans.clan_treasury, "tell_balance"):
            s.cmd_q_co(dict(q_id=qid, mob=1))
            s.cmd_q_co(dict(q_id=qid, mob=1))
        self.assertEqual(notices, [SLOT + 7 * 86400])
        self.assertEqual([p["res"] for n, p in frames if n == "cmdAck"], [0, server.RES_NO_SUCH])
        self.assertEqual(self.store.clan_treasury(self.clan), 3_000_000)
        self.assertTrue(self.store.quest_done(self.cid, self.base.rent_quest))
        self.assertFalse(s.quest_available(quests.get(self.base.rent_quest)))

    def test_native_history_failure_rolls_back_payment_and_success_frames(self):
        self.capture()
        s, frames = self.native()
        qid = self.ready_quest()
        original = self.store.finish_quest
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("failure after history")
        with patch.object(self.store, "finish_quest", fail), \
                patch.object(holdings, "changed") as changed:
            s.cmd_q_co(dict(q_id=qid, mob=1))
        changed.assert_not_called()
        self.assertEqual(self.store.clan_treasury(self.clan), 4_500_000)
        self.assertEqual(self.store.holding(self.base.key)["paid_until"], 0)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, self.base.rent_quest))
        self.assertEqual([p["res"] for n, p in frames if n == "cmdAck"], [1])

    def test_native_rent_locks_clan_before_character_and_holding(self):
        self.capture()
        s, _frames = self.native()
        qid = self.ready_quest()
        sql = []
        original = self.store.db.execute
        def execute(statement, args=()):
            sql.append(statement)
            return original(statement, args)
        with patch.object(self.store.db, "execute", execute), \
                patch.object(holdings, "changed"), \
                patch.object(server.clans.clan_treasury, "tell_balance"):
            s.cmd_q_co(dict(q_id=qid, mob=1))
        clan = next(i for i, text in enumerate(sql) if text.startswith("SELECT k.id FROM clans"))
        character = next(i for i, text in enumerate(sql) if text == "SELECT id FROM characters WHERE id = ?")
        holding = next(i for i, text in enumerate(sql)
                       if text.startswith("SELECT clan_id, slot, paid_until FROM clan_holdings"))
        self.assertLess(clan, character)
        self.assertLess(character, holding)

    def test_native_stale_location_distance_and_membership_refused(self):
        self.capture()
        s, frames = self.native()
        qid = self.ready_quest()
        for stale in ("location", "distance", "membership"):
            if stale == "location":
                s.loc = world.location(609)
            elif stale == "distance":
                s.loc = world.location(118)
                s.pos = 0
            else:
                s.pos = next(c for c, ty in s.loc.spawns if ty == self.base.flag)
                self.leave_owner()
            s.cmd_q_co(dict(q_id=qid, mob=1))
            self.assertNotEqual([p["res"] for n, p in frames if n == "cmdAck"][-1], 0)
            self.assertIsNotNone(self.store.quest(qid))
            self.assertEqual(self.store.clan_treasury(self.clan), 4_500_000)

    def test_live_capture_one_member_and_death_checkpoint_are_persistent(self):
        for base in (self.base, holdings.site('base_dn')):
            with self.subTest(base=base.key):
                self.now = SLOT + 300
                sess = NS(char_id=self.cid, combat=NS(dead=False, level=base.min_level - 1),
                          answer=lambda text: None)
                room = NS(loc=world.location(base.loc), players=[sess], npcs={})
                rc = NS(store=self.store, room=room, place=(base.loc, None, None))
                rc.mobs = {1: NS(type_id=base.guards[0], alive=False, slot=SLOT)}
                rc.boss_spot = lambda mob: combat.RoomCombat.boss_spot(rc, mob)
                mob = NS(type_id=base.boss, slot=SLOT, hp_max=100, sp_max=0,
                         home=100, capture_harm={self.cid: 100})
                snap = holdings.snapshot(rc, mob, None)
                self.assertIsNone(holdings.winner(snap, 1, base.min_level))
                sess.combat.level += 1
                mob.capture = holdings.snapshot(rc, mob, None)
                self.assertEqual(holdings.settle(rc, mob), 'capture')
                self.assertEqual(self.store.holding(base.key)['clan_id'], self.clan)
                self.assertEqual(self.store.boss_kills([rc.boss_spot(mob)]), {rc.boss_spot(mob): SLOT})
                self.assertIsNone(holdings.settle(rc, mob))
                self.assertEqual(len(self.store.holding_log(base.key)), 1)
                self.now = SLOT + 3600
                self.assertIsNone(holdings.snapshot(rc, mob, None))
                # A second independent case must not reuse this clan's
                # still-open reservation for the other base.
                self.store.holding_clear(base.key, 'admin')

    def test_capture_and_boss_death_roll_back_together(self):
        snap = dict(site=self.base.key, slot=SLOT, at=self.now, pool=100,
                    killer=self.cid, killer_clan=self.clan, fighters=[
                        dict(char=self.cid, clan=self.clan, clan_name="Base clan",
                             here=True, alive=True, level=16, harm=100)])
        rc = NS(store=self.store, room=NS(loc=world.location(118), players=[], npcs={}),
                boss_spot=lambda _mob: "base-checkpoint")
        mob = NS(capture=snap)
        original = self.store.boss_killed
        def fail(*args):
            original(*args)
            raise RuntimeError("failure after boss checkpoint")
        with patch.object(self.store, "boss_killed", fail), self.assertRaises(RuntimeError):
            holdings.settle(rc, mob)
        self.assertIsNone(self.store.holding(self.base.key))
        self.assertEqual(self.store.holding_log(self.base.key), [])
        self.assertEqual(self.store.boss_kills(["base-checkpoint"]), {})

    def test_ineligible_second_base_clan_cannot_block_another_clan(self):
        self.capture(holdings.site("base_dn"))
        aid, _ = self.store.register("other-base-clan", "password")
        cid, _ = self.store.create_character(aid, "OtherOwner", 0, "1")
        other = self.store.clan_create(cid, "Other clan", "other-clan", "", None)
        fighters = [dict(char=c, clan=k, clan_name=n, here=True, alive=True, level=16, harm=h)
                    for c, k, n, h in ((self.cid, self.clan, "Base clan", 100),
                                       (cid, other, "Other clan", 50))]
        mob = NS(capture=dict(site=self.base.key, slot=SLOT, at=self.now, pool=150,
                              killer=self.cid, killer_clan=self.clan, fighters=fighters))
        rc = NS(store=self.store, room=NS(loc=world.location(118), players=[], npcs={}),
                boss_spot=lambda _mob: "other-base")
        self.assertEqual(holdings.settle(rc, mob), "capture")
        self.assertEqual(self.store.holding(self.base.key)["clan_id"], other)

    def test_legacy_schema_migration_adds_unpaid_default(self):
        self.capture()
        self.store.db.execute("ALTER TABLE clan_holdings DROP COLUMN paid_until")
        self.store.db.commit()
        accounts.migrate(self.store.db)
        self.assertEqual(self.store.holding(self.base.key)["paid_until"], 0)

    def test_two_connections_racing_different_bases_reserve_only_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "base-race.sqlite")
            setup = accounts.Store(path)
            aid, _ = setup.register("race", "password")
            cid, _ = setup.create_character(aid, "RaceOwner", 0, "1")
            clan = setup.clan_create(cid, "Race clan", "race-clan", "", None)
            setup.close()
            barrier = threading.Barrier(2)
            results, errors = [], []
            def race(key):
                connection = None
                try:
                    connection = accounts.Store(path)
                    barrier.wait(timeout=10)
                    results.append(connection.holding_capture(
                        key, clan, SLOT, cid, SLOT + 10, base_sites=holdings.base_keys())[1])
                except Exception as exc:
                    errors.append(repr(exc))
                finally:
                    if connection is not None:
                        connection.close()
            threads = [threading.Thread(target=race, args=(key,)) for key in holdings.base_keys()]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), ["occupied", "ok"])
            restored = accounts.Store(path)
            try:
                self.assertEqual(len(restored.holdings()), 1)
            finally:
                restored.close()

    def test_two_officers_racing_payment_debit_once_and_survive_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rent-race.sqlite")
            setup = accounts.Store(path)
            aid, _ = setup.register("rent-race", "password")
            head, _ = setup.create_character(aid, "RentHead", 0, "1")
            officer, _ = setup.create_character(aid, "RentOfficer", 0, "1")
            clan = setup.clan_create(head, "Rent clan", "rent-clan", "", None)
            setup.clan_member_add(officer, clan, 0x400, "")
            setup.clan_treasury_adjust(clan, 4_500_000, "admin")
            setup.holding_capture(self.base.key, clan, SLOT, head, SLOT + 10,
                                  base_sites=holdings.base_keys())
            setup.close()
            barrier = threading.Barrier(2)
            results, errors = [], []
            def pay(cid):
                connection = None
                try:
                    connection = accounts.Store(path)
                    barrier.wait(timeout=10)
                    results.append(holdings.pay_rent(connection, self.base, cid, SLOT + 20))
                except Exception as exc:
                    errors.append(repr(exc))
                finally:
                    if connection is not None:
                        connection.close()
            threads = [threading.Thread(target=pay, args=(cid,)) for cid in (head, officer)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(results.count(None), 1)
            self.assertEqual(results.count(3_000_000), 1)
            restored = accounts.Store(path)
            try:
                self.assertEqual(restored.clan_treasury(clan), 3_000_000)
                self.assertEqual(restored.holding(self.base.key)["paid_until"], SLOT + 7 * 86400)
                self.assertIs(holdings.paid_base_for(restored, 609, officer, SLOT + 30), self.base)
                self.assertIsNone(holdings.pay_rent(restored, self.base, head, SLOT + 30))
                self.assertEqual(len([r for r in restored.clan_ledger_rows(clan)
                                      if r["source"] == "base_rent"]), 1)
            finally:
                restored.close()


class WarehouseGold(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        self.now = time.time()
        self.day = server.Session.day_start(self.now)
        date = datetime.fromtimestamp(self.now, bosses.ZONE)
        self.clock = date.replace(hour=19, minute=5, second=0, microsecond=0).timestamp()
        self.enterContext(patch.object(bosses, "clock", lambda: self.clock))
        account, _ = self.store.register("warehouse-gold", "password")
        self.cid, _ = self.store.create_character(account, "GoldHead", 0, "1")
        self.officer, _ = self.store.create_character(account, "GoldOfficer", 0, "1")
        self.clan = self.store.clan_create(self.cid, "Gold clan", "gold-clan", "", None,
                                          when=self.now - 3 * 86400)
        self.store.clan_member_add(self.officer, self.clan, 0x400, "", when=self.now - 3 * 86400)
        self.site = holdings.site("wh_sever")
        self.store.holding_set(self.site.key, self.clan, "admin")
        self.s, self.frames = self.native(self.cid)

    def native(self, cid):
        s = session(self.store, level=20, char_id=cid)
        s.char = progression.Character.load(self.store, cid)
        for skill in s.char.skill:
            skill[0] = 20
        s.char.recalc()
        s.char.save(self.store)
        s.active = self.store.character(cid)
        s.closed = False
        s.loc = world.location(self.site.loc)
        cell = next(c for c, ty in s.loc.spawns if ty == self.site.box)
        s.pos = cell
        s.live_cell = lambda: s.pos
        s.npc_type = lambda _eid: self.site.box
        s.room = NS(npc=lambda _eid: (cell, self.site.box, world.COMMONER))
        s.fee_shown, s.skill_shown = {}, {}
        frames = []
        s.send = lambda command, **p: frames.append((command, p))
        s.answer = lambda text: s.send("answer", text=text)
        return s, frames

    def ready(self, cid=None):
        return self.store.take_quest(cid or self.cid, self.site.gold_quest, {}, True)

    def claim(self, qid, sess=None):
        (sess or self.s).cmd_q_co(dict(q_id=qid, mob=1, obj_idx=0))

    def claims(self):
        return [dict(r) for r in self.store.db.execute("SELECT * FROM clan_holding_claims")]

    def test_seven_native_services_use_only_original_ingots_and_replace_personal_rewards(self):
        self.assertEqual(holdings.problems(), [])
        for i, key in enumerate(("wh_sever", "wh_vostok", "wh_ug", "wh_dn_sever",
                                  "wh_dn_vostok", "wh_dn_ug", "wh_ah_center")):
            site = holdings.site(key)
            q = quests.get(site.gold_quest)
            expected = [(7620, 3)] if i < 3 else [(4796, 1)] if i < 6 else [(4796, 1), (7620, 2)]
            self.assertEqual(q.rew_also, expected)
            self.assertEqual((q.rew_gold, q.rew_afro, q.service, q.repeatable), (0, 0, True, 1))
            self.assertEqual((q.give, q.take, q.holders), ([site.box], [site.box], key))
            personal = quests.get(site.quest)
            self.assertTrue(quests.acquisition_blocked(personal))
            self.assertFalse(quests.acquisition_blocked(q))
            self.assertEqual(events.table().gates[q.type], events.table().gates[personal.type])

    def test_all_seven_real_hand_ins_grant_the_exact_city_totals(self):
        for site in holdings.sites().values():
            if site.kind != "warehouse":
                continue
            self.site = site
            self.store.holding_set(site.key, self.clan, "admin")
            self.s, self.frames = self.native(self.cid)
            self.claim(self.ready())
            self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [0], site.key)
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 11, 4796: 4})
        self.assertEqual(len(self.claims()), 7)
        self.assertEqual(self.store.clan_treasury(self.clan), 0)

    def test_native_claim_and_duplicate_instances_mint_only_three_one_gold_ingots(self):
        self.assertTrue(self.s.quest_available(quests.get(self.site.gold_quest)))
        qid = self.ready()
        self.claim(qid)
        self.claim(qid)
        second = self.ready()
        self.claim(second)
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})
        self.assertEqual(len(self.claims()), 1)
        self.assertEqual(self.claims()[0]["char_id"], self.cid)
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"],
                         [0, server.RES_NO_SUCH, server.RES_NOT_AVAILABLE])
        self.assertIsNotNone(self.store.quest(second))
        self.assertFalse(self.s.quest_available(quests.get(self.site.gold_quest)))

    def test_legacy_personal_reward_cannot_pay_even_from_an_existing_journal(self):
        qid = self.store.take_quest(self.cid, self.site.quest, {}, True)
        before = (self.store.money(self.cid), self.s.inv.rows())
        self.claim(qid)
        self.assertEqual([p['res'] for n, p in self.frames if n == 'cmdAck'],
                         [server.RES_NOT_AVAILABLE])
        self.assertEqual((self.store.money(self.cid), self.s.inv.rows()), before)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertTrue(self.s.quest_available(quests.get(self.site.gold_quest)))
        self.store.clan_member_update(self.officer, self.clan, perm=1)
        member, _ = self.native(self.officer)
        self.assertFalse(member.quest_available(quests.get(self.site.quest)))
        self.assertFalse(member.quest_available(quests.get(self.site.gold_quest)))
        self.claim(self.ready())
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})

    def test_shared_daily_claim_survives_capture_release_disband_and_next_owner(self):
        self.claim(self.ready())
        self.store.holding_clear(self.site.key, "admin")
        self.store.clan_disband(self.clan)
        aid, _ = self.store.register("next-gold-clan", "password")
        cid, _ = self.store.create_character(aid, "NextGoldOwner", 0, "1")
        clan = self.store.clan_create(cid, "Next clan", "next-clan", "", None,
                                      when=self.now - 3 * 86400)
        self.store.holding_set(self.site.key, clan, "capture")
        self.assertFalse(self.store.holding_gold_claim(self.site.key, self.day, cid, 86400,
                                                       self.now + 10))
        self.assertTrue(self.store.holding_gold_claim(self.site.key, self.day + 86400, cid, 86400,
                                                      self.now + 86400))
        self.assertEqual(len(self.claims()), 2)

    def test_roles_membership_tenure_and_live_box_are_rechecked(self):
        qid = self.ready(self.officer)
        s, frames = self.native(self.officer)
        self.store.clan_member_update(self.officer, self.clan, perm=1)
        self.claim(qid, s)
        self.store.clan_member_update(self.officer, self.clan, perm=0x400)
        self.store.db.execute("UPDATE clan_members SET joined_at = ? WHERE char_id = ?",
                              (int(self.now - 23 * 3600), self.officer))
        self.store.db.commit()
        self.claim(qid, s)
        self.store.db.execute("UPDATE clan_members SET joined_at = ? WHERE char_id = ?",
                              (int(self.now - 3 * 86400), self.officer))
        self.store.db.commit()
        s.pos = 0
        self.claim(qid, s)
        self.assertTrue(all(p["res"] != 0 for n, p in frames if n == "cmdAck"))
        self.assertEqual(self.claims(), [])
        self.assertEqual(s.inv.bag_pieces(), {})
        self.assertIsNotNone(self.store.quest(qid))

    def test_carry_limit_is_checked_even_with_normal_quest_overweight_exception(self):
        self.assertTrue(server.QUEST_ITEMS_PAST_WEIGHT)
        qid = self.ready()
        with patch.object(self.s.inv, "carry_limit", return_value=2):
            self.claim(qid)
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [server.RES_OVERLOAD])
        self.assertEqual(self.claims(), [])
        self.assertIsNotNone(self.store.quest(qid))
        self.claim(qid)
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})

    def test_item_failure_after_claim_insert_restores_claim_items_history_and_retry(self):
        qid = self.ready()
        original = self.s.inv.give_pieces
        def fail(*args):
            original(*args)
            raise RuntimeError("failure after item creation")
        with patch.object(self.s.inv, "give_pieces", fail):
            self.claim(qid)
        self.assertEqual(self.claims(), [])
        self.assertEqual(self.s.inv.bag_pieces(), {})
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, self.site.gold_quest))
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [1])
        self.claim(qid)
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})
        self.assertEqual(len(self.claims()), 1)

    def test_unknown_commit_result_cannot_mint_again_after_reconnect(self):
        qid = self.ready()
        raw = self.store.db.raw
        def commit():
            raw.commit()
            raise ConnectionError("commit succeeded; reply lost")
        proxy = NS(commit=commit, rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)), \
                patch.object(self.s, "close") as close:
            self.claim(qid)
        close.assert_called_once_with(force=True)
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})
        self.assertEqual(len(self.claims()), 1)
        self.s, self.frames = self.native(self.cid)
        self.claim(qid)
        self.claim(self.ready())
        self.assertEqual(self.s.inv.bag_pieces(), {7620: 3})
        self.assertEqual(len(self.claims()), 1)

    def test_two_sql_connections_cannot_claim_the_same_warehouse_day_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "gold-race.sqlite")
            setup = accounts.Store(path)
            aid, _ = setup.register("gold-race", "password")
            head, _ = setup.create_character(aid, "RaceGoldHead", 0, "1")
            officer, _ = setup.create_character(aid, "RaceGoldOfficer", 0, "1")
            clan = setup.clan_create(head, "Race gold clan", "race-gold-clan", "", None,
                                     when=self.now - 3 * 86400)
            setup.clan_member_add(officer, clan, 0x400, "", when=self.now - 3 * 86400)
            setup.holding_set(self.site.key, clan, "admin")
            setup.close()
            barrier = threading.Barrier(2)
            results, errors = [], []
            def claim(cid):
                connection = None
                try:
                    connection = accounts.Store(path)
                    barrier.wait(timeout=10)
                    with storage.atomic(connection.db):
                        won = connection.holding_gold_claim(self.site.key, self.day, cid, 86400, self.now)
                        if won:
                            fields = inventory.new_fields(7620, 3)
                            root = fields.pop("root")
                            fields["slot"] = inventory.BAG
                            connection.create_item(cid, 7620, root, **fields)
                    results.append(won)
                except Exception as exc:
                    errors.append(repr(exc))
                finally:
                    if connection is not None:
                        connection.close()
            threads = [threading.Thread(target=claim, args=(cid,)) for cid in (head, officer)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), [False, True])
            restored = accounts.Store(path)
            try:
                self.assertTrue(restored.holding_gold_claimed(self.site.key, self.day))
                pieces = sum(int(r["count"]) for r in restored.db.execute(
                    "SELECT count FROM items WHERE type_id = 7620"))
                self.assertEqual(pieces, 3)
                self.assertFalse(restored.holding_gold_claim(self.site.key, self.day, head, 86400, self.now))
            finally:
                restored.close()


if __name__ == "__main__":
    run_cases(ClanBases, WarehouseGold)
