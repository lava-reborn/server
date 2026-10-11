"""Вади-Хальфа, stage 2: the fixups and the guards of its economy (2026-09-28).

What the plan's corrections а, б, г and д and the stage-1 skeptic asked of
the town before c_ga pays 4000 afro an ounce, each held here:

  1. the clothing market's traders (468, off the map since the owner's cut
     of Вади-Хальфа, 2026-10-09; 5160, 5161 and 5181 stand in the markets of
     Абри, Донгола and Абу-Хамед too): each sells the owner's ladder of sets
     (data/sets.json), A then G, no (P), no quest (Q) set -- the two left at
     468 the levels in their own names, 5160 and 5161 their city's band
     where they stand (the owner's «по уровню городов», 2026-10-10,
     shop_bands.py); «Шахтерская одежда» (5181) the town's miner's clothes, A
     then G, on the numbers of Колонист[2]; Странник[4] and the gold sets of
     4/6/8 are sold in Halfa, by Ваккас and Хамис, not in the valley alone;
  2. Ольсен (431) sells nothing, the lottery man (662) the town's own
     ticket alone, at its own article's price;
  3. the gold taps: the black market's placeholder quests are gone, and
     every row of the table that pays gold is a service, once a day, or an
     ingot changed for its ounces;
  4. the journal of money: every change of a purse is a row -- source,
     character, level -- whose sum is the purse, and the report sums them;
  5. the engine's loose ends: c_ga answers any figure with one ack, and a
     frame nobody can read is answered as its command and value ask; a way
     that moves nobody gives its fee back, unless it paid a reward too; a
     kill quest pays its fee at the take, so its hand-in is never refused
     for money, and a drop gives back what was paid; lent rounds are lent
     once a day, unless they all came back unused, dropped or taken back
     on leaving the place they are kept in (stay_in); the gold belts are named
     as gold;
  6. an object (a box, a Tir target, a stone) pays no experience;
  7. a thing standing in the new places registers nobody's home;
  8. the journal holds 25 ordinary quests.

In process, on the data and on sessions of an in-process server (server.
Session over a writer that keeps the frames), the way test_relogin drives
it: no socket, so every frame is where the handler put it.

    LAVA_RES=.../lava/res python3 server/test_halfa_fixups.py
"""
import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(tempfile.mkdtemp(), "fixups.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
os.environ["LAVA_START"] = "183"
for _knob in ("LAVA_PASSAGES", "LAVA_START_AFRO"):
    os.environ.pop(_knob, None)

# The suite's own rows, on the real table (quests.quests_path): a kill quest
# with a fee, and one that lends a gun and its rounds, both at Техногик.
KILL_FEE_Q, LENT_Q, LENT_STAY_Q = 90040, 90042, 90044
KILL_FEE, KILL_PAY = 300, 50
TRAINING_GUN, TRAINING_ROUNDS = 3728, 3727
FIXTURES = [
    dict(type=KILL_FEE_Q, kind="kill_mobs", name="Собаки за плату", start="Плати и иди.",
         finish="Держи.", give=[652], take=[652], mobs_kill=[82], num_kill=[3],
         cost_afro=KILL_FEE, rew_afro=KILL_PAY, repeatable=1),
    dict(type=LENT_Q, kind="del_obj", name="Тир на день", start="Вот пистолет и патроны.",
         finish="Верни всё.", give=[652], take=[652], obj=0, repeatable=1, lent=True,
         start_obj=[dict(obj=TRAINING_GUN, num=1), dict(obj=TRAINING_ROUNDS, num=10)]),
    # The same loan kept in its place, the black market (stay_in), as the
    # Tir's lessons keep theirs in their ranges.
    dict(type=LENT_STAY_Q, kind="del_obj", name="Тир на месте", start="Стреляй здесь.",
         finish="Верни всё.", give=[652], take=[652], obj=0, repeatable=1, lent=True,
         stay_in=[102],
         start_obj=[dict(obj=TRAINING_GUN, num=1), dict(obj=TRAINING_ROUNDS, num=10)]),
]
with open(os.path.join(ROOT, "data", "quests.json"), encoding="utf-8") as _fh:
    REAL = json.load(_fh)
_table = dict(REAL, quests=REAL["quests"] + FIXTURES)
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as _fh:
    json.dump(_table, _fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import storage  # noqa: E402
import world  # noqa: E402
import money_report  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


SLOTS = ("helm", "shirt", "armor", "pants", "boots")
with open(os.path.join(ROOT, "data", "sets.json"), encoding="utf-8") as _fh:
    SETS = json.load(_fh)["sets"]


def set_of(level, variant):
    """The five pieces of the ladder's set of that level and variant, or []."""
    for s in SETS.values():
        if s["level"] == level and s["variant"] == variant:
            return [s["members"][k]["type"] for k in SLOTS]
    return []


def ladder(lo, hi):
    """What a trader of levels lo..hi sells: every set of the ladder in the
    band, by level, A then G, helm to boots. A quest (Q) set is on the
    ladder as data only (sets.json _meta.decided), so it is on no stall."""
    out = []
    for level in sorted({s["level"] for s in SETS.values()}):
        if lo <= level <= hi:
            out += set_of(level, "A") + set_of(level, "G")
    return out


# --- 1. the clothing market ------------------------------------------------------------
# Each trader's own name gives his band: texts.xml 10407-10410 (halfa-names).
MARKET = {5158: (0, 6), 5159: (7, 10), 5160: (10, 14), 5161: (15, 16)}
check("the four set traders are named with their bands",
      {t: "%d-%d" % band in names.ALL.get(t, "") for t, band in MARKET.items()},
      {t: True for t in MARKET})
# The two left only at 468 sell the band of their name; 5160 and 5161, who
# stand in the markets of Абри (378), Донгола (469) and Абу-Хамед (467), their
# city's band there, and nothing of their own (data/npcs.json).
check("each sells the ladder's sets of his band, A then G, helm to boots",
      {t: items.stock_for(t) for t in (5158, 5159)}, {t: ladder(*MARKET[t]) for t in (5158, 5159)})
CITY_MARKETS = {(5160, 378): (8, 12), (5161, 378): (8, 12), (5161, 469): (12, 16),
                (5161, 467): (16, 20)}
check("  ..5160 and 5161 their city's band at its market, nothing of their own",
      ({k: items.stock_for(*k) for k in CITY_MARKETS}, items.stock_for(5160), items.stock_for(5161)),
      ({k: ladder(*band) for k, band in CITY_MARKETS.items()}, [], []))
check("  ..which is Беженец to Магриб, Налетчик and Пустынник; Абри's Налетчик and Пустынник,"
      " Донгола's Спецназ to Красное Эхо, Абу-Хамед's Красное Эхо to Апокалипсис",
      {k: sorted({s["name"].split("[")[0] for s in SETS.values()
                  if s["members"]["helm"]["type"] in items.stock_for(*k)})
       for k in [(5158, None), (5159, None)] + list(CITY_MARKETS)},
      {(5158, None): ["Беженец", "Колонист", "Магриб", "Странник"],
       (5159, None): ["Налетчик", "Пустынник"],
       (5160, 378): ["Налетчик", "Пустынник"], (5161, 378): ["Налетчик", "Пустынник"],
       (5161, 469): ["Красное Эхо", "Легионер", "Спецназ", "Штурм-М"],
       (5161, 467): ["Апокалипсис", "Дредноут", "Красное Эхо", "Паладин"]})
SOLD = sorted({t for tr, place in [(5158, None), (5159, None), (1204, 102), (1205, 102),
                                   (5181, 378)] + list(CITY_MARKETS)
               for t in items.stock_for(tr, place)})
check("nothing premium, no quest piece, every piece a thing the client can show",
      ([t for t in SOLD if items.premium(t)],
       [t for t in SOLD if (items.params_of(t) or {}).get("quest")
        or items.params_of(t) is None or not names.known(items.STRING_ID_OFFSET + t)]),
      ([], []))
with open(os.path.join(ROOT, "data", "orig_items.json"), encoding="utf-8") as _fh:
    ORIG_ITEMS = json.load(_fh)["items"]
# Вади-Хальфа's miner's pieces, found in the catalogue by their names
# (objects.xml helm_minecraft_U_LVL_WH_A_mod00 ..), A and G; the (P) apart.
WH_MINER = re.compile(r"^(helm|shirt|armor|pants|boots)_minecraft_U_LVL_WH_([AGP])_mod00$")
MINER = {}
for _t, (_root, _name) in items.catalogue().items():
    _m = WH_MINER.match(_name)
    if _m:
        MINER.setdefault(_m.group(2), {})[_m.group(1)] = _t
MINER_A = [MINER["A"][k] for k in SLOTS]
MINER_G = [MINER["G"][k] for k in SLOTS]
check("the miner's clothes have types: objects.xml 34480-34484 (A), 34485-34489 (P),"
      " 34490-34494 (G)", (MINER_A, [MINER["P"][k] for k in SLOTS], MINER_G),
      (list(range(34480, 34485)), list(range(34485, 34490)), list(range(34490, 34495))))
check("  ..«Шахтерская одежда» (5181) sells them, A then G, helm to boots; no (P)",
      (names.ALL.get(5181), items.stock_for(5181)),
      ("Торговец<br>Шахтерская одежда", MINER_A + MINER_G))
check("  ..each named by the original (texts.xml 22856-22875), the gold copy in the words"
      " of its A twin",
      [(names.text(items.STRING_ID_OFFSET + t), ORIG_ITEMS.get(str(t), {}).get("name_id"),
        ORIG_ITEMS.get(str(t), {}).get("desc_id"), names.known(items.DESC_ID_OFFSET + t),
        items.params_of(t)["desc"] == items.DESC_ID_OFFSET + t) for t in MINER_A + MINER_G],
      [(n + v, nid, did, True, True) for v, first in (("", 22856), (" (G)", 22871))
       for n, nid, did in zip(["Каска шахтёра (WH)", "Подстёжка шахтёра (WH)",
                               "Жилет-помощник шахтёра (WH)", "Штаны шахтёра (WH)",
                               "Бутсы (WH)"],
                              [first + k * (2 if first == 22856 else 1) for k in range(5)],
                              [22857 + 2 * k for k in range(5)])])
LIKE = ("armor_class", "max_break_abs", "weight", "cost", "g_cost", "premium", "exchang",
        "bonus_hp", "bonus_st", "bonus_od", "bonus_cp", "bonus_ce", "need_attribs_m",
        "need_attribs", "need_skills_m", "need_skills", "slot_type")
check("  ..on the numbers of Колонист[2]'s piece of the same slot (DESIGNED, items.MINER_WEAR)",
      [{k: items.params_of(t).get(k) for k in LIKE} for t in MINER_A + MINER_G],
      [{k: items.params_of(t).get(k) for k in LIKE} for t in set_of(2, "A") + set_of(2, "G")])
check("  ..A for afro alone, G for gold alone and not exchanged, in no set",
      [(p["cost"] > 0, p["g_cost"] > 0, p["exchang"], p["set_type"])
       for p in map(items.params_of, MINER_A + MINER_G)],
      [(True, False, 1, 0)] * 5 + [(False, True, 0, 0)] * 5)
WANDERER = set_of(4, "A") + set_of(4, "G")
GOLD_468 = set_of(4, "G") + set_of(6, "G") + set_of(8, "G")
check("Странник[4] in both variants and the gold sets of 4, 6 and 8 at Ваккас and Хамис"
      " (correction д)",
      [t for t in WANDERER + GOLD_468
       if t not in items.stock_for(1204, 102) + items.stock_for(1205, 102)], [])
check("  ..both the town's band, 4-8, both versions (shop_bands.py, 2026-10-10); Ваккас then"
      " his belts",
      (items.stock_for(1204, 102), items.stock_for(1205, 102)),
      (ladder(4, 8) + [3582, 3581, 3579, 3578], ladder(4, 8)))

# --- 2. Ольсен and the lottery man ---------------------------------------------------------
check("Ольсен, «Амулеты и сувениры», sells nothing (no amulet or souvenir has a type"
      " on his list; not the Donghola medicine)",
      (names.ALL.get(431), items.stock_for(431)), ("Ольсен<br>Амулеты и сувениры", []))
check("the lottery man sells the town's ticket alone, the gold one's man the gold one",
      (items.stock_for(662), items.stock_for(711)), ([1307], [1333]))
TICKET = items.params_of(1307)
check("  ..LoteryKey by its own name and article: «Лотерейный билет», 500 afro,"
      " no «Билет в Донголу» anywhere near",
      (names.text(items.STRING_ID_OFFSET + 1307), TICKET["cost"], TICKET["g_cost"],
       1124 in items.stock_for(662) + items.stock_for(711)),
      ("Лотерейный билет", 500, 0, False))

# --- 3. the gold taps ---------------------------------------------------------------------
TABLE = quests.load(quests.PATH)
check("the black market's placeholders 1-3, 5, 6 are out of the table; 4 stays",
      ([t for t in (1, 2, 3, 5, 6) if t in TABLE], 4 in TABLE), ([], True))
check("«Золотоискатель» (9) pays its ounce once a day",
      (TABLE[9].rew_gold, TABLE[9].repeatable, TABLE[9].per_day), (100, 1, 1))
check("«Обмен слитка» (10) stays: two ounces for the boss's two ingots of one",
      (TABLE[10].rew_gold, TABLE[10].wants()), (200, [(7620, 2)]))
GOLD_ROWS = {t: q for t, q in TABLE.items() if q.rew_gold > 0}
INGOTS = set(items.GOLD_INGOTS)
check("every row that pays gold asks for something or for kills (Фрэнк's raid, 221)"
      " -- none for a word passed on",
      [t for t, q in GOLD_ROWS.items() if not (q.wants() or q.mobs_kill)], [])
check("and is a service (cashing), a once-a-day task, or an ingot changed for its ounces",
      [t for t, q in GOLD_ROWS.items()
       if not (q.service or q.per_day or {o for o, _n in q.wants()} & INGOTS)], [])
print("      the gold of the quest table: %s" % ", ".join(
    "%d «%s» %.2f G%s" % (t, q.name, q.rew_gold / 100.0,
                          " (service)" if q.service else
                          " (once a day)" if q.per_day else " (for an ingot)")
    for t, q in sorted(GOLD_ROWS.items())))

# --- 5e. the gold belts --------------------------------------------------------------------
BELTS = {3600: "Подсумки снайпера (G)", 3601: "Подсумки спецназовца (G)",
         3603: "Подсумки охотника (G)", 3604: "Подсумки пистолетные (G)"}
check("the gold belt copies carry the (G) rows 47828/47833/47848/47853",
      {t: ORIG_ITEMS[str(t)]["name_id"] for t in BELTS},
      {3600: 47828, 3601: 47833, 3603: 47848, 3604: 47853})
check("  ..and are named so", {t: names.text(items.STRING_ID_OFFSET + t) for t in BELTS}, BELTS)
check("  ..their plain twins keep theirs",
      [names.text(items.STRING_ID_OFFSET + t) for t in (3578, 3579, 3581, 3582)],
      ["Подсумки снайпера", "Подсумки спецназовца", "Подсумки охотника",
       "Подсумки пистолетные"])

# --- 5d. what is lent and used up by its use ------------------------------------------------
check("a quest lending rounds lends what is used up; one lending a gun alone does not",
      (quests.lends_consumables(quests.get(LENT_Q)),
       quests.lends_consumables(quests.Quest(dict(
           type=90043, kind="del_obj", name="x", obj=0, lent=True,
           start_obj=[dict(obj=TRAINING_GUN, num=1)])))), (True, False))
check("a kill quest with a fee pays it at the take; a delivery with one at the hand-in",
      (quests.get(KILL_FEE_Q).fee_at_take, quests.Quest(dict(
          type=90044, kind="del_obj", name="x", obj=0, cost_afro=5)).fee_at_take), (True, False))

# --- 6. an object pays no experience -------------------------------------------------------


class _XpSession(object):
    def __init__(self, ch):
        self.char, self.pushed = ch, []

    def character(self):
        return self.char

    def push_stats(self, **groups):
        self.pushed.append(groups)

    def push_vitals(self):
        pass


def xp_for(mob_type):
    """Стрельба experience a newborn takes for a whole kill of one."""
    ch = progression.Character()
    shooter = combat.Fighter(_XpSession(ch))
    st = mobs.stats(mob_type)
    target = mobs.Mob(1, mob_type, 10)
    shooter.award_xp(progression.SHOOTING, 2, st.hp_max + st.sp_max, target)
    return ch.skill[progression.SHOOTING][1]


TIR_TARGET, STONE, DOG = 1397, 977, 82
check("a Tir target, a quarry stone and a camp box are objects",
      [mobs.stats(t).role for t in (TIR_TARGET, STONE, 409)], ["object"] * 3)
check("a whole kill of a Tir target or a stone teaches nothing; of a dog, something",
      (xp_for(TIR_TARGET), xp_for(STONE), xp_for(DOG) > 0), (0, 0, True))
combat.OBJECTS_PAY_XP = True
check("  ..the switch: paid, they pay at the role's xp_mult again", xp_for(TIR_TARGET) > 0, True)
combat.OBJECTS_PAY_XP = False

# --- 7. things register nobody's home -------------------------------------------------------
check("Rahat's dead wife (68, 47) and the skull of treasure island (2099, 139) register"
      " nobody's home", (world.offers_home(68), world.offers_home(2099)), (False, False))
check("  ..unlisted residents and cows no longer register homes either",
      [world.offers_home(t) for t in (74, 103, 423, 425, 1977, 666, 115)], [False] * 7)
# Not the premium masters' camp 124: off the map since the owner's cut of (P)
# (2026-09-30, data/retired.json), and nobody stands in it. Nor the clothing
# market 468 and the craftsmen's quarters 452, 456, 457: off the map since the
# owner's cut of Вади-Хальфа (2026-10-09), nobody can come in to register.
# Nor the FSC airfield 528, off it since the cut of the town's ФСЦ
# (2026-10-10), whose two upgraders register no home anywhere.
PLACES = ([41, 52, 37, 104, 35, 94, 36, 95, 102, 100, 70, 164, 60,
           176, 107, 59, 78]
          + [43, 48, 65, 119, 120, 140, 62, 61, 47, 64, 63, 117, 137, 138, 139, 141, 142,
             122, 108, 45, 46, 44, 116, 121]
          + list(range(80, 88)) + [109, 110, 111, 165, 198, 199, 598, 599, 623]
          + [732, 1048, 1233, 1260, 1276, 1280, 1282] + list(range(626, 631))
          + [200, 201, 202, 657, 658, 659, 1025, 1218, 1255, 1027, 1220, 1257, 1026, 1219, 1256]
          + [154, 158, 160, 613, 617, 1012, 1016, 1024, 1215, 1017, 1018, 1019])
MT = world.mob_types()
THING_ARTS = {MT[t][2] for t in (68, 75, 104, 625, 634, 816, 2099, 2279, 1135)}
homes = {}
for loc_id in PLACES:
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    for npc in room.npcs.values():
        t = npc.type_id
        if MT[t][0] in (world.COMMONER, world.HEALER) and not inventory.is_bank(t) \
                and world.offers_home(t, MT[t][0]):
            homes.setdefault(t, loc_id)
check("no Commoner of Halfa's places that registers a home is drawn as a thing is"
      " (a box, a corpse, a skull, a fountain or a grindstone)",
      sorted((t, MT[t][2], homes[t]) for t in homes if MT[t][2] in THING_ARTS), [])

# --- the retired quests leave the journals once ---------------------------------------------
_old = os.path.join(tempfile.mkdtemp(), "old.db")
st = accounts.Store(_old)
_acc, _ = st.register("veteran", "secret")
_cid, _ = st.create_character(_acc, "Veteran", 0, "1")
for t in (1, 4, 5):
    st.take_quest(_cid, t, {}, True)
st.db.execute("DELETE FROM migrations WHERE name = ?",
              ("retire-black-market-placeholders-2026-09-28",))
st.db.commit()
st.close()
st = accounts.Store(_old)
check("a journal from before: the placeholders 1 and 5 leave it once, 4 stays",
      sorted(r["type"] for r in st.quests(_cid)), [4])
# A database from before the ledger: its purses open it, once.
st.db.execute("UPDATE characters SET afro = 777, gold = 55 WHERE id = ?", (_cid,))
st.db.execute("DROP TABLE money_ledger")
st.db.execute("DELETE FROM migrations WHERE name = ?", ("money-ledger-opening-2026-09-28",))
st.db.commit()
st.close()
st = accounts.Store(_old)
check("a database from before the ledger: each purse its one opening row, so the rows"
      " add up to it", [(r["source"], r["afro"], r["gold"]) for r in st.ledger(_cid)],
      [("opening", 777, 55)])
st.close()
st = accounts.Store(_old)
check("  ..and only once", len(st.ledger(_cid)), 1)
_o = money_report.summarize(st.ledger(_cid))
check("  ..which the report keeps out of the taps and drains",
      (_o["opening"].rows, _o["total"].rows, "opening balances of 1 characters" in
       money_report.report(st.ledger(_cid))), (1, 0, True))
st.close()
# The table of the sources (accounts.LEDGER_SOURCES), the report's and the
# admin panel's key, one source to a line as the file writes a dict: the
# merge of stage 3 once left «"death":"a paid resurrection",» in it.
with open(os.path.join(HERE, "accounts.py"), encoding="utf-8") as _fh:
    _block = _fh.read().split("\nLEDGER_SOURCES = {\n", 1)[1].split("\n}\n", 1)[0]
check("the ledger's sources one to a line, «\"source\": \"what it is\",», every one of"
      " accounts.LEDGER_SOURCES",
      ([line for line in _block.splitlines() if not re.match(r'^    "[a-z_]+": "[^"]+",$', line)],
       re.findall(r'^    "([a-z_]+)"', _block, re.M) == list(accounts.LEDGER_SOURCES)),
      ([], True))


def adds_up(st, cid):
    """(the sums of a character's ledger rows, his purse)."""
    rows = st.ledger(cid)
    return (sum(r["afro"] for r in rows), sum(r["gold"] for r in rows)), tuple(st.money(cid))


# A character found without stats: migrate gives it a newborn's, the purse
# too, and books it (seed_stats).
st = accounts.Store(_old)
st.db.execute("DELETE FROM char_stats WHERE char_id = ?", (_cid,))
st.db.commit()
st.close()
st = accounts.Store(_old)
check("a character found without stats: re-seeded, its newborn's purse booked, so its rows"
      " still add up to it", (adds_up(st, _cid), st.ledger(_cid)[-1]["source"]),
      (((progression.START_AFRO, 0), (progression.START_AFRO, 0)), "start"))
# The same on a database from before the ledger: the re-seed books first,
# the opening then the rest (open_ledger).
st.db.execute("UPDATE characters SET afro = 5, gold = 7 WHERE id = ?", (_cid,))
st.db.execute("DELETE FROM char_stats WHERE char_id = ?", (_cid,))
st.db.execute("DROP TABLE money_ledger")
st.db.execute("DELETE FROM migrations WHERE name = ?", ("money-ledger-opening-2026-09-28",))
st.db.commit()
st.close()
st = accounts.Store(_old)
check("  ..and on a database from before the ledger: the re-seed, then the opening of the"
      " rest", ([(r["source"], r["afro"], r["gold"]) for r in st.ledger(_cid)],
                adds_up(st, _cid)[0] == adds_up(st, _cid)[1]),
      ([("start", progression.START_AFRO - 5, -7), ("opening", 5, 7)], True))
# Deleted as tools/admin_account.py deletes one, then a new character: on
# SQLite the new one takes the old id (INTEGER PRIMARY KEY, no AUTOINCREMENT).
st.note_lent(_cid, LENT_Q)
for _table in ("char_quests", "char_quests_done", "char_stats", "items"):
    st.db.execute("DELETE FROM %s WHERE char_id = ?" % _table, (_cid,))
st.db.execute("DELETE FROM characters WHERE id = ?", (_cid,))
st.db.commit()
_new, _ = st.create_character(_acc, "Newcomer", 0, "1")
if not storage.using_postgres():
    check("a new character after the last one deleted takes its id (SQLite)", _new, _cid)
check("  ..and inherits neither its ledger nor its loans: its one row is its own start",
      ([(r["source"], r["afro"], r["gold"]) for r in st.ledger(_new)],
       st.lent_at(_new, LENT_Q), adds_up(st, _new)),
      ([("start", progression.START_AFRO, 0)], None,
       ((progression.START_AFRO, 0), (progression.START_AFRO, 0))))
if not storage.using_postgres():
    check("  ..the old rows stay history, under the id negated",
          [r["source"] for r in st.ledger(-_cid)], ["start", "opening"])
st.close()


# --- the in-process server -------------------------------------------------------------------
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("merchant", "secret")
_store.close()
CRED = accounts.credential("merchant", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)

check("the journal: 25 ordinary quests (the wiki's «Максимальное их число 25»), and the"
      " ways and services beside them", (server.QUEST_LOG_CAPACITY,
                                         server.CLIENT_QUEST_LOG_CAPACITY), (25, 35))


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.read = 0
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

    async def drain(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def pending(sess):
    """What the session sent since the last look, without a command."""
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def order(frames):
    return [n for n, _p in frames]


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def of(frames, name):
    return [p for n, p in frames if n == name]


def purse(sess):
    return sess.char.afro, sess.char.gold


def goto(sess, loc_id):
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % loc_id)
    run(sess, "lenter;accept=1;")
    return {npc.type_id: eid for eid, npc in sess.room.npcs.items()}


def take(sess, npc, qtype, npc_type=652):
    return run(sess, "q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))


def status(sess, qtype):
    return of(run(sess, "q_status;q_type=%d;" % qtype), "q_status")[0]["status"]


async def main():
    sess = server.Session(Writer(), "merchant")
    run(sess, "hello;minor=2;major=0;")
    login = run(sess, "login;hash=@%s@;" % CRED)
    check("the client is told a journal of 35: 25 ordinary and 10 of ways and services",
          [p["quest_log_capacity"] for p in of(login, "constants")], [35])
    run(sess, "newPers;res=1;sex=0;name=@Merchant@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    cid = sess.char_id
    start = purse(sess)

    # --- 5a. c_ga: one ack for any figure --------------------------------------------
    # Off the socket first: a figure the frame reader cannot read at all
    # (protocol.decode takes "nan" and "abc" for whole numbers) is answered
    # by its command's name, one ack each, where it used to be dropped.
    reader = asyncio.StreamReader()
    reader.feed_data(b"c_ga;gold=nan;\x00c_ga;gold=abc;\x00c_ga;gold=1e400;\x00")
    reader.feed_eof()
    raw_writer = Writer()
    await server.handle_client(reader, raw_writer)
    check("frames the reader cannot read, and inf: one ack each",
          (order(raw_writer.frames), acks(raw_writer.frames)),
          (["cmdAck"] * 3, [server.RES_NOT_READY, server.RES_NOT_READY,
                            server.RES_NOT_AVAILABLE]))
    # The three commands whose answer turns on a value (expects_ack), in a
    # frame past reading: the value read on its own decides.
    BAD = [b"bg_op;op=0;x=nan;", b"bg_op;op=5;x=nan;", b"p_op;op=5;x=nan;",
           b"p_op;op=1;x=nan;", b"ss_upd;s_status=0;x=nan;", b"ss_upd;s_status=1;x=nan;",
           b"bg_op;x=nan;"]
    check("a frame past reading waits for an answer as its command and value say: bg_op 0"
          " does, 5 not; p_op 5 not, 1 does; ss_upd 0 not, 1 does; a value past reading too"
          " is not answered", [server.bad_frame_expects_ack(b) for b in BAD],
          [True, False, False, True, False, True, False])
    reader = asyncio.StreamReader()
    reader.feed_data(b"\x00".join(BAD) + b"\x00")
    reader.feed_eof()
    raw_writer = Writer()
    await server.handle_client(reader, raw_writer)
    check("  ..on the socket: three acks for the seven, no other frame",
          (order(raw_writer.frames), acks(raw_writer.frames)),
          (["cmdAck"] * 3, [server.RES_NOT_READY] * 3))
    for figure in ("1e400", "-1e400", "-3", "0"):
        got = run(sess, "c_ga;gold=%s;" % figure)
        check("c_ga;gold=%s: one ack, a refusal, the purse untouched" % figure,
              (order(got), acks(got), purse(sess)), (["cmdAck"], [server.RES_NOT_AVAILABLE], start))
    run(sess, "userMsg;entry=@/money 0 300@;group=0;")
    got = run(sess, "c_ga;gold=100;")
    rate = progression.GOLD_TO_AFRO_RATE
    check("c_ga;gold=100: an ounce into %d afro, one ack, then the purse" % rate,
          (order(got), acks(got), purse(sess)),
          (["cmdAck", "userInfo_Player"], [0], (start[0] + rate, 200)))

    # --- 5c. a kill quest pays its fee at the take -----------------------------------
    npc = goto(sess, 102)
    geek = npc[652]
    before = purse(sess)
    check("the kill quest with a fee is offered to a purse that covers it", status(sess, KILL_FEE_Q), 1)
    got = take(sess, geek, KILL_FEE_Q)
    q = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    check("taken: the fee first, the ack, then the journal (complete=0, its kills alone)",
          (order(got), acks(got), purse(sess), [p["complete"] for p in of(got, "q_di_kill_mobs")]),
          (["userInfo_Player", "cmdAck", "q_di_kill_mobs"], [0], (before[0] - KILL_FEE, before[1]),
           [0]))
    got = run(sess, "q_ca;q_id=%d;" % q[0])
    check("dropped: the fee back, then the ack", (order(got), acks(got), purse(sess)),
          (["userInfo_Player", "cmdAck"], [0], before))
    row = quests.get(KILL_FEE_Q)
    got = take(sess, geek, KILL_FEE_Q)
    q = [p["q_id"] for n, p in got if n.startswith("q_di_")][0]
    check("  ..the fee paid is kept with the instance",
          json.loads(server.STORE.quest(q)["progress_json"]).get(server.FEE_PAID), [KILL_FEE, 0])
    row.cost_afro = KILL_FEE * 10
    got = run(sess, "q_ca;q_id=%d;" % q)
    check("  ..dropped after the row's fee went up: what was paid comes back, not the new fee",
          (acks(got), purse(sess)), ([0], before))
    row.cost_afro = 0
    got = take(sess, geek, KILL_FEE_Q)
    q = [p["q_id"] for n, p in got if n.startswith("q_di_")][0]
    row.cost_afro = KILL_FEE
    got = run(sess, "q_ca;q_id=%d;" % q)
    check("  ..one taken while the row asked nothing paid nothing and gets nothing back",
          (acks(got), order(got), purse(sess)), ([0], ["cmdAck"], before))
    got = take(sess, geek, KILL_FEE_Q)
    q = [p["q_id"] for n, p in got if n.startswith("q_di_")][0]
    server.STORE.update_quest(q, {"kill_num": [3]}, True)
    run(sess, "userMsg;entry=@/money -%d 0@;group=0;" % purse(sess)[0])
    check("the purse emptied after the kills", purse(sess)[0], 0)
    got = run(sess, "q_co;obj_idx=0;mob=%d;q_id=%d;" % (geek, q))
    check("handed in with an empty purse: no refusal (no «дневной лимит»), no journal"
          " frame of junk, the reward and no second fee",
          (acks(got), [n for n in order(got) if n.startswith("q_di_")], purse(sess)[0]),
          ([0], [], KILL_PAY))
    check("  ..short of the fee it is not offered again", status(sess, KILL_FEE_Q), 0)
    run(sess, "userMsg;entry=@/money 1000 0@;group=0;")
    check("  ..and with the fee in the purse it is", status(sess, KILL_FEE_Q), 1)

    # --- 5d. lent rounds, once a day ---------------------------------------------------
    got = take(sess, geek, LENT_Q)
    ql = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    check("the lent gun and rounds into the bag", (acks(got), have.get(TRAINING_GUN),
                                                   have.get(TRAINING_ROUNDS)), ([0], 1, 10))
    run(sess, "q_ca;q_id=%d;" % ql[0])
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    check("dropped: both back", (have.get(TRAINING_GUN), have.get(TRAINING_ROUNDS)), (None, None))
    check("  ..nothing used: the loan struck, the quest offered again at once (a lesson"
          " dropped by mistake is not lost for the day)",
          (server.STORE.lent_at(cid, LENT_Q), status(sess, LENT_Q)), (None, 1))
    got = take(sess, geek, LENT_Q)
    ql = [p["q_id"] for n, p in got if n.startswith("q_di_")] or [0]
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    check("  ..taken again: lent again", (acks(got), have.get(TRAINING_ROUNDS)), ([0], 10))
    sess.inv.take_pieces(TRAINING_ROUNDS, 3)
    pending(sess)
    run(sess, "q_ca;q_id=%d;" % ql[0])
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    check("  ..dropped with three rounds shot: the rest back, and the rounds are not lent"
          " again today: not offered, not taken",
          (have.get(TRAINING_ROUNDS), status(sess, LENT_Q), acks(take(sess, geek, LENT_Q))),
          (None, 0, [server.RES_NOT_AVAILABLE]))
    server.STORE.db.execute("UPDATE char_lent SET lent_at = lent_at - 86400 WHERE char_id = ?",
                            (cid,))
    server.STORE.db.commit()
    got = take(sess, geek, LENT_Q)
    check("  ..the next day they are", acks(got), [0])
    run(sess, "q_ca;q_id=%d;" % [p["q_id"] for n, p in got if n.startswith("q_di_")][0])
    # Kept in its place (stay_in): carried out, the loan is taken back on
    # arrival (Session.keep_lent), and the drop after it finds nothing to
    # count -- the arrival strikes the loan when all of it came back.
    got = take(sess, geek, LENT_STAY_Q)
    ql = [p["q_id"] for n, p in got if n.startswith("q_di_")] or [0]
    goto(sess, 35)
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    run(sess, "q_ca;q_id=%d;" % ql[0])
    check("kept in its place (stay_in) and carried out unused: both taken back on arrival, the"
          " loan struck; dropped then, offered again at once",
          (acks(got), have.get(TRAINING_GUN), have.get(TRAINING_ROUNDS),
           server.STORE.lent_at(cid, LENT_STAY_Q), status(sess, LENT_STAY_Q)),
          ([0], None, None, None, 1))
    geek = goto(sess, 102)[652]
    got = take(sess, geek, LENT_STAY_Q)
    ql = [p["q_id"] for n, p in got if n.startswith("q_di_")] or [0]
    sess.inv.take_pieces(TRAINING_ROUNDS, 3)
    pending(sess)
    goto(sess, 35)
    have = {r["type_id"]: r["count"] for r in server.STORE.items_of(cid)}
    run(sess, "q_ca;q_id=%d;" % ql[0])
    check("  ..carried out with three rounds shot: the rest taken back on arrival, and dropped"
          " then it is not lent again today",
          (acks(got), have.get(TRAINING_ROUNDS), status(sess, LENT_STAY_Q)), ([0], None, 0))
    geek = goto(sess, 102)[652]

    # --- a stall: bought and sold ------------------------------------------------------
    here = sess.room.loc.id
    stall = next(eid for eid, n in sess.room.npcs.items() if n.root == world.TRADER
                 and any(items.root_of(t) == items.AMMO for t in items.stock_for(n.type_id, here)))
    ware = [t for t in items.stock_for(sess.room.npcs[stall].type_id, here)
            if items.root_of(t) == items.AMMO][0]
    index = items.stock_for(sess.room.npcs[stall].type_id, here).index(ware)
    run(sess, "ss_create;s_type=1;target=%d;" % stall)
    before = purse(sess)
    got = run(sess, "ss_upd;s_status=1;obj=x%x;param=20;" % index)
    bought = [str(p["obj"]).lstrip("x") for p in of(got, "ss_obj_status") if p["status"] == 1]
    spent = before[0] - purse(sess)[0]
    check("twenty rounds bought", (acks(got), len(bought), spent > 0), ([0], 1, True))
    got = run(sess, "ss_upd;s_status=2;obj=x%s;param=20;" % bought[0])
    check("  ..and sold back", (acks(got), purse(sess)[0] > before[0] - spent), ([0], True))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")

    # --- a healer ------------------------------------------------------------------------
    goto(sess, 37)
    medic = next(eid for eid, n in sess.room.npcs.items() if n.root == world.HEALER)
    medic_type = sess.room.npcs[medic].type_id
    before = purse(sess)
    got = run(sess, "on_conv;mob=%d;op=1;" % medic)
    fee = npcs.healer_price(medic_type, server.MEDIC_PRICE)
    check("healed for the healer's fee", (acks(got), purse(sess)[0]), ([0], before[0] - fee))

    # --- 5b. a way that moves nobody gives its fee back -------------------------------
    way = quests.Quest(dict(type=90041, kind="del_obj", name="Платная дорога", obj=0,
                            give=[652], take=[652], cost_afro=100, cost_gold=20, repeatable=1))
    before = purse(sess)
    sess.follow_way(way, object())
    check("a way whose player is no longer in its room: the fee back, the purse told",
          (purse(sess), order(pending(sess))),
          ((before[0] + 100, before[1] + 20), ["userInfo_Player"]))
    sess.hold_line = lambda verb: ("timer", None)
    before = purse(sess)
    sess.follow_way(way, sess.room)
    check("  ..one held by a fight waits, the fee kept", (sess.way is not None,
                                                          sess.way_quest is way, purse(sess)),
          (True, True, before))
    sess.cancel_way()
    del sess.hold_line
    check("  ..and the wait ended with nobody moved (the room left, the socket gone):"
          " the fee back, once", (sess.way, sess.way_quest, purse(sess)),
          (None, None, (before[0] + 100, before[1] + 20)))
    sess.cancel_way()
    check("  ..not twice", purse(sess), (before[0] + 100, before[1] + 20))
    rewarded = quests.Quest(dict(type=90045, kind="del_obj", name="Дорога с наградой", obj=0,
                                 give=[652], take=[652], cost_afro=100, rew_afro=30,
                                 repeatable=1))
    before = purse(sess)
    pending(sess)
    sess.follow_way(rewarded, object())
    check("  ..one whose hand-in paid a reward too keeps its fee: no reward for nothing",
          (purse(sess), order(pending(sess))), (before, []))

    # --- 4. the journal of money ---------------------------------------------------------
    run(sess, "logout;")
    rows = server.STORE.ledger(cid)
    afro, gold = server.STORE.money(cid)
    check("the ledger sums to the purse, afro and gold",
          (sum(r["afro"] for r in rows), sum(r["gold"] for r in rows)), (afro, gold))
    sources = [r["source"] for r in rows]
    check("every change booked under what made it -- and none under nothing",
          sorted(set(sources)), sorted({"start", "admin", "c_ga", "quest_fee", "quest_refund",
                                        "quest", "shop_buy", "shop_sell", "healer"}))
    by = lambda src: [(r["ref"], r["afro"], r["gold"]) for r in rows if r["source"] == src]
    check("  ..the newborn's thousand first", (rows[0]["source"], rows[0]["afro"], rows[0]["level"]),
          ("start", progression.START_AFRO, 0))
    check("  ..c_ga: an ounce out, its afro in", by("c_ga"), [(0, rate, -100)])
    check("  ..the kill quest: its fee three times, given back twice, then its reward",
          (by("quest_fee"), by("quest")),
          ([(KILL_FEE_Q, -KILL_FEE, 0)] * 3, [(KILL_FEE_Q, KILL_PAY, 0)]))
    check("  ..the refunds: the dropped quest's fee twice, as paid, and the way's twice",
          by("quest_refund"), [(KILL_FEE_Q, KILL_FEE, 0)] * 2 + [(90041, 100, 20)] * 2)
    check("  ..the stall by the thing, the healer by his type",
          ([r for r, _a, _g in by("shop_buy")], [r for r, _a, _g in by("shop_sell")],
           by("healer")),
          ([ware], [ware], [(medic_type, -fee, 0)]))
    check("  ..each row with its level", {r["level"] for r in rows}, {0})
    s = money_report.summarize(rows)
    check("the report sums per source, band and day",
          (s["total"].rows, s["total"].afro_in + s["total"].afro_out,
           s["total"].gold_in + s["total"].gold_out,
           sorted(s["source"]) == sorted(set(sources)),
           sorted({band for band, _src in s["band"]})),
          (len(rows), afro, gold, True, ["0-8"]))
    text = money_report.report(rows)
    check("  ..and prints them", all(w in text for w in ("By source:", "By level band",
                                                          "By day (UTC)", "c_ga", "quest_fee")),
          True)
    now = int(time.time())
    check("  ..its days are the game's: the daily reset is at UTC midnight",
          (server.DAILY_RESET_TIME, money_report.day_of(server.Session.day_start(now)),
           money_report.day_of(server.Session.day_start(now) + 86399)),
          (0, money_report.day_of(now), money_report.day_of(now)))


class _Errors(logging.Handler):
    """Every failure the server logs: a handler that raised is one."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.seen = []

    def emit(self, record):
        self.seen.append(record.getMessage())


_errors = _Errors()
logging.getLogger("lava").addHandler(_errors)
asyncio.run(main())
check("no handler failed on the way (only the frames nobody can read were logged)",
      [m for m in _errors.seen if not m.startswith("  bad frame")], [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa fixups OK")
