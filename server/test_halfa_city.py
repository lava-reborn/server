"""Вади-Хальфа's town chains of the old edition (the owner's «займись фулл
восстановлением Вади-Хальфы», 2026-09-28), types 180-237 of data/quests.json:

  Бари    «Билли Джей», «Курьер» (Умар's parcel, once a day), «Медик Умар»
          (the parcel and a ДСР kit: the Вади-Хальфа steps of the B81 web)
  Выборы  Нильсон -> Мауризио -> Мария (seven Негодяи, books, lamp and
          kerosene, writing things and a ruler) -> Мауризио (grain) ->
          Нильсон -> Фрэнк (the bandit chief's head, the still) -> Шихаб
          (veterans, camel feed, Горбик, dogs) -> Фрэнк -> Нильсон -> Климов
          (the robbers at his door, the turrets' transmitter, the seeds) ->
          Нильсон, twenty-five steps
  кино    «Индийское кино»: the ring, Каспар's thousand afro (a fee), Вивек,
          «Быть или не быть» -- one drop or two, rows that shut each other,
          the two-drop branch switched off until the other side of the
          graveyard (688) is reached -- «Посланник смерти», «Дар»
  single  «Шутка висельника»; «Просьба о помощи» (the lent shawarma) and the
          son's daily raid -- switched off until a way leads into the mine
  Натти   «Странное послание» to Джо, «Веселый праздник» and its seven [Q]
          guns for Магриб tokens -- six of them switched off until their
          guns have numbers of their own --; «Великая проблема», the
          journal's four parts put together from pages (assemblies, walked
          again when a part is lost), «"Верблюжьи холмы"»; «Театр жизни»

In process, on the real table: the rows, their givers and takers, chain,
kinds and pay; their texts the original's (data/orig_misc.json, data/
build_orig_misc.py VERIFIED) laid over; every string id preloaded and in the
launcher's table; every thing a game thing, named, never premium
(quests.check_items too); every weapon a live row pays one with numbers of
its own, of the class its name says; the rows switched off exactly those
whose way on the world does not have yet (the other side of the graveyard,
the mine's tiers, the guns' numbers); every thing one row pays and another
asks for kept at a death or paid again; every giver and taker standing
where its quest sends the player, every kill and every carrier of a slot
drop standing where the quest's mark is, and a live kill where a player
gets; the bandit chief's head falling from his body only for somebody whose
«Фрэнк (часть 2)» is open and short of it (a real kill in RoomCombat);
«Быть или не быть»'s two rows shutting each other.

On a socket, on a copy of the table with the two-drop row switched on (the
way test_quest_mechanics holds «В Хальфу!»): «Выборы» walked end to end --
every take and hand-in through the server, the things put in the bag with
/give, the kills credited through quests.kill_progress on the server's own
database, as a fight's count_kill does --; Каспар's fee refused while the
purse is short and taken once it is not; the branches of «Быть или не быть»
shutting each other and the one-drop vial made at the table; thirty tokens
for the Маузер C96 (Q), the other six guns not offered; four pages for the
journal's first part, the part lost, put together again from new pages and
«"Верблюжьи холмы"» handed in all the same.

    LAVA_RES=.../lava/res python3 server/test_halfa_city.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK", "LAVA_START"):
    os.environ.pop(_knob, None)

# The two-drop row of «Быть или не быть» (213) is switched off in the real
# table: its way on stands in «Кладбище по ту сторону» (688), which nothing
# reaches yet. The run holds it on a copy with its giver and taker back.
BRANCH_A, BRANCH_B = 212, 213
_REAL = os.path.join(os.path.dirname(HERE), "data", "quests.json")
with open(_REAL, encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
REAL_ROWS = {r["type"]: r for r in _TABLE["quests"]}
for _row in _TABLE["quests"]:
    if _row["type"] == BRANCH_B:
        _row["give"], _row["take"] = [1685], [1692]
_ON = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(_ON, "w", encoding="utf-8") as _fh:
    json.dump(_TABLE, _fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = _ON

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- who and what ---------------------------------------------------------------------
BARI, UMAR, NILSON, MAURIZIO, MARIA, FRANK, SHIHAB, KLIMOV = 6520, 858, 694, 6522, 697, 698, 653, 834
GORBIK, OLD_WOMAN, KASPAR, VIVEK, TABLE, HANGMAN, SON, NATTY, JOE = (816, 1685, 49, 1691, 1692,
                                                                   1657, 1014, 106, 103)
WHERE = {BARI: 36, UMAR: 52, NILSON: 35, MAURIZIO: 60, MARIA: 119, FRANK: 104, SHIHAB: 102,
         KLIMOV: 140, GORBIK: 138, OLD_WOMAN: 37, KASPAR: 36, VIVEK: 70, TABLE: 37,
         HANGMAN: 104, SON: 41, NATTY: 37, JOE: 62}
B81 = [180, 181, 182]
ELECTION = list(range(183, 208))
CINEMA = list(range(208, 219))
SINGLES = [219, 220, 221]
NATTY_JOE = list(range(222, 238))
ALL = B81 + ELECTION + CINEMA + SINGLES + NATTY_JOE
GUNS = {224: (30, 25666), 225: (50, 26087), 226: (80, 25556), 227: (200, 25145),
        228: (120, 25851), 229: (150, 25335), 230: (180, 45140)}
PARTS = {233: (420, 416), 234: (424, 417), 235: (428, 418), 236: (432, 419)}
HEAD, CHIEF, FRANK2 = 1322, 696, 193
FEE_Q, VIAL, ONE_DROP, TWO_DROPS, SYRINGE = 209, 3957, 3958, 3959, 3552
SHAWARMA, TOKEN = 3189, 286
MG_PATROL = list(range(301, 312))
LUSHER = [271, 272, 273, 274, 276, 277, 278, 279, 280, 281, 282, 285, 336]

GIVE_TAKE = {
    180: (BARI, BARI), 181: (BARI, BARI), 182: (UMAR, UMAR),
    183: (NILSON, NILSON), 184: (NILSON, MAURIZIO), 185: (MAURIZIO, MARIA),
    186: (MARIA, MARIA), 187: (MARIA, MARIA), 188: (MARIA, MARIA), 189: (MARIA, MAURIZIO),
    190: (MAURIZIO, MAURIZIO), 191: (MAURIZIO, NILSON), 192: (NILSON, FRANK),
    193: (FRANK, FRANK), 194: (FRANK, FRANK), 195: (FRANK, SHIHAB), 196: (SHIHAB, SHIHAB),
    197: (SHIHAB, SHIHAB), 198: (SHIHAB, GORBIK), 199: (GORBIK, SHIHAB),
    200: (SHIHAB, SHIHAB), 201: (SHIHAB, FRANK), 202: (FRANK, NILSON),
    203: (NILSON, KLIMOV), 204: (KLIMOV, MAURIZIO), 205: (MAURIZIO, KLIMOV),
    206: (KLIMOV, KLIMOV), 207: (KLIMOV, NILSON),
    208: (OLD_WOMAN, OLD_WOMAN), 209: (OLD_WOMAN, KASPAR), 210: (KASPAR, VIVEK),
    211: (VIVEK, OLD_WOMAN), 212: (OLD_WOMAN, TABLE), 213: (OLD_WOMAN, TABLE),
    214: (VIVEK, VIVEK), 215: (OLD_WOMAN, OLD_WOMAN), 216: (VIVEK, VIVEK),
    217: (VIVEK, VIVEK), 218: (VIVEK, OLD_WOMAN),
    219: (HANGMAN, HANGMAN), 220: (FRANK, SON), 221: (SON, SON),
    222: (NATTY, JOE), 223: (JOE, JOE), 231: (NATTY, NATTY), 232: (NATTY, NATTY),
    237: (NATTY, NATTY)}
GIVE_TAKE.update({t: (JOE, JOE) for t in GUNS})
GIVE_TAKE.update({t: (NATTY, NATTY) for t in PARTS})
CHAIN = {t: [t - 1] for t in ELECTION[1:]}
CHAIN.update({180: [], 181: [180], 182: [181], 183: [], 208: [], 209: [208], 210: [209],
              211: [210], 212: [211], 213: [211], 214: [212], 215: [214], 216: [213],
              217: [216], 218: [217], 219: [], 220: [], 221: [220], 222: [], 223: [222],
              231: [], 232: [231], 233: [231], 234: [233], 235: [234], 236: [235], 237: []})
CHAIN.update({t: [223] for t in GUNS})
KILLS = {185: ([693], [7], 119), 196: ([298], [3], 86), 200: ([723], [10], 138),
         203: ([722], [10], 140), 217: ([1694], [4], 688), 221: ([838], [5], 613),
         237: ([336], [10], 81)}
# Where a row's way on stands where no way leads yet, the row is switched off
# (give and take []) until one does: the two-drop branch behind the other side
# of the graveyard (688) -- as the son's raid on the miners of the mine's
# tiers was until stage 3 opened them (the ring's Ефрейторы at the entrances
# stood in for the miners until then). A gun with no numbers of its own the
# same, until it has them.
OTHER_SIDE = 688
MINE_TIERS = (613, 617, 1012, 1024)
RAID = 221
# The word after the name's '$' and the class a gun of it is (items.WEAPON_CLASS).
CLASS_WORD = {"Пистолет": items.PISTOL, "Дробовик": items.SHOTGUN, "Автомат": items.ASSAULT,
              "Винтовка": items.RIFLE, "Пулемет": items.MACHINEGUN,
              "Пистолет-пулемёт": items.SMG}
PAYS = {182: (5388, 200), 181: (5382, 0), 185: (None, 200), 186: (None, 250), 187: (None, 300),
        188: (None, 300), 190: (None, 300), 191: (None, 500), 193: (None, 400),
        194: (3190, 200), 196: (None, 300), 197: (None, 300), 199: (None, 200),
        200: (None, 400), 202: (None, 500), 203: (None, 400), 205: (None, 400),
        206: (None, 400), 207: (None, 1000), 208: (None, 5000), 211: (VIAL, 0),
        212: (ONE_DROP, 0), 213: (TWO_DROPS, 0), 215: (SYRINGE, 0), 218: (SYRINGE, 0),
        219: (None, 300), 220: (None, 100), 221: (None, 400), 232: (None, 1000),
        237: (None, 300)}
PAYS.update({t: (gun, 0) for t, (_n, gun) in GUNS.items()})
PAYS.update({t: (chapter, 0) for t, (_p, chapter) in PARTS.items()})
REPEATABLE = {181: 1, 182: 1, 221: 1}          # type -> per_day
REPEATABLE.update({t: 0 for t in PARTS})      # the journal's assemblies, any number of times
MT = world.mob_types()


def pack(gx, gy):
    return (gx << 13) | gy


def has_record(type_id):
    """Numbers of its own: a wiki table, a hand-made one, or the set file's
    -- not items.designed_info's default frame alone."""
    return (type_id in items.wiki() or type_id in items.loot_manual()
            or type_id in items.coldarm_manual() or type_id in items.heal_manual()
            or bool(sets.item(type_id)))


def reached_from(start):
    """Every place a player gets to from start, start among them: through a
    door the server follows (travel.door, travel.DOOR_CONFIDENCE), a side
    exit of data/passages.json 'sides', or a quest way (travel.quest_ways)."""
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
    real = quests.load(_REAL)
    rows = {t: quests.get(t) for t in ALL}
    # The places the quests send the player to, and where he gets from those
    # on the map: what decides which rows are switched off.
    places = sorted(set(WHERE.values()) | {l for _m, _n, l in KILLS.values()} |
                    {81, 83, 84, 85, 86, 87, 120, 122, 137, 139, 141, 154, 158, 160})
    on_map = {lid for lid in places if world.cell_of(lid) is not None}
    reach = reached_from(on_map)
    OFF = ({BRANCH_B} if OTHER_SIDE not in reach else set()) | \
        ({RAID} if not reach & set(MINE_TIERS) else set()) | \
        {t for t, (_n, gun) in GUNS.items() if not has_record(gun)}

    def live(t):
        """Offered to somebody: a giver in the real table, and every step
        before it live too."""
        return bool(real[t].give) and all(live(n) for n in real[t].need_all)

    # From 238 on the rows are stage 3's, appended after these.
    check("the fifty-eight town quests are in the table, 180-237",
          sorted(t for t in real if 180 <= t <= 237), ALL)
    check("  ..appended after the valley's 67, in type order",
          [r["type"] for r in _TABLE["quests"] if r["type"] <= 237][-len(ALL):], ALL)
    check("  ..given and taken by the NPCs the texts, the wiki and each why name, but those"
          " switched off (the two-drop row is on in the run's copy)",
          {t: (q.give, q.take) for t, q in rows.items()},
          {t: ([], []) if t in OFF - {BRANCH_B} else ([g], [k])
           for t, (g, k) in GIVE_TAKE.items()})
    check("the rows switched off in the real table (give and take []) are exactly those whose"
          " way on the world does not have yet: the two drops while nothing reaches 688, the"
          " son's raid while nothing reaches the mine's tiers, a gun with no numbers of its own"
          " -- one listed in got alone is ready: give it back its NPC (its why says which)",
          sorted(t for t in ALL if not real[t].give and not real[t].take), sorted(OFF))
    # The rule turns by itself: on a table of the test's own (LAVA_PASSAGES),
    # a door the server follows from the mine's entrance and a side between
    # two tiers reach the miners, and the raid would then have to be on.
    probe = os.path.join(tempfile.mkdtemp(), "passages.json")
    with open(probe, "w", encoding="utf-8") as fh:
        json.dump({"doors": {"154": {"b": {"confidence": "high", "target_loc_id": 613,
                                           "why": "a probe"}}},
                   "sides": {"613": {"E": {"target_loc_id": 1024, "why": "a probe"}}}}, fh)
    os.environ["LAVA_PASSAGES"] = probe
    travel._PASSAGES = None
    travel._WAYS.clear()
    try:
        probed = reached_from({154})
    finally:
        os.environ.pop("LAVA_PASSAGES", None)
        travel._PASSAGES = None
        travel._WAYS.clear()
    check("  ..and turns once a way leads in: a door from the entrance and a side between the"
          " tiers reach the miners (a table of the test's own)",
          sorted(probed & set(MINE_TIERS)), [613, 1024])
    check("  ..in the chain the texts draw", {t: q.need_all + q.need_any for t, q in rows.items()},
          CHAIN)
    check("  ..one-offs, but Бари's courier, Умар's kit and the son's raid (once a day) and the"
          " journal's four assemblies (as often as a part is lost)",
          {t: q.per_day for t, q in rows.items() if q.repeatable}, REPEATABLE)
    check("  ..no gold among them, nothing beside the reward; the assemblies are services (no"
          " day's task, no place in the journal's count), nothing else",
          ([t for t, q in rows.items() if q.rew_gold or q.rew_also or q.rew_random],
           sorted(t for t, q in rows.items() if q.service)), ([], sorted(PARTS)))
    check("  ..paying what each row's why says",
          {t: ((q.rew_obj[0] if q.rew_obj else None), q.rew_afro) for t, q in rows.items()
           if q.rew_obj or q.rew_afro}, PAYS)
    check("  ..the kills: the creatures and the counts",
          {t: (q.mobs_kill, q.num_kill) for t, q in rows.items() if q.kind == quests.KILL_MOBS},
          {t: (m, n) for t, (m, n, _l) in KILLS.items()})
    orig = orig_texts.quests()
    with open(os.path.join(os.path.dirname(HERE), "data", "orig_misc.json"),
              encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts are the original's (data/orig_misc.json)", [t for t in ALL if t not in pinned],
          [])
    check("  ..laid over the table's",
          [t for t in ALL for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and rows[t].texts[k] != quests.served(rows[t], k, orig[t][key])], [])
    check("  ..each step's own lines: «Медик Умар» the Вади-Хальфа copy, the guns their names",
          (pinned[182], [pinned[t][0] for t in sorted(GUNS)], pinned[184][1]),
          ([41396, 41397, 41398, 41399], [47336, 47340, 47342, 47344, 47346, 47348, 47350], 47401))
    check("  ..the guns' names as the original writes them",
          [rows[t].name for t in (224, 227)],
          ["Веселый праздник: Маузер C96[Q][2]", "Веселый праздник: Lewis[Q][16]"])
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows.values() for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has, and what they hand over passes",
          quests.check_items(), None)
    things = sorted({t for q in rows.values() for _f, t in q.things()})
    check("  ..each named in the launcher's table, none premium ((P) is out of the game)",
          ([t for t in things if not names.known(items.STRING_ID_OFFSET + t)],
           [t for t in things if items.premium(t)]), ([], []))
    check("  ..the guns are the (Q) family's, by the name the quest gives them",
          [names.text(items.STRING_ID_OFFSET + gun).split("$")[0] for _n, gun in
           (GUNS[224], GUNS[227], GUNS[230])],
          ["Маузер C96 (Q)", "Lewis (Q)", "Маузер C96 (Q)"])

    def unarmed(x):
        """Why a weapon paid would not be the weapon its name says, or None:
        no numbers of its own (items.designed_info's default -- for any gun
        a tier-1 pistol on 9 mm, clip 8, no skill), no skill asked, a gun of
        another class than its name's word."""
        si = items.params_of(x)
        if not has_record(x):
            return "no record"
        if si.get("need_skills") is None:
            return "no skill asked"
        word = names.text(items.STRING_ID_OFFSET + x).split("$")[-1]
        if items.root_of(x) == items.FIRE_ARM and si.get("weapon_type") != CLASS_WORD.get(word):
            return "class %r, the name says %r" % (si.get("weapon_type"), word)
        return None
    arms = sorted((t, x) for t in ALL if live(t) for f, x in real[t].things()
                  if f in ("rew_obj", "rew_also", "rew_random")
                  and items.root_of(x) in (items.FIRE_ARM, items.COLD_ARM))
    check("every weapon a live row pays is the weapon its name says: numbers of its own, a"
          " skill asked, the class of its name's word", [(t, x, unarmed(x)) for t, x in arms
                                                       if unarmed(x)], [])
    check("  ..among them the Маузер C96 (Q) and the old woman's syringe",
          {(224, GUNS[224][1]), (215, SYRINGE)} <= set(arms), True)
    check("  ..and a gun row is off exactly when its gun is not so",
          sorted(t for t, (_n, gun) in GUNS.items() if unarmed(gun)),
          sorted(t for t in GUNS if t in OFF))
    wanted = {x for u in ALL for x, _n in real[u].wants()}
    handed = sorted({(t, x) for t in ALL for x in real[t].rew_obj + [o for o, _n in
                                                                    real[t].rew_also]
                     if x in wanted})
    check("every thing one row pays and another asks for stays on the body at a death"
          " (combat.drops_on_death), or the row that pays it is walked again: a thing lost --"
          " fallen, sold, traded -- never strands the row that asks for it",
          [(t, x) for t, x in handed if combat.drops_on_death(x) and not real[t].repeatable],
          [])
    check("  ..the journal's parts are loot like any other (they fall, a stall buys them), so"
          " their assemblies are walked again",
          [(t, x, combat.drops_on_death(x), items.params_of(x).get("quest"), real[t].repeatable)
           for t, x in handed if t in PARTS],
          [(t, ch, True, 0, 1) for t, (_p, ch) in sorted(PARTS.items())])

    # The places, as the rooms stand them.
    stand = {}
    for lid in places:
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            stand.setdefault(n.type_id, set()).add((lid, n.root))
    check("each giver and taker stands where the quests send the player, not a mob",
          {npc: sorted(lid for lid, root in stand.get(npc, ()) if root != world.MOB)
           for npc in WHERE}, {npc: [lid] for npc, lid in WHERE.items()
                               if npc != VIVEK} | {VIVEK: [70, 688]})
    check("  ..and on the map, but the other side of the graveyard (688)",
          sorted(set(WHERE.values()) - on_map), [])
    by_mark = {pack(*world.cell_of(lid)): lid for lid in on_map}
    check("each hand-in's mark is its taker's place",
          {t: by_mark.get(q.finish_loc) for t, q in rows.items() if q.take},
          {t: WHERE[GIVE_TAKE[t][1]] for t in rows if rows[t].take})
    check("each kill stands, a mob, where its quest's mark is",
          {t: [m for m in ms if (lid, world.MOB) in stand.get(m, ())]
           for t, (ms, _n, lid) in KILLS.items()},
          {t: ms for t, (ms, _n, _l) in KILLS.items()})
    check("  ..and every live one where a player gets: on the map, or through a door, a side"
          " or a quest way from it (the son's raid is off while the mine's tiers are not)",
          sorted(t for t, (_m, _n, lid) in KILLS.items() if live(t) and lid not in reach), [])
    check("  ..what stands where no way leads yet: the ghosts of 688 and, in this copy, the"
          " miners of the mine's tiers -- both rows not live",
          sorted((t, live(t)) for t, (_m, _n, lid) in KILLS.items() if lid not in reach),
          sorted((t, False) for t in (217, RAID) if KILLS[t][2] not in reach))
    drops = {t: [(o, n, ms, c) for (o, n, ms), c in
                 zip(q.objs, [s.get("drop") for s in REAL_ROWS[t]["objs"]])]
             for t, q in rows.items() if q.kind == quests.BRING_L_OBJ}
    carried = {t: [o for o, _n, ms, c in slots
                   if c and not [m for m in ms if o in dict(mobs.quest_table(m))
                                 and any(l in reach for l, r in stand.get(m, ())
                                         if r == world.MOB)]]
               for t, slots in drops.items()}
    check("every thing a slot drops is carried by a creature standing where a player gets --"
          " on the map, or through a door, a side or a quest way from it (the ring of 208:"
          " the miners of the mine's tiers) -- for the quest that wants it (quests.quest_drops)",
          {t: v for t, v in carried.items() if v}, {})
    check("  ..each thing to bring either drops so, or is paid by the row before, or is found"
          " as loot (the rope, 6942)",
          sorted((t, o) for t, slots in drops.items() for o, _n, _ms, c in slots if not c),
          [(182, 5382), (219, 6942), (232, 416), (232, 417), (232, 418), (232, 419)])
    check("  ..Умар's parcel is Бари's courier's pay, the parts the pages' quests' pay",
          (rows[181].rew_obj, [rows[t].rew_obj for t in sorted(PARTS)]),
          ([5382], [[416], [417], [418], [419]]))
    check("  ..the rope is loot of the level-7 men on the map (Магриб, ДСР)",
          sorted(m for m in (305, 306, 307, 308, 62, 90, 51, 717)
                 if 6942 in [r[0] for r in mobs.loot_table(m)]),
          [51, 62, 90, 305, 306, 307, 308, 717])

    # «Веселый праздник», the journal, the fee, the shawarma.
    check("«Веселый праздник»: tokens for the guns, the counts the names' tasks say",
          {t: (rows[t].wants(), rows[t].rew_obj) for t in GUNS},
          {t: ([(TOKEN, n)], [gun]) for t, (n, gun) in GUNS.items()})
    check("  ..every Магриб patrol soldier of the camp carries a token for them, certain",
          {m: dict(mobs.quest_table(m)).get(TOKEN) for m in MG_PATROL}, {m: 1.0 for m in MG_PATROL})
    check("the journal: four pages into each part, the four parts into «Верблюжьи холмы»",
          ({t: (rows[t].wants(), rows[t].rew_obj) for t in PARTS}, rows[232].wants()),
          ({t: ([(p, 1) for p in range(page, page + 4)], [ch]) for t, (page, ch) in PARTS.items()},
           [(416, 1), (417, 1), (418, 1), (419, 1)]))
    check("  ..the sect's men carry all sixteen pages for them",
          sorted({t for m in LUSHER for t, _c in mobs.quest_table(m) if 420 <= t <= 435}),
          list(range(420, 436)))
    check("«Блудный сын» asks the original's thousand afro of the purse, paying nothing",
          (rows[FEE_Q].has_fee, rows[FEE_Q].cost_afro, rows[FEE_Q].rew_afro), (True, 1000, 0))
    check("«Просьба о помощи» lends the shawarma, sold by no stall: it cannot get away",
          (rows[220].start_obj, rows[220].obj, sorted(rows[220].lent), quests.lent(SHAWARMA),
           items.params_of(SHAWARMA).get("quest"), items.params_of(SHAWARMA).get("exchang")),
          ([(SHAWARMA, 1)], SHAWARMA, [SHAWARMA], True, 1, 0))
    check("Горбик: the brick handed over and carried to him, his head handed over and carried back",
          [(rows[t].start_obj, rows[t].obj) for t in (198, 199)],
          [([(1558, 1)], 1558), ([(1562, 1)], 1562)])

    # «Быть или не быть».
    check("«Быть или не быть»: one drop or two, rows that shut each other, one vial each",
          [(real[t].excludes, real[t].branch, real[t].obj, real[t].rew_obj)
           for t in (BRANCH_A, BRANCH_B)],
          [([BRANCH_B], [BRANCH_A], VIAL, [ONE_DROP]), ([BRANCH_A], [BRANCH_B], VIAL, [TWO_DROPS])])
    check("  ..the one-drop branch goes on to «Посланник смерти», the two-drop one to «Смерти"
          " вопреки»", (rows[214].need_all, rows[214].obj, rows[216].need_all, rows[216].obj),
          ([BRANCH_A], ONE_DROP, [BRANCH_B], TWO_DROPS))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- in process: the chief's head, only for a quest that wants it ----------------------
class _Store(object):
    """What a corpse's bag is made through, and the log its killer keeps."""

    def __init__(self, open_types):
        self.open = list(open_types)
        self.made = []

    def quests(self, char_id):
        return [dict(type=t, q_id=i + 1, progress_json="{}") for i, t in enumerate(self.open)]

    def create_item(self, owner, type_id, root, **fields):
        self.made.append(type_id)
        return dict(uniq=len(self.made), type_id=type_id)

    def delete_item(self, uniq):
        pass

    def forget_trophy(self, uniq):
        pass

    def lay_down(self, things, place, cell):
        pass

    def sweep_ground(self, uniqs, loot_owner):
        pass


class _Killer(object):
    is_player = True
    eid = rooms.player_id(7)

    def __init__(self, have):
        self.sess = SimpleNamespace(char_id=1, inv=SimpleNamespace(bag_pieces=lambda: dict(have)))

    def count_kill(self, type_id):
        pass

    def release_stats(self):
        """The kill pushes the killer's held rp_info (Fighter.hold_stats);
        nothing is held here."""


async def _the_chief(open_types, have):
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.2
    room = rooms.Room(world.location(120), rooms.IdAllocator(), MT)
    store = _Store(open_types)
    rc = room.combat = combat.RoomCombat(room, store)
    chief = next(m for m in rc.mobs.values() if m.type_id == CHIEF)
    chief.hp = 0
    rc.kill(chief, _Killer(have))
    await asyncio.sleep(0.15)
    return store.made.count(HEAD)


try:
    check("the bandit chief's head falls from his body for a «Фрэнк (часть 2)» that wants it;"
          " not for one whose bag already holds it; not without the quest",
          [asyncio.run(_the_chief([FRANK2], {})), asyncio.run(_the_chief([FRANK2], {HEAD: 1})),
           asyncio.run(_the_chief([], {})), asyncio.run(_the_chief([192], {}))], [1, 0, 0, 0])
except Exception:
    import traceback
    fails.append("the chief's kill broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_city.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("voter", "secret")
_store.close()
CRED = accounts.credential("voter", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5968", LAVA_GY="1727", LAVA_SEED="5",
           LAVA_POLICY_PORT="0", LAVA_QUESTS=_ON)
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


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
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(2)


HERE_NOW = {}


def goto(c, loc_id):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    HERE_NOW.clear()
    HERE_NOW.update(inhabitants(arrive(c)))
    return HERE_NOW


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.3)


def money(c, afro):
    c.send("userMsg;entry=@/money %d 0@;group=0;" % afro)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.3)


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


TAKEN = {}


def take(c, qtype):
    """q_st of a type from its giver here: (ack, the journal's complete flag)."""
    npc_type = GIVE_TAKE[qtype][0]
    npc = HERE_NOW.get(npc_type, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    TAKEN[qtype] = ids[0] if ids else 0
    di = [p for n, p in got if n.startswith("q_di_")]
    return acks(got), (di[-1].get("complete") if di else None)


def hand_in(c, qtype, obj_idx=0):
    npc = HERE_NOW.get(GIVE_TAKE[qtype][1], [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, TAKEN.get(qtype, 0)))
    return c.frames(0.9)


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = 'Voter'").fetchone()
    st.close()
    return row["id"]


def purse():
    st = store()
    got = tuple(st.money(char_id()))
    st.close()
    return got[0]


def owned():
    st = store()
    out = {}
    for r in st.items_of(char_id()):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def done():
    st = store()
    got = sorted(r["type"] for r in st.db.execute(
        "SELECT type FROM char_quests_done WHERE char_id = ?", (char_id(),)).fetchall())
    st.close()
    return got


def credit_kills(qtype):
    """The kills of a quest, as a fight's Fighter.count_kill makes them:
    quests.kill_progress on the server's own database."""
    st = store()
    q = quests.get(qtype)
    for mob, n in zip(q.mobs_kill, q.num_kill):
        for _ in range(n):
            quests.kill_progress(st, char_id(), mob)
    st.close()


def relogin():
    c_ = Client(connect())
    c_.send("hello;minor=2;major=0;")
    c_.send("login;hash=@%s@;" % CRED)
    c_.frames()
    c_.send("selPers;num=0;")
    c_.until(lambda f: f[0] == "lcall")
    HERE_NOW.clear()
    HERE_NOW.update(inhabitants(arrive(c_)))
    return c_


def step(c, qtype, give_things=(), kills=False):
    """Hand in a quest carried here and return the ack; things put in the bag
    first, kills credited first."""
    for t, n in give_things:
        give(c, t, n)
    if kills:
        credit_kills(qtype)
    return acks(hand_in(c, qtype))


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Voter@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    CID = char_id()
    check("a newcomer of the first level: Нильсон's election is not offered yet (third level)",
          status(c, 183), 0)
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)
    st = store()
    st.save_stats(CID, [("skill", progression.SHOOTING, 8, 0, progression.skill_xp_max(8))])
    st.save_character_state(CID, level=8)
    st.close()
    c = relogin()
    check("back at the eighth level of Стрельба: the election, the old woman's ring, Натти's"
          " message and the rest of the chains' heads are offered, their steps not",
          [status(c, t) for t in (183, 184, 208, 209, 222, 223, 180, 181, 219, 220, 221, 231, 237)],
          [1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1])

    # --- «Выборы», end to end ----------------------------------------------------------
    afro0 = purse()
    walk = []                                   # (type, take ack, hand-in ack)

    def go(loc):
        if loc != go.at:
            goto(c, loc)
        go.at = loc
    go.at = None

    def taken(t):
        a, _complete = take(c, t)
        return a

    go(35)
    walk.append((183, taken(183), step(c, 183)))
    check("«Выборы» handed in: «Мауризио» offered now", status(c, 184), 1)
    a184 = taken(184)
    go(60)
    walk.append((184, a184, step(c, 184)))
    a185 = taken(185)
    for t, n in ((1316, 3), (1317, 1), (1318, 1), (1320, 1), (1319, 1)):
        give(c, t, n)
    go(119)
    walk.append((185, a185, step(c, 185, kills=True)))
    for t in (186, 187, 188):
        walk.append((t, taken(t), step(c, t)))
    a189 = taken(189)
    go(60)
    walk.append((189, a189, step(c, 189)))
    walk.append((190, taken(190), step(c, 190, [(1321, 3)])))
    a191 = taken(191)
    go(35)
    walk.append((191, a191, step(c, 191)))
    a192 = taken(192)
    go(104)
    walk.append((192, a192, step(c, 192)))
    walk.append((193, taken(193), step(c, 193, [(HEAD, 1)])))
    walk.append((194, taken(194), step(c, 194, [(1559, 1), (1560, 1), (1561, 1)])))
    a195 = taken(195)
    go(102)
    walk.append((195, a195, step(c, 195)))
    walk.append((196, taken(196), step(c, 196, kills=True)))
    walk.append((197, taken(197), step(c, 197, [(2195, 3)])))
    a198, complete198 = take(c, 198)
    check("Шихаб hands the brick over at the take: found at once", (a198, complete198,
                                                                  owned().get(1558)), ([0], 1, 1))
    go(138)
    walk.append((198, a198, step(c, 198)))
    a199, complete199 = take(c, 199)
    check("  ..fed to Горбик, whose remains hand his head over", (owned().get(1558), a199,
                                                              complete199, owned().get(1562)),
          (None, [0], 1, 1))
    go(102)
    walk.append((199, a199, step(c, 199)))
    walk.append((200, taken(200), step(c, 200, kills=True)))
    a201 = taken(201)
    go(104)
    walk.append((201, a201, step(c, 201)))
    a202 = taken(202)
    go(35)
    walk.append((202, a202, step(c, 202)))
    a203 = taken(203)
    credit_kills(203)
    go(140)
    walk.append((203, a203, step(c, 203)))
    a204 = taken(204)
    go(60)
    walk.append((204, a204, step(c, 204)))
    a205 = taken(205)
    give(c, 2196)
    give(c, 2197)
    go(140)
    walk.append((205, a205, step(c, 205)))
    walk.append((206, taken(206), step(c, 206)))
    a207 = taken(207)
    go(35)
    walk.append((207, a207, step(c, 207)))
    check("«Выборы» walked: every step taken and handed in, the ack 0 each time",
          [(t, a, h) for t, a, h in walk if (a, h) != ([0], [0])], [])
    check("  ..all twenty-five written into the history", [t for t in ELECTION if t in done()],
          ELECTION)
    check("  ..paid what the rows say", purse() - afro0,
          sum(quests.get(t).rew_afro for t in ELECTION))
    have = owned()
    check("  ..the moonshine in the bag, and nothing the chain asked for left in it",
          (have.get(3190), [t for t in (1316, 1317, 1318, 1319, 1320, 1321, HEAD, 1558, 1559,
                                         1560, 1561, 1562, 2195, 2196, 2197) if have.get(t)]),
          (1, []))
    check("  ..nothing of it offered again", [status(c, t) for t in (183, 192, 203, 207)],
          [0, 0, 0, 0])

    # --- «Индийское кино»: the fee, the branches ----------------------------------------
    go(37)
    a208 = taken(208)
    afro1 = purse()
    check("the ring for the old woman: 5000 afro", (a208, step(c, 208, [(3939, 1)]),
                                                    purse() - afro1), ([0], [0], 5000))
    money(c, -10 ** 7)
    money(c, 500)
    a209, complete209 = take(c, FEE_Q)
    check("«Блудный сын» taken with 500 afro: the journal says not complete (the fee)",
          (a209, complete209), ([0], 0))
    go(36)
    got = hand_in(c, FEE_Q)
    check("  ..handed to Каспар short of it: refused (21), the purse untouched",
          (acks(got), purse(), FEE_Q in done()), ([21], 500, False))
    money(c, 1000)
    check("  ..with 1500: handed in, the thousand taken", (step(c, FEE_Q), purse()), ([0], 500))
    a210 = taken(210)
    go(70)
    walk2 = [(210, a210, step(c, 210))]
    a211 = taken(211)
    go(37)
    walk2.append((211, a211, step(c, 211)))
    check("  ..to Вивек and back: the vial in the bag", ([(t, a, h) for t, a, h in walk2
                                                         if (a, h) != ([0], [0])],
                                                        owned().get(VIAL)), ([], 1))
    check("«Быть или не быть»: both drops offered by the old woman",
          [status(c, t) for t in (BRANCH_A, BRANCH_B)], [1, 1])
    a212 = taken(BRANCH_A)
    check("  ..one drop taken: the two drops are no longer offered",
          (a212, status(c, BRANCH_B)), ([0], 0))
    got = hand_in(c, BRANCH_A)
    check("  ..at the table: the vial for the one drop", (acks(got), owned().get(VIAL),
                                                         owned().get(ONE_DROP)), ([0], None, 1))
    go(70)
    check("  ..and at Вивек «Посланник смерти» is offered, «Смерти вопреки» is not",
          [status(c, t) for t in (214, 216)], [1, 0])

    # --- Натти and Джо -------------------------------------------------------------------
    go(37)
    a222 = taken(222)
    a231 = taken(231)
    check("Натти: the message for Джо taken, «Великая проблема» heard",
          (a222, a231, step(c, 231)), ([0], [0], [0]))
    a232 = taken(232)
    a233 = taken(233)
    for p in range(420, 424):
        give(c, p)
    got = hand_in(c, 233)
    have = owned()
    check("  ..«\"Верблюжьи холмы\"» taken; four pages into the journal's first part",
          (a232, a233, acks(got), [p for p in range(420, 424) if have.get(p)], have.get(416)),
          ([0], [0], [0], [], 1))
    check("  ..the assembly offered again, and the second one after it",
          [status(c, 233), status(c, 234)], [1, 1])
    # The part lost, as a death (combat.death_losses) or a stall leaves it:
    # out of the character's things.
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)
    st = store()
    for r in st.items_of(CID):
        if r["type_id"] == 416:
            st.delete_item(r["uniq"])
    st.close()
    c = relogin()
    go.at = None
    go(37)
    a233 = taken(233)
    st = store()
    pages = sorted(t for t in quests.wanted_things(st, CID, {}) if 420 <= t <= 435)
    st.close()
    check("  ..the part lost: the first assembly taken again, its pages wanted again (so the"
          " sect's men drop them again)", (owned().get(416), a233, pages),
          (None, [0], [420, 421, 422, 423]))
    for p in range(420, 424):
        give(c, p)
    got = hand_in(c, 233)
    for part in (417, 418, 419):
        give(c, part)
    afro2 = purse()
    got232 = hand_in(c, 232)
    have = owned()
    check("  ..put together again, and «\"Верблюжьи холмы\"» handed in all the same: the four"
          " parts taken, 1000 afro", (acks(got), acks(got232), [x for x in range(416, 420)
                                                               if have.get(x)],
                                     purse() - afro2, 232 in done()),
          ([0], [0], [], 1000, True))
    c.send("userMsg;entry=@/goto 62@;group=0;")
    c.until(lambda f: f[0] == "lcall")
    arrival = arrive(c)
    HERE_NOW.clear()
    HERE_NOW.update(inhabitants(arrival))
    go.at = 62
    offers = [p.get("give_quests") or [] for n, p in arrival
              if n.startswith("userInfo") and p.get("name") == JOE]
    check("Джо at the oasis offers the guns with numbers of their own, the Маузер C96[Q][2];"
          " the six rows switched off are not in his list",
          [t for t in (offers[0] if offers else []) if t in GUNS],
          sorted(t for t in GUNS if t not in OFF))
    check("  ..he takes the message; the festival follows",
          (step(c, 222), taken(223), step(c, 223)), ([0], [0], [0]))
    a224 = taken(224)
    got = hand_in(c, 224)
    check("  ..the Маузер C96 (Q) asked of him with no token: refused, not ready",
          (a224, acks(got)), ([0], [3]))
    give(c, TOKEN, 30)
    got = hand_in(c, 224)
    have = owned()
    check("  ..with thirty tokens: they are taken, the Маузер C96 (Q) given",
          (acks(got), have.get(TOKEN), have.get(GUNS[224][1])), ([0], None, 1))
    c.send("logout;")
    c.frames(0.3)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    out = open(LOG, encoding="utf-8", errors="replace").read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa city OK")
