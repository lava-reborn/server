"""Trophies: what a player killed by a player leaves the one who killed them,
and where it is registered for the fighter's skill («Навык бойца», rep).

The owner's rules of 2026-09-25: «обязательно падает трофей, если убивший
ниже лвл-ом или одинакового»; «навык бойца качается, если убить кого-то,
получить с него трофей и сдать. Я помню, был моб, у которого можно было
зарегистрировать трофей».

WHAT THE ORIGINAL LEFT

  the things    Root 6 of objects.xml: tr_Skull 1492, tr_Scalp 1493,
                tr_Finger 1494, tr_Ear 1495, tr_Hand 1496 (and tr_Heart,
                tr_Horn, tr_Token, which the mobs' quests speak of). Their
                names are the original's: Череп, Скальп, Палец, Ухо, Кисть.
                Their base price (the wiki: 200, 100, 30, 25, 1500 afro) is
                the registration fee the client's own window shows.
  what one says The client's Trophy (core/objects/Trophy.as) takes count,
                k_id, k_name, k_lvl, v_id, v_name, v_lvl, v_clan and time
                from its ss_di_trophy (ItemFactory.updateItemDI copies every
                key onto the item), and the annotation (gpui/Annotation.
                trophy) prints them as «Количество», «Имя убийцы», «Уровень
                убийцы», «Имя жертвы», «Уровень жертвы», «Клан жертвы» and
                «Последнее убийство» -- the last parsed out of
                "YYYY-MM-DD HH:MM:SS" in UTC (Annotation.parseDate adds the
                viewer's offset). The icon wears the victim's name
                (ItemContainer: v_name.toUpperCase()).
  where         "Мясники, скупка трофеев" on the client's own map
                (database/locations.xml) in Вади-Хальфа, Донгола and
                Абу-Хамед; the wiki's «Мясники» with six «Сумасшедший
                живодер» collectors. Of the three only Вади-Хальфа's is a
                location this world places (164, VH_Butchers, 5979,1721).
                The original also had "Регистрация трофеев" people
                (Tr_registr_*, texts.xml 50639..50641) that no location
                puts down. See world.TROPHY_REGISTRARS.
  how           The registration window (gpui/RegTrophyInterface) is part of
                a trade session: Trade.regTrophy sends ss_upd;s_status=6;
                obj=<trophy> and waits for a cmdAck; the price is the
                trophy's cost, "0" drawn as 1, in afro ("Сохранить все
                трофеи? Стоимость: N А"). On res=0 the trophy fades out of
                the window, and the bag loses it through ss_obj_status 0
                (the window's "save all" leaves the rest of its bag view to
                that frame). What is saved is kept in the collection, the
                s_type=6 session of gpui/TrophyInterface (the location
                window's trophy button): ss_get;slot=16 lists it, ss_get_di
                describes each, ss_upd 4 deletes one; 1 and 3 put one on
                show and buy a place for that (ss_get;slot=32).
  the show      «Демонстрируемые трофеи»: the column of places on the right
                of that window (trophySlotPan, one under another, "ЗАНЯТО
                МЕСТ n ИЗ m") and the second page of another player's
                inspect window (gpui/InspectInterface, the trophy tab: a
                grid three wide, never fewer than 12 cells drawn). Both
                draw PersEquip.publicTrophy_arr, which is the o_list of
                ss_get;target=<whose>;slot=32 -- one entry per place, "0"
                for an empty one (StuffManager.createItem makes nothing of
                it), its length the number of places; the owner asks with
                target 0 (Gamer.ID), anybody else with his entity id, and
                then asks ss_get_di;target=<id> for each trophy. Either an
                ss_ack or a cmdAck ends that request (the first one takes
                the other off the queue), never both.
                ss_upd;s_status=1;obj=x<oid>|x0;param=<place> puts an entry
                on a place or empties it: a drag or a double click
                (TrophyInterface.onMouseUp/doubleClick) sends one or two of
                them -- the new place, then the old one emptied -- each
                waiting for its cmdAck; on 0 the client asks slot=32 again
                by itself. ss_upd;s_status=3 with nothing else buys a place
                after the client's own «Купить новое место под
                демонстрируемый трофей?»; on 0 it asks slot=32 again, on
                anything else it says «У вас недостаточно денег», its only
                word for it. The server's ss_upd 2 (obj=<count>) is heard
                (PUBLIC_SLOT_NUM) but drawn by nothing, and every open
                window listens to ss_upd, so it is not sent. userInfo_Player
                carries nothing of the show. How many places there were,
                what one cost and whether in afro or gold did not survive:
                neither the client, nor texts.xml, nor the wiki says.
  exchange      The game's own template ("Описание трофея", taken from the
                game): «Допустимость обмена: Да», «Допустимость продажи:
                Нет». The stall refuses a trophy by itself ("Вы не можете
                продать трофеи", TradeInterface.checkSellItem), and the
                auction has a «Трофеи» category. So a trophy is a thing like
                any other -- it can be picked up out of a bag, bartered,
                posted, put up at the auction, lost at death -- and it is
                never sold to a trader.

WHAT IS DESIGNED HERE

  * When it falls: a player killed by another player, the killer at the
    victim's level or below it (the owner's rule), always, one trophy, into
    the bag the death leaves (combat.Fighter.pvp_kill, after die() has put
    down what fell off the body). Not for a mob's kill, not for a stronger
    killer.
  * Which part: by the victim's level, four levels a step -- Ухо, Палец,
    Скальп, Череп, Кисть (BY_VICTIM_LEVEL). The original's rule did not
    survive. A newcomer's ear agrees with its quests ("Принеси мне ухо
    убитого противника", from the Nubian arena), and as the fee is the
    trophy's price, registering a strong victim costs what a strong
    fighter can pay.
  * Only the killer's own trophy is registered: one bought, found or
    picked up is refused, so that a rank cannot be bought.
  * The skill is paid at the registration, not at the kill:
    TROPHY_REP, one point a trophy whatever the levels (the owner's; it was
    progression.pvp_rep's 20 for a stronger victim and 10 for an equal).
    The same killer and victim pay it once an hour of registrations
    (PAY_REPEAT; the kill used to be counted in memory, combat.pvp_rep_due,
    and is in the database now, so a restart forgets nothing); a trophy
    registered inside the hour is still registered, its fee paid, and says
    why the skill did not rise. Deleting the entry from the collection
    does not give the hour back: the row stays, nobody's, with its paid_at
    (Store.delete_trophy).
  * Only where a registrar stands: the stall session outlives the
    location it was opened in, so the registrar must be in the room.
  * The collection keeps one entry per kind and victim: a second ear off
    the same player joins the first, «Количество» 2, «Последнее
    убийство» the newer one, and the entry is described again unasked.
  * Where: the butchers, and Демир in «Караван» inside the Nubian valley
    (world.TROPHY_REGISTRARS), where the owner moved it from Адам.
  * The show: every character has START_PLACES places and may buy one
    more at a time for PLACE_PRICE afro, from the purse in memory, up to
    MAX_PLACES -- the inspect window's own 12 cells, so a full show fits
    the page another player looks at. An entry stands on one place at
    most (putting it on another takes it off the first); only a registered
    entry of one's own collection is shown, and one deleted from it leaves
    the show with it. Anybody may ask anybody's show: it is what the
    inspect window is for. Nothing of it is said in chat: the client has
    its words for the one failure it expects (money), and a place refused
    is only a place its next ss_get;slot=32 draws as it really is.
"""
import logging
import time

import inventory
import items
import names
import progression
import rooms
import world
from protocol import BigUInt, Str

log = logging.getLogger("lava")

SKULL, SCALP, FINGER, EAR, HAND = 1492, 1493, 1494, 1495, 1496
# The part by the victim's level: (from this level on, type), highest first.
BY_VICTIM_LEVEL = ((16, HAND), (12, SKULL), (8, SCALP), (4, FINGER), (0, EAR))

# StuffManager.SESSION_TROPHY, and TrophyManager's ss_upd codes.
SESSION_TROPHY = 6
UPD_CLOSE, UPD_SET_PUBLIC, UPD_PUBLIC_COUNT, UPD_BY_PUBLIC, UPD_DELETE = 0, 1, 2, 3, 4
# TrophyManager.requestTrophy: CSM_SSGet(16, Gamer.ID); and
# PersEquip.requestPublicTrophy: CSM_SSGet(32, <whose>), the show.
MASK_COLLECTION = 16
MASK_PUBLIC = 32

# Seconds: one killer, one victim, one paid registration.
PAY_REPEAT = 3600
# «Навык бойца» a registered trophy pays: one point, whatever the levels
# (the owner, 2026-09-26: «навык бойца при сдаче трофея должен
# подниматься на 1, а не на 20»). progression.pvp_rep's 20 / 10 by the
# levels at the kill is no longer paid here.
TROPHY_REP = 1

# The show («демонстрируемые трофеи»), all DESIGNED -- the original's numbers
# did not survive (see the top). The owner's to change:
# places every character has without buying any (three is what the
# collection window's column holds before it scrolls: 253 px tall, a place
# every 85);
START_PLACES = 3
# the most a show can have: the inspect window's own grid, 3 by 4, so a
# full show fits the page other players look at;
MAX_PLACES = 12
# and what one more place costs, in afro (the client's question names no
# price; its only answer to a failed purchase is «У вас недостаточно денег»).
PLACE_PRICE = 500

REGISTRARS = world.TROPHY_REGISTRARS
# The registrars that keep their stall and their repairs beside the
# registration: Хассир (105) on the station of Вади-Хальфы, a trader first.
# The others sell and mend nothing (server.py send_npc_info).
KEEPS_STALL = frozenset({105})
WHERE = ("у Демира в Караване (Нубийская долина), у Мясников в Вади-Хальфе "
         "(Сумасшедшие живодеры) и у Хассира на вокзале Вади-Хальфы")


def is_registrar(type_id):
    return type_id in REGISTRARS


def keeps_stall(type_id):
    """Whether a registrar trades and mends besides (KEEPS_STALL)."""
    return type_id in KEEPS_STALL


def falls(killer_level, victim_level):
    """Whether a kill of a player leaves a trophy: «обязательно падает
    трофей, если убивший ниже лвл-ом или одинакового»."""
    return killer_level <= victim_level


def kind_for(victim_level):
    for since, type_id in BY_VICTIM_LEVEL:
        if victim_level >= since:
            return type_id
    return EAR


def name_of(type_id):
    """The name the client shows ("Ухо"), the class line after "$" cut."""
    return names.text(items.STRING_ID_OFFSET + type_id).split("$")[0].strip()


def fee_of(type_id):
    """What registering costs, in afro: the trophy's price, a 0 counted as
    1 -- exactly what RegTrophyInterface.regCostCount draws."""
    return (items.params_of(type_id) or {}).get("cost", 0) or 1


def when(t):
    """The time as Annotation.parseDate reads it: UTC, by position."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(t)))


def record(killer_id, killer_name, killer_lvl, victim_id, victim_name, victim_lvl,
           t=None, victim_clan=""):
    """What a trophy says of a kill (accounts.TROPHY_FIELDS but its type).
    victim_clan is the name of the victim's clan at the kill, "" for none
    (clan_of): «Клан жертвы» keeps the clan he died in, whatever becomes of
    it or of him later -- a trophy is a record, not a pointer."""
    return dict(killer_id=int(killer_id), killer_name=str(killer_name),
                killer_lvl=int(killer_lvl), victim_id=int(victim_id),
                victim_name=str(victim_name), victim_lvl=int(victim_lvl),
                victim_clan=str(victim_clan or ""),
                killed_at=int(time.time() if t is None else t), kills=1)


def clan_of(store, char_id):
    """The name of the clan a character is in right now, "" for none: what
    ss_di_trophy's v_clan says («Клан жертвы», Annotation.trophy; the
    collection window searches by it too, TrophyInterface.setTrophyList).
    Read from the database, as clans.py reads every membership -- the same
    as clans.Clans.name_of, which this module cannot reach: clans imports
    mail, mail imports inventory, and inventory imports this."""
    m = store.clan_member(char_id) if char_id else None
    return m["clan_name"] if m is not None else ""


# A trophy nothing has written a word about (one an admin handed out): its
# fields still arrive, empty, or the annotation reads "undefined".
BLANK = dict(k_id=0, k_lvl=0, v_id=0, v_lvl=0, time=Str(""), v_clan=Str(""),
             k_name=Str(""), v_name=Str(""))


def fields_of(rec):
    """The trophy keys of ss_di_trophy. Numbers first and the strings last,
    the names the very last: SCDataParser steps over a string by its
    decoded length, and a name is the one thing here a player chose.
    k_id and v_id are the players' entity ids, the client's handle on a
    player; nothing of its own reads them."""
    return dict(count=int(rec["kills"]),
                k_id=rooms.player_id(rec["killer_id"]), k_lvl=int(rec["killer_lvl"]),
                v_id=rooms.player_id(rec["victim_id"]), v_lvl=int(rec["victim_lvl"]),
                time=Str(when(rec["killed_at"])), v_clan=Str(rec["victim_clan"] or ""),
                k_name=Str(rec["killer_name"]), v_name=Str(rec["victim_name"]))


def di_fields(store, uniq):
    """What inventory.di_params adds for a trophy: its words, or BLANK."""
    rec = store.trophy(uniq)
    return fields_of(rec) if rec is not None else dict(BLANK)


def registered_row(store, uniq, type_id, root):
    """A registered trophy as a row push_di can describe, or None. It has no
    items row: it lives in its owner's collection under its old serial. One
    deleted from the collection (owner 0, Store.delete_trophy) is no more."""
    if root != items.TROPHY:
        return None
    rec = store.trophy(uniq)
    if rec is None or rec["registered_at"] is None or not rec["owner"] \
            or rec["type_id"] != type_id:
        return None
    return dict(uniq=uniq, type_id=type_id, root=root, count=rec["kills"], slot=0)


def places(bought):
    """How many places a show has: everybody's START_PLACES and the ones
    bought, never more than MAX_PLACES."""
    return max(0, min(START_PLACES + int(bought or 0), MAX_PLACES))


def show_of(store, char_id):
    """The o_list of ss_get;slot=32 about a character: one entry per place
    of his show, the trophy standing there or "0". Empty for nobody. An
    entry on a place past the count (START_PLACES moved down) waits there,
    unseen, for the count to come back."""
    row = store.character(char_id) if char_id else None
    if row is None:
        return []
    shown = store.shown_trophies(char_id)
    return [BigUInt(inventory.oid(shown[n]["uniq"], shown[n]["type_id"], items.TROPHY))
            if n in shown else inventory.EMPTY
            for n in range(places(row["trophy_places"]))]


def drop(killer, victim, owner, slot):
    """A player killed another (combat.Fighter.pvp_kill): the trophy, if the
    killer stood at the victim's level or below, into the bag the death
    left on the victim's cell -- the same bag, as combat.RoomCombat.
    add_to_bag adds to one already lying there. That cell is the victim's
    pos, as Fighter.drop_on_death has it: the end of a walk the blow cut
    short, where the client lets the corpse finish it -- not Fighter.cell,
    the hex the figure was crossing. Returns the items row, or None when
    nothing fell."""
    kc, vc = killer.sess.char_id, victim.sess.char_id
    rc = victim.rc
    if not kc or not vc or rc is None:
        return None
    k_lvl, v_lvl = killer.level, victim.level
    if not falls(k_lvl, v_lvl):
        log.info("  ..    %s (%d) kills %s (%d): a stronger killer takes no trophy",
                 killer.sess.nick, k_lvl, victim.sess.nick, v_lvl)
        return None
    type_id = kind_for(v_lvl)
    row = killer.store.create_trophy(
        owner, slot, type_id, items.TROPHY,
        record(kc, killer.sess.nick, k_lvl, vc, victim.sess.nick, v_lvl,
               victim_clan=clan_of(killer.store, vc)))
    cell = victim.sess.pos
    rc.add_to_bag(cell, [row])
    killer.sess.say("С %s снят трофей «%s» — он в мешке на месте гибели. "
                    "Зарегистрировать его можно %s: так растёт навык бойца."
                    % (victim.sess.nick, name_of(type_id), WHERE))
    log.info("  ..    %s (%d) kills %s (%d): trophy %d (%s) on cell %d",
             killer.sess.nick, k_lvl, victim.sess.nick, v_lvl, row["uniq"],
             name_of(type_id), cell)
    return row


class Collection:
    """One session's side of it: registering at a registrar (a trade
    session's ss_upd 6) and the collection window (s_type=6). Owned by
    server.Session as .trophies."""

    def __init__(self, sess, store):
        self.sess = sess
        self.store = store

    @property
    def char_id(self):
        return self.sess.char_id

    def ack(self, res):
        self.sess.send("cmdAck", res=res)

    def refuse(self, text):
        """A refusal the chat explains: RES_UNWORDED puts nothing up."""
        self.ack(inventory.RES_UNWORDED)
        self.sess.say(text)

    # --- the registration: ss_upd;s_status=6 in a trade session -------------
    def register(self, p):
        """Trade.regTrophy -> exactly one cmdAck; on 0 the trophy leaves the
        bag (ss_obj_status 0) and the purse and the skill arrive whole
        (userInfo_Player), the client announcing a rise by itself."""
        inv = self.sess.inv
        trade = inv.trade
        if trade is None or not is_registrar(trade.trader_type) or not self.char_id:
            self.ack(inventory.RES_REFUSED)
            return
        # The stall outlives the location it was opened in (leave_room ends
        # the bank, not the trade): the registrar has to be standing here.
        room = self.sess.room
        here = room.npc(trade.npc_id) if room is not None else None
        if here is None or here.type_id != trade.trader_type:
            self.refuse("Трофеи регистрируют только %s, а здесь их нет: "
                        "подойдите к ним и откройте окно снова." % WHERE)
            return
        row = inv.find(p.get("obj"))
        if row is None or row["root"] != items.TROPHY or row["slot"] != inventory.BAG:
            self.ack(inventory.RES_NOT_FOUND)
            return
        rec = self.store.trophy(row["uniq"])
        if rec is None or rec["registered_at"] is not None:
            self.refuse("На этом трофее не сказано, кто и кого убил: "
                        "зарегистрировать его нельзя.")
            return
        if rec["killer_id"] != self.char_id:
            self.refuse("Зарегистрировать можно только свой трофей, а этот снял "
                        "%s. Навык бойца растёт за свою добычу." % rec["killer_name"])
            return
        fee = fee_of(row["type_id"])
        ch = self.sess.character()
        if ch.afro < fee:
            # 21 as the bank and the barter send it; the window has no word
            # for it (RegTrophyInterface.regAck only unblocks the trophy, and
            # ErrorReport knows no 21), so the chat says it.
            self.ack(inventory.RES_NO_MONEY)
            self.sess.say("Не хватает денег: регистрация трофея «%s» стоит %d афро, "
                          "а у вас %d." % (name_of(row["type_id"]), fee, ch.afro))
            return
        now = int(time.time())
        gain = TROPHY_REP
        paid = gain > 0 and not self.store.trophy_paid_since(
            rec["killer_id"], rec["victim_id"], now - PAY_REPEAT)
        before = ch.rep
        rep = max(0, min(before + (gain if paid else 0), progression.REP_CAP))
        into = self.store.trophy_like(self.char_id, row["type_id"], rec["victim_id"])
        if not self.store.register_trophy(row, rec, self.char_id, now, paid,
                                          (self.char_id, ch.afro - fee, ch.gold),
                                          rep, into):
            # Neither the thing nor its words are as they were a moment ago,
            # and nothing was written.
            self.ack(inventory.RES_NOT_FOUND)
            return
        ch.afro -= fee
        ch.set_rep(rep)
        inv.forget_reload(row["uniq"])
        self.ack(inventory.RES_OK)
        inv.push_status(row, 0)
        if into is not None:
            # The entry that grew: the client made its item when the first
            # trophy was taken out of the bag or listed in the collection,
            # and ItemFactory.create never asks for a known one again, so
            # «Количество» and «Последнее убийство» are told unasked, as a
            # reload or a merged stack is (updateItemDI; for an id it does
            # not hold, that is a call on undefined, which AS2 skips).
            grown = registered_row(self.store, into["uniq"], into["type_id"], items.TROPHY)
            if grown is not None:
                inv.push_di(grown)
        self.sess.send_player_info()
        what = "%s — %s, ур. %d" % (name_of(row["type_id"]), rec["victim_name"],
                                    rec["victim_lvl"])
        if into is not None:
            what += " (в коллекции их теперь %d)" % (into["kills"] + rec["kills"])
        if paid and rep > before:
            self.sess.say("Трофей зарегистрирован: %s." % what)
        elif paid:
            self.sess.say("Трофей зарегистрирован: %s. Навык бойца уже на пределе."
                          % what)
        else:
            self.sess.say("Трофей зарегистрирован: %s. Навык бойца за одну и ту же "
                          "жертву растёт не чаще раза в час — в этот раз он не вырос."
                          % what)
        log.info("  ..    %s registers trophy %d (%s off %s) for %d afro: "
                 "fighter skill %d -> %d", self.sess.nick, row["uniq"],
                 name_of(row["type_id"]), rec["victim_name"], fee, before, rep)

    # --- the collection: s_type=6 ----------------------------------------------
    def open(self):
        return self.sess.npc_session == SESSION_TROPHY

    def owner_of(self, target):
        """Whose show an ss_get;slot=32 asks for: 0 is the asker himself
        (Gamer.ID), a player's entity id is that player -- online or not,
        the id is his character's for good (rooms.player_id) -- and
        anything else is nobody."""
        if not target:
            return self.char_id
        if rooms.is_player_id(target):
            return target - rooms.PLAYER_ID_BASE
        return None

    def ss_get(self, p):
        """ss_get;target=0;slot=16 in the collection window: the registered
        trophies, and nothing else -- TrophyManager.requestTrophyAck makes
        an item of every entry, so no divider. And ss_get;target=<whose>;
        slot=32, the show, in the collection window or out of it (the
        inspect window asks with no session): one ss_ack, never a cmdAck
        as well, empty for nobody. True when answered here."""
        slot = int(p.get("slot", 0) or 0)
        if slot == MASK_PUBLIC:
            owner = self.owner_of(int(p.get("target", 0) or 0))
            self.sess.send("ss_ack", o_list=show_of(self.store, owner))
            return True
        if not self.open():
            return False
        if slot != MASK_COLLECTION or int(p.get("target", 0) or 0) != 0:
            return False
        kept = self.store.trophies_of(self.char_id) if self.char_id else []
        self.sess.send("ss_ack", o_list=[
            BigUInt(inventory.oid(r["uniq"], r["type_id"], items.TROPHY)) for r in kept])
        return True

    def ss_upd(self, p):
        """TrophyManager's ss_upd. 0 closes and is sent bare (closeSession);
        1 puts an entry on show or takes it off, 3 buys a place, 4 deletes;
        each of those one cmdAck. True when this was the collection's."""
        if not self.open():
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == UPD_CLOSE:
            self.sess.npc_session = None
            return True
        if code == UPD_DELETE:
            parsed = inventory.parse_oid(p.get("obj"))
            done = False
            if parsed and parsed[2] == items.TROPHY and self.char_id:
                done = self.store.delete_trophy(parsed[0], self.char_id)
            self.ack(inventory.RES_OK if done else inventory.RES_NOT_FOUND)
            if done:
                log.info("  ..    %s deletes trophy %d from the collection",
                         self.sess.nick, parsed[0])
            return True
        if code == UPD_SET_PUBLIC:
            self.set_public(p)
            return True
        if code == UPD_BY_PUBLIC:
            self.buy_place()
            return True
        self.ack(inventory.RES_REFUSED)
        return True

    # --- the show: ss_upd 1 and 3, ss_get slot=32 -------------------------------
    def show_size(self):
        """(places in this character's show, of them bought)."""
        row = self.store.character(self.char_id) if self.char_id else None
        return (places(row["trophy_places"]), row["trophy_places"]) if row else (0, 0)

    def set_public(self, p):
        """ss_upd;s_status=1;obj=x<oid>;param=<place> puts an entry of the
        collection on that place, obj=x0 empties it (TrophyManager.
        setPublicTrophy). One cmdAck: 0; 12 («Объект не найден») for a
        trophy that is no registered entry of one's own; 31, which puts
        nothing up, for a place the show does not have. SET_PUBLIC_ERROR
        has no listener, so a refusal asks nothing again: the window keeps
        what it drew until its next ss_get;slot=32."""
        if not self.char_id:
            self.ack(inventory.RES_REFUSED)
            return
        try:
            place = int(p.get("param"))
        except (TypeError, ValueError):
            place = -1
        if not 0 <= place < self.show_size()[0]:
            self.ack(inventory.RES_UNWORDED)
            return
        raw = str(p.get("obj") or "0").strip().lower()
        try:
            empty = int(raw, 16) == 0
        except ValueError:
            empty = False
        if empty:
            self.store.show_trophy(self.char_id, place)
            self.ack(inventory.RES_OK)
            return
        parsed = inventory.parse_oid(raw)
        done = parsed is not None and registered_row(self.store, *parsed) is not None \
            and self.store.show_trophy(self.char_id, place, parsed[0])
        self.ack(inventory.RES_OK if done else inventory.RES_NOT_FOUND)
        if done:
            log.info("  ..    %s shows trophy %d on place %d", self.sess.nick,
                     parsed[0], place)

    def buy_place(self):
        """ss_upd;s_status=3 (TrophyManager.addSlot): one more place, for
        PLACE_PRICE afro out of the purse in memory (the Character, which
        Character.save writes back), the count and the purse written in one
        transaction. One cmdAck: 0 and the purse (userInfo_Player), the
        client asking for the longer show itself; 21 for too little money,
        31 for a show already MAX_PLACES long -- the client says «У вас
        недостаточно денег» to either, the only words it has."""
        if not self.char_id:
            self.ack(inventory.RES_REFUSED)
            return
        now, bought = self.show_size()
        if places(bought + 1) <= now:
            self.ack(inventory.RES_UNWORDED)
            return
        ch = self.sess.character()
        if ch.afro < PLACE_PRICE:
            self.ack(inventory.RES_NO_MONEY)
            return
        if self.store.buy_trophy_place(self.char_id, bought, ch.afro - PLACE_PRICE,
                                       ch.gold) is None:
            self.ack(inventory.RES_UNWORDED)
            return
        ch.afro -= PLACE_PRICE
        self.ack(inventory.RES_OK)
        self.sess.send_player_info()
        log.info("  ..    %s buys a place to show a trophy on for %d afro: %d places",
                 self.sess.nick, PLACE_PRICE, places(bought + 1))
