import sys
import types
import unittest
from unittest.mock import Mock, patch

from source.utility import action_gate


class ActionGateTests(unittest.TestCase):
    def setUp(self):
        action_gate._last_check = 0.0
        action_gate._state.recovery_depth = 0

    def test_before_action_throttles_state_checks(self):
        player_state = types.SimpleNamespace(check_disconnected=Mock())
        player_package = types.ModuleType("source.ASA.player")
        player_package.player_state = player_state

        with (
            patch.dict(sys.modules, {"source.ASA.player": player_package}),
            patch.object(action_gate.ark_runtime, "wait_until_ready"),
            patch.object(action_gate.time, "monotonic", side_effect=[1.0, 1.1, 1.3]),
        ):
            action_gate.before_ark_action()
            action_gate.before_ark_action()
            action_gate.before_ark_action()

        self.assertEqual(player_state.check_disconnected.call_count, 2)

    def test_recovery_scope_bypasses_state_check(self):
        player_state = types.SimpleNamespace(check_disconnected=Mock())
        player_package = types.ModuleType("source.ASA.player")
        player_package.player_state = player_state

        with (
            patch.dict(sys.modules, {"source.ASA.player": player_package}),
            patch.object(action_gate.ark_runtime, "wait_until_ready"),
            action_gate.recovery_scope(),
        ):
            action_gate.before_ark_action()

        player_state.check_disconnected.assert_not_called()


if __name__ == "__main__":
    unittest.main()
