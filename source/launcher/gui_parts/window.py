import os
import sys

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.widgets import (
    AnimatedButton,
    TitleBar,
    sync_rounded_window_mask,
)
from source.launcher.config.constants import (
    APP_TITLE,
    ASSETS,
    BREAKPOINT_NARROW_WIDTH,
    ENABLE_NATIVE_CUSTOM_CHROME,
    UI_METRICS,
    WINDOW_RESIZE_BORDER_PX,
)
from source.launcher.styles import launcher_style_sheet
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
    WM_NCHITTEST,
    WindowsMSG,
    global_pos_from_lparam,
)
from source.launcher.utils.process_control import terminate_process_tree

START_GAME_DISABLE_DELAY = 10000
RUNNER_READY_MESSAGE = "__RUNNER_READY__"


class WindowGuiMixin:
    def _build_ui(self):
        self.setStyleSheet(launcher_style_sheet())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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
        sync_status = getattr(self, "_sync_ark_status_labels", None)
        if callable(sync_status):
            sync_status()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(8)

        logo = QLabel()
        self.sidebar_logo = logo
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(ASSETS["logo"]):
            logo.setPixmap(
                QPixmap(ASSETS["logo"]).scaled(
                    88,
                    88,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand = QLabel(APP_TITLE)
        self.sidebar_brand = brand
        brand.setObjectName("SidebarBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        build = QLabel("BUILD 1.0.0")
        build.setObjectName("SidebarMeta")
        status = QLabel("STATUS: READY  +")
        status.setObjectName("SidebarReady")
        self.sidebar_ready = status
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
        self._sync_rounded_mask()

    def restore_custom_window(self):
        if self.normal_geometry:
            self.setGeometry(self.normal_geometry)
        self.is_custom_maximized = False
        self.title_bar.sync_maximize_icon()
        self._sync_rounded_mask()

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
        self._sync_rounded_mask()
        QTimer.singleShot(0, self._sync_dashboard_actions_width)

    def _sync_rounded_mask(self):
        sync_rounded_window_mask(
            self,
            UI_METRICS["window_radius"],
            enabled=not getattr(self, "is_custom_maximized", False),
        )

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
        self.runner_loading = False
        self.runner_launch_pending = False
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
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
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
