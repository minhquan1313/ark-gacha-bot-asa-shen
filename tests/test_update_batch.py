import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UpdateBatchContractTests(unittest.TestCase):
    def test_updater_owns_branch_and_emits_manifest_markers(self):
        updater = (ROOT / "updater.bat").read_text(encoding="utf-8")
        service = (ROOT / "source/launcher/utils/update_service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('set "BRANCH=', updater)
        self.assertIn("UPDATE_MANIFEST_BEGIN", updater)
        self.assertIn("UPDATE_MANIFEST_END", updater)
        self.assertNotIn("UPDATE_BRANCH", service)
        self.assertNotIn('git", "show"', service)

    def test_manifest_is_emitted_after_fetch(self):
        updater = (ROOT / "updater.bat").read_text(encoding="utf-8")

        self.assertLess(
            updater.index('git fetch origin "%BRANCH%"'),
            updater.index("UPDATE_MANIFEST_BEGIN"),
        )
        self.assertLess(
            updater.index("UPDATE_MANIFEST_BEGIN"),
            updater.index("UPDATE_MANIFEST_END"),
        )


if __name__ == "__main__":
    unittest.main()
