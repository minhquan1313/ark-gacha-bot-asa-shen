"""Keep opened crystal contents flowing through the remaining Pego routes."""

import unittest
from unittest.mock import Mock, call

from test_deposit_guard import load_deposit_module


class PegoDepositRouteTests(unittest.TestCase):
    def setUp(self):
        """Configure two crystal destinations followed by an active grinder."""
        self.deposit, _, _, self.teleporter, self.player_inventory, _, _ = load_deposit_module()
        self.crystal_routes = [
            {"teleport": name, "check_on_every_dedi": 1, "dedi": {"items": [{}]}, "vault": {"items": []}}
            for name in ("GACHADEDI1", "SSteamForge")
        ]
        self.grinder_route = {
            "teleport": "GACHAGRIND1", "grinder": {"active": True},
            "check_on_every_dedi": 1, "dedi": {"items": [{}]},
        }
        self.deposit.load_deposit_config = Mock(return_value={
            "depositCrystalData": self.crystal_routes,
            "depositGrindableData": [self.grinder_route],
        })
        self.deposit._process_grinder = Mock()
        self.deposit.drop_useless = Mock()

    def test_opened_crystals_continue_through_steamforge_and_grinder(self):
        """Consuming every hotbar crystal must not discard the resulting items."""
        self.deposit.pego.is_crystal_hotbar_visible.side_effect = [True, True, False, False]

        self.assertTrue(self.deposit.deposit_all())

        self.assertEqual(self.teleporter.teleport_not_default.call_args_list, [
            call("GACHADEDI1"), call("SSteamForge"), call("GACHAGRIND1"),
        ])
        self.assertEqual(self.deposit.dedi.open_deposit_all.call_args_list, [
            call("GACHADEDI1", {}), call("SSteamForge", {}), call("GACHAGRIND1", {}),
        ])
        self.assertEqual(self.deposit.utils.press_key.call_count, 10)
        self.deposit._process_grinder.assert_called_once_with(self.grinder_route, "GACHAGRIND1")

    def test_no_initial_crystals_skips_deposit_processing(self):
        """An empty pickup should still stop before processing deposit objects."""
        self.deposit.pego.is_crystal_hotbar_visible.return_value = False

        self.assertTrue(self.deposit.deposit_all())

        self.deposit.dedi.open_deposit_all.assert_not_called()
        self.deposit._process_grinder.assert_not_called()

    def test_confirmed_empty_inventory_stops_remaining_routes(self):
        """Actual inventory checks can still stop the route after depositing all items."""
        self.deposit.pego.is_crystal_hotbar_visible.side_effect = [True, False]
        self.player_inventory.g_last_check_can_transfer = False
        self.deposit.dedi.open_deposit_all.side_effect = lambda *_: setattr(
            self.player_inventory, "g_last_check_can_transfer", False
        )

        self.assertTrue(self.deposit.deposit_all())

        self.teleporter.teleport_not_default.assert_called_once_with("GACHADEDI1")
        self.deposit._process_grinder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
