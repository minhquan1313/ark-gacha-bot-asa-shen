import json
import logging
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.config.constants import installed_version
from source.launcher.gui import SettingsGUI
from source.launcher.utils import update_service
import test_server_transfer_helper_ui as transfer_tests


class LauncherRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def launcher(self):
        with patch.object(SettingsGUI, "_finish_startup"), patch.object(
            SettingsGUI, "persist_settings_from_visible_fields", return_value=False
        ):
            launcher = SettingsGUI()
        launcher._tick = Mock()
        launcher._start_update_check = Mock()
        self.addCleanup(launcher.close)
        launcher.resize(1200, 800)
        launcher.show()
        return launcher

    def test_dashboard_alignment_after_update_and_maximize_restore(self):
        launcher = self.launcher()
        launcher.show_page("dashboard")
        launcher.maximize_custom_window()
        for error in ("", "network unavailable"):
            launcher.show_page("update")
            manifest = update_service.UpdateManifest("1.0.3", "", "Release", ("A long release note " * 100,))
            launcher._on_update_check_finished(
                update_service.UpdateCheckResult(manifest, manifest, False, error), False
            )
            QTest.qWait(20)
            launcher.show_page("dashboard")
            QTest.qWait(20)
            self.assertEqual(launcher.dashboard_actions_card.width(), launcher.dashboard_server_card.width())
        self.assertTrue(launcher.title_bar.property("customMaximized"))
        self.assertTrue(launcher.centralWidget().property("customMaximized"))
        self.assertTrue(launcher.mask().isEmpty())
        launcher.start_drag_from_custom_maximized(QPoint(600, 20), 0.5)
        QTest.qWait(20)
        self.assertFalse(launcher.title_bar.property("customMaximized"))
        self.assertFalse(launcher.mask().isEmpty())
        self.assertEqual(launcher.dashboard_actions_card.width(), launcher.dashboard_server_card.width())

    def test_build_uses_installed_manifest_and_invalid_version_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            self.assertEqual(installed_version(path), "Unknown")
            for invalid in ("{", '{"version": null}', '{"version": "bad"}'):
                path.write_text(invalid)
                self.assertEqual(installed_version(path), "Unknown")
            path.write_text(json.dumps({"version": "1.0.3"}))
            version = installed_version(path)
            with patch("source.launcher.gui_parts.window.APP_VERSION", version), patch("source.launcher.components.widgets.APP_VERSION", version), patch("source.launcher.pages.logs_tools.APP_VERSION", version), patch("source.launcher.pages.logs_tools.load_manifest", return_value=update_service.UpdateManifest("1.0.3", "", "", ())):
                launcher = self.launcher()
            labels = [label.text() for label in launcher.findChildren(QLabel)]
            self.assertIn("BUILD 1.0.3", labels)
            self.assertIn("v1.0.3", labels)
            self.assertIn("Version: 1.0.3", labels)
            self.assertNotIn("BUILD 1.0.0", labels)


class UpdateDiagnosticTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows updater batch")
    def test_batch_preserves_exit_codes_output_and_appends_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="update diagnostics ") as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            batch = (Path(__file__).resolve().parents[1] / "updater.bat").read_text()
            # A batch Git stand-in needs CALL; the installed git.exe does not.
            batch = re.sub(r"(?m)^(\s*)git ", r"\1call git ", batch)
            (root / "updater.bat").write_text(batch)
            (root / "git.cmd").write_text(
                '@echo off\n'
                'if "%1"=="fetch" (\n'
                '  if "%FAIL_FETCH%"=="1" (\n'
                '    echo Network permission denied 1>&2\n'
                '    exit /b 1\n'
                '  )\n'
                '  echo Fetch succeeded\n'
                '  exit /b 0\n'
                ')\n'
                'if "%1"=="rev-list" echo 1\n'
                'if "%1"=="show" echo {"version":"1.0.4"}\n'
                'if "%1"=="pull" echo Pull succeeded\n'
                'exit /b 0\n'
            )
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]}
            log_directory = root / "source/logs"
            log_directory.mkdir(parents=True)
            main_log = log_directory / "logs.txt"
            standalone_log = log_directory / "updater.log"
            logger = logging.Logger("isolated-update-integration")
            handler = logging.FileHandler(main_log, encoding="utf-8")
            logger.addHandler(handler)
            try:
                logger.info("Existing launcher log")
                handler.flush()
                original = main_log.read_bytes()
                for mode, failure, code in (("/check", "0", 10), ("/update", "0", 0), ("/check", "1", 1)):
                    result = subprocess.run(["cmd", "/d", "/c", str(root / "updater.bat"), mode], cwd=root, env={**env, "FAIL_FETCH": failure}, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, code, result.stdout.decode(errors="replace"))
                    self.assertEqual(result.stderr, b"")
                    self.assertIn(b"updater.log", result.stdout)
                    if code == 10:
                        self.assertIn(b"UPDATE_MANIFEST_BEGIN", result.stdout)
                        self.assertIn(b"UPDATE_MANIFEST_END", result.stdout)
                self.assertEqual(main_log.read_bytes(), original)
                log = standalone_log.read_text()
                self.assertEqual(log.count("[UPDATE] Starting"), 3)
                self.assertIn("Network permission denied", log)
                self.assertIn("Pull succeeded", log)
                self.assertIn("exit code 10", log)
                self.assertIn("exit code 1", log)
                standalone_original = standalone_log.read_bytes()
                current = update_service.UpdateManifest("1.0.3", "", "", ())
                with patch.object(update_service, "logger", logger), patch.object(update_service, "UPDATER_PATH", root / "updater.bat"), patch.object(update_service, "REPOSITORY_ROOT", root), patch.object(update_service, "load_manifest", return_value=current):
                    for failure in ("0", "1"):
                        with patch.dict(os.environ, {**env, "FAIL_FETCH": failure}):
                            result = update_service.check_for_update()
                        self.assertEqual(result.update_available, failure == "0", main_log.read_text())
                        self.assertEqual(bool(result.error), failure == "1")
                handler.flush()
                self.assertEqual(standalone_log.read_bytes(), standalone_original)
                log = main_log.read_text()
                self.assertTrue(log.startswith("Existing launcher log"))
                self.assertIn("Remote version: 1.0.4", log)
                self.assertIn("Exit code: 10", log)
                self.assertIn("Exit code: 1", log)
                self.assertIn("Network permission denied", log)
                self.assertNotIn("being used by another process", log)
            finally:
                handler.close()

    def test_checks_append_output_and_timeout_details_to_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs.txt"
            logger = logging.Logger("test-update")
            handler = logging.FileHandler(path, encoding="utf-8")
            logger.addHandler(handler)
            self.addCleanup(handler.close)
            current = update_service.UpdateManifest("1.0.3", "", "", ())
            cases = [
                subprocess.CompletedProcess([], 1, b"fetch started", b"permission denied"),
                subprocess.TimeoutExpired("updater", 120, b"partial fetch", b"partial error"),
                OSError("cannot launch updater"),
                subprocess.CompletedProcess([], 0, b"malformed manifest", b""),
                subprocess.CompletedProcess([], 10, b'UPDATE_MANIFEST_BEGIN\n{"version":"1.0.4"}\nUPDATE_MANIFEST_END', b""),
            ]
            with patch.object(update_service, "logger", logger), patch.object(update_service, "load_manifest", return_value=current):
                for case in cases:
                    with patch.object(update_service, "_run_updater", side_effect=case if isinstance(case, Exception) else None, return_value=case):
                        result = update_service.check_for_update()
                self.assertTrue(result.update_available)
            handler.flush()
            handler.close()
            output = path.read_text()
            for detail in ("1.0.3", "1.0.4", "Exit code: 1", "fetch started", "permission denied", "partial fetch", "partial error", "cannot launch updater", "malformed manifest", "Traceback"):
                self.assertIn(detail, output)
            self.assertEqual(output.count("Check started."), len(cases))


class SwitchRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stale_worker_completion_cannot_finish_new_worker(self):
        current, previous = Mock(), Mock()
        helper = SimpleNamespace(worker_process=current, _emit_worker_finished=Mock())
        WorkerHelperWindow._dispatch_worker_result(helper, previous, "Finished.")
        helper._emit_worker_finished.assert_not_called()
        WorkerHelperWindow._dispatch_worker_result(helper, current, "Finished.")
        helper._emit_worker_finished.assert_called_once_with("Finished.")

    def test_steam_launch_does_not_keep_worker_output_pipe_open(self):
        from source.launcher.utils import steam_accounts
        with patch.object(steam_accounts.subprocess, "Popen") as launch:
            steam_accounts.launch_steam()
        for stream in ("stdin", "stdout", "stderr"):
            self.assertEqual(launch.call_args.kwargs[stream], subprocess.DEVNULL)
        self.assertTrue(launch.call_args.kwargs["close_fds"])

    def test_switch_view_switch_and_busy_rejection(self):
        fixture = transfer_tests.ServerTransferHelperUiTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        accounts = [{"account_name": f"steam{i}", "most_recent": i == 1, "timestamp": i} for i in (1, 2, 3)]
        helper = fixture._transfer_helper(account_count=3, steam_accounts=accounts)
        self.addCleanup(helper.close)
        with patch("source.launcher.server_transfer_helper.load_steam_accounts", return_value=accounts), patch("source.launcher.server_transfer_helper.loginusers_path", return_value=Path("C:/Steam/loginusers.vdf")), patch.object(helper, "_start_worker") as start, patch("source.launcher.server_transfer_helper.QTimer.singleShot"), patch.object(helper, "_require_ark_window", return_value=True), patch.object(helper, "refocus_helper"), patch("source.launcher.server_transfer_helper.view_route_entry") as view:
            for account in (2, 3):
                helper.player_rows[account - 1]["switch"].click()
                self.assertEqual(start.call_args.args[2], f"steam{account}")
                worker = Mock(stdout=None)
                worker.poll.return_value = 0
                helper.worker_process = worker
                helper.worker_launch_pending = True
                helper._dispatch_worker_result(worker, f"Steam restarted for steam{account}.")
                self.assertIsNone(helper.worker_process)
                self.assertFalse(helper.worker_launch_pending)
                self.assertFalse(helper.switching_player_steam)
                helper._view_dedi({"yaw": Mock(text=Mock(return_value="10")), "pitch": Mock(text=Mock(return_value="20")), "crouched": Mock(isChecked=Mock(return_value=False))})
            self.assertEqual(view.call_count, 2)
            self.assertEqual(start.call_count, 2)
            helper.worker_launch_pending = True
            helper._switch_player_steam_from_row(1)
            self.assertIn("another helper operation", helper.status.text())
            self.assertEqual(start.call_count, 2)
            helper.worker_launch_pending = False

    def test_failed_switch_restores_controls_and_ignores_duplicate_completion(self):
        fixture = transfer_tests.ServerTransferHelperUiTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        accounts = [{"account_name": f"steam{i}", "most_recent": i == 1, "timestamp": i} for i in (1, 2)]
        helper = fixture._transfer_helper(account_count=2, steam_accounts=accounts)
        self.addCleanup(helper.close)
        with patch("source.launcher.server_transfer_helper.load_steam_accounts", return_value=accounts), patch("source.launcher.server_transfer_helper.loginusers_path", return_value=Path("C:/Steam/loginusers.vdf")), patch("source.launcher.components.helper_window.start_subprocess", side_effect=OSError("launch failed")):
            helper.player_rows[1]["switch"].click()
        self.assertIn("launch failed", helper.status.text())
        self.assertFalse(helper.running_ui_active)
        self.assertFalse(helper.worker_launch_pending)
        self.assertTrue(helper.player_rows[1]["switch"].isEnabled())
        helper.switching_player_steam = True
        helper.pending_switch_account = "steam2"
        worker = Mock(stdout=None)
        worker.poll.return_value = 1
        helper.worker_process = worker
        helper._dispatch_worker_result(worker, "Failed: sign-in failed")
        self.assertIn("sign-in failed", helper.status.text())
        self.assertTrue(helper.player_rows[1]["switch"].isEnabled())
        with patch.object(helper, "_emit_worker_finished") as finished:
            helper._dispatch_worker_result(worker, "Failed: sign-in failed")
        finished.assert_not_called()
