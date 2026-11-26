"""Execute emitted battle hooks: no Flash, database, sockets or load run."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import math
import re
import unittest

import widescreen as w
from avm_test import Arr, Function
from combat_client import patches
from testkit import run_cases
from test_weapon_tooltips import sparse
from avm_test import execute, get


class CombatClient(unittest.TestCase):
    def level_card(self, root, level, allowance=3, skills=None):
        panel, rows = self.annotation()
        skills = sparse({1: level}) if skills is None else skills
        titles = sparse({0: 'Ближний бой', 1: 'Стрельба', 2: 'Медицина',
                         3: 'Промышленность', 4: 'Производство'}, 5)
        spec_titles = sparse({6: 'Ручные пулеметы'})
        specs = sparse({6: 0})
        props = dict(equip_level=level, equip_allowance=allowance,
                     need_skills=skills, need_specs=specs)
        panel.update(item=dict(rootID=root, getProp=props.get),
                     skillsTitle=titles, specTitle=spec_titles)

        def original(arr, title_arr):
            return ''.join(str(get(title_arr, i)) + ' ' + str(get(arr, i)) + '\r'
                           for i in range(get(arr, 'length')) if get(arr, i)) or None

        # Compose with the existing zero-specialisation wrapper, exactly as
        # injected into the client, rather than replacing its behaviour.
        panel['__requirementsReadOrig'] = original
        panel['__bfLevelReadOrig'] = lambda arr, title_arr: execute(
            w.fn_annotation_requirements_read().assemble(),
            dict(this=panel, arr=arr, titleArr=title_arr))
        return panel, rows, skills, titles, props

    def test_gear_level_requirement_has_allowance_and_retains_independent_skills(self):
        for root in (0, 1, 5):
            for level, allowance, label in ((4, 3, '4(-3)'), (16, 0, '16')):
                with self.subTest(root=root, level=level, allowance=allowance):
                    skills = sparse({0: level, 1: level, 2: 2, 3: 3}, 5)
                    panel, rows, _, titles, _ = self.level_card(root, level, allowance, skills)
                    text = self.call('__bfLevelRead', panel, skills, titles)
                    self.call('__bfAnnotationRow', panel, 'Необходимые\rнавыки', text)
                    self.assertEqual(rows, [('Требуемый уровень:', label),
                                            ('Необходимые\rнавыки',
                                             'Медицина 2\rПромышленность 3\r')])
                    self.assertEqual(get(skills, 1), level)

    def test_level_row_remains_when_native_combat_skill_row_becomes_empty(self):
        panel, rows, skills, titles, _ = self.level_card(0, 4)
        text = self.call('__bfLevelRead', panel, skills, titles)
        self.assertIsNone(text)
        self.call('__bfAnnotationRow', panel, 'Необходимые навыки', text)
        self.call('__bfAnnotationRow', panel, 'Необходимый навык бойца', 5)
        self.assertEqual(rows, [('Требуемый уровень:', '4(-3)'),
                                ('Необходимый навык бойца', 5)])

    def test_native_gear_callers_always_forward_even_undefined_requirement_rows(self):
        source = (Path(__file__).resolve().parents[1] /
                  'recon/as-src/lol/gpui/Annotation.as').read_text(encoding='utf-8')
        for method in ('fireArm', 'coldArm', 'wear', 'healItem'):
            body = source.split('   function ' + method + '(', 1)[1].split('\n   function ', 1)[0]
            self.assertRegex(body, r'\.push\(\["Необходимые(?:\\r| )навыки",(?:_loc\d+_|str)\]\);')
            # This native unconditional loop calls our addItem wrapper before
            # native addItem suppresses undefined values; there is no caller
            # filter that could hide a level-only requirement card.
            self.assertRegex(body, r'while\([^\n]+\.length\)\s*\{\s*'
                                  r'this\.addItem\(_loc\d+_\[_loc\d+_\]\[0\],'
                                  r'_loc\d+_\[_loc\d+_\]\[1\]\);')

    def test_buff_medicine_and_gear_without_level_keep_literal_skill_requirements(self):
        for root, level in ((2, 14), (3, 14), (6, 14), (0, None), (1, 0), (5, 0)):
            with self.subTest(root=root, level=level):
                panel, rows, _, titles, _ = self.level_card(root, level)
                skills = sparse({1: 14, 0: 7}, 5)
                panel['item']['getProp'] = dict(need_skills=skills, equip_level=level,
                                               equip_allowance=3).get
                text = self.call('__bfLevelRead', panel, skills, titles)
                self.call('__bfAnnotationRow', panel, 'Необходимые\rнавыки', text)
                self.assertEqual(rows, [('Необходимые\rнавыки',
                                        'Ближний бой 7\rСтрельба 14\r')])

    def test_stimulant_strict_level_is_visible_without_equipment_allowance(self):
        panel, rows = self.annotation()
        props = dict(buff_level=14)
        panel['item'] = dict(rootID=2, getProp=props.get)
        self.call('__bfAnnotationRow', panel, 'Необходимые\rнавыки', None)
        self.assertEqual(rows, [('Требуемый уровень:', '14')])
        rows.clear()
        props['buff_level'] = 0  # G copy.
        self.call('__bfAnnotationRow', panel, 'Необходимые\rнавыки', None)
        self.assertEqual(rows, [])

    def test_bonus_array_identity_and_zero_specialisation_remain_unchanged(self):
        panel, _, _, titles, props = self.level_card(0, 4)
        bonus = sparse({1: 4}, 5)
        self.assertEqual(self.call('__bfLevelRead', panel, bonus, titles), 'Стрельба 4\r')
        self.assertEqual(self.call('__bfLevelRead', panel, props['need_specs'], panel['specTitle']),
                         'Ручные пулеметы 0\r')

    def test_static_level_fields_are_retained_before_native_need_parser(self):
        seen = []
        obj = dict(equip_level=16, equip_allowance=0, need_skills=[16], need_skills_m=2)
        item = {}
        item['__bfLevelNeedsOrig'] = lambda supplied: seen.append(
            (item.get('equip_level'), item.get('equip_allowance'), supplied)) or 'native'
        self.assertEqual(self.call('__bfLevelNeeds', item, obj), 'native')
        self.assertEqual(seen, [(16, 0, obj)])
        # Reusing a prototype with an ordinary static packet cannot leave a
        # stale allowance on medicine, templates or level-zero equipment.
        self.call('__bfLevelNeeds', item, {})
        self.assertIsNone(item['equip_level'])
        self.assertIsNone(item['equip_allowance'])

    def annotation(self):
        rows = []
        panel = dict(__bfAnnotationRowOrig=lambda title, value:
                     rows.append((title, value)) if value is not None else None,
                     readArray=lambda arr, titles: 'array bonus' if any(arr or ()) else None,
                     attribsTitle=[], skillsTitle=[], specTitle=[])
        panel['addItem'] = lambda *args: self.call('__bfAnnotationRow', panel, *args)
        self.env['lol']['gpui'] = dict(Annotation=dict(getTextDuration=lambda ms: str(ms)))
        return panel, rows

    def effect(self, **changes):
        return dict(dict(work_time=1800000, update_delta=0, bonusAttribs=[],
                         bonusSkills=[], bonusSpecs=[], max_hp=0, max_sp=0, max_od=0,
                         critical_probability=0, critical_evade=0, armor=0,
                         mob_exp=1, player_exp=1, mob_drop=1, player_drop=1), **changes)

    def test_scanner_displays_direct_loot_bonus_and_no_empty_statistics(self):
        panel, rows = self.annotation()
        effect = self.effect(mob_drop=3)
        before = dict(effect)
        self.call('__bfEffectAnnotation', panel, effect)
        self.assertEqual(rows, [('Время действия', '1800000'),
                                ('Бонус\rк луту с мобов', '+200%')])
        self.assertEqual(effect, before)

    def test_experience_bonus_and_penalty_have_correct_sign_in_active_card(self):
        for factor, label, percent in ((1.7, 'Бонус', '+70%'), (1.5, 'Бонус', '+50%'),
                                       (0.5, 'Штраф', '-50%'), (0, 'Штраф', '-100%')):
            panel, rows = self.annotation()
            self.call('__bfEffectAnnotation', panel,
                      self.effect(mob_exp=factor, player_exp=factor))
            self.assertEqual(rows[1:], [(label + '\rк опыту с мобов', percent),
                                        (label + '\rк опыту с игроков', percent)])

    def test_ap_hp_and_other_nonzero_bonuses_match_protocol_without_doubling(self):
        panel, rows = self.annotation()
        self.call('__bfEffectRows', None, panel,
                  self.effect(max_od=40, max_hp=120, max_sp=90, critical_probability=7,
                              critical_evade=4, armor=6, bonusAttribs=[0, 3, 0]))
        self.assertEqual(rows[1:], [('Бонусы\rк аттрибутам', 'array bonus'),
                                   ('Бонус к здоровью', 120), ('Бонус к выносливости', 90),
                                   ('Бонус\rк очкам действия', 40),
                                   ('Бонус\rк критическому попаданию', 7),
                                   ('Бонус\rк избеганию крита', 4), ('Бонус к броне', 6)])

    def test_zero_fighter_requirement_is_hidden_and_real_item_rows_remain(self):
        panel, rows = self.annotation()
        for title, value in [('Необходимый навык бойца', 0), ('Бонус к здоровью', 0),
                             ('Необходимый навык бойца', 5), ('Вес', '0 г'),
                             ('Базовая цена', '0 G'), ('Урон здоровью', '0-0')]:
            self.call('__bfAnnotationRow', panel, title, value)
        self.assertEqual(rows, [('Необходимый навык бойца', 5), ('Вес', '0 г'),
                                ('Базовая цена', '0 G'), ('Урон здоровью', '0-0')])

    def test_missing_and_neutral_modifiers_are_hidden_and_protection_keeps_native_meaning(self):
        for empty in (None, 1, float('nan')):
            panel, rows = self.annotation()
            self.call('__bfEffectRows', None, panel,
                      self.effect(mob_drop=empty, mob_exp=empty, player_exp=empty,
                                  max_od=float('nan'), player_drop=0.75))
            self.assertEqual(rows[1:], [('Защита вашего дропа', '25%')])

    def test_all_server_buffs_show_their_actual_modifiers_and_action_points(self):
        import effects
        for source, value in effects.definitions().items():
            with self.subTest(source=source):
                bonus = value['bonuses']
                modifiers = value.get('modifiers', {})
                panel, rows = self.annotation()
                effect = self.effect(max_od=bonus['od'], mob_drop=modifiers.get('mob_drop', 1),
                                     mob_exp=modifiers.get('mob_exp', 1),
                                     player_exp=modifiers.get('pl_exp', 1))
                self.call('__bfEffectRows', None, panel, effect)
                for key, title in [('mob_drop', 'к луту с мобов'),
                                   ('mob_exp', 'к опыту с мобов'), ('pl_exp', 'к опыту с игроков')]:
                    factor = modifiers.get(key, 1)
                    percent = round((factor - 1) * 100)
                    expected = ('Бонус' if percent > 0 else 'Штраф') + '\r' + title
                    actual = [(name, text) for name, text in rows if name.endswith(title)]
                    self.assertEqual(actual, [(expected, format(percent, '+d') + '%')] if percent else [])
                self.assertEqual([text for title, text in rows if title == 'Бонус\rк очкам действия'],
                                 [bonus['od']] if bonus['od'] else [])

    def test_item_effect_list_uses_same_rows_and_preserves_native_titles_icons_and_alignment(self):
        panel, rows = self.annotation()
        titles, lines, icons, calls = [], [], [], []
        def attach(kind, name, depth):
            if kind == 'effect_title':
                title = dict(effect_name=dict(_y=2, _height=10), effect_prob={})
                titles.append(title)
                return title
            line = {}
            lines.append(line)
            return line
        def clip():
            return dict(attachMovie=attach, getNextHighestDepth=lambda: 1)
        panel.update(cont_mc=dict(removeMovieClip=lambda: calls.append('remove')),
                     createEmptyMovieClip=lambda *args: clip(), getNextHighestDepth=lambda: 1,
                     name_txt=dict(setTextFormat=lambda style: calls.append('style')),
                     back=dict(my_mc={}), showFullAnnotation='full',
                     doLater=lambda method: calls.append(method))
        self.env['TextFormat'] = lambda: {}
        self.env['lol']['services'] = dict(
            HotKeyEvent=dict(CTRL='ctrl'), SSEmulator=dict(getEffectIcon=lambda res: res))
        self.env['lol']['core']['SceneShifter']['hotKeyManager'] = dict(
            removeEventListener=lambda *args: calls.append('unlisten'))
        self.env['lol']['display'] = dict(DisplaySprite=dict(create=lambda *args:
            dict(display=lambda *args: icons.append(args))))
        scanner = self.effect(mob_drop=3, name='Сканер', res_icon=1)
        xp = self.effect(mob_exp=1.9, player_exp=1.9, name='INTUX IV', res_icon=2)
        self.call('__bfEffectsInfo', panel, Arr([scanner, None, xp]), Arr([100, 0, 75]), True, True)
        self.assertEqual([t['effect_name']['htmlText'] for t in titles], ['Сканер', 'INTUX IV'])
        self.assertEqual([t['effect_prob']['htmlText'] for t in titles],
                         ['Вероятность срабатывания: 100', 'Вероятность срабатывания: 75'])
        self.assertEqual(rows, [('Время действия', '1800000'), ('Бонус\rк луту с мобов', '+200%'),
                                ('Время действия', '1800000'), ('Бонус\rк опыту с мобов', '+90%'),
                                ('Бонус\rк опыту с игроков', '+90%')])
        self.assertEqual((panel['arrItem'], panel['arrLine']), (titles, lines))
        self.assertEqual(icons, [('0_effect_icon', 1), ('2_effect_icon', 2)])
        self.assertEqual(calls, ['unlisten', 'remove', 'style', 'align'])
        self.assertEqual(panel['back']['my_mc']['_alpha'], 100)

    def test_base_caption_uses_real_clan_name_as_plain_text_and_tracks_revocation(self):
        clan = dict(clanName='<Clan & friends>')
        member = dict(clanReg=123, clanInfo=clan)
        panel = dict(player=dict(__bfBaseFlag=True, clanMemberInfo=member),
                     info_txt=dict(textHeight=12), infoShadow_txt={},
                     hBar=dict(_visible=False, _y=30), sBar=dict(_y=20))
        self.call('__bfBaseCaption', None, panel)
        self.assertEqual(panel['info_txt']['text'], 'Клановая база\r<Clan & friends>')
        self.assertTrue(panel['info_txt']['multiline'])
        self.assertEqual(panel['infoShadow_txt']['text'], panel['info_txt']['text'])
        self.assertEqual((panel['info_txt']['_y'], panel['infoShadow_txt']['_y']), (8, 9))
        member['clanReg'] = 0
        self.call('__bfBaseCaption', None, panel)
        self.assertEqual(panel['info_txt']['text'], 'Незанятая клановая база')
        self.assertEqual(clan, dict(clanName='<Clan & friends>'))

    def test_other_npc_and_player_captions_are_left_to_the_native_renderer(self):
        for marked in (False, None):
            panel = dict(player=dict(__bfBaseFlag=marked), info_txt=dict(text='native'))
            self.call('__bfBaseCaption', None, panel)
            self.assertEqual(panel['info_txt'], dict(text='native'))
        npc = dict(__bfNPCInfoOrig=lambda event: 'native')
        for type_id, expected in ((4427, True), (4428, True), (1011, False), (1959, False)):
            self.assertEqual(self.call('__bfNPCInfo', npc, dict(param=dict(res=type_id))), 'native')
            self.assertEqual(npc['__bfBaseFlag'], expected)

    def test_quest_only_base_flags_open_after_native_contact_at_the_same_or_adjacent_cell(self):
        for type_id in (4427, 4428):
            for adjacent, same in ((True, False), (False, True)):
                with self.subTest(flag=type_id, adjacent=adjacent, same=same):
                    calls = []
                    cell, other = object(), object()
                    flag = dict(id=73, playerInfo=dict(ally=True), canTrade=False,
                                canRepair=False, canTrophy=False, hasAvailableQuests=lambda: True,
                                __bfNPCInfoOrig=lambda event: None)
                    self.call('__bfNPCInfo', flag, dict(param=dict(res=type_id)))
                    self.env['lol']['core']['Master'] = dict(getInstance=lambda: dict(
                        getPlayer=lambda _id: flag, currentLocation=dict(
                            getCellFromNumber=lambda _pos: cell, isSiblings=lambda a, b: adjacent)))
                    self.env['lol']['core']['player']['NPCService'] = dict(
                        openService=lambda _id: calls.append(('quests', _id)))
                    gamer = dict(walker=dict(numPos=2002), __bfFlagContactOrig=lambda event: calls.append('native'))
                    self.call('__bfFlagContact', gamer, dict(id=73, targetCell=cell if same else other))
                    self.assertEqual(calls, ['native', ('quests', 73)])

    def test_base_flag_contact_respects_reach_availability_and_existing_services(self):
        for reason in ('far', 'unavailable', 'hostile', 'ordinary', 'trade', 'repair', 'trophy', 'gone'):
            with self.subTest(reason=reason):
                calls = []
                flag = dict(id=73, __bfBaseFlag=reason != 'ordinary',
                            playerInfo=dict(ally=reason != 'hostile'), canTrade=reason == 'trade',
                            canRepair=reason == 'repair', canTrophy=reason == 'trophy',
                            hasAvailableQuests=lambda: reason != 'unavailable')
                self.env['lol']['core']['Master'] = dict(getInstance=lambda: dict(
                    getPlayer=lambda _id: None if reason == 'gone' else flag,
                    currentLocation=dict(getCellFromNumber=lambda _pos: 'here',
                                         isSiblings=lambda a, b: reason != 'far')))
                self.env['lol']['core']['player']['NPCService'] = dict(
                    openService=lambda _id: calls.append('unexpected extra window'))
                gamer = dict(walker=dict(numPos=2002), __bfFlagContactOrig=lambda event: calls.append('native'))
                self.call('__bfFlagContact', gamer, dict(id=73, targetCell='there'))
                self.assertEqual(calls, ['native'])

    def test_action_point_stat_changes_ceiling_without_refill_or_timer_reset(self):
        manager = dict(_maxAP=110, currentAP=23, dAP=4, dtAPInterval=91)
        calls = []
        def native(event):
            calls.append(event)
            manager['currentAP'] = max(0, min(event['param']['ap'], manager['_maxAP']))
        manager['__bfSyncAPOrig'] = native
        for maximum, paid in ((155, 23), (155, 23), (140, 140), (155, 140),
                              (150, 17), (150, 11), (110, 110)):
            event = dict(param=dict(amax=maximum, ap=paid))
            self.call('__bfSyncAP', manager, event)
            self.assertEqual((manager['_maxAP'], manager['currentAP']), (maximum, paid))
            self.assertEqual((manager['dAP'], manager['dtAPInterval']), (4, 91))
            self.assertIs(calls[-1], event)
        self.call('__bfSyncAP', manager, dict(param=dict(ap=6)))
        self.assertEqual((manager['_maxAP'], manager['currentAP']), (110, 6))
        self.assertEqual(len(calls), 8)

    def test_legacy_action_point_packet_preserves_native_ceiling(self):
        for supplied in (None, 0, -1, float('nan')):
            manager = dict(_maxAP=110)
            events = []
            manager['__bfSyncAPOrig'] = events.append
            event = dict(param=dict(amax=supplied, ap=17))
            self.call('__bfSyncAP', manager, event)
            self.assertEqual(manager['_maxAP'], 110)
            self.assertEqual(events, [event])

    def test_empty_remote_primary_uses_fist_without_type_zero_request(self):
        equip = dict(isGamer=False, primaryItem='old weapon',
                     __bfRemotePrimaryOrig=lambda event:self.fail('type-zero prototype requested'))
        self.call('__bfRemotePrimary', equip, dict(param=dict(to=512, obj='0')))
        self.assertIsNone(equip['primaryItem'])

    def test_remote_weapon_and_clothes_keep_native_item_processing(self):
        events = []
        equip = dict(isGamer=False, __bfRemotePrimaryOrig=events.append)
        for to, oid in ((512, '1642400'), (256, '0')):
            event = dict(param=dict(to=to, obj=oid))
            self.call('__bfRemotePrimary', equip, event)
            self.assertIs(events[-1], event)

    def test_own_primary_move_is_left_to_native_ack_processing(self):
        events = []
        equip = dict(isGamer=True, __bfRemotePrimaryOrig=events.append)
        event = dict(param=dict(to=512, obj='0'))
        self.call('__bfRemotePrimary', equip, event)
        self.assertEqual(events, [event])

    def test_firearm_stance_exists_before_native_cached_name_notification(self):
        # The native weapon_type setter derives pistol/rifle immediately.
        # Simulate Item.initialize publishing itemUpdate before FireArm's
        # own assignment; no later DI notification is guaranteed for mobs.
        for kind in range(6):
            with self.subTest(kind=kind):
                weapon, notifications = {}, []
                static_info = dict(weapon_type=kind, clip_size=30)

                def native(obj):
                    notifications.append(weapon.get('weapon_type'))
                    self.assertIs(obj, static_info)
                    weapon['clip_size'] = obj['clip_size']
                    return 'initialized'

                weapon['__bfFirearmInitOrig'] = native
                result = self.call('__bfFirearmInit', weapon, static_info)
                self.assertEqual(notifications, [kind])
                self.assertEqual(weapon['clip_size'], 30)
                self.assertEqual(result, 'initialized')
                self.assertEqual(static_info, dict(weapon_type=kind, clip_size=30))

    def setUp(self):
        self.sent, self.calls, self.applied = [], [], []
        self.reported = []
        self.env = dict(_global={}, Number=float, isNaN=math.isnan, TextFormat=lambda: {},
                        String=lambda value: format(value, 'g'),
                        parseFloat=lambda value: float(re.match(r'[-+]?\d+(?:\.\d+)?', str(value))[0])
                        if re.match(r'[-+]?\d+(?:\.\d+)?', str(value)) else float('nan'),
                        Math=dict(max=max, min=min, round=round, floor=math.floor),
                        lol=dict(core=dict(SceneShifter=dict(linkGame=dict(
                            visavisAvatar=dict(removeMovieClip=lambda: self.calls.append('avatar')))),
                            player=dict(Training=dict(UPD_CLOSE=0)),
                            objects=dict(Item=dict(FIRE_ARM=0),
                                         FireArm=dict(PISTOL=0, SHOTGUN=1, ASSAULT=2,
                                                      RIFLE=3, MACHINEGUN=4, SMG=5))),
                            data=dict(BigUINTCluster=lambda n: dict(value=n), BigUINT=lambda c: c),
                            server=dict(mess=dict(CSM_SSUpdate=lambda a,b: dict(kind=a, number=b)))))
        spec = patches(w.Asm, w.UNDEF, training=True)
        self.functions = {}
        for name, params, body in spec['globals']:
            fn = Function(params, body.assemble(), self.env)
            self.env['_global'][name] = fn
            self.functions[name] = fn

    def call(self, name, target, *args):
        return self.functions[name].invoke(target, args)

    def card(self, effects=(), armor=()):
        slots = ('head', 'armor', 'camouflage', 'belt', 'legs', 'boots')
        equipment = {slot: dict(item=None) for slot in slots}
        for slot, remaining, value in armor:
            props = dict(__break=remaining, armor_class=value)
            equipment[slot]['item'] = dict(getProp=props.get)
        equipment['primaryItem'] = dict(rootID=0)
        self.env['lol']['core']['Master'] = dict(getInstance=lambda: dict(gamer=dict(
            equipment=equipment, effects=dict(getFXArrayLength=lambda: len(effects),
                                              getEffect=lambda index: effects[index]))))
        panel = dict(crit_txt=dict(text=''), critDodge_txt=dict(text=''),
                     ArmorClassValue=dict(value=dict(text='')))

        def crit():
            panel['crit_txt']['text'] = str(40 + sum(fx.get('critical_probability', 0) for fx in effects)) + ' %'
            panel['critDodge_txt']['text'] = str(20 + sum(fx.get('critical_probability', 0)
                                                       for fx in effects if fx.get('critical_evade'))) + ' %'

        def armour():
            panel['ArmorClassValue']['value']['text'] = 30 + sum(value for _, _, value in armor)

        panel.update(__bfCritCardOrig=crit, __bfArmorCardOrig=armour)
        return panel, equipment

    def test_omega_anticrit_uses_evade_without_changing_critical(self):
        effects = [dict(critical_probability=0, critical_evade=10)]
        panel, _ = self.card(effects)
        for _ in range(3):
            self.call('__bfCritCard', panel)
            self.assertEqual(panel['crit_txt']['text'], '40 %')
            self.assertEqual(panel['critDodge_txt']['text'], '30 %')
        effects.clear()
        self.call('__bfCritCard', panel)
        self.assertEqual(panel['critDodge_txt']['text'], '20 %')

    def test_mixed_crit_effects_add_their_own_stat_once(self):
        effects = [dict(critical_probability=7, critical_evade=0),
                   dict(critical_probability=3, critical_evade=11),
                   dict(critical_probability=4, critical_evade=4)]
        panel, _ = self.card(effects)
        self.call('__bfCritCard', panel)
        self.assertEqual(panel['crit_txt']['text'], '54 %')
        self.assertEqual(panel['critDodge_txt']['text'], '35 %')

    def test_non_firearm_and_pending_native_stats_are_not_rewritten(self):
        panel, equipment = self.card([dict(critical_probability=0, critical_evade=10)])
        for weapon in (None, dict(rootID=5)):
            equipment['primaryItem'] = weapon
            panel['__bfCritCardOrig'] = lambda: panel['critDodge_txt'].update(text='')
            self.call('__bfCritCard', panel)
            self.assertEqual(panel['critDodge_txt']['text'], '')
        equipment['primaryItem'] = dict(rootID=0)
        panel['__bfCritCardOrig'] = lambda: panel['critDodge_txt'].update(text='-')
        self.call('__bfCritCard', panel)
        self.assertEqual(panel['critDodge_txt']['text'], '-')

    def test_broken_armor_is_removed_from_card_without_losing_other_stats(self):
        armor = [('head', 0, 10), ('armor', 1, 20), ('camouflage', 0, 5),
                 ('belt', 50, 2), ('legs', 0, 7), ('boots', 9, 8)]
        panel, _ = self.card(armor=armor)
        for _ in range(3):
            self.call('__bfArmorCard', panel)
            self.assertEqual(panel['ArmorClassValue']['value']['text'], 60)
        armor[0] = ('head', 1, 10)
        panel, _ = self.card(armor=armor)
        self.call('__bfArmorCard', panel)
        self.assertEqual(panel['ArmorClassValue']['value']['text'], 70)

    def test_training_server_stats_still_override_ordinary_card_corrections(self):
        from avm_codegen import Compiler
        from training_ground_client import SOURCE
        native = {name: Function(params, body.assemble(), self.env)
                  for name, params, body in Compiler(w.Asm, w.UNDEF).functions(SOURCE)
                  if name in ('__tgArmorCard', '__tgCritCard')}
        panel, _ = self.card([dict(critical_probability=0, critical_evade=10)], [('head', 0, 10)])
        panel['__tgCritCardOrig'] = lambda: self.call('__bfCritCard', panel)
        panel['__tgArmorCardOrig'] = lambda: self.call('__bfArmorCard', panel)
        self.env['_global'].update(__tgActive=True,
                                  __tgCombatStats=dict(armour=125, critical=77, anticritical=66))
        native['__tgCritCard'].invoke(panel, ())
        native['__tgArmorCard'].invoke(panel, ())
        self.assertEqual(panel['crit_txt']['text'], '77 %')
        self.assertEqual(panel['critDodge_txt']['text'], '66 %')
        self.assertEqual(panel['ArmorClassValue']['value']['text'], '125')

    def test_ordinary_wrapper_leaves_already_applied_training_values_intact(self):
        panel, _ = self.card([dict(critical_probability=0, critical_evade=10)], [('head', 0, 10)])
        self.env['_global'].update(__tgActive=True, __tgCombatStats=dict(armour=125))
        panel['__bfCritCardOrig'] = lambda: panel['critDodge_txt'].update(text='66 %')
        panel['__bfArmorCardOrig'] = lambda: panel['ArmorClassValue']['value'].update(text='125')
        self.call('__bfCritCard', panel)
        self.call('__bfArmorCard', panel)
        self.assertEqual(panel['critDodge_txt']['text'], '66 %')
        self.assertEqual(panel['ArmorClassValue']['value']['text'], '125')

    def test_training_user_close_sends_one_close_and_finishes_cleanup(self):
        panel = dict(XMC=dict(Send=self.sent.append),
                     dispatchEvent=lambda e: self.calls.append(e['type']),
                     kill=lambda: self.calls.append('kill'))
        self.call('__bfTrainingClose', panel)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]['kind'], 0)
        self.assertEqual(self.calls, ['close', 'avatar', 'kill'])

    def test_server_training_close_does_not_echo_another_request(self):
        panel = dict(dispatchEvent=lambda e: self.calls.append(e['type']),
                     kill=lambda: self.calls.append('kill'))
        target = dict(removeEventListener=lambda *a: self.calls.append('unsubscribe'))
        self.call('__bfTrainingClose', panel, dict(target=target))
        self.assertEqual(self.sent, [])
        self.assertEqual(self.calls, ['unsubscribe', 'close', 'avatar', 'kill'])

    def test_bars_are_clamped_and_valid_full_health_is_preserved(self):
        for method in ('Health', 'Stamina'):
            seen=[]
            panel={'__bf'+method+'Orig': lambda p,v: seen.append((p,v))}
            for value in (-25, 0, 50, 100, 350, float('nan')):
                self.call('__bf'+method, panel, value, 500)
            self.assertEqual(seen, [(0,500),(0,500),(50,500),(100,500),(100,500),(0,500)])

    def scene(self):
        figure = dict(burstArr=Arr(), addEventListener=lambda *a: None,
                      removeEventListener=lambda *a: None)
        scene = dict(getWalker=lambda eid: figure,
                     __bfAimOrig=lambda e: self.calls.append(('aim',e['seq'])),
                     __bfFireOrig=lambda e: (figure['burstArr'].push(e), self.reported.append(e['seq'])),
                     applyFireAck=lambda e: self.applied.append(e['seq']),
                     addFireAckReport=lambda e: self.reported.append(e['seq']), showFireAckReport=lambda: None,
                     shotgunFireAck=lambda e: None, busrtFireAck=lambda e: None,
                     __bfDeadOrig=lambda e: self.calls.append(('dead',e['dead'])))
        return scene, figure

    def facing_scene(self, actor=1):
        scene, figure = self.scene()
        logical = dict(direction=4)
        rotate = lambda *args: None

        def cancel(callback):
            self.assertIs(callback, rotate)
            self.calls.append(('cancel-rotate', figure['__direction']))

        def native_aim(event):
            self.calls.append(('aim', event['seq'], figure['__direction']))
            logical['direction'] = figure['__direction']
            figure['behavior'] = 'fire_in'

        figure.update(id=actor, __direction=4, rotate=rotate, deleteEnterFrame=cancel)
        scene.update(__bfAimOrig=native_aim,
                     master=dict(getPlayer=lambda _id: dict(walker=logical)))
        return scene, figure, logical

    def test_firing_faces_every_direction_before_native_aim_for_owner_observer_and_mob(self):
        for actor in (0, 1, 1736):
            for direction in range(1, 9):
                with self.subTest(actor=actor, direction=direction):
                    self.calls.clear()
                    scene, figure, logical = self.facing_scene(actor)
                    self.call('__bfAim', scene, dict(aim=actor, ang=str(direction), num_shots=1, seq=1))
                    self.assertEqual(self.calls, [('cancel-rotate', 4), ('aim', 1, direction)])
                    self.assertEqual((figure['__direction'], logical['direction']), (direction, direction))
                    self.assertEqual(figure['behavior'], 'fire_in')
                    self.assertEqual(self.sent, [])
                    self.assertFalse(self.env['_global'].get('__bfInputTimer'))

    def test_queued_volley_does_not_turn_the_current_shot_early(self):
        scene, figure, logical = self.facing_scene(17)
        self.call('__bfAim', scene, dict(aim=17, ang=2, num_shots=1, seq=1))
        self.call('__bfFire', scene, dict(gunnerID=17, access=True, seq=1))
        self.call('__bfAim', scene, dict(aim=17, ang=6, num_shots=1, seq=2))
        self.call('__bfFire', scene, dict(gunnerID=17, access=True, seq=2))
        self.assertEqual((figure['__direction'], logical['direction']), (2, 2))
        self.assertEqual(self.calls, [('cancel-rotate', 4), ('aim', 1, 2)])
        figure['burstArr'].shift()
        self.call('__bfVisualFinal', scene, dict(target=figure, data='fire_out'))
        figure['__bfNextSequenceOrig'] = lambda: self.calls.append('native-transition')
        self.call('__bfNextSequence', figure)
        self.assertEqual(self.calls[-3:], ['native-transition', ('cancel-rotate', 2), ('aim', 2, 6)])
        self.assertEqual((figure['__direction'], logical['direction']), (6, 6))
        self.assertEqual([event['seq'] for event in figure['burstArr']], [2])

    def test_inactive_or_unanimated_figure_updates_facing_without_a_visual_queue(self):
        for changed in (dict(animationEnabled=False), dict(isActive=False)):
            with self.subTest(changed=changed):
                self.calls.clear()
                scene, figure, logical = self.facing_scene()
                figure.update(changed)
                self.call('__bfAim', scene, dict(aim=1, ang=6, num_shots=1, seq=1))
                self.assertEqual(self.calls, [('cancel-rotate', 4), ('aim', 1, 6)])
                self.assertEqual(logical['direction'], 6)
                self.assertFalse(figure.get('__bfBursts'))

    def test_invalid_or_coincident_facing_keeps_the_existing_direction_and_rotation(self):
        _scene, figure, _logical = self.facing_scene()
        for angle in (None, 0, -1, 9, 1.5, float('nan'), float('inf')):
            with self.subTest(angle=angle):
                self.call('__bfFaceAim', None, figure, dict(ang=angle))
                self.assertEqual(figure['__direction'], 4)
                self.assertEqual(self.calls, [])
        self.call('__bfFaceAim', None, figure, {})
        self.call('__bfFaceAim', None, None, dict(ang=2))
        self.assertEqual(self.calls, [])

    def test_firing_snap_does_not_override_the_next_native_movement_direction(self):
        scene, figure, _logical = self.facing_scene()
        self.call('__bfAim', scene, dict(aim=1, ang=6, num_shots=1, seq=1))
        figure['__bfBursts'] = Arr()
        walker = dict(id=1, direction=3)

        def native_position(event):
            figure['__direction'] = event['walker']['direction']
            figure['behavior'] = 'run'

        scene['__bfPositionOrig'] = native_position
        self.call('__bfPosition', scene, dict(walker=walker))
        self.assertEqual((figure['__direction'], figure['behavior']), (3, 'run'))

    def confirmed_volley(self, count=3, weapon=4):
        scene, figure = self.scene()
        figure.update(_x=100, _y=200, isActive=True, animationEnabled=True)
        sounds, traces = [], []
        names = ['PISTOL_FIRE', 'SHOTGUN_FIRE', 'ASSAULT_FIRE', 'RIFLE_FIRE',
                 'MACHINEGUN_FIRE', 'SMG_FIRE', 'FIREARM_FIRE']
        self.env['lol']['sound'] = dict(
            SoundEvent={name: name for name in names},
            SoundManager=dict(getInstance=lambda: dict(playEventSound=sounds.append)))
        scene['master'] = dict(getPlayer=lambda _id: dict(
            equipment=dict(primaryItem=dict(getProp=lambda _key: weapon))))
        scene['hitPoint'] = lambda hit: dict(x=hit['x'], y=hit['y'])
        scene['traceShot'] = lambda *args: traces.append(args)
        scene['applyFireAck'] = lambda event: self.call('__bfApplyFire', scene, event)
        scene['__bfApplyFireOrig'] = lambda event: self.fail('lost captured origin')
        self.call('__bfAim', scene, dict(aim=1, num_shots=count, seq=1))
        events = []
        for seq in range(count):
            event = dict(gunnerID=1, shot=True, access=True, seq=seq,
                         hits=Arr([dict(type='point', x=400, y=450)]))
            self.call('__bfFire', scene, event)
            events.append(event)
        return scene, figure, sounds, traces, events

    def test_confirmed_unplayed_shot_survives_movement_once_without_stalling_it(self):
        scene, figure, sounds, traces, events = self.confirmed_volley()
        figure.update(behavior='fire', onEnterFrame=lambda: None, _x=900, _y=900)
        walker = dict(id=1)
        scene['__bfPositionOrig'] = lambda obj: self.calls.append('movement')
        self.call('__bfPosition', scene, dict(walker=walker))
        self.assertEqual(traces, [(1, dict(x=400, y=450), dict(x=100, y=150))])
        self.assertEqual(sounds, ['MACHINEGUN_FIRE'])
        self.assertEqual(self.calls, [('aim', 1), 'movement'])
        self.assertEqual(self.reported, [0, 1, 2])
        self.assertEqual(figure['burstArr'], [])
        self.assertEqual(figure['__bfBursts'], [])
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual(len(traces), 1)
        self.assertEqual(len(sounds), 1)
        # A stale callback must not replay the same projectile.
        self.call('__bfApplyFire', scene, events[0])
        self.assertEqual(len(traces), 1)

    def test_other_action_and_final_frame_preserve_one_trace_not_entire_burst(self):
        for kind in ('Burst', 'Shotgun'):
            for transition in ('run', 'heal', 'change_weapon', 'fire_out'):
                with self.subTest(kind=kind, transition=transition):
                    self.reported.clear()
                    scene, figure, sounds, traces, _events = self.confirmed_volley(
                        count=9, weapon=1 if kind=='Shotgun' else 5)
                    scene['__bf'+kind+'FinalOrig'] = lambda obj: None
                    self.call('__bf'+kind+'Final', scene,
                              dict(target=figure, data=transition))
                    self.assertEqual(len(traces), 1)
                    self.assertEqual(sounds, ['SHOTGUN_FIRE' if kind=='Shotgun' else 'SMG_FIRE'])
                    self.assertEqual(self.reported, list(range(9)))
                    self.assertEqual(figure['__bfBursts'], [])

    def test_native_rendered_volley_is_not_replayed_or_given_a_second_sound(self):
        scene, figure, sounds, traces, events = self.confirmed_volley()
        # The native handler plays its sound after applyFireAck; leave that path alone.
        self.call('__bfApplyFire', scene, figure['burstArr'].shift())
        self.assertEqual(sounds, [])
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual(len(traces), 1)
        self.assertEqual(sounds, [])
        self.assertTrue(events[0]['__bfPresented'])

    def test_interruption_uses_weapon_sound_captured_at_aim_not_new_weapon(self):
        for weapon, expected in enumerate(('PISTOL_FIRE', 'SHOTGUN_FIRE', 'ASSAULT_FIRE',
                                           'RIFLE_FIRE', 'MACHINEGUN_FIRE', 'SMG_FIRE')):
            with self.subTest(weapon=weapon):
                scene, figure, sounds, _traces, _events = self.confirmed_volley(weapon=weapon)
                scene['master']['getPlayer'] = lambda _id: self.fail('late weapon lookup')
                self.call('__bfDead', scene, dict(dead=1))
                self.call('__bfDead', scene, dict(dead=1))
                self.assertEqual(sounds, [expected])

    def test_invisible_unconfirmed_melee_and_empty_shots_do_not_create_effects(self):
        for inactive in ('offscreen', 'animation_disabled', 'refused', 'melee', 'no_hits'):
            with self.subTest(case=inactive):
                scene, figure, sounds, traces, events = self.confirmed_volley(count=1)
                if inactive=='offscreen':
                    figure['isActive'] = False
                elif inactive=='animation_disabled':
                    figure['animationEnabled'] = False
                elif inactive=='refused':
                    events[0]['access'] = False
                elif inactive=='melee':
                    events[0]['shot'] = False
                else:
                    events[0]['hits'] = Arr()
                self.call('__bfVisualFlush', None, scene, figure, False)
                self.assertEqual((sounds, traces), ([], []))

    def test_cancelled_aim_never_creates_a_fallback_shot(self):
        scene, figure = self.scene()
        self.call('__bfAim', scene, dict(aim=1, num_shots=9, seq=1))
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual((self.reported, self.applied), ([], []))

    def test_repeat_aim_preserves_confirmed_previous_bullets(self):
        scene, figure = self.scene()
        self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=1))
        self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=2))
        self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=2))
        self.assertEqual(self.calls,[('aim',1)])
        self.assertEqual([e['seq'] for e in figure['burstArr']],[1])
        # Native final-frame handler consumes the confirmed first burst.
        scene['applyFireAck'](figure['burstArr'].shift())
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.calls,[('aim',1)])
        figure['__bfNextSequenceOrig'] = lambda: self.calls.append('native-transition')
        self.call('__bfNextSequence',figure)
        self.assertEqual(self.calls,[('aim',1),'native-transition',('aim',2)])
        self.assertEqual([e['seq'] for e in figure['burstArr']],[2])
        scene['applyFireAck'](figure['burstArr'].shift())
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[1,2])
        self.assertEqual(figure['__bfBursts'],[])

    def test_final_fire_out_discards_remaining_traces_but_keeps_reports(self):
        scene,figure=self.scene()
        self.call('__bfAim',scene,dict(aim=1,num_shots=2,seq=1))
        for seq in (1,2):
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=seq))
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2])
        self.assertEqual(figure['__bfBursts'],[])
        self.assertEqual(figure['burstArr'],[])
        # Native cleanup observes the empty buffer; no duplicate damage/report.
        scene['__bfBurstFinalOrig']=lambda event:None
        self.call('__bfBurstFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2])

    def test_death_discards_unplayed_traces_and_keeps_each_report_once(self):
        scene, figure = self.scene()
        for i in (1,2,3):
            self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=i))
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=i))
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2,3])
        self.assertEqual(figure['__bfBursts'],[])
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2,3])

    def test_queued_visuals_are_bounded_without_catch_up_traces_or_lost_reports(self):
        scene, figure = self.scene()
        for i in range(30):
            self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=i))
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=i))
            self.assertLessEqual(len(figure['__bfBursts']),8)
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,list(range(30)))

    def test_interrupted_burst_and_shotgun_do_not_render_all_remaining_bullets(self):
        for kind in ('Burst','Shotgun'):
            scene, figure = self.scene()
            scene['__bf'+kind+'FinalOrig'] = lambda e: self.calls.append('native')
            figure['burstArr']=Arr([dict(seq=1),dict(seq=2)])
            self.call('__bf'+kind+'Final',scene,dict(target=figure,data='run'))
            self.assertEqual(figure['burstArr'],[])
        self.assertEqual(self.applied,[])

    def test_delayed_trace_keeps_the_shot_positions_instead_of_following_moving_figures(self):
        scene,figure=self.scene()
        figure.update(_x=100,_y=200)
        target=dict(_x=400,_y=500)
        scene['getWalker']=lambda eid:figure if eid==1 else target
        event=dict(gunnerID=1,access=True,shot=True,seq=1,
                   hits=Arr([dict(type='target',targetID=2)]))
        self.call('__bfFire',scene,event)
        self.assertEqual(event.get('__bfOrigin'),dict(x=100,y=150))
        self.assertEqual(event['hits'][0].get('__bfPoint'),dict(x=400,y=450))
        figure.update(_x=-20,_y=-20)
        target.update(_x=800,_y=900)
        traces=[]
        self.env['lol']['fx']=dict(ShotTrace=lambda:dict(traceShot=lambda *args:traces.append(args)))
        self.env['Math']['random']=lambda:.5
        scene['helpers_mc']='helpers'
        scene['__bfTraceShotOrig']=lambda *args:self.fail('late native coordinates')
        scene['__bfApplyFireOrig']=lambda e:self.fail('lost captured event')
        scene['hitTarget']=lambda hit:hit['__bfPoint']
        scene['traceShot']=lambda *args:self.call('__bfTraceShot',scene,*args)
        self.call('__bfApplyFire',scene,event)
        self.assertEqual(traces,[('helpers',dict(x=100,y=150),dict(x=400,y=450))])
        self.assertEqual(event['hits'],[])


if __name__ == '__main__':
    run_cases(CombatClient)
