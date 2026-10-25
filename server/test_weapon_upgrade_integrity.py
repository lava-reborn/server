"""Obtainable A/G weapons: recipe coverage, actual effects and safe hand-in.

PROTOCOL.md and craft.py require one upgrade per instance, the matching
blueprint and preserved wear. Read runtime shop bands and configured world
sources, then use real handlers and an in-memory Store. No sockets, bots,
waiting for timers or concurrent players; unsupported series are reported
separately rather than invented as new modifications.
"""
import json
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, str(ROOT / "tools"))
logging.disable(logging.CRITICAL)

import accounts  # noqa: E402
import audit_weapon_upgrades  # noqa: E402
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import server  # noqa: E402
import setcraft  # noqa: E402
import upgrader  # noqa: E402
from test_quest_state import session  # noqa: E402
from testkit import run_cases  # noqa: E402

DOC = json.loads((ROOT / "data/questgen_weaponcraft.json").read_text(encoding="utf-8"))
RECIPES = [r for r in DOC["quests"] if r["craft"]["family"] in ("upgrade", "knife")]


class UpgradeCatalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = audit_weapon_upgrades.audit()

    def test_every_documented_obtainable_modification_has_a_recipe(self):
        self.assertGreater(self.audit["base_weapons"], 100)
        self.assertEqual(self.audit["missing_effects"], [])

    def test_every_recipe_has_reachable_masters_and_blueprint_sources(self):
        self.assertEqual(self.audit["unavailable_pairs"], [])
        self.assertEqual(self.audit["missing_blueprint_sources"], [])
        for bp in self.audit["obtainable_blueprints"]:
            params = items.params_of(bp)
            self.assertGreater(params.get("cost", 0) + params.get("g_cost", 0), 0, bp)

    def test_inputs_and_output_match_the_recipe(self):
        self.assertEqual(self.audit["recipe_structure_errors"], [])
        outputs = {r["craft"]["mod"] for r in RECIPES}
        self.assertFalse(outputs & {r["craft"]["gun"] for r in RECIPES})
        families = json.loads((ROOT / "data/firearm_families.json").read_text(encoding="utf-8"))["lines"]
        by_name = {name: t for t, (_root, name) in items.catalogue().items()}
        expected = {(entry["members"].get(line), mod): key.split(":", 1)[1]
                    for entry in families.values() for line in ("A", "G", "Q")
                    for key, mod in entry["members"].items() if key.startswith(line + ":")}
        for row in RECIPES:
            c = row["craft"]
            self.assertIsNotNone(quests.get(row["type"]))
            self.assertFalse(items.out_of_game(c["gun"]))
            self.assertFalse(items.out_of_game(c["mod"]))
            self.assertFalse(items.out_of_game(c["blueprint"]))
            if c["family"] == "upgrade":
                self.assertEqual(expected[c["gun"], c["mod"]], c["effect"])
                bp = items.catalogue()[c["blueprint"]][1]
                # Services share the original blueprint where no separate
                # gold type exists; require G only when it exists.
                gold = bp if "_gold" in bp else bp.replace("_lvl", "_gold_lvl")
                if c["line"] == "G" and gold in by_name:
                    self.assertIn("_gold", bp, row["type"])
                elif c["line"] == "A":
                    self.assertNotIn("_gold", bp, row["type"])

    def test_declared_effect_improves_every_active_fire_mode(self):
        self.assertEqual(self.audit["effect_errors"], [])
        for row in RECIPES:
            c = row["craft"]
            if c["family"] != "upgrade":
                continue
            a, b = (items.params_of(c[k]) for k in ("gun", "mod"))
            self.assertEqual(a["weapon_type"], b["weapon_type"], row["type"])
            self.assertCountEqual(a["comp_array"], b["comp_array"], row["type"])
            self.assertEqual(a["fire_mods"], b["fire_mods"], row["type"])
            for i, enabled in enumerate(b["fire_mods"]):
                if enabled:
                    for low, high in (("h_damage_min", "h_damage_max"),
                                      ("st_damage_min", "st_damage_max")):
                        self.assertLessEqual(b[low][i], b[high][i], (row["type"], i))
                        self.assertGreaterEqual(b[low][i], a[low][i], (row["type"], i, low))
                        self.assertGreaterEqual(b[high][i], a[high][i], (row["type"], i, high))

    def test_corrected_values_and_documented_aug_weight(self):
        self.assertEqual(items.params_of(25142)["target_size"], [0.82, 0.945, 1.76])
        self.assertEqual(items.params_of(25736)["h_damage_max"], [244, 0, 323])
        self.assertEqual(items.params_of(25052)["h_damage_max"],
                         items.params_of(25040)["h_damage_max"])
        for t in (25015, 25016):
            # Both original wiki columns document a heavier durable AUG.
            # This is a separate balance choice, not a missing effect.
            self.assertEqual(items.params_of(t)["weight"], 5500)
            self.assertEqual(items.params_of(t)["max_break_abs"], 5500)

    def test_corrections_only_change_declared_fields(self):
        doc = json.loads((ROOT / "data/weaponcraft_corrections.json").read_text(encoding="utf-8"))
        for key, correction in doc["items"].items():
            t = int(key)
            with patch.object(craft, "lay_stat_corrections"):
                before = items.params_of(t)
            after = items.params_of(t)
            allowed = (set(correction.get("from_effect", ()))
                       | set(correction.get("from_base", ()))
                       | set(correction.get("values", {})))
            changed = {field for field in before.keys() | after.keys()
                       if before.get(field) != after.get(field)}
            self.assertTrue(changed <= allowed, (t, changed - allowed))

    def test_unmodified_series_are_explicitly_accounted_for(self):
        for row in self.audit["uncovered_base_weapons"]:
            name = row["internal"]
            self.assertTrue(name.startswith(("lamantin_", "gift_"))
                            or (name.startswith("knife_lvl") and name.endswith("_A"))
                            or row["type"] in (2943, 3552, 3941, *range(3728, 3734)), row)
            self.assertFalse(any(n.startswith(name + "_mod_")
                                 for _root, n in items.catalogue().values()))


class UpgradeOperations(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, "STORE", previous)
        self.addCleanup(self.store.close)
        account, _ = self.store.register("upgrade-unit", "local-password")
        self.cid, _ = self.store.create_character(account, "upgrade-unit", 0, "1")
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        for skill in self.s.char.skill:
            skill[0] = 20
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.transport = None
        self.s.closed = False
        self.s.room = None
        self.s.loc = NS(id=49, spawns=[])
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames = []
        self.s.send = lambda command, **params: self.frames.append((command, params))

    def give(self, t, **changes):
        fields = inventory.new_fields(t)
        root = fields.pop("root")
        fields.update(slot=inventory.BAG, **changes)
        return self.store.create_item(self.cid, t, root, **fields)

    def acks(self):
        return [p["res"] for n, p in self.frames if n == "cmdAck"]

    def take(self, row):
        self.s.npc_type = lambda _id: row["give"][0]
        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(row["give"][0]).index(row["type"])))
        self.assertEqual(self.acks(), [0], row["type"])
        qid = self.store.quests(self.cid)[0]["q_id"]
        self.frames.clear()
        self.s.npc_type = lambda _id: row["take"][0]
        return qid

    def test_all_512_recipes_use_real_hand_in_and_preserve_wear(self):
        self.assertEqual(len(RECIPES), 512)
        for recipe in RECIPES:
            with self.subTest(quest=recipe["type"]):
                c = recipe["craft"]
                for table in ("items", "char_quests", "char_quests_done"):
                    self.store.db.execute("DELETE FROM " + table + " WHERE char_id=?", (self.cid,))
                self.store.db.commit()
                self.s.fee_shown.clear()
                self.s.skill_shown.clear()
                self.frames.clear()
                level = min(20, recipe.get("max_level", 20))
                for skill in self.s.char.skill:
                    skill[0] = level
                self.s.char.recalc()
                self.s.char.save(self.store)
                top = items.params_of(c["gun"])["max_break_abs"]
                gun = self.give(c["gun"], brk=top // 3, max_break_cur=top * 3 // 4)
                old = craft.wear_of(gun)
                qid = self.take(recipe)
                self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
                self.assertNotEqual(self.acks(), [0], "no blueprint must be refused")
                self.assertIsNotNone(self.store.item(gun["uniq"]))
                self.give(c["blueprint"])
                self.frames.clear()
                self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
                self.assertEqual(self.acks(), [0])
                got = self.store.items_of(self.cid)
                self.assertEqual([r["type_id"] for r in got], [c["mod"]])
                self.assertIsNone(self.store.quest(qid))
                expected = setcraft.worn_as(old, items.params_of(c["mod"])["max_break_abs"])
                self.assertEqual((got[0]["brk"], got[0]["max_break_cur"]), expected)
                self.frames.clear()
                self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
                self.assertEqual(self.acks(), [server.RES_NO_SUCH])
                self.assertEqual(len(self.store.items_of(self.cid)), 1)

    def window(self):
        q, gun, mod, bp = craft.recipes_of(5771)[0]
        self.gun = self.give(gun)
        self.bp = self.give(bp)
        self.room = NS(npcs={1: NS(type_id=5771)})
        self.s.room = self.room
        self.s.npc_session = upgrader.SESSION_UPGRADE
        window = upgrader.Window(self.s)
        window.open_, window.npc_type, window.room = True, 5771, self.room
        self.params = dict(s_status=1, obj=inventory.oid_of(self.gun), param=mod)
        self.mod = mod
        return window

    def test_gold_recipe_refuses_afro_weapon_and_wrong_blueprint(self):
        gold = next(r for r in RECIPES if r["craft"]["gun"] == 25984
                    and r["craft"].get("effect") == "damage_clipsize")
        afro = next(r for r in RECIPES if r["craft"]["gun"] == 25983
                    and r["craft"].get("effect") == "damage_clipsize")
        g, a = gold["craft"], afro["craft"]
        self.assertNotEqual(g["blueprint"], a["blueprint"])
        for gun, bp in ((a["gun"], g["blueprint"]), (g["gun"], a["blueprint"])):
            for table in ("items", "char_quests"):
                self.store.db.execute("DELETE FROM " + table + " WHERE char_id=?", (self.cid,))
            self.store.db.commit()
            self.frames.clear()
            original = [self.give(gun)["uniq"], self.give(bp)["uniq"]]
            qid = self.take(gold)
            self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
            self.assertEqual(len(self.acks()), 1)
            self.assertNotEqual(self.acks(), [0])
            self.assertEqual(sorted(r["uniq"] for r in self.store.items_of(self.cid)),
                             sorted(original))
            self.assertIsNotNone(self.store.quest(qid))

    def test_window_rolls_back_a_failed_reward_and_discards_success(self):
        window = self.window()
        ammo = items.params_of(self.gun["type_id"])["comp_array"][0]
        self.store.update_item(self.gun["uniq"], ammo_type=ammo, ammo_count=3)
        with patch.object(self.s.inv, "give_pieces", side_effect=RuntimeError("reward failed")):
            window.ss_upd(self.params)
        self.assertIsNotNone(self.store.item(self.gun["uniq"]))
        self.assertIsNotNone(self.store.item(self.bp["uniq"]))
        self.assertEqual(self.store.item(self.gun["uniq"])["ammo_count"], 3)
        self.assertNotIn(ammo, self.s.inv.bag_pieces())
        self.assertEqual(self.acks(), [1])
        self.assertFalse(any(n.startswith("ss_") for n, _p in self.frames))

    def test_window_rollback_keeps_reload_and_success_leaves_no_stale_notification(self):
        window = self.window()
        uniq = self.gun["uniq"]
        timer = Mock()
        self.s.inv.reloads[uniq] = timer
        with patch.object(self.s.inv, "give_pieces", side_effect=RuntimeError("reward failed")):
            window.ss_upd(self.params)
        timer.cancel.assert_not_called()
        self.assertIs(self.s.inv.reloads[uniq], timer)
        self.frames.clear()
        self.s.inv.reloaded(uniq)
        self.assertNotIn(uniq, self.s.inv.reloads)
        self.assertTrue(any(n == "ss_di_firearm" for n, _p in self.frames))
        self.frames.clear()
        self.s.inv.reloads[uniq] = timer
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [0])
        self.assertIsNone(self.store.item(uniq))
        self.frames.clear()
        self.s.inv.reloaded(uniq)
        self.assertNotIn(uniq, self.s.inv.reloads)
        self.assertEqual(self.frames, [])

    def test_window_rejects_wrong_output_and_replay_without_consumption(self):
        window = self.window()
        window.ss_upd(dict(self.params, param=25562))
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assertIsNotNone(self.store.item(self.gun["uniq"]))
        self.assertIsNotNone(self.store.item(self.bp["uniq"]))
        self.frames.clear()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [0])
        self.assertEqual(self.s.inv.bag_pieces(), {self.mod: 1})
        self.frames.clear()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assertEqual(self.s.inv.bag_pieces(), {self.mod: 1})

    def test_window_returns_loaded_rounds_once(self):
        window = self.window()
        ammo = items.params_of(self.gun["type_id"])["comp_array"][0]
        self.store.update_item(self.gun["uniq"], ammo_type=ammo, ammo_count=3)
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [0])
        self.assertEqual(self.s.inv.bag_pieces(), {self.mod: 1, ammo: 3})
        self.frames.clear()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assertEqual(self.s.inv.bag_pieces(), {self.mod: 1, ammo: 3})

    def test_window_cannot_upgrade_locked_or_banked_items(self):
        window = self.window()
        self.s.inv.locked.add(self.gun["uniq"])
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.s.inv.locked.clear()
        self.store.update_item(self.gun["uniq"], slot=inventory.BANK)
        self.frames.clear()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        self.assertIsNotNone(self.store.item(self.bp["uniq"]))

    def test_window_refuses_after_leaving_master_and_above_level_cap(self):
        window = self.window()
        window.left()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_NOT_FOUND])
        window.npc_type, window.room = 5771, self.room
        for skill in self.s.char.skill:
            skill[0] = 21
        self.frames.clear()
        window.ss_upd(self.params)
        self.assertEqual(self.acks(), [inventory.RES_REFUSED])
        self.assertIsNotNone(self.store.item(self.gun["uniq"]))
        self.assertIsNotNone(self.store.item(self.bp["uniq"]))


if __name__ == "__main__":
    try:
        run_cases(UpgradeCatalogue, UpgradeOperations)
    finally:
        server.STORE.close()
