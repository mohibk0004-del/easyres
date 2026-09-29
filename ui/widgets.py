"""Reusable UI widgets for EasyRes."""

import math

from PyQt6.QtWidgets import (
    QAbstractButton, QPushButton, QWidget, QVBoxLayout, QLabel, QMenu, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QSize, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QIcon, QPixmap, QPen, QFontMetrics

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
    draw_glyph(p, name, color)
    p.end()
    return QIcon(pixmap)


def draw_glyph(p: QPainter, name: str, color, size: int = 18):
    """Draw a line icon in an 18×18 box at the painter's origin."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if size != 18:
        p.scale(size / 18, size / 18)
    c = 9

    if name == "switch":
        p.drawLine(QPointF(3.5, 6), QPointF(14, 6))
        p.drawPolyline([QPointF(11.5, 3.5), QPointF(14, 6), QPointF(11.5, 8.5)])
        p.drawLine(QPointF(14.5, 12), QPointF(4, 12))
        p.drawPolyline([QPointF(6.5, 9.5), QPointF(4, 12), QPointF(6.5, 14.5)])
    elif name == "custom":
        p.drawRoundedRect(QRectF(2.5, 3.5, 13, 11), 2, 2)
        p.drawLine(QPointF(c, 6.5), QPointF(c, 11.5))
        p.drawLine(QPointF(6.5, c), QPointF(11.5, c))
    elif name == "monitor":
        p.drawRoundedRect(QRectF(2.5, 3, 13, 9), 1.8, 1.8)
        p.drawLine(QPointF(c, 12), QPointF(c, 15))
        p.drawLine(QPointF(6, 15), QPointF(12, 15))
    elif name == "keyboard":
        p.drawRoundedRect(QRectF(2, 4.5, 14, 9), 2, 2)
        for x in (5, 8, 11):
            p.drawPoint(QPointF(x, 7.5))
        p.drawPoint(QPointF(13, 7.5))
        p.drawLine(QPointF(6, 10.8), QPointF(12, 10.8))
    elif name == "search":
        p.drawEllipse(QPointF(8, 8), 4.5, 4.5)
        p.drawLine(QPointF(11.4, 11.4), QPointF(15, 15))
    elif name == "close":
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
    p.restore()


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


TONE_COLORS = {
    "": t.TEXT_PRIMARY,
    None: t.TEXT_PRIMARY,
    "accent": t.ACCENT_PRIMARY,
    "warning": t.DESTRUCTIVE_HOVER,
}


class StatusItem(QWidget):
    """Caption + value, painted. Value changes cross-fade."""

    def __init__(self, caption: str, value: str = "--", parent=None):
        super().__init__(parent)
        self._caption = caption
        self._value = value
        self._old_value = None
        self._tone = ""
        self._old_tone = ""
        self._fade = 1.0
        self._anim = None
        self.setAccessibleName(f"{caption}: {value}")
        self.setMinimumWidth(72)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(38)

    def sizeHint(self):
        width = max(QFontMetrics(self._value_font()).horizontalAdvance(self._value),
                    QFontMetrics(self._caption_font()).horizontalAdvance(self._caption))
        return QSize(width + 4, 38)

    def _caption_font(self):
        font = self.font()
        font.setPixelSize(t.FONT_XS)
        font.setWeight(font.Weight.DemiBold)
        return font

    def _value_font(self):
        font = self.font()
        font.setPixelSize(t.FONT_LG)
        font.setWeight(font.Weight.Bold)
        return font

    def set_value(self, value: str, tone: str = ""):
        tone = tone or ""
        if value == self._value and tone == self._tone:
            return
        from ui import motion
        self._old_value, self._old_tone = self._value, self._tone
        self._value, self._tone = value, tone
        self.setAccessibleName(f"{self._caption}: {value}")
        self.updateGeometry()
        motion.stop(self._anim)
        self._anim = motion.tween(self, 0.0, 1.0, t.MOTION_VALUE, self._set_fade)

    def value(self):
        return self._value

    def _set_fade(self, value):
        self._fade = float(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._caption_font())
        p.setPen(QColor(t.TEXT_SECONDARY))
        p.drawText(QRectF(0, 0, self.width(), 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._caption)
        p.setFont(self._value_font())
        value_rect = QRectF(0, 16, self.width(), 22)
        if self._fade < 1.0 and self._old_value is not None:
            p.setOpacity(1.0 - self._fade)
            p.setPen(QColor(TONE_COLORS.get(self._old_tone, t.TEXT_PRIMARY)))
            p.drawText(value_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._old_value)
        p.setOpacity(self._fade)
        p.setPen(QColor(TONE_COLORS.get(self._tone, t.TEXT_PRIMARY)))
        p.drawText(value_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._value)


def mix(a, b, amount):
    a, b = QColor(a), QColor(b)
    return QColor(
        round(a.red() + (b.red() - a.red()) * amount),
        round(a.green() + (b.green() - a.green()) * amount),
        round(a.blue() + (b.blue() - a.blue()) * amount),
        round(a.alpha() + (b.alpha() - a.alpha()) * amount),
    )


class ModeTile(QAbstractButton):
    """A resolution tile, fully painted so press, active and pending states
    animate without child widgets or stylesheet re-polishing."""

    apply_requested = pyqtSignal(int, int, object)
    save_requested = pyqtSignal(int, int, int)
    delete_requested = pyqtSignal(str, int, int, bool)
    active_clicked = pyqtSignal()

    PRESS_SCALE = 0.97

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
        self._active_p = 1.0 if is_active else 0.0
        self._hover = False
        self._scale = 1.0
        self._pending = False
        self._spin = 0.0
        self._anims = {}
        self._spinner = None

        self.setMinimumWidth(t.MODE_TILE_MIN_WIDTH)
        self.setFixedHeight(t.MODE_TILE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.clicked.connect(self._apply)
        self._update_text()

    # -- state --------------------------------------------------------
    def _hz_text(self):
        if self.hz:
            return f"{self.hz} Hz"
        return f"up to {self.rates[0]} Hz" if self.rates else "Highest Hz"

    def _update_text(self):
        name = f"{self.label_text}, " if (self.is_custom and self.label_text) else ""
        state = "Active" if self._is_active else ("Switching" if self._pending else self._hz_text())
        self.setAccessibleName(f"{name}{self.res_width} by {self.res_height}, {self.ratio}, {state}"
                               + ("" if self._is_active else ". Press to apply"))
        self.setToolTip("Current resolution" if self._is_active else "Apply. Right-click for refresh rates and more.")

    def matches(self, w, h, hz):
        return self.res_width == w and self.res_height == h and (hz is None or self.hz in (None, hz))

    def set_active(self, active):
        if active == self._is_active:
            return
        self._is_active = active
        self.set_pending(False)
        self._update_text()
        self._animate("active", self._active_p, 1.0 if active else 0.0, t.MOTION_FAST, "_active_p")

    def set_pending(self, pending):
        from ui import motion
        if pending == self._pending:
            return
        self._pending = pending
        self._update_text()
        motion.stop(self._spinner)
        self._spinner = None
        if pending and duration(1):
            from PyQt6.QtCore import QVariantAnimation
            self._spinner = QVariantAnimation(self)
            self._spinner.setStartValue(0.0)
            self._spinner.setEndValue(360.0)
            self._spinner.setDuration(900)
            self._spinner.setLoopCount(-1)
            self._spinner.valueChanged.connect(self._set_spin)
            self._spinner.start()
        self.update()

    def _set_spin(self, value):
        self._spin = float(value)
        self.update()

    def _animate(self, key, start, end, ms, attr, curve=None):
        from ui import motion
        motion.stop(self._anims.get(key))

        def apply(value):
            setattr(self, attr, float(value))
            self.update()

        self._anims[key] = motion.tween(self, start, end, ms, apply, curve=curve)

    # -- input --------------------------------------------------------
    def event(self, event):
        if event.type() == event.Type.HoverEnter:
            self._hover = True
            self.update()
        elif event.type() == event.Type.HoverLeave:
            self._hover = False
            self.update()
        return super().event(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate("scale", self._scale, self.PRESS_SCALE, 90, "_scale")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        from ui import motion
        self._animate("scale", self._scale, 1.0, t.MOTION_SPRING, "_scale", motion.spring_curve())

    def sizeHint(self):
        return QSize(t.MODE_TILE_MIN_WIDTH, t.MODE_TILE_HEIGHT)

    # -- paint --------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.55)

        w, h = self.width(), self.height()
        if self._scale != 1.0:
            p.translate(w / 2, h / 2)
            p.scale(self._scale, self._scale)
            p.translate(-w / 2, -h / 2)

        base = QColor(t.BG_CARD_CUSTOM if self.is_custom else t.BG_CARD)
        hover = QColor(t.BG_CARD_CUSTOM_HOVER if self.is_custom else t.BG_CARD_HOVER)
        bg = hover if (self._hover and self.isEnabled()) else base
        active_bg = mix(base, t.ACCENT_PRIMARY, 0.12)
        bg = mix(bg, active_bg, self._active_p)

        border = bg
        if self._hover and self.isEnabled():
            border = QColor(t.BORDER_HOVER)
        border = mix(border, t.ACCENT_PRIMARY, self._active_p)
        if self.hasFocus():
            border = QColor(t.ACCENT_PRIMARY)

        rect = QRectF(1, 1, w - 2, h - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, t.RADIUS_MD, t.RADIUS_MD)
        p.fillPath(path, bg)
        p.setPen(QPen(border, 2))
        p.drawRoundedRect(rect, t.RADIUS_MD, t.RADIUS_MD)

        pad = t.SPACE_MD
        text_w = w - pad * 2
        font = self.font()
        font.setPixelSize(t.FONT_MD)
        font.setWeight(font.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(t.TEXT_PRIMARY))
        fm = QFontMetrics(font)
        p.drawText(QRectF(pad, pad - 1, text_w, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   fm.elidedText(f"{self.res_width} × {self.res_height}", Qt.TextElideMode.ElideRight, int(text_w)))

        font.setPixelSize(t.FONT_SM)
        font.setWeight(font.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor(t.TEXT_SECONDARY))
        meta = self.label_text if (self.is_custom and self.label_text) else self.ratio
        fm = QFontMetrics(font)
        p.drawText(QRectF(pad, pad + 18, text_w, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   fm.elidedText(meta or "", Qt.TextElideMode.ElideRight, int(text_w)))

        bottom = QRectF(pad, h - pad - 16, text_w, 16)
        if self._pending:
            arc = QRectF(pad, h - pad - 13, 10, 10)
            p.setPen(QPen(QColor(t.TEXT_PRIMARY), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(arc, int(-self._spin * 16), 270 * 16)
            p.drawText(bottom.adjusted(16, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "Switching…")
        elif self._active_p > 0.5:
            font.setWeight(font.Weight.DemiBold)
            p.setFont(font)
            p.setPen(QColor(t.TEXT_PRIMARY))
            p.setBrush(QColor(t.ACCENT_PRIMARY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(pad, h - pad - 11, 6, 6))
            p.setPen(QColor(t.TEXT_PRIMARY))
            p.drawText(bottom.adjusted(12, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "Active")
        else:
            p.drawText(bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._hz_text())

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
