"""Change one row of a hand-kept JSON table and leave every other byte alone.

data/passages.json, data/map_labels.json and the like are written by hand:
long 'why' lines kept on one line, cell lists kept on one line, a section
compact where its rows are short. json.dump would rewrite all of it, and a
diff of one new way would be a diff of the whole file. set_key finds the
member by its path in the text itself (json's own raw_decode for every
value, so nothing is parsed twice and nothing is guessed), replaces its
value or adds it at the end of its object, and returns the text with only
those lines changed. The value is written as the table's own rows are: one
space more per level, a list of numbers or of lists of numbers on one line.

    text = set_key(text, ["walk_in", "102"], [{"cells": [[3, 4]], ...}])
    text = set_key(text, ["doors", "1381", "a"], {"target_loc_id": 102, ...})

A path that does not exist yet is made, object by object.

delete_key takes a member out the same way, and an object left with nothing
in it is written {} again. A list of rows written one row a line -- the
labels of data/map_labels.json -- is worked on row by row: items() gives
each row's span, append_item adds a row after the last one (its text as the
caller lays it out), remove_item takes one out with its comma.

    text = delete_key(text, ["walk_in", "102"])
    text = append_item(text, ["labels"], '{"x": 1, "y": 2, "text": "A", "add": true}')
"""
import json

_DEC = json.JSONDecoder()
WS = " \t\r\n"


def _skip(text, i):
    while i < len(text) and text[i] in WS:
        i += 1
    return i


def _members(text, start):
    """([(key, key_at, value_at, value_end)], closing brace index) of the
    object whose '{' is at start."""
    if text[start] != "{":
        raise ValueError("jsonrows: no object at %d" % start)
    out = []
    i = _skip(text, start + 1)
    if text[i] == "}":
        return out, i
    while True:
        key, j = _DEC.raw_decode(text, i)
        j = _skip(text, j)
        if text[j] != ":":
            raise ValueError("jsonrows: no ':' after %r" % key)
        vs = _skip(text, j + 1)
        _value, ve = _DEC.raw_decode(text, vs)
        out.append((key, i, vs, ve))
        k = _skip(text, ve)
        if text[k] == ",":
            i = _skip(text, k + 1)
            continue
        if text[k] != "}":
            raise ValueError("jsonrows: no ',' or '}' after %r" % key)
        return out, k


def _line_indent(text, at):
    """The spaces the line holding text[at] starts with."""
    s = text.rfind("\n", 0, at) + 1
    e = s
    while e < len(text) and text[e] in " \t":
        e += 1
    return text[s:e]


def _flat(v):
    return not isinstance(v, (dict, list)) or (
        isinstance(v, list) and all(not isinstance(x, (dict, list)) or
                                    (isinstance(x, list) and all(not isinstance(y, (dict, list)) for y in x))
                                    for x in v))


def dump(value, indent, nl="\n"):
    """value as the tables write it, its first line unindented and every
    further one under indent, one space more per level."""
    if _flat(value):
        return json.dumps(value, ensure_ascii=False)
    inner = indent + " "
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = ["%s%s: %s" % (inner, json.dumps(str(k), ensure_ascii=False), dump(v, inner, nl))
                for k, v in value.items()]
        return "{" + nl + ("," + nl).join(rows) + nl + indent + "}"
    rows = [inner + dump(v, inner, nl) for v in value]
    return "[" + nl + ("," + nl).join(rows) + nl + indent + "]"


def _nest(path, value):
    for key in reversed(path):
        value = {key: value}
    return value


def set_key(text, path, value):
    """text with the member at path (a list of keys) set to value: its old
    value replaced where it has one, else added last in its object, the
    objects on the way made where they are missing. Every byte outside that
    member stays as it was."""
    nl = "\r\n" if "\r\n" in text else "\n"
    at = _skip(text, 0)
    for depth, key in enumerate(path):
        members, close = _members(text, at)
        hit = [m for m in members if m[0] == key]
        if hit and depth < len(path) - 1:
            at = hit[0][2]
            if text[at] != "{":
                raise ValueError("jsonrows: %r is not an object" % key)
            continue
        new_value = value if depth == len(path) - 1 else _nest(path[depth + 1:], value)
        if hit:
            _key, key_at, vs, ve = hit[0]
            if "\n" not in text[vs:ve]:
                # a row written on one line stays on one line
                return text[:vs] + json.dumps(new_value, ensure_ascii=False) + text[ve:]
            indent = _line_indent(text, key_at)
            return text[:vs] + dump(new_value, indent, nl) + text[ve:]
        if members:
            last_key_at, last_vs, last_end = members[-1][1], members[-1][2], members[-1][3]
            if text.rfind("\n", 0, last_key_at) < at:
                # an object written on one line stays on one line
                row = "%s: %s" % (json.dumps(key, ensure_ascii=False),
                                  json.dumps(new_value, ensure_ascii=False))
                return text[:last_end] + ", " + row + text[last_end:]
            indent = _line_indent(text, last_key_at)
            if text[last_vs] in "{[" and "\n" not in text[last_vs:last_end]:
                # its rows each on one line: so is the new one
                shown = json.dumps(new_value, ensure_ascii=False)
            else:
                shown = dump(new_value, indent, nl)
            row = "%s%s: %s" % (indent, json.dumps(key, ensure_ascii=False), shown)
            return text[:last_end] + "," + nl + row + text[last_end:]
        outer = _line_indent(text, at)
        indent = outer + " "
        row = "%s%s: %s" % (indent, json.dumps(key, ensure_ascii=False), dump(new_value, indent, nl))
        return text[:at] + "{" + nl + row + nl + outer + "}" + text[close + 1:]
    raise ValueError("jsonrows: an empty path")


def get_key(doc, path, default=None):
    """The value at path in a parsed document, or default."""
    for key in path:
        if not isinstance(doc, dict) or key not in doc:
            return default
        doc = doc[key]
    return doc


def _value_at(text, path):
    """Where the value at path starts in text, or None when a key on the
    way is missing. Every key but the last names an object."""
    at = _skip(text, 0)
    for key in path:
        if text[at] != "{":
            raise ValueError("jsonrows: %r is not in an object" % key)
        members, _close = _members(text, at)
        hit = [m for m in members if m[0] == key]
        if not hit:
            return None
        at = hit[0][2]
    return at


def delete_key(text, path):
    """text without the member at path, every other byte as it was; an
    object left empty is written {}. A path that is not there changes
    nothing."""
    if not path:
        raise ValueError("jsonrows: an empty path")
    at = _value_at(text, path[:-1]) if len(path) > 1 else _skip(text, 0)
    if at is None or text[at] != "{":
        return text
    members, close = _members(text, at)
    idx = [i for i, m in enumerate(members) if m[0] == path[-1]]
    if not idx:
        return text
    i = idx[0]
    if len(members) == 1:
        return text[:at] + "{}" + text[close + 1:]
    if i == 0:
        # from this key to the next one: the object's own opening stays
        return text[:members[0][1]] + text[members[1][1]:]
    # from the end of the row before to the end of this one: what followed
    # this row (a comma and the next, or the closing brace) stays
    return text[:members[i - 1][3]] + text[members[i][3]:]


def _items(text, start):
    """([(item_at, item_end)], closing bracket index) of the array at start."""
    if text[start] != "[":
        raise ValueError("jsonrows: no array at %d" % start)
    out = []
    i = _skip(text, start + 1)
    if text[i] == "]":
        return out, i
    while True:
        _value, e = _DEC.raw_decode(text, i)
        out.append((i, e))
        k = _skip(text, e)
        if text[k] == ",":
            i = _skip(text, k + 1)
            continue
        if text[k] != "]":
            raise ValueError("jsonrows: no ',' or ']' after an item at %d" % i)
        return out, k


def items(text, path):
    """[(value, at, end)] of the array at path: each row parsed, and where
    its text is."""
    at = _value_at(text, path)
    if at is None:
        raise ValueError("jsonrows: no %r" % (path,))
    spans, _close = _items(text, at)
    return [(_DEC.raw_decode(text, s)[0], s, e) for s, e in spans]


def append_item(text, path, item_text):
    """text with item_text (one row, laid out by the caller) added after the
    last row of the array at path, on a line of its own under the rows'
    indent; into an empty array it goes one space in from the array's line."""
    at = _value_at(text, path)
    if at is None or text[at] != "[":
        raise ValueError("jsonrows: no array at %r" % (path,))
    spans, close = _items(text, at)
    nl = "\r\n" if "\r\n" in text else "\n"
    if spans:
        last_at, last_end = spans[-1]
        indent = _line_indent(text, last_at)
        return text[:last_end] + "," + nl + indent + item_text + text[last_end:]
    outer = _line_indent(text, at)
    return text[:at] + "[" + nl + outer + " " + item_text + nl + outer + "]" + text[close + 1:]


def remove_item(text, path, index):
    """text without row `index` of the array at path, and the comma that
    went with it; an array left empty is written []."""
    at = _value_at(text, path)
    if at is None or text[at] != "[":
        raise ValueError("jsonrows: no array at %r" % (path,))
    spans, close = _items(text, at)
    if not 0 <= index < len(spans):
        raise ValueError("jsonrows: no row %d in %r" % (index, path))
    if len(spans) == 1:
        return text[:at] + "[]" + text[close + 1:]
    if index == 0:
        return text[:spans[0][0]] + text[spans[1][0]:]
    return text[:spans[index - 1][1]] + text[spans[index][1]:]
