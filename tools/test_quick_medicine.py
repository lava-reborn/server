"""Execute the emitted quick-heal AVM1 against mixed inventories and battle states."""
import os
import sys
import struct
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))
import widescreen as w
from testkit import check, fails


def get(obj, key):
    if obj is None: return None
    if isinstance(obj, dict): return obj.get(key)
    if key == "length" and isinstance(obj, list): return len(obj)
    if isinstance(obj, list): return obj[int(key)] if 0 <= int(key) < len(obj) else None
    return getattr(obj, key, None)


def execute(code, env):
    stack, at = [], 0
    while at < len(code):
        op = code[at]; at += 1
        payload = b""
        if op >= 128:
            size, = struct.unpack_from("<H", code, at); at += 2
            payload = code[at:at+size]; at += size
        if op == 0x96:
            i = 0
            while i < len(payload):
                t = payload[i]; i += 1
                if t == 0:
                    end = payload.index(b"\0", i); stack.append(payload[i:end].decode()); i = end+1
                elif t in (2, 3): stack.append(None)
                elif t == 5: stack.append(bool(payload[i])); i += 1
                elif t == 7: stack.append(struct.unpack_from("<i", payload, i)[0]); i += 4
                else: raise AssertionError(t)
        elif op == 0x1c: stack.append(env.get(stack.pop()))
        elif op == 0x4e:
            key, obj = stack.pop(), stack.pop(); stack.append(get(obj, key))
        elif op == 0x4f:
            value, key, obj = stack.pop(), stack.pop(), stack.pop()
            if isinstance(obj, dict): obj[key] = value
            else: setattr(obj, key, value)
        elif op == 0x3c:
            value, key = stack.pop(), stack.pop(); env[key] = value
        elif op in (0x52, 0x3d):
            name = stack.pop(); obj = stack.pop() if op == 0x52 else env
            count = stack.pop(); args = [stack.pop() for _ in range(count)]
            stack.append(get(obj, name)(*args))
        elif op == 0x42:
            count = stack.pop(); stack.append([stack.pop() for _ in range(count)])
        elif op == 0x12: stack.append(not stack.pop())
        elif op == 0x17: stack.pop()
        elif op in (0x0b, 0x47, 0x48):
            b, a = stack.pop(), stack.pop()
            stack.append(a-b if op == 0x0b else a+b if op == 0x47 else a < b)
        elif op == 0x9d:
            if stack.pop(): at += struct.unpack("<h", payload)[0]
        elif op == 0x3e:
            result = stack.pop()
            assert not stack, stack
            return result
        else: raise AssertionError(hex(op))
    assert not stack, stack


class Item:
    def __init__(self, name, amount, cost, **extra):
        self.name = name
        self.props = dict(max_h_rest=amount, heal_cost=cost, use_count=1, _effects=[], **extra)
    def getProp(self, key): return self.props.get(key, 0)


def run(entries, bag, war, array="healArr", max_ap=100):
    gamer = NS(apManager=NS(maxAP=max_ap))
    master = NS(currentLocation=NS(warStatus=war), gamer=gamer)
    global_obj = NS(lol=NS(core=NS(Master=NS(getInstance=lambda: master))))
    equip = NS(bag=NS(chekExist=lambda item: item in bag))
    original_array = [dict(item=i, max_h_rest=i.props["max_h_rest"]) for i in sorted(entries, key=lambda i:i.props["max_h_rest"])]
    setattr(equip, array, original_array)
    sent = []
    original = "__quickHealOrig" if array == "healArr" else "__quickEatOrig"
    setattr(equip, original, lambda: sent.append(getattr(equip, array)[0]["item"].name))
    env = {"this":equip, "_global":global_obj}
    env["__quickMedPick"] = lambda equip, entries: execute(w.fn_quick_med_pick().assemble(), dict(equip=equip, entries=entries, _global=global_obj))
    execute(w.fn_quick_med_use(array, original).assemble(), env)
    assert getattr(equip, array) is original_array, "original arrays must be restored"
    return sent

peace = Item("peace", 500, 0)
combat = Item("combat", 150, 6)
buff = Item("buff", 1000, 0, bonus_act_time=300)
check("battle excludes peace medicine and buffs", run([peace, combat, buff], [peace, combat, buff], True), ["combat"])
check("peace prefers ordinary medicine in the bag", run([peace, combat, buff], [peace, combat, buff], False), ["peace"])
check("peace bag medicine beats stronger hand medicine", run([peace, Item("hand", 900, 0)], [peace], False), ["peace"])
check("peace falls back to combat medicine when no ordinary one exists", run([combat], [combat], False), ["combat"])
check("battle does not fall back to forbidden peace medicine", run([peace], [peace], True), [])
check("buffs alone cause no automatic use", run([buff], [buff], False), [])
# HealItem stores effects in _effects, not the original wire field.
effect = Item("effect", 999, 4); effect.props["_effects"] = [1]
check("client effect property excluded", run([effect, combat], [effect, combat], True), ["combat"])
check("too expensive battle item is skipped", run([combat], [combat], True, max_ap=5), [])
check("strongest eligible medicine is selected", run([combat, Item("strong", 200, 8)], [combat], True), ["strong"])
check("empty inventory is safe", run([], [], False), [])
check("stamina hotkey uses the same filtering", run([peace, combat, buff], [peace, combat, buff], True, array="eatArr"), ["combat"])
check("both wrappers included in client injection", all(n.encode() in w.injected() for n in ("__quickHealOrig", "__quickEatOrig", "__quickMedPick")), True)
# Cross-check client filtering against the effective server catalogue.
if os.environ.get("LAVA_RES"):
    import items
    mismatch = []
    categories = []
    for t, (root, name) in items.catalogue().items():
        if root != items.HEAL:
            continue
        p = items.params_of(t)
        if name.startswith(("Med_Battle_", "Med_Pacific_")):
            if bool(p.get("heal_cost")) != name.startswith("Med_Battle_"):
                categories.append(t)
        if not items.stimulant_unavailable(t):
            continue
        obj = Item.__new__(Item)
        obj.name = str(t)
        obj.props = dict(p, use_count=1, _effects=p.get("effects", []))
        for war in (False, True):
            if run([obj], [obj], war):
                mismatch.append((t, war))
    check("client skips every stimulant currently blocked by server", mismatch, [])
    check("battle/peace category agrees with all current medical item data", categories, [])
empty = Item("empty", 1000, 6); empty.props["use_count"] = 0
check("empty doses never block the next eligible medicine", run([empty, combat], [empty, combat], True), ["combat"])
if fails:
    print("\n".join(fails)); sys.exit(1)
