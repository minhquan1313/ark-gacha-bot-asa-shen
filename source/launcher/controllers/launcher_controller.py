import ctypes
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

from PySide6.QtCore import (
    Property,
    QAbstractNativeEventFilter,
    QObject,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from source.launcher import ark_game_setup
from source.launcher.constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    GAME_WINDOW_TITLE,
    SUPPORTED_GAME_RESOLUTIONS,
)
from source.launcher.deposit_helper_capture import (
    register_shift_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.native_window import WM_HOTKEY, WindowsMSG
from source.launcher.process_control import terminate_process_tree
from source.launcher.settings_store import save_settings
from source.launcher.system import (
    calculate_cpu_percent,
    find_window_size,
    get_cpu_times,
    get_memory_usage_gb,
    validate_ark_window,
)
from source.utility.debug_screenshots import cleanup_debug_screenshots_on_program_start


class LauncherHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def nativeEventFilter(self, event_type, message):
        if not self.controller.start_stop_hotkey_registered:
            return False, 0
        msg = WindowsMSG.from_address(int(message))
        if (
            msg.message == WM_HOTKEY
            and msg.wParam == self.controller.start_stop_hotkey_id
        ):
            self.controller.toggleProgram()
            return True, 0
        return False, 0


class LauncherController(QObject):
    changed = Signal()
    dialogRequested = Signal(str, str, str)
    toastRequested = Signal(str, str)
    logLine = Signal(str)

    def __init__(
        self, settings_controller, log_controller, queue_controller, parent=None
    ):
        super().__init__(parent)
        self.settings_controller = settings_controller
        self.log_controller = log_controller
        self.queue_controller = queue_controller
        self.process = None
        self.program_stopping = False
        self.stop_deadline = None
        self.shutdown_started = False
        self.output_reader_stop = threading.Event()
        self.output_reader_thread = None
        self.log_tail_stop = threading.Event()
        self.log_tail_thread = None
        self.log_file_position = 0
        self.start_time = None
        self.last_activity = "--:--:--"
        self._cpu_times = get_cpu_times()
        self._memory = "N/A"
        self._cpu = "0%"
        self._clock = time.strftime("%I:%M:%S %p")
        self._current_page = "dashboard"
        self._root_window = None
        self.start_stop_hotkey_id = (id(self) & 0x3FFF) + 0x4000
        self.start_stop_hotkey_registered = False
        self.hotkey_filter = LauncherHotkeyFilter(self)

        self.log_controller.activityChanged.connect(self._mark_activity)
        self.log_controller.queueSnapshotReceived.connect(
            self.queue_controller.updateSnapshot
        )
        self.settings_controller.saved.connect(self.log_controller.append)
        self.settings_controller.error.connect(
            lambda title, message: self.dialogRequested.emit(title, message, "error")
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

    @Property(str, constant=True)
    def appName(self):
        return APP_NAME

    @Property(str, constant=True)
    def appTitle(self):
        return APP_TITLE

    @Property(str, constant=True)
    def appVersion(self):
        return APP_VERSION

    @Property(str, notify=changed)
    def currentPage(self):
        return self._current_page

    @Property(bool, notify=changed)
    def running(self):
        return self.is_running()

    @Property(str, notify=changed)
    def startStopText(self):
        if self.program_stopping:
            return "STOPPING..."
        if self.is_running():
            return "STOP PROGRAM"
        return "START PROGRAM"

    @Property(str, notify=changed)
    def startStopVariant(self):
        if self.program_stopping:
            return "secondary"
        if self.is_running():
            return "danger"
        return "primary"

    @Property(str, notify=changed)
    def serverNumber(self):
        return self.settings_controller.serverNumber

    @Property(str, notify=changed)
    def uptime(self):
        if self.start_time and self.is_running():
            elapsed = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "00:00:00"

    @Property(str, notify=changed)
    def memoryUsage(self):
        return self._memory

    @Property(str, notify=changed)
    def cpuUsage(self):
        return self._cpu

    @Property(str, notify=changed)
    def runnerState(self):
        return "RUNNING" if self.is_running() else "STOPPED"

    @Property(str, notify=changed)
    def lastActivity(self):
        return self.last_activity

    @Property(str, notify=changed)
    def clock(self):
        return self._clock

    @Slot(str)
    def showPage(self, page_name):
        self._current_page = page_name
        self.changed.emit()

    @Slot(QObject)
    def registerWindow(self, window):
        self._root_window = window
        self._register_start_stop_hotkey(window)

    @Slot(int, int)
    def persistWindowSize(self, width, height):
        settings = self.settings_controller.settings()
        settings["launcher_width"] = max(420, int(width))
        settings["launcher_height"] = max(640, int(height))
        try:
            save_settings(settings)
            self.settings_controller.refresh()
        except Exception:
            pass

    @Slot()
    def toggleProgram(self):
        if self.is_running():
            self.stopProgram()
        else:
            self.startProgram()

    @Slot()
    def startProgram(self):
        if self.shutdown_started or self.program_stopping:
            return
        if self.process is not None and self.process.poll() is not None:
            self._finalize_program_stop()
        if self.is_running():
            self.dialogRequested.emit(
                "Program Running", "The program is already running.", "info"
            )
            return
        if not self.require_ark_window("start program"):
            return

        try:
            cleanup_debug_screenshots_on_program_start()
            self.process = subprocess.Popen(
                [sys.executable, "-u", "main_program.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.start_time = time.time()
            self.log_controller.append("[INFO] Started offline runner.\n")
            self.output_reader_stop = threading.Event()
            self.output_reader_thread = threading.Thread(
                target=self._read_output, args=(self.process,), daemon=True
            )
            self.output_reader_thread.start()
        except Exception as exc:
            self.dialogRequested.emit("Start Failed", str(exc), "error")
        self.changed.emit()

    @Slot()
    def stopProgram(self):
        if self.is_running():
            self.program_stopping = True
            self.stop_deadline = time.time() + 5
            self.log_controller.append("[WARN] Stopping program...\n")
            terminate_process_tree(self.process)
            self.changed.emit()

    @Slot()
    def startGame(self):
        try:
            self.log_controller.append("[INFO] Preparing ARK for 1920x1080 launch...\n")
            settings_path = ark_game_setup.prepare_and_launch_game()
            self.log_controller.append(
                f"[SUCCESS] ARK launch requested through Steam. Config: {settings_path}\n"
            )
        except Exception as exc:
            self.log_controller.append(f"[ERROR] Start game failed: {exc}\n")
            self.dialogRequested.emit("Start Game Failed", str(exc), "error")
        self.changed.emit()

    @Slot()
    def restoreGameSettings(self):
        if not ark_game_setup.restore_state_exists():
            return
        try:
            self.log_controller.append(
                "[INFO] Restoring ARK display and config settings...\n"
            )
            settings_path = ark_game_setup.restore_game_settings()
            self.log_controller.append(
                f"[SUCCESS] Restored ARK display and config: {settings_path}\n"
            )
        except Exception as exc:
            self.log_controller.append(f"[ERROR] Restore game settings failed: {exc}\n")
            self.dialogRequested.emit("Restore Game Settings Failed", str(exc), "error")

    @Slot()
    def shutdown(self):
        if self.shutdown_started:
            return
        self.shutdown_started = True
        self.timer.stop()
        self._unregister_start_stop_hotkey()
        self.output_reader_stop.set()
        if self.is_running():
            terminate_process_tree(self.process)
        self._close_output_reader(self.process)

    @Slot(result=bool)
    def shouldShowStartGame(self):
        game_size = find_window_size(GAME_WINDOW_TITLE)
        return game_size is None or game_size not in SUPPORTED_GAME_RESOLUTIONS

    def tick(self):
        if self.shutdown_started:
            return
        self._poll_program_stop()
        self._clock = time.strftime("%I:%M:%S %p")
        self._sync_system_stats()
        self.changed.emit()

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def require_ark_window(self, action):
        try:
            validate_ark_window()
        except RuntimeError as exc:
            message = str(exc)
            self.log_controller.append(f"[ERROR] Cannot {action}: {message}\n")
            self.dialogRequested.emit(f"{GAME_WINDOW_TITLE} Required", message, "error")
            return False
        return True

    def _poll_program_stop(self):
        if self.process is None:
            return
        if self.process.poll() is not None:
            self._finalize_program_stop()
            return
        if self.program_stopping and time.time() >= self.stop_deadline:
            self.log_controller.append(
                "[WARN] Program did not stop in 5 seconds; killing it.\n"
            )
            self.process.kill()

    def _finalize_program_stop(self):
        was_stopping = self.program_stopping
        self._close_output_reader(self.process)
        self.process = None
        self.program_stopping = False
        self.stop_deadline = None
        if was_stopping:
            self.log_controller.append("[WARN] Program stopped.\n")
        self.changed.emit()

    def _read_output(self, process):
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if self.output_reader_stop.is_set():
                break
            self.log_controller.append(line)
        if not self.output_reader_stop.is_set():
            self.log_controller.append("[WARN] Program output stream closed.\n")

    def _close_output_reader(self, process):
        self.output_reader_stop.set()
        if process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except (OSError, ValueError):
                pass
        thread = self.output_reader_thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=1)
        self.output_reader_thread = None

    def _sync_system_stats(self):
        if psutil:
            memory = psutil.virtual_memory()
            used_gb = memory.used / (1024**3)
            total_gb = memory.total / (1024**3)
            self._memory = f"{used_gb:.1f}G / {total_gb:.1f}G"
            self._cpu = f"{psutil.cpu_percent(interval=None):.0f}%"
            return
        memory = get_memory_usage_gb()
        if memory:
            self._memory = f"{memory[0]:.1f}G / {memory[1]:.1f}G"
        current_times = get_cpu_times()
        cpu_percent = calculate_cpu_percent(self._cpu_times, current_times)
        self._cpu_times = current_times or self._cpu_times
        self._cpu = f"{cpu_percent:.0f}%" if cpu_percent is not None else "0%"

    def _mark_activity(self, _line):
        self.last_activity = time.strftime("%H:%M:%S")
        self.changed.emit()

    def _register_start_stop_hotkey(self, window):
        if not hasattr(ctypes, "windll") or window is None:
            return
        try:
            hwnd = int(window.winId())
            self.start_stop_hotkey_registered = register_shift_alt_n_hotkey(
                hwnd, self.start_stop_hotkey_id
            )
            app = QGuiApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self.hotkey_filter)
        except Exception:
            self.start_stop_hotkey_registered = False

    def _unregister_start_stop_hotkey(self):
        if not self.start_stop_hotkey_registered or not hasattr(ctypes, "windll"):
            self.start_stop_hotkey_registered = False
            return
        try:
            if self._root_window is not None:
                unregister_hotkey(
                    int(self._root_window.winId()), self.start_stop_hotkey_id
                )
        except Exception:
            pass
        self.start_stop_hotkey_registered = False
