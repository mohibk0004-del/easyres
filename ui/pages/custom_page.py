from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import edid
import resolution
from theme import styles
from theme import tokens as t
from ui.components.list_row import ListGroup, ListRow
from ui.controller import EDID_STEPS, as_int, mode_text
from ui.pages.base import Page
from ui.widgets import ActionButton, Panel, make_label, set_tone


class Step(Panel):
    def __init__(self, number, title, parent=None):
        super().__init__("true", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_LG, t.SPACE_LG, t.SPACE_LG, t.SPACE_LG)
        layout.setSpacing(t.SPACE_MD)
        head = QHBoxLayout()
        head.setSpacing(t.SPACE_SM)
        self.badge = make_label(str(number), role="badge", tone="accent")
        self.badge.setFixedWidth(26)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.badge)
        head.addWidget(make_label(title, role="strong"))
        head.addStretch()
        layout.addLayout(head)
        self.content = layout


class CustomPage(Page):
    title = "Custom Resolution"
    subtitle = ("Adds a mode your monitor doesn't list by writing an EDID override and restarting the "
                "graphics driver. The original EDID is backed up first.")

    def __init__(self, controller, window, parent=None):
        super().__init__(controller, window, parent)

        # Step 1: size
        step1 = Step(1, "Size")
        self.safe_combo = QComboBox()
        self.safe_combo.setAccessibleName("Common stretched resolution")
        for w, h in resolution.VALORANT_SAFE_RESOLUTIONS:
            self.safe_combo.addItem(f"{w} × {h}   ·   {resolution.get_aspect_ratio(w, h)}", (w, h))
        self.safe_combo.currentIndexChanged.connect(self._on_safe_changed)
        step1.content.addWidget(self.safe_combo)
        self.any_size = QCheckBox("Any size (experimental)")
        self.any_size.toggled.connect(self._on_any_size)
        step1.content.addWidget(self.any_size)
        size_row = QHBoxLayout()
        size_row.setSpacing(t.SPACE_SM)
        self.inp_w = QLineEdit()
        self.inp_w.setPlaceholderText("Width")
        self.inp_w.setAccessibleName("Width in pixels")
        self.inp_w.setValidator(QIntValidator(1, edid.MAX_DIMENSION))
        self.inp_h = QLineEdit()
        self.inp_h.setPlaceholderText("Height")
        self.inp_h.setAccessibleName("Height in pixels")
        self.inp_h.setValidator(QIntValidator(1, edid.MAX_DIMENSION))
        size_row.addWidget(self.inp_w, 1)
        size_row.addWidget(make_label("×", role="muted"))
        size_row.addWidget(self.inp_h, 1)
        step1.content.addLayout(size_row)
        self.size_note = make_label("", role="caption", wrap=True)
        step1.content.addWidget(self.size_note)
        self.body_layout.addWidget(step1)

        # Step 2: refresh + name
        step2 = Step(2, "Refresh rate and name")
        row = QHBoxLayout()
        row.setSpacing(t.SPACE_SM)
        self.hz_combo = QComboBox()
        self.hz_combo.setAccessibleName("Refresh rate")
        self.hz_combo.setFixedWidth(110)
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Name (optional)")
        self.inp_name.setAccessibleName("Name")
        self.inp_name.setMaxLength(40)
        row.addWidget(self.hz_combo)
        row.addWidget(self.inp_name, 1)
        step2.content.addLayout(row)
        self.hz_note = make_label("", role="caption", wrap=True)
        step2.content.addWidget(self.hz_note)
        self.body_layout.addWidget(step2)

        # Step 3: review
        step3 = Step(3, "Review and add")
        self.review = make_label("", role="muted", wrap=True)
        step3.content.addWidget(self.review)
        self.error = make_label("", role="caption", tone="warning", wrap=True)
        self.error.hide()
        step3.content.addWidget(self.error)
        add_row = QHBoxLayout()
        add_row.addStretch()
        self.add_btn = ActionButton("Add and Restart Driver", primary=True)
        self.add_btn.clicked.connect(self.add)
        add_row.addWidget(self.add_btn)
        step3.content.addLayout(add_row)
        self.body_layout.addWidget(step3)

        self.restore_group = ListGroup("Undo")
        self.restore_row = ListRow("Original EDID", "")
        self.restore_btn = ActionButton("Restore Original EDID")
        self.restore_btn.clicked.connect(self.restore)
        self.restore_row.add_trailing(self.restore_btn)
        self.restore_group.add_row(self.restore_row)
        self.body_layout.addWidget(self.restore_group)
        self.body_layout.addWidget(make_label("OLED panels: avoid stretch and monitor-toggle workflows.",
                                              role="caption", tone="warning", wrap=True))
        self.finish()

        for field in (self.inp_w, self.inp_h):
            field.textChanged.connect(self._on_size_edited)
        self.hz_combo.currentIndexChanged.connect(lambda _i: self._update_review())
        self.inp_name.textChanged.connect(lambda _t: self._update_review())
        self.inp_name.returnPressed.connect(self.add)
        controller.busy_changed.connect(lambda busy: self.add_btn.setEnabled(not busy))
        controller.state_changed.connect(self._sync_restore)
        self._on_any_size(False)

    def on_shown(self):
        self._sync_restore()
        self._update_hz()

    # -- inputs ---------------------------------------------------------
    def _values(self):
        return as_int(self.inp_w.text()), as_int(self.inp_h.text()), self.hz_combo.currentData(), self.inp_name.text().strip()

    def _on_safe_changed(self, _i=None):
        if self.any_size.isChecked():
            return
        data = self.safe_combo.currentData()
        if data:
            self.inp_w.setText(str(data[0]))
            self.inp_h.setText(str(data[1]))

    def _on_any_size(self, enabled):
        self.safe_combo.setEnabled(not enabled)
        self.inp_w.setEnabled(enabled)
        self.inp_h.setEnabled(enabled)
        if enabled:
            self.size_note.setText(f"Non-standard sizes are unsupported and may fail or show black bars. "
                                   f"{edid.MIN_DIMENSION}–{edid.MAX_DIMENSION} px.")
            set_tone(self.size_note, "warning")
            self.inp_w.setFocus()
        else:
            self.size_note.setText("Common 4:3 and 5:4 stretched modes.")
            set_tone(self.size_note, None)
            self._on_safe_changed()
        self._update_review()

    def _on_size_edited(self, _text=None):
        self._set_error("")
        self._update_hz()

    def _update_hz(self):
        w, h, previous, _name = self._values()
        rates, reported = self.controller.refresh_rates_for(w, h)
        self.hz_combo.blockSignals(True)
        self.hz_combo.clear()
        for rate in rates:
            self.hz_combo.addItem(f"{rate} Hz", rate)
        if not rates:
            self.hz_combo.addItem("—", None)
        if previous in rates:
            self.hz_combo.setCurrentIndex(rates.index(previous))
        self.hz_combo.blockSignals(False)
        self.hz_note.setText("Refresh rates your monitor reports for this size." if reported else
                             "Windows doesn't list this size yet; your current refresh rate is offered.")
        self._update_review()

    def _update_review(self):
        w, h, hz, name = self._values()
        if not (w and h and hz):
            self.review.setText("Choose a size and refresh rate.")
            return
        label = name or f"{w}×{h} @ {hz} Hz"
        risk = ("This is not a standard 4:3 or 5:4 stretch and may leave the screen blank until you press "
                "Restore Native. " if resolution.get_aspect_ratio(w, h) == "Experimental" else "")
        self.review.setText(f"Adds “{label}” ({mode_text(w, h, hz)}) to My Modes. {risk}"
                            "Your screen flashes black for a few seconds while the driver restarts.")

    def _set_error(self, text, fields=()):
        self.error.setText(text)
        self.error.setVisible(bool(text))
        mapping = {"w": self.inp_w, "h": self.inp_h, "name": self.inp_name}
        for key, widget in mapping.items():
            styles.set_props(widget, error=key in fields)

    # -- actions --------------------------------------------------------
    def add(self):
        c = self.controller
        if c.busy:
            return
        w, h, hz, name = self._values()
        error, fields = c.validate_custom(w, h, hz, name, self.any_size.isChecked())
        if error:
            self._set_error(error, fields)
            return
        self._set_error("")
        experimental = resolution.get_aspect_ratio(w, h) == "Experimental"
        if not self.window_.confirm(
                f"Add {mode_text(w, h, hz)}?",
                self.review.text() + " The original EDID is backed up and can be restored on this page.",
                "Add and Restart Driver", destructive=experimental):
            return

        progress = self.window_.progress_sheet("Adding custom resolution", EDID_STEPS)

        def failed(message):
            self._set_error(message)

        def done():
            self.inp_name.clear()

        c.add_custom(w, h, hz, name, on_done=done, on_error=failed)
        progress.bind(c.edid_progress)

    def restore(self):
        if self.window_.confirm(
                "Restore original EDID?",
                "Writes back the EDID saved before your first custom resolution and restarts the graphics "
                "driver. Injected modes stop working; they stay in My Modes until you remove them.",
                "Restore and Restart Driver", destructive=True):
            self.controller.restore_edid()

    def _sync_restore(self):
        has_backup = self.controller.has_edid_backup()
        self.restore_btn.setEnabled(has_backup and not self.controller.busy)
        self.restore_row.set_subtitle("A backup is saved." if has_backup else
                                      "Nothing to restore. A backup is made before the first override.")
