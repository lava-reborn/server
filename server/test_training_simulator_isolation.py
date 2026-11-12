"""Run the same main-game isolation contract with the simulator engine enabled."""
from unittest.mock import patch

from training import rules, runtime
from test_training_isolation import Isolation


class SimulatorIsolation(Isolation):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        enabled = rules.Rules(revision='simulator-v1', simulator_formulas=True,
                              ammo_modifiers=True)
        selector = patch.object(rules, 'current', return_value=enabled)
        selector.start()
        self.addCleanup(selector.stop)

    def main_state(self):
        for ground in runtime.ACTIVE:
            if ground.owner.inv.store is self.store:
                self.assertTrue(ground.rules.simulator_formulas)
        return super().main_state()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(SimulatorIsolation)
