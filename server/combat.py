"""Combat: shooting, striking, being shot, dying, looting -- and the frames.

The client is a renderer. It computes no hit, no damage and no crit: every
number arrives ready (recon/analysis/combat.md), and what it does insist on is
the ORDER of the frames, because its state machine is built around it:

    cmdAck;res=0                      exactly one per ss_use, before anything else
    faAim;id;ang;num_shots            the figure raises the gun; the aim bar starts
    N x ( faShot;id;status=1          a bullet leaves; AP are charged once per burst
          faHit | faMiss | faWall     what it did, only inside the pair
          faShot;id;status=0 )        the pair closes; on the Nth the damage lands
    usrUp;id=<target>                 absolute HP/SP, after the last pair
    c_ap;ap=<N>                       absolute AP of the shooter -- autofire waits for it
    ss_di_firearm;ammo_count          the magazine

Location.as keeps ONE curFireEvent for the whole scene, so the N pairs of one
shooter go out back to back with nothing else in between; only the aim pause
before them may interleave with other traffic. The count of pairs must equal
num_shots or the walker's counter never reaches zero and the next burst
inherits a broken event. Strikes are one frame: caHit or caMiss.

The formulas are the wiki's "Игромеханика" (the developers' own design
document) where the client shows nothing, and the client's own card
(gpui/CharInterface.as, mirrored in progression.py) where it does, so that
the crit chance a player reads off the card is the one the server rolls.
Mob figures come from data/mob_curves.json through mobs.py.

Two objects: a Fighter per session (action points, timers, the loot window,
death), and a RoomCombat per room (war state, the AP clock, the mobs and
their brains, the corpses and bags). Both are reached from server.Session
through a handful of hooks; nothing here writes to the database behind the
Character's back, and HP travels only as usrUp.
"""
import asyncio
import logging
import math
import os
import random
import re
import time
from collections import namedtuple

import bosses
import events
import holdings
import inventory
import items
import mobs
import names
import orig_texts
import pace
import production
import progression
import quests
import rooms
import sets
import travel
import trophies
import world
from protocol import BigUInt

log = logging.getLogger("lava")

# StuffManager.SESSION_LOOT: the s_type of a bag on the ground.
SESSION_LOOT = 0

# The exit timer, in seconds: the owner's «таймер», after which a player may
# leave a location whatever is still after him, and before which he may not
# (chWorld is refused with 39, "Вы не можете выйти из локации в режиме боя
# в течение N сек..."; the walk-ins, the quest ways and /home wait). It is
# the countdown the client itself shows -- "Выход возможен через N сек." --
# and runs exactly as that one does (Fighter.in_combat): restarted by every
# hit the player gives or takes, a faHit or caHit with him at either end
# (Location.faHit/caHit -> LocationInterface.startExitTimer), and cancelled
# when the room goes to peace (lch;ws=0 -> battleMode ->
# deleteTimerLeaveLocation). Sent to the client in the constants frame as
# leave_combat_timeout, which is what its countdown counts down from.
#
# This timer opens the exits, not the map button. A PvP encounter keeps the
# room at war until one opponent dies or leaves (RoomCombat.hostilities).
LEAVE_COMBAT_TIMEOUT = int(os.environ.get("LAVA_LEAVE_COMBAT", "15"))
# A dead mob lies for this long before lch;lostUser fades it and the bag
# appears; then it comes back after RESPAWN_DELAY. The bag stays LOOT_LIFETIME.
CORPSE_DELAY = 2.5
# Five minutes for a creature, the owner's rule of 2026-10-09 («поменяем
# стандартный респ мобов на 5 минут»); it was 45 seconds. A thing of the
# role "object" -- a Tir target, a camp's box, a quarry stone
# (world.STANDING_OBJECTS) -- keeps the 45 seconds, by the owner's choice
# the same day: a Tir lesson wants its target shot down three times
# (quests 352-357), and five minutes a time would be a quarter of an hour
# of waiting at the counter. LAVA_RESPAWN shortens both for a test;
# LAVA_OBJECT_RESPAWN sets the objects' alone.
RESPAWN_DELAY = float(os.environ.get("LAVA_RESPAWN", "300"))
OBJECT_RESPAWN_DELAY = float(os.environ.get(
    "LAVA_OBJECT_RESPAWN", os.environ.get("LAVA_RESPAWN", "45")))
# How long a thing lies on the ground, in seconds: fifteen minutes from the
# moment it was put down, and then it is gone -- the owner's rule of
# 2026-09-28, «лут должен быть на локации 15 минут, даже если там никого
# нет». Every kind alike: a creature's loot, what fell off a dead player, a
# thing thrown down, a trophy. Nobody need be there: the clock runs in an
# empty room as in a full one, whoever walks in meanwhile is shown the bag
# (Fighter.entered), a pack's room hands its ground to its location's when
# it goes (RoomCombat.hand_over), and a restart stops nothing either (the
# ground table, restore_ground). Each thing keeps its own clock, so one put
# into a bag already lying there neither shortens nor stretches the time of
# what was in it before (RoomCombat.add_to_bag). The environment moves it
# for a test that cannot wait a quarter of an hour (test_ground); nothing
# that serves anybody sets it.
LOOT_LIFETIME = float(os.environ.get("LAVA_LOOT_LIFETIME", str(15 * 60)))
# Whose quests a corpse's quest rows of loot are rolled for (mobs.QUEST_TIER,
# RoomCombat.quest_wants): everybody still here who harmed the mob, and the
# one who struck the last blow -- so a friend's shot does not rob a player of
# the letter his quest sends him for. False: the last blow's alone, the way a
# kill counts towards a kill quest (Fighter.count_kill).
QUEST_LOOT_FOR_ALL_WHO_HARMED = True
# Whether a creature of the role "object" -- a box, a Tir target, a quarry
# stone (world.STANDING_OBJECTS, data/mob_curves.json roles.object) -- pays
# experience for the harm done to it. It never fights back and stands again
# after OBJECT_RESPAWN_DELAY, so paying was a farm without risk: 32 of Стрельба a
# level-5 stone at skill 4, every 45 seconds. False (the owner's plan,
# 2026-09-28): it still dies, counts as a kill for a kill quest
# (Fighter.count_kill) and rolls its loot, and teaches nothing. True pays
# it at the role's xp_mult, as before.
OBJECTS_PAY_XP = False
# APManager.dt: the client adds aspd to the bar every 600 ms while ws=1, and
# the server keeps the same clock so c_ap rarely has to correct anything.
AP_TICK = 0.6
AI_TICK = 0.4
REGEN_PERIOD = 60.0
# A bare-handed strike costs 5 AP (PersEquip.as:86, wiki).
FIST_AP = 5
# ErrorReport codes beyond inventory's, and the resurrection prices
# RegenerationInterface checks (5 hundredths of an ounce / 500 afro; free
# at any time).
#
# The gold figure stays as the window writes it. Unlike the training window,
# which only prints its price, this one compares: it greys the button while
# attributes.gold < GOLD_COST, and attributes.gold is the purse in hundredths
# of an ounce. So its 5 is five hundredths, and the server charges what the
# button lets the player press. (Training's prices are whole ounces and are
# scaled in progression.SPEC_COST; the two windows simply disagree.)
RES_NO_LEAVE = 39
RES_TOO_FAR = progression.ERR_TOO_FAR
# An attack on a player where that is not allowed. ErrorReport has no text
# for 22, so the figure lowers its weapon (Location.fireFailed) and nothing
# pops up; the reason goes to chat (Fighter.refuse_pvp).
RES_NO_PVP = 22
# The three buttons of the regeneration window, in its own numbering
# (RegenerationInterface.RESURECT_FREE/GOLD/AFRO).
RES_FREE, RES_GOLD, RES_AFRO = 0, 1, 2
# GOLD_COST=5 is checked against attributes.gold, which is the same number
# userInfo_Player sent: hundredths of an ounce, the whole part of which the
# purse panel shows (MoneyPan.set value divides by 100): 0.05 G. payAfro
# checks 500 afro, which at the gold_to_afro_rate the server's own constants
# frame carries (progression.GOLD_TO_AFRO_RATE, 50 000: "G 1 = A 50000",
# GoldToAfroInterface) is a hundredth of an ounce -- a fifth of the gold
# button. Both stay as the client has them; only a hand-made
# frame reaches the afro one (see resurrect()).
RESURRECT_GOLD = 5
RESURRECT_AFRO = 500
# What the free button ("Частичное восстановление") wakes up with, in per cent
# of the maximum. The window prints it under the button, in the static text
# of regenerationInterface in main.swf: "Я выкарабкаюсь сам ... 10% здоровья,
# 10% выносливости" -- and 100% of both under "Полное восстановление".
FREE_SHARE_PERCENT = 10
# char_id of item rows lying in a bag on the ground: no character has id 0.
LOOT_OWNER = 0
# What a dead player loses, in per cent -- the owner's rules of 2026-09-25,
# for every death, whoever or whatever did the killing («При любой смерти»):
# each piece of clothing on the body falls with WEAR_DROP_CHANCE if it is
# an afro thing («...с вероятностью 10%, если оно афро; если голд-предметы,
# то они не падают»), and each thing in the backpack with BAG_DROP_CHANCE
# («Каждая вещь с шансом 30%»). See death_losses. The environment moves them
# for a test that has to know what falls (test_death_drops sets both to
# 100); nothing that serves anybody sets either.
WEAR_DROP_CHANCE = int(os.environ.get("LAVA_WEAR_DROP", "10"))
BAG_DROP_CHANCE = int(os.environ.get("LAVA_BAG_DROP", "30"))

# What the server still accepts from a client it knows to be dead. Two
# families, and neither of them moves anything in the world:
#
#   the way in and the way out, because DEAD_STATE is entered after lenter,
#   never before it. A character that logged out dead selects, loads and
#   walks into a location alive as far as the client is concerned, and only
#   when Master.lenter (or gmap) reads persInfo;death does the regeneration
#   window open. Refusing lenter here would leave it standing in nowhere;
#
#   the pipelined requests, each of which carries a window on the client's
#   side that only an answer reopens (PROTOCOL 7): a dropped ss_get leaves
#   its ss_ack queue waiting for ever, and a dropped q_si wedges the journal.
#
#   and gg_info, the clan's questions, which change nothing and which the
#   client asks by itself at the very moment a dead member logs in:
#   Master.lenter enters LOCAL_STATE, ClanInspector.firstRequest sends
#   gg_info;det=1 (and det=5) on that change of state, and only then does
#   the resurrector put the client into DEAD_STATE. Refused, the roster was
#   answered «Сервер не отвечает» (res 3) and never asked for again
#   (ClanInspector.infoReceived) on that connection.
#
# Everything else is an action, and the client's own filter
# (FilterManager.createDSFilter) never sends one while dead.
DEAD_PASSES = frozenset((
    "hello", "login", "logout", "selPers", "newPers", "actPlayer", "lenter",
    "resurrect",
    "getInfo", "rp_get_info", "q_list", "q_si", "q_di", "q_status",
    "ss_get", "ss_get_si", "ss_get_di", "ss_get_s_si", "e_get_si", "e_get_di",
    "gg_info",
))

# What an action refused by the dead filter is answered with, where it is
# not RES_REFUSED (3). 3 is ErrorReport's «Сервер не отвечает», an alert over
# the whole screen; the clan's own commands are refused with the silent 20
# every clan refusal uses (clans.NOT_ALLOWED), whatever the server and the
# client happen to think of the body at that moment.
DEAD_REFUSAL = {"head": 20, "admit": 20, "apply": 20}

# The specialisation each firearm class trains (PersAttributes.specMatrix,
# CharInterface.showKrit): pistols 2, shotguns 3, assault 4, rifles 5,
# machine guns 6, SMGs 7. Fists train 0, blades 1. Medicine: first aid 8,
# surgery 9.
SPEC_OF_WEAPON = {items.PISTOL: 2, items.SHOTGUN: 3, items.ASSAULT: 4,
                  items.RIFLE: 5, items.MACHINEGUN: 6, items.SMG: 7}
SPEC_FIST, SPEC_BLADE, SPEC_FIRST_AID, SPEC_SURGERY = 0, 1, 8, 9

# One generator, seedable for a replayable session (LAVA_SEED).
RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

# What a round that leaves the barrel takes off the gun's durability. The
# wiki gives a Walther P99 a ceiling of 500 and players of the original
# remember a thousand rounds and more through one without a break, so a
# point a round wore guns out two or three times as fast as the game they
# played. Half a point brings the P99 to a thousand rounds; every gun keeps
# its own ceiling (max_break_abs), this one figure is the rate for all of
# them. LAVA_WEAR_PER_ROUND moves it (1 is the old point a round).
WEAR_PER_ROUND = float(os.environ.get("LAVA_WEAR_PER_ROUND", "0.5"))
# A generator of its own for the share of a point a burst leaves over, so
# that changing the rate leaves the seeded fight (RNG) as it was.
WEAR_RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
            else random.Random())


def round_wear(rounds, rate=None, rng=None):
    """The whole points rounds of fire take off a gun. Durability is stored
    in whole points (accounts.Store writes it through int()), so the share
    of a point is rounded up with its own chance: half a point a round is a
    point every other round on average, and never a bar that does not move."""
    exact = rounds * (WEAR_PER_ROUND if rate is None else rate)
    whole = int(math.floor(exact))
    if (WEAR_RNG if rng is None else rng).random() < exact - whole:
        whole += 1
    return whole


def pull(si, mode, ammo):
    """What one trigger pull fires and what it takes from the magazine:
    (bullets or pellets, rounds). A shotgun's mode counts pellets, not
    rounds: Сайга-12 has «длина очереди 6» and a magazine of 5, ИЖ-27 six
    from two barrels, the Излучатель «в разном режиме генерирует разное
    кол-во поражающих элементов» from a cell of ten. The client says the
    same: a shotgun's burst is one shot, one animation and one sound
    (DisplayLocScene.shotgunFireAck, Location.as:372). So a shotgun spends
    one round on its full charge of shot, whatever is left behind it; every
    other gun spends a round a bullet and fires what it holds."""
    shots = si["fire_mods"][mode]
    if si.get("weapon_type") == items.SHOTGUN:
        return shots, 1
    shots = min(shots, ammo)
    return shots, shots


# What one trigger pull is resolved with. cone is how wide the bullets
# scatter per hex of flight (cone_of); crit is a chance in percent before the
# target's evasion; opt_lo..opt_hi is the optimal band where crits are
# possible and the damage floor rises (wiki); skill and spec say where the
# experience goes (None for a mob). through: a round that hits goes on into
# the next body on its line (THROUGH_TYPES); at_players: a round may hit a
# player it was not aimed at (not with a gun a quest lends, quests.lent).
# sdmin/sdmax are the gun's independent stamina damage. Creature curves
# define only health damage, so their extra stamina component stays zero.
Weapon = namedtuple("Weapon", "num_shots dmin dmax opt_lo opt_hi max_range "
                              "piercing cone crit skill spec through at_players sdmin sdmax",
                    defaults=(False, True, 0, 0))


def now():
    return asyncio.get_running_loop().time()


def roll(chance, rng=None):
    """The wiki's test: a number from 1 to 100, at or under the chance."""
    return (RNG if rng is None else rng).randint(1, 100) <= chance


# --- what a dead player loses -----------------------------------------------

# The gold mark in a type's internal name, where the client's own table says
# what the price does not: the _G_ of the LVL clothing
# ("helm_Set_M_LVL_2_G_mod00"), _gold/_Gold on the guns and medicines
# ("pistols_1_lvl_1_gold", "Salus_MK_1_Gold"), _g on the belts
# ("belt_pistols_g"), G_ on the Ninth of May guns.
_GOLD_NAME = re.compile(r"(?:^|_)(?:G|g|gold|Gold|GOLD)(?:_|$)")
_GOLD = {}
_ORIG_NAMES = None


def _positive(rec, key):
    v = rec.get(key)
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _price_written(type_id):
    """Whether some table names this type's price -- the wiki's, a set's in
    data/sets.json, one of the hand-made files, an admin's -- rather than the
    designed frame guessing one (items.designed_info: 80 or 120 afro a tier,
    for 28 000 types the wiki says nothing about)."""
    for rec in (items.wiki().get(type_id), sets.item(type_id),
                items.heal_manual().get(type_id), items.loot_manual().get(type_id),
                items.coldarm_manual().get(type_id), items.ADMIN_OVERRIDES.get(type_id)):
        if rec and (_positive(rec, "cost") or _positive(rec, "g_cost")):
            return True
    return False


def gold_item(type_id):
    """Whether a type is a gold thing -- one of the owner's «голд-предметы»,
    which never fall off a dead player.

    A thing's currency is its price: cost is what a stall asks in afro, g_cost
    in hundredths of an ounce (items._common), and a type priced in gold
    alone is sold for gold alone (Inventory.buy refuses the afro code for
    it, and repair() restores it for its g_cost). That decides first. A type
    with both prices -- the tickets, the upgrade blueprints, the 9 mm rounds
    a newcomer is given -- is bought with afro and is an afro thing.

    Then the game's own label: the original's name tag [G], which reaches
    the player as "(G)" (orig_texts.item_name), is a gold copy whatever a
    wiki column linked to it by its icon says. And where no table names a
    price at all the designed frame's afro figure is a guess, so the gold
    mark of the internal name decides (_GOLD_NAME): a "_G_" piece of
    clothing is the gold copy of its [A] twin even though the frame prices
    both at 80 afro. A written afro price is believed over the name: the
    stun bolts "Ammo_stun_bolt_gold_10" are sold for afro in their article.
    (The gold line's upgrade blueprints "bpg_damage_25_gold_lvl*", which
    their articles price in both, are sold for gold alone since 2026-09-28,
    items.GOLD_PRICE_ONLY, so the price makes them gold things.)

    A gold ingot of 1, 5 or 10 ounces (items.GOLD_INGOTS, "New_Gold_Ingot_*")
    is never a gold thing, whatever its name and its prices: gold is what
    it is made of, and the bosses drop it -- the Nubian valley's and
    Вади-Хальфа's. The owner's «голдовое оружие и сэты не падают» is about
    gear bought for gold -- «это не лут» -- and the ingot is loot, which
    falls («любой лут должен падать»). It carries a gold price since
    2026-10-09, for which Мортимер sells it, beside its afro one; the
    rule above would still say afro, and the ingot is named here so that no
    change of a price can move it.
    """
    type_id = int(type_id)
    cached = _GOLD.get(type_id)
    if cached is None:
        cached = _GOLD[type_id] = _gold_item(type_id)
    return cached


def _gold_item(type_id):
    global _ORIG_NAMES
    if type_id in items.GOLD_INGOTS:
        return False
    si = items.params_of(type_id) or {}
    if _positive(si, "g_cost") and not _positive(si, "cost"):
        return True
    if _ORIG_NAMES is None:
        _ORIG_NAMES = orig_texts.item_names()
    if "(G)" in (_ORIG_NAMES.get(type_id) or ""):
        return True
    if _price_written(type_id):
        return False
    entry = items.catalogue().get(type_id)
    return bool(entry and _GOLD_NAME.search(entry[1]))


def drops_on_death(type_id):
    """Whether a thing of this type may fall off a dead player at all; how
    likely it is to, and how much of a stack, is death_losses'.

    Every thing may: the owner's rule is «Каждая вещь с шансом 30%». Kept
    on the body whatever the roll:

      * a gold thing (gold_item) -- «если голд-предметы, то они не падают»;
      * a premium one (items.premium): out of the game, and priced in gold
        anyway; and so one the owner took out by name (items.out_of_game,
        data/retired.json items): a bag on the ground would pass it on;
      * a quest's own thing, the quest flag of its frame: it belongs to the
        quest, as at the stall, in the post, at the auction and in a barter
        (Inventory.sell, mail, auction, barter.tradable), and no mob drops
        one either (mobs.droppable);
      * a thing a quest hands over when it is taken -- a parcel, provisions
        to carry (quests.kept_on_death, the owner's decision of 2026-09-26):
        fallen into a bag on the ground, it would leave a delivery that
        can never be handed in;
      * a thing whose hand-made record in data/loot_manual.json says
        drop_on_death 0. None does today: the mine's emeralds, which the
        game itself said could not be lost («Падающие в шахте изумруды
        нельзя потерять при гибели персонажа», texts.xml 59937), fall by
        the owner's rule («любой лут должен падать в том числе из шахты»),
        as the gold sand does and the gold ingots;
      * the developers' own gun (items.ADMIN_GUN), which is a tester's and
        nothing a player can buy: dropped by a tester killed in the open,
        it would be one.

    The wiki's own column, "Шанс выпадения при смерти", is not asked any
    more. It reached data/items_wiki.json as a flag: 88 of the 1 270 records
    say "да", 556 say "нет" and 626 do not tabulate it. Read as a rule, the
    556 would keep most of what a player carries -- the quest parts, the
    tickets, the blueprints, whole families of rounds and medicines -- out
    of the owner's "each thing", so it stays a note of the old game's and
    decides nothing here.
    """
    type_id = int(type_id)
    rec = items.loot_manual().get(type_id)
    if rec is not None and "drop_on_death" in rec and not rec["drop_on_death"]:
        return False
    si = items.params_of(type_id)
    if si is None or si.get("quest") or type_id == items.ADMIN_GUN:
        return False
    if quests.kept_on_death(type_id):
        return False
    return not items.out_of_game(type_id) and not gold_item(type_id)


def pieces_of(row):
    """How many of a thing a row is: a stack's size, one of anything else."""
    return row["count"] if row["root"] in items.HEAPABLE_ROOTS else 1


def bag_share(row, rng=None):
    """How many pieces of one backpack row fall.

    A single thing, and a stack of one or two, fall whole with
    BAG_DROP_CHANCE. A stack of three and more loses a third of itself,
    round(count / 3), every time, and keeps the rest under its own serial.

    The owner's "each thing with a chance of 30%" counts pieces: two hundred
    rounds are two hundred things, and thirty per cent of each is sixty on
    average. A third is the whole-number share nearest that which a player
    can be told in one word ("стопка теряет треть") -- 67 of 200, 7 of 20,
    1 of 3 or 4 -- and it is the same share every time, so a stack is never
    wiped out or spared whole by luck. It fails only where a third is less
    than one piece: round(1/3) is 0, a stack that could never fall, and
    round(2/3) is 1, a half. So one and two roll as a single thing does,
    and go whole or not at all. count / 3 is never a half, so round() has
    no tie to break.
    """
    n = pieces_of(row)
    if n >= 3:
        return int(round(n / 3.0))
    return n if roll(BAG_DROP_CHANCE, rng) else 0


def death_losses(rows, locked=(), rng=None):
    """What falls off a dead player: (row, pieces) for each row that loses
    anything, in the order of the rows given (Inventory.rows: by serial).

    Only two places are looked in. The six clothing slots (inventory.
    WEAR_SLOTS: head, shirt, armour, belt, trousers, boots -- everything the
    client draws on the body and describes by ss_si_wear, the belt as much
    as the rest) are the owner's «одежда»: each piece that may fall at all
    does so with WEAR_DROP_CHANCE. The backpack (inventory.BAG) is his
    «рюкзак»: each row there loses bag_share. The two hands hold weapons and
    medicines, which are neither, and keep what they hold; the bank is not
    on the body; what lies on the table in a barter (locked) is not in the
    backpack either -- though Fighter.die ends the barter first, and it
    comes back to it. One roll per row, rows in order, so a seeded RNG
    gives the same losses for the same things.
    """
    out = []
    for row in rows:
        if row["uniq"] in locked or not drops_on_death(row["type_id"]):
            continue
        if row["slot"] in inventory.WEAR_SLOTS:
            if roll(WEAR_DROP_CHANCE, rng):
                out.append((row, pieces_of(row)))
        elif row["slot"] == inventory.BAG:
            n = bag_share(row, rng)
            if n:
                out.append((row, n))
    return out


# At most this many things are named in the line about what fell; the rest
# are counted, so that a full backpack does not make a screenful of chat.
LOST_NAMED = 8


def lost_line(plan):
    """The chat line that tells a dead player what fell off the body:
    plan is Fighter.drop_on_death's, (row, None for whole or the pieces
    split off). The names are the ones the client shows (names.ALL, the
    class line after "$" cut off, as the client cuts it)."""
    said = []
    for row, part in plan:
        name = names.text(items.STRING_ID_OFFSET + row["type_id"]).split("$")[0].strip()
        n = pieces_of(row) if part is None else part
        said.append("%s (%d шт.)" % (name, n) if row["root"] in items.HEAPABLE_ROOTS
                    else name)
    text = ", ".join(said[:LOST_NAMED])
    if len(said) > LOST_NAMED:
        text += " и ещё %d" % (len(said) - LOST_NAMED)
    return ("При гибели выпало: %s. Всё это лежит в мешке там, где вы погибли."
            % text)


def parse_target(value):
    """(target type, id) from the ss_use target BigUINT: one hex digit of
    type, then the id padded to eight (MDString.createBigUINT). 1 is an
    entity, 0 a hex. None, None for anything else."""
    text = str(value or "").strip().lower()
    if not text:
        return None, None
    try:
        return int(text[:-8] or "0", 16), int(text[-8:], 16)
    except ValueError:
        return None, None


# --- the formulas ---------------------------------------------------------

def spec_or_zero(ch, idx):
    """An unlearned specialisation counts as 0 in a chance, not as -1."""
    return max(0, ch.spec_level(idx)) if idx is not None else 0


def melee_hit_chance(ch, spec):
    return 49 + 1.25 * ch.skill_level(progression.MELEE) + 5 * spec_or_zero(ch, spec)


# --- a bullet's flight, wiki "Расчет углового отклонения" ---------------------
#
# No dodge against a bullet: the design scatters the shot and lets the ground
# decide. Spread modifier МР = (1 + (0.7 - 0.65/20 * Стрельба) + (0.8 - 0.75/5
# * spec)) * TargetSize * Ammo.Precision_Mod, a random direction inside it,
# a flight simulated hex by hex, the target 0.3 m wide. The gun's TargetSize
# is read as the client reads it (FireArm.countAccuracy: the tooltip's
# «разброс на 100 метров» = 100 * target_size / max_range): the width the
# scatter has grown to at max_range, in hexes, a hex being a metre. So the
# scatter is a cone, cone_of() wide per hex of flight, and a bullet that
# lands within TARGET_SIZE of its line hits. «Наиточнейшее оружие имеет
# разброс равный площади цели»: a 0.3 gun in a master's hands (factor 1.1)
# at its full range is 0.33 wide, the target itself. A novice's factor is
# 2.5, so the same gun hits every time inside 0.9 of its range, a Walther
# (0.8 over 10 hexes) past two hexes one time in three at five.
TARGET_SIZE = 0.3


def spread_factor(skill, spec):
    """The МР bracket: 2.5 for nobody, 1.1 at Стрельба 20 and spec 5."""
    skill = max(0, min(progression.SKILL_MAX, skill))
    spec = max(0, min(progression.SPEC_MAX, spec))
    return 1 + (0.7 - 0.65 / 20.0 * skill) + (0.8 - 0.75 / 5.0 * spec)


def cone_of(factor, target_size, acc_mod, max_range):
    """How wide the scatter is per hex of flight: a bullet's sideways reach
    at distance d is cone * d / 2 either way."""
    if max_range <= 0:
        return 0.0
    return factor * target_size * acc_mod / float(max_range)


def hit_probability(cone, dist):
    """What the scatter leaves of a shot at this distance, 0..1: the
    target's width over the cone's, once the cone is wider than it."""
    width = cone * dist
    return 1.0 if width <= TARGET_SIZE else TARGET_SIZE / width


def bullet_offset(cone, dist, rng=None):
    """Where in the cone this bullet went: a sideways distance from the line
    of aim, at the target's distance, signed."""
    half = cone * dist / 2.0
    return (RNG if rng is None else rng).uniform(-half, half)


# --- the line of fire: who else stands on it, DESIGNED (2026-10-04) ----------
#
# The wiki kept the scatter and lost the rest, so these three are the
# owner's choice. A round that misses flies on and hits the first body on
# its way (a stray). A rifle's or a machine gun's round that hits goes on
# into the next body on its line for half the damage, and stops there. A
# body on the line between the shooter and the mark is cover: each one
# takes a third of the target's width off the window a round has to land
# in, and a round that would have hit but for the cover hits the cover.
#
# A body is what a round may hit (RoomCombat.bodies): for a player's round
# a creature that fights (MobStats.can_attack -- a box, a heap of ore or a
# Tir target is not one, nor are the traders, who are no mobs at all) and
# where players may be attacked any player outside the shooter's party;
# for a creature's round any player. Whoever cannot be hit is no cover
# either: a round passes a party member as if he were not there.
THROUGH_TYPES = frozenset((items.RIFLE, items.MACHINEGUN))
THROUGH_SHARE = 0.5
COVER_SHARE = 1.0 / 3


def on_target(offset, window=TARGET_SIZE):
    return abs(offset) <= window / 2.0


def cover_window(covers):
    """The width a round has to land in with this many bodies in front of
    the mark: a third of the target off for each, nothing left at three."""
    return TARGET_SIZE * max(0.0, 1.0 - COVER_SHARE * covers)


def bodies_between(loc, a, b, bodies):
    """The bodies (cell -> body) on the straight line strictly between two
    hexes, nearest first: the hexes line_of_fire samples for a wall."""
    w = loc.width
    ax, ay = mobs.real(a, w)
    bx, by = mobs.real(b, w)
    steps = max(1, int(math.ceil(mobs.hex_distance(a, b, w) * 2)))
    out = []
    for i in range(1, steps):
        t = i / float(steps)
        c = mobs.cell_at(ax + (bx - ax) * t, ay + (by - ay) * t, w, loc.height)
        body = bodies.get(c) if c not in (a, b) else None
        if body is not None and body not in out:
            out.append(body)
    return out


def stray(loc, a, aim, offset, max_range):
    """Where a bullet that passed its mark comes down: flight() over an
    empty room."""
    return flight(loc, a, aim, offset, max_range)[1]


def flight(loc, a, aim, offset, max_range, bodies=None, past=0.0):
    """A round's way out from hex a: (the bodies it passes through, nearest
    first, and faWall at the first obstacle or else faMiss where it runs out
    at max_range). Its line goes through the point offset sideways at the
    aim. bodies is cell -> body; a body is passed when its hex is, and only
    farther out than past hexes (a round that hit its mark goes on from
    there).

    A mark on the hex the round starts from -- a creature come back on its
    spawn hex under the player, one he walked onto, the ground at his own
    feet -- gives the line no direction: it passes nobody and lands about
    the aim. That answer is the same pair as every other: when flight()
    began to name the bodies (2026-10-04) this one kept the bare end, and
    burst read the letters of "faMiss" as the bodies a round went through
    (production, 2026-10-09: 'str' object has no attribute 'sp_now')."""
    bodies = bodies or {}
    w, h = loc.width, loc.height
    ax, ay = mobs.real(a, w)
    tx, ty = mobs.real(aim, w)
    dx, dy = tx - ax, ty - ay
    d = math.hypot(dx, dy)
    if d == 0:
        return [], ("faMiss", miss_at(tx, ty))
    ux, uy = dx / d, dy / d
    px, py = tx - uy * offset, ty + ux * offset
    bx, by = px - ax, py - ay
    b = math.hypot(bx, by)
    bx, by = bx / b, by / b
    ground = _Sights(loc) if getattr(loc, "shoot_over", None) else loc
    x, y = tx, ty
    crossed = []
    steps = max(1, int(math.ceil(max_range * 2)))
    for i in range(1, steps + 1):
        t = min(max_range, i / 2.0)
        nx, ny = ax + bx * t, ay + by * t
        if not (-0.5 <= nx < w and -mobs.ROW_H / 2 <= ny <= (h - 0.5) * mobs.ROW_H):
            break
        x, y = nx, ny
        c = mobs.cell_at(x, y, w, h)
        if c == a:
            continue
        if c in ground.obstacles:
            return crossed, ("faWall", dict(hex=c))
        body = bodies.get(c)
        if body is not None and body not in crossed                 and mobs.hex_distance(a, c, w) > past:
            crossed.append(body)
    return crossed, ("faMiss", dict(x=round(x, 2), y=round(y, 2)))


def melee_crit(ch, spec):
    """Wiki: agility + melee * 2.5 + specialisation * 6, and the gear's crit
    on top. The card shows no melee crit to agree with; a "Крит +N" on a
    piece of clothing or a set is still a crit, whatever is in the hand."""
    return ch.attr(progression.AGILITY) + 2.5 * ch.skill_level(progression.MELEE) \
        + 6 * spec_or_zero(ch, spec) + ch.bonus_cp


def melee_crit_evade(ch):
    """Wiki: (agility + perception) / 2 + melee / 4 + specialisation, and
    the gear's anti-crit on top, as melee_crit takes its crit."""
    return (ch.attr(progression.AGILITY) + ch.attr(progression.PERCEPTION)) / 2.0 \
        + ch.skill_level(progression.MELEE) / 4.0 + spec_or_zero(ch, SPEC_FIST) \
        + ch.bonus_ce


def split_damage(dmg, armor, piercing, crit, sp_left, st_dmg=0):
    """(to HP, to SP) of a bullet. On a critical hit, the owner's rule
    (2026-10-10) is H to health and min(H, remaining SP) to stamina, with
    no overflow into health and no additional weapon stamina component.
    On an ordinary hit armour redirects part of H to stamina, as in wiki
    "Броня", on top of the weapon's S; missing stamina spills into health.
    """
    if crit:
        return dmg, min(dmg, max(0, sp_left))
    comp = max(0, int(armor - piercing))
    redirected = min(dmg, comp)
    s = st_dmg + redirected
    h = dmg - redirected
    if s > sp_left:
        h += s - max(0, sp_left)
        s = max(0, sp_left)
    return h, s


def melee_split(dmg, crit, sp_left):
    """A blow lands on stamina first and only the remainder on HP (wiki
    "Ближний бой"); a crit goes straight to HP."""
    if crit:
        return dmg, 0
    s = min(dmg, max(0, sp_left))
    return dmg - s, s


def miss_at(rx, ry):
    """faMiss lands near the aim point: x/y are in hex units (rx, ry), which
    DisplayLocScene scales by the cell size itself."""
    return dict(x=round(rx + RNG.uniform(-0.7, 0.7), 2),
                y=round(ry + RNG.uniform(-0.7, 0.7), 2))


class _Sights(object):
    """The ground as a bullet sees it where it flies over a counter."""

    def __init__(self, loc):
        self.width, self.height = loc.width, loc.height
        self.obstacles = loc.obstacles - loc.shoot_over


def shot_wall(loc, a, b):
    """mobs.line_of_fire for a shot: the first obstacle between the hexes, or
    None -- but in a range (world.SHOOT_OVER) the booth's counter is shot
    over, so the targets beyond it can be hit at all. Everywhere else the
    same answer as line_of_fire."""
    wall = mobs.line_of_fire(loc, a, b)
    if wall is None or not getattr(loc, "shoot_over", None):
        return wall
    return mobs.line_of_fire(_Sights(loc), a, b)


# --- a bag on the ground --------------------------------------------------

class LootBag:
    def __init__(self, cell, uniqs):
        self.cell = cell
        self.uniqs = list(uniqs)
        # uniq -> the epoch second that thing goes (LOOT_LIFETIME after it
        # was put down); expiry is the timer for the first of them.
        self.until = {}
        self.expiry = None


INTERCEPT_PREPARE = 15.0


def interception_positions(room, occupied=(), rng=None):
    """Random free cells 8..15 hexes apart, connected without crossing exits.

    A bounded breadth-first search also keeps the walking distance at most
    fifteen steps. If the map has no such pair, the catch must not force
    two players into an adjacent or disconnected fight.
    """
    rng = RNG if rng is None else rng
    loc = room.loc
    blocked = set(loc.obstacles) | set(travel.exit_sides(loc)) | set(occupied)
    blocked.update(s.pos for s in room.players)
    for cells, _rec in travel.walk_ins(loc):
        blocked.update(cells)
    if room.combat is None:
        blocked.update(n.cell for n in room.npcs.values())
    else:
        blocked.update(n.cell for n in room.npcs.values() if n.root != world.MOB)
        blocked.update(m.cell for m in room.combat.mobs.values() if m.alive)
    starts = [c for c in range(loc.width * loc.height) if c not in blocked]
    rng.shuffle(starts)
    for start in starts:
        seen, fringe, choices = {start}, [start], []
        for _step in range(15):
            next_fringe = []
            for cell in fringe:
                for nb in progression.hex_neighbours(cell, loc.width, loc.height):
                    if nb in seen or nb in blocked:
                        continue
                    seen.add(nb)
                    next_fringe.append(nb)
                    if 8 <= mobs.hex_distance(start, nb, loc.width) <= 15:
                        choices.append(nb)
            fringe = next_fringe
            if not fringe:
                break
        if choices:
            return start, rng.choice(choices)
    return None


class Interception:
    """One shared loading grace period, followed by a duel without a shot."""

    def __init__(self, first, second):
        self.fighters = (first, second)
        self.until = now() + INTERCEPT_PREPARE
        for fighter in self.fighters:
            if fighter.interception is not None:
                fighter.interception.cancel()
            fighter.interception = self
        self.timer = asyncio.get_running_loop().call_later(INTERCEPT_PREPARE, self.finish)

    def finish(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        remaining = self.until - now()
        if remaining > 0:
            self.timer = asyncio.get_running_loop().call_later(remaining, self.finish)
            return
        first, second = self.fighters
        # A slow loader gets no new countdown. Start the duel when both
        # lenter handshakes have arrived; unloading or disconnect cancels it.
        rc = first.rc
        if (rc is None or second.rc is not rc
                or not first.present(rc) or not second.present(rc)):
            for fighter in self.fighters:
                fighter.show_prepare(0)
            return
        self.cancel()
        if not all(f.sess.loc.war and f.pvp_allowed() for f in self.fighters):
            return
        first.engage_player(second)
        rc.mark_foe(first, second)
        rc.mark_foe(second, first)
        rc.set_ws(True)

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        for fighter in self.fighters:
            if fighter.interception is self:
                fighter.interception = None
                fighter.show_prepare(0)


def prepare_interception(first, second):
    """Only a location permitting PvP can turn a map catch into a duel."""
    if all(not f.dead and f.sess.loc.war and f.pvp_allowed() for f in (first, second)):
        Interception(first, second)


# --- one player -----------------------------------------------------------

class Fighter:
    """The combat side of one session. Owned by server.Session as .combat."""
    is_player = True

    def __init__(self, sess):
        self.sess = sess
        self.ap = 0
        # Opponent -> last exchange time. A duel needs two living players;
        # one timestamp per player kept the winner fighting a corpse.
        self.duels = {}
        # loop time of the last hit this player gave or took -- a creature's
        # or a player's, his on anything -- from which the exit timer runs
        # (LEAVE_COMBAT_TIMEOUT, in_combat). Forgotten whenever the client
        # forgets its countdown: the room going to peace, and a new location.
        self.last_hit = -1e9
        # Entity ids of the players this client has been told are its enemies
        # here (lch;enemy, RoomCombat.mark_foe). The mark lives on the other's
        # walker in the client, so it is good until either of them walks in
        # afresh and the figure is built again.
        self.foes = set()
        self.interception = None
        self.dead = False
        self.aim = None         # TimerHandle: a burst waiting for fire_times
        self.strike = None      # TimerHandle: a swing waiting for strike_time
        self.healing = None     # TimerHandle: a heal waiting for heal_time
        self.reloading = None   # TimerHandle: ammunition is applied on completion
        self.reload_plan = None
        self.healing_peace = True
        self.action_revision = 0
        self.walk_ap = None     # (cells, start time, already charged steps)
        self.damage_revision = 0  # Damage since the start of peaceful healing.
        self.hit_revision = 0     # Hits given/taken since healing started.
        self.loot = None        # cell of the bag the loot window is open on
        # Index sets of an rp_info being held back (hold_stats): a burst
        # that kills is paid twice in one breath, for the harm and at the
        # kill, and the client prints a «+N» for each rp_info it gets.
        self.held_stats = None
        # Things that ran out of that bag while its window was open, as
        # (uniq, type_id, root) rows: the window still shows them, since
        # nothing can tell it otherwise (RoomCombat.expire_bag), and a
        # take-all moves them into the bag on the client (ss_upd 3).
        self.ran_out = []
        self.regen_at = 0.0
        # The amax the last lenter carried, or None before the first. The
        # client's bar keeps that ceiling until the next lenter
        # (APManager.setAP is called from Master.lenter and nowhere else),
        # so the fight here keeps it too -- see ap_max.
        self.amax_sent = None

    # --- plumbing ------------------------------------------------------------
    @property
    def store(self):
        return self.sess.inv.store

    @property
    def rc(self):
        """The room's combat state, or None off any room (the map)."""
        room = self.sess.room
        return room_combat(room, self.store) if room is not None else None

    def ack(self, res):
        self.sess.send("cmdAck", res=res)

    def character(self):
        return self.sess.character()

    # --- as an entity in a fight -------------------------------------------
    @property
    def eid(self):
        return self.sess.pid

    @property
    def cell(self):
        """Where the figure is now, not where it is going: a walk takes
        HEX_MS a hex on the client, and a creature must not bite, nor take
        for a target, a player still running towards it from across the
        room (Session.live_cell). A seat without walks (the suites' own
        sessions) stands on its pos."""
        live = getattr(self.sess, "live_cell", None)
        return live() if live is not None else self.sess.pos

    @property
    def alive(self):
        return not self.dead

    @property
    def level(self):
        return self.character().level

    @property
    def hp_max(self):
        return self.character().hp_max

    @property
    def ap_max(self):
        """The card's ОД and the bar's ceiling, gear included: what lenter
        told the client (Character.ap_ceiling), not rp_info's bare ap_max.

        The figure of the last lenter, not the live one. A set piece that
        breaks or comes off in the middle of a location lowers ap_ceiling
        at once, but the client's bar still fills to the old amax -- on its
        own tick and on every edge of ws -- and a server that regenerated
        and reset to the lower one would refuse, with res=11, the shots the
        bar says are paid for. The new ceiling reaches both sides together,
        with the next lenter."""
        if self.amax_sent is not None:
            return self.amax_sent
        return self.character().ap_ceiling

    def vitals(self):
        return self.character().vitals()

    def sp_now(self):
        return self.vitals()["scur"]

    def apply_damage(self, hdmg, sdmg):
        """Take a hit. Through the Character, whose save() writes hp/sp back
        on logout; anything written past it would be undone."""
        ch = self.character()
        v = ch.vitals()
        ch.hp = max(0, v["hcur"] - hdmg)
        ch.sp = max(0, v["scur"] - sdmg)
        # Armour is what took the blow, so armour is what it costs. One piece
        # per hit, chosen by the roll -- this is the only place every hit on a
        # player passes through, from a mob, from a burst or from a blade.
        if hdmg > 0 or sdmg > 0:
            self.damage_revision = getattr(self, "damage_revision", 0) + 1
            try:
                self.sess.inv.wear_worn(1)
            except Exception:                    # never let a bag fault stop a fight
                log.exception("  ..    wearing armour failed")
        return ch.hp <= 0

    def dodge_melee(self):
        return progression.melee_evade(self.character())

    def crit_evade_melee(self):
        return melee_crit_evade(self.character())

    def crit_evade_ranged(self):
        """The card's anti-crit for the weapon in hand (CharInterface.showKrit);
        with no firearm, the pistol row, the one the card would show first --
        but the card shows nothing then, so its set counted twice
        (inventory.card_repeat) is left out, as melee leaves it out."""
        gun = self.primary()
        if gun is not None and gun["root"] == items.FIRE_ARM:
            wt = (items.params_of(gun["type_id"]) or {}).get("weapon_type", items.PISTOL)
            pair = progression.crit_chance(self.character(), wt)
        else:
            pair = progression.crit_chance(self.character(), items.PISTOL, card=False)
        return pair[1] if pair else 0

    def armor(self):
        """The card's armour: base plus armor_class over the six clothing
        slots (CharInterface.showArmorLevel)."""
        worn = sum((items.params_of(r["type_id"]) or {}).get("armor_class", 0)
                   for r in self.sess.inv.rows() if r["slot"] in inventory.WEAR_SLOTS)
        return progression.armor_class(self.character(), worn)

    def present(self, rc):
        return not self.dead and not self.preparing() and self.sess in rc.room.players

    def preparing(self):
        grace = getattr(self, "interception", None)
        return grace is not None and now() < grace.until

    def show_prepare(self, seconds, viewer=None):
        """Player.prepare subtracts two; time=0 must clear its stored flag."""
        room = self.sess.room
        if room is None or self.sess not in room.players:
            return
        params = dict(id=self.eid, time=math.ceil(seconds) + 2 if seconds > 0 else 0)
        if viewer is None:
            room.broadcast(("prepare", params))
        else:
            cmd, fields = rooms.viewer_frame("prepare", params)(viewer)
            viewer.send(cmd, **fields)

    def primary(self):
        return self.sess.inv.in_slot(inventory.PRIMARY)

    # --- session hooks -----------------------------------------------------
    def entered(self):
        """After Room.enter: start the room's clock and hand the client the
        empty effect list it would otherwise never hear about."""
        rc = self.rc
        if rc is None:
            return
        self.ap = self.ap_max
        self.regen_at = now() + REGEN_PERIOD
        # Every figure here is new to this client, and neutral.
        self.foes = set()
        # And its exit countdown is not running: a new location is a new
        # LocationInterface (SceneShifter.locationScene), which starts with
        # the way out open until a hit here starts the count.
        self.last_hit = -1e9
        rc.player_entered(self)
        # A full replacement of the list (EffectManager.e_list); empty is a
        # list too, and mobi_id=0 resolves to the gamer (PlayerRegister).
        self.resend_room()

    def resend_room(self, resumed=False):
        """Restore a client's view without resetting the ongoing fight."""
        rc = self.rc
        if rc is None:
            return
        self.sess.send("e_list", mobi_id=0, effects=[])
        if resumed:
            self.sess.send("lch", ws=int(rc.room.ws))
            self.sess.send("c_ap", ap=int(self.ap))
            for foe in self.foes:
                if rc.actor(foe) is not None:
                    self.sess.send("lch", enemy=foe)
            for mob in rc.mobs.values():
                if mob.target is self:
                    self.sess.send("lch", enemy=mob.eid)
            for other in rc.fighters():
                if other.preparing():
                    other.show_prepare(other.interception.until - now(), viewer=self.sess)
            # Death while the new client was loading may precede its
            # Location; persInfo was still alive at login.
            if self.dead:
                self.sess.send("lch", dead=0)
        # Corpses, both ways round. Someone who logged out dead walks in as
        # one, and the figure the room has just built for them has to fall
        # over (DisplayLocScene.dead); anyone already lying here has to be a
        # corpse on the newcomer's screen too. Never about oneself:
        # Resurrector.lch reads lch;dead=0 as "open the regeneration window",
        # and that window is already up from persInfo;death.
        if self.dead:
            self.sess.room.broadcast(("lch", dict(dead=self.eid)),
                                     exclude=self.sess)
        for other in rc.fighters():
            if other is not self and other.dead:
                self.sess.send("lch", dead=other.eid)
        # And the bags lying here, in one frame (Location.ss_loot takes a
        # list of hexes). The ss_loot that drew each went to whoever stood
        # here when it was put down, and a bag lies its LOOT_LIFETIME
        # whoever is in the room: without this a player back for his own
        # gear walked over it unseen. DisplayLocScene reads the Location's
        # list when it is built, so this lands whether the scene is up yet
        # or not.
        cells = rc.ground_cells()
        if cells:
            self.sess.send("ss_loot", s_status=1, hex=cells)

    def left(self):
        """Before Room.leave: whatever was in flight aims at nothing now,
        and the exit timer and a duel stay with the room they ran in. A duel
        whose last blow missed no longer holds anybody (in_combat), so the
        one who walks out of it must not carry its war into the next room."""
        if self.interception is not None:
            self.interception.cancel()
        self.cancel_timers()
        self.loot = None
        self.last_hit = -1e9
        self.end_duels()

    def moved(self, cells):
        """The player walked. The client drops its aim bar and autofire on
        its own userMove (WeaponPan.breakTimeBar, AutoCommandManager), and
        the wiki says running cancels the aim at no cost, so the burst is
        cancelled here and nothing is charged. Steps cost 1 AP each while
        the room is at war, which the client also subtracts by itself
        (APManager.gamerMove); c_ap after the next action corrects drift."""
        Fighter.settle_walk(self, stop=True)
        Fighter.cancel_pending(self, notify=True, moving=True)
        walk = getattr(self.sess, "walk", None)
        if walk is not None:
            path, began = walk
            self.walk_ap = (path, began, 0)
            return
        rc = self.rc
        if rc is not None and rc.room.ws:
            self.ap = max(0, self.ap - max(0, len(cells) - 1))

    def settle_walk(self, t=None, stop=False):
        """Charge completed steps, never the unwalked end of a route."""
        pending = getattr(self, "walk_ap", None)
        if pending is None:
            return
        cells, began, paid = pending
        t = now() if t is None else t
        steps = min(len(cells) - 1, max(0, int((t - began) * 1000 // mobs.HEX_MS)))
        cost = max(0, steps - paid)
        rc = self.rc
        if cost and rc is not None and rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.walk_ap = None if stop or steps == len(cells) - 1 else (cells, began, steps)

    def primary_changed(self):
        """An accepted active-slot change abandons aim and reloading.

        Invalidate the callback even if the player switches back before its
        deadline. Melee swings and healing keep their existing behaviour.
        """
        had_reload = getattr(self, "reloading", None) is not None
        if getattr(self, "aim", None) is not None or had_reload:
            Fighter.cancel_pending(self, notify=True)
            if not had_reload:  # cancel_pending already corrected reload AP.
                self.c_ap()

    def cancel_timers(self):
        Fighter.settle_walk(self, stop=True)
        Fighter.cancel_pending(self)

    def cancel_pending(self, notify=False, replacing=False, moving=False):
        """Invalidate callbacks as well as removing their timer handles."""
        had = False
        had_heal = getattr(self, "healing", None) is not None
        had_aim = getattr(self, "aim", None) is not None
        had_reload = getattr(self, "reloading", None) is not None
        for name in ("aim", "strike", "healing", "reloading"):
            handle = getattr(self, name, None)
            if handle is not None:
                handle.cancel()
                setattr(self, name, None)
                had = True
        if had_reload:
            self.sess.inv.cancel_reloads()
        self.action_revision = getattr(self, "action_revision", 0) + 1
        if had and notify:
            Fighter.action_cancelled(self, release=not replacing, stop_aim=had_aim, moving=moving)
            if had_heal or had_reload:
                self.c_ap()

    def action_cancelled(self, release=True, stop_aim=False, moving=False):
        """Stop the owner's UI and, for aiming, the observers' animation."""
        params = dict(release=int(release))
        if moving:
            params["moving"] = 1
        if stop_aim:
            params["stop_aim"] = 1
        self.sess.send("actionCancel", **params)
        room = getattr(self.sess, "room", None)
        if stop_aim and room is not None:
            room.broadcast(("actionCancel", dict(id=self.eid, stop_aim=1)),
                           exclude=self.sess)

    def begin_action(self):
        """Called only after the replacement has passed its start checks."""
        Fighter.settle_walk(self, stop=True)
        Fighter.cancel_pending(self, notify=True, replacing=True)
        sess = self.sess
        if getattr(sess, "walk", None) is not None:
            cell = sess.live_cell()
            sess.pos = cell
            sess.cancel_passage()
            sess.send("actionCancel", pos=cell)
            if sess.room is not None:
                sess.room.broadcast(("actionCancel", dict(id=self.eid, pos=cell)),
                                    exclude=sess)
            self.c_ap()  # breakMove emits finishPart; correct its AP prediction.
        return self.action_revision

    def finish_action(self, revision, kind, callback, args):
        if revision != getattr(self, "action_revision", 0) or self.dead:
            return
        setattr(self, kind, None)
        # Consume the revision before execution: a duplicate callback is inert.
        self.action_revision += 1
        try:
            callback(*args)
        finally:
            if kind in ("healing", "reloading"):
                self.c_ap()

    def schedule_action(self, revision, kind, delay, callback, *args):
        handle = asyncio.get_running_loop().call_later(
            delay, Fighter.finish_action, self, revision, kind, callback, args)
        setattr(self, kind, handle)

    def restore(self, row):
        """A character has just been loaded: take its death back up.

        The flag is the characters row's (accounts.CHARACTER_COLUMNS), not
        the Character's, and this is the one place it comes back out of the
        database. The client learns of it from persInfo;death, sent before
        the selection, and raises the regeneration window by itself the
        moment it is standing somewhere (Master.lenter/gmap).
        """
        self.dead = bool(row is not None and row["death"])

    def close(self):
        """Connection gone. Must not raise: Session.close runs this before
        the position and the character are written.

        The dead stay dead: characters.death was written in die(), and the
        Character carries hp=0 out with it, so the next login finds a corpse
        where a corpse was left.
        """
        try:
            if self.interception is not None:
                self.interception.cancel()
            self.cancel_timers()
            self.loot = None
        except Exception:
            log.exception("  !!    combat close failed")

    def blocks(self, cmd, wants_ack):
        """The dead filter (FilterManager.createDSFilter): the client sends
        nothing but resurrect while dead, so an action that arrives anyway
        came from a modified one and is refused -- with an ack where one is
        owed, and an empty page for a search that waits on its own queue,
        so every queue stays in step. What still goes through, and why, is
        DEAD_PASSES."""
        if not self.dead or cmd in DEAD_PASSES:
            return False
        if wants_ack:
            self.ack(DEAD_REFUSAL.get(cmd, inventory.RES_REFUSED))
        elif cmd == "ah_search":
            # Its handler waits on a queue of its own, ah_sresult, and every
            # later search of the session is answered through the same
            # queue: one swallowed search hands each later page to a stale
            # handler for good (auction.py). A server that thinks the player
            # dead while the client does not is exactly the case this
            # filter cannot rule out, so it answers with an empty page.
            self.sess.send("ah_sresult", page=0, count=0, next=0)
        return True

    def hit_exchanged(self, t=None):
        """A hit with this player at one end has just gone out, a faHit or a
        caHit: the client has restarted its exit countdown on it, and so
        does the server (in_combat)."""
        self.last_hit = now() if t is None else t
        self.hit_revision = getattr(self, "hit_revision", 0) + 1
        if (getattr(self, "healing", None) is not None
                and getattr(self, "healing_peace", True)):
            Fighter.cancel_pending(self, notify=True)

    def medicine_blocked(self, peace):
        """Medicine category follows room war only, never the exit timer."""
        return bool(peace and self.rc is not None and self.rc.room.ws)

    def engage_player(self, other, t=None):
        """Remember this pair, without refreshing unrelated opponents."""
        t = now() if t is None else t
        self.duels[other] = other.duels[self] = t

    def end_duels(self):
        """Death or departure ends only this player's exchanges."""
        for other in self.duels:
            other.duels.pop(self, None)
        self.duels.clear()

    def exit_timer_left(self):
        """Seconds the exit timer still runs, 0 once it has run out -- the
        client's countdown to the second (LocationInterface.exitTimer): it
        opens the way when leave_combat_timeout whole seconds have passed
        since the last hit given or taken, and the server, which sent that
        hit before the client could count from it, is never the later of
        the two. Nothing runs off any room."""
        if self.sess.on_map or self.sess.room is None:
            return 0.0
        return max(0.0, LEAVE_COMBAT_TIMEOUT - (now() - self.last_hit))

    def in_combat(self):
        """Whether this player is barred from walking out: during interception
        preparation, then while the hit-based exit timer runs.

        The question is not who is after you. A creature that has taken you
        as its target keeps you for as long as you stay (mobs.Mob.think),
        and the room at war with it (RoomCombat.hostilities) -- but the way
        out is yours once the timer has run out, the creature still at your
        heels. Nor is it whether you fired: a shot that hit nothing -- a
        miss, a burst into the scenery, a swing at bare ground -- starts no
        countdown on the client, and none here. What starts it is a hit,
        given or taken, by a creature or by a player; so a duel holds both
        its sides, the one who struck as much as the one who was struck, and
        every hit that lands keeps it running.

        It is the client's own countdown, which is why it has to be exactly
        that one. The exit window of a zone cell -- the one way out a player
        still has while ws=1 greys the map button (LocationInterface.
        battleMode) -- lights its buttons when that countdown ends
        (ExitLocationInterface.exitEnabled), and the server answers the
        chWorld they send by the same clock: refused while the window is
        dark, never refused when it is lit.

        Asked and not answered, for a caller that has already acknowledged the
        command in hand (/home) and must not ack twice.
        """
        return self.preparing() or self.exit_timer_left() > 0

    def acting(self):
        """Whether a shot, a swing or a heal of this player's is still in
        the air, waiting on its timer."""
        return (self.aim is not None or self.strike is not None
                or self.healing is not None)

    def refuse_leave(self):
        """chWorld while in_combat: Master.changeWorldAck words res=39 as
        "leave_combat_timeout seconds after your last shot", the text the
        client has; what is actually held is the exit timer's countdown."""
        if not self.in_combat():
            return False
        self.ack(RES_NO_LEAVE)
        return True

    def c_ap(self):
        Fighter.settle_walk(self)
        self.sess.send("c_ap", ap=int(self.ap))

    def newbie_ground(self):
        """Standing on the Nubian valley's ground (travel.newbie_ground):
        the file the client reads here lets a player be attacked, and the
        valley does not."""
        sess = self.sess
        return travel.newbie_ground(sess.loc, sess.gx, sess.gy)

    def pvp_allowed(self):
        """Whether another player may be shot or struck here: where the
        location's file allows it, as the client reads it, and not on the
        valley's ground whatever the file says."""
        return bool(self.sess.loc.pvp) and not self.newbie_ground()

    def allied(self, other):
        """In one party with another player: a round of his passes him by
        (RoomCombat.bodies)."""
        party = getattr(self.sess, "party", None)
        mine = party() if party is not None else None
        return mine is not None and other.is_player             and other.sess.char_id in mine.members

    def refuse_pvp(self):
        """A shot or a blow at another player where that is not allowed.

        Where the location's own file says pvp="0" the client never sends
        this (ItemActivator.fire/strike show "В этой локации Вы не можете
        нападать на других игроков" instead), so it is a modified client's.
        In the Nubian valley it is not: the client reads the desert template
        or the pocket of rock, which say nothing or pvp="1", and lets the blow
        go (travel.newbie_ground). Either way the answer is a code the client
        has no text for -- res=3 would pop "Сервер не отвечает" over a rule
        -- and the reason goes to chat: the client's own sentence, or for the
        valley one that says where a fight is allowed."""
        self.ack(RES_NO_PVP)
        if self.newbie_ground():
            self.sess.say("Нубийская долина — земля новичков: здесь нельзя "
                          "нападать на других игроков. Для поединков есть "
                          "Арена Нубии.")
        else:
            self.sess.say("В этой локации Вы не можете нападать на других "
                          "игроков")

    def refuse_no_ap(self):
        """res=11, and then the pool as it stands here. The client let the
        command through on its own bar (ItemActivator.canUse,
        AutoCommandManager.canFire), so its bar is ahead of this pool --
        steps and heals it charged by itself, a tick it counted early --
        and a refusal alone would leave it there to let the next one
        through as well. c_ap takes no handler, so the queue is untouched."""
        self.ack(inventory.RES_NO_AP)
        self.c_ap()

    # --- mobs as the client sees them ----------------------------------------
    def mob_info(self, npc_id):
        """Extra userInfo keys for an inhabitant that is a mob: its level,
        which paints the coloured shield beside its name -- the mob's level
        less the player's, -4 .. +4 (CharInfo.addLevelMc, mobLevel_mc). Since
        the names lost their "[N] " (orig_texts.person_name, 2026-10-12) it
        is all a player sees of a mob's level."""
        rc = self.rc
        mob = rc.mobs.get(npc_id) if rc is not None else None
        return dict(lvl=mob.level) if mob is not None else {}

    def after_npc_info(self, npc_id):
        """usrUp right behind a mob's userInfo, or the bar over its head
        is drawn against maxHealth = 1200 (PersAttributes.as:55)."""
        rc = self.rc
        mob = rc.mobs.get(npc_id) if rc is not None else None
        if mob is not None:
            self.sess.send("usrUp", id=mob.eid, **mob.vitals())

    def ss_get(self, p):
        """ss_get;target=<mob>;slot=<mask>: the creature's clothes and hands.

        Mob.as asks with mask 3 the moment the entity is built, and
        PersEquip.ss_ack splices six wear slots then two hands off the list
        whatever came, so the shape is fixed; the weapon in primary is what
        picks the animation set. True when answered here."""
        target = int(p.get("target", 0) or 0)
        rc = self.rc
        mob = rc.mobs.get(target) if rc is not None and target else None
        if mob is None:
            return False
        mask = int(p.get("slot", 0) or 0)
        weapon = mob.weapon_oid()
        out = []
        if mask & inventory.MASK_WEAR:
            out += [inventory.EMPTY] * len(inventory.WEAR_SLOTS)
        if mask & inventory.MASK_HANDS:
            out += [BigUInt(weapon) if weapon else inventory.EMPTY, inventory.EMPTY]
        if mask & inventory.MASK_SESSION:
            out.append(inventory.EMPTY)
        self.sess.send("ss_ack", o_list=out)
        return True

    def ss_get_di(self, p):
        """Dynamic info of a virtual instance (a mob's weapon). True when
        the id was one of ours; the window of five needs the answer."""
        parsed = inventory.parse_oid(p.get("obj"))
        if not parsed:
            return False
        uniq, type_id, root = parsed
        ammo_type = None
        room = getattr(self.sess, 'room', None)
        npc = room.npcs.get(uniq - mobs.VIRTUAL_BASE) if room is not None else None
        if npc is not None and npc.root == world.MOB:
            stats = mobs.stats(npc.type_id)
            if stats.weapon_type_id == type_id:
                ammo_type = stats.loot_ammo_type
        di = mobs.virtual_di(uniq, type_id, root, ammo_type=ammo_type)
        if di is None:
            return False
        cmd, fields = di
        self.sess.send(cmd, obj=BigUInt(inventory.oid(uniq, type_id, root)), **fields)
        return True

    # --- ss_use 16 / 2 / 4 -------------------------------------------------
    def ss_use(self, kind, p):
        """The combat bits of ss_use; inventory.py keeps load/unload/mode/
        delete. One cmdAck whatever happens, before any fa*/ca* frame."""
        if kind == inventory.USE_FIRE:
            self.use_fire(p)
        elif kind in (inventory.USE_IDLE, inventory.USE_TARGET):
            self.use_heal(p, kind)
        else:
            self.ack(inventory.RES_REFUSED)

    def use_fire(self, p):
        """type=16: a shot with the primary firearm, or a strike with a blade
        or the bare fist (obj=x0, ItemActivator.strike)."""
        sess = self.sess
        rc = self.rc
        if rc is None or sess.on_map or self.dead:
            self.ack(inventory.RES_REFUSED)
            return
        if self.preparing():
            self.ack(inventory.RES_NOT_READY)
            return
        if not sess.loc.war:
            # The client refuses this itself in a peaceful location
            # (ItemActivator.fire: locInfo.battle); a modified one is refused here.
            self.ack(inventory.RES_REFUSED)
            return
        obj = str(p.get("obj", "0") or "0").strip().lower()
        row = None if obj in ("", "0") else sess.inv.find(obj)
        if obj not in ("", "0") and row is None:
            self.ack(inventory.RES_NOT_FOUND)
            return
        why = inventory.weapon_requirement_error(row, self.character()) if row is not None else None
        if why:
            self.ack(inventory.RES_LEVEL)
            sess.answer(why)
            return
        ttype, tid = parse_target(p.get("target"))
        if ttype is None:
            self.ack(inventory.RES_REFUSED)
            return
        target = hexcell = None
        if ttype == 1:
            target = rc.actor(tid)
            if target is None:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if target.is_player and target.preparing():
                self.ack(inventory.RES_NOT_READY)
                return
            if target is self:
                # The client never aims at its own figure (ItemActivator:
                # targetActionMap[Gamer] = null), so this is a modified one;
                # res=3 would read "Сервер не отвечает", and 22 only lowers
                # the weapon (RES_NO_PVP).
                self.ack(RES_NO_PVP)
                return
            if target.is_player and not self.pvp_allowed():
                self.refuse_pvp()
                return
            if target.is_player and row is not None and quests.lent(row["type_id"]):
                # What a quest lends (quests.lent) is the quest's tool, not
                # a weapon: the stonecutter's pick breaks a stone of the
                # quarry in one strike (its article: 2250-2750) and the
                # training guns are for the Tir's targets, and neither is
                # turned on a player -- the quarry's pits are pvp="1".
                # DESIGNED (2026-09-28). The same answer as a peaceful
                # location's: the client lowers the weapon.
                self.ack(RES_NO_PVP)
                self.sess.say("Казённым инструментом на людей не нападают")
                return
        else:
            if not (0 <= tid < sess.loc.width * sess.loc.height):
                self.ack(inventory.RES_NOT_FOUND)
                return
            hexcell = tid
        if row is None or row["root"] == items.COLD_ARM:
            self.strike_with(row, target, hexcell)
            return
        if row["root"] != items.FIRE_ARM or row["slot"] != inventory.PRIMARY:
            self.ack(inventory.RES_NOT_FOUND)
            return
        si = items.params_of(row["type_id"]) or {}
        mode = row["cur_mode"]
        modes = si.get("fire_mods", [])
        if not (0 <= mode < len(modes)) or not modes[mode]:
            self.ack(inventory.RES_REFUSED)
            return
        if row["ammo_count"] <= 0:
            self.ack(inventory.RES_NO_AMMO)
            return
        if row["brk"] <= 0:
            self.ack(inventory.RES_BROKEN)
            return
        aim_cell = target.cell if target is not None else hexcell
        width = sess.loc.width
        # A mark beyond max_range is not refused: the shot goes, the rounds
        # and the action points go with it, and every bullet drops at the
        # range (RoomCombat.burst). The refusal used to be res=8, which the
        # client prints as «Невозможно пройти», its own words for a path it
        # cannot walk, and nothing in its table says «too far»; a player who
        # sees the bullets fall short needs no words.
        cost = si["fire_costs"][mode]
        Fighter.settle_walk(self)
        if rc.room.ws and self.ap < cost:
            self.refuse_no_ap()
            return
        revision = Fighter.begin_action(self)
        self.ack(inventory.RES_OK)
        # Raising the gun is already hostile: the room goes to war here, and
        # self.aim, set below before any tick can run, keeps it there while
        # the aim bar runs (RoomCombat.hostilities).
        rc.set_ws(True)
        ch = self.character()
        wt = si.get("weapon_type", items.PISTOL)
        spec = SPEC_OF_WEAPON.get(wt)
        crit = progression.crit_chance(ch, wt)
        ammo_si = items.params_of(row["ammo_type"]) or {}
        cone = cone_of(spread_factor(ch.skill_level(progression.SHOOTING),
                                     spec_or_zero(ch, spec)),
                       si["target_size"][mode], ammo_si.get("acc_mod", 1) or 1,
                       si["max_range"][mode])
        num_shots, rounds = pull(si, mode, row["ammo_count"])
        weapon = Weapon(num_shots=num_shots,
                        dmin=si["h_damage_min"][mode], dmax=si["h_damage_max"][mode],
                        sdmin=si.get("st_damage_min", [0, 0, 0])[mode],
                        sdmax=si.get("st_damage_max", [0, 0, 0])[mode],
                        opt_lo=si["opt_range"][mode], opt_hi=si["end_opt_range"][mode],
                        max_range=si["max_range"][mode],
                        piercing=ammo_si.get("piercing", 1),
                        cone=cone, crit=crit[0] if crit else 0,
                        skill=progression.SHOOTING, spec=spec,
                        through=wt in THROUGH_TYPES,
                        at_players=not quests.lent(row["type_id"]))
        rc.room.broadcast(("faAim", dict(id=self.eid,
                                         ang=mobs.direction(self.cell, aim_cell, width),
                                         num_shots=weapon.num_shots)))
        # The aim bar on the client runs fire_times[cur_mode] from faAim to
        # the first faShot (WeaponPan.aim); the burst waits the same.
        Fighter.schedule_action(self, revision, "aim",
            pace.paced(si.get("fire_times", [700])[mode] / 1000.0),
            self.fire_now, row["uniq"], target, hexcell, weapon, cost, rounds)

    def fire_now(self, uniq, target, hexcell, weapon, cost, rounds=None):
        """The burst, after the aim. num_shots pairs go out come what may:
        the client has already counted them from faAim. rounds is what the
        pull takes from the magazine (one for a shotgun's charge of shot,
        num_shots for a burst); what the magazine lost meanwhile leaves its
        share of the pairs empty."""
        self.aim = None
        rc = self.rc
        if rc is None or self.dead:
            return
        if rc.room.ws and self.ap < cost:
            Fighter.action_cancelled(self, stop_aim=True)
            self.c_ap()
            return
        row = self.store.item(uniq)
        if row is not None and row["char_id"] != self.sess.char_id:
            row = None
        if (row is None or row["slot"] != inventory.PRIMARY or row["brk"] <= 0
                or inventory.weapon_requirement_error(row, self.character())):
            # Requirements may have changed during aiming. Finish the animation
            # without damage, ammunition, durability or AP consumption.
            for _ in range(weapon.num_shots):
                rc.room.broadcast(("faShot", dict(id=self.eid, status=1)))
                rc.room.broadcast(("faShot", dict(id=self.eid, status=0)))
            # faShot animates a shot and predicts AP use on the client.
            # Restore the authoritative balance after the last pair; an
            # invalidated attack still consumes no server-side resources.
            self.c_ap()
            return
        if rounds is None:
            rounds = weapon.num_shots
        spent = min(rounds, row["ammo_count"]) if row else 0
        live = weapon.num_shots * spent // rounds if rounds else 0
        pool = target.hp if target is not None and not target.is_player else 0
        # Asked before the burst, which may kill it: whether the rounds could
        # have got there at all. Only then is the shot a provocation. It
        # walks the line the burst walks (shot_wall), and a fault in it is
        # no reason to keep the burst back: faAim has announced its pairs,
        # and raised out of here none of them went and nothing was paid. The
        # error log has it; the shot provokes nobody.
        try:
            reached = rc.within_fire(self, target, weapon.max_range)
        except Exception:
            log.exception("  !!    the line of fire of %s failed before its burst: it"
                          " provokes nobody", self.eid)
            reached = False
        others = []
        h, s, hits, killed = rc.burst(self, target, hexcell, weapon, live, others)
        if row is not None:
            # WEAR_PER_ROUND of durability per round that left the barrel. The
            # starter pistol holds 120 points, a median firearm 1000 -- and
            # the refusal when it reaches nothing is already written and
            # waiting (res=16, at the top of fire()). A gun a quest lends does not
            # wear: Берт's training pistol holds 120 and a level-0 cadet can
            # spend more than that on one lesson's targets, and a gun broken
            # halfway would lock the lesson until the next day (quests.lent).
            wear = 0 if quests.lent(row["type_id"]) else round_wear(spent)
            self.store.update_item(uniq, ammo_count=row["ammo_count"] - spent,
                                   brk=max(0, row["brk"] - wear))
        if rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.c_ap()
        if row is not None:
            self.sess.inv.push_di(self.store.item(uniq))
        # The burst's pay and the kill's settlement in one rp_info
        # (hold_stats); release even if the kill raises.
        blueprint_killer_level = (self.level if killed or any(
            dead for _body, _h, _s, dead, _pool in others) else None)
        self.hold_stats()
        try:
            if target is not None and not target.is_player:
                # Health up to what the mob had, and the stamina lost to
                # the weapon and armour (burst takes no more SP than there is):
                # both are harm done, see award_xp.
                self.award_xp(weapon.skill, weapon.spec, min(h, pool) + s, target)
            for body, oh, os_, _dead, opool in others:
                if not body.is_player:
                    self.award_xp(weapon.skill, weapon.spec, min(oh, opool) + os_, body)
            # A burst that fell short of the mark, or into a wall on the way,
            # turns no creature on the shooter and opens no duel: every round
            # dropped on the ground, and nothing out there felt it. A miss
            # within reach does provoke -- the bullets went past its ears.
            # Whatever else a round hit was hit: it turns, or it is a duel.
            if reached:
                rc.after_hostile(self, target)
            for body, _h, _s, _dead, _pool in others:
                rc.after_hostile(self, body)
            if killed:
                rc.kill(target, self, blueprint_killer_level=blueprint_killer_level)
            for body, _h, _s, dead, _pool in others:
                if dead:
                    # kill() lets the held rp_info go; each kill's price in
                    # one frame of its own.
                    self.hold_stats()
                    rc.kill(body, self, blueprint_killer_level=blueprint_killer_level)
        finally:
            self.release_stats()

    def strike_with(self, row, target, hexcell):
        """A swing: fist (5 AP, damage from strength) or the blade in hand."""
        if self.strike is not None:
            # Space/click spam must not restart a melee wind-up. Acknowledge
            # the repeated request silently, keeping the original target and
            # deadline; caHit/caMiss will release the client's AP latch once.
            self.ack(inventory.RES_OK)
            return
        Fighter.settle_walk(self)
        sess = self.sess
        rc = self.rc
        ch = self.character()
        strength = ch.attr(progression.STRENGTH)
        if row is None:
            cost, delay, spec = FIST_AP, 0.0, SPEC_FIST
            dmin, dmax = int(strength / 2), int(strength * 1.5)
        else:
            if row["slot"] != inventory.PRIMARY:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if row["brk"] <= 0:
                self.ack(inventory.RES_BROKEN)
                return
            si = items.params_of(row["type_id"]) or {}
            cost, spec = si.get("strike_cost", 8), SPEC_BLADE
            delay = si.get("strike_time", 0) / 1000.0
            dmin = si.get("h_damage_min", 1) + strength
            dmax = si.get("h_damage_max", 1) + strength
        if rc.room.ws and self.ap < cost:
            self.refuse_no_ap()
            return
        revision = Fighter.begin_action(self)
        self.ack(inventory.RES_OK)
        rc.set_ws(True)
        # The blade is carried into strike_now so the swing can wear it:
        # a fist has no uniq and wears nothing.
        args = (target, hexcell, (max(1, dmin), max(1, dmax)), spec, cost,
                row["uniq"] if row is not None else None)
        if delay:
            # The strike bar runs strike_time from the send to caHit/caMiss
            # (WeaponPan.strike); a fist has none and lands at once.
            Fighter.schedule_action(self, revision, "strike",
                pace.paced(delay), self.strike_now, *args)
        else:
            Fighter.finish_action(self, revision, "strike", self.strike_now, args)

    def strike_now(self, target, hexcell, dmg_range, spec, cost, uniq=None):
        self.strike = None
        rc = self.rc
        if rc is None or self.dead:
            return
        if rc.room.ws and self.ap < cost:
            self.sess.send("actionCancel", release=1)
            self.c_ap()
            return
        sess = self.sess
        ch = self.character()
        loc = sess.loc
        if uniq is not None:
            row = self.store.item(uniq)
            if (row is None or row["char_id"] != sess.char_id
                    or row["slot"] != inventory.PRIMARY or row["brk"] <= 0
                    or inventory.weapon_requirement_error(row, ch)):
                rc.room.broadcast(("caMiss", dict(id=self.eid, hex=hexcell if target is None else target.cell)))
                return
        aim_cell = target.cell if target is not None else hexcell
        killed = False
        reach = (target is not None and target.present(rc)
                 and mobs.adjacent(self.cell, target.cell, loc))
        hit = reach and roll(melee_hit_chance(ch, spec) - target.dodge_melee())
        if hit:
            crit = roll(melee_crit(ch, spec) - target.crit_evade_melee())
            dmg = RNG.randint(dmg_range[0], dmg_range[1])
            h, s = melee_split(dmg, crit, target.sp_now())
            pool = target.hp if not target.is_player else 0
            rc.room.broadcast(("caHit", dict(id=self.eid, target=target.eid,
                                             dmg=h, sdmg=s, crit=int(crit))))
            rc.hit_landed(self, target)
            killed = target.apply_damage(h, s)
            rc.push_vitals(target)
        else:
            # Not adjacent, or the roll failed: the wiki makes no roll for a
            # non-neighbour, and either way the client wants a caMiss on a hex.
            rc.room.broadcast(("caMiss", dict(id=self.eid, hex=aim_cell)))
        if rc.room.ws:
            self.ap = max(0, self.ap - cost)
        self.c_ap()
        # The swing costs the blade a point whether or not it landed: the
        # edge meets something either way, and a miss that cost nothing would
        # make flailing free.
        if uniq is not None:
            self.sess.inv.wear_uniq(uniq, 1)
        # The blow's pay and the kill's settlement in one rp_info
        # (hold_stats), as for a burst.
        blueprint_killer_level = self.level if killed else None
        self.hold_stats()
        try:
            if hit and not target.is_player:
                # A blow that does not crit lands on stamina first, and a mob
                # has as much of it as of health: counting the health alone
                # left the first half of every knife fight training nothing.
                # melee_split never takes more stamina than there is; health
                # is capped here.
                self.award_xp(progression.MELEE, spec, min(h, pool) + s, target)
            # A swing at anything that was never within reach provokes
            # nothing: no duel with a player, no creature turned on him. The
            # client strikes only a neighbour (Gamer.strike: isSiblings), so
            # this is one who stepped away while the blade was coming down --
            # or a modified client swinging from across the room, which would
            # otherwise hold its mark there (res=39) for as long as it kept
            # throwing a fist every half minute, or pull a creature to him
            # from where it stood.
            if reach:
                rc.after_hostile(self, target)
            if killed:
                rc.kill(target, self, blueprint_killer_level=blueprint_killer_level)
        finally:
            self.release_stats()

    # --- healing: ss_use 2 (self) and 4 (another) -----------------------------
    def use_heal(self, p, kind):
        """A heal item on oneself or a neighbour. cmdAck at once (the client
        charges heal_cost on it), the effect after heal_time as an absolute
        heal;hp;sp, then the item's use_count or its removal."""
        sess = self.sess
        rc = self.rc
        row = sess.inv.find(p.get("obj"))
        if row is None or row["root"] != items.HEAL:
            self.ack(inventory.RES_NOT_FOUND)
            return
        if items.stimulant_unavailable(row["type_id"]):
            self.ack(inventory.RES_REFUSED)
            sess.answer(items.STIMULANT_UNAVAILABLE)
            return
        if row["use_count"] <= 0:
            self.ack(inventory.RES_NO_ITEM)
            return
        target = self
        if kind == inventory.USE_TARGET and p.get("target") is not None:
            ttype, tid = parse_target(p.get("target"))
            other = rc.actor(tid) if rc is not None and ttype == 1 else None
            if other is None or not other.is_player:
                self.ack(inventory.RES_NOT_FOUND)
                return
            if other is not self and not progression.within_reach(
                    self.cell, other.cell, sess.loc.width, sess.loc.height):
                self.ack(RES_TOO_FAR)
                return
            target = other
        if getattr(target, "dead", False):
            self.ack(inventory.RES_REFUSED)
            return
        si = items.params_of(row["type_id"]) or {}
        cost = si.get("heal_cost", 0)
        peace = items.no_combat(row["type_id"])
        if Fighter.medicine_blocked(self, peace):
            self.ack(inventory.RES_NOT_READY)
            sess.answer("Обычное лечение недоступно во время боя.")
            return
        Fighter.settle_walk(self)
        if rc is not None and rc.room.ws and self.ap < cost:
            self.refuse_no_ap()
            return
        revision = Fighter.begin_action(self)
        self.ack(inventory.RES_OK)
        # Recreate the accepted heal's bar after cancellation of the old one.
        # The item id avoids relying on ItemActivator's mutable __usedItem.
        delay = pace.paced(si.get("heal_time", 0) / 1000.0)
        sess.send("actionStart", heal_obj=BigUInt(inventory.oid_of(row)),
                  duration=int(delay * 1000))
        ap_cost = cost if rc is not None and rc.room.ws else 0
        peace_damage = (getattr(self, "damage_revision", 0) + getattr(self, "hit_revision", 0),
                        getattr(target, "damage_revision", 0) + getattr(target, "hit_revision", 0)) if peace else None
        self.healing_peace = peace
        Fighter.schedule_action(self, revision, "healing",
            delay,
            self.heal_now, row["uniq"], target, peace_damage, ap_cost)

    def heal_now(self, uniq, target, peace_damage=None, ap_cost=0):
        self.healing = None
        row = self.store.item(uniq)
        if row is None or row["char_id"] != self.sess.char_id or self.dead:
            self.sess.send("actionCancel", release=1)
            return
        if items.stimulant_unavailable(row["type_id"]):
            self.sess.send("actionCancel", release=1)
            self.sess.answer(items.STIMULANT_UNAVAILABLE)
            return
        if target.dead:
            self.sess.send("actionCancel", release=1)
            return
        si = items.params_of(row["type_id"]) or {}
        peace = items.no_combat(row["type_id"])
        if Fighter.medicine_blocked(self, peace):
            self.sess.send("actionCancel", release=1)
            self.sess.answer("Обычное лечение прервано: начался бой.")
            return
        if peace and peace_damage is not None and peace_damage != (
                getattr(self, "damage_revision", 0) + getattr(self, "hit_revision", 0),
                getattr(target, "damage_revision", 0) + getattr(target, "hit_revision", 0)):
            self.sess.send("actionCancel", release=1)
            self.sess.answer("Лечение прервано полученным уроном. Предмет не израсходован.")
            return
        ch = self.character()
        patient = target.character()
        v = patient.vitals()
        if v["hcur"] <= 0:
            self.sess.send("actionCancel", release=1)
            return
        if self.ap < ap_cost:
            self.sess.send("actionCancel", release=1)
            return
        # Wiki "Медицина": the skill moves the floor towards the ceiling by
        # skill/20 of the span; the specialisation (surgery under 30% HP,
        # first aid above) scales both by 1 + 0.2 per level.
        lo, hi = si.get("min_h_rest", 0), si.get("max_h_rest", 0)
        lo = lo + ch.skill_level(progression.MEDICINE) * (hi - lo) / 20.0
        spec = SPEC_SURGERY if v["hcur"] < 0.3 * v["hmax"] else SPEC_FIRST_AID
        mult = 1 + 0.2 * spec_or_zero(ch, spec)
        healed = min(v["hmax"] - v["hcur"], int(RNG.uniform(lo, hi) * mult))
        slo, shi = si.get("min_st_rest", 0), si.get("max_st_rest", 0)
        rested = min(v["smax"] - v["scur"], int(RNG.uniform(slo, shi) * mult))
        patient.hp = v["hcur"] + max(0, healed)
        patient.sp = v["scur"] + max(0, rested)
        if ap_cost:
            self.ap -= ap_cost
        room = self.sess.room
        frame = ("heal", dict(id=self.eid, target=target.eid,
                              hp=patient.hp, sp=patient.sp))
        if room is not None:
            room.broadcast(frame)
        else:
            self.sess.send(frame[0], **frame[1])
        left = row["use_count"] - 1
        if left <= 0:
            self.store.delete_item(uniq)
            self.sess.inv.push_status(row, 0)
        else:
            self.store.update_item(uniq, use_count=left)
            self.sess.inv.push_di(self.store.item(uniq))
        if healed > 0 and hi:
            # Wiki: experience = healed * min(2, patient's max HP / the
            # item's ceiling), half to the skill, half to the specialisation.
            mo = min(2.0, v["hmax"] / float(hi))
            changed = ch.gain_xp(progression.MEDICINE, int(healed * mo), spec)
            if any(changed.values()):
                self.sess.push_stats(**changed)
            if progression.moves_vitals(changed):
                self.sess.push_vitals()

    # --- experience ---------------------------------------------------------
    def award_xp(self, skill, spec, dealt, target):
        """Experience for a blow or a burst that harmed a mob, by the owner's
        rule (progression.mob_xp): a price by the mob's level, halved at the
        trained skill's own level, quartered one below, nothing two below,
        times the mob's xp_mult.

        A kill is worth the price and no more, and a blow pays the part of
        it that its harm is of the mob's health and stamina together -- a
        blade lands on stamina first, and those blows have to train as well.
        A bullet takes little stamina, so blows alone would pay a gun less
        than a knife for the same kill; RoomCombat.settle_xp pays the rest
        when the mob dies, to everyone who harmed it by their share. The
        mob's ledger never lets one fighter be paid more than a whole kill.

        Against the level of the skill being trained, not the best one: a
        Стрельба 6 picking up a knife is a beginner with the blade, and the
        level-1 dog has to teach the knife (test_combat pins it).
        """
        st = getattr(target, "stats", None)
        if st is None or dealt <= 0:
            return
        pool = max(1, int(getattr(st, "hp_max", 1)) + int(getattr(st, "sp_max", 0)))
        share = min(float(dealt), pool) / pool
        ledger = getattr(target, "xp_ledger", None)
        if ledger is not None:
            row = ledger.setdefault(self, [0.0, 0.0, skill, spec])
            row[0] += dealt
            row[2], row[3] = skill, spec
            share = min(share, max(0.0, 1.0 - row[1]))
            row[1] += share
        # The same harm on the capture ledger, by character: what a
        # warehouse's boss is taken by (holdings.py; mobs.Mob.capture_harm).
        harm = getattr(target, "capture_harm", None)
        char_id = getattr(self.sess, "char_id", None)
        if harm is not None and char_id:
            harm[int(char_id)] = harm.get(int(char_id), 0) + dealt
        self.credit_xp(skill, spec, share, target)

    def credit_xp(self, skill, spec, share, target):
        """`share` of a kill of `target` into `skill`: the skill takes the
        whole award and a learned specialisation the same on top (gain_xp
        spec_on_top), so that opening one does not halve the pace the rule
        is built around. The fraction a hit leaves over carries to the next.
        The client prints "+N опыта" from the difference in the next
        rp_info, pushed for the indexes that moved; a level-up (constitution)
        and a level of a strength or agility specialisation move a bar's
        maximum, which travels by usrUp (progression.moves_vitals). An
        object pays nothing (OBJECTS_PAY_XP). From trained skill 17 the
        whole kill price is capped at one before dividing it across hits;
        the same rule applies to the death settlement."""
        if share <= 0:
            return
        ch = self.character()
        st = target.stats
        if not OBJECTS_PAY_XP and getattr(st, "role", None) == "object":
            return
        xp = ch.carry_xp(skill, progression.combat_mob_xp(
            target.level, ch.skill[skill][0], share, getattr(st, "xp_mult", 1)))
        if xp <= 0:
            return
        changed = ch.gain_xp(skill, xp, spec, spec_on_top=True)
        if any(changed.values()):
            self.stats_changed(changed)
        if progression.moves_vitals(changed):
            self.sess.push_vitals()

    # --- one rp_info for a burst that kills ---------------------------------
    def hold_stats(self):
        """Keep the rp_info of what follows until release_stats: the harm of
        a killing blow and the rest of the kill's price (settle_xp) arrive
        in one breath, and the client prints «Стрельба +5» twice for one
        shot, once per frame, where one «+10» is what happened."""
        if self.held_stats is None:
            self.held_stats = {"skills": set(), "specs": set(), "attribs": set()}

    def stats_changed(self, changed):
        """What gain_xp moved: pushed now, or kept for release_stats."""
        if self.held_stats is None:
            self.sess.push_stats(**changed)
            return
        for group, idxs in changed.items():
            self.held_stats[group] |= idxs

    def release_stats(self):
        held, self.held_stats = self.held_stats, None
        if held and any(held.values()):
            self.sess.push_stats(**held)

    def count_kill(self, mob_type):
        """A mob died by this player's hand: kill quests advance and the
        journal is told (KillMobQuest.update reads kill_num)."""
        if not self.sess.char_id:
            return
        for cmd, params in quests.kill_progress(self.store, self.sess.char_id, mob_type):
            self.sess.send(cmd, **params)
        self.character().save(self.store)

    def pvp_kill(self, victim):
        """Another player died by this one's hand: the trophy.

        Skills and specialisations learn from creatures only (the wiki's
        "Игромеханика": experience is paid when the harm was done to a mob),
        and award_xp keeps to that. What a fight between people trains is the
        card's other number, «Навык бойца» -- rep, whose ranks run from
        Странник to Ассасин and whose rise the client announces by itself
        («Навык бойца повышен на: N», SpecSkillMessages.increase_reputation)
        when userInfo_Player brings a larger one. The kill itself pays none
        of it any more. The owner's rule: «навык бойца качается, если убить
        кого-то, получить с него трофей и сдать». So a killer at the
        victim's level or below gets a trophy, always, in the bag the death
        has just left on the victim's cell (die() put down what fell off
        the body first), and the skill is paid when that trophy is
        registered (trophies.Collection.register).
        """
        trophies.drop(self, victim, LOOT_OWNER, inventory.BAG)

    # --- death and resurrection ----------------------------------------------
    def die(self, killer):
        """hcur reached 0. lch;dead=<me> puts the client into DEAD_STATE and
        opens the regeneration window; until resurrect, blocks() holds.

        The flag goes to the database as well as into memory. A death a
        logout undoes is no death at all, and characters.death is what the
        next login is told about by persInfo;death (Session.send_account).
        """
        # A barter ends with the life, and before anything falls off the
        # body: what was on the table is the dead player's again, as much a
        # thing that can fall as the rest of the backpack. getattr, because
        # the suites fight with sessions of their own that have no barter.
        barter = getattr(self.sess, "barter", None)
        if barter is not None:
            barter.died()
        self.dead = True
        self.end_duels()
        self.cancel_timers()
        self.loot = None
        ch = self.character()
        ch.hp = 0
        ch.save(self.store)
        if self.sess.char_id:
            self.store.save_character_state(self.sess.char_id, death=1)
        room = self.sess.room
        if room is not None:
            room.broadcast(("lch", dict(dead=self.eid)))
            self.drop_on_death()
        # Nothing here to shoot at any more. think() would notice on its
        # next tick (present() is false for a corpse), but until then the
        # room stays at war over a target that cannot be hit.
        rc = self.rc
        if rc is not None:
            for mob in rc.mobs.values():
                if mob.target is self:
                    rc.mob_release(mob)
        log.info("  ..    %s died%s", self.sess.nick,
                 "" if killer is None else " to %s" % killer.eid)

    def drop_on_death(self):
        """What the corpse leaves lying on its cell: death_losses decides,
        the owner's rules for every death.

        All of it goes into ONE bag on the cell of the death, the ordinary
        one a mob's loot lands in, so the killer -- or anybody -- picks it up
        through the loot session that already exists (ss_create;s_type=0,
        ss_get;slot=24, ss_upd), and it expires with it (LOOT_LIFETIME).

        Every move of the death is one transaction (Store.drop_items): a
        thing that falls whole changes owner under its own serial, a stack
        that loses a part keeps the rest under its serial and the part
        becomes a row of its own. Then the client is told, the way it is
        told of every other removal, since it takes nothing away by itself:
        ss_obj_status;status=0 for a thing that left whole -- PersEquip.
        ss_obj_status looks for the id in the bag, both hands and all six
        clothing slots, and its removeItem runs checkFullSet, so the wearer's
        own figure is redrawn there -- and ss_di_heap with the new size for a
        stack that kept the rest (inventory.push_status, push_di). When
        anything came off the body the gear is recounted (Inventory.
        refresh_gear): the bonuses of the pieces and of their sets, pushed
        to the victim and the bars to the room, and the figure to everybody
        else in the room. A line in the chat says what fell.
        """
        rc = self.rc
        if rc is None or not self.sess.char_id:
            return
        inv = self.sess.inv
        losses = death_losses(inv.rows(), inv.locked)
        if not losses:
            return
        # None moves the row whole; a number splits that many pieces off.
        plan = [(row, None if n >= pieces_of(row) else n) for row, n in losses]
        ground = self.store.drop_items(self.sess.char_id, plan, LOOT_OWNER,
                                       inventory.BAG)
        if ground is None:
            # A row was no longer as it was read a moment ago, and nothing
            # at all was written: better nothing lost than half a death.
            log.warning("  !!    %s died, but the things to drop changed under"
                        " the write: nothing falls", self.sess.nick)
            return
        off_body = False
        for row, part in plan:
            if part is None:
                inv.forget_reload(row["uniq"])
                inv.push_status(row, 0)
                off_body = off_body or row["slot"] in inventory.WEAR_SLOTS
            else:
                inv.push_di(dict(row, count=row["count"] - part))
        # On the cell the walk was going to: the client does not stop a
        # figure that dies on its way (DisplayLocScene.dead only plays the
        # fall), so the corpse lies where the path ends.
        rc.add_to_bag(self.sess.pos, ground)
        if off_body:
            inv.refresh_gear()
        self.sess.say(lost_line(plan))
        log.info("  ..    %s drops %s on cell %d", self.sess.nick,
                 ", ".join("%d%s (type %d)" % (row["uniq"], "" if part is None
                                               else "/%d" % part, row["type_id"])
                           for row, part in plan), self.sess.pos)

    def resurrect(self, p):
        """resurrect;res_type=0|1|2 -- the buttons of the regeneration window
        (gpui/RegenerationInterface.as), and what each one costs.

        RESURECT_FREE=0 is the button main.swf labels "Частичное
        восстановление" (freeOfCharge_btn): "Я выкарабкаюсь сам", 10% of
        health and 10% of stamina, "this option will be chosen automatically
        in N s". It is enabled from the moment the window opens, and the
        countdown only presses it for a player who does not; so it is taken
        whenever it comes, and FREE_SHARE_PERCENT of both is what the body
        wakes up with. A refusal here would not be silent: ErrorReport
        listens to every cmdAck, so a 17 ("wait for the countdown") shows
        "Объект не готов" over a button the window lets the player press,
        and the press does nothing.

        RESURECT_GOLD=1 is "Полное восстановление" (paymentGold_btn, 100% of
        both): it costs GOLD_COST=5 and hides itself when the purse is short
        of it (init/uiUpd, with a link to the top-up page in its place).
        RESURECT_AFRO=2 costs the 500 payAfro checks for; the class wires a
        paymentAfro_btn, but the window in main.swf places none, so only a
        hand-made frame sends it. The two are not one price: GOLD_COST is
        five hundredths of an ounce (0.05 G), and at the gold_to_afro_rate
        this server sends (progression.GOLD_TO_AFRO_RATE, 50 000) 500 afro
        are 0.01 of an ounce. Both give HP and stamina back whole.

        Then home, always: the location registered with a resident
        (on_conv;op=0), or the starting cell when none was. resurrectAck
        closes the window and returns the client to LOCAL_STATE on res=0, so
        the acknowledgement goes first and Session.go_home's lcall second.
        """
        if not self.dead:
            # The window is not up. Nothing to do, but the ack is owed.
            self.ack(inventory.RES_OK)
            return
        res_type = int(p.get("res_type", 0) or 0)
        ch = self.character()
        if res_type == RES_GOLD:
            if ch.gold < RESURRECT_GOLD:
                self.ack(inventory.RES_NO_MONEY)
                return
            ch.add_money(gold=-RESURRECT_GOLD)
        elif res_type == RES_AFRO:
            if ch.afro < RESURRECT_AFRO:
                self.ack(inventory.RES_NO_MONEY)
                return
            ch.add_money(afro=-RESURRECT_AFRO)
        if res_type in (RES_GOLD, RES_AFRO):
            # None is how the Character spells "full" (progression.py).
            ch.hp = None
            ch.sp = None
        else:
            ch.hp = max(1, ch.hp_max * FREE_SHARE_PERCENT // 100)
            ch.sp = ch.sp_max * FREE_SHARE_PERCENT // 100
        self.dead = False
        # Resurrection puts the character at their home, well away from
        # whoever killed them; carrying the duel's timer across would lock
        # them out of the map on arrival.
        self.end_duels()
        ch.save(self.store)
        if self.sess.char_id:
            self.store.save_character_state(self.sess.char_id, death=0)
        self.ack(inventory.RES_OK)
        if res_type:
            self.sess.push_money()
        log.info("  ..    %s resurrects (res_type=%d) and goes home",
                 self.sess.nick, res_type)
        self.sess.go_home()

    # --- the loot window ------------------------------------------------------
    def open_loot(self, p):
        """ss_create;s_type=0;target=<cell>: Loot.createSession from a click
        on a bag, after Gamer.gotoLoot walked onto its cell -- or from
        PersEquip.dropItem, a thing dragged out of the equipment window onto
        the ground, which opens a session with no window on the player's own
        cell, bag or no bag.

        So the player's own cell opens with nothing on it too, and the first
        thing dropped there puts the bag down (ss_upd). Refused, Loot.status
        would stay false and every drop after it would wait in dropStack for
        a session that never comes: nothing could be thrown away on empty
        ground at all."""
        rc = self.rc
        cell = int(p.get("target", 0) or 0)
        bag = rc.loot.get(cell) if rc is not None else None
        if bag is None and (rc is None or cell != self.sess.pos):
            self.ack(inventory.RES_NOT_FOUND)
            return
        loc = self.sess.loc
        if not progression.within_reach(self.sess.pos, cell, loc.width, loc.height):
            self.ack(RES_TOO_FAR)
            return
        self.loot = cell
        self.ran_out = []           # a new window, listed afresh (ss_get)
        self.ack(inventory.RES_OK)

    def session_items(self):
        """Rows behind the 0 divider of ss_get;slot=24 while a bag is open."""
        rc = self.rc
        bag = rc.loot.get(self.loot) if rc is not None and self.loot is not None else None
        if bag is None:
            return []
        rows = [self.store.item(u) for u in bag.uniqs]
        return [r for r in rows if r is not None]

    def ss_upd(self, p):
        """Loot.UPD_*: 1 to the bag, 2 back to the ground, 3 everything,
        0 close (sent bare, no ack). False when no bag is open."""
        if self.loot is None:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == 0:
            self.loot = None
            return True
        rc = self.rc
        bag = rc.loot.get(self.loot) if rc is not None else None
        # A session on the player's own cell outlives its bag (close_bag):
        # the window or the equipment's drop is still open on the client,
        # and the next thing put down there puts a new bag down.
        underfoot = rc is not None and self.loot == self.sess.pos
        if bag is None and not (underfoot and code == 2):
            if not underfoot:
                self.loot = None
            self.ack(inventory.RES_NOT_FOUND)
            return True
        inv = self.sess.inv
        if code == 1:
            parsed = inventory.parse_oid(p.get("obj"))
            row = self.store.item(parsed[0]) if parsed else None
            if row is None or row["uniq"] not in bag.uniqs:
                self.ack(inventory.RES_NOT_FOUND)
                return True
            if inv.total_weight() + inventory.weight_of(row) > inventory.MAX_WEIGHT:
                self.ack(inventory.RES_OVERLOAD)
                return True
            # The ack first: Loot.transferAck moves the item on res=0, and an
            # emptied bag's ss_loot;s_status=0 may only follow it.
            self.ack(inventory.RES_OK)
            self.take(bag, [row])
        elif code == 2:
            row = inv.find(p.get("obj"))
            if row is None:
                self.ack(inventory.RES_NOT_FOUND)
                return True
            if gold_item(row["type_id"]):
                # A shared ground bag must not bypass gold gear's binding.
                # Refuse before changing ownership or creating a bag; the
                # failed transfer ack restores the item on the client.
                self.ack(inventory.RES_REFUSED)
                return True
            if quests.not_on_ground(row["type_id"]):
                # A quest's parcel stays with whoever it was handed to
                # (quests.START_OBJ_NOT_ON_GROUND). Before any bag is put
                # down; on anything but 0 Loot.transferAck puts it back in
                # the bag, and the session stays open for the next drop.
                log.info("  ..    %s keeps %d: a quest hands it over",
                         self.sess.nick, row["type_id"])
                self.ack(inventory.RES_REFUSED)
                return True
            self.store.update_item(row["uniq"], char_id=LOOT_OWNER, slot=inventory.BAG)
            # The ack first, as for code 1; then the thing is in the bag --
            # a new one drawn for the whole room -- with its own lifetime
            # running and its place written down (add_to_bag).
            self.ack(inventory.RES_OK)
            rc.add_to_bag(self.loot, [row])
        elif code == 3:
            rows = self.session_items()
            if inv.total_weight() + sum(inventory.weight_of(r) for r in rows) \
                    > inventory.MAX_WEIGHT:
                # All or nothing: on res=0 the client moves every item itself.
                self.ack(inventory.RES_OVERLOAD)
                return True
            self.ack(inventory.RES_OK)
            # On res=0 the client moves every item its window shows into
            # the bag (Loot.allTranferAck) -- a thing that ran out while it
            # was open too (ran_out). Right behind the ack that put it there,
            # the frame of every other removal takes it out again (PersEquip.
            # ss_obj_status finds it in the bag): nothing is left on the
            # client that the server does not hold.
            for row in self.ran_out:
                inv.push_status(row, 0)
            self.ran_out = []
            self.take(bag, rows)
        else:
            self.ack(inventory.RES_REFUSED)
        return True

    def take(self, bag, rows):
        """Rows keep their serial and so their oid: the client already holds
        the Item under it and only moves it between containers. Off the
        ground table in the same transaction (Store.pick_up)."""
        self.store.pick_up([row["uniq"] for row in rows], self.sess.char_id,
                           inventory.BAG)
        for row in rows:
            if row["uniq"] in bag.uniqs:
                bag.uniqs.remove(row["uniq"])
            bag.until.pop(row["uniq"], None)
        if not bag.uniqs:
            self.rc.close_bag(bag.cell)

    # --- effects (6.12, the minimum) -------------------------------------------
    def e_get_si(self, p):
        """e_si with every key Effect.clone reads, all neutral. Five of these
        may be in flight (EffectsFactory.packageLength) and each must be
        answered. name is a string id: the shared empty string."""
        self.sess.send("e_si", type=int(p.get("type", 0) or 0),
                       name=quests.EMPTY_STRING_ID, work_time=0, update_delta=0,
                       attribs_mask=0, attribs=[], skills_mask=0, skills=[],
                       specs_mask=0, specs=[], max_hp=0, max_sp=0, max_od=0,
                       critical_probability=0, critical_evade=0, armor=0,
                       mob_exp=0, pl_exp=0, mob_drop=0, pl_drop=0, res_icon=1,
                       immob=0, stun=0)

    def e_get_di(self, p):
        self.sess.send("e_di", type=int(p.get("type", 0) or 0),
                       mobi_id=int(p.get("mobi_id", 0) or 0), time=0)

    # --- regeneration ----------------------------------------------------------
    def regen(self):
        """Wiki: once a minute, +constitution HP (or +1 under 30%), each
        point paid with a point of stamina, and +1 stamina. Only a change
        is announced, as usrUp, so the "+N" floats over the head."""
        if self.dead:
            return
        ch = self.character()
        v = ch.vitals()
        hp, sp = v["hcur"], v["scur"]
        if hp < v["hmax"]:
            gain = ch.attr(progression.CONSTITUTION) if hp >= 0.3 * v["hmax"] else 1
            gain = max(0, min(gain, v["hmax"] - hp, sp))
            hp += gain
            sp -= gain
        sp = min(v["smax"], sp + 1)
        if (hp, sp) != (v["hcur"], v["scur"]):
            ch.hp, ch.sp = hp, sp
            rc = self.rc
            if rc is not None:
                rc.push_vitals(self)


# --- one room -------------------------------------------------------------

class RoomCombat:
    """War state, the AP clock, the mobs and their bags, for one Room."""

    def __init__(self, room, store):
        self.room = room
        self.store = store
        self.mobs = {eid: mobs.Mob(eid, npc.type_id, npc.cell)
                     for eid, npc in room.npcs.items() if npc.root == world.MOB}
        # The ones that keep hours instead of the respawn timer (bosses.py):
        # keep_hours brings them in and sends them away.
        self.bosses = [m for m in self.mobs.values() if bosses.keeps_hours(m.type_id)]
        self.recall_kills()
        # A boss's escort (data/placements.json "escort", rooms.Room.escorts):
        # while the room has a boss keeping hours, one killed waits for its
        # next arrival rather than the respawn timer.
        escorts = getattr(room, "escorts", ())
        self.escorts = [m for m in self.mobs.values() if m.eid in escorts]
        self.loot = {}          # cell -> LootBag
        # The combat state of the room that took this one's ground over when
        # a pack's room was taken away (hand_over): a corpse still fading
        # here then drops its bag there.
        self.heir = None
        self.timer = None
        self.ap_last = 0.0

    # --- who is here -------------------------------------------------------------
    def fighters(self):
        return [s.combat for s in list(self.room.players)]

    def actor(self, entity_id):
        """A living mob or a living player of this room by entity id."""
        mob = self.mobs.get(entity_id)
        if mob is not None:
            return mob if mob.alive else None
        if rooms.is_player_id(entity_id):
            sess = self.room.player(entity_id)
            if sess is not None and not sess.combat.dead:
                return sess.combat
        return None

    def nearest_fighter(self, cell, radius):
        width = self.room.loc.width
        best, best_d = None, radius
        for f in self.fighters():
            if not f.present(self):
                continue
            d = mobs.hex_distance(cell, f.cell, width)
            if d <= best_d:
                best, best_d = f, d
        return best

    def push_vitals(self, actor):
        """usrUp for anyone: the viewer's own id reads as 0 (rooms.viewer_frame)."""
        self.room.broadcast(("usrUp", dict(id=actor.eid, **actor.vitals())))

    # --- the clock -------------------------------------------------------------------
    def player_entered(self, fighter):
        # The newcomer's figure is built afresh on every screen here
        # (lch;newUser -> Location.addPlayer, a new LocWalker, relation
        # "neutral"), so a mark it carried from an earlier visit is gone.
        for f in self.fighters():
            f.foes.discard(fighter.eid)
            if f is not fighter and f.preparing():
                f.show_prepare(f.interception.until - now(), viewer=fighter.sess)
        if fighter.preparing():
            fighter.show_prepare(fighter.interception.until - now())
        elif fighter.interception is not None:
            fighter.interception.finish()
        if self.timer is None:
            self.ap_last = now()
            self._arm()
        if getattr(self.room, "ambush", None) is not None and not fighter.dead:
            # A pack met on the map (encounters.py) is after the one it
            # waylaid from the moment he is in: the room at war (lch;ws=1,
            # the battle track, the fight's bar) and every creature of it red
            # on his screen (lch;enemy). That is what says «На Вас напали»;
            # the loader's caption of those words never comes (encounters.py).
            for mob in self.mobs.values():
                if mob.alive and mob.target is None and mob.stats.can_attack:
                    self.aggro(mob, fighter)

    def _arm(self):
        self.timer = asyncio.get_running_loop().call_later(AI_TICK, self._tick)

    def _tick(self):
        self.timer = None
        try:
            self._step()
        except Exception:
            log.exception("  !!    combat tick in %s failed", self.room.loc.title)
        if self.room.players:
            self._arm()
        else:
            # Nobody left to fight or to tell: the room goes quiet, and the
            # next arrival finds it at peace (lcall;ws reads room.ws).
            self.room.ws = False
            for mob in self.mobs.values():
                if mob.target is not None:
                    self.mob_release(mob)
                if mob.aim is not None:
                    mob.aim.cancel()
                    mob.aim = None

    def _step(self):
        # Before the brains, so a boss whose stay is over is gone before it
        # thinks again.
        self.keep_hours()
        t = now()
        fighters = self.fighters()
        for f in fighters:
            Fighter.settle_walk(f, t)
        if self.room.ws:
            ticks = int((t - self.ap_last) / AP_TICK)
            if ticks:
                for f in fighters:
                    f.ap = min(f.ap_max, f.ap + ticks * progression.AP_REGEN)
                for mob in self.mobs.values():
                    mob.ap = min(mob.ap_max, mob.ap + ticks * progression.AP_REGEN)
                self.ap_last += ticks * AP_TICK
        else:
            self.ap_last = t
        for mob in list(self.mobs.values()):
            mob.think(self, t)
        self.calm(t)
        for f in fighters:
            if t >= f.regen_at:
                f.regen()
                f.regen_at = t + REGEN_PERIOD
        for mob in self.mobs.values():
            if mob.alive and mob.target is None and not mob.homing and t >= mob.regen_at:
                mob.regen_at = t + REGEN_PERIOD
                if mob.hp < mob.hp_max or mob.sp < mob.sp_max:
                    mob.hp = min(mob.hp_max, mob.hp + mob.level + 1)
                    mob.sp = min(mob.sp_max, mob.sp + 1)
                    if mob.hp >= mob.hp_max and mob.sp >= mob.sp_max:
                        # Whole again by its own pace: as mob_recover.
                        mob.capture_harm = {}
                    self.push_vitals(mob)

    def hostilities(self, t):
        """Whether the room is still at war.

        A creature after somebody here, a duel between living players still
        here, or a shot or swing still in the air -- anyone's,
        so that the bar a burst was charged on does not reset under it. That
        is all. The room used to stay at war for leave_combat_timeout after
        anybody's last shot or strike as well, and ws is not a detail the
        client shrugs off: while it is 1, LocationInterface.battleMode greys
        the exit button and toGlobal refuses, so a player who had killed the
        only creature that was after him -- or swung at nothing -- stood in a
        finished fight unable to leave for half a minute, however freely the
        server would have answered a chWorld (Fighter.in_combat).

        A creature after somebody keeps it at war for as long as it keeps
        its target, which is until he leaves or dies (mobs.Mob.think). The
        player is not shut in by that: ws=1 greys the map button, but the
        exit window of a zone cell opens by the exit timer alone.
        """
        for mob in self.mobs.values():
            if mob.alive and (mob.target is not None or mob.aim is not None):
                return True
        fighters = self.fighters()
        living = {f for f in fighters if not f.dead}
        for f in living:
            if f.aim is not None or f.strike is not None:
                return True
            for other in list(f.duels):
                if other in living:
                    return True
                f.duels.pop(other, None)
        return False

    def calm(self, t=None):
        """Peace, the moment there is nothing left to be at war over. Asked
        on every tick and straight after every death: the kill of the last
        creature that was after anybody must not leave the room at war for
        the rest of a tick either, because lch;ws=0 is what lights the
        client's exit button again (LocationInterface.battleMode) and
        cancels the countdown its faHit/caHit started
        (deleteTimerLeaveLocation)."""
        if self.room.ws and not self.hostilities(now() if t is None else t):
            self.set_ws(False)

    def set_ws(self, on):
        """lch;ws to everyone here. The client resets its bar to maxAP on
        either edge (APManager.warState) and only spends AP while ws=1, so
        the server's pools follow the same edges."""
        on = bool(on)
        if self.room.ws == on:
            return
        t = now()
        for f in self.fighters():
            Fighter.settle_walk(f, t)
        self.room.ws = on
        self.room.broadcast(("lch", dict(ws=int(on))))
        self.ap_last = now()
        for f in self.fighters():
            f.ap = f.ap_max
            if not on:
                # Peace cancels the client's exit countdown (battleMode ->
                # deleteTimerLeaveLocation), and the next war does not bring
                # it back: the server's timer goes with it.
                f.last_hit = -1e9
        for mob in self.mobs.values():
            mob.ap = mob.ap_max

    def within_fire(self, shooter, target, max_range):
        """Whether a burst from shooter can reach target at all: it is here,
        no farther than max_range, and no obstacle stands between (shot_wall,
        the line burst itself flies). Nothing about the scatter: a round that
        flies past within reach still flew past."""
        if target is None or not target.present(self):
            return False
        width = self.room.loc.width
        return (mobs.hex_distance(shooter.cell, target.cell, width) <= max_range
                and shot_wall(self.room.loc, shooter.cell, target.cell) is None)

    def after_hostile(self, attacker, target):
        """Bookkeeping after any shot or swing: the encounter of two players
        who exchanged it, and a mob that was attacked turns on its attacker.
        Nothing else is remembered: a shot at nobody leaves nobody after
        anyone, and the room returns to peace on its next tick."""
        t = now()
        if target is None:
            return
        if target.is_player:
            if attacker.is_player:
                # Keep both participants at war until death or departure;
                # the hit timer independently opens the edge exits.
                attacker.engage_player(target, t)
                self.mark_foe(target, attacker)
        elif (target.alive and attacker.is_player and target.stats.can_attack
              and target.target is not attacker):
            # Only what can fight back turns on its attacker. A box or a heap
            # of ore that took its shooter as a target would hold the room at
            # war over nothing -- and, standing next to him, "strike" him for
            # 0 (think() attacks whatever is in reach), which the client's
            # AUTO_SHOT answers with another shot at the box, for ever.
            self.aggro(target, attacker, t)

    def mark_foe(self, fighter, foe):
        """A player was shot at or swung at by another: the one attacked is
        told who by, the frame a mob's aggro sends. lch;enemy is not a mob's
        frame (Location.setEnemy takes any id in the room): the attacker's
        name and minimap mark turn red on the victim's screen
        (DisplayLocScene.enemy, DisplayMM.enemy), as a hostile clan's do
        (CharInfo.checkColor, standing -1). Once per figure: a duel is many
        blows, and the mark stays on the walker until it is built again
        (Fighter.foes). The attacker is marked on the other side the moment
        the victim answers, by the same rule."""
        if foe.eid in fighter.foes:
            return
        fighter.foes.add(foe.eid)
        fighter.sess.send("lch", enemy=foe.eid)

    def aggro(self, mob, fighter, t=None):
        """A mob picks a player: the room goes to war and the player's client
        paints the mob red (lch;enemy -> Location.setEnemy) and remembers it
        for autofire."""
        if fighter.preparing():
            return
        t = now() if t is None else t
        mob.target = fighter
        mob.next_attack = max(mob.next_attack, t + 0.3)
        self.set_ws(True)
        fighter.sess.send("lch", enemy=mob.eid)

    # --- what mobs do -------------------------------------------------------------------
    def mob_walk(self, mob, goal, t):
        """One leg of a walk towards the nearest cell satisfying goal, as
        userMove;id;path to everyone. The mob's cell is its destination at
        once, which is where the client will have it when the animation
        ends; busy_until keeps it from acting before that."""
        loc = self.room.loc
        blocked = {m.cell for m in self.mobs.values() if m.alive and m is not mob}
        # A player's hex now and the one his walk ends on: neither is free
        # to step onto while he is on the way.
        blocked |= {s.pos for s in self.room.players}
        blocked |= {f.cell for f in self.fighters()}
        # Where it is going, for a goal beyond the search's reach: the
        # target's cell while it chases, its spawn on the way home.
        toward = mob.target.cell if mob.target is not None else mob.home
        path = mobs.find_path(loc, mob.cell, goal, blocked, toward=toward)
        if not path or len(path) < 2:
            # Nothing nearer to step to: it waits and looks again, holding
            # on to its target all the same (Mob.think).
            mob.busy_until = t + mobs.STUCK_WAIT
            return
        leg = path[:mobs.LEG + 1]
        self.room.broadcast(("userMove", dict(id=mob.eid, path=leg)))
        mob.cell = leg[-1]
        npc = self.room.npcs.get(mob.eid)
        if npc is not None:
            self.room.npcs[mob.eid] = npc._replace(cell=leg[-1])
        mob.busy_until = t + mobs.HEX_MS / 1000.0 * (len(leg) - 1) + 0.1

    def mob_release(self, mob):
        """The target has left the room, died or dropped its socket: forget
        it. Not whole again on the spot -- the walk home follows on the next
        ticks, and it heals when it gets there (mob_recover). Healed where it
        let go, a creature whose target was still in reach took him again a
        tick later, whole every time."""
        mob.target = None
        mob.homing = True

    def mob_recover(self, mob):
        """Home again after a chase: whole, and the bar over its head shows it.
        Whole, it forgets the harm of the fight it left (Mob.capture_harm):
        a warehouse's boss is taken by the harm done since it was last whole
        (holdings.py), never by harm banked over heal after heal."""
        mob.homing = False
        if mob.hp < mob.hp_max or mob.sp < mob.sp_max:
            mob.hp, mob.sp = mob.hp_max, mob.sp_max
            mob.capture_harm = {}
            self.push_vitals(mob)

    def mob_attack(self, mob, target, t):
        st = mob.stats
        mob.next_attack = t + st.attack_time + mobs.ATTACK_PAUSE
        loop = asyncio.get_running_loop()
        if st.ranged:
            width = self.room.loc.width
            self.room.broadcast(("faAim", dict(
                id=mob.eid, ang=mobs.direction(mob.cell, target.cell, width),
                num_shots=st.shots)))
            # A creature shoots with its level for Стрельба and the curve's
            # spec (mobs.Stats), through the scatter of the gun in its hand.
            cone = spread_factor(st.level, st.spec) * st.scatter
            weapon = Weapon(num_shots=st.shots, dmin=st.dmg_min, dmax=st.dmg_max,
                            opt_lo=1, opt_hi=st.range, max_range=st.range, piercing=1,
                            cone=cone, crit=st.crit, skill=None, spec=None)
            mob.aim = loop.call_later(pace.paced(st.attack_time),
                                      self.mob_burst, mob, target, weapon)
        elif st.attack_time:
            mob.aim = loop.call_later(pace.paced(st.attack_time), self.mob_strike, mob, target)
        else:
            self.mob_strike(mob, target)

    def mob_burst(self, mob, target, weapon):
        mob.aim = None
        if not mob.alive:
            return
        others = []
        h, s, hits, killed = self.burst(mob, target, target.cell, weapon,
                                        weapon.num_shots, others)
        mob.ap = max(0, mob.ap - mob.stats.attack_ap)
        self.after_hostile(mob, target)
        if killed:
            self.kill(target, mob)
        for body, _h, _s, dead, _pool in others:
            if dead:
                self.kill(body, mob)

    def mob_strike(self, mob, target):
        mob.aim = None
        if not mob.alive:
            return
        st = mob.stats
        killed = False
        if target.present(self) and mobs.adjacent(mob.cell, target.cell, self.room.loc) \
                and roll(st.hit - target.dodge_melee()):
            crit = roll(st.crit - target.crit_evade_melee())
            dmg = RNG.randint(st.dmg_min, st.dmg_max)
            h, s = melee_split(dmg, crit, target.sp_now())
            self.room.broadcast(("caHit", dict(id=mob.eid, target=target.eid,
                                               dmg=h, sdmg=s, crit=int(crit))))
            self.hit_landed(mob, target)
            killed = target.apply_damage(h, s)
            self.push_vitals(target)
        else:
            self.room.broadcast(("caMiss", dict(id=mob.eid, hex=target.cell)))
        mob.ap = max(0, mob.ap - st.attack_ap)
        self.after_hostile(mob, target)
        if killed:
            self.kill(target, mob)

    # --- the shot resolver, shared -------------------------------------------------------
    def bodies(self, shooter, target, weapon):
        """cell -> body: whoever else a round of this burst may hit, the
        shooter and the mark left out (the rule over THROUGH_TYPES). One
        body a hex; a creature and a player never share one."""
        out = {}
        if shooter.is_player:
            for mob in self.mobs.values():
                if mob is not target and mob.present(self) and mob.stats.can_attack:
                    out.setdefault(mob.cell, mob)
        if not weapon.at_players:
            return out
        for f in self.fighters():
            if f is shooter or f is target or not f.present(self):
                continue
            if shooter.is_player and (not shooter.pvp_allowed() or f.newbie_ground()
                                      or shooter.allied(f)):
                continue
            out.setdefault(f.cell, f)
        return out

    def burst(self, shooter, target, hexcell, weapon, live, others=None):
        """num_shots pairs of faShot around what each bullet did, then usrUp
        of everyone hit. live is how many chambers held a round; the rest
        click (a miss). Returns (hp damage, sp damage, hits, killed) of the
        target; every other body a round hit (a stray, a cover, the one
        behind) goes into others as (body, hp, sp, killed, hp before).

        The client shows the damage of one body a burst: endOfShot reads
        what faHit piled on the last body hit (Location.as endOfShot,
        LocWalker.damageWalker) and clears that one only. So the pairs that
        hit the mark go last, and every other body's faHit carries no
        damage -- what was piled on it would have been shown with its next
        burst. Its health is in its usrUp all the same."""
        loc = self.room.loc
        width = loc.width
        if target is not None and not target.present(self):
            hexcell = target.cell
            target = None
        aim = target.cell if target is not None else hexcell
        if aim is None or not (0 <= aim < width * loc.height):
            aim = shooter.cell
        try:
            pairs, struck = self.resolve(shooter, target, aim, weapon, live)
        except Exception:
            # faAim has told every client here how many pairs this burst is
            # (Location.faAim, currNumOfShot), and only their last faShot
            # lowers the gun, closes the aim bar and lets the autofire go
            # again (AutoCommandManager.fireShotHandler). A fault in working
            # out where the rounds went -- the zero-length line of
            # 2026-10-09 was one -- sent none of them: the figure stood with
            # its gun raised and the autofire stopped, shot after shot. It
            # goes to the error log whole, and the burst goes out as the
            # miss it has become, every pair of it, and is paid for as one
            # (Fighter.fire_now): rounds, action points and the c_ap after.
            log.exception("  !!    a burst of %s at hex %d of %s failed: its %d round(s)"
                          " go out as misses", shooter.eid, aim, loc.title,
                          weapon.num_shots)
            tx, ty = mobs.real(aim, width)
            pairs = [(("faMiss", miss_at(tx, ty)), []) for _ in range(weapon.num_shots)]
            struck = {}
        # The body the client is shown the damage of: the mark if it was
        # hit, else whoever took the most.
        shown = target if target in struck else max(
            struck, key=lambda b: struck[b][0] + struck[b][1], default=None)
        pairs.sort(key=lambda pair: any(f[0] is shown for f in pair[1]))
        for end, fates in pairs:
            self.room.broadcast(("faShot", dict(id=shooter.eid, status=1)))
            if end is not None:
                self.room.broadcast(end)
            for body, h, s, crit in sorted(fates, key=lambda f: f[0] is shown):
                mine = body is shown
                self.room.broadcast(("faHit", dict(target=body.eid,
                                                   dmg=h if mine else 0,
                                                   sdmg=s if mine else 0,
                                                   crit=int(crit))))
            self.room.broadcast(("faShot", dict(id=shooter.eid, status=0)))
        # The pairs are out. What follows is the server's own account, and
        # its caller settles the shot by it: pays the rounds and the action
        # points, turns or kills whoever was hit. So each body's outcome is
        # written down the moment its damage is applied, before the frames
        # that tell of it, and a fault on the way ends the loop without
        # taking the account with it: raised out of here, it left the shot
        # unpaid and a body brought to 0 alive.
        result = (0, 0, 0, False)
        try:
            for body, (h, s, hits, _sp) in struck.items():
                pool = 0 if body.is_player else body.hp
                killed = body.apply_damage(h, s)
                if body is target:
                    result = (h, s, hits, killed)
                elif others is not None:
                    others.append((body, h, s, killed, pool))
                self.hit_landed(shooter, body)
                self.push_vitals(body)
        except Exception:
            log.exception("  !!    applying the burst of %s at hex %d of %s failed after"
                          " its pairs went out", shooter.eid, aim, loc.title)
        return result

    def resolve(self, shooter, target, aim, weapon, live):
        """Where each round of a burst went, nothing sent and nothing
        applied yet: (pairs, struck). A pair is (the faMiss or faWall it
        ends in, or None, and its fates: (body, hp, sp, crit) for each body
        it hit, nearest first); struck is body -> [hp, sp, hits, sp left]
        over the whole burst. target is the mark, present, or None for the
        ground at aim."""
        loc = self.room.loc
        width = loc.width
        dist = mobs.hex_distance(shooter.cell, aim, width)
        # The line to the mark is the bullets' line only as far as the gun
        # reaches: past max_range they come down (stray), and a wall beyond
        # that is nothing to them. stray finds one within reach on each
        # bullet's own line; asking the whole line drew the rounds flying 30
        # hexes into a rock the gun could never reach.
        wall = shot_wall(loc, shooter.cell, aim) if dist <= weapon.max_range else None
        tx, ty = mobs.real(aim, width)
        reach = target is not None and wall is None and dist <= weapon.max_range
        bodies = self.bodies(shooter, target, weapon) if live and wall is None else {}
        covers = bodies_between(loc, shooter.cell, aim, bodies) if reach else []
        window = cover_window(len(covers))
        depth = 2 if weapon.through else 1
        struck = {}                 # body -> [hp, sp, hits, sp left]
        pairs = []
        for k in range(weapon.num_shots):
            offset = bullet_offset(weapon.cone, dist)
            if k >= live:
                # An empty chamber: the pair was counted from faAim already.
                pairs.append((("faMiss", miss_at(tx, ty)), []))
                continue
            if wall is not None:
                pairs.append((("faWall", dict(hex=wall)), []))
                continue
            if reach and on_target(offset, window):
                behind, _end = flight(loc, shooter.cell, aim, offset,
                                      weapon.max_range, bodies, past=dist)
                chain = [target] + [b for b in behind if b not in covers]
            elif reach and on_target(offset):
                # It would have hit, and the cover took it; through the
                # cover it goes on along the line to the mark.
                chain = covers + [target]
                _end = None
            else:
                # Aimed at the ground, at a mark the gun does not reach, or
                # past the mark: on to where it lands, max_range at the
                # most, and into the first body on the way. Not into a
                # cover: what it had to give the cover is the window above.
                passed, _end = flight(loc, shooter.cell, aim, offset,
                                      weapon.max_range, bodies)
                chain = [b for b in passed if b not in covers]
            chain = chain[:depth]
            if not chain:
                pairs.append((_end, []))
                continue
            fates = []
            for n, body in enumerate(chain):
                rec = struck.setdefault(body, [0, 0, 0, body.sp_now()])
                d = mobs.hex_distance(shooter.cell, body.cell, width)
                optimal = weapon.opt_lo <= d <= weapon.opt_hi
                crit = optimal and roll(weapon.crit - body.crit_evade_ranged())
                lo, hi = weapon.dmin, weapon.dmax
                slo, shi = weapon.sdmin, weapon.sdmax
                if optimal:
                    lo = (hi - lo) // 2 + lo
                    slo = (shi - slo) // 2 + slo
                dmg = RNG.randint(lo, max(lo, hi))
                st_dmg = RNG.randint(slo, max(slo, shi)) if shi > 0 else 0
                if n:
                    dmg = max(1, int(dmg * THROUGH_SHARE)) if dmg > 0 else 0
                    st_dmg = max(1, int(st_dmg * THROUGH_SHARE)) if st_dmg > 0 else 0
                h, s = split_damage(dmg, body.armor(), weapon.piercing, crit, rec[3], st_dmg)
                rec[0] += h
                rec[1] += s
                rec[2] += 1
                rec[3] -= s
                fates.append((body, h, s, crit))
            pairs.append((None, fates))
        return pairs, struck

    def hit_landed(self, attacker, target):
        """A faHit or a caHit has just gone out: the exit timer restarts for
        each player at either end of it, as the client's countdown does
        (Location.faHit/caHit -> startExitTimer)."""
        t = now()
        for side in (attacker, target):
            if side is not None and side.is_player:
                side.hit_exchanged(t)

    # --- death, corpse, bag, respawn ----------------------------------------------------
    def kill(self, victim, killer, *, blueprint_killer_level=None):
        if victim.is_player:
            victim.die(killer)
            if killer is not None and killer.is_player and killer is not victim:
                killer.pvp_kill(victim)
            if getattr(victim.sess, "linger", None) is not None:
                victim.sess.expire_linger()
            # die() has let go every creature that was after the dead.
            self.calm()
            return
        mob = victim
        # Player attacks pass their level before any XP from this attack,
        # including collateral hits. The corpse materializes its loot later.
        mob.blueprint_killer_level = (
            (killer.level if blueprint_killer_level is None else blueprint_killer_level)
            if killer is not None and killer.is_player else None)
        mob.alive = False
        mob.target = None
        if mob.aim is not None:
            mob.aim.cancel()
            mob.aim = None
        # lch;dead plays the death animation and clears the figure's nick and
        # focus; the corpse stays until lostUser (DisplayLocScene.dead).
        self.room.broadcast(("lch", dict(dead=mob.eid)))
        if killer is not None and killer.is_player:
            # An ore rock teaches Промышленность (production.mined_by);
            # count_kill saves the character.
            production.mined_by(killer, mob)
            killer.count_kill(mob.type_id)
        # Before the ledger is settled and emptied: who brought it down is
        # who its quest rows of loot are rolled for (quest_wants).
        mob.quest_wants = self.quest_wants(mob, killer)
        # A warehouse's boss (holdings.py): who brought it down and for which
        # clan, as they stand now; the holding is settled when the corpse
        # fades (corpse_gone). A database that cannot be read costs the
        # capture and a line in the log, never the kill.
        try:
            mob.capture = holdings.snapshot(self, mob, killer)
        except Exception:
            mob.capture = None
            log.exception("  !!    mob %d (%s) killed in %s: who killed it not read",
                          mob.eid, mob.stats.name, self.room.loc.title)
        self.settle_xp(mob)
        # The killer's held rp_info goes out here, before calm() below can
        # end the war: the client keeps the awards of a fight and prints
        # them as one line on lch;ws=0, and an award that lands after that
        # frame is printed on its own (a player read «+5» then «+4»).
        if killer is not None and killer.is_player:
            killer.release_stats()
        # Out of the room's inhabitants until it respawns, so an arrival in
        # the meantime is not handed a corpse as a newUser.
        self.room.npcs.pop(mob.eid, None)
        witnesses = list(self.room.players)
        asyncio.get_running_loop().call_later(pace.paced(CORPSE_DELAY),
                                              self.corpse_gone, mob, witnesses)
        log.info("  ..    mob %d (%s) killed by %s", mob.eid, mob.stats.name,
                 "nobody" if killer is None else killer.eid)
        # If it was the last one after anybody here, the fight is over now.
        self.calm()

    def settle_xp(self, mob):
        """The rest of the kill's price, to everyone who harmed the mob and is
        still here, by their share of all the harm it took. Blows paid as they
        landed against health and stamina together; a gun takes little
        stamina, so its blows fall short of the price, and this closes the
        gap, whichever weapon did the work."""
        ledger, mob.xp_ledger = mob.xp_ledger, {}
        total = sum(row[0] for row in ledger.values())
        if total <= 0:
            return
        for fighter, (harm, paid, skill, spec) in ledger.items():
            if getattr(fighter, "sess", None) not in self.room.players:
                continue
            owed = harm / total - paid
            if owed > 1e-9:
                fighter.credit_xp(skill, spec, owed, mob)

    def quest_wants(self, mob, killer):
        """The things a quest still asks of those who brought the mob down
        -- everybody here who harmed it (its xp ledger; QUEST_LOOT_FOR_ALL_
        WHO_HARMED) and whoever struck the last blow -- for which it has a
        quest row of loot (mobs.
        QUEST_TIER): the courier's letter is in his bag for a player sent to
        intercept him, and for nobody else. Everybody's wants together, since
        the bag lies on the ground for whoever picks it up; each against his
        own bag (quests.wanted_things), so once one has enough it stops.
        Empty for a creature with no quest rows, and nothing is asked then."""
        if not mobs.quest_table(mob.type_id):
            return frozenset()
        fighters = [f for f in mob.xp_ledger
                    if getattr(f, "sess", None) in self.room.players] \
            if QUEST_LOOT_FOR_ALL_WHO_HARMED else []
        if killer is not None and killer.is_player and killer not in fighters:
            fighters.append(killer)
        out = set()
        for f in fighters:
            sess = f.sess
            if sess.char_id:
                out |= quests.wanted_things(self.store, sess.char_id,
                                            sess.inv.bag_pieces())
        return frozenset(out)

    def corpse_gone(self, mob, witnesses):
        """The figure fades (only for those who saw it: a lostUser about an
        id the client never met logs an event with no name), the bag drops
        where it fell, and the respawn clock starts -- for a boss, the clock
        on the wall: it is back at its next hour and not before
        (keep_hours)."""
        for sess in witnesses:
            if sess in self.room.players:
                sess.send("lch", lostUser=mob.eid)
        self.add_to_bag(mob.cell, self.drop_loot(mob))
        # A warehouse's boss settles its holding (holdings.settle) before the
        # hours below take it away -- and with LAVA_BOSS_HOURS=off, when it is
        # an ordinary mob, too. A database that will not take it costs the
        # record and a line in the log, never the kill (boss_killed's rule).
        if getattr(mob, "capture", None) is not None:
            try:
                holdings.settle(self, mob)
            except Exception:
                mob.capture = None
                log.exception("  !!    mob %d (%s) killed in %s: its holding not settled",
                              mob.eid, mob.stats.name, self.room.loc.title)
        if bosses.keeps_hours(mob.type_id):
            mob.away = True
            self.boss_killed(mob)
        elif mob in self.escorts and self.bosses:
            # The boss's escort: back with the boss's next arrival
            # (keep_hours, escort_back), not on the respawn timer -- or now,
            # if the boss arrived while this corpse was still fading.
            if mob.recalled:
                mob.recalled = False
                self.respawn(mob)
            else:
                mob.away = True
        elif getattr(self.room, "ambush", None) is not None:
            # A pack met on the map (encounters.py) is met once: nothing of
            # it comes back.
            mob.away = True
        else:
            delay = OBJECT_RESPAWN_DELAY if mob.stats.role == "object" else RESPAWN_DELAY
            asyncio.get_running_loop().call_later(delay, self.respawn, mob)

    def add_to_bag(self, cell, rows, until=None):
        """Put item rows into the bag on a cell, opening one where there is
        none. ss_loot;s_status=1 is what draws it (Location.ss_loot). Shared
        by a mob's loot, what a player drops where they died, a thing thrown
        down and a trophy.

        Each thing lies LOOT_LIFETIME from now, on its own clock (LootBag.
        until): one added to a bag already lying there neither shortens nor
        stretches the time of what was in it before. Where it lies and until
        when is written down (Store.lay_down), so that a restart puts it
        back. until, {uniq: epoch second}, is for things written down
        already with their time running -- put back after a restart
        (restore_ground), handed over from a pack's room (hand_over) -- and
        then nothing is written."""
        if not rows:
            return
        if self.heir is not None:
            self.heir.add_to_bag(cell, rows, until)
            return
        if until is None:
            t = time.time() + LOOT_LIFETIME
            until = {r["uniq"]: t for r in rows}
            self.store.lay_down(until, self.place, cell)
        bag = self.loot.get(cell)
        if bag is None:
            bag = self.loot[cell] = LootBag(cell, [])
            self.room.broadcast(("ss_loot", dict(s_status=1, hex=[cell])))
        for r in rows:
            if r["uniq"] not in bag.uniqs:
                bag.uniqs.append(r["uniq"])
            bag.until[r["uniq"]] = until[r["uniq"]]
        self.arm_bag(bag)

    def arm_bag(self, bag):
        """The bag's timer, set for the first of its things to run out.

        The deadlines are the wall clock's -- they outlive a restart (the
        ground table) -- and the loop's timer counts on its own clock, which
        never jumps. The two part whenever the wall clock is set: WSL steps
        it forward by most of a second every half minute or so, and a timer
        that slept the whole difference in one go came as late as all the
        steps it slept through, some twenty seconds on a quarter of an hour.
        So it never sleeps more than half of what is left, and expire_bag,
        finding nothing due yet, sets it again from the wall clock as it
        then reads; only the last second is slept in one piece. About ten
        wakes to a bag's fifteen minutes, and late by one step of the clock
        at most. Nothing goes early whatever the clock does: expire_bag
        takes only what the wall clock says is due."""
        if bag.expiry is not None:
            bag.expiry.cancel()
        first = min(bag.until.get(u, 0.0) for u in bag.uniqs)
        left = first - time.time()
        bag.expiry = asyncio.get_running_loop().call_later(
            max(0.0, min(left, max(left / 2.0, 1.0))), self.expire_bag, bag.cell)

    @property
    def place(self):
        """Where this room's ground is written down as lying (the ground
        table): its key (rooms.Room.key) as (loc, gx, gy) for a scene split
        by cell, and (loc, None, None) for a place that is one room -- a
        pack's room (encounters.py) too, whose ground is its location's own
        once the pack's room is gone (hand_over)."""
        key = getattr(self.room, "key", None)
        if isinstance(key, tuple) and len(key) == 3 and all(isinstance(k, int) for k in key):
            return key
        return (self.room.loc.id, None, None)

    def ground_cells(self):
        """The hexes a bag lies on here, for a newcomer (Fighter.entered)."""
        return sorted(self.loot)

    def hand_over(self, room):
        """Every bag of this room's ground onto the same cell of another
        room's, each thing with the time it has left. A pack's room goes
        with the last one out (encounters.Encounters.left), and what lay in
        it -- the pack's loot, a dead man's gear -- lies on in the room of
        its location, the cell's wasteland whoever walks in next enters;
        the ground table has had it there all along (place). Whatever this
        room still puts down -- a corpse that has not yet faded -- goes
        there too (heir)."""
        heir = room_combat(room, self.store)
        self.heir = heir
        for cell, bag in list(self.loot.items()):
            if bag.expiry is not None:
                bag.expiry.cancel()
            heir.add_to_bag(cell, [dict(uniq=u) for u in bag.uniqs], dict(bag.until))
        self.loot = {}

    def drop_loot(self, mob):
        """Item rows on the ground, owned by nobody, made through the store
        so they carry real serials the client can keep after picking up.

        A gold ingot (items.GOLD_INGOTS) comes only off a boss that keeps
        the hours (bosses.keeps_hours): one kill a window, the window
        remembered over a restart (boss_killed). With the rule off
        (LAVA_BOSS_HOURS=off) a boss is back every respawn delay, and an
        ingot on each of those kills would be gold without a limit, so its
        bag holds the rest of its loot and no ingot."""
        rows = []
        thing = mob.stats.role == "object"
        gold_ok = bosses.keeps_hours(mob.type_id)
        # What a timed event puts on top, by place (events.loot): a
        # prisoner's red armband in the uprising. An ore rock leaves its ore
        # beside the loot (production.yield_of).
        for type_id, count in mobs.loot_for(mob.stats, RNG, mob.quest_wants,
                              loc_id=self.room.loc.id,
                              killer_level=getattr(mob, "blueprint_killer_level", None)) \
                + events.loot(self.room.loc.id, mob.type_id, RNG) \
                + production.yield_of(mob.type_id):
            if items.out_of_game(type_id):
                continue            # (P) or retired by name; see items.out_of_game
            if type_id in items.GOLD_INGOTS and not gold_ok:
                continue            # gold off the hours' bosses only, above
            if thing and type_id == mobs.FALLBACK_LOOT:
                # A box, a target or a stone (world.STANDING_OBJECTS) holds
                # what its table rolls and what a quest wants of it -- and an
                # ammunition box its rounds -- not the cigarette that keeps a
                # creature's bag from being empty: nothing found, no bag.
                continue
            fields = inventory.new_fields(type_id, count)
            root = fields.pop("root")
            rows.append(self.store.create_item(LOOT_OWNER, type_id, root, **fields))
        return rows

    def close_bag(self, cell):
        bag = self.loot.pop(cell, None)
        if bag is None:
            return
        if bag.expiry is not None:
            bag.expiry.cancel()
        for f in self.fighters():
            # Except for whoever stands on the cell: the client opens every
            # bag from on top of it (Gamer.gotoLoot), and its window stays
            # open when the bag goes (Location.ss_loot only takes the bag
            # off the ground). Something dragged into that window -- or
            # dropped from the equipment -- must still land somewhere, or
            # the generic ss_upd answer would say it did while it did not.
            if f.loot == cell and f.sess.pos != cell:
                f.loot = None
        self.room.broadcast(("ss_loot", dict(s_status=0, hex=[cell])))

    def expire_bag(self, cell):
        """The bag's timer: whatever in it has lain its LOOT_LIFETIME goes
        for good -- the items row, a trophy's words with it (trophies.py),
        the ground row (Store.sweep_ground) -- and the bag with the last of
        it; the rest waits for its own time.

        A loot window open on the bag goes on showing what went: the client
        has no frame that takes a thing out of one (Loot listens to nothing
        but its own answers). Each such viewer keeps it in Fighter.ran_out,
        and his take-all takes it back out of his bag (ss_upd 3)."""
        bag = self.loot.get(cell)
        if bag is None:
            return
        bag.expiry = None
        t = time.time()
        gone = [u for u in bag.uniqs if bag.until.get(u, 0.0) <= t]
        if gone:
            viewers = [f for f in self.fighters() if f.loot == cell]
            if viewers:
                shown = [dict(uniq=r["uniq"], type_id=r["type_id"], root=r["root"])
                         for r in (self.store.item(u) for u in gone) if r is not None]
                for f in viewers:
                    f.ran_out += shown
            self.store.sweep_ground(gone, LOOT_OWNER)
            for uniq in gone:
                bag.uniqs.remove(uniq)
                bag.until.pop(uniq, None)
            log.info("  ..    %s on cell %d of %s lay out its time: gone",
                     ", ".join(str(u) for u in gone), cell, self.room.loc.title)
        if bag.uniqs:
            self.arm_bag(bag)
        else:
            self.close_bag(cell)

    def respawn(self, mob):
        """Back on its spawn cell under the same id: the client dropped the
        entity on lostUser and builds it afresh from lch;newUser, then asks
        for its details itself; the details are pushed anyway, as on entry.
        One back already, or sent away meanwhile -- a window of events.py
        shut before its respawn came -- is not made again."""
        if mob.alive or mob.away:
            return
        mob.reset()
        mob.cell = mob.home
        self.room.npcs[mob.eid] = rooms.NPC(mob.home, mob.type_id, world.MOB)
        for sess in list(self.room.players):
            sess.send("lch", newUser=mob.eid, pos=mob.home, rtype=world.MOB)
            sess.send_npc_info(mob.eid)

    # --- bosses and their hours ----------------------------------------------------------
    def keep_hours(self):
        """The room's bosses in step with the clock (bosses.py).

        Asked on every tick and, through Session.enter_room, before anybody
        arriving is shown who is here: an empty room has no tick, and a boss
        whose hour came or went meanwhile must be neither met outside it nor
        missed inside it by whoever walks in next.

        Away, with a window open that it has not yet come for, a boss arrives
        the way a respawn does -- lch;newUser, its details and bars -- on its
        own cell, whole. Standing here with no window open, it leaves: the
        lostUser a corpse fades with, and out of the room's inhabitants. Not
        in the middle of a fight, though -- nobody should lose a boss worn
        down to its last hit points to the clock -- so one that is fighting
        stays until the fight is over and starts no new one meanwhile
        (Mob.leaving). A corpse is corpse_gone's to put away. The timed
        windows of events.py are kept the same way, first.

        A boss still standing here when a window it has not come for opens
        was not sent away when the last one shut: the room was empty then
        (an empty room has no tick), or a fight kept it, or the two windows
        overlap. Nobody here now and no fight on, it is taken to have left
        and come back -- whole, on its own cell, its escort with it -- as it
        would have with anybody watching. With somebody here it stays as it
        is, and only its escort comes.

        Each boss keeps its own hours (bosses.slot_of): a warehouse's
        «Хозяин склада» comes once a day, the rest at the bosses' hours.
        """
        events.keep(self)
        if not self.bosses:
            return
        now = bosses.clock()
        for mob in self.bosses:
            due = bosses.slot_of(mob.type_id, now)
            if mob.away:
                if due is not None and due != mob.slot:
                    self.boss_arrives(mob, due)
            elif not mob.alive:
                continue
            elif due is not None:
                if due != mob.slot:
                    if (mob.slot is not None and not self.room.players
                            and mob.target is None and mob.aim is None):
                        self.boss_leaves(mob)
                        self.boss_arrives(mob, due)
                    else:
                        self.escort_back()
                # Standing here in a window counts as having come for it,
                # whether it arrived just now or the room was made in it.
                mob.slot, mob.leaving = due, False
            elif mob.target is None and mob.aim is None:
                self.boss_leaves(mob)
            else:
                mob.leaving = True

    def boss_arrives(self, mob, due):
        """Its window open: back on its own cell, whole, the way a respawn
        does it, and its escort with it (escort_back)."""
        mob.slot, mob.away = due, False
        self.respawn(mob)
        log.info("  ..    boss %d (%s) arrives in %s",
                 mob.eid, mob.stats.name, self.room.loc.title)
        self.escort_back()

    def escort_back(self):
        """A boss's escort comes with it: whoever of them was killed since
        is back now, and only now -- one whose corpse is still fading, as
        soon as it is gone (Mob.recalled, corpse_gone). The living stay
        put."""
        for guard in self.escorts:
            if guard.away:
                guard.away = False
                self.respawn(guard)
            elif not guard.alive:
                guard.recalled = True

    def boss_leaves(self, mob):
        """Its stay is over: gone from every screen here (Location.lch ->
        removePlayer) and from the room, until the next window."""
        mob.alive = False
        mob.away = True
        mob.leaving = False
        mob.target = None
        self.room.npcs.pop(mob.eid, None)
        self.room.broadcast(("lch", dict(lostUser=mob.eid)))
        log.info("  ..    boss %d (%s) leaves %s", mob.eid, mob.stats.name,
                 self.room.loc.title)

    def boss_spot(self, mob):
        """What a boss is written down by over a restart (the boss_kills
        table): the room's place, the boss's spawn cell and its type, which
        stay the same whatever ids the next run's room hands out."""
        return ":".join("-" if v is None else str(int(v))
                        for v in tuple(self.place) + (mob.home, mob.type_id))

    def boss_killed(self, mob):
        """The window a boss keeping the hours was killed in, written down
        (Store.boss_killed): a restart before the window shuts -- a deploy,
        a crash -- must not stand it up again with its loot and its gold
        ingots (recall_kills). mob.slot is the window it came for
        (keep_hours); with none there is nothing to write. A database that
        will not take the row costs the record and a line in the log, never
        the kill."""
        write = getattr(self.store, "boss_killed", None)
        if write is None or mob.slot is None:
            return
        try:
            write(self.boss_spot(mob), mob.slot)
        except Exception:
            log.exception("  !!    boss %d (%s) killed in %s: not written down",
                          mob.eid, mob.stats.name, self.room.loc.title)

    def recall_kills(self):
        """The room's bosses as a restart finds them, before anybody is
        shown the room (Session.enter_room makes this object first): one
        written down as killed in the window open now (boss_killed) starts
        away, as corpse_gone left it, and comes at the next window
        (keep_hours). Unreadable, the record is skipped with a line in the
        log, and the bosses stand as they did before there was one."""
        read = getattr(self.store, "boss_kills", None)
        if not self.bosses or read is None:
            return
        now = bosses.clock()
        # Each boss's own window (bosses.slot_of): a warehouse master's is
        # his day's hour.
        due = {m.eid: bosses.slot_of(m.type_id, now) for m in self.bosses}
        if all(d is None for d in due.values()):
            return
        try:
            killed = read([self.boss_spot(m) for m in self.bosses])
        except Exception:
            log.exception("  !!    the bosses killed in %s could not be read",
                          self.room.loc.title)
            return
        for mob in self.bosses:
            slot = due[mob.eid]
            if slot is not None and killed.get(self.boss_spot(mob)) == slot:
                mob.alive, mob.away, mob.slot = False, True, slot
                self.room.npcs.pop(mob.eid, None)
                log.info("  ..    boss %d (%s) of %s was killed in this window before"
                         " the restart: away until the next", mob.eid, mob.stats.name,
                         self.room.loc.title)


def room_combat(room, store):
    """The RoomCombat of a room, made on first use."""
    if room.combat is None:
        room.combat = RoomCombat(room, store)
    return room.combat


def restore_ground(rooms_, store, now=None):
    """The game server's start, before its first socket: whatever the last
    run left on the ground with time still to lie goes back where it lay --
    its room built for it (rooms.Rooms.get, as a first entry would build
    it), each thing on its cell with the time it has left, running out
    there whoever comes (LOOT_LIFETIME). A deploy restarts the game, and a
    dead player's gear lost to it would be a loss like any other. The rest
    is cleared (Store.clear_ground), and so is a thing whose room cannot be
    built any more. Returns (cleared, put back)."""
    swept = store.clear_ground(LOOT_OWNER, now)
    by_place = {}
    for row in store.on_ground(LOOT_OWNER):
        by_place.setdefault((row["loc"], row["gx"], row["gy"]), []).append(row)
    back = 0
    for (loc, gx, gy), rows in by_place.items():
        try:
            room = rooms_.get(loc if gx is None or gy is None else (loc, gx, gy))
        except Exception as exc:
            log.warning("  !!    no room at %s to put %d thing(s) back into (%s):"
                        " cleared", (loc, gx, gy), len(rows), exc)
            store.sweep_ground([r["uniq"] for r in rows], LOOT_OWNER)
            swept += len(rows)
            continue
        rc = room_combat(room, store)
        cells = {}
        for row in rows:
            cells.setdefault(row["cell"], []).append(row)
        for cell, lying in cells.items():
            rc.add_to_bag(cell, lying, {r["uniq"]: r["expires_at"] for r in lying})
        back += len(rows)
    return swept, back
