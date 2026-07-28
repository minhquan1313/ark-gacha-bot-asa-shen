from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    ChromeIconButton,
    CyberDialog,
    CyberSwitch,
    RoundedShellFrame,
    SmoothScrollArea,
    WrappedStatusLabel,
    sync_rounded_window_mask,
)
from source.launcher.config.auto_feed_config import (
    AUTO_FEED_PATH,
    default_baby,
    load_auto_feed,
    normalize_auto_feed,
    save_auto_feed,
)
from source.launcher.config.constants import ASSETS, UI_METRICS
from source.launcher.utils.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    focus_game_window,
    preload_capture_view_dependencies,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_route_entry,
    view_yaw,
)


class AutoFeedGuide(QDialog):
    """Show temporary setup guidance using the shared helper guide shell."""

    PAGES = [
        (
            "STEP 1 / PREPARE",
            "Placeholder: position the character safely and make sure the player is "
            "outside the Tek pod before configuring Baby locations.",
            "welcome",
        ),
        (
            "STEP 2 / CAPTURE BABIES",
            "Placeholder: use Capture Add for a new Baby, or capture and view an "
            "existing Baby row while aiming at its inventory location.",
            "dashboard",
        ),
        (
            "STEP 3 / CHOOSE MODE",
            "Placeholder: Tek pod mode waits inside the pod. Non-Tek-pod mode shows "
            "a warning and uses the configured food and water actions.",
            "logo",
        ),
        (
            "STEP 4 / START CYCLE",
            "Placeholder: the helper feeds every Baby, waits through the feed cycle, "
            "and repeats until the helper is stopped.",
            "logo_text",
        ),
    ]

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("AutoFeedGuide")
        self.setStyleSheet(parent.styleSheet())
        self.setWindowTitle("Auto Baby Feeding Guide")
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.page_index = 0
        self.drag_position = None
        self.mouse_inside = False

        shell = RoundedShellFrame()
        shell.setObjectName("DepositHelperWindow")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(8, 0, 0, 0)
        header.setSpacing(8)
        self.header_title = QLabel("HELPER GUIDE")
        self.header_title.setObjectName("HelperTitle")
        self.header_title.installEventFilter(self)
        close = ChromeIconButton("close")
        close.setToolTip("Close guide")
        close.clicked.connect(self.close)
        header.addWidget(self.header_title)
        header.addStretch()
        header.addWidget(close)
        shell_layout.addWidget(self.header_frame)

        body = QWidget()
        body.setObjectName("HelperBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 10, 16, 14)
        layout.setSpacing(10)
        shell_layout.addWidget(body, 1)

        self.stack = QStackedWidget()
        for title_text, body_text, asset_key in self.PAGES:
            self.stack.addWidget(self._guide_page(title_text, body_text, asset_key))
        layout.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        self.prev_button = AnimatedButton("PREV", "secondary")
        self.prev_button.clicked.connect(self.previous_page)
        self.page_label = QLabel()
        self.page_label.setObjectName("HelperHint")
        self.next_button = AnimatedButton("NEXT", "primary")
        self.next_button.clicked.connect(self.next_page)
        footer.addWidget(self.prev_button)
        footer.addStretch()
        footer.addWidget(self.page_label)
        footer.addStretch()
        footer.addWidget(self.next_button)
        layout.addLayout(footer)
        self._sync_page_controls()

        self.resize(420, 420)
        sync_rounded_window_mask(self, UI_METRICS["window_radius"])

    def _guide_page(self, title_text: str, body_text: str, asset_key: str) -> QWidget:
        page = QWidget()
        page.setObjectName("HelperGuidePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        image = QLabel()
        image.setObjectName("HelperGuideImage")
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setMinimumHeight(150)
        pixmap = QPixmap(ASSETS.get(asset_key, ""))
        if pixmap.isNull():
            pixmap = QPixmap(ASSETS["logo"])
        if not pixmap.isNull():
            image.setPixmap(
                pixmap.scaled(
                    360,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(image)

        title = QLabel(title_text)
        title.setObjectName("HelperGuideStepTitle")
        layout.addWidget(title)

        body = QLabel(body_text)
        body.setObjectName("MutedCopy")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
        return page

    def next_page(self):
        self.page_index = min(self.page_index + 1, len(self.PAGES) - 1)
        self._sync_page_controls()

    def previous_page(self):
        self.page_index = max(self.page_index - 1, 0)
        self._sync_page_controls()

    def _sync_page_controls(self):
        self.stack.setCurrentIndex(self.page_index)
        self.prev_button.setEnabled(self.page_index > 0)
        self.next_button.setEnabled(self.page_index < len(self.PAGES) - 1)
        self.page_label.setText(f"{self.page_index + 1} / {len(self.PAGES)}")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            self._sync_parent_opacity()

    def enterEvent(self, event):
        self.mouse_inside = True
        self._sync_parent_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self._sync_parent_opacity()
        super().leaveEvent(event)

    def closeEvent(self, event):
        self.mouse_inside = False
        self._sync_parent_opacity()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        sync_rounded_window_mask(self, UI_METRICS["window_radius"])

    def _sync_parent_opacity(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "sync_window_opacity"):
            parent.sync_window_opacity()

    def eventFilter(self, watched, event):
        header_frame = getattr(self, "header_frame", None)
        header_title = getattr(self, "header_title", None)
        if watched not in (header_frame, header_title):
            return super().eventFilter(watched, event)
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return True
        if (
            event.type() == QEvent.Type.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.drag_position = None
            event.accept()
            return True
        return super().eventFilter(watched, event)


class AutoBabyFeedingHelper(WorkerHelperWindow):
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object):
        self.config = load_auto_feed()
        self.baby_rows = []
        self.collapsible_sections = []
        self._preloaded = False
        super().__init__(
            owner,
            "Auto Baby",
            360,
            520,
            route_kind="auto_feed",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self._build_ui()
        self._register_hotkey()
        self.worker_ready.connect(self._on_worker_ready)
        self.worker_finished.connect(self._on_worker_finished)
        self._preload_capture()

    def _build_ui(self):
        guide = self._titlebar_button("?", "Open helper guide")
        guide.clicked.connect(self.show_guide)
        self.add_header_action(guide)

        scroll = SmoothScrollArea()
        scroll.setObjectName("HelperScroll")
        scroll.setWidgetResizable(True)
        self.idle_scroll = scroll
        content = QWidget()
        content.setObjectName("HelperScrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)
        scroll.setWidget(content)
        self.content_layout.addWidget(scroll, 1)

        settings, settings_layout = self._collapsible_section("Mode")
        self.tek_pod_switch = CyberSwitch("Tek pod")
        self.tek_pod_switch.setChecked(bool(self.config["tek_pod"]))
        self.tek_pod_switch.toggled.connect(self._mode_changed)
        settings_layout.addWidget(self.tek_pod_switch)

        self.tek_settings = QWidget()
        tek_layout = QHBoxLayout(self.tek_settings)
        tek_layout.setContentsMargins(0, 0, 0, 0)
        tek_layout.addWidget(self._label("Station yaw"))
        self.station_yaw = self._field(self.config["station_yaw"])
        tek_layout.addWidget(self.station_yaw, 1)
        capture = self._helper_action_button(
            "icon.capture_target", "Capture station yaw"
        )
        capture.clicked.connect(self._capture_station_yaw)
        view = self._helper_action_button("icon.view_eye", "View station yaw")
        view.clicked.connect(self._view_station_yaw)
        tek_layout.addWidget(capture)
        tek_layout.addWidget(view)
        settings_layout.addWidget(self.tek_settings)

        self.no_tek_settings = QWidget()
        no_tek_layout = QHBoxLayout(self.no_tek_settings)
        no_tek_layout.setContentsMargins(0, 0, 0, 0)
        no_tek_layout.addWidget(self._label("Food slot"))
        self.food_slot = self._field(self.config["food_slot"])
        no_tek_layout.addWidget(self.food_slot, 1)
        no_tek_layout.addWidget(self._label("Water slot"))
        self.water_slot = self._field(self.config["water_slot"])
        no_tek_layout.addWidget(self.water_slot, 1)
        settings_layout.addWidget(self.no_tek_settings)

        cycle_row = QHBoxLayout()
        cycle_row.addWidget(self._label("Cycle"))
        self.feed_cycle = self._field(self.config["feed_cycle"])
        cycle_row.addWidget(self.feed_cycle, 1)
        settings_layout.addLayout(cycle_row)
        for field in (
            self.station_yaw,
            self.food_slot,
            self.water_slot,
            self.feed_cycle,
        ):
            field.editingFinished.connect(self._persist)
        self.warning = QLabel(
            "WARNING // NO TEK POD\nMake sure every Baby location is correct before starting."
        )
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(
            "QLabel { color: #FFD166; background: rgba(82, 45, 8, 190); "
            "border: 1px solid #FF9F1C; padding: 8px; }"
        )
        settings_layout.addWidget(self.warning)
        layout.addWidget(settings)

        babies, babies_layout = self._collapsible_section("BABY")
        self.babies_layout = QVBoxLayout()
        self.babies_layout.setContentsMargins(0, 0, 0, 0)
        self.babies_layout.setSpacing(6)
        babies_layout.addLayout(self.babies_layout)

        actions = QFrame()
        actions.setObjectName("AutoFeedAddCaptureRow")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(8, 8, 8, 8)
        actions_layout.setSpacing(8)
        add = AnimatedButton("Add baby", "secondary")
        add.clicked.connect(self._add_baby)
        capture_add = AnimatedButton("Capture add", "primary")
        capture_add.clicked.connect(self._capture_add_baby)
        actions_layout.addWidget(add, 1)
        actions_layout.addWidget(capture_add, 1)
        babies_layout.addWidget(actions)
        layout.addWidget(babies)
        layout.addStretch(1)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        self.content_layout.addWidget(self.start_stop_button)
        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)
        self.register_minimal_running_widgets(scroll)
        self._refresh_babies()
        self._mode_changed(self.tek_pod_switch.isChecked())

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label

    @staticmethod
    def _field(value: object) -> QLineEdit:
        field = QLineEdit(str(value))
        field.setObjectName("SettingField")
        return field

    def _collapsible_section(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        """Create a transparent Transfer-style collapsible section."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(0, 6, 0, 0)
        header.setSpacing(8)
        toggle = self._helper_button("v", f"Expand or collapse {title.lower()}")
        toggle.setObjectName("HelperExpandButton")
        label = QLabel()
        label.setObjectName("SettingsDividerLabel")
        line = QFrame()
        line.setObjectName("SettingsDividerLine")
        line.setFixedHeight(1)
        header.addWidget(toggle)
        header.addWidget(label)
        header.addWidget(line, 1)
        layout.addLayout(header)

        body = QWidget()
        body.setObjectName("AutoFeedSectionBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        layout.addWidget(body)
        toggle.clicked.connect(
            lambda checked=False, target=body, button=toggle: self._toggle_section(
                target, button
            )
        )
        self.collapsible_sections.append((body, toggle))

        if title == "BABY":
            self.baby_section_label = label
            self.baby_section_title = title
        else:
            label.setText(title)
        return wrapper, body_layout

    @staticmethod
    def _toggle_section(body: QWidget, toggle: AnimatedButton):
        """Toggle one collapsible section body and synchronize its arrow."""
        expanded = body.isHidden()
        body.setVisible(expanded)
        toggle.setText("v" if expanded else ">")

    def set_all_collapsible_expanded(self, expanded: bool):
        """Set the expanded state of the Feeding Mode and Baby sections."""
        for body, toggle in self.collapsible_sections:
            body.setVisible(bool(expanded))
            toggle.setText("v" if expanded else ">")

    def _mode_changed(self, tek_pod: bool):
        self.tek_settings.setVisible(tek_pod)
        self.no_tek_settings.setVisible(not tek_pod)
        self.warning.setVisible(not tek_pod)
        self._persist()

    def _refresh_babies(self):
        while self.babies_layout.count():
            item = self.babies_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.baby_rows.clear()
        for index, baby in enumerate(self.config["babies"]):
            row = BabyRow(self, index, baby)
            self.baby_rows.append(row)
            self.babies_layout.addWidget(row)
        self._renumber_babies()

    def _renumber_babies(self):
        """Refresh Baby indices, summaries, and the section count."""
        self.baby_section_label.setText(f"Baby - {len(self.baby_rows)}")
        for index, row in enumerate(self.baby_rows, 1):
            row.index = index - 1
            row.index_label.setText(f"B{index}")
            row.refresh_summary()

    def _add_baby(self):
        self.config["babies"].append(default_baby())
        self._persist()
        self._refresh_babies()

    def _remove_baby(self, index: int):
        if 0 <= index < len(self.config["babies"]):
            self.config["babies"].pop(index)
            self._persist()
            self._refresh_babies()

    def _capture_add_baby(self):
        if not self._require_ark_window("capture and add Baby"):
            return
        cursor = QCursor.pos()
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            baby = default_baby()
            baby["location"] = {"yaw": f"{yaw:.2f}", "pitch": f"{pitch:.2f}"}
            self.config["babies"].append(baby)
            self._persist()
            self._refresh_babies()
            row = self.baby_rows[-1]
            row.set_expanded(True)
            QTimer.singleShot(
                0,
                lambda target=row: self.idle_scroll.ensureWidgetVisible(target, 0, 12),
            )
            row.setFocus()
            self.status.setText(f"Captured Baby {len(self.baby_rows)}.")
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
        finally:
            self.refocus_helper(cursor)

    def _persist(self):
        if not hasattr(self, "station_yaw"):
            return
        self.config.update(
            {
                "tek_pod": self.tek_pod_switch.isChecked(),
                "station_yaw": self.station_yaw.text(),
                "food_slot": self.food_slot.text(),
                "water_slot": self.water_slot.text(),
                "feed_cycle": self.feed_cycle.text(),
            }
        )
        try:
            self.config = save_auto_feed(self.config)
            self.status.setText("Auto Baby Feeding settings saved.")
        except (TypeError, ValueError, OSError) as exc:
            self.status.setText(f"Settings not saved: {exc}")

    def _capture_station_yaw(self):
        if not self._require_ark_window("capture station yaw"):
            return
        cursor = QCursor.pos()
        try:
            yaw, _pitch = capture_ccc_yaw_pitch()
            self.station_yaw.setText(f"{yaw:.2f}")
            self._persist()
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
        finally:
            self.refocus_helper(cursor)

    def _view_station_yaw(self):
        if not self._require_ark_window("view station yaw"):
            return
        cursor = QCursor.pos()
        try:
            view_yaw(float(self.station_yaw.text()))
            self.status.setText("Station view applied.")
        except Exception as exc:
            self.status.setText(f"View failed: {exc}")
        finally:
            self.refocus_helper(cursor)

    def _preload_capture(self):
        try:
            self._preloaded = preload_capture_view_dependencies() is not None
        except Exception as exc:
            self._preloaded = False
            self.status.setText(f"Capture preload skipped: {exc}")

    def show_guide(self):
        if self.guide is None:
            self.guide = AutoFeedGuide(self)
        self.guide.show()
        self.guide.raise_()
        self.guide.activateWindow()

    def start(self):
        if self.is_running() or self.closing:
            return
        try:
            self._persist()
            self.config = normalize_auto_feed(self.config)
        except (TypeError, ValueError, OSError) as exc:
            self.status.setText(str(exc))
            return
        if not self.config["babies"]:
            self.status.setText("Add at least one Baby before starting.")
            return
        if not self._require_ark_window("start Auto Baby Feeding", "Cannot start"):
            return
        if not self.config["tek_pod"]:
            dialog = CyberDialog(
                self,
                "Start Without Tek Pod?",
                "You don't have a Tek pod. Make sure Baby locations are correct. "
                "Do you still want to start now?",
                "warning",
                confirm_text="START",
                cancel_text="CANCEL",
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        try:
            focus_game_window(center_cursor_when_switching=True)
            self._start_worker("auto_feed", "--config", str(Path(AUTO_FEED_PATH)))
            self.start_stop_button.setText("STOP")
            self.start_stop_button.set_variant("danger")
        except Exception as exc:
            self.status.setText(f"Cannot start: {exc}")

    def stop(self):
        if not self.is_running():
            return
        self.start_stop_button.setEnabled(False)
        super().stop()
        self.status.setText("Stopping...")

    def _on_worker_ready(self):
        self.start_stop_button.setEnabled(True)

    def _on_worker_finished(self, message: str):
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)


class BabyRow(QFrame):
    """Render and persist one expandable Baby configuration row."""

    def __init__(self, helper: AutoBabyFeedingHelper, index: int, baby: dict):
        super().__init__(helper)
        self.helper = helper
        self.index = index
        self.baby = baby
        self.setObjectName("AutoFeedRow")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(6)
        expand = self.helper._helper_button(">", "Expand Baby settings")
        expand.setObjectName("HelperExpandButton")
        self.details = QWidget()
        self.details.setObjectName("AutoFeedRowDetails")
        self.details.setVisible(False)
        expand.clicked.connect(lambda: self._toggle(expand))
        self.expand_button = expand
        top.addWidget(expand)
        self.index_label = QLabel("")
        self.index_label.setObjectName("FormLabel")
        self.summary = QLabel("")
        self.summary.setObjectName("HelperRowSummary")
        self.summary.setWordWrap(True)
        top.addWidget(self.index_label)
        top.addWidget(self.summary, 1)
        capture = self.helper._helper_action_button(
            "icon.capture_target", "Capture Baby location"
        )
        capture.clicked.connect(self._capture)
        view = self.helper._helper_action_button("icon.view_eye", "View Baby location")
        view.clicked.connect(self._view)
        root.addLayout(top)

        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)
        info = QHBoxLayout()
        info.setSpacing(8)
        self.yaw = self._field(self.baby["location"]["yaw"])
        self.pitch = self._field(self.baby["location"]["pitch"])
        info.addWidget(self._label("Yaw"))
        info.addWidget(self.yaw, 1)
        info.addWidget(self._label("Pitch"))
        info.addWidget(self.pitch, 1)
        details_layout.addLayout(info)

        food_row = QHBoxLayout()
        food_row.setSpacing(8)
        self.food = self._field(self.baby["food"])
        food_row.addWidget(self._label("Food"))
        food_row.addWidget(self.food, 1)
        details_layout.addLayout(food_row)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.crouched = QCheckBox("Crouched")
        self.crouched.setChecked(bool(self.baby.get("crouched", False)))
        actions.addWidget(self.crouched, 1)
        actions.addWidget(capture)
        actions.addWidget(view)
        remove = AnimatedButton("-", "danger")
        remove.setObjectName("HelperIconButton")
        remove.clicked.connect(lambda: self.helper._remove_baby(self.index))
        actions.addWidget(remove)
        details_layout.addLayout(actions)
        for field in (self.yaw, self.pitch, self.food):
            field.editingFinished.connect(self._persist)
        self.crouched.toggled.connect(self._persist)
        root.addWidget(self.details)
        self.refresh_summary()

    def _toggle(self, button):
        visible = self.details.isHidden()
        self.set_expanded(visible)
        button.setText("v" if visible else ">")

    def set_expanded(self, expanded: bool):
        """Set the row details visibility for focus-after-capture behavior."""
        self.details.setVisible(bool(expanded))

    def refresh_summary(self):
        crouch = "on" if self.crouched.isChecked() else "off"
        self.summary.setText(
            f"Yaw {self.yaw.text()} | Pitch {self.pitch.text()} | Crouch {crouch}"
        )

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label

    @staticmethod
    def _field(value: object) -> QLineEdit:
        field = QLineEdit(str(value))
        field.setObjectName("SettingField")
        return field

    def _persist(self):
        try:
            self.baby.update(
                {
                    "location": {
                        "yaw": self.yaw.text(),
                        "pitch": self.pitch.text(),
                    },
                    "crouched": self.crouched.isChecked(),
                    "food": self.food.text(),
                }
            )
            self.helper.config["babies"][self.index] = self.baby
            self.helper._persist()
            self.refresh_summary()
        except (IndexError, TypeError, ValueError) as exc:
            self.helper.status.setText(f"Baby not saved: {exc}")

    def _capture(self):
        if not self.helper._require_ark_window("capture Baby location"):
            return
        cursor = QCursor.pos()
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            self.yaw.setText(f"{yaw:.2f}")
            self.pitch.setText(f"{pitch:.2f}")
            self._persist()
        except Exception as exc:
            self.helper.status.setText(f"Capture failed: {exc}")
        finally:
            self.helper.refocus_helper(cursor)

    def _view(self):
        if not self.helper._require_ark_window("view Baby location"):
            return
        cursor = QCursor.pos()
        try:
            view_route_entry(
                float(self.yaw.text()),
                float(self.pitch.text()),
                self.crouched.isChecked(),
            )
            self.helper.status.setText("Baby view applied.")
        except Exception as exc:
            self.helper.status.setText(f"View failed: {exc}")
        finally:
            self.helper.refocus_helper(cursor)
