"""Content-validated cache of derived map tiles for the local tester only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import zipfile
import zlib

VERSION = 1
MAX_BYTES = 32 * 1024 * 1024
INPUTS = (
    'tools/tester_map_cache.py',
    'server/map_cells.py',
    'server/jpeg_blocks.py',
    'data/map_cells.json',
    'data/retired.json',
)


def digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(root):
    """Hash code and plan inputs; source JPEGs are recorded while painting."""
    root = Path(root)
    return {name: digest(root / name) for name in INPUTS}


def read_cache(path, resource_root, inputs):
    """Read verified bytes only. No archive member is extracted to disk."""
    resource_root = Path(resource_root).resolve()
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_BYTES:
            raise ValueError('Map cache is too large')
        manifest = json.loads(archive.read('manifest.json'))
        if not isinstance(manifest, dict):
            raise ValueError('Invalid map manifest')
        if manifest.get('version') != VERSION or manifest.get('inputs') != inputs:
            raise ValueError('Map code or plan changed')
        sources = manifest['sources']
        tile_hashes = manifest['tiles']
        if not isinstance(sources, dict) or not isinstance(tile_hashes, dict):
            raise ValueError('Invalid map dependencies or tiles')
        for name, expected in sources.items():
            if not isinstance(name, str):
                raise ValueError('Invalid dependency name')
            source = (resource_root / name).resolve()
            if not source.is_relative_to(resource_root):
                raise ValueError('Invalid source path')
            if digest(source) != expected:
                raise ValueError('Map source changed')
        tiles = {}
        for name, expected in tile_hashes.items():
            if (not isinstance(name, str)
                    or PurePosixPath(name).parent != PurePosixPath('globalmap/full')
                    or not name.endswith('.jpg')):
                raise ValueError('Invalid cached tile path')
            payload = archive.read(name)
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError('Damaged map tile')
            tiles[name] = payload
        return tiles


def write_cache(path, manifest, tiles):
    """Atomically publish the optional cache; a save failure is non-fatal."""
    temporary = path.with_name('map-cache.%d.tmp' % os.getpid())
    try:
        path.parent.mkdir(exist_ok=True)
        # JPEGs are already compressed; ZIP deflation adds CPU without benefit.
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, blob in tiles.items():
                archive.writestr(name, blob)
            archive.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
        os.replace(temporary, path)
    except OSError as error:
        print('Map ready; cache could not be saved: %s' % error, flush=True)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as error:
            print('Map cache temporary file could not be removed: %s' % error, flush=True)


def prepare(web, root, progress):
    root = Path(root)
    cache = root / 'state' / 'map-cache.zip'
    inputs = key(root)
    plan = web.map_cells.load()
    try:
        tiles = read_cache(cache, web.RES_ROOT, inputs)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            RuntimeError, EOFError, zlib.error) as error:
        print('Map cache miss: %s' % error, flush=True)
    else:
        web.MAP_TILES = web.map_cells.Served(web.RES_ROOT, plan, prepared_tiles=tiles)
        progress(100, 'cached')
        print('Map cache ready: %d tiles; painting skipped.' % len(tiles), flush=True)
        return 'hit'

    sources = {}
    read = web.map_cells.reader(web.RES_ROOT)

    def recorded(name):
        blob = read(name)
        sources[name] = hashlib.sha256(blob).hexdigest() if blob is not None else None
        return blob

    # Use the existing painter unchanged, recording donors and missing files too.
    tiles, report = web.map_cells.apply(recorded, plan, progress=progress)
    web.MAP_TILES = web.map_cells.Served(web.RES_ROOT, plan, prepared_tiles=tiles)
    manifest = dict(
        version=VERSION, inputs=inputs, sources=sources,
        tiles={name: hashlib.sha256(blob).hexdigest() for name, blob in tiles.items()},
    )
    write_cache(cache, manifest, tiles)
    print('Map cache built: %d tiles; %s' % (len(tiles), '; '.join(report)), flush=True)
    return 'built'
