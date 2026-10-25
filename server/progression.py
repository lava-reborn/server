"""The character's numbers: attributes, skills, specialisations, and what follows.

The client keeps none of this. PersAttributes is a mirror filled by one
rp_info frame, and it asks for that frame exactly once per session
(PersAttributes.requestAttributes sets firstLoad and never sends again), so
every later change has to be pushed by the server unasked or the card and the
"+N опыта" messages stay frozen. What follows on screen -- HP, stamina, action
points, carried weight, armour -- is not stored either: the formulas here are
the ones the wiki page "Игромеханика" (the developers' own design document)
gives, checked against "Таблица опыта", and the card's own arithmetic in
gpui/CharInterface.as is reproduced verbatim so that the server's combat
numbers agree with what the player is shown.

There are no free points to distribute. Attributes grow with specialisations,
constitution with the best skill, skills and specialisations with experience
for actions. The player's only choice is which specialisations to buy from a
teacher, and that is the one part of this that has a command today.
"""
import os
import time

ATTRIBS = 5    # сила, ловкость, телосложение, восприятие, интеллект
SKILLS = 5     # ближний бой, стрельба, медицина, промышленность, производство
SPECS = 15

STRENGTH, AGILITY, CONSTITUTION, PERCEPTION, INTELLECT = range(ATTRIBS)
MELEE, SHOOTING, MEDICINE, INDUSTRY, PRODUCTION = range(SKILLS)

# Which skill each specialisation belongs to: PersAttributes.specMatrix.
SPEC_SKILL = [0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 4]

# Which attribute a specialisation raises by one per level, from the wiki
# tables "Связи специализаций с атрибутами" and res/xmldocs/spec.xml. The
# three production specialisations raise nothing, and cannot be reached from
# the teacher's window anyway: it builds four slides and skill 4 has none.
SPEC_ATTRIB = [STRENGTH, AGILITY, PERCEPTION, STRENGTH, AGILITY, PERCEPTION,
               STRENGTH, AGILITY, INTELLECT, AGILITY, PERCEPTION, AGILITY,
               None, None, None]

# What the bars are made of (Character.hp_max, sp_max). A change to any of
# them moves a maximum that only usrUp carries -- rp_info has no health or
# stamina -- and a level is one of them: it moves constitution, which
# gain_xp and set_skill report among the attributes.
VITAL_ATTRIBS = frozenset((STRENGTH, AGILITY, CONSTITUTION))


def moves_vitals(changed):
    """Whether the indexes gain_xp, set_skill or set_spec say they changed
    move a bar's maximum, so that usrUp has to follow the rp_info: a level,
    or a specialisation of strength or agility (four hit points or four of
    stamina a level of it)."""
    return bool(changed["attribs"] & VITAL_ATTRIBS)

# The skill level a specialisation needs, PersAttributes.as:111-125. The
# client stores this table and never checks it: the teacher's window reads
# minSkill out of spec.xml instead, where the original says 0 for every entry
# -- the window then offered «Изучить» under «не ниже 0» and the server said
# no. The release ships spec.xml with this table in it
# (client/files/xmldocs/spec.xml, test_progression keeps the two equal), so
# the window shows the real figure in red and hides the button, and the gate
# here stays for a client without it.
SPEC_MIN_SKILL = [0, 0, 0, 4, 12, 6, 16, 8, 0, 0, 0, 0, 0, 0, 0]

# The skills as the teacher's window names them («Требует навык "Стрельбы"
# не ниже 8»): PersAttributes.as:72-85.
SKILL_TITLES = ["Ближнего боя", "Стрельбы", "Медицины", "Промышленность", "Производство"]
# And as a line about them reads: the admin queue's answers, /skill.
SKILL_NAMES = ("ближний бой", "стрельба", "медицина", "промышленность", "производство")
# The specialisations as the card names them (PersAttributes.as:87-125).
SPEC_TITLES = ("Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы",
               "Винтовки", "Ручные пулеметы", "Пистолет-пулеметы", "Хирургия",
               "Первая помощь", "Добыча", "Переработка", "Мастер свинца",
               "Мастер селитры", "Мастер меди")

# Specialisations 12-14 belong to the hidden fifth skill; a teacher does not
# offer them and the server does not hand them out.
LEARNABLE = frozenset(range(12))

SKILL_MAX = 20
SPEC_MAX = 5
ATTRIB_MAX = 20                 # wiki: an attribute without gear stays <= 20
START_ATTRIB = 5
# Settable so an integration suite can afford the gear its scenario needs;
# a player still starts with the thousand.
START_AFRO = int(os.environ.get("LAVA_START_AFRO", "1000"))
SKILL_XP_START = 100
SPEC_XP_START = 1250

# Session type the client opens with a teacher: StuffManager.SESSION_TRAINING.
SESSION_TRAINING = 4
# ss_upd codes inside that session: Training.UPD_CLOSE / UPD_FORGET / UPD_LEARN.
UPD_CLOSE, UPD_FORGET, UPD_LEARN = 0, 1, 2

# Refusal codes for cmdAck. ErrorReport.as turns some of them into an alert of
# its own, so the ones with a fitting text are reused and the rest are picked
# from the gap in its table, where the client shows nothing and the server
# says it in chat instead.
ERR_TOO_FAR = 8         # "Невозможно пройти"
ERR_NOT_FOUND = 12      # "Объект не найден"
ERR_MONEY = 20          # no client text
ERR_STATE = 21          # no client text: already learned, not learned, hidden
ERR_SKILL = 45          # "У вас не хватает навыков для использования этого предмета."

# Cost of one more specialisation once the free ones are used up, by the
# number already learned: Training.getCost, which is also what the window
# prints next to the button. (afro, gold)
# Training.getCost names the price of the next specialisation: free while
# fewer than max_specs are learned, then 1000 afro, then 10, 30, 55 and 75
# gold. Those gold figures are WHOLE OUNCES -- TrainingInterface prints the
# number as it comes and MoneyPan shows a purse as floor(gold/100) ounces and
# gold%100 on top -- while the purse itself is kept in hundredths, the unit
# every frame carries. So a price of 10 is 1000 in the purse; charging 10
# took a hundredth of what the window asked for.
GOLD_OUNCE = 100

# The one rate of gold to afro, afro per WHOLE ounce: what the constants
# frame tells the client (gold_to_afro_rate, «G 1 = A <rate>» in
# GoldToAfroInterface), what c_ga converts at (server.py Session.cmd_c_ga),
# what the auction sorts mixed currencies by (auction.py), what a stall pays
# for a thing priced in gold alone (inventory.Inventory.sell) and what a gold
# ingot is worth in afro (items.GOLD_INGOTS). 50 000 (owner, 2026-09-28: «как
# минимум 1 к 40к», derived from the original's prices): where the original
# converts one currency into the other it asks 40 000-50 000 -- the wiki's
# «официальный курс 1 голд – 40000 афро», the gold coin at 40 000, the
# set-upgrade surcharges (706 of 756 rows at 40 000), «Купить золото»
# (texts 49828: 500 000 afro for 10 ounces), the reagents (8 of 8 at
# 50 000) -- and a G twin is better than its afro one (damage x1.2, effect
# x1.14-1.2), which puts the ounce above the bare ratio: the consumable
# pairs corrected for effect meet at 50 000. The G columns of the gear
# price lists (4000 to the ounce in data/sets.json and the wiki's wear and
# blueprints) are a price ladder, not a rate. Change it here and nowhere
# else.
GOLD_TO_AFRO_RATE = 50000

SPEC_COST = {0: (0, 0), 1: (1000, 0), 2: (0, 10 * GOLD_OUNCE),
             3: (0, 30 * GOLD_OUNCE), 4: (0, 55 * GOLD_OUNCE)}
SPEC_COST_MAX = (0, 75 * GOLD_OUNCE)

# Premium ("вид на жительство" 1, "гражданство" 2) bonuses are shares b of the
# base: the client is handed the total v and splits it back as
# bonus = round(v*b/(1+b)) (SpecSkillMessages.getRealAndBonus for experience,
# WeightPan.calcMaxWeight for weight). The shares themselves are not in the
# client and not on the wiki; a quarter and a half are this server's choice.
PREMIUM_XP_BONUS = {0: 0.0, 1: 0.25, 2: 0.5}
PREMIUM_WEIGHT_BONUS = {0: 0.0, 1: 0.25, 2: 0.5}

# Fighter reputation: ReputationObject.rank_level. The last range ends at
# 25600, and a value at or past it matches no range at all, after which
# repString prints garbage and the rank frame is undefined, so the server
# never lets it get there.
RANKS = [(0, 100, "Странник"), (100, 200, "Следопыт"), (200, 400, "Охотник"),
         (400, 800, "Преследователь"), (800, 1600, "Налетчик"),
         (1600, 3200, "Стрелок"), (3200, 6400, "Пустынный рейнджер"),
         (6400, 12800, "Мститель"), (12800, 25600, "Ассасин")]
REP_CAP = RANKS[-1][1] - 1

# Action points regained per 600 ms tick (APManager.dt) while in combat. The
# original's value did not survive; one point a tick is a placeholder. Sent
# as lenter;aspd and applied by combat.py on the same clock; LAVA_AP_REGEN
# lets a test fight without waiting for the bar.
AP_REGEN = int(os.environ.get("LAVA_AP_REGEN", "1"))

# FireArm.as weapon types, the key the card's crit formula switches on.
PISTOL, SHOTGUN, ASSAULT, RIFLE, MACHINEGUN, SMG = range(6)


def skill_xp_max(level):
    """Experience to leave this skill level: 100 doubling each level (wiki)."""
    return SKILL_XP_START << level


def spec_xp_max(level):
    """Experience to leave this specialisation level: 1250 * 8^level (wiki)."""
    return SPEC_XP_START * (8 ** level)


def starting_rows():
    """char_stats rows for a character just created.

    "Таблица опыта" row "Уровень 1" is the newborn: attributes 5 across,
    skills at 0 with 100 to go, specialisations switched off (-1, wiki
    "Специализации" p.1) with the first threshold waiting.
    """
    rows = [("attrib", i, START_ATTRIB, 0, 0) for i in range(ATTRIBS)]
    rows += [("skill", i, 0, 0, SKILL_XP_START) for i in range(SKILLS)]
    rows += [("spec", i, -1, 0, SPEC_XP_START) for i in range(SPECS)]
    return rows


def packed(values, idxs, n):
    """Mask plus dense list, the way PersAttributes.updateParam reads it.

    The list holds values only for the bits set in the mask, in index order:
    the client walks i over 0..n-1 and takes the next list element whenever
    bit i is set. A full list with a partial mask would misalign silently.
    """
    mask, out = 0, []
    for i in range(n):
        if i in idxs:
            mask |= 1 << i
            out.append(values[i])
    return mask, out


def hex_neighbours(cell, width, height):
    """The six cells around one, as LocationGrid.getSiblings counts them.

    Rows are offset: an even row leans on the column to its left, an odd row
    on the one to its right, which is what 2*(gy%2)-1 picks.
    """
    gx, gy = cell % width, cell // width
    d = 2 * (gy % 2) - 1
    around = [(gx - 1, gy), (gx + 1, gy), (gx, gy - 1), (gx, gy + 1),
              (gx + d, gy + 1), (gx + d, gy - 1)]
    return [y * width + x for x, y in around
            if 0 <= x < width and 0 <= y < height]


def within_reach(a, b, width, height):
    """Same cell or adjacent: what Gamer.proposeContact demands before it
    opens a session, so the server asks for no less."""
    return a == b or b in hex_neighbours(a, width, height)


class Character:
    """One character's progression, loaded from and saved to the Store.

    Base values live in the lists; everything derived is computed on demand
    so it can never drift from them. Bonuses are kept apart because the
    client shows a_* and f_* separately and the card's formulas use the f_*
    ones. Today they are the gear's alone -- what is worn and held, and the
    sets among it -- recounted by inventory.gear_bonus and handed over with
    set_gear; effects do not exist yet. They are never saved: the items are,
    and the next load counts them again.
    """

    def __init__(self):
        self.char_id = None
        self.name = ""
        self.attrib = [START_ATTRIB] * ATTRIBS
        self.skill = [[0, 0, SKILL_XP_START] for _ in range(SKILLS)]   # lvl, xp, xp_max
        self.spec = [[-1, 0, SPEC_XP_START] for _ in range(SPECS)]     # lvl, xp, xp_max
        self.hp = None            # None: full
        self.sp = None
        self.afro = START_AFRO
        self.gold = 0
        self.premium = 0
        self.premium_until = None
        self.rep = 0
        self.bg_rep = 0
        self.bg_pen = 0
        self.max_specs = 1        # free specialisations; wiki: the first is free
        # skill -> the fraction of a point hits on mobs left over
        # (carry_xp); a session's worth at most, never saved
        self.xp_carry = {}
        self.bonus_attribs = [0] * ATTRIBS
        self.bonus_skills = [0] * SKILLS
        self.bonus_specs = [0] * SPECS
        # health, stamina, action points, crit and anti-crit from the gear
        self.bonus_hp = 0
        self.bonus_st = 0
        self.bonus_od = 0
        self.bonus_cp = 0
        self.bonus_ce = 0
        # crit and anti-crit the card counts a second time for a firearm
        # (inventory.card_repeat): crit_chance adds them, melee does not
        self.card_cp = 0
        self.card_ce = 0

    # --- persistence -----------------------------------------------------
    @classmethod
    def load(cls, store, char_id):
        row = store.character(char_id)
        if row is None:
            raise KeyError("no character %r" % char_id)
        ch = cls()
        ch.char_id = char_id
        ch.name = row["name"]
        for r in store.load_stats(char_id):
            kind, idx = r["kind"], r["idx"]
            if kind == "attrib" and idx < ATTRIBS:
                ch.attrib[idx] = r["value"]
            elif kind == "skill" and idx < SKILLS:
                ch.skill[idx] = [r["value"], r["xp"], r["xp_max"]]
            elif kind == "spec" and idx < SPECS:
                ch.spec[idx] = [r["value"], r["xp"], r["xp_max"]]
        ch.hp, ch.sp = row["hp"], row["sp"]
        ch.afro, ch.gold = row["afro"], row["gold"]
        ch.premium, ch.premium_until = row["premium"], row["premium_until"]
        ch.set_rep(row["rep"])
        ch.bg_rep, ch.bg_pen = row["bg_rep"], row["bg_pen"]
        ch.max_specs = row["max_specs"]
        ch.recalc()
        return ch

    def rows(self):
        out = [("attrib", i, self.attrib[i], 0, 0) for i in range(ATTRIBS)]
        out += [("skill", i, s[0], s[1], s[2]) for i, s in enumerate(self.skill)]
        out += [("spec", i, s[0], s[1], s[2]) for i, s in enumerate(self.spec)]
        return out

    def save(self, store):
        if self.char_id is None:
            return
        store.save_stats(self.char_id, self.rows())
        store.save_character_state(
            self.char_id, hp=self.hp, sp=self.sp, afro=self.afro,
            gold=self.gold, premium=self.premium,
            premium_until=self.premium_until, rep=self.rep,
            bg_rep=self.bg_rep, bg_pen=self.bg_pen, max_specs=self.max_specs,
            level=self.level)

    # --- derived ---------------------------------------------------------
    @property
    def level(self):
        """The character has no level of its own: it is the best skill
        (wiki "Уровень персонажа", PersAttributes.getLevel)."""
        return max(s[0] for s in self.skill)

    def recalc(self):
        """Constitution follows the best skill (wiki "Прокачка телосложения")
        and is the one attribute no specialisation feeds, so it is rewritten
        from the formula rather than accumulated."""
        self.attrib[CONSTITUTION] = int(5 + 0.75 * self.level)

    def attr(self, i):
        """Attribute with bonuses: what the card's formulas call .level."""
        return self.attrib[i] + self.bonus_attribs[i]

    def skill_level(self, i):
        return self.skill[i][0] + self.bonus_skills[i]

    def spec_level(self, i):
        """-1 for an unlearned specialisation, as SpecObject.level returns it:
        the card's formulas subtract that one honestly."""
        lvl = self.spec[i][0]
        return lvl + self.bonus_specs[i] if lvl >= 0 else -1

    @property
    def hp_max(self):
        """The gear's health on top: the client adds it nowhere by itself,
        so the maximum usrUp carries has to hold it already."""
        return 4 * self.attr(STRENGTH) + 20 * self.attr(CONSTITUTION) + self.bonus_hp

    @property
    def sp_max(self):
        return 4 * self.attr(AGILITY) + 20 * self.attr(CONSTITUTION) + self.bonus_st

    @property
    def ap_max(self):
        """Without item, set or effect bonuses: the card adds those itself
        (CharInterface.showOD), so putting them here would count them twice.
        This is the figure for rp_info and nothing else; see ap_ceiling."""
        return 50 + 5 * self.level

    @property
    def ap_ceiling(self):
        """The ОД the card shows: ap_max plus the bonus_od of everything
        worn and held and the od of every set (showOD). The bar is filled
        to this -- lenter;amax is its only source (APManager.setAP) -- and
        the fight spends from it, so what the player reads is what he has."""
        return self.ap_max + self.bonus_od

    def set_gear(self, b, repeat=(0, 0)):
        """Take on what the gear adds, in inventory.gear_bonus's shape, and
        the (crit, anti-crit) the card repeats (inventory.card_repeat).

        Returns the indexes whose card value moved, as gain_xp does, ready
        for a partial rp_info. Only a change is worth pushing: SkillObject
        and SpecObject announce every new value_bonus as "повышен до N".
        """
        self.card_cp, self.card_ce = repeat
        changed = {"attribs": set(), "skills": set(), "specs": set()}
        for kind, have in (("attribs", self.bonus_attribs), ("skills", self.bonus_skills),
                           ("specs", self.bonus_specs)):
            for i, value in enumerate(b[kind]):
                if have[i] != value:
                    have[i] = value
                    changed[kind].add(i)
        self.bonus_hp, self.bonus_st = b["hp"], b["st"]
        self.bonus_od, self.bonus_cp, self.bonus_ce = b["od"], b["cp"], b["ce"]
        return changed

    @property
    def armor(self):
        """The card's own base (CharInterface.showArmorLevel), which divides
        by 4 where the wiki divides by 2. The player sees the card."""
        return (3 * self.attr(AGILITY) + self.attr(PERCEPTION)) / 4

    def premium_level(self):
        if self.premium and self.premium_until is not None \
                and self.premium_until <= time.time():
            return 0
        return self.premium or 0

    def max_weight(self):
        """Grams, premium included: WeightPan divides by 1000 and takes the
        premium share back out of this figure to print "+N кг"."""
        base = (30 + 2 * self.attr(STRENGTH)) * 1000
        return int(round(base * (1 + PREMIUM_WEIGHT_BONUS[self.premium_level()])))

    def vitals(self):
        """usrUp payload. Entity.userUpdate assigns hmax before hcur, so a
        raised maximum arrives before the value it has to hold."""
        hp = self.hp_max if self.hp is None else max(0, min(self.hp, self.hp_max))
        sp = self.sp_max if self.sp is None else max(0, min(self.sp, self.sp_max))
        return dict(hcur=hp, hmax=self.hp_max, scur=sp, smax=self.sp_max)

    # --- the rp_info frame -----------------------------------------------
    def rp_info(self, attribs=None, skills=None, specs=None):
        """Parameters of one rp_info frame, full or partial.

        Each group is a mask plus the values for the set bits only (§1.7).
        A group left out of a partial push is sent as mask 0 with an empty
        list, which updateParam walks without assigning anything.

        HP and stamina are deliberately absent. PersAttributes.rp_info
        assigns hp before hp_max, and the health setter clamps against the
        old maximum, so a level-up pushed here would cut the current HP down
        to the previous ceiling. usrUp assigns them in the right order.

        Scalars are guarded by if(param) on the client, so a zero is the
        same as leaving it out; lvl 0 is what a newborn has and userInfo has
        already told the client, whose level setter does accept 0.
        """
        attribs = set(range(ATTRIBS)) if attribs is None else set(attribs)
        skills = set(range(SKILLS)) if skills is None else set(skills)
        specs = set(range(SPECS)) if specs is None else set(specs)
        f_attribs = [self.attr(i) for i in range(ATTRIBS)]
        f_skills = [self.skill_level(i) for i in range(SKILLS)]
        # value_bonus of an unlearned specialisation is sent as 0, not -1:
        # SpecObject starts it at 0 and its setter announces every change as
        # "повышена до N", so -1 would greet the first card with fifteen of
        # those. Its level getter returns value (-1) while value < 0 anyway.
        f_specs = [max(self.spec_level(i), 0) for i in range(SPECS)]
        p = {}
        p["a_attribs_mask"], p["a_attribs"] = packed(self.attrib, attribs, ATTRIBS)
        p["f_attribs_mask"], p["f_attribs"] = packed(f_attribs, attribs, ATTRIBS)
        p["a_skills_mask"], p["a_skills"] = packed(
            [s[0] for s in self.skill], skills, SKILLS)
        p["f_skills_mask"], p["f_skills"] = packed(f_skills, skills, SKILLS)
        p["xp_skills_mask"], p["xp_skills"] = packed(
            [s[1] for s in self.skill], skills, SKILLS)
        p["xp_max_skills_mask"], p["xp_max_skills"] = packed(
            [s[2] for s in self.skill], skills, SKILLS)
        p["a_specs_mask"], p["a_specs"] = packed(
            [s[0] for s in self.spec], specs, SPECS)
        p["f_specs_mask"], p["f_specs"] = packed(f_specs, specs, SPECS)
        p["xp_specs_mask"], p["xp_specs"] = packed(
            [s[1] for s in self.spec], specs, SPECS)
        p["xp_max_specs_mask"], p["xp_max_specs"] = packed(
            [s[2] for s in self.spec], specs, SPECS)
        p.update(max_specs=self.max_specs, ap_max=self.ap_max,
                 max_weight=self.max_weight(), armor=int(self.armor),
                 lvl=self.level)
        return p

    def player_info(self):
        """The progression part of userInfo_Player. rep is a list read at
        index 0 (PersReputations.updateReputations); afro and gold arrive
        only here, which is why a purchase re-sends the whole frame."""
        return dict(lvl=self.level, rep=[self.rep], bg_rep=self.bg_rep,
                    bg_pen=self.bg_pen, pr=self.premium_level(),
                    afro=self.afro, gold=self.gold)

    # --- money -----------------------------------------------------------
    def can_afford(self, afro=0, gold=0):
        return self.afro >= afro and self.gold >= gold

    def add_money(self, afro=0, gold=0):
        self.afro = max(0, self.afro + afro)
        self.gold = max(0, self.gold + gold)

    # --- reputation ------------------------------------------------------
    def set_rep(self, value):
        self.rep = max(0, min(int(value or 0), REP_CAP))

    def add_rep(self, delta):
        self.set_rep(self.rep + delta)

    def rank(self):
        """Index into RANKS, the frame of the skull drawn beside the level."""
        for i, (lo, hi, _title) in enumerate(RANKS):
            if lo <= self.rep < hi:
                return i
        return len(RANKS) - 1

    # --- teacher ---------------------------------------------------------
    def specs_learned(self):
        return sum(1 for s in self.spec if s[0] >= 0)

    def spec_cost(self):
        """(afro, gold) for the next specialisation: Training.getCost."""
        n = self.specs_learned()
        if n < self.max_specs:
            return (0, 0)
        return SPEC_COST.get(n, SPEC_COST_MAX)

    def learn_spec(self, idx):
        """Buy a specialisation. Returns 0, or a cmdAck refusal code.

        The client checks neither the skill requirement nor the money
        (Training.learn sends the request and its ack handler is empty), so
        both gates live here.
        """
        if idx not in LEARNABLE:
            return ERR_STATE
        if self.spec[idx][0] >= 0:
            return ERR_STATE
        # The skill with the gear's bonus, as the window compares it
        # (SkillObject.level is value_bonus): a button it shows is one the
        # server takes.
        if self.skill_level(SPEC_SKILL[idx]) < SPEC_MIN_SKILL[idx]:
            return ERR_SKILL
        afro, gold = self.spec_cost()
        if not self.can_afford(afro, gold):
            return ERR_MONEY
        self.add_money(-afro, -gold)
        self.spec[idx] = [0, 0, SPEC_XP_START]
        return 0

    def forget_spec(self, idx):
        """Reset a specialisation (wiki "Механизм сброса специализации"):
        its attribute drops by its level, it goes back to -1 with the first
        threshold, and nothing is refunded."""
        if idx >= SPECS or self.spec[idx][0] < 0:
            return ERR_STATE
        lvl = self.spec[idx][0]
        a = SPEC_ATTRIB[idx]
        if a is not None:
            # Never below the birth value: a raise that the cap of 20 refused
            # was never added, so it cannot be taken away either.
            self.attrib[a] = max(START_ATTRIB, self.attrib[a] - lvl)
        self.spec[idx] = [-1, 0, SPEC_XP_START]
        return 0

    # --- experience ------------------------------------------------------
    def carry_xp(self, skill_idx, xp):
        """The whole points of `xp`, this skill's leftover fraction added in;
        the new fraction waits for the next hit. A kill arrives as several
        hits and each is a share of a 20-point price, so flooring every hit
        on its own would lose a good part of the reward."""
        xp += self.xp_carry.get(skill_idx, 0.0)
        whole = int(xp + 1e-9)
        self.xp_carry[skill_idx] = max(0.0, xp - whole)
        return whole

    def gain_xp(self, skill_idx, base, spec_idx=None, spec_on_top=False):
        """Award experience for an action. Returns the indexes changed, as
        {"skills": set, "specs": set, "attribs": set}, ready for a push.

        The client is handed the total and splits the premium share back
        out for its message, so the total is base * (1 + share). Half goes
        to the skill and half to the specialisation (wiki "Начисление опыта
        по мобу"); the remainder past a threshold carries into the next
        level. An attribute gains one per specialisation level up to 20.

        spec_on_top: the skill takes the whole total and a learned
        specialisation the same again. Mob kills use it, so that opening a
        specialisation does not halve the pace mob_xp is built around;
        healing keeps the wiki's halves.
        """
        total = int(base * (1 + PREMIUM_XP_BONUS[self.premium_level()]))
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        if total <= 0:
            return changed
        spec_on = spec_idx is not None and self.spec[spec_idx][0] >= 0
        if spec_on_top:
            to_skill, to_spec = total, (total if spec_on else 0)
        else:
            to_spec = total // 2 if spec_on else 0
            to_skill = total - to_spec
        old_level = self.level
        self._skill_up(skill_idx, to_skill, changed)
        if to_spec:
            self._spec_up(spec_idx, to_spec, changed)
        if self.level != old_level:
            self.recalc()
            changed["attribs"].add(CONSTITUTION)
        return changed

    def add_skill_xp(self, skill_idx, xp):
        """xp into the skill as it is, either way -- no premium share, no
        specialisation half: the admin queue's 'xp' (admin_edit), an amount
        the owner names. Given, levels carry over as gain_xp's do; taken,
        they go back the same way, down to level 0 with nothing. Returns
        the indexes changed, as gain_xp does."""
        if not 0 <= skill_idx < SKILLS:
            raise ValueError("skill index")
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        old_level = self.level
        if int(xp) >= 0:
            self._skill_up(skill_idx, int(xp), changed)
        else:
            self._skill_down(skill_idx, -int(xp), changed)
        if self.level != old_level:
            self.recalc()
            changed["attribs"].add(CONSTITUTION)
        return changed

    def _skill_down(self, skill_idx, xp, changed):
        """xp out of a skill: past what this level holds, the level before it
        with its bar full, and so on. Level n with nothing is level n-1 with
        its bar full, so taking back what was given lands where it began."""
        s = self.skill[skill_idx]
        while xp > 0:
            if xp <= s[1]:
                s[1] -= xp
                break
            if s[0] == 0:
                s[1] = 0
                break
            xp -= s[1]
            s[0] -= 1
            s[2] = s[1] = skill_xp_max(s[0])
        changed["skills"].add(skill_idx)

    def add_spec_xp(self, spec_idx, xp):
        """xp into a learned specialisation as it is, either way: its levels
        and its attribute go up and back down with it (one point a level,
        as _spec_up and set_spec move it). Taking never unlearns it -- level
        0 with nothing is the floor; set_spec(-1) forgets. Returns the
        indexes changed, as gain_xp does."""
        if not 0 <= spec_idx < SPECS or self.spec[spec_idx][0] < 0:
            raise ValueError("spec not learned")
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        if int(xp) >= 0:
            self._spec_up(spec_idx, int(xp), changed)
            return changed
        sp, xp, a = self.spec[spec_idx], -int(xp), SPEC_ATTRIB[spec_idx]
        while xp > 0:
            if xp <= sp[1]:
                sp[1] -= xp
                break
            if sp[0] == 0:
                sp[1] = 0
                break
            xp -= sp[1]
            sp[0] -= 1
            sp[2] = sp[1] = spec_xp_max(sp[0])
            if a is not None and self.attrib[a] > START_ATTRIB:
                self.attrib[a] -= 1
                changed["attribs"].add(a)
        changed["specs"].add(spec_idx)
        return changed

    def _skill_up(self, skill_idx, xp, changed):
        """xp into a skill and its levels, the remainder past a threshold
        carried into the next."""
        s = self.skill[skill_idx]
        s[1] += xp
        while s[0] < SKILL_MAX and s[1] >= s[2]:
            s[1] -= s[2]
            s[0] += 1
            s[2] = skill_xp_max(s[0])
        if s[0] >= SKILL_MAX:
            s[1] = min(s[1], s[2])
        changed["skills"].add(skill_idx)

    def gain_spec_xp(self, spec_idx, base):
        """Experience into a specialisation alone, none into its skill: a
        quest's rew_spec_xp (the wiki's «опыт спецу», «требуется открытая
        специализация»). The premium share on top, as gain_xp's. A
        specialisation not learned takes nothing. Returns the indexes
        changed, as gain_xp does."""
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        total = int(base * (1 + PREMIUM_XP_BONUS[self.premium_level()]))
        if total > 0 and 0 <= spec_idx < SPECS and self.spec[spec_idx][0] >= 0:
            self._spec_up(spec_idx, total, changed)
        return changed

    def _spec_up(self, spec_idx, xp, changed):
        """xp into a learned specialisation, its levels and its attribute."""
        sp = self.spec[spec_idx]
        sp[1] += xp
        while sp[0] < SPEC_MAX and sp[1] >= sp[2]:
            sp[1] -= sp[2]
            sp[0] += 1
            sp[2] = spec_xp_max(sp[0])
            a = SPEC_ATTRIB[spec_idx]
            if a is not None and self.attrib[a] < ATTRIB_MAX:
                self.attrib[a] += 1
                changed["attribs"].add(a)
        if sp[0] >= SPEC_MAX:
            sp[1] = min(sp[1], sp[2])
        changed["specs"].add(spec_idx)

    # --- set outright, for a test run (server.py /skill, /spec) ---------------
    def set_skill(self, idx, level):
        """A skill put at a level, its experience at the level's start, with
        what a level-up carries: constitution follows the best skill. Returns
        the indexes changed, as gain_xp does."""
        if not 0 <= idx < SKILLS:
            raise ValueError("skill index")
        level = max(0, min(SKILL_MAX, int(level)))
        changed = {"skills": {idx}, "specs": set(), "attribs": set()}
        old_level = self.level
        self.skill[idx] = [level, 0, skill_xp_max(level)]
        if self.level != old_level:
            self.recalc()
            changed["attribs"].add(CONSTITUTION)
        return changed

    def set_spec(self, idx, level):
        """A specialisation put at a level, learned for nothing if it was
        not, with what its levels carry: one point of its attribute per
        level up (ATTRIB_MAX holds), one back per level down (START_ATTRIB
        holds, as forget_spec). -1 forgets it. Returns the indexes changed,
        as gain_xp does."""
        if not 0 <= idx < SPECS:
            raise ValueError("spec index")
        level = max(-1, min(SPEC_MAX, int(level)))
        changed = {"skills": set(), "specs": {idx}, "attribs": set()}
        if level < 0:
            if self.spec[idx][0] >= 0:
                self.forget_spec(idx)
                if SPEC_ATTRIB[idx] is not None:
                    changed["attribs"].add(SPEC_ATTRIB[idx])
            return changed
        old = max(0, self.spec[idx][0])
        a = SPEC_ATTRIB[idx]
        if a is not None and level != old:
            before = self.attrib[a]
            if level > old:
                self.attrib[a] = min(ATTRIB_MAX, before + (level - old))
            else:
                self.attrib[a] = max(START_ATTRIB, before - (old - level))
            if self.attrib[a] != before:
                changed["attribs"].add(a)
        self.spec[idx] = [level, 0, spec_xp_max(level)]
        return changed

    def admin_edit(self, kind, args):
        """The admin queue's 'xp' and 'stat' (server.py apply_admin_action),
        on this character wherever it is held:

          xp    {skill: i, xp: n} or {spec: i, xp: n}: n either way
                (add_skill_xp, add_spec_xp)
          stat  {skill: i, level: l, xp: n} or {spec: i, level: l, xp: n}:
                put there outright (set_skill, set_spec: -1 forgets a
                specialisation, a level on an unlearned one learns it),
                n within the level's bar

        Returns (changed, the state in words) -- or raises ValueError whose
        text starts «отказ:», what the panel reads as a refusal."""
        n = int(args.get("xp") or 0)
        if args.get("spec") is not None:
            idx = int(args["spec"])
            if idx not in LEARNABLE:
                raise ValueError("отказ: специализации %d нет" % idx)
            title = SPEC_TITLES[idx]
            if kind == "xp":
                if self.spec[idx][0] < 0:
                    raise ValueError("отказ: специализация «%s» не изучена" % title)
                changed = self.add_spec_xp(idx, n)
            else:
                changed = self.set_spec(idx, int(args["level"]))
                sp = self.spec[idx]
                if sp[0] >= 0:
                    sp[1] = max(0, min(n, sp[2] if sp[0] >= SPEC_MAX else sp[2] - 1))
            sp = self.spec[idx]
            state = "не изучена" if sp[0] < 0 else "%d (%d/%d)" % tuple(sp)
            return changed, "специализация «%s» %s" % (title, state)
        idx = int(args["skill"])
        if not 0 <= idx < SKILLS:
            raise ValueError("отказ: навыка %d нет" % idx)
        if kind == "xp":
            changed = self.add_skill_xp(idx, n)
        else:
            changed = self.set_skill(idx, int(args["level"]))
            s = self.skill[idx]
            s[1] = max(0, min(n, s[2] if s[0] >= SKILL_MAX else s[2] - 1))
        s = self.skill[idx]
        return changed, "%s %d (%d/%d)" % (SKILL_NAMES[idx], s[0], s[1], s[2])


# --- the card's formulas, CharInterface.as verbatim -------------------------
# These are what the player reads off the character card, so the combat
# resolver has to produce hits and crits at these rates rather than the
# wiki's, whose coefficients differ by a factor of two to eight.

def melee_evade(ch):
    """showMeleeEvade, line 64: agility + perception + melee skill + blades."""
    return (ch.attr(AGILITY) + ch.attr(PERCEPTION)
            + ch.skill_level(MELEE) + ch.spec_level(1))


def armor_class(ch, equipment_armor=0, effect_armor=0):
    """showArmorLevel, lines 73-114: the base above, plus armor_class over
    the six clothing slots, plus every effect's armor. Not rounded."""
    return ch.armor + equipment_armor + effect_armor


# (attribute, weight, attribute, weight, specialisation) per weapon type,
# showKrit lines 200-230: cp = (A*w + B*v)/4 + shooting/4 + spec.
_CRIT = {
    PISTOL: (AGILITY, 8, PERCEPTION, 4, 2),
    SHOTGUN: (STRENGTH, 6, PERCEPTION, 6, 3),
    ASSAULT: (AGILITY, 6, PERCEPTION, 6, 4),
    RIFLE: (AGILITY, 6, PERCEPTION, 6, 5),
    MACHINEGUN: (STRENGTH, 8, PERCEPTION, 4, 6),
    SMG: (AGILITY, 6, PERCEPTION, 4, 7),
}


def crit_chance(ch, weapon_type, card=True):
    """(crit %, anti-crit %) for a firearm of this type, showKrit 184-231,
    with the gear's bonus_cp/bonus_ce on top as showKrit adds them (the
    items in the eight slots, then the sets). Effects would come next; none
    exist. None for anything the card does not compute, which is every
    non-firearm.

    card: the set the card counts twice counted twice (Character.card_cp),
    for the firearm in hand, whose figure the player reads. False for a row
    the card never shows -- the anti-crit of somebody with no firearm."""
    row = _CRIT.get(weapon_type)
    if row is None:
        return None
    a, wa, b, wb, spec = row
    shooting = ch.skill_level(SHOOTING)
    sp = ch.spec_level(spec)
    cp = (ch.attr(a) * wa + ch.attr(b) * wb) / 4 + shooting / 4 + sp
    ce = (ch.attr(AGILITY) + ch.attr(PERCEPTION)) / 2 + shooting / 2 + sp
    if card:
        cp, ce = cp + ch.card_cp, ce + ch.card_ce
    return cp + ch.bonus_cp, ce + ch.bonus_ce


def level_gap(a, b):
    """PersAttributes.compareLevels: the difference clamped to +-4, which is
    both the frame over a mob's head and the wiki's experience multiplier
    minus four."""
    return max(-4, min(4, a - b))


# --- experience from mobs: the owner's rule (2026-09-24), not the original's --
# The original paid k * damage, k = clamp(mob - player, -4, 4) + 4, against
# thresholds that double from 100. The first colonist took a new character
# from Стрельба 0 straight to 2, while level 19 to 20 would have cost 34 500
# kills: the threshold doubles every level and a mob's health barely grows.
#
# The rule instead sets the pace in kills and prices a mob from it:
#
#   kills_per_level(L) = 5 * 1.5^L, rounded: 5, 8, 11, 17, 25, 38 ... 11 084
#                        mobs one level above the player, each level half as
#                        long again as the one before
#   mob_price(m)       = what a level-m mob pays a player one level below it,
#                        T(m - 1) / kills_per_level(m - 1) rounded up:
#                        20 for the colonist (level 1), 267 at 10, 4 731 at 20
#   by the gap:  mob above the player   the price (as one level up, no more)
#                same level             half
#                one level below        a quarter
#                two or more below      nothing
#
# At one's own level a level takes 10, 20, 32, 44, 67 ... 29 555 kills. Zero
# to twenty is some 33 000 kills of mobs above, 88 000 at one's own level.
# A growth of 2 instead would have made every mob worth the same 20 and the
# last level cost millions; 1.5 was chosen with the owner for that reason.
KILLS_START = 5
KILLS_GROWTH = 1.5
GAP_SHARE = {0: 0.5, -1: 0.25}
GREY_GAP = 2


def kills_per_level(level):
    """How many mobs one level above the player a level takes."""
    return max(1, round(KILLS_START * KILLS_GROWTH ** level))


def mob_price(mob_level):
    """What a mob of this level pays a player one level below it: the most
    one kill of it is ever worth. Levels 0 and 1 share the colonist's 20."""
    m = max(1, mob_level)
    return -(-skill_xp_max(m - 1) // kills_per_level(m - 1))


def mob_xp(mob_level, player_level, share=1.0, xp_mult=1):
    """Experience for `share` of a kill -- the part of the mob's health this
    player took -- as a float, so the caller can carry what a hit leaves
    over.

    A mob above the player is priced as one level up however far above it
    stands: kills_per_level is then a floor no lucky kill can beat, and one
    kill is never worth more than a fifth of a level. The mob's xp_mult
    counts once: a boss at 3.0 is three kills, an animal at 0.7 a little
    less than one.
    """
    gap = mob_level - player_level
    if gap > 0:
        return mob_price(player_level + 1) * share * xp_mult
    if gap <= -GREY_GAP:
        return 0.0
    return mob_price(mob_level) * GAP_SHARE[gap] * share * xp_mult


def combat_mob_xp(mob_level, skill_level, share=1.0, xp_mult=1):
    """Combat only: a trained skill at 17+ receives at most one XP per mob.

    Cap the whole kill after the mob multiplier, then apportion it between
    hits and death settlement. Capping each hit would pay once per hit.
    Keep zero-XP targets at zero and retain the lower-skill formula exactly.
    Mining and other experience sources continue using their existing rules.
    """
    if skill_level < 17:
        return mob_xp(mob_level, skill_level, share, xp_mult)
    return min(1.0, mob_xp(mob_level, skill_level, 1.0, xp_mult)) * share


# --- the fighter's skill from a kill of a player: DESIGNED ---------------------
# «Навык бойца» (rep, RANKS) has no source in anything that survived: the
# client only shows it and announces its rise, and the wiki leaves the article
# empty but for the thresholds. It is paid when the killer registers the
# trophy the kill left (trophies.Collection.register), over the two levels
# the trophy wrote down at the kill -- and a trophy falls only for a killer at
# the victim's level or below, so of the lines below only the first two are
# ever paid now. The owner's shape for mobs is reused, on a flat price,
# because the ranks are fixed numbers rather than a curve that grows with the
# level:
#
#   by the gap:  victim above the killer    the price
#                same level                 half
#                one level below            a quarter
#                two or more below          nothing
#
# At twenty a kill, Следопыт (100) is five kills of a stronger player or ten
# of an equal, Ассасин (12 800) 640 or 1 280 of them. Nothing for beating
# somebody two levels down keeps the newcomers from being anybody's rank.
PVP_REP_PRICE = 20


def pvp_rep(victim_level, killer_level):
    """Fighter's skill for killing a player of victim_level, whole points."""
    gap = victim_level - killer_level
    if gap > 0:
        return PVP_REP_PRICE
    if gap <= -GREY_GAP:
        return 0
    return int(PVP_REP_PRICE * GAP_SHARE[gap])
