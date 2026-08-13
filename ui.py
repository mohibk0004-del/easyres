import sys
import os
import winreg
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect, QGridLayout,
                             QComboBox, QLineEdit, QSizePolicy, QMessageBox, QSizeGrip, QSystemTrayIcon, QMenu, QDialog, QScrollArea, QFrame, QCheckBox)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize, pyqtProperty, QSettings, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QIntValidator, QBrush, QIcon, QPixmap
import json
import threading
import urllib.request
import webbrowser

APP_VERSION = "2.1.2"

def is_newer_version(latest, current):
    try:
        l_parts = [int(x) for x in latest.split('.')]
        c_parts = [int(x) for x in current.split('.')]
        return l_parts > c_parts
    except:
        return latest != current

import resolution
import edid
import driver

class AppleToggle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = True
        self._pos = 22
        
        self.anim = QPropertyAnimation(self, b"handle_pos")
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.setDuration(400)

    @pyqtProperty(int)
    def handle_pos(self):
        return self._pos

    @handle_pos.setter
    def handle_pos(self, pos):
        self._pos = pos
        self.update()

    def setChecked(self, checked):
        self._checked = checked
        self.anim.setEndValue(22 if checked else 2)
        self.anim.start()

    def isChecked(self):
        return self._checked

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled()
            
    def toggled(self):
        pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_color = QColor("#4647C9") if self._checked else QColor("#333333")
        if self.anim.state() == QPropertyAnimation.State.Running:
            if not self._checked: 
                bg_color = QColor("#333333")
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 13, 13)
        p.fillPath(path, QBrush(bg_color))
        
        handle_rect = QRect(self._pos, 2, 22, 22)
        p.setBrush(QBrush(QColor("white")))
        p.setPen(Qt.PenStyle.NoPen)
        
        p.save()
        p.setBrush(QBrush(QColor(0,0,0, 50)))
        p.drawEllipse(handle_rect.translated(0, 1))
        p.restore()
        
        p.drawEllipse(handle_rect)

class ActionButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #15166B, stop:0.62 #3A3FBE, stop:1 #4647C9);
                border: 1px solid #3A3FBE;
                border-radius: 10px;
                color: #F9F9F9;
                font-size: 12px;
                font-weight: 700;
                padding: 9px 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4647C9, stop:0.72 #3A3FBE, stop:1 #C6C8FF);
                border: 1px solid #C6C8FF;
            }
            QPushButton:pressed {
                background-color: #15166B;
                border: 1px solid #3A3FBE;
                padding: 10px 11px 8px 13px;
            }
        """)

class PresetCard(QPushButton):
    delete_requested = pyqtSignal(str, int, int, bool)

    def __init__(self, width, height, ratio, label, is_custom=False, hz=None, parent=None):
        super().__init__(parent)
        self.res_width = width
        self.res_height = height
        self.is_custom = is_custom
        self.label_text = label
        self.hz = hz
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(132, 78)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)
        
        hz_text = f" @ {hz}Hz" if hz else ""
        res_label = QLabel(f"{width} × {height}{hz_text}")
        res_label.setStyleSheet("color: #f5f5f7; font-size: 13px; font-weight: 600; border: none; background: transparent;")
        res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        ratio_label = QLabel(ratio)
        ratio_label.setStyleSheet("color: #86868b; font-size: 11px; font-weight: 500; border: none; background: transparent;")
        ratio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        desc_label = QLabel(label)
        desc_label.setStyleSheet("color: rgba(134, 134, 139, 0.7); font-size: 10px; font-weight: 500; border: none; background: transparent;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(res_label)
        layout.addWidget(ratio_label)
        layout.addWidget(desc_label)
        
        base_color = "#111111" if not is_custom else "#15151d"
        hover_color = "#333333" if not is_custom else "#292943"
        
        self.setStyleSheet(f"""
            PresetCard {{
                background-color: {base_color};
                border: 1px solid #333333;
                border-radius: 14px;
            }}
            PresetCard:hover {{
                background-color: {hover_color};
                border: 1px solid #4647C9;
            }}
            PresetCard:pressed {{
                background-color: #15166B;
                border: 1px solid #3A3FBE;
            }}
        """)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #111111; color: white; border: 1px solid #333333; border-radius: 4px; }
            QMenu::item { padding: 5px 20px 5px 20px; }
            QMenu::item:selected { background-color: #4647C9; }
        """)
        action_text = "Delete Custom Resolution" if self.is_custom else "Hide Preset"
        del_action = menu.addAction(action_text)
        action = menu.exec(event.globalPos())
        if action == del_action:
            self.delete_requested.emit(self.label_text, self.res_width, self.res_height, self.is_custom)

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 480)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        self.container = QWidget()
        self.container.setStyleSheet("QWidget { background-color: #000000; border-radius: 16px; border: 1px solid #333333; }")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Settings")
        title.setStyleSheet("color: #f5f5f7; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        row1 = QHBoxLayout()
        lbl1 = QLabel("Minimize to System Tray on Close")
        lbl1.setStyleSheet("color: white; font-size: 13px; font-weight: 500; border: none;")
        self.tgl_tray = AppleToggle()
        self.tgl_tray.setChecked(self.settings.value("minimize_to_tray", False, type=bool))
        self.tgl_tray.toggled = self.on_tray_toggle
        row1.addWidget(lbl1)
        row1.addStretch()
        row1.addWidget(self.tgl_tray)
        layout.addLayout(row1)
        
        row1_5 = QHBoxLayout()
        lbl1_5 = QLabel("Ask before closing")
        lbl1_5.setStyleSheet("color: white; font-size: 13px; font-weight: 500; border: none;")
        self.tgl_ask_close = AppleToggle()
        ask = not self.settings.value("dont_ask_tray_close", False, type=bool) and not self.settings.value("minimize_to_tray", False, type=bool)
        self.tgl_ask_close.setChecked(ask)
        self.tgl_ask_close.toggled = self.on_ask_close_toggle
        row1_5.addWidget(lbl1_5)
        row1_5.addStretch()
        row1_5.addWidget(self.tgl_ask_close)
        layout.addLayout(row1_5)
        
        row2 = QHBoxLayout()
        lbl2 = QLabel("Run on Windows Startup")
        lbl2.setStyleSheet("color: white; font-size: 13px; font-weight: 500; border: none;")
        self.tgl_startup = AppleToggle()
        self.tgl_startup.setChecked(self.settings.value("run_on_startup", False, type=bool))
        self.tgl_startup.toggled = self.on_startup_toggle
        row2.addWidget(lbl2)
        row2.addStretch()
        row2.addWidget(self.tgl_startup)
        layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        lbl3 = QLabel("Confirm Resolution Changes")
        lbl3.setStyleSheet("color: white; font-size: 13px; font-weight: 500; border: none;")
        self.tgl_confirm = AppleToggle()
        self.tgl_confirm.setChecked(self.settings.value("ask_apply_res", True, type=bool))
        self.tgl_confirm.toggled = self.on_confirm_toggle
        row3.addWidget(lbl3)
        row3.addStretch()
        row3.addWidget(self.tgl_confirm)
        layout.addLayout(row3)
        
        layout.addSpacing(10)
        
        row4 = QHBoxLayout()
        btn_restore = ActionButton("Restore Hidden Presets")
        btn_restore.clicked.connect(self.restore_hidden_presets)
        row4.addWidget(btn_restore)
        row4.addStretch()
        layout.addLayout(row4)
        
        layout.addStretch()
        
        row5 = QHBoxLayout()
        btn_update = ActionButton("Check for Updates")
        btn_update.clicked.connect(self.check_for_updates)
        row5.addWidget(btn_update)
        row5.addStretch()
        layout.addLayout(row5)
        
        layout.addSpacing(10)
        btn = ActionButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        
        main_layout.addWidget(self.container)

    def on_tray_toggle(self):
        self.settings.setValue("minimize_to_tray", self.tgl_tray.isChecked())
        if self.tgl_tray.isChecked():
            self.settings.setValue("dont_ask_tray_close", False)
            self.tgl_ask_close.setChecked(False)

    def on_ask_close_toggle(self):
        if self.tgl_ask_close.isChecked():
            self.settings.setValue("minimize_to_tray", False)
            self.settings.setValue("dont_ask_tray_close", False)
            self.tgl_tray.setChecked(False)
        else:
            self.settings.setValue("dont_ask_tray_close", True)
            self.settings.setValue("minimize_to_tray", False)
            self.tgl_tray.setChecked(False)

    def check_for_updates(self):
        try:
            req = urllib.request.Request("https://api.github.com/repos/mohibk0004-del/easyres/releases/latest")
            req.add_header('User-Agent', 'EasyRes-App')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "").lstrip("v")
                
                if latest_version and is_newer_version(latest_version, APP_VERSION):
                    reply = QMessageBox.question(self, "Update Available", f"Version {latest_version} is available. You are using {APP_VERSION}.\n\nDo you want to download the update?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        webbrowser.open("https://github.com/mohibk0004-del/easyres/releases/latest")
                else:
                    QMessageBox.information(self, "Up to Date", "You are using the latest version of EasyRes.")
        except Exception as e:
            QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates.")

    def restore_hidden_presets(self):
        self.settings.setValue("hidden_presets", [])
        QMessageBox.information(self, "Success", "Hidden presets restored.")
        if self.parent():
            self.parent().load_presets()

    def on_confirm_toggle(self):
        self.settings.setValue("ask_apply_res", self.tgl_confirm.isChecked())

    def on_startup_toggle(self):
        enabled = self.tgl_startup.isChecked()
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
            QMessageBox.warning(self, "Error", f"Failed to modify registry for startup: {e}")
            self.tgl_startup.setChecked(not enabled)

class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 520)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border-radius: 20px;
                border: 1px solid #333333;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("Welcome to EasyRes")
        title.setStyleSheet("color: #f5f5f7; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        content = QLabel(
            "<div style='color: #a1a1a6; font-size: 14px; line-height: 1.6;'>"
            "<p style='margin-bottom: 14px; color: #f5f5f7; font-size: 15px;'>This app makes setting up <span style='color: #4647C9; font-weight: bold;'>True Stretch</span> for Valorant easier.</p>"
            "<p><b>1.</b> Make Valorant <span style='color: #f5f5f7; font-weight: bold;'>Windowed Fullscreen</span>.</p>"
            "<p><b>2.</b> Disable the monitor from the <span style='color: #4647C9; font-weight: bold;'>Hardware Monitors</span> section.</p>"
            "<p><b>3.</b> Choose a predefined preset or add your own custom resolution.</p>"
            "<p><b>4.</b> If you see black bars, change scaling mode to <b>Full Screen</b> in AMD/Nvidia settings, and use <b>Fill</b> in Valorant.</p>"
            "<p><b>5.</b> Use <span style='color: #f5f5f7; font-weight: bold;'>'Reset to Native'</span> to restore defaults and enable your monitor.</p>"
            "</div>"
        )
        content.setStyleSheet("border: none; background: transparent;")
        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        
        btn = ActionButton("Got it!")
        btn.clicked.connect(self.accept)
        
        layout.addWidget(title)
        layout.addWidget(content)
        layout.addStretch()
        layout.addWidget(btn)
        
        main_layout.addWidget(self.container)

class MainWindow(QMainWindow):
    update_available = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(720, 850)
        self.setMinimumSize(400, 400)
        self.offset = None
        self.displays = resolution.get_displays()
        for d in self.displays:
            d['device_id'] = d.get('device_id') # Ensure it exists
        self.current_display = self.displays[0] if self.displays else None
        self._preset_cache = {}
        self._preset_retry_pending = set()
        
        self.settings = QSettings("EasyRes", "App")
        
        self.init_ui()
        self.refresh_display()
        self.load_presets()
        
        QTimer.singleShot(500, self.check_first_run)
        self.update_available.connect(self.show_update_notification)
        threading.Thread(target=self.check_for_updates_background, daemon=True).start()
        
        self.setWindowOpacity(0.0)
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(500)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.opacity_anim.start()

    def check_first_run(self):
        if not self.settings.value("tutorial_shown", False, type=bool):
            self.show_tutorial()
            self.settings.setValue("tutorial_shown", True)

    def show_tutorial(self):
        dlg = TutorialDialog(self)
        dlg.exec()
        
    def show_settings(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.exec()

    def check_for_updates_background(self):
        try:
            req = urllib.request.Request("https://api.github.com/repos/mohibk0004-del/easyres/releases/latest")
            req.add_header('User-Agent', 'EasyRes-App')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "").lstrip("v")
                if latest_version and is_newer_version(latest_version, APP_VERSION):
                    self.update_available.emit(latest_version)
        except:
            pass

    def show_update_notification(self, version):
        self.update_btn = QPushButton("! Update Available")
        self.update_btn.setFixedHeight(20)
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet("QPushButton { background-color: #ed4245; color: white; border-radius: 10px; font-weight: bold; font-size: 11px; padding-left: 8px; padding-right: 8px;} QPushButton:hover { background-color: #f05355; }")
        self.update_btn.clicked.connect(lambda: webbrowser.open("https://github.com/mohibk0004-del/easyres/releases/latest"))
        self.title_layout.insertWidget(self.title_layout.indexOf(self.settings_btn), self.update_btn)


    def closeEvent(self, event):
        if self.settings.value("minimize_to_tray", False, type=bool):
            event.ignore()
            self.hide()
        elif self.settings.value("dont_ask_tray_close", False, type=bool):
            self.tray_icon.hide()
            QApplication.instance().quit()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("EasyRes")
            msg_box.setText("Do you want to minimize to the system tray instead of closing?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            msg_box.setStyleSheet("QMessageBox { background-color: #000000; color: white; } QLabel { color: white; } QPushButton { background-color: #111111; color: white; border: 1px solid #333333; padding: 5px 15px; border-radius: 6px; } QPushButton:hover { background-color: #333333; } QCheckBox { color: white; }")
            
            cb = QCheckBox("Don't ask again")
            msg_box.setCheckBox(cb)
            
            reply = msg_box.exec()
            if reply == QMessageBox.StandardButton.Yes:
                if cb.isChecked():
                    self.settings.setValue("minimize_to_tray", True)
                event.ignore()
                self.hide()
            elif reply == QMessageBox.StandardButton.No:
                if cb.isChecked():
                    self.settings.setValue("dont_ask_tray_close", True)
                self.tray_icon.hide()
                QApplication.instance().quit()
            else:
                event.ignore()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setStyleSheet("""
            QWidget#Container {
                background-color: #000000;
                border-radius: 20px;
                border: 1px solid #333333;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setFixedHeight(42)
        title_bar.setStyleSheet("background-color: #000000; border-top-left-radius: 20px; border-top-right-radius: 20px; border-bottom: 1px solid #333333;")
        self.title_layout = QHBoxLayout(title_bar)
        self.title_layout.setContentsMargins(16, 0, 16, 0)
        
        logo = QLabel()
        logo.setFixedSize(18, 18)
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "icon.png")
        pixmap = QPixmap(icon_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel("EasyRes")
        title_label.setStyleSheet("color: #F9F9F9; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet("QPushButton { color: #A7A7A7; background: transparent; border: none; font-size: 16px; font-weight: bold;} QPushButton:hover { color: #4647C9; }")
        self.settings_btn.clicked.connect(self.show_settings)
        
        help_btn = QPushButton("?")
        help_btn.setFixedSize(28, 28)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet("QPushButton { color: #A7A7A7; background: transparent; border: none; font-size: 14px; font-weight: bold;} QPushButton:hover { color: #4647C9; }")
        help_btn.clicked.connect(self.show_tutorial)
        
        min_btn = QPushButton("—")
        min_btn.setFixedSize(28, 28)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet("QPushButton { color: #A7A7A7; background: transparent; border: none; font-size: 12px; font-weight: bold;} QPushButton:hover { color: #4647C9; }")
        min_btn.clicked.connect(self.showMinimized)
        
        max_btn = QPushButton("⬜")
        max_btn.setFixedSize(28, 28)
        max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        max_btn.setStyleSheet("QPushButton { color: #A7A7A7; background: transparent; border: none; font-size: 14px;} QPushButton:hover { color: #4647C9; }")
        max_btn.clicked.connect(self.toggle_maximize)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { color: #A7A7A7; background: transparent; border: none; font-size: 14px; } QPushButton:hover { color: #4647C9; }")
        close_btn.clicked.connect(self.close)
        
        self.title_layout.addWidget(logo)
        self.title_layout.addSpacing(10)
        self.title_layout.addWidget(title_label)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.settings_btn)
        self.title_layout.addWidget(help_btn)
        self.title_layout.addWidget(min_btn)
        self.title_layout.addWidget(max_btn)
        self.title_layout.addWidget(close_btn)
        
        title_bar.mousePressEvent = self.title_press
        title_bar.mouseMoveEvent = self.title_move
        title_bar.mouseDoubleClickEvent = self.title_double_click
        
        container_layout.addWidget(title_bar)
        
        # Body
        body_scroll = QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        body_scroll.viewport().setStyleSheet("background: transparent;")
        
        body_widget = QWidget()
        body_widget.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(15)
        
        # Monitor Section
        mon_row = QHBoxLayout()
        mon_lbl = QLabel("DISPLAY")
        mon_lbl.setStyleSheet("color: #a7a8ae; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        self.mon_combo = QComboBox()
        self.mon_combo.setStyleSheet("""
            QComboBox { background-color: #111111; border: 1px solid #333333; border-radius: 9px; color: #F9F9F9; padding: 7px 10px; }
            QComboBox:hover, QComboBox:focus { border-color: #4647C9; }
            QComboBox::drop-down { border: none; width: 24px; }
        """)
        for d in self.displays:
            clean_name = d['string'] if d['string'] else d['name']
            self.mon_combo.addItem(f"{clean_name} {'(Primary)' if d['primary'] else ''}", d['name'])
        self.mon_combo.currentIndexChanged.connect(self.on_monitor_changed)
        mon_row.addWidget(mon_lbl)
        mon_row.addSpacing(10)
        mon_row.addWidget(self.mon_combo, 1)
        body_layout.addLayout(mon_row)
        
        # Current Res
        curr_box = QWidget()
        curr_box.setStyleSheet("background-color: #000000; border: none;")
        curr_layout = QVBoxLayout(curr_box)
        curr_layout.setContentsMargins(20, 20, 20, 20)
        lbl1 = QLabel("CURRENT RESOLUTION")
        lbl1.setStyleSheet("color: #A7A7A7; background: transparent; border: none; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.curr_res = QLabel("1920 × 1080")
        self.curr_res.setStyleSheet("color: #F9F9F9; background: transparent; border: none; font-size: 34px; font-weight: 700; letter-spacing: -1px;")
        self.curr_res.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.curr_hz = QLabel("144 Hz")
        self.curr_hz.setStyleSheet("color: #C6C8FF; background: transparent; border: none; font-size: 14px; font-weight: 700;")
        self.curr_hz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        curr_layout.addWidget(lbl1)
        curr_layout.addWidget(self.curr_res)
        curr_layout.addWidget(self.curr_hz)
        body_layout.addWidget(curr_box)
        
        # Add Custom Res form
        custom_res_header_layout = QHBoxLayout()
        lbl_custom_res = QLabel("ADD RESOLUTION")
        lbl_custom_res.setStyleSheet("color: #f5f5f7; font-size: 13px; font-weight: 700; margin-top: 12px;")
        self.lbl_experimental = QLabel("SAFE CATALOG")
        self.lbl_experimental.setStyleSheet("color: #C6C8FF; font-size: 10px; font-weight: 700; background-color: rgba(70, 71, 201, 0.16); border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
        custom_res_header_layout.addWidget(lbl_custom_res)
        custom_res_header_layout.addWidget(self.lbl_experimental)
        custom_res_header_layout.addStretch()
        body_layout.addLayout(custom_res_header_layout)

        add_box = QWidget()
        add_box.setStyleSheet("background-color: #0b0b0b; border-radius: 16px; border: 1px solid #333333; margin-top: 4px;")
        add_layout = QVBoxLayout(add_box)
        add_layout.setContentsMargins(16, 16, 16, 16)
        add_layout.setSpacing(12)

        safe_row = QHBoxLayout()
        safe_lbl = QLabel("TESTED 1080P MODE")
        safe_lbl.setStyleSheet("color: #a7a8ae; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        self.safe_res_combo = QComboBox()
        self.safe_res_combo.setStyleSheet("""
            QComboBox { background-color: #111111; border: 1px solid #333333; border-radius: 9px; color: #F9F9F9; padding: 8px 10px; font-size: 12px; }
            QComboBox:hover, QComboBox:focus { border-color: #4647C9; }
            QComboBox::drop-down { border: none; width: 24px; }
        """)
        for width, height in resolution.VALORANT_SAFE_RESOLUTIONS:
            ratio = resolution.get_aspect_ratio(width, height)
            self.safe_res_combo.addItem(f"{width} × {height}  ·  {ratio}", (width, height))
        self.safe_res_combo.currentIndexChanged.connect(self.on_safe_resolution_changed)
        safe_row.addWidget(safe_lbl)
        safe_row.addWidget(self.safe_res_combo, 1)
        add_layout.addLayout(safe_row)
        
        row1 = QHBoxLayout()
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Custom Name")
        
        self.inp_rw = QLineEdit()
        self.inp_rw.setPlaceholderText("Width")
        self.inp_rw.setValidator(QIntValidator(100, 10000))
        self.inp_rw.setFixedWidth(60)
        
        self.inp_rh = QLineEdit()
        self.inp_rh.setPlaceholderText("Height")
        self.inp_rh.setValidator(QIntValidator(100, 10000))
        self.inp_rh.setFixedWidth(60)
        
        self.inp_hz = QComboBox()
        self.inp_hz.setToolTip("Refresh rates exposed by this monitor for the selected resolution")
        self.inp_hz.setFixedWidth(78)
        self.inp_hz.addItem("Select Hz", None)
        
        btn_add = ActionButton("Add")
        btn_add.setFixedWidth(60)
        btn_add.clicked.connect(self.add_custom_resolution)
        
        for inp in (self.inp_name, self.inp_rw, self.inp_rh):
            inp.setStyleSheet("""
                QLineEdit { background-color: #111111; border: 1px solid #333333; border-radius: 8px; color: #F9F9F9; padding: 6px; font-size: 12px; }
                QLineEdit:focus { border: 1px solid #4647C9; }
            """)
        self.inp_hz.setStyleSheet("""
            QComboBox { background-color: #111111; border: 1px solid #333333; border-radius: 8px; color: #F9F9F9; padding: 6px; font-size: 12px; }
            QComboBox:focus { border: 1px solid #4647C9; }
            QComboBox::drop-down { border: none; }
        """)
        self.inp_rw.textChanged.connect(self.update_custom_hz_options)
        self.inp_rh.textChanged.connect(self.update_custom_hz_options)
            
        row1.addWidget(self.inp_name)
        row1.addWidget(self.inp_rw)
        row1.addWidget(QLabel("×"))
        row1.addWidget(self.inp_rh)
        row1.addWidget(self.inp_hz)
        row1.addWidget(btn_add)
        add_layout.addLayout(row1)

        self.experimental_toggle = QCheckBox("Enable experimental resolution")
        self.experimental_toggle.setStyleSheet("""
            QCheckBox { color: #D9C3AB; font-size: 12px; font-weight: 600; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #664646; border-radius: 5px; background: #111111; }
            QCheckBox::indicator:checked { background: #E85002; border-color: #F16001; }
        """)
        self.experimental_toggle.toggled.connect(self.set_experimental_mode)
        add_layout.addWidget(self.experimental_toggle)
        
        row2 = QHBoxLayout()
        lbl_pc = QLabel("Or add existing:")
        lbl_pc.setStyleSheet("color: #86868b; font-size: 12px;")
        
        self.pc_res_combo = QComboBox()
        self.pc_res_combo.setStyleSheet("""
            QComboBox { background-color: #111111; border: 1px solid #333333; border-radius: 8px; color: white; padding: 4px 8px; font-size: 12px; }
            QComboBox::drop-down { border: none; }
        """)
        
        btn_add_pc = ActionButton("Add")
        btn_add_pc.setFixedWidth(60)
        btn_add_pc.clicked.connect(self.add_pc_resolution)
        
        row2.addWidget(lbl_pc)
        row2.addWidget(self.pc_res_combo, 1)
        row2.addWidget(btn_add_pc)
        add_layout.addLayout(row2)

        self.custom_safety_note = QLabel("Uses a tested 4:3 or 5:4 mode. Refresh rates come directly from your monitor's available modes.")
        self.custom_safety_note.setWordWrap(True)
        self.custom_safety_note.setStyleSheet("color: #a7a8ae; font-size: 11px; line-height: 1.35; padding-top: 2px;")
        add_layout.addWidget(self.custom_safety_note)
        self.set_experimental_mode(False)
        self.on_safe_resolution_changed()
        
        body_layout.addWidget(add_box)

        # Presets Label
        lbl2 = QLabel("PRESETS & CUSTOM RESOLUTIONS")
        lbl2.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold; margin-top: 10px;")
        body_layout.addWidget(lbl2)
        
        # Presets Grid Container
        self.presets_grid_widget = QWidget()
        self.presets_grid_widget.setStyleSheet("background: transparent;")
        self.presets_grid = QGridLayout(self.presets_grid_widget)
        self.presets_grid.setContentsMargins(0, 0, 0, 0)
        self.presets_grid.setSpacing(8)
        body_layout.addWidget(self.presets_grid_widget)
        
        # Hardware Monitors
        lbl3 = QLabel("HARDWARE MONITORS")
        lbl3.setStyleSheet("color: #86868b; font-size: 11px; font-weight: bold; margin-top: 10px;")
        body_layout.addWidget(lbl3)
        
        self.hw_toggles = []
        hw_monitors = resolution.get_hardware_monitors()
        if not hw_monitors:
            no_hw = QLabel("No hardware monitors detected.")
            no_hw.setStyleSheet("color: #86868b; font-size: 12px;")
            body_layout.addWidget(no_hw)
        else:
            hw_box = QWidget()
            hw_box.setStyleSheet("background-color: #111111; border-radius: 12px; border: 1px solid #333333;")
            hw_layout = QVBoxLayout(hw_box)
            hw_layout.setContentsMargins(15, 10, 15, 10)
            for hw in hw_monitors:
                row_layout = QHBoxLayout()
                lbl = QLabel(hw.get("Device Description", "Unknown Monitor"))
                lbl.setStyleSheet("color: white; font-size: 13px; font-weight: bold; border: none;")
                toggle = AppleToggle()
                toggle.setChecked(hw.get("Status", "").lower() != "disabled")
                def make_toggle_handler(instance_id, toggle_widget):
                    def handler():
                        en = toggle_widget.isChecked()
                        success = resolution.set_hardware_monitor_state(instance_id, en)
                        if not success:
                            QMessageBox.warning(self, "Error", "Failed to change hardware state. Run as Admin?")
                            toggle_widget.setChecked(not en)
                    return handler
                toggle.toggled = make_toggle_handler(hw.get("Instance ID", ""), toggle)
                row_layout.addWidget(lbl)
                row_layout.addStretch()
                row_layout.addWidget(toggle)
                hw_layout.addLayout(row_layout)
                self.hw_toggles.append((hw.get("Instance ID", ""), toggle))
            body_layout.addWidget(hw_box)
            
        body_layout.addStretch()
        
        reset_layout = QHBoxLayout()
        reset_btn = ActionButton("Restore Native")
        reset_btn.setToolTip("Restore the saved native resolution without changing monitor power state")
        reset_btn.clicked.connect(lambda: self.reset_res(enable_monitors=False))
        reset_mon_btn = ActionButton("Restore + Enable Monitors")
        reset_mon_btn.setToolTip("Restore the saved native resolution and enable connected monitors")
        reset_mon_btn.clicked.connect(lambda: self.reset_res(enable_monitors=True))
        reset_layout.addWidget(reset_btn)
        reset_layout.addWidget(reset_mon_btn)
        body_layout.addLayout(reset_layout)
        
        body_scroll.setWidget(body_widget)
        container_layout.addWidget(body_scroll)
        
        main_layout.addWidget(self.container)
        
        self.grip = QSizeGrip(self)
        self.grip.resize(20, 20)
        
        self.tray_icon = QSystemTrayIcon(self)
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "icon.png")
        self.tray_icon.setIcon(QIcon(icon_path))
        
        self.tray_menu = QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)
        
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.offset = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def title_double_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if self.isMaximized():
                self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
                self.container.setStyleSheet("QWidget#Container { background-color: #000000; border-radius: 0px; border: none; }")
            else:
                self.centralWidget().layout().setContentsMargins(20, 20, 20, 20)
                self.container.setStyleSheet("QWidget#Container { background-color: #000000; border-radius: 20px; border: 1px solid #333333; }")

    def title_move(self, event):
        if self.offset is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.offset)
            event.accept()

    def load_presets(self):
        dev_name = self.get_dev_name()
        presets_data = resolution.get_supported_resolutions(dev_name)
        # A graphics-driver restart can briefly make EnumDisplaySettings return
        # no modes. Keep the last good list visible and retry the scan instead
        # of replacing the grid with an empty state.
        if presets_data:
            self._preset_cache[dev_name] = presets_data
        elif dev_name in self._preset_cache:
            presets_data = self._preset_cache[dev_name]
            if dev_name not in self._preset_retry_pending:
                self._preset_retry_pending.add(dev_name)
                QTimer.singleShot(750, lambda: self._retry_preset_load(dev_name))
        elif dev_name not in self._preset_retry_pending:
            self._preset_retry_pending.add(dev_name)
            QTimer.singleShot(750, lambda: self._retry_preset_load(dev_name))

        # Never destroy a working grid because Windows temporarily returned no
        # modes while a display driver was restarting.
        if not presets_data:
            return

        while self.presets_grid.count():
            item = self.presets_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        hidden_presets = self.settings.value("hidden_presets", [])
        if isinstance(hidden_presets, str):
            hidden_presets = []
            
        # Load custom ones
        customs = self.settings.value("custom_resolutions", [])
        if not isinstance(customs, list):
            customs = []
        
        final_presets = []
        for w, h, ratio, label, is_custom in presets_data:
            key = f"{w}x{h}"
            if key not in hidden_presets:
                final_presets.append((w, h, ratio, label, is_custom, None))
                
        for c in customs:
            if isinstance(c, dict) and all(key in c for key in ("w", "h", "name")):
                final_presets.append((c['w'], c['h'], "Custom", c['name'], True, c.get('hz')))
            
        row, col = 0, 0
        for w, h, ratio, label, is_custom, hz in final_presets:
            btn = PresetCard(w, h, ratio, label, is_custom, hz)
            btn.clicked.connect(lambda checked, width=w, height=h, freq=hz: self.change_res(width, height, freq))
            btn.delete_requested.connect(self.delete_custom_resolution)
            self.presets_grid.addWidget(btn, row, col)
            col += 1
            if col > 3: # 4 columns
                col = 0
                row += 1
                
        if presets_data and dev_name in self._preset_retry_pending:
            self._preset_retry_pending.discard(dev_name)
        if hasattr(self, 'update_tray_menu'):
            self.update_tray_menu(presets_data)

    def _retry_preset_load(self, dev_name):
        self._preset_retry_pending.discard(dev_name)
        if dev_name == self.get_dev_name():
            self.load_presets()

    def on_safe_resolution_changed(self):
        if not hasattr(self, "safe_res_combo") or self.experimental_toggle.isChecked():
            return
        width, height = self.safe_res_combo.currentData()
        self.inp_rw.setText(str(width))
        self.inp_rh.setText(str(height))
        if not self.inp_name.text().strip() or self.inp_name.text().endswith("(Custom)"):
            self.inp_name.setText(f"{width}x{height} (Custom)")
        self.update_custom_hz_options()

    def set_experimental_mode(self, enabled):
        self.safe_res_combo.setEnabled(not enabled)
        self.inp_rw.setEnabled(enabled)
        self.inp_rh.setEnabled(enabled)
        if enabled:
            self.lbl_experimental.setText("EXPERIMENTAL")
            self.lbl_experimental.setStyleSheet("color: #D9C3AB; font-size: 10px; font-weight: 700; background-color: rgba(193, 8, 1, 0.28); border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
            self.custom_safety_note.setText("Highly unsupported and strongly discouraged. Use only if you understand EDID timing risks. Values above 1080p are blocked.")
        else:
            self.lbl_experimental.setText("SAFE CATALOG")
            self.lbl_experimental.setStyleSheet("color: #D9C3AB; font-size: 10px; font-weight: 700; background-color: rgba(232, 80, 2, 0.16); border-radius: 7px; padding: 3px 7px; margin-top: 12px;")
            self.custom_safety_note.setText("Uses a tested 4:3 or 5:4 mode. Refresh rates come directly from your monitor's available modes.")
            self.on_safe_resolution_changed()

    def update_custom_hz_options(self):
        if not hasattr(self, "inp_hz"):
            return
        try:
            width = int(self.inp_rw.text())
            height = int(self.inp_rh.text())
        except ValueError:
            self.inp_hz.clear()
            self.inp_hz.addItem("Select Hz", None)
            return
        previous = self.inp_hz.currentData()
        self.inp_hz.blockSignals(True)
        self.inp_hz.clear()
        rates = resolution.get_monitor_refresh_rates(width, height, self.get_dev_name())
        if not rates:
            current = resolution.get_current_resolution(self.get_dev_name())
            if current and current.get("hz"):
                rates = [current["hz"]]
                self.inp_hz.setToolTip("This resolution is not currently exposed by Windows; current monitor Hz shown as a fallback.")
        else:
            self.inp_hz.setToolTip("Refresh rates exposed by this monitor for the selected resolution")
        self.inp_hz.addItem("Select Hz", None)
        for rate in rates:
            self.inp_hz.addItem(f"{rate} Hz", rate)
        if previous in rates:
            self.inp_hz.setCurrentIndex(rates.index(previous) + 1)
        elif rates:
            self.inp_hz.setCurrentIndex(1)
        self.inp_hz.blockSignals(False)

    def add_custom_resolution(self):
        name = self.inp_name.text().strip()
        w = self.inp_rw.text().strip()
        h = self.inp_rh.text().strip()
        hz = self.inp_hz.currentData()
        
        if not name or not w or not h:
            QMessageBox.warning(self, "Error", "Please fill all fields.")
            return

        try:
            w_int, h_int = int(w), int(h)
        except ValueError:
            QMessageBox.warning(self, "Invalid resolution", "Width and height must be numbers.")
            return

        if w_int < 100 or h_int < 100 or w_int > 1920 or h_int > 1080:
            QMessageBox.warning(self, "Unsupported size", "For 1080p monitors, custom modes must stay between 100×100 and 1920×1080.")
            return
        if hz is None:
            QMessageBox.warning(self, "Choose refresh rate", "Select a monitor refresh rate before adding this resolution.")
            return

        aspect = resolution.get_aspect_ratio(w_int, h_int)
        safe_catalog = (w_int, h_int) in resolution.VALORANT_SAFE_RESOLUTIONS
        if not self.experimental_toggle.isChecked() and not safe_catalog:
            QMessageBox.warning(self, "Safe catalog only", "Choose a listed 4:3 or 5:4 mode, or explicitly enable Experimental resolution.")
            return
        if aspect in ("4:3", "5:4") and not safe_catalog:
            QMessageBox.warning(self, "Unsupported 4:3 / 5:4 mode", "Choose one of EasyRes's tested 1080p catalog resolutions.")
            return

        resolutions = self.settings.value("custom_resolutions", [])
        if not isinstance(resolutions, list):
            resolutions = []
        for r in resolutions:
            if r['name'] == name:
                QMessageBox.warning(self, "Error", "A custom resolution with this name already exists.")
                return
                
        warning = (f"{w_int}×{h_int} is outside the tested 4:3 / 5:4 VALORANT catalog.\n\n"
                   "This aspect ratio is highly unsupported, highly discouraged, and experimental. "
                   "It may fail in VALORANT, create black bars, or leave the display unusable until reset.\n\n"
                   "Continue anyway?") if aspect == "Experimental" else (
                   f"Adding {w_int}×{h_int} requires injecting it into your monitor's EDID configuration and restarting your graphics driver.\n\n"
                   "Your screen may flash black, and unsupported timings may fail.\n\nProceed to add and inject?")
        reply = QMessageBox.warning(self, "Experimental resolution warning" if aspect == "Experimental" else "Safety Warning: Inject Resolution",
                                    warning,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                    
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # Do injection
        dev_id = None
        for d in self.displays:
            if d['name'] == self.get_dev_name():
                dev_id = d.get('device_id')
                break
        
        active_ids = edid.get_active_monitor_device_ids()
        if not active_ids:
            QMessageBox.warning(self, "Error", "Could not detect active monitor instances.")
            return
            
        target_id = None
        hw_id = dev_id.split('\\')[1] if dev_id and '\\' in dev_id else None
        if hw_id:
            for aid in active_ids:
                if f"DISPLAY\\{hw_id}" in aid:
                    target_id = aid
                    break
                    
        if not target_id:
            target_id = active_ids[0]
            
        curr_edid = edid.get_edid(target_id)
        if not curr_edid:
            QMessageBox.warning(self, "Error", f"Failed to read EDID from the registry for target: {target_id}.")
            return
            
        driver_restarted = False
        # Check if already injected
        if not edid.is_resolution_injected(curr_edid, w_int, h_int, hz):
            new_edid = edid.inject_resolution(curr_edid, w_int, h_int, hz)
            if not new_edid:
                QMessageBox.warning(self, "Error", "Failed to generate new EDID.")
                return
                
            if edid.set_edid(target_id, new_edid):
                driver.restart_graphics_driver()
                driver_restarted = True
            else:
                QMessageBox.warning(self, "Error", "Failed to write EDID override. Are you running as Admin?")
                return
                
        # Save to settings
        resolutions.append({'name': name, 'w': w_int, 'h': h_int, 'hz': hz})
        self.settings.setValue("custom_resolutions", resolutions)
        
        self.inp_name.clear()
        self.inp_rw.clear()
        self.inp_rh.clear()
        self.inp_hz.clear()
        self.inp_hz.addItem("Select Hz", None)
        self.on_safe_resolution_changed()
        
        if driver_restarted:
            QTimer.singleShot(4000, self.load_presets)
        else:
            self.load_presets()

    def delete_custom_resolution(self, name, w, h, is_custom):
        if is_custom:
            reply = QMessageBox.question(self, "Delete Custom Resolution", 
                                         f"Are you sure you want to delete '{name}'?\nNote: This will remove it from the app but not un-inject it from the registry.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                resolutions = self.settings.value("custom_resolutions", [])
                resolutions = [r for r in resolutions if r['name'] != name]
                self.settings.setValue("custom_resolutions", resolutions)
                self.load_presets()
        else:
            hidden = self.settings.value("hidden_presets", [])
            if isinstance(hidden, str):
                hidden = []
            hidden.append(f"{w}x{h}")
            self.settings.setValue("hidden_presets", hidden)
            self.load_presets()

    def change_res(self, w, h, hz=None):
        ask_confirm = self.settings.value("ask_apply_res", True, type=bool)
        if ask_confirm:
            cb = QCheckBox("Don't ask me again")
            msg = QMessageBox(self)
            msg.setWindowTitle("Apply Resolution")
            msg.setText(f"Are you sure you want to apply {w}x{h}?\n\nIf your monitor does not support this resolution, the screen may go black for 15 seconds before reverting (or you might need to use the system tray to reset it).\n\nProceed?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            msg.setCheckBox(cb)
            
            reply = msg.exec()
            
            if cb.isChecked():
                self.settings.setValue("ask_apply_res", False)
                
            if reply != QMessageBox.StandardButton.Yes:
                return
            
        if resolution.set_resolution(w, h, hz, self.get_dev_name()):
            self.refresh_display()
        else:
            QMessageBox.warning(self, "Error", f"Failed to set custom resolution {w}x{h}. The graphics driver might not support it.")

    def reset_res(self, enable_monitors=False):
        if enable_monitors:
            for inst_id, toggle in getattr(self, 'hw_toggles', []):
                toggle.setChecked(True)
                resolution.set_hardware_monitor_state(inst_id, True)
            resolution.set_monitor_state(self.get_dev_name(), True)
            
        if resolution.reset_resolution(self.get_dev_name()):
            self.refresh_display()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'grip'):
            self.grip.move(self.width() - 20, self.height() - 20)

    def on_monitor_changed(self, index):
        dev_name = self.mon_combo.itemData(index)
        for d in self.displays:
            if d['name'] == dev_name:
                self.current_display = d
                break
        if self.current_display:
            self.refresh_display()
            self.on_safe_resolution_changed()

    def get_dev_name(self):
        return self.current_display['name'] if self.current_display else None

    def refresh_display(self):
        info = resolution.get_current_resolution(self.get_dev_name())
        if info:
            self.curr_res.setText(f"{info['width']} × {info['height']}")
            self.curr_hz.setText(f"{info['hz']} Hz")
        self.populate_pc_resolutions()
        QTimer.singleShot(100, self.adjust_window_size)
        
    def adjust_window_size(self):
        screen = QApplication.primaryScreen()
        if not screen: return
        rect = screen.availableGeometry()
        
        w = self.width()
        h = self.height()
        changed = False
        if w > rect.width():
            w = max(400, rect.width() - 50)
            changed = True
        if h > rect.height():
            h = max(400, rect.height() - 50)
            changed = True
            
        if changed:
            self.resize(w, h)
            self.move(rect.center() - self.rect().center())

    def update_tray_menu(self, presets_data=None):
        if not hasattr(self, 'tray_menu'): return
        self.tray_menu.clear()
        
        show_action = self.tray_menu.addAction("Show EasyRes")
        show_action.triggered.connect(self.showNormal)
        self.tray_menu.addSeparator()
        
        presets_menu = self.tray_menu.addMenu("Presets")
        hidden_presets = self.settings.value("hidden_presets", [])
        if isinstance(hidden_presets, str):
            hidden_presets = []
            
        if presets_data is None:
            dev_name = self.get_dev_name()
            presets_data = resolution.get_supported_resolutions(dev_name) or self._preset_cache.get(dev_name, [])
        for w, h, ratio, label, is_custom in presets_data:
            if f"{w}x{h}" not in hidden_presets:
                act = presets_menu.addAction(f"{w}x{h}")
                act.triggered.connect(lambda checked, width=w, height=h: self.change_res(width, height))
                
        customs = self.settings.value("custom_resolutions", [])
        customs = [c for c in customs if isinstance(c, dict) and all(key in c for key in ("name", "w", "h"))] if isinstance(customs, list) else []
        if customs:
            presets_menu.addSeparator()
            for c in customs:
                hz_text = f" @ {c.get('hz')}Hz" if c.get('hz') else ""
                act = presets_menu.addAction(f"{c['name']} ({c['w']}x{c['h']}{hz_text})")
                act.triggered.connect(lambda checked, width=c['w'], height=c['h'], freq=c.get('hz'): self.change_res(width, height, freq))
        
        self.tray_menu.addSeparator()
        
        native_act = self.tray_menu.addAction("Reset to Native (Keep Monitors Disabled)")
        native_act.triggered.connect(lambda: self.reset_res(enable_monitors=False))
        
        native_mon_act = self.tray_menu.addAction("Reset to Native (Enable Monitors)")
        native_mon_act.triggered.connect(lambda: self.reset_res(enable_monitors=True))
        
        self.tray_menu.addSeparator()
        
        quit_action = self.tray_menu.addAction("Quit")
        def quit_app():
            self.tray_icon.hide()
            QApplication.instance().quit()
        quit_action.triggered.connect(quit_app)

    def populate_pc_resolutions(self):
        if not hasattr(self, 'pc_res_combo'): return
        self.pc_res_combo.clear()
        dev = self.get_dev_name()
        if not dev: return
        modes = resolution.get_all_resolutions(dev)
        for w, h, hz in modes:
            if (w, h) not in resolution.VALORANT_SAFE_RESOLUTIONS:
                continue
            self.pc_res_combo.addItem(f"{w} × {h} @ {hz}Hz", (w, h, hz))

    def add_pc_resolution(self):
        data = self.pc_res_combo.currentData()
        if not data: return
        w, h, hz = data
        name = f"{w}x{h}@{hz}Hz (PC)"
        resolutions = self.settings.value("custom_resolutions", [])
        for r in resolutions:
            if r['w'] == w and r['h'] == h and r.get('hz') == hz:
                QMessageBox.warning(self, "Error", "This resolution is already in presets.")
                return
                
        resolutions.append({'name': name, 'w': w, 'h': h, 'hz': hz})
        self.settings.setValue("custom_resolutions", resolutions)
        self.load_presets()

