"""Вади-Хальфа's wild and leftovers: the wasteland's encounters, the
treasures, the Мясники, the rides to other towns and Уорхол's collection
(encounters.py, keepsakes.py, data/quests.json 250-286).

In process, on the real table and the real world:

  * the rows 250-286 stand right after 2128, in type order; the live ones
    are exactly those the world lets be done from Вади-Хальфа today -- the
    NPC standing in a place of the town's region (or one its doors and quest
    ways reach), every map a dig needs sold by a live row, every creature
    that drops a thing standing there too, every step before it live, a
    ride's far end there -- and the rest are switched off (give/take []),
    each saying why and how to switch it on; the live NPCs stand where
    their rows put them;
  * their texts the original's (VERIFIED in data/build_orig_misc.py where
    the matcher can pin them), every string in the preload, every thing a
    live row names a game thing with a real name and description, none
    premium, no gold paid by a row; a row switched off names, in its
    switch-on text, every thing of its own still to be named first;
  * the digs: each draw worth less, at the gold prices of the stalls, than
    the map it takes costs; Уорхол's reward a Самоучитель 11 times in 19;
  * the rides: built -- a fee or a ticket, a way record naming the closed
    town it leads to -- and not offered, and no way of data/passages.json;
  * encounters: the four bands of the town's camps; never a valley cell,
    never a settlement's cell or one beside it; the nests of the desert
    templates, and the arrival out of every band's reach; the cells a leg
    enters, in order; a pack is after the one it waylaid from his first
    moment in its room, a camp's creatures are not; nothing of a pack comes
    back when killed, a camp's creature does;
  * keepsakes: nothing for a non-collector, nothing after a service, a
    wanted piece for a collector.

On a socket (LAVA_ENCOUNTER_CHANCE=1, LAVA_KEEPSAKE_CHANCE=1):

  * a walk through the town's own cells meets nobody;
  * a walk out in the colonists' wasteland is stopped on its third cell by
    an unasked lcall into that cell's desert -- which the client, as the
    test models Master.playerIntercepted, captions «Переход в локацию» and
    not «На Вас напали» -- where the pack of the camp's band stands on the
    nests and is after him at once: lch;ws=1 and each creature his enemy
    (lch;enemy); the exit window takes him back to the map before any shot,
    the pack's room goes, and a second walk right after meets nobody;
  * Бари sells the map of 5987,1729 and a shovel for 0,20 G, the hole of
    Q_Tresure1 there takes both and gives a treasure; the dig, a task,
    leaves a collector a piece of the Ламантин collection, and the six
    pieces handed to Энди Уорхол give a thing to read.

    LAVA_RES=.../lava/res python3 server/test_halfa_extras.py
"""
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_START",
              "LAVA_ENCOUNTER_CHANCE", "LAVA_ENCOUNTER_COOLDOWN", "LAVA_ENCOUNTERS_PER_DAY",
              "LAVA_KEEPSAKE_CHANCE"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import encounters    # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import keepsakes     # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import orig_texts    # noqa: E402
import progression   # noqa: E402
import quests        # noqa: E402
import rooms         # noqa: E402
import travel        # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


WILD = list(range(250, 287))
MT = world.mob_types()

# --- who and what ---------------------------------------------------------------------
BARI, HOLE, SKULL4, WARHOL = 6520, 6512, 2099, 2259
MAP_Z, MAP_D, SHOVEL = 3892, 5507, 3191
LAMANTIN = list(range(7030, 7036))
BUTCHERS = [939, 940, 941, 942, 943]
# Every row's NPC, where it stands, the things it needs sold by a live row,
# the creatures that drop what it asks for, and a ride's far end.
ZUBERI = {251: (6512, 250, 3892), 252: (6516, 251, 3893), 253: (6517, 252, 3894),
          254: (6518, 253, 3895), 255: (6519, 256, 3906)}
SKULLS = {260 + k: (2096 + k, at, 5504 + k)
          for k, at in enumerate((68, 146, 277, 139, 134, 262, 189))}
RIDES = {273: (105, 37, 187), 274: (1179, 187, 37), 275: (1179, 187, 49), 276: (156, 49, 126),
         277: (740, 126, 49), 278: (740, 126, 58), 279: (105, 37, 187), 280: (1179, 187, 37),
         281: (1179, 187, 49), 282: (156, 49, 187), 283: (156, 49, 126), 284: (740, 126, 49),
         285: (740, 126, 58), 286: (1504, 58, 126)}
TICKETS = {279: 6544, 280: 6545, 281: 6546, 282: 6547, 283: 1567, 284: 1639, 285: 5028,
           286: 5029}
WOULD = {250: dict(npc=BARI, at=36), 256: dict(npc=6511, at=255),
         257: dict(npc=2010, at=105), 258: dict(npc=2011, at=107, needs=[5512]),
         259: dict(npc=806, at=1010),
         267: dict(npc=939, at=164), 268: dict(npc=939, at=164), 269: dict(npc=939, at=164),
         270: dict(npc=WARHOL, at=60), 271: dict(npc=WARHOL, at=60, rides=[279, 280, 281, 282]),
         272: dict(npc=WARHOL, at=60, rides=[283, 284, 285, 286])}
WOULD.update({t: dict(npc=h, at=at, needs=[m, SHOVEL]) for t, (h, at, m) in ZUBERI.items()})
WOULD.update({t: dict(npc=s, at=at, needs=[m, SHOVEL]) for t, (s, at, m) in SKULLS.items()})
WOULD.update({t: dict(npc=d, at=at, target=to) for t, (d, at, to) in RIDES.items()})
LIVE = {250, 251, 263, 270}
PAID_OR_TICKET = {t: TICKETS.get(t) for t in RIDES}


def reached_from(start):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way
    (test_halfa_city's rule)."""
    with open(travel.passages_path(), encoding="utf-8") as fh:
        sides = json.load(fh).get("sides") or {}
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = [r.get("target_loc_id") for _c, r in travel.quest_ways(world.location(lid))]
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


# --- in process: the table ------------------------------------------------------------
try:
    with open(os.path.join(ROOT, "data", "quests.json"), encoding="utf-8") as fh:
        order = [r["type"] for r in json.load(fh)["quests"]]
    real = quests.QUESTS
    rows = {t: real[t] for t in WILD}
    at = order.index(2128)
    check("the rows 250-286 stand right after 2128, in type order",
          order[at + 1:at + 1 + len(WILD)], WILD)
    check("  ..and no other row of the table is in 250-299",
          sorted(t for t in real if 250 <= t < 300), WILD)

    # The town's region: every placed file within sixty cells of its market,
    # and whatever the doors and quest ways lead to from those.
    cx, cy = world.cell_of(35)
    region = {lid for (x, y), lid in world.settlements().items()
              if math.hypot(x - cx, y - cy) <= 60}
    reach = reached_from(region)
    stands = {}                                      # type -> places in reach
    for lid in sorted(reach):
        loc = world.location(lid)
        for _cell, t in loc.spawns:
            stands.setdefault(t, set()).add(lid)
        for t in world.camp_fill(lid):
            stands.setdefault(t, set()).add(lid)
    sold = {o for q in real.values() if q.give for o in
            q.rew_obj + [t for t, _n in q.rew_also] + [t for t, _n, _w in q.rew_random]}

    def on_by_rule(t, memo={}):
        if t in memo:
            return memo[t]
        w, q = WOULD[t], real[t]
        ok = w["at"] in reach and w["at"] in stands.get(w["npc"], set())
        ok = ok and all(n in sold for n in w.get("needs", ()))
        drops = [m for _o, _n, ms in q.objs for m in ms]
        if t in (267, 268, 269):
            # the Мясники: every slot's thing drops from somebody who stands here
            ok = ok and all(ms for _o, _n, ms in q.objs) and all(
                stands.get(m, set()) & reach for m in drops)
        ok = ok and all(on_by_rule(n) for n in q.need_all)
        if "target" in w:
            ok = ok and w["target"] in reach
        if "rides" in w:
            ok = ok and all(on_by_rule(r) for r in w["rides"])
        memo[t] = ok
        return ok

    check("the rows live are those the world lets be done from Вади-Хальфа today: the NPC in a"
          " place of the town's region, the maps sold, the creatures there, the steps before"
          " live, a ride's far end there -- the Мясники, the rides, Хоу Сян's, Камал's and the"
          " other towns' digs switched off",
          sorted(t for t in WILD if on_by_rule(t)), sorted(LIVE))
    check("  ..which is exactly the rows with a giver and a taker in the table",
          sorted(t for t in WILD if rows[t].give or rows[t].take), sorted(LIVE))
    check("  ..each given and taken by its NPC, who stands where the row says",
          {t: (rows[t].give, rows[t].take, WOULD[t]["at"] in stands.get(WOULD[t]["npc"], ()))
           for t in LIVE},
          {t: ([WOULD[t]["npc"]], [WOULD[t]["npc"]], True) for t in LIVE})
    raw = {r["type"]: r for r in quests.table_rows()}
    check("  ..and every row switched off says so and how to switch it on",
          [t for t in WILD if t not in LIVE and not ("SWITCHED OFF" in raw[t]["why"]
                                                     and "switch on" in raw[t]["why"])], [])
    check("the Мясники: blood of the hippies of Абри (191), then parts of Донгола's chiefs, then"
          " of «беженцы» -- a chain, off while its first creatures are not Вади-Хальфа's",
          ([m for _o, _n, ms in rows[267].objs for m in ms], sorted(stands.get(1175, set())),
           rows[268].need_all, rows[269].need_all),
          ([1175, 1176, 5631], [], [267], [268]))

    # the rides: built, and not offered
    for t in RIDES:
        q = rows[t]
        check("ride %d «%s» from %d to %d: %s, a way with an end the region does not reach,"
              " not offered, no way of data/passages.json yet"
              % (t, q.name, RIDES[t][1], RIDES[t][2],
                 "the ticket %d" % TICKETS[t] if t in TICKETS else "a fee"),
              (q.give, q.take, travel.is_quest_way(t),
               raw[t]["way"]["at"] in reach and raw[t]["way"]["target_loc_id"] in reach,
               raw[t]["way"]["at"], q.rew_loc, bool(q.repeatable),
               (q.cost_afro, q.cost_gold) != (0, 0) if t not in TICKETS
               else [o for o, _n, _m in q.objs]),
              ([], [], False, False, RIDES[t][1], 1, True,
               True if t not in TICKETS else [TICKETS[t]]))
    check("  ..the fees the texts name: Абри 100 afro, Вади Хальфа 400, Донгола 100 from Абри"
          " and 0,10 G from Абу-Хамед, Абу-Хамед 0,25 G, Мероэ 0,01 G",
          {t: (rows[t].cost_afro, rows[t].cost_gold) for t in range(273, 279)},
          {273: (100, 0), 274: (400, 0), 275: (100, 0), 276: (0, 25), 277: (0, 10),
           278: (0, 1)})

    # the texts, the strings, the things
    with open(os.path.join(ROOT, "data", "orig_misc.json"), encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts pinned to the original (VERIFIED): every row but the digs whose lines"
          " repeat under other labels, the wiki's collection and Мероэ's pass",
          sorted(t for t in WILD if t in pinned),
          sorted(set(WILD) - {252, 253, 254, 255, 260, 261, 262, 263, 264, 265, 266, 270, 286}))
    check("  ..the Мясники's lines the newest copy (60512-60520)",
          [pinned[t][1:] for t in (267, 268, 269)],
          [[60512, 60513, 60514], [60515, 60516, 60517], [60518, 60519, 60520]])
    orig = orig_texts.quests()
    check("  ..laid over the table's",
          [t for t in WILD for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and rows[t].texts[k] != quests.served(rows[t], k, orig[t][key])], [])
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows.values() for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has (quests.check_items)",
          quests.check_items(), None)
    live_things = sorted({t for q in rows.values() if q.give for _f, t in q.things()})
    check("  ..and every thing a live row names has a name of its own -- the Ламантин pieces"
          " and Дирижер's map named by build_orig_items rule 7i -- and none is premium",
          ([t for t in live_things if names.ALL.get(items.STRING_ID_OFFSET + t, "").startswith(
              ("q", "collection_", "ticket_"))], [t for t in live_things if items.premium(t)]),
          ([], []))
    # A name or description id the client does not know kicks it: a live row
    # may name no such thing, and a row switched off names, in the text that
    # says how to switch it on, every one of its own it would bring in.
    unknown = {t: sorted({o for _f, o in rows[t].things()
                          for sid in (items.STRING_ID_OFFSET + o, items.DESC_ID_OFFSET + o)
                          if not names.known(sid)}) for t in WILD}
    check("  ..with a name and a description the client knows (either missing kicks it)",
          {t: v for t, v in unknown.items() if v and t in LIVE}, {})
    check("  ..and every row switched off says which of its things to name and describe before"
          " it is switched on (the Мясники's parts, the drivers' pieces, the ticket 1639)",
          {t: [o for o in v if str(o) not in raw[t]["why"][raw[t]["why"].find("To switch on"):]]
           for t, v in unknown.items() if v and t not in LIVE},
          {t: [] for t, v in unknown.items() if v and t not in LIVE})
    check("  ..which are those", {t: v for t, v in unknown.items() if v},
          {267: [7123], 268: [7125, 7126, 7127], 269: [7124, 7125, 7126, 7127],
           271: list(range(6593, 6599)), 272: [1639] + list(range(6599, 6605)), 284: [1639]})
    check("  ..Дирижер's map of the camel stables and the collection's pieces, by name",
          [names.ALL[items.STRING_ID_OFFSET + t] for t in [MAP_D] + LAMANTIN[:1]] +
          ["5972х1735" in names.ALL[items.DESC_ID_OFFSET + MAP_D]],
          ["Карта сокровищ", "Планшет (Коллекция)", True])
    check("  ..the living NPCs by their names (the hole of Q_Tresure1 is «Ямка»)",
          [names.ALL.get(t) for t in (BARI, HOLE, SKULL4, WARHOL)],
          ["Бари", "Ямка", "Череп", "Энди Уорхол<br>Старый коллекционер"])
    check("no row pays gold (rew_gold); the map costs 0,20 G; the digs draw gold things only --"
          " the helm, rounds and a kit, an ounce ingot at most",
          ([t for t in WILD if rows[t].rew_gold], rows[250].cost_gold,
           sorted({o for t in list(ZUBERI) + list(SKULLS) for o, _n, _w in rows[t].rew_random}),
           [o for t in list(ZUBERI) + list(SKULLS) for o, _n, _w in rows[t].rew_random
            if not items.params_of(o).get("g_cost") and o not in items.GOLD_INGOTS]),
          ([], 20, [6152, 6156, 6905, 7620, 10649], []))

    def gold_worth(obj, num):
        """What a thing drawn is worth in hundredths of an ounce: an ingot its
        ounces, anything else what a stall sells it for in gold -- the helm at
        the Вещевой рынок, the rounds at the gold ammo stalls' 0,01 G a round
        (items.GOLD_AMMO_ROUND, 2026-09-28; 0,10 G before), the kit."""
        if obj in items.GOLD_INGOTS:
            return items.GOLD_INGOTS[obj] * num
        return inventory.buy_price(items.params_of(obj), items.root_of(obj), num, True)

    worth = {t: round(sum(gold_worth(o, n) * w for o, n, w in rows[t].rew_random)
                      / float(sum(w for _o, _n, w in rows[t].rew_random)), 1)
             for t in list(ZUBERI) + list(SKULLS)}
    check("  ..each dig, live or off, worth less in goods than the map it takes costs -- the"
          " house wins: Зубери's 0,11 G, Дирижер's 0,10 G a dig for 0,20 G",
          ({t: v < rows[250].cost_gold for t, v in worth.items()}, worth[251], worth[263],
           gold_worth(6156, 20), gold_worth(10649, 1), gold_worth(6905, 1)),
          ({t: True for t in worth}, 11.4, 9.7, 20, 625, 6))
    shares = {}
    for o, _n, w in rows[270].rew_random:
        kind = "teacher" if 4312 <= o <= 4322 else "journal" if 416 <= o <= 419 else o
        shares[kind] = shares.get(kind, 0) + w
    check("Уорхол's reward: a Самоучитель 11 times in 19, the wiki's share -- its four chapters,"
          " in no objects.xml row, left to the journal's four parts",
          shares, {"teacher": 11, "journal": 8})
    check("Зубери's dig place stands on 5987,1729 (data/settlements_verified.json)",
          (world.location_at(5987, 1729), world.cell_of(250)), (250, (5987, 1729)))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())

# --- in process: encounters and keepsakes ----------------------------------------------
try:
    got = sorted((b.camp, b.lo, b.hi, all(b.lo <= mobs.stats(t).level <= b.hi for t in b.types))
                 for b, _r in encounters.bands())
    check("the town's wasteland belongs to its four camps, each band's creatures in its band",
          got, [(80, 0, 2, True), (81, 2, 4, True), (84, 4, 6, True), (85, 6, 8, True)])
    x0, y0, x1, y1 = world.NOOB_VALLEY
    check("never in the Nubian valley",
          [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
           if encounters.band_at(x, y)], [])
    town = [c for c, lid in world.settlements().items()
            if math.hypot(c[0] - 5968, c[1] - 1727) <= 60]
    check("never on a settlement's cell or one beside it",
          [(x + dx, y + dy) for x, y in town for dx in (-1, 0, 1) for dy in (-1, 0, 1)
           if encounters.band_at(x + dx, y + dy)], [])
    ring = [(x, y) for x in range(5930, 6030) for y in range(1690, 1775)
            if encounters.band_at(x, y)]
    check("  ..but on the open wasteland around the town, and nowhere far from it",
          (len(ring) > 1500, encounters.band_at(5900, 1800), encounters.band_at(5862, 1840)),
          (True, None, None))
    check("the nests of the four desert templates the map lays: two each, on the grid",
          [len(encounters.nests(world.location(world.pack(5950, y)))) for y in
           range(1700, 1704)], [2, 2, 2, 2])
    # The pack is after him from his first moment in: where he arrives, over
    # any edge of any template of the ring, none of the four bands reaches
    # him yet -- the step back out over that edge is his before any shot.
    ring_locs = {}
    for rx, ry in ring:
        loc = world.location(world.pack(rx, ry))
        ring_locs.setdefault(loc.file, loc)
    near = min(mobs.hex_distance(travel.arrival_cell(loc, side), n, loc.width)
               for loc in ring_locs.values() for side in (travel.N, travel.S, travel.E, travel.W)
               for n in encounters.nests(loc))
    longest = max(mobs.stats(t).range for b, _r in encounters.bands() for t in b.types)
    check("  ..and the arrival, over any edge of any of them, out of every band's reach",
          (len(ring_locs), near > longest, longest), (4, True, 10))
    legs = encounters.crossings(5950.0, 1710.0, 5953.5, 1710.0, 0.35)
    check("the cells a leg enters, in order, with the seconds to each",
          [(c, round(s, 1)) for s, c in legs],
          [((5951, 1710), 2.9), ((5952, 1710), 5.7), ((5953, 1710), 8.6)])
    check("the edge a walker comes in over: behind him",
          [encounters.entered_over(*v) for v in ((1, 0), (-1, 0), (0, 1), (0, -1))],
          ["W", "E", "N", "S"])

    class Rng:
        calls = 0

        def random(self):
            Rng.calls += 1
            return 0.0

        def choice(self, seq):
            return seq[0]

    # The legs, on a session of the test's own: where the first roll falls,
    # that a leg laid again over the same cells does not roll them again,
    # and that a band grey to the player leaves him be.
    import asyncio

    class Walker:
        char_id, closed, on_map, nick = 99999, False, True, "probe"

        def __init__(self, level):
            self.level, self.gx, self.gy, self.leg = level, 0.0, 0.0, None

        def skill_level(self):
            return self.level

        def transport_now(self):
            return None

    x, y = next((x, y) for y in range(1700, 1720) for x in range(5940, 5965)
                if all((encounters.band_at(x + k, y) or encounters.Band(0, 0, 0, 0, ())).camp
                       == 80 for k in range(3, 7)))

    async def legs():
        enc = encounters.Encounters(None)
        old_rng, old_chance = encounters.RNG, encounters.CHANCE
        encounters.RNG, encounters.CHANCE = Rng(), 1.0
        try:
            out = []
            for level in (0, 9):
                s = Walker(level)
                s.gx, s.gy = float(x), float(y)
                s.leg = (0.0, s.gx, s.gy, 0.35, 0.0)
                Rng.calls = 0
                enc.arm(s, s.gx, s.gy, s.gx + 6, s.gy, 0.35)
                first = Rng.calls
                handle = enc.armed.get(s)
                when = (round(handle.when() - asyncio.get_running_loop().time(), 1)
                        if handle else None)
                enc.arm(s, s.gx, s.gy, s.gx + 6, s.gy, 0.35)
                out.append((first, Rng.calls - first, when))
                enc.disarm(s)
            return out
        finally:
            encounters.RNG, encounters.CHANCE = old_rng, old_chance

    check("a leg into the colonists' wasteland rolls its third cell first (the grace of two),"
          " and falls there, 3.3 cells on; laid again, it rolls nothing again; at the ninth"
          " level, every colonist grey, nothing is rolled at all",
          asyncio.run(legs()), [(1, 0, 9.4), (0, 0, None)])

    # The pack's room against a camp's, on combat.RoomCombat itself: who is
    # after a newcomer, and what comes back after a kill.
    class Loot:
        """The calls of the store a corpse makes: its bag's rows, and where
        they lie (combat.RoomCombat.add_to_bag)."""
        serial = 0

        def create_item(self, owner, type_id, root, **fields):
            Loot.serial += 1
            return {"uniq": Loot.serial, "type_id": type_id}

        def lay_down(self, things, place, cell):
            pass

    class Newcomer(combat.Fighter):
        """What RoomCombat.player_entered and aggro read of a combat.Fighter."""
        dead, eid = False, 7

        def __init__(self):
            super().__init__(self)
            self.sent = []

        def send(self, name, **params):
            self.sent.append((name, params))

    colonists = encounters.band_at(x + 3, y)

    def pack_room(ambush):
        rs = rooms.Rooms(MT)
        lid = world.pack(x + 3, y)
        room = rs.get((lid, "encounter", 1))
        room.ambush = ambush
        for k, nest in enumerate(encounters.nests(world.location(lid))):
            room.npcs[rs.ids.npc()] = rooms.NPC(nest, colonists.types[k], world.MOB)
        return room, combat.RoomCombat(room, Loot())

    async def packs():
        out = []
        old = combat.CORPSE_DELAY, combat.RESPAWN_DELAY
        combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.01, 0.05
        try:
            for ambush in (80, None):
                room, rc = pack_room(ambush)
                who = Newcomer()
                rc.player_entered(who)
                rc.timer.cancel()
                after = [m.target is who for m in rc.mobs.values()]
                marked = sorted(p["enemy"] for n, p in who.sent if n == "lch" and "enemy" in p)
                mob = next(iter(rc.mobs.values()))
                mob.target = None
                rc.kill(mob, None)
                await asyncio.sleep(0.3)
                out.append((after, room.ws, marked == sorted(rc.mobs), mob.alive,
                            mob.eid in room.npcs))
        finally:
            combat.CORPSE_DELAY, combat.RESPAWN_DELAY = old
        return out

    check("a pack's room (Room.ambush): every creature after the newcomer the moment he is in,"
          " the room at war, each marked his enemy; one killed stays dead past the respawn --"
          " and a camp's room, the control: nobody after him from afar, the killed one back",
          asyncio.run(packs()),
          [([True, True], True, True, False, False), ([False, False], False, False, True, True)])

    old = keepsakes.CHANCE
    keepsakes.CHANCE = 1.0
    try:
        check("keepsakes: the pieces of the live collections only (Ламантин's; the drivers' are"
              " switched off)", keepsakes.pool(), LAMANTIN)
        check("  ..nothing for a hand-in by somebody who collects nothing",
              keepsakes.find(real[251], set(), Rng()), [])
        check("  ..nothing after a service (the map bought) or a collection's own hand-in",
              (keepsakes.find(real[250], set(LAMANTIN), Rng()),
               keepsakes.find(real[270], set(LAMANTIN), Rng())), ([], []))
        check("  ..a piece the collector still wants after a task",
              keepsakes.find(real[251], {7033, 7034}, Rng()), [(7033, 1)])
    finally:
        keepsakes.CHANCE = old
except Exception:
    import traceback
    fails.append("encounters in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_extras.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("walker", "secret")
_store.register("digger", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_SEED="11", LAVA_POLICY_PORT="0",
           LAVA_ENCOUNTER_CHANCE="1", LAVA_ENCOUNTER_COOLDOWN="600",
           LAVA_KEEPSAKE_CHANCE="1")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


class Client:
    """A socket that also keeps the two flags the client's loader caption
    hangs on (Master.as): userCallChangeWorld, up from its own chWorld
    (changeWorld) until the next lenter (enterLocation), and the state an
    lcall lands in -- «Внимание! На Вас напали» only for an lcall on the map
    with the flag down (playerIntercepted, LocGen.loadSources)."""

    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.user_call, self.state, self.captions = False, "enter", []

    def send(self, text):
        if text.startswith("chWorld;"):
            self.user_call, self.state = True, "cw"
        elif text.startswith("lenter;"):
            # locLoaded sends it and calls enterLocation at once
            self.user_call = False
        self.s.sendall(text.encode(ENC) + b"\x00")

    def model(self, frames):
        for name, _p in frames:
            if name == "gmap":
                self.state = "gm"
            elif name == "lcall":
                self.captions.append("Внимание! На Вас напали" if self.state == "gm"
                                     and not self.user_call else "Переход в локацию")
                self.state = "cw"
            elif name == "lenter":
                self.state, self.user_call = "loc", False
        return frames

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
        return self.model([decode(f.decode(ENC)) for f in parts if f])

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
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


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def inhabitants(frames):
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def login(login_name, first=False, pers=None):
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential(login_name, "secret"))
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@%s@;" % pers)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.frames(1.5)
    return c


def goto(c, *where):
    c.send("userMsg;entry=@/goto %s@;group=0;" % " ".join(str(w) for w in where))
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return inhabitants(c.frames(2))


def to_map(c):
    c.send("chWorld;")
    return c.until(lambda f: f[0] == "gmap", 3)


def store():
    return accounts.Store(DB)


def char_id(name):
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def owned(name):
    st = store()
    out = {}
    for r in st.items_of(char_id(name)):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def gold(name):
    st = store()
    got = tuple(st.money(char_id(name)))
    st.close()
    return got[1]


try:
    # --- the walker: the town, then the wasteland ----------------------------------------
    w = login("walker", first=True, pers="Walker")
    # The town's own row of cells, the pier to the arenas: settlements and their doorsteps.
    goto(w, 5965, 1728)
    to_map(w)
    w.send("moveTo;dx=600;dy=0;")
    walked = w.until(lambda f: f[0] == "userMove" and f[1].get("vx") == 0, 30)
    check("six cells through the town's own row, pier to arenas: stopped where the leg ends,"
          " and nobody waylays him there", ("lcall" in [n for n, _p in walked],
                                            bool(named(walked, "userMove"))), (False, True))

    # The colonists' wasteland: a cell whose next cells east are theirs, open desert all.
    start = next((x, y) for y in range(1700, 1720) for x in range(5940, 5965)
                 if world.location_at(x, y) == world.pack(x, y) and world.passable(x, y)
                 and all(world.passable(x + k, y) for k in range(1, 7))
                 and all((encounters.band_at(x + k, y) or encounters.Band(0, 0, 0, 0, ()))
                         .camp == 80 for k in (3, 4, 5, 6)))
    band = encounters.band_at(start[0] + 3, start[1])
    goto(w, *start)
    to_map(w)
    w.send("moveTo;dx=600;dy=0;")
    got = w.until(lambda f: f[0] == "lcall", 30)
    lcall = named(got, "lcall")
    check("walking out in the colonists' wasteland: an lcall the client did not ask for (no"
          " cmdAck before it, the figure stopped first) into the desert of the third cell from"
          " where he stepped onto the map",
          ([n for n, _p in got if n in ("cmdAck", "userMove", "lcall")][-2:],
           lcall[0]["id"] if lcall else None, lcall[0].get("ws") if lcall else None),
          (["userMove", "lcall"], world.pack(start[0] + 3, start[1]), 0))
    check("  ..which the client's loader captions like any other: his own chWorld to the map"
          " keeps userCallChangeWorld up (Master.playerIntercepted) -- «На Вас напали» never"
          " shows, so the room has to say it", w.captions[-1:], ["Переход в локацию"])
    w.send("lenter;accept=1;")
    # A second at most: the nearest of the pack is 25 cells off and walks one
    # in 0,2 s, and none of the colonists shoots beyond 10.
    arrival = w.frames(1.0)
    pack = inhabitants(arrival)
    nests = encounters.nests(world.location(world.pack(start[0] + 3, start[1])))
    check("  ..where the pack of the camp's band stands on the nests, one on each",
          (sum(len(v) for v in pack.values()), all(t in band.types for t in pack),
           sorted(p["pos"] for p in named(arrival, "lch") if "newUser" in p)),
          (len(nests), True, sorted(nests)))
    check("  ..and is after him the moment he is in: the room at war (lch;ws=1 -- the battle"
          " track, the fight's bar) and each of the pack marked his enemy (lch;enemy)",
          ([p["ws"] for p in named(arrival, "lch") if "ws" in p],
           sorted(p["enemy"] for p in named(arrival, "lch") if "enemy" in p)),
          ([1], sorted(i for ids in pack.values() for i in ids)))
    pos = named(arrival, "lenter")[0]["pos"]
    width = world.location(world.pack(start[0] + 3, start[1])).width
    check("  ..he arrives on the edge he walked in over, far out of their reach",
          (pos % width <= travel.EDGE_BAND,
           min(mobs.hex_distance(pos, n, width) for n in nests) > 10), (True, True))
    w.send("chWorld;")
    back = w.until(lambda f: f[0] == "gmap", 3)
    check("  ..and steps straight back out -- the exit window of that edge, «на карту», which"
          " ws=1 does not grey: no shot has come, and the map is his again",
          [n for n, _p in back if n in ("cmdAck", "gmap")][:2], ["cmdAck", "gmap"])
    time.sleep(0.3)
    with open(LOG, encoding="utf-8") as fh:
        log_text = fh.read()
    check("  ..the pack's room goes with him",
          ("waylaid on %d,%d" % (start[0] + 3, start[1]) in log_text,
           "the pack of %d,%d is gone" % (start[0] + 3, start[1]) in log_text), (True, True))
    w.send("moveTo;dx=600;dy=0;")
    again = w.until(lambda f: f[0] == "userMove" and f[1].get("vx") == 0, 30)
    check("  ..and a walk right after meets nobody: he is left in peace for a while",
          "lcall" in [n for n, _p in again], False)
    w.send("logout;")
    w.frames(0.3)
    w.s.close()

    # --- the digger: a treasure and a collection ------------------------------------------
    d = login("digger", first=True, pers="Digger")
    d.send("logout;")
    d.frames(0.3)
    d.s.close()
    time.sleep(0.3)
    st = store()
    cid = char_id("Digger")
    st.save_stats(cid, [("skill", progression.SHOOTING, 5, 0, progression.skill_xp_max(5))])
    st.save_character_state(cid, level=5)
    st.close()
    d = login("digger")
    d.send("userMsg;entry=@/money 0 100@;group=0;")
    d.until(lambda f: f[0] == "userMsg")
    d.frames(0.3)

    here = goto(d, 60)
    d.send("q_st;mob=%d;q_idx=%d;" % (here[WARHOL][0], quests.given_by(WARHOL).index(270)))
    took = d.frames(0.8)
    coll_id = [p["q_id"] for n, p in took if n.startswith("q_di_")]
    check("Энди Уорхол gives his Ламантин collection", acks(took), [0])

    here = goto(d, 36)
    d.send("q_st;mob=%d;q_idx=%d;" % (here[BARI][0], quests.given_by(BARI).index(250)))
    took = d.frames(0.8)
    map_id = [p["q_id"] for n, p in took if n.startswith("q_di_")]
    # Zuberi's map is first in rew_obj; the client sends its original index.
    d.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[BARI][0], map_id[0] if map_id else 0))
    bought = d.frames(1.0)
    have = owned("Digger")
    check("Бари sells Зубери's map of 5987,1729 with a sapper shovel, for 0,20 G",
          (acks(took), acks(bought), have.get(MAP_Z), have.get(SHOVEL), gold("Digger")),
          ([0], [0], 1, 1, 100 - 20))

    here = goto(d, 5987, 1729)
    check("  ..and on 5987,1729 stands Q_Tresure1 with its hole", HOLE in here, True)
    d.send("q_st;mob=%d;q_idx=%d;" % (here[HOLE][0], quests.given_by(HOLE).index(251)))
    took = d.frames(0.8)
    dig_id = [p["q_id"] for n, p in took if n.startswith("q_di_")]
    dig_di = [p for n, p in took if n.startswith("q_di_")]
    d.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[HOLE][0], dig_id[0] if dig_id else 0))
    dug = d.frames(1.0)
    have = owned("Digger")
    treasure = [t for t in (10649, 6156, 6905) if have.get(t)]
    pieces = [t for t in LAMANTIN if have.get(t)]
    check("  ..the dig: the map and the shovel in the bag make it complete, both stay in the"
          " hole, and the chest holds one of Зубери's treasures",
          (acks(took), dig_di[-1].get("complete") if dig_di else None, acks(dug),
           have.get(MAP_Z, 0), have.get(SHOVEL, 0), len(treasure)),
          ([0], 1, [0], 0, 0, 1))
    check("  ..and the dig, a task, leaves the collector one piece he wants",
          len(pieces), 1)

    for t in LAMANTIN:
        if t not in pieces:
            d.send("userMsg;entry=@/give %d 1@;group=0;" % t)
            d.until(lambda f: f[0] == "userMsg")
    d.frames(0.5)
    here = goto(d, 60)
    d.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[WARHOL][0], coll_id[0] if coll_id else 0))
    done = d.frames(1.0)
    have = owned("Digger")
    check("the six pieces to Энди Уорхол: the collection is handed in, the pieces gone, a"
          " thing to read in their place",
          (acks(done), [t for t in LAMANTIN if have.get(t)],
           len([t for t in list(range(4312, 4323)) + [416, 417, 418, 419] if have.get(t)])),
          ([0], [], 1))
    d.send("logout;")
    d.frames(0.3)
    d.s.close()
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
