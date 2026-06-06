import tempfile
import unittest
from pathlib import Path

from source.launcher.transfer_helper_config import (
    account_slot_for_target,
    default_transfer_ui_coords,
    displayed_account_order,
    generated_player_bed_names,
    load_transfer_dedis,
    load_transfer_players,
    load_transfer_settings,
    load_transfer_ui_coords,
    missing_runtime_inputs,
    normalize_transfer_players,
    normalize_transfer_dedis,
    normalize_transfer_settings,
    player_account_count,
    player_bed_name,
    player_bed_name_search_conflicts,
    runtime_account_count,
    save_transfer_players,
    save_transfer_settings,
    save_transfer_ui_coords,
    suggested_loop_count,
)


class TransferHelperConfigTests(unittest.TestCase):
    def test_missing_settings_file_creates_loadable_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            settings = load_transfer_settings(path)

            self.assertTrue(path.exists())
            self.assertEqual(settings["resource_server"], "0")
            self.assertEqual(settings["destination_server"], "0")
            self.assertNotIn("account_count", settings)

    def test_normalize_settings_ignores_old_account_and_rejects_invalid_loop_values(
        self,
    ):
        settings = normalize_transfer_settings({"account_count": 100})

        self.assertNotIn("account_count", settings)
        with self.assertRaisesRegex(ValueError, "loop_count"):
            normalize_transfer_settings({"loop_count": 0})

    def test_player_bed_names_add_underscore_only_for_search_collision(self):
        self.assertEqual(
            generated_player_bed_names(12),
            [
                "Player1",
                "Player2",
                "Player3",
                "Player4",
                "Player5",
                "Player6",
                "Player7",
                "Player8",
                "Player9",
                "Player_10",
                "Player_11",
                "Player_12",
            ],
        )

    def test_player_bed_name_reads_saved_players(self):
        players = normalize_transfer_players(
            {"players": [{"bed_name": "CustomBed"}]}, 2
        )

        self.assertEqual(player_bed_name(players, 1), "CustomBed")
        self.assertEqual(player_bed_name(players, 2), "Player2")

    def test_player_bed_name_search_conflicts_use_prefix_matching(self):
        conflicts = player_bed_name_search_conflicts(
            {"players": [{"bed_name": "Player1"}, {"bed_name": "Player10"}]}
        )

        self.assertEqual(conflicts, {0: ["Player10"]})

    def test_player_bed_name_search_conflicts_include_duplicates(self):
        conflicts = player_bed_name_search_conflicts(
            {"players": [{"bed_name": "Player2"}, {"bed_name": "Player2"}]}
        )

        self.assertEqual(conflicts, {0: ["Player2"], 1: ["Player2"]})

    def test_player_bed_name_search_conflicts_allow_underscored_names(self):
        conflicts = player_bed_name_search_conflicts(
            {"players": [{"bed_name": "Player_1"}, {"bed_name": "Player10"}]}
        )

        self.assertEqual(conflicts, {})

    def test_transfer_players_load_save_preserves_edits_and_appends_missing(self):
        players = normalize_transfer_players(
            {
                "players": [
                    {"bed_name": "Edited1"},
                    {"bed_name": "Edited2"},
                ]
            },
            4,
        )

        self.assertEqual(
            players,
            {
                "players": [
                    {"bed_name": "Edited1"},
                    {"bed_name": "Edited2"},
                    {"bed_name": "Player3"},
                    {"bed_name": "Player4"},
                ]
            },
        )

    def test_transfer_players_allow_zero_account_reset(self):
        self.assertEqual(normalize_transfer_players({}, 0), {"players": []})

    def test_transfer_players_save_and_load_zero_accounts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "players.json"

            saved = save_transfer_players({"players": [{"bed_name": "Old"}]}, path, 0)
            loaded = load_transfer_players(path)

            self.assertEqual(saved, {"players": []})
            self.assertEqual(loaded, {"players": []})

    def test_transfer_players_regenerate_after_zero_account_reset(self):
        players = normalize_transfer_players({"players": []}, 2)

        self.assertEqual(
            players,
            {"players": [{"bed_name": "Player1"}, {"bed_name": "Player2"}]},
        )

    def test_missing_players_file_creates_default_player_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "players.json"

            players = load_transfer_players(path, account_count=3)

            self.assertTrue(path.exists())
            self.assertEqual(
                [player["bed_name"] for player in players["players"]],
                ["Player1", "Player2", "Player3"],
            )

    def test_loading_existing_players_preserves_player_row_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "players.json"
            path.write_text(
                '{"players": [{"bed_name": "A"}, {"bed_name": "B"}]}',
                encoding="utf-8",
            )

            players = load_transfer_players(path)

            self.assertEqual(
                [player["bed_name"] for player in players["players"]],
                ["A", "B"],
            )

    def test_player_count_can_exceed_runtime_cap(self):
        players = normalize_transfer_players({}, 12)

        self.assertEqual(player_account_count(players), 12)
        self.assertEqual(runtime_account_count(players), 4)

    def test_save_settings_does_not_persist_old_account_count_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            settings = save_transfer_settings({"account_count": 12}, path)

            self.assertNotIn("account_count", settings)
            self.assertNotIn("account_count", path.read_text(encoding="utf-8"))

    def test_ui_coords_load_save_is_code_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ui_coords.json"

            coords = load_transfer_ui_coords(path)
            saved = save_transfer_ui_coords({"steam": {"menu": {"x": 1, "y": 2}}}, path)

            self.assertFalse(path.exists())
            self.assertIn("steam", coords)
            self.assertEqual(saved["steam"]["menu"], {"x": 1, "y": 2})

    def test_normalize_settings_drops_old_bed_prefix_keys(self):
        settings = normalize_transfer_settings(
            {"bed_prefix": "BedPlayer", "bed_prefix_pad_start": 2}
        )

        self.assertNotIn("bed_prefix", settings)
        self.assertNotIn("bed_prefix_pad_start", settings)

    def test_suggested_loop_count_ceilings_dedi_transfer_capacity(self):
        self.assertEqual(suggested_loop_count(1, 4), 2)
        self.assertEqual(suggested_loop_count(2, 4), 3)
        self.assertEqual(suggested_loop_count(3, 2), 9)

    def test_dedi_config_normalizes_items_without_enabled_flag(self):
        config = normalize_transfer_dedis(
            {
                "teleport": "TRANSFERDEDI",
                "items": [
                    {
                        "enabled": False,
                        "location": {"yaw": "12.5", "pitch": "-4"},
                        "crouched": True,
                    }
                ],
            }
        )

        self.assertEqual(config["teleport"], "TRANSFERDEDI")
        self.assertEqual(config["items"][0]["location"]["yaw"], 12.5)
        self.assertNotIn("enabled", config["items"][0])
        self.assertTrue(config["items"][0]["crouched"])

    def test_missing_dedis_file_creates_default_route(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dedis.json"

            dedis = load_transfer_dedis(path)

            self.assertTrue(path.exists())
            self.assertEqual(len(dedis["items"]), 1)

    def test_account_display_order_places_current_account_first(self):
        self.assertEqual(displayed_account_order(3, 1), [1, 2, 3])
        self.assertEqual(displayed_account_order(3, 2), [2, 1, 3])
        self.assertEqual(displayed_account_order(3, 3), [3, 1, 2])

    def test_account_slot_for_target_uses_reordered_picker_slots(self):
        coords = default_transfer_ui_coords()

        self.assertEqual(
            account_slot_for_target(coords, 3, current_account=2, target_account=3),
            {"x": 447, "y": 242},
        )
        self.assertIsNone(
            account_slot_for_target(coords, 3, current_account=2, target_account=2)
        )

    def test_validation_blocks_four_accounts_without_four_slot_map(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
                "transmitter_teleport": "TX",
            }
        )
        dedis = normalize_transfer_dedis({"teleport": "DEDI"})
        coords = default_transfer_ui_coords()
        players = normalize_transfer_players({}, 4)

        missing = missing_runtime_inputs(settings, dedis, coords, players)

        self.assertIn("ui_coords.steam.account_slots.4", missing)

    def test_validation_blocks_zero_players(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
                "transmitter_teleport": "TX",
            }
        )
        dedis = normalize_transfer_dedis({"teleport": "DEDI"})
        coords = default_transfer_ui_coords()

        missing = missing_runtime_inputs(settings, dedis, coords, {"players": []})

        self.assertIn("players must include at least one player", missing)


if __name__ == "__main__":
    unittest.main()
