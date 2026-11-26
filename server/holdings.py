"""Warehouses a clan holds: taken by killing the warehouse's boss.

Weekly bases use these same holdings (kind "base" in the table), not a
second ownership system. Their original surfaces/interiors share one site.
The Saturday 20:00–21:00 Moscow kill grants a payment reservation; the
winning clan pays 1,500,000 afro from its treasury by 21:15, then owns the
benefits until next Saturday 19:55, five minutes before the battle. Each week needs a new capture
and payment. The master and three bodyguards arrive at the weekly battle
start, independently of surviving outer guards. One clan may reserve/lease
one base; warehouses do not count.
Bases keep ten ordinary guards between battles, immune to the captured clan.
The master and bodyguards stand only during the weekly battle window.
The ordinary guards return five minutes after death; the existing
boss checkpoints also hold that deadline across restarts. Capture waves do
not respawn, including after an early payment in the same battle window.
At least three living clan members of the site's minimum level must be in
the boss's room at the kill, each having hurt him. Only the killing blow's
clan can win a base. The three contributors must include the actual finisher.
Capture and the weekly boss-death record commit at the kill, before the
corpse timer. Everything below describes the existing warehouses unless it
explicitly names a base.

Warehouse gold is a separate native box service: existing 1/5 G ingots,
3 G in Halfa, 5 G in Dongola, 7 G in Abu. The same ownership, 24-hour
membership and box windows apply, plus treasury-withdrawal permission.
A persistent site/day claim belongs to the whole warehouse and is not
reset by capture or disband. Claim, item grant and quest history commit
together. The old personal ammo/afro rows are closed; the gold treasury
remains disabled. Unlike ordinary quest rewards, this service needs carry room.

The owner's «сделай так чтобы склады можно было захватывать убивая босса»
(2026-10-09). The sites are data/holdings.json's -- Вади-Хальфа's three
склады, 111, 110 and 109, each a room with its boss «Хозяин склада», the
clan flag 1011 and the money box -- and a city added later is a row there.

Who takes it. The killing blow's clan alone may take a warehouse, using
the base's last-hit rule but with at least two distinct living members
in the boss's room at the kill, each at the site's minimum level or above
and each having hurt the boss since its last full heal. Other clans' total
damage never determines ownership, and an ineligible or clanless finisher
has no fallback winner. No party or diplomacy is required.

Warehouse defenders do not initiate attacks against their current holders.
They remain attackable and retaliate when attacked; base defenders retain
their existing friendly immunity. Ownership and membership are read live.

The harm is the boss's own capture ledger (mobs.Mob.capture_harm), keyed by
character so that a reconnect keeps it, and emptied whenever the boss is
whole again (combat.RoomCombat.mob_recover, its regeneration, Mob.reset):
the xp ledger keeps every blow a boss ever took until it dies, and a clan
could bank harm on it through heal after heal and win a kill somebody else
made. Who fought for which clan is read at the kill (snapshot, from
combat.RoomCombat.kill, before the xp ledger is settled), and the holding is
settled when the corpse fades (settle, from corpse_gone, before the hours
take the boss away -- so with LAVA_BOSS_HOURS=off too): a member who leaves
his clan in those seconds still counts for the one he fought for.

A boss killed is away until its next window (bosses.py, combat.
RoomCombat.keep_hours; the boss_kills table keeps that over a restart), so
every window of its hours settles a site once at most. The «Хозяин склада»
keeps hours of his own (bosses.WAREHOUSE_HOURS, the owner's «на складах
хозяин должен прриходить один раз!!!», 2026-10-12): one window a day, from
20:00 to 21:00 Moscow time, as the box's hour ends -- so a site changes
hands once a day at most.

How long. Every warehouse becomes neutral daily at 20:00 Moscow, after
all box reward windows and before the master's new daily window. The old
clan can capture it again under the same two-contributor rule. Re-killing
its own master within one cycle remains a defence, without extending the
cycle or resetting rewards. Expiry is reconciled on startup and by a global
timer even for empty rooms; live reads and the locked gold claim reject an
expired owner immediately. An old corpse cannot capture in a newer cycle.
A disband also releases ownership; admins can assign or clear a site.

What the holders get, in the site's room only:

  the flag  «Складом владеют:» over the holder's name (send_npc_info:
            clan= on its userInfo_Trader and a fellow about the flag right
            after it, flag_for); it mends their things and nobody else's,
            and sells nothing (may_repair, inventory.Inventory.repair). The
            flags of the other cities' warehouses mend for anybody, as
            before;
  the box   the shared daily ingots (data/quests.json, gold_quest), at the
            box from 19:00 to 20:00 (data/schedule.json wh_box): to a member
            of the holding clan of a day's standing with treasury rights.
            The site/day claim is atomic with the grant. The former
            personal ammo/afro quests 765-771 remain closed even in old journals.

What is said. Warehouses keep the original silent capture policy. A base
reports its pending winner/payment deadline, or why the squad did not qualify.
Every outcome -- a capture, a defence, a kill that
took nothing, the admin's order, a disband -- is a line in the log and a row
in clan_holding_log. The flag's caption and the site's page carry the news.
When the holder changes in the game process, the flag's frame goes again to
everybody in its room and the box is shown under a new id on the room's
next tick (events.touch), so that the client asks its rows afresh.

Nothing is cached: every flag, box and repair reads clan_holdings, as
clans.py reads every membership -- tools/admin_account.py disbands clans
from another process. This module imports neither clans nor inventory nor
mail (trophies.clan_of says why): membership is Store.clan_member's.
"""
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta

import bosses
import events
import storage
import world

log = logging.getLogger("lava")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "data", "holdings.json")

# What a row of clan_holding_log says happened (accounts.SCHEMA).
HOW = ("capture", "defend", "none", "admin", "disband", "rent", "expire")
WAREHOUSE_RESET_HOUR = 20
BASE_SQUAD = 3
BASE_RESET_LEAD = 5 * 60
BASE_SOLDIER_RESPAWN = 5 * 60
BASE_MASTER_NAME = 8000002
BASE_BODYGUARD_NAME = 8000003
BASE_GUARD_NAME = 8000004


class Site(object):
    """One capturable place of data/holdings.json."""
    __slots__ = ("key", "loc", "boss", "flag", "box", "quest", "min_level", "title",
                 "kind", "rooms", "traders", "rent_quest", "rent", "battle", "payment",
                 "gold_quest", "health_scale", "guards", "guard_health_scale",
                 "damage_scale", "guard_damage_scale", "troops", "troop_health_scale",
                 "troop_damage_scale")

    def __init__(self, key, rec):
        self.key = str(key)
        self.loc = int(rec["loc"])
        self.boss = int(rec["boss"])
        self.flag = int(rec["flag"])
        self.box = int(rec.get("box", 0))
        self.quest = int(rec.get("quest", 0))
        self.min_level = int(rec["min_level"])
        self.title = str(rec["title"])
        self.kind = str(rec.get("kind", "warehouse"))
        self.rooms = tuple(int(x) for x in rec.get("rooms", [self.loc]))
        self.traders = tuple(int(x) for x in rec.get("traders", []))
        self.rent_quest = int(rec.get("rent_quest", 0))
        self.rent = int(rec.get("rent", 0))
        self.battle = str(rec.get("battle", ""))
        self.payment = str(rec.get("payment", ""))
        self.gold_quest = int(rec.get("gold_quest", 0))
        self.guards = tuple(int(x) for x in rec.get("guards", []))
        self.troops = tuple(int(x) for x in rec.get("troops", []))
        self.health_scale = float(rec.get("health_scale", 1))
        self.guard_health_scale = float(rec.get("guard_health_scale", 1))
        self.troop_health_scale = float(rec.get("troop_health_scale", 1))
        self.damage_scale = float(rec.get("damage_scale", 1))
        self.guard_damage_scale = float(rec.get("guard_damage_scale", 1))
        self.troop_damage_scale = float(rec.get("troop_damage_scale", 1))
        for field in ('health_scale', 'guard_health_scale', 'damage_scale', 'guard_damage_scale',
                      'troop_health_scale', 'troop_damage_scale'):
            if not math.isfinite(getattr(self, field)) or not 1 <= getattr(self, field) <= 100:
                raise ValueError("data/holdings.json: %s %s must be finite, 1..100" % (self.key, field))


class Table(object):
    """data/holdings.json, read and indexed."""

    def __init__(self, doc):
        doc = doc if isinstance(doc, dict) else {}
        self.squad = int(doc.get("squad", 2))
        self.tenure = float(doc.get("box_tenure_hours", 24)) * 3600
        self.one_per_account = bool(doc.get("box_one_per_account", True))
        self.sites = {key: Site(key, rec) for key, rec in (doc.get("sites") or {}).items()
                      if not key.startswith("_")}
        self.by_loc = {}
        for s in self.sites.values():
            for loc_id in s.rooms:
                if loc_id in self.by_loc:
                    raise ValueError("data/holdings.json: %s and %s are both location %d"
                                     % (self.by_loc[loc_id].key, s.key, loc_id))
                self.by_loc[loc_id] = s


_TABLE = None


def table():
    """The sites, read once. No file is no sites: nothing can be taken."""
    global _TABLE
    if _TABLE is None:
        doc = {}
        if os.path.isfile(PATH):
            with open(PATH, encoding="utf-8") as fh:
                doc = json.load(fh)
        _TABLE = Table(doc)
    return _TABLE


def sites():
    """key -> Site."""
    return table().sites


def site(key):
    return table().sites.get(key) if isinstance(key, str) else None


def site_at(loc_id):
    """The site whose room this location is, or None."""
    if loc_id is None:
        return None
    return table().by_loc.get(int(loc_id))


def site_for(loc_id, boss_type):
    """The site whose boss this is, killed in its own room, or None: 982 and
    983, copies of 109 and 110 with the same bosses, are no sites, and a
    kill there is an ordinary boss's."""
    s = site_at(loc_id)
    return s if s is not None and s.loc == int(loc_id) and s.boss == int(boss_type) else None


def base_for(loc_id, boss_type=None):
    """A configured base, optionally only its capture boss on the surface."""
    s = site_at(loc_id) if boss_type is None else site_for(loc_id, boss_type)
    return s if s is not None and s.kind == "base" else None


def prepare_room(rc):
    """Site defenders use local stat copies, never a shared type edit."""
    import battle_balance
    import mobs
    for target in rc.mobs.values():
        s = site_for(rc.room.loc.id, target.type_id) or guard_site(rc.room.loc.id, target.type_id)
        if s is None or getattr(target, "_holding_prepared", False):
            continue
        if target.type_id == s.boss:
            scale, damage = s.health_scale, s.damage_scale
        elif target.type_id in s.guards:
            scale, damage = s.guard_health_scale, s.guard_damage_scale
        else:
            scale, damage = s.troop_health_scale, s.troop_damage_scale
        # Outer guards retain their entity types and death checkpoints, but
        # carry the same automatic weapon as this base's original guardian.
        source = s.guards[0] if s.kind == 'base' and target.type_id in s.troops else target.type_id
        target.stats = mobs.MobStats(source, balanced=False)
        battle_balance.configure_mob(target.stats, health_scale=scale, damage_scale=damage, site=True)
        target.stats.type_id = target.type_id
        target.hp, target.sp = target.stats.hp_max, target.stats.sp_max
        target._holding_prepared = True


def rent_site(quest_type):
    return next((s for s in sites().values()
                 if s.kind == "base" and s.rent_quest == int(quest_type)), None)


def base_keys():
    return tuple(s.key for s in sites().values() if s.kind == "base")


def guard_site(loc_id, type_id):
    s = site_at(loc_id)
    return s if (s is not None and s.loc == int(loc_id)
                 and int(type_id) in s.guards + s.troops) else None


def reset_base(rc):
    """Five minutes before the weekly battle, clear the previous owner.

    The conditional delete preserves a concurrent current-week capture.
    Empty rooms reconcile on entry through the existing schedule tick.
    """
    s = base_for(rc.room.loc.id)
    if s is None:
        return
    now = bosses.clock()
    slot = battle_slot(s, now)
    if slot is None:
        slot = battle_slot(s, now + BASE_RESET_LEAD)
    if slot is None:
        return
    held = holder(rc.store, s)
    if held is not None and (held['slot'] is None or float(held['slot']) < slot):
        if rc.store.holding_clear(s.key, 'expire', when=now, before_slot=slot) is not None:
            refresh(rc.room, s)


def warehouse_reset_at(now=None):
    """The latest daily 20:00 boundary on the boss/reward schedule's clock."""
    now = bosses.clock() if now is None else now
    local = datetime.fromtimestamp(now, bosses.ZONE)
    boundary = local.replace(hour=WAREHOUSE_RESET_HOUR, minute=0, second=0, microsecond=0)
    if local < boundary:
        boundary -= timedelta(days=1)
    return boundary.timestamp()


def reset_warehouses(store, rooms=None, now=None):
    """Expire all seven sites, including empty rooms and days spent offline.

    Conditional deletes cannot erase a concurrent new capture. Reward claims
    and boss-death checkpoints belong to their own schedules and stay intact.
    """
    now = bosses.clock() if now is None else now
    boundary = warehouse_reset_at(now)
    expired = []
    with storage.atomic(store.db):
        for s in sites().values():
            if s.kind == "warehouse" and store.holding_clear(
                    s.key, "expire", when=now, before_since=boundary) is not None:
                expired.append(s)
    if rooms is not None:
        for s in expired:
            room = rooms.rooms.get(s.loc)
            if room is not None:
                refresh(room, s)
    return tuple(s.key for s in expired)


def reset_warehouse(rc):
    """Reconcile on entry/tick before the boss and the box are shown."""
    s = site_at(rc.room.loc.id)
    if s is None or s.kind != "warehouse":
        return
    now = bosses.clock()
    boundary = warehouse_reset_at(now)
    if getattr(rc, "warehouse_cycle", None) == boundary:
        return
    if rc.store.holding_clear(s.key, "expire", when=now, before_since=boundary) is not None:
        refresh(rc.room, s)
    rc.warehouse_cycle = boundary


def gold_site(quest_type):
    return next((s for s in sites().values()
                 if s.kind == "warehouse" and s.gold_quest == int(quest_type)), None)


def gold_refusal(store, s, char_id, day):
    """The gold-specific part of a warehouse box's existing holders gate."""
    member = store.clan_member(char_id) if char_id else None
    if member is None or not int(member["perm"]) & (0x8000 | 0x400):
        return "Золото клана может забрать глава или участник с правом расходовать афро из казны."
    if store.holding_gold_claimed(s.key, day):
        return "Золото с этого склада сегодня уже забрали. Награда общая на весь склад."
    return None


def battle_slot(s, now=None):
    return events.table().window(s.battle).slot(bosses.clock() if now is None else now)


def _paid_at(held, now):
    return (held is not None and held["slot"] is not None
            and float(held["slot"]) <= now < min(float(held["paid_until"]),
                                               float(held["slot"]) + 7 * 86400 - BASE_RESET_LEAD)
            and float(held["paid_until"]) <= float(held["slot"]) + 7 * 86400)


def paid_holder(store, s, now=None):
    """Only a current paid lease grants bunker entry and services."""
    held = holder(store, s)
    return held if _paid_at(held, bosses.clock() if now is None else now) else None


def base_holder(store, s, now=None):
    """The visible owner and friendly clan, including a pending reservation."""
    held = holder(store, s)
    now = bosses.clock() if now is None else now
    if _paid_at(held, now):
        return held
    if held is not None and float(held['paid_until']) == 0:
        slot = events.table().window(s.payment).slot(now)
        if slot is not None and held['slot'] == slot:
            return held
    return None


def paid_base_for(store, loc_id, char_id, now=None):
    """The character's paid base in this room; native NPC rights stay native."""
    s = base_for(loc_id)
    if s is None or not member_of(store, paid_holder(store, s, now), char_id):
        return None
    return s


def defender_friendly(rc, mob, fighter, *, cache=None):
    """Base defenders cannot harm, or be harmed by, their current clan."""
    if not getattr(fighter, 'is_player', False) or getattr(mob, 'is_player', False):
        return False
    return _defender_clanmate(rc, mob, fighter, base_for(getattr(rc.room.loc, 'id', None)), cache)


def warehouse_defender_passive(rc, mob, fighter):
    """Warehouse owners may approach safely, but can provoke a normal fight."""
    if not getattr(fighter, 'is_player', False) or getattr(mob, 'is_player', False):
        return False
    s = site_at(getattr(rc.room.loc, 'id', None))
    return (s is not None and s.kind == 'warehouse'
            and _defender_clanmate(rc, mob, fighter, s))


def _defender_clanmate(rc, mob, fighter, s, cache=None):
    # Reuse rights only within one synchronous AI pass or one explicit burst.
    if cache is None:
        cache = getattr(rc, '_defender_cache', None)
    if s is None:
        return False
    ground = getattr(getattr(fighter, 'sess', None), 'ground', None)
    if getattr(ground, 'ally', False):
        fighter = ground.owner.combat
    if getattr(fighter, 'store', rc.store) is not rc.store:
        return False
    loc_id = getattr(rc.room.loc, 'id', None)
    type_id = getattr(mob, 'type_id', None)
    if type_id != s.boss and (s.loc != loc_id or type_id not in s.guards + s.troops):
        return False
    char_id = fighter.sess.char_id
    key = (s.key, char_id)
    if cache is not None and key in cache:
        return cache[key]
    holding_key = (s.key,)
    if cache is not None and holding_key in cache:
        held = cache[holding_key]
    else:
        held = base_holder(rc.store, s) if s.kind == 'base' else holder(rc.store, s)
        if cache is not None:
            cache[holding_key] = held
    friendly = member_of(rc.store, held, char_id)
    if cache is not None:
        cache[key] = friendly
    return friendly


def soldier_respawns(store, loc_id, type_id, now=None):
    """Outer guards return between battles, including neutral bases."""
    s = guard_site(loc_id, type_id)
    if s is None or s.kind != 'base' or type_id not in s.troops:
        return False
    now = bosses.clock() if now is None else now
    return battle_slot(s, now) is None


def occupation_slot(s, now):
    """The last battle's end names the soldiers' ordinary five-minute phase."""
    window = events.table().window(s.battle)
    day = datetime.fromtimestamp(now, bosses.ZONE).date()
    return max(end for ago in range(8) for _start, end in window.openings(day - timedelta(days=ago))
               if end <= now)


def rent_refusal(store, s, char_id, loc_id=None, now=None, *, check_funds=True):
    """Live lease eligibility; treasury funds gate payment, not the offer."""
    now = bosses.clock() if now is None else now
    slot = events.table().window(s.payment).slot(now)
    if slot is None or (loc_id is not None and int(loc_id) != s.loc):
        return "Аренду можно оплатить у флага базы в субботу до 21:15 по Москве."
    held = holder(store, s)
    if held is None or held["slot"] != slot:
        return "Сначала ваш клан должен захватить базу в этой недельной битве."
    m = store.clan_member(char_id) if char_id else None
    if m is None or int(m["clan_id"]) != int(held["clan_id"]):
        return "Базу может арендовать только захвативший её клан."
    if not int(m["perm"]) & (0x8000 | 0x400):
        return "Нужно право расходовать афро из казны клана."
    if store.base_reserved(held["clan_id"], base_keys(), now, except_site=s.key):
        return "Клан может владеть только одной клановой базой. Склады не учитываются."
    if float(held["paid_until"]) != 0:
        return "Аренда за эту неделю уже оплачена."
    if check_funds:
        balance = store.clan_treasury(int(held["clan_id"]))
        if balance is None or balance < s.rent:
            return "В казне клана недостаточно афро для аренды базы."
    return None


def pay_rent(store, s, char_id, now=None):
    """Part of quest_write's transaction; no other player's frames before commit."""
    now = bosses.clock() if now is None else now
    if rent_refusal(store, s, char_id, s.loc, now) is not None:
        return None
    held = holder(store, s)
    if held is None:
        return None
    slot = events.table().window(s.payment).slot(now)
    return store.holding_rent(s.key, held["clan_id"], char_id, slot,
                              slot + 7 * 86400 - BASE_RESET_LEAD, s.rent, s.rent_quest, now,
                              base_sites=base_keys())


# --- the table holds together ----------------------------------------------------------
def problems():
    """["what: why"] for every site that cannot work as written; empty when
    all of them can. Each location's file holds the site's boss, flag and
    box, and the boss is one of the warehouse masters, who keep the
    warehouses' hour (bosses.WAREHOUSE_MASTERS); the box's row (data/
    quests.json) names the site in holders, asks
    the site's level and is given and taken at the box; data/schedule.json
    keeps it in a window, gate "both"; and no row of the quests names a site
    that is not here."""
    import quests                       # late: quests is the server's to load first
    out = []
    t = table()
    if t.squad < 1:
        out.append("squad: at least one")
    for key, s in sorted(t.sites.items()):
        try:
            loc = world.location(s.loc)
        except (KeyError, OSError, ValueError) as exc:
            out.append("%s: no location %d (%s)" % (key, s.loc, exc))
            continue
        files = {ty for _c, ty in loc.spawns}
        files.update(int(r["type"]) for r in world.placements().get(s.loc, ()))
        if any(g not in files or world.creature_role(g) != 'mob' for g in s.guards + s.troops):
            out.append("%s: guards and troops must be ordinary fighters in its room" % key)
        if set(s.guards) & set(s.troops) or s.boss in s.guards + s.troops:
            out.append("%s: defender roles must use distinct types" % key)
        if s.kind == "base":
            for what, ty in (("boss", s.boss), ("flag", s.flag)):
                if ty not in files:
                    out.append("%s: no %s %d in its surface" % (key, what, ty))
            if world.creature_role(s.boss) != "boss":
                out.append("%s: its capture creature is not a boss" % key)
            if not s.guards or any(g not in files or world.creature_role(g) != 'mob' for g in s.guards):
                out.append("%s: base guards must be ordinary fighters on its surface" % key)
            if s.loc not in s.rooms or s.rent <= 0 or not s.traders:
                out.append("%s: a base needs its surface, traders and a positive rent" % key)
            for loc_id in s.rooms:
                try:
                    world.location(loc_id)
                except (KeyError, OSError, ValueError):
                    out.append("%s: no base room %d" % (key, loc_id))
            q = quests.get(s.rent_quest)
            if (q is None or not q.service or not q.repeatable or q.level != 0
                    or q.give != [s.flag] or q.take != [s.flag] or q.has_fee
                    or q.rew_obj or q.rew_also or q.rew_afro or q.rew_gold
                    or q.rew_xp or q.rew_spec_xp or q.holders):
                out.append("%s: rent quest is not its native treasury service" % key)
            gate = events.table().gates.get(s.rent_quest)
            if gate is None or gate[0].name != s.payment or gate[1] != "both":
                out.append("%s: rent quest needs its payment window, gate both" % key)
            if s.battle not in events.table().windows or s.payment not in events.table().windows:
                out.append("%s: no battle/payment window" % key)
            continue
        if s.boss not in bosses.WAREHOUSE_MASTERS:
            out.append("%s: its boss %d is no warehouse master (bosses.WAREHOUSE_MASTERS)"
                       " and keeps the bosses' hours" % (key, s.boss))
        for what, ty in (("boss", s.boss), ("flag", s.flag), ("box", s.box)):
            if ty not in files:
                out.append("%s: its %s %d is not in location %d's file" % (key, what, ty, s.loc))
        q = quests.get(s.quest)
        if q is None:
            out.append("%s: no quest %d in the table" % (key, s.quest))
        else:
            if q.holders != key:
                out.append("%s: quest %d names %r in holders" % (key, s.quest, q.holders))
            if q.level != s.min_level:
                out.append("%s: quest %d asks level %d, the site %d"
                           % (key, s.quest, q.level, s.min_level))
            if s.box not in q.give or s.box not in q.take:
                out.append("%s: quest %d is not given and taken at the box %d"
                           % (key, s.quest, s.box))
        gate = events.table().gates.get(s.quest)
        if gate is None or gate[1] != "both":
            out.append("%s: quest %d is in no window of data/schedule.json with gate both"
                       % (key, s.quest))
        if s.gold_quest:
            q = quests.get(s.gold_quest)
            gold_gate = events.table().gates.get(s.gold_quest)
            if (q is None or not q.service or not q.repeatable or q.holders != key
                    or q.level != s.min_level or q.give != [s.box] or q.take != [s.box]
                    or not q.rew_also or q.rew_obj or q.rew_random or q.has_fee
                    or q.rew_afro or q.rew_gold or q.rew_xp or q.rew_spec_xp):
                out.append("%s: invalid clan gold service quest" % key)
            if gold_gate != gate:
                out.append("%s: gold service must keep its personal box's window" % key)
    for q in quests.QUESTS.values():
        if q.holders and q.holders not in t.sites:
            out.append("quest %d: holders names no site %r" % (q.type, q.holders))
    return out


def check():
    """Raise ValueError naming every problem: asked by the server before its
    first socket, as events.check is."""
    found = problems()
    if found:
        raise ValueError("data/holdings.json: " + "; ".join(found))


def describe():
    """One line for the start-up log."""
    t = table()
    if not t.sites:
        return "no capturable sites (data/holdings.json)"
    return "capturable sites: " + ", ".join(
        "%s (%d, level %d)" % (key, s.loc, s.min_level) for key, s in sorted(t.sites.items()))


# --- who holds what ----------------------------------------------------------------------
def holder(store, s, now=None):
    """Live ownership, even before the next timer or after an offline day.

    This read has no commits: quest callers may already be in a transaction.
    Daily expiry is also checked under the gold claim's database lock.
    """
    held = store.holding(s.key)
    if (held is not None and s.kind == "warehouse"
            and float(held["since"]) < warehouse_reset_at(now)):
        return None
    return held


def member_of(store, held, char_id):
    """Whether the character is a member of the holding's clan now."""
    if held is None or not char_id:
        return False
    m = store.clan_member(char_id)
    return m is not None and int(m["clan_id"]) == int(held["clan_id"])


def flag_for(store, loc_id, type_id, char_id):
    """What a site's flag tells this viewer (server.Session.send_npc_info):
    None for anything but a site's flag in its own room -- every other
    warehouse's flag is drawn as before -- else (the holding or None,
    whether it mends this viewer's things)."""
    s = site_at(loc_id)
    if s is None or int(type_id) != s.flag:
        return None
    held = base_holder(store, s) if s.kind == "base" else holder(store, s)
    return held, s.kind != "base" and member_of(store, held, char_id)


def may_serve(store, loc_id, trader_type, char_id):
    """Bunker services require the current clan's paid lease, like entry."""
    base = base_for(loc_id)
    if base is None or trader_type not in base.traders:
        return True
    return member_of(store, paid_holder(store, base), char_id)


def may_repair(store, loc_id, trader_type, char_id):
    """Whether a repair at this trader may go ahead (inventory.Inventory.
    repair): anywhere but at a site's flag in its room, always; there, for a
    member of the holding clan only."""
    # Bases have one dedicated repair service; the medic and ammunition
    # supplier must not regain it through a direct ss_upd request.
    if base_for(loc_id) is not None:
        return trader_type == 989 and may_serve(store, loc_id, trader_type, char_id)
    got = flag_for(store, loc_id, trader_type, char_id) if trader_type is not None else None
    return got is None or got[1]


def box_refusal(store, quest, char_id, account_id, since, now=None):
    """None when the character may take or hand in a holders' row (data/
    quests.json holders) now, else why not, for the log. Asked by server.
    Session.quest_available -- before a carried quest is let through, since
    the holding may have changed hands after the take -- and by cmd_q_co,
    which asks nothing else of a carried quest. The window (19:00-20:00) is
    events.quest_open's and the level the row's own.

      the holder   a member of the clan that holds the site now;
      standing     in it for box_tenure_hours (24) at least, or a holding
                   clan could invite its friends at 19:00, let each of them
                   collect and put them out at 19:59 -- a clan has no cap on
                   members, nor a pause before rejoining;
      the account  no character of the account (since the day's reset,
                   `since`) has collected this site's row: per_day counts a
                   character, and an account has many."""
    key = getattr(quest, "holders", None)
    if not key:
        return None
    s = site(key)
    if s is None:
        return "no site %r" % (key,)
    held = holder(store, s)
    if held is None:
        return "nobody holds %s" % key
    m = store.clan_member(char_id) if char_id else None
    if m is None or int(m["clan_id"]) != int(held["clan_id"]):
        return "not a member of clan %d, which holds %s" % (int(held["clan_id"]), key)
    # The lab reuses live site ownership, not the warehouse box's account
    # quota or membership tenure. Its personal parts and global crafting
    # slot have separate committed daily limits.
    import quests
    if quest.type in quests.LABORANT_QUESTS:
        return None
    now = time.time() if now is None else now
    t = table()
    if now - int(m["joined_at"]) < t.tenure:
        return "in clan %d for less than %g hours" % (int(held["clan_id"]), t.tenure / 3600)
    if t.one_per_account and account_id is not None and store.account_quests_done_since(
            account_id, since, [quest.type]):
        return "a character of account %d has collected %s today" % (int(account_id), key)
    return None


# --- the kill ------------------------------------------------------------------------------
def snapshot(rc, mob, killer):
    """Who brought a site's boss down, as they stand at the kill (combat.
    RoomCombat.kill, before settle_xp): None unless the room is a site and
    the mob its boss. For every character on the boss's capture ledger:
    the harm, whether a session of his is in the room, alive, at what level,
    and his clan -- read now, so that a member who leaves his clan before
    the corpse fades still counts for the one he fought for; and the
    killer's character and clan."""
    s = site_for(rc.room.loc.id, mob.type_id)
    if s is None:
        return None
    now = bosses.clock()
    if s.kind == "base" and (mob.slot is None or battle_slot(s, now) != mob.slot):
        return None
    if s.kind == "warehouse" and mob.slot is not None and mob.slot < warehouse_reset_at(now):
        return None
    here, local_owners = {}, {}
    for sess in list(rc.room.players):
        if getattr(sess, "char_id", None) and getattr(sess.combat, 'store', rc.store) is rc.store:
            here[int(sess.char_id)] = sess.combat
        elif getattr(getattr(sess, 'ground', None), 'ally', False):
            ground = sess.ground
            if ground.owner.inv.store is rc.store and ground.owner.room is rc.room:
                here[ground.capture_char] = sess.combat
                local_owners[ground.capture_char] = ground.owner.char_id
    store = rc.store
    fighters = []
    harm_by_char = dict(getattr(mob, "capture_harm", {}))
    for char_id, harm in sorted(harm_by_char.items()):
        f = here.get(char_id)
        credited = local_owners.get(char_id, char_id)
        m = store.clan_member(credited)
        fighters.append({"char": int(char_id), "harm": float(harm),
                         "credited": int(credited),
                         "here": f is not None,
                         "alive": f is not None and not f.dead,
                         "level": int(f.level) if f is not None else 0,
                         "clan": int(m["clan_id"]) if m is not None else None,
                         "clan_name": m["clan_name"] if m is not None else None})
    killer_char = killer_clan = killer_actor = None
    ground = getattr(getattr(killer, 'sess', None), 'ground', None)
    if getattr(ground, 'ally', False):
        killer_actor = ground.capture_char
        killer = ground.owner.combat
    if (killer is not None and killer.is_player and getattr(killer.sess, "char_id", None)
            and getattr(killer, 'store', store) is store):
        killer_char = int(killer.sess.char_id)
        if killer_actor is None:
            killer_actor = killer_char
        km = store.clan_member(killer_char)
        killer_clan = int(km["clan_id"]) if km is not None else None
    return {"site": s.key, "slot": mob.slot, "at": now,
            "pool": float(max(1, int(mob.hp_max) + int(mob.sp_max))),
            "fighters": fighters, "killer": killer_char, "killer_clan": killer_clan,
            "killer_actor": killer_actor}


def winner(snap, squad, min_level, excluded=()):
    """The finishing clan qualifies only with an eligible finisher and helpers.

    There is no damage-ranking fallback. Damage is still capped for the log;
    the credited character is the finisher (or a test ally's owner).
    """
    clan = snap['killer_clan']
    if clan is None or clan in excluded or snap['killer'] is None:
        return None
    members = {f['char']: f for f in snap['fighters'] if f['clan'] == clan and f['here']}
    qualified = {f['char']: f for f in members.values()
                 if f['alive'] and f['level'] >= min_level and f['harm'] > 0}
    finisher = qualified.get(snap.get('killer_actor', snap['killer']))
    if len(qualified) < squad or finisher is None:
        return None
    harm = min(sum(f['harm'] for f in members.values()), snap['pool'])
    return clan, finisher['clan_name'], harm, snap['killer']


def _where(s):
    return "%s %s (%d)" % (s.kind, s.key, s.loc)


def _whose(held):
    return "clan %d «%s»" % (int(held["clan_id"]), held["name"]) if held else "nobody"


def base_capture_unavailable(rc, s):
    """A locally spawned/out-of-window boss is not a silent capture failure."""
    for sess in list(rc.room.players):
        sess.answer("База не захвачена: хозяина нужно победить в субботу с 20:00 до 21:00 по Москве.")


def _base_capture_message(s, snap, won, member, excluded, status):
    """Explain the committed outcome using the existing snapshot, not new hits."""
    if status == 'ok':
        day = datetime.fromtimestamp(snap['slot'], bosses.ZONE).date()
        end = next((end for start, end in events.table().window(s.payment).openings(day)
                    if start == snap['slot']), None)
        deadline = ("до %s по Москве" % datetime.fromtimestamp(end, bosses.ZONE).strftime('%H:%M')
                    if end is not None else "до окончания окна оплаты")
        return ("База захвачена кланом «%s». Оплатите аренду у флага %s: %s афро из казны. "
                "Охрана уже дружественна вашему клану; бункер и его льготы откроются после оплаты."
                % (won[1], deadline, format(s.rent, ',').replace(',', ' ')))
    clan = int(member['clan_id']) if member is not None else None
    if clan in excluded:
        return ("Клан уже владеет другой базой или ещё может оплатить её аренду. "
                "Одновременно можно владеть одной клановой базой; склады не учитываются.")
    if status == 'none':
        if clan != snap['killer_clan'] or clan is None:
            return ("База не захвачена вашим кланом: право захвата получает только клан "
                    "добившего хозяина, если минимум три его живых участника нужного уровня нанесли урон.")
        qualified = [f for f in snap['fighters'] if f['clan'] == clan
                     and f['here'] and f['alive'] and f['level'] >= s.min_level and f['harm'] > 0]
        if not any(f['char'] == snap.get('killer_actor', snap['killer']) for f in qualified):
            return ("База не захвачена: добивший хозяина должен быть живым участником вашего клана "
                    "уровня %d+ на этой локации и нанести хозяину урон." % s.min_level)
        return ("База не захвачена: нужны %d живых соклановца уровня %d+ на этой локации, "
                "каждый должен нанести урон хозяину. У вашего клана выполнили условия: %d из %d."
                % (BASE_SQUAD, s.min_level, len(qualified), BASE_SQUAD))
    if status == 'same':
        return "Результат этого захвата уже учтён. Проверьте владельца и задание аренды у флага."
    return "Захват базы не подтверждён: клан больше не существует или право на базу изменилось."


def settle(rc, mob):
    """The holding a site's boss killed settles (combat.RoomCombat.
    corpse_gone, the snapshot taken at the kill): nothing when no clan
    qualifies, a defence when the holder wins, else a capture -- the flag
    re-sent to the room and the box marked afresh (refresh). Every outcome
    is a line in the log and a row in clan_holding_log. Returns "none",
    "defend" or "capture", or None when the kill was no site's."""
    snap = getattr(mob, "capture", None)
    if snap is None:
        return None
    s = site(snap["site"])
    store = rc.store
    if s.kind == "base":
        excluded = {f["clan"] for f in snap["fighters"] if f["clan"] is not None
                    and store.base_reserved(f["clan"], base_keys(), snap["at"], s.key)}
        won = winner(snap, BASE_SQUAD, s.min_level, excluded)
        # A base's capture and the boss's weekly death survive together,
        # before the corpse timer. Warehouses keep their established path.
        with storage.atomic(store.db):
            status = "none"
            if won is not None:
                clan, _name, _harm, credited = won
                _prev, status = store.holding_capture(s.key, clan, snap["slot"],
                                                      credited, snap["at"],
                                                      base_sites=base_keys())
                if status == "occupied":
                    excluded.add(clan)
            else:
                held = holder(store, s)
                prev = int(held["clan_id"]) if held else None
                store.holding_logged(s.key, "none", prev, slot=snap["slot"], when=snap["at"])
            store.boss_killed(rc.boss_spot(mob), snap["slot"])
        # Keep a valid snapshot after rollback/uncertain COMMIT so the
        # existing corpse callback can retry. Consume it before notifications:
        # a broken recipient must never replay an already committed capture.
        mob.capture = None
        for sess in list(rc.room.players):
            member = store.clan_member(sess.char_id) if sess.char_id else None
            sess.answer(_base_capture_message(s, snap, won, member, excluded, status))
        if status == "ok":
            refresh(rc.room, s)
            return "capture"
        return status
    now = bosses.clock()
    boundary = warehouse_reset_at(now)
    if snap["at"] < boundary or snap["slot"] is not None and snap["slot"] < boundary:
        # A delayed corpse from yesterday cannot reassign today's warehouse.
        mob.capture = None
        return "none"
    store.holding_clear(s.key, "expire", when=now, before_since=boundary)
    held = holder(store, s, now)
    prev = int(held["clan_id"]) if held else None
    won = winner(snap, table().squad, s.min_level)
    if won is not None and won[0] != prev:
        clan, name, harm, credited = won
        before, status = store.holding_set(s.key, clan, "capture", by_char=credited,
                                           slot=snap["slot"], when=snap["at"])
        if status == "ok":
            mob.capture = None
            log.info("  ..    %s: clan %d «%s» takes it%s, %d harm, credited char %s,"
                     " window %s", _where(s), clan, name,
                     " from %s" % _whose(held) if held else "", harm, credited,
                     _window(snap["slot"]))
            refresh(rc.room, s)
            return "capture"
        # The clan went between the kill and now (a disband), or the admin
        # gave it the site meanwhile: nothing taken by this kill.
        log.info("  ..    %s: clan %d «%s» won the kill and takes nothing (%s)",
                 _where(s), clan, name, "the clan is gone" if status == "gone"
                 else "it holds the site already")
        held = holder(store, s)
        prev = int(held["clan_id"]) if held else None
        won = None if status == "gone" else won
    if won is not None:
        clan, name, harm, credited = won
        store.holding_logged(s.key, "defend", clan, by_char=credited, slot=snap["slot"], when=snap["at"])
        mob.capture = None
        log.info("  ..    %s: clan %d «%s» keeps it, %d harm, credited char %s, window %s",
                 _where(s), clan, name, harm, credited, _window(snap["slot"]))
        return "defend"
    store.holding_logged(s.key, "none", prev, slot=snap["slot"], when=snap["at"])
    mob.capture = None
    log.info("  ..    %s: its boss killed, and the finishing clan lacked %d living members of level %d"
             " who hurt it in the room; it stays %s's, window %s", _where(s), table().squad,
             s.min_level, _whose(held), _window(snap["slot"]))
    return "none"


def _window(slot):
    return "-" if slot is None else "%d" % int(slot)


# --- the client told ------------------------------------------------------------------------
def refresh(room, s):
    """The holder changed: the flag's frame (userInfo_Trader, and the fellow
    naming the holder after it -- server.Session.send_npc_info) again to
    everybody in its room, which redraws the caption, and the box marked
    afresh (events.touch): on the room's next tick it is shown under a new
    id and the client asks its rows again, the new holders finding the
    offer and the old ones losing it."""
    _resend_flag(room, s)
    _touch_quests(s)


def _touch_quests(s):
    if s.box:
        events.touch(s.box)
    if s.rent_quest:
        events.touch(s.flag)
    import quests
    if s.loc == quests.LABORANT_LOC:
        events.touch(quests.LABORANT_NPC)


def _resend_flag(room, s):
    for eid, npc in list(room.npcs.items()):
        if npc.type_id == s.flag or (s.kind == 'base' and npc.type_id in (s.boss,) + s.guards + s.troops):
            for sess in list(room.players):
                sess.send_npc_info(eid)


def changed(sessions, s):
    """refresh for a change made outside the room (the admin's order, a
    disband): in whichever room of the site somebody stands, from the
    sessions online. A room nobody stands in is drawn as it is when the
    next one walks in; the box is marked afresh all the same."""
    seen = []
    for sess in list(sessions):
        room = getattr(sess, "room", None)
        if room is not None and room.loc.id in s.rooms and all(room is not r for r in seen):
            seen.append(room)
    for room in seen:
        _resend_flag(room, s)
    _touch_quests(s)


def refresh_paid_services(sessions, s):
    """Publish a committed lease without destroying the payer's quest NPC.

    Ownership already changed at capture. Payment only changes offers and
    service rights; the same flag, lifts and traders can receive fresh info.
    """
    for sess in list(sessions):
        room = getattr(sess, "room", None)
        if room is not None and room.loc.id in s.rooms:
            for eid, npc in list(room.npcs.items()):
                if npc.root != world.MOB:
                    sess.send_npc_info(eid)


# --- from outside the kill -------------------------------------------------------------------
def order_hold(store, sessions, s, clan_id):
    """The admin's hold (clan_admin.py): the clan holds the site now. Returns
    (the holding before, "ok" | "same" | "gone"); "same" writes nothing --
    no new since, no row in the log -- so an order run twice is one."""
    before = holder(store, s)
    if s.kind == "warehouse":
        store.holding_clear(s.key, "expire", when=bosses.clock(), before_since=warehouse_reset_at())
    _prev, status = store.holding_set(s.key, clan_id, "admin", when=bosses.clock())
    if status == "ok":
        log.info("  ..    %s: clan %d holds it by the admin's order (it was %s's)",
                 _where(s), int(clan_id), _whose(before))
        changed(sessions, s)
    return before, status


def order_release(store, sessions, s, clan_id):
    """The admin's release (clan_admin.py): nobody holds the site, if this
    clan holds it now; a stale or repeated order changes nothing. Whether
    it did."""
    gone = store.holding_clear(s.key, "admin", clan_id=clan_id)
    if gone is None:
        return False
    log.info("  ..    %s: clan %d holds it no more, by the admin's order: nobody's",
             _where(s), int(gone))
    changed(sessions, s)
    return True


def disbanded(store, sessions, clan_id):
    """A clan was disbanded in the game process (clans.Clans.disbanded):
    accounts.clan_drop dropped its holdings in the same transaction and
    wrote each a 'disband' row; the flags and boxes of those sites are told
    now. A disband in tools/admin_account.py tells nobody: the flags keep
    the old name until they are next drawn, while the box's gate, which
    reads the database, already refuses. Never raises: the disband is done
    by now, and this only tells the rooms."""
    try:
        for key in store.holdings_lost(clan_id):
            s = site(key)
            if s is None:
                continue
            log.info("  ..    %s: clan %d disbanded, nobody holds it", _where(s), int(clan_id))
            changed(sessions, s)
    except Exception:
        log.exception("  !!    the warehouses of disbanded clan %s not told", clan_id)
