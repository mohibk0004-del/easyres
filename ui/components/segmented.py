"""Segmented control with a sliding selection thumb."""

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from theme import tokens as t
from ui import motion

PAD = 3
H = 30


class SegmentedControl(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, options, parent=None, accessible_name="Filter"):
        super().__init__(parent)
        self.options = list(options)
        self._index = 0
        self._thumb = QRectF()
        self._anim = None
        self._hover = -1
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMouseTracking(True)
        self.setFixedHeight(H)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(accessible_name)
        self._update_accessible()

    def value(self):
        return self.options[self._index] if self.options else None

    def set_options(self, options):
        current = self.value()
        self.options = list(options)
        self._index = self.options.index(current) if current in self.options else 0
        self.updateGeometry()
        self._snap()

    def set_value(self, value, animate=True):
        if value in self.options:
            self._select(self.options.index(value), animate)

    def _font(self):
        font = self.font()
        font.setPixelSize(t.FONT_SM)
        font.setWeight(font.Weight.DemiBold)
        return font

    def _segment_widths(self):
        fm = QFontMetrics(self._font())
        return [fm.horizontalAdvance(o) + 24 for o in self.options]

    def sizeHint(self):
        return QSize(sum(self._segment_widths()) + PAD * 2, H)

    def _segment_rects(self):
        widths = self._segment_widths()
        total = sum(widths) or 1
        scale = (self.width() - PAD * 2) / total
        rects, x = [], PAD
        for w in widths:
            rects.append(QRectF(x, PAD, w * scale, H - PAD * 2))
            x += w * scale
        return rects

    def _select(self, index, animate=True):
        if not (0 <= index < len(self.options)):
            return
        changed = index != self._index
        self._index = index
        target = self._segment_rects()[index]
        motion.stop(self._anim)
        if animate and not self._thumb.isNull():
            self._anim = motion.spring(self, QRectF(self._thumb), target, self._set_thumb)
        else:
            self._set_thumb(target)
        self._update_accessible()
        if changed:
            self.changed.emit(self.options[index])

    def _update_accessible(self):
        if self.options:
            self.setAccessibleDescription(f"{self.options[self._index]} selected, {self._index + 1} of {len(self.options)}")

    def _set_thumb(self, rect):
        self._thumb = QRectF(rect)
        self.update()

    def _snap(self):
        rects = self._segment_rects()
        if rects:
            motion.stop(self._anim)
            self._set_thumb(rects[self._index])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._snap()

    def showEvent(self, event):
        super().showEvent(event)
        self._snap()

    def _index_at(self, pos):
        for i, rect in enumerate(self._segment_rects()):
            if rect.contains(pos.x(), pos.y()):
                return i
        return -1

    def mouseMoveEvent(self, event):
        hover = self._index_at(event.position())
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()

    def mousePressEvent(self, event):
        index = self._index_at(event.position())
        if index >= 0:
            self._select(index)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            step = 1 if event.key() == Qt.Key.Key_Right else -1
            self._select((self._index + step) % len(self.options))
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(outer, t.RADIUS_MD, t.RADIUS_MD)
        p.fillPath(path, QColor(t.BG_CARD))
        p.setPen(QPen(QColor(t.ACCENT_PRIMARY if self.hasFocus() else t.BORDER_DEFAULT), 1.5 if self.hasFocus() else 1))
        p.drawPath(path)

        if not self._thumb.isNull():
            thumb = QPainterPath()
            thumb.addRoundedRect(self._thumb, t.RADIUS_SM, t.RADIUS_SM)
            p.fillPath(thumb, QColor(t.BORDER_DEFAULT))

        p.setFont(self._font())
        for i, rect in enumerate(self._segment_rects()):
            selected = i == self._index
            p.setPen(QColor(t.TEXT_PRIMARY if (selected or i == self._hover) else t.TEXT_SECONDARY))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.options[i])
