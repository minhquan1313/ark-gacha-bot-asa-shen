import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class FakeArray:
    def __init__(self, values, shape=None) -> None:
        self.values = list(values)
        self.shape = shape or (len(self.values),)

    def copy(self):
        return FakeArray(self.values.copy(), self.shape)


def _fake_mean(array: FakeArray):
    return sum(array.values) / len(array.values)


def _fake_absdiff(before: FakeArray, after: FakeArray):
    values = [abs(left - right) for left, right in zip(before.values, after.values)]
    return FakeArray(values, before.shape)


def _load_template_module():
    fake_np = types.ModuleType("numpy")
    fake_np.ndarray = FakeArray
    fake_np.array = lambda value: tuple(value)
    fake_np.mean = _fake_mean
    fake_np.count_nonzero = lambda _value: 0

    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.COLOR_BGR2HSV = 1
    fake_cv2.COLOR_BGR2GRAY = 2
    fake_cv2.cvtColor = Mock(side_effect=lambda image, _code: image)
    fake_cv2.inRange = Mock(return_value=FakeArray([1, 1, 1, 1], (2, 2)))
    fake_cv2.bitwise_and = Mock(side_effect=lambda image, _same, **_kwargs: image)
    fake_cv2.absdiff = Mock(side_effect=_fake_absdiff)
    fake_cv2.matchTemplate = Mock()
    fake_cv2.minMaxLoc = Mock()
    fake_cv2.imread = Mock()

    fake_screen = types.ModuleType("source.utility.screen")
    fake_screen.get_screen_roi = Mock()

    module_path = Path(__file__).resolve().parents[1] / "source" / "utility" / "template.py"
    spec = importlib.util.spec_from_file_location("template_capture_compare_under_test", module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "numpy": fake_np,
            "cv2": fake_cv2,
            "source.utility.screen": fake_screen,
        },
    ):
        spec.loader.exec_module(module)
    return module


class TemplateCaptureCompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = _load_template_module()

    def test_capture_compare_region_uses_item_region_and_bounds(self):
        roi = FakeArray([0, 0, 0, 0], (2, 2, 3))
        self.template.get_region_roi = Mock(return_value=roi)

        capture = self.template.capture_compare_region("item_fertilizer")

        self.template.get_region_roi.assert_called_once_with(
            self.template.roi_regions["item_fertilizer"]
        )
        self.template.cv2.inRange.assert_called_once_with(
            roi,
            tuple(self.template.template_l_bounds_overwrite["item_fertilizer"]),
            tuple(self.template.template_u_bounds_overwrite["item_fertilizer"]),
        )
        self.template.cv2.bitwise_and.assert_called_once()
        self.assertIs(capture, roi)

    def test_masked_gray_capture_can_use_explicit_no_bounds(self):
        roi = FakeArray([0, 0, 0, 0], (2, 2, 3))

        self.template._masked_gray_capture(
            "item_fertilizer",
            roi,
            [0, 0, 0],
            [255, 255, 255],
        )

        self.template.cv2.inRange.assert_called_once_with(
            roi,
            (0, 0, 0),
            (255, 255, 255),
        )

    def test_compare_captures_returns_zero_for_identical_images(self):
        image = FakeArray([0, 0, 0, 0], (2, 2))

        self.assertEqual(self.template.compare_captures(image, image.copy()), 0.0)

    def test_compare_captures_returns_positive_score_for_different_images(self):
        before = FakeArray([0, 0, 0, 0], (2, 2))
        after = FakeArray([0, 255, 0, 0], (2, 2))

        self.assertGreater(self.template.compare_captures(before, after), 0.0)

    def test_compare_captures_accepts_threshold(self):
        before = FakeArray([0, 0, 0, 0], (2, 2))
        after = FakeArray([0, 255, 0, 0], (2, 2))

        self.assertFalse(self.template.compare_captures(before, after, 0.26))
        self.assertTrue(self.template.compare_captures(before, after, 0.25))

    def test_compare_captures_rejects_shape_mismatch(self):
        before = FakeArray([0, 0, 0, 0], (2, 2))
        after = FakeArray([0, 0, 0, 0, 0, 0], (3, 2))

        with self.assertRaisesRegex(ValueError, "same shape"):
            self.template.compare_captures(before, after)

    def test_capture_compare_changed_uses_threshold(self):
        before = FakeArray([0, 0, 0, 0], (2, 2))
        after = FakeArray([0, 255, 0, 0], (2, 2))
        self.template.capture_compare_region = Mock(return_value=after)

        self.assertFalse(
            self.template.capture_compare_changed("item_fertilizer", before, 0.26)
        )
        self.assertTrue(
            self.template.capture_compare_changed("item_fertilizer", before, 0.25)
        )


if __name__ == "__main__":
    unittest.main()
