"""A shot at a mark on the shooter's own hex, and a burst that fails.

Production, 2026-10-09 16:29, five times in twenty seconds, one player at
one creature:

    Exception in callback Fighter.fire_now(19408, <mobs.Mob ...>, None,
        Weapon(...sdmax=0), 27, 1)
    File "combat.py", in burst
        rec = struck.setdefault(body, [0, 0, 0, body.sp_now()])
    AttributeError: 'str' object has no attribute 'sp_now'

27 action points and one round is a rifle's single shot (25691..25704,
third mode) or a machine gun with one round left (7053, 25099..25101):
both send a round on through its mark (THROUGH_TYPES). The creature stood
on the player's hex. It can: a creature comes back on its spawn hex
whoever stands there (RoomCombat.respawn) -- one killed where it stood
leaves its bag on that very hex, and the player walks onto it to loot --
and the server echoes any walk made of the location's cells
(Session.valid_path), a hex the client has not yet seen a creature step
onto included. A line from a hex to itself has no direction, and
combat.flight answered it with the bare end, ("faMiss", {...}), where
since 2026-10-04 every other answer is (bodies, end): burst unpacked the
string "faMiss" as the bodies the round went through, and the round that
went on through the creature took the letter "f" for the next one. The
same answer killed any gun's shot at a creature that died or left during
the aim when it lay on the shooter's hex, and a shot at the ground at his
own feet.

What the player saw: the cmdAck came at once (fire answers before the aim
timer), then faAim and nothing after it -- no faShot, so the figure stood
with its gun raised, the aim bar full, the autofire stopped
(AutoCommandManager waits for the last faShot), no round spent and no
action point paid. He pressed again; it went the same way.

Held to here, on real Sessions and the real room of the dump (100) in
process, a real gun in the hand and ss_use as the client sends it:

  * flight from a hex to itself is a pair like any other: nobody passed,
    a faMiss about the aim (and stray, its other caller, says faMiss);
  * the dog killed on its spawn hex, the player on its bag there, the dog
    back under him: the rifle's single shot, the machine gun's last round
    and its full burst all hit it, every pair goes out, the rounds and the
    action points are paid, and nothing reaches the loop's exception
    handler -- the production record;
  * a pistol's shot at that dog when it dies during the aim, and a shot
    at the ground he stands on: a miss each, every pair out;
  * a fault anywhere in working out where the rounds went (flight made to
    raise): the error log has it, with its traceback, and the burst still
    goes out -- every pair a miss, paid for as a miss -- for a player's
    shot and for a creature's alike; the next shot goes as ever;
  * a fault in the line of fire Fighter.fire_now asks about before the
    burst (shot_wall made to raise): the same, every pair a miss and paid;
  * a fault in applying the hits after the pairs went out (the dog's usrUp
    made to raise once): the shot is paid all the same, and a dog the
    burst brought down is killed, not left standing at 0.

Written against the code before the fix, the point-blank shots and the
two misses fail with the production record, and the fault's checks fail
on the missing pairs, the unpaid shot, the unsettled kill and the
exception at the loop.
"""
import asyncio
import logging
import os
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["LAVA_DB"] = os.path.join(tempfile.mkdtemp(), "point_blank.db")
os.environ["LAVA_ENCOUNTER_CHANCE"] = "0"
# The dog's corpse fades at once (pace.paced, below) and it is back a
# moment later.
os.environ["LAVA_RESPAWN"] = "0.05"
sys.path.insert(0, HERE)
import server     # noqa: E402
import combat     # noqa: E402
import inventory  # noqa: E402
import items      # noqa: E402
import mobs       # noqa: E402
import world      # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, fails  # noqa: E402

DUMP = 100
DOG_HOME = 4551                     # mStarvingDog_lvl1, as in test_aggro_hold
RIFLE, RIFLE_MODE = 25691, 2        # one round, 27 AP: the record's numbers
MG, MG_MODE = 7053, 0               # three a burst, 27 AP
PISTOL, PISTOL_MODE = 25646, 0      # СПС: one round, and no round goes through
LOC = world.location(DUMP)
W = LOC.width


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass


class Records(logging.Handler):
    """WARNING and above, from every logger: what errlog writes to the error
    log the admin panel shows."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def make_player(name):
    server.STORE.register(name, "secret")
    sess = server.Session(Writer(), name)
    sess.cmd_login({"hash": server.accounts.credential(name, "secret")})
    sess.cmd_newPers(dict(res=1, sex=0, name=name))
    sess.cmd_actPlayer({})
    return sess


def named(frames, name):
    return [p for n, p in frames if n == name]


def last(frames, name, key):
    """key of the last frame of this name, or None when none came."""
    got = named(frames, name)
    return got[-1].get(key) if got else None


def shape(out):
    """flight's answer as (bodies passed, end's name, end's keys), or what
    it was when it is no such pair."""
    try:
        passed, end = out
        return list(passed), end[0], sorted(end[1])
    except Exception:
        return repr(out)


def pairs_of(frames):
    """The fa* frames of the shooter's own bursts, by name and target, in
    order -- faShot as its status."""
    out = []
    for n, p in frames:
        if n == "faShot" and p.get("id") == 0:
            out.append(("faShot", p["status"]))
        elif n == "faHit":
            out.append(("faHit", p["target"]))
        elif n in ("faMiss", "faWall"):
            out.append((n, None))
    return out


def sturdy(mob):
    """Health no burst of these guns takes in one go, and full stamina: the
    dog lives through every shot here, and what it lost is all it lost."""
    mob.hp, mob.sp = 5000, mob.sp_max


def gun(sess, type_id, mode, ammo):
    """A gun of this type in the hand, this mode on, ammo rounds of its own
    calibre in it; whatever was in the hand goes to the bag."""
    # This suite exercises flight and settlement, not refusal of an
    # underqualified shooter (covered by test_weapon_requirements).
    for skill in sess.character().skill:
        skill[0] = 20
    for spec in sess.character().spec:
        spec[0] = 5
    store = sess.inv.store
    for r in sess.inv.rows():
        if r["slot"] == inventory.PRIMARY:
            store.update_item(r["uniq"], slot=inventory.BAG)
    si = items.params_of(type_id)
    row = sess.inv.create(type_id, 1, slot=inventory.PRIMARY, char_id=sess.char_id)
    store.update_item(row["uniq"], cur_mode=mode, ammo_count=ammo,
                      ammo_type=si["comp_array"][0])
    return store.item(row["uniq"])


async def shoot(sess, row, target, before=None):
    """ss_use type 16 as ItemActivator sends it, and everything that came of
    it once the aim (paced to nothing here) has run out. target is an
    entity id, or ("hex", cell). before runs between the command and the
    aim's end."""
    sess.combat.ap = sess.combat.ap_max
    sess.writer.frames.clear()
    where = "x0%08x" % target[1] if isinstance(target, tuple) else "x1%08x" % target
    sess.handle(*decode("ss_use;type=16;obj=x%s;target=%s;"
                        % (inventory.oid_of(row), where)))
    if before is not None:
        before()
    for _ in range(40):
        await asyncio.sleep(0.01)
        aims = named(sess.writer.frames, "faAim")
        closed = [p for n, p in sess.writer.frames
                  if n == "faShot" and p.get("id") == 0 and p["status"] == 0]
        if aims and len(closed) >= aims[0]["num_shots"]:
            break
    await asyncio.sleep(0.02)
    return list(sess.writer.frames)


async def main():
    loop = asyncio.get_running_loop()
    caught = []
    loop.set_exception_handler(lambda _loop, ctx: caught.append(ctx))
    records = Records()
    logging.getLogger().addHandler(records)

    def unhandled():
        out = [(c.get("message", "")[:40], repr(c.get("exception"))) for c in caught]
        caught.clear()
        return out

    # --- a line from a hex to itself -------------------------------------------------
    a = next(c for c in range(W * LOC.height) if c not in LOC.obstacles)
    body = object()
    check("flight from a hex to itself: a pair like any other, nobody passed and a faMiss",
          shape(combat.flight(LOC, a, a, 0.0, 10, {a: body, a + 1: body})),
          ([], "faMiss", ["x", "y"]))
    end = combat.stray(LOC, a, a, 0.0, 10)
    check("  ..and stray, its other caller, reads the end of it",
          end[0] if isinstance(end, tuple) else repr(end), "faMiss")

    # The room's brain held still: nothing moves the dog off the hex between
    # its return and a shot. The aims and the corpse take no time.
    with patch.object(combat.pace, "paced", lambda seconds: 0), \
            patch.object(combat, "AI_TICK", 3600):
        sess = make_player("PointBlank")
        try:
            sess.go_to(DUMP)
            sess.cmd_lenter({})
            rc = sess.combat.rc
            dog = next(m for m in rc.mobs.values() if m.home == DOG_HOME)
            check("the dog stands on its spawn hex", (dog.alive, dog.cell), (True, DOG_HOME))

            # --- a creature back on the hex the player stands on --------------------------
            rc.kill(dog, None)
            sess.pos = dog.home          # on its bag, where it fell
            for _ in range(50):
                await asyncio.sleep(0.02)
                if dog.alive:
                    break
            check("killed where it stood, the dog comes back under the player on its bag",
                  (dog.alive, dog.cell, sess.combat.cell), (True, DOG_HOME, DOG_HOME))
            unhandled()

            for label, type_id, mode, ammo, shots in (
                    ("the rifle's single shot", RIFLE, RIFLE_MODE, 5, 1),
                    ("the machine gun's last round", MG, MG_MODE, 1, 1),
                    ("the machine gun's burst of three", MG, MG_MODE, 30, 3)):
                si = items.params_of(type_id)
                sturdy(dog)
                row = gun(sess, type_id, mode, ammo)
                hp, sp = dog.hp, dog.sp
                got = await shoot(sess, row, dog.eid)
                check(label + " at the dog on his own hex: one cmdAck, the first frame, res=0",
                      ([n for n, _p in got].count("cmdAck"), got[:1]),
                      (1, [("cmdAck", {"res": 0})]))
                check("  ..nothing reaches the loop's exception handler", unhandled(), [])
                check("  ..every pair announced goes out, each a hit on the dog",
                      (last(got, "faAim", "num_shots"), pairs_of(got)),
                      (shots, [("faShot", 1), ("faHit", dog.eid), ("faShot", 0)] * shots))
                dealt = sum(p["dmg"] + p["sdmg"] for p in named(got, "faHit"))
                check("  ..and the dog takes what the client is shown",
                      (dealt > 0, (hp - dog.hp) + (sp - dog.sp)), (True, dealt))
                check("  ..the rounds and the action points paid",
                      (last(got, "ss_di_firearm", "ammo_count"),
                       last(got, "c_ap", "ap")),
                      (ammo - shots, sess.combat.ap_max - si["fire_costs"][mode]))

            # --- the dog dies during the aim; the ground at his feet ----------------------
            row = gun(sess, PISTOL, PISTOL_MODE, 5)
            got = await shoot(sess, row, dog.eid, before=lambda: rc.kill(dog, None))
            check("a pistol at the dog on his hex, dead before the aim ran out: a miss at "
                  "its hex, nothing at the loop",
                  (pairs_of(got), unhandled()), ([("faShot", 1), ("faMiss", None),
                                                  ("faShot", 0)], []))
            got = await shoot(sess, row, ("hex", sess.pos))
            check("a shot at the ground he stands on: one ack, a miss, nothing at the loop",
                  ([n for n, _p in got].count("cmdAck"), pairs_of(got), unhandled()),
                  (1, [("faShot", 1), ("faMiss", None), ("faShot", 0)], []))
            for _ in range(50):
                await asyncio.sleep(0.02)
                if dog.alive:
                    break
            check("the dog back under him again", (dog.alive, dog.cell), (True, sess.pos))

            # --- whatever the resolver fails on, the burst is closed ----------------------
            def fault(*_a, **_k):
                raise RuntimeError("a fault of the test's own")

            row = gun(sess, MG, MG_MODE, 30)
            records.records.clear()
            with patch.object(combat, "flight", fault):
                got = await shoot(sess, row, dog.eid)
            check("a fault inside the burst: nothing reaches the loop", unhandled(), [])
            check("  ..faAim's three pairs go out all the same, each a miss",
                  pairs_of(got), [("faShot", 1), ("faMiss", None), ("faShot", 0)] * 3)
            check("  ..paid as the miss it became: three rounds, 27 points, the c_ap",
                  (last(got, "ss_di_firearm", "ammo_count"), last(got, "c_ap", "ap")),
                  (27, sess.combat.ap_max - items.params_of(MG)["fire_costs"][MG_MODE]))
            faulted = [r for r in records.records if r.levelname == "ERROR"]
            check("  ..and the error log has it once, from the game, with its traceback",
                  [(r.name, r.exc_info is not None and r.exc_info[0].__name__,
                    "go out as misses" in r.getMessage()) for r in faulted],
                  [("lava", "RuntimeError", True)])
            sturdy(dog)
            hp = dog.hp
            got = await shoot(sess, row, dog.eid)
            check("the next shot goes as ever: three hits on the dog",
                  (pairs_of(got), dog.hp < hp, unhandled()),
                  ([("faShot", 1), ("faHit", dog.eid), ("faShot", 0)] * 3, True, []))

            claws = combat.Weapon(num_shots=2, dmin=1, dmax=1, opt_lo=1, opt_hi=3,
                                  max_range=6, piercing=1, cone=0.1, crit=0,
                                  skill=None, spec=None)
            sess.writer.frames.clear()
            records.records.clear()
            try:
                with patch.object(combat, "flight", fault):
                    rc.mob_burst(dog, sess.combat, claws)
                raised = None
            except Exception as exc:
                raised = repr(exc)
            got = list(sess.writer.frames)
            check("a creature's burst that fails: its two pairs go out, misses, nothing raised",
                  (raised, [(n, p.get("status")) for n, p in got
                            if n in ("faShot", "faMiss", "faHit")]),
                  (None, [("faShot", 1), ("faMiss", None), ("faShot", 0)] * 2))
            check("  ..logged once", [r.name for r in records.records
                                     if r.levelname == "ERROR"], ["lava"])

            # --- the line of fire asked before the burst; the hits applied after ----------
            # Fighter.fire_now asks whether the rounds could reach the mark at
            # all (RoomCombat.within_fire, the same shot_wall the resolver
            # walks) before the burst, and applies the hits after its pairs
            # went out. A fault in either was outside the guard: the first
            # sent no pair at all, the second left the shot unpaid and its
            # kill unsettled.
            row = gun(sess, MG, MG_MODE, 30)
            records.records.clear()
            with patch.object(combat, "shot_wall", fault):
                got = await shoot(sess, row, dog.eid)
            check("a fault in the line of fire asked before the burst: nothing reaches "
                  "the loop", unhandled(), [])
            check("  ..faAim's three pairs go out all the same, each a miss",
                  pairs_of(got), [("faShot", 1), ("faMiss", None), ("faShot", 0)] * 3)
            check("  ..paid as the miss it became: three rounds, 27 points, the c_ap",
                  (last(got, "ss_di_firearm", "ammo_count"), last(got, "c_ap", "ap")),
                  (27, sess.combat.ap_max - items.params_of(MG)["fire_costs"][MG_MODE]))
            check("  ..the error log has it from the game, with its traceback: the "
                  "question before the burst, then the burst's own line",
                  [(r.name, r.exc_info is not None and r.exc_info[0].__name__)
                   for r in records.records if r.levelname == "ERROR"],
                  [("lava", "RuntimeError")] * 2)

            def once(original):
                """original, except that its first call raises."""
                calls = []

                def wrapped(*a, **k):
                    if not calls:
                        calls.append(1)
                        raise RuntimeError("a fault of the test's own")
                    return original(*a, **k)
                return wrapped

            sturdy(dog)
            hp = dog.hp
            row = gun(sess, MG, MG_MODE, 30)
            records.records.clear()
            with patch.object(rc, "push_vitals", once(rc.push_vitals)):
                got = await shoot(sess, row, dog.eid)
            check("a fault in applying the hits after the pairs went out (the dog's usrUp): "
                  "nothing reaches the loop", unhandled(), [])
            check("  ..the three pairs went out, hits on the dog, and it took them",
                  (pairs_of(got), dog.hp < hp),
                  ([("faShot", 1), ("faHit", dog.eid), ("faShot", 0)] * 3, True))
            check("  ..the shot is paid: three rounds, 27 points, the c_ap",
                  (last(got, "ss_di_firearm", "ammo_count"), last(got, "c_ap", "ap")),
                  (27, sess.combat.ap_max - items.params_of(MG)["fire_costs"][MG_MODE]))
            check("  ..and the error log has it once, from the game, with its traceback",
                  [(r.name, r.exc_info is not None and r.exc_info[0].__name__)
                   for r in records.records if r.levelname == "ERROR"],
                  [("lava", "RuntimeError")])

            dog.hp, dog.sp = 1, dog.sp_max
            row = gun(sess, MG, MG_MODE, 30)
            records.records.clear()
            with patch.object(rc, "push_vitals", once(rc.push_vitals)):
                got = await shoot(sess, row, dog.eid)
            # (Whether it stands again by now is the respawn's business: the
            # frame of its death is what tells.)
            check("the same fault on the burst that brings the dog down: nothing at the "
                  "loop, and the dog is killed (lch dead), not left standing at 0",
                  (unhandled(), [p.get("dead") for p in named(got, "lch") if "dead" in p]),
                  ([], [dog.eid]))
            check("  ..paid as ever", last(got, "c_ap", "ap"),
                  sess.combat.ap_max - items.params_of(MG)["fire_costs"][MG_MODE])
        finally:
            sess.close()
            logging.getLogger().removeHandler(records)


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("the point-blank scene crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("point blank OK")
