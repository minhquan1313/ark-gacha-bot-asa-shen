import ctypes
import os
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from source.launcher.constants import MINIMAL_HELPER_RUNNING_WIDTH
from source.launcher.deposit_helper_capture import (
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.native_window import WM_HOTKEY, WindowsMSG
from source.launcher.process_control import terminate_process_tree
from source.launcher.widgets import AnimatedButton

HELPER_STATUS_PREFIX = "__HELPER_STATUS__ "
HELPER_RESULT_PREFIX = "__HELPER_RESULT__ "


class BaseHelperWindow(QWidget):
    def __init__(
        self,
        owner,
        title,
        width,
        height,
        *,
        route_kind=None,
        route_index=None,
        position="middle_right",
        hotkey_hint="ALT + N focuses this helper",
        unavailable_hotkey_hint="ALT + N focus hotkey unavailable",
        register_hotkey_func=register_alt_n_hotkey,
        unregister_hotkey_func=unregister_hotkey,
    ):
        super().__init__(None)
        self.owner = owner
        self.route_kind = route_kind
        self.route_index = route_index
        self.drag_position = None
        self.mouse_inside = False
        self.closing = False
        self.guide = None
        self.hotkey_id = (id(self) & 0x3FFF) + 1
        self.hotkey_registered = False
        self.hotkey_hint = hotkey_hint
        self.unavailable_hotkey_hint = unavailable_hotkey_hint
        self.register_hotkey_func = register_hotkey_func
        self.unregister_hotkey_func = unregister_hotkey_func
        self.idle_width = width
        self.idle_min_height = height
        self.position = position

        self.setObjectName("DepositHelperWindow")
        self.setStyleSheet(owner.styleSheet())
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(width, height)
        self.setFixedWidth(width)
        self.setMinimumHeight(height)
        self._build_shell(title)
        self._position_helper(position)

    def _build_shell(self, title):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("DepositHelperWindow")
        root.addWidget(shell)

        self.content_layout = QVBoxLayout(shell)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(8)
        self.header_title = QLabel(title)
        self.header_title.setObjectName("HelperTitle")
        self.header_title.installEventFilter(self)
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addStretch()

        self.close_button = self._helper_button("X", "Close helper", "danger")
        self.close_button.clicked.connect(self.close)
        self.header_layout.addWidget(self.close_button)
        self.content_layout.addWidget(self.header_frame)

        self.hotkey_label = QLabel(self.hotkey_hint)
        self.hotkey_label.setObjectName("HelperHint")
        self.content_layout.addWidget(self.hotkey_label)

    def add_header_action(self, button):
        self.header_layout.insertWidget(self.header_layout.count() - 1, button)

    def _helper_button(self, text, tooltip, variant="secondary"):
        button = AnimatedButton(text, variant)
        button.setObjectName("HelperIconButton")
        button.setToolTip(tooltip)
        return button

    def _register_hotkey(self):
        if not hasattr(ctypes, "windll"):
            self.hotkey_registered = False
            self.hotkey_label.setText(f"{self.unavailable_hotkey_hint} here")
            return
        try:
            self.hotkey_registered = self.register_hotkey_func(
                int(self.winId()), self.hotkey_id
            )
        except Exception:
            self.hotkey_registered = False
        if not self.hotkey_registered:
            self.hotkey_label.setText(self.unavailable_hotkey_hint)

    def _unregister_hotkey(self):
        if not self.hotkey_registered or not hasattr(ctypes, "windll"):
            self.hotkey_registered = False
            return
        try:
            self.unregister_hotkey_func(int(self.winId()), self.hotkey_id)
        except Exception:
            pass
        self.hotkey_registered = False

    def nativeEvent(self, event_type, message):
        if self.hotkey_registered:
            msg = WindowsMSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                self.handle_hotkey()
                return True, 0
        return super().nativeEvent(event_type, message)

    def handle_hotkey(self):
        self.refocus_helper()

    def refocus_helper(self, cursor_position=None):
        if self.closing:
            return
        self.show()
        self.raise_()
        self.activateWindow()
        if cursor_position is not None and hasattr(self, "cursor_restore_timer"):
            self.pending_cursor_position = cursor_position
            self.cursor_restore_timer.start(0)

    def _require_ark_window(self, action, failure_prefix="Cannot continue"):
        if self.owner.require_ark_window(action, dialog_parent=self):
            return True
        if hasattr(self, "status"):
            self.status.setText(f"{failure_prefix}: {self.owner.last_ark_window_error}")
        return False

    def _position_helper(self, position):
        if position == "top_right":
            self._position_top_right()
        else:
            self._position_middle_right()

    def _activate_layouts(self):
        self.content_layout.invalidate()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.invalidate()
            root_layout.activate()
        self.content_layout.activate()

    def _height_for_width(self, width):
        self._activate_layouts()
        height = self.sizeHint().height()
        root_layout = self.layout()
        if root_layout is not None and root_layout.hasHeightForWidth():
            layout_height = root_layout.heightForWidth(width)
            if layout_height >= 0:
                height = max(height, layout_height)
        return height

    def _idle_content_height(self):
        return max(self.idle_min_height, self._height_for_width(self.idle_width))

    def _apply_idle_geometry(self):
        self.setFixedWidth(self.idle_width)
        self.setMinimumHeight(self.idle_min_height)
        self.setMaximumHeight(16777215)
        self.resize(self.idle_width, self._idle_content_height())

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "running_ui_active", False):
            self._apply_idle_geometry()
            self._position_helper(self.position)

    def _position_middle_right(self):
        screen = self.screen() or self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(
            rect.right() - self.width() - 18,
            rect.top() + (rect.height() - self.height()) // 2,
        )

    def _position_top_right(self):
        screen = self.screen() or self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.right() - self.width() - 18, rect.top() + 18)

    def _opacity_keep_visible(self):
        guide = getattr(self, "guide", None)
        guide_active = guide is not None and guide.isActiveWindow()
        guide_hovered = guide is not None and getattr(guide, "mouse_inside", False)
        owner_active = self.owner is not None and self.owner.isActiveWindow()
        return (
            self.mouse_inside
            or guide_hovered
            or self.isActiveWindow()
            or guide_active
            or owner_active
        )

    def sync_window_opacity(self):
        opacity = float(self.owner.settings.get("helper_inactive_opacity", 0.3))
        self.setWindowOpacity(
            1.0 if self._opacity_keep_visible() else max(0.1, min(1.0, opacity))
        )

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange:
            self.sync_window_opacity()

    def enterEvent(self, event):
        self.mouse_inside = True
        self.sync_window_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self.sync_window_opacity()
        super().leaveEvent(event)

    def eventFilter(self, watched, event):
        header_frame = getattr(self, "header_frame", None)
        header_title = getattr(self, "header_title", None)
        if watched not in (header_frame, header_title):
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

    def _before_close(self):
        pass

    def closeEvent(self, event):
        self.closing = True
        self._before_close()
        self._unregister_hotkey()
        guide = getattr(self, "guide", None)
        if guide is not None:
            guide.close()
        if self.owner is not None and hasattr(self.owner, "forget_deposit_helper"):
            self.owner.forget_deposit_helper(self)
        super().closeEvent(event)


class WorkerHelperWindow(BaseHelperWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker_process = None
        self.worker_stopping = False
        self.worker_stop_deadline = None
        self.output_reader_stop = threading.Event()
        self.output_reader_thread = None
        self.worker_result_message = None
        self.running_widgets = []
        self.running_ui_active = False
        self.running_hotkey_hint = "ALT + N stops this helper"

    def register_minimal_running_widgets(self, *widgets):
        self.running_widgets.extend(widgets)

    def toggle(self):
        if self.is_running():
            self.stop()
        else:
            self.start()

    def is_running(self):
        return self.worker_process is not None and self.worker_process.poll() is None

    def handle_hotkey(self):
        self.toggle()

    def _start_worker(self, *runner_args):
        self._set_running_ui(True)
        self.worker_stopping = False
        self.worker_stop_deadline = None
        self.worker_result_message = None
        self.output_reader_stop = threading.Event()
        self.worker_process = subprocess.Popen(
            [sys.executable, "-u", "-m", "source.launcher.helper_runner", *runner_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd(),
        )
        self.output_reader_thread = threading.Thread(
            target=self._read_worker_output, args=(self.worker_process,), daemon=True
        )
        self.output_reader_thread.start()

    def _read_worker_output(self, process):
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            if self.output_reader_stop.is_set():
                break
            self._handle_worker_output(line.rstrip())
        if not self.output_reader_stop.is_set():
            message = self.worker_result_message
            if not message:
                return_code = process.poll()
                if self.worker_stopping:
                    message = "Stopped."
                elif return_code == 0:
                    message = "Finished."
                else:
                    message = f"Failed: helper exited with code {return_code}."
            self._emit_worker_finished(message)

    def _handle_worker_output(self, line):
        if line.startswith(HELPER_STATUS_PREFIX):
            self._emit_status(line[len(HELPER_STATUS_PREFIX) :])
            return
        if line.startswith(HELPER_RESULT_PREFIX):
            self.worker_result_message = line[len(HELPER_RESULT_PREFIX) :]
            return
        if line:
            self._emit_status(line)

    def _emit_status(self, message):
        signal = getattr(self, "status_changed", None)
        if signal is not None:
            signal.emit(message)
        elif hasattr(self, "status"):
            self.status.setText(message)

    def _emit_worker_finished(self, message):
        signal = getattr(self, "worker_finished", None)
        if signal is not None:
            signal.emit(message)

    def _finish_worker(self):
        process = self.worker_process
        self._close_output_reader(process)
        self.worker_process = None
        self.worker_stopping = False
        self.worker_stop_deadline = None
        if self.closing:
            self.close()
            return True
        self._set_running_ui(False)
        return False

    def _set_running_ui(self, running):
        if running:
            self.running_ui_active = True
            for widget in self.running_widgets:
                widget.setVisible(False)
            self.hotkey_label.setText(self.running_hotkey_hint)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setFixedWidth(MINIMAL_HELPER_RUNNING_WIDTH)
            compact_height = self._height_for_width(MINIMAL_HELPER_RUNNING_WIDTH)
            self.setFixedHeight(compact_height)
            self.resize(MINIMAL_HELPER_RUNNING_WIDTH, compact_height)
        else:
            self.setMaximumHeight(16777215)
            self.setFixedWidth(self.idle_width)
            self.setMinimumHeight(self.idle_min_height)
            for widget in self.running_widgets:
                widget.setVisible(True)
            self.hotkey_label.setText(self.hotkey_hint)
            self.resize(self.idle_width, self._idle_content_height())
            self.running_ui_active = False
        self._position_middle_right()

    def stop(self):
        if self.is_running():
            self.worker_stopping = True
            self.worker_stop_deadline = time.time() + 5
            if hasattr(self, "status"):
                self.status.setText("Stopping...")
            terminate_process_tree(self.worker_process)
            self._emit_worker_finished("Stopped.")

    def _close_output_reader(self, process):
        self.output_reader_stop.set()
        if process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except (OSError, ValueError):
                pass
        thread = self.output_reader_thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=1)
        self.output_reader_thread = None

    def closeEvent(self, event):
        self.closing = True
        process = self.worker_process
        if process is not None and process.poll() is None:
            self.stop()
            if hasattr(self, "status"):
                self.status.setText("Stopping...")
            if hasattr(self, "start_stop_button"):
                self.start_stop_button.setEnabled(False)
            event.ignore()
            return
        super().closeEvent(event)
