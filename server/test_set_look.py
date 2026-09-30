"""A full set's figure: the wearer's own, and everybody else's view of it.

The client works the figure out for its own character -- PersEquip.
getFullSetID and checkFullSet on every addItem/removeItem, with the res
ss_si_set brought -- and cannot for anybody else's: a stranger's ss_ack
stores the wear list (wear_arr) and fills no slot. So the server tells the
room: set_res on the ss_ack the client asks for when it places a player,
and five ss_obj_move when a figure changes while it looks
(inventory.py, "the figure").

The figures are the owner's, in data/sets.json: Колонист (A) wears his
res 102, a folder res/personages has, and Беженец (A), which he left at 0,
is the full set without one (held to 0 here should he change his mind).

In process first: sets.look against getFullSetID, look_frames replayed
through a transcription of the client's PersEquip. Then two Sessions in one
room, driven frame by frame the way test_relogin drives them, so the order
of what each client receives is exact: Alice puts Колонист on piece by
piece, takes a piece off, lets one break, Bob steps out to the map and back
while she changes, and she logs out and in again. Last, Bob opens the
inspect window on her after a change, which puts the wear list of his last
ss_ack back on her slots, and meets her again. After every step Bob's copy
of her figure is replayed from the frames he got, and so is Alice's own,
and neither side ever gets a cmdAck or an ss_ack it did not ask for.

    LAVA_RES=.../lava/res python3 server/test_set_look.py
"""
import asyncio
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "setlook.db")
os.environ["LAVA_DB"] = DB
# Alice and Bob must wake in one room: a new character's start is drawn from
# server.START_PLACES (181 or 183), and two draws part them about half the
# time. The suite's own server gets the one start, as run_suite asks of a
# suite that needs a switch.
os.environ["LAVA_START"] = "181"

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import sets  # noqa: E402
from inventory import ARMOR, BAG, BELT, BOOTS, CAMO, HEAD, LEGS, PRIMARY, SET_SLOTS  # noqa: E402
from protocol import decode  # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


FIG = 11167            # Колонист (A): a set with a figure of its own
BARE = 11218           # Беженец (A): a full set with none
# The figures are the owner's (data/sets.json, test_sets holds them to his
# page): Колонист draws res/personages/102, Беженец is his "0". Should he
# give Беженец a figure too, it is held to 0 here, for a full set without one.
RES_A = sets.SETS[FIG]["res"]
sets.SETS[BARE]["res"] = 0
SLOT = {"helm": HEAD, "shirt": CAMO, "armor": ARMOR, "pants": LEGS, "boots": BOOTS}
FIG_T = sets.SETS[FIG]["members"]              # helm, shirt, armor, pants, boots -> type
BARE_T = sets.SETS[BARE]["members"]
BELT_BARE = 3577
FEMALE = 128           # avatars/list.xml: 128 and up are women (PersInfo.boolSex)


# --- the client, transcribed ---------------------------------------------------
class Seen:
    """What one client holds of one player's figure: PersEquip's six wear
    slots (slots_arr: head, camouflage, armor, belt, legs, boots) and
    PersInfo.setResID, run the way the client runs them. Every item is
    taken as inited; set_type is the table's, res whatever `res_of` says the
    client's ss_si_set carried."""

    def __init__(self, res_of, sex):
        self.slots = [None] * 6
        self.set_res = None
        self.res_of = res_of
        self.sex = sex
        self.wear = []          # wear_arr: a stranger's list from the last ss_ack

    @property
    def drawn_as(self):
        """PersInfo.persType: the set's figure over the body the sex picks."""
        return self.set_res or self.sex

    def full_set(self):
        """getFullSetID: head, then armour, shirt, legs, boots, one set_type."""
        head = self.slots[0]
        if head is None:
            return None
        st = sets.set_of(inventory.parse_oid(head)[1])
        for i in (2, 1, 4, 5):
            it = self.slots[i]
            if it is None or sets.set_of(inventory.parse_oid(it)[1]) != st:
                return None
        return st

    def check_full_set(self):
        st = self.full_set()
        if st:
            res = self.res_of(st)
            if res:             # a set without a figure leaves setResID alone
                self.set_res = res
        else:
            self.set_res = None

    def add(self, i, item):
        """PersEquip.addItem: Slot.addItem replaces; an undefined item adds
        nothing (StuffManager.addItem), and checkFullSet runs regardless."""
        if item:
            self.slots[i] = item
        self.check_full_set()

    def remove(self, i):
        self.slots[i] = None
        self.check_full_set()

    def ss_obj_move(self, p):
        """PersEquip.ss_obj_move for a stranger (PlayerRegister routes id=0
        nowhere, so a gamer's own never comes through here)."""
        obj = str(p["obj"])
        item = obj if obj != "0" and len(obj) > 1 else None
        if p["from"] >> 8 == 1:
            self.remove(p["from"] & 0xFF)
        if p["to"] == PRIMARY:
            return
        if p["to"] >> 8 == 1:
            self.add(p["to"] & 0xFF, item)

    def ss_ack(self, p, gamer):
        """PersEquip.ss_ack with the wear bit: the gamer's slots are filled
        (parseWear), a stranger's only stored; then set_res if truthy
        (SHOW_OWN_WEAR_SET is on by default)."""
        if gamer:
            for i, oid in enumerate(p["o_list"][:6]):
                self.add(i, str(oid) if str(oid) != "0" else None)
        else:
            self.wear = [str(oid) for oid in p["o_list"][:6]]
        if p.get("set_res"):
            self.set_res = p["set_res"]

    def inspect(self):
        """InspectInterface.setPlayer -> parseWear() with no list: wear_arr
        goes back on the slots one by one, an x0 or a missing entry adding
        nothing (createItem makes no item of it) and so leaving its slot as
        it is, and checkFullSet runs after each."""
        for i in range(6):
            oid = self.wear[i] if i < len(self.wear) else "0"
            self.add(i, oid if oid != "0" and len(oid) > 1 else None)

    def own_move(self, oid, src, dst):
        """applyTransfer after cmdAck;res=0, into an empty slot."""
        if src >> 8 == 1:
            self.remove(src & 0xFF)
        if dst >> 8 == 1:
            self.add(dst & 0xFF, oid)


def table_res(st):
    return sets.frame(st)["res"]


# --- in process ------------------------------------------------------------------
print("sets.look: what getFullSetID and checkFullSet make of five slots")
check("the file gives Колонист a figure to test with", RES_A > 0, True)
fig = [FIG_T[n] for n in sets.SLOTS]
bare = [BARE_T[n] for n in sets.SLOTS]
check("five pieces of one set: its res", sets.look(fig), RES_A)
check("  ..and ss_si_set carries the same", sets.frame(FIG)["res"], RES_A)
check("four and an empty slot: the body's own", sets.look(fig[:4] + [None]), 0)
check("four and a piece of another set: the body's own", sets.look(fig[:4] + [bare[4]]), 0)
check("a full set whose res is 0: the body's own", sets.look(bare), 0)
check("five things of no set: the body's own", sets.look([BELT_BARE] * 5), 0)
check("fewer than five slots named: nothing", sets.look(fig[:4]), 0)

_uniq = [0]


def row(type_id, slot, brk=100):
    _uniq[0] += 1
    return dict(uniq=_uniq[0], type_id=type_id, root=items.root_of(type_id), slot=slot,
                brk=brk)


suit = [row(FIG_T[n], SLOT[n]) for n in sets.SLOTS]
check("inventory.look_of: the five on the body", inventory.look_of(suit), RES_A)
check("  ..a broken piece still wears the figure (getFullSetID reads no __break)",
      inventory.look_of(suit[:4] + [dict(suit[4], brk=0)]), RES_A)
check("  ..a belt and a pistol beside it change nothing",
      inventory.look_of(suit + [row(BELT_BARE, BELT), row(4600, PRIMARY)]), RES_A)
check("  ..one of them in the bag: the body's own",
      inventory.look_of(suit[:4] + [dict(suit[4], slot=BAG)]), 0)

frames = inventory.look_frames(1000042, suit[:2] + suit[3:])
check("look_frames: one ss_obj_move per counted slot, head to boots, each slot its own from and to",
      [(n, p["id"], p["from"], p["to"]) for n, p in frames],
      [("ss_obj_move", 1000042, s, s) for s in SET_SLOTS])
check("  ..carrying what is in it now, x0 for nothing",
      [str(p["obj"]) for _n, p in frames],
      [inventory.oid_of(suit[0]), inventory.oid_of(suit[1]), "0",
       inventory.oid_of(suit[3]), inventory.oid_of(suit[4])])

# A stale copy: the client last saw her in Беженец and was told Колонист's
# figure by an ss_ack since (set_res sets, the slots stay). Now she wears
# Беженец again, a set without a figure: checkFullSet would leave setResID
# as it is on a full Беженец, so only the emptying at each frame's start
# takes the old figure away.
seen = Seen(table_res, FEMALE)
bare_rows = [row(BARE_T[n], SLOT[n]) for n in sets.SLOTS]
for _n, p in inventory.look_frames(1000042, bare_rows):
    seen.ss_obj_move(p)
seen.ss_ack({"o_list": [], "set_res": RES_A}, gamer=False)
check("stale: a copy of Беженец on the slots and Колонист's figure from an ss_ack",
      (seen.full_set(), seen.drawn_as), (BARE, RES_A))
for _n, p in inventory.look_frames(1000042, bare_rows):
    seen.ss_obj_move(p)
check("  ..the five frames of her Беженец bring her own body back", seen.drawn_as, FEMALE)
for _n, p in inventory.look_frames(1000042, suit):
    seen.ss_obj_move(p)
check("  ..and five of Колонист its figure", seen.drawn_as, RES_A)
for _n, p in inventory.look_frames(1000042, suit[:4]):
    seen.ss_obj_move(p)
check("  ..and five with the boots gone, her body again", seen.drawn_as, FEMALE)


# --- two players in one room --------------------------------------------------------
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("alice", "secret")
_store.register("bob", "secret")
_store.close()
ALICE = accounts.credential("alice", "secret")
BOB = accounts.credential("bob", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.read = 0
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def new(sess):
    """What this client received since the last call."""
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def names(frames, *only):
    return [n for n, _p in frames if not only or n in only]


def of(frames, name):
    return [p for n, p in frames if n == name]


def wire_res(sess):
    """res_of for a Seen: what ss_si_set says on this client's socket,
    asked once per set as SetManager does. The answer is taken as read
    only when nothing else was waiting to be."""
    cache = {}

    def res_of(st):
        if st not in cache:
            w = sess.writer
            start = len(w.frames)
            caught_up = w.read == start
            run(sess, "ss_get_s_si;type=%d;" % st)
            cache[st] = of(w.frames[start:], "ss_si_set")[0]["res"]
            if caught_up:
                w.read = len(w.frames)
        return cache[st]
    return res_of


def enter(sess, cred, create=None):
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % cred)
    if create:
        run(sess, create)
        run(sess, "actPlayer;")
    else:
        run(sess, "selPers;num=0;")
    run(sess, "lenter;accept=1;")
    return new(sess)


def placed(frames):
    """Players placed by lch (rtype=-1), as the client builds them."""
    return [p["newUser"] for n, p in frames if n == "lch" and p.get("rtype") == -1]


async def main():
    a = server.Session(Writer(), "a")
    enter(a, ALICE, "newPers;res=49327;sex=%d;name=@Alice@;" % FEMALE)
    b = server.Session(Writer(), "b")
    got = enter(b, BOB, "newPers;res=1;sex=0;name=@Bob@;")
    pid_a = a.pid
    check("Bob comes into Alice's room and has her placed", placed(got), [pid_a])
    check("Alice is told of him", placed(new(a)), [b.pid])

    alice = server.STORE.character_by_name("Alice")["id"]
    # At Колонист's level (2), which the level rule asks of whoever wears it
    # (inventory.py, "the level"); her logout saves it for the relog below.
    lvl = max(inventory.item_level(t) for t in FIG_T.values())
    a.char.skill[progression.SHOOTING] = [lvl, 0, progression.skill_xp_max(lvl)]
    a.char.recalc()

    def bag(type_id, brk=None):
        f = inventory.new_fields(type_id)
        return server.STORE.create_item(alice, type_id, f["root"], slot=BAG,
                                        brk=f["brk"] if brk is None else brk,
                                        max_break_cur=f["max_break_cur"])

    rows = {n: bag(FIG_T[n]) for n in sets.SLOTS}
    oid = {n: inventory.oid_of(r) for n, r in rows.items()}

    # Both clients learn the set's res as every client does, from ss_si_set.
    res_a, res_b = wire_res(a), wire_res(b)
    check("ss_si_set carries the figure to the wearer and to the viewer",
          (res_a(FIG), res_b(FIG)), (RES_A, RES_A))
    own = Seen(res_a, FEMALE)
    hers = Seen(res_b, FEMALE)          # Bob's copy of Alice

    run(a, "ss_get;target=0;slot=11;")
    got = new(a)
    check("Alice's own gear: one ss_ack, no set_res while she wears nothing",
          (names(got), "set_res" in got[0][1]), (["ss_ack"], False))
    own.ss_ack(got[0][1], gamer=True)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("Bob asks for hers: one ss_ack, no set_res, nothing after it",
          (names(got), "set_res" in got[0][1]), (["ss_ack"], False))
    hers.ss_ack(got[0][1], gamer=False)
    check("  ..both draw her as her own body", (own.drawn_as, hers.drawn_as), (FEMALE, FEMALE))

    def move(name, dst, label, bob_sees):
        """Alice moves one piece; her answer is one cmdAck and her own
        ss_obj_move, and Bob gets the five frames or none of them."""
        r = rows[name]
        src = r["slot"]
        run(a, "ss_move;obj=x%s;to=%d;from=%d;" % (oid[name], dst, src))
        r["slot"] = dst
        mine, his = new(a), new(b)
        check(label + ": Alice gets one cmdAck, res 0, no ss_ack",
              (names(mine, "cmdAck", "ss_ack"), of(mine, "cmdAck")[0]["res"]), (["cmdAck"], 0))
        check("  ..and of ss_obj_move only her own, as id 0",
              [p["id"] for p in of(mine, "ss_obj_move")], [0])
        own.own_move(oid[name], src, dst)
        check("  ..Bob gets no cmdAck and no ss_ack", names(his, "cmdAck", "ss_ack"), [])
        moves = of(his, "ss_obj_move")
        if bob_sees:
            check("  ..and five ss_obj_move about her, head to boots, each slot to itself",
                  [(p["id"], p["from"], p["to"]) for p in moves],
                  [(pid_a, s, s) for s in SET_SLOTS])
            on = {r2["slot"]: oid[n2] for n2, r2 in rows.items() if r2["slot"] != BAG}
            check("  ..each with what she now has there",
                  [str(p["obj"]) for p in moves], [on.get(s, "0") for s in SET_SLOTS])
        else:
            check("  ..and not a frame about her figure", moves, [])
        for p in moves:
            hers.ss_obj_move(p)
        return mine, his

    print()
    print("putting it on")
    for n in ("helm", "shirt", "armor", "pants"):
        move(n, SLOT[n], "%s on" % n, bob_sees=False)
        check("  ..she still looks herself, to herself and to Bob",
              (own.drawn_as, hers.drawn_as), (FEMALE, FEMALE))
    move("boots", BOOTS, "the boots, the fifth", bob_sees=True)
    check("  ..she wears the set's figure on her own screen", own.drawn_as, RES_A)
    check("  ..and on Bob's", hers.drawn_as, RES_A)
    check("  ..and the server counts it so", a.inv.look, RES_A)

    run(b, "getInfo;lvl=0;id=%d;type=0;" % pid_a)
    info = of(new(b), "userInfo_Player")[0]
    check("her userInfo_Player still says her own sex and portrait: the figure is set_res's alone",
          (info["sex"], info["res"]), (FEMALE, "49327"))

    print()
    print("taking one off and back")
    move("armor", BAG, "armour off", bob_sees=True)
    check("  ..her own body again, both sides", (own.drawn_as, hers.drawn_as), (FEMALE, FEMALE))
    move("armor", ARMOR, "armour on", bob_sees=True)
    check("  ..the figure again, both sides", (own.drawn_as, hers.drawn_as), (RES_A, RES_A))

    print()
    print("a piece breaking")
    boots = server.STORE.item(rows["boots"]["uniq"])
    a.inv.wear(boots, boots["brk"] + 1000)
    mine, his = new(a), new(b)
    check("the boots give out: Alice is told their break", names(mine, "ss_di_wear"),
          ["ss_di_wear"])
    check("  ..Bob gets no frame about her figure", of(his, "ss_obj_move"), [])
    check("  ..and nobody an ss_ack or a cmdAck", names(mine + his, "cmdAck", "ss_ack"), [])
    check("  ..she keeps the figure: getFullSetID reads no __break", a.inv.look, RES_A)

    print()
    print("Bob away while she changes")
    run(b, "chWorld;")
    check("Bob steps out to the map", names(new(b)), ["cmdAck", "gmap", "marks"])
    check("  ..Alice sees him go", names(new(a)), ["lch"])
    move("armor", BAG, "armour off with nobody there", bob_sees=False)
    run(b, "chWorld;")
    run(b, "lenter;accept=1;")
    got = new(b)
    check("Bob comes back into her room", placed(got), [pid_a])
    new(a)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("he asks for her gear: the ss_ack, then five ss_obj_move to take the figure away",
          names(got), ["ss_ack"] + ["ss_obj_move"] * 5)
    check("  ..no set_res in the ss_ack", "set_res" in got[0][1], False)
    hers.ss_ack(got[0][1], gamer=False)
    check("  ..which alone could not have done it: the client ignores a 0",
          hers.drawn_as, RES_A)
    for p in of(got, "ss_obj_move"):
        hers.ss_obj_move(p)
    check("  ..the frames did: her own body", hers.drawn_as, FEMALE)
    check("  ..and Alice is sent nothing for it", new(a), [])

    run(b, "chWorld;")
    new(b)
    new(a)
    move("armor", ARMOR, "armour back on with nobody there", bob_sees=False)
    run(b, "chWorld;")
    run(b, "lenter;accept=1;")
    new(b)
    new(a)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("back again with her in the set: one ss_ack with set_res, nothing after it",
          (names(got), got[0][1].get("set_res")), (["ss_ack"], RES_A))
    hers.ss_ack(got[0][1], gamer=False)
    check("  ..the figure", hers.drawn_as, RES_A)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("asking again changes nothing: the same one ss_ack",
          (names(got), got[0][1].get("set_res")), (["ss_ack"], RES_A))

    print()
    print("Alice logs out and in")
    run(a, "logout;")
    check("Bob sees her go", [p.get("lostUser") for p in of(new(b), "lch")], [pid_a])
    a2 = server.Session(Writer(), "a2")
    enter(a2, ALICE)
    check("she comes back into his room", placed(new(b)), [pid_a])
    check("  ..counted in the set from the load", a2.inv.look, RES_A)
    run(a2, "ss_get;target=0;slot=11;")
    got = new(a2)
    check("her own ss_ack carries set_res, as PersEquip's isGamer branch reads it",
          (names(got), got[0][1].get("set_res")), (["ss_ack"], RES_A))
    own = Seen(wire_res(a2), FEMALE)    # a new connection: a fresh client
    own.ss_ack(got[0][1], gamer=True)
    check("  ..and her client draws her so", own.drawn_as, RES_A)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("Bob asks for hers: set_res, and nothing more",
          (names(got), got[0][1].get("set_res")), (["ss_ack"], RES_A))
    hers.ss_ack(got[0][1], gamer=False)
    check("  ..the figure", hers.drawn_as, RES_A)

    a = a2
    move("helm", BAG, "the helm off after the relog", bob_sees=True)
    check("  ..her own body, both sides", (own.drawn_as, hers.drawn_as), (FEMALE, FEMALE))

    print()
    print("Bob inspects her after the change")
    # The window asks the server for nothing: setPlayer puts back the list
    # of his last ss_ack about her, which was the whole set.
    hers.inspect()
    check("the inspect window puts his last ss_ack's list back on: the set's figure again",
          (hers.full_set(), hers.drawn_as), (FIG, RES_A))
    run(b, "chWorld;")
    new(b)
    new(a)
    run(b, "chWorld;")
    run(b, "lenter;accept=1;")
    check("Bob comes back into her room", placed(new(b)), [pid_a])
    new(a)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    got = new(b)
    check("he asks for her gear: the ss_ack, then five ss_obj_move, though the last"
          " frames he got showed her own body",
          names(got), ["ss_ack"] + ["ss_obj_move"] * 5)
    hers.ss_ack(got[0][1], gamer=False)
    check("  ..the ss_ack alone leaves the inspect window's figure", hers.drawn_as, RES_A)
    for p in of(got, "ss_obj_move"):
        hers.ss_obj_move(p)
    check("  ..the frames take it away: her own body", hers.drawn_as, FEMALE)
    hers.inspect()
    check("  ..and another inspect keeps it: the list it puts back has no helm",
          hers.drawn_as, FEMALE)
    run(b, "ss_get;target=%d;slot=3;" % pid_a)
    check("asked once more: one ss_ack and nothing after it, that list making no figure",
          names(new(b)), ["ss_ack"])
    check("  ..and Alice is sent nothing for any of it", new(a), [])
    for who, sess in (("Alice", a), ("Bob", b)):
        check("%s received exactly one ss_ack per ss_get sent, over the whole run" % who,
              len(of(sess.writer.frames, "ss_ack")), ASKED.get(id(sess), 0))
    run(a, "logout;")
    run(b, "logout;")


# How many ss_get each session has sent, for the last check.
ASKED = {}
_run = run


def run(sess, text):  # noqa: F811
    if text.startswith("ss_get;"):
        ASKED[id(sess)] = ASKED.get(id(sess), 0) + 1
    _run(sess, text)


class Errors(logging.Handler):
    """Session.handle logs a failing handler and carries on, so a bug in
    the push would otherwise show only as frames missing."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.seen = []

    def emit(self, record):
        self.seen.append(self.format(record))


errors = Errors()
lava_log = logging.getLogger("lava")
lava_log.propagate = False
lava_log.addHandler(errors)
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()
check("and no handler failed on the way", errors.seen, [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("set look OK")
