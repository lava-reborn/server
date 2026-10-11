"""The traders of the Nubian valley and the Caravan, each list held to the
rule it was made by.

The owner decided these on 2026-09-24: the Caravan's Шульц, Эрикесэм and
Абдула sell what their Nubian namesakes Борис, Морис and Локсли sell;
Хасани only the food and water of Морис's list; Бомани and Ро-А-Ким the
rounds of every pistol Борис sells; Одноглазый the cold arms of levels 0-8,
plain and gold; the nameless 5208 nothing at all; and 5220 is Странник. The
lists live in data/npcs.json. Each is recomputed here from its rule, so a
hand edit that breaks one fails, and so does a change to Борис, Морис or
Локсли that their copies did not follow. On 2026-09-26 the owner filled
the empty stall of Барыга Сет (1187) at the arena with his wiki page's
list, as far as the client can show it (below, and test_seth_stall on
the socket). On 2026-10-10 the owner put every weapon and set seller on
his city's band (shop_bands.py, test_stall_bands): Борис and Шульц sell the
valley's pistols 0-4, Одноглазый its knives 0-4 and Локсли and Абдула its
sets 0-4, both versions, from the band at their places; their own lists in
data/npcs.json keep the rest -- the rounds, the silk.

In process, no sockets, like test_items: items.stock_for is the type_list
a stall sends, items.static_info the answer to each ss_get_si its window
asks, names.known what may be sent at all.

    LAVA_RES=.../lava/res python3 server/test_shops.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import sets  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


cat = items.catalogue()

BORIS, MORIS, LOXLEY = 5212, 5211, 5213
SCHULZ, ERIKESAM, ABDULA = 5221, 5224, 5223
HASANI, BOMANI, RO_A_KIM = 5217, 5218, 5219
ONE_EYE, STRANNIK, NAMELESS = 5222, 5220, 5208
SETH = 1187
# Where each stands: the valley's market and the Caravan, the arena.
PLACE = {BORIS: 185, MORIS: 185, LOXLEY: 185, SCHULZ: 186, ERIKESAM: 186, ABDULA: 186,
         ONE_EYE: 186, HASANI: 181, BOMANI: 181, RO_A_KIM: 183, SETH: 167}

# The folder under res/classes each root draws its icons from.
ICON_FOLDER = {items.FIRE_ARM: "FireArm", items.WEAR: "WearItem", items.HEAL: "Heal_Item",
               items.AMMO: "Ammo", items.TRASH: "SimpleObject", items.COLD_ARM: "ColdArm",
               items.TROPHY: "Trophy"}


def icon(t):
    root, internal = cat[t]
    return os.path.isfile(os.path.join(world.RES, "classes", ICON_FOLDER[root],
                                       internal, "ico.swf"))


def unservable(t):
    """Why a stall could not show this type, or [] when it can.

    Its window asks ss_get_si for it and must get the frame of its root; the
    name and description ids in that frame must be preloaded, or the player
    is back at the login screen; the name must read as a name and not as
    the internal one; the icon must be there to draw; and it must cost
    something, or the stall gives it away.
    """
    info = items.static_info(t)
    if not info:
        return ["no static info: ss_get_si would go unanswered"]
    cmd, p = info
    root, internal = cat[t]
    why = []
    if cmd != items.SI_COMMAND[root]:
        why.append("command %s" % cmd)
    if not names.known(p["name"]):
        why.append("name id %r not preloaded" % p["name"])
    elif names.text(p["name"]) == internal:
        why.append("shown under its internal name %r" % internal)
    if p["desc"] != "" and not names.known(p["desc"]):
        why.append("desc id %r not preloaded" % p["desc"])
    if not icon(t):
        why.append("no classes/%s/%s/ico.swf" % (ICON_FOLDER[root], internal))
    if p["cost"] <= 0 and p["g_cost"] <= 0:
        why.append("no price")
    if "bg_p_cost" in p:
        why.append("bg_p_cost turns the purchase into one for battleground points")
    if p["sell_num"] < 1:
        why.append("sell_num %r" % p["sell_num"])
    if "max_count" in p and not 1 <= p["sell_num"] <= p["max_count"]:
        why.append("sell_num %r vs max_count %r" % (p["sell_num"], p["max_count"]))
    if root == items.WEAR and p["set_type"] and not names.known(sets.NAME_ID_OFFSET + p["set_type"]):
        why.append("set %r has no name to show" % p["set_type"])
    if root == items.FIRE_ARM:
        rounds = p["comp_array"]
        if not rounds or any(items.root_of(a) != items.AMMO for a in rounds):
            why.append("comp_array %r" % rounds)
        # The tooltip lists the rounds by name, so each is a window of its own.
        why += ["round %d: %s" % (a, w) for a in rounds for w in
                (["no static info"] if not items.static_info(a) else
                 [] if names.known(items.STRING_ID_OFFSET + a) else ["name not preloaded"])]
    return why


def priced_once(t):
    """One currency exactly. Trade.buy buys for gold whenever g_cost is set,
    and the server buys back for cost: an item priced in both is sold for
    one and bought back for the other."""
    p = items.params_of(t)
    return (p["cost"] > 0) != (p["g_cost"] > 0)


def stock(trader):
    return npcs.stock(trader)


# --- the file itself ------------------------------------------------------------
with io.open(npcs.PATH, encoding="utf-8") as fh:
    text = fh.read()
check("data/npcs.json keeps its format: indent 1, UTF-8 as is, a trailing newline",
      text, json.dumps(json.loads(text), ensure_ascii=False, indent=1) + "\n")

# --- 5220: Странник ---------------------------------------------------------------
mt = world.mob_types()
check("5220 is Npc_Trader000047", mt[STRANNIK][1], "Npc_Trader000047")
check("5220 is called Странник", names.text(STRANNIK), "Странник")
check("  ..and the original does not name him over it",
      STRANNIK in names.ORIG_PERSON_NAMES, False)
check("  ..the name is preloaded and the launcher takes it",
      (names.known(STRANNIK), orig_texts.launcher_ok(names.text(STRANNIK))), (True, True))
# The client's own Strangers, ow_Stranger and nz_Stranger, are drawn by the
# same figure: a man in a long desert coat with his face wrapped.
check("  ..and he wears the Strangers' sprite",
      {mt[t][2] for t in (STRANNIK, 1189, 2087)}, {"m24-Sniper"})

# --- the copies ------------------------------------------------------------------
check("Шульц sells what Борис sells", stock(SCHULZ), stock(BORIS))
check("Эрикесэм sells what Морис sells", stock(ERIKESAM), stock(MORIS))
check("Абдула sells what Локсли sells", stock(ABDULA), stock(LOXLEY))
check("  ..on the wire too, the valley's band at the Caravan as at the market",
      (items.stock_for(SCHULZ, PLACE[SCHULZ]), items.stock_for(ABDULA, PLACE[ABDULA])),
      (items.stock_for(BORIS, PLACE[BORIS]), items.stock_for(LOXLEY, PLACE[LOXLEY])))

# --- Хасани: the food and water of Морис's list -----------------------------------
FOOD = ("Med_Pacific_Heal_", "Med_Pacific_Rest_")


def food_or_water(t):
    """Food (Med_Pacific_Heal_) and water (Med_Pacific_Rest_), and the bar's
    Лава-Кола and Шаурма, the one drink and dish outside the Med_ series.
    Not bandages and injectors (Med_Battle_), energy drinks
    (Med_Battle_Rest_) or kits (Med_Pacific_HR_)."""
    internal = cat[t][1]
    return internal.startswith(FOOD) or not internal.startswith("Med_")


check("Хасани sells the food and water of Морис's list, in his order",
      stock(HASANI), [t for t in stock(MORIS) if food_or_water(t)])
check("  ..each one named as food or water, or the bar's",
      sorted({names.text(items.STRING_ID_OFFSET + t).partition("$")[2] for t in stock(HASANI)}),
      ["", "Вода", "Еда"])
check("  ..no bandage, energy drink, injector or kit among them",
      [t for t in stock(HASANI) if cat[t][1].startswith(("Med_Battle_", "Med_Pacific_HR_"))], [])

# --- Бомани and Ро-А-Ким: the rounds of Борис's pistols ------------------------------
# The pistols he sold when the owner decided (2026-09-24) were the pistol line
# of levels 0-6; the valley's band (0-4) keeps the 0-4 of them on his stall
# since 2026-10-10, and his rounds -- СП-10 of the СПС among them -- stay, as
# every stall's rounds did. So the rule reads the whole line, the band's
# pistols of every city (shop_bands: none has numbers above 6).
pistols = [t for t, w in shop_bands.wares().items() if w[0] == "pistols"]
own = [t for t in stock(BORIS) if cat[t][0] == items.AMMO]
chambers = [items.params_of(t)["comp_array"] for t in pistols]


def rounds_rule():
    """Calibre by calibre in the order Борис sells them: his own rounds of
    it, then every other round his pistols chamber of it (comp_array) that
    a stall can sell -- servable, not premium, priced once."""
    out = []
    for r in own:
        if r in out:
            continue
        calibre = next(c for c in chambers if r in c)
        out += [a for a in own if a in calibre and a not in out]
        out += [a for a in calibre if a not in own and a not in out
                and items.root_of(a) == items.AMMO and not items.premium(a)
                and not unservable(a) and priced_once(a)]
    return out


ROUNDS = rounds_rule()
check("Бомани sells the rounds of every pistol of the line Борис sold", stock(BOMANI), ROUNDS)
check("Ро-А-Ким sells the same", stock(RO_A_KIM), ROUNDS)
check("  ..Борис's own rounds all among them", [t for t in own if t not in ROUNDS], [])
check("  ..and each one chambered by one of his pistols",
      [t for t in ROUNDS if not any(t in c for c in chambers)], [])
check("  ..four calibres and the gifted 9 mm, each with its gold rounds: 26",
      len(ROUNDS), 26)

# --- Одноглазый: the cold arms of levels 0-8 ------------------------------------------
KNIFE = re.compile(r"knife_lvl(\d+)_(A|G)")


def knife_level(t):
    return int(KNIFE.fullmatch(cat[t][1]).group(1))


def knives_rule():
    """The client's knife line, knife_lvl<N>_A and _G, for N up to 8: the
    plain and the gold copy of each level, the cheapest first -- as Борис
    sells his pistols. Not the _G_damage / _actionpoint copies, which are a
    gold knife after the blacksmith; not the event, quest and "personal"
    blades (Кастет$Личный, Кортик (Rw), Финка НКВД ...), none of which a
    stall of the old game sold."""
    line = [t for t, (root, name) in cat.items()
            if root == items.COLD_ARM and KNIFE.fullmatch(name) and knife_level(t) <= 8]
    return sorted(line, key=lambda t: (knife_level(t), cat[t][1]))


KNIVES = knives_rule()
check("Одноглазый sells the knife line of the valley's band, 0-4, level by level, plain before"
      " gold (8 until 2026-10-10)", (stock(ONE_EYE), items.stock_for(ONE_EYE, PLACE[ONE_EYE])),
      ([], [t for t in KNIVES if knife_level(t) <= 4]))
# The table the rule gives, pinned: names from the original (texts.xml,
# data/orig_items.json) where it has one, the wiki's for Булыжник.
KNIFE_TABLE = [
    (6228, 0, "Булыжник"),
    (6229, 1, "Шило"),
    (6230, 2, "Заточка"), (6231, 2, "Самодельный Нож (G)"),
    (6235, 4, "Кухонный нож"), (6236, 4, "Кухонный нож (G)"),
    (6240, 6, "Тесак"), (6241, 6, "Тесак (G)"),
    (6245, 8, "Охотничий нож"), (6246, 8, "Охотничий нож (G)"),
]
check("  ..of this table, the line of 0-8, whose numbers are checked below",
      [(t, knife_level(t), names.text(items.STRING_ID_OFFSET + t)) for t in KNIVES], KNIFE_TABLE)

# MeleeWeapon.initialize (MeleeWeapon.as:33-46) reads these ten; a missing
# one is an undefined the client carries into its arithmetic.
MELEE_FIELDS = ("h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max", "max_range",
                "can_aimed", "max_break_abs", "strike_cost", "strike_mod", "strike_time")
MELEE = 1                      # bit 0 of need_skills_m: Ближний бой (sets.SKILLS)
bad = {}
for t in KNIVES:
    cmd, p = items.static_info(t)
    why = []
    if cmd != "ss_si_coldarm":
        why.append("command %s" % cmd)
    missing = [k for k in MELEE_FIELDS if not items._number(p.get(k))]
    if missing:
        why.append("MeleeWeapon fields missing %s" % missing)
    else:
        # getAbsQuality divides by max_break_abs, the price by sell_num;
        # checkDistance strikes nothing at a reach of 0; and combat charges
        # strike_cost a swing, so at 0 the swings never end.
        for k in ("max_break_abs", "sell_num", "max_range", "strike_cost"):
            if p[k] <= 0:
                why.append("%s %r" % (k, p[k]))
        if not 0 < p["h_damage_min"] <= p["h_damage_max"]:
            why.append("damage %r-%r" % (p["h_damage_min"], p["h_damage_max"]))
    if not p["action_map"] & items.ACT_FIRE:
        why.append("action_map %r: no strike" % p["action_map"])
    level = knife_level(t)
    need = ((p.get("need_skills") or [0])[0]
            if p.get("need_skills_m", 0) & MELEE else 0)
    if need != level:
        why.append("needs Ближний бой %r, the line says %d" % (need, level))
    shown = names.text(p["name"])
    if shown.endswith(" (G)") != cat[t][1].endswith("_G"):
        why.append("name %r for %s" % (shown, cat[t][1]))
    if not priced_once(t):
        why.append("priced %r / %r" % (p["cost"], p["g_cost"]))
    if cat[t][1].endswith("_G") and p["cost"]:
        why.append("a gold knife priced in afro")
    if why:
        bad[t] = why
check("Одноглазый: each knife a full ss_si_coldarm, no zero where the client divides, "
      "its level's skill, its name, one price", bad, {})
check("  ..no two knives under one name",
      len({names.text(items.STRING_ID_OFFSET + t) for t in KNIVES}), len(KNIVES))

# Булыжник's article has no price and a strike for 0 AP; the file fills both
# and says so, and the rest stays the wiki's.
manual = items.coldarm_manual()
check("hand-made cold-arm numbers are for cold arms the client has, each saying why",
      [t for t, rec in manual.items() if cat.get(t, (None,))[0] != items.COLD_ARM
       or not rec.get("_source") or not rec.get("_designed")], [])
p = items.params_of(6228)
check("Булыжник: 100 afro, 5 AP, the rest the wiki's",
      (p["cost"], p["g_cost"], p["strike_cost"], p["h_damage_min"], p["h_damage_max"],
       p["max_range"], p["max_break_abs"], p["weight"]),
      (100, 0, 5, 27, 38, 1.7, 3000, 300))
check("  ..and a knife the wiki prices keeps its own numbers",
      (items.params_of(6229)["cost"], items.params_of(6229)["strike_cost"]), (253, 5))

# Every other number is the article's, key by key: what the old tooltip
# showed is what this one shows, and only the holes the file fills differ.
WIKI_KEYS = ("h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max", "max_range",
             "max_break_abs", "strike_cost", "weight", "cost", "g_cost",
             "need_skills_m", "need_skills")
off = {}
for t in KNIVES:
    rec, p = items.wiki().get(t), items.params_of(t)
    if not rec:
        off[t] = "no wiki table"
        continue
    ours = items._holes(rec, manual.get(t, {}))
    diff = {k: (p.get(k), rec[k]) for k in WIKI_KEYS
            if k in rec and k not in ours and p.get(k) != rec[k]}
    if diff:
        off[t] = diff
check("each knife carries its wiki table's numbers, but for the holes the file fills", off, {})
# names.py puts the original's name first, and it spells one of these with a
# capital (Самодельный Нож (G)); otherwise each reads as its article names it.
check("  ..and its article's name",
      [t for t in KNIVES if names.text(items.STRING_ID_OFFSET + t).lower()
       != (items.wiki_names().get(t) or "").lower()], [])

# Why this line and nothing beside it. Every weapon a stall of the old game
# sold off the cold-arm root is on it (data/trader_stock_wiki.json; the
# root's other stall goods are flowers and a bouquet, which need no Ближний
# бой), and the one knife stall there the wiki verified, Однопальцый's in
# Вади-Хальфа (1152), sold its levels 1-8 -- his plain knives and the gold
# Самодельный нож, whose article has only the gold column. The other cold
# arms of these levels are bound or rewards (Кастет$Личный, Костяной нож
# that can be neither traded nor sold, Кортик (Rw)), and no stall had them.
old = {t for goods in items.stock_table().values() for t in goods
       if cat[t][0] == items.COLD_ARM and items.params_of(t).get("need_skills_m", 0) & MELEE}
check("every cold weapon a stall of the old game sold is on the knife line",
      sorted(t for t in old if not KNIFE.fullmatch(cat[t][1])), [])
wadi = [t for t in items.stock_table().get(1152, []) if cat[t][0] == items.COLD_ARM]
check("  ..and Однопальцый's in Вади-Хальфа was its levels 1-8, all of it Одноглазый's",
      (sorted(t for t in wadi if t not in KNIVES), sorted({knife_level(t) for t in wadi})),
      ([], [1, 2, 4, 6, 8]))

# --- 5208: nothing -----------------------------------------------------------------
check("5208 sells nothing, as a decision and not for want of one",
      (stock(NAMELESS), items.stock_for(NAMELESS)), ([], []))

# --- 1187: Барыга Сет, his wiki page's list ---------------------------------------------
# His page lists sixteen rows under «Торговля»; the linker never bound the
# page to his type (data/trader_stock_wiki.json, "unbound"), so his stall
# stood empty. Each row goes to the type a stall of ours sells under that
# title, in the page's order:
#   * a clothing article to the (A) piece of the owner's sets whose numbers
#     are that article's own column (data/sets.json, the member's _wiki):
#     the Колонист's five, «Каска строителя» among them as the helmet the
#     owner calls «Гоглы с фильтром» by its icon;
#   * «9мм НАТО», listed twice, to the two rows of the calibre Борис's page
#     spells out, (OLD) КС and СТ: the valley's other stall, whose page
#     names the column where Сет's does not;
#   * anything else to what the linker ties the article to, its (A) copies.
# What a stall cannot sell then drops out: premium, or anything
# unservable() refuses. The articles say Сет sold their (G) column; his
# stall, like the rest of the valley's, is priced in afro.
with io.open(os.path.join(os.path.dirname(HERE), "data", "wiki", "pages.json"),
             encoding="utf-8") as fh:
    PAGES = json.load(fh)


def trade_list(page):
    """The titles under a page's «===Торговля===», in order, repeats kept."""
    text = PAGES[page]["wikitext"].split("===Торговля===", 1)[1]
    text = re.split(r"\n==", text, maxsplit=1)[0]
    return re.findall(r"^\*\s*\[\[([^\]|]+)", text, re.M)


with io.open(sets.PATH, encoding="utf-8") as fh:
    _set_doc = json.load(fh)
PIECE_OF = {}
for _s in _set_doc["sets"].values():
    for _m in _s["members"].values():
        if _m.get("_wiki"):
            PIECE_OF.setdefault(_m["_wiki"], []).append(_m["type"])


def seth_rule():
    """(the stall, the rows it leaves out)."""
    nato = iter([items.resolve_stock_title(t) for t in trade_list("Борис")
                 if t.startswith("9мм НАТО")])
    out, left = [], []
    for title in trade_list("Барыга Сет"):
        if title == "9мм НАТО":
            ids = next(nato)
        elif "%s (A column)" % title in PIECE_OF:
            ids = PIECE_OF["%s (A column)" % title]
        else:
            ids = items.resolve_title(title)
        ids = [t for t in ids if t in cat and not items.premium(t) and not unservable(t)]
        if ids:
            out += ids
        else:
            left.append(title)
    return out, left


SETH_ROWS = trade_list("Барыга Сет")
check("Сет's page: sixteen rows, «9мм НАТО» twice",
      SETH_ROWS, ["Walther P99", "9мм НАТО", "9мм НАТО", "Рубашка", "Водолазка", "Джинсы",
                  "Брезентовые штаны", "Старые ботинки", "Берцы", "Каска строителя",
                  "Железная каска", "Кусковая броня", "Рессорная броня", "OP 1",
                  "Альфа-Реагент I", "Омега-Реагент I"])
check("  ..and Борис's two rows of the calibre are КС and СТ",
      [items.resolve_stock_title(t) for t in trade_list("Борис") if t.startswith("9мм НАТО")],
      [[items.AMMO_9MM[0]], [items.AMMO_9MM[1]]])
check("  ..each clothing article the column of one piece of the owner's sets",
      {t: PIECE_OF.get("%s (A column)" % t) for t in ("Рубашка", "Джинсы", "Старые ботинки",
                                                     "Каска строителя", "Кусковая броня")},
      {"Рубашка": [10180], "Джинсы": [10182], "Старые ботинки": [10183],
       "Каска строителя": [10179], "Кусковая броня": [10181]})
SETH_STALL, SETH_LEFT = seth_rule()
check("Барыга Сет sells his page's list, in its order, as far as a stall can show it",
      stock(SETH), SETH_STALL)
check("  ..which is this table",
      [(t, names.text(items.STRING_ID_OFFSET + t)) for t in stock(SETH) or []],
      [(25636, "Walther P99$Пистолет"), (6092, "9мм НАТО $КС"), (6104, "9мм НАТО $СТ"),
       (10180, "Рубашка"), (10182, "Джинсы"), (10183, "Старые ботинки"),
       (10179, "Гоглы с фильтром"), (10181, "Кусковая броня"),
       (4181, "Альфа-реагент I"), (3208, "Омега-реагент I")])
check("  ..leaving out the five of «Старые вещи» and OP 1",
      SETH_LEFT, ["Водолазка", "Брезентовые штаны", "Берцы", "Железная каска",
                  "Рессорная броня", "OP 1"])


def shown(t):
    """The name a type reaches the player under, its modification dropped."""
    return re.sub(r"\s*\(мод\d+\)$", "", names.text(items.STRING_ID_OFFSET + t)).lower()


_left = {t.lower() for t in SETH_LEFT}
_named = sorted(t for t in cat if shown(t) in _left)
# SSEmulator.getIcon draws a thing from classes/<folder>/<internal name>/ico.swf,
# and not one of the original's mob copies (the _Mob_M_ series, its [M] rows)
# has that folder: a stall would hold five empty squares.
check("  ..because the client has «Старые вещи» only as the original's mob copies"
      " (_Mob_M_, every modification), none of which it can draw",
      (len(_named), sorted({(cat[t][0], "_Mob_M_" in cat[t][1], icon(t)) for t in _named})),
      (55, [(items.WEAR, True, False)]))
check("  ..and has nothing called OP 1, which has no article either",
      ([t for t in cat if shown(t) == "op 1"], "OP 1" in PAGES), ([], False))

# --- every list ----------------------------------------------------------------------
LISTS = {SCHULZ: "Шульц", ERIKESAM: "Эрикесэм", ABDULA: "Абдула", HASANI: "Хасани",
         BOMANI: "Бомани", RO_A_KIM: "Ро-А-Ким", ONE_EYE: "Одноглазый",
         SETH: "Барыга Сет"}
LISTS.update({BORIS: "Борис", LOXLEY: "Локсли"})
for trader, who in sorted(LISTS.items()):
    goods = stock(trader) or []
    wire = items.stock_for(trader, PLACE[trader])
    kinds = shop_bands.kinds(trader)
    band = shop_bands.goods(kinds, 0, 4) if kinds else []
    check("%s (%d): %d types, on the wire as written (a seller's band first)" % (
        who, trader, len(wire)), wire, band + goods)
    check("  ..none twice", len(set(wire)), len(wire))
    check("  ..none premium", [t for t in wire if items.premium(t)], [])
    check("  ..every one servable",
          {t: w for t, w in ((t, unservable(t)) for t in wire) if w}, {})
# What this change chose itself, beyond the owner's own lists, is priced in
# one currency. (Борис's 6188, "9мм дареные", carries both from its wiki
# page -- 1 afro and 0.01 G a round -- and his copies carry it as he does.)
chosen = KNIVES + [t for t in ROUNDS if t not in own]
check("the knives and the rounds beyond Борис's own are each priced once",
      [t for t in chosen if not priced_once(t)], [])
check("Сет's goods are each priced once, in afro",
      [t for t in SETH_STALL if not priced_once(t) or items.params_of(t)["g_cost"]], [])

print()
print("Одноглазый (5222):")
for t in KNIVES:
    p = items.params_of(t)
    print("  lvl %d  %5d  %-22s %4s-%-4s AP %-2s  %s" % (
        knife_level(t), t, names.text(p["name"]), p["h_damage_min"], p["h_damage_max"],
        p["strike_cost"], "%d afro" % p["cost"] if p["cost"] else "%.2f G" % (p["g_cost"] / 100.0)))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("shops OK")
