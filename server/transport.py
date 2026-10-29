"""Rentable transport: the table, the ts_si frame, and the rental itself.

The client holds no transport data whatsoever -- `res/transport/` is 57 SWF
icons and `res/xml/transport.xml` a download manifest -- so every number here
travels over the socket. `data/transport.json` is where they come from, built
by `data/build_transport.py`, which also says which of them are recovered from
the wiki and which are designed.

Three frames make the feature:

  userInfo_Lessor;…;give_transport=|type…|  what this desk lets out
  ts_get_si;type=T;  ->  ts_si;type=T;…     the numbers behind one type
  on_conv;op=2;mob=N;p1=type;p2=days;       rent it, answered with cmdAck

and one field pair on userInfo_Player, `tr` and `tr_hours`, which is the only
way the client learns what the player is riding. It never asks: Gamer.userInfo
feeds `tr` straight to TransportFactory.create, so the frame has to be pushed
again after a rental.

TransportFactory asks for at most five `ts_si` at a time and only decrements
its counter when one arrives (TransportFactory.updateCall), so every
`ts_get_si` must be answered -- including for a type this table does not know,
or the lessor's window stops loading halfway.
"""
import io
import json
import os
import time

# Numeric string ids, the only form a name travels in. The item catalogue
# owns 1 000 000 (names) and 3 000 000 (descriptions), quests 2 000 000 and
# the empty string 5 000 000, so transport takes 6 000 000. Both offsets are
# added to names.ALL; a name id the preload has not seen costs the player a
# trip back to the login screen (PROTOCOL.md 9).
NAME_ID_OFFSET = 6_000_000
DESC_ID_OFFSET = 6_100_000

# One placeholder for a type that is not in the table, so an unknown
# ts_get_si can still be answered with a complete frame.
UNKNOWN_NAME_ID = NAME_ID_OFFSET
UNKNOWN_NAME = "Транспорт"

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_HERE, "data", "transport.json")

# Deliberately no try/except, for the same reason quests.strings() has none:
# a table that failed to load would leave every transport string id off the
# HTTP preload while the game server still sent them, and the first lessor
# window would throw the player back to the login screen. Better to fail at
# start, in both processes.
with io.open(_PATH, encoding="utf-8") as _fh:
    _DATA = json.load(_fh)

MAX_DAYS = int(_DATA["max_days"])
ICONS = {int(i) for i in _DATA["icons"]}
TABLE = {int(k): v for k, v in _DATA["types"].items()}


def _lay_original():
    """The original's name and description of each vehicle, over ours.

    A description the original has and we did not is simply added: si_frame
    sends a description id only when there is a description to send, so the
    frame follows the table without being told.
    """
    import orig_texts
    for ttype, (name, desc) in orig_texts.transport().items():
        rec = TABLE.get(ttype)
        if rec is None:
            continue
        if name:
            rec["name"] = name
        if desc:
            rec["desc"] = desc


_lay_original()

# Preserve the original vehicle table and text archive; these are alternative
# rental offers, with the same physical vehicle, speed and verified image.
STATUS_RENTALS = {int(k): v for k, v in _DATA["status_rentals"].items()}
for _offer, _option in STATUS_RENTALS.items():
    _base = TABLE[int(_option["base_type"])]
    _status = int(_option["required_status"])
    _label = "по прописке" if _status == 1 else "по ВНЖ"
    _requirement = "действующая прописка или ВНЖ" if _status == 1 else "действующий ВНЖ"
    if _offer in TABLE:
        raise ValueError("status rental offer overwrites a vehicle type")
    TABLE[_offer] = dict(_base, type=_offer, base_type=int(_option["base_type"]),
                         name=_base["name"] + " (" + _label + ")",
                         desc=(_base.get("desc") or "") + "<br>Аренда за афро; требуется "
                              + _requirement + ". Срок ограничен сроком статуса;"
                              " допускается выход за него менее чем на сутки.",
                         premium=0, required_status=_status,
                         cost=int(_option["cost"]), g_cost=0)
for _type in (4, 5):
    TABLE[_type]["desc"] = (TABLE[_type].get("desc") or "") + (
        "<br>Аренда за голд. Прописка и ВНЖ не требуются.")

LESSORS = {int(k): [int(t) for t in v] for k, v in _DATA["lessors"].items()}
DEFAULT_SET = [int(t) for t in _DATA["default_lessor"]]


def get(type_id):
    """One vehicle's record, or None."""
    return TABLE.get(int(type_id))


def premium(type_id):
    """Whether this vehicle is the dead server's premium: «Газ 67 Б (P)» (8)
    and «Летающая тарелка» (12).

    No lessor lets either out (LESSORS, DEFAULT_SET), and since the owner's
    cut of (P) (2026-09-30) no admin hands one over either -- the panel does
    not offer them and Session.admin_transport, with the panel's offline path
    (server.apply_admin_action), refuses them, as it refuses a (P) thing.
    The rows stay: their names are string ids the client may still be shown.
    """
    rec = get(type_id)
    return bool(rec and int(rec.get("premium") or 0))


def offered_by(npc_type_id):
    """What a lessor of this creature type lets out.

    The wiki resolved three desks by name (data/npc_wiki.json); every other
    lessor keeps the stock yard, which is the set mobs.xml itself gives each
    clan base: donkey, camel, motorcycle, UAZ, Hummer, buggy, airship.
    """
    out = []
    for vehicle in LESSORS.get(int(npc_type_id), DEFAULT_SET):
        out.append(vehicle)
        out.extend(offer for offer, option in STATUS_RENTALS.items()
                   if int(option["base_type"]) == vehicle)
    return out


def strings():
    """Every transport string id and its text, for names.ALL."""
    out = {UNKNOWN_NAME_ID: UNKNOWN_NAME}
    for type_id, rec in TABLE.items():
        out[NAME_ID_OFFSET + type_id] = rec["name"]
        if rec.get("desc"):
            out[DESC_ID_OFFSET + type_id] = rec["desc"]
    return out


def si_frame(type_id):
    """The ts_si parameters, exactly the keys TransObject reads.

    TransObject.initialize takes speed_mod, aggro_mod, g_cost, cost, res and
    premium; initGSDLStringData takes name and desc as string ids, with an
    empty desc meaning "no description" (descStrID stays null). `type` is
    what TransportFactory.initializeItem looks the pending object up by, and
    `res` is the icon: ItemContainer builds transport/<res>.swf from it, not
    from the type. Vehicle IDs are persistent; the art has its own numbering.
    """
    type_id = int(type_id)
    rec = get(type_id)
    if rec is None:
        return dict(type=type_id, speed_mod=1.0, aggro_mod=1.0, g_cost=0,
                    cost=0, res=type_id, premium=0, name=UNKNOWN_NAME_ID,
                    desc="")
    return dict(
        type=type_id,
        speed_mod=float(rec["speed_mod"]),
        aggro_mod=float(rec["aggro_mod"]),
        g_cost=int(rec["g_cost"]),
        cost=int(rec["cost"]),
        res=int(rec["res"]),
        premium=max(int(rec["premium"]), int(rec.get("required_status",0))),
        name=NAME_ID_OFFSET + type_id,
        desc=DESC_ID_OFFSET + type_id if rec.get("desc") else "")


def price(type_id, days):
    """(afro, gold) for renting this type for that many days, or None.

    The client prices it as `g_cost * days / 100` gold when g_cost is set and
    `cost * days` afro otherwise (TransRentInterface.printTxt), and the
    server must ask for exactly what the player was shown. Gold travels in
    hundredths throughout, so g_cost is already in the character's own unit.
    """
    rec = get(type_id)
    if rec is None:
        return None
    days = int(days)
    if rec["g_cost"]:
        return (0, rec["g_cost"] * days)
    return (rec["cost"] * days, 0)


def speed_mod(type_id):
    """The multiplier on map travel speed; 1.0 for walking."""
    rec = get(type_id)
    return float(rec["speed_mod"]) if rec else 1.0


def valid_days(days):
    """Whether a rental length is one the client could have sent.

    The window's slider runs 1..365 (TransRentInterface.maxValue) and clamps
    typed input to it, so anything else is not this client.
    """
    return 1 <= int(days) <= MAX_DAYS


def hours_left(until, now=None):
    """Whole hours remaining on a rental, rounded up, or 0 once it is over.

    Rounded up because the client prints the number as the time the player
    still has ("ОСТАВШЕЕСЯ ВРЕМЯ: N Ч."), and a rental with fifty minutes to
    run has not expired.
    """
    if not until:
        return 0
    left = float(until) - (time.time() if now is None else now)
    if left <= 0:
        return 0
    return int(left // 3600) + (1 if left % 3600 else 0)


def vehicle_type(type_id):
    """Physical vehicle of an offer; payment currency does not replace a ride."""
    rec = get(type_id) if type_id is not None else None
    return int(rec.get("base_type", type_id)) if rec else type_id


def until_after(days, now=None, *, current=None, type_id=None):
    """Same vehicle extends the paid deadline; another replaces it from now."""
    base = time.time() if now is None else now
    if current and vehicle_type(current[0]) == vehicle_type(type_id) and current[1] > base:
        base = current[1]
    return int(base + int(days)*86400)
