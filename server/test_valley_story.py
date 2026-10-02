"""The Nubian valley's story, the second batch of its quests (the owner's
«давай готовь квесты все», 2026-09-26), walked on a socket on the real
data/quests.json: Наби ал-Асад's line from the welcome to the leader's
notes, the ride out to Вади-Хальфа and back, eighteen quests, types 28-45.

  Наби    «Нет больше покоя» Демир -> Наби; «Предки без защиты» (three
          dogs in 184, 20 afro); «Главное - это здоровье» (to Гарард, three
          rags); «Похищенный груз» (to Мастер Норман at the truck)
  Норман  «Похищенный груз (часть 2)» (four weapon parts: Беретта 92 (G),
          150 afro); «(часть 3)» (the medicaments: Рубашка, 150 afro);
          «Дальнейшая борьба» (to Сейфул)
  Сейфул  «Пути информации» (the courier shot in 28, his letter out of his
          bag: 200 afro); «Разведчик» (to Доктор Корбен in 33)
  Корбен  «Хвост» (one Стрелок, one Штурмовик: 100 afro); «Одолжить
          аптечку» (medicaments: 200 afro)
  Аюб     «Важные персоны» (Комиссар Рекс shot in 30: 300 afro); «Последний
          удар» (Ян Дуглас shot in his camp at six, his notes out of his bag:
          Кусковая броня (G), 500 afro); «Новые вопросы» (the notes carried
          to Наби)
  out     «Назад, в большой мир» (Наби: the tribe's gift, Тесак); «В
          Хальфу!» (Демир's ride to Причал, 41) and «Назад, в долину» (the
          ride back, not past the second level of any skill); «Добро
          пожаловать в Хальфу» (Демир at Причал -> Саид, 36)

Each group is held to its take (one ack, then the journal; the notes into
the bag first, and out of it again when the quest is dropped -- never into a
letter or on the ground, where the drop could not take them back), its progress (the kills, the bag, the journal told), its
hand-in (what the quest asked for out of the bag, the reward in: the thing,
the experience, the money, all before the ack) and the chain it opens. The
two rides are ways, as Рудо's is: handed back, the ack and then the lcall,
the hand-in written into the history like any quest's but none of the day's
(server.py cmd_q_co); the ride back is refused past its cap, carried or not. None of the others is repeatable or counts against the day.

In process: the rows, their texts laid over from the original
(data/orig_misc.json, data/build_orig_misc.py VERIFIED, the newest edition,
the three «Похищенный груз» told apart by their own names), every string id
in the launcher's table, every giver and taker standing where the quest
sends the player as an inhabitant the client opens quests for, every
creature a quest asks to kill or rob standing where its mark is and
carrying what is asked for it, the ways in data/passages.json.

    LAVA_RES=.../lava/res python3 server/test_valley_story.py
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK"):
    os.environ.pop(_knob, None)

# «В Хальфу!» (43) is on in the real table again since 2026-10-03 (the owner:
# «открой хальфу»): Демир of the caravan (5193) gives and takes it. Before
# that it was off from 2026-09-26 («пока отключаем квест в Хальфу»), on for a
# few hours on 2026-09-28 once Вади-Хальфа was restored, and off again the
# same evening («закрой хальфу обратно»). That it is on is checked first, and
# the walk below plays on the shipped table itself -- with its questgen
# companions, which a table LAVA_QUESTS names would not have (popped above).
_REAL = os.path.join(os.path.dirname(HERE), "data", "quests.json")
with open(_REAL, encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
HALFA_ON = [(r["give"], r["take"]) for r in _TABLE["quests"] if r["type"] == 43]

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
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


check("«В Хальфу!» is on in the real table: Демир of the caravan gives and takes it",
      HALFA_ON, [([5193], [5193])])
check("  ..and the suite plays on that table, its companions with it (no LAVA_QUESTS)",
      (os.path.abspath(quests.quests_path()) == os.path.abspath(_REAL),
       bool(quests.companion_paths(quests.quests_path()))), (True, True))


# The quests, by type.
(QUIET, ANCESTORS, HEALTH, CARGO1, CARGO2, CARGO3, STRUGGLE, COURIER_Q, SCOUT, TAIL,
 MEDKIT, PERSONS, BLOW, QUESTIONS, BIG_WORLD, TO_HALFA, BACK, WELCOME_H) = range(28, 46)
STORY = list(range(28, 46))
WAYS = (TO_HALFA, BACK)
ONE_OFF = [t for t in STORY if t not in WAYS]
# Who gives and takes them.
DEMIR_V, NABI, GARARD, NORMAN, SEIFUL = 5193, 5202, 5187, 5196, 35
CORBEN, AYUB, DEMIR_H, SAID = 5233, 5232, 30, 44
# The creatures.
DOG, RAIDER1, RAIDER2, COURIER, SHOOTER, STORMER = 82, 14, 15, 17, 250, 251
COMMISSAR, LEADER = 1405, 2103
# The things.
BARREL, TRIGGER, BOLT, GRIP, MEDS, LETTER, NOTES = 228, 229, 230, 231, 232, 233, 234
RAG, BERETTA, SHIRT, ARMOUR, CLEAVER, INGOT = 6055, 25587, 10180, 10201, 6240, 4796
# The places.
VILLAGE, BURIALS, MARKET, TRUCK, RAIDERS, SQUAD = 186, 184, 185, 26, 27, 29
GONETS, SCOUT_LOC, REX, CAMP, PIER, QUARTER = 28, 33, 30, 34, 41, 36
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
MEDICINE, SHOOTING = progression.MEDICINE, progression.SHOOTING
TASK_LABEL = re.compile(r"№\s*0000")      # the 2012 edition's «№0000162» labels

GIVE_TAKE = {QUIET: (DEMIR_V, NABI), ANCESTORS: (NABI, NABI), HEALTH: (NABI, GARARD),
             CARGO1: (NABI, NORMAN), CARGO2: (NORMAN, NORMAN), CARGO3: (NORMAN, NORMAN),
             STRUGGLE: (NORMAN, SEIFUL), COURIER_Q: (SEIFUL, SEIFUL), SCOUT: (SEIFUL, CORBEN),
             TAIL: (CORBEN, CORBEN), MEDKIT: (CORBEN, CORBEN), PERSONS: (AYUB, AYUB),
             BLOW: (AYUB, AYUB), QUESTIONS: (AYUB, NABI), BIG_WORLD: (NABI, NABI),
             TO_HALFA: (DEMIR_V, DEMIR_V), BACK: (DEMIR_H, DEMIR_H),
             WELCOME_H: (DEMIR_H, SAID)}
CHAIN = {QUIET: [], ANCESTORS: [QUIET], HEALTH: [ANCESTORS], CARGO1: [HEALTH],
         CARGO2: [CARGO1], CARGO3: [CARGO2], STRUGGLE: [CARGO3], COURIER_Q: [STRUGGLE],
         SCOUT: [COURIER_Q], TAIL: [SCOUT], MEDKIT: [SCOUT], PERSONS: [MEDKIT],
         BLOW: [PERSONS], QUESTIONS: [BLOW], BIG_WORLD: [QUESTIONS], TO_HALFA: [],
         BACK: [], WELCOME_H: [BIG_WORLD]}
WHERE = {DEMIR_V: VILLAGE, NABI: VILLAGE, GARARD: MARKET, NORMAN: TRUCK, SEIFUL: SQUAD,
         CORBEN: SCOUT_LOC, AYUB: SCOUT_LOC, DEMIR_H: PIER, SAID: QUARTER}
# What each quest pays: (thing, pieces) or None, afro, experience.
PAYS = {QUIET: (None, 0, {"medicine": 20}), ANCESTORS: (None, 20, {}),
        HEALTH: ((RAG, 3), 0, {"medicine": 20}), CARGO1: (None, 0, {"medicine": 20}),
        CARGO2: ((BERETTA, 1), 150, {}), CARGO3: ((SHIRT, 1), 150, {}),
        STRUGGLE: (None, 0, {"medicine": 20}), COURIER_Q: (None, 200, {}),
        SCOUT: (None, 0, {"medicine": 20}), TAIL: (None, 100, {}), MEDKIT: (None, 200, {}),
        PERSONS: (None, 300, {}), BLOW: ((ARMOUR, 1), 500, {}),
        QUESTIONS: (None, 0, {"medicine": 20}), BIG_WORLD: ((CLEAVER, 1), 0, {"medicine": 20}),
        TO_HALFA: (None, 0, {}), BACK: (None, 0, {}), WELCOME_H: (None, 0, {"medicine": 20})}


def pack(gx, gy):
    return (gx << 13) | gy


# --- in process: the table ------------------------------------------------------------
MT = world.mob_types()
try:
    rows = [quests.get(t) for t in STORY]
    check("the eighteen quests of the valley's story are in the table",
          [q is not None for q in rows], [True] * 18)
    check("  ..one-offs, all but the two rides, which are ways and nothing else -- the"
          " client's own «после выполнения задания Вас переместят» (rew_loc)",
          ([t for t in STORY if quests.get(t).repeatable],
           [t for t in STORY if travel.is_quest_way(t)],
           [t for t in STORY if quests.get(t).rew_loc]), (list(WAYS),) * 3)
    check("  ..given and taken by the NPCs the texts and the wiki name",
          {q.type: (q.give, q.take) for q in rows},
          {t: ([g], [k]) for t, (g, k) in GIVE_TAKE.items()})
    check("  ..in the chain the original draws", {q.type: q.need_all + q.need_any for q in rows},
          CHAIN)
    check("  ..paying what the original pays, or what each row's why designs",
          {q.type: ((q.rew_obj[0], q.num_rew_obj[0]) if q.rew_obj else None, q.rew_afro,
                    {key: xp for key, idx in quests.SKILL_KEYS.items()
                     for skill, xp in q.rew_xp if skill == idx})
           for q in rows}, PAYS)
    check("  ..no gold, nothing beside the reward, no level asked",
          [t for t in STORY if quests.get(t).rew_gold or quests.get(t).rew_also
           or quests.get(t).level], [])
    check("  ..the ride back is capped at the second level; nothing else is",
          {t: quests.get(t).max_level for t in STORY if quests.get(t).max_level is not None},
          {BACK: 2})
    check("  ..appended: Демир's welcome is his first (q_idx 0), the ride his second",
          (quests.given_by(DEMIR_V), quests.given_by(DEMIR_H)),
          ([QUIET, TO_HALFA], [BACK, WELCOME_H]))
    orig = orig_texts.quests()
    with open(os.path.join(os.path.dirname(HERE), "data", "orig_misc.json"),
              encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts are the original's (data/orig_misc.json)",
          [t for t in STORY if t not in pinned], [])
    check("  ..laid over the table's",
          [t for t in STORY for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and quests.get(t).texts[k] != quests.served(quests.get(t), k, orig[t][key])], [])
    check("  ..the newest edition: no line carries the 2012 number label",
          [t for t in STORY if any(TASK_LABEL.search(x) for x in quests.get(t).texts)], [])
    check("  ..the three parts of «Похищенный груз» by their own names",
          [quests.get(t).name for t in (CARGO1, CARGO2, CARGO3)],
          ["Похищенный груз", "Похищенный груз (часть 2)", "Похищенный груз (часть 3)"])
    check("  ..«Разведчик» ends in the newest edition's words, not the 2012 copy's «кто—то»",
          (pinned.get(SCOUT, [None] * 4)[3], "—" in quests.get(SCOUT).texts[quests.FINISH]),
          (59861, False))
    check("  ..and the ride back, which the file ends with nothing, with «Ну, поехали!»"
          " -- the original's words for the same ride in (59830)",
          (pinned.get(BACK, [None] * 4)[3], quests.get(BACK).texts[quests.FINISH]),
          (59830, "Ну, поехали!"))
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has, and what they hand over is worth"
          " nothing away from them", quests.check_items(), None)

    # The givers and takers, where the client can open their quests: every
    # class but a mob's has the tab (NPCService.openService).
    stand = {}
    for lid in sorted(set(WHERE.values()) | {BURIALS, RAIDERS, GONETS, REX, CAMP}):
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            stand.setdefault(n.type_id, set()).add((lid, n.root))
    check("each giver and taker stands where the quests send the player, not a mob",
          {npc: sorted(lid for lid, root in stand.get(npc, ()) if root != world.MOB)
           for npc in WHERE}, {npc: [lid] for npc, lid in WHERE.items()})
    at = {lid: pack(*world.cell_of(lid)) for lid in
          (VILLAGE, BURIALS, MARKET, TRUCK, RAIDERS, SQUAD, GONETS, SCOUT_LOC, REX, CAMP,
           QUARTER)}
    by_mark = {v: k for k, v in at.items()}
    check("each hand-in's mark is the taker's place",
          {t: by_mark.get(quests.get(t).finish_loc) for t in ONE_OFF},
          {t: WHERE[GIVE_TAKE[t][1]] for t in ONE_OFF})
    kills = {t: (quests.get(t).mobs_kill, by_mark.get(quests.get(t).loc))
             for t in STORY if quests.get(t).kind == quests.KILL_MOBS}
    check("the kills: three dogs, a Стрелок and a Штурмовик, the commissar",
          {t: m for t, (m, _l) in kills.items()},
          {ANCESTORS: [DOG], TAIL: [SHOOTER, STORMER], PERSONS: [COMMISSAR]})
    check("  ..each creature standing, a mob, where the quest's mark is",
          {t: [m for m in ms if (lid, world.MOB) in stand.get(m, ())]
           for t, (ms, lid) in kills.items()}, {t: ms for t, (ms, _l) in kills.items()})
    brings = {t: [(o, n, ms) for o, n, ms in quests.get(t).objs] for t in STORY
              if quests.get(t).kind == quests.BRING_L_OBJ}
    check("the things to bring, and who carries them",
          brings, {CARGO2: [(o, 1, [RAIDER1, RAIDER2]) for o in (BARREL, TRIGGER, BOLT, GRIP)],
                   CARGO3: [(MEDS, 1, [RAIDER1, RAIDER2])],
                   COURIER_Q: [(LETTER, 1, [COURIER])], MEDKIT: [(MEDS, 1, [STORMER, SHOOTER])],
                   BLOW: [(NOTES, 1, [LEADER])]})
    check("  ..each carrier standing, a mob, where the quest's mark is, and carrying the"
          " thing for a quest that wants it (a «Квестовый» row of data/loot_manual.json)",
          {t: [(o, m) for o, _n, ms in slots for m in ms
               if (by_mark.get(quests.get(t).loc), world.MOB) in stand.get(m, ())
               and o in dict(mobs.quest_table(m))] for t, slots in brings.items()},
          {t: [(o, m) for o, _n, ms in slots for m in ms] for t, slots in brings.items()})
    check("the notes are handed over by Аюб at the take, and kept at a death",
          (quests.get(QUESTIONS).start_obj, quests.get(QUESTIONS).obj,
           combat.drops_on_death(NOTES)), ([(NOTES, 1)], NOTES, False))
    check("  ..the very notes «Последний удар» asks for, so they go nowhere the drop of"
          " «Новые вопросы» cannot take them back from: not into a letter, not on the"
          " ground", ([o for o, _n in quests.get(BLOW).wants()], mail.postable(NOTES),
                      quests.not_on_ground(NOTES)), ([NOTES], False, True))
    check("the rewards are things of the game: the Беретта is its family's G",
          [items.params_of(t) is not None for t in (RAG, BERETTA, SHIRT, ARMOUR, CLEAVER)]
          + [items.params_of(BERETTA).get("g_cost", 0) > 0], [True] * 6)

    # The rides, in data/passages.json.
    for key, qtype, target, npc in ((VILLAGE, TO_HALFA, PIER, DEMIR_V),
                                    (PIER, BACK, VILLAGE, DEMIR_H)):
        loc = world.location(key)
        rec = travel.quest_way(loc, qtype)
        check("%d: quest %d is a way to %d" % (key, qtype, target),
              rec and rec.get("target_loc_id"), target)
        if not rec:
            continue
        way = {y * loc.width + x for x, y in rec["cells"]}
        zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                       "zones", 4)}
        home = [c for c, t in loc.spawns if t == npc]
        check("  ..drawn beside Демир's car, on ground a walker stands on, where no"
              " window opens and nobody arrives",
              (sorted(way & loc.obstacles), sorted(way & zones), sorted(way & set(loc.entries)),
               bool(home) and min(mobs.hex_distance(c, home[0], loc.width) for c in way) <= 2),
              ([], [], [], True))
        check("  ..with its reason", rec.get("why", "").startswith(("DESIGNED", "RECOVERED")),
              True)
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "valley_story.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("wanderer", "secret")
# Somebody to post Аюб's notes to: a character that never logs in.
_store.create_character(_store.register("friend", "secret")[0], "Friend", 0, 1)
_store.close()
CRED = accounts.credential("wanderer", "secret")

# Five seconds past six on the Moscow clock: the leader is in his camp for
# the hour the test takes a few minutes of.
CLOCK = datetime(2026, 9, 24, 18, 0, 5)
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="6268", LAVA_GY="1819", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="30", LAVA_SEED="5", LAVA_BOSS_CLOCK=CLOCK.isoformat())
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


def no_level(seq):
    """A frame order with a level-up's usrUp left out: whether a skill
    crosses a level at a hand-in depends on what the kills paid for it."""
    return [n for n in seq if n != "usrUp"]


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


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def ints(v):
    """A list field as the decoder leaves it -- a list, one value, or none."""
    if v in (None, "", []):
        return []
    return [int(x) for x in (v if isinstance(v, list) else [v])]


def quest_lists(c, here, npc_type):
    """(give_quests, take_quests) of the first inhabitant of a type here, as
    its getInfo answer lists them: the client indexes q_st by the first."""
    c.send("getInfo;lvl=0;id=%d;type=0;" % here.get(npc_type, [0])[0])
    got = [p for n, p in c.until(lambda f: f[0].startswith("userInfo_"), 2)
           if n.startswith("userInfo_") and p.get("name") == npc_type]
    return (ints(got[0].get("give_quests")), ints(got[0].get("take_quests"))) if got else None


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


def hand_in(c, here, qtype, q_id, obj_idx=0, wait=0.9):
    npc = here.get(GIVE_TAKE[qtype][1], [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = 'Wanderer'").fetchone()
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


def unpacked(mask, values):
    """index -> value of a packed group (progression.packed)."""
    out, it = {}, iter(values)
    for i in range(32):
        if mask & (1 << i):
            out[i] = next(it)
    return out


def skill_seen(c, skill):
    """All the experience a skill has had, as the client was last told of it
    (every rp_info seen, the kills' and the quests' alike)."""
    level = xp = 0
    for n, p in c.seen:
        if n != "rp_info":
            continue
        level = unpacked(p["a_skills_mask"], p["a_skills"]).get(skill, level)
        xp = unpacked(p["xp_skills_mask"], p["xp_skills"]).get(skill, xp)
    return sum(progression.skill_xp_max(lvl) for lvl in range(level)) + xp


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


def gone_things(frames):
    """How many things left the bag (ss_obj_status 0)."""
    return len([p for p in named(frames, "ss_obj_status") if p.get("status") == 0])


def purse(frames):
    got = named(frames, "userInfo_Player")
    return got[-1].get("afro") if got else None


def counts(frames, kind):
    key = "kill_num" if kind == quests.KILL_MOBS else "obj_num"
    return [(p[key], p["complete"]) for p in named(frames, "q_di_" + kind)]


def positions(frames):
    """entity id -> cell of every inhabitant the frames bring in (lch
    newUser), moved on by the userMove frames among them."""
    where = {}
    for n, p in frames:
        if n == "lch" and "newUser" in p:
            where[p["newUser"]] = p["pos"]
        elif n == "userMove" and p.get("id") in where and p.get("path"):
            where[p["id"]] = p["path"][-1]
    return where


def hunt(c, got, loc_id, targets, pos):
    """Shoot one creature of each type in targets, in order, each from a cell
    with a clear line to it and out of every hostile's reach (the admin gun
    fells anything with one shot). (the fight's frames, the types killed,
    where the player stands, type -> the cell it fell on, the cells within
    reach of the hostiles still standing)."""
    loc = world.location(loc_id)
    cells = range(loc.width * loc.height)
    types = {}
    for t, es in inhabitants(got).items():
        for e in es:
            types[e] = t
    hostile = {e for e, t in types.items() if MT.get(t, (None,))[0] == world.MOB}
    reach = max([mobs.stats(types[e]).aggro for e in hostile] or [0]) + 0.5
    out, killed, fell, dead = [], [], {}, set()
    for want in targets:
        where = positions(got + out)
        for eid in [e for e, t in types.items() if t == want and e not in dead]:
            home = where.get(eid)
            if home is None:
                continue
            others = [where[e] for e in hostile if e not in dead and e != eid and e in where]
            wary = {cell for cell in cells
                    if any(mobs.hex_distance(cell, o, loc.width) <= reach
                           for o in others + [home])}
            spots = sorted((mobs.hex_distance(cell, home, loc.width), cell) for cell in cells
                           if cell not in loc.obstacles and cell not in wary
                           and travel.side_at(loc, cell) is None
                           and cell not in where.values()
                           and mobs.hex_distance(cell, home, loc.width) <= 40
                           and mobs.line_of_fire(loc, cell, home) is None)
            if not spots:
                continue
            goal = spots[0][1]
            path = mobs.find_path(loc, pos, lambda cell: cell == goal, wary, limit=20000)
            c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
            out += c.frames(0.15 * len(path or [0]) + 0.8)
            pos = goal
            for _ in range(30):
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (GUN, entity(eid)))
                got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                               or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
                out += got_
                if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                    killed.append(want)
                    dead.add(eid)
                    fell[want] = positions(got + out).get(eid, home)
                    break
                time.sleep(0.3)
            if want in killed:
                break
    where = positions(got + out)
    standing = [where[e] for e in hostile if e not in dead and e in where]
    wary = {cell for cell in cells
            if any(mobs.hex_distance(cell, o, loc.width) <= reach for o in standing)}
    return out, killed, pos, fell, wary


def loot(c, fight, loc_id, pos, near, wary=frozenset()):
    """Walk to the corpse's bag that lies nearest `near`, keeping out of
    the wary cells, open it, take all of it and close it: (the types it
    held, the frames of the taking)."""
    loc = world.location(loc_id)
    got = list(fight)
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    bags = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    if not bags:
        return None, []
    bag = min(bags, key=lambda cell: mobs.hex_distance(cell, near, loc.width))
    path = mobs.find_path(loc, pos, lambda cell: cell == bag or progression.within_reach(
        cell, bag, loc.width, loc.height), set(wary), limit=20000)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
    c.frames(0.2 * len(path or [pos]) + 1.0)
    c.send("ss_create;s_type=0;target=%d;" % bag)
    if acks(c.frames()) != [0]:
        return None, []
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
    held = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    took = c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return held, took


def relogin():
    c_ = Client(connect())
    c_.send("hello;minor=2;major=0;")
    c_.send("login;hash=@%s@;" % CRED)
    c_.frames()
    c_.send("selPers;num=0;")
    call = first(c_.until(lambda f: f[0] == "lcall"), "lcall")
    return c_, call, arrive(c_)


def logout(c_):
    c_.send("logout;")
    c_.frames(0.5)
    c_.s.close()
    time.sleep(0.3)


GUN = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Wanderer@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    CID = char_id()
    AFRO0 = 1000
    check("a newcomer: Демир's welcome and his ride are offered, the ride back too; nothing"
          " of Наби's line after the welcome, nor Саид's",
          [status(c, t) for t in STORY],
          [1 if t in (QUIET, TO_HALFA, BACK) else 0 for t in STORY])

    # --- the ride out and back ---------------------------------------------------------
    here = inhabitants(goto(c, VILLAGE))
    check("the caravan's village: Демир and Наби", (len(here.get(DEMIR_V, [])),
                                                   len(here.get(NABI, []))), (1, 1))
    check("  ..their frames list what they give and take, in the order q_idx counts",
          [quest_lists(c, here, npc) for npc in (DEMIR_V, NABI)],
          [([QUIET, TO_HALFA], [TO_HALFA]),
           ([ANCESTORS, HEALTH, CARGO1, BIG_WORLD], [QUIET, ANCESTORS, QUESTIONS, BIG_WORLD])])
    got, q = take(c, here, TO_HALFA)
    check("«В Хальфу!» taken from Демир: the ack, then the journal, complete",
          (order(got), first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    got = hand_in(c, here, TO_HALFA, q)
    call = first(got + c.until(lambda f: f[0] == "lcall", 3), "lcall")
    check("  ..handed back to him: the ack, and the ride to Причал", (upto_ack(got), acks(got),
                                                                    call.get("id")),
          (["cmdAck"], [0], PIER))
    got = arrive(c)
    here = inhabitants(got)
    check("  ..arrived beside the way back, with Демир of Причал there",
          (first(got, "lenter").get("pos"), len(here.get(DEMIR_H, []))),
          (travel.door_arrival(world.location(PIER), VILLAGE), 1))
    c.send("q_list;")
    check("  ..the ride written into the history, the journal empty",
          (done(CID), named(c.frames(), "q_list")), ([TO_HALFA], [{"q_id": [], "q_types": []}]))
    check("  ..his frame lists the ride back and Саид's errand",
          quest_lists(c, here, DEMIR_H), ([BACK, WELCOME_H], [BACK]))
    check("at Причал the ride back is offered; Саид's errand is not, yet",
          [status(c, t) for t in (BACK, WELCOME_H)], [1, 0])
    got, q = take(c, here, BACK)
    got = hand_in(c, here, BACK, q)
    call = first(got + c.until(lambda f: f[0] == "lcall", 3), "lcall")
    check("«Назад, в долину» taken and handed back: the ack, the ride to the caravan",
          (upto_ack(got), acks(got), call.get("id")), (["cmdAck"], [0], VILLAGE))
    got = arrive(c)
    here = inhabitants(got)
    check("  ..arrived beside Демир's car", first(got, "lenter").get("pos"),
          travel.door_arrival(world.location(VILLAGE), PIER))
    got, q = take(c, here, TO_HALFA)
    check("the ride out is offered again at once", acks(got), [0])
    got = hand_in(c, here, TO_HALFA, q)
    if not named(got, "lcall"):
        c.until(lambda f: f[0] == "lcall", 3)
    here = inhabitants(arrive(c))
    got, q_back = take(c, here, BACK)
    check("at Причал again, the ride back taken while still a beginner", acks(got), [0])
    logout(c)
    st = store()
    st.save_stats(CID, [("skill", SHOOTING, 3, 0, progression.skill_xp_max(3))])
    st.save_character_state(CID, level=3)
    st.close()
    c, call, got = relogin()
    here = inhabitants(got)
    check("back at Причал with the third level of Стрельба",
          (call.get("id"), len(here.get(DEMIR_H, []))), (PIER, 1))
    check("  ..the ride back is no longer offered, the ride out still is",
          [status(c, t) for t in (BACK, TO_HALFA)], [0, 1])
    got = hand_in(c, here, BACK, q_back) + c.frames(0.8)
    check("  ..and the one carried is not handed in: refused, nobody moved",
          (order(got), acks(got)), (["cmdAck"], [4]))
    c.send("q_ca;q_id=%d;" % q_back)
    check("  ..the journal can still drop it", acks(c.frames(0.6)), [0])
    got, _q = take(c, here, BACK)
    check("  ..nor is it given any more", (order(got), acks(got)), (["cmdAck"], [4]))

    # --- the admin gun, loaded ---------------------------------------------------------
    GUN, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 99)
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held) > 6 and held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % GUN)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, GUN))
    c.until(lambda f: f[0] == "ss_di_firearm")

    # --- Наби: the welcome, the dogs, the healer ----------------------------------------
    here = inhabitants(goto(c, VILLAGE))
    check("Наби gives nothing before the welcome", status(c, ANCESTORS), 0)
    got, q = take(c, here, QUIET)
    check("«Нет больше покоя» taken from Демир, complete at once",
          (order(got), first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, QUIET, q)
    check("  ..handed in to Наби: the experience, the ack",
          (no_level(upto_ack(got)), acks(got), skill_seen(c, MEDICINE) - med0),
          (["rp_info", "cmdAck"], [0], 20))
    check("  ..«Предки без защиты» is offered now, the welcome no more",
          [status(c, t) for t in (ANCESTORS, QUIET)], [1, 0])
    got, q_dogs = take(c, here, ANCESTORS)
    check("«Предки без защиты» taken: nought of three", counts(got, quests.KILL_MOBS),
          [([0], 0)])
    got = hand_in(c, here, ANCESTORS, q_dogs)
    check("  ..and not handed in before the dogs", (order(got), acks(got)), (["cmdAck"], [3]))
    got = goto(c, BURIALS)
    fight, killed, pos = [], [], first(got, "lenter").get("pos")
    for _ in range(3):
        more, k, pos, _f, _w = hunt(c, got + fight, BURIALS, [DOG], pos)
        fight += more
        killed += k
    fight += c.frames(0.5)
    check("three dogs shot at the burial ground", killed, [DOG] * 3)
    check("  ..and the journal counted each, complete on the third",
          counts(fight, quests.KILL_MOBS), [([1], 0), ([2], 0), ([3], 1)])
    here = inhabitants(goto(c, VILLAGE))
    got = hand_in(c, here, ANCESTORS, q_dogs)
    check("  ..handed in to Наби: twenty afro, the ack",
          (upto_ack(got), acks(got), purse(got)), (["userInfo_Player", "cmdAck"], [0],
                                                   AFRO0 + 20))
    got, q = take(c, here, HEALTH)
    check("«Главное - это здоровье» taken from Наби, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    here = inhabitants(goto(c, MARKET))
    med0 = skill_seen(c, MEDICINE)
    got = hand_in(c, here, HEALTH, q)
    check("  ..handed in to Гарард on the market: three rags, the experience, the ack",
          (new_things(got), no_level(upto_ack(got))[-2:], acks(got),
           owned(CID).get(RAG), skill_seen(c, MEDICINE) - med0),
          ([RAG] * 3, ["rp_info", "cmdAck"], [0], 3, 20))

    # --- to Норман, and his parts ------------------------------------------------------
    here = inhabitants(goto(c, VILLAGE))
    got, q = take(c, here, CARGO1)
    check("«Похищенный груз» taken from Наби", acks(got), [0])
    here = inhabitants(goto(c, TRUCK))
    check("Норман gives nothing before Наби's word reaches him", status(c, CARGO2), 0)
    got = hand_in(c, here, CARGO1, q)
    check("  ..handed in to Мастер Норман at the truck: the experience",
          (no_level(upto_ack(got)), acks(got)), (["rp_info", "cmdAck"], [0]))
    check("part 2 is offered now", status(c, CARGO2), 1)
    got, q = take(c, here, CARGO2)
    check("«Похищенный груз (часть 2)» taken: none of the four parts",
          counts(got, quests.BRING_L_OBJ), [([0, 0, 0, 0], 0)])
    got = []
    for t in (BARREL, TRIGGER, BOLT, GRIP):
        got += give(c, t)[1]
    got += c.frames(0.4)
    check("  ..the four parts in the bag, the journal counting each, complete on the last",
          counts(got, quests.BRING_L_OBJ),
          [([1, 0, 0, 0], 0), ([1, 1, 0, 0], 0), ([1, 1, 1, 0], 0), ([1, 1, 1, 1], 1)])
    got = hand_in(c, here, CARGO2, q)
    check("  ..handed in: the four parts out, the Беретта in, a hundred and fifty afro,"
          " the ack", (upto_ack(got), acks(got), new_things(got), purse(got)),
          (["ss_obj_status"] * 5 + ["ss_di_firearm", "userInfo_Player", "cmdAck"], [0],
           [BERETTA], AFRO0 + 20 + 150))
    have = owned(CID)
    check("  ..in the bag the Беретта 92 (G), no part",
          (have.get(BERETTA), [t for t in (BARREL, TRIGGER, BOLT, GRIP) if have.get(t)]),
          (1, []))
    got, q = take(c, here, CARGO3)
    check("«Похищенный груз (часть 3)» taken", counts(got, quests.BRING_L_OBJ), [([0], 0)])
    _, got = give(c, MEDS)
    got += c.frames(0.4)
    check("  ..the medicaments in the bag: complete", counts(got, quests.BRING_L_OBJ),
          [([1], 1)])
    got = hand_in(c, here, CARGO3, q)
    check("  ..handed in: the medicaments out, the shirt in, a hundred and fifty afro",
          (upto_ack(got), acks(got), new_things(got), purse(got), owned(CID).get(MEDS)),
          (["ss_obj_status", "ss_obj_status", "ss_di_wear", "userInfo_Player", "cmdAck"],
           [0], [SHIRT], AFRO0 + 20 + 300, None))
    got, q = take(c, here, STRUGGLE)
    check("«Дальнейшая борьба» taken from Норман, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))

    # --- Сейфул and the courier ---------------------------------------------------------
    here = inhabitants(goto(c, SQUAD))
    check("Сейфул has nothing for the courier yet", status(c, COURIER_Q), 0)
    got = hand_in(c, here, STRUGGLE, q)
    check("  ..handed in to Сейфул: the experience", (no_level(upto_ack(got)), acks(got)),
          (["rp_info", "cmdAck"], [0]))
    got, q_courier = take(c, here, COURIER_Q)
    check("«Пути информации» taken from Сейфул: no letter yet",
          counts(got, quests.BRING_L_OBJ), [([0], 0)])
    got = goto(c, GONETS)
    fight, killed, pos, fell, wary = hunt(c, got, GONETS, [COURIER],
                                         first(got, "lenter").get("pos"))
    check("the courier shot", killed, [COURIER])
    held, took = loot(c, fight, GONETS, pos, fell.get(COURIER, pos), wary)
    check("  ..his bag holds the letter, once", (held or []).count(LETTER), 1)
    check("  ..taken: the journal counts it, complete", counts(took, quests.BRING_L_OBJ),
          [([1], 1)])
    here = inhabitants(goto(c, SQUAD))
    got = hand_in(c, here, COURIER_Q, q_courier)
    check("  ..handed in to Сейфул: the letter out, two hundred afro, the ack",
          (upto_ack(got), acks(got), purse(got), owned(CID).get(LETTER)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0], AFRO0 + 20 + 300 + 200, None))
    got, q = take(c, here, SCOUT)
    check("«Разведчик» taken from Сейфул", acks(got), [0])

    # --- Корбен and Аюб ----------------------------------------------------------------
    got = goto(c, SCOUT_LOC)
    here = inhabitants(got)
    check("Корбен gives nothing before the scout is found",
          [status(c, t) for t in (TAIL, MEDKIT)], [0, 0])
    got = hand_in(c, here, SCOUT, q)
    check("  ..handed in to Доктор Корбен: the experience", (no_level(upto_ack(got)), acks(got)),
          (["rp_info", "cmdAck"], [0]))
    check("both of Корбен's are offered now; Аюб's not yet",
          [status(c, t) for t in (TAIL, MEDKIT, PERSONS)], [1, 1, 0])
    got, q_tail = take(c, here, TAIL)
    check("«Хвост» taken: nought of one and one", counts(got, quests.KILL_MOBS),
          [([0, 0], 0)])
    got = goto(c, SCOUT_LOC)
    fight, killed, pos, _f, _w = hunt(c, got, SCOUT_LOC, [SHOOTER, STORMER],
                                      first(got, "lenter").get("pos"))
    fight += c.frames(0.5)
    check("a Стрелок and a Штурмовик of the pursuers shot", killed, [SHOOTER, STORMER])
    check("  ..the journal counted each, complete on the second",
          counts(fight, quests.KILL_MOBS), [([1, 0], 0), ([1, 1], 1)])
    here = inhabitants(goto(c, SCOUT_LOC))
    got = hand_in(c, here, TAIL, q_tail)
    check("  ..handed in to Корбен: a hundred afro",
          (upto_ack(got), acks(got), purse(got)),
          (["userInfo_Player", "cmdAck"], [0], AFRO0 + 20 + 300 + 200 + 100))
    got, q = take(c, here, MEDKIT)
    _, more = give(c, MEDS)
    got += more + c.frames(0.4)
    check("«Одолжить аптечку» taken; the medicaments in the bag: complete",
          counts(got, quests.BRING_L_OBJ), [([0], 0), ([1], 1)])
    got = hand_in(c, here, MEDKIT, q)
    check("  ..handed in to Корбен: the medicaments out, two hundred afro",
          (upto_ack(got), acks(got), purse(got)),
          (["ss_obj_status", "userInfo_Player", "cmdAck"], [0],
           AFRO0 + 20 + 300 + 200 + 100 + 200))
    check("Аюб's «Важные персоны» offered now", status(c, PERSONS), 1)
    got, q_rex = take(c, here, PERSONS)
    check("  ..taken: nought of one", counts(got, quests.KILL_MOBS), [([0], 0)])
    got = goto(c, REX)
    fight, killed, pos, _f, _w = hunt(c, got, REX, [COMMISSAR],
                                      first(got, "lenter").get("pos"))
    fight += c.frames(0.5)
    check("Комиссар Рекс shot among his raiders", killed, [COMMISSAR])
    check("  ..the journal says so, complete", counts(fight, quests.KILL_MOBS), [([1], 1)])
    here = inhabitants(goto(c, SCOUT_LOC))
    got = hand_in(c, here, PERSONS, q_rex)
    AFRO1 = AFRO0 + 20 + 300 + 200 + 100 + 200 + 300
    check("  ..handed in to Аюб: three hundred afro", (upto_ack(got), acks(got), purse(got)),
          (["userInfo_Player", "cmdAck"], [0], AFRO1))
    got, q_blow = take(c, here, BLOW)
    check("«Последний удар» taken from Аюб: no notes yet", counts(got, quests.BRING_L_OBJ),
          [([0], 0)])

    # --- the leader, at six in his camp ---------------------------------------------------
    got = goto(c, CAMP)
    check("at six the leader is in his camp", len(inhabitants(got).get(LEADER, [])), 1)
    fight, killed, pos, fell, wary = hunt(c, got, CAMP, [LEADER],
                                         first(got, "lenter").get("pos"))
    check("Ян Дуглас shot", killed, [LEADER])
    held, took = loot(c, fight, CAMP, pos, fell.get(LEADER, pos), wary)
    check("  ..his bag holds his notes, once (and his ingot)",
          ((held or []).count(NOTES), (held or []).count(INGOT)), (1, 1))
    check("  ..taken: the journal counts the notes, complete",
          counts(took, quests.BRING_L_OBJ)[-1:], [([1], 1)])
    got = goto(c, SCOUT_LOC)
    here, cell = inhabitants(got), first(got, "lenter").get("pos")
    got = hand_in(c, here, BLOW, q_blow)
    check("  ..handed in to Аюб: the notes out, the armour in, five hundred afro, the ack",
          (upto_ack(got), acks(got), new_things(got), purse(got), owned(CID).get(NOTES)),
          (["ss_obj_status", "ss_obj_status", "ss_di_wear", "userInfo_Player", "cmdAck"],
           [0], [ARMOUR], AFRO1 + 500, None))
    got, q = take(c, here, QUESTIONS)
    check("«Новые вопросы» taken from Аюб: his notes into the bag, the ack, found and"
          " complete", (order(got), first(got, "q_di_del_obj").get("obj"),
                        first(got, "q_di_del_obj").get("complete"), owned(CID).get(NOTES)),
          (["ss_obj_status", "ss_di_heap", "cmdAck", "q_di_del_obj"], 1, 1, 1))
    # The notes are what «Последний удар» asks for, and the drop of the quest
    # takes back only what the character still has: a set that went to
    # somebody else was a friend's 40 without the boss at every take.
    notes = [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status")
             if (inventory.parse_oid(str(p["obj"]).lstrip("x")) or (0, 0))[1] == NOTES]
    c.send("sndml;item=x%s;body=@@;type=0;subj=@x@;to=@Friend@;" % notes[0])
    got = c.frames()
    check("  ..not posted to a friend (no exchange: the client's own window refuses"
          " them too): refused, no ctml, the notes still in the bag",
          (order(got), acks(got), owned(CID).get(NOTES)), (["cmdAck"], [3], 1))
    c.send("ss_create;s_type=0;target=%d;" % cell)
    opened = acks(c.frames())
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % notes[0])
    got = c.frames()
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    check("  ..nor thrown on the ground for anybody to pick up: the session opens,"
          " the drop is refused, no bag goes down, the notes still in the bag",
          (opened, order(got), acks(got), owned(CID).get(NOTES)), ([0], ["cmdAck"], [3], 1))
    c.send("q_ca;q_id=%d;" % q)
    got = c.frames(0.8)
    check("  ..dropped: the notes go back to Аюб, before the ack",
          (upto_ack(got), acks(got), owned(CID).get(NOTES)), (["ss_obj_status", "cmdAck"],
                                                             [0], None))
    got, q = take(c, here, QUESTIONS)
    check("  ..and taken again: the notes again", (acks(got), owned(CID).get(NOTES)),
          ([0], 1))
    here = inhabitants(goto(c, VILLAGE))
    check("Наби's farewell waits for the notes", status(c, BIG_WORLD), 0)
    got = hand_in(c, here, QUESTIONS, q)
    check("  ..handed in to Наби: the notes out, the experience, the ack",
          (no_level(upto_ack(got)), acks(got), owned(CID).get(NOTES)),
          (["ss_obj_status", "rp_info", "cmdAck"], [0], None))
    got, q = take(c, here, BIG_WORLD)
    check("«Назад, в большой мир» taken from Наби, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, BIG_WORLD, q)
    check("  ..handed in to him: the tribe's gift, the experience, the ack",
          (no_level(upto_ack(got)), acks(got), new_things(got), owned(CID).get(CLEAVER)),
          (["ss_obj_status", "ss_di_coldarm", "rp_info", "cmdAck"], [0], [CLEAVER], 1))

    # --- to Вади-Хальфа, and Саид -------------------------------------------------------
    got, q = take(c, here, TO_HALFA)
    got = hand_in(c, here, TO_HALFA, q)
    call = first(got + ([] if named(got, "lcall") else
                        c.until(lambda f: f[0] == "lcall", 3)), "lcall")
    got = arrive(c)
    here = inhabitants(got)
    check("the ride out with the third level: Причал", call.get("id"), PIER)
    check("  ..Саид's errand offered now", status(c, WELCOME_H), 1)
    got, q = take(c, here, WELCOME_H)
    check("«Добро пожаловать в Хальфу» taken from Демир, complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = goto(c, QUARTER)
    here = inhabitants(got)
    got = hand_in(c, here, WELCOME_H, q)
    check("  ..handed in to Саид in the quarter: the experience, the ack",
          (no_level(upto_ack(got)), acks(got)), (["rp_info", "cmdAck"], [0]))

    # --- all of it ------------------------------------------------------------------------
    check("every one-off of the eighteen is in the history, once; the rides as they"
          " were ridden, both", ([t for t in done(CID) if t not in (TO_HALFA, BACK)],
                                 sorted({t for t in done(CID) if t in (TO_HALFA, BACK)})),
          (ONE_OFF, sorted({TO_HALFA, BACK})))
    check("  ..none of them is offered again", [t for t in ONE_OFF if status(c, t)], [])
    got = goto(c, PIER)
    check("the day's repeatable hand-ins untouched: ten left",
          [p["daily_available"] for p in named(got, "q_sys")][-1:], [10])
    logout(c)
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
print("valley story OK")
