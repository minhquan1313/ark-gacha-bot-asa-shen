import json
import tempfile
import unittest
from pathlib import Path

from source.launcher.utils.auto_join_server_store import (
    load_auto_join_servers,
    remember_auto_join_server,
    save_auto_join_servers,
)


class AutoJoinServerStoreTests(unittest.TestCase):
    def test_loads_valid_unique_history_with_latest_occurrence_last(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(
                json.dumps({"last_join": ["5147", "bad", "6049", "5147"]}),
                encoding="utf-8",
            )

            self.assertEqual(load_auto_join_servers(path), ["6049", "5147"])

    def test_missing_empty_malformed_and_wrong_shape_are_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            self.assertEqual(load_auto_join_servers(path), [])
            for content in ["", "{bad", "[]", '{"last_join": "5147"}']:
                path.write_text(content, encoding="utf-8")
                self.assertEqual(load_auto_join_servers(path), [])

    def test_save_normalizes_values_and_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auto_join" / "server.json"

            saved = save_auto_join_servers([" 5147 ", "0", "6049"], path)

            self.assertEqual(saved, ["5147", "6049"])
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"last_join": ["5147", "6049"]},
            )

    def test_remember_moves_existing_server_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            save_auto_join_servers(["5147", "6049"], path)

            remembered = remember_auto_join_server("5147", path)

            self.assertEqual(remembered, ["6049", "5147"])
            self.assertEqual(load_auto_join_servers(path), remembered)


if __name__ == "__main__":
    unittest.main()
