"""Take a quest from an NPC, hand it in, and use the NPC services with no fight.

The sequence is the client's own (lol/core/quests/QuestInspector.as,
lol/core/player/NPC.as, Attendance.as, Rent.as): q_list on entry, q_status per
type the NPC lists, q_si for the description, q_st to take, q_di to fill the
journal, q_co to hand in, q_ca to drop, on_conv for the services. Every quest
request is pipelined one at a time, so each has to be answered by a frame,
and every string id sent has to be in the preload.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"


def free_port():
    """A port nobody is listening on, so parallel runs do not collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()

DB = os.path.join(tempfile.mkdtemp(), "quests.db")
sys.path.insert(0, HERE)
import accounts
import names
import quests
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- the table and its strings, in process --------------------------------
# Any id the server can put on the wire has to be in the ?all=1 preload, or
# the first q_status after login brings the login screen back (PROTOCOL 9).
for q in quests.QUESTS.values():
    for sid in q.string_ids():
        check("quest %d string %d is preloaded" % (q.type, sid),
              names.known(sid), True)
check("the shared empty string is preloaded",
      names.known(quests.EMPTY_STRING_ID), True)
check("quest ids sit in their own range",
      all(2_000_000 <= i < 3_000_000 for q in quests.QUESTS.values()
          for i in q.strings()), True)
doc = names.document()
check("the empty string is served as an element, not dropped",
      "<s id='5000000'></s>" in doc, True)
# Markup inside a text is XML-escaped: the client unescapes entities, and a
# raw <hint> would break the parse of the whole document.
check("hint markup is escaped in texts.xml",
      "&lt;hint&gt;" in doc and "<hint>" not in doc, True)
check("client macros survive untouched", "%имя%" in doc, True)
check("give order follows the table", quests.given_by(652), [1, 5])
check("take list by NPC type", quests.taken_by(2424), [1])
# QuestInterface numbers reward icons n-1-i, so obj_idx counts from the end.
q4 = quests.get(4)
check("reward index counts from the end", q4.reward_item(0), (11782, 1))
check("delivery with no item completes on take",
      quests.get(1).is_complete(quests.get(1).fresh_progress()), True)
check("kill quest does not", quests.get(5).is_complete(
    quests.get(5).fresh_progress()), False)


env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# The server logs every frame, and this replay enters three locations, so its
# output outgrows a pipe nobody reads; a full pipe blocks the server mid-reply
# and every window after that sees nothing. Drain it as it comes.
import threading
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


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
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]

    def names(self, wait=0.5):
        return [f.split(";")[0] for f in self.frames(wait)]


def field(frame, key):
    """Value of key=...; in a frame, as text."""
    return frame.split(key + "=")[1].split(";")[0]


def keys(frame):
    return [part.split("=")[0] for part in frame.split(";")[1:] if part]


def npc_ids(got):
    """type_id -> entity id, from the userInfo_* frames of a population."""
    out = {}
    for f in got:
        if f.startswith("userInfo"):
            out[int(field(f, "name"))] = int(field(f, "id"))
    return out


def enter(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@polestvr@;")
    c.frames()
    c.send("actPlayer;")
    c.frames()
    got = enter(c)
    npc = npc_ids(got)
    TECHNOGEEK, AARON, SHIHAB, GRINDSTONE = npc[652], npc[2424], npc[653], npc[2279]

    # --- an empty log, and the daily counter pushed on entry ----------------
    # q_sys is the server's to send; the client never asks for it.
    check("daily counter pushed with the location",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=10;"])
    c.send("q_list;")
    got = c.frames()
    check("log is empty", got, ["q_list;q_id=|;q_types=|;"])

    # --- what the NPC offers -------------------------------------------------
    c.send("getInfo;lvl=0;id=%d;type=1;" % TECHNOGEEK)
    info = c.frames()[0]
    check("the technogeek gives two quests", field(info, "give_quests"), "|1|5|")
    check("and takes one back", field(info, "take_quests"), "|5|")
    c.send("getInfo;lvl=0;id=%d;type=1;" % AARON)
    info = c.frames()[0]
    check("Aaron takes the delivery", field(info, "take_quests"), "|1|")

    # The client asks q_status for every listed type; status decides whether
    # it appears at all, and name is a string id.
    c.send("q_status;q_type=1;")
    got = c.frames()
    check("delivery is available", got[0],
          "q_status;type=1;status=1;name=%d;q_type=0;"
          % quests.get(1).string_id(quests.NAME))
    c.send("q_status;q_type=6;")
    check("a quest above the player's level is not",
          "status=0;" in c.frames()[0], True)
    c.send("q_status;q_type=999;")
    got = c.frames()
    check("an unknown type is still answered", got[0].split(";")[0], "q_status")
    check("as unavailable", "status=0;" in got[0], True)

    # --- static description: every key, every kind --------------------------
    COMMON = ["type", "repeatable", "party_size", "loc", "finish_loc", "level",
              "rew_obj", "rew_afro", "rew_gold", "rew_loc", "num_rew_obj",
              "need_quest", "q_type", "name", "start_desc", "notfinish_desc",
              "finish_desc"]
    c.send("q_si;q_type=1;")
    si = c.frames()[0]
    check("delivery described by kind", si.split(";")[0], "q_si_del_obj")
    check("with every common key", keys(si), COMMON + ["obj"])
    check("four string ids, none blank",
          all(field(si, k).isdigit() for k in
              ("name", "start_desc", "notfinish_desc", "finish_desc")), True)
    check("empty reward list encoded as a list", "rew_obj=|;" in si, True)

    c.send("q_si;q_type=4;")
    si = c.frames()[0]
    check("bring quest described by kind", si.split(";")[0], "q_si_bring_l_obj")
    want = COMMON[:]
    for i in range(1, 7):
        want += ["obj_%d" % i, "obj_num_%d" % i, "mobs_%d" % i]
    check("all six object slots present", keys(si), want)
    check("first slot is the certificate", field(si, "obj_1"), "3742")
    check("unused slots are zero", field(si, "obj_6"), "0")
    check("unused mob lists are empty lists", "mobs_6=|;" in si, True)
    check("reward item listed", field(si, "rew_obj"), "|11782|")

    c.send("q_si;q_type=5;")
    si = c.frames()[0]
    check("kill quest described by kind", si.split(";")[0], "q_si_kill_mobs")
    check("with its targets", keys(si), COMMON + ["mobs_kill", "num_kill"])
    check("three dogs", field(si, "num_kill"), "|3|")

    c.send("q_si;q_type=999;")
    got = c.frames()
    check("an unknown type gets a full stub frame",
          got and got[0].startswith("q_si_") and keys(got[0]) == COMMON + ["obj"],
          True)

    # --- taking: q_idx is a position in give_quests -------------------------
    c.send("q_st;mob=%d;q_idx=0;" % TECHNOGEEK)
    got = c.frames()
    check("take is acknowledged, then the instance pushed",
          [f.split(";")[0] for f in got], ["cmdAck", "q_di_del_obj"])
    check("acknowledged as taken", got[0], "cmdAck;res=0;")
    # q_type in q_di is the quest's type, complete because there is nothing
    # to carry: a delivery with obj=0 is a message.
    check("instance is complete at once", got[1],
          "q_di_del_obj;q_id=1;q_type=1;complete=1;obj=1;")

    c.send("q_list;")
    got = c.frames()
    check("the log now holds it", got[0], "q_list;q_id=|1|;q_types=|1|;")

    c.send("q_di;q_id=1;")
    check("instance re-described on request", c.frames()[0],
          "q_di_del_obj;q_id=1;q_type=1;complete=1;obj=1;")
    c.send("q_di;q_id=999;")
    got = c.frames()
    check("an unknown instance is answered as incomplete",
          got and got[0].startswith("q_di_") and "complete=0;" in got[0], True)

    c.send("q_st;mob=%d;q_idx=0;" % TECHNOGEEK)
    got = c.frames()
    check("taking it twice is refused with one ack",
          [f.split(";")[0] for f in got], ["cmdAck"])
    check("and not as success", "res=0;" in got[0], False)
    c.send("q_st;mob=%d;q_idx=7;" % TECHNOGEEK)
    got = c.frames()
    check("an index past the list is refused",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)

    # --- handing in ----------------------------------------------------------
    c.send("q_co;obj_idx=0;mob=%d;q_id=1;" % TECHNOGEEK)
    got = c.frames()
    check("the giver does not take it back",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)
    c.send("q_co;obj_idx=0;mob=%d;q_id=1;" % AARON)
    got = c.frames()
    check("reward lands before the ack",
          [f.split(";")[0] for f in got], ["userInfo_Player", "cmdAck"])
    check("purse credited", field(got[0], "afro"), "1050")
    check("hand-in acknowledged", got[1], "cmdAck;res=0;")

    c.send("q_list;")
    check("log empty again", c.frames()[0], "q_list;q_id=|;q_types=|;")
    # The client re-asks every NPC's types after a hand-in.
    c.send("q_status;q_type=1;")
    check("a one-off quest is gone for good", "status=0;" in c.frames()[0], True)

    # --- a quest with real work: taken, refused early, dropped ---------------
    c.send("q_st;mob=%d;q_idx=1;" % TECHNOGEEK)
    got = c.frames()
    check("second offer is the dogs", got[1],
          "q_di_kill_mobs;q_id=2;q_type=5;complete=0;kill_num=|0|;")
    c.send("q_co;obj_idx=0;mob=%d;q_id=2;" % TECHNOGEEK)
    got = c.frames()
    check("an unfinished quest cannot be handed in",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)
    c.send("q_status;q_type=5;")
    check("but stays available while carried", "status=1;" in c.frames()[0], True)
    c.send("q_ca;q_id=2;")
    check("dropping is acknowledged", c.frames()[0], "cmdAck;res=0;")
    c.send("q_ca;q_id=2;")
    got = c.frames()
    check("dropping twice is refused",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)
    c.send("q_list;")
    check("dropped quest leaves the log", c.frames()[0], "q_list;q_id=|;q_types=|;")

    # --- a repeatable one survives a relogin -------------------------------
    c.send("q_st;mob=%d;q_idx=0;" % AARON)
    got = c.frames()
    check("Aaron's errand taken", got[1],
          "q_di_del_obj;q_id=3;q_type=2;complete=1;obj=1;")
    c.send("logout;")
    c.frames()

    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("selPers;num=0;")
    c.frames()
    got = enter(c)
    npc = npc_ids(got)
    AARON, SHIHAB = npc[2424], npc[653]
    check("one daily hand-in used, remembered across logins",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=9;"])
    c.send("q_list;")
    check("the log is kept across logins", c.frames()[0],
          "q_list;q_id=|3|;q_types=|2|;")
    c.send("q_co;obj_idx=0;mob=%d;q_id=3;" % SHIHAB)
    got = c.frames()
    check("handed to the lessor", [f.split(";")[0] for f in got],
          ["userInfo_Player", "cmdAck"])
    check("purse credited again", field(got[0], "afro"), "1070")
    c.send("q_status;q_type=2;")
    check("a repeatable quest stays available", "status=1;" in c.frames()[0], True)

    # --- services without a fight -------------------------------------------
    c.send("on_conv;mob=%d;op=0;" % AARON)
    check("registering home is acknowledged", c.frames()[0], "cmdAck;res=0;")
    store = accounts.Store(DB)
    home = store.db.execute("SELECT home_loc FROM characters").fetchone()[0]
    store.close()
    check("home is this location", home, 102)
    c.send("on_conv;p2=1;p1=1;mob=%d;op=2;" % SHIHAB)
    got = c.frames()
    check("renting is refused, not ignored",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)
    c.send("on_conv;mob=%d;op=1;" % AARON)
    got = c.frames()
    check("a commoner does not heal",
          [f.split(";")[0] for f in got] == ["cmdAck"] and "res=0;" not in got[0],
          True)

    # A medic lives at the station next door.
    c.send("userMsg;entry=@/goto 37@;group=0;")
    c.frames()
    got = enter(c)
    check("two daily hand-ins used",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=8;"])
    medic = [f for f in got if f.startswith("lch") and "rtype=5;" in f]
    check("the station has a medic", len(medic) > 0, True)
    MEDIC = int(field(medic[0], "newUser"))
    c.send("on_conv;mob=%d;op=1;" % MEDIC)
    got = c.frames()
    check("healing: purse, bars, then the ack",
          [f.split(";")[0] for f in got], ["userInfo_Player", "usrUp", "cmdAck"])
    check("fee taken", field(got[0], "afro"), "1060")
    check("healed to full", "hcur=100;hmax=100;" in got[1], True)
    check("healing acknowledged", got[2], "cmdAck;res=0;")

    c.send("logout;")
except Exception:
    import traceback
    fails.append("test aborted:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-1500:])
    elif fails:
        fails.append("server log tail:\n" + out[-3000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("quests OK")
