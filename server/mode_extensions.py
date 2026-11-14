"""Atomic startup metadata for optional game modes; no feature imports.

Ordinary commerce, craft, loot, quests and transfers must refuse private types
through items.acquisition_blocked. Generic rendering, inventory requirements,
combat and wear accept templates through their registered source/static data.
Ordinary catalogue scans (shop ladders, recipe generation and release tables)
remain ordinary-only: private inventories supply their own authorised sources.
Read helpers must not infer an extension by an id range or a variant letter.

Template-aware entry points: items.root_of/static_info/params_of,
items.battle_medicine/no_combat/stimulant_unavailable, inventory requirement
and durability checks, and sets.record_of/item/frame/bonuses/string helpers.
craft recipe/name lookup, gold_trade, auction valuation, repair_policy price
ladders and combat.gold_item/death_losses are ordinary-only. A private mode
must own or reject those operations; source_type is not permission to trade,
repair, craft, drop or redeem a private copy against its real-world source.

All registrations finish before names.document or the first cached wear lookup.
The owning mode is responsible for authorising private inventory operations and
implementing every effect capability it declares. Never import that mode here.
"""
import item_templates
import sets


def seal():
    import names
    item_templates.seal()
    sets.seal()
    names.seal()


def register(*, frames=None, sources=None, set_document=None, strings=None,
             catalogue, commands, variants=sets.VARIANTS, effects=(), freeze=True):
    """Validate templates, set membership and preload strings before publishing.

    A set may link members of this same template batch, but cannot steal an
    ordinary type, an existing template or another set's member. No database
    access, callbacks or awaits occur between successful validation/publication.
    freeze=False is for several explicitly ordered startup batches only.
    """
    import names
    templates = item_templates.validate(frames or {}, sources or {},
        catalogue=catalogue, commands=commands, effects=effects)
    registered = sets.validate(set_document or {'sets': {}}, variants=variants,
                               template_members=templates[0])
    for type_id in registered[1]:
        if type_id in catalogue:
            raise ValueError('Additional set piece overlaps an ordinary item')
        if type_id in templates[0]:
            root = catalogue[templates[1][type_id]][0]
            if commands[root] != 'ss_si_wear':
                raise ValueError('Set member template must be wearable')
    text = dict(strings or {})
    for key, value in sets.extension_strings(registered).items():
        if key in text and text[key] != value:
            raise ValueError('Conflicting extension strings')
        text[key] = value
    text = names.validate_strings(text)
    item_templates._publish(templates)
    sets._publish(registered)
    names.ALL.update(text)
    if freeze:
        seal()
