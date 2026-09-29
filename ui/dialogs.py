from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QMessageBox,
    QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSettings, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

from theme import tokens as t
from theme.motion import duration
from ui.widgets import ActionButton, PremiumToggle, make_label
from ui.workers import run_async
import startup
import updater

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
        self.container.setObjectName("Container")
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
        self.result_button = StandardButton.Cancel if buttons & StandardButton.Cancel else (
            StandardButton.No if buttons & StandardButton.No else StandardButton.Ok
        )
        self.setAccessibleName(title)
        self.setAccessibleDescription(text)

        body = make_label(text, role="muted", wrap=True)
        body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.content_layout.addWidget(body)

        self.checkbox = None
        if cb_text:
            self.checkbox = QCheckBox(cb_text)
            self.content_layout.addWidget(self.checkbox)

        labels = {**DEFAULT_LABELS, **(labels or {})}
        warning = icon in (QMessageBox.Icon.Warning, QMessageBox.Icon.Critical)
        widgets = []
        default_button = None
        present = [b for b in BUTTON_ORDER if buttons & b]
        for standard in present:
            affirmative = standard in AFFIRMATIVE and len(present) > 1
            button = ActionButton(
                labels.get(standard, standard.name),
                primary=affirmative and not warning,
                destructive=affirmative and warning,
            )
            button.clicked.connect(lambda _checked=False, b=standard: self._finish(b))
            widgets.append(button)
            if standard in AFFIRMATIVE:
                default_button = button
        if default_button is None and widgets:
            default_button = widgets[-1]
        if default_button is not None:
            default_button.setDefault(True)
        self.add_button_row(widgets)

    def _finish(self, button):
        self.result_button = button
        self.accept()


def themed_message_box(parent, title, text, icon=QMessageBox.Icon.Information,
                       buttons=StandardButton.Ok, cb_text=None, labels=None):
    """Drop-in replacement for QMessageBox with EasyRes styling.

    Returns the chosen StandardButton, or (button, checked) with cb_text.
    """
    dialog = MessageDialog(parent, title, text, icon, buttons, cb_text, labels)
    dialog.exec()
    if dialog.checkbox is not None:
        return dialog.result_button, dialog.checkbox.isChecked()
    return dialog.result_button


class RevertDialog(BaseStyledDialog):
    """Keep-or-revert countdown after a resolution change (like Windows and
    macOS display settings). Reverts automatically if the screen went black."""

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


class SettingsDialog(BaseStyledDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__("Settings", 420, parent)
        self.settings = settings
        self._checking = False

        self.content_layout.addSpacing(t.SPACE_XS)
        self._add_row("Close button minimizes to tray", "minimize_to_tray", self.on_tray_toggle)
        self._add_row("Ask before closing", "ask_close", self.on_ask_close_toggle, default=True)
        self.tgl_run_on_startup = self._add_row(
            "Start EasyRes at login", "run_on_startup", self.on_startup_toggle,
            initial=startup.is_enabled(), enabled=startup.is_supported(),
            hint=None if startup.is_supported() else "Available in the packaged EasyRes.exe build.",
        )
        self._add_row("Keep-or-revert prompt after switching", "ask_apply_res", self.on_confirm_toggle, default=True,
                      hint="Automatically reverts in 15 seconds if you don't confirm.")

        self.content_layout.addSpacing(t.SPACE_SM)
        self.status = make_label("", role="caption", wrap=True)
        self.status.hide()

        btn_restore = ActionButton("Show Hidden Modes")
        btn_restore.clicked.connect(self.restore_hidden_presets)
        self.btn_edid = ActionButton("Restore EDID")
        self.btn_edid.setToolTip("Undo custom resolution injection and restart the graphics driver")
        self.btn_edid.clicked.connect(self.restore_edid)
        parent_window = self.parent()
        self.btn_edid.setEnabled(bool(parent_window and getattr(parent_window, "has_edid_backup", lambda: False)()))

        tools_row = QHBoxLayout()
        tools_row.setSpacing(t.SPACE_SM)
        tools_row.addWidget(btn_restore)
        tools_row.addWidget(self.btn_edid)
        tools_row.addStretch()
        self.content_layout.addLayout(tools_row)

        self.btn_update = ActionButton("Check for Updates")
        self.btn_update.clicked.connect(self.check_for_updates)
        version = make_label(f"Version {updater.CURRENT_VERSION}", role="caption")
        update_row = QHBoxLayout()
        update_row.addWidget(self.btn_update)
        update_row.addSpacing(t.SPACE_SM)
        update_row.addWidget(version)
        update_row.addStretch()
        self.content_layout.addLayout(update_row)
        self.content_layout.addWidget(self.status)

        done = ActionButton("Done", primary=True)
        done.clicked.connect(self.accept)
        self.add_button_row([done])

    def _add_row(self, label_text, setting_key, slot, default=False, initial=None, enabled=True, hint=None):
        row = QHBoxLayout()
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        lbl = make_label(label_text, role="body", wrap=True)
        text_col.addWidget(lbl)
        if hint:
            text_col.addWidget(make_label(hint, role="caption", wrap=True))
        tgl = PremiumToggle(label_text)
        value = initial if initial is not None else self.settings.value(setting_key, default, type=bool)
        tgl.setChecked(bool(value), emit=False)
        tgl.setEnabled(enabled)
        lbl.setBuddy(tgl)
        tgl.toggled.connect(slot)
        setattr(self, f"tgl_{setting_key}", tgl)

        row.addLayout(text_col, 1)
        row.addSpacing(t.SPACE_MD)
        row.addWidget(tgl, 0, Qt.AlignmentFlag.AlignTop)
        self.content_layout.addLayout(row)
        return tgl

    def _show_status(self, text, warning=False):
        self.status.setProperty("tone", "warning" if warning else "")
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.adjustSize()

    def on_tray_toggle(self, checked):
        self.settings.setValue("minimize_to_tray", checked)

    def on_ask_close_toggle(self, checked):
        self.settings.setValue("ask_close", checked)

    def on_confirm_toggle(self, checked):
        self.settings.setValue("ask_apply_res", checked)

    def on_startup_toggle(self, enabled):
        self.tgl_run_on_startup.setEnabled(False)

        def done(result):
            ok, message = result
            self.tgl_run_on_startup.setEnabled(True)
            if ok:
                self.settings.setValue("run_on_startup", enabled)
                self._show_status("EasyRes will start at login." if enabled else "")
            else:
                self.tgl_run_on_startup.setChecked(not enabled, emit=False)
                self._show_status(f"Couldn't change start at login: {message}", warning=True)

        run_async(startup.set_enabled, enabled, on_done=done,
                  on_error=lambda msg: done((False, msg)))

    def check_for_updates(self):
        if self._checking:
            return
        self._checking = True
        self.btn_update.setEnabled(False)
        self.btn_update.setText("Checking…")

        def finish():
            self._checking = False
            self.btn_update.setEnabled(True)
            self.btn_update.setText("Check for Updates")

        def done(release):
            finish()
            latest_version = release.get("tag_name", "").lstrip("v")
            if not (latest_version and updater.is_newer_version(latest_version, updater.CURRENT_VERSION)):
                self._show_status("EasyRes is up to date.")
                return
            parent = self.parent()
            if parent and hasattr(parent, "show_update_notification"):
                parent.show_update_notification(release)
            if not updater.can_self_update():
                self._show_status(f"Version {latest_version} is available. Automatic install works in the packaged EasyRes.exe build.")
                return
            reply = themed_message_box(
                self, "Update available",
                f"EasyRes {latest_version} is available (you have {updater.CURRENT_VERSION}). "
                "EasyRes will download it, verify it, and restart.",
                QMessageBox.Icon.Information,
                StandardButton.Yes | StandardButton.Cancel,
                labels={StandardButton.Yes: "Install and Restart", StandardButton.Cancel: "Later"},
            )
            if reply == StandardButton.Yes and parent and hasattr(parent, "start_update"):
                parent.start_update(release)
                self.accept()

        def failed(message):
            finish()
            self._show_status(message, warning=True)

        run_async(updater.fetch_latest_release, on_done=done, on_error=failed)

    def restore_hidden_presets(self):
        self.settings.setValue("hidden_presets", [])
        self._show_status("Hidden modes are visible again.")
        parent = self.parent()
        if parent and hasattr(parent, "load_presets"):
            parent.load_presets()

    def restore_edid(self):
        parent = self.parent()
        if parent and hasattr(parent, "restore_original_edid"):
            self.accept()
            parent.restore_original_edid()


class TutorialDialog(BaseStyledDialog):
    STEPS = (
        "Set your game to Windowed Fullscreen (Borderless).",
        "Pick a mode in the Resolution list. You'll get 15 seconds to keep it or it reverts.",
        "On laptops, true stretch may need the built-in panel turned off under Hardware Monitors.",
        "Black bars? Set GPU scaling to Full Screen in AMD/NVIDIA settings, and use Fill in-game.",
        "Restore Native (Ctrl+Shift+F12, works anywhere) brings back your normal resolution. "
        "Use Restore Native + Enable Monitors to also turn monitors back on.",
    )

    def __init__(self, parent=None):
        super().__init__("Welcome to EasyRes", 460, parent)
        intro = make_label("Switch to stretched and custom resolutions in a click, and get back to native just as fast.",
                           role="muted", wrap=True)
        self.content_layout.addWidget(intro)
        self.content_layout.addSpacing(t.SPACE_XS)
        for index, step in enumerate(self.STEPS, start=1):
            row = QHBoxLayout()
            row.setSpacing(t.SPACE_MD)
            number = make_label(str(index), role="badge", tone="accent")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setFixedWidth(28)
            row.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(make_label(step, role="body", wrap=True), 1)
            self.content_layout.addLayout(row)
        oled = make_label("OLED panels: avoid stretch and monitor-toggle workflows.",
                          role="caption", tone="warning", wrap=True)
        self.content_layout.addSpacing(t.SPACE_XS)
        self.content_layout.addWidget(oled)

        btn = ActionButton("Get Started", primary=True)
        btn.clicked.connect(self.accept)
        btn.setDefault(True)
        self.add_button_row([btn])
