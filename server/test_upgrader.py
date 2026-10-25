"""The upgrader's window (upgrader.py): one window for the weapon recipes of
craft.py and the set rungs of setcraft.py.

In process, no sockets -- test_halfa_weaponcraft plays the recipes
through the window on a socket, and test_halfa_setcraft the set rungs' empty
windows since the owner took Вади-Хальфа's set upgrade away (2026-10-09).
This holds what neither of them can: the lists of an upgrader that has both,
an upgrade sent to the service of the thing dragged in, and the window's
state -- its upgrader forgotten the moment the player leaves his room, its
frames still answered with the one refusal the client waits on, and gone
with the close. Генри's rungs are the ones his slice would give with its
window on (setcraft.window_entries), laid into setcraft's cache for the run.

    wsl.exe -e python3 server/test_upgrader.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import craft
import inventory
import items
import rooms
import setcraft
import upgrader
import world

from testkit import check, fails  # noqa: E402


HENRY, JOSEPH, ANYBODY = 93, 7548, 6765      # sets (off); weapons ([Q]); neither
MAUSER_Q, MAUSER_PRECISION = 25666, 43546
EMPTY = {"in_types": [], "out_types": [], "costs": []}
HALFA = setcraft.SLICES["Вади-Хальфа"]

# --- the lists -------------------------------------------------------------------------
check("since 2026-10-09 Генри's window is empty, as anybody's; a weapons master shows his"
      " recipes", (upgrader.lists(HENRY), upgrader.lists(JOSEPH), upgrader.lists(ANYBODY)),
      (EMPTY, craft.upgrader_lists(JOSEPH), EMPTY))
# Генри with his window on, for the rest of the run: his slice's rungs.
setcraft._WINDOWS[HENRY] = setcraft.window_entries(HALFA, HALFA["upgraders"][HENRY])
check("an upgrader of sets with his window on shows his rungs",
      upgrader.lists(HENRY), setcraft.window(HENRY))
# One with both: Жозеф given Генри's rungs for the while.
setcraft._WINDOWS[JOSEPH] = setcraft.entries(HENRY)
try:
    both = upgrader.lists(JOSEPH)
finally:
    del setcraft._WINDOWS[JOSEPH]
weapons, rungs = craft.upgrader_lists(JOSEPH), setcraft.window(HENRY)
check("  ..one with both shows both, the recipes first, the three lists in step",
      both, {k: weapons[k] + rungs[k] for k in EMPTY})
check("  ..and there are some of each", (len(weapons["in_types"]) > 0, len(rungs["in_types"]) > 0),
      (True, True))

# --- which service an upgrade is -----------------------------------------------------------
helm = setcraft.entries(HENRY)[0][0]
check("a gun goes to the recipes, a piece of clothing to the rungs",
      (upgrader.service_of({"root": items.root_of(MAUSER_Q)}),
       upgrader.service_of({"root": items.root_of(helm)})), (craft, setcraft))


# --- the window's state ------------------------------------------------------------------
class Inv:
    def __init__(self, rows):
        self.rows, self.acks = rows, []

    def ack(self, res):
        self.acks.append(res)

    def find(self, oid):
        return self.rows.get(oid)


class Room:
    def __init__(self, npcs):
        self.npcs = npcs

    def npc(self, entity_id):
        return self.npcs.get(entity_id)


class Sess:
    char_id = 1
    npc_session = None

    def __init__(self, room, rows):
        self.room, self.inv = room, Inv(rows)

    def quest_write(self, callback, *args):
        # These cases exercise window routing/refusals, without any writes.
        # Atomic commits/rollback use the real Session in upgrade integrity tests.
        callback(*args)


gun_row = {"root": items.FIRE_ARM, "type_id": MAUSER_Q, "slot": inventory.BAG, "uniq": 1}
helm_row = {"root": items.WEAR, "type_id": helm, "slot": inventory.BAG, "uniq": 2}
market = Room({7: rooms.NPC(0, HENRY, world.UPGRADER), 8: rooms.NPC(0, 1, world.COMMONER)})
sess = Sess(market, {"x1": gun_row, "x2": helm_row})
window = upgrader.Window(sess)
check("a closed window takes no frame", window.ss_upd({"s_status": "1", "obj": "x2"}), False)
window.open({"target": "8"})
check("opened at somebody who is no upgrader: refused (12), nothing open",
      (sess.inv.acks, sess.npc_session, window.ss_upd({"s_status": "0"})), ([12], None, False))
sess.inv.acks = []
window.open({"target": "7"})
check("opened at Генри: 0, the session is the upgrader's, he is the window's master",
      (sess.inv.acks, sess.npc_session, window.master()), ([0], upgrader.SESSION_UPGRADE, HENRY))
sess.inv.acks = []
check("  ..a thing not in the bag: 12, one ack",
      (window.ss_upd({"s_status": "1", "obj": "x9", "param": "1"}), sess.inv.acks), (True, [12]))
sess.inv.acks = []
window.left()
check("left: no master any more, and the room is not his again by coming back to it",
      (window.master(), window.room), (None, None))
for row, oid, code in ((gun_row, "x1", inventory.RES_NOT_FOUND),
                       (helm_row, "x2", inventory.RES_REFUSED)):
    sess.inv.acks = []
    got = window.ss_upd({"s_status": "1", "obj": oid, "param": "1"})
    check("  ..an upgrade of %s sent after: still the window's frame, refused as its service"
          " refuses (%d), one ack" % ("a gun" if row is gun_row else "a helm", code),
          (got, sess.inv.acks), (True, [code]))
sess.inv.acks = []
check("  ..the close: taken, no answer, and the window gone",
      (window.ss_upd({"s_status": "0"}), sess.inv.acks, sess.npc_session,
       window.ss_upd({"s_status": "1", "obj": "x2"})), (True, [], None, False))
window.open({"target": "7"})
window.close()                              # server.Session.windows_gone
check("another window opened: this one takes no frame", window.ss_upd({"s_status": "0"}), False)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("upgrader OK")
