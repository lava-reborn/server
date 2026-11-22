"""Archived ordinary STR/AP buffs: native caps, real doses and persisted expiry."""
import unittest
from unittest.mock import patch

import effects
import items
import progression as p
import shop_bands
import test_training_ground as fixtures
from training import character as range_character
from test_release_combat import TimedItems
from testkit import run_cases
from protocol import decode


class ArchivedBuffs(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    manager = TimedItems.manager

    def test_catalogue_preserves_archived_prices_doses_and_explicit_effects(self):
        for tid, cost, gold, duration, strength, od in (
                (3474, 500, 0, 3600, 1, 0), (3475, 2500, 0, 3600, 3, 0),
                (3476, 0, 50, 3600, 5, 0), (3897, 0, 10, 7200, 0, 40)):
            with self.subTest(item=tid):
                si = items.params_of(tid)
                self.assertEqual((si['cost'], si['g_cost'], si['weight'], si['use_count']),
                                 (cost, gold, 10, 1))
                self.assertEqual([si[k] for k in ('min_h_rest', 'max_h_rest', 'min_st_rest', 'max_st_rest')], [0] * 4)
                value = effects.definition(tid)
                self.assertEqual((value['duration'], value['bonuses']['attribs'][0], value['bonuses']['od']),
                                 (duration, strength, od))
                self.assertEqual(si['effects'], [effects.FIRST + tid])
                self.assertFalse(items.stimulant_unavailable(tid))
        # The archive does not identify any effects/numbers for these long or
        # 100/150-OD variants. Do not silently invent stronger retail articles.
        for tid in (3830, 7647, 7648):
            self.assertIsNone(effects.definition(tid))

    def test_city_ladder_has_matching_str_rank_and_ap_without_event_variants(self):
        for top, strength in ((4, None), (8, 3474), (12, 3475), (16, 3476), (20, 3476)):
            stock = shop_bands.stimulants(top)
            self.assertEqual(set(stock) & {3474, 3475, 3476}, {strength} if strength else set())
            self.assertEqual(3897 in stock, top >= 8)
            self.assertFalse(set(stock) & {3449, 3450, 3451, 3830, 7647, 7648})
        self.assertIn(3474, items.stock_for(1206, 102))
        self.assertIn(3475, items.stock_for(202, 76))
        self.assertIn(3476, items.stock_for(714, 609))
        self.assertIn(3897, items.stock_for(5240, 958))

    async def test_strength_is_consumed_once_persists_and_expires_without_changing_base(self):
        manager = self.manager()
        f = self.s.combat
        before = (self.s.char.attrib[:], self.s.char.hp, self.s.char.sp)
        base = self.s.char.attr(p.STRENGTH)
        limits = (self.s.char.hp_max, self.s.char.max_weight())
        row = self.s.inv.create(3476)
        effects.activate(f, row['uniq'], f, 0)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(self.s.char.attr(p.STRENGTH), base + 5)
        self.assertEqual((self.s.char.hp_max, self.s.char.max_weight()), (limits[0] + 20, limits[1] + 10000))
        self.assertEqual(self.s.char.attrib, before[0])
        self.assertEqual((self.s.char.hp, self.s.char.sp), before[1:])
        deadline = manager.active['Репарин'].deadline
        effects.activate(f, row['uniq'], f, 0)
        self.assertEqual(manager.active['Репарин'].deadline, deadline)
        weaker = self.s.inv.create(3474)
        effects.activate(f, weaker['uniq'], f, 0)
        self.assertIsNotNone(self.store.item(weaker['uniq']))
        manager.close()
        manager.load()
        self.assertEqual(self.s.char.attr(p.STRENGTH), base + 5)
        self.assertEqual(manager.active['Репарин'].deadline, deadline)
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
        self.assertEqual(self.s.char.attr(p.STRENGTH), base)
        self.assertEqual((self.s.char.hp_max, self.s.char.max_weight()), limits)
        self.assertEqual(self.s.char.attrib, before[0])

    async def test_ap_dose_repeat_relog_expiry_never_refills_or_restarts_regeneration(self):
        manager = self.manager()
        f = self.s.combat
        f.amax_sent = self.s.char.ap_ceiling
        original_max = f.ap_max
        f.ap = 23
        row = self.s.inv.create(3897)
        self.s.writer.frames.clear()
        effects.activate(f, row['uniq'], f, 6)
        packets = [decode(frame[:-1]) for frame in self.s.writer.frames]
        ceiling = [value for name, value in packets if name == 'c_ap' and 'amax' in value]
        self.assertEqual(ceiling, [dict(ap=17, amax=original_max + 40)])
        self.assertEqual((f.ap_max, f.ap, self.s.char.ap_ceiling), (original_max + 40, 17, original_max + 40))
        self.assertIsNone(self.store.item(row['uniq']))
        deadline = manager.active['action_points'].deadline
        other = self.s.inv.create(3897)
        effects.activate(f, other['uniq'], f, 6)
        self.assertEqual((f.ap_max, f.ap), (original_max + 40, 11))
        self.assertEqual(len(manager.active), 1)
        manager.close()
        manager.load()
        self.assertEqual((f.ap_max, f.ap), (original_max + 40, 11))
        f.ap = f.ap_max
        deadline = manager.active['action_points'].deadline
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
        self.assertEqual((f.ap_max, f.ap, self.s.char.ap_ceiling), (original_max, original_max, original_max))
        self.assertFalse(manager.active)

    async def test_ap_effect_adjusts_only_own_bonus_and_keeps_frozen_gear_policy(self):
        manager = self.manager()
        f = self.s.combat
        base = self.s.char.ap_ceiling
        f.amax_sent = base + 12  # A previous room-entry ceiling retained after a gear change.
        f.ap = 19
        manager.add(3897)
        self.assertEqual((f.ap_max, f.ap), (base + 52, 19))
        deadline = manager.active['action_points'].deadline
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
        self.assertEqual((f.ap_max, f.ap), (base + 12, 19))

    def assert_ceiling_before_private_state(self, maximum):
        packets = [decode(frame[:-1]) for frame in self.s.writer.frames]
        caps = [(i, value) for i, (name, value) in enumerate(packets)
                if name == 'c_ap' and 'amax' in value]
        self.assertEqual([value for _, value in caps], [dict(ap=maximum, amax=maximum)])
        state = next(i for i, (name, value) in enumerate(packets)
                     if name == 'tg' and value.get('op') == 'state')
        self.assertLess(caps[0][0], state)

    async def test_training_reset_removes_ap_buff_and_sends_fresh_ceiling_before_state(self):
        g = fixtures.TrainingGround.enter(self)
        g.clone.training_effects.add(3897)
        g.clone.combat.ap = 17
        g.last_request = 0
        g.request(dict(op='reset_prepare', token=g.token))
        nonce = g.reset_confirmation[0]
        self.s.writer.frames.clear()
        g.last_request = 0
        g.request(dict(op='reset_player', token=g.token, confirmation=nonce))
        self.assertFalse(g.clone.training_effects.active)
        self.assertEqual(g.clone.char.level, 1)
        self.assertEqual((g.clone.combat.ap, g.clone.combat.ap_max), (55, 55))
        self.assert_ceiling_before_private_state(55)
        self.assertFalse(self.store.effects_for(self.s.char_id))

    async def test_training_trainer_apply_keeps_ap_buff_but_resynchronizes_new_level_ceiling(self):
        g = fixtures.TrainingGround.enter(self)
        g.clone.training_effects.add(3897)
        npc = g.post_ids['player']
        g.clone.pos = g.room.npcs[npc].cell
        g.open_post(npc)
        profile = range_character.preset(10)
        self.s.writer.frames.clear()
        g.last_request = 0
        g.request(dict(op='apply', token=g.token, who='player',
                       skills=','.join(map(str, profile['skills'])),
                       specs=','.join(map(str, profile['specs'])), gear=''))
        self.assertEqual(g.clone.char.level, 10)
        self.assertEqual(g.clone.training_effects.bonus['od'], 40)
        self.assertEqual((g.clone.combat.ap, g.clone.combat.ap_max), (140, 140))
        self.assert_ceiling_before_private_state(140)
        self.assertFalse(self.store.effects_for(self.s.char_id))

    async def test_ap_private_clone_has_effect_without_touching_real_account(self):
        g = fixtures.TrainingGround.enter(self)
        clone = g.clone
        f = clone.combat
        manager = clone.training_effects
        initial = f.ap_max
        f.ap = 17
        before = self.store.effects_for(self.s.char_id)
        manager.add(3897)
        self.assertEqual((f.ap_max, f.ap), (initial + 40, 17))
        self.assertEqual(self.store.effects_for(self.s.char_id), before)
        deadline = manager.active['action_points'].deadline
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
        self.assertEqual((f.ap_max, f.ap), (initial, 17))
        manager.add(3897)
        manager.close(notify=True)
        self.assertEqual((f.ap_max, f.ap), (initial, 17))


if __name__ == '__main__':
    run_cases(ArchivedBuffs)
