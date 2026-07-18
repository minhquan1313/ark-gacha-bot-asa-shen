import importlib
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, call, patch


def _module(name: str, **attributes: object):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


pyautogui = _module("pyautogui", click=Mock(), press=Mock())
template = _module(
    "source.utility.template",
    register_roi=Mock(),
    check_template_no_bounds=Mock(return_value=False),
)
with patch.dict(
    sys.modules,
    {
        "pyautogui": pyautogui,
        "source.utility.template": template,
    },
):
    auto_fishing = importlib.import_module("source.gacha_bot.auto_fishing")


class StopLoop(RuntimeError):
    pass


class AutoFishingTests(unittest.TestCase):
    def setUp(self) -> None:
        pyautogui.click.reset_mock()
        pyautogui.press.reset_mock()
        template.register_roi.reset_mock()
        template.check_template_no_bounds.reset_mock(return_value=True, side_effect=True)
        template.check_template_no_bounds.return_value = False
        auto_fishing.registered = False

    def test_registers_all_templates_with_independent_empty_rois(self):
        auto_fishing.register_template_roi()

        registered = template.register_roi.call_args.args[0]
        self.assertEqual(set(registered), set(auto_fishing.FISHING_TEMPLATES))
        self.assertEqual(len(registered), 12)
        for region in registered.values():
            self.assertEqual(
                region,
                {"start_x": 0, "start_y": 0, "width": 0, "height": 0},
            )
        self.assertEqual(len({id(region) for region in registered.values()}), 12)
        self.assertEqual(
            auto_fishing.FISHING_KEY_TEMPLATES,
            {
                "fishing_press_q": "q",
                "fishing_press_w": "w",
                "fishing_press_e": "e",
                "fishing_press_a": "a",
                "fishing_press_s": "s",
                "fishing_press_d": "d",
                "fishing_press_z": "z",
                "fishing_press_x": "x",
                "fishing_press_c": "c",
            },
        )

    def test_cast_clicks_every_interval_until_prompt_appears(self):
        template.check_template_no_bounds.side_effect = [False, False, True]

        with patch.object(auto_fishing.time, "sleep") as sleep:
            auto_fishing._cast_until_prompt(Mock())

        self.assertEqual(pyautogui.click.call_count, 2)
        sleep.assert_has_calls(
            [
                call(auto_fishing.CLICK_INTERVAL),
                call(auto_fishing.CLICK_INTERVAL),
            ]
        )

    def test_requested_key_repeats_until_template_disappears(self):
        template.check_template_no_bounds.side_effect = [True, True, False]

        with patch.object(auto_fishing.time, "sleep") as sleep:
            auto_fishing._press_requested_key(
                "fishing_press_q",
                "q",
                Mock(),
            )

        self.assertEqual(pyautogui.press.call_args_list, [call("q"), call("q")])
        sleep.assert_has_calls(
            [
                call(auto_fishing.KEY_PRESS_INTERVAL),
                call(auto_fishing.KEY_PRESS_INTERVAL),
            ]
        )

    def test_single_run_handles_multiple_keys_then_waits_and_stops(self):
        actions = []
        rounds = iter(
            [
                ("fishing_press_q", "q"),
                ("fishing_press_c", "c"),
                None,
            ]
        )

        with (
            patch.object(
                auto_fishing,
                "_cast_until_prompt",
                side_effect=lambda _status: actions.append("cast"),
            ),
            patch.object(auto_fishing, "_find_requested_key", side_effect=rounds),
            patch.object(
                auto_fishing,
                "_press_requested_key",
                side_effect=lambda template_name, key, _status: actions.append(
                    (template_name, key)
                ),
            ),
            patch.object(
                auto_fishing,
                "_is_visible",
                side_effect=lambda name: name == "fishing_success"
                and len(actions) == 3,
            ),
            patch.object(auto_fishing.time, "sleep") as sleep,
        ):
            auto_fishing.run_auto_fishing(False)

        self.assertEqual(
            actions,
            [
                "cast",
                ("fishing_press_q", "q"),
                ("fishing_press_c", "c"),
            ],
        )
        sleep.assert_called_with(auto_fishing.RESULT_DELAY)

    def test_infinite_mode_returns_to_casting_after_result(self):
        casts = 0

        def cast(_status):
            nonlocal casts
            casts += 1
            if casts == 2:
                raise StopLoop

        with (
            patch.object(auto_fishing, "_cast_until_prompt", side_effect=cast),
            patch.object(auto_fishing, "_wait_for_result", return_value="failed"),
            patch.object(auto_fishing.time, "sleep") as sleep,
            self.assertRaises(StopLoop),
        ):
            auto_fishing.run_auto_fishing(True)

        self.assertEqual(casts, 2)
        sleep.assert_called_once_with(auto_fishing.RESULT_DELAY)


class AutoFishingRunnerTests(unittest.TestCase):
    def test_runner_forwards_infinite_and_emits_ready_and_result(self):
        from source.launcher.components import helper_runner

        runtime = _module(
            "source.gacha_bot.auto_fishing",
            run_auto_fishing=Mock(),
        )
        output = io.StringIO()

        with (
            patch.dict(sys.modules, {runtime.__name__: runtime}),
            redirect_stdout(output),
        ):
            result = helper_runner.run_auto_fishing(
                types.SimpleNamespace(infinite=True)
            )

        self.assertEqual(result, 0)
        runtime.run_auto_fishing.assert_called_once_with(
            True,
        )
        self.assertEqual(
            output.getvalue().splitlines(),
            [helper_runner.READY_MESSAGE, "__HELPER_COMPLETION__ Finished."],
        )


if __name__ == "__main__":
    unittest.main()
