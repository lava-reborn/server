"""The plantation's buyback counter, separate from ordinary shop prices."""
from fractions import Fraction

import eden
import gold_trade
import items
import progression


NPC_TYPE, ART_TYPE = 60020, 883
# Other categories retain their ordinary shop policy, currencies and caps.
NOMINAL_ROOTS = frozenset(items.BREAKABLE_ROOTS)
REPAIRABLE_LOCAL = frozenset((eden.CLEAVER, eden.BASKET))


def is_buyer(type_id):
    return type_id == NPC_TYPE


def nominal_item(row):
    return row is not None and row['root'] in NOMINAL_ROOTS


def unit_price(type_id):
    """Catalogue units in the item's own currency; G is already hundredths."""
    si = items.params_of(type_id) or {}
    if (items.root_of(type_id) not in NOMINAL_ROOTS
            or eden.restricted_item(type_id) or gold_trade.protected(type_id, si)):
        return Fraction(0), False
    gold = gold_trade.gold_priced(type_id, si)
    price = si.get('g_cost' if gold else 'cost', 0)
    if price <= 0:
        return Fraction(0), gold
    return Fraction(str(price)) / Fraction(str(si.get('sell_num') or 1)), gold


def client_fields(type_id):
    unit, gold = unit_price(type_id)
    return dict(eden_sale_unit=float(unit), eden_sale_gold=int(gold))


def sale_price(row, count):
    """Floor the full nominal value, including lost factory durability."""
    unit, gold = unit_price(row['type_id'])
    if not unit or row['root'] != items.root_of(row['type_id']):
        return 0, gold
    si = items.params_of(row['type_id']) or {}
    factory, ceiling = si.get('max_break_abs', 0), row['max_break_cur']
    if factory <= 0 or ceiling <= 0:
        return 0, gold
    quality = Fraction(max(0, min(row['brk'], ceiling, factory)), factory)
    return int(unit * count * quality), gold


def available(inv):
    """Recheck the actual counter, reach and live sentence under the lock."""
    trade, sess = inv.trade, inv.sess
    if (not trade or not is_buyer(trade.trader_type)
            or trade.loc_id != eden.CENTER or getattr(sess, 'on_map', False)
            or getattr(getattr(sess, 'loc', None), 'id', None) != eden.CENTER):
        return False
    room = getattr(sess, 'room', None)
    entry = room.npc(trade.npc_id) if room else None
    import world
    if not entry or entry[1] != NPC_TYPE or entry[2] != world.TRADER:
        return False
    cell = sess.live_cell() if hasattr(sess, 'live_cell') else sess.pos
    return bool(eden.assigned(inv.store, inv.char_id) and progression.within_reach(
        cell, entry[0], sess.loc.width, sess.loc.height))
