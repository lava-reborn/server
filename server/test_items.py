"""The wiki laid over the item catalogue: numbers, names, stocks, and the
invariants the client's arithmetic rests on.

In process, no sockets: items.static_info is what cmd_ss_get_si sends, so
what it returns is what the client gets. Twenty linked types picked at
random must answer with the wiki's numbers, every unlinked one with the
designed frame unchanged but for the overlays the server lays on purpose
(each on its own keys), and every linked type must keep every key of its
frame with no zero where the client divides (items.py, top).

    wsl.exe -e python3 server/test_items.py            # random sample
    LAVA_TEST_SEED=7 wsl.exe -e python3 server/test_items.py
"""
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import craft
import events
import items
import names
import production
import progression
import quests
import sets
import setcraft

from testkit import check, fails  # noqa: E402


SEED = int(os.environ.get("LAVA_TEST_SEED") or time.time())
print("sample seed %d (LAVA_TEST_SEED to repeat)" % SEED)
rnd = random.Random(SEED)

cat = items.catalogue()
wiki = items.wiki()
manual = items.heal_manual()
cold = items.coldarm_manual()
loot = items.loot_manual()
linked = sorted(t for t in wiki if t in cat)
# Types with hand-made numbers (data/heal_manual.json, the pieces of
# data/sets.json, the mine's loot in data/loot_manual.json) are neither: they
# must keep the frame's invariants like a wiki type, but their numbers come
# from a file of ours. The cold arms of data/coldarm_manual.json are linked,
# with the file filling their holes. So do the weapon craft's modified guns
# and blueprints (craft.derived: the base gun's table, the level's price).
pieces = sorted(sets.ITEMS)
# And the reworked pieces of the ladder and the clothing cheques (setcraft.py);
# a reworked piece is described by its rung's words under its rung's id.
crafted = sorted(t for t in cat if setcraft.record(t))
own_desc = {t: items.DESC_ID_OFFSET + setcraft.base_of(t) for t in crafted}
# And the miner's clothes (items.MINER_WEAR: a rung's piece's numbers) and
# what the admin's overrides set (items.ADMIN_OVERRIDES).
unlinked = sorted(t for t in cat if t not in wiki and t not in manual and t not in sets.ITEMS
                  and t not in cold and t not in loot and t not in crafted
                  and not craft.derived(t) and t not in items.MINER_WEAR
                  and t not in items.ADMIN_OVERRIDES)
check("the wiki describes over a thousand catalogued types", len(linked) >= 1100, True)
check("and every table names a type the client has", len(linked), len(wiki))


def numbers_only(v):
    if isinstance(v, list):
        return all(numbers_only(x) for x in v)
    return isinstance(v, (int, float, str)) and not isinstance(v, bool)


# --- twenty linked types answer with the wiki's numbers ---------------------
# Scalars the wiki and the frame share are compared as they are; a pack of
# rounds is priced per pack on the wire and per round on the wiki.
SCALARS = ("weight", "cost", "g_cost", "exchang", "premium", "quest", "clip_size",
           "reload_cost", "max_break_abs", "weapon_type", "armor_class", "slot_type",
           "min_h_rest", "max_h_rest", "use_count", "heal_cost", "strike_cost",
           "max_count", "range_mod", "acc_mod", "dam_mod", "st_mod")
for t in rnd.sample(linked, 20):
    rec = wiki[t]
    cmd, p = items.static_info(t)
    root = cat[t][0]
    mismatch = {}
    # What data/coldarm_manual.json decided for a hole in the table.
    ours = items._holes(rec, cold.get(t, {}))
    # A trophy changes hands whatever its article's second, misread
    # "Допустимость обмена" row says (items.static_info, trophies.py).
    if root == items.TROPHY:
        ours = dict(ours, exchang=1)
    # A price the server sets over its article on purpose, held below for
    # every such type: sold for gold alone (items.GOLD_PRICE_ONLY), or a
    # record that is another article's (items.OWN_ARTICLE_PRICE).
    if t in items.GOLD_PRICE_ONLY or t in items.OWN_ARTICLE_PRICE:
        ours = dict(ours, cost=p["cost"])
    # So is a gold round's, a hundredth of an ounce a round whatever its
    # article says (items.GOLD_AMMO_ROUND; every one of them in test_repair).
    if root == items.AMMO and items.gold_round(p):
        ours = dict(ours, g_cost=p["g_cost"])
    # And a medicine's number data/heal_manual.json lays over its article
    # (items.heal_over_article; every one of them held below).
    ours = dict(ours, **{k: v for k, v in items.heal_over_article().get(t, {}).items()
                         if not k.startswith("_")})
    for key in SCALARS:
        if key in rec and key in p and key not in ours:
            want = rec[key]
            if key == "weight":
                want = int(round(want))
            if root == items.AMMO and key in ("cost", "g_cost"):
                want = rec[key] * p["sell_num"]
            if p[key] != want:
                mismatch[key] = (p[key], want)
    for key in ("h_damage_min", "h_damage_max", "fire_costs", "opt_range"):
        if key in rec and isinstance(rec[key], list) and p.get(key) != rec[key]:
            mismatch[key] = (p.get(key), rec[key])
    check("%d %s (%s): wiki numbers on the wire" % (t, cat[t][1], rec["name_ru"]),
          mismatch, {})
    if items.clean_text(rec.get("desc_ru", "")):
        check("  ..its description travels as %d" % (items.DESC_ID_OFFSET + t),
              p["desc"], items.DESC_ID_OFFSET + t)

# The prices laid over the article on purpose, every one of them (the sample
# above leaves their cost alone): a thing sold for gold alone keeps its gold
# price and has no afro one -- the gold lottery's ticket and the gold line's
# blueprints (2026-09-28) --, and the Вади-Хальфа lottery's ticket costs its
# own article's 500.
check("sold for gold alone: no afro price, the article's gold price",
      sorted(t for t in items.GOLD_PRICE_ONLY if t in cat
             and (items.params_of(t)["cost"] or not items.params_of(t)["g_cost"])), [])
check("  ..the gold lottery's ticket and the gold line's blueprints among them",
      (1333 in items.GOLD_PRICE_ONLY, sorted(t for t in cat if t in wiki
                                              and cat[t][1].startswith("bpg_damage_25_gold_")
                                              and t not in items.GOLD_PRICE_ONLY)), (True, []))
check("a record that is another article's: its own article's price",
      {t: items.params_of(t)["cost"] for t in items.OWN_ARTICLE_PRICE if t == 1307}, {1307: 500})
# Абри's stalls (2026-10-12): the things whose articles no record carries, at
# their articles' prices -- the bus tickets, the lottery tickets, the
# junkyard's tools -- and the chain's gypsum, wire and bandages at a designed 50.
# And Донгола's (2026-10-13): the ticket to Абри 110 and the lottery tickets
# [14] 2400 and [G][14] 3 G, their articles'; the ticket from Абри 100, the
# fare of the same ride (DESIGNED, server/test_dongola_trade.py). And
# Абу-Хамед's (2026-10-14): the lottery tickets [16] 3000, [18] 3700, [19] 4730
# and their [G] 3 G, 3.5 G, 4.5 G, the bus tickets from Донгола 0.25 G and to it
# 0.10 G -- their articles', in gold alone (server/test_abuhamed_trade.py).
check("  ..and Абри's, Донгола's and Абу-Хамед's things with an article and no record:"
      " theirs, afro or gold alone",
      ({t: items.params_of(t)["cost"] for t in items.OWN_ARTICLE_PRICE if t != 1307},
       {t: (items.params_of(t)["cost"], items.params_of(t)["g_cost"])
        for t in items.ARTICLE_GOLD_PRICE}),
      (dict([(6544, 100), (6545, 150), (6546, 100), (6547, 110), (2646, 1000), (2647, 1700),
             (2648, 2400), (2652, 3000), (2653, 3700), (3574, 4730),
             (5740, 50), (5741, 50), (5742, 50)]
            + [(t, 100) for t in (7025, 7026, 7027, 7028, 7029, 7036, 7037, 7038, 7039, 7040,
                                  7041, 7042)]),
       {2649: (0, 200), 2650: (0, 250), 2651: (0, 300), 2654: (0, 300), 2655: (0, 350),
        3575: (0, 450), 1567: (0, 25), 1639: (0, 10), 6294: (0, 10), 6295: (0, 100),
        6296: (0, 1000)}))

# --- every unlinked type keeps the designed frame ------------------------------
# All of them, not a sample: twenty drawn by the clock failed now and then on
# a type the server changes on purpose (one run in ten by 2026-09-28, 196 of
# 25 760). What items.static_info lays on a type the wiki has no table for on
# purpose is laid here on the designed frame, each overlay on its own keys
# alone; anything else it changes is a failure.
def deliberate(t):
    """The designed frame of an unlinked type with the server's deliberate
    overlays, each on its own keys: a simple object's original words
    (names.ORIG_ITEM_DESCS), the ore's and the plant's numbers
    (production.item_numbers), a price of the server's (GOLD_PRICE_ONLY,
    ARTICLE_GOLD_PRICE, OWN_ARTICLE_PRICE, GOLD_INGOTS), a trophy's exchange, and the quest flag
    of a thing a quest lends or a place keeps (quests.lent, events.kept)."""
    cmd, p = items.designed_info(t)
    p = dict(p)
    root = cat[t][0]
    if root == items.TROPHY:
        p["exchang"] = 1
    if root == items.TRASH and not p.get("desc") and t in items._orig_described():
        p["desc"] = items.DESC_ID_OFFSET + t
    p.update(production.item_numbers(t) or {})
    if t in items.ARTICLE_GOLD_PRICE:
        p["g_cost"] = items.ARTICLE_GOLD_PRICE[t]
    if t in items.GOLD_PRICE_ONLY:
        p["cost"] = 0
    if t in items.OWN_ARTICLE_PRICE:
        p["cost"] = items.OWN_ARTICLE_PRICE[t]
    if t in items.GOLD_INGOTS:
        p.update(cost=items.GOLD_INGOTS[t] * progression.GOLD_TO_AFRO_RATE
                 // progression.GOLD_OUNCE, g_cost=items.GOLD_INGOTS[t])
    if quests.lent(t) or events.kept(t):
        p.update(quest=1, exchang=0)
    return cmd, p


changed = {}
for t in unlinked:
    got, want = items.static_info(t), deliberate(t)
    if got != want:
        changed[t] = (cat[t][1], sorted(k for k in set(got[1]) | set(want[1])
                                        if got[1].get(k) != want[1].get(k)))
check("every unlinked type (%d) keeps the designed frame but for the overlays laid on"
      " purpose" % len(unlinked), changed, {})
check("  ..those overlays at work: an original description, the ore, a lent thing, the"
      " prison's armband",
      [items.static_info(t) != items.designed_info(t) for t in (425, 3636, 3727, 2476)],
      [True] * 4)
check("an unlinked item has no description", items.static_info(4380)[1]["desc"], "")

# --- invariants over the whole linked catalogue -----------------------------
check("hand-made heal numbers are for types the client has and the wiki lacks",
      [t for t in manual if t not in cat or t in wiki or cat[t][0] != items.HEAL], [])
check("set pieces are types the client has, all of them clothing",
      [t for t in pieces if cat.get(t, (None,))[0] != items.WEAR], [])
check("hand-made cold-arm numbers are for cold arms the client has",
      [t for t in cold if cat.get(t, (None,))[0] != items.COLD_ARM], [])
check("the hand-made loot numbers -- the mine's sand and emeralds, the gold ingots of "
      "1, 5 and 10 ounces -- are for simple objects the client has and the wiki lacks",
      (sorted(loot), [t for t in loot if cat.get(t, (None,))[0] != items.TRASH or t in wiki]),
      ([2258, 3159, 4796, 4797, 7620], []))
check("  ..and fill only holes: a positive wiki value stays, a price stays whole",
      (items._holes({"cost": 5, "strike_cost": 0}, {"cost": 100, "strike_cost": 5}),
       items._holes({"g_cost": 3}, {"cost": 100, "strike_cost": 5}),
       items._holes(None, {"cost": 100})),
      ({"strike_cost": 5}, {"strike_cost": 5}, {"cost": 100}))
bad = {}
for t in linked + sorted(manual) + pieces + sorted(set(cold) - set(linked)) + sorted(loot) \
        + crafted + sorted(set(items.MINER_WEAR) | set(items.ADMIN_OVERRIDES)):
    root = cat[t][0]
    cmd, p = items.static_info(t)
    dcmd, d = items.designed_info(t)
    why = []
    if cmd != dcmd:
        why.append("command %s != %s" % (cmd, dcmd))
    missing = set(d) - set(p)
    if missing:
        why.append("keys lost %s" % sorted(missing))
    extra = set(p) - set(d) - set(items.NEED_BONUS_KEYS)
    if extra:
        why.append("keys added %s" % sorted(extra))
    if not all(numbers_only(v) for v in p.values()):
        why.append("non-numeric value")
    if p["name"] != items.STRING_ID_OFFSET + t or not names.known(p["name"]):
        why.append("name id %r not preloaded" % p["name"])
    if p["desc"] != "" and (p["desc"] != own_desc.get(t, items.DESC_ID_OFFSET + t)
                            or not names.known(p["desc"])):
        why.append("desc id %r not preloaded" % p["desc"])
    if not isinstance(p["weight"], int) or p["weight"] < 0:
        why.append("weight %r" % p["weight"])
    if p["sell_num"] < 1:
        why.append("sell_num %r" % p["sell_num"])
    if "max_count" in p and not (1 <= p["sell_num"] <= p["max_count"]):
        why.append("sell_num %r vs max_count %r" % (p["sell_num"], p["max_count"]))
    if root == items.FIRE_ARM:
        if not any(p["fire_mods"]):
            why.append("no fire mode")
        for key in ("h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max",
                    "max_range", "opt_range", "end_opt_range", "target_size",
                    "piercing", "fire_costs", "fire_times", "fire_mods"):
            if not isinstance(p[key], list) or len(p[key]) != 3:
                why.append("%s not three modes" % key)
        if any(v <= 0 for v in p["max_range"]) or any(v <= 0 for v in p["target_size"]):
            why.append("zero divisor %r / %r" % (p["target_size"], p["max_range"]))
        if p["clip_size"] < 1:
            why.append("clip_size %r" % p["clip_size"])
        if p["weapon_type"] not in range(6):
            why.append("weapon_type %r" % p["weapon_type"])
        if not p["comp_array"] or any(items.root_of(a) != items.AMMO for a in p["comp_array"]):
            why.append("comp_array %r" % p["comp_array"])
        if not (p["action_map"] & items.ACT_LOAD and p["action_map"] & items.ACT_FIRE):
            why.append("action_map %r" % p["action_map"])
    elif root == items.HEAL:
        if p["use_count"] < 1:
            why.append("use_count %r" % p["use_count"])
    elif root == items.WEAR:
        if p["slot_type"] not in range(6):
            why.append("slot_type %r" % p["slot_type"])
    elif root == items.COLD_ARM:
        if p["max_range"] <= 0:
            why.append("max_range %r" % p["max_range"])
    if why:
        bad[t] = why
check("every linked or designed type keeps its frame and the client's invariants", bad, {})

# --- a few known articles, by hand ------------------------------------------
cmd, p = items.static_info(6092)
check("9mm rounds: a pack of 20 at the wiki's 1 afro a round", (p["sell_num"], p["cost"]), (20, 20))
check("9mm rounds: the wiki's modifiers", (p["range_mod"], p["acc_mod"]), (1.2, 1.1))
cmd, p = items.static_info(192)
check("MG-3: the wiki's clip and class", (cmd, p["clip_size"], p["weapon_type"]),
      ("ss_si_firearm", 100, items.MACHINEGUN))
check("MG-3: three fire modes as the wiki has them", p["fire_mods"], [3, 6, 9])
check("MG-3: needs the wiki's shooting skill", (p["need_skills_m"], p["need_skills"]), (2, [20]))
check("MG-3: chambers real rounds of its class", set(p["comp_array"]) >= set(items.AMMO_762x51), True)
cmd, p = items.static_info(26242)
check("AK: comp_array from the wiki's calibre", 6098 in p["comp_array"], True)
check("AK: gold rounds of the calibre chamber too", 6158 in p["comp_array"], True)

# The rounds a gun takes are its article's. Most articles name them in their
# «Боеприпасы» section alone, not in a table row: «P90 ... ==Боеприпасы==
# [[5.7x28 (SS190)]]». Read here off the mirror itself (data/wiki/pages.json):
# each link of the section, less a round's quality and (G)/(P)/(PS)/(OLD) mark
# («9мм НАТО (G) ЭК»), is a calibre page, or the start of one's title
# («5.56х45мм» for «5.56х45мм НАТО»); a Mod page that links none takes its base
# article's. The gun takes every variant of each.
with open(os.path.join(os.path.dirname(HERE), "data", "wiki", "pages.json"),
          encoding="utf-8") as _fh:
    _PAGES = json.load(_fh)
_QUALITY = re.compile(r"\s*(?:\((?:G|P|PS|OLD)\))?\s*(?:КС|СТ|ОТ|ББ|ЭК|СБ|CБ|ШК)?\s*$")
_CALIBRES = [t for t, ids in items.links()[1].items()
             if ids and all(items.root_of(i) == items.AMMO for i in ids)]


def article_rounds(title):
    """Every round the article's «Боеприпасы» section names, as type ids."""
    text = (_PAGES.get(title) or {}).get("wikitext", "")
    body, inside = [], False
    for line in text.split("\n"):
        head = re.match(r"^==([^=].*?)==\s*$", line)
        if head:
            inside = head.group(1).strip() == "Боеприпасы"
        elif inside:
            body.append(line)
    out = set()
    for link in re.findall(r"\[\[([^\]|#]+)", "\n".join(body)):
        link = _QUALITY.sub("", link.strip()).strip()
        for page in _CALIBRES:
            if page == link or page.startswith(link + " "):
                out |= set(items.resolve_title(page, all_variants=True))
    return out


_MOD_TAIL = re.compile(r"\s+Mod\s*[IVX]+\s*$")
odd, said = [], 0
for t, rec in sorted(wiki.items()):
    if items.root_of(t) != items.FIRE_ARM:
        continue
    page = rec["_wiki"]["page"]
    want = article_rounds(page) or article_rounds(_MOD_TAIL.sub("", page))
    if want:
        said += 1
        if set(items.params_of(t)["comp_array"]) != want:
            odd.append((t, page))
check("every linked gun whose article names its rounds chambers those and no others --"
      " P90 5.7x28, Thompson .45, G3 7.62x51, M16A2 5.56x45, ПК 7.62x54R, Li-Enfield 7.62x54R",
      (odd[:12], len(odd)), ([], 0))
check("  ..which is most of the linked guns (801 of 965; the rest name theirs in a table"
      " row alone)", said >= 800, True)
check("  ..and a gun of no stated round keeps its class's: MEG-23 (its «23-й калибр» has"
      " no page)", items.params_of(5727)["comp_array"], items.AMMO_FOR[items.params_of(5727)["weapon_type"]])

# A modification asks for the level of the gun it is made of: РПД's table and its Mod
# pages' leave «Необходимые навыки» out, and the extractor puts the original's 16 into
# all of them (data/wiki_extract.ROW_FIXES).
_lvl = {}
for t, rec in wiki.items():
    if items.root_of(t) == items.FIRE_ARM and not _MOD_TAIL.search(rec["_wiki"]["page"]):
        _lvl.setdefault(rec["_wiki"]["page"], set()).add(
            max((items.params_of(t) or {}).get("need_skills") or [0]))
check("every linked gun modification asks for its base gun's level (РПД Mod VIII to XIV: 16)",
      sorted((t, rec["_wiki"]["page"]) for t, rec in wiki.items()
             if items.root_of(t) == items.FIRE_ARM and _MOD_TAIL.search(rec["_wiki"]["page"])
             and _lvl.get(_MOD_TAIL.sub("", rec["_wiki"]["page"]))
             and max(items.params_of(t).get("need_skills") or [0])
             not in _lvl[_MOD_TAIL.sub("", rec["_wiki"]["page"])]), [])
check("  ..РПД Mod XII (A) among them", max(items.params_of(24992).get("need_skills") or [0]), 16)
cmd, p = items.static_info(6235)
check("kitchen knife: the wiki's reach and cost", (cmd, p["max_range"], p["cost"]),
      ("ss_si_coldarm", 1.7, 1033))

# --- names and descriptions ----------------------------------------------
wn = items.wiki_names()
check("well over a thousand types carry a wiki name", len(wn) >= 1100, True)
check("rounds are named by calibre and column", (wn[6092], wn[6104], wn[6116]),
      ("9мм НАТО КС", "9мм НАТО СТ", "9мм НАТО ОТ"))
check("a gold copy is marked", wn[6236], "Кухонный нож (G)")
check("a type with a page but no table takes the title", wn.get(3727), "Тренировочные патроны")
check("a type tied to two pages keeps its internal name", 65 in wn, False)
# The original table, where it names a type, comes before the wiki; the
# wiki fills in the rest. So each id serves the original's name if there is
# one and the wiki's otherwise -- never anything else.
import orig_texts                                     # noqa: E402
_on = orig_texts.item_names()
check("each item id serves the original's name, else the wiki's",
      all(names.text(items.STRING_ID_OFFSET + t) == _on.get(t, n) for t, n in wn.items()),
      True)
check("and the original really is used where it has a name",
      names.text(items.STRING_ID_OFFSET + 25562) == _on.get(25562), True)
wd = items.wiki_descs()
check("over a thousand descriptions", len(wd) >= 1000, True)
_od = orig_texts.item_descs()
check("each description id serves the original's text, else the wiki's",
      all(names.text(items.DESC_ID_OFFSET + t) == _od.get(t, d) for t, d in wd.items()),
      True)
check("line breaks become <br>, markup goes",
      items.clean_text("'''Нельзя в бою.'''<br />\nКусок [[Мясо|мяса]].\n\nСухой."),
      "Нельзя в бою.<br>Кусок мяса.<br>Сухой.")
check("description and name ranges are apart from quests and mobs",
      (items.STRING_ID_OFFSET + max(cat) < 2_000_000,
       items.DESC_ID_OFFSET + max(cat) < 4_000_000), (True, True))

# --- stocks -----------------------------------------------------------------
table = items.stock_table()
check("the pistol stall opens on the guns the wiki named",
      items.stock_for(1200)[:len(items.WIKI_PISTOLS)], items.WIKI_PISTOLS)
check("and every one of them has a name to show it under",
      [t for t in items.WIKI_PISTOLS if t not in items.wiki_names()], [])
check("cheapest first, the revolver up to the Desert Eagle",
      [items.params_of(t)["cost"] for t in items.WIKI_PISTOLS],
      sorted(items.params_of(t)["cost"] for t in items.WIKI_PISTOLS))
check("and its rounds", all(a in items.stock_for(1200) for a in items.AMMO_9MM), True)
check("with the wiki's other pistol calibres behind them",
      6093 in items.stock_for(1200) and 6094 in items.stock_for(1200), True)
check("the knife trader sells what his page lists", 6235 in items.stock_for(1152), True)
check("but not the gold copy", 6236 in items.stock_for(1152), False)
check("a trader without a page has no stock", items.stock_for(999999), [])
check("dozens of traders got a wiki stock", len(table) >= 70, True)
bad = {t: [i for i in ids if i not in cat] for t, ids in table.items()}
check("every stocked type exists", {t: v for t, v in bad.items() if v}, {})
dup = {t: ids for t, ids in table.items() if len(set(ids)) != len(ids)}
check("no stock lists a type twice", dup, {})
gunsmiths = [t for t, ids in table.items() if any(items.root_of(i) == items.FIRE_ARM for i in ids)]
check("gunsmiths open on a gun",
      all(items.root_of(table[t][0]) == items.FIRE_ARM for t in gunsmiths), True)
check("every stocked type answers ss_get_si",
      all(items.static_info(i) for ids in table.values() for i in ids), True)

# --- Морис (5211): the valley's medicine, tiers 0_3 and 4_7 --------------------
# The valley's tiers of both lines (the owner's «чтобы везде всё было по
# уровням», 2026-10-12: the city's band 0-4 and the tier below it,
# server/shop_bands.py; until then his list of 2026-09-23 ran to 8_11), afro
# and gold, the 20-dose packs among the gold, and the two bar items without
# alcohol his own list keeps (data/npcs.json). This copy of his stall at the
# Nubian market (185) is what the data is held to, so a regeneration of the
# wiki or texts tables that puts a wrong name or number on any of them fails
# here; whatever the stall holds there is held to the same. The (P) kits of
# the old list are out of the game.
import re                                             # noqa: E402
import npcs                                           # noqa: E402
MORIS = [6055, 6061, 6073, 7100, 6056, 6062, 6074, 7101,
         6043, 6898, 6049, 6904, 6044, 6899, 6050, 6905,
         2178, 2184]
# HealItem.initialize (HealItem.as:35-51) reads these seventeen; a missing one
# is an undefined the client carries into its arithmetic.
HEAL_FIELDS = ("heal_time", "max_h_rest", "max_st_rest", "min_h_rest", "min_st_rest",
               "use_count", "bonus_prob", "bonus_act_time", "can_rest_br", "str_bonus",
               "dex_bonus", "sta_bonus", "per_bonus", "int_bonus", "heal_cost",
               "effects", "effects_prob")
AP_ROW = re.compile(r"Расход ОД:\s*</b>\s*(\d+)")
bad = {}
for t in dict.fromkeys(MORIS + items.stock_for(5211, 185)):
    info = items.static_info(t)
    if not info:
        bad[t] = ["no static info: ss_get_si would go unanswered"]
        continue
    cmd, p = info
    why = []
    if cmd != "ss_si_heal":
        why.append("command %s" % cmd)
    missing = [k for k in HEAL_FIELDS if k not in p]
    if missing:
        why.append("HealItem fields missing %s" % missing)
    if not names.known(p["name"]):
        why.append("name id %r not preloaded" % p["name"])
    elif names.text(p["name"]) == cat[t][1]:
        why.append("shown under its internal name %r" % cat[t][1])
    if p["desc"] != "" and not names.known(p["desc"]):
        why.append("desc id %r not preloaded" % p["desc"])
    if (p["cost"] > 0) == (p["g_cost"] > 0):
        why.append("priced in both currencies or in none: %r / %r" % (p["cost"], p["g_cost"]))
    if "bg_p_cost" in p:
        why.append("bg_p_cost turns the purchase into one for battleground points")
    if p["use_count"] < 1:
        why.append("use_count %r" % p["use_count"])
    if cat[t][1].startswith("Med_") and not re.search(r"_(0_3|4_7)_", cat[t][1]):
        why.append("tier of %s is not the valley's (0_3, 4_7)" % cat[t][1])
    if p["desc"] != "":
        m = AP_ROW.search(names.text(p["desc"]))
        if m and int(m.group(1)) != p["heal_cost"]:
            why.append("heal_cost %r, the original says %s" % (p["heal_cost"], m.group(1)))
    if why:
        bad[t] = why
check("Морис: each item answers ss_si_heal, named, described and priced once", bad, {})
check("Морис: no stimulant, alcohol or sleeping bag among them",
      [t for t in MORIS if 4917 <= t <= 4956 or t in (2180, 2181, 2182, 2183, 1289, 1535, 5341)],
      [])
check("  ..and his stall at the Nubian market is this list, the medicine of his city's tiers"
      " (shop_bands) before his own Лава-Кола and Шаурма", items.stock_for(5211, 185), MORIS)


def shown(t):
    """(name as the player reads it, the numbers a player compares)."""
    p = items.params_of(t)
    return (names.text(p["name"]), (p["min_h_rest"], p["max_h_rest"]),
            (p["min_st_rest"], p["max_st_rest"]), p["heal_cost"], p["use_count"],
            p["cost"], p["g_cost"], p["premium"])


# The ones the wiki had tied to the wrong type: a manioc root that called
# itself a first-aid kit, the "Мини" line carrying the "Эгоист" numbers.
check("6043 is the manioc root, food, out of combat",
      shown(6043), ("Корень Маниока$Еда", (68, 90), (5, 10), 0, 1, 12, 0, 0))
check("6067 is the Мини kit: premium, 5 uses, 7 AP",
      shown(6067), ("Аптечка «Мини» (5) (P)$Боевая Медицина", (90, 180), (90, 180), 7, 5, 0, 1, 1))
check("6904 is the Эгоист kit: gold, 20 uses, no premium needed; 0.02 G, not its article's"
      " 0.01 (data/heal_manual.json over_article: a use dearer than food and water, 2026-10-12)",
      shown(6904), ("Аптечка «Эгоист» (20) (G)$Лекарство", (135, 180), (152, 190), 0, 20, 0, 2, 0))
check("  ..the only number laid over an article there, and on a type that has one",
      ({t: sorted(k for k in rec if not k.startswith("_"))
        for t, rec in items.heal_over_article().items()},
       sorted(t for t in items.heal_over_article() if t not in wiki)), ({6904: ["g_cost"]}, []))
check("food of ten portions: Фуль",
      shown(6899), ("Фуль (10)$Еда", (90, 120), (5, 10), 0, 10, 210, 0, 0))
check("the energy drink no longer borrows an NPC's name",
      names.text(items.STRING_ID_OFFSET + 6062), "«Караванщик»$Боевой Энергетик")
check("the bottle of water no longer borrows a piece of junk's",
      names.text(items.STRING_ID_OFFSET + 6049), "Пластиковая бутылка (10)$Вода")
check("bar: Лава-Кола and Шаурма under their own names and prices",
      (shown(2178)[0], shown(2178)[5], shown(2184)[0], shown(2184)[5]),
      ("Лава-Кола", 20, "Шаурма", 250))
need = lambda t: (items.params_of(t).get("need_skills_m"), items.params_of(t).get("need_skills"))
check("the wiki's Медицина requirement travels with food and bandages",
      [need(t) for t in (6043, 6044, 6045, 6899, 6900, 6055, 6056, 6057)],
      [(None, None), (4, [2]), (4, [4]), (4, [2]), (4, [4]), (None, None), (4, [2]), (4, [4])])
# The designed ones (data/heal_manual.json) hold to the rule they were made by.
for pack, single in ((7100, 6073), (7101, 6074), (7102, 6075)):
    a, b = shown(pack), shown(single)
    check("%d: twenty doses of %d at twenty times the price" % (pack, single),
          (a[0].startswith("20 доз " + b[0].split(" (G)")[0]), a[1:4], a[4], a[6], a[5], a[7]),
          (True, b[1:4], 20, 20 * b[6], 0, 0))
    check("  ..and shows the injector's description",
          names.text(items.params_of(pack)["desc"]), names.text(items.params_of(single)["desc"]))
lo, mid1, mid2, hi = (items.params_of(t) for t in (6067, 6068, 6069, 6070))
check("the P kits Базовая and Индивидуальная sit between Мини and Стандарт",
      all(lo[k] < mid1[k] < mid2[k] < hi[k] for k in
          ("min_h_rest", "max_h_rest", "min_st_rest", "max_st_rest", "weight", "g_cost", "heal_cost")),
      True)
check("  ..premium, five uses, Медицина 2 and 4 on the bandages' ladder",
      [(p["premium"], p["use_count"], p.get("need_skills")) for p in (mid1, mid2, hi)],
      [(1, 5, [2]), (1, 5, [4]), (1, 5, [6])])

# --- premium (P) items are out of the game ---------------------------------
# Known by the flag, by the client's internal name, or by the original's
# "(P)": most premium types carry no flag at all, since only the wiki and the
# data files set it.
check("premium: a _pm pistol, a _P_ set piece, a _P medicine, a flagged robe",
      [items.premium(t) for t in (25568, 10069, 6067, 4299)], [True] * 4)
check("  ..and not their plain and gold twins",
      [items.premium(t) for t in (25566, 25567, 10059, 10079, 6055, 6073)], [False] * 6)
_offered = sorted({t for tr in list(npcs.STOCK) + list(items.stock_table())
                   for t in items.stock_for(tr)})
check("no stall anywhere offers a premium item",
      [t for t in _offered if items.premium(t)], [])
check("Морис sells no P kit: 18 things at his market, none of 6067-6069",
      (len(items.stock_for(5211, 185)), {6067, 6068, 6069} & set(items.stock_for(5211, 185))),
      (18, set()))
check("Борис sells no P pistol",
      [t for t in items.stock_for(5212) if items.premium(t)], [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("items OK")
