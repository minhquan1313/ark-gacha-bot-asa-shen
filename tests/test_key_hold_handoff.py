import ctypes
import threading
import unittest
from unittest.mock import Mock, patch

from source.launcher.auto_keys import AutoKeysRuntime
from source.utility import utils, windows


class HeldKeyInputTests(unittest.TestCase):
    def test_scan_code_pair_preserves_identity_after_binding_change(self):
        """Down and up use identical scan codes even if Input.ini changes."""
        for scan, flags in ((0x11, 8), (0xE048, 9)):
            with (
                self.subTest(scan=scan),
                patch.object(utils.local_player, "get_input_settings", return_value="w") as resolve,
                patch.object(utils.ctypes, "windll") as native,
            ):
                events = []

                def send(count: int, pointer: object, size: int):
                    """Capture the actual native payload without sending input."""
                    event = ctypes.cast(pointer, ctypes.POINTER(windows.INPUT)).contents
                    events.append((event.type, event.ki.wVk, event.ki.wScan, event.ki.dwFlags))
                    self.assertEqual(count, 1)
                    self.assertEqual(size, ctypes.sizeof(windows.INPUT))
                    return 1

                native.user32.MapVirtualKeyW.return_value = scan
                native.user32.SendInput.side_effect = send
                held_key = utils.key_hold_down("MoveForward", should_pause=False)
                resolve.side_effect = AssertionError("must not resolve again")
                utils.key_hold_up(held_key)
                self.assertEqual(events, [(1, 0, scan & 255, flags), (1, 0, scan & 255, flags | 2)])
                native.user32.MapVirtualKeyW.assert_called_once_with(0x57, 4)

    def test_native_failures_are_reported(self):
        """Unmappable keys and failed down/up submissions never appear successful."""
        with (
            patch.object(utils.local_player, "get_input_settings", return_value="w"),
            patch.object(utils.ctypes, "windll") as native,
        ):
            native.user32.MapVirtualKeyW.return_value = 0
            with self.assertRaises(ValueError):
                utils.key_hold_down("MoveForward", should_pause=False)
            native.user32.SendInput.assert_not_called()
            native.user32.MapVirtualKeyW.return_value = 0x11
            native.user32.SendInput.return_value = 0
            with self.assertRaises(OSError):
                utils.key_hold_down("MoveForward", should_pause=False)
            with self.assertRaises(OSError):
                utils.key_hold_up((0x11, 8))

    def test_action_name_release_remains_supported(self):
        """Existing action-name callers can still release a held key."""
        with (
            patch.object(utils.local_player, "get_input_settings", return_value="w"),
            patch.object(utils.ctypes, "windll") as native,
        ):
            native.user32.MapVirtualKeyW.return_value = 0x11
            native.user32.SendInput.return_value = 1
            utils.key_hold_up("MoveForward")
            native.user32.SendInput.assert_called_once()


class HeldKeyHandoffTests(unittest.TestCase):
    def setUp(self):
        """Prepare a qualified shortcut with all native input safely mocked."""
        self.runtime = AutoKeysRuntime()
        self.runtime.enabled = True
        self.binding = ("keyboard", 0x57)
        self.runtime._bindings = {self.binding: "MoveForward", ("keyboard", 0x45): "Use"}
        self.runtime._play_beep = Mock()
        self.runtime._notify = Mock()
        self.runtime._ark_is_foreground = Mock(return_value=True)
        self.down = self.enterContext(patch.object(utils, "key_hold_down", return_value=(0x11, 8)))
        self.up = self.enterContext(patch.object(utils, "key_hold_up"))
        self.state = self.enterContext(patch.object(ctypes.windll.user32, "GetAsyncKeyState", return_value=0))
        self.addCleanup(self.runtime.shutdown)
        self.runtime._process_polled_state(self.binding, True, 10.0, True)
        self.runtime._process_polled_state(self.binding, True, 11.0, True)

    def test_both_release_orders_and_simultaneous_release(self):
        """Qualification survives F1-first, W-first, and simultaneous release."""
        # Each test iteration owns its lifecycle, with no real input injection.
        for order in ("f1_first", "w_first", "together"):
            with self.subTest(order=order):
                if order == "f1_first":
                    self.runtime._process_polled_state(self.binding, True, 11.1, False)
                self.runtime._process_polled_state(self.binding, False, 11.2, order == "w_first")
                self.assertTrue(self.runtime._key_hold_injected)
                self.assertFalse(self.runtime._last_states[self.binding])
                self.runtime._process_polled_state(self.binding, False, 11.3, False)
                self.runtime._process_polled_state(self.binding, True, 11.4, False)
                self.assertIsNone(self.runtime._active)
                self.runtime.shutdown()
                self.up.assert_called_with((0x11, 8))
                self.runtime.enabled = True
                self.runtime._process_polled_state(self.binding, True, 12.0, True)
                self.runtime._process_polled_state(self.binding, True, 13.0, True)
        self.assertEqual(self.down.call_count, 3)
        self.assertEqual(self.up.call_count, 3)

    def test_waits_for_windows_release_without_repeating_or_corrupting_history(self):
        """A hook key-up can precede Windows state, and auto-repeat is harmless."""
        self.runtime._process_polled_state(self.binding, True, 11.1, True)
        self.down.assert_not_called()
        self.state.return_value = 0x8000
        self.runtime._process_polled_state(self.binding, False, 11.2, False)
        self.runtime._process_polled_state(self.binding, False, 11.3, False)
        self.down.assert_not_called()
        self.state.return_value = 0
        self.runtime._process_polled_state(self.binding, False, 11.4, False)
        self.runtime._process_polled_state(self.binding, False, 11.5, False)
        self.down.assert_called_once_with("MoveForward", should_pause=False)
        self.assertFalse(self.runtime._last_states[self.binding])
        self.runtime._notify.assert_called_with("Holding MoveForward.")

    def test_new_press_cancels_delayed_handoff(self):
        """A physical re-press stops the qualified hold before it can inject."""
        self.state.return_value = 0x8000
        self.runtime._process_polled_state(self.binding, False, 11.1, False)
        self.runtime._process_polled_state(self.binding, True, 11.2, False)
        self.assertIsNone(self.runtime._active)
        self.down.assert_not_called()
        self.up.assert_not_called()

    def test_focus_check_cancels_just_before_injection(self):
        """Losing foreground ownership at the handoff sends no key-down."""
        self.runtime._ark_is_foreground.return_value = False
        self.runtime._process_polled_state(self.binding, False, 11.1, False)
        self.assertIsNone(self.runtime._active)
        self.down.assert_not_called()

    def test_cancellation_releases_only_successfully_injected_input(self):
        """All stop paths cancel pending input and release an existing hold once."""
        for injected in (False, True):
            for reason in ("focus", "disable", "emergency", "shutdown", "switch"):
                with self.subTest(injected=injected, reason=reason):
                    self.runtime.shutdown()
                    self.runtime.enabled = True
                    self.runtime._process_polled_state(self.binding, True, 10.0, True)
                    self.runtime._process_polled_state(self.binding, True, 11.0, True)
                    self.down.reset_mock()
                    self.up.reset_mock()
                    self.state.return_value = 0 if injected else 0x8000
                    self.runtime._process_polled_state(self.binding, False, 11.1, False)
                    if reason == "focus":
                        self.runtime._cancel_for_focus_loss()
                    elif reason == "switch":
                        self.runtime._process_polled_state(("keyboard", 0x45), True, 11.2, True)
                    elif reason == "shutdown":
                        self.runtime.shutdown()
                    else:
                        self.runtime.disable(play_stop_beep=reason == "emergency")
                    self.runtime.shutdown()
                    self.assertEqual(self.down.call_count, int(injected))
                    self.assertEqual(self.up.call_count, int(injected))

    def test_injection_failure_uses_worker_failure_path(self):
        """A failed native down disables the runtime without claiming a hold."""
        self.down.side_effect = OSError("SendInput failed")
        self.runtime._lifecycle_generation = 1
        self.runtime._refresh_worker_bindings = Mock(return_value=True)
        self.runtime._ensure_input_listener = Mock()
        self.runtime._notify_failure = Mock()
        self.runtime._run_poll_loop = lambda *_args: self.runtime._process_polled_state(self.binding, False, 11.1, False)
        self.runtime._poll_inputs(1, threading.Event(), threading.Event())
        self.assertFalse(self.runtime.enabled)
        self.assertFalse(self.runtime._key_hold_injected)
        self.up.assert_not_called()
        self.runtime._notify_failure.assert_called_once()

    def test_disable_waits_for_inflight_down_then_releases_it(self):
        """Cancellation cannot overtake native injection and leave a late held key."""
        entered = threading.Event()
        finish = threading.Event()
        disabled = threading.Event()

        def down(action: str, *, should_pause: bool = True):
            """Keep native submission in flight until the test allows it to finish."""
            entered.set()
            if not finish.wait(2):
                raise RuntimeError("test handoff timed out")
            return 0x11, 8

        def disable():
            """Request cancellation on another thread while down holds the lock."""
            self.runtime.disable()
            disabled.set()

        self.down.side_effect = down
        polling = threading.Thread(target=self.runtime._process_polled_state, args=(self.binding, False, 11.1, False))
        stopping = threading.Thread(target=disable)
        polling.start()
        try:
            self.assertTrue(entered.wait(1))
            stopping.start()
            self.assertFalse(disabled.wait(0.05))
        finally:
            finish.set()
            polling.join(2)
            if stopping.ident is not None:
                stopping.join(2)
        self.assertTrue(disabled.is_set())
        self.up.assert_called_once_with((0x11, 8))
        self.assertFalse(self.runtime._key_hold_injected)


if __name__ == "__main__":
    unittest.main()
