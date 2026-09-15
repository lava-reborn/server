"""Minimal LAVA Online server: handshake + command logger.

Implements only what lol.core.Session.as requires to get past login:
    C: hello;minor=2;major=0;
    S: hello;...
    C: login;hash=@...@;
    S: cmdAck;res=0;
Everything else is logged so the protocol surface can be filled in incrementally.
"""
import asyncio
import logging
import os

from protocol import FrameReader, decode, frame, Str

HOST = os.environ.get("LAVA_HOST", "0.0.0.0")
PORT = int(os.environ.get("LAVA_PORT", "9775"))
POLICY_PORT = 843

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


class Session:
    def __init__(self, writer, peer):
        self.writer = writer
        self.peer = peer
        self.hash = None
        self.logged_in = False
        # No storage yet: every login starts with an empty roster, so the
        # client goes straight to character creation.
        self.characters = []

    def send(self, name, **params):
        data = frame(name, **params)
        log.info("  S->C  %s", data[:-1].decode("cp1251", "replace"))
        self.writer.write(data)

    def handle(self, name, params):
        log.info("  C->S  %s %s", name, params)
        fn = getattr(self, "cmd_" + name, None)
        if fn:
            fn(params)
        else:
            log.warning("  ??    unimplemented command %r", name)

    # --- implemented commands ---
    def cmd_hello(self, p):
        # Client ignores the params; it only needs a frame named "hello"
        # to arrive within 20s (Session.helloTimeOutFunction).
        self.send("hello", minor=2, major=0)

    def cmd_login(self, p):
        self.hash = p.get("hash")
        # res=0 -> success; client then calls persGen.loadDescription(),
        # which is an HTTP fetch of avatars/list.xml, not a socket command.
        self.logged_in = True
        self.send("cmdAck", res=0)
        self.send_account()

    def send_account(self):
        """Push the account state the client waits for but never asks for.

        PersGenerator.checkFullInfo only opens the character screen once the
        avatar list has loaded AND accountInfo has arrived. Note that
        accountInfo is ignored entirely unless can_create is truthy
        (PersGenerator.accountInfo), so a zero there leaves the client idle
        with no error of any kind.
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
                      sex=pers["sex"], death=0, res=pers["res"])
        self.send("accountInfo",
                  nPers=len(self.characters),
                  can_create=1)

    def cmd_logout(self, p):
        self.writer.close()


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
        log.warning("no permission for port %d; policy served inline only", POLICY_PORT)
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
