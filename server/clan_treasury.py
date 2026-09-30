"""The clan's treasury: afro in and out (apply action 3), its balance
(gg_info det=3), and the gold treasury the original never switched on
(action 4, det=4).

The client side is the money page of the clan window (ClanInterface.
initMoneyPage and the functions after it, frame 5) and four calls of
ClanInspector: addMoneyToClanAccount / withdrawMoneyFromClanAccount send
apply;number=<n>;action=3; (4 for gold), a withdrawal being the same frame
with the number negated; getClanAccauntAfroAmmount / ...GoldAmmount send
gg_info;det=3; (4). The page asks for the balance only with the right to
take it out (refreshMoney: 0x400 for afro, 0x800 for gold) and shows
«у вас недостаточно прав для просмотра счета» otherwise, so the balance is
for those holders only; putting money in is anybody's (the wiki «Клан»:
«Класть деньги может любой»).

What the handlers here keep to, besides the core's rules (clans.py):

  * The SIGN decides, never the button. putAfro and takeAfro do not check
    that the number is positive before they negate it (and putGold does not
    check at all), so a "deposit" of -500 is a withdrawal and is authorised
    as one: 0x400, or gg_code;res=20 and 20.
  * A whole number of afro, 1..999 999 either way (the page's fields take
    six digits, «0-9» only), or 21. What comes in may be anything a
    modified client can write: a fraction, a float the size of the sky,
    1e999 (infinite), a string, a list, the key twice. A float that IS a
    whole number is taken for it, and one within a millionth of a whole
    number too -- that is how Number(text) * 100 writes some sums in AVM1
    (28.999999999999996), which is how the page sends gold. A real fraction
    is refused rather than rounded: rounding it would move a part of an afro
    nobody typed, and the purse and the treasury would have to agree on
    which way it went. The one number decided here (amount) is the one both
    sides move by.
  * One transaction for the three writes of a move: the treasury (by an
    UPDATE that names the member still in that clan and, for a withdrawal,
    the treasury still holding enough -- two withdrawals racing, from two
    officers or from the admin's tools in another process, cannot both
    have it), the purse with its money_ledger row (source 'clan', ref the
    clan: a transfer, not new money -- tools/money_report.py nets it out),
    and the clan_ledger row (deposit / withdraw). accounts.Store.
    clan_treasury_move does all three or nothing.
  * The purse is the live Character's (Character.save writes it back at
    logout), changed only after the database took it, and pushed --
    userInfo_Player -- BEFORE cmdAck 0: on the 0 the page runs refreshMoney,
    which reads the purse off the gamer that very moment.
  * After a move, every OTHER member online who may see the balance (0x400)
    is sent it (gg_list;res=3, tell_balance): a page open on their screen
    shows it at once, a closed one has no listener and drops it. The mover
    asks for it himself after his 0, when he holds the right. DESIGNED: the
    original's behaviour here is not known.

The gold treasury is off (the owner's decision 8): the page has no gold
widgets at all (goldOperation_bool is false, so moneyPan_mc shows its
frame without them), the wiki says «Функция не активна», and it would be a
channel of gold between characters, which only the auction may be. det=4
is refused with a silent 20, action 4 with 21, whatever the number.
"""
import logging
import math

import clans

log = logging.getLogger("lava")

# gg_list res of the afro balance (ClanInspector.gg_list: 3 afro, 4 gold --
# the gold one is never sent).
RES_AFRO = 3
# How far a float may lie from a whole number and still be taken for it:
# the error of AVM1's Number arithmetic on a six-digit sum is some 1e-9, a
# typed fraction at least 1e-2 (the gold field keeps two decimals).
WHOLE_EPS = 1e-6


def whole(number):
    """The whole number a frame's value stands for, or None: an int as it
    is, a finite float within WHOLE_EPS of a whole number as that number,
    anything else -- a fraction, inf, a string, a list, a bool -- None."""
    if isinstance(number, bool):
        return None
    if isinstance(number, int):
        return number
    if isinstance(number, float) and math.isfinite(number):
        near = round(number)
        if abs(number - near) <= WHOLE_EPS:
            return int(near)
    return None


def amount(number):
    """The signed afro a move asks for: whole, and 1..MAX_MOVE either way;
    None otherwise (the answer is then 21)."""
    n = whole(number)
    if n is None or not 1 <= abs(n) <= clans.MAX_MOVE:
        return None
    return n


def tell_balance(clans_, clan_id, balance=None, exclude=None):
    """gg_list;res=3 with the treasury to every member online holding 0x400,
    but `exclude` (the mover, whose page asks for it itself): the money page
    open on a screen shows it (ClanInterface.refreshAfroAck), anywhere else
    it has no listener and is dropped. For the treasury's other writers too
    -- a stance paid for (clan_diplomacy.py), the admin's adjustment
    (clan_admin.py) -- after the write; balance None reads it."""
    if balance is None:
        balance = clans_.store.clan_treasury(clan_id)
        if balance is None:
            return
    for sess, _perm in clans_.online_members(clan_id, need=clans.R_AFRO):
        if sess is not exclude:
            sess.send("gg_list", res=RES_AFRO, data=[int(balance)])


def gg_info(clans_, sess, ack, member, det):
    """det=3: gg_list;res=3;data=|<afro>|; then 0, to a member holding 0x400;
    the page never asks without it, so anything else is a stale or modified
    client and gets a silent 20 (no gg_code: «Вам нельзя этого делать» would
    pop up on a page that merely opened). det=4: the gold treasury is off --
    20, and nothing said, not even to the log: the page asks for it every
    time it opens for a holder of 0x800 (the head's 65535 has it). Its
    handler (getClanAccountGoldAmmountCmdAck) acts on 0 and 2 only, and
    ErrorReport has no alert for 20, so nothing shows; a gg_list;res=4
    would have nowhere to show either, the page having no gold widgets."""
    if det == 4:
        ack(clans.NOT_ALLOWED)
        return
    if member is None:
        ack.refuse("вы не в клане")
        return
    if not member["perm"] & clans.R_AFRO:
        ack.refuse("смотреть клановый счёт вам нельзя")
        return
    balance = clans_.store.clan_treasury(member["clan_id"])
    if balance is None:
        ack.refuse("клана больше нет")
        return
    sess.send("gg_list", res=RES_AFRO, data=[int(balance)])
    ack(clans.OK)


def apply(clans_, sess, ack, member, number, action):
    """apply;number=<±afro>;action=3; -- in, or out when negative -- and
    action 4, the gold, refused. The answers the page's handlers read
    (addMoneyToClanAccountCmdAck, withdraw...CmdAck): 0 runs refreshMoney,
    21 is «can't afford», which nothing listens to, so it shows nothing; 2
    would be a ban, and is never sent (ErrorReport pops «Аккаунт забанен»
    on it). Refusals, in the order they are decided:

      action 4 -> 21;  not a member -> 20;  not a whole 1..999999 -> 21;
      a withdrawal without 0x400 -> gg_code 20, then 20;
      a deposit past the purse -> 21;
      the write touching nothing -> 20 when he is no longer in that clan
      (kicked, the clan disbanded in between), else 21 (the treasury was
      short: two withdrawals raced, or the page showed an old balance --
      said to him then, as the page says nothing).

    Success: the purse (userInfo_Player), cmdAck 0, then the balance to the
    other 0x400 holders online (tell_balance)."""
    if action == 4:
        ack.refuse("золотого счёта у клана нет", clans.NO_MONEY)
        return
    if member is None:
        ack.refuse("вы не в клане")
        return
    n = amount(number)
    if n is None:
        ack.refuse("клановый счёт: сумма — целое число афро от 1 до %d" % clans.MAX_MOVE,
                   clans.NO_MONEY)
        return
    clan_id = int(member["clan_id"])
    if n < 0 and not member["perm"] & clans.R_AFRO:
        ack.rights("снимать афро с кланового счёта вам нельзя")
        return
    ch = sess.character()
    if n > 0 and ch.afro < n:
        ack.refuse("у вас нет %d афро" % n, clans.NO_MONEY)
        return
    # The purse as it will be: n comes out of it (a deposit) or -n goes in.
    balance = clans_.store.clan_treasury_move(clan_id, sess.char_id, n,
                                              (sess.char_id, ch.afro - n, ch.gold))
    if balance is None:
        now = clans_.member(sess.char_id)
        if now is None or int(now["clan_id"]) != clan_id:
            ack.refuse("вы уже не в этом клане")
            return
        ack.refuse("", clans.NO_MONEY)
        have = clans_.store.clan_treasury(clan_id)
        if n < 0 and have is not None:
            # The one refusal a real page runs into (its own check reads the
            # balance it was last shown), and it has no words for it: the
            # input just empties. Said, as the answer to what he did.
            sess.answer("На клановом счёте %d афро — снять %d нельзя" % (have, -n))
        return
    # The copy in memory follows once the database has it: it is what
    # Character.save writes back at logout.
    ch.afro -= n
    log.info("  ..    %s %s %d afro %s the treasury of %r: %d there now", sess.nick,
             "puts" if n > 0 else "takes", abs(n), "into" if n > 0 else "out of",
             member["clan_name"], balance)
    sess.push_money()
    ack(clans.OK)
    tell_balance(clans_, clan_id, balance, exclude=sess)
