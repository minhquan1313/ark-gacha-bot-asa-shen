import ctypes

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from source.launcher.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_yaw,
)
from source.launcher.deposit_route_helper import DepositHelperGuide, WM_HOTKEY
from source.launcher.native_window import WindowsMSG
from source.launcher.widgets import AnimatedButton


class PositionRenderGuide(DepositHelperGuide):
    PAGES = [
        (
            "POSITION / RENDER HELPER",
            "Capture the current horizontal view for each render setting. Replace this placeholder guide with your preferred setup steps later.",
            "welcome",
        ),
        (
            "CAPTURE AND VIEW",
            "Capture stores the current yaw only. View applies the saved yaw with pitch zero. Press Alt + N to return to the helper.",
            "dashboard",
        ),
    ]


class PositionRenderHelper(QWidget):
    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.guide = None
        self.drag_position = None
        self.mouse_inside = False
        self.capture_in_progress = False
        self.closing = False
        self.pending_cursor_position = None
        self.hotkey_id = (id(self) & 0x3FFF) + 1
        self.hotkey_registered = False
        self.guide_timer = self._single_shot_timer(self.show_guide)
        self.cursor_restore_timer = self._single_shot_timer(
            self._restore_pending_cursor
        )

        self.setObjectName("DepositHelperWindow")
        self.setStyleSheet(owner.styleSheet())
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(430, 260)
        self._build_ui()
        self._position_top_right()
        self._register_hotkey()
        self.guide_timer.start(0)

    def _single_shot_timer(self, callback):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        return timer

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("DepositHelperWindow")
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(0, 0, 0, 0)
        self.header_title = QLabel("POSITION / RENDER HELPER")
        self.header_title.installEventFilter(self)
        self.header_title.setObjectName("HelperTitle")
        guide = self._button("?", "Open guide book")
        guide.clicked.connect(self.show_guide)
        close = self._button("X", "Close helper", "danger")
        close.clicked.connect(self.close)
        header.addWidget(self.header_title)
        header.addStretch()
        header.addWidget(guide)
        header.addWidget(close)
        layout.addWidget(self.header_frame)

        hint = QLabel("ALT + N focuses this helper")
        hint.setObjectName("HelperHint")
        self.hotkey_label = hint
        layout.addWidget(hint)

        for key in ("station_yaw", "render_pushout"):
            layout.addWidget(self._setting_row(key))

        self.status = QLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        layout.addWidget(self.status)

    def _setting_row(self, key):
        row = QFrame()
        row.setObjectName("HelperRow")
        layout = QHBoxLayout(row)
        label = QLabel(key)
        label.setObjectName("HelperRowSummary")
        value = QLabel(str(self.owner.settings.get(key, 0.0)))
        value.setObjectName("HelperStatus")
        capture = self._button("C", f"Capture current yaw for {key}")
        capture.clicked.connect(lambda checked=False, name=key: self.capture(name))
        view = self._button("V", f"View saved yaw for {key}")
        view.clicked.connect(lambda checked=False, name=key: self.view(name))
        layout.addWidget(label, 1)
        layout.addWidget(value)
        layout.addWidget(capture)
        layout.addWidget(view)
        return row

    def capture(self, key):
        if self.capture_in_progress:
            return
        cursor_position = QCursor.pos()
        try:
            self._set_busy(True, "Capturing yaw...")
            yaw, _pitch = capture_ccc_yaw_pitch()
            self.owner.form_values[key] = yaw
            self.owner.settings[key] = yaw
            field = self.owner.fields.get(key)
            if field is not None:
                field.setText(str(yaw))
            self.owner.persist_settings_from_visible_fields(show_log=False)
            self.owner._render_settings_group("POSITION / RENDER")
            self.status.setText(f"Saved {key}: {yaw:.2f}.")
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
        finally:
            self._set_busy(False)
            self.refocus_helper(cursor_position)

    def view(self, key):
        if self.capture_in_progress:
            return
        cursor_position = QCursor.pos()
        try:
            self._set_busy(True, "Setting Ark view...")
            view_yaw(self.owner.settings.get(key, 0.0))
            self.status.setText("View applied.")
        except Exception as exc:
            self.status.setText(f"View failed: {exc}")
        finally:
            self._set_busy(False)
            self.refocus_helper(cursor_position)

    def _set_busy(self, active, message=None):
        self.capture_in_progress = active
        if message:
            self.status.setText(message)
        for button in self.findChildren(AnimatedButton):
            button.setEnabled(not active)
        QApplication.processEvents()

    def show_guide(self):
        if self.closing:
            return
        if self.guide is None:
            self.guide = PositionRenderGuide(self)
        self.guide.show()
        self.guide.raise_()
        self.guide.activateWindow()
        self.sync_window_opacity()

    def refocus_helper(self, cursor_position=None):
        if self.closing:
            return
        self.show()
        self.raise_()
        self.activateWindow()
        if cursor_position is not None:
            self.pending_cursor_position = cursor_position
            self.cursor_restore_timer.start(0)

    def _restore_pending_cursor(self):
        cursor_position = self.pending_cursor_position
        self.pending_cursor_position = None
        if self.closing or cursor_position is None:
            return
        QCursor.setPos(cursor_position)

    def _position_top_right(self):
        screen = self.screen() or self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.right() - self.width() - 18, rect.top() + 18)

    def _register_hotkey(self):
        if not hasattr(ctypes, "windll"):
            self.hotkey_label.setText("ALT + N focus hotkey unavailable here")
            return
        try:
            self.hotkey_registered = register_alt_n_hotkey(
                int(self.winId()), self.hotkey_id
            )
        except Exception:
            self.hotkey_registered = False
        if not self.hotkey_registered:
            self.hotkey_label.setText("ALT + N focus hotkey unavailable")

    def nativeEvent(self, event_type, message):
        if self.hotkey_registered:
            msg = WindowsMSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                self.refocus_helper()
                return True, 0
        return super().nativeEvent(event_type, message)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange:
            self.sync_window_opacity()

    def eventFilter(self, watched, event):
        if watched not in (
            getattr(self, "header_frame", None),
            getattr(self, "header_title", None),
        ):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            return True
        if (
            event.type() == QEvent.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self.drag_position = None
            return True
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        self.mouse_inside = True
        self.sync_window_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self.sync_window_opacity()
        super().leaveEvent(event)

    def sync_window_opacity(self):
        guide_active = self.guide is not None and self.guide.isActiveWindow()
        guide_hovered = self.guide is not None and self.guide.mouse_inside
        owner_active = self.owner is not None and self.owner.isActiveWindow()
        keep_visible = (
            self.mouse_inside
            or guide_hovered
            or self.isActiveWindow()
            or guide_active
            or owner_active
        )
        opacity = float(self.owner.settings.get("helper_inactive_opacity", 0.3))
        self.setWindowOpacity(1.0 if keep_visible else max(0.1, min(1.0, opacity)))

    def closeEvent(self, event):
        self.closing = True
        self.guide_timer.stop()
        self.cursor_restore_timer.stop()
        self.pending_cursor_position = None
        if self.hotkey_registered and hasattr(ctypes, "windll"):
            try:
                unregister_hotkey(int(self.winId()), self.hotkey_id)
            except Exception:
                pass
        self.hotkey_registered = False
        if self.guide is not None:
            self.guide.close()
        if self.owner is not None and hasattr(self.owner, "forget_deposit_helper"):
            self.owner.forget_deposit_helper(self)
        super().closeEvent(event)

    @staticmethod
    def _button(text, tooltip, variant="secondary"):
        button = AnimatedButton(text, variant)
        button.setObjectName("HelperIconButton")
        button.setToolTip(tooltip)
        return button
