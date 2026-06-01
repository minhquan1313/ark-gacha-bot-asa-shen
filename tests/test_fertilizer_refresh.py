import threading
import types
import unittest
from unittest.mock import Mock, patch

from source.gacha_bot.fertilizer_refresh import (
    _close_crop_plot_inventory,
    _open_crop_plot_inventory,
    _template_await_false,
    _template_await_true,
    run_fertilizer_refresh,
)


class FertilizerRefreshTests(unittest.TestCase):
    def test_prompt_opens_refreshes_closes_then_waits_for_prompt_to_clear(self):
        stop_event = threading.Event()
        actions = []
        state = {"open": False, "prompt_checks": 0}

        def prompt_is_visible():
            state["prompt_checks"] += 1
            if state["prompt_checks"] == 3:
                stop_event.set()
                return False
            return True

        def open_inventory():
            actions.append("open")
            state["open"] = True

        def close_inventory():
            actions.append("close")
            state["open"] = False

        run_fertilizer_refresh(
            stop_event,
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
        stop_event = threading.Event()
        actions = []

        def close_inventory():
            actions.append("close")
            stop_event.set()

        run_fertilizer_refresh(
            stop_event,
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
        stop_event = threading.Event()
        actions = []
        prompt_checks = 0

        def prompt_is_visible():
            nonlocal prompt_checks
            prompt_checks += 1
            if prompt_checks == 3:
                stop_event.set()
                return False
            return True

        run_fertilizer_refresh(
            stop_event,
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

    def test_does_not_open_or_transfer_until_prompt_is_detected(self):
        stop_event = threading.Event()
        actions = []
        checks = 0

        def crop_plot_is_open():
            nonlocal checks
            checks += 1
            if checks == 3:
                stop_event.set()
            return False

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=crop_plot_is_open,
            crop_plot_prompt_is_visible=lambda: False,
            inventory_is_open=lambda: False,
            open_inventory=lambda: actions.append("open"),
            close_inventory=lambda: actions.append("close"),
            transfer_all_from=lambda: actions.append("from_plot"),
            transfer_all_inventory=lambda: actions.append("to_plot"),
        )

        self.assertEqual(actions, [])
        self.assertEqual(checks, 3)

    def test_stop_between_transfers_exits_without_transfer_back_or_close(self):
        stop_event = threading.Event()
        actions = []

        def transfer_all_from():
            actions.append("from_plot")
            stop_event.set()

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=lambda: True,
            crop_plot_prompt_is_visible=lambda: False,
            inventory_is_open=lambda: True,
            open_inventory=lambda: actions.append("open"),
            close_inventory=lambda: actions.append("close"),
            transfer_all_from=transfer_all_from,
            transfer_all_inventory=lambda: actions.append("to_plot"),
        )

        self.assertEqual(actions, ["from_plot"])

    def test_stop_while_waiting_for_prompt_clear_exits_without_reopening(self):
        stop_event = threading.Event()
        actions = []
        state = {"open": False}

        def open_inventory():
            actions.append("open")
            state["open"] = True

        def close_inventory():
            actions.append("close")
            state["open"] = False

        def prompt_is_visible():
            if actions and actions[-1] == "close":
                stop_event.set()
            return True

        run_fertilizer_refresh(
            stop_event,
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

    def test_stop_during_opening_exits_without_transfer_or_close(self):
        stop_event = threading.Event()
        actions = []

        def open_inventory():
            actions.append("open")
            stop_event.set()

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=lambda: False,
            crop_plot_prompt_is_visible=lambda: True,
            inventory_is_open=lambda: False,
            open_inventory=open_inventory,
            close_inventory=lambda: actions.append("close"),
            transfer_all_from=lambda: actions.append("from_plot"),
            transfer_all_inventory=lambda: actions.append("to_plot"),
        )

        self.assertEqual(actions, ["open"])

    def test_default_inventory_wrappers_use_local_stop_aware_open(self):
        stop_event = threading.Event()
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
                side_effect=lambda _stop_event: stop_event.set(),
            ) as open_inventory,
        ):
            run_fertilizer_refresh(
                stop_event,
                poll_interval=0,
                crop_plot_is_open=lambda: False,
                crop_plot_prompt_is_visible=lambda: True,
                transfer_all_inventory=Mock(),
            )

        open_inventory.assert_called_once_with(stop_event)


class FertilizerLocalInventoryTests(unittest.TestCase):
    def test_local_await_true_stops_without_another_poll(self):
        stop_event = threading.Event()
        check = Mock(side_effect=lambda: stop_event.set() or False)

        self.assertFalse(_template_await_true(stop_event, check, 2))
        check.assert_called_once_with()

    def test_local_await_false_stops_without_another_poll(self):
        stop_event = threading.Event()
        check = Mock(side_effect=lambda: stop_event.set() or True)

        self.assertTrue(_template_await_false(stop_event, check, 2))
        check.assert_called_once_with()

    def test_local_open_stops_during_polling_without_recovery(self):
        stop_event = threading.Event()
        template = types.SimpleNamespace(check_template=Mock(return_value=False))
        utils = types.SimpleNamespace(
            press_key=Mock(side_effect=lambda *_args: stop_event.set())
        )
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
            _open_crop_plot_inventory(stop_event)

        utils.press_key.assert_called_once_with("AccessInventory")

    def test_local_close_stops_during_polling_without_recovery(self):
        stop_event = threading.Event()
        template = types.SimpleNamespace(check_template=Mock(return_value=True))
        variables = types.SimpleNamespace(get_pixel_loc=Mock(return_value=0))
        windows = types.SimpleNamespace(
            click=Mock(side_effect=lambda *_args: stop_event.set())
        )
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
            _close_crop_plot_inventory(stop_event)

        windows.click.assert_called_once_with(0, 0)


if __name__ == "__main__":
    unittest.main()
