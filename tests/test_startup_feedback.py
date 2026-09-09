"""Exercise the real entry point without importing automation or changing settings."""

import subprocess
import sys
import unittest
from pathlib import Path


class StartupFeedbackTests(unittest.TestCase):
    def run_entry(self, fail: bool = False):
        """Exercise success or failure after an intentionally slow launcher import."""
        script = r'''
import os, sys, types, builtins, time
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget
import source.ui.components.boot_splash as boot
import main
events = []
original_init = boot.BootSplash.__init__
def splash_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.first_presented.connect(lambda: events.append('presented'))
boot.BootSplash.__init__ = splash_init
class Launcher(QWidget):
    startup_progress = Signal(str)
    startup_ready = Signal()
    startup_failed = Signal(str)
    def __init__(self, deferred_startup=False):
        super().__init__()
        self.resize(1000, 680)
        QTimer.singleShot(0, self.startup_ready.emit)
    def _shutdown_resources(self):
        pass
    def complete_startup_presentation(self):
        events.append('complete')
        QApplication.instance().quit()
module = types.ModuleType('source.launcher.gui')
module.SettingsGUI = Launcher
sys.modules['source.launcher.gui'] = module
original_import = builtins.__import__
def delayed_import(name, *args, **kwargs):
    if name == 'source.launcher.gui':
        assert events == ['presented'], events
        events.append('import')
        time.sleep(0.3)
    return original_import(name, *args, **kwargs)
builtins.__import__ = delayed_import
assert main.main() == 0
assert events == ['presented', 'import', 'complete'], events
assert 'source.app_lifecycle' not in sys.modules
'''
        if fail:
            script = script.replace(
                "self.resize(1000, 680)", "raise ValueError('startup fixture failure')"
            ).replace(
                "assert main.main() == 0",
                "from PySide6.QtWidgets import QMessageBox\n"
                "QMessageBox.critical = lambda *args: events.append('error-dialog')\n"
                "assert main.main() == 1",
            ).replace(
                "['presented', 'import', 'complete']",
                "['presented', 'import', 'error-dialog']",
            )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_delayed_launcher_import_runs_after_first_presentation(self):
        self.run_entry()

    def test_startup_failure_after_feedback_shows_error_and_exits(self):
        self.run_entry(fail=True)
