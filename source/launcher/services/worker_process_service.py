import os
import subprocess
import sys
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

from source.launcher.helper_runner import RESULT_PREFIX, STATUS_PREFIX
from source.launcher.process_control import terminate_process_tree


class WorkerProcessService(QObject):
    runningChanged = Signal()
    statusChanged = Signal(str)
    outputLine = Signal(str)
    finished = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._reader_stop = threading.Event()
        self._reader_thread = None
        self._result_message = ""
        self._finished = False
        self._finish_lock = threading.Lock()

    @Property(bool, notify=runningChanged)
    def isRunning(self):
        return self._process is not None and self._process.poll() is None

    @Slot(str, "QVariantList")
    def start(self, kind, args=None):
        if self._process is not None:
            return
        args = [str(value) for value in (args or [])]
        self._reader_stop = threading.Event()
        self._result_message = ""
        self._finished = False
        try:
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "source.launcher.helper_runner",
                    kind,
                    *args,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd(),
            )
        except Exception as exc:
            message = f"Failed: {exc}"
            self.statusChanged.emit(message)
            self.finished.emit(message)
            return
        self._reader_thread = threading.Thread(
            target=self._read_output, args=(self._process,), daemon=True
        )
        self._reader_thread.start()
        self.runningChanged.emit()

    @Slot()
    def stop(self):
        if not self.isRunning:
            return
        terminate_process_tree(self._process)
        self._finish("Stopped.")

    def _read_output(self, process):
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            if self._reader_stop.is_set():
                break
            self._handle_line(line.rstrip())
        if not self._reader_stop.is_set():
            message = self._result_message
            if not message:
                return_code = process.poll()
                message = (
                    "Finished."
                    if return_code == 0
                    else f"Failed: helper exited with code {return_code}."
                )
            self._finish(message)

    def _handle_line(self, line):
        if line.startswith(STATUS_PREFIX):
            self.statusChanged.emit(line[len(STATUS_PREFIX) :])
            return
        if line.startswith(RESULT_PREFIX):
            self._result_message = line[len(RESULT_PREFIX) :]
            return
        if line:
            self.outputLine.emit(line)
            self.statusChanged.emit(line)

    def _finish(self, message):
        with self._finish_lock:
            if self._finished:
                return
            self._finished = True
        self._close_reader()
        self._process = None
        self.runningChanged.emit()
        self.finished.emit(message)

    def _close_reader(self):
        self._reader_stop.set()
        process = self._process
        if process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except (OSError, ValueError):
                pass
        thread = self._reader_thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=1)
        self._reader_thread = None
