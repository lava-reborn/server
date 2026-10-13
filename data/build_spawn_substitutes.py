"""Design stand-ins for the creatures the client cannot draw: data/spawn_substitutes.json.

The location files spawn 2947 distinct creature types; 664 of them are gone
from the shipped res/database/mobs.xml (recon/analysis/data.md §4), so the
server skips them and the battle camps open empty: Up_Camp_06LVL_03_boss
lists two creatures the client has no record of, and nothing else that can
fight. This table maps each such type id to a known creature of the SAME
FACTION and the NEAREST LEVEL, so that a camp holds the kind of fighters it
was built for. It is a DESIGN, not a recovery: the original creature is
unknowable, only its company and its level are.

Faction
  The camp files name their faction outright: Bandit_Camp3 and every
  Up_Camp_*LVL_03* are "Лагерь Джанджавидов", whose known inhabitants are
  ja_box_ammo, and the known ja_* creatures (ja_Boevik_lvl4 ...) share the
  prefix. CAMP_FACTIONS is that reading of the ten camp families, checked
  below against the prefixes actually found in each family's files. Any
  other file takes the faction its known hostile inhabitants carry in their
  own prefix, when two or more of them agree and no other prefix rivals
  them. A type standing in files of two factions, or in files with no
  faction, is left unresolved: a wrong company is worse than an empty slot.

Level
  The camp level is in the file name (Up_Camp_07LVL_03_boss -> 7); elsewhere
  the median level of the file's known hostile inhabitants
  (data/mob_types.json); failing both, the faction's own median, marked so.

Choice
  Among the faction's known creatures of role "mob" the ones nearest the
  level, and within that group the k-th for the k-th unknown id of the file,
  so that a camp of four unknowns gets four different fighters rather than
  four copies of one.

Empty slots (data/camp_fill.json)
  A spawn of type 0 names nobody at all: the dead server chose who stood
  there. Вади-Хальфа's camps are made of them -- Bandit_Camp1..4 (80, 81,
  84, 85) hold 10/10/9/10 and nothing that fights but the chief, the
  chiefs' meeting places MW_bandits1..4_boss (82, 83, 86, 87) 9/16/8/13.
  CAMP_FILL below is who stands in each such slot, in the file's order, for
  those Halfa files only, with why; every other file's empty slot stays
  empty. Checked here against the files (one type per slot) and against
  mob_types.json (a fighter of the camp's faction and level band).

    wsl.exe -e python3 data/build_spawn_substitutes.py
"""
import collections
import io
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

# Camp family number (Bandit_CampN, Up_Camp_*LVL_NN) -> faction prefix.
CAMP_FACTIONS = {
    1: "nc",   # Лагерь Новых Колонистов
    2: "lu",   # Лагерь Сектантов Люшеров
    3: "ja",   # Лагерь Джанджавидов
    4: "mg",   # Лагерь Магриба
    5: "st",   # Лагерь Работорговцев (slave traders)
    6: "zd",   # Лагерь Живодеров
    7: "jm",   # Лагерь ДСР
    8: "pc",   # Лагерь Миротворцев (peacekeepers)
    9: "pt",   # Лагерь Пиратов Сомали
    10: "na",  # Лагерь Северного Альянса
    11: "na",  # База Северного Альянса
}
# Fighters with a name of their own, one man each, who never stand in for an
# unknown type: Санденс Кид and Бутч Кэссиди of Абри's camps (st_SundanceKid,
# zd_ButchKassidy), whom data/placements.json puts down in their camps. With
# their rows' levels (data/build_mob_types.py DESIGNED_LEVELS, 2026-10-12) they
# would otherwise be the nearest level of their faction for the Up_Camp copies'
# lost types and stand there by the dozen. And Вильям Блейд of Донгола's ДСР
# camp (jm_WilliamBlade, «[14] Вильям Блейд<Br>ДСР», 8937), put down by hand in
# the camp 93 the same way (the owner's Донгола, 2026-10-13).
NAMED = {1563, 1564, 1565}
# Prefixes that are a season or a test, never a company.
EVENT_PREFIXES = {"vov", "may", "event", "eventboss", "test", "admin", "ny",
                  "hw", "xmas", "vbg", "clan", "kb"}
MIN_POOL = 3


def prefix_of(name):
    m = re.match(r"^([A-Za-z]+?)_", name)
    return m.group(1).lower() if m else None


def camp_family(fn):
    m = re.match(r"^Bandit_Camp_?(\d+)$", fn)
    if m:
        return int(m.group(1))
    m = re.match(r"^Up_Camp_\d+LVL_(\d+)", fn)
    if m:
        return int(m.group(1))
    return None


def camp_level(fn):
    m = re.search(r"(\d+)LVL", fn)
    return int(m.group(1)) if m else None


# DESIGNED: who stands in the empty (type 0) slots of Вади-Хальфа's, Абри's and
# Донгола's camps and quest places, slot by slot in the file's order. location ->
# (faction prefix, or None for stand-ins of another name; (lowest, highest)
# level; the types; why). The bands are the map's tooltips on the camps («Для
# игроков 0-2 уровней» ...); every kind of the faction's fighters that falls in
# the band stands in the camp or at its chief's, so that a quest to kill one of
# them finds it. A place of no faction (None) may stand animals too: Абри's
# fields, totem and car dump held beasts in the original (the wiki's «Поля
# Абри» names the hyenas), and no ambush draws on them (encounters.bands takes
# role "mob" alone).
CAMP_FILL = {
    80: ("nc", (0, 2),
         [258, 259, 260, 261, 262, 263, 264, 265, 268, 586],
         "Лагерь Новых Колонистов (Bandit_Camp1), «Для игроков 0-2 уровней» (tooltip 5970,1724): "
         "the colonists nc_ of levels 0-2, and their treasurer nc_Kaznachei (586), the chief's "
         "man who «руководит сборами дани» -- the commissar «Реклама» sends the player to kill "
         "(texts.xml 62675). He stands all day (server/bosses.py ALL_DAY)."),
    82: ("nc", (0, 2),
         [258, 259, 261, 262, 263, 264, 266, 267, 268],
         "Асмунд's meeting place (MW_bandits1_boss) beside the camp 80: the colonists around "
         "their chief, the kinds 80 leaves out (266, 267) among them."),
    81: ("lu", (2, 4),
         [271, 272, 273, 274, 276, 277, 278, 285, 282, 336],
         "Лагерь Сектантов Люшеров (Bandit_Camp2), «Для игроков 2-4 уровней» (tooltip 5978,1727): "
         "the sect's lu_ of levels 2-4, and lu_Looser_lvl2 (336), the sectarian of «Театр жизни»."),
    83: ("lu", (2, 4),
         [271, 272, 273, 274, 276, 277, 278, 285, 279, 280, 281, 282, 279, 280, 281, 282],
         "Лука's meeting place (MW_bandits2_boss) beside the camp 81: every kind of the sect of "
         "levels 2-4, the level-4 ones twice."),
    84: ("ja", (4, 6),
         [287, 288, 289, 290, 291, 291, 291, 293, 294],
         "Лагерь Джанджавидов (Bandit_Camp3), «Для игроков 4-6 уровней» (tooltip 5974,1739): "
         "the Janjaweed ja_ of levels 4-5, and three ja_Diversant_lvl5 (291): «Бандитская "
         "активность» wants five «Диверсант 5го уровня ... рядом с основным лагерем» "
         "(texts.xml 47283)."),
    86: ("ja", (4, 6),
         [292, 294, 295, 296, 297, 298, 296, 297],
         "Рашад's meeting place (MW_bandits3_boss) beside the camp 84: the Janjaweed of levels "
         "5-6, the kinds 84 leaves out (292, 295-298)."),
    85: ("mg", (6, 8),
         [301, 302, 303, 304, 305, 306, 307, 308, 309, 311],
         "Лагерь Магриба (Bandit_Camp4), «Для игроков 6-8 уровней» (tooltip 5993,1721): Magrib's "
         "mg_ of levels 6-8, the three officers mg_Officer_lvl6/7/8 (303, 307, 311) among them: "
         "«Порядок (часть 2)» finds the plans on the officers of «военного лагеря Магриба» "
         "(texts.xml 47387)."),
    87: ("mg", (6, 8),
         [301, 302, 304, 305, 306, 308, 309, 310, 311, 303, 307, 310, 309],
         "Кайс's meeting place (MW_bandits4_boss) beside the camp 85: every kind of Magrib's "
         "soldiers of levels 6-8, 310 (which 85 leaves out) twice."),
    122: (None, (7, 8),
          [62, 62, 90, 51, 51, 87, 1040, 1040],
          "«Механик ДСР» (Q_VH_Mechanic, tooltip 5988,1714): the mechanic 717 and the ДСР "
          "of levels 7-8 texts.xml names for this line -- [7] Ополченец, [8] Диверсант, [7] "
          "Боевик, [8] Старший офицер, [7] Новобранец (10611-10615) -- whose creatures are "
          "not in mobs.xml (the ДСР jm_ it has are levels 12-14). Stand-ins of the level and "
          "a soldier's art that no location puts down: Ополченец m05_BanditShooter_lvl7 (62), "
          "Боевик m510_BanditAssaultRifle_lvl7 (90), Новобранец m510_Courier_lvl7 (51) -- "
          "all three in the mechanic's own art, mob-m2 -- Диверсант m510_BanditShotgunner_lvl8 "
          "(87), Старший офицер inv_8_cap (1040), two officers for «Операция \"Возмездие\"» "
          "(texts.xml 62728: «уничтожить 5 старших офицеров ДСР»). The rule that the officers "
          "come running at the shooting is not built: they stand from the start."),
    64: ("lu", (4, 4),
         [282, 280],
         "«Сектанты Люшера. Говорят они где-то нашли ящик спирта.» (Q_IV_RitualnoeSozzenie, "
         "tooltip 5986,1725): two level-4 sectarians of the sect, a Послушник and a "
         "Проповедник, beside the six m510_sektant_lvl4 and the box."),
    46: (None, (3, 3),
         [21],
         "«Перехват» (Q_IV_perehvat): a fourth m05_BanditShooter_lvl3 beside the three the "
         "file has, over the box m_WF_Q8_Box (50)."),
    # Абри, the owner's order of 2026-10-12: «В Абри добавь мобов в лагеря и в
    # окрестности».
    88: ("st", (8, 10),
         [315, 316, 317, 318, 319, 320, 321, 323, 324, 590],
         "Лагерь Работорговцев (Bandit_Camp5), «Для игроков 8-10 уровней» (tooltip 5880,1844): "
         "the slave traders st_ of levels 8-10 round their boss Папаша Абу (327), and their "
         "treasurer st_Kaznachei (590, «[10] Казначей<Br>Работорговцы», 8890), who stands all "
         "day (server/bosses.py ALL_DAY). Санденс Кид (1563) is put down by hand "
         "(data/placements.json), so that no ambush draws on him."),
    89: ("st", (8, 10),
         [316, 317, 318, 321, 323, 324, 325, 326, 325],
         "Надзиратель Лаки's meeting place (MW_bandits5_boss) beside the camp 88: the slave "
         "traders round their chief and the four the file has (315, 319, 320, 322), the kinds "
         "88 leaves out (325, 326) among them, the Мучитель twice."),
    92: ("zd", (10, 12),
         [348, 349, 350, 351, 352, 353, 355, 356, 357, 591],
         "Лагерь Живодеров (Bandit_Camp6), «Для игроков 10-12 уровней» (tooltip 5868,1854): the "
         "flayers zd_ of levels 10-12 round their boss Элфрид (360), and their treasurer "
         "zd_Kaznachei (591, «[12] Казначей<Br>Живодеры Элфрида», 8907), who stands all day. "
         "Бутч Кэссиди (1564) is put down by hand (data/placements.json)."),
    90: ("zd", (10, 12),
         [352, 353, 354, 355, 356, 357, 358, 359, 354, 358],
         "Бетти's meeting place (MW_bandits6_boss) beside the camp 92: the flayers of levels "
         "11-12 round their chief, the kinds 92 leaves out (354, 358, 359) among them, 354 and "
         "358 twice."),
    191: (None, (9, 11),
          [1175, 1176, 5631, 1175, 1176, 5631, 1175, 1176, 5631],
          "«Хиппи в пустыне» (Q_Abri_Hippi, tooltip 5860,1838): the file has three hippies, "
          "«Дети цветов» (9048, 9050), and nine empty slots; the same three kinds three times "
          "more, at 9-11 (data/build_mob_types.py DESIGNED_LEVELS). They brew the ФРОК "
          "«Заполучить амазонку (Часть 3)» sends the player for («у них и раздобудь, заодно "
          "порядок наведи», texts.xml 46975)."),
    261: (None, (6, 9),
          [1674, 1674, 1675, 1675, 1676, 1676, 1677, 1677],
          "«Абри: Поля» (Q_Abri_Farm, the map's «Хижина Говарда Хаксли», 5862,1836): the corn "
          "field of Хаксли, where the wiki's «Поля Абри» names the hyenas -- Молодая, Больная, "
          "Голодная, Сытая (m510_Hyena_lvl6..9, 9522-9525), two of each in the file's eight "
          "empty slots. Below the town's band, as the original had them: the corn's pests."),
    262: (None, (7, 8),
          [1675, 1675, 1675, 1675, 1676, 1676, 1676, 1676],
          "The Тотем (Q_Abri_Totem, 5864,1838): Багира's quests at the totem want the skulls of "
          "Больная Гиена (1675, «Жертва Духам», 47020-47023) and ten Голодная Гиена killed (1676, "
          "«Охота: Голодные Гиены», 47024-47027); four of each in the file's eight empty slots."),
    289: (None, (8, 12),
          [2405, 2405, 2405, 2405, 2405, 2405, 2405, 2405, 2405, 2406, 2406, 2406, 2406],
          "«Свалка Автомобилей» (Svalka_OldCars_01, 5863,1835): the dump's own creatures are "
          "lost with the server; rats, the dump's vermin (mRat_8, mRat_12, «[N] Крыса<Br>Дикое "
          "животное», 9498), at the town's band, nine of level 8 and four of 12 in the file's "
          "thirteen empty slots. The junk piles of the dump's searches stand by hand "
          "(data/placements.json)."),
    # Донгола, the owner's order of 2026-10-13: «и потом сделай донголу тоже»,
    # as Абри's «В Абри добавь мобов в лагеря и в окрестности». The ДСР's
    # ranks are their block's (8925-8936: Командир, Ополченец, Солдат, Боевик
    # at 12; Командир Группы, Доброволец, Ветеран, Диверсант at 13; Полевой
    # Командир, Рядовой, Спецназ, Командос at 14), the Peacekeepers' theirs
    # (8942-8953); every rank the town's quests ask for stands: the «[12]
    # Боевик» of «Мясники», the commanders of a group, veterans and saboteurs
    # of Люшер's line, the «[15] Сержант» of «Мухаммед Ахмед».
    93: ("jm", (12, 14),
         [362, 363, 365, 366, 368, 369, 370, 372, 373, 592],
         "Лагерь ДСР (Bandit_Camp7), «Для игроков 12-14 уровней» (tooltip 5883,2035): the ДСР's "
         "jm_ of levels 12-14 round their boss Полковник Халил (374), and their treasurer "
         "jm_Kaznachei (592, «[14] Казначей<Br>ДСР», 8924), who stands all day (server/bosses.py "
         "ALL_DAY). Вильям Блейд (1565) is put down by hand (data/placements.json), so that no "
         "ambush draws on him."),
    91: ("jm", (12, 14),
         [364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 365],
         "Джибрил Ибрагим's meeting place (MW_bandits7_boss) beside the camp 93: the ДСР of levels "
         "12-14 round their chief, the kinds 93 leaves out (364, 367, 371) among them, the «[12] "
         "Боевик» twice."),
    98: ("pc", (14, 16),
         [395, 396, 397, 398, 399, 400, 401, 402, 403, 593],
         "Лагерь Миротворцев (Bandit_Camp8), «Для игроков 14-16 уровней» (tooltip 5921,2011): the "
         "Peacekeepers pc_ of levels 14-16 round their boss Шеф Дженсен (407), and their treasurer "
         "pc_Kaznachei (593, «[16] Казначей<Br>Миротворцы», 8941), who stands all day."),
    99: ("pc", (14, 16),
         [399, 400, 401, 402, 403, 404, 405, 406, 404, 405, 406],
         "Макс Коул's meeting place (MW_bandits8_boss) beside the camp 98: the Peacekeepers of "
         "levels 15-16 round their chief, the kinds 98 leaves out (404-406) twice each."),
}


def camp_fill(mt, types):
    """data/camp_fill.json out of CAMP_FILL, checked: one type per empty
    slot of the file, each a fighter the client can draw (root 0, not an
    object), of the faction's prefix where one is named, in the band."""
    fill = {}
    for loc_id, (faction, (lo, hi), picked, why) in sorted(CAMP_FILL.items()):
        loc = world.location(loc_id)
        empty = sum(1 for _c, t in loc.spawns if t == 0)
        assert loc.war, "camp fill: %d is not a battle location" % loc_id
        assert len(picked) == empty, "camp fill: %d has %d empty slots, %d types" % (
            loc_id, empty, len(picked))
        for t in picked:
            rec = types.get(t)
            assert t in mt and mt[t][0] == 0 and rec, "camp fill: %d in %d is no fighter" % (t, loc_id)
            # A beast only where no faction holds the place (see CAMP_FILL).
            roles = ("mob", "boss") if faction else ("mob", "boss", "animal")
            assert rec["role"] in roles, "camp fill: %d in %d is a %s" % (t, loc_id, rec["role"])
            assert faction is None or prefix_of(rec["name"]) == faction, \
                "camp fill: %d (%s) in %d is not %s" % (t, rec["name"], loc_id, faction)
            assert lo <= rec["level"] <= hi, "camp fill: %d (%s, level %d) in %d is outside %d-%d" % (
                t, rec["name"], rec["level"], loc_id, lo, hi)
        fill[str(loc_id)] = dict(fn=loc.fn, faction=faction, band=[lo, hi], types=picked, why=why)
    return {
        "_": "DESIGNED, not recovered: who stands in the empty (type 0) spawn slots of "
             "Вади-Хальфа's, Абри's and Донгола's camps and quest places, one type per slot in the "
             "file's order. Applied by server/rooms.py in war=1 locations, to these files only; every other "
             "file's empty slot stays empty. Built by data/build_spawn_substitutes.py "
             "(CAMP_FILL), which says why for each.",
        "designed": True,
        "fill": fill,
    }

def main():
    mt = world.mob_types()
    with io.open(os.path.join(HERE, "mob_types.json"), encoding="utf-8") as fh:
        types = {int(k): v for k, v in json.load(fh)["types"].items()}

    # Faction pools: known hostile creatures of role "mob" by prefix, the
    # named ones (NAMED) left out.
    pools = collections.defaultdict(list)
    for tid, rec in types.items():
        if rec["root"] != 0 or rec["role"] != "mob" or tid in NAMED:
            continue
        p = prefix_of(rec["name"])
        if p and p not in EVENT_PREFIXES:
            pools[p].append(tid)
    pools = {p: sorted(v) for p, v in pools.items() if len(v) >= MIN_POOL}

    # Every file: its unknown types, its faction, its level.
    d = os.path.join(world.RES, "locations", "static")
    files = {}
    family_prefixes = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(d), key=lambda s: int(s[:-4])):
        if not fn.endswith(".xml"):
            continue
        i = int(fn[:-4])
        loc = world.location(i)
        unknown = collections.Counter(t for _c, t in loc.spawns if t and t not in mt)
        if not unknown and camp_family(loc.fn) is None:
            continue
        votes = collections.Counter()
        levels = []
        fam = camp_family(loc.fn)
        for _c, t in loc.spawns:
            if t in mt and mt[t][0] == 0 and t in types:
                p = prefix_of(mt[t][1])
                # The camp table is checked against everything known that
                # stands in the family, ammo boxes included (ja_box_ammo).
                if fam is not None and p:
                    family_prefixes[fam][p] += 1
                if types[t]["role"] == "object":
                    continue
                if p in pools:
                    votes[p] += 1
                levels.append(types[t]["level"])
        faction, how = None, ""
        if fam in CAMP_FACTIONS:
            faction, how = CAMP_FACTIONS[fam], "camp_fn"
        elif votes:
            p, n = votes.most_common(1)[0]
            if n >= 2 and n > sum(votes.values()) / 2:
                faction, how = p, "neighbours"
        level, lsrc = camp_level(loc.fn), "fn"
        if level is None and levels:
            level, lsrc = int(statistics.median(levels)), "neighbours"
        if level is None:
            lsrc = ""
        files[i] = dict(fn=loc.fn, title=loc.title, war=loc.war, unknown=unknown,
                        faction=faction, how=how, level=level, level_source=lsrc)

    # Check the camp table against what the files hold.
    for fam, want in sorted(CAMP_FACTIONS.items()):
        seen = family_prefixes.get(fam, collections.Counter())
        top = seen.most_common(1)[0][0] if seen else None
        flag = "" if top in (want, None) else "  <-- files say %s" % dict(seen)
        print("camp family %2d -> %s (files: %s)%s" % (fam, want, dict(seen) or "no known hostiles", flag))

    # One faction and one level per unknown type, from the files it stands in.
    homes = collections.defaultdict(list)
    for i, f in files.items():
        for t, n in f["unknown"].items():
            homes[t].append((i, n))
    subs, unresolved = {}, {}
    faction_median = {p: int(statistics.median(types[t]["level"] for t in ids))
                      for p, ids in pools.items()}
    for t, where in sorted(homes.items()):
        votes = collections.Counter()
        levels = []
        hows = {}
        for i, n in where:
            f = files[i]
            if f["faction"]:
                votes[f["faction"]] += n
                hows.setdefault(f["faction"], f["how"])
            if f["level"] is not None:
                levels.append(f["level"])
        if not votes:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where), reason="фракция не определена")
            continue
        ranked = votes.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where),
                                      reason="файлы разных фракций: %s" % dict(votes))
            continue
        faction = ranked[0][0]
        if faction not in pools:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where),
                                      reason="у фракции %s нет известных бойцов" % faction)
            continue
        if levels:
            level, lsrc = int(statistics.median(levels)), "files"
        else:
            level, lsrc = faction_median[faction], "faction_median"
        # The k-th unknown of the home file takes the k-th nearest creature.
        home = max(where, key=lambda p: (p[1], -p[0]))[0]
        siblings = sorted(files[home]["unknown"])
        k = siblings.index(t)
        ranked_pool = sorted(pools[faction], key=lambda x: (abs(types[x]["level"] - level), mt[x][1]))
        best = abs(types[ranked_pool[0]]["level"] - level)
        nearest = [x for x in ranked_pool if abs(types[x]["level"] - level) == best]
        pick = nearest[k % len(nearest)]
        subs[str(t)] = dict(type_id=pick, name=mt[pick][1], faction=faction,
                            level=level, level_source=lsrc, picked_level=types[pick]["level"],
                            files=sorted(i for i, _n in where), how=hows[faction])

    out = {
        "_": "DESIGNED, not recovered: unknown spawn type id (absent from the "
             "client's mobs.xml) -> a known creature of the same faction and the "
             "nearest level, so that battle camps are not empty. Applied by "
             "server/rooms.py only in war=1 locations and only for hostile "
             "(root 0) creatures. faction = name prefix (ja_ Джанджавиды, mg_ "
             "Магриб, nc_ Новые Колонисты, lu_ Люшер, st_ Работорговцы, zd_ "
             "Живодеры, jm_ ДСР, pc_ Миротворцы, pt_ Пираты, na_ Северный "
             "Альянс, ...); how = camp_fn (Bandit_CampN / Up_Camp_*LVL_NN) or "
             "neighbours (prefix of the known hostiles in the same file); level "
             "from the file name (*LVL), the known neighbours, or the faction's "
             "median. Built by data/build_spawn_substitutes.py.",
        "designed": True,
        "camp_factions": {str(k): v for k, v in CAMP_FACTIONS.items()},
        "pools": {p: len(v) for p, v in sorted(pools.items())},
        "substitutes": subs,
        "unresolved": unresolved,
    }
    path = os.path.join(HERE, "spawn_substitutes.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    reasons = collections.Counter(u["reason"].split(":")[0] for u in unresolved.values())
    by_how = collections.Counter(s["how"] for s in subs.values())
    print("unknown types: %d; substituted: %d (%s); unresolved: %d (%s)" % (
        len(homes), len(subs), dict(by_how), len(unresolved), dict(reasons)))
    print("pools:", {p: len(v) for p, v in sorted(pools.items())})
    print("written to", path)

    fill = camp_fill(mt, types)
    path = os.path.join(HERE, "camp_fill.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fill, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("camp fill: %d slots in %d files, written to %s" % (
        sum(len(v["types"]) for v in fill["fill"].values()), len(fill["fill"]), path))


if __name__ == "__main__":
    main()
