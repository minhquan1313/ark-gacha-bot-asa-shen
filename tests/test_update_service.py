import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from source.launcher.utils import update_service


class UpdateServiceTests(unittest.TestCase):
    def write_manifest(self, document):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_load_manifest_validates_and_normalizes_version(self):
        path = self.write_manifest(
            {
                "version": "v1.2.3",
                "released_at": "2026-07-22",
                "title": "Release",
                "changelog": ["Added updates"],
            }
        )

        manifest = update_service.load_manifest(path)

        self.assertEqual(manifest.version, "v1.2.3")
        self.assertEqual(manifest.changelog, ("Added updates",))

    def test_load_manifest_rejects_invalid_version(self):
        path = self.write_manifest({"version": "1.2"})

        with self.assertRaisesRegex(ValueError, "Invalid version"):
            update_service.load_manifest(path)

    @patch.object(update_service, "_load_remote_manifest")
    @patch.object(update_service, "_run_updater")
    @patch.object(update_service, "load_manifest")
    def test_check_for_update_uses_updater_available_exit_code(
        self, load_manifest, run_updater, remote_manifest
    ):
        current = update_service.UpdateManifest("1.0.0", "", "", ())
        latest = update_service.UpdateManifest("1.1.0", "2026-07-22", "Release", ())
        load_manifest.return_value = current
        run_updater.return_value = Mock(returncode=10, stdout="UPDATE_AVAILABLE")
        remote_manifest.return_value = latest

        result = update_service.check_for_update()

        self.assertTrue(result.update_available)
        self.assertEqual(result.latest, latest)
        run_updater.assert_called_once_with("/check")

    @patch.object(update_service, "_run_updater")
    @patch.object(update_service, "load_manifest")
    def test_check_for_update_reports_updater_failure(self, load_manifest, run_updater):
        current = update_service.UpdateManifest("1.0.0", "", "", ())
        load_manifest.return_value = current
        run_updater.return_value = Mock(returncode=1, stderr="network unavailable")

        result = update_service.check_for_update()

        self.assertFalse(result.update_available)
        self.assertEqual(result.error, "network unavailable")

    @patch.object(update_service, "load_manifest", side_effect=ValueError("bad manifest"))
    def test_check_for_update_reports_invalid_local_manifest(self, _load_manifest):
        result = update_service.check_for_update()

        self.assertFalse(result.update_available)
        self.assertEqual(result.error, "bad manifest")


if __name__ == "__main__":
    unittest.main()
