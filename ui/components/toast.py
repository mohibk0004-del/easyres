"""Status message for the recovery bar: slides up and fades in, then out."""

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from theme import tokens as t
from ui import motion

TONES = {
    "": t.TEXT_SECONDARY,
    "success": t.TEXT_PRIMARY,
    "warning": t.DESTRUCTIVE_HOVER,
}
RISE = 6


class Toast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAccessibleName("Status")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._text = ""
        self._tone = ""
        self._p = 0.0
        self._anim = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_message)

    def text(self):
        return self._text

    def sizeHint(self):
        return QSize(200, 20)

    def show_message(self, text, tone="", ms=t.TOAST_MS):
        self._timer.stop()
        was_visible = self._p > 0.99 and self._text
        self._text, self._tone = text, tone or ""
        self.setAccessibleDescription(text)
        self.setToolTip(text)
        motion.stop(self._anim)
        if was_visible:
            self._set_p(1.0)
        else:
            self._anim = motion.tween(self, self._p, 1.0, t.MOTION_FAST, self._set_p)
        if ms:
            self._timer.start(ms)

    def hide_message(self):
        motion.stop(self._anim)
        self._anim = motion.tween(self, self._p, 0.0, t.MOTION_STANDARD, self._set_p,
                                  on_finished=self._cleared, curve=motion.ease_in())

    def _cleared(self):
        if self._p <= 0.01:
            self._text = ""
            self.setToolTip("")

    def _set_p(self, value):
        self._p = float(value)
        self.update()

    def paintEvent(self, event):
        if not self._text or self._p <= 0:
            return
        p = QPainter(self)
        p.setOpacity(self._p)
        font = self.font()
        font.setPixelSize(t.FONT_SM)
        font.setWeight(font.Weight.Medium)
        p.setFont(font)
        p.setPen(QColor(TONES.get(self._tone, t.TEXT_SECONDARY)))
        rect = QRectF(0, RISE * (1.0 - self._p), self.width(), self.height())
        text = QFontMetrics(font).elidedText(self._text, Qt.TextElideMode.ElideRight, self.width())
        p.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
