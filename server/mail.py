"""Mail: letters between characters, with money and items inside.

The window is lol/gpui/MailInterface.as, the model lol/core/mail/
(MailInspector, LetterObject, MailParam), and the cycle is
recon/analysis/world.md section 7. Five commands, each expecting exactly one
cmdAck first (MailInspector registers one on every send), and two of them
also waiting on a control packet, ctml, that goes out ONLY after res=0:
sendLetterAck and getObjectsFromLetterAck call skipCall("ctml") on any
other answer, so a ctml after a refusal would be consumed by the next
sndml or uldml.

    chkml;mode=0|1|255       -> cmdAck, then lsml (inbox/outbox) or svml
    getml;id=xN              -> cmdAck (0 | 35), then rcml
    sndml;to;subj;type;body;item=xN...;afro;gold
                             -> cmdAck (0 | 34 | 37 | 3), at 0 also ctml;
                                types 2/3 go to the whole clan (clan_letter)
    uldml;id=xN              -> cmdAck (0 | 35 | 36), at 0 also ctml
    rmvml;id=xN;id=xN;...    -> cmdAck

Letter ids travel as big-uints and come back byte for byte (BigUINTCluster
of a string is the string), so they are spelled in decimal: the client
compares a ctml id both with == 0 and with the id it listed, and a decimal
string equals both the number and itself in AS2.

An attachment leaves the sender's bag when the letter is sent and is a
new instance in the addressee's bag when taken out (uldml): while in the
letter it is a snapshot in items_json, not a row in items, so nobody can
wear, sell or load it in transit. The oid shown in the letter keeps the
sender's serial, which AUTOINCREMENT never hands out again.

Delivery is immediate and the tariff table says so (time 0): the times in
svml are only ever displayed by the client, and a two-player world has no
couriers to wait for. Prices are designed here, not recovered.
"""
import json
import logging
import math
import time
import unicodedata

import accounts
import inventory
import items
import rooms
from protocol import BigUInt, Str, every

log = logging.getLogger("lava")

# Letter types, the radio buttons of MailInterface.__sendLetter. Even ones
# are paid in afro, odd ("срочное") in gold. 4/5 carry an asking price
# instead of attached money, 6/7 order goods and are not understood yet.
LETTER, LETTER_EXPRESS = 0, 1
CLAN, CLAN_EXPRESS = 2, 3
TRADE, TRADE_EXPRESS = 4, 5
ORDER, ORDER_EXPRESS = 6, 7

# Letters the server files itself (auction.py) come from character 0,
# which no character is: ids start at 1. The name is what the inbox shows
# for them, and no player may take it (is_system_name): a reply to the
# auction would otherwise reach whoever did, and a letter from them would
# look like one from the house.
SYSTEM_SENDER = 0
SYSTEM_NAME = "Аукцион"

# Latin and Greek letters that look like Cyrillic ones, and the zero that
# looks like an о, so "Aукцион" with a Latin A or "Αукцион" with a Greek
# one cannot pass for the house in an inbox either. Lower case only: the
# name is case-folded first.
_LOOKALIKE = str.maketrans("aceopxykmhtb" "αβεοκμηρτυχ" "0",
                           "асеорхукмнтв" "авеокмнртух" "о")


def _skeleton(name):
    """What a name looks like on the screen, for comparing: compatibility
    forms folded (a fullwidth or mathematical А is an А), case folded,
    accents split off and dropped with everything that draws nothing --
    combining marks, format characters such as the zero-width space and
    the word joiner, controls and spaces -- then the lookalikes."""
    s = unicodedata.normalize("NFKC", str(name or "")).casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c)[0] not in "MCZ")
    return s.translate(_LOOKALIKE)


def is_system_name(name):
    """Whether a name would read as the auction house's: the same letters in
    any case, lookalikes, accents and invisible characters included. Such a
    name is refused at newPers and as a letter's addressee."""
    return _skeleton(name) == _skeleton(SYSTEM_NAME)


# flag bits (LetterObject.set flag); bits 0-3 are the type
FLAG_RETURNED = 1 << 4
FLAG_ATTACHED = 1 << 5
FLAG_UNREAD = 1 << 6
FLAG_OUTBOX = 1 << 7

# cmdAck codes the client words (MailInspector.*Ack)
RES_OK = 0
RES_BAN = 2
RES_REFUSED = 3            # nothing on screen, the client only skips ctml
RES_NO_ADDRESSEE = 34      # "Игрок <..> не найден"
RES_NO_LETTER = 35
RES_NOTHING_TO_TAKE = 36
RES_NOT_IN_CLAN = 37

# ctml codes (MailInspector.sendMailControlPacket_XMC / getObjectsControlPacket_XMC)
CODE_NONE = 0              # no case matches: an empty slot
CODE_TAKEN = -1            # sndml: item left the bag; uldml 5/6: money paid
CODE_GOT = 1               # uldml: item or money received
CODE_NOT_FOUND = -9
CODE_NOT_ATTACHABLE = -11
CODE_NO_MONEY = 9          # uldml 5/6: cannot pay the asking price
CODE_FAILED = 11

# The window holds five items (MailInterface.numberOfItems counts to 5,
# the control packet indexes 0..4 for items and 5/6 for afro/gold).
MAX_ATTACHMENTS = 5
SUBJECT_MAX = 120          # MailInterface.__sendLetter: subj.substr(0, 120)
# Whether a letter may carry gold, attached or as an offer's price. Off
# (2026-09-28, with the rate at 50 000): the original moved gold between
# players by the auction alone, as ingots, and gold earned on a second
# character would otherwise be posted to the first and cashed.
GOLD_BY_POST = False

# Tariffs (svml), in the order MailParam reads them: letter, express
# letter, clan, express clan, per kg, express per kg, order, express
# order. Odd entries are gold in hundredths (MailParam divides by 100).
# Designed, not recovered: cheap enough to be used, dear enough that gold
# stays the express currency.
PRICES = [10, 20, 10, 20, 2, 5, 50, 100]
TIMES = [0] * 8

# Which base price a type is charged (MailInterface.updateLetterPrise:
# plain and trade letters share the first pair, clan the second, orders the
# fourth), and whether the parcel's weight is added at 2/5 per kilogram.
BASE_INDEX = {LETTER: 0, LETTER_EXPRESS: 1, CLAN: 2, CLAN_EXPRESS: 3,
              TRADE: 0, TRADE_EXPRESS: 1, ORDER: 6, ORDER_EXPRESS: 7}
WEIGHED = (LETTER, LETTER_EXPRESS, TRADE, TRADE_EXPRESS)


def tariff(kind, grams):
    """(afro, gold) the sender pays, as the window shows it: base plus
    floor(kg x per-kg), the express pair in hundredths of gold."""
    express = kind % 2
    total = PRICES[BASE_INDEX[kind]]
    if kind in WEIGHED:
        total += int(math.floor(grams / 1000.0 * PRICES[5 if express else 4]))
    return (0, total) if express else (total, 0)


def postable(type_id):
    """Whether a thing may go into a letter. The client's own test is the
    static exchang flag (MailInterface.drop: «Данный предмет нельзя
    передавать»), and a modified client would not make it; a quest's thing
    stays with its quest, as at the auction. A thing with no exchange that
    got into a letter all the same would be out of the reach of the quest
    that handed it over, which takes back only what the character carries
    or banks (Inventory.reclaim_pieces): Аюб's notes, posted, were a new set
    at every take of «Новые вопросы» (quests.START_OBJ_NOT_ON_GROUND). And
    never a premium thing (items.premium), which is out of the game and
    does not change hands, as at the barter and the auction (the owner's
    cut of (P), 2026-09-30), nor one the owner took out by name
    (items.out_of_game, data/retired.json items: Steyr TMP and Chang Feng,
    2026-10-14). Gold items use the same binding rule as barter."""
    from barter import tradable
    return tradable(type_id)


def stamp(when):
    """"YYYY-MM-DD HH:MM:SS" in UTC; LetterObject.set time adds the local
    offset itself."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(when))


def snapshot(row):
    """An item row as it goes into a letter: the serial, so the oid the
    addressee sees is the one the sender had, and every dynamic field."""
    snap = {"uniq": row["uniq"], "type_id": row["type_id"], "root": row["root"]}
    for f in accounts.ITEM_FIELDS:
        snap[f] = row[f]
    return snap


def describe(snap):
    """The attachment block LetterObject.set body reads off the front of
    the text: HS is a stack size, HC the charges of a heal item, BS the
    durability of anything breakable."""
    root = snap["root"]
    if root in items.HEAPABLE_ROOTS or root == items.TROPHY:
        return "=?HS:%d?=" % snap["count"]
    if root == items.HEAL:
        return "=?HC:%d?=" % snap["use_count"]
    return "=?BS:%d/%d?=" % (snap["brk"], snap["max_break_cur"])


def wire_body(text, snaps):
    """Attachment blocks, padding, then the text.

    LetterObject.set body cuts each block off the front in a loop and
    then, after the loop, cuts ONCE MORE by the length of the last block
    header plus two: `_body = rest.substring(lastQ + 2)`, where lastQ is
    the offset of the last "?=" and rest already starts past it. With no
    blocks lastQ is undefined and the cut is from 0. So a letter with a
    parcel loses its first len("=?BS:120/120") + 2 characters unless that
    many are put there to be lost.
    """
    if not snaps:
        return text
    blocks = [describe(s) for s in snaps]
    last = blocks[-1]
    pad = " " * (last.index("?=") + 2)
    return "".join(blocks) + pad + text


def attached(row):
    return row["afro"] or row["gold"] or row["items_json"] != "[]"


def flag_of(row, outbox):
    f = row["type"] & 0xF
    if row["returned"]:
        f |= FLAG_RETURNED
    if attached(row):
        f |= FLAG_ATTACHED
    if outbox:
        # isOutbox looks at flag[0] of a listing; the sender's copy is
        # never "unread".
        f |= FLAG_OUTBOX
    elif not row["read"]:
        f |= FLAG_UNREAD
    return f


def _money(value):
    """Whether a letter's afro or gold field holds anything: a number other
    than 0, or anything else at all -- the window Number()s its text field,
    and what is not a number is not nothing either."""
    if value is None or value == "":
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return True


def letter_id(text):
    """The row id out of a big-uint parameter, or None."""
    try:
        return int(str(text), 10)
    except (TypeError, ValueError):
        return None


class Mail:
    """One connection's mailbox. Owned by server.Session, next to Inventory."""

    def __init__(self, sess, store, directory):
        self.sess = sess
        self.store = store
        self.directory = directory  # rooms.Directory, for the new-letter push
        # Whether this client has listed its inbox (chkml;mode=0) this
        # session. MailInspector.listMail_XMC APPENDS whatever lsml brings,
        # and its first getInbox() fetches the whole box from the server,
        # so a letter pushed before that would be listed twice.
        self.synced = False

    # --- plumbing ----------------------------------------------------------
    @property
    def char_id(self):
        return self.sess.char_id

    def send(self, cmd, **params):
        self.sess.send(cmd, **params)

    def ack(self, res):
        self.send("cmdAck", res=res)

    def name_of(self, char_id):
        if char_id == SYSTEM_SENDER:
            return SYSTEM_NAME
        row = self.store.character(char_id)
        return row["name"] if row else "?"

    def side_of(self, row):
        """"in" if the letter sits in this character's inbox, "out" for
        the outbox, None if it is not theirs to see."""
        if row is None or not self.char_id:
            return None
        if row["to_char"] == self.char_id and not row["to_deleted"]:
            return "in"
        if row["from_char"] == self.char_id and not row["from_deleted"]:
            return "out"
        return None

    def session_of(self, char_id):
        return self.directory.by_pid(rooms.player_id(char_id))

    # --- listings ----------------------------------------------------------
    def listing(self, rows, outbox):
        """lsml: five parallel lists. name is the other party: the sender
        for the inbox, the addressee for the outbox (listMail_XMC builds
        the LetterObject with "я"/"мне" on the near side)."""
        self.send("lsml",
                  id=[BigUInt(str(r["id"])) for r in rows],
                  date=[stamp(r["sent_at"]) for r in rows],
                  name=[self.name_of(r["to_char"] if outbox else r["from_char"])
                        for r in rows],
                  flag=[flag_of(r, outbox) for r in rows],
                  subj=[r["subject"] for r in rows])

    def chkml(self, p):
        """mode 0 inbox, 1 outbox, 255 tariffs; the ack comes first."""
        mode = int(p.get("mode", 0) or 0)
        self.ack(RES_OK)
        if mode == 255:
            self.send("svml", data=list(PRICES), time=list(TIMES))
        elif mode == 1:
            self.listing(self.store.mail_outbox(self.char_id) if self.char_id
                         else [], outbox=True)
        else:
            self.listing(self.store.mail_inbox(self.char_id) if self.char_id
                         else [], outbox=False)
            self.synced = True

    def arrived(self, row):
        """A letter for this character has just been filed. The client
        asks for its inbox by itself and shows the envelope from what it
        holds (LocationInterface.checkNewLetter on UPDATE_INBOX), so one
        more lsml is all a push takes -- once the box has been listed."""
        if self.synced:
            self.listing([row], outbox=False)

    # --- one letter ----------------------------------------------------------
    def getml(self, p):
        row = self.store.mail_letter(letter_id(p.get("id")))
        side = self.side_of(row)
        if side is None:
            self.ack(RES_NO_LETTER)
            return
        if side == "in" and not row["read"]:
            # rcml carries the flag again and the window un-bolds the
            # entry when it reads it as read (doLaterShowLetterInfo).
            self.store.mail_update(row["id"], read=1)
            row["read"] = 1
        snaps = json.loads(row["items_json"])
        self.ack(RES_OK)
        self.send("rcml", id=BigUInt(str(row["id"])),
                  flag=flag_of(row, side == "out"),
                  date=Str(stamp(row["sent_at"])),
                  to=Str(self.name_of(row["to_char"])),
                  body=Str(wire_body(row["body"], snaps)),
                  items=[BigUInt(inventory.oid(s["uniq"], s["type_id"], s["root"]))
                         for s in snaps],
                  afro=row["afro"], gold=row["gold"],
                  **{"from": Str(self.name_of(row["from_char"]))})

    # --- sending ---------------------------------------------------------------
    def sndml(self, p):
        """Charge the tariff and whatever is attached, move the items out of
        the bag into the letter, file it, then tell the client which items
        to drop (ctml code -1 each) and what the purse holds now."""
        if not self.char_id:
            self.ack(RES_REFUSED)
            return
        kind = int(p.get("type", 0) or 0)
        if kind in (CLAN, CLAN_EXPRESS):
            self.clan_letter(p, kind)
            return
        afro = int(p.get("afro", 0) or 0)
        gold = int(p.get("gold", 0) or 0)
        if kind not in BASE_INDEX or kind in (ORDER, ORDER_EXPRESS) \
                or afro < 0 or gold < 0:
            self.ack(RES_REFUSED)
            return
        if gold and not GOLD_BY_POST:
            # Gold changes hands by the auction alone, as ingots (the wiki's
            # «Покупка голд»: «Голд нельзя передавать ... на прямую, только
            # через Аукцион»); neither attached nor asked as a price. The
            # express tariff is still paid in gold: that leaves the game.
            log.info("  ..    letter with %d gold refused", gold)
            self.ack(RES_REFUSED)
            return
        to = str(p.get("to") or "").strip()
        # "Ответить" on a letter from the auction fills in its name; the
        # house reads nothing, and a character that slipped in under that
        # name before it was reserved must not get the replies.
        target = None if is_system_name(to) else self.store.character_by_name(to)
        if target is None or target["id"] == self.char_id:
            self.ack(RES_NO_ADDRESSEE)
            return
        oids = every(p, "item")
        if len(oids) > MAX_ATTACHMENTS or \
                (kind in (TRADE, TRADE_EXPRESS) and not oids):
            self.ack(RES_REFUSED)
            return
        rows = []
        for text in oids:
            row = self.sess.inv.find(text)
            if row is None or not postable(row["type_id"]):
                # The window only offers what the bag holds and what may
                # change hands, so this is a modified client or a stale id;
                # no ctml at all is what keeps its queue straight.
                log.info("  ..    letter attachment %s refused", text)
                self.ack(RES_REFUSED)
                return
            rows.append(row)
        fee_afro, fee_gold = tariff(kind, sum(inventory.weight_of(r) for r in rows))
        # An offer names its price; nothing but the tariff leaves the purse.
        put_afro, put_gold = (0, 0) if kind in (TRADE, TRADE_EXPRESS) else (afro, gold)
        ch = self.sess.character()
        if not ch.can_afford(fee_afro + put_afro, fee_gold + put_gold):
            # No code of sendLetterAck says this; the chat the player has
            # open under the window does.
            self.ack(RES_REFUSED)
            self.sess.say("Не хватает денег на отправку письма")
            return
        ch.add_money(-(fee_afro + put_afro), -(fee_gold + put_gold))
        ch.save(self.store)
        snaps = [snapshot(r) for r in rows]
        for r in rows:
            self.sess.inv.forget_reload(r["uniq"])
            self.store.delete_item(r["uniq"])
        letter = self.store.mail_send(
            target["id"], self.char_id, kind,
            str(p.get("subj") or "")[:SUBJECT_MAX], str(p.get("body") or ""),
            afro, gold, json.dumps(snaps))
        log.info("  ..    letter #%d to %s: %d item(s), %d afro, %d gold,"
                 " fee %d/%d", letter["id"], target["name"], len(rows),
                 afro, gold, fee_afro, fee_gold)
        self.ack(RES_OK)
        # The client removes each item from its own equipment on -1
        # (removeFromEquip), so no ss_obj_status here.
        self.send("ctml", id=BigUInt(str(letter["id"])),
                  item=[BigUInt(inventory.oid_of(r)) for r in rows],
                  code=[CODE_TAKEN] * len(rows))
        self.sess.push_money()
        self.deliver(letter)

    def deliver(self, letter):
        other = self.session_of(letter["to_char"])
        if other is not None:
            other.mail.arrived(letter)

    # --- the clan's mail ---------------------------------------------------------
    def clan_letter(self, p, kind):
        """sndml type 2 («Внутриклановая рассылка», afro) or 3 (the express
        one, gold): the letter to every member of the sender's clan but
        himself, those offline too (the owner's decision 10), for one
        tariff, flat -- MailInterface.updateLetterPrise weighs nothing for
        these two, and tariff() does not either.

        The window hides the addressee and nulls the parcel for these types
        (MailInterface.__sendLetter, :1112-1120), but still sends whatever
        `to` held and whatever afro or gold was typed before the radio was
        switched: `to` is not read, and money or a parcel refuses the
        letter -- a clan's mail carries words only. Membership is the
        database's (clans.py keeps nothing in memory), never the client's:
        the radios are greyed out only while clanInfo.reg is 0, and a
        client put out of its clan keeps its old reg until the page is
        reloaded (ClanInspector.fellow, the kicked case). No right gates
        it: the window asks for none, only for a clan.

        Every refusal is 37, the one code sendLetterAck keeps for these
        letters. It has no listener in the window, so it is silent -- and
        never 3, which ErrorReport shows as «Сервер не отвечает» over the
        whole screen, nor 2 («Аккаунт забанен»), nor 34, whose alert names
        an addressee the window hid. A character in no clan -- a client
        kept stale since a kick -- gets the bare 37; for the rest, a letter
        the player wrote and pressed «Отправить» for, the reason is said to
        him (Session.answer: the answer to his own action, as clans.invite
        does for its silent 29).

        On 0: cmdAck, the ctml the window queued (the first letter's id,
        nothing taken out of the bag), the purse, then each letter to its
        addressee if he plays. The letters and the postage are one
        transaction (Store.mail_send_each); the sender's outbox holds one
        copy, the first."""
        m = self.store.clan_member(self.char_id)
        if m is None:
            log.info("  ..    clan letter from %s, who is in no clan", self.sess.nick)
            self.ack(RES_NOT_IN_CLAN)
            return
        if every(p, "item") or _money(p.get("afro")) or _money(p.get("gold")):
            self.ack(RES_NOT_IN_CLAN)
            self.sess.answer("Во внутриклановую рассылку нельзя вложить ни деньги, ни"
                             " вещи: очистите поля «афро» и «золото» и отправьте снова")
            return
        to = [c for c, _perm in self.store.clan_member_perms(m["clan_id"])
              if c != self.char_id]
        if not to:
            self.ack(RES_NOT_IN_CLAN)
            self.sess.answer("В клане «%s», кроме вас, никого нет: рассылать некому"
                             % m["clan_name"])
            return
        fee_afro, fee_gold = tariff(kind, 0)
        ch = self.sess.character()
        if not ch.can_afford(fee_afro, fee_gold):
            self.ack(RES_NOT_IN_CLAN)
            self.sess.answer("Не хватает денег на рассылку: она стоит %s"
                             % ("%d афро" % fee_afro if fee_afro
                                else ("%.2f G" % (fee_gold / 100.0)).replace(".", ",")))
            return
        letters = self.store.mail_send_each(
            to, self.char_id, kind, str(p.get("subj") or "")[:SUBJECT_MAX],
            str(p.get("body") or ""), (self.char_id, ch.afro - fee_afro, ch.gold - fee_gold))
        # The copy in memory follows the row: it is what Character.save
        # writes back at logout.
        ch.add_money(-fee_afro, -fee_gold)
        log.info("  ..    clan letter #%d.. from %s to %d member(s) of %r, fee %d/%d",
                 letters[0]["id"], self.sess.nick, len(letters), m["clan_name"],
                 fee_afro, fee_gold)
        self.ack(RES_OK)
        self.send("ctml", id=BigUInt(str(letters[0]["id"])), item=[], code=[])
        self.sess.push_money()
        for letter in letters:
            self.deliver(letter)

    # --- taking the parcel out --------------------------------------------------
    def uldml(self, p):
        """Items into the bag, money into the purse; for an offer the price
        goes the other way and reaches the seller as a letter of its own.

        The control packet is seven slots: five items, afro, gold, each
        with a code. On code 1 the client builds the item and puts it in
        the bag itself (addInEquip) and adds the money itself (updMoney),
        so nothing is pushed for the items; the purse is re-sent because
        the client's own arithmetic is not the record.
        """
        row = self.store.mail_letter(letter_id(p.get("id")))
        if self.side_of(row) != "in":
            self.ack(RES_NO_LETTER)
            return
        snaps = json.loads(row["items_json"])
        if not attached(row):
            self.ack(RES_NOTHING_TO_TAKE)
            return
        ch = self.sess.character()
        # A returned offer is the seller's own goods coming back: a parcel,
        # not a sale (rmvml has zeroed the asking price by then).
        offer = row["type"] in (TRADE, TRADE_EXPRESS) and not row["returned"]
        afro, gold = row["afro"], row["gold"]
        if offer and not ch.can_afford(afro, gold):
            self.ack(RES_OK)
            self.send("ctml", id=BigUInt(str(row["id"])),
                      item=[BigUInt("0")] * MAX_ATTACHMENTS
                      + [BigUInt("%x" % afro), BigUInt("%x" % gold)],
                      code=[CODE_NONE] * MAX_ATTACHMENTS
                      + [CODE_NO_MONEY if afro > ch.afro else CODE_NONE,
                         CODE_NO_MONEY if gold > ch.gold else CODE_NONE])
            return
        created = []
        for s in snaps:
            fields = {f: s[f] for f in accounts.ITEM_FIELDS}
            fields["slot"] = inventory.BAG
            created.append(self.store.create_item(
                self.char_id, s["type_id"], s["root"], **{k: v for k, v in fields.items() if k not in ('char_id', 'uniq')}))
            if s["root"] == items.TROPHY:
                # Unpacked under a new serial: its words follow it.
                self.store.rekey_trophy(s["uniq"], created[-1]["uniq"])
        if offer:
            ch.add_money(-afro, -gold)
        else:
            ch.add_money(afro, gold)
        ch.save(self.store)
        self.store.mail_update(row["id"], items_json="[]", afro=0, gold=0)
        log.info("  ..    letter #%d unpacked: %d item(s), %d afro, %d gold%s",
                 row["id"], len(created), afro, gold, " paid" if offer else "")
        self.ack(RES_OK)
        money_code = CODE_TAKEN if offer else CODE_GOT
        pad = MAX_ATTACHMENTS - len(created)
        self.send("ctml", id=BigUInt(str(row["id"])),
                  item=[BigUInt(inventory.oid_of(r)) for r in created]
                  + [BigUInt("0")] * pad
                  + [BigUInt("%x" % afro), BigUInt("%x" % gold)],
                  code=[CODE_GOT] * len(created) + [CODE_NONE] * pad
                  + [money_code if afro else CODE_NONE,
                     money_code if gold else CODE_NONE])
        if afro or gold:
            self.sess.push_money()
        if offer and (afro or gold):
            # The seller is paid by mail: money attached, no tariff, the
            # buyer named as the sender so the outbox reads right.
            payment = self.store.mail_send(
                row["from_char"], self.char_id, LETTER,
                ("Оплата: " + row["subject"])[:SUBJECT_MAX],
                "%s забрал предложенные предметы." % self.sess.nick,
                afro, gold, "[]")
            self.deliver(payment)

    # --- deleting ----------------------------------------------------------------
    def rmvml(self, p):
        """One acknowledgement for the whole list; the client drops the ids
        from its own arrays on res=0 (removeLettersAck).

        An inbox letter still holding a parcel is not thrown away: it goes
        back to the sender as a returned letter (flag bit 4), which is
        also what the offer window's "отказаться" button amounts to. A
        returned letter thrown away loses its parcel; it has nowhere left
        to go.

        A letter from the auction house (SYSTEM_SENDER) that still holds
        its purchase, payment or refund has nobody to go back to either,
        and throwing it away would throw the goods away with it. So such a
        request is refused whole, with the one code the window words
        (removeLettersAck 2: "Недопустимое действие"), and nothing on the
        list is deleted: on any code but 0 the client keeps every id it
        asked about, and deleting some of them anyway would leave letters in
        its list that are gone here. The window asks one letter at a time.
        """
        ids = every(p, "id")
        for text in ids:
            row = self.store.mail_letter(letter_id(text))
            if self.side_of(row) == "in" and row["from_char"] == SYSTEM_SENDER \
                    and attached(row):
                log.info("  ..    letter #%d from the auction still holds its"
                         " parcel, not deleted", row["id"])
                self.ack(RES_BAN)
                self.sess.say("Письмо аукциона нельзя удалить, пока в нём"
                              " что-то лежит: сначала заберите вложение")
                return
        for text in ids:
            row = self.store.mail_letter(letter_id(text))
            side = self.side_of(row)
            if side == "in":
                if attached(row) and not row["returned"] \
                        and row["from_char"] != row["to_char"]:
                    # An offer's afro/gold were the asking price, and
                    # nothing to hand back.
                    offer = row["type"] in (TRADE, TRADE_EXPRESS)
                    self.store.mail_update(
                        row["id"], to_char=row["from_char"], returned=1,
                        read=0, to_deleted=0, from_deleted=1,
                        sent_at=int(time.time()),
                        afro=0 if offer else row["afro"],
                        gold=0 if offer else row["gold"])
                    log.info("  ..    letter #%d returned to its sender", row["id"])
                    self.deliver(self.store.mail_letter(row["id"]))
                    continue
                row["to_deleted"] = 1
                self.store.mail_update(row["id"], to_deleted=1)
            elif side == "out":
                row["from_deleted"] = 1
                self.store.mail_update(row["id"], from_deleted=1)
            else:
                log.info("  ..    rmvml for letter %r, not this character's", text)
                continue
            # The house keeps no outbox, so its letters have only one side
            # to be deleted from.
            if row["to_deleted"] and (row["from_deleted"]
                                      or row["from_char"] == SYSTEM_SENDER):
                self.store.mail_delete(row["id"])
        self.ack(RES_OK)
