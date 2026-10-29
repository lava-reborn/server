"""Weapon eligibility, reset during aiming, and Halfa's existing knife ladder.

Only an in-memory database; no game server or production data.
Reset frames follow PersEquip.ss_obj_status; cancelled bursts close the
Location.faShot sequence before authoritative Fighter.c_ap (see
recon/analysis/combat.md). Client rendering is not exercised here.
"""
import os
import sys
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accounts  # noqa: E402
import combat  # noqa: E402
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
from testkit import check, fails  # noqa: E402

# Malformed dense source lists must not break the machine-gun frame.
overlay = items._overlay
for mask, values, expected in ((1 << 6, None, [4]),
                               ((1 << 2) | (1 << 6) | (1 << 8), [3], [3, 4, 0])):
    def incomplete(type_id, params, rec):
        overlay(type_id, params, rec)
        if type_id == 25006:
            params.update(need_skills=[20], need_specs_m=mask, need_specs=values)
    with patch.object(items, '_overlay', side_effect=incomplete):
        p = items.params_of(25006)
    check('machine-gun requirement pads a short list: %s' % mask,
          (p['need_specs_m'], p['need_specs']), (mask, expected))

ch = progression.Character()
ch.skill[progression.SHOOTING][0] = 20

def row(t, slot=inventory.PRIMARY):
    return dict(uniq=1, char_id=7, type_id=t, root=items.root_of(t), slot=slot,
                brk=100, ammo_count=10)

# --- machine-gun specialisation, ordinary/gold and their modifications ------
machineguns = []
for t, (root, _name) in items.catalogue().items():
    if root != items.FIRE_ARM:
        continue
    si = items.params_of(t)
    level = inventory.item_level(t)
    if si.get('weapon_type') != items.MACHINEGUN or not 16 <= level <= 20:
        continue
    machineguns.append((t, level))
wrong = []
for t, level in machineguns:
    character = progression.Character()
    character.skill[progression.SHOOTING][0] = level
    for spec in character.spec:
        spec[0] = 5
    required = level - 16
    for trained, allowed in ((required - 1, False), (required, True)):
        character.spec[6][0] = trained
        if inventory.wearable(row(t), character.level, character) != allowed:
            wrong.append((t, level, trained, allowed))
check('every level-16..20 machine gun and modification enforces the exact spec boundary', wrong, [])
for t, level in machineguns:
    p = items.params_of(t)
    offset = (p['need_specs_m'] & ((1 << 6) - 1)).bit_count()
    check('machine-gun %d sends the same requirement as its gate' % t,
          p['need_specs'][offset], level - 16)

check('machine-gun coverage includes all five item levels in both A and G',
      {(level, bool(items.params_of(t).get('g_cost'))) for t, level in machineguns},
      {(level, gold) for level in range(16, 21) for gold in (False, True)})

check("low melee no longer blocks a knife without spec requirements", inventory.wearable(row(6231), ch.level, ch), True)
ch.skill[progression.MELEE][0] = 2
check("homemade knife works at melee two without a declared spec", inventory.wearable(row(6231), ch.level, ch), True)
ch.skill[progression.MELEE][0] = 6
for t in (6240, 6241, 6242, 6243, 6244):
    ch.spec[1][0] = -1
    check("Tesak %d needs blade spec" % t, inventory.wearable(row(t), ch.level, ch), False)
    ch.spec[1][0] = 0
    check("Tesak %d needs spec level one, not just learning" % t, inventory.wearable(row(t), ch.level, ch), False)
    ch.spec[1][0] = 1
    check("Tesak %d accepts the exact boundary" % t, inventory.wearable(row(t), ch.level, ch), True)
ch.skill[progression.MELEE][0] = 20
ch.skill[progression.SHOOTING][0] = 0
check("low shooting no longer blocks an unrestricted firearm", inventory.wearable(row(25566), ch.level, ch), True)
ch.skill[progression.SHOOTING][0] = 1
check("firearm accepts exact shooting boundary", inventory.wearable(row(25566), ch.level, ch), True)

# A real inventory move and real spec reset; in-memory storage only.
store = accounts.Store(":memory:")
acc, _ = store.register("requirements", "secret")
cid, _ = store.create_character(acc, "Requirements", 0, 1)
ch = progression.Character.load(store, cid)
ch.skill[progression.SHOOTING][0] = 20
frames, messages = [], []
sess = SimpleNamespace(char_id=cid, pid=1, room=None, character=lambda: ch,
                       send=lambda cmd, **p: frames.append((cmd, p)), answer=messages.append)
sess.combat = combat.Fighter(sess)
inv = sess.inv = inventory.Inventory(sess, store)
fields = inventory.new_fields(6241)
root = fields.pop("root")
fields["slot"] = inventory.BAG
r = store.create_item(cid, 6241, root, **fields)
def equip():
    frames.clear()
    inv.ss_move(dict(obj=inventory.oid_of(store.item(r["uniq"])),
                     **{"from": inventory.BAG, "to": inventory.PRIMARY}))
    return [p["res"] for cmd, p in frames if cmd == "cmdAck"]
check("wire move still rejects the missing blade specialisation", equip(), [inventory.RES_LEVEL])
ch.skill[progression.MELEE][0] = 6
check("wire move rejects missing spec", equip(), [inventory.RES_LEVEL])
ch.spec[1][0] = 1
check("wire move accepts both requirements", equip(), [inventory.RES_OK])
# Execute the actual trainer handler without importing/starting the server.
tree = ast.parse(Path(__file__).with_name("server.py").read_text(encoding="utf-8"))
handler = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "training_upd")
ns = dict(STORE=store, progression=progression)
exec(compile(ast.Module(body=[handler], type_ignores=[]), "server.py", "exec"), ns)
sess.push_stats = lambda **_: None
sess.push_vitals = lambda: None
sess.push_money = lambda: None
ns["training_upd"](sess, dict(s_status=progression.UPD_FORGET, obj="1"))
check("trainer resets blade specialisation", ch.spec_level(1), -1)
check("weapon still exists in the bag", store.item(r["uniq"])["slot"], inventory.BAG)
check("live client rebuilds the same item in its current slot",
      [(p["obj"], p["status"]) for cmd, p in frames if cmd == "ss_obj_status"][-2:],
      [(inventory.oid_of(r), 0), (inventory.oid_of(r), 1)])
check("reset preserves exactly one item", len([x for x in inv.rows() if x["uniq"] == r["uniq"]]), 1)
frames.clear()
inv.ss_move(dict(obj=inventory.oid_of(store.item(r["uniq"])),
                 **{"from": inventory.BAG, "to": inventory.PRIMARY}))
check("subsequent equip is rejected by requirements rather than a stale slot",
      [p["res"] for cmd, p in frames if cmd == "cmdAck"], [inventory.RES_LEVEL])

# Already queued attacks cannot bypass a reset. Any damage/payment call would
# fail this small stand-in, which deliberately exposes neither operation.
guarded_firearm = next(t for t, (root, _) in items.catalogue().items()
                       if root == items.FIRE_ARM and inventory.item_level(t) <= 17
                       and items.params_of(t).get("need_specs_m"))
for t, callback in ((6241, "strike"), (guarded_firearm, "fire")):
    bad = row(t)
    ch = progression.Character()
    events = []
    session = SimpleNamespace(char_id=7, loc=SimpleNamespace(war=True),
                              inv=SimpleNamespace(find=lambda _: bad), on_map=False,
                              answer=events.append)
    fighter = SimpleNamespace(sess=session, character=lambda: ch, rc=SimpleNamespace(
        room=SimpleNamespace(ws=False, broadcast=events.append)), dead=False, ap=60,
        aim=None, strike=None, eid=99, store=SimpleNamespace(item=lambda _: bad),
        preparing=lambda: False, ack=lambda code: events.append(code))
    session.send = lambda cmd, **p: events.append((cmd, p))
    fighter.c_ap = lambda: combat.Fighter.c_ap(fighter)
    combat.Fighter.use_fire(fighter, dict(obj="1", target="invalid"))
    check("use gate precedes targeting: " + callback, events[0], inventory.RES_LEVEL)
    events.clear()
    if callback == "fire":
        for reason, changed in (("requirements", bad), ("missing", None),
                                ("owner", dict(bad, char_id=8)),
                                ("slot", dict(bad, slot=inventory.BAG)),
                                ("broken", dict(bad, brk=0))):
            events.clear()
            fighter.store.item = lambda _, current=changed: current
            combat.Fighter.fire_now(fighter, 1, None, 0, SimpleNamespace(num_shots=3), 8)
            check("cancelled burst closes all pairs: " + reason,
                  [p["status"] for cmd, p in events if cmd == "faShot"], [1, 0]*3)
            check("cancelled burst restores AP after animation: " + reason,
                  events[-1], ("c_ap", dict(ap=60)))
    else:
        combat.Fighter.strike_now(fighter, None, 0, (10, 20), 1, 8, 1)
        check("cancelled strike closes animation", events[0][0], "caMiss")
    check("cancelled attack preserves AP: " + callback, fighter.ap, 60)
    check("cancelled attack preserves ammo/durability: " + callback,
          (bad["ammo_count"], bad["brk"]), (10, 100))

stock = items.stock_for(1152, 102)
check("Halfa sells awl, sharpening blade, homemade G knife", all(t in stock for t in (6229, 6230, 6231)), True)
check("level-one awl needs no spec", inventory.wearable(row(6229), 1, SimpleNamespace(
    level=1, skill_level=lambda _: 1, spec_level=lambda _: -1)), True)
rows = [r for r in quests.table_rows() if isinstance(r.get("craft"), dict) and r["craft"].get("family") == "knife"
        and 2279 in r.get("give", [])]
check("Halfa has three sharpening choices at each existing knife tier",
      sorted(r["craft"]["level"] for r in rows), [2]*3 + [4]*3 + [6]*3 + [8]*3)
check("every Halfa sharpening blueprint is sold", all(r["craft"]["blueprint"] in stock for r in rows), True)
check("existing character level range preserved", {(r["level"], r["max_level"]) for r in rows}, {(0, 20)})

# New service rows reuse the existing valley recipes and the generator's
# configured tiers; no existing recipe or type registry entry is replaced.
import json
root = Path(__file__).resolve().parents[1]
doc = json.loads((root / "data/questgen_weaponcraft.json").read_text(encoding="utf-8"))
sources = {r["craft"]["level"]: [] for r in rows}
for r in doc["quests"]:
    if r["craft"]["key"].startswith("knife:valley:"):
        sources[r["craft"]["level"]].append(r)
for r in rows:
    if r["craft"]["level"] in (2, 4):
        source = next(s for s in sources[r["craft"]["level"]]
                      if s["craft"]["blueprint"] == r["craft"]["blueprint"])
        check("recipe %d preserves ingredients and reward" % r["type"],
              (r["objs"], r["rew_obj"], r["num_rew_obj"], r.get("fee")),
              (source["objs"], source["rew_obj"], source["num_rew_obj"], source.get("fee")))
        check("recipe type remains registered", doc["types"][r["craft"]["key"]], r["type"])
if fails:
    print("\n".join(fails))
    sys.exit(1)
