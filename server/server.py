"""Minimal LAVA Online server: login, character creation, and entering a location.

Enough of the protocol to get a freshly made character standing in a location
and walking around. Everything not implemented is logged rather than ignored,
so the remaining surface stays visible.

Two rules govern nearly every handler here (see PROTOCOL.md):

  * cmdAck is a strict FIFO queue. Exactly one per command that expects one,
    in arrival order. selPers expects none, and answering it desynchronises
    every later reply.
  * Requests the client pipelines (q_list, ss_get, rp_get_info) must always be
    answered, including with empty payloads, or its request window never
    reopens and it stalls with no error shown.
"""
import asyncio
import json
import logging
import math
import os
import signal
import time

import accounts
import combat
import inventory
import items
import mail
import names
import party
import rooms
import progression
import quests
import transport
import travel
import world
from protocol import BigUInt, FrameReader, decode, frame, Str

HOST = os.environ.get("LAVA_HOST", "0.0.0.0")
PORT = int(os.environ.get("LAVA_PORT", "9775"))
POLICY_PORT = 843
STORE = accounts.Store()

# Every connection with a Session behind it, so a stop can reach them all.
# handle_client adds on connect and removes in its finally.
SESSIONS = set()

# Commands whose sender registers a cmdAck handler, gathered from the client:
# mail, clans, party, auction, battlegrounds, item sessions, quests, map marks
# and chat all do. Anything here has to be answered, implemented or not.
#
# Not here, because the client sends them without registering anything, and
# an answer would be consumed by whichever command comes next:
#   ah_search  -- Auction.search waits on its own ah_sresult queue instead
#   updMark    -- GlobalMap.editMark just sends; insMark and rmMark do register
# Two more are in the set but only for some of their op values; see
# expects_ack() below.
EXPECTS_ACK = {
    "chkml", "getml", "sndml", "rmvml", "uldml",
    "p_op", "admit", "apply", "head", "gg_info", "c_ga",
    "ah_create", "ah_op", "bg_op",
    "ss_move", "ss_use", "ss_heap_c", "ss_create", "ss_upd",
    "on_conv", "q_st", "q_co", "q_ca",
    "insMark", "rmMark",
    "userMsg", "resurrect", "actPlayer", "newPers", "lenter", "chWorld",
}


def expects_ack(cmd, params):
    """Whether this particular frame put a handler on the client's queue.

    For most commands that is a property of the command. For two it depends
    on the op value, because the same CSM class is sent from several places
    in the client and only some of them call XMLCCallStack.addCall:

      bg_op  BattleGroundManager registers for 0 (join queue) and 2 (leave
             queue) only; 3/4 answer an invitation, 5/7 leave a battleground
             and 6 asks for its info, all fire-and-forget.
      p_op   op 5 asks for the party list and is sent from errorReport with
             no handler; every other op (invite, kick, yes/no, leader)
             registers one. Caveat: op 3 is also sent unregistered from the
             auto-decline branch of PartyManager, so a player with that
             setting on will drift by one there; nothing here can tell.
    """
    if cmd == "bg_op":
        return int(params.get("op", -1)) in (0, 2)
    if cmd == "p_op":
        return int(params.get("op", -1)) != 5
    return cmd in EXPECTS_ACK

# Where a new character starts, as a cell of the global map. Cell 5970x1730
# is "Черный рынок Вади-Хальфы": peaceful (war="0", so walking costs no action
# points) and already populated in its own XML with 21 traders, an upgrader,
# a lessor and several commoners.
GLOBAL_X = int(os.environ.get("LAVA_GX", "5970"))
GLOBAL_Y = int(os.environ.get("LAVA_GY", "1730"))

# The location follows from the cell, so the two cannot drift apart. LAVA_LOC
# overrides it for trying a particular file out.
START_LOC = int(os.environ.get("LAVA_LOC", "0")) or world.location_at(
    GLOBAL_X, GLOBAL_Y)

# Portrait and body come from two different fields of the same avatars/list.xml
# row and have to be taken together: res selects the portrait, sex selects the
# body, because PersInfo.set sex assigns persType as a side effect. Row 0 is
# the one the creation screen offers first.
AVATARS = world.avatars()
START_AVATAR = int(os.environ.get("LAVA_AVATAR", "0"))

MOB_TYPES = world.mob_types()


def default_character():
    res, sex = AVATARS[START_AVATAR % len(AVATARS)]
    return {"name": "polestvr", "sex": sex, "res": res}


# The map is a plain grid, 5833..6305 by 1600..2110, and the client labels its
# cells from res/database/locations.xml on its own. Every cell can be entered:
# 86 of them hold a settlement recovered into data/settlements.json, and the
# rest resolve to open desert by world.location_at.
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second

# Shared world state, one of each for the process: locations as rooms, the
# map as a room, and who is online. Entity ids come from here too, so a
# trader keeps its id between two players and between two visits.
ROOMS = rooms.Rooms(MOB_TYPES)
GMAP = rooms.GlobalMapRoom(VIEW_RADIUS)
ONLINE = rooms.Directory()
# Parties outlive the sockets of their members (party.py), so they are
# kept here and not on the sessions.
PARTIES = party.Parties(ONLINE)

log = logging.getLogger("lava")

# Flash asks for a socket policy before connecting to a non-default port.
POLICY = (
    b'<?xml version="1.0"?>'
    b'<!DOCTYPE cross-domain-policy SYSTEM '
    b'"http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">'
    b'<cross-domain-policy>'
    b'<allow-access-from domain="*" to-ports="*"/>'
    b'</cross-domain-policy>\x00'
)

# Quest limits, sent in the constants frame and enforced here. The client
# refuses a take beyond quest_log_capacity on its own (QuestInterface.getQuest),
# but a modified one would not, so the server counts too. daily_reset_time is
# minutes past UTC midnight; the client only uses it for the journal caption.
QUEST_LOG_CAPACITY = 20
DAILY_MAX = 10
DAILY_RESET_TIME = 0

# A medic's fee, until healers carry their own price list.
MEDIC_PRICE = 10

# cmdAck codes for quest and service refusals. The client shows any non-zero
# answer to q_co as "сдали максимум ежедневных" (ErrorReport 44) and to
# on_conv;op=2 as GET_TRANSPORT_FAIL, so the distinctions are for the log.
RES_NO_SUCH = 1
RES_WRONG_NPC = 2
RES_NOT_READY = 3
RES_NOT_AVAILABLE = 4
RES_LOG_FULL = 5
RES_NO_MONEY = 21
RES_DAILY_LIMIT = 44


class Session:
    def __init__(self, writer, peer):
        self.writer = writer
        self.peer = peer
        self.closed = False
        self.hash = None
        self.logged_in = False
        self.account = None
        self.characters = []
        self.char_id = None
        self.active = None
        # progression.Character of the selected one; None until selPers/newPers
        self.char = None
        # id of the teacher a training session is open with, or None
        self.training = None
        # The rented vehicle as (type id, epoch second the rental ends), or
        # None on foot. Loaded with the character, written straight to the
        # characters table: Character.save does not carry these two columns,
        # so nothing overwrites a rental on the way out.
        self.transport = None
        self.loc = world.location(START_LOC)
        self.pos = self.loc.entry_cell()
        self.on_map = False
        # The cell the current location stands on, and where leaving returns
        # to. Fractional only while a leg of map travel is in flight.
        self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        self.arrival = None
        # a leg in flight: (start time, from x, from y, vx, vy)
        self.leg = None
        # s_type of the open session with an NPC (StuffManager.SESSION_*:
        # 1 trade, 2 barter, 3 bank, 4 training, 5 upgrade, 6 trophies), or
        # None. Which ss_upd frames get acknowledged depends on it.
        self.npc_session = None
        # the Room this session stands in, from lenter until it leaves
        self.room = None
        # Items, slots and the open stall: inventory.py. Reads the character
        # off this session, so it needs no update when the character changes.
        self.inv = inventory.Inventory(self, STORE)
        # Letters: mail.py. Needs the directory to push a new letter to an
        # addressee who is online.
        self.mail = mail.Mail(self, STORE, ONLINE)
        # Action points, the shot in flight, death and the loot window:
        # combat.py. Rooms hold the mobs and the war state.
        self.combat = combat.Fighter(self)

    @property
    def pid(self):
        """This player's entity id as every other client knows it. Never 0:
        that is what each client calls itself (Gamer.as:31)."""
        return rooms.player_id(self.char_id) if self.char_id else None

    @property
    def nick(self):
        return (self.active or default_character())["name"]

    # --- plumbing --------------------------------------------------------
    def send(self, *_cmd, **params):
        """Send one frame. The command name is positional, because several
        commands carry a parameter literally called "name"."""
        data = frame(_cmd[0], **params)
        log.info("  S->C  %s", data[:-1].decode("utf-8", "replace"))
        self.writer.write(data)

    def handle(self, cmd, params):
        log.info("  C->S  %s %s", cmd, params)
        # Dead: the client's own filter lets only resurrect through
        # (FilterManager.createDSFilter), so this is the server's copy of it.
        if self.combat.blocks(cmd, expects_ack(cmd, params)):
            return
        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
            # Commands that register a handler must be answered even when the
            # feature does not exist yet. A refusal keeps the queue in step; a
            # silence shifts every later reply onto the wrong handler.
            if expects_ack(cmd, params):
                self.send("cmdAck", res=3)
            return
        try:
            fn(params)
        except Exception:
            # A bug in one handler must not drop the player's connection.
            log.exception("  !!    handler for %r failed", cmd)

    # --- session ---------------------------------------------------------
    def cmd_hello(self, p):
        # The client ignores these params; it only needs a frame named "hello"
        # within 20s, or Session.helloTimeOutFunction drops the connection.
        self.send("hello", minor=2, major=0)

    def cmd_login(self, p):
        """The digest the client sends is the whole credential.

        Its login screen hashes password + login and sends only that, so there
        is nothing else to check it against: the digest identifies the account
        by itself. res=1 is what the client words as a wrong login, 2 as a ban.
        """
        self.hash = p.get("hash") or ""
        row = STORE.by_credential(self.hash)
        if not row:
            log.info("  ..    unknown credential, refusing")
            self.send("cmdAck", res=1)
            return
        if row["banned"]:
            self.send("cmdAck", res=2)
            return
        self.account = row
        self.characters = [dict(r) for r in STORE.characters(row["id"])]
        self.logged_in = True
        log.info("  ..    %s logged in, %d character(s)",
                 row["login"], len(self.characters))
        self.send("cmdAck", res=0)
        self.send_account()

    def send_account(self):
        """Push the account state the client waits for but never asks for.

        PersGenerator.checkFullInfo opens the character screen only once the
        avatar list has loaded AND accountInfo has arrived. accountInfo is
        discarded outright unless can_create is truthy, so a zero there leaves
        the client idle with no error of any kind.
        """
        # Premium bonuses are shares, not multipliers: the client takes the
        # totals it is sent and splits a share of b/(1+b) back out as the
        # premium part (SpecSkillMessages.getRealAndBonus, WeightPan), so a
        # 1 here would tell it that half of everything is bonus.
        self.send("constants",
                  gold_to_afro_rate=100,
                  quest_log_capacity=QUEST_LOG_CAPACITY,
                  leave_combat_timeout=combat.LEAVE_COMBAT_TIMEOUT,
                  premium_weight_bonus_1=progression.PREMIUM_WEIGHT_BONUS[1],
                  premium_weight_bonus_2=progression.PREMIUM_WEIGHT_BONUS[2],
                  premium_break_bonus_1=1, premium_break_bonus_2=2,
                  premium_xp_bonus_1=progression.PREMIUM_XP_BONUS[1],
                  premium_xp_bonus_2=progression.PREMIUM_XP_BONUS[2],
                  gold_repair_price_mod=1, gold_repair_mod=10000,
                  daily_max=DAILY_MAX, daily_reset_time=DAILY_RESET_TIME)
        for pers in self.characters:
            # death is a flag, not a count: PersGenerator.persInfo takes it
            # as Boolean(param.death) into PersInfo.dead, and that is what
            # Master.lenter and Master.gmap check to open the regeneration
            # window once the character is standing somewhere. A character
            # that logged out dead must come back to it.
            self.send("persInfo", num=pers["slot"], name=Str(pers["name"]),
                      sex=pers["sex"], death=int(bool(pers["death"])),
                      res=Str(str(pers["res"])))
        # can_create must be falsy once the account has someone, or the client
        # opens the creation screen instead of selecting: PersGenerator acts on
        # the flag alone and never looks at how many characters arrived.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=0 if self.characters else 1)

    def cmd_logout(self, p):
        self.close()

    def close(self):
        """Put the character away and drop the connection.

        Reached three ways -- logout, the finally in handle_client once the
        socket is gone, and a server stop -- and usually two of them in a
        row, so it has to be a no-op the second time: one write of the
        position, one close of the transport.
        """
        if self.closed:
            return
        self.closed = True
        # Whatever fails in here, the transport still closes: a socket left
        # open by a bug in one subsystem would otherwise hold up shutdown()
        # and keep a ghost in every room it was in.
        try:
            self.cancel_travel()
            self.inv.close()
            self.combat.close()         # never raises; see Fighter.close
            # Whoever shared a room or the map with this player is told now:
            # a dropped socket sends no logout, so this is the only place
            # that covers every way out.
            self.leave_room()
            GMAP.leave(self)
            ONLINE.remove(self)
            # The party keeps the seat and tells the others "отключился";
            # the same character on a new socket takes it back.
            PARTIES.disconnected(self)
            if self.char_id:
                STORE.save_position(self.char_id, self.loc.id, self.pos,
                                    self.gx, self.gy, self.on_map)
            if self.char:
                self.char.save(STORE)
        finally:
            self.writer.close()

    def shutdown(self):
        """The server is going: say so, then close as on logout.

        Session.shutdown in the client (Session.as:216) answers the frame
        with an alert -- "Сервер будет остановлен через N секунд" -- and
        asks for a restart, so the socket closing right behind it is what
        the player has just been told to expect.
        """
        if self.closed:
            return
        self.send("shutdown", seconds=0)
        self.close()
    def leave_room(self):
        if self.room is not None:
            self.combat.left()
            self.room.leave(self)
            self.room = None

    def load_character(self, char_id):
        """Bring the selected character's numbers into memory.

        Everything the client is later told about the character comes from
        this object, and it goes back to the database after each change
        that costs something and once more on the way out.
        """
        self.char = progression.Character.load(STORE, char_id)
        self.training = None
        # Whether this one is lying dead is the characters row's business,
        # not the Character's (accounts.CHARACTER_COLUMNS): combat.py wrote
        # it when the body fell and reads it back here, so a logout does not
        # undo a death. The client is told separately, by persInfo;death.
        # The rental rides in the same row and is read in the same breath.
        row = STORE.character(char_id)
        self.combat.restore(row)
        kind = row["transport_type"] if row is not None else None
        self.transport = (int(kind), int(row["transport_until"] or 0))             if kind else None

    def character(self):
        """The loaded character, or a newborn's numbers for a socket that
        asks before selecting one, so an early getInfo cannot fail."""
        return self.char or progression.Character()

    def transport_now(self):
        """The type id under the player, or None once the rental has run out.

        Expiry is noticed here rather than on a timer: nothing in the client
        counts the hours down on its own, and the only moments the number
        matters are the ones that pass through here -- a userInfo_Player, a
        step on the map. The database is cleared at the same time so the next
        login starts on foot.
        """
        if not self.transport:
            return None
        type_id, until = self.transport
        if transport.hours_left(until) > 0:
            return type_id
        self.transport = None
        if self.char_id:
            STORE.save_character_state(self.char_id, transport_type=None,
                                       transport_until=None)
        log.info("  ..    the rental of type %d has run out", type_id)
        return None

    # --- character -------------------------------------------------------
    def cmd_newPers(self, p):
        if not self.account:
            self.send("cmdAck", res=1)
            return
        name = (p.get("name") or "").strip()
        if not name:
            self.send("cmdAck", res=5)          # invalid characters in name
            return
        if STORE.name_taken(name):
            self.send("cmdAck", res=6)          # name already in use
            return
        char_id, slot = STORE.create_character(
            self.account["id"], name, int(p.get("sex", 0)),
            p.get("res", AVATARS[0][0]))
        self.characters = [dict(r) for r in STORE.characters(self.account["id"])]
        self.char_id = char_id
        self.active = next(c for c in self.characters if c["slot"] == slot)
        self.load_character(char_id)
        # A pistol and a pack of rounds in the bag, so there is something to
        # wear, load and sell before the first stall is found.
        self.inv.starter_kit(char_id)
        STORE.save_character_state(char_id, kit=1)
        log.info("  ..    created %r in slot %d", name, slot)
        # The client plays its intro after this, then sends actPlayer itself.
        self.send("cmdAck", res=0)

    def cmd_selPers(self, p):
        # Deliberately no cmdAck: PersGenerator does not register a handler for
        # one, so replying here would be consumed by the next command's.
        slot = int(p.get("num", 0))
        for c in self.characters:
            if c["slot"] == slot:
                self.active = c
                self.char_id = c["id"]
                self.load_character(c["id"])
                self.restore(c)
                # A character from before the inventory existed has an
                # empty bag and no kit flag: give the same pistol and
                # rounds a newborn gets, once.
                if not c.get("kit") and not STORE.items_of(c["id"]):
                    self.inv.starter_kit(c["id"])
                    STORE.save_character_state(c["id"], kit=1)
                    log.info("  ..    starter kit handed to %s", c["name"])
                break
        else:
            # A socket that never logged in, or names a slot it does not
            # have, gets no lcall: the client itself only allows selPers in
            # ENTER_STATE after a login (FilterManager.createEnterFilter),
            # so anything else is not the client.
            log.warning("  ??    selPers without a character, ignoring")
            return
        self.enter_location()

    def restore(self, c):
        """Put the character back where it was left.

        A saved location may no longer resolve -- the id could have come from
        an older table, or name a file this copy of the client does not have --
        so falling back to the starting cell has to be possible without
        losing the character.
        """
        if c["gx"] and c["gy"]:
            self.gx, self.gy = c["gx"], c["gy"]
        loc_id, pos = c["loc"], c["pos"]
        # selPers is always answered with an lcall, so the client starts in
        # a location whichever way the last session ended. Someone who left
        # on the map starts in the location of the cell they were over --
        # the one saved with them is the last they walked out of, possibly
        # cells away -- and the server must not think them still on the
        # map, or their first chWorld re-enters instead of leaving.
        if c["on_map"]:
            self.gx, self.gy = int(round(self.gx)), int(round(self.gy))
            loc_id, pos = travel.destination(self.gx, self.gy), None
        self.on_map = False
        if loc_id is not None:
            try:
                self.loc = world.location(loc_id)
            except (KeyError, OSError) as exc:
                log.warning("  ..    location %s unreadable (%s), starting over",
                            loc_id, exc)
                self.loc = world.location(START_LOC)
                self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        # A cell saved in one location means nothing in another, and a cell
        # outside the grid would put the player in a wall.
        if pos and 0 <= pos < self.loc.width * self.loc.height:
            self.pos = pos
        else:
            self.pos = self.loc.entry_cell()

    def cmd_actPlayer(self, p):
        if not self.char_id:
            self.send("cmdAck", res=1)
            return
        self.send("cmdAck", res=0)
        self.enter_location()

    # --- world -----------------------------------------------------------
    def enter_location(self):
        # An lcall makes the client drop its current Location (Master.lcall
        # builds a new LocGen), so whoever shared the old room is told now,
        # before the new one is even loading.
        self.leave_room()
        ONLINE.add(self)
        # A party member back on a socket: the others hear "в сети" and
        # this client gets the roster. A no-op on every later lcall.
        PARTIES.online(self)
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork. ws is the
        # room's actual war state, not the file's war flag: the flag only
        # says fighting is possible here, and a client told ws=1 spends
        # action points on every step from the moment it arrives. g_id is
        # the map cell, packed; beyond the map's edge it also says "no way
        # to the map from here" (travel.geo_id).
        self.send("lcall", id=self.loc.id, ws=int(ROOMS.get(self.loc.id).ws),
                  ie=0, g_id=travel.geo_id(self.loc, self.gx, self.gy))

    def cmd_lenter(self, p):
        """Answer the client's "I have loaded, let me in".

        No cmdAck on success: Master.lenter cancels the handler it registered
        for one as soon as the lenter frame lands, so the acknowledgement is
        the failure path only.
        """
        if not self.char_id:
            # Not a player: nothing to put in a room. The refusal is the one
            # case where lenter is acknowledged (see above).
            self.send("cmdAck", res=1)
            return
        # aspd is the action-point gain per 600ms tick, amax the ceiling:
        # APManager.setAP takes both from here and nowhere else.
        self.send("lenter", pos=self.pos, aspd=progression.AP_REGEN,
                  amax=self.character().ap_max)
        # How many quests may still be handed in today. Only QuestInspector
        # reads it, and that singleton exists from the first Entity built
        # (Entity.as:37), long before the location opens, so it lands.
        self.send("q_sys", daily_available=self.daily_available())
        self.enter_room()

    def enter_room(self):
        """Join the location as a room: its inhabitants and other players
        come to us, and we are announced to them. The spawn points and their
        type ids come straight out of the location file; only behaviour was
        stripped. See rooms.Room.snapshot_for for the frame order."""
        self.room = ROOMS.get(self.loc.id)
        self.room.enter(self)
        self.combat.entered()

    def cmd_chWorld(self, p):
        """One command, both directions: the button is a toggle.

        GlobalMapInterface.toLocation and LocationInterface both call
        changeWorld with no argument, so which way the player goes is decided
        here, from where they currently are. The one variant is to=1, the
        exit window's "other location" button (Location.exitLoc): from an
        exit cell that goes to whatever lies beyond it, never to the map.
        """
        # Too soon after a shot or a strike: res=39 instead, and nothing
        # moves -- checked before any door, or a fight could be walked out of.
        if self.combat.refuse_leave():
            return
        if not self.on_map and int(p.get("to", 0) or 0) == 1:
            self.leave_through_exit()
            return
        self.send("cmdAck", res=0)
        if self.on_map:
            self.enter_cell()
        else:
            # Leaving puts the player back on the cell the location stands
            # on -- or the nearest one the map has, from a location beyond
            # its edge: the client disables both map buttons there, but
            # the change-world hotkey (LocationInterface.toGlobal) does
            # not look, and a figure past the last tile would be lost.
            self.on_map = True
            self.cancel_travel()
            self.leave_room()
            self.gx, self.gy = travel.clamp(self.gx, self.gy)
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)
            self.send_marks()
            # Only after gmap: newUser is an offset from the client's own
            # figure, which Master.gmap has just created.
            GMAP.enter(self)

    def leave_through_exit(self):
        """chWorld;to=1: out through the exit the player is standing on.

        The client sends nothing about which exit that is (world.md §5), so
        travel reads the side off the cell. A side leads to the neighbouring
        map cell, arriving at the opposite edge; a door to the interior the
        table knows, or nowhere. Master.changeWorldAck treats any non-zero
        res but 39 as a silent return to the previous state, so the reason
        for a refusal goes to chat behind the acknowledgement.
        """
        side = travel.side_at(self.loc, self.pos)
        try:
            dest = travel.plan_exit(self.loc, self.pos,
                                    round(self.gx), round(self.gy))
        except travel.Refused as why:
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            self.say(str(why))
            return
        # Ack first, lcall second: changeWorldAck must run while the client
        # is still in CW_STATE, before Master.lcall starts the loader.
        self.send("cmdAck", res=0)
        self.cancel_travel()
        self.gx, self.gy = dest.gx, dest.gy
        self.loc = world.location(dest.loc_id)
        self.pos = dest.pos
        log.info("  ..    exit %s -> %s (%s) at %d, cell %d,%d", side,
                 self.loc.title, self.loc.file, self.pos, self.gx, self.gy)
        self.enter_location()

    def go_home(self):
        """Send the character home: an lcall into the location registered
        with on_conv;op=0, standing on its map cell, or the starting one.

        For the combat side to call from resurrect. Resurrector.resurrectAck
        closes the window and returns the client to LOCAL_STATE on
        cmdAck;res=0, and this lcall is what then moves the body; HP and
        the dead flag are the caller's, this only travels. Works from the
        map too, with one cosmetic catch: Master.lcall in GLOBAL_STATE with
        no chWorld sent first is read as an interception, and the preloader
        is captioned "На Вас напали" (Master.playerIntercepted).
        """
        row = STORE.character(self.char_id) if self.char_id else None
        loc_id, gx, gy = travel.home(row, (START_LOC, GLOBAL_X, GLOBAL_Y))
        self.on_map = False
        self.cancel_travel()
        GMAP.leave(self)
        self.gx, self.gy = gx, gy
        self.go_to(loc_id)
        log.info("  ..    %s goes home to %s (%s) at %d,%d",
                 self.nick, self.loc.title, self.loc.file, gx, gy)

    # --- map marks ---------------------------------------------------------
    # Bookmarks on the global map. Master.gmap builds a fresh GlobalMap every
    # time, and its markList only comes into being in GlobalMap.marks(), so
    # every gmap is followed by the whole list: dxdy as pairs of whole cells
    # relative to the player, title and info in parallel. Without the frame
    # addMark pushes into undefined and the panel is dead until relogin.
    # The position in that list is the id the client later edits and
    # removes by (GlobalMap.editMark, removeMark), so the store keeps the
    # same order and renumbers on removal as Array.splice does.

    def send_marks(self):
        rows = STORE.marks(self.char_id) if self.char_id else []
        self.send("marks", **travel.marks_frame(rows, self.gx, self.gy))

    def cmd_insMark(self, p):
        """GlobalMap.addMark: appends its own copy on cmdAck;res=0 alone, so
        the answer decides both lists at once."""
        if not self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        if len(STORE.marks(self.char_id)) >= travel.MARKS_MAX:
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        x, y = travel.mark_cell(*self.current_pos(),
                                dx=int(p.get("dx", 0) or 0),
                                dy=int(p.get("dy", 0) or 0))
        STORE.insert_mark(self.char_id, x, y,
                          str(p.get("title") or ""), str(p.get("info") or ""))
        self.send("cmdAck", res=0)

    def cmd_updMark(self, p):
        """No acknowledgement: GlobalMap.editMark sends and applies at once,
        registering no handler, so an answer would be consumed by whatever
        the player does next."""
        if self.char_id:
            STORE.update_mark(self.char_id, int(p.get("id", -1)),
                              str(p.get("title") or ""),
                              str(p.get("info") or ""))

    def cmd_rmMark(self, p):
        """id is the index into the client's array; it splices on res=0."""
        ok = self.char_id and STORE.remove_mark(self.char_id,
                                                int(p.get("id", -1)))
        self.send("cmdAck", res=0 if ok else RES_NO_SUCH)

    def enter_cell(self):
        """Walk into whatever occupies the cell under the player.

        Every cell leads somewhere, so there is nothing to refuse here: the
        86 named cells lead into their settlement, and the rest into open
        desert, which is its own location id. The player stops travelling and
        the cell is rounded to a whole one, because that is the cell the map
        has been drawing them on and the one they expect to walk into.
        """
        x, y = self.current_pos()
        self.cancel_travel()
        # The cell under a position is its floor on the client
        # (DisplayGlobalMap.as:207): the icon sits at the square's corner.
        self.gx, self.gy = int(math.floor(x)), int(math.floor(y))
        self.on_map = False
        GMAP.leave(self)
        self.go_to(world.location_at(self.gx, self.gy))

    def go_to(self, loc_id):
        """Open a location and put the player at one of its own entry cells."""
        self.loc = world.location(loc_id)
        self.pos = self.loc.entry_cell()
        self.enter_location()

    # --- chat, and travel by name ----------------------------------------
    def say(self, text, group=0):
        """A line from the server, answered into the channel it was asked in.

        Not the event channel, tempting as it is. Chat.userMsg drops a message
        for a channel that is neither open nor switched on -- the event, help,
        world and trade channels each hang off a UserSettings flag -- and
        drops it silently, with no error anywhere. The channel the player just
        typed into is open by definition, and that is where they are looking.
        """
        self.send("userMsg", entry=Str(text), group=group,
                  nick=Str("Сервер"), **{"from": 0})

    def cmd_userMsg(self, p):
        """Chat, and the one way into locations the map cannot reach.

        /goto is ours, not the game's. The client parses nothing: whatever is
        typed goes to the server verbatim as userMsg, so there is no original
        command set to collide with and none was recovered.

        It exists because most of the 1381 location files are interiors.
        Players used to be sent through them from an outzone, but an outzone
        says only that leaving is possible here, never where to: the
        destination lived in the serverdata node, and that is the one node
        stripped from every shipped file. Until that graph is rebuilt by other
        means, this is how the rest of the world is reached.
        """
        raw = p.get("entry") or ""
        text = raw.strip()
        group = int(p.get("group", 0) or 0)
        # A private message carries to=@Nick@ and no group at all
        # (ChatPan.sendMessage): addressed by name, the id never travels.
        if "group" not in p and p.get("to"):
            self.whisper(p["to"], raw)
            return
        self.send("cmdAck", res=0)
        if text.startswith("/goto"):
            self.cmd_goto(text.split()[1:], group)
            return
        if text.startswith("/give"):
            self.cmd_give(text.split()[1:], group)
            return
        if text.startswith("/money"):
            self.cmd_money(text.split()[1:], group)
            return
        if text.startswith("/where"):
            # Everything needed to report a cell that opens the wrong place:
            # the title as drawn, the file behind it, and the cell itself.
            self.say("%s — %s [%s] — клетка %d,%d"
                     % (self.loc.title, self.loc.file, self.loc.fn or "-",
                        round(self.gx), round(self.gy)), group)
            return
        if text.startswith("/home"):
            # The same journey resurrect will make, on demand: the way to
            # check a registered home without dying for it. Not out of a
            # fight, though, or it would be the way round the exit timer
            # chWorld is held to -- and the refusal has to be a line of
            # chat, because this userMsg has already been acknowledged and
            # a second cmdAck would shift the client's queue by one.
            if self.combat.in_combat():
                self.say("Из боя домой не уйти: подождите %d с после боя"
                         % combat.LEAVE_COMBAT_TIMEOUT, group)
                return
            self.go_home()
            return
        # Ordinary talk does NOT come back to the sender: Chat.delivery prints
        # the sender's own line the moment cmdAck;res=0 lands, and an echo
        # would show it twice. Everyone else gets the entry verbatim -- long
        # messages arrive split with ^0^/^1^/^2L^ prefixes and the receiver
        # reassembles them by (group, from) -- with the nick, since a
        # listener who has never seen the sender's entity would otherwise
        # print *** (Chat.getName).
        if group == 0 and self.room is not None:
            self.room.broadcast(("userMsg", dict(
                group=0, nick=Str(self.nick), entry=Str(raw),
                **{"from": self.pid})), exclude=self)
        elif group == 1:
            # The party channel: ChatPan only opens it once a p_m or a
            # join has arrived, so a line here without a party is a
            # modified client's, and goes nowhere.
            if not PARTIES.chat(self, raw):
                log.info("  ..    party chat from %s, who has no party", self.nick)
        elif group == 6:
            # The world channel: everyone online, wherever they stand.
            for other in ONLINE:
                if other is not self:
                    other.send("userMsg", group=6, nick=Str(self.nick),
                               entry=Str(raw), **{"from": self.pid})
        else:
            log.info("  ..    chat on channel %d goes nowhere yet", group)

    def whisper(self, nick, raw):
        """A private message. res=9 is what the client words as "the character
        is offline, write a letter"; on res=0 it prints its own line."""
        target = ONLINE.by_nick(nick)
        if target is None or target is self:
            self.send("cmdAck", res=9)
            return
        self.send("cmdAck", res=0)
        # No group: Chat.userMsg treats a frame with from and no group as the
        # private channel.
        target.send("userMsg", nick=Str(self.nick), entry=Str(raw),
                    **{"from": self.pid})

    def cmd_money(self, args, group=0):
        """/money <афро> [голда] -- credit the purse, for testing.

        Through the Character and nowhere else: the row in characters is
        written back from it on the way out, so money added behind its back
        would vanish at logout. The client is told by userInfo_Player, the
        only frame that carries afro and gold at all.
        """
        if not self.char_id:
            return
        try:
            afro = int(args[0]) if args else 1000
            gold = int(args[1]) if len(args) > 1 else 0
        except ValueError:
            self.say("/money <афро> [голда]   например /money 0 1000", group)
            return
        ch = self.character()
        ch.add_money(afro, gold)
        ch.save(STORE)
        self.push_money()
        # Gold is kept in hundredths of an ounce, the unit the client divides
        # by 100 to show; afro is whole.
        self.say("Теперь: %d афро, %d голды" % (ch.afro, ch.gold // 100), group)
        log.info("  ..    /money %+d afro %+d gold to %s", afro, gold, self.nick)

    def cmd_give(self, args, group=0):
        """/give <тип> [сколько] -- put an item straight into the bag.

        Ours, not the game's, and for testing only: the client parses no
        commands of its own, so this costs nothing to have. Everything a
        purchase does on the server happens here too -- the instance, the
        ss_obj_status that adds it to the bag, and the ss_di_* the client
        asks for next -- because the client adds nothing on its own.
        """
        if not self.char_id:
            return
        try:
            type_id = int(args[0])
            count = int(args[1]) if len(args) > 1 else 1
        except (IndexError, ValueError):
            self.say("/give <номер типа> [сколько]   например /give 6092 200",
                     group)
            return
        if items.params_of(type_id) is None:
            self.say("Предмета %d нет в каталоге" % type_id, group)
            return
        root = items.root_of(type_id)
        if root not in items.HEAPABLE_ROOTS:
            count = 1
        count = max(1, min(count, 999))
        row = self.inv.create(type_id, count)
        self.inv.push_status(row, 1)
        self.inv.push_di(row)
        self.say("Выдано: %s x%d"
                 % (names.text(items.STRING_ID_OFFSET + type_id), count), group)
        log.info("  ..    /give %d x%d to %s", type_id, count, self.nick)

    def cmd_goto(self, args, group=0):
        """/goto <id> | /goto <x> <y> -- open a location, or a map cell."""
        try:
            if len(args) >= 2:
                gx, gy = int(args[0]), int(args[1])
                loc_id = world.location_at(gx, gy)
            elif len(args) == 1:
                loc_id = int(args[0])
                # A wilderness id names its own cell. A settlement has one
                # in the map table, and the player has to be moved onto it,
                # or leaving would drop them wherever they stood before. A
                # true interior has none, and there the old cell is right.
                if world.is_wilderness(loc_id):
                    gx, gy = world.unpack(loc_id)
                else:
                    gx, gy = world.cell_of(loc_id) or (self.gx, self.gy)
            else:
                self.say("/goto <номер локации>  или  /goto <x> <y>", group)
                return
        except ValueError:
            self.say("Не понял. /goto <номер локации> или /goto <x> <y>", group)
            return
        try:
            loc = world.location(loc_id)
        except (KeyError, OSError):
            self.say("Локации %d нет" % loc_id, group)
            return
        self.on_map = False
        self.cancel_travel()
        GMAP.leave(self)
        self.gx, self.gy = gx, gy
        self.go_to(loc.id)
        log.info("  ..    /goto %d -> %s", loc_id, loc.file)

    def cancel_travel(self):
        """Drop any leg in flight, so the position stops extrapolating."""
        if self.arrival:
            self.arrival.cancel()
            self.arrival = None
        self.leg = None

    def cmd_moveTo(self, p):
        if self.on_map:
            self.move_on_map(p)
        else:
            self.move_in_location(p)

    def move_on_map(self, p):
        """dx and dy are hundredths of a cell, measured from where we stand.

        moveAck only sets a velocity; the client extrapolates from its own
        position and never asks again, so arrival has to be timed here and
        confirmed with a userMove carrying zero speed.

        The mountains are the server's to keep: the client walks wherever it
        is pointed and asks nothing, so a leg that runs into rock or water is
        cut here and the player is stopped in front of it.
        """
        if "trg" in p:
            return                      # intercepting a player: not implemented
        # Offsets are measured from where the player is standing right now, and
        # the client has been extrapolating since the last moveAck, so a stale
        # origin here sends them somewhere neither side expects.
        self.gx, self.gy = self.current_pos()
        dx = float(p.get("dx", 0)) / 100.0
        dy = float(p.get("dy", 0)) / 100.0
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.01:
            return
        # Only as far as the ground allows (world.passable, recovered by
        # data/build_terrain.py): the leg ends just inside the last open cell.
        tx, ty = travel.walk(self.gx, self.gy, dx, dy)
        dx, dy = tx - self.gx, ty - self.gy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.01:
            # Nowhere to go. The map has no refusal frame: moveAck carries a
            # velocity and nothing else, so a zero one would stop the figure
            # wherever the client has already drawn it, and cor_pos is a
            # location frame the map never listens for (GlobalMap.as registers
            # userMove, moveAck and marks). userMove for id 0 says both things
            # at once -- GlobalMap.userMove assigns walker.x/y and then
            # startMove(0,0,0) -- which is exactly what an arrival sends, so
            # the same frame confirms standing still.
            self.cancel_travel()
            self.arrive(self.gx, self.gy)
            return
        # A rented vehicle is a plain multiplier on the pace, applied after
        # the ground has had its say: the mountains stop a rider exactly
        # where they stop a walker, only sooner. It has to go into both
        # halves at once -- the velocity the client extrapolates from, and
        # the timer that decides when the trip is over. Move one without the
        # other and the figure is somewhere else than the server thinks when
        # it stops it (world.md 4: the client computes no speed of its own).
        speed = TRAVEL_SPEED * self.travel_speed()
        vx, vy = dx / dist * speed, dy / dist * speed
        self.send("moveAck", vx=vx, vy=vy, t=0)

        loop = asyncio.get_running_loop()
        self.leg = (loop.time(), self.gx, self.gy, vx, vy)
        if self.arrival:
            self.arrival.cancel()
        self.arrival = loop.call_later(dist / speed, self.arrive, tx, ty)
        # Whoever sees us on the map gets the new vector at once, not on the
        # next heartbeat.
        GMAP.moved(self)

    def travel_speed(self):
        """The multiplier on map travel: the vehicle's, or 1 on foot."""
        type_id = self.transport_now()
        return transport.speed_mod(type_id) if type_id is not None else 1.0

    def current_pos(self):
        """Where the player is now, matching the client's own extrapolation."""
        if not self.leg:
            return self.gx, self.gy
        started, sx, sy, vx, vy = self.leg
        dt = asyncio.get_running_loop().time() - started
        return sx + vx * dt, sy + vy * dt

    def arrive(self, tx, ty):
        self.arrival = None
        self.leg = None
        self.gx, self.gy = tx, ty
        # zero speed is how the client is told to stop; it has no other signal
        self.send("userMove", id=0, dx=self.gx, dy=self.gy, vx=0, vy=0, t=0)
        GMAP.moved(self)
        # Deliberately no automatic entry here. Settlements occupy a whole
        # cell, so any short hop near one landed inside it and the map became
        # impossible to stay on. Going in is the button's job.

    def cmd_getInfo(self, p):
        who = int(p.get("id", 0))
        if who != 0:
            if rooms.is_player_id(who):
                self.send_other_player_info(who)
            else:
                self.send_npc_info(who)
            return
        self.send_player_info()
        self.push_vitals()

    # --- the character's numbers ------------------------------------------
    def send_player_info(self):
        """userInfo_Player for id 0, whole every time.

        Level, reputation, premium and money all ride here and only here:
        Gamer.userInfo is the one reader of afro/gold (setMoney is called by
        the mail window alone), so a purchase is followed by this frame
        again rather than by anything smaller.
        """
        pers = self.active or default_character()
        # No tr/tr_hours here until the player actually rents a transport.
        # Gamer.userInfo hands tr straight to TransportFactory.create, which
        # does not treat 0 as "none": it builds a TransObject(0), requests
        # its static info with ts_get_si and the player is riding a vehicle
        # type that does not exist. Leaving the key out leaves transport
        # undefined, which is what the client means by walking.
        #
        # With a rental in hand both go out together: MarksAndPlayersPan
        # draws the panel only when the object AND the hours are there, and
        # tr_hours is the countdown itself -- the client never recomputes it.
        riding = {}
        type_id = self.transport_now()
        if type_id is not None:
            riding = dict(tr=type_id,
                          tr_hours=transport.hours_left(self.transport[1]))
        self.send("userInfo_Player",
                  id=0, name=Str(pers["name"]), sex=pers["sex"],
                  res=Str(str(pers["res"])), ail=0, ally=1, clan=0, hl=0,
                  **self.character().player_info(), **riding)

    def push_money(self):
        self.send_player_info()

    def push_vitals(self):
        """HP and stamina go by usrUp, never by rp_info: Entity.userUpdate
        assigns hmax before hcur, while PersAttributes.rp_info assigns hp
        first and clamps it against the maximum it has not raised yet."""
        self.send("usrUp", id=0, **self.character().vitals())

    def push_stats(self, **groups):
        """Send rp_info unasked, whole or for the indexes named in
        attribs=/skills=/specs=. The client asks for this frame once per
        session and never again, so every change is pushed from here."""
        self.send("rp_info", **self.character().rp_info(**groups))

    def send_other_player_info(self, pid):
        """Answer getInfo;type=0 about another player.

        The asking client just built a Player entity for an id it saw in
        lch;newUser or on the map, and the entity asked by itself
        (Entity.as:38-41). Whoever it is may stand in this room or anywhere
        on the map, so the lookup is by who is online, not by room. The
        health bars over the figure are filled only by usrUp, so it follows
        at once.
        """
        other = ONLINE.by_pid(pid)
        if other is None or other.active is None:
            log.info("  ..    getInfo about %d, who is not online", pid)
            return
        self.send("userInfo_Player", **rooms.player_info(other))
        self.send("usrUp", **rooms.player_health(other))

    def char_for_entity(self, entity_id):
        """Which character an entity id on this client's screen belongs to.

        Asked when the client wants somebody else's clothes and hands
        (ss_get;target=<id>;slot=3) so it can draw them. None for anything
        that is not a player -- the location's own inhabitants included --
        and the answer is then bare hands, which is what the client draws
        for a creature anyway. Another player's gear comes from their own
        character, wherever they stand.
        """
        if not rooms.is_player_id(entity_id):
            return None
        other = ONLINE.by_pid(entity_id)
        return other.char_id if other is not None else None

    def send_npc_info(self, npc_id):
        """Answer getInfo for one inhabitant.

        name is a numeric string id, not text: the client resolves it over HTTP
        against database/texts.xml. Passing the type id lets the stub there hand
        back the creature's internal name instead of a placeholder.

        ally must be truthy or every service this NPC offers is refused before
        a single frame is exchanged.
        """
        entry = self.room.npc(npc_id) if self.room is not None else None
        if not entry:
            return
        cell, type_id, root = entry
        cmd = world.USERINFO.get(root, "userInfo")
        # res is the creature's numeric type id. The client keeps its own copy
        # of mobs.xml and looks the record up by that id, then reads the art
        # folder off it, so neither the folder name nor the creature name works
        # here: both make the lookup miss and the path resolve to
        # mobs/undefined.xml.
        #
        # give_quests is indexed by the client: q_st;q_idx is a position in
        # this list (NPC.getGQIndex), so its order is part of the protocol
        # and quests.given_by keeps the table's. The client answers each
        # type here with a q_status, which is where availability is decided;
        # m_hello is a dead field (NPC.createHelloStrings never assigns).
        params = dict(id=npc_id, name=type_id, sex=0, res=type_id,
                      ail=0,
                      ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=quests.given_by(type_id),
                      take_quests=quests.taken_by(type_id), m_hello=[],
                      can_set_home=0, can_banking=0, can_trophy=0,
                      can_repair=0, can_trade=0)
        if root == world.TRADER:
            # type_list is the price list itself, in order: the client builds a
            # TradeItem per entry and later refers to a purchase by that index,
            # not by the item's own id.
            params.update(can_trade=1, can_repair=1,
                          type_list=items.stock_for(type_id),
                          bg_objects=[], bg_obj_rep_req=[],
                          pmod=1, smod=1, rmod=1)
        elif root == world.UPGRADER:
            params.update(in_types=[], out_types=[], costs=[])
        elif root == world.LESSOR:
            # Lessor.createTransList builds a TransObject per entry and asks
            # for its ts_si; the list is the whole of the rental window.
            params.update(give_transport=transport.offered_by(type_id))
        elif root == world.HEALER:
            # Healer.as builds g_price from the same a_price, so only the
            # afro fee is ever shown; on_conv;op=1 charges this much.
            params.update(a_price=MEDIC_PRICE)
        elif root == world.COMMONER:
            params.update(can_set_home=1)
        # A mob's level paints the coloured frame over its head; its usrUp
        # has to follow the userInfo at once, or the bar is drawn against a
        # maximum of 1200 (combat.md 5).
        params.update(self.combat.mob_info(npc_id))
        self.send(cmd, **params)
        self.combat.after_npc_info(npc_id)

    # --- transport --------------------------------------------------------
    def cmd_ts_get_si(self, p):
        """One vehicle's numbers, asked for every type a lessor offers.

        No cmdAck: TransportFactory.addCall sends this without registering
        one, and an acknowledgement here would be handed to whatever the
        player does next. What it does wait for is the ts_si itself --
        updateCall only reopens the five-deep request window when one
        arrives -- so a type this table has never heard of is still answered,
        with the placeholder frame transport.si_frame builds.
        """
        self.send("ts_si", **transport.si_frame(int(p.get("type", 0) or 0)))

    def cmd_rp_get_info(self, p):
        """Attributes, skills and specialisations, despite the name.

        Each group is a bitmask plus a dense list holding only the slots the
        mask sets. A specialisation with a negative value counts as not yet
        learned. The client sends this once per session (PersAttributes
        firstLoad), so this is the first and last time it asks.
        """
        self.push_stats()

    # --- training with a teacher ------------------------------------------
    def training_open(self, p):
        """ss_create;s_type=4: open the teacher's window.

        Training.proposeTrainingAck opens it on res=0 and shows "Невозможно
        начать обучение у <res>" otherwise. The window then needs nothing
        more from the server: it is built from the rp_info already held and
        from res/xmldocs/spec.xml over HTTP. The client only sends this from
        the teacher's own cell or a neighbouring one (Gamer.proposeContact),
        and the server asks for no less.
        """
        target = int(p.get("target", 0))
        # The room owns the inhabitants now; the record is still (cell, type, root).
        entry = self.room.npc(target) if self.room is not None else None
        if not entry or entry[2] != world.TEACHER:
            self.send("cmdAck", res=progression.ERR_NOT_FOUND)
            return
        if not progression.within_reach(self.pos, entry[0], self.loc.width,
                                        self.loc.height):
            self.send("cmdAck", res=progression.ERR_TOO_FAR)
            return
        self.training = target
        self.send("cmdAck", res=0)

    def training_upd(self, p):
        """ss_upd inside a training session: learn, forget, or close.

        Closing (s_status=0) is sent by Training.close without registering
        an acknowledgement handler, so answering it would hand the reply to
        whatever the client asks next. Learn and forget do register one, and
        its handler is empty: the window redraws from the rp_info that has
        to follow, and the purse from the userInfo_Player after it.
        """
        status = int(p.get("s_status", 0))
        if status == progression.UPD_CLOSE:
            self.training = None
            return
        # obj is a BigUINT: "x" plus the index in hex, no padding.
        try:
            idx = int(str(p.get("obj", "0")), 16)
        except ValueError:
            idx = -1
        char = self.character()
        why = None
        if status == progression.UPD_LEARN:
            afro, gold = char.spec_cost()
            res = char.learn_spec(idx)
            if res == progression.ERR_SKILL:
                why = "Нужен навык не ниже %d" % progression.SPEC_MIN_SKILL[idx]
            elif res == progression.ERR_MONEY:
                why = "Не хватает %s" % ("%d афро" % afro if afro
                                         else "%d голда" % gold)
        elif status == progression.UPD_FORGET:
            res = char.forget_spec(idx)
        else:
            res = progression.ERR_STATE
        self.send("cmdAck", res=res)
        if res != 0:
            # The window shows nothing on a refusal (trainingAck is empty),
            # so the reason goes to the chat the player has open.
            if why:
                self.say(why)
            return
        char.save(STORE)
        attribs = ({progression.SPEC_ATTRIB[idx]}
                   if progression.SPEC_ATTRIB[idx] is not None else set())
        self.push_stats(attribs=attribs, skills=set(), specs={idx})
        self.push_money()

    def cmd_ss_get_si(self, p):
        """Static info for one item type.

        ItemFactory keeps at most five of these in flight and only releases a
        slot when the answer arrives, so an unknown type still has to be
        answered or the queue never drains and the shop stays empty.
        """
        type_id = int(p.get("type", 0))
        info = items.static_info(type_id)
        if not info:
            log.warning("  ??    no such item type %d", type_id)
            return
        command, params = info
        self.send(command, **params)

    def cmd_ss_create(self, p):
        """Open a session with an NPC: trade, bank, training and the rest."""
        if int(p.get("s_type", 0) or 0) == progression.SESSION_TRAINING:
            self.training_open(p)
            return
        if int(p.get("s_type", -1) or 0) == inventory.SESSION_TRADE:
            self.inv.open_trade(p)
            return
        if int(p.get("s_type", -1) or 0) == combat.SESSION_LOOT:
            self.combat.open_loot(p)
            return
        self.npc_session = int(p.get("s_type", 0) or 0)
        self.send("cmdAck", res=0)

    def cmd_ss_upd(self, p):
        """Acknowledge only the ss_upd frames the client waits on.

        s_status=0 closes the session, and every session class sends it
        bare -- Trade, Bank, Upgrade, Training and Loot from close(), Barter
        from close(), TrophyManager from closeSession() -- with no
        XMLCCallStack.addCall. Answering it handed the acknowledgement to
        whatever the player did next, so closing a shop was enough to put
        the queue off by one for the rest of the session.

        Barter has three more that go out bare: 2 deny (denyBarter and the
        awaitingAnswer timeout), 5 apply and 6 break (readyToBarter). The
        same numbers in a trade session are sell, gold repair and trophy
        registration, all of which do register, so the session type has to
        be known. Once barter proposals are relayed, a deny can also come
        from the side that never sent ss_create; the relay will have to set
        npc_session for it.
        """
        # Inside an open stall the code is buy/sell/close, and close carries
        # no acknowledgement at all (Trade.close registers none). A loot
        # bag on the ground is the same shape (Loot.close).
        if self.combat.ss_upd(p):
            return
        if self.inv.ss_upd(p):
            return
        if self.training is not None:
            self.training_upd(p)
            return
        s_status = int(p.get("s_status", 0) or 0)
        if s_status == 0:
            self.npc_session = None
            return
        if self.npc_session == 2 and s_status in (2, 5, 6):
            return
        self.send("cmdAck", res=0)

    def cmd_ss_get_di(self, p):
        # Every real instance the client meets asks for this, through the
        # same window of five as ss_get_si; the sixth item stalls without it.
        # A mob's weapon is an instance too, just not one in the database.
        if self.combat.ss_get_di(p):
            return
        self.inv.ss_get_di(p)

    def cmd_ss_move(self, p):
        self.inv.ss_move(p)

    def cmd_ss_use(self, p):
        self.inv.ss_use(p)

    def cmd_ss_heap_c(self, p):
        self.inv.ss_heap_c(p)

    def cmd_ss_get_s_si(self, p):
        # Nothing belongs to a set yet, but the request still needs answering.
        self.send("ss_si_set", type=int(p.get("type", 0)), res=0, name=0,
                  desc="")

    def cmd_ss_get(self, p):
        # Answered whatever the target: the ss_ack queue is FIFO and the
        # client slices the list by the mask it remembers sending. A mob
        # answers with the weapon it holds, which picks its animation set.
        if self.combat.ss_get(p):
            return
        self.inv.ss_get(p)

    def cmd_resurrect(self, p):
        self.combat.resurrect(p)

    def cmd_e_get_si(self, p):
        # Effects are not modelled yet, but EffectsFactory keeps five of these
        # in flight and only releases a slot on the answer.
        self.combat.e_get_si(p)

    def cmd_e_get_di(self, p):
        self.combat.e_get_di(p)

    def cmd_q_list(self, p):
        """The quest log, asked for once per entry into a location or the map.

        Two parallel lists, instance ids and their types. For each entry the
        client then asks q_si for a type it has not seen and q_di for the
        instance -- one request in flight at a time, so a missing answer
        anywhere wedges the whole quest pipeline.
        """
        rows = STORE.quests(self.char_id) if self.char_id else []
        self.send("q_list", q_id=[r["q_id"] for r in rows],
                  q_types=[r["type"] for r in rows])

    # --- mail ----------------------------------------------------------------
    # The whole cycle is in mail.py. The client asks for the inbox the
    # moment it lands in a location (LocationInterface.checkNewLetter) and
    # every one of the five commands expects an acknowledgement first.
    def cmd_chkml(self, p):
        self.mail.chkml(p)

    def cmd_getml(self, p):
        self.mail.getml(p)

    def cmd_sndml(self, p):
        self.mail.sndml(p)

    def cmd_uldml(self, p):
        self.mail.uldml(p)

    def cmd_rmvml(self, p):
        self.mail.rmvml(p)

    # --- party -----------------------------------------------------------------
    def cmd_p_op(self, p):
        """One command for the whole party protocol (party.py). op 5 asks
        for the roster and is not acknowledged; see expects_ack."""
        PARTIES.op(self, int(p.get("op", -1) or 0), int(p.get("id", 0) or 0))

    # --- quests ------------------------------------------------------------
    # The model is in quests.py and recon/analysis/quests.md 1-2. What matters
    # here: q_status/q_si/q_di are pipelined one at a time and must each be
    # answered with a frame, q_st/q_co/q_ca each expect exactly one cmdAck,
    # and after q_st the server itself has to push the new instance's q_di,
    # or the quest never reaches the journal (the client adds nothing on the
    # ack alone, QuestInspector.getAck).

    def skill_level(self):
        """The player's best skill level, the number quest.level is held to."""
        return self.character().level

    def quest_available(self, quest):
        """Whether this player may take or carry the quest right now.

        "Available" on the client gates both lists: a type with status=0
        drops out of the giver's offers and out of the taker's unfinished
        list alike (QuestInspector.getGQs/getTQs check quest.available), so
        a quest already in the log must stay available until handed in.
        """
        if self.char_id and STORE.has_quest(self.char_id, quest.type):
            return True
        if quest.level > self.skill_level():
            return False
        if not quest.repeatable and self.char_id and \
                STORE.quest_done(self.char_id, quest.type):
            return False
        return True

    def daily_available(self):
        """Hand-ins left today, counted from the last daily reset."""
        if not self.char_id:
            return DAILY_MAX
        now = int(time.time())
        reset = now - now % 86400 + DAILY_RESET_TIME * 60
        if reset > now:
            reset -= 86400
        return max(0, DAILY_MAX - STORE.quests_done_since(self.char_id, reset))

    def npc_type(self, npc_id):
        """type_id of an inhabitant of this location, or None."""
        # The room owns the inhabitants; the record is still (cell, type, root).
        entry = self.room.npc(int(npc_id or 0)) if self.room is not None else None
        return entry[1] if entry else None

    def cmd_q_status(self, p):
        """Availability of one type, asked once per type per NPC visit.

        name is a string id and has to be one the preload carried; q_type is
        the category (marker frame over the NPC). A type not in the table is
        simply unavailable, but the frame is still owed.
        """
        quest_type = int(p.get("q_type", 0))
        quest = quests.get(quest_type)
        if not quest:
            self.send("q_status", type=quest_type, status=0, name=0, q_type=0)
            return
        self.send("q_status", type=quest_type,
                  status=1 if self.quest_available(quest) else 0,
                  name=quest.string_id(quests.NAME), q_type=quest.q_type)

    def cmd_q_si(self, p):
        """Static description of a type, once per session per type."""
        quest = quests.get(int(p.get("q_type", 0)))
        cmd, params = quest.si_frame() if quest else quests.stub_si(p.get("q_type", 0))
        self.send(cmd, **params)

    def cmd_q_di(self, p):
        """Progress of one instance. Only the character's own are known."""
        q_id = int(p.get("q_id", 0))
        row = STORE.quest(q_id)
        quest = quests.get(row["type"]) if row and row["char_id"] == self.char_id else None
        if not quest:
            cmd, params = quests.stub_di(q_id)
        else:
            cmd, params = quest.di_frame(q_id, json.loads(row["progress_json"]),
                                         row["complete"])
        self.send(cmd, **params)

    def cmd_q_st(self, p):
        """Take a quest: q_idx is a position in the NPC's give_quests, not a type.

        On success the ack is followed at once by the instance's q_di_*,
        which is what puts it in the journal. A delivery with no item is
        complete the moment it is taken.
        """
        npc_type = self.npc_type(p.get("mob"))
        offered = quests.given_by(npc_type) if npc_type is not None else []
        idx = int(p.get("q_idx", -1))
        if not self.char_id or not (0 <= idx < len(offered)):
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        quest = quests.get(offered[idx])
        if STORE.has_quest(self.char_id, quest.type):
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        if not self.quest_available(quest):
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        if len(STORE.quests(self.char_id)) >= QUEST_LOG_CAPACITY:
            self.send("cmdAck", res=RES_LOG_FULL)
            return
        progress = quest.fresh_progress()
        complete = quest.is_complete(progress)
        q_id = STORE.take_quest(self.char_id, quest.type, progress, complete)
        log.info("  ..    quest %d (%s) taken as #%d%s", quest.type, quest.name,
                 q_id, ", already complete" if complete else "")
        self.send("cmdAck", res=0)
        cmd, params = quest.di_frame(q_id, progress, complete)
        self.send(cmd, **params)

    def cmd_q_co(self, p):
        """Hand a quest in. Rewards go out before the ack: the client listens
        for them between sending and the ack (QuestInspector.takeQuest), and
        the purse only changes through a fresh userInfo_Player. Afterwards
        the client re-asks q_status for every NPC here, and quest_available
        answers from the history this writes.
        """
        q_id = int(p.get("q_id", 0))
        row = STORE.quest(q_id)
        if not row or row["char_id"] != self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        quest = quests.get(row["type"])
        npc_type = self.npc_type(p.get("mob"))
        if not quest or npc_type not in quest.take:
            self.send("cmdAck", res=RES_WRONG_NPC)
            return
        if not row["complete"]:
            self.send("cmdAck", res=RES_NOT_READY)
            return
        if self.daily_available() <= 0:
            self.send("cmdAck", res=RES_DAILY_LIMIT)
            return
        # Reward items wait for the inventory (TASKS 5.11); the choice is
        # still resolved so the index convention is exercised.
        chosen = quest.reward_item(p.get("obj_idx", 0))
        STORE.finish_quest(q_id, self.char_id, quest.type)
        if quest.rew_afro or quest.rew_gold:
            # Through the Character, never the row: Character.save writes
            # the purse back on logout and would undo a reward paid past it.
            ch = self.character()
            ch.add_money(quest.rew_afro, quest.rew_gold)
            ch.save(STORE)
            self.push_money()
        log.info("  ..    quest #%d (%s) handed in: +%d afro +%d gold, item %s",
                 q_id, quest.name, quest.rew_afro, quest.rew_gold, chosen)
        self.send("cmdAck", res=0)

    def cmd_q_ca(self, p):
        """Drop a quest from the journal; nothing is recorded of it."""
        q_id = int(p.get("q_id", 0))
        row = STORE.quest(q_id)
        if not row or row["char_id"] != self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        STORE.drop_quest(q_id)
        self.send("cmdAck", res=0)

    def cmd_on_conv(self, p):
        """Not a conversation: the NPC services with no session of their own.

        op=0 registers this location as home (Attendance.SET_HOME), op=1 buys
        healing from a medic (Attendance.HEAL), op=2 rents transport
        (Rent.getTransport: p1 type, p2 days). Each expects one cmdAck and
        nothing else from the client's side; the effect is all ours. A
        non-zero answer to op=2 is what the client reports as the rental
        failing.
        """
        op = int(p.get("op", -1))
        npc_type = self.npc_type(p.get("mob"))
        if npc_type is None or not self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        if op == 0:
            # The cell goes with it: an interior does not know which map
            # cell it stands on, and going home has to end on one.
            STORE.set_home(self.char_id, self.loc.id,
                           round(self.gx), round(self.gy))
            log.info("  ..    home set to %d (%s)", self.loc.id, self.loc.title)
            self.send("cmdAck", res=0)
        elif op == 1:
            if MOB_TYPES[npc_type][0] != world.HEALER:
                self.send("cmdAck", res=RES_WRONG_NPC)
                return
            ch = self.character()
            if ch.afro < MEDIC_PRICE:
                self.send("cmdAck", res=RES_NO_MONEY)
                return
            ch.add_money(-MEDIC_PRICE)
            # None is how the Character spells "full" (progression.py).
            ch.hp = None
            ch.sp = None
            ch.save(STORE)
            self.push_money()
            self.push_vitals()
            self.send("cmdAck", res=0)
        elif op == 2:
            self.rent_transport(p)
        else:
            self.send("cmdAck", res=RES_NOT_AVAILABLE)

    def rent_transport(self, p):
        """on_conv;op=2;mob=N;p1=<type>;p2=<days> -- hire a vehicle.

        Rent.getTransportAck reads nothing but res: zero is the rental, any
        other number is the one alert "У вас недостаточно денег". So the
        codes below are for the log, and the frames that follow are what the
        player actually sees -- a userInfo_Player carrying the new purse and
        the new tr/tr_hours, which the client does not ask for and cannot
        derive.

        The reach check is the teacher's (training_open): the client only
        opens a rental desk from its own cell or a neighbouring one
        (Gamer.proposeContact), so the server asks for no less.
        """
        entry = self.room.npc(int(p.get("mob", 0) or 0)) \
            if self.room is not None else None
        if not entry or entry[2] != world.LESSOR:
            log.info("  ..    rent refused: %r is no lessor here", p.get("mob"))
            self.send("cmdAck", res=progression.ERR_NOT_FOUND)
            return
        cell, npc_type, _root = entry
        if not progression.within_reach(self.pos, cell, self.loc.width,
                                        self.loc.height):
            log.info("  ..    rent refused: the desk is out of reach")
            self.send("cmdAck", res=progression.ERR_TOO_FAR)
            return
        try:
            type_id, days = int(p.get("p1", 0)), int(p.get("p2", 0))
        except (TypeError, ValueError):
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        vehicle = transport.get(type_id)
        if vehicle is None or type_id not in transport.offered_by(npc_type):
            log.info("  ..    rent refused: type %d is not on this desk's list",
                     type_id)
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        if not transport.valid_days(days):
            log.info("  ..    rent refused: %d days is outside 1..%d",
                     days, transport.MAX_DAYS)
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        char = self.character()
        # The residence permit gate. TransRentInterface refuses this one
        # before it sends anything, so reaching it means a modified client.
        if vehicle["premium"] > char.premium_level():
            log.info("  ..    rent refused: type %d needs premium %d",
                     type_id, vehicle["premium"])
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        afro, gold = transport.price(type_id, days)
        if not char.can_afford(afro, gold):
            log.info("  ..    rent refused: %d afro / %d gold is more than"
                     " the purse holds", afro, gold)
            self.send("cmdAck", res=RES_NO_MONEY)
            return
        char.add_money(-afro, -gold)
        char.save(STORE)
        # A second rental replaces the first outright: the client asks
        # "поменять транспорт?" and sends this only once the player agrees,
        # and there is nowhere to keep two.
        self.transport = (type_id, transport.until_after(days))
        STORE.save_character_state(self.char_id, transport_type=type_id,
                                   transport_until=self.transport[1])
        log.info("  ..    %s rented type %d for %d day(s), %d afro / %d gold",
                 self.nick, type_id, days, afro, gold)
        # The purse and the vehicle ride the same frame, and it is the only
        # one either travels in. Sent before the acknowledgement, the way a
        # medic's fee is (op=1 above): the ack is the last word on the
        # command, and the client's handler for it only raises an alert.
        self.push_money()
        self.send("cmdAck", res=0)

    def move_in_location(self, p):
        """Echo the path back; the client renders no step until we do.

        Location.movePlayer only records the destination and sends the frame.
        The walk animation starts solely from a server userMove, including for
        the player who asked.
        """
        path = p.get("path")
        # Location.movePlayer registers a cmdAck handler for every single step
        # it asks for. Leaving those unanswered does not stall movement, since
        # that handler is empty, but the queue is strictly ordered: each later
        # reply is then handed to a stale mover instead of the command that
        # earned it, and things like opening a shop quietly stop working.
        #
        # A refusal is not an acknowledgement with a non-zero res, it is a
        # breakMv, and it goes INSTEAD of the cmdAck: Location.breakMv starts
        # with skipCall("cmdAck", moveCmdAck), taking that handler off the
        # queue itself, and then snaps the walker to pos. Sending both would
        # hand the ack to the next command. id=0 is the player's own walker
        # (Location.getWalker treats a falsy id as the gamer).
        if not self.valid_path(path):
            self.send("breakMv", id=0, pos=self.pos)
            return
        self.send("cmdAck", res=0)
        self.pos = int(path[-1])
        cells = [int(c) for c in path]
        # Walking drops the aim (the client cancels its own bar on this
        # userMove) and costs a point a hex while the room is at war.
        self.combat.moved(cells)
        self.send("userMove", id=0, path=cells)
        # The same walk under our real id for everyone else in the room:
        # Location.userMove looks the walker up by id and 0 is always the
        # viewer's own figure (Location.getWalker).
        if self.room is not None:
            self.room.broadcast(("userMove", dict(id=self.pid, path=cells)),
                                exclude=self)

    def valid_path(self, path):
        """The structural check only: a real one is task 1.8.

        Cells must exist in this location's grid. The client's own findPath
        never produces anything else, so whatever fails here came from a
        modified client or a desync, and either way the walker is put back
        where the server has it.
        """
        if not isinstance(path, list) or not path:
            return False
        cells = self.loc.width * self.loc.height
        return all(isinstance(c, int) and 0 <= c < cells for c in path)


async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    log.info("connect %s", peer)
    sess = Session(writer, peer)
    SESSIONS.add(sess)
    fr = FrameReader()
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            # Flash may probe for a policy file on the game port itself.
            if data.startswith(b"<policy-file-request/>"):
                log.info("  policy request")
                writer.write(POLICY)
                await writer.drain()
                continue
            for raw in fr.feed(data):
                try:
                    name, params = decode(raw)
                except Exception:
                    log.exception("  bad frame %r", raw[:200])
                    continue
                sess.handle(name, params)
            await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        # A link that simply breaks lands here too, with no logout before
        # it, and the position is written all the same; close() is what
        # makes that safe after a logout already wrote it.
        log.info("disconnect %s", peer)
        SESSIONS.discard(sess)
        sess.close()


async def handle_policy(reader, writer):
    try:
        await reader.read(64)
        writer.write(POLICY)
        await writer.drain()
    finally:
        writer.close()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    # Content is read before the first socket is open, never inside a
    # handler: a lazy load of the wiki tables once stalled the loop for two
    # seconds on whichever request touched an item first.
    items.preload()
    names.document()
    game = await asyncio.start_server(handle_client, HOST, PORT)
    log.info("game server on %s:%d", HOST, PORT)
    servers = [game]
    try:
        pol = await asyncio.start_server(handle_policy, HOST, POLICY_PORT)
        log.info("policy server on %s:%d", HOST, POLICY_PORT)
        servers.append(pol)
    except PermissionError:
        log.warning("no permission for port %d; policy served inline only",
                    POLICY_PORT)
    # run.sh stop sends SIGTERM and a terminal sends SIGINT. Either one only
    # raises the flag; the leaving is done below, on the loop, so a handler
    # in the middle of a frame finishes it first. Without this the loop just
    # died with every handle_client parked in read(), no finally ran, and
    # whoever was online came back wherever they had logged out the time
    # before.
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)
    await stopping.wait()
    await shutdown(servers)


async def shutdown(servers):
    """Stop listening, warn and save everyone online, then let the loop end.

    Each client is told with a shutdown frame before its position is
    written and its socket closed, and the writers are awaited so that
    frame is actually on the wire before the process is gone.
    """
    log.info("shutting down, %d session(s) online", len(SESSIONS))
    for srv in servers:
        srv.close()
    live = list(SESSIONS)
    for sess in live:
        sess.shutdown()
    await asyncio.gather(*(sess.writer.wait_closed() for sess in live),
                         return_exceptions=True)
    # Every connection has been closed above, so this only waits for their
    # handlers to notice; the timeout is a guard, not an expectation.
    try:
        await asyncio.wait_for(
            asyncio.gather(*(srv.wait_closed() for srv in servers)), 5)
    except asyncio.TimeoutError:
        log.warning("listeners did not close in time; leaving anyway")
    log.info("stopped")


if __name__ == "__main__":
    asyncio.run(main())
