"""Plantation harvesting and its resource/respawn settlement.

Palms have 5000 HP. The dedicated tool follows its own damage frame without
character bonuses; other weapons retain ordinary combat timing and costs.
Ripe bananas have 50% of the resource chance, leaves 25%, and green/bad
bananas 12.5% each.
A fixed 15% miss chance is a designed server rule, not recovered historical
balance. Swing timing and AP cost follow the tool's static item frame.
The finishing worker owns one ground resource for this visit. A felled palm
uses the camp creatures' respawn clock and publication, including restart.
"""
import copy
import asyncio
import logging
import random
import time

import eden
import eden_ground
import inventory
import items
import mobs
import pace
import storage


log = logging.getLogger("lava")
TOOL = eden.CLEAVER
PALM_HP = 5000
MISS_CHANCE = 0.15
REWARDS = (eden.GOOD_BANANA, eden.GREEN_BANANA, eden.BAD_BANANA, eden.PALM_LEAF)
REWARD_POOL = ((eden.GOOD_BANANA,) * 4 + (eden.GREEN_BANANA, eden.BAD_BANANA)
               + (eden.PALM_LEAF,) * 2)
RNG = random.Random()


def respawn_seconds():
    """Match a camp creature: corpse phase, then its unscaled respawn wait.

    Palms remain inert objects for harvesting, but deliberately use the
    creature clock rather than the shorter standing-object respawn clock.
    Import locally because combat itself imports this module.
    """
    from combat import CORPSE_DELAY, RESPAWN_DELAY
    return pace.paced(CORPSE_DELAY) + RESPAWN_DELAY


def is_palm(loc, target):
    return (target is not None and not getattr(target, "is_player", False)
            and getattr(target, "type_id", None) in eden.PALMS
            and getattr(loc, "id", None) in eden.LOCATIONS)


def _cycle(target):
    target._eden_cycle = object()
    target.stats.hp_max = PALM_HP
    target.hp = target.stats.hp_max
    target.sp = 0
    target._eden_reward = None
    target._eden_native_before_hit = None


def prepare_room(rc):
    """Give each local palm its own stats; never mutate mobs.stats' cache."""
    saved = None
    for target in rc.mobs.values():
        if not is_palm(rc.room.loc, target):
            continue
        target.stats = copy.copy(target.stats)
        target.stats.role = "object"
        target.stats.sp_max = 0
        target.stats.can_attack = target.stats.moves = False
        target.stats.xp_pool = target.stats.xp_mult = target.stats.aggro = 0
        _cycle(target)
        if saved is None:
            saved = {(r['home_cell'], r['mob_type']): r['respawn_at']
                     for r in rc.store.db.execute(
                         'SELECT home_cell, mob_type, respawn_at FROM eden_palm_state WHERE loc=?',
                         (rc.room.loc.id,)).fetchall()}
        due = saved.get((target.home, target.type_id), 0)
        if due > time.time():
            _retire(rc, target, due, announce=False)


def _respawn(rc, target, token):
    if getattr(target, '_eden_respawn_token', None) is not token:
        return
    left = target._eden_due - time.time()
    if left > 0:
        target._eden_respawn_timer = asyncio.get_running_loop().call_later(
            left, _respawn, rc, target, token)
        return
    try:
        with storage.atomic(rc.store.db):
            rc.store.db.execute('DELETE FROM eden_palm_state WHERE loc=? AND home_cell=?'
                                 ' AND mob_type=? AND respawn_at<=?',
                                 (rc.room.loc.id, target.home, target.type_id, time.time()))
    except Exception:
        log.exception('Eden palm respawn persistence failed')
        target._eden_respawn_timer = asyncio.get_running_loop().call_later(
            1, _respawn, rc, target, token)
        return
    # Ordinary reset/newUser/NPC details; no regeneration or XP path.
    rc.respawn(target)
    _cycle(target)
    target._eden_respawn_timer = None


def _lost(rc, target, witnesses):
    for sess in witnesses:
        if sess in rc.room.players:
            sess.send('lch', lostUser=target.eid)


def _retire(rc, target, due, *, announce=True):
    """Change committed in-memory state before any fallible publication."""
    target.hp, target.alive, target.target = 0, False, None
    target._eden_cycle = object()
    target._eden_reward = None
    target._eden_due = due
    token = target._eden_respawn_token = object()
    rc.room.npcs.pop(target.eid, None)
    if target.aim is not None:
        target.aim.cancel()
        target.aim = None
    loop = asyncio.get_running_loop()
    target._eden_respawn_timer = loop.call_later(max(0, due - time.time()), _respawn, rc, target, token)
    if announce:
        # The same short corpse phase as ordinary mobs, then its figure goes.
        from combat import CORPSE_DELAY
        target._eden_corpse_timer = loop.call_later(
            pace.paced(CORPSE_DELAY), _lost, rc, target, list(rc.room.players))


def _create_ground(fighter, rc, target, reward, sentence):
    """One durable resource and cooldown in the caller's transaction."""
    due = time.time() + respawn_seconds()
    from combat import LOOT_LIFETIME
    expires = time.time() + LOOT_LIFETIME
    row = eden_ground.create(fighter.store, reward, fighter.sess.char_id,
                             sentence['visit'], rc.place, target.cell, expires)
    fighter.store.db.replace('eden_palm_state', ('loc', 'home_cell', 'mob_type', 'respawn_at'),
                             [(rc.room.loc.id, target.home, target.type_id, due)],
                             conflict=('loc', 'home_cell', 'mob_type'))
    return row, due, expires


def _reason(fighter, rc, target, uniq, *, live=False):
    sess = fighter.sess
    if (fighter.dead or sess.closed or sess.on_map or sess.room is not rc.room
            or not is_palm(sess.loc, target)
            or not is_palm(rc.room.loc, target) or not target.present(rc)):
        return "Сбор доступен только у пальмы на плантации Эдем."
    sentence = (eden.assigned(fighter.store, sess.char_id) if live
                else getattr(sess, "eden_sentence", None))
    if not sentence or sentence.get("char_id") != sess.char_id:
        return "Сбор доступен только назначенному на плантацию персонажу."
    row = fighter.store.item(uniq) if uniq is not None else None
    if (row is None or row["char_id"] != sess.char_id or row["type_id"] != TOOL
            or row["slot"] != inventory.PRIMARY or row["brk"] <= 0):
        return "Для сбора возьмите в руки казённый тесак Эдема."
    if not mobs.adjacent(fighter.cell, target.cell, sess.loc):
        return "Подойдите к пальме вплотную."
    return None


def try_attack(fighter, row, target, hexcell):
    """The dedicated tool keeps its harvest swing; other arms use combat."""
    tool = row is not None and row["type_id"] == TOOL
    if not tool:
        return False
    rc = fighter.rc
    if rc is None:
        fighter.ack(inventory.RES_REFUSED)
        return True
    uniq = row["uniq"] if row is not None else None
    why = _reason(fighter, rc, target, uniq)
    if why:
        fighter.ack(inventory.RES_REFUSED)
        fighter.sess.answer(why)
        return True
    if fighter.strike is not None:
        fighter.ack(inventory.RES_OK)
        return True
    si = items.params_of(TOOL)
    cost = si["strike_cost"]
    delay = pace.paced(si["strike_time"] / 1000.0)
    if rc.room.ws and fighter.ap < cost:
        fighter.refuse_no_ap()
        return True
    fighter.settle_walk()
    revision = fighter.begin_action()
    token = object()
    fighter._eden_harvest_pending = token
    fighter.ack(inventory.RES_OK)
    fighter.hostile_action = True
    rc.set_ws(True)
    fighter.schedule_action(revision, "strike", delay,
                            _complete, fighter, rc, target, uniq, cost, token,
                            target._eden_cycle)
    return True


def attack_cycle(rc, target):
    """Only plantation attacks carry a life token into the ordinary timer."""
    if is_palm(getattr(getattr(rc, 'room', None), 'loc', None), target):
        return target._eden_cycle
    return None


def same_cycle(rc, target, cycle):
    return (is_palm(rc.room.loc, target) and target.present(rc)
            and target._eden_cycle is cycle)


def before_native_damage(rc, target):
    """Remember only a palm's pre-impact state for a failed final settlement."""
    if (is_palm(getattr(getattr(rc, 'room', None), 'loc', None), target)
            and target.hp > 0):
        # Native cost/publication can fail after HP reaches zero but before
        # kill(). Keep that cycle's last positive snapshot for a later retry;
        # replacing it with zero would leave an unfinalizable living palm.
        target._eden_native_before_hit = (target.hp, target.sp, target._eden_cycle)


def native_kill(rc, target, fighter):
    """Divert a felled palm before generic kill rewards, loot and respawn.

    The ordinary attack has already paid its ammunition, wear and AP. Only
    the resource/cooldown settlement belongs here: a confirmed rollback
    restores this impact's HP, never the spent shot, and keeps its hidden
    resource. A COMMIT of uncertain outcome must not replay the palm.
    """
    if not is_palm(getattr(getattr(rc, 'room', None), 'loc', None), target):
        return False
    before = getattr(target, '_eden_native_before_hit', None)
    target._eden_native_before_hit = None
    if (not target.present(rc) or target.hp > 0 or before is None
            or before[0] <= 0 or before[2] is not target._eden_cycle):
        return True
    sess = getattr(fighter, 'sess', None)
    ground = due = expires = None
    failed = None
    why = None
    try:
        with storage.atomic(rc.store.db):
            if (sess is None or not getattr(fighter, 'is_player', False)
                    or fighter.dead or sess.closed or sess.on_map
                    or sess.room is not rc.room or not is_palm(sess.loc, target)):
                why = 'Сбор доступен только у пальмы на плантации Эдем.'
            elif not rc.store.lock_quest_character(sess.char_id):
                why = 'Персонаж недоступен для сбора.'
            else:
                sentence = eden.assigned(rc.store, sess.char_id)
                if not sentence or sentence.get('char_id') != sess.char_id:
                    why = 'Сбор доступен только назначенному на плантацию персонажу.'
            if not why:
                if target._eden_reward is None:
                    target._eden_reward = RNG.choice(REWARD_POOL)
                ground, due, expires = _create_ground(
                    fighter, rc, target, target._eden_reward, sentence)
    except Exception as exc:
        failed = exc
    try:
        if isinstance(failed, storage.CommitError):
            log.exception('Eden ordinary-weapon harvest commit uncertain',
                          exc_info=(type(failed), failed, failed.__traceback__))
            _retire(rc, target, due or time.time() + respawn_seconds())
            try:
                if ground is not None:
                    row = rc.store.item(ground['uniq'])
                    if row is not None and row['char_id'] == eden_ground.LOOT_OWNER:
                        if eden_ground.stage(rc, target.cell, row, expires):
                            rc.room.broadcast(('ss_loot', dict(s_status=1, hex=[target.cell])))
            finally:
                if sess is not None:
                    sess.close(force=True)
            return True
        if failed is not None or why:
            if failed is not None:
                log.exception('Eden ordinary-weapon harvest settlement failed',
                              exc_info=(type(failed), failed, failed.__traceback__))
            target.hp, target.sp = before[:2]
            rc.push_vitals(target)
            if sess is not None:
                sess.answer(why or 'Не удалось сохранить добычу. Повторите удар.')
            return True
        _retire(rc, target, due)
        fresh_bag = eden_ground.stage(rc, target.cell, ground, expires)
        rc.room.broadcast(('lch', dict(dead=target.eid)))
        if fresh_bag:
            rc.room.broadcast(('ss_loot', dict(s_status=1, hex=[target.cell])))
        return True
    finally:
        rc.calm()


def _cancel(fighter, why):
    fighter.action_cancelled()
    fighter.c_ap()
    fighter.sess.answer(why)


def _complete(fighter, rc, target, uniq, cost, token, cycle):
    """One validated impact. No ordinary damage/kill/loot/XP path is called."""
    if getattr(fighter, "_eden_harvest_pending", None) is not token:
        return
    if target._eden_cycle is not cycle:
        # Another worker completed this shared palm while this swing waited.
        # An old impact must never count towards the next harvest.
        fighter._eden_harvest_pending = None
        try:
            _cancel(fighter, "Бананы с этой пальмы уже собраны. Начните новый сбор.")
        finally:
            fighter.hostile_action = False
            rc.calm()
        return
    fighter._eden_harvest_pending = None
    sess = fighter.sess
    hit = False
    damage = 0
    reward = None
    why = None
    failed = None
    ground = None
    due = None
    expires = None
    try:
        with storage.atomic(fighter.store.db):
            if not fighter.store.lock_quest_character(sess.char_id):
                why = "Персонаж недоступен для сбора."
            else:
                why = _reason(fighter, rc, target, uniq, live=True)
            if not why and rc.room.ws and fighter.ap < cost:
                why = "Недостаточно очков действия."
            if not why:
                hit = RNG.random() >= MISS_CHANCE
                if hit:
                    si = items.params_of(TOOL)
                    damage = min(target.hp, RNG.randint(si["h_damage_min"], si["h_damage_max"]))
                if hit and damage >= target.hp:
                    # Remember the hidden result across a failed write so a
                    # retry cannot reroll it by provoking a database error.
                    if target._eden_reward is None:
                        target._eden_reward = RNG.choice(REWARD_POOL)
                    reward = target._eden_reward
                    sentence = eden.assigned(fighter.store, sess.char_id)
                    ground, due, expires = _create_ground(fighter, rc, target, reward, sentence)
    except Exception as exc:
        failed = exc
    try:
        if failed is not None:
            log.exception("Eden harvest failed for character %s", sess.char_id,
                          exc_info=(type(failed), failed, failed.__traceback__))
            if isinstance(failed, storage.CommitError):
                # Never replay a possibly committed final cycle. Restore its
                # marker when the authoritative row confirms it, then close.
                _retire(rc, target, due or time.time() + respawn_seconds())
                try:
                    if ground is not None:
                        row = fighter.store.item(ground['uniq'])
                        if row is not None and row['char_id'] == eden_ground.LOOT_OWNER:
                            if eden_ground.stage(rc, target.cell, row, expires):
                                rc.room.broadcast(('ss_loot', dict(s_status=1, hex=[target.cell])))
                finally:
                    sess.close(force=True)
                return
            _cancel(fighter, "Не удалось сохранить добычу. Повторите удар.")
            return
        if why:
            _cancel(fighter, why)
            return
        ended = None
        if hit:
            target.hp -= damage
            ended = dict(hcur=target.hp, hmax=target.hp_max, scur=0, smax=0)
        if rc.room.ws:
            fighter.ap = max(0, fighter.ap - cost)
        if reward is not None:
            # Advance committed state before publishing anything: a lost
            # socket reply cannot leave a paid cycle available for replay.
            _retire(rc, target, due)
            fresh_bag = eden_ground.stage(rc, target.cell, ground, expires)
        if hit:
            rc.room.broadcast(("caHit", dict(id=fighter.eid, target=target.eid,
                                             dmg=damage, sdmg=0, crit=0, recovery_ms=0)))
            rc.room.broadcast(("usrUp", dict(id=target.eid, **ended)))
        else:
            rc.room.broadcast(("caMiss", dict(id=fighter.eid, hex=target.cell,
                                              recovery_ms=0)))
        fighter.c_ap()
        if reward is not None:
            rc.room.broadcast(('lch', dict(dead=target.eid)))
            if fresh_bag:
                rc.room.broadcast(('ss_loot', dict(s_status=1, hex=[target.cell])))
    finally:
        fighter.hostile_action = False
        rc.calm()
