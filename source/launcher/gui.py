import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque

try:
    import psutil
except ImportError:
    psutil = None

import contextlib

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from source.launcher import ark_game_setup
from source.launcher.components.widgets import (
    AnimatedButton,
    CyberDialog,
    LogBridge,
    TitleBar,
)
from source.launcher.config.constants import (
    APP_NAME,
    APP_TITLE,
    ASSETS,
    BREAKPOINT_NARROW_WIDTH,
    COLORS,
    DEFAULT_SETTINGS,
    ENABLE_NATIVE_CUSTOM_CHROME,
    GACHA_LOG_FILE,
    GAME_WINDOW_TITLE,
    MAX_LAUNCHER_LOG_LINES,
    PHONE_MINIMUM_SIZE,
    SUPPORTED_GAME_RESOLUTIONS,
    WINDOW_RESIZE_BORDER_PX,
)
from source.launcher.pages import LauncherPagesMixin
from source.launcher.runner_overlay import RunnerOverlay
from source.launcher.styles import launcher_style_sheet
from source.launcher.utils.deposit_helper_capture import (
    register_shift_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.utils.native_window import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTCAPTION,
    HTCLIENT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
    WM_HOTKEY,
    WM_NCHITTEST,
    WindowsMSG,
    global_pos_from_lparam,
)
from source.launcher.utils.process_control import terminate_process_tree
from source.launcher.utils.settings_store import load_settings, save_settings
from source.launcher.utils.system import (
    calculate_cpu_percent,
    find_window_size,
    get_cpu_times,
    get_memory_usage_gb,
    validate_ark_window,
)
from source.utility.debug_screenshots import cleanup_debug_screenshots_on_program_start

START_GAME_DISABLE_DELAY = 10000


class SettingsGUI(LauncherPagesMixin, QMainWindow):
    start_game_enabled_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Launcher")
        if os.path.exists(ASSETS["logo"]):
            self.setWindowIcon(QIcon(ASSETS["logo"]))
            QApplication.setWindowIcon(QIcon(ASSETS["logo"]))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(*PHONE_MINIMUM_SIZE)
        self.settings = load_settings()
        self.resize(
            self.settings["launcher_width"],
            self.settings["launcher_height"],
        )

        self.process = None
        self.program_stopping = False
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
        self.log_bridge = LogBridge()
        self.log_bridge.line.connect(self.append_log)
        self.log_tail_stop = threading.Event()
        self.log_tail_thread = None
        self.output_reader_stop = threading.Event()
        self.output_reader_thread = None
        self.log_file_position = 0
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

        self._build_ui()
        self._build_timer()
        self.show_page("dashboard")
        self.load_previous_logs()
        self._register_start_stop_hotkey()
        self._schedule_auto_start()

    def _build_ui(self):
        self.setStyleSheet(launcher_style_sheet())
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        layout.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        layout.addLayout(body, 1)

        self.sidebar = self._build_sidebar()
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")
        body.addWidget(self.stack, 1)

        self.pages = {
            "welcome": self._welcome_page(),
            "dashboard": self._dashboard_page(),
            "setup": self._setup_page(),
            "settings": self._settings_page(),
            "logs": self._logs_page(),
            "tools": self._tools_page(),
            "update": self._update_page(),
            "about": self._about_page(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self._apply_responsive_layout()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(8)

        logo = QLabel()
        self.sidebar_logo = logo
        logo.setAlignment(Qt.AlignCenter)
        if os.path.exists(ASSETS["logo"]):
            logo.setPixmap(
                QPixmap(ASSETS["logo"]).scaled(
                    88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        brand = QLabel(APP_TITLE)
        self.sidebar_brand = brand
        brand.setObjectName("SidebarBrand")
        brand.setAlignment(Qt.AlignCenter)

        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addSpacing(18)

        self.pc_nav_labels = {
            "dashboard": "DASHBOARD",
            # "setup": "SETUP GUIDE",
            "settings": "SETTINGS",
            "logs": "LOGS",
            "tools": "TOOLS",
            "update": "CHECK UPDATE",
            "about": "ABOUT ME",
        }
        self.narrow_nav_labels = {
            "dashboard": "DASH",
            "setup": "SETUP",
            "settings": "SET",
            "logs": "LOGS",
            "tools": "TOOLS",
            "update": "UPDATE",
            "about": "ABOUT",
        }
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, label in self.pc_nav_labels.items():
            button = AnimatedButton(label, "nav")
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=key: self.show_page(name))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch()
        music = AnimatedButton("MUSIC: OFF", "secondary")
        music.setObjectName("MusicButton")
        layout.addWidget(music)
        build = QLabel("BUILD 1.0.0")
        build.setObjectName("SidebarMeta")
        status = QLabel("STATUS: READY  +")
        status.setObjectName("SidebarReady")
        layout.addWidget(build)
        layout.addWidget(status)
        return sidebar

    def _build_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.auto_start_timer = QTimer(self)
        self.auto_start_timer.setSingleShot(True)
        self.auto_start_timer.timeout.connect(self.start_program)

    def _schedule_auto_start(self):
        if (
            self.settings.get("auto_start_program", False)
            and self._is_auto_start_allowed()
        ):
            self.append_log(
                "[INFO] Auto start enabled. Starting program after launcher initialization.\n"
            )
            self.auto_start_timer.start(1000)
        elif self.settings.get("auto_start_program", False):
            self.append_log(
                "[WARN] Auto start is enabled but server number is not configured.\n"
            )

    def toggle_max_restore(self):
        if self.is_custom_maximized:
            self.restore_custom_window()
        else:
            self.maximize_custom_window()

    def maximize_custom_window(self):
        self.normal_geometry = self.geometry()
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.availableGeometry())
        self.is_custom_maximized = True
        self.title_bar.sync_maximize_icon()

    def restore_custom_window(self):
        if self.normal_geometry:
            self.setGeometry(self.normal_geometry)
        self.is_custom_maximized = False
        self.title_bar.sync_maximize_icon()

    def start_drag_from_custom_maximized(self, global_pos, title_x_ratio):
        if not self.is_custom_maximized:
            return

        restore_geometry = self.normal_geometry or self.geometry()
        restored_width = restore_geometry.width()
        restored_height = restore_geometry.height()
        new_x = global_pos.x() - int(restored_width * title_x_ratio)
        new_y = 8
        self.setGeometry(new_x, new_y, restored_width, restored_height)
        self.is_custom_maximized = False
        self.title_bar.sync_maximize_icon()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()
        QTimer.singleShot(0, self._sync_dashboard_actions_width)

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "title_bar"):
            QTimer.singleShot(0, self.title_bar.sync_maximize_icon)

    def closeEvent(self, event):
        if self.shutdown_started:
            event.accept()
            super().closeEvent(event)
            return
        if self.is_program_running() and not self.confirm(
            "Stop Program And Exit",
            "The automation is still running. Stop it and close the launcher?",
            "STOP AND EXIT",
        ):
            event.ignore()
            return
        self._shutdown_resources()
        event.accept()
        super().closeEvent(event)

    def _shutdown_resources(self):
        if self.shutdown_started:
            return
        self.shutdown_started = True
        if hasattr(self, "timer"):
            self.timer.stop()
        if hasattr(self, "auto_start_timer"):
            self.auto_start_timer.stop()
        self._unregister_start_stop_hotkey()
        self._hide_runner_overlay()
        self.close_external_helpers()
        self.output_reader_stop.set()
        self.stop_log_tail()

        process = self.process
        if process is not None and process.poll() is None:
            terminate_process_tree(process)
        self._close_output_reader(process)
        self.process = None
        self.program_stopping = False
        self.stop_deadline = None
        self.queue_snapshot = {"running": [], "active": [], "waiting": []}
        self.running_task_name = None

    def nativeEvent(self, event_type, message):
        if self._handle_native_hotkey_message(message):
            return True, 0

        if not ENABLE_NATIVE_CUSTOM_CHROME or sys.platform != "win32":
            return super().nativeEvent(event_type, message)

        msg = WindowsMSG.from_address(int(message))
        if msg.message != WM_NCHITTEST:
            return super().nativeEvent(event_type, message)

        global_pos = global_pos_from_lparam(msg.lParam)
        local_pos = self.mapFromGlobal(global_pos)

        if not self.is_custom_maximized:
            hit_test = self._resize_hit_test(local_pos)
            if hit_test is not None:
                return True, hit_test

        if self._is_title_bar_caption(global_pos, local_pos):
            if self.is_custom_maximized:
                return True, HTCLIENT
            return True, HTCAPTION

        return True, HTCLIENT

    def _resize_hit_test(self, local_pos):
        border = WINDOW_RESIZE_BORDER_PX
        on_left = local_pos.x() <= border
        on_right = local_pos.x() >= self.width() - border
        on_top = local_pos.y() <= border
        on_bottom = local_pos.y() >= self.height() - border

        if on_top and on_left:
            return HTTOPLEFT
        if on_top and on_right:
            return HTTOPRIGHT
        if on_bottom and on_left:
            return HTBOTTOMLEFT
        if on_bottom and on_right:
            return HTBOTTOMRIGHT
        if on_left:
            return HTLEFT
        if on_right:
            return HTRIGHT
        if on_top:
            return HTTOP
        if on_bottom:
            return HTBOTTOM
        return None

    def _is_title_bar_caption(self, global_pos, local_pos):
        if not hasattr(self, "title_bar"):
            return False
        if not (0 <= local_pos.y() < self.title_bar.height()):
            return False
        return not any(
            self._global_rect_for_widget(button).contains(global_pos)
            for button in (
                self.title_bar.minimize_button,
                self.title_bar.maximize_button,
                self.title_bar.close_button,
            )
        )

    @staticmethod
    def _global_rect_for_widget(widget):
        top_left = widget.mapToGlobal(QPoint(0, 0))
        return QRect(top_left, widget.size())

    def _apply_responsive_layout(self):
        if not hasattr(self, "is_narrow_layout"):
            return
        is_narrow = self.width() < BREAKPOINT_NARROW_WIDTH
        if is_narrow == self.is_narrow_layout and hasattr(self, "sidebar"):
            return
        self.is_narrow_layout = is_narrow
        labels = self.narrow_nav_labels if is_narrow else self.pc_nav_labels
        self.sidebar.setFixedWidth(96 if is_narrow else 190)
        for key, button in self.nav_buttons.items():
            button.setText(labels[key])
        if hasattr(self, "sidebar_brand"):
            self.sidebar_brand.setVisible(not is_narrow)
        if hasattr(self, "sidebar_logo"):
            size = 54 if is_narrow else 88
            if os.path.exists(ASSETS["logo"]):
                self.sidebar_logo.setPixmap(
                    QPixmap(ASSETS["logo"]).scaled(
                        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )

    def show_page(self, name):
        self.stack.setCurrentWidget(self.pages[name])
        if name in self.nav_buttons:
            self.nav_buttons[name].setChecked(True)
        if name == "dashboard":
            self._update_game_restore_button_visibility()
            self._render_logs()
            self._tick()

    def _panel(self, title=None):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("PanelTitle")
            layout.addWidget(label)
        return panel, layout

    def _page(self, object_name="Page"):
        page = QWidget()
        page.setObjectName(object_name)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        return page, layout

    def _page_title(self, text):
        label = QLabel(f"{APP_TITLE} - {text}")
        label.setObjectName("PageTitle")
        return label

    def _button(self, text, variant="secondary"):
        button_variant = "secondary" if variant == "ghost" else variant
        return AnimatedButton(text, button_variant)

    def toggle_program(self):
        if self.is_program_running():
            self.stop_program()
        else:
            self.start_program()

    def is_program_running(self):
        return self.process is not None and self.process.poll() is None

    def _update_game_restore_button_visibility(self):
        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setVisible(ark_game_setup.restore_state_exists())

    def _update_start_game_button_visibility(self):
        button = getattr(self, "start_game_button", None)
        if button is None:
            return
        game_size = find_window_size(GAME_WINDOW_TITLE)
        button.setVisible(
            game_size is None or game_size not in SUPPORTED_GAME_RESOLUTIONS
        )

    def _unlock_start_game_button(self):
        self._set_start_game_enabled(True)
        self._update_start_game_button_visibility()

    def _set_start_game_enabled(self, enabled: bool) -> None:
        """Update and broadcast the shared START GAME enabled state."""
        button = getattr(self, "start_game_button", None)
        if button is not None:
            button.setEnabled(enabled)
        self.start_game_enabled_changed.emit(enabled)

    def _unlock_restore_game_button(self):
        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setEnabled(True)
        self._update_game_restore_button_visibility()

    def start_game(self):
        self._set_start_game_enabled(False)
        QTimer.singleShot(START_GAME_DISABLE_DELAY, self._unlock_start_game_button)

        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setEnabled(False)
            QTimer.singleShot(
                START_GAME_DISABLE_DELAY, self._unlock_restore_game_button
            )

        try:
            self.append_log("[INFO] Preparing ARK for 1920x1080 launch...\n")
            settings_path = ark_game_setup.prepare_and_launch_game()
            self.append_log(
                f"[SUCCESS] ARK launch requested through Steam. Config: {settings_path}\n"
            )
        except Exception as exc:
            self.append_log(f"[ERROR] Start game failed: {exc}\n")
            self.dialog("Start Game Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

    def restore_game_settings(self):
        if not ark_game_setup.restore_state_exists():
            self._update_game_restore_button_visibility()
            return

        try:
            self.append_log("[INFO] Restoring ARK display and config settings...\n")
            settings_path = ark_game_setup.restore_game_settings()
            self.append_log(
                f"[SUCCESS] Restored ARK display and config: {settings_path}\n"
            )
        except Exception as exc:
            self.append_log(f"[ERROR] Restore game settings failed: {exc}\n")
            self.dialog("Restore Game Settings Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

    def clear_game_restore_settings(self):
        try:
            ark_game_setup.clear_restore_state()
            self.append_log("[INFO] Cleared saved ARK restore settings.\n")
        except Exception as exc:
            self.append_log(f"[ERROR] Clear game restore settings failed: {exc}\n")
            self.dialog("Clear Restore Settings Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

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
        elif self.is_program_running():
            target_text = "STOP PROGRAM"
            target_variant = "danger"
        else:
            target_text = "START PROGRAM"
            target_variant = "primary"

        if self.start_stop_button.text() != target_text:
            self.start_stop_button.setText(target_text)
        if self.start_stop_button.variant != target_variant:
            self.start_stop_button.set_variant(target_variant)
        target_enabled = not self.program_stopping
        if self.start_stop_button.isEnabled() != target_enabled:
            self.start_stop_button.setEnabled(target_enabled)

    def _is_auto_start_allowed(self):
        cond = str(self.settings.get("server_number", "0")).strip() not in ("", "0")
        return cond

    def _update_auto_start_switch(self):
        if not hasattr(self, "auto_start_switch"):
            return

        allowed = self._is_auto_start_allowed()
        saved_value = bool(self.settings.get("auto_start_program", False))

        self.auto_start_switch.blockSignals(True)
        self.auto_start_switch.setEnabled(allowed)
        self.auto_start_switch.setChecked(saved_value if allowed else False)
        self.auto_start_switch.blockSignals(False)

        self.auto_start_hint.setText(
            "Start program when launcher opens"
            if allowed
            else "Set server number first"
        )

    def toggle_auto_start_program(self, checked):
        if not self._is_auto_start_allowed():
            self._update_auto_start_switch()
            return

        self.settings["auto_start_program"] = bool(checked)
        self.form_values["auto_start_program"] = bool(checked)
        field = self.fields.get("auto_start_program")
        if field is not None:
            field.blockSignals(True)
            field.setChecked(bool(checked))
            field.blockSignals(False)

        save_settings(self._collect_settings())
        state = "enabled" if checked else "disabled"
        self.append_log(f"[INFO] Auto start {state}.\n")

    def persist_single_setting(self, key, show_log=True, show_error=True):
        field = self.fields.get(key)
        if field is None:
            return False
        try:
            self.form_values[key] = self._field_value(key, field)
        except ValueError as exc:
            if show_error:
                self.append_log(f"[ERROR] Invalid setting {key}: {exc}\n")
                self.dialog("Invalid Settings", str(exc), "error")
            return False
        return self.persist_settings_from_visible_fields(show_log, show_error)

    def persist_settings_from_visible_fields(self, show_log=True, show_error=True):
        try:
            self._capture_visible_fields()
            new_data = self._collect_settings()
        except ValueError as exc:
            if show_error:
                self.append_log(f"[ERROR] Invalid settings: {exc}\n")
                self.dialog("Invalid Settings", str(exc), "error")
            return False

        save_settings(new_data)
        self.settings = new_data
        self.form_values = new_data.copy()
        self._update_auto_start_switch()
        if show_log:
            self.append_log("[SUCCESS] Settings saved automatically.\n")
        return True

    def _collect_settings(self):
        data = {}
        for key, default_value in DEFAULT_SETTINGS.items():
            value = self.form_values.get(key, default_value)
            if isinstance(default_value, bool):
                data[key] = bool(value)
            elif isinstance(default_value, int):
                data[key] = int(value)
            elif isinstance(default_value, float):
                data[key] = float(value)
            else:
                data[key] = str(value)
        data["helper_inactive_opacity"] = max(
            0.1, min(1.0, data["helper_inactive_opacity"])
        )
        return data

    def _capture_visible_fields(self):
        for key, field in self.fields.items():
            self.form_values[key] = self._field_value(key, field)

    def _field_value(self, key, field):
        default_value = DEFAULT_SETTINGS[key]
        if isinstance(default_value, bool):
            return field.isChecked()

        raw_value = field.text()
        if isinstance(default_value, int):
            return int(raw_value)
        if isinstance(default_value, float):
            return float(raw_value)
        return raw_value

    def confirm_reset(self):
        if getattr(self, "current_settings_group", "") == "STORAGE":
            if not self.confirm(
                "Reset Deposit Routes",
                "Reset deposit routes to a single empty crystal route and grindable route?",
                "RESET",
            ):
                return
            self.reset_deposit_routes()
            return
        if getattr(self, "current_settings_group", "") == "GACHA":
            if not self.confirm(
                "Reset Gacha Config",
                "Reset gacha config to one default left/right pair?",
                "RESET",
            ):
                return
            self.reset_gacha_config()
            return
        if getattr(self, "current_settings_group", "") == "PEGO":
            if not self.confirm(
                "Reset Pego Config",
                "Reset pego config to one default pego?",
                "RESET",
            ):
                return
            self.reset_pego_config()
            return

        if not self.confirm(
            "Reset Visible Settings",
            "Reset all visible setting values to defaults and save immediately?",
            "RESET",
        ):
            return
        self.reset_visible_settings()

    def reset_visible_settings(self):
        for key, field in self.fields.items():
            value = DEFAULT_SETTINGS[key]
            field.blockSignals(True)
            if isinstance(value, bool):
                field.setChecked(value)
            else:
                field.setText(str(value))
            field.blockSignals(False)
            self.form_values[key] = value
        self.persist_settings_from_visible_fields(show_log=False)
        self.append_log("[INFO] Visible settings reset to defaults and saved.\n")
        self.dialog(
            "Settings Reset",
            "Visible settings were reset and saved.",
            "info",
        )

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
            self.close_external_helpers()
            cleanup_debug_screenshots_on_program_start()
            self.process = subprocess.Popen(
                [sys.executable, "-u", "main_program.py"],
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
            self._show_runner_overlay()
        except Exception as exc:
            self.dialog("Start Failed", str(exc), "error")

    def stop_program(self):
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
        if self.program_stopping and time.time() >= self.stop_deadline:
            self.append_log("[WARN] Program did not stop in 5 seconds; killing it.\n")
            self.process.kill()

    def _finalize_program_stop(self):
        was_stopping = self.program_stopping
        self.stop_log_tail()
        self._close_output_reader(self.process)
        self.process = None
        self.program_stopping = False
        self.stop_deadline = None
        if was_stopping:
            self.append_log("[WARN] Program stopped.\n")
        self._update_start_stop_button()
        self._hide_runner_overlay()

    def _show_runner_overlay(self) -> None:
        if not self.is_program_running() or self.program_stopping:
            self._hide_runner_overlay()
            return
        overlay = getattr(self, "runner_overlay", None)
        try:
            if overlay is None:
                overlay = RunnerOverlay(self)
                self.runner_overlay = overlay
            overlay.refresh(self.queue_snapshot, self.log_lines)
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
        if self.is_program_running() and not self.program_stopping:
            self._show_runner_overlay()
        else:
            self._hide_runner_overlay()

    def read_output(self, process):
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if self.output_reader_stop.is_set():
                break
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

    def load_previous_logs(self):
        if not os.path.exists(GACHA_LOG_FILE):
            return
        try:
            with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=MAX_LAUNCHER_LOG_LINES)
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to load previous log file: {exc}\n")
            return
        self.log_lines = [self._normalize_file_log_line(line) for line in lines]
        self._render_logs()

    def start_log_tail(self):
        self.stop_log_tail()
        self.log_tail_stop = threading.Event()
        self.log_file_position = self._log_file_size()
        self.log_tail_thread = threading.Thread(target=self.tail_log_file, daemon=True)
        self.log_tail_thread.start()

    def stop_log_tail(self):
        if self.log_tail_thread and self.log_tail_thread.is_alive():
            self.log_tail_stop.set()
            self.log_tail_thread.join(timeout=1)
        self.log_tail_thread = None

    def tail_log_file(self):
        missing_logged = False
        while not self.log_tail_stop.is_set():
            try:
                if not os.path.exists(GACHA_LOG_FILE):
                    if not missing_logged:
                        self._emit_log_line(
                            f"[WARN] Log file not found yet: {GACHA_LOG_FILE}\n"
                        )
                        missing_logged = True
                    self.log_tail_stop.wait(1)
                    continue

                missing_logged = False
                file_size = os.path.getsize(GACHA_LOG_FILE)
                if file_size < self.log_file_position:
                    self.log_file_position = 0

                with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.log_file_position)
                    lines = f.readlines()
                    self.log_file_position = f.tell()

                for line in lines:
                    self._emit_log_line(self._normalize_file_log_line(line))
            except Exception as exc:
                self._emit_log_line(f"[ERROR] Unable to read live log file: {exc}\n")
                self.log_tail_stop.wait(2)
                continue
            self.log_tail_stop.wait(1)

    @staticmethod
    def _log_file_size():
        try:
            return os.path.getsize(GACHA_LOG_FILE)
        except OSError:
            return 0

    @staticmethod
    def _normalize_file_log_line(line):
        level_map = {
            " - DEBUG - ": "DEBUG",
            " - INFO - ": "INFO",
            " - WARNING - ": "WARN",
            " - ERROR - ": "ERROR",
            " - CRITICAL - ": "CRITICAL",
            " - TEMPLATE - ": "TEMPLATE",
        }
        if line.startswith("["):
            return line
        for marker, level in level_map.items():
            if marker in line:
                return f"[{level}] {line}"
        return line

    def append_log(self, text):
        if text.startswith("[QUEUE_STATE] "):
            try:
                snapshot = json.loads(text[len("[QUEUE_STATE] ") :])
            except json.JSONDecodeError:
                return
            self._update_queue_snapshot(snapshot)
            self._render_logs()
            return
        if "Added task" in text and "[QUEUE]" not in text:
            text = f"[QUEUE] {text}"
        elif "CRITICAL" in text.upper() and "[CRITICAL]" not in text:
            text = f"[CRITICAL] {text}"
        elif "ERROR" in text.upper() and "[ERROR]" not in text:
            text = f"[ERROR] {text}"
        elif "WARNING" in text.upper() and "[WARN]" not in text:
            text = f"[WARN] {text}"
        elif "DEBUG" in text.upper() and "[DEBUG]" not in text:
            text = f"[DEBUG] {text}"
        elif "TEMPLATE" in text.upper() and "[TEMPLATE]" not in text:
            text = f"[TEMPLATE] {text}"

        self.log_lines.append(text)
        if len(self.log_lines) > MAX_LAUNCHER_LOG_LINES:
            self.log_lines = self.log_lines[-MAX_LAUNCHER_LOG_LINES:]
        self.last_activity = time.strftime("%H:%M:%S")
        if "[QUEUE]" in text:
            self.waiting_count += 1
        if "[SUCCESS]" in text:
            self.active_count = max(self.active_count, 1)
        self._render_logs()

    def _render_logs(self):
        lines = self._filtered_logs()
        full = self._format_log_lines(lines)
        preview = self._format_log_lines(lines[-18:])
        if hasattr(self, "full_log"):
            self._set_console_html(self.full_log, full)
        if hasattr(self, "dashboard_log"):
            self._set_console_html(self.dashboard_log, preview)

    def _set_console_html(self, console, html):
        console.setHtml(html)
        console.moveCursor(console.textCursor().MoveOperation.End)
        QTimer.singleShot(
            0, lambda widget=console: self._scroll_console_to_bottom(widget)
        )

    @staticmethod
    def _scroll_console_to_bottom(console):
        scrollbar = console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _format_log_lines(self, lines):
        html = []
        for line in lines:
            color = COLORS["text"]
            if "[CRITICAL]" in line or "[ERROR]" in line:
                color = COLORS["red"]
            elif "[WARN]" in line:
                color = COLORS["yellow"]
            elif "[SUCCESS]" in line:
                color = COLORS["green"]
            elif "[INFO]" in line:
                color = COLORS["cyan"]
            elif "[DEBUG]" in line:
                color = COLORS["text"]
            elif "[TEMPLATE]" in line:
                color = COLORS["dim"]
            elif "[QUEUE]" in line:
                color = COLORS["muted"]
            html.append(
                f'<span style="color:{color}; white-space:pre;">{self._escape(line)}</span>'
            )
        return "<br>".join(html)

    @staticmethod
    def _escape(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _filtered_logs(self):
        if self.current_filter == "QUEUE":
            return self._format_queue_snapshot()
        if self.current_filter == "RUNNING":
            return self._format_running_snapshot()
        if self.current_filter == "ALL":
            return self.log_lines
        return [
            line
            for line in self.log_lines
            if f"[{self.current_filter}]" in line or self.current_filter in line.upper()
        ]

    def _format_queue_snapshot(self):
        now = time.time()
        lines = []
        queued = self.queue_snapshot.get("active", []) + self.queue_snapshot.get(
            "waiting", []
        )
        queued.sort(
            key=lambda task: float(task.get("execution_time", now)), reverse=True
        )
        for task in queued:
            remaining = max(0, int(float(task.get("execution_time", now)) - now))
            if task.get("state") == "READY" or remaining == 0:
                timer = "READY"
            else:
                hours, remainder = divmod(remaining, 3600)
                minutes, seconds = divmod(remainder, 60)
                timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            lines.append(f"[QUEUE] {timer:<9} {task.get('name', 'unknown')}")
        for task in self.queue_snapshot.get("running", []):
            lines.append(f"[QUEUE] RUNNING   {task.get('name', 'unknown')}")
        return lines or ["[QUEUE] No upcoming tasks."]

    def _update_queue_snapshot(self, snapshot):
        self.queue_snapshot = snapshot
        running = snapshot.get("running", [])
        running_task_name = running[0].get("name", "unknown") if running else None
        if running_task_name and running_task_name != self.running_task_name:
            self.running_history.append(f"[RUNNING] STARTED   {running_task_name}")
        self.running_task_name = running_task_name
        self._sync_runner_overlay()

    def _format_running_snapshot(self):
        lines = self.running_history.copy()
        running = self.queue_snapshot.get("running", [])
        if running:
            lines.append(f"[RUNNING] CURRENT   {running[0].get('name', 'unknown')}")
        else:
            lines.append("[RUNNING] IDLE")
        return lines

    def set_log_filter(self, value):
        self.current_filter = value
        self._render_logs()

    def clear_logs(self):
        self.log_lines.clear()
        self.running_history.clear()
        self.queue_snapshot = {"running": [], "active": [], "waiting": []}
        self.running_task_name = None
        self.active_count = 0
        self.waiting_count = 0
        self.log_file_position = 0
        self._render_logs()
        try:
            with open(GACHA_LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to clear log file: {exc}\n")

    def open_logs(self) -> None:
        """Open the launcher log file with the operating system's default app."""
        log_url = QUrl.fromLocalFile(os.path.abspath(GACHA_LOG_FILE))
        if not QDesktopServices.openUrl(log_url):
            self.dialog(
                "Open Logs Failed",
                f"Unable to open the log file:\n{GACHA_LOG_FILE}",
                "error",
            )

    def check_colours(self):
        if not self.require_ark_window("check console colours"):
            return

        try:
            from source.utility.colour_checks import console_output
        except ImportError:
            self.dialog(
                "Missing Dependency",
                "Console colour check dependencies are not installed.",
                "error",
            )
            return

        colour = console_output.output_mean_colour()
        self.append_log(
            f"[INFO] Average console colour: {colour}. Set console.json lower_bound to average - 5 and upper_bound to average + 5.\n"
        )

    def require_ark_window(self, action, dialog_parent=None):
        try:
            validate_ark_window()
        except RuntimeError as exc:
            self.last_ark_window_error = str(exc)
            self.append_log(f"[ERROR] Cannot {action}: {self.last_ark_window_error}\n")
            self.dialog(
                f"{GAME_WINDOW_TITLE} Required",
                self.last_ark_window_error,
                "error",
                parent=dialog_parent,
            )
            return False
        self.last_ark_window_error = ""
        return True

    def dialog(self, title, message, variant="info", parent=None):
        dialog_parent = self if parent is None else parent
        active_dialog = getattr(dialog_parent, "_active_cyber_dialog", None)
        if active_dialog is not None:
            try:
                if active_dialog.isVisible():
                    active_dialog.show()
                    active_dialog.raise_()
                    active_dialog.activateWindow()
                    return active_dialog.result()
            except RuntimeError:
                pass

        if dialog_parent is not self:
            dialog_parent.show()
            dialog_parent.raise_()
            dialog_parent.activateWindow()

        dialog = CyberDialog(dialog_parent, title, message, variant)
        dialog_parent._active_cyber_dialog = dialog
        try:
            return dialog.exec()
        finally:
            if getattr(dialog_parent, "_active_cyber_dialog", None) is dialog:
                dialog_parent._active_cyber_dialog = None

    def toast(self, message, variant="info"):
        if variant != "success":
            self.dialog(APP_NAME, message, variant)
            return
        dialog = CyberDialog(self, APP_NAME, message, variant)
        dialog.setModal(False)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        if not hasattr(self, "_toast_dialogs"):
            self._toast_dialogs = []
        self._toast_dialogs.append(dialog)
        dialog.finished.connect(
            lambda _result, item=dialog: (
                self._toast_dialogs.remove(item)
                if item in self._toast_dialogs
                else None
            )
        )
        QTimer.singleShot(3000, dialog.accept)
        dialog.show()

    def confirm(self, title, message, confirm_text="OK"):
        return (
            CyberDialog(
                self,
                title,
                message,
                "confirm",
                confirm_text=confirm_text,
                cancel_text="CANCEL",
            ).exec()
            == QDialog.Accepted
        )

    def _tick(self):
        if self.shutdown_started:
            return
        self._poll_program_stop()
        self._sync_runner_overlay()
        if self.current_filter in {"QUEUE", "RUNNING"}:
            self._render_logs()
        if hasattr(self, "server_value"):
            self._update_start_stop_button()
            self._update_start_game_button_visibility()
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
