"""Timed combat effects shared by ordinary characters and private clones."""
import asyncio
from dataclasses import dataclass
from functools import lru_cache
import json
import logging
import math
import time
from pathlib import Path

import items
import progression
import storage
import item_templates

log = logging.getLogger("lava")

FIRST = 90000
MAX_EFFECTS = 32
PATH = Path(__file__).resolve().parents[1] / 'data/training_effects.json'
ARRAYS = {'attribs': 5, 'skills': 5, 'specs': 15}
SCALARS = ('hp', 'sp', 'od', 'cp', 'ce', 'armor')
# Ordinary articles only; event rewards and unidentified long variants stay out.
EXPERIENCE_UP = (3112, 3113, 3114, 3561)
EXPERIENCE_DOWN = (3201, 3202, 3203, 3205, 3206, 3207)
SCANNERS = (3789, 3826)
MAX_EXPERIENCE_MULTIPLIER = 1.7
MAX_TOTAL_EXPERIENCE_MULTIPLIER = 2.0
# Effect captions have their own preloaded strings; item names stay unchanged.
EXPERIENCE_NAME_OFFSET = 9_000_000


def experience_cap_text():
    return ("Максимально возможный суммарный бонус к опыту = +%d%% (не более x%g)."
            % (round((MAX_TOTAL_EXPERIENCE_MULTIPLIER - 1) * 100),
               MAX_TOTAL_EXPERIENCE_MULTIPLIER))


def name_id(source):
    return (EXPERIENCE_NAME_OFFSET if source in EXPERIENCE_UP else items.STRING_ID_OFFSET) + source


@lru_cache(maxsize=1)
def definitions():
    raw = json.loads(PATH.read_text(encoding='utf-8'))['definitions']
    result = {}
    for key, value in raw.items():
        type_id = int(key)
        if not 0 < value['duration'] <= 86400 or not 0 <= value['interval'] <= value['duration']:
            raise ValueError('Invalid effect duration: ' + key)
        bonus = value['bonuses']
        if any(len(bonus[k]) != length for k, length in ARRAYS.items()):
            raise ValueError('Invalid effect array: ' + key)
        numbers = [x for key in ARRAYS for x in bonus[key]] + [bonus[key] for key in SCALARS]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 10000 for x in numbers):
            raise ValueError('Invalid effect value: ' + str(type_id))
        result[type_id] = value
    for type_id in EXPERIENCE_UP + EXPERIENCE_DOWN + SCANNERS:
        row = items.wiki()[type_id]
        modifiers = {key: 1 + row.get(field, 0) / 100 for key, field in
                     (('mob_exp', 'exp_mobs_pct'), ('pl_exp', 'exp_players_pct'), ('mob_drop', 'loot_pct'))}
        if type_id in EXPERIENCE_UP:
            if any(not 1 < modifiers[key] <= MAX_EXPERIENCE_MULTIPLIER for key in ('mob_exp', 'pl_exp')):
                raise ValueError('Invalid experience booster: ' + str(type_id))
            family = 'experience_up'
        else:
            family = 'mob_drop' if type_id in SCANNERS else 'experience_down'
        result[type_id] = dict(duration=row['bonus_act_time'], interval=0, bonuses=zero(),
                               family=family, modifiers=modifiers, self_only=True)
    return result


def definition(type_id):
    return definitions().get(item_templates.source_type(type_id))


def zero():
    return dict(**{key: [0] * length for key, length in ARRAYS.items()},
                **{key: 0 for key in SCALARS})


def multiplier(session, name, *, bonus=0):
    manager = getattr(session, 'effects', None)
    values = []
    if manager is not None:
        clock = manager.clock()
        values = [definitions()[active.source].get('modifiers', {}).get(name, 1)
                  for active in manager.active.values() if active.deadline > clock]
    if name in ('mob_exp', 'pl_exp'):
        # INTUX is capped independently; additive weekend/residence bonuses
        # follow it up to +100% total, then reductions apply.
        boost = min(MAX_EXPERIENCE_MULTIPLIER, math.prod(value for value in values if value > 1))
        return min(MAX_TOTAL_EXPERIENCE_MULTIPLIER, boost + bonus) * math.prod(
            value for value in values if value <= 1)
    return math.prod(values)


def use_error(fighter, target, type_id):
    value = definition(type_id)
    if value is None:
        return None
    if value.get('self_only') and target is not fighter:
        return 'Этот предмет можно применить только к себе.'
    params = items.params_of(type_id)
    if 'buff_level' in params:
        required = params['buff_level']
        if fighter.character().level < required:
            return 'Для применения нужен уровень персонажа: %d.' % required
        return None
    # Registered/private templates retain their explicit independent gates.
    required = params.get('need_pvp_rep', 0)
    if required > fighter.character().rep:
        return 'Для применения нужен навык бойца: %d.' % required
    import inventory
    mask = params.get('need_skills_m', 0)
    levels = inventory.unpacked(mask, params.get('need_skills'), progression.SKILLS)
    for skill, needed in enumerate(levels):
        if mask & (1 << skill) and fighter.character().skill_level(skill) < needed:
            return 'Для применения нужен навык «%s» %d.' % (progression.SKILL_TITLES[skill], needed)
    return None


@dataclass
class Active:
    source: int
    started: float
    deadline: float


class Effects:
    persistent = True
    attribute = 'effects'

    def __init__(self, session):
        self.session = session
        self.char_id = session.char_id
        self.active = {}
        self.bonus = zero()
        self.timer = None
        self._paused_at = None

    def clock(self):
        if self._paused_at is not None:
            return self._paused_at
        return time.time() if self.persistent else asyncio.get_running_loop().time()

    def load(self):
        self._paused_at = None
        if self.persistent:
            store, char_id = self.session.combat.store, self.char_id
            clock = self.clock()
            active = {}
            with storage.atomic(store.db):
                for row in store.effects_for(char_id):
                    value = definitions().get(row['source'])
                    # Legacy rows have no checkpoint: preserve only their
                    # remaining real-time interval at the first new login.
                    anchor = row['checkpoint_at'] if row['checkpoint_at'] is not None else clock
                    if value and row['deadline'] > anchor:
                        shift = clock - anchor
                        current = Active(row['source'], row['started'] + shift, row['deadline'] + shift)
                        active[value['family']] = current
                        store.put_effect(char_id, value['family'], current.source,
                                         current.started, current.deadline, checkpoint_at=clock)
                    else:
                        store.db.execute('DELETE FROM char_effects WHERE char_id=? AND family=?',
                                         (char_id, row['family']))
            self.active = active
        self.refresh(notify=False)

    def pause(self):
        """Stop at socket loss, including a body awaiting combat logout."""
        if not self.persistent or self._paused_at is not None:
            return
        self._paused_at = self.clock()
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        # A failed expiry write may leave rows after the last in-memory
        # effect is gone. Flush those too, before this player leaves heartbeat.
        try:
            self.session.combat.store.checkpoint_effects([self.char_id], self._paused_at)
        except Exception:
            # The heartbeat checkpoint remains usable after a failed
            # disconnect write; never prevent room/socket cleanup.
            log.exception('Saving paused effects failed for character %s', self.char_id)

    def resume(self):
        if self._paused_at is None:
            return
        clock = time.time()
        shift = clock - self._paused_at
        active = {family: Active(row.source, row.started + shift, row.deadline + shift)
                  for family, row in self.active.items()}
        store = self.session.combat.store
        with storage.atomic(store.db):
            for family, row in active.items():
                store.put_effect(self.char_id, family, row.source, row.started,
                                 row.deadline, checkpoint_at=clock)
        self.active = active
        self._paused_at = None
        self.refresh(notify=False)

    def close(self, notify=False):
        self.pause()
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        self.active.clear()
        if notify:
            self.refresh()
        else:
            self.bonus = zero()

    def check(self, source):
        value = definitions()[source]
        clock = self.clock()
        self.active = {key: active for key, active in self.active.items() if active.deadline > clock}
        current = self.active.get(value['family'])
        if current:
            old = definitions()[current.source]
            def power(effect):
                bonus = effect['bonuses']
                return (sum(sum(bonus[k]) for k in ARRAYS) + sum(bonus[k] for k in SCALARS)
                        + sum(abs(v - 1) for v in effect.get('modifiers', {}).values()))
            if power(old) > power(value):
                raise ValueError('Уже действует более сильный эффект этого типа')
        elif len(self.active) >= MAX_EFFECTS:
            raise ValueError('Слишком много активных эффектов')

    def add(self, source):
        self.check(source)
        value = definitions()[source]
        clock = self.clock()
        old = self.active.get(value['family'])
        started = old.started if old and old.source == source and value['interval'] else clock
        self.active[value['family']] = Active(source, started, clock + value['duration'])
        self.refresh()

    def refresh(self, notify=True):
        character = self.session.character()
        previous = getattr(character, self.attribute, None)
        previous_od = (previous['od'] if self.persistent and previous is not None
                       else self.bonus['od'])
        if self.timer:
            self.timer.cancel()
            self.timer = None
        clock = self.clock()
        if self.persistent and self.active and self._paused_at is None:
            try:
                self.session.combat.store.checkpoint_effects([self.char_id], clock)
            except Exception:
                # The online heartbeat retries this checkpoint every second.
                # Persistence must not prevent expiry or the next effect timer.
                log.exception('Saving online effects failed for character %s', self.char_id)
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
        # Quest transactions copy character state; never attach the live session/timer.
        setattr(character, self.attribute, self.bonus if self.persistent else self)
        if self.persistent:
            # Gear already contains the previous flat effect bonuses. Replace
            # only that contribution; expiry must not depend on inventory SQL.
            before = previous if previous is not None else zero()
            for field, key in (('hp', 'hp'), ('st', 'sp'), ('od', 'od'), ('cp', 'cp'), ('ce', 'ce')):
                name = 'bonus_' + field
                setattr(character, name, getattr(character, name) + total[key] - before[key])
        else:
            self.session.inv.refresh_gear(push=False)
        if character.hp is not None:
            character.hp = min(character.hp, character.hp_max)
        if character.sp is not None:
            character.sp = min(character.sp, character.sp_max)
        fighter = self.session.combat
        ap_changed = total['od'] != previous_od
        if ap_changed and fighter.amax_sent is not None:
            # Keep the native room's equipment ceiling, adjusting only this effect.
            fighter.amax_sent += total['od'] - previous_od
        fighter.ap = min(fighter.ap, character.ap_ceiling, fighter.ap_max)
        if next_event is not None and self._paused_at is None:
            self.timer = asyncio.get_running_loop().call_later(max(0.01, next_event - clock), self.refresh)
        if notify:
            self.session.push_stats()
            self.session.push_vitals()
            if ap_changed:
                fighter.c_ap(amax=True)
            else:
                fighter.c_ap()
            self.send_list()

    def send_list(self):
        self.session.send('e_list', mobi_id=0, effects=[FIRST + active.source for active in self.active.values()])

    def static(self, effect_type):
        source = effect_type - FIRST
        value = definitions().get(source)
        if value is None:
            return False
        bonus = value['bonuses']
        params = dict(type=effect_type, name=name_id(source),
                      work_time=value['duration'] * 1000, update_delta=value['interval'] * 1000,
                      max_hp=bonus['hp'], max_sp=bonus['sp'], max_od=bonus['od'],
                      critical_probability=bonus['cp'], critical_evade=bonus['ce'], armor=bonus['armor'],
                      mob_exp=1, pl_exp=1, mob_drop=1, pl_drop=1, res_icon=1, immob=0, stun=0)
        params.update(value.get('modifiers', {}))
        for key, length in ARRAYS.items():
            selected = {i for i, number in enumerate(bonus[key]) if number}
            params[key + '_mask'], params[key] = progression.packed(bonus[key], selected, length)
        self.session.send('e_si', **params)
        return True

    def dynamic(self, effect_type):
        source = effect_type - FIRST
        active = next((value for value in self.active.values() if value.source == source), None)
        elapsed = int((self.clock() - active.started) * 1000) if active else 0
        self.session.send('e_di', mobi_id=0, type=effect_type, time=max(0, elapsed), immob=0, stun=0)


def activate(fighter, uniq, target, ap_cost, peace_damage=None):
    """Called only after the ordinary action timer completed successfully."""
    import inventory
    fighter.healing = None
    row = fighter.store.item(uniq)
    if (row is None or row['char_id'] != fighter.sess.char_id or row['use_count'] <= 0 or fighter.dead
            or target.dead or not target.present(fighter.rc) or not target.is_player
            or target.sess.room is not fighter.sess.room or fighter.ap < ap_cost
            or target is not fighter and not progression.within_reach(
                fighter.cell, target.cell, fighter.sess.loc.width, fighter.sess.loc.height)):
        fighter.sess.send('actionCancel', release=1)
        return
    source = item_templates.source_type(row['type_id'])
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
    error = use_error(fighter, target, row['type_id'])
    if error:
        fighter.sess.send('actionCancel', release=1)
        fighter.sess.answer(error)
        return
    receiver = getattr(target.sess, 'effects', None)
    if receiver is None:
        fighter.sess.send('actionCancel', release=1)
        return
    try:
        receiver.check(source)
    except ValueError as reason:
        fighter.sess.send('actionCancel', release=1)
        fighter.sess.answer(str(reason))
        return
    import intux_confirmation
    if not intux_confirmation.finish_allowed(fighter, row):
        return
    with storage.atomic(fighter.store.db):
        for char_id in sorted({fighter.sess.char_id, target.sess.char_id}):
            if not fighter.store.lock_quest_character(char_id):
                fighter.sess.send('actionCancel', release=1)
                return
        row = fighter.store.item(uniq)
        if (row is None or row['char_id'] != fighter.sess.char_id
                or row['root'] != items.HEAL or row['slot'] not in (inventory.BAG, *inventory.HAND_SLOTS)
                or row['use_count'] <= 0 or row.get('count', 1) <= 0
                or uniq in fighter.sess.inv.locked):
            fighter.sess.send('actionCancel', release=1)
            return
        clock = receiver.clock()
        old = receiver.active.get(effect['family'])
        started = old.started if old and old.source == source and effect['interval'] else clock
        fighter.store.put_effect(target.sess.char_id, effect['family'], source, started,
                                 clock + effect['duration'], checkpoint_at=clock)
        left = row['use_count'] - 1
        if left > 0:
            fighter.store.update_item(uniq, use_count=left)
        else:
            fighter.store.delete_item(uniq)
    fighter.ap -= ap_cost
    # Publish the exact committed interval; do not revalidate after spending a dose.
    receiver.active[effect['family']] = Active(source, started, clock + effect['duration'])
    receiver.refresh()
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
