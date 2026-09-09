import os
import subprocess
import sys
import tempfile
import time
import uuid
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UpdateBatchContractTests(unittest.TestCase):
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
