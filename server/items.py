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
"""
import re
import os

import world

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

# Stock, by the trader's own type id. The numbered series in objects.xml line
# up with the stalls: five tiers each, exactly what a tier-one shop would hold,
# followed by the rounds those guns take. The weapons stay first: the client
# refers to a purchase by its index in this list, and a test relies on the
# head of the pistol stall being a firearm.
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
    return STOCK.get(trader_type, [])


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
        cost=price, g_cost=0, bg_p_cost=0,
        # A trade pack of one. The client divides the price by this, so leaving
        # it out makes the shop show an undefined price rather than no price.
        sell_num=1,
        repair_mod=1, sell_mod=1, premium=0,
        quest=0, need_pvp_rep=0,
        action_map=0)


def static_info(type_id):
    """Everything the client needs to describe one item type.

    Returns (command, params) or None when the type is unknown.
    """
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
