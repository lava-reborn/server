"""Login loads saved progress silently; later gains still reach notifications.

Execute the actual AVM1 wrappers from widescreen.py with the original
rp_info and event forwarders represented by callbacks. A slow login means
SpecSkillMessages is already listening when the first snapshot arrives.
The original SpecObject.value_bonus setter treats saved level 1 as a gain.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import widescreen as w  # noqa: E402
from testkit import check, fails  # noqa: E402


def execute(code, this, obj):
    """Small AVM1 executor for the emitted snapshot and forwarding guards."""
    env, stack, at = dict(this=this, obj=obj), [], 0
    while at < len(code):
        op = code[at]
        at += 1
        payload = b""
        if op >= 0x80:
            size, = struct.unpack_from("<H", code, at)
            at += 2
            payload = code[at:at + size]
            at += size
        if op == 0x96:
            p = 0
            while p < len(payload):
                kind = payload[p]
                p += 1
                if kind == 0:
                    end = payload.index(b"\0", p)
                    stack.append(payload[p:end].decode())
                    p = end + 1
                elif kind == 5:
                    stack.append(bool(payload[p]))
                    p += 1
                elif kind == 7:
                    stack.append(struct.unpack_from("<i", payload, p)[0])
                    p += 4
                else:
                    raise AssertionError("unexpected push type: %s" % kind)
        elif op == 0x1C:
            stack.append(env[stack.pop()])
        elif op == 0x4E:
            key, target = stack.pop(), stack.pop()
            stack.append(target.get(key))
        elif op == 0x4F:
            value, key, target = stack.pop(), stack.pop(), stack.pop()
            target[key] = value
        elif op == 0x52:
            method, target, count = stack.pop(), stack.pop(), stack.pop()
            stack.append(target[method](*[stack.pop() for _ in range(count)]))
        elif op == 0x17:
            stack.pop()
        elif op == 0x12:
            stack.append(not stack.pop())
        elif op == 0x9D:
            if stack.pop():
                at += struct.unpack("<h", payload)[0]
        else:
            raise AssertionError("unexpected opcode: %02x" % op)
    if stack:
        raise AssertionError("wrapper leaked stack values")


METHODS = ("increase_skill_func", "increase_level_func",
           "increase_spec_func", "increase_spec_level_func")


def character():
    attrs, notices, queued, redraws = {}, [], [], []
    for method in METHODS:
        def forward(event, method=method):
            (queued if attrs.get("war") else notices).append((method, event))
        attrs["__progress_" + method] = forward

    def snapshot(frame):
        attrs["values"] = frame["values"]
        for method, value in frame["events"]:
            execute(w.fn_progress_event("__progress_" + method).assemble(), attrs, value)
        redraws.append(frame["values"])

    attrs["__progressInfoOrig"] = snapshot
    return attrs, notices, queued, redraws


# --- actual bytecode: initial load and subsequent updates ------------------
saved = dict(values=dict(skill_xp=195, spec_xp=86, spec_level=1),
             events=list(zip(METHODS, (195, 4, 86, 1))))
later = dict(values=dict(skill_xp=205, spec_xp=91, spec_level=2),
             events=list(zip(METHODS, (10, 5, 5, 2))))
for war in (False, True):
    attrs, notices, queued, redraws = character()
    attrs["war"] = war
    execute(w.fn_progress_snapshot().assemble(), attrs, saved)
    check("slow login, war=%s: saved values load and redraw without notices or queued gains" % war,
          (attrs["values"], redraws, notices, queued), (saved["values"], [saved["values"]], [], []))
    execute(w.fn_progress_snapshot().assemble(), attrs, later)
    check("war=%s: genuine gains and level-ups retain their original event payloads" % war,
          (notices, queued), ([], later["events"]) if war else (later["events"], []))
    # On leaving combat the original notification service flushes this queue.
    if war:
        notices.extend(queued)
        queued.clear()
        check("combat completion shows only gains earned after the login snapshot",
              notices, later["events"])
    fresh, new_notices, new_queued, new_redraws = character()
    execute(w.fn_progress_snapshot().assemble(), fresh, saved)
    check("a new character object has its own silent baseline after relogin or travel, war=%s" % war,
          (new_notices, new_queued, new_redraws), ([], [], [saved["values"]]))

attrs, notices, queued, redraws = character()
execute(w.fn_progress_snapshot().assemble(), attrs, dict(values=saved["values"], events=[]))
execute(w.fn_progress_snapshot().assemble(), attrs, later)
check("fast login without initial events still enables subsequent notifications", notices, later["events"])
execute(w.fn_progress_snapshot().assemble(), attrs, dict(values=later["values"], events=[]))
check("an unchanged repeated snapshot adds no notifications", notices, later["events"])
check("all five guards are installed in the client patch",
      all(s.encode() in w.injected() for s in ["__progressInfoOrig"]
          + ["__progress_" + method for method in METHODS]), True)

if fails:
    print("FAILED %d:\n%s" % (len(fails), "\n".join(fails)))
    sys.exit(1)
print("login notifications OK")
