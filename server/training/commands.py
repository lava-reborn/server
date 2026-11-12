"""Training range: commands."""
import inventory
import items
import logging
import mobs
import secrets
import sets
import time
from protocol import BigUInt, Str
from training import (
    display as training_display,
    formulas as training_formulas,
    items as training_items,
    layout as training_layout,
    opponents as training_opponents,
    presets as training_presets,
    profiles as training_profiles,
    supply as training_supply,
)
from training.catalog import contraband, item_catalogue, item_line, mob_catalogue
from training.character import validate_profile
from training.settings import MAX_ITEMS, MAX_LEVEL, PAGE_SIZE, SPAWN_LABELS
from training.validation import integer


log = logging.getLogger('lava')


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
                raise ValueError('Вход на полигон - через задание у Берта')
            else:
                raise ValueError('Нет активной тренировки')
        elif cmd == 'logout':
            owner.close(force=True)
        else:
            ground.touch()
            ground.clone.handle_training(cmd, p)
    except (ValueError, TypeError, KeyError) as exc:
        if owner.closed:
            return True
        target = ground.clone if ground and not ground.closed else owner
        module = __import__(owner.__class__.__module__)
        if ground and cmd != 'tg' and module.expects_ack(cmd, p) and getattr(target, 'training_acks', 0) == acks:
            target.send('cmdAck', res=inventory.RES_REFUSED)
        target.send('tg', op='error', message=Str(str(exc)))
    except Exception:
        log.exception('training-ground command failed: %s', cmd)
        if ground:
            ground.emergency('Тренировка завершена из-за ошибки. Основной персонаж сохранён.')
        else:
            owner.send('tg', op='error', message=Str('Не удалось выполнить команду полигона'))
    return True


def request(ground, p):
    op = str(p.get('op', ''))
    if p.get('token') != ground.token:
        raise ValueError('Окно тренировки устарело')
    if op == 'exit':
        ground.require_terminal()
        ground.exit()
        return
    now = time.monotonic()
    if op in ('catalogue', 'supply_list', 'supply_variants', 'supply_bag', 'kit_preview'):
        if now - ground.last_catalogue_request < 0.03:
            raise ValueError('Дождитесь загрузки списка и повторите')
        ground.last_catalogue_request = now
    else:
        if now - ground.last_request < 0.08:
            raise ValueError('Дождитесь ответа на предыдущее действие и повторите')
        ground.last_request = now
    ground.touch()
    if op in ('rules', 'spawn', 'fighterpreset', 'apply', 'profile_save', 'profile_delete',
              'kit_apply', 'supply_get', 'supply_return', 'reset_player', 'start'):
        if ground.phase != 'ready':
            raise ValueError('Сначала завершите тренировку')
        ground.require_post()
        from training.checkpoints import mutation
        with mutation(ground):
            result = apply_request(ground, p, op, now)
            if op not in ('supply_get', 'supply_return'):
                ground.save_settings()
            return result
    return apply_request(ground, p, op, now)


def apply_request(ground, p, op, now):
    if op == 'return':
        ground.finish('Возврат к компьютеру', force=True)
        return
    if op == 'abort':
        ground.finish('Бой прерван')
        return
    if op == 'open':
        ground.open_post(integer(p.get('npc', ground.terminal_id), 1, 2**31-1))
        return
    if ground.phase != 'ready':
        raise ValueError('Сначала завершите тренировку')
    ground.require_post()
    if op in ('profile_save', 'profile_delete'):
        training_profiles.manage(ground, op, p)
        return
    if op.startswith('kit_'):
        training_presets.handle(ground, op, p)
        return
    if op.startswith('supply_'):
        training_supply.handle(ground, op, p)
        return
    if op == 'reset_prepare':
        ground.require_player_reset()
        nonce = secrets.token_hex(16)
        ground.reset_confirmation = (nonce, now + 60)
        ground.clone.send('tg', op='reset_confirm', token=Str(ground.token), confirmation=Str(nonce))
    elif op == 'reset_player':
        ground.reset_player(str(p.get('confirmation', '')))
    elif op == 'recover':
        if ground.context != 'player':
            raise ValueError('Восстановление доступно у инструктора')
        ground.clone.char.hp, ground.clone.char.sp = ground.clone.char.hp_max, ground.clone.char.sp_max
        ground.clone.combat.ap = ground.clone.char.ap_ceiling
        ground.clone.push_vitals()
        ground.clone.combat.c_ap()
        ground.state('Тренировочный персонаж восстановлен')
    elif op == 'location':
        ground.require_terminal()
        ground.change_location(integer(p.get('location'), 1, 65535))
        ground.state('Тренировочная локация изменена')
    elif op == 'rules':
        try:
            rules = training_profiles.resolve(str(p.get('values', '')), p.get('profile'), ground.personal_profiles)
        except (ValueError, TypeError):
            raise ValueError('Проверьте профиль и множители (0,01–10; добавка брони 0–200). Если версия устарела, снова откройте компьютер.') from None
        validate_profile(ground.profile, rules)
        validate_profile(ground.opponent, rules)
        ground.require_terminal()
        equipment_changed = ground.configure_player(ground.profile, rules=rules)
        if equipment_changed:
            # Other clients also cache instance ids; update their live list
            # before publishing the replacement clothes and weapons.
            for peer in ground.room.grounds.values():
                if peer is not ground:
                    peer.inventory_state()
            ground.clone.inv.push_look()
            for slot in (inventory.PRIMARY, inventory.SECONDARY):
                row = ground.clone.inv.in_slot(slot)
                oid = BigUInt(inventory.oid_of(row)) if row is not None else inventory.EMPTY
                ground.room.broadcast(('ss_obj_move', dict(id=ground.clone.pid, obj=oid,
                                                       to=slot, **{'from': slot})))
        ground.clone.send_player_info()
        ground.clone.push_stats()
        ground.clone.push_vitals()
        ground.clone.combat.ap = ground.clone.character().ap_ceiling
        ground.clone.combat.c_ap()
        ground.room.combat.push_vitals(ground.clone.combat)
        ground.state('Правила сессии применены и сохранены')
    elif op == 'spawn':
        ground.spawn_point = integer(p.get('spawn_point'), 0, len(SPAWN_LABELS) - 1)
        ground.save_settings()
        ground.state('Точка противника сохранена')
    elif op == 'catalogue':
        post = training_layout.BY_KEY[ground.context]
        request = dict(p)
        if post.key != 'computer':
            request.update(category=post.category, wclass=post.weapon_class)
        elif request.get('category', 'mob') not in ('mob', 'weapon', 'set', 'armour', 'pouch', 'ammo', 'medicine'):
            raise ValueError('Неизвестная категория')
        ground.catalogue(request)
    elif op == 'fighterpreset':
        ground.require_terminal()
        ground.opponent = ground.fighter_preset(integer(p.get('set'), 1, 65535))
        ground.mode = 'fighter'
        ground.save_settings()
        ground.state('Противник собран: комплект, подсумок, оружие и патроны. При желании замените снаряжение.')
    elif op == 'apply':
        who = p.get('who', 'player')
        if who not in ('player', 'enemy'):
            raise ValueError('Неизвестный пресет')
        if any(len(str(p.get(key, ''))) > limit for key, limit in
               (('skills', 128), ('specs', 256), ('gear', 1024))):
            raise ValueError('Слишком большой пресет')
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
        profile = validate_profile(raw, ground.rules)
        if who == 'player':
            if ground.context == 'player':
                ground.configure_player(profile)
            else:
                ground.replace_player(profile, 'Пресет применён и сохранён')
                return
            ground.clone.send_player_info()
            ground.clone.push_stats()
            ground.clone.push_vitals()
            ground.clone.combat.ap = ground.clone.character().ap_ceiling
            ground.clone.combat.amax_sent = ground.clone.character().ap_ceiling
            ground.clone.combat.c_ap()
        else:
            ground.opponent = profile
            ground.mode = 'fighter'
            ground.save_settings()
        ground.state('Пресет применён и сохранён')
    elif op == 'start':
        ground.require_terminal()
        spawn_point = integer(p.get('spawn_point', ground.spawn_point), 0, len(SPAWN_LABELS) - 1)
        mob_health = integer(p.get('mob_health', ground.mob_health), 25, 300)
        mob_damage = integer(p.get('mob_damage', ground.mob_damage), 25, 300)
        ground.stationary = integer(p.get('stationary', 0), 0, 1) == 1
        mode = str(p.get('mode', 'mob'))
        if mode not in ('mob', 'fighter'):
            raise ValueError('Неизвестный противник')
        mob = integer(p.get('mob', ground.mob_type), 1, 100000)
        if mode == 'mob' and mob not in mob_catalogue():
            raise ValueError('Моб недоступен')
        ground.enemy_healing = integer(p.get('enemy_healing', int(ground.enemy_healing)), 0, 1) == 1
        ground.heal_below = integer(p.get('heal_below', ground.heal_below), 10, 90)
        ground.heal_count = integer(p.get('heal_count', ground.heal_count), 0, 30)
        ground.mob_type = mob
        ground.spawn_point = spawn_point
        ground.mob_health, ground.mob_damage = mob_health, mob_damage
        ground.start(mode)
        ground.save_settings()


def catalogue(ground, p):
    cat = str(p.get('category', 'weapon'))
    page = integer(p.get('page', 0), 0, 10000)
    level = integer(p.get('level', 0), 0, 40 if cat == 'mob' else MAX_LEVEL)
    query = str(p.get('query', '')).strip().casefold()[:48]
    wclass = integer(p.get('wclass', -1), -1, 6)
    upgrade = str(p.get('upgrade', 'all'))
    if upgrade not in ('all', 'base', 'modified'):
        raise ValueError('Неизвестный вариант улучшения')
    line = str(p.get('line', 'all'))
    if line not in ('all', 'A', 'G', 'P', 'C'):
        raise ValueError('Неизвестная версия предмета')
    available_levels = []
    if cat == 'set':
        rows = [(t, '%s · %d ур. (%s)' % (v['name'], v['level'], v['variant']))
                for t, v in sets.SETS.items() if v['variant'] in ('A', 'G')
                and (line == 'all' or line == v['variant'])
                and query in v['name'].casefold()
                and all(member in item_catalogue() and training_items.available(member, ground.rules.simulator_formulas)
                        for member in v['members'].values())]
    elif cat == 'mob':
        group = str(p.get('group', 'all'))
        if group not in training_layout.MOB_GROUPS:
            raise ValueError('Неизвестная категория противников')
        def mob_level(t):
            if ground.rules.simulator_formulas and str(t) in training_formulas.data()['mobs']:
                data = training_formulas.data()
                return data['mob_records'][data['mobs'][str(t)]]['level']
            return mobs.stats(t).level
        # Group/profile levels precede search and pagination: the menu must
        # not lose choices just because the current page or search is empty.
        candidates = {t: mob_level(t) for t in mob_catalogue()
                      if group == 'all' or training_opponents.RECORDS[t]['group'] == group}
        available_levels = sorted({value for value in candidates.values() if value > 0})
        if level and level not in available_levels:
            level, page = 0, 0
        rows = [(t, ground.mob_label(t)) for t, value in candidates.items()
                if (not level or value == level) and query in mob_catalogue()[t].casefold()]
    else:
        rows = [(t, entry[2]) for t, entry in item_catalogue().items()
                if t not in training_supply.ARCHIVE_SOURCES
                and (entry[0] == cat or cat == 'weapon' and entry[0] in ('special_weapon','experimental_weapon'))
                and training_items.available(t, ground.rules.simulator_formulas)
                and query in entry[2].casefold()
                and (line == 'all' or (t in contraband() if line == 'C' else item_line(t) == line))
                and (cat != 'weapon' or upgrade == 'all' or bool(training_display.upgrade(t)) == (upgrade == 'modified'))
                and (cat != 'weapon' or wclass < 0 or
                     (6 if items.root_of(t) == items.COLD_ARM else training_display.weapon_class(t)) == wclass)]
    if cat != 'mob':
        def item_level(t):
            return sets.SETS[t]['level'] if cat == 'set' else item_catalogue()[t][1]
        available_levels = sorted({item_level(t) for t, _ in rows if item_level(t) > 0})
        if level and level not in available_levels:
            level, page = 0, 0
        rows = [(t, label) for t, label in rows if not level or item_level(t) == level]
    rows.sort(key=lambda row: (mob_level(row[0]), row[1], row[0]) if cat == 'mob' else (row[1], row[0]))
    total = len(rows)
    rows = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    groups = [','.join(str(member) for member in sets.SETS[t]['members'].values())
              if cat == 'set' else '' for t, _ in rows]
    icons = [next(iter(sets.SETS[t]['members'].values())) if cat == 'set' else t for t, _ in rows]
    ground.clone.send('tg', op='catalogue', ids=[t for t, _ in rows], groups=groups, icons=icons,
                    types=[training_items.copy_type(t, ground.rules.simulator_formulas) if cat not in ('mob', 'set') else 0 for t, _ in rows],
                    context=Str(ground.context), request_id=integer(p.get('request_id', 0), 0, 2**31-1),
                    levels=[mob_level(t) if cat == 'mob' else item_catalogue()[t][1] if t in item_catalogue() else sets.SETS[t]['level'] for t, _ in rows],
                    group_slots=[','.join(str(inventory.HEAD + items.params_of(m)['slot_type']) for m in sets.SETS[t]['members'].values()) if cat == 'set' else '' for t, _ in rows],
                    labels=[name for _, name in rows], total=total, page=page,
                    available_levels=available_levels, selected_level=level,
                    slots=[0 if cat in ('mob', 'set') else inventory.PRIMARY if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)
                           else inventory.HEAD + items.params_of(t)['slot_type']
                           if items.root_of(t) == items.WEAR and cat != 'mob' else 0 for t, _ in rows])
