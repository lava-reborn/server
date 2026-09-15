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

ALL = dict(MOB_NAMES)
ALL.update(ITEM_NAMES)
ALL.update(REAL_NAMES)


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
