import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from source.launcher import ark_game_setup
from source.launcher.ark_game_setup import (
    DisplayMode,
    clear_restore_state,
    find_game_user_input_path,
    find_game_user_settings_path,
    parse_steam_library_paths,
    patch_game_settings,
    restore_game_settings,
    save_restore_state_once,
)


class ArkGameSetupTests(unittest.TestCase):
    def test_offline_input_lookup_does_not_restart_steam(self):
        with (
            patch.object(
                ark_game_setup.steam_accounts,
                "find_running_steam_dir",
                side_effect=ark_game_setup.steam_accounts.SteamNotRunning(
                    "steam.exe is not running"
                ),
            ),
            patch.object(
                ark_game_setup.steam_accounts, "restart_steam"
            ) as restart_steam,
        ):
            with self.assertRaises(ark_game_setup.steam_accounts.SteamNotRunning):
                find_game_user_input_path(restart_steam_if_missing=False)

        restart_steam.assert_not_called()

    def test_parse_steam_library_paths_extracts_multiple_paths(self):
        paths = parse_steam_library_paths(
            """
            "libraryfolders"
            {
                "0" { "path" "C:\\\\Program Files (x86)\\\\Steam" }
                "1" { "path" "E:\\\\SteamLibrary" }
            }
            """
        )

        self.assertEqual(
            paths,
            [
                Path("C:\\Program Files (x86)\\Steam"),
                Path("E:\\SteamLibrary"),
            ],
        )

    def test_find_game_user_settings_path_from_running_steam_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steam_root = root / "Steam"
            library = root / "SteamLibrary"
            ini_path = (
                library
                / "steamapps"
                / "common"
                / "ARK Survival Ascended"
                / "ShooterGame"
                / "Saved"
                / "Config"
                / "Windows"
                / "GameUserSettings.ini"
            )
            ini_path.parent.mkdir(parents=True)
            ini_path.write_text("ResolutionSizeX=2560\n", encoding="utf-8")
            (steam_root / "steamapps").mkdir(parents=True)
            (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{library}" }} }}',
                encoding="utf-8",
            )

            with patch(
                "source.launcher.ark_game_setup.find_running_steam_dir",
                return_value=steam_root,
            ):
                self.assertEqual(find_game_user_settings_path(), ini_path)

    def test_find_running_steam_dir_uses_process_exe_location(self):
        steam_process = types.SimpleNamespace(
            info={"name": "steam.exe", "exe": "C:\\Steam\\steam.exe"}
        )
        fake_psutil = types.SimpleNamespace(
            process_iter=Mock(return_value=[steam_process]),
            AccessDenied=RuntimeError,
            NoSuchProcess=RuntimeError,
        )

        with patch.object(ark_game_setup, "psutil", fake_psutil):
            self.assertEqual(ark_game_setup.find_running_steam_dir(), Path("C:\\Steam"))

    def test_restore_state_is_saved_once_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "restore.json"
            backup_path = root / "backup.ini"
            settings_path = root / "GameUserSettings.ini"

            with patch(
                "source.launcher.ark_game_setup.get_current_display_mode",
                return_value=DisplayMode(2560, 1440, 144),
            ) as get_mode:
                first = save_restore_state_once(
                    settings_path, state_path=state_path, backup_path=backup_path
                )
                second = save_restore_state_once(
                    root / "other.ini",
                    state_path=state_path,
                    backup_path=root / "x.ini",
                )

            self.assertEqual(first, second)
            self.assertEqual(get_mode.call_count, 1)
            self.assertEqual(first["display_mode"]["width"], 2560)
            self.assertEqual(first["settings_path"], str(settings_path))
            self.assertEqual(first["backup_path"], str(backup_path))

    def test_patch_game_settings_updates_existing_keys_and_adds_missing_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "GameUserSettings.ini"
            settings_path.write_text(
                "[ScalabilityGroups]\n"
                "ResolutionSizeX=2560\n"
                "ResolutionSizeY=1440\n"
                "MasterAudioVolume=1.000000\n"
                "UnrelatedKey=keep\n",
                encoding="utf-8",
            )

            patch_game_settings(
                settings_path,
                {
                    "ResolutionSizeX": "1920",
                    "ResolutionSizeY": "1080",
                    "MasterAudioVolume": "0.050000",
                    "FrameGenerationMethod": "0",
                },
            )

            text = settings_path.read_text(encoding="utf-8")
            self.assertIn("ResolutionSizeX=1920\n", text)
            self.assertIn("ResolutionSizeY=1080\n", text)
            self.assertIn("MasterAudioVolume=0.050000\n", text)
            self.assertIn("UnrelatedKey=keep\n", text)
            self.assertTrue(text.endswith("FrameGenerationMethod=0\n"))

    def test_normal_launch_prepares_full_game_and_input_settings(self):
        settings_path = Path("GameUserSettings.ini")
        input_path = Path("Input.ini")
        state = {"display_mode": {"frequency": 144}}

        with (
            patch.object(
                ark_game_setup,
                "find_game_user_settings_path",
                return_value=settings_path,
            ),
            patch.object(
                ark_game_setup, "find_game_user_input_path", return_value=input_path
            ),
            patch.object(ark_game_setup, "restore_state_exists", return_value=True),
            patch.object(ark_game_setup, "load_restore_state", return_value=state),
            patch.object(ark_game_setup, "apply_display_mode") as apply_display,
            patch.object(ark_game_setup, "kill_running_ark") as kill_ark,
            patch.object(ark_game_setup, "patch_game_settings") as patch_settings,
            patch.object(ark_game_setup, "launch_ark_through_steam") as launch_ark,
        ):
            result = ark_game_setup.prepare_and_launch_game()

        apply_display.assert_called_once_with(DisplayMode(1920, 1080, 144))
        kill_ark.assert_called_once_with()
        self.assertEqual(
            patch_settings.call_args_list,
            [
                unittest.mock.call(settings_path, ark_game_setup.TARGET_GAME_SETTINGS),
                unittest.mock.call(
                    input_path, ark_game_setup.TARGET_GAME_INPUT_SETTINGS
                ),
            ],
        )
        launch_ark.assert_called_once_with()
        self.assertEqual(result, f"{settings_path} | {input_path}")

    def test_resolution_only_launch_uses_normal_lifecycle_without_input_settings(self):
        settings_path = Path("GameUserSettings.ini")
        state = {"display_mode": {"frequency": 144}}

        with (
            patch.object(
                ark_game_setup,
                "find_game_user_settings_path",
                return_value=settings_path,
            ),
            patch.object(ark_game_setup, "find_game_user_input_path") as find_input,
            patch.object(ark_game_setup, "restore_state_exists", return_value=False),
            patch.object(ark_game_setup, "backup_game_settings_once") as backup,
            patch.object(
                ark_game_setup, "save_restore_state_once", return_value=state
            ) as save_state,
            patch.object(ark_game_setup, "apply_display_mode") as apply_display,
            patch.object(ark_game_setup, "kill_running_ark") as kill_ark,
            patch.object(ark_game_setup, "patch_game_settings") as patch_settings,
            patch.object(ark_game_setup, "launch_ark_through_steam") as launch_ark,
        ):
            result = ark_game_setup.prepare_and_launch_game_with_display_settings()

        find_input.assert_not_called()
        backup.assert_called_once_with(settings_path, ark_game_setup.CONFIG_BACKUP_PATH)
        save_state.assert_called_once_with(
            settings_path, backup_path=ark_game_setup.CONFIG_BACKUP_PATH
        )
        apply_display.assert_called_once_with(DisplayMode(1920, 1080, 144))
        kill_ark.assert_called_once_with()
        patch_settings.assert_called_once_with(
            settings_path, ark_game_setup.TARGET_GAME_DISPLAY_SETTINGS
        )
        launch_ark.assert_called_once_with()
        self.assertEqual(result, str(settings_path))

    def test_restore_game_settings_copies_backup_and_removes_restore_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "restore.json"
            backup_path = root / "backup.ini"
            settings_path = root / "GameUserSettings.ini"
            backup_path.write_text("original\n", encoding="utf-8")
            settings_path.write_text("patched\n", encoding="utf-8")
            state_path.write_text(
                json.dumps(
                    {
                        "display_mode": {
                            "width": 2560,
                            "height": 1440,
                            "frequency": 144,
                        },
                        "settings_path": str(settings_path),
                        "backup_path": str(backup_path),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch("source.launcher.ark_game_setup.kill_running_ark") as kill,
                patch("source.launcher.ark_game_setup.apply_display_mode") as apply,
            ):
                restored = restore_game_settings(state_path=state_path)

            self.assertEqual(restored, settings_path)
            self.assertEqual(settings_path.read_text(encoding="utf-8"), "original\n")
            self.assertFalse(state_path.exists())
            self.assertFalse(backup_path.exists())
            kill.assert_called_once_with()
            apply.assert_called_once_with(DisplayMode(2560, 1440, 144))

    def test_restore_game_settings_kills_ark_before_restore_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "restore.json"
            backup_path = root / "backup.ini"
            settings_path = root / "GameUserSettings.ini"
            backup_path.write_text("original\n", encoding="utf-8")
            state_path.write_text(
                json.dumps(
                    {
                        "display_mode": {
                            "width": 2560,
                            "height": 1440,
                            "frequency": 144,
                        },
                        "settings_path": str(settings_path),
                        "backup_path": str(backup_path),
                    }
                ),
                encoding="utf-8",
            )
            events = []

            with (
                patch(
                    "source.launcher.ark_game_setup.kill_running_ark",
                    side_effect=lambda: events.append("kill"),
                ),
                patch(
                    "source.launcher.ark_game_setup.apply_display_mode",
                    side_effect=lambda _mode: events.append("display"),
                ),
                patch(
                    "source.launcher.ark_game_setup.shutil.copy2",
                    side_effect=lambda _src, _dst: events.append("copy"),
                ),
                patch(
                    "source.launcher.ark_game_setup.clear_restore_state",
                    side_effect=lambda _state_path: events.append("clear"),
                ),
            ):
                restored = restore_game_settings(state_path=state_path)

            self.assertEqual(restored, settings_path)
            self.assertEqual(events, ["kill", "display", "copy", "clear"])

    def test_restore_game_settings_checks_backup_before_display_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "restore.json"
            missing_backup = root / "missing.ini"
            state_path.write_text(
                json.dumps(
                    {
                        "display_mode": {
                            "width": 2560,
                            "height": 1440,
                            "frequency": 144,
                        },
                        "settings_path": str(root / "GameUserSettings.ini"),
                        "backup_path": str(missing_backup),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch("source.launcher.ark_game_setup.kill_running_ark") as kill,
                patch("source.launcher.ark_game_setup.apply_display_mode") as apply,
                self.assertRaisesRegex(RuntimeError, "backup was not found"),
            ):
                restore_game_settings(state_path=state_path)

            kill.assert_not_called()
            apply.assert_not_called()

    def test_kill_running_ark_waits_for_taskkill_command(self):
        with patch("source.launcher.ark_game_setup.subprocess.run") as run:
            ark_game_setup.kill_running_ark()

        run.assert_called_once_with(
            ["taskkill", "/f", "/im", ark_game_setup.ARK_PROCESS_NAME],
            check=False,
            stdout=ark_game_setup.subprocess.DEVNULL,
            stderr=ark_game_setup.subprocess.DEVNULL,
        )

    def test_clear_restore_state_removes_state_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "restore.json"
            backup_path = root / "backup.ini"
            backup_path.write_text("original\n", encoding="utf-8")
            state_path.write_text(
                json.dumps({"backup_path": str(backup_path)}),
                encoding="utf-8",
            )

            clear_restore_state(state_path=state_path)

            self.assertFalse(state_path.exists())
            self.assertFalse(backup_path.exists())


if __name__ == "__main__":
    unittest.main()
