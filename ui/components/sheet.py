"""In-window modal sheet (macOS style): dims the window and slides a card
down from under the header. Replaces top-level dialogs while the main
window is visible."""

from PyQt6.QtCore import QEventLoop, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget

from theme import tokens as t
from ui import motion
from ui.widgets import ActionButton, make_label

SLIDE = 12


class Sheet(QWidget):
    finished = pyqtSignal(object)

    def __init__(self, host: QWidget, title: str, text: str = "", buttons=(), cancel_value=None,
                 checkbox_text=None, body_widget=None, width=t.SHEET_MAX_W, dismissible=True):
        """buttons: sequence of (label, value, kind) with kind in
        {"primary", "destructive", "secondary"}; the last is the default."""
        super().__init__(host)
        self.setObjectName("SheetOverlay")
        self.cancel_value = cancel_value
        self.dismissible = dismissible
        self.result_value = cancel_value
        self._dim = 0.0
        self._offset = -SLIDE
        self._snapshot = None
        self._anim = None
        self._closing = False
        self._previous_focus = host.window().focusWidget() if host.window() else None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.card = QWidget(self)
        self.card.setObjectName("SheetCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setFixedWidth(width)
        self.card.setAccessibleName(title)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(t.SPACE_2XL, t.SPACE_XL, t.SPACE_2XL, t.SPACE_XL)
        layout.setSpacing(t.SPACE_MD)
        self.title_label = make_label(title, role="dialog-title", wrap=True)
        layout.addWidget(self.title_label)
        self.text_label = make_label(text, role="muted", wrap=True)
        self.text_label.setVisible(bool(text))
        layout.addWidget(self.text_label)
        if body_widget is not None:
            layout.addWidget(body_widget)

        self.checkbox = None
        if checkbox_text:
            self.checkbox = QCheckBox(checkbox_text)
            layout.addWidget(self.checkbox)

        self.buttons = []
        if buttons:
            row = QHBoxLayout()
            row.setSpacing(t.SPACE_SM)
            row.addStretch()
            for label, value, kind in buttons:
                button = ActionButton(label, primary=kind == "primary", destructive=kind == "destructive")
                button.clicked.connect(lambda _c=False, v=value: self.close_with(v))
                row.addWidget(button)
                self.buttons.append(button)
            self.buttons[-1].setDefault(True)
            layout.addSpacing(t.SPACE_XS)
            layout.addLayout(row)

    # -- lifecycle -----------------------------------------------------
    def open(self):
        host = self.parentWidget()
        self.setGeometry(host.rect())
        host.installEventFilter(self)
        self.show()
        self.raise_()
        self._place_card()
        self.card.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.card.setFocus(Qt.FocusReason.PopupFocusReason)
        self._snapshot = self.card.grab()
        self.card.hide()
        motion.stop(self._anim)
        self._anim = motion.tween(self, 0.0, 1.0, t.MOTION_SHEET_IN, self._set_progress,
                                  on_finished=self._opened)

    def _opened(self):
        self._snapshot = None
        self.card.show()
        self.card.setFocus(Qt.FocusReason.PopupFocusReason)
        self.update()

    def exec(self):
        """Block (with a nested event loop) until closed; return the value."""
        loop = QEventLoop()
        self.finished.connect(lambda _v: loop.quit())
        self.open()
        loop.exec()
        return self.result_value

    def close_with(self, value):
        if self._closing:
            return
        self._closing = True
        self.result_value = value
        self._snapshot = self.card.grab()
        self.card.hide()
        motion.stop(self._anim)
        self._anim = motion.tween(self, 1.0, 0.0, t.MOTION_SHEET_OUT, self._set_progress,
                                  on_finished=self._closed, curve=motion.ease_in())

    def dismiss(self):
        self.close_with(self.cancel_value)

    def _closed(self):
        host = self.parentWidget()
        if host:
            host.removeEventFilter(self)
        self.hide()
        if self._previous_focus is not None:
            try:
                self._previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass
        self.finished.emit(self.result_value)
        self.deleteLater()

    def set_text(self, text):
        self.text_label.setText(text)
        self.text_label.setVisible(bool(text))

    # -- geometry / animation ------------------------------------------
    def _card_pos(self):
        x = (self.width() - self.card.width()) / 2
        return QPointF(max(t.SPACE_LG, x), t.HEADER_H + t.SPACE_MD)

    def _place_card(self):
        self.card.adjustSize()
        pos = self._card_pos()
        self.card.move(int(pos.x()), int(pos.y()))

    def _set_progress(self, value):
        value = float(value)
        self._dim = value
        self._offset = -SLIDE * (1.0 - value)
        self.update()

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == event.Type.Resize:
            self.setGeometry(obj.rect())
            self._place_card()
        return False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, int(t.SHEET_DIM_ALPHA * self._dim)))
        card_rect = QRectF(self.card.geometry())
        if self._snapshot is not None:
            card_rect.translate(0, self._offset)
            p.setOpacity(self._dim)
        # Soft shadow under the card.
        for spread, alpha in ((14, 18), (8, 28), (3, 40)):
            path = QPainterPath()
            path.addRoundedRect(card_rect.adjusted(-spread, -spread + 6, spread, spread + 6),
                                t.RADIUS_XL + spread, t.RADIUS_XL + spread)
            p.fillPath(path, QColor(0, 0, 0, alpha))
        if self._snapshot is not None:
            p.drawPixmap(card_rect.topLeft(), self._snapshot)

    # -- input ---------------------------------------------------------
    def mousePressEvent(self, event):
        event.accept()  # Block clicks to the page underneath.

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.dismissible:
            self.dismiss()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.buttons:
            focused = self.focusWidget()
            target = focused if focused in self.buttons else self.buttons[-1]
            target.click()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next_):
        # Trap Tab inside the card.
        chain = [w for w in self.card.findChildren(QWidget)
                 if w.focusPolicy() & Qt.FocusPolicy.TabFocus and w.isVisibleTo(self.card) and w.isEnabled()]
        if not chain:
            return True
        current = self.focusWidget()
        index = chain.index(current) if current in chain else -1
        index = (index + (1 if next_ else -1)) % len(chain)
        chain[index].setFocus(Qt.FocusReason.TabFocusReason)
        return True
