import contextlib

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from source.gacha_bot.craft_config import default_crafter
from source.gacha_bot.deposit_config import default_dedi_item, default_vault_item
from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.components.helper_window import BaseHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    ChromeIconButton,
    CyberSwitch,
    RoundedShellFrame,
    SmoothScrollArea,
    WrappedStatusLabel,
    sync_rounded_window_mask,
)
from source.launcher.config.constants import ASSETS, UI_METRICS
from source.launcher.utils.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_route_entry,
)
from source.launcher.utils.vault_items_store import add_vault_item, load_vault_items

CAPTURE_ACTION_ICON = "icon.capture_target"
VIEW_ACTION_ICON = "icon.view_eye"


class DepositHelperGuide(QDialog):
    PAGES = [
        (
            "STEP 1 / RENDER BED",
            "Lay in the Gacha render bed first. This keeps the route setup aligned with the same starting flow the bot uses.",
            "welcome",
        ),
        (
            "STEP 2 / TELEPORT",
            "Get out of bed and teleport to the route teleporter you are editing in the helper.",
            "dashboard",
        ),
        (
            "STEP 3 / AIM AT TARGET",
            "Aim at the dedi, vault, grinder, or crafter until the in-game deposit/access prompt is visible.",
            "logo",
        ),
        (
            "STEP 4 / CAPTURE",
            "Press capture on a row. The helper focuses Ark, runs ccc through the existing console flow, then saves yaw and pitch. Press Alt + N to return to the helper.",
            "logo_text",
        ),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("DepositHelperGuide")
        self.setStyleSheet(parent.styleSheet())
        self.setWindowTitle("Deposit Helper Guide")
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

    def _guide_page(self, title_text, body_text, asset_key):
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
            parent.sync_window_opacity()  # type: ignore

    def eventFilter(self, watched, event):
        if watched not in (
            getattr(self, "header_frame", None),
            getattr(self, "header_title", None),
        ):
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


class DepositRouteHelper(BaseHelperWindow):
    def __init__(self, owner, route_kind, route_index):
        super().__init__(
            owner,
            self._title_for(owner, route_kind, route_index),
            460,
            640,
            route_kind=route_kind,
            route_index=route_index,
            position="top_right",
            hotkey_hint="ALT + N focuses this helper",
            unavailable_hotkey_hint="ALT + N focus hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self.row_widgets = []
        self.capture_in_progress = False
        self.pending_focus_row = None
        self.pending_cursor_position = None
        self.guide_timer = self._single_shot_timer(self.show_guide)
        self.row_focus_timer = self._single_shot_timer(self._apply_pending_focus_row)
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
        self.set_header_title(self._title())
        guide = self._titlebar_button("?", "Open guide book")
        guide.clicked.connect(self.show_guide)
        self.add_header_action(guide)

        self.scroll = SmoothScrollArea()
        self.scroll.setObjectName("HelperScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("HelperScrollContent")
        self.rows_layout = QVBoxLayout(self.scroll_content)
        self.rows_layout.setContentsMargins(0, 0, 4, 0)
        self.rows_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content)
        self.content_layout.addWidget(self.scroll, 1)

        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)
        self.refresh_rows()

    @staticmethod
    def _title_for(owner, route_kind, route_index):
        prefix, key = DepositRouteHelper._route_metadata(route_kind)
        config = owner.craft_config if route_kind == "craft" else owner.deposit_config
        route = config[key][route_index]
        teleport = route.get("teleport", "")
        return f"{prefix}: {teleport or 'NO TELEPORT'}"

    @staticmethod
    def _route_metadata(route_kind):
        """Return the display prefix and config key for a helper route kind."""
        metadata = {
            "crystal": ("Crystal", "depositCrystalData"),
            "grindable": ("Grindable", "depositGrindableData"),
            "general": ("General dedi", "depositGeneralData"),
            "craft": ("General Craft", "generalCraftData"),
        }
        return metadata[route_kind]

    def _title(self):
        prefix, _key = self._route_metadata(self.route_kind)
        route = self.route()
        teleport = route.get("teleport", "")
        return f"{prefix}: {teleport or 'NO TELEPORT'}"

    def _before_close(self):
        self.guide_timer.stop()
        self.row_focus_timer.stop()
        self.cursor_restore_timer.stop()
        self.pending_focus_row = None
        self.pending_cursor_position = None

    def show_guide(self):
        if self.closing:
            return
        if self.guide is None:
            self.guide = DepositHelperGuide(self)
        self.guide.show()
        self.guide.raise_()
        self.guide.activateWindow()
        self.sync_window_opacity()

    def route(self):
        _prefix, key = self._route_metadata(self.route_kind)
        config = (
            self.owner.craft_config
            if self.route_kind == "craft"
            else self.owner.deposit_config
        )
        return config[key][self.route_index]

    def refresh_rows(self, focus_target=None, preserve_state=True):
        row_state = self._row_state() if preserve_state else {}
        scroll_value = self.scroll.verticalScrollBar().value()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.row_widgets = []

        route = self.route()
        if self.route_kind == "crystal":
            self._add_section_label("DEDIS", len(route["dedi"]["items"]))
            for index, entry in enumerate(route["dedi"]["items"]):
                self._add_row("dedi", index, entry, focus_target, row_state)
            self._add_combo_row("dedi")
            self._add_section_label("VAULTS", len(route["vault"]["items"]))
            for index, entry in enumerate(route["vault"]["items"]):
                self._add_row("vault", index, entry, focus_target, row_state)
            self._add_combo_row("vault")
        elif self.route_kind == "grindable":
            self._add_section_label("GRINDER", 1)
            self._add_row("grinder", 0, route["grinder"], focus_target, row_state)
            self._add_section_label("DEDIS", len(route["dedi"]["items"]))
            for index, entry in enumerate(route["dedi"]["items"]):
                self._add_row("dedi", index, entry, focus_target, row_state)
            self._add_combo_row("dedi")
        else:
            if self.route_kind == "craft":
                self._add_section_label("CRAFTERS", len(route["crafters"]))
                for index, crafter in enumerate(route["crafters"]):
                    self._add_row("crafter", index, crafter, focus_target, row_state)
                self._add_combo_row("crafter")
            label = "CRAFTED ITEMS DEDIS" if self.route_kind == "craft" else "DEDIS"
            self._add_section_label(label, len(route["dedi"]["items"]))
            for index, entry in enumerate(route["dedi"]["items"]):
                self._add_row("dedi", index, entry, focus_target, row_state)
            self._add_combo_row("dedi")
        self.rows_layout.addStretch()
        if focus_target is None:
            QTimer.singleShot(
                0,
                lambda value=scroll_value: self.scroll.verticalScrollBar().setValue(
                    value
                ),
            )

    def _row_state(self):
        return {
            (row.kind, row.index): row.expanded
            for row in self.row_widgets
            if row.expanded
        }

    def _add_section_label(self, text, count):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(8)
        label = QLabel(f"{text} - {count}")
        label.setObjectName("SettingsDividerLabel")
        line = QFrame()
        line.setObjectName("SettingsDividerLine")
        line.setFixedHeight(1)
        layout.addWidget(label)
        layout.addWidget(line, 1)
        self.rows_layout.addWidget(wrapper)

    def _add_row(self, kind, index, entry, focus_target=None, row_state=None):
        row = CollapsibleHelperRow(self, kind, index, entry)
        self.row_widgets.append(row)
        self.rows_layout.addWidget(row)
        if row_state and row_state.get((kind, index)):
            row.expand()
        if focus_target == (kind, index):
            self.pending_focus_row = row
            self.row_focus_timer.start(0)

    def _apply_pending_focus_row(self):
        row = self.pending_focus_row
        self.pending_focus_row = None
        if self.closing or row not in self.row_widgets:
            return
        with contextlib.suppress(RuntimeError):
            self._focus_row(row)

    def _focus_row(self, row):
        row.expand()
        self.scroll.ensureWidgetVisible(row, 0, 12)
        row.setFocus()

    def _add_combo_row(self, kind):
        row = AddCaptureRow(self, kind)
        self.rows_layout.addWidget(row)

    def add_entry(self, kind):
        entry, index = self._append_entry(kind)
        if entry is not None:
            self.save_and_refresh((kind, index))
        return entry

    def _append_entry(self, kind):
        route = self.route()
        if kind == "dedi":
            route["dedi"]["items"].append(default_dedi_item())
            index = len(route["dedi"]["items"]) - 1
            return route["dedi"]["items"][index], index
        if kind == "crafter" and self.route_kind == "craft":
            route["crafters"].append(default_crafter())
            index = len(route["crafters"]) - 1
            return route["crafters"][index], index
        if kind == "vault" and self.route_kind == "crystal":
            route["vault"]["items"].append(default_vault_item())
            index = len(route["vault"]["items"]) - 1
            return route["vault"]["items"][index], index
        return None, None

    def delete_entry(self, kind, index):
        route = self.route()
        if kind == "dedi":
            del route["dedi"]["items"][index]
        elif kind == "vault":
            del route["vault"]["items"][index]
        elif kind == "grinder":
            route["grinder"]["location"] = {"yaw": 0.0, "pitch": 0.0}
            route["grinder"]["crouched"] = False
            route["grinder"]["active"] = False
        elif kind == "crafter":
            del route["crafters"][index]
        self.save_and_refresh()

    def capture_existing(self, kind, index):
        self.capture_entry(self._entry(kind, index), (kind, index))

    def capture_new(self, kind):
        if self.capture_in_progress:
            return
        if not self._require_ark_window("capture route location"):
            return
        cursor_position = QCursor.pos()
        success = False
        try:
            self._set_capture_in_progress(True)
            yaw, pitch = capture_ccc_yaw_pitch()
            entry, index = self._append_entry(kind)
            if entry is None:
                return
            entry["location"]["yaw"] = yaw
            entry["location"]["pitch"] = pitch
            success = self.save()
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
            return
        finally:
            self._set_capture_in_progress(False)
            self.refocus_helper(cursor_position)
        if success:
            self.refresh_rows((kind, index))
            self.status.setText(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")

    def capture_entry(self, entry, focus_target=None):
        if self.capture_in_progress:
            return
        if not self._require_ark_window("capture route location"):
            return
        cursor_position = QCursor.pos()
        success = False
        try:
            self._set_capture_in_progress(True)
            yaw, pitch = capture_ccc_yaw_pitch()
            entry["location"]["yaw"] = yaw
            entry["location"]["pitch"] = pitch
            success = self.save()
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
            return
        finally:
            self._set_capture_in_progress(False)
            self.refocus_helper(cursor_position)
        if success:
            row = self._row_for_target(focus_target)
            if row is not None:
                row.sync_from_entry()
                row.expand()
                self._focus_row(row)
            else:
                self.refresh_rows(focus_target)
            self.status.setText(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")

    def _row_for_target(self, focus_target):
        if focus_target is None:
            return None
        for row in self.row_widgets:
            if (row.kind, row.index) == focus_target:
                return row
        return None

    def view_entry(self, entry):
        if self.capture_in_progress:
            return
        if not self._require_ark_window("view route location"):
            return
        cursor_position = QCursor.pos()
        location = entry.get("location", {})
        try:
            self._set_capture_in_progress(True, "Setting Ark view...")
            view_route_entry(
                location.get("yaw", 0.0),
                location.get("pitch", 0.0),
                entry.get("crouched", False),
            )
            self.status.setText("View applied.")
        except Exception as exc:
            self.status.setText(f"View failed: {exc}")
        finally:
            self._set_capture_in_progress(False)
            self.refocus_helper(cursor_position)

    def _set_capture_in_progress(self, active, message="Capturing yaw/pitch..."):
        self.capture_in_progress = active
        if active:
            self.status.setText(message)
        for widget in self.findChildren(QWidget):
            if not isinstance(
                widget, (AnimatedButton, QCheckBox, QLineEdit, QComboBox, CyberSwitch)
            ):
                continue
            widget.setEnabled(not active)
        QApplication.processEvents()

    def _restore_pending_cursor(self):
        cursor_position = self.pending_cursor_position
        self.pending_cursor_position = None
        if self.closing or cursor_position is None:
            return
        QCursor.setPos(cursor_position)

    def _entry(self, kind, index):
        route = self.route()
        if kind == "dedi":
            return route["dedi"]["items"][index]
        if kind == "vault":
            return route["vault"]["items"][index]
        if kind == "crafter":
            return route["crafters"][index]
        return route["grinder"]

    def update_float(self, entry, key, field):
        previous = entry["location"].get(key, 0.0)
        try:
            entry["location"][key] = float(field.text())
        except ValueError:
            field.setText(str(previous))
            self.status.setText(f"{key} must be a float number.")
            return
        self.save()

    def update_crouched(self, entry, checked):
        entry["crouched"] = bool(checked)
        self.save()

    def update_active(self, entry, checked):
        entry["active"] = bool(checked)
        self.save()

    def update_crafter_item(self, entry, field):
        """Persist the crafted-item search text from a crafter helper row."""
        entry["item"] = field.text()
        self.save()

    def update_vault_item(self, vault, index, combo):
        value = combo.currentText().strip()
        if not value:
            return
        while len(vault["items"]) <= index:
            vault["items"].append("")
        vault["items"][index] = value
        add_vault_item(value, self.owner.deposit_config)
        self.save()

    def add_vault_item_row(self, vault):
        vault["items"].append("")
        self.save_and_refresh(self._target_for_entry(vault))

    def remove_vault_item_row(self, vault, index):
        if 0 <= index < len(vault["items"]):
            del vault["items"][index]
        self.save_and_refresh(self._target_for_entry(vault))

    def save(self):
        save_routes = (
            self.owner.save_craft_routes
            if self.route_kind == "craft"
            else self.owner.save_deposit_routes
        )
        if save_routes(show_log=False):
            self.status.setText("Saved.")
            return True
        self.status.setText("Save failed.")
        return False

    def save_and_refresh(self, focus_target=None):
        if self.save():
            self.refresh_rows(focus_target)

    def _target_for_entry(self, entry):
        for row in self.row_widgets:
            if row.entry is entry:
                return row.kind, row.index
        return None

    def _icon_button(self, text, tooltip, type="secondary"):
        return self._helper_button(text, tooltip, type)


class CollapsibleHelperRow(QFrame):
    def __init__(self, helper, kind, index, entry):
        super().__init__(helper)
        self.helper = helper
        self.kind = kind
        self.index = index
        self.entry = entry
        self.expanded = False
        self.float_fields = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("HelperRow")
        self._build()

    def _build(self):
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.expand_button = self.helper._icon_button(">", "Expand or collapse row")
        self.expand_button.setObjectName("HelperExpandButton")
        self.expand_button.clicked.connect(self.toggle)
        self.summary = QLabel(self._summary_text())
        self.summary.setObjectName("HelperRowSummary")
        self.summary.setWordWrap(True)
        capture = self.helper._helper_action_button(
            CAPTURE_ACTION_ICON, "Capture yaw and pitch"
        )
        capture.clicked.connect(self.capture_row)
        view = self.helper._helper_action_button(
            VIEW_ACTION_ICON, "View saved yaw and pitch in Ark"
        )
        view.clicked.connect(lambda: self.helper.view_entry(self.entry))
        top.addWidget(self.expand_button)
        top.addWidget(self.summary, 1)
        top.addWidget(capture)
        top.addWidget(view)
        self.root.addLayout(top)

        self.details = QWidget()
        self.details.setObjectName("HelperRowDetails")
        detail = QVBoxLayout(self.details)
        detail.setContentsMargins(8, 8, 8, 4)
        detail.setSpacing(8)
        coords = QHBoxLayout()
        coords.setSpacing(8)
        self._add_float_field(coords, "yaw")
        self._add_float_field(coords, "pitch")
        detail.addLayout(coords)

        switches = QHBoxLayout()
        switches.setContentsMargins(0, 2, 0, 2)
        switches.setSpacing(8)
        crouched = QCheckBox("Crouched")
        crouched.blockSignals(True)
        crouched.setChecked(bool(self.entry.get("crouched", False)))
        crouched.blockSignals(False)
        crouched.toggled.connect(self._update_crouched)
        switches.addWidget(crouched)
        if self.kind == "grinder":
            active = CyberSwitch("ACTIVE")
            active.blockSignals(True)
            active.setChecked(bool(self.entry.get("active", False)))
            active.blockSignals(False)
            active.toggled.connect(self._update_active)
            switches.addWidget(active)
        delete = self.helper._icon_button("-", "Delete row", "danger")
        delete.clicked.connect(lambda: self.helper.delete_entry(self.kind, self.index))
        switches.addStretch()
        switches.addWidget(delete)
        detail.addLayout(switches)

        if self.kind == "vault":
            self._add_vault_items(detail)
        elif self.kind == "crafter":
            self._add_crafter_item(detail)

        self.details.setVisible(False)
        self.root.addWidget(self.details)

    def _add_float_field(self, layout, key):
        label = QLabel(key)
        label.setObjectName("FormLabel")
        field = QLineEdit(str(self.entry["location"].get(key, 0.0)))
        field.setObjectName("SettingField")
        field.setMinimumWidth(86)
        field.editingFinished.connect(
            lambda name=key, editor=field: self._update_float_field(name, editor)
        )
        field.returnPressed.connect(
            lambda name=key, editor=field: self._update_float_field(name, editor)
        )
        self.float_fields[key] = field
        layout.addWidget(label)
        layout.addWidget(field)

    def _add_vault_items(self, layout):
        items = self.entry.setdefault("items", [])
        for item_index, value in enumerate(items):
            row = QHBoxLayout()
            label = QLabel(f"item {item_index + 1}")
            label.setObjectName("FormLabel")
            combo = NoWheelComboBox()
            combo.setObjectName("HelperCombo")
            combo.setEditable(True)
            options = load_vault_items(self.helper.owner.deposit_config)
            combo.addItems(options)
            if value and value not in options:
                combo.addItem(value)
            combo.setCurrentText(value)
            combo.activated.connect(
                lambda selected_index, vault=self.entry, index=item_index, widget=combo: (
                    self.helper.update_vault_item(vault, index, widget)
                )
            )
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.editingFinished.connect(
                    lambda vault=self.entry, index=item_index, widget=combo: (
                        self.helper.update_vault_item(vault, index, widget)
                    )
                )
            remove = self.helper._icon_button("-", "Remove this vault item")
            remove.clicked.connect(
                lambda checked=False, vault=self.entry, index=item_index: (
                    self.helper.remove_vault_item_row(vault, index)
                )
            )
            row.addWidget(label)
            row.addWidget(combo, 1)
            row.addWidget(remove)
            layout.addLayout(row)
        add = self.helper._icon_button("+", "Add vault item")
        add.clicked.connect(lambda: self.helper.add_vault_item_row(self.entry))
        layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignRight)

    def _add_crafter_item(self, layout):
        """Add the crafted-item search editor to the crafter row details."""
        row = QHBoxLayout()
        label = QLabel("Crafted item")
        label.setObjectName("FormLabel")
        field = QLineEdit(str(self.entry.get("item", "")))
        field.setObjectName("SettingField")
        field.editingFinished.connect(
            lambda editor=field: self.helper.update_crafter_item(self.entry, editor)
        )
        field.returnPressed.connect(
            lambda editor=field: self.helper.update_crafter_item(self.entry, editor)
        )
        row.addWidget(label)
        row.addWidget(field, 1)
        layout.addLayout(row)

    def toggle(self):
        self.expanded = not self.expanded
        self.details.setVisible(self.expanded)
        self.expand_button.setText("v" if self.expanded else ">")

    def expand(self):
        if not self.expanded:
            self.toggle()

    def sync_from_entry(self):
        for key, field in self.float_fields.items():
            field.setText(str(self.entry["location"].get(key, 0.0)))
        self.refresh_summary()

    def refresh_summary(self):
        self.summary.setText(self._summary_text())

    def _update_float_field(self, key, field):
        self.helper.update_float(self.entry, key, field)
        self.refresh_summary()

    def _update_crouched(self, checked):
        self.helper.update_crouched(self.entry, checked)
        self.refresh_summary()

    def _update_active(self, checked):
        self.helper.update_active(self.entry, checked)
        self.refresh_summary()

    def capture_row(self):
        self.helper.capture_existing(self.kind, self.index)

    def _summary_text(self):
        location = self.entry.get("location", {})
        yaw = location.get("yaw", 0.0)
        pitch = location.get("pitch", 0.0)
        suffix = " crouched" if self.entry.get("crouched", False) else ""
        if self.kind == "grinder":
            active = " active" if self.entry.get("active", False) else ""
            return f"{self.kind.upper()}   yaw {yaw}   pitch {pitch}{suffix}{active}"
        return (
            f"{self.kind.upper()} {self.index + 1}   yaw {yaw}   pitch {pitch}{suffix}"
        )


class AddCaptureRow(QFrame):
    def __init__(self, helper, kind):
        super().__init__(helper)
        self.helper = helper
        self.kind = kind
        self.setObjectName("HelperAddCaptureRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        label = "Crafted Dedi" if kind == "crafted_dedi" else kind.capitalize()
        add = helper._icon_button(f"Add {label}", f"Add blank {label.lower()}")
        add.clicked.connect(lambda checked=False: helper.add_entry(kind))
        capture = helper._icon_button(
            "Capture Add", f"Capture yaw and pitch for a new {label.lower()}"
        )
        capture.clicked.connect(lambda checked=False: helper.capture_new(kind))
        layout.addWidget(add, 1)
        layout.addWidget(capture, 1)
