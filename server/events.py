"""Events on the clock: the timed windows of data/schedule.json, and what
they open and close -- who stands where, which quests are on offer, which
ways lead anywhere.

The whole-game plan's scheduler (its cross-cutting item 4), written once and
for every region: a place adds rows, not code. Вади-Хальфа's prison is its
first user -- the uprising three times a day, «Усиление режима в 12:00,
16:00 и 23:00» -- and the seasons' calendar its second.

The clock is the bosses' (bosses.clock: Moscow time, LAVA_BOSS_CLOCK for a
test), and a window is never remembered, only computed: whether it is open,
and since when, is asked of the clock every time. A server restarted in the
middle of an uprising has the uprising on; one started out of season has no
season. The bosses keep their own rule (bosses.py: the owner's 14/18/22,
the warehouse masters' 20:00); a window here is everything else that keeps
time.

data/schedule.json (LAVA_SCHEDULE names another file, for a test; like
LAVA_PASSAGES it replaces the table rather than adding to it):

  windows   name -> one of
              {"daily": ["12:00", ...], "minutes": 30, "weekdays": [0, ...]}
                  open at each time of the day for so many minutes; weekdays
                  (0 is Monday) narrows it to those days;
              {"of": "<a daily window>", "from": -15, "to": 30}
                  laid over another's openings, in minutes from each: the
                  gates of an uprising a quarter of an hour before it (over
                  a daily window kept to a season, its openings in season);
              {"dates": [["12-20", "01-15"], ...]}
                  the calendar: from the first day to the last, both whole,
                  a range may run over the new year;
            and "within": "<a dates window>" on a daily one: in season only.
  spawns    [{"window", "loc", "types"}]: the creatures of these types the
            location's own file puts down stand while the window is open,
            and only then -- the prisoners of an uprising, a season's stall
            the rest of the year leaves out (world.EVENT_TOKENS). The room
            never builds them itself (world.belongs_here asks owns); keep
            brings them in and sends them away.
  held_out  [{"loc", "types"}]: of the file's own, never.
  quests    [{"window", "types", "gate"}]: rows on offer only while the
            window is open -- "both": offered and handed in then only, a
            way (data/passages.json 'quest') with them; "hand_in": offered
            any time, handed in then only. The NPCs who give or take them
            are shown under a new id when the window opens or shuts, or the
            client would never ask again (_remark) -- and when who may take
            them changes otherwise, a warehouse's holders (touch).
  loot      [{"locs", "mobs", "obj", "num", "chance"}]: a thing these
            creatures carry in these places, on top of their own table.
  keep_in   [{"types", "locs"}]: things that exist in these places only:
            arriving anywhere else takes them away (take_back), and their
            frame carries the quest flag and no exchange (kept), so no post,
            auction, barter or stall takes them out.

Every row says why; keys starting with _ are notes. Asked by the server
before its first socket (check): a table that does not hold together does
not start the game.
"""
import json
import logging
import os
import weakref
from datetime import date, datetime, timedelta

# Only these two at the top: combat and world import this module, and mobs,
# names and rooms -- asked late, where they are used -- import half the
# server; names.ALL is built at its own import and asks mobs for levels,
# which must not find mobs half-imported (names._mob_level).
import bosses
import world

log = logging.getLogger("lava")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The creatures a window stands in are numbered apart, far above the rooms'
# own counter (rooms.IdAllocator) and below the players' (rooms.
# PLAYER_ID_BASE): one that first comes after its room was built needs an
# id nobody has, and keeps it for the life of the process, as every
# inhabitant does.
FIRST_ID = 800_000
GATES = ("both", "hand_in")
DAY = 24 * 60                   # minutes


def schedule_path():
    """data/schedule.json, or the file LAVA_SCHEDULE names."""
    return os.environ.get("LAVA_SCHEDULE") or os.path.join(HERE, "data", "schedule.json")


def _minute_of_day(text):
    """"12:00" -> 720; "23:5" is 23:05; anything else raises ValueError."""
    h, _, m = str(text).strip().partition(":")
    h, m = int(h), int(m or 0)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(text)
    return h * 60 + m


def _month_day(text):
    """"12-20" -> (12, 20)."""
    m, _, d = str(text).strip().partition("-")
    m, d = int(m), int(d)
    date(2024, m, d)            # a leap year: 02-29 is a day
    return m, d


def _day(year, md):
    """The date of (month, day) in a year; the 29th of February of a year
    that has none is the 28th."""
    m, d = md
    try:
        return date(year, m, d)
    except ValueError:
        return date(year, m, d - 1)


def _midnight(day):
    return datetime(day.year, day.month, day.day, tzinfo=bosses.ZONE).timestamp()


class Window:
    """One window of the table. slot(t) is the whole of its behaviour."""

    def __init__(self, name, rec):
        self.name = name
        self.why = str(rec.get("why") or "")
        self.daily = [_minute_of_day(h) for h in rec.get("daily") or ()]
        self.minutes = float(rec.get("minutes", 0) or 0)
        self.weekdays = frozenset(int(d) for d in rec.get("weekdays", range(7)))
        self.of = rec.get("of")
        self.span = (float(rec.get("from", 0) or 0), float(rec.get("to", 0) or 0))
        self.dates = [(_month_day(a), _month_day(b)) for a, b in rec.get("dates") or ()]
        self.within = rec.get("within")
        kinds = [k for k in ("daily", "of", "dates") if rec.get(k)]
        if len(kinds) != 1:
            raise ValueError("window %s: exactly one of daily, of, dates (has %s)"
                             % (name, kinds or "none"))
        self.kind = kinds[0]
        if self.kind == "daily" and not 0 < self.minutes < DAY:
            raise ValueError("window %s: minutes between 0 and a day" % name)
        if self.kind == "of" and not (-DAY < self.span[0] < self.span[1] < DAY):
            raise ValueError("window %s: from before to, both inside a day" % name)
        if not self.weekdays <= set(range(7)):
            raise ValueError("window %s: weekdays are 0 (Monday) to 6" % name)
        self.base = None            # the window "of" names (Schedule links it)
        self.season = None          # the window "within" names

    def openings(self, day):
        """(start, end) of each opening that belongs to a day, as seconds since
        the epoch: a daily window's times on it, or those laid over its base's
        -- over those in season only, where the base keeps to one (within):
        the gates of a season's event are shut the rest of the year."""
        if self.kind == "of":
            for start, _end in self.base.openings(day):
                if self.base.season is None or self.base.season.slot(start) is not None:
                    yield start + self.span[0] * 60, start + self.span[1] * 60
        elif self.kind == "daily" and day.weekday() in self.weekdays:
            for m in self.daily:
                start = datetime(day.year, day.month, day.day, m // 60, m % 60,
                                 tzinfo=bosses.ZONE).timestamp()
                yield start, start + self.minutes * 60

    def slot(self, t):
        """The opening a moment falls in, named by when it began (seconds
        since the epoch), or None when the window is shut.

        An opening may belong to yesterday (a 23:00 one of an hour is open at
        half past midnight) or to tomorrow (a quarter of an hour before a
        midnight one); where two overlap the later counts, as the bosses'
        windows do (bosses.slot). A season is open from the first moment of
        its first day to the last of its last, and its opening is the
        midnight it began."""
        if self.kind == "dates":
            return self._season(t)
        today = datetime.fromtimestamp(t, bosses.ZONE).date()
        best = None
        for shift in (-1, 0, 1):
            for start, end in self.openings(today + timedelta(days=shift)):
                if start <= t < end and (best is None or start > best):
                    best = start
        if best is not None and self.season is not None and self.season.slot(t) is None:
            return None
        return best

    def _season(self, t):
        today = datetime.fromtimestamp(t, bosses.ZONE).date()
        best = None
        for first, last in self.dates:
            over_new_year = last < first
            for year in (today.year, today.year - 1):
                begin = _day(year, first)
                end = _day(year + 1 if over_new_year else year, last)
                if begin <= today <= end and (best is None or begin > best):
                    best = begin
        return None if best is None else _midnight(best)

    def is_open(self, t):
        return self.slot(t) is not None

    def describe(self):
        if self.kind == "dates":
            return "%s: %s" % (self.name, ", ".join(
                "%02d.%02d-%02d.%02d" % (a[1], a[0], b[1], b[0]) for a, b in self.dates))
        if self.kind == "of":
            return "%s: %+g..%+g min of %s" % (self.name, self.span[0], self.span[1], self.of)
        return "%s: %s for %g min%s" % (
            self.name, ", ".join("%d:%02d" % divmod(m, 60) for m in self.daily), self.minutes,
            " in %s" % self.within if self.within else "")


def _types(v):
    return [int(x) for x in (v if isinstance(v, (list, tuple)) else [v])]


class Schedule:
    """The table, read and linked; problems() says what does not hold."""

    def __init__(self, doc):
        doc = doc if isinstance(doc, dict) else {}
        self.windows = {name: Window(name, rec)
                        for name, rec in (doc.get("windows") or {}).items()
                        if not name.startswith("_")}
        for w in self.windows.values():
            if w.of is not None:
                w.base = self.windows.get(w.of)
                if w.base is None or w.base.kind != "daily":
                    raise ValueError("window %s: 'of' names no daily window (%r)"
                                     % (w.name, w.of))
            if w.within is not None:
                w.season = self.windows.get(w.within)
                if w.season is None or w.season.kind != "dates" or w.kind != "daily":
                    raise ValueError("window %s: 'within' is a daily window's, and names"
                                     " a window of dates (%r)" % (w.name, w.within))
        rows = lambda key: [r for r in doc.get(key) or () if isinstance(r, dict)]
        self.spawns = rows("spawns")
        self.held_out = rows("held_out")
        self.quest_rows = rows("quests")
        self.loot_rows = rows("loot")
        self.keep_rows = rows("keep_in")
        # (loc, type) -> the window that stands it in, or None: held out.
        self.owned = {}
        for rec in self.spawns:
            for t in _types(rec.get("types")):
                self.owned[(int(rec["loc"]), t)] = self.window(rec.get("window"))
        for rec in self.held_out:
            for t in _types(rec.get("types")):
                self.owned[(int(rec["loc"]), t)] = None
        # quest type -> (window, gate)
        self.gates = {}
        for rec in self.quest_rows:
            gate = rec.get("gate", "both")
            if gate not in GATES:
                raise ValueError("quests row %r: gate is one of %s" % (rec, GATES))
            for t in _types(rec.get("types")):
                self.gates[t] = (self.window(rec.get("window")), gate)
        # (loc, mob) -> [(thing, pieces, chance)]
        self.loot = {}
        for rec in self.loot_rows:
            for loc in _types(rec.get("locs")):
                for mob in _types(rec.get("mobs")):
                    self.loot.setdefault((loc, mob), []).append(
                        (int(rec["obj"]), int(rec.get("num", 1)), float(rec.get("chance", 1))))
        self.keep_in = [(frozenset(_types(r.get("types"))), frozenset(_types(r.get("locs"))))
                        for r in self.keep_rows]
        self._marked = None         # NPC type -> [window] (marked, made on first asking)

    def marked(self):
        """NPC type -> the windows the rows it gives or takes hang on (quests):
        the giver and the taker of a "both" row, the taker of a "hand_in" one
        -- whose marks the client must be made to ask again (_remark)."""
        if self._marked is None:
            import quests                   # late: see the imports
            self._marked = {}
            for qtype, (window, gate) in sorted(self.gates.items()):
                q = quests.get(qtype)
                for npc_type in (q.take if gate == "hand_in" else q.give + q.take) if q else ():
                    got = self._marked.setdefault(int(npc_type), [])
                    if window not in got:
                        got.append(window)
        return self._marked

    def window(self, name):
        w = self.windows.get(name)
        if w is None:
            raise ValueError("no window %r in data/schedule.json" % (name,))
        return w

    def problems(self, mob_types):
        """["what: why"] for every row that cannot work as written; empty when
        all of them can."""
        import items                    # late: see the imports
        import names
        import quests
        out = []

        def place(what, loc_id):
            try:
                return world.location(int(loc_id))
            except (KeyError, OSError, ValueError, TypeError, AttributeError) as exc:
                out.append("%s: no location %s (%s)" % (what, loc_id, exc))
                return None

        for name, w in sorted(self.windows.items()):
            if not w.why.strip():
                out.append("window %s: no why" % name)
        for key, recs in (("spawns", self.spawns), ("held_out", self.held_out)):
            for rec in recs:
                what = "%s %s %s" % (key, rec.get("loc"), rec.get("types"))
                if not str(rec.get("why") or "").strip():
                    out.append("%s: no why" % what)
                loc = place(what, rec.get("loc"))
                if loc is None:
                    continue
                files = {t for _c, t in loc.spawns}
                for t in _types(rec.get("types")):
                    if t not in files:
                        out.append("%s: %d is not in the location's file" % (what, t))
                    elif key == "spawns" and world.retired_creature(t):
                        # The window stands its creatures itself, past
                        # world.belongs_here: out of the game is out of it
                        # at every hour (data/retired.json).
                        out.append("%s: %d is a creature out of the game (data/retired.json)"
                                   % (what, t))
                    elif key == "spawns" and (t not in mob_types or not names.known(t)):
                        out.append("%s: %d is a creature the client has no record or name of"
                                   % (what, t))
                    elif key == "spawns" and world.creature_role(t) == "object":
                        out.append("%s: %d is a thing, not an inhabitant" % (what, t))
                    elif key == "spawns" and mob_types[t][0] == world.MOB and not loc.war:
                        out.append("%s: %d is hostile, and the place is at peace" % (what, t))
        for rec in self.quest_rows:
            what = "quests %s" % rec.get("types")
            if not str(rec.get("why") or "").strip():
                out.append("%s: no why" % what)
            for t in _types(rec.get("types")):
                if quests.get(t) is None:
                    out.append("%s: no quest %d in the table" % (what, t))
        for rec in self.loot_rows:
            what = "loot %s" % rec.get("obj")
            if not str(rec.get("why") or "").strip():
                out.append("%s: no why" % what)
            obj = int(rec.get("obj", 0))
            if items.params_of(obj) is None or items.premium(obj):
                out.append("%s: no thing of the game's, or a premium one" % what)
            if not 0 < float(rec.get("chance", 1)) <= 1 or int(rec.get("num", 1)) < 1:
                out.append("%s: a chance in (0, 1] and at least one piece" % what)
            for loc in _types(rec.get("locs")):
                place(what, loc)
            for mob in _types(rec.get("mobs")):
                if mob not in mob_types:
                    out.append("%s: no creature %d" % (what, mob))
        for rec in self.keep_rows:
            what = "keep_in %s" % rec.get("types")
            if not str(rec.get("why") or "").strip():
                out.append("%s: no why" % what)
            for t in _types(rec.get("types")):
                if items.params_of(t) is None:
                    out.append("%s: no thing %d" % (what, t))
            for loc in _types(rec.get("locs")):
                place(what, loc)
        return out


_TABLE = None


def table():
    """The schedule, read once. No file is no events, and the world stands as
    it did before the table existed; a file that does not parse raises, and
    the server does not start on it (check)."""
    global _TABLE
    if _TABLE is None:
        path = schedule_path()
        doc = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        _TABLE = Schedule(doc)
    return _TABLE


def check(mob_types):
    """Raise ValueError naming every row of the table that cannot work. The
    server asks this before its first socket: a room is only built on its
    first entry, too late to say no."""
    problems = table().problems(mob_types)
    if problems:
        raise ValueError("data/schedule.json: " + "; ".join(problems))


def describe():
    """One line for the start-up log: the windows and what they hold."""
    t = table()
    if not t.windows:
        return "no timed windows (data/schedule.json)"
    now = bosses.clock()
    return "timed windows: " + "; ".join(
        "%s%s" % (w.describe(), " (open)" if w.is_open(now) else "")
        for _n, w in sorted(t.windows.items()))


def is_open(name, t=None):
    """Whether the named window is open now (or at t)."""
    return table().window(name).is_open(bosses.clock() if t is None else t)


# --- who stands ------------------------------------------------------------------------------
def owns(loc_id, type_id):
    """Whether a creature of this type in this location's file is the
    schedule's to stand in and send away (spawns) or to keep out (held_out),
    and not the room's (world.belongs_here)."""
    if loc_id is None:
        return False
    return (int(loc_id), int(type_id)) in table().owned


class _Entry(object):
    """One spawn point a window keeps: where, who, under which id."""
    __slots__ = ("window", "cell", "type_id", "root", "eid", "mob")

    def __init__(self, window, cell, type_id, root, eid):
        self.window, self.cell, self.type_id, self.root, self.eid = \
            window, cell, type_id, root, eid
        self.mob = None


_ROOMS = weakref.WeakKeyDictionary()      # rooms.Room -> [_Entry]
_SHOWN = weakref.WeakKeyDictionary()      # rooms.Room -> {npc id: what it was shown under}
_TAKEN = {}                               # NPC type -> takes of its rows under a shut gate
_TOUCHED = {}                             # NPC type -> changes of who may take its rows (touch)
_NEXT_ID = [FIRST_ID]
_MOB_TYPES = None


def _new_id():
    eid = _NEXT_ID[0]
    _NEXT_ID[0] += 1
    return eid


def _mob_types():
    global _MOB_TYPES
    if _MOB_TYPES is None:
        _MOB_TYPES = world.mob_types()
    return _MOB_TYPES


def _entries(room):
    """The room's spawn points a window keeps, made on first asking, one id
    each for the life of the process."""
    got = _ROOMS.get(room)
    if got is None:
        import names                    # late: see the imports
        got = []
        sched = table()
        mt = _mob_types()
        for cell, t in room.loc.spawns:
            w = sched.owned.get((room.loc.id, t))
            # Held out, or none of the schedule's; one the client cannot draw
            # or name is left out, as the room leaves it (rooms.Room).
            if w is None or t not in mt or not names.known(t):
                continue
            got.append(_Entry(w, cell, t, world.entity_root(t, mt[t][0]), _new_id()))
        _ROOMS[room] = got
    return got


def keep(rc):
    """A room's creatures of the schedule in step with the clock.

    Asked where the bosses are (combat.RoomCombat.keep_hours): on every tick
    of a room with somebody in it, and before anybody arriving is shown who
    is here -- an empty room has no tick, and a window that opened or shut
    meanwhile must be found as it is.

    A creature that fights arrives the way a boss does, on its own cell,
    whole (RoomCombat.respawn), and leaves at the end of its window -- but
    not in the middle of a fight: it finishes it and starts no new one
    (Mob.leaving). Killed inside its window, it is back after the respawn
    delay like any of its kind -- the prisoners of an uprising keep coming
    while it lasts -- unless it is a boss (bosses.keeps_hours), which comes
    once an opening: the godfather killed is gone until the next uprising.
    Killed and the window shut before its respawn, it is not made
    (RoomCombat.respawn asks mob.away). Anybody else -- a medic, a stall --
    is simply there while the window is open: lch;newUser and his details,
    then lch;lostUser; under a new id each time he comes, so that the
    client asks his rows afresh (_remark), a day's task done yesterday
    included. Then the marks over those whose rows a window keeps (_remark).
    """
    t = bosses.clock()
    slots = {}
    for e in _entries(rc.room):
        if e.window.name not in slots:
            slots[e.window.name] = e.window.slot(t)
        due = slots[e.window.name]
        if e.root == world.MOB:
            _keep_mob(rc, e, due)
        else:
            _keep_npc(rc.room, e, due)
    _remark(rc.room, t)


def _keep_mob(rc, e, due):
    import mobs                         # late: see the imports
    mob = e.mob
    if mob is None:
        # Made away, as a boss out of its hours is: out of the room's
        # inhabitants, in the fight's list, never an actor while not alive.
        mob = e.mob = mobs.Mob(e.eid, e.type_id, e.cell)
        mob.alive, mob.away = False, True
        rc.mobs[e.eid] = mob
    once = bosses.keeps_hours(mob.type_id)
    if mob.away:
        if due is not None and not (once and due == mob.slot):
            mob.slot, mob.away = due, False
            rc.respawn(mob)
            log.info("  ..    %d (%s) comes to %s for window %s", mob.eid, mob.stats.name,
                     rc.room.loc.title, e.window.name)
    elif not mob.alive:
        if due is None:
            mob.away = True
    elif due is not None:
        mob.slot, mob.leaving = due, False
    elif mob.target is None and mob.aim is None:
        mob.alive, mob.away, mob.leaving, mob.target = False, True, False, None
        rc.room.npcs.pop(mob.eid, None)
        rc.room.broadcast(("lch", dict(lostUser=mob.eid)))
        log.info("  ..    %d (%s) leaves %s: window %s shut", mob.eid, mob.stats.name,
                 rc.room.loc.title, e.window.name)
    else:
        mob.leaving = True


def _keep_npc(room, e, due):
    import rooms                        # late: see the imports
    here = e.eid in room.npcs
    if due is not None and not here:
        e.eid = _new_id()
        room.npcs[e.eid] = rooms.NPC(e.cell, e.type_id, e.root)
        for sess in list(room.players):
            sess.send("lch", newUser=e.eid, pos=e.cell, rtype=e.root)
            sess.send_npc_info(e.eid)
        log.info("  ..    %d (type %d) comes to %s for window %s", e.eid, e.type_id,
                 room.loc.title, e.window.name)
    elif due is None and here:
        room.npcs.pop(e.eid, None)
        _SHOWN.get(room, {}).pop(e.eid, None)
        room.broadcast(("lch", dict(lostUser=e.eid)))
        log.info("  ..    %d (type %d) leaves %s: window %s shut", e.eid, e.type_id,
                 room.loc.title, e.window.name)


def _remark(room, t):
    """The marks over the NPCs whose rows a window keeps, in step with it.

    The client asks whether a row is on offer (q_status) once per type, and
    again only for an NPC id it has not met -- or, all of them, after a
    hand-in or a drop answered 0 (QuestInspector.checkQStatus, takeAck,
    cancelAck -> requestAllNPC); the server is never asked otherwise, and
    never tells unasked. So a window opening or shutting before a player
    who stands waiting by the guard would change nothing on his screen:
    the gate would stay shut to him until he handed in something else, and
    open after the uprising. An NPC who gives or takes such a row
    (Schedule.marked) is shown under a new id whenever one of its windows
    has opened or shut since he was shown -- lch;lostUser, then lch;newUser
    and his details, as a respawn is -- and the client, meeting an id it
    has not seen, asks his rows again. On every tick of the room, for
    whoever stands in it, and before a newcomer is shown who is here
    (keep). Mobs never are. The taker of a "hand_in" row is shown anew
    too once the row was taken with its gate shut (taken): the client asks
    nothing after a take, and would go on offering the hand-in the server
    refuses. And so is one whose rows changed hands outside the clock
    (touch): a warehouse's box when its holders change.
    """
    marked = table().marked()
    if not marked:
        return
    shown = _SHOWN.setdefault(room, {})
    for eid, npc in list(room.npcs.items()):
        windows = marked.get(npc.type_id)
        if not windows or npc.root == world.MOB:
            continue
        now = tuple(w.slot(t) for w in windows) + (_TAKEN.get(npc.type_id, 0),
                                                   _TOUCHED.get(npc.type_id, 0))
        if shown.setdefault(eid, now) == now:
            continue
        new = _new_id()
        del room.npcs[eid], shown[eid]
        room.npcs[new] = npc
        shown[new] = now
        for e in _ROOMS.get(room, ()):
            if e.eid == eid:
                e.eid = new
        room.broadcast(("lch", dict(lostUser=eid)))
        for sess in list(room.players):
            sess.send("lch", newUser=new, pos=npc.cell, rtype=npc.root)
            sess.send_npc_info(new)
        log.info("  ..    %d (type %d) in %s shown again as %d: its rows' window moved",
                 eid, npc.type_id, room.loc.title, new)


def taken(quest_type):
    """A row taken (Session.cmd_q_st). One whose hand-in only a window lets
    through ("hand_in"), taken while it is shut, has its takers marked
    afresh (_remark): the client had it on offer at the giver's, will not
    ask again, and at a taker already met would offer the hand-in the
    server refuses -- a refusal the client reads as the day's tasks used
    up (ErrorReport 44)."""
    got = table().gates.get(int(quest_type))
    if got is None or got[1] != "hand_in" or got[0].is_open(bosses.clock()):
        return
    import quests                       # late: see the imports
    for npc_type in quests.get(quest_type).take:
        _TAKEN[int(npc_type)] = _TAKEN.get(int(npc_type), 0) + 1


def touch(npc_type):
    """Who may take an NPC's rows changed by something other than the clock:
    a warehouse's holders (holdings.py), whose box offers its row to the
    holding clan alone. The client asked about the box when it met it and
    will not ask again, so on the room's next tick it is shown under a new
    id (_remark) -- the new holders find the offer, the old ones lose it.
    Only an NPC whose rows a window keeps (Schedule.marked) is marked anew."""
    _TOUCHED[int(npc_type)] = _TOUCHED.get(int(npc_type), 0) + 1


# --- quests, loot, things --------------------------------------------------------------------
def quest_open(quest_type, carried=False):
    """Whether a row the schedule keeps (quests) is on offer now: always for
    one it does not keep; for a "hand_in" gate, always to take and only in
    the window to hand in (carried); for "both", in the window only."""
    got = table().gates.get(int(quest_type))
    if got is None:
        return True
    window, gate = got
    if gate == "hand_in" and not carried:
        return True
    return window.is_open(bosses.clock())


def loot(loc_id, mob_type, rng):
    """[(type, pieces)] a creature killed here carries on top of its own
    table (combat.RoomCombat.drop_loot): a prisoner's red armband."""
    out = []
    for obj, num, chance in table().loot.get((int(loc_id), int(mob_type)), ()):
        if chance >= 1 or rng.random() < chance:
            out.append((obj, num))
    return out


def kept(type_id):
    """Whether a thing exists in certain places only (keep_in). Its frame
    carries the quest flag and no exchange (items.static_info), as a lent
    thing's does: no post, auction, barter or stall carries it out of them
    -- a letter would reach anybody anywhere, and take_back is asked only
    of whoever arrives."""
    return any(int(type_id) in types for types, _locs in table().keep_in)


def take_back(sess):
    """Things that exist in certain places only (keep_in) taken away from a
    character arriving anywhere else, whichever way -- the way out handed
    in, a death sent home, a login put back elsewhere -- out of the bag, the
    hands, the body and the bank (Inventory.reclaim_pieces). Before the
    lcall, as Session.keep_lent, while the client still has the bag. Returns
    how many pieces went."""
    if not sess.char_id or sess.loc is None:
        return 0
    taken = 0
    for types, locs in table().keep_in:
        if sess.loc.id in locs:
            continue
        for t in sorted(types):
            taken += sess.inv.reclaim_pieces(t, 1 << 30)
    if taken:
        log.info("  ..    %d pieces stay behind: %s is not where they are kept",
                 taken, sess.loc.file)
        sess.inv.refresh_gear()
    return taken
