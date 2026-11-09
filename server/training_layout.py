"""Read-only equipment posts inside private ranges; existing game resources."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Post:
    key: str
    title: str
    resource: int
    x: int
    y: int
    category: str
    weapon_class: int = -1
    line: str = ''

    def cell(self, width):
        return self.y * width + self.x


# The category artwork is reused; the A/P/G columns have distinct captions.
CATEGORIES = (
    ('pistols', 'Пистолеты', 1200, 'weapon', 0),
    ('shotguns', 'Дробовики', 76, 'weapon', 1),
    ('smg', 'Пистолет-пулемёты', 1163, 'weapon', 5),
    ('assault', 'Автоматы', 950, 'weapon', 2),
    ('rifles', 'Винтовки', 380, 'weapon', 3),
    ('machineguns', 'Пулемёты', 2514, 'weapon', 4),
    ('melee', 'Холодное оружие', 2279, 'weapon', 6),
    ('armour', 'Броня', 1006, 'armour', -1),
    ('pouches', 'Подсумки', 1006, 'pouch', -1),
    ('ammo', 'Боеприпасы', 1006, 'ammo', -1),
    ('medicine', 'Медицина', 1006, 'medicine', -1),
    ('buffs', 'Баффы', 1006, 'buff', -1),
    ('special', 'Коллекционное', 1006, 'special_weapon', -1),
    ('event', 'Ивентовое лечение', 1006, 'event_medicine', -1),
)
POSTS = (
    Post('computer', 'Компьютер полигона', 1263, 36, 114, 'mob'),
    Post('player', 'Инструктор · навыки и восстановление', 1997, 28, 114, 'skills'),
) + tuple(
    Post(key + '_' + line, title + ' (' + line + ')', resource,
         6 + index * 4,
         134 - column * 6, category, weapon_class, line)
    for index, (key, title, resource, category, weapon_class) in enumerate(CATEGORIES)
    if key != 'special'
    for column, line in enumerate(('A', 'P', 'G'))
) + (Post('special', 'Контрабанда и коллекционное', 2391, 54, 128, 'special_weapon', line='all'),
     Post('experimental', 'Специальное оружие', 5707, 54, 122, 'experimental_weapon', line='all'))
BY_KEY = {post.key: post for post in POSTS}
NAME_BASE = 8_100_000
NAMES = {NAME_BASE + index: post.title + '<br>Испытательный полигон'
         for index, post in enumerate(POSTS)}
NAME_IDS = {post.key: NAME_BASE + index for index, post in enumerate(POSTS)}
NAMES[NAME_IDS['special']] = 'Контрабанда<br>Коллекционное оружие'
NAMES[NAME_IDS['experimental']] = 'Спецоружие<br>Учебное и необычное'
MOB_GROUPS = {
    'all': 'Все противники', 'camps': 'Лагеря', 'mines': 'Шахты',
    'bosses': 'Боссы', 'dogs': 'Собаки', 'crocodiles': 'Крокодилы',
    'vagrants': 'Бродяги', 'animals': 'Другие животные', 'other': 'Другие противники',
}


def mob_group(info):
    name=info.get('name','').casefold()
    resource=info.get('resource','').casefold()
    if info.get('role')=='boss':
        return 'bosses'
    if 'miner' in name:
        return 'mines'
    if 'dog' in resource:
        return 'dogs'
    if 'crocodile' in resource:
        return 'crocodiles'
    if 'bich' in resource or 'bomj' in name:
        return 'vagrants'
    if info.get('role')=='animal':
        return 'animals'
    if name.partition('_')[0] in ('nc','na','lu','ja','mg','st','zd','jm','pc','pt'):
        return 'camps'
    return 'other'
