"""Execute upgrade preview AVM1: consecutive upgrades without reopening the NPC."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parent.parent / 'server')]
import widescreen as w
from avm_test import execute


class UpgradePreview(unittest.TestCase):
    def setUp(self):
        self.models, self.created, self.shown = [], [], []
        self.clears = 0
        self.npc = NS(upgradeCosts=[100, 200], createUpgradeItem=self.create)
        self.upgrade = NS(neededList=[10, 20], upgradedList=[20, 30], visavisID=7,
                          visavisBag=NS(getItemsByType=lambda t:
                              [m for m in self.models if m.typeID == t]),
                          master=NS(getPlayer=lambda _id: self.npc))
        self.panel = NS(upgrade=self.upgrade,
                        visavisPan=NS(fillContent=self.clear, setPosition=lambda x, y: None),
                        createUpgradeItem=lambda before, after:
                            self.shown.append((before.typeID, after.typeID, after.item.cost)))

    def clear(self):
        self.clears += 1
        self.shown.clear()

    def create(self, index, type_id):
        self.created.append((index, type_id))
        # A cold prototype has neither a loaded illustration nor a price yet.
        self.models.append(NS(tradeID=index, typeID=type_id, item=NS()))

    def select(self, type_id):
        item = NS(typeID=type_id) if type_id is not None else None
        execute(w.fn_upgrade_description().assemble(), dict(this=self.panel, item=item))

    def test_next_upgrade_works_without_reopening_service(self):
        self.create(0, 20)  # Only the first recipe's output existed at opening.
        self.select(10)
        self.assertEqual(self.shown, [(10, 20, 100)])
        self.select(20)  # The server has replaced the old part in the bag.
        self.assertEqual(self.shown, [(20, 30, 200)])
        self.assertEqual(self.created, [(0, 20), (1, 30)])

    def test_repeated_selection_reuses_existing_preview(self):
        for _ in range(4):
            self.select(20)
        self.assertEqual(self.created, [(1, 30)])
        self.assertEqual(self.shown, [(20, 30, 200)])

    def test_cold_output_receives_recipe_price_before_display(self):
        self.select(20)
        self.assertEqual(self.shown, [(20, 30, 200)])

    def test_zero_price_weapon_recipe_is_preserved(self):
        self.npc.upgradeCosts[1] = 0
        self.select(20)
        self.assertEqual(self.shown, [(20, 30, 0)])

    def test_last_tier_modified_or_empty_selection_clears_old_preview(self):
        for type_id in (30, 999, None):
            self.select(10)
            self.select(type_id)
            self.assertEqual(self.shown, [])
        self.assertEqual(self.created, [(0, 20)])

    def test_shared_output_types_keep_separate_recipe_prices(self):
        self.upgrade.neededList = [10, 10]
        self.upgrade.upgradedList = [30, 30]
        self.select(10)
        self.assertEqual(self.shown, [(10, 30, 100), (10, 30, 200)])
        self.assertEqual(self.created, [(0, 30), (1, 30)])

    def test_incomplete_recipe_does_not_make_an_undefined_preview(self):
        self.npc.upgradeCosts = [100]
        self.select(20)
        self.assertEqual(self.created, [])
        self.assertEqual(self.shown, [])


if __name__ == '__main__':
    unittest.main()
