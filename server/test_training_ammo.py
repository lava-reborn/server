"""Bidirectional assortment checks and real in-memory loading of each ammo type."""
import copy
import unittest
from unittest.mock import patch

import combat
import inventory
import items
import training_ammo as support
import training_ground as training
import training_items as copies
import training_layout as layout
import training_shop as shop
import test_training_ground as fixtures
from protocol import decode


class TrainingAmmunition(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.TrainingGround.asyncSetUp
    asyncTearDown=fixtures.TrainingGround.asyncTearDown
    enter=fixtures.TrainingGround.enter
    unchanged=fixtures.TrainingGround.unchanged

    def graph(self):
        stock={t for post in layout.POSTS for t in shop.stock(post)}
        guns={t for t in stock if items.root_of(t)==items.FIRE_ARM}
        ammo={t for t in stock if items.root_of(t)==items.AMMO}
        return guns,ammo

    async def test_each_issued_weapon_and_each_issued_ammo_has_an_available_partner(self):
        self.enter();guns,ammo=self.graph();used=set()
        for gun in guns:
            linked=items.params_of(gun)['comp_array']
            self.assertTrue(linked,gun)
            self.assertTrue(set(linked)<=ammo,gun)
            self.assertTrue(all(copies.is_copy(r) for r in linked))
            used.update(linked)
        self.assertEqual(used,ammo)
        self.unchanged()

    async def test_previously_unmatched_rounds_are_retained_and_now_have_weapons(self):
        self.enter();guns,ammo=self.graph()
        previous={3727,6176,6177,6178,6180,6185,6187,6191,6193,6194,6196,6197,6198}
        self.assertTrue({copies.copy_type(source) for source in previous}<=ammo)
        for source in previous:
            self.assertTrue(any(copies.copy_type(source) in items.params_of(gun)['comp_array'] for gun in guns),source)

    async def test_each_ammo_type_actually_loads_without_loss_using_ordinary_reload_transaction(self):
        g=self.enter();guns,ammo=self.graph()
        for rounds in sorted(ammo):
            source_gun=next(gun for gun in sorted(guns) if rounds in items.params_of(gun)['comp_array'])
            gun=g.clone.inv.create(source_gun,slot=inventory.PRIMARY)
            clip=items.params_of(source_gun)['clip_size']
            count=clip+3
            stack=g.clone.inv.create(rounds,count)
            with patch.object(combat.Fighter,'schedule_action') as schedule:
                g.clone.inv.use_load(dict(obj=inventory.oid_of(gun),target=inventory.oid_of(stack)))
                self.assertTrue(schedule.called,(source_gun,rounds))
            g.clone.inv.reloaded(gun['uniq'])
            loaded=g.store.item(gun['uniq']);remaining=g.store.item(stack['uniq'])
            self.assertEqual((loaded['ammo_type'],loaded['ammo_count']),(rounds,clip))
            self.assertEqual(remaining['count'],3)
            g.store.delete_item(gun['uniq']);g.store.delete_item(stack['uniq'])
        self.unchanged()

    async def test_incompatible_cartridges_are_still_refused_without_consumption(self):
        g=self.enter()
        gun=g.clone.inv.create(copies.copy_type(3728),slot=inventory.PRIMARY)
        stack=g.clone.inv.create(copies.copy_type(6092),10)
        before=[dict(row) for row in g.clone.inv.rows()]
        self.s.writer.frames.clear()
        g.clone.inv.use_load(dict(obj=inventory.oid_of(gun),target=inventory.oid_of(stack)))
        frames=[decode(frame[:-1]) for frame in self.s.writer.frames]
        self.assertIn(('cmdAck',dict(res=inventory.RES_WRONG_AMMO)),frames)
        self.assertEqual([dict(row) for row in g.clone.inv.rows()],before)
        self.unchanged()

    async def test_support_weapons_are_at_special_vendor_separate_from_contraband(self):
        self.enter()
        special=layout.BY_KEY['experimental']
        offered=set(shop.stock(special));other=set(shop.stock(layout.BY_KEY['special']))
        self.assertTrue({copies.copy_type(source) for source in support.SPECIAL_WEAPONS}<=offered)
        self.assertTrue(offered.isdisjoint(other))
        for post in layout.POSTS:
            if post.category=='weapon':self.assertTrue(offered.isdisjoint(shop.stock(post)))

    async def test_SB_variants_only_extend_matching_calibres(self):
        self.enter();guns,_ammo=self.graph()
        for source in (25562,43338,43341):
            self.assertEqual(items.params_of(copies.copy_type(source))['comp_array'],[copies.copy_type(6188)])
        for source in (6176,6177,6178,6180,6185,6187):
            prefix=items.catalogue()[source][1].removesuffix('_SB_G')+'_'
            for gun in guns:
                linked=items.params_of(gun)['comp_array']
                if copies.copy_type(source) not in linked:continue
                self.assertTrue(any(r!=copies.copy_type(source) and items.catalogue()[copies.source_type(r)][1].startswith(prefix) for r in linked))

    async def test_preparation_guard_refuses_empty_wrong_and_orphan_ammunition_links(self):
        self.enter()
        valid={1:('ss_si_firearm',dict(comp_array=[2])),2:('ss_si_ammo',{})}
        roots={1:items.FIRE_ARM,2:items.AMMO}
        copies.validate_ammunition(valid,roots)
        for linked in ([],[3],[1]):
            bad=copy.deepcopy(valid);bad[1][1]['comp_array']=linked
            with self.assertRaises(ValueError):copies.validate_ammunition(bad,roots)
        extra=copy.deepcopy(valid);extra[3]=('ss_si_ammo',{})
        with self.assertRaises(ValueError):copies.validate_ammunition(extra,roots|{3:items.AMMO})

    async def test_every_offered_ammo_has_valid_experimental_combat_modifiers(self):
        g=self.enter();_guns,ammo=self.graph()
        weapon=combat.Weapon(1,100,120,1,5,10,1,.1,5,1,2,sdmin=10,sdmax=20)
        for rounds in ammo:
            with self.subTest(rounds=rounds):
                result=g.rules.weapon(weapon,items.params_of(rounds))
                self.assertGreater(result.max_range,0)
                self.assertGreaterEqual(result.dmax,result.dmin)
                self.assertGreaterEqual(result.sdmax,result.sdmin)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingAmmunition)
