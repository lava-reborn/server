"""Free equipment stalls backed only by a private training inventory."""
from functools import lru_cache

import inventory
import items
import progression
import storage
import training_items

MAX_ROWS = 256
MAX_PURCHASE = 50
MAX_STOCK = 128


@lru_cache(maxsize=None)
def stock(post):
    if not post.line:
        return ()
    import training_ground as training
    sources = [source for source, (category, _level, _label) in training.item_catalogue().items()
               if category == post.category and (post.line == 'all' or training.item_line(source) == post.line)
               and (post.weapon_class < 0 or post.weapon_class == (
                   6 if items.root_of(source) == items.COLD_ARM else
                   items.params_of(source).get('weapon_type', -1)))]
    sources.sort(key=lambda source: (training.item_catalogue()[source][1],
                                    training.item_catalogue()[source][2], source))
    if len(sources) > MAX_STOCK:
        raise ValueError('Split the training stock before adding more items: ' + post.key)
    training_items.prepare(training.item_catalogue())
    return tuple(training_items.copy_type(source) for source in sources)


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
        try:
            eid = int(params.get('target', 0))
            post = self.check_post(eid)
        except (ValueError, TypeError):
            self.ack(inventory.RES_REFUSED)
            return
        self.sess.stop_walk()
        self.trade = inventory.TradeSession(eid, post.resource, self.sess.loc.id)
        self.trade.training_stock = stock(post)
        self.ack(inventory.RES_OK)

    def ss_upd(self, params):
        try:
            code = int(params.get('s_status', -1))
        except (TypeError, ValueError):
            code = -1
        if code == inventory.UPD_CLOSE:
            if self.trade is not None:
                self.trade = None
                self.sess.ground.remember_outfit()
                self.sess.ground.save_settings()
            return True  # Native close has no acknowledgement handler.
        try:
            if self.trade is None:
                raise ValueError('Нет открытой торговли')
            self.check_post(self.trade.npc_id)
        except ValueError:
            self.ack(inventory.RES_REFUSED)
            return True
        if code == inventory.UPD_BUY:
            self.buy_free(params)
        elif code == inventory.UPD_SELL:
            self.sell_free(params)
        else:
            self.ack(inventory.RES_REFUSED)
        return True

    def buy_free(self, params):
        try:
            index = int(str(params.get('obj', '')), 16)
            count = int(params.get('param', 1))
        except (ValueError, TypeError):
            self.ack(inventory.RES_REFUSED)
            return
        if not 0 <= index < len(self.trade.training_stock):
            self.ack(inventory.RES_NOT_FOUND)
            return
        type_id = self.trade.training_stock[index]
        si = items.params_of(type_id)
        root = items.root_of(type_id)
        heapable = root in items.HEAPABLE_ROOTS
        maximum = si.get('max_count', 1) if heapable else MAX_PURCHASE
        if not 1 <= count <= maximum:
            self.ack(inventory.RES_REFUSED)
            return
        rows = 1 if heapable else count
        # Bound memory/Flash work as well as weight; a zero-weight type must
        # never allow an unlimited number of separate objects in one session.
        if len(self.rows()) + rows > MAX_ROWS:
            self.ack(inventory.RES_REFUSED)
            return
        if self.total_weight() + si.get('weight', 0) * count > self.carry_limit():
            self.ack(inventory.RES_OVERLOAD)
            return
        ground = self.sess.ground
        if self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq'] > ground.serial_base + (1 << 20) - MAX_ROWS:
            self.ack(inventory.RES_REFUSED)
            return
        # No live store and no purse participate. Publish item frames only
        # after all copies have committed, including a multi-item purchase.
        with storage.atomic(self.store.db):
            created = ([self.create(type_id, count)] if heapable else
                       [self.create(type_id) for _ in range(count)])
        ground.remember_outfit()
        self.ack(inventory.RES_OK)
        ground.inventory_state()
        for row in created:
            self.push_status(row, 1)
            self.push_di(row)


    def sell_free(self, params):
        row = self.find(params.get('obj'))
        if row is None or row['slot'] != inventory.BAG or not training_items.is_copy(row['type_id']):
            self.ack(inventory.RES_NOT_FOUND)
            return
        heapable = row['root'] in items.HEAPABLE_ROOTS
        try:
            count = int(params.get('param', row['count']) or row['count']) if heapable else 1
        except (TypeError, ValueError):
            self.ack(inventory.RES_REFUSED)
            return
        if not 1 <= count <= row['count']:
            self.ack(inventory.RES_REFUSED)
            return
        left = row['count'] - count if heapable else 0
        with storage.atomic(self.store.db):
            if left:
                self.store.update_item(row['uniq'], count=left)
            else:
                self.store.delete_item(row['uniq'])
        self.sess.ground.remember_outfit()
        self.ack(inventory.RES_OK)
        self.sess.ground.inventory_state()
        if left:
            self.push_di(self.store.item(row['uniq']))
        else:
            self.push_status(row, 0)
