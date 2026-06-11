import types
import unittest
from unittest.mock import Mock, patch

from source.gacha_bot.fertilizer_refresh import (
    _close_crop_plot_inventory,
    _open_crop_plot_inventory,
    run_fertilizer_refresh,
)


class StopLoop(RuntimeError):
    pass


class FertilizerRefreshTests(unittest.TestCase):
    def test_prompt_opens_refreshes_closes_then_waits_for_prompt_to_clear(self):
        actions = []
        state = {"open": False, "prompt_checks": 0}

        def prompt_is_visible():
            state["prompt_checks"] += 1
            if state["prompt_checks"] == 3:
                raise StopLoop
            return True

        def open_inventory():
            actions.append("open")
            state["open"] = True

        def close_inventory():
            actions.append("close")
            state["open"] = False

        with self.assertRaises(StopLoop):
            run_fertilizer_refresh(
                poll_interval=0,
                crop_plot_is_open=lambda: state["open"],
                crop_plot_prompt_is_visible=prompt_is_visible,
                inventory_is_open=lambda: state["open"],
                open_inventory=open_inventory,
                close_inventory=close_inventory,
                transfer_all_from=lambda: actions.append("from_plot"),
                transfer_all_inventory=lambda: actions.append("to_plot"),
            )

        self.assertEqual(actions, ["open", "from_plot", "to_plot", "close"])
        self.assertEqual(state["prompt_checks"], 3)

    def test_already_open_crop_plot_refreshes_without_opening_again(self):
        actions = []

        def close_inventory():
            actions.append("close")
            raise StopLoop

        with self.assertRaises(StopLoop):
            run_fertilizer_refresh(
                poll_interval=0,
                crop_plot_is_open=lambda: True,
                crop_plot_prompt_is_visible=lambda: False,
                inventory_is_open=lambda: True,
                open_inventory=lambda: actions.append("open"),
                close_inventory=close_inventory,
                transfer_all_from=lambda: actions.append("from_plot"),
                transfer_all_inventory=lambda: actions.append("to_plot"),
            )

        self.assertEqual(actions, ["from_plot", "to_plot", "close"])

    def test_failed_open_closes_wrong_inventory_and_waits_for_prompt_to_clear(self):
        actions = []
        prompt_checks = 0

        def prompt_is_visible():
            nonlocal prompt_checks
            prompt_checks += 1
            if prompt_checks == 3:
                raise StopLoop
            return True

        with self.assertRaises(StopLoop):
            run_fertilizer_refresh(
                poll_interval=0,
                crop_plot_is_open=lambda: False,
                crop_plot_prompt_is_visible=prompt_is_visible,
                inventory_is_open=lambda: True,
                open_inventory=lambda: actions.append("open"),
                close_inventory=lambda: actions.append("close"),
                transfer_all_from=lambda: actions.append("from_plot"),
                transfer_all_inventory=lambda: actions.append("to_plot"),
            )

        self.assertEqual(actions, ["open", "close"])
        self.assertEqual(prompt_checks, 3)

    def test_default_inventory_wrappers_use_local_open(self):
        inventory = types.SimpleNamespace(
            is_open=Mock(return_value=False),
            transfer_all_from=Mock(),
        )
        structures = types.ModuleType("source.ASA.strucutres")
        structures.inventory = inventory

        with (
            patch.dict("sys.modules", {"source.ASA.strucutres": structures}),
            patch(
                "source.gacha_bot.fertilizer_refresh._open_crop_plot_inventory",
                side_effect=StopLoop,
            ) as open_inventory,
        ):
            with self.assertRaises(StopLoop):
                run_fertilizer_refresh(
                    poll_interval=0,
                    crop_plot_is_open=lambda: False,
                    crop_plot_prompt_is_visible=lambda: True,
                    transfer_all_inventory=Mock(),
                )

        open_inventory.assert_called_once_with()


class FertilizerLocalInventoryTests(unittest.TestCase):
    def test_local_open_retries_until_inventory_opens(self):
        template = types.SimpleNamespace(
            check_template=Mock(side_effect=[False, True, False]),
            template_await_true=Mock(return_value=True),
            template_await_false=Mock(),
        )
        utils = types.SimpleNamespace(press_key=Mock())
        logs = types.SimpleNamespace(logger=types.SimpleNamespace(debug=Mock(), error=Mock()))

        with patch.dict(
            "sys.modules",
            {
                "settings": types.SimpleNamespace(lag_offset=0),
                "source.logs.gachalogs": logs,
            },
        ), patch("source.utility.template", template, create=True), patch(
            "source.utility.utils", utils, create=True
        ):
            _open_crop_plot_inventory()

        utils.press_key.assert_called_once_with("AccessInventory")

    def test_local_close_retries_until_inventory_closes(self):
        template = types.SimpleNamespace(
            check_template=Mock(side_effect=[True, False]),
            template_await_false=Mock(),
        )
        variables = types.SimpleNamespace(get_pixel_loc=Mock(return_value=0))
        windows = types.SimpleNamespace(click=Mock())
        logs = types.SimpleNamespace(logger=types.SimpleNamespace(debug=Mock(), error=Mock()))

        with patch.dict(
            "sys.modules",
            {
                "settings": types.SimpleNamespace(lag_offset=0),
                "source.logs.gachalogs": logs,
            },
        ), patch("source.utility.template", template, create=True), patch(
            "source.utility.variables", variables, create=True
        ), patch("source.utility.windows", windows, create=True):
            _close_crop_plot_inventory()

        windows.click.assert_called_once_with(0, 0)


if __name__ == "__main__":
    unittest.main()
