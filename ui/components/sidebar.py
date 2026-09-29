"""macOS-style sidebar with a spring-animated selection pill."""

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy, QVBoxLayout, QWidget

from theme import tokens as t
from ui import motion
from ui.widgets import draw_glyph


class SidebarItem(QAbstractButton):
    ITEM_H = 36

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setAccessibleName(text)
        self.setToolTip(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(self.ITEM_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.rail = False
        self.badge = False

    def sizeHint(self):
        return QSize(t.SIDEBAR_W - 2 * t.SPACE_SM, self.ITEM_H)

    def event(self, event):
        if event.type() in (event.Type.HoverEnter, event.Type.HoverLeave):
            self.update()
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.click()
                event.accept()
                return
            self.parentWidget().keyPressEvent(event)
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self.underMouse() and not self.isChecked():
            path = QPainterPath()
            path.addRoundedRect(rect, t.RADIUS_MD, t.RADIUS_MD)
            p.fillPath(path, QColor(255, 255, 255, 10))
        if self.hasFocus():
            p.setPen(QPen(QColor(t.ACCENT_PRIMARY), 2))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), t.RADIUS_MD, t.RADIUS_MD)

        color = t.TEXT_PRIMARY if self.isChecked() else t.TEXT_SECONDARY
        icon_x = (self.width() - 18) / 2 if self.rail else 10
        p.save()
        p.translate(icon_x, (self.height() - 18) / 2)
        draw_glyph(p, self.icon_name, color)
        p.restore()

        if self.badge:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.ACCENT_PRIMARY))
            p.drawEllipse(QRectF(icon_x + 14, (self.height() - 18) / 2 - 2, 7, 7))

        if not self.rail:
            font = self.font()
            font.setPixelSize(t.FONT_MD)
            font.setWeight(font.Weight.DemiBold if self.isChecked() else font.Weight.Medium)
            p.setFont(font)
            p.setPen(QColor(color))
            text_rect = QRectF(38, 0, self.width() - 46, self.height())
            p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       QFontMetrics(font).elidedText(self.text(), Qt.TextElideMode.ElideRight, int(text_rect.width())))


class Sidebar(QWidget):
    current_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.items = []
        self._pill = QRectF()
        self._pill_anim = None
        self._current = -1
        self._rail = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(t.SPACE_SM, 0, t.SPACE_SM, t.SPACE_MD)
        self._layout.setSpacing(2)
        self._top = QWidget(self)
        self._top.setFixedHeight(t.HEADER_H)
        self._layout.addWidget(self._top)
        self._items_layout = QVBoxLayout()
        self._items_layout.setSpacing(2)
        self._layout.addLayout(self._items_layout)
        self._layout.addStretch()
        self._bottom_layout = QVBoxLayout()
        self._bottom_layout.setSpacing(2)
        self._layout.addLayout(self._bottom_layout)
        self.setFixedWidth(t.SIDEBAR_W)

    @property
    def header(self):
        """Top area aligned with the page header; used as a drag region."""
        return self._top

    def add_item(self, icon, text, bottom=False):
        item = SidebarItem(icon, text, self)
        index = len(self.items)
        item.clicked.connect(lambda _checked=False, i=index: self.set_current(i))
        (self._bottom_layout if bottom else self._items_layout).addWidget(item)
        self.items.append(item)
        return item

    def current(self):
        return self._current

    def set_rail(self, rail):
        if rail == self._rail:
            return
        self._rail = rail
        self.setFixedWidth(t.SIDEBAR_RAIL_W if rail else t.SIDEBAR_W)
        for item in self.items:
            item.rail = rail
            item.update()
        self._snap_pill()

    def set_current(self, index, animate=True):
        if not (0 <= index < len(self.items)):
            return
        changed = index != self._current
        self._current = index
        self.items[index].setChecked(True)
        target = QRectF(self.items[index].geometry())
        if animate and not self._pill.isNull():
            motion.stop(self._pill_anim)
            self._pill_anim = motion.spring(self, QRectF(self._pill), target, self._set_pill)
        else:
            self._set_pill(target)
        if changed:
            self.current_changed.emit(index)

    def _set_pill(self, rect):
        self._pill = QRectF(rect)
        self.update()

    def _snap_pill(self):
        if 0 <= self._current < len(self.items):
            motion.stop(self._pill_anim)
            self._set_pill(QRectF(self.items[self._current].geometry()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._snap_pill()

    def showEvent(self, event):
        super().showEvent(event)
        self._snap_pill()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.items:
            step = 1 if event.key() == Qt.Key.Key_Down else -1
            index = (self._current + step) % len(self.items)
            self.set_current(index)
            self.items[index].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pill.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self._pill.adjusted(0.5, 0.5, -0.5, -0.5), t.RADIUS_MD, t.RADIUS_MD)
        p.fillPath(path, QColor(88, 101, 242, 38))
        p.setPen(QPen(QColor(88, 101, 242, 90), 1))
        p.drawPath(path)
