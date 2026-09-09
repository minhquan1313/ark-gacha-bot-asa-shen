import threading
import time
import unittest
from collections.abc import Callable
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QLabel

from source.launcher import auto_keys
from source.launcher.auto_keys import AutoKeysRuntime
from source.launcher.pages.settings import SettingsPagesMixin
from source.utility import action_gate, utils


class BindingPanel(QObject, SettingsPagesMixin):
    supported_keys_finished = Signal(object)

    def __init__(self):
        """Supply real queued Qt delivery without constructing the launcher."""
        super().__init__()
        self.auto_keys_supported_binding_labels = {"Use": QLabel("waiting")}
        self.supported_keys_finished.connect(self._on_supported_keys_finished)


class ResponsivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def pump_until(self, predicate: Callable, timeout: float = 2):
        """Process real Qt events until a worker condition is met."""
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate())

    def test_slow_binding_discovery_keeps_qt_alive_and_ignores_old_controls(self):
        panel = BindingPanel()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def slow_resolve():
            entered.set()
            release.wait(2)
            return {"Use": "E"}, None

        with patch("source.launcher.pages.settings.resolve_supported_keys", side_effect=slow_resolve) as resolver:
            panel._refresh_auto_keys_supported_keys(True)
            self.assertTrue(entered.wait(1))
            heartbeat = []
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            self.pump_until(lambda: bool(heartbeat))
            panel._refresh_auto_keys_supported_keys(True)
            self.assertEqual(resolver.call_count, 1)
            replacement = QLabel("new controls")
            panel.auto_keys_supported_binding_labels = {"Use": replacement}
            release.set()
            self.pump_until(lambda: not panel.supported_keys_busy)
            self.assertEqual(replacement.text(), "new controls")
            panel._refresh_auto_keys_supported_keys(True)
            self.pump_until(lambda: not panel.supported_keys_busy)
            self.assertEqual(replacement.text(), "[E]")
            panel.shutdown_started = True
            panel._on_supported_keys_finished((id(panel.auto_keys_supported_binding_labels), {"Use": "F"}, None, None))
            self.assertEqual(replacement.text(), "[E]")

    def test_slow_hook_install_does_not_block_enable_or_resurrect_disabled_runtime(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        runtime = AutoKeysRuntime()
        self.addCleanup(runtime.shutdown)
        listener = Mock()

        def slow_start():
            entered.set()
            release.wait(2)

        listener.start.side_effect = slow_start
        with patch("source.launcher.auto_keys._InputListener", return_value=listener), \
                patch.object(runtime, "_resolve_bindings", return_value={}), \
                patch.object(runtime, "_ark_is_foreground", return_value=True):
            runtime.enable()
            self.assertTrue(entered.wait(1))
            heartbeat = []
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            self.pump_until(lambda: bool(heartbeat))
            self.assertEqual(runtime.state, "starting")
            runtime.disable()
            release.set()
            self.pump_until(lambda: not runtime._worker_threads)
            self.assertEqual(runtime.state, "disabled")
            self.assertFalse(runtime.enabled)

    def test_delayed_key_release_blocks_new_input_without_blocking_qt(self):
        release = threading.Event()
        self.addCleanup(release.set)
        runtime = AutoKeysRuntime()
        worker = threading.Thread(target=lambda: release.wait(2), daemon=True)
        worker.start()
        runtime._repeat_thread = worker
        runtime._stop_repeat()
        self.assertTrue(runtime.cleanup_pending)
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        self.pump_until(lambda: bool(heartbeat))
        release.set()
        self.pump_until(lambda: not runtime.cleanup_pending)

    def test_partial_hook_failure_releases_installed_hook(self):
        user32 = Mock()
        user32.SetWindowsHookExW.side_effect = [123, 0]
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 7
        listener = auto_keys._InputListener()
        with patch.object(auto_keys.ctypes.windll, "user32", user32), \
                patch.object(auto_keys.ctypes.windll, "kernel32", kernel32):
            with self.assertRaisesRegex(RuntimeError, "Could not install"):
                listener.start()
            listener.stop()
        user32.UnhookWindowsHookEx.assert_called_once_with(123)

    def test_cancelled_listener_cannot_install_hooks_later(self):
        listener = auto_keys._InputListener()
        listener.stop()
        with patch.object(listener, "_run") as run:
            listener.start()
        run.assert_not_called()

    def test_repeat_bypasses_automation_pause_and_stops_promptly(self):
        """A real repeat worker skips the pause gate and interrupts its long delay."""
        pressed = threading.Event()
        runtime = AutoKeysRuntime()
        runtime.enabled = True
        runtime.interval = 30
        binding = ("keyboard", 0x45)
        runtime._bindings = {binding: "Use"}
        runtime._pending = binding
        with (
            patch.object(runtime, "_ark_is_foreground", return_value=True),
            patch.object(runtime, "_play_beep"),
            patch.object(action_gate, "before_ark_action", side_effect=AssertionError("unexpected pause")) as gate,
            patch.object(utils.local_player, "get_input_settings", return_value="e"),
            patch.object(utils.windows, "ark_hwnd", return_value=123),
            patch.object(utils, "keymap_return", return_value=0x45),
            patch.object(utils.ctypes.windll.user32, "PostMessageW", side_effect=lambda *_args: pressed.set()),
        ):
            runtime._start_repeat(binding)
            worker = runtime._repeat_thread
            try:
                self.assertTrue(pressed.wait(1))
                runtime.disable()
                self.pump_until(lambda: not runtime.cleanup_pending)
                self.assertFalse(worker.is_alive())
                gate.assert_not_called()
            finally:
                runtime.shutdown()
