"""Buy a pistol and rounds, wear it, load it -- and find it all after relogin.

Every exchange below is the client's own: frame shapes and the order it
expects answers in come from lol/core/player/PersEquip.as, Trade.as,
StuffManager.as, lol/core/objects/ItemFactory.as and ItemActivator.as.
"""
import os
import threading
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts
import inventory
import items
import progression
from protocol import decode

# A free port: several suites run side by side and a fixed number collides.
_probe = socket.socket()
_probe.bind(("127.0.0.1", 0))
PORT = _probe.getsockname()[1]
_probe.close()

DB = os.path.join(tempfile.mkdtemp(), "test.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB, LAVA_GX="5970", LAVA_GY="1730")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


class Client:
    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
        """Whatever arrives within the window, decoded to (name, params).

        The window is exact: a reload is reported after a timer, and the
        test tells the immediate frames from the delayed one by when they
        arrive, so a recv must never outlast the window.
        """
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [decode(f.decode(ENC)) for f in out if f]

    def names(self, wait=0.5):
        return [f[0] for f in self.frames(wait)]


def named(frames, name):
    return [p for n, p in frames if n == name]


def oids(frame_params):
    return [str(x) for x in frame_params["o_list"]]


PISTOL = inventory.STARTER_PISTOL
ROUNDS = inventory.STARTER_AMMO      # what the kit hands out
STALL_ROUNDS = items.AMMO_9MM[0]     # what the stall sells, a different calibre
PISTOL_SI = items.params_of(PISTOL)
ROUNDS_SI = items.params_of(ROUNDS)
# The gun in the starting bag and the gun bought at the stall are two
# different items: the kit still hands out the nameless pistol
# (inventory.py), while the stall sells the models the wiki named. The stall
# is recognised by the head of its price list, and the pistol bought is the
# first one priced in afro: the head itself may be sold for gold only -- the
# wiki's Маузер C96 (Q) is 0.30 G and heads the list now -- and the afro code
# (1) rightly refuses that one ("gold item for afro" below).
STALL_STOCK = items.stock_for(1200)
STALL_BUY = next(i for i, t in enumerate(STALL_STOCK)
                 if items.root_of(t) == items.FIRE_ARM and items.params_of(t)["cost"] > 0)
STALL_PISTOL = STALL_STOCK[STALL_BUY]
STALL_PISTOL_SI = items.params_of(STALL_PISTOL)


def enter(c, first=False):
    """login, pick or create the character, land in the location; returns
    the frames sent on entry (the inhabitants among them)."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@quarter@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.frames()
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


try:
    c = Client(connect())
    arrival = enter(c, first=True)

    # --- the starting kit, in the layout PersEquip.ss_ack slices ---------
    # slot=11 is what PersEquip.firstRequest sends: bag + hands + clothes.
    c.send("ss_get;target=0;slot=11;")
    got = c.frames()
    check("ss_get answered by ss_ack alone", [n for n, _ in got], ["ss_ack"])
    lst = oids(got[0][1])
    # Six clothes, then the two hands. The kit's pistol starts in the first
    # of them: firing refuses anything that is not in the primary hand, so a
    # starting weapon in the bag is a starting weapon nobody can use.
    check("six clothes come first, empty as 0", lst[:6], ["0"] * 6)
    hand = inventory.parse_oid(lst[6])
    check("the pistol is in the hand, not the bag",
          (hand[1], hand[2]), (PISTOL, items.FIRE_ARM))
    check("the other hand is empty", lst[7], "0")
    check("and the bag holds what is left of the pack", len(lst), 9)
    bag = lst[8:]
    parsed = [inventory.parse_oid(o) for o in bag]
    check("rounds id carries a real ammo type and root 3",
          (parsed[0][1], parsed[0][2]), (ROUNDS, items.AMMO))
    check("the id is the serial in hex with a fixed 6-character tail",
          lst[6], "%x%04x%02x" % (hand[0], PISTOL, items.FIRE_ARM))
    pistol, rounds = lst[6], bag[0]

    # each mask on its own, exact lengths
    c.send("ss_get;target=0;slot=1;")
    check("mask 1 is exactly six entries", len(oids(c.frames()[0][1])), 6)
    c.send("ss_get;target=0;slot=2;")
    check("mask 2 is exactly two entries", len(oids(c.frames()[0][1])), 2)
    c.send("ss_get;target=0;slot=8;")
    check("mask 8 is the bag alone", oids(c.frames()[0][1]), bag)
    c.send("ss_get;target=0;slot=3;")
    check("mask 3 is eight entries", len(oids(c.frames()[0][1])), 8)
    # bank and loot read everything after the first 0 as the session
    c.send("ss_get;slot=24;")
    check("mask 24 ends the bag with a 0 divider",
          oids(c.frames()[0][1]), bag + ["0"])

    # --- dynamic info, one frame per instance ---------------------------
    c.send("ss_get_di;obj=x%s;" % pistol)
    got = c.frames()
    check("a firearm is described by ss_di_firearm", got[0][0], "ss_di_firearm")
    di = got[0][1]
    check("with the same id the list carried", str(di["obj"]), pistol)
    check("fresh from the kit: full durability and empty",
          (di["break"], di["max_break_cur"], di["ammo_count"], di["ammo_type"]),
          (PISTOL_SI["max_break_abs"], PISTOL_SI["max_break_abs"], 0, 0))
    check("cur_mode names an enabled mode", PISTOL_SI["fire_mods"][di["cur_mode"]] != 0, True)
    c.send("ss_get_di;obj=x%s;" % rounds)
    got = c.frames()
    check("a stack is described by ss_di_heap", got[0][0], "ss_di_heap")
    check("with its size", got[0][1]["size"], items.AMMO_PACK)

    # An id nobody owns must still be answered, or the window of five closes.
    c.send("ss_get_di;obj=xdead111c00;")
    check("unknown id still answered", c.names(), ["ss_di_firearm"])

    # --- money before the stall ----------------------------------------
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.frames()
    afro = got[0][1]["afro"]
    check("a new character has 1000 afro", afro, 1000)

    # --- the stall: find the pistol seller placed on arrival ------------
    traders = [(p["id"], p) for n, p in arrival if n == "userInfo_Trader"]
    stall = [i for i, p in traders if p["type_list"][:1] == STALL_STOCK[:1]]
    check("a pistol stall lives on the starting cell", len(stall) > 0, True)
    npc = stall[0]
    price_list = dict(traders)[npc]["type_list"]
    check("the stall sells rounds behind the guns", STALL_ROUNDS in price_list, True)
    ammo_idx = price_list.index(STALL_ROUNDS)

    c.send("ss_create;s_type=1;target=%d;" % npc)
    got = c.frames()
    check("stall opens", got[0], ("cmdAck", {"res": 0}))
    c.send("ss_get;slot=8;")
    check("the stall window sees the bag", oids(c.frames()[0][1]), bag)

    # buy the first pistol: obj is the INDEX in type_list, in hex
    c.send("ss_upd;param=1;obj=x%x;s_status=1;" % STALL_BUY)
    got = c.frames()
    check("purchase: ack, then the item, its details, then the money",
          [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_firearm", "userInfo_Player"])
    check("purchase acknowledged", got[0][1]["res"], 0)
    check("item is placed with status 1", got[1][1]["status"], 1)
    pistol2 = str(got[1][1]["obj"])
    check("a new instance, not the one already owned", pistol2 != pistol, True)
    check("details name the same id", str(got[2][1]["obj"]), pistol2)
    afro -= STALL_PISTOL_SI["cost"]
    check("money is the full record with the price taken off",
          got[3][1]["afro"], afro)

    # buy rounds: param is the number of rounds, priced per pack/sell_num
    c.send("ss_upd;param=30;obj=x%x;s_status=1;" % ammo_idx)
    got = c.frames()
    check("rounds purchase answered in full",
          [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_heap", "userInfo_Player"])
    rounds2 = str(got[1][1]["obj"])
    check("a stack of the number asked for", got[2][1]["size"], 30)
    afro -= -(-ROUNDS_SI["cost"] * 30 // ROUNDS_SI["sell_num"])
    check("charged ceil(cost * n / sell_num)", got[3][1]["afro"], afro)

    # a purchase that does not fit the purse is refused, nothing else sent
    # The dearest item the purse can still afford, not the dearest on the
    # shelf: the stall runs from a 100-afro revolver to a 6400 Desert Eagle
    # and a new character carries 1000, so the dearest of all would never be
    # bought once and there would be nothing to spend down or sell back.
    affordable = [i for i in range(len(price_list))
                  if items.params_of(price_list[i])["cost"] <= afro]
    check("the stall holds something the purse can afford", bool(affordable), True)
    dear = max(affordable,
               key=lambda i: items.params_of(price_list[i])["cost"])
    dear_cost = items.params_of(price_list[dear])["cost"]
    while afro >= dear_cost:
        c.send("ss_upd;param=1;obj=x%x;s_status=1;" % dear)
        got = c.frames()
        afro -= dear_cost
        check("spending down: %d left" % afro, got[-1][1]["afro"], afro)
    c.send("ss_upd;param=1;obj=x%x;s_status=1;" % dear)
    got = c.frames()
    check("no money: refused with a code, and only the ack",
          ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))

    # more rounds than a stack holds is refused too
    c.send("ss_upd;param=%d;obj=x%x;s_status=1;" % (ROUNDS_SI["max_count"] + 1, ammo_idx))
    got = c.frames()
    check("over a stack's max_count: refused", [n for n, _ in got], ["cmdAck"])
    check("with a non-zero code", got[0][1]["res"] != 0, True)

    # Premium items are out of the game: the stall shows none.
    check("no premium item on the shelf",
          [t for t in price_list if items.params_of(t).get("premium")], [])
    # A gold-only item asked for with the afro code (1) costs 0 afro. That
    # used to hand it over for nothing; it has to be refused, money untouched.
    gold_only = [i for i in range(len(price_list))
                 if items.params_of(price_list[i])["cost"] == 0
                 and items.params_of(price_list[i])["g_cost"] > 0]
    check("the stall holds a gold-only item", bool(gold_only), True)
    c.send("ss_upd;param=1;obj=x%x;s_status=1;" % gold_only[0])
    got = c.frames()
    check("gold item for afro: refused, only the ack",
          ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))

    # sell part of the stack: the remainder comes back as ss_di_heap
    c.send("ss_upd;param=10;obj=x%s;s_status=2;" % rounds2)
    got = c.frames()
    check("partial sale: ack, the stack's new size, the money",
          [n for n, _ in got], ["cmdAck", "ss_di_heap", "userInfo_Player"])
    check("twenty rounds remain", got[1][1]["size"], 20)
    # The trader buys at smod, and he says so: the client multiplies the
    # price it draws by the same number (ItemContainer.showCost), so anything
    # else here would be a price the player was never shown.
    afro += max(1, int(ROUNDS_SI["cost"] * 10 / ROUNDS_SI["sell_num"]
                       * inventory.SMOD))
    check("paid floor(cost/sell_num * n * smod)", got[2][1]["afro"], afro)

    # sell the expensive gun back whole: it leaves by ss_obj_status 0. One of
    # those bought spending down, never the first pistol, which may be the
    # same model and has to stay for the swap into the hand below.
    c.send("ss_get;slot=8;")
    now = oids(c.frames()[0][1])
    dear_oid = [o for o in now if inventory.parse_oid(o)[1] == price_list[dear]
                and o != pistol2][0]
    c.send("ss_upd;obj=x%s;s_status=2;" % dear_oid)
    got = c.frames()
    check("whole sale: ack, removal, the money",
          [n for n, _ in got], ["cmdAck", "ss_obj_status", "userInfo_Player"])
    check("removed with status 0", (str(got[1][1]["obj"]), got[1][1]["status"]),
          (dear_oid, 0))
    # Unused, so the durability multiplier is 1 and smod is the whole of the
    # difference: a thing sold the moment it was bought loses three tenths.
    afro += max(1, int(dear_cost * inventory.SMOD))
    check("smod of the price back at full durability", got[2][1]["afro"], afro)

    # closing carries NO acknowledgement: Trade.close registers none
    c.send("ss_upd;obj=x0;s_status=0;")
    check("closing the stall is answered with nothing", c.names(), [])

    # --- wearing: ss_move with the swap the client performs itself -----
    # The kit already put the pistol in the hand, so the verb is exercised
    # the other way first: out to the bag, then back where it belongs.
    c.send("ss_move;obj=x%s;to=2048;from=512;" % pistol)
    got = c.frames()
    check("out of the hand: ack then ss_obj_move",
          [n for n, _ in got], ["cmdAck", "ss_obj_move"])
    check("accepted", got[0][1]["res"], 0)
    c.send("ss_move;obj=x%s;to=512;from=2048;" % pistol)
    got = c.frames()
    check("and back into the primary hand: ack then ss_obj_move",
          [n for n, _ in got], ["cmdAck", "ss_obj_move"])
    check("accepted again", got[0][1]["res"], 0)
    check("the move names both slots",
          (got[1][1]["from"], got[1][1]["to"], str(got[1][1]["obj"])),
          (2048, 512, pistol))
    c.send("ss_get;target=0;slot=2;")
    check("the hand now shows it", oids(c.frames()[0][1]), [pistol, "0"])

    # a stack of rounds does not go on the head
    c.send("ss_move;obj=x%s;to=256;from=2048;" % rounds)
    got = c.frames()
    check("rounds on the head: refused", [n for n, _ in got], ["cmdAck"])
    check("with a code", got[0][1]["res"] != 0, True)

    # the client's picture of "from" must agree with ours
    c.send("ss_move;obj=x%s;to=513;from=2048;" % pistol)
    got = c.frames()
    check("a stale from-slot is refused", got[0][1]["res"] != 0, True)

    # The stall's pistol asks Стрельба N of whoever holds it (the level
    # rule, inventory.py): the character shoots its way up to that first,
    # written into the database between two sessions as test_combat does.
    c.send("logout;")
    c.frames()
    st = accounts.Store(DB)
    cid = st.db.execute("SELECT id FROM characters WHERE name = ?", ("quarter",)).fetchone()["id"]
    ch = progression.Character.load(st, cid)
    lvl = inventory.item_level(STALL_PISTOL)
    ch.skill[progression.SHOOTING] = [lvl, 0, progression.skill_xp_max(lvl)]
    ch.recalc()
    ch.save(st)
    st.close()
    c = Client(connect())
    enter(c)

    # occupied hand: the other pistol goes in, this one comes back to the bag
    c.send("ss_move;obj=x%s;to=512;from=2048;" % pistol2)
    got = c.frames()
    check("swap accepted", got[0][1]["res"], 0)
    c.send("ss_get;target=0;slot=11;")
    lst = oids(c.frames()[0][1])
    check("second pistol in hand, first back in the bag",
          (lst[6], pistol in lst[8:]), (pistol2, True))

    # --- loading -------------------------------------------------------
    # The gun loaded here is the one from the starting kit, which is what
    # PISTOL_SI and ROUNDS describe. The pistol bought at the stall is a
    # different model on a different calibre, and loading 9mm into it is
    # refused with RES_WRONG_AMMO -- correctly, so it is not the gun to
    # test the magazine with.
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
    got = c.frames()
    check("load: ack, then the stack is charged at once",
          [n for n, _ in got], ["cmdAck", "ss_di_heap"])
    check("accepted", got[0][1]["res"], 0)
    clip = PISTOL_SI["clip_size"]
    check("the stack lost a magazine's worth",
          (str(got[1][1]["obj"]), got[1][1]["size"]),
          (rounds, items.AMMO_PACK - clip))
    got = c.frames(wait=PISTOL_SI["reload_time"] / 1000.0 + 1)
    check("after reload_time the gun reports", [n for n, _ in got], ["ss_di_firearm"])
    check("loaded with that type",
          (got[0][1]["ammo_count"], got[0][1]["ammo_type"]), (clip, ROUNDS))

    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, pistol))
    got = c.frames()
    check("a full gun refuses with 15", got[0][1]["res"], inventory.RES_LOADED)

    # --- fire mode -----------------------------------------------------
    off = PISTOL_SI["fire_mods"].index(0)
    c.send("ss_use;target=x%x;obj=x%s;type=64;" % (off, pistol))
    got = c.frames()
    check("a switched-off mode is refused", got[0][1]["res"] != 0, True)
    c.send("ss_use;target=x0;obj=x%s;type=64;" % pistol)
    got = c.frames()
    check("an enabled mode is accepted", got, [("cmdAck", {"res": 0})])

    # --- unloading -----------------------------------------------------
    c.send("ss_use;obj=x%s;type=32;" % pistol)
    got = c.frames()
    check("unload: ack, a new stack, its size, then the gun",
          [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_heap", "ss_di_firearm"])
    ejected = str(got[1][1]["obj"])
    check("the new stack holds the magazine", got[2][1]["size"], clip)
    check("the gun is empty", got[3][1]["ammo_count"], 0)
    c.send("ss_use;obj=x%s;type=32;" % pistol)
    check("unloading an empty gun: 13", c.frames()[0][1]["res"], inventory.RES_NO_AMMO)

    # --- stacks: join, then split, then throw away ---------------------
    # obj is the stack dropped ON, trg the one dragged (StuffManager.joinHeap)
    c.send("ss_heap_c;num=%d;trg=x%s;obj=x%s;" % (clip, ejected, rounds))
    got = c.frames()
    check("join: ack, the receiver's size, the emptied donor removed",
          [n for n, _ in got], ["cmdAck", "ss_di_heap", "ss_obj_status"])
    check("receiver back to a full pack",
          (str(got[1][1]["obj"]), got[1][1]["size"]), (rounds, items.AMMO_PACK))
    check("donor gone", (str(got[2][1]["obj"]), got[2][1]["status"]), (ejected, 0))

    c.send("ss_heap_c;num=5;obj=x%s;" % rounds)
    got = c.frames()
    check("split: ack, the new stack, its size, the old stack's size",
          [n for n, _ in got],
          ["cmdAck", "ss_obj_status", "ss_di_heap", "ss_di_heap"])
    part = str(got[1][1]["obj"])
    check("five went out", (str(got[2][1]["obj"]), got[2][1]["size"]), (part, 5))
    check("the rest stayed",
          (str(got[3][1]["obj"]), got[3][1]["size"]), (rounds, items.AMMO_PACK - 5))

    c.send("ss_use;obj=x%s;type=0;" % part)
    got = c.frames()
    check("throw away: ack then removal",
          [n for n, _ in got], ["cmdAck", "ss_obj_status"])
    check("the thrown stack is the one removed",
          (str(got[1][1]["obj"]), got[1][1]["status"]), (part, 0))

    # --- the window of five: six requests in a row, six answers ---------
    c.send("ss_get;target=0;slot=8;")
    now = oids(c.frames()[0][1])
    asks = (now + [pistol2, "dead111c00", "beef17cc03"])[:6]
    for o in asks:
        c.send("ss_get_di;obj=x%s;" % o)
    got = c.frames(wait=1)
    check("six ss_get_di in a row are all answered",
          len([n for n, _ in got if n.startswith("ss_di_")]), 6)
    check("each with the id it asked for",
          [str(p["obj"]) for _, p in got], asks)

    # combat bits are refused with an ack, not ignored
    c.send("ss_use;target=x100000064;obj=x%s;type=16;" % pistol2)
    got = c.frames()
    check("firing is acknowledged with a refusal",
          ([n for n, _ in got], got[0][1]["res"] != 0), (["cmdAck"], True))

    # --- somebody else's outfit --------------------------------------
    c.send("ss_get;target=777;slot=3;")
    got = c.frames()
    check("another entity's clothes and hands: eight entries",
          len(oids(got[0][1])), 8)

    # --- relogin: everything where it was -------------------------------
    c.send("ss_get;target=0;slot=11;")
    before = oids(c.frames()[0][1])
    c.send("logout;")
    c.frames()
    c = Client(connect())
    enter(c)
    c.send("ss_get;target=0;slot=11;")
    after = oids(c.frames()[0][1])
    check("after relogin the outfit and bag are unchanged", after, before)
    c.send("getInfo;lvl=0;id=0;type=0;")
    check("and so is the money", c.frames()[0][1]["afro"], afro)
    c.send("ss_get_di;obj=x%s;" % pistol2)
    got = c.frames()
    check("the gun's state survived too",
          (got[0][1]["ammo_count"], got[0][1]["cur_mode"]), (0, 0))
    c.send("logout;")
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-6000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("inventory OK")
