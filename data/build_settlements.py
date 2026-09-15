"""Rebuild data/settlements.json: which map cell holds which location.

The table the original server used is gone, and the client never had it: it
is told the location id in lcall and looks no further. What the client does
still carry is res/database/locations.xml, the 414 tooltips the global map
draws when a cell is hovered, and the title attribute of all 1381 files in
res/locations/static. Where a tooltip's first line names exactly one location
title, the pairing is unambiguous and that is the cell's settlement.

Nothing is guessed here. Titles shared by several files (there are six camps
called "Лагерь мастеров", one per region) are left out rather than resolved by
coin toss, and so is every tooltip that names no location at all -- most of
the 414 are clan territory markers like "Собственность клана СМЕРШ", which
mark ownership of open desert and never had a location behind them.

Cells left out are not lost: the client resolves any cell with no settlement
to a desert tile by itself, so they stay walkable.

    python3 data/build_settlements.py
"""
import collections
import html
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world

# Titles too generic to identify anything: the desert tiles and the border
# rocks carry them too, so a tooltip saying "Пустошь" means open wasteland,
# not a particular file.
GENERIC = {"пустошь", "скалы", ""}


def norm(s):
    """Compare names the way a reader would, not the way the files spell them.

    The two sources disagree on ё, on case and on punctuation: the map says
    "Чёрный рынок" where the location file says "Черный рынок Вади-Хальфы".
    """
    s = html.unescape(s).lower().replace("ё", "е")
    s = re.sub(r"<[^>]*>", " ", s)
    return re.sub(r"[^а-яa-z0-9 ]+", " ", s).strip()


# How far a neighbouring settlement still counts as the same region. The map
# spans 5833..6305 by 1600..2110, so 25 cells is a locality, not a continent.
REGION_RADIUS = 25


def region_words(title):
    """The parts of a title that name a place rather than describe it."""
    return {w for w in title.split() if len(w) > 3}


def read(path, limit=None):
    with io.open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read() if limit is None else fh.read(limit)


def titles():
    d = os.path.join(world.RES, "locations", "static")
    out = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".xml"):
            continue
        m = re.search(r'title="([^"]*)"', read(os.path.join(d, fn), 400))
        if m:
            out[int(fn[:-4])] = norm(m.group(1))
    return out


def tooltips():
    txt = read(os.path.join(world.RES, "database", "locations.xml"))
    return [(int(x), int(y), t) for x, y, t in
            re.findall(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt)]


def main():
    tl = titles()
    by_title = collections.defaultdict(list)
    for i, t in tl.items():
        if t not in GENERIC:
            by_title[t].append(i)

    table, pending, skipped = {}, [], collections.Counter()
    for x, y, raw in tooltips():
        # Only the first line names the place; the rest lists what it offers.
        head = norm(re.split(r"<[Bb][Rr]>|\n|:", html.unescape(raw))[0])
        if head in GENERIC:
            skipped["открытая пустошь"] += 1
            continue
        hits = by_title.get(head)
        if hits is None:
            # The map often shortens: "Чёрный рынок" for "Черный рынок
            # Вади-Хальфы". Accept that only while it still points at one file.
            hits = [i for i, t in tl.items()
                    if t not in GENERIC and (t.startswith(head)
                                             or head.startswith(t))]
        if len(hits) == 1:
            table[(x, y)] = hits[0]
        elif hits:
            pending.append((x, y, hits))
        else:
            skipped["не локация"] += 1

    # A second pass for the names that point at several files, settled by the
    # region rather than by a coin toss. Locations carry their region in the
    # title -- "Черный рынок Вади-Хальфы" against "Черный рынок Донголы" --
    # and so do their neighbours, so the candidate sharing a word with the
    # places already pinned nearby is the one standing on this cell. Only a
    # clear winner counts. This is what recovers both black markets, and it
    # reproduced on its own the single cell already confirmed by playing on it.
    for x, y, hits in pending:
        near = collections.Counter()
        for (cx, cy), i in table.items():
            if abs(cx - x) <= REGION_RADIUS and abs(cy - y) <= REGION_RADIUS:
                near.update(region_words(tl[i]))
        ranked = sorted(((sum(near[w] for w in region_words(tl[i])), i)
                         for i in hits), reverse=True)
        if ranked[0][0] > 0 and (len(ranked) == 1
                                 or ranked[0][0] > ranked[1][0]):
            table[(x, y)] = ranked[0][1]
        else:
            skipped["название не уникально"] += 1

    table = {"%d,%d" % k: v for k, v in table.items()}

    out = os.path.join(HERE, "settlements.json")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"cells": dict(sorted(table.items()))}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("привязано клеток: %d" % len(table))
    for k, v in skipped.most_common():
        print("  пропущено, %-22s %d" % (k, v))
    print("записано в %s" % out)


if __name__ == "__main__":
    main()
