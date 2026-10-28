"""The shards' impact maps as one: the map a pull request's run picks its
suites by (tools/suite.py --affected).

    python3 deploy/ci/merge_maps.py OUT MAP...

Each shard of a push to main runs its part with --record-map and leaves a
tools/impact_map.json with its own suites only (tools/suite.py save_map);
the suites job puts them together here and keeps the result in the Actions
cache, where the next pull request's assets job finds it. A suite in two
maps would mean two shards ran it, which merge_shards.sh already fails on;
here the later one simply wins.
"""
import json
import sys


def main():
    out, maps = sys.argv[1], sys.argv[2:]
    merged = {"suites": {}}
    for path in maps:
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
        merged["suites"].update(m.get("suites", {}))
        for k in ("commit", "recorded"):
            if m.get(k):
                merged[k] = m[k]
    if not merged["suites"]:
        print("merge_maps: no suites in %s" % " ".join(maps), file=sys.stderr)
        return 1
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=0)
    print("map: %d suites from %d shards" % (len(merged["suites"]), len(maps)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
