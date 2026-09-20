"""Combat: shooting, striking, being shot, dying, looting -- and the frames.

The client is a renderer. It computes no hit, no damage and no crit: every
number arrives ready (recon/analysis/combat.md), and what it does insist on is
the ORDER of the frames, because its state machine is built around it:

    cmdAck;res=0                      exactly one per ss_use, before anything else
    faAim;id;ang;num_shots            the figure raises the gun; the aim bar starts
    N x ( faShot;id;status=1          a bullet leaves; AP are charged once per burst
          faHit | faMiss | faWall     what it did, only inside the pair
          faShot;id;status=0 )        the pair closes; on the Nth the damage lands
    usrUp;id=<target>                 absolute HP/SP, after the last pair
    c_ap;ap=<N>                       absolute AP of the shooter -- autofire waits for it
    ss_di_firearm;ammo_count          the magazine

Location.as keeps ONE curFireEvent for the whole scene, so the N pairs of one
shooter go out back to back with nothing else in between; only the aim pause
before them may interleave with other traffic. The count of pairs must equal
num_shots or the walker's counter never reaches zero and the next burst
inherits a broken event. Strikes are one frame: caHit or caMiss.

The formulas are the wiki's "Игромеханика" (the developers' own design
document) where the client shows nothing, and the client's own card
(gpui/CharInterface.as, mirrored in progression.py) where it does, so that
the crit chance a player reads off the card is the one the server rolls.
Mob figures come from data/mob_curves.json through mobs.py.

Two objects: a Fighter per session (action points, timers, the loot window,
death), and a RoomCombat per room (war state, the AP clock, the mobs and
their brains, the corpses and bags). Both are reached from server.Session
through a handful of hooks; nothing here writes to the database behind the
Character's back, and HP travels only as usrUp.
"""
import asyncio
import logging
import os
import random
from collections import namedtuple

import inventory
import items
import mobs
import progression
import quests
import rooms
import world
from protocol import BigUInt

log = logging.getLogger("lava")

# StuffManager.SESSION_LOOT: the s_type of a bag on the ground.
SESSION_LOOT = 0

# Seconds after a shot or a strike during which chWorld is refused with 39
# ("Вы не можете выйти из локации в режиме боя..."). Sent to the client in
# the constants frame as leave_combat_timeout, so the message it shows
# quotes the same number.
LEAVE_COMBAT_TIMEOUT = int(os.environ.get("LAVA_LEAVE_COMBAT", "30"))
# A dead mob lies for this long before lch;lostUser fades it and the bag
# appears; then it comes back after RESPAWN_DELAY. The bag stays LOOT_LIFETIME.
CORPSE_DELAY = 2.5
RESPAWN_DELAY = float(os.environ.get("LAVA_RESPAWN", "45"))
LOOT_LIFETIME = 120.0
# APManager.dt: the client adds aspd to the bar every 600 ms while ws=1, and
# the server keeps the same clock so c_ap rarely has to correct anything.
AP_TICK = 0.6
AI_TICK = 0.4
REGEN_PERIOD = 60.0
# A bare-handed strike costs 5 AP (PersEquip.as:86, wiki).
FIST_AP = 5
# ErrorReport codes beyond inventory's, and the resurrection prices
# RegenerationInterface shows (5 gold / 500 afro; free after 15 s).
#
# The gold figure stays as the window writes it. Unlike the training window,
# which only prints its price, this one compares: it greys the button while
# attributes.gold < GOLD_COST, and attributes.gold is the purse in hundredths
# of an ounce. So its 5 is five hundredths, and the server charges what the
# button lets the player press. (Training's prices are whole ounces and are
# scaled in progression.SPEC_COST; the two windows simply disagree.)
RES_NO_LEAVE = 39
RES_TOO_FAR = progression.ERR_TOO_FAR
# The three buttons of the regeneration window, in its own numbering
# (RegenerationInterface.RESURECT_FREE/GOLD/AFRO).
RES_FREE, RES_GOLD, RES_AFRO = 0, 1, 2
# GOLD_COST=5 is checked against attributes.gold, which is the same number
# userInfo_Player sent: hundredths of an ounce, the whole part of which the
# purse panel shows (MoneyPan.set value divides by 100). payAfro checks 500,
# and at the gold_to_afro_rate of 100 the server's own constants frame
# carries, the two buttons are one price in two currencies.
RESURRECT_GOLD = 5
RESURRECT_AFRO = 500
# RegenerationInterface.timePause: the window counts fifteen seconds down and
# then presses the free button itself, so free costs the wait (see resurrect).
RESURRECT_WAIT = float(os.environ.get("LAVA_RESURRECT_WAIT", "15"))
# What a free resurrection wakes up with, as a share of the maximum. Designed:
# the client says nothing about how whole a body comes back.
FREE_HP_SHARE = 0.25
# char_id of item rows lying in a bag on the ground: no character has id 0.
LOOT_OWNER = 0

# What the server still accepts from a client it knows to be dead. Two
# families, and neither of them moves anything in the world:
#
#   the way in and the way out, because DEAD_STATE is entered after lenter,
#   never before it. A character that logged out dead selects, loads and
#   walks into a location alive as far as the client is concerned, and only
#   when Master.lenter (or gmap) reads persInfo;death does the regeneration
#   window open. Refusing lenter here would leave it standing in nowhere;
#
#   the pipelined requests, each of which carries a window on the client's
#   side that only an answer reopens (PROTOCOL 7): a dropped ss_get leaves
#   its ss_ack queue waiting for ever, and a dropped q_si wedges the journal.
#
# Everything else is an action, and the client's own filter
# (FilterManager.createDSFilter) never sends one while dead.
DEAD_PASSES = frozenset((
    "hello", "login", "logout", "selPers", "newPers", "actPlayer", "lenter",
    "resurrect",
    "getInfo", "rp_get_info", "q_list", "q_si", "q_di", "q_status",
    "ss_get", "ss_get_si", "ss_get_di", "ss_get_s_si", "e_get_si", "e_get_di",
))

# The specialisation each firearm class trains (PersAttributes.specMatrix,
# CharInterface.showKrit): pistols 2, shotguns 3, assault 4, rifles 5,
# machine guns 6, SMGs 7. Fists train 0, blades 1. Medicine: first aid 8,
# surgery 9.
SPEC_OF_WEAPON = {items.PISTOL: 2, items.SHOTGUN: 3, items.ASSAULT: 4,
                  items.RIFLE: 5, items.MACHINEGUN: 6, items.SMG: 7}
SPEC_FIST, SPEC_BLADE, SPEC_FIRST_AID, SPEC_SURGERY = 0, 1, 8, 9

# One generator, seedable for a replayable session (LAVA_SEED).
RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

# What one trigger pull is resolved with. hit and crit are chances in
# percent before the target's evasion; opt_lo..opt_hi is the optimal band
# where crits are possible and the damage floor rises (wiki); skill and spec
# say where the experience goes (None for a mob).
Weapon = namedtuple("Weapon", "num_shots dmin dmax opt_lo opt_hi max_range "
                              "piercing hit crit skill spec")


def now():
    return asyncio.get_running_loop().time()


def roll(chance):
    """The wiki's test: a number from 1 to 100, at or under the chance."""
    return RNG.randint(1, 100) <= chance


def drops_on_death(type_id):
    """Whether the wiki marks this type as one that falls off a corpse.

    The articles' "Шанс выпадения при смерти" reached data/items_wiki.json as
    drop_on_death, and it is a flag, not a percentage: of the 644 types whose
    article tabulates it, 88 carry a 1. It is one of the wiki extras
    items._overlay deliberately keeps off the wire, so it is read from the
    raw table rather than from params_of.
    """
    rec = items.wiki().get(int(type_id))
    return bool(rec and rec.get("drop_on_death"))


def parse_target(value):
    """(target type, id) from the ss_use target BigUINT: one hex digit of
    type, then the id padded to eight (MDString.createBigUINT). 1 is an
    entity, 0 a hex. None, None for anything else."""
    text = str(value or "").strip().lower()
    if not text:
        return None, None
    try:
        return int(text[:-8] or "0", 16), int(text[-8:], 16)
    except ValueError:
        return None, None


# --- the formulas ---------------------------------------------------------

def spec_or_zero(ch, idx):
    """An unlearned specialisation counts as 0 in a chance, not as -1."""
    return max(0, ch.spec_level(idx)) if idx is not None else 0


def ranged_hit_chance(ch, spec):
    """Wiki: 49 + skill * 1.25 + specialisation * 5, applied to shooting."""
    return 49 + 1.25 * ch.skill_level(progression.SHOOTING) + 5 * spec_or_zero(ch, spec)


def melee_hit_chance(ch, spec):
    return 49 + 1.25 * ch.skill_level(progression.MELEE) + 5 * spec_or_zero(ch, spec)


def ranged_evade(ch):
    """The wiki gives no dodge against bullets (the design simulates the
    flight instead); this is the shape of its evasion formulas at half
    weight, so an agile character is harder to hit but never untouchable."""
    return (ch.attr(progression.AGILITY) + ch.attr(progression.PERCEPTION)) / 2.0 \
        + ch.skill_level(progression.SHOOTING) / 4.0


def melee_crit(ch, spec):
    """Wiki: agility + melee * 2.5 + specialisation * 6."""
    return ch.attr(progression.AGILITY) + 2.5 * ch.skill_level(progression.MELEE) \
        + 6 * spec_or_zero(ch, spec)


def melee_crit_evade(ch):
    """Wiki: (agility + perception) / 2 + melee / 4 + specialisation."""
    return (ch.attr(progression.AGILITY) + ch.attr(progression.PERCEPTION)) / 2.0 \
        + ch.skill_level(progression.MELEE) / 4.0 + spec_or_zero(ch, SPEC_FIST)


def split_damage(dmg, armor, piercing, crit, sp_left):
    """(to HP, to SP) of a bullet, wiki "Броня": the armour class less the
    round's piercing is absorbed by stamina, the rest hurts; what stamina
    cannot absorb spills into HP. A crit ignores armour entirely."""
    if crit:
        return dmg, 0
    comp = max(0, int(armor - piercing))
    s = min(dmg, comp)
    h = dmg - s
    if s > sp_left:
        h += s - max(0, sp_left)
        s = max(0, sp_left)
    return h, s


def melee_split(dmg, crit, sp_left):
    """A blow lands on stamina first and only the remainder on HP (wiki
    "Ближний бой"); a crit goes straight to HP."""
    if crit:
        return dmg, 0
    s = min(dmg, max(0, sp_left))
    return dmg - s, s


def miss_at(rx, ry):
    """faMiss lands near the aim point: x/y are in hex units (rx, ry), which
    DisplayLocScene scales by the cell size itself."""
    return dict(x=round(rx + RNG.uniform(-0.7, 0.7), 2),
                y=round(ry + RNG.uniform(-0.7, 0.7), 2))


# --- a bag on the ground --------------------------------------------------

class LootBag:
    def __init__(self, cell, uniqs):
        self.cell = cell
        self.uniqs = list(uniqs)
        self.expiry = None


# --- one player -----------------------------------------------------------

class Fighter:
    """The combat side of one session. Owned by server.Session as .combat."""
    is_player = True

    def __init__(self, sess):
        self.sess = sess
        self.ap = 0
        # loop time of the last shot or strike given or taken. This is what
        # keeps the room at war (RoomCombat.hostilities), and nothing else:
        # it says a fight happened here, not that anyone is after this player.
        self.last_hostile = -1e9
        # loop time of the last blow exchanged with another player, either
        # way round. Leaving is what this one governs -- see in_combat.
        self.last_pvp = -1e9
        self.dead = False
        # loop time of the death the character is still lying in, for the
        # free resurrection's wait (RegenerationInterface.timePause)
        self.died_at = -1e9
        self.aim = None         # TimerHandle: a burst waiting for fire_times
        self.strike = None      # TimerHandle: a swing waiting for strike_time
        self.healing = None     # TimerHandle: a heal waiting for heal_time
        self.loot = None        # cell of the bag the loot window is open on
        self.regen_at = 0.0

    # --- plumbing ------------------------------------------------------------
    @property
    def store(self):
        return self.sess.inv.store

    @property
    def rc(self):
        """The room's combat state, or None off any room (the map)."""
        room = self.sess.room
        return room_combat(room, self.store) if room is not None else None

    def ack(self, res):
        self.sess.send("cmdAck", res=res)

    def character(self):
        return self.sess.character()

    # --- as an entity in a fight -------------------------------------------
    @property
    def eid(self):
        return self.sess.pid

    @property
    def cell(self):
        return self.sess.pos

    @property
    def alive(self):
        return not self.dead

    @property
    def level(self):
        return self.character().level

    @property
    def hp_max(self):
        return self.character().hp_max

    @property
    def ap_max(self):
        return self.character().ap_max

    def vitals(self):
        return self.character().vitals()

    def sp_now(self):
        return self.vitals()["scur"]

    def apply_damage(self, hdmg, sdmg):
        """Take a hit. Through the Character, whose save() writes hp/sp back
        on logout; anything written past it would be undone."""
        ch = self.character()
        v = ch.vitals()
        ch.hp = max(0, v["hcur"] - hdmg)
        ch.sp = max(0, v["scur"] - sdmg)
        return ch.hp <= 0

    def dodge_melee(self):
        return progression.melee_evade(self.character())

    def dodge_ranged(self):
        return ranged_evade(self.character())

    def crit_evade_melee(self):
        return melee_crit_evade(self.character())

    def crit_evade_ranged(self):
        """The card's anti-crit for the weapon in hand (CharInterface.showKrit);
        with no firearm, the pistol row, the one the card would show first."""
        gun = self.primary()
        wt = items.PISTOL
        if gun is not None and gun["root"] == items.FIRE_ARM:
            wt = (items.params_of(gun["type_id"]) or {}).get("weapon_type", items.PISTOL)
        pair = progression.crit_chance(self.character(), wt)
        return pair[1] if pair else 0

    def armor(self):
        """The card's armour: base plus armor_class over the six clothing
        slots (CharInterface.showArmorLevel)."""
        worn = sum((items.params_of(r["type_id"]) or {}).get("armor_class", 0)
                   for r in self.sess.inv.rows() if r["slot"] in inventory.WEAR_SLOTS)
        return progression.armor_class(self.character(), worn)

    def present(self, rc):
        return not self.dead and self.sess in rc.room.players

    def primary(self):
        return self.sess.inv.in_slot(inventory.PRIMARY)

    # --- session hooks -----------------------------------------------------
    def entered(self):
        """After Room.enter: start the room's clock and hand the client the
        empty effect list it would otherwise never hear about."""
        rc = self.rc
        if rc is None:
            return
        self.ap = self.ap_max
        self.regen_at = now() + REGEN_PERIOD
        rc.player_entered(self)
        # A full replacement of the list (EffectManager.e_list); empty is a
        # list too, and mobi_id=0 resolves to the gamer (PlayerRegister).
        self.sess.send("e_list", mobi_id=0, effects=[])
        # Corpses, both ways round. Someone who logged out dead walks in as
        # one, and the figure the room has just built for them has to fall
        # over (DisplayLocScene.dead); anyone already lying here has to be a
        # corpse on the newcomer's screen too. Never about oneself:
        # Resurrector.lch reads lch;dead=0 as "open the regeneration window",
        # and that window is already up from persInfo;death.
        if self.dead:
            self.sess.room.broadcast(("lch", dict(dead=self.eid)),
                                     exclude=self.sess)
        for other in rc.fighters():
            if other is not self and other.dead:
                self.sess.send("lch", dead=other.eid)

    def left(self):
        """Before Room.leave: whatever was in flight aims at nothing now."""
        self.cancel_timers()
        self.loot = None

    def moved(self, cells):
        """The player walked. The client drops its aim bar and autofire on
        its own userMove (WeaponPan.breakTimeBar, AutoCommandManager), and
        the wiki says running cancels the aim at no cost, so the burst is
        cancelled here and nothing is charged. Steps cost 1 AP each while
        the room is at war, which the client also subtracts by itself
        (APManager.gamerMove); c_ap after the next action corrects drift."""
        self.cancel_aim()
        rc = self.rc
        if rc is not None and rc.room.ws:
            self.ap = max(0, self.ap - max(0, len(cells) - 1))

    def cancel_aim(self):
        for name in ("aim", "strike"):
            handle = getattr(self, name)
            if handle is not None:
                handle.cancel()
                setattr(self, name, None)

    def cancel_timers(self):
        self.cancel_aim()
        if self.healing is not None:
            self.healing.cancel()
            self.healing = None

    def restore(self, row):
        """A character has just been loaded: take its death back up.

        The flag is the characters row's (accounts.CHARACTER_COLUMNS), not
        the Character's, and this is the one place it comes back out of the
        database. The client learns of it from persInfo;death, sent before
        the selection, and raises the regeneration window by itself the
        moment it is standing somewhere (Master.lenter/gmap).

        The wait before a free resurrection starts afresh here rather than
        surviving the logout: the window's own countdown starts when it
        opens, a moment after this, so the server's is never the one that
        refuses.
        """
        self.dead = bool(row is not None and row["death"])
        self.died_at = now() if self.dead else -1e9

    def close(self):
        """Connection gone. Must not raise: Session.close runs this before
        the position and the character are written.

        The dead stay dead: characters.death was written in die(), and the
        Character carries hp=0 out with it, so the next login finds a corpse
        where a corpse was left.
        """
        try:
            self.cancel_timers()
            self.loot = None
        except Exception:
            log.exception("  !!    combat close failed")

    def blocks(self, cmd, wants_ack):
        """The dead filter (FilterManager.createDSFilter): the client sends
        nothing but resurrect while dead, so an action that arrives anyway
        came from a modified one and is refused -- with an ack where one is
        owed, so the queue stays in step. What still goes through, and why,
        is DEAD_PASSES."""
        if not self.dead or cmd in DEAD_PASSES:
            return False
        if wants_ack:
            self.ack(inventory.RES_REFUSED)
        return True

    def hunted(self):
        """Whether any living creature here is currently after this player."""
        rc = self.rc
        if rc is None:
            return False
        return any(m.alive and m.target is self for m in rc.mobs.values())

    def in_combat(self):
        """Whether this player is barred from walking out.

        The question is who is after you, not whether you fired. A shot that
        nothing answered -- a miss at a mob that never woke, a creature killed
        outright, a burst into the scenery -- leaves the wasteland as quiet as
        it was, and standing in it for thirty seconds is a punishment for
        nothing. What holds a player is a mob that has taken them as its
        target, or a fight with another player: there leaving at will would
        make every exchange end the moment it started going badly, so both
        sides are held, the one who struck as much as the one who was struck.

        Asked and not answered, for a caller that has already acknowledged the
        command in hand (/home) and must not ack twice.
        """
        if self.sess.on_map:
            return False
        if now() - self.last_pvp < LEAVE_COMBAT_TIMEOUT:
            return True
        return self.hunted()

    def refuse_leave(self):
        """chWorld inside leave_combat_timeout of the last shot or strike:
        Master.changeWorldAck words res=39 with that timeout."""
        if not self.in_combat():
            return False
        self.ack(RES_NO_LEAVE)
        return True

    def c_ap(self):
        self.sess.send("c_ap", ap=int(self.ap))

    # --- mobs as the client sees them ----------------------------------------
    def mob_info(self, npc_id):
        """Extra userInfo keys for an inhabitant that is a mob: its level,
        which paints the coloured frame over its head (CharInfo)."""
        rc = self.rc
        mob = rc.mobs.get(npc_id) if rc is not None else None
        return dict(lvl=mob.level) if mob is not None else {}

    def after_npc_info(self, npc_id):
        """usrUp right behind a mob's userInfo, or the bar over its head
        is drawn against maxHealth = 1200 (PersAttributes.as:55)."""
        rc = self.rc
        mob = rc.mobs.get(npc_id) if rc is not None else None
        if mob is not None:
            self.sess.send("usrUp", id=mob.eid, **mob.vitals())

    def ss_get(self, p):
        """ss_get;target=<mob>;slot=<mask>: the creature's clothes and hands.

        Mob.as asks with mask 3 the moment the entity is built, and
        PersEquip.ss_ack splices six wear slots then two hands off the list
        whatever came, so the shape is fixed; the weapon in primary is what
        picks the animation set. True when answered here."""
        target = int(p.get("target", 0) or 0)
        rc = self.rc
        mob = rc.mobs.get(target) if rc is not None and target else None
        if mob is None:
            return False
        mask = int(p.get("slot", 0) or 0)
        weapon = mob.weapon_oid()
        out = []
        if mask & inventory.MASK_WEAR:
            out += [inventory.EMPTY] * len(inventory.WEAR_SLOTS)
        if mask & inventory.MASK_HANDS:
            out += [BigUInt(weapon) if weapon else inventory.EMPTY, inventory.EMPTY]
        if mask & inventory.MASK_SESSION:
            out.append(inventory.EMPTY)
        self.sess.send("ss_ack", o_list=out)
        return True

    def ss_get_di(self, p):
        """Dynamic info of a virtual instance (a mob's weapon). True when
        the id was one of ours; the window of five needs the answer."""
        parsed = inventory.parse_oid(p.get("obj"))
        if not parsed:
            return False
        uniq, type_id, root = parsed
        di = mobs.virtual_di(uniq, type_id, root)
        if di is None:
            return False
        cmd, fields = di
        self.sess.send(cmd, obj=BigUInt(inventory.oid(uniq, type_id, root)), **fields)
        return True

    # --- ss_use 16 / 2 / 4 -------------------------------------------------
    def ss_use(self, kind, p):
        """The combat bits of ss_use; inventory.py keeps load/unload/mode/
        delete. One cmdAck whatever happens, before any fa*/ca* frame."""
        if kind == inventory.USE_FIRE:
            self.use_fire(p)
        elif kind in (inventory.USE_IDLE, inventory.USE_TARGET):
            self.use_heal(p, kind)
        else:
            self.ack(inventory.RES_REFUSED)

    def use_fire(self, p):
        """type=16: a shot with the primary firearm, or a strike with a blade
        or the bare fist (obj=x0, ItemActivator.strike)."""
        sess = self.sess
        rc = self.rc
        if rc is None or sess.on_map or self.dead:
            self.ack(inventory.RES_REFUSED)
            return
        if not sess.loc.war:
            # The client refuses this itself in a peaceful location
            # (ItemActivator.fire: locInfo.battle); a modified one is refused here.
            self.ack(inventory.RES_REFUSED)
            return
        obj = str(p.get("obj", "0") or "0").strip().lower()
        row = None if obj in ("", "0") else sess.inv.find(obj)
        if obj not in ("", "0") and row is None:
            self.ack(inventory.RES_NOT_FOUND)
            return
        ttype, tid = parse_target(p.get("target"))
        if ttype is None:
            self.ack(inventory.RES_REFUSED)
            return
        target = hexcell = None
        if ttype == 1:
            target = rc.actor(tid)
            if target is None:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if target is self or (target.is_player and not sess.loc.pvp):
                self.ack(inventory.RES_REFUSED)
                return
        else:
            if not (0 <= tid < sess.loc.width * sess.loc.height):
                self.ack(inventory.RES_NOT_FOUND)
                return
            hexcell = tid
        if self.aim is not None or self.strike is not None:
            self.ack(inventory.RES_NOT_READY)
            return
        if row is None or row["root"] == items.COLD_ARM:
            self.strike_with(row, target, hexcell)
            return
        if row["root"] != items.FIRE_ARM or row["slot"] != inventory.PRIMARY:
            self.ack(inventory.RES_NOT_FOUND)
            return
        si = items.params_of(row["type_id"]) or {}
        mode = row["cur_mode"]
        modes = si.get("fire_mods", [])
        if not (0 <= mode < len(modes)) or not modes[mode]:
            self.ack(inventory.RES_REFUSED)
            return
        if row["ammo_count"] <= 0:
            self.ack(inventory.RES_NO_AMMO)
            return
        if row["brk"] <= 0:
            self.ack(inventory.RES_BROKEN)
            return
        aim_cell = target.cell if target is not None else hexcell
        width = sess.loc.width
        if mobs.hex_distance(sess.pos, aim_cell, width) > si["max_range"][mode]:
            self.ack(RES_TOO_FAR)
            return
        cost = si["fire_costs"][mode]
        if rc.room.ws and self.ap < cost:
            self.ack(inventory.RES_NO_AP)
            return
        self.ack(inventory.RES_OK)
        # Raising the gun is already hostile: the exit timer runs from here,
        # and the room must not fall back to ws=0 while the aim bar runs.
        self.last_hostile = now()
        rc.set_ws(True)
        ch = self.character()
        wt = si.get("weapon_type", items.PISTOL)
        spec = SPEC_OF_WEAPON.get(wt)
        crit = progression.crit_chance(ch, wt)
        ammo_si = items.params_of(row["ammo_type"]) or {}
        weapon = Weapon(num_shots=min(modes[mode], row["ammo_count"]),
                        dmin=si["h_damage_min"][mode], dmax=si["h_damage_max"][mode],
                        opt_lo=si["opt_range"][mode], opt_hi=si["end_opt_range"][mode],
                        max_range=si["max_range"][mode],
                        piercing=ammo_si.get("piercing", 1),
                        hit=ranged_hit_chance(ch, spec), crit=crit[0] if crit else 0,
                        skill=progression.SHOOTING, spec=spec)
        rc.room.broadcast(("faAim", dict(id=self.eid,
                                         ang=mobs.direction(sess.pos, aim_cell, width),
                                         num_shots=weapon.num_shots)))
        # The aim bar on the client runs fire_times[cur_mode] from faAim to
        # the first faShot (WeaponPan.aim); the burst waits the same.
        self.aim = asyncio.get_running_loop().call_later(
            si.get("fire_times", [700])[mode] / 1000.0,
            self.fire_now, row["uniq"], target, hexcell, weapon, cost)

    def fire_now(self, uniq, target, hexcell, weapon, cost):
        """The burst, after the aim. num_shots pairs go out come what may:
        the client has already counted them from faAim."""
        self.aim = None
        rc = self.rc
        if rc is None or self.dead:
            return
        row = self.store.item(uniq)
        if row is not None and row["char_id"] != self.sess.char_id:
            row = None
        live = min(weapon.num_shots, row["ammo_count"]) if row else 0
        pool = target.hp if target is not None and not target.is_player else 0
        h, s, hits, killed = rc.burst(self, target, hexcell, weapon, live)
        if row is not None:
            self.store.update_item(uniq, ammo_count=row["ammo_count"] - live)
        if rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.c_ap()
        if row is not None:
            self.sess.inv.push_di(self.store.item(uniq))
        if target is not None and not target.is_player and h > 0:
            self.award_xp(weapon.skill, weapon.spec, min(h, pool) * target.stats.xp_mult,
                          target.level)
        rc.after_hostile(self, target)
        if killed:
            rc.kill(target, self)

    def strike_with(self, row, target, hexcell):
        """A swing: fist (5 AP, damage from strength) or the blade in hand."""
        sess = self.sess
        rc = self.rc
        ch = self.character()
        strength = ch.attr(progression.STRENGTH)
        if row is None:
            cost, delay, spec = FIST_AP, 0.0, SPEC_FIST
            dmin, dmax = int(strength / 2), int(strength * 1.5)
        else:
            if row["slot"] != inventory.PRIMARY:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if row["brk"] <= 0:
                self.ack(inventory.RES_BROKEN)
                return
            si = items.params_of(row["type_id"]) or {}
            cost, spec = si.get("strike_cost", 8), SPEC_BLADE
            delay = si.get("strike_time", 0) / 1000.0
            dmin = si.get("h_damage_min", 1) + strength
            dmax = si.get("h_damage_max", 1) + strength
        if rc.room.ws and self.ap < cost:
            self.ack(inventory.RES_NO_AP)
            return
        self.ack(inventory.RES_OK)
        self.last_hostile = now()
        rc.set_ws(True)
        args = (target, hexcell, (max(1, dmin), max(1, dmax)), spec, cost)
        if delay:
            # The strike bar runs strike_time from the send to caHit/caMiss
            # (WeaponPan.strike); a fist has none and lands at once.
            self.strike = asyncio.get_running_loop().call_later(
                delay, self.strike_now, *args)
        else:
            self.strike_now(*args)

    def strike_now(self, target, hexcell, dmg_range, spec, cost):
        self.strike = None
        rc = self.rc
        if rc is None or self.dead:
            return
        sess = self.sess
        ch = self.character()
        loc = sess.loc
        aim_cell = target.cell if target is not None else hexcell
        killed = False
        hit = (target is not None and target.present(rc)
               and mobs.adjacent(sess.pos, target.cell, loc)
               and roll(melee_hit_chance(ch, spec) - target.dodge_melee()))
        if hit:
            crit = roll(melee_crit(ch, spec) - target.crit_evade_melee())
            dmg = RNG.randint(dmg_range[0], dmg_range[1])
            h, s = melee_split(dmg, crit, target.sp_now())
            pool = target.hp if not target.is_player else 0
            rc.room.broadcast(("caHit", dict(id=self.eid, target=target.eid,
                                             dmg=h, sdmg=s, crit=int(crit))))
            killed = target.apply_damage(h, s)
            rc.push_vitals(target)
        else:
            # Not adjacent, or the roll failed: the wiki makes no roll for a
            # non-neighbour, and either way the client wants a caMiss on a hex.
            rc.room.broadcast(("caMiss", dict(id=self.eid, hex=aim_cell)))
        if rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.c_ap()
        if hit and not target.is_player and h > 0:
            self.award_xp(progression.MELEE, spec, min(h, pool) * target.stats.xp_mult,
                          target.level)
        rc.after_hostile(self, target)
        if killed:
            rc.kill(target, self)

    # --- healing: ss_use 2 (self) and 4 (another) -----------------------------
    def use_heal(self, p, kind):
        """A heal item on oneself or a neighbour. cmdAck at once (the client
        charges heal_cost on it), the effect after heal_time as an absolute
        heal;hp;sp, then the item's use_count or its removal."""
        sess = self.sess
        rc = self.rc
        row = sess.inv.find(p.get("obj"))
        if row is None or row["root"] != items.HEAL:
            self.ack(inventory.RES_NOT_FOUND)
            return
        if row["use_count"] <= 0:
            self.ack(inventory.RES_NO_ITEM)
            return
        target = self
        if kind == inventory.USE_TARGET and p.get("target") is not None:
            ttype, tid = parse_target(p.get("target"))
            other = rc.actor(tid) if rc is not None and ttype == 1 else None
            if other is None or not other.is_player:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if other is not self and not progression.within_reach(
                    sess.pos, other.cell, sess.loc.width, sess.loc.height):
                self.ack(RES_TOO_FAR)
                return
            target = other
        if self.healing is not None:
            self.ack(inventory.RES_NOT_READY)
            return
        si = items.params_of(row["type_id"]) or {}
        cost = si.get("heal_cost", 0)
        if rc is not None and rc.room.ws and self.ap < cost:
            self.ack(inventory.RES_NO_AP)
            return
        self.ack(inventory.RES_OK)
        if rc is not None and rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.healing = asyncio.get_running_loop().call_later(
            si.get("heal_time", 0) / 1000.0, self.heal_now, row["uniq"], target)

    def heal_now(self, uniq, target):
        self.healing = None
        row = self.store.item(uniq)
        if row is None or row["char_id"] != self.sess.char_id or self.dead:
            return
        si = items.params_of(row["type_id"]) or {}
        ch = self.character()
        patient = target.character()
        v = patient.vitals()
        # Wiki "Медицина": the skill moves the floor towards the ceiling by
        # skill/20 of the span; the specialisation (surgery under 30% HP,
        # first aid above) scales both by 1 + 0.2 per level.
        lo, hi = si.get("min_h_rest", 0), si.get("max_h_rest", 0)
        lo = lo + ch.skill_level(progression.MEDICINE) * (hi - lo) / 20.0
        spec = SPEC_SURGERY if v["hcur"] < 0.3 * v["hmax"] else SPEC_FIRST_AID
        mult = 1 + 0.2 * spec_or_zero(ch, spec)
        healed = min(v["hmax"] - v["hcur"], int(RNG.uniform(lo, hi) * mult))
        slo, shi = si.get("min_st_rest", 0), si.get("max_st_rest", 0)
        rested = min(v["smax"] - v["scur"], int(RNG.uniform(slo, shi) * mult))
        patient.hp = v["hcur"] + max(0, healed)
        patient.sp = v["scur"] + max(0, rested)
        room = self.sess.room
        frame = ("heal", dict(id=self.eid, target=target.eid,
                              hp=patient.hp, sp=patient.sp))
        if room is not None:
            room.broadcast(frame)
        else:
            self.sess.send(frame[0], **frame[1])
        left = row["use_count"] - 1
        if left <= 0:
            self.store.delete_item(uniq)
            self.sess.inv.push_status(row, 0)
        else:
            self.store.update_item(uniq, use_count=left)
            self.sess.inv.push_di(self.store.item(uniq))
        if healed > 0 and hi:
            # Wiki: experience = healed * min(2, patient's max HP / the
            # item's ceiling), half to the skill, half to the specialisation.
            mo = min(2.0, v["hmax"] / float(hi))
            changed = ch.gain_xp(progression.MEDICINE, int(healed * mo), spec)
            if any(changed.values()):
                self.sess.push_stats(**changed)

    # --- experience ---------------------------------------------------------
    def award_xp(self, skill, spec, dealt, mob_level):
        """Wiki "Начисление опыта по мобу": (clamp(mob - player, -4, 4) + 4)
        times the damage, floored; Character.gain_xp splits it between the
        skill and the specialisation and carries the remainder. Damage is
        the HP part, capped by what the mob had left, times the role's
        share: that is how the curve's xp_pool (4 * hp) is what a kill at
        equal level pays out, "пропорционально пулу моба". The client
        prints "+N опыта" from the difference in the next rp_info, which is
        pushed for the indexes that moved; a level-up moves constitution and
        with it hp_max, which travels by usrUp."""
        ch = self.character()
        xp = int((progression.level_gap(mob_level, ch.level) + 4) * dealt)
        if xp <= 0:
            return
        old_level = ch.level
        changed = ch.gain_xp(skill, xp, spec)
        if any(changed.values()):
            self.sess.push_stats(**changed)
        if ch.level != old_level:
            self.sess.push_vitals()

    def count_kill(self, mob_type):
        """A mob died by this player's hand: kill quests advance and the
        journal is told (KillMobQuest.update reads kill_num)."""
        if not self.sess.char_id:
            return
        for cmd, params in quests.kill_progress(self.store, self.sess.char_id, mob_type):
            self.sess.send(cmd, **params)
        self.character().save(self.store)

    # --- death and resurrection ----------------------------------------------
    def die(self, killer):
        """hcur reached 0. lch;dead=<me> puts the client into DEAD_STATE and
        opens the regeneration window; until resurrect, blocks() holds.

        The flag goes to the database as well as into memory. A death a
        logout undoes is no death at all, and characters.death is what the
        next login is told about by persInfo;death (Session.send_account).
        """
        self.dead = True
        self.died_at = now()
        self.cancel_timers()
        self.loot = None
        self.last_hostile = now()
        ch = self.character()
        ch.hp = 0
        ch.save(self.store)
        if self.sess.char_id:
            self.store.save_character_state(self.sess.char_id, death=1)
        room = self.sess.room
        if room is not None:
            room.broadcast(("lch", dict(dead=self.eid)))
            self.drop_on_death()
        # Nothing here to shoot at any more. think() would notice on its
        # next tick (present() is false for a corpse), but until then the
        # room stays at war over a target that cannot be hit.
        rc = self.rc
        if rc is not None:
            for mob in rc.mobs.values():
                if mob.target is self:
                    rc.mob_reset(mob)
        log.info("  ..    %s died%s", self.sess.nick,
                 "" if killer is None else " to %s" % killer.eid)

    def drop_on_death(self):
        """What the corpse leaves lying on its cell.

        The wiki's "Шанс выпадения при смерти" (drops_on_death) decides
        WHICH item can fall; the rest is DESIGNED, there being nothing else
        in the client or the tables about it. One loose item at a time, from
        the backpack only -- what is worn or held stays on the body -- into
        the ordinary bag on the ground, the same one a mob's loot lands in,
        so it is picked up through the loot session that already exists
        (ss_create;s_type=0, ss_get;slot=24, ss_upd) and expires with it.

        The item leaves the client's bag by ss_obj_status;status=0, which is
        how every other removal is reported (inventory.push_status).
        """
        rc = self.rc
        if rc is None or not self.sess.char_id:
            return
        loose = [r for r in self.sess.inv.rows()
                 if r["slot"] == inventory.BAG and drops_on_death(r["type_id"])]
        if not loose:
            return
        row = RNG.choice(loose)
        self.store.update_item(row["uniq"], char_id=LOOT_OWNER,
                               slot=inventory.BAG)
        self.sess.inv.push_status(row, 0)
        rc.add_to_bag(self.cell, [row])
        log.info("  ..    %s drops item %d (type %d) on cell %d",
                 self.sess.nick, row["uniq"], row["type_id"], self.cell)

    def resurrect(self, p):
        """resurrect;res_type=0|1|2 -- the three buttons of the regeneration
        window (gpui/RegenerationInterface.as), and what each one costs.

        RESURECT_FREE=0 is not really a choice: timePause is 15 and
        checkTimePause presses free() itself when the count reaches it
        (:122-142), so the free button is what happens to anyone who waits.
        The wait is therefore the price, and it is the one the server
        charges: before RESURRECT_WAIT seconds have passed the answer is
        non-zero, and RegenerationInterface.resurrect takes a failure by
        restarting its countdown (:108-115) -- the window stays up, nothing
        is shown anywhere, and the timer asks again for free when it runs
        out. On top of the wait the body wakes up at FREE_HP_SHARE of its HP
        with no stamina: DESIGNED, the client saying nothing about how whole
        a corpse comes back.

        RESURECT_GOLD=1 costs GOLD_COST=5 and the button hides itself when
        the purse is short of it (init/uiUpd, with a link to the top-up page
        in its place); RESURECT_AFRO=2 costs the 500 payAfro checks for. At
        the gold_to_afro_rate of 100 this server sends in its constants
        frame, 5 gold and 500 afro are the same sum -- which is what those
        two buttons are, one purchase in either purse. Both skip the wait
        and give HP and stamina back whole.

        Then home, always: the location registered with a resident
        (on_conv;op=0), or the starting cell when none was. resurrectAck
        closes the window and returns the client to LOCAL_STATE on res=0, so
        the acknowledgement goes first and Session.go_home's lcall second.
        """
        if not self.dead:
            # The window is not up. Nothing to do, but the ack is owed.
            self.ack(inventory.RES_OK)
            return
        res_type = int(p.get("res_type", 0) or 0)
        ch = self.character()
        if res_type == RES_GOLD:
            if ch.gold < RESURRECT_GOLD:
                self.ack(inventory.RES_NO_MONEY)
                return
            ch.add_money(gold=-RESURRECT_GOLD)
        elif res_type == RES_AFRO:
            if ch.afro < RESURRECT_AFRO:
                self.ack(inventory.RES_NO_MONEY)
                return
            ch.add_money(afro=-RESURRECT_AFRO)
        elif now() - self.died_at < RESURRECT_WAIT:
            # Not yet. res=17 is "объект не готов", and nothing shows it:
            # resurrectAck reads res alone and ErrorReport is not called.
            self.ack(inventory.RES_NOT_READY)
            return
        if res_type in (RES_GOLD, RES_AFRO):
            # None is how the Character spells "full" (progression.py).
            ch.hp = None
            ch.sp = None
        else:
            ch.hp = max(1, int(ch.hp_max * FREE_HP_SHARE))
            ch.sp = 0
        self.dead = False
        self.died_at = -1e9
        self.last_hostile = -1e9
        # Resurrection puts the character at their home, well away from
        # whoever killed them; carrying the duel's timer across would lock
        # them out of the map on arrival.
        self.last_pvp = -1e9
        ch.save(self.store)
        if self.sess.char_id:
            self.store.save_character_state(self.sess.char_id, death=0)
        self.ack(inventory.RES_OK)
        if res_type:
            self.sess.push_money()
        log.info("  ..    %s resurrects (res_type=%d) and goes home",
                 self.sess.nick, res_type)
        self.sess.go_home()

    # --- the loot window ------------------------------------------------------
    def open_loot(self, p):
        """ss_create;s_type=0;target=<cell>: Loot.createSession from a click
        on a bag, after Gamer.gotoLoot walked next to it."""
        rc = self.rc
        cell = int(p.get("target", 0) or 0)
        bag = rc.loot.get(cell) if rc is not None else None
        if bag is None:
            self.ack(inventory.RES_NOT_FOUND)
            return
        loc = self.sess.loc
        if not progression.within_reach(self.sess.pos, cell, loc.width, loc.height):
            self.ack(RES_TOO_FAR)
            return
        self.loot = cell
        self.ack(inventory.RES_OK)

    def session_items(self):
        """Rows behind the 0 divider of ss_get;slot=24 while a bag is open."""
        rc = self.rc
        bag = rc.loot.get(self.loot) if rc is not None and self.loot is not None else None
        if bag is None:
            return []
        rows = [self.store.item(u) for u in bag.uniqs]
        return [r for r in rows if r is not None]

    def ss_upd(self, p):
        """Loot.UPD_*: 1 to the bag, 2 back to the ground, 3 everything,
        0 close (sent bare, no ack). False when no bag is open."""
        if self.loot is None:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == 0:
            self.loot = None
            return True
        rc = self.rc
        bag = rc.loot.get(self.loot) if rc is not None else None
        if bag is None:
            self.loot = None
            self.ack(inventory.RES_NOT_FOUND)
            return True
        inv = self.sess.inv
        if code == 1:
            parsed = inventory.parse_oid(p.get("obj"))
            row = self.store.item(parsed[0]) if parsed else None
            if row is None or row["uniq"] not in bag.uniqs:
                self.ack(inventory.RES_NOT_FOUND)
                return True
            if inv.total_weight() + inventory.weight_of(row) > inventory.MAX_WEIGHT:
                self.ack(inventory.RES_OVERLOAD)
                return True
            # The ack first: Loot.transferAck moves the item on res=0, and an
            # emptied bag's ss_loot;s_status=0 may only follow it.
            self.ack(inventory.RES_OK)
            self.take(bag, [row])
        elif code == 2:
            row = inv.find(p.get("obj"))
            if row is None:
                self.ack(inventory.RES_NOT_FOUND)
                return True
            self.store.update_item(row["uniq"], char_id=LOOT_OWNER, slot=inventory.BAG)
            bag.uniqs.append(row["uniq"])
            self.ack(inventory.RES_OK)
        elif code == 3:
            rows = self.session_items()
            if inv.total_weight() + sum(inventory.weight_of(r) for r in rows) \
                    > inventory.MAX_WEIGHT:
                # All or nothing: on res=0 the client moves every item itself.
                self.ack(inventory.RES_OVERLOAD)
                return True
            self.ack(inventory.RES_OK)
            self.take(bag, rows)
        else:
            self.ack(inventory.RES_REFUSED)
        return True

    def take(self, bag, rows):
        """Rows keep their serial and so their oid: the client already holds
        the Item under it and only moves it between containers."""
        for row in rows:
            self.store.update_item(row["uniq"], char_id=self.sess.char_id,
                                   slot=inventory.BAG)
            if row["uniq"] in bag.uniqs:
                bag.uniqs.remove(row["uniq"])
        if not bag.uniqs:
            self.rc.close_bag(bag.cell)

    # --- effects (6.12, the minimum) -------------------------------------------
    def e_get_si(self, p):
        """e_si with every key Effect.clone reads, all neutral. Five of these
        may be in flight (EffectsFactory.packageLength) and each must be
        answered. name is a string id: the shared empty string."""
        self.sess.send("e_si", type=int(p.get("type", 0) or 0),
                       name=quests.EMPTY_STRING_ID, work_time=0, update_delta=0,
                       attribs_mask=0, attribs=[], skills_mask=0, skills=[],
                       specs_mask=0, specs=[], max_hp=0, max_sp=0, max_od=0,
                       critical_probability=0, critical_evade=0, armor=0,
                       mob_exp=0, pl_exp=0, mob_drop=0, pl_drop=0, res_icon=1,
                       immob=0, stun=0)

    def e_get_di(self, p):
        self.sess.send("e_di", type=int(p.get("type", 0) or 0),
                       mobi_id=int(p.get("mobi_id", 0) or 0), time=0)

    # --- regeneration ----------------------------------------------------------
    def regen(self):
        """Wiki: once a minute, +constitution HP (or +1 under 30%), each
        point paid with a point of stamina, and +1 stamina. Only a change
        is announced, as usrUp, so the "+N" floats over the head."""
        if self.dead:
            return
        ch = self.character()
        v = ch.vitals()
        hp, sp = v["hcur"], v["scur"]
        if hp < v["hmax"]:
            gain = ch.attr(progression.CONSTITUTION) if hp >= 0.3 * v["hmax"] else 1
            gain = max(0, min(gain, v["hmax"] - hp, sp))
            hp += gain
            sp -= gain
        sp = min(v["smax"], sp + 1)
        if (hp, sp) != (v["hcur"], v["scur"]):
            ch.hp, ch.sp = hp, sp
            rc = self.rc
            if rc is not None:
                rc.push_vitals(self)


# --- one room -------------------------------------------------------------

class RoomCombat:
    """War state, the AP clock, the mobs and their bags, for one Room."""

    def __init__(self, room, store):
        self.room = room
        self.store = store
        self.mobs = {eid: mobs.Mob(eid, npc.type_id, npc.cell)
                     for eid, npc in room.npcs.items() if npc.root == world.MOB}
        self.loot = {}          # cell -> LootBag
        self.timer = None
        self.ap_last = 0.0

    # --- who is here -------------------------------------------------------------
    def fighters(self):
        return [s.combat for s in list(self.room.players)]

    def actor(self, entity_id):
        """A living mob or a living player of this room by entity id."""
        mob = self.mobs.get(entity_id)
        if mob is not None:
            return mob if mob.alive else None
        if rooms.is_player_id(entity_id):
            sess = self.room.player(entity_id)
            if sess is not None and not sess.combat.dead:
                return sess.combat
        return None

    def nearest_fighter(self, cell, radius):
        width = self.room.loc.width
        best, best_d = None, radius
        for f in self.fighters():
            if f.dead:
                continue
            d = mobs.hex_distance(cell, f.cell, width)
            if d <= best_d:
                best, best_d = f, d
        return best

    def push_vitals(self, actor):
        """usrUp for anyone: the viewer's own id reads as 0 (rooms.viewer_frame)."""
        self.room.broadcast(("usrUp", dict(id=actor.eid, **actor.vitals())))

    # --- the clock -------------------------------------------------------------------
    def player_entered(self, fighter):
        if self.timer is None:
            self.ap_last = now()
            self._arm()

    def _arm(self):
        self.timer = asyncio.get_running_loop().call_later(AI_TICK, self._tick)

    def _tick(self):
        self.timer = None
        try:
            self._step()
        except Exception:
            log.exception("  !!    combat tick in %s failed", self.room.loc.title)
        if self.room.players:
            self._arm()
        else:
            # Nobody left to fight or to tell: the room goes quiet, and the
            # next arrival finds it at peace (lcall;ws reads room.ws).
            self.room.ws = False
            for mob in self.mobs.values():
                mob.target = None
                if mob.aim is not None:
                    mob.aim.cancel()
                    mob.aim = None

    def _step(self):
        t = now()
        fighters = self.fighters()
        if self.room.ws:
            ticks = int((t - self.ap_last) / AP_TICK)
            if ticks:
                for f in fighters:
                    f.ap = min(f.ap_max, f.ap + ticks * progression.AP_REGEN)
                for mob in self.mobs.values():
                    mob.ap = min(mob.ap_max, mob.ap + ticks * progression.AP_REGEN)
                self.ap_last += ticks * AP_TICK
        else:
            self.ap_last = t
        for mob in list(self.mobs.values()):
            mob.think(self, t)
        if self.room.ws and not self.hostilities(t):
            self.set_ws(False)
        for f in fighters:
            if t >= f.regen_at:
                f.regen()
                f.regen_at = t + REGEN_PERIOD
        for mob in self.mobs.values():
            if mob.alive and mob.target is None and t >= mob.regen_at:
                mob.regen_at = t + REGEN_PERIOD
                if mob.hp < mob.hp_max or mob.sp < mob.sp_max:
                    mob.hp = min(mob.hp_max, mob.hp + mob.level + 1)
                    mob.sp = min(mob.sp_max, mob.sp + 1)
                    self.push_vitals(mob)

    def hostilities(self, t):
        """Whether the room still counts as at war: a mob with a target, or
        a player within leave_combat_timeout of a shot or strike."""
        if any(m.alive and m.target is not None for m in self.mobs.values()):
            return True
        return any(f.last_hostile + LEAVE_COMBAT_TIMEOUT > t for f in self.fighters())

    def set_ws(self, on):
        """lch;ws to everyone here. The client resets its bar to maxAP on
        either edge (APManager.warState) and only spends AP while ws=1, so
        the server's pools follow the same edges."""
        on = bool(on)
        if self.room.ws == on:
            return
        self.room.ws = on
        self.room.broadcast(("lch", dict(ws=int(on))))
        self.ap_last = now()
        for f in self.fighters():
            f.ap = f.ap_max
        for mob in self.mobs.values():
            mob.ap = mob.ap_max

    def after_hostile(self, attacker, target):
        """Bookkeeping after any shot or swing: the exit timers of the
        players involved, and a mob that was attacked turns on its attacker."""
        t = now()
        if attacker.is_player:
            attacker.last_hostile = t
        if target is None:
            return
        if target.is_player:
            target.last_hostile = t
            if attacker.is_player:
                # Both ends of a duel are held for the same timeout: the one
                # who opened it cannot walk out of the answer.
                attacker.last_pvp = target.last_pvp = t
        elif target.alive and attacker.is_player and target.target is not attacker:
            self.aggro(target, attacker, t)

    def aggro(self, mob, fighter, t=None):
        """A mob picks a player: the room goes to war and the player's client
        paints the mob red (lch;enemy -> Location.setEnemy) and remembers it
        for autofire."""
        t = now() if t is None else t
        mob.target = fighter
        mob.next_attack = max(mob.next_attack, t + 0.3)
        self.set_ws(True)
        fighter.sess.send("lch", enemy=mob.eid)

    # --- what mobs do -------------------------------------------------------------------
    def mob_walk(self, mob, goal, t):
        """One leg of a walk towards the nearest cell satisfying goal, as
        userMove;id;path to everyone. The mob's cell is its destination at
        once, which is where the client will have it when the animation
        ends; busy_until keeps it from acting before that."""
        loc = self.room.loc
        blocked = {m.cell for m in self.mobs.values() if m.alive and m is not mob}
        blocked |= {s.pos for s in self.room.players}
        path = mobs.find_path(loc, mob.cell, goal, blocked)
        if not path or len(path) < 2:
            mob.busy_until = t + 1.0
            return
        leg = path[:mobs.LEG + 1]
        self.room.broadcast(("userMove", dict(id=mob.eid, path=leg)))
        mob.cell = leg[-1]
        npc = self.room.npcs.get(mob.eid)
        if npc is not None:
            self.room.npcs[mob.eid] = npc._replace(cell=leg[-1])
        mob.busy_until = t + mobs.HEX_MS / 1000.0 * (len(leg) - 1) + 0.1

    def mob_reset(self, mob):
        """The target is gone or out of reach: forget it and recover; the
        walk home follows on the next ticks."""
        mob.target = None
        if mob.hp < mob.hp_max or mob.sp < mob.sp_max:
            mob.hp, mob.sp = mob.hp_max, mob.sp_max
            self.push_vitals(mob)

    def mob_attack(self, mob, target, t):
        st = mob.stats
        mob.next_attack = t + st.attack_time + mobs.ATTACK_PAUSE
        loop = asyncio.get_running_loop()
        if st.ranged:
            width = self.room.loc.width
            self.room.broadcast(("faAim", dict(
                id=mob.eid, ang=mobs.direction(mob.cell, target.cell, width),
                num_shots=st.shots)))
            weapon = Weapon(num_shots=st.shots, dmin=st.dmg_min, dmax=st.dmg_max,
                            opt_lo=1, opt_hi=st.range, max_range=st.range, piercing=1,
                            hit=st.hit, crit=st.crit, skill=None, spec=None)
            mob.aim = loop.call_later(st.attack_time, self.mob_burst, mob, target, weapon)
        elif st.attack_time:
            mob.aim = loop.call_later(st.attack_time, self.mob_strike, mob, target)
        else:
            self.mob_strike(mob, target)

    def mob_burst(self, mob, target, weapon):
        mob.aim = None
        if not mob.alive:
            return
        h, s, hits, killed = self.burst(mob, target, target.cell, weapon, weapon.num_shots)
        mob.ap = max(0, mob.ap - mob.stats.attack_ap)
        self.after_hostile(mob, target)
        if killed:
            self.kill(target, mob)

    def mob_strike(self, mob, target):
        mob.aim = None
        if not mob.alive:
            return
        st = mob.stats
        killed = False
        if target.present(self) and mobs.adjacent(mob.cell, target.cell, self.room.loc) \
                and roll(st.hit - target.dodge_melee()):
            crit = roll(st.crit - target.crit_evade_melee())
            dmg = RNG.randint(st.dmg_min, st.dmg_max)
            h, s = melee_split(dmg, crit, target.sp_now())
            self.room.broadcast(("caHit", dict(id=mob.eid, target=target.eid,
                                               dmg=h, sdmg=s, crit=int(crit))))
            killed = target.apply_damage(h, s)
            self.push_vitals(target)
        else:
            self.room.broadcast(("caMiss", dict(id=mob.eid, hex=target.cell)))
        mob.ap = max(0, mob.ap - st.attack_ap)
        self.after_hostile(mob, target)
        if killed:
            self.kill(target, mob)

    # --- the shot resolver, shared -------------------------------------------------------
    def burst(self, shooter, target, hexcell, weapon, live):
        """num_shots pairs of faShot around what each bullet did, then usrUp
        of the target. live is how many chambers held a round; the rest
        click (a miss). Returns (hp damage, sp damage, hits, killed)."""
        loc = self.room.loc
        width = loc.width
        if target is not None and not target.present(self):
            hexcell = target.cell
            target = None
        aim = target.cell if target is not None else hexcell
        if aim is None or not (0 <= aim < width * loc.height):
            aim = shooter.cell
        wall = mobs.line_of_fire(loc, shooter.cell, aim)
        dist = mobs.hex_distance(shooter.cell, aim, width)
        tx, ty = mobs.real(aim, width)
        total_h = total_s = hits = 0
        sp_left = target.sp_now() if target is not None else 0
        frames = []
        for k in range(weapon.num_shots):
            frames.append(("faShot", dict(id=shooter.eid, status=1)))
            if k >= live or target is None:
                frames.append(("faMiss", miss_at(tx, ty)))
            elif wall is not None:
                frames.append(("faWall", dict(hex=wall)))
            elif roll(weapon.hit - target.dodge_ranged()):
                optimal = weapon.opt_lo <= dist <= weapon.opt_hi
                crit = optimal and roll(weapon.crit - target.crit_evade_ranged())
                lo, hi = weapon.dmin, weapon.dmax
                if optimal:
                    lo = (hi - lo) // 2 + lo
                dmg = RNG.randint(lo, max(lo, hi))
                h, s = split_damage(dmg, target.armor(), weapon.piercing, crit, sp_left)
                sp_left -= s
                total_h += h
                total_s += s
                hits += 1
                frames.append(("faHit", dict(target=target.eid, dmg=h, sdmg=s,
                                             crit=int(crit))))
            else:
                frames.append(("faMiss", miss_at(tx, ty)))
            frames.append(("faShot", dict(id=shooter.eid, status=0)))
        for frame in frames:
            self.room.broadcast(frame)
        killed = False
        if target is not None and hits:
            killed = target.apply_damage(total_h, total_s)
            self.push_vitals(target)
        return total_h, total_s, hits, killed

    # --- death, corpse, bag, respawn ----------------------------------------------------
    def kill(self, victim, killer):
        if victim.is_player:
            victim.die(killer)
            return
        mob = victim
        mob.alive = False
        mob.target = None
        if mob.aim is not None:
            mob.aim.cancel()
            mob.aim = None
        # lch;dead plays the death animation and clears the figure's nick and
        # focus; the corpse stays until lostUser (DisplayLocScene.dead).
        self.room.broadcast(("lch", dict(dead=mob.eid)))
        if killer is not None and killer.is_player:
            killer.count_kill(mob.type_id)
        # Out of the room's inhabitants until it respawns, so an arrival in
        # the meantime is not handed a corpse as a newUser.
        self.room.npcs.pop(mob.eid, None)
        witnesses = list(self.room.players)
        asyncio.get_running_loop().call_later(CORPSE_DELAY, self.corpse_gone, mob, witnesses)
        log.info("  ..    mob %d (%s) killed by %s", mob.eid, mob.stats.name,
                 "nobody" if killer is None else killer.eid)

    def corpse_gone(self, mob, witnesses):
        """The figure fades (only for those who saw it: a lostUser about an
        id the client never met logs an event with no name), the bag drops
        where it fell, and the respawn clock starts."""
        for sess in witnesses:
            if sess in self.room.players:
                sess.send("lch", lostUser=mob.eid)
        self.add_to_bag(mob.cell, self.drop_loot(mob))
        asyncio.get_running_loop().call_later(RESPAWN_DELAY, self.respawn, mob)

    def add_to_bag(self, cell, rows):
        """Put item rows into the bag on a cell, opening one where there is
        none. ss_loot;s_status=1 is what draws it (Location.ss_loot), and
        the lifetime restarts with every addition. Shared by a mob's loot
        and by what a player drops where they died."""
        if not rows:
            return
        bag = self.loot.get(cell)
        if bag is None:
            bag = self.loot[cell] = LootBag(cell, [r["uniq"] for r in rows])
            self.room.broadcast(("ss_loot", dict(s_status=1, hex=[cell])))
        else:
            bag.uniqs += [r["uniq"] for r in rows]
        if bag.expiry is not None:
            bag.expiry.cancel()
        bag.expiry = asyncio.get_running_loop().call_later(
            LOOT_LIFETIME, self.expire_bag, cell)

    def drop_loot(self, mob):
        """Item rows on the ground, owned by nobody, made through the store
        so they carry real serials the client can keep after picking up."""
        rows = []
        for type_id, count in mobs.loot_for(mob.stats, RNG):
            fields = inventory.new_fields(type_id, count)
            root = fields.pop("root")
            rows.append(self.store.create_item(LOOT_OWNER, type_id, root, **fields))
        return rows

    def close_bag(self, cell):
        bag = self.loot.pop(cell, None)
        if bag is None:
            return
        if bag.expiry is not None:
            bag.expiry.cancel()
        for f in self.fighters():
            if f.loot == cell:
                f.loot = None
        self.room.broadcast(("ss_loot", dict(s_status=0, hex=[cell])))

    def expire_bag(self, cell):
        bag = self.loot.get(cell)
        if bag is None:
            return
        for uniq in bag.uniqs:
            self.store.delete_item(uniq)
        bag.uniqs = []
        self.close_bag(cell)

    def respawn(self, mob):
        """Back on its spawn cell under the same id: the client dropped the
        entity on lostUser and builds it afresh from lch;newUser, then asks
        for its details itself; the details are pushed anyway, as on entry."""
        mob.reset()
        mob.cell = mob.home
        self.room.npcs[mob.eid] = rooms.NPC(mob.home, mob.type_id, world.MOB)
        for sess in list(self.room.players):
            sess.send("lch", newUser=mob.eid, pos=mob.home, rtype=world.MOB)
            sess.send_npc_info(mob.eid)


def room_combat(room, store):
    """The RoomCombat of a room, made on first use."""
    if room.combat is None:
        room.combat = RoomCombat(room, store)
    return room.combat
