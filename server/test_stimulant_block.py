"""Temporary stimulant refusal preserves items/AP while healing and trade remain available."""
import asyncio
import logging
import os
import sys
from types import SimpleNamespace

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
import items
import inventory
import combat
from testkit import check, fails

check("temporary effects remain disabled", items.STIMULANT_EFFECTS_ENABLED, False)
for t in (4918, 4938, 3114, 3116, 3210):
    check("stimulant %d is blocked" % t, items.stimulant_unavailable(t), True)
for t in (6055, 6043, 6061, items.STARTER_ROUNDS):
    check("ordinary healing/ammo %d is not blocked" % t, items.stimulant_unavailable(t), False)
check("purchase remains available at Gofus", 3114 in items.stock_for(1013, 188), True)

blocked = [t for t, (root, _name) in items.catalogue().items()
           if root == items.HEAL and items.stimulant_unavailable(t)]
errors = []
for t in blocked:
    for kind, war in ((kind, war) for kind in (inventory.USE_IDLE, inventory.USE_TARGET)
                      for war in (False, True)):
        row = dict(type_id=t, root=items.HEAL, use_count=3, uniq=1, char_id=7)
        before = dict(row)
        acks, messages = [], []
        sess = SimpleNamespace(inv=SimpleNamespace(find=lambda _p: row), answer=messages.append,
                               char_id=7)
        fighter = SimpleNamespace(sess=sess, rc=SimpleNamespace(room=SimpleNamespace(ws=war)),
                                  ap=60, healing=None, ack=acks.append)
        combat.Fighter.use_heal(fighter, dict(obj="item", target="other"), kind)
        if (row != before or fighter.ap != 60 or fighter.healing is not None
                or acks != [inventory.RES_REFUSED] or messages != [items.STIMULANT_UNAVAILABLE]):
            errors.append((t, kind, war))
        # No consumption even if an old scheduled callback reaches heal_now.
        fighter.store = SimpleNamespace(item=lambda _u: row)
        fighter.dead = False
        combat.Fighter.heal_now(fighter, 1, None)
        if row != before or len(messages) != 2:
            errors.append((t, "callback"))
check("all %d blocked types preserve doses/AP on self and target, in/out of battle, including callbacks" % len(blocked), errors, [])

async def ordinary_heal():
    row = dict(type_id=6055, root=items.HEAL, use_count=1, uniq=1)
    acks = []
    sess = SimpleNamespace(inv=SimpleNamespace(find=lambda _p: row), send=lambda *a,**kw:None)
    fighter = SimpleNamespace(sess=sess, rc=None, ap=60, healing=None, ack=acks.append, heal_now=lambda *a: None)
    combat.Fighter.use_heal(fighter, dict(obj="item"), inventory.USE_IDLE)
    check("ordinary healing still starts", (acks, fighter.healing is not None), ([inventory.RES_OK], True))
    if fighter.healing:
        fighter.healing.cancel()
asyncio.run(ordinary_heal())
if fails:
    print("\n".join(fails))
    sys.exit(1)
