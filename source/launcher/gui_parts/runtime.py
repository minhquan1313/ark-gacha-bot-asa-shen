import contextlib
import ctypes
import subprocess
import sys
import threading
import time

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from source.launcher.config.constants import (
    COLORS,
    GAME_WINDOW_TITLE,
    SUPPORTED_GAME_RESOLUTIONS,
)
from source.launcher.runner_overlay import RunnerOverlay
from source.launcher.utils.deposit_helper_capture import (
    register_shift_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.utils.native_window import (
    WM_HOTKEY,
    WindowsMSG,
)
from source.launcher.utils.process_control import terminate_process_tree
from source.launcher.utils.system import (
    calculate_cpu_percent,
    find_window_size,
    get_cpu_times,
    get_memory_usage_gb,
)
from source.utility.debug_screenshots import cleanup_debug_screenshots_on_program_start

START_GAME_DISABLE_DELAY = 10000
RUNNER_LAUNCH_DELAY_MS = 120
RUNNER_READY_MESSAGE = "__RUNNER_READY__"
RUNNER_OVERLAY_READY_MESSAGE = "__RUNNER_OVERLAY_READY__"


class RuntimeGuiMixin:
    def toggle_program(self):
        if self.is_program_running():
            self.stop_program()
        else:
            self.start_program()

    def is_program_running(self):
        return self.process is not None and self.process.poll() is None

    def _register_start_stop_hotkey(self):
        if not hasattr(ctypes, "windll"):
            return
        try:
            self.start_stop_hotkey_registered = register_shift_alt_n_hotkey(
                int(self.winId()), self.start_stop_hotkey_id
            )
        except Exception:
            self.start_stop_hotkey_registered = False

    def _unregister_start_stop_hotkey(self):
        if not self.start_stop_hotkey_registered or not hasattr(ctypes, "windll"):
            self.start_stop_hotkey_registered = False
            return
        with contextlib.suppress(Exception):
            unregister_hotkey(int(self.winId()), self.start_stop_hotkey_id)
        self.start_stop_hotkey_registered = False

    def _handle_native_hotkey_message(self, message):
        if not self.start_stop_hotkey_registered:
            return False
        msg = WindowsMSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.start_stop_hotkey_id:
            self.toggle_program()
            return True
        return False

    def _update_start_stop_button(self):
        if not hasattr(self, "start_stop_button"):
            return

        if self.program_stopping:
            target_text = "STOPPING..."
            target_variant = "secondary"
        elif getattr(self, "runner_loading", False) or self.is_program_running():
            target_text = "STOP PROGRAM"
            target_variant = "danger"
        else:
            target_text = "START GBOT"
            target_variant = "primary"

        if self.start_stop_button.text() != target_text:
            self.start_stop_button.setText(target_text)
        if self.start_stop_button.variant != target_variant:
            self.start_stop_button.set_variant(target_variant)
        target_enabled = not self.program_stopping
        if self.start_stop_button.isEnabled() != target_enabled:
            self.start_stop_button.setEnabled(target_enabled)

    def start_program(self):
        if self.shutdown_started or self.program_stopping:
            return
        if self.process is not None and self.process.poll() is not None:
            self._finalize_program_stop()
        if self.process and self.process.poll() is None:
            self.dialog("Program Running", "The program is already running.", "info")
            return

        if not self.require_ark_window("start program"):
            return

        try:
            self.queue_snapshot = {"running": [], "active": [], "waiting": []}
            self.running_task_name = None
            self.runner_loading = True
            self.runner_launch_pending = True
            self.runner_ready_pending = False
            self.runner_log_start_index = len(self.log_lines)
            self._show_runner_overlay()
            self._update_start_stop_button()
            QTimer.singleShot(RUNNER_LAUNCH_DELAY_MS, self._launch_program_process)
        except Exception as exc:
            self.runner_loading = False
            self.runner_launch_pending = False
            self.runner_ready_pending = False
            self._hide_runner_overlay()
            self._update_start_stop_button()
            self.dialog("Start Failed", str(exc), "error")

    def _launch_program_process(self):
        if (
            self.shutdown_started
            or self.program_stopping
            or not self.runner_launch_pending
            or not self.runner_loading
        ):
            return

        try:
            self.runner_launch_pending = False
            self.close_external_helpers()
            cleanup_debug_screenshots_on_program_start()
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-m", "source.launcher.runner_process"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.start_time = time.time()
            self.append_log("[INFO] Started offline runner.\n")
            self._update_start_stop_button()
            self.start_log_tail()
            self.output_reader_stop = threading.Event()
            self.output_reader_thread = threading.Thread(
                target=self.read_output, args=(self.process,), daemon=True
            )
            self.output_reader_thread.start()
        except Exception as exc:
            self.runner_loading = False
            self.runner_launch_pending = False
            self.runner_ready_pending = False
            self._hide_runner_overlay()
            self._update_start_stop_button()
            self.dialog("Start Failed", str(exc), "error")

    def stop_program(self):
        if self.runner_loading and (
            self.process is None or self.process.poll() is not None
        ):
            self.runner_launch_pending = False
            self.runner_ready_pending = False
            self.runner_loading = False
            self.append_log("[WARN] Runner startup cancelled.\n")
            self._update_start_stop_button()
            self._hide_runner_overlay()
            return
        if self.process and self.process.poll() is None:
            self.program_stopping = True
            self.stop_deadline = time.time() + 5
            self.append_log("[WARN] Stopping program...\n")
            self._update_start_stop_button()
            terminate_process_tree(self.process)
            self._hide_runner_overlay()

    def _poll_program_stop(self):
        if self.process is None:
            return
        if self.process.poll() is not None:
            self._finalize_program_stop()
            return
        if (
            self.program_stopping
            and self.stop_deadline is not None
            and time.time() >= self.stop_deadline
        ):
            self.append_log("[WARN] Program did not stop in 5 seconds; killing it.\n")
            self.process.kill()

    def _finalize_program_stop(self):
        was_stopping = self.program_stopping
        was_loading = getattr(self, "runner_loading", False)
        self.stop_log_tail()
        self._close_output_reader(self.process)
        self.process = None
        self.runner_loading = False
        self.runner_launch_pending = False
        self.program_stopping = False
        self.stop_deadline = None
        if was_stopping:
            self.append_log("[WARN] Program stopped.\n")
        elif was_loading:
            self.append_log("[ERROR] Runner stopped before it finished loading.\n")
        self.runner_ready_pending = False
        self._update_start_stop_button()
        self._hide_runner_overlay()

    def _show_runner_overlay(self):
        if (
            not self.is_program_running() and not self.runner_loading
        ) or self.program_stopping:
            self._hide_runner_overlay()
            return
        overlay = getattr(self, "runner_overlay", None)
        try:
            if overlay is None:
                overlay = RunnerOverlay(self)
                self.runner_overlay = overlay
            overlay.stop_button.setText("STOP")
            overlay.stop_button.set_variant("danger")
            overlay.stop_button.setEnabled(True)
            if self.runner_loading:
                overlay.refresh_loading()
            else:
                overlay.refresh(self.queue_snapshot, self._runner_overlay_log_lines())
            overlay.show()
            overlay.raise_()
        except RuntimeError:
            self.runner_overlay = None

    def _hide_runner_overlay(self):
        overlay = getattr(self, "runner_overlay", None)
        self.runner_overlay = None
        if overlay is None:
            return
        with contextlib.suppress(RuntimeError):
            overlay.close()

    def _sync_runner_overlay(self):
        if self.runner_loading and not self.program_stopping:
            if getattr(self, "runner_overlay", None) is None:
                self._show_runner_overlay()
            return
        if self.is_program_running() and not self.program_stopping:
            self._show_runner_overlay()
        else:
            self._hide_runner_overlay()

    def _runner_overlay_log_lines(self):
        """Return only log lines emitted after the current runner launch started."""
        start_index = getattr(self, "runner_log_start_index", 0)
        if start_index < 0 or start_index > len(self.log_lines):
            start_index = 0
        return self.log_lines[start_index:]

    def read_output(self, process):
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if self.output_reader_stop.is_set():
                break
            if line.strip() == RUNNER_READY_MESSAGE:
                self.runner_ready.emit()
                continue
            self._emit_log_line(line)
        if not self.output_reader_stop.is_set():
            self.stop_log_tail()
            self._emit_log_line("[WARN] Program output stream closed.\n")

    def _close_output_reader(self, process):
        self.output_reader_stop.set()
        if process is not None and process.stdout is not None:
            with contextlib.suppress(OSError, ValueError):
                process.stdout.close()
        thread = self.output_reader_thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=1)
        self.output_reader_thread = None

    def _emit_log_line(self, line):
        if not self.shutdown_started:
            self.log_bridge.line.emit(line)

    def _on_runner_ready(self):
        """Reveal live runner state after the bot completes startup preparation."""
        if not self.runner_loading or not self.is_program_running():
            return
        self.runner_ready_pending = True
        self._reveal_runner_overlay_if_ready()

    def _reveal_runner_overlay_if_ready(self):
        """Show the populated overlay and release the bot once task state exists."""
        snapshot = getattr(self, "queue_snapshot", {})
        has_tasks = any(snapshot.get(key) for key in ("running", "active", "waiting"))
        if not (
            getattr(self, "runner_ready_pending", False)
            and self.runner_loading
            and self.is_program_running()
            and has_tasks
        ):
            return
        self.runner_loading = False
        self.runner_ready_pending = False
        self._show_runner_overlay()
        QApplication.processEvents()

        process = getattr(self, "process", None)
        stdin = getattr(process, "stdin", None)
        if process is None or process.poll() is not None or stdin is None:
            return
        try:
            stdin.write(f"{RUNNER_OVERLAY_READY_MESSAGE}\n")
            stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.append_log("[ERROR] Unable to confirm runner overlay readiness.\n")
            return
        self._render_logs()

    def _tick(self):
        if self.shutdown_started:
            return
        self._poll_program_stop()
        self._sync_runner_overlay()
        if self.current_filter in {"QUEUE", "RUNNING"}:
            self._render_logs()
        self._update_start_stop_button()
        self._update_start_game_button_visibility()
        self._sync_ark_status_labels()
        if hasattr(self, "server_value"):
            server_number = self.form_values.get(
                "server_number", self.settings.get("server_number", "0")
            )
            field = self.fields.get("server_number")
            if field is not None:
                server_number = field.text()
            self.server_value.setText(str(server_number))
            self.active_value.setText(
                str(
                    len(self.queue_snapshot.get("running", []))
                    + len(self.queue_snapshot.get("active", []))
                )
            )
            self.waiting_value.setText(str(len(self.queue_snapshot.get("waiting", []))))
            if self.start_time and self.process and self.process.poll() is None:
                elapsed = int(time.time() - self.start_time)
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.uptime_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                self.uptime_value.setText("00:00:00")

            memory_text = "N/A"
            if psutil:
                memory = psutil.virtual_memory()
                used_gb = memory.used / (1024**3)
                total_gb = memory.total / (1024**3)
                memory_text = f"{used_gb:.1f}G / {total_gb:.1f}G"
                self.memory_meter.set_percent((used_gb / total_gb) * 100)
            else:
                memory = get_memory_usage_gb()
                if memory:
                    memory_text = f"{memory[0]:.1f}G / {memory[1]:.1f}G"
                    self.memory_meter.set_percent((memory[0] / memory[1]) * 100)
            self.memory_value.setText(memory_text)

            if psutil:
                cpu_percent = psutil.cpu_percent(interval=None)
                self.cpu_value.setText(f"{cpu_percent:.0f}%")
                self.cpu_meter.set_percent(cpu_percent)
            else:
                current_times = get_cpu_times()
                cpu_percent = calculate_cpu_percent(self._cpu_times, current_times)
                self._cpu_times = current_times or self._cpu_times
                self.cpu_value.setText(
                    f"{cpu_percent:.0f}%" if cpu_percent is not None else "0%"
                )
                self.cpu_meter.set_percent(cpu_percent or 0)

            running = self.process and self.process.poll() is None
            self.runner_value.setText("RUNNING" if running else "STOPPED")
            self.activity_value.setText(self.last_activity)
            self.clock_value.setText(time.strftime("%I:%M:%S %p"))

    def _sync_ark_status_labels(self):
        try:
            game_size = find_window_size(GAME_WINDOW_TITLE)
        except Exception:
            game_size = None
        if game_size is None:
            chrome_text = "ARK NOT FOUND"
            sidebar_text = "STATUS: WAITING"
            color = COLORS["yellow"]
        elif game_size not in SUPPORTED_GAME_RESOLUTIONS:
            chrome_text = "ARK SIZE WARN"
            sidebar_text = "STATUS: CHECK"
            color = COLORS["yellow"]
        else:
            chrome_text = "SYSTEM READY"
            sidebar_text = "STATUS: READY  +"
            color = COLORS["green"]

        title_status = getattr(getattr(self, "title_bar", None), "status_label", None)
        if title_status is not None:
            title_status.setText(chrome_text)
            title_status.setStyleSheet(f"color: {color};")
        sidebar_ready = getattr(self, "sidebar_ready", None)
        if sidebar_ready is not None:
            sidebar_ready.setText(sidebar_text)
            sidebar_ready.setStyleSheet(f"color: {color};")
