"""Thirty-day character statuses; quest fees are committed by quest_write."""
import time
import math
from datetime import datetime, timezone, timedelta

class StaleState(ValueError):
    """External status/purse change: reload before any later cache save."""


REGISTRATION = 1
PERMIT = 2
QUESTS = {2129: REGISTRATION, 2130: PERMIT}
DAYS = 30
SECONDS = DAYS * 86400
WEIGHT = {0: 0, REGISTRATION: 25000, PERMIT: 50000}
PRICES = {REGISTRATION: 1000, PERMIT: 3000}  # gold hundredths
NAMES = {0: "Нет действующего статуса", 1: "Прописка", 2: "ВНЖ"}


def allowed(character, target):
    return character.premium_level() < target


def rent_days(character, now=None, base=None):
    if not character.premium_level():
        return 0
    until = character.premium_until
    if until is None:
        return 365  # preserve legacy admin statuses without a deadline
    now = time.time() if now is None else now
    # Same-vehicle rentals extend their existing deadline. The TOTAL end is
    # bounded by the status, rounded up by strictly less than one day.
    remaining = until - max(now, base if base is not None else now)
    return max(0, int(math.ceil(remaining/86400))) if until > now else 0



def frame(character):
    level = character.premium_level()
    until = int(character.premium_until or 0) if level else 0
    label = NAMES[level]
    if level:
        deadline = datetime.fromtimestamp(until, timezone(timedelta(hours=4))) if until else None
        label += " — до " + (deadline.strftime("%d.%m.%Y %H:%M") + " (UTC+4)" if deadline else "отмены")
        label += ". +%d кг." % (WEIGHT[level]//1000)
    return dict(residence_level=level, residence_until=until,
                residence_bonus=WEIGHT[level], residence_days=rent_days(character),
                residence_text=label, residence_now=int(time.time()))


def refusal(character, quest_type, params):
    target = QUESTS.get(quest_type)
    if target is None:
        return None
    if not allowed(character, target):
        return "Этот статус уже действует. Повторное оформление доступно после его окончания."
    if target == PERMIT and character.premium_level() == REGISTRATION:
        try:
            confirmed = "residence_from" in params and int(params["residence_from"]) == int(character.premium_until or 0)
        except (TypeError, ValueError):
            confirmed = False
        if not confirmed:
            return "Подтвердите замену прописки: оставшиеся дни сгорят, ВНЖ выдаётся на 30 дней за 30 G."
    return None


def grant(store, character, quest_type, now=None):
    """Compare-and-set under the quest's character lock, before its fee save.

    The same transaction contains status, fee, history and instance removal.
    An external change of status/deadline/purse refuses the stale operation.
    """
    level = QUESTS[quest_type]
    if not allowed(character, level):
        raise ValueError("residence already active")
    until = int(time.time() if now is None else now) + SECONDS
    changed = store.db.execute(
        "UPDATE characters SET premium=?, premium_until=? WHERE id=? AND premium=?"
        " AND COALESCE(premium_until,0)=? AND gold=? AND afro=?",
        (level,until,character.char_id,character.premium,character.premium_until or 0,character.gold,character.afro))
    if changed.rowcount != 1:
        raise StaleState("residence or purse changed during quest")
    character.premium, character.premium_until = level, until
