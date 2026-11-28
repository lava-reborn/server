"""Read-only comparison of original inhabitants with the installed map snapshot."""
import argparse, collections, hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--draft', type=Path, required=True)
    ap.add_argument('--previous-draft', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    os.environ['LAVA_BOUNDARY_WORLD'] = 'off'
    import world, rooms, boundary_world as bw, camp_elites, encounters
    manifest = json.loads(args.manifest.read_bytes())
    draft = json.loads(args.draft.read_bytes())
    previous = json.loads(args.previous_draft.read_bytes())
    types = world.mob_types()
    original_cells = {**world.borders(), **world.settlements(), **world.eden_map.CELL_TO_LOC}
    for ident in world.placements():
        if world.is_wilderness(ident):
            original_cells.setdefault(world.unpack(ident), ident)
    ids = set(world.static_ids()) | set(world.placements()) | set(original_cells.values())
    ids.update(r['source_location'] for r in manifest['cells'].values())
    before, escorts, titles = {}, {}, {}
    native_files = {}
    for i, ident in enumerate(sorted(ids), 1):
        # Only native XML bytes are cached. Every coordinate's hand placements,
        # camp filling and filtered roster are still evaluated independently.
        path = world.source_path_for(ident)
        if not path:
            continue
        if path not in native_files:
            text = Path(path).read_text(encoding='utf-8-sig')
            native_files[path] = any(int(c[4:8], 16) for c in world._chunks(text, 'mobs', 8))
        if not native_files[path] and not world.placed_in(ident) and not world.camp_fill(ident):
            before[ident] = []
            continue
        loc = world.location(ident)
        room = rooms.Room(loc, rooms.IdAllocator(), types)
        before[ident] = sorted((n.cell, n.type_id, n.root) for n in room.npcs.values())
        escorts[ident] = sorted((room.npcs[e].cell, room.npcs[e].type_id) for e in room.escorts)
        titles[ident] = (loc.title, loc.fn)
        if i % 2000 == 0:
            print('Baseline identities', i, flush=True)
        world._CACHE.clear()
    print('Original rosters collected:', len(before), flush=True)

    os.environ['LAVA_BOUNDARY_WORLD'] = str(args.manifest)
    for fn in (bw.manifest, bw.by_id, bw.blocked_cells, bw.regions, bw.overlay_path):
        fn.cache_clear()
    world._CACHE.clear()
    errors, additions, retired = [], collections.Counter(), []
    preserved = 0
    copies = {key:record['source_location'] for key,record in manifest['cells'].items()
              if record['source_location'] in (599,624)
              and record['source_location'] != original_cells.get(tuple(map(int,key.split(','))),world.pack(*map(int,key.split(','))))}
    retired_cells = set(manifest['retired'])
    # Original IDs, including interiors, are compared through Room, not merely XML.
    for ident, roster in before.items():
        if not roster or bw.row(ident):
            continue
        room = rooms.Room(world.location(ident), rooms.IdAllocator(), types)
        actual = sorted((n.cell, n.type_id, n.root) for n in room.npcs.values())
        if actual != roster:
            errors.append(dict(id=ident, problem='original_roster_changed', before=roster, after=actual))
        if sorted((room.npcs[e].cell, room.npcs[e].type_id) for e in room.escorts) != escorts.get(ident, []):
            errors.append(dict(id=ident, problem='original_escort_changed'))
        preserved += len(roster)
    for i, (key, record) in enumerate(manifest['cells'].items(), 1):
        cell = tuple(map(int, key.split(',')))
        source = original_cells.get(cell, world.pack(*cell))
        expected = before.get(source, [])
        if key in copies:
            expected = before[copies[key]]
        if key in retired_cells and expected and all(t == 1790 for c, t, r in expected):
            retired.append(dict(cell=key, source=source, palms=len(expected)))
            expected = []
        room = rooms.Room(world.location(record['id']), rooms.IdAllocator(), types)
        actual = collections.Counter((n.cell, n.type_id, n.root) for n in room.npcs.values())
        missing = collections.Counter(expected) - actual
        if missing:
            errors.append(dict(cell=key, problem='original_actor_missing_or_moved', actors=list(missing.elements())))
        extra = actual - collections.Counter(expected)
        for (hex_cell, kind, root), count in extra.items():
            if kind != 98 and not (record.get('crocodile') and kind == record['crocodile']['type_id']):
                errors.append(dict(cell=key, problem='unapproved_new_actor', hex=hex_cell, type=kind, root=root))
            additions[kind] += count
        if key not in copies:
            preserved += len(expected)
        if source in escorts and escorts[source] and record['id'] != source:
            errors.append(dict(cell=key, problem='escort_identity_changed'))
        if sorted((room.npcs[e].cell, room.npcs[e].type_id) for e in room.escorts) != escorts.get(source, []):
            errors.append(dict(cell=key, problem='original_escort_changed'))
        if i % 1000 == 0:
            print('Installed rooms', i, 'errors', len(errors), flush=True)
            world._CACHE.clear()
    for cell, source in original_cells.items():
        key = '%d,%d' % cell
        if key in retired_cells:
            continue
        if before.get(source) and key in bw.blocked_cells():
            errors.append(dict(cell=key, problem='inhabited_original_cell_blocked', id=source))

    camps = set(camp_elites.locations()) | {b.camp for b, reach in encounters.bands()}
    camps.update(i for i, (title, fn) in titles.items() if 'лагер' in title.lower() or 'bandit_camp' in fn.lower())
    camp_rows = []
    a = previous['boundary_preview']['placements']; b = draft['boundary_preview']['placements']
    for camp in sorted(camps):
        locations = [c for c, ident in original_cells.items() if ident == camp]
        nearby = []
        for x, y in locations:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    key = '%d,%d' % (x + dx, y + dy)
                    old = (a.get(key) or {}).get('template'); new = (b.get(key) or {}).get('template')
                    if old != new:
                        nearby.append(dict(cell=key, before=old, after=new))
        current = rooms.Room(world.location(camp), rooms.IdAllocator(), types)
        actual = sorted((n.cell, n.type_id, n.root) for n in current.npcs.values())
        if actual != before.get(camp, []):
            errors.append(dict(id=camp, problem='camp_roster_changed'))
        camp_rows.append(dict(id=camp, title=titles.get(camp, ('', ''))[0], cells=locations,
                              inhabitants=len(actual), nearby_changes=nearby))
    report = dict(manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                  original_identities_checked=len(before), original_inhabited_identities=sum(bool(v) for v in before.values()),
                  preserved_actor_placements=preserved, new_combat_actors=dict(additions),
                  authorised_service_copies=copies, authorised_palm_retirements=retired,
                  camps=camp_rows, errors=errors)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('camps', 'authorised_palm_retirements')}, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
