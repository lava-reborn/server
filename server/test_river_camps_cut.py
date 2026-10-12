"""The owner's cut of the camps across the river, 2026-10-12: «убери во всех
городах лагеря за рекой».

Every town on the Nile had one camp of the resistance on the far bank, one
file of the series Invaider_Camp_* each («Лагерь», war 0, the Армия ЦСЦ's
soldiers, traders, an upgrader and the Лазутчик Северного Альянса; the wiki's
«Лагерь сопротивления Север / Центр / Юг»): 429 Вади-Хальфа (5943,1723, in
Заречье), 430 Абри (on the island, never on a cell; the map paints its
square on 5850,1851), 431 Донгола (5864,2002) and 432 Абу-Хамед (its own
cell 6168,1989 across the river; the placer had stood it on 6160,1975, on
the town's bank under the pirates' name). Мероэ and Керма have none. What the
cut is, each part held here (the pattern of server/test_abri_cut.py):

  1. the places: the four files are out of the game (data/retired.json), on
     no cell (data/settlements_verified.json nulls 5943,1723, 5864,2002 and
     6160,1975), and every cell of theirs -- with 6168,1989 and 5850,1851,
     which had a square or a name and no place -- leads into the wasteland;
     the files stay; every place on the towns' banks stays where it was, and
     so do the digs, the ФСЦ's bases, the gorges and the staffs across the
     river; the camp of the Северный Альянс 168 and its base 263 by
     Абу-Хамед are held where they were;
  2. no way in: no door the server follows, no passage, side or quest way,
     no quest's ride and no quest's marker leads into one of them; the boat
     from Причал to 429 and back (412, 413) has lost its ways and stays off;
  3. the people: whoever stood in the camps stood in them alone, gives and
     takes no quest, is no boss, sells nothing anybody else does not, and
     keeps his name in the string table; the camps stood no mob;
  4. the map's names: «Лагерь за рекой» hidden on its three cells, every
     other name around each camp the file's own; the pirates' names stay;
     Донгола's pier, the town's end of the boat to 431, offers no
     «Отправка на фронт» any more, and the men of the Армия ЦСЦ on the
     piers stay there with no quest;
  5. the map's squares: the four camps' green squares and the three captions
     «Лагерь» go (server/map_cells.py), the pirates' square, the digs' and
     the bases' stay -- on the real map when the original's tiles are here;
  6. the town's ground: the cut's cells of data/retired.json are the towns'
     still for the encounters (world.retired_cells);
  7. the database: whoever is in a camp, or calls one home, goes to Причал
     (41, 5965,1728) -- once, by the run_once «retire-river-camps-2026-10-12»;
     the journals stay. On Postgres: server/test_storage_pg.py.

Абри's clothing market 378, cut the same day by the owner's next order, is
server/test_abri_cut.py's (section 8).

    LAVA_RES=.../res python3 server/test_river_camps_cut.py
"""
import glob
import hashlib
import html
import io
import json
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "river_camps_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import bosses  # noqa: E402
import encounters  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import map_cells  # noqa: E402
import map_labels  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import setcraft  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


def load(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


RETIRED = load("retired.json")
VERIFIED = load("settlements_verified.json")
LABELS = load("map_labels.json")["labels"]
MAP_CELLS = load("map_cells.json")
PASSAGES = load("passages.json")
SCHEDULE = load("schedule.json")
LOOT = load("loot_manual.json")
HOLDINGS = load("holdings.json")
ALL_RETIRED = {int(k) for k in RETIRED["places"]}
CUT_WHY = "The owner's cut of the camps across the river, 2026-10-12"
ORDER = "убери во всех городах лагеря за рекой"
# The camps and the cells they stood on; Абри's never had one.
CAMPS = {429: (5943, 1723), 430: None, 431: (5864, 2002), 432: (6160, 1975)}
TOWNS = {429: "Вади-Хальфа", 430: "Абри", 431: "Донгола", 432: "Абу-Хамед"}
FILES = {429: "Invaider_Camp_WH", 430: "Invaider_Camp_Ab", 431: "Invaider_Camp_DN",
         432: "Invaider_Camp_AH"}
# The cells with a square or a name of a camp and no place: Абу-Хамед's camp's
# own cell across the river, Абри's island camp's square.
LABEL_ONLY = [(6168, 1989), (5850, 1851)]
CELLS = [c for c in CAMPS.values() if c] + LABEL_ONLY
# The cells of data/retired.json: not 6160,1975, whose square is the pirates'.
LISTED = {429: (5943, 1723), 431: (5864, 2002)}
PIRATES = [(6160, 1975), (6161, 1973)]
HELD = {(6274, 1952): 168, (6210, 1986): None}
PRICHAL, PRICHAL_CELL = 41, (5965, 1728)
PIER_DN = (5873, 2012)                                  # Причал Донголы 445
PIER_DN_WAS = "Причал Донголы:<BR>Задания.<br>Отправка на фронт.<br>Новогодняя Елка"
PIER_DN_NOW = "Причал Донголы:<BR>Задания.<br>Новогодняя Елка"
BOAT_OUT, BOAT_BACK = 412, 413
ONEILL, DOBERMAN = 5685, 5694
# The towns' banks: the places that stay (FIND.md, the research of 2026-10-12).
BANKS = {
    "Вади-Хальфа": {(5970, 1724): 80, (5971, 1723): 82, (5978, 1727): 81, (5979, 1728): 83,
                    (5974, 1739): 84, (5975, 1738): 86, (5993, 1721): 85, (5992, 1720): 87,
                    (5976, 1720): 137, (5971, 1731): 108, (5972, 1735): 139, (5966, 1728): 52,
                    (5968, 1728): 94, (5969, 1728): 95, PRICHAL_CELL: PRICHAL},
    "Абри": {(5880, 1844): 88, (5881, 1843): 89, (5868, 1854): 92, (5869, 1855): 90,
             (5885, 1836): 220, (5860, 1835): 187, (5861, 1835): 188, (5862, 1835): 255},
    "Донгола": {(5882, 2036): 93, (5883, 2035): 93, (5920, 2010): 98, (5921, 2011): 98,
                (5878, 2011): 73, (5876, 2011): 96, (5877, 2012): 97, (5873, 2012): 445,
                (5878, 2013): 469},
    "Абу-Хамед": {(6274, 1952): 168, (6273, 1953): 263, (6183, 1977): 131, (6183, 1975): 127,
                  (6182, 1977): 446, (6183, 1974): 467},
}
# Across the river, beside the camps: the digs, the ФСЦ's bases (НИЛ-1, 522,
# went on 2026-10-10), the gorges and the evacuation zones.
ACROSS = {(5943, 1722): 433, (5941, 1697): 508, (5850, 1850): 434, (5849, 1851): 523,
          (5844, 1826): 513, (5844, 1831): 502, (5864, 2001): 435, (5863, 2002): 524,
          (5851, 1986): 516, (5851, 1991): 988, (6168, 1988): 436, (6167, 1989): 525,
          (6145, 1993): 517}
MT = world.mob_types()


def standing(loc_id):
    return {t for _cell, t in world.location(loc_id).spawns}


def stood_in(loc_id):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    return sorted({n.type_id for n in room.npcs.values()})


def place_ids(v):
    """A quest row's place field (one id, or a list of them) as a list."""
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v if str(x).lstrip("-").isdigit()]
    return [int(v)] if str(v).lstrip("-").isdigit() else []


files = sorted(int(os.path.basename(p)[:-4])
               for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")))


# --- 1. the places -------------------------------------------------------------------------
print("the places")
try:
    cut = {int(k): v for k, v in RETIRED["places"].items() if v.startswith(CUT_WHY)}
    check("data/retired.json takes out the four camps across the river, each with its why quoting"
          " the order", {i: ORDER in v for i, v in cut.items()}, {i: True for i in CAMPS})
    series = sorted(lid for lid in files if world.location(lid).fn.startswith("Invaider_Camp"))
    check("  ..which are the whole series Invaider_Camp_*, one a town on the Nile: Мероэ and Керма"
          " have none", ({lid: world.location(lid).fn for lid in series}, sorted(CAMPS)),
          (FILES, series))
    check("  ..each a «Лагерь» at peace", {i: (world.location(i).title.strip(), world.location(i).war)
                                           for i in CAMPS}, {i: ("Лагерь", False) for i in CAMPS})
    check("  ..and lists the cells of 429 and 431, the towns' ground still for the encounters;"
          " not 6160,1975, whose square is the pirates'",
          {i: c for c, i in world.retired_cells().items() if i in CAMPS}, LISTED)
    table = world.settlements()
    check("none of them on any cell", [c for c, i in table.items() if i in CAMPS], [])
    check("  ..their three old cells nulled with their why in data/settlements_verified.json",
          {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"), ORDER in VERIFIED["why"].get("%d,%d" % c, ""))
           for i, c in CAMPS.items() if c}, {i: (None, True) for i, c in CAMPS.items() if c})
    check("every cell of theirs leads into the wasteland: the three they stood on, Абу-Хамед's camp's"
          " own across the river and Абри's island camp's square",
          {c: world.location_at(*c) == world.pack(*c) for c in CELLS}, {c: True for c in CELLS})
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in sorted(CAMPS)], [FILES[i] for i in sorted(CAMPS)])
    check("the towns' banks keep every place: Вади-Хальфа's camps, chiefs, bandits and masters,"
          " Абри's camps, Мантикора and market, Донгола's ДСР, Миротворцы, masters, port and market,"
          " Абу-Хамед's Северный Альянс, masters, quarter, port and market",
          {town: {c: table.get(c) for c in cells} for town, cells in BANKS.items()}, BANKS)
    check("  ..and across the river the digs 433-436, the ФСЦ's bases НИЛ-2..4, the gorges and the"
          " evacuation zones stay", {c: table.get(c) for c in ACROSS}, ACROSS)
    check("by Абу-Хамед the camp of the Северный Альянс 168 and «Аванпост Северного Альянса» are held"
          " as they were (432's going would move 168 there): data/settlements_verified.json",
          ({c: table.get(c) for c in HELD},
           {c: VERIFIED["cells"].get("%d,%d" % c, "absent") for c in HELD},
           [bool(VERIFIED["why"].get("%d,%d" % c)) for c in HELD]),
          (HELD, HELD, [True, True]))
    check("  ..and the pirates' two names by Абу-Хамед, where 432 stood, lead into the wasteland as"
          " the second always did; the pirates' camp 132 on no cell, as before",
          ([world.location_at(*c) == world.pack(*c) for c in PIRATES], world.cell_of(132)),
          ([True, True], None))
except Exception:
    import traceback
    fails.append("the places broke:\n" + traceback.format_exc())


# --- 2. no way in --------------------------------------------------------------------------
print("no way in")
try:
    followed = []
    for lid in files:
        for side in "ab":
            rec = travel.door(lid, side)
            if (rec and int(rec.get("target_loc_id") or 0) in CAMPS
                    and rec.get("confidence") in travel.DOOR_CONFIDENCE and lid not in ALL_RETIRED):
                followed.append((lid, side, int(rec["target_loc_id"])))
    check("no door the server follows leads into a camp from a place still in the game", followed, [])
    into = []
    for section in ("doors", "sides", "quest", "walk_in"):
        for key, recs in (PASSAGES.get(section) or {}).items():
            if key.startswith("_"):
                continue
            if isinstance(recs, dict):
                recs = list(recs.values())
            for rec in recs or ():
                if isinstance(rec, dict) and (int(rec.get("target_loc_id") or 0) in CAMPS
                                              or key in {str(i) for i in CAMPS}):
                    into.append((section, key))
    check("no passage, side or quest way of data/passages.json leads into or out of one, none is a"
          " no_map place", (into, sorted({str(i) for i in CAMPS} & set(PASSAGES.get("no_map") or {}))),
          ([], []))
    boat = (quests.get(BOAT_OUT), quests.get(BOAT_BACK))
    check("the boat from Причал to 429 and back has lost its ways and stays off: nobody gives or takes"
          " it, the lieutenant at Причал offers nothing",
          ([travel.is_quest_way(t) for t in (BOAT_OUT, BOAT_BACK)],
           travel.quest_way(world.location(PRICHAL), BOAT_OUT), travel.quest_way(world.location(429), BOAT_BACK),
           [(q.give, q.take) for q in boat], BOAT_OUT in quests.given_by(ONEILL)),
          ([False, False], None, None, [([], []), ([], [])], False))
    check("  ..their rows say why", ["the camps across the river" in (r.get("why") or "")
                                    for r in quests.table_rows() if int(r["type"]) in (BOAT_OUT, BOAT_BACK)],
          [True, True])
    GEO = {world.pack(*c) for c in CELLS}
    rows = quests.table_rows()
    named = sorted({int(r["type"]) for r in rows for key in ("loc", "finish_loc", "rew_loc")
                    if set(place_ids(r.get(key))) & GEO}
                   | {int(r["type"]) for r in rows for key in ("loc_id", "stay_in")
                      if set(place_ids(r.get(key))) & set(CAMPS)}
                   | {int(r["type"]) for r in rows if isinstance(r.get("way"), dict)
                      and int(r["way"].get("target_loc_id") or 0) in CAMPS})
    check("no quest row rides anybody there, sends him there, marks one of the cells, waits or pays"
          " there", named, [])
    check("  ..nor does any quest as the server reads it",
          sorted(t for t, q in quests.QUESTS.items()
                 if {q.loc, q.finish_loc, q.rew_loc} & GEO or set(q.stay_in) & set(CAMPS)), [])
    check("  ..and none of them has a quest way out", [i for i in CAMPS if travel.quest_ways(world.location(i))],
          [])
except Exception:
    import traceback
    fails.append("the ways broke:\n" + traceback.format_exc())


# --- 3. the people -------------------------------------------------------------------------
print("the people")
try:
    put = {}                                          # type -> where it could be put down
    for lid in files:
        try:
            loc = world.location(lid)
        except (KeyError, OSError, AttributeError, ValueError):
            continue
        for _cell, t in loc.spawns:
            put.setdefault(t, set()).add(("file", lid))
        for t in world.camp_fill(lid):
            put.setdefault(t, set()).add(("fill", lid))
    for lid, recs in world.placements().items():
        for rec in recs:
            put.setdefault(int(rec["type"]), set()).add(("placed", int(lid)))
    for rec in events.table().spawns:
        for t in events._types(rec.get("types")):
            put.setdefault(t, set()).add(("window", rec.get("loc")))
    people = {t for lid in CAMPS for t in stood_in(lid)}
    check("the camps stood their people and no mob: two soldiers of the Армия ЦСЦ, three traders, an"
          " upgrader, the Лазутчик Северного Альянса 6960 and AQ000001 7660 each",
          {i: len(stood_in(i)) for i in CAMPS}, {i: 8 for i in CAMPS})
    check("  ..their other spawn types have no row in mobs.xml and no stand-in, so nothing else ever"
          " stood there", sorted({t for i in CAMPS for t in standing(i) if t and t not in people
                                  and (t in MT or world.substitute(t) is not None)}), [])
    check("  ..and no place fills them, no window and no placement stands anybody there",
          ({i: list(world.camp_fill(i)) for i in CAMPS}, sorted(set(world.placements()) & {str(i) for i in CAMPS}
                                                         | set(world.placements()) & set(CAMPS)),
           [r.get("loc") for r in events.table().spawns if r.get("loc") in CAMPS]),
          ({i: [] for i in CAMPS}, [], []))
    elsewhere = {t: sorted(w for w in put.get(t, ()) if w[1] not in ALL_RETIRED) for t in people}
    check("every one of them stood in the camps alone", {t: w for t, w in elsewhere.items() if w}, {})
    check("nobody of them gives or takes a quest, or registers a home",
          {t: (quests.given_by(t), quests.taken_by(t), world.offers_home(t)) for t in sorted(people)
           if quests.given_by(t) or quests.taken_by(t) or world.offers_home(t)}, {})
    check("  ..nor is a boss of the clock, has loot of the owner's, or keeps a site of the clans",
          (sorted(t for t in people if bosses.keeps_hours(t)),
           sorted(t for t in people if str(t) in (LOOT.get("by_type") or {})),
           sorted(k for k, v in HOLDINGS["sites"].items() if v.get("loc") in CAMPS or v.get("boss") in people)),
          ([], [], []))
    scheduled = ({r.get("loc") for key in ("spawns", "held_out") for r in SCHEDULE.get(key, [])}
                 | {lid for key in ("loot", "keep_in") for r in SCHEDULE.get(key, [])
                    for lid in r.get("locs", [])})
    check("  ..and data/schedule.json names no camp: no window stands anybody there or holds anybody"
          " out, no loot or keeping of its own", (len(scheduled) > 5, sorted(set(CAMPS) & scheduled)),
          (True, []))
    check("  ..and their names stay in the string table: an unknown id sends the client to the"
          " login screen", [t for t in sorted(people) if t in MT and not names.known(t)], [])
    check("the upgraders' windows were empty", {t: setcraft.window(t)["in_types"] for t in (7021, 7022, 7023, 7024)},
          {t: [] for t in (7021, 7022, 7023, 7024)})
    traders = sorted(t for t in people if world.entity_root(t, MT[t][0]) == world.TRADER)
    stalls = {(i, t): items.stock_for(t, i) for i in CAMPS for t in traders if t in stood_in(i)}
    check("the traders: Вади-Хальфа's three named, the others' under internal names; Абри's three and"
          " two of Абу-Хамед's with empty stalls",
          (sorted(t for t in traders if not names.ALL.get(t, "").startswith("Npc_")),
           sorted(t for (i, t), s in stalls.items() if not s)),
          ([5705, 5706, 5707], [5708, 5709, 5710, 5714, 5716]))
except Exception:
    import traceback
    fails.append("the people broke:\n" + traceback.format_exc())


# --- 4. the map's names --------------------------------------------------------------------
print("the map's names")
try:
    raw = open(os.path.join(world.RES, "database", "locations.xml"), "rb").read()
    out, _n = map_labels.apply(raw)

    def rows_in(doc, box):
        x0, x1, y0, y1 = box
        got = []
        for m in map_labels.ROW.finditer(doc):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            x, y = int(a["x"]), int(a["y"])
            if x0 <= x <= x1 and y0 <= y <= y1:
                got.append((x, y, html.unescape(a["text"].decode("utf-8"))))
        return got

    HIDDEN = {(5943, 1723): "Лагерь за рекой", (5864, 2002): "Лагерь за рекой",
              (6168, 1989): "Лагерь за рекой"}
    ours = {(e["x"], e["y"]): (e["was"], bool(e.get("hide")), e.get("text")) for e in LABELS
            if e.get("why", "").startswith(CUT_WHY)}
    want_ours = {c: (t, True, None) for c, t in HIDDEN.items()}
    want_ours[PIER_DN] = (PIER_DN_WAS, False, PIER_DN_NOW)
    check("data/map_labels.json hides «Лагерь за рекой» on its three cells, takes «Отправка на"
          " фронт» off Донгола's pier, and edits nothing else for the cut", ours, want_ours)
    EVERYWHERE = (0, 99999, 0, 99999)
    original = [r for r in rows_in(raw, EVERYWHERE) if r[2] == "Лагерь за рекой"]
    if len(original) == 3:
        check("no «Лагерь за рекой» is left on the map, where the original's file had three",
              ([r for r in rows_in(out, EVERYWHERE) if r[2] == "Лагерь за рекой"], sorted(original)),
              ([], sorted((x, y, t) for (x, y), t in HIDDEN.items())))
    else:
        # An installed client's file is the release's, with the names hidden.
        print("  -- %s is not the original's (%d «Лагерь за рекой»): the map's names are held on the"
              " edits alone" % (os.path.join(world.RES, "database", "locations.xml"), len(original)))
    retexts = {(e["x"], e["y"], e["was"]): e["text"] for e in LABELS if "text" in e and not e.get("add")}
    hidden = {(e["x"], e["y"], e["was"]) for e in LABELS if e.get("hide")}
    # the names of places of ours (data/locations), added by the location
    # editor over their own cells, are the owner's
    ours_ids = {i for i in world.overlay_ids() if i >= world.FIRST_NEW_ID}
    added = {(e["x"], e["y"], e["text"]) for e in LABELS if e.get("add")
             and world.settlements().get((e["x"], e["y"])) in ours_ids}
    for camp, (x, y) in ((429, (5943, 1723)), (431, (5864, 2002)), (432, (6168, 1989)), (430, (5850, 1851))):
        box = (x - 8, x + 8, y - 8, y + 8)
        want = [(rx, ry, retexts.get((rx, ry, t), t)) for rx, ry, t in rows_in(raw, box)
                if (rx, ry, t) not in hidden]
        check("  ..around the camp %d (%s) every other name is the file's own, row for row, or its"
              " retext of the owner's (the places of ours aside)" % (camp, TOWNS[camp]),
              [r for r in rows_in(out, box) if r not in added], want)
    pirates = [r for r in rows_in(out, (6160, 6161, 1973, 1975)) if r[2].startswith("Лагерь Пиратов")]
    check("the pirates' two names by Абу-Хамед stay", sorted((x, y) for x, y, _t in pirates), sorted(PIRATES))
    # The town's end of the boats: Донгола's pier 445 named the front its two
    # men of the Армия ЦСЦ sent the player to by boat (5689 and 5690, the
    # original's Майор Картер and Рядовой Хиггинсон; texts 24458-24459: «к
    # месту боевых действий», «об отправке в лагерь сопротивления»), the camp
    # 431. Абу-Хамед's pier 446 (5691 and 5692), Вади-Хальфа's 41 (О'Нилл
    # and Беккет) and Абри's port market (МакКей and Вулси) never named it.
    PIER_BOX = (PIER_DN[0], PIER_DN[0], PIER_DN[1], PIER_DN[1])
    check("Донгола's pier keeps its name, its quests and its tree, without «Отправка на фронт» (an"
          " installed client's file, the release's, may have it so already)",
          ([t for _x, _y, t in rows_in(raw, PIER_BOX)] in ([PIER_DN_WAS], [PIER_DN_NOW]),
           [t for _x, _y, t in rows_in(out, PIER_BOX)]),
          (True, [PIER_DN_NOW]))
    check("  ..so no name on the map offers the front any more",
          [(x, y) for x, y, t in rows_in(out, EVERYWHERE) if "фронт" in t.lower()], [])
    for lid, crew in ((445, (5689, 5690)), (446, (5691, 5692)), (PRICHAL, (ONEILL, ONEILL + 1))):
        check("  ..the two men of the Армия ЦСЦ on the pier %d stay there, with no quest to give or"
              " take" % lid,
              (sorted(set(crew) & set(stood_in(lid))),
               {t: (quests.given_by(t), quests.taken_by(t)) for t in crew
                if quests.given_by(t) or quests.taken_by(t)}),
              (sorted(crew), {}))
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())


# --- 5. the map's squares ------------------------------------------------------------------
print("the map's squares")
try:
    plan = map_cells.load()
    check("server/map_cells.py paints over the camps' squares: 429's and 431's by data/retired.json,"
          " Абу-Хамед's camp's own and Абри's island camp's by data/map_cells.json",
          sorted(c for c in CELLS if c in plan.cells), sorted(c for c in CELLS if c != (6160, 1975)))
    check("  ..and not the pirates' squares, the digs' or the ФСЦ's bases'",
          sorted(c for c in PIRATES + [c for c, i in ACROSS.items()] if c in plan.cells), [])
    camps_caps = [(b, map_cells.tile_of(b[0], b[1])) for b, was, why in plan.captions if was == "Лагерь"]
    check("  ..and the three captions «Лагерь» right of the squares of Вади-Хальфа's, Абри's and Донгола's"
          " camps, each its line and the tail of its «р»",
          sorted({n for _b, n in camps_caps}), [13753, 14774, 16055])
    base = {}
    with io.open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3:
                base[parts[2]] = parts[0]
    read = map_cells.reader(world.RES)
    tiles = sorted({map_cells.tile_of(8 * x + 4, 8 * y + 4) for x, y in CELLS + PIRATES}
                   | {n for _b, n in camps_caps})
    have = {n: read(map_cells.tile_path(n)) for n in tiles}
    if all(have.values()) and all(hashlib.sha256(d).hexdigest() == base.get(map_cells.tile_path(n))
                                  for n, d in have.items()):
        new, _report = map_cells.apply(read, plan)
        before = map_cells.Squares(map_cells.Canvas(read))
        after = map_cells.Squares(map_cells.Canvas(lambda p: new.get(p) or read(p)))
        check("on the real map each camp's green square is found, and gone after",
              {c: ((before.at(*c) or (0, 0, None))[2], after.at(*c)) for c in CELLS if c != (6160, 1975)},
              {c: (("green",), None) for c in CELLS if c != (6160, 1975)})
        check("  ..the pirates' dark red squares, the digs' and the bases' where they were, as they were",
              [c for c in PIRATES + list(ACROSS) if before.at(*c) and after.at(*c) != before.at(*c)], [])
    else:
        print("  -- not the original's tiles under %s: the real map is test_map_cells' (with them)"
              % world.RES)
except Exception:
    import traceback
    fails.append("the squares broke:\n" + traceback.format_exc())


# --- 6. the town's ground --------------------------------------------------------------------
print("the town's ground")
try:
    check("no ambush on the cut's listed cells, nor beside them: the towns' ground still",
          [(x + dx, y + dy) for x, y in LISTED.values() for dx in (-1, 0, 1) for dy in (-1, 0, 1)
           if encounters.band_at(x + dx + 0.5, y + dy + 0.5) is not None], [])
    check("  ..and none on the other cells of the camps either (no region of the encounters reaches"
          " Донгола, Абу-Хамед or the island)",
          [c for c in CELLS if encounters.band_at(c[0] + 0.5, c[1] + 0.5) is not None], [])
except Exception:
    import traceback
    fails.append("the ground broke:\n" + traceback.format_exc())


# --- 7. the database -----------------------------------------------------------------------
print("the database")


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


try:
    check("the run_once's places are the four camps, Причал on its cell its target, its name new",
          (sorted(accounts.RIVER_CAMPS), accounts.RETIRED_PLACES_TO,
           accounts.RIVER_CAMPS_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                            accounts.HALFA_FSC_FIX, accounts.ABRI_CUT_FIX,
                                            accounts.ABRI_CLOTHES_FIX, accounts.PREMIUM_THINGS_FIX)),
          (sorted(CAMPS), (PRICHAL,) + world.cell_of(PRICHAL), True))
    path = os.path.join(tempfile.mkdtemp(), "river.db")
    st = accounts.Store(path)
    acc, _ = st.register("river", "secret")
    ids = {}
    for name, loc, home in (("in429", 429, None), ("in430", 430, None), ("in431", 431, None),
                            ("in432", 432, None), ("home429", 433, 429), ("home432", 127, 432),
                            ("in433", 433, None), ("in522", 522, None), ("pier", PRICHAL, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5943, gy = 1723,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5943, home_gy = 1723"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in429"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.RIVER_CAMPS_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    moved = ("in429", "in430", "in431", "in432")
    check("whoever was in a camp is at Причал, on its cell, off the map, with no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in moved}, {n: (PRICHAL, 5965, 1728, 0, None) for n in moved})
    check("  ..a home in 429 or 432 is Причал now, the character left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home429", "home432")],
          [(PRICHAL, 5965, 1728, 433), (PRICHAL, 5965, 1728, 127)])
    check("  ..the one at the dig 433, the one in 522 (the cut of the ФСЦ's, run long ago) and the one"
          " at Причал untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in433", "in522", "pier")],
          [(433, 77), (522, 77), (PRICHAL, 77)])
    check("the journal is untouched", sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..and the log says so: four moved, two homes",
          [ln for ln in lines.lines if accounts.RIVER_CAMPS_FIX in ln
           and "4 character(s) moved out of 429/430/431/432" in ln and "2 home(s) moved" in ln] != [],
          True)
    check("  ..nothing left to do on a second pass", accounts.relocate_river_camps(st.db),
          dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 429 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.RIVER_CAMPS_FIX)), (429, True))
    st.close()
except Exception:
    import traceback
    fails.append("the database broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("river camps cut OK")
