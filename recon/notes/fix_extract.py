import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/data/wiki_extract.py"
s = io.open(p, encoding="utf-8").read()

old_fn = s[s.index("def parse_tables(txt):"):s.index("def extract(title):")]
new_fn = '''def parse_tables(txt):
    """Walk the article's wikitables, tracking bold rows as section headers.

    Each wikitable is returned separately: an article often repeats a section
    name (e.g. "Первый режим стрельбы") across several tables, so merging them
    into one dict silently drops all but the last.

    Stat tables carry one column per quality tier (A / P / G), so each parameter
    maps to a list of per-tier values.
    """
    tables = []
    for block in re.findall(r"\{\|.*?\n\|\}", txt, re.S):
        columns, sections, cur = [], {}, "общие"
        for raw in re.split(r"\n\|-", block):
            heads = re.findall(r"^!\s*(?:scope=\\"col\\"\s*\|)?(.+)$", raw, re.M)
            if heads:
                columns = [h.strip() for h in heads]
                continue
            cells = re.findall(r"^\|\s?(.*)$", raw, re.M)
            cells = [c for c in cells if not c.startswith("}") and not c.startswith("-")]
            if not cells:
                continue
            key = cells[0].strip()
            vals = [value(c) for c in cells[1:]]
            if not key:
                continue
            if key.startswith("'''") and not any(v is not None for v in vals):
                cur = key.strip("'").strip()
                sections.setdefault(cur, {})
                continue
            sections.setdefault(cur, {})[key] = vals
        if sections:
            tables.append({"columns": columns[1:] if columns else [],
                           "sections": sections})
    return tables


'''
s = s.replace(old_fn, new_fn)

old_ex = s[s.index("def extract(title):"):s.index('if __name__ == "__main__":')]
new_ex = '''def extract(title):
    txt = wikitext(title)
    tables = parse_tables(txt)
    desc = ""
    m = re.search(r"==\s*Описание\s*==\s*\n(.+?)(?:\n==|\Z)", txt, re.S)
    if m:
        desc = m.group(1).strip()
    return {"title": title, "description": desc, "tables": tables}


'''
s = s.replace(old_ex, new_ex)
io.open(p, "w", encoding="utf-8").write(s)
print("extractor fixed")
