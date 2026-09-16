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
import os
import time

import accounts
import items
import names
import quests
import world
from protocol import FrameReader, decode, frame, Str

HOST = os.environ.get("LAVA_HOST", "0.0.0.0")
PORT = int(os.environ.get("LAVA_PORT", "9775"))
POLICY_PORT = 843
STORE = accounts.Store()

# Commands whose sender registers a cmdAck handler, gathered from the client:
# mail, clans, party, auction, battlegrounds, item sessions, quests, map marks
# and chat all do. Anything here has to be answered, implemented or not.
EXPECTS_ACK = {
    "chkml", "getml", "sndml", "rmvml", "uldml",
    "p_op", "admit", "apply", "head", "gg_info", "c_ga",
    "ah_create", "ah_op", "ah_search", "bg_op",
    "ss_move", "ss_use", "ss_heap_c", "ss_create", "ss_upd",
    "on_conv", "q_st", "q_co", "q_ca",
    "insMark", "updMark", "rmMark",
    "userMsg", "resurrect", "actPlayer", "newPers", "lenter", "chWorld",
}

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
# Entity ids: 0 is always the player, so anything placed in the world starts
# above that.
FIRST_NPC_ID = 100

# The map is a plain grid, 5833..6305 by 1600..2110, and the client labels its
# cells from res/database/locations.xml on its own. Every cell can be entered:
# 86 of them hold a settlement recovered into data/settlements.json, and the
# rest resolve to open desert by world.location_at.
VIEW_RADIUS = 8
TRAVEL_SPEED = 0.35   # cells per second

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

ATTRIBS = 5    # сила, ловкость, телосложение, восприятие, интеллект
SKILLS = 5     # ближний бой, стрельба, медицина, промышленность, производство
SPECS = 15

# Quest limits, sent in the constants frame and enforced here. The client
# refuses a take beyond quest_log_capacity on its own (QuestInterface.getQuest),
# but a modified one would not, so the server counts too. daily_reset_time is
# minutes past UTC midnight; the client only uses it for the journal caption.
QUEST_LOG_CAPACITY = 20
DAILY_MAX = 10
DAILY_RESET_TIME = 0

# Until characters have statistics (TASKS stage 3): every skill sits at level
# 1 (cmd_rp_get_info), HP and SP are a flat 100, and a medic charges 10 afro.
SKILL_LEVEL = 1
HP_MAX = 100
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


def full_mask(n):
    """Mask with every slot present, for the mask + dense-list encoding."""
    return (1 << n) - 1


class Session:
    def __init__(self, writer, peer):
        self.writer = writer
        self.peer = peer
        self.hash = None
        self.logged_in = False
        self.account = None
        self.characters = []
        self.char_id = None
        self.active = None
        self.loc = world.location(START_LOC)
        self.pos = self.loc.entry_cell()
        self.on_map = False
        # The cell the current location stands on, and where leaving returns
        # to. Fractional only while a leg of map travel is in flight.
        self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        self.arrival = None
        # a leg in flight: (start time, from x, from y, vx, vy)
        self.leg = None
        # entity id -> (cell, type_id, rtype) for everything placed
        self.npcs = {}

    # --- plumbing --------------------------------------------------------
    def send(self, *_cmd, **params):
        """Send one frame. The command name is positional, because several
        commands carry a parameter literally called "name"."""
        data = frame(_cmd[0], **params)
        log.info("  S->C  %s", data[:-1].decode("utf-8", "replace"))
        self.writer.write(data)

    def handle(self, cmd, params):
        log.info("  C->S  %s %s", cmd, params)
        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
            # Commands that register a handler must be answered even when the
            # feature does not exist yet. A refusal keeps the queue in step; a
            # silence shifts every later reply onto the wrong handler.
            if cmd in EXPECTS_ACK:
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
        self.send("constants",
                  gold_to_afro_rate=100,
                  quest_log_capacity=QUEST_LOG_CAPACITY,
                  leave_combat_timeout=30,
                  premium_weight_bonus_1=2, premium_weight_bonus_2=4,
                  premium_break_bonus_1=1, premium_break_bonus_2=2,
                  premium_xp_bonus_1=1, premium_xp_bonus_2=2,
                  gold_repair_price_mod=1, gold_repair_mod=10000,
                  daily_max=DAILY_MAX, daily_reset_time=DAILY_RESET_TIME)
        for pers in self.characters:
            self.send("persInfo", num=pers["slot"], name=Str(pers["name"]),
                      sex=pers["sex"], death=0, res=Str(str(pers["res"])))
        # can_create must be falsy once the account has someone, or the client
        # opens the creation screen instead of selecting: PersGenerator acts on
        # the flag alone and never looks at how many characters arrived.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=0 if self.characters else 1)

    def cmd_logout(self, p):
        self.close()

    def close(self):
        self.cancel_travel()
        if self.char_id:
            STORE.save_position(self.char_id, self.loc.id, self.pos,
                                self.gx, self.gy, self.on_map)
        self.writer.close()

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
                self.restore(c)
                break
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
        self.on_map = bool(c["on_map"])
        if c["loc"] is not None:
            try:
                self.loc = world.location(c["loc"])
            except (KeyError, OSError) as exc:
                log.warning("  ..    location %s unreadable (%s), starting over",
                            c["loc"], exc)
                self.loc = world.location(START_LOC)
                self.gx, self.gy = GLOBAL_X, GLOBAL_Y
        # A cell saved in one location means nothing in another, and a cell
        # outside the grid would put the player in a wall.
        if c["pos"] and 0 <= c["pos"] < self.loc.width * self.loc.height:
            self.pos = c["pos"]
        else:
            self.pos = self.loc.entry_cell()

    def cmd_actPlayer(self, p):
        self.send("cmdAck", res=0)
        self.enter_location()

    # --- world -----------------------------------------------------------
    def enter_location(self):
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork.
        self.send("lcall", id=self.loc.id, ws=self.loc.war, ie=0,
                  g_id=world.pack(round(self.gx), round(self.gy)))

    def cmd_lenter(self, p):
        """Answer the client's "I have loaded, let me in".

        No cmdAck on success: Master.lenter cancels the handler it registered
        for one as soon as the lenter frame lands, so the acknowledgement is
        the failure path only.
        """
        # aspd is the action-point gain per 600ms tick, amax the ceiling.
        self.send("lenter", pos=self.pos, aspd=1, amax=20)
        # How many quests may still be handed in today. Only QuestInspector
        # reads it, and that singleton exists from the first Entity built
        # (Entity.as:37), long before the location opens, so it lands.
        self.send("q_sys", daily_available=self.daily_available())
        self.populate()

    def populate(self):
        """Place the location's own inhabitants, one lch frame each.

        The spawn points and their type ids come straight out of the location
        file; only behaviour was stripped. rtype tells the client which class
        to build.
        """
        self.npcs.clear()
        skipped = 0
        for cell, type_id in self.loc.spawns:
            # A creature the client has no record of cannot be drawn or named.
            # res misses in its copy of mobs.xml and the art resolves to
            # mobs/undefined.xml, and worse, the name id reaches the client
            # unknown, which fetches a string batch and puts the login screen
            # back on top of the game. 670 of the type ids used by locations
            # are absent from mobs.xml, so this is not a rare corner.
            if type_id not in MOB_TYPES or not names.known(type_id):
                skipped += 1
                continue
            root = MOB_TYPES[type_id][0]
            self.npcs[FIRST_NPC_ID + len(self.npcs)] = (cell, type_id, root)

        # Three passes, and the order is what makes them visible. A positioned
        # lch builds the figure at once, and the figure resolves its art from
        # persType, which only userInfo supplies. Place first and it asks for
        # mobs/undefined.xml once, never retries, and leaves a placeholder cone
        # standing there. An lch carrying refl registers the entity without a
        # figure, so the details can land before anything is drawn. The refl
        # frame still has to carry pos: Location.lch ignores the whole frame
        # unless newUser, pos and rtype are all present, refl or not.
        for npc_id, (cell, _type, root) in self.npcs.items():
            self.send("lch", newUser=npc_id, pos=cell, rtype=root)
            self.send_npc_info(npc_id)
        log.info("  ..    placed %d inhabitants in %s (%s)%s",
                 len(self.npcs), self.loc.title, self.loc.file,
                 ", %d unknown to the client" % skipped if skipped else "")

    def cmd_chWorld(self, p):
        """One command, both directions: the button is a toggle.

        GlobalMapInterface.toLocation and LocationInterface both call
        changeWorld with no argument, so which way the player goes is decided
        here, from where they currently are.
        """
        self.send("cmdAck", res=0)
        if self.on_map:
            self.enter_cell()
        else:
            # Leaving puts the player back on the cell the location stands on.
            self.on_map = True
            self.cancel_travel()
            self.send("gmap", x=self.gx, y=self.gy, v_rad=VIEW_RADIUS)

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
        self.gx, self.gy = int(round(x)), int(round(y))
        self.on_map = False
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
        self.send("cmdAck", res=0)
        text = (p.get("entry") or "").strip()
        group = int(p.get("group", 0) or 0)
        if text.startswith("/goto"):
            self.cmd_goto(text.split()[1:], group)
            return
        if text.startswith("/where"):
            # Everything needed to report a cell that opens the wrong place:
            # the title as drawn, the file behind it, and the cell itself.
            self.say("%s — %s [%s] — клетка %d,%d"
                     % (self.loc.title, self.loc.file, self.loc.fn or "-",
                        round(self.gx), round(self.gy)), group)
            return
        # Ordinary talk comes back to the sender, which is how the client
        # shows it: it prints nothing of its own when a message is typed.
        pers = self.active or default_character()
        self.send("userMsg", entry=Str(text), group=group,
                  nick=Str(pers["name"]), **{"from": 0})

    def cmd_goto(self, args, group=0):
        """/goto <id> | /goto <x> <y> -- open a location, or a map cell."""
        try:
            if len(args) >= 2:
                gx, gy = int(args[0]), int(args[1])
                loc_id = world.location_at(gx, gy)
            elif len(args) == 1:
                loc_id = int(args[0])
                # A wilderness id names its own cell; an interior does not,
                # so the player keeps the cell they came from and leaving
                # puts them back on it.
                gx, gy = (world.unpack(loc_id) if world.is_wilderness(loc_id)
                          else (self.gx, self.gy))
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
        tx, ty = self.gx + dx, self.gy + dy
        vx, vy = dx / dist * TRAVEL_SPEED, dy / dist * TRAVEL_SPEED
        self.send("moveAck", vx=vx, vy=vy, t=0)

        loop = asyncio.get_running_loop()
        self.leg = (loop.time(), self.gx, self.gy, vx, vy)
        if self.arrival:
            self.arrival.cancel()
        self.arrival = loop.call_later(dist / TRAVEL_SPEED, self.arrive, tx, ty)

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
        # Deliberately no automatic entry here. Settlements occupy a whole
        # cell, so any short hop near one landed inside it and the map became
        # impossible to stay on. Going in is the button's job.

    def cmd_getInfo(self, p):
        who = int(p.get("id", 0))
        if who != 0:
            self.send_npc_info(who)
            return
        self.send_player_info()
        self.send_vitals()

    def send_player_info(self):
        """userInfo_Player for the player, with the purse as stored.

        This is the only frame that carries money: Gamer.userInfo reads afro
        and gold off it and nothing else updates them, so a quest reward or a
        medic's fee is paid by sending it again (quests.md 1.7).
        """
        pers = self.active or default_character()
        afro, gold = STORE.money(self.char_id) if self.char_id else (1000, 0)
        self.send("userInfo_Player",
                  id=0, name=Str(pers["name"]), sex=pers["sex"],
                  res=Str(str(pers["res"])), ail=0, ally=1, lvl=1,
                  rep=[0], bg_rep=0, bg_pen=0, clan=0,
                  hl=0, pr=0,
                  afro=afro, gold=gold, tr=0, tr_hours=0)

    def send_vitals(self, hcur=HP_MAX, scur=HP_MAX):
        """usrUp: the only frame that moves the HP and SP bars."""
        self.send("usrUp", id=0, hcur=hcur, hmax=HP_MAX, scur=scur, smax=HP_MAX)

    def send_npc_info(self, npc_id):
        """Answer getInfo for one inhabitant.

        name is a numeric string id, not text: the client resolves it over HTTP
        against database/texts.xml. Passing the type id lets the stub there hand
        back the creature's internal name instead of a placeholder.

        ally must be truthy or every service this NPC offers is refused before
        a single frame is exchanged.
        """
        entry = self.npcs.get(npc_id)
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
            params.update(give_transport=[])
        elif root == world.HEALER:
            # Healer.as builds g_price from the same a_price, so only the
            # afro fee is ever shown; on_conv;op=1 charges this much.
            params.update(a_price=MEDIC_PRICE)
        elif root == world.COMMONER:
            params.update(can_set_home=1)
        self.send(cmd, **params)

    def cmd_rp_get_info(self, p):
        """Attributes, skills and specialisations, despite the name.

        Each group is a bitmask plus a dense list holding only the slots the
        mask sets. A specialisation with a negative value counts as not yet
        learned.
        """
        self.send("rp_info",
                  a_attribs_mask=full_mask(ATTRIBS), a_attribs=[5] * ATTRIBS,
                  f_attribs_mask=full_mask(ATTRIBS), f_attribs=[5] * ATTRIBS,
                  a_skills_mask=full_mask(SKILLS), a_skills=[1] * SKILLS,
                  f_skills_mask=full_mask(SKILLS), f_skills=[1] * SKILLS,
                  xp_skills_mask=full_mask(SKILLS), xp_skills=[1] * SKILLS,
                  xp_max_skills_mask=full_mask(SKILLS),
                  xp_max_skills=[100] * SKILLS,
                  a_specs_mask=full_mask(SPECS), a_specs=[-1] * SPECS,
                  f_specs_mask=full_mask(SPECS), f_specs=[1] * SPECS,
                  xp_specs_mask=full_mask(SPECS), xp_specs=[1] * SPECS,
                  xp_max_specs_mask=full_mask(SPECS),
                  xp_max_specs=[100] * SPECS,
                  max_specs=3,
                  hp=100, hp_max=100, sp=100, sp_max=100,
                  ap_max=20, max_weight=50000, armor=1, lvl=1)

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
        self.send("cmdAck", res=0)

    def cmd_ss_upd(self, p):
        self.send("cmdAck", res=0)

    def cmd_ss_get_s_si(self, p):
        # Nothing belongs to a set yet, but the request still needs answering.
        self.send("ss_si_set", type=int(p.get("type", 0)), res=0, name=0,
                  desc="")

    def cmd_ss_get(self, p):
        # Answer even when empty; ItemFactory pipelines these and stops
        # issuing new ones until each outstanding request comes back.
        self.send("ss_ack", o_list=[])

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

    def cmd_chkml(self, p):
        """Mail. The client asks the moment it lands in a location.

        mode 0 is the inbox, 1 the outbox, 255 the tariffs. All three expect an
        acknowledgement first, then the listing itself.
        """
        mode = int(p.get("mode", 0))
        self.send("cmdAck", res=0)
        if mode == 255:
            # Eight prices and eight delivery times, in the order the client
            # reads them: ordinary, express, clan, express clan, then the same
            # four again as the charge per kilogram of attachments.
            self.send("svml", data=[10, 100, 20, 200, 5, 50, 15, 150],
                      time=[3600, 600, 3600, 600, 3600, 600, 3600, 600])
        else:
            self.send("lsml", id=[], date=[], name=[], flag=[], subj=[])

    # --- quests ------------------------------------------------------------
    # The model is in quests.py and recon/analysis/quests.md 1-2. What matters
    # here: q_status/q_si/q_di are pipelined one at a time and must each be
    # answered with a frame, q_st/q_co/q_ca each expect exactly one cmdAck,
    # and after q_st the server itself has to push the new instance's q_di,
    # or the quest never reaches the journal (the client adds nothing on the
    # ack alone, QuestInspector.getAck).

    def skill_level(self):
        """The player's best skill level, the number quest.level is held to.
        A flat 1 until characters have statistics (TASKS 3.x)."""
        return SKILL_LEVEL

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
        entry = self.npcs.get(int(npc_id or 0))
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
            STORE.add_money(self.char_id, quest.rew_afro, quest.rew_gold)
            self.send_player_info()
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
        failing, and transport does not exist yet (TASKS 8.7).
        """
        op = int(p.get("op", -1))
        npc_type = self.npc_type(p.get("mob"))
        if npc_type is None or not self.char_id:
            self.send("cmdAck", res=RES_NO_SUCH)
            return
        if op == 0:
            STORE.set_home(self.char_id, self.loc.id)
            log.info("  ..    home set to %d (%s)", self.loc.id, self.loc.title)
            self.send("cmdAck", res=0)
        elif op == 1:
            if MOB_TYPES[npc_type][0] != world.HEALER:
                self.send("cmdAck", res=RES_WRONG_NPC)
                return
            afro, _gold = STORE.money(self.char_id)
            if afro < MEDIC_PRICE:
                self.send("cmdAck", res=RES_NO_MONEY)
                return
            STORE.add_money(self.char_id, -MEDIC_PRICE)
            self.send_player_info()
            self.send_vitals()
            self.send("cmdAck", res=0)
        else:
            self.send("cmdAck", res=RES_NOT_AVAILABLE)

    def move_in_location(self, p):
        """Echo the path back; the client renders no step until we do.

        Location.movePlayer only records the destination and sends the frame.
        The walk animation starts solely from a server userMove, including for
        the player who asked.
        """
        path = p.get("path")
        if not path:
            return
        # Location.movePlayer registers a cmdAck handler for every single step
        # it asks for. Leaving those unanswered does not stall movement, since
        # that handler is empty, but the queue is strictly ordered: each later
        # reply is then handed to a stale mover instead of the command that
        # earned it, and things like opening a shop quietly stop working.
        self.send("cmdAck", res=0)
        self.pos = int(path[-1])
        self.send("userMove", id=0, path=[int(c) for c in path])


async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    log.info("connect %s", peer)
    sess = Session(writer, peer)
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
        log.info("disconnect %s", peer)
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
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
