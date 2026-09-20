"""Every numeric string id the server may send, and the text behind it.

Names travel as numbers. The client resolves them over HTTP against
database/texts.xml, the one file missing from the shipped copy, and a name id
it has not already been handed is not merely a blank label: StringCollector
fetches a batch for it, and any batch arriving after login walks the player
back to the login screen. PROTOCOL.md 9 has the chain.

So the set the HTTP stub preloads and the set the game server is allowed to
put on the wire must be the same set. They were not -- the stub was built from
database/mobs.xml while locations spawn 670 creature types that file has no
record of -- and one wasteland mob was enough to bring the login screen back.
Both sides import this module now, and known() is what the server asks before
sending an id at all.
"""
import json
import os

import items
import npcs
import quests
import transport
import world

# Creatures and items are numbered in separate spaces that overlap, while the
# strings they point at share one, so item ids carry items.STRING_ID_OFFSET.
try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}

try:
    ITEM_NAMES = {items.STRING_ID_OFFSET + t: n
                  for t, (_root, n) in items.catalogue().items()}
except Exception:
    ITEM_NAMES = {}

# Names recovered from the community wiki, which beat the internal ones.
try:
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(_here, "data", "npc_names.json"),
              encoding="utf-8") as _fh:
        REAL_NAMES = {int(k): v for k, v in json.load(_fh)["names"].items()}
except Exception:
    REAL_NAMES = {}

# Item names from the wiki over the internal ones, under the same ids, and
# item descriptions under items.DESC_ID_OFFSET + type: the id ss_si_* puts in
# desc. Deliberately no try/except, for the reason given at QUEST_STRINGS: a
# wiki table that fails to load must stop both processes at start, not leave
# the ids items.py sends off the preload.
WIKI_ITEM_NAMES = {items.STRING_ID_OFFSET + t: n
                   for t, n in items.wiki_names().items()}
ITEM_DESCRIPTIONS = {items.DESC_ID_OFFSET + t: d
                     for t, d in items.wiki_descs().items()}

# Quest names and texts, numbered 2 000 000 + 4 * type + k by quests.py, and
# the one empty string (5 000 000) a quest points at where it has no
# description. Deliberately no try/except: a table that fails to load would
# leave every quest id off the preload, and the first q_status would cost the
# player the login screen. Better to fail at start, in both processes.
QUEST_STRINGS = quests.strings()

# Vehicle names and descriptions, numbered 6 000 000 / 6 100 000 + type by
# transport.py. Same rule, same reason: a lessor's window asks for a ts_si
# per type it offers, each one carries a name id, and an id the preload
# missed is a trip back to the login screen.
TRANSPORT_STRINGS = transport.strings()

ALL = dict(MOB_NAMES)
ALL.update(ITEM_NAMES)
ALL.update(WIKI_ITEM_NAMES)
ALL.update(ITEM_DESCRIPTIONS)
ALL.update(REAL_NAMES)
ALL.update(QUEST_STRINGS)
ALL.update(TRANSPORT_STRINGS)


# The developers' own weapon (items.ADMIN_GUN) has an internal name and no
# article anywhere, so it would reach the player as "admin_gun". Named here
# in the same breath as the numbers that make it what it is.
ALL[items.STRING_ID_OFFSET + items.ADMIN_GUN] = "Админский ствол"

# Some "inhabitants" are not people. Their sprite is a strongbox and they
# open the storage window instead of talking, but mobs.xml still calls them
# by the clerk who was once written beside them -- and the wiki is worse,
# since it recorded the clerk's given name: the black market's box (2424)
# comes back as "Аарон". A man's name floating over a steel cabinet is the
# kind of thing that makes a world look unfinished, so anything drawn as a
# safe is named for what it is.
#
# Matched on the art folder rather than a list of ids: the folder is what
# decides what the player actually sees, and a new location that puts down
# another box gets the right name without anyone remembering to add it.
SAFE_SPRITES = ("1f_Safe", "1f_BankSafe", "1f_Seif_Stary")
STORAGE_NAME = "Хранилище"

try:
    SAFES = frozenset(t for t, (_root, _n, art) in world.mob_types().items()
                      if art in SAFE_SPRITES)
except Exception:
    SAFES = frozenset()

for _t in SAFES:
    ALL[_t] = STORAGE_NAME

# The table as the game's own sources leave it, before anybody had a say.
# tools/npc_editor.py compares against this to tell a name that was chosen
# from one that was merely sitting in the field when Save was pressed.
BASE = dict(ALL)

# Last word of all: the names the owner gave by hand in tools/npc_editor.py.
# After the wiki and after the storage rule, because it is the only one of
# the three that somebody decided on purpose.
ALL.update(npcs.NAMES)


def known(string_id):
    """Whether this id can be sent at all without costing the player a login."""
    return string_id in ALL


def text(string_id):
    """The name behind an id, or a visible placeholder rather than a blank."""
    return ALL.get(string_id, "#%d" % string_id)


_DOCUMENT = None


def document():
    """The whole table as one <s id> run, built once.

    Sizeable -- 35 470 rows, 1.6 MB -- but the original file was 20.8 MB and
    the client was built to swallow it in one request.
    """
    global _DOCUMENT
    if _DOCUMENT is None:
        _DOCUMENT = "".join(
            "<s id='%d'>%s</s>" % (i, _escape(n)) for i, n in sorted(ALL.items()))
    return _DOCUMENT


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
