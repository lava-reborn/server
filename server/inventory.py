"""Item instances: the bag, the eight slots, a stall, and loading a gun.

Everything the client does with an item goes through an instance id on the
wire, and the client takes the item's class and type out of that id rather
than out of any frame name, so the id layout is the contract this module is
built around.

The oid, as the client reads it
-------------------------------

    <uniq hex><type_id: exactly 4 hex><root: exactly 2 hex>

ItemFactory.create hands the string to MDString.parseBigUINT(oid, 4, 2), which
slices from the END: the last 2 characters become the root class, the 4 before
them the type id, and whatever is left in front, `buint.slice(0, length-6)`,
is the serial, read as Number("0x" + rest). Three things follow:

  * The serial has no fixed width. One hex digit is the minimum, because
    Number("0x") is NaN, and StuffManager.createItem drops any id shorter
    than two characters or equal to "0" anyway. There is no maximum short of
    the double the client parses into, exact to 2^53; the rowid used here
    stays many orders below that.
  * Item.set id also computes uID = Number(oid.substr(0, length-6)) -- a
    DECIMAL parse of the same hex serial, NaN whenever a letter appears.
    uID is written there and read nowhere (grepped across all 395 classes),
    so it costs nothing, but it is why the layout is hex-with-fixed-tail and
    not something friendlier.
  * The client never rebuilds the id: BigUINT.toString prefixes "x" and
    concatenates the clusters, and BigUINTCluster(oid) with no size calls
    toString(16) on a String, which returns it unchanged. What is sent back
    in ss_get_di/ss_move/ss_use is byte for byte what ss_ack carried. The
    parser strips the "x" (SCDataParser.getBigUINTData) and keys
    ItemFactory.itemStore on the rest, so every ss_di_*/ss_obj_status frame
    must spell the id exactly as the list did: lowercase, no padding of the
    serial, type and root zero-padded to 4 and 2.

An empty slot is the element "0" (sent as x0): createItem skips it, and the
bank and loot windows treat the first "0" after the bag as the divider
between the bag and the session's own contents.

Containers, in the order ss_ack must list them (PersEquip.ss_ack)
--------------------------------------------------------------

The client reads the ss_ack list against the mask it sent in ss_get -- not
against anything in the frame -- and slices in a fixed order:

    bit 1   splice(0, 6)   head, camouflage, armor, belt, legs, boots
    bit 2   splice(0, 2)   primary, secondary
    bit 8   the rest       bag
    bit 16  Bank/Loot: everything after the first "0" is the session

A slot code in ss_move/ss_obj_move is maskIndex << 8 | index, which gives the
numbers below (PersEquip constructor).
"""
import asyncio
import logging
import math

import items
import world
from protocol import BigUInt, Str

log = logging.getLogger("lava")

# --- the oid ----------------------------------------------------------------

def oid(uniq, type_id, root):
    return "%x%04x%02x" % (uniq, type_id, root)


def oid_of(row):
    return oid(row["uniq"], row["type_id"], row["root"])


def parse_oid(text):
    """(uniq, type_id, root) from a wire id without its "x", or None."""
    text = str(text or "").strip().lower()
    if len(text) < 7:
        return None
    try:
        return int(text[:-6], 16), int(text[-6:-2], 16), int(text[-2:], 16)
    except ValueError:
        return None


EMPTY = BigUInt("0")

# --- containers -------------------------------------------------------------

HEAD, CAMO, ARMOR, BELT, LEGS, BOOTS = 256, 257, 258, 259, 260, 261
PRIMARY, SECONDARY = 512, 513
BAG = 2048

WEAR_SLOTS = (HEAD, CAMO, ARMOR, BELT, LEGS, BOOTS)
HAND_SLOTS = (PRIMARY, SECONDARY)

# ss_get masks (Bag/Slot.maskIndex in the PersEquip constructor)
MASK_WEAR, MASK_HANDS, MASK_BAG, MASK_SESSION = 1, 2, 8, 16

# Carry limit in grams. rp_info sends the same figure as max_weight; the
# client only warns from it, the refusal is ours (WeightPan.count sums the
# bag and all eight slots, so the total here does the same).
MAX_WEIGHT = 50000

# Trader multipliers, as sent in userInfo_Trader (server.send_npc_info). The
# client multiplies prices by them before it shows them, so a change on one
# side without the other shows one price and charges another.
PMOD = 1
SMOD = 1

# cmdAck codes the client words (ErrorReport.as:58-81)
RES_OK = 0
RES_REFUSED = 3
RES_NO_AP = 11
RES_NOT_FOUND = 12
RES_NO_AMMO = 13
RES_WRONG_AMMO = 14
RES_LOADED = 15
RES_BROKEN = 16
RES_NOT_READY = 17
RES_NO_ITEM = 19
RES_NO_MONEY = 21
RES_OVERLOAD = 27

# ss_use bits (Item.set actions)
USE_DELETE, USE_LOAD, USE_IDLE, USE_TARGET = 0, 1, 2, 4
USE_ITEM, USE_FIRE, USE_UNLOAD, USE_MODE = 8, 16, 32, 64

# ss_upd codes inside a trade session (Trade.as:11-19)
UPD_CLOSE, UPD_BUY, UPD_SELL, UPD_REPAIR = 0, 1, 2, 3
UPD_BUY_GOLD, UPD_REPAIR_GOLD, UPD_REG_TROPHY, UPD_RESTORE = 4, 5, 6, 7
UPD_BGPOINTS_BUY = 8

SESSION_TRADE = 1

# Which ss_di_* frame describes an instance. ItemFactory registers all six
# and routes each to the same updateItemDI, so the name is documentation
# more than dispatch; the fields are what matters (items.md 1.2).
DI_COMMAND = {
    items.FIRE_ARM: "ss_di_firearm",
    items.WEAR: "ss_di_wear",
    items.HEAL: "ss_di_heal",
    items.AMMO: "ss_di_heap",
    items.TRASH: "ss_di_heap",
    items.COLD_ARM: "ss_di_coldarm",
    items.TROPHY: "ss_di_trophy",
}

# What a fresh character owns: the tier-one pistol and one pack of the rounds
# it takes. Enough to try every verb in this module without a stall.
STARTER_KIT = ((4380, 1), (items.AMMO_9MM[0], items.AMMO_PACK))


def di_params(row):
    """The dynamic fields of one instance, keyed as the client reads them.

    updateProperties copies every key onto the object as is, except "break",
    which lands in __break. cur_mode is mandatory for a firearm: getAP reads
    fire_costs[cur_mode], and an undefined there makes canUse refuse every
    shot in a battle location.
    """
    root = row["root"]
    p = {"obj": BigUInt(oid_of(row))}
    if root in items.HEAPABLE_ROOTS:
        p["size"] = row["count"]
    elif root == items.HEAL:
        p["use_count"] = row["use_count"]
    elif root == items.TROPHY:
        p["count"] = row["count"]
    else:
        p["break"] = row["brk"]
        p["max_break_cur"] = row["max_break_cur"]
        if root == items.FIRE_ARM:
            p["ammo_count"] = row["ammo_count"]
            p["ammo_type"] = row["ammo_type"]
            p["cur_mode"] = row["cur_mode"]
    return p


def new_fields(type_id, count=1):
    """Column values for a factory-fresh instance of a type."""
    root = items.root_of(type_id)
    si = items.params_of(type_id) or {}
    f = {"root": root, "slot": BAG, "count": 1}
    if root in items.HEAPABLE_ROOTS:
        f["count"] = max(1, min(int(count), si.get("max_count", 1)))
    elif root == items.HEAL:
        f["use_count"] = si.get("use_count", 1)
    elif root in items.BREAKABLE_ROOTS:
        f["brk"] = f["max_break_cur"] = si.get("max_break_abs", 100)
        if root == items.FIRE_ARM:
            f["cur_mode"] = items.first_mode(si.get("fire_mods", [1]))
    return f


def weight_of(row):
    """Grams, the way WeightPan reads it: per piece, times the stack."""
    si = items.params_of(row["type_id"]) or {}
    w = si.get("weight", 0)
    return w * row["count"] if row["root"] in items.HEAPABLE_ROOTS else w


def fits(row, slot):
    """Whether an instance may occupy a container.

    The client's own drag-and-drop never offers a wrong target, so this is
    the check against a modified client rather than a message to a real one.
    """
    if slot == BAG:
        return True
    root = row["root"]
    if slot in HAND_SLOTS:
        return root in items.HAND_ROOTS
    if slot in WEAR_SLOTS:
        if root != items.WEAR:
            return False
        si = items.params_of(row["type_id"]) or {}
        return si.get("slot_type") == slot - HEAD
    return False


class TradeSession:
    """One open stall. The client keeps one Trade object per contact and
    builds a new one for the next, so a session is a single counterpart."""

    def __init__(self, npc_id, trader_type):
        self.s_type = SESSION_TRADE
        self.npc_id = npc_id
        self.trader_type = trader_type


class Inventory:
    """Everything one connection does with items. Owned by server.Session.

    State lives in the database; this object holds only what a session
    needs between frames: the open stall and the reload timers.
    """

    def __init__(self, sess, store):
        self.sess = sess
        self.store = store
        self.trade = None
        self.reloads = {}       # uniq -> asyncio.TimerHandle

    # --- plumbing ----------------------------------------------------------
    @property
    def char_id(self):
        return self.sess.char_id

    def send(self, cmd, **params):
        self.sess.send(cmd, **params)

    def ack(self, res):
        self.send("cmdAck", res=res)

    def rows(self, char_id=None):
        char_id = self.char_id if char_id is None else char_id
        return self.store.items_of(char_id) if char_id else []

    def find(self, text):
        """The row behind a wire id, if it exists and is this character's."""
        parsed = parse_oid(text)
        if not parsed or not self.char_id:
            return None
        row = self.store.item(parsed[0])
        if not row or row["char_id"] != self.char_id:
            return None
        # The type and root ride inside the id, so a forged id that names an
        # existing serial with another type is not the same item.
        if (row["type_id"], row["root"]) != parsed[1:]:
            return None
        return row

    def in_slot(self, slot):
        for row in self.rows():
            if row["slot"] == slot:
                return row
        return None

    def total_weight(self):
        return sum(weight_of(r) for r in self.rows())

    def create(self, type_id, count=1, slot=BAG, char_id=None):
        f = new_fields(type_id, count)
        f["slot"] = slot
        root = f.pop("root")
        return self.store.create_item(char_id or self.char_id, type_id, root, **f)

    # --- pushes ------------------------------------------------------------
    def push_status(self, row, status):
        """ss_obj_status: 1 puts a new item in the bag (the client builds it
        and asks for its DI itself), 0 removes an id from wherever it is."""
        self.send("ss_obj_status", obj=BigUInt(oid_of(row)), status=status)

    def push_di(self, row):
        """Unsolicited dynamic info. This is how a reload, a partial sale or
        a merged stack reaches the client: it changes no number by itself."""
        self.send(DI_COMMAND.get(row["root"], "ss_di_heap"), **di_params(row))

    def money(self):
        """(afro, gold) from the one place they live while the player is on.

        The Character object is what Character.save writes back on the way
        out, so a purse kept only in the database would be overwritten by
        the stale copy in memory the moment the player logged out.
        """
        ch = self.sess.character()
        if ch.char_id is not None:
            return ch.afro, ch.gold
        return self.store.money(self.char_id) if self.char_id else (0, 0)

    def set_money(self, afro, gold):
        ch = self.sess.character()
        if ch.char_id is not None:
            ch.afro, ch.gold = int(afro), int(gold)
            ch.save(self.store)
        elif self.char_id:
            self.store.set_money(self.char_id, afro, gold)

    def push_money(self):
        # The only frame that carries afro/gold is a full userInfo_Player
        # (Gamer.userInfo); there is no lighter update.
        self.sess.send_player_info()

    # --- character life ----------------------------------------------------
    def starter_kit(self, char_id):
        for type_id, count in STARTER_KIT:
            self.create(type_id, count, char_id=char_id)

    def close(self):
        """Connection gone: nothing to save (the database is current), but
        a reload still pending must not fire into a closed socket."""
        for handle in self.reloads.values():
            handle.cancel()
        self.reloads.clear()
        self.trade = None

    # --- ss_get / ss_ack ---------------------------------------------------
    def equipment_list(self, char_id, mask):
        """The o_list for one character and one mask, in the client's order."""
        rows = self.rows(char_id)
        by_slot = {r["slot"]: r for r in rows if r["slot"] != BAG}
        out = []
        if mask & MASK_WEAR:
            out += [BigUInt(oid_of(by_slot[s])) if s in by_slot else EMPTY
                    for s in WEAR_SLOTS]
        if mask & MASK_HANDS:
            out += [BigUInt(oid_of(by_slot[s])) if s in by_slot else EMPTY
                    for s in HAND_SLOTS]
        if mask & MASK_BAG:
            out += [BigUInt(oid_of(r)) for r in rows if r["slot"] == BAG]
        if mask & MASK_SESSION:
            # The divider, then whatever the open session holds. Only the
            # bank, loot and trophies ask with this bit, and none of the
            # three exists yet, so the tail stays empty for now.
            out.append(EMPTY)
        return out

    def ss_get(self, p):
        """ss_get;target=<id>;slot=<mask> -> ss_ack;o_list=|...|

        target 0 is the player (Gamer.ID). Any other id is something on the
        player's screen asking to be drawn: another player's clothes and
        hands, or a creature's. The list has to come back in either case,
        and with the right number of entries -- the ss_ack queue is FIFO and
        the client slices by the mask it remembers, not by what arrives.
        """
        mask = int(p.get("slot", 0) or 0)
        target = int(p.get("target", 0) or 0)
        char_id = self.char_id if target == 0 else self.sess.char_for_entity(target)
        if char_id:
            o_list = self.equipment_list(char_id, mask)
        else:
            # Nobody we know: bare hands and no clothes, one entry per slot.
            o_list = []
            if mask & MASK_WEAR:
                o_list += [EMPTY] * len(WEAR_SLOTS)
            if mask & MASK_HANDS:
                o_list += [EMPTY] * len(HAND_SLOTS)
            if mask & MASK_SESSION:
                o_list.append(EMPTY)
        self.send("ss_ack", o_list=o_list)

    # --- ss_get_di ---------------------------------------------------------
    def ss_get_di(self, p):
        """One instance's dynamic fields.

        Shares ItemFactory's window of five with ss_get_si, and the window
        only reopens when an ss_si_*/ss_di_* frame lands. So an id we do not
        know still gets an answer, shaped by the root the id itself names.
        """
        text = p.get("obj")
        parsed = parse_oid(text)
        if not parsed:
            log.warning("  ??    ss_get_di for unparsable id %r", text)
            self.send("ss_di_heap", obj=BigUInt(str(text or "0")), size=0)
            return
        uniq, type_id, root = parsed
        row = self.store.item(uniq)
        # Not "owned by me": a public trophy on another player is asked for
        # with target=<id>, and that is the one DI the client pulls for
        # somebody else's item. Anything that exists is described.
        if row and (row["type_id"], row["root"]) == (type_id, root):
            self.push_di(row)
            return
        log.warning("  ??    ss_get_di for unknown item %s", text)
        ghost = dict(uniq=uniq, type_id=type_id, root=root, count=0, brk=0,
                     max_break_cur=0, ammo_count=0, ammo_type=0, cur_mode=0,
                     use_count=0)
        self.send(DI_COMMAND.get(root, "ss_di_heap"), **di_params(ghost))

    # --- ss_move -----------------------------------------------------------
    def ss_move(self, p):
        """ss_move;obj;from;to -> cmdAck, then ss_obj_move.

        On res=0 the client moves the item itself, and if the target slot
        was occupied it puts the displaced item back where the moved one
        came from (PersEquip.applyTransfer) -- so the swap here mirrors that
        exactly, or the two sides disagree on where things are.
        """
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        try:
            src, dst = int(p.get("from")), int(p.get("to"))
        except (TypeError, ValueError):
            self.ack(RES_REFUSED)
            return
        if row["slot"] != src or src == dst:
            # The client's picture of where the item is does not match ours;
            # moving it anyway would leave a ghost in one of the two places.
            self.ack(RES_NOT_FOUND)
            return
        if not fits(row, dst):
            self.ack(RES_NO_ITEM)
            return
        displaced = self.in_slot(dst) if dst != BAG else None
        if displaced and not fits(displaced, src):
            self.ack(RES_NO_ITEM)
            return
        self.store.update_item(row["uniq"], slot=dst)
        if displaced:
            self.store.update_item(displaced["uniq"], slot=src)
        self.ack(RES_OK)
        # Meant for everyone else in the location, so they redraw this
        # player's figure; PlayerRegister.ss_obj_move ignores it for
        # Gamer.ID, so the sender's own copy is harmless. There is no room
        # fan-out on the server yet; when there is, this is the frame to
        # send to the rest of the room with the sender's entity id.
        self.send("ss_obj_move", id=0, obj=BigUInt(oid_of(row)), to=dst,
                  **{"from": src})

    # --- ss_use ------------------------------------------------------------
    def ss_use(self, p):
        """ss_use;type=<bit>;obj=x<oid>;[target=x..] -> cmdAck (+ pushes)."""
        try:
            kind = int(p.get("type", -1))
        except (TypeError, ValueError):
            kind = -1
        if kind == USE_DELETE:
            self.use_delete(p)
        elif kind == USE_LOAD:
            self.use_load(p)
        elif kind == USE_UNLOAD:
            self.use_unload(p)
        elif kind == USE_MODE:
            self.use_mode(p)
        else:
            # Shooting, striking and healing belong to combat; until then a
            # refusal keeps the acknowledgement queue in step.
            self.ack(RES_REFUSED)

    def use_delete(self, p):
        """type=0: throw the item away. The client removes nothing until
        ss_obj_status;status=0 arrives (ItemActivator.deleteAck)."""
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        self.forget_reload(row["uniq"])
        self.store.delete_item(row["uniq"])
        self.ack(RES_OK)
        self.push_status(row, 0)

    def use_load(self, p):
        """type=1: load obj (a firearm) from target (a stack of rounds).

        After res=0 the client shows a reload bar and waits for
        ss_di_firearm with the new ammo_count/ammo_type; the stack it loaded
        from is only ever changed by ss_di_heap or removed by ss_obj_status.
        The stack is charged at once, the gun reports after reload_time,
        which is what the bar on the client is counting down.
        """
        gun = self.find(p.get("obj"))
        stack = self.find(p.get("target"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        if not stack or stack["root"] != items.AMMO:
            self.ack(RES_NO_AMMO)
            return
        si = items.params_of(gun["type_id"]) or {}
        if stack["type_id"] not in si.get("comp_array", []):
            self.ack(RES_WRONG_AMMO)
            return
        if gun["uniq"] in self.reloads:
            self.ack(RES_NOT_READY)
            return
        clip = si.get("clip_size", 1)
        if gun["ammo_count"] >= clip and gun["ammo_type"] == stack["type_id"]:
            self.ack(RES_LOADED)
            return
        self.ack(RES_OK)
        if gun["ammo_count"] and gun["ammo_type"] != stack["type_id"]:
            # Other rounds still in it: they come back as a stack of their
            # own before the new ones go in, the way unloading does.
            self.eject(gun)
        take = min(clip - gun["ammo_count"], stack["count"])
        if take >= stack["count"]:
            self.store.delete_item(stack["uniq"])
            self.push_status(stack, 0)
        else:
            stack["count"] -= take
            self.store.update_item(stack["uniq"], count=stack["count"])
            self.push_di(stack)
        self.store.update_item(gun["uniq"], ammo_count=gun["ammo_count"] + take,
                               ammo_type=stack["type_id"])
        delay = si.get("reload_time", 0) / 1000.0
        loop = asyncio.get_running_loop()
        self.reloads[gun["uniq"]] = loop.call_later(delay, self.reloaded,
                                                    gun["uniq"])

    def reloaded(self, uniq):
        self.reloads.pop(uniq, None)
        row = self.store.item(uniq)
        if row and row["char_id"] == self.char_id:
            self.push_di(row)

    def forget_reload(self, uniq):
        handle = self.reloads.pop(uniq, None)
        if handle:
            handle.cancel()

    def eject(self, gun):
        """Rounds out of the gun into a fresh stack in the bag. Always a new
        stack: the client is told about it with ss_obj_status;status=1 and
        then asks for its size itself."""
        if not gun["ammo_count"]:
            return None
        stack = self.create(gun["ammo_type"], gun["ammo_count"])
        gun["ammo_count"] = 0
        self.store.update_item(gun["uniq"], ammo_count=0)
        self.push_status(stack, 1)
        self.push_di(stack)
        return stack

    def use_unload(self, p):
        """type=32: empty the magazine into the bag, then report the gun."""
        gun = self.find(p.get("obj"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        if gun["uniq"] in self.reloads:
            self.ack(RES_NOT_READY)
            return
        if not gun["ammo_count"]:
            self.ack(RES_NO_AMMO)
            return
        self.ack(RES_OK)
        self.eject(gun)
        self.push_di(self.store.item(gun["uniq"]))

    def use_mode(self, p):
        """type=64: switch fire mode; target carries the mode number in hex.

        The client already checked fire_mods[mode] != 0 and applies the mode
        itself on res=0 (PersEquip.applyChangeFireMode); nothing to push.
        """
        gun = self.find(p.get("obj"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        try:
            mode = int(str(p.get("target", "")), 16)
        except ValueError:
            self.ack(RES_REFUSED)
            return
        modes = (items.params_of(gun["type_id"]) or {}).get("fire_mods", [])
        if not (0 <= mode < len(modes)) or not modes[mode]:
            self.ack(RES_REFUSED)
            return
        self.store.update_item(gun["uniq"], cur_mode=mode)
        self.ack(RES_OK)

    # --- ss_heap_c ---------------------------------------------------------
    def ss_heap_c(self, p):
        """Split or merge a stack (StuffManager.separateHeap / joinHeap).

        Without trg: take num pieces OUT of obj into a new stack. With trg:
        move num pieces from trg (the one being dragged) INTO obj (the one
        it was dropped on); the client computed num as what fits. Either
        way it changes no size itself: the old stack's size comes back in
        ss_di_heap, a new one arrives by ss_obj_status, an emptied one
        leaves by ss_obj_status;status=0 (items.md 2.2).
        """
        row = self.find(p.get("obj"))
        if not row or row["root"] not in items.HEAPABLE_ROOTS:
            self.ack(RES_NOT_FOUND)
            return
        try:
            num = int(p.get("num", 0) or 0)
        except (TypeError, ValueError):
            num = 0
        if "trg" not in p:
            if not (0 < num < row["count"]):
                self.ack(RES_REFUSED)
                return
            row["count"] -= num
            self.store.update_item(row["uniq"], count=row["count"])
            part = self.create(row["type_id"], num)
            self.ack(RES_OK)
            self.push_status(part, 1)
            self.push_di(part)
            self.push_di(row)
            return
        donor = self.find(p.get("trg"))
        if not donor or donor["uniq"] == row["uniq"]:
            self.ack(RES_NOT_FOUND)
            return
        if donor["type_id"] != row["type_id"]:
            self.ack(RES_NO_ITEM)
            return
        limit = (items.params_of(row["type_id"]) or {}).get("max_count", 1)
        if not num:
            num = donor["count"]
        if num > donor["count"] or row["count"] + num > limit:
            self.ack(RES_REFUSED)
            return
        row["count"] += num
        donor["count"] -= num
        self.store.update_item(row["uniq"], count=row["count"])
        if donor["count"]:
            self.store.update_item(donor["uniq"], count=donor["count"])
        else:
            self.store.delete_item(donor["uniq"])
        self.ack(RES_OK)
        self.push_di(row)
        if donor["count"]:
            self.push_di(donor)
        else:
            self.push_status(donor, 0)

    # --- the stall: ss_create s_type=1, ss_upd ------------------------------
    def open_trade(self, p):
        """ss_create;s_type=1;target=<npc> -> cmdAck.

        Gamer.proposeContact only sends this for an NPC whose userInfo said
        can_trade, so a refusal here means a forged frame or a stale id.
        """
        target = int(p.get("target", 0) or 0)
        entry = self.sess.room.npc(target)
        if not entry or entry[2] != world.TRADER or not self.char_id:
            self.ack(RES_REFUSED)
            return
        self.trade = TradeSession(target, entry[1])
        self.ack(RES_OK)

    def ss_upd(self, p):
        """An operation inside the open stall. Returns False when no stall
        is open, so the caller can fall back to whatever else ss_upd means.

        Closing (s_status=0) is answered with nothing at all: Trade.close
        sends it without registering a cmdAck handler, so an
        acknowledgement here would be consumed by the next command's.
        """
        if not self.trade:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == UPD_CLOSE:
            self.trade = None
        elif code in (UPD_BUY, UPD_BUY_GOLD, UPD_BGPOINTS_BUY):
            self.buy(p, code)
        elif code == UPD_SELL:
            self.sell(p)
        else:
            # Repair (3/5/7) and trophy registration (6) do register a
            # handler, so they must be refused, not ignored.
            self.ack(RES_REFUSED)
        return True

    def buy(self, p, code):
        """ss_upd;s_status=1|4;obj=x<index>;param=<n> -> cmdAck, then the
        item, then the money.

        obj is the INDEX into the trader's type_list, in hex, not a type id
        (Trade.buy: tradeID.toString(16)). param is the number of rounds for
        ammunition and 1 otherwise. The client adds nothing on res=0: the new
        instance arrives by ss_obj_status;status=1 and the balance by a
        full userInfo_Player.
        """
        stock = items.stock_for(self.trade.trader_type)
        try:
            index = int(str(p.get("obj", "")), 16)
            n = int(p.get("param", 1) or 1)
        except ValueError:
            self.ack(RES_REFUSED)
            return
        if not (0 <= index < len(stock)):
            self.ack(RES_NOT_FOUND)
            return
        type_id = stock[index]
        root = items.root_of(type_id)
        si = items.params_of(type_id)
        if si is None:
            self.ack(RES_NOT_FOUND)
            return
        if root not in items.HEAPABLE_ROOTS:
            n = 1
        if not (1 <= n <= si.get("max_count", 1)):
            self.ack(RES_REFUSED)
            return
        if code == UPD_BGPOINTS_BUY:
            self.ack(RES_REFUSED)           # no battleground points yet
            return
        # cost is per pack of sell_num; the client shows ceil(cost/sell_num
        # * n * pmod) and expects to be charged the same.
        per_pack = si["g_cost"] if code == UPD_BUY_GOLD else si["cost"]
        if code == UPD_BUY_GOLD and not per_pack:
            self.ack(RES_REFUSED)
            return
        price = int(math.ceil(per_pack * n * PMOD / float(si.get("sell_num", 1))))
        if self.total_weight() + si.get("weight", 0) * n > MAX_WEIGHT:
            self.ack(RES_OVERLOAD)
            return
        afro, gold = self.money()
        if code == UPD_BUY_GOLD:
            if gold < price:
                self.ack(RES_NO_MONEY)
                return
            gold -= price
        else:
            if afro < price:
                self.ack(RES_NO_MONEY)
                return
            afro -= price
        self.set_money(afro, gold)
        row = self.create(type_id, n)
        self.ack(RES_OK)
        self.push_status(row, 1)
        self.push_di(row)
        self.push_money()

    def sell(self, p):
        """ss_upd;s_status=2;obj=x<oid>;param=<n> -> cmdAck, then the bag,
        then the money.

        Price as ItemContainer.showCost draws it: cost x smod x sell_mod x
        current quality, per piece for a stack, scaled by use_count for a
        heal item, floored. On res=0 the client removes nothing
        (Trade.applyTransfer only raises an event), so a partial sale is
        reported with ss_di_heap and a whole one with ss_obj_status 0.
        """
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        si = items.params_of(row["type_id"]) or {}
        if si.get("cost", 0) <= 0 or si.get("quest"):
            self.ack(RES_REFUSED)
            return
        heapable = row["root"] in items.HEAPABLE_ROOTS
        try:
            n = int(p.get("param", 0) or 0)
        except (TypeError, ValueError):
            n = 0
        if not heapable:
            n = 1
        elif not (1 <= n <= row["count"]):
            n = row["count"]
        unit = si["cost"] / float(si.get("sell_num", 1))
        quality = 1.0
        if row["root"] in items.BREAKABLE_ROOTS and row["max_break_cur"]:
            quality = row["brk"] / float(row["max_break_cur"])
        elif row["root"] == items.HEAL and si.get("use_count"):
            quality = row["use_count"] / float(si["use_count"])
        price = int(math.floor(unit * n * SMOD * si.get("sell_mod", 1) * quality))
        afro, gold = self.money()
        self.set_money(afro + price, gold)
        if heapable and n < row["count"]:
            row["count"] -= n
            self.store.update_item(row["uniq"], count=row["count"])
            self.ack(RES_OK)
            self.push_di(row)
        else:
            self.forget_reload(row["uniq"])
            self.store.delete_item(row["uniq"])
            self.ack(RES_OK)
            self.push_status(row, 0)
        self.push_money()
