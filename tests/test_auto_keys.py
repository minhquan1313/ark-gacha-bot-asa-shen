import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from PySide6.QtCore import QEasingCurve, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QWidget
from shiboken6 import delete, isValid

import source.utility
from source.launcher import auto_keys
from source.launcher.auto_keys import AutoKeysRuntime
from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import CyberCheckBox, CyberSwitch
from source.launcher.config.constants import AUTO_KEYS_ACTIONS, TEMPLATE_SETTING_KEYS
from source.launcher.gui_parts.runtime import RuntimeGuiMixin
from source.launcher.utils.settings_store import _normalize_settings
from source.utility import local_player


class KeyCodeTests(unittest.TestCase):
    def test_named_keys_share_codes_with_ark_aliases(self):
        """Activation keys and ARK binding names use the same conversion."""
        from source.utility import utils

        cases = {
            "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "return": 0x0D,
            "ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": 0x20, "spacebar": 0x20,
            "PAGEUP": 0x21, "PAGEDOWN": 0x22, "END": 0x23, "HOME": 0x24,
            "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
            "INSERT": 0x2D, "DELETE": 0x2E, "LeftShift": 0xA0,
            "LeftControl": 0xA2, "One": 0x31, "ThumbMouseButton": 0x05,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(utils.keymap_return(name), expected)
                self.assertEqual(auto_keys.activation_key_code(f" {name} "), expected)

    def test_function_keys_and_invalid_names(self):
        """Both callers support F1 through F24 and reject unknown key names."""
        from source.utility import utils

        for number in range(1, 25):
            with self.subTest(number=number):
                self.assertEqual(utils.keymap_return(f"f{number}"), 0x6F + number)
                self.assertEqual(auto_keys.activation_key_code(f"F{number}"), 0x6F + number)
        for name in ("", "F0", "F25", "unknown"):
            with self.subTest(name=name):
                self.assertIsNone(utils.keymap_return(name))
                self.assertIsNone(auto_keys.activation_key_code(name))

    def test_characters_and_default_actions_keep_existing_resolution(self):
        """Characters still use the keyboard layout and actions retain defaults."""
        from source.utility import utils

        with patch.object(utils, "_VkKeyScanW", return_value=0x0145) as scan:
            self.assertEqual(auto_keys.activation_key_code(" E "), 0x45)
            self.assertEqual(utils.keymap_return("Use"), 0x45)
            self.assertEqual(scan.call_args_list, [call("e"), call("e")])
        self.assertEqual(utils.keymap_return("Run"), 0xA0)
        self.assertEqual(utils.keymap_return("PauseMenu"), 0x1B)


class AutoKeysWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])

    def test_switch_loading_is_integrated_and_blocks_toggling(self):
        switch = CyberSwitch("ENABLED")
        initial_size = switch.sizeHint()
        switch.setChecked(True)

        switch.set_loading(True)

        self.assertTrue(switch.isChecked())
        self.assertTrue(switch.is_loading)
        self.assertEqual(switch.text(), "ENABLED")
        self.assertEqual(switch.sizeHint(), initial_size)
        self.assertFalse(switch.hitButton(switch.rect().center()))
        self.assertEqual(switch._loading_animation.duration(), 900)
        self.assertEqual(switch._loading_animation.loopCount(), -1)
        self.assertEqual(
            switch._loading_animation.easingCurve().type(),
            QEasingCurve.Type.Linear,
        )

        switch.nextCheckState()
        self.assertTrue(switch.isChecked())
        switch.set_loading(False)
        self.assertFalse(switch.is_loading)
        switch.nextCheckState()
        self.assertFalse(switch.isChecked())

    def test_checked_action_control_renders_cyan_fill_and_white_check(self):
        checkbox = CyberCheckBox()
        checkbox.resize(24, 24)
        checkbox.blockSignals(True)
        checkbox.setChecked(True)
        checkbox.blockSignals(False)
        image = QImage(checkbox.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor("#000000"))

        checkbox.render(image)

        from source.launcher.config.constants import COLORS

        cyan = QColor(COLORS["cyan"]).rgb()
        white = QColor(COLORS["text"]).rgb()
        pixels = [
            image.pixel(x, y)
            for x in range(image.width())
            for y in range(image.height())
        ]
        self.assertGreater(pixels.count(cyan), 100)
        self.assertGreater(pixels.count(white), 10)


class AutoKeysSettingsTests(unittest.TestCase):
    def test_auto_keys_defaults_are_migrated(self):
        settings = _normalize_settings({})

        self.assertEqual(
            settings["auto_keys"],
            {
                "enabled": False,
                "activation_key": "F1",
                "interval": 0.25,
                "hold_duration": 1.0,
                "actions": {action: True for action in AUTO_KEYS_ACTIONS},
            },
        )
        self.assertNotIn("auto_keys", TEMPLATE_SETTING_KEYS)

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
        self.assertTrue(all(settings["auto_keys"]["actions"].values()))
        self.assertEqual(
            _normalize_settings({"auto_keys": {"interval": 0.1}})["auto_keys"][
                "interval"
            ],
            0.1,
        )
        with self.assertRaises(ValueError):
            _normalize_settings({"auto_keys": {"interval": 0}})

    def test_auto_keys_action_states_are_normalized_and_unknown_actions_removed(self):
        settings = _normalize_settings(
            {
                "auto_keys": {
                    "actions": {"Use": False, "UnknownAction": False}
                }
            }
        )

        self.assertFalse(settings["auto_keys"]["actions"]["Use"])
        self.assertTrue(settings["auto_keys"]["actions"]["Fire"])
        self.assertNotIn("UnknownAction", settings["auto_keys"]["actions"])

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

    def test_action_checkbox_states_are_persisted(self):
        from source.launcher.pages import settings as settings_page

        launcher = settings_page.SettingsPagesMixin()
        launcher.settings = _normalize_settings({})
        launcher.form_values = launcher.settings.copy()
        launcher.auto_keys_enabled_field = Mock(isChecked=Mock(return_value=True))
        launcher.auto_keys_interval_field = Mock(text=Mock(return_value="0.25"))
        launcher.auto_keys_hold_field = Mock(text=Mock(return_value="1.0"))
        launcher.auto_keys_action_fields = {
            action: Mock(isChecked=Mock(return_value=action != "Use"))
            for action in AUTO_KEYS_ACTIONS
        }
        launcher.auto_keys_runtime = Mock()
        launcher._collect_settings = Mock(side_effect=lambda: launcher.form_values)
        launcher.dialog = Mock()
        with patch.object(
            settings_page, "save_settings", side_effect=lambda settings: settings
        ):
            launcher.persist_auto_keys_settings()

        self.assertFalse(launcher.settings["auto_keys"]["actions"]["Use"])
        self.assertTrue(launcher.settings["auto_keys"]["actions"]["Fire"])
        launcher.auto_keys_runtime.configure.assert_called_once_with(
            launcher.settings, allow_enable=True
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

    def test_activation_key_is_required_to_start(self):
        self.runtime._start_repeat = Mock()

        self.runtime._process_polled_state(self.binding, True, 10.0, False)
        self.runtime._process_polled_state(self.binding, True, 11.0, True)
        self.runtime._process_polled_state(self.binding, True, 11.5, False)

        self.runtime._start_repeat.assert_not_called()
        self.runtime._process_polled_state(self.binding, False, 11.6, True)
        self.runtime._process_polled_state(self.binding, True, 13.0, True)
        self.runtime._process_polled_state(self.binding, True, 14.0, True)
        self.runtime._start_repeat.assert_called_once_with(self.binding)

    def test_key_hold_sends_one_down_and_releases_on_second_press(self):
        runtime = AutoKeysRuntime(("MoveForward",))
        binding = ("keyboard", 0x57)
        runtime.enabled = True
        runtime.hold_duration = 1.0
        runtime._bindings = {binding: "MoveForward"}
        with (
            patch("source.utility.utils.key_hold_down", return_value=(0x11, 8)) as key_hold_down,
            patch("source.utility.utils.key_hold_up") as key_hold_up,
            patch.object(runtime, "_ark_is_foreground", return_value=True),
            patch.object(auto_keys.ctypes.windll.user32, "GetAsyncKeyState", return_value=0),
        ):
            runtime._process_polled_state(binding, True, 10.0, True)
            runtime._process_polled_state(binding, True, 11.0, True)
            key_hold_down.assert_not_called()
            runtime._process_polled_state(binding, False, 11.1, True)
            runtime._process_polled_state(binding, True, 11.2, True)
            self.assertIsNone(runtime._active)
            runtime._stop_repeat()
            runtime.shutdown()

        key_hold_down.assert_called_once_with("MoveForward", should_pause=False)
        key_hold_up.assert_called_once_with((0x11, 8))

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
            {
                "Fire": "LeftMouseButton",
                "Use": "E",
                "DropItem": "O",
                "Crouch": "c",
                "MoveForward": "w",
            },
        )

    def test_offline_resolver_uses_default_move_forward_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "Input.ini"
            input_path.write_text("", encoding="utf-8")
            with patch(
                "source.launcher.ark_game_setup.find_game_user_input_path",
                return_value=input_path,
            ):
                resolved, resolved_path = auto_keys.resolve_supported_keys(
                    ("MoveForward",)
                )

        self.assertEqual(resolved_path, input_path)
        self.assertEqual(resolved, {"MoveForward": "w"})

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
            launcher.supported_keys_finished = Mock()
            launcher.supported_keys_finished.emit.side_effect = lambda result: settings_page.SettingsPagesMixin._on_supported_keys_finished(launcher, result)
            original_refresh = settings_page.SettingsPagesMixin._refresh_auto_keys_supported_keys

            def refresh_and_wait(target: object, force: bool = False):
                """Wait for the mocked display delivery before editing Input.ini."""
                original_refresh(target, force=force)
                deadline = time.monotonic() + 2
                while target.supported_keys_busy and time.monotonic() < deadline:
                    time.sleep(0.001)
                self.assertFalse(target.supported_keys_busy)

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
                refresh_and_wait(
                    launcher, force=True
                )
                refresh_and_wait(
                    launcher
                )
                current_stat = input_path.stat()
                os.utime(
                    input_path,
                    ns=(current_stat.st_atime_ns, current_stat.st_mtime_ns + 1_000_000),
                )
                refresh_and_wait(
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
        launcher._refresh_auto_keys_supported_keys = Mock()
        with patch.object(
            settings_page,
            "resolve_supported_keys",
            return_value=(
                {"Fire": "LeftMouseButton", "Use": "E", "DropItem": "O"},
                Path("Input.ini"),
            ),
        ):
            launcher._add_auto_keys_settings(0)
            launcher._on_supported_keys_finished((
                id(launcher.auto_keys_supported_binding_labels),
                {"Fire": "LeftMouseButton", "Use": "E", "DropItem": "O"},
                Path("Input.ini"), None,
            ))

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
        self.assertEqual(header.layout().count(), 3)
        self.assertIsNone(container.findChild(QWidget, "SettingsDivider"))

        action_fields = launcher.auto_keys_action_fields
        binding_labels = launcher.auto_keys_supported_binding_labels
        self.assertEqual(list(action_fields), list(AUTO_KEYS_ACTIONS))
        self.assertTrue(
            all(
                isinstance(field, CyberCheckBox)
                and field.objectName() == "AutoKeysSupportedAction"
                and field.isChecked()
                for field in action_fields.values()
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
        action_style = style.split("QCheckBox#AutoKeysSupportedAction {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn(f'color: {COLORS["cyan"]};', action_style)
        self.assertIn("font-weight: 900;", action_style)
        grid = launcher.auto_keys_supported_grid_layout
        repeat_actions = tuple(action for action in AUTO_KEYS_ACTIONS if action != "MoveForward")
        for index, action in enumerate(repeat_actions):
            pair = index % 2
            row = index // 2
            column = pair * 3
            action_item = grid.itemAtPosition(row, column)
            binding_item = grid.itemAtPosition(row, column + 1)
            self.assertIs(action_item.widget(), action_fields[action])
            self.assertIs(binding_item.widget(), binding_labels[action])
            self.assertTrue(action_item.alignment() & Qt.AlignmentFlag.AlignTop)
            self.assertTrue(binding_item.alignment() & Qt.AlignmentFlag.AlignTop)
        if len(repeat_actions) % 2:
            final_row = len(repeat_actions) // 2
            self.assertIsNone(grid.itemAtPosition(final_row, 3))
            self.assertIsNone(grid.itemAtPosition(final_row, 4))
        supported_title = next(
            label for label in all_labels if label.text() == "Repeat keys"
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

    def test_enable_resolves_bindings_without_blocking_caller(self):
        resolution_started = threading.Event()
        release_resolution = threading.Event()
        states = []
        runtime = AutoKeysRuntime(("Use",), state_callback=states.append)
        runtime._ark_is_foreground = lambda: False

        def slow_resolution(_actions=None):
            resolution_started.set()
            release_resolution.wait(0.5)
            return {}

        with patch.object(runtime, "_resolve_bindings", side_effect=slow_resolution):
            started_at = time.monotonic()
            runtime.configure(
                {
                    "auto_keys": {
                        "enabled": True,
                        "actions": {"Use": True},
                    }
                }
            )
            elapsed = time.monotonic() - started_at
            self.assertTrue(resolution_started.wait(0.2))
            self.assertLess(elapsed, 0.15)
            self.assertEqual(runtime.state, "starting")
            release_resolution.set()
            deadline = time.monotonic() + 1.0
            while runtime.state != "ready" and time.monotonic() < deadline:
                time.sleep(0.01)

        self.assertEqual(runtime.state, "ready")
        self.assertEqual(states[:2], ["starting", "ready"])
        runtime.shutdown()

    def test_disabled_action_is_not_resolved(self):
        runtime = AutoKeysRuntime(("Fire", "Use"))
        fake_utils = types.SimpleNamespace(keymap_return=lambda key: 0x45)
        with (
            patch.object(source.utility, "utils", fake_utils, create=True),
            patch(
                "source.launcher.auto_keys.resolve_supported_keys",
                return_value=({"Fire": "LeftMouseButton"}, Path("Input.ini")),
            ) as resolver,
        ):
            bindings = runtime._resolve_bindings(("Fire",))

        resolver.assert_called_once_with(("Fire",))
        self.assertEqual(bindings, {("mouse", 0x01): "Fire"})
        self.assertNotIn(("keyboard", 0x45), bindings)

    def test_unchecking_active_action_stops_and_beeps(self):
        self.runtime._active = self.binding
        self.runtime._play_beep = Mock()

        self.runtime.configure(
            {
                "auto_keys": {
                    "enabled": True,
                    "actions": {"Use": False},
                }
            }
        )

        self.assertIsNone(self.runtime._active)
        self.runtime._play_beep.assert_called_once_with(False)
        self.assertEqual(self.runtime._selected_actions, set())

    def test_all_actions_unchecked_starts_ready_and_idle(self):
        statuses = []
        runtime = AutoKeysRuntime(("Use",), status_callback=statuses.append)
        runtime._ark_is_foreground = lambda: False
        with patch.object(
            runtime, "_resolve_bindings", wraps=runtime._resolve_bindings
        ) as resolver:
            runtime.configure(
                {
                    "auto_keys": {
                        "enabled": True,
                        "actions": {"Use": False},
                    }
                }
            )
            deadline = time.monotonic() + 1.0
            while runtime.state != "ready" and time.monotonic() < deadline:
                time.sleep(0.01)

        self.assertEqual(runtime.state, "ready")
        resolver.assert_called_once_with(())
        self.assertEqual(runtime._bindings, {})
        self.assertIn("No Auto Keys actions are selected.", statuses)
        runtime.shutdown()

    def test_late_binding_result_cannot_override_disable(self):
        resolution_started = threading.Event()
        release_resolution = threading.Event()
        states = []
        runtime = AutoKeysRuntime(("Use",), state_callback=states.append)

        def slow_resolution(_actions=None):
            resolution_started.set()
            release_resolution.wait(0.5)
            return {("keyboard", 0x45): "Use"}

        with patch.object(runtime, "_resolve_bindings", side_effect=slow_resolution):
            runtime.configure({"auto_keys": {"enabled": True}})
            self.assertTrue(resolution_started.wait(0.2))
            runtime.disable()
            release_resolution.set()
            runtime.shutdown()

        self.assertEqual(runtime.state, "disabled")
        self.assertNotIn("ready", states[states.index("disabled") + 1 :])

    def test_fatal_startup_failure_ends_loading_and_disables_runtime(self):
        failures = []
        runtime = AutoKeysRuntime(("Use",), failure_callback=failures.append)
        with patch.object(
            runtime, "_resolve_bindings", side_effect=ValueError("broken binding")
        ):
            runtime.configure({"auto_keys": {"enabled": True}})
            deadline = time.monotonic() + 1.0
            while not failures and time.monotonic() < deadline:
                time.sleep(0.01)

        self.assertFalse(runtime.enabled)
        self.assertEqual(runtime.state, "disabled")
        self.assertEqual(failures, ["Auto Keys runtime failed: broken binding"])
        runtime.shutdown()

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
            action_down=lambda _action, *, should_pause=True: None,
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
        listener = Mock()
        self.runtime._input_listener = listener

        self.runtime._cancel_for_focus_loss()

        self.runtime._play_beep.assert_called_once_with(False)
        self.assertIsNone(self.runtime._active)
        listener.stop.assert_called_once_with()
        self.assertIsNone(self.runtime._input_listener)

    def test_listener_events_keep_short_physical_click_transitions(self):
        listener = Mock()
        listener.drain.return_value = [
            ("mouse", 0x01, True),
            ("mouse", 0x01, False),
        ]
        self.runtime._input_listener = listener

        events = self.runtime._apply_physical_events()

        self.assertEqual(
            events,
            [("mouse", 0x01, True), ("mouse", 0x01, False)],
        )

    def test_runtime_failure_unhooks_input_listener(self):
        listener = Mock()
        stop_event = threading.Event()
        refresh_event = threading.Event()
        self.runtime._input_listener = listener
        self.runtime._lifecycle_generation = 1
        self.runtime._poll_stop_event = stop_event
        self.runtime._binding_refresh_event = refresh_event
        self.runtime._notify_failure = Mock()

        self.runtime._fail_worker(1, stop_event, refresh_event, RuntimeError("test"))

        listener.stop.assert_called_once_with()
        self.assertTrue(stop_event.is_set())
        self.assertTrue(refresh_event.is_set())
        self.assertIsNone(self.runtime._input_listener)

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
        fake_utils.action_down.assert_called_once_with("Fire", should_pause=False)
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


class AutoKeysSwitchingTests(unittest.TestCase):
    def setUp(self):
        """Prepare supported bindings without starting global input hooks."""
        self.runtime = AutoKeysRuntime()
        self.runtime.enabled = True
        self.runtime._play_beep = Mock()
        self.use = ("keyboard", 0x45)
        self.move = ("keyboard", 0x57)
        self.fire = ("mouse", 0x01)
        self.runtime._bindings = {
            self.use: "Use", self.move: "MoveForward", self.fire: "Fire"
        }
        self.runtime._active = self.use

    def tearDown(self):
        """Release any worker or held input created by a switching test."""
        self.runtime._stop_repeat()
        self.runtime.enabled = False

    def test_repeat_to_hold_stops_immediately_and_preserves_activation_delay(self):
        """E stops on F1+W; W qualifies after the delay and holds on release."""
        with (
            patch("source.utility.utils.key_hold_down") as down,
            patch("source.utility.utils.key_hold_up"),
            patch.object(self.runtime, "_ark_is_foreground", return_value=True),
            patch.object(auto_keys.ctypes.windll.user32, "GetAsyncKeyState", return_value=0),
        ):
            self.runtime._process_polled_state(self.move, True, 10.0, True)
            self.assertIsNone(self.runtime._active)
            self.assertTrue(self.runtime._repeat_stop_event.is_set())
            self.assertEqual(self.runtime._pending, self.move)
            self.runtime._process_polled_state(self.move, True, 10.99, True)
            self.assertIsNone(self.runtime._active)
            self.runtime._process_polled_state(self.move, True, 11.0, True)
            self.assertEqual(self.runtime._active, self.move)
            down.assert_not_called()
            self.runtime._process_polled_state(self.move, False, 11.1, False)
            down.assert_called_once_with("MoveForward", should_pause=False)
            self.runtime._stop_repeat()

    def test_hold_to_repeat_releases_old_key_before_new_activation(self):
        """An injected W hold is released before E can begin repeating."""
        self.runtime._active = self.move
        self.runtime._key_hold_action = "MoveForward"
        self.runtime._key_hold_injected = True
        with (
            patch("source.utility.utils.key_hold_up") as up,
            patch.object(self.runtime, "_start_repeat") as start,
        ):
            self.runtime._process_polled_state(self.use, True, 10.0, True)
            up.assert_called_once_with("MoveForward")
            start.assert_not_called()
            self.runtime._process_polled_state(self.use, True, 11.0, True)
            start.assert_called_once_with(self.use)

    def test_keyboard_and_mouse_workers_release_before_handoff(self):
        """Switching interrupts an actual worker's wait and releases its input."""
        for old, new in ((self.use, self.fire), (self.fire, self.use)):
            with self.subTest(old=old):
                pressed = threading.Event()
                self.runtime.interval = 30.0
                self.runtime._active = None
                self.runtime._pending = old
                self.runtime._last_states = {}
                with (
                    patch.object(self.runtime, "_ark_is_foreground", return_value=True),
                    patch("source.utility.utils.action_down", side_effect=lambda action, *, should_pause=True: pressed.set()),
                    patch("source.utility.utils.action_up") as up,
                ):
                    self.runtime._start_repeat(old)
                    worker = self.runtime._repeat_thread
                    try:
                        self.assertTrue(pressed.wait(1.0))
                        self.runtime._process_polled_state(new, True, 10.0, True)
                        self.assertFalse(worker.is_alive())
                        up.assert_called_once_with(self.runtime._bindings[old])
                        self.assertEqual(self.runtime._pending, new)
                        self.assertIsNone(self.runtime._active)
                    finally:
                        self.runtime._stop_repeat()

    def test_releasing_either_shortcut_key_cancels_without_resuming(self):
        """An incomplete replacement shortcut leaves both actions stopped."""
        for is_down, activation_down in ((False, True), (True, False)):
            with self.subTest(is_down=is_down):
                self.runtime._active = self.use
                self.runtime._last_states = {}
                self.runtime._process_polled_state(self.move, True, 10.0, True)
                self.runtime._process_polled_state(self.move, is_down, 10.5, activation_down)
                self.assertIsNone(self.runtime._active)
                self.assertIsNone(self.runtime._pending)

    def test_only_fresh_supported_enabled_shortcuts_interrupt(self):
        """Ordinary, repeated, unsupported, disabled, and synthetic input is ignored."""
        for case in ("ordinary", "already_down", "unsupported", "disabled", "synthetic"):
            with self.subTest(case=case):
                self.runtime._last_states = {self.move: case == "already_down"}
                self.runtime._selected_actions = set(self.runtime.actions)
                self.runtime._synthetic_down.clear()
                binding = self.move
                if case == "unsupported":
                    binding = ("keyboard", 0x5A)
                elif case == "disabled":
                    self.runtime._selected_actions.remove("MoveForward")
                elif case == "synthetic":
                    self.runtime._synthetic_down.add(self.move)
                self.runtime._process_polled_state(binding, True, 10.0, case != "ordinary")
                self.assertEqual(self.runtime._active, self.use)
                self.assertIsNone(self.runtime._pending)

    def test_lifecycle_change_during_cleanup_prevents_pending_activation(self):
        """A disabled or replaced lifecycle cannot inherit the new shortcut."""
        for reenabled in (False, True):
            with self.subTest(reenabled=reenabled):
                self.runtime.enabled = True
                self.runtime._active = self.use
                self.runtime._last_states = {}

                def stop_and_change_lifecycle():
                    """Simulate disable or disable/enable while cleanup runs."""
                    self.runtime._active = None
                    self.runtime.enabled = reenabled
                    self.runtime._lifecycle_generation += 1

                with patch.object(self.runtime, "_stop_repeat", side_effect=stop_and_change_lifecycle):
                    self.runtime._process_polled_state(self.move, True, 10.0, True)
                self.assertIsNone(self.runtime._pending)


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

    def test_master_switch_shows_starting_and_ready_states(self):
        app = QApplication.instance() or QApplication([])
        launcher = self.Launcher(Mock(), enabled=True)
        launcher.auto_keys_enabled_field = CyberSwitch("ENABLED")
        launcher.auto_keys_runtime_state = "starting"

        launcher._sync_auto_keys_suspension_ui()

        self.assertEqual(launcher.auto_keys_enabled_field.text(), "ENABLED")
        self.assertTrue(launcher.auto_keys_enabled_field.isChecked())
        self.assertTrue(launcher.auto_keys_enabled_field.isEnabled())
        self.assertTrue(launcher.auto_keys_enabled_field.is_loading)

        launcher._on_auto_keys_state_changed("ready")

        self.assertEqual(launcher.auto_keys_enabled_field.text(), "ENABLED")
        self.assertTrue(launcher.auto_keys_enabled_field.isEnabled())
        self.assertFalse(launcher.auto_keys_enabled_field.is_loading)
        app.processEvents()

    def test_runtime_state_ignores_deleted_settings_controls(self):
        app = QApplication.instance() or QApplication([])
        launcher = self.Launcher(Mock(), enabled=True)
        stale_switch = CyberSwitch("ENABLED")
        launcher.auto_keys_enabled_field = stale_switch
        delete(stale_switch)

        launcher._on_auto_keys_state_changed("ready")

        self.assertIsNone(launcher.auto_keys_enabled_field)
        app.processEvents()

    def test_disabled_auto_keys_ignores_deleted_settings_switch(self):
        app = QApplication.instance() or QApplication([])
        runtime = Mock()
        runtime.suspend_for_automation.return_value = False
        launcher = self.Launcher(runtime, enabled=False)
        stale_switch = CyberSwitch("ENABLED")
        launcher.auto_keys_enabled_field = stale_switch
        delete(stale_switch)
        self.assertFalse(isValid(stale_switch))

        launcher._suspend_auto_keys_for_automation("main")

        runtime.suspend_for_automation.assert_called_once_with()
        self.assertIn("main", launcher.auto_keys_automation_suspensions)
        self.assertIsNone(launcher.auto_keys_enabled_field)
        app.processEvents()

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
