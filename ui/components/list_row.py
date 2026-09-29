"""Grouped list rows (macOS System Settings style)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from theme import tokens as t
from ui.widgets import SectionLabel, make_label


class ListGroup(QWidget):
    """A titled, rounded group. Rows are separated by hairlines."""

    def __init__(self, title: str = "", footer: str = "", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(t.SPACE_SM)
        if title:
            heading = SectionLabel(title)
            heading.setContentsMargins(t.SPACE_XS, 0, 0, 0)
            outer.addWidget(heading)
        self.box = QWidget()
        self.box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.box.setProperty("panel", "true")
        self._rows = QVBoxLayout(self.box)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(0)
        outer.addWidget(self.box)
        self.footer = make_label(footer, role="caption", wrap=True)
        self.footer.setContentsMargins(t.SPACE_XS, 0, t.SPACE_XS, 0)
        self.footer.setVisible(bool(footer))
        outer.addWidget(self.footer)

    def add_row(self, row):
        if self._rows.count():
            line = QFrame()
            line.setObjectName("Hairline")
            line.setFixedHeight(1)
            self._rows.addWidget(line)
        self._rows.addWidget(row)
        return row

    def clear(self):
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()


class ListRow(QWidget):
    """Title (+ optional subtitle) on the left, a trailing control on the right."""

    def __init__(self, title: str, subtitle: str = "", trailing: QWidget = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_LG, t.SPACE_MD)
        layout.setSpacing(t.SPACE_MD)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = make_label(title, role="body", wrap=True)
        text.addWidget(self.title)
        self.subtitle = make_label(subtitle, role="caption", wrap=True)
        self.subtitle.setVisible(bool(subtitle))
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)
        self.trailing_layout = QHBoxLayout()
        self.trailing_layout.setSpacing(t.SPACE_SM)
        layout.addLayout(self.trailing_layout)
        if trailing is not None:
            self.add_trailing(trailing)

    def add_trailing(self, widget):
        self.trailing_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        if hasattr(widget, "setAccessibleName") and not widget.accessibleName():
            widget.setAccessibleName(self.title.text())
        return widget

    def set_subtitle(self, text, tone=None):
        from ui.widgets import set_tone
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))
        set_tone(self.subtitle, tone)
