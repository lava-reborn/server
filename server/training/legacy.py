"""Verified classic emitters for the sandbox; original item tables stay intact.

Evidence: saved wiki pages «Излучатель пистолет», «Излучатель (Дробовик)»,
«Излучатель (нож)», «Излучатель (Лекалка)», «Блок питания ЭК».
Reload, swing and healing timings absent from these pages keep existing values.
Later event weapons and unlinked aliases must not stand in for classic forms.
"""
KNIFE, PISTOL, SHOTGUN, HEALER, BATTERY = 1547, 1569, 1570, 1572, 6190
CLASSIC = frozenset((KNIFE, PISTOL, SHOTGUN, HEALER))
LEVELS = {PISTOL: 7, SHOTGUN: 7}
# No corroborating numeric table/identity for these aliases; do not issue fake guns.
# 6023 is the separately documented 2013 Impulsoverter, not the classic pistol.
UNCONFIRMED = frozenset((1571, 3485, 6024, 6214, 6215, 7086, 36331, 41224))


def apply(source, params):
    if source not in CLASSIC:
        return params
    params.update(weight=1531, cost=12000, g_cost=0, premium=0,
                  need_specs_m=0, need_specs=[])
    if source == KNIFE:
        params.update(h_damage_min=0, h_damage_max=200, st_damage_min=0, st_damage_max=0,
                      max_range=1.7, strike_cost=0, max_break_abs=10000,
                      need_skills_m=0, need_skills=[], exchang=1)
    elif source == HEALER:
        params.update(min_h_rest=500, max_h_rest=500, min_st_rest=0, max_st_rest=0,
                      use_count=7000, exchang=0)
    else:
        params.update(weapon_type=0 if source == PISTOL else 1, clip_size=10,
                      comp_array=[BATTERY], max_break_abs=10000, exchang=0,
                      need_skills_m=2, need_skills=[7],
                      st_damage_min=[0,0,0], st_damage_max=[0,0,0])
        if source == PISTOL:
            params.update(fire_mods=[1,0,0], h_damage_min=[200,0,0], h_damage_max=[600,0,0],
                          max_range=[7,0,0], opt_range=[2,0,0], end_opt_range=[4,0,0],
                          target_size=[7*5.7/100,0,0], fire_times=[500,0,0], fire_costs=[11,0,0])
        else:
            params.update(fire_mods=[3,6,9],h_damage_min=[300,250,200],h_damage_max=[300,250,200],
                          max_range=[10,10,10],opt_range=[2,2,2],end_opt_range=[10,10,10],
                          target_size=[.7,1,1.1],fire_times=[400,800,1200],fire_costs=[11,20,30])
    return params
