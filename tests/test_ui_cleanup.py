"""File icons, aligned controls, and smooth reusable toggle animations."""

import unittest
from unittest.mock import patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import QPoint, QVariantAnimation
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest

from source.launcher.components.dashboard import line_icon
from source.launcher.components.widgets import CyberCheckBox, CyberSwitch
from source.launcher.config.constants import ASSETS, TOGGLE_TRANSITION_MS
from source.launcher.dashboard_theme import asset_path


class UiCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()
        cls.app = fixture.DashboardRedesignTests.app

    def test_registered_svg_icons_load_and_tint(self):
        for name, path in ASSETS.items():
            if name.startswith("icon.") and path.endswith(".svg"):
                self.assertTrue(QSvgRenderer(asset_path(path)).isValid(), name)
                icon = line_icon(name.removeprefix("icon."), "#F04080")
                image = icon.pixmap(32, 32).toImage()
                colors = [image.pixelColor(x, y) for x in range(32) for y in range(32)]
                opaque = [color for color in colors if color.alpha() > 240]
                self.assertTrue(opaque, name)
                for color in opaque:
                    for actual, expected in zip(
                        (color.red(), color.green(), color.blue()),
                        (240, 64, 128),
                        strict=True,
                    ):
                        self.assertAlmostEqual(actual, expected, delta=2, msg=name)

    def test_launcher_control_edges_and_header_sizes_match(self):
        window = fixture.DashboardRedesignTests.window(self)
        window.show_page("settings")
        window._render_settings_group("LAUNCHER")
        controls = [
            window.auto_keys_activation_key_field,
            window.auto_keys_interval_field,
            window.auto_keys_hold_field,
        ]
        for width in (1000, 1200, 1536, 1920):
            window.resize(width, 1024)
            QTest.qWait(30)
            self.assertEqual(len({field.width() for field in controls}), 1)
            self.assertEqual(
                len({field.mapTo(window, QPoint()).x() for field in controls}), 1
            )
            self.assertEqual({field.height() for field in controls}, {44})
            self.assertEqual(
                window.template_selector.size(), window.template_action_button.size()
            )

    def test_reusable_animation_reverses_and_syncs(self):
        for cls, animation_name, progress_name in (
            (CyberCheckBox, "_check_animation", "_check_progress"),
            (CyberSwitch, "_switch_animation", "_knob_progress"),
        ):
            widget = cls()
            self.addCleanup(widget.close)
            animation = getattr(widget, animation_name)
            self.assertEqual(animation.duration(), TOGGLE_TRANSITION_MS)
            count = len(widget.findChildren(QVariantAnimation))
            widget.setChecked(True)
            animation.setCurrentTime(TOGGLE_TRANSITION_MS // 2)
            middle = getattr(widget, progress_name)
            self.assertGreater(middle, 0)
            self.assertLess(middle, 1)
            widget.setChecked(False)
            self.assertAlmostEqual(getattr(widget, progress_name), middle)
            widget.blockSignals(True)
            widget.setChecked(True)
            widget.blockSignals(False)
            self.assertEqual(getattr(widget, progress_name), 1)
            self.assertEqual(animation.state(), QVariantAnimation.State.Stopped)
            for _ in range(10):
                widget.setChecked(not widget.isChecked())
            self.assertIs(getattr(widget, animation_name), animation)
            self.assertEqual(len(widget.findChildren(QVariantAnimation)), count)

    def test_visible_toggle_has_intermediate_animation_frames(self):
        window = fixture.DashboardRedesignTests.window(self)
        window.show_page("settings")
        window._render_settings_group("LAUNCHER")
        switch = window.fields["allow_focus_ark_window"]
        QTest.qWait(250)
        frames = []
        switch._switch_animation.valueChanged.connect(frames.append)
        with patch.object(window, "persist_single_setting"):
            switch.setChecked(not switch.isChecked())
            QTest.qWait(TOGGLE_TRANSITION_MS + 60)
        self.assertGreaterEqual(len(set(frames)), 7)
        self.assertEqual(switch._knob_progress, float(switch.isChecked()))


if __name__ == "__main__":
    unittest.main()
