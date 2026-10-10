"""Parties: a handful of players who share a chat channel and a roster.

The client side is lol/core/party/PartyManager.as with the panel in
lol/services/ChatPan.as; recon/analysis/world.md section 8 has the frames.
One command each way, p_op;op=<N>;id=<id> from the client and
p_op;op=<N>;mob_id=<id> from the server, plus p_m;list=|..| carrying the
whole roster with the leader first.

Every id in a frame is in the receiver's coordinates: the receiver is 0
(Gamer.as:31), everyone else their player id. PARTY_RECEIVE_JOIN even
relies on it, adding 0 to an empty list before the newcomer so the
inviter's own entry exists.

Acknowledgements: ops 0-4 register a cmdAck handler, op 5 (list) does not
and is answered by p_m alone (server.expects_ack). After res=0 to an
invitation answer the client asks for the list itself (errorReport), so
the newcomer hears the roster twice; PartyListReceived just replaces it.
One drift cannot be helped from here: a client with "decline invitations"
switched on answers op=0 with an UNREGISTERED op=3 (PartyManager
.PartyCommandReceived), and the acknowledgement it earns lands on the
next command.

Membership is by character, not socket: a dropped link is reported as
"disconnected" (op 6) and the same character back on a new socket as
"returned" (op 5), with the roster re-sent so the fresh PartyManager can
rebuild its panel. A party with nobody left online is forgotten.
"""
import logging

import rooms
from protocol import Str

log = logging.getLogger("lava")

# p_op from the client (PartyManager.PARTY_SEND_*)
SEND_INVITE, SEND_KICK, SEND_YES, SEND_NO, SEND_LEADER, SEND_LIST = range(6)

# p_op to the client (PartyManager.PARTY_RECEIVE_*)
(RECV_INVITE, RECV_LEAVE, RECV_KICKED, RECV_LEADER, RECV_JOIN, RECV_ONLINE,
 RECV_OFFLINE, RECV_EXIST, RECV_REFUSE, RECV_DISBAND) = range(10)

# cmdAck codes. 31 is the one the client words (Gamer.invitePlayer: "Игрок
# не может быть приглашен в ваш отряд в данный момент"); any other
# non-zero answer to kick/leave/leader gets a generic alert from ChatPan
# and to an invitation answer only a trace.
RES_OK = 0
RES_REFUSED = 3
RES_CANT_INVITE = 31

# Designed: the panel has no hard limit, six keeps it readable.
PARTY_MAX = 6


class Party:
    def __init__(self, leader):
        self.members = [leader]      # character ids, the leader first
        self.present = {leader}      # members with a live socket

    @property
    def leader(self):
        return self.members[0]


class Parties:
    """Every party on the server, and every invitation still open."""

    def __init__(self, directory):
        self.directory = directory   # rooms.Directory: who is online
        self.by_char = {}            # character id -> Party
        self.invites = {}            # invited character id -> inviter's

    # --- plumbing ----------------------------------------------------------
    def session_of(self, char_id):
        return self.directory.by_pid(rooms.player_id(char_id))

    def party_of(self, sess):
        return self.by_char.get(sess.char_id) if sess.char_id else None

    def tell(self, party, op, about=None, exclude=None):
        """p_op to every member online, the subject in each one's own
        coordinates."""
        for char_id in list(party.present):
            sess = self.session_of(char_id)
            if sess is None or sess is exclude:
                continue
            mob_id = 0 if about is None or about == char_id else rooms.player_id(about)
            sess.send("p_op", op=op, mob_id=mob_id)

    def roster_for(self, party, sess):
        sess.send("p_m", list=[0 if c == sess.char_id else rooms.player_id(c)
                               for c in party.members])

    def roster(self, party):
        for char_id in list(party.present):
            sess = self.session_of(char_id)
            if sess is not None:
                self.roster_for(party, sess)

    def dissolve(self, party):
        for char_id in party.members:
            if self.by_char.get(char_id) is party:
                del self.by_char[char_id]
        self.tell(party, RECV_DISBAND)
        party.members = []
        party.present = set()

    def remove(self, party, char_id, op):
        """One member gone, by their own choice or the leader's: the rest
        hear which, then the new leader if it was the leader, then the
        roster. Down to one member the party is over: the client itself
        clears a list of one (PartyManager.leaveParty)."""
        was_leader = party.leader == char_id
        party.members.remove(char_id)
        party.present.discard(char_id)
        if self.by_char.get(char_id) is party:
            del self.by_char[char_id]
        self.tell(party, op, char_id)
        if len(party.members) < 2:
            self.dissolve(party)
            return
        if was_leader:
            self.tell(party, RECV_LEADER, party.leader)
        self.roster(party)

    # --- p_op ----------------------------------------------------------------
    def op(self, sess, op, target):
        if op == SEND_INVITE:
            self.invite(sess, target)
        elif op == SEND_KICK:
            if target == 0:
                self.leave(sess)
            else:
                self.kick(sess, target)
        elif op in (SEND_YES, SEND_NO):
            self.answer(sess, op == SEND_YES)
        elif op == SEND_LEADER:
            self.make_leader(sess, target)
        elif op == SEND_LIST:
            self.send_list(sess)
        else:
            sess.send("cmdAck", res=RES_REFUSED)

    def invite(self, sess, guest_pid):
        """op=0: ask a player, by entity id, into the party. Only from the
        leader, or from anyone not yet in one; the guest must be online,
        free, and not already asked."""
        guest = self.directory.by_pid(guest_pid) if rooms.is_player_id(guest_pid) else None
        party = self.party_of(sess)
        if (not sess.char_id or guest is None or guest is sess or guest.closed
                or not guest.char_id or guest.char_id in self.by_char
                or guest.char_id in self.invites
                or (party is not None and (party.leader != sess.char_id
                                           or len(party.members) >= PARTY_MAX))):
            sess.send("cmdAck", res=RES_CANT_INVITE)
            return
        self.invites[guest.char_id] = sess.char_id
        sess.send("cmdAck", res=RES_OK)
        # The client opens "Персонаж <name> приглашает вас отряд" with the
        # name looked up by this id, so the guest should have seen the
        # inviter's figure; the context menu only offers players in view.
        guest.send("p_op", op=RECV_INVITE, mob_id=sess.pid)
        log.info("  ..    %s invites %s to a party", sess.nick, guest.nick)

    def answer(self, sess, yes):
        """op=2 / op=3: the invited player's reply."""
        inviter_char = self.invites.pop(sess.char_id, None) if sess.char_id else None
        inviter = self.session_of(inviter_char) if inviter_char is not None else None
        if inviter is None:
            sess.send("cmdAck", res=RES_REFUSED)
            return
        if not yes:
            sess.send("cmdAck", res=RES_OK)
            inviter.send("p_op", op=RECV_REFUSE, mob_id=sess.pid)
            return
        party = self.by_char.get(inviter_char)
        if sess.char_id in self.by_char or (
                party is not None and (party.leader != inviter_char
                                       or len(party.members) >= PARTY_MAX)):
            sess.send("cmdAck", res=RES_REFUSED)
            return
        if party is None:
            party = self.by_char[inviter_char] = Party(inviter_char)
        party.members.append(sess.char_id)
        party.present.add(sess.char_id)
        self.by_char[sess.char_id] = party
        sess.send("cmdAck", res=RES_OK)
        self.tell(party, RECV_JOIN, sess.char_id, exclude=sess)
        self.roster(party)
        log.info("  ..    %s joins %s's party (%d)", sess.nick, inviter.nick,
                 len(party.members))

    def leave(self, sess):
        """op=1 with id=0: out by choice. The leaver's client clears its
        own panel on res=0 (ChatPan.ResultLeaveGroup), so it hears no
        more."""
        party = self.party_of(sess)
        if party is None:
            sess.send("cmdAck", res=RES_REFUSED)
            return
        sess.send("cmdAck", res=RES_OK)
        self.remove(party, sess.char_id, RECV_LEAVE)
        log.info("  ..    %s leaves the party", sess.nick)

    def kick(self, sess, pid):
        """op=1 with a member's id: the leader throws them out. The victim
        is told with mob_id=0, which their PartyManager.leaveParty reads as
        itself and clears everything."""
        party = self.party_of(sess)
        victim_char = pid - rooms.PLAYER_ID_BASE
        if (party is None or party.leader != sess.char_id
                or victim_char == sess.char_id or victim_char not in party.members):
            sess.send("cmdAck", res=RES_REFUSED)
            return
        sess.send("cmdAck", res=RES_OK)
        victim = self.session_of(victim_char)
        if victim is not None:
            victim.send("p_op", op=RECV_KICKED, mob_id=0)
        self.remove(party, victim_char, RECV_KICKED)
        log.info("  ..    %s kicked from the party by %s", victim_char, sess.nick)

    def make_leader(self, sess, pid):
        """op=4: hand the lead to a member. Everyone, the old leader
        included, gets op=3 and then the roster with the new order."""
        party = self.party_of(sess)
        new_char = pid - rooms.PLAYER_ID_BASE
        if (party is None or party.leader != sess.char_id
                or new_char == sess.char_id or new_char not in party.members):
            sess.send("cmdAck", res=RES_REFUSED)
            return
        party.members.remove(new_char)
        party.members.insert(0, new_char)
        sess.send("cmdAck", res=RES_OK)
        self.tell(party, RECV_LEADER, new_char)
        self.roster(party)

    def send_list(self, sess):
        """op=5, no acknowledgement. Silence when there is no party: an
        empty p_m would still make ChatPan.partyUpdate open the party
        channel and panel for a player who has none."""
        party = self.party_of(sess)
        if party is not None:
            self.roster_for(party, sess)

    # --- chat --------------------------------------------------------------
    def chat(self, sess, raw):
        """Channel 1: the entry verbatim to every other member online, with
        the nick, the way channel 0 does it. True if there was a party."""
        party = self.party_of(sess)
        if party is None:
            return False
        for char_id in list(party.present):
            other = self.session_of(char_id)
            if other is not None and other is not sess:
                other.send("userMsg", group=1, nick=Str(sess.nick),
                           entry=Str(raw), **{"from": sess.pid})
        return True

    # --- presence ------------------------------------------------------------
    def online(self, sess):
        """A character with a socket again, from server.enter_location: the
        first time each session, the others hear op=5 and the returner
        gets the roster its new PartyManager has never seen."""
        party = self.party_of(sess)
        if party is None or sess.char_id in party.present:
            return
        party.present.add(sess.char_id)
        self.tell(party, RECV_ONLINE, sess.char_id, exclude=sess)
        self.roster_for(party, sess)

    def disconnected(self, sess):
        """From Session.close, so it must not raise: whatever goes wrong in
        here is logged and the socket still closes."""
        try:
            if sess.char_id:
                self.invites.pop(sess.char_id, None)
                for guest, host in list(self.invites.items()):
                    if host == sess.char_id:
                        del self.invites[guest]
            party = self.party_of(sess)
            if party is None or sess.char_id not in party.present:
                return
            party.present.discard(sess.char_id)
            if not party.present:
                # Nobody left to tell; the party will not be waited for.
                self.dissolve(party)
                return
            self.tell(party, RECV_OFFLINE, sess.char_id)
        except Exception:
            log.exception("  !!    party bookkeeping failed on disconnect")
