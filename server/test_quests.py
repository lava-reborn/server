"""Take a quest from an NPC, hand it in, and use the NPC services with no fight.

The sequence is the client's own (lol/core/quests/QuestInspector.as,
lol/core/player/NPC.as, Attendance.as, Rent.as): q_list on entry, q_status per
type the NPC lists, q_si for the description, q_st to take, q_di to fill the
journal, q_co to hand in, q_ca to drop, on_conv for the services. Every quest
request is pipelined one at a time, so each has to be answered by a frame,
and every string id sent has to be in the preload.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# The black market's placeholder quests (Техногик 652, Аарон 2424, Шихаб
# 653, Точильный камень 2279) as they stood in data/quests.json until
# 2026-09-28, when they left it (the plan's correction а: texts of this
# server's, no row of the original, 3 paying half an ounce for a word). The
# suite plays the engine on them still, as fixtures put in front of the real
# table -- for this process and the server alike (quests.quests_path,
# LAVA_QUESTS) -- so their givers list them first.
BLACK_MARKET = [
    dict(type=1,
         kind="del_obj",
         name="Посылка для Аарона",
         start=("Слушай, %имя%, выручи. Аарон ждёт от меня расписку, а я от верстака "
                "отойти не могу. <hint>Передай ему на словах</hint>, что всё готово, — "
                "он тут же, на рынке, у сейфа."),
         notfinish="Ты от Техногика? Он обещал расписку... Так что передать-то велел?",
         finish=("Значит, всё готово? Хорошо. Передай Техногику, что я доволен. А это "
                 "тебе за ноги — %sex?сам:сама% понимаешь, лишними не будут."),
         give=[652],
         take=[2424],
         obj=0,
         rew_afro=50,
         rew_gold=0,
         repeatable=0,
         level=0,
         q_type=0),
    dict(type=2,
         kind="del_obj",
         name="Весточка Шихабу",
         start=("Раз уж ты бегаешь по рынку — скажи Шихабу, что его верблюды "
                "застрахованы. Он у загона, там, где сдают транспорт."),
         notfinish="От Аарона? Ну и что там с моими верблюдами?",
         finish="Застрахованы, говоришь? Хвала небесам. Держи за труды.",
         give=[2424],
         take=[653],
         obj=0,
         rew_afro=20,
         rew_gold=0,
         repeatable=1,
         level=0,
         q_type=0),
    dict(type=3,
         kind="del_obj",
         name="Слово для Точильного камня",
         start=("Передай Точильному камню, что ослик Панург снова хромает — пусть "
                "посмотрит подковы. Он у своего станка, за оружейными рядами."),
         notfinish="Что там у Шихаба?",
         finish="Опять Панург? Ладно, зайду. Вот тебе за беготню — щепотка золота.",
         give=[653],
         take=[2279],
         obj=0,
         rew_afro=0,
         rew_gold=50,
         repeatable=1,
         level=0,
         q_type=0),
    dict(type=5,
         kind="kill_mobs",
         name="Голодные собаки",
         start=("Голодные собаки таскают со склада всё, что плохо лежит. Отгони их — "
                "трёх хватит, чтобы остальные поумнели. Ищи за стеной, в пустоши."),
         notfinish="Собаки всё ещё здесь. Три штуки, %имя%, я считал.",
         finish="Тише стало. Держи, заслужил%sex?:а%.",
         give=[652],
         take=[652],
         mobs_kill=[82],
         num_kill=[3],
         rew_afro=40,
         rew_gold=0,
         repeatable=1,
         level=0,
         q_type=0),
    dict(type=6,
         kind="del_obj",
         name="Заказ для бывалого",
         start="Есть заказ для того, кто умеет держать нож. Новичкам не предлагаю.",
         notfinish="Ну что, справился?",
         finish="Чисто сработано. Держи.",
         give=[2279],
         take=[2279],
         obj=0,
         rew_afro=200,
         rew_gold=0,
         repeatable=1,
         level=3,
         q_type=0),
]

with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"), encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
_TABLE["quests"] = BLACK_MARKET + _TABLE["quests"]
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as _fh:
    json.dump(_TABLE, _fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE


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

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- the table and its strings, in process --------------------------------
# Any id the server can put on the wire has to be in the ?all=1 preload, or
# the first q_status after login brings the login screen back (PROTOCOL 9).
for q in quests.QUESTS.values():
    for sid in q.string_ids():
        check("quest %d string %d is preloaded" % (q.type, sid),
              names.known(sid), True)
check("the shared empty string is preloaded",
      names.known(quests.EMPTY_STRING_ID), True)
# The generated companions (data/questgen_*.json) load with the real table
# and never with a table a suite names; data/quests_wiki.json is not one.
_companions = quests.companion_paths(quests.PATH)
check("companions are the questgen_ files beside the table, none of them quests_wiki",
      all(os.path.basename(p).startswith("questgen_") for p in _companions), True)
check("  ..and every row of the table and its companions is loaded",
      sorted(r["type"] for r in quests.table_rows(quests.PATH)),
      sorted(quests.load(quests.PATH)))
check("  ..a table named by path stands alone", quests.companion_paths(DB), [])
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
# A daily quest says so in its start, in the original's words, whether the
# row carried the note (the original's dailies) or the server appended it
# (quests._say_per_day); and the count is declined as the note declines it.
check("every per_day quest says «не чаще N раз в сутки» in its start",
      [q.type for q in quests.QUESTS.values() if q.per_day
       and ("не чаще %s в сутки" % quests.per_day_times(q.per_day))
       not in q.texts[quests.START]], [])
check("  ..and a one-off or a plain repeatable one does not",
      [q.type for q in quests.QUESTS.values() if not q.per_day
       and "в сутки" in q.texts[quests.START]], [])
check("  ..declined: 1 раза, 3 раз, 11 раз, 21 раза",
      [quests.per_day_times(n) for n in (1, 3, 11, 21)],
      ["1 раза", "3 раз", "11 раз", "21 раза"])
check("give order follows the table", quests.given_by(652), [1, 5])
check("take list by NPC type", quests.taken_by(2424), [1])
# Quest.createRewardItems reverses the wire list via AS2 for..in + push.
# QuestInterface.buildRewardItems then assigns n-1-i to those prototypes.
q4 = quests.get(4)
check("reward index zero selects the first part", q4.reward_item(0), (5047, 1))
for q in (quests.get(52), q4):
    prototypes = list(reversed(q.rew_obj))
    for i, item in enumerate(prototypes):
        wire_index = len(prototypes) - 1 - i
        check("quest %d: selecting icon %d pays the item shown" % (q.type, item),
              q.reward_item(wire_index), (item, 1))
    check("quest %d: indexes outside the choice are refused" % q.type,
          [q.reward_item(i) for i in (-1, len(prototypes))], [None, None])
check("delivery with no item completes on take",
      quests.get(1).is_complete(quests.get(1).fresh_progress()), True)
check("kill quest does not", quests.get(5).is_complete(
    quests.get(5).fresh_progress()), False)


# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
# /goto, /give and /money are off on a served server and belong to
# the admin panel; this suite uses them to set a scene, so it asks
# for them by name.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# The server logs every frame, and this replay enters three locations, so its
# output outgrows a pipe nobody reads; a full pipe blocks the server mid-reply
# and every window after that sees nothing. Drain it as it comes.
import threading
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


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
    c.send("newPers;res=1;sex=0;name=@Archivist@;")
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
    check("reward items listed", field(si, "rew_obj"), "|5047|5048|5049|5050|5051|5052|")

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
    AARON, SHIHAB, TECHNOGEEK = npc[2424], npc[653], npc[652]
    # The daily limit counts repeatable quests only (server.DAILY_MAX): the
    # one-off delivery above cost none of the day's ten.
    check("a one-off hand-in costs none of the day's",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=10;"])
    c.send("q_list;")
    check("the log is kept across logins", c.frames()[0],
          "q_list;q_id=|3|;q_types=|2|;")
    c.send("q_co;obj_idx=0;mob=%d;q_id=3;" % SHIHAB)
    got = c.frames()
    # A repeatable one does, and the journal's caption is told at once,
    # before the ack its window rebuilds on.
    check("handed to the lessor, the day's count before the ack",
          [f.split(";")[0] for f in got], ["userInfo_Player", "q_sys", "cmdAck"])
    check("purse credited again", field(got[0], "afro"), "1070")
    check("one daily hand-in used", got[1], "q_sys;daily_available=9;")
    c.send("q_status;q_type=2;")
    check("a repeatable quest stays available", "status=1;" in c.frames()[0], True)

    # --- services without a fight -------------------------------------------
    # Giving quests alone does not make a commoner a home registrar.
    c.send("on_conv;mob=%d;op=0;" % TECHNOGEEK)
    check("the technogeek refuses home registration", c.frames(), ["cmdAck;res=2;"])
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
    check("the day's count as the hand-in left it",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=9;"])
    medic = [f for f in got if f.startswith("lch") and "rtype=5;" in f]
    check("the station has a medic", len(medic) > 0, True)
    MEDIC = int(field(medic[0], "newUser"))
    c.send("on_conv;mob=%d;op=0;" % MEDIC)
    check("the healer registers a home with one ack", c.frames(), ["cmdAck;res=0;"])
    store = accounts.Store(DB)
    home = store.db.execute("SELECT home_loc FROM characters").fetchone()["home_loc"]
    store.close()
    check("home is the healer's station", home, 37)
    c.send("on_conv;mob=%d;op=1;" % MEDIC)
    got = c.frames()
    check("healing: purse, bars, then the ack",
          [f.split(";")[0] for f in got], ["userInfo_Player", "usrUp", "cmdAck"])
    # The station's healer (100) charges the original's 150 (data/npcs.json
    # healer_price), not the old flat 10.
    check("fee taken", field(got[0], "afro"), "920")
    # Full is whatever the character's maximum is (120 for a newborn), so
    # compare the two fields rather than pin a number.
    check("healed to full", field(got[1], "hcur") == field(got[1], "hmax")
          and field(got[1], "scur") == field(got[1], "smax"), True)
    check("healing acknowledged", got[2], "cmdAck;res=0;")

    # --- a reward thing, and a chain, at the master's -------------------------
    # Мастер Тиль (5) on the market gives «Пистолетчик» (4) once Берт's
    # course is over: the certificate of the shooting range in the bag, one
    # of the six parts of «Самоучитель: Пистолеты» chosen as the reward and
    # the finish's coin beside it. The things go into the bag before the ack
    # -- ss_obj_status 1 and their dynamic info -- which is what the client
    # lists under «Вы получили».
    c.send("userMsg;entry=@/goto 102@;group=0;")
    c.frames()
    got = enter(c)
    npc = npc_ids(got)
    TIL = npc[5]
    store = accounts.Store(DB)
    me = store.db.execute("SELECT id FROM characters WHERE name = 'Archivist'").fetchone()["id"]
    store.close()
    # «Охотник» (1829), as «Пистолетчик», comes after the course's last
    # lesson (need_quest 357): not offered until that is handed in, then
    # offered.
    c.send("q_status;q_type=1829;")
    check("a quest whose chain is not walked is not offered",
          "status=0;" in c.frames()[0], True)
    store = accounts.Store(DB)
    store.finish_quest(0, me, 357)
    store.close()
    c.send("q_status;q_type=1829;")
    check("and is, once what comes before it is handed in",
          "status=1;" in c.frames()[0], True)
    c.send("userMsg;entry=@/give 3742@;group=0;")
    c.frames()
    c.send("q_st;mob=%d;q_idx=0;" % TIL)
    got = c.frames()
    check("the certificate in the bag, «Пистолетчик» starts complete",
          [(f.split(";")[0], field(f, "complete")) for f in got
           if f.startswith("q_di_")], [("q_di_bring_l_obj", "1")])
    q_pistol = int(field([f for f in got if f.startswith("q_di_")][0], "q_id"))
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (TIL, q_pistol))
    got = c.frames()
    check("handed in: the certificate out, the part and the coin in, the day's count, the ack",
          [f.split(";")[0] for f in got],
          ["ss_obj_status", "ss_obj_status", "ss_di_heap", "ss_obj_status", "ss_di_heap",
           "q_sys", "cmdAck"])
    check("the certificate left, the part and the coin came",
          [field(f, "status") for f in got if f.startswith("ss_obj_status")], ["0", "1", "1"])
    check("one of each", [field(f, "size") for f in got if f.startswith("ss_di_heap")],
          ["1", "1"])
    check("two of the day's hand-ins used",
          [f for f in got if f.startswith("q_sys")], ["q_sys;daily_available=8;"])
    check("acknowledged", got[-1], "cmdAck;res=0;")
    store = accounts.Store(DB)
    kept = sorted((r["type_id"], r["count"]) for r in store.items_of(me)
                  if r["type_id"] in (3742, 46652) or r["type_id"] in q4.rew_obj)
    store.close()
    check("and the bag holds the part chosen (obj_idx 0: «Пистолеты 1 часть») and the"
          " coin, not the certificate", kept, [(5047, 1), (46652, 1)])

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
