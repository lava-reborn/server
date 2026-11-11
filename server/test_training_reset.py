"""Confirmed private-avatar reset, persistence, rollback and shared-room isolation."""
import copy
import time
import unittest
from unittest.mock import patch

import battle_medicine
import inventory
from protocol import decode
from training import character as range_character
from training import geometry as range_geometry
from training import session as training
from training import items as training_items
from training import rules as training_rules
import test_training_ground as fixtures


class TrainingReset(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    party_members = fixtures.TrainingGround.party_members

    def equip(self, g):
        profile = range_character.preset(12)
        profile['specs'][:8] = [3] * 8
        profile['gear'] = {26075: 1}
        g.profile = range_character.validate_profile(profile, g.rules)
        g.apply(g.clone, g.profile)
        g.clone.inv.create(training_items.copy_type(26075))
        g.remember_outfit()
        g.save_settings()

    def request(self, g, op, **params):
        g.last_request = 0
        g.request(dict(op=op, token=g.token, **params))

    def prepare(self, g):
        self.request(g, 'reset_prepare')
        return g.reset_confirmation[0]

    async def test_confirmation_alone_changes_nothing_and_cannot_be_replayed(self):
        g = self.enter()
        self.equip(g)
        rows = [dict(r) for r in g.clone.inv.rows()]
        profile = copy.deepcopy(g.profile)
        nonce = self.prepare(g)
        self.assertEqual(rows, [dict(r) for r in g.clone.inv.rows()])
        self.assertEqual(profile, g.profile)
        self.request(g, 'reset_player', confirmation=nonce)
        g.clone.inv.create(training_items.copy_type(26075))
        with self.assertRaises(ValueError):
            self.request(g, 'reset_player', confirmation=nonce)
        self.assertEqual(len(g.clone.inv.rows()), 1)
        self.unchanged()

    async def test_reset_clears_equipped_and_bag_items_skills_effects_and_persists(self):
        g = self.enter()
        self.equip(g)
        g.clone.training_effects.add(3115)
        effect_timer = g.clone.training_effects.timer
        battle_medicine.start(g.store, g.clone.char_id, time.monotonic())
        rules, opponent, room = g.rules, copy.deepcopy(g.opponent), g.room
        nonce = self.prepare(g)
        self.request(g, 'reset_player', confirmation=nonce)
        self.assertEqual(g.profile, range_character.validate_profile(range_character.preset(1), rules))
        self.assertEqual(g.clone.char.level, 1)
        self.assertEqual(g.clone.inv.rows(), [])
        self.assertFalse(g.clone.training_effects.active)
        self.assertTrue(effect_timer.cancelled())
        self.assertEqual(battle_medicine.remaining_ms(g.store, g.clone.char_id, time.monotonic()), 0)
        self.assertEqual(g.clone.char.hp, g.clone.char.hp_max)
        self.assertEqual(g.clone.combat.ap, g.clone.char.ap_ceiling)
        self.assertEqual((g.rules, g.opponent, g.room), (rules, opponent, room))
        saved = self.store.training_profile(self.s.char_id)
        self.assertEqual(saved['player'], g.profile)
        g.exit(notify=False)
        reopened = training.Ground(self.s)
        try:
            self.assertEqual(reopened.profile, g.profile)
            self.assertEqual(reopened.clone.inv.rows(), [])
        finally:
            reopened.store.close()
        self.unchanged()

    async def test_reset_keeps_selected_simulator_rules(self):
        g = self.enter()
        g.rules = training_rules.Rules(simulator_formulas=True, ammo_modifiers=True)
        self.equip(g)
        nonce = self.prepare(g)
        self.request(g, 'reset_player', confirmation=nonce)
        self.assertTrue(g.rules.simulator_formulas)
        self.assertIs(g.clone.char.training_rules, g.rules)
        self.unchanged()

    async def test_missing_expired_or_another_session_confirmation_refused(self):
        g = self.enter()
        self.equip(g)
        rows = [dict(r) for r in g.clone.inv.rows()]
        for confirmation in ('', 'forged'):
            with self.assertRaises(ValueError):
                self.request(g, 'reset_player', confirmation=confirmation)
        nonce = self.prepare(g)
        g.reset_confirmation = (nonce, time.monotonic() - 1)
        with self.assertRaises(ValueError):
            self.request(g, 'reset_player', confirmation=nonce)
        self.assertEqual(rows, [dict(r) for r in g.clone.inv.rows()])
        self.unchanged()

    async def test_revalidates_distance_context_combat_and_pending_action(self):
        g = self.enter()
        self.equip(g)
        pos = g.clone.pos
        nonce = self.prepare(g)
        for attr, value in (('context', 'player'), ('phase', 'fight')):
            old = getattr(g, attr)
            setattr(g, attr, value)
            with self.assertRaises(ValueError):
                self.request(g, 'reset_player', confirmation=nonce)
            setattr(g, attr, old)
        g.clone.pos = 0
        with self.assertRaises(ValueError):
            self.request(g, 'reset_player', confirmation=nonce)
        g.clone.pos = pos
        with patch.object(g.clone.combat, 'aim', object()):
            with self.assertRaises(ValueError):
                self.request(g, 'reset_player', confirmation=nonce)
        self.assertTrue(g.clone.inv.rows())
        self.unchanged()

    async def test_persistent_write_failure_keeps_items_character_effects_and_profile(self):
        g = self.enter()
        self.equip(g)
        g.clone.training_effects.add(3115)
        original = g.clone.char
        rows = [dict(r) for r in g.clone.inv.rows()]
        profile = self.store.training_profile(self.s.char_id)
        nonce = self.prepare(g)
        frames = len(self.s.writer.frames)
        with patch.object(self.store, 'save_training_profile', side_effect=RuntimeError('write failed')):
            with self.assertRaises(ValueError):
                self.request(g, 'reset_player', confirmation=nonce)
        self.assertEqual(rows, [dict(r) for r in g.clone.inv.rows()])
        self.assertIs(g.clone.char, original)
        self.assertTrue(g.clone.training_effects.active)
        self.assertEqual(profile, self.store.training_profile(self.s.char_id))
        self.assertEqual(len(self.s.writer.frames), frames)
        self.unchanged()

    async def test_shared_peer_and_its_equipment_stay_unchanged(self):
        members, _, _ = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for g in (first, second):
            g.clone.cmd_lenter({})
            self.equip(g)
        first.clone.pos = range_geometry.control_cell(first.location)
        peer_rows = [dict(r) for r in second.clone.inv.rows()]
        peer_profile = copy.deepcopy(second.profile)
        members[1].writer.frames.clear()
        nonce = self.prepare(first)
        with self.assertRaises(ValueError):
            self.request(second, 'reset_player', confirmation=nonce)
        self.request(first, 'reset_player', confirmation=nonce)
        self.assertEqual(peer_rows, [dict(r) for r in second.clone.inv.rows()])
        self.assertEqual(peer_profile, second.profile)
        frames = [decode(frame[:-1]) for frame in members[1].writer.frames]
        self.assertTrue(any(cmd == 'ss_obj_move' and p['id'] == first.clone.pid
                            and p['to'] == inventory.PRIMARY for cmd, p in frames))
        self.unchanged()

    async def test_private_write_failure_rolls_back_without_publishing_reset(self):
        g = self.enter()
        self.equip(g)
        rows = [dict(r) for r in g.clone.inv.rows()]
        profile = self.store.training_profile(self.s.char_id)
        original = g.clone.char
        nonce = self.prepare(g)
        frames = len(self.s.writer.frames)
        execute = g.store.db.execute
        def fail_after_delete(sql, *args):
            result = execute(sql, *args)
            if sql.startswith('DELETE FROM items WHERE char_id='):
                raise RuntimeError('private write failed')
            return result
        with patch.object(g.store.db, 'execute', side_effect=fail_after_delete):
            with self.assertRaises(ValueError):
                self.request(g, 'reset_player', confirmation=nonce)
        self.assertEqual(rows, [dict(r) for r in g.clone.inv.rows()])
        self.assertIs(g.clone.char, original)
        self.assertEqual(profile, self.store.training_profile(self.s.char_id))
        self.assertEqual(len(self.s.writer.frames), frames)
        self.unchanged()
