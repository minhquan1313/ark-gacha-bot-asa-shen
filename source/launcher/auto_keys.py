import ctypes
import threading
import time
from ctypes import wintypes

from source.launcher.config.constants import AUTO_KEYS_ACTIONS
from source.utility import local_player

POLL_INTERVAL = 0.01
BINDING_RETRY_INTERVAL = 0.5
KEY_DOWN_MASK = 0x8000
MOUSE_VK_CODES = {
    "leftmousebutton": 0x01,
    "rightmousebutton": 0x02,
    "middlemousebutton": 0x04,
}
MOUSE_PRESS_DURATION = 0.02


def resolve_supported_keys(actions=AUTO_KEYS_ACTIONS):
    """Resolve supported actions from Steam's installed ARK Input.ini."""
    from source.launcher import ark_game_setup

    try:
        input_path = ark_game_setup.find_game_user_input_path(
            restart_steam_if_missing=False
        )
    except (OSError, RuntimeError):
        return {}, None

    resolved = {}
    for action in actions:
        try:
            key = str(local_player.get_input_settings(action, input_path=input_path))
            if key.casefold() != action.casefold():
                resolved[action] = key
        except (FileNotFoundError, OSError, TypeError, ValueError):
            continue
    return resolved, input_path


class AutoKeysRuntime:
    """Poll supported physical inputs and repeat a held ARK action."""

    def __init__(
        self,
        actions=AUTO_KEYS_ACTIONS,
        status_callback=None,
        failure_callback=None,
        state_callback=None,
    ):
        self.actions = tuple(actions)
        self.status_callback = status_callback
        self.failure_callback = failure_callback
        self.state_callback = state_callback
        self.interval = 0.25
        self.hold_duration = 1.0
        self.enabled = False
        self.state = "disabled"
        self._repeat_stop_event = threading.Event()
        self._poll_thread = None
        self._repeat_thread = None
        self._poll_stop_event = None
        self._binding_refresh_event = None
        self._worker_threads = set()
        self._lock = threading.RLock()
        self._lifecycle_generation = 0
        self._binding_revision = 0
        self._selected_actions = set(self.actions)
        self._bindings = {}
        self._binding_signature = None
        self._last_states = {}
        self._pending = None
        self._pending_started_at = None
        self._active = None
        self._stop_armed = False
        self._synthetic_down = set()

    def configure(self, settings, allow_enable: bool = True):
        """Apply settings and start or stop the Auto keys polling worker."""
        auto_keys = settings.get("auto_keys", {})
        action_settings = auto_keys.get("actions", {})
        if not isinstance(action_settings, dict):
            action_settings = {}
        selected_actions = {
            action for action in self.actions if bool(action_settings.get(action, True))
        }
        with self._lock:
            self.interval = float(auto_keys.get("interval", 0.25))
            self.hold_duration = float(auto_keys.get("hold_duration", 1.0))
            selection_changed = selected_actions != self._selected_actions
            self._selected_actions = selected_actions
            if selection_changed:
                self._binding_revision += 1
                refresh_event = self._binding_refresh_event
                if refresh_event is not None:
                    refresh_event.set()
            active_action = self._bindings.get(self._active)
            pending_action = self._bindings.get(self._pending)
        if (active_action and active_action not in selected_actions) or (
            pending_action and pending_action not in selected_actions
        ):
            self._stop_repeat()
        if allow_enable and bool(auto_keys.get("enabled", False)):
            self.enable()
        else:
            self.disable()

    def enable(self):
        """Start polling supported physical inputs on Windows."""
        with self._lock:
            if self.enabled:
                return
        if not hasattr(ctypes, "windll"):
            self._set_state("disabled")
            self._notify_failure("Auto keys is only available on Windows.")
            return
        with self._lock:
            self.enabled = True
            self._lifecycle_generation += 1
            generation = self._lifecycle_generation
            stop_event = threading.Event()
            refresh_event = threading.Event()
            self._poll_stop_event = stop_event
            self._binding_refresh_event = refresh_event
            thread = threading.Thread(
                target=self._poll_inputs,
                args=(generation, stop_event, refresh_event),
                name="auto-keys-poll",
                daemon=True,
            )
            self._poll_thread = thread
            self._worker_threads.add(thread)
        self._reset_detection_state()
        self._set_state("starting")
        thread.start()
        self._notify("Polling starting.")

    def disable(self, play_stop_beep: bool = False):
        """Stop polling and release any generated input."""
        with self._lock:
            was_enabled = self.enabled
            had_active_repeat = self._active is not None
            self.enabled = False
            self._lifecycle_generation += 1
            stop_event = self._poll_stop_event
            refresh_event = self._binding_refresh_event
            self._poll_stop_event = None
            self._binding_refresh_event = None
            self._poll_thread = None
        if stop_event is not None:
            stop_event.set()
        if refresh_event is not None:
            refresh_event.set()
        self._stop_repeat()
        self._reset_detection_state()
        self._set_state("disabled")
        if was_enabled:
            if play_stop_beep and not had_active_repeat:
                self._play_beep(False)
            self._notify("Polling stopped.")
        return was_enabled

    def shutdown(self):
        """Stop Auto Keys and briefly join retired polling workers on launcher exit."""
        self.disable()
        deadline = time.monotonic() + 2.0
        with self._lock:
            threads = tuple(self._worker_threads)
        for thread in threads:
            if thread is threading.current_thread():
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(timeout=remaining)

    def suspend_for_automation(self):
        """Disable Auto Keys and announce an automation-owned suspension."""
        was_enabled = self.disable(play_stop_beep=True)
        if was_enabled:
            self._notify("Suspended while automation is running.")
        return was_enabled

    def _reset_detection_state(self):
        with self._lock:
            self._last_states = {}
            self._pending = None
            self._pending_started_at = None
            self._stop_armed = False
            self._synthetic_down.clear()

    def _resolve_bindings(self, actions=None):
        from source.utility import utils

        selected_actions = tuple(self.actions if actions is None else actions)
        bindings = {}
        if not selected_actions:
            return bindings
        resolved_keys, _input_path = resolve_supported_keys(selected_actions)
        for action, resolved in resolved_keys.items():
            try:
                normalized = resolved.casefold()
                if normalized in MOUSE_VK_CODES:
                    bindings[("mouse", MOUSE_VK_CODES[normalized])] = action
                    continue
                vk_code = utils.keymap_return(resolved)
                if vk_code is not None:
                    bindings[("keyboard", int(vk_code))] = action
            except (FileNotFoundError, RuntimeError, OSError, TypeError, ValueError):
                continue
        return bindings

    def _report_bindings(self, bindings, selected_actions):
        """Log a binding summary only when the applied selection changes."""
        binding_signature = tuple(
            sorted((kind, code, action) for (kind, code), action in bindings.items())
        )
        signature = (binding_signature, tuple(selected_actions))
        if signature != self._binding_signature:
            self._binding_signature = signature
            if binding_signature:
                details = ", ".join(
                    f"{action} -> {kind}:0x{code:02X}"
                    for kind, code, action in binding_signature
                )
                self._notify(f"Bindings resolved: {details}.")
            elif not selected_actions:
                self._notify("No Auto Keys actions are selected.")
            else:
                self._notify("No supported ARK bindings could be resolved yet.")

    def _ark_is_foreground(self):
        from source.utility import windows

        user32 = ctypes.windll.user32
        ark_hwnd = windows.ark_hwnd()
        foreground_hwnd = user32.GetForegroundWindow()
        if not ark_hwnd or not foreground_hwnd:
            return False
        ark_pid = wintypes.DWORD()
        foreground_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(ark_hwnd, ctypes.byref(ark_pid))
        user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(foreground_pid))
        return bool(ark_pid.value) and ark_pid.value == foreground_pid.value

    def _poll_inputs(self, generation, stop_event, refresh_event):
        try:
            if not self._refresh_worker_bindings(generation, stop_event):
                return
            if not self._set_state_for_generation(generation, "ready"):
                return
            self._notify("Polling started.")
            self._run_poll_loop(generation, stop_event, refresh_event)
        except Exception as exc:
            self._fail_worker(generation, stop_event, refresh_event, exc)
        finally:
            current_thread = threading.current_thread()
            with self._lock:
                self._worker_threads.discard(current_thread)
                if self._poll_thread is current_thread:
                    self._poll_thread = None

    def _fail_worker(self, generation, stop_event, refresh_event, exc):
        """Disable the current lifecycle when its polling worker fails unexpectedly."""
        with self._lock:
            if not self.enabled or generation != self._lifecycle_generation:
                return
            self.enabled = False
            self._lifecycle_generation += 1
            if self._poll_stop_event is stop_event:
                self._poll_stop_event = None
            if self._binding_refresh_event is refresh_event:
                self._binding_refresh_event = None
        stop_event.set()
        refresh_event.set()
        self._stop_repeat()
        self._reset_detection_state()
        self._set_state("disabled")
        self._notify_failure(f"Auto Keys runtime failed: {exc}")

    def _run_poll_loop(self, generation, stop_event, refresh_event):
        """Poll current bindings and refresh them without blocking the GUI thread."""
        next_binding_retry = time.monotonic() + BINDING_RETRY_INTERVAL
        while self._worker_is_current(generation, stop_event):
            now = time.monotonic()
            if refresh_event.is_set():
                refresh_event.clear()
                if not self._refresh_worker_bindings(generation, stop_event):
                    return
                next_binding_retry = now + BINDING_RETRY_INTERVAL
            if not self._ark_is_foreground():
                self._cancel_for_focus_loss()
                stop_event.wait(POLL_INTERVAL)
                continue
            with self._lock:
                has_bindings = bool(self._bindings)
                has_selected_actions = bool(self._selected_actions)
            if not has_bindings and has_selected_actions and now >= next_binding_retry:
                if not self._refresh_worker_bindings(generation, stop_event):
                    return
                next_binding_retry = now + BINDING_RETRY_INTERVAL
            with self._lock:
                bindings = tuple(self._bindings)
            for binding in bindings:
                is_down = bool(
                    ctypes.windll.user32.GetAsyncKeyState(binding[1]) & KEY_DOWN_MASK
                )
                self._process_polled_state(binding, is_down, now)
            stop_event.wait(POLL_INTERVAL)

    def _refresh_worker_bindings(self, generation, stop_event):
        """Resolve and apply the newest selected-action revision for one worker."""
        while self._worker_is_current(generation, stop_event):
            with self._lock:
                revision = self._binding_revision
                selected_actions = tuple(
                    action
                    for action in self.actions
                    if action in self._selected_actions
                )
            bindings = self._resolve_bindings(selected_actions)
            with self._lock:
                if not self._worker_is_current(generation, stop_event):
                    return False
                if revision != self._binding_revision:
                    continue
                self._bindings = bindings
                self._last_states = {
                    binding: state
                    for binding, state in self._last_states.items()
                    if binding in bindings
                }
            self._report_bindings(bindings, selected_actions)
            return True
        return False

    def _worker_is_current(self, generation, stop_event):
        with self._lock:
            return bool(
                self.enabled
                and generation == self._lifecycle_generation
                and not stop_event.is_set()
            )

    def _set_state_for_generation(self, generation, state):
        with self._lock:
            if not self.enabled or generation != self._lifecycle_generation:
                return False
            if self.state == state:
                return True
            self.state = state
        self._emit_state_callback(state)
        return True

    def _cancel_for_focus_loss(self):
        with self._lock:
            has_active_repeat = self._active is not None
            self._pending = None
            self._pending_started_at = None
            self._last_states = {}
        if has_active_repeat:
            self._stop_repeat()

    def _process_polled_state(self, binding, is_down, now):
        should_start = False
        should_stop = False
        with self._lock:
            if binding in self._synthetic_down:
                return
            was_down = self._last_states.get(binding, False)
            self._last_states[binding] = is_down

            if self._active == binding:
                if not self._stop_armed:
                    if not is_down:
                        self._stop_armed = True
                    return
                should_stop = is_down and not was_down
            elif self._active is not None:
                return
            elif self._pending == binding:
                if not is_down:
                    self._pending = None
                    self._pending_started_at = None
                elif now - self._pending_started_at >= self.hold_duration:
                    should_start = True
            elif is_down and not was_down and self._pending is None:
                self._pending = binding
                self._pending_started_at = now

        if should_stop:
            self._stop_repeat()
        elif should_start:
            self._start_repeat(binding)

    def _start_repeat(self, binding):
        with self._lock:
            if not self.enabled or self._pending != binding:
                return
            action = self._bindings.get(binding)
            if action is None:
                return
            self._pending = None
            self._pending_started_at = None
            self._active = binding
            self._stop_armed = False
            repeat_stop_event = threading.Event()
            self._repeat_stop_event = repeat_stop_event
            self._repeat_thread = threading.Thread(
                target=self._repeat,
                args=(action, binding, repeat_stop_event),
                name="auto-keys-repeat",
                daemon=True,
            )
            self._repeat_thread.start()
        self._play_beep(True)
        self._notify(f"Repeating {action}.")

    def _repeat(self, action, binding, stop_event=None):
        from source.utility import utils

        stop_event = stop_event or self._repeat_stop_event
        try:
            while self.enabled and not stop_event.is_set():
                if not self._ark_is_foreground():
                    break
                is_mouse = binding[0] == "mouse"
                if is_mouse:
                    with self._lock:
                        self._synthetic_down.add(binding)
                utils.action_down(action)
                press_duration = MOUSE_PRESS_DURATION if is_mouse else self.interval
                interrupted = stop_event.wait(press_duration)
                try:
                    utils.action_up(action)
                finally:
                    if is_mouse:
                        with self._lock:
                            self._synthetic_down.discard(binding)
                            self._last_states[binding] = False
                if interrupted or stop_event.wait(self.interval):
                    break
        except Exception as exc:
            self._notify(f"Repeat failed for {action}: {exc}")
        finally:
            with self._lock:
                stopped_without_request = self._active == binding
                if stopped_without_request:
                    self._active = None
                if self._repeat_thread is threading.current_thread():
                    self._repeat_thread = None
            if stopped_without_request:
                self._play_beep(False)
                self._notify("Repeating stopped.")

    def _stop_repeat(self):
        with self._lock:
            was_active = self._active is not None
            self._active = None
            self._pending = None
            self._pending_started_at = None
            self._stop_armed = False
            self._repeat_stop_event.set()
            thread = self._repeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self.interval + 0.25))
        with self._lock:
            if self._repeat_thread is thread:
                self._repeat_thread = None
            self._synthetic_down.clear()
        if was_active:
            self._play_beep(False)
            self._notify("Repeating stopped.")

    def _notify(self, message):
        if self.status_callback is None:
            return
        try:
            self.status_callback(message)
        except Exception:
            return

    def _set_state(self, state):
        """Publish one runtime lifecycle state when it changes."""
        with self._lock:
            if self.state == state:
                return
            self.state = state
        self._emit_state_callback(state)

    def _emit_state_callback(self, state):
        """Deliver a lifecycle state to the optional launcher callback."""
        if self.state_callback is None:
            return
        try:
            self.state_callback(state)
        except Exception:
            return

    def _notify_failure(self, message):
        self._notify(message)
        if self.failure_callback is None:
            return
        try:
            self.failure_callback(message)
        except Exception:
            return

    def _play_beep(self, started):
        """Play a transition beep without blocking polling."""

        def play():
            try:
                import winsound

                winsound.Beep(1100 if started else 500, 80)
            except Exception:
                return

        threading.Thread(target=play, name="auto-keys-beep", daemon=True).start()


__all__ = ["AUTO_KEYS_ACTIONS", "AutoKeysRuntime"]
