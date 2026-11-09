"""Party selects who shares a range; inventories remain per-character."""
import sys

import movement
import progression
import rooms


def entry_available(owner):
    import training_ground
    if not training_ground.ENABLED:
        return False
    party = owner.party()
    return party is None or party.leader == owner.char_id


def entrants(owner):
    if not entry_available(owner):
        raise ValueError('Отправиться на полигон с отрядом может только его командир')
    party = owner.party()
    result = [owner]
    if party is None:
        return result
    directory = sys.modules[owner.__class__.__module__].PARTIES
    for char_id in party.members:
        if char_id == owner.char_id:
            continue
        member = directory.session_of(char_id)
        if member is None or member.room is not owner.room:
            continue
        if (member.closed or member.training_ground is not None or member.combat.dead
                or member.combat.in_combat() or member.barter.deal is not None):
            raise ValueError('Участник отряда %s пока не может отправиться на полигон' % member.nick)
        result.append(member)
    return result


def free_spawn(room, desired, excluded=None):
    """Include participants whose client has not acknowledged lenter yet."""
    blocked = movement.get(room).occupied(excluded)
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
    directory = sys.modules[ground.owner.__class__.__module__].PARTIES
    party = ground.owner.party()
    if party is not None:
        directory.roster(party)


def relocate(ground, location):
    """One shared map, changed only while all participants are ready."""
    import copy
    import training_ground as training
    import world
    if location not in training.LOCATIONS:
        raise ValueError('Неизвестная тренировочная локация')
    old = ground.room
    members = tuple(old.grounds.values())
    if any(member.phase != 'ready' for member in members):
        raise ValueError('Перед сменой общей площадки завершите тренировки всех участников')
    training.geometry(location)
    loc = copy.copy(training.arena_location(location))
    loc.spawns, loc.pvp = [], 1
    room = training.TrainingRoom(loc, rooms.IdAllocator(), {}, key=(location, ground.token))
    room.npcs.clear()
    room.ground, room.grounds, room.owner_ids = ground, {}, dict(old.owner_ids)
    if old.combat.timer:
        old.combat.timer.cancel()
    for member in members:
        member.hide_corpse()
        member.clone.combat.cancel_timers()
        movement.get(old).forget(member.clone)
    old.players.clear()
    for member in members:
        member.room, member.location = room, location
        member.clone.room, member.clone.loc = room, loc
        member.clone.pos = free_spawn(room, training.control_cell(location))
        room.grounds[member.token] = member
        member.context = 'computer'
    ground.populate_posts()
    for member in members:
        member.posts = ground.posts
    room.combat = training.TrainingCombat(room, ground.store)
    for member in members:
        member.save_settings()
        member.clone.enter_location()
