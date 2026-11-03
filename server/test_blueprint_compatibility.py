"""Real recipes, in-memory transactional hand-ins and personal quest rewards."""
import copy
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import accounts
import barter
import combat
import craft
import inventory
import items
import mail
import progression
import quests
import server
import upgrader
import world
from test_quest_state import session


TARGETS = (26061, 26062, 26074, 26075, 25540, 26177)


class BlueprintCompatibility(unittest.TestCase):
    def recipe(self, gun):
        return next(quests.get(t) for t, r in craft.rows().items()
                    if r.get('family') == 'upgrade' and r.get('gun') == gun
                    and r.get('effect') == 'damage_clipsize')

    def test_every_available_upgrade_accepts_its_blueprint_and_only_same_tier_alias(self):
        count = doubles = 0
        for t, rec in craft.rows().items():
            if rec.get('family') != 'upgrade':
                continue
            q = quests.get(t)
            if q is None or quests.acquisition_blocked(q):
                continue
            count += 1
            for bp in craft.blueprint_variants(rec['blueprint']):
                with self.subTest(quest=t, blueprint=bp):
                    have = {rec['gun']: 1, bp: 1}
                    self.assertTrue(q.is_complete(q.bag_progress(have)))
                    self.assertEqual(craft.quest_inputs(q, have), [(rec['gun'], 1), (bp, 1)])
                    parsed = craft.mod_of(rec['mod'])
                    if parsed is None:
                        families = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'firearm_families.json').read_text(encoding='utf-8'))['lines']
                        self.assertTrue(any(f['members'].get(rec['line']) == rec['gun']
                                            and f['members'].get(rec['line'] + ':' + rec['effect']) == rec['mod']
                                            for f in families.values()), t)
                    else:
                        self.assertEqual(parsed, (rec['gun'], rec['effect']))
            if len(craft.blueprint_variants(rec['blueprint'])) > 1:
                doubles += 1
                wrong = 37637 if rec['level'] != 11 else 37638
                self.assertFalse(q.is_complete(q.bag_progress({rec['gun']: 1, wrong: 1})))
        self.assertGreater(count, 300)
        self.assertGreater(doubles, 20)

    def test_all_six_requested_models_have_double_recipes(self):
        for gun in TARGETS:
            q = self.recipe(gun)
            rec = craft.rows()[q.type]
            self.assertTrue(q.give)
            self.assertEqual(len(craft.blueprint_variants(rec['blueprint'])), 2)
            base = items.params_of(gun)
            mod = items.params_of(rec['mod'])
            self.assertGreater(mod['clip_size'], base['clip_size'])
            self.assertTrue(all(b >= a for a, b in zip(base['h_damage_max'], mod['h_damage_max'])))

    def test_double_blueprints_deliver_the_declared_ten_percent_damage(self):
        checked = 0
        for t, rec in craft.rows().items():
            if rec.get('family') != 'upgrade' or rec.get('effect') != 'damage_clipsize':
                continue
            q = quests.get(t)
            if q is None or quests.acquisition_blocked(q):
                continue
            base, result = (items.params_of(rec[k]) for k in ('gun', 'mod'))
            for field in ('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max'):
                expected = craft._scaled(base[field], 1.1)
                for mode, active in enumerate(base['fire_mods']):
                    if active:
                        self.assertEqual(result[field][mode], expected[mode],
                                         (t, rec['mod'], field, mode))
            self.assertGreater(result['clip_size'], base['clip_size'], t)
            checked += 1
        self.assertGreater(checked, 40)

    def test_existing_magazine_sizes_are_preserved(self):
        expected = {26070: 10, 26071: 7, 26083: 10, 26084: 7,
                    26185: 128, 26186: 100, 25992: 16, 26005: 24,
                    26018: 14, 26031: 12, 26044: 12, 26057: 8, 25417: 64}
        for t, capacity in expected.items():
            self.assertEqual(items.params_of(t)['clip_size'], capacity, t)
        mod = items.params_of(26071)
        self.assertEqual(mod['h_damage_min'][0], 22)
        self.assertEqual(mod['h_damage_max'][0], 40)

    def test_exact_copy_preferred_and_only_one_is_taken(self):
        q = self.recipe(26075)
        have = {26075: 1, 37638: 1, 37672: 1}
        self.assertEqual(craft.quest_inputs(q, have), [(26075, 1), (37672, 1)])
        self.assertFalse(q.is_complete(q.bag_progress({26075: 1, 1216: 1})))
        self.assertIsNone(craft.quest_inputs(q, {26075: 1}))

    def test_stalls_remove_only_interchangeable_double_blueprint_duplicates(self):
        self.assertEqual(craft.unique_blueprints([37638, 37672, 37640, 37674, 717, 717]), [37638, 37640, 717, 717])
        for npc in (5770, 580, 583, 584, 585, 748, 751, 752):
            seen = set()
            for t in items.stock_for(npc):
                variants = craft.blueprint_variants(t)
                if len(variants) > 1:
                    key = frozenset(variants)
                    self.assertNotIn(key, seen)
                    seen.add(key)

    def test_non_upgrade_quests_do_not_accept_aliases(self):
        q = quests.Quest(dict(type=987654321, kind='bring_l_obj', name='Exact input',
                             objs=[dict(obj=37672, num=1)]))
        self.assertFalse(q.is_complete(q.bag_progress({37638: 1})))
        self.assertIsNone(craft.quest_inputs(q, {37638: 1}))


class TransactionalHandIn(unittest.TestCase):
    recipe = BlueprintCompatibility.recipe
    def setUp(self):
        self.store = accounts.Store(':memory:')
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, 'STORE', previous)
        self.addCleanup(self.store.close)
        account, _ = self.store.register('blueprint-test', 'test-only')
        self.cid, _ = self.store.create_character(account, 'BlueprintTest', 0, '1')
        self.s = session(self.store, level=14, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.char.set_skill(progression.SHOOTING, 14)
        self.s.char.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.closed, self.s.transport, self.s.residence_timer = False, None, None
        self.s.close = lambda force=False: setattr(self.s, 'closed', True)
        self.s.pos = 0
        self.s.loc = NS(id=36, width=20, height=20, spawns=[])
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames = []
        self.s.send = lambda cmd, **p: self.frames.append((cmd, p))
        self.s.say = self.s.answer = lambda text: None

    def prepare(self, gun, bp):
        for row in self.s.inv.rows():
            self.store.delete_item(row['uniq'])
        q = self.recipe(gun)
        self.s.room = NS(npc=lambda n: (0, q.take[0], world.UPGRADER))
        row = self.s.inv.give_pieces(gun, 1)[0]
        maximum = items.params_of(gun)['max_break_abs']
        self.store.update_item(row['uniq'], brk=maximum // 2, max_break_cur=maximum)
        self.s.inv.give_pieces(bp, 1)
        qid = self.store.take_quest(self.cid, q.type, q.bag_progress(self.s.inv.bag_pieces()), True)
        self.frames.clear()
        return q, qid

    def finish(self, qid):
        self.s.cmd_q_co(dict(q_id=qid, mob=1, obj_idx=0))
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def test_both_bp_variants_hand_in_for_each_model_once(self):
        for gun in TARGETS:
            q = self.recipe(gun)
            rec = craft.rows()[q.type]
            for bp in craft.blueprint_variants(rec['blueprint']):
                with self.subTest(gun=gun, blueprint=bp):
                    q, qid = self.prepare(gun, bp)
                    self.assertEqual(self.finish(qid), [0])
                    self.assertEqual(self.s.inv.bag_pieces(), {rec['mod']: 1})
                    result = self.s.inv.rows()[0]
                    self.assertGreater(result['brk'], 0)
                    self.assertLessEqual(abs(result['brk'] / result['max_break_cur'] - .5), .002)
                    self.frames.clear()
                    self.assertNotEqual(self.finish(qid), [0])
                    self.assertEqual(self.s.inv.bag_pieces(), {rec['mod']: 1})

    def test_wrong_tier_keeps_everything(self):
        q, qid = self.prepare(26075, 37674)
        before = copy.deepcopy(self.s.inv.rows())
        self.assertNotEqual(self.finish(qid), [0])
        self.assertEqual(self.s.inv.rows(), before)
        self.assertIsNotNone(self.store.quest(qid))

    def test_upgrader_window_accepts_the_other_blueprint_type(self):
        for gun in TARGETS:
            q = self.recipe(gun)
            rec = craft.rows()[q.type]
            bp = craft.blueprint_variants(rec['blueprint'])[1]
            self.prepare(gun, bp)
            self.s.room = NS(npcs={1: NS(type_id=q.give[0])})
            self.s.npc_session = upgrader.SESSION_UPGRADE
            window = upgrader.Window(self.s)
            window.open_, window.npc_type, window.room = True, q.give[0], self.s.room
            row = next(r for r in self.s.inv.rows() if r['type_id'] == gun)
            window.ss_upd(dict(s_status=1, obj=inventory.oid_of(row), param=rec['mod']))
            self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
            self.assertEqual(self.s.inv.bag_pieces(), {rec['mod']: 1})

    def test_reward_failure_rolls_back_inputs_and_history(self):
        q, qid = self.prepare(26075, 37638)
        before = copy.deepcopy(self.s.inv.rows())
        with patch.object(self.s.inv, 'give_pieces', side_effect=RuntimeError('test reward failure')):
            self.assertNotEqual(self.finish(qid), [0])
        self.assertEqual(self.s.inv.rows(), before)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, q.type))


class PersonalKnifeAndM24(unittest.TestCase):
    def test_bagira_knife_is_the_actual_reward_and_is_personal(self):
        q = quests.get(488)
        self.assertIn(3941, q.rew_obj)
        for t in (3941, 3944):
            self.assertFalse(combat.drops_on_death(t))
            self.assertFalse(barter.tradable(t))
            self.assertFalse(mail.postable(t))
        self.assertEqual(items.params_of(3941)['exchang'], 0)
        with patch.object(items, 'params_of', return_value={'exchang': 1, 'quest': 0, 'cost': 1}):
            self.assertFalse(barter.tradable(3941))
            self.assertFalse(combat.drops_on_death(3941))

    def test_m24_only_afro_damage_and_its_modifications_change(self):
        a, g = items.params_of(25803), items.params_of(25804)
        self.assertEqual((a['h_damage_min'], a['h_damage_max']), ([95, 0, 102], [255, 0, 348]))
        self.assertEqual((g['h_damage_min'], g['h_damage_max']), ([114, 0, 122], [306, 0, 418]))
        baseline = {t: r for t, r in craft._STAT_CORRECTIONS.items() if t != 25803}
        with patch.dict(craft._STAT_CORRECTIONS, baseline, clear=True):
            before = items.params_of(25803)
        for key in set(a) - {'h_damage_min', 'h_damage_max'}:
            self.assertEqual(a.get(key), before.get(key), key)
        for t, (root, name) in items.catalogue().items():
            if not name.startswith('rifle_1_lvl_16_mod_'):
                continue
            mod = craft.mod_of(t)
            if mod and mod[0] == 25803:
                expected = copy.deepcopy(a)
                craft._apply(expected, mod[1])
                si = items.params_of(t)
                for key in ('h_damage_min', 'h_damage_max'):
                    self.assertEqual(si[key], expected[key], (t, key))


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(BlueprintCompatibility, TransactionalHandIn, PersonalKnifeAndM24)
