import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source.gacha_bot.deposit_config import load_deposit_config
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.station_config import load_gacha_config, load_pego_config


class QmlSettingsControllerActionTests(unittest.TestCase):
    def make_controller(self, root):
        settings_path = root / "settings.json"
        gacha_path = root / "gacha.json"
        pego_path = root / "pego.json"
        deposit_path = root / "dedis.json"
        patches = [
            patch(
                "source.launcher.controllers.settings_controller.load_settings",
                return_value={"server_number": "0", "auto_start_program": False},
            ),
            patch("source.launcher.controllers.settings_controller.save_settings"),
            patch(
                "source.launcher.controllers.settings_controller.load_gacha_config",
                side_effect=lambda: load_gacha_config(gacha_path),
            ),
            patch(
                "source.launcher.controllers.settings_controller.save_gacha_config",
                side_effect=lambda entries: __import__(
                    "source.launcher.station_config",
                    fromlist=["save_gacha_config"],
                ).save_gacha_config(entries, gacha_path),
            ),
            patch(
                "source.launcher.controllers.settings_controller.load_pego_config",
                side_effect=lambda: load_pego_config(pego_path),
            ),
            patch(
                "source.launcher.controllers.settings_controller.save_pego_config",
                side_effect=lambda entries: __import__(
                    "source.launcher.station_config",
                    fromlist=["save_pego_config"],
                ).save_pego_config(entries, pego_path),
            ),
            patch(
                "source.launcher.controllers.settings_controller.load_deposit_config",
                side_effect=lambda: load_deposit_config(deposit_path),
            ),
            patch(
                "source.launcher.controllers.settings_controller.save_deposit_config",
                side_effect=lambda config: __import__(
                    "source.gacha_bot.deposit_config",
                    fromlist=["save_deposit_config"],
                ).save_deposit_config(config, deposit_path),
            ),
        ]
        for patcher in patches:
            patcher.start()
        self.addCleanup(lambda: [patcher.stop() for patcher in patches])
        return SettingsController(), gacha_path, pego_path, deposit_path

    def test_gacha_group_action_adds_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.runGroupAction("add_gacha_pair", "")

            self.assertEqual(len(load_gacha_config(gacha_path)), 4)

    def test_gacha_group_actions_include_remove_last(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("GACHA")

            keys = [action["key"] for action in controller.groupActions]

            self.assertIn("remove_last_gacha_pair", keys)

    def test_gacha_remove_last_pair_updates_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_gacha_pair", "")

            controller.runGroupAction("remove_last_gacha_pair", "")

            entries = load_gacha_config(gacha_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual({entry["teleporter"] for entry in entries}, {"GACHAPAIR_1"})

    def test_gacha_remove_last_keeps_required_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.runGroupAction("remove_last_gacha_pair", "")

            self.assertEqual(len(load_gacha_config(gacha_path)), 2)

    def test_pego_apply_delay_updates_all_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_pego", "")

            controller.runGroupAction("apply_pego_delay", "123")

            self.assertEqual(
                [entry["delay"] for entry in load_pego_config(pego_path)],
                [123, 123],
            )

    def test_pego_group_actions_include_remove_last(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("PEGO")

            keys = [action["key"] for action in controller.groupActions]

            self.assertIn("remove_last_pego", keys)

    def test_pego_remove_last_updates_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_pego", "")

            controller.runGroupAction("remove_last_pego", "")

            entries = load_pego_config(pego_path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["name"], "pego1")

    def test_storage_group_action_adds_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.runGroupAction("add_crystal_route", "")
            controller.runGroupAction("add_grindable_route", "")

            config = load_deposit_config(deposit_path)
            self.assertEqual(len(config["depositCrystalData"]), 2)
            self.assertEqual(len(config["depositGrindableData"]), 2)

    def test_storage_group_actions_include_remove_last(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("STORAGE")

            keys = [action["key"] for action in controller.groupActions]

            self.assertIn("remove_last_crystal_route", keys)
            self.assertIn("remove_last_grindable_route", keys)

    def test_storage_remove_last_routes_update_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_crystal_route", "")
            controller.runGroupAction("add_grindable_route", "")

            controller.runGroupAction("remove_last_crystal_route", "")
            controller.runGroupAction("remove_last_grindable_route", "")

            config = load_deposit_config(deposit_path)
            self.assertEqual(len(config["depositCrystalData"]), 1)
            self.assertEqual(len(config["depositGrindableData"]), 1)

    def test_storage_remove_last_keeps_required_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.runGroupAction("remove_last_crystal_route", "")
            controller.runGroupAction("remove_last_grindable_route", "")

            config = load_deposit_config(deposit_path)
            self.assertEqual(len(config["depositCrystalData"]), 1)
            self.assertEqual(len(config["depositGrindableData"]), 1)

    def test_general_fields_use_project_setting_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            labels = {field["key"]: field["label"] for field in controller.fields}

            self.assertEqual(labels["server_number"], "Server number")
            self.assertEqual(labels["auto_start_program"], "Auto start program")

    def test_gacha_side_is_constrained_options_field(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("GACHA")

            side_fields = [
                field for field in controller.fields if field["key"].endswith(":side")
            ]

            self.assertTrue(side_fields)
            self.assertEqual(side_fields[0]["type"], "options")
            self.assertEqual(side_fields[0]["options"], ["left", "right"])

    def test_invalid_gacha_side_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            errors = []
            controller.error.connect(lambda title, message: errors.append((title, message)))

            controller.setValue("gacha:0:side", "banana")

            self.assertEqual(
                errors,
                [("Invalid Gacha Config", "side must be left or right.")],
            )
            self.assertEqual(load_gacha_config(gacha_path)[0]["side"], "left")

    def test_invalid_gacha_model_key_does_not_mutate_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            errors = []
            controller.error.connect(lambda title, message: errors.append((title, message)))
            original = load_gacha_config(gacha_path)

            controller.setValue("gacha:-1:name", "Changed")
            controller.setValue("gacha:bad:name", "Changed")
            controller.setValue("gacha:0:unknown", "Changed")

            self.assertEqual(load_gacha_config(gacha_path), original)
            self.assertEqual(
                errors,
                [
                    ("Invalid Gacha Config", "Unknown gacha index."),
                    ("Invalid Gacha Config", "Unknown gacha index."),
                    ("Invalid Gacha Config", "Unknown gacha field."),
                ],
            )

    def test_invalid_pego_model_key_does_not_mutate_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            errors = []
            controller.error.connect(lambda title, message: errors.append((title, message)))
            original = load_pego_config(pego_path)

            controller.setValue("pego:-1:name", "Changed")
            controller.setValue("pego:bad:name", "Changed")
            controller.setValue("pego:0:unknown", "Changed")
            controller.setValue("pego:0:delay", "bad")

            self.assertEqual(load_pego_config(pego_path), original)
            self.assertEqual(
                errors,
                [
                    ("Invalid Pego Config", "Unknown pego index."),
                    ("Invalid Pego Config", "Unknown pego index."),
                    ("Invalid Pego Config", "Unknown pego field."),
                    (
                        "Invalid Pego Config",
                        "invalid literal for int() with base 10: 'bad'",
                    ),
                ],
            )

    def test_invalid_storage_model_key_does_not_mutate_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_crystal_route", "")
            errors = []
            controller.error.connect(lambda title, message: errors.append((title, message)))
            original = load_deposit_config(deposit_path)

            controller.setValue("storage:crystal:-1:teleport", "Changed")
            controller.setValue("storage:crystal:0:dedi:-1:yaw", "99")
            controller.setValue("storage:missing:0:teleport", "Changed")

            self.assertEqual(load_deposit_config(deposit_path), original)
            self.assertEqual(
                errors,
                [
                    ("Invalid Storage Config", "Unknown storage route index."),
                    ("Invalid Storage Config", "Unknown storage item index."),
                    ("Invalid Storage Config", "Unknown storage route kind."),
                ],
            )


if __name__ == "__main__":
    unittest.main()
