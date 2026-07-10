import tempfile
import unittest
from pathlib import Path

from source.launcher.config.transfer_helper_config import (
    calculate_same_structure_destination_dedis,
    default_transfer_ui_coords,
    generated_player_bed_names,
    load_transfer_dedis,
    load_transfer_players,
    load_transfer_settings,
    load_transfer_ui_coords,
    missing_runtime_inputs,
    normalize_transfer_dedis,
    normalize_transfer_players,
    normalize_transfer_settings,
    normalize_transfer_ui_coords,
    player_account_count,
    player_bed_name,
    player_bed_name_search_conflicts,
    player_steam_account,
    runtime_account_count,
    save_transfer_players,
    save_transfer_settings,
    save_transfer_ui_coords,
    steam_account_assignment_issues,
    suggested_loop_count,
)

STEAM_ACCOUNTS = [
    {"account_name": "alpha", "most_recent": True, "timestamp": 20},
    {"account_name": "beta", "most_recent": False, "timestamp": 10},
    {"account_name": "gamma", "most_recent": False, "timestamp": 5},
    {"account_name": "delta", "most_recent": False, "timestamp": 1},
]


def assign_steam_accounts(players, names=None):
    names = names or ["alpha", "beta", "gamma", "delta"]
    for player, account_name in zip(players.get("players", []), names):
        player["steam_account"] = account_name
    return players


def valid_transfer_dedis():
    return normalize_transfer_dedis(
        {
            "resource": {
                "teleport": "RESOURCE",
                "transmitter_teleport": "RESOURCE_TX",
                "items": [{"location": {"yaw": 1, "pitch": 2}}],
            },
            "destination": {
                "teleport": "DEST",
                "transmitter_teleport": "DEST_TX",
                "items": [{"location": {"yaw": 3, "pitch": 4}}],
            },
        }
    )


class TransferHelperConfigTests(unittest.TestCase):
    def test_missing_settings_file_creates_loadable_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            settings = load_transfer_settings(path)

            self.assertTrue(path.exists())
            self.assertEqual(settings["resource_server"], "0")
            self.assertEqual(settings["destination_server"], "0")
            self.assertEqual(settings["transfer_start_mode"], "default")
            self.assertEqual(settings["ark_window_ready_timeout"], 120)
            self.assertEqual(settings["ark_launch_attempts"], 10)
            self.assertEqual(settings["steam_restart_interval"], 30)
            self.assertNotIn("transmitter_teleport", settings)
            self.assertNotIn("account_count", settings)
            self.assertNotIn("transfer_retry_delay", settings)

    def test_normalize_settings_ignores_old_account_and_rejects_invalid_loop_values(
        self,
    ):
        settings = normalize_transfer_settings({"account_count": 100})

        self.assertNotIn("account_count", settings)
        with self.assertRaisesRegex(ValueError, "loop_count"):
            normalize_transfer_settings({"loop_count": 0})
        with self.assertRaisesRegex(ValueError, "ark_window_ready_timeout"):
            normalize_transfer_settings({"ark_window_ready_timeout": 0})
        with self.assertRaisesRegex(ValueError, "steam_restart_interval"):
            normalize_transfer_settings({"steam_restart_interval": 0})
        with self.assertRaisesRegex(ValueError, "ping"):
            normalize_transfer_settings({"ping": 125.5})
        self.assertEqual(
            normalize_transfer_settings({"transfer_start_mode": "nope"})[
                "transfer_start_mode"
            ],
            "default",
        )
        self.assertEqual(
            normalize_transfer_settings({"transfer_start_mode": "destinate"})[
                "transfer_start_mode"
            ],
            "destinate",
        )

    def test_load_settings_migrates_missing_steam_restart_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text('{"resource_server": "1234"}', encoding="utf-8")

            settings = load_transfer_settings(path)
            saved = path.read_text(encoding="utf-8")

        self.assertEqual(settings["steam_restart_interval"], 30)
        self.assertEqual(settings["transfer_start_mode"], "default")
        self.assertIn('"steam_restart_interval": 30', saved)
        self.assertIn('"transfer_start_mode": "default"', saved)

    def test_player_bed_names_add_underscore_only_for_search_collision(self):
        self.assertEqual(
            generated_player_bed_names(12),
            [
                "BBedPlayer1",
                "BBedPlayer2",
                "BBedPlayer3",
                "BBedPlayer4",
                "BBedPlayer5",
                "BBedPlayer6",
                "BBedPlayer7",
                "BBedPlayer8",
                "BBedPlayer9",
                "BBedPlayer_10",
                "BBedPlayer_11",
                "BBedPlayer_12",
            ],
        )

    def test_player_bed_name_reads_saved_players(self):
        players = normalize_transfer_players(
            {"players": [{"bed_name": "CustomBed", "steam_account": "alpha"}]}, 2
        )

        self.assertEqual(player_bed_name(players, 1), "CustomBed")
        self.assertEqual(player_bed_name(players, 2), "BBedPlayer2")
        self.assertEqual(player_steam_account(players, 1), "alpha")
        self.assertEqual(player_steam_account(players, 2), "")

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
                    {"bed_name": "Edited2", "steam_account": "beta"},
                ]
            },
            4,
        )

        self.assertEqual(
            players,
            {
                "players": [
                    {"bed_name": "Edited1", "steam_account": ""},
                    {"bed_name": "Edited2", "steam_account": "beta"},
                    {"bed_name": "BBedPlayer3", "steam_account": ""},
                    {"bed_name": "BBedPlayer4", "steam_account": ""},
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
            {
                "players": [
                    {"bed_name": "BBedPlayer1", "steam_account": ""},
                    {"bed_name": "BBedPlayer2", "steam_account": ""},
                ]
            },
        )

    def test_missing_players_file_creates_default_player_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "players.json"

            players = load_transfer_players(path, account_count=3)

            self.assertTrue(path.exists())
            self.assertEqual(
                [player["bed_name"] for player in players["players"]],
                ["BBedPlayer1", "BBedPlayer2", "BBedPlayer3"],
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

            settings = save_transfer_settings(
                {"account_count": 12, "transfer_retry_delay": 5}, path
            )

            self.assertNotIn("account_count", settings)
            self.assertNotIn("transfer_retry_delay", settings)
            self.assertNotIn("account_count", path.read_text(encoding="utf-8"))
            self.assertNotIn("transfer_retry_delay", path.read_text(encoding="utf-8"))

    def test_ui_coords_load_save_is_code_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ui_coords.json"

            coords = load_transfer_ui_coords()
            saved = save_transfer_ui_coords({"steam": {"menu": {"x": 1, "y": 2}}})

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
                "resource": {
                    "teleport": "TRANSFERDEDI",
                    "items": [
                        {
                            "enabled": False,
                            "location": {"yaw": "12.5", "pitch": "-4"},
                            "crouched": True,
                        }
                    ],
                },
                "destination": {"teleport": "DESTDEDI", "items": []},
            }
        )

        self.assertEqual(config["resource"]["teleport"], "TRANSFERDEDI")
        self.assertEqual(config["resource"]["transmitter_teleport"], "")
        self.assertEqual(config["resource"]["items"][0]["location"]["yaw"], 12.5)
        self.assertNotIn("enabled", config["resource"]["items"][0])
        self.assertTrue(config["resource"]["items"][0]["crouched"])
        self.assertEqual(config["destination"]["items"][0]["location"]["yaw"], 0.0)

    def test_flat_dedi_config_migrates_to_resource_and_destination(self):
        config = normalize_transfer_dedis(
            {
                "teleport": "TRANSFERDEDI",
                "items": [
                    {
                        "location": {"yaw": "12.5", "pitch": "-4"},
                        "crouched": True,
                    }
                ],
            }
        )

        self.assertEqual(config["resource"], config["destination"])
        self.assertEqual(config["resource"]["teleport"], "TRANSFERDEDI")
        self.assertEqual(config["resource"]["transmitter_teleport"], "")
        self.assertEqual(config["resource"]["items"][0]["location"]["pitch"], -4.0)

    def test_same_structure_calculation_applies_station_relative_yaw(self):
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "items": [
                        {
                            "location": {"yaw": 50, "pitch": 10},
                            "crouched": True,
                        }
                    ],
                },
                "destination": {
                    "teleport": "DEST",
                    "items": [
                        {
                            "location": {"yaw": 0, "pitch": 0},
                            "crouched": False,
                        }
                    ],
                },
            }
        )

        calculated = calculate_same_structure_destination_dedis(dedis, 10, 20)
        destination = calculated["destination"]["items"][0]

        self.assertEqual(destination["location"], {"yaw": 60.0, "pitch": 10.0})
        self.assertTrue(destination["crouched"])

    def test_same_structure_calculation_wraps_destination_yaw(self):
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "items": [{"location": {"yaw": 170, "pitch": -5}}],
                },
                "destination": {
                    "teleport": "DEST",
                    "items": [{"location": {"yaw": 0, "pitch": 0}}],
                },
            }
        )

        calculated = calculate_same_structure_destination_dedis(dedis, -20, 30)

        self.assertEqual(
            calculated["destination"]["items"][0]["location"],
            {"yaw": -140.0, "pitch": -5.0},
        )

    def test_same_structure_calculation_applies_station_relative_yaw_to_resource(self):
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "items": [
                        {
                            "location": {"yaw": 0, "pitch": 0},
                            "crouched": False,
                        }
                    ],
                },
                "destination": {
                    "teleport": "DEST",
                    "items": [
                        {
                            "location": {"yaw": 60, "pitch": 10},
                            "crouched": True,
                        }
                    ],
                },
            }
        )

        calculated = calculate_same_structure_destination_dedis(
            dedis, 10, 20, target_side="resource"
        )
        resource = calculated["resource"]["items"][0]

        self.assertEqual(resource["location"], {"yaw": 50.0, "pitch": 10.0})
        self.assertTrue(resource["crouched"])

    def test_same_structure_calculation_wraps_resource_yaw(self):
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "items": [{"location": {"yaw": 0, "pitch": 0}}],
                },
                "destination": {
                    "teleport": "DEST",
                    "items": [{"location": {"yaw": 170, "pitch": -5}}],
                },
            }
        )

        calculated = calculate_same_structure_destination_dedis(
            dedis, 30, -20, target_side="resource"
        )

        self.assertEqual(
            calculated["resource"]["items"][0]["location"],
            {"yaw": -140.0, "pitch": -5.0},
        )

    def test_runtime_config_keeps_station_yaws_in_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.json"
            dedis_path = root / "dedis.json"
            players_path = root / "players.json"
            settings_path.write_text(
                '{"resource_station_yaw": "-10.5", "destination_station_yaw": "20"}',
                encoding="utf-8",
            )
            dedis_path.write_text(
                '{"resource": {"teleport": "R", "items": []},'
                ' "destination": {"teleport": "D", "items": []}}',
                encoding="utf-8",
            )
            players_path.write_text(
                '{"players": [{"bed_name": "A"}]}',
                encoding="utf-8",
            )
            import source.launcher.config.transfer_helper_config as config_module

            old_paths = (
                config_module.TRANSFER_SETTINGS_PATH,
                config_module.TRANSFER_DEDIS_PATH,
                config_module.TRANSFER_PLAYERS_PATH,
            )
            config_module.TRANSFER_SETTINGS_PATH = settings_path
            config_module.TRANSFER_DEDIS_PATH = dedis_path
            config_module.TRANSFER_PLAYERS_PATH = players_path
            try:
                config = config_module.load_transfer_runtime_config(
                    create_missing=False
                )
            finally:
                (
                    config_module.TRANSFER_SETTINGS_PATH,
                    config_module.TRANSFER_DEDIS_PATH,
                    config_module.TRANSFER_PLAYERS_PATH,
                ) = old_paths

        self.assertEqual(config["settings"]["resource_station_yaw"], -10.5)
        self.assertEqual(config["settings"]["destination_station_yaw"], 20.0)
        self.assertNotIn("station_yaw", config["dedis"]["resource"])
        self.assertNotIn("station_yaw", config["dedis"]["destination"])

    def test_runtime_config_migrates_legacy_shared_transmitter_to_dedis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.json"
            dedis_path = root / "dedis.json"
            players_path = root / "players.json"
            settings_path.write_text(
                '{"transmitter_teleport": "LEGACY_TX"}',
                encoding="utf-8",
            )
            dedis_path.write_text(
                '{"resource": {"teleport": "R", "items": []},'
                ' "destination": {"teleport": "D", "items": []}}',
                encoding="utf-8",
            )
            players_path.write_text(
                '{"players": [{"bed_name": "A"}]}',
                encoding="utf-8",
            )
            import source.launcher.config.transfer_helper_config as config_module

            old_paths = (
                config_module.TRANSFER_SETTINGS_PATH,
                config_module.TRANSFER_DEDIS_PATH,
                config_module.TRANSFER_PLAYERS_PATH,
            )
            config_module.TRANSFER_SETTINGS_PATH = settings_path
            config_module.TRANSFER_DEDIS_PATH = dedis_path
            config_module.TRANSFER_PLAYERS_PATH = players_path
            try:
                config = config_module.load_transfer_runtime_config()
            finally:
                (
                    config_module.TRANSFER_SETTINGS_PATH,
                    config_module.TRANSFER_DEDIS_PATH,
                    config_module.TRANSFER_PLAYERS_PATH,
                ) = old_paths

        self.assertNotIn("transmitter_teleport", config["settings"])
        self.assertEqual(
            config["dedis"]["resource"]["transmitter_teleport"], "LEGACY_TX"
        )
        self.assertEqual(
            config["dedis"]["destination"]["transmitter_teleport"], "LEGACY_TX"
        )

    def test_missing_dedis_file_creates_default_route(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dedis.json"

            dedis = load_transfer_dedis(path)

            self.assertTrue(path.exists())
            self.assertEqual(
                dedis["resource"]["transmitter_teleport"], "TRANSFER_TTRANS"
            )
            self.assertEqual(
                dedis["destination"]["transmitter_teleport"], "TRANSFER_TTRANS"
            )
            self.assertEqual(len(dedis["resource"]["items"]), 0)
            self.assertEqual(len(dedis["destination"]["items"]), 0)

    def test_steam_account_assignment_requires_unique_accounts(self):
        players = normalize_transfer_players(
            {
                "players": [
                    {"bed_name": "P1", "steam_account": "alpha"},
                    {"bed_name": "P2", "steam_account": "alpha"},
                    {"bed_name": "P3", "steam_account": ""},
                ]
            },
            3,
        )

        issues = steam_account_assignment_issues(players, STEAM_ACCOUNTS)

        self.assertIn("players[2].steam_account duplicates player 1", issues)
        self.assertIn("players[3].steam_account is required", issues)

    def test_steam_account_assignment_blocks_first_player_not_most_recent(self):
        players = assign_steam_accounts(
            normalize_transfer_players({}, 2), ["beta", "alpha"]
        )

        issues = steam_account_assignment_issues(players, STEAM_ACCOUNTS)

        self.assertIn(
            "players[1].steam_account must match Steam MostRecent account", issues
        )

    def test_steam_account_assignment_allows_non_first_start_account(self):
        players = assign_steam_accounts(
            normalize_transfer_players({}, 3), ["beta", "gamma", "alpha"]
        )

        issues = steam_account_assignment_issues(
            players, STEAM_ACCOUNTS, start_account=3
        )

        self.assertNotIn(
            "players[1].steam_account must match Steam MostRecent account", issues
        )

    def test_non_first_start_account_keeps_other_steam_validation(self):
        players = assign_steam_accounts(
            normalize_transfer_players({}, 3), ["beta", "beta", ""]
        )

        issues = steam_account_assignment_issues(
            players, STEAM_ACCOUNTS, start_account=2
        )

        self.assertIn("players[2].steam_account duplicates player 1", issues)
        self.assertIn("players[3].steam_account is required", issues)

    def test_optional_steam_launch_dialog_inputs_do_not_block_validation(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
            }
        )
        dedis = valid_transfer_dedis()
        coords = default_transfer_ui_coords()
        players = assign_steam_accounts(normalize_transfer_players({}, 2))

        missing = missing_runtime_inputs(
            settings, dedis, coords, players, steam_accounts=STEAM_ACCOUNTS
        )

        self.assertFalse(any(item.startswith("ui_coords.steam") for item in missing))

    def test_steam_launch_dialog_defaults_are_not_transfer_helper_config(self):
        steam = default_transfer_ui_coords()["steam"]

        self.assertNotIn("launch_option_template", steam)
        self.assertNotIn("launch_option_checkbox", steam)
        self.assertNotIn("launch_option_play", steam)
        self.assertNotIn("cloud_sync_conflict_template", steam)
        self.assertNotIn("cloud_sync_conflict_play", steam)
        self.assertNotIn("launch_option_region", steam)
        self.assertNotIn("cloud_sync_conflict_region", steam)
        self.assertNotIn("has_failure_template", steam)

    def test_ui_coords_defaults_exclude_retired_transfer_overrides(self):
        coords = default_transfer_ui_coords()

        self.assertNotIn("transfer", coords)

    def test_missing_destination_dedi_items_are_padded_with_blank_defaults(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
            }
        )
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "transmitter_teleport": "RESOURCE_TX",
                    "items": [{"location": {"yaw": 1, "pitch": 2}}],
                },
                "destination": {
                    "teleport": "",
                    "transmitter_teleport": "DEST_TX",
                    "items": [],
                },
            }
        )
        coords = default_transfer_ui_coords()
        players = normalize_transfer_players({}, 1)

        missing = missing_runtime_inputs(settings, dedis, coords, players)

        self.assertIn("dedis.destination.teleport", missing)
        self.assertNotIn("dedis.destination.items must include at least one dedi", missing)
        self.assertEqual(dedis["destination"]["items"][0]["location"]["yaw"], 0.0)

    def test_missing_transmitter_teleports_are_validated_per_route(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
            }
        )
        dedis = normalize_transfer_dedis(
            {
                "resource": {
                    "teleport": "RESOURCE",
                    "items": [{"location": {"yaw": 1, "pitch": 2}}],
                },
                "destination": {
                    "teleport": "DEST",
                    "items": [{"location": {"yaw": 3, "pitch": 4}}],
                },
            }
        )
        players = normalize_transfer_players({}, 1)

        missing = missing_runtime_inputs(settings, dedis, players)

        self.assertIn("dedis.resource.transmitter_teleport", missing)
        self.assertIn("dedis.destination.transmitter_teleport", missing)

    def test_legacy_transfer_dedi_overrides_are_discarded_and_not_validated(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
            }
        )
        dedis = valid_transfer_dedis()
        coords = normalize_transfer_ui_coords(
            {
                "transfer": {
                    "dedi_deposit_ready_template": "legacy.png",
                    "dedi_deposit_ready_region": {},
                    "dedi_init_click": {},
                    "dedi_open_timeout": 1,
                    "dedi_init_attempts": 1,
                }
            }
        )
        players = normalize_transfer_players({}, 1)

        missing = missing_runtime_inputs(settings, dedis, coords, players)

        self.assertNotIn("transfer", coords)
        self.assertFalse(any(item.startswith("ui_coords.transfer") for item in missing))

    def test_validation_blocks_zero_players(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
            }
        )
        dedis = valid_transfer_dedis()
        coords = default_transfer_ui_coords()

        missing = missing_runtime_inputs(settings, dedis, coords, {"players": []})

        self.assertIn("players must include at least one player", missing)


if __name__ == "__main__":
    unittest.main()
