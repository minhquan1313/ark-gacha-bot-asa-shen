import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import cast

from source.logs import gachalogs as logs

COMPLETION_PREFIX = "__HELPER_COMPLETION__ "
TASK_STATE_PREFIX = "__HELPER_TASK_STATE__ "
READY_MESSAGE = "__HELPER_READY__"


def send_completion(message: str):
    print(f"{COMPLETION_PREFIX}{message}", flush=True)


def send_ready():
    """Tell the launcher that the selected helper finished importing."""
    print(READY_MESSAGE, flush=True)


def send_task_state(snapshot: dict):
    """Write a structured helper task snapshot to the parent process."""
    print(f"{TASK_STATE_PREFIX}{json.dumps(snapshot)}", flush=True)


def run_auto_join_server(args: argparse.Namespace):
    from source.join_sim.source.auto_join import run_auto_join_server

    send_ready()
    joined = run_auto_join_server(args.server, args.afk_join)
    completion = "Joined server." if joined else "Stopped."
    logs.logger.info(completion)
    send_completion(completion)
    return 0 if joined else 1


def run_fertilizer_refresh(_args: argparse.Namespace):
    from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh

    send_ready()
    run_fertilizer_refresh()
    logs.logger.info("Stopped.")
    send_completion("Stopped.")
    return 0


def run_auto_fishing(args: argparse.Namespace):
    """Run auto fishing with the selected loop behavior."""
    from source.gacha_bot.auto_fishing import run_auto_fishing

    send_ready()
    run_auto_fishing(args.infinite)
    logs.logger.info("Finished.")
    send_completion("Finished.")
    return 0


def run_server_transfer(args: argparse.Namespace):
    from source.gacha_bot.server_transfer import (
        TransferConfigError,
        run_transfer_helper,
    )
    from source.launcher.config.transfer_helper_config import (
        normalize_transfer_runtime_config,
    )

    with open(args.config, "r", encoding="utf-8") as file:
        raw_config = cast(object, json.load(file))
    config = normalize_transfer_runtime_config(raw_config)
    send_ready()
    try:
        completed = run_transfer_helper(config, task_callback=send_task_state)
    except TransferConfigError as exc:
        logs.logger.error(f"Config blocked: {exc}")
        send_completion(f"Config blocked: {exc}")
        return 2
    completion = "Finished." if completed else "Stopped."
    logs.logger.info(completion)
    send_completion(completion)
    return 0 if completed else 1


def run_switch_steam(args: argparse.Namespace):
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

    send_ready()
    switch_steam_account(
        1,
        current_account,
        players,
        ui_coords,
        force_restart=True,
        close_ark=not getattr(args, "instant", False),
        loginusers=loginusers,
        steam_restart_interval=settings["steam_restart_interval"],
    )
    completion = f"Steam restarted for {args.account}."
    logs.logger.info(completion)
    send_completion(completion)
    return 0


def build_parser():
    """Build the subprocess helper command parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    auto_join = subparsers.add_parser("auto_join_server")
    auto_join.add_argument("--server", required=True)
    auto_join.add_argument(
        "--afk-join",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    auto_join.set_defaults(func=run_auto_join_server)

    fertilizer = subparsers.add_parser("fertilizer_refresh")
    fertilizer.set_defaults(func=run_fertilizer_refresh)

    auto_fishing = subparsers.add_parser("auto_fishing")
    auto_fishing.add_argument("--infinite", action="store_true")
    auto_fishing.set_defaults(func=run_auto_fishing)

    transfer = subparsers.add_parser("server_transfer")
    transfer.add_argument("--config", required=True)
    transfer.set_defaults(func=run_server_transfer)

    switch_steam = subparsers.add_parser("switch_steam")
    switch_steam.add_argument("--account", required=True)
    switch_steam.add_argument("--loginusers", required=True)
    switch_steam.add_argument("--instant", action="store_true")
    switch_steam.set_defaults(func=run_switch_steam)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        send_completion("Stopped.")
        return 1
    except Exception as exc:
        traceback.print_exc()
        logs.logger.error(f"Failed: {exc}")
        send_completion(f"Failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
