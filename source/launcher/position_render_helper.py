from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
)

from source.launcher.components.helper_window import BaseHelperWindow
from source.launcher.components.widgets import AnimatedButton, WrappedStatusLabel
from source.launcher.deposit_route_helper import DepositHelperGuide
from source.launcher.utils.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_yaw,
)


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


class PositionRenderHelper(BaseHelperWindow):
    def __init__(self, owner):
        super().__init__(
            owner,
            "POSITION / RENDER HELPER",
            430,
            260,
            route_kind="position_render",
            route_index=None,
            position="top_right",
            hotkey_hint="ALT + N focuses this helper",
            unavailable_hotkey_hint="ALT + N focus hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self.capture_in_progress = False
        self.pending_cursor_position = None
        self.guide_timer = self._single_shot_timer(self.show_guide)
        self.cursor_restore_timer = self._single_shot_timer(
            self._restore_pending_cursor
        )
        self._build_ui()
        self._register_hotkey()
        self.guide_timer.start(0)

    def _single_shot_timer(self, callback):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        return timer

    def _build_ui(self):
        guide = self._button("?", "Open guide book")
        guide.clicked.connect(self.show_guide)
        self.add_header_action(guide)

        for key in "station_yaw":
            self.content_layout.addWidget(self._setting_row(key))

        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)

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
        if not self._require_ark_window("capture render position"):
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
        if not self._require_ark_window("view render position"):
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

    def _restore_pending_cursor(self):
        cursor_position = self.pending_cursor_position
        self.pending_cursor_position = None
        if self.closing or cursor_position is None:
            return
        QCursor.setPos(cursor_position)

    def _before_close(self):
        self.guide_timer.stop()
        self.cursor_restore_timer.stop()
        self.pending_cursor_position = None

    def _button(self, text, tooltip, variant="secondary"):
        return self._helper_button(text, tooltip, variant)
