"""Temporary model pause: no new drops, no use, no confiscation or balance changes."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.setdefault('LAVA_DB', ':memory:')
os.environ.pop('LAVA_DB_URL',None)

import accounts
import combat
import equipment_release
import inventory
import items
import mob_equipment_loot
import mob_weapon_loot
import mobs
import progression
from testkit import run_cases


class WeaponAvailability(unittest.TestCase):
    def fighter(self, type_id=26698):
        row=dict(uniq=12,char_id=7,type_id=type_id,root=items.FIRE_ARM,
                 slot=inventory.PRIMARY,brk=47,max_break_cur=60,ammo_count=9,ammo_type=6101)
        events=[]
        sess=NS(char_id=7,on_map=False,loc=NS(war=True),room=None,
                answer=events.append,send=lambda cmd,**kw:events.append((cmd,kw)),
                inv=NS(find=lambda _:row))
        f=NS(sess=sess,character=lambda:progression.Character(),
             rc=NS(room=NS(ws=False,broadcast=lambda *a,**kw:None)),
             dead=False,ap=60,aim=None,strike=None,eid=99,preparing=lambda:False,
             ack=lambda code:events.append(code),store=Mock())
        f.store.item.return_value=row
        f.c_ap=lambda:events.append(('c_ap',f.ap))
        return f,row,events

    def test_explicit_pause_is_exact_and_separate_from_retirement(self):
        self.assertEqual(set(items.TEMPORARILY_DISABLED_WEAPONS),{26692,26695,26698})
        for t, reason in items.TEMPORARILY_DISABLED_WEAPONS.items():
            self.assertTrue(reason)
            self.assertEqual(items.weapon_use_error(t),items.WEAPON_UNAVAILABLE)
            self.assertTrue(items.acquisition_blocked(t))
            self.assertFalse(items.out_of_game(t))
            self.assertIsNotNone(items.params_of(t))
        # Native MP-40, its modifications, collectible/event Schmeissers,
        # a quest firearm, an emitter and ordinary gold weapons stay usable.
        for t in (25389,25390,25392,25393,25395,25396,25398,25399,
                  5843,7803,7838,3728,1570,25566,25567,6229):
            self.assertIsNone(items.weapon_use_error(t),t)

    def test_released_drop_has_a_real_retail_witness_and_level_ceiling(self):
        for t in equipment_release.available_types():
            self.assertFalse(items.acquisition_blocked(t),t)
            self.assertTrue(any(t in items.stock_for(trader,loc)
                                and trader in equipment_release.sellers_at(loc)
                                for trader,loc in equipment_release.catalogue()[t]['sellers']),t)
        stats=NS(**vars(mobs.stats(365)))
        for kind in mob_equipment_loot.POUCHES:
            stats.weapon_class=kind;stats.ranged=kind!='knife'
            for level in (1,4,8,11,15,17,20,23):
                stats.level=level
                t=mob_weapon_loot.weapon_type(stats,263)
                if t is not None:
                    self.assertTrue(equipment_release.available(t),t)
                    self.assertLessEqual(inventory.item_level(t),min(level,17))
                    self.assertFalse(items.acquisition_blocked(t))
        for t in (26692,26695,26698,26242,45278):
            self.assertFalse(equipment_release.available(t),t)
        for t in items.TEMPORARILY_DISABLED_WEAPONS:
            self.assertFalse(mobs.droppable(t));self.assertFalse(mobs.one_of_droppable(t))
            self.assertFalse(mobs.quest_droppable(t))

    def test_retail_removal_revokes_an_approved_random_drop(self):
        equipment_release.available_types.cache_clear()
        self.addCleanup(equipment_release.available_types.cache_clear)
        with patch.object(items,'stock_for',return_value=[]):
            self.assertFalse(equipment_release.available_types())

    def test_desertman_keeps_its_actual_abri_seller_and_ordinary_drop(self):
        for t in range(10629,10634):
            self.assertIn(t,items.stock_for(1166,187))
            self.assertTrue(mob_equipment_loot.random_drop_allowed(t))
            self.assertIsNone(items.weapon_use_error(t))

    def test_removed_seller_cannot_keep_an_ordinary_drop_released(self):
        equipment_release.available_types.cache_clear()
        self.addCleanup(equipment_release.available_types.cache_clear)
        with patch.object(equipment_release,'sellers_at',return_value=frozenset()):
            self.assertFalse(equipment_release.available_types())

    def test_new_loot_tables_cannot_bypass_retail_or_the_level_17_ceiling(self):
        for t in (26692,26695,26698,26242,45278,6270,11489):
            self.assertFalse(mob_equipment_loot.random_drop_allowed(t),t)
        # Classifying old ordinary weapons must not lose paused types: this
        # filter suppresses legacy table drops before the new shared slot.
        self.assertEqual(mob_equipment_loot.without_equipment([(26698,1),(334,2)]),[(334,2)])

    def test_banned_attack_is_rejected_before_targeting_cost_or_database_lookup(self):
        for t in items.TEMPORARILY_DISABLED_WEAPONS:
            f,row,events=self.fighter(t);before=copy.deepcopy(row)
            combat.Fighter.use_fire(f,dict(obj='a',target='invalid'))
            self.assertEqual(events,[inventory.RES_REFUSED,items.WEAPON_UNAVAILABLE])
            self.assertEqual((f.ap,row),(60,before));f.store.item.assert_not_called()

    def test_already_aimed_or_direct_melee_attack_cannot_spend_resources(self):
        for method in ('fire','strike','direct'):
            f,row,events=self.fighter();before=copy.deepcopy(row)
            if method=='fire':combat.Fighter.fire_now(f,12,None,0,NS(num_shots=3),8)
            elif method=='strike':combat.Fighter.strike_now(f,None,0,(1,2),1,8,12)
            else:combat.Fighter.strike_with(f,row,None,0)
            self.assertIn(items.WEAPON_UNAVAILABLE,events)
            self.assertEqual((f.ap,row),(60,before))
            f.store.update_item.assert_not_called();f.store.delete_item.assert_not_called()

    def test_inventory_refuses_new_issue_without_a_database_write(self):
        store=Mock();inv=inventory.Inventory(NS(char_id=1),store)
        for t in items.TEMPORARILY_DISABLED_WEAPONS:
            with self.assertRaisesRegex(ValueError,items.WEAPON_UNAVAILABLE):inv.create(t)
        store.create_item.assert_not_called()
        for t in (6270,11489):
            self.assertTrue(items.acquisition_blocked(t))
            with self.assertRaises(ValueError):inv.create(t)

    def test_reload_and_its_delayed_completion_keep_both_ammunition_sources(self):
        f,row,events=self.fighter();f.sess.combat=f
        store=Mock();inv=inventory.Inventory(f.sess,store)
        ammo=dict(uniq=13,type_id=6101,root=items.AMMO,count=30)
        inv.find=lambda value:row if value=='gun' else ammo
        before=copy.deepcopy((row,ammo))
        inv.use_load(dict(obj='gun',target='ammo'))
        self.assertIn(items.WEAPON_UNAVAILABLE,events)
        events.clear();store.item.side_effect=[row,ammo]
        inv.finish_reload(dict(uniq=12,stack=13))
        self.assertIn(items.WEAPON_UNAVAILABLE,events)
        self.assertEqual((row,ammo),before);self.assertEqual(f.ap,60)
        store.update_item.assert_not_called();store.delete_item.assert_not_called()

    def test_equipping_and_hand_swap_are_refused_without_writing_either_item(self):
        for swap in (False,True):
            f,row,events=self.fighter();ch=progression.Character()
            ch.set_skill(progression.SHOOTING,20)
            sess=f.sess;sess.combat=f;sess.character=lambda:ch
            inv=inventory.Inventory(sess,Mock())
            row.update(slot=inventory.PRIMARY if swap else inventory.BAG)
            ordinary=dict(row,type_id=25566,uniq=13,slot=inventory.SECONDARY)
            inv.find=lambda _:ordinary if swap else row
            inv.in_slot=lambda _:row if swap else None
            inv.ss_move(dict(obj='a',**{'from':inventory.SECONDARY if swap else inventory.BAG,
                                     'to':inventory.PRIMARY}))
            self.assertIn(items.WEAPON_UNAVAILABLE,events)
            inv.store.update_item.assert_not_called()

    def test_historical_item_survives_database_reopen_and_login_inventory_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'history.sqlite'
            store=accounts.Store(str(path))
            aid,_=store.register('historical-model','test-only')
            cid,_=store.create_character(aid,'HistoricalModel',0,'1')
            ch=progression.Character.load(store,cid)
            ch.set_skill(progression.SHOOTING,20)
            for i in range(progression.SPECS):ch.set_spec(i,5)
            fields=inventory.new_fields(26698);root=fields.pop('root')
            fields.update(slot=inventory.PRIMARY,brk=47,max_break_cur=60,ammo_count=9,ammo_type=6101)
            old=store.create_item(cid,26698,root,**fields)  # Existing pre-pause item, not new issuance.
            ch.save(store);store.close()
            store=accounts.Store(str(path))
            try:
                loaded=progression.Character.load(store,cid)
                inv=inventory.Inventory(NS(char_id=cid,character=lambda:loaded),store)
                self.assertEqual(inv.over_level_to_bag(),[])
                self.assertEqual(store.item(old['uniq']),old)
            finally:store.close()


if __name__=='__main__':run_cases(WeaponAvailability)
