"""Clans: founding, membership, rights, the clan's chat and its tag over a
player's head -- the core that the treasury (clan_treasury.py), diplomacy
(clan_diplomacy.py) and the admin's tools (clan_admin.py) are built on.

The client side is lol/core/clans/ClanInspector.as, with the window in
lol/gpui/ClanInterface.as; PROTOCOL.md «Кланы» has the frames. Four commands
come in -- head (found a clan), admit (invite by nick, or change a member's
rights by his id), apply (answer an invitation, leave, kick, the invitation
ban, the treasury, diplomacy) and gg_info (the questions) -- and five frames
go out: fellow (who is in which clan: oneself as id 0, somebody else by his
entity id), invite, gg_list (the roster, the standings, the prices),
gg_struct (one row of the roster changed) and gg_code (the rights refusal).

What every handler here keeps to:

  * Exactly one cmdAck per command, to the session that sent it, in order.
    Clans.command wraps each: a handler that returns or raises without an
    answer is answered NOT_ALLOWED, and a second answer is never sent --
    it is logged and counted (Clans.double_acks) instead, a bug for the
    tests to catch. The four commands are always answered by this module,
    even from a body the dead filter holds (combat.DEAD_PASSES,
    DEAD_REFUSAL) and even from a frame that could not be read
    (server.bad_frame_res).
  * Only codes that the clan's handlers word, or that nothing words.
    ErrorReport pops an alert for 1-8, 11-19, 27, 44, 45 and 1001-1003
    whatever the command: 3 reads «Сервер не отвечает», 2 «Аккаунт
    забанен», and 9 makes the roster and standings questions ask again
    every five seconds for good. Three of them are used on purpose: 5 and
    6 for the name at founding (their global texts are the right ones), and
    12, «Объект не найден», for a thing clicked that no longer exists -- an
    invitation run out, a member gone, a clan disbanded. NEVER lists the
    rest.
  * The database is the only authority (accounts.Store, the clan section).
    Nothing about a clan is cached here, because tools/admin_account.py
    changes clans from another process while the game runs, and a cached
    head or member list would then decide in the game's name; the reads
    are a primary key or an index each. What is kept in memory is what
    each CLIENT has been told (View), which is that connection's own
    business, and the open invitations, which live exactly as long as the
    sessions they are for.
  * "char" on the clan wire is characters.id everywhere -- gg_list data,
    fellow char, gg_struct id, the number of a kick, admit's char, userMsg
    player -- and the entity id (rooms.player_id) appears only as fellow id
    about somebody else. "reg" is the clan's id.
  * String lists go raw (protocol.RawList): the client never unescapes
    them. Clan names and posts are kept free of anything that would need
    escaping at all; a character's name, which nothing restricts, has the
    four characters that would break the list swapped for lookalikes in
    lists only (list_safe).

Invariants the pushes keep (the spec's I1-I4):

  I1  gg_struct goes only to a client holding this clan's roster (View.
      roster), and every change of the roster goes to all of them in order.
      Its list then always equals ours, and act=2 always finds the row --
      for an id it does not have, the client's splice(null, 1) would take
      out the FIRST row.
  I2  Before a gg_list res=8/9 about clan X reaches a client, X is in the
      standings it holds (View.known), or the full res=0 goes first:
      ClanInspector.createNewClanStanding mixes its arguments up for a clan
      it does not know yet (ensure_known).
  I3  An open invitation means no clan: invitations go to free characters
      only, and founding a clan over one is refused while it may still be
      on its way to the screen (INVITE_RACE). The invitation popup is modal,
      so apply(0, 1) is "no thanks" from a free character and "I leave"
      from a member, without doubt.
  I4  Exactly one member holds 0x8000, clans.head, with 65535: rights are
      never granted with it (GRANT has no such bit), and only succession
      and the admin's clan_set_head move it.
"""
import asyncio
import collections
import logging
import os
import re
import time
import unicodedata

import accounts
import clan_diplomacy
import clan_treasury
import mail
import storage
from protocol import RawList, Str

log = logging.getLogger("lava")

# --- cmdAck codes, as the clan's handlers read them -------------------------
OK = 0
BAD_NAME = 5         # head: ErrorReport «Имя содержит некорректные символы»
NAME_TAKEN = 6       # head: ErrorReport «Имя уже используется другим аккаунтом»
GONE = 12            # ErrorReport «Объект не найден»: what was clicked is no more
NOT_ALLOWED = 20     # silent; with gg_code;res=20 first when it is about rights
NO_MONEY = 21        # head «Недостаточно средств»; apply 5/6 «Не хватает денег
                     # на клановом счете»; apply 3/4 silent
OFFLINE = 22         # admit: shown as «Персонаж находится в офлайне» (22 and
                     # 30 have their texts swapped in ClanInterface.as:653-662,
                     # so the code is picked by the text wanted)
NICK_TOO_LONG = 23   # admit: «Слишком длинное имя персонажа» (no nick limit yet)
IN_CLAN = 28         # admit: «Персонаж уже состоит в другом клане»
REFUSED = 29         # admit: silent -- the invitation ban, or one already open
NO_SUCH_NICK = 30    # admit: shown as «Персонажа с таким именем не существует»

# Codes no clan command may be answered with (ErrorReport.as:55-78, and 9's
# five-second retry of det=1/5, ClanInspector.as:765-773, 794-803).
NEVER = frozenset([1, 2, 3, 4, 7, 8, 9, 11] + list(range(13, 20))
                  + [27, 44, 45, 1001, 1002, 1003])

# The four commands, all of them in server.EXPECTS_ACK.
COMMANDS = ("head", "admit", "apply", "gg_info")

# --- prices and limits -------------------------------------------------------
CREATE_GOLD = 1000       # 10 G in hundredths, the wiki's «10 унций золота»; the
                         # window shows data[0] / 100 by the gold icon
STANCE_UP = 1000         # afro from the treasury (clan_diplomacy.py): the wiki
STANCE_DOWN = 100
INVITE_TTL = 300         # seconds an invitation waits (the owner's decision 11)
INVITE_RACE = 5          # an invitation this young may still be on its way
MAX_MOVE = 999999        # afro per treasury operation: the field's 6 digits
FORBID_REG = 16777215    # fellow reg of a free character who forbids invitations

# How long a member's client has, after the location opens, to ask for the
# roster before it is taken for one that has stopped listening (View.asked).
# What it is then told is a line the server says by itself (Session.say), so
# it stays out of the chat while the owner keeps the server's own lines off
# (2026-09-29: he saw it twice in a minute and asked for no such lines); the
# log keeps it either way. A player runs the launcher, where there is no page
# to refresh: the remedy is to start the game again.
DEAF_CHECK = float(os.environ.get("LAVA_CLAN_DEAF_CHECK", "8"))
DEAF_LINE = ("Клан: окно клана не получает данных после смены персонажа или обрыва"
             " связи — перезапустите игру")

# --- rights (Rights.as:19-64) --------------------------------------------------
R_BASE = 0x1          # no meaning of its own (Rights.parse always sets it)
R_CHAT = 0x2          # clan chat and the standings
R_STORE_PUT = 0x4     # the clan's storage: no window for it in the client
R_STORE_TAKE = 0x20
R_ACCEPT = 0x40       # invite
R_KICK = 0x100        # put lower ranks out
R_RIGHTS = 0x200      # set lower ranks' rights
R_AFRO = 0x400        # take afro out of the treasury (clan_treasury.py)
R_GOLD = 0x800        # the gold treasury: off
R_DIPLOMACY = 0x2000  # change the stances (clan_diplomacy.py)
R_HEAD = accounts.CLAN_HEAD
VALID = accounts.CLAN_VALID
HEAD_PERM = accounts.CLAN_HEAD_PERM
rank = accounts.clan_rank
# What each rank may grant (ClanInterface.enabledCheckBox and
# unselectionOutRightsCheckBox, :1431-1506): the head everything but the
# head's bit, an officer chat, storage and inviting, the rest nothing.
GRANT = {4: VALID & ~R_HEAD, 2: R_CHAT | R_STORE_PUT | R_STORE_TAKE | R_ACCEPT, 1: 0, 0: 0}

# --- names, posts, lists ---------------------------------------------------------
NAME_MIN, NAME_MAX = 3, 40
DESCR_MAX = 127
POST_MAX = 20
# DESIGNED (the owner's decision 12): letters of the two alphabets, digits,
# the space and a few signs -- none that the wire escapes (% < > ' " & @)
# or that a list or the frame parser would trip on (; = |), so a clan name
# travels the same as a scalar and as a list item.
_NAME_OK = re.compile(r"^[0-9A-Za-zЀ-џ \-_.,!?()\[\]#*+:~]+$")
# Names nobody may take: the house's own signatures (mail.SYSTEM_NAME, and
# the server's lines of chat), compared as skeletons.
RESERVED = ("Аукцион", "Сервер")
# A post keeps none of these: the wire's escapables, what breaks a list.
_POST_DROP = set("@|;=%<>&'\"\\")
# A character's name in a list: what would end or split it, or derail the
# frame parser, swapped for a lookalike from Latin-1 and WGL4, which every
# font of the client's window has (Tahoma, Microsoft Sans Serif).
_LIST_LOOKALIKE = str.maketrans({"@": "©", "|": "¦", ";": ",", "=": "═"})


def _collapse(s):
    return " ".join(str(s or "").split())


def clean_name(raw):
    """A clan name as it will be stored and shown, or None when it breaks
    the rules: trimmed and its spaces collapsed; 3-40 characters of the
    alphabet above; at least two letters or digits."""
    if not isinstance(raw, str):
        return None
    name = _collapse(unicodedata.normalize("NFC", raw))
    if not NAME_MIN <= len(name) <= NAME_MAX or not _NAME_OK.match(name):
        return None
    if sum(1 for c in name if c.isalnum()) < 2:
        return None
    return name


def name_key(name):
    """What must be unique: the name as it looks (mail._skeleton)."""
    return mail._skeleton(name)


def reserved(key):
    return key in {mail._skeleton(n) for n in RESERVED}


def clean_post(raw):
    """A post: none of _POST_DROP, no control characters, at most 20 (the
    window's own limit, ClanInterface.as:569, 695, 764) -- longer is cut."""
    s = "".join(c for c in str(raw if raw is not None else "")
                if c not in _POST_DROP and unicodedata.category(c)[0] != "C")
    return _collapse(s)[:POST_MAX]


def clean_descr(raw):
    s = "".join(c for c in str(raw if raw is not None else "")
                if unicodedata.category(c)[0] != "C")
    return s.strip()[:DESCR_MAX]


def list_safe(s):
    """A string fit to be an item of a raw list (protocol.RawList)."""
    return str(s or "").translate(_LIST_LOOKALIKE)


def stamp(when):
    """A roster date: UTC, as the client shifts only hours and minutes
    itself (ClanMemberInfo.as:73-98); "" for never, which the client shows
    as nothing where 0 would read 01.01.1970."""
    return mail.stamp(int(when)) if when else ""


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


class View:
    """What one connection's client has been told, which is what decides
    whether a push would land right (I1, I2). Per connection, because the
    client's own state is: a new socket is a new page's ClanInspector -- or
    a dead one's (the deaf client, DEAF_LINE)."""

    def __init__(self):
        self.told = False     # the login's own fellow went out (Clans.online)
        self.roster = None    # the clan whose roster (res=1) this client holds
        self.known = set()    # the clans in its standings (the last res=0) ...
        self.known_for = None  # ... sent for this clan of its own
        self.tagged = {}      # entity id -> clan told in a fellow about him
        self.asked = False    # a det=1 came on this connection
        self.timer = None     # the deaf check waiting
        self.warned = False   # DEAF_LINE said once

    def forget_clan(self):
        self.roster = None
        self.known = set()
        self.known_for = None
        self.asked = False


def view(sess):
    """The session's View, made on first use (server.Session makes one)."""
    v = getattr(sess, "clan_view", None)
    if v is None:
        v = sess.clan_view = View()
    return v


# An open invitation: which clan, who sent it (id and nick), the rights and
# post it offers, and when.
Invite = collections.namedtuple("Invite", "clan_id inviter inviter_nick perm post at")


class Ack:
    """The one cmdAck a clan command owes, and the proof it was sent once.
    Handed to every handler here and in the treasury, diplomacy and admin
    modules: call it with the code."""

    def __init__(self, clans, sess, cmd):
        self.clans = clans
        self.sess = sess
        self.cmd = cmd
        self.sent = None

    def __call__(self, res):
        if self.sent is not None:
            # Never on the wire: a second answer would be read by whatever
            # the client asked next. A bug, for the tests to find.
            log.error("  !!    clan %s answered twice (%s, then %s)", self.cmd,
                      self.sent, res)
            self.clans.double_acks.append((self.cmd, self.sent, res))
            return
        self.sent = int(res)
        if self.sent in NEVER:
            log.error("  !!    clan %s answered with %d, which the client pops an"
                      " alert for", self.cmd, self.sent)
        self.sess.send("cmdAck", res=self.sent)

    def rights(self, why):
        """Refused for want of rights: gg_code;res=20 first -- «Вам нельзя
        этого делать», on a client that has opened the rights page once
        (the listener stays, ClanInterface.as:694) -- then the silent 20."""
        self.sess.send("gg_code", res=NOT_ALLOWED)
        self.refuse(why)

    def refuse(self, why, code=NOT_ALLOWED):
        """A refusal the client has no words for: the reason goes to the
        server's own chat, which is off unless SERVER_CHAT (Session.say)."""
        if why:
            self.sess.say(why)
        self(code)


class Clans:
    """Every clan command and push. One for the process (server.CLANS)."""

    def __init__(self, store, directory, gmap=None):
        self.store = store
        self.directory = directory     # rooms.Directory: who is online
        self.gmap = gmap               # rooms.GlobalMapRoom: who sees whom there
        self.invites = {}              # invited character id -> Invite
        self.double_acks = []          # (cmd, first, second): must stay empty

    # --- plumbing ------------------------------------------------------------
    def session_of(self, char_id):
        sess = self.directory.by_char.get(int(char_id)) if char_id else None
        return sess if sess is not None and not sess.closed else None

    def member(self, char_id):
        """The character's membership (accounts.Store.clan_member): char_id,
        clan_id, perm, post, joined_at, invited_by, clan_name, head -- or
        None. Read from the database every time (see the module's note)."""
        return self.store.clan_member(char_id) if char_id else None

    def online_members(self, clan_id, need=0):
        """[(session, perm)] of the clan's members online, those holding
        every bit of `need` only."""
        out = []
        for char_id, perm in self.store.clan_member_perms(clan_id):
            if need and perm & need != need:
                continue
            sess = self.session_of(char_id)
            if sess is not None:
                out.append((sess, perm))
        return out

    def roster_holders(self, clan_id, exclude=None):
        """The clan's members online whose client holds its roster (I1)."""
        return [s for s, _p in self.online_members(clan_id)
                if s is not exclude and view(s).roster == clan_id]

    def push_struct(self, clan_id, act, char_id, exclude=None, **fields):
        """gg_struct about one member to every roster holder (I1)."""
        for sess in self.roster_holders(clan_id, exclude):
            sess.send("gg_struct", id=int(char_id), act=act, **fields)

    # --- what a client is told about itself ------------------------------------
    def fellow_self(self, sess, m=None):
        """fellow id=0: the member's clan, post, id and rights -- the only way
        the client learns its own rights (ClanInspector.fellow, case c), so
        it follows every change of them -- or, free, reg 0 or 16777215."""
        if m is None:
            m = self.member(sess.char_id)
        if m is not None:
            sess.send("fellow", id=0, reg=int(m["clan_id"]), soc=Str(m["clan_name"]),
                      post=Str(m["post"]), char=int(sess.char_id), perm=int(m["perm"]),
                      stand=0)
        else:
            row = self.store.character(sess.char_id)
            sess.send("fellow", id=0,
                      reg=FORBID_REG if row is not None and row["clan_no_invites"] else 0)

    def send_roster(self, sess, m):
        """gg_list with the member list. Any res but 0, 3, 4, 5, 6, 8 and 9 is
        the roster to the client (ClanInspector.gg_list's fall-through);
        1 is what the original sent, so 1 it is."""
        rows = self.store.clan_roster(m["clan_id"])
        online = {r["char_id"] for r in rows if self.session_of(r["char_id"]) is not None}
        sess.send("gg_list", res=1, data=[int(r["char_id"]) for r in rows],
                  names=RawList(list_safe(r["name"]) for r in rows),
                  posts=RawList(list_safe(r["post"]) for r in rows),
                  dates=RawList(stamp(r["seen_at"]) for r in rows),
                  perms=[int(r["perm"]) for r in rows],
                  stats=[1 if r["char_id"] in online else 0 for r in rows])
        v = view(sess)
        v.roster = int(m["clan_id"])
        v.asked = True
        self._cancel_deaf(v)

    def send_standings(self, sess, clan_id):
        """gg_list;res=0: every OTHER clan with our stance toward it. Never
        our own (the window's filter reads a field that does not exist,
        ClanInterface.as:1253), never an id 0 or an empty name (the client
        keys the list by a counter that skips them, ClanInspector.as:
        596-617). Remembered as what this client knows (I2)."""
        rel = self.store.clan_relations_of(clan_id)
        others = [c for c in self.store.clan_all() if int(c["id"]) != int(clan_id)]
        sess.send("gg_list", res=0, data=[int(c["id"]) for c in others],
                  names=RawList(list_safe(c["name"]) for c in others),
                  stats=[rel.get(int(c["id"]), 0) for c in others])
        v = view(sess)
        v.known = {int(c["id"]) for c in others}
        v.known_for = int(clan_id)

    def clear_standings(self, sess):
        """An empty res=0 after leaving: the client keeps the old ClanInfo,
        and with it the old enemies in red, until its standings are
        replaced -- by nothing, here (ClanInspector.as:596-600)."""
        sess.send("gg_list", res=0, data=[], names=RawList(), stats=[])
        v = view(sess)
        v.known = set()
        v.known_for = None

    def ensure_known(self, sess, other_id):
        """I2, for clan_diplomacy.py: the full standings first when this
        client does not know `other_id` yet. Only for a member."""
        m = self.member(sess.char_id)
        if m is None:
            return
        v = view(sess)
        if v.known_for != int(m["clan_id"]) or int(other_id) not in v.known:
            self.send_standings(sess, m["clan_id"])

    def refresh_standings(self, skip_clan=None):
        """A clan came or went: every member online of every other clan gets
        its standings again, so the new one is in them or the old one out."""
        members = self.store.clan_members_all()
        for sess in list(self.directory):
            if sess.closed or not sess.char_id:
                continue
            got = members.get(int(sess.char_id))
            if got is not None and got[0] != skip_clan:
                self.send_standings(sess, got[0])

    # --- what others see: the tag under a name ---------------------------------
    def visible_to(self, viewer):
        """The players whose figures viewer's client has: the room's, or on
        the map those it has been shown (rooms.GlobalMapRoom.seen)."""
        out = []
        if viewer.room is not None:
            out += [s for s in viewer.room.players if s is not viewer]
        if self.gmap is not None:
            out += [s for s in self.gmap.seen.get(viewer, ())]
        return [s for s in out if not s.closed and s.char_id]

    def observers(self, sess):
        """Whoever has sess's figure: the room's others, and on the map the
        viewers it has been shown to."""
        out = []
        if sess.room is not None:
            out += [s for s in sess.room.players if s is not sess]
        if self.gmap is not None:
            out += [v for v, shown in self.gmap.seen.items() if sess in shown and v is not sess]
        return [s for s in out if not s.closed]

    def send_tag(self, viewer, subject, m):
        """fellow about another player (ClanInspector.fellow, case d): the
        clan under his name, and his colour by viewer's standings; reg 0
        clears it. Lost on a client that has no figure for him yet, which is
        why it rides on the answer to getInfo (tag_for) as well."""
        pid = subject.pid
        if not pid:
            return
        v = view(viewer)
        if m is not None:
            viewer.send("fellow", id=pid, reg=int(m["clan_id"]), soc=Str(m["clan_name"]))
            v.tagged[pid] = int(m["clan_id"])
        else:
            viewer.send("fellow", id=pid, reg=0, soc=Str(""))
            v.tagged.pop(pid, None)

    def tag_for(self, viewer, subject):
        """From server.send_other_player_info, after userInfo_Player and
        usrUp: the client has just built the figure and asked about it. A
        member is tagged; somebody this client was once told is in a clan
        and is no longer is untagged (a Player entity outlives its leaving
        the screen, rooms.py); anybody else is left alone, as the client
        starts everyone free."""
        if not subject.char_id:
            return
        m = self.member(subject.char_id)
        if m is not None or subject.pid in view(viewer).tagged:
            self.send_tag(viewer, subject, m)

    def tell_observers(self, sess, m):
        for other in self.observers(sess):
            self.send_tag(other, sess, m)

    # --- the four commands -----------------------------------------------------
    def command(self, sess, cmd, params):
        """server.cmd_head/_admit/_apply/_gg_info: run the handler, and make
        sure exactly one cmdAck came of it."""
        ack = Ack(self, sess, cmd)
        try:
            getattr(self, "_" + cmd)(sess, ack, params)
        except Exception:
            log.exception("  !!    clan %s failed", cmd)
        if ack.sent is None:
            log.error("  !!    clan %s left unanswered; refusing", cmd)
            ack(NOT_ALLOWED)
        return ack.sent

    def _gg_info(self, sess, ack, p):
        det = p.get("det")
        if det == 6:
            # The prices, to anybody, with a character or not: the window
            # asks the moment it opens (ClanInspector.getClanCreationCost).
            # [0] founding in hundredths of gold, [1] a stance down, [2] up.
            sess.send("gg_list", res=6, data=[CREATE_GOLD, STANCE_DOWN, STANCE_UP])
            ack(OK)
            return
        if not sess.char_id or sess.active is None:
            ack(NOT_ALLOWED)
            return
        m = self.member(sess.char_id)
        if det == 1:
            # A free character asking is a client that was put out of its
            # clan earlier on this page (ClanInspector.inClan never falls
            # back): 0 and nothing, never 9, which it would ask again on
            # every five seconds.
            if m is not None:
                self.send_roster(sess, m)
            ack(OK)
        elif det == 5:
            if m is not None:
                self.send_standings(sess, m["clan_id"])
            ack(OK)
        elif det in (3, 4):
            clan_treasury.gg_info(self, sess, ack, m, int(det))
        else:
            ack(NOT_ALLOWED)

    def _head(self, sess, ack, p):
        """Found a clan: head;soc=@name@;reg=@description@;. Answered in this
        order: the purse (userInfo_Player), fellow id=0 with the new clan
        (which makes the client ask for the roster and the standings -- its
        questions queue behind this answer, so the FIFO holds), the
        standings, then cmdAck 0; the founder's tag to whoever sees him and
        the new clan into every other clan's standings after it.

        No level is asked for: the original asked none, and the client has
        no words for such a refusal (createClanCmdAck knows 0, 2, 5, 6, 21)
        -- the player would press «Создать» and see nothing happen."""
        if not sess.char_id or sess.active is None:
            ack.refuse("клан основывает персонаж")
            return
        if self.member(sess.char_id) is not None:
            ack.refuse("вы уже в клане")
            return
        inv = self.live_invite(sess.char_id)
        if inv is not None:
            if time.time() - inv.at < INVITE_RACE:
                # I3: an invitation still on its way to the screen.
                ack.refuse("вас только что пригласили в клан — ответьте на приглашение")
                return
            # Older, and the player could press «Создать» all the same: the
            # popup is modal, so it never showed (another query window was
            # open, or the client had stopped listening). It goes.
            self.drop_invite(sess.char_id, "never shown: the player founds a clan")
        name = clean_name(p.get("soc"))
        if name is None:
            ack(BAD_NAME)
            return
        key = name_key(name)
        if reserved(key) or self.store.clan_by_key(key) is not None:
            ack(NAME_TAKEN)
            return
        ch = sess.character()
        if ch.gold < CREATE_GOLD:
            ack(NO_MONEY)
            return
        gold = ch.gold - CREATE_GOLD
        clan_id = self.store.clan_create(sess.char_id, name, key, clean_descr(p.get("reg")),
                                         (sess.char_id, ch.afro, gold))
        if clan_id is None:
            # A race the look above lost: the same name a moment earlier.
            ack(NOT_ALLOWED if self.member(sess.char_id) is not None else NAME_TAKEN)
            return
        # The copy in memory follows once the database has it: it is what
        # Character.save writes back at logout.
        ch.gold = gold
        self._flag_off(sess)
        m = self.member(sess.char_id)
        log.info("  ..    %s founds the clan %r (%d)", sess.nick, name, clan_id)
        sess.push_money()
        self.fellow_self(sess, m)
        self.send_standings(sess, clan_id)
        ack(OK)
        self.expect_roster(sess)
        self.tell_observers(sess, m)
        self.refresh_standings(skip_clan=clan_id)

    def _admit(self, sess, ack, p):
        """admit;char=@nick@;... invites, admit;char=<id>;... changes a
        member's rights and post -- told apart by the type the value came
        as, never by its digits: a nick "123" comes as @123@. With no char
        at all (a roster row with none, which CSMessage leaves out rather
        than sending) nothing is guessed."""
        if not sess.char_id or sess.active is None:
            ack.refuse("")
            return
        target = p.get("char")
        if isinstance(target, str):
            self.invite(sess, ack, target, p)
        elif _is_int(target):
            self.change_rights(sess, ack, target, p)
        else:
            ack(GONE)

    def _apply(self, sess, ack, p):
        """apply;number=<n>;action=<a>;: 0 the invitation ban, 1 no-thanks /
        leave (number 0) or a kick (number = the member), 2 yes, 3/4 the
        treasury (clan_treasury.py), 5/6/7 diplomacy (clan_diplomacy.py).
        number must come, and be a whole number, for everything but the
        treasury (which reads it itself): a kick of a row with no id is
        sent with no number at all (CSMessage drops undefined), and taken
        for 0 it would be the kicker leaving -- a lone head, disbanding."""
        action = p.get("action")
        if not _is_int(action) or not sess.char_id or sess.active is None:
            ack.refuse("")
            return
        number = p.get("number")
        m = self.member(sess.char_id)
        if action in (3, 4):
            clan_treasury.apply(self, sess, ack, m, number, action)
            return
        if action in (5, 6, 7):
            clan_diplomacy.apply(self, sess, ack, m, number, action)
            return
        if not _is_int(number):
            ack(GONE if action in (1, 2) else NOT_ALLOWED)
            return
        if action == 0 and number == 0:
            self.toggle_invites(sess, ack, m)
        elif action == 2 and number == 0:
            self.accept(sess, ack, m)
        elif action == 1 and number == 0:
            if m is None:
                self.decline(sess, ack)
            else:
                self.leave(sess, ack, m)
        elif action == 1:
            self.kick(sess, ack, m, number)
        elif action == 2:
            ack(GONE)
        else:
            ack(NOT_ALLOWED)

    # --- invitations -----------------------------------------------------------
    def live_invite(self, char_id):
        """The invitation open for char_id, or None; one run out goes."""
        inv = self.invites.get(int(char_id)) if char_id else None
        if inv is not None and time.time() - inv.at > INVITE_TTL:
            self.drop_invite(char_id, "ran out")
            return None
        return inv

    def drop_invite(self, char_id, why):
        inv = self.invites.pop(int(char_id), None)
        if inv is not None:
            log.info("  ..    the clan invitation of %s to clan %d is off: %s",
                     char_id, inv.clan_id, why)

    def invite(self, sess, ack, nick, p):
        """admit;char=@nick@;perm=<p>;post=@s@;. The target sees «Персонаж
        <rec> приглашает вас в клан <soc>» (SceneShifter.inviteInClan) and
        answers apply 2 or 1; the inviter hears «Приглашение отправлено» on
        the 0 that follows the invite frame."""
        m = self.member(sess.char_id)
        if m is None or not m["perm"] & R_ACCEPT:
            ack.rights("приглашать в клан вам нельзя")
            return
        nick = nick.strip()
        row = self.store.character_by_name(nick) if nick else None
        if row is None:
            ack(NO_SUCH_NICK)
            return
        if self.store.clan_member(row["id"]) is not None:
            ack(IN_CLAN)
            return
        target = self.session_of(row["id"])
        if target is None or target.active is None or target.combat.dead:
            # Dead is as good as away: the client lets nothing but the
            # resurrection out while dead (FilterManager.createDSFilter),
            # so the answer could never come.
            ack(OFFLINE)
            return
        if row["clan_no_invites"]:
            # The client has no words for it, and the server's chat is off:
            # this answers what the player just did, so it is said.
            ack(REFUSED)
            sess.answer("%s не принимает приглашений в кланы" % row["name"])
            return
        pending = self.live_invite(row["id"])
        if pending is not None and pending.clan_id != m["clan_id"]:
            ack(REFUSED)
            sess.answer("%s уже приглашён в другой клан — дождитесь его ответа" % row["name"])
            return
        perm = int(p.get("perm") or 0) if _is_int(p.get("perm")) else 0
        perm &= 0xFFFF
        actor_rank = rank(m["perm"])
        granted = (perm & GRANT[actor_rank] & VALID) | (perm & R_BASE)
        if actor_rank <= 1:
            # An inviter with nothing to grant has no boxes to tick
            # (ClanInterface.as:1439-1444): the newcomer gets the chat, or
            # he would be mute and blind to the standings (decision 5).
            granted |= R_CHAT
        post = clean_post(p.get("post"))
        # One open invitation a character: the same clan asking again
        # replaces it and shows the popup again -- the one way out of an
        # invitation lost on its way (a query window already open drops
        # it, SceneShifter.openNewWindow) short of its running out.
        self.invites[int(row["id"])] = Invite(int(m["clan_id"]), int(sess.char_id),
                                              sess.nick, granted, post, time.time())
        target.send("invite", rec=Str(sess.nick), soc=Str(m["clan_name"]), pos=Str(post))
        ack(OK)
        log.info("  ..    %s invites %s into %r", sess.nick, row["name"], m["clan_name"])

    def accept(self, sess, ack, m):
        """apply;number=0;action=2;. Order: fellow id=0 with the clan (the
        client asks for the roster and standings on it), the standings,
        cmdAck 0; then gg_struct act=1 to the others holding the roster --
        never to the newcomer, whose client would take the row for its own
        and replace itself with it (ClanInspector.gg_struct, act 1) -- and
        his tag to whoever sees him."""
        inv = self.live_invite(sess.char_id)
        self.drop_invite(sess.char_id, "answered")
        if inv is None or m is not None:
            ack(GONE)
            return
        try:
            added = self.store.clan_member_add(sess.char_id, inv.clan_id, inv.perm,
                                               inv.post, inv.inviter)
        except storage.IntegrityError:
            added = False
        if not added:
            ack(GONE)
            return
        self._flag_off(sess)
        m = self.member(sess.char_id)
        sess_name = list_safe(sess.nick)
        self.fellow_self(sess, m)
        self.send_standings(sess, m["clan_id"])
        ack(OK)
        self.expect_roster(sess)
        self.push_struct(m["clan_id"], 1, sess.char_id, exclude=sess, name=Str(sess_name),
                         post=Str(m["post"]), date=Str(stamp(time.time())),
                         perm=int(m["perm"]))
        self.tell_observers(sess, m)
        log.info("  ..    %s joins %r", sess.nick, m["clan_name"])

    def decline(self, sess, ack):
        """apply;number=0;action=1; from a free character: no thanks."""
        self.drop_invite(sess.char_id, "declined")
        ack(OK)

    def toggle_invites(self, sess, ack, m):
        """apply;number=0;action=0;: the Settings box «Запретить другим
        игрокам приглашать меня в клан», flipped. cmdAck 0, then fellow
        with the new state: 16777215 forbids, 0 accepts. The box is greyed
        out in a clan."""
        if m is not None:
            ack.refuse("")
            return
        row = self.store.character(sess.char_id)
        flag = 0 if row is not None and row["clan_no_invites"] else 1
        self.store.save_character_state(sess.char_id, clan_no_invites=flag)
        if isinstance(sess.active, dict):
            sess.active["clan_no_invites"] = flag
        ack(OK)
        sess.send("fellow", id=0, reg=FORBID_REG if flag else 0)

    def _flag_off(self, sess):
        """Founding and joining clear the invitation ban (the database's own
        write went with the membership): the box is greyed out in a clan,
        and leaving then needs no fellow reg=16777215, which would bring the
        old clan's name back under the player's own (ClanInspector.fellow,
        case b, leaves the old ClanInfo where it was)."""
        if isinstance(sess.active, dict):
            sess.active["clan_no_invites"] = 0

    # --- rights -----------------------------------------------------------------
    def change_rights(self, sess, ack, char_id, p):
        """admit;char=<id>;perm=<p>;post=@s@;. On oneself, the head alone,
        and the post alone: the page sends the head's own parsed rights,
        which the client's Rights bug has turned into 65535 whatever they
        were (Rights.as:32). On another member: the actor needs 0x200 or
        0x40, must outrank him, he must not be the head, and every bit that
        CHANGES must be one the actor's rank may grant -- a rank-1 editor
        resends the target's own bits from disabled boxes (ClanInterface.
        as:687-692), so "the new code within the grant" would refuse him.
        Order: gg_struct act=3 to the roster holders, fellow id=0 to the
        member (his own rights, chat channel and pages follow only that),
        cmdAck 0."""
        m = self.member(sess.char_id)
        if m is None:
            ack.rights("вы не в клане")
            return
        post = clean_post(p.get("post"))
        perm = (int(p.get("perm")) if _is_int(p.get("perm")) else 0) & 0xFFFF
        if int(char_id) == int(sess.char_id):
            if not m["perm"] & R_HEAD:
                ack.rights("свою должность меняет только глава")
                return
            self.store.clan_member_update(sess.char_id, m["clan_id"], post=post)
            self.push_struct(m["clan_id"], 3, sess.char_id, post=Str(post),
                             perm=int(m["perm"]))
            self.fellow_self(sess)
            ack(OK)
            return
        t = self.store.clan_member(char_id)
        if t is None or int(t["clan_id"]) != int(m["clan_id"]):
            ack(GONE)
            return
        mine, theirs = rank(m["perm"]), rank(t["perm"])
        changed = (perm ^ int(t["perm"])) & ~R_BASE & VALID
        if (not m["perm"] & (R_RIGHTS | R_ACCEPT) or t["perm"] & R_HEAD or mine <= theirs
                or changed & ~GRANT[mine] or perm & R_HEAD):
            ack.rights("эти права менять вам нельзя")
            return
        new = perm & VALID & ~R_HEAD
        if not self.store.clan_member_update(char_id, m["clan_id"], perm=new, post=post):
            ack(GONE)
            return
        self.push_struct(m["clan_id"], 3, char_id, post=Str(post), perm=new)
        target = self.session_of(char_id)
        if target is not None:
            self.fellow_self(target)
        ack(OK)

    # --- leaving -----------------------------------------------------------------
    def leave(self, sess, ack, m):
        """apply;number=0;action=1; from a member. A head passes the clan on
        first (accounts.clan_successor); a head alone disbands it, and what
        the treasury held goes into his purse -- through the live
        Character, so that its save at logout keeps it, pushed before the
        answer. Then cmdAck 0 BEFORE fellow reg=0: the answer closes the
        window (ClanInterface.leaveClanAck), and the fellow first would
        have SceneShifter.kickedFromClan open it again. «Вы больше не
        состоите в клане» follows the fellow."""
        ch = sess.character()
        out = self.store.clan_leave(sess.char_id, m["clan_id"],
                                    purse=(sess.char_id, ch.afro, ch.gold))
        if out is not None and out["paid"]:
            ch.afro += out["paid"]
            sess.push_money()
        ack(OK)
        self.put_out(sess)
        if out is None:
            return
        if out["disbanded"]:
            log.info("  ..    %s leaves %r, the last: disbanded, %d afro paid out",
                     sess.nick, m["clan_name"], out["paid"])
            self.disbanded(m["clan_id"], [])
        else:
            self.push_struct(m["clan_id"], 2, sess.char_id)
            if out["new_head"]:
                self.headed(m["clan_id"], out["new_head"])
            log.info("  ..    %s leaves %r", sess.nick, m["clan_name"])
        self.tell_observers(sess, None)

    def kick(self, sess, ack, m, char_id):
        """apply;number=<member>;action=1;: needs 0x100 and a lower rank, and
        never the head. gg_struct act=2 goes to the roster holders, the
        kicker included, BEFORE his cmdAck 0 (on which his client asks for
        the roster again); then the member, if online, is put out -- «Вас
        исключили из клана» -- and untagged for whoever sees him."""
        if m is None:
            ack(GONE)
            return
        t = self.store.clan_member(char_id)
        if t is None or int(t["clan_id"]) != int(m["clan_id"]):
            ack(GONE)
            return
        if (int(char_id) == int(sess.char_id) or t["perm"] & R_HEAD
                or not m["perm"] & R_KICK or rank(m["perm"]) <= rank(t["perm"])):
            ack.rights("исключить его вам нельзя")
            return
        if not self.store.clan_member_remove(char_id, m["clan_id"]):
            ack(GONE)
            return
        self.push_struct(m["clan_id"], 2, char_id)
        ack(OK)
        log.info("  ..    %s puts %s out of %r", sess.nick, char_id, m["clan_name"])
        target = self.session_of(char_id)
        if target is not None:
            self.put_out(target)
            self.tell_observers(target, None)

    def put_out(self, sess):
        """A client out of its clan: fellow id=0 reg=0 (the "kicked" case of
        ClanInspector.fellow: rights gone, chat channel closed, the alert),
        then the emptied standings (clear_standings). reg=0 and never
        16777215: the ban was cleared on joining."""
        sess.send("fellow", id=0, reg=0)
        self.clear_standings(sess)
        v = view(sess)
        v.forget_clan()
        self._cancel_deaf(v)

    def headed(self, clan_id, new_head):
        """A new head (succession, the admin): his row to the roster
        holders, and his own rights to him."""
        m = self.member(new_head)
        if m is None:
            return
        self.push_struct(clan_id, 3, new_head, post=Str(m["post"]), perm=int(m["perm"]))
        target = self.session_of(new_head)
        if target is not None:
            self.fellow_self(target, m)

    def disbanded(self, clan_id, members):
        """After a clan's rows are gone: each of its members online (the ids
        given) is put out and untagged, invitations into it are void, and
        every other clan's standings lose it."""
        for char_id in members:
            sess = self.session_of(char_id)
            if sess is not None:
                self.put_out(sess)
                self.tell_observers(sess, None)
        for target, inv in list(self.invites.items()):
            if inv.clan_id == int(clan_id):
                self.drop_invite(target, "the clan is disbanded")
        self.refresh_standings(skip_clan=clan_id)

    # --- the clan's chat -----------------------------------------------------------
    def chat(self, sess, raw):
        """userMsg;group=2: the line verbatim to every other member online
        holding 0x2, as userMsg;group=2;player=<char id>;nick;entry -- for
        this channel the client takes the sender from player, not from
        (Chat.as:79-82). Not back to the sender: Chat.delivery printed his
        own line on the cmdAck already sent. From a member without 0x2 it
        goes nowhere: an arriving line opens the channel even where ChatPan
        never did (Chat.as:146-157), and taking the right away was how the
        original muted a member. True when it went out."""
        m = self.member(sess.char_id) if sess.char_id else None
        if m is None or not m["perm"] & R_CHAT:
            return False
        for other, _perm in self.online_members(m["clan_id"], need=R_CHAT):
            if other is not sess:
                other.send("userMsg", group=2, player=int(sess.char_id),
                           nick=Str(sess.nick), entry=Str(raw))
        return True

    # --- presence -------------------------------------------------------------------
    def online(self, sess):
        """The first enter_location of a session (server.py, beside
        PARTIES.online), a no-op after it: seen_at, the client's own fellow
        -- a member's clan, or the invitation ban; a character free and
        open to invitations is what a new page assumes already, and is told
        nothing -- the standings to a member (to every member, not only the
        holders of 0x2 who ask for them: the colours of names are drawn
        from them, decision 6), and act=0 to the others holding the roster.
        The client asks for the roster once it stands somewhere
        (firstRequest), so the lcall may come before or after."""
        v = view(sess)
        if v.told or not sess.char_id:
            return
        v.told = True
        now = int(time.time())
        self.store.save_character_state(sess.char_id, seen_at=now)
        m = self.member(sess.char_id)
        if m is not None:
            self.fellow_self(sess, m)
            self.send_standings(sess, m["clan_id"])
            self.push_struct(m["clan_id"], 0, sess.char_id, exclude=sess,
                             date=Str(stamp(now)), perm=int(m["perm"]))
        else:
            row = self.store.character(sess.char_id)
            if row is not None and row["clan_no_invites"]:
                sess.send("fellow", id=0, reg=FORBID_REG)

    def entered(self, sess):
        """After a lenter (server.cmd_lenter): the location is open, so a
        member's client that listens asks for the roster now. One that
        does not -- a page that has lost a connection before: ClanInspector
        kill()s itself on close and is never made again (ClanInspector.as:
        21-30, 52-68, 819-823) -- is told once to start the game again, in
        the log always and in the chat only while SERVER_CHAT is on."""
        self.expect_roster(sess)

    def expect_roster(self, sess):
        v = view(sess)
        if v.asked or v.warned or v.timer is not None or DEAF_CHECK <= 0:
            return
        if self.member(sess.char_id) is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        v.timer = loop.call_later(DEAF_CHECK, self._deaf, sess)

    def _deaf(self, sess):
        v = view(sess)
        v.timer = None
        if sess.closed or v.asked or v.warned or self.member(sess.char_id) is None:
            return
        v.warned = True
        log.info("  ..    %s's client did not ask for its clan: told to reload", sess.nick)
        sess.say(DEAF_LINE)

    @staticmethod
    def _cancel_deaf(v):
        if v.timer is not None:
            v.timer.cancel()
            v.timer = None

    def offline(self, sess):
        """From Session.close, beside PARTIES.disconnected, so it must not
        raise: act=4 to the roster holders, seen_at, the invitation for
        this character void (a new socket is a new page with no popup), and
        what this client was told forgotten."""
        try:
            v = view(sess)
            self._cancel_deaf(v)
            if sess.char_id:
                self.drop_invite(sess.char_id, "logged out")
                if v.told:
                    self.store.save_character_state(sess.char_id, seen_at=int(time.time()))
                    m = self.member(sess.char_id)
                    if m is not None:
                        self.push_struct(m["clan_id"], 4, sess.char_id, exclude=sess)
            v.forget_clan()
            v.tagged = {}
        except Exception:
            log.exception("  !!    clan bookkeeping failed on disconnect")

    def forget(self, char_id):
        """A new character (server.cmd_newPers): SQLite hands out a deleted
        character's id again, and nothing of his may stick to it."""
        self.drop_invite(char_id, "a new character under the id")

    # --- the public API for clan_treasury, clan_diplomacy, clan_admin -----------
    def pay_purse(self, char_id):
        """(session or None, (char_id, afro, gold)) to pay into a purse: the
        live Character's while he plays -- Character.save writes it back at
        logout -- or None for the row's."""
        sess = self.session_of(char_id)
        if sess is not None and sess.char is not None:
            ch = sess.character()
            return sess, (int(char_id), ch.afro, ch.gold)
        return None, None

    def disband(self, clan_id, payout_char=None):
        """Disband a clan (the admin's): the treasury into payout_char's
        purse, the head's by default -- through his live Character and a
        purse push when he plays -- then every member put out. Returns the
        afro paid, or None when there was no such clan."""
        clan = self.store.clan(clan_id)
        if clan is None:
            return None
        payout_char = int(payout_char or clan["head"])
        members = [c for c, _p in self.store.clan_member_perms(clan_id)]
        sess, purse = self.pay_purse(payout_char)
        paid = self.store.clan_disband(clan_id, payout_char, purse)
        if paid is None:
            return None
        if paid and sess is not None:
            sess.character().afro += paid
            sess.push_money()
        self.disbanded(clan_id, members)
        return paid

    def set_head(self, clan_id, new_head, old_perm=VALID & ~R_HEAD):
        """Hand a clan to one of its members (the admin's): both rows to the
        roster holders, both their own rights to them."""
        clan = self.store.clan(clan_id)
        if clan is None or not self.store.clan_set_head(clan_id, new_head, old_perm):
            return False
        old = int(clan["head"])
        if old != int(new_head):
            om = self.member(old)
            if om is not None:
                self.push_struct(clan_id, 3, old, post=Str(om["post"]), perm=int(om["perm"]))
                target = self.session_of(old)
                if target is not None:
                    self.fellow_self(target, om)
        self.headed(clan_id, new_head)
        return True

    def remove_member(self, clan_id, char_id):
        """Put a member out without a kicker (the admin's): the kick's
        pushes, less the answer. Not the head (set_head first)."""
        if not self.store.clan_member_remove(char_id, clan_id):
            return False
        self.push_struct(clan_id, 2, char_id)
        target = self.session_of(char_id)
        if target is not None:
            self.put_out(target)
            self.tell_observers(target, None)
        return True

    def name_of(self, char_id):
        """The name of the character's clan, '' for none: trophies' v_clan."""
        m = self.member(char_id)
        return m["clan_name"] if m is not None else ""
