"""Supply windows: paging, exact variants, replay and private inventory boundaries."""
import unittest
from unittest.mock import patch

import inventory
import items
from protocol import decode
import training_ground as tg
import training_items as copies
import training_supply as supply
import test_training_ground as fixtures


class TrainingSupply(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    approach_shop = fixtures.TrainingGround.approach_shop
    supply = fixtures.TrainingGround.supply

    def request(self, ground, op, **params):
        ground.last_request = ground.last_catalogue_request = 0
        ground.request(dict(op=op, token=ground.token, **params))
        return decode(self.s.writer.frames[-1][:-1])[1]

    async def test_every_item_has_one_station_and_all_premium_variants_have_correct_class(self):
        self.enter()
        all_sources = [t for station in supply.STATIONS for t in supply.sources(station)]
        self.assertEqual(set(all_sources), set(tg.item_catalogue()))
        self.assertEqual(len(all_sources), len(set(all_sources)))
        for source, entry in supply.index().items():
            if items.root_of(copies.copy_type(source)) == items.FIRE_ARM:
                self.assertEqual(entry.weapon_class, items.params_of(copies.copy_type(source))['weapon_type'])
        self.assertEqual(supply.index()[40175].weapon_class, items.MACHINEGUN)
        self.assertTrue(supply.index()[24994].upgrade)
        self.assertIn('КС', supply.index()[6092].name)
        self.assertTrue(all(supply.index()[t].category == 'experimental_weapon' for t in copies.PROTOTYPES))

    async def test_pages_group_models_but_variants_keep_every_upgrade_and_line(self):
        g = self.enter()
        self.approach_shop(g)
        expected = supply.filtered('weapons', dict(wclass=4, line='P'))
        covered = set()
        models = set()
        page = 0
        while True:
            frame = self.request(g, 'supply_list', wclass=4, line='P', request_id=page+1, page=page)
            self.assertLessEqual(len(frame['ids']), supply.PAGE_SIZE)
            for source in frame['ids']:
                self.assertNotIn(supply.model_key(supply.index()[source]), models)
                models.add(supply.model_key(supply.index()[source]))
                variants = self.request(g, 'supply_variants', source=source, request_id=100+page)
                self.assertEqual(len(variants['ids']), len(variants['types']))
                covered.update(variants['ids'])
                self.assertTrue(all(supply.index()[t].line == 'P' for t in variants['ids']))
            if (page+1)*supply.PAGE_SIZE >= frame['total']:
                break
            page += 1
        self.assertEqual(covered, {e.source for e in expected})
        self.assertIn(40175, covered)

    async def test_same_request_cannot_issue_twice_and_old_sequence_cannot_return_again(self):
        g = self.enter()
        self.approach_shop(g)
        source = next(iter(supply.sources('weapons')))
        self.request(g, 'supply_get', source=source, sequence=1, count=1)
        before = [dict(r) for r in g.clone.inv.rows()]
        self.request(g, 'supply_get', source=source, sequence=1, count=1)
        self.assertEqual([dict(r) for r in g.clone.inv.rows()], before)
        row = next(r for r in before if r['type_id'] == copies.copy_type(source))
        self.request(g, 'supply_return', source=inventory.oid_of(row), sequence=2, count=1)
        self.request(g, 'supply_get', source=source, sequence=1, count=1)
        self.assertFalse(g.store.item(row['uniq']))
        self.unchanged()

    async def test_no_access_with_wrong_token_wrong_station_in_fight_or_to_equipped_item(self):
        g = self.enter()
        self.approach_shop(g, 'medical')
        source = next(iter(supply.sources('weapons')))
        with self.assertRaises(ValueError):
            self.request(g, 'supply_get', source=source, sequence=1)
        with self.assertRaises(ValueError):
            g.request(dict(op='supply_list', token='forged', request_id=1))
        self.approach_shop(g)
        row = g.clone.inv.create(copies.copy_type(source), slot=inventory.PRIMARY)
        with self.assertRaises(ValueError):
            self.request(g, 'supply_return', source=inventory.oid_of(row), count=1, sequence=1)
        g.phase = 'fight'
        with self.assertRaises(ValueError):
            self.request(g, 'supply_get', source=source, sequence=1)
        g.phase = 'ready'
        self.assertIsNotNone(g.store.item(row['uniq']))
        self.unchanged()

    async def test_range_carry_limit_is_advertised_and_does_not_change_owner(self):
        normal_limit = self.s.char.max_weight()
        g = self.enter()
        for level in (1, 12, 20):
            profile = tg.preset(level)
            g.configure_player(profile)
            self.assertEqual(g.clone.inv.carry_limit(), 150_000)
            self.assertEqual(g.clone.char.rp_info()['max_weight'], 150_000)
        self.assertEqual(self.s.char.max_weight(), normal_limit)
        g.exit(notify=False)
        self.assertEqual(self.s.char.max_weight(), normal_limit)
        self.unchanged()

    async def test_supply_accepts_exactly_150kg_and_refuses_one_gram_over(self):
        g = self.enter()
        self.approach_shop(g)
        source = next(t for t in supply.sources('weapons')
                      if items.params_of(copies.copy_type(t)).get('weight', 0) > 0)
        weight = items.params_of(copies.copy_type(source))['weight']
        before = len(g.clone.inv.rows())
        with patch.object(g.clone.inv, 'total_weight', return_value=150_000 - weight):
            self.supply(g, source)
        self.assertEqual(len(g.clone.inv.rows()), before + 1)
        snapshot = [dict(row) for row in g.clone.inv.rows()]
        with patch.object(g.clone.inv, 'total_weight', return_value=150_001 - weight):
            with self.assertRaises(ValueError):
                self.supply(g, source)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], snapshot)
        self.unchanged()

    async def test_bag_is_paged_and_has_quantities_without_equipped_objects(self):
        g = self.enter()
        self.approach_shop(g, 'supplies')
        source = next(t for t in supply.sources('supplies') if items.root_of(t) == items.AMMO)
        self.supply(g, source, 25)
        frame = self.request(g, 'supply_bag', request_id=1, page=0)
        self.assertLessEqual(len(frame['ids']), supply.PAGE_SIZE)
        self.assertIn(25, frame['maximum'])
        self.assertTrue(all(g.clone.inv.find(oid)['slot'] == inventory.BAG for oid in frame['ids']))
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingSupply)
