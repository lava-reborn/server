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
import hashlib
import json
import os

import items
import npcs
import orig_texts
import quests
import sets
import setcraft
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

# Clothing set names and descriptions, 7 000 000 / 7 100 000 + set_type
# (sets.py). The client asks for a set's name the moment ss_si_set arrives,
# which is as soon as a stall or a bag shows one of its pieces -- earlier than
# any tooltip. Same rule as above: sets.py loads its table with no try/except.
SET_STRINGS = sets.strings()

# The game's own words. In September 2026 the owner found the original
# res/database/texts.xml; data/build_orig_*.py work out which of our types
# each of its rows belongs to, and orig_texts cleans the text for the wire.
# They go on top of the wiki, because the wiki was only ever a reconstruction
# of this -- and where the two disagree it is the wiki that had it wrong (the
# Самопальный револьвер is level 0, not 2; the doctor is Гофус, not Гуфус).
#
# Under our own ids, never the original's: nothing in the client needs those,
# there being not one string id written into its code or its data. A name at
# STRING_ID_OFFSET + type, a description at DESC_ID_OFFSET + type. A type
# that had no description before now has one, and items.static_info starts
# sending its id the moment known() says it exists -- which it does, being
# here. Quests and vehicles take theirs at load, in quests.py and
# transport.py, so their frames and QUEST_/TRANSPORT_STRINGS already agree.
ORIG_ITEM_NAMES = {items.STRING_ID_OFFSET + t: n
                   for t, n in orig_texts.item_names().items()}
ORIG_ITEM_DESCS = {items.DESC_ID_OFFSET + t: d
                   for t, d in orig_texts.item_descs().items()}

# The pieces of the clothing sets by the names and descriptions data/sets.json
# gives them, over the original's under the same ids. The one place the file
# beats the game's own words, and for a reason the file states: the owner
# chose Локсли's ladder by its icons, and the original's rows for those types
# are another set's -- a leather hat called "Гоглы с фильтром", a panama
# called "Очки-консервы".
SET_ITEM_NAMES = {items.STRING_ID_OFFSET + t: n for t, n in sets.item_names().items()}
SET_ITEM_DESCS = {items.DESC_ID_OFFSET + t: d for t, d in sets.item_descs().items()}

# The same pieces reworked (mod01-mod10) by their rung's name and the mod,
# and the clothing cheques (setcraft.py): over the original's words for the
# mods, which are another set's as the pieces' own are.
SETCRAFT_STRINGS = setcraft.strings()

ALL = dict(MOB_NAMES)
ALL.update(ITEM_NAMES)
ALL.update(WIKI_ITEM_NAMES)
ALL.update(ITEM_DESCRIPTIONS)
ALL.update(ORIG_ITEM_NAMES)
ALL.update(ORIG_ITEM_DESCS)
ALL.update(SET_ITEM_NAMES)
ALL.update(SET_ITEM_DESCS)
ALL.update(SETCRAFT_STRINGS)
ALL.update(REAL_NAMES)
ALL.update(QUEST_STRINGS)
ALL.update(TRANSPORT_STRINGS)
ALL.update(SET_STRINGS)


# The developers' own weapon (items.ADMIN_GUN) has an internal name and no
# article anywhere, so it would reach the player as "admin_gun". Named here
# in the same breath as the numbers that make it what it is.
ALL[items.STRING_ID_OFFSET + items.ADMIN_GUN] = "Админский ствол"

# The cigarette (41) is what a creature with no parts of its own leaves in
# its bag (mobs.FALLBACK_LOOT: a camel, a jackal, a goat), and neither the
# original's text nor the wiki names it, so it reached the player as
# objects.xml's "cigarette". DESIGNED: the plain word.
ALL[items.STRING_ID_OFFSET + 41] = "Сигарета"

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

# The people of the world by the original's own names, over the wiki's.
# A mob goes by its name alone, without the level the original writes in
# front of it (orig_texts.person_name; the owner's word of 2026-10-12). Of
# the level the client shows only a shield beside the name, the difference
# from the player's own clamped to -4 .. +4, which the lvl of the mob's
# userInfo paints (combat.mob_info); the number itself nowhere.
ORIG_PERSON_NAMES = orig_texts.person_names()
ALL.update(ORIG_PERSON_NAMES)

# A safe the original names keeps its own name: the Nubian market's bank is
# "Хранилище<br>личных вещей" there, which says more than the generic one.
for _t in SAFES - set(ORIG_PERSON_NAMES):
    ALL[_t] = STORAGE_NAME

# The table as the game's own sources leave it, before anybody had a say.
# tools/npc_editor.py compares against this to tell a name that was chosen
# from one that was merely sitting in the field when Save was pressed.
BASE = dict(ALL)

# The names the owner gave by hand in tools/npc_editor.py -- except where the
# original names somebody. That was his own decision when the original turned
# up (2026-09-23): the game's own names over the ones chosen in its absence.
# A hand-given name now fills a gap the original leaves, and the editor still
# decides everyone the original is silent about.
ALL.update({t: n for t, n in npcs.NAMES.items() if t not in ORIG_PERSON_NAMES})


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


# The byte order mark and the client's own single-quoted declaration, with no
# encoding attribute -- which is how every XML file under res/ is written,
# whatever its declaration claims.
#
# It lives here rather than in tools/ because three different readers have to
# agree on it byte for byte: the file exported onto the player's disk for
# LOCAL mode, the ?all=1 reply for WEB mode, and now the update endpoint the
# launcher compares a digest against. A second copy anywhere is a digest that
# will not match for a reason nobody can see. server/ is also the only
# directory that reaches the container -- .dockerignore keeps tools/ out -- so
# this is the one place all three can import from.
PROLOGUE = "﻿<?xml version='1.0'?>"

_BLOB = None
_SHA = None


def document_bytes():
    """The table as the bytes the client reads, built once and kept.

    Safe to cache for the life of the process, and that is not an assumption:
    ALL is assembled at import out of res/ and data/, and nothing writes to it
    afterwards. Measured rather than believed -- five processes under
    PYTHONHASHSEED 0, 1, 12345 and random, on 3.11 and on the 3.12 of the
    container image, all produce the same 1 915 490 bytes and the same digest,
    because document() joins sorted(ALL.items()) and every key is an int.
    """
    global _BLOB
    if _BLOB is None:
        _BLOB = (PROLOGUE + "<data>" + document() + "</data>").encode("utf-8")
    return _BLOB


def document_sha256():
    """Hex digest of document_bytes() -- what the launcher checks against.

    The digest describes the res/ mounted on THIS server, not the state of the
    repository: names.ALL is read from LAVA_RES and data/, and the deploy
    deliberately does not carry res/. That is the point of the whole exercise
    -- the launcher is told what this server will actually put on the wire.
    """
    global _SHA
    if _SHA is None:
        _SHA = hashlib.sha256(document_bytes()).hexdigest()
    return _SHA
