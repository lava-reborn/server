"""Level-17 release boundary: catalogue stays, player acquisition is closed."""
import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"

import auction
import barter
import craft
import inventory
import items
import mail
import names
import mobs
import quests
import server
import setcraft
import sets
import shop_bands
import upgrader
import world
from testkit import run_cases


class ReleaseBoundary(unittest.TestCase):
    def test_event_loot_keeps_allowed_rewards_and_blocks_unreleased_equipment(self):
        import events
        schedule = NS(loot={(1, 2): [(11489, 1, 1), (11309, 1, 1), (334, 2, 1)]}, keep_in=[])
        with patch.object(events, 'table', return_value=schedule):
            self.assertEqual(events.loot(1, 2, Mock()), [(11309, 1), (334, 2)])
            self.assertEqual(events.loot(3, 2, Mock()), [])

    def test_inventory_factory_refuses_creation_before_any_database_write(self):
        store = Mock()
        inv = inventory.Inventory(NS(char_id=1), store)
        for t in (6270, 11489, 60005, 11579, 11669):
            with self.assertRaises(ValueError):
                inv.create(t)
        store.create_item.assert_not_called()

    def test_all_declared_set_parts_follow_actual_release_level(self):
        # Internal art names can disagree with the owner's set levels.
        for rung in setcraft.LADDER:
            if rung["variant"] not in ("A", "G"):
                continue
            for t in rung["members"].values():
                with self.subTest(set=rung["set_type"], item=t):
                    self.assertEqual(items.acquisition_blocked(t), rung["level"] > 17)
                    self.assertIsNotNone(items.params_of(t))
                    self.assertFalse(items.retired(t))

    def test_weapon_boundary_and_non_equipment_are_independent(self):
        for t in (25319, 25320):  # F2000, declared level 17
            self.assertFalse(items.acquisition_blocked(t))
        for t in (6270, 6271, 6275, 6276):  # level-18/20 knives, A and G
            self.assertTrue(items.acquisition_blocked(t))
            self.assertFalse(mobs.droppable(t))
            self.assertFalse(mobs.one_of_droppable(t))
            self.assertFalse(mobs.quest_droppable(t))
            self.assertFalse(barter.tradable(t))
            self.assertFalse(mail.postable(t))
            self.assertIsNotNone(server.refused_gift(t))
        for t in (2258, 3159, 6109, 6953):
            self.assertFalse(items.acquisition_blocked(t))

    def test_no_city_shop_sells_unreleased_equipment(self):
        traders = set(shop_bands.SELLERS) | set(items.stock_table())
        for location in (62, 76, 195, 196, 126, 467):
            for trader in traders:
                for t in items.stock_for(trader, location):
                    self.assertFalse(items.acquisition_blocked(t), (trader, location, t))
        self.assertIn(11309, items.stock_for(1223, 126))  # Storm-M G helmet stays
        self.assertNotIn(11489, items.stock_for(1223, 126))

    def test_quest_gate_covers_every_reward_and_start_item_without_rewriting_rows(self):
        ordinary = dict(type=99999, kind=quests.DEL_OBJ, name="release test")
        for extra in (dict(rew_obj=[11489]), dict(start_obj=[dict(obj=11489)]),
                      dict(rew_also=[dict(obj=11489)]), dict(rew_random=[dict(obj=11489)])):
            q = quests.Quest(dict(ordinary, **extra))
            self.assertTrue(quests.acquisition_blocked(q))
        self.assertFalse(quests.acquisition_blocked(quests.Quest(dict(ordinary, rew_obj=[11309]))))

    def test_high_level_blueprint_upgrades_are_closed_without_removing_rows(self):
        blocked = set()
        for quest_type, recipe in craft.rows().items():
            q = quests.get(quest_type)
            if recipe.get('family') not in ('upgrade', 'knife'):
                continue
            blueprint = recipe['blueprint']
            if items.upgrade_blueprint_blocked(blueprint):
                blocked.add(blueprint)
                self.assertTrue(quests.acquisition_blocked(q), quest_type)
                self.assertIsNotNone(items.params_of(blueprint))
                self.assertFalse(items.out_of_game(blueprint))
            elif not any(items.acquisition_blocked(t) for t in q.rew_obj):
                self.assertFalse(quests.acquisition_blocked(q), quest_type)
        self.assertTrue({1271, 2453, 26581, 6632, 6635, 37678, 37679, 37680} <= blocked)
        # Existing encrypted blueprints can still be decoded.
        decoding = [quests.get(t) for t, r in craft.rows().items()
                    if r.get('family') == 'decode' and r['level'] in (18, 19, 20)]
        self.assertEqual(len(decoding), 3)
        self.assertTrue(all(not quests.acquisition_blocked(q) for q in decoding))

    def test_blocked_upgrade_cannot_consume_existing_quest_resources(self):
        row = dict(type=99999, kind='bring_l_obj', name='closed upgrade',
                   give=[748], take=[748], objs=[dict(obj=1271, num=1)],
                   rew_obj=[11309], cost_gold=100)
        q = quests.Quest(row)
        with patch.object(craft, 'rows', return_value={q.type: {'family': 'upgrade'}}):
            self.assertTrue(quests.acquisition_blocked(q))
            store = Mock()
            store.quest.return_value = dict(type=q.type, char_id=1)
            sess = Mock(char_id=1)
            sess.npc_type.return_value = 748
            with patch.object(server, 'STORE', store), \
                    patch.object(quests, 'get', return_value=q), \
                    patch.object(server.residence, 'refusal', return_value=None):
                server.Session.hand_in_quest(sess, dict(q_id=7, mob=1))
            sess.send.assert_called_once_with('cmdAck', res=server.RES_NOT_AVAILABLE)
            self.assertEqual([call[0] for call in store.method_calls], ['quest'])

    def test_all_shops_hide_high_level_upgrade_blueprints(self):
        traders = set(shop_bands.SELLERS) | set(items.stock_table())
        for loc in (None, 62, 76, 195, 196, 126, 467):
            for trader in traders:
                self.assertTrue(all(not items.upgrade_blueprint_blocked(t)
                                    for t in items.stock_for(trader, loc)), (trader, loc))
        for blueprint in (1271, 2453, 26581, 6632, 6635, 37678, 37679, 37680):
            with patch.object(items, '_own_list', return_value=[blueprint, 37677]):
                self.assertEqual(items.stock_for(99999), [37677])
        for blueprint in (2416, 1270, 2417, 2418, 37677, 334):
            self.assertFalse(items.upgrade_blueprint_blocked(blueprint))

    def test_weapon_windows_never_offer_blocked_outputs(self):
        for npc in (5771, 7548):
            for q, gun, mod, _bp in craft.recipes_of(npc):
                self.assertFalse(quests.acquisition_blocked(q))
                self.assertFalse(items.acquisition_blocked(gun))
                self.assertFalse(items.acquisition_blocked(mod))

    def test_existing_mail_attachment_is_kept_and_no_payment_or_creation_occurs(self):
        store, sess = Mock(), Mock()
        store.mail_letter.return_value = dict(items_json=json.dumps([dict(type_id=11489)]))
        handler = mail.Mail(sess, store, {})
        with patch.object(handler, "side_of", return_value="in"):
            handler.uldml(dict(id="1"))
        store.create_item.assert_not_called()
        store.mail_take.assert_not_called()
        sess.character.assert_not_called()
        sess.send.assert_called_once_with("cmdAck", res=mail.RES_REFUSED)

    def test_expired_blocked_auction_refunds_bid_and_keeps_sellers_item(self):
        store = Mock()
        lot = dict(type_id=11489, id=123, bidder=2, bid=100, bidder_name="buyer")
        store.auction_due.return_value = [lot]
        store.auction_close.return_value = None  # concurrent settlement already won
        with patch.object(auction, "meta", return_value=(0, 0, 0, "item")), \
                patch.object(auction, "refund", return_value=["refund"]) as refund, \
                patch.object(auction, "give_back", return_value=["return"]) as give_back, \
                patch.object(auction, "settle") as sale:
            auction.sweep(store, {}, now=1)
        sale.assert_not_called()
        refund.assert_called_once()
        give_back.assert_called_once()
        store.auction_close.assert_called_once_with(123, ["refund", "return"], was=(2, 100))


class OasisCatalogue(unittest.TestCase):
    def test_all_josephs_offer_all_levels_and_half_of_new_piece_price(self):
        by_part = {t: r for r in setcraft.LADDER for t in r["members"].values()}
        reference = setcraft.oasis_entries(7548, 76)
        for location, npc in setcraft.OASIS_UPGRADERS.items():
            rows = setcraft.oasis_entries(npc, location)
            self.assertTrue(rows, location)
            self.assertEqual(rows, reference, location)
            for src, dst, cost in rows:
                a, b = by_part[src], by_part[dst]
                self.assertEqual((a["variant"], b["variant"]), ("G", "G"))
                self.assertEqual(sets.slot_of(src), sets.slot_of(dst))
                self.assertLess(a["level"], b["level"])
                self.assertLessEqual(b["level"], 17)
                self.assertEqual(cost, (sets.item(dst)["g_cost"] + 1) // 2)
                between = [r for r in setcraft.LADDER if r["variant"] == "G"
                           and a["level"] < r["level"] < b["level"]]
                self.assertFalse(between)
            self.assertEqual(len({(a, b) for a, b, _c in rows}), len(rows))

    def test_red_echo_to_storm_m_is_last_step_and_costs_2188_hundredths(self):
        storm_parts = next(r["members"].values() for r in setcraft.LADDER
                           if 11309 in r["members"].values())
        for location, npc in setcraft.OASIS_UPGRADERS.items():
            self.assertEqual(setcraft.cost_of(npc, 10769, 11309, location), 2188)
            self.assertIsNone(setcraft.cost_of(npc, 11309, 11489, location))
            self.assertIsNone(setcraft.cost_of(npc, 11309, 60005, location))
            self.assertFalse(any(src in storm_parts for src, _dst, _cost
                                 in setcraft.oasis_entries(npc, location)))

    def test_no_oasis_service_at_other_locations_and_old_masters_stay_disabled(self):
        for location in (None, 95, 103, 131):
            self.assertEqual(setcraft.oasis_entries(7548, location), [])
        for npc in (93, 5104, 5):
            self.assertEqual(setcraft.entries(npc), [])
        self.assertEqual(upgrader.lists(7548), craft.upgrader_lists(7548))

    def test_existing_josephs_offer_sets_and_keep_weapon_recipes(self):
        self.assertEqual(setcraft.OASIS_UPGRADERS,
                         {62: 7548, 76: 7548, 195: 7548, 196: 7548})
        weapons = craft.upgrader_lists(7548)
        for location, npc in setcraft.OASIS_UPGRADERS.items():
            loc = world.Location(location)
            self.assertIn(npc, {t for _cell, t in loc.spawns})
            self.assertEqual(world.mob_types()[npc][0], world.UPGRADER)
            sets_list = setcraft.window(npc, location)
            combined = upgrader.lists(npc, location)
            for key in weapons:
                self.assertEqual(combined[key], weapons[key] + sets_list[key])
            for other in (2241, 2242):
                self.assertEqual(setcraft.entries(other, location), [])
        self.assertEqual(names.text(2241), "Эрих Френкель")
        self.assertEqual(names.text(2242), "Фриденсрайх Шнеерсон")

    def test_former_exchangers_are_commoners_without_home_registration(self):
        for npc in (2241, 2242):
            self.assertEqual(world.entity_root(npc, world.UPGRADER), world.COMMONER)
            self.assertFalse(world.offers_home(npc, world.UPGRADER))
            self.assertEqual(upgrader.lists(npc),
                             dict(in_types=[], out_types=[], costs=[]))
        for npc in (93, 5771, 7548):
            self.assertEqual(world.entity_root(npc, world.UPGRADER), world.UPGRADER)

    def test_former_exchangers_refuse_even_a_stale_upgrade_open_request(self):
        for npc in (2241, 2242):
            entry = NS(type_id=npc, root=world.UPGRADER)
            sess = NS(char_id=1, room=NS(npc=lambda _id: entry), inv=Mock())
            window = upgrader.Window(sess)
            window.open(dict(target=1))
            sess.inv.ack.assert_called_once_with(inventory.RES_NOT_FOUND)
            self.assertFalse(window.open_)

    def test_joseph_caption_describes_set_exchange(self):
        self.assertEqual(names.text(7548),
                         "Жозеф де Гобино<br>Оружейный механик<br>Обмен комплектов")
        for location in setcraft.OASIS_UPGRADERS:
            self.assertEqual(world.entity_root(7548, world.UPGRADER), world.UPGRADER)
            self.assertTrue(setcraft.oasis_entries(7548, location))

    def test_modified_inputs_are_not_consumed_by_new_service(self):
        for location, npc in setcraft.OASIS_UPGRADERS.items():
            for src, _dst, _cost in setcraft.oasis_entries(npc, location):
                self.assertEqual(setcraft.base_of(src), src)


if __name__ == "__main__":
    try:
        run_cases(ReleaseBoundary, OasisCatalogue)
    finally:
        server.STORE.close()
