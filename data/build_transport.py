"""Build data/transport.json: the rentable vehicles and who lets them out.

    wsl.exe -e python3 data/build_transport.py

The client carries no transport data at all. `res/transport/` holds 57 SWF
icons and `res/xml/transport.xml` is a download manifest (href/hash/size) with
nothing else in it, so every number a `ts_si` frame needs -- speed, aggro,
price, premium gate -- has to come from outside the client.

WHAT IS RECOVERED
-----------------
`data/wiki_world/transport.json` (category "Транспорт", 17 pages) carries the
annotation the client itself draws. `gpui/Annotation.as:938-960` prints
`(speed_mod - 1) * 100` under "Скорость" and `(1 - aggro_mod) * 100` under
"Шанс перехвата", which is exactly the wiki's own table, so the conversion
back is exact and not a guess:

    Скорость        +70%    ->  speed_mod = 1.7
    Шанс перехвата  -15%    ->  aggro_mod = 0.85
    Премеумность    Да/Нет  ->  premium   = 1/0
    Базовая цена    0.1 G   ->  g_cost    = 10   (hundredths, per day)
                    12000 Афро -> cost     = 12000 (afro, per day)

A page with several columns is one vehicle sold in several grades (the camel
has three, the motorcycle two). The column taken here is the first that is
NOT premium-gated, so the basic ladder stays rentable by a plain account;
every column is kept under "wiki_columns" for whoever wires grades later.

`data/npc_wiki.json` already resolves each wiki NPC page to a spawn type id
and lists the vehicles under its "Аренда транспорта" heading, so who rents
what is recovered too: Шихаб (`wh_Lessor` 653, Вади-Хальфа, confidence
verified) and Марат (`dn_Lessor` 655 / `Abri_Lessor` 1173, medium) all offer
the same seven.

The one-day cap is the client's: `TransRentInterface.maxValue = 365`.

WHAT IS DESIGNED, AND WHY
-------------------------
1. **Persistent vehicle IDs and image IDs differ.** Types 1..7 retain the
   original reconstructed rental ladder (and existing saved rentals). The
   art was visually inspected on 2026-10-28 using the original SWFs:
   donkey=5, camel=1, motorcycle=6, UAZ=2, Hummer=3, buggy=4, Larva=7.
   ICON_RES stores that verified correspondence separately from ASSIGNMENT.
   Other, unavailable vehicles retain their previous image assignment;
   their art is not newly verified by this rental-yard fix.
2. **Северный олень** has an empty parameter table on the wiki (event
   transport, "Базовая цена 0 G"). Its description is word for word the
   T-34's, so it is given the T-34's numbers and no price.
3. **Кобыла** never shipped ("в продажу так и не поступила") and has no
   table at all, yet `mobs.xml` has `Lessor_Horse_I..IV`. Kept with numbers
   between the donkey's and the camel's, offered by nobody.
4. **The default set.** A lessor with no wiki page offers the same seven as
   Шихаб. That is the set `mobs.xml` gives every clan base, so it is the
   game's own idea of a stock rental yard rather than an invention here.

Every designed number is listed in the entry's "designed" field, and
"source" says wiki or designed for the whole record.
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import world  # noqa: E402

OUT = os.path.join(HERE, "transport.json")

# Client cap on the rental slider: TransRentInterface.maxValue.
MAX_DAYS = 365

# wiki page -> type id. Order recovered (see the docstring); the numbers
# themselves are the designed part and remain stable for saved rentals.
ASSIGNMENT = [
    ("Ослик Панург", 1),
    ("Верблюд", 2),
    ("Мотоцикл", 3),
    ("УАЗ", 4),
    ("Хаммер", 5),
    ("Багги", 6),
    ("Ларва", 7),
    ("Газ 67 Б", 8),
    ("Пескоход", 9),
    ("Т-34", 10),
    ("ИС-2", 11),
    ("Летающая тарелка", 12),
    ("Gold Wing GL1800A", 13),
    ("Северный олень", 14),
    ("Кобыла", 15),
    ("Крылатый Ламантин", 16),
]

# Visually verified original transport SWFs, independent of saved vehicle IDs.
# See releases/2026-10-27/TRANSPORT_ICONS.md. Never renumber ASSIGNMENT to fix art.
ICON_RES = {1: 5, 2: 1, 3: 6, 4: 2, 5: 3, 6: 4, 7: 7}

# Pages of the category that describe no vehicle.
SKIP = {"Квесты на перемещение"}

# Filled in where the wiki table is empty or missing; see the docstring.
DESIGNED = {
    "Северный олень": dict(speed_mod=3.4, aggro_mod=0.55, premium=0,
                           cost=0, g_cost=0),
    "Кобыла": dict(speed_mod=1.8, aggro_mod=0.9, premium=0,
                   cost=8000, g_cost=0),
}

# Vehicles no lessor hands out: event art, the admin's toy and the horse that
# never shipped. Kept in the table so a `ts_get_si` for one still answers.
NOT_RENTED = {"Северный олень", "Кобыла", "Крылатый Ламантин",
              "Летающая тарелка", "Пескоход", "Т-34", "ИС-2",
              "Gold Wing GL1800A"}

# What a lessor with no wiki page offers.
DEFAULT_SET = ["Ослик Панург", "Верблюд", "Мотоцикл", "УАЗ", "Хаммер",
               "Багги", "Ларва"]


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


# --- the client's own files -------------------------------------------------
def icon_ids():
    """Every `res/transport/<n>.swf`, by its number.

    The number is the image resource id sent in ts_si.res, not the saved
    vehicle type id. SSEmulator.getTransportIcon builds the path from res.
    `46_.swf` and `FatBoy.swf` are not numbers and cannot be addressed by
    the protocol at all.
    """
    folder = os.path.join(world.RES, "transport")
    out = []
    for fn in os.listdir(folder):
        stem, ext = os.path.splitext(fn)
        if ext.lower() == ".swf" and stem.isdigit():
            out.append(int(stem))
    return sorted(out)


def manifest_ids():
    """The same, as `res/xml/transport.xml` lists it."""
    path = os.path.join(world.RES, "xml", "transport.xml")
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        txt = fh.read()
    out = []
    for href in re.findall(r'href="transport/([^"]+)"', txt):
        stem, ext = os.path.splitext(href)
        if ext.lower() == ".swf" and stem.isdigit():
            out.append(int(stem))
    return sorted(out)


# --- the wiki table ---------------------------------------------------------
def _rows(wikitext):
    """The "Параметры" table as {label: [cell, ...]}, in page order."""
    m = re.search(r"==\s*Параметры\s*==\s*(\{\|.*?\n\|\})", wikitext, re.S)
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for chunk in body.split("\n|-"):
        cells = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith("|}") \
                    or line.startswith("|-"):
                continue
            cells.append(line[1:].strip())
        if len(cells) >= 2:
            out[cells[0]] = cells[1:]
    return out


def _percent(cell):
    """"+70%" -> 0.7, "-100%" -> -1.0, "" -> None."""
    m = re.search(r"([+-]?\d+(?:[.,]\d+)?)\s*%", cell or "")
    return float(m.group(1).replace(",", ".")) / 100.0 if m else None


def _price(cell):
    """"0.1 G" -> (0, 10); "12000 Афро" -> (12000, 0); "" -> None.

    Gold rides the wire in hundredths of an ounce, which is the unit
    TransRentInterface divides by when it prints `g_cost * days / 100`.
    """
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([A-Za-zА-Яа-я]+)", cell or "")
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    if unit.startswith("g") or unit.startswith("г"):
        return (0, int(round(value * 100)))
    return (int(round(value)), 0)


def _text_section(wikitext, title):
    m = re.search(r"==\s*%s\s*==\s*(.*?)(?:\n==|\Z)" % title, wikitext, re.S)
    if not m:
        return ""
    txt = m.group(1)
    # Category tags and the file/gallery furniture are page plumbing, not
    # description; they must not reach the annotation window.
    txt = re.sub(r"<gallery.*?</gallery>", " ", txt, flags=re.S)
    txt = re.sub(r"\[\[\s*(?:Категория|Category|Файл|File|Image)\s*:[^\]]*\]\]",
                 " ", txt)
    txt = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]]*)\]\]", r"\1", txt)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return " ".join(txt.split())


def columns(rows):
    """The table read as a list of grades, one dict per column."""
    speeds = rows.get("Скорость", [])
    aggros = rows.get("Шанс перехвата", [])
    prems = rows.get("Премеумность", [])
    prices = rows.get("Базовая цена", [])
    width = max([len(speeds), len(aggros), len(prems), len(prices)] or [0])
    out = []
    for i in range(width):
        def cell(lst):
            return lst[i] if i < len(lst) else ""
        speed = _percent(cell(speeds))
        aggro = _percent(cell(aggros))
        price = _price(cell(prices))
        prem = cell(prems).strip().lower()
        out.append(dict(
            speed_mod=None if speed is None else round(1.0 + speed, 3),
            # A blank interception cell is not a hole: the cheapest camel
            # simply gives no bonus, which is aggro_mod 1.
            aggro_mod=1.0 if aggro is None else round(1.0 + aggro, 3),
            aggro_blank=aggro is None,
            premium=1 if prem.startswith("да") else 0,
            cost=None if price is None else price[0],
            g_cost=None if price is None else price[1]))
    return out


def pick(cols):
    """The grade to sell: the first that no premium account gate blocks."""
    for c in cols:
        if not c["premium"]:
            return c
    return cols[0] if cols else None


# --- who rents what ---------------------------------------------------------
def lessors(name_to_type):
    """{lessor type id: [transport type id, ...]} from data/npc_wiki.json.

    Keeps a place only when its page resolved to a spawn that mobs.xml calls
    a Lessor, so a mis-resolved page cannot put a rental desk on a trader.
    """
    mt = world.mob_types()
    out, notes = {}, []
    for page, rec in sorted(load("npc_wiki.json")["npcs"].items()):
        rent = [r for r in rec.get("rent") or [] if r in name_to_type]
        if not rent:
            continue
        types = [name_to_type[r] for r in rent]
        for place in rec.get("places") or []:
            tid = place.get("type_id")
            if tid is None:
                notes.append("%s at %s: unresolved, falls back to the default set"
                             % (page, place.get("location")))
                continue
            if mt.get(tid, (None,))[0] != world.LESSOR:
                notes.append("%s at %s: type %d is not a Lessor, skipped"
                             % (page, place.get("location"), tid))
                continue
            out[tid] = types
            notes.append("%s -> %d (%s, %s): %d vehicles"
                         % (page, tid, mt[tid][1], place.get("confidence"),
                            len(types)))
    return out, notes


def main():
    pages = load("wiki_world/transport.json")["pages"]
    icons = icon_ids()
    in_manifest = set(manifest_ids())
    known = set(icons)

    types, name_to_type, report = {}, {}, []
    for page, type_id in ASSIGNMENT:
        if page in SKIP:
            continue
        if page not in pages:
            raise SystemExit("wiki has no page %r" % page)
        icon_res = ICON_RES.get(type_id, type_id)
        if icon_res not in known:
            raise SystemExit("res/transport/%d.swf does not exist" % icon_res)
        cols = columns(_rows(pages[page]))
        grade = pick(cols)
        designed = []
        rec = dict(speed_mod=None, aggro_mod=None, premium=0,
                   cost=0, g_cost=0)
        if grade:
            rec.update({k: grade[k] for k in
                        ("speed_mod", "aggro_mod", "premium", "cost", "g_cost")})
        fill = DESIGNED.get(page, {})
        for key, value in sorted(fill.items()):
            # A blank interception cell means "no bonus" on a page whose
            # table is filled in, and "nobody wrote it down" on one whose
            # table is empty. Only the second is designed over.
            blank = grade is None or rec.get(key) is None or (
                key == "aggro_mod" and grade.get("aggro_blank")
                and grade.get("speed_mod") is None)
            if blank:
                rec[key] = value
                designed.append(key)
        if rec["speed_mod"] is None or rec["cost"] is None:
            raise SystemExit("no numbers and no design for %r" % page)
        # Existing IDs retain the gold offer, available without a status.
        required_status = 0
        if type_id in (4, 5):
            rec.update(cost=0, g_cost={4: 70, 5: 90}[type_id])
        types[type_id] = dict(
            name=page, type=type_id, res=icon_res, required_status=required_status,
            speed_mod=rec["speed_mod"], aggro_mod=rec["aggro_mod"],
            premium=rec["premium"], cost=rec["cost"], g_cost=rec["g_cost"],
            max_days=MAX_DAYS,
            desc=_text_section(pages[page], "Описание"),
            source="wiki" if not designed else "wiki+designed",
            designed=sorted(designed),
            id_source="designed",
            in_manifest=icon_res in in_manifest,
            wiki_columns=cols)
        if not grade:
            types[type_id]["source"] = "designed"
        name_to_type[page] = type_id
        report.append("  %2d  %-22s speed %-6s aggro %-5s prem %d  %s"
                      % (type_id, page, rec["speed_mod"], rec["aggro_mod"],
                         rec["premium"],
                         "%d G/100" % rec["g_cost"] if rec["g_cost"]
                         else "%d афро" % rec["cost"]))

    missing = [p for p in pages if p not in SKIP and p not in name_to_type]
    by_npc, notes = lessors(name_to_type)
    default = [name_to_type[n] for n in DEFAULT_SET]
    rentable = sorted(set(default) | {t for v in by_npc.values() for t in v})
    for page in NOT_RENTED:
        if name_to_type.get(page) in rentable:
            raise SystemExit("%s must not be on a rental list" % page)

    data = {
        "_built": time.strftime("%Y-%m-%d"),
        "_license": "CC-BY-SA 3.0 (lava-online.fandom.com)",
        "_source": {
            "numbers": "data/wiki_world/transport.json",
            "lessors": "data/npc_wiki.json",
            "icons": "res/transport/*.swf, res/xml/transport.xml",
            "max_days": "TransRentInterface.maxValue",
        },
        "_note": ("Vehicle IDs stay stable for saved rentals. ts_si.res is a separate"
                  " image ID; basic rental icons visually verified 2026-10-28"
                  " (see ICON_RES in data/build_transport.py). Unavailable vehicles"
                  " retain their previous image assignment. Prices are per day;"
                  " gold in hundredths. Speed and interception are recovered from"
                  " the client annotation and wiki."),
        "max_days": MAX_DAYS,
        "icons": icons,
        "types": {str(k): v for k, v in sorted(types.items())},
        "lessors": {str(k): v for k, v in sorted(by_npc.items())},
        "default_lessor": default,
        # Same vehicles/art, distinct status-only offers. 1 G = 50,000 afro.
        "status_rentals": {
            str(offer): dict(base_type=base, required_status=status,
                             cost=types[base]["g_cost"] * 50000 // 100)
            for offer, base, status in ((17, 4, 1), (18, 5, 2))
        },
    }
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print("icons on disk: %d numeric (of %d files); manifest lists %d"
          % (len(icons), len(os.listdir(os.path.join(world.RES, "transport"))),
             len(in_manifest)))
    print("named vehicles: %d" % len(types))
    print("\n".join(report))
    if missing:
        print("wiki pages left unassigned: %s" % ", ".join(sorted(missing)))
    print("lessors bound to a type id: %d" % len(by_npc))
    for note in notes:
        print("  " + note)
    print("default rental yard: %s" % ", ".join(DEFAULT_SET))
    print("written %s" % OUT)


if __name__ == "__main__":
    main()
