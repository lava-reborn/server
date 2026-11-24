"""Execute the shipped AVM1: signed stats, trained ranks and partial snapshots."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import inventory
import items
import progression as p
import sets
from avm_test import Arr, Function
from stat_breakdown_client import patches
from testkit import run_cases
import widescreen as w


def string(value):
    return format(value, 'g') if isinstance(value, (int, float)) else str(value)


class StatBreakdown(unittest.TestCase):
    def setUp(self):
        self.attrs = {}
        self.gamer = dict(attributes=self.attrs, equipment={})
        self.env = dict(_global={}, String=string, Number=float,
                        parseFloat=lambda s: float(s.rstrip('% ')),
                        isNaN=math.isnan,
                        Math=dict(round=lambda v: math.floor(v + .5)),
                        lol=dict(core=dict(Master=dict(getInstance=lambda: dict(gamer=self.gamer)))))
        self.functions = {}
        spec = patches(w.Asm, w.UNDEF)
        for name, args, body in spec['globals']:
            fn = Function(args, body.assemble(), self.env)
            self.env['_global'][name] = self.functions[name] = fn
        for path, method, keep, args, body in spec['wraps']:
            self.functions[(path[-1], method)] = Function(args, body.assemble(), self.env)

    def call(self, cls, method, obj, *args):
        return self.functions[(cls, method)].invoke(obj, args)

    def value(self, base, total):
        return self.functions['__sbValue'].invoke(None, [base, total])

    def frame(self, ch):
        self.attrs.clear()
        for kind, count, base, effective in (
            ('attrib', p.ATTRIBS, ch.attrib, ch.attr),
            ('skill', p.SKILLS, [s[0] for s in ch.skill], ch.skill_level),
            ('spec', p.SPECS, [s[0] for s in ch.spec], ch.spec_level),
        ):
            rows = Arr([dict(value=base[i], value_bonus=effective(i), level=effective(i), title=str(i))
                        for i in range(count)])
            self.attrs[kind + 'Array'] = rows
            self.attrs.update({kind + str(i): row for i, row in enumerate(rows)})
        self.attrs['ap_max'] = ch.ap_max

    def test_signed_zero_positive_negative_and_fractional_values(self):
        for base, total, expected in ((16,21,'16 (+5)'), (16,14,'16 (-2)'),
                                      (16,16,'16'), (0,-2,'0 (-2)'),
                                      (10,10.25,'10 (+0.25)'), (0,0,'0')):
            self.assertEqual(self.value(base, total), expected)
        self.assertEqual(self.value(None, 1), '')

    def test_rank_and_experience_text_follow_trained_skill_not_bonus(self):
        for base in range(21):
            for delta in (-5, 0, 1, 5):
                native = lambda n: string(n) + (' (Профи), 12 из 100 (12%)' if n < 20 else ' (Гуру), 12 из 100 (12%)')
                obj = dict(value=base, level=base + delta, __sbSkillStringOrig=native)
                actual = self.call('SkillObject', 'skillString', obj, base + delta)
                self.assertEqual(actual, self.value(base, base + delta) + native(base)[len(str(base)):])
                self.assertEqual((obj['value'], obj['level']), (base, base + delta))

    def test_every_released_set_and_all_pouches_show_the_real_stat_pairs(self):
        pouches = [t for t, (root, _) in items.catalogue().items() if root == items.WEAR
                   and items.params_of(t).get('slot_type') == inventory.BELT - inventory.HEAD]
        for rec in sets.SETS.values():
            if rec.get('variant') not in ('A', 'G') or not 1 <= rec['level'] <= 17:
                continue
            for pouch in pouches:
                ch = p.Character()
                ch.set_skill(p.MELEE, min(16, rec['level']))
                ch.set_skill(p.SHOOTING, min(16, rec['level']))
                for i in range(p.SPECS):
                    ch.set_spec(i, 3)
                rows = [dict(type_id=t, root=items.WEAR, slot=inventory.HEAD + items.params_of(t)['slot_type'], brk=1000)
                        for t in rec['members'].values()]
                rows.append(dict(type_id=pouch, root=items.WEAR, slot=inventory.BELT, brk=1000))
                ch.set_gear(inventory.gear_bonus(rows, ch))
                before = ch.rows()
                self.frame(ch)
                card = {'attribute' + str(i): dict(value={}) for i in range(p.ATTRIBS)}
                card['__sbCardOrig'] = lambda obj: None
                self.call('CharInterface', 'rpUpdate', card, {})
                for i in range(p.ATTRIBS):
                    self.assertEqual(card['attribute' + str(i)]['value']['text'], self.value(ch.attrib[i], ch.attr(i)))
                spec_rows = Arr([dict(data=row) for row in self.attrs['specArray']])
                card['__sbSpecsOrig'] = lambda: card['specItemArr'].extend(spec_rows)
                for _ in range(2):
                    self.call('CharInterface', 'attachSpec', card)
                    self.assertEqual(len(card['specItemArr']), p.SPECS)
                    for i, row in enumerate(card['specItemArr']):
                        self.assertEqual(row['label'], str(i) + ', ' + self.value(ch.spec[i][0], ch.spec_level(i)))
                self.assertEqual(self.call('PersAttributes', 'getLevel', self.attrs), ch.level)
                self.assertEqual(ch.rows(), before)

    def test_snapshot_notifies_only_real_gains_even_when_total_level_is_unchanged(self):
        skill, spec = dict(value=16, level=21), dict(value=3, level=5)
        notices = []
        attrs = dict(skillArray=Arr([skill]), specArray=Arr([spec]), __sbInfoOrig=lambda obj: None,
                     __sbSkillGainOrig=lambda obj: notices.append(('skill', obj['value'])),
                     __sbSpecGainOrig=lambda obj: notices.append(('spec', obj['value'])))
        self.call('PersAttributes', 'rp_info', attrs, {})  # Login is silent.
        for bonus in (0, 5, -2, 5):
            skill['level'], spec['level'] = 16 + bonus, 3 + bonus
            self.call('PersAttributes', 'rp_info', attrs, {})
        self.assertEqual(notices, [])
        skill['value'], spec['value'] = 17, 4  # Effective values may stay unchanged.
        self.call('PersAttributes', 'rp_info', attrs, {})
        self.call('PersAttributes', 'rp_info', attrs, {})
        self.assertEqual(notices, [('skill',17), ('spec',4)])

    def test_derived_card_values_keep_native_totals_and_show_raw_basis(self):
        ch = p.Character()
        ch.set_skill(p.MELEE, 16)
        ch.set_skill(p.SHOOTING, 16)
        for i in range(p.SPECS):
            ch.set_spec(i, 3)
        self.frame(ch)
        for method, field, orig, base, total in (
            ('showArmorLevel', 'ArmorClassValue', '__sbArmorOrig', ch.armor, ch.armor + 460),
            ('showOD', 'od_value', '__sbODOrig', ch.ap_max, ch.ap_max + 50),
            ('showMeleeEvade', 'meleeEvade_value', '__sbEvadeOrig', p.melee_evade(ch), p.melee_evade(ch) - 2),
        ):
            target = {field: dict(value=dict(text=str(total))), orig: lambda: None}
            self.call('CharInterface', method, target)
            suffix = '%' if method == 'showMeleeEvade' else ''
            self.assertEqual(target[field]['value']['text'], self.value(base, total) + suffix)
        for kind in range(6):
            self.gamer['equipment']['primaryItem'] = dict(getProp=lambda key, k=kind: k)
            cp, ce = p.crit_chance(ch, kind)
            card = dict(crit_txt=dict(text=str(cp + 32)), critDodge_txt=dict(text=str(ce - 2)),
                        __sbCritOrig=lambda: None)
            self.call('CharInterface', 'showKrit', card)
            self.assertEqual(card['crit_txt']['text'], self.value(cp, cp + 32) + '%')
            self.assertEqual(card['critDodge_txt']['text'], self.value(ce, ce - 2) + '%')


if __name__ == '__main__':
    run_cases(StatBreakdown)
