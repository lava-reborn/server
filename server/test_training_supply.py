"""Supply windows: paging, exact variants, replay and private inventory boundaries."""
import unittest
from unittest.mock import patch

import inventory
import items
from protocol import decode
from training import catalog as range_catalog
from training import character as range_character
from training import session as tg
from training import items as copies
from training import supply as supply
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

    async def test_archive_placeholders_keep_ids_and_are_issued_only_at_archive(self):
        g = self.enter()
        self.assertEqual(len(supply.ARCHIVE_SOURCES), 28)
        for source in supply.ARCHIVE_SOURCES:
            self.assertIn(source, range_catalog.item_catalogue())
            self.assertTrue(copies.is_copy(copies.copy_type(source)))
            self.assertIn(source, supply.sources('archive'))
        for source in (6542, 31097, 6228, 3552):
            self.assertIn(source, supply.sources('specialist'))
            self.assertNotIn(source, supply.sources('armoury'))
        self.approach_shop(g, 'armoury')
        before = list(g.clone.inv.rows())
        with self.assertRaises(ValueError):
            supply.change(g, dict(sequence=1, source=4329, count=1))
        self.assertEqual(g.clone.inv.rows(), before)
        self.approach_shop(g, 'archive')
        supply.change(g, dict(sequence=1, source=4329, count=1))
        self.assertTrue(any(copies.source_type(row['type_id'])==4329 for row in g.clone.inv.rows()))
        self.unchanged()

    async def test_available_levels_match_each_station_filter_and_profile(self):
        from dataclasses import replace
        g=self.enter()
        for simulator in (False,True):
            g.rules=replace(g.rules,simulator_formulas=simulator)
            for station in supply.STATIONS:
                g.context=station
                for line in ('all','A','P','G','C'):
                    params=dict(request_id=1,line=line)
                    expected=sorted({e.level for e in supply.filtered(station,params,g)
                                     if e.level>0 and copies.available(e.source,simulator)})
                    supply.catalogue(g,params)
                    _,packet=decode(self.s.writer.frames[-1][:-1])
                    self.assertEqual(packet['available_levels'],expected,(station,line,simulator))
                    if expected:
                        supply.catalogue(g,dict(params,level=expected[-1]))
                        _,packet=decode(self.s.writer.frames[-1][:-1])
                        self.assertGreater(packet['total'],0)
                        self.assertTrue(all(supply.index(simulator)[t].level==expected[-1] for t in packet['ids']))
            g.context='armoury'
            supply.catalogue(g,dict(request_id=1,category='set',line='G'))
            _,packet=decode(self.s.writer.frames[-1][:-1])
            expected=sorted({r['level'] for r in supply.set_catalogue().values()
                             if r['variant']=='G' and all(copies.available(t,simulator) for t in r['members'].values())})
            self.assertEqual(packet['available_levels'],expected)
        self.unchanged()

    async def test_supply_announces_live_spas_before_native_creation_and_dynamic_info(self):
        g = self.enter()
        self.approach_shop(g)
        self.s.writer.frames.clear()
        self.request(g, 'supply_get', source=26032, sequence=1, count=1)
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        live_index = next(i for i, (cmd, data) in enumerate(frames) if cmd == 'tg' and data.get('op') == 'inventory')
        status_index = next(i for i, (cmd, data) in enumerate(frames) if cmd == 'ss_obj_status')
        di_index = next(i for i, (cmd, data) in enumerate(frames) if cmd == 'ss_di_firearm')
        self.assertLess(live_index, status_index)
        self.assertLess(status_index, di_index)
        oid = frames[di_index][1]['obj']
        self.assertIn(oid, frames[live_index][1]['live_oids'])
        self.unchanged()

    async def test_every_item_has_one_station_and_all_premium_variants_have_correct_class(self):
        self.enter()
        all_sources = [t for station in supply.STATIONS for t in supply.sources(station)]
        self.assertEqual(set(all_sources), set(range_catalog.item_catalogue()))
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
            profile = range_character.preset(level)
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

    async def test_first_entry_is_empty_level_one_and_saved_range_progress_is_retained(self):
        g = self.enter()
        self.assertEqual(g.clone.char.level, 1)
        self.assertEqual(g.profile['specs'], [-1] * len(g.profile['specs']))
        self.assertFalse(g.profile['gear'])
        self.assertFalse(g.clone.inv.rows())
        profile = range_character.preset(8)
        g.configure_player(profile)
        g.save_settings()
        g.exit(notify=False)
        restored = tg.Ground(self.s)
        try:
            self.assertEqual(restored.clone.char.level, 8)
            self.assertFalse(restored.clone.inv.rows())
        finally:
            restored.exit(notify=False)
        self.unchanged()

    async def test_complete_set_preview_issue_and_replay(self):
        g = self.enter()
        self.approach_shop(g, 'armoury')
        listing = self.request(g, 'supply_list', category='set', line='G', request_id=1)
        self.assertEqual(listing['bundle'], 1)
        key = listing['ids'][0]
        preview = self.request(g, 'supply_variants', source=key, bundle=1, request_id=2)
        record = supply.selected_set(g, key)
        self.assertEqual(len(preview['types']), len(record['members']))
        self.assertEqual(set(preview['ids']), {key})
        self.request(g, 'supply_get', source=key, bundle=1, sequence=1)
        rows = [dict(row) for row in g.clone.inv.rows()]
        self.assertEqual({copies.profile_source(row['type_id']) for row in rows}, set(record['members'].values()))
        self.assertTrue(all(row['slot'] == inventory.BAG for row in rows))
        self.request(g, 'supply_get', source=key, bundle=1, sequence=1)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], rows)
        self.unchanged()

    async def test_set_failure_rolls_back_all_parts_and_sequence(self):
        g = self.enter()
        self.approach_shop(g, 'armoury')
        key = next(iter(supply.set_catalogue()))
        before = [dict(row) for row in g.clone.inv.rows()]
        real = g.clone.inv.create
        count = 0
        def fail_second(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('injected failure')
            return real(*args, **kwargs)
        frames = len(self.s.writer.frames)
        with patch.object(g.clone.inv, 'create', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.request(g, 'supply_get', source=key, bundle=1, sequence=1)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.assertEqual(g.supply_sequence, 0)
        self.assertEqual(len(self.s.writer.frames), frames)
        with patch.object(g.clone.inv, 'carry_limit', return_value=1):
            with self.assertRaises(ValueError):
                self.request(g, 'supply_get', source=key, bundle=1, sequence=1)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()], before)
        self.approach_shop(g, 'medical')
        with self.assertRaises(ValueError):
            self.request(g, 'supply_get', source=key, bundle=1, sequence=1)
        self.unchanged()

    async def test_ammo_compatibility_filter_and_catalogue_classification(self):
        g = self.enter()
        self.approach_shop(g, 'supplies')
        self.assertFalse(supply.filtered('supplies', dict(detail='held'), g))
        gun = g.clone.inv.create(copies.copy_type(26075), slot=inventory.PRIMARY)
        expected = {copies.profile_source(t) for t in items.params_of(gun['type_id'])['comp_array']}
        rows = supply.filtered('supplies', dict(detail='held'), g)
        self.assertEqual({row.source for row in rows}, expected & supply.sources('supplies'))
        self.assertTrue(all(row.category == 'ammo' for row in rows))
        self.assertTrue(supply.filtered('supplies', dict(detail='w1'), g))
        self.assertEqual(supply.search_key('9 мм. НАТO'), supply.search_key('9мм НАТO'))
        self.assertEqual(supply.index()[1535].category, 'legacy')
        self.assertNotIn(1535, supply.sources('medical'))
        self.assertEqual(supply.index()[4329].category, 'souvenir')
        self.assertNotIn(4329, supply.sources('weapons'))
        self.assertTrue(all(row.category in ('medicine', 'event_medicine')
                            for row in supply.filtered('medical', dict(detail='battle'), g)))
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingSupply)
