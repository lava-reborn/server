"""Every stocked item has an exact-model image and correctly classified card."""
import copy
from pathlib import Path
import unittest
import items
import own_items
import training_balance
import training_display as display
import training_ground as training
import training_items as copies
import training_layout as layout
import training_shop as shop
import world
import test_training_ground as fixtures


class TrainingDisplay(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged

    async def test_all_stock_has_existing_icon_without_using_a_different_model(self):
        self.enter()
        seen = set()
        for post in layout.POSTS:
            for target in shop.stock(post):
                source = copies.profile_source(target)
                icon = display.icon_source(source)
                self.assertTrue((Path(world.RES) / own_items.icon_path(*items.catalogue()[icon])).is_file(), source)
                self.assertEqual(items.root_of(source), items.root_of(icon))
                if source != icon:
                    self.assertEqual(display.model(source), display.model(icon))
                seen.add(source)
        self.assertEqual(seen, set(training.item_catalogue()))
        self.unchanged()

    async def test_M60_and_its_modifications_have_M60_icons_and_machinegun_stall(self):
        self.enter()
        for line in ('A', 'P', 'G'):
            stock = [copies.copy_type(e.source) for e in training.training_supply.filtered('weapons', dict(wclass=4,line=line))]
            sources = {copies.source_type(t) for t in stock}
            found = [source for source in sources if display.model(source) == 'machine_gun_2_lvl_18']
            self.assertTrue(found, line)
            for source in found:
                self.assertIn('M60', training.item_catalogue()[source][2])
                self.assertEqual(items.params_of(copies.copy_type(source))['weapon_type'], items.MACHINEGUN)
                self.assertEqual(display.model(display.icon_source(source)), 'machine_gun_2_lvl_18')
        self.assertNotIn(copies.copy_type(40175), [copies.copy_type(e.source) for e in training.training_supply.filtered('weapons',dict(wclass=0,line='P'))])

    async def test_premium_modified_frames_use_exact_afro_variant_and_real_ammunition(self):
        self.enter()
        for source in training.item_catalogue():
            if items.root_of(source) != items.FIRE_ARM or not items.premium(source):
                continue
            if '_mod_' not in items.catalogue()[source][1] or source in items.wiki():
                continue
            reference = training_balance.afro_of(source)
            if reference is None:
                continue
            original = copy.deepcopy(items.params_of(source))
            base = items.params_of(reference)
            p = items.params_of(copies.copy_type(source))
            for field in ('fire_mods', 'fire_costs', 'fire_times', 'clip_size', 'weapon_type', 'reload_cost'):
                self.assertEqual(p[field], base[field], (source, field))
            self.assertEqual(items.params_of(source), original)
            self.assertTrue(p['comp_array'])
        self.unchanged()

    async def test_upgrade_names_disambiguate_every_known_modified_weapon(self):
        self.enter()
        for source, (category, _level, label) in training.item_catalogue().items():
            if items.root_of(source) != items.FIRE_ARM:
                continue
            upgrade = display.upgrade(source)
            if upgrade:
                self.assertIn(upgrade, label, source)
        for line in ('A', 'P', 'G'):
            self.assertTrue(training.training_supply.filtered('weapons', dict(wclass=4,line=line)))

    async def test_exit_quest_quiesces_UI_before_ack_and_public_location_load(self):
        import quests
        from protocol import decode
        from unittest.mock import patch
        ground = self.enter()
        ground.clone.cmd_q_st(dict(mob=ground.terminal_id,
            q_idx=quests.given_by(training.TERMINAL).index(training.EXIT_QUEST)))
        row = ground.store.quests(ground.clone.char_id)[0]
        self.s.writer.frames.clear()
        with patch.object(self.s, 'enter_location'):
            ground.clone.cmd_q_co(dict(mob=ground.terminal_id, q_id=row['q_id']))
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        pending = next(i for i, (name, p) in enumerate(frames) if name == 'tg' and p.get('op') == 'exit_pending')
        ack = next(i for i, (name, p) in enumerate(frames) if name == 'cmdAck' and p.get('res') == 0)
        exit_frame = next(i for i, (name, p) in enumerate(frames) if name == 'tg' and p.get('op') == 'exit')
        self.assertLess(pending, ack)
        self.assertLess(ack, exit_frame)
        self.assertFalse(self.store.training_profile(self.s.char_id)['inside'])
        self.unchanged()

    async def test_exit_checkpoint_failure_keeps_quest_retryable_without_success_ack(self):
        import quests
        from protocol import decode
        from unittest.mock import patch
        ground = self.enter()
        ground.clone.cmd_q_st(dict(mob=ground.terminal_id,
            q_idx=quests.given_by(training.TERMINAL).index(training.EXIT_QUEST)))
        row = ground.store.quests(ground.clone.char_id)[0]
        self.s.writer.frames.clear()
        with patch.object(self.store, 'save_training_profile', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                ground.clone.cmd_q_co(dict(mob=ground.terminal_id, q_id=row['q_id']))
        self.assertIsNotNone(ground.store.quest(row['q_id']))
        self.assertFalse(ground.closed)
        self.assertFalse([decode(f[:-1]) for f in self.s.writer.frames])


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingDisplay)
