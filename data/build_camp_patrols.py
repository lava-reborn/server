"""The patrols round the camps: the "patrol" rows of data/placements.json.

DESIGNED, the owner's word of 2026-10-11: «во всех соседних локациях тоже
добавь мобов они там должны быть». Every map label of Вади-Хальфа's four
camps promises them («Центральный лагерь дает максимальный прирост опыта,
тогда как патрули вокруг позволяют окупить затраты»), texts.xml 61881 says
«Патрули расставлены вокруг лагерей», and the lavabook puts four quests of
the camps on the cells next to them. Until now those cells stood empty: a
desert template's <mobs> node holds four-hex nests and no creature
(world.Location reads one bogus spawn there, which rooms.Room drops), and
encounters.near_town keeps every ambush off a cell that touches a camp.

The cells
  A camp's neighbour cells are the open desert touching it or its chief's
  place: the 8-neighbourhood of both, the two places taken out. That is 12
  cells round each camp pair of Вади-Хальфа (80/82, 81/83, 84/86, 85/87)
  and of Абри (88/89, 92/90: the owner's «В Абри добавь мобов в лагеря и
  в окрестности», 2026-10-12, ORDERED) and 8 round the Nubian valley's
  «Лагерь бандитов» (34). A cell is left
  out (and the run says so) where it is a settlement, a place taken out of
  the game (world.retired_cells), the rock of the rim, impassable, or on the
  other side of the valley's wall from its camp. Open desert's location id
  is its packed cell (world.pack), so the rows are keyed by it, as
  rooms.Room asks world.placed_in(loc.id).

Who
  The camp's own fighters: the kinds of data/camp_fill.json for the camp
  and its chief's place, and the hostile kinds the camp's file stands
  itself (the valley camp's 20, 21 and 251), role "mob" only, so no boss,
  no treasurer, no ammunition box. LEFT_OUT keeps two more in the camps:
  the sect's «Неудачник» 336 («Заказ»: «Секта Люшер все кроме
  Неудачников») and the Магриб's officers 303/307/311, who stand only on
  the cell «Порядок (часть 2)» names. On the four cells the lavabook names
  (ANCHORS) stand the kinds its quests name; on every other cell the i-th
  cell of a ring (by row, then column) takes kinds[(i*n + j) % len(kinds)]
  for its j-th slot, so the ring shows the faction's whole range.

Where in the cell
  The original's wasteland tiles MW_000..MW_033 (static 707-714 and
  1299-1323) are the same file family as the chiefs' places, each with
  6-10 empty slots; which tile stood on which cell is lost. The slots of
  MW_023 (static 1319) are the patrol's cells: eight in Вади-Хальфа, four
  of them (SLOTS4) in the valley, so the valley's camp stays the larger
  group. Each is checked here on the cell's own template: on the grid, no
  obstacle, no exit, no nest, nobody's spawn.

Every row carries "patrol": <camp id>. main() drops every such row from
data/placements.json, puts the new ones in, leaves the hand rows alone,
refuses to write a table rooms.placement_problems finds fault with, and
writes the file as it was written before (json, indent 1).

    LAVA_RES=.../res python3 data/build_camp_patrols.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

PATH = os.path.join(HERE, "placements.json")

# camp -> (its chief's place or None, the name the rows give it)
RINGS = {
    80: (82, "Лагерь Новых Колонистов"),
    81: (83, "Лагерь Сектантов Люшеров"),
    84: (86, "Лагерь Джанджавидов"),
    85: (87, "Лагерь Магриба"),
    34: (None, "Лагерь бандитов"),
    88: (89, "Лагерь Работорговцев"),
    92: (90, "Лагерь Живодеров"),
}
# The owner's word each ring answers: Вади-Хальфа's and the valley's, unless
# named here.
ORDERED = {
    88: ("DESIGNED, the owner's (2026-10-12, «Делаем Абри»): «В Абри добавь мобов в "
         "лагеря и в окрестности». "),
    92: ("DESIGNED, the owner's (2026-10-12, «Делаем Абри»): «В Абри добавь мобов в "
         "лагеря и в окрестности». "),
}

# Fighters of a camp that stay in it, with why.
LEFT_OUT = {
    590: "st_Kaznachei, the slave traders' treasurer, who stands in the camp 88 all day "
         "(server/bosses.py ALL_DAY); a boss by role, so no ring takes him anyway",
    591: "zd_Kaznachei, the flayers' treasurer in 92, as 590",
    336: "lu_Looser_lvl2, the sectarian of «Театр жизни»; «Заказ» names the sect "
         "«все кроме Неудачников»",
    303: "mg_Officer_lvl6: the Магриб's officers stand only where «Порядок (часть 2)» "
         "finds them (ANCHORS)",
    307: "mg_Officer_lvl7, as 303",
    311: "mg_Officer_lvl8, as 303",
}

# The cells the lavabook puts a camp's quest on: the kinds the quest names.
ANCHORS = {
    (5970, 1725): (
        (258, 259, 260, 261, 262, 264, 266, 267),
        "The lavabook puts «Учет» and «Раббин аль-Гуд» here («Квест: 5970x1725x0») with "
        "these kinds: the four whose «Учетные записи» «Учет» wants (261, 262, 266, 267) "
        "and the colonists the money bags of «Раббин аль-Гуд» come off (258-266)."),
    (5977, 1727): (
        (271, 272, 273, 274, 276, 277, 278, 279),
        "The lavabook puts «Заказ» here («Выполнение квеста: Окрестности Лагеря Люшер "
        "5977x1727», «Тут в округе куча фанатиков Люшера бегает») with these kinds: the "
        "sect's fighters, «все кроме Неудачников»."),
    (5974, 1738): (
        (287, 289, 291, 293, 295, 296, 297, 298),
        "The lavabook puts «Как слышно?» here («Квест: 5974x1738x0», the ja_ of 287-298) "
        "with these kinds, among them the «Диверсант 5го уровня» (291) «Бандитская "
        "активность» finds «рядом с основным лагерем»."),
    (5992, 1722): (
        (303, 307, 311, 301, 302, 304, 305, 306),
        "The lavabook puts «Порядок (часть 2)» here («Квест: 5992x1722x0») with these "
        "kinds: the officers mg_Officer_lvl6/7/8 (303, 307, 311), who carry «Планы "
        "Магриба», and their soldiers."),
}

# The empty slots of MW_023 (static 1319), in its file's order.
TILE = 1319
SLOTS8 = ((20, 34), (35, 44), (20, 54), (29, 70), (50, 74), (15, 84), (39, 95), (25, 104))
SLOTS4 = ((20, 34), (29, 70), (50, 74), (25, 104))
PER_CELL = {"halfa": 8, "valley": 4}


def _types():
    with io.open(os.path.join(HERE, "mob_types.json"), encoding="utf-8") as fh:
        return {int(k): v for k, v in json.load(fh)["types"].items()}


def _camp_fill():
    with io.open(os.path.join(HERE, "camp_fill.json"), encoding="utf-8") as fh:
        return {int(k): v for k, v in json.load(fh)["fill"].items()}


def fighters(camp, types=None, fill=None):
    """Every hostile kind of role "mob" that stands in the camp or at its
    chief's place: their filled slots and their files' own spawns."""
    types = _types() if types is None else types
    fill = _camp_fill() if fill is None else fill
    chief = RINGS[camp][0]
    out = set()
    for lid in (camp, chief):
        if lid is None:
            continue
        kinds = list((fill.get(lid) or {}).get("types", ()))
        kinds += [t for _c, t in world.location(lid).spawns if t]
        out |= {t for t in kinds if t in types and types[t]["root"] == 0
                and types[t]["role"] == "mob"}
    return out


def kinds(camp, types=None, fill=None):
    """The camp's patrol kinds, in type order."""
    return sorted(fighters(camp, types, fill) - set(LEFT_OUT))


def region(camp):
    return "valley" if world.in_noob_valley(*world.cell_of(camp)) else "halfa"


def ring(camp, said=None):
    """The camp's neighbour cells that can hold a patrol, by row then column.
    said, a list, collects the cells left out with why."""
    chief = RINGS[camp][0]
    places = [world.cell_of(camp)] + ([world.cell_of(chief)] if chief else [])
    inside = region(camp) == "valley"
    found = set()
    for cx, cy in places:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                found.add((cx + dx, cy + dy))
    out = []
    for x, y in sorted(found - set(places), key=lambda c: (c[1], c[0])):
        why = None
        if (x, y) in world.settlements():
            why = "a settlement (%d)" % world.settlements()[(x, y)]
        elif (x, y) in world.retired_cells():
            why = "a place taken out of the game (%d)" % world.retired_cells()[(x, y)]
        elif world.location_at(x, y) != world.pack(x, y):
            why = "no open desert (%d)" % world.location_at(x, y)
        elif not world.passable(x, y):
            why = "impassable"
        elif world.in_noob_valley(x, y) != inside:
            why = "the other side of the valley's wall"
        if why:
            if said is not None:
                said.append("%d: %d,%d left out, %s" % (camp, x, y, why))
            continue
        out.append((x, y))
    return out


def _check_slots(loc, slots):
    import encounters
    import travel
    taken = {c for c, _t in loc.spawns}
    sides = travel.exit_sides(loc)
    nests = set(encounters.nests(loc))
    for x, y in slots:
        c = y * loc.width + x
        assert 0 <= x < loc.width and 0 <= y < loc.height, "%s: %d,%d off the grid" % (loc.file, x, y)
        assert c not in loc.obstacles, "%s: %d,%d on an obstacle" % (loc.file, x, y)
        assert c not in sides, "%s: %d,%d on an exit" % (loc.file, x, y)
        assert c not in taken and c not in nests, "%s: %d,%d on a spawn or a nest" % (loc.file, x, y)


def _why(camp, x, y, loc, pool):
    chief, name = RINGS[camp]
    cx, cy = world.cell_of(camp)
    head = ORDERED.get(camp) or (
        "DESIGNED, the owner's (2026-10-11): «во всех соседних локациях тоже добавь "
        "мобов они там должны быть». ")
    if region(camp) == "valley":
        text = head + (
            "The patrol of the Nubian valley's «%s» (%d on %d,%d) on the neighbour cell %d,%d "
            "(open desert inside the valley's wall, %s); no ambush is met in the valley "
            "(encounters.band_at). Four of the camp's bandits (%s, the fighters its own file "
            "%s stands) on four of the slot cells of the original's wasteland tile MW_023 "
            "(static %d); they come back on the respawn timer like the camp's. Built by "
            "data/build_camp_patrols.py." % (
                name, camp, cx, cy, x, y, loc.file, ", ".join(str(t) for t in pool),
                world.location(camp).fn, TILE))
    else:
        hx, hy = world.cell_of(chief)
        text = head + (
            "The patrol of «%s» (%d on %d,%d, and its chief's place %d on %d,%d) on the "
            "neighbour cell %d,%d (open desert, %s): the camp's map label promises «патрули "
            "вокруг позволяют окупить затраты» (res/database/locations.xml), and "
            "encounters.near_town keeps every ambush off this cell. Eight of the camp's own "
            "fighters (data/camp_fill.json) on the slot cells of the original's wasteland "
            "tile MW_023 (static %d); they come back on the respawn timer like the camp's. "
            "Built by data/build_camp_patrols.py." % (
                name, camp, cx, cy, chief, hx, hy, x, y, loc.file, TILE))
    anchor = ANCHORS.get((x, y))
    if anchor:
        text += " " + anchor[1]
    return text


def rows():
    """{packed cell: [row]}: every patrol row, ring by ring."""
    types, fill = _types(), _camp_fill()
    tile = world.location(TILE)
    assert tile.fn == "MW_023", "static %d is %s" % (TILE, tile.fn)
    assert tuple((c % tile.width, c // tile.width) for c, t in tile.spawns if t == 0) == SLOTS8, \
        "MW_023's empty slots moved"
    assert set(SLOTS4) <= set(SLOTS8)
    out = {}
    seen = {}
    for camp in RINGS:
        pool = kinds(camp, types, fill)
        allowed = fighters(camp, types, fill)
        n = PER_CELL[region(camp)]
        slots = SLOTS8 if n == 8 else SLOTS4
        assert len(slots) == n
        for i, (x, y) in enumerate(ring(camp)):
            assert (x, y) not in seen, "%d,%d is round %d and %d" % (x, y, seen[(x, y)], camp)
            seen[(x, y)] = camp
            key = world.pack(x, y)
            loc = world.location(key)
            assert loc.war, "%d,%d (%s) is at peace" % (x, y, loc.file)
            _check_slots(loc, slots)
            anchor = ANCHORS.get((x, y))
            if anchor:
                picked = list(anchor[0])
                assert len(picked) == n and set(picked) <= allowed, \
                    "the anchor %d,%d names kinds outside %d's fighters" % (x, y, camp)
            else:
                picked = [pool[(i * n + j) % len(pool)] for j in range(n)]
            first = _why(camp, x, y, loc, pool)
            out[key] = [
                dict(type=t, cell=[sx, sy], patrol=camp,
                     why=first if j == 0 else "As the first row of %d (%d,%d)." % (key, x, y))
                for j, (t, (sx, sy)) in enumerate(zip(picked, slots))]
    missing = set(ANCHORS) - set(seen)
    assert not missing, "anchors on no ring: %s" % sorted(missing)
    return out


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main():
    with io.open(PATH, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    doc = json.loads(raw)
    if dump(doc) != raw:
        sys.exit("data/placements.json is not in the builder's format (json, indent 1): "
                 "a rewrite would change more than the patrols")
    kept = {}
    for k, recs in doc["locations"].items():
        hand = [r for r in recs if "patrol" not in r]
        if hand:
            kept[k] = hand
    said = []
    for camp in RINGS:
        ring(camp, said)
    built = rows()
    for key, recs in built.items():
        kept.setdefault(str(key), []).extend(recs)
    doc["locations"] = kept

    import rooms
    table = {int(k): v for k, v in kept.items()}
    problems = rooms.placement_problems(world.mob_types(), table)
    if problems:
        sys.exit("refused, the table cannot stand:\n  " + "\n  ".join(problems))
    with io.open(PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(doc))
    for line in said:
        print(line)
    for camp in RINGS:
        cells = ring(camp)
        print("%d %s: %d cells x %d, kinds %s" % (
            camp, RINGS[camp][1], len(cells), PER_CELL[region(camp)], kinds(camp)))
    print("patrols: %d cells, %d rows; hand rows kept in %s; written to %s" % (
        len(built), sum(len(v) for v in built.values()),
        sorted(k for k, v in kept.items() if any("patrol" not in r for r in v)), PATH))


if __name__ == "__main__":
    main()
