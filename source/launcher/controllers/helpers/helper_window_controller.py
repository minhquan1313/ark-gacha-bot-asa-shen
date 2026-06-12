import ctypes

from PySide6.QtCore import Property, QAbstractNativeEventFilter, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from source.launcher.deposit_helper_capture import (
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.native_window import WM_HOTKEY, WindowsMSG


class HelperHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def nativeEventFilter(self, event_type, message):
        if not self.controller.hotkeyRegistered:
            return False, 0
        msg = WindowsMSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.controller.hotkeyId:
            self.controller.handleHotkey()
            return True, 0
        return False, 0


class HelperWindowController(QObject):
    VALID_HELPERS = {"autoJoin", "fertilizer", "transfer", "deposit", "position"}
    TOGGLE_HELPERS = {"autoJoin", "fertilizer", "transfer"}

    changed = Signal()
    helperRequested = Signal(str, "QVariant")
    closeRequested = Signal()
    focusRequested = Signal()
    toggleRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_helper_name = ""
        self._active_helper_can_toggle = False
        self._hotkey_id = (id(self) & 0x3FFF) + 0x8000
        self._hotkey_registered = False
        self._root_window = None
        self._hotkey_filter = HelperHotkeyFilter(self)

    @Property(str, notify=changed)
    def activeHelperName(self):
        return self._active_helper_name

    @Property(int, notify=changed)
    def hotkeyId(self):
        return self._hotkey_id

    @Property(bool, notify=changed)
    def hotkeyRegistered(self):
        return self._hotkey_registered

    @Slot(str)
    @Slot(str, "QVariant")
    def openHelper(self, name, payload=None):
        name = str(name)
        if name not in self.VALID_HELPERS:
            return
        if self._active_helper_name:
            self.closeRequested.emit()
        self._active_helper_name = name
        self._active_helper_can_toggle = self._active_helper_name in self.TOGGLE_HELPERS
        self.changed.emit()
        self.helperRequested.emit(self._active_helper_name, payload or {})

    @Slot()
    def closeActiveHelper(self):
        if not self._active_helper_name:
            return
        self.closeRequested.emit()
        self._active_helper_name = ""
        self._active_helper_can_toggle = False
        self.changed.emit()

    @Slot(str)
    def markClosed(self, name):
        if self._active_helper_name == name:
            self._active_helper_name = ""
            self._active_helper_can_toggle = False
            self.changed.emit()

    @Slot(QObject)
    def registerWindow(self, window):
        self._root_window = window
        self._register_hotkey(window)

    @Slot()
    def shutdown(self):
        self._unregister_hotkey()

    @Slot()
    def handleHotkey(self):
        if not self._active_helper_name:
            return
        if self._active_helper_can_toggle:
            self.toggleRequested.emit(self._active_helper_name)
        else:
            self.focusRequested.emit()

    def _register_hotkey(self, window):
        if self._hotkey_registered or not hasattr(ctypes, "windll") or window is None:
            return
        try:
            hwnd = int(window.winId())
            self._hotkey_registered = register_alt_n_hotkey(hwnd, self._hotkey_id)
            app = QGuiApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._hotkey_filter)
        except Exception:
            self._hotkey_registered = False
        self.changed.emit()

    def _unregister_hotkey(self):
        if not self._hotkey_registered or not hasattr(ctypes, "windll"):
            self._hotkey_registered = False
            return
        try:
            if self._root_window is not None:
                unregister_hotkey(int(self._root_window.winId()), self._hotkey_id)
            app = QGuiApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self._hotkey_filter)
        except Exception:
            pass
        self._hotkey_registered = False
        self.changed.emit()
