"""Shared Eden rooms, persisted ground, restoration and admission boundaries."""
import asyncio
import time
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace as NS
from unittest.mock import patch

from test_eden_quests import EdenQuestTests
from test_eden_region import EXPECTED_CELLS
import combat
import eden
import inventory
import items
import names
import progression
import quests
import rooms
import server
import travel
import world
from testkit import run_cases
from protocol import decode


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode('utf-8')))

    def is_closing(self):
        return False

    def close(self):
        pass


class EdenBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixture = EdenQuestTests("test_three_real_exchanges_feed_the_full_quota_and_exit")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.store, self.s, self.cid = fixture, fixture.store, fixture.s, fixture.cid

    def real_sessions(self, count=2):
        self.shared_rooms = rooms.Rooms(world.mob_types())
        self.enterContext(patch.object(server, 'ROOMS', self.shared_rooms))
        self.enterContext(patch.object(server, 'ONLINE', rooms.Directory()))
        self.enterContext(patch.object(server, 'PARTIES', NS(
            online=lambda _s: None, party_of=lambda _s: None)))
        self.enterContext(patch.object(server, 'CLANS', NS(
            online=lambda _s: None, entered=lambda _s: None)))
        self.enterContext(patch.object(server, 'GMAP', NS(
            leave=lambda _s: None, enter=lambda _s: None, moved=lambda _s: None)))
        self.enterContext(patch.object(server, 'broadcast_online_count'))
        aid, _ = self.store.register('eden_shared_test', 'isolated-password')
        players = []
        for idx in range(count):
            cid, _ = self.store.create_character(aid, 'EdenPeer%d' % idx, 0, '1')
            eden.assign(self.store, cid, 'test', 'Shared boundary regression')
            player = server.Session(Writer(), 'eden-shared-test')
            player.char_id = cid
            player.account = {'id': aid}
            player.active = self.store.character(cid)
            player.load_character(cid)
            player.restore(self.store.character(cid))
            players.append(player)
        return players

    def stop_sessions(self, players):
        for player in players:
            player.combat.close()
            player.leave_room()
            if player.residence_timer is not None:
                player.residence_timer.cancel()
        for room in self.shared_rooms.rooms.values():
            if room.combat is not None:
                if room.combat.timer is not None:
                    room.combat.timer.cancel()
                for bag in room.combat.loot.values():
                    if bag.expiry is not None:
                        bag.expiry.cancel()

    def test_room_keys_share_each_eden_location_and_preserve_ordinary_room_keys(self):
        for loc_id in sorted(eden.LOCATIONS):
            self.s.loc = world.location(loc_id)
            self.s.gx, self.s.gy = eden.target_cell(loc_id)
            first = self.s.room_key()
            self.s.char_id += 100
            second = self.s.room_key()
            self.s.char_id = self.cid
            self.assertEqual(first, loc_id)
            self.assertEqual(first, second)
            rc = combat.RoomCombat.__new__(combat.RoomCombat)
            rc.room = NS(loc=self.s.loc, key=first)
            self.assertEqual(rc.place, (loc_id, None, None))
        self.s.loc = world.location(41)
        self.s.gx, self.s.gy = 5970, 1730
        self.assertEqual(self.s.room_key(), travel.room_key(self.s.loc, 5970, 1730))

    def test_shared_ground_survives_store_round_trip_without_merging_different_maps(self):
        uniqs = {}
        for loc_id in sorted(eden.LOCATIONS):
            uniqs[loc_id] = []
            for _player in range(2):
                row = self.store.create_item(combat.LOOT_OWNER, inventory.STARTER_AMMO,
                                             items.AMMO, count=3)
                uniqs[loc_id].append(row["uniq"])
                self.store.lay_down({row["uniq"]: time.time() + 300},
                                    (loc_id, None, None), world.location(loc_id).entry_cell())
        persisted = self.store.on_ground(combat.LOOT_OWNER)
        self.assertEqual([(row["loc"], row["gx"], row["gy"]) for row in persisted],
                         [(loc_id, None, None) for loc_id in sorted(eden.LOCATIONS) for _ in range(2)])

        async def reload_rooms():
            restored = rooms.Rooms(world.mob_types())
            self.assertEqual(combat.restore_ground(restored, self.store), (0, 2 * len(eden.LOCATIONS)))
            for loc_id in sorted(eden.LOCATIONS):
                room = restored.get(loc_id)
                self.assertEqual(room.combat.place, (loc_id, None, None))
                ground = room.combat.loot[room.loc.entry_cell()]
                self.assertEqual(ground.uniqs, uniqs[loc_id])
                others = {u for other_loc, us in uniqs.items() if other_loc != loc_id for u in us}
                self.assertTrue(others.isdisjoint(ground.uniqs))
            for room in restored.rooms.values():
                if room.combat is not None:
                    for bag in room.combat.loot.values():
                        if bag.expiry is not None:
                            bag.expiry.cancel()

        asyncio.run(reload_rooms())

    def test_two_real_sessions_see_each_other_and_cannot_attack_on_every_eden_map(self):
        async def scenario():
            players = self.real_sessions()
            try:
                for loc_id in sorted(eden.LOCATIONS):
                    for player in players:
                        player.leave_room()
                        player.loc = world.location(loc_id)
                        player.pos = player.loc.entry_cell()
                        player.gx, player.gy = eden.target_cell(loc_id)
                        player.writer.frames.clear()
                        player.enter_location()
                        player.cmd_lenter({'accept': 1})
                    first, second = players
                    self.assertIs(first.room, second.room)
                    self.assertEqual(first.room.key, loc_id)
                    if first.loc.war:
                        self.assertNotEqual(first.pos, second.pos)
                    for viewer, other in ((first, second), (second, first)):
                        placements = [p for cmd, p in viewer.writer.frames
                                      if cmd == 'lch' and p.get('newUser') == other.pid]
                        self.assertEqual(len(placements), 1)
                        self.assertEqual(placements[0]['rtype'], -1)
                        self.assertTrue(any(cmd == 'usrUp' and p.get('id') == other.pid
                                            for cmd, p in viewer.writer.frames))
                        before = [p.character().vitals() for p in players]
                        viewer.writer.frames.clear()
                        viewer.combat.use_fire({'obj': '0', 'target': '1%08x' % other.pid})
                        acks = [p['res'] for cmd, p in viewer.writer.frames if cmd == 'cmdAck']
                        self.assertEqual(acks, [combat.RES_NO_PVP if viewer.loc.war
                                               else inventory.RES_REFUSED])
                        self.assertEqual([p.character().vitals() for p in players], before)
                        self.assertIsNone(viewer.combat.strike)
                        self.assertIsNone(viewer.combat.aim)
                        self.assertFalse(viewer.combat.pvp_allowed())
                    # One real exit must announce departure to the other viewer.
                    second.writer.frames.clear()
                    first.leave_room()
                    self.assertTrue(any(cmd == 'lch' and p.get('lostUser') == first.pid
                                        for cmd, p in second.writer.frames))
            finally:
                self.stop_sessions(players)
        asyncio.run(scenario())

    def test_all_eden_files_npcs_and_six_internal_routes_are_closed_and_walkable(self):
        expected = {**{loc_id: {1790} for loc_id in eden.LOCATIONS},
                    267: {1784, 1785, 1789, 60020},
                    1383: {1786, 1790}, 1385: {1787, 1790}, 1384: {1788, 1790}}
        route_targets = {**{loc_id: {} for loc_id in eden.LOCATIONS},
                         267: {18120: 1383, 18121: 1385, 18122: 1384},
                         1383: {18123: 267}, 1385: {18124: 267}, 1384: {18125: 267}}
        self.assertEqual(set(eden.LOCATIONS), set(expected))
        by_cell = {eden.target_cell(loc_id): loc_id for loc_id in eden.LOCATIONS}
        self.assertEqual(frozenset(by_cell), EXPECTED_CELLS)
        directions = {'W': (-1, 0), 'N': (0, -1), 'E': (1, 0), 'S': (0, 1)}
        table = rooms.Rooms(world.mob_types())
        local_quests = set()
        for loc_id in sorted(eden.LOCATIONS):
            loc = world.location(loc_id)
            root = ET.parse(world.path_for(loc_id)).getroot()
            self.assertEqual(int(root.attrib['war']), int(loc_id != eden.CENTER))
            self.assertEqual(root.attrib['pvp'], '0')
            self.assertTrue((root.findtext('outzones') or '').strip())
            gx, gy = eden.target_cell(loc_id)
            neighbours = {side: by_cell[(gx + dx, gy + dy)]
                          for side, (dx, dy) in directions.items()
                          if (gx + dx, gy + dy) in by_cell}
            self.assertEqual(set(travel.exit_sides(loc).values()), set(neighbours))
            for side, destination in neighbours.items():
                self.assertEqual(travel.side_way(loc_id, side)['target_loc_id'], destination)
            self.assertEqual(travel.walk_ins(loc), [])
            self.assertFalse(travel.no_map(loc_id))
            self.assertEqual(world.cell_of(loc_id), eden.target_cell(loc_id))
            pending = [loc.entry_cell()]
            reachable = set(pending)
            while pending:
                cell = pending.pop()
                for neighbour in progression.hex_neighbours(cell, loc.width, loc.height):
                    if neighbour not in reachable and neighbour not in loc.obstacles:
                        reachable.add(neighbour)
                        pending.append(neighbour)
            room = table.get(loc_id)
            self.assertEqual({npc.type_id for npc in room.npcs.values()}, expected[loc_id])
            palm_count = sum(npc.type_id in eden.PALMS for npc in room.npcs.values())
            if loc_id == eden.CENTER:
                self.assertEqual(palm_count, 0)
            else:
                self.assertGreaterEqual(palm_count, 11)
                self.assertLessEqual(palm_count, 15)
            for npc in room.npcs.values():
                self.assertTrue(0 <= npc.cell < loc.width * loc.height)
                self.assertNotIn(npc.cell, loc.obstacles)
                self.assertTrue(any(c in reachable for c in progression.hex_neighbours(
                    npc.cell, loc.width, loc.height)), (loc_id, npc.type_id, npc.cell))
                self.assertTrue(names.known(npc.type_id))
                given, taken = set(quests.given_by(npc.type_id)), set(quests.taken_by(npc.type_id))
                self.assertEqual(given, taken)
                self.assertTrue(given <= eden.QUESTS)
                local_quests.update(given)
            self.assertEqual({int(rec['quest']): int(rec['target_loc_id'])
                              for _cells, rec in travel.quest_ways(loc)}, route_targets[loc_id])
            for cells, _record in travel.quest_ways(loc):
                self.assertTrue(cells <= reachable, loc_id)
            for qtype, target in route_targets[loc_id].items():
                destination = travel.plan_quest_way(loc, qtype, *eden.target_cell(loc_id))
                self.assertEqual(destination.loc_id, target)
                dest = world.location(target)
                self.assertTrue(0 <= destination.pos < dest.width * dest.height)
                self.assertNotIn(destination.pos, dest.obstacles)
        self.assertEqual(local_quests, eden.QUESTS)

    def test_six_real_quest_transitions_keep_sentence_and_canonical_coordinates(self):
        async def scenario():
            players = self.real_sessions(count=1)
            player = players[0]
            try:
                player.enter_location()
                player.cmd_lenter({'accept': 1})
                for outward, inward, target in ((18120, 18123, 1383),
                                                (18121, 18124, 1385),
                                                (18122, 18125, 1384)):
                    for qtype, dest in ((outward, target), (inward, eden.CENTER)):
                        quest = quests.get(qtype)
                        npc_id, npc = next((eid, npc) for eid, npc in player.room.npcs.items()
                                           if npc.type_id in quest.give)
                        player.pos = next(c for c in progression.hex_neighbours(
                            npc.cell, player.loc.width, player.loc.height)
                            if c not in player.loc.obstacles)
                        player.writer.frames.clear()
                        player.cmd_q_st({'mob': npc_id, 'q_idx': quests.given_by(npc.type_id).index(qtype)})
                        self.assertEqual([p['res'] for cmd, p in player.writer.frames if cmd == 'cmdAck'], [0])
                        active = next(r for r in self.store.quests(player.char_id) if r['type'] == qtype)
                        player.writer.frames.clear()
                        player.cmd_q_co({'mob': npc_id, 'q_id': active['q_id'], 'obj_idx': 0})
                        self.assertEqual([p['res'] for cmd, p in player.writer.frames if cmd == 'cmdAck'], [0])
                        self.assertEqual([p['id'] for cmd, p in player.writer.frames if cmd == 'lcall'], [dest])
                        self.assertEqual(player.loc.id, dest)
                        self.assertEqual((player.gx, player.gy, player.on_map),
                                         (*eden.target_cell(dest), False))
                        self.assertEqual(player.room_key(), dest)
                        self.assertIsNotNone(eden.assigned(self.store, player.char_id))
                        player.cmd_lenter({'accept': 1})
                        self.assertEqual(self.store.character(player.char_id)['loc'], dest)
                        for params in ({}, {'to': 1}, {'to': 0}):
                            player.writer.frames.clear()
                            player.cmd_chWorld(params)
                            if params.get('to') == 1:
                                self.assertNotEqual(player.writer.frames[0], ('cmdAck', {'res': 0}))
                                self.assertFalse(player.on_map)
                            else:
                                self.assertEqual(player.writer.frames[0], ('cmdAck', {'res': 0}))
                                self.assertTrue(player.on_map)
                                self.assertTrue(any(cmd == 'gmap' for cmd, _ in player.writer.frames))
                                player.cmd_chWorld({})
                                player.cmd_lenter({'accept': 1})
                                self.assertFalse(player.on_map)
                                self.assertEqual(player.loc.id, dest)
            finally:
                self.stop_sessions(players)
        asyncio.run(scenario())

    def test_real_session_restore_enforces_sentence_before_map_and_uses_home_after_release(self):
        self.store.save_character_state(self.cid, home_loc=41, home_gx=5970, home_gy=1730)
        for loc, on_map in ((41, False), (41, True), (265, True)):
            with self.subTest(loc=loc, on_map=on_map):
                self.store.save_position(self.cid, loc, None, 5970, 1730, on_map)
                server.Session.restore(self.s, self.store.character(self.cid))
                self.assertTrue(eden.inside(self.s.loc))
                self.assertIsNotNone(self.s.eden_sentence)
                self.assertFalse(self.s.on_map)
                self.assertEqual((self.s.gx, self.s.gy), eden.target_cell(self.s.loc))
                self.assertEqual(self.s.room_key(), self.s.loc.id)
        eden.release(self.store, self.cid)
        self.store.save_position(self.cid, 264, None, 5857, 1928, False)
        server.Session.restore(self.s, self.store.character(self.cid))
        self.assertIsNone(self.s.eden_sentence)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy, self.s.on_map),
                         (41, 5970, 1730, False))

    def test_stale_bank_npc_and_open_bank_state_cannot_move_items_in_eden(self):
        row = self.fixture.give(inventory.STARTER_AMMO, 10, slot=inventory.BANK)
        before = self.store.item(row["uniq"])
        # Simulate a retained normal-world NPC/window, even if its id still
        # resolves. The plantation guard must reject before bank_transfer.
        self.s.room = NS(npc=lambda _eid: (self.s.pos, 213, world.COMMONER))
        self.s.inv.bank = 123
        self.fixture.frames.clear()
        self.s.inv.open_bank(dict(target=123))
        self.assertEqual(self.fixture.acknowledgements(), [inventory.RES_NOT_FOUND])
        self.assertIsNone(self.s.inv.bank)
        self.s.inv.bank = 123
        self.fixture.frames.clear()
        self.assertTrue(self.s.inv.bank_upd(dict(s_status=inventory.BANK_GET,
                                                obj=inventory.oid_of(row))))
        self.assertEqual(self.fixture.acknowledgements(), [inventory.RES_NOT_FOUND])
        self.assertEqual(self.store.item(row["uniq"]), before)

    def test_committed_quest_exit_runs_real_restore_and_clears_cached_sentence(self):
        self.store.save_character_state(self.cid, home_loc=41, home_gx=5970, home_gy=1730)
        self.fixture.fund(gold=5000)
        self.s.restore = server.Session.restore.__get__(self.s, server.Session)
        self.assertEqual(self.fixture.take(eden.GOLD_EXIT), [0])
        self.assertEqual(self.fixture.hand_in(self.fixture.taken_id(eden.GOLD_EXIT)), [0])
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertIsNone(self.s.eden_sentence)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy, self.s.on_map),
                         (41, 5970, 1730, False))
        self.assertEqual(self.s.room_key(), travel.room_key(self.s.loc, 5970, 1730))
        self.assertFalse(any(row["type_id"] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.cid)))

    def test_real_resurrection_returns_to_eden_and_never_resumes_training(self):
        self.store.save_character_state(self.cid, home_loc=41, home_gx=5970, home_gy=1730)
        self.store.save_training_profile(self.cid, {'inside': True})
        self.fixture.fund(afro=10000, gold=1000)
        self.s.enter_location = server.Session.enter_location.__get__(self.s, server.Session)
        # Keep real resurrection, home routing, admission and outgoing frames.
        # These services are the network/room-presence boundary of an lcall.
        self.s.cancel_travel = lambda: None
        self.s.leave_room = lambda: None
        self.s.keep_lent = lambda: None
        self.s.training_resume_char = None
        with patch.object(server, 'ONLINE', NS(by_char={}, add=lambda _s: None)), \
                patch.object(server, 'PARTIES', NS(online=lambda _s: None)), \
                patch.object(server, 'CLANS', NS(online=lambda _s: None)), \
                patch.object(server, 'ROOMS', NS(get=lambda _key: NS(ws=False))), \
                patch.object(server, 'GMAP', NS(leave=lambda _s: None)), \
                patch.object(server, 'broadcast_online_count'), \
                patch.object(server.events, 'take_back'), \
                patch.object(server.training_ground, 'resume', return_value=True) as resume:
            for res_type in (combat.RES_FREE, combat.RES_GOLD, combat.RES_AFRO):
                with self.subTest(res_type=res_type):
                    self.s.combat = combat.Fighter(self.s)
                    self.s.combat.dead = True
                    self.s.character().hp = 0
                    self.s.character().sp = 0
                    self.s.training_resume_char = None
                    self.fixture.frames.clear()
                    self.s.cmd_resurrect({'res_type': res_type})
                    self.assertFalse(self.s.combat.dead)
                    self.assertEqual(self.fixture.acknowledgements(), [0])
                    self.assertEqual([p['id'] for cmd, p in self.fixture.frames
                                      if cmd == 'lcall'], [eden.CENTER])
                    self.assertEqual(self.s.loc.id, eden.CENTER)
                    self.assertEqual((self.s.gx, self.s.gy, self.s.on_map),
                                     (*eden.target_cell(eden.CENTER), False))
                    self.assertEqual(self.s.room_key(), eden.CENTER)
                    self.assertIsNotNone(eden.assigned(self.store, self.cid))
                    self.assertIsNotNone(self.s.eden_sentence)
            resume.assert_not_called()

    def test_home_chat_command_cannot_leave_eden(self):
        self.s.combat = NS(in_combat=lambda: False)
        self.fixture.frames.clear()
        with patch.object(self.s, 'go_home') as go_home:
            self.s.cmd_userMsg({'entry': '/home', 'group': 0})
            go_home.assert_not_called()
        self.assertEqual(self.fixture.acknowledgements(), [0])
        self.assertEqual(self.s.loc.id, eden.CENTER)
        self.assertIsNotNone(eden.assigned(self.store, self.cid))
        self.assertFalse(any(cmd in ('gmap', 'lcall') for cmd, _ in self.fixture.frames))


if __name__ == "__main__":
    try:
        run_cases(EdenBoundaryTests)
    finally:
        server.STORE.close()
