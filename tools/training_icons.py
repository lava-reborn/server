"""Generate/check range icon metadata from the shipped client's manifest.

LAVA_RES needs only the server XML slice; SWF artwork is never opened here.
    python tools/training_icons.py          # regenerate data/training_icons.json
    python tools/training_icons.py --check  # refuse stale or missing mappings
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'server')]

from client.build import read_entries, read_paths
import items
import own_items
from training import catalog, display
from training import items as training_items

PATH = ROOT / 'data/training_icons.json'


def client_paths():
    original_paths = set(read_entries(str(ROOT / 'client/base.txt'), 'lava-base 1'))
    paths = set(original_paths)
    paths.difference_update(read_paths(str(ROOT / 'client/remove.txt')))
    paths.update(read_entries(str(ROOT / 'client/extra.txt'), 'lava-extra 1'))
    paths.update(p.relative_to(ROOT / 'client/files').as_posix()
                 for p in (ROOT / 'client/files').rglob('*') if p.is_file())
    # The builder creates these copies only from an existing original icon.
    for target, original in own_items.icons(items.catalogue()).items():
        if original not in original_paths:
            raise ValueError('Missing own-item icon source: ' + original)
        paths.add(target)
    return paths


def document():
    training_items.register_sets_and_strings()
    paths = client_paths()
    return {'version': 1, 'sources': {
        str(source): display.resolve_icon(source, paths)
        for source in sorted(catalog.item_catalogue())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = document()
    if args.check:
        if json.loads(PATH.read_text(encoding='utf-8')) != expected:
            raise SystemExit('Stale training_icons.json; run tools/training_icons.py')
    else:
        PATH.write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')
    print('Training icons: %d verified client mappings' % len(expected['sources']))


if __name__ == '__main__':
    main()
