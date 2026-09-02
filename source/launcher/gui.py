import os
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

from source.launcher.auto_keys import AutoKeysRuntime
from source.launcher.components.widgets import (
    LogBridge,
)
from source.launcher.config.constants import (
    APP_NAME,
    ASSETS,
    PHONE_MINIMUM_SIZE,
)
from source.launcher.gui_parts.dialogs import DialogsGuiMixin
from source.launcher.gui_parts.logs import LogsGuiMixin
from source.launcher.gui_parts.runtime import RuntimeGuiMixin
from source.launcher.gui_parts.settings_state import SettingsStateGuiMixin
from source.launcher.gui_parts.window import WindowGuiMixin
from source.launcher.pages import LauncherPagesMixin
from source.launcher.utils.settings_store import load_settings, save_settings
from source.launcher.utils.system import (
    get_cpu_times,
)

START_GAME_DISABLE_DELAY = 10000
RUNNER_READY_MESSAGE = "__RUNNER_READY__"


class SettingsGUI(
    WindowGuiMixin,
    SettingsStateGuiMixin,
    RuntimeGuiMixin,
    LogsGuiMixin,
    DialogsGuiMixin,
    LauncherPagesMixin,
    QMainWindow,
):
    start_game_enabled_changed = Signal(bool)
    runner_ready = Signal()
    update_check_finished = Signal(object, bool)
    auto_keys_failure = Signal(str)
    auto_keys_state_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Launcher")
        if os.path.exists(ASSETS["logo"]):
            self.setWindowIcon(QIcon(ASSETS["logo"]))
            QApplication.setWindowIcon(QIcon(ASSETS["logo"]))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMinimumSize(*PHONE_MINIMUM_SIZE)
        self.settings = load_settings()
        self.resize(
            self.settings["launcher_width"],
            self.settings["launcher_height"],
        )

        self.process = None
        self.program_stopping = False
        self.runner_loading = False
        self.runner_launch_pending = False
        self.runner_ready_pending = False
        self.stop_deadline = None
        self.shutdown_started = False
        self.queue_snapshot = {"running": [], "active": [], "waiting": []}
        self.running_history = []
        self.running_task_name = None
        self.log_lines = []
        self.current_filter = "ALL"
        self.form_values = self.settings.copy()
        self.fields = {}
        self.nav_buttons = {}
        self.external_helpers = []
        self.auto_keys_automation_suspensions = set()
        self.auto_keys_restore_after_automation = False
        self.auto_keys_runtime_state = "disabled"
        self.log_bridge = LogBridge()
        self.log_bridge.line.connect(self.append_log)
        self.auto_keys_failure.connect(self._handle_auto_keys_failure)
        self.auto_keys_state_changed.connect(self._on_auto_keys_state_changed)
        self.auto_keys_runtime = AutoKeysRuntime(
            status_callback=self._auto_keys_status,
            failure_callback=self.auto_keys_failure.emit,
            state_callback=self.auto_keys_state_changed.emit,
        )
        self.auto_keys_runtime.configure(self.settings)
        self.runner_ready.connect(self._on_runner_ready)
        self.log_tail_stop = threading.Event()
        self.log_tail_thread = None
        self.output_reader_stop = threading.Event()
        self.output_reader_thread = None
        self.log_file_position = 0
        self.runner_log_start_index = 0
        self.active_count = 0
        self.waiting_count = 0
        self.start_time = None
        self.last_activity = "--:--:--"
        self._cpu_times = get_cpu_times()
        self.runner_overlay = None
        self.start_stop_hotkey_id = (id(self) & 0x3FFF) + 0x4000
        self.start_stop_hotkey_registered = False
        self.is_narrow_layout = False
        self.is_custom_maximized = False
        self.normal_geometry = None
        self.update_check_in_progress = False
        self.update_auto_check_enabled = True
        self.update_check_finished.connect(self._on_update_check_finished)

        self._build_ui()
        self.sync_configured_templates()
        self.resize(
            self.settings["launcher_width"],
            self.settings["launcher_height"],
        )
        self._build_timer()
        self.show_page("dashboard")
        self.load_previous_logs()
        self._register_start_stop_hotkey()
        self._schedule_auto_start()
        QTimer.singleShot(0, self._automatic_update_check)

    def _auto_keys_status(self, message):
        """Write Auto keys runtime transitions and failures to launcher logs."""
        self.log_bridge.line.emit(f"[AUTO KEYS] {message}\n")

    def _handle_auto_keys_failure(self, message):
        """Disable and persist Auto keys after a fatal hook setup failure."""
        auto_keys = dict(self.form_values.get("auto_keys", {}))
        auto_keys["enabled"] = False
        self.form_values["auto_keys"] = auto_keys
        self.settings = save_settings(self._collect_settings())
        self.form_values = self.settings.copy()
        self.auto_keys_runtime_state = "disabled"
        self._sync_auto_keys_suspension_ui()
        self.append_log(f"[AUTO KEYS] Disabled: {message}\n")
