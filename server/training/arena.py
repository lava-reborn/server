"""Training range: arena."""
import asyncio
import combat
import inventory
import items
import mobs
import progression
import rooms
from training import balance as training_balance, effects as training_effects, formulas as training_formulas
from training.character import character


class TrainingFighter(combat.Fighter):
    def prepare_weapon(self, weapon, ammo, row=None, mode=None):
        rules = self.sess.ground.rules
        if rules.simulator_formulas:
            if row is None:
                row = self.sess.inv.in_slot(inventory.PRIMARY)
            return training_formulas.weapon(weapon, self.character(), row, ammo, rules, mode)
        result = rules.weapon(weapon, ammo)
        if rules.combat_v2:
            multiplier = training_balance.intellect_multiplier(self.character())
            result = result._replace(dmin=training_balance.rounded(result.dmin * multiplier),
                                     dmax=training_balance.rounded(result.dmax * multiplier),
                                     sdmin=training_balance.rounded(result.sdmin * multiplier),
                                     sdmax=training_balance.rounded(result.sdmax * multiplier))
        return result

    def prepare_melee(self, bounds, row):
        if self.sess.ground.rules.simulator_formulas:
            return training_formulas.melee(bounds, self.character(), row)
        return bounds

    def healing_multiplier(self, character):
        return training_formulas.healing_multiplier(character) if self.sess.ground.rules.simulator_formulas else 1

    def medicine_cooldown_seconds(self):
        return (training_formulas.cooldown_seconds(self.character()) if self.sess.ground.rules.simulator_formulas
                else combat.battle_medicine.COOLDOWN_SECONDS)

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
        result = super().heal_now(uniq, target, peace_damage, ap_cost)
        ground = self.sess.ground
        if self.sess is ground.enemy and row is not None:
            after = self.store.item(uniq)
            if after is None or after['use_count'] != row['use_count']:
                ground.enemy_heals_left = max(0, ground.enemy_heals_left - 1)
        return result

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
    def ranged_critical(self, shooter, target, weapon, optimal):
        if training_formulas.enabled(shooter):
            return training_formulas.ranged_critical(shooter, target, weapon, optimal)
        return optimal and combat.roll(weapon.crit - target.crit_evade_ranged())

    def melee_critical(self, shooter, target, chance):
        if training_formulas.enabled(shooter):
            return training_formulas.critical(shooter, target, chance)
        return combat.roll(chance)

    def bullet_damage(self, shooter, target, weapon, damage, stamina_damage, critical, stamina_left):
        if training_formulas.enabled(shooter):
            return training_formulas.split(shooter, target, damage, weapon.piercing,
                                           critical, stamina_left, stamina_damage,
                                           rifle=(weapon.spec == combat.SPEC_OF_WEAPON[items.RIFLE]
                                                  if shooter.is_player else
                                                  getattr(shooter, 'training_weapon_class', '') == 'rifle'))
        return combat.split_damage(damage, target.armor(), weapon.piercing, critical, stamina_left, stamina_damage)

    def melee_damage(self, shooter, target, damage, critical, stamina_left):
        if training_formulas.enabled(shooter):
            return training_formulas.split(shooter, target, damage, 1, critical, stamina_left, melee=True)
        return combat.melee_split(damage, critical, stamina_left)

    def prepare_weapon(self, weapon, ammo):
        return self.room.ground.rules.weapon(weapon, ammo)

    def mob_attack(self, mob, target, t):
        weapon = getattr(mob, 'training_weapon', None)
        if mob.stats.ranged and hasattr(mob, 'training_modes'):
            distance = mobs.hex_distance(mob.cell, target.cell, self.room.loc.width)
            selected = training_formulas.mob_mode(mob, distance)
            if selected is None or selected[1] > mob.ap:
                return
            weapon, mob.stats.attack_ap, mob.stats.attack_time = selected
        if weapon is None or not mob.stats.ranged:
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
