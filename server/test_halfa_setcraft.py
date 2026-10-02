"""Вади-Хальфа's set craft (server/setcraft.py, the owner's «всё
отложенное», stage 3): the upgrader's window, the gold-set exchange, the
clothing rework with its cheques and the parts upgrade.

In process: the reworked pieces of the owner's ladder (numbers, names, set,
no P, their rung's description id), a set of them counted as the set, what
the module adds to the preload; the windows of Генри, Генри ст and Мастер
Тиль and the empty ones of the town's other upgraders; the generated rows
(data/questgen_setcraft.json is setcraft.generate_all(), rebuilt, and the
server's start check refuses one priced off another ladder) -- their
craftsmen, band, services, prices, no premium thing, no step a stall pays
for, whole or worn; the same generator fed Абри's slice; the hand rows
238/239 in the original's words.

On a socket, a character of the eighth level with «Переработка»: Генри's
window opened, an upgrade (the frames, the one ack, the rung, the price, the
ledger), its refusals and the bare close; Генри ст's exchange of a mod10,
and his window left open behind upgrading nothing from another room; at the
craftsmen of 452 the rows offered only for the piece in the bag, cheques
bought, a rework and a parts upgrade handed in, the fees in the ledger, and
a worn piece reworked and upgraded keeping its wear; and at the ninth level
nothing of the band.

    LAVA_RES=.../lava/res python3 server/test_halfa_setcraft.py
"""
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import sets  # noqa: E402
import setcraft  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "data"))
import build_setcraft  # noqa: E402

from testkit import check, fails  # noqa: E402


HENRY, OLD_HENRY, TIL = 93, 5104, 5
OTHER_UPGRADERS = (6765, 2000, 2001, 8213, 8214)
PORT_MARKET, OLD_MARKET, CRAFT_6, CRAFT_7, CRAFT_8 = 104, 35, 452, 456, 457
MAGRIB_G, RAIDER_G, WANDERER_G = 11260, 11187, 11193          # set types
MAGRIB_A, RAIDER_A = 11258, 11185
HELM = "helm"
RECYCLING = quests.SPEC_KEYS["recycling"]
RATE, OUNCE = progression.GOLD_TO_AFRO_RATE, progression.GOLD_OUNCE
ROWS = [q for q in quests.table_rows(quests.PATH) if q["type"] in setcraft.TYPE_RANGE]


def piece(set_type, slot=HELM):
    return sets.SETS[set_type]["members"][slot]


def chain(set_type, slot=HELM):
    return setcraft.CHAINS[piece(set_type, slot)]


def row_for(craft, first_obj):
    got = [q for q in ROWS if q["craft"] == craft and q["objs"][0]["obj"] == first_obj]
    return got[0] if got else None


def cheque_row(level, variant, n):
    cheque = setcraft.CHEQUES[(level, variant)]
    got = [q for q in ROWS if q["craft"] == "cheque" and q["rew_obj"] == [cheque]
           and q["num_rew_obj"] == [n]]
    return got[0] if got else None


def standing(loc_id):
    return {t for _cell, t in world.location(loc_id).spawns}


# --- in process: the pieces -------------------------------------------------------------
try:
    print("the reworked pieces")
    ladder_ag = [r for r in setcraft.LADDER if r["variant"] in ("A", "G")]
    check("every A and G piece of the owner's ladder has its ten mods in objects.xml",
          (len(setcraft.CHAINS), setcraft.MISSING), (5 * len(ladder_ag), []))
    cat = items.catalogue()
    check("  ..mod01-mod10 of the same series, slot and variant, never a P",
          [t for c in setcraft.CHAINS.values() for k, t in enumerate(c)
           if not cat[t][1].endswith("_mod%02d" % k) or cat[t][1][:-2] != cat[c[0]][1][:-2]
           or items.premium(t)], [])
    mod3 = chain(RAIDER_G)[3]
    si0, si3 = items.params_of(chain(RAIDER_G)[0]), items.params_of(mod3)
    check("a reworked piece: its rung's set, needs and bonuses, armour, wear and price stepped"
          " up by the mod",
          (si3["set_type"], si3["need_skills"], si3["bonus_st"], si3["armor_class"],
           si3["max_break_abs"], si3["g_cost"], si3["cost"], si3["exchang"]),
          (RAIDER_G, si0["need_skills"], si0["bonus_st"],
           int(math.floor(si0["armor_class"] * (1 + 3 * setcraft.MOD_ARMOR) + 0.5)),
           int(math.floor(si0["max_break_abs"] * (1 + 3 * setcraft.MOD_WEAR) + 0.5)),
           int(math.floor(si0["g_cost"] * (1 + 3 * setcraft.MOD_PRICE) + 0.5)), 0, 0))
    check("  ..named by its rung's name and the mod, described by its rung's words under its"
          " rung's id",
          (names.text(items.STRING_ID_OFFSET + mod3), si3["desc"], names.text(si3["desc"])),
          ("Очки налетчика (G) (мод03)", items.DESC_ID_OFFSET + chain(RAIDER_G)[0],
           sets.item_descs()[chain(RAIDER_G)[0]]))
    mods = [t for c in setcraft.CHAINS.values() for t in c[1:]]
    check("  ..every one of them named in the preload, its description id its rung's and"
          " known there",
          [t for t in mods if not (names.known(items.STRING_ID_OFFSET + t)
                                   and items.params_of(t).get("desc")
                                   == items.params_of(setcraft.base_of(t)).get("desc")
                                   and names.known(items.params_of(t)["desc"]))], [])
    # The preload every client reads at start: the module adds names, not
    # ten copies of a rung's description (the skeptic's +0.6 MB), and the
    # rows' templates stay within a budget.
    own = setcraft.strings()
    row_text = sum(len(names.text(i).encode(ENC)) for q in ROWS
                   for i in quests.get(q["type"]).string_ids())
    check("  ..no description string of a mod's own; the module's strings and its rows' texts"
          " add under 450 KB to the preload",
          ([i for i in own if i - items.DESC_ID_OFFSET in setcraft.MOD_OF],
           sum(len(v.encode(ENC)) for v in own.values()) + row_text < 450 * 1024),
          ([], True))
    # A full set of reworked pieces is the set, on the card and in the figure.
    slots = dict(zip(sets.SLOTS, inventory.SET_SLOTS))

    def body(types):
        return [dict(uniq=i, type_id=t, root=items.WEAR, slot=slots[s], brk=100,
                     max_break_cur=100, count=1) for i, (s, t) in enumerate(zip(sets.SLOTS, types))]

    plain = [chain(RAIDER_G, s)[0] for s in sets.SLOTS]
    reworked = [chain(RAIDER_G, s)[k] for k, s in enumerate(sets.SLOTS)]
    check("five reworked pieces of a set, of mixed mods, are the set: the same bonus on the"
          " character as the plain five (the set's and each piece's own), the set's figure",
          (inventory.gear_bonus(body(reworked)) == inventory.gear_bonus(body(plain)),
           inventory.gear_bonus(body(plain))["st"] > sum(
               items.params_of(t).get("bonus_st", 0) for t in plain),
           inventory.look_of(body(reworked))),
          (True, True, sets.SETS[RAIDER_G]["res"]))

    # --- the windows ------------------------------------------------------------------
    print("the windows")
    henry = setcraft.entries(HENRY)
    check("Генри leads up to the band's rungs, 6 and 8, in gold alone: Странник to Магриб,"
          " Магриб to Налетчик",
          sorted({(sets.set_of(setcraft.base_of(i)), sets.set_of(setcraft.base_of(o)))
                  for i, o, _c in henry}),
          [(WANDERER_G, MAGRIB_G), (MAGRIB_G, RAIDER_G)])
    check("  ..any mod of the old piece for the new one's mod00, slot for slot",
          sorted((i, o) for i, o, _c in henry if setcraft.base_of(o) == piece(RAIDER_G)),
          sorted((t, piece(RAIDER_G)) for t in chain(MAGRIB_G)))
    check("  ..at 60% of the new piece's price («со скидкой в 40%»), rounded up",
          {c for i, o, c in henry if o == piece(RAIDER_G)},
          {int(math.ceil(0.6 * setcraft.price(piece(RAIDER_G))[1]))})
    check("  ..his userInfo carries the three lists, in step",
          setcraft.window(HENRY), dict(in_types=[i for i, _o, _c in henry],
                                        out_types=[o for _i, o, _c in henry],
                                        costs=[c for _i, _o, c in henry]))
    old = setcraft.entries(OLD_HENRY)
    exchange = [e for e in old if e not in henry]
    check("Генри ст upgrades the same and exchanges a G mod10 for the next rung's mod05 at 50%",
          (set(henry) <= set(old), sorted(exchange)),
          (True, sorted((chain(frm, s)[10], chain(to, s)[5],
                         int(math.ceil(0.5 * setcraft.price(chain(to, s)[5])[1])))
                        for frm, to in ((WANDERER_G, MAGRIB_G), (MAGRIB_G, RAIDER_G))
                        for s in sets.SLOTS)))
    check("Мастер Тиль upgrades as Генри; the town's other upgraders keep their own services",
          (setcraft.entries(TIL) == henry, [setcraft.window(t)["in_types"] for t in OTHER_UPGRADERS]),
          (True, [[]] * len(OTHER_UPGRADERS)))
    every = {t for u in (HENRY, OLD_HENRY, TIL) for e in setcraft.entries(u) for t in e[:2]}
    check("  ..no A, no P, no Q in any window («Обменять можно только (G) вещи»)",
          sorted({cat[t][1].split("_")[-2] for t in every}), ["G"])
    saved = setcraft.UPGRADE_VARIANTS
    try:
        setcraft.UPGRADE_VARIANTS = ("A", "G")
        with_a = setcraft.window_entries(setcraft.SLICES["Вади-Хальфа"], ("upgrade",))
    finally:
        setcraft.UPGRADE_VARIANTS = saved
    a_rows = [(i, o, c) for i, o, c in with_a if cat[o][1].split("_")[-2] == "A"]
    check("  ..switched on, an afro set upgrades too, priced in gold at the one rate",
          {c for _i, o, c in a_rows if o == piece(RAIDER_A)},
          {int(math.ceil(0.6 * setcraft.price(piece(RAIDER_A))[0] * OUNCE / RATE))})

    # --- the rows ---------------------------------------------------------------------
    print("the rows")
    with open(build_setcraft.OUT, encoding="utf-8") as fh:
        on_disk = json.load(fh)["quests"]
    check("data/questgen_setcraft.json is what the generator makes now (rebuilt)",
          on_disk == json.loads(json.dumps(setcraft.generate_all(), ensure_ascii=False)), True)
    # The server asks the same at start (setcraft.check_rows, server.main):
    # a ladder whose prices moved (the wardrobe rebuilt data/sets.json) and
    # no rebuild of the rows would sell cheques off the old prices.
    saved_price = setcraft.price

    def refused():
        try:
            setcraft.check_rows()
        except ValueError as why:
            return "build_setcraft.py" in str(why)
        return False

    try:
        setcraft.price = lambda t: tuple(int(x * 1.5) for x in saved_price(t))
        moved = refused()
    finally:
        setcraft.price = saved_price
    check("  ..and the server's start refuses rows priced off another ladder, names the builder;"
          " a table standing alone (LAVA_QUESTS) is not asked",
          (setcraft.check_rows(), moved,
           setcraft.check_rows(os.path.join(tempfile.mkdtemp(), "quests.json"))),
          (None, True, None))
    by_craft = {}
    for q in ROWS:
        by_craft.setdefault(q["craft"], []).append(q)
    check("200 rework rows, 200 parts upgrades, 8 cheque sales, 11000-11407, all loaded",
          ({k: len(v) for k, v in by_craft.items()}, ROWS[0]["type"], ROWS[-1]["type"],
           all(q["type"] in quests.QUESTS for q in ROWS)),
          ({"rework": 200, "parts": 200, "cheque": 8}, 11000, 11407, True))
    check("  ..each a service, repeatable, outside the daily limit and the journal's count",
          ({(q["service"], q["repeatable"]) for q in ROWS},
           [q["type"] for q in ROWS if q["type"] in quests.repeatable_types()]),
          ({(True, 1)}, []))
    check("  ..of the band: the owner's rungs 6 and 8 (Магриб, Налетчик), offered from the"
          " rung's level up to the eighth",
          sorted({(q["level"], q["max_level"]) for q in ROWS}), [(6, 8), (8, 8)])
    named_things = {t for q in ROWS for t in q["rew_obj"] + [o["obj"] for o in q.get("objs", [])]}
    check("  ..no premium thing anywhere, every thing a thing the game has",
          ([t for t in named_things if items.premium(t)],
           [t for t in named_things if items.params_of(t) is None]), ([], []))
    check("  ..every string preloaded",
          [q["type"] for q in ROWS if not all(names.known(i)
                                             for i in quests.get(q["type"]).string_ids())], [])
    craftsmen = {6: standing(CRAFT_6), 8: standing(CRAFT_8)}
    wrong = []
    for q in by_craft["rework"] + by_craft["parts"]:
        giver = q["give"][0]
        base, k = setcraft.mod_of(q["objs"][0]["obj"])
        variant = cat[base][1].split("_")[-2]
        slot = cat[base][1].split("_")[0]
        who = names.text(giver)
        rank = {"G": "Мастер", "A": "Ученик"}[variant]
        if q["give"] != q["take"] or giver not in craftsmen[q["level"]] \
                or not who.startswith(rank) or q["rew_obj"] != [setcraft.chain_of(base)[k + 1]] \
                or giver - setcraft.SLICES["Вади-Хальфа"]["craftsmen"][q["level"]] \
                != 3 * sets.SLOTS.index(slot) + setcraft.RANK[variant]:
            wrong.append(q["type"])
    check("every step is its craftsman's: the level's quarter (452 for 6, 457 for 8), the"
          " master for G, the pupil for A, his slot; modN in, modN+1 out", wrong, [])
    check("  ..the apprentices (P) and the seventh level's quarter (456) give nothing",
          sorted({g for q in ROWS for g in q["give"]} & (standing(CRAFT_7) | {
              t for t in standing(CRAFT_6) | standing(CRAFT_8) if "Подмастерье" in names.text(t)})),
          [])
    steps = []
    for q in by_craft["rework"]:
        base, k = setcraft.mod_of(q["objs"][0]["obj"])
        variant = cat[base][1].split("_")[-2]
        level = q["level"]
        each = setcraft.cheque_price(level, variant)
        piece_price = setcraft.price(base)[1 if variant == "G" else 0]
        steps.append((q["objs"][1]["num"] * each * 10 == piece_price,
                      q["rew_spec_xp"] == {"recycling": 9 * level}))
    check("a rework step asks cheques worth 10% of the piece's price (the owner's decision 13)"
          " and pays «Переработка» 9 x the level", set(steps), {(True, True)})
    arbitrage = []
    for base, c in setcraft.CHAINS.items():
        if cat[base][1].split("_")[-2] != "A":
            continue
        for k in range(10):
            gain = inventory.SMOD * (setcraft.price(c[k + 1])[0] - setcraft.price(c[k])[0])
            if gain >= 0.1 * setcraft.price(base)[0]:
                arbitrage.append(c[k])
    check("  ..and a stall's price of the new mod never pays for the step",
          arbitrage, [])
    # Nor for a worn piece: the step keeps the wear (setcraft.keep_wear), so
    # it is no repair at a tenth of the price -- the stall pays for the new
    # mod at the old quality, and mending it costs no less than before.
    mended = []
    for base, c in setcraft.CHAINS.items():
        if cat[base][1].split("_")[-2] != "A":
            continue
        for k in range(10):
            s0, s1 = items.params_of(c[k]), items.params_of(c[k + 1])
            a0, a1 = s0["max_break_abs"], s1["max_break_abs"]
            for brk, top in ((1, 20), (0, a0), (a0 // 2, a0), (a0 // 3, a0 // 2), (a0, a0)):
                nb, nt = setcraft.worn_as((brk, top, a0), a1)
                q0, q1 = brk / float(top), nb / float(nt)
                sale = [math.floor(s["cost"] * inventory.SMOD * s.get("sell_mod", 1) * q)
                        for s, q in ((s0, q0), (s1, q1))]
                fix = [math.floor(s["cost"] * inventory.RMOD * s.get("repair_mod", 1) * (1 - q))
                       for s, q in ((s0, q0), (s1, q1))]
                if q1 > q0 or nt / float(a1) > top / float(a0) \
                        or sale[1] - sale[0] >= 0.1 * setcraft.price(base)[0] or fix[1] < fix[0] \
                        or (brk, top) == (a0, a0) and (nb, nt) != (a1, a1):
                    mended.append((c[k], brk, top, nb, nt))
    check("  ..nor a worn one's: the new mod keeps its share of wear and of the ceiling (rounded"
          " down), a whole piece stays whole, the repair costs no less",
          mended, [])
    parts = {(q["level"], cat[setcraft.base_of(q["objs"][0]["obj"])][1].split("_")[-2],
              q["cost_afro"], q["cost_gold"], q["rew_spec_xp"]["recycling"])
             for q in by_craft["parts"]}
    check("the parts upgrade: 4000 x the level afro, silver 2 x the level ounces in gold at the"
          " ФСЦ's 10 to 1, a tenth of the level more for G, «Переработка» 40 x the level",
          sorted(parts), [(6, "A", 24000, 120, 240), (6, "G", 24000, 180, 240),
                          (8, "A", 32000, 160, 320), (8, "G", 32000, 240, 320)])
    check("the cheques: [6] and [8], A and G, one or five, the A for afro and the G for gold,"
          " sold by the treasurers and the craftsmen who ask them",
          sorted((q["level"], cat[q["rew_obj"][0]][1], q["num_rew_obj"][0], q["cost_afro"],
                  q["cost_gold"], tuple(q["give"][:3])) for q in by_craft["cheque"]),
          sorted((lv, "Chek_Set_%s_%d" % (v, lv), n,
                  0 if v == "G" else n * setcraft.cheque_price(lv, v),
                  n * setcraft.cheque_price(lv, v) if v == "G" else 0, setcraft.TREASURERS)
                 for lv in (6, 8) for v in ("A", "G") for n in (1, 5)))
    g6 = setcraft.CHEQUES[(6, "G")]
    check("  ..named by the original's row with the level kept; the gold one priced in gold"
          " alone", (names.text(items.STRING_ID_OFFSET + setcraft.CHEQUES[(6, "A")]),
                     names.text(items.STRING_ID_OFFSET + g6),
                     (items.params_of(g6)["cost"], items.params_of(g6)["g_cost"])),
          ("Чек на одежду [6]", "Чек на одежду [6] (G)", (0, setcraft.cheque_price(6, "G"))))
    # One mechanism: Абри's slice gives Абри's rows (Пустынник[10]; Чёрный
    # Ловелас[12] is a quest set, not reworked).
    abri = dict(band=(10, 12), parts_band=(10, 12), upgraders={},
                craftsmen={10: 90000, 11: 90015, 12: 90030},
                types={"rework": 12000, "parts": 12200, "cheque": 12400, "end": 12500})
    got = setcraft.generate(abri)
    check("the same generator fed Абри's slice: Пустынник[10] A and G, 100 + 100 + 4 rows",
          (len(got), sorted({(q["level"], q["max_level"]) for q in got}),
           sorted({sets.set_of(setcraft.base_of(q["objs"][0]["obj"]))
                   for q in got if q.get("objs")})),
          (204, [(10, 12)], [11182, 11184]))
    check("the hand rows: «Как менять старые комплекты» at both Генри, «Обмен б/у снаряжения»"
          " at Генри ст, in the original's words",
          [(quests.get(t).give, orig_texts.quests().get(t, {}).get("name")) for t in (238, 239)],
          [([HENRY, OLD_HENRY], "Как менять старые комплекты"),
           ([OLD_HENRY], "Обмен б/у снаряжения")])
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_setcraft.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tailor", "secret")
_store.close()
CRED = accounts.credential("tailor", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_SEED="5", LAVA_POLICY_PORT="0")
for _k in ("LAVA_QUESTS", "LAVA_PASSAGES"):
    env.pop(_k, None)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=15):
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
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def order(frames):
    return [n for n, _p in frames]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(2)


def infos(frames):
    """type id -> (frame name, params) of the population's userInfo_* frames."""
    return {p["name"]: (n, p) for n, p in frames
            if n.startswith("userInfo_") and n != "userInfo_Player" and "name" in p}


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    return infos(arrive(c))


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.frames()
    return [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status") if p["status"] == 1]


def money(c, afro, gold):
    c.send("userMsg;entry=@/money %d %d@;group=0;" % (afro, gold))
    c.frames(0.4)


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, npc, npc_type, qtype):
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, npc, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (npc, q_id))
    return c.frames(0.9)


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    cid = st.character_by_name("Tailor")["id"]
    st.close()
    return cid


def purse():
    st = store()
    got = tuple(st.money(char_id()))
    st.close()
    return got


def owned():
    st = store()
    out = {}
    for r in st.items_of(char_id()):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def rows_of(type_id):
    """The character's rows of a type, oldest first."""
    st = store()
    got = [dict(r) for r in st.items_of(char_id()) if r["type_id"] == type_id]
    st.close()
    return got


def ledger(source):
    st = store()
    got = [(r["ref"], r["afro"], r["gold"]) for r in st.db.execute(
        "SELECT ref, afro, gold FROM money_ledger WHERE char_id = ? AND source = ? ORDER BY id",
        (char_id(), source)).fetchall()]
    st.close()
    return got


def spec_xp():
    st = store()
    ch = progression.Character.load(st, char_id())
    st.close()
    return tuple(ch.spec[RECYCLING][:2])


def reshape(skill):
    """The logged-out character's Стрельба, and «Переработка» learned."""
    st = store()
    ch = progression.Character.load(st, char_id())
    ch.skill[progression.SHOOTING] = [skill, 0, progression.skill_xp_max(skill)]
    if ch.spec[RECYCLING][0] < 0:
        ch.spec[RECYCLING] = [0, 0, progression.SPEC_XP_START]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(st)
    st.close()


def login(first_time=False):
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    if first_time:
        c.send("newPers;res=1;sex=0;name=@Tailor@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    return c


def logout(c):
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)


try:
    c = login(first_time=True)
    logout(c)
    reshape(8)
    c = login()
    money(c, 200000, 5000)

    # --- Генри's window: an upgrade --------------------------------------------------------
    print("Генри's window")
    here = goto(c, PORT_MARKET)
    kind, henry_info = here.get(HENRY, ("", {}))
    check("Генри is an upgrader whose userInfo carries his window's three lists",
          (kind, {k: henry_info.get(k) for k in ("in_types", "out_types", "costs")}),
          ("userInfo_Upgrader", setcraft.window(HENRY)))
    old_helm = give(c, piece(MAGRIB_G))[0]
    c.send("ss_create;s_type=5;target=%d;" % henry_info["id"])
    check("ss_create;s_type=5 at Генри: one ack, 0", acks(c.frames()), [0])
    c.send("ss_get;target=0;slot=8;")
    got = c.frames()
    check("  ..the window asks for the bag and gets it, the army helmet in it",
          old_helm in [str(x).lstrip("x") for x in first(got, "ss_ack").get("o_list", [])], True)
    cost = setcraft.cost_of(HENRY, piece(MAGRIB_G), piece(RAIDER_G))
    afro0, gold0 = purse()
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (piece(RAIDER_G), old_helm))
    got = c.frames()
    check("«Улучшить»: the ack, the old piece out, the new one in with its numbers, the purse",
          (order(got)[:5], acks(got), [(p["status"], str(p["obj"]).lstrip("x") == old_helm)
                                      for p in named(got, "ss_obj_status")]),
          (["cmdAck", "ss_obj_status", "ss_obj_status", "ss_di_wear", "userInfo_Player"], [0],
           [(0, True), (1, False)]))
    check("  ..the army helmet (G) became the raider's goggles (G) for 60% of their 2.5 ounces",
          (owned().get(piece(MAGRIB_G)), owned().get(piece(RAIDER_G)), gold0 - purse()[1],
           purse()[0] - afro0, first(got, "userInfo_Player").get("gold")),
          (None, 1, cost, 0, gold0 - cost))
    check("  ..booked in the money ledger as the upgrade, under the new piece",
          ledger("set_upgrade"), [(piece(RAIDER_G), 0, -cost)])
    # Refusals: one ack each, nothing moves.
    shirt = give(c, piece(MAGRIB_G, "shirt"))[0]
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (piece(RAIDER_G), shirt))
    got = c.frames()
    check("a piece for another slot's piece: refused (3), one ack, nothing moves",
          (acks(got), "ss_obj_status" in order(got), owned().get(piece(MAGRIB_G, "shirt"))),
          ([3], False, 1))
    c.send("ss_upd;param=%d;obj=x0;s_status=1;" % piece(RAIDER_G, "shirt"))
    check("  ..a piece that is not in the bag: 12", acks(c.frames()), [12])
    money(c, 0, -10 ** 6)
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (piece(RAIDER_G, "shirt"), shirt))
    got = c.frames()
    check("  ..no gold: 21, the shirt stays", (acks(got), owned().get(piece(MAGRIB_G, "shirt"))),
          ([21], 1))
    money(c, 0, 5000)
    c.send("ss_upd;obj=x0;s_status=0;")
    check("closing the window is sent bare and answered with nothing", c.frames(0.4), [])
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (piece(RAIDER_G, "shirt"), shirt))
    got = c.frames()
    check("  ..and after it an upgrade is no longer the window's", (
        owned().get(piece(MAGRIB_G, "shirt")), owned().get(piece(RAIDER_G, "shirt"))), (1, None))

    # --- Генри ст: the exchange -------------------------------------------------------------
    print("Генри ст's exchange")
    here = goto(c, OLD_MARKET)
    old_info = here.get(OLD_HENRY, ("", {}))[1]
    worn_out = give(c, chain(MAGRIB_G)[10])[0]
    c.send("ss_create;s_type=5;target=%d;" % old_info.get("id", 0))
    c.frames()
    gold1 = purse()[1]
    want = chain(RAIDER_G)[5]
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (want, worn_out))
    got = c.frames()
    check("a (G) mod10 for the next rung's mod05, for half the new piece's price",
          (acks(got), owned().get(chain(MAGRIB_G)[10]), owned().get(want), gold1 - purse()[1]),
          ([0], None, 1, int(math.ceil(0.5 * setcraft.price(want)[1]))))
    # The window never closed and the player gone: it upgrades nothing.
    boots = give(c, piece(WANDERER_G, "boots"))[0]
    here = goto(c, CRAFT_6)
    gold1 = purse()[1]
    c.send("ss_upd;param=%d;obj=x%s;s_status=1;" % (piece(MAGRIB_G, "boots"), boots))
    got = c.frames()
    check("a window left open behind, in another room: the upgrade refused (3), one ack, the"
          " boots and the gold stay",
          (acks(got), "ss_obj_status" in order(got), owned().get(piece(WANDERER_G, "boots")),
           owned().get(piece(MAGRIB_G, "boots")), purse()[1]), ([3], False, 1, None, gold1))
    c.send("ss_upd;obj=x0;s_status=0;")
    c.frames(0.3)

    # --- the craftsmen: cheques, a rework, a parts upgrade -----------------------------------
    print("the craftsmen")
    master = setcraft.craftsman(setcraft.SLICES["Вади-Хальфа"], 6, HELM, "G")
    npc = here.get(master, ("", {}))[1].get("id", 0)
    helm = chain(MAGRIB_G)
    rework, parts = row_for("rework", helm[0]), row_for("parts", helm[1])
    five = cheque_row(6, "G", 5)
    check("the master of the (G) helmets offers his cheques; the step of a helmet not in the"
          " bag is not offered",
          (status(c, five["type"]), status(c, rework["type"])), (1, 0))
    give(c, helm[0])
    check("  ..with the army helmet (G) in the bag its step is", status(c, rework["type"]), 1)
    gold2 = purse()[1]
    got, qid = take(c, npc, master, five["type"])
    got = hand_in(c, npc, qid)
    check("five cheques bought: the gold, five «Чек на одежду [6] (G)»",
          (acks(got), gold2 - purse()[1], owned().get(setcraft.CHEQUES[(6, "G")])),
          ([0], five["cost_gold"], 5))
    xp0 = spec_xp()
    got, qid = take(c, npc, master, rework["type"])
    check("the rework taken, complete with the helmet and the cheques in the bag",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 1))
    got = hand_in(c, npc, qid)
    check("  ..handed in: the helmet at mod01, the cheques gone, «Переработка» +54",
          (acks(got), owned().get(helm[0]), owned().get(helm[1]),
           owned().get(setcraft.CHEQUES[(6, "G")]), spec_xp()[1] - xp0[1]),
          ([0], None, 1, None, 54))
    check("  ..and now the next steps are offered: the rework's and the parts upgrade's",
          (status(c, row_for("rework", helm[1])["type"]), status(c, parts["type"])), (1, 1))
    afro3, gold3 = purse()
    got, qid = take(c, npc, master, parts["type"])
    got = hand_in(c, npc, qid)
    check("the parts upgrade: mod01 to mod02 for 24 000 afro and 1.80 ounces, «Переработка» +240",
          (acks(got), owned().get(helm[1]), owned().get(helm[2]), afro3 - purse()[0],
           gold3 - purse()[1], spec_xp()[1] - xp0[1]),
          ([0], None, 1, 24000, 180, 54 + 240))
    check("  ..both fees in the money ledger as the quests', under their types",
          [(r, a, g) for r, a, g in ledger("quest") if r in (five["type"], parts["type"])],
          [(five["type"], 0, -five["cost_gold"]), (parts["type"], -24000, -180)])

    # A worn piece: the step changes the mod and keeps the wear.
    pupil = setcraft.craftsman(setcraft.SLICES["Вади-Хальфа"], 6, HELM, "A")
    pnpc = here.get(pupil, ("", {}))[1].get("id", 0)
    helm_a = chain(MAGRIB_A)
    abs_a = [items.params_of(t)["max_break_abs"] for t in helm_a[:3]]
    give(c, helm_a[0])
    give(c, helm_a[0])
    worn_uniq = rows_of(helm_a[0])[0]["uniq"]           # the older of the two
    st = store()
    st.update_item(worn_uniq, brk=1, max_break_cur=20)   # as fights and repairs leave it
    st.close()
    got, qid = take(c, pnpc, pupil, cheque_row(6, "A", 5)["type"])
    hand_in(c, pnpc, qid)
    got, qid = take(c, pnpc, pupil, row_for("rework", helm_a[0])["type"])
    got = hand_in(c, pnpc, qid)
    want1 = setcraft.worn_as((1, 20, abs_a[0]), abs_a[1])
    new_oid = [str(p["obj"]).lstrip("x") for p in named(got, "ss_obj_status") if p["status"] == 1]
    shown = [(p["break"], p["max_break_cur"]) for p in named(got, "ss_di_wear")
             if str(p["obj"]).lstrip("x") in new_oid]
    check("a worn army helmet (1 of a ceiling sagged to 20) reworked: the older, worn one taken,"
          " the mod01 as worn (its share of wear and of the ceiling), the client told so last;"
          " the whole one stays whole",
          (acks(got), want1, [(r["brk"], r["max_break_cur"]) for r in rows_of(helm_a[1])],
           shown[-1:], [(r["uniq"] == worn_uniq, r["brk"], r["max_break_cur"])
                        for r in rows_of(helm_a[0])]),
          ([0], (1, 21), [want1], [want1], [(False, abs_a[0], abs_a[0])]))
    got, qid = take(c, pnpc, pupil, row_for("parts", helm_a[1])["type"])
    got = hand_in(c, pnpc, qid)
    want2 = setcraft.worn_as(want1 + (abs_a[1],), abs_a[2])
    check("  ..and so does the parts upgrade: mod02 as worn",
          (acks(got), [(r["brk"], r["max_break_cur"]) for r in rows_of(helm_a[2])]),
          ([0], [want2]))
    logout(c)

    # --- the band ---------------------------------------------------------------------------
    reshape(9)
    c = login()
    check("at the ninth level the band's rows are no longer offered",
          (status(c, five["type"]), status(c, row_for("rework", helm[2])["type"])), (0, 0))
    logout(c)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [line for line in out.splitlines() if "C->S" in line or "  ..  " in line]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa setcraft OK")
