"""Shared animated application-overlay lifecycle for previews and release notes."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

# Shared transition durations in milliseconds; adjust here for templates and release notes.
POPOUT_OPEN_MS = 420
POPOUT_CLOSE_MS = 360


class AnimatedPopout:
    """Share reversible animation, dismissal, resize handling, and focus restoration."""

    def focus_targets(self):
        """Return the visible controls participating in the overlay focus cycle."""
        return [self.close_button] + ([self.import_button] if hasattr(self, "import_button") and self.import_button.isEnabled() else [])

    def _animate(self, end: float, duration: int):
        """Reverse from current progress without replacing the live overlay."""
        self.animation.stop()
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.progress)
        self.animation.setEndValue(end)
        self.panel.hide()
        self.animation.start()

    def _frame(self, value: float):
        """Advance snapshot geometry and background dimming together."""
        self.progress = float(value)
        self.update()

    def _finished(self):
        """Restore the source focus only after the reverse animation ends."""
        if self.closing:
            self.hide()
            QApplication.instance().removeEventFilter(self)
            if self.card is not None and isValid(self.card) and self.card.isVisible():
                self.card.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.panel.show()
            self.close_button.setFocus()

    def close_preview(self):
        """Shrink back to the source, or fade centrally if it disappeared."""
        if not self.isVisible() or self.closing:
            return
        self.closing = True
        if self.panel.isVisible():
            self._capture_panel()
        if isValid(self.card) and self.card.isVisible():
            self._map_source()
        else:
            self.source = self.target.adjusted(30, 30, -30, -30)
            if hasattr(self, "image_target"):
                self.image_source = self.image_target.adjusted(15, 15, -15, -15)
            self.source_clip = self.rect()
        self._animate(0.0, POPOUT_CLOSE_MS)

    def eventFilter(self, watched: object, event: QEvent):
        """Track window bounds and keep keyboard navigation inside the preview."""
        if not self.isVisible():
            return False
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
            if isValid(self.card):
                self._map_source()
            self._prepare_panel()
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close_preview()
                return True
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                targets = self.focus_targets()
                current = QApplication.focusWidget()
                direction = -1 if event.key() == Qt.Key.Key_Backtab or event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
                index = targets.index(current) if current in targets else 0
                targets[(index + direction) % len(targets)].setFocus()
                return True
        return False

    def mousePressEvent(self, event: object):
        """Outside clicks dismiss only; they never trigger import."""
        if not self.target.contains(event.position().toPoint()):
            self.close_preview()
        event.accept()
