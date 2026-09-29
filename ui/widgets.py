"""Reusable UI widgets for EasyRes."""

import math

from PyQt6.QtWidgets import (
    QAbstractButton, QPushButton, QWidget, QVBoxLayout, QLabel, QMenu, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QSize, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QIcon, QPixmap, QPen

from theme import tokens as t
from theme import styles
from theme.motion import duration

ICON_RENDER_SCALE = 3  # Painted icons stay sharp up to 300% display scaling.


class PremiumToggle(QAbstractButton):
    """Animated switch. A checkable button, so keyboard (Space) and
    accessibility (checked state) come from Qt."""

    TRACK_W = 44
    TRACK_H = 24
    HANDLE = 18

    def __init__(self, accessible_name: str = "Toggle", parent=None):
        super().__init__(parent)
        self._progress = 1.0
        self.anim = QPropertyAnimation(self, b"progress", self)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setCheckable(True)
        self.setChecked(True, emit=False)
        self.setFixedSize(self.TRACK_W, self.TRACK_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(accessible_name)

    def sizeHint(self):
        return QSize(self.TRACK_W, self.TRACK_H)

    @pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value
        self.update()

    def setChecked(self, checked: bool, emit: bool = True):
        if not emit:
            blocked = self.blockSignals(True)
            super().setChecked(checked)
            self.blockSignals(blocked)
        else:
            super().setChecked(checked)

    def checkStateSet(self):
        super().checkStateSet()
        self._animate()

    def nextCheckState(self):
        super().nextCheckState()
        self._animate()

    def _animate(self):
        target = 1.0 if self.isChecked() else 0.0
        ms = duration(t.MOTION_TOGGLE)
        self.anim.stop()
        if ms == 0 or not self.isVisible():
            self.progress = target
            return
        self.anim.setDuration(ms)
        self.anim.setStartValue(self._progress)
        self.anim.setEndValue(target)
        self.anim.start()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        radius = rect.height() / 2

        off = QColor(t.BORDER_HOVER)
        on = QColor(t.ACCENT_HOVER)
        track = QColor(
            round(off.red() + (on.red() - off.red()) * self._progress),
            round(off.green() + (on.green() - off.green()) * self._progress),
            round(off.blue() + (on.blue() - off.blue()) * self._progress),
        )
        if not self.isEnabled():
            track.setAlpha(110)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.fillPath(path, track)

        if self.hasFocus():
            p.setPen(QPen(QColor(t.TEXT_PRIMARY), 2))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

        margin = (self.TRACK_H - self.HANDLE) / 2
        travel = self.TRACK_W - self.HANDLE - margin * 2
        x = margin + travel * self._progress
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(QRectF(x, margin + 1, self.HANDLE, self.HANDLE))
        p.setBrush(QColor(t.TEXT_PRIMARY))
        p.drawEllipse(QRectF(x, margin, self.HANDLE, self.HANDLE))


class ActionButton(QPushButton):
    def __init__(self, text, parent=None, primary: bool = False, destructive: bool = False):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        if primary:
            self.setProperty("variant", "primary")
        elif destructive:
            self.setProperty("variant", "destructive")


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, accessible_name: str, parent=None, danger: bool = False):
        super().__init__(parent)
        self.setFixedSize(t.ICON_BTN_SIZE, t.ICON_BTN_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(accessible_name)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setIconSize(QSize(18, 18))
        self.setProperty("variant", "icon")
        if danger:
            self.setProperty("danger", True)
        self.set_icon_name(icon_name)

    def set_icon_name(self, icon_name: str):
        self.setIcon(painted_icon(icon_name))


def painted_icon(name: str, color: str = t.TEXT_SECONDARY, size: int = 18) -> QIcon:
    scale = ICON_RENDER_SCALE
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(scale)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    c = size / 2

    if name == "close":
        p.drawLine(QPointF(5, 5), QPointF(13, 13))
        p.drawLine(QPointF(13, 5), QPointF(5, 13))
    elif name == "minimize":
        p.drawLine(QPointF(5, 9), QPointF(13, 9))
    elif name == "maximize":
        p.drawRoundedRect(QRectF(5, 5, 8, 8), 1.5, 1.5)
    elif name == "restore":
        p.drawRoundedRect(QRectF(4.5, 7, 6.5, 6.5), 1.2, 1.2)
        p.drawPolyline([QPointF(7, 7), QPointF(7, 4.5), QPointF(13.5, 4.5), QPointF(13.5, 11), QPointF(11, 11)])
    elif name == "help":
        p.drawEllipse(QPointF(c, c), 6.5, 6.5)
        path = QPainterPath(QPointF(7, 7.2))
        path.cubicTo(QPointF(7, 5.2), QPointF(11, 5.2), QPointF(11, 7.2))
        path.cubicTo(QPointF(11, 8.6), QPointF(9, 8.8), QPointF(9, 10.4))
        p.drawPath(path)
        p.drawPoint(QPointF(9, 12.6))
    elif name == "settings":
        p.drawEllipse(QPointF(c, c), 2.4, 2.4)
        p.drawEllipse(QPointF(c, c), 5.2, 5.2)
        for i in range(8):
            angle = math.radians(i * 45)
            p.drawLine(
                QPointF(c + math.cos(angle) * 5.2, c + math.sin(angle) * 5.2),
                QPointF(c + math.cos(angle) * 7.2, c + math.sin(angle) * 7.2),
            )
    else:
        p.drawRoundedRect(QRectF(5, 5, 8, 8), 1.5, 1.5)

    p.end()
    return QIcon(pixmap)


def make_label(text: str = "", role: str = "body", tone: str = None, wrap: bool = False, parent=None) -> QLabel:
    """Plain-text label styled by role. Plain text so device names or other
    external strings are never interpreted as rich text."""
    label = QLabel(parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    label.setProperty("role", role)
    if tone:
        label.setProperty("tone", tone)
    label.setWordWrap(wrap)
    return label


def set_tone(widget, tone):
    styles.set_props(widget, tone=tone or "")


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)
        self.setProperty("role", "section")


class Panel(QWidget):
    """Flat elevated surface. Styled via the app stylesheet."""

    def __init__(self, kind: str = "true", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("panel", kind)


class StatPill(QWidget):
    def __init__(self, label: str, value: str = "--", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("panel", "inset")
        self.setMinimumHeight(68)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_LG, t.SPACE_MD)
        layout.setSpacing(2)

        self.label = SectionLabel(label)
        self.value = make_label(value, role="value")
        self.value.setMinimumWidth(0)
        self.value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._label_text = label

        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, value: str, accent: bool = False, warning: bool = False):
        self.value.setText(value)
        self.setAccessibleName(f"{self._label_text}: {value}")
        set_tone(self.value, "warning" if warning else ("accent" if accent else None))


class ModeRow(QPushButton):
    apply_requested = pyqtSignal(int, int, object)
    save_requested = pyqtSignal(int, int, int)
    delete_requested = pyqtSignal(str, int, int, bool)
    active_clicked = pyqtSignal()

    def __init__(self, width, height, ratio, label, is_custom=False, hz=None, is_active=False,
                 rates=None, parent=None):
        super().__init__(parent)
        self.res_width = width
        self.res_height = height
        self.ratio = ratio
        self.label_text = label
        self.is_custom = is_custom
        self.hz = hz
        self.rates = list(rates or [])
        self._is_active = is_active
        max_hz = self.rates[0] if self.rates else None
        self.setMinimumWidth(t.MODE_TILE_MIN_WIDTH)
        self.setFixedHeight(t.MODE_TILE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setProperty("variant", "tile")
        self.setProperty("custom", bool(is_custom))
        self.setProperty("active", bool(is_active))
        self.clicked.connect(self._apply)

        hz_text = f"{hz} Hz" if hz else (f"up to {max_hz} Hz" if max_hz else "Highest Hz")
        state_text = "Active" if is_active else hz_text
        name = f"{label}, " if (is_custom and label) else ""
        self.setAccessibleName(
            f"{name}{width} by {height}, {ratio}, {state_text}"
            + ("" if is_active else ". Press to apply")
        )
        self.setToolTip("Current resolution" if is_active else "Apply this resolution. Right-click for more.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_MD, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)
        layout.setSpacing(2)

        title = make_label(f"{width} × {height}", role="strong")
        title.setMinimumWidth(0)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        meta_bits = [label] if (is_custom and label) else [ratio]
        meta = make_label("  ·  ".join(bit for bit in meta_bits if bit), role="caption")
        meta.setMinimumWidth(0)
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        state = make_label(("●  Active" if is_active else hz_text), role="caption" if not is_active else "strong")
        state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addStretch()
        layout.addWidget(state)

    def _apply(self):
        if self._is_active:
            self.active_clicked.emit()
            return
        self.apply_requested.emit(self.res_width, self.res_height, self.hz)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        apply_action = menu.addAction("Apply")
        apply_action.setEnabled(not self._is_active)
        rate_actions = {}
        save_actions = {}
        if not self.is_custom and self.rates:
            apply_at = menu.addMenu("Apply at")
            save_at = menu.addMenu("Save to My Modes at")
            for rate in self.rates:
                rate_actions[apply_at.addAction(f"{rate} Hz")] = rate
                save_actions[save_at.addAction(f"{rate} Hz")] = rate
        menu.addSeparator()
        action_text = "Delete from My Modes" if self.is_custom else "Hide from List"
        delete_action = menu.addAction(action_text)
        action = menu.exec(event.globalPos())
        if action is None:
            return
        if action == delete_action:
            self.delete_requested.emit(self.label_text, self.res_width, self.res_height, self.is_custom)
        elif action == apply_action:
            self._apply()
        elif action in rate_actions:
            self.apply_requested.emit(self.res_width, self.res_height, rate_actions[action])
        elif action in save_actions:
            self.save_requested.emit(self.res_width, self.res_height, save_actions[action])
