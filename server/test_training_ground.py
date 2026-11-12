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
from training import arena as range_arena
from training import catalog as range_catalog
from training import character as range_character
from training import commands as range_commands
from training import geometry as range_geometry
from training import items as range_items
from training import layout as range_layout
from training import opponents as range_opponents
from training import party as range_party
from training import rules as range_rules
from training import runtime as range_runtime
from training import settings as range_settings
from training import shop as range_shop
from training import supply as range_supply
import craft
import mobs
import movement
import sets
from training import session as tg
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
        self.flag = patch.object(tg.settings, 'ENABLED', True)
        self.flag.start()
        self.environment = patch.dict(os.environ, LAVA_TRAINING_GROUND='1')
        self.environment.start()
        aid, _ = self.store.register('training-test', 'test-only')
        cid, _ = self.store.create_character(aid, 'RangeTester', 0, '1')
        self.s = server.Session(Writer(), 'test')
        self.s.training_protocol = 1
        self.s.char_id = cid
        self.s.active = dict(self.store.character(cid))
        self.s.char = progression.Character.load(self.store, cid)
        self.s.char.set_skill(progression.SHOOTING, 12)
        self.s.char.save(self.store)
        self.s.loc = world.location(range_settings.MARKET)
        self.s.room = rooms.Room(self.s.loc, rooms.IdAllocator(), world.mob_types())
        self.npc, bert = next((k, n) for k, n in self.s.room.npcs.items() if n.type_id == range_settings.BERT)
        self.s.pos = bert.cell
        self.real_item = self.s.inv.create(26075)
        self.before = list(self.store.db._db.iterdump())

    async def asyncTearDown(self):
        # Close every shared visitor before closing their common real store.
        for ground in tuple(range_runtime.ACTIVE):
            if ground.owner.inv.store is self.store:
                ground.exit(notify=False)
        if self.s.training_ground:
            self.s.training_ground.exit(notify=False)
        self.flag.stop()
        self.environment.stop()
        self.patch.stop()
        self.store.close()

    def enter(self):
        tg.enter(self.s, dict(npc=self.npc))
        self.g = self.s.training_ground
        self.g.clone.cmd_lenter({})
        return self.g

    async def test_clan_roster_reads_owner_and_mutations_stay_blocked(self):
        import clans
        from types import SimpleNamespace
        clan = self.store.clan_create(self.s.char_id, 'Range clan', 'rangeclan', '', None)
        aid, _ = self.store.register('other-clan-member', 'test-only')
        cid, _ = self.store.create_character(aid, 'ClanPeer', 0, '1')
        self.store.clan_member_add(cid, clan, clans.R_CHAT, '')
        manager = clans.Clans(self.store, SimpleNamespace(by_char={self.s.char_id:self.s}))
        with patch.object(server, 'CLANS', manager):
            g = self.enter()
            self.s.writer.frames.clear()
            g.clone.handle_training('gg_info', dict(det=1))
            packets = [decode(f[:-1]) for f in self.s.writer.frames]
            roster = next(p for name,p in packets if name=='gg_list' and p['res']==1)
            self.assertEqual(set(roster['data']), {self.s.char_id,cid})
            self.assertEqual(g.store.clan_roster(clan), [])
            self.assertFalse(self.s.training_clan_read)
            self.s.writer.frames.clear()
            self.s.training_clan_read = True
            self.s.send('userInfo_Player', id=0, gold=99999)
            self.s.send('ss_ack', o_list=[])
            self.s.training_clan_read = False
            self.assertEqual(self.s.writer.frames, [])
            with patch.object(self.s,'cmd_gg_info',side_effect=ValueError('read failed')):
                with self.assertRaises(ValueError):
                    g.clone.handle_training('gg_info',dict(det=1))
            self.assertFalse(self.s.training_clan_read)
            before = list(self.store.db._db.iterdump())
            for cmd,params in [('apply',dict(action=0)), ('admit',dict()),
                               ('head',dict()), ('gg_info',dict(det=3)), ('gg_info',dict(det=4))]:
                self.s.writer.frames.clear()
                g.clone.handle_training(cmd,params)
                self.assertNotIn('gg_list',[decode(f[:-1])[0] for f in self.s.writer.frames])
            self.assertEqual(list(self.store.db._db.iterdump()),before)
            self.s.writer.frames.clear()
            with patch.object(self.s,'enter_location'), patch.object(range_party,'refresh'):
                g.exit()
            packets = [decode(f[:-1]) for f in self.s.writer.frames]
            roster = next(p for name,p in packets if name=='gg_list' and p['res']==1)
            self.assertEqual(set(roster['data']),{self.s.char_id,cid})
            self.assertEqual(len(self.store.clan_roster(clan)),2)

    def unchanged(self):
        # Only the linked sandbox preset may persist; real items, skills,
        # currencies and quest progress must stay byte-for-byte unchanged.
        # Saving real progress can reorder SQLite rows without changing values.
        relevant = lambda rows: sorted(row for row in rows
                                      if not row.startswith('INSERT INTO "char_training_profiles"'))
        self.assertEqual(relevant(self.store.db._db.iterdump()), relevant(self.before))

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
        self.assertEqual(g.location, 108)
        public = world.location(108)
        self.assertIsNot(g.clone.loc, public)
        self.assertFalse(g.clone.loc.spawns)
        g.request(dict(op='location', token=g.token, location=59))
        self.assertEqual(g.location, 59)
        self.assertEqual(g.clone.pos, range_geometry.control_cell(59))
        self.assertEqual(g.room.npcs[g.terminal_id].type_id, range_settings.TERMINAL)
        self.assertEqual(self.store.training_profile(self.s.char_id)['location'], 59)
        g.last_request = 0
        g.clone.cmd_lenter({})
        with self.assertRaises(ValueError):
            g.request(dict(op='location', token=g.token, location=35))
        self.assertEqual(g.location, 59)
        self.assertIs(world.location(108), public)

    async def test_three_spawn_points_are_free_reachable_and_ordered(self):
        for location in range_settings.LOCATIONS:
            loc = range_geometry.arena_location(location)
            safe, arena, start = range_geometry.geometry(location)
            terminal = range_settings.LOCATIONS[location][0]
            self.assertEqual(terminal % loc.width, loc.width // 2)
            self.assertEqual(terminal // loc.width, next(p.y for p in range_layout.posts_for(location) if p.key == 'computer'))
            self.assertIn(range_geometry.control_cell(location), safe)
            self.assertEqual(start % loc.width, loc.width // 2)
            self.assertGreater(start // loc.width, loc.height // 2)
            distances = []
            for cell in range_settings.ENEMY_SPAWNS[location]:
                self.assertIn(cell, arena)
                if location == range_settings.RANGE:
                    self.assertIsNone(combat.shot_wall(loc, start, cell))
                distances.append(mobs.hex_distance(range_geometry.control_cell(location), cell, loc.width))
            self.assertEqual(len(set(distances)), 3)
            self.assertEqual(distances, sorted(distances))
            near = range_settings.ENEMY_SPAWNS[location][range_settings.DEFAULT_SPAWN]
            self.assertGreater(near % loc.width, terminal % loc.width)
            self.assertLess(near // loc.width, terminal // loc.width)
            far = range_settings.ENEMY_SPAWNS[location][-1]
            if location == range_settings.RANGE:
                self.assertGreaterEqual(far % loc.width, 3 * loc.width // 4)
                self.assertLess(far // loc.width, loc.height // 4)

    async def test_halfa_arena_keeps_real_art_geometry_and_is_private(self):
        import copy
        original = world.location(59)
        before = copy.deepcopy(vars(original))
        g = self.enter()
        self.s.writer.frames.clear()
        g.change_location(59)
        loc = g.room.loc
        self.assertEqual((loc.width,loc.height),(64,128))
        self.assertEqual(loc.obstacles,original.obstacles)
        self.assertIsNot(loc.obstacles,original.obstacles)
        self.assertEqual(loc.entries,[])
        self.assertEqual(loc.spawns,[])
        self.assertEqual(vars(original),before)
        frames=[decode(frame[:-1]) for frame in self.s.writer.frames]
        map_index=next(i for i,(cmd,p) in enumerate(frames) if cmd=='tg' and p.get('op')=='map')
        call_index=next(i for i,(cmd,p) in enumerate(frames) if cmd=='lcall')
        self.assertLess(map_index,call_index)
        self.assertEqual(frames[map_index][1]['native_map'],1)
        reachable={range_geometry.control_cell(59)}
        queue=list(reachable)
        for cell in queue:
            for n in progression.hex_neighbours(cell,loc.width,loc.height):
                if n not in reachable and n not in loc.obstacles:
                    reachable.add(n);queue.append(n)
        for cell in range_settings.ENEMY_SPAWNS[59]:
            self.assertIn(cell,reachable)
        for npc in g.room.npcs.values():
            self.assertIn(npc.cell,reachable)
        g.clone.cmd_lenter({})
        for mode in ('mob','fighter'):
            g.start(mode)
            g.finish('Проверка арены',force=True)
            await asyncio.sleep(0)
            self.assertEqual(g.phase,'ready')
        g.change_location(range_settings.RANGE)
        self.assertEqual(vars(original),before)
        self.unchanged()

    async def test_old_second_desert_migrates_to_halfa_without_losing_profile(self):
        g=self.enter();g.save_settings()
        saved=self.store.training_profile(self.s.char_id)
        saved['location']=106
        self.store.save_training_profile(self.s.char_id,saved)
        restored=tg.Ground(self.s)
        try:
            self.assertEqual(restored.location,59)
            self.assertEqual(restored.profile,g.profile)
        finally:
            restored.exit(notify=False)

    async def test_selected_spawn_is_saved_validated_and_used_in_both_fight_modes(self):
        g = self.enter()
        self.assertEqual(g.spawn_point, range_settings.DEFAULT_SPAWN)
        for point in range(3):
            g.last_request = 0
            g.request(dict(op='spawn', token=g.token, spawn_point=point))
            self.assertEqual(self.store.training_profile(self.s.char_id)['spawn_point'], point)
            _, state = decode(self.s.writer.frames[-1][:-1])
            self.assertEqual(state['spawn_point'], point)
            self.assertEqual(len(state['spawn_labels']), 3)
            for mode in ('mob', 'fighter'):
                g.start(mode)
                self.assertEqual(g.clone.pos, range_geometry.control_cell(g.location))
                enemy_cell = g.enemy.pos if mode == 'fighter' else g.room.combat.mobs[g.mob_eid].cell
                self.assertEqual(enemy_cell, range_settings.ENEMY_SPAWNS[g.location][point])
                g.reset('Проверка')
                g.clone.cmd_lenter({})
        saved = self.store.training_profile(self.s.char_id)
        for point in (-1, 3, 'bad', True):
            g.last_request = 0
            with self.assertRaises(ValueError):
                g.request(dict(op='spawn', token=g.token, spawn_point=point))
            self.assertEqual(self.store.training_profile(self.s.char_id), saved)
        g.exit(notify=False)
        restored = tg.Ground(self.s)
        try:
            self.assertEqual(restored.spawn_point, 2)
        finally:
            restored.exit(notify=False)

    async def test_saved_arena_profile_migrates_without_losing_presets(self):
        g = self.enter()
        g.save_settings()
        saved = self.store.training_profile(self.s.char_id)
        g.exit(notify=False)
        for legacy in range_settings.LEGACY_LOCATIONS:
            saved['location'] = legacy
            saved.pop('spawn_point', None)
            saved['distance'] = 12
            self.store.save_training_profile(self.s.char_id, saved)
            restored = tg.Ground(self.s)
            try:
                self.assertEqual(restored.location, range_settings.RANGE)
                self.assertEqual(restored.profile, g.profile)
                self.assertEqual(restored.opponent, g.opponent)
                self.assertEqual(restored.spawn_point, range_settings.DEFAULT_SPAWN)
            finally:
                restored.exit(notify=False)

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
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        ammo = items.params_of(26075)['comp_array'][0]
        profile['gear'] = {26075: 1, ammo: 40}
        g.profile = range_character.validate_profile(profile)
        g.spawn_point = 0
        g.start('mob')
        g.clone.cmd_lenter({})
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        copy_ammo = range_items.copy_type(ammo)
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
        q = quests.get(range_settings.EXIT_QUEST)
        self.assertFalse(self.s.quest_available(q))
        with self.assertRaises(ValueError):
            g.clone.cmd_q_st(dict(mob=g.terminal_id, q_idx=0))
        # An already issued legacy row remains safely finishable.
        g.store.take_quest(g.clone.char_id, range_settings.EXIT_QUEST, {'obj': 1}, True)
        row = g.store.quests(g.clone.char_id)[0]
        self.assertEqual(row['type'], range_settings.EXIT_QUEST)
        self.unchanged()
        g.clone.pos = max(range_geometry.geometry(g.location)[1])
        with self.assertRaises(ValueError):
            g.clone.cmd_q_co(dict(mob=g.terminal_id, q_id=row['q_id']))
        self.assertIsNotNone(g.store.quest(row['q_id']))
        g.clone.pos = range_geometry.control_cell(g.location)
        with patch.object(self.s, 'enter_location') as returned:
            g.clone.cmd_q_co(dict(mob=g.terminal_id, q_id=row['q_id']))
            returned.assert_called_once_with()
        self.assertTrue(g.closed)
        self.assertIsNone(self.s.training_ground)
        self.unchanged()

    async def test_all_desert_maps_have_free_bottom_left_control_cells(self):
        for location, (terminal, _label, entry) in range_settings.LOCATIONS.items():
            loc = range_geometry.arena_location(location)
            self.assertNotIn(terminal, loc.obstacles)
            self.assertNotIn(entry, loc.obstacles)
            self.assertNotEqual(terminal, entry)
            self.assertTrue(progression.within_reach(entry, terminal, loc.width, loc.height))
            self.assertIn(entry, range_geometry.geometry(location)[0])
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
            self.assertIsNone(craft.mod_of(t))
        with self.assertRaises(ValueError):
            g.catalogue(dict(category='weapon', upgrade='forged'))

    async def test_clone_refuses_saving_to_real_store_or_applying_to_real_character(self):
        g = self.enter()
        real_character = self.s.char
        with self.assertRaises(ValueError):
            g.clone.char.save(self.store)
        with self.assertRaises(ValueError):
            g.apply(self.s, range_character.preset(12))
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
            type_id = range_items.copy_type(26075)
            a = first.clone.inv.create(type_id)
            b = second.clone.inv.create(type_id)
            self.assertNotEqual(a['uniq'], b['uniq'])
            self.assertIsNone(first.clone.inv.find(inventory.oid_of(b)))
            self.assertIsNone(second.clone.inv.find(inventory.oid_of(a)))
            with self.assertRaises(ValueError):
                second.apply(first.clone, range_character.preset(7))
            with self.assertRaises(ValueError):
                first.clone.char.save(second.store)
            first.save_settings()
            saved = self.store.training_profile(self.s.char_id)
            self.assertIsNone(self.store.training_profile(cid))
            second.profile = range_character.preset(7)
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
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        ammo = items.params_of(26075)['comp_array'][0]
        profile['gear'] = {26075:1, 26074:1, ammo:40}
        g.apply(g.clone, range_character.validate_profile(profile))
        primary = g.clone.inv.in_slot(inventory.PRIMARY)
        secondary = g.clone.inv.in_slot(inventory.SECONDARY)
        self.assertEqual(primary['type_id'], range_items.copy_type(26075))
        self.assertEqual(secondary['type_id'], range_items.copy_type(26074))
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
        target = min(range_geometry.geometry()[1], key=lambda cell: mobs.hex_distance(g.clone.pos, cell, g.clone.loc.width))
        path = mobs.find_path(g.clone.loc, g.clone.pos, lambda cell: cell == target)
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
        heal = next(t for t in range_catalog.item_catalogue() if items.root_of(t) == items.HEAL
                    and (items.params_of(t) or {}).get('max_h_rest', 0) > 0
                    and not items.no_combat(t) and not items.stimulant_unavailable(t))
        profile = range_character.preset(12)
        profile['gear'] = {heal:1}
        g.apply(g.clone, range_character.validate_profile(profile))
        row = next(r for r in g.clone.inv.rows() if r['root'] == items.HEAL)
        g.clone.char.hp = 1
        self.s.writer.frames.clear()
        g.clone.handle_training('ss_use', dict(type=inventory.USE_IDLE, obj=inventory.oid_of(row)))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(n == 'cmdAck' and p.get('res') == 0 for n,p in frames), frames)
        g.clone.combat.cancel_timers()
        self.unchanged()

    async def test_movement_is_available_immediately_after_spawning_target(self):
        g = self.enter()
        g.start('mob')
        self.s.writer.frames.clear()
        g.clone.handle_training('moveTo', dict(path=[g.clone.pos]))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(n == 'cmdAck' and p.get('res') == 0 for n,p in frames))
        self.assertFalse(any(n == 'lcall' for n,p in frames))
        self.assertEqual(g.phase, 'fight')
        self.unchanged()

    async def test_every_training_item_has_shop_or_quest_source(self):
        # Initialise the same metadata as server startup, even when this single
        # scenario runs first. Other tests must not register its prototypes.
        tg.preload()
        catalogue = range_catalog.item_catalogue()
        prototypes = range_items.prototype_rows()
        eligible, rewards = range_catalog.obtainable_sources()
        extra = set(catalogue) - eligible
        self.assertTrue(extra)
        self.assertTrue(all(t in items.catalogue() or t in prototypes for t in extra))
        self.assertTrue(any(inventory.item_level(t) == 20 for t in extra))
        self.assertIn(26075, eligible)
        self.assertIn(7051, eligible)
        self.assertTrue(rewards)
        for t, row in catalogue.items():
            with self.subTest(type_id=t):
                if t in prototypes:
                    definition = prototypes[t]
                    self.assertNotIn(t, items.catalogue())
                    self.assertIn(definition['base'], items.catalogue())
                    self.assertEqual(range_items.PROTOTYPES[t], definition)
                    self.assertEqual(range_items.source_type(t), definition['base'])
                    self.assertEqual(row[1], definition['level'])
                    self.assertLessEqual(row[1], range_settings.MAX_LEVEL)
                    self.assertTrue(items.acquisition_blocked(t))
                    with self.assertRaises(ValueError):
                        self.s.inv.create(t)
                elif items.acquisition_blocked(t):
                    self.assertGreater(row[1], 17)
                    self.assertLessEqual(inventory.item_level(t), 20)
                self.assertFalse(items.retired(t))
        self.unchanged()

    async def test_completed_bert_course_keeps_certificate_one_off(self):
        import quests
        for quest_type in [1682] + list(range(351, 358)):
            self.store.finish_quest(0, self.s.char_id, quest_type)
        for quest_type in [1682] + list(range(351, 358)):
            self.assertFalse(self.s.quest_available(quests.get(quest_type)))
            self.assertFalse(quests.get(quest_type).repeatable)
        self.assertTrue(self.s.quest_available(quests.get(range_settings.ENTRY_QUEST)))

    async def test_enter_exit_never_mutate_real_items_or_character(self):
        g = self.enter()
        self.assertIsNot(g.store, self.store)
        self.assertIsNot(g.clone.char, self.s.char)
        self.unchanged()
        g.exit(notify=False)
        self.assertIsNone(self.s.training_ground)
        self.assertNotIn(g, range_runtime.ACTIVE)
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

    async def test_killing_target_does_not_reload_teleport_heal_or_replace_items(self):
        g = self.enter()
        profile=range_character.preset(12)
        profile['specs'][3]=3
        profile['gear']={26075:1}
        g.profile=range_character.validate_profile(profile)
        g.start('mob')
        gun=g.clone.inv.in_slot(inventory.PRIMARY)
        ammo=items.params_of(gun['type_id'])['comp_array'][0]
        g.store.update_item(gun['uniq'],ammo_count=2,ammo_type=ammo)
        g.clone.pos=6162
        g.clone.char.hp=80
        before=[dict(row) for row in g.clone.inv.rows()]
        self.s.writer.frames.clear()
        mob=next(iter(g.room.combat.mobs.values()))
        with patch.object(combat.RoomCombat,'materialize_loot') as loot:
            g.room.combat.kill(mob,g.clone.combat)
            loot.assert_not_called()
        self.assertEqual(g.phase,'ready')
        self.assertEqual(g.clone.pos,6162)
        self.assertEqual(g.clone.char.hp,80)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()],before)
        self.assertFalse(g.room.combat.loot)
        frames=[decode(f[:-1]) for f in self.s.writer.frames]
        self.assertFalse(any(n in ('lcall','lenter') for n,p in frames))
        self.assertTrue(any(n=='lch' and p.get('dead')==mob.eid for n,p in frames))
        g.start('mob')
        self.assertEqual(g.clone.pos,6162)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()],before)
        self.unchanged()

    async def test_return_stops_motion_without_reload_or_equipment_loss(self):
        g = self.enter()
        before = [dict(row) for row in g.clone.inv.rows()]
        target = 6162
        path = mobs.find_path(g.clone.loc, g.clone.pos, lambda cell: cell == target)
        self.assertGreater(len(path), 1)
        g.clone.move_in_location(dict(path=path))
        self.assertIsNotNone(g.clone.walk)
        self.s.writer.frames.clear()
        g.reset('Возврат к компьютеру')
        self.assertIsNone(g.clone.walk)
        self.assertNotIn(id(g.clone), movement.get(g.room).walks)
        self.assertEqual(g.clone.pos, range_geometry.control_cell(g.location))
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        self.assertFalse(any(command == 'lcall' for command, _ in frames))
        self.unchanged()

    async def test_training_medicine_and_modified_weapon_keep_source_classification(self):
        g = self.enter()
        for source in range_catalog.item_catalogue():
            target = range_items.copy_type(source)
            if items.root_of(source) == items.HEAL:
                self.assertEqual(items.battle_medicine(source), items.battle_medicine(target))
                self.assertEqual(items.no_combat(source), items.no_combat(target))
            if items.root_of(source) in (items.FIRE_ARM, items.COLD_ARM):
                for level in (4, 12, 17):
                    self.assertEqual(inventory.weapon_durability_ratio(source, level),
                                     inventory.weapon_durability_ratio(target, level))
        self.unchanged()

    async def test_next_target_cancels_previous_corpse_cleanup(self):
        g = self.enter()
        g.start('mob')
        target = g.room.combat.mobs[g.mob_eid]
        g.target_defeated(target)
        timer = g.corpse_timer
        self.assertIsNotNone(timer)
        g.start('mob')
        self.assertTrue(timer.cancelled())
        self.assertIsNone(g.corpse_id)
        self.assertIn(g.mob_eid, g.room.combat.mobs)
        self.unchanged()

    async def test_posts_use_distinct_resources_and_preloaded_names_on_free_cells(self):
        from training import layout as layout
        import names
        g=self.enter()
        expected = [p for p in layout.POSTS if not p.line or range_shop.stock(p)]
        self.assertEqual(len(g.posts), len(expected))
        self.assertTrue(all(p.resource == 1006 for p in expected if p.category in ('ammo','pouch','armour','medicine','buff','event_medicine')))
        self.assertEqual(len(expected), 9)
        self.assertEqual(len({p.cell(g.clone.loc.width) for p in expected}), len(expected))
        for location in range_settings.LOCATIONS:
            loc=range_geometry.arena_location(location)
            for post in layout.posts_for(location):
                self.assertNotIn(post.cell(loc.width),loc.obstacles)
                self.assertIn(post.resource,world.mob_types())
                self.assertIn(layout.NAME_IDS[post.key],names.ALL)
        for eid,post in g.posts.items():
            g.clone.send_npc_info(eid)
            cmd,data=decode(self.s.writer.frames[-1][:-1])
            self.assertEqual(cmd, 'userInfo_Commoner')
            self.assertEqual(data['tg_station'],post.key)
            self.assertEqual(data['can_trade'], 0)
            self.assertNotIn('type_list', data)
            self.assertEqual(data['tg_terminal'], 1)
        self.unchanged()

    def approach_shop(self, ground, key='weapons'):
        eid = ground.post_ids[key]
        npc = ground.room.npc(eid)
        occupied = {entry.cell for entry in ground.room.npcs.values()}
        cell = next(cell for cell in progression.hex_neighbours(
            npc.cell, ground.clone.loc.width, ground.clone.loc.height)
            if cell not in ground.clone.loc.obstacles and cell not in occupied)
        ground.clone.pos = cell
        ground.open_post(eid)
        return eid

    def supply(self, ground, source, count=1, returning=False):
        ground.last_request = 0
        ground.request(dict(op='supply_return' if returning else 'supply_get', token=ground.token,
                            source=source, count=count, sequence=ground.supply_sequence + 1))

    async def test_shops_require_proximity_and_only_offer_their_line_and_class(self):
        g = self.enter()
        with self.assertRaises(ValueError):
            g.open_post(g.post_ids['weapons'])
        eid = self.approach_shop(g)
        self.assertEqual(g.context, 'weapons')
        rows = range_supply.filtered('weapons', dict(wclass=1, line='A'))
        self.assertTrue(rows)
        self.assertTrue(all(row.weapon_class == 1 and row.line == 'A' for row in rows))
        g.clone.handle_training('ss_create', dict(s_type=1, target=eid))
        self.assertIsNone(g.clone.inv.trade)
        self.unchanged()

    async def test_computer_can_list_fighter_sets_and_weapon_categories(self):
        g = self.enter()
        g.request(dict(op='open', token=g.token))
        g.request(dict(op='catalogue', token=g.token, category='set', line='G', level=12))
        _, data = decode(self.s.writer.frames[-1][:-1])
        self.assertTrue(data['ids'])
        self.assertTrue(all(sets.SETS[t]['level'] == 12 for t in data['ids']))
        self.unchanged()

    async def test_free_shop_purchase_sale_partial_sale_and_close_never_change_money(self):
        g = self.enter()
        self.approach_shop(g, 'supplies')
        source = next(t for t in range_supply.sources('supplies') if items.root_of(t) == items.AMMO)
        purse = (g.clone.char.afro, g.clone.char.gold)
        self.supply(g, source, 17)
        row = next(row for row in g.clone.inv.rows() if row['root'] == items.AMMO)
        self.assertEqual(row['count'], 17)
        self.supply(g, inventory.oid_of(row), 7, returning=True)
        self.assertEqual(g.store.item(row['uniq'])['count'], 10)
        self.supply(g, inventory.oid_of(row), 10, returning=True)
        self.assertIsNone(g.store.item(row['uniq']))
        self.assertEqual((g.clone.char.afro, g.clone.char.gold), purse)
        self.unchanged()

    async def test_free_shop_multiple_items_are_atomic_and_private(self):
        g = self.enter()
        self.approach_shop(g, 'medical')
        source = next(t for t in range_supply.sources('medical') if items.root_of(t) == items.HEAL)
        before = [dict(row) for row in g.clone.inv.rows()]
        create = g.clone.inv.create
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError('test write failure')
            return create(*args, **kwargs)
        with patch.object(g.clone.inv, 'create', side_effect=fail_second):
            with self.assertRaises(ValueError):
                self.supply(g, source, 3)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.assertEqual(g.supply_sequence, 0)
        self.supply(g, source, 3)
        fresh = [row for row in g.clone.inv.rows() if row['uniq'] not in {r['uniq'] for r in before}]
        self.assertEqual(len(fresh), 3)
        self.assertTrue(all(range_items.is_copy(row['type_id']) for row in fresh))
        self.unchanged()

    async def test_shop_rejects_forged_currency_quantity_source_and_distant_requests(self):
        g = self.enter()
        self.approach_shop(g)
        source = next(iter(range_supply.sources('weapons')))
        before = [dict(row) for row in g.clone.inv.rows()]
        for bad_source, count in ((source, 0), (source, 2), (source, 'nan'), (-1, 1), (65535, 1)):
            with self.assertRaises((ValueError, TypeError)):
                self.supply(g, bad_source, count)
            self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        with self.assertRaises(ValueError):
            self.supply(g, inventory.oid_of(self.real_item), returning=True)
        g.clone.pos = range_geometry.control_cell()
        with self.assertRaises(ValueError):
            self.supply(g, source)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.unchanged()

    async def test_shop_respects_weight_and_separate_object_limit(self):
        g = self.enter()
        self.approach_shop(g)
        source = next(iter(range_supply.sources('weapons')))
        before = [dict(row) for row in g.clone.inv.rows()]
        with patch.object(g.clone.inv, 'carry_limit', return_value=0):
            with self.assertRaises(ValueError):
                self.supply(g, source)
        with patch.object(g.clone.inv, 'rows', return_value=[{}] * range_shop.MAX_ROWS):
            with self.assertRaises(ValueError):
                self.supply(g, source)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.unchanged()

    async def test_all_catalogue_items_are_copies_in_exactly_one_supply_service(self):
        g = self.enter()
        seen = []
        for post in g.posts.values():
            if not post.line:
                continue
            stock = range_shop.stock(post)
            self.assertTrue(stock)
            seen.extend(range_items.profile_source(t) for t in stock)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(range_catalog.item_catalogue()))
        for type_id in (26061, 26062, 26063, 26070, 26071, 7051):
            self.assertIn(type_id, seen)
        self.unchanged()

    async def test_skill_changes_keep_shop_items_and_next_fight_does_not_replace_them(self):
        g = self.enter()
        self.approach_shop(g, 'medical')
        source = next(iter(range_supply.sources('medical')))
        self.supply(g, source, 2)
        before = [dict(row) for row in g.clone.inv.rows()]
        profile = dict(skills=[12, 12, 4, 0, 0], specs=[-1] * progression.SPECS, gear={})
        g.configure_player(profile)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        g.start('mob')
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.assertIsNone(g.clone.inv.trade)
        self.unchanged()

    async def test_fighter_equipment_gets_compatible_training_ammo(self):
        g = self.enter()
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        g.request(dict(op='apply', token=g.token, who='enemy', skills='12,12,0,0,0',
                       specs=','.join(str(n) for n in profile['specs']), gear='26075:1'))
        self.assertIn(26075, g.opponent['gear'])
        ammo = [t for t in g.opponent['gear'] if items.root_of(t) == items.AMMO]
        self.assertEqual(len(ammo), 1)
        self.assertIn(ammo[0], items.params_of(26075)['comp_array'])
        g.start('fighter')
        self.assertTrue(any(row['root'] == items.AMMO for row in g.enemy.inv.rows()))
        self.unchanged()

    async def test_mob_groups_cover_catalogue_and_private_scaling_does_not_modify_source(self):
        from training import layout as layout
        g=self.enter()
        seen=set()
        for group in layout.MOB_GROUPS:
            if group=='all':
                continue
            ids=[t for t in range_catalog.mob_catalogue() if range_opponents.RECORDS[t]['group']==group]
            seen.update(ids)
            g.catalogue(dict(category='mob',group=group))
            _,data=decode(self.s.writer.frames[-1][:-1])
            self.assertTrue(set(data['ids'])<=set(ids))
        self.assertEqual(seen,set(range_catalog.mob_catalogue()))
        original=mobs.stats(g.mob_type)
        hp,damage=original.hp_max,original.dmg_min
        g.mob_health,g.mob_damage=200,150
        g.start('mob')
        spawned=g.room.combat.mobs[g.mob_eid]
        self.assertIsNot(spawned.stats,original)
        self.assertEqual(spawned.hp,hp*2)
        self.assertEqual(spawned.stats.dmg_min,round(damage*1.5))
        self.assertEqual(original.hp_max,hp)
        self.assertEqual(original.dmg_min,damage)
        self.unchanged()

    async def test_equipped_opponent_uses_same_inventory_and_combat_rules(self):
        g = self.enter()
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        profile = range_character.validate_profile(profile)
        g.opponent = profile
        g.start('fighter')
        g.clone.cmd_lenter({})
        enemy = g.enemy
        self.assertIsInstance(enemy.combat, range_arena.TrainingFighter)
        self.assertEqual(enemy.combat.ap, enemy.combat.ap_max)
        self.assertEqual(enemy.inv.in_slot(inventory.PRIMARY)['type_id'], range_items.copy_type(26075))
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
        g.clone.inv.create(range_items.copy_type(26075))
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
                range_commands.handle(self.s, command, p)
                self.assertIsNotNone(g.store.item(row['uniq']))
                self.unchanged()

    async def test_token_remote_terminal_and_duplicate_start_are_rejected(self):
        g = self.enter()
        with self.assertRaises(ValueError):
            g.request(dict(op='exit', token='forged'))
        g.clone.pos = max(range_geometry.geometry()[0])
        with self.assertRaises(ValueError):
            g.request(dict(op='open', token=g.token))
        self.assertIs(self.s.training_ground, g)
        g.clone.pos = range_geometry.control_cell()
        g.start('mob')
        g.last_request = 0
        with self.assertRaises(ValueError):
            g.request(dict(op='start', token=g.token))
        self.assertEqual(len(g.room.combat.mobs), 1)

    async def test_terminal_reachable_and_arena_has_separate_movement_zone(self):
        safe, arena, start = range_geometry.geometry()
        self.assertIn(range_geometry.control_cell(), safe)
        self.assertNotIn(start, safe)
        self.assertTrue(safe.isdisjoint(arena))
        self.assertTrue(progression.within_reach(range_geometry.control_cell(),
                                                range_settings.TERMINAL_CELL, range_settings.ARENA_WIDTH, range_settings.ARENA_HEIGHT))

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
        row = g.clone.inv.create(range_items.copy_type(26075))
        g.clone.cmd_ss_get_di(dict(obj=inventory.oid_of(row)))
        cmd, p = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual(cmd, 'ss_di_firearm')
        self.assertEqual(p['ammo_count'], 0)
        ammo = items.params_of(26075)['comp_array'][0]
        row = g.clone.inv.create(range_items.copy_type(ammo), 27)
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
                self.assertLessEqual(len(data['ids']), range_settings.PAGE_SIZE)
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
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        g.profile = range_character.validate_profile(profile)
        g.spawn_point = 0
        g.start('mob')
        g.clone.cmd_lenter({})
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        ammo = items.params_of(26075)['comp_array'][0]
        g.store.update_item(gun['uniq'], ammo_count=3, ammo_type=range_items.copy_type(ammo))
        target = next(iter(g.room.combat.mobs.values()))
        target.cell = next(cell for cell in progression.hex_neighbours(g.clone.pos, g.clone.loc.width, g.clone.loc.height) if cell not in {npc.cell for npc in g.room.npcs.values()})
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
            a = first.clone.inv.create(range_items.copy_type(26075))
            b = second.clone.inv.create(range_items.copy_type(26075))
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
            range_commands.handle(self.s, command, request)
            name, _ = decode(self.s.writer.frames[-1][:-1])
            self.assertTrue(name.startswith(response), (command, name))
        self.unchanged()

    async def test_target_spawns_on_the_loaded_map_and_aggros_from_far_corner(self):
        g = self.enter()
        self.s.writer.frames.clear()
        g.spawn_point = 2
        g.start('mob')
        self.assertEqual(g.phase, 'fight')
        self.assertIn(g.clone, g.room.players)
        mob = next(iter(g.room.combat.mobs.values()))
        self.assertIs(mob.target, g.clone.combat)
        self.assertGreaterEqual(mob.stats.aggro, 100)
        self.assertGreater(mobs.hex_distance(mob.cell,g.clone.pos,g.clone.loc.width),50)
        frames = [decode(raw[:-1]) for raw in self.s.writer.frames]
        self.assertFalse(any(n in ('lcall','lenter') for n,p in frames))
        self.assertTrue(any(n == 'lch' and p.get('newUser') == mob.eid for n,p in frames))
        with patch.object(mob,'think') as think:
            g.room.combat._step()
            think.assert_called_once()
        g.finish('test')
        await asyncio.sleep(0)
        self.assertIn(g.terminal_id,g.room.npcs)
        self.unchanged()

    async def test_late_training_item_requests_keep_the_native_info_queue_in_sync(self):
        g = self.enter()
        ammo = items.params_of(26075)['comp_array'][0]
        row = g.clone.inv.create(range_items.copy_type(ammo), 27)
        oid = inventory.oid_of(row)
        g.exit(notify=False)
        self.s.cmd_ss_get_di(dict(obj=oid))
        cmd, p = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual(cmd, 'ss_di_heap')
        self.assertEqual(p['size'], 0)
        self.unchanged()

    async def test_invalid_profiles_are_rejected_before_replacing_equipment(self):
        for gear in ({26075: 2}, {26075: 1, 26074: 1}, {999999: 1}):
            profile = range_character.preset()
            profile['gear'] = gear
            with self.subTest(gear=gear), self.assertRaises(ValueError):
                range_character.validate_profile(profile)
        profile = range_character.preset()
        profile['skills'] = [21] * 5
        with self.assertRaises(ValueError):
            range_character.validate_profile(profile)


    async def test_candidate_templates_do_not_change_real_items_and_use_copy_ammo(self):
        g = self.enter()
        templates = range_items
        source = 26075
        target = templates.copy_type(source)
        self.assertNotEqual(source, target)
        before = items.params_of(source)
        command, base = templates.static_info(target)
        changed = templates.candidate(base, {'h_damage_min': [x + 1 for x in base['h_damage_min']],
                                             'h_damage_max': [x + 1 for x in base['h_damage_max']]})
        with patch.dict(templates.FRAMES, {target: (command, changed)}):
            self.assertEqual(items.params_of(target)['h_damage_min'], base['h_damage_min'])
            self.assertEqual(items.params_of(source), before)
            detached = items.params_of(target)
            detached['h_damage_min'][0] = 99999
            self.assertEqual(items.params_of(target)['h_damage_min'], base['h_damage_min'])
        ammo = before['comp_array'][0]
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {source: 1, ammo: 40}
        g.apply(g.clone, range_character.validate_profile(profile))
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
        rules = range_rules.Rules.parse(dict(revision='candidate', health=2, stamina=1.5, armour=2))
        base = range_character.character(range_character.preset(12))
        base_hp, base_sp = base.hp_max, base.sp_max
        with patch.object(range_rules, 'current', return_value=rules):
            clone = range_character.character(range_character.preset(12))
            self.assertEqual(clone.hp_max, base_hp * 2)
            self.assertEqual(clone.sp_max, round(base_sp * 1.5))
            self.assertEqual(self.s.character().vitals(), baseline)
        for raw in ({'health': float('nan')}, {'spread': 0}, {'unknown': 2}):
            with self.assertRaises(ValueError):
                range_rules.Rules.parse(raw)

    async def test_session_rules_are_private_saved_and_leave_real_progress_untouched(self):
        first = self.enter()
        other = server.Session(Writer(), 'other-rules-test')
        other.char_id, other.active, other.char = self.s.char_id, self.s.active, self.s.char
        second = tg.Ground(other)
        ordinary = self.s.character().vitals()
        base_hp = first.clone.char.hp_max
        db_before = [line for line in self.store.db._db.iterdump()
                     if not line.startswith('INSERT INTO "char_training_profiles"')]
        values = '1,1,1,1,1,2,1.5,2,0.5,25,1,0,0'
        try:
            first.request(dict(op='rules', token=first.token, values=values))
            self.assertEqual(first.clone.char.hp_max, base_hp * 2)
            self.assertEqual(first.clone.char.training_rules, first.rules)
            self.assertNotEqual(second.rules, first.rules)
            self.assertEqual(second.clone.char.hp_max, base_hp)
            self.assertFalse(range_rules.current().combat_v2)
            self.assertEqual(self.s.character().vitals(), ordinary)
            self.assertEqual(db_before, [line for line in self.store.db._db.iterdump()
                                        if not line.startswith('INSERT INTO "char_training_profiles"')])
            _, data = decode(self.s.writer.frames[-1][:-1])
            self.assertEqual(data['rule_values'], values)
            first.exit(notify=False)
            restored = tg.Ground(self.s)
            try:
                self.assertEqual(restored.rules.values(), values)
                self.assertEqual(restored.clone.char.hp_max, base_hp * 2)
            finally:
                restored.exit(notify=False)
        finally:
            second.exit(notify=False)

    async def test_invalid_or_midfight_rules_do_not_change_session(self):
        g = self.enter()
        g.save_settings()
        before = self.store.training_profile(self.s.char_id)
        for values in ('', 'nan,1,1,1,1,1,1,1,1,0,0,1',
                       '1,1,1,1,1,1,1,1,1,0,2,1', '1' * 257):
            g.last_request = 0
            with self.assertRaises(ValueError):
                g.request(dict(op='rules', token=g.token, values=values))
            self.assertEqual(self.store.training_profile(self.s.char_id), before)
        g.start('mob')
        g.last_request = 0
        with self.assertRaises(ValueError):
            g.request(dict(op='rules', token=g.token, values='1,1,1,1,1,2,1,1,1,0,1,0'))
        self.assertEqual(self.store.training_profile(self.s.char_id), before)

    async def test_experimental_armour_scales_full_gear_and_handles_broken_parts(self):
        from dataclasses import replace
        g = self.enter()
        armour = next(t for t, (cat, level, _label) in range_catalog.item_catalogue().items()
                      if cat == 'armour' and level <= 12 and items.params_of(t).get('armor_class', 0) > 0)
        profile = range_character.preset(12)
        profile['gear'] = {armour: 1}
        g.profile = range_character.validate_profile(profile)
        g.apply(g.clone, g.profile)
        base = g.clone.combat.armor()
        rules = replace(g.rules, armour=2, effect_armour=25, broken_armour=False)
        g.rules = rules
        g.apply(g.clone, g.profile)
        self.assertEqual(g.clone.combat.armor(), (base + 25) * 2)
        worn = next(row for row in g.clone.inv.rows() if row['slot'] in inventory.WEAR_SLOTS)
        points = items.params_of(worn['type_id'])['armor_class']
        g.store.update_item(worn['uniq'], brk=0)
        g.clone.inv.refresh_gear(push=False)
        without_broken = g.clone.combat.armor()
        g.clone.char.training_rules = replace(rules, broken_armour=True)
        self.assertEqual(g.clone.combat.armor(), without_broken + points * 2)

    async def test_shot_factory_uses_session_ammunition_rules(self):
        g = self.enter()
        profile = range_character.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        g.profile = range_character.validate_profile(profile)
        g.rules = range_rules.Rules.parse(dict(ammo_modifiers=True, spread=0.5))
        g.spawn_point = 0
        g.start('mob')
        g.clone.cmd_lenter({})
        gun = g.clone.inv.in_slot(inventory.PRIMARY)
        si = items.params_of(gun['type_id'])
        ammo = si['comp_array'][0]
        asi = items.params_of(ammo)
        g.store.update_item(gun['uniq'], ammo_count=3, ammo_type=ammo)
        target = next(iter(g.room.combat.mobs.values()))
        with patch.object(combat.Fighter, 'schedule_action') as schedule:
            g.clone.combat.use_fire(dict(obj=inventory.oid_of(gun), target='1%08x' % target.eid))
            weapon = schedule.call_args.args[8]
        mode = gun['cur_mode']
        self.assertEqual(weapon.dmin, round(si['h_damage_min'][mode] * asi['dam_mod']))
        self.assertEqual(weapon.max_range, si['max_range'][mode] * asi['range_mod'])
        self.assertEqual(weapon.piercing, asi['piercing'])

    def party_members(self, count=3):
        import party
        directory = rooms.Directory()
        parties = party.Parties(directory)
        self.addCleanup(patch.stopall)
        patch.object(server, 'PARTIES', parties).start()
        members = [self.s]
        for number in range(1, count):
            aid, _ = self.store.register('party-range-' + str(number), 'test-only')
            cid, _ = self.store.create_character(aid, 'PartyTester' + str(number), 0, '1')
            member = server.Session(Writer(), 'test-party')
            member.training_protocol = 1
            member.char_id = cid
            member.active = dict(self.store.character(cid))
            member.char = progression.Character.load(self.store, cid)
            member.loc, member.room, member.pos = self.s.loc, self.s.room, self.s.pos
            members.append(member)
        group = party.Party(self.s.char_id)
        group.members = [member.char_id for member in members]
        group.present = set(group.members)
        for member in members:
            directory.add(member)
            parties.by_char[member.char_id] = group
            member.room.players[member] = True
        self.before = list(self.store.db._db.iterdump())
        async def close_members():
            for member in members:
                if member.training_ground:
                    member.training_ground.exit(notify=False)
        self.addAsyncCleanup(close_members)
        return members, parties, group

    async def test_party_leader_takes_only_members_at_bert_into_one_isolated_room(self):
        members, parties, group = self.party_members(4)
        members[-1].room = rooms.Room(world.location(106), rooms.IdAllocator(), {})
        with self.assertRaises(ValueError):
            tg.check_entry(members[1], dict(npc=self.npc))
        import quests
        self.assertFalse(members[1].quest_available(quests.get(range_settings.ENTRY_QUEST)))
        tg.enter(self.s, dict(npc=self.npc))
        grounds = [member.training_ground for member in members[:3]]
        self.assertIsNone(members[-1].training_ground)
        self.assertTrue(all(ground.room is grounds[0].room for ground in grounds))
        self.assertEqual(len({ground.clone.pid for ground in grounds}), 3)
        self.assertEqual(len({ground.clone.pos for ground in grounds}), 3)
        self.assertEqual(len({id(ground.store) for ground in grounds}), 3)
        for ground in grounds:
            ground.clone.cmd_lenter({})
        self.assertEqual(len(grounds[0].room.players), 3)
        parties.dissolve(group)
        self.assertTrue(all(member.party() is None for member in members))
        self.assertTrue(all(not grounds[0].clone.combat.allied(other.clone.combat) for other in grounds[1:]))
        self.unchanged()

    async def test_party_can_leave_or_disband_using_the_actual_client_command(self):
        members, parties, group = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for ground in (first, second):
            ground.clone.cmd_lenter({})
        self.assertTrue(first.clone.combat.allied(second.clone.combat))
        members[1].writer.frames.clear()
        second.clone.handle_training('p_op', dict(op=1, id=0))
        self.assertIsNone(members[0].party())
        self.assertIsNone(members[1].party())
        frames = [decode(frame[:-1]) for frame in members[1].writer.frames]
        self.assertEqual(sum(command == 'cmdAck' and params['res'] == 0 for command, params in frames), 1)
        self.assertIs(first.room, second.room)
        self.assertFalse(first.clone.combat.allied(second.clone.combat))
        self.unchanged()

    async def test_party_individual_trade_and_actor_inspection_never_mix_inventories(self):
        members, parties, group = self.party_members()
        tg.enter(self.s, dict(npc=self.npc))
        first, second, third = [member.training_ground for member in members]
        for ground in (first, second, third):
            ground.clone.cmd_lenter({})
        for ground, count in ((first, 2), (second, 3)):
            self.approach_shop(ground, 'medical')
            source = next(iter(range_supply.sources('medical')))
            self.supply(ground, source, count)
        a = [row for row in first.clone.inv.rows() if row['root'] == items.HEAL]
        b = [row for row in second.clone.inv.rows() if row['root'] == items.HEAL]
        self.assertEqual((len(a), len(b)), (2, 3))
        self.assertFalse(set(row['uniq'] for row in a) & set(row['uniq'] for row in b))
        self.assertFalse(third.clone.inv.rows())
        members[0].writer.frames.clear()
        first.clone.cmd_getInfo(dict(id=second.clone.pid))
        frames = [decode(frame[:-1]) for frame in members[0].writer.frames]
        self.assertTrue(any(command == 'userInfo_Player' and params['name'] == members[1].nick
                            for command, params in frames))
        first.clone.cmd_ss_get(dict(target=second.clone.pid, slot=inventory.MASK_BAG))
        _, snapshot = decode(members[0].writer.frames[-1][:-1])
        self.assertEqual(set(snapshot['o_list']), {inventory.oid_of(row) for row in b})
        first.clone.cmd_ss_get_di(dict(obj=inventory.oid_of(b[0])))
        _, info = decode(members[0].writer.frames[-1][:-1])
        self.assertEqual(str(info['obj']), inventory.oid_of(b[0]))
        self.unchanged()

    async def test_each_party_member_controls_only_their_target_and_survives_leader_exit(self):
        members, parties, group = self.party_members()
        tg.enter(self.s, dict(npc=self.npc))
        first, second, third = [member.training_ground for member in members]
        for ground in (first, second, third):
            ground.clone.cmd_lenter({})
            ground.start('mob')
        room = first.room
        self.assertEqual(len(room.combat.mobs), 3)
        self.assertEqual(len({mob.cell for mob in room.combat.mobs.values()}), 3)
        remaining = {second.mob_eid, third.mob_eid}
        first.reset('Возврат')
        self.assertEqual(set(room.combat.mobs), remaining)
        self.assertTrue(room.ws)
        first.exit(notify=False)
        self.assertEqual(set(room.combat.mobs), remaining)
        self.assertEqual(len(room.grounds), 2)
        self.assertIs(room.ground, second)
        self.assertFalse(second.closed)
        third.clone.combat.die(second.clone.combat)
        await asyncio.sleep(0)
        self.assertFalse(third.clone.combat.dead)
        self.assertEqual(third.phase, 'ready')
        self.assertIn(second.mob_eid, room.combat.mobs)
        second.exit(notify=False)
        self.assertEqual(len(room.grounds), 1)
        self.assertIs(room.ground, third)
        third.state()
        third.exit(notify=False)
        self.assertFalse(room.grounds)
        self.assertFalse(room.players)
        self.assertTrue(room.combat.timer is None or room.combat.timer.cancelled())
        self.unchanged()

    async def test_party_roster_translates_visible_clone_ids_and_party_command_back(self):
        members, parties, group = self.party_members()
        tg.enter(self.s, dict(npc=self.npc))
        first, second, third = [member.training_ground for member in members]
        members[0].writer.frames.clear()
        parties.roster_for(group, members[0])
        command, roster = decode(members[0].writer.frames[-1][:-1])
        self.assertEqual(command, 'p_m')
        self.assertEqual(roster['list'], [0, second.clone.pid, third.clone.pid])
        first.clone.handle_training('p_op', dict(op=4, id=second.clone.pid))
        self.assertEqual(group.leader, members[1].char_id)
        self.unchanged()

    async def test_shared_map_changes_all_ready_participants_and_keeps_their_items(self):
        members, parties, group = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for ground in (first, second):
            ground.clone.cmd_lenter({})
        first.change_location(59)
        self.assertIs(first.room, second.room)
        self.assertEqual((first.location, second.location), (59, 59))
        self.assertNotEqual(first.clone.pos, second.clone.pos)
        first.clone.cmd_lenter({})
        second.clone.cmd_lenter({})
        second.start('mob')
        with self.assertRaises(ValueError):
            first.change_location(108)
        self.assertEqual(second.phase, 'fight')
        self.unchanged()

    async def test_shared_pvp_hits_only_the_other_clone_and_recovers_from_ready_phase(self):
        members, parties, group = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        for ground in (first, second):
            ground.clone.cmd_lenter({})
        self.assertTrue(combat.Fighter.allied(first.clone.combat, second.clone.combat))
        parties.dissolve(group)
        self.assertFalse(combat.Fighter.allied(first.clone.combat, second.clone.combat))
        second.clone.pos = next(cell for cell in progression.hex_neighbours(
            first.clone.pos, first.clone.loc.width, first.clone.loc.height)
            if cell not in first.clone.loc.obstacles and cell not in {entry.cell for entry in first.room.npcs.values()})
        hp = second.clone.char.hp
        with patch.object(combat, 'roll', return_value=True):
            first.clone.combat.strike_now(second.clone.combat, second.clone.pos, (3, 3), 0, 0)
        self.assertLess(second.clone.char.hp, hp)
        self.assertFalse(first.room.combat.loot)
        self.assertEqual(second.phase, 'ready')
        second.room.combat.kill(second.clone.combat, first.clone.combat)
        await asyncio.sleep(0)
        self.assertFalse(second.clone.combat.dead)
        self.assertEqual(second.clone.char.hp, second.clone.char.hp_max)
        self.assertIs(first.room, second.room)
        self.assertFalse(first.closed)
        self.unchanged()

    async def test_shared_peer_information_is_available_before_map_ack(self):
        members, parties, group = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        members[0].writer.frames.clear()
        first.clone.handle_training('getInfo', dict(id=second.clone.pid))
        frames = [decode(frame[:-1]) for frame in members[0].writer.frames]
        self.assertTrue(any(command == 'userInfo_Player' and params['id'] == second.clone.pid
                            for command, params in frames))
        self.assertIsNone(first.room.combat.actor(second.clone.pid))
        self.unchanged()

    async def test_one_participant_return_does_not_end_other_players_pvp(self):
        members, parties, group = self.party_members()
        tg.enter(self.s, dict(npc=self.npc))
        first, second, third = [member.training_ground for member in members]
        for ground in (first, second, third):
            ground.clone.cmd_lenter({})
        parties.dissolve(group)
        second.clone.combat.engage_player(third.clone.combat)
        first.room.combat.set_ws(True)
        ap = second.clone.combat.ap = 12
        first.reset('Возврат')
        self.assertTrue(first.room.ws)
        self.assertEqual(second.clone.combat.ap, ap)
        self.assertIn(third.clone.combat, second.clone.combat.duels)
        self.unchanged()

    async def test_group_preparation_failure_leaves_everyone_in_the_original_world(self):
        members, parties, group = self.party_members()
        public = self.s.room
        constructor = tg.Ground
        calls = 0
        def fail_second(owner):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError('test preparation failure')
            return constructor(owner)
        active = set(range_runtime.ACTIVE)
        with patch.object(tg, 'Ground', side_effect=fail_second):
            with self.assertRaises(ValueError):
                tg.enter(self.s, dict(npc=self.npc))
        self.assertTrue(all(member.room is public and member.training_ground is None for member in members))
        self.assertEqual(range_runtime.ACTIVE, active)
        self.assertEqual(group.members, [member.char_id for member in members])
        self.unchanged()

    async def test_individual_exit_restores_real_party_identifiers_for_the_leaver(self):
        members, parties, group = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        members[0].writer.frames.clear()
        with patch.object(members[0], 'enter_location'):
            first.exit()
        frames = [decode(frame[:-1]) for frame in members[0].writer.frames]
        roster = next(params for command, params in frames if command == 'p_m')
        self.assertEqual(roster['list'], [0, members[1].pid])
        self.assertIsNotNone(members[1].training_ground)
        second.clone.cmd_lenter({})
        self.unchanged()

    async def test_ready_fighter_presets_cover_each_released_set(self):
        g = self.enter()
        for type_id, info in sets.SETS.items():
            if not all(t in range_catalog.item_catalogue() for t in info['members'].values()):
                continue
            profile = g.fighter_preset(type_id)
            self.assertTrue(set(sets.SETS[type_id]['members'].values()) <= set(profile['gear']))
            self.assertTrue(any(items.root_of(t) == items.FIRE_ARM for t in profile['gear']))
            self.assertTrue(any(items.root_of(t) == items.AMMO for t in profile['gear']))
        self.unchanged()

    async def test_bert_quest_and_reentry_after_course_history(self):
        import quests
        self.s.send_npc_info(self.npc)
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertTrue(any(range_settings.ENTRY_QUEST in p.get('give_quests', []) for n, p in frames if n.startswith('userInfo_')))
        self.store.finish_quest(0, self.s.char_id, 1682)
        self.assertFalse(self.s.quest_available(quests.get(1682)))
        self.assertTrue(self.s.quest_available(quests.get(range_settings.ENTRY_QUEST)))
        self.assertFalse(any(quests.get(t).repeatable for t in range(351, 365)))
        for quest_type in range(358, 365):
            self.assertIn('второго шанса не будет', quests.get(quest_type).texts[1])
        self.assertIn(7051, range_catalog.item_catalogue())
        g = self.enter()
        g.catalogue(dict(category='weapon', level=16, line='C'))
        _, data = decode(self.s.writer.frames[-1][:-1])
        self.assertIn(7051, data['ids'])


    async def test_entry_quest_rejects_remote_hand_in_and_enters_after_commit(self):
        import quests
        quest = quests.get(range_settings.ENTRY_QUEST)
        self.assertTrue(quest.repeatable)
        self.assertTrue(quest.service)
        with patch.object(tg.settings, 'ENABLED', False):
            self.assertFalse(self.s.quest_available(quest))
        self.s.cmd_q_st(dict(mob=self.npc, q_idx=quests.given_by(range_settings.BERT).index(range_settings.ENTRY_QUEST)))
        row = next(q for q in self.store.quests(self.s.char_id) if q['type'] == range_settings.ENTRY_QUEST)
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
        self.assertTrue(self.store.quest_done(self.s.char_id, range_settings.ENTRY_QUEST))
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
        self.assertEqual(terminal[1]['res'], range_settings.TERMINAL)
        self.assertTrue(self.s.quest_available(quest))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingGround)
