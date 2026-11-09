"""Timed combat effects for private clones; no live-account persistence."""
import asyncio
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

import inventory
import items
import progression
import storage
import training_items

FIRST = 90000
MAX_EFFECTS = 32
PATH = Path(__file__).resolve().parents[1] / 'data/training_effects.json'
ARRAYS = {'attribs': 5, 'skills': 5, 'specs': 15}
SCALARS = ('hp', 'sp', 'od', 'cp', 'ce', 'armor')


@lru_cache(maxsize=1)
def definitions():
    raw = json.loads(PATH.read_text(encoding='utf-8'))['definitions']
    result = {}
    for key, value in raw.items():
        type_id = int(key)
        if not 0 < value['duration'] <= 86400 or not 0 <= value['interval'] <= value['duration']:
            raise ValueError('Invalid training effect duration: ' + key)
        bonus = value['bonuses']
        if any(len(bonus[k]) != length for k, length in ARRAYS.items()):
            raise ValueError('Invalid training effect array: ' + key)
        numbers = [x for key in ARRAYS for x in bonus[key]] + [bonus[key] for key in SCALARS]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 10000 for x in numbers):
            raise ValueError('Invalid training effect value: ' + str(type_id))
        result[type_id] = value
    return result


def definition(type_id):
    return definitions().get(training_items.source_type(type_id))


def zero():
    return dict(**{key: [0] * length for key, length in ARRAYS.items()},
                **{key: 0 for key in SCALARS})


@dataclass
class Active:
    source: int
    started: float
    deadline: float


class Effects:
    def __init__(self, session):
        self.session = session
        self.active = {}
        self.bonus = zero()
        self.timer = None

    def close(self, notify=False):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        self.active.clear()
        self.bonus = zero()
        if notify:
            self.refresh()

    def check(self, source):
        value = definitions()[source]
        clock = asyncio.get_running_loop().time()
        self.active = {key: active for key, active in self.active.items() if active.deadline > clock}
        current = self.active.get(value['family'])
        if current:
            old = definitions()[current.source]['bonuses']
            new = value['bonuses']
            power = lambda bonus: sum(sum(bonus[k]) for k in ARRAYS) + sum(bonus[k] for k in SCALARS)
            if power(old) > power(new):
                raise ValueError('Уже действует более сильный эффект этого типа')
        elif len(self.active) >= MAX_EFFECTS:
            raise ValueError('Слишком много активных эффектов')

    def add(self, source):
        self.check(source)
        value = definitions()[source]
        clock = asyncio.get_running_loop().time()
        old = self.active.get(value['family'])
        started = old.started if old and old.source == source and value['interval'] else clock
        self.active[value['family']] = Active(source, started, clock + value['duration'])
        self.refresh()

    def refresh(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        clock = asyncio.get_running_loop().time()
        self.active = {key: active for key, active in self.active.items() if active.deadline > clock}
        total = zero()
        next_event = None
        for active in self.active.values():
            value = definitions()[active.source]
            interval = value['interval']
            pulses = min(value['duration'] // interval, int((clock - active.started) // interval)) if interval else 1
            for key in ARRAYS:
                total[key] = [max(old, delta * pulses) for old, delta in zip(total[key], value['bonuses'][key])]
            for key in SCALARS:
                total[key] = max(total[key], value['bonuses'][key] * pulses)
            event = active.deadline
            if interval and pulses < value['duration'] // interval:
                event = min(event, active.started + (pulses + 1) * interval)
            next_event = event if next_event is None else min(next_event, event)
        self.bonus = total
        character = self.session.character()
        character.training_effects = self
        self.session.inv.refresh_gear(push=False)
        if character.hp is not None:
            character.hp = min(character.hp, character.hp_max)
        if character.sp is not None:
            character.sp = min(character.sp, character.sp_max)
        self.session.combat.ap = min(self.session.combat.ap, character.ap_ceiling)
        self.session.push_stats()
        self.session.push_vitals()
        self.session.combat.c_ap()
        self.send_list()
        if next_event is not None:
            self.timer = asyncio.get_running_loop().call_later(max(0.01, next_event - clock), self.refresh)

    def send_list(self):
        self.session.send('e_list', mobi_id=0, effects=[FIRST + active.source for active in self.active.values()])

    def static(self, effect_type):
        source = effect_type - FIRST
        value = definitions().get(source)
        if value is None:
            return False
        bonus = value['bonuses']
        params = dict(type=effect_type, name=items.STRING_ID_OFFSET + source,
                      work_time=value['duration'] * 1000, update_delta=value['interval'] * 1000,
                      max_hp=bonus['hp'], max_sp=bonus['sp'], max_od=bonus['od'],
                      critical_probability=bonus['cp'], critical_evade=bonus['ce'], armor=bonus['armor'],
                      mob_exp=1, pl_exp=1, mob_drop=1, pl_drop=1, res_icon=1, immob=0, stun=0)
        for key, length in ARRAYS.items():
            selected = {i for i, number in enumerate(bonus[key]) if number}
            params[key + '_mask'], params[key] = progression.packed(bonus[key], selected, length)
        self.session.send('e_si', **params)
        return True

    def dynamic(self, effect_type):
        source = effect_type - FIRST
        active = next((value for value in self.active.values() if value.source == source), None)
        elapsed = int((asyncio.get_running_loop().time() - active.started) * 1000) if active else 0
        self.session.send('e_di', mobi_id=0, type=effect_type, time=max(0, elapsed), immob=0, stun=0)


def activate(fighter, uniq, target, ap_cost, peace_damage=None):
    """Called only after the ordinary action timer completed successfully."""
    fighter.healing = None
    row = fighter.store.item(uniq)
    if (row is None or row['char_id'] != fighter.sess.char_id or row['use_count'] <= 0 or fighter.dead
            or target.dead or not target.present(fighter.rc) or not target.is_player
            or target.sess.room is not fighter.sess.room or fighter.ap < ap_cost
            or target is not fighter and not progression.within_reach(
                fighter.cell, target.cell, fighter.sess.loc.width, fighter.sess.loc.height)):
        fighter.sess.send('actionCancel', release=1)
        return
    source = training_items.source_type(row['type_id'])
    peace = items.no_combat(row['type_id'])
    if (combat_blocked(fighter, peace) or peace and peace_damage is not None and peace_damage != (
            getattr(fighter, 'damage_revision', 0) + getattr(fighter, 'hit_revision', 0),
            getattr(target, 'damage_revision', 0) + getattr(target, 'hit_revision', 0))):
        fighter.sess.send('actionCancel', release=1)
        return
    effect = definition(row['type_id'])
    if effect is None:
        fighter.sess.send('actionCancel', release=1)
        return
    receiver = target.sess.training_effects
    try:
        receiver.check(source)
    except ValueError as reason:
        fighter.sess.send('actionCancel', release=1)
        fighter.sess.answer(str(reason))
        return
    with storage.atomic(fighter.store.db):
        left = row['use_count'] - 1
        if left > 0:
            fighter.store.update_item(uniq, use_count=left)
        else:
            fighter.store.delete_item(uniq)
    fighter.ap -= ap_cost
    receiver.add(source)
    fighter.sess.ground.remember_outfit()
    fighter.sess.ground.inventory_state()
    if left > 0:
        fighter.sess.inv.push_di(fighter.store.item(uniq))
    else:
        fighter.sess.inv.push_status(row, 0)
    fighter.rc.room.broadcast(('heal', dict(id=fighter.eid, target=target.eid,
                                           hp=target.character().vitals()['hcur'],
                                           sp=target.character().vitals()['scur'])))
    fighter.c_ap()


def combat_blocked(fighter, peace):
    import combat
    return combat.Fighter.medicine_blocked(fighter, peace)
