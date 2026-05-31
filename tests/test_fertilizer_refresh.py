import threading
import unittest

from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh


class FertilizerRefreshTests(unittest.TestCase):
    def test_refreshes_once_then_waits_for_inventory_close(self):
        stop_event = threading.Event()
        transfers = []
        inventory_checks = []
        crop_plot_checks = 0

        def crop_plot_is_open():
            nonlocal crop_plot_checks
            crop_plot_checks += 1
            if crop_plot_checks > 1:
                stop_event.set()
            return True

        def inventory_is_open():
            inventory_checks.append(True)
            return len(inventory_checks) < 3

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=crop_plot_is_open,
            inventory_is_open=inventory_is_open,
            transfer_all_from=lambda: transfers.append("from_plot"),
            transfer_all_inventory=lambda: transfers.append("to_plot"),
        )

        self.assertEqual(transfers, ["from_plot", "to_plot"])
        self.assertEqual(len(inventory_checks), 3)

    def test_does_not_transfer_until_crop_plot_is_detected(self):
        stop_event = threading.Event()
        transfers = []
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
            inventory_is_open=lambda: False,
            transfer_all_from=lambda: transfers.append("from_plot"),
            transfer_all_inventory=lambda: transfers.append("to_plot"),
        )

        self.assertEqual(transfers, [])
        self.assertEqual(checks, 3)

    def test_stop_between_transfers_prevents_transfer_back(self):
        stop_event = threading.Event()
        transfers = []

        def transfer_all_from():
            transfers.append("from_plot")
            stop_event.set()

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=lambda: True,
            inventory_is_open=lambda: False,
            transfer_all_from=transfer_all_from,
            transfer_all_inventory=lambda: transfers.append("to_plot"),
        )

        self.assertEqual(transfers, ["from_plot"])

    def test_can_stop_while_idle(self):
        stop_event = threading.Event()
        checks = 0

        def crop_plot_is_open():
            nonlocal checks
            checks += 1
            stop_event.set()
            return False

        run_fertilizer_refresh(
            stop_event,
            poll_interval=0,
            crop_plot_is_open=crop_plot_is_open,
            inventory_is_open=lambda: False,
            transfer_all_from=lambda: self.fail("unexpected transfer"),
            transfer_all_inventory=lambda: self.fail("unexpected transfer"),
        )

        self.assertEqual(checks, 1)


if __name__ == "__main__":
    unittest.main()
