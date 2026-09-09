import asyncio
import contextlib
import sys
import time

import pyautogui

import settings
from source.launcher.config.constants import GAME_WINDOW_TITLE
from source.launcher.utils.system import focus_window_if_needed
from source.logs import gachalogs as logs
from source.utility import windows
from source.utility.debug_screenshots import stop_debug_screenshot_worker

pyautogui.FAILSAFE = False


focus_window_task = None


def focus_window(window_title=GAME_WINDOW_TITLE, interval=5.0, is_repeat_once=False):
    global focus_window_task

    if focus_window_task and not focus_window_task.done():
        return

    interval = max(0.1, float(interval))

    async def callback():
        while True:
            try:
                if focus_window_if_needed(window_title):
                    await asyncio.sleep(0.1)
            except Exception as exc:
                print(f"[ERROR] Error focusing window: {exc}")
            await asyncio.sleep(interval)
            if is_repeat_once:
                break

    focus_window_task = asyncio.create_task(callback())


async def cancel_focus_window():
    global focus_window_task

    task = focus_window_task
    focus_window_task = None
    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def prepare_bot():
    """Prepare scheduler and game focus before the bot starts executing tasks."""
    print("[INFO] Offline runner starting.")

    import task_manager

    await asyncio.to_thread(task_manager.prepare)

    # Reset mouse position to edge of the screen to prevent unintended movements when starting the program.
    windows.move_mouse(2, 2)

    if settings.allow_focus_ark_window:
        focus_window(GAME_WINDOW_TITLE, settings.focus_ark_window_interval)
        print(
            f"[INFO] {GAME_WINDOW_TITLE} auto-focus enabled every {max(0.1, settings.focus_ark_window_interval)} seconds."
        )
    else:
        print(f"[INFO] {GAME_WINDOW_TITLE} auto-focus disabled.")
        focus_window(GAME_WINDOW_TITLE, is_repeat_once=True)

    return task_manager


async def run_bot(task_manager):
    """Run the prepared task scheduler."""
    await asyncio.to_thread(task_manager.run)


async def shutdown_bot():
    """Stop background helpers owned by the bot process."""
    await cancel_focus_window()
    stop_debug_screenshot_worker()


async def main():
    try:
        task_manager = await prepare_bot()
        await run_bot(task_manager)
    finally:
        await shutdown_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[WARN] Offline runner stopped.")
    except Exception as exc:
        print(f"[ERROR] {exc}")
        logs.logger.critical("Something happened and GBot stopped", exc_info=True)
        time.sleep(1)
        sys.exit(1)
