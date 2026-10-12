"""The rules orig_texts applies to the original's strings, pinned down.

    python3 server/test_orig_texts.py

Each case is a row the original table really carries, or its exact shape, and
what the player is meant to see. The rules are written up in orig_texts'
docstring; this is what stops them drifting.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import orig_texts as O  # noqa: E402

from testkit import check, fails  # noqa: E402


BS = chr(92)

print("names of things -- the variant the wiki way, the level and [A] gone")
check("[A][0] goes, the class after $ stays",
      O.item_name("Самострел[A][0]$Пистолет"), "Самострел$Пистолет")
check("[G] becomes (G)", O.item_name("Самострел[G][0]$Пистолет"), "Самострел (G)$Пистолет")
check("[P] becomes (P)", O.item_name("Наган 1895[P][1]$Пистолет"), "Наган 1895 (P)$Пистолет")
check("a solo line keeps its variant", O.item_name("Маузер C96[Q][2]$Пистолет"),
      "Маузер C96 (Q)$Пистолет")
check("[M], a mob's copy, is not labelled",
      O.item_name("Desert Eagle Mark XIX[M][0]$Пистолет"), "Desert Eagle Mark XIX$Пистолет")
check("a fractional level goes too", O.item_name("Пулемет MG[A][14.00]$Пулемет"),
      "Пулемет MG$Пулемет")
check("the space before a round's $ survives -- the client eats one character there",
      O.item_name("9мм НАТО[A] $КС"), "9мм НАТО $КС")
check("a clothing mod becomes a bracketed suffix",
      O.item_name("Шлем легионера[0][A][мод03]"), "Шлем легионера (мод03)")
check("but [мод00], the piece unmodified, goes like [A]",
      O.item_name("Шлем легионера[0][P][мод00]"), "Шлем легионера (P)")
check("a stray space before the tags does not outlive them",
      O.item_name("Рубашка [0][A][мод00]"), "Рубашка")

print()
print("descriptions")
check("a description written into a name's row loses the name's tags",
      O.item_desc("Рубашка неизвестного происхождения с короткими рукавами.[2][A][мод00]"),
      "Рубашка неизвестного происхождения с короткими рукавами.")
check("and an ordinary one is only cleaned",
      O.item_desc("Топик неизвестного [происхождения]."), "Топик неизвестного [происхождения].")

print()
print("people")
check("<Br> in lower case, the only one the event log parses",
      O.person_name("Борис<Br>Пистолеты и патроны"), "Борис<br>Пистолеты и патроны")
check("a mob's level in front of its name goes (the owner, 2026-10-12)",
      O.person_name("[3] Бугор Асмунд<Br>Новые колонисты"), "Бугор Асмунд<br>Новые колонисты")
check("  ..written loosely, too", O.person_name(" [ 12 ]Амазонка"), "Амазонка")
check("  ..and only in front: a bracket inside the name is the name's",
      O.person_name("Аббас ибн Заглюль<Br>Обмен экзоодежды [6-8]"),
      "Аббас ибн Заглюль<br>Обмен экзоодежды [6-8]")

print()
print("every string")
check("the doubled ? of the sex macro, which would show a man 'гол?ым'",
      O.text("Решил%sex??:а% помочь"), "Решил%sex?:а% помочь")
check("escaped quotes", O.text("сказал " + BS + '"да' + BS + '"'), 'сказал "да"')
check("the original's own markup is kept",
      O.text("<B>жирный</B><br/>и<i>курсив</i><u>x</u><hint>№1</hint>"),
      "<B>жирный</B><br/>и<i>курсив</i><u>x</u><hint>№1</hint>")
check("a stray '<B.' is dropped the way the launcher reads it, the <Br> after it kept",
      O.text("строка<B.<Br>битая"), "строка<Br>битая")
check("a tag the launcher would refuse is dropped",
      O.text("x<script>y</script>z"), "xyz")
check("and whatever comes out, the launcher accepts",
      O.launcher_ok(O.text("a<B.<Br>b<font color='red'>c</font>&amp;lt;img&amp;gt;")), True)

print()
print("the launcher's check itself")
check("plain text passes", O.launcher_ok("обычное имя"), True)
check("the original's markup passes", O.launcher_ok("<B>x</B><br/>y<Br>"), True)
check("a link is refused", O.launcher_ok("<a href='asfunction:x'>t</a>"), False)
check("a link with a tab instead of a space is refused", O.launcher_ok("<a\thref='x'>t</a>"), False)
check("an image written with a numeric bracket is refused",
      O.launcher_ok("&#60;img src='x.swf'&#62;"), False)

print("the Nubian valley's creatures, named by hand from the original")
_names = O.person_names()
check("a row with no level stays without one", _names.get(1023), "Серая крыса")
check("the Nubian defender is one of the valley's own guards, a resident: no level",
      _names.get(40), "Нубийский защитник")
check("a row with a level loses it", _names.get(82), "Голодная собака")
check("the colonists keep their clan under the name", _names.get(251), "Штурмовик<br>Новые колонисты")
check("a resident gets no level", _names.get(5205), "Говард Хаксли<br>Антиквариат и колониальные товары")

print()
print("no mob of the original goes by its level (the owner, 2026-10-12)")
_mobs = {int(t): r["name"] for t, r in O._NPCS.items() if r.get("kind") == "mob" and r.get("name")}
_before = sorted(t for t, n in _mobs.items() if O._MOB_LEVEL.match(n))
_after = sorted(t for t in _mobs if O._MOB_LEVEL.match(_names.get(t) or ""))
print("  mobs in data/orig_npcs.json: %d, with a level in front in the file: %d, on the wire: %d"
      % (len(_mobs), len(_before), len(_after)))
check("the file writes a level in front of most of its mobs (there is work to do)",
      len(_before) > len(_mobs) // 2, True)
check("  ..and not one of them keeps it on the wire", _after, [])
check("  ..and none is left with nothing to show",
      [t for t in _before if t in _names and not _names[t].strip()], [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("orig_texts OK")
