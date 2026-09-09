"""Final process cleanup and update restart for the Python entry point."""

import contextlib
import os
import subprocess
import sys
from pathlib import Path

import psutil


def cleanup_app_processes(app_id: str):
    """Stop remaining Python or packaged processes carrying this exact app ID."""
    names = {"python.exe", "pythonw.exe", Path(sys.executable).name.lower()}
    # Windows venv executables may keep a forwarding parent with the same tag.
    protected_pids = {
        os.getpid(),
        *(parent.pid for parent in psutil.Process().parents()),
    }
    targets = []
    for process in psutil.process_iter(["name", "cmdline"]):
        if process.pid in protected_pids:
            continue
        command = process.info["cmdline"] or []
        tagged = any(
            command[index : index + 2] == ["--app-id", app_id]
            for index in range(len(command) - 1)
        )
        if (process.info["name"] or "").lower() not in names or not tagged:
            continue
        with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
            process.terminate()
            targets.append(process)
    _, alive = psutil.wait_procs(targets, timeout=5)
    for process in alive:
        with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
            process.kill()
    psutil.wait_procs(alive, timeout=2)


def finish_application(root: Path, app_id: str):
    """Clean up workers before consuming an update request and relaunching."""
    cleanup_app_processes(app_id)
    request = root / ".update_restart.request"
    if not request.exists():
        return
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(root / "main.py"))
    command.extend(sys.argv[1:])
    request.unlink()
    try:
        subprocess.Popen(command, cwd=root)
    except OSError:
        request.write_text("restart\n", encoding="utf-8")
        raise
