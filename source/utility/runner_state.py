import json

RUNNER_STATE_PREFIX = "__RUNNER_STATE__ "


def emit_runner_state(state: str):
    """Publish a runner state message for the launcher process."""
    print(
        f"{RUNNER_STATE_PREFIX}{json.dumps({'state': state})}",
        flush=True,
    )
