"""Party selects who shares a range; inventories remain per-character."""
from training import services
from protocol import Str

import movement
import progression
import rooms
import storage


def entry_available(owner):
    from training import settings
    if not settings.ENABLED:
        return False
    party = owner.party()
    return party is None or party.leader == owner.char_id


def cancel_invites(owner):
    directory = services.parties()
    host = directory.invites.pop(owner.char_id, None)
    inviter = directory.session_of(host) if host is not None else None
    if inviter is not None:
        inviter.send('p_op', op=8, mob_id=owner.pid)
    for guest, sender in tuple(directory.invites.items()):
        if sender == owner.char_id:
            directory.invites.pop(guest, None)
    services.clans().drop_invite(owner.char_id, 'entered training range')


def entrants(owner):
    """Leader-directed group entry, as requested by the game rules.

    Windows/routes are cancelled on entry; already paid/queued journeys are
    refused before any participant is changed, so entry cannot eat their fare.
    """
    if not entry_available(owner):
        raise ValueError('Отправиться на полигон с отрядом может только его командир')
    party = owner.party()
    result = [owner]
    if owner.way is not None or owner.passage is not None or owner.arrival is not None:
        raise ValueError('Сначала завершите или отмените поездку перед входом на полигон')
    if party is None:
        return result
    directory = services.parties()
    for char_id in party.members:
        if char_id == owner.char_id:
            continue
        member = directory.session_of(char_id)
        if member is None or member.room is not owner.room:
            continue
        from training.config import CLIENT_PROTOCOL
        if getattr(member, 'training_protocol', None) != CLIENT_PROTOCOL:
            raise ValueError('Участнику отряда %s нужно обновить клиент для полигона' % member.nick)
        if (member.closed or member.training_ground is not None or member.combat.dead
                or member.combat.in_combat() or member.barter.deal is not None
                or member.way is not None or member.passage is not None or member.arrival is not None):
            raise ValueError('Участник отряда %s пока не может отправиться на полигон' % member.nick)
        result.append(member)
    return result


def free_spawn(room, desired, excluded=None, reserved=()):
    """Include participants whose client has not acknowledged lenter yet."""
    blocked = movement.get(room).occupied(excluded)
    blocked.update(reserved)
    blocked.update(ground.clone.pos for ground in room.grounds.values()
                   if ground.clone is not excluded)
    queue, seen = [desired], {desired}
    for cell in queue:
        if cell not in blocked and cell not in room.loc.obstacles:
            return cell
        for candidate in progression.hex_neighbours(cell, room.loc.width, room.loc.height):
            if candidate not in seen and candidate not in room.loc.obstacles:
                seen.add(candidate)
                queue.append(candidate)
    raise ValueError('На полигоне нет свободной клетки')


def join(ground, room):
    ground.room = room
    ground._mob_entity_id = None
    ground.location = room.loc.id
    ground.post_ids = room.ground.post_ids
    ground.terminal_id = room.ground.terminal_id
    ground.posts = room.ground.posts
    ground.clone.room, ground.clone.loc = room, room.loc
    ground.clone.pos = free_spawn(room, room.ground.clone.pos)
    room.grounds[ground.token] = ground
    room.owner_ids[ground.owner.pid] = ground.clone.pid


def frame(ground, command, params):
    params = dict(params)
    ids = ground.room.owner_ids
    if command == 'p_m':
        params['list'] = [ids.get(value, value) for value in params.get('list', ())]
    elif 'mob_id' in params:
        params['mob_id'] = ids.get(params['mob_id'], params['mob_id'])
    return params


def command(ground, params):
    params = dict(params)
    pid = int(params.get('id', 0) or 0)
    params['id'] = next((real for real, clone in ground.room.owner_ids.items() if clone == pid), pid)
    owner = ground.owner
    owner.training_party_control = True
    try:
        owner.cmd_p_op(params)
    finally:
        owner.training_party_control = False


def refresh(ground):
    directory = services.parties()
    party = ground.owner.party()
    if party is not None:
        directory.roster(party)


def relocate(ground, location):
    """One shared map, changed only while all participants are ready."""
    import copy
    from training import arena, geometry, settings, layout, shop
    import world
    if location not in settings.LOCATIONS:
        raise ValueError('Неизвестная тренировочная локация')
    old = ground.room
    members = tuple(old.grounds.values())
    if any(member.phase != 'ready' or member.clone.combat.duels
           or member.clone.combat.dead for member in members):
        raise ValueError('Перед сменой общей площадки завершите тренировки всех участников')
    geometry.geometry(location)
    loc = copy.copy(geometry.arena_location(location))
    loc.spawns, loc.pvp = [], 1
    room = arena.TrainingRoom(loc, rooms.IdAllocator(first=max(ground.post_ids.values()) + 1), {}, key=(location, old.key[1]))
    room.npcs.clear()
    room.ground, room.grounds, room.owner_ids = ground, {}, dict(old.owner_ids)
    # Prepare geometry and all durable destinations before moving anyone.
    # Party profiles share one main store, so one failed write rolls back all.
    store = ground.owner.inv.store
    if any(member.owner.inv.store is not store for member in members):
        raise ValueError('Участники используют разные хранилища')
    posts = {ground.post_ids[p.key]: p for p in layout.posts_for(location)
             if not p.line or shop.stock(p)}
    for eid, post in posts.items():
        cell = post.cell(loc.width)
        if cell in loc.obstacles:
            raise ValueError('Стойка на новой площадке недоступна')
        room.npcs[eid] = rooms.NPC(cell, post.resource, world.COMMONER)
    positions = []
    for member in members:
        positions.append(free_spawn(room, geometry.control_cell(location), reserved=positions))
    room.combat = arena.TrainingCombat(room, ground.store)
    try:
        with storage.atomic(store.db):
            for member in members:
                member.save_settings(location=location)
    except storage.CommitError as exc:
        for member in members:
            member.emergency('Не удалось подтвердить смену площадки. Перезайдите для восстановления.')
        raise ValueError('Не удалось подтвердить смену площадки') from exc
    except Exception as exc:
        raise ValueError('Не удалось сохранить площадку; участники остаются на прежнем месте.') from exc
    if old.combat.timer:
        old.combat.timer.cancel()
    for member in members:
        member.hide_corpse()
        member.clone.combat.cancel_timers()
        movement.get(old).forget(member.clone)
    old.players.clear()
    for member, position in zip(members, positions):
        member._mob_entity_id = None
        member.room, member.location = room, location
        member.clone.room, member.clone.loc = room, loc
        member.clone.pos = position
        room.grounds[member.token] = member
        member.context = 'computer'
    for member in members:
        member.posts = posts
    for member in members:
        member.clone.enter_location()
