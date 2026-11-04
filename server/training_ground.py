"""Private shooting-range contexts. No training identity enters the real store."""
import asyncio
import copy
from functools import lru_cache
import logging
import itertools
import os
import secrets
import time

import accounts
import training_items
import training_rules
import combat
import craft
import npcs
import sets
import inventory
import items
import mobs
import names
import quests
import mail
import progression
import rooms
import storage
import world
from protocol import Str

log = logging.getLogger('lava')
BERT = 2088
ENTRY_QUEST = 9301
MARKET = 35
RANGE = 732
TERMINAL = 1263
TERMINAL_CELL = 936
MAX_SESSIONS = 16
MAX_ITEMS = 32
PAGE_SIZE = 10
IDLE_SECONDS = 1800
ACTIVE = set()
SERIAL_BASE = 1 << 40
SERIALS = itertools.count(SERIAL_BASE, 1 << 20)
ENABLED = os.environ.get('LAVA_TRAINING_GROUND', '0') == '1'
READ_COMMANDS = frozenset(('getInfo', 'rp_get_info', 'ss_get_si', 'ss_get_di',
                           'ss_get', 'ss_get_s_si', 'e_get_si', 'e_get_di', 'q_si', 'q_di', 'q_status', 'ah_search'))
PLAY_COMMANDS = frozenset(('moveTo', 'ss_move', 'ss_use'))


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
def item_catalogue():
    eligible = set(sets.ITEMS) | set(items.PERSONAL_QUEST_REWARDS)
    craft._read()
    for trader in set(items.stock_table()) | set(npcs.STOCK) | set(craft._STOCK):
        eligible.update(items.stock_for(trader))
    mod_labels = {}
    for rec in craft.rows().values():
        if rec.get('family') == 'upgrade' and rec.get('line') in ('A', 'G'):
            eligible.update((int(rec['gun']), int(rec['mod'])))
            mod_labels[int(rec['mod'])] = names.text(items.STRING_ID_OFFSET + int(rec['blueprint'])).partition('$')[0]
    out = {}
    for type_id in eligible:
        if training_items.is_copy(type_id):
            continue
        if type_id not in items.catalogue():
            continue
        root, name = items.catalogue()[type_id]
        if root not in (items.FIRE_ARM, items.COLD_ARM, items.WEAR, items.HEAL, items.AMMO):
            continue
        if (items.premium(type_id) or items.out_of_game(type_id)
                or items.acquisition_blocked(type_id) or type_id in items.ADMIN_OVERRIDES):
            continue
        p = items.params_of(type_id) or {}
        if not p or p.get('quest') or (not (p.get('cost') or p.get('g_cost')) and type_id not in items.PERSONAL_QUEST_REWARDS):
            continue
        level = inventory.item_level(type_id) if root in items.BREAKABLE_ROOTS else 0
        if level > 17:
            continue
        category = {items.FIRE_ARM: 'weapon', items.COLD_ARM: 'weapon',
                    items.WEAR: 'armour', items.HEAL: 'medicine', items.AMMO: 'ammo'}[root]
        if root == items.WEAR and (p.get('slot_type', -1) + inventory.HEAD) == inventory.BELT:
            category = 'pouch'
        label = names.text(items.STRING_ID_OFFSET + type_id).partition('$')[0]
        if root in items.BREAKABLE_ROOTS:
            label += ' · %d ур.' % level
        if type_id in contraband():
            label += ' · Контрабанда'
        if type_id in mod_labels:
            label += ' · ' + mod_labels[type_id]
        out[type_id] = (category, level, label)
    return out


@lru_cache(maxsize=1)
def mob_catalogue():
    known = world.mob_types()
    return {int(k): '%s · %d ур.' % (names.text(int(k)), int(v.get('level', 0))) for k, v in mobs.TYPES.items()
            if int(k) in known and known[int(k)][0] == world.MOB
            and v.get('role') in ('mob', 'animal', 'boss')
            and 0 <= int(v.get('level', 0)) <= 17 and not world.retired_creature(int(k))}


@lru_cache(maxsize=1)
def geometry():
    loc = world.location(RANGE)
    free = set(range(loc.width * loc.height)) - loc.obstacles
    parts = []
    while free:
        queue = [free.pop()]
        part = set(queue)
        for cell in queue:
            for c in progression.hex_neighbours(cell, loc.width, loc.height):
                if c in free:
                    free.remove(c)
                    part.add(c)
                    queue.append(c)
        parts.append(part)
    safe = next(p for p in parts if TERMINAL_CELL in p)
    arena = max((p for p in parts if p is not safe), key=len)
    start = min(arena, key=lambda c: mobs.hex_distance(c, TERMINAL_CELL, loc.width))
    return frozenset(safe), frozenset(arena), start


def preset(level=12):
    return dict(skills=[level, level, level, 0, 0], specs=[-1] * progression.SPECS,
                gear={})


def validate_profile(raw):
    skills = [integer(x, 0, 17) for x in raw['skills']]
    specs = [integer(x, -1, progression.SPEC_MAX) for x in raw['specs']]
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
        if root in (items.FIRE_ARM, items.COLD_ARM):
            slot = inventory.PRIMARY
        elif root == items.WEAR:
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
    ch = character(result)
    fields = []
    for source, n in gear.items():
        t = training_items.copy_type(source)
        f = inventory.new_fields(t, n)
        f['type_id'] = t
        f['slot'] = inventory.PRIMARY if f['root'] in (items.FIRE_ARM, items.COLD_ARM) else (
            inventory.HEAD + items.params_of(t)['slot_type'] if f['root'] == items.WEAR else inventory.BAG)
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
    @property
    def armor(self):
        return super().armor * training_rules.current().armour

    def attr(self, i):
        return max(0, round(super().attr(i) * training_rules.current().attributes[i]))

    @property
    def hp_max(self):
        return max(1, round(super().hp_max * training_rules.current().health))

    @property
    def sp_max(self):
        return max(1, round(super().sp_max * training_rules.current().stamina))

    def gain_xp(self, *args, **kwargs):
        return {'skills': set(), 'specs': set(), 'attribs': set()}


def character(profile):
    ch = TrainingCharacter()
    for i, level in enumerate(profile['skills']):
        ch.set_skill(i, level)
    ch.recalc()
    for i, level in enumerate(profile['specs']):
        ch.set_spec(i, level)
    return ch


class TrainingFighter(combat.Fighter):
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
        self.sess.ground.finish('Поражение' if self.sess is self.sess.ground.clone else 'Победа')


class TrainingCombat(combat.RoomCombat):
    def keep_hours(self):
        pass

    def recall_kills(self):
        pass

    def kill(self, victim, killer, **kwargs):
        self.room.ground.finish('Поражение' if victim is self.room.ground.clone.combat else 'Победа')

    def _step(self):
        if self.room.ground.phase == 'loading':
            return  # No attacks or AP charges before the client accepts the arena.
        super()._step()
        ground = self.room.ground
        if ground.phase == 'fight' and ground.enemy is not None and not ground.stationary:
            ground.enemy_turn()


class TrainingRoom(rooms.Room):
    def broadcast(self, event, exclude=None):
        if isinstance(event, tuple):
            cmd, p = event
            if self.ground.phase == 'fight':
                if cmd == 'faShot' and p.get('status') == 1 and p.get('id') == self.ground.clone.pid:
                    self.ground.shots += 1
                if cmd in ('faHit', 'caHit') and p.get('target') != self.ground.clone.pid:
                    self.ground.hits += 1
                    self.ground.damage += p.get('dmg', 0)
        super().broadcast(event, exclude)


def clone_class(base):
    class Clone(base):
        """Only a whitelist of base handlers is reachable; persistence stays local."""
        @property
        def pid(self):
            return rooms.player_id(1000000000 + self.char_id)

        def char_for_entity(self, entity_id):
            enemy = self.ground.enemy
            return enemy.char_id if enemy and entity_id == enemy.pid else None

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

        def cmd_q_di(self, p):
            command, fields = quests.stub_di(int(p.get('q_id', 0)))
            self.send(command, **fields)

        def cmd_q_status(self, p):
            t = int(p.get('q_type', 0))
            q = quests.get(t)
            self.send('q_status', type=t, status=0,
                      name=q.string_id(quests.NAME) if q else 0, q_type=q.q_type if q else 0)

        def cmd_ah_search(self, p):
            self.send('ah_sresult', page=0, count=0, next=0)

        def count_bag(self):
            pass

        def arm_passage(self, *args):
            pass

        def take_passage(self, *args):
            pass

        def party(self):
            return None

        def push_stats(self, **groups):
            self.send('rp_info', **self.character().rp_info(**groups))

        def enter_location(self):
            self.send('lcall', id=RANGE, ws=int(self.ground.phase in ('fight', 'loading')), ie=0,
                      g_id=1 << 26)

        def cmd_lenter(self, p):
            ground = self.ground
            if ground.phase == 'loading':
                ground.phase = 'fight'
                ground.room.ws = True
                ground.started = time.monotonic()
                if ground.enemy is not None:
                    ground.enemy.combat.entered()
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

        def cmd_getInfo(self, p):
            target = int(p.get('id', 0))
            if not target:
                self.send_player_info()
                self.push_vitals()
            elif self.ground.enemy and target == self.ground.enemy.pid:
                enemy = self.ground.enemy
                fields = rooms.player_info(enemy)
                fields.update(name=Str('Тренировочный боец'), ally=0)
                self.send('userInfo_Player', **fields)
                self.send('usrUp', **rooms.player_health(enemy))
            else:
                self.send_npc_info(target)

        def send_npc_info(self, eid):
            npc = self.room.npc(eid)
            if npc is None:
                return
            if npc.type_id != TERMINAL:
                return super().send_npc_info(eid)
            self.send(world.USERINFO[world.COMMONER], id=eid, name=TERMINAL, sex=0, res=TERMINAL,
                      ail=0, ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=[], take_quests=[], m_hello=[], can_set_home=0,
                      can_banking=0, can_trophy=0, can_repair=0, can_trade=0,
                      tg_terminal=1)

        def cmd_ss_get_di(self, p):
            parsed = inventory.parse_oid(p.get('obj'))
            if parsed and parsed[0] >= self.ground.serial_base:
                return self.inv.ss_get_di(p)
            if parsed and self.ground.mob_eid is not None and parsed[0] == mobs.VIRTUAL_BASE + self.ground.mob_eid:
                return self.combat.ss_get_di(p)
            return self.inv.ss_get_di(p)

        def cmd_ss_get(self, p):
            if not self.combat.ss_get(p):
                self.inv.ss_get(p)

        def handle_training(self, cmd, p):
            if cmd == 'lcall':
                self.enter_location()
                return
            if cmd == 'lenter':
                self.cmd_lenter(p)
                return
            if cmd == 'userMsg':
                if str(p.get('entry', '')).lstrip().startswith('/') and not ('group' not in p and p.get('to')):
                    self.send('cmdAck', res=0)
                    self.answer('Игровые команды недоступны в тренировке. Используйте терминал или кнопку выхода.')
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
                self.send('q_list', q_id=[], q_types=[])
                return
            if cmd == 'ss_move' and (int(p.get('to', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,) or int(p.get('from', inventory.BAG)) not in inventory.WEAR_SLOTS + inventory.HAND_SLOTS + (inventory.BAG,)):
                self.send('cmdAck', res=inventory.RES_REFUSED)
                return
            if cmd in READ_COMMANDS or (cmd in PLAY_COMMANDS and self.ground.phase == 'fight'):
                if cmd == 'getInfo' and int(p.get('id', 0)) not in (0, self.ground.terminal_id) \
                        and not (self.ground.enemy and int(p.get('id', 0)) == self.ground.enemy.pid) \
                        and int(p.get('id', 0)) not in self.room.combat.mobs:
                    return
                if cmd == 'moveTo':
                    path = p.get('path', [])
                    if not isinstance(path, list) or len(path) > self.loc.width * self.loc.height \
                            or any(c not in geometry()[1] for c in path):
                        self.send('cmdAck', res=inventory.RES_REFUSED)
                        return
                fn = getattr(self, 'cmd_' + cmd)
                fn(p)
                if cmd in ('ss_move', 'ss_use'):
                    self.inv.refresh_gear()
                return
            if cmd == 'moveTo' and self.ground.phase == 'ready':
                path = p.get('path', [])
                if isinstance(path, list) and len(path) <= 2048 and all(c in geometry()[0] for c in path):
                    self.cmd_moveTo(p)
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
        self.profile = preset(max(1, min(17, owner.character().level)))
        source = owner.character()
        self.profile['skills'] = [max(0, min(17, r[0])) for r in source.skill]
        if not max(self.profile['skills']):
            self.profile['skills'][progression.SHOOTING] = 1
        self.profile['specs'] = [max(-1, min(progression.SPEC_MAX, r[0])) for r in source.spec]
        for row in owner.inv.rows():
            t = row['type_id']
            if t not in item_catalogue() or row['slot'] == inventory.SECONDARY:
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
        self.mob_type = next(iter(mob_catalogue()))
        self.enemy = None
        self.enemy_cache = None
        self.stationary = False
        self.distance = 12
        self.closed = False
        self.pending = None
        self.last_request = 0.0
        self.last_activity = time.monotonic()
        self.timer = None
        self.store = accounts.Store.temporary()
        self.serial_base = next(SERIALS)
        self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('items',?)", (self.serial_base,))
        self.store.db.commit()
        self.shots = self.hits = self.damage = 0
        self.started = 0.0
        self.clone = None
        try:
            self.Clone = clone_class(owner.__class__)
            self.clone = self.make_clone('Тренировка', owner.active)
            loc = copy.copy(world.location(RANGE))
            loc.spawns = []
            loc.pvp = 1
            self.room = TrainingRoom(loc, rooms.IdAllocator(), {}, key=(RANGE, self.token))
            self.room.npcs.clear()
            self.room.ground = self
            module = __import__(owner.__class__.__module__)
            self.terminal_id = module.ROOMS.ids.npc()
            self.mob_eid = None
            self.room.npcs[self.terminal_id] = rooms.NPC(TERMINAL_CELL, TERMINAL, world.COMMONER)
            self.room.combat = TrainingCombat(self.room, self.store)
            self.clone.room = self.room
            self.clone.loc = loc
            self.clone.pos = world.location(RANGE).entry_cell()
            self.apply(self.clone, self.profile)
        except Exception:
            self.store.close()
            raise

    def make_clone(self, label, source=None):
        # No account registration/password hashing, and no persistent login slot.
        aid = self.store.db.execute("INSERT INTO accounts(login, hash, created) VALUES(?, ?, ?)",
                                    (secrets.token_hex(8), secrets.token_hex(16), int(time.time()))).lastrowid
        self.store.db.commit()
        source = source or self.owner.active
        cid, _ = self.store.create_character(aid, label, source['sex'], source['res'])
        clone = self.Clone(self.owner.writer, self.owner.peer)
        clone.ground = self
        clone.char_id = cid
        clone.active = dict(self.store.character(cid))
        if label == 'Тренировка':
            clone.active['name'] = self.owner.nick
        clone.char = progression.Character.load(self.store, cid)
        clone.inv = inventory.Inventory(clone, self.store)
        clone.combat = TrainingFighter(clone)
        clone.transport = None
        return clone

    def apply(self, clone, profile):
        ch = character(profile)
        ch.char_id, ch.name = clone.char_id, clone.active['name']
        clone.char = ch
        if self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq'] > self.serial_base + (1 << 20) - 2048:
            raise ValueError('Лимит тренировки исчерпан; войдите в центр заново')
        for row in clone.inv.rows():
            self.store.delete_item(row['uniq'])
        for t, n in profile['gear'].items():
            t = training_items.copy_type(t)
            root = items.root_of(t)
            slot = inventory.PRIMARY if root in (items.FIRE_ARM, items.COLD_ARM) else (
                inventory.HEAD + items.params_of(t)['slot_type'] if root == items.WEAR else inventory.BAG)
            if root == items.HEAL:
                for _ in range(n):
                    clone.inv.create(t)
            else:
                clone.inv.create(t, n, slot=slot)
        clone.inv.refresh_gear(push=False)
        ch.hp, ch.sp = ch.hp_max, ch.sp_max
        ch.save(self.store)
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
        return {prefix + 'ids': ids,
                prefix + 'labels': [item_catalogue()[t][2] + ' (тестовая версия)' for t in ids],
                prefix + 'slots': [inventory.PRIMARY if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)
                                    else inventory.HEAD + items.params_of(t)['slot_type']
                                    if items.root_of(t) == items.WEAR else 0 for t in ids]}

    def state(self, message=''):
        c = self.clone
        live = [inventory.oid_of(row) for row in self.store.items_of(c.char_id)]
        if self.enemy:
            live.extend(inventory.oid_of(row) for row in self.enemy.inv.rows())
        virtual_uid = 0
        if self.mob_eid is not None and self.mob_eid in self.room.combat.mobs:
            mob = self.room.combat.mobs[self.mob_eid]
            if mob.weapon_oid():
                live.append(mob.weapon_oid())
                virtual_uid = mobs.VIRTUAL_BASE + self.mob_eid
        c.send('tg', op='state', token=Str(self.token), active=1, phase=Str(self.phase),
               live_oids=live, virtual_uid=virtual_uid, message=Str(message), level=c.char.level, hp=c.char.hp_max,
               sp=c.char.sp_max, ap=c.char.ap_ceiling,
               rules=Str(training_rules.current().description()), regen=progression.AP_REGEN, owner=Str(self.owner.nick), loaded=int(c in self.room.players), spec_max=progression.SPEC_MAX,
               **self.equipment_meta(self.profile, 'gear_'),
               **self.equipment_meta(self.opponent, 'enemy_'),
               skills=self.profile['skills'], specs=self.profile['specs'],
               gear=Str(','.join('%d:%d' % pair for pair in self.profile['gear'].items())),
               enemy_skills=self.opponent['skills'], enemy_specs=self.opponent['specs'],
               enemy_gear=Str(','.join('%d:%d' % pair for pair in self.opponent['gear'].items())))

    def request(self, p):
        op = str(p.get('op', ''))
        if p.get('token') != self.token:
            raise ValueError('Окно тренировки устарело')
        if op == 'exit':
            self.exit()
            return
        now = time.monotonic()
        if now - self.last_request < 0.08:
            return
        self.last_request = now
        self.touch()
        if op == 'abort':
            self.finish('Бой прерван')
            return
        if self.phase != 'ready':
            raise ValueError('Сначала завершите бой')
        if op not in ('open',) and not progression.within_reach(
                self.clone.live_cell(), TERMINAL_CELL, self.clone.loc.width, self.clone.loc.height):
            raise ValueError('Подойдите к компьютеру')
        if op == 'open':
            if not progression.within_reach(self.clone.live_cell(), TERMINAL_CELL,
                                            self.clone.loc.width, self.clone.loc.height):
                raise ValueError('Подойдите к компьютеру')
            self.state()
            self.clone.send('tg', op='open', mob=self.mob_type)
        elif op == 'catalogue':
            self.catalogue(p)
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
            profile = validate_profile(raw)
            if who == 'player':
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
            self.state('Пресет применён')
        elif op == 'start':
            self.distance = integer(p.get('distance', 12), 1, 30)
            self.stationary = integer(p.get('stationary', 0), 0, 1) == 1
            mode = str(p.get('mode', 'mob'))
            if mode not in ('mob', 'fighter'):
                raise ValueError('Неизвестный противник')
            mob = integer(p.get('mob', self.mob_type), 1, 100000)
            if mode == 'mob' and mob not in mob_catalogue():
                raise ValueError('Моб недоступен')
            self.mob_type = mob
            self.start(mode)

    def catalogue(self, p):
        cat = str(p.get('category', 'weapon'))
        page = integer(p.get('page', 0), 0, 10000)
        level = integer(p.get('level', 0), 0, 17)
        query = str(p.get('query', '')).strip().casefold()[:48]
        wclass = integer(p.get('wclass', -1), -1, 6)
        line = str(p.get('line', 'all'))
        if line not in ('all', 'A', 'G', 'C'):
            raise ValueError('Неизвестная версия предмета')
        if cat == 'set':
            rows = [(t, '%s · %d ур. (%s) (тестовая версия)' % (v['name'], v['level'], v['variant']))
                    for t, v in sets.SETS.items() if v['variant'] in ('A', 'G')
                    and (line == 'all' or line == v['variant'])
                    and (not level or v['level'] == level) and query in v['name'].casefold()
                    and all(member in item_catalogue() for member in v['members'].values())]
        elif cat == 'mob':
            rows = [(t, name) for t, name in mob_catalogue().items()
                    if (not level or mobs.stats(t).level == level) and query in name.casefold()]
        else:
            rows = [(t, entry[2] + ' (тестовая версия)') for t, entry in item_catalogue().items()
                    if entry[0] == cat and (not level or entry[1] == level)
                    and query in entry[2].casefold()
                    and (line == 'all' or ('C' if t in contraband() else 'G' if combat.gold_item(t) else 'A') == line)
                    and (cat != 'weapon' or wclass < 0 or
                         (6 if items.root_of(t) == items.COLD_ARM else items.params_of(t).get('weapon_type')) == wclass)]
        rows.sort(key=lambda r: (r[1], r[0]))
        total = len(rows)
        rows = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        groups = [','.join(str(member) for member in sets.SETS[t]['members'].values())
                  if cat == 'set' else '' for t, _ in rows]
        icons = [next(iter(sets.SETS[t]['members'].values())) if cat == 'set' else t for t, _ in rows]
        self.clone.send('tg', op='catalogue', ids=[t for t, _ in rows], groups=groups, icons=icons,
                        group_slots=[','.join(str(inventory.HEAD + items.params_of(m)['slot_type']) for m in sets.SETS[t]['members'].values()) if cat == 'set' else '' for t, _ in rows],
                        labels=[name for _, name in rows], total=total, page=page,
                        slots=[0 if cat in ('mob', 'set') else inventory.PRIMARY if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)
                               else inventory.HEAD + items.params_of(t)['slot_type']
                               if items.root_of(t) == items.WEAR and cat != 'mob' else 0 for t, _ in rows])

    def start(self, mode):
        start = geometry()[2]
        candidates = [c for c in geometry()[1]
                      if mobs.hex_distance(c, start, self.clone.loc.width) == self.distance
                      and combat.shot_wall(self.clone.loc, start, c) is None]
        if not candidates:
            raise ValueError('Эта дистанция недоступна на площадке')
        enemy_cell = candidates[len(candidates) // 2]
        self.apply(self.clone, self.profile)
        self.clone.combat.cancel_timers()
        self.clone.combat.dead = False
        self.clone.pos = start
        if mode == 'fighter':
            if self.enemy_cache is None:
                self.enemy_cache = self.make_clone('Противник')
            self.enemy = self.enemy_cache
            self.enemy.combat = TrainingFighter(self.enemy)
            self.enemy.send = lambda *args, **kwargs: None
            self.enemy.loc, self.enemy.room, self.enemy.pos = self.clone.loc, self.room, enemy_cell
            self.apply(self.enemy, self.opponent)
            self.room.players[self.enemy] = True
        else:
            module = __import__(self.owner.__class__.__module__)
            eid = module.ROOMS.ids.npc()
            self.mob_eid = eid
            self.room.npcs[eid] = rooms.NPC(enemy_cell, self.mob_type, world.MOB)
            mob = mobs.Mob(eid, self.mob_type, enemy_cell)
            if self.stationary:
                mob.stats = copy.copy(mob.stats)
                mob.think = lambda rc, now: None
                mob.stats.can_attack = False
                mob.stats.moves = False
            self.room.combat.mobs[eid] = mob
        self.phase = 'loading'
        self.room.ws = False
        self.room.players.pop(self.clone, None)
        self.shots = self.hits = self.damage = 0
        self.started = 0.0
        self.state('Подготовка арены')
        self.clone.enter_location()

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
        else:
            reach = 1
        if distance > reach or combat.shot_wall(self.clone.loc, enemy.pos, target.cell) is not None:
            path = mobs.find_path(self.clone.loc, enemy.pos, target.cell)
            if path and len(path) > 1:
                # The same server/client walk clock as a player.
                enemy.move_in_location(dict(path=path[:2]))
            return
        enemy.combat.use_fire(dict(obj=inventory.oid_of(gun) if gun else '0',
                                   target='1%08x' % target.eid))

    def finish(self, result):
        if self.phase not in ('fight', 'loading') or self.pending is not None:
            return
        self.phase = 'finishing'
        self.pending = asyncio.get_running_loop().call_soon(self.reset, result)

    def reset(self, result):
        self.pending = None
        if self.closed:
            return
        seconds = max(0.001, time.monotonic() - self.started) if self.started else 0.001
        summary = '%s. Снаряды: %d; попадания (включая дробь): %d; урон HP: %d; время боя: %.1f с; DPS по HP: %.1f' % (
            result, self.shots, self.hits, self.damage, seconds, self.damage / seconds)
        self.clone.combat.cancel_timers()
        self.clone.combat.end_duels()
        for mob in self.room.combat.mobs.values():
            if mob.aim:
                mob.aim.cancel()
        self.room.combat.mobs.clear()
        self.room.npcs = {self.terminal_id: rooms.NPC(TERMINAL_CELL, TERMINAL, world.COMMONER)}
        if self.enemy:
            self.enemy.combat.cancel_timers()
            self.room.players.pop(self.enemy, None)
            for row in self.enemy.inv.rows():
                self.store.delete_item(row['uniq'])
            self.enemy = None
        self.phase = 'ready'
        self.room.ws = False
        self.clone.combat.dead = False
        self.apply(self.clone, self.profile)
        self.clone.pos = world.location(RANGE).entry_cell()
        self.clone.enter_location()
        self.clone.send('tg', op='result', message=Str(summary))

    def exit(self, notify=True):
        if self.closed:
            return
        self.closed = True
        try:
            if self.timer:
                self.timer.cancel()
            if self.pending:
                self.pending.cancel()
            self.clone.combat.cancel_timers()
            if self.enemy:
                self.enemy.combat.cancel_timers()
            rc = self.room.combat
            if rc.timer:
                rc.timer.cancel()
            for mob in rc.mobs.values():
                if mob.aim:
                    mob.aim.cancel()
            self.room.players.clear()
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


def check_entry(owner, p):
    if len(ACTIVE) >= MAX_SESSIONS:
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
    ground = Ground(owner)
    try:
        owner.windows_gone()
        owner.cancel_passage()
        owner.cancel_way()
        owner.cancel_travel()
        owner.pos = owner.live_cell()
        owner.leave_room()
        owner.training_return_ap = owner.combat.ap
        owner.training_ground = ground
        ACTIVE.add(ground)
        ground.touch()
        owner.send("tg", op="types", copies=list(training_items.SOURCES), sources=list(training_items.SOURCES.values()))
        ground.state()
        ground.clone.enter_location()
    except Exception:
        ground.exit()
        raise


def preload():
    training_rules.current()
    training_items.prepare(item_catalogue())
    mob_catalogue()
    geometry()


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
            ground.exit(notify=False)
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
