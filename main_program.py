import asyncio
import sys
import time

import pyautogui

import settings
from source.launcher.constants import GAME_WINDOW_TITLE
from source.launcher.system import focus_window_if_needed
from source.utility import windows

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
    try:
        await task
    except asyncio.CancelledError:
        pass


async def main():
    try:
        print("[INFO] Offline runner starting.")

        # Reset mouse position to center of the screen to prevent unintended movements when starting the program.
        windows.move_mouse(1920 / 2, 1080 / 2)

        if settings.allow_focus_ark_window:
            focus_window(GAME_WINDOW_TITLE, settings.focus_ark_window_interval)
            print(
                f"[INFO] {GAME_WINDOW_TITLE} auto-focus enabled every {max(0.1, settings.focus_ark_window_interval)} seconds."
            )
        else:
            print(f"[INFO] {GAME_WINDOW_TITLE} auto-focus disabled.")
            focus_window(GAME_WINDOW_TITLE, is_repeat_once=True)

        import task_manager

        await asyncio.to_thread(task_manager.main)
    finally:
        await cancel_focus_window()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[WARN] Offline runner stopped.")
    except Exception as exc:
        print(f"[ERROR] {exc}")
        time.sleep(1)
        sys.exit(1)
