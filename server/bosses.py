"""Bosses keep hours: they stand in their place only at set times of day.

The owner's rule (2026-09-24): «босс постоянно не должен быть в локации, а
только в 18 и 20 часов», and on 2026-10-02 «добавь ещё боссов на 14
часов»: 14, 18 and 20; and on 2026-10-11 «давай 14 18 22»: 14, 18 and
22. What data/mob_types.json calls a boss -- the named
mrare_ leaders, the LandLords and godfathers, the camp, warehouse and
instance bosses: 191 spawn points in 169 war locations -- used to stand
there all day and come back RESPAWN_DELAY after every kill like the rest of
its camp. Now it arrives at each of the hours, Moscow time, stays until it
is killed or its stay runs out, and then leaves; killed, it is gone until
the next hour, however soon the rest of the camp is back.

DESIGNED, not recovered: the hours are the owner's. The original's own
timetable lived in the serverdata node of the location files, which was
stripped, and only its announcements survive in the map's tooltips
(res/database/locations.xml): Вади-Хальфа's camps «В 18:00 и 22:00 часто
кто-то приезжает... встреча с главарем» and «Сражение за чертежи в 01.00,
05.00, 18:00 и 22:00», the warehouses «Хозяин присутствует с 20:00 до
21:00», the prison «Усиление режима в 12:00, 16:00 и 23:00». The owner's 14, 18
and 22 are kept over them (18 and 22 are the camps' labels' own, 14 is the
owner's) -- but for the prison, whose uprising keeps its
label's hours as a window of data/schedule.json (events.py, on this
module's clock). This module only knows the clock;
combat.RoomCombat.keep_hours is what brings a room's bosses in and sends
them away.

The warehouses' «Хозяин склада» keeps hours of his own: the owner's
«на складах хозяин должен прриходить один раз!!!» (2026-10-12) -- once a
day. DESIGNED, the default: at 20:00, the hour of the original's own label
«Хозяин присутствует с 20:00 до 21:00», right after the money box's «Дележ
добычи с 19:00 до 20:00» (data/schedule.json wh_box); the map shows that
label again as the original has it (data/map_labels.json). He stays STAY
like every boss; killed, he is gone until tomorrow's hour, and at 14, 18
and 22 he does not come. A master killed in his window hands the warehouse
to a clan (holdings.py), so a day settles it once.

    LAVA_BOSS_HOURS  "14,18,22"       the hours, H or H:MM on that clock.
                                      "off" turns the rule off, and a boss is
                                      an ordinary mob again, which drops no
                                      gold ingot (combat.RoomCombat.
                                      drop_loot) -- the warehouse masters
                                      too; blank, or not one hour in it, is
                                      the default
    LAVA_WAREHOUSE_HOURS "20"         the warehouse masters' (WAREHOUSE_
                                      MASTERS) hours, read the same way;
                                      "off" is no hours of their own, and
                                      they keep LAVA_BOSS_HOURS like every
                                      boss
    LAVA_BOSS_STAY   "60"             minutes a boss stays after its hour,
                                      a warehouse master too; not a number
                                      above 0 is the default
    LAVA_BOSS_TZ     "Europe/Moscow"  whose clock the hours are read on
    LAVA_BOSS_CLOCK  unset            tests only: the local time the clock
                                      reads when the server starts; it runs
                                      on from there
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import world

log = logging.getLogger("lava")

TZ_NAME = os.environ.get("LAVA_BOSS_TZ", "Europe/Moscow").strip() or "Europe/Moscow"


def _zone(name):
    """The zone the hours are on. A system without the tz database (a slim
    image that dropped tzdata) still gets Moscow right: it has kept UTC+3
    all year round since 2014. Any other zone it cannot find falls back to
    UTC, loudly, rather than stopping the server over a boss."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        if name == "Europe/Moscow":
            return timezone(timedelta(hours=3), "MSK")
        log.warning("  !!    no time zone %r, boss hours are read in UTC", name)
        return timezone.utc


ZONE = _zone(TZ_NAME)


def parse_hours(raw, name="LAVA_BOSS_HOURS"):
    """"18,22" -> [1080, 1320]: minutes after local midnight, sorted, each
    once. H or H:MM; anything else is left out with a warning naming the
    setting, so a typo costs one hour and not the schedule."""
    out = set()
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if not part or part.lower() == "off":
            continue
        try:
            h, _, m = part.partition(":")
            h, m = int(h), int(m or 0)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError(part)
        except ValueError:
            log.warning("  !!    %s: %r is not an hour, skipped", name, part)
            continue
        out.add(h * 60 + m)
    return sorted(out)


DEFAULT_HOURS = "14,18,22"
DEFAULT_STAY = 60.0
# The warehouse masters' hour (the module's docstring). It lives here so that
# a server started without compose's defaults (a test, a bare docker run)
# keeps it too; no quest text names it, and the map's warehouse labels name
# it as the original's own fixed text, which server/test_map_labels.py keeps
# in step with it.
DEFAULT_WAREHOUSE_HOURS = "20"


def hours_from(raw, name="LAVA_BOSS_HOURS", default=DEFAULT_HOURS):
    """LAVA_BOSS_HOURS -- or another setting of hours, LAVA_WAREHOUSE_HOURS
    -- as the rule reads it. Only "off" turns it off. Unset or blank is the
    owner's hours -- "LAVA_BOSS_HOURS=" in a shell or an env file outside
    compose, whose ${...:-14,18,22} covers only its own case, must not
    quietly leave every boss standing all day -- and so is a value in which
    not one hour could be read."""
    raw = (raw or "").strip()
    if not raw:
        return parse_hours(default, name)
    if "off" in [p.strip().lower() for p in raw.replace(";", ",").split(",")]:
        return []
    got = parse_hours(raw, name)
    if not got:
        log.warning("  !!    %s=%r names no hour, keeping %s", name, raw, default)
        return parse_hours(default, name)
    return got


def warehouse_hours_from(raw):
    """LAVA_WAREHOUSE_HOURS: the warehouse masters' own hours, read as
    LAVA_BOSS_HOURS is, with DEFAULT_WAREHOUSE_HOURS for its default. "off"
    is no hours of their own (an empty list), and hours_of then gives the
    masters the bosses' HOURS."""
    return hours_from(raw, "LAVA_WAREHOUSE_HOURS", DEFAULT_WAREHOUSE_HOURS)


def stay_from(raw):
    """LAVA_BOSS_STAY in seconds. Never a whole day or more: slot() looks
    back one day only, and a boss that never leaves is what turning the rule
    off is for. Never nothing either: a stay of 0 is a boss that never
    comes, which is not a stay but a typo, like a word where the minutes go.
    Either is the default, with a warning, rather than a server that will
    not start over a boss."""
    raw = (raw or "").strip()
    try:
        minutes = float(raw) if raw else DEFAULT_STAY
        if not minutes > 0:
            raise ValueError(raw)
    except ValueError:
        log.warning("  !!    LAVA_BOSS_STAY=%r is not a stay in minutes, "
                    "keeping %g", raw, DEFAULT_STAY)
        minutes = DEFAULT_STAY
    return min(minutes * 60.0, 86400.0 - 1)


HOURS = hours_from(os.environ.get("LAVA_BOSS_HOURS"))
WAREHOUSE_HOURS = warehouse_hours_from(os.environ.get("LAVA_WAREHOUSE_HOURS"))
STAY = stay_from(os.environ.get("LAVA_BOSS_STAY"))


def _offset():
    """How far the schedule's clock runs from the machine's: 0 unless a test
    set LAVA_BOSS_CLOCK to the local time it wants the server to start at.
    A value that is no time is ignored, loudly: it is a test's knob, and a
    server must not fail to start over it."""
    raw = os.environ.get("LAVA_BOSS_CLOCK", "").strip()
    if not raw:
        return 0.0
    try:
        wanted = datetime.fromisoformat(raw)
    except ValueError:
        log.warning("  !!    LAVA_BOSS_CLOCK=%r is not a time, ignored", raw)
        return 0.0
    if wanted.tzinfo is None:
        wanted = wanted.replace(tzinfo=ZONE)
    return wanted.timestamp() - time.time()


_OFFSET = _offset()


def clock():
    """Seconds since the epoch, as the schedule reads the time. Called
    through the module, so a test can put its own in its place."""
    return time.time() + _OFFSET


# Bosses by name that a quest needs at any hour, and so stand all day and
# come back on the respawn timer like the rest of their place -- the owner's
# default (2026-09-28): the «Главарь бандитов» m05_glavbandit (696) of the
# plundered caravan (120), whom «Фрэнк (часть 2)» sends the player to, and
# the colonists' treasurer nc_Kaznachei (586) in their camp (80, data/
# camp_fill.json), the commissar «Реклама» wants dead (texts.xml 62675). And
# Абри's two treasurers (the owner's Абри, 2026-10-12), st_Kaznachei (590)
# of the slave traders' camp (88) and zd_Kaznachei (591) of the flayers' (92):
# bosses by role who stand in their camps all day, as the colonists' one does,
# and carry no ingot -- the camps' gold is their two bosses' who keep the
# hours (data/loot_manual.json).
ALL_DAY = frozenset({696, 586, 590, 591})

# The warehouses' «Хозяин склада», who keep WAREHOUSE_HOURS: the bosses of
# the stok_ files, each the one boss of its warehouse (data/mob_types.json
# names; the locations are their files' spawns, and server/test_bosses.py
# checks the list against both). The three of Вади-Хальфа are data/
# holdings.json's capturable sites.
WAREHOUSE_MASTERS = frozenset({
    7448,   # boss_WH_sever   Северный склад Вади-Хальфы 111
    7449,   # boss_WH_vostok  Восточный склад Вади-Хальфы 110 (and its copy 983)
    7450,   # boss_WH_ug      Южный склад Вади-Хальфы 109 (and its copy 982)
    7451,   # boss_DN_sever   Северный склад Донголы 113 (and its copy 984)
    7452,   # boss_DN_vostok  Восточный склад Донголы 114
    7453,   # boss_DN_ug      Южный склад Донголы 112
    7454,   # boss_AH_vostok  Центр Абу-Хамеда 128
    7455,   # boss_AH_sever   Ангары Абу-Хамеда 288 (out of the game since 2026-10-13: across the river)
})


def keeps_hours(type_id):
    """Whether a creature of this type keeps the hours rather than the
    respawn timer: a boss, while the rule is on, but for ALL_DAY."""
    return (bool(HOURS) and type_id not in ALL_DAY
            and world.creature_role(type_id) == "boss")


def hours_of(type_id):
    """The hours a boss of this type keeps: a warehouse master's own
    WAREHOUSE_HOURS, unless they are off, and HOURS for every other boss."""
    if type_id in WAREHOUSE_MASTERS and WAREHOUSE_HOURS:
        return WAREHOUSE_HOURS
    return HOURS


def slot(t, hours=None):
    """The window a moment falls in, named by when it opened (seconds since
    the epoch), or None outside every window.

    A window opens at each of the hours -- HOURS unless others are given,
    a warehouse master's for him (slot_of) -- on the zone's clock and lasts
    STAY. It may have opened yesterday -- a 23:00 hour with a two-hour stay
    is still open at half past midnight -- and where two overlap the later
    one is the answer: a boss killed in the first comes back for the second.
    """
    hours = HOURS if hours is None else hours
    if not hours:
        return None
    today = datetime.fromtimestamp(t, ZONE).date()
    best = None
    for back in (0, 1):
        d = today - timedelta(days=back)
        for minute in hours:
            start = datetime(d.year, d.month, d.day, minute // 60, minute % 60,
                             tzinfo=ZONE).timestamp()
            if start <= t < start + STAY and (best is None or start > best):
                best = start
    return best


def slot_of(type_id, t):
    """slot() on the hours a boss of this type keeps (hours_of): a
    warehouse master's window, or the bosses' one."""
    return slot(t, hours_of(type_id))


def _clock_list(hours):
    return ", ".join("%d:%02d" % divmod(m, 60) for m in hours)


def describe():
    """One line for the start-up log: what the rule is today."""
    if not HOURS:
        return "bosses keep no hours (LAVA_BOSS_HOURS is off)"
    return "bosses come at %s %s and stay %g min; the warehouse masters at %s" % (
        _clock_list(HOURS), TZ_NAME, STAY / 60.0,
        _clock_list(WAREHOUSE_HOURS) if WAREHOUSE_HOURS
        else "the same hours (LAVA_WAREHOUSE_HOURS is off)")


def _and(parts):
    """«14, 18 и 22»: a Russian list."""
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " и " + parts[-1]


def _hours_word(n):
    """«час», «часа», «часов» for the hour a list ends on."""
    if n % 10 == 1 and n % 100 != 11:
        return "час"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "часа"
    return "часов"


def say_hours(short=False):
    """The hours as a quest's start names them (quests._say_boss_hours):
    «в 14:00, 18:00 и 22:00», or short, «в 14, 18 и 22 часа», which falls
    back to the long one where an hour has minutes. A text that tells a
    player when to come must say what the server does, whatever
    LAVA_BOSS_HOURS is; with the rule off a boss stands all day."""
    if not HOURS:
        return "в любое время"
    if short and not any(m % 60 for m in HOURS):
        last = HOURS[-1] // 60
        return "в %s %s" % (_and([str(m // 60) for m in HOURS]), _hours_word(last))
    return "в " + _and(["%d:%02d" % divmod(m, 60) for m in HOURS])
