import contextlib
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.widgets import (
    AnimatedButton,
    ChromeIconButton,
    RoundedShellFrame,
    sync_rounded_window_mask,
)
from source.launcher.config.constants import (
    ASSETS,
    GACHA_LOG_FILE,
    MINIMAL_HELPER_RUNNING_WIDTH,
    TITLE_BAR_HEIGHT,
    UI_METRICS,
)
from source.launcher.runner_overlay import (
    HelperRunnerOverlay,
    _format_runner_log_line,
)
from source.launcher.utils.deposit_helper_capture import (
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.utils.native_window import WM_HOTKEY, WindowsMSG
from source.launcher.utils.process_control import terminate_process_tree
from source.logs import gachalogs as logs
from source.utility.runner_state import RUNNER_STATE_PREFIX
from source.utility.utils_simple import start_subprocess

HELPER_COMPLETION_PREFIX = "__HELPER_COMPLETION__ "
HELPER_READY_MESSAGE = "__HELPER_READY__"


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
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(width, height)
        self.setFixedWidth(width)
        self.setMinimumHeight(height)
        self._build_shell(title)
        self._position_helper(position)

    def _build_shell(self, title):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = RoundedShellFrame()
        shell.setObjectName("DepositHelperWindow")
        root.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.shell_layout = shell_layout

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(8, 0, 0, 0)
        self.header_layout.setSpacing(0)
        self.header_title = QLabel(title)
        self.header_title.setObjectName("HelperTitle")
        self.header_title.setWordWrap(False)
        self.header_title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.header_title.installEventFilter(self)
        self._header_title_full_text = title
        self.header_layout.addWidget(self.header_title, 1)

        self.close_button = ChromeIconButton("close")
        self.close_button.setToolTip("Close helper")
        self.close_button.clicked.connect(self.close)
        self.header_layout.addWidget(self.close_button)
        shell_layout.addWidget(self.header_frame)

        body = QWidget()
        body.setObjectName("HelperBody")
        self.content_layout = QVBoxLayout(body)
        padding = UI_METRICS["helper_padding"]
        self.content_layout.setContentsMargins(padding, 0, padding, padding)
        self.content_layout.setSpacing(8)
        shell_layout.addWidget(body)

        self.hotkey_label = QLabel(self.hotkey_hint)
        self.hotkey_label.setObjectName("HelperHint")
        self.content_layout.addWidget(self.hotkey_label)
        self._sync_header_title()

    def add_header_action(self, button):
        self.header_layout.insertWidget(self.header_layout.count() - 1, button)

    def set_header_title(self, title):
        self._header_title_full_text = title
        self.setWindowTitle(title)
        self._sync_header_title()

    def _sync_header_title(self):
        title = getattr(self, "_header_title_full_text", "")
        width = max(40, self.header_title.width())
        self.header_title.setToolTip(title)
        self.header_title.setText(
            self.header_title.fontMetrics().elidedText(
                title, Qt.TextElideMode.ElideRight, width
            )
        )

    def _titlebar_button(self, text, tooltip):
        button = AnimatedButton(text, "chrome")
        button.setObjectName("ChromeIconButton")
        button.setFixedSize(46, TITLE_BAR_HEIGHT - 1)
        button.setToolTip(tooltip)
        return button

    def _helper_button(self, text, tooltip, variant="secondary"):
        button = AnimatedButton(text, variant)
        button.setObjectName("HelperIconButton")
        button.setToolTip(tooltip)
        return button

    def _helper_action_button(self, icon_key, tooltip, variant="secondary"):
        button = self._helper_button("", tooltip, variant)
        button.setIcon(QIcon(ASSETS[icon_key]))
        button.setIconSize(QSize(24, 24))
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
        with contextlib.suppress(Exception):
            self.unregister_hotkey_func(int(self.winId()), self.hotkey_id)
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
        self.shell_layout.invalidate()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.invalidate()
            root_layout.activate()
        self.shell_layout.activate()
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
        self._sync_rounded_mask()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_header_title()
        self._sync_rounded_mask()

    def _sync_rounded_mask(self):
        sync_rounded_window_mask(self, UI_METRICS["window_radius"])

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
        if event.type() == QEvent.Type.ActivationChange:
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
    worker_result_ready = Signal(object, str)
    helper_log_changed = Signal()
    helper_ready = Signal()
    runner_state_changed = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker_process = None
        self.worker_result_ready.connect(self._dispatch_worker_result)
        self.worker_stopping = False
        self.worker_launch_pending = False
        self.worker_stop_deadline = None
        self.output_reader_stop = threading.Event()
        self.output_reader_thread = None
        self.worker_result_message = None
        self.worker_debug_lines = []
        self.running_widgets = []
        self.running_ui_active = False
        self.running_hotkey_hint = "ALT + N stops this helper"
        self.helper_log_lines = []
        self.helper_log_file_position = 0
        self.helper_log_overlay = None
        self.runner_state = "RUNNING"
        self.auto_keys_suspension_active = False
        self.helper_log_timer = QTimer(self)
        self.helper_log_timer.timeout.connect(self._poll_helper_log_file)
        self.helper_log_changed.connect(self._refresh_helper_log_overlay)
        self.helper_ready.connect(self._finish_helper_loading)
        self.runner_state_changed.connect(self._refresh_helper_overlay_for_runner_state)

    def register_minimal_running_widgets(self, *widgets):
        self.running_widgets.extend(widgets)

    def toggle(self):
        if self.is_running() or self.worker_launch_pending:
            self.stop()
        else:
            self.start()

    def is_running(self):
        return self.worker_process is not None and self.worker_process.poll() is None

    def handle_hotkey(self):
        self.toggle()

    def _start_worker(self, *runner_args):
        if self.closing or getattr(self.owner, "shutdown_started", False):
            self.worker_launch_pending = False
            self._release_auto_keys_suspension()
            return
        suspend_auto_keys = getattr(
            self.owner, "_suspend_auto_keys_for_automation", None
        )
        if callable(suspend_auto_keys) and not self.auto_keys_suspension_active:
            suspend_auto_keys(self)
            self.auto_keys_suspension_active = True
        runtime = getattr(self.owner, "auto_keys_runtime", None)
        if getattr(runtime, "cleanup_pending", False) is True:
            self.worker_launch_pending = True
            self._set_running_ui(True)

            def retry():
                """Launch only while this helper still owns its suspension."""
                if self.worker_launch_pending and self.auto_keys_suspension_active:
                    self._start_worker(*runner_args)

            QTimer.singleShot(20, self, retry)
            return
        self.helper_log_lines = []
        self.worker_launch_pending = False
        self.helper_log_file_position = self._helper_log_file_size()
        self._set_runner_state("RUNNING")
        self._set_running_ui(True)
        self.worker_stopping = False
        self.worker_stop_deadline = None
        self.worker_result_message = None
        self.worker_debug_lines = []
        self.output_reader_stop = threading.Event()
        try:
            self.worker_process = start_subprocess(
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "source.launcher.components.helper_runner",
                    *runner_args,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd(),
            )
        except Exception:
            self._release_auto_keys_suspension()
            raise
        try:
            self.output_reader_thread = threading.Thread(
                target=self._read_worker_output,
                args=(self.worker_process,),
                daemon=True,
            )
            self.output_reader_thread.start()
            self.helper_log_timer.start(250)
        except Exception:
            process = self.worker_process
            if process is not None and process.poll() is None:
                with contextlib.suppress(Exception):
                    terminate_process_tree(process)
            self._close_output_reader(process)
            self.worker_process = None
            self.helper_log_timer.stop()
            self._release_auto_keys_suspension()
            raise

    def _read_worker_output(self, process):
        if process is None or process.stdout is None:
            return
        stop_event = self.output_reader_stop
        for line in process.stdout:
            if stop_event.is_set() or process is not self.worker_process:
                break
            self._handle_worker_output(line.rstrip())
        if not stop_event.is_set() and process is self.worker_process:
            message = self.worker_result_message
            if not message:
                return_code = process.poll()
                if return_code is None:
                    try:
                        return_code = process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        return_code = "unknown"
                if self.worker_stopping:
                    message = "Stopped."
                elif return_code == 0:
                    message = "Finished."
                else:
                    message = f"Failed: helper exited with code {return_code}."
            self._log_worker_debug_output(message)
            self.worker_result_ready.emit(process, message)

    def _dispatch_worker_result(self, process: subprocess.Popen, message: str):
        """Deliver completion only to the operation that owns this process."""
        if process is self.worker_process:
            self._emit_worker_finished(message)

    def _handle_worker_output(self, line: str):
        if line == HELPER_READY_MESSAGE:
            self._emit_worker_ready()
            return
        if line.startswith(HELPER_COMPLETION_PREFIX):
            self.worker_result_message = line[len(HELPER_COMPLETION_PREFIX) :]
            return
        if line.startswith(RUNNER_STATE_PREFIX):
            try:
                state = json.loads(line[len(RUNNER_STATE_PREFIX) :]).get("state")
            except (json.JSONDecodeError, AttributeError):
                return
            if state in {"RUNNING", "PAUSED"}:
                self._set_runner_state(state)
            return
        if line:
            self.worker_debug_lines.append(line)

    def _log_worker_debug_output(self, result_message: str):
        """Write unstructured worker output as one traceback-style log entry."""
        if not result_message.startswith("Failed:") or not self.worker_debug_lines:
            return
        logs.logger.error(
            "Helper worker failed: %s\n%s",
            result_message,
            "\n".join(self.worker_debug_lines),
        )

    @staticmethod
    def _helper_log_file_size():
        try:
            return os.path.getsize(GACHA_LOG_FILE)
        except OSError:
            return 0

    def _poll_helper_log_file(self):
        try:
            file_size = os.path.getsize(GACHA_LOG_FILE)
            if file_size < self.helper_log_file_position:
                self.helper_log_file_position = 0
            with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as file:
                file.seek(self.helper_log_file_position)
                lines = file.readlines()
                self.helper_log_file_position = file.tell()
        except (OSError, ValueError):
            return

        changed = False
        for line in lines:
            message = _format_runner_log_line(line)
            if message is None:
                continue
            self.helper_log_lines.append(line.rstrip())
            changed = True
        if changed:
            self.helper_log_lines = self.helper_log_lines[-2000:]
            self.helper_log_changed.emit()

    def _refresh_helper_log_overlay(self):
        overlay = self.helper_log_overlay
        if overlay is None or overlay.loading_active:
            return
        try:
            overlay.refresh(
                {"running": [], "active": [], "waiting": []}, self.helper_log_lines
            )
        except RuntimeError:
            self.helper_log_overlay = None

    def _refresh_helper_overlay_for_runner_state(self, _state: str):
        """Refresh the generic helper overlay after a worker state change."""
        self._refresh_helper_log_overlay()

    def _set_runner_state(self, state: str):
        """Store a valid worker state and publish it to the helper UI."""
        if self.runner_state == state:
            return
        self.runner_state = state
        self.runner_state_changed.emit(state)

    def _emit_worker_ready(self):
        """Forward worker readiness through a Qt signal when supported."""
        self.helper_ready.emit()
        signal = getattr(self, "worker_ready", None)
        if signal is not None:
            signal.emit()

    def _finish_helper_loading(self):
        """Switch the generic helper overlay from loading to file-backed logs."""
        overlay = self.helper_log_overlay
        if overlay is None:
            return
        try:
            overlay.refresh(
                {"running": [], "active": [], "waiting": []}, self.helper_log_lines
            )
        except RuntimeError:
            self.helper_log_overlay = None

    def _emit_worker_finished(self, message):
        signal = getattr(self, "worker_finished", None)
        if signal is not None:
            signal.emit(message)

    def _finish_worker(self):
        self.worker_launch_pending = False
        process = self.worker_process
        self._close_output_reader(process)
        self.helper_log_timer.stop()
        overlay = self.helper_log_overlay
        self.helper_log_overlay = None
        if overlay is not None:
            overlay.close()
        self.worker_process = None
        self._set_runner_state("RUNNING")
        self.worker_stopping = False
        self.worker_stop_deadline = None
        self._release_auto_keys_suspension()
        if self.closing:
            self.close()
            return True
        self._set_running_ui(False)
        return False

    def _release_auto_keys_suspension(self):
        """Release this helper's temporary Auto Keys suspension once."""
        if not self.auto_keys_suspension_active:
            return
        self.auto_keys_suspension_active = False
        resume_auto_keys = getattr(
            self.owner, "_resume_auto_keys_after_automation", None
        )
        if callable(resume_auto_keys):
            resume_auto_keys(self)

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
            if self.helper_log_overlay is None:
                self.helper_log_overlay = HelperRunnerOverlay(self)
            self.helper_log_overlay.stop_button.setText("STOP")
            self.helper_log_overlay.stop_button.set_variant("danger")
            self.helper_log_overlay.stop_button.setEnabled(True)
            self.helper_log_overlay.refresh_loading(self.helper_log_lines)
            self.hide()
            self.helper_log_overlay.show()
            self.helper_log_overlay.raise_()
        else:
            self.setMaximumHeight(16777215)
            self.setFixedWidth(self.idle_width)
            self.setMinimumHeight(self.idle_min_height)
            for widget in self.running_widgets:
                widget.setVisible(True)
            self.hotkey_label.setText(self.hotkey_hint)
            self.resize(self.idle_width, self._idle_content_height())
            self.running_ui_active = False
            self.show()
            self.raise_()
            self.activateWindow()
        self._position_middle_right()

    def stop(self):
        if self.worker_launch_pending:
            self.worker_launch_pending = False
            self._release_auto_keys_suspension()
            self._set_running_ui(False)
            return
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
            with contextlib.suppress(OSError, ValueError):
                process.stdout.close()
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
        if self.worker_launch_pending:
            self.stop()
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
