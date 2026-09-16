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
        out[int(fn[:-4])] = dict(
            title=norm(attrs.get("title", "")),
            fn=attrs.get("fn", ""),
            # Background and library together identify the place itself: two
            # files drawing the same art from the same library are one place.
            place=(attrs.get("bg", ""), attrs.get("library", "")),
            war=int(attrs.get("war", 0) or 0))
    return out


# How much of a word to keep when comparing. The two sources decline
# differently and order differently -- the map says "Вокзал Вади-Хальфы" where
# the file says "Вади Хальфа: вокзал" -- so words are cut to a stem and
# compared as a set. Equality only: a subset would start inventing matches
# between "Старый рынок" and "Новый рынок".
STEM = 5


def stems(title):
    return frozenset(w[:STEM] for w in title.split() if len(w) > 2)


def tokens(fn):
    """Words of a file name, with w folded into v.

    Cyrillic В was transliterated both ways by whoever named the files, so the
    same settlement is Vadihalfa3 in one and NY_Wadihalfa_port_old in another.
    Left alone, those two never look like the same region.
    """
    return {w.lower().replace("w", "v")
            for w in re.split(r"[^A-Za-z]+", fn) if len(w) > 1}


def is_test(fn):
    """Files that were scratch work, not places on any map.

    Matched inside a word, not as a whole one: the worst offender is spelled
    KB_TESTCLAN_Block_Post, and being titled "Кладбище" -- a word generic
    enough to appear all over the map -- it had claimed six scattered cells.
    All 25 files carrying "test" anywhere in the name are of that kind.
    """
    return any("test" in w for w in tokens(fn))


def collapse(hits, meta):
    """Fold candidates that are one place with two sets of rules.

    A settlement usually ships twice: Vadihalfa3 and Night_WH_Rail are the
    same background drawn from the same library, differing only in war, which
    decides whether walking costs action points and whether players may shoot
    each other. The names gave nothing away -- fn spells the pair Night_, NY_
    or nothing at all -- but the background and library say it outright.

    Where every candidate is the same place, the peaceful file is the one the
    map leads into. Where they are not, nothing is folded and the caller is
    left with a genuine ambiguity.
    """
    if len({meta[i]["place"] for i in hits}) != 1:
        return hits
    calm = [i for i in hits if not meta[i]["war"]]
    return calm or hits


def tooltips():
    txt = read(os.path.join(world.RES, "database", "locations.xml"))
    return [(int(x), int(y), t) for x, y, t in
            re.findall(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt)]


# Words that name a kind of place rather than a place, so sharing one of them
# is no evidence that two names mean the same spot.
GENERIC_WORDS = {"лагер", "база", "посел", "дерев", "оазис", "рынок", "лавка",
                 "ферма", "пещер", "дорог", "пост"}


def wiki_claims():
    """Cells the wiki points at, from data/settlements_wiki.json.

    The wiki gives every NPC and location article a map coordinate, which
    data/build_exits.py turned into claims per cell: which files the
    articles standing there could mean, with a confidence. City coordinates
    on the wiki are coarse -- every stall of the black market is written as
    one cell -- so the claims are evidence to weigh, not a table to copy.
    """
    path = os.path.join(HERE, "settlements_wiki.json")
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)["cells"]
    except (OSError, ValueError, KeyError):
        return {}


def weigh_wiki(cell, rec, head, tl):
    """One file the wiki claims for a free cell, or None.

    A single candidate is taken at medium confidence or better. Where
    articles disagree -- the black market's stalls are all written on the
    old market's cell -- the file with at least two thirds of the votes
    wins. A low-confidence single candidate counts only when the map's own
    tooltip and the file's title share a word that names the place rather
    than its kind: "Лагерь Новых Колонистов" against "Лагерь Новые
    Колонисты" yes, "Лагерь Люшер" against the same file no.
    """
    votes = collections.Counter()
    for claim in rec.get("claims", []):
        ids = claim.get("loc_ids", [])
        if len(ids) == 1:
            votes[ids[0]] += 1
        # A location article named exactly as the map's own tooltip is the
        # place itself, whatever the NPC articles around it say: the black
        # market's stalls are all written on the old market's cell, but the
        # article "Старый рынок Вади-Хальфы" is the old market's.
        src = claim.get("source", "")
        if (len(ids) == 1 and src.startswith("location:") and head
                and stems(norm(src[len("location:"):])) == stems(head)):
            return ids[0]
    if not votes:
        return None
    best, n = votes.most_common(1)[0]
    total = sum(votes.values())
    conf = rec.get("confidence")
    if len(votes) > 1:
        return best if n * 3 >= total * 2 and conf != "low" else None
    if conf in ("verified", "high", "medium"):
        return best
    if conf == "low" and head and best in tl:
        shared = (stems(head) & stems(tl[best])) - {w for w in stems(head)
                                                   if w[:5] in GENERIC_WORDS}
        return best if shared else None
    return None


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
    tl = {i: m["title"] for i, m in meta.items()}

    # Scratch files were never anywhere, and one of them, KB_TESTCLAN_Block_Post,
    # is titled "Кладбище" -- a title generic enough that it was claiming six
    # cells scattered across the whole map.
    usable = {i for i, m in meta.items() if not is_test(m["fn"])}

    freq = collections.Counter()
    for i in usable:
        freq.update(tokens(meta[i]["fn"]))
    rare = {w for w, n in freq.items() if n <= RARE}

    def marks(i):
        """The words in a file name that say which region it belongs to."""
        return tokens(meta[i]["fn"]) & rare

    by_title = collections.defaultdict(list)
    by_stem = collections.defaultdict(list)
    for i in usable:
        if tl[i] not in GENERIC:
            by_title[tl[i]].append(i)
            by_stem[stems(tl[i])].append(i)

    def candidates(head):
        """Files this tooltip could name.

        Three ways of reading the same name, taken together: the title as
        written, the same words in another order or case, and the shortening
        the map likes -- "Чёрный рынок" for "Черный рынок Вади-Хальфы". They
        are unioned rather than tried in turn, because the docks match one way
        as "Вади Хальфа: Причал" and another as "Причал", and those two files
        are the same place. Collapsing settles that; a name that really does
        belong to several places stays ambiguous and is dropped later.
        """
        hits = set(by_title.get(head, ()))
        hits |= set(by_stem.get(stems(head), ()))
        hits |= {i for i in usable
                 if tl[i] not in GENERIC and (tl[i].startswith(head)
                                              or head.startswith(tl[i]))}
        return collapse(sorted(hits), meta)

    table, pending, skipped = {}, [], collections.Counter()
    for x, y, raw in tooltips():
        # Only the first line names the place; the rest lists what it offers.
        head = norm(re.split(BR, html.unescape(raw))[0])
        if head in GENERIC:
            skipped["открытая пустошь"] += 1
            continue
        hits = candidates(head)
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

    # Fourth, the wiki's coordinates, for cells the names left free.
    heads = {}
    for x, y, raw in tooltips():
        heads[(x, y)] = norm(re.split(BR, html.unescape(raw))[0])
    RANK = {"verified": 3, "high": 2, "medium": 1}
    claims = sorted(wiki_claims().items(),
                    key=lambda kv: (-RANK.get(kv[1].get("confidence"), 0),
                                    -int(kv[1].get("votes", 0) or 0)))
    for cell, rec in claims:
        gx, gy = (int(v) for v in cell.split(","))
        if (gx, gy) in table:
            continue
        pick = weigh_wiki((gx, gy), rec, heads.get((gx, gy), ""), tl)
        if pick is None or pick not in usable:
            continue
        # The wiki writes a whole town on one or two cells, so the same
        # file turns up wherever its NPCs are listed. A file already
        # standing further than a settlement is wide stays where it is.
        far = [c for c, i in table.items() if i == pick
               and abs(c[0] - gx) + abs(c[1] - gy) > ADJACENT]
        if far:
            skipped["вики: файл уже стоит в другом месте"] += 1
            continue
        table[(gx, gy)] = pick
        skipped["добавлено по вики"] += 1

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
