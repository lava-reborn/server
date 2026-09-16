"""Item catalogue: what a trader stocks, and what each item is.

The client knows 29 483 items by type id and internal name, and holds an icon
for each, but not one number about any of them: damage, weight, price and the
rest all lived on the server. So the static info assembled here is designed,
not recovered, and only its shape is taken from the client.

That shape matters more than it looks. Several fields the client divides by,
so a zero there is not a weak item but a broken one: target_size and max_range
feed the accuracy it computes itself, fire_mods doubles as the burst length
with zero meaning the mode is off, and sell_num and max_count divide prices
and stack sizes. action_map is a bitmask of the actions the item offers at
all; without the right bits a weapon cannot be loaded or fired.

Part of the numbers did survive, on the community wiki, whose tables were
copied off the game's own tooltips: data/items_wiki.json holds them for 1 164
types in the ss_si_* vocabulary, data/wiki_links.json ties wiki pages to type
ids, and data/trader_stock_wiki.json lists what 87 traders sold. Those are
laid over the designed frames here, field by field, never changing the shape
of a frame: a wiki table decides what a rifle does, the designed frame decides
which keys travel. The same files give the Russian names and descriptions
names.py serves.
"""
import json
import logging
import re
import os

import world

log = logging.getLogger("lava")

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WIKI_ITEMS_PATH = os.path.join(DATA, "items_wiki.json")
WIKI_LINKS_PATH = os.path.join(DATA, "wiki_links.json")
WIKI_STOCK_PATH = os.path.join(DATA, "trader_stock_wiki.json")

# A wiki page names a type through a link with a confidence; below this the
# link is a candidate the linker could not settle (two firearm lines fitting
# one article), and a candidate is not a name, a stock entry or a price.
LINK_CONFIDENCE = 0.5

# Item.as:39-45. The root type decides which ss_si_* frame describes the item.
FIRE_ARM, WEAR, HEAL, AMMO, TRASH, COLD_ARM, TROPHY = range(7)

SI_COMMAND = {
    FIRE_ARM: "ss_si_firearm",
    WEAR: "ss_si_wear",
    HEAL: "ss_si_heal",
    AMMO: "ss_si_ammo",
    TRASH: "ss_si_simple_obj",
    COLD_ARM: "ss_si_coldarm",
    TROPHY: "ss_si_trophy",
}

# Item.as:48-55, as powers of two: load, use on self, use on target, use on
# item, fire, unload, switch fire mode.
ACT_LOAD, ACT_USE_IDLE, ACT_USE_TARGET, ACT_USE_ITEM = 1, 2, 4, 8
ACT_FIRE, ACT_UNLOAD, ACT_USEMODE = 16, 32, 64

# FireArm.as:38-43
PISTOL, SHOTGUN, ASSAULT, RIFLE, MACHINEGUN, SMG = range(6)

# Ammunition, by calibre. objects.xml carries two families under root 3: the
# bare calibre records "_9mmNato", "_762x39", "_12mm", "_762x51" (ids 1, 8, 9,
# 23 and their _power/_med/_high variants below 500), which have no folder
# under classes/Ammo and so draw as nothing, and the Ammo_<calibre>_<mod>
# series from 6092 up, each with its icon. The mod suffix is the client's own
# vocabulary (Ammo.as:18-24): KS standard, ST steel core, OT tracer. Three
# mods per calibre are enough for a stall; the rest of the series (KS_P,
# OT_PS, gold) waits for real numbers from the wiki.
AMMO_9MM = [6092, 6104, 6116]        # Ammo_9mmNato_KS / _ST / _OT
AMMO_762x39 = [6098, 6110, 6122]     # Ammo_762x39_*
AMMO_762x51 = [6095, 6107, 6119]     # Ammo_762x51_*
AMMO_12MM = [6096, 6108, 6120]       # Ammo_12mm_*

# Designed stock, by the trader's own type id. The numbered series in
# objects.xml line up with the stalls: five tiers each, exactly what a
# tier-one shop would hold, followed by the rounds those guns take. The
# weapons stay first: the client refers to a purchase by its index in this
# list, and a test relies on the head of the pistol stall being a firearm.
# stock_for() is what goes on the wire: this table, extended with what the
# wiki says each of these traders sold, and the wiki alone for the rest.
STOCK = {
    1200: [4380, 4381, 4382, 4383, 4384] + AMMO_9MM,      # wh_Pistols
    1202: [4385, 4386, 4387, 4388, 4389] + AMMO_762x51,   # wh_Rifles
    1201: [4392, 4393, 4394, 4395, 4396] + AMMO_12MM,     # wh_Shotguns
    1203: [4397, 4398, 4399, 4400, 4401] + AMMO_762x39,   # wh_SubMachineGuns
    1204: [6848, 6853, 6858, 6863, 6868],                 # wh_wear_trd, shirts
    1205: [6847, 6849, 6850, 6852, 6854],                 # wh_set_trd, a raider set
}

# Which weapon class a series belongs to, and the ammunition it accepts.
WEAPON_CLASS = {
    4380: PISTOL, 4381: PISTOL, 4382: PISTOL, 4383: PISTOL, 4384: PISTOL,
    4385: RIFLE, 4386: RIFLE, 4387: RIFLE, 4388: RIFLE, 4389: RIFLE,
    4392: SHOTGUN, 4393: SHOTGUN, 4394: SHOTGUN, 4395: SHOTGUN, 4396: SHOTGUN,
    4397: ASSAULT, 4398: ASSAULT, 4399: ASSAULT, 4400: ASSAULT, 4401: ASSAULT,
}

# Rough per-class shape: damage at tier one, range, action points per shot,
# magazine, and how long a burst runs in each of the three fire modes.
CLASS_SHAPE = {
    PISTOL:     dict(dmg=(12, 26), rng=14, ap=10, clip=8,  modes=(1, 0, 0)),
    SHOTGUN:    dict(dmg=(24, 52), rng=9,  ap=18, clip=6,  modes=(1, 2, 0)),
    ASSAULT:    dict(dmg=(18, 40), rng=22, ap=15, clip=30, modes=(1, 3, 6)),
    RIFLE:      dict(dmg=(30, 66), rng=30, ap=20, clip=10, modes=(1, 0, 0)),
    MACHINEGUN: dict(dmg=(20, 44), rng=20, ap=22, clip=50, modes=(1, 5, 9)),
    SMG:        dict(dmg=(14, 30), rng=12, ap=12, clip=25, modes=(1, 3, 5)),
}

# What each class chambers. This is comp_array on the wire, and the client
# checks it itself before asking to load (FireArm.compare): a weapon with an
# empty list accepts nothing at all and cannot be loaded.
AMMO_FOR = {
    PISTOL: AMMO_9MM,
    SMG: AMMO_9MM,
    SHOTGUN: AMMO_12MM,
    ASSAULT: AMMO_762x39,
    RIFLE: AMMO_762x51,
    MACHINEGUN: AMMO_762x51,
}

# Rounds per trade pack, and the most one stack holds. The client divides the
# pack price by the first to show a per-round price, and caps the "how many"
# dialogue at the second; a purchase asks for rounds, never packs.
AMMO_PACK = 20
AMMO_STACK = 200

# Which slot classes a hand takes: PersEquip.checkUse and the drop targets in
# EquipInterface only ever put these three in primary/secondary. A heal item
# goes there by the client's own hand (PersEquip.as:339-349).
HAND_ROOTS = (FIRE_ARM, COLD_ARM, HEAL)
HEAPABLE_ROOTS = (AMMO, TRASH)
BREAKABLE_ROOTS = (FIRE_ARM, WEAR, COLD_ARM)

SLOT_HEAD, SLOT_CAMO, SLOT_ARMOR, SLOT_BELT, SLOT_LEGS, SLOT_BOOTS = range(6)

# Wear.as:44-56 wants a slot, and the series names say which.
SLOT_BY_PREFIX = {
    "helm": SLOT_HEAD, "warhat": SLOT_HEAD,
    "wear": SLOT_CAMO, "shirt": SLOT_CAMO,
    "vest": SLOT_ARMOR, "armor": SLOT_ARMOR,
    "belt": SLOT_BELT,
    "pants": SLOT_LEGS,
    "boots": SLOT_BOOTS,
}

# Creatures and items are numbered in separate spaces that overlap, while the
# strings they point at share one. The real texts.xml gave each its own string
# id; this offset keeps the stub's synthetic ones apart, so item 4380 no longer
# answers with the name of the creature that happens to share the number.
STRING_ID_OFFSET = 1000000

_CATALOGUE = None
_SERIES = re.compile(r"^([a-z_]+?)_(\d+)$")


def catalogue():
    """type_id -> (root_type_id, internal name), from the client's own table."""
    global _CATALOGUE
    if _CATALOGUE is None:
        txt = world._read(os.path.join(world.RES, "database", "objects.xml"))
        _CATALOGUE = {
            int(m.group(1)): (int(m.group(2)), m.group(3))
            for m in re.finditer(
                r'<object type_id="(\d+)" root_type_id=\s*"(\d+)"'
                r' name="([^"]*)"', txt)}
    return _CATALOGUE


def tier(name):
    """Trailing number of a series name, which is as close to a tier as we get."""
    m = _SERIES.match(name)
    return int(m.group(2)) if m else 1


def stock_for(trader_type):
    """What this trader sells, as the list of type ids the client indexes."""
    return stock_table().get(trader_type, [])


# --- the wiki -------------------------------------------------------------
# Each table is read once, on first use, and a table that cannot be read is
# a failure at start (TASKS 1.10), not a silently emptier world: names.py
# pulls the names at import, so both processes fall over before any client
# can be handed an id that would have been missing from the preload.

def _load_wiki(path, *keys):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return tuple(doc[k] for k in keys) if len(keys) > 1 else doc[keys[0]]
    except (OSError, ValueError, KeyError) as e:
        raise RuntimeError("wiki table %s cannot be loaded: %s: %s -- the server "
                           "does not start without it" % (path, type(e).__name__, e))


_WIKI = None
_LINKS = None
_STOCK = None


def wiki():
    """type_id -> the wiki's ss_si_* fields for it (data/items_wiki.json)."""
    global _WIKI
    if _WIKI is None:
        _WIKI = {int(k): v for k, v in _load_wiki(WIKI_ITEMS_PATH, "items").items()}
    return _WIKI


def links():
    """(page title -> type ids of its standard (A) variants,
    page title -> type ids of every variant, type_id -> page titles), from
    data/wiki_links.json with candidate links below LINK_CONFIDENCE left out."""
    global _LINKS
    if _LINKS is None:
        pages, by_type = _load_wiki(WIKI_LINKS_PATH, "pages", "by_type")
        standard, every = {}, {}
        for title, page in pages.items():
            a_ids, all_ids = [], []
            for link in page.get("links", []):
                if link.get("confidence", 0) < LINK_CONFIDENCE:
                    continue
                a_ids += (link.get("variants") or {}).get("A", [])
                all_ids += link.get("type_ids", [])
            if all_ids:
                # A page with no (A) column at all -- a gold-only item, say --
                # stands for whatever it lists.
                standard[title] = _unique(a_ids or all_ids)
                every[title] = _unique(all_ids)
        _LINKS = (standard, every, {int(k): v for k, v in by_type.items()})
    return _LINKS


def _unique(ids):
    out = []
    for i in ids:
        if i not in out:
            out.append(i)
    return out


def resolve_title(title, all_variants=False):
    """Type ids behind a wiki page title, or [] when the page is not linked.

    The standard variants by default -- what a stall sells and a quest
    asks for; all_variants adds the gold and premium copies, for the list
    of rounds a gun chambers.
    """
    return list(links()[1 if all_variants else 0].get(title, []))


# Stock order on the wire: guns first, rounds last, the rest between, so a
# stall opens on its wares and the client's index-based purchase keeps the
# head of a gunsmith's list a firearm.
_STOCK_ORDER = {FIRE_ARM: 0, COLD_ARM: 1, WEAR: 2, HEAL: 3, TRASH: 4, TROPHY: 5, AMMO: 6}


def stock_table():
    """trader type_id -> type ids on sale, built once.

    The designed table is the base for the six black-market stalls and the
    wiki (data/trader_stock_wiki.json) extends it; every other trader in the
    wiki list sells what its page lists. A title the linker never tied to a
    type id is logged once and left out rather than guessed.
    """
    global _STOCK
    if _STOCK is None:
        table = {t: list(ids) for t, ids in STOCK.items()}
        unresolved = {}
        for key, rec in _load_wiki(WIKI_STOCK_PATH, "by_type").items():
            trader = int(key)
            goods = []
            for title in rec.get("items", []):
                ids = [i for i in resolve_title(title) if i in catalogue()]
                if not ids:
                    unresolved.setdefault(rec.get("npc", key), []).append(title)
                    continue
                goods += ids
            if not goods:
                continue
            base = table.get(trader, [])
            extra = [i for i in _unique(goods) if i not in base]
            extra.sort(key=lambda i: _STOCK_ORDER.get(root_of(i), 4))
            if base:
                # keep the guns of the designed stall ahead of the new rounds
                guns = [i for i in base if root_of(i) == FIRE_ARM]
                rest = [i for i in base if root_of(i) != FIRE_ARM]
                new_guns = [i for i in extra if root_of(i) == FIRE_ARM]
                new_rest = [i for i in extra if root_of(i) != FIRE_ARM]
                table[trader] = guns + new_guns + rest + new_rest
            else:
                table[trader] = extra
        for npc, titles in sorted(unresolved.items()):
            log.warning("stock: %s: %d wiki titles without a type id, left out: %s",
                        npc, len(titles), ", ".join(titles))
        _STOCK = table
    return _STOCK


def root_of(type_id):
    """Root class of a type, or None when the client has no such type."""
    entry = catalogue().get(type_id)
    return entry[0] if entry else None


def params_of(type_id):
    """The static fields of a type as one dict, or None. What ss_si_* sends,
    read back here for prices, weight, clip size and slot."""
    info = static_info(type_id)
    return info[1] if info else None


def first_mode(fire_mods):
    """The first fire mode that is switched on. cur_mode must name one: the
    client reads fire_costs[cur_mode] and refuses to shoot on undefined."""
    for i, burst in enumerate(fire_mods):
        if burst:
            return i
    return 0


def _common(type_id, name, root, price, weight):
    return dict(
        type=type_id,
        name=STRING_ID_OFFSET + type_id,   # string id, not the item id
        desc="",
        vis=0, weight=weight, tech_dif=1, exchang=1,
        # No bg_p_cost here. Trade.buy switches to UPD_BGPOINTS_BUY the moment
        # the field is defined and numeric -- zero included -- so a 0 sent
        # "for completeness" turned every purchase into one for battleground
        # points, which the server then refused. Items actually priced that
        # way set the key themselves.
        cost=price, g_cost=0,
        # A trade pack of one. The client divides the price by this, so leaving
        # it out makes the shop show an undefined price rather than no price.
        sell_num=1,
        repair_mod=1, sell_mod=1, premium=0,
        quest=0, need_pvp_rep=0,
        action_map=0)


def static_info(type_id):
    """Everything the client needs to describe one item type.

    Returns (command, params) or None when the type is unknown. The frame is
    the designed one, with the wiki's numbers laid over it where the wiki
    has a table for this type (see _overlay).
    """
    info = designed_info(type_id)
    if info:
        rec = wiki().get(type_id)
        if rec:
            _overlay(type_id, info[1], rec)
    return info


def designed_info(type_id):
    """The designed frame alone: (command, params) or None. What the client
    gets for the 28 000 types the wiki says nothing about."""
    entry = catalogue().get(type_id)
    if not entry:
        return None
    root, name = entry
    t = tier(name)

    if root == FIRE_ARM:
        cls = WEAPON_CLASS.get(type_id, PISTOL)
        sh = CLASS_SHAPE[cls]
        lo, hi = sh["dmg"][0] + 4 * (t - 1), sh["dmg"][1] + 9 * (t - 1)
        modes = sh["modes"]
        p = _common(type_id, name, root, 120 * t, 1800 + 300 * t)
        p.update(
            action_map=ACT_LOAD | ACT_FIRE | ACT_UNLOAD | ACT_USEMODE,
            weapon_type=cls,
            clip_size=sh["clip"], reload_time=1500, reload_cost=4,
            max_break_abs=100 + 20 * t,
            # One entry per fire mode. A mode with fire_mods 0 is switched off,
            # and the client reads the same list as the burst length.
            fire_mods=list(modes),
            h_damage_min=[lo, int(lo * 0.8), int(lo * 0.7)],
            h_damage_max=[hi, int(hi * 0.8), int(hi * 0.7)],
            st_damage_min=[lo // 3, lo // 4, lo // 5],
            st_damage_max=[hi // 3, hi // 4, hi // 5],
            max_range=[sh["rng"], max(1, sh["rng"] - 4), max(1, sh["rng"] - 8)],
            opt_range=[2, 2, 1],
            end_opt_range=[sh["rng"] - 2, sh["rng"] - 6, max(2, sh["rng"] - 10)],
            # Never zero: the client divides by it to show the spread.
            target_size=[4, 5, 7],
            piercing=[t, t, t],
            fire_costs=[sh["ap"], sh["ap"] + 4, sh["ap"] + 8],
            fire_times=[700, 800, 900],
            comp_array=AMMO_FOR.get(cls, AMMO_9MM))
        return SI_COMMAND[root], p

    if root == WEAR:
        prefix = _SERIES.match(name).group(1) if _SERIES.match(name) else name
        p = _common(type_id, name, root, 80 * t, 900 + 200 * t)
        p.update(armor_class=t, slot_type=SLOT_BY_PREFIX.get(prefix, SLOT_CAMO),
                 max_break_abs=60 + 15 * t, set_type=0)
        return SI_COMMAND[root], p

    if root == AMMO:
        # cost is the price of one pack of sell_num rounds; the client
        # divides, so the two have to be read together.
        p = _common(type_id, name, root, 40, 12)
        p.update(max_count=AMMO_STACK, sell_num=AMMO_PACK, range_mod=1,
                 acc_mod=1, dam_mod=1, st_mod=1, piercing=1)
        return SI_COMMAND[root], p

    if root == HEAL:
        p = _common(type_id, name, root, 60 * t, 200)
        p.update(min_h_rest=20 * t, max_h_rest=35 * t,
                 min_st_rest=5 * t, max_st_rest=10 * t,
                 heal_time=1200, heal_cost=6, use_count=1,
                 bonus_prob=0, bonus_act_time=0, can_rest_br=0,
                 str_bonus=0, dex_bonus=0, sta_bonus=0,
                 per_bonus=0, int_bonus=0,
                 effects=[], effects_prob=[],
                 action_map=ACT_USE_IDLE | ACT_USE_TARGET)
        return SI_COMMAND[root], p

    if root == COLD_ARM:
        p = _common(type_id, name, root, 70 * t, 1200)
        p.update(h_damage_min=10 + 3 * t, h_damage_max=22 + 6 * t,
                 st_damage_min=4, st_damage_max=9,
                 max_range=1, can_aimed=1, strike_cost=8, strike_mod=1,
                 strike_time=600, max_break_abs=80 + 15 * t,
                 action_map=ACT_FIRE)
        return SI_COMMAND[root], p

    # Trash and trophies: stackable, no behaviour of their own.
    p = _common(type_id, name, root, 10 * t, 150)
    p.update(max_count=50, range_mod=1, st_mod=1, dam_mod=1)
    return SI_COMMAND[TRASH if root != TROPHY else TROPHY], p


# --- the wiki laid over the designed frame ----------------------------------

# Requirements and bonuses the client reads on any item beyond the keys the
# designed frames carry (Item.parseNeedBonus, Item.as:110-221): a bit mask
# and the dense list of values for the bits set. The wiki tables keep them in
# exactly that form.
NEED_BONUS_KEYS = (
    "need_attribs_m", "need_attribs", "need_skills_m", "need_skills",
    "need_specs_m", "need_specs", "bonus_attribs_m", "bonus_attribs",
    "bonus_skills_m", "bonus_skills", "bonus_specs_m", "bonus_specs",
    "bonus_hp", "bonus_st", "bonus_od", "bonus_cp", "bonus_ce")

# String ids of item descriptions (recon/analysis/quests.md 4.4). The name
# of a type is STRING_ID_OFFSET + type, its description DESC_ID_OFFSET + type;
# quests sit between the two ranges at 2 000 000 and the shared empty string
# at 5 000 000, so none of the four overlap.
DESC_ID_OFFSET = 3_000_000


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _overlay(type_id, p, rec):
    """Lay a wiki table over a designed frame, in place.

    Only keys the frame already carries are taken, plus the need/bonus
    family, so nothing the wiki adds on its own (sellable, auction, the
    linker's notes) reaches the wire and the frame's shape never depends on
    what one article happened to tabulate. Then the invariants the client's
    arithmetic rests on are restored where a table left a hole: a zero
    divisor keeps the designed value, a firearm keeps at least one fire
    mode, a heal item at least one use, and a pack of rounds a stack it
    fits in.
    """
    root = root_of(type_id)
    designed = dict(p)
    for key, value in rec.items():
        if key not in designed and key not in NEED_BONUS_KEYS:
            continue
        if isinstance(designed.get(key), list) or (
                key in NEED_BONUS_KEYS and key.endswith(("_attribs", "_skills", "_specs"))):
            if not isinstance(value, list) or not all(_number(x) for x in value):
                continue
            if key in designed and len(value) != len(designed[key]):
                continue
            p[key] = list(value)
        elif _number(value):
            p[key] = value
    # Grams, like the client's; one table carries a fraction.
    p["weight"] = int(round(p["weight"]))

    if root == FIRE_ARM:
        if not any(p["fire_mods"]):
            p["fire_mods"] = list(designed["fire_mods"])
        for key in ("max_range", "target_size"):
            p[key] = [v if v > 0 else d for v, d in zip(p[key], designed[key])]
        if p["clip_size"] < 1:
            p["clip_size"] = designed["clip_size"]
        if p["weapon_type"] not in range(len(CLASS_SHAPE)):
            p["weapon_type"] = designed["weapon_type"]
        p["comp_array"] = _calibre(rec) or AMMO_FOR.get(p["weapon_type"], AMMO_9MM)
    elif root == AMMO:
        if p["max_count"] < 1:
            p["max_count"] = designed["max_count"]
        if p["sell_num"] > p["max_count"]:
            p["sell_num"] = p["max_count"]
        # The wiki's price is the tooltip's, per round; on the wire cost is
        # the price of a pack of sell_num rounds, which the client divides.
        for key in ("cost", "g_cost"):
            if _number(rec.get(key)):
                p[key] = rec[key] * p["sell_num"]
    elif root == HEAL:
        if p["use_count"] < 1:
            p["use_count"] = designed["use_count"]
    elif root == WEAR:
        if p["slot_type"] not in range(6):
            p["slot_type"] = designed["slot_type"]
    elif root == COLD_ARM:
        if p["max_range"] <= 0:
            p["max_range"] = designed["max_range"]
    if "max_count" in p and p["max_count"] < 1:
        p["max_count"] = designed["max_count"]
    if clean_text(rec.get("desc_ru", "")):
        p["desc"] = DESC_ID_OFFSET + type_id


def _calibre(rec):
    """The rounds a wiki firearm table names, as ammunition type ids of
    every variant, or [] when the table names none the linker knows."""
    names = rec.get("ammo_calibre") or []
    if isinstance(names, str):
        names = [names]
    out = []
    for name in names:
        for part in str(name).split(","):
            for i in resolve_title(part.strip(), all_variants=True):
                if root_of(i) == AMMO and i not in out:
                    out.append(i)
    return out


# Wiki markup that survives in a table cell or a quest text: [[page|shown]]
# and [[page]] links, ''italic'' and '''bold''' quotes, the odd <br />.
_MARKUP = (
    (re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]"), r"\1"),
    (re.compile(r"'{2,}"), ""),
    (re.compile(r"<br\s*/?>", re.I), "<br>"),
)


def clean_text(s):
    """A wiki text as the client renders it: markup stripped, line breaks
    as the <br> the client's HTML fields understand."""
    for rx, rep in _MARKUP:
        s = rx.sub(rep, s)
    # One break per run of newlines and <br>s: a tooltip has no paragraphs.
    s = re.sub(r"(?:\s*(?:<br>|\r?\n))+\s*", "<br>", s.strip())
    return s.strip()


def wiki_names():
    """type_id -> the wiki's Russian name, for every type a page is tied to.

    A type with a table takes that record's name: rounds get their column
    (9мм НАТО КС / СТ / ОТ, the page's own captions) and gold or premium
    copies their (G) / (P) mark, so the three rows of one calibre on a stall
    read apart. A type with a page but no table takes the page title, unless
    the linker tied it to several pages.
    """
    out = {}
    for t, titles in links()[2].items():
        if len(titles) == 1 and t in catalogue():
            out[t] = titles[0]
    for t, rec in wiki().items():
        meta = rec.get("_wiki", {})
        name = rec.get("name_ru") or meta.get("page")
        if not name or t not in catalogue():
            continue
        if root_of(t) == AMMO:
            label = re.sub(r"\[\d+\]$", "", meta.get("column", ""))
            if label not in ("", "-", "bullets"):
                name = "%s %s" % (name, label)
        else:
            variant = (meta.get("variant") or "A")[:1]
            if variant in ("G", "P") and not name.endswith("(%s)" % variant):
                name = "%s (%s)" % (name, variant)
        out[t] = name
    return out


def wiki_descs():
    """type_id -> the wiki's description, for the types that have one."""
    out = {}
    for t, rec in wiki().items():
        text = clean_text(rec.get("desc_ru", ""))
        if text and t in catalogue():
            out[t] = text
    return out


def preload():
    """Read every table now, before the first connection is accepted.

    The wiki files run to megabytes and were parsed on first use -- inside
    whatever handler happened to touch an item first, which held the event
    loop for a couple of seconds and delayed every reply to every client.
    A server may read its content at start; a request may not wait for it.
    """
    catalogue()
    wiki()
    links()
    stock_table()
