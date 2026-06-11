import argparse
import json
import sys
import traceback


STATUS_PREFIX = "__HELPER_STATUS__ "
RESULT_PREFIX = "__HELPER_RESULT__ "


def emit_status(message):
    print(f"{STATUS_PREFIX}{message}", flush=True)


def emit_result(message):
    print(f"{RESULT_PREFIX}{message}", flush=True)


def run_auto_join_server(args):
    from source.join_sim.source.auto_join import run_auto_join_server

    joined = run_auto_join_server(args.server, emit_status)
    emit_result("Joined server." if joined else "Stopped.")
    return 0 if joined else 1


def run_fertilizer_refresh(_args):
    from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh

    run_fertilizer_refresh(emit_status)
    emit_result("Stopped.")
    return 0


def run_server_transfer(args):
    from source.gacha_bot.server_transfer import TransferConfigError, run_transfer_helper

    with open(args.config, "r", encoding="utf-8") as file:
        config = json.load(file)
    try:
        completed = run_transfer_helper(config, emit_status)
    except TransferConfigError as exc:
        emit_result(f"Config blocked: {exc}")
        return 2
    emit_result("Finished." if completed else "Stopped.")
    return 0 if completed else 1


def build_parser():
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
