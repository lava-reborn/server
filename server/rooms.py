"""Rooms: the places where more than one player can stand at once.

A room is one location shared by everyone in it, and the global map is a room
of its own. Rooms own what used to live in each Session -- the inhabitants and
who else is present -- and they fan frames out to their subscribers.

One axiom drives the whole design: to the client, id 0 is always "me"
(Gamer.as:31 sets Gamer.ID = 0; PlayerRegister.getPlayer and
Location.getWalker both resolve a falsy id to the gamer). So a single fact --
"player 1000017 walked this path" -- is a different frame for every receiver:
id=0 to 1000017 itself, id=1000017 to everyone else. broadcast() therefore
takes the frame per viewer and rewrites the viewer's own id to 0.

Ids are global and stable. PlayerRegister.removePlayer never deletes a Player
entity (only NPCs and mobs go), so once a client has seen an id it keeps that
entity for the rest of its session; the same id must mean the same person for
as long as the server runs, and never collide with an NPC. NPCs take one
counter shared by every room, players take 1_000_000 + character id.
"""
import asyncio
import logging
from collections import namedtuple

import names
import world
from protocol import Str

log = logging.getLogger("lava")

# Entity ids: 0 is always the viewer, so anything placed in the world starts
# above that. Players sit far above the NPC counter so the two never meet.
FIRST_NPC_ID = 100
PLAYER_ID_BASE = 1_000_000

# What userInfo_Player for a stranger says about health, until characters
# carry real statistics. usrUp is what fills the bars over a player's head
# (Entity.userUpdate); without it they stay empty.
HP_MAX = 100
SP_MAX = 100


def player_id(char_id):
    return PLAYER_ID_BASE + char_id


def is_player_id(entity_id):
    return entity_id >= PLAYER_ID_BASE


class IdAllocator:
    """Hands out NPC ids, once each, for the life of the process."""

    def __init__(self, first=FIRST_NPC_ID):
        self._next = first

    def npc(self):
        out = self._next
        self._next += 1
        return out


# One inhabitant of a location: the hex it stands on, the creature type from
# the location file, and the root class the client builds for it (rtype).
NPC = namedtuple("NPC", "cell type_id root")


def viewer_frame(cmd, params):
    """A frame function showing the viewer as id 0.

    Any integer parameter equal to the viewer's own player id becomes 0, which
    is how the client recognises itself (Gamer.as:31). Lists and strings are
    left alone: nothing in them is ever the viewer's id.
    """
    def fn(viewer):
        return cmd, {k: (0 if isinstance(v, int) and not isinstance(v, bool)
                         and v == viewer.pid else v)
                     for k, v in params.items()}
    return fn


class Room:
    """One location, shared. Subscribers are sessions standing in it."""

    def __init__(self, loc, ids, mob_types):
        self.loc = loc
        # entity id -> NPC, allocated once: every player in this room sees the
        # same trader under the same id, and a second visit finds it unchanged.
        self.npcs = {}
        # sessions present, in order of arrival (dict as an ordered set)
        self.players = {}
        # War state and the fight itself live in combat.RoomCombat, made on
        # the first entry; ws is what lcall reports, and lch;ws=1/0 switch it.
        self.ws = False
        self.combat = None
        skipped = 0
        for cell, type_id in loc.spawns:
            # A creature the client has no record of cannot be drawn or named.
            # res misses in its copy of mobs.xml and the art resolves to
            # mobs/undefined.xml, and worse, the name id reaches the client
            # unknown, which fetches a string batch and puts the login screen
            # back on top of the game. 670 of the type ids used by locations
            # are absent from mobs.xml, so this is not a rare corner.
            if type_id not in mob_types or not names.known(type_id):
                skipped += 1
                continue
            root, name, _art = mob_types[type_id]
            # The file lists everyone who ever stood here, seasonal stalls
            # and clan-event vendors included; world.belongs_here says who
            # belongs to the place itself.
            if not world.belongs_here(type_id, name, root, loc.war):
                skipped += 1
                continue
            self.npcs[ids.npc()] = NPC(cell, type_id, root)
        log.info("  ..    room %s (%s) holds %d inhabitants%s",
                 loc.title, loc.file, len(self.npcs),
                 ", %d unknown to the client" % skipped if skipped else "")

    def npc(self, entity_id):
        return self.npcs.get(entity_id)

    def player(self, pid):
        for sess in self.players:
            if sess.pid == pid:
                return sess
        return None

    def broadcast(self, frame, exclude=None):
        """Send one fact to everyone here, shaped for each receiver.

        frame is either a callable viewer -> (cmd, params) | None, or a plain
        (cmd, params) pair, which then goes through viewer_frame so the
        receiver's own id reads as 0.
        """
        fn = frame if callable(frame) else viewer_frame(*frame)
        for sess in list(self.players):
            if sess is exclude:
                continue
            out = fn(sess)
            if out:
                sess.send(out[0], **out[1])

    def snapshot_for(self, sess):
        """Everything already here, for someone who just arrived.

        Two passes for the inhabitants, and the order is what makes them
        visible. A positioned lch builds the figure at once, and the figure
        resolves its art from persType, which only userInfo supplies. Place
        first and it asks for mobs/undefined.xml once, never retries, and
        leaves a placeholder cone standing there. So each placement is
        followed immediately by that inhabitant's details.

        Other players are placed with rtype=-1: PlayerRegister.createPlayer
        builds a Player for anything outside 0..7, and for an id it already
        knows, -1 makes addPlayer ask for that player's gear again. Their
        details are not pushed: the new Player entity sends getInfo;type=0
        and ss_get;slot=3 of its own accord (Entity.as:38-41, Player.as:11-18),
        and the answers go back to whoever asked.
        """
        for npc_id, npc in self.npcs.items():
            sess.send("lch", newUser=npc_id, pos=npc.cell, rtype=npc.root)
            sess.send_npc_info(npc_id)
        for other in self.players:
            if other is not sess:
                sess.send("lch", newUser=other.pid, pos=other.pos, rtype=-1)

    def enter(self, sess):
        """Arrival, after the client's lenter: snapshot to the newcomer,
        the newcomer to everyone else. The client adds its own figure itself
        (Master.lenter -> currentLocation.addGamer), so the newcomer never
        hears about its own id."""
        if sess in self.players:
            return
        self.players[sess] = True
        self.snapshot_for(sess)
        self.broadcast(("lch", dict(newUser=sess.pid, pos=sess.pos, rtype=-1)),
                       exclude=sess)
        log.info("  ..    %s enters %s (%d here)",
                 sess.nick, self.loc.title, len(self.players))

    def leave(self, sess):
        """Departure for any reason: map, /goto, logout, a dropped socket.

        Only the others are told. The leaver's client kills its Location on
        the next gmap or lenter and removes every entity itself
        (Location.kill), and a lostUser about oneself would be looked up in
        the register as a stranger.
        """
        if self.players.pop(sess, None) is None:
            return
        self.broadcast(("lch", dict(lostUser=sess.pid)))
        log.info("  ..    %s leaves %s (%d left)",
                 sess.nick, self.loc.title, len(self.players))


class Rooms:
    """loc_id -> Room, created on first entry and kept."""

    def __init__(self, mob_types, ids=None):
        self.mob_types = mob_types
        self.ids = ids or IdAllocator()
        self.rooms = {}

    def get(self, loc_id):
        room = self.rooms.get(loc_id)
        if room is None:
            room = self.rooms[loc_id] = Room(world.location(loc_id), self.ids,
                                             self.mob_types)
        return room


class GlobalMapRoom:
    """The map as a room: who is on it, and who can see whom.

    Every other player on the map has a one-second timer on the client
    (MapObject.checkLive) that only a userMove resets: after 3 s of silence
    the figure fades, after 6 s it is removed without a word. So each viewer
    is sent a userMove for every visible player on a fixed beat, moving or
    not, and the beat has to be under 3 s.
    """
    HEARTBEAT = 2.0

    def __init__(self, radius):
        self.radius = radius
        # session -> the set of sessions it has been shown (newUser sent and
        # no userLost since)
        self.seen = {}
        self._timer = None

    def enter(self, sess):
        """After gmap: the newcomer and its neighbours learn of each other."""
        if sess in self.seen:
            return
        self.seen[sess] = set()
        self._refresh()
        if self._timer is None:
            self._arm()

    def leave(self, sess):
        """Into a cell, /goto, logout, a dropped socket: userLost to whoever
        could see the leaver."""
        if self.seen.pop(sess, None) is None:
            return
        for other, shown in self.seen.items():
            if sess in shown:
                shown.discard(sess)
                other.send("userLost", id=sess.pid)
        if not self.seen and self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def moved(self, sess):
        """A new leg or an arrival: whoever sees sess gets the vector now
        rather than on the next beat, so the figure turns when the player
        does."""
        for other, shown in self.seen.items():
            if sess in shown:
                self._send_move(other, sess)

    # --- internals -------------------------------------------------------
    def _within(self, a, b):
        ax, ay = a.current_pos()
        bx, by = b.current_pos()
        return (ax - bx) ** 2 + (ay - by) ** 2 <= self.radius ** 2

    def _refresh(self):
        """Bring each viewer's shown set in line with who is in radius:
        newUser for the newly visible, userLost for those gone out of it."""
        for viewer, shown in self.seen.items():
            visible = {o for o in self.seen
                       if o is not viewer and self._within(viewer, o)}
            for other in visible - shown:
                self._introduce(viewer, other)
            for other in shown - visible:
                viewer.send("userLost", id=other.pid)
            shown.clear()
            shown.update(visible)

    def _introduce(self, viewer, other):
        """newUser carries an offset the client SUBTRACTS from its own cell
        (GlobalMap.newUser: x = gamer.x - dx), so the offset is viewer minus
        other, in whole cells. The absolute position and speed follow at once
        in a userMove, which is also what starts the client's liveness
        timer for the figure."""
        vx, vy = viewer.current_pos()
        ox, oy = other.current_pos()
        viewer.send("newUser", id=other.pid,
                    dx=int(round(vx - ox)), dy=int(round(vy - oy)))
        self._send_move(viewer, other)

    def _send_move(self, viewer, other):
        """userMove on the map is absolute: dx/dy are the cell, fractional in
        flight, vx/vy cells per second. t is read and never used."""
        x, y = other.current_pos()
        speed_x, speed_y = (other.leg[3], other.leg[4]) if other.leg else (0, 0)
        viewer.send("userMove", id=other.pid, dx=x, dy=y,
                    vx=speed_x, vy=speed_y, t=0)

    def _arm(self):
        self._timer = asyncio.get_running_loop().call_later(
            self.HEARTBEAT, self._tick)

    def _tick(self):
        self._timer = None
        self._refresh()
        for viewer, shown in self.seen.items():
            for other in shown:
                self._send_move(viewer, other)
        if self.seen:
            self._arm()


class Directory:
    """Who is online, by character: the registry behind private chat,
    getInfo about a stranger and the world channel."""

    def __init__(self):
        self.by_char = {}

    def add(self, sess):
        """Register a session for its character.

        The same character on two sockets would share one player id, and to
        every other client that is one entity, so the earlier socket is
        closed: the later login wins, as it did on the original.
        """
        old = self.by_char.get(sess.char_id)
        if old is not None and old is not sess:
            log.info("  ..    %s logged in again, dropping the older socket",
                     sess.nick)
            old.close()
        self.by_char[sess.char_id] = sess

    def remove(self, sess):
        if self.by_char.get(sess.char_id) is sess:
            del self.by_char[sess.char_id]

    def by_pid(self, pid):
        return self.by_char.get(pid - PLAYER_ID_BASE)

    def by_nick(self, nick):
        """Private chat addresses by name (ChatPan.sendMessage cuts the
        'private Nick: ' prefix and sends to=@Nick@); the id never travels."""
        for sess in self.by_char.values():
            if sess.nick == nick:
                return sess
        want = nick.casefold()
        for sess in self.by_char.values():
            if sess.nick.casefold() == want:
                return sess
        return None

    def __iter__(self):
        return iter(list(self.by_char.values()))


def player_info(sess):
    """userInfo_Player about a stranger, as Entity.userInfo and Player.userInfo
    read it: name is text, not a string id (Entity.as:66-70); sex picks the
    body and res the portrait, both from the same avatars/list.xml row; ally
    must be truthy; afro, gold and transport are read only by Gamer.userInfo
    for id 0 and are not sent for anyone else."""
    pers = sess.active
    ch = sess.character()
    return dict(id=sess.pid, name=Str(pers["name"]), sex=pers["sex"],
                res=Str(str(pers["res"])), ail=0, ally=1, lvl=ch.level,
                rep=[ch.rep], bg_rep=ch.bg_rep, bg_pen=ch.bg_pen, hl=0,
                pr=ch.premium_level())


def player_health(sess):
    """usrUp about a stranger: their real bars, from their own Character."""
    return dict(id=sess.pid, **sess.character().vitals())
