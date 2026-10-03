"""What the owner decided about an inhabitant, by creature type.

Everything the game knows about an NPC comes from tables that were not made
for this world: mobs.xml names them after whoever was written beside them in
2008, and the wiki's stock lists are what players saw on a server that has
been off for years. Both are a good start and neither is a decision.

This is where the decisions live. `data/npcs.json` is written by
`tools/npc_editor.py` and read here once, at import, by both processes that
need it -- the game server and the HTTP one, which must agree about every
string id on the wire (see names.py).

Keyed by creature type, not by location, because that is how the client and
the server already think: `items.stock_for` takes a trader type, and a name
travels as the type id itself. Two markets that put down the same trader are
putting down the same trader.

A missing file means no decisions have been made yet, which is not an error:
everything falls back to the tables underneath.
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "npcs.json")


def _load():
    try:
        with open(PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return {}, {}, {}, {}
    except (OSError, ValueError) as e:
        # Deliberately loud, like the wiki tables in items.py: a file that is
        # there but unreadable is a mistake someone just made, and starting
        # without it would quietly serve the old world back.
        raise RuntimeError("data/npcs.json cannot be read: %s: %s -- the "
                           "server does not start without it"
                           % (type(e).__name__, e))
    names = {int(k): str(v) for k, v in (doc.get("names") or {}).items()
             if str(v).strip()}
    stock = {int(k): [int(t) for t in v]
             for k, v in (doc.get("stock") or {}).items()}
    # A healer's fee by type (on_conv;op=1, Healer.as a_price); a type with
    # none takes server.MEDIC_PRICE.
    healer = {int(k): int(v) for k, v in (doc.get("healer_price") or {}).items()
              if not str(k).startswith("_")}
    # Healers register homes by default; other eligible NPCs need an
    # explicit decision with its source. False can also disable a healer.
    home = {}
    for key, row in (doc.get("home") or {}).items():
        if str(key).startswith("_"):
            continue
        if not isinstance(row, dict) or type(row.get("home")) is not bool \
                or not str(row.get("why") or "").strip():
            raise RuntimeError("data/npcs.json home %s needs a boolean home and a why" % key)
        home[int(key)] = row["home"]
    return names, stock, healer, home


NAMES, STOCK, HEALER_PRICE, HOME = _load()


def name(type_id):
    """The name this creature should carry, or None to leave it alone."""
    return NAMES.get(type_id)


def stock(type_id):
    """What this trader should sell, or None to fall back to the wiki.

    An empty list is a decision too -- a trader with nothing to sell -- and
    is not the same as no entry at all.
    """
    return STOCK.get(type_id)


def healer_price(type_id, default):
    """What this healer charges for a full heal, or default."""
    return HEALER_PRICE.get(type_id, default)


def home(type_id):
    """An explicit registration decision, or None to use the NPC's class."""
    return HOME.get(type_id)
