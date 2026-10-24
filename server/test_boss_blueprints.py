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


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value

    def choice(self, members):
        return members[0]


class BossBlueprints(unittest.TestCase):
    def test_explicit_sources_and_complete_decoding_coverage(self):
        expected = [(82, 269, 1), (80, 270, 2), (83, 284, 3), (81, 283, 4),
                    (86, 300, 5), (84, 299, 6), (87, 314, 7), (85, 313, 8),
                    (89, 328, 9), (88, 327, 10), (90, 361, 11), (92, 360, 12),
                    (91, 375, 13), (93, 374, 14), (99, 408, 15), (98, 407, 16),
                    (133, 778, 17), (132, 777, 18), (274, 1038, 19), (263, 1037, 20)]
        self.assertEqual(len(bosses.BLUEPRINTS), 20)
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

    def test_chance_and_finisher_level_boundaries_without_quests(self):
        for (loc, mob), item in bosses.BLUEPRINTS.items():
            st = mobs.stats(mob)
            blueprint_level = int(items.catalogue()[item][1].rsplit('_', 1)[1])
            base = (20, 19, 18, 17, 16, 15, 14, 13, 12, 10, 10,
                    5, 5, 5, 5, 2, 2, 2, 2, 2)[blueprint_level - 1] / 100.0
            for delta in (-2, 0, 1, 2, 3, 4, 5, 10):
                chance = (0.02 if delta >= 4 else
                          max(0.02, round(base * (1 - max(0, delta) * 0.2), 8)))
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

    def test_old_encrypted_drop_cannot_duplicate_or_bypass_level_gate(self):
        # Existing active quests can want both encrypted and ready blueprints.
        encrypted = 2408
        ready = next(t for t, chance in quests.quest_drops(269)
                     if quests.drop_group(t) == 'craft_blueprint')
        table = [(encrypted, 0.02), (ready, 0.1), (3742, 1.0)]
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
            blocked = mobs.loot_for(st, FixedRandom(0.03), wanted, loc_id=82,
                                    killer_level=5)  # blueprint level 1, difference +4
            self.assertNotIn((encrypted, 1), blocked)
            self.assertIn((ready, 1), blocked)
            self.assertIn((3742, 1), blocked)
            # Wrong location keeps its old quest rules and gains no new roll.
            self.assertEqual(mobs.loot_for(st, FixedRandom(0), wanted,
                                          loc_id=999, killer_level=st.level).count((encrypted, 1)), 1)
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
                    loc_id=82, killer_level=5), [])

    def test_boss_combat_level_does_not_affect_blueprint_chance(self):
        # Asmund drops a level-1 blueprint even if his combat stats change.
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[]):
            for boss_level in (0, 10, 100):
                st = SimpleNamespace(type_id=269, level=boss_level)
                self.assertEqual(mobs.loot_for(st, FixedRandom(0.05), (),
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
        self.assertTrue(0.17 < sum(bool(x) for x in outcomes) / len(outcomes) < 0.23)

    def test_players_below_blueprint_level_keep_maximum_chance(self):
        for blueprint_level in range(1, 21):
            for player_level in range(blueprint_level + 1):
                self.assertEqual(bosses.blueprint_drop_chance(player_level, blueprint_level),
                    (20, 19, 18, 17, 16, 15, 14, 13, 12, 10, 10,
                     5, 5, 5, 5, 2, 2, 2, 2, 2)[blueprint_level - 1] / 100.0)

    def test_tier_boundaries_and_overlevel_floor(self):
        for tier, expected in ((1, (0.2, 0.16, 0.12, 0.08, 0.02)),
                               (9, (0.12, 0.096, 0.072, 0.048, 0.02)),
                               (10, (0.1, 0.08, 0.06, 0.04, 0.02)),
                               (11, (0.1, 0.08, 0.06, 0.04, 0.02)),
                               (12, (0.05, 0.04, 0.03, 0.02, 0.02)),
                               (15, (0.05, 0.04, 0.03, 0.02, 0.02)),
                               (16, (0.02,) * 5), (20, (0.02,) * 5)):
            with self.subTest(tier=tier):
                self.assertEqual(tuple(bosses.blueprint_drop_chance(tier + delta, tier)
                                       for delta in range(5)), expected)

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
                combat.RNG.value = 0.02
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
