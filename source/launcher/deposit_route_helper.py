import ctypes

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from source.gacha_bot.deposit_config import default_dedi_item, default_vault_item
from source.launcher.constants import APP_NAME, ASSETS
from source.launcher.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    register_shift_n_hotkey,
    unregister_hotkey,
)
from source.launcher.native_window import WindowsMSG
from source.launcher.vault_items_store import add_vault_item, load_vault_items
from source.launcher.widgets import AnimatedButton, CyberSwitch

WM_HOTKEY = 0x0312


class DepositHelperGuide(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("DepositHelperGuide")
        self.setStyleSheet(parent.styleSheet())
        self.setWindowTitle("Deposit Helper Guide")
        self.setModal(False)
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)

        shell = QFrame()
        shell.setObjectName("DepositHelperWindow")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("HELPER GUIDE")
        title.setObjectName("HelperTitle")
        close = AnimatedButton("X", "danger")
        close.setObjectName("HelperIconButton")
        close.setFixedHeight(30)
        close.setMinimumWidth(36)
        close.clicked.connect(self.close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close)
        layout.addLayout(header)

        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(ASSETS["welcome"])
        if pixmap.isNull():
            pixmap = QPixmap(ASSETS["logo"])
        if not pixmap.isNull():
            image.setPixmap(
                pixmap.scaled(320, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        layout.addWidget(image)

        body = QLabel(
            "1. Lay in the Gacha render bed.\n"
            "2. Get out and teleport to the desired teleporter.\n"
            "3. Aim at the dedi, vault, or grinder until the in-game deposit/access prompt is visible.\n"
            "4. Use the helper capture button to save yaw and pitch."
        )
        body.setObjectName("MutedCopy")
        body.setWordWrap(True)
        layout.addWidget(body)

        self.resize(380, 320)


class DepositRouteHelper(QWidget):
    def __init__(self, owner, route_kind, route_index):
        super().__init__(None)
        self.owner = owner
        self.route_kind = route_kind
        self.route_index = route_index
        self.selected = None
        self.row_widgets = []
        self.guide = None
        self.drag_position = None
        self.hotkey_id = (id(self) & 0x3FFF) + 1
        self.hotkey_registered = False

        self.setObjectName("DepositHelperWindow")
        self.setStyleSheet(owner.styleSheet())
        self.setWindowTitle(f"{APP_NAME} Route Helper")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(460, 640)
        self._build_ui()
        self._position_top_right()
        self._register_hotkey()
        QTimer.singleShot(0, self.show_guide)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(10, 8, 10, 8)
        header.setSpacing(8)
        self.header_title = QLabel(self._title())
        self.header_title.setObjectName("HelperTitle")
        self.header_title.setWordWrap(True)
        self.header_title.installEventFilter(self)
        guide = self._icon_button("?", "Open guide book")
        guide.clicked.connect(self.show_guide)
        close = self._icon_button("X", "Close helper", "danger")
        close.clicked.connect(self.close)
        header.addWidget(self.header_title)
        header.addStretch()
        header.addWidget(guide)
        header.addWidget(close)
        root.addWidget(self.header_frame)

        self.hotkey_label = QLabel("SHIFT + N focuses this helper")
        self.hotkey_label.setObjectName("HelperHint")
        root.addWidget(self.hotkey_label)

        toolbar = QFrame()
        toolbar.setObjectName("HelperToolbar")
        actions = QHBoxLayout(toolbar)
        actions.setContentsMargins(8, 8, 8, 8)
        actions.setSpacing(8)
        if self.route_kind == "crystal":
            add_dedi = self._icon_button("+D", "Add dedi row")
            add_dedi.clicked.connect(lambda: self.add_entry("dedi"))
            add_vault = self._icon_button("+V", "Add vault row")
            add_vault.clicked.connect(lambda: self.add_entry("vault"))
            cap_dedi = self._icon_button("CD", "Capture selected row or add a dedi")
            cap_dedi.clicked.connect(lambda: self.capture("dedi"))
            cap_vault = self._icon_button("CV", "Capture selected row or add a vault")
            cap_vault.clicked.connect(lambda: self.capture("vault"))
            for button in (add_dedi, add_vault, cap_dedi, cap_vault):
                actions.addWidget(button)
        else:
            cap_grinder = self._icon_button("CG", "Capture grinder")
            cap_grinder.clicked.connect(lambda: self.capture("grinder"))
            add_dedi = self._icon_button("+D", "Add dedi row")
            add_dedi.clicked.connect(lambda: self.add_entry("dedi"))
            cap_dedi = self._icon_button("CD", "Capture selected row or add a dedi")
            cap_dedi.clicked.connect(lambda: self.capture("dedi"))
            for button in (cap_grinder, add_dedi, cap_dedi):
                actions.addWidget(button)
        actions.addStretch()
        root.addWidget(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("HelperScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("HelperScrollContent")
        self.rows_layout = QVBoxLayout(self.scroll_content)
        self.rows_layout.setContentsMargins(0, 0, 4, 0)
        self.rows_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content)
        root.addWidget(self.scroll, 1)

        self.status = QLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        root.addWidget(self.status)
        self.refresh_rows()

    def _title(self):
        prefix = "CRYSTAL" if self.route_kind == "crystal" else "GRINDABLE"
        route = self.route()
        teleport = route.get("teleport", "")
        return f"{prefix} HELPER {self.route_index + 1}: {teleport or 'NO TELEPORT'}"

    def _position_top_right(self):
        screen = self.screen()
        if screen is None and self.owner:
            screen = self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.right() - self.width() - 18, rect.top() + 18)

    def _register_hotkey(self):
        if not hasattr(ctypes, "windll"):
            self.hotkey_label.setText("SHIFT + N focus hotkey unavailable here")
            return
        hwnd = int(self.winId())
        try:
            self.hotkey_registered = register_shift_n_hotkey(hwnd, self.hotkey_id)
        except Exception:
            self.hotkey_registered = False
        if not self.hotkey_registered:
            self.hotkey_label.setText("SHIFT + N focus hotkey unavailable")

    def nativeEvent(self, event_type, message):
        if not self.hotkey_registered:
            return super().nativeEvent(event_type, message)
        msg = WindowsMSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
            self.raise_()
            self.activateWindow()
            return True, 0
        return super().nativeEvent(event_type, message)

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
            event.accept()
            return True
        if (
            event.type() == QEvent.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self.drag_position = None
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        if self.hotkey_registered and hasattr(ctypes, "windll"):
            try:
                unregister_hotkey(int(self.winId()), self.hotkey_id)
            except Exception:
                pass
        if self.guide is not None:
            self.guide.close()
        if self.owner is not None and hasattr(self.owner, "forget_deposit_helper"):
            self.owner.forget_deposit_helper(self)
        super().closeEvent(event)

    def show_guide(self):
        if self.guide is None:
            self.guide = DepositHelperGuide(self)
        self.guide.show()
        self.guide.raise_()
        self.guide.activateWindow()

    def route(self):
        key = (
            "depositCrystalData"
            if self.route_kind == "crystal"
            else "depositGrindableData"
        )
        return self.owner.deposit_config[key][self.route_index]

    def refresh_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.row_widgets = []

        route = self.route()
        if self.route_kind == "crystal":
            self._add_section_label("DEDIS")
            for index, entry in enumerate(route["dedi"]["items"]):
                self._add_row("dedi", index, entry)
            self._add_section_label("VAULTS")
            for index, entry in enumerate(route["vault"]["items"]):
                self._add_row("vault", index, entry)
        else:
            self._add_section_label("GRINDER")
            self._add_row("grinder", 0, route["grinder"])
            self._add_section_label("DEDIS")
            for index, entry in enumerate(route["dedi"]["items"]):
                self._add_row("dedi", index, entry)
        self.rows_layout.addStretch()

    def _add_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("HelperSectionLabel")
        self.rows_layout.addWidget(label)

    def _add_row(self, kind, index, entry):
        row = CollapsibleHelperRow(self, kind, index, entry)
        self.row_widgets.append(row)
        self.rows_layout.addWidget(row)

    def add_entry(self, kind):
        route = self.route()
        if kind == "dedi":
            if self.route_kind == "crystal":
                route["dedi"]["items"].append(default_dedi_item())
                index = len(route["dedi"]["items"]) - 1
            else:
                route["dedi"]["items"].append(default_dedi_item())
                index = len(route["dedi"]["items"]) - 1
            self.selected = ("dedi", index)
        elif kind == "vault":
            route["vault"]["items"].append(default_vault_item())
            index = len(route["vault"]["items"]) - 1
            self.selected = ("vault", index)
        self.save_and_refresh()

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
        self.selected = None
        self.save_and_refresh()

    def select_entry(self, kind, index):
        self.selected = (kind, index)
        for row in self.row_widgets:
            row.sync_selected()

    def capture(self, default_kind):
        kind, index = self._capture_target(default_kind)
        entry = self._entry(kind, index)
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
            return
        entry["location"]["yaw"] = yaw
        entry["location"]["pitch"] = pitch
        self.status.setText(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")
        self.save_and_refresh()

    def _capture_target(self, default_kind):
        if self.selected is not None:
            kind, index = self.selected
            if self._kind_allowed(kind):
                return kind, index
        if default_kind == "grinder":
            self.selected = ("grinder", 0)
            return "grinder", 0
        self.add_entry(default_kind)
        return self.selected

    def _kind_allowed(self, kind):
        if self.route_kind == "crystal":
            return kind in ("dedi", "vault")
        return kind in ("dedi", "grinder")

    def _entry(self, kind, index):
        route = self.route()
        if kind == "dedi":
            return route["dedi"]["items"][index]
        if kind == "vault":
            return route["vault"]["items"][index]
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
        self.save_and_refresh()

    def remove_vault_item_row(self, vault, index):
        if 0 <= index < len(vault["items"]):
            del vault["items"][index]
        self.save_and_refresh()

    def save(self):
        if self.owner.save_deposit_routes(show_log=False):
            self.status.setText("Saved.")
            return True
        self.status.setText("Save failed.")
        return False

    def save_and_refresh(self):
        if self.save():
            self.refresh_rows()
            self.owner._render_settings_group("DEPOSIT ROUTES")

    def _icon_button(self, text, tooltip, type="secondary"):
        button = AnimatedButton(text, type)
        button.setObjectName("HelperIconButton")
        button.setToolTip(tooltip)
        # button.setFixedSize(38, 30)
        return button


class CollapsibleHelperRow(QFrame):
    def __init__(self, helper, kind, index, entry):
        super().__init__(helper)
        self.helper = helper
        self.kind = kind
        self.index = index
        self.entry = entry
        self.expanded = False
        self.setObjectName("HelperRow")
        self._build()
        self.sync_selected()

    def _build(self):
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.expand_button = self.helper._icon_button(">", "Expand or collapse row")
        self.expand_button.clicked.connect(self.toggle)
        self.summary = QLabel(self._summary_text())
        self.summary.setObjectName("HelperRowSummary")
        self.summary.setWordWrap(True)
        select = self.helper._icon_button("*", "Select row")
        select.clicked.connect(lambda: self.helper.select_entry(self.kind, self.index))
        capture = self.helper._icon_button("C", "Capture yaw and pitch")
        capture.clicked.connect(self.capture_row)
        delete = self.helper._icon_button("-", "Delete row", "danger")
        delete.clicked.connect(lambda: self.helper.delete_entry(self.kind, self.index))
        top.addWidget(self.expand_button)
        top.addWidget(self.summary, 1)
        top.addWidget(select)
        top.addWidget(capture)
        top.addWidget(delete)
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
        crouched = CyberSwitch("CROUCHED")
        crouched.blockSignals(True)
        crouched.setChecked(bool(self.entry.get("crouched", False)))
        crouched.blockSignals(False)
        crouched.toggled.connect(
            lambda checked: self.helper.update_crouched(self.entry, checked)
        )
        switches.addWidget(crouched)
        if self.kind == "grinder":
            active = CyberSwitch("ACTIVE")
            active.blockSignals(True)
            active.setChecked(bool(self.entry.get("active", False)))
            active.blockSignals(False)
            active.toggled.connect(
                lambda checked: self.helper.update_active(self.entry, checked)
            )
            switches.addWidget(active)
        switches.addStretch()
        detail.addLayout(switches)

        if self.kind == "vault":
            self._add_vault_items(detail)

        self.details.setVisible(False)
        self.root.addWidget(self.details)

    def _add_float_field(self, layout, key):
        label = QLabel(key)
        label.setObjectName("FormLabel")
        field = QLineEdit(str(self.entry["location"].get(key, 0.0)))
        field.setObjectName("SettingField")
        field.setMinimumWidth(86)
        field.editingFinished.connect(
            lambda entry=self.entry, name=key, editor=field: self.helper.update_float(
                entry, name, editor
            )
        )
        field.returnPressed.connect(
            lambda entry=self.entry, name=key, editor=field: self.helper.update_float(
                entry, name, editor
            )
        )
        layout.addWidget(label)
        layout.addWidget(field)

    def _add_vault_items(self, layout):
        items = self.entry.setdefault("items", [])
        for item_index, value in enumerate(items):
            row = QHBoxLayout()
            label = QLabel(f"item {item_index + 1}")
            label.setObjectName("FormLabel")
            combo = QComboBox()
            combo.setObjectName("HelperCombo")
            combo.setEditable(True)
            options = load_vault_items(self.helper.owner.deposit_config)
            combo.addItems(options)
            if value and value not in options:
                combo.addItem(value)
            combo.setCurrentText(value)
            combo.activated.connect(
                lambda selected_index, vault=self.entry, index=item_index, widget=combo: self.helper.update_vault_item(
                    vault, index, widget
                )
            )
            if combo.lineEdit() is not None:
                combo.lineEdit().editingFinished.connect(
                    lambda vault=self.entry, index=item_index, widget=combo: self.helper.update_vault_item(
                        vault, index, widget
                    )
                )
            remove = self.helper._icon_button("-", "Remove this vault item")
            remove.clicked.connect(
                lambda checked=False, vault=self.entry, index=item_index: self.helper.remove_vault_item_row(
                    vault, index
                )
            )
            row.addWidget(label)
            row.addWidget(combo, 1)
            row.addWidget(remove)
            layout.addLayout(row)
        add = self.helper._icon_button("+", "Add vault item")
        add.clicked.connect(lambda: self.helper.add_vault_item_row(self.entry))
        layout.addWidget(add, alignment=Qt.AlignRight)

    def toggle(self):
        self.expanded = not self.expanded
        self.details.setVisible(self.expanded)
        self.expand_button.setText("v" if self.expanded else ">")

    def capture_row(self):
        self.helper.select_entry(self.kind, self.index)
        self.helper.capture(self.kind)

    def sync_selected(self):
        selected = self.helper.selected == (self.kind, self.index)
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _summary_text(self):
        location = self.entry.get("location", {})
        yaw = location.get("yaw", 0.0)
        pitch = location.get("pitch", 0.0)
        suffix = " crouched" if self.entry.get("crouched", False) else ""
        if self.kind == "grinder":
            active = " active" if self.entry.get("active", False) else ""
            return f"GRINDER   yaw {yaw}   pitch {pitch}{suffix}{active}"
        return (
            f"{self.kind.upper()} {self.index + 1}   "
            f"yaw {yaw}   pitch {pitch}{suffix}"
        )
