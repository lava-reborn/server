"""The Nubian valley's tutorial, the first batch of its quests (the owner's
«давай готовь квесты все», 2026-09-26), walked on a socket on the real
data/quests.json: both starts and the chain that follows them, seventeen
quests, types 11-27. The two starts exclude each other (the rows'
"excludes", the owner's «делай» of the same day): one character walks the
north and the chain, a second the west, and each is shut out of the
other's -- the starter gear comes once (test_start holds the rest: where a
character wakes, and who is offered what).

  north   «Добро пожаловать» Думисани -> Зула (Шорты, +20 Медицина);
          «Друзья» Зула -> Салех, the milk of «Подоить корову», the cow's
          own quest in the pasture above the village (Самодельные тапки);
          «Финансовая система» Салех -> Гарард, a parcel carried to the
          market (Панама, 100 afro)
  west    «Добро пожаловать» Джеррах -> Ибрахим; «Друзья» Ибрахим, the
          tools of «Забрать инструменты», the box's quest in 184 (tools and
          50 afro); «Финансовая система» Ибрахим -> Гарард
  market  «Немного мудрости» (Шило), «Стреляем» -- three rats shot in 184,
          the Наган in the window and fifty rounds beside it --, «Снабжение»,
          «Провиант» (a box of meat carried), «Мертвые беззащитны» (three
          dog skins), «Шелковый путь» (the silk bought at the bottom of
          Локсли's list), «Доверие» (to Сейфул's squad), «Доклад» (back to
          Джеррах, 20 experience), «Слава или смерть» (an ear)

Each group is held to its take (one ack, then the journal), its progress
(the bag, the kills, the journal told), its hand-in (what the quest asked
for out of the bag, the reward in: the thing, the experience, the money,
all before the ack) and to the chain it opens: a quest is offered only once
the one before it is handed in, and a one-off quest handed in is not
offered again. None of them counts against the daily limit.

In process: the rows, their texts laid over from the original
(data/orig_misc.json, data/build_orig_misc.py VERIFIED), every string id in
the launcher's table, every giver and taker standing in the valley as an
inhabitant the client opens quests for, the chain as the wiki draws it, the
milk and the tools kept at a death, the silk last on Локсли's list.

    LAVA_RES=.../lava/res python3 server/test_valley_quests.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


# The quests, by type.
(WELCOME_N, FRIENDS_N, COW_Q, FINANCE_N, WELCOME_W, FRIENDS_W, BOX_Q, FINANCE_W,
 WISDOM, SHOOT, SUPPLY, PROVISIONS, DOGS, SILK_Q, TRUST, REPORT, GLORY) = range(11, 28)
VALLEY = list(range(11, 28))
NORTH_Q, WEST_Q = [WELCOME_N, FRIENDS_N, COW_Q, FINANCE_N], [WELCOME_W, FRIENDS_W, BOX_Q,
                                                             FINANCE_W]
# Who gives and takes them.
DUMISANI, ZULA, SALEH, COW, JERRAH, IBRAHIM = 5207, 5200, 5190, 5195, 5206, 5210
BOX, GARARD, AMINA, LOXLEY, SEIFUL = 1135, 5187, 5185, 5213, 35
# What they hand over and pay.
SHORTS, SLIPPERS, PANAMA, PONCHO, ARMOR, AWL = 10062, 10063, 10059, 10060, 10061, 6229
NAGAN, ROUNDS = 25567, 6094
MILK, PARCEL, MEAT, SILK, TOOLS, SKIN, EAR = 3479, 3480, 3481, 3482, 3483, 218, 1495
RAT = 1023
MEDICINE, SHOOTING = progression.MEDICINE, progression.SHOOTING
VILLAGE, WEST, BURIALS, MARKET, SQUAD, PASTURE = 181, 183, 184, 185, 29, 182
ADMIN_GUN, GUN_ROUNDS = 1534, 6092

# The chain as the wiki draws it: parent -> child ("Родительский квест").
CHAIN = {WELCOME_N: [], FRIENDS_N: [WELCOME_N], COW_Q: [], FINANCE_N: [FRIENDS_N],
         WELCOME_W: [], FRIENDS_W: [WELCOME_W], BOX_Q: [], FINANCE_W: [FRIENDS_W],
         WISDOM: [], SHOOT: [WISDOM], SUPPLY: [SHOOT], PROVISIONS: [SUPPLY],
         DOGS: [PROVISIONS], SILK_Q: [DOGS], TRUST: [SILK_Q], REPORT: [TRUST],
         GLORY: [REPORT]}
GIVE_TAKE = {WELCOME_N: (DUMISANI, ZULA), FRIENDS_N: (ZULA, SALEH), COW_Q: (COW, COW),
             FINANCE_N: (SALEH, GARARD), WELCOME_W: (JERRAH, IBRAHIM),
             FRIENDS_W: (IBRAHIM, IBRAHIM), BOX_Q: (BOX, BOX), FINANCE_W: (IBRAHIM, GARARD),
             WISDOM: (GARARD, GARARD), SHOOT: (GARARD, IBRAHIM), SUPPLY: (IBRAHIM, AMINA),
             PROVISIONS: (AMINA, IBRAHIM), DOGS: (IBRAHIM, AMINA), SILK_Q: (AMINA, JERRAH),
             TRUST: (JERRAH, SEIFUL), REPORT: (SEIFUL, JERRAH), GLORY: (JERRAH, JERRAH)}
WHERE = {DUMISANI: VILLAGE, ZULA: VILLAGE, SALEH: VILLAGE, COW: PASTURE, JERRAH: WEST,
         IBRAHIM: WEST, BOX: BURIALS, GARARD: MARKET, AMINA: MARKET, SEIFUL: SQUAD}

# --- in process: the table ------------------------------------------------------------
MT = world.mob_types()
try:
    rows = [quests.get(t) for t in VALLEY]
    check("the seventeen quests of the valley's tutorial are in the table",
          [q is not None for q in rows], [True] * 17)
    check("  ..each a one-off, as the wiki says «не повторяемым», none of them"
          " counted by the daily limit",
          ([q.repeatable for q in rows], [t for t in VALLEY if t in quests.repeatable_types()]),
          ([0] * 17, []))
    check("  ..given and taken by the NPCs the wiki names",
          {q.type: (q.give, q.take) for q in rows},
          {t: ([g], [k]) for t, (g, k) in GIVE_TAKE.items()})
    check("  ..in the chain the wiki draws", {q.type: q.need_all + q.need_any for q in rows},
          CHAIN)
    check("  ..the two starts shutting each other out, the cow and the box with them",
          {q.type: q.excludes for q in rows if q.excludes},
          {t: (WEST_Q if t in NORTH_Q else NORTH_Q) for t in NORTH_Q + WEST_Q})
    check("  ..appended: Джеррах's «Обмен слитка» is still his first (q_idx 0)",
          quests.given_by(JERRAH)[0], 10)
    orig = orig_texts.quests()
    with open(os.path.join(os.path.dirname(HERE), "data", "orig_misc.json"),
              encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts are the original's (data/orig_misc.json), all four where the file has"
          " them", [t for t in VALLEY if t not in pinned], [])
    check("  ..laid over the table's",
          [t for t in VALLEY for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig[t].get(key) and quests.get(t).texts[k] != quests.served(quests.get(t), k, orig[t][key])], [])
    check("  ..the newest edition: no line carries the 2012 number label",
          [t for t in VALLEY if any("№" in x for x in quests.get(t).texts)], [])
    check("  ..and the names the file has no line for are ours: «Провиант», «Доклад»",
          (pinned[PROVISIONS][0], pinned[REPORT][0], quests.get(PROVISIONS).name,
           quests.get(REPORT).name), (None, None, "Провиант", "Доклад"))
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has, and what they hand over is worth"
          " nothing away from them", quests.check_items(), None)
    # The givers and takers, where the client can open their quests: every
    # class but a mob's has the tab (NPCService.openService).
    stand = {}
    for lid in sorted(set(WHERE.values())):
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            stand.setdefault(n.type_id, set()).add((lid, n.root))
    check("each giver and taker stands where the quests send the player, not a mob",
          {npc: sorted(lid for lid, root in stand.get(npc, ()) if root != world.MOB)
           for npc in WHERE}, {npc: [lid] for npc, lid in WHERE.items()})
    check("the rats of «Стреляем» and the dogs of «Мертвые беззащитны» are in 184",
          sorted(t for t in (RAT, 82) if (BURIALS, world.MOB) in stand.get(t, ())),
          [82, RAT])
    check("the parcels and the box of meat are handed over at the take and worth nothing",
          {t: quests.get(t).start_obj for t in (FINANCE_N, FINANCE_W, PROVISIONS)},
          {FINANCE_N: [(PARCEL, 1)], FINANCE_W: [(PARCEL, 1)], PROVISIONS: [(MEAT, 1)]})
    check("the milk and the tools, paid by a one-off and asked for by the next, stay"
          " on the body at a death; the parcels too, and the skins do not",
          [combat.drops_on_death(t) for t in (MILK, TOOLS, PARCEL, MEAT, SKIN)],
          [False, False, False, False, True])
    check("«Стреляем» shows the Наган and gives fifty rounds beside it",
          (quests.get(SHOOT).rew_obj, quests.get(SHOOT).rew_also), ([NAGAN], [(ROUNDS, 50)]))
    check("the Наган takes those rounds first", items.params_of(NAGAN)["comp_array"][0], ROUNDS)
    check("Локсли sells the silk, last on his list, as the task says",
          items.stock_for(LOXLEY)[-1], SILK)
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "valley_quests.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("novice", "secret")
_store.register("westerner", "secret")
_store.close()
CRED = accounts.credential("novice", "secret")
CRED_W = accounts.credential("westerner", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="6268", LAVA_GY="1819", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="3", LAVA_SEED="5")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.seen = []

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        out = [decode(f.decode(ENC)) for f in parts if f]
        self.seen += out
        return out

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def order(frames):
    return [n for n, _p in frames]


def upto_ack(frames):
    seq = order(frames)
    return seq[:seq.index("cmdAck") + 1] if "cmdAck" in seq else seq


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(target_id):
    return "x1%08x" % target_id


def inhabitants(frames):
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, loc_id):
    """/goto a location: the arrival's frames."""
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def exit_cell(loc, side):
    cells = sorted(c for c, s in travel.exit_sides(loc).items() if s == side
                   and 0 <= c < loc.width * loc.height and c not in loc.obstacles)
    mx, my = travel._edge_middle(loc, side)
    return min(cells, key=lambda c: ((c % loc.width - mx) ** 2
                                     + (c // loc.width - my) ** 2, c))


def through(c, loc_id, side):
    """Walk out of a location by one side's exit: the next one's arrival."""
    c.send("moveTo;path=|%d|;" % exit_cell(world.location(loc_id), side))
    c.frames(0.4)
    c.send("chWorld;to=1;")
    call = first(c.until(lambda f: f[0] == "lcall", 2), "lcall")
    return call, (arrive(c) if call else [])


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, here, qtype):
    """q_st of a type from the first NPC of its giver's type here."""
    npc_type = GIVE_TAKE[qtype][0]
    npc = here.get(npc_type, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, qtype, q_id, obj_idx=0):
    npc = here.get(GIVE_TAKE[qtype][1], [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(0.9)


def store():
    return accounts.Store(DB)


def char_id(name="Novice"):
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def owned(cid, slot=inventory.BAG):
    """type id -> pieces of it in the bag."""
    st = store()
    out = {}
    for r in st.items_of(cid):
        if r["slot"] == slot:
            n = r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
            out[r["type_id"]] = out.get(r["type_id"], 0) + n
    st.close()
    return out


def experience(cid, skill):
    """All the experience a skill has had: its levels' worth and the rest."""
    st = store()
    row = [r for r in st.load_stats(cid) if r["kind"] == "skill" and r["idx"] == skill][0]
    st.close()
    return sum(progression.skill_xp_max(lvl) for lvl in range(row["value"])) + row["xp"]


def unpacked(mask, values):
    """index -> value of a packed group (progression.packed)."""
    out, it = {}, iter(values)
    for i in range(32):
        if mask & (1 << i):
            out[i] = next(it)
    return out


def skill_seen(c, skill):
    """All the experience a skill has had, as the client was last told of it
    (every rp_info seen, the kills' and the quests' alike): its levels'
    worth and the rest. The database lags the Character between saves; the
    frames do not."""
    level = xp = 0
    for n, p in c.seen:
        if n != "rp_info":
            continue
        level = unpacked(p["a_skills_mask"], p["a_skills"]).get(skill, level)
        xp = unpacked(p["xp_skills_mask"], p["xp_skills"]).get(skill, xp)
    return sum(progression.skill_xp_max(lvl) for lvl in range(level)) + xp


def no_level(seq):
    """A frame order with a level-up's usrUp left out: whether Стрельба
    crosses a level at a hand-in depends on what the rats paid for it."""
    return [n for n in seq if n != "usrUp"]


def done(cid):
    st = store()
    got = sorted(r["type"] for r in st.db.execute(
        "SELECT type FROM char_quests_done WHERE char_id = ?", (cid,)).fetchall())
    st.close()
    return got


def new_things(frames):
    """The type ids of what came into the bag (ss_obj_status 1), in order."""
    out = []
    for p in named(frames, "ss_obj_status"):
        oid = inventory.parse_oid(str(p["obj"]).lstrip("x"))
        if p.get("status") == 1 and oid:
            out.append(oid[1])
    return out


def purse(frames):
    got = named(frames, "userInfo_Player")
    return got[-1].get("afro") if got else None


def hunt(c, got, mob_type, gun, n):
    """In 184: shoot n creatures of this type, each from a cell it can be hit
    from and out of every hostile's reach; the frames of the fight."""
    here = world.location(BURIALS)
    homes = {p["newUser"]: p["pos"] for p in named(got, "lch") if "newUser" in p}
    hostile = [homes[e] for t, es in inhabitants(got).items()
               if t in (RAT, 82) for e in es if e in homes]
    reach = max(mobs.stats(t).aggro for t in (RAT, 82))
    out, killed = [], 0
    for eid in inhabitants(got).get(mob_type, []):
        if killed >= n:
            break
        home = homes.get(eid)
        if home is None:
            continue
        spots = sorted((mobs.hex_distance(cell, home, here.width), cell)
                       for cell in range(here.width * here.height)
                       if cell not in here.obstacles and travel.side_at(here, cell) is None
                       and all(mobs.hex_distance(cell, h, here.width) > reach + 0.5
                               for h in hostile)
                       and mobs.hex_distance(cell, home, here.width) <= 14
                       and mobs.line_of_fire(here, cell, home) is None)
        if not spots:
            continue
        c.send("moveTo;path=|%d|;" % spots[0][1])
        out += c.frames(0.6)
        for _ in range(30):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
            got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                           or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
            out += got_
            if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                killed += 1
                break
            time.sleep(0.3)
    return out, killed


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Novice@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    here = inhabitants(arrive(c))
    CID = char_id()
    AFRO0 = 1000

    # --- the north start ------------------------------------------------------------
    check("a newcomer in the village: Думисани's welcome, the cow's milk and Гарард's"
          " lesson are offered; what follows them is not",
          [status(c, t) for t in (WELCOME_N, FRIENDS_N, FINANCE_N, COW_Q, WISDOM, SHOOT,
                                  WELCOME_W, BOX_Q)], [1, 0, 0, 1, 1, 0, 1, 1])
    c.send("q_st;mob=%d;q_idx=0;" % here[ZULA][0])
    got = c.frames(0.6)
    check("«Друзья» taken before its time is refused, with one ack",
          (order(got), acks(got) != [0]), (["cmdAck"], True))
    got, q = take(c, here, WELCOME_N)
    check("«Добро пожаловать» taken from Думисани: the ack, then the journal, complete",
          (order(got), first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    got = hand_in(c, here, WELCOME_N, q)
    check("handed in to Зула: the shorts, the experience, the ack -- no q_sys, a"
          " one-off counts for nothing", (upto_ack(got), acks(got)),
          (["ss_obj_status", "ss_di_wear", "rp_info", "cmdAck"], [0]))
    check("  ..the shorts in the bag, twenty to Медицина",
          (owned(CID).get(SHORTS), experience(CID, MEDICINE)), (1, 20))
    check("  ..and «Друзья» is offered now, «Добро пожаловать» no more",
          [status(c, t) for t in (WELCOME_N, FRIENDS_N)], [0, 1])
    check("  ..nor anything of the west: Джеррах's welcome, Ибрахим's errands, the box",
          [status(c, t) for t in WEST_Q], [0, 0, 0, 0])
    got, q_friends = take(c, here, FRIENDS_N)
    check("«Друзья» taken from Зула: the milk not in the bag yet",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([0], 0)])
    got = hand_in(c, here, FRIENDS_N, q_friends)
    check("  ..and Салех takes nothing without it", (order(got), acks(got)), (["cmdAck"], [3]))

    call, got = through(c, VILLAGE, travel.N)
    here = inhabitants(got)
    check("north out of the village: the pasture, with the cows",
          (call.get("id"), len(here.get(COW, []))), (PASTURE, 3))
    got, q = take(c, here, COW_Q)
    check("«Подоить корову» taken from a cow, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, COW_Q, q) + c.frames(0.5)
    check("handed in to her: the milk into the bag before the ack",
          (upto_ack(got), acks(got)), (["ss_obj_status", "ss_di_heap", "cmdAck"], [0]))
    check("  ..and after it the journal: «Друзья» found and complete",
          [(p["q_id"], p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")],
          [(q_friends, [1], 1)])
    check("  ..the cow's quest is a one-off: not offered again", status(c, COW_Q), 0)

    call, got = through(c, PASTURE, travel.S)
    here = inhabitants(got)
    check("back south into the village", call.get("id"), VILLAGE)
    got = hand_in(c, here, FRIENDS_N, q_friends)
    check("«Друзья» handed in to Салех: the milk out, the slippers in, the experience",
          (upto_ack(got), acks(got)),
          (["ss_obj_status", "ss_obj_status", "ss_di_wear", "rp_info", "cmdAck"], [0]))
    have = owned(CID)
    check("  ..no milk, the slippers, forty to Медицина",
          (have.get(MILK), have.get(SLIPPERS), experience(CID, MEDICINE)), (None, 1, 40))
    got, q = take(c, here, FINANCE_N)
    check("«Финансовая система» taken from Салех: the parcel into the bag, the ack, the"
          " delivery found and complete",
          (order(got), first(got, "q_di_del_obj").get("obj"),
           first(got, "q_di_del_obj").get("complete"), owned(CID).get(PARCEL)),
          (["ss_obj_status", "ss_di_heap", "cmdAck", "q_di_del_obj"], 1, 1, 1))
    here = inhabitants(goto(c, MARKET))
    got = hand_in(c, here, FINANCE_N, q)
    check("handed in to Гарард on the market: the parcel out, the panama in, the"
          " experience, the hundred afro, the ack",
          (upto_ack(got), acks(got), purse(got)),
          (["ss_obj_status", "ss_obj_status", "ss_di_wear", "rp_info", "userInfo_Player",
            "cmdAck"], [0], AFRO0 + 100))
    have = owned(CID)
    check("  ..no parcel, the panama, seventy to Медицина",
          (have.get(PARCEL), have.get(PANAMA), experience(CID, MEDICINE)), (None, 1, 70))

    # --- Гарард's lesson and his rats ------------------------------------------------------
    got, q = take(c, here, WISDOM)
    got = hand_in(c, here, WISDOM, q)
    check("«Немного мудрости»: the awl, the experience -- Медицина's first level, so the"
          " bars follow", (upto_ack(got), acks(got), owned(CID).get(AWL)),
          (["ss_obj_status", "ss_di_coldarm", "rp_info", "usrUp", "cmdAck"], [0], 1))
    check("  ..a hundred and ten to Медицина, its first level",
          experience(CID, MEDICINE), 110)
    check("«Стреляем» offered now", status(c, SHOOT), 1)
    got, q_shoot = take(c, here, SHOOT)
    check("«Стреляем» taken from Гарард: nought of three",
          [(p["kill_num"], p["complete"]) for p in named(got, "q_di_kill_mobs")],
          [([0], 0)])
    gun, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 50)
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held) > 6 and held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")
    got = goto(c, BURIALS)
    fight, killed = hunt(c, got, RAT, gun, 3)
    fight += c.frames(0.5)
    check("three rats shot in the ancestors' burial ground", killed, 3)
    check("  ..and the journal counted each", [p["kill_num"] for p in named(
        fight, "q_di_kill_mobs")], [[1], [2], [3]])
    check("  ..complete on the third", named(fight, "q_di_kill_mobs")[-1:] and
          named(fight, "q_di_kill_mobs")[-1]["complete"], 1)
    here = inhabitants(goto(c, WEST))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, SHOOT, q_shoot)
    check("handed in to Ибрахим: the Наган, then the fifty rounds beside it, the"
          " experience, the ack", (no_level(upto_ack(got)), acks(got)),
          (["ss_obj_status", "ss_di_firearm", "ss_obj_status", "ss_di_heap", "rp_info",
            "cmdAck"], [0]))
    check("  ..the window's one reward and the one beside it, both «Вы получили»",
          new_things(got)[:2], [NAGAN, ROUNDS])
    have = owned(CID)
    check("  ..in the bag: the Наган and fifty rounds; fifty to Стрельба",
          (have.get(NAGAN), have.get(ROUNDS), skill_seen(c, SHOOTING) - shooting0),
          (1, 50, 50))

    # --- the provisions -------------------------------------------------------------------
    got, q = take(c, here, SUPPLY)
    check("«Снабжение» taken from Ибрахим", acks(got), [0])
    here = inhabitants(goto(c, MARKET))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, SUPPLY, q)
    check("  ..handed in to Амина: the poncho, fifty to Стрельба",
          (acks(got), owned(CID).get(PONCHO), skill_seen(c, SHOOTING) - shooting0),
          ([0], 1, 50))
    got, q = take(c, here, PROVISIONS)
    check("«Провиант» taken from Амина: the box of meat into the bag, found",
          (order(got), first(got, "q_di_del_obj").get("obj"), owned(CID).get(MEAT)),
          (["ss_obj_status", "ss_di_heap", "cmdAck", "q_di_del_obj"], 1, 1))
    c.send("q_ca;q_id=%d;" % q)
    got = c.frames(0.8)
    check("  ..dropped: the box goes back to her, before the ack",
          (upto_ack(got), acks(got), owned(CID).get(MEAT)),
          (["ss_obj_status", "cmdAck"], [0], None))
    got, q = take(c, here, PROVISIONS)
    check("  ..and taken again, a new box", (acks(got), owned(CID).get(MEAT)), ([0], 1))
    here = inhabitants(goto(c, WEST))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, PROVISIONS, q)
    check("handed in to Ибрахим: the box out, the armour in, the experience",
          (no_level(upto_ack(got)), acks(got)),
          (["ss_obj_status", "ss_obj_status", "ss_di_wear", "rp_info", "cmdAck"], [0]))
    check("  ..no box, the armour, fifty to Стрельба",
          (owned(CID).get(MEAT), owned(CID).get(ARMOR), skill_seen(c, SHOOTING) - shooting0),
          (None, 1, 50))

    # --- the dog skins ----------------------------------------------------------------------
    got, q = take(c, here, DOGS)
    check("«Мертвые беззащитны» taken from Ибрахим: nought of three skins",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([0], 0)])
    _, got = give(c, SKIN, 3)
    got += c.frames(0.4)
    check("  ..three skins in the bag: the journal says three, complete",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")],
          [([3], 1)])
    here = inhabitants(goto(c, MARKET))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, DOGS, q)
    check("handed in to Амина: the skins out, fifty rounds in, the experience",
          (no_level(upto_ack(got)), acks(got)),
          (["ss_obj_status", "ss_obj_status", "ss_di_heap", "rp_info", "cmdAck"], [0]))
    check("  ..no skins, a hundred rounds now, seventy to Стрельба",
          (owned(CID).get(SKIN), owned(CID).get(ROUNDS), skill_seen(c, SHOOTING) - shooting0),
          (None, 100, 70))

    # --- the silk ----------------------------------------------------------------------------
    got, q = take(c, here, SILK_Q)
    check("«Шелковый путь» taken from Амина", acks(got), [0])
    c.send("ss_create;s_type=1;target=%d;" % here[LOXLEY][0])
    check("Локсли's stall opens", acks(c.frames()), [0])
    c.send("ss_upd;param=1;obj=x%x;s_status=1;" % items.stock_for(LOXLEY).index(SILK))
    got = c.frames(0.8)
    check("the silk bought from the bottom of his list, for five afro",
          (upto_ack(got), new_things(got), purse(got)),
          (["cmdAck"], [SILK], AFRO0 + 100 - 5))
    check("  ..and the journal counts it, complete",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([1], 1)])
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.3)
    here = inhabitants(goto(c, WEST))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, SILK_Q, q)
    check("handed in to Джеррах: the silk out, the experience",
          (no_level(upto_ack(got)), acks(got), owned(CID).get(SILK),
           skill_seen(c, SHOOTING) - shooting0),
          (["ss_obj_status", "rp_info", "cmdAck"], [0], None, 70))

    # --- the squad --------------------------------------------------------------------------
    got, q = take(c, here, TRUST)
    check("«Доверие» taken from Джеррах, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    here = inhabitants(goto(c, SQUAD))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, TRUST, q)
    check("  ..handed in to Сейфул at the squad's coordinates",
          (acks(got), skill_seen(c, SHOOTING) - shooting0), ([0], 70))
    check("the report is Сейфул's to give now", status(c, REPORT), 1)
    got, q = take(c, here, REPORT)
    here = inhabitants(goto(c, WEST))
    shooting0 = skill_seen(c, SHOOTING)
    got = hand_in(c, here, REPORT, q)
    check("«Доклад» handed in to Джеррах: the twenty experience its start promises",
          (acks(got), skill_seen(c, SHOOTING) - shooting0), ([0], 20))

    # --- the ear ----------------------------------------------------------------------------
    check("«Слава или смерть» offered now", status(c, GLORY), 1)
    got, q = take(c, here, GLORY)
    got = hand_in(c, here, GLORY, q)
    check("  ..taken; with no ear it is not handed in", acks(got), [3])
    _, got = give(c, EAR)
    got += c.frames(0.4)
    check("an ear in the bag: the journal says found, complete",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([1], 1)])
    got = hand_in(c, here, GLORY, q)
    check("handed in to Джеррах: the ear out, two hundred afro, the ack",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(EAR)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], AFRO0 + 100 - 5 + 200, None))

    # --- the west is not his: the branches exclude each other ---------------------------
    check("the north walked: nothing of the west is offered to him",
          [status(c, t) for t in WEST_Q], [0, 0, 0, 0])
    c.send("q_st;mob=%d;q_idx=%d;" % (here[JERRAH][0], quests.given_by(JERRAH).index(WELCOME_W)))
    got = c.frames(0.6)
    check("  ..and Джеррах's welcome asked for anyway is refused, one ack, no journal",
          (order(got), acks(got)), (["cmdAck"], [4]))

    # --- all of it, one-offs: nothing offered twice, the day untouched ---------------------
    NORTH_DONE = sorted(set(VALLEY) - set(WEST_Q))
    check("every one of the thirteen of his is in the history, once", done(CID), NORTH_DONE)
    check("  ..one pair of shorts, one of slippers, one panama",
          [owned(CID).get(t) for t in (SHORTS, SLIPPERS, PANAMA)], [1, 1, 1])
    check("  ..and none of the seventeen is offered again",
          [t for t in VALLEY if status(c, t)], [])
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    got = arrive(c)
    check("the day's repeatable hand-ins untouched by all thirteen: ten left",
          [p["daily_available"] for p in named(got, "q_sys")], [10])
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)

    # --- the west start, a second newcomer's --------------------------------------------------
    w = Client(connect())
    w.send("hello;minor=2;major=0;")
    w.send("login;hash=@%s@;" % CRED_W)
    w.frames()
    w.send("newPers;res=1;sex=0;name=@Westerner@;")
    w.frames()
    w.send("actPlayer;")
    w.until(lambda f: f[0] == "lcall")
    arrive(w)
    CID_W = char_id("Westerner")
    here = inhabitants(goto(w, WEST))
    check("a second newcomer in the Западный поселок: Джеррах's welcome and the box are"
          " offered, and still Думисани's and the cow's -- nothing is taken yet",
          [status(w, t) for t in (WELCOME_W, BOX_Q, FRIENDS_W, WELCOME_N, COW_Q)],
          [1, 1, 0, 1, 1])
    got, q = take(w, here, WELCOME_W)
    check("the west's «Добро пожаловать» taken from Джеррах: the ack, then the journal,"
          " complete", ([n for n, _p in got], first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    check("  ..and nothing of the north is offered any more, the cow included",
          [status(w, t) for t in NORTH_Q], [0, 0, 0, 0])
    got = hand_in(w, here, WELCOME_W, q)
    check("  ..handed in to Ибрахим: the shorts -- one pair --, twenty to Медицина",
          (upto_ack(got), acks(got), owned(CID_W).get(SHORTS), experience(CID_W, MEDICINE)),
          (["ss_obj_status", "ss_di_wear", "rp_info", "cmdAck"], [0], 1, 20))
    got, q_tools = take(w, here, FRIENDS_W)
    check("Ибрахим's «Друзья»: the tools not in the bag yet",
          [(p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")], [([0], 0)])
    here = inhabitants(goto(w, BURIALS))
    check("the tools box stands in 184", len(here.get(BOX, [])), 1)
    got, q = take(w, here, BOX_Q)
    got = hand_in(w, here, BOX_Q, q) + w.frames(0.5)
    check("«Забрать инструменты» taken and handed in at the box: the tools, fifty afro",
          (upto_ack(got), acks(got), purse(got)),
          (["ss_obj_status", "ss_di_heap", "userInfo_Player", "cmdAck"], [0], AFRO0 + 50))
    check("  ..and the journal: the tools found, «Друзья» complete",
          [(p["q_id"], p["obj_num"], p["complete"]) for p in named(got, "q_di_bring_l_obj")],
          [(q_tools, [1], 1)])
    check("  ..the box's quest a one-off", status(w, BOX_Q), 0)
    here = inhabitants(goto(w, WEST))
    got = hand_in(w, here, FRIENDS_W, q_tools)
    check("«Друзья» handed in to Ибрахим: the tools out, the slippers in, forty to Медицина",
          (upto_ack(got)[:2], acks(got), owned(CID_W).get(TOOLS), owned(CID_W).get(SLIPPERS),
           experience(CID_W, MEDICINE)),
          (["ss_obj_status", "ss_obj_status"], [0], None, 1, 40))
    got, q = take(w, here, FINANCE_W)
    check("Ибрахим's «Финансовая система»: a parcel", (acks(got), owned(CID_W).get(PARCEL)),
          ([0], 1))
    here = inhabitants(goto(w, MARKET))
    got = hand_in(w, here, FINANCE_W, q)
    check("  ..handed in to Гарард: the parcel out, the panama, a hundred afro, seventy to"
          " Медицина", (acks(got), owned(CID_W).get(PARCEL), owned(CID_W).get(PANAMA),
                        purse(got), experience(CID_W, MEDICINE)),
          ([0], None, 1, AFRO0 + 50 + 100, 70))
    check("the west walked: its four in the history, the north's four never offered, and"
          " Гарард's lesson is his as it is everybody's",
          (done(CID_W), [status(w, t) for t in NORTH_Q + WEST_Q], status(w, WISDOM)),
          (WEST_Q, [0] * 8, 1))
    w.send("logout;")
    w.frames(0.5)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-60:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("valley quests OK")
