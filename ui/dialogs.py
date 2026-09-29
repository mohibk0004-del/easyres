"""Top-level dialogs, used only when the main window is hidden (tray use).
While the window is visible, the same calls open in-window sheets."""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QMessageBox,
    QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

from theme import tokens as t
from theme.motion import duration
from ui.widgets import ActionButton, make_label

StandardButton = QMessageBox.StandardButton

DEFAULT_LABELS = {
    StandardButton.Ok: "OK",
    StandardButton.Yes: "Yes",
    StandardButton.No: "No",
    StandardButton.Cancel: "Cancel",
    StandardButton.Close: "Close",
}
# Dismissive buttons first, affirmative last (right-most), macOS style.
BUTTON_ORDER = (StandardButton.Cancel, StandardButton.No, StandardButton.Close, StandardButton.Ok, StandardButton.Yes)
AFFIRMATIVE = (StandardButton.Yes, StandardButton.Ok)


def button_specs(buttons, icon, labels=None):
    """[(label, StandardButton, kind)] in display order, plus the cancel value."""
    labels = {**DEFAULT_LABELS, **(labels or {})}
    warning = icon in (QMessageBox.Icon.Warning, QMessageBox.Icon.Critical)
    present = [b for b in BUTTON_ORDER if buttons & b]
    specs = []
    for standard in present:
        affirmative = standard in AFFIRMATIVE and len(present) > 1
        kind = ("destructive" if warning else "primary") if affirmative else "secondary"
        specs.append((labels.get(standard, standard.name), standard, kind))
    cancel = (StandardButton.Cancel if buttons & StandardButton.Cancel else
              StandardButton.No if buttons & StandardButton.No else StandardButton.Ok)
    return specs, cancel


class BaseStyledDialog(QDialog):
    def __init__(self, title_text, width, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title_text)
        self._drag_offset = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)

        self.container = QWidget()
        self.container.setObjectName("DialogCard")
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.container.setFixedWidth(width)
        # Holds initial focus so no control shows a focus ring on open;
        # Enter still triggers the default button, Tab moves into controls.
        self.container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(t.SHADOW_BLUR)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, t.SHADOW_OFFSET_Y)
        self.container.setGraphicsEffect(shadow)

        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(t.SPACE_2XL, t.SPACE_2XL, t.SPACE_2XL, t.SPACE_XL)
        self.content_layout.setSpacing(t.SPACE_MD)

        self.title_lbl = make_label(title_text, role="dialog-title", wrap=True)
        self.content_layout.addWidget(self.title_lbl)

        main_layout.addWidget(self.container)

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()
        parent = self.parentWidget()
        if parent and parent.isVisible():
            center = parent.frameGeometry().center()
        else:
            screen = self.screen()
            center = screen.availableGeometry().center() if screen else self.frameGeometry().center()
        geometry = self.frameGeometry()
        geometry.moveCenter(center)
        self.move(geometry.topLeft())
        self.container.setFocus(Qt.FocusReason.OtherFocusReason)
        ms = duration(t.MOTION_FADE)
        if ms:
            self.setWindowOpacity(0.0)
            self._fade = QPropertyAnimation(self, b"windowOpacity", self)
            self._fade.setDuration(ms)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._fade.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def add_button_row(self, buttons):
        row = QHBoxLayout()
        row.setSpacing(t.SPACE_SM)
        row.addStretch()
        for button in buttons:
            row.addWidget(button)
        self.content_layout.addSpacing(t.SPACE_SM)
        self.content_layout.addLayout(row)


class MessageDialog(BaseStyledDialog):
    def __init__(self, parent, title, text, icon, buttons, cb_text=None, labels=None):
        super().__init__(title, 420, parent)
        specs, self.result_button = button_specs(buttons, icon, labels)
        self.setAccessibleName(title)
        self.setAccessibleDescription(text)

        body = make_label(text, role="muted", wrap=True)
        body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.content_layout.addWidget(body)

        self.checkbox = None
        if cb_text:
            self.checkbox = QCheckBox(cb_text)
            self.content_layout.addWidget(self.checkbox)

        widgets = []
        for label, standard, kind in specs:
            button = ActionButton(label, primary=kind == "primary", destructive=kind == "destructive")
            button.clicked.connect(lambda _checked=False, b=standard: self._finish(b))
            widgets.append(button)
        if widgets:
            widgets[-1].setDefault(True)
        self.add_button_row(widgets)

    def _finish(self, button):
        self.result_button = button
        self.accept()


def _sheet_host(parent):
    window = parent.window() if parent is not None else None
    if window is not None and hasattr(window, "sheet_host") and window.isVisible() and not window.isMinimized():
        return window.sheet_host()
    return None


def themed_message_box(parent, title, text, icon=QMessageBox.Icon.Information,
                       buttons=StandardButton.Ok, cb_text=None, labels=None):
    """Drop-in replacement for QMessageBox with EasyRes styling.

    Opens as an in-window sheet when the main window is visible, otherwise
    as a frameless dialog. Returns the chosen StandardButton, or
    (button, checked) when cb_text is given.
    """
    host = _sheet_host(parent)
    if host is not None:
        from ui.components.sheet import Sheet
        specs, cancel = button_specs(buttons, icon, labels)
        sheet = Sheet(host, title, text, specs, cancel_value=cancel, checkbox_text=cb_text)
        result = sheet.exec()
        if cb_text:
            return result, bool(sheet.checkbox and sheet.checkbox.isChecked())
        return result

    dialog = MessageDialog(parent, title, text, icon, buttons, cb_text, labels)
    dialog.exec()
    if dialog.checkbox is not None:
        return dialog.result_button, dialog.checkbox.isChecked()
    return dialog.result_button


class RevertDialog(BaseStyledDialog):
    """Keep-or-revert countdown after a resolution change, for when the main
    window is hidden. Reverts automatically if the screen went black."""

    def __init__(self, mode_text, seconds=t.REVERT_SECONDS, parent=None):
        super().__init__("Keep this resolution?", 400, parent)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._remaining = seconds
        self.keep = False

        self.body = make_label("", role="muted", wrap=True)
        self._mode_text = mode_text
        self.content_layout.addWidget(self.body)

        revert = ActionButton("Revert")
        revert.clicked.connect(self.reject)
        keep = ActionButton("Keep", primary=True)
        keep.clicked.connect(self._keep)
        keep.setDefault(True)
        self.add_button_row([revert, keep])

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._update_text()
        self._timer.start()

    def _update_text(self):
        self.body.setText(f"Switched to {self._mode_text}. Reverting in {self._remaining} s unless you keep it.")

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.reject()
            return
        self._update_text()

    def _keep(self):
        self.keep = True
        self._timer.stop()
        self.accept()
