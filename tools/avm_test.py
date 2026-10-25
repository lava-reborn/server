"""Small AVM1 executor shared by emitted hotkey and medicine regression tests.

Only the instructions these patches emit are supported. This executes the
assembled bytecode, not a second Python implementation of the game rule.
It models key state and UI objects, not Windows focus or Flash rendering.
"""
import struct


class Arr(list):
    """AVM arrays also carry named properties such as code16."""

    def push(self, value):
        self.append(value)
        return len(self)


def get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    if isinstance(obj, list):
        if key == "length":
            return len(obj)
        if isinstance(key, int) or str(key).isdigit():
            return obj[int(key)] if 0 <= int(key) < len(obj) else None
    return getattr(obj, str(key), None)


def execute(code, env):
    stack, at = [], 0
    instructions = 0
    while at < len(code):
        instructions += 1
        if instructions > 100000:
            raise AssertionError("AVM test exceeded its instruction budget")
        op = code[at]
        at += 1
        payload = b""
        if op >= 128:
            size, = struct.unpack_from("<H", code, at)
            at += 2
            payload = code[at:at + size]
            at += size
        if op == 0x96:  # Push
            i = 0
            while i < len(payload):
                kind = payload[i]
                i += 1
                if kind == 0:
                    end = payload.index(b"\0", i)
                    stack.append(payload[i:end].decode())
                    i = end + 1
                elif kind in (2, 3):
                    stack.append(None)
                elif kind == 5:
                    stack.append(bool(payload[i]))
                    i += 1
                elif kind == 7:
                    stack.append(struct.unpack_from("<i", payload, i)[0])
                    i += 4
                else:
                    raise AssertionError(kind)
        elif op == 0x1C:  # GetVariable
            stack.append(env.get(stack.pop()))
        elif op == 0x4E:  # GetMember
            key, obj = stack.pop(), stack.pop()
            stack.append(get(obj, key))
        elif op == 0x4F:  # SetMember
            value, key, obj = stack.pop(), stack.pop(), stack.pop()
            if isinstance(obj, dict):
                obj[key] = value
            else:
                setattr(obj, str(key), value)
        elif op == 0x3C:  # DefineLocal
            value, key = stack.pop(), stack.pop()
            env[key] = value
        elif op in (0x52, 0x3D):  # CallMethod / CallFunction
            name = stack.pop()
            obj = stack.pop() if op == 0x52 else env
            count = stack.pop()
            args = [stack.pop() for _ in range(count)]
            stack.append(get(obj, name)(*args))
        elif op == 0x42:  # InitArray
            count = stack.pop()
            stack.append(Arr(stack.pop() for _ in range(count)))
        elif op == 0x43:  # InitObject
            count = stack.pop()
            result = {}
            for _ in range(count):
                value, key = stack.pop(), stack.pop()
                result[key] = value
            stack.append(result)
        elif op == 0x49:  # Equals2
            b, a = stack.pop(), stack.pop()
            stack.append(a == b)
        elif op == 0x12:  # Not
            stack.append(not stack.pop())
        elif op == 0x17:  # Pop
            stack.pop()
        elif op in (0x0B, 0x47, 0x48):  # Subtract / Add2 / Less2
            b, a = stack.pop(), stack.pop()
            if op == 0x0B:
                stack.append(a - b)
            elif op == 0x48:
                stack.append(a < b)
            else:
                stack.append(str(a) + str(b) if isinstance(a, str) or isinstance(b, str) else a + b)
        elif op == 0x9D:  # If
            if stack.pop():
                at += struct.unpack("<h", payload)[0]
        elif op == 0x3E:  # Return
            result = stack.pop()
            assert not stack, stack
            return result
        else:
            raise AssertionError(hex(op))
    assert not stack, stack
