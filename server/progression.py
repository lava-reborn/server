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

# The skill level a specialisation needs, PersAttributes.as:111-125. The
# client stores this table and never checks it: the teacher's window reads
# minSkill out of spec.xml instead, where every entry says 0. So the gate is
# the server's alone.
SPEC_MIN_SKILL = [0, 0, 0, 4, 12, 6, 16, 8, 0, 0, 0, 0, 0, 0, 0]

# Specialisations 12-14 belong to the hidden fifth skill; a teacher does not
# offer them and the server does not hand them out.
LEARNABLE = frozenset(range(12))

SKILL_MAX = 20
SPEC_MAX = 5
ATTRIB_MAX = 20                 # wiki: an attribute without gear stays <= 20
START_ATTRIB = 5
START_AFRO = 1000
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
    so it can never drift from them. Bonuses from equipment and effects are
    kept apart (all zero until those exist) because the client shows
    a_* and f_* separately and the card's formulas use the f_* ones.
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
        self.bonus_attribs = [0] * ATTRIBS
        self.bonus_skills = [0] * SKILLS
        self.bonus_specs = [0] * SPECS

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
        return 4 * self.attr(STRENGTH) + 20 * self.attr(CONSTITUTION)

    @property
    def sp_max(self):
        return 4 * self.attr(AGILITY) + 20 * self.attr(CONSTITUTION)

    @property
    def ap_max(self):
        """Without item, set or effect bonuses: the card adds those itself
        (CharInterface.showOD), so putting them here would count them twice."""
        return 50 + 5 * self.level

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
        if self.skill[SPEC_SKILL[idx]][0] < SPEC_MIN_SKILL[idx]:
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
    def gain_xp(self, skill_idx, base, spec_idx=None):
        """Award experience for an action. Returns the indexes changed, as
        {"skills": set, "specs": set, "attribs": set}, ready for a push.

        The client is handed the total and splits the premium share back
        out for its message, so the total is base * (1 + share). Half goes
        to the skill and half to the specialisation (wiki "Начисление опыта
        по мобу"); the remainder past a threshold carries into the next
        level. An attribute gains one per specialisation level up to 20.
        """
        total = int(base * (1 + PREMIUM_XP_BONUS[self.premium_level()]))
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        if total <= 0:
            return changed
        to_spec = total // 2 if spec_idx is not None and self.spec[spec_idx][0] >= 0 else 0
        to_skill = total - to_spec
        old_level = self.level

        s = self.skill[skill_idx]
        s[1] += to_skill
        while s[0] < SKILL_MAX and s[1] >= s[2]:
            s[1] -= s[2]
            s[0] += 1
            s[2] = skill_xp_max(s[0])
        if s[0] >= SKILL_MAX:
            s[1] = min(s[1], s[2])
        changed["skills"].add(skill_idx)

        if to_spec:
            sp = self.spec[spec_idx]
            sp[1] += to_spec
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

        if self.level != old_level:
            self.recalc()
            changed["attribs"].add(CONSTITUTION)
        return changed


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


def crit_chance(ch, weapon_type):
    """(crit %, anti-crit %) for a firearm of this type, showKrit 184-231,
    before item, set and effect bonuses. None for anything the card does
    not compute, which is every non-firearm."""
    row = _CRIT.get(weapon_type)
    if row is None:
        return None
    a, wa, b, wb, spec = row
    shooting = ch.skill_level(SHOOTING)
    sp = ch.spec_level(spec)
    cp = (ch.attr(a) * wa + ch.attr(b) * wb) / 4 + shooting / 4 + sp
    ce = (ch.attr(AGILITY) + ch.attr(PERCEPTION)) / 2 + shooting / 2 + sp
    return cp, ce


def level_gap(a, b):
    """PersAttributes.compareLevels: the difference clamped to +-4, which is
    both the frame over a mob's head and the wiki's experience multiplier
    minus four."""
    return max(-4, min(4, a - b))
