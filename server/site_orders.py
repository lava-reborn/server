"""Stance steps ordered on the site: the rows lava-site writes into the
table site_orders (its api/db.py queue_stance), carried out by the game.

The site's «Дипломатия» panel (/cabinet) lets a character who holds the
right of diplomacy (0x2000, clans.R_DIPLOMACY) move his clan's stance toward
another clan by the game's own rules: one step within war..peace, 1 000 afro
up and 100 down (clans.STANCE_UP, STANCE_DOWN), out of the treasury. The
site does not make the step itself. Only this process can tell the clients
online (clan_admin.py's note), and two writers of one stance on Postgres
could both pass the step's checks: READ COMMITTED reads the subqueries of
its WHERE in the statement's snapshot. So the site writes intent, one row

    site_orders: id, made_at, login, char_id, clan_id, other, stat_from, dir

and polls its done_at, code and result for a few seconds, showing the
result to the player word for word. The game drains the table on every pass
of its admin loop (server.drain_admin_actions, after the admin's own rows),
and nothing from it ever reaches server.apply_admin_action: whatever a row
here holds, it can ask for one stance step and nothing else. On Postgres the
site writes with a role of its own that may read and insert into this one
table (lava-pg); the admin queue is out of its reach.

The site's checks are for its messages only. Every one is made again here,
in this order, from the database; the row is trusted for nothing but the
login it speaks for, and that is checked against the character:

  1. The shape: every column a whole number but login (a string) and
     made_at (a number); stat_from -1, 0 or 1, dir +1 or -1 -- else R7.
     SQLite keeps whatever it is given in a column of any type.
  2. The age: made more than MAX_AGE ago -- R6, and nothing else written.
     The site looks at the game's heartbeat before it inserts, not after,
     so without this a row made just before the game stopped would run
     whenever it came back, long after the page said it had not answered.
     Site and game share a host and its clock; a row from further ahead
     than that is one no site there wrote (R7).
  3. Who it speaks for: the character, whose account's login is the row's
     and is not banned -- else R7. Nothing here resolves a name.
  4. Which clan: the character's own (Store.clan_member), never the row's
     clan_id. None, or no 0x2000 -- R1; another than the row names -- R4.
  5. The other clan: still there, and not ours -- else R2.
  6. The step: stat_from + dir within war..peace -- else R3.
  7. The guard: our stance toward them still stat_from -- else R4.
  8. The write: Store.clan_stance_step with the order, so the step and the
     order's "done" commit together. A stop after the commit leaves a done
     row, never run again; a stop before it leaves nothing written and the
     row waiting, to run within the minute or be refused as too old. The
     write touching nothing: the treasury short -- R5; else R2 or R4, told
     apart as clan_diplomacy.step tells them.
  9. Then what the in-game button sends (clan_diplomacy.py): res=8 to every
     member of ours online, the actor too when he plays -- with no cmdAck,
     there being no command to answer -- each followed by the fresh tags of
     their members on his screen; res=9 to theirs; the new balance to our
     0x400 holders (clan_treasury.tell_balance). After the commit: a stop
     in between loses them, and the clients learn the stance at their next
     login (res=0, Clans.online).

A refusal writes its row's done_at, code and words and nothing else, so one
run again after a stop is harmless; an order answered already keeps the
answer it has. Every outcome goes to the log; no line goes to any chat, as
none goes from the in-game button.
"""
import logging
import math
import time

import clan_diplomacy
import clan_treasury
import clans

log = logging.getLogger("lava")

# Seconds a row may wait before it is refused (R6). The site polls for 3.5
# and then tells the player that the order cancels itself within a minute.
MAX_AGE = 60.0
# Rows carried out per pass of the admin loop (one a second).
BATCH = 20

# The words the site shows the player, and the log keeps. {clan} is ours,
# {other} theirs, {char} the character, {stance} a word of
# clan_diplomacy.STANCE_WORDS, {price} the afro with the original's dot.
TEXTS = {
    "OK": ("Готово: отношение клана «{clan}» к клану «{other}» теперь — {stance}."
           " Из казны списано {price} афро."),
    "R1": "У персонажа {char} нет права дипломатии в клане.",
    "R2": "Клана «{other}» больше нет.",
    "R3": "Отношение к клану «{other}» уже {stance}.",
    "R4": "Отношение к клану «{other}» уже изменилось. Обновите страницу.",
    "R5": "В казне клана «{clan}» меньше {price} афро.",
    "R6": ("Игровой сервер не успел выполнить приказ, отношения не изменились."
           " Попробуйте ещё раз."),
    "R7": "Приказ отклонён.",
}

_INTS = ("id", "char_id", "clan_id", "other", "stat_from", "dir")


def afro(n):
    """1000 -> «1.000»: the original's thousands dot (the site's too)."""
    return "{:,}".format(int(n)).replace(",", ".")


def _field(row, name):
    try:
        return row[name]
    except (KeyError, IndexError):
        return None


def _shaped(row):
    """Step 1: every column of the type the site writes it as. SQLite keeps
    what it is given in a column of any type (a text, a fraction); Postgres
    would not, but a row is not trusted to come from there."""
    if not all(clans._is_int(_field(row, c)) for c in _INTS):
        return False
    made = _field(row, "made_at")
    if isinstance(made, bool) or not isinstance(made, (int, float)) or not math.isfinite(made):
        return False
    login = _field(row, "login")
    if not isinstance(login, str) or not login:
        return False
    return (row["stat_from"] in (clan_diplomacy.WAR, clan_diplomacy.NEUTRAL,
                                 clan_diplomacy.PEACE)
            and row["dir"] in (1, -1))


def _other_name(store, other):
    """Their clan's name for the words, or its number when it is no more."""
    row = store.clan(other) if 0 < other <= store.CLAN_MAX_ID else None
    return row["name"] if row is not None else str(other)


def apply(store, clans_, row, now=None):
    """Carry out one order (steps 1-9 of the module's note): its done_at,
    code and words written, and the pushes of a step sent. Returns (code,
    words) as the order holds them now."""
    now = time.time() if now is None else float(now)
    if not _shaped(row):
        return _refuse(store, row, now, "R7")
    if now - row["made_at"] > MAX_AGE:
        return _refuse(store, row, now, "R6")
    if row["made_at"] - now > MAX_AGE:
        return _refuse(store, row, now, "R7")
    char = store.character(row["char_id"])
    account = store.account_by_id(char["account_id"]) if char is not None else None
    if account is None or account["login"] != row["login"] or account["banned"]:
        return _refuse(store, row, now, "R7")
    member = store.clan_member(char["id"])
    if member is None:
        return _refuse(store, row, now, "R1", char=char["name"])
    ours = int(member["clan_id"])
    if ours != row["clan_id"]:
        return _refuse(store, row, now, "R4", other=_other_name(store, row["other"]))
    if not int(member["perm"]) & clans.R_DIPLOMACY:
        return _refuse(store, row, now, "R1", char=char["name"])
    other = clan_diplomacy.other_clan(clans_, row["other"], ours)
    if other is None:
        return _refuse(store, row, now, "R2", other=_other_name(store, row["other"]))
    other_id = int(other["id"])
    old, new = row["stat_from"], row["stat_from"] + row["dir"]
    if not clan_diplomacy.WAR <= new <= clan_diplomacy.PEACE:
        return _refuse(store, row, now, "R3", other=other["name"],
                       stance=clan_diplomacy.STANCE_WORDS[old])
    if store.clan_relation(ours, other_id) != old:
        return _refuse(store, row, now, "R4", other=other["name"])
    price = clans.STANCE_UP if row["dir"] > 0 else clans.STANCE_DOWN
    words = TEXTS["OK"].format(clan=member["clan_name"], other=other["name"],
                               stance=clan_diplomacy.STANCE_WORDS[new], price=afro(price))
    balance = store.clan_stance_step(ours, other_id, old, new, price, char["id"],
                                     need=clans.R_DIPLOMACY, when=now,
                                     order=(row["id"], words))
    if balance is None:
        # Nothing was written, the order included. As in the game, short
        # is the one way here this process leaves open; the rest is another
        # process (tools/admin_account.py) taking a clan or a member away
        # in between -- or the order answered already, which _refuse then
        # leaves as it is.
        have = store.clan_treasury(ours)
        if store.clan(other_id) is None:
            return _refuse(store, row, now, "R2", other=other["name"])
        if have is not None and have < price:
            return _refuse(store, row, now, "R5", clan=member["clan_name"], price=afro(price))
        return _refuse(store, row, now, "R4", other=other["name"])
    log.info("  ..    site order %d: %s (%s) sets %r toward %r: %s -> %s, %d afro"
             " (treasury %d)", row["id"], char["name"], row["login"], member["clan_name"],
             other["name"], old, new, price, balance)
    clan_diplomacy.announce(clans_, ours, member["clan_name"], other_id, other["name"], new)
    # The price came out of the treasury: an open money page follows it.
    clan_treasury.tell_balance(clans_, ours, balance)
    return "OK", words


def _refuse(store, row, now, code, **names):
    """A refusal: the row's done_at, code and words, nothing else. An order
    answered already (a stop after its commit, a row read twice) keeps its
    answer, and that is what is returned."""
    words = TEXTS[code].format(**names)
    order_id = _field(row, "id")
    if not clans._is_int(order_id):
        log.warning("  !!    site order without a number refused %s: %r", code, dict(row))
        return code, words
    if store.site_done(order_id, code, words, when=now):
        log.info("  ..    site order %d (%r, char %r): %s %s", order_id, _field(row, "login"),
                 _field(row, "char_id"), code, words)
        return code, words
    held = store.site_order(order_id) or {}
    log.info("  ..    site order %d was answered already (%s); %s not written",
             order_id, held.get("code"), code)
    return held.get("code"), held.get("result")


def drain(store, clans_, now=None):
    """One pass over the waiting orders, oldest first, BATCH at most (the
    admin loop calls it every second). An order that raises is logged and
    left as the failure left it: waiting when it raised before the commit,
    to run again or go stale; done when after. Never raises. Returns
    [(id, code)] of the orders it answered."""
    out = []
    try:
        rows = store.site_pending(BATCH)
    except Exception:                                    # noqa: BLE001
        log.exception("site orders")
        return out
    for row in rows:
        try:
            code, _words = apply(store, clans_, row, now)
        except Exception:                                # noqa: BLE001
            log.exception("site order %s failed", _field(row, "id"))
            continue
        out.append((_field(row, "id"), code))
    return out
