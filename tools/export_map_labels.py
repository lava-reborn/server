#!/usr/bin/env python3
"""Write the launcher's copy of data/map_labels.json (see server/map_labels.py).

    python3 tools/export_map_labels.py -o dist/.build/map_labels.txt
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import map_labels  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    text = map_labels.export_rules()
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("%s: %d edits" % (args.out, len(map_labels.load())))


if __name__ == "__main__":
    main()
