"""Warehouses a clan holds: taken by killing the warehouse's boss.

Weekly bases use these same holdings (kind "base" in the table), not a
second ownership system. Their original surfaces/interiors share one site.
The Saturday 20:00–21:00 Moscow kill grants a payment reservation; the
winning clan pays 1,500,000 afro from its treasury by 21:15, then owns the
benefits until next Saturday 19:55, five minutes before the battle. Each week needs a new capture
and payment. Three bodyguards and six outer soldiers must die before the
master appears. One clan may reserve/lease one base; warehouses do not count.
At least three living clan members of the site's minimum level must be in
the boss's room at the kill; only one of them needs to hurt him. Capture and weekly
boss-death record commit at the kill, before the corpse timer. Everything
below describes the existing warehouses unless it explicitly names a base.

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

Who takes it. Only a clan: the map labels' «Захват возможен игроками 8
уровня при поддержке клана» (12 for the south one; data/holdings.json
min_level). When the site's boss dies in its room, a clan qualifies if at
least `squad` (2) of its members stand in the room at the kill, alive, at
the site's level or above, and hurt the boss since its last full heal; of
the clans that qualify, the one that did it the most harm takes the site --
every member in the room counting for it, alive or dead, below the level or
not, and a clan's harm never more than the boss's health and stamina
together. A tie goes to the clan of the killing blow if it is among the
tied, else to the older clan, the lower id. A clanless killer takes
nothing, nor does a stranger's last shot take a warehouse two members wore
down. No party is asked for, and diplomacy plays no part (the owner's
decision 7: war is colours and notices). DESIGNED: the plan's default 16,
«отряд из 2+ членов клана убивает «Хозяина» в окне; уровень — по подписи»;
who got the credit in the original is not recorded.

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

How long. DESIGNED, the owner's of 2026-10-09: the clan holds the site until
another clan takes it. A disband drops its holdings in the same transaction
(accounts.clan_drop), and the admin may set or clear one (clan_admin.py
hold, release). No decay, no rent; a kill that qualifies nobody changes
nothing.

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

What is said. Nothing in the chat (the owner, 2026-10-09: no lines of the
server's about captures): every outcome -- a capture, a defence, a kill that
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
import copy
import json
import logging
import math
import os
import time

import bosses
import events
import storage
import world

log = logging.getLogger("lava")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "data", "holdings.json")

# What a row of clan_holding_log says happened (accounts.SCHEMA).
HOW = ("capture", "defend", "none", "admin", "disband", "rent", "expire")
BASE_SQUAD = 3
BASE_RESET_LEAD = 5 * 60


class Site(object):
    """One capturable place of data/holdings.json."""
    __slots__ = ("key", "loc", "boss", "flag", "box", "quest", "min_level", "title",
                 "kind", "rooms", "traders", "rent_quest", "rent", "battle", "payment",
                 "gold_quest", "health_scale", "guards", "guard_health_scale",
                 "damage_scale", "guard_damage_scale", "troops", "troop_health_scale")

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
        for field in ('health_scale', 'guard_health_scale', 'damage_scale', 'guard_damage_scale',
                      'troop_health_scale'):
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
    for target in rc.mobs.values():
        s = site_for(rc.room.loc.id, target.type_id) or guard_site(rc.room.loc.id, target.type_id)
        if s is None or getattr(target, "_holding_prepared", False):
            continue
        target.stats = copy.copy(target.stats)
        if target.type_id == s.boss:
            scale, damage = s.health_scale, s.damage_scale
        elif target.type_id in s.guards:
            scale, damage = s.guard_health_scale, s.guard_damage_scale
        else:
            scale, damage = s.troop_health_scale, 1
        target.stats.hp_max = max(1, int(round(target.stats.hp_max * scale)))
        target.stats.sp_max = max(0, int(round(target.stats.sp_max * scale)))
        target.stats.dmg_min = max(0, int(round(target.stats.dmg_min * damage)))
        target.stats.dmg_max = max(target.stats.dmg_min, int(round(target.stats.dmg_max * damage)))
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


def guards_cleared(rc, s, slot):
    """All scheduled defenders must have died in this window, not earlier."""
    guards = [m for m in rc.mobs.values() if m.type_id in s.guards + s.troops]
    return bool(guards) and all(not m.alive and m.slot == slot for m in guards)


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


def paid_holder(store, s, now=None):
    """Only a current paid lease owns a base's benefits and public caption."""
    held = holder(store, s)
    now = bosses.clock() if now is None else now
    if (held is None or held["slot"] is None
            or not float(held["slot"]) <= now < min(float(held["paid_until"]),
                                                    float(held["slot"]) + 7 * 86400 - BASE_RESET_LEAD)
            or float(held["paid_until"]) > float(held["slot"]) + 7 * 86400):
        return None
    return held


def paid_base_for(store, loc_id, char_id, now=None):
    """The character's paid base in this room; native NPC rights stay native."""
    s = base_for(loc_id)
    if s is None or not member_of(store, paid_holder(store, s, now), char_id):
        return None
    return s


def defender_friendly(rc, mob, fighter):
    """Only a paid base's own defenders spare its current clan members."""
    if not getattr(fighter, 'is_player', False):
        return False
    s = base_for(rc.room.loc.id, mob.type_id) or guard_site(rc.room.loc.id, mob.type_id)
    if s is None or s.kind != 'base':
        return False
    return member_of(rc.store, paid_holder(rc.store, s), fighter.sess.char_id)


def rent_refusal(store, s, char_id, loc_id=None, now=None):
    """Rechecked at both native quest offer and hand-in, never a purse fee."""
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
            if (q is None or not q.service or not q.repeatable or q.level != s.min_level
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
def holder(store, s):
    """The site's holding -- site, clan_id, name, since, by_char, slot
    (Store.holding) -- or None: nobody holds it."""
    return store.holding(s.key)


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
    held = paid_holder(store, s) if s.kind == "base" else holder(store, s)
    return held, s.kind != "base" and member_of(store, held, char_id)


def may_repair(store, loc_id, trader_type, char_id):
    """Whether a repair at this trader may go ahead (inventory.Inventory.
    repair): anywhere but at a site's flag in its room, always; there, for a
    member of the holding clan only."""
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
    if s.kind == "base" and (mob.slot is None or battle_slot(s, now) != mob.slot
                             or not guards_cleared(rc, s, mob.slot)):
        return None
    here = {}
    for sess in list(rc.room.players):
        if getattr(sess, "char_id", None):
            here[int(sess.char_id)] = sess.combat
    store = rc.store
    fighters = []
    harm_by_char = dict(getattr(mob, "capture_harm", {}))
    if s.kind == "base":
        # Base support counts by presence at the kill, without requiring a
        # token shot from every member. Ordinary warehouses keep harm-only squads.
        for char_id in here:
            harm_by_char.setdefault(char_id, 0)
    for char_id, harm in sorted(harm_by_char.items()):
        f = here.get(char_id)
        m = store.clan_member(char_id)
        fighters.append({"char": int(char_id), "harm": float(harm),
                         "here": f is not None,
                         "alive": f is not None and not f.dead,
                         "level": int(f.level) if f is not None else 0,
                         "clan": int(m["clan_id"]) if m is not None else None,
                         "clan_name": m["clan_name"] if m is not None else None})
    killer_char = killer_clan = None
    if killer is not None and killer.is_player and getattr(killer.sess, "char_id", None):
        killer_char = int(killer.sess.char_id)
        km = store.clan_member(killer_char)
        killer_clan = int(km["clan_id"]) if km is not None else None
    return {"site": s.key, "slot": mob.slot, "at": now,
            "pool": float(max(1, int(mob.hp_max) + int(mob.sp_max))),
            "fighters": fighters, "killer": killer_char, "killer_clan": killer_clan}


def winner(snap, squad, min_level, excluded=(), require_harm=True):
    """(clan, its name, the harm counted, the member credited) of the clan
    that takes the site by this kill, or None (the module's docstring): of
    the clans with `squad` members in the room, alive, at min_level or
    above (each with harm unless require_harm is false), the one with the
    most harm of all its members in the room, capped at the boss's health and stamina; a tie to
    the killing blow's clan, else the lowest id. Credited is the killer when
    he is of it, else its member with the most harm."""
    totals, squads, names, best_of = {}, {}, {}, {}
    for f in snap["fighters"]:
        clan = f["clan"]
        if clan is None or clan in excluded or not f["here"]:
            continue
        totals[clan] = totals.get(clan, 0.0) + f["harm"]
        names[clan] = f["clan_name"]
        if f["alive"] and f["level"] >= min_level and (not require_harm or f["harm"] > 0):
            squads[clan] = squads.get(clan, 0) + 1
        top = best_of.get(clan)
        if top is None or (f["harm"], -f["char"]) > (top["harm"], -top["char"]):
            best_of[clan] = f
    counted = {c: min(h, snap["pool"]) for c, h in totals.items()
               if h > 0 and squads.get(c, 0) >= squad}
    if not counted:
        return None
    most = max(counted.values())
    tied = sorted(c for c, h in counted.items() if h == most)
    clan = snap["killer_clan"] if snap["killer_clan"] in tied else tied[0]
    credited = snap["killer"] if snap["killer_clan"] == clan else best_of[clan]["char"]
    return clan, names[clan], counted[clan], credited


def _where(s):
    return "%s %s (%d)" % (s.kind, s.key, s.loc)


def _whose(held):
    return "clan %d «%s»" % (int(held["clan_id"]), held["name"]) if held else "nobody"


def settle(rc, mob):
    """The holding a site's boss killed settles (combat.RoomCombat.
    corpse_gone, the snapshot taken at the kill): nothing when no clan
    qualifies, a defence when the holder wins, else a capture -- the flag
    re-sent to the room and the box marked afresh (refresh). Every outcome
    is a line in the log and a row in clan_holding_log. Returns "none",
    "defend" or "capture", or None when the kill was no site's."""
    snap, mob.capture = getattr(mob, "capture", None), None
    if snap is None:
        return None
    s = site(snap["site"])
    store = rc.store
    if s.kind == "base":
        excluded = {f["clan"] for f in snap["fighters"] if f["clan"] is not None
                    and store.base_reserved(f["clan"], base_keys(), snap["at"], s.key)}
        won = winner(snap, BASE_SQUAD, s.min_level, excluded, require_harm=False)
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
        for sess in list(rc.room.players):
            member = store.clan_member(sess.char_id) if sess.char_id else None
            if member is not None and int(member["clan_id"]) in excluded:
                sess.answer("Клан уже владеет другой базой или ещё может оплатить её аренду."
                            " Одновременно можно владеть одной клановой базой; склады не учитываются.")
        if status == "ok":
            refresh(rc.room, s)
            return "capture"
        return status
    held = holder(store, s)
    prev = int(held["clan_id"]) if held else None
    won = winner(snap, table().squad, s.min_level)
    if won is not None and won[0] != prev:
        clan, name, harm, credited = won
        before, status = store.holding_set(s.key, clan, "capture", by_char=credited,
                                           slot=snap["slot"])
        if status == "ok":
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
        store.holding_logged(s.key, "defend", clan, by_char=credited, slot=snap["slot"])
        log.info("  ..    %s: clan %d «%s» keeps it, %d harm, credited char %s, window %s",
                 _where(s), clan, name, harm, credited, _window(snap["slot"]))
        return "defend"
    store.holding_logged(s.key, "none", prev, slot=snap["slot"])
    log.info("  ..    %s: its boss killed, and no clan had %d living members of level %d"
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
        if npc.type_id == s.flag:
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


# --- from outside the kill -------------------------------------------------------------------
def order_hold(store, sessions, s, clan_id):
    """The admin's hold (clan_admin.py): the clan holds the site now. Returns
    (the holding before, "ok" | "same" | "gone"); "same" writes nothing --
    no new since, no row in the log -- so an order run twice is one."""
    before = holder(store, s)
    _prev, status = store.holding_set(s.key, clan_id, "admin")
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
