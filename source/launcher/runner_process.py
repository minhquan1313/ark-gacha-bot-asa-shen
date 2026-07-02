import asyncio
import queue
import sys
import threading

import main_program
from source.logs import gachalogs as logs

RUNNER_READY_MESSAGE = "__RUNNER_READY__"
RUNNER_OVERLAY_READY_MESSAGE = "__RUNNER_OVERLAY_READY__"
RUNNER_OVERLAY_ACK_TIMEOUT_SECONDS = 10.0


def wait_for_launcher_ack(timeout_seconds: float) -> bool:
    """Wait for the launcher overlay before allowing bot tasks to run."""
    if sys.stdin is None or sys.stdin.isatty():
        return True

    responses: queue.Queue[str] = queue.Queue(maxsize=1)

    def read_ack() -> None:
        try:
            responses.put(sys.stdin.readline().strip())
        except (OSError, ValueError):
            responses.put("")

    thread = threading.Thread(target=read_ack, daemon=True)
    thread.start()
    try:
        return responses.get(timeout=timeout_seconds) == RUNNER_OVERLAY_READY_MESSAGE
    except queue.Empty:
        return False


async def main():
    try:
        task_manager = await main_program.prepare_bot()
        print(RUNNER_READY_MESSAGE, flush=True)
        if not wait_for_launcher_ack(RUNNER_OVERLAY_ACK_TIMEOUT_SECONDS):
            message = (
                "Runner overlay was not ready; offline runner will not start tasks."
            )
            print(f"[ERROR] {message}", flush=True)
            logs.logger.error(message)
            return
        await main_program.run_bot(task_manager)
    finally:
        await main_program.shutdown_bot()


if __name__ == "__main__":
    asyncio.run(main())
