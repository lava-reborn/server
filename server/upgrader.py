"""The upgrader's window (ss_create;s_type=5): one window for every service
an upgrader (mobs.xml class Upgrader, world.UPGRADER) has.

The client knows one such window (Upgrader.as, Upgrade.as). userInfo_Upgrader
carries three parallel lists, in_types, out_types and costs in hundredths of
an ounce; the window lists what of the bag is an in_type, a click shows the
out_type and its cost, and «Улучшить» sends ss_upd;s_status=1;obj=x<oid>;
param=<out type> (Upgrade._upgradeItem), waiting on exactly one cmdAck (0
is the success picture, anything else the failure one). s_status=0 closes,
sent bare, with no acknowledgement registered (Upgrade.close).

Two services fill it, each in its own module:

  weapons  craft.py: a master's upgrade recipes, the gun in and its
           modification out, for nothing but the blueprint the upgrade asks
           of the bag (craft.upgrader_lists, craft.upgrade) -- the [Q]
           weapons masters 5771 and 7548;
  sets     setcraft.py: a set's piece for the next rung's, and the gold-set
           exchange, for gold (setcraft.window, setcraft.upgrade) -- Генри,
           Генри ст and Тиль.

An upgrader with both shows both, the weapons first (lists); one with
neither shows the empty lists every upgrader had before. The recipes take
guns and the rungs clothing, so an upgrade goes to the service of the thing
dragged in (service_of), which gives its own answers: what it refuses and
with which code, what it takes and what it gives.

The window is the upgrader's beside him. The session keeps who opened it
and in which room; leaving that room (server.Session.leave_room: the map, a
way, a death, /goto, a dropped socket) forgets him (Window.left), and so do
another ss_create (server.Session.windows_gone) and the close. An upgrade
sent after the player left -- only a modified client sends one -- is still
this window's frame, answered with the one refusal it waits on, and moves
nothing; not the bare cmdAck 0 an unknown ss_upd gets, which would play the
success picture.
"""
import logging

import craft
import inventory
import items
import setcraft
import world

log = logging.getLogger("lava")

SESSION_UPGRADE = 5                 # StuffManager.SESSION_UPGRADE
UPD_CLOSE, UPD_UPGRADE = 0, 1       # Upgrade.close / Upgrade._upgradeItem


def lists(npc_type, loc_id=None):
    """userInfo_Upgrader's in_types, out_types and costs for this NPC: its
    weapon recipes (craft.py), then its set rungs (setcraft.py), in step."""
    out = dict(in_types=[], out_types=[], costs=[])
    for part in (craft.upgrader_lists(npc_type), setcraft.window(npc_type, loc_id)):
        for key in out:
            out[key] += part[key]
    return out


def service_of(row):
    """The module whose upgrade a bag row is: craft for a weapon, setcraft
    for anything else."""
    return craft if row["root"] in (items.FIRE_ARM, items.COLD_ARM) else setcraft


class Window:
    """One connection's upgrader window. Owned by server.Session.

    Told apart from the other windows by the session's npc_session
    (SESSION_UPGRADE), which windows_gone clears for any other ss_create.
    """

    def __init__(self, sess):
        self.sess = sess
        self.open_ = False
        self.npc_type = None
        self.room = None

    def open(self, p):
        """ss_create;s_type=5;target=<npc> -> one cmdAck: 0 opens the window
        (Upgrade.createSession), anything else puts up «Невозможно улучшить
        снаряжение у <res>». The window then asks for the bag (ss_get),
        which the inventory answers as any bag request."""
        sess = self.sess
        try:
            target = int(p.get("target", 0) or 0)
        except (TypeError, ValueError):
            target = 0
        entry = sess.room.npc(target) if sess.room is not None else None
        if not entry or world.entity_root(entry.type_id, entry.root) != world.UPGRADER:
            sess.inv.ack(inventory.RES_NOT_FOUND)
            return
        if not sess.char_id:
            sess.inv.ack(inventory.RES_REFUSED)
            return
        self.open_ = True
        self.npc_type, self.room = entry.type_id, sess.room
        sess.npc_session = SESSION_UPGRADE
        sess.inv.ack(inventory.RES_OK)

    def left(self):
        """The player is out of the room the window was opened in: its
        upgrader stays behind. The window's frames are still its own."""
        self.npc_type = self.room = None

    def close(self):
        """Closed, or another window opened (server.Session.windows_gone)."""
        self.open_ = False
        self.npc_type = self.room = None

    def master(self):
        """The type of the upgrader who opened the window while he stands in
        the room with the player; None once the player has left him. By type,
        not entity: a re-shown NPC (events.py) is the same upgrader."""
        room = self.sess.room
        if self.npc_type is None or room is None or room is not self.room:
            return None
        if not any(n.type_id == self.npc_type for n in room.npcs.values()):
            return None
        return self.npc_type

    def ss_upd(self, p):
        """ss_upd inside the window; False when the window is not open. 0
        closes and is sent bare; 1 upgrades, with exactly one cmdAck."""
        sess = self.sess
        if not self.open_ or sess.npc_session != SESSION_UPGRADE:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == UPD_CLOSE:
            sess.npc_session = None
            self.close()
            return True
        if code != UPD_UPGRADE:
            sess.inv.ack(inventory.RES_REFUSED)
            return True
        row = sess.inv.find(p.get("obj"))
        if row is None:
            sess.inv.ack(inventory.RES_NOT_FOUND)
            return True
        if service_of(row) is craft:
            sess.quest_write(self.upgrade_weapon, p)
            return True
        sess.quest_write(self.upgrade_set, p)
        return True

    def upgrade_set(self, p):
        """Validate again under the character lock; publish only after commit."""
        sess = self.sess
        row = sess.inv.find(p.get("obj"))
        if row is None:
            sess.inv.ack(inventory.RES_NOT_FOUND)
            return
        try:
            out = int(p.get("param", 0) or 0)
        except (TypeError, ValueError):
            out = 0
        setcraft.upgrade(sess, self.master(), row, out)

    def upgrade_weapon(self, p):
        """Re-read the item under the character's transaction lock."""
        sess = self.sess
        row = sess.inv.find(p.get("obj"))
        if row is None:
            sess.inv.ack(inventory.RES_NOT_FOUND)
            return
        try:
            out = int(p.get("param", 0) or 0)
        except (TypeError, ValueError):
            out = 0
        craft.upgrade(sess, self.master(), row, out)
