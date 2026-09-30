"""Check data/orig_misc.json against texts.xml, our own tables and itself.

Runs under WSL with the original file present. Plain asserts, no framework,
like the other data sets:

    MSYS_NO_PATHCONV=1 wsl.exe -e bash -lc "cd /mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server && LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/test_orig_misc.py"

What is pinned here is what would go wrong quietly: a text changed on its way
out of the original (the formatting belongs to server/orig_texts.py alone), a
quest of our own dressed in somebody else's words, a vehicle given the wrong
line, and a file that comes out different on a second build -- the digest of
the final string table is compared by every player's launcher, so a file that
moves makes every player download the table again.

The original is read here with a parser of its own, not the builder's, so a
fault in build_orig_misc.load_texts cannot hide itself.
"""
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True     # a test leaves nothing behind in data/
import build_orig_misc as builder  # noqa: E402

SOURCE = os.environ.get("LAVA_ORIG_TEXTS") or builder.DEFAULT_SOURCE
# The file every id below was checked against. Another texts.xml means
# checking them again, not just rebuilding.
SOURCE_MD5 = "7a10e992003480a76546b6c824b3dbc2"
SOURCE_SIZE = 20433511

# type -> (name id, desc id) in the original, checked by hand.
TRANSPORT = {
    1: (10680, 10744),     # "Ослик Панург" (a lessor desk's name), its description
    2: (10681, 10748),
    3: (10682, 10752),
    4: (10683, 10756),
    5: (10684, 10760),
    6: (10764, 10902),     # "...как свои пять пальцев" -- 10765 says "четыре пальца"
    7: (10904, 10804),     # "Ларва"; the description is stored once, under ЛАРВА[G]
    8: (10901, 10756),     # "Газ 67 Б (P)" -- ours is premium; the УАЗ's description
    9: (10908, 10909),
    10: (10778, 10779),
    11: (10780, 10781),
    12: (None, None),      # "Летающая тарелка": not in the file
    13: (10910, 10911),
    14: (10906, 10779),    # the wiki gives the reindeer the Т-34's description
    15: (None, None),      # "Кобыла": only "Тест Кобыла -" / "Тест кобыла +"
    16: (10903, 10902),
}
# The black market's 1, 2, 3, 5 and 6 were ours until they left the table
# (2026-09-28); none is left.
OWN_QUESTS = ()
QUEST_KEYS = ("name", "start", "notfinish", "finish")


def original():
    """id -> decoded text, by a parser independent of the builder's."""
    with open(SOURCE, "rb") as fh:
        raw = fh.read()
    out = {}
    for line in raw.decode("utf-8").split("</item>"):
        head, sep, body = line.partition('<item id="')
        if not sep:
            continue
        num, _, text = body.partition('">')
        out[int(num)] = html.unescape(text)
    return out, hashlib.md5(raw).hexdigest(), len(raw)


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def fresh_digest(seed):
    """sha256 of a build made in a new interpreter with this hash seed."""
    code = ("import sys, hashlib; sys.path.insert(0, %r); import build_orig_misc as b; "
            "d, _ = b.build(); "
            "sys.stdout.write(hashlib.sha256(b.dumps(d).encode('utf-8')).hexdigest())" % HERE)
    env = dict(os.environ, PYTHONHASHSEED=str(seed), LAVA_ORIG_TEXTS=SOURCE,
               PYTHONDONTWRITEBYTECODE="1")
    return subprocess.check_output([sys.executable, "-c", code], env=env).decode("ascii")


def main():
    with open(os.path.join(HERE, "orig_misc.json"), "rb") as fh:
        raw = fh.read()
    doc = json.loads(raw.decode("utf-8"))
    texts, md5, size = original()
    print("orig_misc.json: %d bytes; texts.xml: %d rows, md5 %s" % (len(raw), len(texts), md5))

    # --- built from the file it says, and the file is the one checked ------
    assert md5 == SOURCE_MD5 and size == SOURCE_SIZE, \
        "texts.xml is not the file the pins were checked against"
    assert set(texts) == set(range(62795)), "texts.xml: not ids 0..62794"
    meta = doc["_meta"]
    assert meta["source_md5"] == md5 and meta["source_size"] == size, meta
    assert meta["source_rows"] == len(texts), meta["source_rows"]
    assert set(doc) == {"_meta", "transport", "quests"}, sorted(doc)

    # --- deterministic: the same bytes again, whatever the hash seed --------
    again = builder.dumps(builder.build(SOURCE)[0]).encode("utf-8")
    assert again == raw, "a fresh build differs from data/orig_misc.json: rebuild it"
    digests = {fresh_digest(seed) for seed in (1, 2)}
    assert digests == {hashlib.sha256(raw).hexdigest()}, digests
    print("deterministic: sha256 %s (in process and under two hash seeds)"
          % hashlib.sha256(raw).hexdigest())

    # --- every text is the original's, decoded and untouched ----------------
    def verbatim(where, text, sid):
        assert (text is None) == (sid is None), "%s: text and id disagree" % where
        if sid is not None:
            assert isinstance(sid, int) and not isinstance(sid, bool), where
            assert text == texts[sid], "%s: differs from original %d" % (where, sid)
            assert not text.strip().lower().startswith("тест"), "%s: a test string" % where

    # --- transport ----------------------------------------------------------
    ours = {int(k): v for k, v in load("transport.json")["types"].items()}
    tr = doc["transport"]
    assert all(k == str(int(k)) for k in tr), "transport keys must be type ids as strings"
    assert {int(k) for k in tr} == set(ours), "transport: not exactly our types"
    for key, rec in tr.items():
        assert set(rec) == {"name", "desc", "name_id", "desc_id"}, (key, sorted(rec))
        verbatim("transport %s name" % key, rec["name"], rec["name_id"])
        verbatim("transport %s desc" % key, rec["desc"], rec["desc_id"])
        for sid in (rec["name_id"], rec["desc_id"]):
            assert sid is None or sid in builder.TRANSPORT_BLOCK, (key, sid)
        got = (rec["name_id"], rec["desc_id"])
        assert got == TRANSPORT[int(key)], "transport %s: %r, checked %r" % (
            key, got, TRANSPORT[int(key)])
    names = sum(1 for r in tr.values() if r["name"])
    descs = sum(1 for r in tr.values() if r["desc"])
    print("transport: %d types, %d names, %d descriptions" % (len(tr), names, descs))

    # --- quests -------------------------------------------------------------
    rows = {int(r["type"]): r for r in load("quests.json")["quests"]}
    qs = doc["quests"]
    assert all(k == str(int(k)) for k in qs), "quest keys must be type ids as strings"
    for own in OWN_QUESTS:
        assert own in rows, "quest %d is gone from data/quests.json" % own
        assert str(own) not in qs, "quest %d is ours, the original never had it" % own
    assert {int(k) for k in qs} == set(builder.VERIFIED), sorted(qs)
    assert {int(k) for k in qs} <= set(rows), "a quest we do not have"
    for key, rec in qs.items():
        assert set(rec) == set(QUEST_KEYS) | {"ids", "confidence"}, (key, sorted(rec))
        assert rec["confidence"] == "high", key
        ids = rec["ids"]
        assert isinstance(ids, list) and len(ids) == 4, (key, ids)
        assert tuple(ids) == builder.VERIFIED[int(key)], (key, ids)
        assert rec["start"], "quest %s: no start" % key
        # A name the file does not have (the wiki's «Провиант», our «Доклад»)
        # stays ours, and ours must be there.
        assert rec["name"] or rows[int(key)].get("name"), "quest %s: no name" % key
        for k, sid in zip(QUEST_KEYS, ids):
            verbatim("quest %s %s" % (key, k), rec[k], sid)
            # A slot we leave empty is not filled from the original.
            if not rows[int(key)].get(k):
                assert sid is None, "quest %s: %s is empty in ours" % (key, k)

    q4 = qs["4"]
    assert q4["ids"] == [41453, 41454, 41455, 41456], q4["ids"]
    assert q4["name"] == "Пистолетчик", q4["name"]
    assert "Решил%sex?:а%" in q4["start"], q4["start"]
    assert "Показывай сертификат стрелка" in q4["notfinish"], q4["notfinish"]
    assert q4["finish"].startswith("- На базе Магриба"), q4["finish"]
    # Untouched means the <hint> number and the file's "<Br>" are still there.
    assert q4["start"].startswith("<hint><B>Задание №B81000024</B>"), q4["start"]
    assert "<Br>" in q4["start"] and "<br>" not in q4["start"], q4["start"]
    # Мастер Тиль's trainings share quest 4's finish, stored once.
    for t in ("1829", "1895", "1971", "2128"):
        assert qs[t]["ids"][3] == 41456 and qs[t]["ids"][1] == qs[t]["ids"][0] + 1, t
    # The Nubian valley's tutorial (11-27) is the newest edition: no line of
    # it carries the 2012 edition's number label, where the file has both
    # («Мертвые беззащитны» 59813, not 25177's «№0000158»; «Немного
    # мудрости» 59806, not the em-dashed 24391), and the names the file has
    # are the old edition's own lines, far before the starts.
    valley = [str(t) for t in range(11, 28)]
    assert all(t in qs for t in valley), sorted(qs)
    for t in valley:
        for k in QUEST_KEYS:
            assert "№" not in (qs[t][k] or ""), (t, k)
    assert qs["23"]["ids"] == [25176, 59813, 59814, 59815], qs["23"]["ids"]
    assert qs["19"]["ids"] == [24390, 59806, 24392, 59807], qs["19"]["ids"]
    assert qs["22"]["name"] is None and qs["26"]["name"] is None
    assert rows[22]["name"] == "Провиант" and rows[26]["name"] == "Доклад"
    # The valley's story (28-45) is the newest edition too, where it wrote a
    # line again (its own hints say «Подсказка №2», so only the 2012 number
    # label is looked for). The three parts of «Похищенный груз» go by their
    # own name lines, not all by 59851; «Разведчик» keeps its 2012 start and
    # ends in the newest edition's words (59861, not "кто—то" of 24425);
    # «Важные персоны» takes the later copy 45368/45369 of its start and
    # finish; «Назад, в долину», which the file ends with nothing, ends in
    # the original's words for the same ride in, 59830.
    story = [str(t) for t in range(28, 46)]
    assert all(t in qs for t in story), sorted(qs)
    for t in story:
        for k in QUEST_KEYS:
            assert not re.search(r"№\s*0000", qs[t][k] or ""), (t, k)
    assert [qs[t]["ids"][0] for t in ("31", "32", "33")] == [59851, 25191, 25195]
    assert [qs[t]["name"] for t in ("32", "33")] == ["Похищенный груз (часть 2)",
                                                      "Похищенный груз (часть 3)"]
    assert qs["36"]["ids"] == [24423, 24424, None, 59861], qs["36"]["ids"]
    assert "—" not in qs["36"]["finish"], qs["36"]["finish"]
    assert qs["39"]["ids"] == [24349, 45368, 24351, 45369], qs["39"]["ids"]
    assert qs["44"]["ids"] == [59870, 59871, None, 59830], qs["44"]["ids"]
    assert qs["44"]["finish"] == "Ну, поехали!", qs["44"]["finish"]
    # The valley's market, farm and mine (46-67), the newest edition again.
    # «Точильный камень» and «Крысиный король» have no name line of their
    # own, and the thing's (6342, 6344) says the same words; «Крысиный
    # переполох» starts and ends in the newest edition's words (59916,
    # 59917), not the 2012 copies with other hours and em dashes; «Еда»'s
    # start and notfinish are told apart by their task lines (59875, 59877),
    # which folded without them are one text; «Королевский Элексир» shares
    # its notfinish with «Крысиный король».
    market = [str(t) for t in range(46, 68)]
    assert all(t in qs for t in market), sorted(qs)
    for t in market:
        for k in QUEST_KEYS:
            assert not re.search(r"№\s*0000", qs[t][k] or ""), (t, k)
    assert [qs[t]["ids"][0] for t in ("48", "55")] == [6342, 6344]
    assert [qs[t]["name"] for t in ("48", "55")] == ["Точильный камень", "Крысиный король"]
    assert qs["53"]["ids"] == [24613, 59916, None, 59917], qs["53"]["ids"]
    assert qs["62"]["ids"] == [59874, 59875, 59877, 59878], qs["62"]["ids"]
    assert "не чаще 1 раза в сутки" in qs["62"]["start"], qs["62"]["start"]
    assert qs["56"]["ids"][2] == qs["55"]["ids"][2] == 59919
    assert qs["58"]["ids"] == [24341, 59832, 59833, 24344], qs["58"]["ids"]
    print("quests: %d written (%s), %d of ours left alone"
          % (len(qs), ", ".join(sorted(qs, key=int)), len(OWN_QUESTS)))

    # --- the slot order is the server's k -----------------------------------
    with io.open(os.path.join(ROOT, "server", "quests.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert re.search(r"NAME,\s*START,\s*NOTFINISH,\s*FINISH\s*=\s*range\(", src), \
        "server/quests.py no longer numbers the texts name, start, notfinish, finish"
    assert builder.QUEST_KEYS == QUEST_KEYS
    print("test_orig_misc: OK")


if __name__ == "__main__":
    main()
