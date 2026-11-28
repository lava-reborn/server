"""Server-priced INTUX consent before an ordinary item action starts.

Quotes belong to this session, this dose and this location/action state.
Nothing is charged by a quote. The completion check also covers a weekend
boundary or a changed residence status during the item's use timer.
"""
import math
import secrets
import time

import effects
import item_templates
import progression

QUOTE_SECONDS = 60


def projection(fighter, type_id):
    """Positive XP totals after replacing, rather than stacking, INTUX."""
    source = item_templates.source_type(type_id)
    incoming = effects.definition(source)
    manager = fighter.sess.effects
    clock = manager.clock()
    active = tuple(sorted((family, row.source, row.deadline)
                          for family, row in manager.active.items() if row.deadline > clock))
    residence = progression.PREMIUM_XP_BONUS[fighter.character().premium_level()]
    calendar = progression.combat_calendar_multiplier()
    totals = []
    for name, extra in (('mob_exp', calendar - 1), ('pl_exp', 0)):
        values = [effects.definitions()[row[1]].get('modifiers', {}).get(name, 1)
                  for row in active if row[0] != incoming['family']]
        values.append(incoming.get('modifiers', {}).get(name, 1))
        boost = min(effects.MAX_EXPERIENCE_MULTIPLIER,
                    math.prod(value for value in values if value > 1))
        totals.append(boost + residence + extra)
    return tuple(totals), (source, residence, calendar, active)


def _context(fighter, row, state):
    return (fighter.sess.char_id, row['uniq'], row['type_id'], row['use_count'],
            row.get('count', 1), row.get('slot'), id(fighter.sess.room),
            getattr(fighter, 'action_revision', 0), fighter.cell, state)


def guard(fighter, row, params):
    """False means this call was quoted/refused and has already been acked."""
    if row['type_id'] not in effects.EXPERIENCE_UP:
        return True
    import inventory
    session = fighter.sess
    if (row['char_id'] != session.char_id or row.get('use_count', 0) <= 0
            or row.get('count', 1) <= 0 or row.get('slot') not in (inventory.BAG, *inventory.HAND_SLOTS)
            or row['uniq'] in session.inv.locked):
        fighter.ack(inventory.RES_REFUSED)
        return False
    try:
        session.effects.check(row['type_id'])
    except ValueError as reason:
        fighter.ack(inventory.RES_REFUSED)
        session.answer(str(reason))
        return False
    totals, state = projection(fighter, row['type_id'])
    ceiling = effects.MAX_TOTAL_EXPERIENCE_MULTIPLIER
    exceeds = max(totals) > ceiling + 1e-9
    context = _context(fighter, row, state)
    if params.get('xp_stage') == 'quote':
        token = secrets.token_urlsafe(24)
        session._intux_quote = (token, time.monotonic() + QUOTE_SECONDS, context)
        message = ("После применения INTUX сумма положительных бонусов к опыту составит +%g%%. "
                   "Максимально возможный суммарный бонус = +100%% (x2). "
                   "Часть бонуса не будет начисляться. Всё равно использовать INTUX?"
                   % round((max(totals) - 1) * 100, 6)) if exceeds else ''
        session.send('cmdAck', res=inventory.RES_OK, xp_warning=int(exceeds),
                     xp_token=token, xp_message=message)
        return False
    quote = getattr(session, '_intux_quote', None)
    session._intux_quote = None  # one use, including a rejected replay
    supplied = params.get('xp_token')
    valid = (quote is not None and isinstance(supplied, str)
             and secrets.compare_digest(quote[0], supplied)
             and quote[1] >= time.monotonic() and quote[2] == context)
    if (exceeds and not valid) or (supplied is not None and not valid):
        fighter.ack(inventory.RES_REFUSED)
        session.answer('Подтверждение INTUX устарело или отсутствует. Повторите применение: предмет не израсходован.')
        return False
    session._intux_consent = (row['uniq'], row['type_id'], max(totals),
                              time.monotonic() + QUOTE_SECONDS)
    return True


def finish_allowed(fighter, row):
    if row['type_id'] not in effects.EXPERIENCE_UP:
        return True
    consent = getattr(fighter.sess, '_intux_consent', None)
    fighter.sess._intux_consent = None
    totals, _state = projection(fighter, row['type_id'])
    if max(totals) <= effects.MAX_TOTAL_EXPERIENCE_MULTIPLIER + 1e-9:
        return True
    if (consent is not None and consent[:2] == (row['uniq'], row['type_id'])
            and consent[3] >= time.monotonic() and max(totals) <= consent[2] + 1e-9):
        return True
    fighter.sess.send('actionCancel', release=1)
    fighter.sess.answer('Бонусы опыта изменились. Подтвердите применение INTUX заново: предмет не израсходован.')
    return False
