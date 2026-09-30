"""The names over the global map's cells, with the owner's edits laid on.

res/database/locations.xml is the player's own file: 414 rows of
<location x="…" y="…" text="…" /> that the client reads and draws over the map
itself. Nothing the server sends touches them, and the file is not ours to
ship, so the owner's edits (data/map_labels.json: hide a row, or give it
another text) are made at the moment the file is served:

  * by the player's launcher, launcher/MapLabels.cs, from the rules
    tools/export_map_labels.py writes and the build embeds;
  * by bootstrap_http, for a local run over the owner's own res/.

Both do the same thing, and both are tested against the same expectations:
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
    """[(x, y, was, new_text or None to hide)] -- a missing file is no edits."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return []
    out = []
    for e in doc.get("labels", []):
        hide = bool(e.get("hide"))
        text = e.get("text")
        if hide == (text is not None):
            raise ValueError("map_labels: %r must either hide or give a text" % e)
        for s in (e["was"], text or ""):
            if "\t" in s or "\n" in s or "\r" in s:
                raise ValueError("map_labels: tab or line break in %r" % s)
        out.append((int(e["x"]), int(e["y"]), e["was"], None if hide else text))
    return out


def apply(raw, edits=None):
    """locations.xml bytes with the edits made; (bytes, rows changed)."""
    edits = load() if edits is None else edits
    if not edits:
        return raw, 0
    want = {(x, y, was): new for x, y, was, new in edits}
    changed = 0

    def one(m):
        nonlocal changed
        row = m.group(0)
        attrs = {k.decode(): v for k, v in ATTR.findall(row)}
        try:
            key = (int(attrs["x"]), int(attrs["y"]),
                   html.unescape(attrs["text"].decode("utf-8")))
        except (KeyError, ValueError):
            return row
        if key not in want:
            return row
        changed += 1
        new = want[key]
        if new is None:
            return b""
        value = escape(new).encode("utf-8")
        return ATTR.sub(lambda a: a.group(0) if a.group(1) != b"text"
                        else b'text="' + value + b'"', row)

    return ROW.sub(one, raw), changed


def export_rules(edits=None):
    """The launcher's form of the edits: one tab-separated line each,
    x, y, was, then 'hide' or 'text' and the new text."""
    edits = load() if edits is None else edits
    lines = ["# data/map_labels.json for launcher/MapLabels.cs: x, y, was, hide|text, new text"]
    for x, y, was, new in edits:
        lines.append("\t".join((str(x), str(y), was, "hide" if new is None else "text", new or "")))
    return "\n".join(lines) + "\n"
