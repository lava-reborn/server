"""Medicine's displayed AP row must agree with the server's final cost."""
import re
import unittest
import items
import names
from testkit import run_cases


class MedicineDescriptions(unittest.TestCase):
    def test_every_battle_variant_describes_final_ap_and_preserves_other_words(self):
        seen=0
        pattern=re.compile(r'(Расход ОД:\s*</b>\s*)\d+(?:[.,]\d+)?')
        for type_id,(root,internal) in items.catalogue().items():
            if root!=items.HEAL or not internal.startswith('Med_Battle_'):
                continue
            with self.subTest(type=type_id):
                params=items.params_of(type_id)
                cost=params['heal_cost']
                did=items.DESC_ID_OFFSET+type_id
                before=names.ORIG_ITEM_DESCS[did]
                after=names.ALL[did]
                expected=pattern.sub(lambda m:m.group(1)+format(cost,'g'),before,count=1)
                self.assertEqual(after,expected)
                self.assertRegex(after,r'Расход ОД: </b>'+re.escape(format(cost,'g'))+r'$')
                seen+=1
        self.assertGreaterEqual(seen,31)

    def test_pacific_medicine_and_injector_costs_are_unchanged_by_description_patch(self):
        for type_id,(root,internal) in items.catalogue().items():
            if root==items.HEAL and internal.startswith('Med_Pacific_'):
                did=items.DESC_ID_OFFSET+type_id
                if did in names.ORIG_ITEM_DESCS:
                    self.assertEqual(names.ALL[did],names.ORIG_ITEM_DESCS[did])
        self.assertEqual(items.params_of(6055)['heal_cost'],9)
        self.assertEqual(items.params_of(7100)['heal_cost'],13)
        self.assertEqual(items.params_of(7101)['heal_cost'],15)


if __name__=='__main__':
    run_cases(MedicineDescriptions)
