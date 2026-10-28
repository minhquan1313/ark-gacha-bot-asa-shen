import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt" and shutil.which("git"), "Windows Git integration")
class UpdaterIntegrationTests(unittest.TestCase):
    def test_ownership_backup_and_setup_before_restart(self):
        """Update overlapping client edits despite a simulated owner mismatch."""
        for inherited_config in (False, True):
            with self.subTest(inherited_config=inherited_config):
                self.exercise_update(inherited_config=inherited_config)

    def test_setup_failure_prevents_restart(self):
        """Leave updated code in place but do not launch with missing dependencies."""
        self.exercise_update(setup_exit=1)

    def test_current_installation_retries_setup(self):
        """Run setup even when there are no new commits to download."""
        self.exercise_update(has_update=False)

    def test_divergent_history_prevents_setup_and_restart(self):
        """Fail rather than merging client commits into a release."""
        self.exercise_update(divergent=True)

    def exercise_update(self, setup_exit: int = 0, has_update: bool = True,
                        divergent: bool = False, inherited_config: bool = True):
        """Run the actual batch against disposable repositories and stub setup/run scripts."""
        with tempfile.TemporaryDirectory(prefix="gbot update ") as directory:
            root = Path(directory)
            remote = root / "remote"
            client = root / "client install"
            env = dict(os.environ)
            env.update(TEMP=str(root), TMP=str(root),
                       GIT_CONFIG_GLOBAL=str(root / "gitconfig"), GIT_CONFIG_NOSYSTEM="1",
                       GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="gbot.inherited", GIT_CONFIG_VALUE_0="retained",
                       GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
                       GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com")
            if not inherited_config:
                for key in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
                    env.pop(key)

            def git(cwd: Path, *args: str):
                """Run Git with isolated configuration and capture its output."""
                return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                                      capture_output=True, text=True).stdout.strip()

            remote.mkdir()
            git(remote, "init", "-b", "stable_before_qml")
            shutil.copyfile(ROOT / "updater.bat", remote / "updater.bat")
            (remote / "setup.bat").write_text(
                '@echo off\necho setup %1>>sequence.txt\n'
                'git config --get gbot.inherited >config-check.txt\n'
                'echo %GIT_CONFIG_COUNT% >>config-check.txt\n'
                'git config --get-all safe.directory >>config-check.txt\n'
                'exit /b %SETUP_EXIT%\n')
            (remote / "run.bat").write_text('@echo off\necho run>>sequence.txt\nexit /b 0\n')
            (remote / "manifest.json").write_text('{"version":"1.0.0"}')
            (remote / ".gitignore").write_text('source/logs/\nsequence.txt\nconfig-check.txt\n')
            (remote / "code.txt").write_text("old code")
            git(remote, "add", ".")
            git(remote, "commit", "-m", "initial")
            git(root, "clone", str(remote), str(client))
            if has_update:
                (remote / "code.txt").write_text("latest code")
                git(remote, "commit", "-am", "release")
            if divergent:
                (client / "local-commit.txt").write_text("local commit")
                git(client, "add", "local-commit.txt")
                git(client, "commit", "-m", "client commit")
            (client / "code.txt").write_text("staged client edit")
            git(client, "add", "code.txt")
            (client / "code.txt").write_text("unstaged client edit")
            (client / "client.txt").write_text("untracked backup")
            # Simulate ownership only on the client, not on the local remote server.
            git(client, "config", "remote.origin.uploadpack",
                "unset GIT_TEST_ASSUME_DIFFERENT_OWNER; git-upload-pack")
            original_config = (client / ".git" / "config").read_bytes()
            env.update(GIT_TEST_ASSUME_DIFFERENT_OWNER="1", SETUP_EXIT=str(setup_exit))
            (root / "caller.bat").write_text(
                '@echo off\ncall "%~dp0client install\\updater.bat" %1\n'
                'set "RESULT=%ERRORLEVEL%"\necho %GIT_CONFIG_COUNT% >"%~dp0parent-count.txt"\n'
                'exit /b %RESULT%\n')

            def updater(mode: str):
                """Run the updater in a parent shell to check configuration does not leak."""
                result = subprocess.run(["cmd.exe", "/d", "/c", "call", str(root / "caller.bat"), mode],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual((root / "parent-count.txt").read_text().strip(),
                                 "1" if inherited_config else "ECHO is off.")
                return result

            rejected = subprocess.run(["git", "status"], cwd=client, env=env,
                                      capture_output=True, text=True)
            self.assertIn("dubious ownership", rejected.stderr)
            checked = updater("/check")
            self.assertEqual(checked.returncode, 10 if has_update else 0, checked.stdout + checked.stderr)
            self.assertFalse((client / "sequence.txt").exists())
            self.assertEqual((client / "code.txt").read_text(), "unstaged client edit")
            updated = updater("/update")
            self.assertEqual(updated.returncode, 1 if divergent else setup_exit, updated.stdout + updated.stderr)
            self.assertEqual((client / ".git" / "config").read_bytes(), original_config)
            self.assertFalse((root / "gitconfig").exists())
            self.assertIn("Finished /update", (client / "source/logs/updater.log").read_text())
            if divergent:
                self.assertFalse((client / "sequence.txt").exists())
            else:
                expected = ["setup /update"] + ([] if setup_exit else ["run"])
                self.assertEqual((client / "sequence.txt").read_text().splitlines(), expected)
                self.assertEqual([line.strip() for line in (client / "config-check.txt").read_text().splitlines()],
                                 ["retained", "2", client.as_posix()] if inherited_config
                                 else ["1", client.as_posix()])
            if has_update:
                self.assertEqual((client / "code.txt").read_text(), "old code" if divergent else "latest code")
                self.assertFalse((client / "client.txt").exists())
                env.pop("GIT_TEST_ASSUME_DIFFERENT_OWNER")
                self.assertEqual(git(client, "show", "stash@{0}:code.txt"), "unstaged client edit")
                self.assertEqual(git(client, "show", "stash@{0}^2:code.txt"), "staged client edit")
                self.assertEqual(git(client, "show", "stash@{0}^3:client.txt"), "untracked backup")

    def test_unattended_setup_returns_pip_failures(self):
        """Run actual setup without installing packages, covering both pip failure points."""
        for failure in ("", "--upgrade", "-r"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix="gbot setup ") as directory:
                root = Path(directory)
                shutil.copyfile(ROOT / "setup.bat", root / "setup.bat")
                scripts = root / "venv" / "Scripts"
                scripts.mkdir(parents=True)
                (scripts / "activate.bat").write_text('@echo off\nexit /b 0\n')
                (root / "pip.py").write_text(
                    "import os, pathlib, sys\n"
                    "with pathlib.Path('pip-calls.txt').open('a') as log: log.write(' '.join(sys.argv[1:]) + '\\n')\n"
                    "sys.exit(1 if os.environ['PIP_TEST_FAILURE'] in sys.argv else 0)\n")
                env = dict(os.environ)
                env.update(PYTHONPATH=str(root), PIP_TEST_FAILURE=failure)
                env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
                result = subprocess.run(["cmd.exe", "/d", "/c", "call", str(root / "setup.bat"), "/update"],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1 if failure else 0, result.stdout + result.stderr)
                expected = ["install --upgrade pip"]
                if failure != "--upgrade":
                    expected.append("install -r requirements.txt")
                self.assertEqual((root / "pip-calls.txt").read_text().splitlines(), expected)


class UpdateBatchContractTests(unittest.TestCase):
    def test_restart_hands_off_after_cleanup(self):
        from source import app_lifecycle

        with tempfile.TemporaryDirectory(prefix="gbot restart ") as directory:
            root = Path(directory)
            request = root / ".update_restart.request"
            request.touch()
            events = Mock()
            with patch.object(app_lifecycle, "cleanup_app_processes", events.cleanup), \
                    patch.object(app_lifecycle.subprocess, "Popen", events.popen):
                app_lifecycle.finish_application(root, "TestApp")
            self.assertEqual([call[0] for call in events.mock_calls], ["cleanup", "popen"])
            self.assertEqual(events.popen.call_args.args[0],
                             ["cmd.exe", "/d", "/c", "call", str(root / "updater.bat"), "/update"])
            self.assertFalse(request.exists())

    def test_failed_handoff_preserves_restart_request(self):
        from source import app_lifecycle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / ".update_restart.request"
            request.touch()
            with patch.object(app_lifecycle, "cleanup_app_processes"), \
                    patch.object(app_lifecycle.subprocess, "Popen", side_effect=OSError("cannot launch")):
                with self.assertRaises(OSError):
                    app_lifecycle.finish_application(root, "TestApp")
            self.assertTrue(request.exists())

    def test_updater_exposes_check_and_update_modes(self):
        contents = (ROOT / "updater.bat").read_text(encoding="utf-8")

        self.assertIn("/check", contents)
        self.assertIn("/update", contents)
        self.assertIn("exit /b 10", contents)
        self.assertIn("exit /b 0", contents)
        self.assertIn("exit /b 1", contents)

    def test_run_hands_off_to_windowed_python(self):
        contents = (ROOT / "run.bat").read_text(encoding="utf-8")
        self.assertIn('start "" /d "%~dp0" "%~dp0venv\\Scripts\\pythonw.exe"', contents)
        self.assertNotIn("Get-CimInstance", contents)
        self.assertNotIn(".update_restart.request", contents)
        self.assertNotIn("activate.bat", contents)


@unittest.skipUnless(os.name == "nt", "Windows batch integration")
class PythonLifecycleIntegrationTests(unittest.TestCase):
    def test_crash_cleanup_and_restart_with_spaces(self):
        """Exercise the real batch in isolation with a disposable application ID."""
        import psutil

        for mode in ("normal", "crash", "restart"):
            restart = mode == "restart"
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="gbot batch ") as directory:
                root = Path(directory)
                app_id = "GBotTest" + uuid.uuid4().hex
                batch = (ROOT / "run.bat").read_text().replace("ShenGBot", app_id)
                batch = batch.replace(
                    "%~dp0venv\\Scripts\\pythonw.exe",
                    str(Path(sys.executable).with_name("pythonw.exe")),
                )
                (root / "run.bat").write_text(batch)
                (root / "updater.bat").write_text('@echo off\ncall "%~dp0run.bat"\n')
                scripts = root / "venv" / "Scripts"
                scripts.mkdir(parents=True)
                (scripts / "pythonw.exe").touch()
                (root / "app_lifecycle.py").write_text(
                    (ROOT / "source" / "app_lifecycle.py").read_text()
                )
                (root / "main.py").write_text(
                    "import pathlib, subprocess, sys\n"
                    "from app_lifecycle import finish_application\n"
                    "root=pathlib.Path(__file__).parent\n"
                    "try:\n"
                    "    count=len(list(root.glob('child*.pid')))\n"
                    "    child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', '--app-id', sys.argv[2]])\n"
                    "    (root / f'child{count}.pid').write_text(str(child.pid))\n"
                    + ("    if count == 0: (root / '.update_restart.request').touch()\n" if restart else "")
                    + ("    raise RuntimeError('startup failure')\n" if mode == "crash" else "    sys.exit(0)\n")
                    + "finally:\n    finish_application(root, sys.argv[2])\n"
                )
                env = dict(os.environ)
                env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
                try:
                    with (root / "batch.log").open("w") as output:
                        subprocess.run(
                            ["cmd.exe", "/d", "/c", str(root / "run.bat")], cwd=root,
                            env=env, stdout=output, stderr=subprocess.STDOUT, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    expected = 2 if restart else 1
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        files = list(root.glob("child*.pid"))
                        if len(files) == expected and all(not psutil.pid_exists(int(f.read_text())) for f in files):
                            break
                        time.sleep(0.1)
                    self.assertEqual(len(files), expected, (root / "batch.log").read_text())
                    self.assertTrue(all(not psutil.pid_exists(int(f.read_text())) for f in files))
                    self.assertFalse((root / ".update_restart.request").exists())
                finally:
                    for process in psutil.process_iter(["cmdline"]):
                        command = process.info["cmdline"] or []
                        if app_id in command or any(str(root).casefold() in arg.casefold() for arg in command):
                            try:
                                children = process.children(recursive=True)
                                for child in children:
                                    try:
                                        child.kill()
                                    except psutil.NoSuchProcess:
                                        pass
                                process.kill()
                                psutil.wait_procs([process, *children], timeout=5)
                            except psutil.NoSuchProcess:
                                pass


if __name__ == "__main__":
    unittest.main()
