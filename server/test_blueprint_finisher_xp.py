"""Finishing attacks keep blueprint chance when their XP raises player level.

Runs real Fighter.fire_now/strike_now -> award_xp/credit_xp -> RoomCombat.kill
with deterministic hits and fake sessions, without any database or sockets.
"""
import asyncio
import os
import sqlite3
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

def no_database(*args, **kwargs):
    raise RuntimeError('This suite must not open a database')

sqlite3.connect = no_database

import bosses
import combat
import mobs
import progression
import inventory
import items
from testkit import check, fails


class Finisher:
    is_player = True
    eid = 1
    cell = 0
    dead = False
    fire_now = combat.Fighter.fire_now
    strike_now = combat.Fighter.strike_now
    award_xp = combat.Fighter.award_xp
    credit_xp = combat.Fighter.credit_xp
    level = property(lambda self: self.ch.level)
    character = lambda self: self.ch
    stats_changed = lambda *args: None
    hold_stats = lambda *args: None
    release_stats = lambda *args: None
    count_kill = lambda *args: None
    c_ap = lambda *args: None


def victim(eid, level):
    return NS(is_player=False, eid=eid, type_id=269, level=level, hp=100,
              cell=1, aim=None, stats=NS(name='test boss', hp_max=100,
              sp_max=0, xp_mult=1), present=lambda rc: True,
              dodge_melee=lambda: 0, crit_evade_melee=lambda: 0,
              sp_now=lambda: 0, apply_damage=lambda h, s: True)


# --- real finishing attack, XP level-up, corpse snapshot and loot roll ---
async def exercise():
    for attack in ('melee', 'ranged', 'ranged collateral'):
        for level in (1, 4):
            killer = Finisher()
            killer.ch = progression.Character()
            skill = progression.MELEE if attack == 'melee' else progression.SHOOTING
            cap = progression.skill_xp_max(level)
            killer.ch.skill[skill] = [level, cap - 1, cap]
            killer.ch.recalc()
            target = victim(2, level + 2)
            other = victim(3, level + 2)
            row = dict(char_id=7, ammo_count=1, brk=100, type_id=25566,
                       slot=inventory.PRIMARY, root=items.FIRE_ARM)
            killer.store = NS(item=lambda uniq: row, update_item=lambda *a, **k: None)
            killer.sess = NS(char_id=7, loc=NS(width=10, height=10),
                push_vitals=lambda: None,
                inv=NS(push_di=lambda row: None, wear_uniq=lambda *a: None))
            room = NS(ws=False, broadcast=lambda frame: None,
                npcs={2: target, 3: other}, players=[], loc=NS(title='test'))
            rc = NS(room=room, within_fire=lambda *a: True,
                after_hostile=lambda *a: None, hit_landed=lambda *a: None,
                push_vitals=lambda *a: None, quest_wants=lambda *a: frozenset(),
                settle_xp=lambda mob: None, corpse_gone=lambda *a: None,
                calm=lambda: None)
            rc.kill = lambda mob, player, **kw: combat.RoomCombat.kill(rc, mob, player, **kw)
            killer.rc = rc

            def burst(shooter, mob, cell, weapon, live, others):
                check('ranged finishing shot has ammunition', live, 1)
                if attack == 'ranged collateral':
                    others.append((other, 100, 0, True, 100))
                return 100, 0, 1, True

            rc.burst = burst
            with patch.object(combat.production, 'mined_by'), \
                    patch.object(combat.holdings, 'snapshot', return_value=None), \
                    patch.object(combat.mobs, 'adjacent', return_value=True), \
                    patch.object(combat, 'roll', return_value=True):
                if attack == 'melee':
                    killer.strike_now(target, None, (100, 100), combat.SPEC_BLADE, 5)
                else:
                    weapon = NS(num_shots=1, max_range=10, skill=skill, spec=None)
                    killer.fire_now(1, target, None, weapon, 5)
            label = '%s at player level %d' % (attack, level)
            check(label + ': actual damage XP raises level', killer.level > level, True)
            corpses = (target, other) if attack == 'ranged collateral' else (target,)
            for corpse in corpses:
                check(label + ': every corpse keeps pre-attack level',
                      corpse.blueprint_killer_level, level)
                chance = bosses.blueprint_drop_chance(level, 1)
                check(label + ': corpse chance uses level before XP',
                    bosses.blueprint_drop_chance(corpse.blueprint_killer_level, 1), chance)
                # A roll between old and new chances proves actual loot differs.
                roll = (chance + bosses.blueprint_drop_chance(killer.level, 1)) / 2
                with patch.object(mobs, 'carried', return_value=[]), \
                        patch.object(mobs, 'roll_table', return_value=[]), \
                        patch.object(mobs, 'quest_table', return_value=[]):
                    loot = mobs.loot_for(NS(type_id=269), NS(random=lambda: roll),
                        loc_id=82, killer_level=corpse.blueprint_killer_level)
                check(label + ': encrypted blueprint survives XP boundary', loot, [(2408, 1)])

try:
    asyncio.run(exercise())
except Exception:
    import traceback
    fails.append(traceback.format_exc())
if fails:
    for failure in fails:
        print(failure)
    raise SystemExit(1)
print('blueprint finisher XP OK')
