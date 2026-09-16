"""The wiki laid over the item catalogue: numbers, names, stocks, and the
invariants the client's arithmetic rests on.

In process, no sockets: items.static_info is what cmd_ss_get_si sends, so
what it returns is what the client gets. Twenty linked types picked at
random must answer with the wiki's numbers, twenty unlinked ones with the
designed frame unchanged, and every linked type must keep every key of its
frame with no zero where the client divides (items.py, top).

    wsl.exe -e python3 server/test_items.py            # random sample
    LAVA_TEST_SEED=7 wsl.exe -e python3 server/test_items.py
"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items
import names

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


SEED = int(os.environ.get("LAVA_TEST_SEED") or time.time())
print("sample seed %d (LAVA_TEST_SEED to repeat)" % SEED)
rnd = random.Random(SEED)

cat = items.catalogue()
wiki = items.wiki()
linked = sorted(t for t in wiki if t in cat)
unlinked = sorted(t for t in cat if t not in wiki)
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
    for key in SCALARS:
        if key in rec and key in p:
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

# --- twenty unlinked types keep the designed frame ----------------------------
for t in rnd.sample(unlinked, 20):
    check("%d %s: designed frame untouched" % (t, cat[t][1]),
          items.static_info(t), items.designed_info(t))
check("an unlinked item has no description", items.static_info(4380)[1]["desc"], "")

# --- invariants over the whole linked catalogue -----------------------------
bad = {}
for t in linked:
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
    if p["desc"] != "" and (p["desc"] != items.DESC_ID_OFFSET + t or not names.known(p["desc"])):
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
check("every linked type keeps its frame and the client's invariants", bad, {})

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
check("every wiki name is served under the item's id",
      all(names.text(items.STRING_ID_OFFSET + t) == n for t, n in wn.items()), True)
wd = items.wiki_descs()
check("over a thousand descriptions", len(wd) >= 1000, True)
check("descriptions are served under their own ids",
      all(names.text(items.DESC_ID_OFFSET + t) == d for t, d in wd.items()), True)
check("line breaks become <br>, markup goes",
      items.clean_text("'''Нельзя в бою.'''<br />\nКусок [[Мясо|мяса]].\n\nСухой."),
      "Нельзя в бою.<br>Кусок мяса.<br>Сухой.")
check("description and name ranges are apart from quests and mobs",
      (items.STRING_ID_OFFSET + max(cat) < 2_000_000,
       items.DESC_ID_OFFSET + max(cat) < 4_000_000), (True, True))

# --- stocks -----------------------------------------------------------------
table = items.stock_table()
check("the designed pistol stall keeps its head", items.stock_for(1200)[:5],
      [4380, 4381, 4382, 4383, 4384])
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

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("items OK")
