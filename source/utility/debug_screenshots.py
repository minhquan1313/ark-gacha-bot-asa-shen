import multiprocessing
import os
import re
import shutil
import time
from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path
from queue import Empty

SHUTDOWN_TIMEOUT_SECONDS = 2.0
DEBUG_SCREENSHOT_ROOT = Path("debug_screenshots")

IS_DEBUG_ON = False
IS_CLEANUP_ONSTART = False

CAPTURE_DEDI_DEPOSIT_CRYSTAL = True
CAPTURE_DEDI_DEPOSIT_GRIND = True
CAPTURE_IGUANADON_SEED = True
CAPTURE_GACHA_SEED = True
CAPTURE_GACHA_OVERCAP = True
CAPTURE_PEGO_CRYSTAL = True
CAPTURE_ROUTE_READY = True
CAPTURE_GRINDER_WITHDRAW = True
CAPTURE_VAULT_TRANSFER = True
CAPTURE_PLAYER_STATE = True

_state = None
_cleanup_done = False
_run_timestamp = time.strftime("%Y%m%d_%H%M%S")


@dataclass
class _WorkerState:
    request_queue: object
    process: object


def capture_for(category, active=False, delay=0.5):
    if not active or not IS_DEBUG_ON:
        return _noop_capture

    delay_seconds = max(0.0, float(delay))

    def capture(label="capture"):
        _request_capture(category, label, delay_seconds)

    return capture


def stop_debug_screenshot_worker():
    global _state
    state = _state
    _state = None
    if state is None:
        return

    try:
        state.request_queue.put(None)
    except Exception:
        pass

    process = state.process
    try:
        process.join(SHUTDOWN_TIMEOUT_SECONDS)
    except Exception:
        return

    if process.is_alive():
        process.terminate()
        process.join(SHUTDOWN_TIMEOUT_SECONDS)


def cleanup_debug_screenshots_on_program_start():
    global _cleanup_done
    if _cleanup_done or not IS_DEBUG_ON or not IS_CLEANUP_ONSTART:
        return

    _cleanup_done = True
    try:
        DEBUG_SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        for child in DEBUG_SCREENSHOT_ROOT.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    except Exception as exc:
        _warn(f"Unable to cleanup debug screenshots: {exc}")


def _noop_capture(label="capture"):
    return None


def _request_capture(category, label, delay):
    try:
        state = _ensure_worker()
    except Exception as exc:
        _warn(f"Unable to start debug screenshot worker: {exc}")
        return

    try:
        state.request_queue.put(
            {
                "category": category,
                "label": str(label),
                "delay": delay,
            }
        )
    except Exception as exc:
        _warn(f"Unable to queue debug screenshot: {exc}")


def _ensure_worker():
    global _state
    if _state is not None and _state.process.is_alive():
        return _state
    _state = _start_worker()
    return _state


def _start_worker():
    context = multiprocessing.get_context("spawn")
    request_queue = context.Queue()
    process = context.Process(
        target=_worker_main,
        args=(
            request_queue,
            os.getpid(),
            str(DEBUG_SCREENSHOT_ROOT),
            _run_timestamp,
        ),
        name="debug_screenshot_worker",
    )
    process.start()
    return _WorkerState(request_queue, process)


def _worker_main(request_queue, parent_pid, root, run_timestamp):
    capturer = None
    pending = []
    sequence = 0
    while _parent_alive(parent_pid):
        capturer = _capture_due_requests(pending, capturer, root, run_timestamp)

        timeout = _next_queue_timeout(pending)
        try:
            request = request_queue.get(timeout=timeout)
        except Empty:
            continue
        if request is None:
            return

        delay = max(0.0, float(request.get("delay", 0.0)))
        heappush(
            pending,
            (
                time.monotonic() + delay,
                sequence,
                request["category"],
                request.get("label", "capture"),
            ),
        )
        sequence += 1


def _capture_due_requests(pending, capturer, root, run_timestamp):
    if not pending:
        return capturer
    now = time.monotonic()
    while pending and pending[0][0] <= now:
        _, _, category, label = heappop(pending)
        try:
            if capturer is None:
                capturer = _ScreenCapturer(Path(root), run_timestamp)
            capturer.capture(category, label)
        except Exception as exc:
            _warn(f"Unable to save debug screenshot: {exc}")
    return capturer


def _next_queue_timeout(pending):
    if not pending:
        return 0.5
    return max(0.0, min(0.5, pending[0][0] - time.monotonic()))


class _ScreenCapturer:
    def __init__(self, root, run_timestamp):
        self.root = root / run_timestamp

    def capture(self, category, label):
        import mss
        from PIL import Image

        category_name = _sanitize(category)
        label_name = _sanitize(label)
        folder = self.root / category_name
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        timestamp = f"{timestamp}_{time.time_ns() % 1_000_000_000:09d}"
        filename = f"{timestamp}__{label_name}.png"
        path = folder / filename

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            image.save(path)
        return path


def _sanitize(value):
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text)
    text = text.strip("._-")
    return text[:120] or "capture"


def _parent_alive(parent_pid):
    if os.name == "nt":
        return _windows_process_alive(parent_pid)
    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True


def _windows_process_alive(pid):
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False

    exit_code = ctypes.c_ulong()
    try:
        if not ctypes.windll.kernel32.GetExitCodeProcess(
            handle, ctypes.byref(exit_code)
        ):
            return False
        return exit_code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _warn(message):
    try:
        from source.logs import gachalogs as logs

        logs.logger.warning(message)
    except Exception:
        print(f"[WARN] {message}", flush=True)


def _reset_for_tests():
    global _state, _cleanup_done
    _state = None
    _cleanup_done = False
