"""Чёрный Ловелас[12] for afro and for gold, at Гали's stall.

The owner's order of 2026-10-13: «поставь ловеласа у Гали и за афро и за
голд». The set was the original's quest series Bs_U_LVL_12, quest types
only (_Q_mod00..mod10), and one type has one currency: the client buys
anything with a g_cost for gold (Trade.buy). So its A is the quest pieces,
priced in afro, and its G five types of our own (data/own_items.json,
own_items.py), which the release's objects.xml carries with the quest
pieces' pictures (client/build.py; client/test_client.py has the release).

In process:
  1. the types: the G is 60000-60004 in the server's catalogue, root and
     slot as the client reads them, each the copy of its quest piece; a
     table of our own types that would clash with the original's is refused;
  2. the prices by the rule the afro ones were designed by (data/sets.json
     _meta): t = 2/3 between Пустынник[10] and Спецназ[13], piece by piece,
     afro to whole thousands and gold to the same grain, 1 000 afro = 0.25 G
     at the wiki's 4 000 : 1 -- which is the A's price at that rate; the G's
     numbers between the neighbours' G pieces, as the A's between their A;
  3. the names in the table (names.ALL), as the ladder's A and G read;
  4. the sets: five A one set, five G one set with the same figure, each
     with a bonus designed between its neighbours' columns (the wiki page's
     is Штурм-М[15]'s, an event set's never sold), and a mix of A and G two
     sets -- as every rung's A and G, which the original named as two sets
     ([A] and [G] rows of texts.xml);
  5. Гали's stall at Портовый рынок Абри (187): the band's sets, A then G,
     helm to boots, Чёрный Ловелас last.
Then on the wire (server.Session, in process): Гали's window is that stall,
each gold piece is bought for gold and refused for afro, each afro piece for
afro and refused for gold; then the character puts on two afro pieces and
three gold ones, and its card carries what the two sets add, then five gold
ones and the five-piece bonus.

    LAVA_RES=.../lava/res python3 server/test_lovelace.py
"""
import asyncio
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB = os.path.join(tempfile.mkdtemp(), "lovelace.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import own_items  # noqa: E402
import sets  # noqa: E402
import setcraft  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

A, G = 11120, 60000                  # the set_types: the quest row, our first piece
DESERT_A, DESERT_G = 11182, 11184    # Пустынник[10]
SPEC_A, SPEC_G = 11206, 11208        # Спецназ[13]
GALI, PORT = 1166, 187               # Гали «Торговец комплектами», Портовый рынок Абри
SLOTS = sets.SLOTS
A_TYPES = [11721, 11722, 11723, 11724, 11725]
G_TYPES = [60000, 60001, 60002, 60003, 60004]
A_PRICES = [42000, 25000, 50000, 33000, 17000]     # afro
G_PRICES = [1050, 625, 1250, 825, 425]             # hundredths of an ounce
WORDS = ["Шлем", "Жилет", "Броня", "Штанишки", "Ботинки"]
cat = items.catalogue()
with open(sets.PATH, encoding="utf-8") as fh:
    RAW = json.load(fh)["sets"]


def half_up(x):
    return int(math.floor(x + 0.5 + 1e-9))


def members(st):
    return [sets.SETS[st]["members"][s] for s in SLOTS]


def price(t):
    p = items.params_of(t)
    return p["cost"], p["g_cost"]


# --- 1. the types ------------------------------------------------------------------------
print("the types")
check("its A: the original's quest pieces, Bs_U_LVL_12 _Q_mod00, in the set of its [Q] row",
      (members(A), [cat[t][1] for t in A_TYPES], sets.SETS[A]["variant"]),
      (A_TYPES, ["%s_Bs_U_LVL_12_Q_mod00" % s for s in SLOTS], "A"))
check("its G: five types of our own in the server's catalogue, clothing, named as the G of"
      " the series, keyed by the first of them",
      (members(G), [cat[t] for t in G_TYPES], [items.own(t) for t in G_TYPES],
       sets.SETS[G]["variant"]),
      (G_TYPES, [(items.WEAR, "%s_Bs_U_LVL_12_G_mod00" % s) for s in SLOTS], [True] * 5, "G"))
check("  ..the original has none of them: its last type is 50 035, and no row named so",
      ([t for t in G_TYPES if t <= 50035],
       [t for t, (_r, n) in cat.items() if "Bs_U_LVL_12_G" in n and not items.own(t)]), ([], []))
check("  ..each the copy of its quest piece: its root and its picture (data/own_items.json)",
      [(own_items.load()[t]["like"], own_items.icon_path(*cat[t])) for t in G_TYPES],
      [(a, "classes/WearItem/%s_Bs_U_LVL_12_G_mod00/ico.swf" % s) for a, s in zip(A_TYPES, SLOTS)])
check("  ..each in its slot, as the client puts it",
      [items.static_info(t)[1]["slot_type"] for t in G_TYPES],
      [items.SLOT_HEAD, items.SLOT_CAMO, items.SLOT_ARMOR, items.SLOT_LEGS, items.SLOT_BOOTS])


def refused(doc, original=None):
    try:
        own_items.rows(original or cat, own_items.parse(doc))
    except own_items.Refused as e:
        return str(e)
    return None


ok = {"60000": {"name": "helm_Bs_U_LVL_12_G_mod00", "like": 11721}}
check("a table of our own types is refused where it would clash with the original's",
      [bool(refused({"items": d})) for d in (
          ok,
          {"11722": {"name": "helm_x", "like": 11721}},          # a type of the original's range
          {"65536": {"name": "helm_x", "like": 11721}},          # past an oid's four hex digits
          {"60000": {"name": "helm_Bs_U_LVL_12_Q_mod00", "like": 11721}},   # the original's name
          {"60000": {"name": "helm x", "like": 11721}},          # no folder name
          {"60000": {"name": "helm_x", "like": 4242424}},        # like no type
          {"60000": {"name": "helm_x", "like": 11721},
           "60001": {"name": "HELM_X", "like": 11722}},          # one name twice
          {"60001": {"name": "helm_x", "like": 60000}})],        # like one of ours
      [False, True, True, True, True, True, True, True])
# The objects.xml of a client the launcher installed is the release's: our
# rows in it, as that release had them -- this one's, or an older one's. The
# type taken out is 60099, none of ours (60005-60009 are Тёмное Эхо's G since
# 2026-10-14).
STALE = dict(cat)
STALE.update({60000: (1, "helm_renamed_G_mod00"), 60099: (1, "helm_dropped_G_mod00")})
check("  ..and a release's objects.xml read as the original is not: its rows in our range are"
      " ours, as they are now or as an older release had them (a rename, a type taken out)",
      (refused({"items": ok}, dict(cat)), refused({"items": ok}, STALE),
       own_items.rows(STALE, own_items.parse({"items": ok}))),
      (None, None, {60000: (1, "helm_Bs_U_LVL_12_G_mod00")}))
HEAD = (b"<?xml version='1.0'?>\n<data>\n<object type_id=\"11721\" "
        b"root_type_id= \"1\" name=\"helm_Bs_U_LVL_12_Q_mod00\" />\n")
MINE = {60000: (1, "helm_Bs_U_LVL_12_G_mod00")}
xml = own_items.objects_xml(HEAD + b"</data>", MINE)
stale_xml = (HEAD + b'<object type_id="60000" root_type_id= "1" name="helm_renamed_G_mod00" />\n'
             b'<object type_id="60099" root_type_id= "1" name="helm_dropped_G_mod00" />\n</data>')
check("  ..the row the release writes, in the original's format, once however often it is laid,"
      " and the same file out of a release's with stale rows of ours",
      (xml, own_items.objects_xml(xml, MINE) == xml, own_items.objects_xml(stale_xml, MINE) == xml),
      (HEAD + b'<object type_id="60000" root_type_id= "1" name="helm_Bs_U_LVL_12_G_mod00" />\n'
       b"</data>", True, True))
with open(os.path.join(world.RES, "database", "objects.xml"), "rb") as fh:
    ORIGINAL = own_items.objects_xml(fh.read(), {})       # the original's, whatever the res
OLDER = ORIGINAL.replace(b"</data>", b'<object type_id="60000" root_type_id= "1" name="helm_ren'
                         b'amed_G_mod00" />\n<object type_id="60099" root_type_id= "1" name="hel'
                         b'm_dropped_G_mod00" />\n</data>')
_read, _was = world._read, items._CATALOGUE
try:
    world._read = lambda _path: OLDER.decode("ascii")
    items._CATALOGUE = None
    seen = items.catalogue()
except own_items.Refused as e:
    seen = {"refused": str(e)}
finally:
    world._read, items._CATALOGUE = _read, _was
check("  ..the server reads an older release's objects.xml as it reads the original:"
      " items.catalogue() has the current rows of ours and none of the stale",
      (seen == cat, seen.get(60000), 60099 in seen), (True, (1, "helm_Bs_U_LVL_12_G_mod00"), False))
check("  ..and the release made out of it is the release made out of the original",
      own_items.release_xml(OLDER) == own_items.release_xml(ORIGINAL) != ORIGINAL, True)

# The local stand's /res/ (bootstrap_http, LAVA_HTTP_RES=1: run.sh, the
# suites) serves the release's layer of ours as the release has it: without
# it a branch tried against the original's res shows the gold pieces as
# empty cells (SBase.getItem(60000) undefined). Its handler, in process.
import bootstrap_http  # noqa: E402


def served(path):
    h = bootstrap_http.Handler.__new__(bootstrap_http.Handler)
    got = []
    h._send = lambda body, ctype="", code=200: got.append((code, body))
    bootstrap_http.Handler._resource(h, path)
    return got[0]


code, body = served("/res/database/objects.xml")
check("the stand's /res/database/objects.xml is the release's: a row for each of ours, the"
      " original's rows as they are", (code, body == own_items.release_xml(ORIGINAL)), (200, True))
ICONS = own_items.icons(cat)
if all(os.path.isfile(os.path.join(world.RES, *p.split("/"))) for p in ICONS.values()):
    pictures = {}
    for mine, like in sorted(ICONS.items()):
        with open(os.path.join(world.RES, *like.split("/")), "rb") as fh:
            pictures[mine] = served("/res/" + mine) == (200, fh.read())
    check("  ..and each one's icon, its quest piece's picture byte for byte, at the path the client"
          " builds from that row (Тёмное Эхо's G among them since 2026-10-14)", pictures,
          {own_items.icon_path(*cat[t]): True for t in own_items.load()})
else:
    print("  --  no quest pieces' icons in %s; the stand's icons are not checked" % world.RES)

# --- 2. the prices -----------------------------------------------------------------------
print()
print("the prices")
T = 2 / 3.0          # (12 - 10) / (13 - 10)
check("the afro: 42 000, 25 000, 50 000, 33 000, 17 000 -- t = 2/3 between Пустынник and"
      " Спецназ, to whole thousands, as the rule designed them",
      ([price(t) for t in A_TYPES],
       [half_up((price(lo)[0] + (price(hi)[0] - price(lo)[0]) * T) / 1000.0) * 1000
        for lo, hi in zip(members(DESERT_A), members(SPEC_A))]),
      ([(p, 0) for p in A_PRICES], A_PRICES))
check("  ..between their neighbours: Пустынник 25 000 .. 10 000 and Спецназ 50 000 .. 20 000",
      ([price(t)[0] for t in members(DESERT_A)], [price(t)[0] for t in members(SPEC_A)]),
      ([25000, 15000, 30000, 20000, 10000], [50000, 30000, 60000, 40000, 20000]))
raw_g = [price(lo)[1] + (price(hi)[1] - price(lo)[1]) * T
         for lo, hi in zip(members(DESERT_G), members(SPEC_G))]
check("the gold: t = 2/3 between Пустынник (G) and Спецназ (G) -- 10.42, 6.25, 12.50, 8.33,"
      " 4.17 G -- to the grain of the afro, 1 000 afro = 0.25 G: 10.50, 6.25, 12.50, 8.25, 4.25",
      ([round(x) for x in raw_g], [half_up(x / 25.0) * 25 for x in raw_g], [price(t) for t in G_TYPES]),
      ([1042, 625, 1250, 833, 417], G_PRICES, [(0, p) for p in G_PRICES]))
check("  ..which is the A's price at the wiki's 4 000 afro = 1 G, the rule of every designed"
      " rung's G (Дредноут, Паладин)", [a // 40 for a in A_PRICES], G_PRICES)
check("  ..the set: 167 000 afro or 41.75 G, between Пустынник's 100 000 / 25 G and"
      " Спецназ's 200 000 / 50 G",
      (sum(A_PRICES), sum(G_PRICES), sum(price(t)[0] for t in members(DESERT_A)),
       sum(price(t)[1] for t in members(DESERT_G)), sum(price(t)[0] for t in members(SPEC_A)),
       sum(price(t)[1] for t in members(SPEC_G))),
      (167000, 4175, 100000, 2500, 200000, 5000))
NUMS = ("armor_class", "max_break_abs", "weight", "bonus_hp", "bonus_st", "bonus_od", "bonus_cp",
        "bonus_ce")


def between(lo, hi, key):
    a, b = items.params_of(lo).get(key, 0), items.params_of(hi).get(key, 0)
    return half_up(a + (b - a) * T)


check("the numbers: t = 2/3 piece by piece -- armour, wear, weight, what it adds -- the A between"
      " Пустынник's and Спецназ's A pieces, the G between their (G) ones",
      [[items.params_of(t).get(k, 0) for k in NUMS] for t in A_TYPES + G_TYPES],
      [[between(lo, hi, k) for k in NUMS] for lo, hi in zip(members(DESERT_A), members(SPEC_A))]
      + [[between(lo, hi, k) for k in NUMS] for lo, hi in zip(members(DESERT_G), members(SPEC_G))])
check("  ..so each gold piece is the stronger, as on every rung: armour, health, stamina, action"
      " points", [g for a, g in zip(A_TYPES, G_TYPES)
                  if any(items.params_of(g).get(k, 0) <= items.params_of(a).get(k, 0)
                         for k in ("armor_class", "bonus_hp", "bonus_st", "bonus_od"))], [])
check("  ..and asks what the A asks", [g for a, g in zip(A_TYPES, G_TYPES)
                                       if any(items.params_of(a).get(k) != items.params_of(g).get(k)
                                              for k in ("need_attribs_m", "need_attribs",
                                                        "need_skills_m", "need_skills"))], [])
check("  ..the A exchanged, the G not, as every rung's; neither premium nor a quest's",
      [(items.params_of(t)["exchang"], items.params_of(t)["premium"], items.params_of(t)["quest"])
       for t in (A_TYPES[0], G_TYPES[0])], [(1, 0, 0), (0, 0, 0)])
check("  ..Стрельба 12 and Телосложение 13 asked, the level the band reads them at",
      sorted({(inventory.item_level(t), shop_bands.level_of(t)) for t in A_TYPES + G_TYPES}),
      [(12, 12)])

# --- 3. the names ------------------------------------------------------------------------
print()
print("the names")
check("in the table under the item ids: the A plain, the G with (G), as «Шлем пустынника» and"
      " «Шлем пустынника (G)»",
      ([names.text(items.STRING_ID_OFFSET + t) for t in A_TYPES + G_TYPES],
       [names.text(items.STRING_ID_OFFSET + t) for t in (10629, 10649)]),
      (["%s Чёрного Ловеласа" % w for w in WORDS] + ["%s Чёрного Ловеласа (G)" % w for w in WORDS],
       ["Шлем пустынника", "Шлем пустынника (G)"]))
check("  ..over the original's «(Q)» and the internal name",
      (orig_texts.item_names()[11721], 60000 in orig_texts.item_names()),
      ("Шлем Чёрного Ловеласа (Q)", False))
check("  ..and the file writes them as the ladder does: [12][A], [12][G]",
      [RAW[str(st)]["members"]["helm"]["name"] for st in (A, G)],
      ["Шлем Чёрного Ловеласа[12][A]", "Шлем Чёрного Ловеласа[12][G]"])
check("each described by its quest piece's words, the gold one under its own id",
      [names.text(items.static_info(t)[1]["desc"]) for t in (A_TYPES[0], G_TYPES[0])],
      ["Встроен рентген сканер обнажающий натуру противника. Без смсок!"] * 2)
check("the sets: «Чёрный Ловелас» and «Чёрный Ловелас (G)», one description",
      [names.text(sets.NAME_ID_OFFSET + st) for st in (A, G)] + [
          names.text(sets.DESC_ID_OFFSET + G) == names.text(sets.DESC_ID_OFFSET + A)],
      ["Чёрный Ловелас", "Чёрный Ловелас (G)", True])
ids = [items.STRING_ID_OFFSET + t for t in A_TYPES + G_TYPES] \
    + [items.static_info(t)[1]["desc"] for t in A_TYPES + G_TYPES] \
    + [sets.NAME_ID_OFFSET + st for st in (A, G)] + [sets.DESC_ID_OFFSET + st for st in (A, G)]
check("every one of those ids in the preload, its text one the launcher takes",
      [i for i in ids if not names.known(i) or not orig_texts.launcher_ok(names.text(i))], [])

# --- 4. the sets -------------------------------------------------------------------------
print()
print("the sets")


def bonus_of(st, n):
    """What n pieces of a set add by the file's own columns, K by K up to n."""
    out = sets.zero()
    for k, line in RAW[str(st)]["bonus"].items():
        if int(k) > n:
            continue
        one = sets._bonus("t", line)
        for key in sets.SCALARS:
            out[key] += one[key]
        for kind, _t in sets.LISTS:
            out[kind] = [a + b for a, b in zip(out[kind], one[kind])]
    return out


def plus(*bs):
    out = sets.zero()
    for b in bs:
        for key in sets.SCALARS:
            out[key] += b[key]
        for kind, _t in sets.LISTS:
            out[kind] = [a + c for a, c in zip(out[kind], b[kind])]
    return out


def column(st):
    return {int(k): line for k, line in RAW[str(st)]["bonus"].items()}


def between_columns(lo, hi):
    """K by K and bonus by bonus, t = 2/3, half up, 0 left out."""
    out = {}
    for k in sorted(set(column(lo)) | set(column(hi))):
        a, b = column(lo).get(k, {}), column(hi).get(k, {})
        line = {key: half_up(a.get(key, 0) + (b.get(key, 0) - a.get(key, 0)) * T)
                for key in list(a) + [x for x in b if x not in a]}
        line = {key: x for key, x in line.items() if x}
        if line:
            out[k] = line
    return out


check("the afro set's bonus: K by K between Пустынник's and Спецназ's columns, t = 2/3; the gold"
      " set's between their (G) columns -- designed like the pieces, a rung's power",
      (column(A), column(G)), (between_columns(DESERT_A, SPEC_A), between_columns(DESERT_G, SPEC_G)))
check("  ..at three pieces +10 stamina, +4 anti-crit, Ловкость 1 (gold: +23, +4, Ловкость 2);"
      " at five +38 stamina, +4 action points, +8 crit, Сила 1, Телосложение 2, Восприятие 1"
      " (gold: +47, +4, +10, the same three)", [column(st)[k] for st in (A, G) for k in (3, 5)],
      [{"st": 10, "ce": 4, "Ловкость": 1},
       {"st": 38, "od": 4, "cp": 8, "Сила": 1, "Телосложение": 2, "Восприятие": 1},
       {"st": 23, "ce": 4, "Ловкость": 2},
       {"st": 47, "od": 4, "cp": 10, "Сила": 1, "Телосложение": 2, "Восприятие": 1}])
check("  ..the wiki page's own column, Штурм-М[15]'s A word for word (+20 action points at three),"
      " serves neither", [column(st) == column(11002) for st in (A, G)]
      + [column(st)[3].get("od", 0) for st in (A, G)], [False, False, 0, 0])
check("  ..the same figure, 111", (sets.frame(A)["res"], sets.frame(G)["res"]),
      (111, 111))
check("five A are one set, five G one set, each with its five-piece bonus",
      (sets.pieces(A_TYPES), sets.pieces(G_TYPES), sets.bonuses(A_TYPES), sets.bonuses(G_TYPES)),
      ({A: 5}, {G: 5}, bonus_of(A, 5), bonus_of(G, 5)))
mix = A_TYPES[:2] + G_TYPES[2:]
check("a mix, two A and three G, is two sets: two pieces of the one and three of the other",
      (sets.pieces(mix), sets.bonuses(mix)), ({A: 2, G: 3}, plus(bonus_of(A, 2), bonus_of(G, 3))))
desert = members(DESERT_A)[:2] + members(DESERT_G)[2:]
check("  ..as every rung's A and G (the original's [A] and [G] rows): two of Пустынник and"
      " three of Пустынник (G)", sets.pieces(desert), {DESERT_A: 2, DESERT_G: 3})
check("the figure: res 111 for five of either, the wearer's own for a mix, as for Пустынник",
      (sets.look(A_TYPES), sets.look(G_TYPES), sets.look(mix), sets.look(desert)), (111, 111, 0, 0))
DARK_ECHO = list(range(36056, 36061)) + list(range(60005, 60010))   # sold since 2026-10-14
check("not reworked, as while it was a quest set: its A's mods have no pictures, its G has"
      " none (setcraft.NOT_REWORKED); every other rung of the ladder is, but Тёмное Эхо[17],"
      " sold the same way since 2026-10-14 (server/test_abuhamed_trade.py)",
      (sorted(setcraft.NOT_REWORKED), [t for t in A_TYPES + G_TYPES if t in setcraft.CHAINS],
       setcraft.MISSING), (sorted(A_TYPES + G_TYPES + DARK_ECHO), [], []))

# --- 5. Гали's stall ---------------------------------------------------------------------
print()
print("Гали's stall")
stall = items.stock_for(GALI, PORT)
check("Гали at Портовый рынок Абри: Абри's band 8-12, Налетчик, Пустынник and Чёрный Ловелас,"
      " each A then G, helm to boots",
      stall, members(11185) + members(11187) + members(DESERT_A) + members(DESERT_G)
      + A_TYPES + G_TYPES)
check("  ..the last ten: the five afro pieces for afro, then the five gold ones for gold",
      [price(t) for t in stall[-10:]], [(p, 0) for p in A_PRICES] + [(0, p) for p in G_PRICES])
check("  ..the city's band says so on its own (shop_bands.wares): kind, level, slot, currency",
      [shop_bands.ware(t) for t in A_TYPES + G_TYPES],
      [("sets", 12, i, 0) for i in range(5)] + [("sets", 12, i, 1) for i in range(5)])
check("Тёмное Эхо[17], still a quest set, is on no stall of any city",
      sorted({t for st in RAW if RAW[st]["variant"] == "Q" for t in members(int(st))}
             & set(shop_bands.wares())), [])

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("lovelace", "secret")
_store.close()
CRED = accounts.credential("lovelace", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.read = 0

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

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


def of(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def purse(sess):
    return sess.char.afro, sess.char.gold


def rows(sess):
    return server.STORE.items_of(sess.char_id)


def bag(sess):
    return sorted(r["type_id"] for r in rows(sess))


def buy(sess, index, code):
    """One purchase by the window's index: (acks, what came, afro, gold spent)."""
    before, had = purse(sess), bag(sess)
    got = run(sess, "ss_upd;s_status=%d;obj=x%x;param=1;" % (code, index))
    now = bag(sess)
    came = [t for t in set(now) if now.count(t) > had.count(t)]
    return acks(got), came, before[0] - purse(sess)[0], before[1] - purse(sess)[1]


SLOT_OF = dict(zip(SLOTS, (inventory.HEAD, inventory.CAMO, inventory.ARMOR, inventory.LEGS,
                           inventory.BOOTS)))


def wear(sess, type_id, slot):
    r = next(r for r in rows(sess) if r["type_id"] == type_id)
    got = run(sess, "ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(r), SLOT_OF[slot], r["slot"]))
    return acks(got)


def gear(sess):
    ch = sess.char
    return dict(hp=ch.bonus_hp, st=ch.bonus_st, od=ch.bonus_od, cp=ch.bonus_cp, ce=ch.bonus_ce,
                attribs=list(ch.bonus_attribs))


def want_gear(worn):
    """The pieces' own bonus_* and the sets' columns (bonus_of), by hand."""
    own = sets.zero()
    for t in worn:
        p = items.params_of(t)
        for key in sets.SCALARS:
            own[key] += p.get("bonus_" + key, 0)
    total = plus(own, *[bonus_of(st, n) for st, n in sets.pieces(worn).items()])
    return dict(hp=total["hp"], st=total["st"], od=total["od"], cp=total["cp"], ce=total["ce"],
                attribs=total["attribs"])


async def main():
    sess = server.Session(Writer(), "lovelace")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Ловелас@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 300000 10000@;group=0;")
    run(sess, "userMsg;entry=@/skill 1 12@;group=0;")
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % PORT)
    run(sess, "lenter;accept=1;")
    npc = {n.type_id: eid for eid, n in sess.room.npcs.items()}.get(GALI)
    check("Гали stands at Портовый рынок Абри", npc is not None, True)
    info = of(run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc), "userInfo_Trader")
    window = list(info[0]["type_list"]) if info else []
    check("  ..his window is his stall there, the thirty", (window == stall, len(window)), (True, 30))
    si = {p["type"]: p for t in (A_TYPES[0], G_TYPES[0])
          for p in of(run(sess, "ss_get_si;type=%d;" % t), "ss_si_wear")}
    check("ss_get_si: the gold helmet's frame, a piece of the set 60000 for 10.50 ounces alone,"
          " the afro one's of 11120 for 42 000",
          [(si[t]["set_type"], si[t]["cost"], si[t]["g_cost"], names.known(si[t]["name"]))
           for t in (A_TYPES[0], G_TYPES[0])], [(A, 42000, 0, True), (G, 0, 1050, True)])
    s_si = {p["type"]: p for st in (A, G) for p in of(run(sess, "ss_get_s_si;type=%d;" % st),
                                                       "ss_si_set")}
    check("ss_get_s_si: the two sets' frames, figure 111", (s_si[A]["res"], s_si[G]["res"],
                                                             s_si[G]["name"]), (111, 111, 7060000))
    check("the stall opens: one ack", acks(run(sess, "ss_create;s_type=1;target=%d;" % npc)), [0])
    at = {t: window.index(t) for t in A_TYPES + G_TYPES}
    start = purse(sess)
    check("each gold piece for afro: refused, nothing taken, nothing given",
          [buy(sess, at[t], inventory.UPD_BUY) for t in G_TYPES],
          [([inventory.RES_REFUSED], [], 0, 0)] * 5)
    check("each afro piece for gold: refused, nothing taken, nothing given",
          [buy(sess, at[t], inventory.UPD_BUY_GOLD) for t in A_TYPES],
          [([inventory.RES_REFUSED], [], 0, 0)] * 5)
    check("each gold piece for gold: one ack, the piece, its price in hundredths of an ounce,"
          " no afro", [buy(sess, at[t], inventory.UPD_BUY_GOLD) for t in G_TYPES],
          [([0], [t], 0, p) for t, p in zip(G_TYPES, G_PRICES)])
    check("each afro piece for afro: one ack, the piece, its price, no gold",
          [buy(sess, at[t], inventory.UPD_BUY) for t in A_TYPES],
          [([0], [t], p, 0) for t, p in zip(A_TYPES, A_PRICES)])
    check("  ..the purse: 167 000 afro and 41.75 ounces less, the set's two prices",
          (start[0] - purse(sess)[0], start[1] - purse(sess)[1]), (167000, 4175))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")

    check("the character, Стрельба 12, puts on the afro helmet and vest and the gold armour,"
          " trousers and boots: accepted, each",
          [wear(sess, t, s) for t, s in zip(A_TYPES[:2] + G_TYPES[2:], SLOTS)], [[0]] * 5)
    check("  ..its card: the pieces' own and two sets' -- two of the afro, three of the gold",
          gear(sess), want_gear(A_TYPES[:2] + G_TYPES[2:]))
    check("  ..which is more than five pieces of no set would give: +29 health, +46 stamina,"
          " +4 anti-crit and Ловкость 2 -- no action points (Штурм-М's column gave 20)",
          ([gear(sess)[k] - sum(items.params_of(t)["bonus_" + k] for t in mix)
            for k in ("hp", "st", "od", "cp", "ce")], gear(sess)["attribs"]),
          ([29, 46, 0, 0, 4], [0, 2, 0, 0, 0]))
    check("the gold helmet and vest in their place: accepted",
          [wear(sess, t, s) for t, s in zip(G_TYPES[:2], SLOTS)], [[0], [0]])
    check("  ..five of the gold set: the five-piece bonus on the card",
          gear(sess), want_gear(G_TYPES))
    check("  ..Сила 2, Ловкость 2, Телосложение 2, Восприятие 1 of it",
          gear(sess)["attribs"], [2, 2, 2, 1, 0])
    worn = {r["slot"]: r["type_id"] for r in rows(sess) if r["slot"] in inventory.SET_SLOTS}
    check("  ..and the figure the set draws: 111", sets.look([worn.get(s) for s in inventory.SET_SLOTS]),
          111)


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("the wire broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("lovelace OK")
