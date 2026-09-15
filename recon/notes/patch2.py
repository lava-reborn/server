import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/data/wiki_extract.py"
s = io.open(p, encoding="utf-8").read()
old = '''            vals = [value(c) for c in cells[1:]]
            if key.startswith(BOLD) and not any(v is not None for v in vals):
                cur = key.strip("'").strip()
                sections.setdefault(cur, {})
                continue
            sections.setdefault(cur, {})[key.strip("'").strip()] = vals'''
new = '''            # A bold first cell always marks a section header row (the other
            # cells on such rows are empty, but stray "|" fragments from the
            # markup would otherwise make them look like real values).
            if key.startswith(BOLD):
                cur = key.strip("'").strip()
                sections.setdefault(cur, {})
                continue
            vals = [value(c) for c in cells[1:]]
            sections.setdefault(cur, {})[key.strip("'").strip()] = vals'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("patched")
