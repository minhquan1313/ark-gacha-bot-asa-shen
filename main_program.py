import asyncio
import sys
import time

import pyautogui
import win32con
import win32gui

import settings

pyautogui.FAILSAFE = False


focus_window_task = None


def focus_window(window_title="ArkAscended", interval=5.0):
    global focus_window_task

    if focus_window_task and not focus_window_task.done():
        return

    interval = max(0.1, float(interval))

    async def callback():
        while True:
            try:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd and win32gui.GetForegroundWindow() != hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    await asyncio.sleep(0.1)
            except Exception as exc:
                print(f"[ERROR] Error focusing window: {exc}")
            await asyncio.sleep(interval)

    focus_window_task = asyncio.create_task(callback())


async def main():
    print("[INFO] Offline runner starting.")
    if settings.allow_focus_ark_window:
        focus_window("ArkAscended", settings.focus_ark_window_interval)
        print(
            f"[INFO] ArkAscended auto-focus enabled every {max(0.1, settings.focus_ark_window_interval)} seconds."
        )
    else:
        print("[INFO] ArkAscended auto-focus disabled.")
    await asyncio.sleep(3)

    import task_manager

    await asyncio.to_thread(task_manager.main)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[WARN] Offline runner stopped.")
    except Exception as exc:
        print(f"[ERROR] {exc}")
        time.sleep(1)
        sys.exit(1)
