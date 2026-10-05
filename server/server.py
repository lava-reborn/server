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
import random
import re
import signal
import time

import accounts
import auction
import barter
import bosses
import clan_admin
import clans
import combat
import craft
import encounters
import events
import inventory
import items
import keepsakes
import mail
import mobs
import names
import npcs
import party
import rooms
import progression
import quests
import sets
import setcraft
import transport
import travel
import trophies
import upgrader
import world
from protocol import BigUInt, FrameReader, decode, frame, Str

HOST = os.environ.get("LAVA_HOST", "0.0.0.0")
PORT = int(os.environ.get("LAVA_PORT", "9775"))
# Flash's own port for the socket policy. Configurable because a container
# that drops NET_BIND_SERVICE cannot have it at all, and 0 turns the second
# listener off outright: the policy is also answered inline on the game port.
POLICY_PORT = int(os.environ.get("LAVA_POLICY_PORT", "843"))

# /goto, /give and /money in chat. Off unless a test run turns them on: they
# are the admin panel's business now, and on a server other people are on
# they would be a purse and an armoury for anyone who can type.
CHEATS = os.environ.get("LAVA_CHEATS", "").strip().lower() not in (
    "", "0", "no", "off", "false")
# What an admin's gift of a premium thing comes back as, in the chat and in
# the panel's log (Session.admin_give, apply_admin_action): (P) is out of the
# game, for an admin too (the owner's cut of (P), 2026-09-30).
PREMIUM_REFUSED = "предмет %d — (P), выведен из игры, не выдаётся"
# And of a premium vehicle (transport.premium: 8 «Газ 67 Б (P)», 12 «Летающая
# тарелка»), from Session.admin_transport and the panel's offline path.
PREMIUM_TRANSPORT_REFUSED = "транспорт %d — (P), выведен из игры, не выдаётся"
# The lines of chat the server says by itself, signed «Сервер» (Session.say):
# a refusal's reason, what fell on death, how a barter ended, a trophy
# registered, a fight holding a move. The owner took them out of the game's
# chat (2026-09-25); they go to the log instead, and LAVA_SERVER_CHAT=1 brings
# them back. The answer to a command the player typed himself -- /where, a
# /home refused -- is not one of them and always comes (Session.answer).
SERVER_CHAT = os.environ.get("LAVA_SERVER_CHAT", "").strip().lower() not in (
    "", "0", "no", "off", "false")
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
# Three more are in the set but only for some of their values; see
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

    For most commands that is a property of the command. For three it
    depends on a value in the frame, because the same CSM class is sent from
    several places in the client and only some of them call
    XMLCCallStack.addCall:

      bg_op  BattleGroundManager registers for 0 (join queue) and 2 (leave
             queue) only; 3/4 answer an invitation, 5/7 leave a battleground
             and 6 asks for its info, all fire-and-forget.
      p_op   op 5 asks for the party list and is sent from errorReport with
             no handler; every other op (invite, kick, yes/no, leader)
             registers one. Caveat: op 3 is also sent unregistered from the
             auto-decline branch of PartyManager, so a player with that
             setting on will drift by one there; nothing here can tell.
      ss_upd s_status=0 closes a session, and every session class sends it
             bare -- Trade, Bank, Upgrade, Training, Loot and Barter from
             close(), TrophyManager from closeSession(). The handlers keep
             quiet about it already; this is for the paths that answer on
             the handler's behalf, the dead filter first of all: a window
             closed in the same instant the body fell was answered with a
             refusal nobody waited for. Barter's bare 2/5/6 cannot be told
             from a trade's sell and repairs without the session: a live
             barter takes them in cmd_ss_upd, and one the server has just
             closed in Session.handle, before this is ever asked.
    """
    if cmd == "bg_op":
        return int(params.get("op", -1)) in (0, 2)
    if cmd == "p_op":
        return int(params.get("op", -1)) != 5
    if cmd == "ss_upd":
        try:
            return int(params.get("s_status", -1)) != 0
        except (TypeError, ValueError):
            return True
    return cmd in EXPECTS_ACK


# The value three commands' answer turns on (expects_ack), by command.
ACK_DECIDED_BY = {"bg_op": "op", "p_op": "op", "ss_upd": "s_status"}


def bad_frame_expects_ack(raw):
    """expects_ack for a frame protocol.decode could not read as a whole:
    by its name, and for the three commands whose answer turns on a value,
    by that value read on its own (;op=5;), where the rest of the frame is
    past reading. One whose value cannot be read either is not answered:
    whichever way that guessed, a wrong guess shifts the queue by one."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    cmd = text.split(";", 1)[0]
    key = ACK_DECIDED_BY.get(cmd)
    if key is None:
        return expects_ack(cmd, {})
    m = re.search(r";%s=(-?\d+);" % key, text)
    return bool(m) and expects_ack(cmd, {key: int(m.group(1))})


def bad_frame_res(raw):
    """What a frame that could not be read is refused with: RES_NOT_READY,
    but a clan command's own silent 20 (clans.NOT_ALLOWED). 3 is
    ErrorReport's «Сервер не отвечает» over the whole screen, and the clan
    window is the one place that promises never to show it (clans.NEVER)."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    return (clans.NOT_ALLOWED if text.split(";", 1)[0] in clans.COMMANDS
            else RES_NOT_READY)


# Commands after which what is on the body may be different, so the gear's
# bonuses are recounted (Inventory.refresh_gear): ss_move puts things on and
# takes them off, ss_use deletes, ss_upd sells, mends a broken piece or drops
# a thing into a bag on the ground, sndml mails it away and ah_create puts it
# up for auction. The client offers only the bag for the last four, but the
# server takes a thing by its id wherever it is, and a bonus that outlived
# the item it came from would be one a modified client could keep. q_ca and
# q_co take back what a quest handed over from the hands and the body too
# (Inventory.reclaim_pieces). The recount pushes only what moved, so after a
# purchase, a shot or a hand-in of a parcel it sends nothing.
GEAR_COMMANDS = frozenset(("ss_move", "ss_use", "ss_upd", "sndml", "ah_create",
                           "q_ca", "q_co"))

# Commands after which the bag may hold a different number of something a
# bring_l_obj quest asks for, so the log is recounted (Session.count_bag,
# through Inventory.bag_changed): the ones that move a thing the client
# moves by itself, with no ss_obj_status for the server to notice -- ss_upd
# picking a bag on the ground up or putting a thing down into one, ss_move
# between the bag and the body, sndml mailing it away and uldml unpacking a
# letter, ah_create and ah_op at the auction. Everything else that changes
# the bag says so by ss_obj_status or a stack's size, which Inventory.push_status
# and push_di answer the same way. Nothing is sent when no count moved.
BAG_COMMANDS = frozenset(("ss_upd", "ss_move", "sndml", "uldml", "ah_create", "ah_op"))

# Where a new character starts: one of these map cells, drawn by weight at
# newPers (pick_start), (x, y, weight). The valley's tutorial begins twice,
# and each start is one of them (the owner's «видимо там случайный старт
# должен быть» -- «делай», 2026-09-26): 6268x1819 is «Нубийское поселение»
# (181), where Думисани gives the north «Добро пожаловать» (11), 6262x1825
# «Западный поселок» (183), where Джеррах gives the west one (15). Even odds.
# The branches exclude each other (the rows' "excludes", Session.excluded),
# so a character walks the one his start puts him beside -- or the other,
# if he walks there first -- and gets the starter gear once.
#
# Both are peaceful (war="0", so walking costs no action points) and pvp="0".
# The Nubian market is six cells south of the first and six east of the
# second at 6268x1825, and carries the rest of what a newcomer wants -- the
# specialisation trainer, the lessor, a bank and an auctioneer.
#
# The start is the character's home as well until a «Прописка» moves it
# (accounts.create_character), so /home and a resurrection come back here.
START_PLACES = (
    (6268, 1819, 1),
    (6262, 1825, 1),
)

# The start of old: a character with no home and no saved place -- one made
# before the start was drawn -- wakes here, and so does a socket before it
# selects anybody. The first of START_PLACES, which was the only one.
#
# LAVA_GX/LAVA_GY make it the one start of every new character too, which
# is how the suites fix where theirs wake; LAVA_START=181|183 picks one of
# START_PLACES by its location id instead.
GLOBAL_X = int(os.environ.get("LAVA_GX", START_PLACES[0][0]))
GLOBAL_Y = int(os.environ.get("LAVA_GY", START_PLACES[0][1]))

# The location follows from the cell, so the two cannot drift apart. LAVA_LOC
# overrides it for trying a particular file out.
START_LOC = int(os.environ.get("LAVA_LOC", "0")) or world.location_at(
    GLOBAL_X, GLOBAL_Y)


def start_places():
    """(loc_id, gx, gy, weight) of every place a new character may wake in:
    the one LAVA_START names, or the one cell LAVA_GX/LAVA_GY/LAVA_LOC make
    the start, or all of START_PLACES. A knob that names none of them, or a
    table with nothing to draw, does not start the server."""
    forced = os.environ.get("LAVA_START", "").strip()
    places = [(world.location_at(x, y), x, y, w) for x, y, w in START_PLACES]
    if forced:
        picked = [p[:3] + (1,) for p in places if str(p[0]) == forced]
        if not picked:
            raise SystemExit("LAVA_START=%s is none of START_PLACES (%s)"
                             % (forced, ", ".join(str(p[0]) for p in places)))
        return picked[:1]
    if any(os.environ.get(k) for k in ("LAVA_GX", "LAVA_GY", "LAVA_LOC")):
        return [(START_LOC, GLOBAL_X, GLOBAL_Y, 1)]
    if not places or any(w < 0 for *_p, w in places) or not sum(w for *_p, w in places):
        raise SystemExit("START_PLACES has nothing to draw from")
    return places


STARTS = start_places()

# Its own generator, so the draw neither moves nor is moved by combat's and
# the inventory's; LAVA_SEED fixes it the same way, for a replayable run.
START_RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
             else random.Random())


def pick_start():
    """(loc_id, gx, gy): where the character being made now wakes."""
    loc_id, gx, gy, _w = START_RNG.choices(STARTS, weights=[p[3] for p in STARTS])[0]
    return loc_id, gx, gy

# Portrait and body come from two different fields of the same avatars/list.xml
# row and have to be taken together: res selects the portrait, sex selects the
# body, because PersInfo.set sex assigns persType as a side effect. Row 0 is
# the one the creation screen offers first.
AVATARS = world.avatars()
START_AVATAR = int(os.environ.get("LAVA_AVATAR", "0"))

MOB_TYPES = world.mob_types()


def default_character():
    res, sex = AVATARS[START_AVATAR % len(AVATARS)]
    return {"name": "Бродяга", "sex": sex, "res": res}


# The map is a plain grid (world.MAP_X by world.MAP_Y) and the client labels
# its cells from res/database/locations.xml on its own. Every cell can be
# entered: 262 of them hold a settlement recovered into data/settlements.json,
# 2088 on the rim hold a rock scene from data/borders.json, and the rest
# resolve to open desert by world.location_at.
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second

# How often a walk-in passage held shut by a fight asks again, for as long as
# the player stays on its cell (Session.take_passage). Once is not enough:
# the client never sends a path to the cell it already stands on
# (Location.movePlayer), so a player refused there could otherwise only step
# off and back on.
PASSAGE_RETRY = 1.0

# Shared world state, one of each for the process: locations as rooms, the
# map as a room, and who is online. Entity ids come from here too, so a
# trader keeps its id between two players and between two visits.
ROOMS = rooms.Rooms(MOB_TYPES)
GMAP = rooms.GlobalMapRoom(VIEW_RADIUS)
# The wasteland's packs, met while walking the map (encounters.py).
ENCOUNTERS = encounters.Encounters(ROOMS)
ONLINE = rooms.Directory()
# Parties outlive the sockets of their members (party.py), so they are
# kept here and not on the sessions.
PARTIES = party.Parties(ONLINE)
# Clans are in the database (clans.py), and this holds only what each
# client has been told and the invitations still open.
CLANS = clans.Clans(STORE, ONLINE, GMAP)

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
# DAILY_MAX counts repeatable quests only (quests.repeatable_types; the
# owner's decision of 2026-09-26): the one-off quests of a chain -- the
# valley's tutorial alone is a dozen hand-ins -- are never held back by it,
# and the journal's «Сейчас вам доступно N ежедневных квестов» counts what
# its words say. Nor are the services (quests: service) and the ways (data/
# passages.json 'quest'): a cashing, a lottery, a ride is no day's task
# (Session.counts_daily).
#
# The journal: the client refuses a take by itself once it holds
# quest_log_capacity quests of any kind (QuestInterface.getQuest), before the
# server hears of it, so a journal full of errands would bar every way out
# of the Tir, the quarry or the mine. So the client is told QUEST_LOG_EXEMPT_
# ROOM more than the server's own QUEST_LOG_CAPACITY, which counts only the
# ordinary quests: the ways and the services are taken whatever the ordinary
# count, up to the client's own figure (UNDONE 5.x-журнал). The cost: a
# player with QUEST_LOG_CAPACITY ordinary quests who asks for one more is
# refused by the server (RES_LOG_FULL), which the client answers with
# nothing, where it used to put up «У вас слишком много заданий» itself.
# DESIGNED (2026-09-28). The ordinary count is the original's: «Максимальное
# их число 25» (the wiki's «Категория:Квесты»; the plan's correction г of
# 2026-09-28), up from the 20 this server began with. The client takes the
# whole of it: its journal is a list in a scroll pane (QuestInfoInterface.
# buildQuestList lays one row under the other in listPan, a ScrollPan whose
# chekSize raises the scroll bar once they outgrow its 380 pixels), and the
# only figure it holds anything against is the one the constants frame
# carries (GConstatns.getMaxNumberOfQuests, QuestInterface.getQuest).
QUEST_LOG_CAPACITY = 25
QUEST_LOG_EXEMPT_ROOM = 10
CLIENT_QUEST_LOG_CAPACITY = QUEST_LOG_CAPACITY + QUEST_LOG_EXEMPT_ROOM
DAILY_MAX = 10
DAILY_RESET_TIME = 0

# What a quest puts in the bag -- its reward, a parcel at the take -- goes in
# past inventory.MAX_WEIGHT too (the owner's decision of 2026-09-26). A
# refusal cannot be worded: the client answers any non-zero q_co with «Вы
# сдали максимальное количество ежедневных квестов» (QuestInspector.takeAck,
# ErrorReport 44) and a q_st refused with nothing at all, the server's own
# chat is off, and the post knows one sender, the auction. The post's parcels
# go in past the limit already (mail.uldml), the client warns of the load by
# itself (WeightPan), and a player past it buys and picks up nothing more
# until he is lighter. False refuses the take or the hand-in instead
# (RES_OVERLOAD) and nothing moves.
QUEST_ITEMS_PAST_WEIGHT = True

# A medic's fee where data/npcs.json 'healer_price' names none for the
# healer's type (npcs.healer_price): the Nubian valley's. Вади-Хальфа's are
# the original's, 150 afro, 250 in the prison.
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
RES_OVERLOAD = inventory.RES_OVERLOAD
RES_DAILY_LIMIT = 44

# The journal of money (accounts.money_ledger): what a purse written while a
# command runs is booked under, by the command (Session.money_cause); a
# handler that knows better names its own source (STORE.booked_as) -- the
# quest and its type, the thing bought or sold. A command not listed is
# booked as "cmd:<command>", so no change of a purse is ever booked under
# nothing; one no command made (a timer's) is "other".
MONEY_CAUSE = {"q_co": "quest", "q_st": "quest_fee", "q_ca": "quest_refund",
               "c_ga": "c_ga", "on_conv": "npc", "ss_upd": "trade",
               "sndml": "mail", "uldml": "mail", "getml": "mail",
               "ah_create": "auction", "ah_op": "auction", "ah_search": "auction",
               "resurrect": "death", "userMsg": "admin",
               "head": "clan_create", "apply": "clan"}

# The key of a quest instance's progress (char_quests.progress_json) that
# keeps the fee a kill quest paid at the take, [afro, gold]: what a drop
# gives back (Session.cmd_q_ca), whatever the row asks by then. An instance
# without it paid nothing and gets nothing back.
FEE_PAID = "fee_paid"


class Session:
    def __init__(self, writer, peer):
        self.writer = writer
        self.peer = peer
        self.closed = False
        # When this socket arrived, so the panel can show how long somebody
        # has been in the game.
        self.since = int(time.time())
        self.hash = None
        self.logged_in = False
        # Patched clients opt into the HUD counter in hello. Old clients
        # keep their original frame sequence, but still count as players.
        self.online_counter = False
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
        # the player id being run down on the map, and the timer that keeps
        # re-aiming at them: the global map's "перехват".
        self.chase = None
        self.chase_timer = None
        self.chase_until = 0.0
        # s_type of an open NPC session nothing else keeps track of
        # (StuffManager.SESSION_*: 5 upgrade, 6 trophies), or None. Trade,
        # bank, training and loot live in their own objects, and a barter
        # (2) is barter.py's.
        self.npc_session = None
        # the Room this session stands in, from lenter until it leaves
        self.room = None
        # TimerHandle: a walk that ends on a walk-in passage, waiting for the
        # figure to get there (arm_passage), or for a fight to let the player
        # standing on it through (take_passage)
        self.passage = None
        # TimerHandle: a quest way handed in while a fight held the player,
        # asking again until it lets him go (hand_in_way, take_way), and
        # the quest it is: its fee comes back if the wait ends with no move
        self.way = None
        self.way_quest = None
        # q_id -> the complete flag the journal was last told for a quest
        # with a fee (fee_gate), so a change of purse tells it again only
        # where the answer moved (fee_recount).
        self.fee_shown = {}
        # Base skill requirements on carried talks, last shown to this client.
        self.skill_shown = {}
        # Items, slots and the open stall: inventory.py. Reads the character
        # off this session, so it needs no update when the character changes.
        self.inv = inventory.Inventory(self, STORE)
        # Letters: mail.py. Needs the directory to push a new letter to an
        # addressee who is online.
        self.mail = mail.Mail(self, STORE, ONLINE)
        # The auction house: auction.py. Letters it files reach whoever is
        # online through the same directory.
        self.auction = auction.Auction(self, STORE, ONLINE)
        # Action points, the shot in flight, death and the loot window:
        # combat.py. Rooms hold the mobs and the war state.
        self.combat = combat.Fighter(self)
        # Barter with another player: barter.py. The other side is found
        # through the directory, by the player id the client names.
        self.barter = barter.Barter(self, STORE, ONLINE)
        # Registering a trophy and the collection window: trophies.py.
        self.trophies = trophies.Collection(self, STORE)
        # The upgrader's window (s_type=5), weapons and sets: upgrader.py.
        self.upgrader = upgrader.Window(self)
        # What this connection's client has been told about clans (clans.View).
        self.clan_view = clans.View()

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
        commands carry a parameter literally called "name".

        Every q_di_* passes fee_gate on its way out, whoever built it -- the
        kills combat counts (quests.kill_progress), the bag's count, a take,
        the journal's own ask -- so a quest with a fee is complete on the
        client only while the purse covers it. skill_gate also keeps a
        talk incomplete until its base skill goals have been reached."""
        if _cmd[0].startswith("q_di_"):
            params = self.fee_gate(params)
            params = self.skill_gate(params)
        data = frame(_cmd[0], **params)
        log.info("  S->C  %s", data[:-1].decode("utf-8", "replace"))
        self.writer.write(data)

    def handle(self, cmd, params):
        log.info("  C->S  %s %s", cmd, params)
        # A closed session acts on nothing. Its socket can still hold frames
        # that arrived before the close -- the same character logging in on
        # a new socket closes this one from inside another handler -- and
        # each of them would run against this session's Character, a copy
        # the new session no longer shares: a letter with money in it paid
        # from here is saved, then overwritten by the new copy's purse, and
        # the money exists twice.
        if self.closed:
            return
        # What a barter the server has just closed still sends, having sent
        # it before the close arrived: a bare ready or deny that the dead
        # filter below would answer as if it waited for something, or a
        # transfer whose handler the close took off the client's queue.
        if cmd == "ss_upd" and self.barter.stray(params):
            return
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
            # Whatever purse this command writes is booked under what it is
            # (money_cause), unless the handler names a narrower source.
            with STORE.booked_as(*self.money_cause(cmd, params)):
                fn(params)
        except Exception:
            # A bug in one handler must not drop the player's connection.
            log.exception("  !!    handler for %r failed", cmd)
        if cmd in GEAR_COMMANDS:
            # After the handler, whatever it did: its cmdAck is already out,
            # and a handler that failed half-way may still have moved things.
            try:
                self.inv.refresh_gear()
            except Exception:
                log.exception("  !!    recounting the gear after %r failed", cmd)
        if cmd in BAG_COMMANDS:
            self.inv.bag_changed()

    @staticmethod
    def money_cause(cmd, params):
        """(source, ref) a purse this command writes is booked under
        (MONEY_CAUSE). A letter taken out of the mail is the auction's when
        the auction filed it (mail.SYSTEM_SENDER): the payout of a lot, a
        bid given back."""
        source = MONEY_CAUSE.get(cmd, "cmd:" + str(cmd))
        if cmd == "uldml":
            try:
                letter = STORE.mail_letter(mail.letter_id(params.get("id")))
            except Exception:                            # noqa: BLE001
                letter = None
            if letter is not None:
                return ("auction" if letter["from_char"] == mail.SYSTEM_SENDER
                        else source), int(letter["id"])
        return source, 0

    # --- session ---------------------------------------------------------
    def cmd_hello(self, p):
        # The client ignores these params; it only needs a frame named "hello"
        # within 20s, or Session.helloTimeOutFunction drops the connection.
        self.online_counter = p.get("online") == 1
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
                  gold_to_afro_rate=progression.GOLD_TO_AFRO_RATE,
                  quest_log_capacity=CLIENT_QUEST_LOG_CAPACITY,
                  leave_combat_timeout=combat.LEAVE_COMBAT_TIMEOUT,
                  premium_weight_bonus_1=progression.PREMIUM_WEIGHT_BONUS[1],
                  premium_weight_bonus_2=progression.PREMIUM_WEIGHT_BONUS[2],
                  premium_break_bonus_1=1, premium_break_bonus_2=2,
                  premium_xp_bonus_1=progression.PREMIUM_XP_BONUS[1],
                  premium_xp_bonus_2=progression.PREMIUM_XP_BONUS[2],
                  # The repair window's two gold divisors, from the
                  # constants the server charges with (inventory.repair_prices).
                  gold_repair_price_mod=inventory.GOLD_RESTORE_PRICE_MOD,
                  gold_repair_mod=inventory.GOLD_REPAIR_MOD,
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
            # First, while everything it touches is still in place: the
            # other side of a barter is told, and gets its things back.
            self.barter.close()
            self.cancel_travel()
            self.inv.close()
            self.combat.close()         # never raises; see Fighter.close
            # Whoever shared a room or the map with this player is told now:
            # a dropped socket sends no logout, so this is the only place
            # that covers every way out.
            self.leave_room()
            GMAP.leave(self)
            was_online = ONLINE.by_char.get(self.char_id) is self
            ONLINE.remove(self)
            if was_online:
                broadcast_online_count()
            # The party keeps the seat and tells the others "отключился";
            # the same character on a new socket takes it back.
            PARTIES.disconnected(self)
            # The clan's roster holders hear "offline", seen_at is written,
            # an invitation to this character is off. Never raises.
            CLANS.offline(self)
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

    def kick(self, admin="Сервер", seconds=0, reason=""):
        """Put the player out with the game's own words for it.

        Session.kickban (Session.as:199) writes "Администратор <admin> ведет
        работу над вашим аккаунтом", adds how long the account will be
        unavailable when seconds is given, and the reason underneath. It only
        opens the window -- the leaving is the socket closing behind it, and
        close() saves the character on the way, so nothing is lost by it.
        """
        if self.closed:
            return
        self.send("kickban", admin=Str(admin), seconds=int(seconds),
                  reason=Str(reason or ""))
        log.info("  ..    kicked %s by %s: %s", self.nick, admin,
                 reason or "-")
        self.close()

    def leave_room(self):
        # A barter is between two people standing side by side, so it ends
        # with the room, whichever way out this is.
        self.barter.left()
        # The bank window goes with the location it was opened in, and a
        # banker id means nothing in the next one. So does a walk onto a
        # walk-in (arm_passage), and a way handed in that a fight holds
        # (hand_in_way): whatever took the player out of this room first --
        # the map, /goto, a resurrection, a dropped socket -- wins.
        self.inv.bank = None
        # The upgrader of an open upgrade window stays behind too: from
        # elsewhere the window upgrades nothing (upgrader.Window.left).
        self.upgrader.left()
        self.cancel_passage()
        self.cancel_way()
        if self.room is not None:
            self.combat.left()
            self.room.leave(self)
            self.room = None
        ENCOUNTERS.left(self)

    def load_character(self, char_id):
        """Bring the selected character's numbers into memory.

        Everything the client is later told about the character comes from
        this object, and it goes back to the database after each change
        that costs something and once more on the way out.
        """
        self.char = progression.Character.load(STORE, char_id)
        # Anything worn in a slot it does not fit (a row from before the
        # slot_type fix) goes back to the bag before the gear is counted,
        # and so does anything above the character's level (the level rule).
        self.inv.unfit_to_bag()
        self.inv.over_level_to_bag()
        # The gear's bonuses are not saved with the character: they follow
        # from what it has on, counted here once and after every change.
        # Nothing is pushed -- the client asks for rp_info and the bars
        # itself once it stands somewhere.
        self.inv.refresh_gear(push=False)
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

    # --- where the figure stands -------------------------------------------
    # pos is where the player is going: the cell the last walk ends on, the
    # one lenter, a save, a barter or a bag ask about. The figure gets there
    # one hex every mobs.HEX_MS after the echo (LocWalker.startMove), and
    # until then a creature has to meet it where it is -- live_cell, what
    # the fight sees through Fighter.cell. Any other way the player is put
    # on a cell (a door, /goto, a resurrection) is instant, and drops the
    # walk with it.
    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, cell):
        self._pos = cell
        self.walk = None

    def live_cell(self):
        """The last hex the figure has finished stepping onto: the client's
        own walker.numPos, which it moves only at the end of each step
        (LocWalker.finishPathPart) and which the next moveTo starts from."""
        walk = self.walk
        if walk is None:
            return self._pos
        cells, began = walk
        step = int((asyncio.get_running_loop().time() - began) * 1000 // mobs.HEX_MS)
        if step >= len(cells) - 1:
            self.walk = None
            return self._pos
        return cells[max(0, step)]

    def walk_of(self, cells):
        """The walk live_cell is to follow for a moveTo of these cells, or
        None: the player on its last cell at once, as before there was a
        walk to follow. Asked before pos moves.

        Only a path the client's own Location.movePlayer could have sent:
        from the hex its walker stands on (numPos -- the server's live cell,
        or one it passed on the way, since a re-route is sent from where
        the client has got to and the echo it walks by reached it later
        than it left here), one neighbour to the next, no hex twice. Any
        other path is a modified client's -- [start] * 300 + [beside the
        dog], a jump -- and followed, it held the figure, for the fight, on
        a cell the player had left: pos was already at the end for the bags,
        the saves and the doors, while nothing that stood there could take
        him for a minute."""
        if len(cells) < 2 or len(set(cells)) != len(cells):
            return None
        loc = self.loc
        if not all(mobs.adjacent(a, b, loc) for a, b in zip(cells, cells[1:])):
            return None
        here = self.live_cell()
        passed = ()
        if self.walk is not None:
            # Up to the hex the figure is on, not beyond: a turn from a hex
            # still ahead would put it there before it got there.
            walking = self.walk[0]
            passed = walking[:walking.index(here) + 1] if here in walking else ()
        if not (cells[0] in passed or cells[0] == self._pos
                or progression.within_reach(cells[0], here, loc.width, loc.height)):
            return None
        return (cells, asyncio.get_running_loop().time())

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
        # The auction house signs its letters "Аукцион" (mail.SYSTEM_NAME),
        # so that name is taken for good: a player under it would get the
        # replies meant for the house and could pass letters off as its own.
        if STORE.name_taken(name) or mail.is_system_name(name):
            self.send("cmdAck", res=6)          # name already in use
            return
        # Where it wakes (START_PLACES), written as its place and its home in
        # the same row: the intro's actPlayer, a relog before the first
        # save, /home and a resurrection all find it there.
        start = pick_start()
        char_id, slot = STORE.create_character(
            self.account["id"], name, int(p.get("sex", 0)),
            p.get("res", AVATARS[0][0]), home=start)
        self.characters = [dict(r) for r in STORE.characters(self.account["id"])]
        # An id SQLite hands out again carries nothing of the deleted
        # character's: the database's side is create_character's.
        CLANS.forget(char_id)
        self.char_id = char_id
        self.active = next(c for c in self.characters if c["slot"] == slot)
        self.on_map = False
        self.loc = world.location(start[0])
        self.pos = self.loc.entry_cell()
        self.gx, self.gy = start[1], start[2]
        # A pistol and a pack of rounds in the bag, so there is something to
        # wear, load and sell before the first stall is found. Before the
        # load, which counts what the character has on.
        self.inv.starter_kit(char_id)
        STORE.save_character_state(char_id, kit=1)
        self.load_character(char_id)
        log.info("  ..    created %r in slot %d, waking in %s (%d) at %d,%d", name,
                 slot, self.loc.title, self.loc.id, self.gx, self.gy)
        # The client plays its intro after this, then sends actPlayer itself.
        self.send("cmdAck", res=0)

    def cmd_selPers(self, p):
        # Deliberately no cmdAck: PersGenerator does not register a handler for
        # one, so replying here would be consumed by the next command's.
        slot = int(p.get("num", 0))
        for c in self.characters:
            if c["slot"] == slot:
                # The same character on another socket is put away before
                # this one is loaded, not after (ONLINE.add would close it
                # only at enter_location): its close() saves what it holds
                # in memory -- health and stamina live nowhere else until
                # then -- and the load below reads that, instead of a row
                # the older copy overwrites a moment later.
                old = ONLINE.by_char.get(c["id"])
                if old is not None and old is not self:
                    log.info("  ..    %s logged in again, dropping the older socket",
                             c["name"])
                    old.close()
                self.active = c
                self.char_id = c["id"]
                # A character from before the inventory existed has an
                # empty bag and no kit flag: give the same pistol and
                # rounds a newborn gets, once -- before the load, which
                # counts what the character has on.
                if not c.get("kit") and not STORE.items_of(c["id"]):
                    self.inv.starter_kit(c["id"])
                    STORE.save_character_state(c["id"], kit=1)
                    log.info("  ..    starter kit handed to %s", c["name"])
                self.load_character(c["id"])
                self.restore(c)
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
        losing the character. Both that and a row with no place saved at all
        go home (travel.home): the character's own start, or the old one
        for a character made before starts were drawn -- never whatever an
        earlier newPers on this socket left in the session.
        """
        loc_id, pos = c["loc"], c["pos"]
        if loc_id is None:
            loc_id, self.gx, self.gy = travel.home(c, (START_LOC, GLOBAL_X, GLOBAL_Y))
        elif c["gx"] and c["gy"]:
            self.gx, self.gy = c["gx"], c["gy"]
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
                home, self.gx, self.gy = travel.home(c, (START_LOC, GLOBAL_X, GLOBAL_Y))
                try:
                    self.loc = world.location(home)
                except (KeyError, OSError):
                    self.loc = world.location(START_LOC)
                    self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        # A cell saved in one location means nothing in another, and a cell
        # outside the grid would put the player in a wall.
        if pos and 0 <= pos < self.loc.width * self.loc.height:
            self.pos = pos
        else:
            self.pos = self.loc.entry_cell()
        # Left standing on a walk-in -- a socket that dropped on the way
        # through, a logout while a fight held it shut: the login
        # does not take it, and puts the player beside it instead. Taking it
        # would move somebody who has asked for nothing since logging in,
        # with a second lcall straight behind the one this selPers is
        # answered with, and the client's own doors open nothing on a login
        # either: their window comes at the end of a walk and only then
        # (Location.finishMove). Left on it, though, the player could not
        # take it at all: the client sends no walk to the cell it stands on.
        beside = travel.off_walk_in(self.loc, self.pos)
        if beside != self.pos:
            log.info("  ..    left on the walk-in at %d in %s, back beside it"
                     " at %d", self.pos, self.loc.file, beside)
            self.pos = beside

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
        was_online = ONLINE.by_char.get(self.char_id) is self
        ONLINE.add(self)
        if not was_online:
            broadcast_online_count()
        # A party member back on a socket: the others hear "в сети" and
        # this client gets the roster. A no-op on every later lcall.
        PARTIES.online(self)
        # The same for a clan: the client's own fellow, a member's standings,
        # "online" to the roster holders. Also once a session.
        CLANS.online(self)
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork. ws is the
        # room's actual war state, not the file's war flag: the flag only
        # says fighting is possible here, and a client told ws=1 spends
        # action points on every step from the moment it arrives. g_id is
        # the map cell, packed; beyond the map's edge it also says "no way
        # to the map from here" (travel.geo_id), and so does it for an
        # interior left only by its own ways (travel.no_map).
        self.keep_lent()
        # Things that exist in certain places only (data/schedule.json
        # keep_in: the prison's armbands) stay there.
        events.take_back(self)
        self.send("lcall", id=self.loc.id,
                  ws=int(ROOMS.get(self.room_key()).ws),
                  ie=0, g_id=travel.geo_id(self.loc, self.gx, self.gy))

    def keep_lent(self):
        """Take back what a quest lent to be used in certain places only
        (quests.json stay_in: the quarry's pick, a lesson's training gun)
        when the character arrives anywhere else, whichever way -- the way
        out handed in, a death sent home, a login put back elsewhere --
        as a drop takes it (cmd_q_ca, Inventory.reclaim_pieces). The quest
        stays in the journal. Before the lcall, while the client still has
        the bag and the hands it takes the things out of. Rounds or medicine
        lent (quests.lends_consumables) that all come back were not used,
        and the day's loan is struck as a drop strikes it (Store.forget_lent):
        the drop that follows finds nothing left to take back, and would
        otherwise keep a lesson carried out of its range, never fired, closed
        for the day."""
        if not self.char_id or self.loc is None:
            return
        taken = 0
        for row in STORE.quests(self.char_id):
            quest = quests.get(row["type"])
            if quest is None or not quest.stay_in or self.loc.id in quest.stay_in:
                continue
            short = False
            for obj, num in quest.start_obj:
                if obj in quest.lent:
                    back = self.inv.reclaim_pieces(obj, num)
                    taken += back
                    if back < num and items.root_of(obj) in (items.AMMO, items.HEAL):
                        short = True
            # Short -- some used up, or all taken back by an earlier arrival
            # (which struck the loan then if it was whole) -- the loan stands.
            if quests.lends_consumables(quest) and not short:
                STORE.forget_lent(self.char_id, quest.type)
        if taken:
            log.info("  ..    %d lent pieces stay behind: %s is not where they are used",
                     taken, self.loc.file)
            self.inv.refresh_gear()

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
        # APManager.setAP takes both from here and nowhere else. The ceiling
        # is the card's ОД, gear included (Character.ap_ceiling), where
        # rp_info's ap_max goes without it for the card to add. The fight
        # keeps this figure until the next lenter, as the bar does
        # (combat.Fighter.ap_max); entered() below fills the pool to it.
        amax = self.character().ap_ceiling
        self.combat.amax_sent = amax
        self.send("lenter", pos=self.pos, aspd=progression.AP_REGEN, amax=amax)
        # How many quests may still be handed in today. Only QuestInspector
        # reads it, and that singleton exists from the first Entity built
        # (Entity.as:37), long before the location opens, so it lands.
        self.send("q_sys", daily_available=self.daily_available())
        self.enter_room()
        # A member's client asks for its roster now that it stands in a
        # location; one that has stopped listening is told to reload.
        CLANS.entered(self)
        # What the login took off for the level, now that there is a chat
        # to read it in (Inventory.over_level_to_bag); once.
        for line in self.inv.taken_off_lines():
            self.say(line)

    def room_key(self):
        """Which room this location is, for us: see travel.room_key -- or the
        room of the pack that waylaid the player here (encounters.py)."""
        return ENCOUNTERS.room_key(self) or travel.room_key(self.loc, self.gx, self.gy)

    def enter_room(self):
        """Join the location as a room: its inhabitants and other players
        come to us, and we are announced to them. The spawn points and their
        type ids come straight out of the location file; only behaviour was
        stripped. See rooms.Room.snapshot_for for the frame order."""
        self.room = ROOMS.get(self.room_key())
        # Bosses keep the clock, not the room's company: one whose hour came
        # or went while nobody stood here arrives or leaves now, before the
        # snapshot shows the newcomer who is in (combat.RoomCombat.keep_hours).
        self.combat.rc.keep_hours()
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
        # The exit timer still running -- too soon after a hit given or
        # taken: res=39 instead, and nothing moves -- checked before any
        # door, or a fight could be walked out of. Run out, the way is open,
        # whatever is still after the player (combat.Fighter.in_combat).
        if self.combat.refuse_leave():
            return
        if not self.on_map and int(p.get("to", 0) or 0) == 1:
            self.leave_through_exit()
            return
        if not self.on_map and travel.no_map(self.loc.id):
            # An interior left only by its own ways (travel.no_map): the
            # client greys both map buttons out there (travel.geo_id), and
            # the hotkey that does not look is answered no -- a silent
            # return to the location (Master.changeWorldAck).
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
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
        with on_conv;op=0, standing on its map cell -- the start it woke in
        until one is (cmd_newPers), the old start for a character made
        before that with none.

        For the combat side to call from resurrect. Resurrector.resurrectAck
        closes the window and returns the client to LOCAL_STATE on
        cmdAck;res=0, and this lcall is what then moves the body; HP and
        the dead flag are the caller's, this only travels. Works from the
        map too, under the ordinary "Переход в локацию": Master.lcall in
        GLOBAL_STATE is read as an interception ("На Вас напали") only with
        no chWorld since the last lenter, and the one that took the player
        to the map counts (Master.playerIntercepted).
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

    def meet(self, loc_id, pos, gx, gy):
        """Waylaid on the map (encounters.py): the figure stops where it is,
        and the location of the cell opens unasked. The loader still reads
        «Переход в локацию» (Master.playerIntercepted counts the chWorld that
        brought him to the map); the pack, at war with him the moment he is
        in, says the rest (combat.RoomCombat.player_entered)."""
        x, y = self.current_pos()
        self.cancel_travel()
        self.arrive(x, y)
        GMAP.leave(self)
        self.on_map = False
        self.gx, self.gy = gx, gy
        self.loc = world.location(loc_id)
        self.pos = pos
        self.enter_location()

    # --- chat, and travel by name ----------------------------------------
    def say(self, text, group=0):
        """A line the server says by itself: a refusal's reason, what fell
        on death, how a barter ended. Off the chat unless SERVER_CHAT is on;
        either way it is in the log, with who it was for.

        Every module with something to tell the player calls this, so this
        is the one place that decides; an answer to what the player typed
        goes through answer() instead and is never held back.
        """
        if not SERVER_CHAT:
            log.info("  ..    not said to %s: %s", self.nick, text)
            return
        self.answer(text, group)

    def answer(self, text, group=0):
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
        # /goto, /give and /money make money, items and distance out of
        # nothing for whoever types them, which stopped being acceptable the
        # moment anyone else could log in. They are the admin panel's now,
        # and reach the game through admin_actions.
        #
        # They stay here behind a switch that is off everywhere but a test
        # run, because the suites use them to set a scene -- put the player
        # in the dump, give them the item that drops on death, take their
        # money away to check the refusal. Driving all of that through the
        # queue would test the queue instead of what the suite is about.
        # LAVA_CHEATS is set by no script that serves anybody: not run.sh,
        # not the compose file, not the deployment.
        if CHEATS and text.split(" ")[0] in ("/goto", "/give", "/money",
                                             "/skill", "/spec"):
            args = text.split()[1:]
            try:
                if text.startswith("/goto"):
                    if len(args) >= 2:
                        out = self.admin_goto(None, args[0], args[1])
                    else:
                        out = self.admin_goto(args[0] if args else None)
                    # Silent when it worked, the way it always was: the
                    # location frame is the answer, and a line of chat behind
                    # it is one more frame every caller has to expect.
                    if out.startswith(self.nick + ":"):
                        return
                elif text.startswith("/give"):
                    out = self.admin_give(args[0], args[1] if len(args) > 1
                                          else 1)
                elif text.startswith("/skill"):
                    out = self.admin_skill(args[0], args[1])
                elif text.startswith("/spec"):
                    out = self.admin_spec(args[0], args[1])
                else:
                    out = self.admin_money(args[0] if args else 1000,
                                           args[1] if len(args) > 1 else 0)
            except (IndexError, ValueError):
                out = "не понял аргументы"
            self.answer(out, group)
            return
        if text.startswith("/where"):
            # Everything needed to report a cell that opens the wrong place:
            # the title as drawn, the file behind it, and the cell itself.
            self.answer("%s — %s [%s] — клетка %d,%d"
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
                self.answer("Из боя домой не уйти: подождите %d с"
                            % self.exit_seconds(), group)
                return
            # Nor out of a place left only by its own ways (travel.no_map):
            # Берт's course would be lost by it as by the map button.
            if travel.no_map(self.loc.id):
                self.answer("Отсюда домой не уйти: выход отсюда только у здешних"
                            " жителей", group)
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
        if group == 0:
            if self.on_map:
                GMAP.chat(self, raw)
            elif self.room is not None:
                self.room.broadcast(("userMsg", dict(
                    group=0, nick=Str(self.nick), entry=Str(raw),
                    **{"from": self.pid})), exclude=self)
        elif group == 1:
            # The party channel: ChatPan only opens it once a p_m or a
            # join has arrived, so a line here without a party is a
            # modified client's, and goes nowhere.
            if not PARTIES.chat(self, raw):
                log.info("  ..    party chat from %s, who has no party", self.nick)
        elif group in (4, 6):
            # Trade and world: everyone online, wherever they stand. Keep
            # the channel id so Chat.userMsg applies the matching tab/filter.
            for other in ONLINE:
                if other is not self:
                    other.send("userMsg", group=group, nick=Str(self.nick),
                               entry=Str(raw), **{"from": self.pid})
        elif group == 2:
            # The clan's channel, to the members holding its right (clans.py).
            if not CLANS.chat(self, raw):
                log.info("  ..    clan chat from %s, who may not use it", self.nick)
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

    # --- what the admin panel asks for ------------------------------------
    #
    # These were chat commands once, open to whoever typed them, which was
    # fine while the only player was the person running the server. They are
    # driven from the panel now (admin_actions in the database, drained by
    # apply_admin_actions below) and the chat knows nothing about them.
    #
    # Each returns a line for the panel's log. They run against a character
    # that is online, so the change goes through the objects holding it --
    # money added behind Character's back is written over at logout.

    # Skills and specialisations set outright: /skill <0..4> <0..20> and
    # /spec <0..14> <-1..5>, chat cheats only (LAVA_CHEATS), never the
    # panel's. For a test of what a level changes -- the scatter of a shot
    # (combat.spread_factor), the card's crit, the action-point ceiling --
    # without the hours of play that raise it. Skills: 0 ближний бой,
    # 1 стрельба, 2 медицина, 3 промышленность, 4 производство;
    # specialisations as PersAttributes.specMatrix numbers them (2 пистолеты,
    # 3 дробовики, 4 автоматы, 5 винтовки, 6 пулемёты, 7 ПП).
    SKILL_NAMES = ("ближний бой", "стрельба", "медицина", "промышленность",
                   "производство")

    def admin_skill(self, idx, level):
        if not self.char_id:
            return "персонаж не выбран"
        ch = self.character()
        old_level = ch.level
        changed = ch.set_skill(int(idx), int(level))
        ch.save(STORE)
        self.push_stats(**changed)
        if ch.level != old_level:
            # rp_info carries the level too, but the client leaves a zero in
            # it alone (Character.rp_info: if(param) on every scalar), so a
            # skill set back to 0 left the card on the old level;
            # userInfo_Player's setter takes a 0.
            self.send_player_info()
        if progression.moves_vitals(changed):
            self.push_vitals()
        return "%s: %s теперь %d" % (self.nick, self.SKILL_NAMES[int(idx)],
                                     ch.skill[int(idx)][0])

    def admin_spec(self, idx, level):
        if not self.char_id:
            return "персонаж не выбран"
        ch = self.character()
        changed = ch.set_spec(int(idx), int(level))
        ch.save(STORE)
        self.push_stats(**changed)
        # Strength or agility moves a bar's maximum, and only usrUp says so.
        if progression.moves_vitals(changed):
            self.push_vitals()
        lvl = ch.spec[int(idx)][0]
        return "%s: специализация %d %s" % (
            self.nick, int(idx), "забыта" if lvl < 0 else "теперь %d" % lvl)

    def admin_money(self, afro=0, gold=0):
        if not self.char_id:
            return "персонаж не выбран"
        ch = self.character()
        ch.add_money(int(afro), int(gold))
        with STORE.booked_as("admin"):
            ch.save(STORE)
        self.push_money()
        # Gold is kept in hundredths of an ounce, the unit the client divides
        # by 100 to show; afro is whole.
        return "%s: теперь %d афро, %d голды" % (self.nick, ch.afro,
                                                 ch.gold // 100)

    def admin_give(self, type_id, count=1):
        """Put an item straight into the bag.

        Everything a purchase does on the server happens here too -- the
        instance, the ss_obj_status that adds it to the bag, and the ss_di_*
        the client asks for next -- because the client adds nothing itself.

        Never a premium thing (items.premium): (P) is out of the game, and
        this -- with the panel's offline path in apply_admin_action -- was
        the one way left for one to reach a bag (the owner's cut of (P),
        2026-09-30, «можно ли админу выдавать (P)? Нельзя»).
        """
        if not self.char_id:
            return "персонаж не выбран"
        type_id, count = int(type_id), int(count)
        if items.params_of(type_id) is None:
            return "предмета %d нет в каталоге" % type_id
        if items.premium(type_id):
            return PREMIUM_REFUSED % type_id
        if items.root_of(type_id) not in items.HEAPABLE_ROOTS:
            count = 1
        count = max(1, min(count, 999))
        row = self.inv.create(type_id, count)
        self.inv.push_status(row, 1)
        self.inv.push_di(row)
        return "%s: выдано %s x%d" % (
            self.nick, names.text(items.STRING_ID_OFFSET + type_id), count)

    def admin_transport(self, type_id, days=None):
        """Hand a vehicle over, paying nobody and asking no lessor.

        This is the only way to the nine the lessors do not stock, the
        winged manatee among them -- a hundred times walking pace, where
        nothing else in the table passes five. Never the two premium ones
        of those nine (transport.premium: 8 «Газ 67 Б (P)», 12 «Летающая
        тарелка»): (P) is out of the game, for an admin too, as in
        admin_give (the owner's cut of (P), 2026-09-30).
        """
        if not self.char_id:
            return "персонаж не выбран"
        type_id = int(type_id)
        if type_id == 0:
            self.transport = None
            STORE.save_character_state(self.char_id, transport_type=None,
                                       transport_until=None)
            self.send_player_info()
            return "%s: транспорт снят" % self.nick
        vehicle = transport.get(type_id)
        if vehicle is None:
            return "транспорта %d нет в таблице" % type_id
        if transport.premium(type_id):
            return PREMIUM_TRANSPORT_REFUSED % type_id
        # Clamped rather than refused: valid_days answers whether the client
        # could have sent it, and this does not come from the client.
        days = transport.MAX_DAYS if days is None else int(days)
        days = max(1, min(days, transport.MAX_DAYS))
        self.transport = (type_id, transport.until_after(days))
        STORE.save_character_state(self.char_id, transport_type=type_id,
                                   transport_until=self.transport[1])
        # tr and tr_hours ride userInfo_Player and travel in nothing else.
        self.send_player_info()
        return "%s: %s на %d дн., скорость x%s" % (
            self.nick, vehicle["name"], days, vehicle["speed_mod"])

    def admin_goto(self, loc_id=None, gx=None, gy=None):
        """Open a location, or the one standing on a map cell.

        This is how the rest of the world is reached at all: most of the 1381
        location files are interiors, and the graph that led into them lived
        in the serverdata node, which is stripped from every shipped file.
        """
        if not self.char_id:
            return "персонаж не выбран"
        try:
            if loc_id is None:
                gx, gy = int(gx), int(gy)
                loc_id = world.location_at(gx, gy)
            else:
                loc_id = int(loc_id)
                # A wilderness id names its own cell. A settlement has one in
                # the map table, and the player has to be moved onto it, or
                # leaving would drop them wherever they stood before. A true
                # interior has none, and there the old cell is right.
                if world.is_wilderness(loc_id):
                    gx, gy = world.unpack(loc_id)
                else:
                    gx, gy = world.cell_of(loc_id) or (self.gx, self.gy)
        except (TypeError, ValueError):
            return "нужен номер локации или пара координат"
        try:
            loc = world.location(loc_id)
        except (KeyError, OSError):
            return "локации %d нет" % loc_id
        self.on_map = False
        self.cancel_travel()
        GMAP.leave(self)
        self.gx, self.gy = gx, gy
        self.go_to(loc.id)
        return "%s: перенесён в %s [%d]" % (self.nick, loc.title, loc.id)

    # --- running somebody down on the map ---------------------------------
    # How close counts as caught. A cell is a day's walk across the wasteland
    # and the figures are drawn at its centre, so anything under a third of
    # one is the two of them standing together.
    CHASE_CAUGHT = 0.3
    # How often the pursuit re-aims. The quarry is walking too, so a single
    # leg towards where they were is a leg to where they no longer are; this
    # is a chase, not a delivery. Under the map's own 2 s heartbeat, so the
    # figure turns as often as it is redrawn.
    CHASE_BEAT = 1.0
    # Long enough to cross the valley, short enough that a pursuit nobody is
    # watching does not run forever.
    CHASE_LIMIT = 300.0

    def intercept(self, pid):
        """Start running down another player on the map."""
        self.stop_chase()
        other = ONLINE.by_pid(pid) if pid else None
        if other is None or other is self or not other.on_map:
            # Gone into a location, logged out, or never there. The client
            # has no frame for a refused interception (GlobalMap.interceptAck
            # is empty), so there is nothing to say: the figure simply does
            # not set off.
            self.stop_chase()
            return
        self.chase = pid
        self.chase_until = asyncio.get_running_loop().time() + self.CHASE_LIMIT
        self.pursue()

    def pursue(self):
        """One beat of the chase: aim at where the quarry is now."""
        self.chase_timer = None
        pid, self.chase = self.chase, None
        if pid is None or not self.on_map:
            return
        loop = asyncio.get_running_loop()
        other = ONLINE.by_pid(pid)
        if (other is None or not other.on_map
                or loop.time() >= self.chase_until):
            return
        x, y = self.current_pos()
        ox, oy = other.current_pos()
        dx, dy = ox - x, oy - y
        if (dx * dx + dy * dy) ** 0.5 <= self.CHASE_CAUGHT:
            self.caught(other, ox, oy)
            return
        self.chase = pid
        self.step_on_map(dx, dy)
        self.schedule_chase()

    def schedule_chase(self):
        """Re-aim on the beat, but catch at first contact between the beats.

        Both legs are linear until an arrival or a new movement order. Solve
        their relative motion only over that interval; a changed leg calls
        this again. The contact callback keeps the predicted point even if
        the event loop wakes after the two figures have already crossed.
        """
        other = ONLINE.by_pid(self.chase) if self.chase else None
        if other is None or not self.on_map or not other.on_map:
            return
        loop = asyncio.get_running_loop()
        now = loop.time()
        delay = min(self.CHASE_BEAT, max(0.0, self.chase_until - now))
        if self.chase_timer is not None:
            delay = min(delay, max(0.0, self.chase_timer.when() - now))
            self.chase_timer.cancel()
        for walker in (self, other):
            if walker.arrival is not None:
                delay = min(delay, max(0.0, walker.arrival.when() - now))
        x, y = self.current_pos()
        ox, oy = other.current_pos()
        vx, vy = self.leg[3:] if self.leg else (0.0, 0.0)
        ovx, ovy = other.leg[3:] if other.leg else (0.0, 0.0)
        dx, dy, dvx, dvy = ox - x, oy - y, ovx - vx, ovy - vy
        a = dvx * dvx + dvy * dvy
        b = dx * dvx + dy * dvy
        c = dx * dx + dy * dy - self.CHASE_CAUGHT ** 2
        hit = 0.0 if c <= 0 else None
        discriminant = b * b - a * c
        if hit is None and a > 0 and b < 0 and discriminant >= 0:
            hit = c / (-b + math.sqrt(discriminant))
        if hit is not None and hit <= delay:
            state = (self.leg, self.gx, self.gy, other.leg, other.gx, other.gy)
            self.chase_timer = loop.call_later(
                hit, self.chase_contact, other, state, ox + ovx * hit, oy + ovy * hit)
        else:
            self.chase_timer = loop.call_later(delay, self.pursue)

    def chase_contact(self, other, state, x, y):
        """A predicted contact is valid only while both movements still match."""
        self.chase_timer = None
        if (self.chase == other.pid and ONLINE.by_pid(other.pid) is other
                and self.on_map and other.on_map and not self.closed and not other.closed
                and state == (self.leg, self.gx, self.gy, other.leg, other.gx, other.gy)):
            self.caught(other, x, y)
        else:
            self.pursue()

    def update_chasers(self):
        """A changed vector can move contact ahead of a pursuer's next beat."""
        for pursuer in ONLINE:
            if pursuer is not self and pursuer.chase == self.pid:
                pursuer.schedule_chase()

    def caught(self, other, ox, oy):
        """Run down: both of them go into the location under that cell.

        Catching somebody on the open map and then standing next to them is
        not an interception, it is an escort -- the quarry walks on and the
        map has no way to stop them. So the ground itself decides: both are
        put into whatever occupies the cell, facing each other, and getting
        out of it is the ordinary way out of any location.

        The one who was caught has no say in it, which is the point and also
        the danger, so it is kept narrow: it happens on the pursuer's own
        cell, it cannot reach anyone already inside a location, and whether
        the two can then shoot each other is the location's business
        (combat.Fighter.pvp_allowed). Out in the open wasteland they can --
        that is what running somebody down was for ("Основа ПвП": перехват,
        then уход от врага по локациям) -- and in the Nubian valley they
        cannot, which this does not overrule either.
        """
        self.stop_chase()
        self.cancel_travel()
        self.arrive(ox, oy)
        self.say("Вы настигли %s." % other.nick)
        other.say("%s настиг вас." % self.nick)
        # The pursuer goes in first, so the cell is resolved from the
        # position that was just confirmed to both clients.
        self.enter_cell()
        if other.on_map and not other.closed:
            other.cancel_travel()
            other.gx, other.gy = self.gx, self.gy
            other.on_map = False
            GMAP.leave(other)
            other.go_to(self.loc.id)

    def stop_chase(self):
        if self.chase_timer is not None:
            self.chase_timer.cancel()
            self.chase_timer = None
        self.chase = None

    def cancel_travel(self):
        """Drop any leg in flight, so the position stops extrapolating.

        A pursuit is a stream of legs, so it ends here too -- and that covers
        every way it can end without being caught: going into a location,
        logging out, being stopped by the lake, or simply pointing somewhere
        else. One place, rather than a stop_chase beside every one of them.
        """
        self.stop_chase()
        ENCOUNTERS.disarm(self)
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

        The ground is the server's to keep: the client walks wherever it is
        pointed and asks nothing, so a leg that runs into the lake or off the
        edge of the world is cut here and the player stopped in front of it.
        """
        if "trg" in p:
            # The map's context menu, opened by holding shift and clicking
            # somebody (DisplayGlobalMap.playerMcOnPress): "перехват" sends
            # moveTo with the target's id and nothing else, because where
            # they are is the server's business, not the client's.
            self.intercept(int(p.get("trg", 0) or 0))
            return
        # Any ordinary order gives up the pursuit: the player pointed
        # somewhere else, and that is an answer.
        self.stop_chase()
        self.step_on_map(float(p.get("dx", 0)) / 100.0,
                         float(p.get("dy", 0)) / 100.0)

    def step_on_map(self, dx, dy):
        """Lay one leg from where we stand, dx and dy in whole cells."""
        # Offsets are measured from where the player is standing right now, and
        # the client has been extrapolating since the last moveAck, so a stale
        # origin here sends them somewhere neither side expects.
        self.gx, self.gy = self.current_pos()
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.01:
            return
        # Only as far as the ground allows (world.passable: the lake and the
        # rectangle): the leg ends just inside the last open cell.
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
        # A pack of the wasteland may be waiting on a cell of it.
        ENCOUNTERS.arm(self, self.gx, self.gy, tx, ty, speed)
        # Whoever sees us on the map gets the new vector at once, not on the
        # next heartbeat.
        GMAP.moved(self)
        self.update_chasers()

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
        self.update_chasers()
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
        # The one frame that carries the purse: whatever moved it, a quest
        # whose fee it now covers, or no longer covers, is told (fee_recount).
        self.fee_recount()

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
        self.skill_recount()

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
        # The clan under his name: the figure exists now, and a fellow about
        # him before it did would have been lost (ClanInspector.fellow).
        CLANS.tag_for(self, other)

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
                          # One source, not two: the client draws prices
                          # with these and the server charges with the same.
                          pmod=inventory.PMOD, smod=inventory.SMOD,
                          rmod=inventory.RMOD)
            if trophies.is_registrar(type_id):
                # A trophy registrar sells and mends nothing: its only
                # service is "regTrophy" (NPCService.openService) -- but
                # Хассир, a trader first, keeps both (trophies.keeps_stall).
                params.update(can_trophy=1)
                if not trophies.keeps_stall(type_id):
                    params.update(can_trade=0, can_repair=0)
        elif root == world.UPGRADER:
            # What its window turns into what, and for how many hundredths
            # of an ounce (upgrader.lists): the recipes a weapons master
            # gives, gun in and gun out (craft.py), and a set's rungs
            # (setcraft.py); empty lists for an upgrader of another service.
            params.update(upgrader.lists(type_id))
        elif root == world.LESSOR:
            # Lessor.createTransList builds a TransObject per entry and asks
            # for its ts_si; the list is the whole of the rental window.
            params.update(give_transport=transport.offered_by(type_id))
        elif root == world.HEALER:
            # Healer.as builds g_price from the same a_price, so only the
            # afro fee is ever shown; on_conv;op=1 charges this much: the
            # healer's own (npcs.healer_price, the original's 150 in
            # Вади-Хальфа), else MEDIC_PRICE. And «Прописка» beside the
            # healing, as the original's healers had it (NPC.userInfo puts
            # SET_HOME in the same support tab as HEAL).
            params.update(a_price=npcs.healer_price(type_id, MEDIC_PRICE),
                          can_set_home=1 if self.home_here(type_id) else 0)
        elif root == world.COMMONER:
            # A bank opens the storage (Gamer.proposeContact: Commoner plus
            # can_banking) and offers no "Прописка". With can_set_home the
            # client would put the support tab first (NPCService.openService),
            # and leaving the bank tab kills the bank (BankInterface.kill ->
            # Bank.kill clears gamer.bank) until the NPC is clicked again.
            # Other Commoners register homes only when explicitly listed
            # in npcs.json. An inhabitant with no service or quest opens
            # nothing (NPCService.openService has no tab to show).
            if inventory.is_bank(type_id):
                params.update(can_banking=1)
            elif self.home_here(type_id):
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
            bars = (char.hp_max, char.sp_max)
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
        with STORE.booked_as("spec", idx):
            char.save(STORE)
        attribs = ({progression.SPEC_ATTRIB[idx]}
                   if progression.SPEC_ATTRIB[idx] is not None else set())
        self.push_stats(attribs=attribs, skills=set(), specs={idx})
        if status == progression.UPD_FORGET and (char.hp_max, char.sp_max) != bars:
            # Forgetting a strength or agility specialisation takes its levels
            # off the attribute, and four of a bar's maximum with each: only
            # usrUp carries that (progression.moves_vitals).
            self.push_vitals()
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

    def windows_gone(self):
        """Forget every session window the server thinks is open: the stall,
        the bank, the teacher, a bag on the ground, any other NPC's.

        For a new ss_create, whichever it is. Every such window on the client
        is modal (SceneShifter's UIPanels, mode:true), so a player asking for
        a new one has none of the others open, whether or not their close
        ever arrived: a bank opened from 2424's quests tab and shut without
        the bank tab ever being drawn sends none. Left set, the old one would
        take the new session's ss_upd for its own, since cmd_ss_upd asks a
        bag on the ground first, then a stall, then the bank, then a teacher
        -- a teacher's "learn" (2) read as a stall's "sell" or a bank's
        "take", the repair window's afro repair (3) as a bag's "take all"."""
        self.inv.trade = None
        self.inv.bank = None
        self.training = None
        self.combat.loot = None
        self.upgrader.close()
        self.npc_session = None

    def cmd_ss_create(self, p):
        """Open a session with an NPC: trade, bank, training and the rest --
        or, with s_type=2, propose a barter to another player (barter.py)."""
        # Whatever a closed barter still had on its way has arrived.
        self.barter.new_session()
        if int(p.get("s_type", -1) or 0) == barter.SESSION_BARTER:
            self.barter.propose(p)
            return
        if self.barter.refuse_other_session():
            return
        self.windows_gone()
        if int(p.get("s_type", -1) or 0) == inventory.SESSION_BANK:
            self.inv.open_bank(p)
            return
        if int(p.get("s_type", 0) or 0) == progression.SESSION_TRAINING:
            self.training_open(p)
            return
        if int(p.get("s_type", -1) or 0) == inventory.SESSION_TRADE:
            self.inv.open_trade(p)
            return
        if int(p.get("s_type", -1) or 0) == combat.SESSION_LOOT:
            self.combat.open_loot(p)
            return
        if int(p.get("s_type", -1) or 0) == upgrader.SESSION_UPGRADE:
            self.upgrader.open(p)
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
        proposer's awaitingAnswer), 5 apply and 6 break (readyToBarter). The
        same numbers in a trade session are sell, gold repair and trophy
        registration, all of which do register, so the session has to be
        known -- and a deny comes from the side that never sent ss_create.
        Both sides of a barter hold it (barter.Barter.deal), so it is asked
        first; what a barter already closed still sends is handle()'s.
        """
        if self.barter.ss_upd(p):
            return
        # Inside an open stall the code is buy/sell/close, and close carries
        # no acknowledgement at all (Trade.close registers none). A loot
        # bag on the ground is the same shape (Loot.close).
        if self.combat.ss_upd(p):
            return
        if self.inv.ss_upd(p):
            return
        # The bank: put, take, expand, close (inventory.bank_upd).
        if self.inv.bank_upd(p):
            return
        # The trophy collection, s_type=6: the show (1, 3) and delete (4).
        if self.trophies.ss_upd(p):
            return
        # The upgrader's window, s_type=5: close (0, bare) and upgrade (1),
        # of a gun (craft.py) or a piece of a set (setcraft.py).
        if self.upgrader.ss_upd(p):
            return
        if self.training is not None:
            self.training_upd(p)
            return
        s_status = int(p.get("s_status", 0) or 0)
        if s_status == 0:
            self.npc_session = None
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
        """What a clothing set is: exactly one ss_si_set per request.

        SetManager holds five of these in flight and frees a place only when
        an answer arrives, so an unknown type is answered too, with a set that
        says nothing, and so is a request this handler fails on -- handle()
        would send nothing at all after an exception, and one place in the
        window would be gone for the rest of the session. Never a cmdAck: the
        client registers none for this command. The name ids sets.frame puts
        in are the ones names.ALL carries (sets.strings); the empty string of
        the fallback is too. There is no string 0 to fall back on: SetObject
        asks the collector for whatever id arrives, and a missing one costs
        the player the login screen.
        """
        raw = p.get("type", 0)
        try:
            set_type = int(raw)
        except (TypeError, ValueError):
            log.warning("  ??    ss_get_s_si for a type that is no number: %r", raw)
            self.send("ss_si_set", **sets.fallback(raw))
            return
        try:
            params = sets.frame(set_type)
        except Exception:
            log.exception("  !!    ss_get_s_si for %d failed; answering with an empty set", set_type)
            params = sets.fallback(set_type)
        self.send("ss_si_set", **params)

    def cmd_ss_get(self, p):
        # Answered whatever the target: the ss_ack queue is FIFO and the
        # client slices the list by the mask it remembers sending. A mob
        # answers with the weapon it holds, which picks its animation set.
        # The one exception is a barter window's bag request that its close
        # overtook: Barter.kill took the handler for it off that queue.
        if self.barter.swallow_get(p):
            return
        if self.combat.ss_get(p):
            return
        # The trophy collection's own list (slot=16 in an s_type=6 session),
        # and anybody's show (slot=32, the inspect window's too).
        if self.trophies.ss_get(p):
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

    # --- auction ---------------------------------------------------------------
    # auction.py. ah_create and ah_op each get exactly one cmdAck (both are
    # in EXPECTS_ACK); ah_search gets none and exactly one ah_sresult.
    def cmd_ah_search(self, p):
        self.auction.search(p)

    def cmd_ah_create(self, p):
        self.auction.create(p)

    def cmd_ah_op(self, p):
        self.auction.op(p)

    # --- party -----------------------------------------------------------------
    def cmd_p_op(self, p):
        """One command for the whole party protocol (party.py). op 5 asks
        for the roster and is not acknowledged; see expects_ack."""
        PARTIES.op(self, int(p.get("op", -1) or 0), int(p.get("id", 0) or 0))

    def party(self):
        """This player's party, or None: combat asks it whom a stray round
        passes by (Fighter.allied)."""
        return PARTIES.party_of(self)

    # --- clans (clans.py) ----------------------------------------------------
    # Each of the four answers exactly one cmdAck whatever happens inside
    # (clans.Clans.command); the purse a founding or the treasury writes is
    # booked through MONEY_CAUSE and the Store's own sources.
    def cmd_head(self, p):
        CLANS.command(self, "head", p)

    def cmd_admit(self, p):
        CLANS.command(self, "admit", p)

    def cmd_apply(self, p):
        CLANS.command(self, "apply", p)

    def cmd_gg_info(self, p):
        CLANS.command(self, "gg_info", p)

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
        a quest already in the log must stay available until handed in --
        with one exception: a quest past its cap (max_level) is nobody's
        above it, carried or not, or «Назад, в долину» taken at the second
        level would stay a ticket back for good. The taker's window drops
        it then, and the journal can still drop it (q_ca).

        A chain (need_quest, need_any) offers a quest only once what comes
        before it is handed in, and a one-off quest handed in is gone for
        good; a quest of once a day (per_day) handed in today is gone until
        the day's reset. All three are asked of the history,
        char_quests_done. The last needs no word at the hand-in: one
        instance at a time, and none taken on a day it was handed in, is
        never two hand-ins in a day. The other branch of a choice
        (excludes) is gone once one of its quests is in the log or the
        history, unless one of this one's own was handed in first
        (excluded) -- which q_st asks through here, and q_co
        writes: the hand-in that makes the history is what closes it. A
        quest that pays into a specialisation may ask for it learned
        (requires_spec). A kill quest whose fee is paid at the take
        (quests.Quest.fee_at_take) is not offered to a purse short of it,
        and a quest that lends what is used up by its use -- rounds,
        medicine (quests.lends_consumables) -- lends it once a day: the day
        it did, it is not offered again (Store.lent_at), whether it was
        handed in or dropped since -- unless it was dropped with all of it
        back, nothing used (cmd_q_ca strikes the loan, and so does keep_lent
        taking all of it back away from its stay_in): a lesson dropped by
        mistake is the player's to take again at once.
        """
        if quest.over_cap(self.skill_level()):
            return False
        carried = bool(self.char_id) and STORE.has_quest(self.char_id, quest.type)
        # A row a timed window keeps (events.py, data/schedule.json quests):
        # on offer -- and, carried, at its taker's -- only while it is open.
        if not events.quest_open(quest.type, carried):
            return False
        if carried:
            return True
        if quest.level > self.skill_level():
            return False
        # A craftsman's step (setcraft.py) only for the piece in the bag.
        if not setcraft.offered(quest, self.inv.bag_pieces):
            return False
        if not self.char_id:
            return not (quest.need_all or quest.need_any or quest.requires_spec)
        if any(self.character().spec[i][0] < 0 for i in quest.requires_spec):
            return False
        if quest.fee_at_take and not self.fee_ready(quest):
            return False
        if quests.lends_consumables(quest) \
                and (STORE.lent_at(self.char_id, quest.type) or 0) >= self.day_start():
            return False
        if not quest.repeatable and STORE.quest_done(self.char_id, quest.type):
            return False
        if quest.per_day and quest.done_for_today(STORE.quests_done_since(
                self.char_id, self.day_start(), [quest.type])):
            return False
        # A plant's line resting after its cycle (quests: cooldown).
        if quest.cooldown and STORE.quests_done_since(
                self.char_id, int(time.time()) - quest.cooldown, [quest.type]):
            return False
        if self.excluded(quest):
            return False
        return quest.prerequisites_met(lambda t: STORE.quest_done(self.char_id, t))

    def excluded(self, quest):
        """Whether the other branch keeps this quest from this character
        (quests: excludes): one of the types it names is in his log or his
        history. Not when a quest of its own branch (Quest.branch) was the
        first of the two handed in (STORE.first_done): a character that
        walked into both of the valley's tutorials before the rule goes on
        with the one he handed a quest of in first -- its slippers and its
        panama once, not never -- and the other's rest is shut. The history
        only grows, so that first hand-in stays first. Nor while a quest in
        his log asks for what this one pays (Quest.feeds): such a character
        with Зула's «Друзья» in the journal still gets the cow's milk for
        it, whichever branch came first. A character made under the rule
        never has a step of the other branch in his log or his history, so
        for him neither opens anything."""
        cid = self.char_id
        if not quest.excluded_by(lambda t: STORE.has_quest(cid, t)
                                 or STORE.quest_done(cid, t)):
            return False
        if STORE.first_done(cid, quest.branch + quest.excludes) in quest.branch:
            return False
        carried = (quests.get(r["type"]) for r in STORE.quests(cid))
        return not any(q is not None and quest.feeds(q) for q in carried)

    @staticmethod
    def day_start(now=None):
        """The last daily reset (DAILY_RESET_TIME minutes past UTC
        midnight), as a unix time: the day of the daily limit and of the
        once-a-day quests alike."""
        now = int(time.time() if now is None else now)
        reset = now - now % 86400 + DAILY_RESET_TIME * 60
        if reset > now:
            reset -= 86400
        return reset

    def daily_available(self):
        """Repeatable hand-ins left today, counted from the last daily reset
        (DAILY_MAX: a one-off quest does not count, nor a service or a way,
        counts_daily)."""
        if not self.char_id:
            return DAILY_MAX
        return max(0, DAILY_MAX - STORE.quests_done_since(
            self.char_id, self.day_start(),
            [t for t in quests.repeatable_types() if not travel.is_quest_way(t)]))

    @staticmethod
    def counts_daily(quest):
        """Whether a hand-in of this quest is one of the day's (DAILY_MAX):
        a repeatable quest that is neither a service (quests: service) nor
        a way (travel.is_quest_way) -- a ride or a cashing is no day's
        task, and the ways were never counted."""
        return bool(quest.repeatable) and not quest.service \
            and not travel.is_quest_way(quest.type)

    @staticmethod
    def log_exempt(quest):
        """Whether a quest takes no place in the server's count of the
        journal (QUEST_LOG_CAPACITY): a way or a service."""
        return quest is not None and (quest.service or travel.is_quest_way(quest.type))

    def fee_ready(self, quest):
        """Whether the purse covers the quest's fee (cost_afro, cost_gold) --
        and the bag holds what a craft row asks beyond its things (a
        salvage's broken gun, craft.ready), which is told and refused the
        same way."""
        if not quest.has_fee:
            return craft.ready(self, quest)
        return quest.affordable(*self.inv.money()) and craft.ready(self, quest)

    def fee_gate(self, params):
        """A q_di_*'s complete flag, AND the purse covering the quest's fee
        (quests: cost_afro, cost_gold): the client shows the hand-in button
        on complete=1 alone (QuestInterface.openDescription), and any
        non-zero answer to q_co it words as the daily limit
        (QuestInspector.takeAck -> ErrorReport 44), so a fee refused at the
        hand-in could not be explained. Short of it, the journal says not
        complete and the NPC shows the notfinish. What the client was told
        is kept (fee_shown) for fee_recount. The stored complete flag stays
        the task's own: the kills, the bag. A kill quest paid its fee at the
        take (quests.Quest.fee_at_take): its flag is the kills' alone."""
        quest = quests.get(params.get("q_type", 0) or 0)
        if quest is None or not quest.has_fee or quest.fee_at_take or not self.char_id:
            return params
        shown = bool(params.get("complete")) and self.fee_ready(quest)
        self.fee_shown[int(params.get("q_id", 0) or 0)] = shown
        return dict(params, complete=1 if shown else 0)

    def fee_recount(self):
        """The purse changed: every quest with a fee whose journal entry the
        client holds (fee_shown) is told again where the answer moved --
        complete now that the purse covers the fee, or no longer. Not a kill
        quest: it paid its fee at the take (quests.Quest.fee_at_take),
        because a q_di_kill_mobs whose kills did not change makes the client
        print «Убит персонаж для задания ... (undefined из undefined)»
        (LocationInterface.killMob), so a purse that fell short after its
        last kill could not be told, and the hand-in the client still
        offered would be refused as «дневной лимит» (QuestInspector.takeAck
        -> ErrorReport 44)."""
        if not quests.HAS_FEES or not self.fee_shown or self.closed or not self.char_id:
            return
        for row in STORE.quests(self.char_id):
            q_id = row["q_id"]
            quest = quests.get(row["type"])
            if q_id not in self.fee_shown or quest is None or not quest.has_fee \
                    or quest.kind == quests.KILL_MOBS:
                continue
            if (bool(row["complete"]) and self.fee_ready(quest)) != self.fee_shown[q_id]:
                cmd, params = quest.di_frame(q_id, json.loads(row["progress_json"]),
                                             row["complete"])
                self.send(cmd, **params)

    def skills_ready(self, quest):
        """Only trained base levels count, never equipment bonuses or other skills."""
        return all(self.character().skill[i][0] >= level
                   for i, level in quest.complete_skills)

    def skill_gate(self, params):
        """A talk can be taken before its skill goal, but not handed in.

        The stored flag remains the mission's own, as with fee_gate. Track
        skill readiness separately so purse changes cannot cause duplicate
        journal updates. The client shows the unfinished reply on complete=0.
        """
        quest = quests.get(params.get("q_type", 0) or 0)
        if quest is None or not quest.complete_skills or not self.char_id:
            return params
        ready = self.skills_ready(quest)
        self.skill_shown[int(params.get("q_id", 0) or 0)] = ready
        return dict(params, complete=int(bool(params.get("complete")) and ready))

    def skill_recount(self):
        """A skill changed: tell the journal only when its level goal crosses."""
        if not self.skill_shown or self.closed or not self.char_id:
            return
        for row in STORE.quests(self.char_id):
            quest = quests.get(row["type"])
            if row["q_id"] not in self.skill_shown or quest is None \
                    or not quest.complete_skills:
                continue
            if self.skills_ready(quest) != self.skill_shown[row["q_id"]]:
                cmd, params = quest.di_frame(row["q_id"], json.loads(row["progress_json"]),
                                             row["complete"])
                self.send(cmd, **params)

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
        """Progress of one instance. Only the character's own are known.

        A quest the bag decides (Quest.counts_bag: things asked for, a thing
        delivered) answers from the bag as it is: the journal is asked for
        on every entry into a location, so whatever changed the bag out of
        sight of count_bag is set right there.
        """
        q_id = int(p.get("q_id", 0))
        row = STORE.quest(q_id)
        quest = quests.get(row["type"]) if row and row["char_id"] == self.char_id else None
        if not quest:
            cmd, params = quests.stub_di(q_id)
        else:
            progress, complete = json.loads(row["progress_json"]), row["complete"]
            if quest.counts_bag:
                progress, moved = quests.recount(quest, progress, self.inv.bag_pieces())
                if moved:
                    complete = quest.is_complete(progress)
                    STORE.update_quest(q_id, progress, complete)
            cmd, params = quest.di_frame(q_id, progress, complete)
        self.send(cmd, **params)

    def count_bag(self):
        """Every quest in the log the bag decides against the bag as it is
        now, and the journal told of each whose count moved (q_di_*,
        quests.bring_progress): the client counts nothing itself, and shows
        the hand-in only on complete=1. Asked by Inventory.bag_changed once
        a command that changed the bag is done."""
        if self.closed or not self.char_id:
            return
        for cmd, params in quests.bring_progress(STORE, self.char_id,
                                                 self.inv.bag_pieces()):
            self.send(cmd, **params)
        # What a craft row asks of the bag beyond its things moves with it
        # (a salvage's broken gun, fee_ready).
        self.fee_recount()

    def cmd_q_st(self, p):
        """Take a quest: q_idx is a position in the NPC's give_quests, not a type.

        On success the ack is followed at once by the instance's q_di_*,
        which is what puts it in the journal. A delivery with no item is
        complete the moment it is taken unless complete_skills keeps its
        hand-in pending, and a quest that asks for things
        starts from what the bag already holds. What the giver hands over
        (start_obj: a parcel, a bucket) is in the bag before the ack, so a
        delivery of the parcel starts found and complete. A quest that is a
        way somewhere (travel.is_quest_way) is taken the same way and moves
        nobody yet: its hand-in is the way (cmd_q_co, hand_in_way).
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
        # Asked of the whole table, not of this location's rows: a way
        # handed in where the table does not say where it leads could not
        # be handed in at all (cmd_q_co), so given by somebody standing
        # where the table has not caught up with him it is refused here,
        # not left in the journal for good. A fight refuses nothing: taking
        # the quest moves nobody.
        if travel.is_quest_way(quest.type):
            try:
                travel.plan_quest_way(self.loc, quest.type,
                                      round(self.gx), round(self.gy))
            except travel.Refused as why:
                log.info("  ..    quest %d (%s) leads nowhere from %s",
                         quest.type, quest.name, self.loc.file)
                self.send("cmdAck", res=RES_NOT_AVAILABLE)
                self.say(str(why))
                return
        # The journal (QUEST_LOG_CAPACITY): the ordinary quests against the
        # server's own figure, a way or a service against the client's only.
        log_rows = STORE.quests(self.char_id)
        ordinary = sum(1 for r in log_rows if not self.log_exempt(quests.get(r["type"])))
        if len(log_rows) >= CLIENT_QUEST_LOG_CAPACITY or (
                not self.log_exempt(quest) and ordinary >= QUEST_LOG_CAPACITY):
            self.send("cmdAck", res=RES_LOG_FULL)
            return
        if not QUEST_ITEMS_PAST_WEIGHT and self.over_weight(quest.start_obj):
            self.send("cmdAck", res=RES_OVERLOAD)
            return
        # A kill quest's fee is paid here, not at the hand-in (quests.Quest.
        # fee_at_take); short of it -- a purse spent since the window was
        # opened -- the take is refused with nothing taken, which the client
        # shows as nothing at all (QuestInspector.getAck reads a 0 only).
        if quest.fee_at_take:
            if not self.fee_ready(quest):
                self.send("cmdAck", res=RES_NO_MONEY)
                return
            ch = self.character()
            ch.add_money(-quest.cost_afro, -quest.cost_gold)
            with STORE.booked_as("quest_fee", quest.type):
                ch.save(STORE)
            self.push_money()
        # What the giver hands over (start_obj) goes into the bag first --
        # ss_obj_status 1 and its dynamic info, as a purchase comes -- so
        # that a delivery of it starts found: the bag decides (counts_bag).
        for obj, num in quest.start_obj:
            self.inv.give_pieces(obj, num)
        # Rounds or medicine lent: once a day (quest_available).
        if quests.lends_consumables(quest):
            STORE.note_lent(self.char_id, quest.type)
        progress = quest.fresh_progress()
        if quest.counts_bag:
            progress.update(quest.bag_progress(self.inv.bag_pieces()))
        # The fee paid, kept with the instance: a drop gives back what was
        # paid (cmd_q_ca), not what the row asks by then.
        if quest.fee_at_take:
            progress[FEE_PAID] = [quest.cost_afro, quest.cost_gold]
        complete = quest.is_complete(progress)
        q_id = STORE.take_quest(self.char_id, quest.type, progress, complete)
        # Its hand-in kept by a shut window: its takers marked afresh.
        events.taken(quest.type)
        log.info("  ..    quest %d (%s) taken as #%d%s%s", quest.type, quest.name,
                 q_id, ", already complete" if complete else "",
                 ", handed %s" % quest.start_obj if quest.start_obj else "")
        self.send("cmdAck", res=0)
        cmd, params = quest.di_frame(q_id, progress, complete)
        self.send(cmd, **params)

    def over_weight(self, pieces, less=()):
        """Whether (type, pieces) more, and less taken away, would take the
        load past inventory.MAX_WEIGHT: what QUEST_ITEMS_PAST_WEIGHT=False
        refuses."""
        weigh = self.inv.pieces_weight
        return bool(pieces) and self.inv.total_weight() \
            - sum(weigh(t, n) for t, n in less) \
            + sum(weigh(t, n) for t, n in pieces) > inventory.MAX_WEIGHT

    def cmd_q_co(self, p):
        """Hand a quest in. Rewards go out before the ack: the client listens
        for them between sending and the ack (QuestInspector.takeQuest), and
        the purse only changes through a fresh userInfo_Player. Afterwards
        the client re-asks q_status for every NPC here, and quest_available
        answers from the history this writes.

        A quest the bag decides (Quest.counts_bag) is counted against the
        bag here, not taken on the journal's word: what left the bag since
        the last count is not handed in. Short of it, the refusal comes with
        the journal set right (q_di). A fee (cost_afro, cost_gold) is part of
        completeness: short of it the refusal comes with the journal told
        not complete (fee_gate), which the client should have been shown
        already -- the refusal is for a purse that moved in between. Enough,
        and the things go -- each slot's number of pieces, the one thing a
        delivery carries, oldest first (Quest.wants, Inventory.take_pieces)
        -- and with them the rest of what the giver handed over at the take,
        wherever it is kept, as a dropped quest gives it back (Quest.returns,
        Inventory.reclaim_pieces), all before the reward.

        The history is written before the reward is made: a hand-in that
        failed between the two would lose a reward, where the other order
        would leave a quest paid and still in the journal, to be paid again.
        Nothing in the table can make it fail there -- every thing a row
        names is one the game has, or the server does not start
        (quests.check_items).

        The reward, in this order, all before the ack: the thing chosen
        (rew_obj[obj_idx], Quest.reward_item) as num_rew_obj pieces into
        the bag -- ss_obj_status 1 and its dynamic info each, which is what
        the client's «Вы получили: <...>» is made of (Inventory.give_pieces)
        -- and after it what the row gives beside it (rew_also: the rounds
        beside «Стреляем»'s Наган) and the one thing drawn (rew_random),
        announced the same way though the window showed none of it; the
        experience (rew_xp, rew_spec_xp: pay_xp); the money, the fee taken
        off it in the same stroke. A reward index naming none of the rewards
        is a modified client's and is refused before anything moves. Then,
        for a quest the daily limit counts (counts_daily), the day's count,
        which the journal's caption reads (q_sys). A one-off quest, a
        service and a way are not counted and not held back by the limit.

        A quest that is a way (travel.is_quest_way) is handed in the same
        way, all of it -- a lesson of the Tir counts its kills and pays, a
        way writes the history its need_quest children ask for and per_day
        counts -- and only after the ack moves the player (hand_in_way).
        Where the table does not say where it leads from here, it is refused
        before anything else, with the reason in chat, and stays in the
        journal. Which inhabitant it is handed to is asked of the room first,
        as for any quest, so one handed in anywhere but beside its NPC moves
        nobody. A quest past its cap (max_level) is refused first, a way
        too: the taker's window no longer lists it (quest_available).
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
        if quest.over_cap(self.skill_level()) or not events.quest_open(quest.type, True):
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        way = travel.is_quest_way(quest.type)
        if way:
            try:
                travel.plan_quest_way(self.loc, quest.type,
                                      round(self.gx), round(self.gy))
            except travel.Refused as why:
                log.info("  ..    quest #%d (%s) handed in where it leads nowhere, %s",
                         q_id, quest.name, self.loc.file)
                self.send("cmdAck", res=RES_NOT_AVAILABLE)
                self.say(str(why))
                return
        progress = json.loads(row["progress_json"])
        complete = row["complete"]
        if quest.counts_bag:
            progress, moved = quests.recount(quest, progress, self.inv.bag_pieces())
            if moved:
                complete = quest.is_complete(progress)
                STORE.update_quest(q_id, progress, complete)
                cmd, params = quest.di_frame(q_id, progress, complete)
                self.send(cmd, **params)
        if not self.skills_ready(quest):
            cmd, params = quest.di_frame(q_id, progress, complete)
            self.send(cmd, **params)
            self.send("cmdAck", res=RES_NOT_READY)
            return
        if not complete:
            self.send("cmdAck", res=RES_NOT_READY)
            return
        if not quest.fee_at_take and not self.fee_ready(quest):
            cmd, params = quest.di_frame(q_id, progress, complete)
            self.send(cmd, **params)
            self.send("cmdAck", res=RES_NO_MONEY)
            return
        if self.counts_daily(quest) and self.daily_available() <= 0:
            self.send("cmdAck", res=RES_DAILY_LIMIT)
            return
        chosen = quest.reward_item(p.get("obj_idx", 0))
        if quest.rew_obj and chosen is None:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        drawn = quest.draw()
        reward = ([chosen] if chosen else []) + quest.rew_also + ([drawn] if drawn else [])
        if not QUEST_ITEMS_PAST_WEIGHT and self.over_weight(reward, quest.wants()):
            self.send("cmdAck", res=RES_OVERLOAD)
            return
        # A craftsman's step changes the mod, not the wear (setcraft.py), and
        # so does a gun's upgrade or a knife's sharpening, the gun's rounds
        # given back first (craft.py).
        worn = setcraft.wear(quest, self.inv)
        worn_gun = craft.before_take(quest, self.inv)
        for obj, num in quest.wants():
            self.inv.take_pieces(obj, num)
        for obj, num in quest.returns():
            self.inv.reclaim_pieces(obj, num)
        craft.hand_in(self, quest)
        STORE.finish_quest(q_id, self.char_id, quest.type)
        self.fee_shown.pop(q_id, None)
        self.skill_shown.pop(q_id, None)
        for obj, num in reward:
            given = self.inv.give_pieces(obj, num)
            setcraft.keep_wear(worn, given, self.inv)
            craft.keep_wear(worn_gun, given, self.inv)
        # Now and then a piece of a collection besides, for a collector
        # (keepsakes.py).
        for obj, num in keepsakes.find(quest, quests.wanted_things(
                STORE, self.char_id, self.inv.bag_pieces())):
            self.inv.give_pieces(obj, num)
        if quest.rew_xp or quest.rew_spec_xp:
            self.pay_xp(quest.rew_xp, quest.rew_spec_xp)
        # A kill quest paid its fee at the take (quests.Quest.fee_at_take).
        paid = 0 if quest.fee_at_take else 1
        afro = quest.rew_afro - paid * quest.cost_afro
        gold = quest.rew_gold - paid * quest.cost_gold
        if afro or gold or quest.has_fee:
            # Through the Character, never the row: Character.save writes
            # the purse back on logout and would undo a reward paid past it.
            ch = self.character()
            ch.add_money(afro, gold)
            with STORE.booked_as("quest", quest.type):
                ch.save(STORE)
            self.push_money()
        if self.counts_daily(quest):
            self.send("q_sys", daily_available=self.daily_available())
        log.info("  ..    quest #%d (%s) handed in: %+d afro %+d gold, item %s%s%s, xp %s%s",
                 q_id, quest.name, afro, gold, chosen,
                 " and %s" % quest.rew_also if quest.rew_also else "",
                 ", drawn %s" % (drawn,) if drawn else "",
                 quest.rew_xp or "-",
                 ", spec xp %s" % quest.rew_spec_xp if quest.rew_spec_xp else "")
        self.send("cmdAck", res=0)
        if way:
            self.hand_in_way(q_id, quest)

    def pay_xp(self, rewards, spec_rewards=()):
        """Experience a quest pays (rew_xp: (skill, points)), all of it into
        the skill -- rew_xp trains no specialisation -- with the premium
        share on top, as any action pays (Character.gain_xp); and into a
        specialisation alone (rew_spec_xp: (spec, points),
        Character.gain_spec_xp), where it is learned. The card and the
        client's own «Медицина: +20 опыта» follow from the rp_info pushed
        for the indexes that moved (SpecSkillMessages); a level gained moves
        constitution and the bars, which go by usrUp, and so does a level of
        a strength or agility specialisation (progression.moves_vitals)."""
        ch = self.character()
        changed = {"skills": set(), "specs": set(), "attribs": set()}
        for skill, xp in rewards:
            for group, idxs in ch.gain_xp(skill, xp).items():
                changed[group] |= idxs
        for spec, xp in spec_rewards:
            for group, idxs in ch.gain_spec_xp(spec, xp).items():
                changed[group] |= idxs
        ch.save(STORE)
        if any(changed.values()):
            self.push_stats(**changed)
        if progression.moves_vitals(changed):
            self.push_vitals()

    def hand_in_way(self, q_id, quest):
        """The move that follows the hand-in of a quest that is a way
        (travel.quest_ways) -- Рудо's "Отправка в шахту" down into the Nubian
        mine, Камал's "Выведи меня отсюда" back up, Демир's rides -- once
        cmd_q_co has handed it in like any other quest and acked it.

        Taking it was a take like any other: the ack and its q_di, which is
        what puts it in the journal (QuestInspector.createQuestTask) and, the
        giver taking it back, into his window's "Завершенные задания" with
        the finish text and the hand-in button (QuestInspector.getTQs,
        QuestInterface.openDescription). rew_loc=1 in its q_si is the
        client's own word for what follows: "после выполнения задания Вас
        переместят в другое место", in the NPC's window and in the journal
        alike (QuestInfoInterface).

        The hand-in is cmd_q_co's, all of it: complete or refused, what it
        asks for taken and what was handed over taken back, the fee, the
        reward, and the history (char_quests_done), so a way can be a lesson
        that counts its kills and pays, a need_quest of the next, a per_day
        row. None of it counts against the day (counts_daily) or takes a
        place in the server's count of the journal (log_exempt), and a
        repeatable way is offered again at once, as before. On the ack the
        client takes the quest out of the journal, says "Задание <...>
        завершено" and starts re-asking q_status of the room's inhabitants
        (QuestInspector.takeAck, requestAllNPC) -- each answered, wherever
        the player is by then. The move follows it: an lcall with no ack of
        its own, as /goto and the walk-ins make, which takes the window down
        with the location (SceneShifter.locationScene), to where
        travel.door_arrival puts a player coming that way.

        A fight holds the move (fight_hold), or the quest would be the way
        out of every fight in the mine -- and it has to be held, not
        refused: any non-zero answer to q_co the client words as the daily
        limit (QuestInspector.takeAck -> ErrorReport 44), and on a zero one
        it takes the quest out of its journal. So the hand-in is accepted
        and the move waits, asked again every PASSAGE_RETRY for as long as
        the player stays in the room (take_way), with the reason in chat
        once. Leaving the room ends the wait, and so do death and a dropped
        socket (leave_room, follow_way); a second hand-in replaces the first
        wait, so one lcall at most. A second q_co of the same instance finds
        no row. A wait that ends with nobody moved gives the fee back
        (refund_way): paid for a ride, it is not kept for none -- unless the
        hand-in paid a reward too. The rest of the hand-in stands -- the
        history, a reward -- as before.
        """
        log.info("  ..    quest #%d (%s) handed in: the way", q_id, quest.name)
        self.cancel_way()
        self.follow_way(quest, self.room)

    def cancel_way(self):
        """End the wait of a held way: the room left, the socket gone, a
        second way handed in. Nobody moved, so its fee comes back."""
        if self.way is not None:
            self.way.cancel()
            self.way = None
            quest, self.way_quest = self.way_quest, None
            self.refund_way(quest)

    def refund_way(self, quest):
        """The fee of a way whose move never came (cancel_way, follow_way):
        given back when the hand-in paid nothing else. One that also paid a
        reward keeps its fee with the reward: the hand-in stands, and giving
        the fee back too would pay the reward for nothing, as often as the
        move could be made to fail (a fight, a step out of the room)."""
        if quest is not None and not quest.pays:
            self.refund_fee(quest)

    def refund_fee(self, quest, afro=None, gold=None):
        """A fee paid for nothing, given back into the purse: a kill quest
        dropped after it paid at the take (quests.Quest.fee_at_take; the
        afro and gold its instance paid, FEE_PAID), or a way handed in whose
        move never came (refund_way; the row's fee, paid a moment ago).
        Through the Character, as every purse, booked as quest_refund;
        pushed to a client that is still there."""
        if quest is None or self.char is None:
            return
        afro = quest.cost_afro if afro is None else int(afro)
        gold = quest.cost_gold if gold is None else int(gold)
        if not (afro or gold):
            return
        ch = self.character()
        ch.add_money(afro, gold)
        with STORE.booked_as("quest_refund", quest.type):
            ch.save(STORE)
        log.info("  ..    quest %d (%s): its fee of %d afro %d gold given back",
                 quest.type, quest.name, afro, gold)
        if not self.closed:
            self.push_money()

    def take_way(self, quest, room, said):
        """The timer of a held way: asked again (follow_way)."""
        self.way = None
        # A timer, not a command: nothing in handle() is around this to
        # keep a bug from taking the player's session with it.
        try:
            self.follow_way(quest, room, said)
        except Exception:
            log.exception("  !!    quest way %d from %s failed", quest.type,
                          self.loc.file)

    def follow_way(self, quest, room, said=frozenset()):
        """Move the player along a way handed in (hand_in_way), or wait for
        the fight that holds him and ask again.

        Asked again rather than trusted, since a second may have passed: the
        player must be in the room he handed it in in, and alive. Where he
        stands in it does not matter -- he may well have to walk to get out
        of reach of what keeps hitting him. said holds the reasons already
        told, so the wait is one line of chat per reason, not one a second.
        Whatever ends it with nobody moved -- gone from the room, dead, the
        socket closed, the way refused -- gives the fee back (refund_way).
        """
        self.way = None
        self.way_quest = None
        if (self.closed or self.on_map or self.room is not room
                or self.combat.dead):
            self.refund_way(quest)
            return
        hold = self.hold_line("отправитесь")
        if hold is not None:
            reason, line = hold
            if reason not in said:
                log.info("  ..    quest way %d (%s) held: %s", quest.type,
                         quest.name, reason)
                if line:
                    self.say(line)
                said = said | {reason}
            self.way = asyncio.get_running_loop().call_later(
                PASSAGE_RETRY, self.take_way, quest, room, said)
            self.way_quest = quest
            return
        try:
            dest = travel.plan_quest_way(self.loc, quest.type,
                                         round(self.gx), round(self.gy))
        except travel.Refused as why:
            self.say(str(why))
            self.refund_way(quest)
            return
        self.cancel_travel()
        self.gx, self.gy = dest.gx, dest.gy
        self.loc = world.location(dest.loc_id)
        self.pos = dest.pos
        log.info("  ..    quest %d (%s) -> %s (%s) at %d, cell %d,%d",
                 quest.type, quest.name, self.loc.title, self.loc.file,
                 self.pos, self.gx, self.gy)
        self.enter_location()

    def cmd_q_ca(self, p):
        """Drop a quest from the journal; nothing is recorded of it.

        What its giver handed over at the take (start_obj) goes back with
        it, as much of it as the character still has: the bag first, then
        the hands and the body, then the bank (Inventory.reclaim_pieces): a
        parcel is not a thing to keep by giving up the errand, nor one to
        hoard by taking the quest again and again. What left the bag, a
        hand or the body goes before the ack (ss_obj_status 0, or a stack's
        new size), like a hand-in's; the gear it took away is recounted
        after it (GEAR_COMMANDS). A kill quest that paid its fee at the take
        (quests.Quest.fee_at_take) gets back what it paid, as the instance
        keeps it (FEE_PAID), the purse before the ack. Rounds or medicine
        lent (quests.lends_consumables) that all come back were not used:
        the day's loan is struck (Store.forget_lent) and the quest is
        offered again at once; one used up keeps it for the day."""
        q_id = int(p.get("q_id", 0))
        row = STORE.quest(q_id)
        if not row or row["char_id"] != self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        quest = quests.get(row["type"])
        STORE.drop_quest(q_id)
        self.fee_shown.pop(q_id, None)
        self.skill_shown.pop(q_id, None)
        short = False
        for obj, num in (quest.start_obj if quest else ()):
            back = self.inv.reclaim_pieces(obj, num)
            if back < num and obj in quest.lent \
                    and items.root_of(obj) in (items.AMMO, items.HEAL):
                short = True
        if quest is not None and quests.lends_consumables(quest) and not short:
            STORE.forget_lent(self.char_id, quest.type)
        paid = json.loads(row["progress_json"] or "{}").get(FEE_PAID)
        if quest is not None and paid:
            self.refund_fee(quest, *paid)
        self.send("cmdAck", res=0)

    @staticmethod
    def offers_home(type_id):
        """Whether an inhabitant of this type registers a home («Прописка»,
        on_conv;op=0): a healer or an explicitly listed Commoner, never a
        bank. The same rule governs the advertised service and the command,
        including NPCs built as Traders for their trophies."""
        root = MOB_TYPES.get(type_id, (None,))[0]
        return not inventory.is_bank(type_id) and world.offers_home(type_id, root)

    def home_here(self, type_id):
        """offers_home, where a home can be: not in a place left only by its
        own ways (travel.no_map) -- the prison's blocks, the range's rooms,
        the quarry -- or /home and a death would lead in past its one way
        in, at any hour: into the prison with its gates shut."""
        return self.offers_home(type_id) and not (
            self.loc is not None and travel.no_map(self.loc.id))

    def cmd_c_ga(self, p):
        """c_ga;gold=<hundredths>: gold into afro at the one rate
        (progression.GOLD_TO_AFRO_RATE). Not a bank's service: the window is
        opened from a button on the global map's top frame
        (GlobalMapInterface -> GoldToAfroInterface, BankAccount.
        convertGoldToAfro), anywhere, with no NPC. It prints «G 1 = A
        <rate>» off the constants frame and sends the ounces typed times
        100, hundredths, the unit the purse is kept in (rounded here: the
        client multiplies a decimal by 100 in floating point). Exactly one
        cmdAck, which the window reads as done or «Не удалось произвести
        операцию» (GoldToAfroInterface.converted), then the purse by
        userInfo_Player. The afro is floored: a hundredth of an ounce is
        rate/100 afro. A figure no purse can hold -- 1e400 is inf to
        float(), and int(round(inf)) is an OverflowError, nan a ValueError
        -- is no figure: refused like a zero, with its one ack (only a
        modified client sends one: the window clamps to the purse)."""
        try:
            gold = int(round(float(p.get("gold", 0) or 0)))
        except (TypeError, ValueError, OverflowError):
            gold = 0
        if not self.char_id or gold <= 0:
            self.send("cmdAck", res=RES_NOT_AVAILABLE)
            return
        ch = self.character()
        if ch.gold < gold:
            self.send("cmdAck", res=RES_NO_MONEY)
            return
        afro = gold * progression.GOLD_TO_AFRO_RATE // progression.GOLD_OUNCE
        ch.add_money(afro, -gold)
        with STORE.booked_as("c_ga"):
            ch.save(STORE)
        log.info("  ..    %d hundredths of gold into %d afro", gold, afro)
        self.send("cmdAck", res=0)
        self.push_money()

    def cmd_on_conv(self, p):
        """Not a conversation: the NPC services with no session of their own.

        op=0 registers this location as home (Attendance.SET_HOME), op=1 buys
        healing from a medic (Attendance.HEAL), op=2 rents transport
        (Rent.getTransport: p1 type, p2 days). Each expects one cmdAck and
        nothing else from the client's side; the effect is all ours. A
        non-zero answer to op=2 is what the client reports as the rental
        failing. op=0 only at a healer or an explicitly listed Commoner
        (offers_home), and not where the map is out of reach (home_here);
        op=1 costs the healer's own fee (npcs.healer_price,
        MEDIC_PRICE where the file names none).
        """
        op = int(p.get("op", -1))
        npc_type = self.npc_type(p.get("mob"))
        if npc_type is None or not self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        if op == 0:
            if not self.home_here(npc_type):
                self.send("cmdAck", res=RES_WRONG_NPC)
                return
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
            price = npcs.healer_price(npc_type, MEDIC_PRICE)
            if ch.afro < price:
                self.send("cmdAck", res=RES_NO_MONEY)
                return
            ch.add_money(-price)
            # None is how the Character spells "full" (progression.py).
            ch.hp = None
            ch.sp = None
            with STORE.booked_as("healer", npc_type):
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
        with STORE.booked_as("transport", type_id):
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
        # A new order replaces the old one, the walk onto a walk-in included:
        # the player has turned round before reaching it.
        self.cancel_passage()
        # Location.movePlayer registers a cmdAck handler for every single step
        # it asks for. Leaving those unanswered does not stall movement, since
        # that handler is empty, but the queue is strictly ordered: each later
        # reply is then handed to a stale mover instead of the command that
        # earned it, and things like opening a shop quietly stop working.
        if self.room is None and "path" in p:
            self.refuse_walk_between_rooms()
            return
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
        cells = [int(c) for c in path]
        walk = self.walk_of(cells)
        self.pos = cells[-1]
        # The figure starts from cells[0] on the echo below and is not at
        # pos for another HEX_MS a step (live_cell).
        self.walk = walk
        try:
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
        finally:
            # A barter needs the two side by side; a step away ends it --
            # the step is taken (pos above) whatever failed on the way.
            self.barter.moved()
        self.arm_passage(len(cells))

    def refuse_walk_between_rooms(self):
        """A walk that arrives after an lcall and before its lenter.

        enter_location has left the old room and enter_room has not joined
        the next, and self.loc and self.pos are already the next location's.
        The walk was sent from the location being left -- the client stops
        sending moveTo only once the lcall reaches it (FilterManager.
        createCWFilter) -- so its cells are numbered for that file's grid:
        taken, they would land wherever those numbers fall in the new one,
        on rock as readily as not, and lenter would stand the player there.
        Every lcall opens this gap -- a door, a quest way, /goto, a walk-in,
        a resurrection -- for the one round trip the lcall takes to arrive.

        It is refused, and nothing moves: lenter puts the player on the cell
        the server moved him to. The step is still owed its cmdAck -- the
        location being left keeps its moveCmdAck on the queue until lenter
        (Location.kill), and the handler reads nothing in the answer -- and
        this once the refusal is that ack, not a breakMv: the location being
        left and the one being built both listen for breakMv, and both would
        move the one walker (Location.getWalker gives master.gamer's) to a
        cell numbered for the new grid and looked up in the old one
        (LocWalker.breakMove), whose finishMove opens the exit window if the
        cell happens to be a zone there.

        A frame without a path is left to move_in_location's own refusal: a
        map's moveTo in flight registers no cmdAck (GlobalMap.playerMove),
        so an ack for it would be handed to whatever command came next.
        """
        log.info("  ..    walk between rooms, into %s: refused", self.loc.file)
        self.send("cmdAck", res=RES_NOT_READY)

    # --- walk-in passages ----------------------------------------------------
    # A way a location file draws without a zone on it: the client never
    # opens its exit window there (Location.finishMove asks for the zone
    # flag). data/passages.json lists such cells under walk_in, and a walk
    # that ends on one moves the player through once the figure has arrived
    # -- or, if a fight holds it shut then, the moment the fight lets them
    # go, for as long as they stay on the cell (take_passage). No place has
    # one now: the Nubian mine's mouth and EXIT sign were the two, and its
    # quests are the way in and out again (hand_in_way); test_walk_in
    # keeps the mechanism running on a table of its own.
    # Nothing on the client side waits for this -- no chWorld was sent, no
    # handler is queued -- so it is an lcall and nothing else, the way /goto
    # and a resurrection move a player.

    def arm_passage(self, path_len):
        """After a walk: if it ends on a walk-in cell, go through when the
        figure gets there (travel.walk_seconds)."""
        if self.room is None or travel.walk_in_at(self.loc, self.pos) is None:
            return
        self.passage = asyncio.get_running_loop().call_later(
            travel.walk_seconds(path_len), self.take_passage,
            self.room, self.pos)

    def cancel_passage(self):
        if self.passage is not None:
            self.passage.cancel()
            self.passage = None

    def take_passage(self, room, pos, said=frozenset()):
        """The walk has ended on a walk-in cell: open what lies beyond.

        Asked again rather than trusted, because a second has passed: the
        player must still be standing there, in the same room, alive, and not
        held by a fight -- the same hold chWorld keeps, or the passage would
        be the way out of every fight at its mouth. A refusal is a line of chat:
        there is no command of the client's to refuse.

        A fight only postpones it. The player who stays on the cell has not
        changed their mind, and cannot say so again -- the client sends no
        path to the cell it stands on -- so the passage asks once more every
        PASSAGE_RETRY for as long as they stand there, and goes the moment
        the fight lets them. Whatever ends that wait ends it here or before:
        a new moveTo and leaving the room cancel the timer (move_in_location,
        leave_room: the map, /goto, a resurrection, a dropped socket), and a
        death leaves the player lying on the cell, which the check below
        refuses without asking again. said holds the reasons already told,
        so the wait is one line of chat per reason and not one a second.
        """
        self.passage = None
        if (self.closed or self.on_map or self.room is not room
                or self.pos != pos or self.combat.dead):
            return
        # A timer, not a command: nothing in handle() is around this to
        # keep a bug from taking the player's session with it.
        try:
            self.go_through_passage(said)
        except Exception:
            log.exception("  !!    walk-in from %s failed", self.loc.file)

    def fight_hold(self):
        """Why the player may not be moved out of this room just now, or
        None: "timer", the exit timer in_combat keeps (the one chWorld is
        refused by), which a creature still after the player does not
        prolong -- only a hit given or taken does -- or "acting": a shot, a
        swing or a heal of the player's own still in the air. The lcall
        would cancel that half-way (Fighter.left), and a shot at a creature
        that nothing was after turns it on the shooter when it lands -- the
        fight the player has just started."""
        fighter = self.combat
        if fighter.in_combat():
            return "timer"
        if fighter.acting():
            return "acting"
        return None

    def exit_seconds(self):
        """Whole seconds the exit timer has left, at least one: what the
        client's own countdown shows (LocationInterface.exitTimer)."""
        return max(1, math.ceil(self.combat.exit_timer_left()))

    def hold_line(self, verb):
        """(reason, line of chat) while a fight holds the player where he
        is, or None: what a walk-in ("пройдёте") and a way handed in
        ("отправитесь") wait for. The line is None for a hold nobody needs
        telling about: the move goes by itself the moment a shot in the air
        lands."""
        reason = self.fight_hold()
        if reason == "timer":
            return reason, "Идёт бой: %s через %d с" % (verb, self.exit_seconds())
        if reason == "acting":
            return reason, None
        return None

    def passage_hold(self):
        """hold_line for a walk-in: while the player may not go through."""
        return self.hold_line("пройдёте")

    def go_through_passage(self, said=frozenset()):
        """What leave_through_exit does for a door, minus the cmdAck: the
        client sent no chWorld and holds no handler for one."""
        hold = self.passage_hold()
        if hold is not None:
            reason, line = hold
            if line and reason not in said:
                self.say(line)
                said = said | {reason}
            self.passage = asyncio.get_running_loop().call_later(
                PASSAGE_RETRY, self.take_passage, self.room, self.pos, said)
            return
        try:
            dest = travel.plan_walk_in(self.loc, self.pos,
                                       round(self.gx), round(self.gy))
        except travel.Refused as why:
            self.say(str(why))
            return
        self.cancel_travel()
        self.gx, self.gy = dest.gx, dest.gy
        self.loc = world.location(dest.loc_id)
        self.pos = dest.pos
        log.info("  ..    walk-in -> %s (%s) at %d, cell %d,%d",
                 self.loc.title, self.loc.file, self.pos, self.gx, self.gy)
        self.enter_location()

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
                # Closed under our feet (a relogin elsewhere, a kick): the
                # rest of what this socket sent is not read at all, see
                # Session.handle.
                if sess.closed:
                    break
                try:
                    name, params = decode(raw)
                except Exception:
                    log.exception("  bad frame %r", raw[:200])
                    # One answer to every command the client waits on, even
                    # one that cannot be read (a modified client's
                    # «c_ga;gold=nan;»): its name says whether it waits,
                    # and a silence would hand every later reply to the
                    # wrong handler.
                    if bad_frame_expects_ack(raw):
                        sess.send("cmdAck", res=bad_frame_res(raw))
                    continue
                sess.handle(name, params)
            if sess.closed:
                break
            await writer.drain()
            if sess.closed:
                break
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
    logging.basicConfig(level=os.environ.get("LAVA_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(message)s")
    # Content is read before the first socket is open, never inside a
    # handler: a lazy load of the wiki tables once stalled the loop for two
    # seconds on whichever request touched an item first.
    items.preload()
    # A quest row naming a thing the game does not have, or handing over one
    # worth something, stops the server here, as a broken chain stops it at
    # the import (quests.check_items): at a hand-in it would be a quest
    # written as done, nothing paid and no ack.
    quests.check_items()
    # So does a data/questgen_setcraft.json built off another ladder than
    # data/sets.json is now: its prices would not be the stalls' (setcraft).
    setcraft.check_rows()
    # So does an inhabitant put down by hand who cannot stand where the
    # table says (rooms.check_placements): a room is built on its first
    # entry, and there the player would meet a creature the client cannot
    # draw, or one on the exit.
    rooms.check_placements(MOB_TYPES)
    # And so does a timed window whose rows cannot work (events.check).
    events.check(MOB_TYPES)
    names.document()
    # Bags left lying when the last process ended go back where they lay,
    # for the rest of their time; what ran out meanwhile, or has no place
    # written down, is cleared (combat.restore_ground).
    swept, back = combat.restore_ground(ROOMS, STORE)
    if swept:
        log.info("cleared %d item(s) the last run left on the ground", swept)
    if back:
        log.info("%d item(s) back on the ground where the last run left them", back)
    # The admin panel's gifts to players not in the game, given bare before
    # 2026-09-29: once per database, here rather than in accounts.migrate,
    # which the registration page runs too and which knows no catalogue.
    if accounts.run_once(STORE.db, inventory.OFFLINE_GIFTS_FIX,
                         inventory.fill_offline_gifts):
        log.info("filled the admin panel's offline gifts (%s)",
                 inventory.OFFLINE_GIFTS_FIX)
    game = await asyncio.start_server(handle_client, HOST, PORT)
    log.info("game server on %s:%d", HOST, PORT)
    log.info("%s", bosses.describe())
    log.info("%s", events.describe())
    servers = [game]
    admin_task = asyncio.ensure_future(drain_admin_actions())
    # Lots that ran out while the server was down are settled by the first
    # pass, before anybody can search for them.
    auction_task = asyncio.ensure_future(auction.run(STORE, ONLINE))
    if POLICY_PORT:
        try:
            pol = await asyncio.start_server(handle_policy, HOST, POLICY_PORT)
            log.info("policy server on %s:%d", HOST, POLICY_PORT)
            servers.append(pol)
        except PermissionError:
            log.warning("no permission for port %d; policy served inline only",
                        POLICY_PORT)
        except OSError as e:
            # Taken, by another server of ours as a rule: on Linux a second
            # one is refused 843 as non-root and lands above; on Windows
            # anybody may bind it, so the first holds it and the rest came
            # down here and died at start, with every suite on the machine.
            # The policy is answered inline on the game port regardless.
            log.warning("port %d is taken (%s); policy served inline only",
                        POLICY_PORT, e.strerror or e)
    # run.sh stop sends SIGTERM and a terminal sends SIGINT. Either one only
    # raises the flag; the leaving is done below, on the loop, so a handler
    # in the middle of a frame finishes it first. Without this the loop just
    # died with every handle_client parked in read(), no finally ran, and
    # whoever was online came back wherever they had logged out the time
    # before.
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            # Windows: the proactor loop has no signal handlers, and the
            # process used to die right here before it had served a frame.
            # A plain handler raises the same flag from the loop's thread;
            # Ctrl-C reaches it, a TerminateProcess from outside does not
            # and takes the loop with it, as it does any process.
            signal.signal(sig, lambda *_a: loop.call_soon_threadsafe(stopping.set))
    await stopping.wait()
    admin_task.cancel()
    auction_task.cancel()
    await shutdown(servers)


ADMIN_POLL_SECONDS = float(os.environ.get("LAVA_ADMIN_POLL", "1.0"))


def session_for(char_id):
    """The live session playing that character, if any."""
    for sess in SESSIONS:
        if sess.char_id == char_id and not sess.closed:
            return sess
    return None


def apply_admin_action(row):
    """Carry out one queued action and say what happened.

    A character who is online is changed through the session holding it,
    because Character.save() writes its own numbers back at logout and would
    undo anything done behind it. A character who is not online has no such
    copy, so the database is the truth and is written directly.
    """
    args = json.loads(row["args_json"] or "{}")
    kind = row["kind"]
    sess = session_for(row["char_id"]) if row["char_id"] else None

    if kind == "kick" or kind == "ban":
        if kind == "ban":
            STORE.set_banned(row["account_id"], bool(args.get("banned", True)))
        target = None
        for s in SESSIONS:
            if s.account and s.account["id"] == row["account_id"]:
                target = s
                break
        if target is None:
            return ("забанен, в игре его нет" if kind == "ban"
                    else "в игре его нет")
        target.kick(row["admin"], args.get("seconds", 0), args.get("reason", ""))
        return "выкинут из игры"

    # A clan's action names a clan, not a character, so it goes before the
    # question of one (clan_admin.py).
    if kind == "clan":
        return clan_admin.apply(row, CLANS)

    if row["char_id"] is None:
        return "действию нужен персонаж"

    if sess is not None:
        if kind == "money":
            return sess.admin_money(args.get("afro", 0), args.get("gold", 0))
        if kind == "item":
            return sess.admin_give(args["type_id"], args.get("count", 1))
        if kind == "transport":
            return sess.admin_transport(args["type_id"], args.get("days"))
        if kind == "goto":
            return sess.admin_goto(args.get("loc_id"), args.get("gx"),
                                   args.get("gy"))
        return "неизвестное действие: %s" % kind

    # Offline: nothing is holding this character, so the row is the truth.
    row_c = STORE.character(row["char_id"])
    if row_c is None:
        return "персонажа нет"
    if kind == "money":
        with STORE.booked_as("admin"):
            STORE.save_character_state(
                row["char_id"],
                afro=int(row_c["afro"]) + int(args.get("afro", 0)),
                gold=int(row_c["gold"]) + int(args.get("gold", 0)))
        return "начислено (не в игре)"
    if kind == "item":
        type_id = int(args["type_id"])
        if items.params_of(type_id) is None:
            return "предмета %d нет в каталоге" % type_id
        if items.premium(type_id):            # as Session.admin_give
            return PREMIUM_REFUSED % type_id
        count = int(args.get("count", 1))
        if items.root_of(type_id) not in items.HEAPABLE_ROOTS:
            count = 1
        # Factory-fresh, as Session.admin_give's Inventory.create makes it:
        # the bare row this was gave a gun 0 of 0, past any repair window
        # (inventory.OFFLINE_GIFTS_FIX mends the ones already given).
        fields = inventory.new_fields(type_id, max(1, min(count, 999)))
        STORE.create_item(row["char_id"], type_id, fields.pop("root"), **fields)
        return "положено в рюкзак (не в игре)"
    if kind == "transport":
        type_id = int(args["type_id"])
        if type_id == 0:
            STORE.save_character_state(row["char_id"], transport_type=None,
                                       transport_until=None)
            return "транспорт снят (не в игре)"
        if transport.get(type_id) is None:
            return "транспорта %d нет в таблице" % type_id
        if transport.premium(type_id):        # as Session.admin_transport
            return PREMIUM_TRANSPORT_REFUSED % type_id
        days = max(1, min(int(args.get("days") or transport.MAX_DAYS),
                          transport.MAX_DAYS))
        STORE.save_character_state(
            row["char_id"], transport_type=type_id,
            transport_until=transport.until_after(days))
        return "выдан на %d дн. (не в игре)" % days
    if kind == "goto":
        loc_id = args.get("loc_id")
        if loc_id is None:
            gx, gy = int(args["gx"]), int(args["gy"])
            loc_id = world.location_at(gx, gy)
        else:
            loc_id = int(loc_id)
            gx, gy = (world.unpack(loc_id) if world.is_wilderness(loc_id)
                      else world.cell_of(loc_id) or (row_c["gx"], row_c["gy"]))
        STORE.save_character_state(row["char_id"])       # no-op, keeps the API
        STORE.db.execute(
            "UPDATE characters SET loc = ?, gx = ?, gy = ?, on_map = 0"
            " WHERE id = ?", (loc_id, gx, gy, row["char_id"]))
        STORE.db.commit()
        return "перенесён (войдёт там)"
    return "неизвестное действие: %s" % kind


def broadcast_online_count():
    """HUD presence: entered characters, including people on the map.

    Directory membership survives room changes and excludes the login and
    character creation screens. Only hello;online=1 clients receive this
    unsolicited frame; it never participates in the cmdAck queue.
    """
    count = len(ONLINE.by_char)
    for sess in ONLINE:
        if sess.online_counter and not sess.closed:
            sess.send("online", count=count)


def publish_online():
    """Write down who is playing, for the panel in the other process.

    It cannot see the sessions -- they are objects in this one -- so the
    snapshot goes through the database with the rest of the traffic between
    the two. Rewritten whole on every pass rather than patched, because a
    session that ends abruptly leaves no event to patch it by.
    """
    rows = []
    for sess in list(SESSIONS):
        if sess.closed or not sess.char_id:
            continue
        loc = getattr(sess, "loc", None)
        rows.append(dict(
            char_id=sess.char_id,
            nick=sess.nick or "",
            login=(sess.account["login"] if sess.account else ""),
            loc=(loc.id if loc is not None else None),
            title=("на карте" if sess.on_map else
                   (loc.title if loc is not None else "")),
            gx=int(sess.gx or 0), gy=int(sess.gy or 0),
            since=int(getattr(sess, "since", time.time()))))
    STORE.set_online(rows)


async def drain_admin_actions():
    """Watch the queue the admin panel writes into.

    Polling, and not a socket between the two processes: one small indexed
    read a second costs nothing, needs no port, no second protocol and no
    second thing to authenticate, and it keeps working when the panel is
    restarted under the game or the other way round.
    """
    while True:
        try:
            publish_online()
            for row in STORE.admin_pending():
                try:
                    result = apply_admin_action(row)
                except Exception as exc:                 # noqa: BLE001
                    log.exception("admin action %d failed", row["id"])
                    result = "ошибка: %s" % exc
                log.info("  ..    admin %s: %s -> %s",
                         row["admin"], row["kind"], result)
                STORE.admin_done(row["id"], result)
        except Exception:                                # noqa: BLE001
            # A failure here must not take the game down with it.
            log.exception("admin queue")
        await asyncio.sleep(ADMIN_POLL_SECONDS)


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
