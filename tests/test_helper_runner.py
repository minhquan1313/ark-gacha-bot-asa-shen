import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from source.launcher.components import helper_runner
from source.launcher.utils import steam_accounts as steam_accounts_module
from source.launcher.config import transfer_helper_config


class HelperRunnerReadyTests(unittest.TestCase):
    def test_auto_join_emits_ready_before_running(self) -> None:
        runtime = types.ModuleType("source.join_sim.source.auto_join")
        runtime.run_auto_join_server = Mock(return_value=True)
        output = io.StringIO()

        with (
            patch.dict(sys.modules, {runtime.__name__: runtime}),
            redirect_stdout(output),
        ):
            result = helper_runner.run_auto_join_server(
                types.SimpleNamespace(server="5147", afk_join=False)
            )

        self.assertEqual(result, 0)
        runtime.run_auto_join_server.assert_called_once_with("5147", False)
        self.assertEqual(
            output.getvalue().splitlines(),
            [helper_runner.READY_MESSAGE, "__HELPER_COMPLETION__ Joined server."],
        )

    def test_auto_join_does_not_emit_ready_when_import_fails(self) -> None:
        output = io.StringIO()
        with (
            patch.dict(sys.modules, {"source.join_sim.source.auto_join": None}),
            redirect_stdout(output),
            self.assertRaises(ModuleNotFoundError),
        ):
            helper_runner.run_auto_join_server(types.SimpleNamespace(server="5147"))

        self.assertEqual(output.getvalue(), "")

    def test_auto_join_parser_defaults_afk_join_to_true(self) -> None:
        args = helper_runner.build_parser().parse_args(
            ["auto_join_server", "--server", "5147"]
        )

        self.assertTrue(args.afk_join)

    def test_auto_join_parser_accepts_disabled_afk_join(self) -> None:
        args = helper_runner.build_parser().parse_args(
            ["auto_join_server", "--server", "5147", "--no-afk-join"]
        )

        self.assertFalse(args.afk_join)

    def test_transfer_emits_ready_after_config_load(self) -> None:
        runtime = types.ModuleType("source.gacha_bot.server_transfer")
        runtime.TransferConfigError = type("TransferConfigError", (RuntimeError,), {})
        runtime.run_transfer_helper = Mock(return_value=True)
        config = {"settings": {}}
        output = io.StringIO()

        with (
            patch.dict(sys.modules, {runtime.__name__: runtime}),
            patch("builtins.open", mock_open()),
            patch.object(helper_runner.json, "load", return_value=config),
            redirect_stdout(output),
        ):
            for enabled in (False, True):
                arguments = ["server_transfer", "--config", "runtime.json"]
                if enabled:
                    arguments.append("--multiple-resource")
                args = helper_runner.build_parser().parse_args(arguments)
                self.assertEqual(args.multiple_resource, enabled)
                result = helper_runner.run_server_transfer(args)
                self.assertEqual(result, 0)
                runtime.run_transfer_helper.assert_called_with(
                    transfer_helper_config.normalize_transfer_runtime_config(config),
                    task_callback=helper_runner.send_task_state,
                    multiple_resource=enabled,
                )

        self.assertEqual(
            output.getvalue().splitlines(),
            [helper_runner.READY_MESSAGE, "__HELPER_COMPLETION__ Finished."] * 2,
        )

    def test_transfer_does_not_emit_ready_when_config_load_fails(self) -> None:
        runtime = types.ModuleType("source.gacha_bot.server_transfer")
        runtime.TransferConfigError = type("TransferConfigError", (RuntimeError,), {})
        runtime.run_transfer_helper = Mock(return_value=True)
        output = io.StringIO()

        with (
            patch.dict(sys.modules, {runtime.__name__: runtime}),
            patch("builtins.open", mock_open()),
            patch.object(
                helper_runner.json, "load", side_effect=ValueError("bad json")
            ),
            redirect_stdout(output),
            self.assertRaises(ValueError),
        ):
            helper_runner.run_server_transfer(
                types.SimpleNamespace(config="runtime.json")
            )

        self.assertEqual(output.getvalue(), "")

    def test_switch_steam_emits_ready_after_validation_and_restarts(self) -> None:
        runtime = types.ModuleType("source.launcher.utils.steam_switch")
        runtime.switch_steam_account = Mock(return_value="beta")
        accounts = [
            {"account_name": "alpha", "most_recent": True},
            {"account_name": "beta", "most_recent": False},
        ]
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            loginusers = root / "config" / "loginusers.vdf"
            loginusers.parent.mkdir()
            loginusers.touch()
            with (
                patch.dict(
                    sys.modules,
                    {
                        runtime.__name__: runtime,
                        "source.gacha_bot.server_transfer": None,
                    },
                ),
                patch.object(
                    steam_accounts_module, "load_steam_accounts", return_value=accounts
                ),
                patch.object(
                    steam_accounts_module,
                    "most_recent_account_name",
                    return_value="alpha",
                ),
                patch.object(
                    transfer_helper_config,
                    "load_transfer_settings",
                    return_value={"steam_restart_interval": 45},
                ),
                patch.object(
                    transfer_helper_config,
                    "load_transfer_ui_coords",
                    return_value={"steam": {"restart_delay": 8}},
                ),
                redirect_stdout(output),
            ):
                result = helper_runner.run_switch_steam(
                    types.SimpleNamespace(account="beta", loginusers=str(loginusers))
                )

        self.assertEqual(result, 0)
        runtime.switch_steam_account.assert_called_once()
        call = runtime.switch_steam_account.call_args
        self.assertEqual(
            call.args[:3],
            (
                1,
                "alpha",
                {"players": [{"bed_name": "", "steam_account": "beta"}]},
            ),
        )
        self.assertTrue(call.kwargs["force_restart"])
        self.assertTrue(call.kwargs["close_ark"])
        self.assertEqual(call.kwargs["loginusers"], loginusers.resolve())
        self.assertEqual(call.kwargs["steam_restart_interval"], 45)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                helper_runner.READY_MESSAGE,
                "__HELPER_COMPLETION__ Steam restarted for beta.",
            ],
        )

    def test_switch_steam_instant_passes_close_ark_false(self) -> None:
        runtime = types.ModuleType("source.launcher.utils.steam_switch")
        runtime.switch_steam_account = Mock(return_value="beta")
        accounts = [
            {"account_name": "alpha", "most_recent": True},
            {"account_name": "beta", "most_recent": False},
        ]
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            loginusers = root / "config" / "loginusers.vdf"
            loginusers.parent.mkdir()
            loginusers.touch()
            with (
                patch.dict(sys.modules, {runtime.__name__: runtime}),
                patch.object(
                    steam_accounts_module, "load_steam_accounts", return_value=accounts
                ),
                patch.object(
                    steam_accounts_module,
                    "most_recent_account_name",
                    return_value="alpha",
                ),
                patch.object(
                    transfer_helper_config,
                    "load_transfer_settings",
                    return_value={"steam_restart_interval": 45},
                ),
                patch.object(
                    transfer_helper_config,
                    "load_transfer_ui_coords",
                    return_value={"steam": {"restart_delay": 8}},
                ),
                redirect_stdout(output),
            ):
                result = helper_runner.run_switch_steam(
                    types.SimpleNamespace(
                        account="beta",
                        loginusers=str(loginusers),
                        instant=True,
                    )
                )

        self.assertEqual(result, 0)
        call = runtime.switch_steam_account.call_args
        self.assertFalse(call.kwargs["close_ark"])
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                helper_runner.READY_MESSAGE,
                "__HELPER_COMPLETION__ Steam restarted for beta.",
            ],
        )

    def test_switch_steam_does_not_emit_ready_for_missing_account(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            loginusers = Path(temp_dir) / "config" / "loginusers.vdf"
            loginusers.parent.mkdir()
            loginusers.touch()
            with (
                redirect_stdout(output),
                self.assertRaisesRegex(RuntimeError, "Steam account was not found"),
            ):
                helper_runner.run_switch_steam(
                    types.SimpleNamespace(account="beta", loginusers=str(loginusers))
                )

        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
