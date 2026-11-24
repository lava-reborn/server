"""Archived ordinary STR/AP buffs: native caps, real doses and persisted expiry."""
import unittest
from unittest.mock import patch

import effects
import inventory
import items
import names
import progression as p
import shop_bands
import test_gold_commerce as trade_fixtures
import test_training_ground as fixtures
from training import character as range_character
from test_release_combat import TimedItems
from testkit import run_cases
from protocol import decode


class ArchivedBuffs(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    manager = TimedItems.manager

    async def test_alpha_changes_only_crit_and_omega_only_anticrit_in_real_fights(self):
        manager = self.manager()
        f = self.s.combat
        self.s.char.rep = 0
        self.s.char.skill[p.SHOOTING][0] = 20
        self.s.char.skill[p.MELEE][0] = 10
        baseline = p.crit_chance(self.s.char, items.PISTOL, card=False)
        # A/G of every ordinary rank; values are the archived reagent bonuses.
        for alpha, omega, cp, ce in ((4181, 3208, 5, 10), (3115, 3209, 10, 20),
                                    (3116, 3210, 15, 20), (3117, 3211, 20, 30),
                                    (3118, 3212, 25, 30), (3119, 3213, 30, 40),
                                    (4182, 4184, 30, 40), (4183, 4185, 60, 75)):
            with self.subTest(alpha=alpha, omega=omega):
                for tid, expected in ((alpha, (cp, 0)), (omega, (0, ce))):
                    value = effects.definition(tid)
                    self.assertEqual((value['bonuses']['cp'], value['bonuses']['ce']), expected)
                    self.s.writer.frames.clear()
                    self.assertTrue(manager.static(effects.FIRST + tid))
                    packet = next(data for cmd, data in
                                  (decode(frame[:-1]) for frame in self.s.writer.frames) if cmd == 'e_si')
                    self.assertEqual((packet['critical_probability'], packet['critical_evade']), expected)
                    row = self.s.inv.create(tid)
                    effects.activate(f, row['uniq'], f, 0)
                    self.assertIsNone(self.store.item(row['uniq']))
                    actual = p.crit_chance(self.s.char, items.PISTOL, card=False)
                    self.assertEqual(actual, (baseline[0] + cp,
                                             baseline[1] + (ce if tid == omega else 0)))
                    self.assertEqual(f.crit_evade_ranged(), actual[1])
                self.assertEqual(len(manager.active), 2)
                manager.close()
                manager.load()
                self.assertEqual(p.crit_chance(self.s.char, items.PISTOL, card=False),
                                 (baseline[0] + cp, baseline[1] + ce))
                deadline = max(active.deadline for active in manager.active.values())
                with patch.object(manager, 'clock', return_value=deadline + 1):
                    manager.refresh()
                self.assertFalse(manager.active)
                self.assertEqual(p.crit_chance(self.s.char, items.PISTOL, card=False), baseline)
                self.assertEqual(f.crit_evade_ranged(), baseline[1])

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
        self.assertIn(3474, items.stock_for(1196, 36))
        self.assertIn(3475, items.stock_for(1196, 188))
        self.assertIn(3476, items.stock_for(1013, 609))
        self.assertIn(3897, items.stock_for(1013, 1443))

    async def test_strength_is_consumed_once_persists_and_expires_without_changing_base(self):
        manager = self.manager()
        f = self.s.combat
        before = (self.s.char.attrib[:], self.s.char.hp, self.s.char.sp)
        self.s.char.skill[p.SHOOTING][0] = 20
        self.s.char.skill[p.MELEE][0] = 10
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


    async def test_level_is_rechecked_before_consumption_and_qualification_uses_base_level(self):
        manager = self.manager()
        fighter = self.s.combat
        for skill in self.s.char.skill:
            skill[0] = 0
        self.s.char.skill[p.MELEE][0] = 13
        self.s.char.rep = -100
        row = self.s.inv.create(3203)
        fighter.ap = fighter.ap_max
        before_ap = fighter.ap
        effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertFalse(manager.active)
        self.assertEqual(fighter.ap, before_ap)
        self.s.char.skill[p.MELEE][0] = 14
        effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(fighter.ap, before_ap - 1)
        self.assertIn('experience_down', manager.active)


class GofusStock(unittest.TestCase):
    def test_nubian_doctor_has_lowest_gold_pair_and_keeps_starter_afro_at_assistant(self):
        import rooms
        import server
        import world
        from test_quest_state import session

        room = rooms.Rooms(world.mob_types()).get(185)
        doctor = next(eid for eid, npc in room.npcs.items() if npc.type_id == 5215)
        self.assertFalse(any(npc.type_id == 1013 for npc in room.npcs.values()))
        self.assertEqual(items.stock_for(5215, 185), [4919, 4939])
        self.assertEqual(items.stock_for(5216, 185), [4917, 4937])
        viewer = session(None, level=1)
        viewer.frames = []
        viewer.send = lambda cmd, **params: viewer.frames.append((cmd, params))
        viewer.room, viewer.loc = room, room.loc
        viewer.combat = type('Presentation', (), dict(mob_info=lambda *_: {}, after_npc_info=lambda *_: None))()
        viewer.fee_shown, viewer.skill_shown = {}, {}
        with patch.object(server, 'STORE', None):
            viewer.send_npc_info(doctor)
        frame = next(params for cmd, params in viewer.frames if cmd == 'userInfo_Trader')
        self.assertEqual((frame['can_trade'], frame['type_list']), (1, [4919, 4939]))
        self.assertTrue(frame['give_quests'])  # Original doctor's quests remain.
        for tid, bonus in ((4919, ('hp', 75)), (4939, ('sp', 150))):
            params = items.params_of(tid)
            self.assertEqual((params['cost'], params['g_cost'], params['buff_level']), (0, 8, 0))
            definition = effects.definition(tid)
            self.assertEqual((definition['duration'], definition['bonuses'][bonus[0]]), (1200, bonus[1]))

    def test_each_city_offers_its_ranks_scanner_and_ap_at_the_doctor(self):
        for loc, booster, strength, scanner, salus in (
                (36, 3112, 3474, 3789, {1, 2, 3}),
                (188, 3113, 3475, 3789, {3, 4, 5}),
                (197, 3114, 3476, 3826, {5, 6, 7}),
                (127, 3561, 3476, 3826, {7, 8, 9})):
            with self.subTest(location=loc):
                stock = items.stock_for(1013, loc) + items.stock_for(1196, loc)
                self.assertEqual(len(stock), len(set(stock)))
                self.assertEqual(set(stock) & {3112, 3113, 3114, 3561}, {booster})
                self.assertEqual(set(stock) & {3474, 3475, 3476}, {strength})
                self.assertEqual(set(stock) & {3789, 3826}, {scanner})
                self.assertIn(3897, stock)
                ranks = {int(items.catalogue()[t][1].split('_')[2]) for t in stock
                         if items.catalogue()[t][1].startswith('Salus_MK_')}
                self.assertEqual(ranks, salus)
                self.assertFalse(set(stock) & {6294, 6295, 6296, 3449, 3450, 3451, 7647, 7648})
                for type_id in stock:
                    si = items.params_of(type_id)
                    self.assertTrue(effects.definition(type_id))
                    self.assertTrue(si['cost'] or si['g_cost'])
                    self.assertTrue(names.known(si['name']))

    def test_helpers_do_not_repeat_the_doctors_goods_in_the_same_room(self):
        for loc, junior in ((36, 2015), (188, 2016), (197, 2017), (127, 2018)):
            doctor = set(items.stock_for(1013, loc))
            for helper in (1196, junior):
                with self.subTest(location=loc, helper=helper):
                    self.assertFalse(doctor.intersection(items.stock_for(helper, loc)))

    def test_both_assistants_sell_afro_and_doctor_sells_gold_with_safe_fallback(self):
        for loc, senior in ((36, 2015), (188, 2016), (197, 2017), (127, 2018)):
            doctor = items.stock_for(1013, loc)
            self.assertTrue(doctor)
            self.assertTrue(all(items.params_of(t)['g_cost'] for t in doctor))
            for helper in (1196, senior):
                stock = [t for t in items.stock_for(helper, loc) if effects.definition(t)]
                self.assertTrue(stock)
                self.assertTrue(all(items.params_of(t)['cost'] and not items.params_of(t)['g_cost'] for t in stock))
        for loc in (609, 1443):
            stock = [t for t in items.stock_for(1013, loc) if effects.definition(t)]
            self.assertTrue(any(items.params_of(t)['cost'] for t in stock))
            self.assertTrue(any(items.params_of(t)['g_cost'] for t in stock))
        for trader, loc in ((1206, 102), (202, 76), (714, 609), (5240, 1443)):
            self.assertFalse(any(effects.definition(t) for t in items.stock_for(trader, loc)))

    def test_afro_buffs_use_strict_character_level_and_gold_has_no_requirement(self):
        for tid in effects.definitions():
            params = items.params_of(tid)
            for field in ('need_attribs', 'need_skills', 'need_specs', 'bonus_attribs', 'bonus_skills', 'bonus_specs'):
                self.assertTrue(all(params.get(field, ())), (tid, field))
                self.assertEqual(int(params.get(field + '_m', 0)).bit_count(), len(params.get(field, ())))
            self.assertEqual(params.get('need_pvp_rep', 0), 0)
            self.assertEqual((params['need_skills_m'], params['need_skills']), (0, []))
            ch = p.Character()
            ch.rep = -100
            fighter = type('BuffUser', (), {'character': lambda self: ch})()
            for skill in ch.skill:
                skill[0] = 0
            if params.get('cost') and not params.get('g_cost'):
                required = params['buff_level']
                self.assertTrue(2 <= required <= 17)
                # A melee character qualifies with no shooting or PvP skill.
                ch.skill[p.MELEE][0] = required
                self.assertIsNone(effects.use_error(fighter, fighter, tid))
                ch.skill[p.MELEE][0] = required - 1
                ch.bonus_skills = [100] * p.SKILLS
                self.assertIn('уровень персонажа', effects.use_error(fighter, fighter, tid))
                ch.skill[p.MELEE][0] = 0
                ch.skill[p.INDUSTRY][0] = required
                self.assertIsNone(effects.use_error(fighter, fighter, tid))
            else:
                self.assertEqual(params['buff_level'], 0)
                self.assertIsNone(effects.use_error(fighter, fighter, tid))

    def test_picodin_keeps_agreed_six_ten_fourteen_character_levels(self):
        self.assertEqual([items.params_of(t)['buff_level'] for t in (3201, 3202, 3203)], [6, 10, 14])
        self.assertEqual([items.params_of(t)['buff_level'] for t in (3205, 3206, 3207)], [0, 0, 0])

    def test_outside_city_and_without_location_keep_the_archive_list(self):
        for trader in (1013, 1196, 2018):
            self.assertEqual(items.stock_for(trader, 58), items.stock_for(trader))
        self.assertNotIn(3561, items.stock_for(1013, 58))


class GofusTrade(unittest.TestCase):
    setUp = trade_fixtures.GoldCommerce.setUp

    def test_actual_purchase_index_charges_catalogue_currency_once_in_each_city(self):
        import world
        for trader, loc in ((5215, 185), (1013, 36), (1013, 188), (1013, 197), (1013, 127)):
            self.s.loc.id = loc
            self.inv.trade = inventory.TradeSession(1, trader, loc)
            self.s.room.npc = lambda n: (0, trader, world.TRADER) if n == 1 else None
            for index, type_id in enumerate(items.stock_for(trader, loc)):
                with self.subTest(location=loc, item=type_id):
                    self.store.set_money(self.cid, 5000000, 100000)
                    self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
                    before = self.store.money(self.cid)
                    si = items.params_of(type_id)
                    gold = bool(si['g_cost'])
                    self.frames.clear()
                    self.inv.buy(dict(obj=format(index, 'x'), param=1),
                                 inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
                    self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
                    after = self.store.money(self.cid)
                    self.assertEqual(before[int(gold)] - after[int(gold)],
                                     si['g_cost'] if gold else si['cost'])
                    self.assertEqual(before[int(not gold)], after[int(not gold)])
                    rows = self.inv.rows()
                    self.assertEqual([row['type_id'] for row in rows], [type_id])
                    self.store.delete_item(rows[0]['uniq'])


if __name__ == '__main__':
    run_cases(ArchivedBuffs, GofusStock, GofusTrade)
