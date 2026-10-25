"""Clothing sets: which pieces make one, what the set adds, and ss_si_set.

A piece of clothing belongs to a set when its ss_si_wear carries a non-zero
set_type (Wear.as:49-53). The moment such a frame arrives -- a stall's list
opening, a bag loading at login -- the client asks once per set what it is,
ss_get_s_si;type=N, and later draws the answer as a second tooltip beside the
item's (AnnotationManager, Annotation.sets): the set's name, its description,
and one line "Комплект из K предметов" for each K from 2 to 6 that has a
bonus, in gold once K pieces are worn. Pieces are counted in the head, shirt,
armour, legs and boots slots, and only while not broken; the belt never counts
(PersEquip.getNumOfSetItem). All five of one set also swap the character's
look for the set's res (PersEquip.getFullSetID/checkFullSet); res 0 leaves it.
look() says which; the wearer's client works its own out from ss_si_set's
res, and everybody else is told (inventory.py, "the figure").

The original server's sets are lost, numbers and all; texts.xml kept their
names and descriptions and nothing else. data/sets.json is the owner's file:
which types form a set, what each piece is called and worth, what the set
adds -- the ladder Локсли sells, numbered from the 2013 wiki's tables of
those very sets, and its header says where and why it had to design instead.

A piece's name and description in the file are its own and win over the
original's (item_names, item_descs; names.py lays them over ORIG_ITEM_*).
The owner chose the sets by their icons (data/build_sets.py turns his layout
into this file), and the original's words for those types often belong to
other sets: it calls the Странник and Налетчик pieces (Set_M_LVL_11 and _8)
Колонист, and Вещи Беженца's panama and poncho (Bs_M_LVL_0) "Очки-консервы"
and "Топик".

WHAT THE CLIENT ADDS ITSELF, AND WHAT IT LEAVES TO US

Of a set's bonuses the client adds three on its own: od, cp and ce, to the
action points and the crit figures of the character card (CharInterface
showOD/showKrit -> getBonusFromSet). Health, stamina, attributes, skills and
specialisations it adds nowhere; those are the server's to put into rp_info
and into the fight. This module does not apply anything. bonuses() answers
the one question applying them needs -- what does this character get from
what it has on -- and pieces() the question under it; inventory.gear_bonus
asks it, with each piece's own bonus_* beside it, and the Character carries
the sum.

THE WINDOW

SetManager keeps at most five ss_get_s_si in flight and frees a place only
when an ss_si_set comes back, looked up by the type it carries
(setList[obj.param.type]). So every request gets exactly one ss_si_set with
the type it asked about -- an unknown type too, and a request whose handler
failed -- and never a cmdAck: nothing waits for one on that queue.

NUMBERS ON THE WIRE

The name travels as a string id, like everything else (names.py): 7 000 000 +
set_type for the name, 7 100 000 + set_type for the description, so a
set_type stays below 100 000. Both are added to names.ALL; the client asks
the string collector for the name the moment the answer arrives
(SetObject.initGDSLStringData), and an id the preload lacks is a trip back
to the login screen. The bonus lists are a bit mask and the dense list of
values for the bits set, exactly as PersAttributes reads rp_info
(progression.packed); a K with nothing to add sends nothing at all.

Like the quest and transport tables, the file is read at import with no
try/except: a table that failed to load would leave the set names off the
HTTP preload while the game server still sent them. Better to fail at start,
in both processes.
"""
import io
import json
import os

import orig_texts
import progression
import quests

NAME_ID_OFFSET = 7_000_000
DESC_ID_OFFSET = 7_100_000
MAX_SET_TYPE = DESC_ID_OFFSET - NAME_ID_OFFSET - 1

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "sets.json")

# The five pieces a set is counted over, in the client's order.
SLOTS = ("helm", "shirt", "armor", "pants", "boots")
# A set's variant (the file's "variant"): A sold for afro, G for gold, Q a
# quest's, "" where the file says none. What the stalls sell of the ladder
# is its A and G sets (shop_bands.wares).
VARIANTS = ("", "A", "G", "Q")
# SetObject.initSet reads bonus_2_* .. bonus_6_*.
PIECES = range(2, 7)

# The names the client's tooltip gives them (Annotation.as:36-41), in the
# order of the bits: what the owner writes in the file.
ATTRIBS = ("Сила", "Ловкость", "Телосложение", "Восприятие", "Интеллект")
SKILLS = ("Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство")
SPECS = ("Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы",
         "Винтовки", "Ручные пулеметы", "Пистолет-пулеметы", "Хирургия", "Первая помощь",
         "Добыча", "Переработка", "UC1", "UC2", "UC3")
LISTS = (("attribs", ATTRIBS), ("skills", SKILLS), ("specs", SPECS))
# Health, stamina, action points, crit, anti-crit: one number each.
SCALARS = ("hp", "st", "od", "cp", "ce")

# What a piece's record may lay over its designed ss_si_wear frame, the way a
# wiki record is laid (items._overlay), plus "need" by name.
ITEM_FIELDS = ("armor_class", "max_break_abs", "weight", "cost", "g_cost", "premium",
               "exchang", "bonus_hp", "bonus_st", "bonus_od", "bonus_cp", "bonus_ce")


def zero():
    """A bonus of nothing: the scalars and the three lists, all naught."""
    b = {k: 0 for k in SCALARS}
    for kind, titles in LISTS:
        b[kind] = [0] * len(titles)
    return b


def _where(name):
    """(list kind, index) of an attribute, skill or specialisation, or None."""
    for kind, titles in LISTS:
        if name in titles:
            return kind, titles.index(name)
    return None


def _int(where, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s: %r is not a whole number" % (where, value))
    return value


def _bonus(where, rec):
    """One K of a set's bonus, from the file's names to zero()'s shape."""
    if not isinstance(rec, dict):
        raise ValueError("%s: not an object" % where)
    b = zero()
    for key, value in rec.items():
        if key.startswith("_"):
            continue
        value = _int("%s.%s" % (where, key), value)
        if key in SCALARS:
            b[key] = value
            continue
        at = _where(key)
        if at is None:
            raise ValueError("%s: %r is no bonus the client can show (%s, or an attribute, "
                             "skill or specialisation by its tooltip name)"
                             % (where, key, "/".join(SCALARS)))
        b[at[0]][at[1]] = value
    return b


def _need(where, rec):
    """A piece's requirements by name -> need_*_m / need_* for the frame."""
    if not isinstance(rec, dict):
        raise ValueError("%s: not an object" % where)
    values = {kind: [0] * len(titles) for kind, titles in LISTS}
    for key, value in rec.items():
        at = _where(key)
        if at is None:
            raise ValueError("%s: %r is no attribute, skill or specialisation" % (where, key))
        values[at[0]][at[1]] = _int("%s.%s" % (where, key), value)
    out = {}
    for kind, titles in LISTS:
        idxs = [i for i, v in enumerate(values[kind]) if v]
        if idxs:
            mask, dense = progression.packed(values[kind], idxs, len(titles))
            out["need_%s_m" % kind] = mask
            out["need_%s" % kind] = dense
    return out


def _label(where, value, clean):
    """A piece's name or description as the wire shows it, or None where the
    file gives none (the original's, if any, then stands)."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not clean(value).strip():
        raise ValueError("%s: not text" % where)
    return clean(value)


def parse(doc):
    """(sets, set of each type, piece records) out of the file's document.

    Raises ValueError on anything the wire could not carry or the file does
    not mean: an unknown key, a number that is not whole, a type in two
    sets, a K the client does not read. What makes a good set is the tests'
    business; what makes a readable one is this.

    A piece's name is written the way texts.xml writes one, tags and all
    ("Шляпа странника[6][G]"), and cleaned the way the original's are, so a
    gold piece reads "(G)" exactly like every other gold thing in the game.
    """
    table, set_of, pieces = {}, {}, {}
    for key, rec in (doc.get("sets") or {}).items():
        where = "set %s" % key
        if not isinstance(rec, dict):
            raise ValueError("%s: not an object" % where)
        try:
            set_type = int(key)
        except ValueError:
            raise ValueError("%s: the key is the set_type, a number" % where)
        if not 0 < set_type <= MAX_SET_TYPE:
            raise ValueError("%s: set_type out of 1..%d" % (where, MAX_SET_TYPE))
        name = rec.get("name")
        if not isinstance(name, str) or not orig_texts.item_name(name).strip():
            raise ValueError("%s: no name" % where)
        desc = rec.get("desc") or ""
        if not isinstance(desc, str):
            raise ValueError("%s: desc is not text" % where)
        bonus = {}
        for k, b in (rec.get("bonus") or {}).items():
            if not k.isdigit() or int(k) not in PIECES:
                raise ValueError("%s: bonus for %r pieces; the client reads 2..6" % (where, k))
            bonus[int(k)] = _bonus("%s bonus %s" % (where, k), b)
        members, names, descs = {}, {}, {}
        for slot, piece in (rec.get("members") or {}).items():
            at = "%s %s" % (where, slot)
            if slot not in SLOTS:
                raise ValueError("%s: a set is counted over %s only" % (at, ", ".join(SLOTS)))
            if not isinstance(piece, dict):
                raise ValueError("%s: not an object" % at)
            type_id = _int(at + ".type", piece.get("type"))
            if type_id in set_of:
                raise ValueError("%s: type %d is already in set %d" % (at, type_id, set_of[type_id]))
            over = {}
            for field, value in piece.items():
                if field in ("type", "need", "name", "desc") or field.startswith("_"):
                    continue
                if field not in ITEM_FIELDS:
                    raise ValueError("%s: %r is not a field a piece may set (%s, need, name, desc)"
                                     % (at, field, ", ".join(ITEM_FIELDS)))
                over[field] = _int("%s.%s" % (at, field), value)
            over.update(_need(at + ".need", piece.get("need") or {}))
            label = _label(at + ".name", piece.get("name"), orig_texts.item_name)
            if label is not None:
                names[type_id] = label
            label = _label(at + ".desc", piece.get("desc"), orig_texts.text)
            if label is not None:
                descs[type_id] = label
            members[slot] = type_id
            set_of[type_id] = set_type
            pieces[type_id] = over
        if not members:
            raise ValueError("%s: no members" % where)
        variant = rec.get("variant") or ""
        if variant not in VARIANTS:
            raise ValueError("%s: variant %r is none of %s" % (where, variant, "/".join(VARIANTS[1:])))
        table[set_type] = dict(name=orig_texts.item_name(name), desc=orig_texts.text(desc),
                               family=rec.get("family") or str(set_type),
                               level=_int(where + ".level", rec.get("level", 0)),
                               res=_int(where + ".res", rec.get("res", 0)), variant=variant,
                               bonus=bonus, members=members, names=names, descs=descs)
    return table, set_of, pieces


def _load():
    with io.open(PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    try:
        return parse(doc)
    except ValueError as e:
        raise ValueError("data/sets.json: %s -- the server does not start without "
                         "a readable table" % e)


SETS, SET_OF, ITEMS = _load()


def set_of(type_id):
    """The set a type belongs to, or 0 -- which is what ss_si_wear says for none."""
    return SET_OF.get(type_id, 0)


def variant_of(type_id):
    """The variant of the set a piece is in (VARIANTS), "" for none."""
    s = SETS.get(SET_OF.get(type_id))
    return s["variant"] if s else ""


def slot_of(type_id):
    """The slot a piece fills in its set (SLOTS), or None."""
    s = SETS.get(SET_OF.get(type_id))
    if not s:
        return None
    return next(slot for slot, t in s["members"].items() if t == type_id)


def item(type_id):
    """What the file lays over this piece's ss_si_wear, or None."""
    return ITEMS.get(type_id)


def strings():
    """Every set string id and its text, for names.ALL."""
    out = {}
    for set_type, s in SETS.items():
        out[NAME_ID_OFFSET + set_type] = s["name"]
        if s["desc"]:
            out[DESC_ID_OFFSET + set_type] = s["desc"]
    return out


def item_names():
    """type_id -> the name the file gives a piece, cleaned.

    By type, not by string id: the pieces' names live where every item's
    does (items.STRING_ID_OFFSET + type), and names.py puts them there, over
    the original's, since the owner named these by their icons.
    """
    return {t: n for s in SETS.values() for t, n in s["names"].items()}


def item_descs():
    """type_id -> the description the file gives a piece, cleaned; names.py
    puts it under items.DESC_ID_OFFSET + type, over the original's."""
    return {t: d for s in SETS.values() for t, d in s["descs"].items()}


def described(type_id):
    """Whether the file gives this piece a description of its own -- and so
    whether ss_si_wear may carry its id even where the original has none."""
    s = SETS.get(SET_OF.get(type_id))
    return bool(s and type_id in s["descs"])


def fallback(type_value):
    """An answer that says nothing, for a type nobody knows or a request that
    went wrong: it frees the window's place and shows no tooltip. The type is
    echoed however it came, since that is what the client looks the set up
    by; the name is the empty string every client already has."""
    try:
        type_value = int(type_value)
    except (TypeError, ValueError):
        pass
    return dict(type=type_value, res=0, name=quests.EMPTY_STRING_ID, desc="")


def frame(set_type):
    """The ss_si_set parameters for one set, the keys SetObject.initSet reads."""
    s = SETS.get(set_type)
    if s is None:
        return fallback(set_type)
    p = dict(type=set_type, res=s["res"], name=NAME_ID_OFFSET + set_type,
             desc=DESC_ID_OFFSET + set_type if s["desc"] else "")
    for k in PIECES:
        b = s["bonus"].get(k)
        if not b:
            continue
        for kind, titles in LISTS:
            idxs = [i for i, v in enumerate(b[kind]) if v]
            if idxs:
                mask, dense = progression.packed(b[kind], idxs, len(titles))
                p["bonus_%d_%s_m" % (k, kind)] = mask
                p["bonus_%d_%s" % (k, kind)] = dense
        for key in SCALARS:
            if b[key]:
                p["bonus_%d_%s" % (k, key)] = b[key]
    return p


def pieces(worn):
    """set_type -> how many of its pieces are among these types.

    `worn` is the type ids in the five counted slots -- head, shirt, armour,
    legs, boots -- of pieces that are not broken, as the client counts them.
    """
    out = {}
    for type_id in worn:
        s = SET_OF.get(type_id)
        if s:
            out[s] = out.get(s, 0) + 1
    return out


def bonuses(worn):
    """Everything the sets among these pieces add, as zero()'s shape.

    Cumulative, the way the tooltip lights its lines: four pieces of a set
    earn its K=2, K=3 and K=4 bonuses together. Remember that od, cp and ce
    are added by the client's card on its own; whoever applies these must
    not put them into rp_info a second time.
    """
    total = zero()
    for set_type, n in pieces(worn).items():
        for k, b in SETS[set_type]["bonus"].items():
            if k <= n:
                for key in SCALARS:
                    total[key] += b[key]
                for kind, _titles in LISTS:
                    total[kind] = [a + c for a, c in zip(total[kind], b[kind])]
    return total


def look(worn):
    """The res a character in these five pieces is drawn as, or 0 for its own.

    `worn` is the type in each counted slot -- head, shirt, armour, legs,
    boots, None where the slot is empty -- and the answer is what the
    client works out for itself (PersEquip.getFullSetID, then checkFullSet):
    all five slots filled, all with one set_type that is not 0, and that
    set's res. Broken or not does not matter here, unlike for the bonuses:
    getFullSetID never reads __break, so a full set whose boots gave out
    still wears the set's figure on the wearer's own screen, and so it must
    on everybody else's. Nor does the sex: PersInfo puts setResID over
    persType whoever wears it.
    """
    worn = list(worn)
    if len(worn) != len(SLOTS) or any(t is None for t in worn):
        return 0
    kinds = {SET_OF.get(t, 0) for t in worn}
    if len(kinds) != 1:
        return 0
    set_type = kinds.pop()
    return SETS[set_type]["res"] if set_type else 0
