import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source.gacha_bot.deposit_config import default_deposit_config, load_deposit_config
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.station_config import (
    default_gacha_pair,
    default_pego_entry,
    load_gacha_config,
    load_pego_config,
)


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

    def test_storage_route_fields_expose_payload_helper_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("STORAGE")

            crystal_row = next(
                field for field in controller.fields if field["label"] == "Crystal route 1"
            )
            grindable_row = next(
                field
                for field in controller.fields
                if field["label"] == "Grindable route 1"
            )

            self.assertEqual(
                crystal_row["actions"],
                [
                    {
                        "key": "open_helper:deposit",
                        "label": "OPEN HELPER",
                        "value": {"routeKind": "crystal", "routeIndex": 0},
                        "variant": "primary",
                    }
                ],
            )
            self.assertEqual(
                grindable_row["actions"][0]["value"],
                {"routeKind": "grindable", "routeIndex": 0},
            )

    def test_position_and_storage_groups_expose_helper_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.setGroup("POSITION / RENDER")
            position_keys = [action["key"] for action in controller.groupActions]

            controller.setGroup("STORAGE")
            storage_keys = [action["key"] for action in controller.groupActions]

            self.assertIn("open_helper:position", position_keys)
            self.assertIn("open_helper:deposit", storage_keys)

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

    def test_reset_visible_resets_gacha_config_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_gacha_pair", "")
            controller.setGroup("GACHA")

            controller.resetVisible()

            self.assertEqual(load_gacha_config(gacha_path), default_gacha_pair())

    def test_reset_visible_resets_pego_config_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_pego", "")
            controller.setValue("pego:0:delay", "123")
            controller.setGroup("PEGO")

            controller.resetVisible()

            self.assertEqual(load_pego_config(pego_path), [default_pego_entry()])

    def test_reset_visible_resets_storage_config_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_crystal_route", "")
            controller.runGroupAction("add_grindable_route", "")
            controller.setValue("storage:crystal:0:teleport", "Changed")
            controller.setGroup("STORAGE")

            controller.resetVisible()

            self.assertEqual(load_deposit_config(deposit_path), default_deposit_config())

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

    def test_gacha_and_pego_teleport_fields_expose_copy_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.setGroup("GACHA")
            gacha_teleport = next(
                field
                for field in controller.fields
                if field["key"] == "gacha:0:teleporter"
            )

            controller.setGroup("PEGO")
            pego_teleport = next(
                field
                for field in controller.fields
                if field["key"] == "pego:0:teleporter"
            )

            self.assertEqual(gacha_teleport["actionLabel"], "COPY")
            self.assertEqual(gacha_teleport["actionValue"], gacha_teleport["value"])
            self.assertEqual(pego_teleport["actionLabel"], "COPY")
            self.assertEqual(pego_teleport["actionValue"], pego_teleport["value"])

    def test_gacha_fields_expose_group_and_row_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            entries = load_gacha_config(gacha_path)
            entries.pop()
            __import__(
                "source.launcher.station_config",
                fromlist=["save_gacha_config"],
            ).save_gacha_config(entries, gacha_path)

            controller.setGroup("GACHA")

            group_row = next(
                field
                for field in controller.fields
                if field["type"] == "summary" and "(1/2)" in field["label"]
            )
            name_row = next(
                field for field in controller.fields if field["key"] == "gacha:0:name"
            )

            self.assertIn(
                "ADD GACHA",
                [action["label"] for action in group_row["actions"]],
            )
            self.assertIn(
                "REMOVE GROUP",
                [action["label"] for action in group_row["actions"]],
            )
            self.assertIn(
                "REMOVE",
                [action["label"] for action in name_row["actions"]],
            )

    def test_gacha_fields_expose_group_teleporter_editor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("GACHA")

            group_teleporter = next(
                field
                for field in controller.fields
                if field["key"] == "gacha_group:0:teleporter"
            )

            self.assertEqual(group_teleporter["label"], "Group teleporter")
            self.assertEqual(group_teleporter["value"], "GACHAPAIR_1")

    def test_gacha_group_teleporter_editor_updates_whole_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.setValue("gacha_group:0:teleporter", "GACHAPAIR_MAIN")

            entries = load_gacha_config(gacha_path)
            self.assertEqual(
                [entry["teleporter"] for entry in entries],
                ["GACHAPAIR_MAIN", "GACHAPAIR_MAIN"],
            )

    def test_gacha_fields_expose_legacy_optional_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            entries = load_gacha_config(gacha_path)
            entries[0]["depo_tp"] = "DEPO"
            entries[0]["resource_type"] = "collect"
            __import__(
                "source.launcher.station_config",
                fromlist=["save_gacha_config"],
            ).save_gacha_config(entries, gacha_path)

            controller.setGroup("GACHA")

            depo_tp = next(
                field for field in controller.fields if field["key"] == "gacha:0:depo_tp"
            )
            resource_type = next(
                field
                for field in controller.fields
                if field["key"] == "gacha:0:resource_type"
            )

            self.assertEqual(depo_tp["value"], "DEPO")
            self.assertEqual(resource_type["type"], "options")
            self.assertEqual(resource_type["value"], "collect")
            self.assertEqual(resource_type["options"], ["", "collect"])

    def test_gacha_legacy_optional_fields_update_and_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )

            controller.setValue("gacha:0:depo_tp", "DEPO")
            controller.setValue("gacha:0:resource_type", "collect")

            entry = load_gacha_config(gacha_path)[0]
            self.assertEqual(entry["depo_tp"], "DEPO")
            self.assertEqual(entry["resource_type"], "collect")

            controller.setValue("gacha:0:depo_tp", "")
            controller.setValue("gacha:0:resource_type", "")

            entry = load_gacha_config(gacha_path)[0]
            self.assertNotIn("depo_tp", entry)
            self.assertNotIn("resource_type", entry)

    def test_gacha_fields_warn_about_risky_teleporter_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            entries = load_gacha_config(gacha_path)
            entries[0]["teleporter"] = "GACHAPAIR2"
            entries[1]["teleporter"] = "GACHAPAIR20"
            __import__(
                "source.launcher.station_config",
                fromlist=["save_gacha_config"],
            ).save_gacha_config(entries, gacha_path)

            controller.setGroup("GACHA")

            risky_row = next(
                field
                for field in controller.fields
                if field["type"] == "summary" and "GACHAPAIR2" in field["label"]
            )

            self.assertIn("WARNING", risky_row["label"])
            self.assertIn("may match longer teleport names", risky_row["warning"])

    def test_gacha_field_actions_mutate_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            entries = load_gacha_config(gacha_path)
            entries.pop()
            __import__(
                "source.launcher.station_config",
                fromlist=["save_gacha_config"],
            ).save_gacha_config(entries, gacha_path)

            controller.runFieldAction("add_gacha_to_group", "GACHAPAIR_1")
            self.assertEqual(len(load_gacha_config(gacha_path)), 2)

            controller.runFieldAction("remove_gacha", 1)
            self.assertEqual(len(load_gacha_config(gacha_path)), 1)

    def test_gacha_group_remove_action_mutates_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_gacha_pair", "")

            controller.runFieldAction("remove_gacha_group", "GACHAPAIR_1")

            entries = load_gacha_config(gacha_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual({entry["teleporter"] for entry in entries}, {"GACHAPAIR_2"})

    def test_gacha_auto_fill_requires_confirmation_before_mutating_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            confirmations = []
            controller.fieldActionConfirmationRequested.connect(
                lambda title, message, confirm_text, value: confirmations.append(
                    (title, message, confirm_text, value)
                )
            )
            entries = load_gacha_config(gacha_path)
            for entry in entries:
                entry["teleporter"] = "bad_name"
                entry["name"] = "bad"
            __import__(
                "source.launcher.station_config",
                fromlist=["save_gacha_config"],
            ).save_gacha_config(entries, gacha_path)
            original = load_gacha_config(gacha_path)

            controller.runFieldAction("auto_fill_gacha_group", "bad_name")

            self.assertEqual(load_gacha_config(gacha_path), original)
            self.assertEqual(confirmations[0][0], "Auto Fill Gacha Group")
            self.assertEqual(confirmations[0][2], "AUTO FILL")
            self.assertEqual(confirmations[0][3], "bad_name")

            controller.confirmFieldAction("auto_fill_gacha_group", "bad_name")

            entries = load_gacha_config(gacha_path)
            self.assertEqual({entry["teleporter"] for entry in entries}, {"GACHAPAIR_1"})
            self.assertEqual({entry["side"] for entry in entries}, {"left", "right"})

    def test_pego_fields_expose_row_remove_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, _pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.setGroup("PEGO")

            name_row = next(
                field for field in controller.fields if field["key"] == "pego:0:name"
            )

            self.assertIn(
                "REMOVE",
                [action["label"] for action in name_row["actions"]],
            )

    def test_pego_row_remove_action_mutates_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller, _gacha_path, pego_path, _deposit_path = self.make_controller(
                Path(temp_dir)
            )
            controller.runGroupAction("add_pego", "")

            controller.runFieldAction("remove_pego", 0)

            entries = load_pego_config(pego_path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["name"], "pego2")

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
