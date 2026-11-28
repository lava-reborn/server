"""INTUX consent binds a real projected reward to one item and one session."""
import copy
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

import effects
import intux_confirmation as consent
import inventory
from testkit import run_cases


class IntuxConfirmation(unittest.TestCase):
    def setUp(self):
        self.frames, self.messages = [], []
        self.now, self.calendar, self.residence = 1000, 1.5, 2
        self.enterContext(patch.object(consent.time, 'monotonic', lambda:self.now))
        self.enterContext(patch.object(consent.progression, 'combat_calendar_multiplier', lambda:self.calendar))
        self.session = NS(char_id=1, room=object(), inv=NS(locked=set()),
                          send=lambda cmd, **fields:self.frames.append((cmd,fields)), answer=self.messages.append)
        self.session.effects = effects.Effects(self.session)
        self.session.effects.clock = lambda:self.now
        self.fighter = NS(sess=self.session, cell=100, action_revision=2,
                          character=lambda:NS(premium_level=lambda:self.residence),
                          ack=lambda res:self.session.send('cmdAck',res=res))
        self.row=dict(uniq=123,type_id=3561,char_id=1,use_count=1,count=1,slot=inventory.BAG)

    def quote(self):
        self.assertFalse(consent.guard(self.fighter,self.row,dict(xp_stage='quote')))
        return self.frames[-1][1]

    def accept(self, quote=None):
        quote=quote if quote is not None else self.quote()
        return consent.guard(self.fighter,self.row,dict(xp_token=quote['xp_token']))

    def test_quote_does_not_spend_or_start_an_action_and_warns_of_real_overflow(self):
        before=copy.deepcopy(self.row)
        quote=self.quote()
        self.assertEqual(quote['xp_warning'],1)
        self.assertIn('+150%',quote['xp_message'])
        self.assertIn('+100%',quote['xp_message'])
        self.assertEqual((self.row,self.fighter.action_revision),(before,2))
        self.assertIsNone(getattr(self.session,'_intux_consent',None))

    def test_exactly_two_times_needs_no_dialog_and_replacement_is_not_stacked(self):
        self.residence=0;self.row['type_id']=3114
        self.assertEqual(self.quote()['xp_warning'],0)
        self.session.effects.active['experience_up']=effects.Active(3112,900,1100)
        self.row['type_id']=3113;self.residence=2
        self.assertAlmostEqual(consent.projection(self.fighter,3113)[0][0],2.1)
        self.assertEqual(self.quote()['xp_warning'],1)

    def test_no_confirmation_or_cancelling_before_apply_keeps_the_dose(self):
        self.assertFalse(consent.guard(self.fighter,self.row,{}))
        self.quote()  # Cancel sends no application request at all.
        self.assertEqual(self.row['use_count'],1)
        self.assertIsNone(getattr(self.session,'_intux_consent',None))

    def test_token_is_one_use_and_bound_to_the_exact_item_room_action_and_bonuses(self):
        for field in ('item','room','revision','cell','residence','effect'):
            with self.subTest(field=field):
                quote=self.quote()
                if field=='item':self.row['uniq']+=1
                elif field=='room':self.session.room=object()
                elif field=='revision':self.fighter.action_revision+=1
                elif field=='cell':self.fighter.cell+=1
                elif field=='residence':self.residence=1
                else:self.session.effects.active['other']=effects.Active(3473,900,1200)
                self.assertFalse(self.accept(quote))
                self.residence=2
        self.session.effects.active.clear()
        quote=self.quote();self.assertTrue(self.accept(quote));self.assertFalse(self.accept(quote))

    def test_expired_quote_and_replaced_quote_cannot_authorise_a_dose(self):
        old=self.quote();self.quote()
        self.assertFalse(self.accept(old))
        quote=self.quote();self.now+=consent.QUOTE_SECONDS+1
        self.assertFalse(self.accept(quote))

    def test_stronger_current_intux_and_locked_or_foreign_doses_are_refused(self):
        self.session.effects.active['experience_up']=effects.Active(3561,900,1200)
        self.row['type_id']=3112
        self.assertFalse(consent.guard(self.fighter,self.row,dict(xp_stage='quote')))
        self.assertEqual(self.frames[-1][1]['res'],inventory.RES_REFUSED)
        self.session.effects.active.clear();self.row['type_id']=3561
        for field,value in (('char_id',2),('slot',inventory.BANK),('use_count',0)):
            original=self.row[field];self.row[field]=value
            self.assertFalse(consent.guard(self.fighter,self.row,dict(xp_stage='quote')))
            self.row[field]=original
        self.session.inv.locked.add(self.row['uniq'])
        self.assertFalse(consent.guard(self.fighter,self.row,dict(xp_stage='quote')))

    def test_weekend_start_during_use_cancels_before_consumption(self):
        self.calendar=1;self.assertTrue(consent.guard(self.fighter,self.row,{}))
        self.calendar=1.5
        self.assertFalse(consent.finish_allowed(self.fighter,self.row))
        self.assertEqual(self.frames[-1],('actionCancel',dict(release=1)))
        self.assertEqual(self.row['use_count'],1)

    def test_confirmed_budget_survives_lower_bonuses_but_not_an_increase(self):
        self.residence=1;self.assertTrue(self.accept())
        self.residence=2;self.assertFalse(consent.finish_allowed(self.fighter,self.row))
        self.assertTrue(self.accept());self.residence=1
        self.assertTrue(consent.finish_allowed(self.fighter,self.row))
        self.assertFalse(consent.finish_allowed(self.fighter,self.row))

    def test_other_consumables_and_private_templates_keep_their_original_path(self):
        self.row['type_id']=3473
        self.assertTrue(consent.guard(self.fighter,self.row,{}))
        self.assertTrue(consent.finish_allowed(self.fighter,self.row))


class IntuxConsumption(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import accounts
        import progression
        from testkit import healing_fixture
        # Honour LAVA_DB_URL so CI checks the same transaction on Postgres.
        self.store=accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        suffix=uuid.uuid4().hex[:8]
        aid,_=self.store.register('intux-'+suffix,'test-only')
        cid,_=self.store.create_character(aid,'Intux'+suffix,0,'1')
        self.ch=progression.Character.load(self.store,cid)
        self.ch.set_skill(progression.SHOOTING,20)
        self.ch.premium=2
        self.f,self.old_ch,self.room,_=healing_fixture(3561)
        self.f.character=lambda:self.ch;self.f.store=self.store
        self.f.cell=100;self.f.action_revision=0;self.f.present=lambda rc:True
        self.s=self.f.sess;self.s.char_id=cid;self.s.character=lambda:self.ch
        self.s.loc=NS(width=80,height=80)
        self.s.inv=inventory.Inventory(self.s,self.store)
        self.s.inv.carry_limit=lambda:1_000_000
        self.s.effects=effects.Effects(self.s)
        self.s.effects.clock=lambda:1000
        self.s.effects.refresh=lambda **kw:None  # Persistence/consumption remain real.
        self.frames=[]
        self.s.send=lambda cmd,**fields:self.frames.append((cmd,fields))
        self.f.ack=lambda res:self.s.send('cmdAck',res=res)
        self.calendar=1.5
        self.enterContext(patch.object(consent.progression,'combat_calendar_multiplier',lambda:self.calendar))
        self.row=self.s.inv.create(3561)

    def agree(self):
        self.assertFalse(consent.guard(self.f,self.row,dict(xp_stage='quote')))
        token=self.frames[-1][1]['xp_token']
        self.assertTrue(consent.guard(self.f,self.row,dict(xp_token=token)))

    async def test_real_dose_and_persistent_effect_are_untouched_until_agreement_then_spent_once(self):
        before=self.store.item(self.row['uniq'])
        effects.activate(self.f,self.row['uniq'],self.f,0)
        self.assertEqual(self.store.item(self.row['uniq']),before)
        self.assertEqual(self.store.effects_for(self.s.char_id),[])
        self.agree();effects.activate(self.f,self.row['uniq'],self.f,0)
        remaining=self.store.item(self.row['uniq'])
        self.assertEqual(remaining['use_count'] if remaining else 0,before['use_count']-1)
        self.assertEqual([r['source'] for r in self.store.effects_for(self.s.char_id)],[3561])
        effects.activate(self.f,self.row['uniq'],self.f,0)
        self.assertEqual(len(self.store.effects_for(self.s.char_id)),1)

    async def test_weekend_boundary_during_use_never_consumes_an_unapproved_dose(self):
        self.calendar=1;self.assertTrue(consent.guard(self.f,self.row,{}))
        self.calendar=1.5
        before=self.store.item(self.row['uniq'])
        effects.activate(self.f,self.row['uniq'],self.f,0)
        self.assertEqual(self.store.item(self.row['uniq']),before)
        self.assertEqual(self.store.effects_for(self.s.char_id),[])

    async def test_inventory_failure_rolls_back_the_persistent_bonus_and_dose_together(self):
        self.store.update_item(self.row['uniq'],use_count=1)
        self.row=self.store.item(self.row['uniq']);self.agree()
        with patch.object(self.store,'delete_item',side_effect=RuntimeError('inventory failure')):
            with self.assertRaises(RuntimeError):effects.activate(self.f,self.row['uniq'],self.f,0)
        self.assertEqual(self.store.item(self.row['uniq'])['use_count'],1)
        self.assertEqual(self.store.effects_for(self.s.char_id),[])
        self.assertFalse(self.s.effects.active)


if __name__=='__main__':
    run_cases(IntuxConfirmation,IntuxConsumption)
