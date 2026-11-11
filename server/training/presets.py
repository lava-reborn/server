"""Server-selected starter kits for private avatars, never for real inventories."""
import copy
from functools import lru_cache
import secrets
import time

import inventory
import items
import progression
from training import items as training_items
from training import supply as training_supply
from protocol import Str

CLASSES = ('Пистолеты', 'Дробовики', 'Автоматы', 'Винтовки',
           'Пулемёты', 'Пистолет-пулемёты', 'Холодное оружие')
SPEC = (2, 3, 4, 5, 6, 7, 1)
AMMO_COUNT = 800
AFRO_MEDICINE_COUNT = 10
GOLD_MEDICINE_USES = 20


def required_level(params):
    return max(inventory.unpacked(params.get('need_skills_m'),
                                  params.get('need_skills'), progression.SKILLS))


def add_pouch(profile, level, line, simulator):
    candidates = [e for e in training_supply.index(simulator).values()
                  if e.category == 'pouch' and e.line == line and e.level <= level
                  and training_items.available(e.source, simulator)
                  and required_level(items.params_of(training_items.copy_type(e.source, simulator))) <= level]
    if candidates:
        chosen = min(candidates, key=lambda e: (-e.level, e.source))
        profile['gear'][chosen.source] = 1


@lru_cache(maxsize=560)
def recipe(level, line, wclass, simulator):
    """Bounded catalogue lookup; no database queries or per-frame calculations."""
    from training import catalog, character as ground
    from training import rules as training_rules
    if level not in range(1, 21) or line not in ('A', 'G') or wclass not in range(7):
        raise ValueError('Неизвестный готовый набор')
    entries = training_supply.index(simulator)
    available = lambda t: training_items.available(t, simulator)
    params = lambda t: items.params_of(training_items.copy_type(t, simulator=simulator))
    armours = [r for r in training_supply.set_catalogue().values()
               if r['variant'] == line and r['level'] <= level
               and all(available(t) for t in r['members'].values())]
    guns = [e for e in entries.values() if e.category == 'weapon'
            and e.line == line and e.weapon_class == wclass and 0 < e.level <= level
            and not e.upgrade and e.source not in catalog.contraband() and available(e.source)]
    if not armours or not guns:
        return None
    armour = min(armours, key=lambda r: (-r['level'], r['name']))
    rules = training_rules.Rules(simulator_formulas=simulator)
    for gun in sorted(guns, key=lambda e: (-e.level, e.source)):
        profile = ground.preset(level)
        spec_level = min(progression.SPEC_MAX, (level + 3) // 4)
        for index in (SPEC[wclass], 8, 9):
            profile['specs'][index] = spec_level
        profile['gear'] = {t: 1 for t in armour['members'].values()}
        profile['gear'][gun.source] = 1
        if items.root_of(gun.source) == items.FIRE_ARM:
            rounds = [training_items.profile_source(t) for t in params(gun.source).get('comp_array', ())]
            rounds = [t for t in rounds if t in entries and available(t)]
            if not rounds:
                continue
            # Prefer matching currency and standard ammunition; use the actual
            # active-profile compatibility list, not a guessed calibre name.
            ammo = min(rounds, key=lambda t: (entries[t].line != line,
                       not items.catalogue()[t][1].endswith('_ST'), t))
            profile['gear'][ammo] = min(AMMO_COUNT, params(ammo).get('max_count', AMMO_COUNT))
        add_pouch(profile, level, line, simulator)
        for field in ('max_h_rest', 'max_st_rest'):
            medicines = [e for e in entries.values() if e.category == 'medicine'
                         and e.line == line and available(e.source)
                         and required_level(params(e.source)) <= level
                         and params(e.source).get(field, 0) > 0
                         and (line == 'G' or params(e.source).get(field, 0) >
                              params(e.source).get('max_st_rest' if field == 'max_h_rest' else 'max_h_rest', 0))
                         and params(e.source).get('use_count', 1) == (GOLD_MEDICINE_USES if line == 'G' else 1)
                         and items.battle_medicine(e.source)]
            if medicines:
                medicine = min(medicines, key=lambda e: (-required_level(params(e.source)),
                               -params(e.source).get(field, 0), e.source))
                # A gold injector restores both resources: issue it once.
                profile['gear'][medicine.source] = 1 if line == 'G' else AFRO_MEDICINE_COUNT
        for source in profile['gear']:
            p = params(source)
            mask = p.get('need_specs_m', 0) or 0
            required = inventory.unpacked(mask, p.get('need_specs'), progression.SPECS)
            for index, need in enumerate(required):
                if mask >> index & 1:
                    profile['specs'][index] = max(profile['specs'][index], need)
        try:
            profile = ground.validate_profile(profile, rules)
        except ValueError:
            continue
        specs = ', '.join('%s %d' % (progression.SPEC_TITLES[i], n)
                          for i, n in enumerate(profile['specs']) if n >= 0)
        return dict(profile=profile, title='%d ур. · %s · %s' % (level, line, CLASSES[wclass]),
                    summary='Навыки: ближний бой, стрельба, медицина — %d.\nСпециализации: %s.\nКомплект: %s (%d ур.).'
                    % (level, specs, armour['name'], armour['level']),
                    contents='\n'.join('%s × %d' % (entries[t].name, n) for t, n in profile['gear'].items()))
    return None


def selected(ground, params):
    from training.validation import integer
    key = (integer(params.get('level', 1), 1, 20), str(params.get('line', 'A')),
           integer(params.get('wclass', 0), 0, 6), bool(ground.rules.simulator_formulas))
    result = recipe(*key)
    if result is None:
        raise ValueError('Для этого уровня и типа оружия готового набора нет')
    return key, result


def require(ground):
    ground.require_post()
    fighter = ground.clone.combat
    if (ground.closed or ground.phase != 'ready' or ground.context != 'player'
            or ground.clone.inv.store is not ground.store or ground.clone.ground is not ground
            or fighter.dead or fighter.duels
            or any(getattr(fighter, name, None) is not None
                   for name in ('aim', 'strike', 'healing', 'reloading'))):
        raise ValueError('Готовые наборы доступны у инструктора после завершения боя и действий')


def handle(ground, op, params):
    from training.validation import integer
    from training.character import validate_profile
    require(ground)
    if op == 'kit_preview':
        line = str(params.get('line', 'A'))
        wclass = integer(params.get('wclass', 0), 0, 6)
        level = integer(params.get('level', 1), 1, 20)
        levels = [n for n in range(1, 21) if recipe(n, line, wclass, bool(ground.rules.simulator_formulas))]
        if levels and level not in levels:
            level = min(levels, key=lambda n: (abs(n - level), n))
        entry = recipe(level, line, wclass, bool(ground.rules.simulator_formulas))
        ground.clone.send('tg', op='kit_preview', request_id=integer(params.get('request_id', 0), 0, 2**31-1),
                          level=level, line=Str(line), wclass=wclass, levels=levels, available=int(entry is not None),
                          title=Str(entry['title'] if entry else 'Нет готового набора'),
                          summary=Str(entry['summary'] if entry else 'Выберите другой тип оружия или версию.'),
                          contents=Str(entry['contents'] if entry else ''))
    elif op == 'kit_prepare':
        key, entry = selected(ground, params)
        validate_profile(entry['profile'], ground.rules)
        nonce = secrets.token_hex(16)
        ground.kit_confirmation = (nonce, time.monotonic() + 60, key, ground.rules, ground.outfit_revision)
        ground.clone.send('tg', op='kit_confirm', token=Str(ground.token), confirmation=Str(nonce),
                          title=Str(entry['title']))
    elif op == 'kit_apply':
        pending = getattr(ground, 'kit_confirmation', None)
        ground.kit_confirmation = None
        if (pending is None or pending[0] != params.get('confirmation') or time.monotonic() > pending[1]
                or pending[3] != ground.rules or pending[4] != ground.outfit_revision):
            raise ValueError('Набор или снаряжение изменились. Подтвердите получение заново.')
        entry = recipe(*pending[2])
        profile = validate_profile(copy.deepcopy(entry['profile']), ground.rules)
        ground.replace_player(profile, 'Готовый набор применён: ' + entry['title'])
    else:
        raise ValueError('Неизвестное действие готового набора')
