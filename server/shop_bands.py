"""Лавки по уровню городов: what a city's weapon, set and medicine sellers
offer.

The owner's order of 2026-10-10: «у всех продавцов оружия и сетов добавь
всё, что есть, но только по уровню городов: в Вади-Хальфе 8 уровень
потолок; чтобы была и голдовая версия, и обычная. Нижняя граница есть у
каждого города: старт от максимального для предыдущего города». And of
2026-10-12, of the medicine: «сделай во всех городах нормальную продажу
медикаментов и боевой медицины, чтобы везде всё было по уровням, были
версии афро и голд, афро меньше статов должна давать».

data/shop_bands.json holds what was decided: the cities in their order,
each with its ceiling and its places, and which trader types are the
weapon, set and medicine sellers, what kinds each sells and, for a
medicine seller, whether in one currency only. The rest is a rule, so a
gun that gets its numbers or a ceiling that moves is followed without
anybody touching a list:

  THE BAND of a city runs from the ceiling of the city before it (0 for the
  first) to its own, both ends included -- the owner's «старт от
  максимального для предыдущего города»: a thing of level 4 is the valley's
  and Вади-Хальфа's both. The medicine reaches one tier lower (MED_REACH):
  a tier is the city's when its floor lies from the band's floor less 4 to
  its ceiling, the band's tiers and the one under them -- as six of the
  seven medicine stalls of the original the wiki describes sold (Люций and
  Магдалена 0_3-8_11 in Вади-Хальфа, Торси and Мухсим 4_7-12_15 in Абри,
  Киплер and Курт 12_15-20 in Абу-Хамед), for whoever comes to a city
  below its band.

  THE GOODS of a kind are every thing of that kind the game has as an
  ordinary shop thing (ware): a gun of a mass line <class>_<N>_lvl_<L>
  (objects.xml; N from 1, the 0 lines being the collectible and quest (Q)
  ones) or a knife of the knife_lvl<L> series, ordinary (A) or gold (G),
  that has its article's table (data/items_wiki.json -- without one a gun is
  the designed stand-in, 120 afro and no level), a name, and a price in its
  own currency, afro for the ordinary one and gold for the (G); nothing
  out of the game (items.out_of_game: no premium thing, none the owner took
  out by name, data/retired.json items -- Steyr TMP and Chang Feng since
  2026-10-14), nothing a quest owns or lends, no modification. A set piece is
  one of an A or G set of the owner's ladder (data/sets.json), mod00 -- by
  the file's variant, not the piece's internal name: Чёрный Ловелас[12]'s A
  is the original's quest series (_Q_), its G types of our own
  (data/own_items.json), and both are sold since the owner's «за афро и за
  голд» (2026-10-13); a Q set stays off the stalls. And by the name the
  player reads: a piece of the ladder shows the file's, not the original's
  «(Q)». Its
  level is inventory.item_level: the «Необходимые навыки» the client shows,
  the level the owner's rule of 2026-09-25 lets a character hold or wear it
  at. A medicine is one of the original's two lines, named by its stalls:
  «Боевая медицина» (combat_meds, Med_Battle_*: the bandage and the energy
  drink for afro, the injector and its 20-dose pack for gold) and «Еда,
  вода, лекарства» (peace_meds, Med_Pacific_*, no use in a fight: the food,
  the food of ten, the water for afro, the kit of twenty for gold), six
  tiers each, 0_3 to 20, with its table (the wiki's, or data/
  heal_manual.json's for the packs no article describes), its name and its
  price in its own currency as above. Its level is the floor of its tier,
  read off the internal name: the Медицина a bandage's tooltip asks (0 to
  8) is no level, and the gold ones ask none. Every tier has both
  currencies, and the gold one of a tier gives more for one action than
  the afro ones: the original's own numbers, nothing here changes them.

  THE STALL of a seller standing in a city's place is the goods of its
  kinds in the band -- kind by kind in the seller's order, each by level,
  then line, the ordinary before its gold; a set whole, helm to boots, A
  before G; a tier's afro things before its gold ones -- of one currency
  where the file says only, followed by its own list (data/npcs.json, or
  the wiki's) without any weapon, set piece or medicine of the two lines:
  its rounds, stimulants, blueprints, pouches and quest things stay where
  they were. A seller with no kinds keeps its own list, less whatever
  weapon, set piece or medicine on it is not of the band (Хан Сэлл's gold
  collectibles, Барыга Сет's list).

Anywhere else -- a place that is no city's, or no place given at all, which
is what items.stock_for's callers off the wire ask -- a stall is its own
list, as before this module.

The place matters on the wire. A type standing in three cities (the
clothing markets' 5161, Хан Сэлл, the apothecary Джут) sells three bands,
so the client's type_list and the purchase index into it are both taken at
the place of the NPC (server.send_npc_info, inventory.TradeSession).

A file that is there but unreadable or wrong stops the server, as
data/npcs.json does: started without it, the stalls would quietly be the
old ones. A missing file means no bands.
"""
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "shop_bands.json")

# What a seller may sell by its city's band. The six firearm kinds go by the
# class word of the line (objects.xml), which is also the gun's weapon_type.
FIREARM_KINDS = {"pistols": "pistols", "shotguns": "shotgun", "smgs": "sub_machine_guns",
                 "rifles": "rifle", "assault_rifles": "assault_rifle",
                 "machine_guns": "machine_gun"}
# The medicine, by the names of the original's stalls (texts.xml 62151-62166):
# «Боевая медицина» and «Еда, вода, лекарства» / «Лекарства и еда».
MED_KINDS = ("combat_meds", "peace_meds")
KINDS = tuple(FIREARM_KINDS) + ("knives", "sets") + MED_KINDS
_KIND_OF_LINE = {v: k for k, v in FIREARM_KINDS.items()}
# A seller of medicine alone may sell in one currency (the file's "only"):
# the apothecary Джут's gold, the grocers' afro, as their articles had them.
CURRENCIES = ("afro", "gold")

# The highest level a thing asks for (progression's ceiling, the top rung).
TOP_LEVEL = 20
# How far under a city's floor its medicine reaches: one tier (the tiers are
# four levels wide), so a city sells the tiers of its band and the one below
# -- the original's medicine stalls by their articles (the docstring). 0
# sells the band's tiers alone, two to a city. Weapons and sets keep the band.
MED_REACH = 4

_LINE = re.compile(r"^(pistols|shotgun|sub_machine_guns|assault_rifle|rifle|machine_gun)"
                   r"_([1-9]\d*)_lvl_(\d+)(_gold)?$")
_KNIFE = re.compile(r"^knife_lvl(\d+)_(A|G)$")
# The two lines of medicine, tier by tier: the tier is the levels it is for
# (0_3 .. 16_19, 20), the end what it is (A afro, Ax10 ten of it, G gold,
# G_Pack twenty doses of the gold). Not the (P) kits (_P, out of the game),
# not the thousand-dose pack (_Pack1000, no numbers), not the May ones.
_MED = re.compile(r"^Med_(Battle|Pacific)_(Heal|Rest|HR)_(0_3|4_7|8_11|12_15|16_19|20)"
                  r"_(A|Ax10|G|G_Pack)$")
_MED_PREFIX = ("Med_Battle_", "Med_Pacific_")
# The rows of a tier, in the stall's order: the afro ones, then the gold.
_MED_ROW = {("Battle", "Heal", "A"): 0, ("Battle", "Rest", "A"): 1,
            ("Battle", "HR", "G"): 2, ("Battle", "HR", "G_Pack"): 3,
            ("Pacific", "Heal", "A"): 0, ("Pacific", "Heal", "Ax10"): 1,
            ("Pacific", "Rest", "A"): 2, ("Pacific", "HR", "G"): 3}
_MED_KIND = {"Battle": "combat_meds", "Pacific": "peace_meds"}
# An original's name that marks a thing no shop line is: a quest (Q), a
# reward (R/Rw), somebody's own, a holiday's.
_NOT_SHOP_NAME = re.compile(r"\((?:Q|R|Rw|RW|VIP)\)|Личн|Новогод|1 апреля", re.I)


def _fail(why):
    raise RuntimeError("data/shop_bands.json: %s -- the server does not start without "
                       "a readable table" % why)


def parse(doc):
    """(cities, city of each place, sellers, currency) out of the file's document.

    cities: [(name, low, top, frozenset of places)] in the file's order, each
    low the ceiling of the one before (0 for the first); sellers: trader
    type -> tuple of kinds, empty for a seller that only has its own list cut;
    currency: trader type -> "afro" or "gold" for a seller of medicine that
    sells in that currency alone (its "only"; weapons and sets go in both
    versions by the order of 2026-10-10, so no other seller may have one).
    """
    cities, city_of, low = [], {}, 0
    rows = doc.get("cities")
    if not isinstance(rows, list):
        _fail("cities is a list, in order")
    for i, row in enumerate(rows):
        where = "city %d" % i
        if not isinstance(row, dict):
            _fail("%s: not an object" % where)
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            _fail("%s: no name" % where)
        top = row.get("top")
        if isinstance(top, bool) or not isinstance(top, int) or not low <= top <= TOP_LEVEL:
            _fail("%s (%s): top %r is a whole level from %d (the city before's) to %d"
                  % (where, name, top, low, TOP_LEVEL))
        places = row.get("places")
        if not isinstance(places, list) or not all(
                isinstance(p, int) and not isinstance(p, bool) for p in places):
            _fail("%s (%s): places is a list of location ids" % (where, name))
        for p in places:
            if p in city_of:
                _fail("place %d is in %s and %s" % (p, city_of[p], name))
            city_of[p] = name
        cities.append((name, low, top, frozenset(places)))
        low = top
    sellers, currency = {}, {}
    for key, row in (doc.get("sellers") or {}).items():
        if str(key).startswith("_"):
            continue
        try:
            trader = int(key)
        except ValueError:
            _fail("seller %r: the key is a trader type" % key)
        kinds = (row or {}).get("sells") if isinstance(row, dict) else None
        if not isinstance(kinds, list) or any(k not in KINDS for k in kinds) \
                or len(set(kinds)) != len(kinds):
            _fail("seller %s: sells is a list of distinct kinds of %s" % (key, ", ".join(KINDS)))
        one = row.get("only")
        if one is not None:
            if one not in CURRENCIES:
                _fail("seller %s: only is %s, or no such key" % (key, " or ".join(CURRENCIES)))
            if not kinds or any(k not in MED_KINDS for k in kinds):
                _fail("seller %s: one currency only is for a seller of medicine alone (%s);"
                      " weapons and sets go in both versions" % (key, ", ".join(MED_KINDS)))
            currency[trader] = one
        sellers[trader] = tuple(kinds)
    return cities, city_of, sellers, currency


def _load():
    try:
        with open(PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return [], {}, {}, {}
    except (OSError, ValueError) as e:
        _fail("%s: %s" % (type(e).__name__, e))
    return parse(doc)


CITIES, CITY_OF, SELLERS, ONLY = _load()


def city(loc_id):
    """(name, low, top) of the city a place is, or None."""
    name = CITY_OF.get(loc_id)
    for row in CITIES:
        if row[0] == name:
            return row[:3]
    return None


def band(loc_id):
    """(low, top) of the place's city, or None for a place that is no city's."""
    c = city(loc_id)
    return c[1:] if c else None


def kinds(trader_type):
    """The kinds a seller sells by its city's band, () for one that only has
    its own list cut to it, or None for a trader the bands leave alone."""
    return SELLERS.get(trader_type)


def only(trader_type):
    """The one currency a seller of medicine sells in, "afro" or "gold", or
    None for both (and for every other trader)."""
    return ONLY.get(trader_type)


# --- the goods ---------------------------------------------------------------------------

_WARES = None


def _named(type_id):
    """Whether some table gives the thing a name of its own, rather than the
    internal one names.ITEM_NAMES falls back to. Read off the tables names.py
    lays, not names itself, which imports this module's importer."""
    import items
    import orig_texts
    import sets
    return type_id in orig_texts.item_names() or type_id in items.wiki_names() \
        or type_id in sets.item_names()


def _med(name):
    """(kind, level, row, gold) of a medicine of the two lines by its internal
    name, or None: the level is the floor of its tier, the row its place in
    the tier (_MED_ROW)."""
    m = _MED.match(name)
    row = _MED_ROW.get((m.group(1), m.group(2), m.group(4))) if m else None
    if row is None:
        return None
    return (_MED_KIND[m.group(1)], int(m.group(3).split("_")[0]), row,
            m.group(4).startswith("G"))


def ware(type_id):
    """(kind, level, line, tier) of an ordinary shop thing, or None.

    tier is 0 for the ordinary (afro) one and 1 for the gold; line orders the
    guns of a level (the line's index), the pieces of a set (its slot) and the
    medicines of a tier (_MED_ROW)."""
    return wares().get(type_id)


def wares():
    """type_id -> (kind, level, line, tier) for every shop thing; built once."""
    global _WARES
    if _WARES is not None:
        return _WARES
    import inventory
    import items
    import orig_texts
    import quests
    import sets
    out = {}
    orig = orig_texts.item_names()
    wiki = items.wiki()
    manual = items.heal_manual()
    set_names = sets.item_names()
    for t, (root, name) in items.catalogue().items():
        kind = line = level = None
        if root == items.FIRE_ARM:
            m = _LINE.match(name)
            if m:
                kind, line, gold = _KIND_OF_LINE[m.group(1)], int(m.group(2)), bool(m.group(4))
        elif root == items.COLD_ARM:
            m = _KNIFE.match(name)
            if m:
                kind, line, gold = "knives", 0, m.group(2) == "G"
        elif root == items.WEAR:
            # A piece of an A or G set of the ladder by the file's variant
            # (the file holds the mod00 pieces alone): Чёрный Ловелас's A is
            # the original's quest series, _Q_ by its internal name.
            variant = sets.variant_of(t)
            if variant in ("A", "G"):
                kind, gold = "sets", variant == "G"
                line = sets.SLOTS.index(sets.slot_of(t))
        elif root == items.HEAL:
            med = _med(name)
            if med:
                kind, level, line, gold = med
        if kind is None:
            continue
        if kind in MED_KINDS:
            if t not in wiki and t not in manual:
                continue                # the designed frame: 60 afro, one use, under a (G) name
        elif kind != "sets" and t not in wiki:
            continue                    # the designed stand-in: no level, 120 afro
        p = items.params_of(t) or {}
        priced = (p.get("g_cost", 0) > 0 and not p.get("cost")) if gold \
            else (p.get("cost", 0) > 0 and not p.get("g_cost"))
        # The name the player reads: a piece of the ladder shows the set
        # file's, over the original's «... (Q)» (names.SET_ITEM_NAMES).
        shown = set_names.get(t) or orig.get(t) or ""
        # Nothing out of the game (items.out_of_game): no (P), and nothing
        # the owner took out by name (data/retired.json items) -- whatever
        # band, so a city added later sells none of them either.
        if not priced or items.out_of_game(t) or p.get("quest") or quests.lent(t) \
                or not _named(t) or _NOT_SHOP_NAME.search(shown):
            continue
        if level is None:
            level = inventory.item_level(t)
        out[t] = (kind, level, line, 1 if gold else 0)
    _WARES = out
    return out


def _order(type_id):
    import sets
    kind, level, line, tier = wares()[type_id]
    if kind == "sets":
        # A set whole, helm to boots, the ordinary before the gold one.
        family = sets.SETS[sets.set_of(type_id)]["name"].removesuffix(" (G)")
        return level, family, tier, line
    # A gun or a knife by its line, the ordinary right before its gold; a
    # medicine by the rows of its tier, the afro ones before the gold.
    return level, line, tier, type_id


def goods(kinds_, low, top, only=None):
    """The band's things of these kinds, in the stall's order: of the band
    low-top (the medicine from a tier under it, MED_REACH), and of one
    currency where only says which ("afro", "gold")."""
    out = []
    for kind in kinds_:
        floor = low - (MED_REACH if kind in MED_KINDS else 0)
        mine = [t for t, w in wares().items() if w[0] == kind and floor <= w[1] <= top
                and (only is None or w[3] == (only == "gold"))]
        out += sorted(mine, key=_order)
    return out


def medicine(type_id):
    """Whether a type is a medicine of the two lines, Med_Battle_* or
    Med_Pacific_*, of any tier or variant, the (P) and the thousand-dose pack
    among them: a city's band decides it in place of a trader's list. The
    stimulants, the reagents and a quest's bandages are named otherwise and
    stay on their lists."""
    import items
    entry = items.catalogue().get(type_id)
    return bool(entry and entry[0] == items.HEAL and entry[1].startswith(_MED_PREFIX))


def band_ware(type_id):
    """Whether a type is a weapon, a set piece or a medicine of the two lines:
    what a seller's own list gives up in a city (all of it for a seller of
    kinds, what is out of the band for one without). A gift bouquet is a cold
    arm to the client, and on nobody's band list it stays where it is."""
    import items
    import sets
    return items.root_of(type_id) in (items.FIRE_ARM, items.COLD_ARM) \
        or bool(sets.set_of(type_id)) or medicine(type_id)


def level_of(type_id):
    """The level a city's band reads a thing at: a shop thing's (wares), a
    medicine's by the floor of its tier, anything else inventory.item_level."""
    w = wares().get(type_id)
    if w:
        return w[1]
    import inventory
    import items
    entry = items.catalogue().get(type_id)
    med = _med(entry[1]) if entry and entry[0] == items.HEAL else None
    return med[1] if med else inventory.item_level(type_id)


def fits(type_id, low, top):
    """Whether a thing is of the band low-top, both ends included: a medicine
    of the two lines from a tier under the floor (MED_REACH), anything else
    within it."""
    reach = MED_REACH if medicine(type_id) else 0
    return low - reach <= level_of(type_id) <= top


def apply(trader_type, loc_id, own):
    """What the trader's stall holds at this place, given its own list."""
    which = SELLERS.get(trader_type)
    b = band(loc_id) if loc_id is not None else None
    if which is None or b is None:
        return list(own)
    low, top = b
    # Halfa's knife merchant also serves players arriving at level one.
    # Keep every other seller and city band unchanged.
    if trader_type == 1152 and loc_id == 102:
        low = 1
    if which:
        return goods(which, low, top, ONLY.get(trader_type)) \
            + [t for t in own if not band_ware(t)]
    return [t for t in own if not band_ware(t) or fits(t, low, top)]
