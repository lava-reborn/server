#!/usr/bin/env python3
"""What the journal of money says: where afro and gold come from and go.

Every change of a purse is one row of money_ledger (server/accounts.py
book): the character, his level at the time, the source -- a quest
and its type, a stall, c_ga, a letter, the auction, a barter, a death, the
admin panel ... (accounts.LEDGER_SOURCES) -- and the amounts. This sums the
rows three ways, the plan's gate «краны <= стоки» (correction б):

  * per source: what came in (the taps, positive) and what went out (the
    drains, negative), afro and gold apart, and how many rows;
  * per level band and source: the belts of the plan (0-8, 9-12, 13-16,
    17-18, 19-20, 21+), by the level the character had at each change;
  * per day and source: the calendar day in UTC (day_of). The server's
    daily reset is at UTC midnight today (server.DAILY_RESET_TIME 0), so
    it is the game's day too; should the reset move, move day_of with it.

The purses the characters had when the ledger began (source "opening",
accounts.open_ledger) are a stock, not a flow: they are summed on a line of
their own and kept out of the three tables.

Money moved between a purse and a clan's treasury is not money made or
destroyed either: afro put into a treasury or taken out of it (source
"clan"), and a disbanded clan's treasury paid into a purse ("clan_disband"),
are the same afro on both sides. They are TRANSFERS, summed in a table of
their own and kept out of the taps, the drains and the three tables. The
treasuries have a journal of their own (clan_ledger, accounts.
CLAN_LEDGER_SOURCES), and the report reads it as well:

  * deposit / withdraw: the other side of a "clan" row -- a transfer;
  * disband: a transfer when the treasury was paid into a purse (the
    "clan_disband" rows of that clan), a drain for what was not -- the
    treasury of a clan whose last member was deleted with his account
    (tools/admin_account.py);
  * diplomacy: a change of stance paid for -- a drain (a sink);
  * admin: the admin panel's adjustment -- a tap or a drain by its sign.

What the treasuries hold now is a stock, as the opening purses are, and is
shown beside what their journal adds up to. The founding fee of a clan
(10 G, "clan_create") is a purse's drain like any other and stays in the
tables. The whole economy's taps and drains -- the purses' and the
treasuries', transfers left out -- close the report.

Gold is kept in hundredths of an ounce, as everywhere, and printed in
ounces; silver is printed once there is any.

    python3 tools/money_report.py                 # the last 7 days
    python3 tools/money_report.py --days 1
    python3 tools/money_report.py --days 0        # the whole ledger
    python3 tools/money_report.py --db data/lava.db --char 42

Where the data lives is the environment's business, as it is for the
server: LAVA_DB_URL picks Postgres, its absence the SQLite file (--db, or
data/lava.db next to this checkout).
"""
import argparse
import collections
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))

import accounts  # noqa: E402  (needs the path above)

# The plan's belts of levels (LAVA-план-восстановления-игры.md, «Принципы» 12).
BANDS = ((0, 8), (9, 12), (13, 16), (17, 18), (19, 20))
DAY = 86400


def band_of(level):
    level = int(level or 0)
    for lo, hi in BANDS:
        if lo <= level <= hi:
            return "%d-%d" % (lo, hi)
    return "%d+" % (BANDS[-1][1] + 1)


def day_of(at):
    """The calendar day in UTC of a unix time (the module's docstring)."""
    return time.strftime("%Y-%m-%d", time.gmtime(int(at)))


class Sum:
    """Taps and drains of one cell of a table."""
    __slots__ = ("rows", "afro_in", "afro_out", "gold_in", "gold_out", "silver")

    def __init__(self):
        self.rows = self.afro_in = self.afro_out = 0
        self.gold_in = self.gold_out = self.silver = 0

    def add(self, row):
        self.rows += 1
        a, g = int(row["afro"]), int(row.get("gold") or 0)
        self.afro_in += max(a, 0)
        self.afro_out += min(a, 0)
        self.gold_in += max(g, 0)
        self.gold_out += min(g, 0)
        self.silver += int(row.get("silver") or 0)

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


OPENING = "opening"
# A purse's rows that move afro to or from a clan's treasury (the module's
# docstring): transfers, never a tap or a drain.
TRANSFERS = ("clan", "clan_disband")


def summarize(rows):
    """{"source": {source: Sum}, "band": {(band, source): Sum},
    "day": {(day, source): Sum}, "total": Sum, "opening": Sum,
    "transfer": {source: Sum}} of ledger rows; the opening balances are in
    "opening" alone, the moves to and from a clan's treasury in "transfer"
    alone."""
    out = {"source": collections.defaultdict(Sum), "band": collections.defaultdict(Sum),
           "day": collections.defaultdict(Sum), "total": Sum(), "opening": Sum(),
           "transfer": collections.defaultdict(Sum)}
    for row in rows:
        src = row["source"]
        if src == OPENING:
            out["opening"].add(row)
            continue
        if src in TRANSFERS:
            out["transfer"][src].add(row)
            continue
        out["source"][src].add(row)
        out["band"][band_of(row["level"]), src].add(row)
        out["day"][day_of(row["at"]), src].add(row)
        out["total"].add(row)
    return out


# --- the clans' treasuries (clan_ledger) -------------------------------------------
TAP, DRAIN, TRANSFER = "tap", "drain", "transfer"


def treasury_rows(store, since=0, char_id=None):
    """The treasuries' journal since a time, oldest first: of every clan, or
    the rows one character made (char_id: who put in, took out, paid)."""
    if char_id is None:
        return [dict(r) for r in store.db.execute(
            "SELECT * FROM clan_ledger WHERE at >= ? ORDER BY id", (int(since),))]
    return [dict(r) for r in store.db.execute(
        "SELECT * FROM clan_ledger WHERE char_id = ? AND at >= ? ORDER BY id",
        (int(char_id), int(since)))]


def payouts(store):
    """{clan id: afro} a disbanded clan's treasury paid into purses (the
    money_ledger rows "clan_disband", whose ref is the clan) -- all of them,
    whatever the window, as they settle a disband row of any day. A clan's
    id is never handed out again (clans AUTOINCREMENT), so the clan is
    enough to pair them."""
    return {int(r["ref"]): int(r["afro"] or 0) for r in store.db.execute(
        "SELECT ref, SUM(afro) AS afro FROM money_ledger WHERE source = ?"
        " GROUP BY ref", ("clan_disband",))}


def treasury_stock(store):
    """What the treasuries hold now and what their journal adds up to:
    {"clans": n, "afro": sum of clans.afro, "journal": the journal's sum over
    the same clans, "off": [(clan id, name, afro, journal)] where the two
    disagree}. They agree while every write of a treasury is booked, as
    every one is in the same transaction (accounts.Store, the clan section)."""
    booked = {int(r["clan_id"]): int(r["afro"] or 0) for r in store.db.execute(
        "SELECT clan_id, SUM(afro) AS afro FROM clan_ledger GROUP BY clan_id")}
    out = {"clans": 0, "afro": 0, "journal": 0, "off": []}
    for r in store.db.execute("SELECT id, name, afro FROM clans ORDER BY id"):
        cid, afro = int(r["id"]), int(r["afro"] or 0)
        out["clans"] += 1
        out["afro"] += afro
        out["journal"] += booked.get(cid, 0)
        if booked.get(cid, 0) != afro:
            out["off"].append((cid, r["name"], afro, booked.get(cid, 0)))
    return out


def summarize_treasury(rows, paid_out=None):
    """{"source": {source: Sum}, "kind": {tap / drain / transfer: Sum}} of
    clan_ledger rows (the module's docstring for which is which). paid_out
    is payouts(): of a disband row, what went into a purse is a transfer
    and the rest a drain -- each clan's payout is spent on its disband rows
    once."""
    left = dict(paid_out or {})
    out = {"source": collections.defaultdict(Sum), "kind": collections.defaultdict(Sum)}
    for row in rows:
        src, afro = row["source"], int(row["afro"])
        out["source"][src].add({"afro": afro})
        if src in ("deposit", "withdraw"):
            out["kind"][TRANSFER].add({"afro": afro})
        elif src == "disband":
            cid = int(row["clan_id"])
            paid = max(0, min(-afro, left.get(cid, 0)))
            left[cid] = left.get(cid, 0) - paid
            if paid:
                out["kind"][TRANSFER].add({"afro": -paid})
            if -afro - paid:
                out["kind"][DRAIN].add({"afro": afro + paid})
        elif src == "diplomacy":
            out["kind"][DRAIN].add({"afro": afro})
        else:
            # admin, and any source a later package adds: by its sign.
            out["kind"][TAP if afro > 0 else DRAIN].add({"afro": afro})
    return out


def ounces(hundredths):
    return "%.2f" % (hundredths / 100.0)


def table(title, cells, key_names):
    lines = [title, "  %-28s %6s %12s %12s %10s %10s" % (
        " / ".join(key_names), "rows", "afro +", "afro -", "G +", "G -")]
    for key in sorted(cells):
        s = cells[key]
        label = " / ".join(key) if isinstance(key, tuple) else key
        lines.append("  %-28s %6d %12d %12d %10s %10s%s" % (
            label, s.rows, s.afro_in, s.afro_out, ounces(s.gold_in), ounces(s.gold_out),
            "  silver %+d" % s.silver if s.silver else ""))
    return "\n".join(lines)


def afro_table(title, cells, key_name):
    lines = [title, "  %-28s %6s %12s %12s" % (key_name, "rows", "afro +", "afro -")]
    for key in sorted(cells):
        s = cells[key]
        lines.append("  %-28s %6d %12d %12d" % (key, s.rows, s.afro_in, s.afro_out))
    return "\n".join(lines)


def treasury_report(clan_rows, paid_out=None, stock=None):
    """The treasuries' part of the report: the journal by source and by what
    it is to the economy, and the stock."""
    t = summarize_treasury(clan_rows, paid_out)
    k = t["kind"]
    tap, drain, moved = k.get(TAP, Sum()), k.get(DRAIN, Sum()), k.get(TRANSFER, Sum())
    lines = ["Clan treasuries (clan_ledger): %d changes; taps +%d, drains %d;"
             " transfers with purses %+d (in %d, out %d)"
             % (sum(s.rows for s in t["source"].values()), tap.afro_in + tap.afro_out,
                drain.afro_in + drain.afro_out, moved.afro_in + moved.afro_out,
                moved.afro_in, moved.afro_out)]
    if stock is not None:
        lines.append("treasuries now: %d clans hold %d afro; their journal adds up to %d%s"
                     % (stock["clans"], stock["afro"], stock["journal"],
                        "" if not stock["off"] else "; OFF: " + ", ".join(
                            "%s %r holds %d, journal %d" % off for off in stock["off"])))
    return "\n".join(lines) + "\n\n" + afro_table("Clan treasuries by source:", t["source"],
                                                  "source")


def report(rows, clan_rows=None, paid_out=None, stock=None):
    s = summarize(rows)
    t = s["total"]
    head = ("%d changes of a purse: afro %+d (in %d, out %d), gold %s oz (in %s, out %s)"
            % (t.rows, t.afro_in + t.afro_out, t.afro_in, t.afro_out,
               ounces(t.gold_in + t.gold_out), ounces(t.gold_in), ounces(t.gold_out)))
    o = s["opening"]
    if o.rows:
        head += ("\nopening balances of %d characters: afro %d, gold %s oz"
                 % (o.rows, o.afro_in + o.afro_out, ounces(o.gold_in + o.gold_out)))
    moved = s["transfer"]
    if moved:
        n = sum(x.rows for x in moved.values())
        into = sum(x.afro_out for x in moved.values())
        back = sum(x.afro_in for x in moved.values())
        head += ("\n%d moves between purses and clan treasuries (transfers, not taps or"
                 " drains): afro %d into treasuries, %d out of them" % (n, -into, back))
    parts = [head,
             table("By source:", s["source"], ["source"]),
             table("By level band and source:", s["band"], ["band", "source"]),
             table("By day (UTC) and source:", s["day"], ["day", "source"])]
    if moved:
        parts.append(table("Transfers with clan treasuries:", moved, ["source"]))
    if clan_rows is not None:
        parts.append(treasury_report(clan_rows, paid_out, stock))
        k = summarize_treasury(clan_rows, paid_out)["kind"]
        tap, drain = k.get(TAP, Sum()), k.get(DRAIN, Sum())
        parts.append("The whole economy, purses and treasuries, transfers left out:"
                     " afro taps +%d, drains %d; gold taps +%s oz, drains %s oz"
                     % (t.afro_in + tap.afro_in, t.afro_out + drain.afro_out,
                        ounces(t.gold_in), ounces(t.gold_out)))
    return "\n\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=7.0,
                        help="how far back, in days; 0 is the whole ledger (default 7)")
    parser.add_argument("--char", type=int, default=None, help="one character's rows only")
    parser.add_argument("--db", default=None,
                        help="the SQLite file (ignored when LAVA_DB_URL is set)")
    args = parser.parse_args(argv)
    since = 0 if args.days <= 0 else int(time.time() - args.days * DAY)
    store = accounts.Store(args.db) if args.db else accounts.Store()
    try:
        rows = store.ledger(args.char, since)
        clan_rows = treasury_rows(store, since, args.char)
        paid_out = payouts(store)
        stock = treasury_stock(store)
    finally:
        store.close()
    print(report(rows, clan_rows, paid_out, stock))
    return 0


if __name__ == "__main__":
    sys.exit(main())
