import sys
from pathlib import Path

# Debug hold after initialization; use 0 for immediate reveal.
SPLASH_DEBUG_DELAY_MS = 300


def main():
    """Paint a boot core before importing the launcher, then reveal its dashboard."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    from source.ui.components.boot_splash import BootSplash

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    loading = BootSplash(reveal_delay_ms=SPLASH_DEBUG_DELAY_MS)
    window = None

    def cancelled():
        """Release any partially initialized launcher when startup is cancelled."""
        if window is not None:
            window._shutdown_resources()
            window.hide()
        app.exit(0)

    def failed(message: str):
        """Report startup errors visibly and stop all pending splash callbacks."""
        loading.stop_animation()
        loading.hide()
        print(f"Launcher startup failed: {message}", file=sys.stderr, flush=True)
        if window is not None:
            window._shutdown_resources()
            window.hide()
        QMessageBox.critical(None, "Launcher startup failed", message)
        app.exit(1)

    def presented():
        """Start background work only after the launcher is fully visible."""
        app.setQuitOnLastWindowClosed(True)
        if window is not None:
            window.complete_startup_presentation()

    def initialize():
        """Import and initialize the interface after the boot core first paints."""
        nonlocal window
        if loading._cancelled or window is not None:
            return
        try:
            from source.launcher.gui import SettingsGUI

            launcher = SettingsGUI(deferred_startup=True)
            window = launcher
            window.startup_progress.connect(loading.set_status)
            window.startup_ready.connect(lambda: loading.reveal(launcher))
            window.startup_failed.connect(failed)
        except Exception as exc:
            failed(str(exc))

    loading.cancelled.connect(cancelled)
    loading.finished.connect(presented)
    loading.failed.connect(failed)
    app.aboutToQuit.connect(loading.stop_animation)
    loading.first_presented.connect(initialize)
    loading.show()
    loading.raise_()
    loading.activateWindow()
    loading.repaint()
    try:
        return app.exec()
    finally:
        if window is not None:
            window._shutdown_resources()


if __name__ == "__main__":
    root = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    # Windowed Python and packaged executables have no console streams.
    if sys.stdout is None or sys.stderr is None:
        log_directory = root / "source" / "logs"
        log_directory.mkdir(parents=True, exist_ok=True)
        startup_log = (log_directory / "launcher_startup.log").open(
            "a", encoding="utf-8", buffering=1
        )
        if sys.stdout is None:
            sys.stdout = startup_log
        if sys.stderr is None:
            sys.stderr = startup_log
    app_id = "ShenGBot"
    if "--app-id" in sys.argv:
        app_id = sys.argv[sys.argv.index("--app-id") + 1]
    try:
        sys.exit(main())
    finally:
        from source.app_lifecycle import finish_application

        finish_application(root, app_id)
