"""Restored clan bases use native maps, safe ways and only approved staff."""
from collections import Counter, deque
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import names
import npcs
import holdings
import map_labels
import progression
import quests
import rooms
import travel
import world
from testkit import run_cases


ROOT = Path(__file__).resolve().parents[1]
BASES = {118: (6083, 1957), 1442: (5926, 2068)}
STAFF = {118: Counter({688: 3, 4427: 1}), 609: Counter({689: 3, 714: 1, 1013: 1}),
         1442: Counter({5275: 3, 4428: 1}), 1443: Counter({689: 3, 1013: 1, 5240: 1})}
ROUTES = ((118, 18201, 609, BASES[118]), (609, 18202, 118, BASES[118]),
          (1442, 18203, 1443, BASES[1442]), (1443, 18204, 1442, BASES[1442]))


def read(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))


def parts(raw):
    location = re.search(rb'<location\b[^>]*>', raw)
    mobs = re.search(rb'<mobs>.*?</mobs>', raw, re.S)
    attrs = dict(re.findall(rb'(\w+)="([^"]*)"', location[0]))
    art = raw[:location.start()] + raw[location.end():mobs.start()] + raw[mobs.end():]
    return attrs, art


def reachable(loc, start):
    blocked = (loc.obstacles | {cell for cell, _type in loc.spawns}
               | {r['cell'][1] * loc.width + r['cell'][0] for r in world.placed_in(loc.id)})
    seen, todo = {start}, deque([start])
    while todo:
        for cell in progression.hex_neighbours(todo.popleft(), loc.width, loc.height):
            if cell not in blocked and cell not in seen:
                seen.add(cell)
                todo.append(cell)
    return seen


class ClanBaseWorldTests(unittest.TestCase):
    def test_base_presentations_preserve_service_identity_and_preload_local_caption(self):
        import accounts
        import items
        import server
        from training import api
        api.preload_strings()
        texts = {int(row.attrib['id']): row.text or ''
                 for row in ET.fromstring(names.document_bytes())}
        self.assertEqual(texts[8000001], 'Снабженец базы клана')
        self.assertEqual(names.text(1013), names.BASE[1013])
        with closing(accounts.Store(':memory:')) as store, patch.object(server, 'STORE', store):
            for lid, type_id in ((118, 688), (1442, 5275), (609, 1013), (1443, 1013), (185, 1013)):
                with self.subTest(lid=lid, type_id=type_id):
                    base_medic = type_id == 1013 and lid in (609, 1443)
                    root = world.entity_root(type_id, world.mob_types()[type_id][0])
                    # A clanless observer retains presentation/quest identity,
                    # but cannot open the bunker's owner-only supply services.
                    entry_allowed = Mock(return_value=True)
                    seat = NS(room=NS(loc=world.location(lid), npc=lambda _eid: (0, type_id, root)),
                              char_id=0, home_here=lambda _type: False,
                              base_entry_allowed=entry_allowed,
                              combat=NS(mob_info=lambda _eid: {}, after_npc_info=Mock()))
                    frames = []
                    seat.send = lambda command, **params: frames.append((command, params))
                    server.Session.send_npc_info(seat, 123)
                    if type_id in (688, 5275):
                        entry_allowed.assert_called_once()
                    else:
                        entry_allowed.assert_not_called()
                    command, params = frames[0]
                    self.assertEqual(params['give_quests'], quests.given_by(type_id))
                    self.assertEqual(params['take_quests'], quests.taken_by(type_id))
                    self.assertEqual(params['res'], 4443 if base_medic else type_id if type_id == 1013 else 689)
                    self.assertEqual(params['name'], 8000001 if base_medic else type_id)
                    if type_id == 1013:
                        self.assertEqual(command, 'userInfo_Trader')
                        self.assertEqual(params['type_list'], [] if base_medic else items.stock_for(type_id, lid))
                        self.assertEqual(params['can_trade'], 0 if base_medic else 1)
                    else:
                        self.assertEqual(command, 'userInfo_Commoner')
                        self.assertEqual((params['can_trade'], params['can_repair']), (0, 0))
                    self.assertTrue(names.known(params['name']))
                    self.assertIn(params['res'], world.mob_types())
        changed = npcs.presentation(1013, 609)
        changed['name'] = 1
        self.assertEqual(npcs.presentation(1013, 609)['name'], 8000001)
        self.assertEqual(npcs.presentation(1013, 185), {})
        for lid, type_id in ((118, 688), (1442, 5275)):
            self.assertEqual(world.mob_types()[npcs.presentation(type_id, lid)['res']][2],
                             world.mob_types()[689][2])
        self.assertEqual(world.mob_types()[4443][2], '1f_Dok')

    def test_presentation_records_cannot_change_services_or_use_unknown_captions(self):
        for row in ({'res': 4443, 'can_trade': 1, 'why': 'invalid'},
                    {'name': 8000001, 'why': 'unknown string'},
                    {'res': -1, 'why': 'invalid model'}, {'res': 689}):
            with self.subTest(row=row), self.assertRaises(RuntimeError):
                npcs._presentation({'presentation': {'609': {'1013': row}}})

    def test_ammunition_suppliers_stand_by_tall_cylinders_with_free_approach(self):
        for lid, type_id in ((609, 714), (1443, 5240)):
            with self.subTest(lid=lid):
                loc = world.location(lid)
                cell = next(cell for cell, typ in loc.spawns if typ == type_id)
                x, y = cell % loc.width, cell // loc.width
                self.assertEqual((x, y), (31, 43))
                self.assertNotIn(cell, loc.obstacles)
                self.assertNotIn(cell, travel.exit_sides(loc))
                root = ET.fromstring(Path(world.overlay_path(lid)).read_bytes())
                cylinders = root.find("sprite[@id='balon.png']").text
                bx, by = int(cylinders[:2], 16), int(cylinders[2:4], 16)
                # The native point is (40*x + 20 for odd rows, 15*y).
                self.assertGreater(40 * x + 20 * (y % 2), 40 * bx + 20 * (by % 2))
                self.assertLess(y, by)
                neighbours = progression.hex_neighbours(cell, loc.width, loc.height)
                self.assertGreaterEqual(sum(c not in loc.obstacles for c in neighbours), 4)

    def test_relocated_bases_retire_both_old_squares_and_reach_dongola(self):
        import map_cells
        plan = map_cells.load()
        old = {(6032, 1957), (6033, 1957)}
        self.assertTrue(old <= set(plan.cells))
        self.assertFalse(old & (set(plan.keep) | set(plan.paint)))
        self.assertTrue(all(world.is_wilderness(world.location_at(*cell)) for cell in old))
        shown = map_labels.apply(Path(world.RES, 'database', 'locations.xml').read_bytes())[0]
        labels = {map_labels._key(row[0])[:2] for row in map_labels.ROW.finditer(shown)}
        self.assertFalse(old & labels)
        self.assertEqual(BASES[118], (6033 + 50, 1957))
        self.assertEqual({cell for cell, (colour, _why) in plan.paint.items() if colour == 'clan'},
                         set(BASES.values()))
        town, south, east = (world.cell_of(lid) for lid in (49, 112, 114))
        base = BASES[1442]
        ratio = math.dist(town, base) / max(math.dist(town, south), math.dist(town, east))
        self.assertTrue(1.30 <= ratio <= 1.32, ratio)
        slope = lambda cell: (cell[1] - town[1]) / (cell[0] - town[0])
        self.assertTrue(slope(east) < slope(base) < slope(south))
        self.assertTrue(all(world.passable(base[0] + dx, base[1] + dy)
                            for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
        seen, todo = {town}, deque([town])
        while todo and base not in seen:
            x, y = todo.popleft()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                cell = x + dx, y + dy
                if (cell not in seen and town[0] - 20 <= cell[0] <= east[0] + 20
                        and town[1] - 20 <= cell[1] <= base[1] + 20
                        and world.passable(*cell)):
                    seen.add(cell)
                    todo.append(cell)
        self.assertIn(base, seen)

    def test_saved_base_occupants_follow_yards_without_moving_map_walkers(self):
        import accounts
        with closing(accounts.Store(':memory:')) as store:
            for lid in (118, 609, 1442, 1443):
                aid, _ = store.register('base-' + str(lid), 'local-password')
                cid, _ = store.create_character(aid, 'Base ' + str(lid), 0, '1')
                store.save_position(cid, lid, 123, 6033, 1957, False)
                store.set_home(cid, lid, 6033, 1957)
            aid, _ = store.register('walker', 'local-password')
            walker, _ = store.create_character(aid, 'Walker', 0, '1')
            store.save_position(walker, 1442, None, 6000.25, 2000.75, True)
            result = accounts.relocate_clan_base_cells(store.db)
            self.assertEqual(result, dict(moved=4, homes=4))
            for lid in (118, 609, 1442, 1443):
                row = store.character_by_name('Base ' + str(lid))
                target = BASES[118 if lid in (118, 609) else 1442]
                self.assertEqual((row['gx'], row['gy']), target)
                self.assertEqual((row['home_gx'], row['home_gy']), target)
                self.assertEqual((row['loc'], row['pos'], row['home_loc']), (lid, 123, lid))
            self.assertEqual((store.character(walker)['gx'], store.character(walker)['gy']),
                             (6000.25, 2000.75))

    def test_service_names_are_preloaded_without_renaming_shared_npcs(self):
        from training import api
        api.preload_strings()
        texts = {int(row.attrib['id']): row.text or ''
                 for row in ET.fromstring(names.document_bytes())}
        services = {688: 'Подъёмник<br>В бункер',
                    689: 'Подъёмник<br>На поверхность',
                    5275: 'Вход в бункер', 4427: 'Флаг базы', 4428: 'Флаг базы',
                    716: 'Снабжение базы<br>Медицина и патроны за афро',
                    714: 'Снабжение базы<br>Патроны за афро и G',
                    5239: 'Снабжение базы<br>Медицина и патроны за афро',
                    5240: 'Снабжение базы<br>Патроны за афро и G'}
        for type_id, title in services.items():
            with self.subTest(type_id=type_id):
                self.assertEqual(texts[type_id], title)
                self.assertEqual(names.text(type_id), title)
        for type_id in (1011, 655):
            self.assertEqual(texts[type_id], names.ORIG_PERSON_NAMES[type_id])
        # Dynamic clan captions stay on the native ClanInfo object, not in
        # the numeric static table fetched before a player logs in.
        self.assertNotIn('Клановая база — ', ''.join(texts.values()))

    def test_only_two_base_cells_are_restored(self):
        retired = read('retired.json')
        for lid, cell in BASES.items():
            with self.subTest(lid=lid):
                self.assertEqual(world.location_at(cell[0] + .99, cell[1] + .99), lid)
                self.assertEqual(world.cell_of(lid), cell)
                self.assertEqual(read('settlements_verified.json')['cells']['%d,%d' % cell], lid)
                self.assertNotIn('%d,%d' % cell, retired['cells'])
        self.assertFalse(set(STAFF) & {int(i) for i in retired['places']})
        # Adjacent historical arenas, transport rooms and other clan bases
        # must not become accessible as a side effect of this restoration.
        still_closed = {380, 382, 958, 381, 385, 386, 387, 388, 959, 960, 1196, 610, 328, 936, 297, 938}
        self.assertTrue(still_closed <= {int(i) for i in retired['places']})
        self.assertFalse(still_closed & set(world.settlements().values()))
        self.assertIsNone(world.cell_of(380))
        self.assertIsNone(world.cell_of(609))
        self.assertIsNone(world.cell_of(1443))

    def test_original_art_and_geometry_are_unchanged(self):
        for lid in STAFF:
            with self.subTest(lid=lid):
                source_id = {1442: 118, 1443: 609}.get(lid, lid)
                source = Path(world.RES) / 'locations' / 'static' / ('%d.xml' % source_id)
                original, art = parts(source.read_bytes())
                current, restored_art = parts(Path(world.overlay_path(lid)).read_bytes())
                # Git may normalize XML CRLF to LF. Every other byte of
                # the non-NPC artwork/geometry fragment must stay exact.
                self.assertEqual(restored_art.replace(b'\r\n', b'\n'),
                                 art.replace(b'\r\n', b'\n'))
                original.pop(b'title')
                current.pop(b'title')
                self.assertEqual(current, original)
                self.assertEqual(world.location(lid).title,
                                 world.overlay_index()[lid]['title'])

    def test_only_approved_original_staff_and_capture_placements_stand(self):
        for lid, expected in STAFF.items():
            with self.subTest(lid=lid):
                self.assertEqual(Counter(t for _cell, t in world.location(lid).spawns), expected)
        placed = {lid: Counter(r['type'] for r in world.placed_in(lid)) for lid in STAFF}
        self.assertEqual(placed, {118: Counter({7454: 1, 4829: 3, 2312: 10}),
                                  1442: Counter({7451: 1, 4828: 3, 918: 10}),
                                  609: Counter({989: 1}), 1443: Counter({989: 1})})
        self.assertIsNone(rooms.check_placements(world.mob_types()))

    def test_site_defenders_have_reachable_spread_out_spawn_cells(self):
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                loc = world.location(site.loc)
                cells = [r['cell'][1] * loc.width + r['cell'][0]
                         for r in world.placed_in(site.loc)
                         if r['type'] in site.guards + site.troops]
                self.assertEqual(len(cells), 13 if site.kind == 'base' else 2)
                exits = travel.exit_sides(loc)
                self.assertTrue(exits)
                accessible = set()
                for edge in exits:
                    if edge not in accessible and edge not in loc.obstacles:
                        accessible.update(reachable(loc, edge))
                for cell in cells:
                    self.assertNotIn(cell, loc.obstacles)
                    self.assertNotIn(cell, exits)
                    self.assertTrue(accessible.intersection(
                        progression.hex_neighbours(cell, loc.width, loc.height)))
                if site.kind == 'base':
                    soldiers = [r['cell'] for r in world.placed_in(site.loc)
                                if r['type'] in site.troops]
                    self.assertEqual(len(soldiers), 10)
                    self.assertGreaterEqual(sum(x < loc.width / 2 for x, _y in soldiers), 4)
                    self.assertGreater(max(y for _x, y in soldiers) - min(y for _x, y in soldiers),
                                       loc.height / 2)

    def test_lifts_are_quest_only_and_do_not_expose_trade_or_repair(self):
        for lid in STAFF:
            room = rooms.Room(world.location(lid), rooms.IdAllocator(), world.mob_types())
            lifts = [npc for npc in room.npcs.values() if npc.type_id in (688, 689, 5275)]
            self.assertEqual(len(lifts), 3)
            self.assertEqual({npc.root for npc in lifts}, {world.COMMONER})

    def test_native_passage_quests_have_no_reward_fee_or_chain_gate(self):
        for source, qid, target, cell in ROUTES:
            with self.subTest(qid=qid):
                quest = quests.get(qid)
                self.assertEqual(quest.give, quest.take)
                self.assertEqual(quest.level, 0)
                self.assertEqual((quest.repeatable, quest.service), (1, True))
                self.assertEqual((quest.rew_afro, quest.rew_gold, quest.rew_obj), (0, 0, []))
                self.assertEqual(quest.wants(), [])
                raw = next(row for row in read('quests.json')['quests'] if row['type'] == qid)
                self.assertFalse(any(raw.get(key) for key in
                                     ('cost_afro', 'cost_gold', 'need_quest', 'need_any', 'rew_xp')))
                for other in set(STAFF) - {source}:
                    with self.assertRaises(travel.Refused):
                        travel.plan_quest_way(world.location(other), qid, *cell)
                self.assertEqual(travel.plan_quest_way(world.location(source), qid, *cell).loc_id,
                                 target)

    def test_inner_edges_and_door_return_only_to_their_own_base(self):
        self.assertTrue(travel.no_map(1443))
        self.assertTrue(travel.no_map(609))
        for source, cell in BASES.items():
            self.assertFalse(travel.no_map(source))
            loc = world.location(source)
            for pos, side in travel.exit_sides(loc).items():
                result = travel.plan_exit(loc, pos, *cell)
                destination = travel.neighbour(*cell, side)
                self.assertEqual((result.loc_id, result.gx, result.gy),
                                 (world.location_at(*destination), *destination))

    def test_arrivals_can_reach_services_and_a_return_route(self):
        arrivals = [travel.plan_quest_way(world.location(source), qid, *cell)
                    for source, qid, _target, cell in ROUTES]
        for result in arrivals:
            loc = world.location(result.loc_id)
            with self.subTest(lid=loc.id):
                self.assertNotIn(result.pos, loc.obstacles)
                accessible = reachable(loc, result.pos)
                if loc.id in (609, 1443):
                    qid = 18202 if loc.id == 609 else 18204
                    return_cells = next(cells for cells, row in travel.quest_ways(loc)
                                        if row['quest'] == qid)
                else:
                    return_cells = set(travel.exit_sides(loc))
                self.assertTrue(accessible & return_cells)
                inhabitants = [cell for cell, _type in loc.spawns]
                inhabitants += [r['cell'][1] * loc.width + r['cell'][0] for r in world.placed_in(loc.id)]
                for cell in inhabitants:
                    self.assertTrue(any(c in accessible for c in
                                        progression.hex_neighbours(cell, loc.width, loc.height)))

    def test_native_resource_ids_and_client_manifest_are_valid(self):
        pinned = {}
        for line in (ROOT / 'client' / 'base.txt').read_text(encoding='utf-8').splitlines():
            fields = line.split('\t')
            if len(fields) == 3:
                digest, size, path = fields
                pinned[path] = (digest, int(size))
        files = {lid: Path(world.overlay_path(lid)).read_bytes() for lid in STAFF}
        manifest = world.loc_defs(b'<data></data>', files)
        for lid, raw in files.items():
            self.assertIn(('locations/static/%d.xml' % lid).encode(), manifest)
            self.assertIn(hashlib.md5(raw).hexdigest().encode(), manifest)
            loc = world.location(lid)
            types = {t for _cell, t in loc.spawns} | {r['type'] for r in world.placed_in(lid)}
            for type_id in types:
                self.assertIn(type_id, world.mob_types())
                self.assertTrue(names.known(type_id))
                art = world.mob_types()[type_id][2]
                path = 'mobs/' + art + '.xml'
                self.assertIn(path, pinned)
                # Model art belongs to the client. The production/CI server
                # slice omits unused client files; a full original archive
                # additionally verifies their pinned size and hash here.
                model = Path(world.RES) / path
                if model.is_file():
                    raw = model.read_bytes()
                    self.assertEqual((hashlib.sha256(raw).hexdigest(), len(raw)), pinned[path])

    def test_base_tooltips_restore_both_original_and_previously_cut_clients(self):
        cells = set(BASES.values())
        edits = [row for row in map_labels.load() if row[:2] in cells]
        originals = b''.join(b'<location x="%d" y="%d" text="%s" />\n'
                             % (x, y, map_labels.escape(was).encode())
                             for x, y, was, _new in edits if was is not None)
        expected = {(x, y, new) for x, y, _was, new in edits if new is not None}
        for x, y, text in expected:
            self.assertIn('3 живых соклановца ' + ('12+' if (x, y) == BASES[1442] else '16+'), text)
            self.assertIn('Каждый ранит хозяина', text)
            self.assertIn('клан с наибольшим уроном', text)
            self.assertLessEqual(len(text.split('<br>')), 5)
            for value in ('20:00–21:00', '19:55', '1 500 000', '21:15'):
                self.assertIn(value, text)
        for raw in (b'<data>' + originals + b'</data>', b'<data></data>'):
            with self.subTest(original=bool(originals in raw)):
                shown, _changed = map_labels.apply(raw, edits)
                self.assertEqual([map_labels._key(m[0]) for m in map_labels.ROW.finditer(shown)],
                                 list(dict.fromkeys(map_labels._key(m[0])
                                                    for m in map_labels.ROW.finditer(shown))))
                self.assertEqual({map_labels._key(m[0]) for m in map_labels.ROW.finditer(shown)},
                                 expected)
                self.assertEqual(map_labels.apply(shown, edits), (shown, 0))


if __name__ == '__main__':
    run_cases(ClanBaseWorldTests)
