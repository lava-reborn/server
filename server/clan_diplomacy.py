"""Diplomacy between clans: war, neutrality, peace (apply actions 5, 6, 7).

The client's side is the standings page of the clan window (ClanInterface.
as, frame 7: «Клан / Наше отношение к ним / Их отношение к нам») and the two
notices SceneShifter pops for every member (:682-693). Its three commands:

    apply;number=<clan>;action=5;   «Улучшить»: our stance one step up
    apply;number=<clan>;action=6;   «Ухудшить»: one step down
    apply;number=<clan>;action=7;   «Спросить»: their stance toward us

A stance is -1 war, 0 neutrality, 1 peace (clan_relations.stat, the wire's
stats), and one-sided, as the wiki «Дипломатия» has it: each clan sets its
own toward each other clan, and what one sets changes nothing of what the
other has set. A step costs the treasury (clans.STANCE_UP, 1 000 afro, and
STANCE_DOWN, 100 -- the prices gg_info;det=6 shows beside the buttons),
a sink booked in the clan's journal as 'diplomacy' with the other clan for
ref; no purse is touched. War is colours and notices and nothing else (the
owner's decision 7): no PvP, loot or capture reads a stance.

What a change sends, and why in that order:

  * The actor's cmdAck 0 FIRST, then his res=8. The 0 is what his page
    words («Вы улучшили / ухудшили отношения с кланом <X>», upStandingAck /
    downStandingAck), and res=8 pops «Ваш клан изменил отношения…» for every
    member (SceneShifter.weChangeStanding) -- but only one alert window can
    be open (SceneShifter.openNewWindow hands back nothing for a second), so
    whichever comes first is the one he reads. His own words win.
  * gg_list;res=8;data=|X|;names=|@X@|;stats=|s|; to every member of our
    clan online, not only the holders of 0x2 who ask for the standings: the
    colours of names are drawn from them (decision 6, as the core's login
    push). gg_list;res=9;data=|us|;names=|@us@|;stats=|s|; to every member
    of X online: «Клан <us> изменил отношения к вашему клану на …», and
    their «Их отношение к нам» column. Before each, the client must hold
    the clan named in its standings (I2, Clans.ensure_known), or the full
    res=0 goes first: for a clan it does not hold, ClanInspector.
    createNewClanStanding stores its arguments in the wrong fields, and
    the notice would read «<undefined>» and a later click act on a stance
    taken for a clan id.
  * Then the colours. CharInfo.checkColor paints another player's name
    from OUR stance toward his clan (standingArray[..].stat: war red, peace
    and our own clan green, the rest yellow), but it never listens to the
    standings changing (CharInfo.as:97-103): a name already on the screen
    keeps its colour until some clan event makes every CharInfo look again.
    A fellow about another player is such an event (OTHER_CLAN_MEMBER_
    ARRIVED), so each member of our clan online is re-sent the tag of every
    member of X he has on his screen -- after his res=8, which is what the
    look will read. X's side needs none: their colours of us come from
    THEIR stance, which did not move. The global map's names under Ctrl
    (DisplayMapObject.showInfo) are coloured from the standings each time
    they are shown, and the minimap's red is a PvP attacker's
    (Location.setEnemy), not a stance's: res=8 is all those need.
  * Last, the treasury's new balance, gg_list;res=3, to our members online
    who hold 0x400 (clan_treasury.tell_balance, as every writer of the
    treasury does): a money page open on one of their screens shows what
    the step left, and anywhere else the frame has no listener and is
    dropped.

Refusals, each with the code the page has words for, or none:

  * no 0x2000 (R_DIPLOMACY) -- or no clan at all, a page left open after a
    kick: gg_code;res=20; then 20 (Ack.rights);
  * number missing, not a whole number, our own clan, or a clan that is no
    more: 12, «Объект не найден» -- what was clicked has gone. The page
    never sends such a number from a list the server built (I2 above), so
    this is a stale page or a hand-made frame;
  * a step past war or peace: 20, silent (the page greys the button out at
    the ends, ClanInterface.selectStanding, so only a stale page gets here);
  * the treasury short: 21, «Не хватает денег на клановом счете».

The page's own listeners leak on a refusal (it removes only the one that
fired, and the one-per-(event, handler) rule of LEventDispatcher keeps the
rest): after a refused «Ухудшить», the next accepted «Улучшить» can pop
«Вы ухудшили…». The original's client did the same; nothing the server
sends can take a listener off.
"""
import logging

import clan_treasury
import clans
from protocol import RawList

log = logging.getLogger("lava")

# The stances as clan_relations.stat and the wire's stats carry them.
WAR, NEUTRAL, PEACE = -1, 0, 1
STANCE_WORDS = {WAR: "война", NEUTRAL: "нейтралитет", PEACE: "мир"}
UP, DOWN, ASK = 5, 6, 7


def apply(clans_, sess, ack, member, number, action):
    """apply action 5, 6 or 7 (Clans._apply): member is the asker's
    membership (accounts.Store.clan_member) or None, number the frame's
    number unread. ack is owed exactly once."""
    if action == ASK:
        ask(clans_, sess, ack, member, number)
    elif action in (UP, DOWN):
        step(clans_, sess, ack, member, number, +1 if action == UP else -1)
    else:
        ack(clans.NOT_ALLOWED)


def step(clans_, sess, ack, member, number, delta):
    """One step of our stance toward clan `number`, up (+1) or down (-1),
    paid out of the treasury; see the module's note for what goes out."""
    store = clans_.store
    if member is None or not member["perm"] & clans.R_DIPLOMACY:
        ack.rights("менять отношения с другими кланами вам нельзя")
        return
    ours = int(member["clan_id"])
    other = other_clan(clans_, number, ours)
    if other is None:
        ack(clans.GONE)
        return
    other_id = int(other["id"])
    old = store.clan_relation(ours, other_id)
    new = old + delta
    if not WAR <= new <= PEACE:
        ack.refuse("отношение к клану %s уже %s" % (other["name"], STANCE_WORDS.get(old, old)))
        return
    price = clans.STANCE_UP if delta > 0 else clans.STANCE_DOWN
    balance = store.clan_stance_step(ours, other_id, old, new, price, sess.char_id,
                                     need=clans.R_DIPLOMACY)
    if balance is None:
        # Nothing was written. Short is the one way here the game itself
        # leaves open -- it runs one command at a time, and everything else
        # the write named was read a moment ago; the rest is another
        # process (tools/admin_account.py) taking a clan away in between.
        have = store.clan_treasury(ours)
        if have is not None and have < price and store.clan(other_id) is not None:
            ack(clans.NO_MONEY)
        else:
            ack(clans.GONE)
        return
    ack(clans.OK)
    log.info("  ..    %s sets %r toward %r: %s -> %s, %d afro (treasury %d)", sess.nick,
             member["clan_name"], other["name"], old, new, price, balance)
    announce(clans_, ours, member["clan_name"], other_id, other["name"], new, first=sess)
    # The price came out of the treasury: an open money page follows it.
    clan_treasury.tell_balance(clans_, ours, balance)


def announce(clans_, ours, our_name, other_id, other_name, stat, first=None):
    """A stance of ours toward other_id is now stat: res=8 to our members
    online (first, the actor, before the rest), each followed by the fresh
    tags of other_id's members on his screen; res=9 to other_id's members
    online. Each res after the I2 check."""
    targets = {int(c) for c, _p in clans_.store.clan_member_perms(other_id)}
    tag = {"clan_id": int(other_id), "clan_name": other_name}
    ours_online = [s for s, _p in clans_.online_members(ours)]
    if first in ours_online:
        ours_online.remove(first)
        ours_online.insert(0, first)
    for sess in ours_online:
        clans_.ensure_known(sess, other_id)
        sess.send("gg_list", res=8, data=[int(other_id)],
                  names=RawList([clans.list_safe(other_name)]), stats=[int(stat)])
        for subject in clans_.visible_to(sess):
            if int(subject.char_id) in targets:
                clans_.send_tag(sess, subject, tag)
    for sess, _p in clans_.online_members(other_id):
        clans_.ensure_known(sess, ours)
        sess.send("gg_list", res=9, data=[int(ours)],
                  names=RawList([clans.list_safe(our_name)]), stats=[int(stat)])


def ask(clans_, sess, ack, member, number):
    """apply;number=<clan>;action=7;: gg_list;res=5;data=|X|;stats=|their
    stance toward us|; then cmdAck 0. The client writes it into the row it
    holds for X (ClanInspector.gg_list, res 5), so the standings go first
    when it holds none (I2). A clan that is no more: 12. Free, and open to
    every member: the page enables «Спросить» for any row."""
    if member is None:
        ack(clans.NOT_ALLOWED)
        return
    other = other_clan(clans_, number, member["clan_id"])
    if other is None:
        ack(clans.GONE)
        return
    clans_.ensure_known(sess, other["id"])
    sess.send("gg_list", res=5, data=[int(other["id"])],
              stats=[clans_.store.clan_relation(other["id"], member["clan_id"])])
    ack(clans.OK)


def other_clan(clans_, number, ours):
    """The clan row `number` names, when it is a clan other than ours that
    still exists; else None. Ids live in 1..Store.CLAN_MAX_ID (0 and
    16777215 mean "no clan" on the wire), so anything outside -- a stance
    or a clan id where a clan id should be, a number no column can hold --
    is nobody without asking the database."""
    if not clans._is_int(number) or not 0 < number <= clans_.store.CLAN_MAX_ID \
            or number == int(ours):
        return None
    return clans_.store.clan(number)
