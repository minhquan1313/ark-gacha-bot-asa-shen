import os
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

from PySide6.QtCore import QEasingCurve, QObject, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from source.launcher.constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    BREAKPOINT_NARROW_WIDTH,
    BUTTON_STYLES,
    BUTTON_TRANSITION_MS,
    COLORS,
    DEFAULT_SETTINGS,
    FONT_SIZES,
    GAME_WINDOW_TITLE,
    PHONE_MINIMUM_SIZE,
    SETTINGS_GROUPS,
    SUPPORTED_GAME_RESOLUTIONS,
)
from source.launcher.settings_store import load_settings, save_settings
from source.launcher.system import (
    calculate_cpu_percent,
    find_window_size,
    get_cpu_times,
    get_memory_usage_gb,
)


class LogBridge(QObject):
    line = Signal(str)


class ClickableTextEdit(QTextEdit):
    copied = Signal()

    def mouseDoubleClickEvent(self, event):
        self.selectAll()
        self.copy()
        self.copied.emit()
        super().mouseDoubleClickEvent(event)


class AnimatedButton(QPushButton):
    def __init__(self, text="", variant="secondary", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._state = "normal"
        self._animation = None
        self._colors = BUTTON_STYLES[variant]["normal"].copy()
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", FONT_SIZES["button"], QFont.Bold))
        self._apply_style()
        self.toggled.connect(self._handle_toggled)

    def set_state(self, state):
        if not self.isEnabled():
            state = "disabled"
        self._state = state
        self._animate_to(BUTTON_STYLES[self.variant][state])

    def setObjectName(self, name):
        super().setObjectName(name)
        self._apply_style()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.set_state("normal" if enabled else "disabled")

    def enterEvent(self, event):
        if self.isEnabled() and not self.isChecked():
            self.set_state("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isEnabled() and not self.isChecked():
            self.set_state("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.set_state("active")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if not self.isEnabled():
            return
        if self.isChecked():
            self.set_state("active")
        elif self.underMouse():
            self.set_state("hover")
        else:
            self.set_state("normal")

    def _handle_toggled(self, checked):
        if self.isEnabled():
            self.set_state("active" if checked else "normal")

    def _animate_to(self, target):
        start = self._colors.copy()
        if self._animation:
            self._animation.stop()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(BUTTON_TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)

        def update(value):
            self._colors = {
                key: self._mix_color(start[key], target[key], value)
                for key in ("bg", "fg", "border")
            }
            self._apply_style()

        self._animation.valueChanged.connect(update)
        self._animation.start()

    def _apply_style(self):
        selector = (
            f"QPushButton#{self.objectName()}" if self.objectName() else "QPushButton"
        )
        self.setStyleSheet(f"""
            {selector} {{
                min-height: 34px;
                padding: 5px 16px;
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: 1px solid {self._colors["border"]};
                font-weight: 900;
            }}
            {selector}:disabled {{
                background: {BUTTON_STYLES[self.variant]["disabled"]["bg"]};
                color: {BUTTON_STYLES[self.variant]["disabled"]["fg"]};
                border: 1px solid {BUTTON_STYLES[self.variant]["disabled"]["border"]};
            }}
            {selector}:hover, {selector}:checked {{
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: 1px solid {self._colors["border"]};
            }}
            """)

    @staticmethod
    def _mix_color(start, end, ratio):
        start_color = QColor(start)
        end_color = QColor(end)
        red = round(start_color.red() + (end_color.red() - start_color.red()) * ratio)
        green = round(
            start_color.green() + (end_color.green() - start_color.green()) * ratio
        )
        blue = round(
            start_color.blue() + (end_color.blue() - start_color.blue()) * ratio
        )
        return QColor(red, green, blue).name()


class ChromeIconButton(AnimatedButton):
    def __init__(self, icon_name, parent=None):
        variant = "close" if icon_name == "close" else "chrome"
        super().__init__("", variant, parent)
        self.icon_name = icon_name
        self.setFixedSize(34, 28)
        self.setObjectName("ChromeIconButton")
        self.set_state("normal")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(self._colors["fg"]), 2)
        painter.setPen(pen)
        center_y = self.height() // 2
        if self.icon_name == "minimize":
            painter.drawLine(10, center_y + 5, self.width() - 10, center_y + 5)
        elif self.icon_name == "maximize":
            painter.drawRect(10, 8, self.width() - 20, self.height() - 16)
        elif self.icon_name == "restore":
            painter.drawRect(8, 11, self.width() - 20, self.height() - 16)
            painter.drawRect(12, 7, self.width() - 20, self.height() - 16)
        elif self.icon_name == "close":
            painter.drawLine(10, 8, self.width() - 10, self.height() - 8)
            painter.drawLine(self.width() - 10, 8, 10, self.height() - 8)

    def set_icon(self, icon_name):
        self.icon_name = icon_name
        self.update()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_position = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(10)

        title = QLabel(APP_TITLE)
        title.setObjectName("ChromeTitle")
        version = QLabel(APP_VERSION)
        version.setObjectName("ChromeVersion")
        status = QLabel("SYSTEM READY")
        status.setObjectName("ChromeStatus")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(status)

        self.minimize_button = ChromeIconButton("minimize")
        self.maximize_button = ChromeIconButton("maximize")
        self.close_button = ChromeIconButton("close")
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(window.toggle_max_restore)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.window.isMaximized():
                ratio = event.position().x() / max(1, self.width())
                self.window.showNormal()
                restored_width = self.window.width()
                self.window.move(
                    event.globalPosition().toPoint().x() - int(restored_width * ratio),
                    8,
                )
            self.drag_position = (
                event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.toggle_max_restore()
            event.accept()

    def sync_maximize_icon(self):
        self.maximize_button.set_icon(
            "restore" if self.window.isMaximized() else "maximize"
        )


class CyberDialog(QDialog):
    def __init__(
        self,
        parent,
        title,
        message,
        variant="info",
        confirm_text="OK",
        cancel_text=None,
    ):
        super().__init__(parent)
        self.setObjectName("CyberDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        accent = {
            "success": COLORS["green"],
            "warning": COLORS["yellow"],
            "error": COLORS["red"],
            "confirm": COLORS["cyan"],
            "info": COLORS["cyan"],
        }.get(variant, COLORS["cyan"])

        shell = QFrame()
        shell.setObjectName("DialogShell")
        shell.setStyleSheet(f"""
            QFrame#DialogShell {{
                background: #050B12;
                border: 1px solid {accent};
            }}
            QLabel#DialogTitle {{ color: {accent}; font-size: {FONT_SIZES["dialog_title"]}px; font-weight: 800; }}
            QLabel#DialogMessage {{ color: {COLORS["text"]}; font-size: {FONT_SIZES["dialog_message"]}px; }}
            """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        heading = QLabel(title.upper())
        heading.setObjectName("DialogTitle")
        body = QLabel(message)
        body.setObjectName("DialogMessage")
        body.setWordWrap(True)

        actions = QHBoxLayout()
        actions.addStretch()
        if cancel_text:
            cancel = AnimatedButton(cancel_text, "secondary")
            cancel.clicked.connect(self.reject)
            actions.addWidget(cancel)
        confirm = AnimatedButton(confirm_text, "primary")
        confirm.clicked.connect(self.accept)
        actions.addWidget(confirm)

        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addLayout(actions)
        self.setFixedWidth(430)


class HeroBanner(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logo = (
            QPixmap(ASSETS["logo"]) if os.path.exists(ASSETS["logo"]) else QPixmap()
        )
        self.art = (
            QPixmap(ASSETS["dashboard"])
            if os.path.exists(ASSETS["dashboard"])
            else QPixmap()
        )
        self.setObjectName("HeroBanner")
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#03070C"))

        if not self.art.isNull():
            art = self.art.scaled(
                rect.width(),
                rect.height() + 180,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            painter.setOpacity(0.62)
            painter.drawPixmap(rect.width() - art.width(), -80, art)
            painter.setOpacity(1)

        painter.fillRect(rect, QBrush(QColor(3, 7, 12, 110)))
        painter.setPen(QColor("#0E3D54"))
        for x in range(-80, rect.width() + 80, 42):
            painter.drawLine(x, 0, x + 80, rect.height())

        painter.setPen(QColor(COLORS["cyan"]))
        painter.drawLine(0, rect.height() - 2, rect.width(), rect.height() - 2)

        if not self.logo.isNull() and rect.width() > 760:
            logo = self.logo.scaled(
                118, 118, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            painter.drawPixmap(rect.width() - 150, 16, logo)

        painter.setPen(QColor(COLORS["cyan"]))
        painter.setFont(QFont("Segoe UI", FONT_SIZES["section_heading"], QFont.Bold))
        painter.drawText(28, 42, "WELCOME BACK,")
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", FONT_SIZES["welcome_title"], QFont.Bold))
        painter.drawText(28, 88, f"{APP_TITLE}.")
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Consolas", FONT_SIZES["chrome_status"]))
        painter.drawText(28, 128, "SYSTEM STATUS")
        painter.setPen(QColor(COLORS["green"]))
        painter.setFont(QFont("Consolas", FONT_SIZES["form"], QFont.Bold))
        painter.drawText(165, 128, "ONLINE")


class SettingsGUI(QMainWindow):
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
        self.active_count = 0
        self.waiting_count = 0
        self.start_time = None
        self.last_activity = "--:--:--"
        self._cpu_times = get_cpu_times()
        self.is_narrow_layout = False

        self._build_ui()
        self._build_timer()
        self.show_page("dashboard")

    def _build_ui(self):
        self.setStyleSheet(self._style_sheet())
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

        self.size_grip = QSizeGrip(root)
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.raise_()
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

    def toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.title_bar.sync_maximize_icon()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "size_grip"):
            self.size_grip.move(
                self.width() - self.size_grip.width(),
                self.height() - self.size_grip.height(),
            )
        self._apply_responsive_layout()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "title_bar"):
            self.title_bar.sync_maximize_icon()

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

    def _welcome_page(self):
        page, layout = self._page("WelcomePage")
        row = QHBoxLayout()
        row.setSpacing(22)
        layout.addLayout(row, 1)

        left = QVBoxLayout()
        left.setSpacing(16)
        row.addLayout(left, 1)
        title = QLabel(f"WELCOME TO\n{APP_TITLE}")
        title.setObjectName("WelcomeTitle")
        copy = QLabel(
            "AUTOMATE. MANAGE. DOMINATE.\n\n"
            f"{APP_NAME} is your compact companion for managing automation tasks, "
            "queues, and Discord integrations with style."
        )
        copy.setObjectName("MutedCopy")
        copy.setWordWrap(True)
        checklist, checklist_layout = self._panel("BEFORE YOU START:")
        for item in [
            "Configure your settings",
            "Set up your Discord channels",
            "Review the setup guide",
            "Save settings before starting",
        ]:
            checklist_layout.addWidget(QLabel(f"- {item}"))
        checkbox = QCheckBox("Do not show again")
        start = self._button("GET STARTED  >", "primary")
        start.clicked.connect(lambda: self.show_page("dashboard"))
        left.addStretch()
        left.addWidget(title)
        left.addWidget(copy)
        left.addWidget(checklist)
        left.addWidget(checkbox)
        left.addWidget(start, alignment=Qt.AlignRight)
        left.addStretch()

        art = QLabel()
        art.setObjectName("HeroArt")
        art.setAlignment(Qt.AlignCenter)
        if os.path.exists(ASSETS["welcome"]):
            art.setPixmap(
                QPixmap(ASSETS["welcome"]).scaled(
                    430, 430, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        row.addWidget(art, 1)
        return page

    def _dashboard_page(self):
        page, layout = self._page("DashboardPage")
        layout.addWidget(HeroBanner(self))

        stats = QGridLayout()
        stats.setSpacing(10)
        layout.addLayout(stats)
        self.server_value = self._stat_card(stats, 0, "SERVER NUMBER", "ID")
        self.active_value = self._stat_card(stats, 1, "ACTIVE QUEUE", "TASKS")
        self.waiting_value = self._stat_card(stats, 2, "WAITING QUEUE", "TASKS")
        self.uptime_value = self._stat_card(stats, 3, "UPTIME", "HH:MM:SS")

        middle = QHBoxLayout()
        middle.setSpacing(12)
        layout.addLayout(middle, 1)

        actions, action_layout = self._panel("QUICK ACTIONS")
        actions.setFixedWidth(300)
        for text, variant, slot in [
            ("START PROGRAM", "primary", self.start_program),
            ("STOP PROGRAM", "danger", self.stop_program),
            ("SAVE SETTINGS", "secondary", self.confirm_save),
            ("TEST CONSOLE COLOURS", "secondary", self.check_colours),
        ]:
            button = self._button(text, variant)
            button.clicked.connect(slot)
            action_layout.addWidget(button)
        action_layout.addStretch()
        middle.addWidget(actions)

        console, console_layout = self._panel("LIVE CONSOLE (LATEST)")
        self.dashboard_log = self._console_widget()
        console_layout.addWidget(self.dashboard_log)
        open_logs = self._button("OPEN FULL LOGS", "secondary")
        open_logs.clicked.connect(lambda: self.show_page("logs"))
        console_layout.addWidget(open_logs, alignment=Qt.AlignRight)
        middle.addWidget(console, 1)

        footer = QGridLayout()
        footer.setSpacing(8)
        layout.addLayout(footer)
        self.memory_value = self._footer_stat(footer, 0, "MEMORY USAGE")
        self.cpu_value = self._footer_stat(footer, 1, "CPU USAGE")
        self.discord_value = self._footer_stat(footer, 2, "DISCORD")
        self.activity_value = self._footer_stat(footer, 3, "LAST ACTIVITY")
        self.clock_value = self._footer_stat(footer, 4, "SYSTEM TIME")
        return page

    def _stat_card(self, layout, column, label, sublabel):
        panel, panel_layout = self._panel()
        title = QLabel(label)
        title.setObjectName("StatLabel")
        value = QLabel("0")
        value.setObjectName("StatValue")
        sub = QLabel(sublabel)
        sub.setObjectName("StatSubLabel")
        panel_layout.addWidget(title, alignment=Qt.AlignCenter)
        panel_layout.addWidget(value, alignment=Qt.AlignCenter)
        panel_layout.addWidget(sub, alignment=Qt.AlignCenter)
        layout.addWidget(panel, 0, column)
        return value

    def _footer_stat(self, layout, column, label):
        panel, panel_layout = self._panel()
        panel_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel(label)
        title.setObjectName("FooterLabel")
        value = QLabel("--")
        value.setObjectName("FooterValue")
        panel_layout.addWidget(title)
        panel_layout.addWidget(value)
        layout.addWidget(panel, 0, column)
        return value

    def _setup_page(self):
        page, layout = self._page("SetupPage")
        layout.addWidget(self._page_title("SETUP GUIDE"))
        row = QHBoxLayout()
        row.setSpacing(14)
        layout.addLayout(row, 1)

        steps, steps_layout = self._panel()
        steps_layout.setSpacing(8)
        for number, text, state in [
            ("01", "Configure Discord Token", "DONE"),
            ("02", "Set Server Number", "DONE"),
            ("03", "Configure Gacha Names", "INCOMPLETE"),
            ("04", "Setup Queue Channels", "PENDING"),
            ("05", "Save Settings", "PENDING"),
            ("06", "Start Program", "PENDING"),
        ]:
            steps_layout.addWidget(self._setup_step(number, text, state))
        row.addWidget(steps, 1)

        detail, detail_layout = self._panel("STEP 03")
        heading = QLabel("CONFIGURE GACHA NAMES")
        heading.setObjectName("SectionHeading")
        body = QLabel(
            "Set your gacha station names below. These names will be used for "
            "text automation and queue processing."
        )
        body.setObjectName("MutedCopy")
        body.setWordWrap(True)
        go = self._button("GO TO SETTINGS  >", "primary")
        go.clicked.connect(lambda: self.show_page("settings"))
        tip, tip_layout = self._panel("TIP")
        tip_text = QLabel(
            "Make sure the names match exactly with your in-game stations to avoid errors."
        )
        tip_text.setWordWrap(True)
        tip_layout.addWidget(tip_text)
        detail_layout.addWidget(heading)
        detail_layout.addWidget(body)
        detail_layout.addWidget(go)
        detail_layout.addWidget(tip)
        detail_layout.addStretch()
        row.addWidget(detail, 1)
        return page

    def _setup_step(self, number, text, state):
        item = QFrame()
        item.setObjectName("StepItem")
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 9, 12, 9)
        label = QLabel(number)
        label.setObjectName("StepNumber")
        title = QLabel(text)
        badge = QLabel(state)
        badge.setObjectName(
            "BadgeDone"
            if state == "DONE"
            else "BadgeWarn" if state == "INCOMPLETE" else "BadgePending"
        )
        layout.addWidget(label)
        layout.addWidget(title, 1)
        layout.addWidget(badge)
        return item

    def _settings_page(self):
        page, layout = self._page("SettingsPage")
        layout.addWidget(self._page_title("SETTINGS"))

        shell, shell_layout = self._panel()
        shell_layout.setContentsMargins(0, 0, 0, 0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        shell_layout.addLayout(content, 1)
        layout.addWidget(shell, 1)

        self.settings_tabs = QButtonGroup(self)
        self.settings_tabs.setExclusive(True)
        tabs = QVBoxLayout()
        tabs.setContentsMargins(8, 10, 8, 10)
        tabs.setSpacing(6)
        tab_frame = QFrame()
        tab_frame.setObjectName("SettingsTabs")
        tab_frame.setFixedWidth(210)
        tab_frame.setLayout(tabs)
        content.addWidget(tab_frame)

        form_area = QScrollArea()
        form_area.setWidgetResizable(True)
        form_area.setObjectName("SettingsScroll")
        self.settings_form = QWidget()
        self.settings_form_layout = QGridLayout(self.settings_form)
        self.settings_form_layout.setContentsMargins(28, 20, 28, 20)
        self.settings_form_layout.setHorizontalSpacing(18)
        self.settings_form_layout.setVerticalSpacing(10)
        form_area.setWidget(self.settings_form)
        content.addWidget(form_area, 1)

        for group_name in SETTINGS_GROUPS:
            button = AnimatedButton(group_name, "nav")
            button.setObjectName("SettingsTab")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, name=group_name: self._render_settings_group(name)
            )
            self.settings_tabs.addButton(button)
            tabs.addWidget(button)
            if group_name == "GENERAL":
                button.setChecked(True)
        tabs.addStretch()

        action_bar = QHBoxLayout()
        shell_layout.addLayout(action_bar)
        action_bar.addStretch()
        save_button = self._button("SAVE SETTINGS", "primary")
        reset_button = self._button("RESET", "secondary")
        save_button.clicked.connect(self.confirm_save)
        reset_button.clicked.connect(self.confirm_reset)
        action_bar.addWidget(save_button)
        action_bar.addWidget(reset_button)
        self._render_settings_group("GENERAL")
        return page

    def _render_settings_group(self, group_name):
        self._capture_visible_fields()
        while self.settings_form_layout.count():
            item = self.settings_form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.fields = {}

        heading = QLabel(f"{group_name} SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)

        keys = SETTINGS_GROUPS[group_name]
        for index, key in enumerate(keys, start=1):
            default_value = DEFAULT_SETTINGS[key]
            label = QLabel(key)
            label.setObjectName("FormLabel")
            row = 1 + ((index - 1) // 2)
            col = 0 if index % 2 else 2
            self.settings_form_layout.addWidget(label, row, col)
            if isinstance(default_value, bool):
                field = QCheckBox()
                field.setChecked(bool(self.form_values.get(key, default_value)))
            else:
                field = QLineEdit(str(self.form_values.get(key, default_value)))
                if key == "discord_api_key":
                    field.setEchoMode(QLineEdit.Password)
            field.setObjectName("SettingField")
            self.fields[key] = field
            self.settings_form_layout.addWidget(field, row, col + 1)

        self.settings_form_layout.setColumnStretch(1, 1)
        self.settings_form_layout.setColumnStretch(3, 1)

    def _logs_page(self):
        page, layout = self._page("LogsPage")
        layout.addWidget(self._page_title("LOGS"))
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        layout.addLayout(filter_row)
        for name in ["ALL", "INFO", "SUCCESS", "WARN", "ERROR", "QUEUE"]:
            button = self._button(name, "secondary")
            button.clicked.connect(
                lambda checked=False, value=name: self.set_log_filter(value)
            )
            filter_row.addWidget(button)
        filter_row.addStretch()
        clear = self._button("CLEAR LOGS", "danger")
        export = self._button("EXPORT", "secondary")
        clear.clicked.connect(self.clear_logs)
        export.clicked.connect(self.copy_logs)
        filter_row.addWidget(clear)
        filter_row.addWidget(export)

        console, console_layout = self._panel()
        self.full_log = self._console_widget()
        console_layout.addWidget(self.full_log)
        layout.addWidget(console, 1)
        bottom = QHBoxLayout()
        test = self._button("TEST CONSOLE COLOURS  >", "secondary")
        copy = self._button("COPY LOGS", "primary")
        test.clicked.connect(self.check_colours)
        copy.clicked.connect(self.copy_logs)
        bottom.addWidget(test)
        bottom.addStretch()
        bottom.addWidget(copy)
        layout.addLayout(bottom)
        return page

    def _console_widget(self):
        console = ClickableTextEdit()
        console.setObjectName("Console")
        console.setReadOnly(True)
        console.copied.connect(lambda: self.toast("Logs copied", "success"))
        return console

    def _update_page(self):
        page, layout = self._page("UpdatePage")
        layout.addWidget(self._page_title("CHECK UPDATE"))
        layout.addStretch()
        card, card_layout = self._panel()
        card.setMaximumWidth(420)
        icon = QLabel("[CLOUD]")
        icon.setObjectName("UpdateIcon")
        icon.setAlignment(Qt.AlignCenter)
        current = QLabel("CURRENT VERSION\nv1.0.0")
        current.setAlignment(Qt.AlignCenter)
        latest = QLabel("LATEST VERSION\nv1.1.0\nUpdate available!")
        latest.setObjectName("UpdateLatest")
        latest.setAlignment(Qt.AlignCenter)
        changelog, changelog_layout = self._panel("CHANGELOG")
        changelog_layout.addWidget(QLabel("- Added new queue management"))
        changelog_layout.addWidget(QLabel("- Improved stability and performance"))
        changelog_layout.addWidget(QLabel("- Fixed minor bugs"))
        row = QHBoxLayout()
        check = self._button("CHECK UPDATE  >", "primary")
        download = self._button("OPEN DOWNLOAD PAGE", "secondary")
        check.clicked.connect(
            lambda: self.toast("Update check is not wired yet.", "info")
        )
        download.clicked.connect(
            lambda: self.toast("Download page is not configured yet.", "info")
        )
        row.addWidget(check)
        row.addWidget(download)
        card_layout.addWidget(icon)
        card_layout.addWidget(current)
        card_layout.addWidget(latest)
        card_layout.addWidget(changelog)
        card_layout.addLayout(row)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def _about_page(self):
        page, layout = self._page("AboutPage")
        layout.addWidget(self._page_title("ABOUT ME"))
        layout.addStretch()
        card, card_layout = self._panel()
        card.setMaximumWidth(420)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        if os.path.exists(ASSETS["logo"]):
            logo.setPixmap(
                QPixmap(ASSETS["logo"]).scaled(
                    110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        title = QLabel(f"{APP_TITLE}\n{APP_VERSION}")
        title.setObjectName("AboutTitle")
        title.setAlignment(Qt.AlignCenter)
        author = QLabel('DEVELOPED BY\nShen\n\n"Code. Automate. Dominate."')
        author.setAlignment(Qt.AlignCenter)
        connect = QHBoxLayout()
        for text in ["DISCORD", "GITHUB", "WEBSITE"]:
            button = self._button(text, "secondary")
            button.clicked.connect(
                lambda checked=False, name=text: self.toast(
                    f"{name} link is not configured yet.", "info"
                )
            )
            connect.addWidget(button)
        thanks = QLabel(f"SPECIAL THANKS TO\nYou, for using {APP_NAME}")
        thanks.setObjectName("MutedCopy")
        thanks.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(author)
        card_layout.addLayout(connect)
        card_layout.addWidget(thanks)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def confirm_save(self):
        if not self.confirm(
            "Save Settings",
            "Write the current settings to json_files/settings.json?",
            "SAVE",
        ):
            return
        self.save()

    def save(self):
        try:
            self._capture_visible_fields()
            new_data = self._collect_settings()
        except ValueError as exc:
            self.dialog("Invalid Settings", str(exc), "error")
            return

        save_settings(new_data)
        self.settings = new_data
        self.form_values = new_data.copy()
        self.append_log("[SUCCESS] Settings saved successfully.\n")
        self.dialog("Settings Saved", "Settings were saved successfully.", "success")

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
            if isinstance(DEFAULT_SETTINGS[key], bool):
                self.form_values[key] = field.isChecked()
            else:
                self.form_values[key] = field.text()

    def confirm_reset(self):
        if not self.confirm(
            "Reset Visible Settings",
            "Reset all visible setting values to defaults? This will not write to disk until you save.",
            "RESET",
        ):
            return
        self.reset_visible_settings()

    def reset_visible_settings(self):
        for key, field in self.fields.items():
            value = DEFAULT_SETTINGS[key]
            if isinstance(value, bool):
                field.setChecked(value)
            else:
                field.setText(str(value))
            self.form_values[key] = value
        self.append_log("[INFO] Visible settings reset to defaults.\n")
        self.dialog(
            "Settings Reset",
            "Visible settings were reset. Save to persist changes.",
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
            self.append_log("[INFO] Started main_program.py.\n")
            threading.Thread(target=self.read_output, daemon=True).start()
        except Exception as exc:
            self.dialog("Start Failed", str(exc), "error")

    def stop_program(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process = None
            self.append_log("[WARN] Program terminated by launcher.\n")
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
        self.log_bridge.line.emit("[WARN] Program output stream closed.\n")

    def append_log(self, text):
        if "discord.gateway" in text or "logged in as" in text:
            text = text.replace("logged in as", "[SUCCESS] Logged in as")
        elif "Added task" in text and "[QUEUE]" not in text:
            text = f"[QUEUE] {text}"
        elif "ERROR" in text.upper() and "[ERROR]" not in text:
            text = f"[ERROR] {text}"

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
            self.full_log.setHtml(full)
        if hasattr(self, "dashboard_log"):
            self.dashboard_log.setHtml(preview)

    def _format_log_lines(self, lines):
        html = []
        for line in lines:
            color = COLORS["text"]
            if "[ERROR]" in line:
                color = COLORS["red"]
            elif "[WARN]" in line:
                color = COLORS["yellow"]
            elif "[SUCCESS]" in line:
                color = COLORS["green"]
            elif "[INFO]" in line:
                color = COLORS["cyan"]
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
                memory_text = (
                    f"{memory.used / (1024**3):.1f}G / {memory.total / (1024**3):.1f}G"
                )
            else:
                memory = get_memory_usage_gb()
                if memory:
                    memory_text = f"{memory[0]:.1f}G / {memory[1]:.1f}G"
            self.memory_value.setText(memory_text)

            if psutil:
                self.cpu_value.setText(f"{psutil.cpu_percent(interval=None):.0f}%")
            else:
                current_times = get_cpu_times()
                cpu_percent = calculate_cpu_percent(self._cpu_times, current_times)
                self._cpu_times = current_times or self._cpu_times
                self.cpu_value.setText(
                    f"{cpu_percent:.0f}%" if cpu_percent is not None else "0%"
                )

            running = self.process and self.process.poll() is None
            self.discord_value.setText("CONNECTED" if running else "DISCONNECTED")
            self.activity_value.setText(self.last_activity)
            self.clock_value.setText(time.strftime("%I:%M:%S %p"))

    def _style_sheet(self):
        return f"""
        QWidget#AppRoot, QWidget#PageStack {{
            background: {COLORS["bg"]};
            color: {COLORS["text"]};
            font-family: Segoe UI;
        }}
        QFrame#TitleBar {{
            background: #03070C;
            border-bottom: 1px solid {COLORS["border"]};
        }}
        QLabel#ChromeTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["chrome_title"]}px;
            font-weight: 900;
            letter-spacing: 1px;
        }}
        QLabel#ChromeVersion, QLabel#SidebarMeta, QLabel#FooterLabel, QLabel#StatSubLabel {{
            color: {COLORS["muted"]};
            font-family: Consolas;
        }}
        QLabel#ChromeStatus, QLabel#SidebarReady {{
            color: {COLORS["green"]};
            font-family: Consolas;
            font-weight: 700;
        }}
        QPushButton#ChromeButton, QPushButton#ChromeCloseButton {{
            background: transparent;
            color: {COLORS["cyan"]};
            border: none;
            font-weight: 800;
        }}
        QPushButton#ChromeButton:hover {{
            background: rgba(0, 216, 255, 41);
        }}
        QPushButton#ChromeCloseButton:hover {{
            background: {COLORS["red"]};
            color: white;
        }}
        QFrame#Sidebar {{
            background: #050A10;
            border-right: 1px solid {COLORS["border"]};
        }}
        QLabel#SidebarBrand {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["sidebar_brand"]}px;
            font-weight: 900;
        }}
        QPushButton#NavButton {{
            min-height: 40px;
            text-align: left;
            padding-left: 18px;
            background: transparent;
            color: {COLORS["text"]};
            border: 1px solid transparent;
            font-size: {FONT_SIZES["nav"]}px;
            font-weight: 800;
        }}
        QPushButton#NavButton:hover {{
            background: rgba(0, 216, 255, 20);
            border: 1px solid rgba(0, 216, 255, 46);
        }}
        QPushButton#NavButton:checked {{
            background: rgba(0, 216, 255, 41);
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 115);
        }}
        QPushButton#MusicButton {{
            background: #06101A;
            color: {COLORS["cyan"]};
            border: 1px solid {COLORS["border"]};
            min-height: 32px;
        }}
        QFrame#Panel, QFrame#HeroBanner, QFrame#StepItem {{
            background: rgba(10, 16, 25, 235);
            border: 1px solid {COLORS["border"]};
        }}
        QLabel#PanelTitle, QLabel#PageTitle {{
            color: {COLORS["muted"]};
            font-size: {FONT_SIZES["panel_title"]}px;
            font-weight: 900;
        }}
        QLabel#PageTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["page_title"]}px;
        }}
        QLabel#WelcomeTitle {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["welcome_title"]}px;
            font-weight: 900;
        }}
        QLabel#SectionHeading {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 900;
        }}
        QLabel#MutedCopy, QLabel#FormLabel {{
            color: {COLORS["muted"]};
        }}
        QLabel#StatLabel {{
            color: {COLORS["muted"]};
            font-size: {FONT_SIZES["stat_label"]}px;
            font-weight: 800;
        }}
        QLabel#StatValue {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["stat_value"]}px;
            font-weight: 900;
        }}
        QLabel#FooterValue {{
            color: {COLORS["text"]};
            font-family: Consolas;
            font-size: {FONT_SIZES["footer"]}px;
            font-weight: 800;
        }}
        QTextEdit#Console {{
            background: #02060A;
            color: {COLORS["text"]};
            border: 1px solid rgba(0, 216, 255, 36);
            font-family: Consolas;
            font-size: {FONT_SIZES["console"]}px;
        }}
        QPushButton#PrimaryButton, QPushButton#SecondaryButton, QPushButton#DangerButton, QPushButton#GhostButton {{
            min-height: 34px;
            padding: 5px 16px;
            font-weight: 900;
        }}
        QPushButton#PrimaryButton {{
            background: rgba(0, 216, 255, 41);
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 168);
        }}
        QPushButton#PrimaryButton:hover {{
            background: rgba(0, 216, 255, 66);
        }}
        QPushButton#SecondaryButton, QPushButton#GhostButton {{
            background: rgba(18, 28, 42, 140);
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
        }}
        QPushButton#SecondaryButton:hover, QPushButton#GhostButton:hover {{
            color: {COLORS["cyan"]};
            border: 1px solid rgba(0, 216, 255, 128);
        }}
        QPushButton#DangerButton {{
            background: rgba(255, 77, 109, 31);
            color: {COLORS["red"]};
            border: 1px solid rgba(255, 77, 109, 148);
        }}
        QFrame#SettingsTabs {{
            background: #050A10;
            border-right: 1px solid {COLORS["border"]};
        }}
        QPushButton#SettingsTab {{
            min-height: 34px;
            text-align: left;
            padding-left: 10px;
            background: rgba(18, 28, 42, 89);
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
        }}
        QPushButton#SettingsTab:checked {{
            background: rgba(0, 216, 255, 46);
            color: {COLORS["cyan"]};
        }}
        QLineEdit#SettingField {{
            min-height: 26px;
            background: #050A10;
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            padding: 2px 8px;
            font-family: Consolas;
        }}
        QCheckBox {{
            color: {COLORS["text"]};
        }}
        QLabel#StepNumber {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["step_number"]}px;
            font-family: Consolas;
        }}
        QLabel#BadgeDone, QLabel#BadgeWarn, QLabel#BadgePending {{
            padding: 4px 9px;
            font-size: {FONT_SIZES["badge"]}px;
            font-weight: 900;
        }}
        QLabel#BadgeDone {{
            color: {COLORS["green"]};
            border: 1px solid rgba(107, 255, 158, 102);
        }}
        QLabel#BadgeWarn {{
            color: {COLORS["yellow"]};
            border: 1px solid rgba(255, 209, 102, 102);
        }}
        QLabel#BadgePending {{
            color: {COLORS["muted"]};
            border: 1px solid {COLORS["border"]};
        }}
        QLabel#UpdateIcon {{
            color: {COLORS["cyan"]};
            font-size: {FONT_SIZES["update_icon"]}px;
        }}
        QLabel#UpdateLatest {{
            color: {COLORS["green"]};
            font-size: {FONT_SIZES["section_heading"]}px;
            font-weight: 800;
        }}
        QLabel#AboutTitle {{
            color: {COLORS["text"]};
            font-size: {FONT_SIZES["about_title"]}px;
            font-weight: 900;
        }}
        QScrollArea#SettingsScroll {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: #050A10;
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["border"]};
            min-height: 24px;
        }}
        """
