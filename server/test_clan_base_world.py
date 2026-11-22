"""Restored clan bases use native maps, safe ways and only approved staff."""
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

import names
import holdings
import map_labels
import progression
import quests
import rooms
import travel
import world
from testkit import run_cases


ROOT = Path(__file__).resolve().parents[1]
BASES = {118: (6154, 1963), 382: (5955, 2032)}
STAFF = {118: Counter({688: 3, 4427: 1}), 609: Counter({689: 3, 714: 1, 716: 1}),
         382: Counter(), 380: Counter({5275: 2}), 958: Counter({5239: 1, 5240: 1})}
ROUTES = ((118, 18201, 609, BASES[118]), (609, 18202, 118, BASES[118]),
          (380, 18203, 958, BASES[382]))


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
    def test_service_names_are_preloaded_without_renaming_shared_npcs(self):
        from training import api
        api.preload_strings()
        texts = {int(row.attrib['id']): row.text or ''
                 for row in ET.fromstring(names.document_bytes())}
        services = {688: 'Подъёмник<br>В бункер',
                    689: 'Подъёмник<br>На поверхность',
                    5275: 'Вход в бункер', 4427: 'Флаг базы', 4428: 'Флаг базы',
                    716: 'Снабжение базы<br>Медицина и патроны за афро',
                    714: 'Снабжение базы<br>Медицина и патроны за G',
                    5239: 'Снабжение базы<br>Медицина и патроны за афро',
                    5240: 'Снабжение базы<br>Медицина и патроны за G'}
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
        still_closed = {381, 385, 386, 387, 388, 959, 960, 1196, 610, 328, 936, 297, 938}
        self.assertTrue(still_closed <= {int(i) for i in retired['places']})
        self.assertFalse(still_closed & set(world.settlements().values()))
        self.assertIsNone(world.cell_of(380))
        self.assertIsNone(world.cell_of(609))
        self.assertIsNone(world.cell_of(958))

    def test_original_art_and_geometry_are_unchanged(self):
        for lid in STAFF:
            with self.subTest(lid=lid):
                source = Path(world.RES) / 'locations' / 'static' / ('%d.xml' % lid)
                original, art = parts(source.read_bytes())
                current, restored_art = parts(Path(world.overlay_path(lid)).read_bytes())
                self.assertEqual(restored_art, art)
                original.pop(b'title')
                current.pop(b'title')
                if lid == 382:
                    self.assertEqual((current.pop(b'war'), current.pop(b'pvp')), (b'1', b'1'))
                    self.assertEqual((original.pop(b'war'), original.pop(b'pvp')), (b'0', b'0'))
                self.assertEqual(current, original)
                self.assertEqual(world.location(lid).title,
                                 world.overlay_index()[lid]['title'])

    def test_only_approved_original_staff_and_capture_placements_stand(self):
        for lid, expected in STAFF.items():
            with self.subTest(lid=lid):
                self.assertEqual(Counter(t for _cell, t in world.location(lid).spawns), expected)
        placed = {lid: Counter(r['type'] for r in world.placed_in(lid)) for lid in STAFF}
        self.assertEqual(placed, {118: Counter({7454: 1, 4829: 3, 2312: 6}),
                                  382: Counter({7451: 1, 4428: 1, 4828: 3, 918: 6}),
                                  609: Counter(), 380: Counter(), 958: Counter()})
        self.assertIsNone(rooms.check_placements(world.mob_types()))

    def test_site_defenders_have_reachable_spread_out_spawn_cells(self):
        for site in holdings.sites().values():
            with self.subTest(site=site.key):
                loc = world.location(site.loc)
                cells = [r['cell'][1] * loc.width + r['cell'][0]
                         for r in world.placed_in(site.loc)
                         if r['type'] in site.guards + site.troops]
                self.assertEqual(len(cells), 9 if site.kind == 'base' else 2)
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
                    self.assertEqual(len(soldiers), 6)
                    self.assertEqual(sum(x < loc.width / 2 for x, _y in soldiers), 3)
                    self.assertGreater(max(y for _x, y in soldiers) - min(y for _x, y in soldiers),
                                       loc.height / 2)

    def test_lifts_are_quest_only_and_do_not_expose_trade_or_repair(self):
        for lid in (118, 609):
            room = rooms.Room(world.location(lid), rooms.IdAllocator(), world.mob_types())
            lifts = [npc for npc in room.npcs.values() if npc.type_id in (688, 689)]
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
        for source, expected in [(380, 382), (958, 380)]:
            loc = world.location(source)
            self.assertTrue(travel.no_map(source))
            for cell in travel.exit_sides(loc):
                result = travel.plan_exit(loc, cell, *BASES[382])
                self.assertEqual((result.loc_id, result.gx, result.gy), (expected, *BASES[382]))
        self.assertTrue(travel.no_map(609))
        for source, cell in BASES.items():
            self.assertFalse(travel.no_map(source))
            loc = world.location(source)
            for pos, side in travel.exit_sides(loc).items():
                result = travel.plan_exit(loc, pos, *cell)
                if source == 382 and side == 'N':
                    self.assertEqual(result.loc_id, 380)
                else:
                    destination = travel.neighbour(*cell, side)
                    self.assertEqual((result.loc_id, result.gx, result.gy),
                                     (world.location_at(*destination), *destination))

    def test_arrivals_can_reach_services_and_a_return_route(self):
        arrivals = [travel.plan_quest_way(world.location(source), qid, *cell)
                    for source, qid, _target, cell in ROUTES]
        post = world.location(382)
        north = next(c for c, side in travel.exit_sides(post).items() if side == 'N')
        arrivals.append(travel.plan_exit(post, north, *BASES[382]))
        for result in arrivals:
            loc = world.location(result.loc_id)
            with self.subTest(lid=loc.id):
                self.assertNotIn(result.pos, loc.obstacles)
                accessible = reachable(loc, result.pos)
                if loc.id in (609, 380):
                    qid = 18202 if loc.id == 609 else 18203
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
            self.assertIn('минимум 3 живых соклановца ' + ('12+' if x == 5955 else '16+'), text)
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
