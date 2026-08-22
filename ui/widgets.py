"""Reusable UI widgets for EasyRes."""

from PyQt6.QtWidgets import (
    QPushButton, QWidget, QVBoxLayout, QLabel, QMenu, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QPainter, QPainterPath, QBrush, QColor, QIcon

from theme import tokens as t
from theme import styles
from theme.assets import icon_path


class PremiumToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Toggle")
        self._checked = True
        self._pos = 22
        self._focused = False

        self.anim = QPropertyAnimation(self, b"handle_pos")
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.setDuration(t.MOTION_TOGGLE)

    @pyqtProperty(int)
    def handle_pos(self):
        return self._pos

    @handle_pos.setter
    def handle_pos(self, pos):
        self._pos = pos
        self.update()

    def setChecked(self, checked: bool, emit: bool = True):
        if self._checked == checked:
            return
        self._checked = checked
        self.anim.setEndValue(22 if checked else 2)
        self.anim.start()
        if emit:
            self.toggled.emit(checked)

    def isChecked(self) -> bool:
        return self._checked

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        self._focused = True
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focused = False
        self.update()
        super().focusOutEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._checked:
            bg_color = QColor(t.ACCENT_PRIMARY)
        else:
            bg_color = QColor(255, 255, 255, 26)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 13, 13)
        p.fillPath(path, QBrush(bg_color))

        if self._focused:
            p.setPen(QColor(t.ACCENT_HOVER))
            p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 12, 12)

        handle_rect = QRect(self._pos, 2, 22, 22)
        p.setBrush(QBrush(QColor("white")))
        p.setPen(Qt.PenStyle.NoPen)
        p.save()
        p.setBrush(QBrush(QColor(0, 0, 0, 50)))
        p.drawEllipse(handle_rect.translated(0, 1))
        p.restore()
        p.drawEllipse(handle_rect)


class ActionButton(QPushButton):
    def __init__(self, text, parent=None, primary: bool = False, destructive: bool = False):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(styles.button_qss(primary=primary, destructive=destructive))


class IconButton(QPushButton):
    def __init__(self, svg_name: str, tooltip: str, accessible_name: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(t.ICON_BTN_SIZE, t.ICON_BTN_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(accessible_name)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setIcon(QIcon(icon_path(svg_name)))
        self.setIconSize(self.size() * 0.55)
        self.setStyleSheet(styles.icon_button_qss())
        self._svg_name = svg_name

    def set_svg(self, svg_name: str):
        self._svg_name = svg_name
        self.setIcon(QIcon(icon_path(svg_name)))


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(styles.section_label_qss())


class ResolutionHero(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(styles.resolution_hero_qss())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_XL, t.SPACE_XL, t.SPACE_XL, t.SPACE_XL)

        self.section_label = QLabel("CURRENT RESOLUTION")
        self.section_label.setStyleSheet(styles.section_label_qss() + " letter-spacing: 2px;")
        self.section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.res_label = QLabel("1920 × 1080")
        self.res_label.setStyleSheet(
            f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_2XL}px; font-weight: 700; border: none; background: transparent;"
        )
        self.res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hz_label = QLabel("144 Hz")
        self.hz_label.setStyleSheet(
            f"color: {t.ACCENT_PRIMARY}; font-size: {t.FONT_LG}px; font-weight: 600; border: none; background: transparent;"
        )
        self.hz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.section_label)
        layout.addWidget(self.res_label)
        layout.addWidget(self.hz_label)

    def set_resolution(self, width: int, height: int, hz: int):
        self.res_label.setText(f"{width} × {height}")
        self.hz_label.setText(f"{hz} Hz")


class PresetCard(QPushButton):
    delete_requested = pyqtSignal(str, int, int, bool)

    def __init__(
        self,
        width,
        height,
        ratio,
        label,
        is_custom=False,
        hz=None,
        is_active=False,
        parent=None,
    ):
        super().__init__(parent)
        self.res_width = width
        self.res_height = height
        self.is_custom = is_custom
        self.label_text = label
        self.hz = hz
        self._is_active = is_active
        self._card_opacity = 1.0
        self._offset_y = 0

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(t.PRESET_CARD_WIDTH, t.PRESET_CARD_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)

        hz_text = f" @ {hz}Hz" if hz else ""
        res_label = QLabel(f"{width} × {height}{hz_text}")
        res_label.setStyleSheet(styles.preset_card_label_qss(primary=True))
        res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ratio_label = QLabel(ratio)
        ratio_label.setStyleSheet(styles.preset_card_label_qss(primary=False))
        ratio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(label)
        desc_label.setStyleSheet(styles.preset_card_label_qss(primary=None))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(res_label)
        layout.addWidget(ratio_label)
        layout.addWidget(desc_label)

        self._apply_style()

        self._apply_style()

    @pyqtProperty(int)
    def offset_y(self):
        return self._offset_y

    @offset_y.setter
    def offset_y(self, value):
        self._offset_y = value
        self.move(self.x(), self.parent().mapFromGlobal(self.mapToGlobal(self.rect().topLeft())).y() if self.parent() else self.y())

    def set_active(self, active: bool):
        self._is_active = active
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(styles.preset_card_qss(is_custom=self.is_custom, is_active=self._is_active))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(styles.menu_qss())
        action_text = "Delete Custom Resolution" if self.is_custom else "Hide Preset"
        del_action = menu.addAction(action_text)
        action = menu.exec(event.globalPos())
        if action == del_action:
            self.delete_requested.emit(self.label_text, self.res_width, self.res_height, self.is_custom)

    def animate_entrance(self, delay_ms: int = 0):
        # Disabled due to QGraphicsOpacityEffect black-box rendering bug on Windows
        pass
