"""Small isolated training sessions, lifecycle and forged-command checks."""
import asyncio
import logging
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')
logging.disable(logging.CRITICAL)

import accounts
import combat
import inventory
import items
from protocol import decode
import progression
import rooms
import server
import storage
import training_ground as tg
import world


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(data)

    def close(self):
        pass


class TrainingGround(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = accounts.Store.temporary()
        self.patch = patch.object(server, 'STORE', self.store)
        self.patch.start()
        self.flag = patch.object(tg, 'ENABLED', True)
        self.flag.start()
        aid, _ = self.store.register('training-test', 'test-only')
        cid, _ = self.store.create_character(aid, 'RangeTester', 0, '1')
        self.s = server.Session(Writer(), 'test')
        self.s.char_id = cid
        self.s.active = dict(self.store.character(cid))
        self.s.char = progression.Character.load(self.store, cid)
        self.s.char.set_skill(progression.SHOOTING, 12)
        self.s.char.save(self.store)
        self.s.loc = world.location(tg.MARKET)
        self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
        self.npc, bert = next((k, n) for k, n in self.s.room.npcs.items() if n.type_id == tg.BERT)
        self.s.pos = bert.cell
        self.real_item = self.s.inv.create(26075)
        self.before = list(self.store.db._db.iterdump())

    async def asyncTearDown(self):
        if self.s.training_ground:
            self.s.training_ground.exit(notify=False)
        self.flag.stop()
        self.patch.stop()
        self.store.close()

    def enter(self):
        tg.enter(self.s, dict(npc=self.npc))
        self.g = self.s.training_ground
        self.g.clone.cmd_lenter({})
        return self.g

    def unchanged(self):
        self.assertEqual(list(self.store.db._db.iterdump()), self.before)

    async def test_applied_clone_settings_survive_sessions_without_real_progress_changes(self):
        def real_dump():
            return [line for line in self.store.db._db.iterdump()
                    if not line.startswith('INSERT INTO "char_training_profiles"')]
        before = real_dump()
        g = self.enter()
        original = [list(row) for row in self.s.char.skill]
        g.request(dict(op='apply', token=g.token, who='player',
                       skills='0,16,4,0,0', specs=','.join(['4'] * 15), gear=''))
        g.last_request = 0
        g.request(dict(op='apply', token=g.token, who='enemy',
                       skills='0,14,2,0,0', specs=','.join(['3'] * 15), gear=''))
        self.assertEqual(real_dump(), before)
        self.assertEqual([list(row) for row in self.s.char.skill], original)
        self.assertIsNot(g.clone.char, self.s.char)
        g.exit(notify=False)
        restored = tg.Ground(self.s)
        try:
            self.assertEqual(restored.profile['skills'], [0,16,4,0,0])
            self.assertEqual(restored.opponent['skills'], [0,14,2,0,0])
            self.assertEqual(real_dump(), before)
            restored.clone.char.gain_xp(100000)
            self.assertEqual(real_dump(), before)
        finally:
            restored.exit(notify=False)

    async def test_private_map_choice_is_persistent_and_does_not_change_public_map(self):
        g = self.enter()
        self.assertEqual(g.location, 78)
        public = world.location(78)
        self.assertIsNot(g.clone.loc, public)
        self.assertFalse(g.clone.loc.spawns)
        g.request(dict(op='location', token=g.token, location=59))
        self.assertEqual(g.location, 59)
        self.assertEqual(g.clone.pos, tg.control_cell(59))
        self.assertEqual(g.room.npcs[g.terminal_id].type_id, tg.TERMINAL)
        self.assertEqual(self.store.training_profile(self.s.char_id)['location'], 59)
        g.last_request = 0
        g.clone.cmd_lenter({})
        with self.assertRaises(ValueError):
            g.request(dict(op='location', token=g.token, location=35))
        self.assertEqual(g.location, 59)
        self.assertIs(world.location(78), public)

    async def test_invalid_profile_keeps_last_saved_clone_and_real_items(self):
        g = self.enter()
        g.save_settings()
        before = self.store.training_profile(self.s.char_id)
        g.last_request = 0
        with self.assertRaises(ValueError):
            g.request(dict(op='apply', token=g.token, who='player', skills='999', specs='', gear=''))
        self.assertEqual(self.store.training_profile(self.s.char_id), before)
        self.assertIsNotNone(self.store.item(self.real_item['uniq']))

    async def test_start_uses_fresh_clone_weapon_and_rejects_real_weapon_id(self):
        g = self.enter()
        profile = tg.preset(12)
        profile['specs'][3] = 3
        ammo = items.params_of(26075)['comp_array'][0]
        profile['gear'] = {26075: 1, ammo: 40}
        g.profile = tg.validate_profile(profile)
        g.distance = 1
        g.start('mob')
        g.clone.cmd_lenter({})
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        copy_ammo = tg.training_items.copy_type(ammo)
        g.store.update_item(gun['uniq'], ammo_count=3, ammo_type=copy_ammo)
        target = '1%08x' % g.mob_eid
        self.s.writer.frames.clear()
        g.clone.handle_training('ss_use', dict(type=16, obj=inventory.oid_of(self.real_item), target=target))
        self.assertTrue(any(n == 'cmdAck' and p.get('res') == inventory.RES_NOT_FOUND
                            for n, p in [decode(f[:-1]) for f in self.s.writer.frames]))
        self.s.writer.frames.clear()
        g.clone.handle_training('ss_use', dict(type=16, obj=inventory.oid_of(gun), target=target))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(n == 'cmdAck' and p.get('res') == 0 for n, p in frames), frames)
        self.assertNotEqual(inventory.oid_of(gun), inventory.oid_of(self.real_item))
        self.unchanged()

    async def test_return_quest_uses_clone_store_and_requires_terminal(self):
        import quests
        g = self.enter()
        q = quests.get(tg.EXIT_QUEST)
        self.assertFalse(self.s.quest_available(q))
        g.clone.cmd_q_st(dict(mob=g.terminal_id, q_idx=quests.given_by(tg.TERMINAL).index(tg.EXIT_QUEST)))
        row = g.store.quests(g.clone.char_id)[0]
        self.assertEqual(row['type'], tg.EXIT_QUEST)
        self.unchanged()
        g.clone.pos = max(tg.geometry(g.location)[1])
        with self.assertRaises(ValueError):
            g.clone.cmd_q_co(dict(mob=g.terminal_id, q_id=row['q_id']))
        self.assertIsNotNone(g.store.quest(row['q_id']))
        g.clone.pos = tg.control_cell(g.location)
        with patch.object(self.s, 'enter_location') as returned:
            g.clone.cmd_q_co(dict(mob=g.terminal_id, q_id=row['q_id']))
            returned.assert_called_once_with()
        self.assertTrue(g.closed)
        self.assertIsNone(self.s.training_ground)
        self.unchanged()

    async def test_all_training_maps_have_free_central_control_cells(self):
        for location, (terminal, _label, entry) in tg.LOCATIONS.items():
            loc = world.location(location)
            self.assertNotIn(terminal, loc.obstacles)
            self.assertNotIn(entry, loc.obstacles)
            self.assertNotEqual(terminal, entry)
            self.assertTrue(progression.within_reach(entry, terminal, loc.width, loc.height))
            self.assertIn(entry, tg.geometry(location)[0])
            self.assertNotIn(entry, loc.entries)

    async def test_catalogue_filters_class_level_line_and_modification(self):
        g = self.enter()
        g.catalogue(dict(category='weapon', level=12, wclass=1, line='G', upgrade='base'))
        _, data = decode(self.s.writer.frames[-1][:-1])
        self.assertGreater(data['total'], 0)
        for t in data['ids']:
            self.assertEqual(items.params_of(t)['weapon_type'], 1)
            self.assertEqual(inventory.item_level(t), 12)
            self.assertTrue(combat.gold_item(t))
            self.assertIsNone(tg.craft.mod_of(t))
        with self.assertRaises(ValueError):
            g.catalogue(dict(category='weapon', upgrade='forged'))

    async def test_clone_refuses_saving_to_real_store_or_applying_to_real_character(self):
        g = self.enter()
        real_character = self.s.char
        with self.assertRaises(ValueError):
            g.clone.char.save(self.store)
        with self.assertRaises(ValueError):
            g.apply(self.s, tg.preset(12))
        self.assertIs(self.s.char, real_character)
        self.unchanged()
        g.clone.char.save(g.store)
        self.unchanged()

    async def test_two_characters_have_independent_clones_items_and_saved_settings(self):
        first = self.enter()
        aid, _ = self.store.register('second-training-test', 'test-only')
        cid, _ = self.store.create_character(aid, 'OtherRangeTester', 0, '1')
        owner = server.Session(Writer(), 'test')
        owner.char_id = cid
        owner.active = dict(self.store.character(cid))
        owner.char = progression.Character.load(self.store, cid)
        before = [line for line in self.store.db._db.iterdump()
                  if not line.startswith('INSERT INTO "char_training_profiles"')]
        second = tg.Ground(owner)
        try:
            self.assertIsNot(first.store, second.store)
            self.assertIsNot(first.clone.char, second.clone.char)
            self.assertIsNot(first.room, second.room)
            self.assertNotEqual(first.room.key, second.room.key)
            type_id = tg.training_items.copy_type(26075)
            a = first.clone.inv.create(type_id)
            b = second.clone.inv.create(type_id)
            self.assertNotEqual(a['uniq'], b['uniq'])
            self.assertIsNone(first.clone.inv.find(inventory.oid_of(b)))
            self.assertIsNone(second.clone.inv.find(inventory.oid_of(a)))
            with self.assertRaises(ValueError):
                second.apply(first.clone, tg.preset(7))
            with self.assertRaises(ValueError):
                first.clone.char.save(second.store)
            first.save_settings()
            saved = self.store.training_profile(self.s.char_id)
            self.assertIsNone(self.store.training_profile(cid))
            second.profile = tg.preset(7)
            second.save_settings()
            self.assertEqual(self.store.training_profile(self.s.char_id), saved)
            self.assertEqual(self.store.training_profile(cid)['player']['skills'], [7,7,7,0,0])
            after = [line for line in self.store.db._db.iterdump()
                     if not line.startswith('INSERT INTO "char_training_profiles"')]
            self.assertEqual(after, before)
        finally:
            second.exit(notify=False)

    async def test_normal_inventory_and_reload_controls_work_before_starting_fight(self):
        g = self.enter()
        profile = tg.preset(12)
        profile['specs'][3] = 3
        ammo = items.params_of(26075)['comp_array'][0]
        profile['gear'] = {26075:1, 26074:1, ammo:40}
        g.apply(g.clone, tg.validate_profile(profile))
        primary = g.clone.inv.in_slot(inventory.PRIMARY)
        secondary = g.clone.inv.in_slot(inventory.SECONDARY)
        self.assertEqual(primary['type_id'], tg.training_items.copy_type(26075))
        self.assertEqual(secondary['type_id'], tg.training_items.copy_type(26074))
        self.s.writer.frames.clear()
        g.clone.handle_training('ss_move', dict(obj=inventory.oid_of(secondary),
                                              **{'from':inventory.SECONDARY,'to':inventory.PRIMARY}))
        self.assertEqual(g.clone.inv.in_slot(inventory.PRIMARY)['uniq'], secondary['uniq'])
        stack = next(row for row in g.clone.inv.rows() if row['root'] == items.AMMO)
        g.clone.handle_training('ss_use', dict(type=1, obj=inventory.oid_of(secondary), target=inventory.oid_of(stack)))
        self.assertIsNotNone(g.clone.combat.reload_plan)
        g.clone.combat.cancel_timers()
        g.clone.handle_training('ss_heap_c', dict(obj=inventory.oid_of(stack), num=5))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        acks = [p['res'] for n,p in frames if n == 'cmdAck']
        self.assertEqual(acks, [0,0,0])
        self.assertEqual(g.phase, 'ready')
        self.unchanged()

    async def test_ready_movement_uses_the_whole_closed_map_and_invalid_route_gets_break(self):
        g = self.enter()
        target = min(tg.geometry()[1], key=lambda cell: tg.mobs.hex_distance(g.clone.pos, cell, g.clone.loc.width))
        path = tg.mobs.find_path(g.clone.loc, g.clone.pos, lambda cell: cell == target)
        self.assertTrue(path)
        self.s.writer.frames.clear()
        g.clone.handle_training('moveTo', dict(path=path))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(n == 'userMove' for n,p in frames), frames)
        g.clone.stop_walk()
        self.s.writer.frames.clear()
        g.clone.handle_training('moveTo', dict(path=[-1]))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertEqual([n for n,p in frames], ['breakMv'])
        self.unchanged()

    async def test_configured_fighter_can_approach_target_using_normal_walk(self):
        g = self.enter()
        g.start('fighter')
        g.clone.cmd_lenter({})
        g.enemy_turn()
        self.assertIsNotNone(g.enemy.walk)
        self.unchanged()

    async def test_healing_works_before_starting_fight(self):
        g = self.enter()
        heal = next(t for t in tg.item_catalogue() if items.root_of(t) == items.HEAL
                    and (items.params_of(t) or {}).get('max_h_rest', 0) > 0
                    and not items.no_combat(t) and not items.stimulant_unavailable(t))
        profile = tg.preset(12)
        profile['gear'] = {heal:1}
        g.apply(g.clone, tg.validate_profile(profile))
        row = next(r for r in g.clone.inv.rows() if r['root'] == items.HEAL)
        g.clone.char.hp = 1
        self.s.writer.frames.clear()
        g.clone.handle_training('ss_use', dict(type=inventory.USE_IDLE, obj=inventory.oid_of(row)))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(n == 'cmdAck' and p.get('res') == 0 for n,p in frames), frames)
        g.clone.combat.cancel_timers()
        self.unchanged()

    async def test_movement_during_arena_loading_receives_break_instead_of_silent_drop(self):
        g = self.enter()
        g.start('mob')
        self.s.writer.frames.clear()
        g.clone.handle_training('moveTo', dict(path=[g.clone.pos]))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertEqual([n for n,p in frames], ['breakMv'])
        self.assertEqual(g.phase, 'loading')
        self.unchanged()

    async def test_every_training_item_has_shop_or_quest_source(self):
        eligible, rewards = tg.obtainable_sources()
        self.assertLessEqual(set(tg.item_catalogue()), eligible)
        self.assertIn(26075, eligible)
        self.assertIn(7051, eligible)
        self.assertTrue(rewards)
        for t in tg.item_catalogue():
            self.assertFalse(items.acquisition_blocked(t))
            self.assertFalse(items.out_of_game(t))

    async def test_completed_bert_course_keeps_certificate_one_off(self):
        import quests
        for quest_type in [1682] + list(range(351, 358)):
            self.store.finish_quest(0, self.s.char_id, quest_type)
        self.assertTrue(self.s.quest_available(quests.get(1682)))
        self.assertTrue(self.s.quest_available(quests.get(351)))
        self.assertFalse(self.s.quest_available(quests.get(357)))
        self.assertFalse(quests.get(357).repeatable)

    async def test_enter_exit_never_mutate_real_items_or_character(self):
        g = self.enter()
        self.assertIsNot(g.store, self.store)
        self.assertIsNot(g.clone.char, self.s.char)
        self.unchanged()
        g.exit(notify=False)
        self.assertIsNone(self.s.training_ground)
        self.assertNotIn(g, tg.ACTIVE)
        self.unchanged()
        g.exit(notify=False)

    async def test_mob_fight_win_and_death_reset_without_rewards(self):
        g = self.enter()
        g.start('mob')
        g.clone.cmd_lenter({})
        mob = next(iter(g.room.combat.mobs.values()))
        g.room.combat.kill(mob, g.clone.combat)
        await asyncio.sleep(0)
        self.assertEqual(g.phase, 'ready')
        self.assertFalse(g.room.combat.mobs)
        self.assertFalse(g.clone.combat.dead)
        g.start('mob')
        g.clone.combat.die(None)
        await asyncio.sleep(0)
        self.assertEqual(g.phase, 'ready')
        self.unchanged()

    async def test_equipped_opponent_uses_same_inventory_and_combat_rules(self):
        g = self.enter()
        profile = tg.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        profile = tg.validate_profile(profile)
        g.opponent = profile
        g.start('fighter')
        g.clone.cmd_lenter({})
        enemy = g.enemy
        self.assertIsInstance(enemy.combat, tg.TrainingFighter)
        self.assertEqual(enemy.combat.ap, enemy.combat.ap_max)
        self.assertEqual(enemy.inv.in_slot(inventory.PRIMARY)['type_id'], tg.training_items.copy_type(26075))
        self.assertIs(g.clone.combat.rc.actor(enemy.pid), enemy.combat)
        g.clone.cmd_getInfo(dict(id=enemy.pid))
        g.clone.cmd_ss_get(dict(target=enemy.pid, slot=3))
        g.finish('test')
        await asyncio.sleep(0)
        g.start('fighter')
        self.assertIs(g.enemy, enemy)
        self.unchanged()

    async def test_item_ids_are_separate_and_outside_transfers_are_refused(self):
        g = self.enter()
        g.clone.inv.create(26075)
        row = g.clone.inv.rows()[0]
        self.assertGreaterEqual(row['uniq'], 1 << 40)
        for command, p in (
            ('sndml', dict(to='Other', item=inventory.oid_of(row))),
            ('ss_create', dict(s_type=inventory.SESSION_BANK, id=self.npc)),
            ('ah_create', dict(obj=inventory.oid_of(row))),
            ('q_co', dict(q_id=1)),
            ('ss_upd', dict(s_status=2, obj=inventory.oid_of(row), param=1)),
        ):
            with self.subTest(command=command):
                tg.handle(self.s, command, p)
                self.assertIsNotNone(g.store.item(row['uniq']))
                self.unchanged()

    async def test_token_remote_terminal_and_duplicate_start_are_rejected(self):
        g = self.enter()
        with self.assertRaises(ValueError):
            g.request(dict(op='exit', token='forged'))
        g.clone.pos = max(tg.geometry()[0])
        with self.assertRaises(ValueError):
            g.request(dict(op='open', token=g.token))
        self.assertIs(self.s.training_ground, g)
        g.clone.pos = tg.control_cell()
        g.start('mob')
        g.last_request = 0
        with self.assertRaises(ValueError):
            g.request(dict(op='start', token=g.token))
        self.assertEqual(len(g.room.combat.mobs), 1)

    async def test_terminal_reachable_and_arena_has_separate_movement_zone(self):
        safe, arena, start = tg.geometry()
        self.assertIn(tg.control_cell(), safe)
        self.assertNotIn(start, safe)
        self.assertTrue(safe.isdisjoint(arena))
        self.assertTrue(progression.within_reach(tg.control_cell(),
                                                tg.TERMINAL_CELL, world.location(tg.RANGE).width, world.location(tg.RANGE).height))

    async def test_temporary_store_does_not_follow_postgres_url_or_change_db_path(self):
        path = accounts.DB_PATH
        with patch.object(storage, 'DB_URL', 'postgresql://must-not-connect'), \
                patch.object(storage, 'connect', side_effect=AssertionError('real DB accessed')):
            # Constructing a temporary store must never call storage.connect.
            tmp = accounts.Store.temporary()
            try:
                self.assertIsInstance(tmp.db, storage.SqliteDB)
                self.assertEqual(accounts.DB_PATH, path)
            finally:
                tmp.close()

    async def test_dynamic_info_uses_the_real_training_row_not_virtual_mob_defaults(self):
        g = self.enter()
        row = g.clone.inv.create(26075)
        g.clone.cmd_ss_get_di(dict(obj=inventory.oid_of(row)))
        cmd, p = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual(cmd, 'ss_di_firearm')
        self.assertEqual(p['ammo_count'], 0)
        ammo = items.params_of(26075)['comp_array'][0]
        row = g.clone.inv.create(ammo, 27)
        g.clone.cmd_ss_get_di(dict(obj=inventory.oid_of(row)))
        cmd, p = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual(cmd, 'ss_di_heap')
        self.assertEqual(p['size'], 27)
        self.unchanged()

    async def test_catalogue_pages_sets_and_currency_filters(self):
        g = self.enter()
        for category in ('weapon', 'armour', 'pouch', 'set', 'ammo', 'medicine', 'mob'):
            with self.subTest(category=category):
                g.catalogue(dict(category=category, level=0, page=0, line='all'))
                cmd, data = decode(self.s.writer.frames[-1][:-1])
                self.assertEqual(cmd, 'tg')
                self.assertEqual(data['op'], 'catalogue')
                self.assertLessEqual(len(data['ids']), tg.PAGE_SIZE)
                self.assertEqual(len(data['ids']), len(data['labels']))
                if category == 'set':
                    self.assertGreater(data['total'], 0)
                    self.assertEqual(len(data['groups'][0].split(',')), 5)
        g.catalogue(dict(category='weapon', level=12, wclass=items.SHOTGUN, line='G'))
        _, data = decode(self.s.writer.frames[-1][:-1])
        self.assertTrue(data['ids'])
        self.assertTrue(all(combat.gold_item(t) for t in data['ids']))
        self.unchanged()

    async def test_real_shot_consumes_only_training_ammo_and_produces_result(self):
        g = self.enter()
        profile = tg.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        g.profile = tg.validate_profile(profile)
        g.distance = 1
        g.start('mob')
        g.clone.cmd_lenter({})
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        ammo = items.params_of(26075)['comp_array'][0]
        g.store.update_item(gun['uniq'], ammo_count=3, ammo_type=ammo)
        target = next(iter(g.room.combat.mobs.values()))
        with patch.object(combat.Fighter, 'schedule_action') as schedule:
            g.clone.combat.use_fire(dict(obj=inventory.oid_of(gun), target='1%08x' % target.eid))
            self.assertTrue(schedule.called)
            args = schedule.call_args.args
        with patch.object(combat, 'bullet_offset', return_value=0):
            args[4](*args[5:])
        self.assertGreater(g.shots, 0)
        self.assertGreater(g.damage, 0)
        self.assertLess(g.store.item(gun['uniq'])['ammo_count'], 3)
        self.assertFalse(g.store.quests(g.clone.char_id))
        self.unchanged()

    async def test_two_training_contexts_have_separate_rooms_tokens_and_item_ids(self):
        first = self.enter()
        other = server.Session(Writer(), 'other-test')
        other.char_id, other.active, other.char = self.s.char_id, self.s.active, self.s.char
        second = tg.Ground(other)
        try:
            self.assertIsNot(first.room, second.room)
            self.assertIsNot(first.store, second.store)
            self.assertNotEqual(first.token, second.token)
            a = first.clone.inv.create(26075)
            b = second.clone.inv.create(26075)
            self.assertNotEqual(a['uniq'], b['uniq'])
            first.store.delete_item(a['uniq'])
            self.assertIsNotNone(second.store.item(b['uniq']))
            self.unchanged()
        finally:
            second.exit(notify=False)

    async def test_healing_xp_is_disabled_and_pending_read_queues_receive_answers(self):
        g = self.enter()
        skills = [list(row) for row in g.clone.char.skill]
        specs = [list(row) for row in g.clone.char.spec]
        self.assertFalse(any(g.clone.char.gain_xp(progression.MEDICINE, 10000, 8).values()))
        self.assertEqual(g.clone.char.skill, skills)
        self.assertEqual(g.clone.char.spec, specs)
        for command, request, response in (
            ('q_si', dict(q_type=1682), 'q_si_'),
            ('q_di', dict(q_id=1), 'q_di_'),
            ('q_status', dict(q_type=1682), 'q_status'),
            ('ah_search', {}, 'ah_sresult'),
            ('chkml', {}, 'lsml'),
        ):
            tg.handle(self.s, command, request)
            name, _ = decode(self.s.writer.frames[-1][:-1])
            self.assertTrue(name.startswith(response), (command, name))
        self.unchanged()

    async def test_arena_is_sent_and_combat_waits_for_location_acceptance(self):
        g = self.enter()
        g.start('mob')
        self.assertEqual(g.phase, 'loading')
        self.assertNotIn(g.clone, g.room.players)
        mob = next(iter(g.room.combat.mobs.values()))
        with patch.object(mob, 'think') as think:
            g.room.combat._step()
            think.assert_not_called()
        self.s.writer.frames.clear()
        g.clone.cmd_lenter({})
        self.assertEqual(g.phase, 'fight')
        frames = [decode(raw[:-1]) for raw in self.s.writer.frames]
        self.assertTrue(any(n == 'lch' and p.get('newUser') == mob.eid for n, p in frames))
        g.finish('test')
        await asyncio.sleep(0)
        self.s.writer.frames.clear()
        g.clone.cmd_lenter({})
        frames = [decode(raw[:-1]) for raw in self.s.writer.frames]
        self.assertTrue(any(n == 'userInfo_Commoner' and p.get('tg_terminal') == 1 for n, p in frames))
        self.unchanged()

    async def test_late_training_item_requests_keep_the_native_info_queue_in_sync(self):
        g = self.enter()
        ammo = items.params_of(26075)['comp_array'][0]
        row = g.clone.inv.create(ammo, 27)
        oid = inventory.oid_of(row)
        g.exit(notify=False)
        self.s.cmd_ss_get_di(dict(obj=oid))
        cmd, p = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual(cmd, 'ss_di_heap')
        self.assertEqual(p['size'], 0)
        self.unchanged()

    async def test_invalid_profiles_are_rejected_before_replacing_equipment(self):
        for gear in ({26075: 2}, {26075: 1, 26074: 1}, {999999: 1}):
            profile = tg.preset()
            profile['gear'] = gear
            with self.subTest(gear=gear), self.assertRaises(ValueError):
                tg.validate_profile(profile)
        profile = tg.preset()
        profile['skills'] = [18] * 5
        with self.assertRaises(ValueError):
            tg.validate_profile(profile)


    async def test_candidate_templates_do_not_change_real_items_and_use_copy_ammo(self):
        g = self.enter()
        templates = tg.training_items
        source = 26075
        target = templates.copy_type(source)
        self.assertNotEqual(source, target)
        before = items.params_of(source)
        command, base = templates.static_info(target)
        changed = templates.candidate(base, {'h_damage_min': [x + 1 for x in base['h_damage_min']],
                                             'h_damage_max': [x + 1 for x in base['h_damage_max']]})
        with patch.dict(templates.FRAMES, {target: (command, changed)}):
            self.assertEqual(items.params_of(target)['h_damage_min'], changed['h_damage_min'])
            self.assertEqual(items.params_of(source), before)
            detached = items.params_of(target)
            detached['h_damage_min'][0] = 99999
            self.assertEqual(items.params_of(target)['h_damage_min'], changed['h_damage_min'])
        ammo = before['comp_array'][0]
        profile = tg.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {source: 1, ammo: 40}
        g.apply(g.clone, tg.validate_profile(profile))
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        stack = next(x for x in g.clone.inv.rows() if x['root'] == items.AMMO)
        self.assertEqual(gun['type_id'], target)
        self.assertEqual(stack['type_id'], templates.copy_type(ammo))
        self.assertIn(stack['type_id'], items.params_of(target)['comp_array'])
        with patch.object(combat.Fighter, 'schedule_action') as schedule:
            g.clone.inv.use_load(dict(obj=inventory.oid_of(gun), target=inventory.oid_of(stack)))
            self.assertTrue(schedule.called)
            args = schedule.call_args.args
        args[4](*args[5:])
        self.assertGreater(g.store.item(gun['uniq'])['ammo_count'], 0)
        with self.assertRaises(ValueError):
            self.s.inv.create(target)
        self.unchanged()

    async def test_rules_apply_to_clones_and_do_not_change_main_character(self):
        baseline = self.s.character().vitals()
        rules = tg.training_rules.Rules.parse(dict(revision='candidate', health=2, stamina=1.5, armour=2))
        base = tg.character(tg.preset(12))
        base_hp, base_sp = base.hp_max, base.sp_max
        with patch.object(tg.training_rules, 'current', return_value=rules):
            clone = tg.character(tg.preset(12))
            self.assertEqual(clone.hp_max, base_hp * 2)
            self.assertEqual(clone.sp_max, round(base_sp * 1.5))
            self.assertEqual(self.s.character().vitals(), baseline)
        for raw in ({'health': float('nan')}, {'spread': 0}, {'unknown': 2}):
            with self.assertRaises(ValueError):
                tg.training_rules.Rules.parse(raw)

    async def test_bert_quest_and_reentry_after_course_history(self):
        import quests
        self.s.send_npc_info(self.npc)
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(tg.ENTRY_QUEST in p.get('give_quests', []) for n, p in frames if n.startswith('userInfo_')))
        self.store.finish_quest(0, self.s.char_id, 1682)
        self.assertTrue(self.s.quest_available(quests.get(1682)))
        self.assertTrue(all(quests.get(t).repeatable for t in list(range(351, 357)) + list(range(358, 365))))
        self.assertFalse(quests.get(357).repeatable)
        self.assertIn(7051, tg.item_catalogue())
        g = self.enter()
        g.catalogue(dict(category='weapon', level=16, line='C'))
        _, data = decode(self.s.writer.frames[-1][:-1])
        self.assertIn(7051, data['ids'])


    async def test_entry_quest_rejects_remote_hand_in_and_enters_after_commit(self):
        import quests
        quest = quests.get(tg.ENTRY_QUEST)
        self.assertTrue(quest.repeatable)
        self.assertTrue(quest.service)
        with patch.object(tg, 'ENABLED', False):
            self.assertFalse(self.s.quest_available(quest))
        self.s.cmd_q_st(dict(mob=self.npc, q_idx=quests.given_by(tg.BERT).index(tg.ENTRY_QUEST)))
        row = next(q for q in self.store.quests(self.s.char_id) if q['type'] == tg.ENTRY_QUEST)
        npc_cell = self.s.pos
        self.s.pos = 0
        self.s.cmd_q_co(dict(mob=self.npc, q_id=row['q_id'], obj_idx=0))
        self.assertIsNotNone(self.store.quest(row['q_id']))
        self.assertIsNone(self.s.training_ground)
        self.s.pos = npc_cell
        money = self.s.character().afro, self.s.character().gold
        self.s.writer.frames.clear()
        self.s.cmd_q_co(dict(mob=self.npc, q_id=row['q_id'], obj_idx=0))
        self.assertIsNone(self.store.quest(row['q_id']))
        self.assertTrue(self.store.quest_done(self.s.char_id, tg.ENTRY_QUEST))
        self.assertIsNotNone(self.s.training_ground)
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        ack = next(i for i, (n, p) in enumerate(frames) if n == 'cmdAck' and p['res'] == 0)
        transition = next(i for i, (n, p) in enumerate(frames) if n == 'lcall')
        self.assertLess(ack, transition)
        self.assertEqual(money, (self.s.character().afro, self.s.character().gold))
        self.s.training_ground.clone.cmd_lenter({})
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        terminal = next((n, p) for n, p in frames if p.get('tg_terminal'))
        self.assertEqual(terminal[0], world.USERINFO[world.COMMONER])
        player_register = __import__('pathlib').Path(__file__).resolve().parents[1] / 'recon/as-src/lol/core/player/PlayerRegister.as'
        self.assertIn('function ' + terminal[0] + '(obj)', player_register.read_text(encoding='utf-8'))
        self.assertEqual(terminal[1]['res'], tg.TERMINAL)
        self.assertTrue(self.s.quest_available(quest))


if __name__ == '__main__':
    unittest.main()
