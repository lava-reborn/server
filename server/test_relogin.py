"""The same character on a second socket: the first one is put away for good.

The later login wins (rooms.Directory.add), and the older Session is closed
from inside the newer one's selPers. Its socket can still hold frames that
arrived before that -- nothing in asyncio drops a StreamReader's buffer when
the transport closes -- and each of them used to run against the old
Session's own Character: a letter with 2000 afro in it was paid from the old
copy and filed, the new copy's purse (read before the payment) was written
back over it at logout, and the 2000 existed twice. Over the socket that
takes a scripted client and a server stalled in drain(), so this suite drives
two Sessions in process, where the order is exact.

And the load itself: a thing worn in a slot it does not fit -- a row from
before the LVL clothing's slot_type was put right -- goes back to the bag.

    LAVA_RES=.../lava/res python3 server/test_relogin.py
"""
import asyncio
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "relogin.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
from protocol import decode  # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("alice", "secret")
_store.register("bob", "secret")
_store.close()
ALICE = accounts.credential("alice", "secret")
BOB = accounts.credential("bob", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)

LETTERS0 = server.STORE.db.execute("SELECT count(*) c FROM mail").fetchone()["c"]

from testkit import check, fails  # noqa: E402


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)


def db_money(name):
    row = server.STORE.character_by_name(name)
    return row["afro"]


def letters():
    """Letters filed since the suite began: the database may hold others
    (LAVA_DB_URL pointing at an upgraded copy)."""
    return server.STORE.db.execute("SELECT count(*) c FROM mail").fetchone()["c"] - LETTERS0


async def main():
    bob = server.Session(Writer(), "bob")
    run(bob, "login;hash=@%s@;" % BOB)
    run(bob, "newPers;res=1;sex=0;name=@Bob@;")
    run(bob, "actPlayer;")

    old = server.Session(Writer(), "old")
    run(old, "login;hash=@%s@;" % ALICE)
    run(old, "newPers;res=1;sex=0;name=@Alice@;")
    run(old, "actPlayer;")
    ch = old.character()
    ch.afro = 51000
    ch.save(server.STORE)
    # Health lives in the Character alone until the next save: a hit taken
    # just before the relogin is in memory and nowhere else.
    ch.hp = 7

    new = server.Session(Writer(), "new")
    run(new, "login;hash=@%s@;" % ALICE)
    run(new, "selPers;num=0;")
    check("the second login closes the first socket", (old.closed, old.writer.closed),
          (True, True))
    check("and it is closed before the load: the new copy has the old one's health",
          new.character().vitals()["hcur"], 7)
    check("the directory holds the new session", server.ONLINE.by_char.get(new.char_id) is new,
          True)

    # What was still in the old socket's buffer when it was closed.
    sent = len(old.writer.frames)
    for _ in range(3):
        run(old, "sndml;to=@Bob@;subj=@x@;type=0;body=@y@;afro=2000;gold=0;")
    run(old, "userMsg;entry=@/money 90000 0@;group=0;")
    check("the old session answers nothing more", old.writer.frames[sent:], [])
    check("files no letter", letters(), 0)
    check("and pays nothing out of the database purse", db_money("Alice"), 51000)
    check("the new copy's purse is untouched", new.character().afro, 51000)

    run(new, "logout;")
    check("after the new session's logout the purse is what it was", db_money("Alice"), 51000)
    run(bob, "logout;")

    # A helmet worn as a shirt, as a row from before the LVL clothing's
    # slot_type was put right can be, and one on the head where it belongs.
    alice = server.STORE.character_by_name("Alice")["id"]
    helm = next(t for t, (_r, n) in items.catalogue().items() if n == "helm_Set_M_LVL_8_A_mod00")
    as_shirt = server.STORE.create_item(alice, helm, items.WEAR, slot=inventory.CAMO,
                                        brk=100, max_break_cur=100)["uniq"]
    on_head = server.STORE.create_item(alice, helm, items.WEAR, slot=inventory.HEAD,
                                       brk=100, max_break_cur=100)["uniq"]
    # Alice at the helmet's own level (Налетчик, 8), so that the level rule
    # (inventory.over_level_to_bag) has nothing to say about the one on the head.
    ch = progression.Character.load(server.STORE, alice)
    lvl = inventory.item_level(helm)
    ch.skill[progression.SHOOTING] = [lvl, 0, progression.skill_xp_max(lvl)]
    ch.recalc()
    ch.gold = 500
    ch.save(server.STORE)

    # The live session still works as before, and the one that closed on a
    # logout of its own ignores what follows it in the same read.
    solo = server.Session(Writer(), "solo")
    run(solo, "login;hash=@%s@;" % ALICE)
    run(solo, "selPers;num=0;")
    check("loaded: the helmet worn as a shirt is back in the bag, the one on the head stays",
          (server.STORE.item(as_shirt)["slot"], server.STORE.item(on_head)["slot"]),
          (inventory.BAG, inventory.HEAD))
    check("  ..and counts once: its own crit, no second helmet's",
          solo.character().bonus_cp, items.params_of(helm).get("bonus_cp", 0))
    gold0 = solo.character().gold
    run(solo, "sndml;to=@Bob@;subj=@x@;type=0;body=@y@;afro=0;gold=100;")
    check("gold does not go by post (mail.GOLD_BY_POST): no letter, the purse whole",
          (letters(), solo.character().gold, gold0 >= 100), (0, gold0, True))
    run(solo, "sndml;to=@Bob@;subj=@x@;type=0;body=@y@;afro=2000;gold=0;")
    check("an open session still posts a letter", letters(), 1)
    run(solo, "logout;")
    after = db_money("Alice")
    run(solo, "sndml;to=@Bob@;subj=@x@;type=0;body=@y@;afro=2000;gold=0;")
    check("and after its logout nothing more", (letters(), db_money("Alice")), (1, after))


logging.getLogger("lava").disabled = True
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("relogin OK")
