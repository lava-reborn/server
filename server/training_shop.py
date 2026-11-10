"""Free equipment stalls backed only by a private training inventory."""
from functools import lru_cache

import inventory
import items
import progression
import storage
import training_items


MAX_ROWS = 256
MAX_PURCHASE = 50



@lru_cache(maxsize=None)
def stock(post):
    if not post.line:
        return ()
    import training_supply
    return tuple(training_items.copy_type(source) for source in sorted(training_supply.sources(post.key)))



class Inventory(inventory.Inventory):
    def check_post(self, eid):
        ground = self.sess.ground
        post = ground.posts.get(eid)
        npc = self.sess.room.npc(eid)
        if ground.closed or ground.phase != 'ready' or post is None or not post.line or npc is None:
            raise ValueError('Торговля доступна у стоек после завершения боя')
        if not progression.within_reach(self.sess.live_cell(), npc.cell,
                                        self.sess.loc.width, self.sess.loc.height):
            raise ValueError('Подойдите к торговцу полигона')
        if self.store is not ground.store:
            raise ValueError('Тестовые предметы доступны только клону полигона')
        return post

    def open_trade(self, params):
        self.ack(inventory.RES_REFUSED)

    def ss_upd(self, params):
        self.ack(inventory.RES_REFUSED)
        return True

    def issue(self, type_id, count):
        si = items.params_of(type_id)
        root = items.root_of(type_id)
        heapable = root in items.HEAPABLE_ROOTS
        maximum = si.get('max_count', 1) if heapable else MAX_PURCHASE
        if not 1 <= count <= maximum:
            raise ValueError('Недопустимое количество или предел предметов')
        rows = 1 if heapable else count
        # Bound memory/Flash work as well as weight; a zero-weight type must
        # never allow an unlimited number of separate objects in one session.
        if len(self.rows()) + rows > MAX_ROWS:
            raise ValueError('Недопустимое количество или предел предметов')
        if self.total_weight() + si.get('weight', 0) * count > self.carry_limit():
            raise ValueError('Недостаточно свободного веса')
        ground = self.sess.ground
        if self.store is not ground.store or not training_items.is_copy(type_id):
            raise ValueError('Выдача доступна только клону')
        if self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq'] > ground.serial_base + (1 << 20) - MAX_ROWS:
            raise ValueError('Недопустимое количество или предел предметов')
        # No live store and no purse participate. Publish item frames only
        # after all copies have committed, including a multi-item purchase.
        with storage.atomic(self.store.db):
            created = ([self.create(type_id, count)] if heapable else
                       [self.create(type_id) for _ in range(count)])
        return created
