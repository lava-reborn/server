"""Вади-Хальфа's weapon craft (the plan's stage 0.3, «рецепты улучшения,
мастерские, разборка, заточка, Квартал ремесленников»): the recipes of the
generic generator (data/build_weaponcraft.py -> data/questgen_weaponcraft.json,
server/craft.py), the blueprints' stalls and drops, the gunsmiths' salvage
and assembly, the whetstones, the decoder, and the way into the quarter
behind the owner's wall.

In process: the generator's band filter (Вади-Хальфа's rows inside 0-8, and
the same code given another city's band returns that band's rows), a row's
type kept by its key across rebuilds, no premium thing anywhere, every
recipe a gun into its own modification that no recipe asks for, the
blueprints dropping only off the camps of their own level and one a corpse
at most, the stalls' stock (every whetstone's knife and blueprint on sale in
its town), the modified guns' frames, the salvage (each class's levels
holding a gun its bench takes), knife, assembly (each part drawn by a
salvage row) and decode rows, the ways 414/415 switched off with the
premium masters' camp 124 they started from (the owner's cut of (P),
2026-09-30). On a socket: a recipe walked
(gun + blueprint -> Mod) and the upgraded gun refused a second time, the
upgrader's window at Жозеф де Гобино (62) turning the very gun dragged in,
refusing what came out and refusing once the player has left, a broken
pistol taken apart at the gunsmith's bench (the unbroken one refused; the
cheapest first, never a gold or modified one), a rifle of the 6th level and
a sub-machine gun of the 8th on their benches of the 1st class, a knife
sharpened, a blueprint decoded, a gun assembled, the quarter's [Q]
upgrader in the Квартал ремесленников (reached by an admin's /goto, the
way in being gone), and the wear an upgrade keeps: a broken gun
handed in comes out a broken modification (its rounds back in the bag), a
worn one in the window a worn one, a worn knife sharpened a worn sharp one
(in process too: at the gun's price, never a share of the ceiling more).

    LAVA_RES=.../lava/res python3 server/test_halfa_weaponcraft.py
"""
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import setcraft  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


BAND = (0, 8)
MASTERS = {338: ("pistol", "A"), 377: ("pistol", "G"), 339: ("shotgun", "A"),
           378: ("shotgun", "G"), 341: ("rifle", "A"), 380: ("rifle", "G")}
Q_MASTERS = [5771, 7548]
RAKIN = 7311
GUNSMITHS = {"rifle": 238, "shotgun": 239, "pistol": 242, "smg": 243}
WHETSTONES = {5192: (2, 4), 2279: (2, 4, 6, 8), 2280: (10, 12)}
ABRI_WHETSTONE, ABRI_KNIVES, ABRI_PORT = 2280, 1164, 187     # Абри's (2026-10-12)
DECODER = 652
# The blueprints' stalls. The premium masters 702, 704 and 705, whose stalls
# repeated these, stand nowhere since the owner's cut of (P) (2026-09-30,
# data/retired.json), and their lists are gone from data/npcs.json.
STALLS = {"shotgun": (576, 7309), "rifle": (578, 7310), "smg": (7311,)}
Q_STALL = 5770
CAMPS = [((0, 2), (80, 82)), ((3, 4), (81, 83)), ((5, 6), (84, 86)), ((7, 8), (85, 87))]
WAY_IN, WAY_OUT = 414, 415
MASTERS_CAMP, QUARTER, OASIS, BLACK_MARKET, SMITHS, CRAFTSMEN_I = 124, 447, 62, 102, 599, 94
AZAM_P, QUARTER_MASTER, JOSEPH = 704, 5771, 7548
ITZHAK, PISTOL_SMITH, WHETSTONE = 338, 242, 2279
BERETTA, BERETTA_DAMAGE, DAMAGE_2 = 25586, 25589, 717
MAUSER_Q, MAUSER_PRECISION, PRECISION_2 = 25666, 43546, 723
TESAK_G, TESAK_SHARP, SHARPEN_6 = 6241, 6242, 6614
NAGAN = 25566                     # Наган 1895, a pistol of the 1st level: class 2 (the
                                  # starter pistol, Самострел, is in the hands)
BERETTA_G = 25587                 # Беретта 92 (G), bought for gold
RIFLE_6, SMG_8 = 25671, 25341     # Самодельная винтовка, Кустарный ПП: class 1
CODIFIED_2 = 1131
PORT_MARKET, SHOTGUN_STALL = 104, 576
GOLD_BP_5 = 37665                 # bpg_damage_25_gold_lvl5: the gold line's, gold alone

with open(os.path.join(DATA, "questgen_weaponcraft.json"), encoding="utf-8") as fh:
    DOC = json.load(fh)
ROWS = DOC["quests"]
CRAFT = {r["type"]: r["craft"] for r in ROWS}


def city_of(r):
    """The city a row was written for, off its key (build_weaponcraft.row_key)."""
    return r["craft"]["key"].split(":")[1]


# The cities after Абри, each with its own suite: Донгола's rows (2026-10-13, its
# band 9-16, its own masters, stalls, gunsmiths, decoder and whetstone) are
# server/test_dongola_trade.py's, Абу-Хамед's (2026-10-14, its band 17-20)
# server/test_abuhamed_trade.py's.
LATER = ("dongola", "abu_hamed")


def family(name):
    """A family's rows of the cities before Донгола (LATER)."""
    return [r for r in ROWS if r["craft"]["family"] == name and city_of(r) not in LATER]


def things(r):
    return [o["obj"] for o in r.get("objs", [])] + list(r.get("rew_obj", [])) + \
        [o["obj"] for o in r.get("rew_random", [])]


def stood(loc_id):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), world.mob_types())
    return {npc[1] for npc in room.npcs.values()}


# --- in process: the table ----------------------------------------------------------------
try:
    check("blueprint upgrades and decoding stay open through level 20; other craft services keep Вади-Хальфа's band (or the valley's"
          " 0-4 at its whetstone, Абри's 6-20 at its own, Донгола's 9-16 since 2026-10-13,"
          " Абу-Хамед's 17-20 since 2026-10-14) in 10000-10999, of the loaded table",
          sorted({(r["repeatable"], r["service"], r["level"], r["max_level"],
                   10000 <= r["type"] <= 10999, quests.get(r["type"]) is not None)
                  for r in ROWS}),
          [(1, True, 0, 4, True, True), (1, True, 0, 8, True, True), (1, True, 0, 20, True, True),
           (1, True, 6, 20, True, True), (1, True, 9, 16, True, True), (1, True, 9, 20, True, True),
           (1, True, 17, 20, True, True)])
    check("  ..Abri keeps its existing whetstone recipes, now for player levels 6-20",
          sorted({(r["craft"]["family"], tuple(r["give"])) for r in ROWS
                  if city_of(r) == "abri"}),
          [("knife", (ABRI_WHETSTONE,))])
    check("  ..the families", {f: len(family(f)) for f in
                               ("upgrade", "knife", "salvage", "assembly", "decode")},
          {"upgrade": 132, "knife": 18, "salvage": 10, "assembly": 19, "decode": 8})
    check("  ..each row's type the one its key was given (the table's \"types\"), no type"
          " given twice",
          ([r["type"] for r in ROWS if DOC["types"].get(r["craft"]["key"]) != r["type"]],
           len(set(DOC["types"].values())) == len(DOC["types"])), ([], True))
    check("  ..every thing a row names is one the game has (quests.check_items), no quest"
          " string or item name off the preload",
          (quests.check_items(),
           [r["type"] for r in ROWS if not all(names.known(i) for i in
                                               quests.get(r["type"]).string_ids())],
           sorted({t for r in ROWS for t in things(r)
                   if not names.known(items.STRING_ID_OFFSET + t)})), (None, [], []))
    check("no premium thing in any row, stall or prize", sorted({t for r in ROWS for t in things(r)
                                                                 if items.premium(t)}), [])
    ups = family("upgrade")
    check("the recipes' guns are of the band, A and G lines, but the (Q) Маузер C96 of"
          " «Веселый праздник»; each at the master of its class and line",
          (sorted({r["craft"]["line"] for r in ups}),
           [r["type"] for r in ups if not BAND[0] <= r["craft"]["level"] <= BAND[1]],
           [r["type"] for r in ups if r["craft"]["line"] in "AG" and r["give"] != [RAKIN]
            and MASTERS.get(r["give"][0]) != (craft.weapon_of(r["craft"]["gun"]),
                                              r["craft"]["line"])],
           sorted({t for r in ups if r["craft"]["line"] == "Q" for t in r["give"]})),
          (["A", "G", "Q"], [], [], [ITZHAK] + Q_MASTERS))
    guns = {r["craft"]["gun"] for r in ups}
    mods = {r["craft"]["mod"] for r in ups}
    check("once per instance: every recipe turns a gun into its own modification"
          " (<base>_mod_<effect>[_gold]), and no recipe asks for a modification",
          ([r["type"] for r in ups if craft.mod_of(r["craft"]["mod"])
            != (r["craft"]["gun"], r["craft"]["effect"])],
           sorted(guns & mods), [r["type"] for r in ups
                                 if r["objs"][0]["obj"] != r["craft"]["gun"]
                                 or r["rew_obj"] != [r["craft"]["mod"]]]), ([], [], []))
    check("  ..a gun with the wiki's table only (a gun without one would be the designed"
          " stand-in), and the blueprint of the recipe's own level",
          ([r["type"] for r in ups if r["craft"]["gun"] not in items.wiki()],
           [r["type"] for r in ups if not items.catalogue()[r["craft"]["blueprint"]][1]
            .endswith("lvl%d" % r["craft"]["level"])]), ([], []))
    check("  ..in the original's words: name, start, «Само собой ничего не сделается.»,"
          " «Готово, пользуйся.»",
          (quests.get(10009).name, "Задача:</b> принести Маузер C96 и Чертеж: урон (2у)"
           in quests.get(10009).texts[quests.START], quests.get(10009).texts[2:]),
          ("Маузер C96: повышение урона", True,
           ("Само собой ничего не сделается.", "Готово, пользуйся.")))
    check("  ..the file's slip «shotgun_1_lvl_8» read as the gun's name",
          [r["name"] for r in ups if "shotgun_1_lvl_8" in r["name"] + r["start"]], [])
    # An upgrade keeps the gun's wear (craft.keep_wear, setcraft.worn_as), a
    # sharpening the knife's: the modification's price is the gun's, and at
    # any wear its share of the ceiling left, and of the ceiling whole, is no
    # more than the gun's -- so no stall pays more for it and no repair costs
    # less, and a broken gun comes out broken. It came out new: a broken
    # Desert Eagle (25656, which no stall buys) and a 3 000 blueprint made a
    # whole 25659 the pistols' stall bought for 4 480 afro.
    better, repriced = [], []
    for r in ups + family("knife"):
        pg, pm = items.params_of(r["craft"]["gun"]), items.params_of(r["craft"]["mod"])
        a, b = pg["max_break_abs"], pm["max_break_abs"]
        if r["craft"]["family"] == "upgrade" and any(
                pg.get(k) != pm.get(k) for k in ("cost", "g_cost", "sell_mod", "repair_mod")):
            repriced.append(r["type"])
        for brk, top in ((0, a), (0, a * 3 // 4), (1, a), (a // 3, a), (a // 2, a * 3 // 4),
                         (a - 1, a - 1), (a, a)):
            nb, nt = setcraft.worn_as((brk, top, a), b)
            if nb * top > brk * nt or nt * a > top * b or (brk == 0) != (nb == 0):
                better.append((r["type"], (brk, top, a), (nb, nt, b)))
    check("an upgrade keeps the gun's wear, a sharpening the knife's: the modification at"
          " the gun's price, never a share of the ceiling more, a broken gun a broken"
          " modification (a Desert Eagle at 0/550 a Desert Eagle Mod at 0/550)",
          (repriced, better, setcraft.worn_as((0, 550, 550), 550)), ([], [], (0, 550)))

    # The generator is one for every city: another band, other rows.
    sys.path.insert(0, DATA)
    source = os.environ.get("LAVA_ORIG_TEXTS") or "/mnt/c/Users/gmkrt/Downloads/texts.xml"
    if os.path.isfile(source):
        import build_orig_misc  # noqa: E402
        import build_weaponcraft  # noqa: E402
        texts, _md5, _size = build_orig_misc.load_texts(source)
        abri = dict(name="abri", band=(9, 12),
                    masters={(c, v): [1] for c in craft.WEAPONS for v in "AGQ"})
        got = build_weaponcraft.upgrade_rows(abri, texts)
        # Few: most guns above the 8th level have no table of the wiki's
        # yet, and a recipe waits for its gun's (the report's «left out»).
        check("the same generator given Абри's band 9-12 returns that band's recipes and no"
              " other: all of 9-12, no premium line, none of Вади-Хальфа's",
              (len(got) > 0, all(9 <= r["craft"]["level"] <= 12 for r in got),
               {r["craft"]["line"] for r in got} <= {"A", "G"},
               sorted({r["craft"]["gun"] for r in got} & guns)), (True, True, True, []))
        check("  ..and rebuilt now, Вади-Хальфа's table is the one on disk",
              json.dumps(build_weaponcraft.build(texts), sort_keys=True),
              json.dumps(DOC, sort_keys=True))
        # The blueprint stalls are each city's (2026-10-13): Вади-Хальфа's entry
        # names the stalls these were before, and --stock gives them the
        # blueprints of Вади-Хальфа's recipes alone, none of Донгола's 9-16.
        printed = build_weaponcraft.stock(DOC)
        check("  ..the blueprint stalls by city: Вади-Хальфа's entry the stalls of before,"
              " each printed the blueprints of its own city's recipes of its class and no"
              " other's, as data/npcs.json has them",
              ([c.get("stalls") for c in build_weaponcraft.CITIES if c["name"] == "halfa"],
               {s: sorted(set(printed[s]) - {r["craft"]["blueprint"] for r in family("upgrade")})
                for ss in STALLS.values() for s in ss},
               {s: printed[s] == npcs.stock(s) for ss in STALLS.values() for s in ss}),
              ([STALLS], {s: [] for ss in STALLS.values() for s in ss},
               {s: True for ss in STALLS.values() for s in ss}))
        # A type is its row's for good: a recipe line gone (a gun's table
        # withdrawn) leaves its type unused, and a key new to the table (a
        # table found later, a line the original's order puts between two
        # old ones) takes a type after the family's last -- nobody moves.
        gone, new = sorted(t for t, c in CRAFT.items() if c["family"] == "upgrade")[5:7]
        cut = dict(texts)
        name_line = int(CRAFT[gone]["key"].rsplit(":", 1)[1])
        del cut[name_line], cut[name_line + 1]
        types = dict(DOC["types"])
        del types[CRAFT[new]["key"]]
        again = build_weaponcraft.build(cut, types)
        by_key = {r["craft"]["key"]: r["type"] for r in again["quests"]}
        check("  ..rebuilt with a recipe's line gone and another's key new: the one gone"
              " leaves its type unused, the new one takes the family's next, the rest stay",
              (gone in {r["type"] for r in again["quests"]},
               again["types"].get(CRAFT[gone]["key"]),
               by_key[CRAFT[new]["key"]] == 1 + max(t for k, t in DOC["types"].items()
                                                    if k.startswith("upgrade:")),
               [k for k, t in by_key.items() if k != CRAFT[new]["key"]
                and DOC["types"][k] != t]),
              (False, gone, True, []))
        fams = {f: [] for f in build_weaponcraft.FAMILIES}
        fams["upgrade"] = [{"craft": {"key": "upgrade:test:1"}}]
        check("  ..a family past the end of its block goes on in its next (the upgrades"
              " after 10399 at 10800)",
              build_weaponcraft.number(fams, {"upgrade:test:0": 10399})[0][0]["type"], 10800)
        salvage_classes = {}
        for i in range(25400, 25457):
            m = re.match(r"^Разобрать сломан\w+ (.+?) (\d)кл", texts[i])
            if m:
                salvage_classes.setdefault(build_weaponcraft.kind_of(m.group(1)),
                                           []).append(int(m.group(2)))
        tiled = {}
        for cls, ks in salvage_classes.items():
            bands = [build_weaponcraft.class_levels(cls, k, ks)[1:] for k in sorted(ks)]
            tiled[cls] = (bands[0][0], bands[-1][1],
                          all(a[1] + 1 == b[0] for a, b in zip(bands, bands[1:])))
        check("the salvage classes of every weapon take the levels 0-20 between them, no gap"
              " and no overlap", tiled, {cls: (0, 20, True) for cls in salvage_classes})
    else:
        print("  --  no %s: the generator's band filter is checked on the table only" % source)

    # The blueprints drop only in the camps of their level (Донгола's camps:
    # test_dongola_trade; Абу-Хамед's: test_abuhamed_trade).
    camp_of = {}
    for (lo, hi), locs in CAMPS:
        for loc in locs:
            for t in stood(loc):
                camp_of.setdefault(t, set()).add((lo, hi))
    stray = []
    for r in (r for r in ROWS if city_of(r) not in LATER):
        level = r["craft"].get("level")
        for o in r.get("objs", []):
            for m in o.get("mobs", []):
                if not any(lo <= level <= hi for lo, hi in camp_of.get(m, ())):
                    stray.append((r["type"], o["obj"], m))
    check("every drop a row declares is off a creature of a camp whose band holds the"
          " thing's level: stat blueprints off the chiefs, the encrypted off the camp",
          (stray, sorted({mobs.stats(m).role for r in ups for o in r["objs"]
                          for m in o.get("mobs", [])}),
           sorted({round(o["drop"], 2) for r in ROWS for o in r.get("objs", [])
                   if o.get("drop")})), ([], ["boss"], [0.02, 0.1]))
    level_of_bp = {r["craft"]["blueprint"]: r["craft"]["level"] for r in ups}
    level_of_bp.update({r["objs"][0]["obj"]: r["craft"]["level"] for r in family("decode")})
    check("  ..a camp of 0-2 drops nothing above the 2nd level, a camp of 7-8 nothing below"
          " the 7th",
          (sorted({level_of_bp[t] for t, _c in quests.quest_drops(270) if t in level_of_bp}),
           sorted({level_of_bp[t] for t, _c in quests.quest_drops(305) if t in level_of_bp})),
          ([1, 2], [7, 8]))
    # One a corpse: a player may hold every recipe of a chief's level open
    # (services: no journal limit of 25), and the corpse still rolls once.
    rng = random.Random(3)
    rolls = {}
    for m, group, (lo, hi) in ((269, "craft_blueprint", (0.07, 0.13)),
                               (313, "craft_blueprint", (0.07, 0.13)),
                               (269, "craft_codified", (0.01, 0.03)),
                               (305, "craft_codified", (0.01, 0.03))):
        wanted = {o["obj"] for r in ROWS for o in r.get("objs", [])
                  if m in o.get("mobs", ()) and o.get("one_of") == group}
        got = [len([t for t, _n in mobs.quest_roll(m, wanted, rng) if t in wanted])
               for _k in range(4000)]
        rolls[(m, group)] = (len(wanted), max(got), lo < sum(got) / 4000.0 < hi)
    check("  ..every drop slot one of a group, so a corpse gives one of each group at most"
          " whatever rows are open: a stat blueprint off a chief about one in ten, an"
          " encrypted one off anybody of the camp one in fifty",
          (sorted({o.get("one_of") for r in ROWS for o in r.get("objs", []) if o.get("drop")}),
           rolls),
          (["craft_blueprint", "craft_codified"],
           {(269, "craft_blueprint"): (15, 1, True), (313, "craft_blueprint"): (14, 1, True),
            (269, "craft_codified"): (2, 1, True), (305, "craft_codified"): (2, 1, True)}))

    # The stalls.
    by_class = {}
    for r in ups:
        if r["craft"]["line"] in "AG":
            by_class.setdefault(craft.weapon_of(r["craft"]["gun"]), set()).add(r["craft"]["blueprint"])
    check("the empty blueprint stalls sell their master's class's blueprints, all of them",
          {cls: [set(items.stock_for(s)) == by_class[cls] for s in stalls]
           for cls, stalls in STALLS.items()},
          {cls: [True] * len(stalls) for cls, stalls in STALLS.items()})
    check("  ..the quarter's trader the [Q] Маузер's twelve, Однопальцый (1152) the valley's"
          " and Вади-Хальфа's whetstones' blueprints; the valley's Одноглазый his knife line"
          " alone (test_shops)",
          (set(items.stock_for(Q_STALL)) == {r["craft"]["blueprint"] for r in ups
                                            if r["craft"]["line"] == "Q"},
           {r["craft"]["blueprint"] for r in family("knife")
            if r["give"][0] in (5192, WHETSTONE)} <= set(items.stock_for(1152)),
           [t for t in items.stock_for(5222) if items.root_of(t) != items.COLD_ARM]),
          (True, True, []))
    # Абри's whetstone (2026-10-12): its six blueprints at Одноухий, the head of
    # his own list in data/npcs.json (build_weaponcraft --stock prints it,
    # KNIFE_STALLS), the gypsum, wire and bandages of Марис Дамбис's chain
    # after them; its knives (G) are the town's band's at his stall.
    import npcs  # noqa: E402
    abri_stone = [r for r in family("knife") if r["give"] == [ABRI_WHETSTONE]]
    abri_prints = sorted({r["craft"]["blueprint"] for r in abri_stone})
    check("Абри's whetstone (2280): «Заточка», «Эргономика» and both of Нож кастет (10у) and"
          " Штык нож (12у); its blueprints on sale at Одноухий, who stands beside it in the"
          " port market, his own list's head as --stock prints it, and its knives (G) at his"
          " stall",
          (sorted((r["craft"]["level"], r["craft"]["gun"]) for r in abri_stone), abri_prints,
           npcs.stock(ABRI_KNIVES)[:len(abri_prints)] == abri_prints,
           build_weaponcraft.stock(DOC)[ABRI_KNIVES] == abri_prints
           if "build_weaponcraft" in sys.modules else True,
           sorted({r["craft"]["gun"] for r in abri_stone} - set(items.stock_for(ABRI_KNIVES,
                                                                                 ABRI_PORT))),
           ABRI_KNIVES in stood(ABRI_PORT), ABRI_WHETSTONE in stood(ABRI_PORT)),
          ([(10, 6251)] * 3 + [(12, 6256)] * 3, list(range(6620, 6626)), True, True, [],
           True, True))
    import npcs  # noqa: E402
    check("  ..those two added to the wiki's list (craft.stock_extra), the owner's file"
          " (data/npcs.json) untouched there, so the wiki's list still reaches Однопальцый",
          (npcs.stock(Q_STALL), npcs.stock(1152),
           items.stock_for(1152)[:len(items.stock_table()[1152])] == items.stock_table()[1152]),
          (None, None, True))
    # Each whetstone's knives on sale where it stands: Вади-Хальфа's Тесак and
    # Охотничий нож (G) were the walled valley's Одноглазый's alone, and the
    # valley's way back (44) asks level 2 at most.
    halfa_stone = [r for r in family("knife") if r["give"] == [WHETSTONE]]
    check("Вади-Хальфа's whetstone: its knives (G) and blueprints on sale at Однопальцый,"
          " who stands in the town's black market",
          (sorted({r["craft"]["gun"] for r in halfa_stone} - set(items.stock_for(1152))),
           sorted({r["craft"]["blueprint"] for r in halfa_stone} - set(items.stock_for(1152))),
           1152 in stood(BLACK_MARKET), WHETSTONE in stood(BLACK_MARKET),
           sorted({r["craft"]["gun"] for r in halfa_stone})), ([], [], True, True, [6241, 6246]))
    sold = {t for s in (576, 578, 7311, Q_STALL, 1152) for t in items.stock_for(s)}
    check("  ..so every recipe's blueprint is on sale in Вади-Хальфа (the pistols' at Мастер"
          " Клара's, 575, as the wiki's list had it)",
          sorted({r["craft"]["blueprint"] for r in ups} - sold - set(items.stock_for(575))), [])
    check("  ..every blueprint on sale priced and named, none premium; the «Урон и размер"
          " обоймы» of the afro line at the article's price, afro or gold, the gold line's"
          " at its gold price alone",
          ([t for t in sold if not (items.params_of(t)["cost"] or items.params_of(t)["g_cost"])],
           [t for t in sold if items.catalogue()[t][1] == names.text(items.STRING_ID_OFFSET + t)],
           [t for t in sold if items.premium(t)],
           (items.params_of(37631)["cost"], items.params_of(37631)["g_cost"],
            items.params_of(37665)["cost"], items.params_of(37665)["g_cost"])),
          ([], [], [], (6000, 150, 0, 150)))
    # The owner's gold line is paid in gold (2026-09-28): a blueprint that only
    # the (G) guns' rows ask -- bpg_damage_25_gold_lvl*, «Урон и размер обоймы»
    # -- is sold for gold alone (items.GOLD_PRICE_ONLY), so it is a gold thing
    # that never falls off a body; a blueprint the afro line asks too keeps
    # both prices.
    import combat  # noqa: E402
    asked = {}
    for r in ups:
        asked.setdefault(r["craft"]["blueprint"], set()).add(r["craft"]["line"])
    g_only = sorted(t for t, lines in asked.items() if lines == {"G"})
    gold_named = sorted(t for t, (_r, n) in items.catalogue().items()
                        if re.match(r"^bp[gb]_.*_gold_", n))
    on_sale = sorted({t for s in (576, 578, 7311, 7309, 7310)
                      for t in items.stock_for(s)} & set(gold_named))
    check("the gold line's own blueprints (asked only by the (G) guns' rows, all of the"
          " gold line's name) on sale in Вади-Хальфа for gold alone: no afro price, a gold"
          " thing, never falls at a death",
          (g_only, on_sale, set(gold_named) <= items.GOLD_PRICE_ONLY,
           sorted({(items.params_of(t)["cost"], items.params_of(t)["g_cost"] > 0,
                    combat.gold_item(t), combat.drops_on_death(t)) for t in gold_named})),
          ([37665, 37666, 37667, 37668], [37665, 37666, 37667, 37668], True,
           [(0, True, True, False)]))
    shared = sorted(t for t, lines in asked.items() if lines & {"A", "Q"})
    check("  ..while every blueprint the afro line or the [Q] one asks keeps its afro price",
          [t for t in shared if not items.params_of(t)["cost"]], [])

    # The modified guns with no table of their own.
    base = items.params_of(MAUSER_Q)
    aim, clip, agile = (items.params_of(t) for t in (43547, 43550, 43552))
    check("a modification the wiki has no table for: its gun's numbers and price, and the"
          " effect the original's hints size (aim -15%, twice the clip, agility +2)",
          ([int(v * 0.85 + 0.5) for v in base["fire_times"]] == aim["fire_times"],
           clip["clip_size"] == 2 * base["clip_size"],
           (agile["bonus_attribs_m"], agile["bonus_attribs"]),
           {(p["cost"], p["g_cost"]) for p in (aim, clip, agile)} == {(base["cost"], base["g_cost"])},
           [names.text(items.STRING_ID_OFFSET + t) for t in (43547, MAUSER_Q)]),
          (True, True, (2, [2]), True, ["Маузер C96 (Q)$Пистолет"] * 2))

    # The gunsmiths, the whetstones, the decoder.
    sal = family("salvage")
    # The fee and the experience of each class are its text's: 1433 afro and
    # 143 for the lowest, 6900/690, 19033/1903 and 40300/4030 above.
    fee = {1: (1433, 143), 2: (1433, 143), 3: (6900, 690), 4: (19033, 1903), 5: (40300, 4030)}
    check("the salvage: at the gunsmith of its class, «сломаный ... Nкл.» of the original,"
          " its fee and «Переработка», one part of the class drawn; the classes whose parts"
          " are of Вади-Хальфа's levels",
          sorted((r["give"][0], r["craft"]["weapon"], r["craft"]["class"],
                  (r["cost_afro"], r["rew_spec_xp"]["recycling"]) == fee[r["craft"]["class"]],
                  len(r["rew_random"]), tuple(r["craft"]["levels"])) for r in sal),
          sorted([(242, "pistol", 2, True, 3, (0, 2)), (242, "pistol", 3, True, 3, (3, 3)),
                  (242, "pistol", 4, True, 3, (4, 4)), (242, "pistol", 5, True, 3, (5, 20)),
                  (238, "rifle", 1, True, 4, (0, 9)),
                  (239, "shotgun", 2, True, 4, (0, 5)), (239, "shotgun", 3, True, 4, (6, 6)),
                  (239, "shotgun", 4, True, 4, (7, 7)), (239, "shotgun", 5, True, 4, (8, 20)),
                  (243, "smg", 1, True, 4, (0, 8))]))
    check("  ..its parts the class's, named in the original's words; the start says what the"
          " bench takes",
          ([names.text(items.STRING_ID_OFFSET + o["obj"]) for o in sal[0]["rew_random"]],
           sal[0]["start"].endswith("самое дешёвое сломанное оружие этого класса 0-2 уровня из"
                                    " рюкзака. Золотое, улучшенное и выданное по заданию оружие"
                                    " не разбирается.")),
          (["Кустарный пистолетный ствол", "Кустарный пистолетный корпус",
            "Кустарный пистолетный ударно-спусковой механизм"], True))
    bench = {}
    for t, (root, _n) in items.catalogue().items():
        got = craft.salvageable(t) if root == items.FIRE_ARM else None
        if got:
            bench.setdefault(got[0], set()).add(got[1])
    check("  ..every class's levels hold a gun its bench takes (the wiki's table, not premium,"
          " gold, modified or lent), and a class-1 bench takes the rifles of 6-8 and the"
          " sub-machine guns of the 8th",
          ([r["type"] for r in sal if not any(r["craft"]["levels"][0] <= n <= r["craft"]["levels"][1]
                                               for n in bench.get(r["craft"]["weapon"], ()))],
           sorted(n for n in bench["rifle"] if n <= 9), sorted(n for n in bench["smg"] if n <= 8),
           [craft.salvageable(t) for t in (BERETTA_G, BERETTA_DAMAGE, MAUSER_Q)]),
          ([], [6, 7, 8], [8], [None, None, None]))
    drawn = {o["obj"] for r in sal for o in r["rew_random"]}
    check("the assembly: at the gunsmith of the gun's class, its parts, the gun; every part"
          " one a salvage row draws",
          (sorted({(r["give"][0], craft.weapon_of(r["rew_obj"][0])) for r in family("assembly")}),
           sorted({o["obj"] for r in family("assembly") for o in r["objs"]} - drawn)),
          ([(238, "rifle"), (239, "shotgun"), (242, "pistol"), (243, "smg")], []))
    check("the whetstones sharpen their own knives, each three ways",
          sorted((r["give"][0], r["craft"]["level"]) for r in family("knife")),
          sorted((w, lvl) for w, lvls in WHETSTONES.items() for lvl in lvls for _k in range(3)))
    check("the decoder: «Чертежи N-го уровня» for 1-8, a fee, a blueprint of the level drawn",
          [(r["give"], r["craft"]["level"], r["cost_afro"] > 0,
            all(items.catalogue()[o["obj"]][1].endswith("lvl%d" % r["craft"]["level"])
                for o in r["rew_random"])) for r in family("decode")],
          [([DECODER], n, True, True) for n in range(1, 9)])

    def decode_margin(r):
        """The draw's mean sale back to a stall (Inventory.sell: cost x SMOD,
        floored) less the fee, and a tenth of the draw's mean price."""
        prices = [items.params_of(o["obj"]) for o in r["rew_random"]]
        sale = sum(int(p["cost"] * inventory.SMOD * p.get("sell_mod", 1)) for p in prices)
        worth = sum(p["cost"] for p in prices) / float(len(prices))
        return sale / float(len(prices)) - r["cost_afro"], worth / 10.0

    check("  ..and no farm: a decoded blueprint sold back nets at most a tenth of its price"
          " (data/build_weaponcraft.py DECODE_FEE, 60 % of the draw's price)",
          [r["craft"]["level"] for r in family("decode")
           if decode_margin(r)[0] > decode_margin(r)[1]], [])

    # The way into the quarter and back went with the premium masters' camp
    # 124 it started from (the owner's cut of (P), 2026-09-30): Мастер Азам
    # stands nowhere, neither row has a giver, no passage is left, and the
    # quarter is no no_map place any more -- its people stay (test_premium_cut).
    check("the ways off: Мастер Азам (124) gone, 414 and 415 given and taken by nobody, no"
          " passage left, the quarter no no_map place; its master still stands there",
          (travel.quest_way(world.location(MASTERS_CAMP), WAY_IN),
           travel.quest_way(world.location(QUARTER), WAY_OUT),
           travel.no_map(QUARTER), AZAM_P in stood(MASTERS_CAMP),
           QUARTER_MASTER in stood(QUARTER),
           [(quests.get(t).give, quests.get(t).take) for t in (WAY_IN, WAY_OUT)]),
          (None, None, False, False, True, [([], [])] * 2))
    check("the upgrader's window at the [Q] masters: the Маузер in, its twelve out; empty"
          " anywhere else",
          (craft.upgrader_lists(JOSEPH)["in_types"] == [MAUSER_Q] * 12,
           sorted(craft.upgrader_lists(QUARTER_MASTER)["out_types"]) ==
           sorted(r["craft"]["mod"] for r in ups if r["give"] == Q_MASTERS),
           craft.upgrader_lists(93)), (True, True, {"in_types": [], "out_types": [], "costs": []}))
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server ----------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_weaponcraft.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("smith", "secret")
_store.close()
CRED = accounts.credential("smith", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5967", LAVA_GY="1727", LAVA_SEED="7",
           LAVA_POLICY_PORT="0")
for _k in ("LAVA_QUESTS", "LAVA_PASSAGES"):
    env.pop(_k, None)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.7):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=4.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(2)


def inhabitants(frames):
    """type id -> (entity id, the userInfo_* frame's name, its params)."""
    return {p["name"]: (p["id"], n, p) for n, p in frames
            if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p}


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    return inhabitants(arrive(c))


def give(c, type_id, n=1):
    """The wire ids of what came into the bag."""
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.frames()
    return [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status") if p["status"] == 1]


def wire(oid):
    return "x" + oid.lstrip("x")


def take(c, here, npc_type, qtype):
    c.send("q_st;mob=%d;q_idx=%d;" % (here[npc_type][0], quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.9)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id, wait=0.9):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[npc_type][0], q_id))
    return c.frames(wait)


def completes(frames):
    return [p["complete"] for n, p in frames if n.startswith("q_di_")]


def char_id():
    st = accounts.Store(DB)
    cid = st.db.execute("SELECT id FROM characters WHERE name = 'Smith'").fetchone()["id"]
    st.close()
    return cid


def owned():
    st = accounts.Store(DB)
    out = {}
    for r in st.items_of(char_id()):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def purse():
    st = accounts.Store(DB)
    got = tuple(st.money(char_id()))
    st.close()
    return got


def worn(type_id):
    """uniq -> (brk, max_break_cur, ammo_count, slot) of Smith's things of a type."""
    st = accounts.Store(DB)
    got = {r["uniq"]: (r["brk"], r["max_break_cur"], r["ammo_count"], r["slot"])
           for r in st.items_of(char_id()) if r["type_id"] == type_id}
    st.close()
    return got


def wear_to(uniq, **cols):
    st = accounts.Store(DB)
    st.update_item(uniq, **cols)
    st.close()


def last_wear(frames, cmd):
    """(break, max_break_cur) of the last dynamic info of that command."""
    got = named(frames, cmd)
    return (got[-1]["break"], got[-1]["max_break_cur"]) if got else None


def recipe(gun, effect, giver):
    return [t for t, c in CRAFT.items() if c["family"] == "upgrade" and c["gun"] == gun
            and c["effect"] == effect and giver in quests.get(t).give][0]


def row_of(fam, **kw):
    return [t for t, c in CRAFT.items() if c["family"] == fam
            and all(c.get(k) == v for k, v in kw.items())][0]


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Smith@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    c.send("userMsg;entry=@/money 100000 0@;group=0;")
    c.frames()

    # --- a recipe at the pistols' apprentice ------------------------------------------------
    here = goto(c, CRAFTSMEN_I)
    give(c, BERETTA)
    give(c, DAMAGE_2)
    q = recipe(BERETTA, "damage", ITZHAK)
    got, q_id = take(c, here, ITZHAK, q)
    check("«Беретта 92: повышение урона» at Ицхак Уорнер (94): taken, the gun and the"
          " blueprint already in the bag", (acks(got), completes(got)), ([0], [1]))
    got = hand_in(c, here, ITZHAK, q_id)
    have = owned()
    check("  ..handed in: the gun and the blueprint gone, «Беретта 92 Mod XII» in the bag",
          (acks(got), have.get(BERETTA, 0), have.get(DAMAGE_2, 0), have.get(BERETTA_DAMAGE, 0)),
          ([0], 0, 0, 1))
    give(c, DAMAGE_2)
    got, q_id = take(c, here, ITZHAK, q)
    check("  ..the upgraded gun cannot be upgraded again: with it and a blueprint the recipe"
          " is not complete, and its hand-in is refused",
          (completes(got), acks(hand_in(c, here, ITZHAK, q_id))[-1:], owned().get(BERETTA_DAMAGE)),
          ([0], [3], 1))
    c.send("q_ca;q_id=%d;" % q_id)
    c.frames()

    # --- the upgrader's window at Жозеф де Гобино -------------------------------------------
    here = goto(c, OASIS)
    eid, kind, info = here[JOSEPH]
    check("Жозеф де Гобино (62): an upgrader whose window lists the Маузер's twelve",
          (kind, info.get("in_types", [])[:1], len(info.get("out_types", [])), set(info.get("costs", []))),
          ("userInfo_Upgrader", [MAUSER_Q], 12, {0}))
    gun = give(c, MAUSER_Q)[0]
    c.send("ss_create;s_type=5;target=%d;" % eid)
    check("  ..the window opens", acks(c.frames()), [0])
    c.send("ss_upd;s_status=1;obj=%s;param=%d;" % (wire(gun), MAUSER_PRECISION))
    got = c.frames()
    check("  ..no blueprint in the bag: refused, the gun untouched",
          (acks(got), owned().get(MAUSER_Q), owned().get(MAUSER_PRECISION, 0)),
          ([inventory.RES_REFUSED], 1, 0))
    give(c, PRECISION_2)
    c.send("ss_upd;s_status=1;obj=%s;param=%d;" % (wire(gun), MAUSER_PRECISION))
    got = c.frames()
    have = owned()
    check("  ..with «Точность (2у)»: that very gun and the blueprint gone, the «точность на"
          " 20%» Маузер in",
          (acks(got), [p["status"] for p in named(got, "ss_obj_status")],
           have.get(MAUSER_Q, 0), have.get(PRECISION_2, 0), have.get(MAUSER_PRECISION)),
          ([0], [0, 0, 1], 0, 0, 1))
    new = [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status") if p["status"] == 1][0]
    give(c, PRECISION_2)
    c.send("ss_upd;s_status=1;obj=%s;param=%d;" % (wire(new), MAUSER_PRECISION))
    check("  ..and what came out is no gun the window takes: refused",
          acks(c.frames()), [inventory.RES_NOT_FOUND])
    c.send("ss_upd;s_status=0;obj=x0;")
    check("  ..closed with no answer", acks(c.frames(0.5)), [])
    gun = give(c, MAUSER_Q)[0]
    c.send("ss_create;s_type=5;target=%d;" % eid)
    c.frames()
    goto(c, CRAFTSMEN_I)
    c.send("ss_upd;s_status=1;obj=%s;param=%d;" % (wire(gun), MAUSER_PRECISION))
    got = c.frames()
    have = owned()
    check("  ..a window left open while the player went elsewhere upgrades nothing: refused,"
          " the gun and the blueprint where they were",
          (acks(got)[-1:], have.get(MAUSER_Q), have.get(PRECISION_2), have.get(MAUSER_PRECISION)),
          ([inventory.RES_NOT_FOUND], 1, 1, 1))

    # --- the gunsmith's bench -----------------------------------------------------------------
    here = goto(c, SMITHS)
    salvage = row_of("salvage", weapon="pistol", **{"class": 2})
    pistol = give(c, NAGAN)[0]
    got, q_id = take(c, here, PISTOL_SMITH, salvage)
    check("«Разобрать сломаный пистолет 2кл.» at the pistols' gunsmith (599): taken, but a"
          " whole pistol is no broken one -- not complete, and the hand-in refused",
          (acks(got), completes(got), acks(hand_in(c, here, PISTOL_SMITH, q_id))),
          ([0], [0], [21]))
    st = accounts.Store(DB)
    st.update_item(inventory.parse_oid(pistol)[0], brk=0)
    st.close()
    got = c.frames(0.2)
    give(c, 41)                                     # anything into the bag: the recount
    got = c.frames(0.8)
    afro0, _g = purse()
    parts = {o[0] for o in quests.get(salvage).rew_random}
    got = hand_in(c, here, PISTOL_SMITH, q_id)
    have = owned()
    check("  ..broken, it is: handed in, 1433 afro, the pistol gone, one of the class's parts",
          (acks(got), afro0 - purse()[0], have.get(NAGAN, 0),
           sum(have.get(t, 0) for t in parts)), ([0], 1433, 0, 1))

    # The bench takes the cheapest broken gun of its class, and never one
    # bought for gold or upgraded: given dearest first, taken cheapest first.
    uniqs = [inventory.parse_oid(give(c, t)[0])[0] for t in (BERETTA_G, BERETTA, NAGAN)]
    st = accounts.Store(DB)
    uniqs += [r["uniq"] for r in st.items_of(char_id()) if r["type_id"] == BERETTA_DAMAGE]
    for u in uniqs:
        st.update_item(u, brk=0)
    st.close()
    give(c, 41)
    c.frames(0.5)
    taken = []
    for _k in range(3):
        before = owned()
        got, q_id = take(c, here, PISTOL_SMITH, salvage)
        got = hand_in(c, here, PISTOL_SMITH, q_id)
        after = owned()
        taken.append((acks(got)[-1:], [t for t in (NAGAN, BERETTA, BERETTA_G, BERETTA_DAMAGE)
                                       if after.get(t, 0) < before.get(t, 0)]))
        if acks(got)[-1:] != [0]:
            c.send("q_ca;q_id=%d;" % q_id)
            c.frames()
    check("  ..four broken pistols of the class: the Наган (400) first, then the Беретта"
          " (800), then nothing -- the gold Беретта and the upgraded one stay",
          (taken, owned().get(BERETTA_G), owned().get(BERETTA_DAMAGE)),
          ([([0], [NAGAN]), ([0], [BERETTA]), ([21], [])], 1, 1))

    # The 1st class of the rifles and the sub-machine guns: their guns start
    # at the 6th and the 8th level.
    first_class = []
    for weapon, gun_type in (("rifle", RIFLE_6), ("smg", SMG_8)):
        row = row_of("salvage", weapon=weapon, **{"class": 1})
        u = inventory.parse_oid(give(c, gun_type)[0])[0]
        st = accounts.Store(DB)
        st.update_item(u, brk=0)
        st.close()
        give(c, 41)
        c.frames(0.5)
        smith = GUNSMITHS[weapon]
        got, q_id = take(c, here, smith, row)
        got = hand_in(c, here, smith, q_id)
        have = owned()
        first_class.append((acks(got)[-1:], have.get(gun_type, 0),
                            sum(have.get(o[0], 0) for o in quests.get(row).rew_random)))
    check("  ..a broken Самодельная винтовка (6) at the rifles' bench of the 1st class, a"
          " broken Кустарный ПП (8) at the sub-machine guns': taken, a part each",
          first_class, [([0], 0, 1), ([0], 0, 1)])

    assembly = row_of("assembly", gun=BERETTA)
    for o in quests.get(assembly).objs:
        give(c, o[0], o[1])
    got, q_id = take(c, here, PISTOL_SMITH, assembly)
    got = hand_in(c, here, PISTOL_SMITH, q_id)
    check("«Беретта 92(A)» assembled from its three parts: the gun in the bag",
          (acks(got), owned().get(BERETTA, 0)), ([0], 1))

    # --- the whetstone and the decoder ------------------------------------------------------------
    here = goto(c, BLACK_MARKET)
    give(c, TESAK_G)
    give(c, SHARPEN_6)
    got, q_id = take(c, here, WHETSTONE, row_of("knife", gun=TESAK_G, blueprint=SHARPEN_6))
    got = hand_in(c, here, WHETSTONE, q_id)
    check("«Заточка Тесака» at the whetstone of Вади-Хальфы: the sharp Тесак (G)",
          (acks(got), owned().get(TESAK_G, 0), owned().get(TESAK_SHARP)), ([0], 0, 1))
    give(c, CODIFIED_2)
    decode2 = row_of("decode", level=2)
    before = owned()
    afro0, _g = purse()
    got, q_id = take(c, here, DECODER, decode2)
    got = hand_in(c, here, DECODER, q_id)
    have = owned()
    prizes = {o[0] for o in quests.get(decode2).rew_random}
    check("«Чертежи 2-го уровня» at the Техногик: the encrypted one and 600 afro for one"
          " blueprint of the 2nd level",
          (acks(got), have.get(CODIFIED_2, 0), afro0 - purse()[0],
           sum(have.get(t, 0) - before.get(t, 0) for t in prizes)), ([0], 0, 600, 1))

    # --- the gold line's blueprint at the shotgun blueprints' stall -------------------------------
    here = goto(c, PORT_MARKET)
    c.send("userMsg;entry=@/money 0 1000@;group=0;")
    c.frames()
    c.send("ss_create;s_type=1;target=%d;" % here[SHOTGUN_STALL][0])
    check("the shotgun blueprints' stall (576) opens at the port market",
          acks(c.frames()), [0])
    index = "x%x" % items.stock_for(SHOTGUN_STALL).index(GOLD_BP_5)
    money0 = purse()
    c.send("ss_upd;s_status=1;obj=%s;param=1;" % index)
    got = c.frames()
    check("  ..«Урон и размер обоймы (5у)» of the gold line is not sold for afro: refused,"
          " nothing moves", (acks(got) != [0], purse(), owned().get(GOLD_BP_5, 0)),
          (True, money0, 0))
    c.send("ss_upd;s_status=4;obj=%s;param=1;" % index)
    got = c.frames()
    check("  ..and is for gold: 1.50 G", (acks(got), purse(), owned().get(GOLD_BP_5, 0)),
          ([0], (money0[0], money0[1] - 150), 1))
    c.send("ss_upd;s_status=0;obj=x0;")
    c.frames(0.3)

    # --- the quarter ------------------------------------------------------------------------------
    # The ways in and out went with the cut of (P); an admin's /goto is what
    # is left, and the quarter's master is still an upgrader there.
    here = goto(c, MASTERS_CAMP)
    check("the premium masters' camp 124, gone to by /goto: nobody stands in it",
          sorted(here), [])
    here = goto(c, QUARTER)
    check("the Квартал ремесленников by /goto: its master stands there, an upgrader with the"
          " [Q] recipes",
          (here.get(QUARTER_MASTER, (0, ""))[1], len(here.get(QUARTER_MASTER, (0, "", {}))[2]
                                                       .get("in_types", []))),
          ("userInfo_Upgrader", 12))

    # --- an upgrade keeps the wear --------------------------------------------------------------
    # At a hand-in: the take takes the oldest Беретта in the bag (Inventory.
    # take_pieces) -- here broken, its ceiling sagged, seven rounds in it --
    # and the modification comes out as broken as it went in, the rounds
    # into the bag; the newer, whole one stays whole.
    here = goto(c, CRAFTSMEN_I)
    a_ber = items.params_of(BERETTA)["max_break_abs"]
    rounds = items.params_of(BERETTA)["comp_array"][0]
    give(c, BERETTA)
    give(c, DAMAGE_2)
    bag_guns = sorted(u for u, w in worn(BERETTA).items() if w[3] == inventory.BAG)
    oldest = bag_guns[0]
    wear_to(oldest, brk=0, max_break_cur=a_ber * 9 // 10, ammo_count=7, ammo_type=rounds)
    mods0 = worn(BERETTA_DAMAGE)
    rounds0 = owned().get(rounds, 0)
    got, q_id = take(c, here, ITZHAK, q)
    got = hand_in(c, here, ITZHAK, q_id)
    new_mods = {u: w for u, w in worn(BERETTA_DAMAGE).items() if u not in mods0}
    want = setcraft.worn_as((0, a_ber * 9 // 10, a_ber), items.params_of(BERETTA_DAMAGE)["max_break_abs"])
    check("an upgrade at a hand-in keeps the gun's wear: the oldest Беретта taken, broken at"
          " 0/%d, its «Mod XII» broken at 0/%d and so told, its 7 rounds back in the bag, the"
          " newer Беретта whole" % (a_ber * 9 // 10, want[1]),
          (acks(got), oldest in worn(BERETTA), [w[:2] for w in new_mods.values()],
           last_wear(got, "ss_di_firearm"), owned().get(rounds, 0) - rounds0,
           sorted(w[:2] for u, w in worn(BERETTA).items() if u in bag_guns)),
          ([0], False, [want], want, 7, [(a_ber, a_ber)] * (len(bag_guns) - 1)))
    check("  ..so a broken gun upgraded is still a broken gun: no stall buys it",
          [w[0] for w in new_mods.values()], [0])

    # In the window: the very Маузер dragged in, worn and its ceiling sagged.
    here = goto(c, OASIS)
    a_mau = items.params_of(MAUSER_Q)["max_break_abs"]
    gun = give(c, MAUSER_Q)[0]
    wear_to(inventory.parse_oid(gun)[0], brk=a_mau // 4, max_break_cur=a_mau - 30)
    give(c, PRECISION_2)
    c.send("ss_create;s_type=5;target=%d;" % here[JOSEPH][0])
    c.frames()
    mods0 = worn(MAUSER_PRECISION)
    c.send("ss_upd;s_status=1;obj=%s;param=%d;" % (wire(gun), MAUSER_PRECISION))
    got = c.frames()
    want = setcraft.worn_as((a_mau // 4, a_mau - 30, a_mau),
                            items.params_of(MAUSER_PRECISION)["max_break_abs"])
    check("  ..and in the upgrader's window: the Маузер at %d/%d comes out a «точность» Маузер"
          " at %d/%d, so told" % ((a_mau // 4, a_mau - 30) + want),
          (acks(got), [w[:2] for u, w in worn(MAUSER_PRECISION).items() if u not in mods0],
           last_wear(got, "ss_di_firearm")), ([0], [want], want))
    c.send("ss_upd;s_status=0;obj=x0;")
    c.frames(0.3)

    # At the whetstone: a worn Тесак (G) sharpened is a worn sharp Тесак.
    here = goto(c, BLACK_MARKET)
    a_tes = items.params_of(TESAK_G)["max_break_abs"]
    give(c, SHARPEN_6)
    knife = inventory.parse_oid(give(c, TESAK_G)[0])[0]
    wear_to(knife, brk=a_tes // 3, max_break_cur=a_tes - 20)
    sharp0 = worn(TESAK_SHARP)
    got, q_id = take(c, here, WHETSTONE, row_of("knife", gun=TESAK_G, blueprint=SHARPEN_6))
    got = hand_in(c, here, WHETSTONE, q_id)
    want = setcraft.worn_as((a_tes // 3, a_tes - 20, a_tes),
                            items.params_of(TESAK_SHARP)["max_break_abs"])
    check("  ..and a sharpening: the Тесак (G) at %d/%d sharpened is a sharp one at %d/%d"
          % ((a_tes // 3, a_tes - 20) + want),
          (acks(got), [w[:2] for u, w in worn(TESAK_SHARP).items() if u not in sharp0],
           last_wear(got, "ss_di_coldarm")), ([0], [want], want))
except SystemExit:
    raise
except Exception:
    import traceback
    fails.append("the socket part broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

bad = [line for line in _log if "Traceback" in line or "!!" in line]
check("the server logged no traceback", bad, [])
if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    tail = "".join(_log[-60:])
    print("\n--- server log tail ---\n" + tail)
    sys.exit(1)
print("\nall passed")
