import io
import sys
import time
import unittest
from unittest.mock import Mock, patch

from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from source.launcher.helper_runner import RESULT_PREFIX, STATUS_PREFIX
from source.launcher.services.worker_process_service import WorkerProcessService


class FakeProcess:
    def __init__(self, output="", return_code=0, running=False):
        self.stdout = io.StringIO(output)
        self.return_code = return_code
        self.running = running

    def poll(self):
        return None if self.running else self.return_code


class WorkerProcessServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, predicate, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents()
        return predicate()

    def test_start_builds_helper_runner_command_and_parses_output(self):
        process = FakeProcess(
            "\n".join(
                [
                    f"{STATUS_PREFIX}Working",
                    "plain output",
                    f"{RESULT_PREFIX}Done",
                    "",
                ]
            ),
            return_code=0,
        )
        service = WorkerProcessService()
        statuses = []
        output = []
        finished = []
        service.statusChanged.connect(statuses.append)
        service.outputLine.connect(output.append)
        service.finished.connect(finished.append)

        with patch(
            "source.launcher.services.worker_process_service.subprocess.Popen",
            return_value=process,
        ) as popen:
            service.start("auto_join_server", ["--server", "1234"])

        self.assertTrue(self.wait_until(lambda: finished))
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(
            command,
            [
                sys.executable,
                "-u",
                "-m",
                "source.launcher.helper_runner",
                "auto_join_server",
                "--server",
                "1234",
            ],
        )
        self.assertIn("Working", statuses)
        self.assertIn("plain output", output)
        self.assertEqual(finished, ["Done"])

    def test_start_failure_reports_finished_without_raising(self):
        service = WorkerProcessService()
        statuses = []
        finished = []
        service.statusChanged.connect(statuses.append)
        service.finished.connect(finished.append)

        with patch(
            "source.launcher.services.worker_process_service.subprocess.Popen",
            side_effect=OSError("boom"),
        ):
            service.start("fertilizer_refresh", [])

        self.assertEqual(statuses, ["Failed: boom"])
        self.assertEqual(finished, ["Failed: boom"])

    def test_start_ignores_second_request_until_previous_process_finishes(self):
        process = FakeProcess("", return_code=0, running=False)
        service = WorkerProcessService()

        with (
            patch(
                "source.launcher.services.worker_process_service.subprocess.Popen",
                return_value=process,
            ) as popen,
            patch(
                "source.launcher.services.worker_process_service.threading.Thread"
            ) as thread,
        ):
            thread.return_value.start = Mock()
            service.start("fertilizer_refresh", [])
            service.start("auto_join_server", ["--server", "1234"])

        popen.assert_called_once()

    def test_stop_terminates_running_process_once(self):
        process = FakeProcess("", running=True)
        service = WorkerProcessService()
        finished = []
        service.finished.connect(finished.append)

        with (
            patch(
                "source.launcher.services.worker_process_service.subprocess.Popen",
                return_value=process,
            ),
            patch(
                "source.launcher.services.worker_process_service.threading.Thread"
            ) as thread,
            patch(
                "source.launcher.services.worker_process_service.terminate_process_tree"
            ) as terminate,
        ):
            thread.return_value.is_alive.return_value = False
            service.start("fertilizer_refresh", [])
            self.assertTrue(service.isRunning)
            service.stop()

        terminate.assert_called_once_with(process)
        self.assertEqual(finished, ["Stopped."])
        self.assertFalse(service.isRunning)


if __name__ == "__main__":
    unittest.main()
