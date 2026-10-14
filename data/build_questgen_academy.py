"""Build data/questgen_academy.json: the lessons of Абу-Хамед's Боевая Академия.

The owner's «сделай потом абу хамед в таком же формате» (2026-10-14), the
plan's decision 26 (abuhamed/DESIGN.md 5.6). The Академия (1295
Bunker_Univer, «Боевая Академия.») is entered by Охранник Илья's way from the
Жилой квартал (data/quests.json 965) and left by his twin's (966); its four
teachers give the lessons:

  1425 «Учитель<Br>Рукопашные навыки»  ближний бой; рукопашный бой, режущее оружие
  1426 «Учитель<Br>Обучение стрельбе»  стрельба; пистолеты, дробовики, автоматы,
                                        винтовки, пулемёты, пистолеты-пулемёты
  1427 «Учитель<Br>Навыки доктора»     медицина; хирургия, первая помощь
  1428 «Учитель<Br>Промышленность»     промышленность; добыча

-- twenty lessons of the four skills (texts.xml 49374-49415) and fifty-five of
the eleven specialisations (49416-49525), five each, the original's texts.
What a lesson gives is its start's: «Я обучу тебя ... (800 000 ед. опыта)»,
into the skill (rew_xp) or, «Требуется открытая специализация для зачисления
опыта», into the specialisation alone and only if it is learned
(rew_spec_xp, requires_spec). What it costs is its start's too, «5 унций
золота и один слиток в 10 унций серебра»: the gold, and the silver at the
FSC's rate of ten to one (texts.xml 44112) -- silver has no source on this
server (server/setcraft.py prices its cheques the same way) -- so 6, 12, 25,
50 and 100 G a lesson (cost_gold), 193 G the five. The start says the sum in
gold and nothing of silver: its words are the original's with that one
phrase written over, DESIGNED, so none of these rows is pinned in
data/build_orig_misc.py VERIFIED.

The wiki's (data/quests_wiki.json 764-783, 1045-1124): every lesson asks level
17 and the one before it in its group (children/parents), and each may be
taken again: once a day here (per_day 1), since a lesson asks no level of
its skill below the top, and the first lesson, the cheapest experience
for a gold ounce, would otherwise raise a character 16 -> 20 for some 740 G
in a row. With the chain and the day, one skill takes at most 10.55 million
a day for 193 G: a character 17 -> 20 by the Академия alone is nine days and
some 1 690 G (server/test_abuhamed_quests holds the floor). Nor is a lesson
offered, taken or handed in once its skill is at level 20 or its
specialisation at 5 (until_max, server/quests.py Quest.maxed): the start
names no ceiling, and the experience would be clamped there and the fee
taken for nothing. A lesson is a service (outside the daily limit, as the
exams are).

Numbers: 12000-12074 (the plan's register gives Абу-Хамед's generators
12000-12999; the wiki's own numbers are taken by the exams and the
warehouses' boxes), the eleven specialisations in the wiki's order first
(12000-12054), then the four skills (12055-12074). Every why names the
lesson's wiki number and texts.xml lines.

Run from WSL (LAVA_ORIG_TEXTS moves the source):
    python3 data/build_questgen_academy.py
"""
import html
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

import orig_texts  # noqa: E402

DEFAULT_TEXTS = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "questgen_academy.json")
ITEM_ROW = re.compile(r'<item id="(\d+)">(.*?)</item>', re.S)

FIRST_TYPE = 12000
LEVEL = 17
# The Академия has no cell: its marks are those of the Жилой квартал 127
# (6183,1975), where Илья's way leads in.
MARK = (6183 << 13) | 1975
AH = "the owner's «сделай потом абу хамед в таком же формате», 2026-10-14"

MELEE, RANGED, MEDIC, INDUSTRY = 1425, 1426, 1427, 1428
# The eleven specialisations in the wiki's order (1045 ...): key (server/
# quests.py SPEC_KEYS), the first lesson's name row, the wiki's first
# number, the teacher.
SPECS = [("assault", 49456, 1045, RANGED), ("rifles", 49466, 1052, RANGED),
         ("mining", 49516, 1059, INDUSTRY), ("shotguns", 49446, 1067, RANGED),
         ("first_aid", 49506, 1074, MEDIC), ("pistols", 49436, 1084, RANGED),
         ("smg", 49486, 1089, RANGED), ("machineguns", 49476, 1099, RANGED),
         ("blades", 49426, 1104, MELEE), ("unarmed", 49416, 1112, MELEE),
         ("surgery", 49496, 1120, MEDIC)]
# The four skills (764 ...): key (SKILL_KEYS), the five name rows (the start
# is the row after each), the wiki's first number, the teacher.
SKILLS = [("melee", (49374, 49378, 49380, 49382, 49384), 764, MELEE),
          ("medicine", (49396, 49398, 49400, 49402, 49404), 769, MEDIC),
          ("industry", (49406, 49408, 49410, 49412, 49414), 774, INDUSTRY),
          ("shooting", (49386, 49388, 49390, 49392, 49394), 779, RANGED)]
FINISH, NOTFINISH = 49376, 49377
SKILL_XP = (800000, 1200000, 1800000, 2700000, 4050000)
SPEC_XP = (400000, 600000, 900000, 1350000, 2025000)
COST_GOLD = (600, 1200, 2500, 5000, 10000)       # hundredths: 6, 12, 25, 50, 100 G
SILVER_RATE = 10                                 # silver ounces to one of gold (44112)

_PAY = re.compile(r"заплатить за занятие (\d+) унций золота и (один|два) слит(?:ок|ка) в "
                  r"(\d+) унций серебра\.")
_XP = re.compile(r"\(([\d ]+) ед\. опыта\)")


def load_texts(path):
    with io.open(path, encoding="utf-8") as fh:
        return {int(i): orig_texts.text(html.unescape(t))
                for i, t in ITEM_ROW.findall(fh.read())}


def lesson(texts, qtype, name_id, n, key, kind, wiki, teacher, prev):
    """One lesson's row, its start's sums checked against the module's."""
    name, start = texts[name_id], texts[name_id + 1]
    pay = _PAY.search(start)
    xp = _XP.search(start)
    if not pay or not xp:
        raise SystemExit("texts.xml %d is no lesson's start: %r" % (name_id + 1, start))
    gold, count, bar = int(pay.group(1)), pay.group(2), int(pay.group(3))
    silver = (1 if count == "один" else 2) * bar
    total = gold + silver // SILVER_RATE
    amount = int(xp.group(1).replace(" ", ""))
    want_xp = (SKILL_XP if kind == "skill" else SPEC_XP)[n - 1]
    if amount != want_xp or total * 100 != COST_GOLD[n - 1] or silver % SILVER_RATE:
        raise SystemExit("texts.xml %d: %d xp, %d G and %d silver, not the lesson %d's"
                         % (name_id + 1, amount, gold, silver, n))
    own_start = start.replace(pay.group(0), "заплатить за занятие %d унций золота." % total)
    row = {"type": qtype, "kind": "del_obj", "name": name, "start": own_start,
           "notfinish": texts[NOTFINISH], "finish": texts[FINISH],
           "give": [teacher], "take": [teacher], "obj": 0, "rew_afro": 0, "rew_gold": 0}
    if kind == "skill":
        row["rew_xp"] = {key: amount}
    else:
        row["rew_spec_xp"] = {key: amount}
        row["requires_spec"] = key
    row["until_max"] = True
    row.update({"cost_gold": total * 100, "repeatable": 1, "per_day": 1, "service": True,
                "level": LEVEL, "q_type": 0})
    if prev:
        row["need_quest"] = prev
    row.update({"loc": MARK, "finish_loc": MARK})
    row["why"] = (
        "RECOVERED texts and sums, DESIGNED fee and workings (%s; the plan's decision 26). "
        "The wiki's %d «%s» (texts.xml %d name, %d start, %d notfinish, %d finish, the "
        "series' last two stored once), given and taken by the teacher %d in the Боевая "
        "Академия (1295): %d of experience %s, the start's. The start is the original's but "
        "for its price, «%d унций золота и %s в %d унций серебра», written as the one sum in "
        "gold, %d G (silver at the FSC's 10:1, 44112: no source of silver on this server). "
        "Level 17 and %s, the wiki's; once a day (per_day 1), DESIGNED, so that the cheapest "
        "lesson is not bought again and again; and none once %s is at the top (until_max), "
        "DESIGNED: its fee would buy nothing. A service: outside the daily limit."
        % (AH, wiki + n - 1, name, name_id, name_id + 1, NOTFINISH, FINISH, teacher, amount,
           "into the skill %s (rew_xp)" % key if kind == "skill" else
           "into the specialisation %s alone, and only if it is learned (rew_spec_xp, "
           "requires_spec: «Требуется открытая специализация для зачисления опыта»)" % key,
           gold, "один слиток" if count == "один" else "два слитка", bar, total,
           "after the lesson before it (need_quest %d)" % prev if prev else
           "the first of its group, asking no lesson before it",
           "the skill (level 20, progression.SKILL_MAX)" if kind == "skill" else
           "the specialisation (level 5, progression.SPEC_MAX)"))
    return row


def build(texts_path=None):
    texts_path = texts_path or os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_TEXTS
    texts = load_texts(texts_path)
    for sid, want in ((FINISH, "Молодец, хорошо потрудился."),
                      (NOTFINISH, "На твоём счету недостаточно золота.")):
        if not texts[sid].startswith(want):
            raise SystemExit("texts.xml %d is not the lessons' line %r" % (sid, want))
    rows, qtype = [], FIRST_TYPE
    for key, first, wiki, teacher in SPECS:
        prev = None
        for n in range(1, 6):
            rows.append(lesson(texts, qtype, first + 2 * (n - 1), n, key, "spec", wiki, teacher,
                               prev))
            prev, qtype = qtype, qtype + 1
    for key, name_ids, wiki, teacher in SKILLS:
        prev = None
        for n, name_id in enumerate(name_ids, 1):
            rows.append(lesson(texts, qtype, name_id, n, key, "skill", wiki, teacher, prev))
            prev, qtype = qtype, qtype + 1
    meta = {
        "about": "GENERATED by data/build_questgen_academy.py -- do not edit: change the "
                 "builder (its SPECS, SKILLS and sums) and run it again.",
        "teachers": {"1425": "ближний бой; рукопашный бой, режущее оружие",
                     "1426": "стрельба; пистолеты, дробовики, автоматы, винтовки, пулемёты, "
                             "пистолеты-пулемёты",
                     "1427": "медицина; хирургия, первая помощь",
                     "1428": "промышленность; добыча"},
        "cost_gold": list(COST_GOLD),
        "counts": {"specialisations": len(SPECS) * 5, "skills": len(SKILLS) * 5},
        "types": [rows[0]["type"], rows[-1]["type"]],
    }
    return {"_meta": meta, "quests": rows}


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def main():
    doc = build()
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(doc))
    print("wrote %s: %d rows %s" % (OUT, len(doc["quests"]), doc["_meta"]["counts"]))


if __name__ == "__main__":
    sys.exit(main())
