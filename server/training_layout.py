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


# Six catalogue services: variants and upgrades are selected in the window.
POSTS = (
    Post('computer', 'Компьютер полигона', 1263, 36, 114, 'mob'),
    Post('player', 'Инструктор · навыки и восстановление', 1997, 28, 114, 'skills'),
    Post('weapons', 'Оружейник', 2514, 17, 128, 'weapon', line='all'),
    Post('armoury', 'Броня', 1006, 23, 128, 'armour', line='all'),
    Post('supplies', 'Боеприпасы и подсумки', 1006, 29, 128, 'ammo', line='all'),
    Post('medical', 'Медицина', 1006, 35, 128, 'medicine', line='all'),
    Post('boosts', 'Баффы', 1006, 41, 128, 'buff', line='all'),
    Post('specialist', 'Особое оружие', 2391, 47, 128, 'special_weapon', line='all'),
)
BY_KEY = {post.key: post for post in POSTS}
NAME_BASE = 8_100_000
NAMES = {NAME_BASE + index: post.title + '<br>Испытательный полигон'
         for index, post in enumerate(POSTS)}
NAME_IDS = {post.key: NAME_BASE + index for index, post in enumerate(POSTS)}
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
