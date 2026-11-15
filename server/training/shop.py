"""Free equipment stalls backed only by a private training inventory."""
from functools import lru_cache
import logging

import inventory
import items
import progression
import storage
from training import items as training_items


log = logging.getLogger(__name__)

MAX_ROWS = 256
MAX_PURCHASE = 50



@lru_cache(maxsize=None)
def stock(post):
    if not post.line:
        return ()
    from training import supply as training_supply
    return tuple(training_items.copy_type(source) for source in sorted(training_supply.sources(post.key)))



class Inventory(inventory.Inventory):
    def worn_rows(self):
        slots = inventory.WEAR_SLOTS
        return self.store.db.execute(
            'SELECT type_id,brk FROM items WHERE char_id=? AND slot IN (%s)' %
            ','.join('?' for _ in slots), (self.char_id, *slots)).fetchall()

    def validate_creation(self, type_id):
        if self.store is not self.sess.ground.store or not training_items.is_copy(type_id):
            raise ValueError('Предметы доступны только тренировочному клону')

    def in_slot(self, slot):
        # Bots inspect their active weapon frequently; do not materialise the
        # whole private bag to read one slot. The ordering matches items_of.
        row = self.store.db.execute(
            'SELECT * FROM items WHERE char_id=? AND slot=? ORDER BY uniq LIMIT 1',
            (self.char_id, slot)).fetchone()
        return dict(row) if row is not None else None

    def create(self, type_id, count=1, slot=inventory.BAG, char_id=None):
        # All creation paths (including split/unload), not only the supplier,
        # share the same private row and serial budget.
        ground = self.sess.ground
        if self.store is not ground.store or not training_items.is_copy(type_id):
            raise ValueError('Предметы полигона создаются только в частном хранилище')
        owner = char_id or self.char_id
        size = self.store.db.execute(
            'SELECT COUNT(*) AS n FROM items WHERE char_id=?', (owner,)).fetchone()['n']
        sequence = self.store.db.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()
        if size >= MAX_ROWS or (sequence and sequence['seq'] >= ground.serial_base + (1 << 20) - 1):
            raise ValueError('Достигнут предел предметов полигона; сначала сдайте лишние вещи')
        return super().create(type_id, count, slot, char_id)

    def private_mutation(self, operation, params):
        """Reuse native packets, but release them only after the private commit."""
        original_send = self.sess.send
        had_send = 'send' in self.sess.__dict__
        frames = []
        self.sess.send = lambda command, **fields: frames.append((command, fields))
        failed = None
        try:
            with storage.atomic(self.store.db):
                operation(params)
        except Exception as exc:
            failed = exc
            if not isinstance(exc, ValueError):
                log.exception('Private inventory operation failed for %s', self.char_id)
        finally:
            if had_send:
                self.sess.send = original_send
            else:
                del self.sess.send
        if isinstance(failed, storage.CommitError):
            self.sess.close(force=True)
        elif failed is not None:
            self.ack(inventory.RES_REFUSED)
        else:
            for command, fields in frames:
                original_send(command, **fields)

    def ss_heap_c(self, params):
        raw = params.get('num', 0)
        try:
            if isinstance(raw, bool):
                raise ValueError('boolean count')
            count = int(str(raw))
            if count < 0:
                raise ValueError('negative count')
        except (ValueError, TypeError):
            self.ack(inventory.RES_REFUSED)
            return
        self.private_mutation(super().ss_heap_c, dict(params, num=count))

    def use_unload(self, params):
        self.private_mutation(super().use_unload, params)

    def switch_profile(self, simulator):
        """Change only private copy identities; preserve every instance field.

        Different static ids keep both profiles' client caches independent.
        A single transaction commits all rows before publishing any update.
        """
        if self.store is not self.sess.ground.store:
            raise ValueError('Профиль меняется только внутри полигона')
        changed = []
        for row in self.rows():
            source = training_items.profile_source(row['type_id'])
            if not training_items.is_copy(row['type_id']) or not training_items.available(source, simulator):
                raise ValueError('Сдайте предметы, исключённые из нового профиля симулятора, перед сменой правил.')
            target = training_items.copy_type(source, simulator=simulator)
            if (row['root'] == items.FIRE_ARM
                    and row['ammo_count'] > items.params_of(target)['clip_size']):
                raise ValueError('Разрядите оружие перед сменой профиля: в новом магазине меньше места.')
            if target != row['type_id']:
                changed.append((dict(row), target))
        with storage.atomic(self.store.db):
            for row, target in changed:
                result = self.store.db.execute(
                    'UPDATE items SET type_id=? WHERE uniq=? AND char_id=? AND type_id=?',
                    (target, row['uniq'], self.char_id, row['type_id']))
                if result.rowcount != 1:
                    raise ValueError('Снаряжение изменилось; повторите смену профиля')
        for row, target in changed:
            self.push_status(row, 0)
            current = self.store.item(row['uniq'])
            self.push_status(current, 1)
            self.push_di(current)
        return bool(changed)

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
        source = training_items.profile_source(type_id)
        if (not training_items.available(source, ground.rules.simulator_formulas)
                or type_id != training_items.copy_type(source, simulator=ground.rules.simulator_formulas)):
            raise ValueError('Предмет не соответствует выбранному профилю')
        if self.store.db.execute("SELECT seq FROM sqlite_sequence WHERE name='items'").fetchone()['seq'] > ground.serial_base + (1 << 20) - MAX_ROWS:
            raise ValueError('Недопустимое количество или предел предметов')
        # No live store and no purse participate. Publish item frames only
        # after all copies have committed, including a multi-item purchase.
        with storage.atomic(self.store.db):
            created = ([self.create(type_id, count)] if heapable else
                       [self.create(type_id) for _ in range(count)])
        return created
