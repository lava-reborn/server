"""Quests: the table in data/quests.json, and the frames the client builds one from.

There is no dialogue tree in the client. Talking to an NPC opens
QuestInterface, a window listing what that NPC gives and takes, and a quest is
three things on the wire (lol/core/quests/QuestInspector.as):

  q_status      per type: may this player take or carry it now, and its name
  q_si_<kind>   per type, once: the static description
  q_di_<kind>   per instance: progress and the complete flag

kind travels in the frame name -- q_si_kill_mobs, q_si_bring_l_obj,
q_si_del_obj -- not in a field, and each kind has its own mission class on the
client (KillMobQuest, BringObjQuest, DeliverObjQuest) reading its own keys.
Every key has to be present in every frame. Quest.initGDSLStringData compares
start_desc == "" and otherwise applies Number() to it, so an absent key turns
into NaN, getString(NaN) stays null, and stringUpdate never completes: the
quest has no name and the window shows "Загружается описание..." for good.
The four texts therefore always travel as string ids, with EMPTY_STRING_ID
standing in for a description the quest does not have.

Strings ride as numbers the client resolves once, before login, against
texts.xml?all=1 (PROTOCOL.md 9); an id outside that preload costs the player
the login screen. Quest strings are numbered STRING_BASE + 4 * type + k, and
names.py folds them into the one table both processes serve.
"""
import json
import os

KILL_MOBS, BRING_L_OBJ, DEL_OBJ = "kill_mobs", "bring_l_obj", "del_obj"
KINDS = (KILL_MOBS, BRING_L_OBJ, DEL_OBJ)

# String id layout (recon/analysis/quests.md 4.4): 2 000 000 + 4 * type + k.
STRING_BASE = 2_000_000
STRINGS_PER_QUEST = 4
NAME, START, NOTFINISH, FINISH = range(STRINGS_PER_QUEST)
# The one shared empty string, for a description a quest does not have.
EMPTY_STRING_ID = 5_000_000

# BringObjQuest.num: obj_1..obj_6, obj_num_1..6 and mobs_1..6 are read
# whether or not a slot is used, so all six are always sent.
BRING_SLOTS = 6

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "quests.json")


class Quest:
    """One row of the table, and the frames it produces."""

    def __init__(self, row):
        self.type = int(row["type"])
        self.kind = row["kind"]
        if self.kind not in KINDS:
            raise ValueError("quest %d: unknown kind %r" % (self.type, self.kind))
        # Exactly four texts, in string-id order.
        self.texts = (row["name"], row.get("start", ""),
                      row.get("notfinish", ""), row.get("finish", ""))
        self.give = [int(x) for x in row.get("give", [])]
        self.take = [int(x) for x in row.get("take", [])]
        self.rew_afro = int(row.get("rew_afro", 0))
        self.rew_gold = int(row.get("rew_gold", 0))
        self.rew_obj = [int(x) for x in row.get("rew_obj", [])]
        self.num_rew_obj = [int(x) for x in row.get("num_rew_obj", [])]
        if len(self.num_rew_obj) != len(self.rew_obj):
            self.num_rew_obj = [1] * len(self.rew_obj)
        self.repeatable = 1 if row.get("repeatable") else 0
        self.level = int(row.get("level", 0))
        self.q_type = int(row.get("q_type", 0))
        self.party_size = int(row.get("party_size", 0))
        # geoIDs for the map markers; 0 and -1 are the client's "none".
        self.loc = int(row.get("loc", 0))
        self.finish_loc = int(row.get("finish_loc", -1))
        self.rew_loc = int(row.get("rew_loc", 0))
        self.need_quest = int(row.get("need_quest", 0))
        # kind-specific goals
        self.mobs_kill = [int(x) for x in row.get("mobs_kill", [])]
        self.num_kill = [int(x) for x in row.get("num_kill", [])]
        if len(self.num_kill) != len(self.mobs_kill):
            raise ValueError("quest %d: num_kill must match mobs_kill" % self.type)
        objs = row.get("objs", [])
        if len(objs) > BRING_SLOTS:
            raise ValueError("quest %d: at most %d objects" % (self.type, BRING_SLOTS))
        self.objs = [(int(o["obj"]), int(o.get("num", 1)),
                      [int(m) for m in o.get("mobs", [])]) for o in objs]
        self.obj = int(row.get("obj", 0))

    @property
    def name(self):
        return self.texts[NAME]

    # --- strings -----------------------------------------------------------
    def string_id(self, k):
        """The id the client is sent for text k; the shared empty id when blank."""
        if not self.texts[k]:
            return EMPTY_STRING_ID
        return STRING_BASE + STRINGS_PER_QUEST * self.type + k

    def string_ids(self):
        return tuple(self.string_id(k) for k in range(STRINGS_PER_QUEST))

    def strings(self):
        return {self.string_id(k): self.texts[k]
                for k in range(STRINGS_PER_QUEST) if self.texts[k]}

    # --- frames ------------------------------------------------------------
    def si_frame(self):
        """q_si_<kind> with every key the client reads (Quest.initialize and
        the mission class), in the order recon/analysis/protocol.md 3.8 lists."""
        p = dict(type=self.type, repeatable=self.repeatable,
                 party_size=self.party_size, loc=self.loc,
                 finish_loc=self.finish_loc, level=self.level,
                 rew_obj=list(self.rew_obj), rew_afro=self.rew_afro,
                 rew_gold=self.rew_gold, rew_loc=self.rew_loc,
                 num_rew_obj=list(self.num_rew_obj), need_quest=self.need_quest,
                 q_type=self.q_type,
                 name=self.string_id(NAME), start_desc=self.string_id(START),
                 notfinish_desc=self.string_id(NOTFINISH),
                 finish_desc=self.string_id(FINISH))
        if self.kind == KILL_MOBS:
            p.update(mobs_kill=list(self.mobs_kill), num_kill=list(self.num_kill))
        elif self.kind == BRING_L_OBJ:
            for i in range(BRING_SLOTS):
                obj, num, mobs = self.objs[i] if i < len(self.objs) else (0, 0, [])
                p["obj_%d" % (i + 1)] = obj
                p["obj_num_%d" % (i + 1)] = num
                p["mobs_%d" % (i + 1)] = list(mobs)
        else:
            p["obj"] = self.obj
        return "q_si_" + self.kind, p

    def fresh_progress(self):
        """Progress of a just-taken instance, as stored in progress_json."""
        if self.kind == KILL_MOBS:
            return {"kill_num": [0] * len(self.mobs_kill)}
        if self.kind == BRING_L_OBJ:
            return {"obj_num": [0] * len(self.objs)}
        # A delivery with no item is a message: carried the moment it is
        # taken, so obj (DeliverObjQuest's "found" flag) is set at once.
        return {"obj": 0 if self.obj else 1}

    def is_complete(self, progress):
        if self.kind == KILL_MOBS:
            got = progress.get("kill_num", [])
            return all(g >= n for g, n in zip(got, self.num_kill)) and \
                len(got) == len(self.num_kill)
        if self.kind == BRING_L_OBJ:
            got = progress.get("obj_num", [])
            return all(g >= o[1] for g, o in zip(got, self.objs)) and \
                len(got) == len(self.objs)
        return bool(progress.get("obj", 0))

    def di_frame(self, q_id, progress, complete):
        """q_di_<kind>. Note q_type here is the quest's type id, not the
        category q_si carries under the same key (QuestInspector.q_di_*)."""
        p = dict(q_id=q_id, q_type=self.type, complete=1 if complete else 0)
        if self.kind == KILL_MOBS:
            p["kill_num"] = list(progress.get("kill_num", [0] * len(self.mobs_kill)))
        elif self.kind == BRING_L_OBJ:
            p["obj_num"] = list(progress.get("obj_num", [0] * len(self.objs)))
        else:
            p["obj"] = 1 if progress.get("obj", 0) else 0
        return "q_di_" + self.kind, p

    def reward_item(self, obj_idx):
        """The reward chosen by obj_idx, or None.

        QuestInterface.buildRewardItems numbers the icons id = n - 1 - i, so
        the index the client sends counts from the end of rew_obj.
        """
        n = len(self.rew_obj)
        i = n - 1 - int(obj_idx)
        if 0 <= i < n:
            return self.rew_obj[i], self.num_rew_obj[i]
        return None


def load(path=PATH):
    """type -> Quest, in file order. Errors are fatal: a table that fails to
    load would leave every quest id off the string preload."""
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["quests"]
    out = {}
    for row in rows:
        q = Quest(row)
        if q.type in out:
            raise ValueError("quest type %d listed twice" % q.type)
        out[q.type] = q
    return out


QUESTS = load()


def get(quest_type):
    return QUESTS.get(int(quest_type))


def given_by(npc_type):
    """Types this NPC hands out, in table order: q_st;q_idx indexes this list."""
    return [q.type for q in QUESTS.values() if npc_type in q.give]


def taken_by(npc_type):
    return [q.type for q in QUESTS.values() if npc_type in q.take]


def strings():
    """Every quest string id and its text, plus the shared empty one."""
    out = {EMPTY_STRING_ID: ""}
    for q in QUESTS.values():
        out.update(q.strings())
    return out


def kill_progress(store, char_id, mob_type):
    """A mob of this type died by this character's hand: advance every
    kill_mobs instance in the log that wants it.

    Returns the q_di_kill_mobs frames to push, one per instance that moved.
    KillMobQuest.update reads kill_num against what it holds and prints
    "Убито N целей из M" for the slot that changed; the client counts
    nothing itself, so a kill the server does not report never happened.
    """
    out = []
    for row in store.quests(char_id):
        quest = get(row["type"])
        if not quest or quest.kind != KILL_MOBS or mob_type not in quest.mobs_kill:
            continue
        progress = json.loads(row["progress_json"])
        kill_num = list(progress.get("kill_num", [0] * len(quest.mobs_kill)))
        kill_num += [0] * (len(quest.mobs_kill) - len(kill_num))
        moved = False
        for i, wanted in enumerate(quest.mobs_kill):
            if wanted == mob_type and kill_num[i] < quest.num_kill[i]:
                kill_num[i] += 1
                moved = True
        if not moved:
            continue
        progress["kill_num"] = kill_num
        complete = quest.is_complete(progress)
        store.update_quest(row["q_id"], progress, complete)
        out.append(quest.di_frame(row["q_id"], progress, complete))
    return out


def stub_si(quest_type):
    """An answer for a type we do not have.

    QuestInspector allows one quest request in flight and only frees it on a
    q_si_*/q_di_* frame, so an unknown type still has to be answered with a
    complete frame. The client only touches a Quest object it already created
    from q_list or q_status, so the values here are never shown.
    """
    p = dict(type=int(quest_type), repeatable=0, party_size=0, loc=0,
             finish_loc=-1, level=0, rew_obj=[], rew_afro=0, rew_gold=0,
             rew_loc=0, num_rew_obj=[], need_quest=0, q_type=0,
             name=EMPTY_STRING_ID, start_desc=EMPTY_STRING_ID,
             notfinish_desc=EMPTY_STRING_ID, finish_desc=EMPTY_STRING_ID,
             obj=0)
    return "q_si_" + DEL_OBJ, p


def stub_di(q_id):
    """An answer for an instance we do not have: complete=0, same reason."""
    return "q_di_" + DEL_OBJ, dict(q_id=int(q_id), q_type=0, complete=0, obj=0)
