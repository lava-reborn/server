"""Read-only equipment posts inside private ranges; existing game resources."""
from dataclasses import dataclass, replace
from training import content


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
POSTS = tuple(Post(**row) for row in content.data()['posts'])

BY_KEY = {post.key: post for post in POSTS}
NAME_BASE = 8_100_000
NAMES = {NAME_BASE + index: post.title + '<br>Испытательный полигон'
         for index, post in enumerate(POSTS)}
NAME_IDS = {post.key: NAME_BASE + index for index, post in enumerate(POSTS)}
# Categories belong to the isolated range, not the ordinary spawn tables.
from training.opponents import GROUPS as MOB_GROUPS

# The city arena is a private copy; its original NPCs/geometry are never edited.
HALFA_POSTS = tuple(replace(post, x=post.x + content.location(59)['post_x_offset'],
                           y=content.location(59)['control_row'] if post.key in ('computer', 'player')
                           else content.location(59)['archive_row'] if post.key == 'archive'
                           else content.location(59)['stock_row'])
                   for post in POSTS)

def posts_for(location):
    return HALFA_POSTS if location == 59 else POSTS
