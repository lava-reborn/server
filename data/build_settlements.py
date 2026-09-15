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

BR = "<[Bb][Rr]>|" + chr(10) + "|:"
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


# Cells a settlement may legitimately span. Two neighbouring cells leading
# into the same file is a wide settlement; the same file claimed from opposite
# ends of the map is a name shared by places that are not the same place.
ADJACENT = 3

# A word has to be rare across the 1381 file names before it says anything
# about where a file belongs. "Camp", "old" and "new" appear everywhere and
# mean nothing; "WH", "Domination", "Kerma" appear in one region only.
RARE = 20


def static_meta():
    """id -> (normalised title, internal file name).

    The file name is not decoration. It carries the region a file was built
    for -- WH_Gold_Traders_old, DN_Gold_Traders_old, Q_Domination_A3 -- which
    is the only thing left that can tell two identically titled places apart,
    and it marks the test files that were never places at all.
    """
    d = os.path.join(world.RES, "locations", "static")
    out = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".xml"):
            continue
        m = re.search(r"<location([^>]*)>", read(os.path.join(d, fn), 600))
        if not m:
            continue
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        out[int(fn[:-4])] = (norm(attrs.get("title", "")), attrs.get("fn", ""))
    return out


def tokens(fn):
    return {w.lower() for w in re.split(r"[^A-Za-z]+", fn) if len(w) > 1}


def is_test(fn):
    """Files that were scratch work, not places on any map."""
    return "test" in tokens(fn)


def tooltips():
    txt = read(os.path.join(world.RES, "database", "locations.xml"))
    return [(int(x), int(y), t) for x, y, t in
            re.findall(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt)]


def verified():
    """Cells confirmed by playing on them, which no rule may overrule."""
    path = os.path.join(HERE, "settlements_verified.json")
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)["cells"]
    except (OSError, ValueError, KeyError):
        return {}


def main():
    meta = static_meta()
    tl = {i: t for i, (t, _fn) in meta.items()}

    # Scratch files were never anywhere, and one of them, KB_TESTCLAN_Block_Post,
    # is titled "Кладбище" -- a title generic enough that it was claiming six
    # cells scattered across the whole map.
    usable = {i for i, (_t, fn) in meta.items() if not is_test(fn)}

    freq = collections.Counter()
    for i in usable:
        freq.update(tokens(meta[i][1]))
    rare = {w for w, n in freq.items() if n <= RARE}

    def marks(i):
        """The words in a file name that say which region it belongs to."""
        return tokens(meta[i][1]) & rare

    by_title = collections.defaultdict(list)
    for i in usable:
        if tl[i] not in GENERIC:
            by_title[tl[i]].append(i)

    table, pending, skipped = {}, [], collections.Counter()
    for x, y, raw in tooltips():
        # Only the first line names the place; the rest lists what it offers.
        head = norm(re.split(BR, html.unescape(raw))[0])
        if head in GENERIC:
            skipped["открытая пустошь"] += 1
            continue
        hits = by_title.get(head)
        if hits is None:
            # The map often shortens: "Чёрный рынок" for "Черный рынок
            # Вади-Хальфы". Accept that only while it still points at one file.
            hits = [i for i in usable
                    if tl[i] not in GENERIC and (tl[i].startswith(head)
                                                 or head.startswith(tl[i]))]
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

    # A third pass, for one file claimed from several places at once. Titles
    # like "Причал" or "Мясники" are reused up and down the map, so matching
    # them pins the same file to cells hundreds apart, and at most one of those
    # can be where it stands. Neighbouring cells are left alone: a settlement
    # is allowed to be wider than one cell.
    #
    # The file name decides which one. It carries the region it was built for,
    # so the cell whose already-pinned neighbours share rare words with it --
    # VH_Butchers among the Q_VH_* around Вади-Хальфа -- is the real one, and
    # the rest are the name being reused elsewhere.
    claims = collections.defaultdict(list)
    for cell, i in table.items():
        claims[i].append(cell)
    for i, cells in claims.items():
        if len(cells) == 1:
            continue
        spread = max(abs(a[0] - b[0]) + abs(a[1] - b[1])
                     for a in cells for b in cells)
        if spread <= ADJACENT:
            continue
        scored = []
        for x, y in cells:
            near = collections.Counter()
            for (cx, cy), j in table.items():
                if j != i and abs(cx - x) <= REGION_RADIUS                         and abs(cy - y) <= REGION_RADIUS:
                    near.update(marks(j))
            scored.append((sum(near[w] for w in marks(i)), (x, y)))
        scored.sort(reverse=True)
        keep = scored[0][1] if scored[0][0] > 0 and (
            len(scored) == 1 or scored[0][0] > scored[1][0]) else None
        for _score, cell in scored:
            if cell != keep:
                del table[cell]
                skipped["название переиспользовано"] += 1

    table = {"%d,%d" % k: v for k, v in table.items()}

    # Anything confirmed by standing on it outranks anything worked out from
    # the files, and survives a rebuild. A null there deletes a binding: the
    # cell goes back to being open desert, which is what a wrong settlement
    # should become rather than staying wrong.
    fixed = verified()
    for cell, loc_id in fixed.items():
        if loc_id is None:
            if table.pop(cell, None) is not None:
                skipped["снято проверкой"] += 1
        else:
            table[cell] = loc_id
    if fixed:
        print("проверенных игрой: %d" % len(fixed))

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
