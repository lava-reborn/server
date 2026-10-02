"""Mining and production: ore out of the mines' rock, and what a town's
plant makes of it (the owner's «всё отложенное», stage 3, 2026-09-28).

The original's chain, as its texts and the wiki tell it:

  mining      an ore rock is a thing to break, not a place to click: «Медная
              порода», «Свинцовая порода», «Источник селитры» stand in the
              mines' tiers as creatures of the object role, with a health
              bar, and «Добывать можно любым ножом или же огнестрельным
              оружием, но гораздо удобней ... молотка геолога» (the wiki's
              «Добыча серебра»); the ore is what a rock leaves («(АХ)
              Свинцовая руда ... Мобы-хранители: Свинцовая порода»). The
              client has no mining action of its own (recon: «Добыча» is a
              specialisation's title and nothing else), so a rock is broken
              the way a quarry stone is, with any weapon;
  sorting     the terminals «Сортировка» of the mines' control rooms
              («Конвейер имеет смысл запускать при наличии 10 кусков
              свинцовой руды», texts.xml CrBQ№1010109);
  processing  the three lines of the processing base, bullets out of lead,
              powder out of saltpetre, cases out of copper («Запустить первую
              очередь обработки? ... 120 частей сортированной свинцовой руды»,
              CrBQ№1010001; «Повторное использование возможно через 20 минут»);
  assembly    the factory's ammunition line («Производство патронов 12мм. ...
              принести 3 ящика пуль, 12 мешков пороха, 9 коробок гильз»,
              CrBQ№1010061), of the calibres the factory's map label names.

The last three are quest rows, the original's own CrBQ family: data/
build_questgen_production.py writes a city's rows into data/questgen_
production.json from the texts. This module holds what is no quest: which
rocks stand where (world.belongs_here asks stands()), what a broken one
leaves (combat.RoomCombat.drop_loot asks yield_of()), the experience of
breaking one (mined_by, from RoomCombat.kill) and the numbers of the things
(items.static_info asks item_numbers()). A city is added by adding its rows
to the tables below; nothing here knows which city it is in.

Imports nothing that imports it: items, world and combat all ask here.
"""
import progression                 # no imports of its own

# --- the rocks -------------------------------------------------------------------
# The ore rocks that stand, by location: each tier of Вади-Хальфа's three ore
# mines (the label «Вход разрешен персонажам 4-8 ур.», quests.json 406-411 the
# gates) stands the rocks its own file puts there -- 20, 10 and 5 of copper in
# WH_Copper_Mine_lvl1..3, 20, 15 and 12 of lead in WH_Plumbum_Mine_lvl1..3,
# 10, 9 and 7 sources of saltpetre in WH_Nitre_Mine_lvl1..3 -- and nothing
# else of the object role: the electrical panel of every tier
# (Craft_Miner_elect_panel, 2022, [14]) stays out, as the quarry's does. The
# guards («Злой шахтёр», 1714) are fighters and stand anyway. RECOVERED
# placement, the rest of the object engine world.py's (STANDING_OBJECTS).
ORE_ROCKS = {
    1025: frozenset({1316}),        # WH_Copper_Mine_lvl1, WH_Stone_Copper_1
    1218: frozenset({1354}),        # WH_Copper_Mine_lvl2, WH_Stone_Copper_2
    1255: frozenset({1355}),        # WH_Copper_Mine_lvl3, WH_Stone_Copper_3
    1027: frozenset({1308}),        # WH_Plumbum_Mine_lvl1, WH_Stone_Plumbum_1
    1220: frozenset({1344}),        # WH_Plumbum_Mine_lvl2, WH_Stone_Plumbum_2
    1257: frozenset({1345}),        # WH_Plumbum_Mine_lvl3, WH_Stone_Plumbum_3
    1026: frozenset({1312}),        # WH_Nitre_Mine_lvl1, WH_Source_Nitre_1
    1219: frozenset({1349}),        # WH_Nitre_Mine_lvl2, WH_Source_Nitre_2
    1256: frozenset({1350}),        # WH_Nitre_Mine_lvl3, WH_Source_Nitre_3
}

# What a rock leaves when broken: (ore, pieces). The town's own ore, the (ВХ)
# copy of each series («(ВХ) Медная руда», «(ВХ) Свинцовая руда», «(ВХ)
# Селитра сырьевая»: copper_ore_1, plumbum_ore_1, nitre_ore_1). One piece a
# rock, DESIGNED: the texts ask for ten pieces a run of the conveyor, and a
# tier stands 5 to 20 rocks, back 45 seconds after they fall -- a run is a
# tier walked once. Whoever picks the bag up has it, as any corpse's.
ORE_YIELD = {
    1316: (3644, 1), 1354: (3644, 1), 1355: (3644, 1),     # copper
    1308: (3636, 1), 1344: (3636, 1), 1345: (3636, 1),     # lead
    1312: (3640, 1), 1349: (3640, 1), 1350: (3640, 1),     # saltpetre
}

# «Добыча», the specialisation of Промышленность a broken rock trains beside
# the skill (PersAttributes.spec10; quests.SPEC_KEYS "mining").
MINING_SPEC = 10
# Whether a broken rock teaches Промышленность (mined_by). Off, as every
# object is (combat.OBJECTS_PAY_XP, the owner's plan of 2026-09-28): a rock
# never fights back and stands again after 45 s, and a character's level
# is its best skill, so paying for rocks would raise one without a fight
# (the sixth level after some 330 rocks, the seventh after 800 more). The
# plant's rows teach the skill instead. Mining is what the skill is for
# (the wiki's «Добыча и переработка ресурсов из полезных ископаемых»):
# the owner's to turn on, the one switch. DESIGNED.
MINING_PAYS_XP = False


def stands(type_id, loc_id):
    """Whether an ore rock of this type stands in this location (ORE_ROCKS):
    world.belongs_here lets it, beside world.STANDING_OBJECTS."""
    return int(type_id) in ORE_ROCKS.get(loc_id, ())


def yield_of(type_id):
    """[(ore, pieces)] a broken rock of this type leaves, or []: laid beside
    its loot (combat.RoomCombat.drop_loot)."""
    got = ORE_YIELD.get(int(type_id))
    return [got] if got else []


def mined_by(fighter, mob):
    """A rock broken by a player: experience into Промышленность, and into
    «Добыча» on top where it is learned (Character.gain_xp spec_on_top, the
    way a kill pays its weapon's skill). The same curve as a kill
    (progression.mob_xp: the rock's level against the skill's, at the object
    role's xp_mult), so a level-5 rock teaches up to the seventh level of
    the skill and nothing past its grey gap -- the mines' own band. Only this
    skill: an object pays no weapon (combat.OBJECTS_PAY_XP), and mining is
    not fighting. Whoever struck the breaking blow; nothing while
    MINING_PAYS_XP is off. DESIGNED (2026-09-28), as the original's numbers
    are lost."""
    if not MINING_PAYS_XP or int(mob.type_id) not in ORE_YIELD:
        return
    ch = fighter.character()
    st = mob.stats
    xp = ch.carry_xp(progression.INDUSTRY, progression.mob_xp(
        mob.level, ch.skill_level(progression.INDUSTRY), 1.0, getattr(st, "xp_mult", 1)))
    if xp <= 0:
        return
    changed = ch.gain_xp(progression.INDUSTRY, xp, MINING_SPEC, spec_on_top=True)
    if any(changed.values()):
        fighter.sess.push_stats(**changed)
    if progression.moves_vitals(changed):
        fighter.sess.push_vitals()


# --- the things --------------------------------------------------------------------
# Each of the chain's series is five types, one a city, in the order the texts
# name them: (ВХ), (Аб), (Дн), (АХ), (Мр) -- the first four in one run of
# objects.xml, Мероэ's added after them (5602-5610), as the city was
# (data/build_orig_items.py rule 7i names them so).
ORE = {"plumbum": (3636, 3637, 3638, 3639, 5602),
       "nitre": (3640, 3641, 3642, 3643, 5603),
       "copper": (3644, 3645, 3646, 3647, 5604)}
SORTED = {"plumbum": (3672, 3673, 3674, 3675, 5605),
          "nitre": (3676, 3677, 3678, 3679, 5606),
          "copper": (3680, 3681, 3682, 3683, 5607)}
SACKS = {"bullet": (3648, 3649, 3650, 3651, 5608),       # «Ящик пуль»
         "powder": (3652, 3653, 3654, 3655, 5609),       # «Мешок пороха»
         "shell": (3656, 3657, 3658, 3659, 5610)}        # «Коробка гильз»
# The quarry's polishing mix and its four components («Полировочная смесь»,
# «Компонент №1..4»: Catalizator, Catalizator_part1..4).
POLISH_MIX, POLISH_PARTS = 2945, (2946, 2947, 2948, 2949)

# The ore: the (АХ) articles' «Цена в афро 1», «Количество предметов в стеке
# 100», «Допустимость продажи/обмена: да» (RECOVERED; one series, one price),
# and less than their «Вес 1 шт.» -- 4000 g of lead, 2000 of copper and
# saltpetre -- DESIGNED: the carry limit here is a flat 50 kg that counts
# what is worn (inventory.MAX_WEIGHT, UNDONE 4.10), and at the article's
# weights the original's own second conveyor (20 pieces) and its first run
# (40) could never be carried to the terminal. A quarter of copper's and
# saltpetre's; lead at 750 g, so that the 40 pieces of its first run fit
# beside the heaviest set (10 kg) and gun (6 kg) of the mines' band and
# 600 rounds. Back to 4000/2000 in this one table once the limit grows
# with the character.
ORE_WEIGHT = {"plumbum": 750, "nitre": 500, "copper": 500}
# What sorting and the lines make: no article, DESIGNED. Worth nothing at a
# stall (cost 0: the client itself refuses the sale, TradeInterface.
# checkSellItem), so ore made into sacks is never more afro than the ore and
# the rounds it ends as; they change hands between players as the ore does.
# Light enough that a run's worth fits the bag: 120-800 parts, 3-96 sacks.
SORTED_NUMBERS = dict(cost=0, weight=25, max_count=1000)
SACK_NUMBERS = dict(cost=0, weight=250, max_count=100)
# The quarry's mix and components: things of its quests alone, dropped for the
# one who wants them (quests.json 320, 321), worth nothing at a stall, where
# the designed frame's price of 10 sold each for 7.
POLISH_NUMBERS = dict(cost=0)

ITEM_NUMBERS = {}
for _kind, _types in ORE.items():
    for _t in _types:
        ITEM_NUMBERS[_t] = dict(cost=1, weight=ORE_WEIGHT[_kind], max_count=100)
for _types in SORTED.values():
    for _t in _types:
        ITEM_NUMBERS[_t] = dict(SORTED_NUMBERS)
for _types in SACKS.values():
    for _t in _types:
        ITEM_NUMBERS[_t] = dict(SACK_NUMBERS)
for _t in (POLISH_MIX,) + POLISH_PARTS:
    ITEM_NUMBERS[_t] = dict(POLISH_NUMBERS)


def item_numbers(type_id):
    """The numbers this module sets on a thing's frame (items.static_info),
    or None for a thing it has none for."""
    got = ITEM_NUMBERS.get(int(type_id))
    return dict(got) if got else None
