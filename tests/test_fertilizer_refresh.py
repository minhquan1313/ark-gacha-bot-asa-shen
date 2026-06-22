import importlib
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch


def _module(name: str, **attributes: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


settings = _module("settings", lag_offset=0)
asa_config = _module(
    "source.ASA.config",
    inventory_open_attempts=3,
    inventory_close_attempts=3,
)
inventory = _module(
    "source.ASA.strucutres.inventory",
    open=Mock(),
    close=Mock(),
    is_open=Mock(return_value=False),
    transfer_all_from=Mock(),
)
player_inventory = _module(
    "source.ASA.player.player_inventory",
    transfer_all_inventory=Mock(),
)
logs = _module(
    "source.logs.gachalogs",
    logger=types.SimpleNamespace(debug=Mock(), error=Mock()),
)
template = _module(
    "source.utility.template",
    check_template=Mock(return_value=False),
    check_template_no_bounds=Mock(return_value=False),
    template_await_false=Mock(),
)
with patch.dict(
    sys.modules,
    {
        "settings": settings,
        "source.ASA.config": asa_config,
        "source.ASA.strucutres.inventory": inventory,
        "source.ASA.player.player_inventory": player_inventory,
        "source.logs.gachalogs": logs,
        "source.utility.template": template,
    },
):
    fertilizer_refresh = importlib.import_module("source.gacha_bot.fertilizer_refresh")


class StopLoop(RuntimeError):
    pass


class FertilizerRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        inventory.is_open.reset_mock(return_value=True, side_effect=True)
        inventory.is_open.return_value = False
        inventory.transfer_all_from.reset_mock(return_value=True, side_effect=True)
        player_inventory.transfer_all_inventory.reset_mock(
            return_value=True, side_effect=True
        )
        template.check_template.reset_mock(return_value=True, side_effect=True)
        template.check_template.return_value = False
        template.check_template_no_bounds.reset_mock(
            return_value=True, side_effect=True
        )
        template.check_template_no_bounds.return_value = False

    def test_prompt_opens_refreshes_closes_then_waits_for_prompt_to_clear(self):
        actions = []
        template.check_template.side_effect = [False, True]
        template.check_template_no_bounds.side_effect = [True, True, StopLoop]
        inventory.transfer_all_from.side_effect = lambda: actions.append("from_plot")
        player_inventory.transfer_all_inventory.side_effect = lambda: actions.append(
            "to_plot"
        )

        with (
            patch.object(
                fertilizer_refresh,
                "_open_crop_plot_inventory",
                side_effect=lambda: actions.append("open"),
            ),
            patch.object(
                fertilizer_refresh,
                "_close_crop_plot_inventory",
                side_effect=lambda: actions.append("close"),
            ),
            patch.object(fertilizer_refresh.time, "sleep"),
            self.assertRaises(StopLoop),
        ):
            fertilizer_refresh.run_fertilizer_refresh()

        self.assertEqual(actions, ["open", "from_plot", "to_plot", "close"])

    def test_already_open_crop_plot_refreshes_without_opening_again(self):
        actions = []
        template.check_template.return_value = True
        inventory.transfer_all_from.side_effect = lambda: actions.append("from_plot")
        player_inventory.transfer_all_inventory.side_effect = lambda: actions.append(
            "to_plot"
        )

        def close_inventory():
            actions.append("close")
            raise StopLoop

        with (
            patch.object(
                fertilizer_refresh, "_open_crop_plot_inventory"
            ) as open_inventory,
            patch.object(
                fertilizer_refresh,
                "_close_crop_plot_inventory",
                side_effect=close_inventory,
            ),
            self.assertRaises(StopLoop),
        ):
            fertilizer_refresh.run_fertilizer_refresh()

        self.assertEqual(actions, ["from_plot", "to_plot", "close"])
        open_inventory.assert_not_called()

    def test_failed_open_closes_wrong_inventory_and_waits_for_prompt_to_clear(self):
        actions = []
        template.check_template.return_value = False
        template.check_template_no_bounds.side_effect = [True, True, StopLoop]
        inventory.is_open.return_value = True

        with (
            patch.object(
                fertilizer_refresh,
                "_open_crop_plot_inventory",
                side_effect=lambda: actions.append("open"),
            ),
            patch.object(
                fertilizer_refresh,
                "_close_crop_plot_inventory",
                side_effect=lambda: actions.append("close"),
            ),
            patch.object(fertilizer_refresh.time, "sleep"),
            self.assertRaises(StopLoop),
        ):
            fertilizer_refresh.run_fertilizer_refresh()

        self.assertEqual(actions, ["open", "close"])
        self.assertEqual(template.check_template_no_bounds.call_count, 3)


class FertilizerLocalInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        inventory.open.reset_mock(return_value=True, side_effect=True)
        inventory.close.reset_mock(return_value=True, side_effect=True)
        inventory.is_open.reset_mock(return_value=True, side_effect=True)
        template.check_template.reset_mock(return_value=True, side_effect=True)
        template.template_await_false.reset_mock(return_value=True, side_effect=True)
        logs.logger.debug.reset_mock()
        logs.logger.error.reset_mock()

    def test_local_open_retries_until_inventory_opens(self):
        template.check_template.side_effect = [False, False]
        inventory.is_open.side_effect = [False, True]

        with patch.object(fertilizer_refresh.time, "sleep"):
            fertilizer_refresh._open_crop_plot_inventory()

        self.assertEqual(inventory.open.call_count, 2)
        self.assertEqual(inventory.is_open.call_count, 2)
        logs.logger.error.assert_not_called()

    def test_local_close_retries_until_inventory_closes(self):
        template.check_template.side_effect = [True, False]
        with patch.object(fertilizer_refresh.time, "sleep"):
            fertilizer_refresh._close_crop_plot_inventory()

        inventory.close.assert_called_once_with()


class FertilizerRunnerTests(unittest.TestCase):
    def test_runner_emits_ready_after_import_before_starting_tool(self):
        from source.launcher.components import helper_runner

        calls = []
        runtime_module = _module(
            "source.gacha_bot.fertilizer_refresh",
            run_fertilizer_refresh=Mock(
                side_effect=lambda _status: calls.append("run")
            ),
        )
        output = io.StringIO()

        with (
            patch.dict(
                sys.modules,
                {"source.gacha_bot.fertilizer_refresh": runtime_module},
            ),
            redirect_stdout(output),
        ):
            result = helper_runner.run_fertilizer_refresh(types.SimpleNamespace())

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["run"])
        self.assertEqual(
            output.getvalue().splitlines(),
            [helper_runner.READY_MESSAGE, "__HELPER_RESULT__ Stopped."],
        )

    def test_runner_does_not_emit_ready_when_import_fails(self):
        from source.launcher.components import helper_runner

        output = io.StringIO()
        with (
            patch.dict(
                sys.modules,
                {"source.gacha_bot.fertilizer_refresh": None},
            ),
            redirect_stdout(output),
            self.assertRaises(ModuleNotFoundError),
        ):
            helper_runner.run_fertilizer_refresh(types.SimpleNamespace())

        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
