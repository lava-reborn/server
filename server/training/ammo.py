"""Range-only ammunition closure and recovered support weapons.

Training gun identities/rounds: items.TRAINING_GUNS (original client texts).
Crossbow/flare-gun values: archived pages «Арбалет»/«Ракетница».
Resources crossbow/ny_debuf_pistol exist in the client; the latter is the
flare-gun icon. This reconstruction does not alter the ordinary server.
Control effects of rare ammunition are outside the compatibility check.
"""
from functools import lru_cache

ROCKET, CROSSBOW = 3148, 3173
TUTORIAL_WEAPONS = frozenset(range(3728,3734))
SPECIAL_WEAPONS = TUTORIAL_WEAPONS | {ROCKET,CROSSBOW,1547,1569,1570}
EXTRA_SOURCES = TUTORIAL_WEAPONS | {ROCKET,CROSSBOW,3727,6192,6195,6199,6200}
LEVELS = {CROSSBOW:10}
NAMES = {ROCKET:'Ракетница',CROSSBOW:'Арбалет'}
GIFT_ALIASES = frozenset((1,44,202,203,204,235,236,366,436))


@lru_cache(maxsize=1)
def expanding_rounds():
    import items
    # Exact same calibre, different cartridge variant; never mix chamberings.
    return tuple((source,items.catalogue()[source][1].removesuffix('_SB_G')+'_')
                 for source in range(6176,6188))


def compatible(source,params):
    import items
    if source == ROCKET:
        return [6191,6192]
    if source == CROSSBOW:
        return list(range(6193,6201))
    if source in TUTORIAL_WEAPONS:
        return [3727]
    rounds=list(params.get('comp_array',()))
    if source in (25562,43338,43341):
        return list(dict.fromkeys(6188 if r in GIFT_ALIASES else r for r in rounds))
    result=list(dict.fromkeys(rounds))
    for candidate,prefix in expanding_rounds():
        if candidate not in result and any(items.catalogue().get(r,(None,''))[1].startswith(prefix) for r in rounds):
            result.append(candidate)
    return result


def parameters(source,params):
    import items
    if source in (ROCKET,CROSSBOW):
        bow=source==CROSSBOW
        params.update(h_damage_min=[3 if bow else 1,0,0],h_damage_max=[7 if bow else 3,0,0],
                      st_damage_min=[0 if bow else 1,0,0],st_damage_max=[0 if bow else 5,0,0],
                      fire_mods=[1,0,0],fire_times=[1500,0,0],fire_costs=[30 if bow else 10,0,0],
                      clip_size=1,max_range=[12 if bow else 20,0,0],
                      opt_range=[5 if bow else 1,0,0],end_opt_range=[9 if bow else 15,0,0],
                      target_size=[12*3.3/100 if bow else 1,0,0],
                      max_break_abs=300 if bow else 2000,weight=3500 if bow else 1500,
                      cost=2500 if bow else 100,g_cost=0,premium=0,
                      need_skills_m=2 if bow else 0,need_skills=[10] if bow else [],
                      need_specs_m=0,need_specs=[])
    if items.root_of(source)==items.FIRE_ARM:
        params['comp_array']=compatible(source,params)
    return params
