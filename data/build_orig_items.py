"""Original item names and descriptions keyed by our type_id: data/orig_items.json.

The game's own string table survived outside the client: texts.xml, 62 795
rows <item id="N">text</item>. The server does not send those ids -- an item
name goes out as items.STRING_ID_OFFSET + type_id, a description as
items.DESC_ID_OFFSET + type_id -- so the only thing carried over is the TEXT,
filed under our type_id. name_id/desc_id stay in the output as an audit trail
back into texts.xml; nothing reads them at run time.

A text is html.unescape'd (&lt;Br&gt; -> <Br>) and nothing else: tier marks
such as [A][4]$Пистолет, tags and typos stay as they are. Formatting belongs
to one place on the server.

Run from WSL (LAVA_RES is required; LAVA_ORIG_TEXTS moves the source):
    LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/build_orig_items.py

How a type finds its rows. A type taken by an earlier rule is never looked at
by a later one, and only "high" and "medium" records are written.

 1. Firearm lines (data/firearm_families.json). Gun rows read
    "Имя[тир][уровень]$Класс"; consecutive rows of one name form a block, the
    rows after its name rows are its descriptions, recognised by the phrase
    after <Br><B> ("Увеличено повреждение на 10%." -> damage). Kinds: std =
    A, P and G present and either [M] or >= 12 mod descriptions; solo = Q or
    RW with no P/G; mob = only [M]. Per (class, level) the lines with _pm/_gold
    copies take the std blocks, lines without them the solo blocks, mob-only
    lines the mob blocks -- in both lists by ascending index/row id. Equal
    counts give "high"; fewer blocks than lines name the lowest indexes and
    give "medium". Inside a block a tier takes its own name row (A falls back
    to Q/RW), the base type the "original model" description, a mod type the
    description with its phrase, the mob copy the [M] name and the base
    description. A short block borrows descriptions from the full block of the
    same name, and a mob copy whose block has no [M] takes the one [M]-only
    block of its (class, level) that no mob-only line took.
 2. Clan copies of those lines (+LeMon, +Liberty, +Delta_Force, +ID256): the
    [S]/[CL] block of the level, several of them sorted against the lines that
    carry the suffix; descriptions from that block, else from the line's.
 3. USSR_/NY2016_ event pistols: the "Тульский Токарева" and "Пустынный Ёж"
    [A][P][G] rows of their level.
 4. Ammo_<calibre>_<quality>: the one row "калибр[тир] $КОД"; the
    description is the one the first calibre carries for that tier and code.
    Mixed calibres (SP_5_6), arrows and grenades are "medium".
 5. Wear, series Mob and Bs_U only: per level, the one set of 5-slot runs of
    "Имя[ур][тир][мод N]" rows (helm, shirt, armor, pants, boots) that covers
    >= 90% of the series' (tier, mod) keys, best overlap winning.
 5b. Wear of the three sets at levels 0-8 -- Bs (Беженец), Set (Колонист),
    Exzo (Легионер, from level 7 Красное ЭXO) -- by the five words of each
    series (SET_SERIES): the one row "<слово>[ур][тир][мод N]" that is not
    the title of an upgrade quest. Колонист[2] takes the names of level 0,
    its own rows being descriptions; a piece's description is the row after
    its first name, else (Колонист) that level-2 row.
 6. Trophies tr_Skull..tr_Horn: rows 800, 802 .. 812 and the row after each.
 7. Medicine, food and water (Med_*): hand-checked blocks of six level
    bands, name and description row by row (HEAL_BLOCKS); the 20-dose
    injector packs and the bar (HEAL_ROWS).
 7b. The shop knives knife_lvl<N>_{A,G,G_damage,G_actionpoint,
    G_damage_actionpoints}: one hand-checked run, 1488-1580, level by level
    (KNIFE_ROWS); the (G) copy shows its plain twin's description.
 7c. What the Nubian mine's marauders drop (data/loot_manual.json): gold
    sand and the small emeralds, two hand-checked name and description
    pairs (MINE_ROWS).
 7d. The gold ingots New_Gold_Ingot_1/_5/_10, the 1-ounce one being what
    the Nubian valley's boss drops, two at a time (data/loot_manual.json):
    the run of three hand-checked pairs 7636-7641 (GOLD_INGOT_ROWS).
 7e. What the Nubian valley's dogs, rats and antelopes leave in a bag, and
    the things its quests send the player to take off a creature -- the gun
    parts, the medicaments, the rat king, the old chip: hand-checked name
    and description pairs of two runs in objects.xml's order, 6097-6110 and
    6154-6163, and three by their names (VALLEY_ROWS).
 7f. The things Вади-Хальфа's quests hand out and ask for that had no row:
    the town's quest run 6167-6341 and a few named rows elsewhere (the
    journal «Верблюжьи холмы», Берт's training guns, the certificate, the
    stone block), hand-checked name and description pairs (HALFA_ROWS).
 7i. Вади-Хальфа's stage 3, a table of hand-checked rows for each of its
    parts: the prison's red armband, the one thing of the uprising that had
    no row (PRISON_ROWS); the plant's things (server/production.py): the
    ore, sorted ore and sacks, a family of five cities each out of the run
    7189-7240 (PRODUCTION_FAMILIES), and the quarry's other stones,
    polishing mix and components 7255-7265 (POLISH_ROWS); what the treasure
    digs, Уорхол's collection and the rides hand out and ask for --
    Дирижер's maps, the Бункер Ламантина pieces, the tickets rule 7f leaves
    (WILD_ROWS).
 8. Everything else: the wiki name from data/items_wiki.json equals exactly
    one row (brackets, $-suffix, case, ё and quotes ignored); "high" when the
    row after it is the wiki description too. Types of firearm_families.json
    lines are left to rules 1-2 even when those fail.
"""
import collections
import hashlib
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import (AMMO, COLD_ARM, FIRE_ARM, HEAL, HERE, RES, TRASH,
                         TROPHY, WEAR, dump_json, load_json, load_objects)

DEFAULT_TEXTS = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "orig_items.json")

ROOT_NAME = {FIRE_ARM: "FireArm", WEAR: "WearItem", HEAL: "Heal_Item",
             AMMO: "Ammo", TRASH: "SimpleObject", COLD_ARM: "ColdArm",
             TROPHY: "Trophy"}
KEEP = ("high", "medium")


# --- texts.xml ---------------------------------------------------------------

ITEM_ROW = re.compile(r'<item id="(\d+)">(.*?)</item>\n', re.S)


def load_texts(path):
    """-> (texts indexed by id, md5, size). The ids must run 0..N-1."""
    with open(path, "rb") as f:
        raw = f.read()
    body = raw.decode("utf-8")
    rows = ITEM_ROW.findall(body)
    if [int(i) for i, _ in rows] != list(range(len(rows))):
        raise SystemExit("%s: item ids are not 0..N-1 in order" % path)
    if "<item" in ITEM_ROW.sub("", body):
        raise SystemExit("%s: an <item> row this parser does not read" % path)
    return [html.unescape(t) for _, t in rows], hashlib.md5(raw).hexdigest(), len(raw)


# --- 1. firearm lines ----------------------------------------------------------

GUN_CLASS = {"Пистолет": "pistols", "Пистолет-пулемёт": "sub_machine_guns",
             "Дробовик": "shotgun", "Пулемет": "machine_gun",
             "Автомат": "assault_rifle", "Винтовка": "rifle"}
GUN_NAME = re.compile(r"^(.*?)\s*((?:\[[^\[\]]*\])+)\s*(?:\$(.*))?$")
LEVEL_TAG = re.compile(r"-?\d+(?:\.\d+)?")     # [7], and [14.00] of MG 1_14/2_14

# Phrase after the last <Br><B> of a description -> the modification it
# describes. Longer phrases first: "...на 20% и ..." is not plain precision.
MOD_PHRASE = [
    ("Оригинальная модель без конструктивных", "base"),
    ("Увеличена точность на 20% и", "precision_shotrange"),
    ("Увеличено повреждение на 10% и увеличена обойма", "damage_clipsize"),
    ("Увеличена точность на 20%", "precision"),
    ("Увеличено повреждение на 10%", "damage"),
    ("У оружия увеличена максимальная дальность", "shotrange"),
    ("Время прицеливания", "aimtime"),
    ("Скорость перезарядки увеличена", "reloadspeed"),
    ("Скорострельность увеличена", "shotspeed"),
    ("Увеличена обойма", "clipsize"),
    ("Прочность увеличена в 2 раза", "attrition_x2"),
    ("Ловкость +", "agility"),
    ("Восприятие +", "perception"),
    ("Увеличено повреждение на 25%", "damage25"),
    ("Снижен вес на 25%", "weight"),
]
# Mod keys of objects.xml that name a description under another key;
# "clipsize_damafe" is the client's own typo (rifle_1_lvl_20_gold_mod_clipsize_damafe_Delta_Force).
MOD_ALIAS = {"clipsize_damage": "damage_clipsize", "clipsize_damafe": "damage_clipsize",
             "durability": "attrition_x2"}
FULL_BLOCK = 12          # a block with this many mod descriptions is complete


def parse_gun_name(text):
    """'Имя[тир][уровень]$Класс' -> (name, [tags], level, class word) or None."""
    if "$" not in text:
        return None
    m = GUN_NAME.match(text)
    if not m:
        return None
    level, tags = None, []
    for tag in re.findall(r"\[([^\[\]]*)\]", m.group(2)):
        if LEVEL_TAG.fullmatch(tag.strip()):
            level = int(float(tag))
        else:
            tags.append(tag)
    if level is None:
        return None
    return m.group(1), tags, level, m.group(3)


def mod_of(text):
    """Modification a description row speaks of; None without <Br><B>, '?' unknown."""
    if "<Br><B>" not in text:
        return None
    tail = text.split("<Br><B>")[-1]
    for phrase, mod in MOD_PHRASE:
        if phrase in tail:
            return mod
    return "?"


class Block:
    """Consecutive rows of one gun at one level: its name rows, then descriptions."""

    def __init__(self, name, level, word, first):
        self.name, self.level, self.word, self.first = name, level, word, first
        self.cls = GUN_CLASS[word]
        self.names = {}      # tier tag ("A", "P", "Q", "A/HM"...) -> row id
        self.mods = {}       # "base"/"damage"/... -> row id of its description (last wins)

    @property
    def n_mods(self):
        return sum(1 for m in self.mods if m != "base")

    @property
    def kind(self):
        t = set(self.names)
        if {"A", "P", "G"} <= t and ("M" in t or self.n_mods >= FULL_BLOCK):
            return "std"
        if t & {"Q", "RW"} and not t & {"P", "G"} and not any("/" in x for x in t):
            return "solo"
        if t == {"M"}:
            return "mob"
        return "other"


def gun_blocks(T):
    """Walk texts.xml once. A gun name row opens a block or extends the open one
    (same name, level and class); any other row that is not itself a name keeps
    the block open as a description, except an empty row or a <hint> without
    <Br><B>, which closes it, as does a name of another class."""
    blocks, cur = [], None
    for i, text in enumerate(T):
        p = parse_gun_name(text)
        if p and p[3] in GUN_CLASS:
            name, tags, level, word = p
            if cur is None or (cur.name, cur.level, cur.word) != (name, level, word):
                cur = Block(name, level, word, i)
                blocks.append(cur)
            cur.names["/".join(tags)] = i
        elif cur is not None and p is None:
            mod = mod_of(text)
            if mod is None and (not text or text.startswith("<hint")):
                cur = None
            elif mod not in (None, "?"):
                cur.mods[mod] = i
        else:
            cur = None
    return blocks


def first_set(*values):
    for v in values:
        if v is not None:
            return v
    return None


class Firearms:
    """Lines of firearm_families.json matched to gun blocks of texts.xml."""

    def __init__(self, T, families):
        self.lines = families
        self.blocks = gun_blocks(T)
        self.full = collections.defaultdict(list)
        self.by_level = collections.defaultdict(list)
        for b in self.blocks:
            if b.n_mods >= FULL_BLOCK:
                self.full[b.name].append(b)
            self.by_level[(b.cls, b.level)].append(b)
        self.match = {}          # line -> (block, exact)
        self.mob_taken = set()   # ids of [M]-only blocks some mob-only line took
        self._match_lines()

    @staticmethod
    def group(rec):
        if rec["mob_only"]:
            return "mob"
        return "std" if rec["members"].get("P") or rec["members"].get("G") else "solo"

    def _match_lines(self):
        lines = collections.defaultdict(list)
        for key, rec in self.lines.items():
            lines[(rec["cls"], rec["level"], self.group(rec))].append((rec["index"], key))
        for (cls, level, kind), ls in lines.items():
            ls.sort()
            bs = [b for b in self.by_level[(cls, level)] if b.kind == kind]
            for (_, key), b in zip(ls, bs):
                self.match[key] = (b, len(ls) == len(bs))
                if kind == "mob":
                    self.mob_taken.add(b.first)

    def parent(self, b):
        """The complete block whose descriptions a short block borrows."""
        if b.n_mods >= FULL_BLOCK:
            return b
        cands = self.full.get(b.name, [])
        cands = [x for x in cands if x.cls == b.cls] or cands
        if not cands:
            return None
        return min(cands, key=lambda x: (abs(x.level - b.level), x.first))

    def desc(self, b, mod):
        p = self.parent(b)
        return first_set(b.mods.get(mod), p.mods.get(mod) if p else None)

    def tier_name(self, b, tier):
        if tier in b.names:
            return b.names[tier]
        if tier == "A":
            for t in ("Q", "RW"):
                if t in b.names:
                    return b.names[t]
        return None

    def mob_name(self, b):
        """-> (row id of the [M] name, whether it was only inferred)."""
        if "M" in b.names:
            return b.names["M"], False
        same = self.by_level[(b.cls, b.level)]
        for x in same:
            if x.kind == "mob" and x.name == b.name:
                return x.names["M"], False
        # No [M] of its own name: the one [M]-only block of the level that no
        # mob-only line took (pistols_0_lvl_15 -> "Mauser Mod.712[M][15]").
        free = [x for x in same if x.kind == "mob" and x.first not in self.mob_taken]
        return (free[0].names["M"], True) if len(free) == 1 else (None, False)

    def records(self):
        """type_id -> (name_id, desc_id, confidence) for every type of a matched line."""
        out = {}
        for line, (b, exact) in sorted(self.match.items()):
            rec = self.lines[line]
            conf = "high" if exact else "medium"
            types = {} if rec["mob_only"] else dict(rec["members"])
            if "A+mob" in rec["extra"]:
                types["A+mob"] = rec["extra"]["A+mob"]
            for key, tid in types.items():
                inferred = False
                if key == "A+mob" and b.kind == "mob":
                    nid = b.names["M"]
                    base = [x for x in self.blocks if x.name == b.name and x.cls == b.cls
                            and "base" in x.mods]
                    did = base[0].mods["base"] if base else None
                elif key == "A+mob":
                    (nid, inferred), did = self.mob_name(b), self.desc(b, "base")
                else:
                    tier, _, mod = key.partition(":")
                    nid = self.tier_name(b, tier)
                    did = self.desc(b, MOD_ALIAS.get(mod, mod) if mod else "base")
                if nid is None or did is None:
                    out[tid] = (nid, did, "partial")
                else:
                    out[tid] = (nid, did, "medium" if inferred else conf)
        return out


# --- 2. clan copies ------------------------------------------------------------

CLAN_WORD = {"Liberty": "Liberty", "Delta_Force": "Delta Force",
             "Delta_Force_base": "Delta Force", "ID256": "Blackwater"}


def clan_blocks(T, fire):
    starts = sorted((b.first, b.cls) for b in fire.blocks if b.kind == "std")

    def region(i):
        cls = None
        for first, c in starts:
            if first > i:
                break
            cls = c
        return cls

    out = []
    for i, text in enumerate(T):
        p = parse_gun_name(text)
        if not p or not {"CL", "S"} & set(p[1]):
            continue
        # Its descriptions: the rows up to the next name or <hint>; the first
        # one of a modification counts, a row without <Br><B> is "base".
        descs, j = {}, i + 1
        while j < len(T) and not parse_gun_name(T[j]) and not T[j].startswith("<hint"):
            descs.setdefault(mod_of(T[j]) or "base", j)
            j += 1
        out.append(dict(id=i, name=p[0], tags=p[1], level=p[2], word=p[3],
                        cls=region(i), descs=descs))
    for b in out:
        b["donor"] = None
        if len(b["descs"]) < 2:
            donors = [x for x in out if x["name"] == b["name"] and len(x["descs"]) >= 2]
            b["donor"] = donors[0] if donors else None
    return out


def clan_records(fire, cblocks):
    out = {}
    for line, rec in sorted(fire.lines.items()):
        matched = fire.match.get(line)
        groups = collections.defaultdict(list)
        for key, tid in rec["extra"].items():
            suffix = key.partition("+")[2]
            if suffix != "mob":
                groups[suffix].append((key, tid))
        for suffix, items in sorted(groups.items()):
            if suffix == "LeMon":
                words = ("Le Mon", "Пулемет") if rec["cls"] == "machine_gun" else ("Le Mon",)
                name = matched[0].name if matched else None
                cands = [b for b in cblocks if "S" in b["tags"] and b["level"] == rec["level"]
                         and b["name"] == name and b["word"] in words]
            elif suffix in CLAN_WORD:
                cands = [b for b in cblocks if b["word"] == CLAN_WORD[suffix]
                         and b["level"] == rec["level"] and b["cls"] == rec["cls"]]
            else:
                cands = []
            conf = "medium" if cands else "unmatched"
            if len(cands) > 1:
                peers = sorted((x["index"], k) for k, x in fire.lines.items()
                               if x["cls"] == rec["cls"] and x["level"] == rec["level"]
                               and any(e.endswith("+" + suffix) for e in x["extra"]))
                peers = [k for _, k in peers]
                if len(peers) == len(cands):
                    cands = [sorted(cands, key=lambda b: b["id"])[peers.index(line)]]
                else:
                    conf = "ambiguous"
            for key, tid in items:
                if conf != "medium":
                    out[tid] = (None, None, conf)
                    continue
                b = cands[0]
                tier, _, mod = key.partition("+")[0].partition(":")
                mod = mod.replace("_gold_CL", "").replace("_CL", "").replace("_gold", "")
                if mod.startswith("speedshot"):
                    mod = "shotspeed"
                mod = MOD_ALIAS.get(mod, mod) if mod else "base"
                donor = b["donor"]
                did = first_set(b["descs"].get(mod), donor["descs"].get(mod) if donor else None)
                if did is None and matched:
                    did = fire.desc(matched[0], mod)
                out[tid] = (b["id"], did, conf)
    return out


# --- 3. event pistols ------------------------------------------------------------

EVENT_PISTOL = {"USSR": "Тульский Токарева", "NY2016": "Пустынный Ёж"}


def event_records(T, objects):
    out = {}
    for prefix, gun in sorted(EVENT_PISTOL.items()):
        row = re.compile(r"^" + re.escape(gun) + r"\[([APG])\]\[(\d+)\]")
        names, descs = {}, {}
        for i, text in enumerate(T):
            m = row.match(text)
            if m:
                names[(int(m.group(2)), m.group(1))] = i
        for (level, tier), i in names.items():
            if tier == "A" and i + 1 < len(T) and "[" not in T[i + 1][:40]:
                descs[level] = i + 1
        typ = re.compile(r"^" + prefix + r"_pistols_\d_lvl_(\d+)(_gold)?_mod_([a-z_]+?)(_gold|_pm)?$")
        for tid, (_, name) in objects.items():
            m = typ.match(name)
            if not m:
                continue
            level = int(m.group(1))
            tier = "G" if m.group(2) or m.group(4) == "_gold" else ("P" if m.group(4) == "_pm" else "A")
            # Levels 16-18 have no description row: reuse level 6 (damage) or
            # 15 (damage + clipsize), the two modifications these guns carry.
            did = descs.get(level) or descs.get(6 if m.group(3) == "damage" else 15)
            out[tid] = (names.get((level, tier)), did, "medium")
    return out


# --- 4. ammo -------------------------------------------------------------------------

AMMO_ROW = re.compile(r"^(.*?)\s*\[([A-Z]+)\]\s*\$(КС|СТ|ОТ|ЭК|ББ|СБ|ШК)$")
CALIBRE = {"9mmNato": ["9мм НАТО"], "45": ["0.45 калибр"], "762x25": ["7.62х25"],
           "762x51": ["7.62х51мм НАТО"], "12mm": ["12–й калибр"],
           "556x45": ["5.56х45мм НАТО"], "762x39": ["7.62х39мм"], "762x54R": ["7.62х54R"],
           "SP_5_6": ["ПАБ–9", "СП–6", "СП–5"], "SP_5": ["СП–5"], "SS190": ["5.7x28"],
           "86x70": ["8.6x70"], "SP_10_12": ["СП–10", "СП–12"], "545x39": ["5.45х39мм"],
           "68x43": ["6.8 mm Remington SPC"], "16mm": ["16–й калибр"],
           "40mmRPG": ["Граната"], "Metallbolt": ["Металлическая стрела"]}
QUALITY = {"KS_P": ("R", "КС"), "KS": ("A", "КС"), "ST": ("A", "СТ"), "OT": ("A", "ОТ"),
           "KSG": ("G", "КС"), "OT_PS": ("Q", "ОТ"), "EK_G": ("G", "ЭК"),
           "BB_G": ("G", "ББ"), "SB_G": ("G", "СБ")}
# The row names of these calibres mix several cartridges or are no bullets.
AMMO_MEDIUM = {"SP_5_6", "Metallbolt", "40mmRPG"}
AMMO_SPECIAL = {"Ammo_9mmNato_kal": (922, 923), "Ammo_9mmNato_shock": (1025, 1026)}
AMMO_TYPE = re.compile(r"^Ammo_(.+?)_(KS_P|KSG|KS|ST|OT_PS|OT|EK_G|BB_G|SB_G)$")


def ammo_records(T, objects):
    rows = []
    for i, text in enumerate(T):
        m = AMMO_ROW.match(text)
        if m:
            rows.append((i, m.group(1).strip(), m.group(2), m.group(3)))
    # One description per (tier, code): the row after its first occurrence.
    desc = {}
    for i, _, tier, code in rows:
        nxt = T[i + 1] if i + 1 < len(T) else ""
        if (tier, code) not in desc and nxt and not AMMO_ROW.match(nxt) and "$" not in nxt:
            desc[(tier, code)] = i + 1
    out = {}
    for tid, (root, name) in sorted(objects.items()):
        if root != AMMO:
            continue
        if name in AMMO_SPECIAL:
            out[tid] = AMMO_SPECIAL[name] + ("medium",)
            continue
        m = AMMO_TYPE.match(name)
        if not m:
            continue
        cal, quality = m.groups()
        tier, code = QUALITY[quality]
        hits = [i for i, n, t, c in rows if n in CALIBRE.get(cal, ()) and (t, c) == (tier, code)]
        if len(hits) != 1:
            continue
        # [A]КС has no description of its own and shares [R]КС's.
        did = desc.get((tier, code)) or (desc.get(("R", "КС")) if (tier, code) == ("A", "КС") else None)
        out[tid] = (hits[0], did, "medium" if cal in AMMO_MEDIUM else "high")
    return out


# --- 5. wear ---------------------------------------------------------------------------

WEAR_ROW = re.compile(r"^(.*?)\s*\[(\d+)\]((?:\[[A-Za-zА-Яа-я]+\])+)\[мод\s*([0-9A-Za-z]+)\]\s*$")
WEAR_TYPE = re.compile(r"^(helm|shirt|armor|pants|boots)_(.+?)_(M|F|U)_LVL_(\d+)_([A-Z]+)(?:_(.*?))?_mod(\w+)$")
WEAR_SLOTS = ["helm", "shirt", "armor", "pants", "boots"]
WEAR_SERIES = {"Mob", "Bs_U"}


def wear_records(T, objects):
    rows = []
    for i, text in enumerate(T):
        m = WEAR_ROW.match(text)
        if m:
            tags = "/".join(re.findall(r"\[([^\]]+)\]", m.group(3)))
            rows.append((i, m.group(1), int(m.group(2)), tags, m.group(4)))
    # Runs of rows with one (level, tier, mod), ids at most 2 apart, cut into
    # quintuples helm..boots: series -> {(tier, mod): [5 row ids]}.
    runs = collections.OrderedDict()
    for i, name, level, tags, mod in rows:
        runs.setdefault((level, tags, mod), []).append((i, name))
    series = collections.OrderedDict()
    for (level, tags, mod), v in runs.items():
        chunks, cur = [], [v[0]]
        for a in v[1:]:
            if a[0] - cur[-1][0] <= 2:
                cur.append(a)
            else:
                chunks.append(cur)
                cur = [a]
        chunks.append(cur)
        for run in chunks:
            if len(run) % 5:
                continue
            for c in range(0, len(run), 5):
                q = run[c:c + 5]
                key = (level, tuple(n for _, n in q))
                series.setdefault(key, {}).setdefault((tags, mod), [i for i, _ in q])
    first = {}
    for i, name, *_ in rows:
        first.setdefault(name, i)
    ours = collections.defaultdict(dict)
    for tid, (root, name) in sorted(objects.items()):
        m = WEAR_TYPE.match(name) if root == WEAR else None
        if not m:
            continue
        slot, ser, sex, level, tier, extra, mod = m.groups()
        ser += "_U" if sex == "U" else ""
        if not extra and ser in WEAR_SERIES:
            ours[(ser, int(level))][(slot, tier, mod)] = tid
    out = {}
    for (ser, level), types in sorted(ours.items()):
        keys = {(t, m) for _, t, m in types}
        cands = [v for k, v in series.items() if k[0] == level and len(keys & set(v)) >= 0.9 * len(keys)]
        if len(cands) > 1:
            best = max(len(keys & set(v)) for v in cands)
            cands = [v for v in cands if len(keys & set(v)) == best]
        if len(cands) != 1:
            continue
        for (slot, tier, mod), tid in types.items():
            ids = cands[0].get((tier, mod))
            if not ids:
                continue
            nid = ids[WEAR_SLOTS.index(slot)]
            # The first row of a slot name is followed by its description.
            i = first.get(re.match(r"^(.*?)\s*\[", T[nid]).group(1))
            did = None
            if i is not None and i + 1 < len(T) and not re.search(r"\[мод", T[i + 1]) and len(T[i + 1]) > 20:
                did = i + 1
            out[tid] = (nid, did, "medium")
    return out


# --- 5b. the three sets of levels 0-8, by name ------------------------------------------

# Rule 5 cannot tell these three apart. At every level from 0 to 8 each has the
# same tiers and the same eleven mods, so three runs of rows fit each series
# equally well and the rule keeps none. Their words can: each series has five
# of its own, and which words go with which series was settled on the client's
# icons (recon, 2026-09-23). Exzo draws a Corinthian helmet with a gas mask --
# "Шлем легионера" to the letter -- and from level 7 an exoskeleton with a
# Soviet star; Set draws the goggles, shirt and jeans of the Колонист; Bs is
# what is left. Set against Bs is the weaker call -- Bs at levels 2-4 draws
# what the wiki shows as the Колонист's -- and the owner took it as it
# stands, so every record here is "medium". Only levels 0-8, where the icons
# were looked at: above them the same words also name clan, VIP and mob
# copies, and those levels wait for someone to look.
SET_SERIES = {
    "Bs": ((0, ("Очки-консервы", "Топик", "Жилет из брезента", "Рваные брюки",
                "Ботинки рабочего")),),
    "Set": ((0, ("Гоглы с фильтром", "Рубашка", "Кусковая броня", "Джинсы",
                 "Старые ботинки")),),
    "Exzo": ((0, ("Шлем легионера", "Плащ легионера", "Броня легионера",
                  "Штаны легионера", "Ботинки легионера")),
             (7, ("Шлем Красное ЭXO", "Поддоспешник Красное ЭXO", "Корпус Красное ЭXO",
                  "Моторика Красное ЭXO", "Боты Красное ЭXO"))),
}
SET_LEVELS = range(0, 9)
# Where Колонист[2]'s names should be, texts.xml has the five descriptions
# instead ("Рубашка неизвестного происхождения с короткими рукавами.[2][A][мод00]").
# The level is no part of a name the player sees (orig_texts drops it), so
# level 2 takes the names of level 0 -- and those five rows, the only
# description four of the five pieces have anywhere, describe every level.
SET_BORROWED_LEVEL = {("Set", 2): 0}
SET_DESC_LEVEL = {"Set": 2}


def set_words(series, level):
    """The five words of a series at this level, helm to boots."""
    words = None
    for since, names in SET_SERIES[series]:
        if level >= since:
            words = names
    return words


def wear_set_records(T, objects):
    # An upgrade quest is titled with the very name of the item it improves
    # ("Шлем легионера [6][G][мод01]" at row 27722, its <hint> text next);
    # such a row names the quest, not the item.
    rows = collections.defaultdict(list)
    for i, text in enumerate(T):
        m = WEAR_ROW.match(text)
        if m and not (i + 1 < len(T) and T[i + 1].startswith("<hint")):
            rows[(m.group(1), int(m.group(2)), m.group(3), m.group(4))].append(i)

    def plain(i):
        return (i < len(T) and len(T[i]) > 20 and not WEAR_ROW.match(T[i])
                and not T[i].startswith("<hint"))

    names = {}
    for tid, (root, name) in sorted(objects.items()):
        m = WEAR_TYPE.match(name) if root == WEAR else None
        if not m:
            continue
        slot, ser, sex, level, tier, extra, mod = m.groups()
        level = int(level)
        if ser not in SET_SERIES or sex != "M" or extra or level not in SET_LEVELS:
            continue
        word = set_words(ser, level)[WEAR_SLOTS.index(slot)]
        look = SET_BORROWED_LEVEL.get((ser, level), level)
        hits = rows.get((word, look, "[%s]" % tier, mod), [])
        if len(hits) == 1:
            names[tid] = (ser, level, slot, word, hits[0])

    # A piece's description follows the first row of its name, at the level
    # its words begin, [A][мод00]; the Колонист has one for the goggles only,
    # and for the rest the level-2 rows between its levels 0 and 3.
    descs = {}
    for ser, groups in SET_SERIES.items():
        for since, words in groups:
            for word in words:
                first = rows.get((word, since, "[A]", "00"))
                if first and plain(first[0] + 1):
                    descs[word] = first[0] + 1
    for ser, level in SET_DESC_LEVEL.items():
        lo = max((r for s, lv, _, _, r in names.values() if s == ser and lv == 0), default=None)
        hi = min((r for s, lv, _, _, r in names.values() if s == ser and lv == 3), default=None)
        if lo is None or hi is None:
            continue
        found = []
        for i in range(lo, hi):
            m = WEAR_ROW.match(T[i])
            if m and (int(m.group(2)), m.group(3), m.group(4)) == (level, "[A]", "00"):
                found.append(i)
        if len(found) != len(WEAR_SLOTS) or any(len(WEAR_ROW.match(T[i]).group(1)) < 30 for i in found):
            raise SystemExit("texts.xml rows %d..%d: expected the five %s[%d] descriptions"
                             % (lo, hi, ser, level))
        for word, i in zip(set_words(ser, 0), found):
            descs.setdefault(word, i)

    return {tid: (nid, descs.get(word), "medium")
            for tid, (ser, level, slot, word, nid) in names.items()}


# --- 6. trophies -------------------------------------------------------------------------

TROPHY_ROW = {"tr_Skull": 800, "tr_Scalp": 802, "tr_Finger": 804, "tr_Ear": 806,
              "tr_Hand": 808, "tr_Heart": 810, "tr_Horn": 812}


def trophy_records(objects):
    ids = {name: tid for tid, (root, name) in objects.items() if root == TROPHY}
    return {ids[n]: (i, i + 1, "high") for n, i in TROPHY_ROW.items() if n in ids}


# --- 7. medicine, food and water ------------------------------------------------------------

# Each consumable line is one block of texts.xml: six level bands, a name row
# and a description row each, in the order of the bands in the internal
# names. The wiki matched only part of them by name (rule 8), and wrongly
# where a page title is also somebody's name: "Караванщик" went to an NPC's
# row, "Пластиковая бутылка" to a piece of junk's. So these are pinned by
# hand. The evidence, checked row by row: each description ends in
# "Расход ОД: N", and N equals the action points the wiki's tables give for
# the lines it did link (bandages 6..16, energy drinks 8..23, injectors
# 5..10); the "(5) (P)" / "(20) (G)" / "(10)" marks of the names agree with
# the _P / _G / x10 of the internal ones; and the client's icons draw what
# the names say (a root marked "ЕДА" for Med_Pacific_Heal_0_3_A).
HEAL_BANDS = ("0_3", "4_7", "8_11", "12_15", "16_19", "20")
HEAL_BLOCKS = (
    ("Med_Pacific_Heal_%s_A", 320),      # Корень Маниока .. Консерва
    ("Med_Pacific_Heal_%s_Ax10", 332),   # Корни Маниока (10) .. Продуктовый Набор (10)
    ("Med_Pacific_Rest_%s_A", 344),      # Пластиковая бутылка (10) .. Питьевая система (10)
    ("Med_Pacific_HR_%s_G", 356),        # Аптечка «Эгоист» (20) (G) .. «Спасатель»
    ("Med_Battle_Heal_%s_A", 368),       # Кусок тряпки .. Противошоковый Комплекс
    ("Med_Battle_Rest_%s_A", 380),       # «Второе Дыхание» .. «Красная Буря»
    ("Med_Battle_HR_%s_P", 392),         # Аптечка «Мини» (5) (P) .. «Спецназ»
    ("Med_Battle_HR_%s_G", 404),         # Б.Т.Р. (G) .. С.У.П.Е.Р. (G)
)
# Single rows: internal name -> (name row, description row). "20 доз Б.Т.Р.
# (G)" .. "20 доз С.У.П.Е.Р. (G)" (450-455) have no description of their own;
# a pack is twenty doses of the injector, so it shows the injector's (405 ..
# 415, the same "Расход ОД"). The bar sits at 464-475, a name and its
# description each.
HEAL_ROWS = dict(
    [("Med_Battle_HR_%s_G_Pack" % b, (450 + k, 405 + 2 * k)) for k, b in enumerate(HEAL_BANDS)]
    + [("Med_Battle_HR_20_G_Pack1000", (456, 457)),
       ("lava_cola", (464, 465)), ("beer", (466, 467)), ("shaurma", (468, 469)),
       ("whisky", (470, 471)), ("vodka", (472, 473)), ("tequila", (474, 475))])
AP_ROW = re.compile(r"Расход ОД: </b>\d+$")


def heal_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == HEAL}
    rows = {}
    for pattern, start in HEAL_BLOCKS:
        for k, band in enumerate(HEAL_BANDS):
            rows[pattern % band] = (start + 2 * k, start + 2 * k + 1)
    rows.update(HEAL_ROWS)
    out = {}
    for name, (nid, did) in sorted(rows.items()):
        # A guard against a texts.xml other than the one these rows were read
        # off: a name row is short and plain, a Med_* description states its
        # action points.
        if len(T[nid]) > 60 or "<" in T[nid] or (
                name.startswith("Med_") and not AP_ROW.search(T[did])):
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no heal item %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7b. the knife line -----------------------------------------------------------------------

# The shop knives are one run of texts.xml, 1488-1580, level by level, and
# rule 8 read them wrongly: the wiki calls a (G) copy by its plain twin's
# name and rule 8 ignores the mark, so every gold knife took the plain row
# ("Кухонный нож" twice on one stall); and the wiki's Тесак article carries
# the sharpened copy's description, which pulled both Тесак types onto
# "Тесак (G)$Острый". So the run is pinned by hand, like the medicine.
#
# From level 4 on a level is nine rows: the plain name and its description,
# the (G) name (no description of its own -- it shows the plain one's), then
# three "(G)$<mod>" names each followed by its description. The evidence:
# the wiki's articles, matched to the types by icon (knife_lvl4_A.png is the
# Кухонный нож (A) picture), give "Ближний бой N" in exactly this order;
# the (G) of a name agrees with the _G of the type; "$Острый" is the
# sharpened blade ("бритвенно острую заточку", and the "Заточка ...$BP"
# blueprints) and its wiki table (Mod III) has more damage for the same AP --
# _G_damage; "$Эргономичный" is the balanced handle, fewer AP (Mod II) --
# _G_actionpoint; and both together _G_damage_actionpoints. Level 2 is the
# odd one: its plain knife is "Заточка" and its gold one "Самодельный Нож
# (G)", two articles with an icon each, both "Ближний бой 2". Level 1 (Шило)
# has no gold copy in objects.xml either, and level 0 (knife_lvl0_A, the
# wiki's Булыжник) no row at all.
KNIFE_MODS = (("G_damage", "Острый"), ("G_actionpoint", "Эргономичный"),
              ("G_damage_actionpoints", "Острый и Эргономичный"))


def knife_rows():
    """internal name -> (name row, description row, the row's tier)."""
    rows = {"knife_lvl1_A": (1488, 1489, "A"), "knife_lvl2_A": (1490, 1491, "A"),
            "knife_lvl2_G": (1492, 1493, "G")}
    for j, (mod, _word) in enumerate(KNIFE_MODS):
        rows["knife_lvl2_" + mod] = (1494 + 2 * j, 1495 + 2 * j, mod)
    for k, level in enumerate(range(4, 21, 2)):
        s = 1500 + 9 * k
        rows["knife_lvl%d_A" % level] = (s, s + 1, "A")
        rows["knife_lvl%d_G" % level] = (s + 2, s + 1, "G")
        for j, (mod, _word) in enumerate(KNIFE_MODS):
            rows["knife_lvl%d_%s" % (level, mod)] = (s + 3 + 2 * j, s + 4 + 2 * j, mod)
    return rows


def knife_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == COLD_ARM}
    rows = knife_rows()
    # "knife_lvl4" -> the text of its (G) name row, which each mod row repeats
    gold = {name[:-len("_G")]: T[nid] for name, (nid, _did, tier) in rows.items()
            if tier == "G"}
    out = {}
    for name, (nid, did, tier) in sorted(rows.items()):
        # A guard against a texts.xml other than the one these rows were read
        # off: each row must say what its place in the run says it is.
        text = T[nid]
        if tier == "A":
            ok = "(G)" not in text and "$" not in text
        elif tier == "G":
            ok = text.endswith(" (G)")
        else:
            level = re.match(r"knife_lvl\d+", name).group(0)
            ok = text == "%s$%s" % (gold.get(level), dict(KNIFE_MODS)[tier])
        if not ok or len(text) > 60 or "<" in text or len(T[did]) < 30 or "$" in T[did]:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no cold arm %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7c. the Nubian mine's loot ---------------------------------------------------------------

# The two things the mine's marauders drop (data/loot_manual.json, the owner's
# decision of 2026-09-25). Rule 8 cannot reach either: data/items_wiki.json
# has no record of them, the one article writing its figures as sections the
# extractor does not read, the other carrying an icon named after no type.
#
# Gold_sand (2258) is "Золотой песок" at 7352, and 7353 is its bag ("именно
# такими песчинками и наполнен этот мешочек"), and the run 7352-7361 goes the
# way the types 2258-2263 do (Gold_sand, Meds, Valuable_clock, Science_book,
# Searchlight, Glasses: "Золотой песок", a text on medicines, "Дорогие
# часы", "Фонарик", "Очки", descriptions between). The three emeralds are the run
# 7241-7246 -- "Треснутый изумруд", "Небольшие изумруды", "Крупный изумруд",
# each with its description -- and objects.xml names them cracked_emerald,
# small_emerald and fine_emerald (3160, 3159, 3161): the name says which row
# is whose. Only the one the mine drops is pinned here.
MINE_ROWS = {"Gold_sand": (7352, 7353, "Золотой песок"),
             "small_emerald": (7243, 7244, "Небольшие изумруды")}


def mine_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == TRASH}
    out = {}
    for name, (nid, did, text) in sorted(MINE_ROWS.items()):
        # A guard against a texts.xml other than the one these rows were read
        # off: the name row is the name, the one after it a description.
        if T[nid] != text or len(T[did]) < 30 or "$" in T[did] or "<" in T[did]:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no simple object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7d. the gold ingots ----------------------------------------------------------------------

# The 1-ounce ingot is what the Nubian valley's boss drops, two at a time,
# and Джеррах cashes in (data/loot_manual.json, data/quests.json 10; the
# owner's decisions of 2026-09-25 and 2026-10-11, the 5-ounce one until
# then); its 5- and 10-ounce siblings are pinned beside it, at no cost,
# so that no ingot ever reaches a player under its internal name. Rule 8
# cannot reach them: data/items_wiki.json has no record of the three, their
# articles carrying icons named after no type (5.png, 1gold.png, 10.png).
#
# 7636-7641 are one run of three pairs -- "1 унция золота", "5 унций золота",
# "10 унций золота", each followed by "Слиток номиналом в одну / пять /
# десять золотых унций." -- and the run after it is the silver money,
# "1 пиастр" (7642, which rule 8 gives Silver_Moneta_1 11782 by its article)
# and the bars of 1, 5, 10, 50 and 100 ounces of silver (Silver_Nugget_1 ..
# _100): the game's money, named by its denomination. objects.xml has two
# series of gold ingots, and the run belongs to the one with a 1-ounce bar:
# New_Gold_Ingot_1, _5, _10 (7620, 4796, 4797), whose icons are gold bars
# stamped 1, 5 and 10 (res/classes/SimpleObject/New_Gold_Ingot_*/ico.swf).
# The older Gold_Ingot_5 and _10 (3562, 3563) draw a red-and-white lollipop
# in the client instead -- the "Леденец" of the two rows before the run,
# 7634/7635 -- so they are no ingots a player would recognise, and neither
# takes these rows. The wiki's three articles of those titles quote the same
# descriptions word for word.
GOLD_INGOT_ROWS = {"New_Gold_Ingot_1": (7636, 7637, "1 унция золота"),
                   "New_Gold_Ingot_5": (7638, 7639, "5 унций золота"),
                   "New_Gold_Ingot_10": (7640, 7641, "10 унций золота")}


def gold_ingot_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == TRASH}
    out = {}
    for name, (nid, did, text) in sorted(GOLD_INGOT_ROWS.items()):
        # The same guard as the mine's: a texts.xml other than the one these
        # rows were read off fails here, not in a player's tooltip.
        if T[nid] != text or not T[did].startswith("Слиток номиналом") or "$" in T[did]:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no simple object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7e. what the Nubian valley's creatures and quests leave in a bag --------------------------

# The dogs', rats' and antelopes' parts (mobs.ANIMAL_LOOT) and the things the
# valley's quests send the player to take off a creature (data/loot_manual.json,
# the "Квестовый" rows): the owner's «давай готовь квесты все», 2026-09-26.
# Most of them reached the player under objects.xml's own words -- qMedicaments,
# qUSM, AntilopeMeat -- since data/items_wiki.json has no record of them.
#
# Two runs of texts.xml name them, a name and its description each, in the
# order objects.xml numbers the types. 6097-6110 are "Мясо животного" (hot-dog
# meat), "Собачий клык", "Собачья шкура", "Кость животного", "Мясо антилопы",
# "Шкура антилопы", "Рог антилопы": DogMeat, DogFang, DogSkin, BrittleBone,
# AntilopeMeat, AntilopeSkin, AntilopeHorn (216-219, 224-226), one to one. And
# 6150-6165 are "Туша антилопы" (qAntilopeMeat 227), "Филей антилопы", then
# "Ствол оружия", "УСМ", "Железный затвор", "Рукоятка", "Медикаменты",
# "Бумага с посланием": qBarrel, qUSM, qBreechblock, qHandle, qMedicaments,
# qMessagePaper (228-233) -- the parts Мастер Норман's «Похищенный груз (часть
# 2)» lists as 'Железный ствол с рамой, УСМ, Железный Затвор, Рукоятку' (59854),
# and the medicaments of its part 3. The rat's tail, "Крысиный хвост" 6089, heads
# the rat's own run (tail, skin, skull, meat) and is RatTail (3216) by its name;
# the rat king, "Крысиный король" 6344, is qRatKing (3218) by its name, between
# "Точильный камень" (qGrindstone 3217, which rule 8 already finds) and the next
# quest's things. Rule 8 found some of them by the wiki's name alone and without
# a description; here each takes both. Бумага с посланием (233), which rule 8
# already ties to both rows, is left to it. And the old chip Доктор Гофус's
# «Сгоревшая микросхема» asks for (texts.xml 59742, 'Старую микросхему'):
# "Старая микросхема" 8327, 'Пыльная микросхема, извлеченная из неизвестного
# устройства.', is old_chip (3179) by its name, in a run of junk that keeps
# objects.xml's order there -- sewing_kit "Набор иголок" 8326 before it --
# and the wiki's article of the thing has the same description.
VALLEY_ROWS = {"DogMeat": (6097, 6098, "Мясо животного"),
               "DogFang": (6099, 6100, "Собачий клык"),
               "DogSkin": (6101, 6102, "Собачья шкура"),
               "BrittleBone": (6103, 6104, "Кость животного"),
               "AntilopeMeat": (6105, 6106, "Мясо антилопы"),
               "AntilopeSkin": (6107, 6108, "Шкура антилопы"),
               "AntilopeHorn": (6109, 6110, "Рог антилопы"),
               "qBarrel": (6154, 6155, "Ствол оружия"),
               "qUSM": (6156, 6157, "УСМ"),
               "qBreechblock": (6158, 6159, "Железный затвор"),
               "qHandle": (6160, 6161, "Рукоятка"),
               "qMedicaments": (6162, 6163, "Медикаменты"),
               "RatTail": (6089, 6090, "Крысиный хвост"),
               "qRatKing": (6344, 6345, "Крысиный король"),
               "old_chip": (8327, 8328, "Старая микросхема")}


def valley_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == TRASH}
    out = {}
    for name, (nid, did, text) in sorted(VALLEY_ROWS.items()):
        # The same guard as the mine's: the name row is the name, the row
        # after it a description rather than the next thing's name.
        if T[nid] != text or did != nid + 1 or "$" in T[did] or "<" in T[did] \
                or T[did] in {t for _n, _d, t in VALLEY_ROWS.values()}:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no simple object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7f. the things of Вади-Хальфа's quests -----------------------------------------------------

# The Halfa restoration (2026-09-28): the things its quests hand out and ask
# for, where they still reached the player under objects.xml's own words
# (qMiniMoneySack, Magazine_p1, noob_Pistol, qTIRcertificate ...) or without a
# description. Rule 8 cannot reach them: items_wiki.json has no article of
# theirs, or one whose name is not the row's.
#
# 6167-6341 is the town's quest run, a name and its description each in the
# order objects.xml numbers the types: qAccounts 253 "Учетные записи" (6167),
# qMoneySack, qCostlyCargo, qPackage, qReports 257 "Отчеты" (6175/6176),
# qMiniMoneySack 258 "Мешочек с деньгами" (6177/6178), then qEar (whose name
# is the trophy's), qDogsMeat, qPipe ... qFul 334 "Фуль" (6212/6213), and
# at its end the ankhs, qShaurma 3189 -- whose name row the run skips: only
# its description, 6339, a copy of the food's 469, follows the golden ankh --
# and qSamogon 3190 "Бутылка самогона" (6340/6341). qEngravedSoapBar 3940 is
# "Мыло с гравировкой" (6417/6418) of the next run, after the bloody ring 3939
# (6415). Elsewhere, each by its words: Magrib_tokens 286 "Жетон Магриба"
# (6831/6832, 'Жетон Магрибских солдат'); the journal of «Верблюжьи холмы»
# (47354-47373), four parts Magazine_Chapter_1..4 (416-419, "Первая ...
# Четвертая часть журнала", 5795-5802) and sixteen pages Magazine_p1..p16
# (420-435, "Страница 1 ... 16 журнала", 5803-5834), a name and a description
# each; Берт Гаммер's training guns noob_Pistol, _Shotgun, _SMG,
# _AssaultGun, _MachineGun, _Rifle (3728-3733, "Тренировочный пистолет" ...,
# 1814-1823 and "Тренировочный Пистолет Пулемет" 2012/2013) and their
# rounds noob_ammo 3727 "Тренировочные патроны" (1094/1095, 'Могут быть
# использованы только в специальном, тренировочном оружии'); the range's
# certificate qTIRcertificate 3742 "Сертификат" (6604/6605, 'прошел Курс
# обучения тактике и стрельбе в тире Берта Гаммера'); and the quarry's stone
# block Crafted_Stone 2944 "Каменный блок" (7253/7254, 'Обтесанный каменный
# блок'), what «Каменные блоки» (61433-61436) pays for. And the tickets of
# the tickets' run 6901-6922, each by its words: the town's lottery keys,
# LoteryKey 1307 and WhLoteryKey_g 1333 (Дн and Ах have their own by level
# bands, 2646-3575), "Лотерейный билет [8]" and "Золотой лотерейный билет [8]"
# (6918, 6920; the gold one has no description of its own and shares 6919),
# where the wiki's name had given 1307 a travel ticket's row; the boat's
# ticket_WH_to_Abri 6544 "Билет в Абри из Вади Хальфы" (6901/6902). qDogsMeat
# 260 keeps the valley's "Мясо антилопы" (rule 7e): its quests hand it out.
HALFA_ROWS = {"qReports": (6175, 6176, "Отчеты"),
              "qMiniMoneySack": (6177, 6178, "Мешочек с деньгами"),
              "qFul": (6212, 6213, "Фуль"),
              "qShaurma": (468, 6339, "Шаурма"),
              "qSamogon": (6340, 6341, "Бутылка самогона"),
              "qEngravedSoapBar": (6417, 6418, "Мыло с гравировкой"),
              "Magrib_tokens": (6831, 6832, "Жетон Магриба"),
              "Magazine_Chapter_1": (5795, 5796, "Первая часть журнала"),
              "Magazine_Chapter_2": (5797, 5798, "Вторая часть журнала"),
              "Magazine_Chapter_3": (5799, 5800, "Третья часть журнала"),
              "Magazine_Chapter_4": (5801, 5802, "Четвертая часть журнала"),
              "noob_ammo": (1094, 1095, "Тренировочные патроны"),
              "noob_Pistol": (1814, 1815, "Тренировочный пистолет"),
              "noob_Shotgun": (1816, 1817, "Тренировочный дробовик"),
              "noob_SMG": (2012, 2013, "Тренировочный Пистолет Пулемет"),
              "noob_AssaultGun": (1818, 1819, "Тренировочный Автомат"),
              "noob_MachineGun": (1820, 1821, "Тренировочный Пулемёт"),
              "noob_Rifle": (1822, 1823, "Тренировочная винтовка"),
              "qTIRcertificate": (6604, 6605, "Сертификат"),
              "Crafted_Stone": (7253, 7254, "Каменный блок"),
              "LoteryKey": (6918, 6919, "Лотерейный билет [8]"),
              "WhLoteryKey_g": (6920, 6919, "Золотой лотерейный билет [8]"),
              "ticket_WH_to_Abri": (6901, 6902, "Билет в Абри из Вади Хальфы")}
HALFA_ROWS.update(("Magazine_p%d" % k, (5801 + 2 * k, 5802 + 2 * k, "Страница %d журнала" % k))
                  for k in range(1, 17))
# The Магриб base's quests (147, 153, 155) and «Быть Техногиком: инструменты
# ученого» (188): the sleeping bag Касим pays, the wire, clips, bolts and nuts
# Сейид asks, the wood and rubber of «Деловые партнеры», Мария's ruler --
# each objects.xml name once, each row a name with its description next to
# it, named by the quests' own words (the integration of 2026-09-28; the
# packages left them showing their internal names).
HALFA_ROWS.update({"old_flea_bag": (460, 461, "Старый спальный мешок"),
                   "wire": (8322, 8323, "Проволока"),
                   "clip": (8349, 8350, "Скрепки"),
                   "bolt": (8351, 8352, "Болты"),
                   "screw": (8353, 8354, "Гайки"),
                   "piece_of_wood": (8356, 8357, "Кусок Древесины"),
                   "piece_of_rubber": (8314, 8315, "Кусок резины"),
                   "qLineika": (6257, 6258, "Линейка")})
# The self-teachers' six parts (objects.xml 5041-5106, <Skill>_p1.._p6):
# what Тиль's trainings pay for the certificate (4, 1829, 1895, 1971, 2128,
# 366) and Бюльбюль-Оглы's assemblies ask (368-378). Each skill's block of
# the original is its «Самоучитель: …» row, for some its description, and
# then «<Skill> N часть» and its words, N = 1..6 (texts.xml 5881-6027).
SELF_TEACHER_PARTS = (("Pistols", 5881, "Пистолеты"), ("Shotguns", 5894, "Дробовики"),
                      ("SMG", 5907, "Пистолет-Пулемёты"), ("AssaultRifle", 5920, "Автоматы"),
                      ("Rifle", 5933, "Винтовки"), ("Machineguns", 5946, "Пулеметы"),
                      ("FirstAid", 5960, "Первая Помощь"), ("Surgery", 5974, "Хирургия"),
                      ("MartialArts", 5988, "Рукопашный бой"), ("Knives", 6002, "Ножевой бой"),
                      ("Mining", 6016, "Горное Дело"))
HALFA_ROWS.update(("%s_p%d" % (obj, k), (first + 2 * (k - 1), first + 2 * (k - 1) + 1,
                                          "%s %d часть" % (word, k)))
                  for obj, first, word in SELF_TEACHER_PARTS for k in range(1, 7))


def halfa_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items()}
    names = {text for _n, _d, text in HALFA_ROWS.values()}
    out = {}
    for name, (nid, did, text) in sorted(HALFA_ROWS.items()):
        # The same guard as the valley's: the name row is the name, and the
        # description row is prose -- no "$", no bracket, not another name.
        if T[nid] != text or "$" in T[did] or "[" in T[did] or T[did] in names or len(T[did]) < 20:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7g. the belts ----------------------------------------------------------------------------

# The belts Ваккас sells (data/npcs.json 1204) and their gold copies. Rule 8
# read them off the wiki, whose article names the plain belt and lists both
# copies under it (data/wiki_links.py MANUAL: "Подсумки снайпера" ->
# belt_rifles, belt_rifles_g), so the gold copy took the plain row, the
# knives' trouble of rule 7b. texts.xml 47822-47856 is the belts' run, five
# rows a line -- the plain name, its "(G)", the "(G). МОД. А1." copy with its
# description, then "М2" -- so the (G) row is the one after the plain one.
# Neither has a description of its own (only the МОД copy does). Pinned here
# for the four lines on sale (2026-09-28), and since the owner's «добавь еще
# голдовые подсумки» (2026-10-11) for the other three too, whose articles
# are now linked and whose belts Алима, Галия and Ваккас sell: the automatic
# rifles' (47822), the unarmed fighters' (47837, belt_knife: its gold mod
# belt_knife_g_mod is «Подсумки рукопашника МОД. А1.») and the machine
# guns' (47842, «пулемётчика» with ё where the wiki writes е).
BELT_ROWS = {"belt_assault_rifles": (47822, "Подсумки автоматчика"),
             "belt_assault_rifles_g": (47823, "Подсумки автоматчика (G)"),
             "belt_knife": (47837, "Подсумки рукопашника"),
             "belt_knife_g": (47838, "Подсумки рукопашника (G)"),
             "belt_machineguns": (47842, "Подсумки пулемётчика"),
             "belt_machineguns_g": (47843, "Подсумки пулемётчика (G)"),
             "belt_rifles": (47827, "Подсумки снайпера"),
             "belt_rifles_g": (47828, "Подсумки снайпера (G)"),
             "belt_sub_machineguns": (47832, "Подсумки спецназовца"),
             "belt_sub_machineguns_g": (47833, "Подсумки спецназовца (G)"),
             "belt_shotguns": (47847, "Подсумки охотника"),
             "belt_shotguns_g": (47848, "Подсумки охотника (G)"),
             "belt_pistols": (47852, "Подсумки пистолетные"),
             "belt_pistols_g": (47853, "Подсумки пистолетные (G)")}


def belt_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == WEAR}
    out = {}
    for name, (nid, text) in sorted(BELT_ROWS.items()):
        if T[nid] != text:
            raise SystemExit("texts.xml row %d does not look like %s" % (nid, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no wear item %s" % name)
        out[by_name[name]] = (nid, None, "high")
    return out


# --- 7h. the miner's clothes -------------------------------------------------------------

# What «Шахтерская одежда» (5181, texts.xml 10430) sells: Вади-Хальфа's
# miner's pieces helm_/shirt_/armor_/pants_/boots_minecraft_U_LVL_WH_A_mod00
# (objects.xml 34480-34484) and their gold copies _G_ (34490-34494), an
# icon each in classes/WearItem/. texts.xml 22856-22875 is their run in slot
# order: the five A names, each followed by its description, then the five
# P names and the five G names, with none of their own -- a gold copy takes
# its A twin's, as the gold lottery ticket does (rule 7f). The P copies
# (34485-34489) are left out: the owner took premium out of the game
# (items.premium); so are Абри's run ([AB], 22876-) and the other towns'.
# Pinned 2026-09-28.
MINER_SLOTS = (("helm", "Каска шахтёра"), ("shirt", "Подстёжка шахтёра"),
               ("armor", "Жилет-помощник шахтёра"), ("pants", "Штаны шахтёра"),
               ("boots", "Бутсы"))
MINER_A, MINER_G = 22856, 22871


def miner_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == WEAR}
    out = {}
    for k, (slot, word) in enumerate(MINER_SLOTS):
        did = MINER_A + 2 * k + 1
        for variant, nid in (("A", MINER_A + 2 * k), ("G", MINER_G + k)):
            name = "%s_minecraft_U_LVL_WH_%s_mod00" % (slot, variant)
            if T[nid] != "%s[WH][%s][мод00]" % (word, variant) \
                    or "[" in T[did] or "$" in T[did] or len(T[did]) < 20:
                raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
            if name not in by_name:
                raise SystemExit("objects.xml has no wear item %s" % name)
            out[by_name[name]] = (nid, did, "high")
    return out


# --- 7i. the prison's armband ------------------------------------------------------------

# What the prisoners of Вади-Хальфа's uprising carry and its medics pay for
# (data/schedule.json, data/quests.json 164-168): Red_Bandage (objects.xml
# 2476) is texts.xml 7323 "Красная повязка ВХ", 7324 its description
# ("Красная повязка, сорванная с ваших соперников"), the first of the run
# ВХ, ДН, АХ (7323, 7325, 7326) whose other two are Red_Bandage_DN/_AH
# (4165, 4166), the other prisons'. Pinned 2026-09-28.
PRISON_ROWS = {"Red_Bandage": (7323, 7324, "Красная повязка ВХ")}


def prison_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items()}
    out = {}
    for name, (nid, did, text) in sorted(PRISON_ROWS.items()):
        if T[nid] != text or "$" in T[did] or "[" in T[did] or len(T[did]) < 20:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7i. the plant's things -------------------------------------------------------------

# The mines' ore, sorted ore and the base's sacks (server/production.py, the
# owner's «всё отложенное», 2026-09-28), and the quarry's polishing mix with
# its four components («Полированные камни», «Создать Полировочную смесь»,
# quests.json 320-323). Rule 8 cannot reach any of them: the wiki's only
# articles are the (АХ) ores', whose icons are named after no type.
#
# texts.xml 7189-7240 is the chain's run, family by family in objects.xml's
# order -- lead, saltpetre, copper; sorted lead, saltpetre, copper; bullets,
# powder, cases -- each five names, one a city in the order «(ВХ)», «(Аб)»,
# «(Дн)», «(АХ)», «(Мр)», with a description after the first where the
# family has one. objects.xml numbers each family _1 to _5 the same way, the
# fifth added later with its city (plumbum_ore_5 ... shell_sack_5, 5602-5610,
# Мероэ's). A sorted saltpetre or copper has no words of its own and shows
# its ore's, as a gold copy shows its plain twin's (rule 7f). Then
# 7253-7265: the quarry's blocks -- «Каменный блок» (rule 7f), «Обтесанный
# песчаник» and «Обтесанный мрамор» (Crafted_Stone_DN/_AH) -- «Полировочная
# смесь» (Catalizator) and «Компонент №1..4» (Catalizator_part1..4), the
# four sharing the first's words («Один из четырех необходимых компонентов
# для создания Полировочной смеси»). Pinned 2026-09-28.
PRODUCTION_CITIES = ("ВХ", "Аб", "Дн", "АХ", "Мр")
PRODUCTION_FAMILIES = (("plumbum_ore", 7189, 7190), ("nitre_ore", 7195, 7196),
                       ("copper_ore", 7201, 7202), ("plumbum_ore_sorting", 7207, 7208),
                       ("nitre_ore_sorting", 7213, 7196), ("copper_ore_sorting", 7218, 7202),
                       ("bullet_sack", 7223, 7224), ("powder_sack", 7229, 7230),
                       ("shell_sack", 7235, 7236))
POLISH_ROWS = {"Crafted_Stone_DN": (7255, 7256, "Обтесанный песчаник"),
               "Crafted_Stone_AH": (7257, 7258, "Обтесанный мрамор"),
               "Catalizator": (7259, 7260, "Полировочная смесь"),
               "Catalizator_part1": (7261, 7262, "Компонент №1"),
               "Catalizator_part2": (7263, 7262, "Компонент №2"),
               "Catalizator_part3": (7264, 7262, "Компонент №3"),
               "Catalizator_part4": (7265, 7262, "Компонент №4")}


def production_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items() if root == TRASH}
    out = {}
    for family, first, did in PRODUCTION_FAMILIES:
        # The five names: the first row, then the next rows that are names of
        # the family (its description, if any, is skipped).
        nids, nid = [first], first + 1
        while len(nids) < len(PRODUCTION_CITIES):
            if T[nid].startswith("("):
                nids.append(nid)
            nid += 1
        for k, (city, nid) in enumerate(zip(PRODUCTION_CITIES, nids)):
            name = "%s_%d" % (family, k + 1)
            if not T[nid].startswith("(%s)" % city) or "$" in T[nid] \
                    or T[did].startswith("(") or len(T[did]) < 20:
                raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
            if name not in by_name:
                raise SystemExit("objects.xml has no simple object %s" % name)
            out[by_name[name]] = (nid, did, "high")
    for name, (nid, did, text) in sorted(POLISH_ROWS.items()):
        if T[nid] != text or "$" in T[did] or len(T[did]) < 20:
            raise SystemExit("texts.xml rows %d/%d do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no simple object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 7i. the wild and the leftovers -------------------------------------------------------

# What the treasure digs, Уорхол's collection and the rides to other towns
# (data/quests.json 250-286) hand out and ask for, pinned 2026-09-28:
#   * Дирижер's seven maps qMapTreasureIsland_1..7 (5504-5510), one name,
#     «Карта сокровищ» (6047), and seven descriptions in objects.xml's order,
#     6048-6054, each with its skull's coordinates -- 5876х2019 ... 5972х1735
#     (the fourth, the camel stables 139, where TreasureIsland_4 stands) ...
#     5862х1846. The wiki's article of the last had given all seven its name.
#   * the Бункер Ламантина collection collection_lamantin_1..6 (7030-7035):
#     «Планшет», «Читательский билет», «Карточка из библиотеки»,
#     «Энциклопедии», «Очки ботаника», «Штурвал от гермодвери», each «(Коллекция)»,
#     8474-8485, a name and its description, in the order of the wiki's own
#     list; objects.xml numbers the permanent collections in the order
#     texts.xml writes them (12 June, the two drivers', VDV, 1 September,
#     Ламантин).
#   * the tickets of the tickets' run 6901-6917 that rule 7f leaves: Абри to
#     Вади Хальфа and Донгола and back (ticket_Abri_to_WH, _Abri_to_DN,
#     _DN_to_Abri: 6903-6908), and Абу-Хамед's by their internal names:
#     ah_dongola_ticket_g "Билет в Донголу из Абу-Хамеда" (6911, no
#     description), ah_Meroe_ticket_g and Meroe_ah_ticket_g to and from
#     Мероэ (6912-6915), ah_ticket "Билет в Абу-Хамед из Донголы" (6916/6917).
WILD_ROWS = {"qMapTreasureIsland_%d" % (k + 1): (6047, 6048 + k, "Карта сокровищ")
             for k in range(7)}
WILD_ROWS.update(("collection_lamantin_%d" % (k + 1), (8474 + 2 * k, 8475 + 2 * k, word))
                 for k, word in enumerate(("Планшет (Коллекция)", "Читательский билет (Коллекция)",
                                           "Карточка из библиотеки (Коллекция)",
                                           "Энциклопедии (Коллекция)", "Очки ботаника (Коллекция)",
                                           "Штурвал от гермодвери (Коллекция)")))
WILD_ROWS.update({"ticket_Abri_to_WH": (6903, 6904, "Билет в Вади Хальфу из Абри"),
                  "ticket_Abri_to_DN": (6905, 6906, "Билет в Донголу из Абри"),
                  "ticket_DN_to_Abri": (6907, 6908, "Билет в Абри из Донголы"),
                  "ah_dongola_ticket_g": (6911, None, "Билет в Донголу из Абу-Хамеда"),
                  "ah_Meroe_ticket_g": (6912, 6913, "Билет в Мероэ из Абу-Хамеда"),
                  "Meroe_ah_ticket_g": (6914, 6915, "Билет в Абу-Хамед из Мероэ"),
                  "ah_ticket": (6916, 6917, "Билет в Абу-Хамед из Донголы")})


def wild_records(T, objects):
    by_name = {name: tid for tid, (root, name) in objects.items()}
    out = {}
    for name, (nid, did, text) in sorted(WILD_ROWS.items()):
        # The name row is the name; the description, where there is one, is
        # prose -- no "$", no bracket, not a name of the run.
        if T[nid] != text or (did is not None and (
                "$" in T[did] or "[" in T[did] or T[did].startswith("Билет")
                or len(T[did]) < 20)):
            raise SystemExit("texts.xml rows %s/%s do not look like %s" % (nid, did, name))
        if name not in by_name:
            raise SystemExit("objects.xml has no object %s" % name)
        out[by_name[name]] = (nid, did, "high")
    return out


# --- 8. wiki names ------------------------------------------------------------------------

def wiki_norm(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace('\\"', '"').replace("ё", "е").replace("Ё", "Е")
    s = re.sub(r"[«»\"“”]", '"', s)
    return re.sub(r"\s+", " ", s).strip().lower()


def wiki_row_name(s):
    """A row as a name: no $-suffix, no [..] tags, no (G)/(RW)-style marks."""
    s = s.split("$")[0]
    s = re.sub(r"\s*(\[[^\]]*\]|\([A-Za-zА-Яа-я]{1,3}\))\s*", " ", s)
    return wiki_norm(s)


def wiki_name_variants(name):
    a = wiki_norm(name)
    yield a
    yield re.sub(r"\((\d+)\s*у\)", r"[\1у]", a)
    yield re.sub(r"\s*\((\d+)\s*у\)", r" [\1у]", a)


def wiki_records(T, objects, wiki, skip):
    by_name, by_desc, by_full = (collections.defaultdict(list) for _ in range(3))
    for i, t in enumerate(T):
        by_name[wiki_row_name(t)].append(i)
        by_full[wiki_norm(t.split("$")[0])].append(i)
        if len(t) > 25:
            by_desc[wiki_norm(t)].append(i)
    out = {}
    for key, rec in sorted(wiki.items(), key=lambda kv: int(kv[0])):
        tid = int(key)
        if tid not in objects or tid in skip:
            continue
        name, desc = rec.get("name_ru"), rec.get("desc_ru")
        ids = by_name.get(wiki_norm(name), []) if name else []
        dids = set(by_desc.get(wiki_norm(desc), [])) if desc else set()
        pair = [n for n in ids if n + 1 in dids]
        only_desc = min(dids) if len(dids) == 1 else None
        if len(pair) == 1:
            out[tid] = (pair[0], pair[0] + 1, "high")
            continue
        if not pair and len(ids) == 1:
            out[tid] = (ids[0], only_desc, "medium")
            continue
        if not name:
            continue
        # The name with its level in brackets: "Ботинки (10у)" -> "ботинки [10у]".
        for v in wiki_name_variants(name):
            full = by_full.get(v)
            if full:
                if len(full) == 1:
                    n = full[0]
                    did = n + 1 if n + 1 in dids else (only_desc if not ids else None)
                    out[tid] = (n, did, "medium")
                break
    return out


# --- assembly ------------------------------------------------------------------------------

RULE = ("type_id -> original texts.xml rows (html-unescaped, otherwise verbatim). "
        "Firearm lines <-> 'Имя[тир][уровень]$Класс' blocks per (class, level): lines with "
        "_pm/_gold copies <-> std blocks (A+P+G and [M] or >=12 mod descriptions), without "
        "<-> Q/RW blocks, mob-only <-> [M] blocks, both sides ascending (index / row id); "
        "high = equal counts, medium = fewer blocks. Then clan copies, USSR/NY2016 pistols, "
        "ammo (calibre + quality code), wear (Mob, Bs_U), the sets Bs/Set/Exzo of levels "
        "0-8 by their words (Колонист[2] named as level 0), trophies 800..813, medicine/food/"
        "water blocks 320..415 by level band with the packs 450..457 and the bar 464..475, "
        "the knife line 1488..1580 level by level (A, G, three G mods), "
        "the Nubian mine's gold sand 7352/7353 and small emeralds 7243/7244, "
        "the gold ingots New_Gold_Ingot_1/5/10 7636..7641, "
        "the Nubian valley's animal parts and quest things 6089..6163 and 6344, "
        "Вади-Хальфа's quest things (its run 6167..6341, the journal 5795..5834, the training "
        "guns 1094..1823 and 2012, the certificate 6604, the stone block 7253, "
        "the lottery and boat tickets 6901..6920), "
        "the belts on sale and their (G) copies 47822..47853, "
        "Вади-Хальфа's miner's clothes and their (G) copies 22856..22875, "
        "the plant's ore, sorted ore and sacks of the five cities 7189..7240 and the quarry's "
        "stones, polishing mix and its components 7255..7265, "
        "and an exact wiki name for the rest. See data/build_orig_items.py.")


def build(texts_path):
    if not os.path.isfile(os.path.join(RES, "database", "objects.xml")):
        raise SystemExit("set LAVA_RES to the client's res directory (database/objects.xml)")
    T, md5, size = load_texts(texts_path)
    objects = load_objects()
    families = load_json(os.path.join(HERE, "firearm_families.json"))["lines"]
    wiki = load_json(os.path.join(HERE, "items_wiki.json"))["items"]

    fire = Firearms(T, families)
    family_types = {t for rec in families.values()
                    for t in list(rec["members"].values()) + list(rec["extra"].values())}
    rules = [("firearm_line", fire.records()),
             ("firearm_clan", clan_records(fire, clan_blocks(T, fire))),
             ("event_pistol", event_records(T, objects)),
             ("ammo", ammo_records(T, objects)),
             ("wear", wear_records(T, objects)),
             ("wear_set", wear_set_records(T, objects)),
             ("trophy", trophy_records(objects)),
             ("heal", heal_records(T, objects)),
             ("knife", knife_records(T, objects)),
             ("mine_loot", mine_records(T, objects)),
             ("gold_ingot", gold_ingot_records(T, objects)),
             ("valley_loot", valley_records(T, objects)),
             ("halfa_quest", halfa_records(T, objects)),
             ("belt", belt_records(T, objects)),
             ("miner_wear", miner_records(T, objects)),
             ("prison", prison_records(T, objects)),
             ("production", production_records(T, objects)),
             ("wild", wild_records(T, objects))]
    found, owner = {}, {}
    for rule, recs in rules:
        for tid, rec in recs.items():
            if tid in owner:
                raise SystemExit("type %d claimed by %s and %s" % (tid, owner[tid], rule))
            owner[tid] = rule
            found[tid] = rec
    skip = set(owner) | family_types
    for tid, rec in wiki_records(T, objects, wiki, skip).items():
        owner[tid] = "wiki_name"
        found[tid] = rec

    items, counts, by_rule = {}, {}, collections.Counter()
    for tid in sorted(found):
        nid, did, conf = found[tid]
        if conf not in KEEP or tid not in objects:
            continue
        root = ROOT_NAME[objects[tid][0]]
        items[str(tid)] = {
            "name": T[nid] if nid is not None else None,
            "desc": T[did] if did is not None else None,
            "name_id": nid, "desc_id": did, "confidence": conf, "root": root}
        counts.setdefault(root, collections.Counter())[conf] += 1
        by_rule[owner[tid], conf] += 1
    meta = {"source": texts_path, "source_md5": md5, "source_size": size, "rule": RULE,
            "counts": {r: dict(c) for r, c in counts.items()}}
    return {"_meta": meta, "items": items}, by_rule


def main():
    """build_orig_items.py [OUT] -- OUT defaults to data/orig_items.json."""
    path = os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_TEXTS
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    data, by_rule = build(path)
    dump_json(out, data)
    for (rule, conf), n in sorted(by_rule.items()):
        print("%-14s %-6s %5d" % (rule, conf, n))
    print("%d types -> %s" % (len(data["items"]), out))


if __name__ == "__main__":
    main()
