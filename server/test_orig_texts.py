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
check("a mob's level prefix is rewritten with its real level",
      O.person_name("[3] Бугор Асмунд", 0), "[0] Бугор Асмунд")
check("and left alone when there is no level to write",
      O.person_name("[3] Бугор Асмунд"), "[3] Бугор Асмунд")

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
_lv = {1023: 2, 40: 1, 82: 1, 251: 3}
_names = O.person_names(lambda t: _lv.get(t, 1))
check("a row with no level gets the mob's own", _names.get(1023), "[2] Серая крыса")
check("the Nubian defender is one of the valley's own guards, a resident: no level",
      _names.get(40), "Нубийский защитник")
check("a row with a level has it rewritten, as always", _names.get(82), "[1] Голодная собака")
check("the colonists keep their clan under the name", _names.get(251), "[3] Штурмовик<br>Новые колонисты")
check("a resident gets no level", _names.get(5205), "Говард Хаксли<br>Антиквариат и колониальные товары")

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("orig_texts OK")
