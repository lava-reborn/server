"""Weapon craft: a gun and a blueprint made into the gun's modification, a
knife sharpened at a whetstone, a broken gun taken apart on a gunsmith's
bench and a gun put together from its parts, a blueprint decoded.

THE ROWS ARE QUESTS

In the original every one of these was a quest of a master's --
«Хочешь улучшить свое оружие? Мне нужен соответствующий чертеж и,
собственно, само оружие» (texts.xml 51682 and some 2 000 more), «На этом
верстаке можно разобрать сломаный пистолет 2кл.» (25401), «Принеси мне
несколько деталей и я научу тебя как собирать Беретту 92(A)» (46154),
«Если найдешь зашифрованный чертеж 2-го уровня, то сразу приноси его ко
мне» (48001) -- and so they are here: repeatable services (quests.py
service) that data/build_weaponcraft.py writes into
data/questgen_weaponcraft.json out of the original's own lines, a city at
a time by its level band. Each row carries a "craft" record saying what it
is (family, and what the family needs). The quest engine hands them in as
any quest; this module adds what a row cannot say by itself:

  * the frame of a modified gun the wiki has no table for: its base gun's
    table with the blueprint's effect laid on, in the sizes the original's
    own recipe hints give (EFFECTS, lay_frame);
  * the price of a blueprint no article priced (lay_frame);
  * the names of the parts, and of the few blueprints the original names
    only in a quest's words (item_names: the companion table's "items");
  * the salvage's broken gun (ready, hand_in): «сломаный пистолет 2кл.» is
    no type but any broken gun of a class, so the row asks the bag itself,
    and the hand-in takes that gun -- the cheapest, never a gold one, a
    modification or a lent one (salvageable);
  * the weapons of the upgrader's window (s_type=5, userInfo_Upgrader
    in_types/out_types/costs; the window is upgrader.py's, shared with the
    set rungs of setcraft.py): at a master whose mobs.xml class is Upgrader
    the same recipes are offered for the very gun the player drags in
    (upgrader_lists, upgrade);
  * what the craft adds to a stall the owner wrote no list for (stock_extra:
    the companion table's "stock", items.stock_for).

ONCE PER INSTANCE

«Внимание!!! Каждый экземпляр оружия можно улучшить только один раз.»
A recipe takes the gun and gives its modification, a type of its own
(objects.xml <base>_mod_<effect>[_gold]) that no recipe and no window
asks for: the instance that was upgraded is gone, and what came back
cannot be upgraded again. The modification keeps its base gun's price
(lay_frame), so an upgrade makes no money, only a better gun -- and the
gun's wear (keep_wear, DESIGNED as setcraft.py's steps have it): a worn or
broken gun comes out a worn or broken modification, the same share of its
ceiling left, never a point more. Otherwise a blueprint cheaper than the
repair would be a repair, and a broken gun no stall buys a whole one it
does (a broken Desert Eagle and a 3 000 blueprint: 4 480 afro). A
whetstone's knife keeps its wear the same way.

Nothing here is imported at load but json/os/re: items imports this module,
and this one asks items, quests, inventory and combat late, inside the
functions.
"""
import json
import logging
import os
import re

log = logging.getLogger("lava")

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TABLE = os.path.join(DATA, "questgen_weaponcraft.json")

# The effect a modification carries, by the suffix objects.xml gives it
# (<base>_mod_<effect>[_gold|_pm]), and what it does to the frame of a gun
# the wiki has no table for. The sizes are the original's own words in the
# hints of its recipes (texts.xml 24619-24691, «Маузер C96[Q][2]: точность
# на 20%», «урон на 10%», «дальность на 2 единицы», «время прицеливания
# -15%», «ОД на перезарядку -20%», «ОД на выстрел -20%», «прочность
# увеличена в 2 раза», «ловкость +2», «восприятие +2»), which the wiki's
# tables of the modified guns it does have agree with (target_size x 0.8,
# fire_times x 0.85, max_break_abs x 2, clip_size x 2, max_range + 2 with
# the target size stretched by as much). «Увеличена обойма» names no size:
# twice the clip, as those tables have it. «Вес» the hints never size:
# DESIGNED -20 %.
EFFECTS = {
    "damage": {"damage": 1.1},
    "precision": {"precision": 0.8},
    "shotrange": {"range": 2},
    "aimtime": {"aim": 0.85},
    "reloadspeed": {"reload": 0.8},
    "shotspeed": {"shot": 0.8},
    "clipsize": {"clip": 2},
    "attrition_x2": {"wear": 2},
    "agility": {"agility": 2},
    "perception": {"perception": 2},
    "weight": {"weight": 0.8},
    "precision_shotrange": {"precision": 0.8, "range": 2},
    "damage_clipsize": {"damage": 1.1, "clip": 2},
}

_MOD = re.compile(r"^(.+?)_mod_(%s)(_gold|_pm)?$" % "|".join(
    sorted(EFFECTS, key=len, reverse=True)))
_BLUEPRINT = re.compile(r"^(bpg|bpb)_(.+?)_lvl(\d+)$")
_KNIFE_BLUEPRINT = re.compile(r"^bpg_knife_lvl(\d+)_(Damage|Actionpoint|Damage_Actionpoint)$")
_LEVEL = re.compile(r"(?:^|_)lvl_?(\d+)(?:_|$)")

# What a blueprint of a level costs, afro and gold (hundredths), where no
# article priced it: the wiki's own ladder for that level («Урон (2у)» 1 000
# afro or 0,25 G ... «Урон (12у)» 30 000 or 7,5 G; data/mods_wiki.json),
# every single-effect blueprint of a level costing the same there. A
# blueprint of two effects («Урон и размер обоймы», «Точность и дистанция
# стрельбы», bpb_*) twice that: DESIGNED, between the wiki's own 2x and
# 3.3x for the ones it prices. RECOVERED ladder, DESIGNED use of it.
LADDER = {0: (520, 13), 1: (520, 13), 2: (1000, 25), 3: (1520, 38), 4: (2000, 50),
          5: (2520, 63), 6: (3000, 75), 7: (6520, 163), 8: (10000, 250),
          9: (15000, 375), 10: (20000, 500), 11: (25000, 625), 12: (30000, 750),
          13: (35000, 875), 14: (40000, 1000), 15: (45000, 1125), 16: (50000, 1250),
          17: (55000, 1375), 18: (60000, 1500), 19: (65000, 1625), 20: (70000, 1750)}
_TWO_EFFECTS = ("damage_25", "damage_clipsize", "precision_shotrange")

_ROWS = None
_ITEMS = None
_STOCK = None
_MODS = None
_BY_NAME = None


# --- the companion table ------------------------------------------------------------
def _read():
    """The builder's table, read once: {"quests": [...], "items": {...},
    "stock": {...}}; its "items" and "stock" keyed by type."""
    global _ITEMS, _STOCK
    if _ITEMS is None:
        try:
            with open(TABLE, encoding="utf-8") as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            doc = {}
        _ITEMS = {int(k): v for k, v in (doc.get("items") or {}).items()}
        _STOCK = {int(k): [int(t) for t in v] for k, v in (doc.get("stock") or {}).items()}


def _table():
    """type -> the table's record of a thing ("items")."""
    _read()
    return _ITEMS


def stock_extra(trader_type):
    """What the craft adds to a stall with no list of the owner's (items.
    stock_for, after the wiki's): the table's "stock" -- Однопальцый's
    whetstone blueprints and the (G) knives Вади-Хальфа's whetstone
    sharpens, the quarter's trader's [Q] blueprints. A list of the owner's
    (data/npcs.json) wins over both, as it wins over the wiki's."""
    _read()
    return _STOCK.get(int(trader_type), [])


def item_names():
    """type -> the name the craft table gives a thing the original names only
    in words: the gunsmith's parts («Кустарный пистолетный ствол», texts.xml
    7924-8139), a blueprint only a recipe's start names. Laid under the
    original's own names (names.py: the wiki's layer), never over them."""
    return {t: r["name"] for t, r in _table().items() if r.get("name")}


def item_descs():
    """type -> the description the craft table gives, as item_names."""
    return {t: r["desc"] for t, r in _table().items() if r.get("desc")}


def rows():
    """quest type -> the "craft" record of every row of the table that has
    one (quests.table_rows: the real table and its companions, or the one
    LAVA_QUESTS names), read once. A record is a dict; the set craft's rows
    (data/questgen_setcraft.json) carry the same key as a word of their own
    -- "rework", "parts", "cheque" -- and are none of this module's."""
    global _ROWS
    if _ROWS is None:
        import quests                  # late: items imports this module
        _ROWS = {int(r["type"]): r["craft"] for r in quests.table_rows()
                 if isinstance(r.get("craft"), dict)}
    return _ROWS


# --- guns ----------------------------------------------------------------------------
def _by_name():
    global _BY_NAME
    if _BY_NAME is None:
        import items
        _BY_NAME = {}
        for t, (_root, name) in sorted(items.catalogue().items()):
            _BY_NAME.setdefault(name, t)
    return _BY_NAME


def mod_of(type_id):
    """(base type, effect) of a modified firearm, or None: objects.xml's
    <base>_mod_<effect> and its _gold copy, whose base is <base>_gold. A
    premium copy (_pm) has none: premium is out of the game."""
    global _MODS
    if _MODS is None:
        import items
        _MODS = {}
        for t, (root, name) in items.catalogue().items():
            m = _MOD.match(name) if root == items.FIRE_ARM else None
            if not m or m.group(3) == "_pm":
                continue
            base = _by_name().get(m.group(1) + (m.group(3) or ""))
            if base is not None:
                _MODS[t] = (base, m.group(2))
    return _MODS.get(int(type_id))


def gun_level(type_id):
    """The level a gun's internal name carries (pistols_1_lvl_2, NY2016_...
    _lvl_8), or None."""
    import items
    entry = items.catalogue().get(int(type_id))
    m = _LEVEL.search(entry[1]) if entry else None
    return int(m.group(1)) if m else None


# progression's weapon classes (PISTOL, SHOTGUN, ASSAULT, RIFLE, MACHINEGUN,
# SMG = range(6)) by the word the craft rows use.
WEAPONS = {"pistol": 0, "shotgun": 1, "assault": 2, "rifle": 3, "mg": 4, "smg": 5}


def weapon_of(type_id):
    """The class word of a firearm (WEAPONS), or None."""
    import items
    if items.root_of(type_id) != items.FIRE_ARM:
        return None
    wt = (items.params_of(type_id) or {}).get("weapon_type")
    for word, n in WEAPONS.items():
        if n == wt:
            return word
    return None


def salvageable(type_id):
    """(class word, level) of a gun a gunsmith's bench may take apart, or
    None. Only a gun with the wiki's table (its class is the table's; a gun
    without one is the designed stand-in, a pistol whatever it is), and none
    of what a player would lose by it: nothing premium, nothing gold
    (combat.gold_item, the owner's «голд-предметы»), no modification (an
    upgrade paid for), nothing a quest lends. Nor anything the owner took
    out by name (items.out_of_game, data/retired.json items): no bench takes
    a Steyr TMP or a Chang Feng apart."""
    import combat                      # late: combat imports items, items this
    import items
    import quests
    t = int(type_id)
    if t not in items.wiki() or items.out_of_game(t) or combat.gold_item(t) \
            or mod_of(t) or quests.lent(t):
        return None
    cls, level = weapon_of(t), gun_level(t)
    return (cls, level) if cls and level is not None else None


# --- frames ---------------------------------------------------------------------------
def _scaled(values, k):
    return [int(v * k + 0.5) if v else v for v in values]


def _apply(p, effect):
    """Lay one effect (EFFECTS) on a firearm's frame, in place."""
    how = EFFECTS[effect]
    if "damage" in how:
        for key in ("h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max"):
            if isinstance(p.get(key), list):
                p[key] = _scaled(p[key], how["damage"])
    if "clip" in how and p.get("clip_size"):
        p["clip_size"] = int(p["clip_size"] * how["clip"])
    if "precision" in how and isinstance(p.get("target_size"), list):
        p["target_size"] = [round(v * how["precision"], 3) for v in p["target_size"]]
    if "range" in how and isinstance(p.get("max_range"), list):
        old = list(p["max_range"])
        p["max_range"] = [v + how["range"] if v > 0 else v for v in old]
        if isinstance(p.get("target_size"), list):
            p["target_size"] = [round(ts * new / float(was), 3) if was > 0 else ts
                                for ts, was, new in zip(p["target_size"], old, p["max_range"])]
    if "aim" in how and isinstance(p.get("fire_times"), list):
        p["fire_times"] = _scaled(p["fire_times"], how["aim"])
    if "shot" in how and isinstance(p.get("fire_costs"), list):
        p["fire_costs"] = [max(1, int(v * how["shot"] + 0.5)) if v else v
                           for v in p["fire_costs"]]
    if "reload" in how and p.get("reload_cost"):
        p["reload_cost"] = max(1, int(p["reload_cost"] * how["reload"] + 0.5))
    if "wear" in how and p.get("max_break_abs"):
        p["max_break_abs"] = int(p["max_break_abs"] * how["wear"])
    if "weight" in how and p.get("weight"):
        p["weight"] = int(p["weight"] * how["weight"])
    for key, idx in (("agility", 1), ("perception", 3)):     # progression.AGILITY, PERCEPTION
        if key in how:
            _add_attrib(p, idx, how[key])


def _add_attrib(p, idx, n):
    """bonus_attribs (bit mask plus the dense list of the bits set) with n
    more of attribute idx."""
    mask = int(p.get("bonus_attribs_m") or 0)
    dense = list(p.get("bonus_attribs") or [])
    full, j = [], 0
    for i in range(5):                                       # progression.ATTRIBS
        if mask & (1 << i):
            full.append(dense[j] if j < len(dense) else 0)
            j += 1
        else:
            full.append(0)
    full[idx] += n
    p["bonus_attribs_m"] = sum(1 << i for i, v in enumerate(full) if v)
    p["bonus_attribs"] = [v for v in full if v]


def derived(type_id):
    """Whether lay_frame lays numbers of its own on a type the wiki has no
    table for -- a modified gun (its base's table and effect), a blueprint
    (its level's price), a thing the craft table describes -- so that its
    frame is no longer the designed one (server/test_items.py counts such a
    type among the hand-made ones)."""
    import items
    entry = items.catalogue().get(int(type_id))
    if not entry or int(type_id) in items.wiki():
        return False
    root, name = entry
    if root == items.FIRE_ARM:
        mod = mod_of(type_id)
        return bool(mod and items.wiki().get(mod[0]))
    if root == items.TRASH:
        return bool(_BLUEPRINT.match(name) and not _KNIFE_BLUEPRINT.match(name)) \
            or bool(_table().get(int(type_id), {}).get("desc"))
    return False


def lay_frame(type_id, p, rec):
    """What the weapon craft adds to a thing's static frame (items.static_info,
    after the wiki's table, rec, or the hand-made ones were laid):

      a modified gun the wiki has no table for takes its base gun's table,
      price included, and the effect of its blueprint (EFFECTS) -- rather than
      the designed stand-in every table-less gun gets, a pistol of the first
      level on 9 mm;
      a blueprint no article priced costs its level's (LADDER), and one of
      two effects twice that; a knife's blueprint no article priced half its
      «Заточка и Эргономика» (gold alone, as the knife line is);
      a thing the craft table describes (the parts) points at its words.
    A priced blueprint keeps the article's two prices, afro and gold, each
    paid in its own currency (the stall's «Купить» and «Купить за золото»),
    except the «Урон и размер обоймы» of the gold line (bpg_damage_25_gold_*):
    items.static_info drops its afro price after this (items.GOLD_PRICE_ONLY,
    GOLD_LINE_BLUEPRINTS), so a gold gun's upgrade is paid in gold.
    """
    import items
    entry = items.catalogue().get(type_id)
    if not entry:
        return
    root, name = entry
    if root == items.FIRE_ARM and not rec:
        mod = mod_of(type_id)
        base_rec = items.wiki().get(mod[0]) if mod else None
        if base_rec:
            items._overlay(type_id, p, base_rec)
            _apply(p, mod[1])
            # The base's words are not this type's: its own, or none.
            p["desc"] = items.DESC_ID_OFFSET + type_id \
                if type_id in items._orig_described() else ""
    elif root == items.TRASH:
        m = _BLUEPRINT.match(name)
        k = _KNIFE_BLUEPRINT.match(name)
        if k and not p.get("cost") and not p.get("g_cost") and k.group(2) != "Damage_Actionpoint":
            both = _by_name().get("bpg_knife_lvl%s_Damage_Actionpoint" % k.group(1))
            g = (items.params_of(both) or {}).get("g_cost", 0) if both else 0
            p.update(cost=0, g_cost=g // 2)
        elif m and not rec and not k:
            cost, gold = LADDER.get(int(m.group(3)), LADDER[20])
            two = m.group(1) == "bpb" or m.group(2).startswith(_TWO_EFFECTS)
            p.update(cost=cost * (2 if two else 1), g_cost=gold * (2 if two else 1))
    if type_id in _table() and _table()[type_id].get("desc"):
        p["desc"] = items.DESC_ID_OFFSET + type_id


# --- the upgrader's window -------------------------------------------------------------
def recipes_of(npc_type):
    """[(quest, gun, mod, blueprint)] of the upgrade rows this NPC gives, in
    table order: what its window offers."""
    import quests
    out = []
    for t, rec in rows().items():
        q = quests.get(t)
        if rec.get("family") == "upgrade" and q is not None and int(npc_type) in q.give:
            out.append((q, int(rec["gun"]), int(rec["mod"]), int(rec["blueprint"])))
    return out


def upgrader_lists(npc_type):
    """userInfo_Upgrader's three lists (Upgrader.as: in_types, out_types,
    costs in hundredths of gold): each of the NPC's recipes as the gun it
    takes and the gun it gives, for nothing but the blueprint -- the window
    shows «G 0» under it, and the blueprint is asked for at the upgrade.
    Empty for anybody with no recipe, as every upgrader was before."""
    got = recipes_of(npc_type)
    return dict(in_types=[g for _q, g, _m, _b in got], out_types=[m for _q, _g, m, _b in got],
                costs=[0] * len(got))


def upgrade(sess, master, row, out):
    """«Улучшить» on a gun in the upgrader's window (upgrader.Window: ss_upd;
    s_status=1;obj=x<oid>;param=<type it becomes>, Upgrade._upgradeItem),
    answered with the one cmdAck the client waits on.

    master is the type of the upgrader who opened the window, None once the
    player has left him (upgrader.Window.master): refused (12), nothing
    moves. The gun is the one dragged in (row), wherever the player carries
    it; the recipe is this master's that turns its type into out, and the
    player must be in its band (the row's level and max_level, as the
    quest's) and carry its blueprint in the bag. Then, after the ack
    (Upgrade.upgradeAck plays the animation), the rounds in the gun come out
    into the bag, the gun and one blueprint go, and the modification comes
    in with the gun's wear (wear_of, setcraft.pass_wear; below) -- the
    client changes nothing by itself (ss_obj_status 0 and 1, then the kept
    wear's dynamic info)."""
    import inventory
    import items
    import setcraft                    # late: it imports items, items this module
    inv = sess.inv
    recipe = None
    for q, gun, mod, bp in recipes_of(master) if master is not None else ():
        if gun == row["type_id"] and mod == out:
            recipe = (q, bp)
            break
    if recipe is None:
        inv.ack(inventory.RES_NOT_FOUND)
        return
    quest, bp = recipe
    level = sess.skill_level()
    if quest.over_cap(level) or quest.level > level \
            or inv.bag_pieces().get(bp, 0) < 1:
        inv.ack(inventory.RES_REFUSED)
        return
    inv.ack(inventory.RES_OK)
    inv.forget_reload(row["uniq"])
    if row["root"] == items.FIRE_ARM:
        inv.eject(row)
    old = wear_of(row)
    inv.store.delete_item(row["uniq"])
    inv.push_status(row, 0)
    inv.take_pieces(bp, 1)
    for new in inv.give_pieces(out, 1):
        setcraft.pass_wear(old, new, inv)
    log.info("  ..    upgraded %d into %d at %s with blueprint %d, wear %d/%d",
             row["type_id"], out, master, bp, row["brk"], row["max_break_cur"])


# --- the wear an upgrade keeps -----------------------------------------------------------
# The gun that goes passes its wear to the modification that comes
# (setcraft.worn_as: the share of the ceiling left and of the ceiling
# whole, rounded down), in the window (upgrade) and at a hand-in
# (server.Session.cmd_q_co: before_take, keep_wear) alike; a whetstone's
# knife to its sharpened one the same.
KEEPS_WEAR = ("upgrade", "knife")


def wear_of(row):
    """(brk, max_break_cur, max_break_abs) of a thing, as setcraft.worn_as
    reads it."""
    import items
    return (row["brk"], row["max_break_cur"],
            (items.params_of(row["type_id"]) or {}).get("max_break_abs", 0))


def before_take(quest, inv):
    """Before a hand-in takes its things (server.Session.cmd_q_co, every
    check passed): for an upgrade or a sharpening row, the thing its take
    will take -- the first of the recipe's type in the bag, not on the table
    in a barter, as Inventory.take_pieces goes -- gives its rounds back into
    the bag, as the window's upgrade does, and its wear is kept for
    keep_wear: (the modification, its uniq, wear_of). None for any other
    row, or a bag without the thing."""
    import inventory
    import items
    rec = rows().get(quest.type) if quest is not None else None
    if not rec or rec.get("family") not in KEEPS_WEAR:
        return None
    gun = int(rec["gun"])
    for r in inv.rows():
        if r["type_id"] == gun and r["slot"] == inventory.BAG and r["uniq"] not in inv.locked:
            if r["root"] == items.FIRE_ARM:
                inv.forget_reload(r["uniq"])
                inv.eject(r)
            return int(rec["mod"]), r["uniq"], wear_of(r)
    return None


def keep_wear(worn, given, inv):
    """After the hand-in's take and its reward (given: the rows
    Inventory.give_pieces made): the modification takes the wear of the
    thing that left (before_take). Nothing for None, for a thing the take
    did not take, or for a reward of another type. Returns given."""
    import setcraft                    # late: it imports items, items this module
    if not worn:
        return given
    mod, uniq, old = worn
    if inv.store.item(uniq) is not None:
        return given
    for row in given:
        if row["type_id"] == mod:
            setcraft.pass_wear(old, row, inv)
            break
    return given


# --- the gunsmith's bench: a broken gun -------------------------------------------------
def salvage_of(quest):
    """The salvage record of a quest row ({"weapon", "levels"}), or None."""
    rec = rows().get(quest.type) if quest is not None else None
    return rec if rec and rec.get("family") == "salvage" else None


def _broken(inv, spec):
    """The bag's broken guns a salvage row takes, the cheapest first (then
    the oldest): its class, its levels, worn to nothing (brk 0), one a bench
    may take (salvageable), not on the table in a barter. The row's start
    says so (data/build_weaponcraft.py), and the player cannot pick: the
    bench never takes the dearer of two when a cheaper one is there."""
    import inventory
    import items
    lo, hi = spec["levels"]
    out = []
    for r in inv.rows():
        if r["slot"] != inventory.BAG or r["uniq"] in inv.locked \
                or r["root"] != items.FIRE_ARM or r["brk"] > 0:
            continue
        got = salvageable(r["type_id"])
        if got and got[0] == spec["weapon"] and lo <= got[1] <= hi:
            out.append(r)
    return sorted(out, key=lambda r: (items.params_of(r["type_id"]) or {}).get("cost", 0))


def ready(sess, quest):
    """Whether the hand-in has what a row asks beyond its things and its fee
    (server.Session.fee_ready): for a salvage, a broken gun of its class in
    the bag. Anything else is ready."""
    spec = salvage_of(quest)
    return spec is None or bool(sess.char_id and _broken(sess.inv, spec))


def hand_in(sess, quest):
    """What a hand-in takes beyond its things (server.Session.cmd_q_co, after
    ready): the broken gun of a salvage -- the rounds in it first into the
    bag, then the gun, by ss_obj_status 0."""
    spec = salvage_of(quest)
    if spec is None:
        return
    got = _broken(sess.inv, spec)
    if not got:
        return
    row = got[0]
    sess.inv.forget_reload(row["uniq"])
    sess.inv.eject(row)
    sess.inv.store.delete_item(row["uniq"])
    sess.inv.push_status(row, 0)
