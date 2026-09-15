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

import world
from protocol import FrameReader, decode, frame, Str

HOST = os.environ.get("LAVA_HOST", "0.0.0.0")
PORT = int(os.environ.get("LAVA_PORT", "9775"))
POLICY_PORT = 843
NEW_CHAR = os.environ.get("LAVA_NEWCHAR") == "1"

# "Черный рынок Вади-Хальфы": peaceful (war="0", so walking costs no action
# points) and already populated in its own XML with 21 traders, an upgrader,
# a lessor and several commoners.
START_LOC = int(os.environ.get("LAVA_LOC", "102"))

# Portrait and body come from two different fields of the same avatars/list.xml
# row and have to be taken together: res selects the portrait, sex selects the
# body, because PersInfo.set sex assigns persType as a side effect. Row 0 is
# the one the creation screen offers first.
AVATARS = world.avatars()
START_AVATAR = int(os.environ.get("LAVA_AVATAR", "0"))

LOCATION = world.Location(START_LOC)
MOB_TYPES = world.mob_types()


def default_character():
    res, sex = AVATARS[START_AVATAR % len(AVATARS)]
    return {"name": "polestvr", "sex": sex, "res": res}
# Entity ids: 0 is always the player, so anything placed in the world starts
# above that.
FIRST_NPC_ID = 100

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
        # With a character already on the account and can_create=0, the client
        # selects slot 0 by itself and walks straight into the world, which
        # makes every test run reproducible without clicking through creation.
        # LAVA_NEWCHAR=1 starts with an empty roster and shows that screen.
        self.characters = [] if NEW_CHAR else [default_character()]
        self.active = None
        self.pos = LOCATION.entry_cell()
        # entity id -> (cell, type_id, rtype) for everything placed
        self.npcs = {}

    # --- plumbing --------------------------------------------------------
    def send(self, *_cmd, **params):
        """Send one frame. The command name is positional, because several
        commands carry a parameter literally called "name"."""
        data = frame(_cmd[0], **params)
        log.info("  S->C  %s", data[:-1].decode("cp1251", "replace"))
        self.writer.write(data)

    def handle(self, cmd, params):
        log.info("  C->S  %s %s", cmd, params)
        fn = getattr(self, "cmd_" + cmd, None)
        if not fn:
            log.warning("  ??    unimplemented command %r", cmd)
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
        self.hash = p.get("hash")
        self.logged_in = True
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
        for i, pers in enumerate(self.characters):
            self.send("persInfo", num=i, name=Str(pers["name"]),
                      sex=pers["sex"], death=0,
                      res=Str(str(pers["res"])))
        # can_create must be falsy for the auto-select path: PersGenerator
        # opens the creation screen whenever it is truthy, regardless of how
        # many characters the account already has.
        self.send("accountInfo", nPers=len(self.characters),
                  can_create=1 if not self.characters else 0)

    def cmd_logout(self, p):
        self.writer.close()

    # --- character -------------------------------------------------------
    def cmd_newPers(self, p):
        self.characters = [{"name": p.get("name", "Noname"),
                            "sex": p.get("sex", 0),
                            "res": p.get("res", AVATARS[0][0])}]
        self.active = self.characters[0]
        # The client plays its intro after this, then sends actPlayer itself.
        self.send("cmdAck", res=0)

    def cmd_selPers(self, p):
        # Deliberately no cmdAck: PersGenerator does not register a handler for
        # one, so replying here would be consumed by the next command's.
        idx = int(p.get("num", 0))
        if idx < len(self.characters):
            self.active = self.characters[idx]
        self.enter_location()

    def cmd_actPlayer(self, p):
        self.send("cmdAck", res=0)
        self.enter_location()

    # --- world -----------------------------------------------------------
    def enter_location(self):
        # ie != 1 means the client must confirm with lenter;accept=1 once it
        # has finished loading the location's XML and artwork.
        self.send("lcall", id=LOCATION.id, ws=LOCATION.war, ie=0,
                  g_id=LOCATION.id)

    def cmd_lenter(self, p):
        self.send("cmdAck", res=0)
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
        for i, (cell, type_id) in enumerate(LOCATION.spawns):
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
        log.info("  ..    placed %d inhabitants in %s",
                 len(self.npcs), LOCATION.title)

    def cmd_chWorld(self, p):
        self.send("cmdAck", res=0)

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
            # An empty stock still opens the trade window; goods come later.
            params.update(can_trade=1, can_repair=1, type_list=[],
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

    def cmd_ss_get(self, p):
        # Answer even when empty; ItemFactory pipelines these and stops
        # issuing new ones until each outstanding request comes back.
        self.send("ss_ack", o_list=[])

    def cmd_q_list(self, p):
        # QuestInspector allows exactly one outstanding quest request, so a
        # missing answer wedges the whole quest pipeline.
        self.send("q_list", q_id=[], q_types=[])

    def cmd_q_status(self, p):
        self.send("q_status", type=int(p.get("q_type", 0)), status=0,
                  name=0, q_type=0)

    def cmd_moveTo(self, p):
        """Echo the path back; the client renders no step until we do.

        Location.movePlayer only records the destination and sends the frame.
        The walk animation starts solely from a server userMove, including for
        the player who asked.
        """
        path = p.get("path")
        if not path:
            return
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
        writer.close()


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
