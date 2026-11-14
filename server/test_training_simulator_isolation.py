"""Run the same main-game isolation contract with the simulator engine enabled."""
from unittest.mock import patch

from training import rules, runtime
import test_training_isolation as isolation
import test_training_review as review
import test_training_entry as entry


def enable_simulator(case):
    enabled = rules.Rules(revision='simulator-v1', simulator_formulas=True,
                          ammo_modifiers=True)
    selector = patch.object(rules, 'current', return_value=enabled)
    selector.start()
    case.addCleanup(selector.stop)


class SimulatorReview(review.Review):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        enable_simulator(self)


class SimulatorSoloEntry(entry.SoloEntry):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        enable_simulator(self)


class SimulatorIsolation(isolation.Isolation):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        enable_simulator(self)

    def main_state(self):
        for ground in runtime.ACTIVE:
            if ground.owner.inv.store is self.store:
                self.assertTrue(ground.rules.simulator_formulas)
        return super().main_state()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(SimulatorIsolation, SimulatorReview, SimulatorSoloEntry)
