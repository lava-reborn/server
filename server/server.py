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
import logging
import os

import accounts
import items
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
                  quest_log_capacity=20,
                  leave_combat_timeout=30,
                  premium_weight_bonus_1=2, premium_weight_bonus_2=4,
                  premium_break_bonus_1=1, premium_break_bonus_2=2,
                  premium_xp_bonus_1=1, premium_xp_bonus_2=2,
                  gold_repair_price_mod=1, gold_repair_mod=10000,
                  daily_max=10, daily_reset_time=0)
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
        self.populate()

    def populate(self):
        """Place the location's own inhabitants, one lch frame each.

        The spawn points and their type ids come straight out of the location
        file; only behaviour was stripped. rtype tells the client which class
        to build.
        """
        self.npcs.clear()
        for i, (cell, type_id) in enumerate(self.loc.spawns):
            root = MOB_TYPES.get(type_id, (world.MOB, "", ""))[0]
            self.npcs[FIRST_NPC_ID + i] = (cell, type_id, root)

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
        log.info("  ..    placed %d inhabitants in %s (%s)",
                 len(self.npcs), self.loc.title, self.loc.file)

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
    EVENT_CHANNEL = 3          # Chat.CHAT_EVENT_CHANNEL

    def say(self, text):
        """A line from the server, on the channel the client keeps for them."""
        self.send("userMsg", entry=Str(text), group=self.EVENT_CHANNEL,
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
        if text.startswith("/goto"):
            self.cmd_goto(text.split()[1:])
            return
        if text.startswith("/where"):
            # Everything needed to report a cell that opens the wrong place:
            # the title as drawn, the file behind it, and the cell itself.
            self.say("%s — %s [%s] — клетка %d,%d"
                     % (self.loc.title, self.loc.file, self.loc.fn,
                        round(self.gx), round(self.gy)))
            return
        # Ordinary talk comes back to the sender, which is how the client
        # shows it: it prints nothing of its own when a message is typed.
        pers = self.active or default_character()
        self.send("userMsg", entry=Str(text), group=int(p.get("group", 0)),
                  nick=Str(pers["name"]), **{"from": 0})

    def cmd_goto(self, args):
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
                self.say("/goto <номер локации>  или  /goto <x> <y>")
                return
        except ValueError:
            self.say("Не понял. /goto <номер локации> или /goto <x> <y>")
            return
        try:
            loc = world.location(loc_id)
        except (KeyError, OSError):
            self.say("Локации %d нет" % loc_id)
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
        pers = self.active or default_character()
        self.send("userInfo_Player",
                  id=0, name=Str(pers["name"]), sex=pers["sex"],
                  res=Str(str(pers["res"])), ail=0, ally=1, lvl=1,
                  rep=[0], bg_rep=0, bg_pen=0, clan=0,
                  hl=0, pr=0,
                  afro=1000, gold=0, tr=0, tr_hours=0)
        self.send("usrUp", id=0, hcur=100, hmax=100, scur=100, smax=100)

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
        params = dict(id=npc_id, name=type_id, sex=0, res=type_id,
                      ail=0,
                      ally=1, lvl=1, rep=[0], bg_rep=0, bg_pen=0,
                      give_quests=[], take_quests=[], m_hello=[],
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
            params.update(a_price=10)
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
        # QuestInspector allows exactly one outstanding quest request, so a
        # missing answer wedges the whole quest pipeline.
        self.send("q_list", q_id=[], q_types=[])

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

    def cmd_q_status(self, p):
        self.send("q_status", type=int(p.get("q_type", 0)), status=0,
                  name=0, q_type=0)

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
