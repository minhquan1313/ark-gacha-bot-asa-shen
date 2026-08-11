import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QWidget

import source.utility
from source.launcher import auto_keys
from source.launcher.auto_keys import AutoKeysRuntime
from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.config.constants import AUTO_KEYS_ACTIONS
from source.launcher.gui_parts.runtime import RuntimeGuiMixin
from source.launcher.utils.settings_store import _normalize_settings
from source.utility import local_player


class AutoKeysSettingsTests(unittest.TestCase):
    def test_auto_keys_defaults_are_migrated(self):
        settings = _normalize_settings({})

        self.assertEqual(
            settings["auto_keys"],
            {"enabled": False, "interval": 0.25, "hold_duration": 1.0},
        )

    def test_auto_keys_values_are_nested_and_validated(self):
        settings = _normalize_settings(
            {
                "auto_keys": {
                    "enabled": True,
                    "interval": "0.5",
                    "hold_duration": 2,
                }
            }
        )

        self.assertEqual(settings["auto_keys"]["interval"], 0.5)
        self.assertEqual(settings["auto_keys"]["hold_duration"], 2.0)
        self.assertTrue(settings["auto_keys"]["enabled"])
        self.assertEqual(
            _normalize_settings({"auto_keys": {"interval": 0.1}})["auto_keys"][
                "interval"
            ],
            0.1,
        )
        with self.assertRaises(ValueError):
            _normalize_settings({"auto_keys": {"interval": 0}})

    def test_suspended_ui_persistence_keeps_saved_enabled_preference(self):
        from source.launcher.pages import settings as settings_page

        launcher = settings_page.SettingsPagesMixin()
        launcher.settings = {
            "auto_keys": {"enabled": True, "interval": 0.25, "hold_duration": 1.0}
        }
        launcher.form_values = launcher.settings.copy()
        launcher.auto_keys_enabled_field = Mock(isChecked=Mock(return_value=False))
        launcher.auto_keys_interval_field = Mock(text=Mock(return_value="0.1"))
        launcher.auto_keys_hold_field = Mock(text=Mock(return_value="1.0"))
        launcher.auto_keys_runtime = Mock()
        launcher._auto_keys_are_suspended = Mock(return_value=True)
        launcher._collect_settings = Mock(side_effect=lambda: launcher.form_values)
        launcher.dialog = Mock()
        with patch.object(
            settings_page, "save_settings", side_effect=lambda settings: settings
        ):
            launcher.persist_auto_keys_settings()

        self.assertTrue(launcher.form_values["auto_keys"]["enabled"])
        launcher.auto_keys_runtime.configure.assert_called_once_with(
            launcher.settings, allow_enable=False
        )


class AutoKeysPollingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = AutoKeysRuntime(("Use",))
        self.runtime.enabled = True
        self.runtime.hold_duration = 1.0
        self.binding = ("keyboard", 0x45)
        self.runtime._bindings = {self.binding: "Use"}

    def tearDown(self):
        self.runtime.enabled = False
        self.runtime._repeat_stop_event.set()

    def test_continuous_hold_starts_after_duration(self):
        self.runtime._start_repeat = Mock()

        self.runtime._process_polled_state(self.binding, True, 10.0)
        self.runtime._process_polled_state(self.binding, True, 10.99)
        self.runtime._start_repeat.assert_not_called()
        self.runtime._process_polled_state(self.binding, True, 11.0)

        self.runtime._start_repeat.assert_called_once_with(self.binding)

    def test_release_before_duration_cancels_activation(self):
        self.runtime._start_repeat = Mock()

        self.runtime._process_polled_state(self.binding, True, 10.0)
        self.runtime._process_polled_state(self.binding, False, 10.5)
        self.runtime._process_polled_state(self.binding, False, 11.5)

        self.runtime._start_repeat.assert_not_called()
        self.assertIsNone(self.runtime._pending)

    def test_release_arms_and_second_press_stops_latched_repeat(self):
        self.runtime._active = self.binding
        self.runtime._last_states[self.binding] = True
        self.runtime._stop_repeat = Mock()

        self.runtime._process_polled_state(self.binding, False, 1.0)
        self.assertTrue(self.runtime._stop_armed)
        self.runtime._process_polled_state(self.binding, True, 1.1)

        self.runtime._stop_repeat.assert_called_once_with()

    def test_synthetic_mouse_state_is_ignored(self):
        mouse_binding = ("mouse", 0x01)
        self.runtime._bindings = {mouse_binding: "Fire"}
        self.runtime._active = mouse_binding
        self.runtime._stop_armed = True
        self.runtime._last_states[mouse_binding] = False
        self.runtime._synthetic_down.add(mouse_binding)
        self.runtime._stop_repeat = Mock()

        self.runtime._process_polled_state(mouse_binding, True, 1.0)

        self.runtime._stop_repeat.assert_not_called()
        self.assertFalse(self.runtime._last_states[mouse_binding])

    def test_live_bindings_resolve_left_mouse_e_and_o(self):
        runtime = AutoKeysRuntime(("Fire", "Use", "DropItem"))
        fake_utils = types.SimpleNamespace(
            keymap_return=lambda key: {"E": 0x45, "O": 0x4F}.get(key)
        )
        with (
            patch.object(source.utility, "utils", fake_utils, create=True),
            patch(
                "source.launcher.auto_keys.resolve_supported_keys",
                return_value=(
                    {
                        "Fire": "LeftMouseButton",
                        "Use": "E",
                        "DropItem": "O",
                    },
                    Path("Input.ini"),
                ),
            ),
        ):
            bindings = runtime._resolve_bindings()

        self.assertEqual(bindings[("mouse", 0x01)], "Fire")
        self.assertEqual(bindings[("keyboard", 0x45)], "Use")
        self.assertEqual(bindings[("keyboard", 0x4F)], "DropItem")

    def test_offline_resolver_reads_explicit_input_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "Input.ini"
            input_path.write_text(
                '\n'.join(
                    [
                        'ActionMappings=(ActionName="Fire",Key=LeftMouseButton)',
                        'ActionMappings=(ActionName="Use",Key=E)',
                        'ActionMappings=(ActionName="DropItem",Key=O)',
                    ]
                ),
                encoding="utf-8",
            )
            with patch(
                "source.launcher.ark_game_setup.find_game_user_input_path",
                return_value=input_path,
            ):
                resolved, resolved_path = auto_keys.resolve_supported_keys()

        self.assertEqual(resolved_path, input_path)
        self.assertEqual(
            resolved,
            {"Fire": "LeftMouseButton", "Use": "E", "DropItem": "O"},
        )

    def test_explicit_input_path_does_not_require_running_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "Input.ini"
            input_path.write_text(
                'ActionMappings=(ActionName="Use",Key=E)\n', encoding="utf-8"
            )
            with patch.object(local_player, "get_base_path") as get_base_path:
                self.assertEqual(
                    local_player.get_input_settings("Use", input_path=input_path),
                    "E",
                )

        get_base_path.assert_not_called()

    def test_supported_keys_label_refreshes_after_input_file_change(self):
        from source.launcher.pages import settings as settings_page

        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "Input.ini"
            input_path.write_text("first", encoding="utf-8")
            binding_labels = {action: Mock() for action in AUTO_KEYS_ACTIONS}
            launcher = types.SimpleNamespace(
                auto_keys_supported_binding_labels=binding_labels,
                auto_keys_supported_grid=Mock(),
                auto_keys_input_path=None,
                auto_keys_input_mtime=None,
            )
            resolver = Mock(
                return_value=(
                    {
                        "Fire": "LeftMouseButton",
                        "Use": "E",
                        "DropItem": "O",
                    },
                    input_path,
                )
            )
            with patch.object(
                settings_page, "resolve_supported_keys", resolver
            ):
                settings_page.SettingsPagesMixin._refresh_auto_keys_supported_keys(
                    launcher, force=True
                )
                settings_page.SettingsPagesMixin._refresh_auto_keys_supported_keys(
                    launcher
                )
                current_stat = input_path.stat()
                os.utime(
                    input_path,
                    ns=(current_stat.st_atime_ns, current_stat.st_mtime_ns + 1_000_000),
                )
                settings_page.SettingsPagesMixin._refresh_auto_keys_supported_keys(
                    launcher
                )

        self.assertEqual(resolver.call_count, 2)
        resolved = {"Fire": "LeftMouseButton", "Use": "E", "DropItem": "O"}
        for action, label in binding_labels.items():
            label.setText.assert_called_with(
                f"[{resolved[action]}]" if action in resolved else "—"
            )

    def test_auto_keys_descriptions_render_and_hold_duration_updates(self):
        from source.launcher.pages import settings as settings_page

        app = QApplication.instance() or QApplication([])
        container = QWidget()
        launcher = settings_page.SettingsPagesMixin()
        launcher.form_values = {
            "auto_keys": {"enabled": False, "interval": 0.1, "hold_duration": 1.0}
        }
        launcher._settings_form_action_column = 3
        launcher.settings_form_layout = QGridLayout(container)
        with patch.object(
            settings_page,
            "resolve_supported_keys",
            return_value=(
                {"Fire": "LeftMouseButton", "Use": "E", "DropItem": "O"},
                Path("Input.ini"),
            ),
        ):
            launcher._add_auto_keys_settings(0)

        all_labels = container.findChildren(QLabel)
        labels = {label.objectName(): label for label in all_labels}
        self.assertIn("below 0.15 seconds", labels["AutoKeysWarning"].text())
        self.assertTrue(labels["AutoKeysWarning"].wordWrap())
        self.assertFalse(labels["AutoKeysWarning"].isHidden())
        self.assertIn(
            "delay between repeated presses",
            labels["AutoKeysIntervalDescription"].text(),
        )
        self.assertIn("must be held", labels["AutoKeysTriggerDescription"].text())
        self.assertTrue(labels["AutoKeysTriggerDescription"].wordWrap())
        self.assertIn("for 1 second", labels["AutoKeysInstruction"].text())
        self.assertTrue(labels["AutoKeysInstruction"].wordWrap())
        self.assertIn("Trigger (seconds)", [label.text() for label in all_labels])

        header = container.findChild(QWidget, "AutoKeysHeader")
        heading = header.findChild(QLabel, "SectionHeading")
        self.assertEqual(heading.text(), "AUTO KEYS")
        self.assertIs(header.layout().itemAt(0).widget(), heading)
        self.assertIsNotNone(header.layout().itemAt(1).spacerItem())
        self.assertIs(
            header.layout().itemAt(2).widget(), launcher.auto_keys_enabled_field
        )
        self.assertIsNone(container.findChild(QWidget, "SettingsDivider"))

        action_labels = launcher.auto_keys_supported_action_labels
        binding_labels = launcher.auto_keys_supported_binding_labels
        self.assertEqual(list(action_labels), list(AUTO_KEYS_ACTIONS))
        self.assertTrue(
            all(
                label.objectName() == "AutoKeysSupportedAction"
                for label in action_labels.values()
            )
        )
        self.assertTrue(
            all(
                label.objectName() == "AutoKeysSupportedBinding"
                for label in binding_labels.values()
            )
        )
        from source.launcher.config.constants import COLORS
        from source.launcher.styles import launcher_style_sheet

        style = launcher_style_sheet()
        action_style = style.split("QLabel#AutoKeysSupportedAction {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn(f'color: {COLORS["cyan"]};', action_style)
        self.assertIn("font-weight: 900;", action_style)
        grid = launcher.auto_keys_supported_grid_layout
        for index, action in enumerate(AUTO_KEYS_ACTIONS):
            pair = index % 2
            row = index // 2
            column = pair * 3
            action_item = grid.itemAtPosition(row, column)
            binding_item = grid.itemAtPosition(row, column + 1)
            self.assertIs(action_item.widget(), action_labels[action])
            self.assertIs(binding_item.widget(), binding_labels[action])
            self.assertTrue(action_item.alignment() & Qt.AlignmentFlag.AlignTop)
            self.assertTrue(binding_item.alignment() & Qt.AlignmentFlag.AlignTop)
        if len(AUTO_KEYS_ACTIONS) % 2:
            final_row = len(AUTO_KEYS_ACTIONS) // 2
            self.assertIsNone(grid.itemAtPosition(final_row, 3))
            self.assertIsNone(grid.itemAtPosition(final_row, 4))
        supported_title = next(
            label for label in all_labels if label.text() == "Supported keys"
        )
        self.assertTrue(supported_title.alignment() & Qt.AlignmentFlag.AlignTop)
        supported_item = launcher.settings_form_layout.itemAt(
            launcher.settings_form_layout.indexOf(launcher.auto_keys_supported_grid)
        )
        self.assertTrue(supported_item.alignment() & Qt.AlignmentFlag.AlignTop)
        self.assertEqual(binding_labels["Fire"].text(), "[LeftMouseButton]")
        self.assertEqual(binding_labels["Use"].text(), "[E]")
        self.assertEqual(binding_labels["DropItem"].text(), "[O]")
        for action in set(AUTO_KEYS_ACTIONS) - {"Fire", "Use", "DropItem"}:
            self.assertEqual(binding_labels[action].text(), "—")

        launcher.auto_keys_hold_field.setText("2.5")
        launcher.auto_keys_interval_field.setText("0.15")
        app.processEvents()

        self.assertIn("for 2.5 seconds", labels["AutoKeysInstruction"].text())
        self.assertTrue(labels["AutoKeysWarning"].isHidden())
        self.assertFalse(labels["AutoKeysIntervalDescription"].isHidden())

        launcher.auto_keys_interval_field.setText("0.14")
        self.assertFalse(labels["AutoKeysWarning"].isHidden())
        launcher.auto_keys_interval_field.setText("invalid")
        self.assertTrue(labels["AutoKeysWarning"].isHidden())

    def test_foreground_check_accepts_same_process_child_window(self):
        fake_windows = types.SimpleNamespace(ark_hwnd=lambda: 100)
        pids = {100: 55, 200: 55}

        def set_pid(hwnd, pointer):
            pointer._obj.value = pids[hwnd]
            return 1

        fake_user32 = types.SimpleNamespace(
            GetForegroundWindow=lambda: 200,
            GetWindowThreadProcessId=set_pid,
        )
        fake_windll = types.SimpleNamespace(user32=fake_user32)
        with (
            patch.object(source.utility, "windows", fake_windows, create=True),
            patch("source.launcher.auto_keys.ctypes.windll", fake_windll),
        ):
            self.assertTrue(self.runtime._ark_is_foreground())

    def test_foreground_check_rejects_other_process(self):
        fake_windows = types.SimpleNamespace(ark_hwnd=lambda: 100)
        pids = {100: 55, 200: 77}

        def set_pid(hwnd, pointer):
            pointer._obj.value = pids[hwnd]
            return 1

        fake_user32 = types.SimpleNamespace(
            GetForegroundWindow=lambda: 200,
            GetWindowThreadProcessId=set_pid,
        )
        fake_windll = types.SimpleNamespace(user32=fake_user32)
        with (
            patch.object(source.utility, "windows", fake_windows, create=True),
            patch("source.launcher.auto_keys.ctypes.windll", fake_windll),
        ):
            self.assertFalse(self.runtime._ark_is_foreground())

    def test_start_and_stop_emit_beeps(self):
        self.runtime._play_beep = Mock()
        self.runtime._notify = Mock()
        fake_utils = types.SimpleNamespace(
            action_down=lambda _action: None,
            action_up=lambda _action: None,
        )
        self.runtime._pending = self.binding
        self.runtime._pending_started_at = 0.0
        self.runtime._ark_is_foreground = lambda: True
        with patch.object(source.utility, "utils", fake_utils, create=True):
            self.runtime._start_repeat(self.binding)
            time.sleep(0.02)
            self.runtime._stop_repeat()

        self.assertEqual(
            self.runtime._play_beep.call_args_list,
            [call(True), call(False)],
        )

    def test_idle_automation_suspension_emits_one_stop_beep(self):
        self.runtime._play_beep = Mock()
        self.runtime._notify = Mock()

        self.assertTrue(self.runtime.suspend_for_automation())

        self.runtime._play_beep.assert_called_once_with(False)
        self.assertFalse(self.runtime.enabled)

    def test_focus_loss_stops_active_repeat_with_beep(self):
        self.runtime._active = self.binding
        self.runtime._play_beep = Mock()

        self.runtime._cancel_for_focus_loss()

        self.runtime._play_beep.assert_called_once_with(False)
        self.assertIsNone(self.runtime._active)

    def test_mouse_repeat_uses_short_pulse_then_configured_interval(self):
        waits = []

        class RepeatEvent:
            def is_set(self):
                return False

            def wait(self, duration):
                waits.append(duration)
                return len(waits) == 2

            def set(self):
                return None

        mouse_binding = ("mouse", 0x01)
        fake_utils = types.SimpleNamespace(
            action_down=Mock(), action_up=Mock()
        )
        self.runtime._repeat_stop_event = RepeatEvent()
        self.runtime._active = mouse_binding
        self.runtime.interval = 0.25
        self.runtime._ark_is_foreground = lambda: True
        with patch.object(source.utility, "utils", fake_utils, create=True):
            self.runtime._repeat("Fire", mouse_binding)

        self.assertEqual(waits, [0.02, 0.25])
        fake_utils.action_down.assert_called_once_with("Fire")
        fake_utils.action_up.assert_called_once_with("Fire")
        self.assertFalse(self.runtime._last_states[mouse_binding])

    def test_first_mouse_press_after_release_stops(self):
        mouse_binding = ("mouse", 0x01)
        self.runtime._active = mouse_binding
        self.runtime._last_states[mouse_binding] = True
        self.runtime._stop_repeat = Mock()

        self.runtime._process_polled_state(mouse_binding, False, 1.0)
        self.runtime._process_polled_state(mouse_binding, True, 1.1)

        self.runtime._stop_repeat.assert_called_once_with()

    def test_transition_beep_failure_does_not_raise(self):
        fake_winsound = types.SimpleNamespace(
            Beep=lambda *_args: (_ for _ in ()).throw(OSError("no speaker"))
        )
        with patch.dict(sys.modules, {"winsound": fake_winsound}):
            self.runtime._play_beep(True)
            time.sleep(0.01)


class AutoKeysAutomationSuspensionTests(unittest.TestCase):
    class Launcher(RuntimeGuiMixin):
        def __init__(self, runtime, enabled=True):
            self.auto_keys_runtime = runtime
            self.auto_keys_automation_suspensions = set()
            self.auto_keys_restore_after_automation = False
            self.settings = {"auto_keys": {"enabled": enabled}}
            self.shutdown_started = False
            self.auto_keys_enabled_field = Mock()

    def test_nested_workers_restore_only_after_final_worker(self):
        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        launcher = self.Launcher(runtime)

        launcher._suspend_auto_keys_for_automation("main")
        launcher._suspend_auto_keys_for_automation("helper")
        launcher._resume_auto_keys_after_automation("main")

        runtime.suspend_for_automation.assert_called_once_with()
        runtime.configure.assert_not_called()
        launcher._resume_auto_keys_after_automation("helper")
        runtime.configure.assert_called_once_with(launcher.settings)
        launcher.auto_keys_enabled_field.setChecked.assert_called_with(True)
        launcher.auto_keys_enabled_field.setEnabled.assert_called_with(True)

    def test_previously_disabled_runtime_is_not_restored(self):
        runtime = Mock()
        runtime.suspend_for_automation.return_value = False
        launcher = self.Launcher(runtime, enabled=False)

        launcher._suspend_auto_keys_for_automation("worker")
        launcher._resume_auto_keys_after_automation("worker")

        runtime.configure.assert_not_called()

    def test_shutdown_does_not_restore_suspended_runtime(self):
        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        launcher = self.Launcher(runtime)
        launcher._suspend_auto_keys_for_automation("worker")
        launcher.shutdown_started = True

        launcher._resume_auto_keys_after_automation("worker")

        runtime.configure.assert_not_called()

    def test_worker_helper_uses_shared_suspension_lifecycle(self):
        class Owner(QWidget, RuntimeGuiMixin):
            def __init__(self, runtime):
                super().__init__()
                self.auto_keys_runtime = runtime
                self.auto_keys_automation_suspensions = set()
                self.auto_keys_restore_after_automation = False
                self.settings = {"auto_keys": {"enabled": True}}
                self.shutdown_started = False

        app = QApplication.instance() or QApplication([])
        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        owner = Owner(runtime)
        helper = WorkerHelperWindow(owner, "Test Worker", 240, 100)
        helper._set_running_ui = Mock()
        helper._read_worker_output = Mock()
        process = Mock(stdout=None)
        with patch(
            "source.launcher.components.helper_window.start_subprocess",
            return_value=process,
        ):
            helper._start_worker("auto_fishing")

        self.assertIn(helper, owner.auto_keys_automation_suspensions)
        runtime.suspend_for_automation.assert_called_once_with()
        helper._finish_worker()
        app.processEvents()

        self.assertNotIn(helper, owner.auto_keys_automation_suspensions)
        runtime.configure.assert_called_once_with(owner.settings)
        helper.close()
        owner.close()

    def test_worker_launch_failure_releases_suspension(self):
        class Owner(QWidget, RuntimeGuiMixin):
            def __init__(self, runtime):
                super().__init__()
                self.auto_keys_runtime = runtime
                self.auto_keys_automation_suspensions = set()
                self.auto_keys_restore_after_automation = False
                self.settings = {"auto_keys": {"enabled": True}}
                self.shutdown_started = False

        app = QApplication.instance() or QApplication([])
        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        owner = Owner(runtime)
        helper = WorkerHelperWindow(owner, "Test Worker", 240, 100)
        helper._set_running_ui = Mock()
        with patch(
            "source.launcher.components.helper_window.start_subprocess",
            side_effect=OSError("launch failed"),
        ):
            with self.assertRaises(OSError):
                helper._start_worker("auto_fishing")

        self.assertFalse(owner.auto_keys_automation_suspensions)
        runtime.configure.assert_called_once_with(owner.settings)
        helper.close()
        owner.close()
        app.processEvents()

    def test_main_runner_suspends_until_process_finalizes(self):
        class Launcher(RuntimeGuiMixin):
            def __init__(self, runtime):
                self.auto_keys_runtime = runtime
                self.auto_keys_automation_suspensions = set()
                self.auto_keys_restore_after_automation = False
                self.settings = {"auto_keys": {"enabled": True}}
                self.shutdown_started = False
                self.program_stopping = False
                self.runner_launch_pending = True
                self.runner_loading = True
                self.runner_ready_pending = False
                self.process = None
                self.stop_deadline = None
                self.close_external_helpers = Mock()
                self.append_log = Mock()
                self._update_start_stop_button = Mock()
                self.start_log_tail = Mock()
                self.stop_log_tail = Mock()
                self.read_output = Mock()
                self._close_output_reader = Mock()
                self._hide_runner_overlay = Mock()
                self.dialog = Mock()

        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        launcher = Launcher(runtime)
        process = Mock(stdout=None)
        process.poll.return_value = None
        with (
            patch(
                "source.launcher.gui_parts.runtime.cleanup_debug_screenshots_on_program_start"
            ),
            patch(
                "source.launcher.gui_parts.runtime.start_subprocess",
                return_value=process,
            ),
        ):
            launcher._launch_program_process()

        self.assertIn("main-runner", launcher.auto_keys_automation_suspensions)
        runtime.suspend_for_automation.assert_called_once_with()
        process.poll.return_value = 0
        launcher._finalize_program_stop()

        self.assertFalse(launcher.auto_keys_automation_suspensions)
        runtime.configure.assert_called_once_with(launcher.settings)

    def test_main_runner_launch_failure_restores_auto_keys(self):
        runtime = Mock()
        runtime.suspend_for_automation.return_value = True
        launcher = self.Launcher(runtime)
        launcher.program_stopping = False
        launcher.runner_launch_pending = True
        launcher.runner_loading = True
        launcher.runner_ready_pending = False
        launcher.process = None
        launcher.close_external_helpers = Mock()
        launcher._hide_runner_overlay = Mock()
        launcher._update_start_stop_button = Mock()
        launcher.dialog = Mock()
        with (
            patch(
                "source.launcher.gui_parts.runtime.cleanup_debug_screenshots_on_program_start"
            ),
            patch(
                "source.launcher.gui_parts.runtime.start_subprocess",
                side_effect=OSError("launch failed"),
            ),
        ):
            launcher._launch_program_process()

        self.assertFalse(launcher.auto_keys_automation_suspensions)
        runtime.configure.assert_called_once_with(launcher.settings)


if __name__ == "__main__":
    unittest.main()
