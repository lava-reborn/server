"""Bizon capacities and atomic conservation of historical loaded rounds."""
import contextlib
import unittest
from unittest.mock import patch

import test_mortimer_sales as fixtures
import inventory
import items
import magazine_migration as migration
import storage
from testkit import run_cases


class BizonMagazine(unittest.TestCase):
    give = fixtures.MortimerSales.give

    def setUp(self):
        fixtures.MortimerSales.setUp(self)

    def loaded(self, ammo=None, slot=inventory.BAG):
        row=self.give(26185)
        ammo=ammo or items.params_of(26185)['comp_array'][0]
        self.store.update_item(row['uniq'],ammo_count=128,ammo_type=ammo,slot=slot)
        return self.store.item(row['uniq'])

    def test_all_damage_magazine_variants_have_100_and_unmodified_have_64(self):
        self.assertEqual([items.static_info(t)[1]['clip_size'] for t in (26185,26186,26187)],[100,100,100])
        self.assertEqual([items.params_of(t)['clip_size'] for t in (25540,26177,26178)],[64,64,64])

    def test_legacy_rounds_keep_type_owner_container_and_total_idempotently(self):
        ammo_types=items.params_of(26185)['comp_array']
        for ammo,slot in ((ammo_types[0],inventory.BAG),(ammo_types[-1],inventory.BANK)):
            row=self.loaded(ammo,slot)
            changed,added=migration.normalize(self.store,self.cid,[row])
            self.assertEqual(changed[row['uniq']]['ammo_count'],100)
            self.assertEqual([(r['type_id'],r['count'],r['slot'],r['char_id']) for r in added],[(ammo,28,slot,self.cid)])
            self.assertEqual(100+added[0]['count'],128)
            self.assertEqual(migration.normalize(self.store,self.cid,[self.store.item(row['uniq'])]),({},[]))

    def test_failure_after_creating_ammo_rolls_back_both_rows(self):
        row=self.loaded()
        before=self.inv.rows()
        with patch.object(self.store,'update_item',side_effect=RuntimeError('magazine write failed')):
            with self.assertRaises(RuntimeError):
                migration.normalize(self.store,self.cid,[row])
        self.assertEqual(self.inv.rows(),before)

    def test_corrupt_magazine_is_preserved_without_blocking_valid_ones(self):
        for fields in (dict(ammo_count=129), dict(ammo_type=6055), dict(root=items.TRASH)):
            with self.subTest(fields=fields):
                bad = self.loaded()
                # root is intentionally immutable through Store.update_item;
                # inject historical DB corruption only in this test fixture.
                if 'root' in fields:
                    self.store.db.execute('UPDATE items SET root=? WHERE uniq=?',
                                          (fields['root'], bad['uniq']))
                else:
                    self.store.update_item(bad['uniq'], **fields)
                bad = self.store.item(bad['uniq'])
                good = self.loaded()
                with patch.object(migration.log, 'error') as error:
                    changed, added = migration.normalize(self.store, self.cid, [bad, good])
                self.assertEqual(self.store.item(bad['uniq']), bad)
                self.assertEqual(set(changed), {good['uniq']})
                self.assertEqual(sum(r['count'] for r in added), 28)
                self.assertEqual(error.call_args.args[1:], (bad['uniq'], self.cid))

    def test_invalid_magazine_dynamic_info_does_not_close_inventory(self):
        row = self.loaded()
        self.store.update_item(row['uniq'], ammo_count=129)
        before = self.inv.rows()
        self.frames.clear()
        with patch.object(migration.log, 'error') as error:
            self.inv.ss_get_di(dict(obj=inventory.oid_of(row)))
        error.assert_called_once()
        self.assertEqual(self.inv.rows(), before)
        self.assertEqual([p['ammo_count'] for c,p in self.frames if c=='ss_di_firearm'], [129])

    def test_locked_or_foreign_items_are_never_changed(self):
        row=self.loaded()
        self.assertEqual(migration.normalize(self.store,self.cid,[row],{row['uniq']}),({},[]))
        aid,_=self.store.register('otherbizon','secret')
        cid,_=self.store.create_character(aid,'OtherBizon',0,'1')
        self.assertEqual(migration.normalize(self.store,cid,[row]),({},[]))
        self.assertEqual(self.store.item(row['uniq'])['ammo_count'],128)

    def test_uncertain_commit_can_be_retried_without_duplicating_excess(self):
        row=self.loaded()
        original=storage.atomic
        @contextlib.contextmanager
        def uncertain(db):
            with original(db):
                yield db
            raise storage.CommitError('reply lost')
        with patch.object(storage,'atomic',uncertain):
            with self.assertRaises(storage.CommitError):
                migration.normalize(self.store,self.cid,[row])
        self.assertEqual(migration.normalize(self.store,self.cid,self.inv.rows()),({},[]))
        rows=[r for r in self.inv.rows() if r['type_id']==row['ammo_type']]
        self.assertEqual(sum(r['count'] for r in rows),28)

    def test_claimed_weapon_dynamic_info_reports_returned_rounds_and_100_loaded(self):
        row=self.loaded()
        self.frames.clear()
        self.inv.ss_get_di(dict(obj=inventory.oid_of(row)))
        self.assertEqual(self.store.item(row['uniq'])['ammo_count'],100)
        self.assertTrue(any(c=='ss_obj_status' and p['status']==1 for c,p in self.frames))
        self.assertEqual([p['ammo_count'] for c,p in self.frames if c=='ss_di_firearm'],[100])


if __name__ == '__main__':
    run_cases(BizonMagazine)
