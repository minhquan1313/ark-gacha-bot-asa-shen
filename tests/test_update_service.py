import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from source.launcher.utils import update_service


class UpdateServiceTests(unittest.TestCase):
    def manifest(self, version="1.1.0"):
        return {
            "version": version,
            "released_at": "2026-07-22",
            "title": "Release",
            "changelog": ["First change", "Second change"],
        }

    def test_remote_manifest_is_parsed_from_updater_output(self):
        output = "\n".join(
            [
                "Checking update...",
                update_service.MANIFEST_BEGIN_MARKER,
                json.dumps(self.manifest()),
                update_service.MANIFEST_END_MARKER,
                "UPDATE_AVAILABLE",
            ]
        )

        result = update_service._load_remote_manifest(output)

        self.assertEqual(result.version, "1.1.0")
        self.assertEqual(result.changelog, ("First change", "Second change"))

    def test_remote_manifest_decodes_utf8_bytes(self):
        document = self.manifest()
        document["title"] = "Bản phát hành mới"
        output = "\n".join(
            [
                update_service.MANIFEST_BEGIN_MARKER,
                json.dumps(document, ensure_ascii=False),
                update_service.MANIFEST_END_MARKER,
            ]
        ).encode("utf-8")

        result = update_service._load_remote_manifest(output)

        self.assertEqual(result.title, "Bản phát hành mới")

    def test_remote_manifest_requires_output_markers(self):
        with self.assertRaisesRegex(ValueError, "remote manifest"):
            update_service._load_remote_manifest("UPDATE_AVAILABLE")

    def test_invalid_remote_manifest_is_rejected(self):
        output = "\n".join(
            [
                update_service.MANIFEST_BEGIN_MARKER,
                "{invalid}",
                update_service.MANIFEST_END_MARKER,
            ]
        )

        with self.assertRaisesRegex(ValueError, "Remote manifest is invalid"):
            update_service._load_remote_manifest(output)

    def test_empty_or_missing_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no output"):
            update_service._load_remote_manifest(None)

        with self.assertRaisesRegex(ValueError, "no output"):
            update_service._load_remote_manifest("")

    @patch.object(update_service, "_run_updater")
    @patch.object(update_service, "load_manifest")
    def test_check_uses_updater_exit_code_and_stdout_manifest(
        self, load_manifest, run_updater
    ):
        current = update_service._manifest_from_document(self.manifest("1.0.0"), "local")
        load_manifest.return_value = current
        run_updater.return_value = Mock(
            returncode=10,
            stdout="\n".join(
                [
                    update_service.MANIFEST_BEGIN_MARKER,
                    json.dumps(self.manifest()),
                    update_service.MANIFEST_END_MARKER,
                ]
            ),
            stderr="",
        )

        result = update_service.check_for_update()

        self.assertTrue(result.update_available)
        self.assertEqual(result.latest.changelog, ("First change", "Second change"))

    @patch.object(update_service, "_run_updater")
    @patch.object(update_service, "load_manifest")
    def test_check_decodes_utf8_stdout_and_stderr(self, load_manifest, run_updater):
        current = update_service._manifest_from_document(self.manifest("1.0.0"), "local")
        load_manifest.return_value = current
        remote = json.dumps(self.manifest(), ensure_ascii=False)
        run_updater.return_value = Mock(
            returncode=10,
            stdout=(
                f"{update_service.MANIFEST_BEGIN_MARKER}\n{remote}\n"
                f"{update_service.MANIFEST_END_MARKER}"
            ).encode("utf-8"),
            stderr="Không có lỗi".encode("utf-8"),
        )

        result = update_service.check_for_update()

        self.assertTrue(result.update_available)
        self.assertEqual(result.latest.title, "Release")

    @patch.object(update_service, "_run_updater")
    @patch.object(update_service, "load_manifest")
    def test_check_none_stdout_returns_safe_error(self, load_manifest, run_updater):
        current = update_service._manifest_from_document(self.manifest("1.0.0"), "local")
        load_manifest.return_value = current
        run_updater.return_value = Mock(returncode=0, stdout=None, stderr=None)

        result = update_service.check_for_update()

        self.assertFalse(result.update_available)
        self.assertIn("remote manifest", result.error.lower())


if __name__ == "__main__":
    unittest.main()
