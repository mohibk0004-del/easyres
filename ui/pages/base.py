from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from theme import tokens as t
from ui.widgets import make_label


class Page(QWidget):
    """Title, subtitle and a scrolling content column."""

    title = ""
    subtitle = ""

    def __init__(self, controller, window, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.window_ = window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(t.SPACE_2XL, t.SPACE_XL, t.SPACE_2XL, t.SPACE_2XL)
        self.body_layout.setSpacing(t.SPACE_LG)

        header = QVBoxLayout()
        header.setSpacing(2)
        self.title_label = make_label(self.title, role="page-title")
        header.addWidget(self.title_label)
        if self.subtitle:
            header.addWidget(make_label(self.subtitle, role="muted", wrap=True))
        self.body_layout.addLayout(header)

        self.scroll.setWidget(body)
        outer.addWidget(self.scroll)

    def finish(self):
        self.body_layout.addStretch()

    def on_shown(self):
        """Called when the page becomes current."""
