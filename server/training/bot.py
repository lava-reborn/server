"""One bounded decision per server combat tick, using ordinary player actions."""
import asyncio
import copy
from types import SimpleNamespace
import accounts
import battle_medicine
import combat
import holdings
import inventory
import items
import mobs
import movement
import progression

PATH_LEGS = 8


def player_info(viewer, actor):
    """Announce a local clone, then its bars, including when its id is reused."""
    import rooms
    from protocol import Str
    viewer.send('userInfo_Player', **rooms.player_info(actor))
    viewer.send('usrUp', **rooms.player_health(actor))
    if actor.ground.ally:
        member = actor.ground.owner.inv.store.clan_member(actor.ground.owner.char_id)
        if member is not None:
            viewer.send('fellow', id=actor.pid, reg=int(member['clan_id']), soc=Str(member['clan_name']))


def local_equipment(viewer, actor, params):
    """Reuse native appearance replies without granting ownership of the copy."""
    view = SimpleNamespace(char_id=None, character=viewer.character, send=viewer.send,
                           char_for_entity=lambda entity: actor.char_id if entity == actor.pid else None)
    reader = inventory.Inventory(view, actor.inv.store)
    reader.shown, reader.acked = viewer.inv.shown, viewer.inv.acked
    reader.ss_get(params)


class LocalOpponent:
    """A disposable native player; only the local cheat command creates one."""
    def __init__(self, owner, ally=False, index=0):
        from training.avatar import clone_class
        from training.runtime import PLAYER_IDS, SERIALS
        import rooms
        self.owner = self.clone = owner
        self.ally = ally
        self.room = owner.room
        self.closed = False
        self.timer = None
        self.deadline = combat.now() + (1800 if ally else 300)
        self.enemy_healing = True
        self.enemy_heals_left = 20
        self.heal_below = 60
        self.rules = SimpleNamespace(ammo_modifiers=True)
        self.store = accounts.Store.temporary()
        try:
            # Flash keeps remote players and their items for the session.
            # One reserved identity/serial range per creator bounds repeat tests.
            identities = getattr(owner.inv.store, '_local_bot_ids', None)
            if identities is None:
                identities = owner.inv.store._local_bot_ids = {}
            key = (owner.char_id, index) if ally else owner.char_id
            if key not in identities:
                if len(identities) >= 1024:
                    raise ValueError('Лимит тестовых персонажей: перезапустите локальный сервер.')
                identities[key] = rooms.player_id(next(PLAYER_IDS)), next(SERIALS)
            pid, serial_base = identities[key]
            self.capture_char = -pid if ally else None
            self.store.db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('items',?)", (serial_base,))
            aid = self.store.db.execute("INSERT INTO accounts(login, hash, created) VALUES(?, ?, ?)",
                                        ('local-bot', '', 0)).lastrowid
            self.store.db.commit()
            name = 'Тестовый союзник %d' % (index + 1) if ally else 'Тестовый противник'
            cid, _ = self.store.create_character(aid, name, owner.active['sex'], owner.active['res'])
            enemy = self.enemy = clone_class(type(owner))(None, 'local-test-bot')
            enemy.ground = self
            enemy.training_pid = pid
            enemy.char_id, enemy.active = cid, dict(self.store.character(cid))
            enemy.send = lambda *args, **kwargs: None
            enemy.send_npc_info = lambda eid: None
            enemy.inv = inventory.Inventory(enemy, self.store)
            enemy.char = copy.deepcopy(owner.character())
            enemy.char.char_id, enemy.char.name = cid, enemy.nick
            enemy.char.afro = enemy.char.gold = 0
            for row in sorted(owner.inv.rows(), key=lambda r: (r['slot'] not in inventory.BODY_SLOTS,
                                                               r['slot'], r['type_id'], r['uniq'])):
                if row['slot'] not in inventory.BODY_SLOTS and row['root'] != items.AMMO:
                    continue
                fields = {key: row[key] for key in accounts.ITEM_FIELDS if key != 'char_id'}
                self.store.create_item(cid, row['type_id'], row['root'], **fields)
            # One finite G pack of the character's tier, in the private store.
            medicine = (7100, 7101, 7102, 7103, 7104, 7105)[min(5, enemy.char.level // 4)]
            enemy.inv.create(medicine)
            enemy.char.set_gear(inventory.gear_bonus(enemy.inv.rows(), enemy.char),
                               inventory.card_repeat(enemy.inv.rows()))
            enemy.char.hp, enemy.char.sp = enemy.char.hp_max, enemy.char.sp_max
            enemy.char.save(self.store)
            enemy.combat = LocalFighter(enemy)
            enemy.loc, enemy.room = owner.loc, self.room
            enemy.pos = movement.get(self.room).free_cell(owner.live_cell())
            enemy.combat.ap = enemy.combat.amax_sent = enemy.char.ap_ceiling
            self.room.enter(enemy)
            # Cached Player entities do not reliably ask getInfo again after
            # death/replacement. Send the same bounded introduction explicitly.
            for viewer in tuple(self.room.players):
                if viewer is not enemy:
                    player_info(viewer, enemy)
            if ally:
                owner.local_test_allies.append(self)
            else:
                owner.local_test_bot = self
            self.timer = asyncio.get_running_loop().call_later(combat.AI_TICK, self.step)
        except Exception:
            self.exit()
            raise

    def combat_stats(self, actor):
        pass

    def step(self):
        self.timer = None
        if (self.closed or self.owner.closed or self.owner.room is not self.room
                or self.owner.combat.dead or self.enemy.combat.dead or combat.now() >= self.deadline):
            self.exit()
            return
        try:
            turn(self)
        except Exception:
            self.exit()
            raise
        self.timer = asyncio.get_running_loop().call_later(combat.AI_TICK, self.step)

    def target(self):
        if not self.ally:
            return self.clone.combat
        rc = self.room.combat
        candidates = [mob for mob in rc.mobs.values()
                      if mob.alive and not mob.away and mob.stats.can_attack
                      and not holdings.defender_friendly(rc, mob, self.enemy.combat)]
        # Clan-base allies attack the capture objective first. The same
        # visibility and friendship filters above still apply to the master.
        base = holdings.base_for(self.enemy.loc.id)
        if base is not None:
            master = next((mob for mob in candidates if mob.type_id == base.boss), None)
            if master is not None:
                return master
        # Else clear escorts first. A hidden master is not a target until
        # the native schedule exposes him; no timer/clearance is bypassed.
        masters = {site.boss for site in holdings.table().sites.values()
                   if site.loc == self.enemy.loc.id}
        masters.update(mob.type_id for mob in candidates if mob.stats.role == 'boss'
                       and holdings.guard_site(self.enemy.loc.id, mob.type_id) is None)
        return min(candidates, key=lambda mob: (mob.type_id in masters,
                   mobs.hex_distance(self.enemy.pos, mob.cell, self.enemy.loc.width), mob.eid), default=None)

    def exit(self, notify=False):
        if self.closed:
            return
        self.closed = True
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        enemy = getattr(self, 'enemy', None)
        if enemy is not None:
            enemy.combat.close()
            enemy.combat.end_duels()
            enemy.inv.close()
            enemy.stop_walk()
            self.room.leave(enemy)
            enemy.room = None
        self.store.close()
        self.room.combat.calm()
        if getattr(self.owner, 'local_test_bot', None) is self:
            self.owner.local_test_bot = None
        allies = getattr(self.owner, 'local_test_allies', [])
        if self in allies:
            allies.remove(self)


class LocalFighter(combat.Fighter):
    """Ordinary combat equations, with no artificial loot or progression."""
    def prepare_weapon(self, weapon, ammo, row=None, mode=None):
        return super().prepare_weapon(weapon, ammo, row)

    def award_xp(self, skill, spec, dealt, target):
        ground = self.sess.ground
        harm = getattr(target, 'capture_harm', None)
        if ground.ally and harm is not None and dealt > 0:
            key = ground.capture_char
            harm[key] = harm.get(key, 0) + dealt

    def heal_now(self, uniq, target, peace_damage=None, ap_cost=0):
        before = self.store.item(uniq)
        super().heal_now(uniq, target, peace_damage, ap_cost)
        after = self.store.item(uniq)
        if before and (after is None or after['use_count'] < before['use_count']
                       or after['count'] < before['count']):
            ground = self.sess.ground
            ground.enemy_heals_left = max(0, ground.enemy_heals_left - 1)

    def credit_xp(self, *args, **kwargs):
        pass

    def count_kill(self, *args):
        pass

    def pvp_kill(self, victim):
        pass

    def die(self, killer):
        self.dead = True
        self.character().hp = 0
        self.cancel_timers()
        self.end_duels()
        self.sess.room.broadcast(('lch', dict(dead=self.eid)))
        asyncio.get_running_loop().call_soon(self.sess.ground.exit)


def modes(ground, gun, distance):
    """At most three small estimates; the actual shot still uses Fighter."""
    enemy = ground.enemy
    si = items.params_of(gun['type_id'])
    ammo = items.params_of(gun['ammo_type']) or {}
    ch = enemy.character()
    spec = combat.SPEC_OF_WEAPON.get(si.get('weapon_type', items.PISTOL))
    factor = combat.spread_factor(ch.skill_level(progression.SHOOTING), combat.spec_or_zero(ch, spec))
    choices = []
    for mode, burst in enumerate(si['fire_mods']):
        if not burst or si['fire_costs'][mode] > enemy.combat.ap:
            continue
        shots, _rounds = combat.pull(si, mode, gun['ammo_count'])
        if not shots:
            continue
        weapon = combat.Weapon(shots, si['h_damage_min'][mode], si['h_damage_max'][mode],
            si['opt_range'][mode], si['end_opt_range'][mode], si['max_range'][mode],
            ammo.get('piercing', 1), combat.cone_of(factor, si['target_size'][mode],
                ammo.get('acc_mod', 1) or 1, si['max_range'][mode]), 0,
            progression.SHOOTING, spec)
        weapon = enemy.combat.prepare_weapon(weapon, ammo, dict(gun, cur_mode=mode), mode)
        if distance > weapon.max_range:
            continue
        hit = combat.hit_probability(weapon.cone, distance, weapon.hit_cap)
        # Expected HP per time spent aiming/firing; no RNG or simulated shots.
        aim = si['fire_times'][mode] / 1000
        duration = max(.1, aim + combat.action_animation.duration_ms(enemy, si, shots, aimed_for=aim) / 1000)
        score = shots * (weapon.dmin + weapon.dmax) / 2 * hit / duration
        choices.append((score, -si['fire_costs'][mode], -mode, mode))
    return max(choices)[3] if choices else None


def heal(ground):
    enemy = ground.enemy
    if (not ground.enemy_healing or ground.enemy_heals_left <= 0
            or battle_medicine.remaining_ms(ground.store, enemy.char_id, combat.now())):
        return False
    vitals = enemy.character().vitals()
    threshold = ground.heal_below / 100
    hp_low = vitals['hcur'] < vitals['hmax'] * threshold
    sp_low = vitals['scur'] < vitals['smax'] * threshold
    if not (hp_low or sp_low):
        return False
    for row in enemy.inv.rows():
        if row['root'] != items.HEAL or not items.battle_medicine(row['type_id']):
            continue
        si = items.params_of(row['type_id'])
        useful = (hp_low and si.get('max_h_rest', 0) > 0) or (sp_low and si.get('max_st_rest', 0) > 0)
        if useful and enemy.combat.ap >= si['heal_cost']:
            enemy.combat.use_heal(dict(obj=inventory.oid_of(row)), inventory.USE_IDLE)
            if enemy.combat.healing is not None:
                return True
    return False


def turn(ground):
    enemy = ground.enemy
    fighter = enemy.combat
    if (fighter.acting() or fighter.dead or fighter.reloading is not None
            or fighter.recovering() or enemy.walk is not None):
        return
    if heal(ground):
        return
    gun = enemy.inv.in_slot(inventory.PRIMARY)
    if gun and gun['root'] == items.FIRE_ARM and not gun['ammo_count']:
        si = items.params_of(gun['type_id'])
        if fighter.ap < si['reload_cost']:
            return
        stack = next((row for row in enemy.inv.rows() if row['root'] == items.AMMO
                      and row['type_id'] in si['comp_array']), None)
        if stack:
            enemy.inv.use_load(dict(obj=inventory.oid_of(gun), target=inventory.oid_of(stack)))
        return
    target = ground.target() if isinstance(ground, LocalOpponent) else ground.clone.combat
    if target is None:
        return
    loc = enemy.loc
    distance = mobs.hex_distance(enemy.pos, target.cell, loc.width)
    firearm = gun and gun['root'] == items.FIRE_ARM
    mode = modes(ground, gun, distance) if firearm else None
    if firearm:
        si = items.params_of(gun['type_id'])
        if mode is not None and mode != gun['cur_mode']:
            enemy.inv.use_mode(dict(obj=inventory.oid_of(gun), target=format(mode, 'x')))
            gun = enemy.inv.in_slot(inventory.PRIMARY)
        ammo = items.params_of(gun['ammo_type']) or {}
        reach = max(r for r, burst in zip(si['max_range'], si['fire_mods']) if burst)
        if ground.rules.ammo_modifiers:
            reach *= ammo.get('range_mod', 1)
    else:
        reach = 1
    in_reach = distance <= reach if firearm else mobs.adjacent(enemy.pos, target.cell, loc)
    if not in_reach or combat.shot_wall(loc, enemy.pos, target.cell) is not None:
        target_cell = target.cell
        def goal(cell):
            reachable = (0 < mobs.hex_distance(cell, target_cell, loc.width) <= reach if firearm
                         else mobs.adjacent(cell, target_cell, loc))
            return reachable and combat.shot_wall(loc, cell, target_cell) is None
        blocked = movement.get(ground.room).occupied(exclude=enemy)
        path = mobs.find_path(loc, enemy.pos, goal, blocked, toward=target_cell)
        if path and len(path) > 1:
            # One short continuous route, not a one-cell start/stop per AI tick.
            enemy.move_in_location(dict(path=path[:PATH_LEGS + 1]))
        return
    if not firearm or mode is not None:
        fighter.use_fire(dict(obj=inventory.oid_of(gun) if gun else '0', target='1%08x' % target.eid))
