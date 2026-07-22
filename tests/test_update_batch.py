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

    def test_run_calls_updater_before_starting_python_and_restarts_after_cleanup(self):
        contents = (ROOT / "run.bat").read_text(encoding="utf-8")

        self.assertLess(contents.index("call updater.bat /update"), contents.index("python main.py"))
        self.assertLess(contents.index("call deactivate"), contents.index(".update_restart.request"))
        self.assertIn('start "" /d "%~dp0" "%~f0"', contents)


if __name__ == "__main__":
    unittest.main()
