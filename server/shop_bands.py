"""Лавки по уровню городов: what a city's weapon and set sellers offer.

The owner's order of 2026-10-10: «у всех продавцов оружия и сетов добавь
всё, что есть, но только по уровню городов: в Вади-Хальфе 8 уровень
потолок; чтобы была и голдовая версия, и обычная. Нижняя граница есть у
каждого города: старт от максимального для предыдущего города».

data/shop_bands.json holds what was decided: the cities in their order,
each with its ceiling and its places, and which trader types are the
weapon and set sellers and what kinds each sells. The rest is a rule, so a
gun that gets its numbers or a ceiling that moves is followed without
anybody touching a list:

  THE BAND of a city runs from the ceiling of the city before it (0 for the
  first) to its own, both ends included -- the owner's «старт от
  максимального для предыдущего города»: a thing of level 4 is the valley's
  and Вади-Хальфа's both.

  THE GOODS of a kind are every thing of that kind the game has as an
  ordinary shop thing (ware): a gun of a mass line <class>_<N>_lvl_<L>
  (objects.xml; N from 1, the 0 lines being the collectible and quest (Q)
  ones) or a knife of the knife_lvl<L> series, ordinary (A) or gold (G),
  that has its article's table (data/items_wiki.json -- without one a gun is
  the designed stand-in, 120 afro and no level), a name, and a price in its
  own currency, afro for the ordinary one and gold for the (G); nothing
  premium, nothing a quest owns or lends, no modification. A set piece is
  one of an A or G set of the owner's ladder (data/sets.json), mod00. Its
  level is inventory.item_level: the «Необходимые навыки» the client shows,
  the level the owner's rule of 2026-09-25 lets a character hold or wear it
  at.

  THE STALL of a seller standing in a city's place is the goods of its
  kinds in the band -- kind by kind in the seller's order, each by level,
  then line, the ordinary before its gold; a set whole, helm to boots, A
  before G -- followed by its own list (data/npcs.json, or the wiki's)
  without any weapon or set piece: its rounds, medicine, blueprints and
  pouches stay where they were. A seller with no kinds keeps its own list,
  less whatever weapon or set piece on it is not of the band (Хан Сэлл's
  gold collectibles, Барыга Сет's list).

Anywhere else -- a place that is no city's, or no place given at all, which
is what items.stock_for's callers off the wire ask -- a stall is its own
list, as before this module.

The place matters on the wire. A type standing in three cities (the
clothing markets' 5161, Хан Сэлл) sells three bands, so the client's
type_list and the purchase index into it are both taken at the place of the
NPC (server.send_npc_info, inventory.TradeSession).

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
KINDS = tuple(FIREARM_KINDS) + ("knives", "sets")
_KIND_OF_LINE = {v: k for k, v in FIREARM_KINDS.items()}

# The highest level a thing asks for (progression's ceiling, the top rung).
TOP_LEVEL = 20

_LINE = re.compile(r"^(pistols|shotgun|sub_machine_guns|assault_rifle|rifle|machine_gun)"
                   r"_([1-9]\d*)_lvl_(\d+)(_gold)?$")
_KNIFE = re.compile(r"^knife_lvl(\d+)_(A|G)$")
_SET_PIECE = re.compile(r"^(helm|shirt|armor|pants|boots)_.+_LVL_\d+_(A|G)_mod00$")
# An original's name that marks a thing no shop line is: a quest (Q), a
# reward (R/Rw), somebody's own, a holiday's.
_NOT_SHOP_NAME = re.compile(r"\((?:Q|R|Rw|RW|VIP)\)|Личн|Новогод|1 апреля", re.I)


def _fail(why):
    raise RuntimeError("data/shop_bands.json: %s -- the server does not start without "
                       "a readable table" % why)


def parse(doc):
    """(cities, city of each place, sellers) out of the file's document.

    cities: [(name, low, top, frozenset of places)] in the file's order, each
    low the ceiling of the one before (0 for the first); sellers: trader
    type -> tuple of kinds, empty for a seller that only has its own list cut.
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
    sellers = {}
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
        sellers[trader] = tuple(kinds)
    return cities, city_of, sellers


def _load():
    try:
        with open(PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return [], {}, {}
    except (OSError, ValueError) as e:
        _fail("%s: %s" % (type(e).__name__, e))
    return parse(doc)


CITIES, CITY_OF, SELLERS = _load()


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


def ware(type_id):
    """(kind, level, line, tier) of an ordinary shop thing, or None.

    tier is 0 for the ordinary (afro) one and 1 for the gold; line orders the
    guns of a level (the line's index) and the pieces of a set (its slot)."""
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
    for t, (root, name) in items.catalogue().items():
        kind = line = None
        if root == items.FIRE_ARM:
            m = _LINE.match(name)
            if m:
                kind, line, gold = _KIND_OF_LINE[m.group(1)], int(m.group(2)), bool(m.group(4))
        elif root == items.COLD_ARM:
            m = _KNIFE.match(name)
            if m:
                kind, line, gold = "knives", 0, m.group(2) == "G"
        elif root == items.WEAR:
            m = _SET_PIECE.match(name)
            set_type = sets.set_of(t)
            if m and set_type:
                kind, gold = "sets", m.group(2) == "G"
                line = sets.SLOTS.index(m.group(1))
        if kind is None:
            continue
        if kind != "sets" and t not in wiki:
            continue                    # the designed stand-in: no level, 120 afro
        p = items.params_of(t) or {}
        priced = (p.get("g_cost", 0) > 0 and not p.get("cost")) if gold \
            else (p.get("cost", 0) > 0 and not p.get("g_cost"))
        if not priced or items.premium(t) or p.get("quest") or quests.lent(t) \
                or not _named(t) or _NOT_SHOP_NAME.search(orig.get(t) or ""):
            continue
        out[t] = (kind, inventory.item_level(t), line, 1 if gold else 0)
    _WARES = out
    return out


def _order(type_id):
    import sets
    kind, level, line, tier = wares()[type_id]
    if kind == "sets":
        # A set whole, helm to boots, the ordinary before the gold one.
        return level, tier, sets.set_of(type_id), line
    return level, line, tier, type_id


def goods(kinds_, low, top):
    """The band's things of these kinds, in the stall's order."""
    out = []
    for kind in kinds_:
        mine = [t for t, w in wares().items() if w[0] == kind and low <= w[1] <= top]
        out += sorted(mine, key=_order)
    return out


def band_ware(type_id):
    """Whether a type is a weapon or a set piece: what a seller's own list
    gives up in a city (all of it for a seller of kinds, what is out of the
    band for one without). A gift bouquet is a cold arm to the client, and on
    nobody's band list it stays where it is."""
    import items
    import sets
    return items.root_of(type_id) in (items.FIRE_ARM, items.COLD_ARM) \
        or bool(sets.set_of(type_id))


def apply(trader_type, loc_id, own):
    """What the trader's stall holds at this place, given its own list."""
    which = SELLERS.get(trader_type)
    b = band(loc_id) if loc_id is not None else None
    if which is None or b is None:
        return list(own)
    low, top = b
    if which:
        return goods(which, low, top) + [t for t in own if not band_ware(t)]
    import inventory
    return [t for t in own if not band_ware(t) or low <= inventory.item_level(t) <= top]
