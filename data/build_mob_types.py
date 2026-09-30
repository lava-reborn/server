"""Build data/mob_types.json and data/mob_curves.json: what every mob is and how strong.

The client carries no number for any creature. res/database/mobs.xml has
type_id, root_type_id, name and the art folder, nothing else; the art XML
under res/mobs/ holds animation frame maps and a body type. Everything the
server needs for a fight -- level, hit points, damage, experience, weapon,
speed -- was on the dead server and is designed here, not recovered. What
is recovered is the level, which the developers wrote into the type names
(m05_BanditShotgun_lvl2, olm_LandLord10_lvl, EventBoss_lvl_17), into the
names of the camp locations (Up_Camp_6LVL_01_boss) and into the fan wiki's
32 mob pages. Where none of those says anything, the level is borrowed from
the other mobs spawned in the same location, and last of all defaulted.

mob_types.json: type_id -> level, where the level came from, weapon class
(read off a word in the name: Shotgun, AssaultGunner, Shooter, SubMach,
Raider ...), role (mob / boss / animal / object, and the one designed turret),
body type and move speed.
Covers every root_type_id 0 entry and every other type carrying a level.

mob_curves.json: one table by level, 0..33, giving hp, sp, damage range,
hit chance, dodge, armour, action points and the experience pool, plus the
per-weapon-class and per-role multipliers. The design rule is that a mob of
level N is a fair match for a player of level N, using the player formulas
from the wiki's "Игромеханика" page (the developers' own design document):

    HP = 4*strength + 20*constitution      SP = 4*agility + 20*constitution
    constitution grows with the best skill; the "Таблица опыта" page lists
    the resulting HP by level: 120 at 1-2, 140 at 3 ... 400 at 20, 420 at 21
    melee hit chance = 49 + skill*1.25 + spec*5
    dodge = agility + perception + skill + spec*3
    AP = 50 + 5*best skill
    fist damage = rnd(strength/2 .. strength*1.5)
    XP for damage = floor((clamp(mob_lvl - player_lvl, -4, 4) + 4) * damage)

A level-N mob gets exactly the HP and SP a level-N player has before gear,
the hit chance and dodge of a player whose skill is N and whose
specialisation is N/4 (capped at 5, the game's maximum), and a damage range
tuned so that a group of three or four same-level mobs is a serious fight
and a lone one is not: at level 1 a mob hits for 6-10 against 240 HP+SP,
at level 20 for 36-56 against 800. Bosses have triple hit points, animals
less and no weapon. Speeds follow the body type of the art: men walk at the
client's own 200 ms per hex, dogs faster, and static objects (ore, boxes,
alarms, targets) do not move at all.

    wsl.exe -e python3 data/build_mob_types.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

MAX_LEVEL = 33

# --- level from the type name -------------------------------------------

LEVEL_PATTERNS = [
    re.compile(r"_lvl_?(\d+)", re.I),          # m05_BanditRaider_lvl1, EventBoss_lvl_17
    re.compile(r"_LVL_(\d+)"),                 # Delta_Force_mob_LVL_20_00001
    re.compile(r"_(\d+)lvl", re.I),            # pm_CobraMerc_10lvl, WH_Dart_Sorenser_13lvl
    re.compile(r"(?:LandLord|guarder|safeguard|GuardDog)(\d+)_"),  # olm_LandLord10_lvl
    re.compile(r"_(\d+)_event$"),              # mRat_12_event
    re.compile(r"^inv_(\d+)_"),                # inv_13_sniper
    re.compile(r"^fash_boss_(\d+)"),
    re.compile(r"^NG_2014_(\d+)_"),
    re.compile(r"^set_(\d+)_"),
    re.compile(r"^boss_(\d+)$"),
    re.compile(r"^mob_(\d+)"),
    re.compile(r"^m(8|11|19)_uf_"),            # m8_uf_Competitor
    re.compile(r"^VOV_Mob_\d+_\w+?_(\d+)$"),    # VOV_Mob_1_WH_6: 9 May event, per city
]
# Animals are numbered by level: mRat_3, mAntilope_07, mCrocodile_04. Less
# certain than an explicit _lvl, so it gets its own source tag.
INDEX_PATTERN = re.compile(r"^m[A-Z][a-z]+_(\d+)$")

# Prefix bands the developers used for whole tiers of content.
PREFIX_BANDS = {"m05_": 3, "m510_": 8, "m1520_": 18}

# The wiki's city pages state the level band each region is built for:
# Вади-Хальфа 1-8, Абри 8-12, Донгола 12-16, Абу-Хамед 16-20. A type that
# names its city and nothing else (EventBoss_lvl_WH_001) gets the middle.
CITY_BANDS = [(re.compile(r"(^|_)(WH|VH|Wh|Vh)(_|$)"), 5),
              (re.compile(r"(^|_)(AB|Ab|Abri)(_|$)"), 10),
              (re.compile(r"(^|_)(DN|Dn)(_|$)"), 14),
              (re.compile(r"(^|_)(AH|Ah)(_|$)"), 18)]


def level_from_name(name):
    for pat in LEVEL_PATTERNS:
        m = pat.search(name)
        if m:
            return int(m.group(1)), "name"
    m = INDEX_PATTERN.match(name)
    if m:
        return int(m.group(1)), "name_index"
    for prefix, lvl in PREFIX_BANDS.items():
        if name.startswith(prefix):
            return lvl, "name_band"
    for pat, lvl in CITY_BANDS:
        if pat.search(name):
            return lvl, "city_band"
    return None, None


# --- level from the wiki's mob pages -------------------------------------
# The 32 pages describe groups, not client types, and only twelve carry a
# level. These are the ones whose names transliterate to a type unambiguously.
WIKI_LEVELS = {
    "Oasis_AH_Teilor": 19,        # Наемник Гейнц Тейлор, 19 ур.
    "pt_Klenz": 19,               # Шахтер Хорст Кленз, 19 ур.
    "mg_miner": 8,                # Шахтер Магриб, 8-ой уровень
    "Stone_DN": 15,               # Камень (ДН), 15 ур.
}

# --- levels set by hand -----------------------------------------------------
# DESIGNED, not recovered: a creature a quest needs that nothing above gives
# a level, so that it would default to 1. nubia_boss is Большой Мвамба of the
# Nubian valley (31, «Лагерь Большого Мвамбы», data/orig_names_manual.json),
# whom Шульц's «Экипировка к пистолету» sends a party to: «В одиночку с ним не
# справиться ... отряд как минимум из трех человек», «Приходи, когда
# дорастешь до 3-4-го уровня» (texts.xml 59832, 59945). The level of the
# valley's other boss, [5] Лидер Ян Дуглас (m05_nc_Leader_lvl5): a boss
# triples its hit points (ROLES), which is what makes it a party's fight.
#
# And the ammunition boxes of Вади-Хальфа's four camps, which stand, can be
# broken and are looted there (server/world.py STANDING_OBJECTS) and nowhere
# else: one type serves a faction's camp in every city and every Up_Camp
# copy, whose median made each of them level 14 -- a box of 300 hit points
# and armour 26 in the camp for levels 0-2. Each takes the middle of its
# Halfa camp's band, as the map's tooltips give it («Для игроков 0-2
# уровней» on 5970,1724, 2-4 on 5978,1727, 4-6 on 5974,1739, 6-8 on
# 5993,1721).
DESIGNED_LEVELS = {
    "nubia_boss": 5,
    "nc_box_ammo": 1,
    "lu_box_ammo": 3,
    "ja_box_ammo": 5,
    "mg_box_ammo": 7,
}

# --- kinds set by hand ------------------------------------------------------
# DESIGNED: a type whose name makes it something it is not in its place.
# m_turret_lvl6 (832) is named an object by the word "turret" and would stand
# nowhere; the twelve of them in «Огневые установки» (141, Q_VH_TurretGArden)
# are the «автоматические огневые установки» of «Механизмы» that shoot «во
# все движущееся» (texts.xml 47467-47472), and their art (Turrel) is a figure
# with the rifle's firing frames. So a turret: a gun that never walks, with
# a machine gun's burst, and the rounds of it in its bag (ROLES "turret").
DESIGNED_KINDS = {
    "m_turret_lvl6": {"role": "turret", "weapon_class": "machine_gun", "hex_ms": 0},
}

# --- weapon class from a word in the name ---------------------------------
# Order matters: the first matching group wins, so the specific gun words
# come before the generic soldier words.
WEAPON_WORDS = [
    ("machine_gun", r"MachineGunner|machgun|MachGun|support_gunner|Gromila"),
    ("shotgun", r"Shotgun"),
    ("smg", r"SubMach|SubMG|submach|SubMachGun"),
    ("assault_rifle", r"AssaultGunner|AssaultRifle|Asslt|assault_rifle|Assault"),
    ("rifle", r"Shooter|Rifle|rifle|[Ss]nip|sharpshooter|scout|ranger|headhunter|Hunter|Sniper"),
    ("pistol", r"Pistol|pistol|Leader|Chieftain|[Bb]oss|Kaznachei|Comissar|Officer|oficer|"
               r"capitan|captain|colonel|commander|Commander|Courier|Messenger|"
               r"godfather|glavbandit|chief|komandir|Komandir|LandLord|Lord|Master|"
               r"polboss|Primarh|Propovednik|Kupec|Bashi|Karavanshik|caravaner|"
               r"Caravaner|Smotritel|serjeant|sergeant|Barmen|Doctor|doctor|"
               r"Competitor|Dempers|Morgan|Kassidy|Tornhil|Baker|Rudolf|"
               r"Sorenser|Dayson|Dyson|Amin|Johar|Khalid|Jacal|Abdula|Roy|Rich|"
               r"Blade|Gruber|Fanatic|Warrior|Looser|Ramires|Albert|Cobra|"
               r"MOSSAD|prototype|Agnes|Ashram|Asmund|Betty|Ditrich|Elfriede|"
               r"Ihsan|Kais|Kris|Lucky|Luka|Rashad|Sherhan|Tabaqui|koul|marabu|"
               r"ngoro|Abu$|Pilot|Manticore|Tech|Guard$"),
    ("knife", r"Raider|[Bb]ich|bomj|Tramp|Digger|prisoner|[Ss]lave|grabitel|"
              r"negodyai|Maniak|Sadist|Svezhevatel|zhivoder|Dolzhnik|Locked|"
              r"Pogonshik|pogonshik|Pastyx|sektant|Ghost|Ispolnitel|Poslyshnik|"
              r"Naemnik|Golovorez|Maroder|hippie|zapadlist|Amazon|cannonmeat|"
              r"bouncer|Nooby|matros|seaman|bocman|bootsmann|miner|Miner|"
              r"archeolog|labor|xenos|ksenos|Palm|Mechanic|Dancer|Client|"
              r"Father|Tramp|hs$|hs_"),
    ("assault_rifle", r"[Ss]oldier|soldat|Specnaz|Commando|private|recruit|"
                      r"Recruit|Boevik|Veteran|veteran|Opolchenec|Guard|guard|"
                      r"safeguard|Chasovoi|Dozor|Patrol|sentinel|Watchman|"
                      r"ohrannik|ohrana|secur|shturmovik|Diversant|Terr|"
                      r"Bandit|Delta|Force|operative|Force|clun|Touareg|"
                      r"tough|extra|agro|weak|cap$|cap_|spec$|quest|add|"
                      r"battalion|clan|Clan|rkka|snow|VOV|may_|HWS|LIB|LM_|"
                      r"RB_|VBG|VES|KKND|Ilg|Zakon|olc_|pc_|pt_|st_|zd_|jm_|"
                      r"ja_|na_|nc_|mg_|lu_|kv_|me_|cosm|OZ|city_mob|mrare|"
                      r"Apoc|test_boss|EventBoss|event_Mob|inst_|AA_boss|"
                      r"nubia_boss|boss_|ADMIN|Z1_|Z2_|Abri_|DN_|DP_|ME_LC|"
                      r"qJM|set_17|inv_|fash|NG_2014|Dot_|tester|VH_N|UFO_guard"),
]
ANIMAL = re.compile(r"Dog|dog|Hyena|Rat$|Rat_|Antilope|Camel|Kozel|Crocodile|"
                    r"Scot|AnimalSkin|Jacal", re.I)
OBJECT = re.compile(r"Stone|Source|[Bb]ox|Target|target|sirena|turret|Crater|"
                    r"Dracena|Rock|elect_panel|Armorcar|tank|controller|Ship|"
                    r"bridge_mob|Dot_1|part_box")
BOSS = re.compile(r"[Bb]oss|LandLord|Lord|godfather|glavbandit|Chieftain|"
                  r"polboss|chief|komandir|Komandir|mrare_|Primarh|Kaznachei|"
                  r"Leader|Commander|colonel|captain|capitan|Sebek|Mega")


def classify(name, body):
    if OBJECT.search(name) or body in ("none", "flag"):
        return "object", "none"
    if ANIMAL.search(name) or body == "dog":
        return "animal", "fist"
    role = "boss" if BOSS.search(name) else "mob"
    for cls, words in WEAPON_WORDS:
        if re.search(words, name):
            return role, cls
    return role, "pistol"


# --- speed by body type --------------------------------------------------
# The client walks every entity at 200 ms per hex (Location.as); a mob's
# own pace is a server decision. Dogs are quick, men are men, ore is ore.
HEX_MS = {"man": 200, "dog": 150, "dog_fast": 120, "none": 0, "flag": 0,
          "unknown": 200, None: 200}


def body_types():
    """resource -> body type from res/mobs/<resource>.xml."""
    out = {}
    d = os.path.join(world.RES, "mobs")
    for fn in os.listdir(d):
        if fn.endswith(".xml"):
            txt = open(os.path.join(d, fn), "rb").read().decode("utf-8", "replace")
            m = re.search(r'<body type="([^"]*)"', txt)
            out[fn[:-4]] = m.group(1) if m else None
    return out


def spawns_by_location():
    """loc_id -> (fn, [type_id ...]) for every static location."""
    static = os.path.join(world.RES, "locations", "static")
    out = {}
    for fn in os.listdir(static):
        if not fn.endswith(".xml"):
            continue
        txt = world._read(os.path.join(static, fn))
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        types = [int(c[4:8], 16) for c in world._chunks(txt, "mobs", 8)]
        out[int(fn[:-4])] = (attrs.get("fn", ""), attrs.get("title", ""), types)
    return out


# --- the curves ----------------------------------------------------------

# HP by level from the wiki's "Таблица опыта": 4*5 + 20*constitution with
# constitution = 5 + floor(0.75 * (level - 1)). Reproduces the table exactly
# (120, 120, 140, 160, 180, 180, 200, 220, 240, 240, 260 ... 400 at 20).
def player_hp(level):
    lvl = max(1, level)
    return 4 * 5 + 20 * (5 + int(0.75 * (lvl - 1)))


def curve(level):
    n = level
    spec = min(5, n // 4)                     # specialisation a level-n player can hold
    attr = 5 + spec                           # one attribute point per spec level
    hit = min(95, 49 + n * 1.25 + spec * 5)   # melee hit formula, skill = level
    dodge = attr + attr + n + spec * 3        # agility + perception + skill + spec*3
    return {
        "hp": player_hp(n),
        "sp": player_hp(n),
        "dmg_min": int(round(4 + 1.6 * n)),
        "dmg_max": int(round(8 + 2.4 * n)),
        "hit": round(hit, 2),
        "dodge": dodge,
        "armor": int(round(5 + 1.5 * n)),
        "ap": 50 + 5 * n,
        "xp_pool": 4 * player_hp(n),
    }


WEAPON_CLASSES = {
    # dmg_mult scales the level's damage range per shot; shots is the burst
    # the client is told in faAim.num_shots; range in hexes; ap per attack.
    "fist": {"dmg_mult": 0.6, "shots": 1, "range": 1, "ap": 5, "anim": "fist"},
    "knife": {"dmg_mult": 1.0, "shots": 1, "range": 1, "ap": 6, "anim": "knife"},
    "pistol": {"dmg_mult": 1.0, "shots": 1, "range": 6, "ap": 8, "anim": "pistol"},
    "shotgun": {"dmg_mult": 1.4, "shots": 1, "range": 4, "ap": 10, "anim": "rifle"},
    "smg": {"dmg_mult": 0.6, "shots": 3, "range": 5, "ap": 10, "anim": "pistol"},
    "assault_rifle": {"dmg_mult": 0.9, "shots": 2, "range": 7, "ap": 10, "anim": "rifle"},
    "rifle": {"dmg_mult": 1.6, "shots": 1, "range": 10, "ap": 12, "anim": "rifle"},
    "machine_gun": {"dmg_mult": 0.8, "shots": 4, "range": 8, "ap": 14, "anim": "rifle"},
    "none": {"dmg_mult": 0.0, "shots": 0, "range": 0, "ap": 0, "anim": "fist"},
}

ROLES = {
    "mob": {"hp_mult": 1.0, "dmg_mult": 1.0, "xp_mult": 1.0, "aggro": 6},
    "boss": {"hp_mult": 3.0, "dmg_mult": 1.5, "xp_mult": 3.0, "aggro": 8},
    "animal": {"hp_mult": 0.7, "dmg_mult": 0.8, "xp_mult": 0.7, "aggro": 5},
    "object": {"hp_mult": 1.0, "dmg_mult": 0.0, "xp_mult": 0.5, "aggro": 0},
    # A fixed gun (DESIGNED_KINDS): a man's numbers, and it opens fire as
    # soon as anybody is within its machine gun's range.
    "turret": {"hp_mult": 1.0, "dmg_mult": 1.0, "xp_mult": 1.0, "aggro": 8},
}


def dump(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def main():
    mt = world.mob_types()
    bodies = body_types()
    locs = spawns_by_location()

    # Camp level: the Up_ files say it in their name, Up_Camp_6LVL_01_boss.
    camp_level = {}
    for loc_id, (fn, title, types) in locs.items():
        m = re.search(r"(\d+)\s*LVL", fn, re.I)
        if m:
            camp_level[loc_id] = int(m.group(1))

    where = collections.defaultdict(set)
    for loc_id, (fn, title, types) in locs.items():
        for t in types:
            where[t].add(loc_id)

    types = {}
    for tid, (root, name, res) in mt.items():
        lvl, src = level_from_name(name)
        # NPCs are here only when their name spells a level outright.
        if root != 0 and src != "name":
            continue
        if lvl is None and name in WIKI_LEVELS:
            lvl, src = WIKI_LEVELS[name], "wiki"
        if lvl is None and name in DESIGNED_LEVELS:
            lvl, src = DESIGNED_LEVELS[name], "designed"
        if lvl is None:
            camps = sorted(camp_level[l] for l in where[tid] if l in camp_level)
            if camps:
                lvl, src = camps[len(camps) // 2], "camp"
        body = bodies.get(res)
        role, weapon = classify(name, body)
        types[tid] = {
            "name": name, "root": root, "resource": res, "body": body,
            "level": lvl, "level_source": src, "role": role,
            "weapon_class": weapon, "hex_ms": HEX_MS.get(body, 200),
            "spawn_locations": len(where[tid]),
        }
        types[tid].update(DESIGNED_KINDS.get(name, {}))

    # Second pass: a type with no level of its own takes the median level of
    # the levelled types spawned beside it.
    loc_levels = collections.defaultdict(list)
    for tid, rec in types.items():
        if rec["level"] is not None:
            for l in where[tid]:
                loc_levels[l].append(rec["level"])
    for tid, rec in types.items():
        if rec["level"] is None:
            near = sorted(v for l in where[tid] for v in loc_levels[l])
            if near:
                rec["level"], rec["level_source"] = near[len(near) // 2], "location"
    for rec in types.values():
        if rec["level"] is None:
            rec["level"], rec["level_source"] = 1, "default"
        rec["level"] = max(0, min(MAX_LEVEL, rec["level"]))

    levels = {str(n): curve(n) for n in range(0, MAX_LEVEL + 1)}
    dump(os.path.join(HERE, "mob_curves.json"), {
        "_": "Designed, not recovered: the client and the wiki hold no mob "
             "stat. One table by level; multiply hp/dmg/xp by the role and "
             "weapon multipliers of the type. Rationale and the player "
             "formulas this mirrors: docstring of data/build_mob_types.py "
             "(wiki 'Игромеханика', 'Таблица опыта', CC-BY-SA).",
        "formulas": {
            "hp": "player HP of the same level: 20 + 20*(5 + floor(0.75*(L-1)))",
            "sp": "same as hp (SP = 4*agility + 20*constitution)",
            "dmg": "4 + 1.6*L .. 8 + 2.4*L, then * weapon dmg_mult * role dmg_mult",
            "hit": "49 + 1.25*L + 5*min(5, L//4), capped at 95 (wiki melee hit)",
            "dodge": "2*(5 + min(5, L//4)) + L + 3*min(5, L//4) (wiki dodge)",
            "armor": "5 + 1.5*L (attribute part + gear of the tier)",
            "ap": "50 + 5*L (wiki AP)",
            "xp_pool": "4*hp: what a same-level player earns for the kill, "
                       "wiki: floor((clamp(Lmob-Lplayer,-4,4)+4) * damage)",
        },
        "levels": levels,
        "weapon_classes": WEAPON_CLASSES,
        "roles": ROLES,
        "hex_ms": {k: v for k, v in HEX_MS.items() if k},
    })
    dump(os.path.join(HERE, "mob_types.json"), {
        "_": "type_id -> level (level_source: name = _lvlN in mobs.xml, "
             "name_index = animal numbered by level, name_band = "
             "m05_/m510_/m1520_ tier prefix, city_band = region named in "
             "the type, wiki = mob page, designed = set by hand for a "
             "quest (DESIGNED_LEVELS), camp = Up_*LVL location it spawns "
             "in, location = median of neighbours, default), role, "
             "weapon_class, body from "
             "res/mobs/<resource>.xml, hex_ms move speed. Built by "
             "data/build_mob_types.py.",
        "types": {str(k): v for k, v in types.items()},
    })

    by_src = collections.Counter(r["level_source"] for r in types.values())
    by_role = collections.Counter(r["role"] for r in types.values())
    by_weapon = collections.Counter(r["weapon_class"] for r in types.values())
    n_lvl = sum(1 for r, n, s in mt.values() if re.search(r"_lvl", n, re.I))
    print("types written: %d (root 0: %d); names with _lvl in mobs.xml: %d"
          % (len(types), sum(1 for r in types.values() if r["root"] == 0), n_lvl))
    print("level source:", dict(by_src))
    print("roles:", dict(by_role))
    print("weapons:", dict(by_weapon))
    print("camps with a level in fn: %d" % len(camp_level))


if __name__ == "__main__":
    main()
