"""Read-only equipment posts inside private ranges; existing game resources."""
from dataclasses import dataclass, replace


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


# Catalogue services: variants and upgrades are selected in the window.
POSTS = (
    Post('computer', 'Компьютер полигона', 1263, 36, 114, 'mob'),
    Post('player', 'Инструктор · навыки и наборы', 1997, 28, 114, 'skills'),
    Post('weapons', 'Оружейник', 2514, 20, 126, 'weapon', line='all'),
    Post('armoury', 'Броня', 1006, 25, 126, 'armour', line='all'),
    Post('supplies', 'Боеприпасы и подсумки', 1006, 30, 126, 'ammo', line='all'),
    Post('medical', 'Медицина', 1006, 34, 126, 'medicine', line='all'),
    Post('boosts', 'Баффы', 1006, 39, 126, 'buff', line='all'),
    Post('specialist', 'Особое оружие', 2391, 44, 126, 'special_weapon', line='all'),
    Post('archive', 'Архив предметов', 1006, 32, 133, 'souvenir', line='all'),
)
BY_KEY = {post.key: post for post in POSTS}
NAME_BASE = 8_100_000
NAMES = {NAME_BASE + index: post.title + '<br>Испытательный полигон'
         for index, post in enumerate(POSTS)}
NAME_IDS = {post.key: NAME_BASE + index for index, post in enumerate(POSTS)}
# Categories belong to the isolated range, not the ordinary spawn tables.
from training_opponents import GROUPS as MOB_GROUPS

# The city arena is a private copy; its original NPCs/geometry are never edited.
HALFA_POSTS = tuple(replace(post, x=post.x - 4,
                           y=96 if post.key in ('computer', 'player') else 118 if post.key == 'archive' else 112)
                   for post in POSTS)

def posts_for(location):
    return HALFA_POSTS if location == 59 else POSTS
