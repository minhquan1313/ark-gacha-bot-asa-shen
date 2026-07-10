import contextlib
import subprocess
import time


def terminate_process_tree(process, terminate_timeout=5.0, kill_timeout=2.0):
    if process is None or process.poll() is not None:
        return
    try:
        _terminate_with_psutil(process, terminate_timeout, kill_timeout)
    except Exception:
        _terminate_direct(process, terminate_timeout, kill_timeout)


def _terminate_with_psutil(process, terminate_timeout, kill_timeout):
    import psutil

    parent = psutil.Process(process.pid)
    children = parent.children(recursive=True)
    targets = children + [parent]
    for target in targets:
        with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
            target.terminate()
    gone, alive = psutil.wait_procs(targets, timeout=terminate_timeout)
    if alive:
        for target in alive:
            with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
                target.kill()
        psutil.wait_procs(alive, timeout=kill_timeout)
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        process.wait(timeout=0)


def _terminate_direct(process, terminate_timeout, kill_timeout):
    try:
        process.terminate()
        process.wait(timeout=terminate_timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    except OSError:
        return
    try:
        process.kill()
        process.wait(timeout=kill_timeout)
    except (OSError, subprocess.TimeoutExpired):
        pass


def stop_process_now(process):
    terminate_process_tree(process, terminate_timeout=0.1, kill_timeout=0.1)


def poll_kill_after_deadline(process, deadline):
    if process is None or process.poll() is not None:
        return False
    if deadline is None or time.time() < deadline:
        return False
    try:
        process.kill()
    except OSError:
        return False
    return True
