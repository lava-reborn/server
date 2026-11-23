"""Legacy boss shields are wire-only; combat and private targets stay unchanged."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

import battle_balance
import bosses
import combat
import mobs
from testkit import run_cases


class BossPresentation(unittest.TestCase):
    def info(self, mob):
        fighter = NS(rc=NS(mobs={mob.eid: mob}))
        return combat.Fighter.mob_info(fighter, mob.eid)

    def mob(self, type_id, level=18, role='boss', **extra):
        return NS(eid=1, type_id=type_id, level=level,
                  stats=NS(level=level, role=role, hp_max=1000, sp_max=1200),
                  hp=700, sp=800, loot_level=16, xp_ledger={}, **extra)

    def test_abu_legacy_levels_are_fixed_for_all_viewers_and_stats_are_untouched(self):
        for type_id, shown in ((777, 21), (778, 21), (8620, 21), (1037, 23), (1038, 23)):
            mob = self.mob(type_id)
            before = deepcopy(mob.__dict__)
            for viewer_level in (1, 3, 16, 17):
                fighter = NS(rc=NS(mobs={mob.eid: mob}), level=viewer_level)
                self.assertEqual(combat.Fighter.mob_info(fighter, mob.eid), {'lvl': shown})
            self.assertEqual(mob.__dict__, before)
            self.assertEqual((mob.level, mob.stats.level), (18, 18))

    def test_other_legacy_boss_uses_the_pinned_record_or_original_type(self):
        source = battle_balance.data()
        fallback = next(int(t) for t, row in mobs.TYPES.items()
                        if row.get('role') == 'boss' and t not in source['mobs'])
        for type_id in (269, 270, 2103, fallback):
            mob = self.mob(type_id, level=4)
            index = source['mobs'].get(str(type_id))
            shown = (source['mob_records'][index]['level'] if index is not None
                     else mobs.TYPES[str(type_id)].get('level', 4))
            self.assertEqual(self.info(mob), {'lvl': max(1, shown)})
            self.assertEqual(mob.stats.level, 4)

    def test_prepared_sites_warehouse_and_private_targets_keep_their_actual_level(self):
        cases = [self.mob(777, _holding_prepared=True),
                 self.mob(next(iter(bosses.WAREHOUSE_MASTERS))),
                 self.mob(777, training_ground=NS()), self.mob(777, role='mob')]
        for mob in cases:
            with self.subTest(type_id=mob.type_id, role=mob.stats.role):
                self.assertEqual(self.info(mob), {'lvl': 18})

    def test_missing_mob_has_no_extra_info(self):
        self.assertEqual(combat.Fighter.mob_info(NS(rc=NS(mobs={})), 999), {})
        self.assertEqual(combat.Fighter.mob_info(NS(rc=None), 999), {})


if __name__ == '__main__':
    run_cases(BossPresentation)
