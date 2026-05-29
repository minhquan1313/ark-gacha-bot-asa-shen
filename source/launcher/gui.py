import os
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
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

from source.launcher.constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    BREAKPOINT_NARROW_WIDTH,
    COLORS,
    DEFAULT_SETTINGS,
    ENABLE_NATIVE_CUSTOM_CHROME,
    GACHA_LOG_FILE,
    GAME_WINDOW_TITLE,
    PHONE_MINIMUM_SIZE,
    SUPPORTED_GAME_RESOLUTIONS,
    WINDOW_RESIZE_BORDER_PX,
)
from source.launcher.native_window import (
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
    WM_NCHITTEST,
    WindowsMSG,
    global_pos_from_lparam,
)
from source.launcher.pages import LauncherPagesMixin
from source.launcher.settings_store import load_settings, save_settings
from source.launcher.styles import launcher_style_sheet
from source.launcher.system import (
    calculate_cpu_percent,
    find_window_size,
    get_cpu_times,
    get_memory_usage_gb,
)
from source.launcher.widgets import (
    AnimatedButton,
    CyberDialog,
    LogBridge,
    TitleBar,
)


class SettingsGUI(LauncherPagesMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Launcher")
        if os.path.exists(ASSETS["logo"]):
            self.setWindowIcon(QIcon(ASSETS["logo"]))
            QApplication.setWindowIcon(QIcon(ASSETS["logo"]))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(1400, 800)
        self.setMinimumSize(*PHONE_MINIMUM_SIZE)

        self.process = None
        self.log_lines = []
        self.current_filter = "ALL"
        self.settings = load_settings()
        self.form_values = self.settings.copy()
        self.fields = {}
        self.nav_buttons = {}
        self.log_bridge = LogBridge()
        self.log_bridge.line.connect(self.append_log)
        self.log_tail_stop = threading.Event()
        self.log_tail_thread = None
        self.log_file_position = 0
        self.active_count = 0
        self.waiting_count = 0
        self.start_time = None
        self.last_activity = "--:--:--"
        self._cpu_times = get_cpu_times()
        self.is_narrow_layout = False
        self.is_custom_maximized = False
        self.normal_geometry = None

        self._build_ui()
        self._build_timer()
        self.show_page("dashboard")
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
            "setup": "SETUP GUIDE",
            "settings": "SETTINGS",
            "logs": "LOGS",
            "update": "CHECK UPDATE",
            "about": "ABOUT ME",
        }
        self.narrow_nav_labels = {
            "dashboard": "DASH",
            "setup": "SETUP",
            "settings": "SET",
            "logs": "LOGS",
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

    def _schedule_auto_start(self):
        if (
            self.settings.get("auto_start_program", False)
            and self._is_auto_start_allowed()
        ):
            self.append_log(
                "[INFO] Auto start enabled. Starting program after launcher initialization.\n"
            )
            QTimer.singleShot(1000, self.start_program)
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

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "title_bar"):
            QTimer.singleShot(0, self.title_bar.sync_maximize_icon)

    def nativeEvent(self, event_type, message):
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

    def _update_start_stop_button(self):
        if not hasattr(self, "start_stop_button"):
            return
        if self.is_program_running():
            target_text = "STOP PROGRAM"
            target_variant = "danger"
        else:
            target_text = "START PROGRAM"
            target_variant = "primary"

        if self.start_stop_button.text() != target_text:
            self.start_stop_button.setText(target_text)
        self.start_stop_button.set_variant(target_variant)

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
        if self.process and self.process.poll() is None:
            self.dialog("Program Running", "The program is already running.", "info")
            return

        game_size = find_window_size(GAME_WINDOW_TITLE)
        if game_size not in SUPPORTED_GAME_RESOLUTIONS:
            if game_size:
                size_message = (
                    f"Detected ArkAscended size: {game_size[0]}x{game_size[1]}."
                )
                self.append_log(
                    f"[ERROR] Unsupported ArkAscended resolution: {game_size[0]}x{game_size[1]}.\n"
                )
            else:
                size_message = "ArkAscended window was not found."
                self.append_log("[ERROR] ArkAscended window was not found.\n")
            self.dialog(
                "Unsupported Screen Resolution",
                f"{size_message}\n\n{APP_NAME} supports ArkAscended at 1920x1080.",
                "error",
            )
            return

        try:
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
            threading.Thread(target=self.read_output, daemon=True).start()
        except Exception as exc:
            self.dialog("Start Failed", str(exc), "error")

    def stop_program(self):
        if self.process and self.process.poll() is None:
            self.stop_log_tail()
            self.process.terminate()
            self.process = None
            self.append_log("[WARN] Program terminated by launcher.\n")
            self._update_start_stop_button()
            self.dialog("Program Stopped", "Program terminated.", "warning")
        else:
            self.dialog(
                "No Program Running", "There is no running program to stop.", "info"
            )

    def read_output(self):
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            self.log_bridge.line.emit(line)
        self.stop_log_tail()
        self.log_bridge.line.emit("[WARN] Program output stream closed.\n")

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
                        self.log_bridge.line.emit(
                            f"[WARN] Log file not found yet: {GACHA_LOG_FILE}\n"
                        )
                        missing_logged = True
                    time.sleep(1)
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
                    self.log_bridge.line.emit(self._normalize_file_log_line(line))
            except Exception as exc:
                self.log_bridge.line.emit(f"[ERROR] Unable to read live log file: {exc}\n")
                time.sleep(2)
                continue
            time.sleep(1)

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
        if self.current_filter == "ALL":
            return self.log_lines
        return [
            line
            for line in self.log_lines
            if f"[{self.current_filter}]" in line or self.current_filter in line.upper()
        ]

    def set_log_filter(self, value):
        self.current_filter = value
        self._render_logs()

    def clear_logs(self):
        self.log_lines.clear()
        self.active_count = 0
        self.waiting_count = 0
        self._render_logs()

    def copy_logs(self):
        QApplication.clipboard().setText("".join(self._filtered_logs()))
        self.toast("Logs copied to clipboard.", "success")

    def check_colours(self):
        game_size = find_window_size(GAME_WINDOW_TITLE)
        if game_size not in SUPPORTED_GAME_RESOLUTIONS:
            if game_size:
                size_message = (
                    f"Detected ArkAscended size: {game_size[0]}x{game_size[1]}."
                )
                self.append_log(
                    f"[ERROR] Unsupported ArkAscended resolution for colour check: {game_size[0]}x{game_size[1]}.\n"
                )
            else:
                size_message = "ArkAscended window was not found."
                self.append_log(
                    "[ERROR] ArkAscended window was not found for colour check.\n"
                )
            self.dialog(
                "Unsupported Screen Resolution",
                f"{size_message}\n\nConsole colour checking supports ArkAscended at 1920x1080.",
                "error",
            )
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

    def dialog(self, title, message, variant="info"):
        CyberDialog(self, title, message, variant).exec()

    def toast(self, message, variant="info"):
        self.dialog(APP_NAME, message, variant)

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
        if hasattr(self, "server_value"):
            self._update_start_stop_button()
            server_number = self.form_values.get(
                "server_number", self.settings.get("server_number", "0")
            )
            field = self.fields.get("server_number")
            if field is not None:
                server_number = field.text()
            self.server_value.setText(str(server_number))
            self.active_value.setText(str(self.active_count))
            self.waiting_value.setText(str(self.waiting_count))
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
