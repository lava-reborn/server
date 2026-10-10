"""Disconnected bodies remain vulnerable and reconnect without resetting combat.

Issue #65: 900 seconds on war ground, immediate removal elsewhere. The wire
exchange follows PersGenerator.selPers and Master.lenter; no extra cmdAck.
Real Sessions exercise death, timers and AI in process, then handle_client
runs behind a real TCP listener to check transport replacement and EOF.
"""
import asyncio
import logging
import os
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.TemporaryDirectory(prefix="combat-linger-")
os.environ["LAVA_DB"] = os.path.join(TMP.name, "linger.db")
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import server  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, fails  # noqa: E402


class Writer:
    def __init__(self):
        self.frames = []
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True


def create(name, loc_id=100):
    server.STORE.register(name, "secret")
    sess = server.Session(Writer(), name)
    sess.handle("login", dict(hash=accounts.credential(name, "secret")))
    sess.handle("newPers", dict(res=1, sex=0, name=name))
    sess.handle("actPlayer", {})
    sess.loc = world.location(loc_id)
    sess.pos = sess.loc.entry_cell()
    sess.enter_location()
    sess.handle("lenter", dict(accept=1))
    return sess


async def in_process():
    # --- the rules, in process --------------------------------------------
    check("default body lifetime is fifteen minutes", server.COMBAT_LINGER, 900)
    peace = create("Peace", 181)
    peace.close()
    check("peaceful logout immediately removes the player",
          (peace.room, peace.linger, peace.writer.closed), (None, None, True))
    for loc in (626, 1025, 1048):
        sess = create("Exempt%d" % loc, loc)
        sess.close()
        check("production or training location %d leaves no body" % loc,
              (sess.room, sess.linger), (None, None))

    body = create("Body")
    room, fighter = body.room, body.combat
    witness = create("Witness")
    server.PARTIES.invite(witness, body.pid)
    server.PARTIES.answer(body, True)
    party = server.PARTIES.party_of(witness)
    witness.online_counter = True
    witness.online_names = True
    witness.writer.frames.clear()
    fighter.ap = 3
    fighter.last_hit = combat.now()
    pending = asyncio.get_running_loop().call_later(30, lambda: None)
    fighter.strike = pending
    start = body.pos
    body._pos = start + 1
    body.walk = ([start, start + 1], asyncio.get_running_loop().time())
    body.close()
    timer = body.linger
    check("logout keeps one vulnerable body and closes its socket",
          (body in room.players, fighter.present(fighter.rc), body.closed,
           body.writer.closed, timer is not None), (True, True, True, True, True))
    check("pending attacks are cancelled on disconnect", pending.cancelled(), True)
    check("the party retains its offline member",
          (body.char_id in party.members, body.char_id in party.present), (True, False))
    check("disconnect stops a walk at its current cell", (body.pos, body.walk),
          (start, None))
    check("observers keep the body and get a valid stationary walk",
          [(n, p) for n, p in witness.writer.frames
           if n == "userMove" or (n == "lch" and "lostUser" in p)],
          [("userMove", dict(id=body.pid, path=[start, start]))])
    check("the disconnected body leaves the online counter",
          [p["count"] for n, p in witness.writer.frames if n == "online"], [1])
    check("the default timeout is scheduled fifteen minutes ahead",
          899 < timer.when() - asyncio.get_running_loop().time() <= 900, True)
    body.close()
    check("duplicate close does not extend the lifetime", body.linger is timer, True)
    before = body.pos
    body.handle("moveTo", dict(path=[before, before + 1]))
    check("buffered commands cannot move a disconnected body", body.pos, before)

    # A real mob's hit and death path, with the hit roll controlled so a
    # miss cannot turn a broken implementation green.
    rc = fighter.rc
    mob = next(m for m in rc.mobs.values() if m.stats.can_attack and not m.stats.ranged)
    body.pos = next(c for c in range(room.loc.width * room.loc.height)
                    if mobs.adjacent(mob.cell, c, room.loc))
    body.character().hp = body.character().hp_max
    body.character().sp = 0
    hp = body.character().vitals()["hcur"]
    rc.aggro(mob, fighter)
    with patch.object(combat, "roll", return_value=True):
        rc.mob_strike(mob, fighter)
    check("a mob still damages the disconnected body",
          body.character().vitals()["hcur"] < hp, True)
    check("the mob keeps the same target", mob.target is fighter, True)

    incoming = server.Session(Writer(), "reconnect")
    incoming.handle("login", dict(hash=accounts.credential("Body", "secret")))
    hp = body.character().vitals()["hcur"]
    ap, last_hit = fighter.ap, fighter.last_hit
    fighter.foes.add(9999999)  # a hostile player who left during the disconnect
    incoming.handle("selPers", dict(num=0))
    check("relogin takes over the original session and fighter",
          (incoming.resumed is body, body.combat is fighter, timer.cancelled(),
           mob.target is fighter, body in room.players), (True,) * 5)
    body.handle("lenter", dict(accept=1))
    check("relogin preserves health, AP and the exit timer",
          (body.character().vitals()["hcur"], fighter.ap, fighter.last_hit),
          (hp, ap, last_hit))
    check("relogin restores the party seat", body.char_id in party.present, True)
    check("the snapshot does not name enemies absent from the room",
          any(n == "lch" and p.get("enemy") == 9999999
              for n, p in body.writer.frames), False)
    check("relogin sends no extra acknowledgement",
          [p for n, p in body.writer.frames if n == "cmdAck"], [dict(res=0)])
    body.close()
    body.character().hp = 1
    body.character().sp = 0
    with patch.object(combat, "roll", return_value=True):
        rc.mob_strike(mob, fighter)
    check("death removes the body and cancels its timeout",
          (fighter.dead, body.room, body.linger), (True, None, None))
    check("death and zero health persist",
          (server.STORE.character(body.char_id)["death"],
           server.STORE.character(body.char_id)["hp"]), (1, 0))
    check("the witness sees death before the body disappears",
          [(n, next(iter(p))) for n, p in witness.writer.frames
           if n == "lch" and (p.get("dead") == body.pid or
                              p.get("lostUser") == body.pid)],
          [("lch", "dead"), ("lch", "lostUser")])

    # PvP uses the same death path, and must create its trophy before the
    # victim loses its room. The ordinary live PvP suite tests attack gates.
    victim = create("PvpBody")
    victim.close()
    killer = witness.combat
    killer.rc.kill(victim.combat, killer)
    trophies = [r for r in server.STORE.items_of(combat.LOOT_OWNER)
                if r["root"] == items.TROPHY]
    check("a disconnected PvP victim still leaves a trophy", len(trophies), 1)
    check("PvP death removes the body", victim.room, None)
    witness.close(force=True)

    loading = create("Loading")
    loading.close()
    incoming = server.Session(Writer(), "loading")
    incoming.handle("login", dict(hash=accounts.credential("Loading", "secret")))
    incoming.handle("selPers", dict(num=0))
    loading.combat.rc.kill(loading.combat, None)
    loading.writer.frames.clear()
    loading.handle("lenter", dict(accept=1))
    check("death during reconnect loading reaches the new client",
          any(n == "lch" and p.get("dead") == 0
              for n, p in loading.writer.frames), True)
    loading.close()
    check("an already dead player leaves immediately", loading.room, None)

    with patch.object(server, "COMBAT_LINGER", 0.05):
        timed = create("Timed")
        timed.close()
        money = timed.character().afro
        server.apply_admin_action(dict(char_id=timed.char_id, kind="money",
                                       args_json='{"afro": 123}'))
        await asyncio.sleep(0.1)
        check("timeout removes the body from room and directory",
              (timed.room, server.ONLINE.by_char.get(timed.char_id)), (None, None))
        check("body expiry does not overwrite an admin payment",
              server.STORE.character(timed.char_id)["afro"], money + 123)
    stopped = create("Stopped")
    stopped.close()
    stopped.shutdown()
    check("server shutdown immediately saves and removes a body",
          (stopped.room, stopped.linger), (None, None))


class Client:
    async def connect(self, port):
        self.reader, self.writer = await asyncio.open_connection("127.0.0.1", port)
        return self

    async def send(self, text):
        self.writer.write(text.encode("utf-8") + b"\0")
        await self.writer.drain()

    async def until(self, name):
        out = []
        async with asyncio.timeout(5):
            while True:
                raw = await self.reader.readuntil(b"\0")
                decoded = decode(raw[:-1].decode("utf-8"))
                out.append(decoded)
                if decoded[0] == name:
                    return out


async def wire():
    # --- real sockets: EOF, logout and a second socket --------------------
    fixture = create("Socket")
    fixture.close(force=True)
    listener = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1]
    clients = []

    async def login():
        client = await Client().connect(port)
        clients.append(client)
        await client.send("login;hash=@%s@;" % accounts.credential("Socket", "secret"))
        await client.until("accountInfo")
        await client.send("selPers;num=0;")
        await client.until("lcall")
        await client.send("lenter;accept=1;")
        await client.until("e_list")
        return client

    try:
        first = await login()
        body = server.ONLINE.by_char[fixture.char_id]
        room = body.room
        first.writer.close()
        await first.writer.wait_closed()
        for _ in range(100):
            if body.linger is not None:
                break
            await asyncio.sleep(0.01)
        check("EOF retains a body in the real handler",
              (body.linger is not None, body in room.players), (True, True))
        second = await login()
        check("new socket adopts that exact body",
              server.ONLINE.by_char[fixture.char_id] is body, True)
        # Replace an active transport too: its finally must not close the
        # newly adopted socket or restart its body timeout.
        third = await login()
        await third.send("rp_get_info;")
        got = await third.until("rp_info")
        check("old transport cleanup does not close the replacement",
              (body.closed, body.linger, any(n == "rp_info" for n, _ in got)),
              (False, None, True))
        await third.send("logout;")
        for _ in range(100):
            if body.linger is not None:
                break
            await asyncio.sleep(0.01)
        check("explicit logout also retains exactly one body",
              (body.linger is not None,
               sum(s.char_id == body.char_id for s in room.players)), (True, 1))
        await server.shutdown([listener])
        check("global shutdown also finds bodies with no connection handler",
              (body.room, body.linger, body.char_id in server.ONLINE.by_char),
              (None, None, False))
    finally:
        for client in clients:
            client.writer.close()
        listener.close()
        await listener.wait_closed()
        for sess in list(server.ONLINE):
            sess.close(force=True)


async def main():
    await in_process()
    await wire()


logging.getLogger("lava").disabled = True
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()
    TMP.cleanup()

if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("combat linger OK")
