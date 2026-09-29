import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.launcher import ark_game_setup as setup
from source.utility import screen


def display_layout(
    positions: tuple, adapter_id: int = 17, source_start: int = 0, target_start: int = 100
):
    """Build Windows records with distinct targets and caller-selected positions."""
    paths = (screen.DISPLAYCONFIG_PATH_INFO * len(positions))()
    modes = (screen.DISPLAYCONFIG_MODE_INFO * (2 * len(positions)))()
    for index, (x, y) in enumerate(positions):
        path = paths[index]
        path.flags = screen.DISPLAYCONFIG_PATH_ACTIVE
        path.sourceInfo.id = source_start + index
        path.sourceInfo.adapterId.LowPart = adapter_id
        path.sourceInfo.modeInfoIdx = index * 2
        path.targetInfo.id = target_start + index
        path.targetInfo.adapterId.LowPart = adapter_id
        path.targetInfo.modeInfoIdx = index * 2 + 1
        path.targetInfo.targetAvailable = 1
        path.targetInfo.rotation = 1 + index
        path.targetInfo.scaling = 1
        path.targetInfo.refreshRate.Numerator = 144000
        path.targetInfo.refreshRate.Denominator = 1001
        path.targetInfo.scanLineOrdering = 1
        source = modes[index * 2]
        source.infoType = screen.DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
        source.id = source_start + index
        source.adapterId.LowPart = adapter_id
        source.sourceMode.width = 2560
        source.sourceMode.height = 1440
        source.sourceMode.pixelFormat = 4
        source.sourceMode.position.x = x
        source.sourceMode.position.y = y
        target = modes[index * 2 + 1]
        target.infoType = 2
        target.id = target_start + index
        target.adapterId.LowPart = adapter_id
        signal = target.targetMode.targetVideoSignalInfo
        signal.pixelRate = 600000000
        signal.hSyncFreq.Numerator = 600000000
        signal.hSyncFreq.Denominator = 2720
        signal.vSyncFreq.Numerator = 144000
        signal.vSyncFreq.Denominator = 1001
        signal.activeSize.cx = 2560
        signal.activeSize.cy = 1440
        signal.totalSize.cx = 2720
        signal.totalSize.cy = 1481
        signal.videoStandard = 255
        signal.scanLineOrdering = 1
    return paths, len(paths), modes, len(modes)


class DisplayConfigTests(unittest.TestCase):
    def setUp(self):
        """Prevent every test from accessing the real Windows display APIs."""
        self.user32 = Mock()
        self.user32.SetDisplayConfig.return_value = 0
        self.enterContext(
            patch.object(screen.ctypes, "windll", SimpleNamespace(user32=self.user32))
        )
        self.monitor_paths = {}
        self.enterContext(
            patch.object(
                screen,
                "_get_monitor_device_path",
                side_effect=lambda target: self.monitor_paths.get(
                    (target.adapterId.LowPart, target.id), f"monitor-{target.id}"
                ),
            )
        )

    def capture(self, layout: tuple):
        """Capture a JSON round trip of mocked active displays."""
        with patch.object(screen, "_query_active_display_config", return_value=layout):
            return json.loads(json.dumps(screen.capture_display_config()))

    def restore(self, snapshot: dict, layout: tuple):
        """Restore against mocked connected displays without touching Windows."""
        with (
            patch.object(screen, "_query_display_config", return_value=layout),
            patch.object(screen, "_query_active_display_config", return_value=layout),
        ):
            screen.restore_display_config(snapshot)

    def assert_semantic_layout(self, original: tuple, applied: tuple):
        """Compare saved mode payloads and layout while allowing new hardware IDs."""
        saved_paths, saved_count, saved_modes, _ = original
        path_count, paths, mode_count, modes, _ = applied
        self.assertEqual(path_count, saved_count)
        self.assertEqual(len(modes), mode_count)
        for index in range(path_count):
            saved = saved_paths[index]
            restored = paths[index]
            source_index = restored.sourceInfo.modeInfoIdx
            target_index = restored.targetInfo.modeInfoIdx
            self.assertLess(source_index, mode_count)
            self.assertLess(target_index, mode_count)
            self.assertEqual(
                bytes(modes[source_index].sourceMode),
                bytes(saved_modes[saved.sourceInfo.modeInfoIdx].sourceMode),
            )
            self.assertEqual(
                bytes(modes[target_index].targetMode),
                bytes(saved_modes[saved.targetInfo.modeInfoIdx].targetMode),
            )
            self.assertEqual(modes[source_index].infoType, 1)
            self.assertEqual(modes[target_index].infoType, 2)
            for attribute in ("rotation", "scaling", "scanLineOrdering"):
                self.assertEqual(
                    getattr(restored.targetInfo, attribute),
                    getattr(saved.targetInfo, attribute),
                )
            self.assertEqual(
                bytes(restored.targetInfo.refreshRate), bytes(saved.targetInfo.refreshRate)
            )
            for endpoint, mode in (
                (restored.sourceInfo, modes[source_index]),
                (restored.targetInfo, modes[target_index]),
            ):
                self.assertEqual(mode.id, endpoint.id)
                self.assertEqual(bytes(mode.adapterId), bytes(endpoint.adapterId))

    def test_single_monitor_does_not_change_displays(self):
        with patch.object(
            screen,
            "_query_active_display_config",
            return_value=display_layout(((0, 0),)),
        ):
            screen.keep_primary_display_only()
        self.user32.SetDisplayConfig.assert_not_called()

    def test_primary_is_selected_by_position_including_external_and_cloned(self):
        for positions, primary_index, clone in (
            (((0, 0), (2560, 0), (-2560, 0)), 0, False),
            (((-2560, 0), (0, 0)), 1, False),
            (((0, 0), (0, 0)), 0, True),
        ):
            with self.subTest(positions=positions):
                layout = display_layout(positions)
                paths, _, modes, mode_count = layout
                if clone:
                    paths[1].sourceInfo = paths[0].sourceInfo
                remaining = (screen.DISPLAYCONFIG_PATH_INFO * 1)(paths[primary_index])
                with patch.object(
                    screen,
                    "_query_active_display_config",
                    side_effect=(layout, (remaining, 1, modes, mode_count)),
                ):
                    screen.keep_primary_display_only()
                args = self.user32.SetDisplayConfig.call_args.args
                self.assertEqual(args[0], 1)
                self.assertEqual(args[1][0].targetInfo.id, 100 + primary_index)
                self.assertEqual(bytes(args[3]), bytes(modes))

    def test_missing_primary_never_changes_displays(self):
        with (
            patch.object(
                screen,
                "_query_active_display_config",
                return_value=display_layout(((2560, 0),)),
            ),
            self.assertRaisesRegex(RuntimeError, "primary"),
        ):
            screen.keep_primary_display_only()
        self.user32.SetDisplayConfig.assert_not_called()

    def test_isolation_api_failure_is_reported(self):
        self.user32.SetDisplayConfig.return_value = 87
        with (
            patch.object(
                screen,
                "_query_active_display_config",
                return_value=display_layout(((0, 0), (2560, 0))),
            ),
            self.assertRaisesRegex(RuntimeError, "Windows result: 87"),
        ):
            screen.keep_primary_display_only()

    def test_isolation_verifies_count_and_target_identity(self):
        original = display_layout(((0, 0), (2560, 0)))
        wrong_target = display_layout(((0, 0),))
        wrong_target[0][0].targetInfo.id = 999
        for remaining in (original, wrong_target):
            with (
                self.subTest(count=remaining[1]),
                patch.object(
                    screen,
                    "_query_active_display_config",
                    side_effect=(original, remaining),
                ),
                self.assertRaisesRegex(RuntimeError, "selected primary"),
            ):
                screen.keep_primary_display_only()

    def test_snapshot_is_version_one_with_monitor_identity_and_semantic_modes(self):
        snapshot = self.capture(display_layout(((-2560, 0), (0, 0))))
        self.assertEqual(snapshot["version"], 1)
        self.assertEqual(
            [monitor["device_path"] for monitor in snapshot["monitors"]],
            ["monitor-100", "monitor-101"],
        )
        self.assertEqual(
            [monitor["group"] for monitor in snapshot["monitors"]], [0, 1]
        )
        self.assertEqual(
            snapshot["monitors"][0]["source_mode"],
            {
                "width": 2560,
                "height": 1440,
                "pixelFormat": 4,
                "position": {"x": -2560, "y": 0},
            },
        )
        serialized = json.dumps(snapshot)
        self.assertNotIn("adapterId", serialized)
        self.assertNotIn("modeInfoIdx", serialized)
        self.assertNotIn("paths", snapshot)
        self.assertNotIn("modes", snapshot)

    def test_restore_rebuilds_all_ids_and_preserves_saved_layout_and_timings(self):
        original = display_layout(((-2560, 0), (0, 0)))
        snapshot = self.capture(original)
        before = json.dumps(snapshot)
        live = display_layout(((0, 0), (2560, 0)), 91, 8, 400)
        self.monitor_paths.update({(91, 400): "MONITOR-100", (91, 401): "monitor-101"})
        self.restore(snapshot, live)
        calls = self.user32.SetDisplayConfig.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0].args[4], screen.SDC_VALIDATE | screen.SDC_USE_SUPPLIED_DISPLAY_CONFIG
        )
        self.assertEqual(
            calls[1].args[4], screen.SDC_APPLY | screen.SDC_USE_SUPPLIED_DISPLAY_CONFIG
        )
        applied = calls[1].args
        self.assert_semantic_layout(original, applied)
        self.assertEqual([path.targetInfo.id for path in applied[1]], [400, 401])
        self.assertEqual({path.sourceInfo.id for path in applied[1]}, {8, 9})
        self.assertTrue(all(mode.adapterId.LowPart == 91 for mode in applied[3]))
        self.assertEqual(json.dumps(snapshot), before)

    def test_inactive_extended_targets_receive_distinct_feasible_sources(self):
        original = display_layout(((0, 0), (2560, 0)))
        snapshot = self.capture(original)
        paths, _, modes, mode_count = display_layout(((0, 0), (2560, 0)), 91, 8, 400)
        paths[1].sourceInfo.id = 8
        paths[1].flags = 0
        paths[1].sourceInfo.modeInfoIdx = 0xFFFFFFFF
        paths[1].targetInfo.modeInfoIdx = 0xFFFFFFFF
        alternatives = (screen.DISPLAYCONFIG_PATH_INFO * 3)(paths[0], paths[1], paths[0])
        alternatives[2].sourceInfo.id = 9
        alternatives[2].flags = 0
        alternatives[2].sourceInfo.modeInfoIdx = 0xFFFFFFFF
        alternatives[2].targetInfo.modeInfoIdx = 0xFFFFFFFF
        self.monitor_paths.update({(91, 400): "monitor-100", (91, 401): "monitor-101"})
        self.restore(snapshot, (alternatives, 3, modes, mode_count))
        applied = self.user32.SetDisplayConfig.call_args.args
        self.assert_semantic_layout(original, applied)
        self.assertEqual(
            [(path.targetInfo.id, path.sourceInfo.id) for path in applied[1]],
            [(400, 9), (401, 8)],
        )
        self.assertTrue(all(path.flags & screen.DISPLAYCONFIG_PATH_ACTIVE for path in applied[1]))

    def test_cloned_monitors_share_one_source_mode_after_restore(self):
        original = display_layout(((0, 0), (0, 0)))
        original[0][1].sourceInfo = original[0][0].sourceInfo
        snapshot = self.capture(original)
        self.assertEqual([entry["group"] for entry in snapshot["monitors"]], [0, 0])
        live = display_layout(((0, 0), (0, 0)), 91, 8, 400)
        live[0][1].sourceInfo.id = 8
        live[0][1].flags = 0
        live[0][1].sourceInfo.modeInfoIdx = 0xFFFFFFFF
        live[0][1].targetInfo.modeInfoIdx = 0xFFFFFFFF
        self.monitor_paths.update({(91, 400): "monitor-100", (91, 401): "monitor-101"})
        self.restore(snapshot, live)
        applied = self.user32.SetDisplayConfig.call_args.args
        self.assert_semantic_layout(original, applied)
        self.assertEqual(applied[2], 3)
        self.assertEqual(
            applied[1][0].sourceInfo.modeInfoIdx, applied[1][1].sourceInfo.modeInfoIdx
        )

    def test_restore_rejects_missing_or_ambiguous_monitor_identity(self):
        for ambiguous in (False, True):
            with self.subTest(ambiguous=ambiguous):
                snapshot = self.capture(
                    display_layout(((0, 0),) if ambiguous else ((0, 0), (2560, 0)))
                )
                live = display_layout(((0, 0), (2560, 0)), 91, 8, 400)
                self.monitor_paths.update(
                    {(91, 400): "monitor-100", (91, 401): "monitor-100" if ambiguous else "other"}
                )
                with self.assertRaises(RuntimeError):
                    self.restore(snapshot, live)
                self.user32.SetDisplayConfig.assert_not_called()

    def test_restore_rejects_unavailable_target_or_impossible_source_assignment(self):
        snapshot = self.capture(display_layout(((0, 0), (2560, 0))))
        for disconnected in (False, True):
            with self.subTest(disconnected=disconnected):
                live = display_layout(((0, 0), (2560, 0)))
                if disconnected:
                    live[0][1].targetInfo.targetAvailable = 0
                else:
                    live[0][1].sourceInfo.id = live[0][0].sourceInfo.id
                with self.assertRaises(RuntimeError):
                    self.restore(snapshot, live)
                self.user32.SetDisplayConfig.assert_not_called()

    def test_restore_rejects_invalid_snapshot_without_apply(self):
        for snapshot in (
            {"version": 2},
            {"version": 1, "monitors": []},
            {"version": 1, "paths": ["00"], "modes": []},
        ):
            with self.subTest(snapshot=snapshot), self.assertRaisesRegex(RuntimeError, "Invalid saved"):
                self.restore(snapshot, display_layout(((0, 0),)))
        self.user32.SetDisplayConfig.assert_not_called()

    def test_restore_rejects_malformed_monitor_fields_before_windows_call(self):
        live = display_layout(((0, 0),))
        original = self.capture(live)
        for field, values in (
            ("device_path", (None, 1, [], {})),
            ("rotation", (-1, 1 << 32, "1", 1.5, None, True)),
            ("scaling", (-1, 1 << 32, "1", 1.5, None, True)),
            ("scan_line_ordering", (-1, 1 << 32, "1", 1.5, None, True)),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    snapshot = json.loads(json.dumps(original))
                    snapshot["monitors"][0][field] = value
                    with self.assertRaises(RuntimeError):
                        self.restore(snapshot, live)
                    self.user32.SetDisplayConfig.assert_not_called()

    def test_validation_failure_never_applies_and_apply_failure_is_reported(self):
        live = display_layout(((0, 0),))
        snapshot = self.capture(live)
        for results in ([87], [0, 87]):
            with self.subTest(results=results):
                self.user32.SetDisplayConfig.reset_mock()
                self.user32.SetDisplayConfig.side_effect = results
                with self.assertRaisesRegex(RuntimeError, "Windows result: 87"):
                    self.restore(snapshot, live)
                self.assertEqual(self.user32.SetDisplayConfig.call_count, len(results))
                self.assertFalse(self.user32.SetDisplayConfig.call_args_list[0].args[4] & screen.SDC_APPLY)

    def test_legacy_single_monitor_snapshot_uses_fresh_ids_and_saved_modes(self):
        original = display_layout(((0, 0),))
        original[0][0].targetInfo.rotation = 3
        original[0][0].targetInfo.scaling = 2
        original[2][0].sourceMode.width = 5120
        snapshot = {
            "version": 1,
            "paths": [bytes(path).hex() for path in original[0]],
            "modes": [bytes(mode).hex() for mode in original[2]],
        }
        live = display_layout(((0, 0),), 91, 8, 400)
        self.restore(snapshot, live)
        applied = self.user32.SetDisplayConfig.call_args.args
        self.assert_semantic_layout(original, applied)
        self.assertEqual(applied[1][0].targetInfo.id, 400)
        self.assertEqual(applied[1][0].sourceInfo.id, 8)
        self.assertTrue(all(mode.adapterId.LowPart == 91 for mode in applied[3]))

    def test_legacy_snapshot_never_guesses_between_multiple_monitors(self):
        for saved_positions, connected_positions in (
            (((0, 0), (2560, 0)), ((0, 0),)),
            (((0, 0),), ((0, 0), (2560, 0))),
        ):
            with self.subTest(saved=saved_positions, connected=connected_positions):
                original = display_layout(saved_positions)
                snapshot = {
                    "version": 1,
                    "paths": [bytes(path).hex() for path in original[0]],
                    "modes": [bytes(mode).hex() for mode in original[2]],
                }
                with self.assertRaises(RuntimeError):
                    self.restore(snapshot, display_layout(connected_positions))
                self.user32.SetDisplayConfig.assert_not_called()


class DisplayLaunchTests(unittest.TestCase):
    def setUp(self):
        """Isolate display, process, and file effects from the user's environment."""
        self.enterContext(
            patch.object(screen.ctypes, "windll", SimpleNamespace(user32=Mock()))
        )
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.state_path = self.root / "restore.json"
        self.backup_path = self.root / "backup.ini"
        self.settings_path = self.root / "GameUserSettings.ini"
        self.backup_path.write_text("original", encoding="utf-8")
        self.settings_path.write_text("modified", encoding="utf-8")
        self.state = {
            "display_mode": {"width": 2560, "height": 1440, "frequency": 144},
            "settings_path": str(self.settings_path),
            "backup_path": str(self.backup_path),
        }
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")
        self.events = []
        self.mocks = {}
        for name in (
            "keep_primary_display_only",
            "apply_display_mode",
            "kill_running_ark",
            "patch_game_settings",
            "launch_ark_through_steam",
            "restore_display_config",
        ):
            self.mocks[name] = self.enterContext(
                patch.object(
                    setup,
                    name,
                    side_effect=lambda *args, name=name: self.events.append(name),
                )
            )
        self.mocks["get_current_display_mode"] = self.enterContext(
            patch.object(
                setup,
                "get_current_display_mode",
                return_value=screen.DisplayMode(1920, 1080, 144),
            )
        )

    def test_layout_is_added_to_legacy_state_once_without_overwriting_backups(self):
        original = dict(self.state)
        with patch.object(
            setup, "capture_display_config", return_value={"version": 1}
        ) as capture:
            setup.save_display_restore_state_once(self.state, self.state_path)
            reloaded = setup.load_restore_state(self.state_path)
            setup.save_display_restore_state_once(reloaded, self.state_path)
        capture.assert_called_once_with()
        self.assertEqual({key: reloaded[key] for key in original}, original)
        self.assertEqual(self.backup_path.read_text(encoding="utf-8"), "original")

    def test_failed_snapshot_write_prevents_isolation(self):
        with (
            patch.object(setup, "capture_display_config", return_value={"version": 1}),
            patch.object(Path, "replace", side_effect=OSError("write failed")),
            self.assertRaises(OSError),
        ):
            setup.save_display_restore_state_once(self.state, self.state_path)
        self.assertNotIn("display_config", self.state)
        self.assertNotIn("display_config", setup.load_restore_state(self.state_path))

    def test_launch_order_right_click_and_isolation_failure(self):
        for normal, failure in ((True, False), (False, False), (True, True)):
            with self.subTest(normal=normal, failure=failure):
                self.events.clear()
                self.mocks["keep_primary_display_only"].side_effect = (
                    RuntimeError("isolation failed")
                    if failure
                    else lambda: self.events.append("keep_primary_display_only")
                )
                with (
                    patch.object(
                        setup,
                        "find_game_user_settings_path",
                        return_value=self.settings_path,
                    ),
                    patch.object(
                        setup,
                        "find_game_user_input_path",
                        return_value=self.root / "Input.ini",
                    ),
                    patch.object(setup, "restore_state_exists", return_value=False),
                    patch.object(
                        setup,
                        "backup_game_settings_once",
                        side_effect=lambda *a: self.events.append("backup"),
                    ),
                    patch.object(
                        setup,
                        "save_restore_state_once",
                        side_effect=lambda *a, **kw: (
                            self.events.append("save") or self.state
                        ),
                    ),
                    patch.object(
                        setup,
                        "save_display_restore_state_once",
                        side_effect=lambda *a: self.events.append("snapshot"),
                    ),
                ):
                    launch = (
                        setup.prepare_and_launch_game
                        if normal
                        else setup.prepare_and_launch_game_with_display_settings
                    )
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, "isolation failed"):
                            launch()
                        self.assertEqual(self.events, ["backup", "save", "snapshot"])
                    else:
                        launch()
                        expected = ["backup", "save"]
                        if normal:
                            expected += ["snapshot", "keep_primary_display_only"]
                        expected += [
                            "apply_display_mode",
                            "kill_running_ark",
                            "patch_game_settings",
                        ]
                        if normal:
                            expected += ["patch_game_settings"]
                        self.assertEqual(
                            self.events, expected + ["launch_ark_through_steam"]
                        )

    def test_restore_order_legacy_compatibility_and_failure_retains_data(self):
        for has_layout, failure in ((True, False), (False, False), (True, True)):
            with self.subTest(has_layout=has_layout, failure=failure):
                self.events.clear()
                state = dict(self.state)
                if has_layout:
                    state["display_config"] = {"version": 1}
                self.state_path.write_text(json.dumps(state), encoding="utf-8")
                self.mocks["restore_display_config"].side_effect = (
                    RuntimeError("monitor disconnected")
                    if failure
                    else lambda *a: self.events.append("restore_display_config")
                )
                with patch.object(setup, "clear_restore_state") as clear:
                    if failure:
                        with self.assertRaisesRegex(
                            RuntimeError, "monitor disconnected"
                        ):
                            setup.restore_game_settings(self.state_path)
                        clear.assert_not_called()
                        self.assertTrue(self.state_path.exists())
                        self.assertTrue(self.backup_path.exists())
                        self.assertEqual(self.events, ["kill_running_ark"])
                    else:
                        setup.restore_game_settings(self.state_path)
                        expected = ["kill_running_ark"]
                        if has_layout:
                            expected += ["restore_display_config"]
                        self.assertEqual(self.events, expected + ["apply_display_mode"])
                        self.assertEqual(
                            self.settings_path.read_text(encoding="utf-8"), "original"
                        )
                        clear.assert_called_once_with(self.state_path)

    def test_restored_original_mode_is_not_reapplied_and_preserves_scaling(self):
        state = {**self.state, "display_config": {"version": 1}}
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        self.mocks["get_current_display_mode"].side_effect = lambda: (
            self.events.append("read_display_mode") or screen.DisplayMode(2560, 1440, 144)
        )
        with patch.object(setup, "clear_restore_state") as clear:
            setup.restore_game_settings(self.state_path)
        self.mocks["apply_display_mode"].assert_not_called()
        self.assertEqual(
            self.events, ["kill_running_ark", "restore_display_config", "read_display_mode"]
        )
        self.assertEqual(self.settings_path.read_text(encoding="utf-8"), "original")
        clear.assert_called_once_with(self.state_path)


if __name__ == "__main__":
    unittest.main()
