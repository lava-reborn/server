"""Real harvest commands and transactions; no server, sockets or wall-clock waits."""
import logging
from contextlib import ExitStack
import copy
import os
import random
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)

import accounts
import combat
import eden
import eden_ground
import eden_harvest as harvest
import inventory
import items
import mobs
import pace
import progression
import quests
import rooms
import server
import storage
import world
from test_quest_state import session
from testkit import run_cases


class EdenHarvestTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch.object(pace, "SCALE", 1))
        self.store = accounts.Store.temporary()
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        aid, _ = self.store.register("harvest_test", "isolated-password")
        self.cid, _ = self.store.create_character(aid, "HarvestTester", 0, "1")
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.active = self.store.character(self.cid)
        self.s.closed, self.s.on_map, self.s.walk = False, False, None
        self.s.writer = NS(is_closing=lambda: False)
        self.s.loc = world.location(264)
        self.s.gx, self.s.gy = eden.target_cell(264)
        self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
        self.s.room.players[self.s] = None
        self.frames = []
        self.s.send = lambda command, **params: self.frames.append((command, params))
        self.s.answer = lambda text: self.frames.append(("answer", text))
        self.s.cancel_passage = self.s.stop_chase = lambda: None
        self.s.count_bag = lambda: self.frames.append(("count_bag", {}))
        self.s.live_cell = lambda: self.s.pos
        self.s.eden_sentence = eden.assign(self.store, self.cid, "test", "Harvest regression")
        self.s.combat = self.f = combat.Fighter(self.s)
        self.rc = self.f.rc
        self.palm = next(m for m in self.rc.mobs.values() if m.type_id == 1790)
        self.s.pos = next(c for c in progression.hex_neighbours(
            self.palm.cell, self.s.loc.width, self.s.loc.height) if c not in self.s.loc.obstacles)
        self.tool = self.give(harvest.TOOL, inventory.PRIMARY)
        self.clock = 100.0
        self.enterContext(patch.object(harvest.time, 'time', side_effect=lambda: self.clock))
        self.enterContext(patch.object(harvest.RNG, "choice", side_effect=lambda values: values[0]))
        self.enterContext(patch.object(harvest.RNG, "random", return_value=0.5))
        self.enterContext(patch.object(harvest.RNG, "randint", return_value=1700))
        self.enterContext(patch.object(self.s.inv, "carry_limit", return_value=1000000))
        self.pending = None

        def schedule(revision, kind, delay, callback, *args):
            timer = NS(cancel=lambda: None)
            setattr(self.f, kind, timer)
            self.pending = (revision, kind, callback, args, delay)
        self.f.schedule_action = schedule
        self.addCleanup(self.f.cancel_timers)
        self.addCleanup(self.stop_ground_timers)
        self.reset_cycle()

    def give(self, type_id, slot=inventory.BAG):
        fields = inventory.new_fields(type_id)
        root = fields.pop("root")
        fields["slot"] = slot
        return self.store.create_item(self.cid, type_id, root, **fields)

    def dispose(self):
        # Borrowed by other test cases without its own asyncio runner.
        # Its registered cleanups are synchronous; execute all of them even
        # if one fails, without IsolatedAsyncioTestCase swallowing runner errors.
        with ExitStack() as stack:
            for callback, args, kwargs in self._cleanups:
                stack.callback(callback, *args, **kwargs)
            self._cleanups.clear()

    def reset_cycle(self):
        if not self.palm.alive:
            self.clock = self.palm._eden_due
            self.palm._eden_respawn_timer.cancel()
            harvest._respawn(self.rc, self.palm, self.palm._eden_respawn_token)
        harvest._cycle(self.palm)

    def stop_ground_timers(self):
        for target in self.rc.mobs.values():
            for name in ('_eden_respawn_timer', '_eden_corpse_timer'):
                timer = getattr(target, name, None)
                if timer is not None:
                    timer.cancel()
        for bag in self.rc.loot.values():
            if bag.expiry:
                bag.expiry.cancel()

    def prime_final_hit(self):
        for _ in range(2):
            self.click()
            self.finish()
        self.assertEqual(self.palm.hp, 1600)

    def click(self, row=None, target=None):
        row = self.tool if row is None else row
        target = "1%08x" % self.palm.eid if target is None else target
        obj = "0" if row is False else str(inventory.oid_of(row))
        self.f.use_fire(dict(obj=obj, target=target))

    def finish(self, saved=None):
        revision, kind, callback, args, delay = saved or self.pending
        if revision == self.f.action_revision:
            self.clock += delay
        combat.Fighter.finish_action(self.f, revision, kind, callback, args)

    def amounts(self):
        return self.awarded(self.s)

    def awarded(self, sess):
        amounts = {t: sess.inv.bag_pieces().get(t, 0) for t in harvest.REWARDS}
        for row in self.store.db.execute(
                'SELECT i.type_id, i.count FROM items i JOIN eden_ground e ON e.uniq=i.uniq'
                ' WHERE e.owner_char=?', (sess.char_id,)).fetchall():
            amounts[row['type_id']] += row['count']
        return amounts

    def pickup(self, worker=None):
        fighter = worker.f if worker else self.f
        frames = worker.frames if worker else self.frames
        fighter.open_loot(dict(target=self.palm.cell))
        frames.clear()
        fighter.ss_upd(dict(s_status=3))
        self.assertEqual([p['res'] for c, p in frames if c == 'cmdAck'], [0])

    def other_worker(self, number):
        aid, _ = self.store.register("worker_%d" % number, "isolated-password")
        cid, _ = self.store.create_character(aid, "Worker%d" % number, 0, "1")
        s = session(self.store, char_id=cid)
        s.char = progression.Character.load(self.store, cid)
        s.active = self.store.character(cid)
        s.closed, s.on_map, s.walk = False, False, None
        s.writer = NS(is_closing=lambda: False)
        s.loc, s.room = self.s.loc, self.s.room
        s.gx, s.gy = eden.target_cell(264)
        s.pos = self.s.pos
        s.live_cell = lambda: s.pos
        s.cancel_passage = s.stop_chase = lambda: None
        s.eden_sentence = eden.assign(self.store, cid, "test", "Shared harvest regression")
        worker = NS(s=s, frames=[], pending=None)
        s.send = lambda command, **params: worker.frames.append((command, params))
        s.answer = lambda text: worker.frames.append(("answer", text))
        s.count_bag = lambda: worker.frames.append(("count_bag", {}))
        s.combat = worker.f = combat.Fighter(s)
        s.room.players[s] = None
        fields = inventory.new_fields(harvest.TOOL)
        root = fields.pop("root")
        worker.tool = self.store.create_item(cid, harvest.TOOL, root,
                                            **dict(fields, slot=inventory.PRIMARY))
        self.enterContext(patch.object(s.inv, "carry_limit", return_value=1000000))

        def schedule(revision, kind, delay, callback, *args):
            setattr(worker.f, kind, NS(cancel=lambda: None))
            worker.pending = (revision, kind, callback, args, delay)
        worker.f.schedule_action = schedule
        worker.click = lambda: worker.f.use_fire(dict(
            obj=str(inventory.oid_of(worker.tool)), target="1%08x" % self.palm.eid))
        self.addCleanup(worker.f.cancel_timers)
        return worker

    def impact_at(self, when, pending, fighter=None):
        self.clock = when
        revision, kind, callback, args, _delay = pending
        combat.Fighter.finish_action(fighter or self.f, revision, kind, callback, args)

    def resource_count(self, sess=None):
        return sum(self.awarded(sess or self.s).values())

    async def test_two_workers_combine_damage_without_duplicate_rewards(self):
        other = self.other_worker(2)
        self.click()
        other.click()
        self.impact_at(101, self.pending)
        self.assertEqual(self.palm.hp, 3300)
        self.impact_at(101, other.pending, other.f)
        self.assertEqual(self.palm.hp, 1600)
        self.assertIsNone(other.f.strike)
        self.assertEqual([p for c, p in other.frames if c == "cmdAck"], [{"res": 0}])
        self.assertEqual(other.pending[-1], pace.paced(1))
        self.assertEqual(self.clock, 101)
        self.assertEqual((self.resource_count(), self.resource_count(other.s)), (0, 0))
        other.click()
        saved = other.pending
        self.impact_at(102, saved, other.f)
        self.impact_at(102, saved, other.f)
        self.assertEqual((self.resource_count(), self.resource_count(other.s)), (0, 1))
        self.assertEqual(self.palm.hp, 0)
        self.assertFalse(self.palm.alive)

    async def test_three_workers_progress_one_shared_cycle_and_only_finisher_receives_item(self):
        other, third = self.other_worker(2), self.other_worker(3)
        self.click()
        other.click()
        third.click()
        self.impact_at(101, self.pending)
        self.impact_at(101, other.pending, other.f)
        self.assertEqual(self.palm.hp, 1600)
        self.impact_at(101, third.pending, third.f)
        self.assertEqual(self.clock, 101)
        self.assertEqual([self.resource_count(s) for s in (self.s, other.s, third.s)], [0, 0, 1])
        self.assertEqual(self.palm.hp, 0)

    async def test_concurrent_final_strikes_never_carry_old_progress_into_next_cycle(self):
        other, third = self.other_worker(2), self.other_worker(3)
        self.prime_final_hit()
        other.click()
        third.click()
        old = third.pending
        old_generation = self.palm._eden_cycle
        self.impact_at(103, other.pending, other.f)
        self.assertIsNot(self.palm._eden_cycle, old_generation)
        fresh_hp = self.palm.hp
        self.impact_at(103, old, third.f)
        self.impact_at(103, old, third.f)
        self.assertEqual(self.palm.hp, fresh_hp)
        self.assertEqual([self.resource_count(s) for s in (self.s, other.s, third.s)], [0, 1, 0])
        self.assertTrue(any(c == "actionCancel" for c, _ in third.frames))
        third.click()
        self.assertIsNone(third.f.strike)
        self.reset_cycle()
        fresh_hp = self.palm.hp
        third.click()
        self.impact_at(104, third.pending, third.f)
        self.assertEqual(self.palm.hp, fresh_hp - 1700)

    async def test_shared_finisher_failure_preserves_progress_and_one_hidden_reward(self):
        other = self.other_worker(2)
        self.prime_final_hit()
        self.click()
        other.click()
        generation = self.palm._eden_cycle
        original = harvest._create_ground
        def fail(*args):
            original(*args)
            raise RuntimeError("injected shared harvest rollback")
        with patch.object(harvest, "_create_ground", side_effect=fail):
            self.impact_at(103, self.pending)
        self.assertIs(self.palm._eden_cycle, generation)
        self.assertEqual(self.palm.hp, 1600)
        self.assertEqual(self.resource_count(), 0)
        chosen = self.palm._eden_reward
        with patch.object(harvest.RNG, "choice", side_effect=AssertionError("must not reroll reward")):
            self.impact_at(103, other.pending, other.f)
        self.assertEqual(self.awarded(other.s).get(chosen), 1)
        self.assertEqual(self.resource_count() + self.resource_count(other.s), 1)

    async def test_shared_publication_failure_cannot_reuse_cycle_or_skip_next_swing(self):
        other, third = self.other_worker(2), self.other_worker(3)
        self.prime_final_hit()
        other.click()
        third.click()
        original = self.rc.room.broadcast
        def fail(frame, *args, **kwargs):
            if frame[0] == "ss_loot":
                self.assertFalse(self.store.db.raw.in_transaction)
                raise OSError("lost shared harvest reply")
            original(frame, *args, **kwargs)
        with patch.object(self.rc.room, "broadcast", fail), self.assertRaises(OSError):
            self.impact_at(103, other.pending, other.f)
        self.impact_at(103, third.pending, third.f)
        self.assertEqual(self.palm.hp, 0)
        self.assertEqual([self.resource_count(s) for s in (self.s, other.s, third.s)], [0, 1, 0])
        self.reset_cycle()
        self.click()
        third.click()
        self.impact_at(104, self.pending)
        self.assertEqual(self.resource_count() + self.resource_count(third.s), 0)
        self.impact_at(104, third.pending, third.f)
        self.assertEqual(self.palm.hp, 1600)
        self.assertEqual(self.resource_count() + self.resource_count(third.s), 0)
        third.click()
        self.impact_at(105, third.pending, third.f)
        self.assertEqual(self.resource_count() + self.resource_count(third.s), 1)

    async def test_damage_boundaries_need_three_or_four_hits_without_loot_xp_or_overkill(self):
        before = copy.deepcopy((self.store.money(self.cid), self.s.char.skill, self.s.char.spec))
        for rolled, damages in ((1600, [1600, 1600, 1600, 200]),
                                (1800, [1800, 1800, 1400])):
            self.reset_cycle()
            self.frames.clear()
            amount = sum(self.amounts().values())
            started = self.clock
            with patch.object(self.f, "award_xp", side_effect=AssertionError("no XP")), \
                 patch.object(self.rc, "kill", side_effect=AssertionError("no kill")), \
                 patch.object(self.rc, "melee_damage", side_effect=AssertionError("no combat formula")), \
                 patch.object(harvest.RNG, "randint", return_value=rolled) as damage_roll:
                for index in range(len(damages)):
                    self.click()
                    self.assertIsNotNone(self.f.strike)
                    saved = self.pending
                    self.finish()
                    self.finish(saved)  # saved callback cannot issue another item
                    self.assertEqual(self.resource_count(), amount + int(index == len(damages) - 1))
                self.assertEqual([call.args for call in damage_roll.call_args_list],
                                 [(1600, 1800)] * len(damages))
            self.assertEqual(sum(self.amounts().values()), amount + 1)
            self.assertEqual(self.clock - started, len(damages) * pace.paced(1))
            self.assertFalse(self.palm.alive)
            self.assertEqual(self.palm.hp, 0)
            self.assertEqual([p["dmg"] for c, p in self.frames if c == "caHit"], damages)
            self.assertEqual(sum(damages), 5000)
            self.assertFalse(any(c == 'rp_info' for c, _ in self.frames))
            self.assertTrue(any(c == 'lch' and 'dead' in p for c, p in self.frames))
            self.assertEqual(sum(self.s.inv.bag_pieces().get(t, 0) for t in harvest.REWARDS), 0)
        self.assertEqual((self.store.money(self.cid), self.s.char.skill, self.s.char.spec), before)
        self.assertEqual(self.store.item(self.tool["uniq"])["brk"], self.tool["brk"])

    async def test_character_level_and_stats_do_not_change_hit_progress(self):
        for level in (1, 20):
            for skill in self.s.char.skill:
                skill[0] = level
            self.s.char.attrib[progression.STRENGTH] = 5 if level == 1 else 50
            self.reset_cycle()
            self.click()
            self.finish()
            self.assertEqual(self.palm.hp, 3300)

    async def test_strike_timing_and_ap_follow_the_current_tool_static_frame(self):
        original = items.params_of
        for milliseconds, cost in ((250, 3), (1750, 7)):
            def configured(type_id):
                params = original(type_id)
                return (dict(params, strike_time=milliseconds, strike_cost=cost)
                        if type_id == harvest.TOOL else params)
            self.reset_cycle()
            started = self.clock
            paid = []
            with patch.object(items, "params_of", side_effect=configured), \
                 patch.object(self.f, "c_ap", side_effect=lambda: paid.append(self.f.ap)):
                for _ in range(3):
                    self.click()  # Real Fighter.use_fire -> the harvest adapter.
                    self.assertEqual(self.pending[-1], milliseconds / 1000.0)
                    self.finish()
            self.assertEqual(self.clock - started, 3 * milliseconds / 1000.0)
            self.assertEqual(paid, [self.f.ap_max - cost] * 3)

    async def test_tool_static_frame_matches_actual_damage_timing_and_requirements(self):
        si = items.params_of(harvest.TOOL)
        self.assertEqual(tuple(si[key] for key in (
            "h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max",
            "strike_time", "strike_cost")), (1600, 1800, 0, 0, 1000, 0))
        for mask in ("need_skills_m", "need_specs_m", "need_attribs_m"):
            self.assertEqual(si[mask], 0)
        self.assertIsNone(inventory.weapon_requirement_error(self.tool, self.s.char))
        for level in (0, 20):
            for skill in self.s.char.skill:
                skill[0] = level
            harvest._cycle(self.palm)
            self.assertEqual((self.palm.hp, self.palm.hp_max), (5000, 5000))
            self.frames.clear()
            self.click()
            self.finish()
            impacts = [p for c, p in self.frames if c == "caHit"]
            self.assertEqual([(p["dmg"], p["sdmg"]) for p in impacts], [(1700, 0)])

    async def test_default_starter_can_collect_twenty_leaves_without_basket_or_mocked_capacity(self):
        # Recreate the real creation/assignment loadout, retaining the starter
        # pistol and ammunition; only the dedicated cleaver is auto-issued.
        self.store.delete_item(self.tool["uniq"])
        self.s.inv.starter_kit(self.cid)
        eden.grant_tools(self.store, self.cid)
        self.tool = next(r for r in self.s.inv.rows() if r["type_id"] == harvest.TOOL)
        ordinary = {r["uniq"]: r for r in self.s.inv.rows()
                    if r["type_id"] not in eden.LOCAL_ITEMS}
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.s.transport = None
        self.s.inv.refresh_gear(push=False)

        def exchange(banana):
            qtype = {eden.GREEN_BANANA: 18111, eden.GOOD_BANANA: 18112,
                     eden.BAD_BANANA: 18113}[banana]
            quest = quests.get(qtype)
            giver = quest.give[0]
            loc_id = next(loc_id for loc_id in sorted(eden.LOCATIONS)
                          if any(t == giver for _cell, t in world.location(loc_id).spawns)
                          or any(row['type'] == giver for row in world.placements().get(loc_id, ())))
            old = self.s.loc, self.s.room, self.s.pos, self.s.gx, self.s.gy
            self.s.loc = world.location(loc_id)
            self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
            self.s.gx, self.s.gy = eden.target_cell(loc_id)
            npc, entry = next((eid, entry) for eid, entry in self.s.room.npcs.items()
                              if entry.type_id == quest.give[0])
            self.s.pos = entry.cell
            self.frames.clear()
            self.s.cmd_q_st(dict(mob=npc, q_idx=quests.given_by(quest.give[0]).index(qtype)))
            qid = next(r["q_id"] for r in self.store.quests(self.cid) if r["type"] == qtype)
            self.s.cmd_q_co(dict(q_id=qid, mob=npc, obj_idx=0))
            self.assertEqual([p["res"] for c, p in self.frames if c == "cmdAck"], [0, 0])
            self.s.loc, self.s.room, self.s.pos, self.s.gx, self.s.gy = old

        real_capacity = inventory.Inventory.carry_limit.__get__(self.s.inv)
        with patch.object(self.s.inv, "carry_limit", real_capacity):
            self.assertEqual(self.s.char.attr(progression.STRENGTH), 5)
            self.assertEqual(self.s.inv.carry_limit(), 40000)
            self.assertEqual(self.s.inv.total_weight(), 1840)
            self.assertFalse(any(r["type_id"] == eden.BASKET for r in self.s.inv.rows()))
            for index in range(20):
                banana = (eden.GOOD_BANANA, eden.GREEN_BANANA, eden.BAD_BANANA)[index % 3]
                for expected in (banana, eden.PALM_LEAF):
                    self.assertLessEqual(self.s.inv.total_weight() + 30000,
                                         self.s.inv.carry_limit())
                    self.reset_cycle()
                    with patch.object(harvest.RNG, "choice", return_value=expected):
                        for _ in range(3):
                            self.click()
                            self.assertIsNotNone(self.f.strike)
                            self.finish()
                    self.pickup()
                    if expected == banana:
                        # It cannot carry another 30 kg bunch yet: use the
                        # real sorter quest, then continue gathering leaves.
                        self.assertGreater(self.s.inv.total_weight() + 30000,
                                           self.s.inv.carry_limit())
                        exchange(banana)
            self.assertEqual(self.s.inv.bag_pieces().get(eden.PALM_LEAF), 20)
            self.assertFalse(any(r["type_id"] == eden.BASKET for r in self.s.inv.rows()))
            self.assertEqual({uniq: self.store.item(uniq) for uniq in ordinary}, ordinary)

    async def test_fixed_miss_boundary_does_not_progress_or_award(self):
        with patch.object(harvest.RNG, "random", return_value=0.1499):
            self.click()
            self.finish()
        self.assertEqual(self.palm.hp, 5000)
        self.assertEqual(sum(self.amounts().values()), 0)
        self.assertTrue(any(c == "caMiss" for c, _ in self.frames))
        with patch.object(harvest.RNG, "random", return_value=0.15):
            self.click()
            self.finish()
        self.assertEqual(self.palm.hp, 3300)

    async def test_other_weapons_and_bare_fist_pass_to_ordinary_combat(self):
        for weapon in (False, self.give(6240, inventory.PRIMARY),
                       self.give(25566, inventory.PRIMARY)):
            self.assertFalse(harvest.try_attack(
                self.f, None if weapon is False else weapon, self.palm, None))
            self.assertIsNone(self.f.strike)
            self.assertEqual(self.palm.hp, 5000)
        self.assertEqual(sum(self.amounts().values()), 0)

    async def test_each_draw_gives_exactly_one_of_the_four_resources(self):
        for expected in harvest.REWARDS:
            self.reset_cycle()
            before = self.amounts()
            self.prime_final_hit()
            self.click()
            with patch.object(harvest.RNG, "choice", return_value=expected):
                self.finish()
            self.assertEqual(self.amounts(), {t: before[t] + int(t == expected)
                                              for t in harvest.REWARDS})

    async def test_real_weighted_choice_delivers_four_ripe_two_leaves_and_other_bananas(self):
        # Exercise Random.choice itself and the real transaction/publication
        # path. Supply each equally likely entropy index once, instead of
        # replacing choice or relying on a noisy statistical simulation.
        rng = random.Random(1)
        indices = iter(range(8))
        draws = []
        def entropy(size):
            self.assertEqual(size, 8)
            index = next(indices)
            draws.append(index)
            return index
        with patch.object(harvest, "RNG", rng), \
             patch.object(rng, "random", return_value=0.5), \
             patch.object(rng, "randint", return_value=1700), \
             patch.object(rng, "_randbelow", side_effect=entropy):
            for _ in range(8):
                self.reset_cycle()
                for _hit in range(3):
                    self.click()
                    self.finish()
        self.assertEqual(draws, list(range(8)))
        self.assertEqual(self.amounts(), {
            eden.GOOD_BANANA: 4, eden.GREEN_BANANA: 1,
            eden.BAD_BANANA: 1, eden.PALM_LEAF: 2})
        self.assertEqual(self.resource_count(), 8)

    async def test_assignment_and_distance_rechecked_at_completion(self):
        self.click()
        self.s.pos = 0
        self.finish()
        self.assertEqual(self.palm.hp, 5000)
        self.s.pos = progression.hex_neighbours(self.palm.cell, 64, 128)[0]
        self.click()
        eden.release(self.store, self.cid)
        self.finish()
        self.assertEqual(self.palm.hp, 5000)
        self.assertEqual(sum(self.amounts().values()), 0)

    async def test_full_inventory_may_harvest_but_pickup_checks_the_actual_weight(self):
        with patch.object(self.s.inv, 'carry_limit', return_value=0):
            for _ in range(3):
                self.click()
                self.finish()
            self.assertEqual(self.resource_count(), 1)
            self.assertFalse(any(t in harvest.REWARDS for t in self.s.inv.bag_pieces()))
            self.f.open_loot(dict(target=self.palm.cell))
            self.frames.clear()
            self.f.ss_upd(dict(s_status=3))
            self.assertEqual([p['res'] for c, p in self.frames if c == 'cmdAck'],
                             [inventory.RES_OVERLOAD])
            self.assertEqual(self.resource_count(), 1)
        self.pickup()
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_BANANA), 1)
        self.assertEqual(self.s.inv.pieces_weight(eden.GREEN_BANANA, 1), 30000)

    async def test_spam_and_cancellation_do_not_replay_strikes(self):
        self.click()
        first, saved = self.f.strike, self.pending
        for _ in range(20):
            self.click()
            self.assertIs(self.f.strike, first)
            self.assertEqual(self.pending, saved)
        self.f.cancel_pending()
        self.finish(saved)
        self.assertEqual(self.palm.hp, 5000)
        self.click()
        self.finish()
        self.assertEqual(self.palm.hp, 3300)

    async def test_failed_inventory_write_rolls_back_without_reward_reroll(self):
        self.reset_cycle()
        self.prime_final_hit()
        original = harvest._create_ground
        def fail(*args):
            original(*args)
            raise RuntimeError("injected write failure")
        self.click()
        with patch.object(harvest, "_create_ground", side_effect=fail):
            self.finish()
        self.assertEqual(self.palm.hp, 1600)
        self.assertEqual(sum(self.amounts().values()), 0)
        chosen = self.palm._eden_reward
        self.click()
        with patch.object(harvest.RNG, "choice", side_effect=AssertionError("must preserve hidden result")):
            self.finish()
        self.assertEqual(self.amounts()[chosen], 1)

    async def test_failed_final_roll_keeps_hidden_reward_through_a_nonfinal_retry(self):
        with patch.object(harvest.RNG, "randint", return_value=1650):
            for _ in range(2):
                self.click()
                self.finish()
        self.assertEqual(self.palm.hp, 1700)
        original = harvest._create_ground
        def fail(*args):
            original(*args)
            raise RuntimeError("failed final hit at the damage boundary")
        self.click()
        with patch.object(harvest.RNG, "randint", return_value=1800), \
             patch.object(harvest, "_create_ground", side_effect=fail):
            self.finish()
        chosen = self.palm._eden_reward
        self.assertIsNotNone(chosen)
        self.assertEqual(self.palm.hp, 1700)
        with patch.object(harvest.RNG, "randint", return_value=1600), \
             patch.object(harvest.RNG, "choice", side_effect=AssertionError("must preserve reward")):
            self.click()
            self.finish()
            self.assertEqual(self.palm.hp, 100)
            self.assertEqual(self.resource_count(), 0)
            self.assertEqual(self.palm._eden_reward, chosen)
            self.click()
            self.finish()
        self.assertEqual(self.amounts()[chosen], 1)
        self.assertEqual(self.palm.hp, 0)
        self.assertEqual([p["dmg"] for c, p in self.frames if c == "caHit"][-1], 100)

    async def test_uncertain_commit_closes_session_and_consumes_pending_cycle(self):
        self.prime_final_hit()
        self.click()
        saved = self.pending
        with patch.object(harvest, "_create_ground", side_effect=storage.CommitError("uncertain")), \
             patch.object(self.s, "close") as close:
            self.finish()
        close.assert_called_once_with(force=True)
        self.finish(saved)
        self.assertEqual(self.palm.hp, 0)
        self.assertEqual(sum(self.amounts().values()), 0)

    async def test_tool_changed_during_strike_or_target_disappeared_cannot_progress(self):
        self.click()
        self.store.update_item(self.tool["uniq"], slot=inventory.BAG)
        self.finish()
        self.assertEqual(self.palm.hp, 5000)
        self.store.update_item(self.tool["uniq"], slot=inventory.PRIMARY)
        self.click()
        del self.rc.mobs[self.palm.eid]
        self.finish()
        self.assertEqual(self.palm.hp, 5000)
        self.assertEqual(sum(self.amounts().values()), 0)

    async def test_published_inventory_follows_commit_and_network_failure_cannot_duplicate(self):
        self.prime_final_hit()
        self.click()
        saved = self.pending
        original = self.rc.room.broadcast
        failures = []
        def fail(frame, *args, **kwargs):
            if frame[0] == "ss_loot":
                self.assertFalse(self.store.db.raw.in_transaction)
                failures.append(frame[0])
                raise OSError("lost reply")
            original(frame, *args, **kwargs)
        with patch.object(self.rc.room, "broadcast", fail):
            try:
                self.finish()
            except OSError:
                pass
        self.finish(saved)
        self.assertEqual(failures, ["ss_loot"])
        self.assertEqual(sum(self.amounts().values()), 1)
        self.assertEqual(self.palm.hp, 0)

    async def test_ground_shots_do_not_include_palms_as_damageable_bodies(self):
        weapon = NS(at_players=True)
        self.assertFalse(self.palm.stats.can_attack)
        self.assertNotIn(self.palm, self.rc.bodies(self.f, None, weapon).values())
        # Pure real shot resolution at a palm hex has no target or collateral.
        weapon = NS(num_shots=3, max_range=30, cone=0, hit_cap=1,
                    through=False, at_players=True)
        pairs, struck = self.rc.resolve(self.f, None, self.palm.cell, weapon, 3)
        self.assertEqual(struck, {})
        self.assertEqual(len(pairs), 3)
        self.assertEqual(self.palm.hp, 5000)

    async def test_adapter_leaves_ordinary_locations_and_targets_unchanged(self):
        regular = NS(is_player=False, type_id=1790)
        ordinary_location = NS(id=41)
        self.s.loc = ordinary_location
        self.assertFalse(harvest.try_attack(self.f, None, regular, None))
        # Dedicated Eden tool is refused anywhere else, without ordinary combat.
        self.assertTrue(harvest.try_attack(self.f, self.tool, regular, None))
        self.assertIsNone(self.f.strike)
        self.s.loc = self.s.room.loc
        self.assertFalse(harvest.try_attack(self.f, None, NS(type_id=1), None))

    async def test_local_palms_have_private_stats_and_no_regeneration(self):
        self.assertIsNot(self.palm.stats, mobs.stats(self.palm.type_id))
        self.palm.hp = 1
        self.rc.regen_mob(self.palm, 1000)
        self.assertEqual(self.palm.hp, 1)
        self.assertEqual(self.palm.stats.xp_pool, 0)
        self.assertFalse(self.palm.stats.can_attack or self.palm.stats.moves)


if __name__ == "__main__":
    try:
        run_cases(EdenHarvestTests)
    finally:
        server.STORE.close()
