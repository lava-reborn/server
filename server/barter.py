"""Barter between two players: ss_create;s_type=2 and the ss_upd behind it.

The client is lol/core/player/Barter.as, the window gpui/BarterInterface.as,
and the two ways in, Gamer.proposeContact (a click on a player standing
next to you) and Gamer.ss_create (an invitation from the server). The
frames, in the order they travel (A proposes, B is invited; what one side
sends, the other receives in the same shape):

    A: ss_create;s_type=2;target=<B>   A <- cmdAck 0   B <- ss_create;target=<A>
    B: ss_upd;s_status=1 (agree)       B <- cmdAck 0   A <- ss_upd;s_status=1
       or ss_upd;s_status=2 (no)       both <- ss_upd;s_status=0
    both windows open and each asks ss_get;slot=8 for its bag
    X: ss_upd 3|4;obj=x<oid>           X <- cmdAck     Y <- ss_upd 3|4;obj=x<oid>
    X: ss_upd 7|8;obj=x<hex sum>       X <- cmdAck     Y <- ss_upd 7|8;obj=x<hex>
    X: ss_upd 5 (ready) | 6 (not)      no answer       Y <- ss_upd 5|6
    the second 5: the exchange, then   Y <- ss_upd 5, both <- ss_upd 0, the
                                       bag as it now is, the purse

Which of them the client waits an answer for is fixed by the class: 1, 3,
4, 7 and 8 register a cmdAck handler; 0 (close), 2 (deny, from the
invitation and from the proposer's "Отказаться от бартера"), 5 and 6
(readyToBarter) go out bare. Money is always the whole sum on offer, afro
whole and gold in hundredths, and the other side reads it as
Number("0x" + obj) (Barter.visavisAddMoney). An item goes over as its oid,
and the other side builds it and asks ss_get_di for it by itself
(addToVAVList), which inventory.ss_get_di answers for anything that exists.

The client's Barter object dies in one place only, close(): its own close
button, or a server ss_upd;s_status=0. A deny, a proposer's cancel, a
refused proposal and a completed exchange all leave it alive -- and while
it lives the client ignores every new invitation (Gamer.ss_create), never
proposes again (Gamer.proposeContact), and reads every ss_upd the server
sends anybody as barter, a bank's weights included. So every end of a
barter, whatever brought it about, is followed by ss_upd 0 to each client
whose Barter is still alive: kill() below.

That close has one more side to it. Barter.kill takes off the client's
queues the ss_ack its window's own bag request is waiting for and up to two
transfers (3/4) still waiting for their cmdAck -- but not a money offer
(7/8) or an agree (1). Whatever of those was already on its way when our
ss_upd 0 went out arrives after it, and is answered, or swallowed, the way
the client's queues now expect: stray() and swallow_get().

Neither client moves anything on the server's say-so alone. It puts its own
things back when it closes the window itself (returnBarterStuff), and moves
the other side's list into its bag when it sees both sides ready
(applyBarter) -- and nothing else. So after every end the server tells each
side what its bag really holds: ss_obj_status 1 for what is in it and 0 for
what is not, which PersEquip applies idempotently (Bag.addItem skips an id
it has, findItem finds no id it lacks).

applyBarter also closes the barter window, and the client runs it the
moment both lights are on in its OWN window: readyToBarter lights this
side's before its 5 is even sent. Those lights are the window's, not the
server's. A 5 of the other side's that crossed a change on the way, or a
change of theirs still on its way here, leaves a light on that the server
has already put out -- and a ready clicked on it comes from a client whose
window is gone and whose bag already holds the other side's things. No
frame reopens that window, so such a ready ends the deal (Barter.ready),
and the server keeps track of what each window shows to know when a ready
may be one (Side.lit, show()).

The exchange is one database transaction (accounts.Store.barter_swap), and
the purses are the online players' in-memory Characters, updated only once
it has committed. An offered thing is locked (Inventory.locked): every verb
that starts at Inventory.find -- sell, post, auction, bank, use, split,
merge, move, drop -- refuses it until it is taken back or the barter ends.
"""
import asyncio
import logging
import os
import time

import inventory
import items
import progression
from protocol import BigUInt

log = logging.getLogger("lava")

SESSION_BARTER = 2              # StuffManager.SESSION_BARTER

# Barter.UPD_* (Barter.as:18-26); the same numbers travel both ways.
UPD_CLOSE, UPD_AGREE, UPD_DENY = 0, 1, 2
UPD_TO_BUFFER, UPD_TO_BAG = 3, 4
UPD_APPLY, UPD_BREAK = 5, 6
UPD_ADD_AFRO, UPD_ADD_GOLD = 7, 8

# The four the client sends without registering an answer (see above).
BARE = frozenset((UPD_CLOSE, UPD_DENY, UPD_APPLY, UPD_BREAK))

# cmdAck codes. Anything but 0 to a proposal shows "Невозможно совершить
# бартер <res>" (proposeBarterAck), and ErrorReport listens to every cmdAck
# and puts up its own text for the codes it knows -- 3 is "Сервер не
# отвечает" there -- so a refusal that needs words uses 31, which it does
# not know, and says why in the chat.
RES_OK = 0
RES_NOT_FOUND = inventory.RES_NOT_FOUND     # 12 "Объект не найден"
RES_NOT_READY = inventory.RES_NOT_READY     # 17 "Объект не готов"
RES_NO_MONEY = inventory.RES_NO_MONEY       # 21, no text of its own
RES_CANT = 31

# A ready (5) that reaches us this soon after the other side changed the
# offer may have been clicked before that change reached the one who
# clicked it: its window had already turned the button off again, and the
# client says nothing when it does. Taking it would trade on terms one side
# never saw, so it is not taken (see ready()). A second is several round
# trips anywhere this game is played from -- and everything that reasons
# about what a window has or has not seen yet leans on that.
READY_SETTLE = float(os.environ.get("LAVA_BARTER_SETTLE", "1.0"))
# How long an invitation waits for an answer. The client has a timer for it
# (awaitingAnswerInt, cleared in ss_create) that nothing starts, and an
# invitation its window never showed -- the invitee's own Barter was alive
# and Gamer.ss_create passed it by -- would otherwise wait for ever.
PENDING_TIMEOUT = float(os.environ.get("LAVA_BARTER_WAIT", "60"))
# How long after the server closed a client's barter its leftovers are still
# taken for barter frames. They were sent before the close reached it, so a
# round trip is all they need; any ss_create from the client ends it sooner.
GRACE = 10.0
# And for how long nobody may invite that client again: a leftover agree or
# deny that arrived after the next invitation would be read as the answer
# to it. Also a round trip or two; a suite on one machine needs less.
LEFTOVERS = float(os.environ.get("LAVA_BARTER_LEFTOVERS", "2.0"))
# Barter.kill skips the transferAck handler twice, so at most two transfers
# already on their way have lost the handler their answer would go to.
SKIPPED_TRANSFERS = 2

EMPTY = BigUInt("0")


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sum(value):
    """A money offer: BigUINTCluster(num).toString() is num.toString(16),
    so whole numbers come as bare hex. A fraction -- 100 * 0.29 is not a
    whole number in a double -- keeps only what is before the point, the
    way the client's own Number("0x" + obj) reads it on the other side."""
    text = str(value if value is not None else "").strip().lower()
    head = text.split(".", 1)[0]
    try:
        n = int(head, 16)
    except ValueError:
        return None
    return n if n >= 0 else None


def tradable(type_id):
    """Whether a thing may change hands at all: the client's own test is the
    static exchang flag (BarterInterface.checkSellItem), and a modified
    client would not make it. Quest things stay with the quest, as they do
    in the post and at the auction, and what is out of the game -- premium
    things and those the owner took out by name -- does not change hands
    (items.out_of_game). Gold items also stay with their owner, even when the
    original exchange flag permits them."""
    import combat  # late: combat imports inventory and its session handlers
    si = items.params_of(type_id) or {}
    return bool(si.get("exchang")) and not si.get("quest") \
        and not items.out_of_game(type_id) and not combat.gold_item(type_id)


class Side:
    """What one of the two has put on the table."""

    def __init__(self, sess):
        self.sess = sess
        self.items = {}         # uniq -> the row as it was when offered
        self.afro = 0
        self.gold = 0           # hundredths of an ounce, as everywhere
        self.ready = False
        # A ready from this side before this moment may be stale (READY_SETTLE).
        self.quiet_until = 0.0
        # The other side's light in this side's window (Barter.vavReady), as
        # the frames sent to it leave it: on after a relayed 5, off after
        # anything else relayed (show()). lit_at is when the last 5 went out,
        # and until lit_until the window may still show a light the server
        # has already put out, the frame that says so being on its way.
        self.lit = False
        self.lit_at = 0.0
        self.lit_until = 0.0


class Deal:
    """One barter: an invitation until the invitee agrees, then open."""

    def __init__(self, proposer, invitee):
        self.proposer = Side(proposer)
        self.invitee = Side(invitee)
        self.open = False
        self.timer = None       # the invitation's time limit

    def sides(self):
        return (self.proposer, self.invitee)

    def side(self, sess):
        return self.proposer if sess is self.proposer.sess else self.invitee

    def other(self, sess):
        return self.invitee if sess is self.proposer.sess else self.proposer


class Barter:
    """One connection's part in barter. Owned by server.Session.

    deal is shared by the two sessions in it. The rest is about this
    client's own Barter object: when the server last closed it, and which
    answers the close took off its queues.
    """

    def __init__(self, sess, store, directory):
        self.sess = sess
        self.store = store
        self.directory = directory      # rooms.Directory: the other player
        self.deal = None
        self.ended = None               # monotonic time of our last close
        self.skip_transfers = 0
        # cmdAcks this object has sent, so a handler that fails half way can
        # tell whether its one answer already went out.
        self.acks = 0
        # The window has opened and its ss_get;slot=8 is on its way; and,
        # if the close overtook it, that the client no longer waits for the
        # answer.
        self.awaiting_bag = False
        self.skip_bag = False

    # --- plumbing ------------------------------------------------------------
    def send(self, cmd, **params):
        self.sess.send(cmd, **params)

    def ack(self, res):
        self.acks += 1
        self.send("cmdAck", res=res)

    def relay(self, code, obj=EMPTY):
        self.send("ss_upd", s_status=code, obj=obj)

    def kill(self):
        """ss_upd 0: close this client's Barter, whatever state it is in.

        A proposer waiting for an answer reads it as "Игрок занят" in its
        waiting alert, an invitee as the same on its invitation, and an open
        window closes. Whatever the close overtook is dealt with in stray()
        and swallow_get()."""
        self.relay(UPD_CLOSE)
        self.ended = time.monotonic()
        self.skip_transfers = SKIPPED_TRANSFERS
        if self.awaiting_bag:
            self.awaiting_bag = False
            self.skip_bag = True

    def in_grace(self, window=GRACE):
        if self.ended is None:
            return False
        if time.monotonic() - self.ended > window:
            if window == GRACE:
                self.ended = None
                self.skip_bag = False
            return False
        return True

    # --- who may barter --------------------------------------------------------
    def present(self):
        """Standing in a location, alive, with a character."""
        s = self.sess
        return bool(not s.closed and s.char_id and s.active is not None
                    and not s.combat.dead and s.room is not None
                    and not s.on_map)

    def windows_open(self):
        """Whether the server has another session window open for this
        player: a stall, the bank, a teacher, a bag on the ground, or any
        other NPC session. The client hands every ss_upd from the server to
        every session object alive (Trade, Bank, Upgrade and TrophyManager
        all listen), so a barter's relays would read to an open bank as its
        weights, and its close would shut the shop."""
        s = self.sess
        return (s.inv.trade is not None or s.inv.bank is not None
                or s.training is not None or s.combat.loot is not None
                or s.npc_session is not None)

    def new_session(self):
        """Any ss_create: whatever the last close left in flight has arrived
        by now, since the client sent it before this."""
        self.ended = None
        self.skip_bag = False

    def refuse_other_session(self):
        """ss_create for a shop, bank, teacher or bag on the ground while
        this player is in a barter: True when it was dealt with here.

        Every window a barter puts up is modal (SceneShifter's UIPanels,
        mode:true): the invitation, the proposer's waiting alert, the barter
        window itself. A client that has just clicked an NPC or a bag shows
        none of them. Either its invitation was passed by (Gamer.ss_create
        found a Barter of its own alive -- its own "Предложить бартер?"
        query, answered no), or applyBarter shut its window on lights the
        server never had on (see the module note). Waiting would help
        nobody: until the other side gave up, every shop, bank and teacher
        would be refused, and nothing on this player's screen could end it.
        So the barter ends here, the bag put right as after a failed
        exchange (applied: what applyBarter took in goes out again).

        The ss_create itself is still refused, and its cmdAck goes out ahead
        of our ss_upd 0. The NPC's session object (Trade, Bank, Upgrade)
        listens to ss_upd from the moment it is built, and a close that
        reached it after its window opened would shut that window. Refused,
        its window never opens and the 0 only lays the object to rest; the
        next click opens it."""
        deal = self.deal
        if deal is None:
            return False
        s = self.sess
        other = deal.other(s).sess
        self.ack(RES_CANT)
        log.info("  ..    %s turns to another window mid-barter; it ends", s.nick)
        finish(deal, {s: "Бартер с %s отменён" % other.nick,
                      other: "%s занят, бартер отменён" % s.nick}, applied=True)
        return True

    # --- ss_create;s_type=2 ------------------------------------------------------
    def propose(self, p):
        """The proposer's ss_create: exactly one cmdAck, whatever breaks.

        A refusal is followed by ss_upd 0, or the proposer's Barter would
        outlive it and block the next proposal (see the module note)."""
        before = self.acks
        try:
            self._propose(p)
        except Exception:                                   # noqa: BLE001
            log.exception("  !!    barter proposal failed")
            if self.acks == before:
                self.ack(RES_CANT)

    def _propose(self, p):
        s = self.sess
        self.new_session()
        s.windows_gone()
        deal = self.deal
        if deal is not None:
            if not deal.open and deal.invitee.sess is s:
                # Proposing while invited: the client built a Barter of its
                # own before our invitation reached it, and Gamer.ss_create
                # passed the invitation by. Its proposer is told no; this
                # client never heard of it and is told nothing.
                finish(deal, {deal.proposer.sess: "%s занят" % s.nick},
                       spare=(s,))
            else:
                # Its window for the barter it is in is still alive, so this
                # is not the client's own frame; a close would take that
                # window down with it.
                self.ack(RES_CANT)
                return
        why, other = self.target(p)
        if why is not None:
            log.info("  ..    barter from %s refused: %s", s.nick, why)
            self.ack(RES_CANT)
            self.kill()
            s.say("Бартер невозможен: %s" % why)
            return
        deal = Deal(s, other)
        self.deal = other.barter.deal = deal
        self.ack(RES_OK)
        # Gamer.ss_create builds the invitee's Barter; Barter.ss_create reads
        # target to name the proposer in "<name> предлагает бартер".
        other.send("ss_create", target=s.pid, s_type=SESSION_BARTER)
        deal.timer = asyncio.get_running_loop().call_later(
            PENDING_TIMEOUT, expire, deal)
        log.info("  ..    %s proposes a barter to %s", s.nick, other.nick)

    def target(self, p):
        """(why not, None) or (None, the invitee's session)."""
        s = self.sess
        if not self.present():
            return "вы не можете сейчас меняться", None
        pid = _int(p.get("target"), 0)
        other = self.directory.by_pid(pid) if pid else None
        if other is None or other.closed or other.active is None:
            return "игрок не найден", None
        if other is s:
            return "нельзя меняться с самим собой", None
        theirs = other.barter
        if theirs.deal is not None or not theirs.present() \
                or theirs.windows_open() or theirs.in_grace(LEFTOVERS):
            return "%s занят" % other.nick, None
        if other.room is not s.room:
            return "%s в другом месте" % other.nick, None
        loc = s.loc
        if not progression.within_reach(s.pos, other.pos, loc.width, loc.height):
            # Gamer.proposeContact asks from beside the other player, and
            # the server asks no less (progression.within_reach).
            return "%s слишком далеко" % other.nick, None
        return None, other

    # --- ss_upd ----------------------------------------------------------------------
    def ss_upd(self, p):
        """An ss_upd while this session is in a deal. False when it is not,
        so the caller falls back to whatever else ss_upd means.

        Exactly one cmdAck for the codes that wait for one, none for the
        bare ones, whatever happens inside."""
        deal = self.deal
        if deal is None:
            return False
        code = _int(p.get("s_status"), -1)
        before = self.acks
        try:
            self._upd(deal, code, p)
        except Exception:                                   # noqa: BLE001
            log.exception("  !!    barter ss_upd %s failed", code)
            if code not in BARE and self.acks == before:
                self.ack(RES_CANT)
        return True

    def _upd(self, deal, code, p):
        s = self.sess
        me, them = deal.side(s), deal.other(s)
        if code == UPD_CLOSE:
            # The window's close button (or Esc): its Barter is dead already
            # and has put its own things back (returnBarterStuff). The other
            # window closes on our ss_upd 0 and puts nothing back by itself.
            log.info("  ..    %s closes the barter", s.nick)
            finish(deal, {them.sess: "%s прервал бартер" % s.nick}, spare=(s,))
        elif code == UPD_DENY:
            # From the invitation it is a no; from the proposer's waiting
            # alert a change of mind -- and if that crossed the invitee's
            # yes on the way, the proposer's window is opening right now on
            # the relayed agree, and the close takes it down again.
            log.info("  ..    %s says no to the barter", s.nick)
            if s is deal.invitee.sess and not deal.open:
                text = "%s отказывается от бартера" % s.nick
            else:
                text = "%s передумал меняться" % s.nick
            finish(deal, {them.sess: text})
        elif code == UPD_AGREE:
            if deal.open or s is not deal.invitee.sess:
                self.ack(RES_CANT)
                return
            deal.open = True
            if deal.timer is not None:
                deal.timer.cancel()
                deal.timer = None
            # agreeBarterAck opens the invitee's window, the relayed agree
            # the proposer's (Barter.ss_upd -> createSession), and each
            # window asks for the bag at once.
            self.ack(RES_OK)
            self.awaiting_bag = True
            them.sess.barter.relay(UPD_AGREE)
            them.sess.barter.awaiting_bag = True
            log.info("  ..    %s agrees to barter with %s", s.nick, them.sess.nick)
        elif code == UPD_TO_BUFFER:
            self.put(deal, me, them, p)
        elif code == UPD_TO_BAG:
            self.take_back(deal, me, them, p)
        elif code in (UPD_ADD_AFRO, UPD_ADD_GOLD):
            self.money(deal, me, them, code, p)
        elif code == UPD_APPLY:
            if deal.open:
                self.ready(deal, me, them)
        elif code == UPD_BREAK:
            if deal.open:
                changed(deal, me)
                show(them, UPD_BREAK)
        elif code not in BARE:
            self.ack(RES_CANT)

    def put(self, deal, me, them, p):
        """3: a thing from the bag onto the table. The window moves it on
        res=0 (StuffManager.transferAck) and back on anything else."""
        if not deal.open:
            self.not_open()
            return
        inv = self.sess.inv
        # find() is this character's own things on them, not the bank's
        # and not anything already on the table (Inventory.locked).
        row = inv.find(p.get("obj"))
        if row is None or row["slot"] != inventory.BAG:
            self.ack(RES_NOT_FOUND)
            return
        if not tradable(row["type_id"]):
            self.ack(RES_CANT)
            self.sess.say("Эту вещь нельзя передать")
            return
        if row["uniq"] in inv.reloads:
            self.ack(RES_NOT_READY)
            return
        me.items[row["uniq"]] = row
        inv.locked.add(row["uniq"])
        self.ack(RES_OK)
        changed(deal, me)
        show(them, UPD_TO_BUFFER, BigUInt(inventory.oid_of(row)))

    def take_back(self, deal, me, them, p):
        """4: a thing from the table back into the bag."""
        if not deal.open:
            self.not_open()
            return
        parsed = inventory.parse_oid(p.get("obj"))
        row = me.items.get(parsed[0]) if parsed else None
        if row is None or (row["type_id"], row["root"]) != parsed[1:]:
            self.ack(RES_NOT_FOUND)
            return
        del me.items[row["uniq"]]
        self.sess.inv.locked.discard(row["uniq"])
        self.ack(RES_OK)
        changed(deal, me)
        show(them, UPD_TO_BAG, BigUInt(inventory.oid_of(row)))

    def not_open(self):
        """A transfer before the window is open: one that the window a close
        of ours shut had sent before the close reached it, arriving only
        after somebody invited this player again (a round trip longer than
        LEFTOVERS). Barter.kill took its handler with that window, so
        stray() would have swallowed it but for the new deal, and so does
        this; anything else is refused."""
        if self.skip_transfers > 0 and self.in_grace():
            self.skip_transfers -= 1
            return
        self.ack(RES_CANT)

    def money(self, deal, me, them, code, p):
        """7/8: the whole sum on offer, afro or gold in hundredths. The
        window caps it at the purse it was last told about; the purse the
        server holds is the one that counts. The client follows every
        change of the sum with a bare 6 of its own."""
        if not deal.open:
            self.ack(RES_CANT)
            return
        amount = _sum(p.get("obj"))
        if amount is None:
            self.ack(RES_CANT)
            return
        ch = self.sess.character()
        if amount > (ch.afro if code == UPD_ADD_AFRO else ch.gold):
            self.ack(RES_NO_MONEY)
            self.sess.say("Не хватает денег")
            return
        if code == UPD_ADD_AFRO:
            me.afro = amount
        else:
            me.gold = amount
        self.ack(RES_OK)
        changed(deal, me)
        show(them, code, BigUInt("%x" % amount))

    def ready(self, deal, me, them):
        """5: this side says yes to the table as it stands.

        Three answers, by what the clicking window may have been showing:

        * the other side is ready and its last change is long enough ago
          to have been seen: the exchange;
        * the other side's light was on in this window and may still have
          been when it was clicked: that window ran applyBarter and is gone
          (module note), and the server has nothing to exchange on terms
          both saw -- a change put the other side's yes out, or came too
          late to be seen. A 6 or a 5 back would go to a Barter with no
          window, leaving this player nothing to close and the other side
          waiting at theirs, so the deal ends here instead;
        * the light was off: the window is still open. Too soon after the
          other side's change (READY_SETTLE) the ready is turned back with a
          6, which puts this side's button out as the change did or is about
          to; otherwise it stands and the other side sees it.
        """
        now = time.monotonic()
        seen = now >= me.quiet_until
        if them.ready and seen:
            me.ready = True
            # settle() relays this yes itself, and only if it goes through:
            # on it the other window moves this side's list into its bag.
            settle(deal, me, them)
            return
        if me.lit or now < me.lit_until:
            log.info("  ..    %s is ready on a light the server has put out;"
                     " the barter ends", self.sess.nick)
            why = "Бартер не состоялся: условия изменились в момент согласия"
            finish(deal, {me.sess: why, them.sess: why}, applied=True)
            return
        if not seen:
            log.info("  ..    %s is ready too soon after a change; turned back",
                     self.sess.nick)
            show(me, UPD_BREAK)
            return
        me.ready = True
        show(them, UPD_APPLY)

    # --- leftovers of a closed barter ---------------------------------------------
    def stray(self, p):
        """An ss_upd that left the client before our close reached it: True
        once it is dealt with. Runs before the dead filter, which would
        answer a bare 5 as if it waited for something.

        Bare codes are dropped. A transfer is dropped while the close has
        taken its handler (SKIPPED_TRANSFERS) and refused after that; an
        agree and a money offer keep theirs and are refused."""
        if self.deal is not None or not self.in_grace():
            return False
        code = _int(p.get("s_status"), -1)
        if code in BARE:
            return True
        if code in (UPD_TO_BUFFER, UPD_TO_BAG) and self.skip_transfers > 0:
            self.skip_transfers -= 1
            return True
        self.ack(RES_CANT)
        return True

    def swallow_get(self, p):
        """ss_get;slot=8 with no target is the window's own bag request
        (Barter.requestSession). True when its answer must not be sent: the
        close overtook it and Barter.kill took the ss_ack handler off the
        queue, where an answer would land on the next request's."""
        if _int(p.get("slot"), 0) != inventory.MASK_BAG or _int(p.get("target"), 0):
            return False
        self.awaiting_bag = False
        if self.skip_bag and self.in_grace():
            self.skip_bag = False
            log.info("  ..    the closed barter window's bag request goes unanswered")
            return True
        self.skip_bag = False
        return False

    # --- the world moving underneath ------------------------------------------------
    def moved(self):
        """After a step in the location: a barter needs the two side by
        side, the way it was proposed."""
        deal = self.deal
        if deal is None:
            return
        s, other = self.sess, deal.other(self.sess).sess
        loc = s.loc
        if other.room is s.room and progression.within_reach(
                s.pos, other.pos, loc.width, loc.height):
            return
        log.info("  ..    %s walks away from a barter", s.nick)
        finish(deal, {other: "%s отошёл, бартер отменён" % s.nick,
                      s: "Вы отошли, бартер отменён"})

    def left(self):
        """Out of the room: the map, another location, a /goto, home."""
        deal = self.deal
        if deal is not None:
            log.info("  ..    %s leaves the room mid-barter", self.sess.nick)
            finish(deal, {deal.other(self.sess).sess:
                          "%s ушёл, бартер отменён" % self.sess.nick})

    def died(self):
        deal = self.deal
        if deal is not None:
            log.info("  ..    %s dies mid-barter", self.sess.nick)
            finish(deal, {deal.other(self.sess).sess:
                          "%s погиб, бартер отменён" % self.sess.nick})

    def close(self):
        """The connection is going: logout, a dropped socket, the same
        character logging in elsewhere. Only the other side is told."""
        deal = self.deal
        if deal is not None:
            log.info("  ..    %s leaves the game mid-barter", self.sess.nick)
            finish(deal, {deal.other(self.sess).sess:
                          "%s вышел из игры, бартер отменён" % self.sess.nick})
        self.awaiting_bag = self.skip_bag = False
        self.ended = None


# --- the deal as a whole ---------------------------------------------------------------
def show(side, code, obj=EMPTY):
    """Relay one move of the other side's to side's window, and keep track
    of the other side's light there. A 5 turns it on (Barter.vavReady);
    a 3, 4, 6, 7 or 8 turns it off, and this side's own with it (the
    vavReady setter clears iReady) -- once the frame arrives, so for
    READY_SETTLE more the window may still show it on."""
    now = time.monotonic()
    if code == UPD_APPLY:
        side.lit, side.lit_at = True, now
    elif side.lit:
        side.lit = False
        side.lit_until = now + READY_SETTLE
    side.sess.barter.relay(code, obj)


def changed(deal, me):
    """The table changed on me's side: nobody is ready any more -- the
    windows turn both lights off by themselves (Barter.iReady/vavReady) --
    and a ready from the other side is not taken for a moment.

    me's window put the other side's light out itself as it sent the change.
    But a 5 of theirs relayed less than READY_SETTLE before the change got
    here may have crossed it on the way and lit it again after; nothing
    else would ever put that light out, and a click on me's own button
    would then find both on and run applyBarter. So me gets a 6 of its own
    then. A 5 older than that reached the window before the change left it."""
    now = time.monotonic()
    deal.proposer.ready = deal.invitee.ready = False
    deal.other(me.sess).quiet_until = now + READY_SETTLE
    if me.lit:
        if now - me.lit_at < READY_SETTLE:
            show(me, UPD_BREAK)
        else:
            me.lit = False


def expire(deal):
    """The invitation went unanswered."""
    deal.timer = None
    if deal.open or deal.proposer.sess.barter.deal is not deal:
        return
    invitee = deal.invitee.sess
    log.info("  ..    %s never answered a barter", invitee.nick)
    finish(deal, {deal.proposer.sess:
                  "%s не ответил на предложение бартера" % invitee.nick})


def owns(sess, row):
    """Whether this offered row is still where it was offered from: the
    owner's bag, and the owner's."""
    now = sess.barter.store.item(row["uniq"])
    return now is not None and now["char_id"] == sess.char_id \
        and now["slot"] == inventory.BAG


def finish(deal, texts, spare=(), applied=False):
    """End a deal that did not go through.

    Every client whose Barter is alive gets ss_upd 0 -- all but `spare`,
    whose own close already killed it or which never built one -- and then
    its bag as it really is: its own offered things are back in it (the
    window puts nothing back when the server closes it), and, when both had
    said yes (`applied`), the other side's things are not, whatever
    applyBarter did with them. texts: a line of chat for whoever should
    hear why.

    Each side is seen to on its own: the deal is already gone for both, so
    a side whose resync failed half way (a database gone from under
    owns()) must not cost the other its ss_upd 0 -- a Barter left alive
    blocks every invitation and proposal until the player logs in again."""
    if deal.timer is not None:
        deal.timer.cancel()
        deal.timer = None
    for side in deal.sides():
        if side.sess.barter.deal is deal:
            side.sess.barter.deal = None
        side.sess.inv.locked.difference_update(side.items)
    for side in deal.sides():
        sess = side.sess
        if sess in spare or sess.closed:
            continue
        try:
            sess.barter.kill()
            for row in side.items.values():
                if owns(sess, row):
                    sess.inv.push_status(row, 1)
            if applied:
                for row in deal.other(sess).items.values():
                    sess.inv.push_status(row, 0)
            text = texts.get(sess)
            if text:
                sess.say(text)
        except Exception:                                   # noqa: BLE001
            log.exception("  !!    ending the barter for %s failed half way",
                          sess.nick)


def obstacle(deal):
    """Why the two cannot trade this instant, or None."""
    a, b = deal.proposer.sess, deal.invitee.sess
    for s in (a, b):
        if s.closed or s.barter.deal is not deal:
            return "%s уже не здесь" % s.nick
        if s.combat.dead:
            return "%s погиб" % s.nick
    if a.room is None or a.room is not b.room or not progression.within_reach(
            a.pos, b.pos, a.loc.width, a.loc.height):
        return "вы разошлись"
    return None


def settle(deal, me, them):
    """Both said yes: the exchange, all of it in one transaction or none.

    me is the side whose yes came last. Its window has already moved the
    other side's list into its bag (applyBarter) on seeing both lights on;
    them's window does the same on the ss_upd 5 relayed a moment ago. The
    server's own answer follows as for any other end, plus the purse."""
    a, b = deal.proposer, deal.invitee
    why = obstacle(deal)
    cha, chb = a.sess.character(), b.sess.character()
    purse_a = (cha.afro - a.afro + b.afro, cha.gold - a.gold + b.gold)
    purse_b = (chb.afro - b.afro + a.afro, chb.gold - b.gold + a.gold)
    if why is None:
        for side, ch in ((a, cha), (b, chb)):
            if not ch.can_afford(side.afro, side.gold):
                why = "у %s не хватает денег" % side.sess.nick
                break
    if why is None:
        moves = [(row, b.sess.char_id) for row in a.items.values()] \
            + [(row, a.sess.char_id) for row in b.items.values()]
        store = a.sess.barter.store
        try:
            stale = store.barter_swap(
                moves, [(a.sess.char_id,) + purse_a, (b.sess.char_id,) + purse_b])
        except Exception:                                   # noqa: BLE001
            # Rolled back with the transaction; the purses in memory are
            # untouched as well, so this is a refusal like any other.
            log.exception("  !!    the barter between %s and %s failed to write",
                          a.sess.nick, b.sess.nick)
            why = "не удалось записать, попробуйте ещё раз"
        else:
            if stale is not None:
                why = "вещи изменились"
                log.info("  ..    barter between %s and %s: item %s is not as offered",
                         a.sess.nick, b.sess.nick, stale)
    if why is not None:
        log.info("  ..    barter between %s and %s did not go through: %s",
                 a.sess.nick, b.sess.nick, why)
        finish(deal, {a.sess: "Бартер не состоялся: " + why,
                      b.sess: "Бартер не состоялся: " + why}, applied=True)
        return
    # Committed: the purses in memory are the ones Character.save writes
    # back, so they follow the database now, and nothing after this may undo
    # it.
    cha.afro, cha.gold = purse_a
    chb.afro, chb.gold = purse_b
    log.info("  ..    barter done: %s gives %d item(s), %d afro, %d gold;"
             " %s gives %d item(s), %d afro, %d gold",
             a.sess.nick, len(a.items), a.afro, a.gold,
             b.sess.nick, len(b.items), b.afro, b.gold)
    them.sess.barter.relay(UPD_APPLY)
    for side in deal.sides():
        side.sess.barter.deal = None
        side.sess.inv.locked.difference_update(side.items)
    for side in deal.sides():
        # One side at a time, as in finish(): the exchange stands whatever
        # goes wrong telling one of them about it.
        sess, other = side.sess, deal.other(side.sess)
        try:
            sess.barter.kill()
            for row in side.items.values():
                sess.inv.push_status(row, 0)
            for row in other.items.values():
                sess.inv.push_status(row, 1)
            sess.push_money()
            sess.say("Бартер с %s состоялся" % other.sess.nick)
        except Exception:                                   # noqa: BLE001
            log.exception("  !!    telling %s of the barter failed half way",
                          sess.nick)
