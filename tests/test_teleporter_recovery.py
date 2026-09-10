import unittest
from contextvars import copy_context
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.ASA.strucutres import teleporter
from source.gacha_bot import server_transfer
from source.launcher.components import helper_runner


class TeleporterRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.state = Mock()
        self.state.human.on_tp = True
        self.bed = Mock()
        self.console = Mock()
        self.template = Mock()
        self.template.check_template_no_bounds.return_value = False
        self.template.check_teleporter_orange.return_value = True
        self.template.template_await_true.return_value = True
        self.clock = Mock(return_value=False)
        self.clocks = Mock()
        self.clocks.get_default_clock.return_value = self.clock
        patches = patch.multiple(
            teleporter,
            player_state=self.state,
            bed=self.bed,
            console=self.console,
            template=self.template,
            utils_simple=self.clocks,
            utils=Mock(),
            windows=Mock(),
            variables=Mock(),
            time=Mock(),
            settings=SimpleNamespace(bed_spawn="Home", singleplayer=False),
            is_open=Mock(return_value=True),
            close=Mock(),
        )
        patches.start()
        self.addCleanup(patches.stop)

    def assert_no_destructive_recovery(self):
        self.bed.fast_travel.assert_not_called()
        self.bed.spawn_in.assert_not_called()
        self.state.check_state.assert_not_called()
        self.state.reset_state.assert_not_called()
        self.state.check_disconnected.assert_not_called()

    @teleporter.prevent_suicide_recovery()
    def test_protected_success_reopens_without_destructive_recovery(self):
        with patch.object(teleporter, "open", wraps=teleporter.open) as reopen:
            teleporter.teleport_not_default("Dedis")
        reopen.assert_called_once_with()
        self.console.console_exit_mainmenu.assert_not_called()
        self.assert_no_destructive_recovery()

    @teleporter.prevent_suicide_recovery()
    def test_protected_fast_travel_stops_even_when_menu_exit_raises(self):
        self.state.human.on_tp = False
        self.console.console_exit_mainmenu.side_effect = OSError("Console unavailable")
        with self.assertRaisesRegex(RuntimeError, "Manual recovery required") as raised:
            teleporter.teleport_not_default("Dedis")
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.console.console_exit_mainmenu.assert_called_once_with()
        self.assert_no_destructive_recovery()

    @teleporter.prevent_suicide_recovery()
    def test_open_failure_stops_before_player_state_recovery(self):
        teleporter.is_open.return_value = False
        self.clocks.get_default_clock.side_effect = [
            Mock(side_effect=[False, True]), Mock(return_value=True)
        ]
        with self.assertRaisesRegex(RuntimeError, "teleporter did not open"):
            teleporter.open()
        self.console.console_exit_mainmenu.assert_called_once_with()
        self.assert_no_destructive_recovery()

    @teleporter.prevent_suicide_recovery()
    def test_open_outer_timeout_cannot_silently_return(self):
        teleporter.is_open.return_value = False
        self.clock.return_value = True
        with self.assertRaisesRegex(RuntimeError, "opening timed out"):
            teleporter.open()
        self.assert_no_destructive_recovery()

    @teleporter.prevent_suicide_recovery()
    def test_list_timeout_does_not_reconnect_or_respawn(self):
        self.template.template_await_true.return_value = False
        self.clocks.get_default_clock.side_effect = [
            Mock(side_effect=[False, True]), Mock(side_effect=[False, True])
        ]
        with self.assertRaisesRegex(RuntimeError, "destination list did not load"):
            teleporter.teleport_not_default("Dedis")
        self.console.console_exit_mainmenu.assert_called_once_with()
        self.assert_no_destructive_recovery()

    @teleporter.prevent_suicide_recovery()
    def test_post_teleport_verification_failure_is_protected(self):
        teleporter.is_open.side_effect = [True, True, False, False]
        self.clocks.get_default_clock.side_effect = [
            Mock(return_value=False), Mock(return_value=False),
            Mock(return_value=False), Mock(return_value=True),
        ]
        with self.assertRaisesRegex(RuntimeError, "opening timed out"):
            teleporter.teleport_not_default("Dedis")
        self.console.console_exit_mainmenu.assert_called_once_with()
        self.assert_no_destructive_recovery()

    def test_default_preserves_bed_fast_travel(self):
        self.state.human.on_tp = False
        teleporter.teleport_not_default("Dedis")
        self.bed.fast_travel.assert_called_once_with("Home")
        self.console.console_exit_mainmenu.assert_not_called()

    def test_default_open_preserves_respawn_recovery(self):
        teleporter.is_open.return_value = False
        self.clocks.get_default_clock.side_effect = [
            Mock(side_effect=[False, True, True]), Mock(return_value=True)
        ]
        teleporter.open()
        self.state.check_state.assert_called_once_with()
        self.bed.spawn_in.assert_called_once_with("Home")
        self.console.console_exit_mainmenu.assert_not_called()

    def test_scoped_policy_restores_nested_contexts(self):
        self.state.human.on_tp = False
        unprotected_context = copy_context()
        with teleporter.prevent_suicide_recovery():
            with teleporter.prevent_suicide_recovery():
                with self.assertRaises(RuntimeError):
                    teleporter.teleport_not_default("Dedis")
            with self.assertRaises(RuntimeError):
                teleporter.teleport_not_default("Dedis")
            unprotected_context.run(teleporter.teleport_not_default, "Dedis")
        teleporter.teleport_not_default("Dedis")
        self.assertEqual(self.bed.fast_travel.call_count, 2)

    def test_transfer_run_protects_nested_calls_and_restores_policy_on_error(self):
        self.state.human.on_tp = False
        with patch.object(
            server_transfer, "_run_transfer_helper",
            side_effect=lambda *_args, **_kwargs: teleporter.teleport_not_default("Dedis"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Manual recovery required"):
                server_transfer.run_transfer_helper({})
        self.bed.fast_travel.assert_not_called()
        teleporter.teleport_not_default("Dedis")
        self.bed.fast_travel.assert_called_once_with("Home")

    def test_transfer_run_restores_policy_after_normal_return(self):
        with patch.object(server_transfer, "_run_transfer_helper", return_value=True) as run:
            self.assertTrue(server_transfer.run_transfer_helper({}))
            run.assert_called_with({}, None, multiple_resource=False)
            self.assertTrue(server_transfer.run_transfer_helper({}, multiple_resource=True))
            run.assert_called_with({}, None, multiple_resource=True)
        self.state.human.on_tp = False
        teleporter.teleport_not_default("Dedis")
        self.bed.fast_travel.assert_called_once_with("Home")

    @teleporter.prevent_suicide_recovery()
    def test_worker_reports_manual_recovery_error(self):
        self.state.human.on_tp = False
        args = SimpleNamespace(
            func=lambda _args: teleporter.teleport_not_default("Dedis")
        )
        parser = Mock()
        parser.parse_args.return_value = args
        with (
            patch.object(helper_runner, "build_parser", return_value=parser),
            patch.object(helper_runner, "send_completion") as completion,
            patch.object(helper_runner.traceback, "print_exc"),
        ):
            self.assertEqual(helper_runner.main([]), 1)
        self.assertIn("Manual recovery required", completion.call_args.args[0])

    def test_transfer_to_transmitter_calls_teleport_without_policy_argument(self):
        with (
            patch.object(teleporter, "teleport_not_default") as teleport,
            patch.object(server_transfer, "utils", Mock()),
            patch.object(server_transfer, "transmitter", Mock()),
        ):
            self.assertTrue(server_transfer.transfer_to_server(
                "Destination", {"resource": {"transmitter_teleport": "Transmitter"}}
            ))
        teleport.assert_called_once_with("Transmitter")

    def test_destination_deposit_calls_teleport_without_policy_argument(self):
        with (
            patch.object(teleporter, "teleport_not_default") as teleport,
            patch.object(server_transfer, "utils", Mock()),
        ):
            self.assertTrue(server_transfer.deposit_to_transfer_dedis(
                {"destination": {"teleport": "Dedis", "items": []}}, 1
            ))
        teleport.assert_called_once_with("Dedis")


if __name__ == "__main__":
    unittest.main()
