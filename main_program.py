import asyncio
import sys
import time

import pyautogui
import win32con
import win32gui

pyautogui.FAILSAFE = False


focus_window_task = None


def focus_window(window_title="ArkAscended"):
    global focus_window_task

    if focus_window_task and not focus_window_task.done():
        return

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
            await asyncio.sleep(5)

    focus_window_task = asyncio.create_task(callback())


async def main():
    print("[INFO] Offline runner starting.")
    focus_window("ArkAscended")
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
