"""A run of the suites as a table: mechanic, test, check, status, time.

    python tools/suite_report.py D:\\lava_suite

Reads what tools/suite.py left in the directory: summary.txt (exit code,
seconds, name per suite), <suite>.jsonl (one line per check, written by
server/testkit.py) and <suite>.out (the suite's own output, for a crash or a
suite with no checks of its own). Writes report.html beside them, and prints
the same table, shorter, to the terminal.

A suite's status is its exit code: a check can pass and the suite still
fail after it (a crash, a server that did not start), and the report says
so rather than showing a column of green.
"""
import html
import json
import os
import sys
from collections import OrderedDict


def read_summary(out):
    rows = OrderedDict()
    path = os.path.join(out, "summary.txt")
    if not os.path.exists(path):
        return rows
    for line in open(path, encoding="utf-8-sig"):
        parts = line.split()
        if len(parts) == 3 and parts[1].endswith("s"):
            rows[parts[2]] = dict(code=int(parts[0]), seconds=int(parts[1][:-1]))
    return rows


def read_checks(out, name):
    path = os.path.join(out, name + ".jsonl")
    if not os.path.exists(path):
        return []
    out_rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out_rows.append(json.loads(line))
            except ValueError:
                pass
    return out_rows


def tail(out, name, n=40):
    for ext in (".out", ".err"):
        path = os.path.join(out, name + ext)
        if os.path.exists(path):
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            text = "\n".join(lines[-n:]).strip()
            if text:
                yield ext[1:], text


def collect(out):
    suites = []
    for name, s in read_summary(out).items():
        checks = read_checks(out, name)
        sections = OrderedDict()
        for c in checks:
            sections.setdefault(c.get("section") or "(без раздела)", []).append(c)
        failed = [c for c in checks if not c.get("ok")]
        mech = checks[0]["mechanic"] if checks else name
        suites.append(dict(name=name, code=s["code"], seconds=s["seconds"], mechanic=mech,
                           checks=checks, sections=sections, failed=failed))
    suites.sort(key=lambda x: (x["code"] == 0, -x["seconds"]))
    return suites


def fmt_secs(s):
    s = float(s)
    if s < 1:
        return "%.2f с" % s
    if s < 90:
        return "%.1f с" % s
    return "%d мин %02d с" % divmod(int(round(s)), 60)


CSS = """
:root { --bg:#fbfbfa; --fg:#1d1d1b; --mute:#6b6b66; --line:#e3e2dd; --card:#ffffff;
        --ok:#2f7d4a; --bad:#b3261e; --bad-bg:#fbeceb; --bar:#c9c8c1; }
@media (prefers-color-scheme: dark) { :root { --bg:#161615; --fg:#ecebe6; --mute:#9a9992;
        --line:#2e2e2b; --card:#1e1e1c; --ok:#6cc58b; --bad:#ff8a80; --bad-bg:#3a1f1d; --bar:#4a4a45; } }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif; margin:0; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:20px; margin:0 0 4px; } .sub { color:var(--mute); margin-bottom:20px; }
.totals { display:flex; gap:24px; flex-wrap:wrap; margin-bottom:20px; }
.totals div b { display:block; font-size:22px; }
details { background:var(--card); border:1px solid var(--line); border-radius:8px; margin:6px 0; }
summary { cursor:pointer; padding:8px 12px; display:grid;
          grid-template-columns: 18px 1fr 170px 90px 90px; gap:10px; align-items:center; }
summary .mech { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
summary .name, .num { color:var(--mute); font-variant-numeric:tabular-nums; }
.dot { width:10px; height:10px; border-radius:50%; background:var(--ok); }
.bad .dot, .dot.bad { background:var(--bad); }
table { width:100%; border-collapse:collapse; }
td, th { padding:4px 12px; border-top:1px solid var(--line); vertical-align:top; text-align:left; }
th { color:var(--mute); font-weight:500; }
td.t { width:90px; text-align:right; font-variant-numeric:tabular-nums; color:var(--mute); }
td.s { width:30px; }
tr.sec td { background:var(--bg); font-weight:600; }
tr.fail td { background:var(--bad-bg); }
pre { white-space:pre-wrap; word-break:break-word; margin:4px 0; font-size:12px; }
.bar { height:4px; background:var(--bar); border-radius:2px; margin-top:2px; }
"""


def render_html(out, suites):
    total = sum(s["seconds"] for s in suites)
    bad = [s for s in suites if s["code"] != 0]
    nchecks = sum(len(s["checks"]) for s in suites)
    nfail = sum(len(s["failed"]) for s in suites)
    e = html.escape
    parts = ["<!doctype html><html lang=ru><meta charset=utf-8>",
             "<meta name=viewport content='width=device-width,initial-scale=1'>",
             "<title>Прогон тестов</title><style>%s</style><main>" % CSS,
             "<h1>Прогон тестов</h1><div class=sub>%s</div>" % e(os.path.abspath(out)),
             "<div class=totals><div><b>%d</b>наборов</div><div><b>%d</b>упало</div>"
             "<div><b>%d</b>проверок</div><div><b>%d</b>не прошло</div>"
             "<div><b>%s</b>сумма времени</div></div>"
             % (len(suites), len(bad), nchecks, nfail, fmt_secs(total))]
    for s in suites:
        cls = "bad" if s["code"] != 0 else ""
        ok_n = len(s["checks"]) - len(s["failed"])
        parts.append("<details class='%s'%s><summary><span class=dot></span>"
                     "<span class=mech>%s</span><span class=name>%s</span>"
                     "<span class=num>%d/%d</span><span class=num>%s</span></summary>"
                     % (cls, " open" if cls else "", e(s["mechanic"]), e(s["name"]),
                        ok_n, len(s["checks"]), fmt_secs(s["seconds"])))
        parts.append("<table><tr><th></th><th>проверка</th><th style='text-align:right'>время</th></tr>")
        for sec, rows in s["sections"].items():
            spent = sum(r.get("seconds", 0) for r in rows)
            parts.append("<tr class=sec><td></td><td>%s</td><td class=t>%s</td></tr>"
                         % (e(sec), fmt_secs(spent)))
            for r in rows:
                fail = not r.get("ok")
                extra = ""
                if fail:
                    extra = "<pre>got  %s\nwant %s</pre>" % (e(r.get("got", "")), e(r.get("want", "")))
                parts.append("<tr class='%s'><td class=s><span class='dot%s'></span></td>"
                             "<td>%s%s</td><td class=t>%s</td></tr>"
                             % ("fail" if fail else "", " bad" if fail else "",
                                e(r["check"]), extra, fmt_secs(r.get("seconds", 0))))
        if s["code"] != 0 and not s["failed"]:
            for kind, text in tail(out, s["name"]):
                parts.append("<tr class=fail><td></td><td><pre>%s: %s</pre></td><td></td></tr>"
                             % (kind, e(text)))
        parts.append("</table></details>")
    parts.append("</main></html>")
    path = os.path.join(out, "report.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    return path


def render_text(suites):
    lines = []
    for s in suites:
        mark = "ok " if s["code"] == 0 else "BAD"
        ok_n = len(s["checks"]) - len(s["failed"])
        mech = s["mechanic"]
        if len(mech) > 60:
            mech = mech[:57] + "..."
        lines.append("%s %-24s %-60s %4d/%-4d %s" % (mark, s["name"], mech, ok_n,
                                                   len(s["checks"]), fmt_secs(s["seconds"])))
        for c in s["failed"][:5]:
            lines.append("      x [%s] %s" % (c.get("section") or "-", c["check"]))
    return "\n".join(lines)


def main(out):
    suites = collect(out)
    path = render_html(out, suites)
    print(render_text(suites))
    print("report: %s" % path)
    return 0 if all(s["code"] == 0 for s in suites) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
