"""Training range: session."""
import accounts
from training import checkpoints, config, content, services
import asyncio
import combat
import copy
import inventory
import items
import logging
import mobs
import movement
import progression
import re
import rooms
import secrets
import sets
import storage
import time
import world
from protocol import BigUInt, Str
from training import (
    bot as training_bot,
    commands,
    display as training_display,
    effects as training_effects,
    formulas as training_formulas,
    items as training_items,
    layout as training_layout,
    mobs as training_mobs,
    party as training_party,
    presets as training_presets,
    profiles as training_profiles,
    rules as training_rules,
    settings,
    shop as training_shop,
    supply as training_supply,
)
from training.arena import TrainingCombat, TrainingFighter, TrainingRoom
from training.avatar import clone_class
from training.catalog import contraband, item_catalogue, item_line, mob_catalogue
from training.character import character, preset, profile_slots, validate_profile
from training.geometry import arena_location, control_cell, geometry
from training.runtime import ACTIVE, PLAYER_IDS, SERIALS
from training.settings import (
    BERT,
    DEFAULT_SPAWN,
    ENEMY_SPAWNS,
    IDLE_SECONDS,
    LEGACY_LOCATIONS,
    LOCATIONS,
    MARKET,
    MAX_ITEMS,
    MAX_LEVEL,
    RANGE,
    SPAWN_LABELS,
)
from training.validation import integer


from training.engines import install as install_engines

install_engines()

log = logging.getLogger('lava')


class Ground:
    def __init__(self, owner):
        self.owner = owner
        training_items.prepare(item_catalogue())
        training_items.register_sets_and_strings()
        self.token = secrets.token_hex(16)
        self.phase = 'ready'
        # A new sandbox is independent of the owner's inventory and progress.
        # Saved sandbox profiles below remain persistent across visits.
        self.profile = validate_profile(preset(1))
        self.opponent = preset(max(self.profile['skills']))
        default_mob = content.data()['default_mob']
        self.mob_type = default_mob if default_mob in mob_catalogue() else next(iter(mob_catalogue()))
        self.enemy = None
        self.enemy_cache = None
        self.stationary = False
        self.mob_health = self.mob_damage = 100
        self.enemy_healing, self.heal_below, self.heal_count = False, 50, 5
        self.enemy_heals_left = 0
        self.rules = training_profiles.restore(training_rules.current())
        self.restore_notice = ''
        self.spawn_point = DEFAULT_SPAWN
        self.location = RANGE
        self.mode = 'mob'
        saved = owner.inv.store.training_profile(owner.char_id)
        self.personal_profiles = ()
        self.unavailable_rules = None
        self.unavailable_presets = {}
        try:
            self.restore_settings(saved)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            from training.restoration import archive
            self.personal_profiles = ()
            self.unavailable_rules = None
            self.unavailable_presets = {'checkpoint': archive(saved)}
            self.restore_notice = 'Прежние настройки повреждены или устарели и сохранены отдельно. Настройте клона заново.'
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
        self.supply_sequence = 0
        self.reset_confirmation = None
        self.last_activity = time.monotonic()
        self.timer = None
        self.store = accounts.Store.temporary()
        self.serial_base = next(SERIALS)
        self.shots = self.hits = self.damage = 0
        self.started = 0.0
        self.clone = None
        try:
            self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('items',?)", (self.serial_base,))
            self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('char_quests',?)", (self.serial_base,))
            self.store.db.commit()
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
            self.post_ids = {post.key: self.room.ids.npc() for post in training_layout.POSTS}
            self.terminal_id = self.post_ids['computer']
            self.mob_eid = None
            self.populate_posts()
            self.room.combat = TrainingCombat(self.room, self.store)
            self.clone.room = self.room
            self.clone.loc = loc
            self.clone.pos = control_cell(self.location)
            self.apply(self.clone, self.profile)
        except Exception:
            self.store.close()
            raise

    @property
    def distance(self):
        return round(mobs.hex_distance(self.clone.live_cell(), ENEMY_SPAWNS[self.location][self.spawn_point],
                                       self.clone.loc.width))

    def populate_posts(self):
        self.posts = {self.post_ids[p.key]: p for p in training_layout.posts_for(self.location)
                      if not p.line or training_shop.stock(p)}
        for eid, post in self.posts.items():
            cell = post.cell(self.room.loc.width)
            if cell in self.room.loc.obstacles:
                raise ValueError('Training post is blocked: ' + post.key)
            root = world.COMMONER
            self.room.npcs[eid] = rooms.NPC(cell, post.resource, root)

    def restore_settings(self, saved):
        if saved is None:
            return
        if not isinstance(saved, dict):
            raise ValueError("Saved checkpoint must be an object")
        if not isinstance(saved.get('personal_rules', []), list):
            raise ValueError('Personal profiles must be a list')
        self.personal_profiles = training_profiles.load_personal((saved or {}).get('personal_rules', []))
        self.unavailable_rules = (saved or {}).get('unavailable_rules')
        self.unavailable_presets = copy.deepcopy((saved or {}).get('unavailable_presets', {}))
        if not isinstance(self.unavailable_presets, dict):
            raise ValueError('Unavailable presets must be an object')
        if isinstance(saved, dict):
            saved = copy.deepcopy(saved)
            for who in ('player', 'opponent'):
                raw = saved.get(who, {})
                if isinstance(raw, dict) and any(int(t) not in item_catalogue() for t in raw.get('gear', {})):
                    self.unavailable_presets[who] = raw
                    saved[who] = preset(1)
                    self.restore_notice = 'Часть снаряжения относится к недоступному профилю. Пресет сохранён отдельно.'
            if saved.get('version') != 1:
                raise ValueError('Unsupported training profile')
            rules = training_rules.Rules.parse(saved.get('rules', self.rules.as_dict()))
            if rules.simulator_formulas and not training_formulas.available():
                self.unavailable_rules = rules.as_dict()
                rules = training_rules.Rules.parse(dict(rules.as_dict(), simulator_formulas=False, combat_v2=False))
                self.restore_notice = 'Дополнительный профиль пока недоступен. Его настройки сохранены; включён исходный.'
            if rules.simulator_formulas and any(
                    not training_items.available(int(source), True)
                    for who in ('player', 'opponent') for source in saved[who]['gear']):
                rules = training_rules.Rules.parse(dict(rules.as_dict(), simulator_formulas=False))
                self.restore_notice = ('Пресеты сохранены. В них есть предметы, исключённые из нового симулятора; '
                                       'восстановлен прежний профиль полигона. Замените эти вещи для новых правил.')
            restored_rules = training_profiles.restore(rules)
            if restored_rules != rules:
                self.restore_notice = self.restore_notice + (' Промежуточный профиль удалён. Включён исходный профиль; '
                                       'настройки персонажа и снаряжение сохранены.')
            rules = restored_rules
            player = validate_profile(saved['player'], rules)
            opponent = validate_profile(saved['opponent'], rules)
            location = integer(saved.get('location', RANGE), 1, 65535)
            location = content.data()['map_aliases'].get(str(location), location)
            if location in LEGACY_LOCATIONS:
                location = RANGE
            if location not in LOCATIONS:
                raise ValueError('Unsupported training location')
            mob_type = integer(saved.get('mob', self.mob_type), 1, 100000)
            if mob_type not in mob_catalogue():
                mob_type = self.mob_type
                self.restore_notice = 'Прежняя цель удалена из каталога. Выберите нового противника.'
            spawn_point = integer(saved.get('spawn_point', DEFAULT_SPAWN), 0, len(SPAWN_LABELS) - 1)
            stationary = integer(saved.get('stationary', 0), 0, 1)
            mob_health = integer(saved.get('mob_health', 100), settings.MOB_SCALE_MIN, settings.MOB_SCALE_MAX)
            mob_damage = integer(saved.get('mob_damage', 100), settings.MOB_SCALE_MIN, settings.MOB_SCALE_MAX)
            enemy_healing = integer(saved.get('enemy_healing', 0), 0, 1)
            heal_below = integer(saved.get('heal_below', 50), 10, 90)
            heal_count = integer(saved.get('heal_count', 5), 0, 30)
            mode = saved.get('mode', 'mob')
            if mode not in ('mob', 'fighter'):
                raise ValueError('Unsupported training mode')
            self.enemy_healing, self.heal_below, self.heal_count = bool(enemy_healing), heal_below, heal_count
            self.profile, self.opponent = player, opponent
            self.rules = rules
            self.mob_health, self.mob_damage = mob_health, mob_damage
            self.location, self.mob_type = location, mob_type
            self.spawn_point, self.stationary, self.mode = spawn_point, bool(stationary), mode

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
        self.context = post.key
        self.state()
        self.clone.send('tg', op='open', mob=self.mob_type, context=Str(post.key),
                        title=Str(post.title), category=Str(post.category), wclass=post.weapon_class, supply=int(bool(post.line)),
                        **(training_profiles.payload(self.rules, self.personal_profiles) if post.key == 'computer' else {}))

    def remember_outfit(self):
        """Save an equipped preset, not every spare/free item in the bag."""
        gear = {}
        for row in sorted(self.clone.inv.rows(), key=lambda row: row['slot'] not in inventory.BODY_SLOTS):
            source = training_items.profile_source(row['type_id'])
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

    def configure_player(self, profile, rules=None):
        with checkpoints.mutation(self):
            return self._configure_player(profile, rules)

    def _configure_player(self, profile, rules=None):
        clone = self.clone
        changed = False
        with storage.atomic(self.store.db):
            if rules is not None:
                changed = clone.inv.switch_profile(rules.simulator_formulas)
                self.rules = rules
            ch = character(profile, self.rules)
            ch._training_store = self.store
            ch.char_id, ch.name = clone.char_id, clone.active['name']
            ch.training_effects = clone.training_effects
            rows = clone.inv.rows()
            ch.set_gear(inventory.gear_bonus(rows, ch), inventory.card_repeat(rows))
            ch.hp, ch.sp = ch.hp_max, ch.sp_max
            ch.save(self.store)
        clone.char = ch
        self.profile['skills'], self.profile['specs'] = profile['skills'], profile['specs']
        self.remember_outfit()
        self.save_settings()
        clone.combat.cancel_timers()
        clone.stop_walk()
        return changed

    def fighter_preset(self, set_type):
        selected = sets.SETS.get(set_type)
        simulator = self.rules.simulator_formulas
        if selected is None or not all(t in item_catalogue() and training_items.available(t, simulator)
                                       for t in selected['members'].values()):
            raise ValueError('Комплект недоступен в выбранном профиле')
        level = selected['level']
        entries = training_supply.index(simulator)
        params = lambda t: items.params_of(training_items.copy_type(t, simulator))
        guns = [e for e in entries.values() if e.category == 'weapon' and 0 < e.level <= level
                and e.line == selected['variant'] and not e.upgrade and e.source not in contraband()
                and training_items.available(e.source, simulator) and items.root_of(e.source) == items.FIRE_ARM]
        for gun in sorted(guns, key=lambda e: (-e.level, e.weapon_class, e.source)):
            rounds = [training_items.profile_source(t) for t in params(gun.source).get('comp_array', ())]
            rounds = [t for t in rounds if t in entries and training_items.available(t, simulator)]
            if not rounds:
                continue
            profile = preset(level)
            profile['specs'][:8] = [min(5, max(3, (level + 3) // 4))] * 8
            profile['gear'] = {t: 1 for t in selected['members'].values()}
            profile['gear'][gun.source] = 1
            ammo = min(rounds, key=lambda t: (entries[t].line != selected['variant'],
                                             not items.catalogue()[t][1].endswith('_ST'), t))
            profile['gear'][ammo] = 80
            training_presets.add_pouch(profile, level, selected['variant'], simulator)
            for source in profile['gear']:
                p = params(source)
                required = inventory.unpacked(p.get('need_specs_m'), p.get('need_specs'), progression.SPECS)
                for index in range(progression.SPECS):
                    if (p.get('need_specs_m', 0) or 0) >> index & 1:
                        profile['specs'][index] = max(profile['specs'][index], required[index])
            try:
                return validate_profile(profile, self.rules)
            except ValueError:
                continue
        raise ValueError('Для этого комплекта нет доступного оружия по текущим правилам')

    def save_settings(self, *, player=None, location=None):
        payload = copy.deepcopy(dict(
            version=1, inside=self.inside, room=self.room.key[1],
            unavailable_rules=self.unavailable_rules, unavailable_presets=self.unavailable_presets,
            personal_rules=training_profiles.dump_personal(self.personal_profiles),
            player=self.profile if player is None else player, opponent=self.opponent,
            location=self.location if location is None else location, rules=self.rules.as_dict(),
            mob=self.mob_type, spawn_point=self.spawn_point, stationary=int(self.stationary), mode=self.mode,
            mob_health=self.mob_health, mob_damage=self.mob_damage,
            enemy_healing=int(self.enemy_healing), heal_below=self.heal_below, heal_count=self.heal_count))
        if getattr(self, '_checkpoint_staging', False):
            self._checkpoint_payload = payload
        else:
            self.owner.inv.store.save_training_profile(self.owner.char_id, payload)

    def require_player_reset(self):
        self.require_terminal()
        fighter = self.clone.combat
        if (self.context != 'computer' or self.clone.inv.store is not self.store
                or self.clone.ground is not self or fighter.dead or fighter.duels
                or any(getattr(fighter, name, None) is not None
                       for name in ('aim', 'strike', 'healing', 'reloading'))):
            raise ValueError('Сброс доступен у компьютера после завершения действий и боя')

    def reset_player(self, confirmation):
        self.require_player_reset()
        pending, self.reset_confirmation = self.reset_confirmation, None
        if pending is None or pending[0] != confirmation or time.monotonic() > pending[1]:
            raise ValueError('Подтвердите очистку заново')
        profile = validate_profile(preset(1), self.rules)
        self.replace_player(profile, 'Персонаж очищен: 1-й уровень, без специализаций, вещей и эффектов')

    def replace_player(self, profile, message):
        with checkpoints.mutation(self):
            return self._replace_player(profile, message)

    def _replace_player(self, profile, message):
        """Commit a complete private avatar before publishing any new identities."""
        clone = self.clone
        if clone.ground is not self or clone.inv.store is not self.store:
            raise ValueError('Можно заменить только тренировочного клона')
        seq = self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq']
        if seq > self.serial_base + (1 << 20) - 2048:
            raise ValueError('Лимит тренировки исчерпан; войдите в центр заново')
        fresh = character(profile, self.rules)
        fresh._training_store = self.store
        fresh.char_id, fresh.name = clone.char_id, clone.active['name']
        fresh.training_effects = training_effects.Effects(clone)
        fresh.hp, fresh.sp = fresh.hp_max, fresh.sp_max
        rows = [dict(row) for row in clone.inv.rows()]
        try:
            # Private changes stage first; the outer checkpoint boundary
            # publishes frames only after the durable profile is confirmed.
            with storage.atomic(self.store.db):
                self.store.db.execute('DELETE FROM items WHERE char_id=?', (clone.char_id,))
                slots = profile_slots(profile)
                for source, count in profile['gear'].items():
                    type_id = training_items.copy_type(source, simulator=self.rules.simulator_formulas)
                    if items.root_of(type_id) == items.HEAL:
                        for _ in range(count):
                            clone.inv.create(type_id)
                    else:
                        clone.inv.create(type_id, count, slot=slots[source])
                new_rows = [dict(row) for row in clone.inv.rows()]
                fresh.set_gear(inventory.gear_bonus(new_rows, fresh), inventory.card_repeat(new_rows))
                fresh.hp, fresh.sp = fresh.hp_max, fresh.sp_max
                fresh.save(self.store)
                self.save_settings(player=profile)
        except Exception as exc:
            raise ValueError('Не удалось сохранить настройки. Персонаж и вещи не изменены; повторите попытку.') from exc
        clone.combat.cancel_timers()
        clone.stop_walk()
        clone.training_effects.close()
        clone.training_effects = fresh.training_effects
        clone.char = fresh
        self.profile = profile
        self.applied_profile = copy.deepcopy(profile)
        self.outfit_revision += 1
        clone.inv.refresh_gear(push=False)
        getattr(self.store, '_battle_medicine_deadlines', {}).pop(clone.char_id, None)
        for row in rows:
            clone.inv.push_status(row, 0)
        for ground in self.room.grounds.values():
            ground.inventory_state()
        for row in new_rows:
            if row['slot'] == inventory.BAG:
                clone.inv.push_status(row, 1)
        clone.inv.push_look()
        for slot in inventory.HAND_SLOTS:
            row = next((r for r in new_rows if r['slot'] == slot), None)
            oid = BigUInt(inventory.oid_of(row)) if row is not None else inventory.EMPTY
            self.room.broadcast(('ss_obj_move', dict(id=clone.pid, obj=oid,
                                                    to=slot, **{'from': slot})))
        clone.send_player_info()
        clone.push_stats()
        clone.push_vitals()
        clone.training_effects.send_list()
        combat.Fighter.send_medicine_cooldown(clone.combat, 0)
        clone.combat.ap = clone.combat.amax_sent = fresh.ap_ceiling
        clone.combat.c_ap()
        self.room.combat.push_vitals(clone.combat)
        self.state(message)

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
        seq = self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq']
        if seq > self.serial_base + (1 << 20) - 2048:
            raise ValueError('Лимит тренировки исчерпан; войдите в центр заново')
        ch = character(profile, self.rules)
        ch._training_store = self.store
        ch.char_id, ch.name = clone.char_id, clone.active['name']
        ch.training_effects = clone.training_effects
        slots = profile_slots(profile)
        with storage.atomic(self.store.db):
            self.store.db.execute('DELETE FROM items WHERE char_id=?', (clone.char_id,))
            for source, n in profile['gear'].items():
                type_id = training_items.copy_type(source, simulator=self.rules.simulator_formulas)
                if items.root_of(type_id) == items.HEAL:
                    for _ in range(n):
                        clone.inv.create(type_id)
                else:
                    clone.inv.create(type_id, n, slot=slots[source])
            rows = clone.inv.rows()
            ch.set_gear(inventory.gear_bonus(rows, ch), inventory.card_repeat(rows))
            ch.hp, ch.sp = ch.hp_max, ch.sp_max
            ch.save(self.store)
        clone.combat.cancel_timers()
        clone.stop_walk()
        clone.char = ch
        if clone is self.clone:
            self.applied_profile = copy.deepcopy(profile)

    def touch(self):
        self.last_activity = time.monotonic()
        if self.timer is None:
            self.timer = asyncio.get_running_loop().call_later(IDLE_SECONDS, self.idle)

    def idle(self):
        self.timer = None
        left = IDLE_SECONDS - (time.monotonic() - self.last_activity)
        if left <= 0:
            try:
                self.exit()
            except Exception:
                log.exception('Idle range exit failed for %s', self.owner.char_id)
                self.emergency('Тренировка закрыта после ошибки сохранения. Настройки последнего сохранения доступны при входе.')
        else:
            self.timer = asyncio.get_running_loop().call_later(left, self.idle)

    def equipment_meta(self, profile, prefix):
        ids = list(profile['gear'])
        slots = profile_slots(profile)
        return {prefix + 'ids': ids,
                prefix + 'types': [training_items.copy_type(t, self.rules.simulator_formulas) for t in ids],
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

    def mob_label(self, type_id):
        label = mob_catalogue().get(type_id, 'Выберите противника')
        if self.rules.simulator_formulas:
            table = training_formulas.data()
            if str(type_id) in table['mobs']:
                level = table['mob_records'][table['mobs'][str(type_id)]]['level']
                label = label.rsplit(' · ', 1)[0] + ' · %d ур.' % level
            else:
                label += ' · исходные параметры моба'
        return label

    def opponent_summary(self):
        gear = set(self.opponent['gear'])
        selected = next((record for record in sets.SETS.values()
                         if set(record['members'].values()) <= gear), None)
        label = '%s (%s)' % (selected['name'], selected['variant']) if selected else 'Своя сборка'
        guns = [t for t in self.opponent['gear'] if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)]
        weapon = item_catalogue()[guns[0]][2] if guns else 'Без оружия'
        return '%s · %d ур. · %s' % (label, max(self.opponent['skills']), weapon)

    def state(self, message=''):
        message = message or self.restore_notice
        self.restore_notice = ''
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
               mob_label=Str(self.mob_label(self.mob_type)),
               enemy_preset=Str(self.opponent_summary()),
               distance=self.distance, stationary=int(self.stationary), mob_health=self.mob_health, mob_damage=self.mob_damage, enemy_healing=int(self.enemy_healing), heal_below=self.heal_below, heal_count=self.heal_count, selected_mob=self.mob_type, selected_mode=Str(self.mode),
               rules=Str(self.rules.description()), rule_values=Str(self.rules.values()), armour=c.combat.armor(), regen=progression.AP_REGEN, owner=Str(self.owner.nick), arena_width=c.loc.width, arena_height=c.loc.height, native_map=int(self.location == 59), loaded=int(c in self.room.players), spec_max=progression.SPEC_MAX,
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
        return commands.request(self, p)

    def catalogue(self, p):
        return commands.catalogue(self, p)

    def start(self, mode):
        with checkpoints.mutation(self):
            self._start(mode)
            self.save_settings()

    def _start(self, mode):
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
            self.enemy_heals_left = self.heal_count
            if self.enemy_healing and self.heal_count and not any(
                    row['root'] == items.HEAL and items.battle_medicine(row['type_id'])
                    for row in self.enemy.inv.rows()):
                # Basic ordinary combat kit, subject to the same normal use checks.
                medicine = min((source for source in item_catalogue()
                    if items.root_of(source) == items.HEAL and items.battle_medicine(source)
                    and item_line(source) == 'A' and items.params_of(source).get('max_h_rest', 0) > 0),
                    key=lambda source: (items.params_of(source).get('heal_cost', 0), source))
                count = min(self.heal_count, max(0, training_shop.MAX_ROWS - len(self.enemy.inv.rows())))
                for _ in range(count):
                    self.enemy.inv.create(training_items.copy_type(medicine, simulator=self.rules.simulator_formulas))
            self.room.enter(self.enemy)
            self.enemy.combat.entered()
        else:
            eid = getattr(self, '_mob_entity_id', None)
            if eid is None:
                self._mob_entity_id = eid = self.room.ids.npc()
            self.mob_eid = eid
            self.room.npcs[eid] = rooms.NPC(enemy_cell, self.mob_type, world.MOB)
            mob = mobs.Mob(eid, self.mob_type, enemy_cell)
            mob.training_ground = self
            mob.stats = copy.copy(mob.stats)
            if self.rules.simulator_formulas and str(self.mob_type) in training_formulas.data()['mobs']:
                training_formulas.configure_mob(mob, self)
            elif not self.rules.simulator_formulas and 1 <= mob.stats.level <= MAX_LEVEL:
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
        note = 'Противник вызван'
        if mode == 'mob' and self.rules.simulator_formulas and str(self.mob_type) not in training_formulas.data()['mobs']:
            note += '. Для этой цели нет профиля симулятора: параметры моба из основной игры.'
        self.state(note)

    def enemy_turn(self):
        training_bot.turn(self)

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
            victim.sess.training_effects.close()
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
        try:
            self._reset(result)
        except Exception:
            log.exception('Could not reset range for %s', self.owner.char_id)
            self.emergency('Не удалось восстановить тренировку. Основной персонаж сохранён.')

    def _reset(self, result):
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

    def dispose(self):
        """Best-effort teardown never leaves the owner attached to a half-clone."""
        if self.closed:
            return
        self.closed = True
        if self.owner.training_ground is self:
            self.owner.training_ground = None
        ACTIVE.discard(self)
        actions = [self.hide_corpse]
        for timer in (self.timer, self.pending):
            if timer is not None:
                actions.append(timer.cancel)
        self.timer = self.pending = None
        for clone in (self.clone, self.enemy_cache):
            if clone is not None:
                actions.extend((clone.training_effects.close, clone.combat.cancel_timers,
                                clone.combat.end_duels))
        actions.extend((self.clear_target, lambda: movement.get(self.room).forget(self.clone),
                        lambda: self.room.leave(self.clone)))
        for action in actions:
            try:
                action()
            except Exception:
                log.exception('Range cleanup failed for %s', self.owner.char_id)
        self.room.grounds.pop(self.token, None)
        self.room.owner_ids.pop(self.owner.pid, None)
        rc = self.room.combat
        try:
            if self.room.grounds:
                self.room.ground = next(iter(self.room.grounds.values()))
                rc.store = self.room.ground.store
                rc.sync_ws()
            else:
                if rc.timer is not None:
                    rc.timer.cancel()
                    rc.timer = None
                self.room.npcs.clear()
                rc.mobs.clear()
        except Exception:
            log.exception('Range room cleanup failed for %s', self.owner.char_id)
        finally:
            try:
                self.store.close()
            except Exception:
                log.exception('Could not close private range store for %s', self.owner.char_id)

    def emergency(self, message):
        """Discard only the working clone, without another checkpoint write."""
        from protocol import frame
        try:
            if not self.owner.closed:
                self.owner.writer.write(frame('tg', op='error', message=Str(message)))
        except Exception:
            log.exception('Could not report range failure to %s', self.owner.char_id)
        try:
            self.dispose()
        finally:
            try:
                self.owner.close(force=True)
            except Exception:
                log.exception('Could not close range owner %s', self.owner.char_id)

    def exit(self, notify=True, suspend=False, quest_ack=False):
        if self.closed:
            return
        previous_inside = self.inside
        try:
            self.remember_outfit()
            self.inside = bool(suspend)
            self.save_settings()
        except Exception as exc:
            self.inside = previous_inside
            if checkpoints.uncertain(exc, self.owner.inv.store.db):
                self.emergency('Не удалось подтвердить выход. Перезайдите для восстановления.')
                if not suspend:
                    raise ValueError('Не удалось подтвердить выход с полигона') from exc
                return
            if not suspend:
                self.touch()
                raise ValueError('Не удалось сохранить выход. Настройки сохранены ранее; повторите попытку.') from None
            log.exception('Could not checkpoint training for %s; last durable checkpoint retained', self.owner.char_id)
        if quest_ack:
            self.clone.send('tg', op='exit_pending')
            self.clone.send('cmdAck', res=0)
        self.dispose()
        if notify:
            self.return_owner()

    def return_owner(self):
        if not self.owner.closed:
            self.owner.send('tg', op='exit', active=0)
            self.owner.training_return = True
            self.owner.enter_location()
            manager = services.clans()
            member = manager.member(self.owner.char_id)
            manager.fellow_self(self.owner, member)
            if member is not None:
                manager.send_roster(self.owner, member)
                manager.send_standings(self.owner, member['clan_id'])
            training_party.refresh(self)



def check_entry(owner, p):
    from training.config import CLIENT_PROTOCOL
    if not settings.ENABLED:
        raise ValueError('Учебный центр пока недоступен')
    if getattr(owner, 'training_protocol', None) != CLIENT_PROTOCOL:
        raise ValueError('Обновите клиент для входа на полигон')
    participants = training_party.entrants(owner)
    if len(ACTIVE) + len(participants) > settings.MAX_SESSIONS:
        raise ValueError('Учебный центр занят. Попробуйте позже')
    npc = owner.room.npc(integer(p.get('npc', 0), 1, 999999)) if owner.room else None
    if owner.loc.id != MARKET or npc is None or npc.type_id != BERT \
            or owner.combat.dead or owner.combat.in_combat() or owner.barter.deal is not None \
            or not progression.within_reach(owner.live_cell(), npc.cell, owner.loc.width, owner.loc.height):
        raise ValueError('Подойдите к Берту вне боя')


def enter_from_quest(owner):
    npc_id = next((eid for eid, npc in owner.room.npcs.items() if npc.type_id == BERT), 0) if owner.room else 0
    from training.entry import request
    request(owner, dict(npc=npc_id), check_entry, enter)


def save_presence(grounds):
    """Freeze real progress and presence in one main-store transaction."""
    store = grounds[0].owner.inv.store
    dirty = [(ground.owner.char, ground.owner.char._spec_slots_dirty) for ground in grounds]
    try:
        with storage.atomic(store.db):
            for ground in grounds:
                ground.owner.char.save(store)
                ground.inside = True
                ground.save_settings()
    except BaseException:
        # Character.save clears this flag after its nested transaction.
        # An outer rollback must not lose the pending paid-slot update.
        for char, pending in dirty:
            char._spec_slots_dirty |= pending
        raise


def enter(owner, p):
    check_entry(owner, p)
    participants = training_party.entrants(owner)
    prepared = []
    activated = set()
    presence_saved = False
    presence_attempted = False
    try:
        for participant in participants:
            ground = Ground(participant)
            if prepared:
                training_party.join(ground, prepared[0].room)
            prepared.append(ground)
        store = owner.inv.store
        if any(ground.owner.inv.store is not store for ground in prepared):
            raise ValueError('Участники используют разные хранилища')
        presence_attempted = True
        save_presence(prepared)
        presence_saved = True
        for ground in prepared:
            activated.add(ground)
            activate(ground, persist=False)
        training_party.refresh(prepared[0])
    except Exception as exc:
        uncertain = presence_attempted and checkpoints.uncertain(exc, owner.inv.store.db)
        if presence_saved:
            try:
                # Everyone got inside=True, including visitors not yet activated.
                # Clear all their memberships together before discarding clones.
                with storage.atomic(owner.inv.store.db):
                    for ground in prepared:
                        ground.inside = False
                        ground.save_settings()
            except Exception:
                log.exception('Could not roll back durable range memberships')
                uncertain = True
        for ground in reversed(prepared):
            if uncertain:
                ground.emergency('Не удалось подтвердить вход. Перезайдите для восстановления.')
                continue
            ground.dispose()
            if ground in activated and not ground.owner.closed:
                ground.return_owner()
        raise ValueError('Не удалось открыть полигон. Основные персонажи сохранены; повторите попытку.') from exc



def activate(ground, persist=True):
    participant = ground.owner
    if persist:
        save_presence((ground,))
    from training.events import inventory_snapshot
    participant.training_inventory_before = inventory_snapshot(participant)
    training_party.cancel_invites(participant)
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
    from training.type_metadata import announce
    announce(participant)
    ground.state()
    ground.clone.enter_location()


def resume(owner):
    """Restore personal progress; ignore legacy shared-room tokens in solo mode.

    In the dormant shared mode party membership selects visitors at entry,
    not continued access. Only the server's durable checkpoint supplies that
    room token, never a client command. Solo restoration keeps the personal
    checkpoint but allocates a fresh room instead of rejoining another player.
    """
    current = getattr(owner, 'training_ground', None)
    if current is not None:
        current.clone.enter_location()
        return True
    saved = owner.inv.store.training_profile(owner.char_id)
    if not isinstance(saved, dict) or saved.get('inside') is not True:
        return False
    if not settings.ENABLED or len(ACTIVE) >= settings.MAX_SESSIONS:
        owner.say('Полигон временно недоступен. Его настройки сохранены; повторите вход в игру позже.')
        return False
    ground = None
    activating = False
    try:
        ground = Ground(owner)
        visit = saved.get('room')
        if config.SHARED_ROOMS and isinstance(visit, str) and re.fullmatch('[0-9a-f]{32}', visit):
            shared = next((peer.room for peer in ACTIVE
                           if not peer.closed and peer.room.key[1] == visit), None)
            if shared is not None:
                training_party.join(ground, shared)
                ground.clone.pos = training_party.free_spawn(
                    shared, control_cell(ground.location), excluded=ground.clone)
            else:
                ground.room.key = (ground.location, visit)
        activating = True
        activate(ground)
        training_party.refresh(ground)
        return True
    except Exception as exc:
        log.exception('Could not resume training for character %s', owner.char_id)
        if activating and checkpoints.uncertain(exc, owner.inv.store.db):
            # Do not overwrite a possibly committed, migrated checkpoint with
            # an old snapshot just to increment the failed-resume counter.
            ground.emergency('Не удалось подтвердить восстановление. Повторите вход позже.')
            return False
        if ground is not None:
            ground.dispose()
        failed = copy.deepcopy(saved)
        try:
            failures = integer(failed.get('resume_failures', 0), 0, 3)
        except ValueError:
            failures = 0
        failed['resume_failures'] = min(3, failures + 1)
        if failed['resume_failures'] >= 3:
            failed['inside'] = False
        try:
            owner.inv.store.save_training_profile(owner.char_id, failed)
        except Exception:
            log.exception('Could not record range recovery guard for %s', owner.char_id)
        owner.send('tg', op='exit', active=0)
        owner.say('Не удалось загрузить полигон. Основной персонаж сохранён; повторите вход позже.')
        return False


def preload():
    training_rules.current()
    training_profiles.catalogue()
    if training_formulas.available():
        training_formulas.engine().coefficients()
    training_effects.definitions()
    training_items.prepare(item_catalogue())
    training_items.register_sets_and_strings()
    # Build both immutable catalogue indexes before accepting sockets, not on
    # the first filter click or profile switch in the shared event loop.
    training_supply.index(False)
    if training_formulas.available():
        training_supply.index(True)
    for source in item_catalogue():
        training_display.icon_source(source)
    mob_catalogue()
    from training.type_metadata import payload
    payload()  # Build once at startup, never on the first visitor's hot path.
    content.validate()
    for location in LOCATIONS:
        geometry(location)
        loc = arena_location(location)
        cells = [post.cell(loc.width) for post in training_layout.posts_for(location)]
        if len(set(cells)) != len(cells) or any(not 0 <= cell < loc.width * loc.height or cell in loc.obstacles for cell in cells):
            raise ValueError('Invalid private range post layout')
