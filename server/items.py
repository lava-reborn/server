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
copied off the game's own tooltips: data/items_wiki.json holds them for 1 255
types in the ss_si_* vocabulary, data/wiki_links.json ties wiki pages to type
ids, and data/trader_stock_wiki.json lists what 87 traders sold. Those are
laid over the designed frames here, field by field, never changing the shape
of a frame: a wiki table decides what a rifle does, the designed frame decides
which keys travel. The same files give the Russian names and descriptions
names.py serves. A few medicines no article describes take numbers of our
own, from data/heal_manual.json, laid over the same way, and so do the
pieces of the clothing sets of data/sets.json (sets.py). A cold arm whose
article leaves a hole a stall cannot sell around -- no price, a strike for
no action points -- has it filled from data/coldarm_manual.json. And the
things the Nubian mine's marauders drop, whose articles the extractor could
not read or the linker could not tie, take their numbers from the "items" of
data/loot_manual.json, the file whose rows make them drop -- and so do
the gold ingots of 1, 5 and 10 ounces.
"""
import json
import logging
import re
import os

import craft
import npcs
import orig_texts
import production
import progression
import quests
import sets
import shop_bands
import world

log = logging.getLogger("lava")

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WIKI_ITEMS_PATH = os.path.join(DATA, "items_wiki.json")
WIKI_LINKS_PATH = os.path.join(DATA, "wiki_links.json")
WIKI_STOCK_PATH = os.path.join(DATA, "trader_stock_wiki.json")
HEAL_MANUAL_PATH = os.path.join(DATA, "heal_manual.json")
COLDARM_MANUAL_PATH = os.path.join(DATA, "coldarm_manual.json")
LOOT_MANUAL_PATH = os.path.join(DATA, "loot_manual.json")

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
# The other calibres the recovered pistols chamber. SP-10 has no tracer round.
AMMO_45 = [6093, 6105, 6117]         # Ammo_45_*
AMMO_762x25 = [6094, 6106, 6118]     # Ammo_762x25_*
AMMO_SP10 = [6103, 6115]             # Ammo_SP_10_12_KS / _ST
AMMO_SP_5_6 = [6100, 6112]           # ПАБ-9 КС, СП-6 СТ: АС Вал's (Ammo_SP_5_6_KS / _ST)

# The pistols the wiki named, by the line each one sits on (the pairing is
# data/firearm_lines_manual.json), cheapest first. Ordinary copies only: the
# _pm and _gold ones were never sold for afro. The five nameless pistols_1..5
# the stall used to hold stay where they are still needed -- the starter kit
# and a bandit's weapon (inventory.py, mobs.py) -- but a stall that can name
# its wares should. On the wire, in Вади-Хальфа, the black market's gun
# stalls sell their city's band instead (shop_bands.py): this table is the
# stalls' own list, where their rounds come from.
WIKI_PISTOLS = [
    25666,   # Самопальный револьвер, Стрельба 2, 100
    25566,   # Наган 1895,            Стрельба 1, 400
    25576,   # С. и В. специальный,   Стрельба 1, 400
    25586,   # Браунинг,              Стрельба 2, 800
    25596,   # Беретта 92,            Стрельба 2, 800
    25606,   # CZ 75,                 Стрельба 3, 1600
    25616,   # Colt 1911,             Стрельба 3, 1600
    25626,   # Walther P99,           Стрельба 4, 2800
    25636,   # Glock 17,              Стрельба 4, 2800
    25646,   # СПС,                   Стрельба 5, 4300
    25656,   # Desert Eagle,          Стрельба 6, 6400
]

# Designed stock, by the trader's own type id. The pistol stall holds the
# wiki's pistols, named; the other three gun stalls of the black market only
# the rounds their guns take, and their guns are the ones the wiki says they
# sold (data/trader_stock_wiki.json: Jackhammer, SPAS-12, Li-Enfield, MP-40
# and the rest, tied to their lines by data/firearm_lines_manual.json), which
# stock_table() puts first -- no longer the nameless placeholder series of
# objects.xml (shotgun_1..5, rifle_1..5, assrifle_1..5, the last an assault
# rifle in the stall of sub-machine guns). The weapons stay first: the client
# refers to a purchase by its index in this list, and a test relies on the
# head of the pistol stall being a firearm. stock_for() is what goes on the
# wire: data/npcs.json where the owner decided, else this table extended
# with what the wiki says each of these traders sold, and the wiki alone
# for the rest. Ваккас (1204) and Хамис (1205) are data/npcs.json's.
STOCK = {
    1200: WIKI_PISTOLS + AMMO_9MM + AMMO_45 + AMMO_762x25 + AMMO_SP10,  # wh_Pistols
    1202: AMMO_762x51,                                    # wh_Rifles
    1201: AMMO_12MM,                                      # wh_Shotguns
    # The sub-machine guns chamber 9 mm (their articles' «Тип патронов»),
    # beside the wiki's own 0.45 and 7.62x25 lines of this stall.
    1203: AMMO_9MM,                                       # wh_SubMachineGuns
    # Лавки по уровню городов (shop_bands.py) put guns on stalls whose own
    # rounds do not fit them: Абри and Донгола sell the 9 mm sub-machine guns
    # of 8-14 (Кустарный ПП to Бизон ПП-19) and the 12-bore shotguns of 8-12,
    # and no trader of either city sold those rounds. Each class's rounds go
    # to the stall of its class, ahead of the wiki's own (.45, SS190 and
    # 7.62x25 at Абри's, SS190 at Донгола's); Донгола has no shotgun stall,
    # so its shells go where its shotguns are, the oasis's general one; and
    # АС Вал (16, Донгола's and Абу-Хамед's) gets Донгола's assault rifle
    # stall the two rounds Абу-Хамед's sells for it (1217, the wiki's).
    1163: AMMO_9MM,                                       # Abri_SubMachineGuns_trd
    1162: AMMO_12MM,                                      # Abri_Shotguns_trd
    1211: AMMO_9MM,                                       # dn_SubMachineGuns
    1229: AMMO_12MM,                                      # dn_oasis_w_trd
    1209: AMMO_SP_5_6,                                    # dn_AssaultRifles
}

# Which weapon class a series belongs to, and the ammunition it accepts.
WEAPON_CLASS = {
    4380: PISTOL, 4381: PISTOL, 4382: PISTOL, 4383: PISTOL, 4384: PISTOL,
    4385: RIFLE, 4386: RIFLE, 4387: RIFLE, 4388: RIFLE, 4389: RIFLE,
    4392: SHOTGUN, 4393: SHOTGUN, 4394: SHOTGUN, 4395: SHOTGUN, 4396: SHOTGUN,
    4397: ASSAULT, 4398: ASSAULT, 4399: ASSAULT, 4400: ASSAULT, 4401: ASSAULT,
}

# Rough per-class shape: damage at tier one, range, action points per shot,
# magazine, how long a burst runs in each of the three fire modes, and the
# spread the tooltip shows («разброс на 100 метров», the client's 100 *
# target_size / max_range) -- the median of the class's wiki guns in their
# first mode (pistols 8.3 over 333 guns, shotguns 7.1, assault rifles 11.4,
# rifles 10, machine guns 2.9, SMGs 4.6), because the server now scatters
# bullets by it (combat.cone_of) and a designed gun has to stand beside a
# wiki one, not five times wider.
CLASS_SHAPE = {
    PISTOL:     dict(dmg=(12, 26), rng=14, ap=10, clip=8,  modes=(1, 0, 0), acc=8),
    SHOTGUN:    dict(dmg=(24, 52), rng=9,  ap=18, clip=6,  modes=(1, 2, 0), acc=7),
    ASSAULT:    dict(dmg=(18, 40), rng=22, ap=15, clip=30, modes=(1, 3, 6), acc=11),
    RIFLE:      dict(dmg=(30, 66), rng=30, ap=20, clip=10, modes=(1, 0, 0), acc=10),
    MACHINEGUN: dict(dmg=(20, 44), rng=20, ap=22, clip=50, modes=(1, 5, 9), acc=3),
    SMG:        dict(dmg=(14, 30), rng=12, ap=12, clip=25, modes=(1, 3, 5), acc=5),
}
# A burst scatters wider than a single shot: the wiki's second and third
# modes run 1.5 and 2 times the first's spread (a pistol's 8.3 -> 14, an
# SMG's 4.6 -> 6.8 -> 6.8).
MODE_SPREAD = (1.0, 1.5, 2.0)

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

# Берт Гаммер's training guns, one of each class his lessons teach (the
# Tir's lessons lend them, quests.json 352-357): noob_Pistol, _Shotgun, _SMG,
# _AssaultGun, _MachineGun, _Rifle. They chamber the Tir's own rounds,
# noob_ammo, and nothing else, as the original says of both: «Предназначен
# для тренировочной стрельбы особыми пулями кал. 5,6 мм» (texts.xml 1815 to
# 1823, 2013) and «Могут быть использованы только в специальном,
# тренировочном оружии» (1095). The class and the rounds are RECOVERED; the
# numbers are the class's designed shape (CLASS_SHAPE), as for any gun the
# wiki has no table for.
TRAINING_GUNS = {3728: PISTOL, 3729: SHOTGUN, 3730: SMG, 3731: ASSAULT,
                 3732: MACHINEGUN, 3733: RIFLE}
TRAINING_ROUNDS = 3727

# Rounds per trade pack, and the most one stack holds. The client divides the
# pack price by the first to show a per-round price, and caps the "how many"
# dialogue at the second; a purchase asks for rounds, never packs.
#
# The owner's rule (2026-09-25): up to 5000 rounds in one purchase. The
# window's ceiling IS the stack: a stall's rounds are drawn as a stack of
# max_count (TradeItem.initParams) and "Сколько штук купить?" runs from 1
# to that size (TradeInterface.createExchangePan), and the same max_count is
# what a stack in the bag holds -- the client joins two up to it
# (StuffManager.joinHeap) and inventory.ss_heap_c refuses past it. So a
# purchase of 5000 is one stack of 5000, and no other number could let the
# window offer it; it was 200. Rounds only: the client asks "how many" for
# nothing else (Trade.buy sends 1), and junk keeps its stack of 50.
AMMO_PACK = 20
AMMO_STACK = 5000

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


def slot_of(name):
    """The slot a piece of clothing goes in, read off its internal name.

    A numbered series ("helm_12") says it in its stem. Every other name says
    it in its first word: the 15 169 pieces of the LVL system are
    "<helm|shirt|armor|pants|boots>_<series>_M_LVL_<level>_...", the belts
    "belt_...". Reading the whole name instead found no slot in any of them,
    and the default put every helmet, boot and belt into the shirt's place --
    where inventory.fits then kept them, so no set could ever be worn whole.
    """
    m = _SERIES.match(name)
    prefix = m.group(1) if m else name.split("_", 1)[0].lower()
    return SLOT_BY_PREFIX.get(prefix, SLOT_CAMO)


def stock_for(trader_type, loc_id=None):
    """What this trader sells, as the list of type ids the client indexes.

    The owner's own list wins where there is one (data/npcs.json, written by
    tools/npc_editor.py): the wiki records what a dead server sold, which is
    a starting point and not a decision. An empty list there is a decision as
    much as a full one, so only a missing entry falls through -- to the
    wiki's list and what the weapon craft adds to it (craft.stock_extra).

    At a place of a city (loc_id, the room the trader stands in), a weapon
    or set seller's stall is its city's band (shop_bands.py, the owner's
    «по уровню городов» of 2026-10-10): what goes on the wire, and what a
    purchase indexes, is asked with the place. Without one it is the
    trader's own list, as the editor and the start-up checks read it.

    Either way an ordinary base belt on the list brings its gold copy
    right after it (GOLD_POUCHES, the owner's of 2026-10-11).
    """
    chosen = npcs.stock(trader_type)
    if chosen is None:
        chosen = stock_table().get(trader_type, [])
        chosen = chosen + [t for t in craft.stock_extra(trader_type) if t not in chosen]
    chosen = shop_bands.apply(trader_type, loc_id, with_gold_pouches(chosen))
    return [t for t in chosen if not premium(t)]


# Голдовые подсумки, the owner's «добавь еще голдовые подсумки» (2026-10-11,
# after «чтобы была и голдовая версия, и обычная» of the city bands): the
# base belt of each weapon class -> its gold copy, the seven lines of the
# original's run of belts (texts.xml 47822-47856) and of their articles
# (data/wiki_links.py MANUAL: the A column the ordinary one, the G column the
# gold one). Every stall that sells the ordinary belt sells the gold one
# right after it (with_gold_pouches), whatever list it came from -- the
# owner's (data/npcs.json), the wiki's or the designed one. The gold copy is
# priced in gold alone, its article's G price, and is not exchanged or sold
# back: a gold thing (combat.gold_item). The МОД. А1./А2. pouches, Jons',
# the event's and the U_ series are other lines and stay where they are.
GOLD_POUCHES = {
    3582: 3604,    # belt_pistols          Подсумки пистолетные    3 000 afro / 0.5 G
    3581: 3603,    # belt_shotguns         Подсумки охотника       8 000 / 1.6 G
    3578: 3600,    # belt_rifles           Подсумки снайпера      20 000 / 4 G
    3579: 3601,    # belt_sub_machineguns  Подсумки спецназовца   40 000 / 8 G
    5613: 5614,    # belt_knife            Подсумки рукопашника   40 000 / 8 G
    3577: 3599,    # belt_assault_rifles   Подсумки автоматчика   50 000 / 10 G
    3580: 3602,    # belt_machineguns      Подсумки пулемётчика  100 000 / 20 G
}


def with_gold_pouches(ids):
    """The list with each ordinary base belt's gold copy right after it.

    A gold copy already on the list moves there; one whose ordinary twin is
    not on the list stays where it is. Nothing else moves."""
    ids = list(ids)
    present = set(ids)
    moved = {GOLD_POUCHES[t] for t in present if t in GOLD_POUCHES}
    out, placed = [], set()
    for t in ids:
        if t in moved:
            continue
        out.append(t)
        gold = GOLD_POUCHES.get(t)
        if gold is not None and gold not in placed:
            out.append(gold)
            placed.add(gold)
    return out


def premium(type_id):
    """Whether the type is a premium item, the "(P)" of its name.

    The client will not put one in a hand or on the body without a residence
    permit (EquipInterface: "У вас должен быть вид на жительство"), and
    nothing on this server grants one. So a premium item is money spent on
    something that can only sit in the bag, and the owner took them out of
    the game: no stall sells one and no mob drops one. Filtered here and in
    combat.drop_loot rather than in each list, so a wiki fallback or a
    hand-written list cannot bring one back by accident.

    The frame's premium flag alone is not enough: it is set only where the
    wiki or a data file said so, and most premium types have neither. The
    client's own internal name says it for all of them -- _P_modNN on the
    clothing series, _pm on the guns, a trailing _P on the medicines, 6 848
    types -- and the original's "(P)" catches the rest.
    """
    global _ORIG_NAMES
    cached = _PREMIUM.get(type_id)
    if cached is None:
        if _ORIG_NAMES is None:
            _ORIG_NAMES = orig_texts.item_names()
        entry = catalogue().get(type_id)
        p = params_of(type_id)
        cached = _PREMIUM[type_id] = bool(
            (p and p.get("premium"))
            or (entry and _PREMIUM_NAME.search(entry[1]))
            or "(P)" in (_ORIG_NAMES.get(type_id) or ""))
    return cached


_PREMIUM = {}
_ORIG_NAMES = None
_PREMIUM_NAME = re.compile(r"(?:^|_)(?:P|pm)(?:_|$)")


def no_combat(type_id):
    """Whether a medicine is for peace only: the Med_Pacific_ series, 24
    types, each described "<b>Нельзя использовать в бою.</b>" in the
    original's own words -- and exactly those; the Med_Battle_ ones say
    nothing of the kind. Their heal_cost is 0, as a thing never spent in a
    fight needs none, so nothing but this refusal keeps them out of one: the
    client's own quick heal picks the strongest medicine in the bag with no
    look at the war state (PersEquip.useHealItem), 1035-1380 health for
    0 AP among them."""
    entry = catalogue().get(type_id)
    return bool(entry and entry[0] == HEAL and entry[1].startswith("Med_Pacific_"))


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
_HEAL_MANUAL = None
_COLDARM_MANUAL = None
_LOOT_MANUAL = None
_ORIG_DESCRIBED = None


def wiki():
    """type_id -> the wiki's ss_si_* fields for it (data/items_wiki.json)."""
    global _WIKI
    if _WIKI is None:
        _WIKI = {int(k): v for k, v in _load_wiki(WIKI_ITEMS_PATH, "items").items()}
    return _WIKI


def heal_manual():
    """type_id -> designed ss_si_heal fields (data/heal_manual.json).

    For the medicine a trader sells that no wiki article describes: the
    (P) kits between "Мини" and "Стандарт" and the 20-dose injector packs.
    The numbers are ours, and the file says which and how they were chosen.
    They travel the way a wiki record does, through _overlay, so the frame
    keeps its shape; a wiki table for the same type, should one turn up,
    wins. Loaded like the wiki tables: unreadable means no start.
    """
    global _HEAL_MANUAL
    if _HEAL_MANUAL is None:
        _HEAL_MANUAL = {int(k): v for k, v in _load_wiki(HEAL_MANUAL_PATH, "items").items()}
    return _HEAL_MANUAL


def coldarm_manual():
    """type_id -> designed ss_si_coldarm fields (data/coldarm_manual.json).

    Unlike the medicines of heal_manual, these types have a wiki table; it
    just leaves out what a stall needs -- the level-0 Булыжник has no price
    and a strike for 0 action points, which is a free swing without end. So
    the file fills holes (_holes) instead of standing in for a table, and
    says in each record which numbers are ours. Loaded like the wiki tables.
    """
    global _COLDARM_MANUAL
    if _COLDARM_MANUAL is None:
        _COLDARM_MANUAL = {int(k): v for k, v in
                           _load_wiki(COLDARM_MANUAL_PATH, "items").items()}
    return _COLDARM_MANUAL


def loot_manual():
    """type_id -> the numbers of a hand-dropped thing (the "items" of
    data/loot_manual.json): the Nubian mine's gold sand and emeralds, and
    the gold ingots of 1, 5 and 10 ounces.

    Recovered, unlike heal_manual's: each record is its wiki article's own
    figures, which data/items_wiki.json lacks because the article writes
    them as sections the extractor does not read (Золотой песок) or carries
    an icon named after no type (Небольшие изумруды, the ingots) -- but
    for the ingots' afro price, which the file designs out of the
    article's gold one and says why (GOLD_INGOTS lays both). Laid over the
    frame like a heal_manual record, and like one only where the wiki has
    no table of its own. drop_on_death rides along for combat.drops_on_death and,
    being no key of any frame, stays off the wire. Loaded like the wiki
    tables: unreadable means no start.
    """
    global _LOOT_MANUAL
    if _LOOT_MANUAL is None:
        _LOOT_MANUAL = {int(k): v for k, v in _load_wiki(LOOT_MANUAL_PATH, "items").items()}
    return _LOOT_MANUAL


def _holes(rec, fix):
    """The part of a hand-made record that fills what a wiki table leaves out.

    A key the table gives a positive value for stays the table's, and a
    price stays out altogether when the table names one in either currency:
    an afro price laid next to the wiki's gold one would be an item priced
    twice, which the client buys for gold and the server buys back for afro.
    """
    rec = rec or {}
    has = lambda k: _number(rec.get(k)) and rec[k] > 0
    priced = has("cost") or has("g_cost")
    return {k: v for k, v in fix.items()
            if not has(k) and not (priced and k in ("cost", "g_cost"))}


def _orig_described():
    """Type ids the original string table has a description for."""
    global _ORIG_DESCRIBED
    if _ORIG_DESCRIBED is None:
        _ORIG_DESCRIBED = frozenset(orig_texts.item_descs())
    return _ORIG_DESCRIBED


def links():
    """(page title -> type ids of its standard (A) variants,
    page title -> type ids of every variant, type_id -> page titles), from
    data/wiki_links.json with candidate links below LINK_CONFIDENCE left out."""
    global _LINKS
    if _LINKS is None:
        pages, by_type = _load_wiki(WIKI_LINKS_PATH, "pages", "by_type")
        standard, every, columns = {}, {}, {}
        for title, page in pages.items():
            a_ids, all_ids = [], []
            for link in page.get("links", []):
                if link.get("confidence", 0) < LINK_CONFIDENCE:
                    continue
                a_ids += (link.get("variants") or {}).get("A", [])
                all_ids += link.get("type_ids", [])
                # Ammunition is linked calibre-wide, one id per quality
                # column, and a stall names the column it sells.
                for col, ids in (link.get("by_column") or {}).items():
                    columns.setdefault(title, {})[col] = list(ids)
            if all_ids:
                # A page with no (A) column at all -- a gold-only item, say --
                # stands for whatever it lists.
                standard[title] = _unique(a_ids or all_ids)
                every[title] = _unique(all_ids)
        _LINKS = (standard, every, {int(k): v for k, v in by_type.items()},
                  columns)
    return _LINKS


# A stall lists a round by its page and the quality column: "0.45 калибр СТ".
# "(OLD)" marks the pre-patch copy of a round the wiki kept a single page for,
# and names the same column.
_OLD = re.compile(r"\s*\(OLD\)")


def resolve_stock_title(title):
    """Type ids for one line of a trader's list, the column suffix included.

    resolve_title answers for a page; this also answers for "<page> <column>",
    which is how the wiki's stock lists name a single quality of a round.
    """
    ids = resolve_title(title)
    if ids:
        return ids
    columns = links()[3]
    words = _OLD.sub("", title).split()
    for k in (1, 2):
        if len(words) <= k:
            break
        page, col = " ".join(words[:-k]), " ".join(words[-k:])
        got = columns.get(page, {}).get(col)
        if got:
            return list(got)
    return []


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

    The designed table (STOCK) is the base for the stalls it names and the
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
                ids = [i for i in resolve_stock_title(title) if i in catalogue()]
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


# The gold ingots of 1, 5 and 10 ounces (New_Gold_Ingot_1/_5/_10, texts.xml
# 7636-7641), by what each is worth in hundredths of an ounce: the articles'
# «Базовая цена 1 G / 5 G / 10 G». An ingot carries both prices. Its g_cost
# is that worth, for which Мортимер sells it (data/npcs.json 1188, the
# owner's of 2026-10-09): the shipped client buys anything with a g_cost for
# gold (Trade.buy sends UPD_BUY_GOLD) and the stall draws the gold price
# (ItemContainer, showPriseInGold). Its cost is the same worth in afro at
# the one rate (progression.GOLD_TO_AFRO_RATE), which keeps it loot: a
# corpse's bag holds nothing without an afro price (mobs.droppable), and it
# falls off a dead player like any loot (combat.gold_item answers no for
# every ingot). A stall pays SMOD of the afro price, less than c_ga gives
# for the same ounces and less than Мортимер's cashing (0.95, 4.95, 9.95
# ounces) or Джеррах's ounce for each of the valley boss's ingots; and no
# stall sells one for afro (Inventory.buy), which would turn afro into gold.
GOLD_INGOTS = {7620: 100, 4796: 500, 4797: 1000}

# Things a table prices in both currencies that are sold for gold alone:
# their afro price is dropped from the frame. The gold lottery's ticket
# (1333; its article: 500 afro or 0.5 G) buys prizes priced in gold -- five
# expansive rounds (quests.json 309) -- and for 500 afro it would turn afro
# into five times as much gold at the one rate (fifty before the rounds fell
# to a hundredth, GOLD_AMMO_ROUND). DESIGNED (2026-09-28); take a type out to
# sell it for both again.
#
# So is the gold line's own blueprint, «Урон и размер обоймы» of the (G)
# guns (bpg_damage_25_gold_lvl4..20, objects.xml 37664-37680; the upgrade
# rows of data/questgen_weaponcraft.json line "G" ask 37665-37668): its
# article prices it in both, 6 000 afro or 1.50 G at level 5, and afro
# bought a gold gun's upgrade. The owner's gold line is paid in gold
# (2026-09-28). Gold alone, it is a gold thing (combat.gold_item): it never
# falls off a body, and a stall does not buy it (inventory.SELL_GOLD_ONLY).
# The blueprints both lines share (bpg_damage_lvl2 ...) and the afro line's
# own (bpg_damage_25_afro_*) keep both prices.
GOLD_LINE_BLUEPRINTS = frozenset(range(37664, 37681))
GOLD_PRICE_ONLY = frozenset({1333}) | GOLD_LINE_BLUEPRINTS

# The price of a gold round, in hundredths of an ounce a ROUND: the owner's
# «цену патронам снизь до 0.01 голды (которые голдовые)» (2026-09-28). A
# round is gold when it is priced in gold alone and is not premium
# (gold_round): the (G) ЭК and ББ of every calibre, СБ of six, the 9мм ШК
# and the (Q) ОТ the prison's coupons pay out, 43 types. The premium КС
# (_KS_P) keep their price, out of the game with every premium thing
# (premium), and so do the few priced in both, which no stall stocks but
# the 9мм даренные, already a hundredth a round. It replaces the wiki's
# columns, 10 hundredths a round (a pack of 20 at 2 G) for ЭК, ББ, ОТ and
# ШК and 20 (4 G a pack) for СБ:
# a pack is now 20 hundredths, 0.20 G, and 5000 rounds 50 G. A hundredth is
# the least a round can cost at all -- Ammo.initialize rounds the pack's
# g_cost over sell_num to whole hundredths -- and it is nearer the original
# than the columns were: its own gift lists offer «Купон на 500 патронов
# [G]» as the alternative to «Слиток 1 унция золота» (texts.xml 26121). On
# the wire g_cost is the pack's price (_overlay), so a pack of sell_num
# rounds is GOLD_AMMO_ROUND * sell_num; Ammo.initialize divides it back to
# 1 a round, the tooltip's «Базовая цена: 0.01 G», and the stall's
# «Сколько штук купить?» asks n hundredths for n rounds (inventory.buy_price).
GOLD_AMMO_ROUND = 1


def gold_round(p):
    """Whether a frame of rounds is gold ammunition (GOLD_AMMO_ROUND)."""
    return p.get("g_cost", 0) > 0 and not p.get("cost") and not p.get("premium")


# The afro price of a thing whose wiki record is another article's. The
# Вади-Хальфа lottery's own ticket, LoteryKey 1307 («Лотерейный билет [8]»,
# texts.xml 6918; what the lottery man 662 sells and «Лотерея Вади-Хальфы
# (0-9)» takes), carries the record of «Билет в Вади Хальфу», a train
# ticket's article that borrowed LoteryKey.png (data/wiki_links.py links
# by icon), and with it that ticket's 400 afro; its own article,
# «Лотерейный билет (8)» -- seller «Лотерейщик», quest «Лотерея
# Вади-Хальфы (0-9)» -- says 500. RECOVERED (2026-09-28).
OWN_ARTICLE_PRICE = {1307: 500}

# The miner's clothes «Шахтерская одежда» (5181) sells: Вади-Хальфа's
# helm_..boots_minecraft_U_LVL_WH_A_mod00 34480-34484 and their gold copies
# 34490-34494, named and described by the original (texts.xml 22856-22875,
# data/build_orig_items.py rule 7h). Neither the wiki nor the original has a
# number for them, so each piece takes those of the same slot of the owner's
# Колонист[2] (data/sets.json 11167 for A, 11169 for G): armour, wear,
# weight, price -- afro for A, gold for G --, what it asks and what it adds;
# and nothing of the set itself: a miner's piece is in none (set_type 0) and
# counts towards no set bonus. DESIGNED (2026-09-28): work clothes a rung
# above the refugee's rags, at a price the ladder already asks, following
# the owner's numbers of that rung if he moves them.
MINER_WEAR = {first + k: sets.SETS[like]["members"][slot]
              for first, like in ((34480, 11167), (34490, 11169))
              for k, slot in enumerate(sets.SLOTS)}

# The developers left themselves a weapon: objects.xml carries type 1534 under
# the name admin_gun, in no trader's stock and in no location's spawns. It is
# given the numbers that name implies, so a tester can settle a fight without
# arguing with the balance. Ours, and openly so; nothing sells it.
ADMIN_GUN = 1534

ADMIN_OVERRIDES = {
    ADMIN_GUN: dict(
        # One action point a shot, the whole clip in a burst if wanted.
        fire_costs=[1, 1, 1],
        fire_times=[200, 200, 200],
        fire_mods=[1, 3, 9],
        h_damage_min=[999, 999, 999],
        h_damage_max=[999, 999, 999],
        st_damage_min=[99, 99, 99],
        st_damage_max=[99, 99, 99],
        # Reaches across any location and never misses for spread: a
        # scatter of 0.01 over 64 hexes stays inside the target at any
        # distance a location has (combat.cone_of); the client divides by
        # target_size, so it may be small but never zero.
        max_range=[64, 64, 64],
        opt_range=[1, 1, 1],
        end_opt_range=[64, 64, 64],
        target_size=[0.01, 0.01, 0.01],
        piercing=[99, 99, 99],
        clip_size=99,
        reload_time=200,
        reload_cost=1,
        max_break_abs=9999,
        weight=100,
        cost=0,
        # Takes the rounds a starting pistol takes, so /give 6092 feeds it.
        comp_array=[AMMO_9MM[0], AMMO_9MM[1], AMMO_9MM[2]],
    ),
}


def static_info(type_id):
    """Everything the client needs to describe one item type.

    Returns (command, params) or None when the type is unknown. The frame is
    the designed one, with the wiki's numbers laid over it where the wiki
    has a table for this type (see _overlay), or the hand-made numbers of
    data/heal_manual.json or data/loot_manual.json where it has none;
    data/coldarm_manual.json then
    fills what a cold arm's table leaves out (_holes). A piece of a set
    takes the numbers of data/sets.json last: the owner's file for the whole
    ladder of a set, which a wiki table of the old system has no say in.
    """
    info = designed_info(type_id)
    if info:
        rec = wiki().get(type_id)
        if rec:
            _overlay(type_id, info[1], rec)
        elif type_id in heal_manual():
            _overlay(type_id, info[1], heal_manual()[type_id])
            # A designed record has no wiki text to show; the original's
            # description, where the game had one, is already under this
            # id in names.ALL (names.ORIG_ITEM_DESCS).
            if type_id in _orig_described():
                info[1]["desc"] = DESC_ID_OFFSET + type_id
        elif type_id in loot_manual():
            _overlay(type_id, info[1], loot_manual()[type_id])
            # The same: the original's description, where it has one, is
            # under this id in names.ALL (names.ORIG_ITEM_DESCS).
            if type_id in _orig_described():
                info[1]["desc"] = DESC_ID_OFFSET + type_id
        # The weapon craft's things (craft.lay_frame): a modified gun with no
        # table of its own takes its base's and its blueprint's effect, a
        # blueprint with no price its level's.
        craft.lay_frame(type_id, info[1], rec)
        fix = coldarm_manual().get(type_id)
        if fix:
            _overlay(type_id, info[1], _holes(rec, fix))
            # Without a table there is no wiki text; the original's, as for
            # the medicines above.
            if not rec and type_id in _orig_described():
                info[1]["desc"] = DESC_ID_OFFSET + type_id
        piece = sets.item(type_id)
        if piece:
            _overlay(type_id, info[1], piece)
            # Its description is the file's own or else the original's;
            # either is under this id in names.ALL (names.SET_ITEM_DESCS,
            # names.ORIG_ITEM_DESCS).
            if sets.described(type_id) or type_id in _orig_described():
                info[1]["desc"] = DESC_ID_OFFSET + type_id
        # A miner's piece: the numbers of its rung's piece (MINER_WEAR), the
        # original's words (names.ORIG_ITEM_DESCS).
        like = MINER_WEAR.get(type_id)
        if like:
            _overlay(type_id, info[1], sets.item(like))
            if type_id in _orig_described():
                info[1]["desc"] = DESC_ID_OFFSET + type_id
        # A reworked piece of the owner's ladder (mod01-mod10: its rung's
        # numbers stepped up, its set) or a clothing cheque (its price):
        # setcraft.py's, with its words (names.SETCRAFT_STRINGS; a reworked
        # piece's description is its rung's, setcraft.desc_of).
        import setcraft                    # late: setcraft imports this module
        reworked = setcraft.record(type_id)
        if reworked:
            _overlay(type_id, info[1], reworked)
            desc = setcraft.desc_of(type_id)
            if desc:
                info[1]["desc"] = desc
        # A trophy changes hands (trophies.py): the game's own template, the
        # wiki's "Описание трофея", says «Допустимость обмена: Да» and
        # «Допустимость продажи: Нет», and the auction has a «Трофеи»
        # category. Each trophy's article lists "Допустимость обмена" twice,
        # Да and then Нет -- the second is the sale row under the wrong
        # label -- and the table took the last. Selling one to a trader is
        # refused whatever this says (Inventory.sell).
        if root_of(type_id) == TROPHY:
            info[1]["exchang"] = 1
        # A simple object is nothing but its name and its words: a dog's
        # fang, a quest's gun part, an ingot. One the wiki does not describe
        # takes the original's description where the game had one
        # (names.ORIG_ITEM_DESCS, data/build_orig_items.py rules 7d and 7e):
        # without this the table carried the text and no frame pointed at
        # it, so the tooltip stayed empty -- the valley's animal parts and
        # quest things, the 1- and 10-ounce ingots. Every other root keeps
        # the rule above (a wiki or hand-made record first), UNDONE.
        if root_of(type_id) == TRASH and not info[1].get("desc") \
                and type_id in _orig_described():
            info[1]["desc"] = DESC_ID_OFFSET + type_id
        # The ore and what the plant makes of it: price, weight, stack
        # (production.item_numbers).
        made = production.item_numbers(type_id)
        if made:
            info[1].update(made)
        if type_id in GOLD_PRICE_ONLY:
            info[1]["cost"] = 0
        if type_id in OWN_ARTICLE_PRICE:
            info[1]["cost"] = OWN_ARTICLE_PRICE[type_id]
        # A gold ingot is worth its ounces: in gold, and in afro at the one
        # rate (GOLD_INGOTS).
        ounces = GOLD_INGOTS.get(type_id)
        if ounces:
            info[1].update(cost=ounces * progression.GOLD_TO_AFRO_RATE
                           // progression.GOLD_OUNCE, g_cost=ounces)
        # A gold round costs the owner's hundredth, the pack its rounds'
        # worth (GOLD_AMMO_ROUND).
        if root_of(type_id) == AMMO and gold_round(info[1]):
            info[1]["g_cost"] = GOLD_AMMO_ROUND * info[1]["sell_num"]
        # A thing a quest lends (quests.lent) is the quest's, not the
        # player's: the quest flag and no exchange, the two things the
        # stall, the barter, the post and the auction ask (Inventory.sell,
        # barter.tradable, mail.postable, Auction.create), and a death and
        # the ground ask quests.kept_on_death/not_on_ground. The client
        # files it with the quest things and will not post or barter it.
        # So is a thing that exists in certain places only, theirs
        # (events.kept, data/schedule.json keep_in: the prison's armbands).
        import events                   # late: it reads data/schedule.json
        if quests.lent(type_id) or events.kept(type_id):
            info[1].update(quest=1, exchang=0)
        # Last, so neither the design nor the wiki can argue with it.
        admin = ADMIN_OVERRIDES.get(type_id)
        if admin:
            info[1].update(admin)
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
        cls = WEAPON_CLASS.get(type_id, TRAINING_GUNS.get(type_id, PISTOL))
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
            # The class's spread at each mode's range (CLASS_SHAPE acc,
            # MODE_SPREAD); never zero, the client divides by it.
            target_size=[max(0.05, round(sh["acc"] * r / 100.0 * m, 2))
                         for r, m in zip([sh["rng"], max(1, sh["rng"] - 4),
                                          max(1, sh["rng"] - 8)], MODE_SPREAD)],
            piercing=[t, t, t],
            fire_costs=[sh["ap"], sh["ap"] + 4, sh["ap"] + 8],
            fire_times=[700, 800, 900],
            comp_array=([TRAINING_ROUNDS] if type_id in TRAINING_GUNS
                        else AMMO_FOR.get(cls, AMMO_9MM)))
        return SI_COMMAND[root], p

    if root == WEAR:
        p = _common(type_id, name, root, 80 * t, 900 + 200 * t)
        p.update(armor_class=t, slot_type=slot_of(name),
                 max_break_abs=60 + 15 * t, set_type=sets.set_of(type_id))
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

    # Priced in gold and not in afro: say so rather than let the designed
    # frame's guess stand. Without this a gold copy arrives with the 120 afro
    # the frame invents for a tier it could not read, and the trader buys it
    # back for them.
    if _number(rec.get("g_cost")) and rec["g_cost"] > 0 and not _number(rec.get("cost")):
        p["cost"] = 0

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
    for t, name in out.items():
        out[t] = _WIKI_DISAMBIGUATION.sub("", name)
    # The weapon craft's names for what the original names only in words
    # (craft.item_names: the gunsmith's parts), where the wiki has none;
    # the original's own names still go over them (names.py).
    for t, name in craft.item_names().items():
        if t in catalogue():
            out.setdefault(t, name)
    return out


# A page title's disambiguation, which is not part of the name: the wiki
# keeps the junk bottle (TrashLoot_LvL_2, «Пластиковая бутылка (trash)»,
# category «Треш лут») apart from another page of the same name, and the
# page's own heading says «Пластиковая бутылка». The original's text has no
# row for it, so the title is what a player reads, and every man of level 2
# to 4 carries one (mobs.junk).
_WIKI_DISAMBIGUATION = re.compile(r"\s*\((?:trash|треш)\)\s*$", re.I)


def wiki_descs():
    """type_id -> the wiki's description, for the types that have one."""
    out = {}
    for t, rec in wiki().items():
        text = clean_text(rec.get("desc_ru", ""))
        if text and t in catalogue():
            out[t] = text
    for t, text in craft.item_descs().items():         # as wiki_names
        if t in catalogue():
            out.setdefault(t, text)
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
    heal_manual()
    coldarm_manual()
    loot_manual()
    _orig_described()
    links()
    stock_table()
    # The city bands' wares (every weapon line, knife and set piece sorted
    # out of the catalogue by level and price): over a second on a quiet
    # machine, and the first stall of a city entered after a restart held
    # the loop for it -- in CI, test_terrain_move, which starts on Хальфа's
    # black market (102), read that market's stalls after the map's frames.
    shop_bands.wares()
