"""Gold commerce valuations, separate from purchase prices and death rules."""
from functools import lru_cache
from fractions import Fraction
import re

import items
import progression
import repair_policy
import restore_policy


# The legacy-blueprint ceiling is a pricing decision, independent of future level caps.
BLUEPRINT_SALE_MAX_LEVEL = 17
BLUEPRINT_SALE_DISCOUNT = 3
NPC_SALE_SHARE = Fraction(7, 10)


# Twice the agreed 175-kill afro income around the source camp. Legacy
# levels 18-20 use the last available tier at/below 17, with acquisition off.
BLUEPRINT_SALE_CAPS = {
    1: 60000, 2: 60000, 3: 72000, 4: 72000, 5: 84000, 6: 84000,
    7: 98666, 8: 98666, 9: 120000, 10: 120000,
    11: 136000, 12: 136000, 13: 144000, 14: 144000,
    15: 153333, 16: 153333, 17: 180000, 18: 180000,
    19: 180000, 20: 180000,
}


def decoded_blueprint(type_id):
    root, name = items.catalogue().get(type_id, (None, ""))
    return root == items.TRASH and name.startswith(("bpg_", "bpb_"))


def blueprint_level(type_id):
    root, name = items.catalogue().get(type_id, (None, ''))
    if root == items.TRASH and name.startswith(('bpg_', 'bpb_')):
        level = re.search(r'_lvl(\d+)', name)
        return int(level[1]) if level else None
    return None


@lru_cache(maxsize=None)
def blueprint_reference(type_id):
    """Same effect/variant at 17; knife recipes have only even tiers."""
    import craft
    name = items.catalogue().get(type_id, (None, ''))[1]
    for level in range(BLUEPRINT_SALE_MAX_LEVEL, 0, -1):
        twin = craft._by_name().get(re.sub(r'_lvl\d+', '_lvl%d' % level, name))
        if twin is not None:
            return twin
    return None


def protected(type_id, params):
    return (params.get('quest') or params.get('gold_trade_restricted')
            or type_id in items.PERSONAL_QUEST_REWARDS
            or type_id in items.ADMIN_OVERRIDES or items.out_of_game(type_id))


def gold_priced(type_id, params):
    import combat
    return bool(params.get('g_cost') and combat.gold_item(type_id))


def transferable(type_id):
    params = items.params_of(type_id) or {}
    return bool(params and not protected(type_id, params)
                and not items.acquisition_blocked(type_id)
                and (params.get('exchang') or gold_priced(type_id, params)))


def afro_blueprint(type_id, params=None):
    """Identify NPC-priced A blueprints for their afro resale basis."""
    params = params if params is not None else (items.params_of(type_id) or {})
    return bool(blueprint_level(type_id) is not None and params.get('cost', 0) > 0
                and not gold_priced(type_id, params))


def sale_quality(row, params):
    """NPC resale uses remaining factory durability, including ceiling loss."""
    if row["root"] in items.BREAKABLE_ROOTS:
        factory = params.get("max_break_abs", 0) or 0
        ceiling = row["max_break_cur"]
        if factory <= 0 or ceiling <= 0:
            return 0.0
        return max(0.0, min(row["brk"], ceiling, factory) / float(factory))
    if row["root"] == items.HEAL and params.get("use_count"):
        return max(0.0, min(1.0, row["use_count"] / float(params["use_count"])))
    return 1.0


def _sent_unit(value):
    """One wire value for both the shop display and the authoritative payout."""
    return int(value) if value.denominator == 1 else float('%.6g' % float(value))


def afro_sale_unit(type_id, params):
    """Healthy A-gear payout; purchase/repair prices retain their own fields."""
    if (items.root_of(type_id) not in items.BREAKABLE_ROOTS
            or params.get("quest") or gold_priced(type_id, params)
            or params.get("cost", 0) <= 0):
        return 0
    unit = (Fraction(str(params['cost'])) * NPC_SALE_SHARE
            * Fraction(str(params.get('sell_mod', 1)))
            / Fraction(str(params.get('sell_num') or 1)))
    return _sent_unit(max(Fraction(0), unit))


def sale_unit(type_id, params):
    """Afro payout per healthy piece, before quantity and condition.

    A blueprint with an alternative gold purchase price stays an A item.
    """
    if protected(type_id, params) or not gold_priced(type_id, params):
        return 0
    unit = (Fraction(str(params['g_cost'])) * progression.GOLD_TO_AFRO_RATE
            * NPC_SALE_SHARE / progression.GOLD_OUNCE)
    # Preserve every existing purchase route. If a G-labelled type has an
    # afro purchase price too, cap resale against that cheaper source.
    if params.get('cost', 0) > 0:
        unit = min(unit, Fraction(str(params['cost'])) * NPC_SALE_SHARE)
    sell_mod = min(Fraction(1), Fraction(str(params.get('sell_mod', 1))))
    unit *= sell_mod / Fraction(str(params.get('sell_num') or 1))
    level = blueprint_level(type_id)
    if level is not None:
        if level > BLUEPRINT_SALE_MAX_LEVEL:
            counterpart = blueprint_reference(type_id)
            if counterpart is None:
                return 0
            return min(int(unit), sale_unit(counterpart, items.params_of(counterpart) or {}))
        # The limit applies to the final payout, not to the shop buy price.
        cap = BLUEPRINT_SALE_CAPS.get(level, 0)
        return min(int(unit / BLUEPRINT_SALE_DISCOUNT), cap)
    return _sent_unit(unit)


def afro_sale_cap(type_id, params):
    """Old A blueprints above 17 keep an A basis, capped at the last tier."""
    level = blueprint_level(type_id)
    if level is None or level <= BLUEPRINT_SALE_MAX_LEVEL or not afro_blueprint(type_id, params):
        return 0
    twin = blueprint_reference(type_id)
    p = (items.params_of(twin) or {}) if twin is not None else {}
    return int(Fraction(str(p.get('cost', 0))) * NPC_SALE_SHARE
               * min(Fraction(1), Fraction(str(p.get('sell_mod', 1))))
               / Fraction(str(p.get('sell_num') or 1)))


@lru_cache(maxsize=None)
def auction_base(type_id):
    params = items.params_of(type_id) or {}
    if not gold_priced(type_id, params):
        return params.get('cost', 0)
    matched = params.get('repair_cost')
    if matched is not None:
        return matched
    # Blueprints cannot be repaired. Apply the same level multiplier to
    # their A twin, rather than charging a fee on the full gold conversion.
    root, name = items.catalogue().get(type_id, (None, ''))
    if root == items.TRASH and name.startswith(('bpg_', 'bpb_')):
        import craft
        counterpart = craft._by_name().get(name.replace('_gold_', '_afro_', 1))
        level = re.search(r'_lvl(\d+)', name)
        if counterpart is not None and level:
            cost = repair_policy.afro_cost(counterpart)
            if cost:
                return cost * repair_policy.multiplier(int(level[1]))
    # Existing repair fallback for types without an A counterpart.
    return (params.get('cost') or params.get('g_cost', 0)
            * progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE)


@lru_cache(maxsize=None)
def client_fields(type_id):
    params = items.params_of(type_id) or {}
    gold_sale = sale_unit(type_id, params)
    blueprint_sellable = (decoded_blueprint(type_id)
                          and not protected(type_id, params)
                          and (params.get('cost', 0) > 0 or gold_sale > 0))
    return dict(a_sale_unit=afro_sale_unit(type_id, params),
                g_restore_base=restore_policy.base_price(type_id, params),
                g_sale_unit=gold_sale, bp_sell=int(blueprint_sellable),
                a_sale_cap=afro_sale_cap(type_id, params),
                g_transfer=int(transferable(type_id)),
                g_auction_base=auction_base(type_id))
