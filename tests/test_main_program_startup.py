import asyncio
import io
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

pyautogui_stub = ModuleType("pyautogui")
pyautogui_stub.FAILSAFE = True
sys.modules.setdefault("pyautogui", pyautogui_stub)
windows_stub = ModuleType("source.utility.windows")
windows_stub.move_mouse = Mock()
sys.modules.setdefault("source.utility.windows", windows_stub)

import main_program
from source.launcher import runner_process


class MainProgramStartupTests(unittest.TestCase):
    def test_direct_main_program_runs_without_launcher_ack(self) -> None:
        task_manager = SimpleNamespace(prepare=Mock(), run=Mock())

        with (
            patch.dict(sys.modules, {"task_manager": task_manager}),
            patch.object(main_program.windows, "move_mouse"),
            patch.object(
                main_program.settings, "allow_focus_ark_window", False, create=True
            ),
            patch.object(main_program, "focus_window"),
            patch.object(main_program, "shutdown_bot"),
        ):
            asyncio.run(main_program.main())

        task_manager.prepare.assert_called_once_with()
        task_manager.run.assert_called_once_with()

    def test_runner_process_ack_skips_direct_terminal_launch(self) -> None:
        stdin = SimpleNamespace(isatty=Mock(return_value=True))

        with patch.object(sys, "stdin", stdin):
            self.assertTrue(runner_process.wait_for_launcher_ack(0.01))

    def test_runner_process_ack_reads_expected_pipe_message(self) -> None:
        stdin = io.StringIO("__RUNNER_OVERLAY_READY__\n")
        stdin.isatty = Mock(return_value=False)

        with patch.object(sys, "stdin", stdin):
            self.assertTrue(runner_process.wait_for_launcher_ack(0.5))

    def test_runner_process_waits_for_overlay_ack_before_running_tasks(self) -> None:
        task_manager = Mock()

        with (
            patch.object(
                runner_process.main_program, "prepare_bot", return_value=task_manager
            ) as prepare,
            patch.object(runner_process.main_program, "run_bot") as run,
            patch.object(
                runner_process, "wait_for_launcher_ack", return_value=True
            ) as wait,
            patch.object(runner_process.main_program, "shutdown_bot"),
        ):
            asyncio.run(runner_process.main())

        prepare.assert_called_once_with()
        wait.assert_called_once_with(runner_process.RUNNER_OVERLAY_ACK_TIMEOUT_SECONDS)
        run.assert_called_once_with(task_manager)

    def test_runner_process_does_not_run_tasks_without_overlay_ack(self) -> None:
        task_manager = Mock()

        with (
            patch.object(
                runner_process.main_program, "prepare_bot", return_value=task_manager
            ),
            patch.object(runner_process.main_program, "run_bot") as run,
            patch.object(runner_process, "wait_for_launcher_ack", return_value=False),
            patch.object(runner_process.logs.logger, "error") as log_error,
            patch.object(runner_process.main_program, "shutdown_bot"),
        ):
            asyncio.run(runner_process.main())

        run.assert_not_called()
        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
