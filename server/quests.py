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

What a row may ask for beyond the frames (the client shows none of it, so
it is the server's word alone, and the texts say it where the original
does):

  need_quest    a type, or a list of types, all handed in before this one is
                offered (the original's own key; q_si carries the first);
  need_any      a list of types, one of them handed in -- where two branches
                of a chain meet, as the valley's two starts do;
  excludes      a list of types: not offered to a character who has taken
                any of them or handed it in -- the other branch of a choice,
                as the valley's two tutorials are (the owner's «делай»,
                2026-09-26: one start, the starter gear once). The rows
                that exclude the same types are one branch (Quest.branch),
                and the branch a character handed a quest of in first
                stays open to him all the same: one that walked into both
                before the rule goes on with that one, not with neither. A
                quest already in the log stays his, and so does one that pays
                what a quest in the log asks for (Quest.feeds): a journal
                from before the rule is never stranded by it. Dropping a
                quest (q_ca) takes it back out of the reckoning;
  max_level     offered only while the best skill is at most this: the
                original's «недоступен после достижения третьего уровня
                любого навыка» is max_level 2;
  complete_skills
                base skill levels needed to hand in a talk, not to take it,
                e.g. {"shooting": 3}. Only del_obj with no item: the journal
                stays incomplete until the skills reach these levels. The
                requirement is appended after the original text is laid over;
  per_day       a repeatable quest handed in this many times since the
                day's reset is not offered again before the next one: the
                original's «данное задание можно выполнять не чаще 1 раза в
                сутки» is per_day 1 («На сегодня это всё. Приходи завтра.»).
                The day is the daily limit's (server.py DAILY_RESET_TIME),
                and the hand-in still counts against that limit too. The
                player is told: a start that does not say «в сутки» gets
                the original's note appended (_say_per_day), because the
                client prints «Задание является повторяемым» off the
                repeatable flag alone and the spent quest just leaves the
                giver's list, with no word why;
  cooldown      seconds: a repeatable quest handed in less than this long
                ago is not offered again yet -- the plant's lines, «Цикл
                закончен. Повторное использование возможно через 20 минут»
                (texts.xml 40304): 1200. Asked of the history like per_day
                (server.py Session.quest_available);
  start_obj     things put in the bag when the quest is taken -- a parcel,
                a bucket -- [{"obj": type, "num": pieces}]; taken back if the
                quest is dropped, and at the hand-in, wherever the character
                keeps them (START_OBJ_BACK_AT_HAND_IN); only things worth
                nothing away from the quest (START_OBJ_WORTHLESS_ONLY);
  lent          true on a row, or on one start_obj entry: what is handed over
                is lent, not given -- the Tir's training guns and rounds,
                the quarry's pick, «По завершению обучения заберу всё
                обратно» (59768). A lent thing may be worth something away
                from the quest (START_OBJ_WORTHLESS_ONLY does not ask it),
                because it never gets away: its frame carries the quest flag
                and no exchange (items.static_info), so no stall buys it and
                no barter, letter or lot takes it; it is not thrown on the
                ground and does not fall at a death, whatever the START_OBJ_*
                switches say; and the hand-in and the drop (q_ca) always take
                it back, from the bag, the hands, the body and the bank. A
                type a stall sells cannot be lent (check_items): the bought
                ones would be taken back with the lent;
  stay_in       a list of locations where what the quest lends stays: the
                quarry's pick in its five pits, a lesson's training gun in
                its range. Arriving anywhere else, whichever way -- the way
                out handed in, a death sent home, a login put back
                somewhere else -- takes it back as a drop would (server.py
                Session.keep_lent); the quest stays in the journal, to be
                finished on coming back or dropped. Only for a row that
                lends;
  rew_xp        experience into skills at the hand-in, {"medicine": 20}
                (SKILL_KEYS): the wiki's «+20 к Медицине»;
  rew_spec_xp   experience into specialisations at the hand-in,
                {"pistols": 20000} (SPEC_KEYS), the whole of it into the
                specialisation and none into its skill, premium share on
                top; a specialisation not learned by then takes nothing;
  requires_spec a key of SPEC_KEYS or a list of them: not offered, and not
                taken, unless every one of them is learned -- the
                original's «Требуется открытая специализация для зачисления
                опыта» (50441). A quest already in the log stays his;
  cost_afro, cost_gold
                a fee charged at the hand-in (gold in hundredths, as
                rew_gold): «с вашего счёта будет списано …». It is part of
                completeness: while the purse is short the journal is told
                the quest is not complete (the q_di_* complete flag, whatever
                the kills or the bag say), so the client shows the notfinish
                and no hand-in button, and nothing is taken; the moment the
                purse covers it the journal is told again (server.py
                Session.fee_gate, fee_recount). A kill quest pays it at the
                take instead (Quest.fee_at_take), is offered only to a purse
                that covers it, and gets it back when dropped: its journal
                cannot be told that a purse fell short after the last kill
                -- a q_di pushed with its kills unchanged makes the client
                print «Убит персонаж ... (undefined из undefined)» -- and
                the hand-in the client would still offer, refused, reads
                «дневной лимит» (QuestInspector.takeAck -> ErrorReport 44).
                A way whose move never comes gives its fee back (server.py
                Session.refund_fee);
  rew_random    [{"obj": type, "num": pieces, "w": weight}]: one entry drawn
                at the hand-in, by weight, and given beside rew_obj and
                rew_also (a lottery, «Любой предмет из вышеперечисленного
                списка в рандомном порядке»); announced by «Вы получили»
                like rew_also;
  service       true: a repeatable row that is a service, not a task --
                cashing, lotteries, exams, assemblies, ammunition -- is
                neither counted nor refused by the daily limit (server.py
                DAILY_MAX) and takes no place in the server's own count of
                the journal (server.py QUEST_LOG_CAPACITY). A way (data/
                passages.json 'quest') is treated the same;
  rew_also      things given at the hand-in beside the one chosen from
                rew_obj, [{"obj": type, "num": pieces}]: the window
                shows one reward and the player gets more, the way
                the wiki's «Стреляем» reads -- «Вы получите: Наган» in the
                window, «Наган, 7.62х25 (OLD) КС 50 штук» in its reward
                list. The client has no field for them (QuestInterface
                draws rew_obj alone, and more than one icon there is a
                choice of one), so only «Вы получили: …» names them, which
                lists every thing that came into the bag between the q_co
                and its ack (QuestInspector.getRewardItem);
  own_texts     a list of the four texts' keys ("name", "start",
                "notfinish", "finish") the row keeps as written, where the
                original's own would otherwise be laid over it
                (_lay_original): a line of the original this server cannot
                stand behind -- 158's «у вас должен быть вид на жительство
                или гражданство», Мортимер's cashing (301-303) «Как для лица
                не имеющего гражданства или вида на жительство», a premium
                of the dead server's, the owner's cut of (P) of 2026-09-30
                -- is taken out of the row and stays out. The row's own text
                is still cleaned as the original's would be (orig_texts.text).

A slot of objs may carry "drop": a chance. Its mobs then drop the thing,
the way a «Квестовый» row of data/loot_manual.json does (mobs.QUEST_TIER):
only for somebody who brought the creature down with a quest open that asks
for the thing and holds fewer than it asks (wanted_things), never for
anybody else (quest_drops). A slot with a drop may also carry "one_of": a
group's name. The things of one group come off a corpse one at most: the
group is rolled once, at the highest chance of its wanted things, and one of
those drawn (drop_group, mobs.quest_roll) -- so what falls does not grow
with the number of such rows a player holds open.

A way (data/passages.json 'quest') is handed in as any quest is -- complete
or refused, what it asks for taken, what was handed over taken back, the fee
charged, the reward paid, the history written, so that per_day counts it and
need_quest opens after it -- and only then does it move the player (server.py
Session.cmd_q_co, hand_in_way).

Every thing a row names -- rew_obj, rew_also, rew_random, start_obj, obj,
objs -- has to be a thing the game has, or the hand-in that makes it fails
half-way: written into the history, nothing paid, no ack. load() cannot ask that
(items imports sets, which imports this module, so items is not there yet
when the table is read), and the server asks check_items before its first
socket instead.
"""
import json
import os
import random
import re

import progression                 # no imports of its own; safe at load

KILL_MOBS, BRING_L_OBJ, DEL_OBJ = "kill_mobs", "bring_l_obj", "del_obj"
KINDS = (KILL_MOBS, BRING_L_OBJ, DEL_OBJ)

# String id layout (recon/analysis/quests.md 4.4): 2 000 000 + 4 * type + k.
STRING_BASE = 2_000_000
STRINGS_PER_QUEST = 4
NAME, START, NOTFINISH, FINISH = range(STRINGS_PER_QUEST)
# The row's keys of the four, in the same order (own_texts, _lay_original).
TEXT_KEYS = ("name", "start", "notfinish", "finish")
# The one shared empty string, for a description a quest does not have.
EMPTY_STRING_ID = 5_000_000

# BringObjQuest.num: obj_1..obj_6, obj_num_1..6 and mobs_1..6 are read
# whether or not a slot is used, so all six are always sent.
BRING_SLOTS = 6

# The skills rew_xp may name. The fifth, production, is hidden on the card
# (its specialisations have no slide in the teacher's window), so a quest
# does not train it.
SKILL_KEYS = {"melee": progression.MELEE, "shooting": progression.SHOOTING,
              "medicine": progression.MEDICINE, "industry": progression.INDUSTRY}

# The specialisations rew_spec_xp and requires_spec may name, by their index
# on the card (PersAttributes.specMatrix; recon/analysis/progression.md 1.3):
# the twelve a teacher offers (progression.LEARNABLE). The production three
# are hidden, as their skill is.
SPEC_KEYS = {"unarmed": 0, "blades": 1, "pistols": 2, "shotguns": 3,
             "assault": 4, "rifles": 5, "machineguns": 6, "smg": 7,
             "surgery": 8, "first_aid": 9, "mining": 10, "recycling": 11}

# What rew_random draws with. Its own generator, seeded like the others by
# LAVA_SEED, so a suite gets the same prize twice.
RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

# Whether what a quest puts in the bag at the take (start_obj) stays on the
# body at a death, the way a quest's own thing does (combat.drops_on_death).
# The owner's decision (2026-09-26), for this reason: a parcel fallen into a
# bag on the ground leaves a delivery that can never be handed in -- found
# only while the bag holds it -- and the one way on is to drop the quest and
# take it again. False lets it fall like any loot -- and into anybody's
# hands, the loop START_OBJ_NOT_ON_GROUND closes for a thing thrown down.
START_OBJ_KEPT_ON_DEATH = True

# Whether a thing one quest pays as its reward and another quest asks to be
# brought -- the cow's milk for Салех («Подоить корову» for «Друзья»), the
# box's tools for Ибрахим («Забрать инструменты» for «Друзья I») -- stays on
# the body at a death too, when it is worth nothing away from them (no
# price, no exchange: items.params_of). The same reason as a parcel's, and
# a harder one: the quest that pays it is a one-off, as the original's was
# («не повторяемым»), so a thing fallen into a bag on the ground is a chain
# that can never be walked on. False lets it fall like any loot. The
# owner's to change; DESIGNED on the owner's parcel rule (2026-09-26).
STEP_REWARD_KEPT_ON_DEATH = True

# Whether the hand-in takes back, besides what the quest asks for (wants),
# the rest of what its giver handed over at the take -- the bucket beside
# the parcel -- as much of it as the character still has, the way dropping
# the quest does (Quest.returns, Inventory.reclaim_pieces). The owner's
# decision (2026-09-26): what a quest hands over it «takes back at hand-in
# (or on cancel)». False leaves the rest with the player, and then a
# repeatable quest hands another one over at every take.
START_OBJ_BACK_AT_HAND_IN = True

# Whether a quest may hand over at the take only a thing worth nothing away
# from it: no stall pays for it (cost 0, or the quest flag -- Inventory.sell
# refuses those), it changes hands neither by barter, nor at the auction,
# nor by post (no exchang, or the quest flag -- barter.tradable, auction,
# mail.postable; the ground is START_OBJ_NOT_ON_GROUND's), and it is not used
# up by its use (not a medicine or a booster, not rounds: items.HEAL, AMMO).
# What left the character altogether -- sold, traded, eaten, fired, thrown
# away -- is not there to take back when the quest is dropped, so a thing
# that sold would be money made by taking the quest, selling it, dropping
# the quest and taking it again, as often as one likes, and a medicine a
# free one each time. The valley's parcels (3481 and the rest) are all
# worth nothing. Asked by check_items; a table that breaks it does not start
# the server. False lets a row hand over anything, and those loops with it.
# A thing lent (the docstring's lent) is not asked: it never gets away.
START_OBJ_WORTHLESS_ONLY = True

# Whether a thing a quest hands over at the take (start_obj) stays with the
# character it was handed to: it is not thrown on the ground (a loot bag's
# ss_upd 2, combat.Fighter.ss_upd -- the equipment window's «Выкинуть
# предмет?», PersEquip.dropItem), where whoever stands by picks it up. Worth
# nothing is not enough when another quest asks for the same thing:
# «Новые вопросы» (41) hands over Записи 234, the very notes «Последний удар»
# (40) asks to be taken from Ян Дуглас, and what went down is not there for
# the drop of 41 to take back (Inventory.reclaim_pieces), so taking 41 again
# handed over a new set -- a friend's 40 for every set thrown down, 500 afro
# and a body armour each, and no boss (and the antelope's meat of «Любимая
# антилопа (часть 2)», 61, is what «Еда», 62, asks for). The post is closed
# to it by the client's own rule (mail.postable: no exchang, or the quest
# flag), barter and the auction by theirs, a death keeps it on the body
# (START_OBJ_KEPT_ON_DEATH), and the bank is the character's own; the trash
# can still takes it, gone for everybody. Refused, the client puts it back
# in the bag (Loot.transferAck). DESIGNED (2026-09-26). False lets it go
# down like any thing, and that loop with it.
START_OBJ_NOT_ON_GROUND = True

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "quests.json")


def quests_path():
    """data/quests.json, or the file LAVA_QUESTS names. The variable is for a
    suite that needs quests the world does not have yet -- a parcel, a chain,
    a cap -- on NPCs that stand where it plays (test_quest_mechanics); like
    LAVA_PASSAGES it replaces the table rather than adding to it."""
    return os.environ.get("LAVA_QUESTS") or PATH


def companion_paths(path):
    """The tables that come with data/quests.json: every data/questgen_*.json
    beside it, in name order, each {"quests": [...]} like the main one (not
    quests_*: data/quests_wiki.json is the wiki's raw material). They
    hold the rows a builder writes by the hundred (a recipe family, a
    region's generated work), so that the hand-written table stays readable
    and two builders never edit one file. Only the real table has them: a
    table LAVA_QUESTS names, or any other path, stands alone."""
    if os.path.abspath(path) != os.path.abspath(PATH):
        return []
    here = os.path.dirname(PATH)
    return [os.path.join(here, f) for f in sorted(os.listdir(here))
            if f.startswith("questgen_") and f.endswith(".json")]


def table_rows(path=None):
    """Every row of the table and its companions, in file order."""
    path = path or quests_path()
    rows = []
    for p in [path] + companion_paths(path):
        with open(p, encoding="utf-8") as fh:
            rows += json.load(fh)["quests"]
    return rows


def _types(v):
    """A type or a list of types, as a list."""
    if v in (None, "", 0):
        return []
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v if int(x)]
    return [int(v)]


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
        # The texts the original's are not laid over (the docstring's
        # own_texts, _lay_original).
        self.own_texts = frozenset(row.get("own_texts") or ())
        unknown = sorted(self.own_texts - set(TEXT_KEYS))
        if unknown:
            raise ValueError("quest %d: own_texts names no text %s" % (self.type, unknown))
        self.give = [int(x) for x in row.get("give", [])]
        self.take = [int(x) for x in row.get("take", [])]
        self.rew_afro = int(row.get("rew_afro", 0))
        self.rew_gold = int(row.get("rew_gold", 0))
        self.rew_obj = [int(x) for x in row.get("rew_obj", [])]
        self.num_rew_obj = [int(x) for x in row.get("num_rew_obj", [])]
        if len(self.num_rew_obj) != len(self.rew_obj):
            self.num_rew_obj = [1] * len(self.rew_obj)
        # Beside the one chosen, never instead of it (the docstring).
        self.rew_also = [(int(o["obj"]), int(o.get("num", 1)))
                         for o in row.get("rew_also", [])]
        if any(n < 1 for _obj, n in self.rew_also):
            raise ValueError("quest %d: rew_also pieces must be positive" % self.type)
        self.repeatable = 1 if row.get("repeatable") else 0
        self.level = int(row.get("level", 0))
        self.q_type = int(row.get("q_type", 0))
        self.party_size = int(row.get("party_size", 0))
        # geoIDs for the map markers; 0 and -1 are the client's "none".
        self.loc = int(row.get("loc", 0))
        self.finish_loc = int(row.get("finish_loc", -1))
        self.rew_loc = int(row.get("rew_loc", 0))
        # Chains (the module's docstring): every type of need_all handed in,
        # and one of need_any. q_si's need_quest is the first of need_all;
        # the client keeps it and shows it nowhere.
        self.need_all = _types(row.get("need_quest"))
        self.need_any = _types(row.get("need_any"))
        self.need_quest = self.need_all[0] if self.need_all else 0
        if self.type in self.need_all + self.need_any:
            raise ValueError("quest %d needs itself" % self.type)
        # The other branch (the docstring); asked of the log and the history.
        self.excludes = _types(row.get("excludes"))
        if self.type in self.excludes:
            raise ValueError("quest %d excludes itself" % self.type)
        # Its own branch, the rows that exclude the same; load fills it in.
        self.branch = [self.type]
        cap = row.get("max_level")
        self.max_level = None if cap is None else int(cap)
        # Hand-ins a day (the docstring); 0 is no such limit. Only a
        # repeatable quest has a second day: a one-off is gone once done.
        self.per_day = int(row.get("per_day", 0))
        if self.per_day < 0 or (self.per_day and not self.repeatable):
            raise ValueError("quest %d: per_day is for a repeatable quest, at least 1"
                             % self.type)
        # Seconds before it is offered again (the docstring's cooldown).
        self.cooldown = int(row.get("cooldown", 0))
        if self.cooldown < 0 or (self.cooldown and not self.repeatable):
            raise ValueError("quest %d: cooldown is for a repeatable quest, in seconds"
                             % self.type)
        self.start_obj = [(int(o["obj"]), int(o.get("num", 1)))
                          for o in row.get("start_obj", [])]
        if any(n < 1 for _obj, n in self.start_obj):
            raise ValueError("quest %d: start_obj pieces must be positive" % self.type)
        # Lent, not given (the docstring): the whole row's hand-over, or one
        # entry's.
        self.lent = frozenset(int(o["obj"]) for o in row.get("start_obj", [])
                              if row.get("lent") or o.get("lent"))
        # Where the lent things stay (the docstring's stay_in).
        self.stay_in = frozenset(_types(row.get("stay_in")))
        if self.stay_in and not self.lent:
            raise ValueError("quest %d: stay_in keeps what is lent, and it lends nothing"
                             % self.type)
        xp = row.get("rew_xp", {}) or {}
        unknown = sorted(set(xp) - set(SKILL_KEYS))
        if unknown:
            raise ValueError("quest %d: rew_xp names no skill %s" % (self.type, unknown))
        self.rew_xp = [(SKILL_KEYS[k], int(v)) for k, v in xp.items() if int(v) > 0]
        spec_xp = row.get("rew_spec_xp", {}) or {}
        needs = row.get("requires_spec") or []
        needs = [needs] if isinstance(needs, str) else list(needs)
        unknown = sorted((set(spec_xp) | set(needs)) - set(SPEC_KEYS))
        if unknown:
            raise ValueError("quest %d: rew_spec_xp/requires_spec name no specialisation %s"
                             % (self.type, unknown))
        self.rew_spec_xp = [(SPEC_KEYS[k], int(v)) for k, v in spec_xp.items() if int(v) > 0]
        self.requires_spec = [SPEC_KEYS[k] for k in needs]
        # The fee, charged at the hand-in and part of completeness (the
        # docstring); gold in hundredths, as rew_gold.
        self.cost_afro = int(row.get("cost_afro", 0))
        self.cost_gold = int(row.get("cost_gold", 0))
        if self.cost_afro < 0 or self.cost_gold < 0:
            raise ValueError("quest %d: a fee cannot be negative" % self.type)
        self.rew_random = [(int(o["obj"]), int(o.get("num", 1)), int(o.get("w", 1)))
                           for o in row.get("rew_random", [])]
        if any(n < 1 or w < 1 for _obj, n, w in self.rew_random):
            raise ValueError("quest %d: rew_random pieces and weights must be positive"
                             % self.type)
        self.service = bool(row.get("service"))
        # kind-specific goals
        self.mobs_kill = [int(x) for x in row.get("mobs_kill", [])]
        self.num_kill = [int(x) for x in row.get("num_kill", [])]
        if len(self.num_kill) != len(self.mobs_kill):
            raise ValueError("quest %d: num_kill must match mobs_kill" % self.type)
        # Other creature types a kill of which counts for a slot: type -> the
        # slot's type in mobs_kill. The client shows the slot's own creature
        # and its count; a kin of it under another type id (the mine's [9]
        # miners beside the [8] the raid names) moves the same count.
        self.kill_also = {int(k): int(v) for k, v in row.get("kill_also", {}).items()}
        if any(v not in self.mobs_kill for v in self.kill_also.values()):
            raise ValueError("quest %d: kill_also must count for a slot of mobs_kill"
                             % self.type)
        objs = row.get("objs", [])
        if len(objs) > BRING_SLOTS:
            raise ValueError("quest %d: at most %d objects" % (self.type, BRING_SLOTS))
        self.objs = [(int(o["obj"]), int(o.get("num", 1)),
                      [int(m) for m in o.get("mobs", [])]) for o in objs]
        # A slot's own drop (the docstring): (mob, thing, chance), and the
        # group it falls one of (thing -> "one_of").
        self.drops = []
        self.drop_groups = {}
        for o in objs:
            if o.get("drop") is None:
                continue
            chance = float(o["drop"])
            if not 0 < chance <= 1 or not o.get("mobs"):
                raise ValueError("quest %d: a slot's drop is a chance in (0, 1] and needs"
                                 " its mobs" % self.type)
            self.drops += [(int(m), int(o["obj"]), chance) for m in o["mobs"]]
            if o.get("one_of"):
                self.drop_groups[int(o["obj"])] = str(o["one_of"])
        self.obj = int(row.get("obj", 0))
        goals = row.get("complete_skills") or {}
        if set(goals) - set(SKILL_KEYS):
            raise ValueError("quest %d: complete_skills names an unknown skill" % self.type)
        self.complete_skills = [(SKILL_KEYS[k], int(v)) for k, v in goals.items()]
        if self.complete_skills and (self.kind != DEL_OBJ or self.obj
                                     or any(not 1 <= v <= progression.SKILL_MAX
                                            for _, v in self.complete_skills)):
            raise ValueError("quest %d: complete_skills needs a talk and levels 1..20"
                             % self.type)

    @property
    def name(self):
        return self.texts[NAME]

    @property
    def has_fee(self):
        return bool(self.cost_afro or self.cost_gold)

    @property
    def fee_at_take(self):
        """Whether the fee is paid when the quest is taken, not at the
        hand-in: a kill quest's (the docstring's cost_afro)."""
        return self.has_fee and self.kind == KILL_MOBS

    @property
    def pays(self):
        """Whether the hand-in pays anything: money, a thing, experience."""
        return bool(self.rew_afro or self.rew_gold or self.rew_obj or self.rew_also
                    or self.rew_random or self.rew_xp or self.rew_spec_xp)

    def affordable(self, afro, gold):
        """Whether a purse of afro and gold (hundredths) covers the fee."""
        return afro >= self.cost_afro and gold >= self.cost_gold

    def draw(self, rng=None):
        """(type, pieces) of rew_random drawn by weight, or None."""
        if not self.rew_random:
            return None
        obj, num, _w = (rng or RNG).choices(
            self.rew_random, weights=[w for _o, _n, w in self.rew_random])[0]
        return obj, num

    @property
    def counts_bag(self):
        """Whether the bag decides the progress: a quest that asks for
        things, and a delivery of a real thing (obj), which is "found" --
        DeliverObjQuest's flag, the journal's «найден, но не доставлен» --
        while the bag holds one. A delivery with no thing is a message."""
        return self.kind == BRING_L_OBJ or (self.kind == DEL_OBJ and self.obj != 0)

    def wants(self):
        """(type, pieces) the hand-in takes out of the bag: each slot of a
        quest that asks for things, the one thing a delivery carries."""
        if self.kind == BRING_L_OBJ:
            return [(obj, num) for obj, num, _mobs in self.objs]
        if self.kind == DEL_OBJ and self.obj:
            return [(self.obj, 1)]
        return []

    def returns(self):
        """(type, pieces) the hand-in takes back besides wants(): what the
        giver handed over at the take (start_obj) and the quest does not ask
        for -- the buckets beside the parcel -- taken as a dropped quest
        takes it, as much as is left (Inventory.reclaim_pieces). With
        START_OBJ_BACK_AT_HAND_IN off, only what was lent (lent)."""
        asked = {}
        for obj, num in self.wants():
            asked[obj] = asked.get(obj, 0) + num
        out = []
        for obj, num in self.start_obj:
            covered = min(num, asked.get(obj, 0))
            asked[obj] = asked.get(obj, 0) - covered
            if num > covered and (START_OBJ_BACK_AT_HAND_IN or obj in self.lent):
                out.append((obj, num - covered))
        return out

    def things(self):
        """(field, type) of every thing the row names: what it pays, hands
        over, carries and asks to be brought (check_items)."""
        return [("rew_obj", t) for t in self.rew_obj] + \
            [("rew_also", t) for t, _n in self.rew_also] + \
            [("rew_random", t) for t, _n, _w in self.rew_random] + \
            [("start_obj", t) for t, _n in self.start_obj] + \
            ([("obj", self.obj)] if self.obj else []) + \
            [("objs", t) for t, _n, _mobs in self.objs]

    def prerequisites_met(self, done):
        """Whether the chain lets this quest be offered; done(type) answers
        whether this character has handed that type in."""
        return all(done(t) for t in self.need_all) and \
            (not self.need_any or any(done(t) for t in self.need_any))

    def excluded_by(self, touched):
        """Whether the other branch keeps this quest back (excludes);
        touched(type) answers whether this character has that type in his
        log or has handed it in."""
        return any(touched(t) for t in self.excludes)

    def feeds(self, other):
        """Whether this quest pays -- the thing chosen or one beside it -- a
        thing the other asks for (wants): the cow's milk for Зула's
        «Друзья», the box's tools for Ибрахим's."""
        paid = set(self.rew_obj) | {t for t, _n in self.rew_also}
        return any(t in paid for t, _n in other.wants())

    def over_cap(self, level):
        """Past max_level: the quest is no longer this player's."""
        return self.max_level is not None and level > self.max_level

    def done_for_today(self, handed_today):
        """Whether per_day is spent, handed_today being this type's hand-ins
        since the day's reset: not offered again before the next one."""
        return bool(self.per_day) and handed_today >= self.per_day

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
        # taken, so obj (DeliverObjQuest's "found" flag) is set at once. One
        # with an item is found by the bag (bag_progress).
        return {"obj": 0 if self.obj else 1}

    def bring_count(self, have):
        """obj_num as the bag answers it, have being type -> pieces in the
        bag (inventory.Inventory.bag_pieces): per slot, the pieces of its
        type, never more than the slot asks for -- the journal counts
        towards the goal, the way kill_num stops at num_kill."""
        return [min(int(have.get(obj, 0)), num) for obj, num, _mobs in self.objs]

    def bag_progress(self, have):
        """The part of the progress the bag answers (counts_bag): obj_num
        of a quest that asks for things, obj -- found or not -- of a
        delivery of a thing."""
        if self.kind == BRING_L_OBJ:
            return {"obj_num": self.bring_count(have)}
        return {"obj": 1 if int(have.get(self.obj, 0)) >= 1 else 0}

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

        Quest.createRewardItems first reverses rew_obj: AS2 for..in walks
        array indexes backwards and pushes each prototype into a new array.
        QuestInterface.buildRewardItems assigns id = n - 1 - i in that
        reversed array, so the wire index is back in the original order.
        """
        n = len(self.rew_obj)
        i = int(obj_idx)
        if 0 <= i < n:
            return self.rew_obj[i], self.num_rew_obj[i]
        return None


def load(path=None):
    """type -> Quest, in file order. Errors are fatal: a table that fails to
    load would leave every quest id off the string preload. So is a chain
    that cannot be walked -- a prerequisite the table does not have, or a
    ring of them: its quests would never be offered to anybody -- and an
    exclusion the table does not have, or one of the quest's own
    prerequisites, however far back: it would never be offered either.
    The first problem check_rows finds is raised, as it was found."""
    out, found = check_rows(table_rows(path))
    if found:
        raise found[0]
    return out


def check_rows(rows):
    """type -> Quest for every row that makes one, and every problem of the
    table, each an exception, in the order load meets them: a row that does
    not make a quest (Quest raises), a type listed twice, then the chains
    (table_problems). load raises the first; the quest editor
    (tools/quest_editor) shows them all, so that one save is told everything
    a table holds wrong rather than one thing per try."""
    out, found = {}, []
    for row in rows:
        try:
            q = Quest(row)
        except (ValueError, KeyError, TypeError) as exc:
            found.append(exc)
            continue
        if q.type in out:
            found.append(ValueError("quest type %d listed twice" % q.type))
            continue
        out[q.type] = q
    found += [ValueError(m) for m in table_problems(out)]
    return out, found


def table_problems(out):
    """What is wrong with the chains of a table (type -> Quest), in words:
    a prerequisite or an exclusion the table does not have, a ring, an
    exclusion of what the quest itself needs. Fills in each quest's branch
    (the rows that exclude the same) on the way. A quest whose chain is
    already wrong one way is not asked the next: the first word is the one
    worth reading."""
    found, wrong = [], set()
    for q in out.values():
        missing = [t for t in q.need_all + q.need_any if t not in out]
        if missing:
            found.append("quest %d needs %s, which the table does not have"
                         % (q.type, missing))
            wrong.add(q.type)
    for q in out.values():
        if q.type in wrong:
            continue
        seen, todo = set(), list(q.need_all + q.need_any)
        while todo:
            t = todo.pop()
            if t == q.type:
                found.append("quest %d needs itself through its chain" % q.type)
                wrong.add(q.type)
                break
            if t not in seen and t in out:
                seen.add(t)
                todo += out[t].need_all + out[t].need_any
    for q in out.values():
        if q.type in wrong:
            continue
        missing = [t for t in q.excludes if t not in out]
        if missing:
            found.append("quest %d excludes %s, which the table does not have"
                         % (q.type, missing))
            continue
        # Everything that has to be handed in before it: need_all, and theirs.
        needed, todo = set(), list(q.need_all)
        while todo:
            t = todo.pop()
            if t not in needed and t in out:
                needed.add(t)
                todo += out[t].need_all
        blocked = sorted(needed & set(q.excludes))
        if blocked or (q.need_any and set(q.need_any) <= set(q.excludes)):
            found.append("quest %d excludes what it needs (%s): it would never be"
                         " offered" % (q.type, blocked or q.need_any))
            continue
        # Its own branch: every row that excludes the same, itself among
        # them -- none of which it can exclude, as none excludes itself.
        if q.excludes:
            q.branch = sorted(t for t, o in out.items() if set(o.excludes) == set(q.excludes))
    return found


QUESTS = load()


def check_items(table=None):
    """Every thing a quest row names is one the game has (items.params_of)
    and no premium one (items.premium, out of the game since the owner's
    cut of (P)), and what one hands over at the take is worth nothing away from it
    (START_OBJ_WORTHLESS_ONLY): of this module's table, or of the one given
    (type -> Quest, as load returns it).

    Fatal, like a chain that cannot be walked (load), and asked by the
    server once the items are read, before its first socket (server.main).
    load() itself cannot: items imports sets and sets imports this module,
    so the table is read before items is there to ask, and items is
    imported here, late, for the same reason. A reward that is no item
    would fail the hand-in half-way -- written into the history, nothing
    paid, no cmdAck, the one-off quest gone for good -- and one handed over
    at the take would hand the pieces before it, write no quest and ack
    nothing, so that a retry hands them again. A delivery or a thing to
    bring that is no item could never be handed in. What is lent (the
    docstring's lent) may be worth something, but no stall may sell it:
    the lent type's frame carries the quest flag, so a bought copy could not
    be sold again, and the hand-in would take it back with the lent one.
    Returns None; raises ValueError naming the quest and the types -- the
    first of item_problems.
    """
    found = item_problems(table)
    if found:
        raise ValueError(found[0])


def item_problems(table=None):
    """check_items's findings, every one of them, in words: per quest the
    things the game does not have, the premium ones, the lent ones a stall
    sells, the dear ones handed over (the order check_items raises them in)."""
    import items                       # late: see check_items
    import npcs
    table = QUESTS if table is None else table
    found = []
    sold = {}
    if any(q.lent for q in table.values()):
        for trader in set(items.stock_table()) | set(npcs.STOCK):
            for t in items.stock_for(trader):
                sold.setdefault(t, trader)
    for q in table.values():
        unknown = ["%s %d" % (field, t) for field, t in q.things()
                   if items.params_of(t) is None]
        if unknown:
            found.append("quest %d names things the game does not have: %s"
                         % (q.type, ", ".join(unknown)))
        # Nor a premium one, given or asked for, on a row switched on or
        # off: (P) is out of the game (items.premium; the owner's cut of
        # (P), 2026-09-30), and a row switched on later must not bring one
        # back past the stalls' and the loot's filters.
        premium = ["%s %d" % (field, t) for field, t in q.things()
                   if items.params_of(t) is not None and items.premium(t)]
        if premium:
            found.append("quest %d names premium things, out of the game: %s"
                         % (q.type, ", ".join(premium)))
        on_sale = ["%d (trader %d)" % (t, sold[t]) for t in sorted(q.lent) if t in sold]
        if on_sale:
            found.append("quest %d lends what a stall sells: %s"
                         % (q.type, ", ".join(on_sale)))
        if not START_OBJ_WORTHLESS_ONLY:
            continue
        dear = []
        for t, _n in q.start_obj:
            if t in q.lent:
                continue
            si = items.params_of(t)
            if si is None:
                continue                # told above, among the unknown
            if items.root_of(t) in (items.HEAL, items.AMMO):
                dear.append("%d (used up by its use)" % t)
            elif not si.get("quest") and (si.get("cost", 0) > 0 or si.get("exchang")):
                dear.append("%d (cost %s, exchang %s)" % (t, si.get("cost", 0),
                                                         si.get("exchang", 0)))
        if dear:
            found.append("quest %d hands over what is worth something away from "
                         "it: %s (quests.START_OBJ_WORTHLESS_ONLY)"
                         % (q.type, ", ".join(dear)))
    return found


def _lay_original():
    """The original's texts of our quests, over the ones we had.

    Only where the original has the text: a slot it leaves empty keeps ours,
    and so does one the row names in own_texts (the module's docstring),
    whose words were changed from the original's on purpose. orig_texts has
    already cleaned them -- the doubled "%sex??" that would show a man
    "гол?ым", the escaped quotes -- and kept the <hint> numbers and the
    %имя% macros, which the client fills in itself (Quest.as:169-181).

    An own text gets the same cleaning (orig_texts.text). It is the
    original's line with a sentence taken out, and the rows were copied from
    texts.xml before that cleaning existed: 158's start went out with the
    original's '\\"Охранять\\"', which the tooltip never unescapes -- the
    ВНЖ sentence gone, and the line reading worse than the original's
    (2026-10-02). The rows are written clean now; this is the net under the
    next one copied by hand.
    """
    import orig_texts                  # no imports of its own; safe at load
    originals = orig_texts.quests()
    for q in QUESTS.values():
        _lay(q, originals)


def _lay(q, originals):
    """_lay_original for one quest: originals is orig_texts.quests()."""
    import orig_texts
    texts = originals.get(q.type) or {}
    q.texts = tuple(orig_texts.text(old) if key in q.own_texts
                    else texts.get(key) or old
                    for key, old in zip(TEXT_KEYS, q.texts))


_lay_original()


# The note the original writes at the end of a daily quest's start, in the
# words of «В поисках артефактов» (405) and nine others of its rows.
PER_DAY_NOTE = "<Br><Br><b>Примечание:</b> данное задание можно выполнять не чаще %s в сутки."
# Breaks a start ends on (181 «Курьер» on <Br>, 182 «Медик Умар» on </Br><Br>):
# the note brings its own two, and a blank line between would be a third.
_TRAILING_BREAKS = re.compile(r"(?:\s|</?br\s*/?>)+$", re.IGNORECASE)


def per_day_times(n):
    """«1 раза», «3 раз»: the count as the note declines it."""
    n = int(n)
    return "%d раза" % n if n % 10 == 1 and n % 100 != 11 else "%d раз" % n


def per_day_start(start, per_day):
    """A start as the player reads it: as written for a quest that is not
    daily or whose start says «в сутки» already, else with PER_DAY_NOTE in
    place of its trailing breaks."""
    if not per_day or "в сутки" in start:
        return start
    return _TRAILING_BREAKS.sub("", start) + PER_DAY_NOTE % per_day_times(per_day)


def served(q, k, line):
    """The original's line for slot k of quest q (NAME..FINISH) as this
    server serves it: the start carries its daily note and any skill goal
    after the original overlay (_say_per_day). What the suites hold the laid
    texts to (every «laid over the table's» check)."""
    if k != START:
        return line
    line = per_day_start(line, q.per_day)
    if q.complete_skills:
        labels = ("Ближний бой", "Стрельба", "Медицина", "Промышленность")
        goals = "; ".join("%s: %d-й уровень" % (labels[i], level)
                          for i, level in q.complete_skills)
        line += ("<Br><Br><b>Задача:</b> Развить навык до указанного уровня "
                 "и вернуться к персонажу, выдавшему задание. " + goals + ".")
    return line


def _say_per_day():
    """Append daily notes and skill goals after the original overlay.

    The original's own dailies say it in their text; the rows this server
    made daily (DESIGNED per_day: «Золотоискатель», the prison's armbands,
    the quarry's stones) did not, and the client has no flag to say it for
    them: Quest.repeatable alone makes it print «Задание является
    повторяемым», and a quest handed in today is simply not offered
    (server.py Session.quest_available), so a player read «повторяемым»,
    found the quest gone, and reported a fault (2026-10-02). After the
    original's texts are laid, so that an original start keeps its own note
    and a row the overlay replaces (118) is read as the player will see it.
    """
    for q in QUESTS.values():
        _note(q)


def _note(q):
    """_say_per_day for one quest."""
    start = served(q, START, q.texts[START])
    if start != q.texts[START]:
        texts = list(q.texts)
        texts[START] = start
        q.texts = tuple(texts)


_say_per_day()


# What a start writes where the boss hours go: the starts of 10, 131 and 132
# tell the player when the boss is there, and the hours are LAVA_BOSS_HOURS's
# (bosses.py), so the text is made from them rather than written down and
# left behind when they change.
BOSS_HOURS_MARKS = {"{boss_hours}": False, "{boss_hours_short}": True}


def _say_boss_hours():
    for q in QUESTS.values():
        _hours(q)


def _hours(q):
    """_say_boss_hours for one quest."""
    import bosses                      # world only; safe at load
    texts = list(q.texts)
    for k, text in enumerate(texts):
        for mark, short in BOSS_HOURS_MARKS.items():
            if text and mark in text:
                text = text.replace(mark, bosses.say_hours(short))
        texts[k] = text
    q.texts = tuple(texts)


_say_boss_hours()


def player_texts(row, originals=None):
    """The four texts of a row as the client will show them, keyed by
    TEXT_KEYS: the original's laid over (_lay), the daily note and the
    skill goal on the start (_note), the boss hours filled in (_hours) --
    the steps the table goes through at load, on one row that need not be
    in it. What the quest editor previews. Raises what Quest raises."""
    import orig_texts
    q = Quest(row)
    _lay(q, orig_texts.quests() if originals is None else originals)
    _note(q)
    _hours(q)
    return dict(zip(TEXT_KEYS, q.texts))


def original_texts(quest_type, originals=None):
    """The original's own texts of a quest type (orig_texts.quests), the
    ones _lay puts over a row's unless own_texts keeps the row's: {} for a
    type the original never had."""
    import orig_texts
    originals = orig_texts.quests() if originals is None else originals
    return dict(originals.get(int(quest_type)) or {})


def get(quest_type):
    return QUESTS.get(int(quest_type))


def given_by(npc_type):
    """Types this NPC hands out, in table order: q_st;q_idx indexes this list."""
    return [q.type for q in QUESTS.values() if npc_type in q.give]


def taken_by(npc_type):
    return [q.type for q in QUESTS.values() if npc_type in q.take]


def repeatable_types():
    """The types the daily limit counts: repeatable ones only, so that the
    one-off quests of a chain -- the valley's tutorial is a dozen of them --
    are never held back by it; and of those not the services (service), a
    cashing or a lottery being no day's task. The ways are left out by the
    server, which knows them (server.py Session.counts_daily)."""
    return [q.type for q in QUESTS.values() if q.repeatable and not q.service]


def kept_on_death(type_id):
    """Whether a thing of this type stays on a dead player because a quest
    hands it over at the take (start_obj, START_OBJ_KEPT_ON_DEATH) -- or
    lends it, whatever the switch says -- or because one quest pays it and
    another asks for it and it is worth nothing away from them
    (STEP_REWARD_KEPT_ON_DEATH)."""
    t = int(type_id)
    if t in _LENT or (START_OBJ_KEPT_ON_DEATH and t in _HANDED):
        return True
    return STEP_REWARD_KEPT_ON_DEATH and t in _STEPS and _worthless(t)


def not_on_ground(type_id):
    """Whether a thing of this type may not be thrown on the ground because
    a quest hands it over at the take (start_obj, START_OBJ_NOT_ON_GROUND),
    or lends it, whatever the switch says -- whoever has it, and however it
    came: Ян Дуглас's notes out of his bag are 41's notes too."""
    t = int(type_id)
    return t in _LENT or (START_OBJ_NOT_ON_GROUND and t in _HANDED)


def lent(type_id):
    """Whether some quest lends a thing of this type (the docstring's lent):
    its frame carries the quest flag and no exchange (items.static_info)."""
    return int(type_id) in _LENT


def lends_consumables(quest):
    """Whether the quest lends something used up by its use -- rounds, a
    medicine (items.AMMO, items.HEAL): lent once a day (the docstring's
    lent). Use it, drop the quest, take it again was a free supply; so the
    day it lent, the quest is not offered again (server.py Session.
    quest_available) -- unless it was dropped with all of it back, nothing
    used (Session.cmd_q_ca), or all of it was taken back on leaving where
    it stays (stay_in, Session.keep_lent)."""
    if not quest.lent:
        return False
    import items                       # late: see check_items
    return any(items.root_of(t) in (items.AMMO, items.HEAL) for t in quest.lent)


def quest_drops(mob_type):
    """[(type, chance)] of the slots that name this creature with a drop
    (the docstring): the thing it drops for a quest that asks for it, the
    highest chance where two slots name the same (mobs.quest_table)."""
    got = {}
    for q in QUESTS.values():
        for mob, obj, chance in q.drops:
            if mob == int(mob_type):
                got[obj] = max(chance, got.get(obj, 0.0))
    return sorted(got.items())


def drop_group(type_id):
    """The group a slot's drop of this thing falls one of ("one_of", the
    docstring), or None."""
    return _ONE_OF.get(int(type_id))


def _worthless(type_id):
    """No stall pays for it and it changes no hands: no price, no exchange
    (asked late, at a death: items imports this module)."""
    import items                       # late: see check_items
    si = items.params_of(type_id) or {}
    return not si.get("cost", 0) and not si.get("exchang")


_HANDED = frozenset(obj for q in QUESTS.values() for obj, _n in q.start_obj)
_LENT = frozenset(t for q in QUESTS.values() for t in q.lent)
_ONE_OF = {t: g for q in QUESTS.values() for t, g in q.drop_groups.items()}
# Whether any row has a fee: the server looks at the journal on a change of
# purse only then (server.py Session.fee_recount).
HAS_FEES = any(q.has_fee for q in QUESTS.values())
# Paid by one quest (the one chosen, or beside it) and asked for by another.
_STEPS = frozenset(
    {t for q in QUESTS.values() for t in q.rew_obj}
    | {t for q in QUESTS.values() for t, _n in q.rew_also}) & frozenset(
    t for q in QUESTS.values() for t, _n in q.wants())


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
        if not quest or quest.kind != KILL_MOBS:
            continue
        counted = quest.kill_also.get(mob_type, mob_type)
        if counted not in quest.mobs_kill:
            continue
        progress = json.loads(row["progress_json"])
        kill_num = list(progress.get("kill_num", [0] * len(quest.mobs_kill)))
        kill_num += [0] * (len(quest.mobs_kill) - len(kill_num))
        moved = False
        for i, wanted in enumerate(quest.mobs_kill):
            if wanted == counted and kill_num[i] < quest.num_kill[i]:
                kill_num[i] += 1
                moved = True
        if not moved:
            continue
        progress["kill_num"] = kill_num
        complete = quest.is_complete(progress)
        store.update_quest(row["q_id"], progress, complete)
        out.append(quest.di_frame(row["q_id"], progress, complete))
    return out


def wanted_things(store, char_id, have):
    """The types an open instance in this character's log asks for (Quest.
    wants: a slot of a quest that asks for things, the thing a delivery
    carries) and the bag (have: type -> pieces, Inventory.bag_pieces) holds
    fewer of than it asks. What a creature's quest rows of loot may drop
    for him (mobs.QUEST_TIER): nothing once he has enough."""
    out = set()
    for row in store.quests(char_id):
        quest = get(row["type"])
        if quest is None:
            continue
        for obj, num in quest.wants():
            if int(have.get(obj, 0)) < num:
                out.add(obj)
    return out


def recount(quest, progress, have):
    """(progress, moved): the progress of an instance the bag decides
    (Quest.counts_bag) against the bag as it is (have: type -> pieces), and
    whether that changed it."""
    counted = quest.bag_progress(have)
    if all(progress.get(k) == v for k, v in counted.items()):
        return progress, False
    return dict(progress, **counted), True


def bring_progress(store, char_id, have):
    """The bag changed: every instance in the log the bag decides
    (Quest.counts_bag) against what it holds now (have: type -> pieces).

    Returns the q_di_* frames to push, one per instance whose count moved,
    having stored each. BringObjQuest.update reads obj_num against what it
    holds and prints "Найдено N <имя>" -- or the loss of one -- for the
    slot that changed; DeliverObjQuest takes obj as found or not, and the
    client says «Получен предмет <имя> для задания» either way
    (LocationInterface.delObject does not look at the flag). The hand-in
    button waits for complete=1 (QuestInterface.openDescription), so a
    count the server does not push leaves a quest that cannot be handed
    in, or one that shows a hand-in the bag no longer covers -- which the
    hand-in counts again anyway (server.py Session.cmd_q_co).
    """
    out = []
    for row in store.quests(char_id):
        quest = get(row["type"])
        if not quest or not quest.counts_bag:
            continue
        progress, moved = recount(quest, json.loads(row["progress_json"]), have)
        if not moved:
            continue
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
