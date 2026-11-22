"""Native lab recipes: scarce daily completion, physical inputs and no free repair."""
import asyncio
import logging
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)

import accounts
import auction
import barter
import bosses
import combat
import events
import gold_trade
import holdings
import inventory
import items
import mail
import names
import progression
import quests
import rooms
import server
import storage
from testkit import run_cases


class Laborant(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        self.now = int(time.time())
        self.enterContext(patch.object(time, "time", lambda: self.now))
        self.enterContext(patch.object(bosses, "clock", lambda: self.now))
        account, _ = self.store.register("lab-test", "local-password")
        self.cid, _ = self.store.create_character(account, "LabOwner", 0, "1")
        self.other, _ = self.store.create_character(account, "LabOther", 0, "1")
        self.clan = self.store.clan_create(self.cid, "Lab clan", "lab-clan", "", None)
        self.store.clan_member_add(self.other, self.clan, 0, "", self.cid)
        self.store.holding_capture("wh_ah_center", self.clan, self.now, self.cid, self.now)
        self.room = rooms.Room(server.world.location(128), rooms.IdAllocator(),
                               server.world.mob_types())
        self.rc = combat.room_combat(self.room, self.store)
        events.keep(self.rc)
        self.s = self.native(self.cid)

    def native(self, cid):
        s = server.Session(NS(write=lambda data: None, get_extra_info=lambda *_: None), "lab-test")
        s.char_id, s.char = cid, progression.Character.load(self.store, cid)
        for skill in s.char.skill:
            skill[0] = 20
        s.char.recalc()
        s.char.save(self.store)
        s.active = self.store.character(cid)
        s.account = {'id': s.active['account_id']}
        s.loc, s.room = self.room.loc, self.room
        s.pos = next(c for c, t in s.loc.spawns if t == quests.LABORANT_NPC)
        s.frames = []
        s.send = lambda command, **p: s.frames.append((command, p))
        s.answer = lambda text: s.send("answer", text=text)
        self.room.players[s] = None
        self.addCleanup(self.room.players.pop, s, None)
        self.addCleanup(s.combat.cancel_timers)
        return s

    def lab(self):
        return next(e for e, n in self.room.npcs.items() if n.type_id == quests.LABORANT_NPC)

    def ready(self, kind=18306, sess=None):
        s = sess or self.s
        q = quests.get(kind)
        for obj, count in q.wants():
            s.inv.give_pieces(obj, count)
        return self.take(kind, s)

    def take(self, kind, sess=None):
        s = sess or self.s
        s.frames.clear()
        s.handle("q_st", dict(mob=self.lab(), q_idx=quests.given_by(1407).index(kind)))
        rows = [p["q_id"] for n, p in s.frames if n.startswith("q_di_")]
        self.assertTrue(rows, s.frames)
        s.frames.clear()
        return rows[0]

    def visit(self, loc_id, trader):
        s = self.s
        s.room.players.pop(s, None)
        s.inv.close()
        s.room = self.room if loc_id == 128 else rooms.Room(
            server.world.location(loc_id), rooms.IdAllocator(), server.world.mob_types())
        s.loc = s.room.loc
        s.room.players[s] = None
        npc_id, npc = next((e, n) for e, n in s.room.npcs.items() if n.type_id == trader)
        s.pos = npc.cell
        s.frames.clear()
        s.inv.open_trade(dict(target=npc_id))
        self.assertEqual([p["res"] for n, p in s.frames if n == "cmdAck"], [0])

    def buy(self, type_id, gold):
        s = self.s
        stock = items.stock_for(s.inv.trade.trader_type, s.inv.trade.loc_id)
        s.frames.clear()
        s.inv.buy(dict(obj=format(stock.index(type_id), "x"), param=1),
                  inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
        self.assertEqual([p["res"] for n, p in s.frames if n == "cmdAck"], [0])

    def finish(self, qid, sess=None, mob=None):
        s = sess or self.s
        s.frames.clear()
        s.handle("q_co", dict(q_id=qid, mob=self.lab() if mob is None else mob, obj_idx=0))
        return [p["res"] for n, p in s.frames if n == "cmdAck"]

    def advance_day(self):
        self.now = server.Session.day_start(self.now) + 86400
        events.keep(self.rc)

    def test_seven_recipes_use_exact_archive_inputs_and_separate_plain_A1(self):
        self.assertEqual(len(quests.LABORANT_RECIPES), 7)
        for kind, (base, output) in quests.LABORANT_RECIPES.items():
            q = quests.get(kind)
            self.assertEqual(dict(q.wants()), {3726: 1, base: 1, 3741: 5, 1573: 1})
            self.assertEqual((q.rew_obj, q.num_rew_obj, q.level, q.service), ([output], [1], 16, True))
            self.assertEqual(q.start_obj, [])
            self.assertEqual(q.holders, "wh_ah_center")
        si = items.params_of(3726)
        self.assertEqual((si["g_cost"], si["cost"], si["armor_class"], si["max_break_abs"],
                          si["weight"], si["bonus_ce"], si["bonus_skills"], si["bonus_specs"]),
                         (3600, 0, 5, 5000, 100, 20, [3], [3, 3]))
        self.assertIn("спецназовца", names.ALL[items.STRING_ID_OFFSET + 3737])
        self.assertEqual(items.params_of(3737)["bonus_specs_m"], 131)

    def test_research_kit_buy_at_both_markets_and_carry_to_saved_laboratory(self):
        for loc in (35, 104):
            with self.subTest(location=loc):
                self.store.set_money(self.cid, 500000, 0)
                self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
                before = self.s.inv.total_weight()
                self.visit(loc, 81)
                self.buy(1573, False)
                self.assertEqual(self.store.money(self.cid), (250000, 0))
                self.assertEqual(self.s.inv.total_weight() - before, 2500)
                self.assertLessEqual(self.s.inv.total_weight(), self.s.inv.carry_limit())
                rows = self.s.inv.rows()
                self.store.save_position(self.cid, 128, self.room.loc.entry_cell(), 0, 0, False)
                reloaded = self.native(self.cid)
                self.assertEqual(reloaded.inv.rows(), rows)
                self.assertEqual(reloaded.inv.total_weight(), self.s.inv.total_weight())
                self.assertEqual(self.store.character(self.cid)['loc'], 128)

    def test_large_weapon_stall_can_purchase_last_calibre_row_after_index_sixty_four(self):
        self.store.set_money(self.cid, 1000000, 100000)
        self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
        self.visit(195, 1229)
        stock = items.stock_for(1229, 195)
        self.assertGreater(len(stock), 64)
        type_id = stock[-1]
        self.assertEqual(items.root_of(type_id), items.AMMO)
        before = self.s.inv.bag_pieces().get(type_id, 0)
        self.buy(type_id, bool(items.params_of(type_id).get('g_cost')))
        self.assertEqual(self.s.inv.bag_pieces()[type_id], before + 1)

    def test_all_A1_items_share_tier_sixteen_and_cannot_transfer_to_low_levels(self):
        types = [3726] + [output for _base, output in quests.LABORANT_RECIPES.values()]
        for type_id in types:
            row = dict(type_id=type_id, root=items.WEAR)
            self.assertEqual(inventory.item_level(type_id), 16)
            for level in range(13):
                self.assertFalse(inventory.wearable(row, level), (type_id, level))
            self.assertTrue(inventory.wearable(row, 13))
            for skill in self.s.char.skill:
                skill[0] = 16
            self.assertEqual(inventory.wear_multiplier(row, self.s.char), 1)
        stock = items.stock_for(1219, 126)
        for type_id in (3722, 3723, 3724, 3725, 3726):
            self.assertEqual(stock.count(type_id), 1)
        self.assertEqual([items.params_of(t)["g_cost"] for t in (3735, 3736, 3738, 5615)],
                         [6000, 5500, 7000, 6000])
        self.assertFalse({3737, 3739, 3740}.intersection(stock))

    def test_crafting_each_retail_pouch_saves_money_without_resale_arbitrage(self):
        mod = items.params_of(quests.LABORANT_MOD)
        kit = items.params_of(1573)
        self.assertEqual((mod['g_cost'], kit['cost']), (3600, 250000))
        retail = set(items.stock_for(1219, 126))
        rate = progression.GOLD_TO_AFRO_RATE // progression.GOLD_OUNCE
        compared = []
        for base, output in quests.LABORANT_RECIPES.values():
            if output not in retail:
                continue
            with self.subTest(output=output):
                source = items.params_of(base)
                made = items.params_of(output)
                inputs = mod['g_cost'] + source['g_cost']
                self.assertGreaterEqual(made['g_cost'] * rate
                                        - inputs * rate - kit['cost'], 250000)
                for share in (gold_trade.NPC_SALE_SHARE, gold_trade.BASE_SALE_SHARE):
                    self.assertLessEqual(gold_trade.sale_unit(output, made, share),
                                         gold_trade.sale_unit(quests.LABORANT_MOD, mod, share)
                                         + gold_trade.sale_unit(base, source, share))
                compared.append(output)
        self.assertCountEqual(compared, [3735, 3736, 3738, 5615])

    def test_original_inputs_and_ready_pouch_combat_stats_stay_unchanged(self):
        for type_id, price, attr in ((3722, 3000, [3]), (3723, 3000, [3]),
                                     (3724, 3000, [3]), (3725, 3000, [4])):
            si = items.params_of(type_id)
            self.assertEqual((si['g_cost'], si['bonus_attribs'], si['max_break_abs'], si['weight']),
                             (price, attr, 5000, 100))
        for type_id, price, mask in ((3599, 1000, 2), (3600, 400, 8),
                                    (3602, 2000, 1), (5614, 800, 2)):
            si = items.params_of(type_id)
            self.assertEqual((si['g_cost'], si['bonus_attribs'], si['bonus_attribs_m'],
                              si['armor_class'], si['max_break_abs'], si['weight']),
                             (price, [1], mask, 5, 600, 700))
        for type_id in (3735, 3736, 3738, 5615):
            si = items.params_of(type_id)
            self.assertEqual((si['armor_class'], si['bonus_ce'], si['max_break_abs'],
                              si['weight'], si['need_attribs']), (5, 20, 5600, 700, [5]))

    def test_detail_and_craft_need_live_central_warehouse_owner(self):
        detail = quests.get(quests.LABORANT_DETAIL)
        craft = quests.get(18306)
        self.assertEqual(detail.holders, 'wh_ah_center')
        other = self.native(self.other)
        # The lab's own daily counters stay personal: no box tenure or
        # shared-account quota is silently added to these quests.
        qid = self.ready(quests.LABORANT_DETAIL)
        self.assertEqual(self.finish(qid), [0])
        qid = self.ready(quests.LABORANT_DETAIL, other)
        self.assertEqual(self.finish(qid, other), [0])
        self.assertTrue(self.s.quest_available(craft))
        craft_id = self.ready()
        before = self.s.inv.rows()
        outsider_id, _ = self.store.create_character(self.s.active['account_id'], 'LabOutsider', 0, '1')
        outsider = self.native(outsider_id)
        self.assertFalse(outsider.quest_available(detail))
        self.assertFalse(outsider.quest_available(craft))
        rival = self.store.clan_create(outsider_id, 'Rival lab', 'rival-lab', '', None)
        self.store.holding_capture('wh_ah_center', rival, self.now + 1, outsider_id, self.now + 1)
        self.assertFalse(self.s.quest_available(craft))
        self.assertTrue(outsider.quest_available(detail))
        self.assertEqual(self.finish(craft_id), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.s.inv.rows(), before)
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})
        self.store.holding_capture('wh_ah_center', self.clan, self.now + 2, self.cid, self.now + 2)
        self.assertEqual(self.finish(craft_id), [0])

    def test_personal_part_daily_take_cancel_and_relog_cannot_duplicate(self):
        qid = self.ready(quests.LABORANT_DETAIL)
        self.assertEqual(self.finish(qid), [0])
        self.assertEqual(self.s.inv.bag_pieces(), {3741: 1})
        self.assertFalse(self.s.quest_available(quests.get(quests.LABORANT_DETAIL)))
        # A forged second active instance is checked against committed history.
        qid = self.store.take_quest(self.cid, quests.LABORANT_DETAIL, {}, True)
        self.assertNotEqual(self.finish(qid), [0])
        reloaded = self.native(self.cid)
        # Carried quests stay in the journal; their live hand-in gate still
        # checks today's committed reward after a reconnect.
        self.assertTrue(reloaded.quest_available(quests.get(quests.LABORANT_DETAIL)))
        self.assertEqual(self.finish(qid, reloaded), [server.RES_NOT_AVAILABLE])
        self.advance_day()
        self.assertEqual(self.finish(qid, reloaded), [0])
        self.assertEqual(reloaded.inv.bag_pieces(), {3741: 2})
        self.assertTrue(self.native(self.other).quest_available(quests.get(quests.LABORANT_DETAIL)))

    def test_all_seven_real_native_handins_create_exact_outputs_once(self):
        for kind, (_base, output) in quests.LABORANT_RECIPES.items():
            with self.subTest(quest=kind):
                qid = self.ready(kind)
                old_lab = self.lab()
                before = self.s.inv.bag_pieces()
                self.assertEqual(self.finish(qid), [0])
                self.assertEqual(self.s.inv.bag_pieces().get(output, 0), before.get(output, 0) + 1)
                self.assertFalse(any(n.type_id == 1407 for n in self.room.npcs.values()))
                self.assertIn(("lch", {"dead": old_lab}), self.s.frames)
                self.assertIn(("lch", {"lostUser": old_lab}), self.s.frames)
                self.assertEqual(self.finish(qid, mob=old_lab), [server.RES_NO_SUCH])
                self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]),
                                 {quests.LABORANT_SPOT: float(self.s.day_start())})
                self.advance_day()
                self.assertNotEqual(self.lab(), old_lab)

    def test_other_character_competing_recipe_keeps_all_inputs_after_winner(self):
        other = self.native(self.other)
        qid = self.ready(18306)
        second = self.ready(18307, other)
        before = other.inv.bag_pieces()
        old_lab = self.lab()
        self.assertEqual(self.finish(qid), [0])
        self.assertNotEqual(self.finish(second, other, old_lab), [0])
        self.assertEqual(other.inv.bag_pieces(), before)
        self.assertIsNotNone(self.store.quest(second))
        # Same location rebuilt after restart: claim suppresses the NPC.
        rebuilt = rooms.Room(server.world.location(128), rooms.IdAllocator(), server.world.mob_types())
        events.keep(combat.room_combat(rebuilt, self.store))
        self.assertFalse(any(n.type_id == 1407 for n in rebuilt.npcs.values()))
        self.advance_day()
        self.assertEqual(self.finish(second, other), [0])

    def test_failure_after_sql_claim_and_physical_item_restores_everything(self):
        qid = self.ready()
        before = self.s.inv.bag_pieces()
        original = self.s.inv.give_pieces

        def fail(*args):
            original(*args)
            raise RuntimeError("failure after native reward item insertion")

        with patch.object(self.s.inv, "give_pieces", fail):
            self.assertEqual(self.finish(qid), [1])
        self.assertEqual(self.s.inv.bag_pieces(), before)
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})
        self.assertFalse(self.store.quest_done(self.cid, 18306))
        self.assertIsNotNone(self.store.quest(qid))
        self.assertTrue(any(n.type_id == 1407 for n in self.room.npcs.values()))
        self.assertEqual(self.finish(qid), [0])

    def test_missing_locked_or_equipped_input_never_consumes_daily_claim(self):
        qid = self.ready()
        mod = next(r for r in self.s.inv.rows() if r["type_id"] == 3726)
        self.s.inv.locked.add(mod["uniq"])
        self.assertNotEqual(self.finish(qid), [0])
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})
        self.s.inv.locked.clear()
        self.store.update_item(mod["uniq"], slot=inventory.BELT)
        self.assertNotEqual(self.finish(qid), [0])
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})
        self.store.update_item(mod["uniq"], slot=inventory.BAG)
        self.s.inv.take_pieces(3741, 1)
        self.assertNotEqual(self.finish(qid), [0])
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})
        self.s.inv.give_pieces(3741, 1)
        self.assertEqual(self.finish(qid), [0])

    def test_cancel_keeps_owned_components_and_never_grants_a_free_kit(self):
        qid = self.ready()
        before = self.s.inv.bag_pieces()
        self.s.handle("q_ca", dict(q_id=qid))
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.s.inv.bag_pieces(), before)
        self.assertEqual(self.store.boss_kills([quests.LABORANT_SPOT]), {})

    def test_reserved_inputs_are_kept_and_the_consumed_copies_pass_their_wear(self):
        qid = self.ready()
        reserved = [r for r in self.s.inv.rows() if r["type_id"] in (3726, 3599)]
        self.s.inv.locked.update(r["uniq"] for r in reserved)
        for type_id, brk, top in ((3726, 2500, 5000), (3599, 150, 300)):
            self.s.inv.give_pieces(type_id, 1)
            row = next(r for r in reversed(self.s.inv.rows()) if r["type_id"] == type_id)
            self.store.update_item(row["uniq"], brk=brk, max_break_cur=top)
        self.assertEqual(self.finish(qid), [0])
        for row in reserved:
            self.assertEqual(self.store.item(row["uniq"]), row)
        output = next(r for r in self.s.inv.rows() if r["type_id"] == 3735)
        self.assertEqual((output["brk"], output["max_break_cur"]), (1400, 2800))

    def test_personal_parts_cannot_be_dropped_killed_out_or_picked_from_legacy_ground(self):
        async def scenario():
            row = self.s.inv.give_pieces(quests.LABORANT_PART, 5)[0]
            fighter = self.s.combat
            fighter.open_loot(dict(target=self.s.pos))
            for _ in range(3):
                self.s.frames.clear()
                fighter.ss_upd(dict(s_status=2, obj=inventory.oid_of(row)))
                self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"],
                                 [inventory.RES_REFUSED])
                self.assertEqual(self.store.item(row["uniq"]), row)
                self.assertFalse(self.rc.loot)
            self.assertFalse(combat.drops_on_death(quests.LABORANT_PART))
            with patch.object(combat, "RNG", NS(randint=lambda *_: 1)):
                fighter.drop_on_death()
            self.assertEqual(self.store.item(row["uniq"]), row)
            self.assertFalse(self.rc.loot)
            # A legacy/admin-created shared bag also cannot transfer a part,
            # individually or by a replayed take-all with ordinary loot.
            fields = inventory.new_fields(quests.LABORANT_PART)
            root = fields.pop("root")
            old = self.store.create_item(combat.LOOT_OWNER, quests.LABORANT_PART, root, **fields)
            fields = inventory.new_fields(6946)
            root = fields.pop("root")
            ordinary = self.store.create_item(combat.LOOT_OWNER, 6946, root, **fields)
            self.rc.add_to_bag(self.s.pos, [old, ordinary])
            try:
                forged = inventory.oid_of(dict(old, type_id=6946))
                for code, oid in ((1, inventory.oid_of(old)), (3, inventory.oid_of(old)),
                                  (1, forged), (3, forged)):
                    self.s.frames.clear()
                    fighter.ss_upd(dict(s_status=code, obj=oid))
                    self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"],
                                     [inventory.RES_REFUSED])
                    self.assertEqual(self.store.item(old["uniq"])["char_id"], combat.LOOT_OWNER)
                    self.assertEqual(self.store.item(ordinary["uniq"])["char_id"], combat.LOOT_OWNER)
                    self.assertEqual(self.s.inv.bag_pieces(), {quests.LABORANT_PART: 5})
                self.s.frames.clear()
                fighter.ss_upd(dict(s_status=1, obj=inventory.oid_of(ordinary)))
                self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"],
                                 [inventory.RES_OK])
                self.assertEqual(self.store.item(ordinary["uniq"])["char_id"], self.cid)
            finally:
                for bag in self.rc.loot.values():
                    if bag.expiry:
                        bag.expiry.cancel()
        asyncio.run(scenario())

    def test_personal_parts_refuse_native_mail_barter_auction_and_vendor(self):
        row = self.s.inv.give_pieces(quests.LABORANT_PART, 5)[0]
        before = self.s.inv.rows(), self.store.money(self.cid)
        self.assertFalse(barter.tradable(quests.LABORANT_PART))
        self.assertFalse(mail.postable(quests.LABORANT_PART))
        self.assertEqual(items.params_of(quests.LABORANT_PART)["cost"], 0)
        for kind in (mail.LETTER, mail.LETTER_EXPRESS, mail.TRADE, mail.TRADE_EXPRESS):
            self.s.frames.clear()
            self.s.handle("sndml", dict(to="LabOther", type=kind, item=inventory.oid_of(row),
                                        subj="Part", body="test"))
            self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"],
                             [mail.RES_REFUSED])
        other = self.native(self.other)
        me, them = barter.Side(self.s), barter.Side(other)
        self.s.frames.clear()
        self.s.barter.put(NS(open=True), me, them, dict(obj=inventory.oid_of(row)))
        self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"], [barter.RES_CANT])
        self.assertEqual(me.items, {})
        self.s.frames.clear()
        with patch.object(self.s.auction, "at_auctioneer", return_value=True):
            self.s.handle("ah_create", dict(target=1, obj=inventory.oid_of(row), time=6, a_bid=1000))
        self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"], [auction.RES_REFUSED])
        self.visit(126, 1219)
        self.s.frames.clear()
        self.s.inv.sell(dict(obj=inventory.oid_of(row), param=5))
        self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"], [inventory.RES_REFUSED])
        self.assertEqual((self.s.inv.rows(), self.store.money(self.cid)), before)
        self.assertEqual(self.store.mail_inbox(self.other), [])
        self.assertEqual(self.store.auction_count(self.cid, self.now), 0)
        # The bought kit keeps its existing non-exchange article flag;
        # the new personal-reward/ground/death restrictions do not bind it.
        self.assertNotIn(1573, items.PERSONAL_QUEST_REWARDS)
        self.assertFalse(barter.tradable(1573))
        self.assertFalse(mail.postable(1573))
        self.assertFalse(quests.not_on_ground(1573))
        self.assertFalse(combat.drops_on_death(1573))  # its pre-existing quest flag
        self.assertEqual((items.params_of(1573)["cost"], items.params_of(1573)["quest"]),
                         (250000, 1))

    def test_worst_condition_and_repaired_ceiling_of_both_sources_survive(self):
        cases = [(5000, 5000, 0, 600, 0, 5600),
                 (0, 5000, 600, 600, 0, 5600),
                 (2500, 2500, 300, 600, 1400, 2800),
                 (1000, 5000, 100, 300, 560, 2800),
                 (5000, 5000, 600, 600, 5600, 5600)]
        for mod_brk, mod_top, bag_brk, bag_top, brk, ceiling in cases:
            with self.subTest(condition=(mod_brk, mod_top, bag_brk, bag_top)):
                qid = self.ready()
                for row in self.s.inv.rows():
                    if row["type_id"] == 3726:
                        self.store.update_item(row["uniq"], brk=mod_brk, max_break_cur=mod_top)
                    elif row["type_id"] == 3599:
                        self.store.update_item(row["uniq"], brk=bag_brk, max_break_cur=bag_top)
                self.assertEqual(self.finish(qid), [0])
                made = next(r for r in reversed(self.s.inv.rows()) if r["type_id"] == 3735)
                self.assertEqual((made["brk"], made["max_break_cur"]), (brk, ceiling))
                self.advance_day()

    def test_real_shop_buy_craft_and_paid_base_resale_never_make_profit(self):
        clan = self.clan
        slot = self.now - 3600
        base = holdings.site("base_ah")
        self.store.clan_treasury_adjust(clan, 3_000_000, "admin")
        self.store.holding_capture(base.key, clan, slot, self.cid, slot)
        self.assertIsNotNone(self.store.holding_rent(
            base.key, clan, self.cid, slot, slot + 7 * 86400,
            base.rent, base.rent_quest, slot + 1, base_sites=holdings.base_keys()))
        # Each path actually buys both wearable inputs and the kit, uses the
        # native quest and confirms a real85%base quote. Rent is not counted,
        # making this profitability check stricter than the real expense.
        for kind, (pouch, output) in quests.LABORANT_RECIPES.items():
            for condition in (1, 0.2):
                with self.subTest(quest=kind, condition=condition):
                    self.store.set_money(self.cid, 10_000_000, 100_000)
                    self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
                    before = self.store.money(self.cid)
                    self.visit(126, 1219)
                    self.buy(3726, True)
                    self.visit(102 if pouch in (3603, 3604) else 126,
                               1204 if pouch in (3603, 3604) else 1219)
                    self.buy(pouch, True)
                    self.visit(35, 81)
                    self.buy(1573, False)
                    sources = [r for r in self.s.inv.rows() if r["type_id"] in (3726, pouch)]
                    if condition < 1:
                        for row in sources:
                            self.store.update_item(row["uniq"], brk=int(row["brk"] * condition))
                    self.s.inv.give_pieces(3741, 5)
                    self.s.room.players.pop(self.s, None)
                    self.s.inv.close()
                    self.s.room, self.s.loc = self.room, self.room.loc
                    self.room.players[self.s] = None
                    self.s.pos = self.room.npcs[self.lab()].cell
                    qid = self.take(kind)
                    self.assertEqual(self.finish(qid), [0])
                    row = next(r for r in self.s.inv.rows() if r["type_id"] == output)
                    self.assertLessEqual(gold_trade.sale_quality(row, items.params_of(output)), condition)
                    self.visit(609, 714)
                    request = dict(obj=inventory.oid_of(row), param=1)
                    self.s.frames.clear()
                    self.s.inv.quote_gold_sale(request)
                    quote = next(p for n, p in self.s.frames if n == "cmdAck")
                    self.assertEqual(quote["res"], 0)
                    self.s.frames.clear()
                    self.s.inv.sell(dict(request, sale_token=quote["token"], confirmation="ПРОДАТЬ"))
                    self.assertEqual([p["res"] for n, p in self.s.frames if n == "cmdAck"], [0])
                    after = self.store.money(self.cid)
                    value = lambda money: money[0] + money[1] * progression.GOLD_TO_AFRO_RATE / 100
                    self.assertLess(value(after), value(before))
                    # Even valuing both worn inputs at the same85%buyback
                    # floor (rather than their fresh shop prices) cannot
                    # turn the researcher kit into profitable recycling.
                    input_floor = sum(gold_trade.sale_unit(r["type_id"], items.params_of(r["type_id"]),
                                                          gold_trade.BASE_SALE_SHARE) * condition
                                      for r in sources) + 250000
                    self.assertLessEqual(quote["price"], input_floor)
                    self.advance_day()
                    # Keep a paid lease in each independent scenario; the
                    # weekly-expiry policy itself is covered by clan suites.
                    self.store.db.execute("UPDATE clan_holdings SET slot=?,paid_until=? WHERE site=?",
                                          (self.now - 3600, self.now + 6 * 86400, base.key))
                    self.store.db.commit()

    def test_unknown_commit_reply_cannot_repeat_the_reward_after_reconnect(self):
        qid = self.ready()
        old_lab = self.lab()
        raw = self.store.db.raw

        def commit():
            raw.commit()
            raise ConnectionError("COMMIT succeeded, reply lost")

        proxy = NS(commit=commit, rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _: proxy)), \
                patch.object(self.s, "close") as close:
            self.finish(qid)
        close.assert_called_once_with(force=True)
        reloaded = self.native(self.cid)
        self.assertEqual(reloaded.inv.bag_pieces(), {3735: 1})
        self.assertEqual(self.finish(qid, reloaded, old_lab), [server.RES_NO_SUCH])
        events.keep(self.rc)
        self.assertFalse(any(n.type_id == 1407 for n in self.room.npcs.values()))

    def test_new_day_boundaries_do_not_reset_warehouse_boss_or_unrelated_rows(self):
        old = server.Session.day_start(self.now)
        self.assertEqual(events.day_start(old - 1), old - 86400)
        self.assertEqual(events.day_start(old), old)
        self.store.boss_killed("128:100:7454", old + 20 * 3600)
        self.store.boss_claim(quests.LABORANT_SPOT, old)
        events.keep(self.rc)
        self.assertFalse(any(n.type_id == 1407 for n in self.room.npcs.values()))
        self.now = old + 86400 - 1
        events.keep(self.rc)
        self.assertFalse(any(n.type_id == 1407 for n in self.room.npcs.values()))
        self.now += 1
        events.keep(self.rc)
        self.assertTrue(any(n.type_id == 1407 for n in self.room.npcs.values()))
        self.assertEqual(self.store.boss_kills(["128:100:7454"]), {"128:100:7454": old + 20 * 3600})

    def test_live_laborant_refreshes_daily_quest_offer_without_a_relogin(self):
        qid = self.ready(quests.LABORANT_DETAIL)
        self.assertEqual(self.finish(qid), [0])
        old_lab = self.lab()
        self.assertFalse(self.s.quest_available(quests.get(quests.LABORANT_DETAIL)))
        self.s.frames.clear()
        self.advance_day()
        self.assertNotEqual(self.lab(), old_lab)
        self.assertIn(("lch", dict(lostUser=old_lab)), self.s.frames)
        self.assertTrue(any(n == "lch" and p.get("newUser") == self.lab()
                            for n, p in self.s.frames))
        self.assertTrue(self.s.quest_available(quests.get(quests.LABORANT_DETAIL)))

    def test_two_database_connections_cannot_complete_different_recipes_same_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lab-race.sqlite")
            setup = accounts.Store(path)
            aid, _ = setup.register("lab-race", "password")
            cids = [setup.create_character(aid, "RaceLab%d" % i, 0, "1")[0] for i in range(2)]
            setup.close()
            barrier = threading.Barrier(2)
            results, errors = [], []

            def complete(cid, kind):
                connection = None
                try:
                    connection = accounts.Store(path)
                    barrier.wait(timeout=10)
                    with storage.atomic(connection.db):
                        won = connection.boss_claim(quests.LABORANT_SPOT, self.s.day_start())
                        if won:
                            target = quests.LABORANT_RECIPES[kind][1]
                            fields = inventory.new_fields(target)
                            root = fields.pop("root")
                            fields["slot"] = inventory.BAG
                            connection.create_item(cid, target, root, **fields)
                    results.append(won)
                except Exception as exc:
                    errors.append(repr(exc))
                finally:
                    if connection is not None:
                        connection.close()

            threads = [threading.Thread(target=complete, args=(cid, kind))
                       for cid, kind in zip(cids, (18306, 18307))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), [False, True])
            restored = accounts.Store(path)
            try:
                self.assertEqual(sum(len(restored.items_of(cid)) for cid in cids), 1)
                self.assertFalse(restored.boss_claim(quests.LABORANT_SPOT, self.s.day_start()))
            finally:
                restored.close()


if __name__ == "__main__":
    run_cases(Laborant)
