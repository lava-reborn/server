"""Warehouses a clan holds: taken by killing the warehouse's boss.

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
every window of its hours settles a site once at most: the owner's 14:00,
18:00 and 20:00, Moscow time.

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
  the box   the daily «Патроны и афро владельцам склада» (data/quests.json
            765-767, holders), at the box from 19:00 to 20:00 (data/
            schedule.json wh_box): to a member of the holding clan of a
            day's standing, one character of an account a day (box_refusal,
            asked at the take and at the hand-in).

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
import json
import logging
import os
import time

import events
import world

log = logging.getLogger("lava")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "data", "holdings.json")

# What a row of clan_holding_log says happened (accounts.SCHEMA).
HOW = ("capture", "defend", "none", "admin", "disband")


class Site(object):
    """One capturable place of data/holdings.json."""
    __slots__ = ("key", "loc", "boss", "flag", "box", "quest", "min_level", "title")

    def __init__(self, key, rec):
        self.key = str(key)
        self.loc = int(rec["loc"])
        self.boss = int(rec["boss"])
        self.flag = int(rec["flag"])
        self.box = int(rec["box"])
        self.quest = int(rec["quest"])
        self.min_level = int(rec["min_level"])
        self.title = str(rec["title"])


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
            if s.loc in self.by_loc:
                raise ValueError("data/holdings.json: %s and %s are both location %d"
                                 % (self.by_loc[s.loc].key, s.key, s.loc))
            self.by_loc[s.loc] = s


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
    return s if s is not None and s.boss == int(boss_type) else None


# --- the table holds together ----------------------------------------------------------
def problems():
    """["what: why"] for every site that cannot work as written; empty when
    all of them can. Each location's file holds the site's boss, flag and
    box; the box's row (data/quests.json) names the site in holders, asks
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
    held = holder(store, s)
    return held, member_of(store, held, char_id)


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
    here = {}
    for sess in list(rc.room.players):
        if getattr(sess, "char_id", None):
            here[int(sess.char_id)] = sess.combat
    store = rc.store
    fighters = []
    for char_id, harm in sorted(getattr(mob, "capture_harm", {}).items()):
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
    return {"site": s.key, "slot": mob.slot,
            "pool": float(max(1, int(mob.hp_max) + int(mob.sp_max))),
            "fighters": fighters, "killer": killer_char, "killer_clan": killer_clan}


def winner(snap, squad, min_level):
    """(clan, its name, the harm counted, the member credited) of the clan
    that takes the site by this kill, or None (the module's docstring): of
    the clans with `squad` members in the room, alive, at min_level or
    above, with harm on the boss, the one with the most harm of all its
    members in the room, capped at the boss's health and stamina; a tie to
    the killing blow's clan, else the lowest id. Credited is the killer when
    he is of it, else its member with the most harm."""
    totals, squads, names, best_of = {}, {}, {}, {}
    for f in snap["fighters"]:
        clan = f["clan"]
        if clan is None or not f["here"]:
            continue
        totals[clan] = totals.get(clan, 0.0) + f["harm"]
        names[clan] = f["clan_name"]
        if f["alive"] and f["level"] >= min_level and f["harm"] > 0:
            squads[clan] = squads.get(clan, 0) + 1
        top = best_of.get(clan)
        if top is None or (f["harm"], -f["char"]) > (top["harm"], -top["char"]):
            best_of[clan] = f
    counted = {c: min(h, snap["pool"]) for c, h in totals.items()
               if squads.get(c, 0) >= squad}
    if not counted:
        return None
    most = max(counted.values())
    tied = sorted(c for c, h in counted.items() if h == most)
    clan = snap["killer_clan"] if snap["killer_clan"] in tied else tied[0]
    credited = snap["killer"] if snap["killer_clan"] == clan else best_of[clan]["char"]
    return clan, names[clan], counted[clan], credited


def _where(s):
    return "warehouse %s (%d)" % (s.key, s.loc)


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
    events.touch(s.box)


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
        if room is not None and room.loc.id == s.loc and all(room is not r for r in seen):
            seen.append(room)
    for room in seen:
        _resend_flag(room, s)
    events.touch(s.box)


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
