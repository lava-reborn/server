"""Persistent admission to the administrative Eden plantation.

The row, rather than the current map position, is the sentence. Session code
loads it on character selection and updates its cached copy after an admin
action or a successful release quest; movement/combat ticks need no queries.
The admin queue is the audit trail and the only admission authority. Ordinary
gameplay reaches only the local work, admission and release helpers.
"""
import math
import time
import copy

import storage
import eden_map


CENTER = 267
CELLS = eden_map.LOC_TO_CELL
LOCATIONS = frozenset(CELLS)
GREEN_TICKET, GOOD_TICKET, BAD_TICKET, EXIT_PASS = 4231, 4232, 4233, 4234
GOOD_BANANA, GREEN_BANANA, BAD_BANANA = 4235, 4236, 4237
PALM_LEAF, BASKET = 4305, 4304
CLEAVER = 60010
LOCAL_ITEMS = frozenset((GREEN_TICKET, GOOD_TICKET, BAD_TICKET, EXIT_PASS,
                         GOOD_BANANA, GREEN_BANANA, BAD_BANANA, PALM_LEAF,
                         BASKET, CLEAVER))
TICKET_QUOTA = {GREEN_TICKET: 100, GOOD_TICKET: 1000, BAD_TICKET: 75}
GIFT = 18128
QUESTS = frozenset(range(18111, 18118)) | {18119, 18127, GIFT} | frozenset(range(18120, 18126))
# The retired instant-gather quest can remain in a legacy journal as well.
LOCAL_QUESTS = QUESTS | {18110}
EXIT_QUESTS = frozenset((18115, 18117, 18119))
GOLD_EXIT, AFRO_EXIT = 18117, 18119
PALMS = frozenset((1790, 1798, 1799, 1800))


def inside(loc_or_id):
    """Whether a Location (or its integer id) belongs to the plantation."""
    loc_id = getattr(loc_or_id, "id", loc_or_id)
    return isinstance(loc_id, int) and loc_id in LOCATIONS


def target_cell(loc_or_id):
    """The plantation room's historical global coordinates, or None."""
    return CELLS.get(getattr(loc_or_id, "id", loc_or_id))


def confined(sess):
    """The sentence and its entire island, including global-map travel."""
    return (bool(getattr(sess, "eden_sentence", None))
            or inside(getattr(sess, "loc", None))
            or eden_map.inside_cell(getattr(sess, "gx", None),
                                    getattr(sess, "gy", None)))


def restricted_item(type_id):
    return type_id in LOCAL_ITEMS


def assigned(store, char_id):
    row = store.db.execute("SELECT * FROM char_eden WHERE char_id = ?",
                           (int(char_id),)).fetchone()
    return dict(row) if row is not None else None


def _words(value, field, limit):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s is required" % field)
    value = value.strip()
    if len(value) > limit:
        raise ValueError("%s is too long (maximum %d)" % (field, limit))
    return value


def _return_place(state):
    out = {}
    for key in ("loc", "pos"):
        value = state.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("return %s must be an integer" % key)
            if value < 0 or (key == "loc" and value == 0):
                raise ValueError("invalid return %s" % key)
        out[key] = value
    for key in ("gx", "gy"):
        value = state.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value):
                raise ValueError("return %s must be a finite coordinate" % key)
        out[key] = value
    on_map = state.get("on_map", 0)
    if on_map not in (0, 1, False, True):
        raise ValueError("invalid return on_map")
    out["on_map"] = int(on_map)
    return out


def assign(store, char_id, admin, reason, return_state=None):
    """Create one sentence, leaving any surrounding transaction in control.

    The character lock serializes assignment with release on Postgres; SQLite
    reserves its writer at the outer atomic boundary. Repeated assignment is
    refused, preserving the original reason and return position. The caller
    must first close an online training clone successfully, then move the
    ordinary character after this transaction commits.
    """
    char_id = int(char_id)
    admin = _words(admin, "admin", 100)
    reason = _words(reason, "reason", 1000)
    with storage.atomic(store.db):
        if not store.lock_quest_character(char_id):
            raise ValueError("character does not exist")
        if assigned(store, char_id) is not None:
            raise ValueError("character is already assigned to Eden")
        state = store.character(char_id) if return_state is None else return_state
        if not hasattr(state, "get"):
            state = dict(state)
        place = _return_place(state)
        previous = store.db.execute(
            "SELECT visits FROM char_eden_visits WHERE char_id = ?", (char_id,)
        ).fetchone()
        visit = int(previous["visits"]) + 1 if previous is not None else 1
        if previous is None:
            store.db.execute("INSERT INTO char_eden_visits (char_id, visits) VALUES (?, ?)",
                             (char_id, visit))
        else:
            store.db.execute("UPDATE char_eden_visits SET visits = ? WHERE char_id = ?",
                             (visit, char_id))
        store.db.execute(
            "INSERT INTO char_eden (char_id, admin, reason, assigned_at, visit,"
            " return_loc, return_pos, return_gx, return_gy, return_on_map)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (char_id, admin, reason, int(time.time()), visit, place["loc"], place["pos"],
             place["gx"], place["gy"], place["on_map"]))
        # Keep every personal training setting, but never let an old dormant
        # checkpoint reopen a training clone while the character is sentenced.
        profile = store.training_profile(char_id)
        if profile is not None and profile.get("inside") is True:
            profile["inside"] = False
            store.save_training_profile(char_id, profile)
        return assigned(store, char_id)


def release(store, char_id):
    """Remove the active sentence and return its old row, or None.

    Inventory cleanup and the actual departure belong to the caller's same
    transaction. The lifetime visit count stays after either administrative
    or earned release. A second request cannot create a second departure reward.
    """
    char_id = int(char_id)
    with storage.atomic(store.db):
        if not store.lock_quest_character(char_id):
            return None
        row = assigned(store, char_id)
        if row is not None:
            store.db.execute("DELETE FROM char_eden WHERE char_id = ?", (char_id,))
        return row


def entry(store, char_id):
    """The safe arrival (location, cell, gx, gy) for a sentenced character."""
    if assigned(store, char_id) is None:
        return None
    import world                       # Resources are needed only for an arrival.
    loc = world.location(CENTER)
    candidates = sorted(set(loc.entries) - set(loc.obstacles))
    if not candidates:
        raise ValueError("Eden has no walkable entrance")
    return (CENTER, candidates[0]) + CELLS[CENTER]


def paid_exit_available(sentence):
    """Only the first two lifetime assignments permit a paid release."""
    visit = sentence.get("visit") if sentence else None
    return type(visit) is int and visit in (1, 2)


def price(sentence):
    """Afro and hundredths of G, only while paid release is available."""
    if not paid_exit_available(sentence):
        raise ValueError("paid Eden exit is unavailable for this visit")
    return 5_000_000 * sentence["visit"], 5_000 * sentence["visit"]


def priced(quest, sentence):
    # Never change the process-wide quest shared by other characters.
    if (quest is None or quest.type not in (GOLD_EXIT, AFRO_EXIT)
            or not paid_exit_available(sentence)):
        return quest
    quest = copy.copy(quest)
    afro, gold = price(sentence)
    quest.cost_afro = afro if quest.type == AFRO_EXIT else 0
    quest.cost_gold = gold if quest.type == GOLD_EXIT else 0
    return quest


def allowed(sess, quest, *, sentence=None):
    """Display uses the session cache; a hand-in supplies its locked live row."""
    if quest is None or quest.type == 18110:
        return False
    if quest.type not in QUESTS:
        return True
    if sentence is None:
        sentence = getattr(sess, 'eden_sentence', None)
    return (bool(sentence) and inside(sess.loc) and not getattr(sess, "on_map", False)
            and (quest.type != GIFT or sentence['visit'] == 1)
            and (quest.type not in (GOLD_EXIT, AFRO_EXIT) or paid_exit_available(sentence)))


def restore_state(store, char_id, state, home):
    """An active sentence wins over a saved map/home/training position."""
    state = dict(state)
    sentence = assigned(store, char_id)
    if sentence:
        if state.get("on_map") and eden_map.inside_cell(state.get("gx"), state.get("gy")):
            gx, gy = math.floor(state['gx']), math.floor(state['gy'])
            state.update(loc=eden_map.location_at(gx, gy), pos=None, gx=gx, gy=gy)
        elif not inside(state.get("loc")):
            loc, pos, gx, gy = entry(store, char_id)
            state.update(loc=loc, pos=pos, gx=gx, gy=gy)
        else:
            # A local scene always saves its own canonical world cell.
            state["gx"], state["gy"] = target_cell(state["loc"])
            if state.get("on_map"):
                state["pos"] = None
        state["on_map"] = 0
    elif (inside(state.get("loc"))
          or eden_map.inside_cell(state.get("gx"), state.get("gy"))):
        loc, gx, gy = home
        state.update(loc=loc, pos=None, gx=gx, gy=gy, on_map=0)
    return sentence, state


def enforce(sess, store, home):
    """Last admission gate, also covering party moves and resurrection.

    The cached sentence is loaded at selection and updated by the queue;
    ordinary movement and combat never poll the database.
    """
    sentence = getattr(sess, "eden_sentence", None)
    if sentence and inside(sess.loc):
        # Every local scene has its own island cell. Retain the arrival cell
        # chosen by an internal quest or a legitimate edge transition.
        gx, gy = target_cell(sess.loc)
        if (sess.gx, sess.gy, sess.on_map) != (gx, gy, False):
            sess.gx, sess.gy, sess.on_map = gx, gy, False
            sess._accepted_place = None
        return
    if sentence and not inside(sess.loc):
        loc, pos, gx, gy = entry(store, sess.char_id)
    elif not sentence and (inside(sess.loc) or eden_map.inside_cell(sess.gx, sess.gy)):
        loc, gx, gy = home
        import world
        pos = world.location(loc).entry_cell()
    else:
        return
    import world
    sess.loc, sess.pos = world.location(loc), pos
    sess.gx, sess.gy, sess.on_map = gx, gy, False
    sess._accepted_place = None
    sess.cancel_travel()


def cleanup(sess, store):
    """Reclaim local property and active local quests in the caller's tx."""
    import eden_ground
    eden_ground.withdraw_owned_ground(store, sess.char_id)
    # A legacy/stale barter lock must not turn mandatory reclamation into
    # an escape route. Ordinary belongings retain their locks throughout;
    # restore the cache even when the surrounding transaction rolls back.
    local_locks = {r['uniq'] for r in store.items_of(sess.char_id)
                   if r['type_id'] in LOCAL_ITEMS} & sess.inv.locked
    sess.inv.locked.difference_update(local_locks)
    try:
        for type_id in LOCAL_ITEMS:
            sess.inv.reclaim_pieces(type_id, 1 << 30)
    finally:
        sess.inv.locked.update(local_locks)
    for row in store.quests(sess.char_id):
        if row["type"] in LOCAL_QUESTS:
            store.drop_quest(row["q_id"], sess.char_id)


def complete_release(sess, store, home):
    """Release and save a real-world destination with the paid hand-in."""
    if release(store, sess.char_id) is None:
        raise ValueError("character is not assigned to Eden")
    cleanup(sess, store)
    loc, gx, gy = home
    store.save_position(sess.char_id, loc, None, gx, gy, False)


def departure(sess, store):
    """Called only after commit: reconnect also reads this saved destination."""
    import eden_ground
    import server
    sess.eden_sentence = None
    sess._accepted_place = None
    try:
        eden_ground.refresh_rooms(server.ROOMS)
        if getattr(sess, "on_map", False):
            # Administrative release can arrive while a global leg is running.
            # Its callback must not move the freed body back onto the island.
            sess.cancel_travel()
            server.GMAP.leave(sess)
        sess.inv.refresh_gear()
        sess.restore(store.character(sess.char_id))
        # SQL cleanup has committed. Native QuestInspector otherwise keeps
        # these tasks indefinitely; q_list does not replace currentQuests.
        sess.send('eden_inv', refresh=1, clear_eden=1, q_types=sorted(LOCAL_QUESTS))
        sess.enter_location()
    except Exception:
        # Release and reclamation are already durable. A failed refresh must
        # not leave a playable old body or overwrite its saved destination.
        sess._failed_location_entry = True
        sess.close(force=True)
        raise


def price_text(sentence):
    if not paid_exit_available(sentence):
        return ("Попадание в Эдем №%d. Платный выход недоступен. "
                "Для освобождения выполните норму у Рона Деккера "
                "и передайте пропуск Люку Хэйзену.") % sentence["visit"]
    afro, gold = price(sentence)
    return "Попадание в Эдем №%d. Платный выход: %s афро или %d G." % (
        sentence["visit"], format(afro, ",").replace(",", " "), gold // 100)


def admin_apply(store, row, sess, home):
    """Apply the authenticated admin queue, never a player command."""
    import json
    import world
    args = json.loads(row["args_json"] or "{}")
    reason = _words(args.get("reason"), "reason", 1000)
    cid = row["char_id"]
    state = store.character(cid)
    if state is None:
        return "персонажа нет"
    if row["kind"] == "eden":
        # The owner must resume the real character before changing anything.
        ground = getattr(sess, "training_ground", None) if sess else None
        if ground is not None:
            ground.exit(notify=False, suspend=False)
            if getattr(sess, "training_ground", None) is not None:
                raise ValueError("сначала завершите выход с полигона")
            sess.send("tg", op="exit", active=0)
        # Validate resources before committing a sentence or its counter.
        loc = world.location(CENTER)
        if not set(loc.entries) - set(loc.obstacles):
            raise ValueError("Eden has no walkable entrance")
        if sess is not None:
            state = dict(store.character(cid))
            state.update(loc=sess.loc.id, pos=sess.live_cell(),
                         gx=sess.gx, gy=sess.gy, on_map=int(sess.on_map))
        with storage.atomic(store.db):
            sentence = assign(store, cid, row["admin"], reason, state)
            grant_tools(store, cid)
            destination = entry(store, cid)
            store.save_position(cid, *destination, False)
        if sess is not None:
            try:
                if sess.on_map:
                    # Cancel the ordinary-world leg before setting the Eden
                    # cache: it must not be interpreted as an island leg or
                    # publish a later global arrival into the local scene.
                    sess.cancel_travel()
                    import server
                    server.GMAP.leave(sess)
                sess.eden_sentence = sentence
                sess._accepted_place = None
                # The old merchant must not remain usable from the island.
                # Clear only after COMMIT: a failed assignment still leaves
                # the character and its ordinary shop session where they were.
                sess.inv.trade = None
                sess.inv.refresh_gear()
                sess.restore(store.character(cid))
                sess.send('eden_inv', refresh=1)
                sess.enter_location()
                sess.answer("Назначена плантация Эдем. Причина: " + reason)
                sess.answer(price_text(sentence))
            except Exception:
                # The sentence is already durable; a failed client refresh
                # must not leave its old, ordinary-world body playable.
                sess.eden_sentence = sentence
                sess._failed_location_entry = True
                sess.close(force=True)
                raise
        return "Эдем: назначение №%d; %s" % (sentence["visit"], reason)
    if row["kind"] != "eden_release":
        raise ValueError("unknown Eden admin action")
    if sess is not None:
        try:
            with storage.atomic(store.db):
                if assigned(store, cid) is None:
                    return "персонаж не находится на плантации"
                complete_release(sess, store, home)
        except storage.CommitError:
            # The queue's caller rereads durable state before closing.
            raise
        except Exception:
            # Cleanup may already have published an inventory removal. Its
            # SQL rollback is final before this close; reconnect reloads it.
            sess._failed_location_entry = True
            sess.close(force=True)
            raise
        departure(sess, store)
        sess.answer("Вы освобождены с плантации Эдем администратором.")
    else:
        with storage.atomic(store.db):
            if release(store, cid) is None:
                return "персонаж не находится на плантации"
            import eden_ground
            eden_ground.withdraw_owned_ground(store, cid)
            # No session owns these rows. Only Eden property is reclaimed.
            for type_id in LOCAL_ITEMS:
                store.db.execute("DELETE FROM items WHERE char_id=? AND type_id=?", (cid, type_id))
            for quest in store.quests(cid):
                if quest["type"] in LOCAL_QUESTS:
                    store.drop_quest(quest["q_id"], cid)
            loc, gx, gy = home
            store.save_position(cid, loc, None, gx, gy, False)
        import server
        eden_ground.refresh_rooms(server.ROOMS)
    return "Эдем: освобождён; " + reason


def grant_tools(store, char_id):
    """Give only the cleaver; the work basket must be crafted from leaves."""
    import inventory
    for row in store.items_of(char_id):
        if row["slot"] == inventory.PRIMARY:
            store.update_item(row["uniq"], slot=inventory.BAG)
    fields = inventory.new_fields(CLEAVER)
    root = fields.pop("root")
    fields["slot"] = inventory.PRIMARY
    store.create_item(char_id, CLEAVER, root, **fields)
