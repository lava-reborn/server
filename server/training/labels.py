"""Range display fallbacks derived from named equivalents, not file stems."""
from functools import lru_cache
import re


def named(type_id):
    import items
    import names
    text = names.text(items.STRING_ID_OFFSET + type_id).partition('$')[0]
    raw = items.catalogue()[type_id][1]
    return text if text and raw.casefold() != text.casefold() else None


def version(text, line):
    # Keep the piece's existing name/level, replace only its variant marker.
    text = re.sub(r'\s*(?:\([APG]\)|\[[APG]\])\s*$', '', text)
    return text + ' (' + line + ')'


@lru_cache(maxsize=1)
def raw_index():
    import items
    return {raw: source for source, (_root, raw) in items.catalogue().items()}


@lru_cache(maxsize=None)
def title(source):
    import items
    from training import balance as training_balance
    text = named(source)
    if text:
        return text
    reference = training_balance.afro_of(source)
    if reference is not None and reference != source:
        text = named(reference)
        if text:
            return version(text, training_balance.line(source))
    raw = items.catalogue()[source][1]
    base = raw_index().get(raw.replace('_mod_damage_clipsize', ''))
    if base is not None and base != source:
        text = named(base)
        if text:
            return version(text, training_balance.line(source)) + ' · Урон и размер обоймы'
    # Retain unknown names for diagnosis rather than invent a model identity.
    import names
    return names.text(items.STRING_ID_OFFSET + source).partition('$')[0]
