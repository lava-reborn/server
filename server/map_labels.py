"""The names over the global map's cells, with the owner's edits laid on.

res/database/locations.xml holds 414 rows of <location x="…" y="…" text="…" />
that the client reads and draws over the map itself. Nothing the server sends
touches them, so the owner's edits (data/map_labels.json: hide a row, give
it another text, or add one -- the name of a place of ours, data/locations,
put on the map) are laid on the file itself:

  * by client/build.py, which puts the edited file into every client
    release, so the launcher installs it as it is (client/FORMAT.md);
  * by bootstrap_http, for a local run over the owner's own res/.

Launchers before the self-updating one did the same on the fly from the
rules export_rules() writes; it stays for them and for its test. Every
version is held to the same expectations:
the row whose cell and current text match an edit is dropped or retexted,
every other byte of the file stays as it was, and a row that does not match
exactly is left alone -- so a different copy of the client is never edited
by mistake.
"""
import html
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "map_labels.json")

# One row with the line break after it, so a hidden row leaves no blank line.
ROW = re.compile(rb'<location\b[^>]*?/>[ \t]*(?:\r?\n)?')
ATTR = re.compile(rb'\b(x|y|text)\s*=\s*"([^"]*)"')


def escape(s):
    """XML attribute escaping exactly as .NET's SecurityElement.Escape does it,
    so the launcher and this module produce the same bytes."""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def load(path=PATH):
    """[(x, y, was, new_text or None to hide)] -- a missing file is no edits.
    An added row is (x, y, None, text): it has no 'was'."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return []
    out = []
    for e in doc.get("labels", []):
        hide = bool(e.get("hide"))
        text = e.get("text")
        if e.get("add"):
            # A name over a cell that has none of this text: a place of ours
            # (data/locations) put on the map.
            if hide or "was" in e or not text:
                raise ValueError("map_labels: %r adds a row: a text, no 'was', no hide" % e)
            if "\t" in text or "\n" in text or "\r" in text:
                raise ValueError("map_labels: tab or line break in %r" % text)
            out.append((int(e["x"]), int(e["y"]), None, text))
            continue
        if hide == (text is not None):
            raise ValueError("map_labels: %r must either hide or give a text" % e)
        for s in (e["was"], text or ""):
            if "\t" in s or "\n" in s or "\r" in s:
                raise ValueError("map_labels: tab or line break in %r" % s)
        out.append((int(e["x"]), int(e["y"]), e["was"], None if hide else text))
    return out


def _key(row):
    """(x, y, text) of a row, entities decoded, or None."""
    attrs = {k.decode(): v for k, v in ATTR.findall(row)}
    try:
        return (int(attrs["x"]), int(attrs["y"]),
                html.unescape(attrs["text"].decode("utf-8")))
    except (KeyError, ValueError):
        return None


def apply(raw, edits=None):
    """locations.xml bytes with the edits made; (bytes, rows changed).

    An added row goes before </data>, in the file's own line ending, in the
    order of the edits; one whose cell already has a row of that text is
    not added twice."""
    edits = load() if edits is None else edits
    if not edits:
        return raw, 0
    want = {(x, y, was): new for x, y, was, new in edits if was is not None}
    adds = [(x, y, new) for x, y, was, new in edits if was is None]
    changed = 0

    def one(m):
        nonlocal changed
        row = m.group(0)
        key = _key(row)
        if key is None or key not in want:
            return row
        changed += 1
        new = want[key]
        if new is None:
            return b""
        value = escape(new).encode("utf-8")
        return ATTR.sub(lambda a: a.group(0) if a.group(1) != b"text"
                        else b'text="' + value + b'"', row)

    out = ROW.sub(one, raw)
    if adds:
        there = {_key(m.group(0)) for m in ROW.finditer(out)}
        eol = b"\r\n" if b"\r\n" in out else b"\n"
        rows = b""
        for x, y, text in adds:
            if (x, y, text) in there:
                continue
            there.add((x, y, text))
            rows += b'<location x="%d" y="%d" text="%s" />' % (x, y, escape(text).encode("utf-8")) + eol
            changed += 1
        if rows:
            end = out.rfind(b"</data>")
            if end < 0:
                raise ValueError("map_labels: no </data> to add a row before")
            out = out[:end] + rows + out[end:]
    return out, changed


def export_rules(edits=None):
    """The launcher's form of the edits: one tab-separated line each,
    x, y, was, then 'hide' or 'text' and the new text. An added row is not
    among them: the launchers that read these rules can only hide or
    retext, and the self-updating one installs the edited file itself."""
    edits = load() if edits is None else edits
    lines = ["# data/map_labels.json for launcher/MapLabels.cs: x, y, was, hide|text, new text"]
    for x, y, was, new in edits:
        if was is None:
            continue
        lines.append("\t".join((str(x), str(y), was, "hide" if new is None else "text", new or "")))
    return "\n".join(lines) + "\n"
