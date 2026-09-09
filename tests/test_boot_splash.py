import os
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QRectF, QTimer
from PySide6.QtWidgets import QApplication, QWidget
from source.ui.components.boot_splash import BootSplash
from source.launcher.gui import SettingsGUI


class BootSplashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.splash = BootSplash()
        self.window = QWidget()
        self.window.resize(1000, 680)
        self.addCleanup(self.window.close)
        self.addCleanup(self.splash.cancel)
        self.splash.show()

    def test_first_feedback_precedes_slow_image_loading(self):
        import threading
        from source.ui.components.boot_splash import _SplashImages
        gate = threading.Event()
        self.addCleanup(gate.set)
        done = Mock()
        loop = QEventLoop()
        self.splash.first_presented.connect(done)
        self.splash.first_presented.connect(loop.quit)
        with patch.object(_SplashImages, "_load", lambda worker: gate.wait(2)):
            QTimer.singleShot(500, loop.quit)
            loop.exec()
        done.assert_called_once()
        self.assertTrue(self.splash._painted)
        self.assertTrue(self.splash.isVisible())
        self.assertTrue(self.splash._logo.isNull())
        self.assertTrue(self.splash._artwork.isNull())
        self.splash._notify_presented()
        done.assert_called_once()

    def test_close_before_first_presentation_cancels_initialization(self):
        initialized = Mock()
        self.splash.first_presented.connect(initialized)
        self.splash.close()
        self.splash._notify_presented()
        initialized.assert_not_called()
        self.assertFalse(self.splash._first_frame.isActive())

    def test_image_decode_runs_off_thread_and_results_arrive_on_gui_thread(self):
        import threading
        from source.ui.components.boot_splash import _SplashImages
        gui_thread = threading.get_ident()
        decoded_on, received_on = [], []
        original = _SplashImages._load
        loop = QEventLoop()
        def decode(worker):
            decoded_on.append(threading.get_ident())
            original(worker)
        def received(logo, artwork):
            received_on.append(threading.get_ident())
            loop.quit()
        self.splash._images.loaded.connect(received)
        with patch.object(_SplashImages, "_load", decode):
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
        self.assertEqual(received_on, [gui_thread])
        self.assertEqual(len(decoded_on), 1)
        self.assertNotEqual(decoded_on[0], gui_thread)
        self.assertFalse(self.splash._logo.isNull())
        self.assertFalse(self.splash._artwork.isNull())

    def test_missing_images_are_allowed_and_late_results_are_rejected(self):
        from PySide6.QtGui import QImage, QColor
        self.splash._apply_images(QImage(), QImage())
        self.assertTrue(self.splash._logo.isNull())
        self.splash.cancel()
        image = QImage(8, 8, QImage.Format.Format_ARGB32)
        image.fill(QColor("cyan"))
        self.splash._apply_images(image, image)
        self.assertTrue(self.splash._logo.isNull())
        self.assertTrue(self.splash._artwork.isNull())

    def test_surface_swap_preserves_screen_bounds_and_first_frame(self):
        from PySide6.QtCore import QPointF
        compact_geometry = self.splash.geometry()
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        surface = self.splash._surface
        self.assertEqual(self.splash.geometry(), compact_geometry)
        self.assertTrue(self.splash.isVisible())
        self.assertFalse(self.splash._reveal_started)
        self.splash._start_expansion()
        self.assertFalse(self.splash._reveal_started)
        replacement = surface.grab().toImage()
        origin = self.splash._origin
        replacement_global = origin.translated(QPointF(surface.geometry().topLeft()))
        self.assertEqual(replacement_global, QRectF(compact_geometry))
        self.assertEqual(
            replacement.copy(origin.toRect()), self.splash._compact.toImage()
        )
        self.assertFalse(self.splash._reveal_started)
        self.assertTrue(self.splash.isVisible())
        surface._ready.stop()
        self.splash._start_expansion()
        self.assertTrue(self.splash._reveal_started)
        self.assertFalse(self.splash.isVisible())
        self.assertTrue(surface.isVisible())
        self.assertEqual(self.splash.geometry(), compact_geometry)

    def test_cancel_before_replacement_first_paint_prevents_swap(self):
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        surface = self.splash._surface
        surface.grab()  # Queue readiness, then cancel before its delivery.
        self.splash.cancel()
        self.splash._start_expansion()
        self.assertFalse(surface._ready.isActive())
        self.assertFalse(surface.isVisible())
        self.assertFalse(self.splash._reveal_started)
        self.assertIsNone(self.splash._surface)

    def test_cancel_before_capture_prevents_surface_creation(self):
        self.splash.reveal(self.window)
        self.splash.cancel()
        self.splash._capture_dashboard()
        self.assertIsNone(self.splash._surface)
        self.assertFalse(self.splash._prepare.isActive())

    def test_debug_hold_keeps_event_loop_active_and_defers_completion(self):
        self.splash._hold.setInterval(150)
        done = Mock()
        self.splash.finished.connect(done)
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start(10)
        loop = QEventLoop()
        self.splash.reveal(self.window)
        self.splash.reveal(self.window)  # A duplicate request cannot restart the hold.
        QTimer.singleShot(80, loop.quit)
        loop.exec()
        self.assertTrue(self.splash._hold.isActive())
        self.assertEqual(self.splash.size().width(), 600)
        self.assertFalse(self.window.isVisible())
        self.assertGreater(len(ticks), 2)
        done.assert_not_called()
        QTimer.singleShot(160, loop.quit)
        loop.exec()
        timer.stop()
        self.assertFalse(self.splash._hold.isActive())
        self.assertTrue(self.window.isVisible())
        done.assert_not_called()

    def test_cancellation_and_failure_stop_pending_hold(self):
        for action in (self.splash.cancel, self.splash.stop_animation):
            self.splash._hold.start(5000)
            action()
            self.assertFalse(self.splash._hold.isActive())
            self.assertFalse(self.splash._pulse.isActive())

    def test_launcher_close_during_hold_cancels(self):
        self.splash._hold.setInterval(5000)
        self.splash.reveal(self.window)
        self.window.close()
        self.assertTrue(self.splash._cancelled)
        self.assertFalse(self.splash._hold.isActive())

    def test_expansion_keeps_launcher_geometry_fixed(self):
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        self.splash._surface.grab()
        self.splash._surface._ready.stop()
        self.splash._start_expansion()
        self.splash._reveal.pause()
        target = self.window.geometry()
        self.splash._reveal.setCurrentTime(250)
        self.assertEqual(self.splash._surface.geometry(), target)
        self.assertGreater(self.splash._paint_bounds.width(), 600)
        self.assertLess(self.splash._paint_bounds.width(), target.width())
        self.assertEqual(self.window.geometry(), target)
        self.splash._reveal.setCurrentTime(500)
        self.assertEqual(self.splash._surface.geometry(), target)
        self.assertEqual(self.splash._paint_bounds, QRectF(self.splash._surface.rect()))
        self.assertEqual(self.window.windowOpacity(), 0)
        self.assertEqual(self.splash._fade, 0)
        self.splash._reveal.setCurrentTime(650)
        self.assertEqual(self.splash._surface.geometry(), target)
        self.assertEqual(self.window.geometry(), target)
        self.assertEqual(self.splash.windowOpacity(), 1)
        self.assertAlmostEqual(self.splash._fade, 0.5)

    def test_reveal_completes_once_after_the_animation(self):
        done = Mock()
        self.splash.finished.connect(done)
        loop = QEventLoop()
        self.splash.finished.connect(loop.quit)
        started = time.monotonic()
        self.splash.reveal(self.window)
        QTimer.singleShot(1500, loop.quit)
        loop.exec()
        self.assertGreater(time.monotonic() - started, 0.5)
        done.assert_called_once()
        self.splash._finish_reveal()
        done.assert_called_once()
        self.assertFalse(self.splash.isVisible())
        self.assertEqual(self.window.windowOpacity(), 1)
        self.assertFalse(self.splash._pulse.isActive())

    def test_close_during_reveal_cancels_without_completion(self):
        cancelled, finished = Mock(), Mock()
        self.splash.cancelled.connect(cancelled)
        self.splash.finished.connect(finished)
        self.splash.reveal(self.window)
        self.window.close()
        self.splash.cancel()
        cancelled.assert_called_once()
        finished.assert_not_called()
        self.assertFalse(self.splash._pulse.isActive())

    def test_narrow_launcher_keeps_compact_splash_inside_fixed_canvas(self):
        self.window.resize(420, 640)
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        self.splash._surface.grab()
        self.splash._surface._ready.stop()
        self.splash._start_expansion()
        self.splash._reveal.pause()
        canvas = self.splash._surface.geometry()
        self.assertTrue(QRectF(self.splash._surface.rect()).contains(self.splash._origin))
        self.splash._animate_reveal(800)
        self.assertEqual(self.splash._surface.geometry(), canvas)
        self.assertEqual(self.splash._paint_bounds.width(), 420)
        self.assertEqual(self.splash._paint_bounds.height(), 640)

    def test_snapshot_blend_stays_opaque_and_matches_last_frame(self):
        self.window.setStyleSheet("background: #cf3050;")
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        self.splash._surface.grab()
        self.splash._surface._ready.stop()
        self.splash._start_expansion()
        self.splash._reveal.pause()
        self.splash._reveal.setCurrentTime(650)
        frame = self.splash._surface.grab().toImage()
        self.assertEqual(frame.pixelColor(500, 340).alpha(), 255)
        self.splash._animate_reveal(800)
        frame = self.splash._surface.grab().toImage()
        self.assertEqual(frame.pixelColor(500, 340), self.splash._dashboard.toImage().pixelColor(500, 340))

    def test_cancel_during_fade_or_handoff_prevents_completion(self):
        done = Mock()
        self.splash.finished.connect(done)
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        self.splash._capture_dashboard()
        self.splash._surface.grab()
        self.splash._surface._ready.stop()
        self.splash._start_expansion()
        self.splash._reveal.pause()
        self.splash._reveal.setCurrentTime(650)
        self.splash._finish_reveal()
        self.assertTrue(self.splash._handoff.isActive())
        self.splash.cancel()
        self.splash._complete_handoff()
        done.assert_not_called()
        self.assertFalse(self.splash._handoff.isActive())
        self.assertTrue(self.splash._dashboard.isNull())

    def test_snapshot_failure_reports_and_stops(self):
        from PySide6.QtGui import QPixmap
        failure = Mock()
        self.splash.failed.connect(failure)
        self.splash.reveal(self.window)
        self.splash._prepare.stop()
        with patch.object(self.window, "grab", return_value=QPixmap()):
            self.splash._capture_dashboard()
        failure.assert_called_once()
        self.assertFalse(self.splash._pulse.isActive())
        self.assertTrue(self.splash._dashboard.isNull())

    def test_presentation_completion_starts_services_once(self):
        launcher = SimpleNamespace(
            startup_complete=False, shutdown_started=False,
            _register_start_stop_hotkey=Mock(), _register_auto_keys_stop_hotkey=Mock(),
            timer=Mock(), _start_background_services=Mock(),
        )
        with patch("source.launcher.gui.QTimer.singleShot") as schedule:
            SettingsGUI.complete_startup_presentation(launcher)
            SettingsGUI.complete_startup_presentation(launcher)
        launcher.timer.start.assert_called_once_with(1000)
        schedule.assert_called_once_with(0, launcher._start_background_services)

    def test_deferred_startup_waits_for_presentation(self):
        launcher = SimpleNamespace(
            settings={"launcher_width": 1000, "launcher_height": 680},
            sync_configured_templates=Mock(), resize=Mock(), _build_timer=Mock(),
            show_page=Mock(), load_previous_logs=Mock(), startup_ready=Mock(),
            deferred_startup=True, complete_startup_presentation=Mock(),
        )
        SettingsGUI._finish_startup(launcher)
        launcher.startup_ready.emit.assert_called_once()
        launcher.complete_startup_presentation.assert_not_called()

    def test_boot_module_does_not_import_launcher_pages(self):
        result = subprocess.run(
            [sys.executable, "-c", "import sys; import source.ui.components.boot_splash; assert 'source.launcher' not in sys.modules"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
