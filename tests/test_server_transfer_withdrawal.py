import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from source.gacha_bot import server_transfer


class ResourceWithdrawalTests(unittest.TestCase):
    def setUp(self):
        """Isolate withdrawal state and replace all game interactions."""
        self.items = [{"yaw": index} for index in range(3)]
        self.dedis = {"resource": {"teleport": "RESOURCE", "items": self.items}}
        self.dedi = SimpleNamespace(
            was_clear_dedi=False,
            was_last_dedi_empty=False,
            open_withdraw_all=Mock(return_value=True),
            open_deposit_all=Mock(return_value=True),
        )
        self.inventory = SimpleNamespace(g_last_check_can_transfer=False)
        self.teleporter = Mock()
        self.transmitter = Mock()
        patches = patch.multiple(
            server_transfer,
            dedi=self.dedi,
            player_inventory=self.inventory,
            teleporter=self.teleporter,
            transmitter=self.transmitter,
            utils=Mock(),
            logs=Mock(),
            list_of_withdrawed_dedi=set(),
            is_withdrawed_all=False,
            account_detect_withdrawed_all=None,
            transmitter_teleport="TRANSMITTER",
        )
        patches.start()
        self.addCleanup(patches.stop)

    def test_nonempty_dedi_stops_and_is_revisited_next_cycle(self):
        """A successful withdrawal alone does not exhaust a dedi."""
        for account in (1, 2):
            self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, account))
        self.assertEqual(
            self.dedi.open_withdraw_all.call_args_list,
            [call("RESOURCE", self.items[0], should_clear_on_empty=True)] * 2,
        )
        self.assertEqual(server_transfer.list_of_withdrawed_dedi, set())
        self.assertFalse(server_transfer.is_withdrawed_all)

    def test_cleared_or_unassigned_dedi_advances_and_is_skipped_next_cycle(self):
        """Both empty signals allow advancing and persist across cycles."""
        for flag in ("was_clear_dedi", "was_last_dedi_empty"):
            with self.subTest(flag=flag):
                server_transfer.list_of_withdrawed_dedi.clear()
                self.dedi.open_withdraw_all.reset_mock()

                def withdraw(route: str, item: dict, **kwargs: bool):
                    """Report the first dedi as exhausted."""
                    setattr(self.dedi, flag, item is self.items[0])
                    return True

                self.dedi.open_withdraw_all.side_effect = withdraw
                for account in (1, 2):
                    self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, account))
                self.assertEqual(
                    [args.args[1] for args in self.dedi.open_withdraw_all.call_args_list],
                    [self.items[0], self.items[1], self.items[1]],
                )
                self.assertEqual(server_transfer.list_of_withdrawed_dedi, {1})

    def test_consecutive_empty_dedis_advance_until_nonempty(self):
        """A chain of empty dedis does not impose a two-dedi limit."""
        def withdraw(route: str, item: dict, **kwargs: bool):
            """Leave only the last dedi nonempty."""
            self.dedi.was_clear_dedi = item is not self.items[-1]
            return True

        self.dedi.open_withdraw_all.side_effect = withdraw
        self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, 2))
        self.assertEqual(self.dedi.open_withdraw_all.call_count, 3)
        self.assertEqual(server_transfer.list_of_withdrawed_dedi, {1, 2})
        self.assertFalse(server_transfer.is_withdrawed_all)

    def test_final_empty_dedi_records_exhaustion_and_stops_future_calls(self):
        """Exhaustion belongs to the account that empties the final dedi."""
        def withdraw(route: str, item: dict, **kwargs: bool):
            """Report every dedi as cleared."""
            self.dedi.was_clear_dedi = True
            return True

        self.dedi.open_withdraw_all.side_effect = withdraw
        self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, 2))
        self.assertEqual(server_transfer.list_of_withdrawed_dedi, {1, 2, 3})
        self.assertTrue(server_transfer.is_withdrawed_all)
        self.assertEqual(server_transfer.account_detect_withdrawed_all, 2)
        self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, 3))
        self.assertEqual(self.dedi.open_withdraw_all.call_count, 3)

    def test_failure_after_clearing_stops_remaining_dedis(self):
        """A failure does not mark the failing dedi exhausted."""
        def withdraw(route: str, item: dict, **kwargs: bool):
            """Clear the first dedi and fail the second."""
            self.dedi.was_clear_dedi = True
            return item is self.items[0]

        self.dedi.open_withdraw_all.side_effect = withdraw
        self.assertFalse(server_transfer.withdraw_from_transfer_dedis(self.dedis, 1))
        self.assertEqual(self.dedi.open_withdraw_all.call_count, 2)
        self.assertEqual(server_transfer.list_of_withdrawed_dedi, {1})

    def test_timer_recovery_rewithdraws_only_one_nonempty_dedi(self):
        """Missing timers trigger recovery with the same stopping rule."""
        def withdraw(route: str, item: dict, **kwargs: bool):
            """Report carried resources requiring a timer check."""
            self.inventory.g_last_check_can_transfer = True
            return True

        self.dedi.open_withdraw_all.side_effect = withdraw
        self.transmitter.open_and_has_timer.return_value = False
        self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, 1))
        self.assertEqual(
            self.dedi.open_withdraw_all.call_args_list,
            [call("RESOURCE", self.items[0], should_clear_on_empty=True)] * 2,
        )
        self.transmitter.open_and_has_timer.assert_called_once_with()
        self.assertEqual(self.teleporter.teleport_not_default.call_args_list,
                         [call("RESOURCE"), call("TRANSMITTER"), call("RESOURCE")])

    def test_timer_recovery_reopens_final_exhausted_dedi(self):
        """Recovery must withdraw again after redepositing into the last dedi."""
        def withdraw(route: str, item: dict, **kwargs: bool):
            """Empty each visited dedi while carrying resources."""
            self.dedi.was_clear_dedi = True
            self.inventory.g_last_check_can_transfer = True
            return True

        self.dedi.open_withdraw_all.side_effect = withdraw
        self.transmitter.open_and_has_timer.return_value = False
        self.assertTrue(server_transfer.withdraw_from_transfer_dedis(self.dedis, 2))
        self.dedi.open_deposit_all.assert_called_once_with("RESOURCE", self.items[-1])
        self.assertEqual(
            [args.args[1] for args in self.dedi.open_withdraw_all.call_args_list],
            self.items + [self.items[-1]],
        )
        self.assertTrue(server_transfer.is_withdrawed_all)
        self.assertEqual(server_transfer.account_detect_withdrawed_all, 2)


if __name__ == "__main__":
    unittest.main()
