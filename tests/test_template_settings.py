import json
import tempfile
import unittest
from pathlib import Path

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_dedi_item,
    default_deposit_config,
)
from source.launcher.config.constants import DEFAULT_SETTINGS, TEMPLATE_SETTING_KEYS
from source.launcher.config.station_config import default_gacha_pair, default_pego_entry
from source.launcher.config.template_settings import (
    TEMPLATE_TYPE,
    TemplateCatalog,
    build_template,
    convert_deposit_yaw,
    migrate_template_references,
    next_unique_template_filename,
    normalize_template,
    normalize_template_id,
    normalize_yaw,
    resolve_template_reference,
    safe_template_filename,
    scan_templates,
    write_template,
)


def template_document(name: str = "Example") -> dict:
    return {
        "name": name,
        "type": TEMPLATE_TYPE,
        "version": 1,
        "data": {
            "settings": {key: DEFAULT_SETTINGS[key] for key in TEMPLATE_SETTING_KEYS},
            "dedis": default_deposit_config(),
            "gacha": default_gacha_pair(),
            "pego": [default_pego_entry()],
        },
    }


class TemplateSettingsTests(unittest.TestCase):
    def test_v1_normalization_strips_station_yaw_with_warning(self) -> None:
        document = template_document()
        document["data"]["settings"]["station_yaw"] = 55

        normalized, warnings = normalize_template(document)

        self.assertNotIn("station_yaw", normalized["data"]["settings"])
        self.assertEqual(warnings, ["Ignored local-only station_yaw."])

    def test_unsupported_version_is_rejected(self) -> None:
        document = template_document()
        document["version"] = 2

        with self.assertRaisesRegex(ValueError, "Unsupported template version: 2"):
            normalize_template(document)

    def test_missing_required_setting_is_rejected(self) -> None:
        document = template_document()
        del document["data"]["settings"]["lag_offset"]

        with self.assertRaisesRegex(ValueError, "missing: lag_offset"):
            normalize_template(document)

    def test_windows_safe_filename_preserves_display_name_separately(self) -> None:
        self.assertEqual(safe_template_filename("Shen   B_"), "Shen_B_.json")
        self.assertEqual(safe_template_filename("A:B?"), "A_B_.json")
        self.assertEqual(safe_template_filename("CON"), "_CON.json")
        self.assertEqual(safe_template_filename("CON.txt"), "_CON.txt.json")
        self.assertEqual(safe_template_filename("Shen B.json"), "Shen_B.json")
        self.assertEqual(normalize_template_id("Shen B.json"), "Shen B.json")

    def test_yaw_normalization_wraps_to_expected_range(self) -> None:
        self.assertEqual(normalize_yaw(180), -180)
        self.assertEqual(normalize_yaw(540), -180)
        self.assertEqual(normalize_yaw(-181), 179)

    def test_deposit_yaw_round_trip_preserves_pitch(self) -> None:
        data = default_deposit_config()
        route = default_crystal_route()
        item = default_dedi_item()
        item["location"] = {"yaw": -102.58, "pitch": 20.0}
        route["dedi"]["items"].append(item)
        data["depositCrystalData"] = [route]

        exported = convert_deposit_yaw(data, -78.57, True)
        restored = convert_deposit_yaw(exported, 30.0, False)

        exported_location = exported["depositCrystalData"][0]["dedi"]["items"][0][
            "location"
        ]
        restored_location = restored["depositCrystalData"][0]["dedi"]["items"][0][
            "location"
        ]
        self.assertEqual(exported_location, {"yaw": -24.01, "pitch": 20.0})
        self.assertEqual(restored_location, {"yaw": 5.99, "pitch": 20.0})

    def test_build_template_excludes_local_and_assignment_fields(self) -> None:
        settings = DEFAULT_SETTINGS | {
            "lag_offset_template": "Other",
            "station_yaw": 45.0,
        }

        template = build_template(
            "Snapshot",
            settings,
            default_deposit_config(),
            default_gacha_pair(),
            [default_pego_entry()],
        )

        template_settings = template["data"]["settings"]
        self.assertNotIn("station_yaw", template_settings)
        self.assertNotIn("lag_offset_template", template_settings)
        self.assertEqual(template_settings["iguanadon_seed_throw_amount"], 18)
        self.assertEqual(template_settings["time_to_reberry"], 30)

    def test_template_allows_empty_deposit_routes(self) -> None:
        document = template_document()
        document["data"]["dedis"] = {
            "depositCrystalData": [],
            "depositGrindableData": [],
        }

        normalized, _warnings = normalize_template(document)

        self.assertEqual(normalized["data"]["dedis"]["depositCrystalData"], [])
        self.assertEqual(normalized["data"]["dedis"]["depositGrindableData"], [])

    def test_template_preserves_deposit_route_check_interval(self) -> None:
        document = template_document()
        document["data"]["dedis"]["depositCrystalData"][0][
            "check_on_every_dedi"
        ] = 4
        document["data"]["dedis"]["depositGrindableData"][0][
            "check_on_every_dedi"
        ] = 8

        normalized, _warnings = normalize_template(document)

        self.assertEqual(
            normalized["data"]["dedis"]["depositCrystalData"][0][
                "check_on_every_dedi"
            ],
            4,
        )
        self.assertEqual(
            normalized["data"]["dedis"]["depositGrindableData"][0][
                "check_on_every_dedi"
            ],
            8,
        )

    def test_catalog_uses_filenames_and_allows_duplicate_display_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            for filename in ("first.json", "second.json"):
                (directory / filename).write_text(
                    json.dumps(template_document("Duplicate")), encoding="utf-8"
                )

            catalog = scan_templates(directory)

            self.assertEqual(set(catalog.templates), {"first.json", "second.json"})
            self.assertEqual(catalog.templates["first.json"]["name"], "Duplicate")
            self.assertEqual(catalog.errors, {})

    def test_changing_display_name_does_not_change_catalog_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            path = directory / "Stable_ID.json"
            path.write_text(json.dumps(template_document("Old Name")), encoding="utf-8")
            first_catalog = scan_templates(directory)
            path.write_text(json.dumps(template_document("New Name")), encoding="utf-8")
            second_catalog = scan_templates(directory)

            self.assertIn("Stable_ID.json", first_catalog.templates)
            self.assertIn("Stable_ID.json", second_catalog.templates)
            self.assertEqual(
                second_catalog.templates["Stable_ID.json"]["name"], "New Name"
            )

    def test_keep_both_filename_uses_underscores_until_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_template(template_document("Shen B"), "Shen_B.json", directory)
            write_template(template_document("Shen B_"), "Shen_B_.json", directory)
            catalog = scan_templates(directory)

            self.assertEqual(
                next_unique_template_filename("Shen_B.json", catalog),
                "Shen_B__.json",
            )

    def test_write_preserves_explicit_source_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)

            path = write_template(
                template_document("Friendly Name"), "Source File.json", directory
            )

            self.assertEqual(path.name, "Source File.json")
            self.assertIn("Source File.json", scan_templates(directory).templates)

    def test_replacement_keeps_filename_while_display_name_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            path = write_template(
                template_document("Old Name"), "Stable.json", directory
            )

            replacement = write_template(
                template_document("New Name"),
                "Stable.json",
                directory,
                replaced_path=path,
            )

            catalog = scan_templates(directory)
            self.assertEqual(replacement.name, "Stable.json")
            self.assertEqual(catalog.templates["Stable.json"]["name"], "New Name")

    def test_legacy_references_migrate_by_stem_and_display_name(self) -> None:
        template = template_document("Friendly Name")
        catalog = TemplateCatalog(
            {"Stable_ID.json": template},
            {"Stable_ID.json": Path("Stable_ID.json")},
            {},
        )
        settings = {
            "lag_offset_template": "Stable_ID",
            "server_number_template": "Friendly Name",
        }

        migrated, errors = migrate_template_references(settings, catalog)

        self.assertEqual(migrated["lag_offset_template"], "Stable_ID.json")
        self.assertEqual(migrated["server_number_template"], "Stable_ID.json")
        self.assertEqual(errors, {})

    def test_ambiguous_legacy_display_name_is_not_migrated(self) -> None:
        catalog = TemplateCatalog(
            {
                "first.json": template_document("Duplicate"),
                "second.json": template_document("Duplicate"),
            },
            {},
            {},
        )

        resolved, error = resolve_template_reference("Duplicate", catalog)

        self.assertIsNone(resolved)
        self.assertIn("ambiguous", error)


if __name__ == "__main__":
    unittest.main()
