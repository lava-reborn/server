"""Client patch: valid AVM1 branches, one injection, original artwork intact.

The online HUD shares the frame patch's handwritten AVM1. Verify every
function's branches within that function, then patch a small SWF fixture
twice: no accumulated wrappers, altered art or unrelated class changes.
CI intentionally carries no main.swf (deploy/ci/make_test_extras.sh).
When the real client is available, run the same checks on it as well.
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import widescreen as w  # noqa: E402
from testkit import check, fails  # noqa: E402


def validate(code):
    """Parse function envelopes separately; no jump may leave its body."""
    at, starts, targets, errors = 0, set(), [], []
    while at < len(code):
        starts.add(at)
        op = code[at]
        at += 1
        if op < 0x80:
            if op not in w.OPS.values():
                errors.append("unexpected action %02x" % op)
            continue
        size, = struct.unpack_from("<H", code, at)
        at += 2
        end = at + size
        if end > len(code):
            errors.append("truncated action")
            break
        if op == 0x9D:
            delta, = struct.unpack_from("<h", code, at)
            targets.append(end + delta)
        elif op == 0x9B:
            body_size, = struct.unpack_from("<H", code, end - 2)
            errors.extend(validate(code[end:end + body_size]))
            end += body_size
        elif op != 0x96:
            errors.append("unexpected long action %02x" % op)
        at = end
    starts.add(len(code))
    errors.extend("branch outside its function: %s" % target
                  for target in targets if target not in starts)
    if at != len(code):
        errors.append("function length mismatch")
    return errors


# --- bytecode, in process --------------------------------------------------
check("every HUD and frame branch lands inside its own function",
      validate(w.injected()), [])


def check_container(label, version, body):
    """The same file round trip for the fixture and the optional real client."""
    original = w.split_tags(body)
    patched = w.inject(list(original))
    w.patch_ceiling(patched, 3840, 2160)
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "main.swf")
        w.write_swf(path, version, w.join_tags(body[:w.header_len(body)], patched))
        check(label + ": the saved client verifies its code and dimensions",
              w.verify(path, 3840, 2160)[1] > 0, True)
        _, out = w.read_swf(path)
        actual = w.split_tags(out)
        check(label + ": applying the patch twice does not stack HUDs or wrappers",
              w.inject(actual), actual)
        # Both ceilings are normalized to the same value; everything else
        # except our marked DoAction and new bitmap must remain identical.
        w.patch_ceiling(original, 3840, 2160)
        keep = lambda tags: [t for t in w.without_online_art(tags)
                             if not (t[0] == 12 and w.MARK.encode() in t[1])]
        check(label + ": the patch preserves all artwork and unrelated scripts",
              keep(actual) == keep(original), True)


def fixture():
    """Minimal SWF tags, including a nested bitmap whose ID must stay reserved.

    The class-init action has the compiler's ConstantPool and Push register,
    constant8, integer / SetMember shape documented by patch_ceiling. It is
    only a container fixture, not an executable substitute for the client.
    """
    # RECT with one-bit coordinates, 25 fps, one frame.
    head = b"\x08\x00\x00\x19\x01\x00"
    pool = b"\x03\x00maxW\x00maxH\x00setMCSize\x00"
    actions = b"\x88" + struct.pack("<H", len(pool)) + pool
    for index, value in enumerate((1280, 1024)):
        actions += b"\x96\x09\x00\x04\x02\x08" + bytes([index])
        actions += b"\x07" + struct.pack("<i", value) + b"\x4f"
    actions += b"\x00"
    bitmap = (21, b"\x02\x00" + w.ONLINE_ASSET.read_bytes(), True)
    sprite = b"\x01\x00\x01\x00" + w.join_tags(
        b"", [bitmap, (1, b"", False), (0, b"", False)])
    # The settings window's frame and texture, which the online list
    # borrows by ID: empty shapes with a one-bit RECT are enough here.
    shapes = [(2, struct.pack("<H", ident) + b"\x08\x00\x00\x00\x00\x00", True)
              for ident in (581, 596)]
    tags = [(9, b"\x12\x34\x56", True)] + shapes + [
            (39, sprite, True),
            (56, b"\x01\x00\x02\x00fixtureIcon\x00", False),
            (59, b"\x01\x00" + actions, True),
            (12, b"\x07\x00", False),
            (1, b"", False), (0, b"", False)]
    return head, tags


# --- SWF fixture: always, including CI without the client ------------------
try:
    head, tags = fixture()
    patched = w.inject(list(tags))
    check("the HUD bitmap avoids both sprite and nested bitmap IDs",
          [struct.unpack_from("<H", payload)[0]
           for code, payload, _ in patched if code == 21], [3])
    check_container("fixture", 8, w.join_tags(head, tags))
except Exception:
    import traceback
    fails.append("SWF fixture check crashed:\n" + traceback.format_exc())


# --- real SWF container: the full client, when installed -------------------
res = os.environ.get("LAVA_RES", os.path.join(os.path.dirname(HERE), "..", "client", "res"))
src = os.path.join(res, "main.swf")
try:
    if os.path.exists(src):
        version, body = w.read_swf(src)
        check_container("real client", version, body)
    else:
        print("  --  main.swf not found at %s; real-client checks skipped;"
              " fixture checks ran above" % res)
except Exception:
    import traceback
    fails.append("SWF check crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("widescreen OK")
