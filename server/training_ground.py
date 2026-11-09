"""Private shooting-range contexts. No training identity enters the real store."""
import asyncio
import copy
from functools import lru_cache
import logging
import itertools
import json
import os
import re
import secrets
import time

import accounts
import training_items
import training_rules
import training_layout
import training_shop
import training_effects
import training_balance
import training_mobs
import training_sets
import training_legacy
import training_ammo
import training_labels
import training_party
import combat
import craft
import npcs
import sets
import inventory
import items
import mobs
import movement
import names
import quests
import mail
import progression
import rooms
import storage
import shop_bands
import world
from protocol import Str

log = logging.getLogger('lava')
BERT = 2088
ENTRY_QUEST = 9301
EXIT_QUEST = 9302
MARKET = 35
RANGE = 108
ARENA_WIDTH, ARENA_HEIGHT = 72, 144
COMPUTER_CELL = training_layout.BY_KEY['computer'].cell(ARENA_WIDTH)
CONTROL_CELL = COMPUTER_CELL + 1
LOCATIONS = {108: (COMPUTER_CELL, 'Пустынный полигон', CONTROL_CELL),
             106: (COMPUTER_CELL, 'Пустынный полигон — вторая площадка', CONTROL_CELL)}
LEGACY_LOCATIONS = frozenset((78, 59))
FIGHT_START = 78 * ARENA_WIDTH + 36
ENEMY_SPAWNS = {location: (55 * ARENA_WIDTH + 36, 35 * ARENA_WIDTH + 36, 8 * ARENA_WIDTH + 65) for location in LOCATIONS}
SPAWN_LABELS = ('Ближняя', 'Средняя', 'Дальняя — справа сверху')
DEFAULT_SPAWN = 2
TERMINAL = 1263
TERMINAL_CELL = LOCATIONS[RANGE][0]
MAX_SESSIONS = 16
MAX_ITEMS = 32
MAX_LEVEL = 20
PAGE_SIZE = 10
IDLE_SECONDS = 1800
ACTIVE = set()
SERIAL_BASE = 1 << 40
SERIALS = itertools.count(SERIAL_BASE, 1 << 20)
PLAYER_IDS = itertools.count(100_000_000)
ENABLED = os.environ.get('LAVA_TRAINING_GROUND', '0') == '1'
READ_COMMANDS = frozenset(('getInfo', 'rp_get_info', 'ss_get_si', 'ss_get_di',
                           'ss_get', 'ss_get_s_si', 'e_get_si', 'e_get_di', 'q_si', 'q_di', 'q_status', 'ah_search'))
PLAY_COMMANDS = frozenset(('moveTo', 'ss_move', 'ss_use', 'ss_heap_c'))


def integer(value, low, high):
    if isinstance(value, bool):
        raise ValueError('Ожидается целое число')
    n = int(str(value))
    if not low <= n <= high:
        raise ValueError('Значение вне допустимого диапазона')
    return n


CONTRABAND_TRADER = 2391


@lru_cache(maxsize=1)
def contraband():
    return frozenset(items.stock_for(CONTRABAND_TRADER))


@lru_cache(maxsize=1)
def obtainable_sources():
    craft._read()
    eligible, rewards = set(), set()
    for trader in set(items.stock_table()) | set(npcs.STOCK) | set(craft._STOCK):
        eligible.update(items.stock_for(trader))
    # The real stall depends on its city: stock_for(type) alone misses
    # weapons and armour supplied by city bands rather than legacy lists.
    known = set(items.stock_table()) | set(npcs.STOCK) | set(craft._STOCK) | set(shop_bands.SELLERS)
    seen = set()
    for location in shop_bands.CITY_OF:
        for _cell, trader in world.location(location).spawns:
            key = trader, shop_bands.city(location)
            if trader in known and key not in seen:
                seen.add(key)
                eligible.update(items.stock_for(trader, location))
    for quest in quests.QUESTS.values():
        if quest.give and not quests.acquisition_blocked(quest):
            rewards.update(quest.rew_obj)
            rewards.update(t for t, _n in quest.rew_also)
            rewards.update(t for t, _n, _weight in quest.rew_random)
    eligible.update(rewards)
    for type_id in tuple(eligible):
        if type_id in sets.SETS:
            eligible.update(sets.SETS[type_id]['members'].values())
    return frozenset(eligible), frozenset(rewards)


def item_family(name):
    name = re.sub(r'_([AGP])_mod', '_X_mod', name)
    return re.sub(r'_(?:gold|pm|g|p)$', '', name, flags=re.I)


def item_line(type_id):
    if items.premium(type_id):
        return 'P'
    return 'G' if combat.gold_item(type_id) else 'A'


@lru_cache(maxsize=1)
def item_catalogue():
    eligible, rewards = obtainable_sources()
    extra = {t for info in sets.SETS.values() if info['level'] <= MAX_LEVEL
             for t in info['members'].values()}
    extra.update(t for info in training_sets.records().values() if info['level'] <= MAX_LEVEL
                 for t in info['members'].values())
    for t, (root, name) in items.catalogue().items():
        if root in (items.FIRE_ARM, items.COLD_ARM) and (
                17 < inventory.item_level(t) <= MAX_LEVEL and '_lvl_' in name
                and not name.endswith('_mob') or name.startswith('ufo_gun')
                or '(R)' in names.text(items.STRING_ID_OFFSET + t)):
            extra.add(t)
    if 1572 in items.catalogue():
        extra.add(1572)
    extra.update(training_effects.definitions())
    extra.update(training_legacy.CLASSIC)
    extra.update(training_ammo.EXTRA_SOURCES)
    extra.update(t for t, info in items.wiki().items() if items.root_of(t) == items.HEAL
                 and any(word in items.catalogue()[t][1].casefold() for word in
                         ('newyear', 'valentine', 'oct31', 'march', 'may9', 'june', 'ny20', 'febr')))
    eligible = eligible | extra
    # P counterparts are offered only inside the sandbox. Do not enumerate the
    # thousands of unused/placeholder premium templates as usable equipment.
    families = {item_family(items.catalogue()[t][1]) for t in eligible
                if t in items.catalogue() and not items.out_of_game(t)}
    premium_sources = {t for t, (root, name) in items.catalogue().items()
                       if items.premium(t) and (
                           item_family(name) in families or
                           root in (items.HEAL, items.AMMO) and
                           (t in items.wiki() or t in items.heal_manual()))}
    eligible = eligible | premium_sources
    mod_labels = {}
    for rec in craft.rows().values():
        if rec.get('family') == 'upgrade' and rec.get('line') in ('A', 'G'):
            mod_labels[int(rec['mod'])] = names.text(items.STRING_ID_OFFSET + int(rec['blueprint'])).partition('$')[0]
    out = {}
    for type_id in eligible:
        if training_items.is_copy(type_id) or type_id in training_legacy.UNCONFIRMED:
            continue
        if type_id not in items.catalogue():
            continue
        root, name = items.catalogue()[type_id]
        if root not in (items.FIRE_ARM, items.COLD_ARM, items.WEAR, items.HEAL, items.AMMO):
            continue
        if (items.retired(type_id) or type_id in items.ADMIN_OVERRIDES):
            continue
        p = items.params_of(type_id) or {}
        if not p:
            continue
        level = inventory.item_level(type_id) if root in items.BREAKABLE_ROOTS else 0
        if root in items.BREAKABLE_ROOTS and not level:
            reference = training_balance.afro_of(type_id)
            level = inventory.item_level(reference) if reference is not None else 0
        level = training_legacy.LEVELS.get(type_id, level)
        level = training_ammo.LEVELS.get(type_id, level)
        if level > MAX_LEVEL:
            continue
        category = {items.FIRE_ARM: 'weapon', items.COLD_ARM: 'weapon',
                    items.WEAR: 'armour', items.HEAL: 'medicine', items.AMMO: 'ammo'}[root]
        if root == items.WEAR and (p.get('slot_type', -1) + inventory.HEAD) == inventory.BELT:
            category = 'pouch'
        label = training_labels.title(type_id)
        if root in (items.FIRE_ARM, items.COLD_ARM) and type_id in training_ammo.SPECIAL_WEAPONS:
            category = 'experimental_weapon'
        elif root in (items.FIRE_ARM, items.COLD_ARM) and (
                type_id in contraband() or (craft.mod_of(type_id) or (None,))[0] in contraband()
                or name.startswith('ufo_gun') or '(R)' in label
                or any(word in name.casefold() for word in ('prototype', 'experimental', '_quest'))
                or type_id in rewards and '_lvl_' not in name and type_id not in contraband() and type_id < 4000):
            category = 'special_weapon'
        elif root == items.HEAL:
            if name.startswith('ufo_gun') or any(word in name.casefold() for word in (
                    'newyear', 'valentine', 'oct31', 'march', 'may9', 'june', 'ny20', 'november', 'febr')):
                category = 'event_medicine'
            elif training_effects.definition(type_id):
                category = 'buff'
            elif items.stimulant_unavailable(type_id):
                continue

        aliases = {1569: 'Излучатель', 1571: 'Излучатель · вариант II',
                   1572: 'Лечебный излучатель', 1547: 'Излучатель · холодное оружие',
                   3485: 'Излучатель · дальность', 6024: 'Излучатель · автомат',
                   6214: 'Излучатель · пистолет (A)', 6215: 'Излучатель · автомат (A)',
                   7086: 'Излучатель · нож', 36331: 'Излучатель · холодное оружие II',
                   41224: 'Излучатель · автомат (P)'}
        label = training_ammo.NAMES.get(type_id, aliases.get(type_id, label))
        if root in items.BREAKABLE_ROOTS:
            label += ' · %d ур.' % level
        if type_id in contraband():
            label += ' · Контрабанда'
        if type_id in mod_labels:
            label += ' · ' + mod_labels[type_id]
        elif root == items.FIRE_ARM:
            reference = training_balance.afro_of(type_id)
            if reference in mod_labels:
                label += ' · ' + mod_labels[reference]
        out[type_id] = (category, level, label)
    return out


@lru_cache(maxsize=1)
def mob_catalogue():
    known = world.mob_types()
    return {int(k): '%s · %d ур.' % (names.text(int(k)).replace('<br>', ' · '), int(v.get('level', 0))) for k, v in mobs.TYPES.items()
            if int(k) in known and known[int(k)][0] == world.MOB
            and v.get('role') in ('mob', 'animal', 'boss')
            and 1 <= int(v.get('level', 0)) <= 20 and not world.retired_creature(int(k))}


def control_cell(location=RANGE):
    return LOCATIONS[location][2]


@lru_cache(maxsize=len(LOCATIONS))
def arena_location(location=RANGE):
    loc = copy.copy(world.location(location))
    loc.width, loc.height = ARENA_WIDTH, ARENA_HEIGHT
    loc.obstacles, loc.shoot_over = set(), frozenset()
    loc.entries, loc.spawns = [], []
    loc.war, loc.pvp, loc.newbies = 1, 1, False
    return loc


@lru_cache(maxsize=len(LOCATIONS))
def geometry(location=RANGE):
    loc = arena_location(location)
    free = set(range(loc.width * loc.height))
    arena = {cell for cell in free if cell // loc.width < 100
             and mobs.hex_distance(cell, LOCATIONS[location][0], loc.width) > 4}
    return frozenset(free - arena), frozenset(arena), FIGHT_START


def preset(level=12):
    return dict(skills=[level, level, level, 0, 0], specs=[-1] * progression.SPECS,
                gear={})


def profile_slots(profile):
    hand = iter(inventory.HAND_SLOTS)
    slots = {}
    for type_id in profile['gear']:
        root = items.root_of(type_id)
        if root in (items.FIRE_ARM, items.COLD_ARM):
            slots[type_id] = next(hand, inventory.BAG)
        elif root == items.WEAR:
            slots[type_id] = inventory.HEAD + items.params_of(type_id)['slot_type']
        else:
            slots[type_id] = inventory.BAG
    return slots


def validate_profile(raw, rules=None):
    skills = [integer(x, 0, MAX_LEVEL) for x in raw['skills']]
    specs = [integer(x, -1, progression.SPEC_MAX) for x in raw['specs']]
    if len(specs) == progression.SPECS:
        specs[12:] = [-1] * 3
    if len(skills) != progression.SKILLS or len(specs) != progression.SPECS or max(skills) < 1:
        raise ValueError('Проверьте навыки персонажа')
    gear = {}
    if len(raw['gear']) > MAX_ITEMS:
        raise ValueError('Слишком много предметов')
    worn = set()
    for raw_id, count in raw['gear'].items():
        t = integer(raw_id, 1, 65535)
        if t not in item_catalogue():
            raise ValueError('Предмет недоступен на полигоне')
        root = items.root_of(t)
        n = integer(count, 1, 5000 if root == items.AMMO else 50 if root == items.HEAL else 1)
        slot = inventory.BAG
        if root == items.WEAR:
            slot = inventory.HEAD + items.params_of(t)['slot_type']
        if slot != inventory.BAG:
            if slot in worn:
                raise ValueError('На один слот выбрано несколько вещей')
            worn.add(slot)
        gear[t] = n
    if sum(n if items.root_of(t) == items.HEAL else 1 for t, n in gear.items()) > 256:
        raise ValueError('Слишком много отдельных предметов')
    training_items.prepare(item_catalogue())
    result = dict(skills=skills, specs=specs, gear=gear)
    ch = character(result, rules)
    fields = []
    slots = profile_slots(result)
    for source, n in gear.items():
        t = training_items.copy_type(source)
        f = inventory.new_fields(t, n)
        f['type_id'] = t
        f['slot'] = slots[source]
        fields.append(f)
    ch.set_gear(inventory.gear_bonus(fields, ch), inventory.card_repeat(fields))
    if sum((items.params_of(r['type_id']) or {}).get('weight', 0) * r.get('count', 1) for r in fields) > ch.max_weight():
        raise ValueError('Пресет превышает допустимый вес персонажа')
    for row in fields:
        if row['slot'] != inventory.BAG:
            error = inventory.weapon_requirement_error(row, ch)
            if error:
                raise ValueError(error)
    return result


class TrainingCharacter(progression.Character):
    def __init__(self, rules=None):
        super().__init__()
        self.training_rules = rules if rules is not None else training_rules.current()
    def save(self, store):
        if store is not getattr(self, '_training_store', None):
            raise ValueError('Тренировочный персонаж сохраняется только внутри своей сессии')
        return super().save(store)

    def attr(self, i):
        effects = getattr(self, 'training_effects', None)
        extra = effects.bonus['attribs'][i] if effects else 0
        return max(0, round((super().attr(i) + extra) * self.training_rules.attributes[i]))

    @property
    def hp_max(self):
        return max(1, round(super().hp_max * self.training_rules.health))

    @property
    def sp_max(self):
        return max(1, round(super().sp_max * self.training_rules.stamina))

    def set_gear(self, bonus, repeat=(0, 0)):
        changed = super().set_gear(bonus, (0, 0) if self.training_rules.combat_v2 else repeat)
        effects = getattr(self, 'training_effects', None)
        if effects:
            for key in ('hp', 'st', 'od', 'cp', 'ce'):
                setattr(self, 'bonus_' + key, getattr(self, 'bonus_' + key) + effects.bonus['sp' if key == 'st' else key])
        return changed

    def gain_xp(self, *args, **kwargs):
        return {'skills': set(), 'specs': set(), 'attribs': set()}


def character(profile, rules=None):
    ch = TrainingCharacter(rules)
    for i, level in enumerate(profile['skills']):
        ch.set_skill(i, level)
    ch.recalc()
    for i, level in enumerate(profile['specs']):
        ch.set_spec(i, level)
    return ch


class TrainingFighter(combat.Fighter):
    def prepare_weapon(self, weapon, ammo):
        rules = self.sess.ground.rules
        result = rules.weapon(weapon, ammo)
        if rules.combat_v2:
            multiplier = training_balance.intellect_multiplier(self.character())
            result = result._replace(dmin=training_balance.rounded(result.dmin * multiplier),
                                     dmax=training_balance.rounded(result.dmax * multiplier),
                                     sdmin=training_balance.rounded(result.sdmin * multiplier),
                                     sdmax=training_balance.rounded(result.sdmax * multiplier))
        return result

    def healing_spec(self, vitals):
        if self.sess.ground.rules.combat_v2:
            return 8 if vitals['hcur'] < 0.3 * vitals['hmax'] else 9
        return combat.SPEC_SURGERY if vitals['hcur'] < 0.3 * vitals['hmax'] else combat.SPEC_FIRST_AID

    def use_heal(self, params, kind):
        row = self.sess.inv.find(params.get('obj'))
        if row is not None and self.sess.ground.rules.combat_v2:
            si = items.params_of(row['type_id']) or {}
            mask = si.get('need_skills_m', 0) or 0
            required = inventory.unpacked(mask, si.get('need_skills'), progression.SKILLS)
            for index in range(2, progression.SKILLS):
                if mask >> index & 1 and self.character().skill_level(index) < required[index]:
                    self.ack(inventory.RES_LEVEL)
                    self.sess.answer('Не хватает навыка для использования этого средства')
                    return
        return super().use_heal(params, kind)

    def heal_now(self, uniq, target, peace_damage=None, ap_cost=0):
        row = self.store.item(uniq)
        if row is not None and training_effects.definition(row['type_id']):
            return training_effects.activate(self, uniq, target, ap_cost, peace_damage)
        return super().heal_now(uniq, target, peace_damage, ap_cost)

    def e_get_si(self, params):
        if not self.sess.training_effects.static(int(params.get('type', 0))):
            super().e_get_si(params)

    def e_get_di(self, params):
        if int(params.get('type', 0)) - training_effects.FIRST in training_effects.definitions():
            self.sess.training_effects.dynamic(int(params['type']))
        else:
            super().e_get_di(params)

    def resend_room(self, resumed=False):
        super().resend_room(resumed)
        self.sess.training_effects.send_list()

    def regen(self):
        if not self.sess.ground.rules.combat_v2:
            return super().regen()
        if self.dead:
            return
        ch = self.character()
        vitals = ch.vitals()
        hp, sp = vitals['hcur'], vitals['scur']
        constitution = ch.attr(progression.CONSTITUTION)
        if hp < vitals['hmax']:
            gain = constitution if hp >= 0.3 * vitals['hmax'] else 1
            gain = max(0, min(gain, vitals['hmax'] - hp, sp))
            hp, sp = hp + gain, sp - gain
        sp = min(vitals['smax'], sp + max(1, constitution // 5))
        if (hp, sp) != (vitals['hcur'], vitals['scur']):
            ch.hp, ch.sp = hp, sp
            self.rc.push_vitals(self)


    def allied(self, other):
        if not other.is_player:
            return False
        mine = self.sess.ground.owner.party()
        theirs = getattr(other.sess, 'ground', None)
        return bool(mine is not None and theirs is not None
                    and other.sess is theirs.clone and theirs.owner.char_id in mine.members)

    def armor(self):
        rules = self.character().training_rules
        worn = sum((items.params_of(row['type_id']) or {}).get('armor_class', 0)
                   for row in self.sess.inv.rows() if row['slot'] in inventory.WEAR_SLOTS
                   and (rules.broken_armour or row['brk'] > 0))
        effect = self.sess.training_effects.bonus['armor']
        return (progression.armor_class(self.character(), worn) + rules.effect_armour + effect) * rules.armour

    def award_xp(self, *args, **kwargs):
        pass

    def credit_xp(self, *args, **kwargs):
        pass

    def count_kill(self, *args):
        pass

    def pvp_kill(self, *args):
        pass

    def pvp_allowed(self):
        return True

    def die(self, killer):
        self.dead = True
        self.cancel_timers()
        if self.sess is self.sess.ground.clone:
            self.sess.ground.finish('Поражение', force=True)
        else:
            self.sess.ground.target_defeated(self)


class TrainingCombat(combat.RoomCombat):
    def prepare_weapon(self, weapon, ammo):
        return self.room.ground.rules.weapon(weapon, ammo)

    def mob_attack(self, mob, target, t):
        weapon = getattr(mob, 'training_weapon', None)
        if weapon is None:
            return super().mob_attack(mob, target, t)
        mob.next_attack = t + mob.stats.attack_time + mobs.ATTACK_PAUSE
        self.room.broadcast(('faAim', dict(id=mob.eid,
            ang=mobs.direction(mob.cell, target.cell, self.room.loc.width), num_shots=weapon.num_shots)))
        scaled = weapon._replace(**{field: training_balance.rounded(getattr(weapon, field) * mob.training_ground.mob_damage / 100)
                                   for field in ('dmin', 'dmax', 'sdmin', 'sdmax')})
        mob.aim = asyncio.get_running_loop().call_later(combat.pace.paced(mob.stats.attack_time),
                                                       self.mob_burst, mob, target, scaled)

    def keep_hours(self):
        pass

    def recall_kills(self):
        pass

    def kill(self, victim, killer, **kwargs):
        if victim.is_player:
            victim.die(killer)
        else:
            victim.training_ground.target_defeated(victim)

    def _step(self):
        super()._step()
        for ground in tuple(self.room.grounds.values()):
            if ground.phase == 'fight' and ground.enemy is not None and not ground.stationary:
                ground.enemy_turn()

    def sync_ws(self):
        self.set_ws(any(ground.phase == 'fight' for ground in self.room.grounds.values())
                    or self.hostilities(combat.now()))


class TrainingRoom(rooms.Room):
    def view_player(self, pid):
        # Roster requests can precede the other client's map acknowledgement.
        for ground in self.grounds.values():
            if ground.clone.pid == pid:
                return ground.clone
            if ground.enemy is not None and ground.enemy.pid == pid:
                return ground.enemy
        return None

    def broadcast(self, event, exclude=None):
        if isinstance(event, tuple):
            command, params = event
            shooter = None
            if command == 'faShot':
                shooter = next((ground for ground in self.grounds.values()
                                if params.get('id') == ground.clone.pid), None)
                if params.get('status') == 1:
                    self.shot_owner = shooter
                    if shooter is not None:
                        shooter.shots += 1
                else:
                    self.shot_owner = None
            if command in ('faHit', 'caHit'):
                shooter = (getattr(self, 'shot_owner', None) if command == 'faHit' else
                           next((ground for ground in self.grounds.values()
                                 if params.get('id') == ground.clone.pid), None))
                if shooter is not None and params.get('target') != shooter.clone.pid:
                    shooter.hits += 1
                    shooter.damage += params.get('dmg', 0)
        super().broadcast(event, exclude)


def clone_class(base):
    class Clone(base):
        """Only a whitelist of base handlers is reachable; persistence stays local."""
        @property
        def pid(self):
            return self.training_pid

        def char_for_entity(self, entity_id):
            peer = self.room.view_player(entity_id)
            return peer.char_id if peer is not None else None

        def send(self, *cmd, **p):
            if cmd and cmd[0] == 'cmdAck':
                self.training_acks = getattr(self, 'training_acks', 0) + 1
            return super().send(*cmd, **p)

        def save_place(self):
            pass

        def fee_recount(self):
            pass

        def skill_recount(self):
            pass

        def fee_gate(self, params):
            return params

        def skill_gate(self, params):
            return params

        def terminal_quest(self, p):
            ground = self.ground
            if int(p.get('mob', 0)) != ground.terminal_id:
                raise ValueError('Подойдите к компьютеру')
            ground.require_terminal()
            return quests.get(EXIT_QUEST)

        def cmd_q_st(self, p):
            quest = self.terminal_quest(p)
            offered = quests.given_by(TERMINAL)
            index = int(p.get('q_idx', -1))
            if not 0 <= index < len(offered) or offered[index] != EXIT_QUEST:
                raise ValueError('Задание недоступно')
            if self.inv.store.has_quest(self.char_id, EXIT_QUEST):
                raise ValueError('Задание уже взято')
            q_id = self.inv.store.take_quest(self.char_id, EXIT_QUEST, {'obj': 1}, True)
            self.ground.save_settings()
            self.send('cmdAck', res=0)
            cmd, fields = quest.di_frame(q_id, {'obj': 1}, True)
            self.send(cmd, **fields)

        def cmd_q_co(self, p):
            quest = self.terminal_quest(p)
            row = self.inv.store.quest(int(p.get('q_id', 0)))
            if not row or row['char_id'] != self.char_id or row['type'] != EXIT_QUEST:
                raise ValueError('Задание недоступно')
            self.inv.store.finish_quest(row['q_id'], self.char_id, EXIT_QUEST, require_active=True)
            self.send('cmdAck', res=0)
            self.ground.exit()

        def cmd_q_ca(self, p):
            q_id = int(p.get('q_id', 0))
            row = self.inv.store.quest(q_id)
            if not row or row['char_id'] != self.char_id or row['type'] != EXIT_QUEST:
                raise ValueError('Задание недоступно')
            self.inv.store.drop_quest(q_id, self.char_id)
            self.ground.save_settings()
            self.send('cmdAck', res=0)

        def cmd_q_di(self, p):
            q_id = int(p.get('q_id', 0))
            row = self.inv.store.quest(q_id)
            if row and row['char_id'] == self.char_id and row['type'] == EXIT_QUEST:
                command, fields = quests.get(EXIT_QUEST).di_frame(q_id, {'obj': 1}, True)
            else:
                command, fields = quests.stub_di(q_id)
            self.send(command, **fields)

        def cmd_q_status(self, p):
            t = int(p.get('q_type', 0))
            q = quests.get(t)
            available = t == EXIT_QUEST and self.ground.phase == 'ready' and not self.inv.store.has_quest(self.char_id, t)
            self.send('q_status', type=t, status=int(available),
                      name=q.string_id(quests.NAME) if q else 0, q_type=q.q_type if q else 0)

        def cmd_ah_search(self, p):
            self.send('ah_sresult', page=0, count=0, next=0)

        def count_bag(self):
            pass

        def arm_passage(self, *args):
            pass

        def take_passage(self, *args):
            pass

        @property
        def party_member_id(self):
            return self.ground.owner.char_id if self is self.ground.clone else None

        def party(self):
            return self.ground.owner.party() if self is self.ground.clone else None

        def push_stats(self, **groups):
            self.ground.combat_stats(self)
            self.send('rp_info', **self.character().rp_info(**groups))

        def enter_location(self):
            self.send('lcall', id=self.ground.location, ws=int(self.room.ws), ie=0,
                      g_id=1 << 26)

        def cmd_lenter(self, p):
            ground = self.ground
            if ground.phase == 'loading':
                ground.phase = 'fight'
                ground.room.ws = True
                ground.started = time.monotonic()
                if ground.enemy is not None:
                    ground.enemy.combat.entered()
            if self not in self.room.players:
                self.pos = training_party.free_spawn(self.room, self.pos, excluded=self)
            self.combat.amax_sent = self.character().ap_ceiling
            self.send('lenter', pos=self.pos, aspd=progression.AP_REGEN, amax=self.character().ap_ceiling)
            if self in self.room.players:
                self.room.snapshot_for(self)
            else:
                self.room.enter(self)
            self.combat.entered()
            self.send_player_info()
            self.push_stats()
            self.push_vitals()
            self.ground.state()
            if getattr(ground, 'open_after_load', False):
                ground.open_after_load = False
                self.send('tg', op='open', mob=ground.mob_type)

        def cmd_getInfo(self, p):
            target = int(p.get('id', 0))
            if not target:
                self.send_player_info()
                self.push_vitals()
            elif self.room.view_player(target) is not None:
                peer = self.room.view_player(target)
                fields = rooms.player_info(peer)
                fields.update(name=Str(peer.nick), ally=int(self.combat.allied(peer.combat)))
                self.send('userInfo_Player', **fields)
                self.send('usrUp', **rooms.player_health(peer))
            else:
                self.send_npc_info(target)

        def send_npc_info(self, eid):
            npc = self.room.npc(eid)
            if npc is None:
                return
            post = self.ground.posts.get(eid)
            if post is None:
                return super().send_npc_info(eid)
            params = dict(type_list=list(training_shop.stock(post)), bg_objects=[], bg_obj_rep_req=[],
                          pmod=1, smod=0, rmod=0) if post.line else {}
            self.send(world.USERINFO[world.TRADER if post.line else world.COMMONER], id=eid,
                      name=training_layout.NAME_IDS[post.key], sex=0, res=post.resource,
                      ail=0, ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=[EXIT_QUEST] if post.key == 'computer' else [],
                      take_quests=[EXIT_QUEST] if post.key == 'computer' else [], m_hello=[], can_set_home=0,
                      can_banking=0, can_trophy=0, can_repair=0, can_trade=int(bool(post.line)),
                      tg_terminal=int(not post.line), tg_shop=int(bool(post.line)),
                      tg_station=Str(post.key), tg_title=Str(post.title), **params)

        def cmd_ss_get_di(self, p):
            parsed = inventory.parse_oid(p.get('obj'))
            if parsed:
                for ground in self.room.grounds.values():
                    if ground.serial_base <= parsed[0] < ground.serial_base + (1 << 20):
                        row = ground.store.item(parsed[0])
                        if row and (row['type_id'], row['root']) == parsed[1:]:
                            self.send(inventory.DI_COMMAND[row['root']], **inventory.di_params(row, ground.store))
                            return
                if any(parsed[0] == mobs.VIRTUAL_BASE + ground.mob_eid
                       for ground in self.room.grounds.values() if ground.mob_eid is not None):
                    return self.combat.ss_get_di(p)
            return self.inv.ss_get_di(p)

        def cmd_ss_get(self, p):
            peer = self.room.view_player(int(p.get('target', 0) or 0))
            if peer is not None and peer is not self:
                # Read-only view: never switch the receiving clone's store.
                reader = inventory.Inventory(self, peer.inv.store)
                reader.shown, reader.acked = self.inv.shown, self.inv.acked
                reader.ss_get(p)
            elif not self.combat.ss_get(p):
                self.inv.ss_get(p)

        def handle_training(self, cmd, p):
            if cmd == 'p_op':
                training_party.command(self.ground, p)
                return
            if cmd == 'ss_create':
                if int(p.get('s_type', -1)) == inventory.SESSION_TRADE:
                    self.inv.open_trade(p)
                else:
                    self.send('cmdAck', res=inventory.RES_REFUSED)
                return
            if cmd == 'ss_upd':
                self.inv.ss_upd(p)
                return
            if cmd == 'lcall':
                self.enter_location()
                return
            if cmd == 'lenter':
                self.cmd_lenter(p)
                return
            if cmd == 'userMsg':
                if str(p.get('entry', '')).lstrip().startswith('/') and not ('group' not in p and p.get('to')):
                    self.send('cmdAck', res=0)
                    self.answer('Игровые команды недоступны в тренировке. Используйте компьютер полигона.')
                else:
                    owner = self.ground.owner
                    owner.training_chat = True
                    try:
                        owner.cmd_userMsg(p)
                    finally:
                        owner.training_chat = False
                return
            if cmd == 'chkml':
                self.send('cmdAck', res=0)
                if int(p.get('mode', 0)) == 255:
                    self.send('svml', data=list(mail.PRICES), time=list(mail.TIMES))
                else:
                    self.send('lsml', id=[], date=[], name=[], flag=[], subj=[])
                return
            if cmd == 'q_list':
                rows = self.inv.store.quests(self.char_id)
                self.send('q_list', q_id=[r['q_id'] for r in rows], q_types=[r['type'] for r in rows])
                return
            if cmd in ('q_st', 'q_co', 'q_ca'):
                getattr(self, 'cmd_' + cmd)(p)
                return
            if cmd == 'ss_move' and (int(p.get('to', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,) or int(p.get('from', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,)):
                self.send('cmdAck', res=inventory.RES_REFUSED)
                return
            if cmd in READ_COMMANDS or (cmd in PLAY_COMMANDS and self.ground.phase in ('ready', 'fight')):
                if cmd == 'getInfo' and int(p.get('id', 0)) not in (0, *self.ground.posts) \
                        and self.room.view_player(int(p.get('id', 0))) is None \
                        and int(p.get('id', 0)) not in self.room.combat.mobs:
                    return
                if cmd == 'moveTo':
                    path = p.get('path', [])
                    limit = self.loc.width * self.loc.height
                    if not isinstance(path, list) or len(path) > limit or any(
                            not isinstance(c, int) or c < 0 or c >= limit or c in self.loc.obstacles for c in path):
                        cell = self.live_cell()
                        self.pos = cell
                        self.send('breakMv', id=0, pos=cell)
                        return
                fn = getattr(self, 'cmd_' + cmd)
                fn(p)
                if cmd in ('ss_move', 'ss_use'):
                    self.inv.refresh_gear()
                    self.ground.remember_outfit()
                    self.ground.combat_stats(self)
                return
            if cmd == 'moveTo':
                self.send('breakMv', id=0, pos=self.live_cell())
                return
            module = __import__(base.__module__)
            if module.expects_ack(cmd, p):
                self.send('cmdAck', res=inventory.RES_REFUSED)
    return Clone


class Ground:
    def __init__(self, owner):
        self.owner = owner
        training_items.prepare(item_catalogue())
        self.token = secrets.token_hex(16)
        self.phase = 'ready'
        self.profile = preset(max(1, min(MAX_LEVEL, owner.character().level)))
        source = owner.character()
        self.profile['skills'] = [max(0, min(MAX_LEVEL, r[0])) for r in source.skill]
        if not max(self.profile['skills']):
            self.profile['skills'][progression.SHOOTING] = 1
        self.profile['specs'] = [max(-1, min(progression.SPEC_MAX, r[0])) for r in source.spec]
        for row in sorted(owner.inv.rows(), key=lambda row: row['slot'] != inventory.PRIMARY):
            t = row['type_id']
            if t not in item_catalogue():
                continue
            if row['root'] in (items.FIRE_ARM, items.COLD_ARM) and t in self.profile['gear']:
                continue
            if row['slot'] in inventory.BODY_SLOTS or row['root'] in (items.AMMO, items.HEAL):
                n = row['count'] if row['root'] == items.AMMO else 1
                self.profile['gear'][t] = min(5000 if row['root'] == items.AMMO else 50,
                                             self.profile['gear'].get(t, 0) + n)
        try:
            self.profile = validate_profile(self.profile)
        except ValueError:
            self.profile['gear'] = {}
            self.profile = validate_profile(self.profile)
        self.opponent = preset(max(self.profile['skills']))
        self.mob_type = 11 if 11 in mob_catalogue() else next(iter(mob_catalogue()))
        self.enemy = None
        self.enemy_cache = None
        self.stationary = False
        self.mob_health = self.mob_damage = 100
        self.rules = training_rules.current()
        self.spawn_point = DEFAULT_SPAWN
        self.location = RANGE
        self.mode = 'mob'
        saved = owner.inv.store.training_profile(owner.char_id)
        if saved is not None:
            try:
                if saved.get('version') != 1:
                    raise ValueError('Unsupported training profile')
                rules = training_rules.Rules.parse(saved.get('rules', self.rules.as_dict()))
                player = validate_profile(saved['player'], rules)
                opponent = validate_profile(saved['opponent'], rules)
                location = integer(saved.get('location', RANGE), 1, 65535)
                if location in LEGACY_LOCATIONS:
                    location = RANGE
                if location not in LOCATIONS:
                    raise ValueError('Unsupported training location')
                mob_type = integer(saved.get('mob', self.mob_type), 1, 100000)
                if mob_type not in mob_catalogue():
                    raise ValueError('Unsupported training opponent')
                spawn_point = integer(saved.get('spawn_point', DEFAULT_SPAWN), 0, len(SPAWN_LABELS) - 1)
                stationary = integer(saved.get('stationary', 0), 0, 1)
                mob_health = integer(saved.get('mob_health', 100), 25, 300)
                mob_damage = integer(saved.get('mob_damage', 100), 25, 300)
                mode = saved.get('mode', 'mob')
                if mode not in ('mob', 'fighter'):
                    raise ValueError('Unsupported training mode')
                self.profile, self.opponent = player, opponent
                self.rules = rules
                self.mob_health, self.mob_damage = mob_health, mob_damage
                self.location, self.mob_type = location, mob_type
                self.spawn_point, self.stationary, self.mode = spawn_point, bool(stationary), mode
            except (ValueError, TypeError, KeyError, AttributeError):
                log.warning('Saved training profile unavailable for character %s', owner.char_id)
        self.context = 'computer'
        self.corpse_id = None
        self.corpse_timer = None
        self.applied_profile = None
        self.outfit_revision = 0
        self.closed = False
        self.inside = False
        self.pending = None
        self.last_request = 0.0
        self.last_catalogue_request = 0.0
        self.last_activity = time.monotonic()
        self.timer = None
        self.store = accounts.Store.temporary()
        self.serial_base = next(SERIALS)
        self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('items',?)", (self.serial_base,))
        self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('char_quests',?)", (self.serial_base,))
        self.store.db.commit()
        self.shots = self.hits = self.damage = 0
        self.started = 0.0
        self.clone = None
        try:
            self.Clone = clone_class(owner.__class__)
            self.clone = self.make_clone('Тренировка', owner.active)
            loc = copy.copy(arena_location(self.location))
            loc.spawns = []
            loc.pvp = 1
            self.room = TrainingRoom(loc, rooms.IdAllocator(), {}, key=(self.location, self.token))
            self.room.npcs.clear()
            self.room.ground = self
            self.room.grounds = {self.token: self}
            self.room.owner_ids = {owner.pid: self.clone.pid}
            module = __import__(owner.__class__.__module__)
            self.post_ids = {post.key: module.ROOMS.ids.npc() for post in training_layout.POSTS}
            self.terminal_id = self.post_ids['computer']
            self.mob_eid = None
            self.populate_posts()
            self.room.combat = TrainingCombat(self.room, self.store)
            self.clone.room = self.room
            self.clone.loc = loc
            self.clone.pos = control_cell(self.location)
            self.apply(self.clone, self.profile)
            if isinstance(saved, dict) and saved.get('inside') is True and saved.get('exit_quest') is True:
                self.store.take_quest(self.clone.char_id, EXIT_QUEST, {'obj': 1}, True)
        except Exception:
            self.store.close()
            raise

    @property
    def distance(self):
        return round(mobs.hex_distance(self.clone.live_cell(), ENEMY_SPAWNS[self.location][self.spawn_point],
                                       self.clone.loc.width))

    def populate_posts(self):
        self.posts = {self.post_ids[p.key]: p for p in training_layout.POSTS
                      if not p.line or training_shop.stock(p)}
        for eid, post in self.posts.items():
            cell = post.cell(self.room.loc.width)
            if cell in self.room.loc.obstacles:
                raise ValueError('Training post is blocked: ' + post.key)
            root = world.TRADER if post.line else world.COMMONER
            self.room.npcs[eid] = rooms.NPC(cell, post.resource, root)

    def require_post(self):
        eid = self.post_ids[self.context]
        if not progression.within_reach(self.clone.live_cell(), self.room.npcs[eid].cell,
                                        self.clone.loc.width, self.clone.loc.height):
            raise ValueError('Подойдите к выбранной стойке или компьютеру')

    def open_post(self, eid):
        post = self.posts.get(eid)
        if post is None or not progression.within_reach(self.clone.live_cell(), self.room.npcs[eid].cell,
                                                       self.clone.loc.width, self.clone.loc.height):
            raise ValueError('Подойдите к стойке или компьютеру')
        if self.phase != 'ready':
            raise ValueError('Сначала завершите тренировку: кнопка «К компьютеру»')
        if post.line:
            raise ValueError('Снаряжение выдаётся через окно торговли')
        self.context = post.key
        self.state()
        self.clone.send('tg', op='open', mob=self.mob_type, context=Str(post.key),
                        title=Str(post.title), category=Str(post.category), wclass=post.weapon_class)

    def remember_outfit(self):
        """Save an equipped preset, not every spare/free item in the bag."""
        gear = {}
        for row in sorted(self.clone.inv.rows(), key=lambda row: row['slot'] not in inventory.BODY_SLOTS):
            source = training_items.source_type(row['type_id'])
            if source not in item_catalogue():
                continue
            root = row['root']
            if row['slot'] in inventory.BODY_SLOTS:
                gear[source] = 1
            elif root in (items.HEAL, items.AMMO) and len(gear) < MAX_ITEMS:
                maximum = 5000 if root == items.AMMO else 50
                gear[source] = min(maximum, gear.get(source, 0) + row['count'])
        if self.profile['gear'] != gear:
            self.outfit_revision += 1
        self.profile['gear'] = gear
        self.applied_profile = copy.deepcopy(self.profile)

    def configure_player(self, profile):
        """Changing training skills never deletes items bought at the posts."""
        clone = self.clone
        clone.combat.cancel_timers()
        clone.stop_walk()
        ch = character(profile, self.rules)
        ch._training_store = self.store
        ch.char_id, ch.name = clone.char_id, clone.active['name']
        ch.training_effects = clone.training_effects
        clone.char = ch
        clone.inv.refresh_gear(push=False)
        ch.hp, ch.sp = ch.hp_max, ch.sp_max
        ch.save(self.store)
        self.profile['skills'], self.profile['specs'] = profile['skills'], profile['specs']
        self.remember_outfit()

    def fighter_preset(self, set_type):
        selected = sets.SETS.get(set_type)
        if selected is None or not all(t in item_catalogue() for t in selected['members'].values()):
            raise ValueError('Комплект недоступен')
        level = selected['level']
        profile = preset(level)
        profile['specs'][:8] = [min(5, max(3, (level + 3) // 4))] * 8
        profile['gear'] = {t: 1 for t in selected['members'].values()}
        guns = [t for t, (category, item_level, _label) in item_catalogue().items()
                if category == 'weapon' and item_level <= level
                and items.root_of(t) == items.FIRE_ARM and item_line(t) == selected['variant']
                and not craft.mod_of(t) and t not in contraband()
                and any(a in item_catalogue() for a in items.params_of(t).get('comp_array', ()))]
        if guns:
            gun = min(guns, key=lambda t: (-item_catalogue()[t][1],
                                         items.params_of(t).get('weapon_type', 0), t))
            profile['gear'][gun] = 1
            ammo = next(a for a in items.params_of(gun)['comp_array'] if a in item_catalogue())
            profile['gear'][ammo] = 20
            params = items.params_of(gun)
            required = inventory.unpacked(params.get('need_specs_m'), params.get('need_specs'), progression.SPECS)
            mask = params.get('need_specs_m', 0) or 0
            for index in range(progression.SPECS):
                if mask >> index & 1:
                    profile['specs'][index] = max(3, required[index])
        return validate_profile(profile, self.rules)

    def save_settings(self):
        self.owner.inv.store.save_training_profile(self.owner.char_id, dict(
            version=1, inside=self.inside, room=self.room.key[1],
            exit_quest=self.inside and self.store.has_quest(self.clone.char_id, EXIT_QUEST),
            player=self.profile, opponent=self.opponent, location=self.location, rules=self.rules.as_dict(),
            mob=self.mob_type, spawn_point=self.spawn_point, stationary=int(self.stationary), mode=self.mode,
            mob_health=self.mob_health, mob_damage=self.mob_damage))

    def change_location(self, location):
        training_party.relocate(self, location)

    def make_clone(self, label, source=None):
        # No account registration/password hashing, and no persistent login slot.
        aid = self.store.db.execute("INSERT INTO accounts(login, hash, created) VALUES(?, ?, ?)",
                                    (secrets.token_hex(8), secrets.token_hex(16), int(time.time()))).lastrowid
        self.store.db.commit()
        source = source or self.owner.active
        cid, _ = self.store.create_character(aid, label, source['sex'], source['res'])
        clone = self.Clone(self.owner.writer, self.owner.peer)
        clone.ground = self
        clone.training_pid = rooms.player_id(next(PLAYER_IDS))
        clone.char_id = cid
        clone.active = dict(self.store.character(cid))
        if label == 'Тренировка':
            clone.active['name'] = self.owner.nick
        clone.char = progression.Character.load(self.store, cid)
        clone.inv = training_shop.Inventory(clone, self.store)
        clone.combat = TrainingFighter(clone)
        clone.training_effects = training_effects.Effects(clone)
        clone.transport = None
        return clone

    def apply(self, clone, profile):
        if getattr(clone, 'ground', None) is not self or clone.inv.store is not self.store:
            raise ValueError('Пресет можно применять только к клону своей тренировки')
        clone.combat.cancel_timers()
        clone.stop_walk()
        ch = character(profile, self.rules)
        ch._training_store = self.store
        ch.char_id, ch.name = clone.char_id, clone.active['name']
        ch.training_effects = clone.training_effects
        clone.char = ch
        if self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq'] > self.serial_base + (1 << 20) - 2048:
            raise ValueError('Лимит тренировки исчерпан; войдите в центр заново')
        for row in clone.inv.rows():
            self.store.delete_item(row['uniq'])
        slots = profile_slots(profile)
        for source, n in profile['gear'].items():
            t = training_items.copy_type(source)
            root = items.root_of(t)
            slot = slots[source]
            if root == items.HEAL:
                for _ in range(n):
                    clone.inv.create(t)
            else:
                clone.inv.create(t, n, slot=slot)
        clone.inv.refresh_gear(push=False)
        ch.hp, ch.sp = ch.hp_max, ch.sp_max
        ch.save(self.store)
        if clone is self.clone:
            self.applied_profile = copy.deepcopy(profile)
        # Leave ammunition in the bag: ordinary loading rules are used in combat.

    def touch(self):
        self.last_activity = time.monotonic()
        if self.timer is None:
            self.timer = asyncio.get_running_loop().call_later(IDLE_SECONDS, self.idle)

    def idle(self):
        self.timer = None
        left = IDLE_SECONDS - (time.monotonic() - self.last_activity)
        if left <= 0:
            self.exit()
        else:
            self.timer = asyncio.get_running_loop().call_later(left, self.idle)

    @staticmethod
    def equipment_meta(profile, prefix):
        ids = list(profile['gear'])
        slots = profile_slots(profile)
        return {prefix + 'ids': ids,
                prefix + 'labels': [item_catalogue()[t][2] for t in ids],
                prefix + 'slots': [slots[t] if slots[t] != inventory.BAG else 0 for t in ids]}

    def inventory_state(self):
        live = []
        for ground in self.room.grounds.values():
            live.extend(inventory.oid_of(row) for row in ground.clone.inv.rows())
            if ground.enemy:
                live.extend(inventory.oid_of(row) for row in ground.enemy.inv.rows())
        self.clone.send('tg', op='inventory', live_oids=live, outfit_rev=self.outfit_revision,
                        gear=Str(','.join('%d:%d' % pair for pair in self.profile['gear'].items())),
                        skills=self.profile['skills'], specs=self.profile['specs'])

    def combat_stats(self, clone):
        if clone is not self.clone:
            return
        gun = clone.combat.primary()
        params = items.params_of(gun['type_id']) if gun and gun['root'] == items.FIRE_ARM else None
        pair = progression.crit_chance(clone.char, params['weapon_type']) if params else None
        values = (clone.combat.armor(), pair[0] if pair else 0,
                  clone.combat.crit_evade_ranged(), clone.combat.dodge_melee())
        if values != getattr(self, '_combat_stats', None):
            self._combat_stats = values
            clone.send('tg', op='combat_stats', armour=values[0], critical=values[1],
                       anticritical=values[2], dodge=values[3])

    def state(self, message=''):
        c = self.clone
        live = []
        for ground in self.room.grounds.values():
            live.extend(inventory.oid_of(row) for row in ground.clone.inv.rows())
            if ground.enemy:
                live.extend(inventory.oid_of(row) for row in ground.enemy.inv.rows())
        virtual_uid = 0
        if self.mob_eid is not None and self.mob_eid in self.room.combat.mobs:
            mob = self.room.combat.mobs[self.mob_eid]
            if mob.weapon_oid():
                live.append(mob.weapon_oid())
                virtual_uid = mobs.VIRTUAL_BASE + self.mob_eid
        c.send('tg', op='state', token=Str(self.token), active=1, phase=Str(self.phase), outfit_rev=self.outfit_revision, participants=len(self.room.grounds),
               live_oids=live, virtual_uid=virtual_uid, message=Str(message), level=c.char.level, hp=c.char.hp_max,
               sp=c.char.sp_max, ap=c.char.ap_ceiling,
               location=self.location, locations=list(LOCATIONS), location_labels=[Str(v[1]) for v in LOCATIONS.values()],
               spawn_point=self.spawn_point, spawn_labels=[Str(label) for label in SPAWN_LABELS],
               distance=self.distance, stationary=int(self.stationary), mob_health=self.mob_health, mob_damage=self.mob_damage, selected_mob=self.mob_type, selected_mode=Str(self.mode),
               rules=Str(self.rules.description()), rule_values=Str(self.rules.values()), armour=c.combat.armor(), regen=progression.AP_REGEN, owner=Str(self.owner.nick), arena_width=ARENA_WIDTH, arena_height=ARENA_HEIGHT, loaded=int(c in self.room.players), spec_max=progression.SPEC_MAX,
               **self.equipment_meta(self.profile, 'gear_'),
               **self.equipment_meta(self.opponent, 'enemy_'),
               skills=self.profile['skills'], specs=self.profile['specs'],
               gear=Str(','.join('%d:%d' % pair for pair in self.profile['gear'].items())),
               enemy_skills=self.opponent['skills'], enemy_specs=self.opponent['specs'],
               enemy_gear=Str(','.join('%d:%d' % pair for pair in self.opponent['gear'].items())))

    def require_terminal(self):
        if self.phase != 'ready' or not progression.within_reach(
                self.clone.live_cell(), LOCATIONS[self.location][0], self.clone.loc.width, self.clone.loc.height):
            raise ValueError('Подойдите к компьютеру после завершения боя')

    def request(self, p):
        op = str(p.get('op', ''))
        if p.get('token') != self.token:
            raise ValueError('Окно тренировки устарело')
        if op == 'exit':
            self.require_terminal()
            self.exit()
            return
        now = time.monotonic()
        if op == 'catalogue':
            if now - self.last_catalogue_request < 0.03:
                raise ValueError('Дождитесь загрузки списка и повторите')
            self.last_catalogue_request = now
        else:
            if now - self.last_request < 0.08:
                raise ValueError('Дождитесь ответа на предыдущее действие и повторите')
            self.last_request = now
        self.touch()
        if op == 'return':
            self.finish('Возврат к компьютеру', force=True)
            return
        if op == 'abort':
            self.finish('Бой прерван')
            return
        if op == 'open':
            self.open_post(integer(p.get('npc', self.terminal_id), 1, 2**31-1))
            return
        if self.phase != 'ready':
            raise ValueError('Сначала завершите тренировку')
        self.require_post()
        if op == 'recover':
            if self.context != 'player':
                raise ValueError('Восстановление доступно у инструктора')
            self.clone.char.hp, self.clone.char.sp = self.clone.char.hp_max, self.clone.char.sp_max
            self.clone.combat.ap = self.clone.char.ap_ceiling
            self.clone.push_vitals()
            self.clone.combat.c_ap()
            self.state('Тренировочный персонаж восстановлен')
        elif op == 'location':
            self.require_terminal()
            self.change_location(integer(p.get('location'), 1, 65535))
            self.state('Тренировочная локация изменена')
        elif op == 'rules':
            try:
                rules = training_rules.Rules.from_values(str(p.get('values', '')))
            except (ValueError, TypeError):
                raise ValueError('Проверьте правила: множители от 0,01 до 10; добавка брони от 0 до 200.') from None
            validate_profile(self.profile, rules)
            validate_profile(self.opponent, rules)
            self.require_terminal()
            self.rules = rules
            self.configure_player(self.profile)
            self.clone.send_player_info()
            self.clone.push_stats()
            self.clone.push_vitals()
            self.clone.combat.ap = self.clone.character().ap_ceiling
            self.clone.combat.c_ap()
            self.save_settings()
            self.state('Правила сессии применены и сохранены')
        elif op == 'spawn':
            self.spawn_point = integer(p.get('spawn_point'), 0, len(SPAWN_LABELS) - 1)
            self.save_settings()
            self.state('Точка противника сохранена')
        elif op == 'catalogue':
            post = training_layout.BY_KEY[self.context]
            request = dict(p)
            if post.key != 'computer':
                request.update(category=post.category, wclass=post.weapon_class)
            elif request.get('category', 'mob') not in ('mob', 'weapon', 'set', 'armour', 'pouch', 'ammo', 'medicine'):
                raise ValueError('Неизвестная категория')
            self.catalogue(request)
        elif op == 'fighterpreset':
            self.require_terminal()
            self.opponent = self.fighter_preset(integer(p.get('set'), 1, 65535))
            self.mode = 'fighter'
            self.save_settings()
            self.state('Боец собран: комплект, оружие и патроны. При желании замените снаряжение.')
        elif op == 'apply':
            who = p.get('who', 'player')
            if who not in ('player', 'enemy'):
                raise ValueError('Неизвестный пресет')
            raw = dict(skills=str(p.get('skills', '')).split(','),
                       specs=str(p.get('specs', '')).split(','), gear={})
            pairs = str(p.get('gear', '')).split(',')
            if len(pairs) > MAX_ITEMS:
                raise ValueError('Слишком много предметов')
            for pair in pairs:
                if pair:
                    t, n = pair.split(':')
                    if t in raw['gear']:
                        raise ValueError('Повтор предмета')
                    raw['gear'][t] = n
            if who == 'enemy':
                for text in tuple(raw['gear']):
                    source = int(text)
                    if source in item_catalogue() and items.root_of(source) == items.FIRE_ARM:
                        compatible = [t for t in items.params_of(source).get('comp_array', ())
                                      if t in item_catalogue()]
                        if compatible and not any(str(t) in raw['gear'] for t in compatible):
                            raw['gear'][str(compatible[0])] = 100
            profile = validate_profile(raw, self.rules)
            if who == 'player':
                if self.context == 'player':
                    self.configure_player(profile)
                else:
                    self.apply(self.clone, profile)
                    self.profile = profile
                self.clone.send_player_info()
                self.clone.push_stats()
                self.clone.push_vitals()
                self.clone.combat.ap = self.clone.character().ap_ceiling
                self.clone.combat.amax_sent = self.clone.character().ap_ceiling
                self.clone.combat.c_ap()
            else:
                self.opponent = profile
                self.mode = 'fighter'
            self.save_settings()
            self.state('Пресет применён и сохранён')
        elif op == 'start':
            self.require_terminal()
            spawn_point = integer(p.get('spawn_point', self.spawn_point), 0, len(SPAWN_LABELS) - 1)
            mob_health = integer(p.get('mob_health', self.mob_health), 25, 300)
            mob_damage = integer(p.get('mob_damage', self.mob_damage), 25, 300)
            self.stationary = integer(p.get('stationary', 0), 0, 1) == 1
            mode = str(p.get('mode', 'mob'))
            if mode not in ('mob', 'fighter'):
                raise ValueError('Неизвестный противник')
            mob = integer(p.get('mob', self.mob_type), 1, 100000)
            if mode == 'mob' and mob not in mob_catalogue():
                raise ValueError('Моб недоступен')
            self.mob_type = mob
            self.spawn_point = spawn_point
            self.mob_health, self.mob_damage = mob_health, mob_damage
            self.start(mode)
            self.save_settings()

    def catalogue(self, p):
        cat = str(p.get('category', 'weapon'))
        page = integer(p.get('page', 0), 0, 10000)
        level = integer(p.get('level', 0), 0, MAX_LEVEL)
        query = str(p.get('query', '')).strip().casefold()[:48]
        wclass = integer(p.get('wclass', -1), -1, 6)
        upgrade = str(p.get('upgrade', 'all'))
        if upgrade not in ('all', 'base', 'modified'):
            raise ValueError('Неизвестный вариант улучшения')
        line = str(p.get('line', 'all'))
        if line not in ('all', 'A', 'G', 'P', 'C'):
            raise ValueError('Неизвестная версия предмета')
        if cat == 'set':
            rows = [(t, '%s · %d ур. (%s)' % (v['name'], v['level'], v['variant']))
                    for t, v in sets.SETS.items() if v['variant'] in ('A', 'G')
                    and (line == 'all' or line == v['variant'])
                    and (not level or v['level'] == level) and query in v['name'].casefold()
                    and all(member in item_catalogue() for member in v['members'].values())]
        elif cat == 'mob':
            group = str(p.get('group', 'all'))
            if group not in training_layout.MOB_GROUPS:
                raise ValueError('Неизвестная категория противников')
            rows = [(t, name) for t, name in mob_catalogue().items()
                    if (group == 'all' or training_layout.mob_group(mobs.TYPES[str(t)]) == group)
                    and (not level or mobs.stats(t).level == level) and query in name.casefold()]
        else:
            rows = [(t, entry[2]) for t, entry in item_catalogue().items()
                    if (entry[0] == cat or cat == 'weapon' and entry[0] in ('special_weapon','experimental_weapon'))
                    and (not level or entry[1] == level)
                    and query in entry[2].casefold()
                    and (line == 'all' or (t in contraband() if line == 'C' else item_line(t) == line))
                    and (cat != 'weapon' or upgrade == 'all' or bool(craft.mod_of(t)) == (upgrade == 'modified'))
                    and (cat != 'weapon' or wclass < 0 or
                         (6 if items.root_of(t) == items.COLD_ARM else items.params_of(t).get('weapon_type')) == wclass)]
        rows.sort(key=lambda row: (mobs.stats(row[0]).level, row[1], row[0]) if cat == 'mob' else (row[1], row[0]))
        total = len(rows)
        rows = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        groups = [','.join(str(member) for member in sets.SETS[t]['members'].values())
                  if cat == 'set' else '' for t, _ in rows]
        icons = [next(iter(sets.SETS[t]['members'].values())) if cat == 'set' else t for t, _ in rows]
        self.clone.send('tg', op='catalogue', ids=[t for t, _ in rows], groups=groups, icons=icons,
                        context=Str(self.context), request_id=integer(p.get('request_id', 0), 0, 2**31-1),
                        levels=[mobs.stats(t).level if cat == 'mob' else item_catalogue()[t][1] if t in item_catalogue() else sets.SETS[t]['level'] for t, _ in rows],
                        group_slots=[','.join(str(inventory.HEAD + items.params_of(m)['slot_type']) for m in sets.SETS[t]['members'].values()) if cat == 'set' else '' for t, _ in rows],
                        labels=[name for _, name in rows], total=total, page=page,
                        slots=[0 if cat in ('mob', 'set') else inventory.PRIMARY if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)
                               else inventory.HEAD + items.params_of(t)['slot_type']
                               if items.root_of(t) == items.WEAR and cat != 'mob' else 0 for t, _ in rows])

    def start(self, mode):
        self.hide_corpse()
        enemy_cell = movement.get(self.room).free_cell(ENEMY_SPAWNS[self.location][self.spawn_point])
        if self.applied_profile != self.profile:
            self.apply(self.clone, self.profile)
        self.clone.stop_walk()
        self.clone.combat.cancel_timers()
        self.clone.combat.dead = False
        if mode == 'fighter':
            if self.enemy_cache is None:
                self.enemy_cache = self.make_clone('Противник')
            self.enemy = self.enemy_cache
            self.enemy.combat = TrainingFighter(self.enemy)
            self.enemy.send = lambda *args, **kwargs: None
            self.enemy.loc, self.enemy.room, self.enemy.pos = self.clone.loc, self.room, enemy_cell
            self.apply(self.enemy, self.opponent)
            self.room.enter(self.enemy)
            self.enemy.combat.entered()
        else:
            module = __import__(self.owner.__class__.__module__)
            eid = module.ROOMS.ids.npc()
            self.mob_eid = eid
            self.room.npcs[eid] = rooms.NPC(enemy_cell, self.mob_type, world.MOB)
            mob = mobs.Mob(eid, self.mob_type, enemy_cell)
            mob.training_ground = self
            mob.stats = copy.copy(mob.stats)
            training_mobs.configure(mob, self)
            mob.ap = mob.stats.ap_max
            mob.stats.aggro = max(100, mob.stats.aggro)
            mob.stats.hp_max = max(1, round(mob.stats.hp_max*self.mob_health/100))
            mob.stats.sp_max = max(0, round(mob.stats.sp_max*self.mob_health/100))
            mob.hp, mob.sp = mob.stats.hp_max, mob.stats.sp_max
            mob.stats.dmg_min = max(0, round(mob.stats.dmg_min*self.mob_damage/100))
            mob.stats.dmg_max = max(mob.stats.dmg_min, round(mob.stats.dmg_max*self.mob_damage/100))
            if self.stationary:
                mob.stats = copy.copy(mob.stats)
                mob.think = lambda rc, now: None
                mob.stats.can_attack = False
                mob.stats.moves = False
            self.room.combat.mobs[eid] = mob
            self.room.broadcast(('lch', dict(newUser=eid, pos=enemy_cell, rtype=world.MOB)))
        self.clone.inv.trade = None
        self.mode = mode
        self.phase = 'fight'
        self.room.combat.set_ws(True)
        self.shots = self.hits = self.damage = 0
        self.started = time.monotonic()
        if mode == 'mob' and not self.stationary:
            self.room.combat.aggro(mob, self.clone.combat)
        self.state('Противник вызван')

    def enemy_turn(self):
        enemy = self.enemy
        if enemy.combat.acting() or enemy.combat.dead or enemy.live_cell() != enemy.pos:
            return
        vitals = enemy.character().vitals()
        if vitals['hcur'] < vitals['hmax'] / 2 or vitals['scur'] < vitals['smax'] / 2:
            for row in enemy.inv.rows():
                if row['root'] != items.HEAL or items.no_combat(row['type_id']) or items.stimulant_unavailable(row['type_id']):
                    continue
                si = items.params_of(row['type_id']) or {}
                useful = ((vitals['hcur'] < vitals['hmax'] / 2 and si.get('max_h_rest', 0) > 0)
                          or (vitals['scur'] < vitals['smax'] / 2 and si.get('max_st_rest', 0) > 0))
                if useful and enemy.combat.ap >= si.get('heal_cost', 0):
                    enemy.combat.use_heal(dict(obj=inventory.oid_of(row)), inventory.USE_IDLE)
                    return
        gun = enemy.inv.in_slot(inventory.PRIMARY)
        if gun and gun['root'] == items.FIRE_ARM and gun['ammo_count'] == 0:
            # Reuse ordinary reload/ammunition checks, never grant real rounds.
            stack = next((r for r in enemy.inv.rows() if r['root'] == items.AMMO
                          and r['type_id'] in items.params_of(gun['type_id']).get('comp_array', [])), None)
            if stack:
                enemy.inv.use_load(dict(obj=inventory.oid_of(gun), target=inventory.oid_of(stack)))
            return
        target = self.clone.combat
        distance = mobs.hex_distance(enemy.pos, target.cell, self.clone.loc.width)
        if gun and gun['root'] == items.FIRE_ARM:
            params = items.params_of(gun['type_id'])
            reach = params['max_range'][gun['cur_mode']]
            if self.rules.ammo_modifiers:
                reach *= (items.params_of(gun['ammo_type']) or {}).get('range_mod', 1)
        else:
            reach = 1
        in_reach = (distance <= reach if gun and gun['root'] == items.FIRE_ARM
                    else mobs.adjacent(enemy.pos, target.cell, self.clone.loc))
        if not in_reach or combat.shot_wall(self.clone.loc, enemy.pos, target.cell) is not None:
            loc = self.clone.loc
            target_cell = target.cell
            def goal(cell):
                reachable = (0 < mobs.hex_distance(cell, target_cell, loc.width) <= reach
                             if gun and gun['root'] == items.FIRE_ARM
                             else mobs.adjacent(cell, target_cell, loc))
                return reachable and combat.shot_wall(loc, cell, target_cell) is None
            blocked = movement.get(self.room).occupied(exclude=enemy)
            path = mobs.find_path(loc, enemy.pos, goal, blocked, toward=target_cell)
            if path and len(path) > 1:
                # The same server/client walk clock as a player.
                enemy.move_in_location(dict(path=path[:2]))
            return
        enemy.combat.use_fire(dict(obj=inventory.oid_of(gun) if gun else '0',
                                   target='1%08x' % target.eid))

    def hide_corpse(self):
        if self.corpse_timer is not None:
            self.corpse_timer.cancel()
            self.corpse_timer = None
        if self.corpse_id is not None:
            self.room.broadcast(('lch', dict(lostUser=self.corpse_id)))
            self.corpse_id = None

    def target_defeated(self, victim):
        if self.phase != 'fight':
            return
        self.hide_corpse()
        cell = victim.cell
        movement.get(self.room).forget(victim.sess if victim.is_player else victim)
        self.room.broadcast(('actionCancel', dict(id=victim.eid, pos=cell, stop_aim=1)))
        if victim.is_player:
            victim.sess.pos = cell
            victim.dead = True
            victim.cancel_timers()
            victim.end_duels()
            self.room.players.pop(victim.sess, None)
            self.enemy = None
        else:
            victim.cell = cell
            victim.alive = False
            victim.target = None
            victim.walk = None
            if victim.aim is not None:
                victim.aim.cancel()
                victim.aim = None
            self.room.combat.mobs.pop(victim.eid, None)
            self.room.npcs.pop(victim.eid, None)
            self.mob_eid = None
        self.room.broadcast(('lch', dict(dead=victim.eid)))
        self.corpse_id = victim.eid
        self.corpse_timer = asyncio.get_running_loop().call_later(2, self.hide_corpse)
        self.phase = 'ready'
        self.room.combat.sync_ws()
        seconds = max(0.001, time.monotonic()-self.started)
        summary = 'Цель поражена. Попадания: %d; урон HP: %d; время: %.1f с. Можно вызвать следующую цель у компьютера.' % (self.hits,self.damage,seconds)
        self.state('Цель поражена. Вы остаётесь на полигоне.')
        self.clone.send('tg', op='result', message=Str(summary))

    def finish(self, result, force=False):
        if (not force and self.phase not in ('fight', 'loading')) or self.pending is not None:
            return
        self.phase = 'finishing'
        self.pending = asyncio.get_running_loop().call_soon(self.reset, result)

    def reset(self, result):
        self.pending = None
        if self.closed:
            return
        self.hide_corpse()
        seconds = max(0.001, time.monotonic() - self.started) if self.started else 0.001
        summary = '%s. Снаряды: %d; попадания (включая дробь): %d; урон HP: %d; время боя: %.1f с; DPS по HP: %.1f' % (
            result, self.shots, self.hits, self.damage, seconds, self.damage / seconds)
        summary += '\n' + self.rules.description()
        self.clone.combat.cancel_timers()
        self.clone.combat.end_duels()
        self.clear_target()
        self.phase = 'ready'
        self.room.combat.sync_ws()
        revive = self.clone.combat.dead
        self.clone.combat.dead = False
        if revive:
            self.clone.training_effects.close()
            self.apply(self.clone, self.profile)
            self.clone.training_effects.send_list()
        self.context = 'computer'
        self.clone.pos = training_party.free_spawn(self.room, control_cell(self.location), excluded=self.clone)
        self.room.broadcast(('actionCancel', dict(id=self.clone.pid, pos=self.clone.pos, stop_aim=1, release=1)))
        self.room.broadcast(('breakMv', dict(id=self.clone.pid, pos=self.clone.pos)))
        self.clone.push_stats()
        self.clone.push_vitals()
        self.clone.combat.ap = self.clone.char.ap_ceiling
        self.clone.combat.c_ap()
        self.state('Вы у компьютера')
        self.clone.send('tg', op='result', message=Str(summary))

    def clear_target(self):
        if self.mob_eid is not None:
            mob = self.room.combat.mobs.pop(self.mob_eid, None)
            if mob is not None:
                movement.get(self.room).forget(mob)
                if mob.aim:
                    mob.aim.cancel()
            self.room.npcs.pop(self.mob_eid, None)
            self.room.broadcast(('lch', dict(lostUser=self.mob_eid)))
            self.mob_eid = None
        if self.enemy:
            self.enemy.training_effects.close()
            self.enemy.combat.cancel_timers()
            self.enemy.combat.end_duels()
            self.room.leave(self.enemy)
            for row in self.enemy.inv.rows():
                self.store.delete_item(row['uniq'])
            self.enemy = None

    def exit(self, notify=True, suspend=False):
        if self.closed:
            return
        was_inside = self.inside
        try:
            self.remember_outfit()
            self.inside = bool(suspend)
            self.save_settings()
        except Exception:
            self.inside = was_inside
            if not suspend:
                raise  # Do not report an explicit exit before presence commits.
            log.exception('Could not checkpoint training for character %s', self.owner.char_id)
        self.closed = True
        try:
            self.hide_corpse()
            if self.timer:
                self.timer.cancel()
            if self.pending:
                self.pending.cancel()
            self.clone.training_effects.close()
            if self.enemy_cache is not None:
                self.enemy_cache.training_effects.close()
            self.clone.combat.cancel_timers()
            self.clone.combat.end_duels()
            self.clear_target()
            self.room.leave(self.clone)
            self.room.grounds.pop(self.token, None)
            rc = self.room.combat
            if self.room.grounds:
                self.room.ground = next(iter(self.room.grounds.values()))
                rc.store = self.room.ground.store
                rc.sync_ws()
            else:
                if rc.timer:
                    rc.timer.cancel()
                self.room.npcs.clear()
                rc.mobs.clear()
        finally:
            self.owner.training_ground = None
            ACTIVE.discard(self)
            self.store.close()
        if notify and not self.owner.closed:
            self.owner.send('tg', op='exit', active=0)
            self.owner.training_return = True
            self.owner.enter_location()
            training_party.refresh(self)


def check_entry(owner, p):
    participants = training_party.entrants(owner)
    if len(ACTIVE) + len(participants) > MAX_SESSIONS:
        raise ValueError('Учебный центр занят. Попробуйте позже')
    if not ENABLED:
        raise ValueError('Учебный центр пока недоступен')
    npc = owner.room.npc(integer(p.get('npc', 0), 1, 999999)) if owner.room else None
    if owner.loc.id != MARKET or npc is None or npc.type_id != BERT \
            or owner.combat.dead or owner.combat.in_combat() or owner.barter.deal is not None \
            or not progression.within_reach(owner.live_cell(), npc.cell, owner.loc.width, owner.loc.height):
        raise ValueError('Подойдите к Берту вне боя')


def enter_from_quest(owner):
    npc_id = next((eid for eid, npc in owner.room.npcs.items() if npc.type_id == BERT), 0) if owner.room else 0
    enter(owner, dict(npc=npc_id))


def enter(owner, p):
    check_entry(owner, p)
    participants = training_party.entrants(owner)
    prepared = []
    activated = set()
    try:
        for participant in participants:
            ground = Ground(participant)
            if prepared:
                training_party.join(ground, prepared[0].room)
            prepared.append(ground)
        for ground in prepared:
            activated.add(ground)
            activate(ground)
        training_party.refresh(prepared[0])
    except Exception:
        for ground in reversed(prepared):
            try:
                ground.exit(notify=ground in activated)
            except Exception:
                ground.exit(notify=False, suspend=True)
        raise



def activate(ground):
    participant = ground.owner
    # Commit membership before removing the real avatar or sending clone data.
    ground.inside = True
    ground.save_settings()
    participant.windows_gone()
    participant.cancel_passage()
    participant.cancel_way()
    participant.cancel_travel()
    participant.pos = participant.live_cell()
    participant.leave_room()
    participant.training_return_ap = participant.combat.ap
    participant.training_ground = ground
    ACTIVE.add(ground)
    ground.touch()
    participant.send('tg', op='types', copies=list(training_items.SOURCES), sources=list(training_items.SOURCES.values()),
                     lines=[item_line(source) for source in training_items.SOURCES.values()],
                     costs=[training_items.REFERENCE_PRICES[source][0] for source in training_items.SOURCES.values()],
                     gold_costs=[training_items.REFERENCE_PRICES[source][1] for source in training_items.SOURCES.values()],
                     price_packs=[training_items.REFERENCE_PRICES[source][2] for source in training_items.SOURCES.values()],
                     labels=[item_catalogue()[source][2] for source in training_items.SOURCES.values()])
    ground.state()
    ground.clone.enter_location()


def resume(owner):
    """Restore membership, never a real character or a caller-selected room."""
    current = getattr(owner, 'training_ground', None)
    if current is not None:
        current.clone.enter_location()
        return True
    saved = owner.inv.store.training_profile(owner.char_id)
    if not isinstance(saved, dict) or saved.get('inside') is not True:
        return False
    if not ENABLED or len(ACTIVE) >= MAX_SESSIONS:
        owner.say('Полигон временно недоступен. Его настройки сохранены; повторите вход в игру позже.')
        return False
    ground = None
    try:
        ground = Ground(owner)
        visit = saved.get('room')
        if isinstance(visit, str) and re.fullmatch('[0-9a-f]{32}', visit):
            shared = next((peer.room for peer in ACTIVE
                           if not peer.closed and peer.room.key[1] == visit), None)
            if shared is not None:
                training_party.join(ground, shared)
                ground.clone.pos = training_party.free_spawn(
                    shared, control_cell(ground.location), excluded=ground.clone)
            else:
                ground.room.key = (ground.location, visit)
        activate(ground)
        training_party.refresh(ground)
        return True
    except Exception:
        log.exception('Could not resume training for character %s', owner.char_id)
        if ground is not None:
            ground.exit(notify=False, suspend=True)
        owner.send('tg', op='exit', active=0)
        owner.say('Не удалось загрузить полигон. Основной персонаж сохранён; повторите вход позже.')
        return False

def preload():
    training_rules.current()
    training_effects.definitions()
    training_items.prepare(item_catalogue())
    mob_catalogue()
    for location in LOCATIONS:
        geometry(location)


def handle(owner, cmd, p):
    ground = getattr(owner, 'training_ground', None)
    if cmd != 'tg' and ground is None:
        return False
    acks = getattr(ground.clone, 'training_acks', 0) if ground else 0
    try:
        if cmd == 'tg':
            if ground:
                ground.request(p)
            elif p.get('op') == 'enter':
                raise ValueError('Вход на полигон — через задание у Берта')
            else:
                raise ValueError('Нет активной тренировки')
        elif cmd == 'logout':
            owner.close(force=True)
        else:
            ground.touch()
            ground.clone.handle_training(cmd, p)
    except (ValueError, TypeError, KeyError) as exc:
        target = ground.clone if ground else owner
        module = __import__(owner.__class__.__module__)
        if ground and cmd != 'tg' and module.expects_ack(cmd, p) and getattr(target, 'training_acks', 0) == acks:
            target.send('cmdAck', res=inventory.RES_REFUSED)
        target.send('tg', op='error', message=Str(str(exc)))
    except Exception:
        log.exception('training-ground command failed: %s', cmd)
        if ground:
            ground.exit()
        owner.send('tg', op='error', message=Str('Тренировка завершена из-за ошибки'))
    return True
