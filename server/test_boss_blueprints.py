"""Run with LAVA_RES set; all persistence in this suite is SQLite :memory:."""
import asyncio
import json
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

# These suites run as separate scripts (TESTING.md). Cached database modules
# may already hold a live connection; changing the environment cannot isolate it.
if any(name in sys.modules for name in ('storage', 'accounts', 'server')):
    raise RuntimeError(
        'Blueprint tests require a fresh process; run '
        'python server/test_boss_blueprints.py separately.')

# Must precede every game import: LAVA_DB_URL takes precedence over LAVA_DB.
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

import storage  # noqa: E402
if storage.using_postgres():
    raise RuntimeError('Blueprint tests require SQLite :memory:, not PostgreSQL.')

import bosses
import items
import mobs
import quests
import world


def tearDownModule():
    # Some cases import the real server, which owns a module-level Store.
    # Session.close saves the character but does not close that database.
    server_module = sys.modules.get('server')
    if server_module is not None:
        server_module.STORE.close()


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value

    def choice(self, members):
        return members[0]


class BossBlueprints(unittest.TestCase):
    def test_ordinary_mobs_never_drop_encrypted_blueprints_even_with_legacy_rows(self):
        for mob in (258, 305, 1750, 1751):
            self.assertNotEqual(mobs.stats(mob).role, 'boss')
            with self.subTest(mob=mob), \
                    patch.object(mobs, 'carried', return_value=[(2408, 1), (4796, 1)]), \
                    patch.object(mobs, 'roll_table', return_value=[(1131, 1)]), \
                    patch.object(mobs, 'quest_table', return_value=[(2418, 1.0)]):
                self.assertEqual(mobs.loot_for(mobs.stats(mob), FixedRandom(0),
                    {2418}, loc_id=82, killer_level=1), [(4796, 1)])

    def test_decoding_services_do_not_create_quest_drop_sources(self):
        catalogue = items.catalogue()
        for mob in world.mob_types():
            self.assertFalse(any(catalogue[t][1].startswith('codified_bp_')
                                 for t, chance in mobs.quest_table(mob)), mob)
        self.assertEqual(quests.get(132).rew_obj, [1131])
        self.assertEqual(quests.get(153).rew_obj, [1132])

    def test_active_decoding_quest_does_not_enable_ordinary_mob_drops(self):
        import accounts
        store = accounts.Store(':memory:')
        try:
            account, _ = store.register('blueprint-probe', 'local-password')
            cid, _ = store.create_character(account, 'BlueprintProbe', 0, '1')
            catalogue = items.catalogue()
            q = next(q for q in quests.QUESTS.values()
                     if any(catalogue.get(t, (None, ''))[1].startswith('codified_bp_')
                            for t, _num, _mobs in q.objs))
            store.take_quest(cid, q.type, {}, False)
            active = [quests.get(row['type']) for row in store.quests(cid)]
            wanted = {t for quest in active for t, _num, _mobs in quest.objs}
            self.assertTrue(wanted)
            self.assertTrue(all(catalogue[t][1].startswith('codified_bp_')
                                for t in wanted))
            with patch.object(mobs, 'carried', return_value=[]), \
                    patch.object(mobs, 'roll_table', return_value=[]):
                for mob in world.mob_types():
                    if mobs.stats(mob).role != 'boss':
                        self.assertEqual(mobs.loot_for(mobs.stats(mob), FixedRandom(0),
                                         wanted, loc_id=82, killer_level=1), [], mob)
        finally:
            store.close()

    def test_craft_quest_blueprint_sources_are_bosses_only(self):
        catalogue = items.catalogue()
        for mob in world.mob_types():
            if mobs.stats(mob).role == 'boss':
                continue
            for t, _chance in mobs.quest_table(mob):
                self.assertFalse(catalogue[t][1].startswith(
                    ('codified_bp_', 'bpg_', 'bpb_')), (mob, t))

    def test_explicit_sources_and_complete_decoding_coverage(self):
        expected = [(82, 269, 1), (80, 270, 2), (83, 284, 3), (81, 283, 4),
                    (86, 300, 5), (84, 299, 6), (87, 314, 7), (85, 313, 8),
                    (89, 328, 9), (88, 327, 10), (90, 361, 11), (92, 360, 12),
                    (91, 375, 13), (93, 374, 14), (99, 408, 15), (98, 407, 16),
                    (133, 778, 17)]
        self.assertEqual(len(bosses.BLUEPRINTS), 17)
        for loc, mob, level in expected:
            item = bosses.BLUEPRINTS[(loc, mob)]
            self.assertEqual(items.catalogue()[item][1], 'codified_bp_%d' % level)
            self.assertTrue(any(t == mob for c, t in world.location(loc).spawns))
            self.assertNotIn(mob, bosses.ALL_DAY)
        self.assertIsNone(bosses.blueprint_for(168, 8620))
        self.assertIsNone(bosses.blueprint_for(168, 1037))
        self.assertIsNone(bosses.blueprint_for(999, 269))
        self.assertIsNone(bosses.blueprint_for(80, 586))  # treasurer
        with patch.object(bosses, 'HOURS', []):
            self.assertIsNone(bosses.blueprint_for(82, 269))
        doc = json.loads((Path(__file__).resolve().parents[1] /
                          'data/questgen_weaponcraft.json').read_text(encoding='utf-8'))
        decoding = [r for r in doc['quests'] if r['craft']['family'] == 'decode']
        self.assertEqual({r['craft']['level'] for r in decoding}, set(range(1, 21)))
        added = [r for r in decoding if r['craft']['level'] in (9, 10, 11)]
        self.assertEqual(len(added), 3)
        for r in added:
            self.assertEqual((r['give'], r['take'], r['level'], r['max_level']),
                             ([651], [651], 9, 20))
            self.assertEqual(doc['types'][r['craft']['key']], r['type'])
            self.assertEqual(set(r['objs'][0]), {'obj', 'num'})
            for reward in r['rew_random']:
                self.assertTrue(items.catalogue()[reward['obj']][1].endswith(
                    'lvl%d' % r['craft']['level']))
        self.assertFalse(quests.check_items())

    def test_generator_keeps_decoding_disabled_drops_without_opening_other_sources(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
        import build_weaponcraft as builder

        doc = json.loads((Path(__file__).resolve().parents[1] /
                          'data/questgen_weaponcraft.json').read_text(encoding='utf-8'))
        rows = [r for r in doc['quests'] if r['craft']['family'] == 'decode'
                and r['craft']['key'].startswith('decode:abu_hamed:')]
        texts = {i: '' for i in range(47998, 48038)}
        for row in rows:
            ident = int(row['craft']['key'].rsplit(':', 1)[1])
            texts[ident] = row['name']
            texts[ident + 1] = row['start'].split('<Br><Br><b>Внимание:')[0]
        texts[builder.DECODE_NOTFINISH] = rows[0]['notfinish']
        texts[builder.DECODE_FINISH] = rows[0]['finish']
        city = next(c for c in builder.CITIES if c['name'] == 'abu_hamed')
        upgrades = [r for r in doc['quests'] if r['craft']['family'] == 'upgrade'
                    and r['craft']['key'].startswith('upgrade:abu_hamed:')]
        rebuilt = builder.decode_rows(city, texts, upgrades)
        self.assertEqual(rebuilt, [{k: v for k, v in row.items() if k != 'type'}
                                   for row in rows])
        self.assertEqual({r['craft']['level'] for r in rebuilt}, {17, 18, 19, 20})
        # Only the three explicitly disabled drops keep a service without a source.
        with patch.object(bosses, 'BLUEPRINTS', {}):
            self.assertEqual({r['craft']['level'] for r in
                              builder.decode_rows(city, texts, upgrades)}, {18, 19, 20})
        self.assertEqual(bosses.DISABLED_BLUEPRINT_DROPS, {1270, 2417, 2418})

    def test_high_level_bosses_cannot_drop_blueprints_from_any_source(self):
        for loc, mob, blueprint in ((132, 777, 1270), (274, 1038, 2417),
                                    (263, 1037, 2418)):
            self.assertIsNone(bosses.blueprint_for(loc, mob))
            self.assertTrue(bosses.is_camp_boss(loc, mob))
            st = mobs.stats(mob)
            self.assertIn(items.catalogue()[blueprint][1],
                          ('codified_bp_18', 'codified_bp_19', 'codified_bp_20'))
            for player_level in (1, 17, 18, 19, 20, 100):
                for wanted in ((), {blueprint}):
                    with self.subTest(boss=mob, player=player_level, wanted=wanted), \
                            patch.object(mobs, 'carried', return_value=[(blueprint, 1)]), \
                            patch.object(mobs, 'roll_table', return_value=[(blueprint, 1), (7620, 4)]), \
                            patch.object(mobs, 'quest_table', return_value=[(blueprint, 1.0)]):
                        self.assertEqual(mobs.loot_for(st, FixedRandom(0), wanted,
                            loc_id=loc, killer_level=player_level), [(7620, 4)])

    def test_chance_and_finisher_level_boundaries_without_quests(self):
        for (loc, mob), item in bosses.BLUEPRINTS.items():
            st = mobs.stats(mob)
            blueprint_level = int(items.catalogue()[item][1].rsplit('_', 1)[1])
            for delta in (-2, 0, 1, 2, 3, 4, 5, 10):
                chance = 0.10
                for value in (0.0, chance - 0.000001, chance, 0.999999):
                    with self.subTest(mob=mob, delta=delta, roll=value), \
                            patch.object(mobs, 'carried', return_value=[(4796, 1)]), \
                            patch.object(mobs, 'roll_table', return_value=[(7620, 2)]), \
                            patch.object(mobs, 'quest_table', return_value=[]):
                        result = mobs.loot_for(st, FixedRandom(value), (), loc_id=loc,
                                               killer_level=blueprint_level + delta)
                        expected = [(4796, 1), (7620, 2)]
                        if value < chance:
                            expected.append((item, 1))
                        self.assertEqual(result, expected)
            with patch.object(mobs, 'carried', return_value=[]), \
                    patch.object(mobs, 'roll_table', return_value=[]), \
                    patch.object(mobs, 'quest_table', return_value=[]):
                self.assertEqual(mobs.loot_for(st, FixedRandom(0), (), loc_id=loc), [])

    def test_old_encrypted_drop_cannot_duplicate_or_bypass_fixed_chance(self):
        # Existing active quests can want both encrypted and ready blueprints.
        encrypted = 2408
        ready = next(t for t, chance in quests.quest_drops(269)
                     if quests.drop_group(t) == 'craft_blueprint')
        table = [(encrypted, 0.02), (ready, 0.2), (3742, 1.0)]
        st = mobs.stats(269)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=table):
            wanted = {encrypted, ready, 3742}
            result = mobs.loot_for(st, FixedRandom(0), wanted, loc_id=82,
                                   killer_level=st.level)
            self.assertEqual(result.count((encrypted, 1)), 1)
            self.assertIn((ready, 1), result)
            self.assertIn((3742, 1), result)
            blocked = mobs.loot_for(st, FixedRandom(0.10), wanted, loc_id=82,
                                    killer_level=5)  # blueprint level 1, difference +4
            self.assertNotIn((encrypted, 1), blocked)
            self.assertIn((ready, 1), blocked)
            self.assertIn((3742, 1), blocked)
            # Wrong locations cannot fall back to legacy quest sources.
            self.assertEqual(mobs.loot_for(st, FixedRandom(0), wanted,
                                          loc_id=999, killer_level=st.level).count((encrypted, 1)), 0)
            with patch.object(bosses, 'HOURS', []):
                self.assertEqual(mobs.loot_for(st, FixedRandom(0), (), loc_id=82,
                                              killer_level=st.level), [])

    def test_decoding_quest_does_not_raise_chance(self):
        st = mobs.stats(269)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[(2408, 0.02)]):
            for wanted in ((), {2408}):
                self.assertEqual(mobs.loot_for(st, FixedRandom(0.21), wanted,
                    loc_id=82, killer_level=4), [])
                self.assertEqual(mobs.loot_for(st, FixedRandom(0.03), wanted,
                    loc_id=82, killer_level=5), [(2408, 1)])

    def test_boss_combat_level_does_not_affect_blueprint_chance(self):
        # Asmund drops a level-1 blueprint even if his combat stats change.
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[]):
            for boss_level in (0, 10, 100):
                st = SimpleNamespace(type_id=269, level=boss_level)
                self.assertEqual(mobs.loot_for(st, FixedRandom(0.015), (),
                    loc_id=82, killer_level=4), [(2408, 1)])
                self.assertEqual(mobs.loot_for(st, FixedRandom(0.1), (),
                    loc_id=82, killer_level=5), [])

    def test_equal_level_chance_uses_one_roll_per_kill(self):
        st = mobs.stats(269)
        rng = random.Random(1234)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[]):
            outcomes = [mobs.loot_for(st, rng, (), loc_id=82,
                                     killer_level=1) for _ in range(4000)]
        self.assertTrue(all(len(x) <= 1 for x in outcomes))
        self.assertTrue(0.08 < sum(bool(x) for x in outcomes) / len(outcomes) < 0.12)

    def test_fixed_chance_for_all_blueprint_and_player_levels(self):
        for blueprint_level in range(1, 21):
            for player_level in range(101):
                with self.subTest(blueprint=blueprint_level, player=player_level):
                    self.assertEqual(bosses.blueprint_drop_chance(
                        player_level, blueprint_level), 0.10)

    def test_finisher_level_is_snapshotted_before_xp(self):
        import combat

        async def exercise():
            killer = SimpleNamespace(is_player=True, level=4, eid=1,
                                     count_kill=lambda t: None, release_stats=lambda: None)
            mob = SimpleNamespace(is_player=False, eid=2, type_id=269,
                                  stats=SimpleNamespace(name='test'), aim=None)
            rc = SimpleNamespace(room=SimpleNamespace(broadcast=lambda f: None,
                npcs={2: mob}, players=[], loc=SimpleNamespace(title='test')),
                quest_wants=lambda m, k: frozenset(),
                settle_xp=lambda m: setattr(killer, 'level', 5),
                corpse_gone=lambda *a: None, calm=lambda: None)
            with patch.object(combat.production, 'mined_by'), \
                    patch.object(combat.holdings, 'snapshot', return_value=None):
                combat.RoomCombat.kill(rc, mob, killer)
            self.assertEqual(mob.blueprint_killer_level, 4)
            self.assertEqual(killer.level, 5)
        asyncio.run(exercise())

    def test_actual_corpse_materializes_drop_in_memory(self):
        import accounts
        import combat
        store = accounts.Store(':memory:')
        st = mobs.stats(269)
        rc = SimpleNamespace(room=SimpleNamespace(loc=SimpleNamespace(id=82)), store=store)
        mob = SimpleNamespace(type_id=269, stats=st, quest_wants=frozenset(),
                              blueprint_killer_level=4)  # level-1 blueprint +3
        try:
            with patch.object(combat, 'RNG', FixedRandom(0)), \
                    patch.object(mobs, 'carried', return_value=[(4796, 1)]), \
                    patch.object(mobs, 'roll_table', return_value=[]), \
                    patch.object(mobs, 'quest_table', return_value=[]), \
                    patch.object(combat.events, 'loot', return_value=[]), \
                    patch.object(combat.production, 'yield_of', return_value=[]):
                rows = combat.RoomCombat.drop_loot(rc, mob)
                self.assertEqual([r['type_id'] for r in rows], [4796, 2408])
                self.assertTrue(all(store.item(r['uniq']) is not None for r in rows))
                mob.blueprint_killer_level = 5  # level-1 blueprint +4
                combat.RNG.value = 0.10
                self.assertEqual([r['type_id'] for r in combat.RoomCombat.drop_loot(rc, mob)], [4796])
        finally:
            store.close()

    def test_real_decoding_transactions_in_memory(self):
        import accounts
        import server
        from protocol import decode

        class Writer:
            def __init__(self): self.frames = []
            def write(self, data): self.frames.append(decode(data[:-1]))
            def close(self): pass
            def get_extra_info(self, *args): return None
            async def drain(self): pass

        async def exercise():
            self.assertEqual(accounts.DB_PATH, ':memory:')
            store = server.STORE
            store.register('bossblueprinttest', 'test-only-password')
            s = server.Session(Writer(), 'local-unittest')

            def cmd(name, params):
                s.writer.frames = []
                s.handle(name, params)
                return [p['res'] for n, p in s.writer.frames if n == 'cmdAck']

            self.assertEqual(cmd('login', {'hash': accounts.credential(
                'bossblueprinttest', 'test-only-password')}), [0])
            cmd('newPers', {'res': 1, 'sex': 0, 'name': 'Bossblueprinttest'})
            cmd('actPlayer', {}); cmd('lenter', {'accept': 1})
            s.admin_goto(103); cmd('lenter', {'accept': 1})
            npc = next(e for e, n in s.room.npcs.items() if n.type_id == 651)
            offered = quests.given_by(651)
            added = [t for t in offered if t in (10717, 10718, 10719)]
            self.assertEqual(len(added), 3)
            for level in (8, 9, 20, 21):
                # Boundary 21 is a defensive gate, even though progression caps at 20.
                s.skill_level = lambda value=level: value
                for tid in added:
                    q = quests.get(tid)
                    obj, num = q.wants()[0]
                    # Blueprint acquired before taking its decoding quest.
                    if level in (9, 20): s.inv.give_pieces(obj, num)
                    ack = cmd('q_st', {'mob': npc, 'q_idx': offered.index(tid)})
                    if level in (8, 21):
                        self.assertEqual(ack, [server.RES_NOT_AVAILABLE])
                        continue
                    self.assertEqual(ack, [0])
                    row = next(r for r in store.quests(s.char_id) if r['type'] == tid)
                    s.count_bag()
                    before = s.inv.bag_pieces()
                    s.char.afro = 0
                    self.assertEqual(cmd('q_co', {'mob': npc, 'q_id': row['q_id']}),
                                     [server.RES_NO_MONEY])
                    self.assertEqual(s.inv.bag_pieces(), before)
                    s.char.afro = 100000
                    money = s.char.afro
                    self.assertEqual(cmd('q_co', {'mob': npc, 'q_id': row['q_id']}), [0])
                    after = s.inv.bag_pieces()
                    self.assertEqual(after.get(obj, 0), before.get(obj, 0) - 1)
                    self.assertEqual(s.char.afro, money - q.cost_afro)
                    self.assertEqual(sum(after.get(t, 0) - before.get(t, 0)
                                         for t, n, w in q.rew_random), 1)
                    self.assertFalse(store.has_quest(s.char_id, tid))
                    self.assertEqual(cmd('q_co', {'mob': npc, 'q_id': row['q_id']}),
                                     [server.RES_NO_SUCH])
                    if level == 9:
                        self.assertEqual(cmd('q_st', {'mob': npc,
                            'q_idx': offered.index(tid)}), [0])
                        empty = next(r for r in store.quests(s.char_id) if r['type'] == tid)
                        self.assertEqual(cmd('q_co', {'mob': npc, 'q_id': empty['q_id']}),
                                         [server.RES_NOT_READY])
                        self.assertEqual(cmd('q_ca', {'q_id': empty['q_id']}), [0])
            s.close()
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
