"""Restored coasts: local, loot-free animal profiles on the common mob ladder.

The same crocodile types in quest locations retain their original stats and
loot. The manifest is read once; combat hits and loot rolls do no file I/O.
"""
import copy
from functools import lru_cache
import json
import math
from pathlib import Path


@lru_cache(maxsize=1)
def manifest():
    return json.loads((Path(__file__).resolve().parents[1] /
                       'data/coastal_locations.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def profiles():
    doc = manifest()
    result = {}
    for loc_id, row in doc['locations'].items():
        city = doc['cities'][row['city']]
        level, mob = city['level'], city['mob']
        if type(level) is not int or not 1 <= level <= 17 or type(mob) is not int:
            raise ValueError('Invalid coastal crocodile profile')
        result[(int(loc_id), mob)] = level
    import boundary_world
    for ident, row in boundary_world.by_id().items():
        profile = row.get('crocodile')
        if profile:
            result[(ident, profile['type_id'])] = profile['level']
    return result


def without_loot(loc_id, type_id):
    # The selected old level-19 Magrib patrol is XP-only everywhere it stands.
    # Low-level camp soldiers, officers and quest crocodiles keep their own tables.
    return type_id == 98 or (loc_id, type_id) in profiles()


@lru_cache(maxsize=20)
def fangs(level):
    """Gold knife attack tier, interpolated between the native even levels."""
    import items
    rows=[]
    for t,(root,name) in items.catalogue().items():
        if root == items.COLD_ARM and name.startswith('knife_lvl') and name.endswith('_G'):
            params=items.params_of(t)
            rows.append((max(params.get('need_skills') or [0]),params))
    low=max((r for r in rows if r[0]<=level),key=lambda r:r[0])
    high=min((r for r in rows if r[0]>=level),key=lambda r:r[0])
    fraction=(level-low[0])/(high[0]-low[0]) if high[0]!=low[0] else 0
    return {key:math.floor(low[1][key]+(high[1][key]-low[1][key])*fraction+.5)
            for key in ('h_damage_min','h_damage_max','strike_cost','strike_time')}


def patrol_stats():
    """A local copy: twice ordinary level-19 HP, existing G damage mod."""
    import items,mobs
    stats=copy.copy(mobs.stats(98));stats.hp_max*=2
    old=items.params_of(stats.weapon_type_id)
    stats.weapon_type_id=25078  # machine_gun_1_lvl_19_mod_damage_gold
    gold=items.params_of(stats.weapon_type_id)
    modes=[]
    for index,mode in enumerate(stats.balanced_modes):
        modes.append(dict(mode,
            dmin=max(1,round(mode['dmin']*gold['h_damage_min'][index]/old['h_damage_min'][index])),
            dmax=max(1,round(mode['dmax']*gold['h_damage_max'][index]/old['h_damage_max'][index]))))
    stats.balanced_modes=tuple(modes);row=max(modes,key=lambda r:r['reach'])
    stats.dmg_min,stats.dmg_max=row['dmin'],row['dmax']
    stats.plain_weapon=False
    return stats


def prepare_room(rc):
    """Ordinary-level defence, gold-knife natural attacks and the patrol bonus.

    Pay ordinary same-level XP; keep melee movement and the native model.
    A shared mobs.stats entry is never modified, including on respawn.
    """
    import battle_balance as balance
    moves = manifest()['locations'].get(str(rc.room.loc.id), {}).get('spawn_moves', {})
    for target in rc.mobs.values():
        if target.type_id == 98:
            stats=patrol_stats()
            target.stats=stats;target.hp,target.sp,target.ap=stats.hp_max,stats.sp_max,stats.ap_max
            continue
        level = profiles().get((rc.room.loc.id, target.type_id))
        if level is None:
            continue
        reference = balance.ordinary_mob_reference()[0][level]
        stats = copy.copy(target.stats)
        if stats.role != 'animal' or stats.ranged or stats.weapon_type_id is not None:
            raise ValueError('Coastal profile requires an unarmed animal')
        stats.level = level
        stats.xp_mult = 1.0
        import mobs
        stats.xp_pool = int(mobs.LEVELS[str(level)]['xp_pool'])
        destination = moves.get(str(target.home))
        if destination is not None:
            target.home = target.cell = destination
            npc = rc.room.npcs[target.eid]
            rc.room.npcs[target.eid] = npc._replace(cell=destination)
        for key,source in (('hp_max','hp'),('sp_max','sp')):
            floor=round(mobs.LEVELS[str(level)][source]*mobs.ROLES['mob']['hp_mult'])
            setattr(stats,key,max(floor,round(reference[key]/balance.MOB_BALANCE_DIVISOR)))
        for key in ('armor', 'dodge', 'hit', 'crit', 'crit_evade', 'spec'):
            setattr(stats, key, reference[key])
        stats.ap_max = balance.ordinary_mob_ap(level)
        attack=fangs(level)
        stats.dmg_min,stats.dmg_max=attack['h_damage_min'],attack['h_damage_max']
        stats.attack_ap,stats.attack_time=attack['strike_cost'],attack['strike_time']/1000
        stats.attack_name='Клыки';stats.range=stats.shots=1
        stats.ranged=False;stats.melee_only=True;stats.weapon_type_id=None
        if hasattr(stats,'balanced_modes'):del stats.balanced_modes
        target.stats = stats
        target.hp, target.sp, target.ap = stats.hp_max, stats.sp_max, stats.ap_max
