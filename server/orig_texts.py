"""The game's own words, from its original string table, ready for the wire.

In September 2026 the owner found the original res/database/texts.xml -- the
file this project had spent a year reconstructing from the wiki and the
client's tables, because the copy of the game it started from never shipped
it. 62 795 rows. The data/build_orig_*.py builders work out which of our
types each row belongs to and store the raw text in data/orig_*.json; this
module is the one place that turns that raw text into what a player sees.

WHY ONE PLACE

The builders store the original verbatim, and every change to it happens
here, under a name, with the reason beside it. If each builder cleaned its
own strings the rules would drift apart, and the next person to ask "why does
this name look like that" would have three answers.

WHAT ARRIVES AND WHAT LEAVES

Our string ids stay our own (items.STRING_ID_OFFSET + type and so on); the
original ids never reach the wire, because nothing in the client needs them --
there is not one string id written into its code or its data files. So what
this module produces is simply: our id -> the original's text, cleaned.

THE CLEANING, RULE BY RULE

  names of things   "Самострел[A][0]$Пистолет" -> "Самострел$Пистолет"
                    "Наган 1895[G][1]$Пистолет" -> "Наган 1895 (G)$Пистолет"
      The owner chose to show variants the way the wiki does, as "(G)" and
      "(P)", not as the bracket tags the file carries -- although the players
      of 2008 almost certainly saw the tags, since the client read the table
      as a static file and nothing in it strips a bracket. The level tag and
      [A] go, [M] goes (a mob's copy of a gun is not something to label), and
      any other variant tag becomes a bracketed suffix.
      What follows "$" is kept to the character: it is data, not decoration.
      The client cuts the name there and shows the rest as the class line
      under a weapon ("ПИСТОЛЕТ"), as the quality badge of a round, as the
      frame of a New Year hat.
                    "Шлем легионера[0][P][мод00]" -> "Шлем легионера (P)"
      [мод00] is the piece as it left the workshop, no modification at all,
      so it goes the way [A] does; [мод03] and the rest stay, being what
      tells two pieces of one name apart.

  descriptions      "Рубашка ... с короткими рукавами.[2][A][мод00]" -> "Рубашка ... с короткими рукавами."
      The rows of Колонист[2] carry the pieces' descriptions where their
      names should be, tags and all, and they are the only descriptions most
      of those pieces have. As a description the tags are not text.

  people           "Борис<Br>Пистолеты и патроны" -> "Борис<br>Пистолеты и патроны"
      Lower case, because GameEvents.parseNamePers only recognises "<br>" when
      it turns a name into "Имя <Роль>" for the event log.
                    "[3] Бугор Асмунд" -> "[0] Бугор Асмунд"
      A mob's level is written into its name and the client shows it as is --
      it adds a level prefix only to players. The file's number agrees with
      the mob's real level for 102 of 252 mobs, so the prefix is rewritten
      with the level the mob actually fights at, rather than let a player read
      a number that is not true.
                    "Серая крыса" -> "[2] Серая крыса"
      A few rows chosen by hand (data/orig_names_manual.json) name a mob
      without writing a level at all; it is added, so that no mob of the
      world reads like a person who happens to stand among them.

  every string      "%sex??:а%" -> "%sex?:а%"
      2 521 rows carry a doubled "?". ParseString takes everything after the
      first "?" as the male form, so a man would read "гол?ым".
                    '\\"' -> '"'
      Escaped quotes the tooltip never unescapes.
                    tags outside the launcher's whitelist are dropped
      The launcher refuses a whole table for one tag it does not know
      (Updater.Sane), and a refused table leaves the player on his old one --
      whose missing ids are a trip back to the login screen. The original uses
      nothing but <br>, <b>, <i>, <u> and <hint>, all of which the launcher
      admits; this is the net under the eight rows whose markup is broken.
"""
import html
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

# The same list as launcher/TextsCheck.cs ALLOWED_TAGS. The two are kept equal by
# tools/test_export_texts.py, which runs this check over the whole table.
ALLOWED_TAGS = frozenset(("br", "/br", "br/", "b", "/b", "b/", "i", "/i",
                          "u", "/u", "hint", "/hint"))

_TAG = re.compile(r"<([^<>]*)>")
_LEVEL = re.compile(r"\[\s*\d+(?:[.,]\d+)?(?:x\d+)?\s*\]")      # [0] [14.00] [20x2]
_VARIANT = re.compile(r"\[\s*([^\[\]]+?)\s*\]")
_MOB_LEVEL = re.compile(r"^\s*\[\s*\d+\s*\]\s*")
_BASE_MOD = re.compile(r"мод\s*0+$")                               # [мод00]
_NAME_TAGS = re.compile(r"\s*\[\s*\d+\s*\](?:\[[^\[\]]*\])*\[мод[^\[\]]*\]\s*$")
_BR = re.compile(r"<\s*br\s*/?\s*>", re.I)
_SPACES = re.compile(r"[ \t]{2,}")


def _load(name):
    """A builder's output, or nothing at all if it has not been built.

    Nothing rather than an error: the table the game already has is complete
    without these files, and a server started before the builders ran must
    still start. The texts simply stay the wiki's until they are built.
    """
    try:
        with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return {}


# --- the rules --------------------------------------------------------------

def tag_ok(tag):
    return tag.strip().lower() in ALLOWED_TAGS


def safe_tags(text):
    """Drop whatever the launcher would refuse the whole table for.

    This walks the text exactly the way Updater.TagsAllowed does -- from each
    "<" to the next ">" or the next "<", whichever comes first -- rather than
    looking for well-formed tags, because the difference is the whole point.
    The original has rows like "<B.<Br>": a regular expression for tags sees
    only the "<Br>" and keeps the stray "<B.", while the launcher sees "<B."
    as a tag, finds it on no list, and refuses every row of the table with it.
    """
    return _SCAN.sub(_keep_tag, text)


# The walk, as one pattern: a "<", everything up to the next "<" or ">", and
# the ">" if that is what it met. A closed tag on the list stays; anything
# else goes, an unclosed fragment up to (not including) the "<" after it.
# The same as stepping through it a character at a time, which cost a
# quarter of the server's start over the 26 000 rows that carry a bracket.
_SCAN = re.compile(r"<([^<>]*)(>?)")


def _keep_tag(m):
    return m.group(0) if m.group(2) and tag_ok(m.group(1)) else ""


def launcher_ok(value):
    """What Updater.SafeValue will say about this text once it is served.

    A port of the C#, run on the escaped form the table carries: a raw
    bracket is already wrong, and after decoding -- up to four times, for a
    value escaped more than once -- every tag must be on the list. The table
    test runs this over every row; one refusal here is every player on an
    old table.
    """
    v = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for _ in range(4):
        nxt = html.unescape(v)
        if nxt == v:
            return True
        v = nxt
        i = 0
        while True:
            i = v.find("<", i)
            if i < 0:
                break
            j = i + 1
            while j < len(v) and v[j] not in "<>":
                j += 1
            if not tag_ok(v[i + 1:j]):
                return False
            i = j + 1 if j < len(v) else len(v)
    return True


def clean(text):
    """The fixes every string gets, whatever it names."""
    if not text:
        return text
    text = text.replace("%sex??", "%sex?")
    text = text.replace('\\"', '"')
    text = safe_tags(text)
    if launcher_ok(text):
        return text
    # Something here decodes into a bracket the launcher refuses -- an entity,
    # perhaps nested: "&amp;lt;img&amp;gt;" walks straight past the scan above,
    # which only sees raw brackets, and the launcher then unescapes it up to
    # four times and meets "<img>". So decode it all the way, until it stops
    # changing, and walk it again: what were entities are now brackets, and
    # the walk takes the ones that are not on the list.
    prev = None
    while prev != text:
        prev, text = text, html.unescape(text)
    text = safe_tags(text)
    if launcher_ok(text):
        return text
    # Last resort, which nothing in the original has been seen to reach: keep
    # the line breaks, lose every other tag and every loose bracket.
    text = re.sub(r"<(?!/?br\s*/?>)[^<>]*>?", "", text, flags=re.I)
    return text.replace("<", "").replace(">", "") if not launcher_ok(text) else text


def item_name(raw):
    """A thing's name, the way the owner chose to show it."""
    if not raw:
        return raw
    name, dollar, rest = raw.partition("$")
    name = _LEVEL.sub("", name)

    def variant(m):
        tag = m.group(1).strip()
        if tag.upper() in ("A", "M") or _BASE_MOD.match(tag):
            return ""
        return " (%s)" % tag
    name = _VARIANT.sub(variant, name)
    name = _SPACES.sub(" ", name)
    # Keep a space that stood before "$": for a round, the client cuts one
    # character before the dollar (substr(0, idx - 1), Ammo's setter), and
    # that character is meant to be the space, not the last letter. With no
    # "$" after it a space is only a stray ("Рубашка [0][A][мод00]").
    trailing = " " if dollar and name.endswith(" ") else ""
    name = name.strip() + trailing
    return clean(name + dollar + rest)


def item_desc(raw):
    """A thing's description: a name's tags, where it sits in a name's row, go."""
    if not raw:
        return raw
    return clean(_NAME_TAGS.sub("", raw))


def person_name(raw, level=None):
    """A name over somebody's head."""
    if not raw:
        return raw
    text = _BR.sub("<br>", raw)
    if level is not None and _MOB_LEVEL.match(text):
        text = _MOB_LEVEL.sub("[%d] " % int(level), text, count=1)
    return clean(text)


def text(raw):
    """A description or a line of a quest: only the fixes every string gets."""
    return clean(raw)


# --- what the builders produced ----------------------------------------------

_ITEMS = _load("orig_items.json").get("items", {})
_NPCS = _load("orig_npcs.json").get("npcs", {})

# Original strings the builder assigned with confidence that the evidence does
# not bear out, kept off the wire by id and with the reason written down.
#
#   9163 "[7] Фиолетовый Лорд<Br>Банда Лоры Крафт" -- given to 38 different
#        *LandLord* mob types at once, eight of which stand in the world, one
#        in 24 locations. The only thing tying them to it is that "lord"
#        transliterates as "Лорд"; "land" is explained by nothing, and their
#        levels (1-4) are not the 7 the string carries. Every other string
#        goes to six types or fewer, and those are plausible -- the same lab
#        assistant at one level, the same healer in three villages. Thirty-
#        eight is not a pattern of the file; it is a pattern of the matcher.
#        The builder flagged it itself. Better the name the mob had than a
#        wrong one over it in two dozen places.
DOUBTFUL_STRINGS = frozenset((9163,))
_MISC = _load("orig_misc.json")


# Both tables are cleaned once a process: _ITEMS does not change after the
# load, and the server asked for each of them twice at start (items, names,
# combat), over 23 000 rows apiece. A copy goes out, so no caller can change
# what the next one gets.
_CLEANED = {}


def _cleaned(field, fix):
    if field not in _CLEANED:
        _CLEANED[field] = {int(t): fix(r[field]) for t, r in _ITEMS.items() if r.get(field)}
    return dict(_CLEANED[field])


def item_names():
    """type_id -> the original's name for it, cleaned."""
    return _cleaned("name", item_name)


def item_descs():
    """type_id -> the original's description for it, cleaned."""
    return _cleaned("desc", item_desc)


def person_names(level_of=None):
    """type_id -> the original's name over its head, cleaned.

    level_of(type_id) gives the level a mob really fights at; the prefix the
    file wrote is replaced with it.
    """
    out = {}
    for t, r in _NPCS.items():
        if not r.get("name") or r.get("string_id") in DOUBTFUL_STRINGS:
            continue
        tid = int(t)
        lvl = None
        if level_of is not None:
            try:
                lvl = level_of(tid)
            except Exception:
                lvl = None
        name = r["name"]
        if r.get("kind") == "mob" and lvl is not None and not _MOB_LEVEL.match(name):
            name = "[%d] %s" % (int(lvl), name)
        out[tid] = person_name(name, lvl)
    return out


def transport():
    """type -> (name, desc), cleaned, either may be None."""
    out = {}
    for t, r in (_MISC.get("transport") or {}).items():
        out[int(t)] = (item_name(r.get("name")) if r.get("name") else None,
                       text(r.get("desc")) if r.get("desc") else None)
    return out


def quests():
    """type -> {"name", "start", "notfinish", "finish"}, cleaned, any may be None."""
    out = {}
    for t, r in (_MISC.get("quests") or {}).items():
        out[int(t)] = {k: text(r.get(k)) if r.get(k) else None
                       for k in ("name", "start", "notfinish", "finish")}
    return out
