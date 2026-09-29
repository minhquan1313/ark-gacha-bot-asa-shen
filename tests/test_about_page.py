"""Combined About page state, navigation, geometry, and website verification."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt, QAbstractAnimation
from PySide6.QtTest import QTest
from test_dashboard_redesign import DashboardRedesignTests

from source.launcher.utils.update_service import UpdateCheckResult, UpdateManifest, load_manifest


class AboutPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DashboardRedesignTests.setUpClass()

    def window(self):
        """Build a full shell with network, startup, and dialog actions mocked."""
        window = DashboardRedesignTests.window(self, ('_start_update_check', 'dialog', 'confirm'))
        window.show_page('about')
        QTest.qWait(50)
        return window, window.about_update_page

    def test_navigation_states_website_and_captures(self):
        window, page = self.window()
        self.assertNotIn('update', window.nav_buttons)
        self.assertEqual(page.state_icon.state, 'idle')
        for name in ('dashboard', 'update', 'about'):
            window.show_page(name)
        window._start_update_check.assert_not_called()
        self.assertIs(window.stack.currentWidget(), page)
        with patch('source.launcher.config.constants.OFFICIAL_WEBSITE_URL', ''):
            page.website.click()
            window.dialog.assert_called_with('Website', 'Out of money so no website for now :>', 'info')
        with patch('source.launcher.config.constants.OFFICIAL_WEBSITE_URL', 'https://example.com'), patch('source.launcher.pages.logs_tools.QDesktopServices.openUrl') as launch:
            page.website.click()
            self.assertEqual(launch.call_args.args[0].toString(), 'https://example.com')
        manifest = UpdateManifest('1.0.0', '2026-07-22', 'Shen GBot - Version 1.0.0', ('A test release note', 'Another test release note'))
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, False, 'Offline'), False)
        self.assertEqual(page.state_icon.state, 'error')
        self.assertEqual(page.latest_badge.text(), 'Current')
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, True), False)
        self.assertEqual(page.action.text(), 'UPDATE')
        self.assertEqual(page.latest_badge.text(), 'Lastest')
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, False), False)
        self.assertEqual(page.state_icon.state, 'current')
        self.assertEqual(page.status.text(), "You're up to date!")
        # Capture actual bundled release content; the successful check is mocked.
        installed = load_manifest()
        window._on_update_check_finished(UpdateCheckResult(installed, installed, False), False)
        output = Path('.artifacts/about')
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get('QT_SCALE_FACTOR', '1')
        for width, height in ((1200, 800), (1536, 1024), (900, 800)):
            window.resize(width, height)
            QTest.qWait(600)
            self.assertEqual(page._stacked, width == 900)
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(), 0)
            if not page._stacked:
                self.assertEqual(page.scroll.verticalScrollBar().maximum(), 0)
                middle = (page.left.geometry().right()+1+page.right.x())/2
                expected = page.hero.mapFromGlobal(page.content.mapToGlobal(QPoint(round(middle), 0))).x()
                self.assertAlmostEqual(page.hero.dip_center, expected, delta=1)
            window.grab().save(str(output / f'about-{width}x{height}-{scale}.png'))
        window.show_page('dashboard')
        window.show_page('about')
        self.assertEqual(page.state_icon.state, 'current')
        window._start_update_check.assert_not_called()

    def test_long_notes_and_manifest_error(self):
        window, page = self.window()
        manifest = UpdateManifest('1.0.0', '', 'Release', ('Long release notes ' * 150,))
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, False), False)
        window.resize(1200, 800)
        QTest.qWait(60)
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(page.scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(page.notes.show_more.isVisible())
        page.notes.show_more.click()
        QTest.qWait(500)
        self.assertIn('Long release notes ' * 10, page.notes.overlay.text.toPlainText())
        window.grab().save(f'.artifacts/about/release-notes-popup-{os.environ.get("QT_SCALE_FACTOR", "1")}.png')
        page.notes.overlay.close_preview()
        QTest.qWait(400)
        self.assertFalse(page.notes.overlay.isVisible())

    def test_invalid_manifest_is_not_success(self):
        """An unreadable local manifest produces visible error feedback."""
        with patch('source.launcher.pages.logs_tools.load_manifest', side_effect=ValueError('broken manifest')):
            window, page = self.window()
        self.assertEqual(page.state_icon.state, 'error')
        self.assertIn('broken manifest', page.support.text())
        self.assertEqual(page.latest_badge.text(), 'Current')
        window._start_update_check.assert_not_called()

    def test_success_animation_lifecycle_and_failed_check_preserves_notes(self):
        window, page = self.window()
        manifest = UpdateManifest('1.1.0', '2026-09-22', 'Release 1.1', ('Preserved release information',))
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, True), False)
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, False, 'Connection failed'), False)
        self.assertEqual(page.notes.manifest, manifest)
        self.assertEqual(page.latest_badge.text(), 'Lastest')
        self.assertEqual(page.state_icon.pulse.state(), QAbstractAnimation.State.Stopped)
        window._on_update_check_finished(UpdateCheckResult(manifest, manifest, False), False)
        QTest.qWait(550)
        self.assertAlmostEqual(page.state_icon.reveal, 1)
        self.assertEqual(page.state_icon.pulse.state(), QAbstractAnimation.State.Running)
        window.show_page('dashboard')
        self.assertEqual(page.state_icon.pulse.state(), QAbstractAnimation.State.Stopped)
        window.show_page('about')
        page.set_state('checking')
        self.assertEqual(page.state_icon.draw_animation.state(), QAbstractAnimation.State.Stopped)
        self.assertEqual(page.state_icon.pulse.state(), QAbstractAnimation.State.Stopped)

    def test_bounded_notes_popup_resize_reverse_keyboard_and_focus(self):
        window, page = self.window()
        window.resize(1200, 800)
        QTest.qWait(60)
        for notes in ((), ('Short note',), ('W'*3000,), tuple('Release improvement '+str(i) for i in range(30))):
            page.set_manifest(UpdateManifest('1.0.0', '', 'Release', notes))
            QTest.qWait(20)
            self.assertEqual(page.notes.show_more.isVisible(), len(notes)>1 or bool(notes and len(notes[0])>100))
            self.assertEqual(page.scroll.verticalScrollBar().maximum(), 0)
        page.notes.show_more.click()
        QTest.qWait(70)
        popup = page.notes.overlay
        self.assertGreater(popup.progress, 0)
        self.assertLess(popup.progress, 1)
        QTest.keyClick(popup, Qt.Key.Key_Escape)
        QTest.qWait(400)
        self.assertFalse(popup.isVisible())
        self.assertTrue(page.notes.show_more.hasFocus())
        page.notes.show_more.click()
        QTest.qWait(500)
        window.resize(1536, 1024)
        QTest.qWait(60)
        self.assertEqual(popup.geometry(), window.rect())
        self.assertTrue(popup.rect().contains(popup.panel.geometry()))
        self.assertIn('Release improvement 29', popup.text.toPlainText())
        QTest.mouseClick(popup, Qt.MouseButton.LeftButton, pos=QPoint(4,4))
        QTest.qWait(400)
        self.assertFalse(popup.isVisible())
        self.assertEqual(page.scroll.verticalScrollBar().value(), 0)

    def test_desktop_content_contours_and_track_geometry(self):
        window, page = self.window()
        for width,height in ((1200,800),(1536,1024)):
            window.resize(width,height)
            QTest.qWait(80)
            self.assertEqual(page.content.height(), page.scroll.viewport().height())
            self.assertTrue(page.right.rect().contains(page.quote.geometry()))
            self.assertTrue(page.left.rect().contains(page.notes.geometry()))
            self.assertLessEqual(page.support.geometry().bottom(), page.action.y())
            self.assertEqual(page.action.height(), 44)
            self.assertEqual(page.right.x()-page.left.width(), 16)
            self.assertFalse(page.left.outline().contains(QPointF(page.left.width()-2,2)))
            self.assertFalse(page.right.outline().contains(QPointF(2,2)))
            self.assertTrue(page.left.outline().contains(QPointF(20,20)))
            self.assertTrue(page.right.outline().contains(QPointF(40,40)))
            self.assertLess(page.brand.geometry().center().x(), page.right.width()/2)
