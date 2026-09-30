"""Keepsakes: the pieces of Энди Уорхол's collections, found in the bag
after a finished task now and then.

The original's own rule, the wiki's «Категория:Коллекции»: «Предметы для
коллекций появляются у вас в рюкзаке случайно при выполнении заданий ...
Задание на сбор коллекции можно взять у Коллекционера на Бензоколонке в
Вади-Хальфе» (Энди Уорхол, 2259, in the Свалка/Старая бензоколонка, 60).
What is collected is data: a row of data/quests.json marked "collection"
asks for its pieces (objs), and those pieces are what a hand-in may leave --
only while the row is live (it has a giver), so a collection switched off
leaves nothing of it (a season's, or the drivers' whose tickets lead to
closed cities).

DESIGNED, the rest. How often is lost: CHANCE. And a piece turns up only for
a collector -- somebody with the collection open in his journal and short of
that piece -- the way a quest's own things drop only for somebody whose open
quest wants them (quests.wanted_things, mobs.QUEST_TIER): nobody else's bag
fills with keepsakes he never asked for, and the finds stop once he has what
the collection wants. A service, a way and a collection's own hand-in leave
nothing: the rule speaks of tasks. One piece at most, beside the reward,
announced with it («Вы получили»: server.py Session.cmd_q_co gives it before
the ack).
"""
import os
import random

import quests
import travel

# The share of a collector's hand-ins that leave a piece: a piece he still
# wants each time, so a collection of six is six finds -- some sixty tasks,
# a week of the day's quests. DESIGNED.
CHANCE = float(os.environ.get("LAVA_KEEPSAKE_CHANCE", "0.1"))

RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

_ROWS = None


def collections():
    """[(type, live, (piece, ...))] of the rows marked "collection", in table
    order: live when the row has a giver."""
    global _ROWS
    if _ROWS is None:
        _ROWS = [(int(r["type"]), bool(r.get("give")),
                  tuple(int(o["obj"]) for o in r.get("objs", ())))
                 for r in quests.table_rows() if r.get("collection")]
    return _ROWS


def pool():
    """The pieces a hand-in may leave: those of the live collections."""
    out = []
    for _t, live, pieces in collections():
        if live:
            out += [p for p in pieces if p not in out]
    return out


def find(quest, wanted, rng=None):
    """[(type, 1)] -- the piece a hand-in of this quest leaves a collector
    whose open quests still want the pieces in wanted (quests.wanted_things)
    -- or []."""
    if quest is None or quest.service or travel.is_quest_way(quest.type):
        return []
    if quest.type in {t for t, _l, _p in collections()}:
        return []
    pieces = [p for p in pool() if p in wanted]
    rng = rng or RNG
    if not pieces or rng.random() >= CHANCE:
        return []
    return [(rng.choice(pieces), 1)]
