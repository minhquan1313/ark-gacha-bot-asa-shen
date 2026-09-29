"""Pixel-level cover opacity and border checks at fractional display scales."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from source.launcher.components.cover_painting import painted_cover  # noqa: E402
from source.launcher.config.constants import COVER_OVERLAY_COLOR  # noqa: E402


class CoverPaintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def render(self, ratio: float, bottom_lip: float = 0):
        """Draw white artwork into a transparent high-DPI surface."""
        result = QImage(
            round(200 * ratio),
            round(80 * ratio),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        result.setDevicePixelRatio(ratio)
        result.fill(Qt.GlobalColor.transparent)
        art = QPixmap(200, 80)
        art.fill(Qt.GlobalColor.white)
        painter = QPainter(result)
        with (
            patch(
                "source.launcher.components.cover_painting.COVER_OVERLAY_STOPS",
                ((0.0, 0.50), (0.5, 0.20), (1.0, 0.05)),
            ),
            painted_cover(
                painter,
                QRectF(0, 0, 200, 80),
                11,
                art,
                QPointF(),
                QPen(QColor("#00D9FF"), 1),
                QColor("black"),
                QRectF(0, 0, 200, 80),
                bottom_lip=bottom_lip,
                drop_start=60,
            ),
        ):
            pass
        painter.end()
        return result

    def test_rounded_lip_clips_artwork_and_keeps_continuous_outline(self):
        for ratio in (1.0, 1.25, 1.5):
            result = self.render(ratio, bottom_lip=12)
            self.assertEqual(result.pixelColor(0, 0).alpha(), 0)
            self.assertEqual(
                result.pixelColor(round(9 * ratio), round(9 * ratio)).alpha(), 255
            )
            self.assertEqual(
                result.pixelColor(round(25 * ratio), round(74 * ratio)).alpha(), 0
            )
            self.assertEqual(
                result.pixelColor(round(100 * ratio), round(74 * ratio)).alpha(), 255
            )
            # The drop stays filled all the way to the rounded right corner.
            for x in range(86, 188):
                self.assertEqual(
                    result.pixelColor(round(x * ratio), round(74 * ratio)).alpha(), 255
                )
            for x in range(60, 85):
                self.assertTrue(
                    any(
                        result.pixelColor(round(x * ratio), y).alpha()
                        for y in range(round(67 * ratio), round(80 * ratio))
                    )
                )
            self.assertGreater(result.pixelColor(result.width() // 2, 0).alpha(), 240)

    def test_horizontal_opacity_without_uniform_tint(self):
        tint = QColor(COVER_OVERLAY_COLOR)
        for ratio in (1.0, 1.25, 1.5):
            result = self.render(ratio)
            for position, opacity in ((0.02, 0.488), (0.5, 0.20), (0.98, 0.056)):
                pixel = result.pixelColor(
                    round(200 * ratio * position), round(40 * ratio)
                )
                for actual, overlay in zip(
                    (pixel.red(), pixel.green(), pixel.blue()),
                    (tint.red(), tint.green(), tint.blue()),
                    strict=True,
                ):
                    self.assertAlmostEqual(
                        actual, 255 * (1 - opacity) + overlay * opacity, delta=2
                    )

    def test_corners_are_symmetric_and_border_is_not_clipped(self):
        for ratio in (1.0, 1.25, 1.5):
            result = self.render(ratio)
            width, height = result.width(), result.height()
            self.assertEqual(result.pixelColor(0, 0).alpha(), 0)
            self.assertGreater(result.pixelColor(width // 2, 0).alpha(), 240)
            for x in range(round(14 * ratio)):
                for y in range(round(14 * ratio)):
                    alpha = result.pixelColor(x, y).alpha()
                    # Qt's rasterizer rounds opposing fractional curve coverage differently.
                    self.assertAlmostEqual(
                        alpha, result.pixelColor(width - x - 1, y).alpha(), delta=16
                    )
                    self.assertAlmostEqual(
                        alpha, result.pixelColor(x, height - y - 1).alpha(), delta=16
                    )


if __name__ == "__main__":
    unittest.main()
