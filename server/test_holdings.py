"""Warehouses clans hold (server/holdings.py): taken by killing the boss.

The owner's «сделай так чтобы склады можно было захватывать убивая босса»
(2026-10-09). In process, with the game's own sessions (server.Session)
standing in the Северный склад (111), its boss on a clock turned by hand,
and a real database:

  * the capture: a clan qualifies with two living members at the site's
    level who hurt the boss, and the most harm wins -- a tie to the killing
    blow's clan, else the older clan; one member alone, one below the level,
    one dead, one gone from the room take nothing; the holder's own kill is
    a defence; harm banked over a heal, or past the boss's health and
    stamina, counts for nothing; a reconnect, onto the body left standing or
    as a new session once it is put away, keeps a member's harm, and a
    member who leaves his clan after the kill still counts for it; a new
    window forgets the last one's harm; the boss, the «Хозяин склада», comes
    once a day, at 20:00, and not at the bosses' 14, 18 and 22 (the owner's
    «на складах хозяин должен прриходить один раз!!!», 2026-10-12), so every
    fight below is a day's; the rule off (LAVA_BOSS_HOURS=off)
    settles too; a restart inside the window settles nothing twice; a
    disband drops the holding; and no outcome ever reaches a chat channel,
    only the log and clan_holding_log;
  * the flag: per viewer in a site room -- clan= and a fellow after the
    frame, repair for the holders alone, nothing for sale -- and Абу-Хамед's
    flag (128) as it always was, mending for anybody (Донгола's three are
    sites since 2026-10-13, the owner's «и потом сделай донголу тоже»);
  * the box: «Патроны и афро владельцам склада» (765) between 19:00 and
    20:00 to a member of the holding clan of a day's standing at the site's
    level, once a day, one character of an account; refused at the hand-in
    to one who left the clan or whose clan lost the site, the quest in his
    journal; the day turning at 03:00 Moscow time; the box shown under a new
    id when its window opens and shuts, and when the holder changes;
  * the admin's hold and release (clan_admin.py) through the queue, and
    tools/admin_account.py's holdings, clan-hold and clan-release.

    LAVA_RES=.../lava/res python3 server/test_holdings.py

The frames over a socket: test_holdings_wire.py.
"""
import asyncio
import contextlib
import io
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(tempfile.mkdtemp(), "holdings.db")
os.environ["LAVA_DB"] = DB
os.environ.setdefault("LAVA_GX", "6268")
os.environ.setdefault("LAVA_GY", "1819")
os.environ["LAVA_CLAN_DEAF_CHECK"] = "0"
# The owner's hours, a quiet chat and a body left standing on war ground
# (server.COMBAT_LINGER, which the reconnect scene takes up again) are part
# of what is tested, whatever the shell running this carries.
for _k in ("LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ", "LAVA_BOSS_CLOCK",
           "LAVA_WAREHOUSE_HOURS",
           "LAVA_SERVER_CHAT", "LAVA_COMBAT_LINGER"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import accounts  # noqa: E402
from protocol import decode  # noqa: E402

LOGINS = ("alice", "amir", "anna", "andy", "arno", "bob", "bill", "carl", "dora", "dick")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _l in LOGINS:
    _store.register(_l, "secret")
_store.close()

import admin_account  # noqa: E402
import bosses  # noqa: E402
import clans  # noqa: E402
import combat  # noqa: E402
import events  # noqa: E402
import holdings  # noqa: E402
import inventory  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)
import world  # noqa: E402

STORE = server.STORE
CLANS = server.CLANS
from testkit import check, fails  # noqa: E402

SEVER, ELSEWHERE = 111, 128            # the Северный склад, and Абу-Хамед's (no site yet)
FLAG, BOX, BOSS = 1011, 6824, 7448
BOX_ROW = quests.get(765)
WALTHER = 25636                         # a gun to mend (test_repair's)


def at(h, m=0, s=0, day=5):
    """A moment on the Moscow clock, the day-th day from 2026-10-01 (the 1st),
    as seconds since the epoch."""
    first = datetime(2026, 10, 1, h, m, s, tzinfo=bosses.ZONE)
    return (first + timedelta(days=day - 1)).timestamp()


NOW = [at(12)]
bosses.clock = lambda: NOW[0]
combat.CORPSE_DELAY = 0.05


# --- the lines the module writes ------------------------------------------------------------
class Lines(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self, logging.INFO)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    def take(self, word="warehouse"):
        out = [line.strip() for line in self.lines if word in line]
        self.lines = []
        return out


LINES = Lines()
_lava = logging.getLogger("lava")
_lava.handlers, _lava.propagate = [LINES], False
_lava.setLevel(logging.INFO)


# --- sessions of the game's own -------------------------------------------------------------
class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def take(sess):
    out = sess.writer.frames[:]
    sess.writer.frames.clear()
    return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def login(login_name, char_name, new=True):
    """A session playing the character: on a body of his still standing on war
    ground (Session.linger) selPers hands this socket to that session, and from
    there on it is the one the client talks to, as in handle_client."""
    sess = server.Session(Writer(), login_name)
    run(sess, "login;hash=@%s@;" % accounts.credential(login_name, "secret"))
    if new:
        run(sess, "newPers;res=1;sex=0;name=@%s@;" % char_name)
        run(sess, "actPlayer;")
    else:
        run(sess, "selPers;num=0;")
        sess = sess.resumed or sess
    run(sess, "lenter;accept=1;")
    return sess


def into(sess, loc_id):
    """To a location and in, as /goto and the client's lenter make it."""
    sess.admin_goto(loc_id)
    run(sess, "lenter;accept=1;")
    take(sess)


def level(sess, n):
    """The best skill at n: the level a capture and the box's row ask."""
    sess.character().skill[progression.SHOOTING][0] = n
    sess.character().save(STORE)


def found(head, name, days=3):
    """A clan, founded days ago, with this head."""
    return STORE.clan_create(head.char_id, name, clans.name_key(name), "", None,
                             when=time.time() - days * 86400)


def admit(clan_id, sess, days=3):
    STORE.clan_member_add(sess.char_id, clan_id, clans.R_CHAT, "", 0,
                          when=time.time() - days * 86400)


def joined(sess, hours_ago):
    STORE.db.execute("UPDATE clan_members SET joined_at = ? WHERE char_id = ?",
                     (int(time.time() - hours_ago * 3600), sess.char_id))
    STORE.db.commit()


def holder():
    h = STORE.holding("wh_sever")
    return h["clan_id"] if h else None


def log_rows(n=1000):
    return STORE.holding_log("wh_sever", n)


def order(op, **args):
    """One clan order through the queue, as the panel and the tool write it
    and the game carries it out (server.apply_admin_action): what it said."""
    aid = STORE.admin_push("tester", "clan", op=op, **args)
    for row in STORE.admin_pending():
        STORE.admin_done(row["id"], server.apply_admin_action(row))
    return STORE.db.execute("SELECT result FROM admin_actions WHERE id = ?",
                            (aid,)).fetchone()["result"]


def tool(*argv):
    """tools/admin_account.py as its command line runs: (exit code, output)."""
    STORE.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = admin_account.main(list(argv) + ["--db", DB])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


async def main():
    alice = login("alice", "Alice")         # the Волки's head
    amir = login("amir", "Amir")            # Волки
    anna = login("anna", "Anna")            # Волки, a level short
    andy = login("andy", "Andy")            # Волки
    arno = login("arno", "Arno")            # Волки, the newcomer of the box
    bob = login("bob", "Bob")               # the Шакалы's head
    bill = login("bill", "Bill")            # Шакалы
    carl = login("carl", "Carl")            # in no clan
    dora = login("dora", "Dora")            # the Орлы's head, disbanded below
    dick = login("dick", "Dick")            # Орлы
    for s in (alice, amir, andy, arno, bob, bill, carl, dora, dick):
        level(s, 8)
    level(anna, 7)
    wolves = found(alice, "Волки")
    jackals = found(bob, "Шакалы")
    for s in (amir, anna, andy, arno):
        admit(wolves, s)
    admit(jackals, bill)
    check("the Волки are the older clan, the lower id", wolves < jackals, True)

    everybody = [alice, amir, anna, andy, arno, bob, bill, carl, dora, dick]
    NOW[0] = at(12)
    for s in everybody:
        into(s, SEVER)
    room = server.ROOMS.get(SEVER)
    rc = combat.room_combat(room, STORE)
    boss = next(m for m in rc.mobs.values() if m.type_id == BOSS)
    flag = next(e for e, n in room.npcs.items() if n.type_id == FLAG)
    check("the Северный склад is a site, its boss the boss whose kill takes it",
          (holdings.site_at(SEVER).key, holdings.site_for(SEVER, BOSS).key,
           holdings.site_for(SEVER, 7449), holdings.site_for(110, 7449).key),
          ("wh_sever", "wh_sever", None, "wh_vostok"))
    check("982 and 983, the copies with the same bosses, are no sites",
          (holdings.site_at(982), holdings.site_for(983, 7449)), (None, None))
    check("the table holds together: each room has its boss, flag and box, each box"
          " its row in the window (holdings.check)", holdings.problems(), [])
    check("the boxes' rows: on the string preload, the rows' own name, the site and its"
          " level, the original's daily note and no word of residence",
          [(server.names.known(q.string_id(quests.NAME)),
            server.names.known(q.string_id(quests.START)), q.name, q.holders, q.level,
            "в сутки" in q.texts[quests.START], "жительств" in q.texts[quests.START])
           for q in map(quests.get, (765, 766, 767))],
          [(True, True, "Патроны и афро владельцам склада", key, lvl, True, False)
           for key, lvl in (("wh_sever", 8), ("wh_vostok", 8), ("wh_ug", 12))])

    # The master's hours: one window a day, at 20:00, and none at the bosses'
    # 14, 18 and 22 -- the day before the fights below, he is not there.
    check("the boss keeps the warehouse masters' hour, 20:00 alone",
          (bosses.hours_of(BOSS),
           [bosses.hours_of(site.boss) for site in holdings.sites().values()]),
          ([20 * 60], [[20 * 60]] * 6))
    seen = []
    for h in (14, 18, 22, 20):
        NOW[0] = at(h, 5)
        rc.keep_hours()
        seen.append((h, boss.alive and boss.eid in room.npcs))
    NOW[0] = at(21, 5)
    rc.keep_hours()
    check("  ..not there at 14:00, 18:00 nor 22:00, there at 20:00",
          seen, [(14, False), (18, False), (22, False), (20, True)])
    check("  ..and gone at 21:00, nobody fighting him", (boss.alive, boss.away), (False, True))

    windows = iter([at(20, 5, day=d) for d in range(6, 40)])

    def window():
        """The next day's 20:00, the boss's hour: he arrives, whole, his
        ledgers empty."""
        NOW[0] = next(windows)
        rc.keep_hours()
        return boss.alive and boss.eid in room.npcs

    async def fight(harm, killer=None, between=None):
        """The next window; each (session, harm) on the boss as its blows put
        it (Fighter.award_xp); the kill by killer's hand; the corpse fading.
        (the log's new row's how or None, the holder after)."""
        if not window():
            fails.append("the boss did not come at %s" % NOW[0])
        for sess, dealt in harm:
            sess.combat.award_xp(progression.SHOOTING, None, dealt, boss)
        before = len(log_rows())
        rc.kill(boss, killer.combat if killer is not None else None)
        if between is not None:
            between()
        await asyncio.sleep(0.3)
        rows = log_rows()
        return (rows[0]["how"] if len(rows) > before else None), holder()

    # --- who may take it ---------------------------------------------------------------------
    for s in everybody:
        take(s)
    LINES.take()
    check("one member of a clan alone: nobody takes it, a 'none' row",
          await fight([(alice, 300)], alice), ("none", None))
    check("  ..and the log says why: no two living members of level 8 who hurt it",
          [line.startswith("..    warehouse wh_sever (111): its boss killed, and no clan had 2"
                           " living members of level 8") for line in LINES.take()], [True])
    check("two members, one of them a level short (7): nobody takes it",
          await fight([(alice, 300), (anna, 300)], alice), ("none", None))
    amir.combat.dead = True
    check("two members, one of them lying dead in the room: nobody takes it",
          await fight([(alice, 300), (amir, 300)], alice), ("none", None))
    amir.combat.dead = False
    window()
    alice.combat.award_xp(progression.SHOOTING, None, 300, boss)
    andy.combat.award_xp(progression.SHOOTING, None, 300, boss)
    into(andy, ELSEWHERE)
    rc.kill(boss, alice.combat)
    await asyncio.sleep(0.3)
    check("two members hurt it and one leaves the room before the kill: he does not"
          " count, and nobody takes it", (log_rows(1)[0]["how"], holder()), ("none", None))
    into(andy, SEVER)
    for s in everybody:
        take(s)
    check("carl, in no clan, kills it alone: nothing", await fight([(carl, 900)], carl),
          ("none", None))

    # --- a capture -------------------------------------------------------------------------
    for s in everybody:
        take(s)
    LINES.take()
    got = await fight([(alice, 200), (amir, 200)], amir)
    check("two members of the Волки at level 8 hurt it and kill it: they take it",
          got, ("capture", wolves))
    row = log_rows(1)[0]
    check("  ..one 'capture' row: the Волки after, nobody before, the killer credited,"
          " the window it was taken in",
          (row["how"], row["clan_id"], row["prev"], row["by_char"], row["slot"]),
          ("capture", wolves, None, amir.char_id, bosses.slot_of(BOSS, NOW[0])))
    held = STORE.holding("wh_sever")
    check("  ..the holding: the clan, its name, since now, the window",
          (held["clan_id"], held["name"], abs(held["since"] - time.time()) < 60,
           held["slot"]), (wolves, "Волки", True, bosses.slot_of(BOSS, NOW[0])))
    check("  ..and the log line: who takes it, the harm, who is credited",
          LINES.take(), ["..    warehouse wh_sever (111): clan %d «Волки» takes it, 400 harm,"
                         " credited char %d, window %d"
                         % (wolves, amir.char_id, bosses.slot_of(BOSS, NOW[0]))])
    frames = {s: take(s) for s in everybody}
    check("  ..no frame of it to any chat channel, world, room or clan",
          sorted({n for fr in frames.values() for n, _p in fr if n == "userMsg"}), [])
    check("  ..everybody in the room is sent the flag again, naming the Волки",
          sorted({(p.get("clan"), p["can_trade"]) for fr in frames.values()
                  for p in named(fr, "userInfo_Trader") if p["id"] == flag}),
          [(wolves, 0)])
    since = held["since"]
    check("the holder kills its own boss: a defence, its since unchanged",
          (await fight([(alice, 300), (amir, 300)], alice), STORE.holding("wh_sever")["since"]),
          (("defend", wolves), since))
    check("  ..its row: the Волки before and after, the killer credited",
          [(r["how"], r["clan_id"], r["prev"], r["by_char"]) for r in log_rows(1)],
          [("defend", wolves, wolves, alice.char_id)])

    # --- the most harm ---------------------------------------------------------------------
    check("both clans qualify: the one with more harm takes it, though the other struck"
          " last", await fight([(alice, 100), (amir, 100), (bob, 150), (bill, 150)], alice),
          ("capture", jackals))
    check("  ..the row says from whom", (log_rows(1)[0]["prev"], log_rows(1)[0]["by_char"]),
          (wolves, bob.char_id))
    check("a tie, the killing blow carl's, in no clan: the older clan, the Волки",
          await fight([(alice, 150), (amir, 150), (bob, 150), (bill, 150)], carl),
          ("capture", wolves))
    check("a tie, the killing blow the Шакалы's: the Шакалы, the younger",
          await fight([(alice, 150), (amir, 150), (bob, 150), (bill, 150)], bill),
          ("capture", jackals))
    check("the Волки have more harm, a stranger and the Шакалы strike too, the Шакалы"
          " last: the Волки", await fight([(alice, 300), (amir, 300), (carl, 400), (bob, 50),
                                          (bill, 50)], bob), ("capture", wolves))
    order("hold", clan=jackals, site="wh_sever")
    andy.combat.dead = True
    check("a member lying dead in the room still adds his harm: 100 + 100 + his 100 beat"
          " 160 + 130", await fight([(alice, 100), (amir, 100), (andy, 100), (bob, 160),
                                     (bill, 130)], bob), ("capture", wolves))
    andy.combat.dead = False
    check("a clan's harm is the boss's health and stamina at most (%d): ten times that"
          " ties with 1200, and the killing blow decides" % (boss.hp_max + boss.sp_max),
          await fight([(alice, 5000), (amir, 5000), (bob, 600), (bill, 600)], bill),
          ("capture", jackals))

    # --- banked harm --------------------------------------------------------------------------
    window()
    alice.combat.award_xp(progression.SHOOTING, None, 400, boss)
    amir.combat.award_xp(progression.SHOOTING, None, 400, boss)
    boss.hp, boss.homing = 10, True
    rc.mob_recover(boss)
    check("harm, then the boss goes home and heals: its capture ledger is empty",
          (boss.hp == boss.hp_max, boss.capture_harm), (True, {}))
    alice.combat.award_xp(progression.SHOOTING, None, 20, boss)
    amir.combat.award_xp(progression.SHOOTING, None, 20, boss)
    bob.combat.award_xp(progression.SHOOTING, None, 100, boss)
    bill.combat.award_xp(progression.SHOOTING, None, 100, boss)
    order("hold", clan=wolves, site="wh_sever")
    rc.kill(boss, bob.combat)
    await asyncio.sleep(0.3)
    check("  ..the Волки's 800 before the heal count for nothing: the Шакалы's 200 since"
          " take it from their 40", (log_rows(1)[0]["how"], holder()), ("capture", jackals))
    window()
    boss.hp = boss.hp_max - 3
    bob.combat.award_xp(progression.SHOOTING, None, 3, boss)
    boss.regen_at, boss.target, boss.homing = 0.0, None, False
    rc._step()
    check("whole again by its own regeneration: the ledger is empty too",
          (boss.hp == boss.hp_max, boss.capture_harm), (True, {}))
    rc.kill(boss, None)
    await asyncio.sleep(0.3)

    # --- a reconnect, a member leaving, a new window ----------------------------------------
    window()
    amir.combat.award_xp(progression.SHOOTING, None, 100, boss)
    body = amir
    amir.close()
    amir = login("amir", "Amir", new=False)
    amir.combat.award_xp(progression.SHOOTING, None, 50, boss)
    check("a member reconnects in the fight: his body stood in the room and his login"
          " takes it up again (Session.linger); his harm before and after, once, by his"
          " character", (amir is body, amir in room.players, boss.capture_harm.get(amir.char_id)),
          (True, True, 150))
    amir.close()
    amir.expire_linger()
    gone = body in room.players
    amir = login("amir", "Amir", new=False)
    into(amir, SEVER)
    amir.combat.award_xp(progression.SHOOTING, None, 50, boss)
    alice.combat.award_xp(progression.SHOOTING, None, 100, boss)
    check("  ..his body put away when its time runs out, a new session of his walks in:"
          " his harm is still his character's",
          (gone, amir is body, boss.capture_harm.get(amir.char_id)), (False, False, 200))
    rc.kill(boss, alice.combat)
    await asyncio.sleep(0.3)
    check("  ..and with it the Волки take it from the Шакалы", (log_rows(1)[0]["how"], holder()),
          ("capture", wolves))
    everybody[1] = amir
    order("hold", clan=jackals, site="wh_sever")
    check("a member put out of his clan between the kill and the corpse fading still"
          " counts for it", await fight([(alice, 200), (amir, 200)], alice,
                                        between=lambda: STORE.clan_member_remove(amir.char_id,
                                                                                 wolves)),
          ("capture", wolves))
    admit(wolves, amir)
    window()
    alice.combat.award_xp(progression.SHOOTING, None, 300, boss)
    NOW[0] += 3600
    rc.keep_hours()
    gone = (boss.alive, boss.away)
    NOW[0] = next(windows)
    rc.keep_hours()
    check("harm in a window nobody won, the boss gone at its end: back at the next hour,"
          " its ledger empty", (gone, boss.alive, boss.capture_harm), ((False, True), True, {}))
    rc.kill(boss, None)
    await asyncio.sleep(0.3)

    # --- the rule off -----------------------------------------------------------------------
    hours, delay = bosses.HOURS, combat.RESPAWN_DELAY
    bosses.HOURS = ()
    combat.RESPAWN_DELAY = 0.05
    try:
        off_room = rooms.Room(world.location(SEVER), rooms.IdAllocator(), world.mob_types(), SEVER)
        off_rc = off_room.combat = combat.RoomCombat(off_room, STORE)
        off_boss = next(m for m in off_rc.mobs.values() if m.type_id == BOSS)
        for s in (bob, bill):
            room.players.pop(s, None)
            off_room.players[s] = True
            s.room = off_room
        bob.combat.award_xp(progression.SHOOTING, None, 300, off_boss)
        bill.combat.award_xp(progression.SHOOTING, None, 300, off_boss)
        off_rc.kill(off_boss, bob.combat)
        await asyncio.sleep(0.3)
        check("with LAVA_BOSS_HOURS=off the boss is an ordinary mob, and its kill settles all"
              " the same", (off_rc.bosses, log_rows(1)[0]["how"], holder(), off_boss.alive),
              ([], "capture", jackals, True))
    finally:
        bosses.HOURS, combat.RESPAWN_DELAY = hours, delay
        for s in (bob, bill):
            off_room.players.pop(s, None)
            room.players[s] = True
            s.room = room
        for bag in off_rc.loot.values():
            if bag.expiry is not None:
                bag.expiry.cancel()

    # --- a restart inside the window ----------------------------------------------------------
    got = await fight([(alice, 300), (amir, 300)], amir)
    rows = len(log_rows())
    again = rooms.Room(world.location(SEVER), rooms.IdAllocator(), world.mob_types(), SEVER)
    again_rc = combat.RoomCombat(again, STORE)
    again_boss = next(m for m in again_rc.mobs.values() if m.type_id == BOSS)
    again_rc.keep_hours()
    check("killed in its window and the server restarted inside it: the boss starts away,"
          " nothing to kill or to settle again",
          (got, again_boss.alive, again_boss.away, again_boss.eid in again.npcs,
           len(log_rows()) - rows), (("capture", wolves), False, True, False, 0))

    # --- the flag ---------------------------------------------------------------------------
    for s in everybody:
        take(s)

    def flag_frames(sess, eid=flag):
        """The frames getInfo about the flag brings: the userInfo_Trader and
        whatever follows it about the same id."""
        take(sess)
        sess.send_npc_info(eid)
        return [(n, p) for n, p in take(sess) if p.get("id") == eid]

    got = flag_frames(alice)
    check("a holder in the room: userInfo_Trader, then a fellow naming the Волки",
          [n for n, _p in got], ["userInfo_Trader", "fellow"])
    check("  ..the frame: nothing for sale, repair, the clan",
          {k: got[0][1].get(k) for k in ("name", "can_trade", "can_repair", "clan")},
          {"name": FLAG, "can_trade": 0, "can_repair": 1, "clan": wolves})
    check("  ..the fellow: the flag's id, the clan, its name",
          got[1][1], {"id": flag, "reg": wolves, "soc": "Волки"})
    got = flag_frames(bob)
    check("a member of another clan: the same caption, and no repair",
          ([n for n, _p in got], got[0][1]["can_repair"], got[0][1]["clan"], got[1][1]["reg"]),
          (["userInfo_Trader", "fellow"], 0, wolves, wolves))
    got = flag_frames(carl)
    check("a viewer in no clan: the fellow too, for his client knows no clan to name",
          ([n for n, _p in got], got[0][1]["can_repair"], got[1][1]),
          (["userInfo_Trader", "fellow"], 0, {"id": flag, "reg": wolves, "soc": "Волки"}))
    order("release", clan=wolves, site="wh_sever")
    got = flag_frames(alice)
    check("held by nobody: the caption alone -- no clan, no fellow, no repair",
          ([n for n, _p in got], "clan" in got[0][1], got[0][1]["can_repair"]),
          (["userInfo_Trader"], False, 0))
    order("hold", clan=wolves, site="wh_sever")
    into(carl, ELSEWHERE)
    droom = server.ROOMS.get(ELSEWHERE)
    dflag = next(e for e, n in droom.npcs.items() if n.type_id == FLAG)
    got = flag_frames(carl, dflag)
    check("Абу-Хамед's flag (128), a warehouse nobody can take yet: its frame as before --"
          " for sale and mending, no clan, no fellow",
          ([n for n, _p in got], got[0][1]["can_trade"], got[0][1]["can_repair"],
           "clan" in got[0][1]), (["userInfo_Trader"], 1, 1, False))
    check("  ..its caption is the original's «Складом владеют:» all the same: names are"
          " per type", server.names.ALL.get(FLAG), "Складом владеют:")

    def mend(sess, eid):
        """A worn gun mended at the flag, the stall opened as the client
        opens it: the answer, and whether it was mended."""
        ch = sess.character()
        ch.afro = 10 ** 6
        row = sess.inv.create(WALTHER)
        STORE.update_item(row["uniq"], brk=100, max_break_cur=2800)
        take(sess)
        sess.inv.open_trade({"target": eid})
        sess.inv.repair({"obj": inventory.oid_of(row)}, inventory.UPD_REPAIR)
        got = acks(take(sess))
        return got, STORE.item(row["uniq"])["brk"] > 100

    check("repair at Абу-Хамед's flag: anybody, carl in no clan", mend(carl, dflag),
          ([0, 0], True))
    into(carl, SEVER)
    check("repair at the Северный склад's flag: the holders' (alice)", mend(alice, flag),
          ([0, 0], True))
    check("  ..and refused to carl, who sends it though his window would not open",
          mend(carl, flag), ([0, inventory.RES_REFUSED], False))
    check("  ..and to bob of the Шакалы", mend(bob, flag), ([0, inventory.RES_REFUSED], False))

    # --- the box ----------------------------------------------------------------------------
    for s in everybody:
        joined(s, 48)
    joined(alice, 72)

    def box():
        return next(e for e, n in room.npcs.items() if n.type_id == BOX)

    NOW[0] = at(18, 59, day=40)
    rc.keep_hours()
    shut_id = box()
    for s in everybody:
        take(s)
    check("18:59: the box's row is nobody's, the holders' neither",
          [s.quest_available(BOX_ROW) for s in (alice, carl)], [False, False])
    NOW[0] = at(19, 0, day=40)
    rc.keep_hours()
    open_id = box()
    seen = [p for n, p in take(alice) if n == "lch"
            and (p.get("lostUser") in (shut_id, open_id) or p.get("newUser") in (shut_id, open_id))]
    check("19:00: the window opens, and the box is shown under a new id, so the client"
          " asks its rows again", (open_id != shut_id, seen),
          (True, [{"lostUser": shut_id}, {"newUser": open_id, "pos": room.npcs[open_id].cell,
                                          "rtype": room.npcs[open_id].root}]))
    NOW[0] = at(19, 30, day=40)
    check("19:30: the row is on offer to a holder of a day's standing at level 8",
          alice.quest_available(BOX_ROW), True)
    check("  ..not to carl, in no clan, nor to bob of another clan, nor to anna, a level"
          " short", [s.quest_available(BOX_ROW) for s in (carl, bob, anna)],
          [False, False, False])
    joined(arno, 23)
    check("  ..nor to arno, in the clan for 23 hours", arno.quest_available(BOX_ROW), False)
    joined(arno, 24)
    check("  ..who has it at 24", arno.quest_available(BOX_ROW), True)
    afro0 = alice.character().afro
    take(alice)
    run(alice, "q_st;mob=%d;q_idx=0;" % open_id)
    got = take(alice)
    q_id = named(got, "q_di_del_obj")[0]["q_id"] if named(got, "q_di_del_obj") else None
    check("alice takes it at the box: 0, and in the journal complete",
          (acks(got), named(got, "q_di_del_obj")[0]["obj"] if q_id else None), ([0], 1))
    rounds0 = sum(r["count"] for r in STORE.items_of(alice.char_id) if r["type_id"] == 6092)
    run(alice, "q_co;q_id=%d;mob=%d;obj_idx=0;" % (q_id, open_id))
    got = take(alice)
    check("  ..and hands it in: 0, 8000 afro and 50 rounds of 9мм НАТО КС",
          (acks(got)[-1:], alice.character().afro - afro0,
           sum(r["count"] for r in STORE.items_of(alice.char_id) if r["type_id"] == 6092)
           - rounds0), ([0], 8000, 50))
    check("  ..the hand-in written in the history, which per_day reads",
          STORE.quests_done_since(alice.char_id, server.Session.day_start(), [765]), 1)
    check("  ..so not on offer a second time that day", alice.quest_available(BOX_ROW), False)
    check("  ..and not counted against the day's tasks: a service",
          (BOX_ROW.service, server.Session.counts_daily(BOX_ROW)), (True, False))
    alice.close()
    alice2 = login("alice", "Alice2")
    admit(wolves, alice2, days=3)
    level(alice2, 8)
    into(alice2, SEVER)
    check("alice's other character, of the Волки for days: refused the same box that day,"
          " one character of an account a day",
          (alice2.quest_available(BOX_ROW),
           holdings.box_refusal(STORE, BOX_ROW, alice2.char_id, alice2.account["id"],
                                server.Session.day_start())),
          (False, "a character of account %d has collected wh_sever today"
           % alice2.account["id"]))
    check("  ..a box of another site is no concern of this one's",
          holdings.box_refusal(STORE, quests.get(766), alice2.char_id, alice2.account["id"],
                               server.Session.day_start()), "nobody holds wh_vostok")
    take(andy)
    run(andy, "q_st;mob=%d;q_idx=0;" % box())
    andy_q = named(take(andy), "q_di_del_obj")[0]["q_id"]
    STORE.clan_member_remove(andy.char_id, wolves)
    check("andy takes it, then is put out of the clan: no longer on offer, carried or not",
          andy.quest_available(BOX_ROW), False)
    run(andy, "q_co;q_id=%d;mob=%d;obj_idx=0;" % (andy_q, box()))
    check("  ..and the hand-in refused, the quest still in his journal",
          (acks(take(andy)), STORE.has_quest(andy.char_id, 765)),
          ([server.RES_NOT_AVAILABLE], True))
    admit(wolves, andy, days=3)
    run(arno, "q_st;mob=%d;q_idx=0;" % box())
    arno_q = named(take(arno), "q_di_del_obj")[0]["q_id"]
    order("release", clan=wolves, site="wh_sever")
    run(arno, "q_co;q_id=%d;mob=%d;obj_idx=0;" % (arno_q, box()))
    check("arno takes it, then the Волки lose the site: the hand-in refused",
          (acks(take(arno)), STORE.has_quest(arno.char_id, 765)),
          ([server.RES_NOT_AVAILABLE], True))
    order("hold", clan=wolves, site="wh_sever")
    before = box()
    for s in everybody[1:] + [alice2]:
        take(s)
    order("hold", clan=jackals, site="wh_sever")
    rc.keep_hours()
    check("the holder changes: on the room's next tick the box is shown under a new id"
          " (events.touch)", (box() != before,
                              [p for n, p in take(bob) if n == "lch" and "newUser" in p]
                              == [{"newUser": box(), "pos": room.npcs[box()].cell,
                                   "rtype": room.npcs[box()].root}]), (True, True))
    check("  ..and now the row is the Шакалы's, of a day's standing",
          (bob.quest_available(BOX_ROW), andy.quest_available(BOX_ROW)), (True, False))
    order("hold", clan=wolves, site="wh_sever")
    NOW[0] = at(20, 0, day=40)
    before = box()
    rc.keep_hours()
    check("20:00: shut again -- refused, and the box shown under a new id once more",
          (andy.quest_available(BOX_ROW), box() != before), (False, True))
    check("the day turns at 00:00 UTC, three in the morning in Moscow",
          (server.Session.day_start(at(2, 59, day=41)), server.Session.day_start(at(3, day=41)),
           datetime.fromtimestamp(at(3, day=41), timezone.utc).hour),
          (at(3, day=40), at(3, day=41), 0))
    STORE.finish_quest(0, andy.char_id, 765, when=at(2, 59, day=41))
    check("  ..a box collected at 02:59 is yesterday's from 03:00",
          [STORE.account_quests_done_since(andy.account["id"], server.Session.day_start(t),
                                           [765]) for t in (at(2, 59, day=41), at(3, day=41))],
          [1, 0])

    # --- the admin's orders -------------------------------------------------------------------
    for s in [alice2] + everybody[1:]:
        take(s)
    touched = events._TOUCHED.get(BOX, 0)
    rows = len(log_rows())
    check("hold for the clan that holds it: said so, nothing written, since kept",
          (order("hold", clan=wolves, site="wh_sever"), len(log_rows()) - rows,
           events._TOUCHED.get(BOX, 0) - touched),
          ("склад «Северный склад Вади-Хальфы» уже за кланом «Волки»", 0, 0))
    check("hold for the Шакалы: theirs, an 'admin' row, the flag sent again to the room,"
          " the box touched",
          (order("hold", clan=jackals, site="wh_sever"), holder(),
           [(r["how"], r["clan_id"], r["prev"], r["by_char"]) for r in log_rows(1)],
           sorted({p.get("clan") for p in named(take(carl), "userInfo_Trader")
                   if p["id"] == flag}), events._TOUCHED.get(BOX, 0) - touched),
          ("склад «Северный склад Вади-Хальфы» теперь за кланом «Шакалы» (был за кланом"
           " «Волки»)", jackals, [("admin", jackals, wolves, None)], [jackals], 1))
    since = STORE.holding("wh_sever")["since"]
    check("  ..the same order again: nothing changes, since kept",
          (order("hold", clan=jackals, site="wh_sever"), STORE.holding("wh_sever")["since"]),
          ("склад «Северный склад Вади-Хальфы» уже за кланом «Шакалы»", since))
    check("release with the clan that does not hold it: said so, nothing cleared",
          (order("release", clan=wolves, site="wh_sever"), holder()),
          ("склад «Северный склад Вади-Хальфы» уже не за кланом «Волки»", jackals))
    check("release with the holder: nobody's, an 'admin' row",
          (order("release", clan=jackals, site="wh_sever"), holder(),
           [(r["how"], r["clan_id"], r["prev"]) for r in log_rows(1)]),
          ("склад «Северный склад Вади-Хальфы» больше не за кланом «Шакалы»: теперь он ничей",
           None, [("admin", None, jackals)]))
    rows = len(log_rows())
    check("  ..the same release again: said so, no row",
          (order("release", clan=jackals, site="wh_sever"), len(log_rows()) - rows),
          ("склад «Северный склад Вади-Хальфы» уже не за кланом «Шакалы»", 0))
    check("a site that is not: said so, with the ones there are",
          order("hold", clan=wolves, site="склад"),
          "склада «склад» нет (есть: wh_dn_sever, wh_dn_ug, wh_dn_vostok, wh_sever, wh_ug,"
          " wh_vostok)")

    # --- a disband ------------------------------------------------------------------------------
    eagles = found(dora, "Орлы")
    admit(eagles, dick)
    order("hold", clan=eagles, site="wh_sever")
    for s in [alice2] + everybody[1:]:
        take(s)
    touched = events._TOUCHED.get(BOX, 0)
    CLANS.disband(eagles)
    check("the holding clan disbanded: the row gone with it, a 'disband' row",
          (STORE.holding("wh_sever"), [(r["how"], r["clan_id"], r["prev"])
                                       for r in log_rows(1)]),
          (None, [("disband", None, eagles)]))
    got = [(n, p) for n, p in take(carl) if p.get("id") == flag]
    check("  ..the flag sent again in the room, naming nobody; the box touched",
          ([n for n, _p in got], "clan" in got[0][1] if got else None,
           events._TOUCHED.get(BOX, 0) - touched), (["userInfo_Trader"], False, 1))

    # --- the tool --------------------------------------------------------------------------------
    order("hold", clan=wolves, site="wh_sever")
    code, out = tool("holdings")
    check("tool: holdings lists the six sites, who holds each, and the last changes",
          (code, any(line.startswith("wh_sever") and "Волки (id %d)" % wolves in line
                     for line in out.splitlines()),
           any(line.startswith("wh_ug") and "nobody" in line for line in out.splitlines()),
           "the last changes" in out), (0, True, True, True))
    code, out = tool("clan-hold", "Шакалы", "--wait", "0.5")
    check("tool: clan-hold without --site is refused, nothing queued",
          (code, list(STORE.admin_pending())),
          ("clan-hold needs --site, one of: wh_dn_sever, wh_dn_ug, wh_dn_vostok, wh_sever,"
           " wh_ug, wh_vostok", []))
    code, out = tool("clan-hold", "Шакалы", "--site", "wh_sever", "--wait", "0.5")
    pending = [json.loads(r["args_json"]) for r in STORE.admin_pending()]
    check("tool: clan-hold queues the order, the clan by id, and with no game says it waits",
          (code, pending), (2, [{"op": "hold", "clan": jackals, "site": "wh_sever"}]))
    for row in STORE.admin_pending():
        STORE.admin_done(row["id"], server.apply_admin_action(row))
    code, out = tool("clan-release", "Шакалы", "--site", "wh_sever", "--wait", "0.5")
    for row in STORE.admin_pending():
        STORE.admin_done(row["id"], server.apply_admin_action(row))
    check("  ..carried out when the game reads its queue; clan-release the same way",
          [(r["how"], r["clan_id"], r["prev"]) for r in log_rows(2)],
          [("admin", None, jackals), ("admin", jackals, wolves)])

    check("no clan command was answered twice", CLANS.double_acks, [])
    for s in list(server.SESSIONS):
        s.close()
    for bag in rc.loot.values():
        if bag.expiry is not None:
            bag.expiry.cancel()


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("holdings OK")
