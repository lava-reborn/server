"""Bounded personal rule records; ownership, persistence and failure safety."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from training import profiles as profiles
from training import session as tg
import test_training_ground as fixtures
import test_training_resume as resume

class PersonalProfiles(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.TrainingGround.asyncSetUp
    asyncTearDown=resume.TrainingResume.asyncTearDown
    enter=fixtures.TrainingGround.enter
    unchanged=fixtures.TrainingGround.unchanged
    next_session=resume.TrainingResume.next_session
    approach_shop=fixtures.TrainingGround.approach_shop

    def save(self,g,name='Мой тест',key='',rules=None):
        rules=rules or profiles.catalogue()[0].rules
        profiles.manage(g,'profile_save',dict(name=name,key=key,base=profiles.selected(rules).key,values=rules.values()))
        return next(p for p in g.personal_profiles if p.title==name)

    async def test_crud_survives_reconnect_without_changing_real_character(self):
        g=self.enter();self.approach_shop(g,'computer')
        original=g.rules
        record=self.save(g,rules=replace(original,health=2))
        self.assertEqual(g.rules,original) # Saving is not applying.
        self.assertEqual(record.rules.health,2)
        edited=self.save(g,'Другой',record.key,replace(original,health=3))
        self.assertEqual(len(g.personal_profiles),1)
        g.exit(notify=False,suspend=True)
        self.assertTrue(tg.resume(self.next_session()))
        g=self.s.training_ground;g.clone.cmd_lenter({});self.approach_shop(g,'computer')
        self.assertEqual(g.personal_profiles[0].rules.health,3)
        g.last_request=0
        g.request(dict(op='rules',token=g.token,profile=edited.key,values=edited.rules.values()))
        self.assertEqual(g.rules.health,3)
        profiles.manage(g,'profile_delete',dict(key=edited.key))
        self.assertFalse(g.personal_profiles)
        self.assertEqual(g.rules.health,3)
        self.assertEqual(profiles.payload(g.rules)['profile_selected'],0)
        self.unchanged()

    async def test_forged_keys_limits_and_failed_write_preserve_everything(self):
        g=self.enter();self.approach_shop(g,'computer');record=self.save(g)
        for key in ('baseline-v1','user-0000000000000000'):
            with self.assertRaises(ValueError):profiles.manage(g,'profile_delete',dict(key=key))
            with self.assertRaises(ValueError):self.save(g,key=key)
        with self.assertRaises(ValueError):self.save(g) # Duplicate name.
        with self.assertRaises(ValueError):self.save(g,'bad;name=@x@')
        before=g.personal_profiles;saved=self.store.training_profile(self.s.char_id)
        with patch.object(self.store,'save_training_profile',side_effect=RuntimeError('disk')):
            with self.assertRaises(ValueError):self.save(g,'Не сохранится')
            with self.assertRaises(ValueError):profiles.manage(g,'profile_delete',dict(key=record.key))
        self.assertEqual(g.personal_profiles,before)
        self.assertEqual(self.store.training_profile(self.s.char_id),saved)
        for i in range(1,profiles.MAX_PERSONAL):self.save(g,'Профиль '+str(i))
        with self.assertRaises(ValueError):self.save(g,'Лишний')
        self.assertLess(len(str(self.store.training_profile(self.s.char_id))),16384)
        with self.assertRaises(ValueError):profiles.resolve(record.rules.values(),record.key,())
        with patch.object(g,'phase','fight'):
            with self.assertRaises(ValueError):profiles.manage(g,'profile_delete',dict(key=record.key))
        self.unchanged()
