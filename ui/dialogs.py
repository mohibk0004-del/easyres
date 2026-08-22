import sys
import os
import winreg
import urllib.request
import json
import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsDropShadowEffect, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QIcon

from theme import tokens as t
from theme import styles
from theme.assets import icon_path
from ui.widgets import ActionButton, PremiumToggle

APP_VERSION = "2.1.4"

def is_newer_version(latest, current):
    try:
        l_parts = [int(x) for x in latest.split('.')]
        c_parts = [int(x) for x in current.split('.')]
        return l_parts > c_parts
    except:
        return latest != current

class BaseStyledDialog(QDialog):
    def __init__(self, title_text, width, height, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setStyleSheet(styles.dialog_container_qss())
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(t.SHADOW_BLUR)
        shadow.setColor(QColor(t.SHADOW_COLOR))
        shadow.setOffset(0, t.SHADOW_OFFSET_Y)
        self.container.setGraphicsEffect(shadow)
        
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(t.SPACE_2XL, t.SPACE_2XL, t.SPACE_2XL, t.SPACE_2XL)
        
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_XL}px; font-weight: bold; border: none; background: transparent;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.title_lbl)
        
        main_layout.addWidget(self.container)

class SettingsDialog(BaseStyledDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__("Settings", 400, 480, parent)
        self.settings = settings
        
        self.content_layout.addSpacing(20)
        
        self._add_row("Minimize to System Tray on Close", "minimize_to_tray", self.on_tray_toggle)
        self._add_row("Ask before closing", "ask_close", self.on_ask_close_toggle)
        self._add_row("Run on Windows Startup", "run_on_startup", self.on_startup_toggle)
        self._add_row("Confirm Resolution Changes", "ask_apply_res", self.on_confirm_toggle, default=True)
        
        self.content_layout.addSpacing(10)
        
        row4 = QHBoxLayout()
        btn_restore = ActionButton("Restore Hidden Presets")
        btn_restore.clicked.connect(self.restore_hidden_presets)
        row4.addWidget(btn_restore)
        row4.addStretch()
        self.content_layout.addLayout(row4)
        
        self.content_layout.addStretch()
        
        row5 = QHBoxLayout()
        btn_update = ActionButton("Check for Updates")
        btn_update.clicked.connect(self.check_for_updates)
        row5.addWidget(btn_update)
        row5.addStretch()
        self.content_layout.addLayout(row5)
        
        self.content_layout.addSpacing(10)
        btn = ActionButton("Close")
        btn.clicked.connect(self.accept)
        self.content_layout.addWidget(btn)
        
    def _add_row(self, label_text, setting_key, slot, default=False):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {t.TEXT_PRIMARY}; font-size: {t.FONT_MD}px; font-weight: 500; border: none;")
        tgl = PremiumToggle()
        
        if setting_key == "ask_close":
            val = not self.settings.value("dont_ask_tray_close", False, type=bool) and not self.settings.value("minimize_to_tray", False, type=bool)
            tgl.setChecked(val, emit=False)
        else:
            tgl.setChecked(self.settings.value(setting_key, default, type=bool), emit=False)
            
        tgl.toggled.connect(slot)
        setattr(self, f"tgl_{setting_key}", tgl)
        
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(tgl)
        self.content_layout.addLayout(row)

    def on_tray_toggle(self):
        self.settings.setValue("minimize_to_tray", self.tgl_minimize_to_tray.isChecked())
        if self.tgl_minimize_to_tray.isChecked():
            self.settings.setValue("dont_ask_tray_close", False)
            self.tgl_ask_close.setChecked(False, emit=False)

    def on_ask_close_toggle(self):
        if self.tgl_ask_close.isChecked():
            self.settings.setValue("minimize_to_tray", False)
            self.settings.setValue("dont_ask_tray_close", False)
            self.tgl_minimize_to_tray.setChecked(False, emit=False)
        else:
            self.settings.setValue("dont_ask_tray_close", True)
            self.settings.setValue("minimize_to_tray", False)
            self.tgl_minimize_to_tray.setChecked(False, emit=False)

    def on_confirm_toggle(self):
        self.settings.setValue("ask_apply_res", self.tgl_ask_apply_res.isChecked())

    def on_startup_toggle(self):
        enabled = self.tgl_run_on_startup.isChecked()
        self.settings.setValue("run_on_startup", enabled)
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "EasyRes"
        exe_path = os.path.abspath(sys.argv[0])
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            themed_message_box(self, "Error", f"Failed to modify registry for startup: {e}", QMessageBox.Icon.Warning)
            self.tgl_run_on_startup.setChecked(not enabled, emit=False)
            
    def check_for_updates(self):
        try:
            req = urllib.request.Request("https://api.github.com/repos/mohibk0004-del/easyres/releases/latest")
            req.add_header('User-Agent', 'EasyRes-App')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "").lstrip("v")
                
                if latest_version and is_newer_version(latest_version, APP_VERSION):
                    reply = themed_message_box(
                        self, "Update Available", 
                        f"Version {latest_version} is available. You are using {APP_VERSION}.\n\nDo you want to download the update?", 
                        QMessageBox.Icon.Information,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        webbrowser.open("https://github.com/mohibk0004-del/easyres/releases/latest")
                else:
                    themed_message_box(self, "Up to Date", "You are using the latest version of EasyRes.")
        except Exception as e:
            themed_message_box(self, "Update Check Failed", "Could not check for updates.", QMessageBox.Icon.Warning)

    def restore_hidden_presets(self):
        self.settings.setValue("hidden_presets", [])
        themed_message_box(self, "Success", "Hidden presets restored.")
        if self.parent():
            self.parent().load_presets()

class TutorialDialog(BaseStyledDialog):
    def __init__(self, parent=None):
        super().__init__("Welcome to EasyRes", 460, 520, parent)
        
        self.content_layout.setSpacing(16)
        
        content = QLabel(
            f"<div style='color: {t.TEXT_SECONDARY}; font-size: {t.FONT_MD}px; line-height: 1.6;'>"
            f"<p style='margin-bottom: 14px; color: {t.TEXT_PRIMARY}; font-size: {t.FONT_LG}px;'>This app makes setting up <span style='color: {t.ACCENT_PRIMARY}; font-weight: bold;'>True Stretch</span> for Valorant easier.</p>"
            f"<p><b>1.</b> Make Valorant <span style='color: {t.TEXT_PRIMARY}; font-weight: bold;'>Windowed Fullscreen</span>.</p>"
            f"<p><b>2.</b> Disable the monitor from the <span style='color: {t.ACCENT_PRIMARY}; font-weight: bold;'>Hardware Monitors</span> section.</p>"
            f"<p><b>3.</b> Choose a predefined preset or add your own custom resolution.</p>"
            f"<p><b>4.</b> If you see black bars, change scaling mode to <b>Full Screen</b> in AMD/Nvidia settings, and use <b>Fill</b> in Valorant.</p>"
            f"<p><b>5.</b> Use <span style='color: {t.TEXT_PRIMARY}; font-weight: bold;'>'Reset to Native'</span> to restore defaults and enable your monitor.</p>"
            "</div>"
        )
        content.setStyleSheet("border: none; background: transparent;")
        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        
        btn = ActionButton("Got it!", primary=True)
        btn.clicked.connect(self.accept)
        
        self.content_layout.addWidget(content)
        self.content_layout.addStretch()
        self.content_layout.addWidget(btn)

def themed_message_box(parent, title, text, icon=QMessageBox.Icon.Information, buttons=QMessageBox.StandardButton.Ok, cb_text=None):
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(buttons)
    msg_box.setStyleSheet(styles.message_box_qss())
    
    cb = None
    if cb_text:
        cb = QCheckBox(cb_text)
        msg_box.setCheckBox(cb)
        
    reply = msg_box.exec()
    if cb:
        return reply, cb.isChecked()
    return reply
