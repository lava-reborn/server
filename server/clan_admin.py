"""The admin's clan tools: admin_actions rows of kind 'clan', carried out by
the game process (server.apply_admin_action hands them here before it asks
for a character -- a clan's action has none). The client has no button for
any of them: disbanding, handing the lead on and renaming were the
original's administration's (the owner's decision 4), and the treasury and
a kick from above are the admin's remedies.

    {"op": "rename",   "clan": C, "name": "<new name>"}
    {"op": "disband",  "clan": C, "payout": P}      P optional: the head
    {"op": "head",     "clan": C, "char": P}
    {"op": "treasury", "clan": C, "afro": <signed afro>}
    {"op": "kick",     "clan": C, "char": P}

C is a clan's id or its name (looked up as its skeleton, clans.name_key),
P a character's id or name. The rows are written by the panel
(bootstrap_http.py, /admin/clan) and by tools/admin_account.py (its clan-*
commands); both only queue, and apply() is the one place the checks live,
so the two cannot disagree -- and the tool, which may not import the game
(names reads the client's files at import), needs none of them.

Why here and not in the database straight from the panel or the tool: a
member who is online has a client that has been told his clan, his rights
and his roster, and a Character whose purse Character.save writes back at
logout. Only the game process can tell the client (the same pushes the
players' own commands send) and pay into that purse. What is not online is
the database's alone, and the game reads the database on every clan
command -- clans.py caches nothing -- so an offline member finds it all as
it now is at his next login. So every op here is safe while the game runs,
and acts the same on a member who plays and on one who does not:

  rename    validated as a founding is (clans.clean_name: 3-40 of the
            alphabet, two letters or digits; unique by skeleton; «Аукцион»
            and «Сервер» taken). Every other clan's members online get their
            standings again (res=0), so the diplomacy list shows the new
            name at once. The clan's own members and whoever sees their tag
            keep the old one until F5: ClanInspector.clanArray holds a
            ClanInfo per reg for the life of the page, and a fellow with a
            known reg never renames it (ClanInspector.fellow).
  disband   Clans.disband: the treasury into the payee's purse -- the head
            by default, or any character named -- through his live
            Character and a purse push when he plays, into his row when he
            does not; 'clan_disband' in money_ledger and 'disband' in
            clan_ledger in one transaction. Every member online is put out
            («Вас исключили из клана») and untagged, invitations into the
            clan are void, every other clan's standings lose it, and the
            name is free again (the id never is).
  head      Clans.set_head: 65535 moves to the member named, the old head
            keeps every right but the head's (0x2F67); both rows to the
            roster holders (act=3) and both their own rights to them
            (fellow id=0).
  treasury  Store.clan_treasury_adjust: a signed change, a debit only while
            the treasury holds it, one 'admin' row in clan_ledger with ref
            the admin_actions row, so the journal says which order made
            it. The new balance goes to the members online who may see it
            (0x400: ClanInterface.refreshMoney shows the balance to nobody
            else), as the gg_list;res=3 their own det=3 would bring
            (clan_treasury.tell_balance, the treasury's one push).
  kick      Clans.remove_member: the pushes of a kick without a kicker --
            act=2 to the roster holders, the member put out and untagged.
            Not the head: hand the lead on first, or disband.

apply(row, clans) -> the line the panel's log and the tool print. It never
raises for a bad order; anything that does is the queue's «ошибка: ...».
"""
import json
import logging

import clan_treasury
import clans as clanlib
import storage

log = logging.getLogger("lava")

OPS = ("rename", "disband", "head", "treasury", "kick")

# clans.afro is an INTEGER, 32 bits in Postgres: a treasury pushed past it
# would fail the UPDATE there and wrap nowhere in SQLite.
AFRO_LIMIT = 2 ** 31 - 1


def _field(row, name, default=None):
    """A column of an admin_actions row: a sqlite3.Row, Postgres's dict, or
    a test's own dict that may leave it out."""
    try:
        return row[name]
    except (KeyError, IndexError):
        return default


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _shown(ref):
    return "«%s»" % ref if isinstance(ref, str) else str(ref)


def find_clan(store, ref):
    """A clan row by id, or by name as its skeleton -- a name first, since
    "123" is a name a clan may have; digits that name no clan are an id."""
    if _is_int(ref):
        return store.clan(ref) if ref > 0 else None
    if isinstance(ref, str) and ref.strip():
        row = store.clan_by_key(clanlib.name_key(ref))
        if row is None and ref.strip().isdigit():
            row = store.clan(int(ref.strip()))
        return row
    return None


def find_char(store, ref):
    """A characters row by id or by name (Store.character_by_name, which
    falls back to the skeleton)."""
    if _is_int(ref):
        return store.character(ref) if ref > 0 else None
    if isinstance(ref, str) and ref.strip():
        row = store.character_by_name(ref.strip())
        if row is None and ref.strip().isdigit():
            row = store.character(int(ref.strip()))
        return row
    return None


def apply(row, clans):
    """Carry out one clan order; returns what happened, in the panel's
    words."""
    try:
        args = json.loads(_field(row, "args_json") or "{}")
    except ValueError:
        return "не разобрать аргументы действия"
    if not isinstance(args, dict):
        return "не разобрать аргументы действия"
    op = args.get("op")
    handler = _HANDLERS.get(op)
    if handler is None:
        return "неизвестная операция с кланом: %s (есть: %s)" % (op, ", ".join(OPS))
    clan = find_clan(clans.store, args.get("clan"))
    if clan is None:
        return "клана %s нет" % _shown(args.get("clan"))
    return handler(clans, clan, args, int(_field(row, "id", 0) or 0))


def _rename(clans, clan, args, _action):
    store = clans.store
    name = clanlib.clean_name(args.get("name"))
    if name is None:
        return ("название не годится: 3–40 символов — буквы, цифры, пробел и"
                " - _ . , ! ? ( ) [ ] # * + : ~, из них хотя бы две буквы или цифры")
    key = clanlib.name_key(name)
    if clanlib.reserved(key):
        return "название «%s» занято: так подписывается сама игра" % name
    other = store.clan_by_key(key)
    if other is not None and int(other["id"]) != int(clan["id"]):
        return "название «%s» уже у клана «%s» (id %d)" % (name, other["name"], other["id"])
    if name == clan["name"]:
        return "у клана «%s» уже это название" % name
    try:
        done = store.clan_rename(clan["id"], name, key)
    except storage.IntegrityError:
        # The look above lost a race: the same skeleton a moment earlier.
        return "название «%s» только что занял другой клан" % name
    if not done:
        return "клана «%s» больше нет" % clan["name"]
    clans.refresh_standings(skip_clan=int(clan["id"]))
    return ("«%s» → «%s»; списки отношений других кланов обновлены сразу, а члены"
            " клана и те, кто видит их метку, увидят новое название после"
            " обновления страницы (F5): клиент помнит название по id клана"
            % (clan["name"], name))


def _disband(clans, clan, args, _action):
    store = clans.store
    ref = args.get("payout")
    if ref in (None, "", 0):
        payee = store.character(clan["head"])
    else:
        payee = find_char(store, ref)
        if payee is None:
            return "персонажа %s нет: клан не распущен" % _shown(ref)
    payee_id = int(payee["id"]) if payee is not None else int(clan["head"])
    members = len(store.clan_member_perms(clan["id"]))
    paid = clans.disband(clan["id"], payee_id)
    if paid is None:
        return "клана «%s» уже нет" % clan["name"]
    playing = clans.session_of(payee_id) is not None
    where = (" — %s, %s" % (payee["name"] if payee is not None else payee_id,
                            "в игре: в кошелёк сразу" if playing else "не в игре: в его строку")
             if paid else "")
    return ("клан «%s» распущен (членов: %d), название свободно; казна %d афро%s"
            % (clan["name"], members, paid, where))


def _head(clans, clan, args, _action):
    store = clans.store
    who = find_char(store, args.get("char"))
    if who is None:
        return "персонажа %s нет" % _shown(args.get("char"))
    m = store.clan_member(who["id"])
    if m is None or int(m["clan_id"]) != int(clan["id"]):
        return "%s не состоит в клане «%s»" % (who["name"], clan["name"])
    if int(who["id"]) == int(clan["head"]):
        return "%s и так глава «%s»" % (who["name"], clan["name"])
    old = store.character(clan["head"])
    if not clans.set_head(clan["id"], who["id"]):
        return "%s уже не в клане «%s»" % (who["name"], clan["name"])
    return ("глава «%s» теперь %s; %s остаётся в клане со всеми правами, кроме главы"
            % (clan["name"], who["name"], old["name"] if old is not None else clan["head"]))


def _treasury(clans, clan, args, action):
    store = clans.store
    delta = args.get("afro")
    if not _is_int(delta) or delta == 0:
        return "сумма — целое число афро, не ноль (минус — снять)"
    if int(clan["afro"]) + delta > AFRO_LIMIT:
        return "столько в казну не поместится: не больше %d афро" % AFRO_LIMIT
    new = store.clan_treasury_adjust(clan["id"], delta, "admin", ref=action)
    if new is None:
        have = store.clan_treasury(clan["id"])
        if have is None:
            return "клана «%s» больше нет" % clan["name"]
        return "в казне «%s» %d афро: снять %d нельзя" % (clan["name"], have, -delta)
    # The same push as every other writer of the treasury (the package that
    # built it asked for this one path): res=3 to the 0x400 holders online.
    clan_treasury.tell_balance(clans, clan["id"], new)
    return "казна «%s»: %+d афро, теперь %d" % (clan["name"], delta, new)


def _kick(clans, clan, args, _action):
    store = clans.store
    who = find_char(store, args.get("char"))
    if who is None:
        return "персонажа %s нет" % _shown(args.get("char"))
    m = store.clan_member(who["id"])
    if m is None or int(m["clan_id"]) != int(clan["id"]):
        return "%s не состоит в клане «%s»" % (who["name"], clan["name"])
    if int(who["id"]) == int(clan["head"]):
        return ("главу не исключить: сначала передайте главенство (head) или"
                " распустите клан (disband)")
    playing = clans.session_of(who["id"]) is not None
    if not clans.remove_member(clan["id"], who["id"]):
        return "%s уже не в клане «%s»" % (who["name"], clan["name"])
    return "%s исключён из «%s» (%s)" % (
        who["name"], clan["name"],
        "в игре: ему пришло «Вас исключили из клана»" if playing
        else "не в игре: увидит при входе")


_HANDLERS = {"rename": _rename, "disband": _disband, "head": _head,
             "treasury": _treasury, "kick": _kick}
