import argparse
import json
import sys
import traceback
from pathlib import Path

STATUS_PREFIX = "__HELPER_STATUS__ "
RESULT_PREFIX = "__HELPER_RESULT__ "
TASK_STATE_PREFIX = "__HELPER_TASK_STATE__ "
READY_MESSAGE = "__HELPER_READY__"


def emit_status(message):
    print(f"{STATUS_PREFIX}{message}", flush=True)


def emit_result(message):
    print(f"{RESULT_PREFIX}{message}", flush=True)


def emit_ready() -> None:
    """Tell the launcher that the selected helper finished importing."""
    print(READY_MESSAGE, flush=True)


def emit_task_state(snapshot: dict) -> None:
    """Write a structured helper task snapshot to the parent process."""
    print(f"{TASK_STATE_PREFIX}{json.dumps(snapshot)}", flush=True)


def run_auto_join_server(args: argparse.Namespace) -> int:
    from source.join_sim.source.auto_join import run_auto_join_server

    emit_ready()
    joined = run_auto_join_server(args.server, emit_status)
    emit_result("Joined server." if joined else "Stopped.")
    return 0 if joined else 1


def run_fertilizer_refresh(_args: argparse.Namespace) -> int:
    from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh

    emit_ready()
    run_fertilizer_refresh(emit_status)
    emit_result("Stopped.")
    return 0


def run_server_transfer(args: argparse.Namespace) -> int:
    from source.gacha_bot.server_transfer import (
        TransferConfigError,
        run_transfer_helper,
    )

    with open(args.config, "r", encoding="utf-8") as file:
        config = json.load(file)
    emit_ready()
    try:
        completed = run_transfer_helper(
            config, emit_status, task_callback=emit_task_state
        )
    except TransferConfigError as exc:
        emit_result(f"Config blocked: {exc}")
        return 2
    emit_result("Finished." if completed else "Stopped.")
    return 0 if completed else 1


def run_switch_steam(args: argparse.Namespace) -> int:
    """Restart Steam with the selected account through the transfer workflow."""
    from source.launcher.config.transfer_helper_config import (
        load_transfer_settings,
        load_transfer_ui_coords,
    )
    from source.launcher.utils import steam_accounts
    from source.launcher.utils.steam_switch import switch_steam_account

    loginusers = Path(args.loginusers).resolve()
    accounts = steam_accounts.load_steam_accounts(loginusers)
    account_names = {str(account["account_name"]) for account in accounts}
    if args.account not in account_names:
        raise RuntimeError(
            f"Steam account was not found in loginusers.vdf: {args.account}"
        )
    current_account = steam_accounts.most_recent_account_name(accounts)
    players = {
        "players": [{"bed_name": "", "steam_account": args.account}],
    }
    settings = load_transfer_settings()
    ui_coords = load_transfer_ui_coords()

    emit_ready()
    switch_steam_account(
        1,
        current_account,
        players,
        ui_coords,
        emit_status,
        force_restart=True,
        loginusers=loginusers,
        steam_restart_interval=settings["steam_restart_interval"],
    )
    emit_result(f"Steam restarted for {args.account}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the subprocess helper command parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    auto_join = subparsers.add_parser("auto_join_server")
    auto_join.add_argument("--server", required=True)
    auto_join.set_defaults(func=run_auto_join_server)

    fertilizer = subparsers.add_parser("fertilizer_refresh")
    fertilizer.set_defaults(func=run_fertilizer_refresh)

    transfer = subparsers.add_parser("server_transfer")
    transfer.add_argument("--config", required=True)
    transfer.set_defaults(func=run_server_transfer)

    switch_steam = subparsers.add_parser("switch_steam")
    switch_steam.add_argument("--account", required=True)
    switch_steam.add_argument("--loginusers", required=True)
    switch_steam.set_defaults(func=run_switch_steam)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        emit_result("Stopped.")
        return 1
    except Exception as exc:
        traceback.print_exc()
        emit_result(f"Failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
