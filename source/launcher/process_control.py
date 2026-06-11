import subprocess
import time


def terminate_process_tree(process, terminate_timeout=5, kill_timeout=2):
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
        try:
            target.terminate()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    gone, alive = psutil.wait_procs(targets, timeout=terminate_timeout)
    if alive:
        for target in alive:
            try:
                target.kill()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        psutil.wait_procs(alive, timeout=kill_timeout)
    try:
        process.wait(timeout=0)
    except (subprocess.TimeoutExpired, OSError):
        pass


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
