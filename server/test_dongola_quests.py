"""Донгола's quests (the owner's «и потом сделай донголу тоже», 2026-10-13): the
rows 630-799 of data/quests.json, the ways of data/passages.json they take,
the prison's windows of data/schedule.json, the warehouses of
data/holdings.json and the rows of Вади-Хальфа and Абри that waited for the
town (250-286, 163-168), held on the real tables.

In process:

  * every row of 630-799 (but Вади-Хальфа's boxes 765-767) sits in its block
    of the plan (DESIGN.md 5.0) and is on (a giver and a taker); the blocks
    cut stay empty -- Абу-Хамед's box 772 (771, the Центр's, is Абу-Хамед's
    since 2026-10-14: server/test_abuhamed_quests), «Секреты Магриба» 773-788,
    the raids 789-795 -- and the rows of 250-286 that wait for no closed town
    are on: Хоу Сян's and Мун Сон Мён's map and shovel (257, 258), the dig of
    5899.2003 (254) and the skulls of 68 and 146 (260, 261), Энди Уорхол's
    «Коллекция водителя шайтан-арбы» (271), the rides between Абри and
    Донгола (275, 281, 282);
  * the givers and takers stand in a place the map opens (a cell of
    data/settlements.json, or what a door, a side or a quest way leads to
    from one), each by a name of the original's or a DESIGNED one, never its
    mobs.xml name;
  * every string id is in the preload; the texts are the original's where
    data/build_orig_misc.py pins them (VERIFIED), laid over the table's; the
    rows not pinned are exactly the DESIGNED ones, and no DESIGNED line says
    «не ..., а ...»;
  * every thing a row names is an objects.xml object with a name and a
    description of its own, none premium, and drawn -- its picture in the
    original's res or in client/files (the coin 46652, the release's copy of
    the original's qSilverReal); every thing asked for can be had --
    dropped while the quest wants it by somebody standing in the open places,
    sold at a stall there, or handed out by a row; no row pays gold or an
    ingot;
  * the ways: each way row has its record at the giver's place, its cells on
    the grid, walkable, off the exits, where no window opens, nobody arrives
    and nobody stands; given and taken by one inhabitant; the pairs of the
    plan written on both sides (630/631, 275-281/282, 632/633, 79/607,
    608/1009, 702/703); from every interior of Донгола -- the prison, the
    quarry, the mine, the sewers, Zone 49 -- the free ways (level 0, no chain,
    nothing asked, no window), its sides and its doors lead to a place of the
    map; the ways into Zone 49 cost the fares of the rides to Донгола from the
    same towns (733 as 630, 744 as 275), the Zone's own stay free;
  * the prison: «Выход» (163) is a way under '622' up to the yard 159, the
    gates lead to 618 and 619, the windows prison_dn* keep the label's hours,
    the prisoners drop the armband 2476 in 620-622, and the one keep_in row of
    2476 holds both prisons' blocks; 164-168 name both prisons' prisoners;
  * the mines' gates: three ways down at levels 12-15, three up at any level;
    the lotteries: every prize worth less than its ticket, open to the town's
    band 12-16 and named for it; the warehouses:
    three sites, their boxes 768-770 in the window wh_box;
  * «Коллекция водителя шайтан-арбы»: its six pieces named and described,
    a live collection (keepsakes), Уорхол gives 270 and 271;
  * «Посланник Смерти»: part 1 alone (757), parts 2-6 not in the table.

On a socket (a server of the suite's own, LAVA_CHEATS) only the rides:

  * at Вади-Хальфа's station (37) «Поездка в Донголу» with no afro is
    refused, with 200 it brings the player to Донгола's station (49), beside
    Нур-ад-Дин's way back; «Поездка в Вади Хальфу» there costs 150 and brings
    him back; Луиджи's «Поездка в Донголу» (275) costs 100 from Абри's
    Портовый рынок (187); Нур-ад-Дин's «Проездной в Абри» (282) takes the
    ticket 6547 and nothing else.

    LAVA_RES=.../lava/res python3 server/test_dongola_quests.py
"""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_START",
              "LAVA_START_AFRO", "LAVA_BOSS_HOURS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import events  # noqa: E402
import holdings  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import keepsakes  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import own_items  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import shop_bands  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MT = world.mob_types()
# 771, the box of Абу-Хамед's Центр, is Абу-Хамед's since 2026-10-14 (the owner's
# «сделай потом абу хамед в таком же формате»; server/test_abuhamed_quests).
DONGOLA = [t for t in range(630, 800) if t not in (765, 766, 767, 771)]
# The plan's blocks (DESIGN.md 5.0); the cut ones stay empty.
BLOCKS = {"rides": range(630, 632), "prison": range(632, 638), "amin": range(638, 645),
          "friends": range(645, 654), "meeting": range(654, 666), "butchers": range(666, 671),
          "lusher": range(671, 689), "well": range(689, 695), "catacombs": range(695, 708),
          "quarry": range(708, 715), "gates": range(715, 721), "lottery": range(721, 725),
          "muhammad": range(725, 738), "jones": range(738, 750), "spell": range(750, 757),
          "messenger": range(757, 762), "reserve": range(762, 765),
          "boxes": range(768, 771), "boxes_ah": range(772, 773), "magrib": range(773, 789),
          "raids": range(789, 796), "reserve2": range(796, 800)}
CUT = ("boxes_ah", "magrib", "raids", "reserve2")
EXPECT = {"rides": [630, 631], "prison": list(range(632, 637)),
          "amin": list(range(638, 645)), "friends": list(range(645, 654)),
          "meeting": list(range(654, 665)), "butchers": list(range(666, 671)),
          "lusher": list(range(671, 688)), "well": list(range(689, 695)),
          "catacombs": list(range(695, 708)), "quarry": list(range(708, 715)),
          "gates": list(range(715, 721)), "lottery": [721, 722],
          "muhammad": list(range(725, 736)), "jones": list(range(738, 750)),
          "spell": list(range(750, 757)), "messenger": [757, 758],
          "reserve": [762], "boxes": [768, 769, 770]}
# Not pinned to the original: their texts are DESIGNED, or a start is ours
# (the lotteries' names for the town's band and prize lists without the (P)
# guns, the fee lines of the ways into Zone 49, the boss hours of 653).
DESIGNED = {653, 706, 707, 715, 716, 717, 718, 719, 720, 721, 722, 733, 744, 748, 749, 762}
# The ways into Zone 49 and the rides to Донгола whose fares they cost (the
# review of 2026-10-14): Каспар's from Вади-Хальфа's quarter as Хассир's,
# Генри Джонс's from Абри's slums as Луиджи's.
ZONE_IN = {733: 630, 744: 275}
# The band of Донгола's lotteries: the town's.
TOWN_BAND = (12, 16)
# The coin «Серебристая монета» (46652, qSilverReal_one), whose picture the
# release ships (client/files): the original's qSilverReal/ico.swf.
COIN, COIN_ICON = 46652, "classes/SimpleObject/qSilverReal_one/ico.swf"
COIN_ORIGINAL = "classes/SimpleObject/qSilverReal/ico.swf"
# Вади-Хальфа's and Абри's rows that waited for Донгола and are on now.
WAITED = [254, 257, 258, 260, 261, 271, 275, 281, 282]
NUR, HASSIR, LUIGI, STATION, DN_STATION, PORT = 156, 105, 1179, 37, 49, 187
RIDES = {630: (HASSIR, STATION, DN_STATION), 631: (NUR, DN_STATION, STATION),
         275: (LUIGI, PORT, DN_STATION), 281: (LUIGI, PORT, DN_STATION),
         282: (NUR, DN_STATION, PORT)}
TICKET_TO_ABRI = 6547
GATES_DOWN = {715: (208, 663), 716: (209, 664), 717: (210, 665)}
GATES_UP = {718: (663, 208), 719: (664, 209), 720: (665, 210)}
LOTTERIES = {721: (2648, 2400, False), 722: (2651, 300, True)}   # ticket, price, gold
BOXES = {768: ("wh_dn_sever", 113, 7451, 6827, 12), 769: ("wh_dn_vostok", 114, 7452, 6828, 16),
         770: ("wh_dn_ug", 112, 7453, 6829, 16)}
# The interiors of Донгола, none of them a place of the map: the prison's
# blocks, the quarry, the mine under the three entrances, the sewers and
# Zone 49 (DESIGN.md 4.3).
INTERIORS = ([618, 619, 620, 621, 622], [631, 632, 633, 634, 635],
             [614, 616, 1013, 1015, 1020, 1021, 1022, 1023, 1214], [607, 608, 1009],
             [702, 703, 704, 705])
# The pairs of ways written on both sides (DESIGN.md 5.2).
PAIRS = [((STATION, 630), (DN_STATION, 631)), ((PORT, 275), (DN_STATION, 282)),
         ((DN_STATION, 632), (159, 633)), ((79, 697), (607, 705)),
         ((608, 699), (1009, 700)), ((702, 741), (703, 749))]
NOT_BUT = re.compile(r"(?:^|[\s(«])не\s[^.!?<]*?,\s*а\s", re.I)
BAND, BLOCKS_DN, BLOCKS_WH = 2476, [618, 619, 620, 621, 622], [644, 645, 646, 647, 648]
PRISONERS_DN = [932, 933, 934, 935, 936, 2174]


def passages():
    with open(travel.passages_path(), encoding=ENC) as fh:
        return json.load(fh)


def reached_from(start, free_only=False):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way
    (test_halfa_city's rule); with free_only, only the free ways -- level 0,
    no chain, nothing asked, no fee, no window (DESIGN.md 5.2)."""
    sides = passages().get("sides") or {}
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = []
        for _c, r in travel.quest_ways(world.location(lid)):
            q = quests.get(int(r["quest"]))
            if free_only and (q is None or not q.give or q.level or q.need_all
                              or q.need_any or q.wants() or q.has_fee
                              or int(r["quest"]) in events.table().gates):
                continue
            targets.append(r.get("target_loc_id"))
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
                targets.append(rec.get("target_loc_id"))
        own = sides.get(str(lid)) if isinstance(sides, dict) else None
        targets += [r.get("target_loc_id") for r in (own or {}).values() if isinstance(r, dict)]
        for t in targets:
            if t and int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    return seen


def item_name(t):
    return names.ALL.get(items.STRING_ID_OFFSET + t)


# --- in process: the table -------------------------------------------------------------
try:
    real = quests.QUESTS
    raw = {r["type"]: r for r in quests.table_rows()}
    mine = sorted(t for t in real if t in DONGOLA)
    check("the rows of 630-799 sit in their blocks of the plan, the cut blocks empty",
          {b: [t for t in mine if t in r] for b, r in BLOCKS.items()},
          dict({b: [] for b in CUT}, **EXPECT))
    check("  ..and every one of them is on (a giver and a taker)",
          [t for t in mine if not (real[t].give and real[t].take)], [])
    check("the rows of 250-286 that waited for Донгола are on",
          [t for t in WAITED if not (real[t].give and real[t].take)], [])

    # Where the people stand: every place of the map, and what it opens.
    open_places = reached_from(set(world.settlements().values()))
    stands = {}
    for lid in sorted(open_places):
        loc = world.location(lid)
        for _cell, t in loc.spawns:
            stands.setdefault(t, set()).add(lid)
        for t in world.camp_fill(lid):
            stands.setdefault(t, set()).add(lid)
        for rec in world.placed_in(lid):
            stands.setdefault(int(rec["type"]), set()).add(lid)
    live = mine + WAITED
    people = sorted({w for t in live for w in real[t].give + real[t].take})
    check("every giver and taker of the rows stands in a place the map opens",
          [w for w in people if not stands.get(w)], [])
    check("  ..and shows a name of the original's or a DESIGNED one, never its mobs.xml name",
          [w for w in people if not names.known(w) or names.ALL.get(w) == MT[w][1]], [])

    # The strings and the texts.
    check("every string id of the rows is in the preload",
          [(t, sid) for t in mine for sid in real[t].string_ids() if not names.known(sid)], [])
    with open(os.path.join(ROOT, "data", "orig_misc.json"), encoding=ENC) as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts pinned to the original (data/build_orig_misc.py VERIFIED): every row but"
          " the DESIGNED ones (the mines' gates, the lotteries' names and starts, the DESIGNED"
          " ways, the fee lines of the ways into Zone 49, the boss hours of 653)",
          sorted(set(mine) - set(pinned)), sorted(DESIGNED))
    orig = orig_texts.quests()
    check("  ..laid over the table's (but what a row keeps as its own, own_texts)",
          [(t, key) for t in mine for k, key in enumerate(quests.TEXT_KEYS)
           if orig.get(t, {}).get(key) and key not in real[t].own_texts
           and real[t].texts[k] != quests.served(real[t], k, orig[t][key])], [])
    designed_lines = [(t, key, raw[t][key]) for t in mine for key in quests.TEXT_KEYS
                      if raw[t].get(key) and (t in DESIGNED or not orig.get(t, {}).get(key)
                                              or key in real[t].own_texts)]
    check("no DESIGNED line says «не ..., а ...»",
          [(t, key) for t, key, line in designed_lines if NOT_BUT.search(line)], [])

    # The things.
    things = sorted({o for t in live for _f, o in real[t].things()})
    cat = items.catalogue()
    check("every thing the rows name is an objects.xml object (quests.check_items)",
          ([o for o in things if o not in cat], quests.check_items()), ([], None))
    check("  ..with a name and a description the client knows, the name never the internal one,"
          " none premium",
          [o for o in things if not names.known(items.STRING_ID_OFFSET + o)
           or not names.known(items.DESC_ID_OFFSET + o)
           or item_name(o) in (None, "", cat[o][1]) or items.premium(o)], [])

    def icon(o):
        """Where the client looks for a thing's picture (SSEmulator.getIcon):
        a type of our own draws the one of the type it is like."""
        t = own_items.load()[o]["like"] if items.own(o) else o
        return own_items.icon_path(*cat[t])

    def drawn(rel):
        """The picture is in the client: the original's res, or the release's
        own files (client/files), which the launcher puts beside them."""
        return any(os.path.isfile(os.path.join(base, *rel.split("/")))
                   for base in (world.RES, os.path.join(ROOT, "client", "files")))

    check("  ..and drawn: every one has its picture, in the original's res or in client/files --"
          " the coin «Серебристая монета» 46652 too, which Хоу Сян's «Сокровища» (257) asks"
          " fifteen of (the original ships it as qSilverReal, its row says qSilverReal_one)",
          ([o for o in things if not drawn(icon(o))], icon(COIN)), ([], COIN_ICON))
    with open(os.path.join(ROOT, "client", "base.txt"), encoding=ENC) as fh:
        base_rows = [ln.rstrip("\n").split("\t") for ln in fh]
    base_sha = {r[2]: r[0] for r in base_rows
                if len(r) == 3 and r[2] in (COIN_ICON, COIN_ORIGINAL)}
    with open(os.path.join(ROOT, "client", "files", *COIN_ICON.split("/")), "rb") as fh:
        coin_sha = hashlib.sha256(fh.read()).hexdigest()
    check("  ..the coin's picture is the release's copy of the original's qSilverReal, byte for"
          " byte (client/base.txt), at a path the original lacks",
          (coin_sha == base_sha.get(COIN_ORIGINAL), COIN_ICON in base_sha), (True, False))
    traders = {w for w in stands if MT.get(w) and MT[w][0] == world.TRADER}
    on_sale = {o for w in traders for lid in stands[w] for o in items.stock_for(w, lid)}
    # Handed out by a row, or -- a live collection's pieces -- put in a
    # collector's bag after a task (server/keepsakes.py).
    handed = {o for q in real.values() if q.give for o in
              q.rew_obj + [t for t, _n in q.rew_also] + [t for t, _n, _w in q.rew_random]
              + [t for t, _n in q.start_obj]} | set(keepsakes.pool())
    dropped = {o for q in real.values() if q.give for _m, o, _c in q.drops if stands.get(_m)}
    asked = sorted({o for t in live for o, _n in real[t].wants()})
    check("every thing a row asks for can be had: dropped while the quest wants it by somebody"
          " standing in the open places, sold at a stall there, or handed out by a row",
          [o for o in asked if o not in on_sale | handed | dropped], [])
    check("  ..the envelope, the beans, the lottery tickets and the bus tickets are sold",
          sorted(o for o in (1309, 333, 2648, 2651, 6546, 6547) if o not in on_sale), [])
    check("no row of 630-799 pays gold (rew_gold), and none hands out an ingot",
          ([t for t in mine if real[t].rew_gold],
           [t for t in mine for _f, o in real[t].things() if o in items.GOLD_INGOTS]), ([], []))

    # The ways.
    ways = {}
    for t in live + [163]:
        if not real[t].rew_loc:
            continue
        for lid in sorted({p for w in real[t].give for p in stands.get(w, ())}):
            rec = travel.quest_way(world.location(lid), t)
            if rec:
                ways.setdefault(t, set()).add((lid, int(rec["target_loc_id"])))
    check("every way row has its record at the giver's place in data/passages.json",
          sorted(t for t in live if real[t].rew_loc and t not in ways), [])
    bad_cells = []
    for t in sorted(ways):
        for lid, _to in sorted(ways[t]):
            loc = world.location(lid)
            cells, _rec = next((c, r) for c, r in travel.quest_ways(loc) if int(r["quest"]) == t)
            taken = {c for c, _t in loc.spawns}
            zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                           "zones", 4)}
            here = {s for _c, s in loc.spawns}
            if not all(w in here for w in real[t].give):
                bad_cells.append((t, lid, "giver"))
            for c in cells:
                if c in loc.obstacles or c in travel.exit_sides(loc) or c in taken \
                        or c in zones or c in loc.entries:
                    bad_cells.append((t, lid, c % loc.width, c // loc.width))
    check("  ..its cells on the grid, walkable, off the exits, where no window opens, nobody"
          " arrives and nobody stands, its giver standing there (test_halfa_training's rule)",
          bad_cells, [])
    check("  ..given and taken by one inhabitant, as every way (server/test_mine)",
          [t for t in ways if real[t].give != real[t].take], [])
    check("  ..the pairs written on both sides, each leading to the other's place",
          [((a, ta), (b, tb)) for (a, ta), (b, tb) in PAIRS
           if not ((a, b) in ways.get(ta, ()) and (b, a) in ways.get(tb, ()))], [])
    traps = {}
    for group in INTERIORS:
        for lid in group:
            reach = reached_from({lid}, free_only=True)
            if not any(world.cell_of(p) is not None for p in reach):
                traps[lid] = sorted(reach)
    check("from every interior of Донгола its free ways (level 0, no chain, nothing asked, no"
          " window), sides and doors lead to a place of the map (DESIGN.md 5.2)", traps, {})
    check("the rides: Хассир to Донгола and Нур-ад-Дин back to Вади-Хальфа; Луиджи to Донгола"
          " for the fare and the ticket, Нур-ад-Дин to Абри for the ticket",
          {t: (real[t].give, sorted(ways.get(t, ()))) for t in RIDES},
          {t: ([d], [(frm, to)]) for t, (d, frm, to) in RIDES.items()})
    check("  ..the fares the texts name, 200, 150 and 100 afro, and the tickets 6546 and 6547",
          [(real[t].cost_afro, [o for o, _n in real[t].wants()]) for t in (630, 631, 275, 281,
                                                                           282)],
          [(200, []), (150, []), (100, []), (0, [6546]), (0, [6547])])
    check("  ..each a way of the row's own record ('way'), at no level, repeatable",
          {t: (raw[t]["way"]["at"], raw[t]["way"]["target_loc_id"], real[t].level,
               real[t].repeatable) for t in RIDES},
          {t: (frm, to, 0, 1) for t, (_d, frm, to) in RIDES.items()})
    check("Хассир, Луиджи and Нур-ад-Дин list their rides where q_idx finds them",
          (quests.given_by(HASSIR), quests.given_by(LUIGI), quests.given_by(NUR)),
          ([273, 279, 158, 159, 630], [274, 275, 280, 281], [276, 282, 283, 631, 632, 636]))
    # With «Осмотр пирамиды» (741) and «Выбраться наверх» (748) free, a free
    # way into Zone 49 was a free ride to Донгола's station (the review of
    # 2026-10-14).
    check("the ways into Zone 49 cost the fare of the ride to Донгола from the same town:"
          " Каспар's (733) from Вади-Хальфа's quarter as Хассир's 630, Генри Джонс's (744) from"
          " Абри's slums as Луиджи's 275; each start says what is taken, and both stay"
          " repeatable, so that nobody who left the Zone is shut out of its chain",
          {t: (real[t].cost_afro, real[t].repeatable, sorted(to for _f, to in ways.get(t, ())),
               "будет списано %d афро" % real[t].cost_afro in real[t].texts[quests.START])
           for t in ZONE_IN},
          {t: (real[ride].cost_afro, 1, [702] if t == 733 else [704], True)
           for t, ride in ZONE_IN.items()})
    check("  ..the Zone's own ways stay free: into the first room (741), back to the cellar (749),"
          " out to Донгола's station (748)",
          [(t, real[t].cost_afro, real[t].has_fee) for t in (741, 748, 749)],
          [(741, 0, False), (748, 0, False), (749, 0, False)])

    # The prison.
    sched = events.table()
    check("the prison: «Выход» (163) leads from 622 up to the yard 159 (and, since 2026-10-14,"
          " from Абу-Хамед's 651 to its yard 177), the gates of 159 down to 618 and 619,"
          " «Поехали!» from the station to the yard and «Назад в Донголу» back",
          (sorted(ways.get(163, ())), sorted(ways.get(634, ())), sorted(ways.get(635, ())),
           sorted(ways.get(632, ())), sorted(ways.get(633, ()))),
          ([(622, 159), (646, 176), (651, 177)], [(159, 618)], [(159, 619)], [(DN_STATION, 159)],
           [(159, DN_STATION)]))
    w = sched.window("prison_dn")
    check("  ..the uprising at the label's 13:00, 17:00 and 21:00 for half an hour, the gates"
          " from a quarter before, the medics for the last five minutes",
          (w.why.startswith("RECOVERED"), sorted(raw_w for raw_w in
                                                  json.load(open(events.schedule_path(),
                                                                 encoding=ENC))["windows"]
                                                  if raw_w.startswith("prison_dn")),
           json.load(open(events.schedule_path(), encoding=ENC))["windows"]["prison_dn"]
           ["daily"],
           [(sched.gates[t][0].name, sched.gates[t][1]) for t in (632, 634, 635, 636)]),
          (True, ["prison_dn", "prison_dn_gates", "prison_dn_medics"],
           ["13:00", "17:00", "21:00"],
           [("prison_dn_gates", "both")] * 3 + [("prison_dn_gates", "hand_in")]))
    check("  ..the prisoners and the godfather drop the armband in 620-622, one each, and the"
          " one keep_in row of 2476 holds both prisons' blocks (since 2026-10-14 Абу-Хамед's"
          " too)",
          (sorted((loc, mob) for (loc, mob), drops in sched.loot.items()
                  if loc in BLOCKS_DN and (BAND, 1, 1.0) in drops),
           [sorted(locs) for types, locs in sched.keep_in if BAND in types]),
          (sorted((loc, mob) for loc in (620, 621, 622) for mob in PRISONERS_DN),
           [sorted(BLOCKS_WH + BLOCKS_DN + [649, 650, 651, 652, 653])]))
    check("  ..the armbands' rows (164-168) name both prisons' prisoners as who drops them"
          " (and since 2026-10-14 Абу-Хамед's)",
          {t: sorted(m for _o, _n, ms in real[t].objs for m in ms) for t in range(164, 169)},
          {t: sorted([1113, 1114, 1115, 1116, 1117, 2173] + PRISONERS_DN
                     + [1118, 1119, 1120, 1121, 1122, 2175])
           for t in range(164, 169)})
    check("  ..Донгола's «Охранник санатория особого режима» (636): Нур-ад-Дин's, handed in to"
          " the southern guard 1795 at the gates, 158's start word for word",
          (real[636].give, real[636].take, raw[636]["start"] == raw[158]["start"],
           real[636].own_texts),
          ([NUR], [1795], True, frozenset(["start"])))

    # The mines' gates, the lotteries, the warehouses.
    check("the mines' gates: down at levels 12-15 from the surface to the control room, up at"
          " any level back",
          ({t: (real[t].level, real[t].max_level, sorted(ways.get(t, ()))) for t in GATES_DOWN},
           {t: (real[t].level, real[t].max_level, sorted(ways.get(t, ()))) for t in GATES_UP}),
          ({t: (12, 15, [v]) for t, v in GATES_DOWN.items()},
           {t: (0, None, [v]) for t, v in GATES_UP.items()}))

    def worth(obj, num, gold):
        return inventory.buy_price(items.params_of(obj), items.root_of(obj), num, gold)

    check("the lotteries: every prize worth less than the ticket (the house wins), the gold"
          " one's prizes gold things",
          ({t: [worth(o, n, gold) < price for o, n, _w in real[t].rew_random]
            for t, (_k, price, gold) in LOTTERIES.items()},
           [o for o, _n, _w in real[722].rew_random if not items.params_of(o).get("g_cost")]),
          ({t: [True] * len(real[t].rew_random) for t in LOTTERIES}, []))
    check("  ..at the tickets' prices: 2400 afro and 3 G (the TRADE package's stalls)",
          {t: worth(ticket, 1, gold) for t, (ticket, _p, gold) in LOTTERIES.items()},
          {t: price for t, (_k, price, _g) in LOTTERIES.items()})
    check("  ..open to the town's band 12-16, the stalls' whole band of buyers, and named for it:"
          " a 15th or 16th who buys a ticket can play it (the original's «(13-14)» left them a"
          " ticket no row took, the gold one lost whole)",
          ({t: (real[t].level, real[t].max_level, real[t].name) for t in LOTTERIES},
           tuple(shop_bands.band(50)), tuple(shop_bands.band(103))),
          ({721: TOWN_BAND + ("Лотерея Донголы (12-16)",),
            722: TOWN_BAND + ("Золотая Лотерея Донголы (12-16)",)}, TOWN_BAND, TOWN_BAND))
    with open(os.path.join(ROOT, "data", "holdings.json"), encoding=ENC) as fh:
        sites = json.load(fh)["sites"]
    check("the warehouses: three sites of data/holdings.json, their boxes' rows 768-770 the"
          " holders', at the labels' levels, in the window of the boxes (wh_box)",
          ({t: (real[t].holders, sites[s]["loc"], sites[s]["boss"], sites[s]["box"],
                sites[s]["quest"], sites[s]["min_level"], real[t].give, real[t].level,
                sched.gates[t][0].name, real[t].per_day)
            for t, (s, *_r) in BOXES.items()}, holdings.check()),
          ({t: (s, loc, boss, box, t, lvl, [box], lvl, "wh_box", 1)
            for t, (s, loc, boss, box, lvl) in BOXES.items()}, None))

    # Уорхол's collection and «Посланник Смерти».
    pieces = list(range(6593, 6599))
    check("«Коллекция водителя шайтан-арбы» (271): its six pieces named and described, a live"
          " collection, and Уорхол gives 270 and 271 (and since 2026-10-14 the джихад-такси's"
          " 272)",
          ([item_name(o) for o in pieces],
           [names.known(items.DESC_ID_OFFSET + o) for o in pieces],
           [(t, live_) for t, live_, _p in keepsakes.collections()],
           quests.given_by(2259)),
          (["Балонник (Коллекция)", "Прикуриватель (Коллекция)", "Дворники (Коллекция)",
            "Домкрат (Коллекция)", "Ароматизатор (Коллекция)",
            "Зеркало заднего вида (Коллекция)"], [True] * 6,
           [(270, True), (271, True), (272, True)], [270, 271, 272]))
    check("«Посланник Смерти»: part 1 alone (757, the trinket to Лейла), parts 2-6 not in the"
          " table, the why saying why",
          (real[757].give, real[757].take, real[757].obj,
           sorted(t for t, q in real.items() if q.name.startswith("Посланник Смерти ч.")),
           "раскопк" in raw[757]["why"] and "МакКей" in raw[757]["why"]),
          ([1685], [860], 4251, [757], True))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT_NO = free_port()
DB = os.path.join(tempfile.mkdtemp(), "dongola_quests.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("rider", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT_NO), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_START_AFRO="0", LAVA_SEED="11",
           LAVA_POLICY_PORT="0")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


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

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def inhabitants(frames):
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(1.5)


def goto(c, where):
    c.send("userMsg;entry=@/goto %d@;group=0;" % where)
    c.until(lambda f: f[0] == "lcall")
    return inhabitants(arrive(c))


def store():
    return accounts.Store(DB)


def char_id(name):
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def purse(name):
    st = store()
    got = tuple(st.money(char_id(name)))
    st.close()
    return got


def owned(name):
    st = store()
    out = {}
    for r in st.items_of(char_id(name)):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def login(first=False):
    c = Client(testkit.connect(PORT_NO, srv, LOG))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential("rider", "secret"))
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@Rider@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    return c


def take(c, here, npc_type, qtype):
    c.send("q_st;mob=%d;q_idx=%d;" % (here[npc_type][0], quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[npc_type][0], q_id))
    return c.frames(1.0)


def ride(c, got):
    """The lcall a way's hand-in brings, and where the player stands after it."""
    call = named(got, "lcall") or named(c.until(lambda f: f[0] == "lcall", 6), "lcall")
    if not call:
        return None, None, {}
    arrival = arrive(c)
    pos = named(arrival, "lenter")
    return call[0].get("id"), (pos[0].get("pos") if pos else None), inhabitants(arrival)


def money(c, afro):
    c.send("userMsg;entry=@/money %d 0@;group=0;" % afro)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)


try:
    c = login(first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.3)
    st = store()
    cid = char_id("Rider")
    st.save_stats(cid, [("skill", progression.SHOOTING, 12, 0, progression.skill_xp_max(12))])
    st.save_character_state(cid, level=12)
    st.close()
    c = login()

    # --- to Донгола for the fare
    here = goto(c, STATION)
    check("Хассир stands at Вади-Хальфа's station", HASSIR in here, True)
    took, q_id = take(c, here, HASSIR, 630)
    refused = hand_in(c, here, HASSIR, q_id)
    check("«Поездка в Донголу» with no afro: taken, and the hand-in refused -- nobody moves",
          (acks(took), acks(refused)[:1] != [0], bool(named(refused, "lcall"))),
          ([0], True, False))
    money(c, 200)
    went = hand_in(c, here, HASSIR, q_id)
    lid, pos, there = ride(c, went)
    dn = world.location(DN_STATION)
    check("  ..with 200 afro: handed in, the fare gone, and an lcall to Донгола's station,"
          " where Нур-ад-Дин stands",
          (acks(went)[:1], purse("Rider")[0], lid, NUR in there), ([0], 0, DN_STATION, True))
    check("  ..arrived beside the way back (travel.door_arrival on 631's cells)",
          pos == travel.door_arrival(dn, STATION) if pos is not None else None, True)

    # --- back for the fare
    money(c, 150)
    took, q_id = take(c, there, NUR, 631)
    back = hand_in(c, there, NUR, q_id)
    lid, _pos, here = ride(c, back)
    check("«Поездка в Вади Хальфу» at Нур-ад-Дин's: 150 afro, and back at Вади-Хальфа's"
          " station", (acks(took), acks(back)[:1], purse("Rider")[0], lid, HASSIR in here),
          ([0], [0], 0, STATION, True))

    # --- from Абри for the fare
    here = goto(c, PORT)
    money(c, 100)
    took, q_id = take(c, here, LUIGI, 275)
    went = hand_in(c, here, LUIGI, q_id)
    lid, _pos, there = ride(c, went)
    check("Луиджи's «Поездка в Донголу» (275): 100 afro from Абри's Портовый рынок to"
          " Донгола's station", (acks(took), acks(went)[:1], purse("Rider")[0], lid),
          ([0], [0], 0, DN_STATION))

    # --- to Абри by the ticket
    c.send("userMsg;entry=@/give %d 1@;group=0;" % TICKET_TO_ABRI)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)
    took, q_id = take(c, there, NUR, 282)
    went = hand_in(c, there, NUR, q_id)
    lid, _pos, _there = ride(c, went)
    check("«Проездной в Абри» (282): the ticket 6547 taken, no afro, and on to the Портовый"
          " рынок", (acks(took), acks(went)[:1], owned("Rider").get(TICKET_TO_ABRI, 0),
                     purse("Rider")[0], lid), ([0], [0], 0, 0, PORT))
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    with open(LOG, encoding=ENC) as fh:
        text = fh.read()
    check("the server's log has no Traceback", "Traceback" in text, False)
except Exception:
    import traceback
    fails.append("the socket run broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print("  - " + f)
    print("server log: %s" % LOG)
    sys.exit(1)
print("\nall ok")
